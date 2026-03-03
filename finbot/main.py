"""
FinBot Platform Main Application
- Serves all the applications for the FinBot platform.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from finbot.apps.admin.main import app as admin_app
from finbot.apps.ctf import ctf_app
from finbot.apps.vendor.main import app as vendor_app
from finbot.apps.web.auth import router as auth_router
from finbot.apps.web.routes import router as web_router
from finbot.core.auth.csrf import CSRFProtectionMiddleware
from finbot.core.auth.middleware import SessionMiddleware, get_session_context
from finbot.core.auth.session import SessionContext, session_manager
from finbot.core.messaging import event_bus
from finbot.core.data import (
    models as _models,  # noqa: F401 — register all tables with Base
)
from finbot.mcp.servers.findrive import models as _findrive_models  # noqa: F401
from finbot.mcp.servers.finstripe import models as _finstripe_models  # noqa: F401
from finbot.core.data.database import create_tables
from finbot.core.error_handlers import register_error_handlers
from finbot.core.websocket import websocket_router

# CTF
from finbot.ctf.definitions.loader import load_definitions_on_startup
from finbot.ctf.processor import start_processor_task

# Logging
from finbot.logging_config import setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""

    # 1. Ensure all database tables exist (safe no-op if they already do)
    create_tables()

    # 2. Cleanup expired sessions
    try:
        cleaned_count = session_manager.cleanup_expired_sessions()
        if cleaned_count > 0:
            print(f"🧹 Cleaned up {cleaned_count} expired sessions on startup")
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"⚠️ Session cleanup skipped: {e}")

    # 3. Load CTF definitions from YAML
    try:
        result = load_definitions_on_startup()
        print(
            f"🎯 CTF loaded: {len(result['challenges'])} challenges, "
            f"{len(result['badges'])} badges"
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"⚠️ CTF definition loading failed: {e}")

    # 4. Start CTF event processor as async task
    processor_task = None
    try:
        processor_task = start_processor_task()
        print("🚀 CTF event processor started")
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"⚠️ CTF processor start failed: {e}")

    yield  # App is running

    # Stop CTF event processor gracefully
    try:
        # pylint: disable=import-outside-toplevel
        from finbot.ctf.processor import get_processor

        processor = get_processor()
        if processor:
            processor.stop()
        if processor_task:
            processor_task.cancel()
            try:
                await processor_task
            except Exception:  # pylint: disable=broad-exception-caught
                pass  # Task cancelled
            print("🛑 CTF event processor stopped")
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"⚠️ CTF processor stop failed: {e}")


app = FastAPI(
    title="FinBot Platform",
    description="FinBot Application Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Add middleware - last in, first out order
# Execute session first, then CSRF
app.add_middleware(CSRFProtectionMiddleware)
app.add_middleware(SessionMiddleware)

# Register error handlers
register_error_handlers(app)

# Define the uploads directory path
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"

# Ensure the directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Mount Static Files
app.mount("/static", StaticFiles(directory="finbot/static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Mount all the applications for the platform
app.mount("/vendor", vendor_app)
app.mount("/admin", admin_app)
app.mount("/ctf", ctf_app)
app.include_router(websocket_router)
# Auth routes for magic link sign-in
app.include_router(auth_router)
# Web application is mounted at the root of the platform
app.include_router(web_router)


# web agreement handler
@app.get("/agreement", response_class=HTMLResponse)
async def agreement(_: Request):
    """FinBot Agreement page"""
    try:
        # (TODO) cache this to reduce disk I/O
        with open("finbot/static/pages/agreement.html", "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content, status_code=200)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail="Agreement page not found") from e


# Agreement acceptance audit log
@app.post("/api/log-agreement")
async def log_agreement(
    request: Request,
    session_context: SessionContext = Depends(get_session_context),
):
    """Log user acceptance of the CTF participation agreement for audit purposes."""
    body = await request.json()
    await event_bus.emit_business_event(
        event_type="platform.agreement_accepted",
        event_subtype="lifecycle",
        event_data={
            "user_agent": body.get("userAgent", ""),
            "referrer": body.get("referrer", ""),
        },
        session_context=session_context,
        summary=f"CTF agreement accepted by user {session_context.user_id[:8]}",
    )
    return {"success": True}


# Session health check endpoint
@app.get("/api/session/status")
async def session_status(
    session_context: SessionContext = Depends(get_session_context),
):
    """Get current session status and security information"""
    return {
        "session_id": session_context.session_id[:8] + "...",
        "user_id": session_context.user_id,
        "is_temporary": session_context.is_temporary,
        "namespace": session_context.namespace,
        "security_status": session_context.get_security_status(),
        "csrf_token": session_context.csrf_token,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
