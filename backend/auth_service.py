"""
Auth Service
JWT tokens · Role guards · Tenant scope enforcement
Every protected endpoint calls require_tenant_access() to enforce isolation.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
import bcrypt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models_tenant import User, Tenant, UserRole
from backend.services.database import get_db
from backend.settings import get_settings

settings = get_settings()

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 hours

bearer_scheme = HTTPBearer()


# ── Token ─────────────────────────────────────────────────

def create_access_token(user_id: str, role: str, tenant_id: Optional[str]) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
        "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.now(tz=timezone.utc),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired — please log in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")


# ── Current user dependency ───────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(credentials.credentials)
    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or deactivated")
    return user


# ── Role guards ───────────────────────────────────────────

def require_super_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Super admin access required")
    return user


def require_owner_or_above(user: User = Depends(get_current_user)) -> User:
    if user.role not in (UserRole.SUPER_ADMIN, UserRole.BUSINESS_OWNER):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Business owner access required")
    return user


def require_any_auth(user: User = Depends(get_current_user)) -> User:
    return user


# ── Core tenant isolation check ───────────────────────────

async def require_tenant_access(
    tenant_id: str,
    user: User,
    db: AsyncSession,
) -> Tenant:
    """
    THE key isolation function.
    super_admin  → can access any tenant
    business_owner / staff → can ONLY access their own tenant_id
    Raises HTTP 403 if the user tries to access a different tenant.
    """
    if user.role == UserRole.SUPER_ADMIN:
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
        return tenant

    # Non-super-admin: must belong to this exact tenant
    if user.tenant_id != tenant_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Access denied — you do not have permission to view this business"
        )

    result = await db.execute(
        select(Tenant)
        .where(Tenant.id == tenant_id)
        .where(Tenant.is_active == True)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found or inactive")
    if tenant.is_suspended:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been suspended. Contact support.")
    return tenant


# ── Auto tenant resolver (inject from JWT) ────────────────

class ResolveTenant:
    """
    Dependency that resolves the current tenant from the JWT automatically.
    - Staff / business_owner: gets their own tenant
    - Super admin: must pass ?tenant_id= query param to act on a specific tenant
    """
    async def __call__(
        self,
        request: Request,
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> Tenant:
        if user.role == UserRole.SUPER_ADMIN:
            tid = request.query_params.get("tenant_id")
            if not tid:
                raise HTTPException(400, "Super admin must specify ?tenant_id= query parameter")
            return await require_tenant_access(tid, user, db)

        if not user.tenant_id:
            raise HTTPException(400, "User has no tenant assigned — contact your administrator")
        return await require_tenant_access(user.tenant_id, user, db)


resolve_tenant = ResolveTenant()


# ── Password helpers ──────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── Permission matrix reference ───────────────────────────
#
#  Action                              super_admin  business_owner  staff
#  ──────────────────────────────────────────────────────────────────────
#  List all tenants                        ✅            ✗            ✗
#  Create / suspend tenant                 ✅            ✗            ✗
#  View any tenant's dashboard             ✅            ✗            ✗
#  View own tenant dashboard               ✅           ✅           ✅
#  Edit own tenant config                  ✅           ✅            ✗
#  Invite / remove team members            ✅           ✅            ✗
#  View call logs + transcripts            ✅           ✅           ✅
#  View appointments                       ✅           ✅           ✅
#  Cancel / reschedule appointment         ✅           ✅            ✗
#  Edit notification templates             ✅           ✅            ✗
#  View API keys / credentials             ✅           ✅            ✗
#  Billing / plan management               ✅            ✗            ✗
#  View platform-wide audit log            ✅            ✗            ✗
