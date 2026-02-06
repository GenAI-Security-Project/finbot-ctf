"""Admin API Routes
TODO:
- Protect these routes
- Take care of CSRF protection (Super Admin portal should take care of this)
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from finbot.core.data.database import get_db
from finbot.ctf.definitions.loader import get_loader
from finbot.ctf.processor import get_processor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["admin"])


class ReloadResponse(BaseModel):
    """Reload response model"""

    status: str
    challenges_loaded: int
    badges_loaded: int


@router.post("/definitions/reload", response_model=ReloadResponse)
def reload_definitions(
    db: Session = Depends(get_db),
):
    """Reload challenge and badge definitions from YAML"""
    loader = get_loader()
    result = loader.load_all(db)

    # Clear processor caches
    processor = get_processor()
    processor.reload_definitions()

    return ReloadResponse(
        status="reloaded",
        challenges_loaded=len(result["challenges"]),
        badges_loaded=len(result["badges"]),
    )
