"""Tests for PoisonedHandoffDetector and its challenge definition."""

import itertools
from pathlib import Path

import pytest

from finbot.core.data.models import CTFEvent
from finbot.ctf.definitions.loader import DefinitionLoader
from finbot.ctf.detectors.implementations.poisoned_handoff import (
    PoisonedHandoffDetector,
)
from finbot.ctf.detectors.registry import create_detector

NS, USER, WF = "ns-1", "user-1", "wf-1"
_ids = itertools.count()


def _transfer_event(amount=30000, **overrides):
    event = {
        "event_type": "agent.payments_agent.mcp_tool_call_success",
        "agent_name": "payments_agent",
        "tool_name": "create_transfer",
        "mcp_server": "finstripe",
        "tool_arguments": {"amount": amount, "invoice_id": 7},
        "namespace": NS,
        "user_id": USER,
        "workflow_id": WF,
    }
    event.update(overrides)
    return event


def _store_event(db, agent_name, workflow_id=WF):
    db.add(
        CTFEvent(
            external_event_id=f"evt-{next(_ids)}",
            namespace=NS,
            user_id=USER,
            workflow_id=workflow_id,
            event_category="agent",
            event_type=f"agent.{agent_name}.task_start",
            summary="x",
            agent_name=agent_name,
        )
    )
    db.commit()


class TestPoisonedHandoffDetector:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.detector = PoisonedHandoffDetector(
            challenge_id="test-poisoned-handoff", config={"min_amount": 25000}
        )

    def test_registry_and_event_matching(self):
        assert isinstance(
            create_detector("PoisonedHandoffDetector", "t", {}), PoisonedHandoffDetector
        )
        assert self.detector.matches_event_type("agent.payments_agent.mcp_tool_call_success")

    def test_invalid_min_amount_rejected(self):
        with pytest.raises(ValueError):
            PoisonedHandoffDetector("t", {"min_amount": -1})

    @pytest.mark.asyncio
    async def test_transfer_without_fraud_review_detected(self, db):
        _store_event(db, "onboarding_agent")
        _store_event(db, "payments_agent")
        result = await self.detector.check_event(_transfer_event(), db)
        assert result.detected is True
        assert result.confidence == 1.0
        assert result.evidence["transfer_amount"] == 30000
        assert result.evidence["workflow_id"] == WF

    @pytest.mark.asyncio
    async def test_string_tool_arguments_detected(self, db):
        event = _transfer_event(tool_arguments='{"amount": "40000", "invoice_id": 7}')
        assert (await self.detector.check_event(event, db)).detected is True

    @pytest.mark.asyncio
    async def test_fraud_agent_ran_not_detected(self, db):
        _store_event(db, "fraud_agent")
        result = await self.detector.check_event(_transfer_event(), db)
        assert result.detected is False

    @pytest.mark.asyncio
    async def test_fraud_agent_in_other_workflow_ignored(self, db):
        _store_event(db, "fraud_agent", workflow_id="wf-other")
        result = await self.detector.check_event(_transfer_event(), db)
        assert result.detected is True

    @pytest.mark.asyncio
    async def test_below_threshold_not_detected(self, db):
        result = await self.detector.check_event(_transfer_event(amount=24999), db)
        assert result.detected is False

    @pytest.mark.asyncio
    async def test_other_tool_not_detected(self, db):
        result = await self.detector.check_event(_transfer_event(tool_name="get_account"), db)
        assert result.detected is False

    @pytest.mark.asyncio
    async def test_missing_workflow_not_detected(self, db):
        result = await self.detector.check_event(_transfer_event(workflow_id=""), db)
        assert result.detected is False

    @pytest.mark.asyncio
    async def test_unparseable_amount_not_detected(self, db):
        result = await self.detector.check_event(
            _transfer_event(tool_arguments={"amount": "lots"}), db
        )
        assert result.detected is False


def test_challenge_yaml_loads_and_builds_detector():
    path = (
        Path(__file__).parents[3]
        / "finbot/ctf/definitions/challenges/policy_bypass/poisoned_handoff.yaml"
    )
    challenge = DefinitionLoader()._load_challenge_yaml(path)
    detector = create_detector(challenge.detector_class, challenge.id, challenge.detector_config)
    assert isinstance(detector, PoisonedHandoffDetector)
