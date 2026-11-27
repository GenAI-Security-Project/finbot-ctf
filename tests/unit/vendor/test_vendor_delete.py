from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from finbot.core.auth.session import session_manager
from finbot.core.data.models import Invoice, Vendor
from finbot.core.data.repositories import InvoiceRepository
from finbot.mcp.servers.findrive.repositories import FinDriveFileRepository
from finbot.mcp.servers.finmail.repositories import EmailRepository

VENDOR_API_PREFIX = "/vendor/api/v1"


def _ctx(session):
    ctx, _ = session_manager.get_session_with_vendor_context(session.session_id)
    return ctx


def _delete(client, session, vendor_id):
    return client.delete(
        f"{VENDOR_API_PREFIX}/vendors/{vendor_id}",
        cookies={"finbot_session": session.session_id},
        headers={"X-CSRF-Token": session.csrf_token},
    )


def _vendor_exists(db, vendor_id):
    db.expire_all()
    return db.query(Vendor).filter(Vendor.id == vendor_id).first() is not None


@pytest.mark.unit
def test_delete_vendor_with_invoice_does_not_500(fast_client, vendor_pair_setup):
    s1, v1, db = vendor_pair_setup["s1"], vendor_pair_setup["v1"], vendor_pair_setup["db"]
    invoice = InvoiceRepository(db, _ctx(s1)).create_invoice_for_current_vendor(
        invoice_number="INV-1",
        amount=100.0,
        description="Consulting",
        invoice_date=datetime.now(timezone.utc),
        due_date=datetime.now(timezone.utc) + timedelta(days=30),
    )

    r = _delete(fast_client, s1, v1.id)

    assert r.status_code == 409
    assert _vendor_exists(db, v1.id)
    assert db.query(Invoice).filter(Invoice.id == invoice.id).first().vendor_id == v1.id


@pytest.mark.unit
def test_delete_vendor_with_file_returns_409(fast_client, vendor_pair_setup):
    s1, v1, db = vendor_pair_setup["s1"], vendor_pair_setup["v1"], vendor_pair_setup["db"]
    FinDriveFileRepository(db, _ctx(s1)).create_file("w9.pdf", "W-9", vendor_id=v1.id)

    r = _delete(fast_client, s1, v1.id)

    assert r.status_code == 409
    assert _vendor_exists(db, v1.id)


@pytest.mark.unit
def test_delete_vendor_with_email_returns_409(fast_client, vendor_pair_setup):
    s1, v1, db = vendor_pair_setup["s1"], vendor_pair_setup["v1"], vendor_pair_setup["db"]
    EmailRepository(db, _ctx(s1)).create_email(
        inbox_type="vendor",
        subject="Welcome",
        body="Hi",
        message_type="general",
        sender_name="FinBot",
        vendor_id=v1.id,
    )

    r = _delete(fast_client, s1, v1.id)

    assert r.status_code == 409
    assert _vendor_exists(db, v1.id)


@pytest.mark.unit
def test_delete_unused_vendor_still_works(fast_client, vendor_pair_setup, monkeypatch):
    s1, v1, db = vendor_pair_setup["s1"], vendor_pair_setup["v1"], vendor_pair_setup["db"]
    emit = AsyncMock()
    monkeypatch.setattr("finbot.apps.vendor.routes.api.event_bus.emit_business_event", emit)

    r = _delete(fast_client, s1, v1.id)

    assert r.status_code == 200
    assert not _vendor_exists(db, v1.id)
    assert emit.call_args.kwargs["event_type"] == "vendor.deleted"


@pytest.mark.unit
def test_cannot_delete_another_vendor(fast_client, vendor_pair_setup):
    s1, v2, db = vendor_pair_setup["s1"], vendor_pair_setup["v2"], vendor_pair_setup["db"]

    r = _delete(fast_client, s1, v2.id)

    assert r.status_code == 403
    assert _vendor_exists(db, v2.id)
