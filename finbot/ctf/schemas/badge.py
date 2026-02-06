"""Badge Definition Schema"""

from typing import Literal

from pydantic import BaseModel, Field


class BadgeSchema(BaseModel):
    """Validates badge YAML structure"""

    id: str = Field(
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$",
        min_length=1,
        max_length=64,
        description="Unique badge identifier",
    )
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(min_length=5)

    category: Literal["achievement", "milestone", "special"]
    rarity: Literal["common", "rare", "epic", "legendary"] = "common"
    points: int = Field(ge=0, le=500, default=10)

    icon_url: str | None = Field(default=None, max_length=500)

    # Evaluator configuration
    evaluator_class: str = Field(min_length=1, max_length=100)
    evaluator_config: dict | None = None

    is_active: bool = True
    is_secret: bool = False
