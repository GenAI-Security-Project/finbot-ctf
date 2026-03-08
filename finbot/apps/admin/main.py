"""Admin Portal Main Application"""

from fastapi import FastAPI

from finbot.config import settings
from finbot.core.error_handlers import register_error_handlers

from .routes import api_router, web_router

app = FastAPI(
    title="FinBot Admin Portal",
    description="FinBot Admin Portal - MCP Server Management & Configuration",
    version="0.1.0",
    debug=settings.DEBUG,
)

register_error_handlers(app)

app.include_router(web_router)
app.include_router(api_router)
