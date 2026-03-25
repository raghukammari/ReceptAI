"""
ReceptAI — AI Receptionist Platform
FastAPI Backend Entry Point
Stack: Twilio Voice/SMS · Claude AI · Calendly · SendGrid · PostgreSQL
Built by Adroit Associates LLC
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import logging
import os

from backend.services.database import init_db
from backend.routers import calls, dashboard, admin
from backend.services.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting ReceptAI platform...")
    await init_db()
    start_scheduler()
    logger.info("Database initialized · Scheduler started")
    yield
    # Shutdown
    stop_scheduler()
    logger.info("ReceptAI shut down cleanly")


app = FastAPI(
    title="ReceptAI API",
    description="Multi-tenant AI Receptionist — Twilio + Claude + Calendly",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routers ───────────────────────────────────────────
app.include_router(calls.router,     prefix="/calls",     tags=["Voice Calls"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(admin.router,     prefix="/admin",     tags=["Super Admin"])

# ── Health check (Railway uses this) ─────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "receptai", "version": "1.0.0"}

# ── Serve frontend as static ──────────────────────────────
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_path, "receptai-multitenant-portal.html"))
