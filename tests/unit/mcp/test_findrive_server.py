"""Tests for the FinDrive MCP server's upload_file tool."""

import pytest

from finbot.core.auth.session import session_manager
from finbot.mcp.servers.findrive.server import create_findrive_server


@pytest.fixture
def upload(db):
    """Return the FinDrive upload_file tool bound to a fresh admin session."""
    _ = db
    session_context = session_manager.create_session(email="findrive_test@example.com")
    server = create_findrive_server(session_context)

    async def call(**kwargs):
        tool = await server.get_tool("upload_file")
        return tool.fn(**kwargs)

    return call


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["", " ", "   ", "\t", "\n", " \t\n "])
async def test_fd_str_008_empty_content_rejected(upload, content):
    """FD-STR-008: blank content must be rejected instead of stored."""
    result = await upload(filename="doc.pdf", content=content)

    assert "error" in result, f"{content!r} was accepted"
    assert "file_id" not in result


@pytest.mark.asyncio
async def test_fd_str_008_valid_content_still_uploads(upload):
    """Content with real text is unaffected by the new check."""
    result = await upload(filename="doc.pdf", content="Invoice total: 100.00")

    assert "error" not in result
    assert result["status"] == "uploaded"
    assert result["filename"] == "doc.pdf"
    assert result["file_size"] > 0


@pytest.mark.asyncio
async def test_fd_str_008_surrounding_whitespace_preserved(upload):
    """Padding around real content is not treated as blank."""
    result = await upload(filename="doc.pdf", content="  Invoice total: 100.00  ")

    assert "error" not in result
    assert result["status"] == "uploaded"
