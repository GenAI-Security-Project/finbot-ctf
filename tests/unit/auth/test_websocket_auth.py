"""
WebSocket /ws/connect authentication tests

The handshake must identify the user from the session cookie, not from
client-supplied query params, and a connection may only subscribe to its
own activity topic.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from finbot.config import settings
from finbot.core.auth.session import session_manager
from finbot.core.data.models import UserSession
from finbot.core.websocket.manager import get_ws_manager


def _cookie_header(session_id: str) -> dict:
    return {"cookie": f"{settings.SESSION_COOKIE_NAME}={session_id}"}


VICTIM_URL = "/ws/connect?namespace=ns_victim&user_id=user_victim"


def _assert_rejected(client: TestClient, url: str = VICTIM_URL, headers=None):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(url, headers=headers or {}) as ws:
            ws.receive_json()
    assert exc_info.value.code == 1008


@pytest.mark.unit
def test_ws_rejects_connection_without_session_cookie(client, db):
    """No cookie: the handshake is refused even if IDs are passed in the URL."""
    _assert_rejected(client)


@pytest.mark.unit
def test_ws_rejects_unknown_session_cookie(client, db):
    _assert_rejected(client, headers=_cookie_header("not-a-real-session"))


@pytest.mark.unit
def test_ws_rejects_expired_session(client, db):
    ctx = session_manager.create_session(email="ws_expired@example.com")
    row = db.query(UserSession).filter(UserSession.session_id == ctx.session_id).first()
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()

    _assert_rejected(client, headers=_cookie_header(ctx.session_id))


@pytest.mark.unit
def test_ws_rejects_tampered_session(client, db):
    ctx = session_manager.create_session(email="ws_tampered@example.com")
    row = db.query(UserSession).filter(UserSession.session_id == ctx.session_id).first()
    row.signature = "0" * 64
    db.commit()

    _assert_rejected(client, headers=_cookie_header(ctx.session_id))


@pytest.mark.unit
def test_ws_identity_comes_from_session_not_query_params(client, db):
    """Query params pointing at another user are ignored."""
    ctx = session_manager.create_session(email="ws_owner@example.com")
    manager = get_ws_manager()

    with client.websocket_connect(VICTIM_URL, headers=_cookie_header(ctx.session_id)) as ws:
        assert ws.receive_json()["type"] == "connected"
        assert manager.get_user_connection_count(ctx.namespace, ctx.user_id) == 1
        assert manager.get_user_connection_count("ns_victim", "user_victim") == 0


@pytest.mark.unit
def test_ws_allows_subscribing_to_own_activity_topic(client, db):
    ctx = session_manager.create_session(email="ws_own_topic@example.com")
    own_topic = f"activity:{ctx.namespace}:{ctx.user_id}"

    with client.websocket_connect("/ws/connect", headers=_cookie_header(ctx.session_id)) as ws:
        ws.receive_json()  # connected
        ws.send_json({"action": "subscribe", "topic": own_topic})
        msg = ws.receive_json()
        assert msg["type"] == "subscribed"
        assert msg["data"]["topic"] == own_topic


@pytest.mark.unit
def test_ws_rejects_subscribing_to_another_users_topic(client, db):
    ctx = session_manager.create_session(email="ws_snoop@example.com")
    other_topic = "activity:ns_someone_else:user_someone_else"
    manager = get_ws_manager()

    with client.websocket_connect("/ws/connect", headers=_cookie_header(ctx.session_id)) as ws:
        connection_id = ws.receive_json()["data"]["connection_id"]
        ws.send_json({"action": "subscribe", "topic": other_topic})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert other_topic not in manager._connections[connection_id].subscriptions


@pytest.mark.unit
def test_get_session_identity_does_not_rotate_or_touch_session(db):
    """A session due for rotation must keep its ID, since a WebSocket
    handshake can't hand the browser a new cookie."""
    ctx = session_manager.create_session(email="ws_rotation@example.com")
    row = db.query(UserSession).filter(UserSession.session_id == ctx.session_id).first()
    row.last_rotation = datetime.now(UTC) - timedelta(days=1)
    db.commit()
    expires_before = row.expires_at

    identity = session_manager.get_session_identity(ctx.session_id)

    assert identity == (ctx.namespace, ctx.user_id)
    db.expire_all()
    rows = db.query(UserSession).filter(UserSession.user_id == ctx.user_id).all()
    assert [r.session_id for r in rows] == [ctx.session_id]
    assert rows[0].expires_at == expires_before


@pytest.mark.unit
def test_get_session_identity_handles_missing_cookie(db):
    assert session_manager.get_session_identity(None) is None
    assert session_manager.get_session_identity("") is None
