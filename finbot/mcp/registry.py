

import os
import sys
from typing import Dict, List

class MCPRegistry:
    def __init__(self):
        self._servers: Dict[str, Dict] = {
            "payments": {
                "enabled": True,
                "command": sys.executable,
                "args": ["finbot/mock_mcp_servers/payments_mcp/server.py"],
            },
            "drive": {
                "enabled": True,
                "command": sys.executable,
                "args": ["finbot/mock_mcp_servers/drive_mcp/server.py"],
            },
        }

    def list_servers(self) -> List[str]:
        return [name for name, cfg in self._servers.items() if cfg.get("enabled")]

    def get_server(self, name: str) -> Dict:
        if name not in self._servers:
            raise KeyError(f"Server '{name}' not found")

        cfg = self._servers[name].copy()

        # Resolve absolute script path
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        cfg["args"] = [os.path.join(project_root, cfg["args"][0])]

        return cfg
