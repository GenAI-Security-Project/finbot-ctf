"""CTF Challenges API Routes"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from finbot.core.auth.middleware import get_session_context
from finbot.core.auth.session import SessionContext
from finbot.core.data.database import get_db
from finbot.core.data.repositories import (
    ChallengeRepository,
    UserChallengeProgressRepository,
)
from finbot.ctf.detectors import create_detector

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["challenges"])


class ChallengeListItem(BaseModel):
    """Challenge list item model"""

    id: str
    title: str
    category: str
    subcategory: str | None
    difficulty: str
    points: int
    image_url: str | None
    status: str
    is_active: bool


class ChallengeDetail(BaseModel):
    """Challenge detail model"""

    id: str
    title: str
    description: str
    category: str
    subcategory: str | None
    difficulty: str
    points: int
    image_url: str | None
    hints: list[dict]
    labels: dict
    prerequisites: list[str]
    resources: list[dict]
    status: str
    attempts: int
    hints_used: int
    hints_cost: int
    completed_at: str | None


class CheckResult(BaseModel):
    """Check result model"""

    status: str
    detected: bool
    message: str | None
    confidence: float


class HintResponse(BaseModel):
    """Hint response model"""

    hint_index: int
    hint_text: str
    points_deducted: int
    total_hints_cost: int


@router.get("/challenges", response_model=list[ChallengeListItem])
def list_challenges(
    category: str | None = Query(None),
    difficulty: str | None = Query(None),
    status: str | None = Query(None),
    session_context: SessionContext = Depends(get_session_context),
    db: Session = Depends(get_db),
):
    """List all challenges with optional filters"""
    challenge_repo = ChallengeRepository(db)
    challenges = challenge_repo.list_challenges(
        category=category, difficulty=difficulty
    )

    # Get user progress
    progress_map = {}
    if session_context:
        progress_repo = UserChallengeProgressRepository(db, session_context)
        progress_map = progress_repo.get_progress_map()

    result = []
    for c in challenges:
        user_status = progress_map.get(c.id, "available")

        if status and user_status != status:
            continue

        result.append(
            ChallengeListItem(
                id=c.id,
                title=c.title,
                category=c.category,
                subcategory=c.subcategory,
                difficulty=c.difficulty,
                points=c.points,
                image_url=c.image_url,
                status=user_status,
                is_active=c.is_active,
            )
        )

    return result


@router.get("/challenges/{challenge_id}", response_model=ChallengeDetail)
def get_challenge(
    challenge_id: str,
    session_context: SessionContext = Depends(get_session_context),
    db: Session = Depends(get_db),
):
    """Get challenge details with user progress"""
    challenge_repo = ChallengeRepository(db)
    challenge = challenge_repo.get_challenge(challenge_id)

    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    # Get user progress
    progress = None
    if session_context:
        progress_repo = UserChallengeProgressRepository(db, session_context)
        progress = progress_repo.get_progress(challenge_id)

    # Parse JSON fields
    hints = json.loads(challenge.hints) if challenge.hints else []
    labels = json.loads(challenge.labels) if challenge.labels else {}
    prerequisites = (
        json.loads(challenge.prerequisites) if challenge.prerequisites else []
    )
    resources = json.loads(challenge.resources) if challenge.resources else []

    # Mask hints user hasn't unlocked
    hints_used = progress.hints_used if progress else 0
    masked_hints = []
    for i, hint in enumerate(hints):
        if i < hints_used:
            masked_hints.append(hint)
        else:
            masked_hints.append({"cost": hint["cost"], "text": "[locked]"})

    return ChallengeDetail(
        id=challenge.id,
        title=challenge.title,
        description=challenge.description,
        category=challenge.category,
        subcategory=challenge.subcategory,
        difficulty=challenge.difficulty,
        points=challenge.points,
        image_url=challenge.image_url,
        hints=masked_hints,
        labels=labels,
        prerequisites=prerequisites,
        resources=resources,
        status=progress.status if progress else "available",
        attempts=progress.attempts if progress else 0,
        hints_used=hints_used,
        hints_cost=progress.hints_cost if progress else 0,
        completed_at=progress.completed_at.isoformat()
        if progress and progress.completed_at
        else None,
    )


@router.post("/challenges/{challenge_id}/check", response_model=CheckResult)
def check_challenge(
    challenge_id: str,
    session_context: SessionContext = Depends(get_session_context),
    db: Session = Depends(get_db),
):
    """On-demand challenge progress check"""
    if not session_context:
        raise HTTPException(status_code=401, detail="Authentication required")

    challenge_repo = ChallengeRepository(db)
    challenge = challenge_repo.get_challenge(challenge_id)

    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    progress_repo = UserChallengeProgressRepository(db, session_context)
    progress = progress_repo.get_progress(challenge_id)

    if progress and progress.status == "completed":
        return CheckResult(
            status="completed",
            detected=True,
            message="Challenge already completed",
            confidence=1.0,
        )

    # Create detector and run aggregate check
    config = (
        json.loads(challenge.detector_config) if challenge.detector_config else None
    )
    detector = create_detector(challenge.detector_class, challenge.id, config)

    if not detector:
        raise HTTPException(status_code=500, detail="Detector not available")

    result = detector.check_aggregate(
        session_context.namespace, session_context.user_id, db
    )

    # Record the attempt
    progress_repo.record_attempt(challenge_id)

    return CheckResult(
        status="completed" if result.detected else "in_progress",
        detected=result.detected,
        message=result.message,
        confidence=result.confidence,
    )


@router.post("/challenges/{challenge_id}/hint", response_model=HintResponse)
def use_hint(
    challenge_id: str,
    session_context: SessionContext = Depends(get_session_context),
    db: Session = Depends(get_db),
):
    """Use the next available hint"""
    if not session_context:
        raise HTTPException(status_code=401, detail="Authentication required")

    challenge_repo = ChallengeRepository(db)
    challenge = challenge_repo.get_challenge(challenge_id)

    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    hints = json.loads(challenge.hints) if challenge.hints else []
    if not hints:
        raise HTTPException(status_code=400, detail="No hints available")

    progress_repo = UserChallengeProgressRepository(db, session_context)
    progress = progress_repo.get_progress(challenge_id)

    current_hints_used = progress.hints_used if progress else 0
    if current_hints_used >= len(hints):
        raise HTTPException(status_code=400, detail="All hints already used")

    # Get next hint
    hint = hints[current_hints_used]

    # Use hint
    updated_progress = progress_repo.use_hint(challenge_id, hint["cost"])

    return HintResponse(
        hint_index=current_hints_used,
        hint_text=hint["text"],
        points_deducted=hint["cost"],
        total_hints_cost=updated_progress.hints_cost,
    )
