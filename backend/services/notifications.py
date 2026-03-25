"""
Notification Service
SMS via Twilio · Email via SendGrid
All templates rendered per business vertical.
"""

import logging
from datetime import datetime, timezone
from backend.settings import get_settings
from backend.verticals import get_vertical

settings = get_settings()
logger = logging.getLogger(__name__)


def _format_dt(iso_str: str):
    """Parse ISO datetime → (friendly_date, friendly_time)."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%A, %B %-d"), dt.astimezone().strftime("%-I:%M %p")
    except Exception:
        return iso_str, ""


def _render(template: str, **kwargs) -> str:
    """Simple template renderer — replaces {key} tokens."""
    kwargs.setdefault("business_name", settings.business_name if hasattr(settings, 'business_name') else "Our Business")
    for k, v in kwargs.items():
        template = template.replace(f"{{{k}}}", str(v or ""))
    return template


def _email_html(vertical: dict, heading: str, body_lines: list) -> str:
    """Build branded HTML email."""
    color   = vertical.get("primary_color", "#2c3e50")
    emoji   = vertical.get("logo_emoji", "📅")
    biz     = vertical.get("business_name", "Our Business")
    lines   = "".join(f"<p style='margin:8px 0;color:#444;font-size:15px;'>{l}</p>" for l in body_lines)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px;">
<div style="max-width:500px;margin:auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
  <div style="background:{color};padding:24px 32px;text-align:center;">
    <div style="font-size:36px;margin-bottom:8px;">{emoji}</div>
    <div style="color:white;font-size:20px;font-weight:600;">{biz}</div>
  </div>
  <div style="padding:28px 32px;">
    <h2 style="color:{color};margin:0 0 16px;font-size:18px;">{heading}</h2>
    {lines}
    <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
    <p style="color:#999;font-size:12px;text-align:center;">{biz} · Powered by ReceptAI</p>
  </div>
</div></body></html>"""


async def _send_sms(to_phone: str, body: str):
    if not to_phone or not body or not settings.twilio_account_sid:
        logger.warning(f"SMS skipped — missing phone or Twilio config")
        return
    try:
        from twilio.rest import Client
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        msg = client.messages.create(body=body, from_=settings.twilio_phone_number, to=to_phone)
        logger.info(f"SMS sent to {to_phone}: {msg.sid}")
    except Exception as e:
        logger.error(f"SMS failed to {to_phone}: {e}")


async def _send_email(to_email: str, subject: str, html_body: str):
    if not to_email or not settings.sendgrid_api_key:
        logger.warning(f"Email skipped — missing email or SendGrid config")
        return
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        sg = SendGridAPIClient(settings.sendgrid_api_key)
        mail = Mail(
            from_email=(settings.sendgrid_from_email, settings.sendgrid_from_name),
            to_emails=to_email,
            subject=subject,
            html_content=html_body,
        )
        r = sg.send(mail)
        logger.info(f"Email sent to {to_email}: {r.status_code}")
    except Exception as e:
        logger.error(f"Email failed to {to_email}: {e}")


# ── Public functions ───────────────────────────────────────

async def send_confirmation(
    phone: str, email: str, name: str,
    service: str, start_time: str, vertical_key: str
):
    v = get_vertical(vertical_key)
    date, time = _format_dt(start_time)
    tmpl = v.get("sms_templates", {})

    sms = _render(tmpl.get("confirmation", "Hi {name}, your appointment is confirmed for {date} at {time}."),
                  name=name, date=date, time=time, service=service, business_name=v["business_name"])
    await _send_sms(phone, sms)

    et = v.get("email_templates", {})
    subject = _render(et.get("confirmation_subject", "Appointment Confirmed — {date}"),
                      service=service, date=date, time=time)
    html = _email_html(v, f"Appointment Confirmed! {v.get('logo_emoji','✅')}", [
        f"Hi <strong>{name}</strong>,",
        f"Your <strong>{service}</strong> is confirmed for:",
        f"📅 <strong>{date} at {time}</strong>",
        "You'll receive a reminder 24 hours and 1 hour before your appointment.",
        f"Need to change? Call {v['business_name']} or reply to this email.",
    ])
    await _send_email(email, subject, html)


async def send_reminder_24h(
    phone: str, email: str, name: str,
    service: str, start_time: str, vertical_key: str
):
    v = get_vertical(vertical_key)
    date, time = _format_dt(start_time)
    tmpl = v.get("sms_templates", {})

    sms = _render(tmpl.get("reminder_24h", "Hi {name}, reminder: {service} tomorrow at {time}. Reply CONFIRM or CANCEL."),
                  name=name, date=date, time=time, service=service, business_name=v["business_name"])
    await _send_sms(phone, sms)

    et = v.get("email_templates", {})
    subject = _render(et.get("reminder_subject", "Reminder: Your appointment is tomorrow at {time}"), time=time)
    html = _email_html(v, "See you tomorrow! 👋", [
        f"Hi <strong>{name}</strong>,",
        f"Reminder: your <strong>{service}</strong> is tomorrow at <strong>{time}</strong>.",
        "Reply CONFIRM to confirm or CANCEL to cancel.",
        f"— {v['business_name']}",
    ])
    await _send_email(email, subject, html)


async def send_reminder_1h(phone: str, name: str, time: str, vertical_key: str):
    v = get_vertical(vertical_key)
    tmpl = v.get("sms_templates", {})
    sms = _render(tmpl.get("reminder_1h", "Hi {name}! Your appointment is in 1 hour at {time}."),
                  name=name, time=time, business_name=v["business_name"])
    await _send_sms(phone, sms)


async def send_cancellation(
    phone: str, email: str, name: str,
    vertical_key: str, date: str = ""
):
    v = get_vertical(vertical_key)
    tmpl = v.get("sms_templates", {})
    sms = _render(tmpl.get("cancellation", "Hi {name}, your appointment on {date} has been cancelled."),
                  name=name, date=date, business_name=v["business_name"])
    await _send_sms(phone, sms)

    et = v.get("email_templates", {})
    subject = _render(et.get("cancellation_subject", "Appointment Cancelled — {date}"), date=date)
    html = _email_html(v, "Appointment Cancelled", [
        f"Hi <strong>{name}</strong>,",
        f"Your appointment on <strong>{date}</strong> has been cancelled.",
        f"Call us anytime to rebook. — {v['business_name']}",
    ])
    await _send_email(email, subject, html)


async def send_reschedule(
    phone: str, email: str, name: str,
    new_start_time: str, vertical_key: str
):
    v = get_vertical(vertical_key)
    date, time = _format_dt(new_start_time)
    tmpl = v.get("sms_templates", {})
    sms = _render(tmpl.get("reschedule", "Hi {name}, rescheduled to {date} at {time}."),
                  name=name, date=date, time=time, business_name=v["business_name"])
    await _send_sms(phone, sms)

    html = _email_html(v, "Appointment Rescheduled", [
        f"Hi <strong>{name}</strong>,",
        f"Your appointment has been rescheduled to:",
        f"📅 <strong>{date} at {time}</strong>",
        f"— {v['business_name']}",
    ])
    await _send_email(email, f"Appointment Rescheduled — {date}", html)
