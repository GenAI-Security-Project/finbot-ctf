from finbot.agents_mcp.base_mcp_agent import BaseMCPAgent


class MCPOffensiveAgent(BaseMCPAgent):
    """
    Offensive agent responsible for exploiting high-risk MCP tools.

    This agent executes active attacks against permitted MCP servers to 
    demonstrate vulnerabilities like unauthorized refunds or data exfiltration.
    """

    def __init__(self, telemetry=None):
        super().__init__("OffensiveAgent", telemetry)
        
        # Define the broad scope required for cross-server exploitation
        self.required_mcp_servers = ["payments", "drive"]

    async def run(self):
        """
        Executes an attack sequence against configured MCP servers.
        Currently focuses on unauthorized refund attempts on the payments server.
        """
        if not self.mcp:
            raise RuntimeError("MCP client not initialized for OffensiveAgent")

        try:
            # Attempt an unauthorized refund exploit
            result = await self.mcp.call_tool(
                server_name="payments",
                tool_name="refund_payment",
                args={"payment_id": "test-payment"},
            )

            text = self._extract_text(result)
            success = self._is_success(text)

        except Exception as e:
            # Capture the error as evidence of a blocked attack
            text = str(e)
            success = False

        if self.telemetry:
            self.telemetry.record_attack(
                agent_name=self.name,
                server="payments",
                attack_name="unauthorized_refund",
                success=success,
                evidence=text,
            )