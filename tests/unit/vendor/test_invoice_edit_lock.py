from datetime import datetime, timedelta, timezone

import pytest

from finbot.core.auth.session import session_manager
from finbot.core.data.models import Invoice
from finbot.core.data.repositories import InvoiceRepository

VENDOR_API_PREFIX = "/vendor/api/v1"


def _create_invoice(db, session, status):
    ctx, _ = session_manager.get_session_with_vendor_context(session.session_id)
    invoice = InvoiceRepository(db, ctx).create_invoice_for_current_vendor(
        invoice_number=f"INV-{status}",
        amount=100.0,
        description="Consulting",
        invoice_date=datetime.now(timezone.utc),
        due_date=datetime.now(timezone.utc) + timedelta(days=30),
    )
    invoice.status = status
    db.commit()
    return invoice.id


def _put(client, session, invoice_id, payload):
    return client.put(
        f"{VENDOR_API_PREFIX}/invoices/{invoice_id}",
        json=payload,
        cookies={"finbot_session": session.session_id},
        headers={"X-CSRF-Token": session.csrf_token},
    )


@pytest.mark.unit
@pytest.mark.parametrize("status", ["submitted", "processing", "rejected"])
def test_open_invoice_can_be_edited(fast_client, vendor_pair_setup, status):
    s1, db = vendor_pair_setup["s1"], vendor_pair_setup["db"]
    invoice_id = _create_invoice(db, s1, status)

    r = _put(fast_client, s1, invoice_id, {"amount": 250.0, "description": "Updated"})

    assert r.status_code == 200
    assert r.json()["invoice"]["amount"] == 250.0
    assert r.json()["invoice"]["status"] == status


@pytest.mark.unit
@pytest.mark.parametrize("status", ["approved", "paid"])
def test_approved_or_paid_invoice_cannot_be_edited(fast_client, vendor_pair_setup, status):
    s1, db = vendor_pair_setup["s1"], vendor_pair_setup["db"]
    invoice_id = _create_invoice(db, s1, status)

    r = _put(fast_client, s1, invoice_id, {"amount": 45000.0})

    assert r.status_code == 409
    db.expire_all()
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    assert invoice.amount == 100.0
    assert invoice.status == status


@pytest.mark.unit
def test_other_fields_locked_on_approved_invoice(fast_client, vendor_pair_setup):
    s1, db = vendor_pair_setup["s1"], vendor_pair_setup["db"]
    invoice_id = _create_invoice(db, s1, "approved")

    r = _put(fast_client, s1, invoice_id, {"invoice_number": "INV-NEW", "description": "Changed"})

    assert r.status_code == 409
    db.expire_all()
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    assert invoice.invoice_number == "INV-approved"
    assert invoice.description == "Consulting"


@pytest.mark.unit
def test_cross_vendor_edit_still_forbidden(fast_client, vendor_pair_setup):
    s1, s2, db = vendor_pair_setup["s1"], vendor_pair_setup["s2"], vendor_pair_setup["db"]
    invoice_id = _create_invoice(db, s2, "submitted")

    r = _put(fast_client, s1, invoice_id, {"amount": 45000.0})

    assert r.status_code in (403, 404)
