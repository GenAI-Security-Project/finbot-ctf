import pytest
from finbot.agents_mcp.base_mcp_agent import BaseMCPAgent


class FakeMCPClient:
    async def call_tool(self, server_name, tool_name, args):
        return {"status": "ok"}


@pytest.mark.asyncio
async def test_base_agent_call_tool_delegates_to_client():
    agent = BaseMCPAgent(name="TestAgent")

    fake_client = FakeMCPClient()
    agent.set_mcp_client(fake_client)

    result = await agent.call_tool(
        server="payments",
        tool="test_tool",
        args={"a": 1},
    )

    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_base_agent_call_tool_without_client_raises():
    agent = BaseMCPAgent(name="TestAgent")

    with pytest.raises(RuntimeError):
        await agent.call_tool(
            server="payments",
            tool="test_tool",
            args={},
        )
