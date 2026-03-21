"""Reusable analytics query functions for both public stats and CC dashboard"""

# pylint: disable=not-callable

from datetime import UTC, datetime, timedelta

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from .models import PageView


def get_pageviews_count(db: Session, days: int = 7) -> int:
    since = datetime.now(UTC) - timedelta(days=days)
    return db.query(func.count(PageView.id)).filter(PageView.timestamp >= since).scalar() or 0


def get_unique_visitors(db: Session, days: int = 7) -> int:
    since = datetime.now(UTC) - timedelta(days=days)
    return (
        db.query(func.count(distinct(PageView.session_id)))
        .filter(PageView.timestamp >= since, PageView.session_id.isnot(None))
        .scalar()
        or 0
    )


def get_top_pages(db: Session, days: int = 7, limit: int = 10) -> list[dict]:
    since = datetime.now(UTC) - timedelta(days=days)
    rows = (
        db.query(PageView.path, func.count(PageView.id).label("views"))
        .filter(PageView.timestamp >= since)
        .group_by(PageView.path)
        .order_by(func.count(PageView.id).desc())
        .limit(limit)
        .all()
    )
    return [{"path": r.path, "views": r.views} for r in rows]


def get_browser_breakdown(db: Session, days: int = 7) -> list[dict]:
    since = datetime.now(UTC) - timedelta(days=days)
    rows = (
        db.query(PageView.browser, func.count(PageView.id).label("count"))
        .filter(PageView.timestamp >= since, PageView.browser.isnot(None))
        .group_by(PageView.browser)
        .order_by(func.count(PageView.id).desc())
        .all()
    )
    return [{"browser": r.browser, "count": r.count} for r in rows]


def get_device_breakdown(db: Session, days: int = 7) -> list[dict]:
    since = datetime.now(UTC) - timedelta(days=days)
    rows = (
        db.query(PageView.device_type, func.count(PageView.id).label("count"))
        .filter(PageView.timestamp >= since, PageView.device_type.isnot(None))
        .group_by(PageView.device_type)
        .order_by(func.count(PageView.id).desc())
        .all()
    )
    return [{"device": r.device_type, "count": r.count} for r in rows]


def get_referer_breakdown(db: Session, days: int = 7, limit: int = 10) -> list[dict]:
    since = datetime.now(UTC) - timedelta(days=days)
    rows = (
        db.query(PageView.referer_domain, func.count(PageView.id).label("count"))
        .filter(
            PageView.timestamp >= since,
            PageView.referer_domain.isnot(None),
            PageView.referer_domain != "",
        )
        .group_by(PageView.referer_domain)
        .order_by(func.count(PageView.id).desc())
        .limit(limit)
        .all()
    )
    return [{"domain": r.referer_domain, "count": r.count} for r in rows]


def get_daily_pageviews(db: Session, days: int = 30) -> list[dict]:
    since = datetime.now(UTC) - timedelta(days=days)
    rows = (
        db.query(
            func.date(PageView.timestamp).label("day"),
            func.count(PageView.id).label("views"),
            func.count(distinct(PageView.session_id)).label("visitors"),
        )
        .filter(PageView.timestamp >= since)
        .group_by(func.date(PageView.timestamp))
        .order_by(func.date(PageView.timestamp))
        .all()
    )
    return [
        {"day": str(r.day), "views": r.views, "visitors": r.visitors} for r in rows
    ]


def get_auth_funnel(db: Session, days: int = 7) -> dict:
    """Track portals → magic-link → verify conversion"""
    since = datetime.now(UTC) - timedelta(days=days)

    def count_path(path_prefix: str) -> int:
        return (
            db.query(func.count(PageView.id))
            .filter(PageView.timestamp >= since, PageView.path.like(f"{path_prefix}%"))
            .scalar()
            or 0
        )

    return {
        "portals_visits": count_path("/portals"),
        "magic_link_requests": count_path("/auth/magic-link"),
        "verifications": count_path("/auth/verify"),
    }


def get_response_time_avg(db: Session, days: int = 7) -> float:
    since = datetime.now(UTC) - timedelta(days=days)
    result = (
        db.query(func.avg(PageView.response_time_ms))
        .filter(PageView.timestamp >= since, PageView.response_time_ms.isnot(None))
        .scalar()
    )
    return round(result or 0, 1)


def get_total_pageviews(db: Session) -> int:
    return db.query(func.count(PageView.id)).scalar() or 0
