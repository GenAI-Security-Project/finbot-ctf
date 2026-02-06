"""Template utilities and context processors for FinBot CTF Platform"""

from fastapi import Request
from fastapi.templating import Jinja2Templates

from finbot.core.auth.csrf import csrf_token_field, csrf_token_meta, get_csrf_token


def add_csrf_context(request: Request, context: dict) -> dict:
    """Add CSRF token context to template context"""
    csrf_context = {
        "csrf_token": get_csrf_token(request),
        "csrf_token_field": csrf_token_field(request),
        "csrf_token_meta": csrf_token_meta(request),
    }

    # Merge with existing context
    return {**context, **csrf_context}


def add_session_context(request: Request, context: dict) -> dict:
    """Add session context to template context for CTF sidecar etc."""
    session_context = getattr(request.state, "session_context", None)
    if session_context:
        context["session_context"] = session_context
        if session_context.email:
            context["user"] = {"email": session_context.email}
    return context


class TemplateResponse:
    """Enhanced template response with automatic CSRF and session context injection"""

    def __init__(self, directory: str):
        self.templates = Jinja2Templates(directory=directory)

    def __call__(self, request: Request, name: str, context: dict = None, **kwargs):
        """Render template with CSRF and session context automatically added"""
        if context is None:
            context = {}

        # Add CSRF context
        enhanced_context = add_csrf_context(request, context)

        # Add session context for CTF sidecar
        enhanced_context = add_session_context(request, enhanced_context)

        return self.templates.TemplateResponse(
            request=request, name=name, context=enhanced_context, **kwargs
        )
