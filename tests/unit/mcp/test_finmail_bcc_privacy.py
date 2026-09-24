"""Unit tests for BCC privacy fix in finbot/mcp/servers/finmail/routing.py

Covers the fix for #585:
  1. BCC addresses must never appear on any recipient's email row (bcc_addresses=None always)
  2. TO and CC recipients correctly get bcc_addresses=None (regression guard)
  3. A vendor BCC'd recipient also gets bcc_addresses=None
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from finbot.mcp.servers.finmail.routing import route_and_deliver


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(vendor=None, user=None):
    """Minimal SQLAlchemy session mock."""
    db = MagicMock()
    query_mock = MagicMock()

    # Vendor lookup
    vendor_query = MagicMock()
    vendor_query.filter.return_value.first.return_value = vendor
    # User lookup
    user_query = MagicMock()
    user_query.filter.return_value.first.return_value = user

    # Route queries by model type
    def side_effect(model):
        from finbot.core.data.models import Vendor, User
        if model is Vendor:
            return vendor_query
        if model is User:
            return user_query
        return query_mock

    db.query.side_effect = side_effect
    return db


def _make_repo():
    """Minimal EmailRepository mock that captures create_email calls."""
    repo = MagicMock()
    repo.namespace = "testns"
    repo.create_email.return_value = MagicMock()
    return repo


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBCCPrivacyFix:
    """BCC addresses must never be stored on any recipient's email row."""

    def test_bcc_recipient_gets_null_bcc_addresses(self):
        """Fix #585: BCC row must have bcc_addresses=None, not the full BCC list."""
        db = _make_db()
        repo = _make_repo()

        route_and_deliver(
            db=db,
            repo=repo,
            namespace="testns",
            to=["to@external.com"],
            bcc=["alice@external.com", "bob@external.com"],
            subject="Test",
            body="Hello",
        )

        # Collect all create_email calls
        calls = repo.create_email.call_args_list

        # Find the BCC delivery calls (inbox_type="external", role="bcc")
        bcc_calls = [
            c for c in calls
            if c.kwargs.get("recipient_role") == "bcc"
        ]

        assert len(bcc_calls) == 2, "Expected two BCC delivery rows"
        for call in bcc_calls:
            assert call.kwargs["bcc_addresses"] is None, (
                f"BCC recipient got bcc_addresses={call.kwargs['bcc_addresses']!r}, expected None. "
                "BCC addresses must not be visible to any recipient."
            )

    def test_to_recipient_gets_null_bcc_addresses(self):
        """Regression: TO recipient rows must also have bcc_addresses=None."""
        db = _make_db()
        repo = _make_repo()

        route_and_deliver(
            db=db,
            repo=repo,
            namespace="testns",
            to=["to@external.com"],
            bcc=["alice@external.com"],
            subject="Test",
            body="Hello",
        )

        to_calls = [
            c for c in repo.create_email.call_args_list
            if c.kwargs.get("recipient_role") == "to"
        ]

        assert len(to_calls) == 1
        assert to_calls[0].kwargs["bcc_addresses"] is None

    def test_cc_recipient_gets_null_bcc_addresses(self):
        """Regression: CC recipient rows must also have bcc_addresses=None."""
        db = _make_db()
        repo = _make_repo()

        route_and_deliver(
            db=db,
            repo=repo,
            namespace="testns",
            to=["to@external.com"],
            cc=["cc@external.com"],
            bcc=["alice@external.com"],
            subject="Test",
            body="Hello",
        )

        cc_calls = [
            c for c in repo.create_email.call_args_list
            if c.kwargs.get("recipient_role") == "cc"
        ]

        assert len(cc_calls) == 1
        assert cc_calls[0].kwargs["bcc_addresses"] is None

    def test_no_bcc_sent_is_unaffected(self):
        """Sending without BCC at all should still work cleanly (no regression)."""
        db = _make_db()
        repo = _make_repo()

        result = route_and_deliver(
            db=db,
            repo=repo,
            namespace="testns",
            to=["to@external.com"],
            subject="No BCC test",
            body="Hello",
        )

        assert result["sent"] is True
        calls = repo.create_email.call_args_list
        assert len(calls) == 1
        assert calls[0].kwargs["bcc_addresses"] is None
