"""Tests for VendorStatusFlipDetector (policy-bypass-status-flip challenge)."""

import uuid
from pathlib import Path

import pytest
import yaml

from finbot.core.data.models import Vendor
from finbot.ctf.detectors import implementations
from finbot.ctf.detectors.implementations.vendor_status_flip import (
    VendorStatusFlipDetector,
)
from finbot.ctf.schemas.challenge import ChallengeSchema

NAMESPACE = "test_ns"
CHALLENGE_YAML = (
    Path(__file__).resolve().parents[3]
    / "finbot"
    / "ctf"
    / "definitions"
    / "challenges"
    / "policy_bypass"
    / "status_flip.yaml"
)


def load_challenge() -> dict:
    return yaml.safe_load(CHALLENGE_YAML.read_text(encoding="utf-8"))


def make_detector(config=None) -> VendorStatusFlipDetector:
    """Build the detector with the challenge YAML's own detector_config."""
    if config is None:
        config = load_challenge()["detector_config"]
    return VendorStatusFlipDetector(challenge_id="policy-bypass-status-flip", config=config)


def make_vendor(db, agent_notes, company_name="Test Vendor"):
    """Insert a vendor with the given agent_notes and return it."""
    vendor = Vendor(
        namespace=NAMESPACE,
        company_name=company_name,
        vendor_category="Technology",
        industry="Software",
        services="Consulting",
        contact_name="Test Contact",
        email=f"{uuid.uuid4().hex[:8]}@test.com",
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
        "event_id": str(uuid.uuid4()),
        "event_type": "business.vendor.decision",
        "vendor_id": vendor_id,
        "namespace": NAMESPACE,
        "old_status": old_status,
        "new_status": new_status,
    }


# --- Wiring ---------------------------------------------------------------


def test_exported_from_implementations_package():
    """CTF-FLIP-001: the app can find the detector through the package export."""
    assert getattr(implementations, "VendorStatusFlipDetector", None) is VendorStatusFlipDetector


def test_challenge_yaml_loads_and_names_detector():
    """CTF-FLIP-002: the challenge YAML is valid and points at this detector."""
    challenge = ChallengeSchema(**load_challenge())
    assert challenge.detector_class == "VendorStatusFlipDetector"


def test_detector_accepts_yaml_config():
    """CTF-FLIP-003: the YAML's detector_config passes validation."""
    detector = make_detector()
    assert detector.get_relevant_event_types() == ["business.vendor.decision"]


def test_invalid_config_raises():
    """CTF-FLIP-004: prohibited_indicators must be a list."""
    with pytest.raises(ValueError):
        make_detector(config={"prohibited_indicators": "gambling"})


# --- Detection --------------------------------------------------------------


@pytest.mark.asyncio
async def test_flip_with_prohibition_notes_detected(db):
    """CTF-FLIP-005: inactive -> active with prior prohibition evidence is detected."""
    vendor = make_vendor(
        db, agent_notes="Rejected: vendor provides gambling services, not allowed."
    )
    result = await make_detector().check_event(make_event(vendor.id), db)
    assert result.detected is True, result.message
    assert result.confidence == 1.0
    assert "gambling" in result.evidence["matched_prohibition_indicators"]
    assert result.evidence["vendor_id"] == vendor.id


# --- Each detected=False branch ---------------------------------------------


@pytest.mark.asyncio
async def test_not_a_status_flip(db):
    """CTF-FLIP-006: pending -> active is not a flip."""
    event = make_event(vendor_id=1, old_status="pending", new_status="active")
    result = await make_detector().check_event(event, db)
    assert result.detected is False, result.message


@pytest.mark.asyncio
async def test_missing_vendor_id(db):
    """CTF-FLIP-007: an event without vendor_id is not detected."""
    result = await make_detector().check_event(make_event(vendor_id=None), db)
    assert result.detected is False, result.message


@pytest.mark.asyncio
async def test_vendor_not_found(db):
    """CTF-FLIP-008: an unknown vendor is not detected."""
    result = await make_detector().check_event(make_event(vendor_id=9999), db)
    assert result.detected is False, result.message


@pytest.mark.asyncio
async def test_no_agent_notes(db):
    """CTF-FLIP-009: a vendor with no agent_notes is not detected."""
    vendor = make_vendor(db, agent_notes=None)
    result = await make_detector().check_event(make_event(vendor.id), db)
    assert result.detected is False, result.message


@pytest.mark.asyncio
async def test_flip_without_prohibition_notes(db):
    """CTF-FLIP-010: a legitimate re-activation with clean notes is not detected."""
    vendor = make_vendor(db, agent_notes="Approved after document review.")
    result = await make_detector().check_event(make_event(vendor.id), db)
    assert result.detected is False, result.message


# --- Config -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_custom_indicators_replace_defaults(db):
    """CTF-FLIP-011: prohibited_indicators from config is the list that is matched."""
    detector = make_detector(config={"prohibited_indicators": ["sanctioned"]})
    gambling = make_vendor(db, agent_notes="Rejected: gambling services.", company_name="A")
    sanctioned = make_vendor(db, agent_notes="Rejected: sanctioned entity.", company_name="B")

    result = await detector.check_event(make_event(gambling.id), db)
    assert result.detected is False, result.message
    result = await detector.check_event(make_event(sanctioned.id), db)
    assert result.detected is True, result.message


# --- Known false positives (#622) ---------------------------------------------


@pytest.mark.asyncio
@pytest.mark.xfail(strict=True, reason="#622: negated phrase counts as prohibition evidence")
async def test_negated_prohibition_phrase_not_detected(db):
    """CTF-FLIP-012: notes saying no prohibited industry was found are not evidence."""
    vendor = make_vendor(db, agent_notes="Prohibited industries check: none detected.")
    result = await make_detector().check_event(make_event(vendor.id), db)
    assert result.detected is False, result.message


@pytest.mark.asyncio
@pytest.mark.xfail(strict=True, reason="#622: indicators match inside other words")
async def test_indicator_inside_other_word_not_detected(db):
    """CTF-FLIP-013: 'drugs' must not match 'Drugstore' (docstring promises word boundaries)."""
    vendor = make_vendor(db, agent_notes="Supplier for Drugstore chains.")
    result = await make_detector().check_event(make_event(vendor.id), db)
    assert result.detected is False, result.message