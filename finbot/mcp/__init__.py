"""FinBot MCP Integration Layer

Provides reusable infrastructure for connecting agents to MCP servers:
- MCPToolProvider: discovers tools from MCP servers and bridges them to the agent loop
- Server Factory: creates ephemeral, namespace-scoped MCP server instances
- MCP Servers: mock external services (FinStripe, GDrive, TaxCalc)
"""
