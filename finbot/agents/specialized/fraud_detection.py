from finbot.agents.workflow import AgentBase

class ValidatorAgent(AgentBase):
    def __init__(self):
        super().__init__("ValidatorAgent")
    def run(self, context):
        # Example: validate invoice fields
        context["validated"] = True
        context["validation_result"] = "ok"
        return context
    def rollback(self, context):
        context["validated"] = False

import json
from finbot.core.llm.contextual_client import ContextualLLMClient
from finbot.core.auth.session import SessionContext
from finbot.core.data.models import LLMRequest
import asyncio

class RiskAnalyzerAgent(AgentBase):
    def __init__(self, session_context: SessionContext, workflow_id: str = None):
        super().__init__("RiskAnalyzerAgent")
        self.llm_client = ContextualLLMClient(
            session_context=session_context,
            agent_name="RiskAnalyzerAgent",
            workflow_id=workflow_id,
        )

    async def run(self, context):
        # Compose a prompt with invoice and historical context
        invoice = context.get("invoice", {})
        historical = context.get("historical", {})
        
        # Helper to convert sets to lists for JSON serialization
        def json_serializable(obj):
            if isinstance(obj, set):
                return list(obj)
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
        
        prompt = (
            "You are a fraud detection expert. Analyze the following invoice and context for red flags of invoice fraud. "
            "Red flags include: incorrect vendor info, discrepancies in vendor name/address/contact, unfamiliar vendors, duplicate invoices, urgent/high-pressure language, unusual invoice amounts, poor formatting, unusual billing patterns, currency inconsistencies, lack of detailed descriptions. "
            "Return a JSON object with 'risk' ('high' or 'low') and a list of 'risk_reasons'.\n"
            f"Invoice: {json.dumps(invoice, default=json_serializable)}\n"
            f"Historical: {json.dumps(historical, default=json_serializable)}\n"
        )
        request = LLMRequest(
            messages=[{"role": "system", "content": "You are a helpful fraud detection AI."},
                      {"role": "user", "content": prompt}],
            output_json_schema={
                "name": "FraudAnalysisResult",
                "schema": {
                    "type": "object",
                    "properties": {
                        "risk": {"type": "string", "enum": ["high", "low"]},
                        "risk_reasons": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["risk", "risk_reasons"]
                }
            }
        )
        response = await self.llm_client.chat(request)
        
        # Log the raw response for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"RiskAnalyzerAgent: Raw LLM response content: {response.content!r}")
        
        try:
            result = json.loads(response.content)
            context["risk"] = result.get("risk", "low")
            context["risk_reasons"] = result.get("risk_reasons", [])
        except json.JSONDecodeError as e:
            logger.error(f"RiskAnalyzerAgent: Failed to parse JSON: {e}. Content was: {response.content!r}")
            context["risk"] = "low"
            context["risk_reasons"] = [f"LLM response could not be parsed: {str(e)[:100]}"]
        except Exception as e:
            logger.error(f"RiskAnalyzerAgent: Unexpected error: {e}")
            context["risk"] = "low"
            context["risk_reasons"] = ["LLM response could not be parsed"]
        return context

    def rollback(self, context):
        context["risk"] = None
        context["risk_reasons"] = []

class ApprovalAgent(AgentBase):
    def __init__(self):
        super().__init__("ApprovalAgent")
    def run(self, context):
        # Example: approve if risk is low
        context["approved"] = context.get("risk") == "low"
        return context
    def rollback(self, context):
        context["approved"] = False

class PaymentProcessorAgent(AgentBase):
    def __init__(self):
        super().__init__("PaymentProcessorAgent")
    def run(self, context):
        # Example: process payment if approved
        if context.get("approved"):
            context["payment_status"] = "processed"
        else:
            context["payment_status"] = "not_processed"
        return context
    def rollback(self, context):
        context["payment_status"] = "rolled_back"
