"""
Claude AI Conversation Engine
Vertical-aware system prompt · Tool calling · Intent detection
"""

import json
import logging
from typing import Optional, Tuple
import anthropic

from backend.settings import get_settings
from backend.verticals import get_vertical

settings = get_settings()
logger = logging.getLogger(__name__)
client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

TOOLS = [
    {
        "name": "check_availability",
        "description": "Check available Calendly slots for a given date and service type",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_preference": {"type": "string", "description": "e.g. 'tomorrow', 'next Monday', '2026-03-25'"},
                "service_slug":    {"type": "string", "description": "Calendly event type slug"}
            },
            "required": ["date_preference"]
        }
    },
    {
        "name": "book_appointment",
        "description": "Book a confirmed appointment slot in Calendly",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_name":    {"type": "string"},
                "customer_email":   {"type": "string"},
                "slot_start_time":  {"type": "string", "description": "ISO 8601 datetime"},
                "event_type_uri":   {"type": "string"},
                "service_name":     {"type": "string"}
            },
            "required": ["customer_name", "customer_email", "slot_start_time", "event_type_uri"]
        }
    },
    {
        "name": "find_customer_appointment",
        "description": "Find an existing appointment by phone number or email",
        "input_schema": {
            "type": "object",
            "properties": {
                "phone": {"type": "string"},
                "email": {"type": "string"}
            }
        }
    },
    {
        "name": "cancel_appointment",
        "description": "Cancel an existing appointment by invitee URI",
        "input_schema": {
            "type": "object",
            "properties": {
                "invitee_uri": {"type": "string"},
                "reason":      {"type": "string"}
            },
            "required": ["invitee_uri"]
        }
    },
    {
        "name": "reschedule_appointment",
        "description": "Cancel old slot and book a new one",
        "input_schema": {
            "type": "object",
            "properties": {
                "invitee_uri":        {"type": "string"},
                "new_slot_start_time":{"type": "string"},
                "event_type_uri":     {"type": "string"}
            },
            "required": ["invitee_uri", "new_slot_start_time", "event_type_uri"]
        }
    },
    {
        "name": "transfer_to_human",
        "description": "Transfer the call to a human staff member",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason":  {"type": "string"},
                "urgency": {"type": "string", "enum": ["normal", "urgent"]}
            },
            "required": ["reason"]
        }
    },
    {
        "name": "collect_caller_info",
        "description": "Save caller name, email, phone collected during conversation",
        "input_schema": {
            "type": "object",
            "properties": {
                "name":            {"type": "string"},
                "email":           {"type": "string"},
                "phone":           {"type": "string"},
                "additional_info": {"type": "object"}
            }
        }
    }
]


def build_system_prompt(vertical_key: str, caller_phone: str, current_time: str) -> str:
    v = get_vertical(vertical_key)

    services_list = "\n".join(
        f"  - {s['name']} ({s['duration_min']} min) → slug: {s['calendly_slug']}"
        for s in v.get("services", [])
    )

    faq_text = "\n".join(
        f"  Q: {q}\n  A: {a}" for q, a in v.get("faq", {}).items()
    ) or "  (none configured)"

    intake_qs = "\n".join(
        f"  {i+1}. {q}" for i, q in enumerate(v.get("intake_questions", []))
    )

    transfer_triggers = ", ".join(v.get("transfer_triggers", ["emergency", "speak to human"]))

    hours_lines = ""
    for day, h in v.get("business_hours", {}).items():
        if h:
            hours_lines += f"  {day.capitalize()}: {h['open']} – {h['close']}\n"
        else:
            hours_lines += f"  {day.capitalize()}: Closed\n"

    return f"""You are {v['receptionist_name']}, the AI receptionist for {v['business_name']}.
{v.get('tagline', '')}

Current date/time: {current_time}
Caller phone: {caller_phone}

## YOUR ROLE
Handle inbound phone calls. Your goals:
1. Greet callers warmly and professionally
2. Detect intent: book / reschedule / cancel / info / transfer
3. Collect required information naturally through conversation
4. Use tools to check availability and manage appointments
5. Confirm before executing any action
6. End calls warmly

## BUSINESS HOURS
{hours_lines}
If caller contacts outside business hours, let them know and offer to book a future slot.

## SERVICES
{services_list}

## INTAKE QUESTIONS (ask naturally, not as a form)
{intake_qs}

## FAQ
{faq_text}

## ESCALATE IMMEDIATELY IF CALLER MENTIONS:
{transfer_triggers}

## PHONE CALL RULES — CRITICAL
- Keep responses SHORT — max 2 sentences. This is a phone call, not a chat.
- NEVER read long lists. Offer 2-3 options max.
- Spell out times: "three thirty PM" not "3:30 PM"
- Spell out dates: "Tuesday March twenty-fifth" not "2026-03-25"
- Always confirm before booking: "Just to confirm — [service] for [name] on [date] at [time]. Does that sound right?"
- If you don't understand after 2 attempts, offer to transfer to a team member
- Collect name and email before booking — required for Calendly
- Never invent availability — always use check_availability tool first

## TOOL RULES
- check_availability BEFORE offering any slots
- collect_caller_info as soon as you have name/email/phone
- transfer_to_human immediately for urgent escalation triggers
- After booking: confirm verbally and mention confirmation SMS/email will be sent

## FORMAT
Plain conversational text only. No markdown, no bullets, no lists.
This text will be spoken aloud via text-to-speech.
"""


async def process_turn(
    vertical_key: str,
    caller_phone: str,
    conversation_history: list,
    user_message: str,
    current_time: str,
    tool_executor=None,
) -> Tuple[str, list, Optional[dict]]:
    """Process one conversation turn. Returns (response_text, updated_history, tool_result)."""

    history = conversation_history + [{"role": "user", "content": user_message}]
    system_prompt = build_system_prompt(vertical_key, caller_phone, current_time)

    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=512,
        system=system_prompt,
        tools=TOOLS,
        messages=history,
    )

    tool_result_data = None

    if response.stop_reason == "tool_use":
        tool_use_block = next((b for b in response.content if b.type == "tool_use"), None)

        if tool_use_block and tool_executor:
            tool_name  = tool_use_block.name
            tool_input = tool_use_block.input
            logger.info(f"Claude calling tool: {tool_name} → {tool_input}")

            tool_result = await tool_executor(tool_name, tool_input)
            tool_result_data = {"tool": tool_name, "input": tool_input, "result": tool_result}

            history = history + [
                {"role": "assistant", "content": response.content},
                {
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_use_block.id,
                        "content": json.dumps(tool_result),
                    }],
                },
            ]

            final = await client.messages.create(
                model=settings.claude_model,
                max_tokens=512,
                system=system_prompt,
                tools=TOOLS,
                messages=history,
            )
            response_text = _extract_text(final)
        else:
            response_text = _extract_text(response)
    else:
        response_text = _extract_text(response)

    history = history + [{"role": "assistant", "content": response_text}]
    return response_text, history, tool_result_data


def _extract_text(response) -> str:
    for block in response.content:
        if hasattr(block, "text"):
            return block.text.strip()
    return "I'm sorry, I didn't catch that. Could you please repeat that?"


async def classify_intent(transcript: str) -> str:
    """Classify the dominant intent of a completed call for logging."""
    result = await client.messages.create(
        model=settings.claude_model,
        max_tokens=10,
        messages=[{
            "role": "user",
            "content": (
                f"Classify this call transcript into ONE word: "
                f"book, reschedule, cancel, info, transfer, or unknown.\n\n"
                f"Transcript: {transcript[:500]}\n\nOne word only:"
            )
        }]
    )
    raw = _extract_text(result).lower().strip().split()[0]
    return raw if raw in {"book", "reschedule", "cancel", "info", "transfer", "unknown"} else "unknown"
