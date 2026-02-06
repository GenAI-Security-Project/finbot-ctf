"""WebSocket Event Types"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class WSEventType(str, Enum):
    """WebSocket event types"""

    # Connection events
    CONNECTED = "connected"
    SUBSCRIBED = "subscribed"
    UNSUBSCRIBED = "unsubscribed"
    ERROR = "error"

    # CTF events
    ACTIVITY = "activity"
    CHALLENGE_COMPLETED = "challenge_completed"
    BADGE_EARNED = "badge_earned"
    CHALLENGE_PROGRESS = "challenge_progress"

    # System events
    PING = "ping"
    PONG = "pong"


@dataclass
class WSEvent:
    """WebSocket event structure"""

    type: WSEventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_json(self) -> str:
        """Serialize to JSON"""
        return json.dumps(
            {
                "type": self.type.value
                if isinstance(self.type, WSEventType)
                else self.type,
                "data": self.data,
                "timestamp": self.timestamp,
            }
        )

    @classmethod
    def from_json(cls, data: str) -> "WSEvent":
        """Deserialize from JSON"""
        parsed = json.loads(data)
        return cls(
            type=WSEventType(parsed["type"]),
            data=parsed.get("data", {}),
            timestamp=parsed.get("timestamp", datetime.now(UTC).isoformat()),
        )


def create_activity_event(event_data: dict) -> WSEvent:
    """Create activity stream event"""
    return WSEvent(
        type=WSEventType.ACTIVITY,
        data={
            "event_type": event_data.get("event_type"),
            "summary": event_data.get("summary"),
            "severity": event_data.get("severity", "info"),
            "workflow_id": event_data.get("workflow_id"),
            "agent_name": event_data.get("agent_name"),
        },
    )


def create_challenge_completed_event(
    challenge_id: str, challenge_title: str, points: int
) -> WSEvent:
    """Create challenge completed event"""
    return WSEvent(
        type=WSEventType.CHALLENGE_COMPLETED,
        data={
            "challenge_id": challenge_id,
            "challenge_title": challenge_title,
            "points": points,
        },
    )


def create_badge_earned_event(badge_id: str, badge_title: str, rarity: str) -> WSEvent:
    """Create badge earned event"""
    return WSEvent(
        type=WSEventType.BADGE_EARNED,
        data={
            "badge_id": badge_id,
            "badge_title": badge_title,
            "rarity": rarity,
        },
    )
