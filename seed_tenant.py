"""
Seed script - creates the first tenant and super admin user directly in DB
Run once after first Railway deploy:
    python seed_tenant.py
"""

import asyncio
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

# Fix DATABASE_URL prefix for asyncpg
db_url = os.getenv("DATABASE_URL", "")
db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
db_url = db_url.replace("postgres://", "postgresql+asyncpg://")

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from datetime import datetime
import bcrypt

engine = create_async_engine(db_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def seed():
    async with AsyncSessionLocal() as db:

        # 1. Create tenant
        tenant_id = str(uuid.uuid4())
        await db.execute(sa.text("""
            INSERT INTO tenants (
                id, name, slug, vertical,
                is_active, is_suspended,
                twilio_phone_number,
                primary_color, logo_emoji,
                plan, calls_this_month, call_limit_monthly,
                config, created_at
            ) VALUES (
                :id, :name, :slug, :vertical,
                true, false,
                :phone,
                :color, :emoji,
                :plan, 0, 500,
                '{}', :now
            )
            ON CONFLICT (slug) DO UPDATE SET
                twilio_phone_number = EXCLUDED.twilio_phone_number,
                is_active = true
        """), {
            "id":       tenant_id,
            "name":     "Worthington Family Dental",
            "slug":     "worthington-dental",
            "vertical": "dental",
            "phone":    "+17407222770",
            "color":    "#1a6b8a",
            "emoji":    "tooth",
            "plan":     "starter",
            "now":      datetime.utcnow(),
        })
        print("PASS Tenant created: Worthington Family Dental")
        print("     Tenant ID: " + tenant_id)

        # 2. Create super admin (Raghu)
        admin_id = str(uuid.uuid4())
        pw_hash  = bcrypt.hashpw("AdroitAdmin2026!".encode(), bcrypt.gensalt()).decode()
        await db.execute(sa.text("""
            INSERT INTO users (
                id, email, name, password_hash,
                role, tenant_id, is_active, created_at
            ) VALUES (
                :id, :email, :name, :hash,
                'super_admin', NULL, true, :now
            )
            ON CONFLICT (email) DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                is_active = true
        """), {
            "id":    admin_id,
            "email": "raghu@adroitassociates.com",
            "name":  "Raghu K.",
            "hash":  pw_hash,
            "now":   datetime.utcnow(),
        })
        print("PASS Super admin created: raghu@adroitassociates.com")

        # 3. Create business owner
        owner_id   = str(uuid.uuid4())
        owner_hash = bcrypt.hashpw("Dental2026!".encode(), bcrypt.gensalt()).decode()
        await db.execute(sa.text("""
            INSERT INTO users (
                id, email, name, password_hash,
                role, tenant_id, is_active, created_at
            ) VALUES (
                :id, :email, :name, :hash,
                'business_owner', :tenant_id, true, :now
            )
            ON CONFLICT (email) DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                tenant_id = EXCLUDED.tenant_id,
                is_active = true
        """), {
            "id":        owner_id,
            "email":     "dr.smith@worthingtondental.com",
            "name":      "Dr. Smith",
            "hash":      owner_hash,
            "tenant_id": tenant_id,
            "now":       datetime.utcnow(),
        })
        print("PASS Business owner created: dr.smith@worthingtondental.com")

        await db.commit()

        print("")
        print("=== Seed Complete ===")
        print("")
        print("Tenant:        Worthington Family Dental")
        print("Tenant ID:     " + tenant_id)
        print("Twilio number: +17407222770")
        print("")
        print("Login credentials:")
        print("  Super Admin:  raghu@adroitassociates.com / AdroitAdmin2026!")
        print("  Dental Owner: dr.smith@worthingtondental.com / Dental2026!")
        print("")
        print("Dashboard: https://receptai-prod.up.railway.app/")


if __name__ == "__main__":
    asyncio.run(seed())
