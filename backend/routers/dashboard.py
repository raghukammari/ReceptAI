"""
Dashboard API Router
Stats · Call logs · Transcripts · Appointments
All queries are scoped by tenant_id via JWT.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timedelta, timezone

from backend.services.database import get_db
from backend.models_tenant import (
    CallLog, AppointmentRecord, Customer,
    CallStatus, AppointmentStatus
)
from backend.auth_service import get_current_user, resolve_tenant
from backend.models_tenant import User, Tenant

router = APIRouter()


@router.get("/stats")
async def get_stats(
    user: User   = Depends(get_current_user),
    tenant: Tenant = Depends(resolve_tenant),
    db: AsyncSession = Depends(get_db),
):
    today = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0)

    calls_today = (await db.execute(
        select(func.count(CallLog.id))
        .where(CallLog.tenant_id == tenant.id)
        .where(CallLog.created_at >= today)
    )).scalar() or 0

    bookings_today = (await db.execute(
        select(func.count(CallLog.id))
        .where(CallLog.tenant_id == tenant.id)
        .where(CallLog.created_at >= today)
        .where(CallLog.intent == "book")
    )).scalar() or 0

    transfers_today = (await db.execute(
        select(func.count(CallLog.id))
        .where(CallLog.tenant_id == tenant.id)
        .where(CallLog.created_at >= today)
        .where(CallLog.status == CallStatus.TRANSFERRED)
    )).scalar() or 0

    avg_dur = (await db.execute(
        select(func.avg(CallLog.duration_seconds))
        .where(CallLog.tenant_id == tenant.id)
        .where(CallLog.created_at >= today)
        .where(CallLog.duration_seconds.isnot(None))
    )).scalar() or 0

    upcoming = (await db.execute(
        select(func.count(AppointmentRecord.id))
        .where(AppointmentRecord.tenant_id == tenant.id)
        .where(AppointmentRecord.status == AppointmentStatus.ACTIVE)
        .where(AppointmentRecord.start_time >= datetime.now(tz=timezone.utc))
    )).scalar() or 0

    return {
        "calls_today":          calls_today,
        "bookings_today":       bookings_today,
        "booking_rate":         round(bookings_today / calls_today * 100, 1) if calls_today else 0,
        "transfers_today":      transfers_today,
        "transfer_rate":        round(transfers_today / calls_today * 100, 1) if calls_today else 0,
        "avg_duration_seconds": int(avg_dur),
        "upcoming_appointments":upcoming,
        "plan_usage":           tenant.calls_this_month,
        "plan_limit":           tenant.call_limit_monthly,
    }


@router.get("/calls")
async def get_calls(
    limit: int     = Query(20, le=100),
    offset: int    = 0,
    user: User     = Depends(get_current_user),
    tenant: Tenant = Depends(resolve_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CallLog)
        .where(CallLog.tenant_id == tenant.id)
        .order_by(CallLog.created_at.desc())
        .limit(limit).offset(offset)
    )
    logs = result.scalars().all()
    return [
        {
            "id":             l.id,
            "call_sid":       l.call_sid,
            "caller":         l.caller_number,
            "caller_name":    l.caller_name,
            "status":         l.status,
            "intent":         l.intent,
            "duration_seconds": l.duration_seconds,
            "created_at":     l.created_at.isoformat(),
            "has_transcript": bool(l.transcript),
        }
        for l in logs
    ]


@router.get("/calls/{call_id}/transcript")
async def get_transcript(
    call_id: str,
    user: User     = Depends(get_current_user),
    tenant: Tenant = Depends(resolve_tenant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CallLog)
        .where(CallLog.id == call_id)
        .where(CallLog.tenant_id == tenant.id)  # tenant isolation
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(404, "Call not found")
    return {"transcript": log.transcript, "history": log.conversation_history}


@router.get("/appointments")
async def get_appointments(
    upcoming_only: bool = True,
    limit: int     = Query(50, le=200),
    user: User     = Depends(get_current_user),
    tenant: Tenant = Depends(resolve_tenant),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(AppointmentRecord)
        .where(AppointmentRecord.tenant_id == tenant.id)
        .order_by(AppointmentRecord.start_time)
        .limit(limit)
    )
    if upcoming_only:
        q = q.where(AppointmentRecord.start_time >= datetime.now(tz=timezone.utc))
        q = q.where(AppointmentRecord.status == AppointmentStatus.ACTIVE)

    result = await db.execute(q)
    appts  = result.scalars().all()
    return [
        {
            "id":                a.id,
            "customer_name":     a.customer_name,
            "customer_email":    a.customer_email,
            "customer_phone":    a.customer_phone,
            "service":           a.event_name,
            "start_time":        a.start_time.isoformat(),
            "status":            a.status,
            "reminder_24h_sent": a.reminder_24h_sent,
            "reminder_1h_sent":  a.reminder_1h_sent,
        }
        for a in appts
    ]
