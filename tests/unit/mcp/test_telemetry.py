
import os
from finbot.mcp.telemetry import Telemetry

def test_telemetry_records_events(tmp_path):
    telemetry = Telemetry()

    telemetry.record_recon("ReconAgent", "payments", {"tools": []})
    telemetry.record_attack("OffensiveAgent", "payments", "double_refund", True, {})
    telemetry.record_audit("AuditorAgent", [{"x": 1}], 100)

    assert len(telemetry.events) == 3

    output = tmp_path / "telemetry.json"
    telemetry.dump_json(output)

    assert output.exists()
