import re


class BaseMCPAgent:
    """
    Base class for all MCP agents.

    Provides shared utilities for interacting with MCP servers,
    invoking tools, and safely extracting structured information
    from tool responses.
    """

    def __init__(self, mcp_host, name, telemetry=None):
        """
        Initialize the base MCP agent.

        Args:
            mcp_host (object):
                MCP host instance responsible for tool invocation.
            name (str):
                Logical name of the agent.
            telemetry (object, optional):
                Telemetry or monitoring interface for recording agent activity.
        """
        self.mcp = mcp_host
        self.name = name
        self.telemetry = telemetry

    async def call_tool(self, server, tool, args):
        """
        Invoke a tool exposed by a specific MCP server.

        Args:
            server (str):
                Target MCP server name.
            tool (str):
                Tool identifier to be executed.
            args (dict):
                Arguments to be passed to the tool.

        Returns:
            Any:
                Raw result returned by the MCP tool invocation.
        """
        return await self.mcp.call_tool(server, tool, args)

    def _extract_text(self, result):
        """
        Safely extract textual content from MCP tool responses.

        MCP tools may return a list of TextContent objects or
        plain strings. This method normalizes the output into text.

        Args:
            result (list | None):
                Tool response payload.

        Returns:
            str:
                Extracted textual content or an empty string if unavailable.
        """
        if not result:
            return ""

        item = result[0]

        # FastMCP TextContent object
        if hasattr(item, "text"):
            return item.text

        # Fallback for plain string responses
        if isinstance(item, str):
            return item

        # Last-resort conversion
        return str(item)

    def _extract_uuid(self, text):
        """
        Extract a UUID from the given text, if present.

        Args:
            text (str):
                Input string potentially containing a UUID.

        Returns:
            str | None:
                Extracted UUID string or None if not found.
        """
        if not isinstance(text, str):
            return None

        match = re.search(r"[0-9a-fA-F-]{36}", text)
        return match.group(0) if match else None

    def _is_success(self, text):
        """
        Determine whether a tool response indicates success.

        Args:
            text (str):
                Tool response text.

        Returns:
            bool:
                True if the response indicates success, otherwise False.
        """
        return isinstance(text, str) and text.startswith("Success")
