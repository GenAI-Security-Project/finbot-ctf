"""Activity Stream API Routes"""

import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from finbot.core.auth.middleware import get_session_context
from finbot.core.auth.session import SessionContext
from finbot.core.data.database import get_db
from finbot.core.data.repositories import CTFEventRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["activity"])


class ActivityItem(BaseModel):
    """Activity item model"""

    id: int
    event_category: str
    event_type: str
    summary: str
    severity: str
    agent_name: str | None
    tool_name: str | None
    workflow_id: str | None
    vendor_id: int | None
    challenge_id: str | None
    badge_id: str | None
    timestamp: str


class ActivityResponse(BaseModel):
    """Activity response model"""

    items: list[ActivityItem]
    total: int
    page: int
    page_size: int
    has_more: bool


@router.get("/activity", response_model=ActivityResponse)
def get_activity(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    category: str | None = Query(None),
    workflow_id: str | None = Query(None),
    vendor_id: int | None = Query(None),
    session_context: SessionContext = Depends(get_session_context),
    db: Session = Depends(get_db),
):
    """Get paginated activity stream"""
    event_repo = CTFEventRepository(db, session_context)

    # Get total count
    total = event_repo.count_events(
        category=category, workflow_id=workflow_id, vendor_id=vendor_id
    )

    # Get paginated events
    offset = (page - 1) * page_size
    events = event_repo.get_events(
        limit=page_size + 1,
        offset=offset,
        category=category,
        workflow_id=workflow_id,
        vendor_id=vendor_id,
    )

    has_more = len(events) > page_size
    events = events[:page_size]

    items = [
        ActivityItem(
            id=e.id,
            event_category=e.event_category,
            event_type=e.event_type,
            summary=e.summary or f"Event: {e.event_type}",
            severity=e.severity,
            agent_name=e.agent_name,
            tool_name=e.tool_name,
            workflow_id=e.workflow_id,
            vendor_id=e.vendor_id,
            challenge_id=e.challenge_id,
            badge_id=e.badge_id,
            timestamp=e.timestamp.isoformat(),
        )
        for e in events
    ]

    return ActivityResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )
