"""Inputs reaching the LLM judge in judge-based detectors (#121, #122, #123)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from finbot.ctf.detectors.implementations.indirect_exfil import IndirectExfilDetector
from finbot.ctf.detectors.implementations.system_prompt_leak import (
    SystemPromptLeakDetector,
)
from finbot.ctf.detectors.implementations.vendor_risk_downplay import (
    VendorRiskDownplayDetector,
)

JUDGE_DETECTORS = [
    (SystemPromptLeakDetector, {"agent_output_tool_names": ["complete_task"]}),
    (VendorRiskDownplayDetector, {}),
    (IndirectExfilDetector, {}),
]


@pytest.mark.parametrize("detector_class, extra", JUDGE_DETECTORS)
@pytest.mark.parametrize("prompt", ["", "   ", "\n\t"])
def test_blank_judge_prompt_is_rejected(detector_class, extra, prompt):
    with pytest.raises(ValueError, match="empty"):
        detector_class("c", config={"judge_system_prompt": prompt, **extra})


@pytest.mark.parametrize("detector_class, extra", JUDGE_DETECTORS)
def test_non_blank_judge_prompt_is_accepted(detector_class, extra):
    detector_class("c", config={"judge_system_prompt": "judge it", **extra})


def _detector_and_event(messages):
    detector = SystemPromptLeakDetector(
        "c",
        config={
            "judge_system_prompt": "judge it",
            "agent_output_tool_names": [],
            "include_llm_text": True,
        },
    )
    event = {
        "request_dump": {"messages": messages},
        "response_dump": {"content": "reply"},
    }
    return detector, event


def test_every_system_message_is_kept_in_order():
    detector, event = _detector_and_event(
        [
            {"role": "system", "content": "FIRST RULES"},
            {"role": "user", "content": "hello"},
            {"role": "system", "content": "SECOND RULES"},
        ]
    )

    system_prompt, _ = detector._extract_texts(event)

    assert system_prompt == "FIRST RULES\nSECOND RULES"


@pytest.mark.parametrize(
    "contents, expected",
    [
        (["ONLY RULES"], "ONLY RULES"),
        ([None], ""),
        (["RULES", None], "RULES"),
        ([None, "RULES"], "RULES"),
        ([], ""),
    ],
)
def test_single_null_and_missing_system_content(contents, expected):
    detector, event = _detector_and_event([{"role": "system", "content": c} for c in contents])

    system_prompt, _ = detector._extract_texts(event)

    assert system_prompt == expected


@pytest.mark.asyncio
async def test_judge_receives_the_first_system_message():
    detector, event = _detector_and_event(
        [
            {"role": "system", "content": "FIRST RULES"},
            {"role": "system", "content": "SECOND RULES"},
        ]
    )
    verdict = MagicMock(score=0, reasoning="no leak")

    with patch("finbot.ctf.detectors.implementations.system_prompt_leak.LLMJudge") as judge_class:
        judge_class.return_value.evaluate = AsyncMock(return_value=verdict)
        await detector.check_event(event, MagicMock())

    judge_input = judge_class.return_value.evaluate.call_args[0][0]
    assert "FIRST RULES" in judge_input
    assert "SECOND RULES" in judge_input
