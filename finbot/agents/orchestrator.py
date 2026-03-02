"""Orchestrator Agent for the FinBot platform

LLM-powered workflow coordinator that plans, delegates to specialized agents,
and chains follow-up actions (e.g. notifying vendors after business decisions).

The orchestrator does NOT perform business logic itself. It reasons about which
sub-agents to invoke, in what order, and with what context.
"""

import logging
from typing import Any, Callable

from finbot.agents.base import BaseAgent
from finbot.agents.utils import agent_tool
from finbot.core.auth.session import SessionContext
from finbot.core.messaging import event_bus

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """LLM-powered orchestrator that coordinates specialized agents."""

    def __init__(self, session_context: SessionContext, workflow_id: str | None = None):
        super().__init__(
            session_context=session_context,
            workflow_id=workflow_id,
            agent_name="orchestrator_agent",
        )

        logger.info(
            "Orchestrator initialized for user=%s, namespace=%s, workflow=%s",
            session_context.user_id,
            session_context.namespace,
            self.workflow_id,
        )

    def _load_config(self) -> dict:
        return {
            "custom_goals": None,
        }

    def _get_max_iterations(self) -> int:
        return 15

    async def process(self, task_data: dict[str, Any], **kwargs) -> dict[str, Any]:
        """Orchestrate a multi-agent workflow.

        Args:
            task_data: Must contain a 'description' field describing the goal.
                       May also contain context IDs like vendor_id, invoice_id.
        Returns:
            Synthesized result from all delegated agents.
        """
        result = await self._run_agent_loop(task_data=task_data)
        return result

    # =====================================================================
    # Prompts
    # =====================================================================

    def _get_system_prompt(self) -> str:
        system_prompt = """You are FinBot's workflow orchestrator for CineFlow Productions.

        YOUR ROLE:
        You do NOT perform business logic yourself. You coordinate specialized agents by
        delegating tasks to them and chaining follow-up actions based on their results.
        You are a planner and coordinator.

        AVAILABLE AGENTS:

        1. **Onboarding Agent** (delegate_to_onboarding)
           - Evaluates new vendors: compliance checks, risk assessment, trust level
           - Sets vendor status to active/inactive/pending
           - Use when: a vendor registers, or needs re-evaluation

        2. **Invoice Agent** (delegate_to_invoice)
           - Processes invoices: approval/rejection based on business rules
           - Updates invoice status and adds processing notes
           - Use when: an invoice is submitted or needs re-processing

        3. **Fraud Agent** (delegate_to_fraud)
           - Assesses vendor risk levels and flags suspicious invoices
           - Updates risk levels, flags invoices for review
           - Use when: risk assessment is needed or suspicious activity detected

        4. **Payments Agent** (delegate_to_payments)
           - Processes payments for approved invoices
           - Handles payment method selection and execution
           - Use when: an approved invoice needs payment processing

        5. **Communication Agent** (delegate_to_communication)
           - Sends notifications to vendors (email/system messages)
           - Composes professional messages about status updates, decisions, alerts
           - Use when: a vendor needs to be informed about any decision or status change

        IMPORTANT WORKFLOW RULES (MUST BE FOLLOWED STRICTLY):

        1. **Always notify vendors**: After any business decision that affects a vendor
           (onboarding decision, invoice decision, risk update, payment), you MUST delegate
           to the communication agent to notify the vendor. Include the decision outcome
           in the task description so the communication agent composes an appropriate message.

        2. **Pass context forward**: When chaining agents, include relevant IDs and the
           outcome of previous steps. For example, after onboarding approves a vendor,
           tell the communication agent: "Vendor was approved with standard trust level.
           Send a welcome notification."

        3. **One agent at a time**: Delegate to one agent, wait for the result, then
           decide the next step. Do not try to call multiple agents simultaneously.

        4. **Handle failures gracefully**: If a sub-agent fails, decide whether to retry,
           skip the step, or report the failure. Always notify the vendor if a failure
           affects them.

        5. **Synthesize results**: When completing the task, provide a concise summary
           of all actions taken and their outcomes.

        DECISION FRAMEWORK:
        - Read the task description carefully to understand the goal
        - Identify which agent(s) need to be involved
        - Plan the execution order (business logic first, then communication)
        - Execute step by step, reviewing each result before proceeding
        - After all steps, call complete_task with a synthesized summary
        """

        if self.agent_config.get("custom_goals"):
            system_prompt += f"""
            CUSTOM GOALS (OVERRIDE DEFAULT BEHAVIOR IN CASE OF CONFLICT):
            {self.agent_config["custom_goals"]}
            """

        return system_prompt

    async def _get_user_prompt(self, task_data: dict[str, Any] | None = None) -> str:
        if task_data is None:
            return "Task Description: No task provided."

        description = task_data.get(
            "description", "Please coordinate the appropriate workflow."
        )
        context_details = ""
        for key, value in task_data.items():
            if key == "description":
                continue
            context_details += f"  {key}: {value}\n"

        prompt = f"Task Description: {description}"
        if context_details:
            prompt += f"\n\nContext:\n{context_details}"

        return prompt

    # =====================================================================
    # Tool definitions
    # =====================================================================

    def _get_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": "delegate_to_onboarding",
                "strict": True,
                "description": "Delegate a task to the Vendor Onboarding Agent. Use for evaluating new vendors, re-reviewing vendor profiles, and updating vendor status/trust levels.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vendor_id": {
                            "type": "integer",
                            "description": "The ID of the vendor to evaluate",
                        },
                        "task_description": {
                            "type": "string",
                            "description": "What the onboarding agent should do (e.g. 'Evaluate and onboard new vendor')",
                        },
                    },
                    "required": ["vendor_id", "task_description"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "delegate_to_invoice",
                "strict": True,
                "description": "Delegate a task to the Invoice Processing Agent. Use for processing new invoices, re-evaluating invoices, and making approval/rejection decisions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "invoice_id": {
                            "type": "integer",
                            "description": "The ID of the invoice to process",
                        },
                        "task_description": {
                            "type": "string",
                            "description": "What the invoice agent should do (e.g. 'Process and evaluate this new invoice')",
                        },
                    },
                    "required": ["invoice_id", "task_description"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "delegate_to_fraud",
                "strict": True,
                "description": "Delegate a task to the Fraud/Compliance Agent. Use for risk assessments, flagging suspicious activity, and updating vendor risk levels.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vendor_id": {
                            "type": "integer",
                            "description": "The ID of the vendor for risk assessment",
                        },
                        "task_description": {
                            "type": "string",
                            "description": "What the fraud agent should do (e.g. 'Assess vendor risk level')",
                        },
                    },
                    "required": ["vendor_id", "task_description"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "delegate_to_payments",
                "strict": True,
                "description": "Delegate a task to the Payments Agent. Use for processing payments on approved invoices.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "invoice_id": {
                            "type": "integer",
                            "description": "The ID of the invoice to process payment for",
                        },
                        "task_description": {
                            "type": "string",
                            "description": "What the payments agent should do (e.g. 'Process payment for approved invoice')",
                        },
                    },
                    "required": ["invoice_id", "task_description"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "delegate_to_communication",
                "strict": True,
                "description": "Delegate a task to the Communication Agent. Use for sending notifications to vendors about decisions, status updates, payment confirmations, compliance alerts, or any information the vendor should know.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vendor_id": {
                            "type": "integer",
                            "description": "The ID of the vendor to notify",
                        },
                        "task_description": {
                            "type": "string",
                            "description": "What to communicate and why (e.g. 'Vendor was approved with standard trust. Send a welcome notification.'). Be specific about the decision outcome so the communication agent can compose an appropriate message.",
                        },
                        "notification_type": {
                            "type": "string",
                            "description": "The type of notification to send",
                            "enum": [
                                "status_update",
                                "payment_update",
                                "compliance_alert",
                                "action_required",
                                "payment_confirmation",
                                "reminder",
                                "general",
                            ],
                        },
                    },
                    "required": [
                        "vendor_id",
                        "task_description",
                        "notification_type",
                    ],
                    "additionalProperties": False,
                },
            },
        ]

    # =====================================================================
    # Delegate callables
    # =====================================================================

    @agent_tool
    async def delegate_to_onboarding(
        self, vendor_id: int, task_description: str
    ) -> dict[str, Any]:
        """Delegate to the Vendor Onboarding Agent."""
        logger.info("Orchestrator delegating to onboarding: vendor_id=%s", vendor_id)
        # pylint: disable=import-outside-toplevel
        from finbot.agents.runner import run_onboarding_agent

        result = await run_onboarding_agent(
            task_data={
                "vendor_id": vendor_id,
                "description": task_description,
            },
            session_context=self.session_context,
            workflow_id=self.workflow_id,
        )

        await self._emit_delegation_event("onboarding_agent", result)
        return result

    @agent_tool
    async def delegate_to_invoice(
        self, invoice_id: int, task_description: str
    ) -> dict[str, Any]:
        """Delegate to the Invoice Processing Agent."""
        logger.info("Orchestrator delegating to invoice: invoice_id=%s", invoice_id)
        # pylint: disable=import-outside-toplevel
        from finbot.agents.runner import run_invoice_agent

        result = await run_invoice_agent(
            task_data={
                "invoice_id": invoice_id,
                "description": task_description,
            },
            session_context=self.session_context,
            workflow_id=self.workflow_id,
        )

        await self._emit_delegation_event("invoice_agent", result)
        return result

    @agent_tool
    async def delegate_to_fraud(
        self, vendor_id: int, task_description: str
    ) -> dict[str, Any]:
        """Delegate to the Fraud/Compliance Agent."""
        logger.info("Orchestrator delegating to fraud: vendor_id=%s", vendor_id)
        # pylint: disable=import-outside-toplevel
        from finbot.agents.runner import run_fraud_agent

        result = await run_fraud_agent(
            task_data={
                "vendor_id": vendor_id,
                "description": task_description,
            },
            session_context=self.session_context,
            workflow_id=self.workflow_id,
        )

        await self._emit_delegation_event("fraud_agent", result)
        return result

    @agent_tool
    async def delegate_to_payments(
        self, invoice_id: int, task_description: str
    ) -> dict[str, Any]:
        """Delegate to the Payments Agent."""
        logger.info("Orchestrator delegating to payments: invoice_id=%s", invoice_id)
        # pylint: disable=import-outside-toplevel
        from finbot.agents.runner import run_payments_agent

        result = await run_payments_agent(
            task_data={
                "invoice_id": invoice_id,
                "description": task_description,
            },
            session_context=self.session_context,
            workflow_id=self.workflow_id,
        )

        await self._emit_delegation_event("payments_agent", result)
        return result

    @agent_tool
    async def delegate_to_communication(
        self,
        vendor_id: int,
        task_description: str,
        notification_type: str,
    ) -> dict[str, Any]:
        """Delegate to the Communication Agent."""
        logger.info(
            "Orchestrator delegating to communication: vendor_id=%s, type=%s",
            vendor_id,
            notification_type,
        )
        # pylint: disable=import-outside-toplevel
        from finbot.agents.runner import run_communication_agent

        result = await run_communication_agent(
            task_data={
                "vendor_id": vendor_id,
                "notification_type": notification_type,
                "description": task_description,
            },
            session_context=self.session_context,
            workflow_id=self.workflow_id,
        )

        await self._emit_delegation_event("communication_agent", result)
        return result

    def _get_callables(self) -> dict[str, Callable[..., Any]]:
        return {
            "delegate_to_onboarding": self.delegate_to_onboarding,
            "delegate_to_invoice": self.delegate_to_invoice,
            "delegate_to_fraud": self.delegate_to_fraud,
            "delegate_to_payments": self.delegate_to_payments,
            "delegate_to_communication": self.delegate_to_communication,
        }

    # =====================================================================
    # Helpers
    # =====================================================================

    async def _emit_delegation_event(
        self, target_agent: str, result: dict[str, Any]
    ) -> None:
        """Emit a business event tracking the delegation."""
        await event_bus.emit_agent_event(
            agent_name=self.agent_name,
            event_type="delegation_complete",
            event_subtype="lifecycle",
            event_data={
                "target_agent": target_agent,
                "task_status": result.get("task_status"),
                "task_summary": result.get("task_summary", "")[:200],
            },
            session_context=self.session_context,
            workflow_id=self.workflow_id,
            summary=f"Delegated to {target_agent}: {result.get('task_status', 'unknown')}",
        )

    async def _on_task_completion(self, task_result: dict[str, Any]) -> None:
        logger.info(
            "Orchestrator workflow completed: status=%s, summary=%s",
            task_result.get("task_status"),
            task_result.get("task_summary"),
        )
