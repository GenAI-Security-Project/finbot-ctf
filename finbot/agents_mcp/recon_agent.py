class MCPReconAgent:
    """
    Reconnaissance agent responsible for enumerating MCP server
    attack surfaces and identifying potentially high-risk tools.

    This agent performs passive analysis only and does not
    execute any offensive actions.
    """

    def __init__(self, mcp_host, telemetry=None):
        """
        Initialize the reconnaissance agent.

        Args:
            mcp_host (object):
                MCP host containing registered MCP servers.
            telemetry (object, optional):
                Telemetry interface for recording reconnaissance findings.
        """
        self.mcp = mcp_host
        self.telemetry = telemetry
        self.name = "ReconAgent"

    async def run(self):
        """
        Enumerate all MCP servers and their exposed tools,
        classifying tools that may present higher security risk.

        Returns:
            dict:
                Reconnaissance surface map with discovered tools
                and high-risk classifications per server.
        """
        surface_map = {}

        # Iterate through all registered MCP servers
        for server_name, server in self.mcp.servers.items():
            surface_map[server_name] = {
                "tools": [],
                "high_risk_tools": []
            }

            # Retrieve the list of tools exposed by the MCP server
            tools = await server.list_tools()

            for tool in tools:
                # Normalize tool metadata
                tool_data = {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": list(
                        tool.inputSchema.get("properties", {}).keys()
                    )
                }

                surface_map[server_name]["tools"].append(tool_data)

                # Heuristic keyword-based risk classification
                risk_keywords = [
                    "refund", "confirm", "delete",
                    "read", "share", "admin", "transfer"
                ]

                if any(keyword in tool.name.lower() for keyword in risk_keywords):
                    surface_map[server_name]["high_risk_tools"].append(tool.name)

            # Record reconnaissance findings in telemetry system if available
            if self.telemetry:
                self.telemetry.record_recon(
                    agent_name=self.name,
                    server=server_name,
                    findings=surface_map[server_name]
                )

        return surface_map
