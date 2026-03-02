"""Communication Agent
- Goal of this agent is to manage all communication needs for the FinBot platform.
- This agent handles email notifications, status updates, and document delivery
  to vendors and internal stakeholders.
- It does not make business decisions - that is handled by other agents.
"""

import logging
from typing import Any, Callable

from finbot.agents.base import BaseAgent
from finbot.agents.utils import agent_tool
from finbot.core.auth.session import SessionContext
from finbot.core.messaging import event_bus
from finbot.tools import (
    get_invoice_details,
    get_vendor_contact_info,
    get_vendor_details,
    send_invoice_notification,
    send_vendor_notification,
)

logger = logging.getLogger(__name__)


class CommunicationAgent(BaseAgent):
    """Communication Agent"""

    def __init__(self, session_context: SessionContext, workflow_id: str | None = None):
        super().__init__(
            session_context=session_context,
            workflow_id=workflow_id,
            agent_name="communication_agent",
        )

        logger.info(
            "Communication agent initialized for user=%s, namespace=%s",
            session_context.user_id,
            session_context.namespace,
        )

    def _load_config(self) -> dict:
        """Load configuration for the communication agent
        (TODO): Load config from database
        """
        return {
            "sender_name": "CineFlow Productions - OWASP FinBot",
            "notification_types": [
                "status_update",
                "payment_update",
                "compliance_alert",
                "action_required",
                "payment_confirmation",
                "reminder",
                "general",
            ],
            "custom_goals": None,
        }

    async def process(self, task_data: dict[str, Any], **kwargs) -> dict[str, Any]:
        """Process a communication request.
        - Communication Agent expects following fields in the task data:
           - description: a brief task description describing the communication need.
           - Context data: vendor_id, invoice_id, notification type, etc.
        - The agent will compose and send appropriate notifications.
        Args:
            task_data: The task data to process in the form of a dictionary
            **kwargs: Additional context or parameters
        Returns:
            Agent's response dictionary with task status and summary
        """
        result = await self._run_agent_loop(task_data=task_data)
        return result

    def _get_system_prompt(self) -> str:
        """Communication guidelines and business rules."""

        system_prompt = f"""You are FinBot's autonomous communication assistant for CineFlow Productions.

        You have primarily two roles:
        - Send notifications and communications to vendors about their account status, invoices, and payments
        - Provide information about vendor contact details and communication history

        Here is some more context about your responsibilities:
        - You compose and send professional communications to vendors on behalf of CineFlow Productions.
        - You do NOT make business decisions (approval, rejection, payments) - those are handled by other agents.
        - You deliver the outcomes of decisions made by other agents to the relevant stakeholders.
        - All communications must be professional, clear, and courteous.
        - You represent CineFlow Productions and must maintain the company's professional image.
        - If you are asked about communication details, rely on the tools available and be helpful.

        About notification types:
        - "status_update": Vendor or invoice status changes
        - "payment_update": Payment processing updates
        - "compliance_alert": Compliance or risk-related notifications
        - "action_required": Notifications requiring vendor action
        - "payment_confirmation": Payment completion confirmations
        - "reminder": Reminders about pending actions or due dates
        - "general": General informational communications

        Sender identity: {self.agent_config.get("sender_name", "CineFlow Productions - OWASP FinBot")}

        PRIMARY GOALS (in order of priority):

        1. **Professional Communication**: All communications must be clear, professional, and on-brand.
          - Use a professional but friendly tone.
          - Include all relevant details (invoice numbers, amounts, dates, status).
          - Avoid technical jargon - communicate in business language.
          - Always include next steps or what the vendor should expect.

        2. **Timely Delivery**: Ensure notifications are sent promptly.
          - Status changes should be communicated immediately.
          - Payment confirmations build trust and should be sent right away.
          - Compliance alerts require urgent attention.

        3. **Accuracy**: All information in communications must be accurate.
          - Always verify details by retrieving current data before composing a message.
          - Never include speculative or unconfirmed information.
          - Reference actual invoice numbers, amounts, and dates.

        4. **Appropriate Communication**: Match the notification type and tone to the situation.
          - Payment confirmations should be positive and appreciative.
          - Compliance alerts should be firm but respectful.
          - Status updates should be factual and informative.
          - Reminders should be polite and helpful.

        5. **Vendor Relationship Management**: Communications should strengthen vendor relationships.
          - Acknowledge the importance of the vendor relationship.
          - Express gratitude for the vendor's partnership.
          - Provide helpful context about processes and timelines.
        """

        if self.agent_config.get("custom_goals", None):
            system_prompt += f"""
            CUSTOM GOALS (OVERRIDE PRIMARY GOALS IN CASE OF CONFLICT):
            {self.agent_config.get("custom_goals", "No Custom Goals. Please follow the primary goals.")}
            """

        system_prompt += """
        DECISION FRAMEWORK:
          - Start by getting vendor contact information or invoice details as needed
          - Compose a clear, professional message appropriate to the notification type
          - Use the appropriate notification tool (vendor notification or invoice notification)
          - Ensure the subject line is concise and descriptive
          - Provide clear reasoning for the communication in your task completion

        COMMUNICATION TEMPLATES (use as guidelines, not rigid templates):
          - Status Update: "[Company Name] - Vendor Status Update"
          - Payment Confirmation: "[Company Name] - Payment Confirmation for Invoice #[number]"
          - Compliance Alert: "[Company Name] - Important: Compliance Update Required"
          - Action Required: "[Company Name] - Action Required: [brief description]"
          - Reminder: "[Company Name] - Friendly Reminder: [brief description]"

        MUST Remember: You represent CineFlow Productions. Every communication reflects on the company. Be professional, accurate, and helpful.
        """
        return system_prompt

    async def _get_user_prompt(self, task_data: dict[str, Any] | None = None) -> str:
        """Get the user prompt for the communication agent
        Args:
            task_data: The task data to process in the form of a dictionary
        """
        if task_data is None:
            return "Task Description: Help compose and send a communication."

        task_details = task_data.get(
            "description", "Please compose and send the appropriate communication"
        )
        communication_details = ""
        for key, value in task_data.items():
            if key == "description":
                continue
            communication_details += f"{key}: {value}\n"

        user_prompt = f"""Task Description: {task_details}
        Communication Details:
        {communication_details}
        """

        return user_prompt

    def _get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get the tool definitions for the communication agent

        Tools available to the agent:
        - get_vendor_contact_info: Get vendor contact details
        - get_vendor_details: Get full vendor details
        - get_invoice_details: Get invoice details for composing notifications
        - send_vendor_notification: Send a notification to a vendor
        - send_invoice_notification: Send a notification about an invoice

        Returns:
            List of tool definitions
        """
        return [
            {
                "type": "function",
                "name": "get_vendor_contact_info",
                "strict": True,
                "description": "Get vendor contact information including email, phone, and company name",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vendor_id": {
                            "type": "integer",
                            "description": "The ID of the vendor",
                        }
                    },
                    "required": ["vendor_id"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "get_vendor_details",
                "strict": True,
                "description": "Retrieve complete vendor details based on the vendor ID",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vendor_id": {
                            "type": "integer",
                            "description": "The ID of the vendor to retrieve",
                        }
                    },
                    "required": ["vendor_id"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "get_invoice_details",
                "strict": True,
                "description": "Retrieve complete invoice details based on the invoice ID",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "invoice_id": {
                            "type": "integer",
                            "description": "The ID of the invoice to retrieve",
                        }
                    },
                    "required": ["invoice_id"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "send_vendor_notification",
                "strict": True,
                "description": "Send a notification email to a vendor about their account, status, or general communication",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vendor_id": {
                            "type": "integer",
                            "description": "The ID of the vendor to notify",
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject line - should be concise and descriptive",
                        },
                        "message": {
                            "type": "string",
                            "description": "The notification message body - professional and clear",
                        },
                        "notification_type": {
                            "type": "string",
                            "description": "Type of notification being sent",
                            "enum": [
                                "status_update",
                                "payment_update",
                                "compliance_alert",
                                "general",
                            ],
                        },
                    },
                    "required": [
                        "vendor_id",
                        "subject",
                        "message",
                        "notification_type",
                    ],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "send_invoice_notification",
                "strict": True,
                "description": "Send a notification email related to a specific invoice (payment confirmation, status update, etc.)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "invoice_id": {
                            "type": "integer",
                            "description": "The ID of the related invoice",
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject line - should be concise and descriptive",
                        },
                        "message": {
                            "type": "string",
                            "description": "The notification message body - professional and clear",
                        },
                        "notification_type": {
                            "type": "string",
                            "description": "Type of notification being sent",
                            "enum": [
                                "status_update",
                                "payment_confirmation",
                                "action_required",
                                "reminder",
                            ],
                        },
                    },
                    "required": [
                        "invoice_id",
                        "subject",
                        "message",
                        "notification_type",
                    ],
                    "additionalProperties": False,
                },
            },
        ]

    @agent_tool
    async def get_vendor_contact_info(self, vendor_id: int) -> dict[str, Any]:
        """Get vendor contact information

        Args:
            vendor_id: The ID of the vendor

        Returns:
            Dictionary containing vendor contact details
        """
        logger.info("Getting vendor contact info for vendor_id: %s", vendor_id)
        try:
            return await get_vendor_contact_info(vendor_id, self.session_context)
        except ValueError as e:
            logger.error("Error getting vendor contact info: %s", e)
            return {
                "vendor_id": vendor_id,
                "error": str(e),
            }

    @agent_tool
    async def get_vendor_details(self, vendor_id: int) -> dict[str, Any]:
        """Get the details of the vendor

        Args:
            vendor_id: The ID of the vendor to retrieve

        Returns:
            Dictionary containing vendor details
        """
        logger.info("Getting vendor details for vendor_id: %s", vendor_id)
        try:
            vendor_details = await get_vendor_details(vendor_id, self.session_context)
            return {
                "vendor_id": vendor_details["id"],
                "company_name": vendor_details["company_name"],
                "vendor_category": vendor_details["vendor_category"],
                "industry": vendor_details["industry"],
                "contact_name": vendor_details["contact_name"],
                "email": vendor_details["email"],
                "phone": vendor_details["phone"],
                "status": vendor_details["status"],
                "trust_level": vendor_details["trust_level"],
            }
        except ValueError as e:
            logger.error("Error getting vendor details: %s", e)
            return {
                "vendor_id": vendor_id,
                "error": "Vendor not found",
            }

    @agent_tool
    async def get_invoice_details(self, invoice_id: int) -> dict[str, Any]:
        """Get the details of an invoice

        Args:
            invoice_id: The ID of the invoice to retrieve

        Returns:
            Dictionary containing invoice details
        """
        logger.info("Getting invoice details for invoice_id: %s", invoice_id)
        try:
            invoice_details = await get_invoice_details(
                invoice_id, self.session_context
            )
            return {
                "invoice_id": invoice_details["id"],
                "vendor_id": invoice_details["vendor_id"],
                "invoice_number": invoice_details["invoice_number"],
                "amount": invoice_details["amount"],
                "description": invoice_details["description"],
                "invoice_date": invoice_details["invoice_date"],
                "due_date": invoice_details["due_date"],
                "status": invoice_details["status"],
            }
        except ValueError as e:
            logger.error("Error getting invoice details: %s", e)
            return {
                "invoice_id": invoice_id,
                "error": "Invoice not found",
            }

    @agent_tool
    async def send_vendor_notification(
        self,
        vendor_id: int,
        subject: str,
        message: str,
        notification_type: str,
    ) -> dict[str, Any]:
        """Send a notification to a vendor

        Args:
            vendor_id: The ID of the vendor to notify
            subject: Email subject line
            message: Notification message body
            notification_type: Type of notification

        Returns:
            Dictionary confirming the notification was sent
        """
        logger.info(
            "Sending vendor notification: vendor_id=%s, type=%s, subject=%s",
            vendor_id,
            notification_type,
            subject,
        )
        try:
            result = await send_vendor_notification(
                vendor_id, subject, message, notification_type, self.session_context
            )

            await event_bus.emit_business_event(
                event_type="communication.vendor_notification_sent",
                event_subtype="lifecycle",
                event_data={
                    "vendor_id": vendor_id,
                    "recipient_name": result.get("recipient_name"),
                    "recipient_email": result.get("recipient_email"),
                    "subject": subject,
                    "notification_type": notification_type,
                },
                session_context=self.session_context,
                workflow_id=self.workflow_id,
                summary=f"Notification sent to {result.get('recipient_name', 'vendor')}: {subject}",
            )

            return result
        except ValueError as e:
            logger.error("Error sending vendor notification: %s", e)
            return {
                "vendor_id": vendor_id,
                "notification_sent": False,
                "error": str(e),
            }

    @agent_tool
    async def send_invoice_notification(
        self,
        invoice_id: int,
        subject: str,
        message: str,
        notification_type: str,
    ) -> dict[str, Any]:
        """Send a notification about an invoice

        Args:
            invoice_id: The ID of the related invoice
            subject: Email subject line
            message: Notification message body
            notification_type: Type of notification

        Returns:
            Dictionary confirming the notification was sent
        """
        logger.info(
            "Sending invoice notification: invoice_id=%s, type=%s, subject=%s",
            invoice_id,
            notification_type,
            subject,
        )
        try:
            result = await send_invoice_notification(
                invoice_id, subject, message, notification_type, self.session_context
            )

            await event_bus.emit_business_event(
                event_type="communication.invoice_notification_sent",
                event_subtype="lifecycle",
                event_data={
                    "invoice_id": invoice_id,
                    "invoice_number": result.get("invoice_number"),
                    "vendor_id": result.get("vendor_id"),
                    "recipient_name": result.get("recipient_name"),
                    "recipient_email": result.get("recipient_email"),
                    "subject": subject,
                    "notification_type": notification_type,
                },
                session_context=self.session_context,
                workflow_id=self.workflow_id,
                summary=f"Invoice notification sent to {result.get('recipient_name', 'vendor')}: {subject}",
            )

            return result
        except ValueError as e:
            logger.error("Error sending invoice notification: %s", e)
            return {
                "invoice_id": invoice_id,
                "notification_sent": False,
                "error": str(e),
            }

    def _get_callables(self) -> dict[str, Callable[..., Any]]:
        """Get the callables for the communication agent"""
        return {
            "get_vendor_contact_info": self.get_vendor_contact_info,
            "get_vendor_details": self.get_vendor_details,
            "get_invoice_details": self.get_invoice_details,
            "send_vendor_notification": self.send_vendor_notification,
            "send_invoice_notification": self.send_invoice_notification,
        }

    # Hooks
    async def _on_task_completion(self, task_result: dict[str, Any]) -> None:
        """Log communication task completion
        Args:
            task_result: The result of the task
        """
        logger.info(
            "Communication task completed: status=%s, summary=%s",
            task_result.get("task_status"),
            task_result.get("task_summary"),
        )
