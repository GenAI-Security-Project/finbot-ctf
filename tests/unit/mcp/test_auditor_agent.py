import pytest
from finbot.agents_mcp.auditor_agent import MCPAuditorAgent

@pytest.mark.asyncio
async def test_audit_marks_system_compromised():
    attack_results = {
        "payments": {
            "exploits": ["double_refund"]
        },
        "drive": {
            "exploits": ["bola_read"]
        }
    }

    auditor = MCPAuditorAgent()
    report = await auditor.run(attack_results)

    assert report["system_status"] == "COMPROMISED"
    assert report["total_breaches"] == 2

    severities = {f["vulnerability"]: f["severity"] for f in report["critical_findings"]}
    assert severities["bola_read"] == "CRITICAL"
    assert severities["double_refund"] == "HIGH"
