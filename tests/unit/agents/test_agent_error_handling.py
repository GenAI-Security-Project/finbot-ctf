"""
Unit tests for agent error handling -- Issue #589.

Verifies that unresolvable vendor_id or invoice_id in task_data does not
escape the agent loop's error handling, that prompt construction degrades
gracefully when database entities are absent, that setup exceptions
in BaseAgent._run_agent_loop follow the established task completion path,
and that resource cleanup in finally executes reliably even if MCP disconnect fails.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Generator
from unittest.mock import AsyncMock, patch

import pytest

from finbot.agents.base import BaseAgent
from finbot.agents.specialized.invoice import InvoiceAgent
from finbot.agents.specialized.onboarding import VendorOnboardingAgent
from finbot.core.auth.session import SessionContext, session_manager
from finbot.core.data.database import db_session
from finbot.core.data.models import Invoice, LLMResponse, Vendor
from finbot.core.data.repositories import VendorRepository
from finbot.core.messaging import event_bus


@pytest.fixture(autouse=True)
def mock_event_bus_emission() -> Generator[None, None, None]:
    """Mock async Redis event emissions so unit tests are isolated and offline."""
    with (
        patch.object(event_bus, "emit_agent_event", new_callable=AsyncMock),
        patch.object(event_bus, "emit_business_event", new_callable=AsyncMock),
    ):
        yield


def _create_session_context(email: str) -> SessionContext:
    """Helper to create SessionContext for testing."""
    session = session_manager.create_session(
        email=email,
        user_agent="AgentErrorHandlingTest/1.0",
    )
    created_at = datetime.now(UTC)
    expires_at = created_at + timedelta(hours=24)

    return SessionContext(
        session_id=session.session_id,
        user_id=f"user_{email.split('@')[0]}",
        email=email,
        namespace=f"user_{email.split('@')[0]}",
        is_temporary=False,
        created_at=created_at,
        expires_at=expires_at,
    )


# ============================================================================
# VendorOnboardingAgent Prompt & Lookup Error Handling Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_vendor_prompt_with_valid_vendor_id() -> None:
    """Valid seeded vendor ID populates services and agent_notes in prompt."""
    session_context = _create_session_context("valid_vendor@example.com")
    with db_session() as db:
        repo = VendorRepository(db, session_context)
        vendor = repo.create_vendor(
            company_name="Alpha Tech",
            vendor_category="Technology",
            industry="Software",
            services="Cloud Hosting and Security",
            contact_name="Alice Alpha",
            email="alice@alphatech.com",
            tin="11-1111111",
            bank_account_number="123456789012",
            bank_name="Test Bank",
            bank_routing_number="021000021",
            bank_account_holder_name="Alice Alpha",
        )
        vendor.agent_notes = "Verified tier-1 strategic partner"  # type: ignore[assignment]
        db.commit()
        vendor_id = vendor.id

    agent = VendorOnboardingAgent(session_context=session_context)
    prompt = await agent._get_user_prompt({"vendor_id": vendor_id})

    assert "Cloud Hosting and Security" in prompt
    assert "Verified tier-1 strategic partner" in prompt


@pytest.mark.unit
@pytest.mark.asyncio
async def test_vendor_prompt_with_missing_integer_vendor_id() -> None:
    """Non-existent integer vendor ID does not raise ValueError; prompt is generated."""
    session_context = _create_session_context("missing_vendor_int@example.com")
    agent = VendorOnboardingAgent(session_context=session_context)

    # Vendor 999999 does not exist in this namespace
    prompt = await agent._get_user_prompt({"vendor_id": 999999})

    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert "vendor" in prompt.lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_vendor_prompt_with_string_vendor_id() -> None:
    """Non-integer string vendor ID does not raise ValueError; prompt is generated."""
    session_context = _create_session_context("missing_vendor_str@example.com")
    agent = VendorOnboardingAgent(session_context=session_context)

    prompt = await agent._get_user_prompt({"vendor_id": "VEND-001"})

    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert "VEND-001" in prompt


@pytest.mark.unit
@pytest.mark.asyncio
async def test_vendor_process_with_unresolvable_vendor_id() -> None:
    """VendorOnboardingAgent.process() with unresolvable vendor ID passes prompt to LLM and completes."""
    session_context = _create_session_context("vendor_process_missing@example.com")
    agent = VendorOnboardingAgent(session_context=session_context)

    mock_llm_response = LLMResponse(
        content=None,
        tool_calls=[
            {
                "name": "complete_task",
                "call_id": "call_vendor_001",
                "arguments": {
                    "task_status": "failed",
                    "task_summary": "Vendor identifier VEND-001 could not be resolved in the database.",
                },
            }
        ],
    )

    with patch.object(
        agent.llm_client, "chat", new_callable=AsyncMock, return_value=mock_llm_response
    ) as mock_chat:
        result = await agent.process({"action": "get_progress", "vendor_id": "VEND-001"})

        # Verify LLM was invoked with the constructed prompt containing the identifier
        mock_chat.assert_awaited_once()
        assert mock_chat.await_args is not None
        called_request = mock_chat.await_args.kwargs["request"]
        user_message = next(m for m in called_request.messages if m["role"] == "user")
        assert "VEND-001" in user_message["content"]

        # Verify task completion was returned from the tool call rather than a crash or stall
        assert isinstance(result, dict)
        assert result["task_status"] == "failed"
        assert (
            result["task_summary"]
            == "Vendor identifier VEND-001 could not be resolved in the database."
        )


# ============================================================================
# InvoiceAgent Prompt & Lookup Error Handling Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invoice_prompt_with_valid_invoice_id() -> None:
    """Valid seeded invoice ID populates description and agent_notes in prompt."""
    session_context = _create_session_context("valid_invoice@example.com")
    with db_session() as db:
        vendor_repo = VendorRepository(db, session_context)
        vendor = vendor_repo.create_vendor(
            company_name="Beta Services",
            vendor_category="Consulting",
            industry="Finance",
            services="Advisory",
            contact_name="Bob Beta",
            email="bob@betaservices.com",
            tin="22-2222222",
            bank_account_number="987654321098",
            bank_name="Beta Bank",
            bank_routing_number="021000021",
            bank_account_holder_name="Bob Beta",
        )
        invoice = Invoice(
            vendor_id=vendor.id,
            invoice_number="INV-2026-001",
            amount=5000.0,
            description="Q3 Security Architecture Review",
            agent_notes="Pre-approved under MSA 2026",
            status="pending_approval",
            namespace=session_context.namespace,
            invoice_date=datetime.now(UTC) - timedelta(days=5),
            due_date=datetime.now(UTC) + timedelta(days=25),
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        invoice_id = invoice.id

    agent = InvoiceAgent(session_context=session_context)
    prompt = await agent._get_user_prompt({"invoice_id": invoice_id})

    assert "Q3 Security Architecture Review" in prompt
    assert "Pre-approved under MSA 2026" in prompt


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invoice_prompt_with_missing_integer_invoice_id() -> None:
    """Non-existent integer invoice ID does not raise ValueError; prompt is generated."""
    session_context = _create_session_context("missing_invoice_int@example.com")
    agent = InvoiceAgent(session_context=session_context)

    # Invoice 999999 does not exist in this namespace
    prompt = await agent._get_user_prompt({"invoice_id": 999999})

    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert "invoice" in prompt.lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invoice_prompt_with_string_invoice_id() -> None:
    """Non-integer string invoice ID does not raise ValueError; prompt is generated."""
    session_context = _create_session_context("missing_invoice_str@example.com")
    agent = InvoiceAgent(session_context=session_context)

    prompt = await agent._get_user_prompt({"invoice_id": "INV-001"})

    assert isinstance(prompt, str)
    assert len(prompt) > 0
    assert "INV-001" in prompt


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invoice_process_with_unresolvable_invoice_id() -> None:
    """InvoiceAgent.process() with unresolvable invoice ID passes prompt to LLM and completes."""
    session_context = _create_session_context("invoice_process_missing@example.com")
    agent = InvoiceAgent(session_context=session_context)

    mock_llm_response = LLMResponse(
        content=None,
        tool_calls=[
            {
                "name": "complete_task",
                "call_id": "call_invoice_001",
                "arguments": {
                    "task_status": "failed",
                    "task_summary": "Invoice identifier INV-001 could not be resolved.",
                },
            }
        ],
    )

    with patch.object(
        agent.llm_client, "chat", new_callable=AsyncMock, return_value=mock_llm_response
    ) as mock_chat:
        result = await agent.process({"action": "review_invoice", "invoice_id": "INV-001"})

        # Verify LLM was invoked with the constructed prompt containing the identifier
        mock_chat.assert_awaited_once()
        assert mock_chat.await_args is not None
        called_request = mock_chat.await_args.kwargs["request"]
        user_message = next(m for m in called_request.messages if m["role"] == "user")
        assert "INV-001" in user_message["content"]

        # Verify task completion was returned from the tool call rather than a crash or stall
        assert isinstance(result, dict)
        assert result["task_status"] == "failed"
        assert result["task_summary"] == "Invoice identifier INV-001 could not be resolved."


# ============================================================================
# BaseAgent Setup Exception Handling & MCP Cleanup Tests
# ============================================================================


class FailingSetupAgent(BaseAgent):
    """Test agent whose prompt construction fails unexpectedly."""

    def _load_config(self) -> dict[str, Any]:
        return {}

    def _get_system_prompt(self) -> str:
        return "System prompt for failing setup agent"

    async def _get_user_prompt(self, task_data: dict[str, Any] | None = None) -> str:
        raise RuntimeError("Simulated unexpected prompt construction failure")

    def _get_tool_definitions(self) -> list[dict[str, Any]]:
        return []

    def _get_callables(self) -> dict[str, Callable[..., Any]]:
        return {}

    async def process(self, task_data: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return await self._run_agent_loop(task_data=task_data)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_base_agent_catches_setup_exception_and_returns_failed_status() -> None:
    """Unexpected exception in _get_user_prompt is caught by setup handler and returns failed task."""
    session_context = _create_session_context("setup_failure@example.com")
    agent = FailingSetupAgent(
        session_context=session_context,
        workflow_id="wf_setup_fail_test",
    )

    result = await agent.process({"action": "do_something"})

    assert isinstance(result, dict)
    assert result["task_status"] == "failed"
    assert "Agent setup failed" in result["task_summary"]
    assert "Simulated unexpected prompt construction failure" in result["task_summary"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_base_agent_cleanup_on_setup_exception() -> None:
    """MCP servers and workflow context are cleaned up even when setup fails."""
    session_context = _create_session_context("cleanup_on_failure@example.com")
    agent = FailingSetupAgent(
        session_context=session_context,
        workflow_id="wf_cleanup_test",
    )

    with patch.object(agent, "_disconnect_mcp_servers", new_callable=AsyncMock) as mock_disconnect:
        result = await agent.process({"action": "do_something"})

        assert result["task_status"] == "failed"
        mock_disconnect.assert_awaited_once()

    # Workflow context should be cleared
    assert "wf_cleanup_test" not in event_bus._workflow_ctx


@pytest.mark.unit
@pytest.mark.asyncio
async def test_base_agent_cleanup_when_mcp_disconnect_fails() -> None:
    """Workflow context is cleared even if MCP disconnection raises an exception."""
    session_context = _create_session_context("mcp_disconnect_fail@example.com")
    agent = FailingSetupAgent(
        session_context=session_context,
        workflow_id="wf_mcp_fail_test",
    )

    with patch.object(
        agent,
        "_disconnect_mcp_servers",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Simulated MCP disconnect crash"),
    ):
        result = await agent.process({"action": "do_something"})

        assert result["task_status"] == "failed"
        assert "Simulated unexpected prompt construction failure" in result["task_summary"]

    # Workflow context MUST be cleared despite MCP disconnect failure
    assert "wf_mcp_fail_test" not in event_bus._workflow_ctx


@pytest.mark.unit
@pytest.mark.asyncio
async def test_base_agent_stall_termination() -> None:
    """Agent terminates with failed status after max stall iterations when no tools called."""
    session_context = _create_session_context("stall_test@example.com")
    agent = VendorOnboardingAgent(session_context=session_context)

    # Return text-only response with no tool calls to deterministically trigger stall detection
    text_only_response = LLMResponse(content="Just thinking out loud...", tool_calls=[])

    with patch.object(
        agent.llm_client, "chat", new_callable=AsyncMock, return_value=text_only_response
    ) as mock_chat:
        result = await agent.process({})

        assert isinstance(result, dict)
        assert result["task_status"] == "failed"
        assert "stalled" in result["task_summary"].lower()
        # Verify it stalled after exactly 2 iterations (max_stall_iterations)
        assert mock_chat.await_count == 2
