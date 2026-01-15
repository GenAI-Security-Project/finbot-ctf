from mcp.server.fastmcp import FastMCP
import os
import yaml

# Initialize FastMCP server instance for the Drive service
mcp = FastMCP("Drive")

# Load vulnerability configuration flags
# These flags intentionally control insecure behavior for testing purposes
with open(os.path.join(os.path.dirname(__file__), "vulnerabilities.yaml")) as f:
    VULNS = yaml.safe_load(f) or {}

# Base directory containing mock files exposed by this MCP server
BASE = os.path.join(os.path.dirname(__file__), "mock_data")


@mcp.tool()
def read_file(user_id: str, filename: str):
    """
    Read the contents of a file from the mock drive.

    This tool intentionally simulates a Broken Object Level Authorization (BOLA)
    vulnerability when the corresponding configuration flag is enabled.

    Args:
        user_id (str):
            Identifier of the requesting user.
        filename (str):
            Name of the file to be read.

    Returns:
        str:
            Success message with file contents, or an error message
            if access is denied.
    """
    # Enforce access control unless explicitly disabled via vulnerability config
    if not VULNS.get("allow_unauthorized_read"):
        return "Error: Access denied"

    # Read and return file contents without validating ownership or permissions
    with open(os.path.join(BASE, filename)) as f:
        return f"Success: {f.read()}"


# if __name__ == "__main__":
#     """
#     Entry point for running the Drive MCP server.

#     Starts the FastMCP event loop and exposes registered tools.
#     """
#     mcp.run()


if __name__ == "__main__":
    import sys
    import asyncio

    if not sys.stdin.isatty():
        sys.stdout = sys.stderr
        asyncio.run(mcp.run_stdio_async())
    else:
        mcp.run()
