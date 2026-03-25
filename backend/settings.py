"""
ReceptAI Settings
All values come from environment variables.
Railway injects these automatically from the Variables tab.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # ── App ────────────────────────────────────────────────
    business_type: str = "dental"          # dental | spa | roofing | bakery | generic
    base_url: str = "http://localhost:8000"
    secret_key: str = "change-this-to-a-long-random-string-in-production"
    debug: bool = False

    # ── Twilio ─────────────────────────────────────────────
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    transfer_phone_number: str = ""        # Human staff number for escalations

    # ── Anthropic ──────────────────────────────────────────
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"

    # ── Calendly ───────────────────────────────────────────
    calendly_api_token: str = ""
    calendly_user_uri: str = ""
    calendly_webhook_signing_key: str = ""

    # ── SendGrid ───────────────────────────────────────────
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = "receptionist@yourbusiness.com"
    sendgrid_from_name: str = "AI Receptionist"

    # ── Database ───────────────────────────────────────────
    # Railway PostgreSQL plugin injects DATABASE_URL automatically
    # MUST use postgresql+asyncpg:// prefix (not plain postgresql://)
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/receptai"

    class Config:
        env_file = ".env"
        extra = "ignore"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
