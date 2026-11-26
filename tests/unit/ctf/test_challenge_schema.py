# ==============================================================================
# Challenge Definition Schema Test Suite
# ==============================================================================
# User Story: As a maintainer, I want every challenge definition to validate,
#             and the list of where its planted bug lives to stay in the repo,
#             so that a broken definition is caught in CI and players are
#             never shown where a bug is.
#
# Acceptance Criteria:
#   - Every challenge definition in the repo passes ChallengeSchema
#   - planted_in is optional and must be a list of paths
#   - planted_in never reaches the database, so the game can't serve it
#
# Test Categories:
#   CS-001: Every Definition Validates
#   CS-002: planted_in Field
#   CS-003: planted_in Stays Out of the Database
# ==============================================================================

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from finbot.core.data.models import Challenge
from finbot.ctf.definitions.loader import DefinitionLoader
from finbot.ctf.schemas.challenge import ChallengeSchema

CHALLENGES = sorted(
    (Path(__file__).resolve().parents[3] / "finbot/ctf/definitions/challenges").rglob("*.yaml")
)
MINIMAL = {
    "id": "schema-test",
    "title": "Schema test",
    "description": "A challenge used only by this test.",
    "category": "recon",
    "difficulty": "beginner",
    "detector_class": "AnyDetector",
}


# =============================================================================
# CS-001: Every Definition Validates
# =============================================================================
@pytest.mark.parametrize("path", CHALLENGES, ids=lambda p: p.stem)
def test_cs_001_definition_validates(path):
    """The loader logs and skips an invalid file, so nothing else would notice."""
    ChallengeSchema(**yaml.safe_load(path.read_text()))


# =============================================================================
# CS-002: planted_in Field
# =============================================================================
def test_cs_002_planted_in_is_optional():
    assert ChallengeSchema(**MINIMAL).planted_in == []


def test_cs_002_planted_in_must_be_a_list():
    with pytest.raises(ValidationError):
        ChallengeSchema(**MINIMAL, planted_in="finbot/mcp/servers/systemutils/server.py")


# =============================================================================
# CS-003: planted_in Stays Out of the Database
# =============================================================================
def test_cs_003_planted_in_is_never_stored(db):
    loaded = DefinitionLoader().load_challenges(db)
    stored = " ".join(
        str(value) for row in db.query(Challenge).all() for value in vars(row).values()
    )

    assert "destructive-vendor-vendetta" in loaded
    assert "planted_in" not in Challenge.__table__.columns
    assert "finbot/mcp/servers" not in stored
