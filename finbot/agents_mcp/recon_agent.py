from finbot.agents_mcp.base_mcp_agent import BaseMCPAgent


class MCPReconAgent(BaseMCPAgent):
    """
    Reconnaissance agent responsible for enumerating MCP server
    attack surfaces and identifying potentially high-risk tools.
    """

    def __init__(self, telemetry=None):
        super().__init__("ReconAgent", telemetry)
        
        # Define the scope of servers the agent is authorized to scan
        self.required_mcp_servers = ["payments", "drive"]

    async def run(self):
        """
        Enumerates tools from authorized MCP servers and classifies 
        them based on potential security risk.
        """
        if not self.mcp:
            raise RuntimeError("MCP client not initialized for ReconAgent")

        surface_map = {}

        for server_name in self.required_mcp_servers:
            surface_map[server_name] = {
                "tools": [],
                "high_risk_tools": [],
            }

            try:
                # Query the MCP server for its available toolset
                tools = await self.mcp.list_tools(server_name)
            except Exception as e:
                # Log the error but allow recon to continue for other servers
                surface_map[server_name]["error"] = str(e)
                continue

            for tool in tools:
                # Normalize tool metadata for uniform reporting
                tool_name = tool.name
                description = tool.description or ""
                input_schema = tool.inputSchema or {}

                tool_data = {
                    "name": tool_name,
                    "description": description,
                    "parameters": list(
                        input_schema.get("properties", {}).keys()
                    ),
                }

                surface_map[server_name]["tools"].append(tool_data)

                # Identify sensitive tools that could be abused in a CTF scenario
                risk_keywords = [
                    "refund", "confirm", "delete",
                    "read", "share", "admin", "transfer",
                ]

                if any(
                    keyword in tool_name.lower()
                    for keyword in risk_keywords
                ):
                    surface_map[server_name]["high_risk_tools"].append(tool_name)

            # Log findings to telemetry for global reporting
            if self.telemetry:
                self.telemetry.record_recon(
                    agent_name=self.name,
                    server=server_name,
                    findings=surface_map[server_name],
                )

        return surface_map