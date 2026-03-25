"""
Tool Executor
Bridges Claude's tool_use calls → Calendly / DB / notifications
"""

import uuid
import logging
from datetime import datetime
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.services import calendly_service
from backend.services.notifications import (
    send_confirmation, send_cancellation, send_reschedule
)
from backend.models_tenant import (
    Customer, AppointmentRecord, AppointmentStatus, CallLog
)

logger = logging.getLogger(__name__)


async def execute_tool(
    tool_name: str,
    tool_input: dict,
    call_state: dict,
    db: AsyncSession,
    vertical_key: str,
    background_tasks: BackgroundTasks,
) -> dict:
    """Route a Claude tool call to the appropriate real-world action."""
    try:
        if tool_name == "check_availability":
            return await _check_availability(tool_input, vertical_key)

        elif tool_name == "book_appointment":
            return await _book_appointment(tool_input, call_state, db, vertical_key, background_tasks)

        elif tool_name == "find_customer_appointment":
            return await _find_appointment(tool_input, call_state, db)

        elif tool_name == "cancel_appointment":
            return await _cancel_appointment(tool_input, call_state, db, vertical_key, background_tasks)

        elif tool_name == "reschedule_appointment":
            return await _reschedule(tool_input, call_state, db, vertical_key, background_tasks)

        elif tool_name == "transfer_to_human":
            return {"status": "transfer", "reason": tool_input.get("reason", "Caller requested")}

        elif tool_name == "collect_caller_info":
            info = call_state.setdefault("caller_info", {})
            for k in ["name", "email", "phone"]:
                if tool_input.get(k):
                    info[k] = tool_input[k]
            if tool_input.get("additional_info"):
                info.update(tool_input["additional_info"])
            # Persist to customer table
            phone = info.get("phone", call_state.get("caller", ""))
            if phone:
                res = await db.execute(
                    select(Customer).where(Customer.phone == phone)
                    .where(Customer.tenant_id == call_state.get("tenant_id"))
                )
                cust = res.scalar_one_or_none()
                if cust:
                    if info.get("name"):  cust.name  = info["name"]
                    if info.get("email"): cust.email = info["email"]
                    await db.commit()
            return {"status": "saved", "info": info}

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.error(f"Tool '{tool_name}' failed: {e}")
        return {"error": str(e), "tool": tool_name}


async def _check_availability(tool_input: dict, vertical_key: str) -> dict:
    slug = tool_input.get("service_slug", "")
    event_type = await calendly_service.get_event_type_by_slug(slug)
    if not event_type:
        return {"error": "No event types found in Calendly. Please configure event types first.", "slots": []}

    slots = await calendly_service.get_available_slots(
        event_type_uri=event_type["uri"],
        date_preference=tool_input.get("date_preference", "tomorrow"),
    )

    if not slots:
        return {
            "status": "no_slots",
            "message": "No availability found for that date. Try a different day.",
            "event_type_uri": event_type["uri"],
        }

    return {
        "status": "available",
        "event_type_uri": event_type["uri"],
        "event_name": event_type.get("name", "Appointment"),
        "slots": slots[:3],
    }


async def _book_appointment(
    tool_input: dict, call_state: dict,
    db: AsyncSession, vertical_key: str, background_tasks: BackgroundTasks
) -> dict:
    name       = tool_input.get("customer_name")  or call_state.get("caller_info", {}).get("name", "")
    email      = tool_input.get("customer_email") or call_state.get("caller_info", {}).get("email", "")
    start_time = tool_input.get("slot_start_time")
    event_uri  = tool_input.get("event_type_uri")

    if not all([name, email, start_time, event_uri]):
        missing = [k for k, v in {"name": name, "email": email, "start_time": start_time, "event_type_uri": event_uri}.items() if not v]
        return {"error": f"Missing required fields: {', '.join(missing)}"}

    result = await calendly_service.create_invitee(
        event_type_uri=event_uri,
        start_time=start_time,
        name=name,
        email=email,
    )

    if result.get("status") == "booked":
        appt = AppointmentRecord(
            id=str(uuid.uuid4()),
            tenant_id=call_state.get("tenant_id", ""),
            calendly_event_uri=result.get("event_uri", ""),
            customer_phone=call_state.get("caller", ""),
            customer_name=name,
            customer_email=email,
            event_name=tool_input.get("service_name", "Appointment"),
            start_time=datetime.fromisoformat(start_time.replace("Z", "+00:00")),
            end_time=datetime.fromisoformat(start_time.replace("Z", "+00:00")),
            call_log_id=call_state.get("call_id"),
        )
        db.add(appt)
        await db.commit()

        background_tasks.add_task(
            send_confirmation,
            phone=call_state.get("caller", ""),
            email=email, name=name,
            service=tool_input.get("service_name", "Appointment"),
            start_time=start_time,
            vertical_key=vertical_key,
        )

    return result


async def _find_appointment(tool_input: dict, call_state: dict, db: AsyncSession) -> dict:
    phone = tool_input.get("phone") or call_state.get("caller", "")
    email = tool_input.get("email") or call_state.get("caller_info", {}).get("email")

    if phone:
        res = await db.execute(
            select(AppointmentRecord)
            .where(AppointmentRecord.customer_phone == phone)
            .where(AppointmentRecord.tenant_id == call_state.get("tenant_id"))
            .where(AppointmentRecord.status == AppointmentStatus.ACTIVE)
            .order_by(AppointmentRecord.start_time)
        )
        appts = res.scalars().all()
        if appts:
            a = appts[0]
            return {"found": True, "appointment": {
                "id": a.id, "service": a.event_name,
                "start_time": a.start_time.isoformat(),
                "customer_name": a.customer_name, "customer_email": a.customer_email,
                "invitee_uri": a.calendly_invitee_uri, "event_uri": a.calendly_event_uri,
            }}

    if email:
        appt = await calendly_service.get_invitee_by_email(email)
        if appt:
            return {"found": True, "appointment": appt}

    return {"found": False, "message": "No upcoming appointment found. Would you like to book one?"}


async def _cancel_appointment(
    tool_input: dict, call_state: dict,
    db: AsyncSession, vertical_key: str, background_tasks: BackgroundTasks
) -> dict:
    invitee_uri = tool_input.get("invitee_uri")
    if not invitee_uri:
        return {"error": "No appointment URI provided"}

    result = await calendly_service.cancel_invitee(invitee_uri, tool_input.get("reason", "Cancelled via phone"))

    await db.execute(
        update(AppointmentRecord)
        .where(AppointmentRecord.calendly_invitee_uri == invitee_uri)
        .values(status=AppointmentStatus.CANCELLED)
    )
    await db.commit()

    info = call_state.get("caller_info", {})
    background_tasks.add_task(
        send_cancellation,
        phone=call_state.get("caller", ""),
        email=info.get("email", ""),
        name=info.get("name", ""),
        vertical_key=vertical_key,
    )
    return result


async def _reschedule(
    tool_input: dict, call_state: dict,
    db: AsyncSession, vertical_key: str, background_tasks: BackgroundTasks
) -> dict:
    await calendly_service.cancel_invitee(tool_input["invitee_uri"], "Rescheduled via AI receptionist")

    info = call_state.get("caller_info", {})
    new_result = await calendly_service.create_invitee(
        event_type_uri=tool_input["event_type_uri"],
        start_time=tool_input["new_slot_start_time"],
        name=info.get("name", ""),
        email=info.get("email", ""),
    )

    background_tasks.add_task(
        send_reschedule,
        phone=call_state.get("caller", ""),
        email=info.get("email", ""),
        name=info.get("name", ""),
        new_start_time=tool_input["new_slot_start_time"],
        vertical_key=vertical_key,
    )
    return {"status": "rescheduled", "new_booking": new_result}
