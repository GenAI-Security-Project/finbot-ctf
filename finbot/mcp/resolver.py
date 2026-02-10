import logging
from typing import List

from finbot.mcp.registry import MCPRegistry
from finbot.mcp.host import MCPHost
from finbot.mcp.client import MCPClient


class AgentToolRegistrationResolver:
    """
    Resolves agent-declared MCP dependencies into scoped MCP clients
    registered with the MCP host.
    """

    def __init__(self, mcp_registry: MCPRegistry, mcp_host: MCPHost):
        self.mcp_registry = mcp_registry
        self.mcp_host = mcp_host
        self.logger = logging.getLogger("AgentToolRegistrationResolver")

    def resolve(self, agent) -> None:
        agent_name = agent.name

        required_servers: List[str] = getattr(
            agent, "required_mcp_servers", []
        )

        if not required_servers:
            self.logger.info(
                f"Agent '{agent_name}' declares no MCP dependencies"
            )
            return

        self.logger.info(
            f"Resolving MCP servers for agent '{agent_name}': "
            f"{required_servers}"
        )

        for server_name in required_servers:
            if not self.mcp_registry.has_server(server_name):
                raise ValueError(
                    f"Agent '{agent_name}' requires unknown MCP server "
                    f"'{server_name}'"
                )

        mcp_client = MCPClient(
            agent_name=agent_name,
            allowed_servers=required_servers,
            mcp_registry=self.mcp_registry,
        )

        self.mcp_host.register_agent_client(
            agent_name=agent_name,
            mcp_client=mcp_client,
        )

        agent.set_mcp_client(mcp_client)

        self.logger.info(
            f"MCP resolution complete for agent '{agent_name}'"
        )

    def resolve_all(self, agents: List) -> None:
        for agent in agents:
            self.resolve(agent)
