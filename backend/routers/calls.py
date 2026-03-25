"""
Twilio Call Handler Router
Inbound calls → TwiML greeting → STT → Claude → TTS → loop
"""

import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Response, Depends, BackgroundTasks
from twilio.twiml.voice_response import VoiceResponse, Gather
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update as sql_update

from backend.settings import get_settings
from backend.verticals import get_vertical
from backend.services.database import get_db
from backend.models_tenant import (
    CallLog, Customer, CallStatus, Tenant
)
from backend.services.claude_engine import process_turn, classify_intent
from backend.services.tool_executor import execute_tool

settings = get_settings()
logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory call state — use Redis in production for multi-instance
active_calls: dict = {}


def xml_response(xml: str) -> Response:
    return Response(content=xml, media_type="application/xml")


def make_gather(speech: str, action_url: str, vertical: dict, timeout: int = 5) -> str:
    """Build TwiML: say something and listen for speech."""
    vr = VoiceResponse()
    gather = Gather(
        input="speech",
        action=action_url,
        method="POST",
        timeout=timeout,
        speech_timeout="auto",
        language="en-US",
        action_on_empty_result=True,
    )
    gather.say(speech, voice=vertical.get("voice", "Polly.Joanna"), language="en-US")
    vr.append(gather)
    vr.redirect(action_url + ("&" if "?" in action_url else "?") + "no_input=1")
    return str(vr)


async def _get_tenant_for_phone(phone: str, db: AsyncSession) -> Tenant | None:
    """Look up which tenant owns this Twilio phone number."""
    result = await db.execute(
        select(Tenant)
        .where(Tenant.twilio_phone_number == phone)
        .where(Tenant.is_active == True)
    )
    return result.scalar_one_or_none()


# ── 1. Inbound Call ───────────────────────────────────────

@router.post("/incoming")
async def incoming_call(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    form     = await request.form()
    call_sid = form.get("CallSid", "")
    caller   = form.get("From", "Unknown")
    called   = form.get("To", "")

    logger.info(f"Inbound call: {call_sid} from {caller} to {called}")

    # Resolve tenant from called number
    tenant = await _get_tenant_for_phone(called, db)
    if not tenant:
        logger.warning(f"No tenant found for number {called} — using default vertical")
        vertical_key = settings.business_type
        tenant_id    = None
    else:
        vertical_key = tenant.vertical
        tenant_id    = tenant.id

    vertical = get_vertical(vertical_key)
    call_id  = str(uuid.uuid4())

    # Save call log
	log = CallLog(
        id=call_id, call_sid=call_sid,
        tenant_id=tenant_id if tenant_id else None,
        caller_number=caller,
        status=CallStatus.IN_PROGRESS,
        conversation_history=[],
    )
    db.add(log)

    # Upsert customer (only if tenant exists)
    if tenant_id:
        res = await db.execute(
            select(Customer)
            .where(Customer.phone == caller)
            .where(Customer.tenant_id == tenant_id)
        )
        cust = res.scalar_one_or_none()
        if not cust:
            db.add(Customer(id=str(uuid.uuid4()), tenant_id=tenant_id, phone=caller, call_count=1))
        else:
            cust.call_count += 1

    await db.commit()

    # Store conversation state
    active_calls[call_sid] = {
        "call_id":    call_id,
        "caller":     caller,
        "tenant_id":  tenant_id,
        "vertical":   vertical_key,
        "history":    [],
        "transcript": "",
        "caller_info":{"phone": caller},
        "turn":       0,
    }

    action_url = f"{settings.base_url}/calls/respond?call_sid={call_sid}"
    return xml_response(make_gather(vertical["greeting"], action_url, vertical))


# ── 2. Conversation Turn ────────────────────────────────

@router.post("/respond")
async def respond(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    form         = await request.form()
    call_sid     = form.get("CallSid", "")
    speech       = form.get("SpeechResult", "").strip()
    no_input     = request.query_params.get("no_input", "0") == "1"

    state = active_calls.get(call_sid)
    if not state:
        vr = VoiceResponse()
        vr.say("I'm sorry, I lost track of our conversation. Please call back and I'll be happy to help.")
        vr.hangup()
        return xml_response(str(vr))

    vertical_key = state["vertical"]
    vertical     = get_vertical(vertical_key)
    action_url   = f"{settings.base_url}/calls/respond?call_sid={call_sid}"
    state["turn"] += 1

    # No input
    if no_input or not speech:
        if state["turn"] > 8:
            return await _end_call(call_sid, "Thank you for calling. Goodbye!", db)
        return xml_response(make_gather(
            "I didn't catch that. Could you repeat what you'd like to do?",
            action_url, vertical, timeout=6
        ))

    state["transcript"] += f"Caller: {speech}\n"
    current_time = datetime.now(tz=timezone.utc).strftime("%A, %B %-d %Y at %-I:%M %p UTC")

    async def tool_executor(tool_name, tool_input):
        return await execute_tool(
            tool_name=tool_name, tool_input=tool_input,
            call_state=state, db=db,
            vertical_key=vertical_key,
            background_tasks=background_tasks,
        )

    try:
        response_text, updated_history, tool_result = await process_turn(
            vertical_key=vertical_key,
            caller_phone=state["caller"],
            conversation_history=state["history"],
            user_message=speech,
            current_time=current_time,
            tool_executor=tool_executor,
        )
    except Exception as e:
        logger.error(f"Claude error on {call_sid}: {e}")
        response_text = "I'm having a little trouble right now. Let me connect you with a team member."
        return await _transfer_call(call_sid, response_text, vertical)

    state["history"] = updated_history
    state["transcript"] += f"{vertical.get('receptionist_name','AI')}: {response_text}\n"

    # Transfer trigger
    if tool_result and tool_result.get("tool") == "transfer_to_human":
        return await _transfer_call(call_sid, response_text, vertical)

    # Detect end-of-call
    end_phrases = ["goodbye", "have a great day", "thank you for calling", "take care", "bye-bye"]
    if any(p in response_text.lower() for p in end_phrases):
        background_tasks.add_task(_finalize_call, call_sid, state)
        vr = VoiceResponse()
        vr.say(response_text, voice=vertical.get("voice", "Polly.Joanna"), language="en-US")
        vr.hangup()
        return xml_response(str(vr))

    # Max turns guard
    if state["turn"] >= 25:
        return await _end_call(call_sid, response_text, db)

    return xml_response(make_gather(response_text, action_url, vertical))


# ── 3. Status Callback ────────────────────────────────────

@router.post("/status")
async def call_status(request: Request, db: AsyncSession = Depends(get_db)):
    form     = await request.form()
    call_sid = form.get("CallSid", "")
    status   = form.get("CallStatus", "")
    duration = form.get("CallDuration", 0)

    logger.info(f"Call {call_sid}: {status} ({duration}s)")

    await db.execute(
        sql_update(CallLog)
        .where(CallLog.call_sid == call_sid)
        .values(
            duration_seconds=int(duration) if duration else None,
            status=CallStatus.COMPLETED if status == "completed" else CallStatus.FAILED,
        )
    )
    await db.commit()
    active_calls.pop(call_sid, None)
    return Response(status_code=204)


# ── Helpers ───────────────────────────────────────────────

async def _transfer_call(call_sid: str, announcement: str, vertical: dict) -> Response:
    vr = VoiceResponse()
    vr.say(announcement, voice=vertical.get("voice", "Polly.Joanna"), language="en-US")
    vr.say(
        f"Please hold while I connect you with a team member.",
        voice=vertical.get("voice", "Polly.Joanna"),
    )
    if settings.transfer_phone_number:
        vr.dial(settings.transfer_phone_number)
    else:
        vr.say("I'm sorry, no one is available right now. Please call back during business hours.")
        vr.hangup()
    active_calls.pop(call_sid, None)
    return xml_response(str(vr))


async def _end_call(call_sid: str, final_text: str, db: AsyncSession) -> Response:
    state   = active_calls.get(call_sid, {})
    vertical = get_vertical(state.get("vertical", "generic"))
    vr = VoiceResponse()
    vr.say(final_text, voice=vertical.get("voice", "Polly.Joanna"), language="en-US")
    vr.hangup()
    active_calls.pop(call_sid, None)
    return xml_response(str(vr))


async def _finalize_call(call_sid: str, state: dict):
    """Background: persist transcript + classify intent."""
    from backend.services.database import AsyncSessionLocal
    transcript = state.get("transcript", "")
    intent     = await classify_intent(transcript)

    async with AsyncSessionLocal() as db:
        await db.execute(
            sql_update(CallLog)
            .where(CallLog.call_sid == call_sid)
            .values(
                transcript=transcript,
                conversation_history=state.get("history", []),
                intent=intent,
                status=CallStatus.COMPLETED,
            )
        )
        await db.commit()
