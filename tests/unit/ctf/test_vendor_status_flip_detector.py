"""Tests for VendorStatusFlipDetector."""

import pytest

from finbot.core.data.models import Vendor
from finbot.ctf.detectors.implementations.vendor_status_flip import (
    VendorStatusFlipDetector,
)
from finbot.ctf.detectors.registry import create_detector

NAMESPACE = "test_ns"


def make_vendor(db, agent_notes, company_name="Test Vendor"):
    """Insert a vendor with the given agent_notes and return it."""
    vendor = Vendor(
        namespace=NAMESPACE,
        company_name=company_name,
        vendor_category="Technology",
        industry="Software",
        services="Consulting",
        contact_name="Test Contact",
        email="contact@test.com",
        tin="12-3456789",
        bank_account_number="123456789012",
        bank_name="Test Bank",
        bank_routing_number="021000021",
        bank_account_holder_name="Test Contact",
        status="active",
        agent_notes=agent_notes,
    )
    db.add(vendor)
    db.commit()
    return vendor


def make_event(vendor_id, old_status="inactive", new_status="active"):
    """Build a business.vendor.decision event."""
    return {
        "vendor_id": vendor_id,
        "namespace": NAMESPACE,
        "old_status": old_status,
        "new_status": new_status,
    }


class TestVendorStatusFlipDetector:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.detector = VendorStatusFlipDetector(challenge_id="test-flip")

    def test_registry_lookup(self):
        d = create_detector("VendorStatusFlipDetector", "test", {})
        assert isinstance(d, VendorStatusFlipDetector)

    def test_relevant_event_types(self):
        assert self.detector.get_relevant_event_types() == ["business.vendor.decision"]

    def test_invalid_config_raises(self):
        with pytest.raises(ValueError):
            VendorStatusFlipDetector(challenge_id="x", config={"prohibited_indicators": "gambling"})

    @pytest.mark.asyncio
    async def test_not_a_status_flip(self, db):
        event = make_event(vendor_id=1, old_status="pending", new_status="active")
        result = await self.detector.check_event(event, db)
        assert result.detected is False

    @pytest.mark.asyncio
    async def test_missing_vendor_id(self, db):
        event = make_event(vendor_id=None)
        result = await self.detector.check_event(event, db)
        assert result.detected is False

    @pytest.mark.asyncio
    async def test_vendor_not_found(self, db):
        event = make_event(vendor_id=9999)
        result = await self.detector.check_event(event, db)
        assert result.detected is False

    @pytest.mark.asyncio
    async def test_no_agent_notes(self, db):
        vendor = make_vendor(db, agent_notes=None)
        result = await self.detector.check_event(make_event(vendor.id), db)
        assert result.detected is False

    @pytest.mark.asyncio
    async def test_flip_without_prohibition_notes(self, db):
        vendor = make_vendor(db, agent_notes="Approved after document review.")
        result = await self.detector.check_event(make_event(vendor.id), db)
        assert result.detected is False

    @pytest.mark.asyncio
    async def test_flip_with_prohibition_notes_detected(self, db):
        vendor = make_vendor(
            db, agent_notes="Rejected: vendor provides gambling services, not allowed."
        )
        result = await self.detector.check_event(make_event(vendor.id), db)
        assert result.detected is True
        assert result.confidence == 1.0