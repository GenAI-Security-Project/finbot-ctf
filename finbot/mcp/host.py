import logging


class MCPHost:
    """
    Central MCP authority responsible for routing tool calls
    through per-agent scoped MCP clients.
    """

    def __init__(self, telemetry=None):
        self._agent_clients = {}
        self.telemetry = telemetry
        self.logger = logging.getLogger("MCPHost")

    def register_agent_client(self, agent_name: str, mcp_client) -> None:
        self._agent_clients[agent_name] = mcp_client
        self.logger.info(f"Registered MCP client for agent '{agent_name}'")

    async def call_tool(
        self,
        agent_name: str,
        server_name: str,
        tool_name: str,
        args: dict,
    ):
        if agent_name not in self._agent_clients:
            raise PermissionError(
                f"Agent '{agent_name}' is not registered with MCPHost"
            )

        mcp_client = self._agent_clients[agent_name]

        if self.telemetry:
            try:
                self.telemetry.record_call_attempt(
                    agent=agent_name,
                    server=server_name,
                    tool=tool_name,
                )
            except Exception:
                pass

        result = await mcp_client.call_tool(
            server_name=server_name,
            tool_name=tool_name,
            args=args,
        )

        if self.telemetry:
            try:
                self.telemetry.record_call_result(
                    agent=agent_name,
                    server=server_name,
                    tool=tool_name,
                    result=result,
                )
            except Exception:
                pass

        return result

    def has_agent(self, agent_name: str) -> bool:
        return agent_name in self._agent_clients

    def unregister_agent(self, agent_name: str) -> None:
        if agent_name in self._agent_clients:
            del self._agent_clients[agent_name]
            self.logger.info(f"Unregistered MCP client for agent '{agent_name}'")
