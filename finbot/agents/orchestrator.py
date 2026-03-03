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

    _max_delegation_attempts: int = 2

    def __init__(self, session_context: SessionContext, workflow_id: str | None = None):
        super().__init__(
            session_context=session_context,
            workflow_id=workflow_id,
            agent_name="orchestrator_agent",
        )
        self._delegation_attempts: dict[str, int] = {}

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
           - Evaluates vendor profiles: compliance, risk assessment, trust level
           - Sets vendor status to active/inactive/pending

        2. **Invoice Agent** (delegate_to_invoice)
           - Processes invoices: approval/rejection based on business rules
           - Updates invoice status and adds processing notes

        3. **Fraud Agent** (delegate_to_fraud)
           - Assesses vendor risk levels and flags suspicious invoices
           - Updates risk levels, flags invoices for review

        4. **Payments Agent** (delegate_to_payments)
           - Processes payments for approved invoices
           - Handles payment method selection and execution

        5. **Communication Agent** (delegate_to_communication)
           - Sends notifications to vendors (email/system messages)
           - Composes professional messages about status updates, decisions, alerts

        WORKFLOW RECIPES (follow the matching recipe step-by-step):

        **Vendor Onboarding** (task mentions new vendor registration):
          Step 1: delegate_to_onboarding -- evaluate and set vendor status, trust level, risk level
          Step 2: delegate_to_fraud -- assess initial risk profile for the new vendor; pass the onboarding outcome in the task description
          Step 3: delegate_to_communication -- notify the vendor of the onboarding decision; include outcomes from steps 1 and 2

        **Vendor Re-Review** (task mentions vendor re-review or re-evaluation):
          Step 1: delegate_to_onboarding -- re-evaluate the vendor profile
          Step 2: delegate_to_fraud -- re-assess risk with the updated profile; pass the re-evaluation outcome
          Step 3: delegate_to_communication -- notify the vendor of the updated decision

        **Invoice Processing** (task mentions new invoice submitted):
          Step 1: delegate_to_invoice -- evaluate and approve/reject the invoice
          Step 2: delegate_to_fraud -- check the invoice for fraud patterns; pass the invoice decision
          Step 3: If the invoice was approved in step 1, delegate_to_payments -- process payment for the approved invoice
          Step 4: delegate_to_communication -- MANDATORY: notify the vendor of the FINAL outcome including payment status.
                  Use notification_type "payment_confirmation" if payment was processed, or "status_update" otherwise.
                  This step must ALWAYS be executed as the last step, even if payment succeeded. Do NOT call complete_task before this step.

        **Invoice Reprocessing** (task mentions invoice re-processing or re-evaluation):
          Step 1: delegate_to_invoice -- re-evaluate the invoice
          Step 2: delegate_to_fraud -- re-check for fraud patterns; pass the invoice decision
          Step 3: If the invoice was approved in step 1, delegate_to_payments -- process payment
          Step 4: delegate_to_communication -- MANDATORY: notify the vendor of the FINAL outcome including payment status.
                  Use notification_type "payment_confirmation" if payment was processed, or "status_update" otherwise.
                  This step must ALWAYS be executed as the last step. Do NOT call complete_task before this step.

        IMPORTANT WORKFLOW RULES (MUST BE FOLLOWED STRICTLY):

        1. **Follow the recipe**: Identify the matching workflow recipe from the task description
           and execute ALL steps in order. Do not skip steps unless a previous step failed
           and the subsequent step depends on its success.

        2. **Pass context forward**: When chaining agents, include relevant IDs and the
           outcome of previous steps in the task_description. For example, after onboarding
           approves a vendor, tell the fraud agent: "Vendor was approved with standard trust
           level. Assess initial risk profile."

        3. **One agent at a time**: Delegate to one agent, wait for the result, then
           proceed to the next step. Do not try to call multiple agents simultaneously.

        4. **Handle failures gracefully**: If a sub-agent fails, skip steps that depend
           on its success and continue with remaining steps. Always notify the vendor
           via the communication agent, even if earlier steps failed.

        5. **Synthesize results**: After all steps, call complete_task with a concise
           summary of all actions taken and their outcomes.
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

    def _check_delegation_limit(self, agent_key: str) -> dict[str, Any] | None:
        """Track delegation attempts and return a failure result if the cap is reached."""
        self._delegation_attempts[agent_key] = (
            self._delegation_attempts.get(agent_key, 0) + 1
        )
        attempt = self._delegation_attempts[agent_key]
        if attempt > self._max_delegation_attempts:
            logger.warning(
                "Delegation cap reached for %s: %d/%d attempts",
                agent_key,
                attempt,
                self._max_delegation_attempts,
            )
            return {
                "task_status": "failed",
                "task_summary": (
                    f"Maximum delegation attempts ({self._max_delegation_attempts}) "
                    f"reached for {agent_key}. Moving on to the next step."
                ),
            }
        return None

    @agent_tool
    async def delegate_to_onboarding(
        self, vendor_id: int, task_description: str
    ) -> dict[str, Any]:
        """Delegate to the Vendor Onboarding Agent."""
        if cap_result := self._check_delegation_limit("onboarding"):
            return cap_result
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
        if cap_result := self._check_delegation_limit("invoice"):
            return cap_result
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
        if cap_result := self._check_delegation_limit("fraud"):
            return cap_result
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
        if cap_result := self._check_delegation_limit("payments"):
            return cap_result
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

        result["next_step"] = (
            "IMPORTANT: You MUST now delegate_to_communication to notify the vendor "
            "about this payment outcome. Use notification_type 'payment_confirmation'. "
            "Do NOT call complete_task until the vendor has been notified."
        )
        return result

    @agent_tool
    async def delegate_to_communication(
        self,
        vendor_id: int,
        task_description: str,
        notification_type: str,
    ) -> dict[str, Any]:
        """Delegate to the Communication Agent."""
        if cap_result := self._check_delegation_limit("communication"):
            return cap_result
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
