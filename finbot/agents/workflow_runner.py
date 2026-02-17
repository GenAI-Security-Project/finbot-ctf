import os
from finbot.agents.workflow import WorkflowOrchestrator
from finbot.agents.specialized.fraud_detection import (
    ValidatorAgent, RiskAnalyzerAgent, ApprovalAgent, PaymentProcessorAgent
)


import asyncio
import json
from finbot.core.auth.session import SessionContext
from finbot.core.data.database import get_db
from finbot.core.data.repositories import InvoiceRepository, VendorRepository
from datetime import datetime, timedelta, UTC

async def run_invoice_lifecycle_workflow(enable_fraud_agent=True, invoice_id=None, session_context=None):
    """Run invoice lifecycle workflow with real or test data
    
    Args:
        enable_fraud_agent: Whether to include fraud detection
        invoice_id: Optional invoice ID to process. If None, uses test data
        session_context: Optional session context. If None, uses test context
    """
    workflow_path = os.path.join(os.path.dirname(__file__), "workflows", "invoice_lifecycle.yaml")
    workflow_def = WorkflowOrchestrator.load_workflow_definition(workflow_path)
    # Dynamically filter steps
    if not enable_fraud_agent:
        workflow_def["steps"] = [step for step in workflow_def["steps"] if step["agent"] != "RiskAnalyzerAgent"]
    
    # Use provided session or create test session
    if session_context is None:
        session_context = SessionContext(
            session_id="test-session",
            user_id="test-user",
            is_temporary=True,
            namespace="test-ns",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    
    # Build initial context from database or use test data
    if invoice_id:
        initial_context = await _build_context_from_db(invoice_id, session_context)
    else:
        # Fallback to static test data
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
    
    agent_registry = {
        "ValidatorAgent": ValidatorAgent(),
        "RiskAnalyzerAgent": RiskAnalyzerAgent(session_context=session_context),
        "ApprovalAgent": ApprovalAgent(),
        "PaymentProcessorAgent": PaymentProcessorAgent(),
    }
    orchestrator = WorkflowOrchestrator(workflow_def, agent_registry)
    result = await orchestrator.run(initial_context)
    
    # Save fraud detection results back to database if enabled and invoice_id provided
    if enable_fraud_agent and invoice_id and result.get("risk"):
        await _save_fraud_results(invoice_id, result, session_context)
    
    print("Workflow result:", result)
    return result

async def _build_context_from_db(invoice_id: int, session_context: SessionContext) -> dict:
    """Build workflow context from database invoice"""
    db = next(get_db())
    try:
        invoice_repo = InvoiceRepository(db, session_context)
        vendor_repo = VendorRepository(db, session_context)
        
        # Get the invoice
        invoice = invoice_repo.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        # Get vendor details
        vendor = vendor_repo.get_vendor(invoice.vendor_id)
        if not vendor:
            raise ValueError(f"Vendor {invoice.vendor_id} not found")
        
        # Get vendor history (recent invoices for this vendor)
        vendor_invoices = invoice_repo.list_invoices_for_specific_vendor(invoice.vendor_id)
        vendor_history = [
            {"amount": float(inv.amount), "created_at": inv.created_at.isoformat()}
            for inv in vendor_invoices
            if inv.id != invoice_id  # Exclude current invoice
        ]
        
        # Get recent invoice IDs (last 10 invoices)
        all_invoices = invoice_repo.list_all_invoices_for_user()
        recent_invoice_ids = {inv.invoice_number for inv in all_invoices[:10] if inv.invoice_number}
        
        # Build invoice object for analysis
        invoice_data = {
            "vendor": vendor.company_name,
            "amount": float(invoice.amount),
            "currency": "USD",  # Default currency
            "account": vendor.bank_account_number,
            "payment_method": "wire",  # Default payment method
            "created_at": invoice.invoice_date.isoformat() if invoice.invoice_date else datetime.now(UTC).isoformat(),
            "description": invoice.description,
            "invoice_number": invoice.invoice_number,
        }
        
        # Known fraud patterns (static for now, could be loaded from config)
        known_fraud_patterns = [
            {"amount": 100000, "vendor": "*NEW*"},
            {"vendor": "EvilInc"},
            {"account": "000-000"},
            {"payment_method": "gift_card", "amount": 5000},
            {"account": vendor.bank_account_number, "created_at": "*DUPLICATE_TIME*"},
            {"vendor": vendor.company_name, "currency": "BTC"},
            {"amount": 50000, "payment_method": "wire", "vendor": "*NEW*"}
        ]
        
        return {
            "invoice_id": invoice.invoice_number or str(invoice_id),
            "invoice": invoice_data,
            "historical": {
                "vendor_history": {vendor.company_name: vendor_history},
                "recent_invoice_ids": recent_invoice_ids,
                "known_fraud_patterns": known_fraud_patterns,
            }
        }
    finally:
        db.close()

async def _save_fraud_results(invoice_id: int, result: dict, session_context: SessionContext) -> None:
    """Save fraud detection results back to the invoice"""
    db = next(get_db())
    try:
        invoice_repo = InvoiceRepository(db, session_context)
        
        # Serialize risk reasons to JSON
        risk_reasons_json = json.dumps(result.get("risk_reasons", []))
        
        # Update invoice with fraud results
        invoice_repo.update_invoice(
            invoice_id,
            fraud_risk_level=result.get("risk"),
            fraud_risk_reasons=risk_reasons_json,
            fraud_analyzed_at=datetime.now(UTC)
        )
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_invoice_lifecycle_workflow())
