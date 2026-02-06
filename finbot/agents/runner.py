"""Agent Runner"""

import asyncio
import logging
import secrets
from typing import Type

from finbot.agents.base import BaseAgent
from finbot.agents.specialized.invoice import InvoiceAgent
from finbot.agents.specialized.onboarding import VendorOnboardingAgent
from finbot.core.auth.session import SessionContext
from finbot.core.messaging import event_bus

logger = logging.getLogger(__name__)


async def run_agent_with_retry(
    agent_class: Type[BaseAgent],
    session_context: SessionContext,
    task_data: dict,
    max_retries: int = 3,
    workflow_id: str | None = None,
) -> dict:
    """Run an agent with automatic retry on failure
    Args:
        agent_class: The class of the agent to instantiate
        session_context: The session context from the request
        task_data: The task data to pass on to the agent
        max_retries: The maximum number of retries
        workflow_id: Optional workflow id
    Returns:
        Agent execution result
    """
    workflow_id = workflow_id or f"wf_{secrets.token_urlsafe(12)}"
    for attempt in range(max_retries):
        try:
            agent = agent_class(
                session_context=session_context,
                workflow_id=workflow_id,
            )
            result = await agent.process(task_data=task_data)

            logger.info(
                "Agent %s completed (workflow=%s): %s",
                agent.agent_name,
                workflow_id,
                result.get("task_summary", ""),
            )

            return result

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Agent %s attempt %d/%d failed: %s",
                agent.agent_name,
                attempt + 1,
                max_retries,
                e,
                exc_info=True,
            )
            if attempt < max_retries - 1:
                retry_delay = 2**attempt
                # Emit retry event
                await event_bus.emit_agent_event(
                    agent_name=agent.agent_name,
                    event_type="agent_retry",
                    event_subtype="error",
                    event_data={
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "retry_delay_seconds": retry_delay,
                    },
                    session_context=session_context,
                    workflow_id=workflow_id,
                    summary=f"Agent retry {attempt + 1}/{max_retries}: {type(e).__name__}",
                )
                await asyncio.sleep(retry_delay)
            else:
                logger.critical(
                    "Agent %s permanently failed after %d attempts",
                    agent.agent_name,
                    max_retries,
                )
                await event_bus.emit_business_event(
                    event_type="agent.failed",
                    event_subtype="error",
                    event_data={
                        "agent_name": agent.agent_name,
                        "workflow_id": workflow_id,
                        "error": str(e),
                        "task_data": task_data,
                    },
                    session_context=session_context,
                    workflow_id=workflow_id,
                    summary=f"Agent failed permanently: {agent.agent_name} ({type(e).__name__})",
                )
                return {
                    "task_status": "failed",
                    "task_summary": f"Agent {agent.agent_name} permanently failed after {max_retries} attempts: {str(e)}",
                }
    return {
        "task_status": "failed",
        "task_summary": f"Agent {agent.agent_name} failed due to unknown reason",
    }


async def run_onboarding_agent(
    task_data: dict,
    session_context: SessionContext,
    workflow_id: str | None = None,
) -> dict:
    """Run the onboarding agent for a vendor
    Args:
        task_data: The task data to pass on to the agent
        session_context: The session context from the request
        workflow_id: Optional workflow id
    Returns:
        Agent execution result
    """
    return await run_agent_with_retry(
        agent_class=VendorOnboardingAgent,
        session_context=session_context,
        task_data=task_data,
        workflow_id=workflow_id,
    )


async def run_invoice_agent(
    task_data: dict,
    session_context: SessionContext,
    workflow_id: str | None = None,
) -> dict:
    """Run the invoice agent for an invoice
    Args:
        task_data: The task data to pass on to the agent
        session_context: The session context from the request
        workflow_id: Optional workflow id
    Returns:
        Agent execution result
    """
    return await run_agent_with_retry(
        agent_class=InvoiceAgent,
        session_context=session_context,
        task_data=task_data,
        workflow_id=workflow_id,
    )
