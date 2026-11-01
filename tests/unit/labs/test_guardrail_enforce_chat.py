"""Caller-side enforcement: ChatAssistantBase skips the tool when should_block()."""

from unittest.mock import patch

import pytest

from finbot.agents.chat import ChatAssistantBase
from finbot.config import settings
from finbot.core.auth.session import session_manager
from finbot.guardrails.schemas import HookOutcome


@pytest.fixture()
def session(db):
    return session_manager.create_session(email="guardrail_chat@example.com")


class _Assistant(ChatAssistantBase):
    def _get_system_prompt(self) -> str:
        return "test"

    def _get_native_tool_definitions(self) -> list[dict]:
        return []

    def _build_native_callables(self) -> dict:
        return {}


def _make_assistant(session):
    with patch("finbot.agents.chat.AsyncOpenAI"):
        return _Assistant(session_context=session)


@pytest.mark.asyncio
async def test_execute_tool_skips_when_enforced_block(session, monkeypatch):
    monkeypatch.setattr(settings, "LABS_GUARDRAIL_ENFORCE", True)
    assistant = _make_assistant(session)
    ran = False

    async def _tool(**_kwargs):
        nonlocal ran
        ran = True
        return "deleted"

    assistant._tool_callables = {"findrive__delete_file": _tool}

    async def _invoke(*_args, **_kwargs):
        assistant._guardrail_service.last_verdict = "block"
        assistant._guardrail_service.last_reason = "not permitted"
        return HookOutcome.completed

    assistant._guardrail_service.invoke = _invoke

    result = await assistant._execute_tool("findrive__delete_file", {"file_id": 1})

    assert ran is False
    assert "blocked" in result
    assert "not permitted" in result


@pytest.mark.asyncio
async def test_execute_tool_runs_when_block_is_observe_only(session, monkeypatch):
    monkeypatch.setattr(settings, "LABS_GUARDRAIL_ENFORCE", False)
    assistant = _make_assistant(session)
    ran = False

    async def _tool(**_kwargs):
        nonlocal ran
        ran = True
        return "deleted"

    assistant._tool_callables = {"findrive__delete_file": _tool}

    async def _invoke(*_args, **_kwargs):
        assistant._guardrail_service.last_verdict = "block"
        assistant._guardrail_service.last_reason = "not permitted"
        return HookOutcome.completed

    assistant._guardrail_service.invoke = _invoke

    result = await assistant._execute_tool("findrive__delete_file", {"file_id": 1})

    assert ran is True
    assert result == "deleted"
