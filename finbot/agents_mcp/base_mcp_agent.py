import re
from typing import Any, Dict, Optional


class BaseMCPAgent:
    """
    Base class for all MCP-enabled agents within the FinBot framework.

    This class implements the 'Scoped Dependency Injection' pattern. Agents 
    do not manage MCP connections themselves; instead, they operate on a 
    pre-configured MCPClient injected by the framework's Resolver.
    """

    def __init__(self, name: str, telemetry: Optional[Any] = None):
        """
        Initialize the base agent.

        Args:
            name: Unique identifier for the agent.
            telemetry: Optional telemetry instance for logging activity.
        """
        self.name = name
        self.telemetry = telemetry
        
        # Subclasses must populate this to request server access
        self.required_mcp_servers = []
        
        # Injected at runtime by AgentToolRegistrationResolver
        self.mcp = None

    def set_mcp_client(self, mcp_client):
        """Injects a scoped MCP client into the agent."""
        self.mcp = mcp_client

    async def call_tool(self, server: str, tool: str, args: Dict[str, Any]):
        """
        Invoke a tool on a specific MCP server.
        
        Raises:
            RuntimeError: If the agent is executed before its MCP client is injected.
        """
        if not self.mcp:
            raise RuntimeError(
                f"MCP client not initialized for agent '{self.name}'. "
                "Ensure the agent is registered with the Resolver."
            )

        return await self.mcp.call_tool(server, tool, args)

    # ---------- Response Parsing Helpers ----------

    def _extract_text(self, result: Any) -> str:
        """Helper to extract raw text from diverse MCP tool response formats."""
        if not result:
            return ""

        item = result[0]

        if hasattr(item, "text"):
            return item.text

        if isinstance(item, str):
            return item

        return str(item)

    def _extract_uuid(self, text: str) -> Optional[str]:
        """Helper to identify UUIDs within tool output text."""
        if not isinstance(text, str):
            return None

        match = re.search(r"[0-9a-fA-F-]{36}", text)
        return match.group(0) if match else None

    def _is_success(self, text: str) -> bool:
        """Standardized check for 'Success' prefix in tool responses."""
        return isinstance(text, str) and text.startswith("Success")