import pytest
from types import SimpleNamespace
from finbot.agents_mcp.offensive_agent import MCPOffensiveAgent



def mcp_result(text: str):
    return [SimpleNamespace(text=text)]


class FakeHost:
    async def call_tool(self, server, tool, args):
        if tool == "create_payment":
            return mcp_result(
                "Success: Payment 123e4567-e89b-12d3-a456-426614174000 created."
            )
        if tool == "refund_payment":
            return mcp_result("Success: refunded")
        if tool == "read_file":
            return mcp_result("Success: CTF{BOLA_FLAG}")
        raise RuntimeError(f"Unknown tool: {tool}")


@pytest.mark.asyncio
async def test_double_refund_exploit_success():
    agent = MCPOffensiveAgent(FakeHost())

    recon = {
        "payments": {"high_risk_tools": ["refund_payment"]},
        "drive": {"high_risk_tools": []},
    }

    results = await agent.run(recon)

    assert results["payments"]["exploits"] == ["double_refund"]


@pytest.mark.asyncio
async def test_bola_read_exploit_success():
    agent = MCPOffensiveAgent(FakeHost())

    recon = {
        "drive": {"high_risk_tools": ["read_file"]},
        "payments": {"high_risk_tools": []},
    }

    results = await agent.run(recon)

    assert results["drive"]["exploits"] == ["bola_read"]
