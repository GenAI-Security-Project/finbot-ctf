"""Argument validation in the FinDrive and FinMail MCP tools.

Covers #345, #348, #352, #353, #359, #366, #367 and #368.
"""

from contextlib import contextmanager

import pytest

from finbot.core.auth.session import session_manager
from finbot.mcp.servers.findrive.server import create_findrive_server
from finbot.mcp.servers.finmail.models import Email
from finbot.mcp.servers.finmail.server import create_finmail_server

pytestmark = pytest.mark.asyncio


@pytest.fixture
def session(db, monkeypatch):
    @contextmanager
    def _db_session():
        yield db

    for server in ("findrive", "finmail"):
        monkeypatch.setattr(f"finbot.mcp.servers.{server}.server.db_session", _db_session)
    return session_manager.create_session(email="mcp_validation@example.com")


async def call(server, tool, **arguments):
    result = await server.call_tool(tool, arguments)
    return result.structured_content


@pytest.fixture
def drive(session):
    return create_findrive_server(session)


@pytest.fixture
def mail(session):
    return create_finmail_server(session)


@pytest.mark.parametrize(
    "arguments",
    [{"filename": ""}, {"filename": "  \t"}, {"content": ""}, {"content": " \n "}],
)
async def test_blank_upload_raises_and_is_not_stored(drive, arguments):
    with pytest.raises(Exception, match="must not be empty"):
        await call(drive, "upload_file", **{"filename": "a.pdf", "content": "text", **arguments})

    assert (await call(drive, "list_files"))["count"] == 0


@pytest.mark.parametrize(
    "arguments",
    [
        {"filename": "../../etc/passwd"},
        {"filename": "..\\..\\secrets.txt"},
        {"filename": "/etc/passwd"},
        {"filename": ".."},
        {"folder": "../../etc"},
        {"folder": "/invoices/../admin"},
    ],
)
async def test_traversal_is_rejected_and_not_stored(drive, arguments):
    result = await call(
        drive,
        "upload_file",
        **{"filename": "a.pdf", "content": "text", **arguments},
    )

    assert "error" in result
    assert (await call(drive, "list_files"))["count"] == 0


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"filename": "report..final.pdf"},
        {"filename": "Q1 compliance (v2).pdf"},
        {"folder": "invoices"},
        {"folder": "/invoices/2026"},
    ],
)
async def test_ordinary_upload_still_works(drive, arguments):
    result = await call(
        drive,
        "upload_file",
        **{"filename": "a.pdf", "content": "text", **arguments},
    )

    assert result["status"] == "uploaded"


@pytest.mark.parametrize("tool, arguments", [("list_files", {}), ("search_files", {"query": "a"})])
async def test_negative_limit_raises(drive, tool, arguments):
    with pytest.raises(Exception, match="limit must be non-negative"):
        await call(drive, tool, limit=-1, **arguments)


@pytest.mark.parametrize("tool, arguments", [("list_files", {}), ("search_files", {"query": "a"})])
async def test_zero_limit_returns_nothing(drive, tool, arguments):
    await call(drive, "upload_file", filename="a.pdf", content="a")

    assert (await call(drive, tool, limit=0, **arguments))["count"] == 0


@pytest.mark.parametrize("field", ["to", "cc", "bcc"])
@pytest.mark.parametrize("address", ["no-at-sign", "@domain.com", "user@", ""])
async def test_malformed_address_sends_nothing(db, mail, field, address):
    arguments = {"to": ["ok@example.com"], "subject": "s", "body": "b"}
    arguments[field] = [*arguments.get(field, []), address]

    result = await call(mail, "send_email", **arguments)

    assert "error" in result
    assert db.query(Email).count() == 0


async def test_external_address_still_reaches_dead_drop(mail):
    result = await call(mail, "send_email", to=["attacker@evil.example"], subject="s", body="b")

    assert [d["type"] for d in result["deliveries"]] == ["external"]


@pytest.mark.parametrize("length, accepted", [(100, True), (101, False)])
async def test_sender_name_length_limit(db, mail, length, accepted):
    result = await call(
        mail,
        "send_email",
        to=["ok@example.com"],
        subject="s",
        body="b",
        sender_name="A" * length,
    )

    assert ("error" not in result) is accepted
    assert db.query(Email).count() == int(accepted)
