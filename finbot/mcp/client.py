from typing import Any, Dict, List


class MCPClient:
    """
    Scoped MCP client bound to a single agent.

    Responsible for communicating with allowed MCP servers
    and executing exposed tools. Contains no agent or policy logic.
    """

    def __init__(self, agent_name: str, allowed_servers: List[str], mcp_registry):
        self.agent_name = agent_name
        self.allowed_servers = allowed_servers
        self.registry = mcp_registry

    def _get_server(self, server_name: str):
        if server_name not in self.allowed_servers:
            raise PermissionError(
                f"Agent '{self.agent_name}' is not allowed to access "
                f"MCP server '{server_name}'"
            )

        return self.registry.get_server(server_name)

    async def list_tools(self, server_name: str) -> List[Dict[str, Any]]:
        server = self._get_server(server_name)
        return await server.list_tools()

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        args: Dict[str, Any],
    ) -> Any:
        server = self._get_server(server_name)
        return await server.call_tool(tool_name, args)
