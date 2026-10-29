---
name: agent-tests
description: Write unit tests for finbot-ctf AI agents (finbot/agents/*, finbot/agents/specialized/*) with the LLM and event bus mocked, so tests are fast, free, and deterministic. Covers tool schemas, tool callables, task handling, and how the agent reacts to each kind of model response. Use when asked to test an agent, orchestrator, chat assistant, or agent tool.
---

# Agent tests

Unit tests never call a real model. You control what the model "says" by
mocking `ContextualLLMClient.chat`, then check what the agent does with it.

## Read first

- The agent class: its tools (schemas plus the callables they map to), the
  system prompt builder, and what it does with `complete_task`.
- `tests/unit/agents/test_specialized_agents.py`: the house style to copy.

## File layout

`tests/unit/agents/test_<agent>.py`, starting with the header block used
across the repo:

```python
# ==============================================================================
# <Agent> Test Suite
# ==============================================================================
# User Story: As a <role>, I want <capability> so that <outcome>.
#
# Acceptance Criteria:
#   - <one line per behaviour under test>
#
# Test Categories:
#   <PREFIX>-001: <title>
# ==============================================================================
```

## Mocking the model

```python
from unittest.mock import AsyncMock, patch

from finbot.core.data.models import LLMResponse


def llm_says(*tool_calls, content=None):
    return LLMResponse(content=content, tool_calls=list(tool_calls))


def call(name, **arguments):
    return {"name": name, "call_id": f"call_{name}", "arguments": arguments}


@pytest.fixture(autouse=True)
def mock_event_bus():
    with patch("finbot.agents.base.event_bus") as bus, \
         patch("finbot.core.llm.contextual_client.event_bus", bus):
        bus.emit_agent_event = AsyncMock()
        bus.emit_business_event = AsyncMock()
        yield bus


@pytest.fixture
def model():
    """Set model.side_effect to a list of LLMResponses, one per turn."""
    with patch(
        "finbot.core.llm.contextual_client.ContextualLLMClient.chat",
        new_callable=AsyncMock,
    ) as chat:
        yield chat
```

## Tests to write

| Area | Check |
|---|---|
| Tool definitions | Every tool has name, description, JSON schema; every tool name maps to a callable |
| Happy path | Model calls the right tool, then `complete_task` with `success`; the agent returns that status |
| Model failure modes | Model returns no tool call, an unknown tool, malformed arguments, or `task_status="failed"` |
| Context passing | What the agent forwards downstream (summaries, `next_step`), especially on failure |
| Empty input | Empty or missing task data doesn't crash |
| Events | The expected `emit_agent_event` calls happen (assert on the mock) |

The failure-mode row finds the most bugs. Orchestrator issues #459 and #460
came from exactly these cases: whitespace-only summaries and success
instructions sent after a failed payment.

## Rules

- Async tests need `@pytest.mark.asyncio`.
- Use the `db` fixture from `tests/unit/conftest.py` when the agent touches
  repositories.
- Assert on behaviour (status returned, tool invoked, event emitted), not on
  prompt wording.
- A test that exposes a real bug goes in a `TestQAFindings` class, marked
  `xfail(strict=True)` with the reason, and gets a ticket via `qa-ticket`.
