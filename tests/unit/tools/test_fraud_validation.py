"""Argument validation in the fraud data tools (#180, #182, #183, #188, #191)."""

from contextlib import contextmanager
from datetime import date

import pytest

from finbot.core.auth.session import session_manager
from finbot.core.data.models import Invoice
from finbot.core.data.repositories import VendorRepository
from finbot.tools.data.fraud import (
    flag_invoice_for_review,
    update_fraud_agent_notes,
    update_vendor_risk,
)

pytestmark = pytest.mark.asyncio

BLANK = ["", "   ", "\t", "\n", None]


@pytest.fixture
def session(db, monkeypatch):
    @contextmanager
    def _db_session():
        yield db

    monkeypatch.setattr("finbot.tools.data.fraud.db_session", _db_session)
    return session_manager.create_session(email="fraud_validation@example.com")


@pytest.fixture
def vendor(db, session):
    return VendorRepository(db, session).create_vendor(
        company_name="Test Vendor",
        vendor_category="Technology",
        industry="Software",
        services="Consulting",
        contact_name="Alice",
        email="alice@vendor.test",
        tin="12-3456789",
        bank_account_number="123456789012",
        bank_name="Test Bank",
        bank_routing_number="021000021",
        bank_account_holder_name="Alice",
    )


@pytest.fixture
def invoice(db, session, vendor):
    row = Invoice(
        namespace=session.namespace,
        vendor_id=vendor.id,
        description="Test invoice",
        amount=1000.0,
        status="submitted",
        invoice_date=date.today(),
        due_date=date.today(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.mark.parametrize("risk_level", ["critical", "Medium", "HIGH", " low", "low ", "", None])
async def test_invalid_risk_level_is_not_saved(db, session, vendor, risk_level):
    before = (vendor.risk_level, vendor.agent_notes)

    with pytest.raises(ValueError, match="risk_level"):
        await update_vendor_risk(vendor.id, risk_level, "notes", session)

    db.refresh(vendor)
    assert (vendor.risk_level, vendor.agent_notes) == before


@pytest.mark.parametrize("risk_level", ["low", "medium", "high"])
async def test_valid_risk_level_is_saved(session, vendor, risk_level):
    result = await update_vendor_risk(vendor.id, risk_level, "notes", session)

    assert result["risk_level"] == risk_level


@pytest.mark.parametrize("action", ["approve_immediately", "REJECT", " hold", "", None])
async def test_invalid_action_is_not_saved(db, session, invoice, action):
    with pytest.raises(ValueError, match="recommended_action"):
        await flag_invoice_for_review(invoice.id, "suspicious_amount", action, "notes", session)

    db.refresh(invoice)
    assert invoice.status == "submitted"
    assert not invoice.agent_notes


@pytest.mark.parametrize("reason", BLANK)
async def test_blank_flag_reason_is_not_saved(db, session, invoice, reason):
    with pytest.raises(ValueError, match="flag_reason"):
        await flag_invoice_for_review(invoice.id, reason, "reject", "notes", session)

    db.refresh(invoice)
    assert invoice.status == "submitted"
    assert not invoice.agent_notes


@pytest.mark.parametrize(
    "action, expected_status",
    [
        ("hold", "submitted"),
        ("escalate", "submitted"),
        ("monitor", "submitted"),
        ("reject", "rejected"),
    ],
)
async def test_valid_actions_still_work(session, invoice, action, expected_status):
    result = await flag_invoice_for_review(
        invoice.id, "suspicious_amount", action, "notes", session
    )

    assert result["status"] == expected_status


@pytest.mark.parametrize("notes", BLANK)
async def test_blank_fraud_notes_are_not_saved(db, session, vendor, notes):
    before = vendor.agent_notes

    with pytest.raises(ValueError, match="agent_notes"):
        await update_fraud_agent_notes(vendor.id, notes, session)

    db.refresh(vendor)
    assert vendor.agent_notes == before


async def test_real_fraud_notes_are_appended(session, vendor):
    result = await update_fraud_agent_notes(vendor.id, "checked", session)

    assert "[Fraud Agent] checked" in result["agent_notes"]
