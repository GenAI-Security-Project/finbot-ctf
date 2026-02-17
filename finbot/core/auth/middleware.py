"""Enhanced middleware with automatic cookie enforcement"""

import hashlib
import logging

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from finbot.config import settings
from finbot.core.auth.session import (
    SessionContext,
    session_manager,
)
from finbot.core.utils import create_fingerprint_data

logger = logging.getLogger(__name__)



# Function-based SessionMiddleware for FastAPI
from fastapi import FastAPI

def add_session_middleware(app: FastAPI):
    @app.middleware("http")
    async def session_middleware(request: Request, call_next):
        # Skip WebSocket upgrade requests
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        # Create or get session for this request
        session_context, status = await get_or_create_session_static(request)
        logger.debug(
            f"SessionMiddleware: session_id={getattr(session_context, 'session_id', None)}, "
            f"status={status}, cookies={request.cookies}"
        )
        request.state.session_context = session_context
        request.state.session_status = status

        # Process the request
        response = await call_next(request)

        # Set or update session cookie if needed
        if (
            session_context.needs_cookie_update
            or session_context.was_rotated
            or status in ["session_created", "session_rotated"]
        ):
            logger.debug(f"SessionMiddleware: Setting session cookie for session_id={session_context.session_id}")
            set_secure_session_cookie_static(response, session_context)
            if session_context.was_rotated:
                logger.info("🔄 Session rotated: %s", session_context.user_id)

        # Add security headers to response
        add_security_headers_static(response)
        return response

# Move static helpers outside the class for direct use
async def get_or_create_session_static(request: Request) -> tuple[SessionContext, str]:
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    current_ip = request.client.host if request.client else ""
    user_agent = request.headers.get("User-Agent")
    accept_language = request.headers.get("Accept-Language")
    accept_encoding = request.headers.get("Accept-Encoding")
    current_strict_fingerprint = hashlib.sha256(
        create_fingerprint_data(
            user_agent, accept_language, accept_encoding, "strict"
        ).encode()
    ).hexdigest()[:16]
    current_loose_fingerprint = hashlib.sha256(
        create_fingerprint_data(
            user_agent, accept_language, accept_encoding, "loose"
        ).encode()
    ).hexdigest()[:16]
    if session_id:
        session_context, status = session_manager.get_session_with_vendor_context(
            session_id,
            current_strict_fingerprint=current_strict_fingerprint,
            current_loose_fingerprint=current_loose_fingerprint,
            current_ip=current_ip,
        )
        # If session not found or invalid, create a new one
        if session_context is None or status in ["session_not_found", "session_hijacked"]:
            logger.info(f"Creating new session (old session status: {status})")
            session_context = session_manager.create_session(
                user_agent=user_agent,
                ip_address=current_ip,
                accept_language=accept_language,
                accept_encoding=accept_encoding,
            )
            # Load vendor context for new sessions too
            session_context = session_manager.load_vendor_context(session_context)
            status = "session_created"
    else:
        session_context = session_manager.create_session(
            user_agent=user_agent,
            ip_address=current_ip,
            accept_language=accept_language,
            accept_encoding=accept_encoding,
        )
        # Load vendor context for new sessions too
        session_context = session_manager.load_vendor_context(session_context)
        status = "session_created"
    return session_context, status

def set_secure_session_cookie_static(response: Response, session_context: SessionContext):
    # Use the appropriate timeout based on session type
    max_age = settings.TEMP_SESSION_TIMEOUT if session_context.is_temporary else settings.PERM_SESSION_TIMEOUT
    
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_context.session_id,
        max_age=max_age,
        expires=max_age,
        path="/",
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )

def add_security_headers_static(response: Response):
    """Add security headers to response"""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"


# Dependencies for FastAPI routes
async def get_session_context(request: Request) -> SessionContext:
    """FastAPI dependency to get normal session context
    - This is used for routes that don't explicitly require authentication
    - May or may not be bound to an email address (temporary vs persistent)
    """
    return request.state.session_context


async def get_authenticated_session_context(request: Request) -> SessionContext:
    """FastAPI dependency to get authenticated session context
    - Requires a non-temporary session (bound to an email address aka persistent)
    - Raises 401 if the session is temporary
    """
    session_context = request.state.session_context

    if session_context.is_temporary:
        raise HTTPException(
            status_code=401,
            detail="Persistent session required. Please bind your email.",
        )

    return session_context
