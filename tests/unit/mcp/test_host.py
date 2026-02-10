import pytest
from finbot.mcp.host import MCPHost


class MockMCPClient:
    def __init__(self):
        self.called = False

    async def call_tool(self, server_name, tool_name, args):
        self.called = True
        return {"ok": True}


class MockTelemetry:
    def __init__(self):
        self.attempts = []
        self.results = []

    def record_call_attempt(self, agent, server, tool):
        self.attempts.append((agent, server, tool))

    def record_call_result(self, agent, server, tool, result):
        self.results.append((agent, server, tool, result))


@pytest.mark.asyncio
async def test_call_tool_unregistered_agent():
    host = MCPHost()

    with pytest.raises(PermissionError):
        await host.call_tool(
            agent_name="UnknownAgent",
            server_name="payments",
            tool_name="refund",
            args={},
        )


@pytest.mark.asyncio
async def test_call_tool_registered_agent():
    telemetry = MockTelemetry()
    host = MCPHost(telemetry=telemetry)

    client = MockMCPClient()
    host.register_agent_client("Agent1", client)

    result = await host.call_tool(
        agent_name="Agent1",
        server_name="payments",
        tool_name="refund",
        args={},
    )

    assert result == {"ok": True}
    assert client.called is True
    assert telemetry.attempts[0] == ("Agent1", "payments", "refund")
    assert telemetry.results[0][0] == "Agent1"
