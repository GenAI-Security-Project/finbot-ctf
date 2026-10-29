---
name: detector-tests
description: Write unit tests for a finbot-ctf CTF challenge detector (finbot/ctf/detectors/implementations/*.py) and its challenge YAML. Covers the success case, false positives, multi-turn gates, config validation, event filtering, and YAML wiring. Use when asked to test a detector or challenge, or when verify-change reports an untested detector.
---

# Detector tests

Most detector bugs in this repo's history are false positives and flaky
thresholds, not crashes. A detector test suite that only proves the attack
is detected is half a suite.

## Read first

1. The detector module: what events it listens to (`get_relevant_event_types`),
   every `return DetectionResult(detected=False, ...)` branch, and any
   `db.query(CTFEvent)` lookups.
2. The challenge YAML that names it (`grep -rl "detector_class: <Name>"
   finbot/ctf/definitions/challenges`): the success criteria, hints, and
   `detector_config`.

## Tests to write

One file per detector: `tests/unit/ctf/test_<module>_detector.py`. If the
detector already has tests elsewhere (the Labs guardrail detector's live in
`tests/unit/labs/`), add to that file instead.
Give every test an ID like `CTF-<SHORT>-NNN` in its docstring, matching the
house style in `tests/unit/agents/test_specialized_agents.py`.

| Group | One test per... |
|---|---|
| Detects | Success criterion in the YAML, using the YAML's own `detector_config` |
| False positives | Legitimate use of the same tool (the thing a normal player or the hints would do), plus each `detected=False` branch |
| Gates | Multi-turn or threshold gate: one below the bar, one exactly at it |
| Config | Each config key changes behaviour the way the docstring says |
| Wiring | YAML loads, `detector_class` is registered, detector accepts the YAML's config |

## Two things that are easy to get wrong

**Wiring.** The app only knows detectors that
`finbot/ctf/detectors/implementations/__init__.py` imports. Your test file
imports the detector module directly, which registers it as a side effect,
so checking `list_registered_detectors()` would pass even when the app is
broken. Check the package export instead:

```python
from finbot.ctf.detectors import implementations

assert getattr(implementations, "<DetectorClass>", None) is <DetectorClass>
```

**Event order.** The processor stores every event *before* it runs the
detectors (`event_processor.py`, `_process_single_event`). A detector that
counts earlier events from `CTFEvent` therefore also sees the current one.
Replay events the same way production does:

```python
from finbot.ctf.processor.event_processor import CTFEventProcessor


async def process(event, db):
    CTFEventProcessor()._store_ctf_event(event, "agent", db)
    return await make_detector().check_event(event, db)
```

Calling `check_event` without storing the event first hides gate bypasses.
This is how the path traversal "single-shot" bug was found.

## Rules

- Async tests need `@pytest.mark.asyncio`; the repo runs asyncio in strict mode.
- Use the `db` fixture from `tests/unit/conftest.py` for anything that
  queries `CTFEvent`. Don't pass `db=None` to skip a gate; test the gate.
- Import the detector class from its module and build it with the YAML's
  `detector_config`, so the tests still run while the wiring is broken.
- Build event dicts shaped like `EventBus.emit_agent_event` output
  (`finbot/core/messaging/events.py`), with a unique `event_id`. If the
  detector reads `mcp_server` or `agent_name`, set them.
- LLM-judge detectors: patch the judge call and test both verdicts plus the
  confidence threshold. Never call a real model.
- Assert on `result.detected` and include `result.message` in the assert, so
  a failure says which branch fired.
- If a test fails because the detector is wrong, keep it, mark it
  `@pytest.mark.xfail(strict=True, reason="<bug>")`, and report it. Never
  weaken an assertion to make it pass.

## Run

```bash
uv run python -m pytest tests/unit/ctf/test_<module>_detector.py -v
```
