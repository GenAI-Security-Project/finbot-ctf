"""Admin Portal API Routes -- MCP Server Configuration & Activity"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from finbot.core.auth.middleware import get_session_context
from finbot.core.auth.session import SessionContext
from finbot.core.data.database import get_db
from finbot.core.data.repositories import (
    MCPActivityLogRepository,
    MCPServerConfigRepository,
)
from finbot.mcp.servers.findrive.server import DEFAULT_CONFIG as FINDRIVE_DEFAULTS
from finbot.mcp.servers.finstripe.server import DEFAULT_CONFIG as FINSTRIPE_DEFAULTS
from finbot.mcp.servers.systemutils.server import DEFAULT_CONFIG as SYSTEMUTILS_DEFAULTS
from finbot.mcp.servers.taxcalc.server import DEFAULT_CONFIG as TAXCALC_DEFAULTS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["admin-api"])

# Default server definitions for seeding
MCP_SERVER_DEFAULTS = {
    "finstripe": {
        "display_name": "FinStripe",
        "enabled": True,
        "config": {
            **FINSTRIPE_DEFAULTS,
        },
        "description": "Mock Stripe payment processor for fund transfers to vendor accounts.",
    },
    "findrive": {
        "display_name": "FinDrive",
        "enabled": True,
        "config": {
            **FINDRIVE_DEFAULTS,
        },
        "description": "Mock Google Drive for invoice document storage. Files uploaded here can be read by agents during invoice processing -- the indirect prompt injection delivery mechanism.",
    },
    "taxcalc": {
        "display_name": "TaxCalc",
        "enabled": True,
        "config": {
            **TAXCALC_DEFAULTS,
        },
        "description": "Mock tax calculator for tax rate lookups, calculations, and TIN validation.",
    },
    "systemutils": {
        "display_name": "SystemUtils",
        "enabled": False,
        "config": {
            **SYSTEMUTILS_DEFAULTS,
        },
        "description": "System diagnostic and maintenance tools. Sandboxed -- records attempted commands but executes nothing. Enable for CTF RCE challenges.",
    },
}


class ServerConfigUpdate(BaseModel):
    config: dict


class ToolOverridesUpdate(BaseModel):
    tool_overrides: dict


# =============================================================================
# MCP Server Config endpoints
# =============================================================================


@router.get("/mcp/servers")
async def list_mcp_servers(
    session_context: SessionContext = Depends(get_session_context),
):
    """List all MCP server configs for this namespace, seeding defaults if needed."""
    db = next(get_db())
    repo = MCPServerConfigRepository(db, session_context)

    configs = repo.list_all()
    existing = {c.server_type: c for c in configs}

    for server_type, defaults in MCP_SERVER_DEFAULTS.items():
        existing_config = existing.get(server_type)
        if not existing_config:
            repo.upsert(
                server_type=server_type,
                display_name=defaults["display_name"],
                enabled=defaults["enabled"],
                config_json=json.dumps(defaults["config"]),
            )
        elif not existing_config.get_config() and defaults.get("config"):
            repo.upsert(
                server_type=server_type,
                display_name=defaults["display_name"],
                enabled=defaults["enabled"],
                config_json=json.dumps(defaults["config"]),
            )

    configs = repo.list_all()

    servers = []
    for config in configs:
        server_data = config.to_dict()
        defaults = MCP_SERVER_DEFAULTS.get(config.server_type, {})
        server_data["description"] = defaults.get("description", "")
        servers.append(server_data)

    return {"servers": servers}


@router.get("/mcp/servers/{server_type}")
async def get_mcp_server(
    server_type: str,
    session_context: SessionContext = Depends(get_session_context),
):
    """Get config for a specific MCP server."""
    db = next(get_db())
    repo = MCPServerConfigRepository(db, session_context)

    config = repo.get_by_type(server_type)
    if not config:
        if server_type in MCP_SERVER_DEFAULTS:
            defaults = MCP_SERVER_DEFAULTS[server_type]
            config = repo.upsert(
                server_type=server_type,
                display_name=defaults["display_name"],
                enabled=defaults["enabled"],
                config_json=json.dumps(defaults["config"]),
            )
        else:
            raise HTTPException(status_code=404, detail="MCP server not found")

    server_data = config.to_dict()
    defaults = MCP_SERVER_DEFAULTS.get(server_type, {})
    server_data["description"] = defaults.get("description", "")

    default_tools = await _get_default_tool_definitions(server_type)
    server_data["default_tools"] = default_tools

    return {"server": server_data}


@router.put("/mcp/servers/{server_type}")
async def update_mcp_server_config(
    server_type: str,
    update: ServerConfigUpdate,
    session_context: SessionContext = Depends(get_session_context),
):
    """Update server-specific settings (payment limits, mock balance, etc.)."""
    db = next(get_db())
    repo = MCPServerConfigRepository(db, session_context)

    config = repo.update_config(server_type, json.dumps(update.config))
    if not config:
        raise HTTPException(status_code=404, detail="MCP server not found")

    return {"success": True, "server": config.to_dict()}


@router.put("/mcp/servers/{server_type}/tools")
async def update_tool_overrides(
    server_type: str,
    update: ToolOverridesUpdate,
    session_context: SessionContext = Depends(get_session_context),
):
    """Update tool definition overrides (the CTF supply chain attack surface)."""
    db = next(get_db())
    repo = MCPServerConfigRepository(db, session_context)

    config = repo.update_tool_overrides(server_type, json.dumps(update.tool_overrides))
    if not config:
        raise HTTPException(status_code=404, detail="MCP server not found")

    logger.info(
        "Tool overrides updated for '%s' in namespace '%s': %d tools modified",
        server_type,
        session_context.namespace,
        len(update.tool_overrides),
    )

    return {"success": True, "server": config.to_dict()}


@router.post("/mcp/servers/{server_type}/reset-tools")
async def reset_tool_overrides(
    server_type: str,
    session_context: SessionContext = Depends(get_session_context),
):
    """Reset tool overrides to defaults (remove all user modifications)."""
    db = next(get_db())
    repo = MCPServerConfigRepository(db, session_context)

    config = repo.reset_tool_overrides(server_type)
    if not config:
        raise HTTPException(status_code=404, detail="MCP server not found")

    return {"success": True, "server": config.to_dict()}


@router.put("/mcp/servers/{server_type}/toggle")
async def toggle_mcp_server(
    server_type: str,
    session_context: SessionContext = Depends(get_session_context),
):
    """Enable/disable an MCP server."""
    db = next(get_db())
    repo = MCPServerConfigRepository(db, session_context)

    config = repo.toggle_enabled(server_type)
    if not config:
        raise HTTPException(status_code=404, detail="MCP server not found")

    return {"success": True, "server": config.to_dict()}


# =============================================================================
# MCP Activity Log endpoints
# =============================================================================


@router.get("/mcp/activity")
async def list_mcp_activity(
    server_type: str | None = None,
    workflow_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
    session_context: SessionContext = Depends(get_session_context),
):
    """List MCP activity log entries."""
    db = next(get_db())
    repo = MCPActivityLogRepository(db, session_context)

    entries = repo.list_activity(
        server_type=server_type,
        workflow_id=workflow_id,
        limit=limit,
        offset=offset,
    )
    total = repo.get_activity_count(server_type=server_type)

    return {
        "entries": [e.to_dict() for e in entries],
        "total_count": total,
    }


# =============================================================================
# Helpers
# =============================================================================


def _make_dummy_session_context():
    """Create a minimal SessionContext for server introspection."""
    from datetime import UTC, datetime

    from finbot.core.auth.session import SessionContext as SC

    return SC(
        session_id="",
        user_id="",
        namespace="__introspect__",
        is_temporary=True,
        csrf_token="",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC),
    )


_SERVER_INTROSPECTORS = {
    "finstripe": "finbot.mcp.servers.finstripe.server.create_finstripe_server",
    "taxcalc": "finbot.mcp.servers.taxcalc.server.create_taxcalc_server",
    "systemutils": "finbot.mcp.servers.systemutils.server.create_systemutils_server",
    "findrive": "finbot.mcp.servers.findrive.server.create_findrive_server",
}


async def _get_default_tool_definitions(server_type: str) -> list[dict]:
    """Get the default tool definitions for a server type by introspecting the FastMCP server."""
    factory_path = _SERVER_INTROSPECTORS.get(server_type)
    if not factory_path:
        return []

    try:
        import importlib

        module_path, func_name = factory_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        factory_fn = getattr(module, func_name)

        dummy_ctx = _make_dummy_session_context()
        server = factory_fn(dummy_ctx)
        server_tools = await server.list_tools()

        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.parameters if hasattr(tool, "parameters") else {},
            }
            for tool in server_tools
        ]
    except Exception:
        logger.debug("Failed to introspect %s tools", server_type, exc_info=True)
    return []
