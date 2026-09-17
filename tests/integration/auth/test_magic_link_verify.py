"""
Integration tests for magic-link verification.

GET /auth/verify used to consume the token and issue a session, so anything that
merely fetched the emailed URL -- a click tracker, a mail scanner, a link preview,
or the user opening it on a second device -- signed in as the user and locked the
real user out. Refs #541.

The contract these tests pin down:
    GET  /auth/verify  -> read-only confirmation page, consumes nothing, signs no one in
    POST /auth/verify  -> creates the session first, then consumes the token

Two things make these bugs easy to miss, and the tests are written around both:

- Every retry uses a separate TestClient. A retry from a client that already holds a
  signed-in session short-circuits in _is_authenticated before the token is read.
- Every test uses a fresh email address, and new and returning users are tested
  separately. Signing in an existing account discards the temporary session, and the
  middleware then sets the cookie back to that discarded session, so a returning user
  ends up anonymous. That hides the prefetch bypass for returning users and makes
  results depend on what is already in the database.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from finbot.config import settings
from finbot.core.auth.session import session_manager
from finbot.core.data.database import SessionLocal
from finbot.core.data.models import MagicLinkToken
from finbot.main import app


class _RecordingEmailService:
    """Captures the magic link instead of sending it."""

    def __init__(self):
        self.last_link: str | None = None

    async def send_magic_link(self, to_email: str, magic_link: str) -> bool:
        _ = to_email
        self.last_link = magic_link
        return True


class _FailingSessionManager:
    """Delegates to the real session manager, except that sign-in cannot create a session."""

    def __init__(self, real):
        self._real = real

    def upgrade_to_permanent(self, **_kwargs):
        return None, None

    def create_session(self, **_kwargs):
        return None

    def __getattr__(self, name):
        return getattr(self._real, name)


@pytest.fixture
def email_service(monkeypatch):
    service = _RecordingEmailService()
    monkeypatch.setattr("finbot.apps.finbot.auth.get_email_service", lambda: service)
    return service


def _unique_email(label: str) -> str:
    return f"{label}-{uuid.uuid4().hex[:12]}@example.test"


def _new_client() -> TestClient:
    """A separate browser: its own cookie jar, no shared session."""
    return TestClient(app, raise_server_exceptions=False)


def _request_token(email_service, email: str, client: TestClient | None = None) -> str:
    (client or _new_client()).post(
        "/auth/magic-link", data={"email": email}, follow_redirects=False
    )
    assert email_service.last_link, "no magic link was generated"
    return email_service.last_link.split("token=")[1]


def _token_row(token: str) -> MagicLinkToken | None:
    db = SessionLocal()
    try:
        return db.query(MagicLinkToken).filter(MagicLinkToken.token == token).first()
    finally:
        db.close()


def _is_signed_in(client: TestClient) -> bool:
    status = client.get("/api/session/status").json()
    return status["is_temporary"] is False


def _sign_in(client: TestClient, email_service, email: str, same_browser: bool = False):
    """Complete a sign-in the way a person would: open the link, then confirm."""
    token = _request_token(email_service, email, client if same_browser else None)
    client.get(f"/auth/verify?token={token}", follow_redirects=False)
    return client.post("/auth/verify", data={"token": token}, follow_redirects=False)


def _account(kind: str, email_service) -> str:
    """An email for a new account, or for one that has signed in before."""
    email = _unique_email(kind)
    if kind == "returning":
        _sign_in(_new_client(), email_service, email)
    return email


@pytest.mark.integration
class TestVerifyGetIsSafe:
    """Fetching the verify URL must have no effect beyond rendering a page."""

    def test_get_does_not_consume_the_token(self, email_service):
        token = _request_token(email_service, _unique_email("get-consume"))

        _new_client().get(f"/auth/verify?token={token}", follow_redirects=False)

        row = _token_row(token)
        assert row is not None and row.used_at is None, (
            "a GET of the verify URL consumed the token -- any prefetch locks the " "user out"
        )

    @pytest.mark.parametrize("kind", ["new", "returning"])
    def test_get_does_not_sign_in_the_fetching_client(self, email_service, kind):
        """The authentication bypass: a client that only fetches the URL stays anonymous.

        For returning users this currently passes only because their sign-in is
        broken outright. It guards against the bypass reappearing once that is fixed.
        """
        email = _account(kind, email_service)
        token = _request_token(email_service, email)
        prefetcher = _new_client()

        prefetcher.get(f"/auth/verify?token={token}", follow_redirects=False)

        assert not _is_signed_in(prefetcher), (
            f"a client that merely fetched the verify URL holds a signed-in session "
            f"for a {kind} account -- link scanners and click trackers take over "
            f"the account"
        )

    def test_get_renders_a_form_that_posts_the_token(self, email_service):
        token = _request_token(email_service, _unique_email("get-form"))

        response = _new_client().get(f"/auth/verify?token={token}", follow_redirects=False)

        assert response.status_code == 200
        body = response.text
        assert (
            'method="POST"' in body or "method='POST'" in body
        ), "no POST form on the confirmation page"
        assert 'action="/auth/verify"' in body, "confirmation form does not post to /auth/verify"
        assert token in body, "confirmation form does not carry the token"


@pytest.mark.integration
class TestVerifyPostSignsIn:
    """Signing in requires the POST, and the POST is single-use."""

    @pytest.mark.parametrize("kind", ["new", "returning"])
    @pytest.mark.parametrize("same_browser", [True, False], ids=["same-browser", "other-browser"])
    def test_user_signs_in(self, email_service, kind, same_browser):
        """Every combination of account and browser signs in, with one session cookie."""
        email = _account(kind, email_service)
        user = _new_client()

        response = _sign_in(user, email_service, email, same_browser=same_browser)

        assert (
            response.status_code == 303
        ), f"sign-in returned {response.status_code}, expected a redirect"
        assert response.headers.get("location") == "/portals"
        session_cookies = [
            value
            for name, value in response.headers.multi_items()
            if name == "set-cookie" and value.startswith(f"{settings.SESSION_COOKIE_NAME}=")
        ]
        assert len(session_cookies) == 1, f"expected one session cookie, got {len(session_cookies)}"
        assert f"Max-Age={settings.PERM_SESSION_TIMEOUT}" in session_cookies[0]
        assert _is_signed_in(user), f"a {kind} user was redirected to /portals but is not signed in"

    def test_returning_user_signs_in_when_the_submit_has_no_session(self, email_service):
        """Opening the confirmation page normally gives the browser a session before it
        submits. If the submit arrives without one -- cookies cleared, or the session
        expired in between -- a returning user must still be signed in.

        The middleware used to re-set the cookie to the temporary session that sign-in
        had just deleted, leaving the user anonymous (#583).
        """
        email = _account("returning", email_service)
        token = _request_token(email_service, email)
        user = _new_client()

        response = user.post("/auth/verify", data={"token": token}, follow_redirects=False)

        assert response.status_code == 303
        session_cookies = [
            value
            for name, value in response.headers.multi_items()
            if name == "set-cookie" and value.startswith(f"{settings.SESSION_COOKIE_NAME}=")
        ]
        assert len(session_cookies) == 1, (
            f"expected one session cookie, got {len(session_cookies)} -- the middleware "
            f"overwrote the cookie the sign-in route set"
        )
        assert _is_signed_in(
            user
        ), "a returning user was redirected to /portals but is not signed in"

    def test_user_signs_in_after_link_was_prefetched(self, email_service):
        token = _request_token(email_service, _unique_email("post-after-prefetch"))

        _new_client().get(f"/auth/verify?token={token}", follow_redirects=False)

        user = _new_client()
        user.get(f"/auth/verify?token={token}", follow_redirects=False)
        response = user.post("/auth/verify", data={"token": token}, follow_redirects=False)

        assert (
            response.status_code == 303
        ), f"sign-in after a prefetch returned {response.status_code}, expected a redirect"
        assert _is_signed_in(user)
        assert _token_row(token).used_at is not None, "a successful sign-in must consume the token"

    def test_token_cannot_be_redeemed_twice(self, email_service):
        token = _request_token(email_service, _unique_email("post-single-use"))

        first = _new_client()
        first.post("/auth/verify", data={"token": token}, follow_redirects=False)
        assert _is_signed_in(first), "the first POST should sign in"

        second = _new_client()
        second.post("/auth/verify", data={"token": token}, follow_redirects=False)
        assert not _is_signed_in(second), "a spent token signed in a second client"


@pytest.mark.integration
class TestVerifySessionFailure:
    """A failed sign-in must leave the link usable."""

    def test_session_failure_does_not_burn_the_token(self, email_service, monkeypatch):
        token = _request_token(email_service, _unique_email("post-session-failure"))
        monkeypatch.setattr(
            "finbot.apps.finbot.auth.session_manager",
            _FailingSessionManager(session_manager),
        )

        failed = _new_client()
        failed.post("/auth/verify", data={"token": token}, follow_redirects=False)

        assert not _is_signed_in(failed)
        assert _token_row(token).used_at is None, (
            "the token was consumed although no session was created -- the link is " "now dead"
        )

        monkeypatch.undo()
        retry = _new_client()
        retry.post("/auth/verify", data={"token": token}, follow_redirects=False)
        assert _is_signed_in(retry), "the link did not work after the session layer recovered"
