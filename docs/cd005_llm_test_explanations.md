# CD005 — LLM Integration Layer: Test Explanations

This document explains what each unit test in the LLM Integration Layer is actually
testing, what the mocks simulate, and what real code runs. Intended for code reviewers
and onboarding.

---

## Why Mocks?

The mocks replace external dependencies (real AI services, event buses, Google Sheets)
so tests run fast, offline, and deterministically. What the mocks do NOT replace is the
code written in this codebase — that always runs for real.

**Rule of thumb:** Mocked = external service. Not mocked = code we own.

---

## File Overview

| File | Class Under Test | What It Does |
|---|---|---|
| `test_ollama_client.py` | `OllamaClient` | Local AI via Ollama server |
| `test_llm_client.py` | `LLMClient` | Router that picks the right provider |
| `test_mock_client.py` | `MockLLMClient` | Fake AI client for testing |
| `test_openai_client.py` | `OpenAIClient` | Cloud AI via OpenAI API |
| `test_contextual_client.py` | `ContextualLLMClient` | Wrapper adding session identity + event tracking |

---

## test_ollama_client.py (27 tests)

**What the mocks simulate:** The Ollama API responding (or failing), the shape of
Ollama's response object.

**What the tests actually verify:** The `OllamaClient` wrapper code.

| Test | What the code does | Description + Example |
|---|---|---|
| LLM-CONF-001 | Reads settings and wires them to AsyncClient constructor | `settings.LLM_DEFAULT_MODEL = "llama3.2"` → `client.default_model == "llama3.2"` / `settings.OLLAMA_BASE_URL = "http://host"` → `AsyncClient(host="http://host", timeout=60)` |
| LLM-CHAT-001 | Maps `LLMRequest` → Ollama API call → `LLMResponse` | `LLMRequest(messages=[{"role":"user","content":"hi"}])` goes in → `LLMResponse(success=True, content="hello", provider="ollama")` comes out |
| LLM-CHAT-002 | Appends new assistant message to existing history | Input: `[user, assistant, user]` → After chat: `[user, assistant, user, new_assistant]` — nothing dropped, nothing reordered |
| LLM-CHAT-003 | Passes request-level model/temperature overrides to the API | `request.model="codellama"` → Ollama receives `model="codellama"`, not the default `"llama3.2"` |
| LLM-CHAT-004 | Passes `temperature=0.0` to Ollama unchanged | Regression for falsy-zero bug: `request.temperature=0.0` → Ollama receives `0.0`, not the default `0.7` (the `or` operator treats `0.0` as falsy) |
| LLM-TOOL-001 | Extracts tool calls and normalises them to standard dict format | Ollama: `tool_call.function.name="get_weather"` → `{"name":"get_weather","call_id":"ollama_call_0","arguments":{...}}` |
| LLM-TOOL-002 | Assigns sequential IDs to multiple tool calls | Two tool calls → `ollama_call_0` (NYC) and `ollama_call_1` (LA), both preserved in order |
| LLM-TOOL-003 | Tool call dicts stored in assistant history are JSON-serializable | `json.dumps(response.messages[-1]["tool_calls"])` succeeds — raw SDK objects would raise `TypeError` |
| LLM-TOOL-004 | Tool call dicts in history have keys `name`, `call_id`, `arguments` | History entry format matches `response.tool_calls` format — callers use both interchangeably |
| LLM-ERR-001 | Retry loop catches TimeoutError and retries | Attempt 1: TimeoutError → retry → Attempt 2: success → `response.success = True`, `call_count == 2` |
| LLM-ERR-002 | Retry loop stops after max_retries (3) and propagates the error | Attempts 1–4 all raise TimeoutError → error raised to caller, `call_count == 4` |
| LLM-ERR-003 | ConnectionError is treated as retryable same as TimeoutError | Attempt 1: ConnectionError → retry → Attempt 2: success → `response.content == "recovered"` |
| LLM-ERR-004 | ValueError fails immediately without any retry | Attempt 1: ValueError raised → fails immediately, `call_count == 1` (no retries) |
| LLM-JSON-001 | Extracts schema and passes it as `format` to Ollama API | `request.output_json_schema = {"name": "user_info", "schema": {...}}` → `AsyncClient.chat(format={...})` |
| LLM-META-001 | Extracts performance fields into `response.metadata` | `ollama_response.total_duration = 5000` → `response.metadata["total_duration"] == 5000` |
| LLM-META-002 | Handles missing metadata with None fallback instead of crashing | Response has no `.total_duration` → `response.metadata["total_duration"] is None` |
| LLM-OLLA-EDGE-001 | Converts `None` content to empty string | `message.content = None` → `response.content == ""` — callers doing `len(response.content)` won't crash |
| LLM-OLLA-EDGE-002 | Preserves both text content AND tool calls when both are present | Response has content + tool call → both in `response.content` and `response.tool_calls`, and `tool_calls` key added to message history |
| LLM-OLLA-EDGE-003 | Does not mutate the caller's original messages list | Length of caller's list checked before and after `chat()` — unchanged |
| LLM-OLLA-EDGE-004 | Second `chat()` call on same request does not include first reply | `len(input_to_call_2) == 1`, not 2 — assistant reply from call 1 must not be in call 2's input |
| LLM-OLLA-EDGE-005 | Bug doc: `response.messages` is `None` after chat | Current code does not populate `response.messages` — callers that iterate it crash with `TypeError` |
| LLM-OLLA-EDGE-006 | Handles `tool_calls` with unexpected type (dict instead of list) | `message.tool_calls = {}` → no `AttributeError` on iterating a non-list |
| LLM-OLLA-EDGE-007 | Handles tool call missing required fields | Tool call without `function.name` → client does not crash with `AttributeError` |
| LLM-OLLA-EDGE-008 | Handles `request.messages=None` | `LLMRequest(messages=None)` → no `NoneType` error when building request |
| LLM-OLLA-EDGE-009 | Handles `message.content` as unexpected type (dict instead of string) | `message.content = {"key": "val"}` → client handles gracefully, no crash |
| LLM-OLLA-EDGE-010 | Does not retry on unexpected exceptions | `RuntimeError` raised → propagates immediately, `call_count == 1`, no retry |
| LLM-OLLA-GSI-001 | Connects to real Google Sheets and checks test tracking columns | No mocks — connects to actual API, checks Summary worksheet headers exist |

---

## test_llm_client.py (15 tests)

**What the mocks simulate:** The underlying provider (OpenAI/Ollama/Mock client) being
created and responding.

**What the tests actually verify:** The `LLMClient` routing and delegation logic.

| Test | What the code does | Description + Example |
|---|---|---|
| LLM-PROV-001 | Initialises with OpenAI provider when settings say so | `settings.LLM_PROVIDER = "openai"` → `client.provider == "openai"`, `OpenAIClient` instantiated once |
| LLM-PROV-002 | Instantiates OllamaClient directly with settings | `settings.OLLAMA_BASE_URL = "http://localhost:11434"` → `AsyncClient(host="http://localhost:11434", timeout=60)`, `client.host` correct |
| LLM-PROV-003 | Initialises with Mock provider when settings say so | `settings.LLM_PROVIDER = "mock"` → `MockLLMClient` instantiated once |
| LLM-PROV-004 | Raises ValueError for unknown provider names | `settings.LLM_PROVIDER = "unsupported_provider"` → `ValueError` raised with provider name in message |
| LLM-PROV-005 | Logs warning when request asks for different provider than configured | Configured: `"openai"`, request specifies `provider="mock"` → warning logged, request still processed |
| LLM-PROV-006 | Returns `success=False` response when the provider raises an error | Provider raises `Exception("API connection failed")` → `LLMResponse(success=False)` returned, no crash |
| LLM-PROV-007 | Delegates chat to the configured provider unchanged | `client.chat(request)` → `mock_provider.chat(request)` called exactly once, response passed through unmodified |
| LLM-PROV-008 | Documents import-time singleton risk | `get_llm_client()` returns the same `llm_client` object created at module import — wrong provider at import time raises `ValueError` that crashes any importer |
| LLM-PROV-009 | `LLM_PROVIDER="does_not_exist"` raises `ValueError` at instantiation | Error is catchable at `LLMClient()` call time, not deferred silently |
| LLM-PROV-010 | Duplicate of PROV-002 — OllamaClient direct init | Independently verifies same OllamaClient wiring (added before PROV-002 slot existed) |
| LLM-PROV-011 | `LLM_PROVIDER="ollama"` raises `ValueError` from `LLMClient` | OllamaClient is not registered in `_get_client()` — `"ollama"` falls through to `raise ValueError` |
| LLM-PROV-012 | No warning logged when `request.provider == client.provider` | `logger.warning.assert_not_called()` — warning only fires on real mismatches, not on every call |
| LLM-PROV-013 | Does not mutate request fields before delegating | `request.provider`, `model`, `temperature`, `len(messages)` all unchanged after `client.chat(request)` |
| LLM-PROV-014 | Error response is well-formed | On provider failure: `success=False`, `content` non-empty, `provider` non-empty, `"unavailable"` in content |
| LLM-CLI-GSI-001 | Connects to real Google Sheets and checks test tracking columns | No mocks — real API connection |

---

## test_mock_client.py (8 tests)

**What the mocks simulate:** Nothing — `MockLLMClient` is itself the fake, no external
dependencies.

**What the tests actually verify:** That the mock client behaves consistently so other
tests that depend on it get reliable results.

| Test | What the code does | Description + Example |
|---|---|---|
| LLM-MOCK-001 | Returns the same canned response every time | Request 1 and Request 2 both return `"This is a mock LLM response"` — deterministic |
| LLM-MOCK-002 | Ignores all request parameters and returns mock response | Custom model, temperature, tools passed → still returns same mock response |
| LLM-MOCK-003 | Handles empty messages list without error | `LLMRequest(messages=[])` → mock response returned successfully |
| LLM-MOCK-004 | Handles `messages=None` without error | `LLMRequest(messages=None)` → mock response returned successfully |
| LLM-MOCK-005 | Returns `response.success=True` | Callers that gate on `success` before processing will proceed normally with mock |
| LLM-MOCK-006 | Bug doc: `response.tool_calls` is `None`, not `[]` | Callers doing `for tc in response.tool_calls:` get `TypeError: 'NoneType' is not iterable` — fix would return `[]` |
| LLM-MOCK-EDGE-001 | Bug doc: exception wrapping loses original exception type | `raise Exception(f"Mock LLM chat failed: {e}") from e` discards `ValueError` — `except ValueError` in callers never matches |
| LLM-MOCK-GSI-001 | Connects to real Google Sheets and checks test tracking columns | No mocks — real API connection |

---

## test_openai_client.py (21 tests)

**What the mocks simulate:** The OpenAI `AsyncOpenAI` client and its responses.

**What the tests actually verify:** The `OpenAIClient` wrapper code.

| Test | What the code does | Description + Example |
|---|---|---|
| LLM-OAPI-001 | Reads settings and initialises `AsyncOpenAI` with the API key | `settings.OPENAI_API_KEY = "test-key"` → `AsyncOpenAI(api_key="test-key")` |
| LLM-OAPI-002 | Maps OpenAI response format to standard `LLMResponse` | `response.output_text = "Hello from OpenAI"` → `LLMResponse(content="Hello from OpenAI", provider="openai", success=True)` |
| LLM-OAPI-003 | Formats JSON schema correctly for OpenAI Responses API | `request.output_json_schema = {...}` → API called with `text.format.type="json_schema"`, `strict=True` |
| LLM-OAPI-004 | Extracts function calls and parses JSON arguments | `item.arguments = '{"location": "NYC"}'` (string) → `tool_call["arguments"] == {"location": "NYC"}` (dict) |
| LLM-OAPI-005 | Passes `previous_response_id` for stateful conversation chaining | `request.previous_response_id = "prev_123"` → API call includes `previous_response_id="prev_123"` |
| LLM-OAPI-006 | Preserves full message history in response | Input: 3 messages → Output: `response.messages` has 4 (3 original + 1 new assistant) |
| LLM-OAPI-007 | Passes `temperature=0.0` to OpenAI unchanged | Regression for falsy-zero bug: `request.temperature=0.0` → API receives `0.0`, not the default `0.7` |
| LLM-OAPI-008 | Passes explicit temperature to OpenAI unchanged | `request.temperature=0.5` → API receives `0.5` exactly |
| LLM-OAPI-009 | `temperature=None` falls back to client default | `request.temperature=None` → API receives `0.7` (the client's `default_temperature`) |
| LLM-OAPI-ERR-001 | Raises exception on malformed JSON in function arguments | `item.arguments = '{invalid json'` → `JSONDecodeError` raised, no silent failure |
| LLM-OAPI-ERR-002 | Propagates network errors with clear message wrapping | `ConnectionError("Network unreachable")` → `Exception` raised containing both `"Network unreachable"` and `"OpenAI chat failed"` |
| LLM-OAPI-EDGE-001 | Handles response with no function calls without error | Response output has no `function_call` items → `response.tool_calls` is empty, `success=True` |
| LLM-OAPI-EDGE-002 | Handles `response.output` as unexpected type (dict instead of list) | `response.output = {}` → no crash, client handles non-list output gracefully |
| LLM-OAPI-EDGE-003 | Handles function call item with missing `arguments` field | `item.arguments = None` → no crash when arguments is not a valid JSON string |
| LLM-OAPI-EDGE-004 | Handles `request.messages=None` | `LLMRequest(messages=None)` → no `NoneType` error |
| LLM-OAPI-EDGE-005 | Handles `message.content` as non-standard type | SDK content items normally have `.type` attribute — missing or wrong type handled gracefully |
| LLM-OAPI-EDGE-006 | Does not retry on unexpected exceptions | `RuntimeError` raised → propagates immediately, `call_count == 1` |
| LLM-OAPI-EDGE-007 | Bug doc: caller's messages list mutated after chat | `input_list = request.messages or []` is an alias — `input_list.append(reply)` mutates the caller's list |
| LLM-OAPI-EDGE-008 | `response.messages` and `request.messages` are independent | Mutating `response.messages` after chat does not corrupt `request.messages` |
| LLM-OAPI-EDGE-009 | Bug doc: second `chat()` call on same request leaks first reply | Reusing same `LLMRequest`: call 2 receives 3 messages instead of 1 (list mutation accumulates across calls) |
| LLM-OAPI-GSI-001 | Connects to real Google Sheets and checks test tracking columns | No mocks — real API connection |

---

## test_contextual_client.py (17 tests)

### What is ContextualLLMClient?

A wrapper around the base LLM client that adds three things the raw clients don't have:

1. **Session identity** — knows *who* is making the request (`user_id`, `session_id`, `namespace`)
2. **Workflow tracking** — knows *what process* is running (`workflow_id`, `call_count`, `agent_name`)
3. **Event emission** — *announces* every LLM call to the event bus (start / success / error)
   so the CTF monitoring system can observe what agents are doing

The raw Ollama/OpenAI clients just talk to the AI. `ContextualLLMClient` wraps that
with observability and identity.

**What the mocks simulate:** The underlying LLM provider responding, the event bus
receiving events.

---

### LLM-CTX-001: Session Context Preservation

```python
client = ContextualLLMClient(session_context=session_context, agent_name="test_agent")
assert client.session_context.user_id == "user_123"
assert client.context_info["namespace"] == "vendor_789"
```

**What IS mocked:** `get_llm_client()` — blocks real AI provider creation.

**What is NOT mocked:**

| What runs for real | What it proves |
|---|---|
| `ContextualLLMClient.__init__()` | Constructor stores session_context without modification |
| `client.session_context.user_id` | Real attribute access — data wasn't dropped or transformed |
| `client.context_info` | Real property reads from session_context and returns correct dict |

---

### LLM-CTX-002: Workflow ID Tracking

```python
# Auto-generated
client1 = ContextualLLMClient(session_context=..., agent_name="agent1")
assert client1.workflow_id.startswith("wf_")

# Custom
client2 = ContextualLLMClient(session_context=..., workflow_id="custom_workflow")
assert client2.workflow_id == "custom_workflow"

# Updatable
client2.update_workflow_id("updated_workflow")
assert client2.workflow_id == "updated_workflow"
```

**What IS mocked:** `get_llm_client()` only.

**What is NOT mocked:** Auto-generation logic, constructor storage, `update_workflow_id()`
method. Two separate instances don't share state.

**Why workflow ID matters:** The event bus uses it to link together a chain of LLM calls
that belong to the same operation — e.g. all 5 AI calls an agent makes to process one
invoice share the same `workflow_id`.

---

### LLM-CTX-003: Event Emission on Request Start

```python
await client.chat(request)
start_call = calls[0]  # First event = start
assert start_call.kwargs["event_type"] == "llm_request_start"
assert start_call.kwargs["agent_name"] == "test_agent"
```

**What IS mocked:** `get_llm_client`, `mock_llm_client.chat` (returns fake response),
`event_bus` (records calls without sending them).

**What is NOT mocked:**

| What runs for real | What it proves |
|---|---|
| `ContextualLLMClient.chat()` | Real method executes end to end |
| `emit_agent_event(...)` call inside `chat()` | Real event emission logic calls the bus |
| Event payload construction | Real code builds dict with `event_type`, `agent_name`, model, message count |
| `calls[0]` being the start event | Start event fires **before** the AI call, not after |

**Key insight:** `event_bus` is mocked but `emit_agent_event` is called by real code.
The mock acts as a spy — records what was sent without actually sending it.

---

### LLM-CTX-004: Event Emission on Success

```python
await client.chat(request)
success_call = calls[1]  # Second event = success (first was start)
assert success_call.kwargs["event_type"] == "llm_request_success"
assert success_call.kwargs["event_data"]["response_length"] == len("Success response")
assert success_call.kwargs["event_data"]["tool_call_count"] == 1
```

**What IS mocked:** Same as CTX-003, plus `mock_llm_client.chat` returns a response
with 1 tool call.

**What is NOT mocked:** Success path of `chat()`, event payload calculation
(`response_length`, `duration_ms`, `tool_call_count`).

**Key insight:** `calls[0]` = start event, `calls[1]` = success event. Ordering is
implicitly verified — start fires before the call, success fires after.

---

### LLM-CTX-005: Event Emission on Error

```python
mock_llm_client.chat = AsyncMock(side_effect=Exception("API Error"))

with pytest.raises(Exception):
    await client.chat(request)

error_call = calls[1]
assert error_call.kwargs["event_type"] == "llm_request_error"
assert error_call.kwargs["event_data"]["success"] is False
assert "API Error" in error_call.kwargs["event_data"]["error"]
assert error_call.kwargs["event_data"]["error_type"] == "Exception"
```

**What IS mocked:** `get_llm_client`, `mock_llm_client.chat` (raises Exception),
`event_bus`.

**What is NOT mocked:** Error path of `chat()`, error event payload construction
(captures error message and class name), exception re-propagation.

**Key insight:** The error event fires AND the exception still reaches the caller.
Both things must happen — observability and error propagation are not mutually exclusive.

---

### LLM-CTX-006: Child Client Creation

```python
child1 = parent.create_child_client()
assert child1.session_context.user_id == parent.session_context.user_id  # inherited
assert child1.agent_name == "parent_agent.child"                          # auto-named
assert child1.workflow_id != parent.workflow_id                           # independent

child2 = parent.create_child_client(agent_name="custom_child")
assert child2.agent_name == "custom_child"
```

**What IS mocked:** `get_llm_client()` only.

**What is NOT mocked:** `create_child_client()` method, session context copying,
auto name generation, new independent `workflow_id`.

**Key insight:** Same user, same session, different workflow. A parent agent spawning a
sub-agent shares identity but tracks its own work separately.

---

### LLM-CTX-007: Workflow ID Update

```python
client = ContextualLLMClient(..., workflow_id="initial_workflow")
assert client.workflow_id == "initial_workflow"

client.update_workflow_id("new_workflow_123")

assert client.workflow_id == "new_workflow_123"
assert client.context_info["workflow_id"] == "new_workflow_123"  # both places updated
```

**What IS mocked:** `get_llm_client()` only.

**What is NOT mocked:** `update_workflow_id()` method and `context_info` property.

The second assert is the important one — it proves `context_info` reads from the live
attribute, not a cached snapshot from construction time.

---

### LLM-CTX-008: Call Count Tracking

```python
assert client.call_count == 0
await client.chat(request); assert client.call_count == 1
await client.chat(request); assert client.call_count == 2
await client.chat(request); assert client.call_count == 3
```

**What IS mocked:** `get_llm_client`, `mock_llm_client.chat`, `event_bus`.

**What is NOT mocked:** The `call_count` increment logic inside `chat()`. Counter is
checked after each individual call — proves it increments by exactly 1 and persists
across calls.

---

### LLM-CTX-009: Zero Temperature Override Prevention

```python
request = LLMRequest(messages=[...], temperature=0.0)
await client.chat(request)
actual_request = mock_llm_client.chat.call_args[0][0]
assert actual_request.temperature == 0.0  # not swapped to default
```

**What IS mocked:** `get_llm_client`, `mock_llm_client.chat`, `event_bus`.

**What is NOT mocked:** The temperature forwarding logic inside `chat()`.

**Regression for:** `temperature = request.temperature or self.default_temperature` —
the `or` operator treats `0.0` as falsy, silently replacing it with the default.
`ContextualLLMClient` must not re-apply this bug when it delegates.

---

### LLM-CTX-010: Full Request Content Emitted to Redis Event Bus

**What IS mocked:** `get_llm_client`, `mock_llm_client.chat`, `event_bus`.

**What is NOT mocked:** The event payload construction inside `chat()`.

**Key insight — data-exposure documentation test.** The current implementation
serializes the entire `LLMRequest` (including all message content) into the Redis event
payload via `request_dump`. If messages contain PII or financial data, that content
flows into Redis Streams and is visible to any subscriber reading those streams.

---

### LLM-CTX-011: Full Response Content Emitted to Redis Event Bus

**What IS mocked:** `get_llm_client`, `mock_llm_client.chat`, `event_bus`.

**What is NOT mocked:** The success event payload construction inside `chat()`.

**Key insight — paired with CTX-010.** The success event payload includes
`response_content` (the raw LLM reply). If the model echoes back sensitive input,
that content is also stored in Redis Streams alongside the request dump.

---

### LLM-CTX-ERR-001: Event Emission Failure Resilience

```python
mock_event_bus.emit_agent_event = AsyncMock(side_effect=Exception("Event bus error"))

with pytest.raises(Exception) as exc_info:
    await client.chat(request)

assert "Event bus error" in str(exc_info.value)
```

**What IS mocked:** `get_llm_client`, `mock_llm_client.chat` (would succeed if reached),
`event_bus` (raises exception).

**What is NOT mocked:** The real error propagation path when the event bus fails before
the AI is even called.

**Key insight — bug documentation test.** The AI call would have succeeded, but the
start event fires first and crashes, so the AI call never happens. The test locks in
the current broken behaviour with a TODO comment. When fixed, this test should be
updated to assert the AI call still completes despite the event failure.

---

### LLM-CTX-EDGE-001: Concurrent Client Access

```python
requests = [client.chat(LLMRequest(...)) for i in range(5)]
responses = await asyncio.gather(*requests)  # all 5 run simultaneously

assert len(responses) == 5
assert all(r.success for r in responses)
assert client.call_count == 5
```

**What IS mocked:** `get_llm_client`, `event_bus`, and a custom `mock_chat` with
`asyncio.sleep(0.01)` to simulate real async interleaving.

**What is NOT mocked:**

| What runs for real | What it proves |
|---|---|
| `asyncio.gather()` with 5 tasks | Real concurrency — tasks interleave during the sleep |
| `call_count` reaching exactly 5 | Counter handles concurrent increments without losing counts |
| All 5 responses `success=True` | No request silently fails during concurrent execution |

---

### LLM-CTX-EDGE-002: LLMRequest Object Not Mutated By ContextualLLMClient

```python
provider_before = request.provider
model_before    = request.model
temp_before     = request.temperature

await client.chat(request)

assert request.provider    == provider_before
assert request.model       == model_before
assert request.temperature == temp_before
```

**What IS mocked:** `get_llm_client`, `mock_llm_client.chat`, `event_bus`.

**What is NOT mocked:** Any field-modification logic (or lack thereof) inside `chat()`.

**Regression for:** `ContextualLLMClient` applying defaults directly to `request`
before delegating — callers that inspect the request after the call would see
unexpected mutations.

---

### LLM-CTX-EDGE-003: Zero Temperature Shows Default In Event Log

```python
request = LLMRequest(messages=[...], temperature=0.0)
await client.chat(request)
start_event = calls[0].kwargs["event_data"]
assert start_event["temperature"] == 0.0  # not 0.7
```

**What IS mocked:** `get_llm_client`, `mock_llm_client.chat`, `event_bus`.

**What is NOT mocked:** The event payload `temperature` field inside `chat()`.

**Companion to CTX-009.** Even if the forwarded temperature is correct, the emitted
event must also reflect `0.0` — not the client default. Misleading event data makes
debugging harder when tracing why an AI call used a specific temperature.

---

### LLM-CTX-EDGE-004: Full Request and Response Serialized Into Redis Event

**What IS mocked:** `get_llm_client`, `mock_llm_client.chat`, `event_bus`.

**What is NOT mocked:** The full event payload construction in `chat()`.

**Key insight — security documentation test.** Verifies that the Redis event payload
contains the raw prompt text (`request_dump`) and raw response content
(`response_content`). This is flagged as a data-exposure risk: any process reading
these Redis Streams receives complete conversation content, not just metadata.
The test locks in the current behaviour so any future change (e.g. redacting PII
before emission) is explicit and deliberate.

---

### LLM-CONT-GSI-001: Google Sheets Integration Verification

**Nothing is mocked.** This is the only test in the file that talks to a real external
service. It connects to the actual Google Sheets API, opens the real spreadsheet, and
checks that the Summary worksheet has the expected headers. If credentials are not
configured locally, the test skips automatically via `pytest.skip()`.

---

## Google Sheets Tab Routing

The `pytest_google_sheets.py` plugin automatically routes test results to the correct
tab based on the test file path:

| Test File | Google Sheets Tab |
|---|---|
| `tests/unit/llm/test_llm_client.py` | LLM Client |
| `tests/unit/llm/test_mock_client.py` | LLM Mock Client |
| `tests/unit/llm/test_ollama_client.py` | LLM Ollama Client |
| `tests/unit/llm/test_openai_client.py` | LLM OpenAI Client |
| `tests/unit/llm/test_contextual_client.py` | LLM Contextual Client |
| `tests/unit/vendor/...` | Isolation Testing Framework TCs |
| `tests/unit/auth/...` | Secure Session Management |

LLM files are checked first (by filename) before the generic keyword map to avoid
false matches on words like `mock` or `client` appearing in other test paths.
