"""Unit tests for SystemUtils MCP Server manage_users operations.

Validates that SystemUtils manage_users protects reserved system accounts
from deletion while allowing valid user lifecycle operations.
"""

from unittest.mock import MagicMock

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from finbot.core.auth.session import SessionContext
from finbot.mcp.servers.systemutils.server import create_systemutils_server


@pytest.fixture
def session_context():
    """Create a mock SessionContext with a valid namespace."""
    ctx = MagicMock(spec=SessionContext)
    ctx.namespace = "test-systemutils-namespace"
    ctx.user_id = "test-user-001"
    ctx.session_id = "test-session-001"
    return ctx


class TestManageUsers:
    """Tests for manage_users tool validation and protection."""

    @pytest.mark.asyncio
    async def test_su_usr_001_returns_expected_fields(self, session_context):
        """SU-USR-001: manage_users returns a complete result for a valid operation."""
        server = create_systemutils_server(session_context)
        async with Client(server) as client:
            result = await client.call_tool(
                "manage_users",
                {"action": "list", "username": "admin", "role": "viewer"},
            )
            data = result.data
            assert data["status"] == "completed"
            assert data["action"] == "list"
            assert data["username"] == "admin"
            assert data["role"] == "viewer"
            assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_su_usr_002_delete_admin_rejected_as_protected(self, session_context):
        """SU-USR-002: Deleting admin user must be rejected as protected."""
        server = create_systemutils_server(session_context)
        async with Client(server) as client:
            with pytest.raises((ValueError, ToolError), match="protected"):
                await client.call_tool(
                    "manage_users",
                    {"action": "delete", "username": "admin"},
                )

    @pytest.mark.asyncio
    async def test_su_usr_002_delete_admin_accepted_without_validation(self, session_context):
        """SU-USR-002 Acceptance alias: verify deleting admin raises an error."""
        await self.test_su_usr_002_delete_admin_rejected_as_protected(session_context)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "protected_name",
        [
            "admin",
            "Admin",
            "ADMIN",
            "root",
            "Root",
            "ROOT",
            "system",
            "System",
            "SYSTEM",
            "  admin  ",
        ],
    )
    async def test_protected_usernames_rejected_case_insensitively(
        self, session_context, protected_name
    ):
        """All reserved accounts (admin, root, system) are blocked from deletion case-insensitively."""
        server = create_systemutils_server(session_context)
        async with Client(server) as client:
            with pytest.raises((ValueError, ToolError), match="protected"):
                await client.call_tool(
                    "manage_users",
                    {"action": "delete", "username": protected_name},
                )

    @pytest.mark.asyncio
    async def test_deleting_regular_user_succeeds(self, session_context):
        """Deleting a standard, non-protected account is allowed."""
        server = create_systemutils_server(session_context)
        async with Client(server) as client:
            result = await client.call_tool(
                "manage_users",
                {"action": "delete", "username": "temp_guest"},
            )
            assert result.data["status"] == "completed"
            assert result.data["action"] == "delete"
            assert result.data["username"] == "temp_guest"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("action", ["list", "create", "modify"])
    async def test_non_delete_actions_on_protected_user_allowed(self, session_context, action):
        """Actions other than delete (list, create, modify) on protected accounts are not blocked."""
        server = create_systemutils_server(session_context)
        async with Client(server) as client:
            result = await client.call_tool(
                "manage_users",
                {"action": action, "username": "admin", "role": "admin"},
            )
            assert result.data["status"] == "completed"
            assert result.data["action"] == action
            assert result.data["username"] == "admin"
