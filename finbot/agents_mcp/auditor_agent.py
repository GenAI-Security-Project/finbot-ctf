class MCPAuditorAgent:
    """
    Auditor agent responsible for reviewing attack results,
    determining system security status, and producing a final audit report.
    """

    def __init__(self, telemetry=None):
        """
        Initialize the auditor agent.

        Args:
            telemetry (object, optional):
                Telemetry or monitoring interface used to record audit results.
                If not provided, audit data will not be externally recorded.
        """
        self.telemetry = telemetry
        self.name = "AuditorAgent"

    async def run(self, attack_results):
        """
        Analyze attack results from offensive agents and generate
        a consolidated security audit report.

        Args:
            attack_results (dict):
                Dictionary containing exploit results per MCP server.
                Expected structure:
                {
                    "server_name": {
                        "exploits": [<exploit_identifier>, ...]
                    }
                }

        Returns:
            dict:
                Final audit report including system status, breach count,
                and critical findings.
        """

        # Initialize default audit report assuming a secure system
        report = {
            "system_status": "SECURE",
            "total_breaches": 0,
            "critical_findings": []
        }

        # Iterate through each MCP server's attack results
        for server, data in attack_results.items():
            for exploit in data.get("exploits", []):
                # Each exploit represents a confirmed security breach
                report["total_breaches"] += 1
                report["system_status"] = "COMPROMISED"

                # Classify severity based on exploit type
                report["critical_findings"].append({
                    "target": server,
                    "vulnerability": exploit,
                    "severity": "CRITICAL" if "bola" in exploit else "HIGH"
                })

        # Record audit results to telemetry system if available
        if self.telemetry:
            self.telemetry.record_audit(
                agent_name=self.name,
                incidents=report["critical_findings"],
                score_impact=report["total_breaches"]
            )

        return report
