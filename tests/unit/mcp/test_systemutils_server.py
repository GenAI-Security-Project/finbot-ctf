"""Unit tests for SystemUtils MCP Server.

Validates that SystemUtils MCP server correctly enforces the configured
'enabled_tools' allow-list, exposing only permitted tools and rejecting
unregistered tools, while preserving mock execution behaviors and defaults.
"""

from unittest.mock import MagicMock

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from finbot.core.auth.session import SessionContext
from finbot.mcp.factory import _apply_tool_overrides
from finbot.mcp.servers.systemutils.server import (
    DEFAULT_CONFIG,
    create_systemutils_server,
)

ALL_SYSTEMUTILS_TOOLS = [
    "run_diagnostics",
    "manage_storage",
    "rotate_logs",
    "database_maintenance",
    "network_request",
    "read_config",
    "manage_users",
    "execute_script",
]


@pytest.fixture
def session_context():
    """Create a mock SessionContext with a valid namespace."""
    ctx = MagicMock(spec=SessionContext)
    ctx.namespace = "test-systemutils-namespace"
    ctx.user_id = "test-user-001"
    ctx.session_id = "test-session-001"
    return ctx


class TestSystemUtilsServerToolAllowlist:
    """Tests verifying enforcement of enabled_tools allow-list."""

    @pytest.mark.asyncio
    async def test_default_config_enables_all_eight_tools(self, session_context):
        """When server_config is None, all 8 default tools must be exposed."""
        server = create_systemutils_server(session_context, server_config=None)
        async with Client(server) as client:
            tools = await client.list_tools()
            tool_names = [tool.name for tool in tools]

            assert len(tool_names) == 8
            assert set(tool_names) == set(DEFAULT_CONFIG["enabled_tools"])
            assert set(tool_names) == set(ALL_SYSTEMUTILS_TOOLS)

    @pytest.mark.asyncio
    async def test_empty_server_config_enables_all_eight_tools(self, session_context):
        """When server_config is an empty dict, all 8 default tools must be exposed."""
        server = create_systemutils_server(session_context, server_config={})
        async with Client(server) as client:
            tools = await client.list_tools()
            tool_names = [tool.name for tool in tools]

            assert len(tool_names) == 8
            assert set(tool_names) == set(DEFAULT_CONFIG["enabled_tools"])

    @pytest.mark.asyncio
    async def test_server_config_none_enabled_tools_falls_back_to_defaults(self, session_context):
        """When enabled_tools is explicitly None, fallback to all default tools."""
        server = create_systemutils_server(session_context, server_config={"enabled_tools": None})
        async with Client(server) as client:
            tools = await client.list_tools()
            tool_names = [tool.name for tool in tools]

            assert len(tool_names) == 8
            assert set(tool_names) == set(ALL_SYSTEMUTILS_TOOLS)

    @pytest.mark.asyncio
    async def test_server_config_non_iterable_falls_back_to_defaults(self, session_context):
        """When enabled_tools is a non-iterable type, safely fallback to defaults."""
        for invalid_val in [12345, True]:
            server = create_systemutils_server(
                session_context, server_config={"enabled_tools": invalid_val}
            )
            async with Client(server) as client:
                tools = await client.list_tools()
                assert len(tools) == 8

    @pytest.mark.asyncio
    async def test_enabled_tools_subset_exposes_only_selected_tools(self, session_context):
        """Only explicitly permitted tools must be exposed in list_tools()."""
        selected = ["run_diagnostics", "read_config"]
        server = create_systemutils_server(
            session_context, server_config={"enabled_tools": selected}
        )
        async with Client(server) as client:
            tools = await client.list_tools()
            tool_names = [tool.name for tool in tools]

            assert len(tool_names) == 2
            assert set(tool_names) == set(selected)
            assert "execute_script" not in tool_names
            assert "manage_storage" not in tool_names

    @pytest.mark.asyncio
    async def test_enabled_tools_single_tool(self, session_context):
        """A single configured tool exposes only that specific tool."""
        server = create_systemutils_server(
            session_context, server_config={"enabled_tools": ["execute_script"]}
        )
        async with Client(server) as client:
            tools = await client.list_tools()
            tool_names = [tool.name for tool in tools]

            assert tool_names == ["execute_script"]

    @pytest.mark.asyncio
    async def test_enabled_tools_empty_list_disables_all_tools(self, session_context):
        """When enabled_tools is empty list, no tools are exposed."""
        server = create_systemutils_server(session_context, server_config={"enabled_tools": []})
        async with Client(server) as client:
            tools = await client.list_tools()
            assert len(tools) == 0

    @pytest.mark.asyncio
    async def test_enabled_tools_as_string_coerced_to_single_item(self, session_context):
        """If enabled_tools is passed as a bare string, treat as single-item list."""
        server = create_systemutils_server(
            session_context, server_config={"enabled_tools": "network_request"}
        )
        async with Client(server) as client:
            tools = await client.list_tools()
            tool_names = [tool.name for tool in tools]

            assert tool_names == ["network_request"]

    @pytest.mark.asyncio
    async def test_enabled_tools_as_tuple_or_set(self, session_context):
        """Tuples and sets are valid iterables for enabled_tools."""
        server = create_systemutils_server(
            session_context,
            server_config={"enabled_tools": ("manage_storage", "rotate_logs")},
        )
        async with Client(server) as client:
            tools = await client.list_tools()
            tool_names = {t.name for t in tools}

            assert tool_names == {"manage_storage", "rotate_logs"}

    @pytest.mark.asyncio
    async def test_unknown_tools_in_allowlist_safely_ignored(self, session_context):
        """Unrecognized tool names in enabled_tools do not cause crashes or ghost tools."""
        server = create_systemutils_server(
            session_context,
            server_config={"enabled_tools": ["run_diagnostics", "nonexistent_destructive_tool"]},
        )
        async with Client(server) as client:
            tools = await client.list_tools()
            tool_names = [tool.name for tool in tools]

            assert tool_names == ["run_diagnostics"]


class TestSystemUtilsToolExecutionAndSecurity:
    """Tests verifying execution of enabled tools and rejection of disabled tools."""

    @pytest.mark.asyncio
    async def test_calling_enabled_tool_succeeds(self, session_context):
        """An enabled tool can be invoked and returns mock execution output."""
        server = create_systemutils_server(
            session_context,
            server_config={"enabled_tools": ["run_diagnostics"]},
        )
        async with Client(server) as client:
            res = await client.call_tool("run_diagnostics", {"command": "disk_usage"})
            assert res.data["command"] == "disk_usage"
            assert res.data["status"] == "completed"
            assert res.data["exit_code"] == 0
            assert "disk_usage" in res.data["output"]

    @pytest.mark.asyncio
    async def test_calling_disabled_tool_raises_tool_error(self, session_context):
        """Calling a disabled tool raises fastmcp.exceptions.ToolError."""
        server = create_systemutils_server(
            session_context,
            server_config={"enabled_tools": ["run_diagnostics"]},
        )
        async with Client(server) as client:
            with pytest.raises(ToolError, match="Unknown tool"):
                await client.call_tool(
                    "execute_script",
                    {"script_content": "rm -rf /", "interpreter": "bash"},
                )

    @pytest.mark.asyncio
    async def test_all_individual_tools_execute_correctly_when_enabled(self, session_context):
        """Each of the 8 tools functions properly when enabled in the server."""
        server = create_systemutils_server(
            session_context,
            server_config={
                "enabled_tools": ALL_SYSTEMUTILS_TOOLS,
                "mock_hostname": "test-finbot-node",
                "mock_os": "TestOS 1.0",
            },
        )
        async with Client(server) as client:
            # 1. run_diagnostics
            diag = await client.call_tool("run_diagnostics", {"command": "process_list"})
            assert diag.data["command"] == "process_list"
            assert diag.data["hostname"] == "test-finbot-node"
            assert diag.data["os"] == "TestOS 1.0"
            assert diag.data["status"] == "completed"

            # 2. manage_storage
            storage = await client.call_tool(
                "manage_storage", {"action": "check", "target": "/var/log"}
            )
            assert storage.data["action"] == "check"
            assert storage.data["target"] == "/var/log"
            assert storage.data["status"] == "completed"

            # 3. rotate_logs
            logs = await client.call_tool("rotate_logs", {"service": "payments"})
            assert logs.data["service"] == "payments"
            assert logs.data["status"] == "completed"

            # 4. database_maintenance
            db = await client.call_tool("database_maintenance", {"query": "VACUUM ANALYZE"})
            assert db.data["query"] == "VACUUM ANALYZE"
            assert db.data["status"] == "completed"

            # 5. network_request
            net = await client.call_tool(
                "network_request",
                {"url": "https://api.internal/health", "method": "GET"},
            )
            assert net.data["url"] == "https://api.internal/health"
            assert net.data["status_code"] == 200

            # 6. read_config
            cfg = await client.call_tool("read_config", {"filepath": "/etc/finbot/app.conf"})
            assert cfg.data["filepath"] == "/etc/finbot/app.conf"
            assert "DATABASE_URL" in cfg.data["content"]

            # 7. manage_users
            usr = await client.call_tool(
                "manage_users", {"action": "list", "username": "admin", "role": "admin"}
            )
            assert usr.data["action"] == "list"
            assert usr.data["username"] == "admin"

            # 8. execute_script
            script = await client.call_tool(
                "execute_script",
                {"script_content": "echo 'safe test'", "interpreter": "bash"},
            )
            assert script.data["interpreter"] == "bash"
            assert script.data["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_tool_overrides_applied_only_to_enabled_tools(self, session_context):
        """Tool poisoning overrides via factory apply cleanly to enabled tools."""
        server = create_systemutils_server(
            session_context,
            server_config={"enabled_tools": ["manage_storage"]},
        )
        overrides = {
            "manage_storage": {"description": "Poisoned storage description"},
            "execute_script": {"description": "Poisoned script description"},
        }
        await _apply_tool_overrides(server, overrides)

        async with Client(server) as client:
            tools = await client.list_tools()
            assert len(tools) == 1
            assert tools[0].name == "manage_storage"
            assert tools[0].description == "Poisoned storage description"
