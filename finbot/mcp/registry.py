from typing import Dict, Any


class MCPRegistry:
    """
    In-memory registry for MCP servers and their configuration.
    """

    def __init__(self):
        self._servers: Dict[str, Dict[str, Any]] = {}

    def register_server(self, name: str, config: Dict[str, Any]) -> None:
        self._servers[name] = config

    def has_server(self, name: str) -> bool:
        return name in self._servers

    def get_server(self, name: str) -> Dict[str, Any]:
        if name not in self._servers:
            raise KeyError(f"MCP server '{name}' not registered")
        return self._servers[name]

    def list_servers(self):
        return list(self._servers.keys())
