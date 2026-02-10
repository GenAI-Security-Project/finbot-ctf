from mcp.server.fastmcp import FastMCP
import os
import yaml


mcp = FastMCP("Drive")

with open(os.path.join(os.path.dirname(__file__), "vulnerabilities.yaml")) as f:
    VULNS = yaml.safe_load(f) or {}

BASE = os.path.join(os.path.dirname(__file__), "mock_data")


@mcp.tool()
def read_file(user_id: str, filename: str):
    if not VULNS.get("allow_unauthorized_read"):
        return "Error: Access denied"

    with open(os.path.join(BASE, filename)) as f:
        return f"Success: {f.read()}"


if __name__ == "__main__":
    import sys
    import asyncio

    if not sys.stdin.isatty():
        sys.stdout = sys.stderr
        asyncio.run(mcp.run_stdio_async())
    else:
        mcp.run()
