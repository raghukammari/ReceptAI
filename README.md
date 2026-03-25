# ReceptAI — AI Receptionist Platform

**Multi-tenant SaaS · Twilio Voice + SMS · Claude AI · Calendly · SendGrid**
Built by Adroit Associates LLC

---

## What It Does

ReceptAI answers inbound phone calls for small businesses using AI.
When a customer calls, the AI receptionist:
- Greets them by business name and persona
- Detects their intent (book / reschedule / cancel / info / transfer)
- Checks real availability via Calendly
- Books, reschedules, or cancels the appointment
- Sends SMS + email confirmations automatically
- Fires 24h and 1h reminders before every appointment
- Transfers to a human staff member when needed

Supports: Dental · Spa/Wellness · Roofing/Home Services · Bakery · Any SMB

---

## Architecture

```
Caller (PSTN)
     │
     ▼
Twilio Voice ──────────── STT/TTS
     │
     ▼
FastAPI Backend (Railway)
     │
     ├── Claude AI (intent detection + conversation)
     ├── Calendly API (availability + booking)
     ├── SendGrid (email confirmations + reminders)
     ├── Twilio SMS (text reminders)
     └── PostgreSQL (call logs + appointments + tenants)
```

---

## Project Structure

```
ReceptAI/
├── backend/
│   ├── __init__.py
│   ├── main.py               # FastAPI app entry + router mount
│   ├── config.py             # Env var settings (pydantic-settings)
│   ├── auth_service.py       # JWT auth + role guards + tenant isolation
│   ├── models_tenant.py      # All DB models (multi-tenant)
│   ├── requirements.txt
│   ├── config/
│   │   ├── __init__.py
│   │   └── verticals.py      # Dental/Spa/Roofing/Bakery/Generic configs
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── calls.py          # Twilio webhook handler + TwiML
│   │   ├── dashboard.py      # Stats + call log + appointments API
│   │   └── admin.py          # Super admin CRUD endpoints
│   └── services/
│       ├── __init__.py
│       ├── database.py       # Async SQLAlchemy engine + session
│       ├── claude_engine.py  # Claude conversation + tool calling
│       ├── calendly_service.py  # Calendly v2 API
│       ├── notifications.py  # Twilio SMS + SendGrid email
│       ├── scheduler.py      # APScheduler — 24h/1h reminders
│       └── tool_executor.py  # Claude tool → real action bridge
├── frontend/
│   └── receptai-multitenant-portal.html   # Admin dashboard UI
├── verify_env.py             # Pre-deploy environment checker
├── .env.example              # Template — copy to .env
├── .gitignore
├── Procfile                  # Railway start command
├── railway.toml              # Railway deployment config
└── README.md
```

---

## User Roles

| Role | What They Can Do |
|---|---|
| **Super Admin** (Adroit) | Create/suspend tenants, manage all users, view audit log, access any tenant dashboard |
| **Business Owner** | Full access to their own business — config, team, AI settings, integrations, appointments |
| **Staff** | Read-only — view call logs, transcripts, appointments |

---

## Local Development

### 1. Clone and set up

```bash
git clone https://github.com/YOUR_USERNAME/ReceptAI.git
cd ReceptAI

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Open .env and fill in all values
```

### 3. Verify configuration

```bash
python verify_env.py
```

This checks every env var and tests each API connection live.
Fix any failures before continuing.

### 4. Run the server

```bash
uvicorn backend.main:app --reload --port 8000
```

### 5. Expose to Twilio (required for call testing)

```bash
# Install ngrok: https://ngrok.com
ngrok http 8000

# Copy the HTTPS URL e.g. https://abc123.ngrok.io
# Set BASE_URL=https://abc123.ngrok.io in .env
# Set Twilio webhook: https://abc123.ngrok.io/calls/incoming
```

### 6. Open the dashboard

```
http://localhost:8000/
```

---

## Deploy to Railway

### Step 1 — Push to GitHub

```bash
git add .
git commit -m "Initial ReceptAI deploy"
git push origin main
```

### Step 2 — Create Railway project

1. Go to [railway.app](https://railway.app) → New Project
2. → Deploy from GitHub → select `ReceptAI`
3. Railway detects Python via Nixpacks automatically

### Step 3 — Add PostgreSQL

1. Railway dashboard → New → Database → PostgreSQL
2. Click the PostgreSQL plugin → Variables tab
3. Copy `DATABASE_URL`
4. **Important:** Change `postgresql://` to `postgresql+asyncpg://`

### Step 4 — Set environment variables

In Railway → your service → Variables tab, add every variable from `.env.example`:

```
BUSINESS_TYPE          = dental
BASE_URL               = https://YOUR-APP.up.railway.app   ← set after deploy
SECRET_KEY             = (generate: python -c "import secrets; print(secrets.token_hex(32))")
TWILIO_ACCOUNT_SID     = ACxxxxxxxx
TWILIO_AUTH_TOKEN      = xxxxxxxx
TWILIO_PHONE_NUMBER    = +16145550191
TRANSFER_PHONE_NUMBER  = +16145550000
ANTHROPIC_API_KEY      = sk-ant-xxxxxxxx
CLAUDE_MODEL           = claude-sonnet-4-20250514
CALENDLY_API_TOKEN     = eyJhbGci...
CALENDLY_USER_URI      = https://api.calendly.com/users/xxxx
SENDGRID_API_KEY       = SG.xxxxxxxx
SENDGRID_FROM_EMAIL    = receptionist@yourbusiness.com
SENDGRID_FROM_NAME     = Your Business Name
DATABASE_URL           = postgresql+asyncpg://...   ← from PostgreSQL plugin
```

### Step 5 — Get your Railway URL

Railway → Settings → Domains → copy your URL
Set `BASE_URL` to this URL in Variables.

### Step 6 — Configure Twilio webhooks

In [Twilio Console](https://console.twilio.com) → Phone Numbers → your number:

| Field | Value |
|---|---|
| Voice Webhook (HTTP POST) | `https://YOUR-APP.up.railway.app/calls/incoming` |
| Status Callback (HTTP POST) | `https://YOUR-APP.up.railway.app/calls/status` |

### Step 7 — Register Calendly webhook

In Calendly → Integrations → Webhooks → Create:
- URL: `https://YOUR-APP.up.railway.app/webhooks/calendly`
- Events: `invitee.created`, `invitee.canceled`
- Copy the signing key → set as `CALENDLY_WEBHOOK_SIGNING_KEY`

### Step 8 — Deploy

Every `git push origin main` triggers an automatic Railway redeploy.

---

## Adding a New Business Client

```bash
# Via API (requires super admin JWT token)
POST /admin/tenants
Authorization: Bearer YOUR_SUPER_ADMIN_TOKEN

{
  "name": "Serenity Spa & Wellness",
  "slug": "serenity-spa",
  "vertical": "spa",
  "owner_email": "owner@serenityspa.com",
  "owner_name": "Maya Rodriguez",
  "owner_password": "TempPass123!",
  "twilio_phone_number": "+16145550292",
  "plan": "starter",
  "call_limit_monthly": 500
}
```

This creates the tenant record and provisions the business owner account in one call.
The owner can then log in and invite their own staff members.

---

## API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | None | Health check (Railway uses this) |
| POST | `/calls/incoming` | Twilio signature | Inbound call webhook |
| POST | `/calls/respond` | Twilio signature | Conversation turn webhook |
| POST | `/calls/status` | Twilio signature | Call status callback |
| GET | `/dashboard/stats` | JWT | Tenant call stats |
| GET | `/dashboard/calls` | JWT | Call log list |
| GET | `/dashboard/calls/{id}/transcript` | JWT | Call transcript |
| GET | `/dashboard/appointments` | JWT | Upcoming appointments |
| GET | `/admin/stats` | Super admin JWT | Platform-wide stats |
| GET | `/admin/tenants` | Super admin JWT | List all tenants |
| POST | `/admin/tenants` | Super admin JWT | Create tenant + owner |
| PATCH | `/admin/tenants/{id}` | Super admin JWT | Update tenant |
| POST | `/admin/tenants/{id}/suspend` | Super admin JWT | Suspend tenant |
| GET | `/admin/audit-logs` | Super admin JWT | Full audit trail |
| POST | `/admin/users/invite` | Super admin JWT | Invite user |
| GET | `/api/docs` | None (dev only) | Swagger UI |

---

## Business Verticals

| Key | Business Type | AI Name | Voice |
|---|---|---|---|
| `dental` | Dental office | Aria | Polly.Joanna |
| `spa` | Spa / Wellness | Luna | Polly.Salli |
| `roofing` | Roofing / Home services | Max | Polly.Matthew |
| `bakery` | Bakery / Food | Rosie | Polly.Kendra |
| `generic` | Any SMB | Alex | Polly.Joanna |

Each vertical has its own: greeting, services list, intake questions, FAQ, SMS templates, email templates, escalation triggers, and business hours.

---

## Support

Built and maintained by **Adroit Associates LLC**
Columbus, Ohio · adroitassociates.com
