"""Base Badge Evaluator"""

import fnmatch
import logging
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.orm import Session

from finbot.ctf.detectors.result import DetectionResult

logger = logging.getLogger(__name__)


class BaseEvaluator(ABC):
    """
    Abstract base class for badge evaluators.

    Evaluators check if a user has met the criteria for earning a badge.
    Each evaluator decides whether to check just the current event or
    query aggregate data from the database.
    """

    def __init__(self, badge_id: str, config: dict[str, Any] | None = None):
        """Initialize the evaluator

        Args:
            badge_id: The ID of the badge this evaluator is associated with
            config: Optional evaluator configuration (evaluator-specific)
        """
        self.badge_id = badge_id
        self.config = config or {}
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate the evaluator configuration - Expected to be overridden by subclasses"""

    @abstractmethod
    def get_relevant_event_types(self) -> list[str]:
        """Return list of event types this evaluator cares about.
        Used to filter events before calling check_event().
        Examples: ["agent.llm_response", "business.vendor.created"]
        Returns:
            List of event type strings (supports wildcards like "agent.*")
        """

    @abstractmethod
    async def check_event(self, event: dict[str, Any], db: Session) -> DetectionResult:
        """Check if the user has met the criteria for earning the badge.

        Called for each relevant event. The evaluator decides whether to:
        - Just analyze the current event
        - Query aggregate data from the database
        - Use an LLM judge for semantic evaluation
        - Any combination of the above

        Args:
            event: The event data dictionary to check
            db: Database session for querying data if needed

        Returns:
            DetectionResult object containing detection status and confidence
        """

    def get_progress(self, namespace: str, user_id: str, db: Session) -> dict[str, Any]:
        """Get the progress of the user for the badge.

        Args:
            namespace: The namespace of the user
            user_id: The ID of the user
            db: The database session to use
        Returns:
            Dictionary containing the progress of the user for the badge
        """
        return {
            "current": 0,
            "target": 1,
            "percentage": 0,
        }

    def matches_event_type(self, event_type: str) -> bool:
        """Check if an event type matches this evaluator's relevant types.
        Patterns may use '*' to match any sequence of characters (glob-style).
        """
        relevant = self.get_relevant_event_types()

        for pattern in relevant:
            if "*" in pattern:
                if fnmatch.fnmatch(event_type, pattern):
                    return True
            elif pattern == event_type:
                return True

        return False
