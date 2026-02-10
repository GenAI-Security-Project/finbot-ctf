from finbot.agents_mcp.base_mcp_agent import BaseMCPAgent


class MCPAuditorAgent(BaseMCPAgent):
    """
    Auditor agent responsible for validating security incidents
    discovered during reconnaissance and offensive phases.
    """

    def __init__(self, telemetry=None):
        super().__init__("AuditorAgent", telemetry)
        
        # Define the limited scope of servers this agent is permitted to access
        self.required_mcp_servers = ["payments"]

    async def run(self):
        """
        Executes audit checks against the payments server to detect 
        unauthorized financial activity like suspicious refunds.
        """
        if not self.mcp:
            raise RuntimeError("MCP client not initialized for AuditorAgent")

        incidents = []

        try:
            # Query the payments server for transaction history
            result = await self.mcp.call_tool(
                server_name="payments",
                tool_name="list_transactions",
                args={},
            )

            text = self._extract_text(result)

            # Heuristic check: Flag results that indicate potential exploit success
            if "refund" in text.lower():
                incidents.append(
                    {"issue": "Suspicious refund activity detected"}
                )

        except Exception as e:
            incidents.append(
                {"issue": "Audit execution failed", "error": str(e)}
            )

        if self.telemetry:
            self.telemetry.record_audit(
                agent_name=self.name,
                incidents=incidents,
                score_impact=len(incidents),
            )