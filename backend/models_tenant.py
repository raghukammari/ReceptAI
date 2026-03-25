"""
Multi-Tenant Database Models
Roles: super_admin · business_owner · staff
All business data is isolated by tenant_id at every query.
"""

from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
from sqlalchemy import (
    String, Boolean, DateTime, JSON, Text,
    Enum as SAEnum, ForeignKey, Integer
)
from datetime import datetime
import enum
import uuid


class Base(DeclarativeBase):
    pass


# ── Enums ─────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    SUPER_ADMIN    = "super_admin"
    BUSINESS_OWNER = "business_owner"
    STAFF          = "staff"


class VerticalType(str, enum.Enum):
    DENTAL  = "dental"
    SPA     = "spa"
    ROOFING = "roofing"
    BAKERY  = "bakery"
    GENERIC = "generic"


class CallStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"
    FAILED      = "failed"
    TRANSFERRED = "transferred"


class CallIntent(str, enum.Enum):
    BOOK       = "book"
    RESCHEDULE = "reschedule"
    CANCEL     = "cancel"
    INFO       = "info"
    TRANSFER   = "transfer"
    UNKNOWN    = "unknown"


class AppointmentStatus(str, enum.Enum):
    ACTIVE    = "active"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW   = "no_show"


# ── Tenant (one row = one business client) ────────────────

class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    vertical: Mapped[VerticalType] = mapped_column(SAEnum(VerticalType))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False)

    # Twilio
    twilio_phone_number: Mapped[str] = mapped_column(String(20), nullable=True)

    # Calendly (per-tenant credentials stored encrypted in production)
    calendly_user_uri: Mapped[str] = mapped_column(String(500), nullable=True)
    calendly_api_token_enc: Mapped[str] = mapped_column(Text, nullable=True)

    # Business config overrides (greeting, aiName, services, hours, templates etc.)
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    # Branding
    primary_color: Mapped[str] = mapped_column(String(10), default="#4f8ef7")
    logo_emoji: Mapped[str] = mapped_column(String(10), default="📅")

    # Billing
    plan: Mapped[str] = mapped_column(String(30), default="starter")
    calls_this_month: Mapped[int] = mapped_column(Integer, default=0)
    call_limit_monthly: Mapped[int] = mapped_column(Integer, default=500)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[str] = mapped_column(String(36), nullable=True)


# ── User ──────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    invited_by: Mapped[str] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Tenant Invite ─────────────────────────────────────────

class TenantInvite(Base):
    __tablename__ = "tenant_invites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"))
    email: Mapped[str] = mapped_column(String(200))
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.STAFF)
    invited_by: Mapped[str] = mapped_column(String(36))
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Call Log ──────────────────────────────────────────────

class CallLog(Base):
    __tablename__ = "call_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True, nullable=True)
    call_sid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    caller_number: Mapped[str] = mapped_column(String(20))
    caller_name: Mapped[str] = mapped_column(String(100), nullable=True)
    caller_email: Mapped[str] = mapped_column(String(200), nullable=True)
    status: Mapped[CallStatus] = mapped_column(SAEnum(CallStatus), default=CallStatus.IN_PROGRESS)
    intent: Mapped[CallIntent] = mapped_column(SAEnum(CallIntent), nullable=True)
    transcript: Mapped[str] = mapped_column(Text, nullable=True)
    conversation_history: Mapped[dict] = mapped_column(JSON, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
    recording_url: Mapped[str] = mapped_column(String(500), nullable=True)
    calendly_event_uri: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Customer ──────────────────────────────────────────────

class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True, nullable=True)
    phone: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=True)
    email: Mapped[str] = mapped_column(String(200), nullable=True)
    call_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Appointment ───────────────────────────────────────────

class AppointmentRecord(Base):
    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), index=True)
    calendly_event_uri: Mapped[str] = mapped_column(String(500), index=True)
    calendly_invitee_uri: Mapped[str] = mapped_column(String(500), nullable=True)
    customer_phone: Mapped[str] = mapped_column(String(20), index=True)
    customer_name: Mapped[str] = mapped_column(String(100))
    customer_email: Mapped[str] = mapped_column(String(200))
    event_name: Mapped[str] = mapped_column(String(200))
    start_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[AppointmentStatus] = mapped_column(SAEnum(AppointmentStatus), default=AppointmentStatus.ACTIVE)
    reminder_24h_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_1h_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    call_log_id: Mapped[str] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Audit Log ─────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    user_role: Mapped[str] = mapped_column(String(30))
    action: Mapped[str] = mapped_column(String(100))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
