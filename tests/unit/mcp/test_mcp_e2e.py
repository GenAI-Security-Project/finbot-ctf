import pytest
from finbot.mcp_runtime.orchestrator import run_ctf_scenario

@pytest.mark.asyncio
async def test_mcp_end_to_end_execution(tmp_path):
    report_path = tmp_path / "ctf_report.json"

    result = await run_ctf_scenario(report_path=str(report_path))

    assert result["status"] == "completed"
    assert len(result["events"]) > 0
    assert report_path.exists()

    event_types = {e["event_type"] for e in result["events"]}
    assert "RECON" in event_types
    assert "ATTACK" in event_types
    assert "AUDIT" in event_types