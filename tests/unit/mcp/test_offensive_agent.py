import pytest
from finbot.agents_mcp.offensive_agent import MCPOffensiveAgent


class FakeMCPClient:
    def __init__(self):
        self.calls = []

    async def call_tool(self, server_name, tool_name, args):
        self.calls.append((server_name, tool_name, args))
        return {"status": "success"}


class FakeTelemetry:
    def __init__(self):
        self.events = []

    def record_attack(self, agent_name, server, attack_name, success, evidence):
        self.events.append(
            (agent_name, server, attack_name, success, evidence)
        )


@pytest.mark.asyncio
async def test_offensive_agent_executes_attack():
    telemetry = FakeTelemetry()
    agent = MCPOffensiveAgent(telemetry=telemetry)

    agent.set_mcp_client(FakeMCPClient())

    await agent.run()

    assert agent.mcp.calls
    assert agent.mcp.calls[0][0] == "payments"
    assert telemetry.events
