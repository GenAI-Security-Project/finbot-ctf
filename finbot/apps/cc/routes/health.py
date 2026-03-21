"""CC Health check API endpoint"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from finbot.apps.cc.health import get_all_health

router = APIRouter(prefix="/health")


@router.get("/")
async def health_check():
    """JSON health check for all platform services"""
    health = get_all_health()

    def is_ok(v):
        if isinstance(v, dict) and "status" in v:
            return v["status"] == "ok"
        if isinstance(v, dict):
            return all(is_ok(sub) for sub in v.values())
        return True

    all_ok = all(is_ok(v) for v in health.values())
    status_code = 200 if all_ok else 503

    return JSONResponse(content=health, status_code=status_code)
