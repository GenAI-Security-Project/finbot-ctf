import pytest
from finbot.agents_mcp.recon_agent import MCPReconAgent

class FakeTool:
    def __init__(self, name):
        self.name = name
        self.description = "test"
        self.inputSchema = {"properties": {}}

class FakeServer:
    async def list_tools(self):
        return [
            FakeTool("refund_payment"),
            FakeTool("read_file"),
            FakeTool("health_check")
        ]

class FakeHost:
    servers = {"payments": FakeServer(), "drive": FakeServer()}

@pytest.mark.asyncio
async def test_recon_detects_high_risk_tools():
    agent = MCPReconAgent(FakeHost())
    results = await agent.run()

    assert "refund_payment" in results["payments"]["high_risk_tools"]
    assert "read_file" in results["drive"]["high_risk_tools"]
