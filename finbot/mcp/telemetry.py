import json
import os
import time
from typing import Any, Dict, List


_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REPORT_DIR = os.path.dirname(_CURRENT_DIR)


class Telemetry:
    """
    Central telemetry collector for MCP agents.
    Designed to be non-intrusive and never affect execution flow.
    """

    def __init__(self):
        self.events: List[Dict[str, Any]] = []

    def _emit(self, event_type: str, payload: Dict[str, Any]):
        try:
            event = {
                "timestamp": time.time(),
                "event_type": event_type,
                "payload": payload,
            }
            self.events.append(event)
        except Exception:
            pass

    def dump(self) -> List[Dict[str, Any]]:
        return self.events

    def record_call_attempt(self, agent: str, server: str, tool: str):
        self._emit(
            "CALL_ATTEMPT",
            {"agent": agent, "server": server, "tool": tool},
        )

    def record_call_result(
        self,
        agent: str,
        server: str,
        tool: str,
        result: Any,
    ):
        self._emit(
            "CALL_RESULT",
            {
                "agent": agent,
                "server": server,
                "tool": tool,
                "result": str(result),
            },
        )

    def record_recon(
        self,
        agent_name: str,
        server: str,
        findings: Dict[str, Any],
    ):
        self._emit(
            "RECON",
            {"agent": agent_name, "server": server, "findings": findings},
        )

    def record_attack(
        self,
        agent_name: str,
        server: str,
        attack_name: str,
        success: bool,
        evidence: Any,
    ):
        self._emit(
            "ATTACK",
            {
                "agent": agent_name,
                "server": server,
                "attack": attack_name,
                "success": success,
                "evidence": str(evidence),
            },
        )

    def record_audit(
        self,
        agent_name: str,
        incidents: List[Dict[str, Any]],
        score_impact: int,
    ):
        self._emit(
            "AUDIT",
            {
                "agent": agent_name,
                "incidents": incidents,
                "score_impact": score_impact,
            },
        )

    def dump_json(self, filepath: str = "ctf_report.json"):
        try:
            if not os.path.dirname(filepath):
                target_path = os.path.join(DEFAULT_REPORT_DIR, filepath)
            else:
                target_path = filepath

            total_incidents = sum(
                len(event["payload"].get("incidents", []))
                for event in self.events
                if event["event_type"] == "AUDIT"
            )

            os.makedirs(
                os.path.dirname(os.path.abspath(target_path)),
                exist_ok=True,
            )

            with open(target_path, "w") as f:
                json.dump(self.events, f, indent=2)

            print(f"Telemetry successfully exported to: {target_path}")
            print(f"Security Incidents Detected: {total_incidents}")

        except Exception as e:
            print(f"Failed to export telemetry: {e}")
