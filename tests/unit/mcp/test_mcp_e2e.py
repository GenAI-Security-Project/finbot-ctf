import asyncio
import os
import sys

# Ensure project root is available in the Python path
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../")
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from finbot.mcp.host import MCPHost
from finbot.agents_mcp.recon_agent import MCPReconAgent
from finbot.agents_mcp.offensive_agent import MCPOffensiveAgent
from finbot.agents_mcp.auditor_agent import MCPAuditorAgent
from finbot.mcp.telemetry import Telemetry

from finbot.mock_mcp_servers.payments_mcp.server import mcp as payments
from finbot.mock_mcp_servers.drive_mcp.server import mcp as drive


async def test_mcp_end_to_end():
    print("Starting MCP end-to-end test (Embedded FastMCP mode)")

    # --------------------
    # Initialization
    # --------------------
    host = MCPHost()
    telemetry = Telemetry()

    # --------------------
    # Register MCP servers (embedded mode)
    # --------------------
    host.servers["payments"] = payments
    host.servers["drive"] = drive

    print("Loaded MCP servers: ['payments', 'drive']")

    # --------------------
    # Reconnaissance phase
    # --------------------
    print("\nRunning Recon Agent...")
    recon = MCPReconAgent(host)
    recon_results = await recon.run()

    for server, findings in recon_results.items():
        telemetry.record_recon(
            agent_name="ReconAgent",
            server=server,
            findings=findings
        )

    # --------------------
    # Offensive phase
    # --------------------
    print("\nRunning Offensive Agent...")
    attacker = MCPOffensiveAgent(host)
    attack_results = await attacker.run(recon_results)

    for server, data in attack_results.items():
        for attack in data.get("attacks", []):
            telemetry.record_attack(
                agent_name="OffensiveAgent",
                server=server,
                attack_name=attack["attack"],
                success=attack["success"],
                evidence=attack.get("evidence"),
            )

    # --------------------
    # Audit phase
    # --------------------
    print("\nRunning Auditor Agent...")
    auditor = MCPAuditorAgent()
    audit_report = await auditor.run(attack_results)

    telemetry.record_audit(
        agent_name="AuditorAgent",
        incidents=audit_report["critical_findings"],
        score_impact=audit_report["total_breaches"] * 100,
    )

    # --------------------
    # Output
    # --------------------
    telemetry.dump_json("ctf_report.json")

    print("\nFinal audit report")
    print(audit_report)

    print("\nMCP end-to-end test complete")


if __name__ == "__main__":
    asyncio.run(test_mcp_end_to_end())
