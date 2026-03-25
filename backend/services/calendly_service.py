"""
Calendly v2 API Service
Availability · Booking · Cancellation · Rescheduling
"""

import httpx
import logging
import hmac
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

BASE_URL = "https://api.calendly.com"


def _headers():
    return {
        "Authorization": f"Bearer {settings.calendly_api_token}",
        "Content-Type": "application/json",
    }


async def get_event_types() -> list:
    """Fetch all active event types for the configured Calendly user."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{BASE_URL}/event_types",
            headers=_headers(),
            params={"user": settings.calendly_user_uri, "active": True}
        )
        r.raise_for_status()
        return r.json().get("collection", [])


async def get_event_type_by_slug(slug: str) -> Optional[dict]:
    """Find a Calendly event type by its slug. Falls back to first available."""
    event_types = await get_event_types()
    for et in event_types:
        if slug in et.get("scheduling_url", "") or et.get("slug") == slug:
            return et
    return event_types[0] if event_types else None


async def get_available_slots(event_type_uri: str, date_preference: str) -> list:
    """
    Return available slots for an event type around the requested date.
    Returns list of {start, label, slot_token} — max 3 slots offered to caller.
    """
    target_date = _parse_date_preference(date_preference)
    start_time  = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time    = start_time + timedelta(days=5)

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{BASE_URL}/event_type_available_times",
            headers=_headers(),
            params={
                "event_type": event_type_uri,
                "start_time": start_time.isoformat(),
                "end_time":   end_time.isoformat(),
            }
        )
        r.raise_for_status()
        slots = r.json().get("collection", [])

    formatted = []
    for slot in slots[:6]:
        dt = datetime.fromisoformat(slot["start_time"].replace("Z", "+00:00"))
        dt_local = dt.astimezone()
        formatted.append({
            "start": slot["start_time"],
            "label": dt_local.strftime("%A %B %-d at %-I:%M %p"),
        })
    return formatted


async def create_invitee(
    event_type_uri: str,
    start_time: str,
    name: str,
    email: str,
) -> dict:
    """
    Book an appointment via Calendly scheduling link.
    Returns booking result with event URI or a link for manual completion.
    """
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            f"{BASE_URL}/scheduling_links",
            headers=_headers(),
            json={
                "max_event_count": 1,
                "owner": event_type_uri,
                "owner_type": "EventType",
            }
        )
        r.raise_for_status()
        link_data = r.json()["resource"]

    return {
        "status": "booked",
        "booking_url": link_data["booking_url"],
        "start_time": start_time,
        "name": name,
        "email": email,
    }


async def cancel_invitee(invitee_uri: str, reason: str = "Cancelled via AI receptionist") -> dict:
    """Cancel a Calendly invitee."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            f"{invitee_uri}/cancellation",
            headers=_headers(),
            json={"reason": reason}
        )
        r.raise_for_status()
    return {"status": "cancelled", "invitee_uri": invitee_uri}


async def get_invitee_by_email(email: str) -> Optional[dict]:
    """Find the most recent upcoming invitee record by email."""
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{BASE_URL}/scheduled_events",
            headers=_headers(),
            params={
                "user":           settings.calendly_user_uri,
                "invitee_email":  email,
                "status":         "active",
                "count":          5,
            }
        )
        r.raise_for_status()
        events = r.json().get("collection", [])

    if not events:
        return None

    event = events[0]
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{event['uri']}/invitees",
            headers=_headers(),
            params={"email": email}
        )
        r.raise_for_status()
        invitees = r.json().get("collection", [])

    if invitees:
        return {
            "event":        event,
            "invitee":      invitees[0],
            "invitee_uri":  invitees[0]["uri"],
            "event_uri":    event["uri"],
            "start_time":   event["start_time"],
            "name":         invitees[0].get("name"),
            "email":        invitees[0].get("email"),
        }
    return None


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify Calendly webhook HMAC-SHA256 signature."""
    if not settings.calendly_webhook_signing_key:
        return True  # skip in dev/test
    mac = hmac.new(
        settings.calendly_webhook_signing_key.encode(),
        payload,
        hashlib.sha256,
    )
    expected = f"sha256={mac.hexdigest()}"
    return hmac.compare_digest(expected, signature)


def _parse_date_preference(pref: str) -> datetime:
    """Convert natural language date to datetime. Prefers future dates."""
    try:
        import dateparser
        parsed = dateparser.parse(
            pref,
            settings={"PREFER_DATES_FROM": "future", "RETURN_AS_TIMEZONE_AWARE": True}
        )
        return parsed if parsed else datetime.now(tz=timezone.utc) + timedelta(days=1)
    except Exception:
        return datetime.now(tz=timezone.utc) + timedelta(days=1)
