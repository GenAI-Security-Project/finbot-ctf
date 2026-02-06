"""CTF Portal FastAPI Application"""

from fastapi import FastAPI

from finbot.apps.ctf.routes import (
    activity,
    admin,
    badges,
    challenges,
    sidecar,
    stats,
    web_router,
)

ctf_app = FastAPI(
    title="FinBot CTF API",
    description="Capture The Flag Portal API",
    version="1.0.0",
)

# Include web routes (page routes)
ctf_app.include_router(web_router)

# Include API routers
ctf_app.include_router(challenges.router)
ctf_app.include_router(badges.router)
ctf_app.include_router(activity.router)
ctf_app.include_router(stats.router)
ctf_app.include_router(admin.router)
ctf_app.include_router(sidecar.router)
