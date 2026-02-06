"""Challenge Completion Service"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from finbot.core.data.models import Challenge, UserChallengeProgress
from finbot.ctf.detectors.registry import create_detector
from finbot.ctf.detectors.result import DetectionResult

logger = logging.getLogger(__name__)


class ChallengeService:
    """Handles challenge detection and progress tracking"""

    def check_event_for_challenges(
        self, event: dict[str, Any], db: Session
    ) -> list[tuple[str, DetectionResult]]:
        """Check if an event completes any challenges
        Returns list of (challenge_id, result) tuples for completed challenges
        """
        event_type = event.get("event_type", "")
        namespace = event.get("namespace")
        user_id = event.get("user_id")
        if not namespace or not user_id:
            return []

        completed = []
        challenges = db.query(Challenge).filter(Challenge.is_active).all()
        for challenge in challenges:
            config = (
                json.loads(challenge.detector_config)
                if challenge.detector_config
                else None
            )
            detector = create_detector(challenge.detector_class, challenge.id, config)
            if not detector:
                continue
            if not detector.matches_event_type(event_type):
                continue
            progress = self._get_or_create_progress(
                db, namespace, user_id, challenge.id
            )
            if progress.status == "completed":
                continue

            prerequisites = (
                json.loads(challenge.prerequisites) if challenge.prerequisites else []
            )
            if not self._check_prerequisites(db, namespace, user_id, prerequisites):
                continue

            # Run detection
            try:
                result: DetectionResult = detector.check_event(event, db)
                progress.attempts += 1
                if progress.first_attempt_at is None:
                    progress.first_attempt_at = datetime.now(UTC)
                if result.detected:
                    self._mark_completed(db, progress, event, result)
                    completed.append((challenge.id, result))
                    logger.info(
                        "Challenge completed: %s for user %s (confidence: %.2f)",
                        challenge.id,
                        user_id,
                        result.confidence,
                    )
                else:
                    progress.failed_attempts += 1
                progress.status = (
                    "in_progress" if progress.status == "available" else progress.status
                )
                db.commit()

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Error checking challenge %s: %s", challenge.id, e)
                db.rollback()

        return completed

    def _get_or_create_progress(
        self, db: Session, namespace: str, user_id: str, challenge_id: str
    ) -> UserChallengeProgress:
        """Get or create user progress record"""
        progress = (
            db.query(UserChallengeProgress)
            .filter(
                UserChallengeProgress.namespace == namespace,
                UserChallengeProgress.user_id == user_id,
                UserChallengeProgress.challenge_id == challenge_id,
            )
            .first()
        )

        if not progress:
            progress = UserChallengeProgress(
                namespace=namespace,
                user_id=user_id,
                challenge_id=challenge_id,
                status="available",
            )
            db.add(progress)
            db.flush()

        return progress

    def _check_prerequisites(
        self,
        db: Session,
        namespace: str,
        user_id: str,
        prerequisites: list[str],
    ) -> bool:
        """Return True if all prerequisite challenges are completed for this user."""
        if not prerequisites:
            return True
        for prereq_id in prerequisites:
            progress = (
                db.query(UserChallengeProgress)
                .filter(
                    UserChallengeProgress.namespace == namespace,
                    UserChallengeProgress.user_id == user_id,
                    UserChallengeProgress.challenge_id == prereq_id,
                    UserChallengeProgress.status == "completed",
                )
                .first()
            )
            if not progress:
                return False
        return True

    def _mark_completed(
        self,
        db: Session,
        progress: UserChallengeProgress,
        event: dict[str, Any],
        result: DetectionResult,
    ):
        """Mark challenge as completed"""
        now = datetime.now(UTC)

        progress.status = "completed"
        progress.successful_attempts += 1
        progress.completed_at = now

        if progress.first_attempt_at:
            progress.completion_time_seconds = int(
                (now - progress.first_attempt_at).total_seconds()
            )

        progress.completion_evidence = json.dumps(
            {
                "result_message": result.message,
                "confidence": result.confidence,
                "evidence": result.evidence,
                "event_type": event.get("event_type"),
                "timestamp": result.timestamp.isoformat(),
            }
        )
        progress.completion_workflow_id = event.get("workflow_id")
