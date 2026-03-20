"""Route handlers for the OWASP FinBot CTF platform pages"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from finbot.core.templates import TemplateResponse

finbot_templates = TemplateResponse("finbot/apps/finbot/templates")
web_templates = TemplateResponse("finbot/apps/web/templates")

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """OWASP FinBot CTF home page"""
    return finbot_templates(request, "home.html")


@router.get("/portals", response_class=HTMLResponse)
async def portals(request: Request):
    """Portals page - access vendor, admin, and CTF portals"""
    return finbot_templates(request, "portals.html")


@router.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    """About OWASP FinBot - project info, team, and contributors"""
    return web_templates(request, "pages/finbot.html")
