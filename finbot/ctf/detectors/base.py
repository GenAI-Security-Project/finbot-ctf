"""Base Challenge Detector"""

import logging
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.orm import Session

from finbot.ctf.detectors.result import DetectionResult

logger = logging.getLogger(__name__)


class BaseDetector(ABC):
    """Abstract Base class for challenge detectors
    The goal of a detector is to check if a specific challenge condition is met
    by analyzing events and/or querying aggregated data from the database.
    """

    def __init__(self, challenge_id: str, config: dict[str, Any] | None = None):
        """Initialize the detector

        Args:
            challenge_id: The ID of the challenge this detector is associated with
            config: Optional detector configuration (detector-specific)
        """
        self.challenge_id = challenge_id
        self.config = config or {}
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate the detector configuration - Expected to be overridden by subclasses"""

    @abstractmethod
    def get_relevant_event_types(self) -> list[str]:
        """Return list of event types this detector cares about.
        Used to filter events before calling check_event().
        Examples: ["agent.llm_response", "business.vendor.created"]
        Returns:
            List of event type strings (supports wildcards like "agent.*")
        """

    @abstractmethod
    def check_event(self, event: dict[str, Any]) -> DetectionResult:
        """Check if the challenge condition is met for a given event.
        Called for each event as it arrives and primary detection methods for
        real-time event detection.
        Args:
            event: The event data dictionary to check
        Returns:
            DetectionResult object containing detection status and confidence
        """

    def check_aggregate(
        self, namespace: str, user_id: str, db: Session
    ) -> DetectionResult:
        """Check aggregate data for challenge completion.
        Called on-demand when user needs to check progress.
        Override for challenges that need to query historical data.
        Args:
            namespace: The namespace of the user
            user_id: The ID of the user
            db_session: The database session to use
        Returns:
            DetectionResult object containing detection status and confidence
        """
        return DetectionResult(
            detected=False,
            message="Aggregate data check not implemented for this detector",
        )

    def matches_event_type(self, event_type: str) -> bool:
        """Check if an event type matches this detector's relevant types"""
        relevant = self.get_relevant_event_types()

        for pattern in relevant:
            if pattern.endswith("*"):
                # Wildcard match
                prefix = pattern[:-1]
                if event_type.startswith(prefix):
                    return True
            elif pattern == event_type:
                return True

        return False
