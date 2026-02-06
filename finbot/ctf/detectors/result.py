"""Detection Result Model"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class DetectionResult:
    """Result of a challenge detection check"""

    detected: bool
    confidence: float = 1.0  # for pattern matching
    evidence: dict[str, Any] = field(default_factory=dict)  # audit trail
    message: str | None = None  # human readable description of the detection
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __bool__(self) -> bool:
        return self.detected
