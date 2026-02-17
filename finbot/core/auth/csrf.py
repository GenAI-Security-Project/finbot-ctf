"""CSRF Protection Middleware for FinBot CTF Platform"""

import hmac
import logging
from typing import Callable

from fastapi import HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from finbot.config import settings
from finbot.core.auth.session import SessionContext

logger = logging.getLogger(__name__)



# Function-based CSRF protection middleware for FastAPI
from fastapi import FastAPI

PROTECTED_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
EXEMPT_PATHS = {"/api/health", "/api/status", "/static/", "/favicon.ico", "/auth/"}

def add_csrf_protection_middleware(app: FastAPI):
    @app.middleware("http")
    async def csrf_protection_middleware(request: Request, call_next):
        # Skip CSRF for disabled protection
        if not settings.ENABLE_CSRF_PROTECTION:
            return await call_next(request)
        
        # Skip WebSocket upgrade requests
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)
        
        # Skip for safe methods (GET, HEAD, OPTIONS)
        if request.method not in PROTECTED_METHODS:
            return await call_next(request)
        
        # Skip for exempt paths (static files, health checks, auth endpoints)
        if _is_exempt_path(request.url.path):
            return await call_next(request)
        
        # Debug logging for protected requests
        logger.debug(
            f"CSRF check: {request.method} {request.url.path}, "
            f"session_cookie={'finbot_session' in request.cookies}"
        )
        
        # Validate CSRF token for protected requests
        try:
            await _validate_csrf_token(request)
        except HTTPException as e:
            logger.warning(
                f"CSRF validation failed for {request.method} {request.url.path} "
                f"from {request.client.host if request.client else 'unknown'}: {e.detail}"
            )
            return _create_csrf_error_response(request, e)
        
        # CSRF validation passed, proceed with request
        return await call_next(request)

def _is_exempt_path(path: str) -> bool:
    """Check if path is exempt from CSRF protection"""
    # Exempt static files and favicon
    if path.startswith("/static/") or path.endswith((".ico", ".css", ".js", ".png", ".jpg", ".svg")):
        return True
    
    # Exempt explicitly listed paths
    return any(path.startswith(exempt) for exempt in EXEMPT_PATHS)

async def _validate_csrf_token(request: Request) -> None:
    session_context: SessionContext | None = getattr(request.state, "session_context", None)
    if not session_context:
        raise HTTPException(status_code=403, detail="No session found - CSRF validation failed")
    expected_token = session_context.csrf_token
    if not expected_token:
        raise HTTPException(status_code=403, detail="No CSRF token in session")
    request_token = await _extract_csrf_token(request)
    if not request_token:
        raise HTTPException(status_code=403, detail="CSRF token missing from request")
    if not _compare_tokens(expected_token, request_token):
        raise HTTPException(status_code=403, detail="CSRF token mismatch")
    logger.debug("CSRF validation successful for %s %s", request.method, request.url.path)

async def _extract_csrf_token(request: Request) -> str | None:
    token = request.headers.get(settings.CSRF_HEADER_NAME)
    if token:
        return token
    content_type = request.headers.get("content-type", "").lower()
    if (
        "application/x-www-form-urlencoded" in content_type
        or "multipart/form-data" in content_type
    ):
        try:
            form = await request.form()
            # Store form data in request.state so route handlers can access it
            request.state.form_data = form
            token = form.get(settings.CSRF_TOKEN_NAME)
            if token:
                return token
        except Exception as e:
            logger.warning(f"CSRF: Failed to parse form data: {e}")
    return None

def _compare_tokens(expected: str, actual: str) -> bool:
    return hmac.compare_digest(expected, actual)

def _create_csrf_error_response(request: Request, exc: HTTPException) -> Response:
    if _is_api_request(request):
        return JSONResponse(
            content={
                "error": {
                    "code": 403,
                    "message": "CSRF token validation failed",
                    "type": "csrf_error",
                    "details": exc.detail,
                }
            },
            status_code=403,
        )
    else:
        try:
            with open(
                "finbot/static/pages/error/403_csrf.html", "r", encoding="utf-8"
            ) as f:
                content = f.read()
            return HTMLResponse(content=content, status_code=403)
        except FileNotFoundError:
            return HTMLResponse(
                content="<h1>403 Forbidden</h1><p>Security validation failed. Please refresh the page and try again.</p>",
                status_code=403,
            )

def _is_api_request(request: Request) -> bool:
    """Determine if the request is for an API endpoint"""
    return request.url.path.startswith("/api/")


def get_csrf_token(request: Request) -> str:
    """Helper function to get CSRF token for templates"""
    session_context: SessionContext | None = getattr(
        request.state, "session_context", None
    )
    if session_context and session_context.csrf_token:
        return session_context.csrf_token
    return ""


def csrf_token_field(request: Request) -> str:
    """Generate HTML hidden field with CSRF token"""
    token = get_csrf_token(request)
    if token:
        return (
            f'<input type="hidden" name="{settings.CSRF_TOKEN_NAME}" value="{token}">'
        )
    return ""


def csrf_token_meta(request: Request) -> str:
    """Generate HTML meta tag with CSRF token"""
    token = get_csrf_token(request)
    if token:
        return f'<meta name="csrf-token" content="{token}">'
    return ""
