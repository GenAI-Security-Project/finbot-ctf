"""Unit tests for magic-link email validation and per-IP rate limiting."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from finbot.apps.finbot import auth
from finbot.core.data.database import Base
from finbot.core.data.models import MagicLinkToken


def _make_auth_client(client_ip: str = "203.0.113.10") -> TestClient:
    """Create a TestClient wrapping the auth router with a fixed client IP."""
    app = FastAPI()
    app.mount("/static", StaticFiles(directory="finbot/static"), name="static")
    app.include_router(auth.router)
    return TestClient(app, client=(client_ip, 12345))


@pytest.fixture(autouse=True)
def _reset_rate_limit_store():
    """Ensure rate-limiter state does not leak across tests."""
    with auth._rate_lock:
        auth._rate_store.clear()
    yield
    with auth._rate_lock:
        auth._rate_store.clear()


@pytest.fixture
def auth_db(monkeypatch):
    """Provide an isolated in-memory database patched into auth.SessionLocal."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    monkeypatch.setattr(auth, "SessionLocal", TestSessionLocal)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mock_email_service(monkeypatch):
    """Mock the email service so tests never invoke an external provider."""
    service = MagicMock()
    service.send_magic_link = AsyncMock(return_value=True)
    monkeypatch.setattr(auth, "get_email_service", lambda: service)
    return service


@pytest.mark.parametrize(
    "bad_email",
    [
        "not-an-email",
        "   ",
        "user@",
        "@example.com",
        "user@localhost",
    ],
)
def test_magic_link_rejects_invalid_email(auth_db, mock_email_service, bad_email):
    """Invalid email inputs return HTTP 400 without creating tokens or sending email."""
    with _make_auth_client() as client:
        response = client.post(
            "/auth/magic-link",
            data={"email": bad_email},
            follow_redirects=False,
        )

    assert response.status_code == 400
    assert "Invalid email" in response.text
    assert auth_db.query(MagicLinkToken).count() == 0
    mock_email_service.send_magic_link.assert_not_called()


def test_magic_link_accepts_and_normalizes_valid_email(auth_db, mock_email_service):
    """Valid email creates a token, sends a magic link, and redirects via 303."""
    with _make_auth_client(client_ip="203.0.113.20") as client:
        response = client.post(
            "/auth/magic-link",
            data={"email": "  Alice.Example@Example.COM "},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/auth/check-email?email=alice.example@example.com"

    tokens = auth_db.query(MagicLinkToken).all()
    assert len(tokens) == 1
    assert tokens[0].email == "alice.example@example.com"
    assert tokens[0].ip_address == "203.0.113.20"
    mock_email_service.send_magic_link.assert_awaited_once()


def test_magic_link_rate_limits_after_max_requests(auth_db, mock_email_service):
    """Exceeding the per-IP window returns HTTP 429 while separate IPs stay unaffected."""
    with _make_auth_client(client_ip="198.51.100.5") as client:
        for i in range(auth._RATE_LIMIT_MAX):
            resp = client.post(
                "/auth/magic-link",
                data={"email": f"user{i}@example.com"},
                follow_redirects=False,
            )
            assert resp.status_code == 303

        blocked = client.post(
            "/auth/magic-link",
            data={"email": "user5@example.com"},
            follow_redirects=False,
        )

    assert blocked.status_code == 429
    assert "Too many requests" in blocked.text
    assert mock_email_service.send_magic_link.await_count == auth._RATE_LIMIT_MAX

    # A different IP still has its own quota
    with _make_auth_client(client_ip="198.51.100.6") as other_client:
        other_resp = other_client.post(
            "/auth/magic-link",
            data={"email": "other@example.com"},
            follow_redirects=False,
        )
    assert other_resp.status_code == 303


def test_rate_limiter_resets_after_window_and_evicts_stale_entries(monkeypatch):
    """Expired timestamps allow subsequent requests and bound store growth."""
    fake_now = [100.0]
    monkeypatch.setattr(auth.time, "monotonic", lambda: fake_now[0])

    for _ in range(auth._RATE_LIMIT_MAX):
        assert auth._is_rate_limited("192.0.2.1") is False
    assert auth._is_rate_limited("192.0.2.1") is True

    # Advance past the rate limit window
    fake_now[0] += auth._RATE_LIMIT_WINDOW + 1
    assert auth._is_rate_limited("192.0.2.1") is False

    # Fill store up to _MAX_STORE_SIZE with expired IPs and trigger eviction
    monkeypatch.setattr(auth, "_MAX_STORE_SIZE", 2)
    auth._rate_store.clear()
    auth._rate_store["192.0.2.10"] = [fake_now[0] - auth._RATE_LIMIT_WINDOW - 5]
    auth._rate_store["192.0.2.11"] = [fake_now[0] - auth._RATE_LIMIT_WINDOW - 5]
    assert auth._is_rate_limited("192.0.2.12") is False
    assert "192.0.2.10" not in auth._rate_store
    assert "192.0.2.12" in auth._rate_store


def test_rate_limiter_clears_store_if_eviction_leaves_store_full(monkeypatch):
    """If active entries fill _MAX_STORE_SIZE, clearing prevents unbounded growth."""
    fake_now = 100.0
    monkeypatch.setattr(auth.time, "monotonic", lambda: fake_now)
    monkeypatch.setattr(auth, "_MAX_STORE_SIZE", 2)

    auth._rate_store["192.0.2.20"] = [fake_now]
    auth._rate_store["192.0.2.21"] = [fake_now]
    assert auth._is_rate_limited("192.0.2.22") is False
    assert list(auth._rate_store.keys()) == ["192.0.2.22"]


def test_authenticated_user_redirects_before_validation_or_rate_limit(auth_db, mock_email_service):
    """Authenticated users redirect to /portals without hitting rate limiting."""
    app = FastAPI()

    @app.middleware("http")
    async def inject_auth_session(request, call_next):
        request.state.session_context = SimpleNamespace(
            email="signed@example.com",
            is_temporary=False,
            session_id="sess-1",
        )
        return await call_next(request)

    app.include_router(auth.router)

    with TestClient(app, client=("198.51.100.99", 12345)) as client:
        response = client.post(
            "/auth/magic-link",
            data={"email": "bad-email"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/portals"
    mock_email_service.send_magic_link.assert_not_called()
