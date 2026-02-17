import os
from finbot.agents.workflow import WorkflowOrchestrator
from finbot.agents.specialized.fraud_detection import (
    ValidatorAgent, RiskAnalyzerAgent, ApprovalAgent, PaymentProcessorAgent
)


import asyncio
from finbot.core.auth.session import SessionContext
from datetime import datetime, timedelta, UTC

async def run_invoice_lifecycle_workflow(enable_fraud_agent=True):
    workflow_path = os.path.join(os.path.dirname(__file__), "workflows", "invoice_lifecycle.yaml")
    workflow_def = WorkflowOrchestrator.load_workflow_definition(workflow_path)
    # Dynamically filter steps
    if not enable_fraud_agent:
        workflow_def["steps"] = [step for step in workflow_def["steps"] if step["agent"] != "RiskAnalyzerAgent"]
    # Dummy session context for demo/testing
    session_context = SessionContext(
        session_id="test-session",
        user_id="test-user",
        is_temporary=True,
        namespace="test-ns",
        created_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    agent_registry = {
        "ValidatorAgent": ValidatorAgent(),
        "RiskAnalyzerAgent": RiskAnalyzerAgent(session_context=session_context),
        "ApprovalAgent": ApprovalAgent(),
        "PaymentProcessorAgent": PaymentProcessorAgent(),
    }
    orchestrator = WorkflowOrchestrator(workflow_def, agent_registry)
    initial_context = {
        "invoice_id": "INV-001",
        "invoice": {"vendor": "AcmeCorp", "amount": 12000, "currency": "USD", "account": "123-456", "payment_method": "wire", "created_at": "2026-02-03T10:00:00Z"},
        "historical": {
            "vendor_history": {
                "AcmeCorp": [
                    {"amount": 4000},
                    {"amount": 5000},
                    {"amount": 6000}
                ]
            },
            "recent_invoice_ids": {"INV-000", "INV-001"},
            "known_fraud_patterns": [
                {"amount": 100000, "vendor": "*NEW*"},
                {"vendor": "EvilInc"},
                {"account": "000-000"},
                {"payment_method": "gift_card", "amount": 5000},
                {"account": "123-456", "created_at": "*DUPLICATE_TIME*"},
                {"vendor": "AcmeCorp", "currency": "BTC"},
                {"amount": 50000, "payment_method": "wire", "vendor": "*NEW*"}
            ]
        }
    }
    result = await orchestrator.run(initial_context)
    print("Workflow result:", result)
    return result

if __name__ == "__main__":
    asyncio.run(run_invoice_lifecycle_workflow())
