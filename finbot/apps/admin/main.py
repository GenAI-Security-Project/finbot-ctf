"""Admin Portal Main Application"""

from fastapi import FastAPI

from finbot.config import settings

from .routes import api_router, web_router

app = FastAPI(
    title="FinBot Admin Portal",
    description="FinBot Admin Portal - MCP Server Management & Configuration",
    version="0.1.0",
    debug=settings.DEBUG,
)

app.include_router(web_router)
app.include_router(api_router)
