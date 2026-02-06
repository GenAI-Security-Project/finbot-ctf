"""CTF Portal Web Routes"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from finbot.core.auth.middleware import get_session_context
from finbot.core.auth.session import SessionContext
from finbot.core.templates import TemplateResponse

# Setup templates
template_response = TemplateResponse("finbot/apps/ctf/templates")

# Create web router
router = APIRouter(tags=["ctf-web"])


@router.get("/", name="ctf_root")
async def ctf_root():
    """Redirect /ctf to /ctf/dashboard"""
    return RedirectResponse(url="/ctf/dashboard", status_code=302)


@router.get("/dashboard", response_class=HTMLResponse, name="ctf_dashboard")
async def ctf_dashboard(
    request: Request, session_context: SessionContext = Depends(get_session_context)
):
    """CTF Dashboard page"""
    return template_response(
        request,
        "pages/dashboard.html",
        {"session_context": session_context},
    )


@router.get("/challenges", response_class=HTMLResponse, name="ctf_challenges")
async def ctf_challenges(
    request: Request, session_context: SessionContext = Depends(get_session_context)
):
    """CTF Challenges list page"""
    return template_response(
        request,
        "pages/challenges.html",
        {"session_context": session_context},
    )


@router.get(
    "/challenges/{challenge_id}", response_class=HTMLResponse, name="ctf_challenge"
)
async def ctf_challenge(
    request: Request,
    challenge_id: str,
    session_context: SessionContext = Depends(get_session_context),
):
    """CTF Challenge detail page"""
    return template_response(
        request,
        "pages/challenge.html",
        {
            "challenge_id": challenge_id,
            "session_context": session_context,
        },
    )


@router.get("/activity", response_class=HTMLResponse, name="ctf_activity")
async def ctf_activity(
    request: Request, session_context: SessionContext = Depends(get_session_context)
):
    """CTF Activity stream page"""
    return template_response(
        request,
        "pages/activity.html",
        {"session_context": session_context},
    )


@router.get("/badges", response_class=HTMLResponse, name="ctf_badges")
async def ctf_badges(
    request: Request, session_context: SessionContext = Depends(get_session_context)
):
    """CTF Badges page"""
    return template_response(
        request,
        "pages/badges.html",
        {"session_context": session_context},
    )
