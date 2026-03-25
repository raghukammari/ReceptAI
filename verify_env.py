"""
ReceptAI — Environment Variable Verifier
Run this BEFORE deploying to Railway to catch missing config early.

Usage:
    python verify_env.py

It checks every required variable, tests each API connection,
and prints a pass/fail summary with fix instructions.
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

load_dotenv()

# ── Color helpers (no dependencies) ───────────────────────

def green(s):  return f"\033[92m{s}\033[0m"
def red(s):    return f"\033[91m{s}\033[0m"
def yellow(s): return f"\033[93m{s}\033[0m"
def bold(s):   return f"\033[1m{s}\033[0m"
def dim(s):    return f"\033[2m{s}\033[0m"

PASS = green("✓ PASS")
FAIL = red("✗ FAIL")
WARN = yellow("⚠ WARN")


# ── Required variables ─────────────────────────────────────

REQUIRED = {
    "Core": [
        ("SECRET_KEY",          "Long random string for JWT signing",         True),
        ("BASE_URL",            "Public URL e.g. https://app.up.railway.app", True),
        ("BUSINESS_TYPE",       "dental | spa | roofing | bakery | generic",  True),
    ],
    "Twilio": [
        ("TWILIO_ACCOUNT_SID",  "Starts with AC",                             True),
        ("TWILIO_AUTH_TOKEN",   "32-char hex string",                         True),
        ("TWILIO_PHONE_NUMBER", "E.164 format e.g. +16145550191",             True),
        ("TRANSFER_PHONE_NUMBER","Staff number for escalations",              False),
    ],
    "Anthropic": [
        ("ANTHROPIC_API_KEY",   "Starts with sk-ant-",                        True),
        ("CLAUDE_MODEL",        "claude-sonnet-4-20250514",                   False),
    ],
    "Calendly": [
        ("CALENDLY_API_TOKEN",  "Personal Access Token from Calendly",        True),
        ("CALENDLY_USER_URI",   "https://api.calendly.com/users/xxxx",        True),
        ("CALENDLY_WEBHOOK_SIGNING_KEY", "From Calendly webhook settings",    False),
    ],
    "SendGrid": [
        ("SENDGRID_API_KEY",    "Starts with SG.",                            True),
        ("SENDGRID_FROM_EMAIL", "Verified sender email",                      True),
        ("SENDGRID_FROM_NAME",  "Display name for emails",                    False),
    ],
    "Database": [
        ("DATABASE_URL",        "Must start with postgresql+asyncpg://",       True),
    ],
}

# ── Validation rules ───────────────────────────────────────

VALIDATORS = {
    "TWILIO_ACCOUNT_SID":  lambda v: v.startswith("AC"),
    "ANTHROPIC_API_KEY":   lambda v: v.startswith("sk-ant-"),
    "SENDGRID_API_KEY":    lambda v: v.startswith("SG."),
    "CALENDLY_USER_URI":   lambda v: "api.calendly.com" in v,
    "DATABASE_URL":        lambda v: v.startswith("postgresql+asyncpg://"),
    "BASE_URL":            lambda v: v.startswith("http"),
    "BUSINESS_TYPE":       lambda v: v in ("dental", "spa", "roofing", "bakery", "generic"),
    "TWILIO_PHONE_NUMBER": lambda v: v.startswith("+"),
    "SECRET_KEY":          lambda v: len(v) >= 20,
}

HINTS = {
    "DATABASE_URL": (
        "Railway gives you 'postgresql://...' — you MUST change it to "
        "'postgresql+asyncpg://...' (just insert '+asyncpg' after 'postgresql')"
    ),
    "SECRET_KEY": "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\"",
    "BASE_URL":   "Set AFTER Railway assigns your domain. Find it in Railway → Settings → Domains",
    "BUSINESS_TYPE": "Must be one of: dental, spa, roofing, bakery, generic",
    "TWILIO_ACCOUNT_SID": "Find in Twilio Console → Account Info (starts with AC)",
    "ANTHROPIC_API_KEY": "Find in console.anthropic.com → API Keys",
    "SENDGRID_API_KEY": "Find in SendGrid → Settings → API Keys (starts with SG.)",
    "CALENDLY_API_TOKEN": "Calendly → Integrations → API & Webhooks → Personal Access Tokens",
    "CALENDLY_USER_URI": "Run: curl -H 'Authorization: Bearer YOUR_TOKEN' https://api.calendly.com/users/me",
}


# ── Live connection tests ──────────────────────────────────

async def test_anthropic():
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        r = await client.messages.create(
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=10,
            messages=[{"role": "user", "content": "say ok"}]
        )
        return True, f"Model: {r.model}"
    except Exception as e:
        return False, str(e)


async def test_twilio():
    try:
        from twilio.rest import Client
        client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        account = client.api.accounts(os.getenv("TWILIO_ACCOUNT_SID")).fetch()
        return True, f"Account: {account.friendly_name}"
    except Exception as e:
        return False, str(e)


async def test_calendly():
    try:
        import httpx
        r = await httpx.AsyncClient().get(
            "https://api.calendly.com/users/me",
            headers={"Authorization": f"Bearer {os.getenv('CALENDLY_API_TOKEN')}"},
            timeout=10,
        )
        if r.status_code == 200:
            name = r.json().get("resource", {}).get("name", "unknown")
            return True, f"User: {name}"
        return False, f"HTTP {r.status_code}: {r.text[:100]}"
    except Exception as e:
        return False, str(e)


async def test_sendgrid():
    try:
        import httpx
        r = await httpx.AsyncClient().get(
            "https://api.sendgrid.com/v3/user/profile",
            headers={"Authorization": f"Bearer {os.getenv('SENDGRID_API_KEY')}"},
            timeout=10,
        )
        if r.status_code == 200:
            username = r.json().get("username", "unknown")
            return True, f"Account: {username}"
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)


async def test_database():
    try:
        import sqlalchemy.ext.asyncio as sa
        engine = sa.create_async_engine(os.getenv("DATABASE_URL", ""), echo=False)
        async with engine.connect() as conn:
            await conn.execute(sa.text("SELECT 1"))
        await engine.dispose()
        return True, "Connection successful"
    except Exception as e:
        return False, str(e)


# ── Main runner ────────────────────────────────────────────

def check_env_vars():
    print(bold("\n━━━ Environment Variables ━━━\n"))
    all_pass = True
    missing_required = []

    for section, vars in REQUIRED.items():
        print(bold(f"  {section}"))
        for var_name, description, required in vars:
            value = os.getenv(var_name, "")

            if not value:
                if required:
                    print(f"    {FAIL}  {var_name}")
                    print(dim(f"           → {description}"))
                    if var_name in HINTS:
                        print(yellow(f"           💡 {HINTS[var_name]}"))
                    missing_required.append(var_name)
                    all_pass = False
                else:
                    print(f"    {WARN}  {var_name} {dim('(optional — using default)')}")
                continue

            # Validate format
            validator = VALIDATORS.get(var_name)
            if validator and not validator(value):
                display = value[:6] + "..." if len(value) > 6 else value
                print(f"    {FAIL}  {var_name} = {display}")
                print(red(f"           → Value format is wrong"))
                if var_name in HINTS:
                    print(yellow(f"           💡 {HINTS[var_name]}"))
                all_pass = False
            else:
                # Mask sensitive values
                if any(k in var_name for k in ["TOKEN", "KEY", "SECRET", "PASSWORD", "AUTH"]):
                    display = value[:4] + "..." + value[-4:] if len(value) > 8 else "****"
                else:
                    display = value if len(value) <= 40 else value[:37] + "..."
                print(f"    {PASS}  {var_name} = {dim(display)}")

        print()
    return all_pass, missing_required


async def check_connections():
    print(bold("━━━ Live API Connections ━━━\n"))

    tests = [
        ("Anthropic (Claude)",  test_anthropic,  "ANTHROPIC_API_KEY"),
        ("Twilio",              test_twilio,      "TWILIO_ACCOUNT_SID"),
        ("Calendly",            test_calendly,    "CALENDLY_API_TOKEN"),
        ("SendGrid",            test_sendgrid,    "SENDGRID_API_KEY"),
        ("PostgreSQL Database", test_database,    "DATABASE_URL"),
    ]

    results = []
    for name, test_fn, required_var in tests:
        if not os.getenv(required_var):
            print(f"  {WARN}  {name} {dim('— skipped (env var not set)')}")
            results.append((name, None, "skipped"))
            continue

        print(f"  ⏳  {name} ...", end="\r")
        try:
            ok, detail = await test_fn()
            if ok:
                print(f"  {PASS}  {name} {dim(f'— {detail}')}")
                results.append((name, True, detail))
            else:
                print(f"  {FAIL}  {name}")
                print(red(f"         → {detail}"))
                results.append((name, False, detail))
        except Exception as e:
            print(f"  {FAIL}  {name}")
            print(red(f"         → {e}"))
            results.append((name, False, str(e)))

    print()
    return results


def print_summary(env_ok, missing, conn_results):
    print(bold("━━━ Summary ━━━\n"))

    conn_failures = [r for r in conn_results if r[1] is False]
    conn_skipped  = [r for r in conn_results if r[1] is None]

    if env_ok and not conn_failures:
        print(green("  🎉 All checks passed! You're ready to deploy to Railway.\n"))
        print("  Next steps:")
        print("  1. git add . && git commit -m 'Ready for Railway deploy'")
        print("  2. git push origin main")
        print("  3. In Railway → set all env vars from .env (excluding DATABASE_URL — Railway sets that)")
        print("  4. Railway will auto-deploy on push")
        print("  5. Point your Twilio webhook to: YOUR_RAILWAY_URL/calls/incoming\n")
    else:
        print(red("  ❌ Issues found — fix these before deploying:\n"))
        if missing:
            print(red("  Missing required env vars:"))
            for v in missing:
                print(red(f"    • {v}"))
                if v in HINTS:
                    print(yellow(f"      💡 {HINTS[v]}"))
            print()
        if conn_failures:
            print(red("  Failed API connections:"))
            for name, _, detail in conn_failures:
                print(red(f"    • {name}: {detail}"))
            print()
        if conn_skipped:
            print(yellow("  Skipped (env var not set):"))
            for name, _, _ in conn_skipped:
                print(yellow(f"    • {name}"))
            print()


async def main():
    print(bold("\n" + "="*50))
    print(bold("  ReceptAI — Pre-Deploy Verification"))
    print(bold("  Built by Adroit Associates LLC"))
    print(bold("="*50))

    env_ok, missing = check_env_vars()
    conn_results    = await check_connections()
    print_summary(env_ok, missing, conn_results)

    # Exit code for CI/CD
    conn_failures = [r for r in conn_results if r[1] is False]
    if not env_ok or conn_failures:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
