"""
Unit tests for Command Center Platform Pulse stats calculation.

Verifies that total_users in _get_pulse_stats correctly counts User records
rather than collapsing distinct Vendor namespaces.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from finbot.apps.cc.routes.dashboard import _get_pulse_stats
from finbot.core.data.models import (
    Base,
    Challenge,
    User,
    UserBadge,
    UserChallengeProgress,
    Vendor,
)


@pytest.fixture
def in_memory_db():
    """Create a fresh in-memory SQLite database for testing pulse stats."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    yield session_factory
    Base.metadata.drop_all(engine)


def _create_challenge(challenge_id: str = "ch_1") -> Challenge:
    """Helper to instantiate a valid Challenge record."""
    return Challenge(
        id=challenge_id,
        title=f"Challenge {challenge_id}",
        description="Test Challenge Description",
        category="recon",
        difficulty="beginner",
        detector_class="TestDetector",
    )


def _create_vendor(company_name: str = "Test Vendor", namespace: str = "default") -> Vendor:
    """Helper to instantiate a valid Vendor record."""
    return Vendor(
        namespace=namespace,
        company_name=company_name,
        vendor_category="consulting",
        industry="technology",
        services="software development",
        contact_name="Alice Smith",
        email=f"{company_name.lower().replace(' ', '_')}@example.com",
        tin="12-3456789",
        bank_account_number="1234567890",
        bank_name="Test Bank",
        bank_routing_number="123456789",
        bank_account_holder_name="Alice Smith",
    )


@pytest.mark.unit
class TestPulseStatsTotalUsers:
    """Tests verifying total_users in Command Center platform pulse."""

    def test_pulse_returns_zero_when_database_empty(self, in_memory_db):
        """Platform pulse should return zero for all counters when database is empty."""
        with patch("finbot.apps.cc.routes.dashboard.SessionLocal", in_memory_db):
            stats = _get_pulse_stats()

        assert stats["total_users"] == 0
        assert stats["vendors_total"] == 0
        assert stats["challenges_today"] == 0
        assert stats["badges_total"] == 0

    def test_pulse_total_users_counts_users_without_vendors(self, in_memory_db):
        """Users without associated vendor records must be counted in total_users.

        Regression test: previously, total_users queried distinct Vendor namespaces,
        meaning registered users with 0 vendors were ignored.
        """
        session = in_memory_db()
        session.add(User(user_id="user_1", email="u1@example.com", namespace="default"))
        session.add(User(user_id="user_2", email="u2@example.com", namespace="default"))
        session.add(User(user_id="user_3", email="u3@example.com", namespace="tenant_b"))
        session.commit()
        session.close()

        with patch("finbot.apps.cc.routes.dashboard.SessionLocal", in_memory_db):
            stats = _get_pulse_stats()

        assert stats["total_users"] == 3
        assert stats["vendors_total"] == 0

    def test_pulse_total_users_does_not_collapse_shared_namespace(self, in_memory_db):
        """Multiple users sharing the same namespace must each be counted.

        Regression test: previously, distinct(Vendor.namespace) collapsed all users
        sharing a namespace into a single count of 1.
        """
        session = in_memory_db()
        for idx in range(5):
            session.add(User(
                user_id=f"user_{idx}",
                email=f"u{idx}@shared.com",
                namespace="shared_ns",
            ))
        session.add(_create_vendor("Shared Vendor", namespace="shared_ns"))
        session.commit()
        session.close()

        with patch("finbot.apps.cc.routes.dashboard.SessionLocal", in_memory_db):
            stats = _get_pulse_stats()

        assert stats["total_users"] == 5
        assert stats["vendors_total"] == 1

    def test_pulse_total_users_ignores_orphan_vendor_namespaces(self, in_memory_db):
        """Vendor namespaces with no registered user account should not count as users."""
        session = in_memory_db()
        session.add(_create_vendor("Vendor A", namespace="ns_a"))
        session.add(_create_vendor("Vendor B", namespace="ns_b"))
        session.commit()
        session.close()

        with patch("finbot.apps.cc.routes.dashboard.SessionLocal", in_memory_db):
            stats = _get_pulse_stats()

        assert stats["total_users"] == 0
        assert stats["vendors_total"] == 2

    def test_pulse_stats_contains_all_expected_keys(self, in_memory_db):
        """Verify the pulse dictionary structure matches desktop template expectations."""
        with patch("finbot.apps.cc.routes.dashboard.SessionLocal", in_memory_db):
            stats = _get_pulse_stats()

        expected_keys = {"total_users", "challenges_today", "badges_total", "vendors_total"}
        assert set(stats.keys()) == expected_keys

    def test_pulse_challenges_today_filters_by_completion_date(self, in_memory_db):
        """Only challenges completed on or after today_start should be counted in challenges_today."""
        now = datetime.now(UTC)
        yesterday = now - timedelta(days=1)

        session = in_memory_db()
        session.add(_create_challenge("ch_1"))
        session.add(_create_challenge("ch_2"))
        session.add(_create_challenge("ch_3"))

        # Challenge completed today
        session.add(UserChallengeProgress(
            namespace="default",
            user_id="u1",
            challenge_id="ch_1",
            status="completed",
            completed_at=now,
        ))
        # Challenge completed yesterday
        session.add(UserChallengeProgress(
            namespace="default",
            user_id="u1",
            challenge_id="ch_2",
            status="completed",
            completed_at=yesterday,
        ))
        # Challenge attempted but not completed
        session.add(UserChallengeProgress(
            namespace="default",
            user_id="u1",
            challenge_id="ch_3",
            status="in_progress",
            completed_at=now,
        ))
        session.commit()
        session.close()

        with patch("finbot.apps.cc.routes.dashboard.SessionLocal", in_memory_db):
            stats = _get_pulse_stats()

        assert stats["challenges_today"] == 1
