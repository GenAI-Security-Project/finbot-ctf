# ==============================================================================
# Challenge Service Test Suite
# ==============================================================================
# User Story: As someone running FinBot on SQLite (the default local setup), I
#             want challenge detection to leave the database free while a
#             detector is thinking, so that the app doesn't freeze and return
#             500s whenever a judge-based challenge is being checked.
#
# Acceptance Criteria:
#   - While a detector's check_event is awaited, another connection can still
#     write to the database
#
# Why a file and not the usual in-memory fixture: the `db` fixture shares one
# connection, so it can never show one connection locking out another.
#
# Test Categories:
#   CS-001: No write lock is held across the detector call (regression for
#           Bug_215, #645)
# ==============================================================================

import sqlite3
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from finbot.core.data.database import Base
from finbot.core.data.models import Challenge
from finbot.ctf.detectors.result import DetectionResult
from finbot.ctf.processor.challenge_service import ChallengeService


class SlowDetector:
    """Stands in for a judge-based detector: while it "waits for the model",
    it checks whether anyone else could write to the database."""

    def __init__(self, db_path):
        self.db_path = db_path
        self.another_writer_was_blocked: bool | None = None

    def matches_event_type(self, event_type: str) -> bool:
        return True

    async def check_event(self, event, db) -> DetectionResult:
        other = sqlite3.connect(self.db_path, timeout=0)  # fail at once instead of waiting
        try:
            other.execute("BEGIN IMMEDIATE")  # what any INSERT or UPDATE has to do first
            other.rollback()
            self.another_writer_was_blocked = False
        except sqlite3.OperationalError:
            self.another_writer_was_blocked = True
        finally:
            other.close()
        return DetectionResult(detected=False, message="not detected")


@pytest.fixture
def file_db(tmp_path):
    """A session on a SQLite file, in the journal mode the app uses."""
    path = tmp_path / "challenge_service.db"
    engine = create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA journal_mode=WAL")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(
        Challenge(
            id="qa-judge-based",
            title="QA judge-based challenge",
            description="A challenge whose detector takes a while.",
            category="policy_bypass",
            difficulty="beginner",
            detector_class="SlowDetector",
            is_active=True,
        )
    )
    session.commit()
    yield session, path
    session.close()
    engine.dispose()


class TestDatabaseStaysWritable:
    @pytest.mark.asyncio
    async def test_cs_001_database_stays_writable_while_detector_runs(self, file_db):
        """A player's first event for a challenge creates their progress row.

        That row used to be flushed, not committed, which held the write lock
        for as long as the detector took (Bug_215, #645).
        """
        session, path = file_db
        detector = SlowDetector(path)
        event = {"event_type": "agent.invoice_agent.llm_request_success", "namespace": "ns_qa", "user_id": "user_qa"}

        with patch("finbot.ctf.processor.challenge_service.create_detector", return_value=detector):
            await ChallengeService().check_event_for_challenges(event, session)

        assert detector.another_writer_was_blocked is False
