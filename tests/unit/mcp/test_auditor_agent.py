import pytest
from finbot.agents_mcp.auditor_agent import MCPAuditorAgent


class FakeMCPClient:
    async def call_tool(self, server_name, tool_name, args):
        return {
            "transactions": [
                {"id": "tx1", "amount": 100},
                {"id": "tx2", "amount": 200},
            ]
        }


class FakeTelemetry:
    def __init__(self):
        self.events = []

    def record_audit(self, agent_name, incidents, score_impact):
        self.events.append((agent_name, incidents, score_impact))


@pytest.mark.asyncio
async def test_auditor_agent_runs_and_records_audit():
    telemetry = FakeTelemetry()
    agent = MCPAuditorAgent(telemetry=telemetry)

    agent.set_mcp_client(FakeMCPClient())

    await agent.run()

    assert telemetry.events
    agent_name, incidents, score = telemetry.events[0]
    assert agent_name == "AuditorAgent"
    assert isinstance(incidents, list)
    assert isinstance(score, int)
