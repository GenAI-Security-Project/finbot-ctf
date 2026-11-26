"""Tests for the challenge check/hint endpoints (#514).

Both endpoints had an `if not session_context` check that could never be
true, because get_session_context always returns a session (temporary or
not). The check has been removed. Temporary sessions are allowed on purpose,
since the CTF can be played without signing up.
"""

import inspect
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from finbot.apps.ctf.routes import challenges
from finbot.core.auth.middleware import get_session_context
from finbot.core.data.database import get_db


def _session_deps(func):
    sig = inspect.signature(func)
    return [
        p.default.dependency for p in sig.parameters.values() if hasattr(p.default, "dependency")
    ]


@pytest.fixture
def anon_client(monkeypatch):
    """Client with a temporary session and mocked repositories."""
    challenge = SimpleNamespace(
        id="test-challenge",
        hints=json.dumps([{"text": "Look at the invoice notes", "cost": 10}]),
    )
    challenge_repo = MagicMock()
    challenge_repo.get_challenge.return_value = challenge

    progress_repo = MagicMock()
    progress_repo.get_progress.return_value = None
    progress_repo.use_hint.return_value = SimpleNamespace(hints_cost=10)

    monkeypatch.setattr(challenges, "ChallengeRepository", lambda db: challenge_repo)
    monkeypatch.setattr(
        challenges, "UserChallengeProgressRepository", lambda db, ctx: progress_repo
    )

    app = FastAPI()
    app.include_router(challenges.router)
    app.dependency_overrides[get_session_context] = lambda: SimpleNamespace(is_temporary=True)
    app.dependency_overrides[get_db] = lambda: None

    return TestClient(app), progress_repo


@pytest.mark.unit
def test_check_works_for_temporary_session(anon_client):
    client, progress_repo = anon_client

    response = client.post("/api/v1/challenges/test-challenge/check")

    assert response.status_code == 200
    assert response.json()["status"] == "available"
    progress_repo.record_attempt.assert_called_once_with("test-challenge")


@pytest.mark.unit
def test_hint_works_for_temporary_session(anon_client):
    client, _ = anon_client

    response = client.post("/api/v1/challenges/test-challenge/hint")

    assert response.status_code == 200
    assert response.json()["hint_text"] == "Look at the invoice notes"


@pytest.mark.unit
@pytest.mark.parametrize("endpoint", [challenges.check_challenge, challenges.use_hint])
def test_endpoints_use_regular_session_dependency(endpoint):
    assert get_session_context in _session_deps(endpoint)


@pytest.mark.unit
@pytest.mark.parametrize("endpoint", [challenges.check_challenge, challenges.use_hint])
def test_dead_session_check_removed(endpoint):
    assert "if not session_context" not in inspect.getsource(endpoint)
