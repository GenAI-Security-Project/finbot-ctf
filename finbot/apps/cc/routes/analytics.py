"""CC Analytics dashboard routes"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from finbot.core.analytics.queries import (
    get_auth_funnel,
    get_browser_breakdown,
    get_daily_pageviews,
    get_device_breakdown,
    get_pageviews_count,
    get_referer_breakdown,
    get_response_time_avg,
    get_top_pages,
    get_total_pageviews,
    get_unique_visitors,
)
from finbot.core.data.database import SessionLocal
from finbot.core.templates import TemplateResponse

template_response = TemplateResponse("finbot/apps/cc/templates")

router = APIRouter(prefix="/analytics")


@router.get("/", response_class=HTMLResponse)
async def analytics_dashboard(request: Request):
    """Analytics overview dashboard"""
    db = SessionLocal()
    try:
        data = {
            "pageviews_7d": get_pageviews_count(db, days=7),
            "pageviews_30d": get_pageviews_count(db, days=30),
            "visitors_7d": get_unique_visitors(db, days=7),
            "visitors_30d": get_unique_visitors(db, days=30),
            "total_pageviews": get_total_pageviews(db),
            "top_pages": get_top_pages(db, days=7, limit=10),
            "browsers": get_browser_breakdown(db, days=7),
            "devices": get_device_breakdown(db, days=7),
            "referers": get_referer_breakdown(db, days=7, limit=8),
            "daily": get_daily_pageviews(db, days=30),
            "funnel": get_auth_funnel(db, days=7),
            "avg_response_ms": get_response_time_avg(db, days=7),
        }
    finally:
        db.close()

    return template_response(request, "pages/analytics.html", data)
