"""
Super Admin Router — /admin/*
Only accessible to role=super_admin (Adroit Associates)
Tenant CRUD · User provisioning · Audit trail · Platform stats
"""

import uuid
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from backend.models_tenant import (
    Tenant, User, UserRole, VerticalType,
    TenantInvite, AuditLog
)
from backend.auth_service import require_super_admin, hash_password
from backend.services.database import get_db

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────

class CreateTenantRequest(BaseModel):
    name:                 str
    slug:                 str
    vertical:             VerticalType
    owner_email:          EmailStr
    owner_name:           str
    owner_password:       str
    twilio_phone_number:  str = ""
    plan:                 str = "starter"
    primary_color:        str = "#4f8ef7"
    logo_emoji:           str = "📅"
    call_limit_monthly:   int = 500


class UpdateTenantRequest(BaseModel):
    name:               str | None = None
    is_active:          bool | None = None
    is_suspended:       bool | None = None
    plan:               str | None = None
    call_limit_monthly: int | None = None
    primary_color:      str | None = None
    logo_emoji:         str | None = None


class InviteUserRequest(BaseModel):
    email:     EmailStr
    name:      str
    role:      UserRole = UserRole.STAFF
    tenant_id: str


# ── Platform overview ─────────────────────────────────────

@router.get("/stats")
async def platform_stats(
    _:  User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    total_tenants  = (await db.execute(select(func.count(Tenant.id)))).scalar()
    active_tenants = (await db.execute(select(func.count(Tenant.id)).where(Tenant.is_active == True))).scalar()
    total_users    = (await db.execute(select(func.count(User.id)))).scalar()
    total_calls    = (await db.execute(select(func.sum(Tenant.calls_this_month)))).scalar() or 0

    return {
        "total_tenants":        total_tenants,
        "active_tenants":       active_tenants,
        "total_users":          total_users,
        "total_calls_this_month": total_calls,
    }


# ── Tenant management ─────────────────────────────────────

@router.get("/tenants")
async def list_tenants(
    _:  User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    result  = await db.execute(select(Tenant).order_by(Tenant.created_at.desc()))
    tenants = result.scalars().all()
    return [_tenant_dict(t) for t in tenants]


@router.post("/tenants", status_code=201)
async def create_tenant(
    body:  CreateTenantRequest,
    admin: User = Depends(require_super_admin),
    db:    AsyncSession = Depends(get_db),
):
    # Slug uniqueness
    slug_check = await db.execute(select(Tenant).where(Tenant.slug == body.slug))
    if slug_check.scalar_one_or_none():
        raise HTTPException(400, f"Slug '{body.slug}' is already taken")

    # Email uniqueness
    email_check = await db.execute(select(User).where(User.email == body.owner_email))
    if email_check.scalar_one_or_none():
        raise HTTPException(400, "Owner email is already registered")

    tenant_id = str(uuid.uuid4())
    user_id   = str(uuid.uuid4())

    tenant = Tenant(
        id=tenant_id, name=body.name, slug=body.slug,
        vertical=body.vertical, twilio_phone_number=body.twilio_phone_number,
        plan=body.plan, call_limit_monthly=body.call_limit_monthly,
        primary_color=body.primary_color, logo_emoji=body.logo_emoji,
        created_by=admin.id, config={},
    )
    owner = User(
        id=user_id, email=body.owner_email, name=body.owner_name,
        password_hash=hash_password(body.owner_password),
        role=UserRole.BUSINESS_OWNER, tenant_id=tenant_id,
    )

    db.add(tenant)
    db.add(owner)
    db.add(AuditLog(
        id=str(uuid.uuid4()), tenant_id=tenant_id,
        user_id=admin.id, user_role=admin.role,
        action="tenant.create",
        detail={"name": body.name, "vertical": body.vertical, "owner_email": body.owner_email},
    ))
    await db.commit()

    return {"tenant_id": tenant_id, "owner_id": user_id, "message": "Tenant and owner account created"}


@router.patch("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    body:  UpdateTenantRequest,
    admin: User = Depends(require_super_admin),
    db:    AsyncSession = Depends(get_db),
):
    res    = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(tenant, k, v)

    db.add(AuditLog(
        id=str(uuid.uuid4()), tenant_id=tenant_id,
        user_id=admin.id, user_role=admin.role,
        action="tenant.update", detail=changes,
    ))
    await db.commit()
    return {"message": "Updated", "changes": changes}


@router.post("/tenants/{tenant_id}/suspend")
async def suspend_tenant(
    tenant_id: str,
    admin: User = Depends(require_super_admin),
    db:    AsyncSession = Depends(get_db),
):
    await db.execute(update(Tenant).where(Tenant.id == tenant_id).values(is_suspended=True))
    db.add(AuditLog(
        id=str(uuid.uuid4()), tenant_id=tenant_id,
        user_id=admin.id, user_role=admin.role,
        action="tenant.suspend", detail={},
    ))
    await db.commit()
    return {"message": "Tenant suspended"}


@router.post("/tenants/{tenant_id}/reactivate")
async def reactivate_tenant(
    tenant_id: str,
    admin: User = Depends(require_super_admin),
    db:    AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Tenant).where(Tenant.id == tenant_id)
        .values(is_suspended=False, is_active=True)
    )
    db.add(AuditLog(
        id=str(uuid.uuid4()), tenant_id=tenant_id,
        user_id=admin.id, user_role=admin.role,
        action="tenant.reactivate", detail={},
    ))
    await db.commit()
    return {"message": "Tenant reactivated"}


# ── User management ───────────────────────────────────────

@router.get("/tenants/{tenant_id}/users")
async def list_tenant_users(
    tenant_id: str,
    _:  User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.tenant_id == tenant_id).order_by(User.created_at)
    )
    return [_user_dict(u) for u in result.scalars().all()]


@router.post("/users/invite")
async def invite_user(
    body:  InviteUserRequest,
    admin: User = Depends(require_super_admin),
    db:    AsyncSession = Depends(get_db),
):
    token = secrets.token_urlsafe(32)
    invite = TenantInvite(
        id=str(uuid.uuid4()), token=token,
        tenant_id=body.tenant_id, email=body.email,
        role=body.role, invited_by=admin.id,
        expires_at=datetime.now(tz=timezone.utc) + timedelta(days=7),
    )
    db.add(invite)
    db.add(AuditLog(
        id=str(uuid.uuid4()), tenant_id=body.tenant_id,
        user_id=admin.id, user_role=admin.role,
        action="user.invite",
        detail={"email": body.email, "role": body.role},
    ))
    await db.commit()
    return {
        "invite_token": token,
        "invite_link":  f"{'/accept-invite'}?token={token}",
        "expires_in":   "7 days",
    }


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: str,
    admin: User = Depends(require_super_admin),
    db:    AsyncSession = Depends(get_db),
):
    await db.execute(update(User).where(User.id == user_id).values(is_active=False))
    db.add(AuditLog(
        id=str(uuid.uuid4()), tenant_id=None,
        user_id=admin.id, user_role=admin.role,
        action="user.deactivate", detail={"target_user_id": user_id},
    ))
    await db.commit()
    return {"message": "User deactivated"}


# ── Audit logs ────────────────────────────────────────────

@router.get("/audit-logs")
async def get_audit_logs(
    tenant_id: str | None = None,
    limit:     int = 50,
    _:  User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    q = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if tenant_id:
        q = q.where(AuditLog.tenant_id == tenant_id)
    result = await db.execute(q)
    logs   = result.scalars().all()
    return [
        {
            "id":        l.id, "tenant_id": l.tenant_id,
            "user_id":   l.user_id, "user_role": l.user_role,
            "action":    l.action, "detail":    l.detail,
            "ip":        l.ip_address,
            "created_at":l.created_at.isoformat(),
        }
        for l in logs
    ]


# ── Helpers ───────────────────────────────────────────────

def _tenant_dict(t: Tenant) -> dict:
    return {
        "id": t.id, "name": t.name, "slug": t.slug,
        "vertical": t.vertical, "is_active": t.is_active,
        "is_suspended": t.is_suspended, "plan": t.plan,
        "calls_this_month": t.calls_this_month,
        "call_limit_monthly": t.call_limit_monthly,
        "primary_color": t.primary_color, "logo_emoji": t.logo_emoji,
        "twilio_phone_number": t.twilio_phone_number,
        "created_at": t.created_at.isoformat(),
    }


def _user_dict(u: User) -> dict:
    return {
        "id": u.id, "email": u.email, "name": u.name,
        "role": u.role, "tenant_id": u.tenant_id,
        "is_active": u.is_active,
        "last_login": u.last_login.isoformat() if u.last_login else None,
        "created_at": u.created_at.isoformat(),
    }
