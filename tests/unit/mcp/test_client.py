import pytest
from finbot.mcp.client import MCPClient


class MockMCPServer:
    async def list_tools(self):
        return [{"name": "test_tool"}]

    async def call_tool(self, tool_name, args):
        return {"tool": tool_name, "args": args}


class MockRegistry:
    def __init__(self):
        self.servers = {"payments": MockMCPServer()}

    def get_server(self, name):
        return self.servers[name]


@pytest.mark.asyncio
async def test_list_tools_allowed_server():
    registry = MockRegistry()
    client = MCPClient(
        agent_name="TestAgent",
        allowed_servers=["payments"],
        mcp_registry=registry,
    )

    tools = await client.list_tools("payments")
    assert tools[0]["name"] == "test_tool"


@pytest.mark.asyncio
async def test_call_tool_allowed_server():
    registry = MockRegistry()
    client = MCPClient(
        agent_name="TestAgent",
        allowed_servers=["payments"],
        mcp_registry=registry,
    )

    result = await client.call_tool(
        server_name="payments",
        tool_name="refund",
        args={"id": 1},
    )

    assert result["tool"] == "refund"


@pytest.mark.asyncio
async def test_call_tool_disallowed_server():
    registry = MockRegistry()
    client = MCPClient(
        agent_name="TestAgent",
        allowed_servers=["payments"],
        mcp_registry=registry,
    )

    with pytest.raises(PermissionError):
        await client.call_tool(
            server_name="drive",
            tool_name="upload",
            args={},
        )
