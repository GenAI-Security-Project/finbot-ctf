"""CTF Schemas"""

from finbot.ctf.schemas.badge import BadgeSchema
from finbot.ctf.schemas.challenge import (
    ChallengeSchema,
    HintSchema,
    LabelsSchema,
    ResourceSchema,
)

__all__ = [
    "ChallengeSchema",
    "HintSchema",
    "ResourceSchema",
    "LabelsSchema",
    "BadgeSchema",
]
