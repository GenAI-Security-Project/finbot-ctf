import json
import time
from typing import Any, Dict, List


class Telemetry:
    """
    Central telemetry collector for MCP agents.

    This component captures reconnaissance, attack execution,
    and audit results in a unified, time-ordered format.
    """

    def __init__(self):
        """
        Initialize the telemetry collector.

        Events are stored in memory and can later be
        exported for analysis or reporting.
        """
        self.events: List[Dict[str, Any]] = []

    def _emit(self, event_type: str, payload: Dict[str, Any]):
        """
        Internal helper to record a telemetry event with a timestamp.

        Args:
            event_type (str):
                Type of event (RECON, ATTACK, AUDIT).
            payload (dict):
                Structured event data.
        """
        event = {
            "timestamp": time.time(),
            "event_type": event_type,
            "payload": payload
        }
        self.events.append(event)

    # -------- Recon --------
    def record_recon(self, agent_name: str, server: str, findings: Dict[str, Any]):
        """
        Record reconnaissance findings for an MCP server.

        Args:
            agent_name (str):
                Name of the agent performing reconnaissance.
            server (str):
                Target MCP server name.
            findings (dict):
                Discovered tools and risk classification.
        """
        self._emit(
            "RECON",
            {
                "agent": agent_name,
                "server": server,
                "findings": findings
            }
        )

    # -------- Offensive --------
    def record_attack(
        self,
        agent_name: str,
        server: str,
        attack_name: str,
        success: bool,
        evidence: Any,
    ):
        """
        Record the execution and outcome of an offensive action.

        Args:
            agent_name (str):
                Name of the offensive agent.
            server (str):
                Target MCP server.
            attack_name (str):
                Identifier of the attack technique.
            success (bool):
                Whether the attack was successful.
            evidence (Any):
                Supporting evidence or response data.
        """
        self._emit(
            "ATTACK",
            {
                "agent": agent_name,
                "server": server,
                "attack": attack_name,
                "success": success,
                "evidence": evidence
            }
        )

    # -------- Audit --------
    def record_audit(
        self,
        agent_name: str,
        incidents: List[Dict[str, Any]],
        score_impact: int
    ):
        """
        Record the final audit assessment.

        Args:
            agent_name (str):
                Name of the auditing agent.
            incidents (list):
                List of confirmed security incidents.
            score_impact (int):
                Aggregate impact score or breach count.
        """
        self._emit(
            "AUDIT",
            {
                "agent": agent_name,
                "incidents": incidents,
                "score_impact": score_impact
            }
        )

    # -------- Output --------
    def dump(self) -> List[Dict[str, Any]]:
        """
        Retrieve all telemetry events currently stored in memory.

        Returns:
            list:
                Ordered list of telemetry events.
        """
        return self.events

    def dump_json(self, filepath: str):
        """
        Persist telemetry events to disk as a JSON file and
        print a high-level execution summary.

        Args:
            filepath (str):
                Destination file path for the JSON export.
        """
        total_incidents = sum(
            len(event["payload"].get("incidents", []))
            for event in self.events
            if event["event_type"] == "AUDIT"
        )

        print(f"Telemetry Exported: {len(self.events)} events captured.")
        print(f"Security Incidents Detected: {total_incidents}")

        with open(filepath, "w") as f:
            json.dump(self.events, f, indent=2)
