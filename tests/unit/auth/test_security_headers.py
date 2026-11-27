"""Unit tests for security response headers and /api/session/status."""

import pytest
from starlette.responses import Response

from finbot.core.auth.middleware import SessionMiddleware


@pytest.mark.unit
def test_security_headers_present_and_xss_protection_removed(fast_client):
    """Responses include CSP and modern headers without deprecated X-XSS-Protection."""
    resp = fast_client.get("/api/session/status")

    assert resp.status_code == 200
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "X-XSS-Protection" not in resp.headers

    csp = resp.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "https://cdn.tailwindcss.com" in csp
    assert "https://cdn.jsdelivr.net" in csp
    assert "https://fonts.googleapis.com" in csp
    assert "https://fonts.gstatic.com" in csp
    assert "img-src 'self' data: https:" in csp
    assert "connect-src 'self' ws: wss:" in csp


@pytest.mark.unit
def test_session_middleware_add_security_headers_unit():
    """Direct check of SessionMiddleware._add_security_headers."""
    middleware = SessionMiddleware(app=lambda scope, receive, send: None)
    resp = Response()

    middleware._add_security_headers(resp)

    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "X-XSS-Protection" not in resp.headers
    assert "img-src 'self' data: https:" in resp.headers["Content-Security-Policy"]


@pytest.mark.unit
def test_session_status_still_returns_csrf_token(fast_client):
    """Keep csrf_token in /api/session/status for callers and test helpers."""
    resp = fast_client.get("/api/session/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data.get("csrf_token")
