"""Authentication routes for magic link sign-in"""

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from finbot.config import settings
from finbot.core.auth.session import session_manager
from finbot.core.data.database import SessionLocal
from finbot.core.data.models import MagicLinkToken
from finbot.core.email import get_email_service
from finbot.core.templates import TemplateResponse

template_response = TemplateResponse("finbot/apps/finbot/templates")

router = APIRouter(prefix="/auth", tags=["auth"])


def _is_authenticated(request: Request) -> bool:
    """Check if the current request has a verified (non-temporary) session."""
    ctx = getattr(request.state, "session_context", None)
    return bool(ctx and ctx.email and not ctx.is_temporary)


@router.post("/magic-link")
async def request_magic_link(
    request: Request,
    email: str = Form(...),
):
    """Generate and send a magic link to the user's email"""
    if _is_authenticated(request):
        return RedirectResponse(url="/portals", status_code=303)

    email = email.lower().strip()
    db = SessionLocal()
    try:
        # Get current session to link with token
        session_context = getattr(request.state, "session_context", None)
        session_id = session_context.session_id if session_context else None

        # Generate secure token
        token = secrets.token_urlsafe(32)

        # Create magic link token
        magic_token = MagicLinkToken(
            token=token,
            email=email,
            session_id=session_id,
            expires_at=datetime.now(UTC)
            + timedelta(minutes=settings.MAGIC_LINK_EXPIRY_MINUTES),
            ip_address=request.client.host if request.client else None,
        )
        db.add(magic_token)
        db.commit()

        # Build magic link URL
        magic_link = f"{settings.MAGIC_LINK_BASE_URL}/auth/verify?token={token}"

        # Send email
        email_service = get_email_service()
        await email_service.send_magic_link(email, magic_link)

        # Redirect to check-email page
        return RedirectResponse(
            url=f"/auth/check-email?email={email}",
            status_code=303,  # POST-redirect-GET
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        db.rollback()
        return template_response(
            request,
            "auth-error.html",
            {
                "error": "Failed to send magic link",
                "message": f"An error occurred: {e}. Please try again.",
            },
        )
    finally:
        db.close()


def _token_error(magic_token: MagicLinkToken | None) -> dict | None:
    """Return error page context for an unusable token, or None if it can be used."""
    if not magic_token:
        return {
            "error": "Invalid link",
            "message": "This sign-in link is invalid or has already been used.",
        }
    if not magic_token.is_valid():
        return {
            "error": "Link expired",
            "message": "This sign-in link has expired. Please request a new one.",
        }
    return None


def _release_token(db, token: str) -> None:
    """Make a claimed token usable again after a sign-in that did not complete."""
    db.query(MagicLinkToken).filter(MagicLinkToken.token == token).update(
        {MagicLinkToken.used_at: None}, synchronize_session=False
    )
    db.commit()


@router.get("/verify")
async def confirm_magic_link(request: Request, token: str):
    """Show a confirmation page for a magic link.

    Opening the link must not use up the token or sign anyone in. Mail scanners,
    click trackers and link previews fetch links automatically, so sign-in happens
    only when the confirmation form is submitted.
    """
    if _is_authenticated(request):
        return RedirectResponse(url="/portals", status_code=303)

    db = SessionLocal()
    try:
        magic_token = (
            db.query(MagicLinkToken).filter(MagicLinkToken.token == token).first()
        )
        error = _token_error(magic_token)
        if error:
            return template_response(request, "auth-error.html", error)

        return template_response(request, "auth-confirm.html", {"token": token})
    finally:
        db.close()


@router.post("/verify")
async def verify_magic_link(request: Request, token: str = Form(...)):
    """Verify magic link token and upgrade session to permanent"""
    if _is_authenticated(request):
        return RedirectResponse(url="/portals", status_code=303)

    db = SessionLocal()
    claimed = False
    try:
        # Find token
        magic_token = (
            db.query(MagicLinkToken).filter(MagicLinkToken.token == token).first()
        )
        error = _token_error(magic_token)
        if error:
            return template_response(request, "auth-error.html", error)

        # Claim the token with a conditional update, so two submissions of the
        # same link cannot both sign in. The claim is released if sign-in fails.
        claimed = bool(
            db.query(MagicLinkToken)
            .filter(MagicLinkToken.token == token, MagicLinkToken.used_at.is_(None))
            .update(
                {MagicLinkToken.used_at: datetime.now(UTC)},
                synchronize_session=False,
            )
        )
        db.commit()
        if not claimed:
            return template_response(request, "auth-error.html", _token_error(None))

        # Determine which session to upgrade:
        # 1. Prefer the current browser's session (the one clicking the link)
        # 2. Fall back to the original session stored in the token
        # 3. If neither exists, create a new permanent session
        #
        # We must NOT upgrade the stored session when a different browser clicks
        # the link, otherwise both browsers share the same session ID and both
        # become authenticated.

        current_session = getattr(request.state, "session_context", None)
        session_id_to_upgrade = (
            current_session.session_id if current_session else magic_token.session_id
        )

        if session_id_to_upgrade:
            # Upgrade the session (original or current)
            new_session, _ = session_manager.upgrade_to_permanent(
                session_id=session_id_to_upgrade,
                email=magic_token.email,
                user_agent=request.headers.get("user-agent"),
                ip_address=request.client.host if request.client else None,
                accept_language=request.headers.get("accept-language"),
                accept_encoding=request.headers.get("accept-encoding"),
            )

            # If the original session was invalid/expired, create a new one
            if not new_session:
                new_session = session_manager.create_session(
                    email=magic_token.email,
                    user_agent=request.headers.get("user-agent"),
                    ip_address=request.client.host if request.client else None,
                    accept_language=request.headers.get("accept-language"),
                    accept_encoding=request.headers.get("accept-encoding"),
                )
        else:
            # No session to upgrade, create new permanent session
            new_session = session_manager.create_session(
                email=magic_token.email,
                user_agent=request.headers.get("user-agent"),
                ip_address=request.client.host if request.client else None,
                accept_language=request.headers.get("accept-language"),
                accept_encoding=request.headers.get("accept-encoding"),
            )
        if not new_session:
            _release_token(db, token)
            claimed = False
            return template_response(
                request,
                "auth-error.html",
                {
                    "error": "Session error",
                    "message": "Failed to create session. Please try again.",
                },
            )

        # Redirect to portals with new session cookie
        response = RedirectResponse(url="/portals", status_code=303)
        response.set_cookie(
            key=settings.SESSION_COOKIE_NAME,
            value=new_session.session_id,
            httponly=settings.SESSION_COOKIE_HTTP_ONLY,
            secure=settings.SESSION_COOKIE_SECURE,
            samesite=settings.SESSION_COOKIE_SAMESITE,
            max_age=settings.PERM_SESSION_TIMEOUT,
            path="/",
        )
        return response

    except Exception as e:  # pylint: disable=broad-exception-caught
        db.rollback()
        if claimed:
            try:
                _release_token(db, token)
            except Exception:  # pylint: disable=broad-exception-caught
                # Keep the error page below rather than raising a second error.
                db.rollback()
        return template_response(
            request,
            "auth-error.html",
            {
                "error": "Verification failed",
                "message": f"An error occurred: {e}. Please try again.",
            },
        )
    finally:
        db.close()


@router.get("/logout")
async def logout(request: Request):
    """Sign out - delete session and create new temporary session"""
    session_context = getattr(request.state, "session_context", None)

    # Delete current session
    if session_context:
        session_manager.delete_session(session_context.session_id)

    # Create new temporary session
    new_session = session_manager.create_session(
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
        accept_language=request.headers.get("accept-language"),
        accept_encoding=request.headers.get("accept-encoding"),
    )

    # Redirect to portals with new session cookie
    response = RedirectResponse(url="/portals", status_code=303)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=new_session.session_id,
        httponly=settings.SESSION_COOKIE_HTTP_ONLY,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        max_age=settings.TEMP_SESSION_TIMEOUT,
        path="/",
    )
    return response


@router.get("/check-email", response_class=HTMLResponse)
async def check_email(request: Request, email: str = ""):
    """Show 'check your email' confirmation page"""
    if _is_authenticated(request):
        return RedirectResponse(url="/portals", status_code=303)

    return template_response(
        request,
        "check-email.html",
        {"email": email},
    )
