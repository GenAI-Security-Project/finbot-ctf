from finbot.core.auth import session


class MCPHost:
    """
    Central registry and execution layer for MCP servers.

    This class acts as the coordination point between agents
    and individual MCP servers, abstracting server lookup
    and tool invocation.
    """

    def __init__(self):
        """
        Initialize the MCP host.

        Maintains an in-memory registry of MCP servers
        indexed by logical server name.
        """
        self.servers = {}

    def register(self, name: str, server):
        """
        Register an MCP server with the host.

        Args:
            name (str):
                Logical name used by agents to reference the server.
            server (object):
                MCP server instance exposing callable tools.
        """
        self.servers[name] = session

    async def call_tool(self, server_name: str, tool_name: str, args: dict):
        """
        Invoke a tool on a registered MCP server.

        Args:
            server_name (str):
                Name of the registered MCP server.
            tool_name (str):
                Tool identifier to execute on the server.
            args (dict):
                Arguments to pass to the tool.

        Returns:
            Any:
                Raw result returned by the MCP server tool.
        """
        return await self.servers[server_name].call_tool(tool_name, args)
