import pytest
from finbot.agents_mcp.recon_agent import MCPReconAgent


class FakeTool:
    def __init__(self, name, description, input_schema):
        self.name = name
        self.description = description
        self.inputSchema = input_schema


class FakeMCPClient:
    async def list_tools(self, server_name):
        return [
            FakeTool(
                name="refund_payment",
                description="Refund a payment",
                input_schema={
                    "properties": {
                        "payment_id": {"type": "string"}
                    }
                },
            ),
            FakeTool(
                name="list_transactions",
                description="List transactions",
                input_schema={"properties": {}},
            ),
        ]


class FakeTelemetry:
    def __init__(self):
        self.events = []

    def record_recon(self, agent_name, server, findings):
        self.events.append((agent_name, server, findings))


@pytest.mark.asyncio
async def test_recon_agent_discovers_tools_and_risk():
    telemetry = FakeTelemetry()
    agent = MCPReconAgent(telemetry=telemetry)

    agent.set_mcp_client(FakeMCPClient())

    result = await agent.run()

    assert "payments" in result
    assert len(result["payments"]["tools"]) == 2
    assert "refund_payment" in result["payments"]["high_risk_tools"]
    assert telemetry.events
