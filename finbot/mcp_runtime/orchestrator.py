import asyncio

from finbot.mcp.registry import MCPRegistry
from finbot.mcp.host import MCPHost
from finbot.mcp.telemetry import Telemetry
from finbot.mcp.resolver import AgentToolRegistrationResolver

from finbot.agents_mcp.recon_agent import MCPReconAgent
from finbot.agents_mcp.offensive_agent import MCPOffensiveAgent
from finbot.agents_mcp.auditor_agent import MCPAuditorAgent

from finbot.mock_mcp_servers.payments_mcp.server import mcp as payments_mcp
from finbot.mock_mcp_servers.drive_mcp.server import mcp as drive_mcp


async def run_ctf_scenario(report_path: str = "ctf_report.json"):
    telemetry = Telemetry()
    registry = MCPRegistry()
    host = MCPHost(telemetry=telemetry)

    registry.register_server("payments", payments_mcp)
    registry.register_server("drive", drive_mcp)

    recon_agent = MCPReconAgent(telemetry=telemetry)
    offensive_agent = MCPOffensiveAgent(telemetry=telemetry)
    auditor_agent = MCPAuditorAgent(telemetry=telemetry)

    agents = [
        recon_agent,
        offensive_agent,
        auditor_agent,
    ]

    resolver = AgentToolRegistrationResolver(
        mcp_registry=registry,
        mcp_host=host,
    )
    resolver.resolve_all(agents)

    recon_results = await recon_agent.run()
    await offensive_agent.run()
    await auditor_agent.run()

    telemetry.dump_json(report_path)

    return {
        "status": "completed",
        "recon": recon_results,
        "events": telemetry.dump(),
    }


if __name__ == "__main__":
    asyncio.run(run_ctf_scenario())
