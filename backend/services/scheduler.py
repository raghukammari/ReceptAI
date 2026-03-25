"""
Reminder Scheduler
Runs every 15 minutes. Fires 24h and 1h SMS/email reminders.
"""

import logging
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select

from backend.services.database import engine
from backend.models_tenant import AppointmentRecord, AppointmentStatus, Tenant
from backend.services.notifications import send_reminder_24h, send_reminder_1h

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def fire_reminders():
    """Check for appointments needing 24h or 1h reminders and fire them."""
    now = datetime.now(tz=timezone.utc)

    window_24h_start = now + timedelta(hours=23, minutes=45)
    window_24h_end   = now + timedelta(hours=24, minutes=15)
    window_1h_start  = now + timedelta(minutes=55)
    window_1h_end    = now + timedelta(hours=1, minutes=5)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AppointmentRecord)
            .where(AppointmentRecord.status == AppointmentStatus.ACTIVE)
            .where(AppointmentRecord.start_time >= now)
        )
        appointments = result.scalars().all()

        for appt in appointments:
            appt_utc = appt.start_time.replace(tzinfo=timezone.utc)

            # 24h reminder
            if window_24h_start <= appt_utc <= window_24h_end and not appt.reminder_24h_sent:
                logger.info(f"Firing 24h reminder → {appt.customer_name} ({appt.start_time})")
                try:
                    # Get tenant vertical
                    t_result = await db.execute(
                        select(Tenant).where(Tenant.id == appt.tenant_id)
                    )
                    tenant = t_result.scalar_one_or_none()
                    vertical_key = tenant.vertical if tenant else "generic"

                    await send_reminder_24h(
                        phone=appt.customer_phone,
                        email=appt.customer_email,
                        name=appt.customer_name,
                        service=appt.event_name,
                        start_time=appt.start_time.isoformat(),
                        vertical_key=vertical_key,
                    )
                    appt.reminder_24h_sent = True
                    await db.commit()
                except Exception as e:
                    logger.error(f"24h reminder failed for {appt.id}: {e}")

            # 1h reminder
            if window_1h_start <= appt_utc <= window_1h_end and not appt.reminder_1h_sent:
                logger.info(f"Firing 1h reminder → {appt.customer_name} ({appt.start_time})")
                try:
                    t_result = await db.execute(
                        select(Tenant).where(Tenant.id == appt.tenant_id)
                    )
                    tenant = t_result.scalar_one_or_none()
                    vertical_key = tenant.vertical if tenant else "generic"

                    time_str = appt.start_time.astimezone().strftime("%-I:%M %p")
                    await send_reminder_1h(
                        phone=appt.customer_phone,
                        name=appt.customer_name,
                        time=time_str,
                        vertical_key=vertical_key,
                    )
                    appt.reminder_1h_sent = True
                    await db.commit()
                except Exception as e:
                    logger.error(f"1h reminder failed for {appt.id}: {e}")


def start_scheduler():
    scheduler.add_job(fire_reminders, "interval", minutes=15, id="reminders", replace_existing=True)
    scheduler.start()
    logger.info("Reminder scheduler started (every 15 min)")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Reminder scheduler stopped")
