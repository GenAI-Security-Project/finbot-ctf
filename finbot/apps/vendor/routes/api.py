"""Vendor Portal API Routes"""

import secrets
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from finbot.agents.runner import run_orchestrator_agent
from finbot.core.auth.middleware import get_session_context
from finbot.core.auth.session import SessionContext
from finbot.core.data.database import get_db
from finbot.core.data.repositories import (
    ChatMessageRepository,
    InvoiceRepository,
    VendorMessageRepository,
    VendorRepository,
)
from finbot.core.messaging import event_bus

# Create API router
router = APIRouter(prefix="/api/v1", tags=["vendor-api"])


class VendorRegistrationRequest(BaseModel):
    """Vendor registration request model"""

    # Company Information
    company_name: str
    vendor_category: str
    industry: str
    services: str

    # Contact Information
    name: str
    email: str
    phone: str | None = None

    # Financial Information
    tin: str
    bank_account_number: str
    bank_name: str
    bank_routing_number: str
    bank_account_holder_name: str


class VendorUpdateRequest(BaseModel):
    """Vendor profile update request model"""

    # Company Information
    company_name: str | None = None
    services: str | None = None

    # Contact Information
    contact_name: str | None = None
    email: str | None = None
    phone: str | None = None


class VendorContextResponse(BaseModel):
    """Vendor context response"""

    current_vendor: dict | None
    available_vendors: list[dict]
    is_multi_vendor: bool


class InvoiceCreateRequest(BaseModel):
    """Invoice creation request"""

    invoice_number: str
    amount: float
    description: str
    invoice_date: str  # ISO date string YYYY-MM-DD
    due_date: str  # ISO date string YYYY-MM-DD


@router.post("/vendors/register")
async def register_vendor(
    vendor_data: VendorRegistrationRequest,
    background_tasks: BackgroundTasks,
    session_context: SessionContext = Depends(get_session_context),
):
    """Register a new vendor"""
    try:
        db = next(get_db())
        vendor_repo = VendorRepository(db, session_context)

        # Create vendor with all required fields
        vendor = vendor_repo.create_vendor(
            company_name=vendor_data.company_name,
            vendor_category=vendor_data.vendor_category,
            industry=vendor_data.industry,
            services=vendor_data.services,
            contact_name=vendor_data.name,
            email=vendor_data.email,
            tin=vendor_data.tin,
            bank_account_number=vendor_data.bank_account_number,
            bank_name=vendor_data.bank_name,
            bank_routing_number=vendor_data.bank_routing_number,
            bank_account_holder_name=vendor_data.bank_account_holder_name,
            phone=vendor_data.phone,
        )

        workflow_id = f"wf_{secrets.token_urlsafe(12)}"

        background_tasks.add_task(
            run_orchestrator_agent,
            task_data={
                "vendor_id": vendor.id,
                "description": "A new vendor has registered. Evaluate and onboard the vendor, then notify them of the decision.",
            },
            session_context=session_context,
            workflow_id=workflow_id,
        )

        await event_bus.emit_business_event(
            event_type="vendor.created",
            event_subtype="lifecycle",
            event_data={
                "vendor_id": vendor.id,
                "company_name": vendor.company_name,
                "workflow_id": workflow_id,
            },
            session_context=session_context,
            workflow_id=workflow_id,
            summary=f"New vendor registered: {vendor.company_name}",
        )

        return {
            "success": True,
            "message": "Vendor registered successfully. Onboarding in progress.",
            "vendor_id": vendor.id,
            "workflow_id": workflow_id,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to register vendor: {str(e)}"
        ) from e


@router.get("/vendors/me")
async def get_my_vendors(
    session_context: SessionContext = Depends(get_session_context),
):
    """Get user's vendors with current context"""
    return {
        "vendors": session_context.available_vendors,
        "current_vendor_id": session_context.current_vendor_id,
        "total_count": len(session_context.available_vendors),
    }


@router.get("/vendors/context", response_model=VendorContextResponse)
async def get_vendor_context(
    session_context: SessionContext = Depends(get_session_context),
):
    """Get current vendor context"""
    return VendorContextResponse(
        current_vendor=session_context.current_vendor,
        available_vendors=session_context.available_vendors,
        is_multi_vendor=session_context.is_multi_vendor_user(),
    )


@router.get("/vendors/{vendor_id}")
async def get_vendor(
    vendor_id: int,
    session_context: SessionContext = Depends(get_session_context),
):
    """Get vendor details for a specific vendor"""
    db = next(get_db())
    vendor_repo = VendorRepository(db, session_context)
    vendor = vendor_repo.get_vendor(vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    # Verify vendor is the current vendor (vendor portal only sees current vendor)
    if vendor.id != session_context.current_vendor_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to view this vendor"
        )

    return vendor.to_dict()


@router.put("/vendors/{vendor_id}")
async def update_vendor(
    vendor_id: int,
    vendor_data: VendorUpdateRequest,
    session_context: SessionContext = Depends(get_session_context),
):
    """Update vendor profile"""
    db = next(get_db())
    vendor_repo = VendorRepository(db, session_context)

    # Get vendor and verify access
    vendor = vendor_repo.get_vendor(vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    # Verify vendor belongs to current user and is the current vendor
    if vendor.id != session_context.current_vendor_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to update this vendor"
        )

    try:
        # Update only provided fields
        update_data = vendor_data.dict(exclude_unset=True)

        # Map contact_name to the correct field if provided
        if "contact_name" in update_data:
            vendor.contact_name = update_data["contact_name"]
        if "company_name" in update_data:
            vendor.company_name = update_data["company_name"]
        if "services" in update_data:
            vendor.services = update_data["services"]
        if "email" in update_data:
            vendor.email = update_data["email"]
        if "phone" in update_data:
            vendor.phone = update_data["phone"]

        db.commit()
        db.refresh(vendor)

        await event_bus.emit_business_event(
            event_type="vendor.updated",
            event_subtype="lifecycle",
            event_data={
                "vendor_id": vendor.id,
                "company_name": vendor.company_name,
                "updates": list(update_data.keys()),
            },
            session_context=session_context,
            summary=f"Vendor profile updated: {vendor.company_name}",
        )

        return {
            "success": True,
            "message": "Vendor profile updated successfully",
            "vendor": {
                "id": vendor.id,
                "company_name": vendor.company_name,
                "contact_name": vendor.contact_name,
                "email": vendor.email,
                "phone": vendor.phone,
                "services": vendor.services,
            },
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update vendor: {str(e)}"
        ) from e


@router.delete("/vendors/{vendor_id}")
async def delete_vendor(
    vendor_id: int, session_context: SessionContext = Depends(get_session_context)
):
    """Delete a vendor"""
    db = next(get_db())
    vendor_repo = VendorRepository(db, session_context)

    # Get vendor and verify access
    vendor = vendor_repo.get_vendor(vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    # Verify vendor belongs to current user and is the current vendor
    if vendor.id != session_context.current_vendor_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to delete this vendor"
        )

    company_name = vendor.company_name
    success = vendor_repo.delete_vendor(vendor_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete vendor")

    await event_bus.emit_business_event(
        event_type="vendor.deleted",
        event_subtype="lifecycle",
        event_data={"vendor_id": vendor_id, "company_name": company_name},
        session_context=session_context,
        summary=f"Vendor deleted: {company_name}",
    )

    return {"success": True, "message": "Vendor deleted successfully"}


@router.post("/vendors/{vendor_id}/request-review")
async def request_vendor_review(
    vendor_id: int,
    background_tasks: BackgroundTasks,
    session_context: SessionContext = Depends(get_session_context),
):
    """Request a re-review of vendor status by running the onboarding workflow again"""
    db = next(get_db())
    vendor_repo = VendorRepository(db, session_context)

    # Get vendor and verify access
    vendor = vendor_repo.get_vendor(vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    # Verify vendor belongs to current user and is the current vendor
    if vendor.id != session_context.current_vendor_id:
        raise HTTPException(
            status_code=403, detail="Not authorized to request review for this vendor"
        )

    try:
        # Generate workflow ID for tracking
        workflow_id = f"wf_review_{secrets.token_urlsafe(12)}"

        background_tasks.add_task(
            run_orchestrator_agent,
            task_data={
                "vendor_id": vendor.id,
                "description": "Vendor requested a re-review of their profile. Re-evaluate the vendor and notify them of the outcome.",
            },
            session_context=session_context,
            workflow_id=workflow_id,
        )

        await event_bus.emit_business_event(
            event_type="vendor.review_requested",
            event_subtype="lifecycle",
            event_data={
                "vendor_id": vendor.id,
                "company_name": vendor.company_name,
                "previous_status": vendor.status,
                "workflow_id": workflow_id,
            },
            session_context=session_context,
            workflow_id=workflow_id,
            summary=f"Vendor review requested: {vendor.company_name}",
        )

        return {
            "success": True,
            "message": "Review request submitted. Your profile is being re-evaluated.",
            "vendor_id": vendor.id,
            "workflow_id": workflow_id,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to submit review request: {str(e)}"
        ) from e


@router.post("/vendors/switch/{vendor_id}")
async def switch_vendor(
    vendor_id: int,
    session_context: SessionContext = Depends(get_session_context),
):
    """Switch to different vendor (updates all user sessions)"""
    db = next(get_db())
    vendor_repo = VendorRepository(db, session_context)

    # Validate vendor exists and belongs to user
    vendor = vendor_repo.get_vendor(vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    # Switch vendor context globally
    success = vendor_repo.set_current_vendor(vendor_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to switch vendor")

    await event_bus.emit_business_event(
        event_type="vendor.switched",
        event_subtype="lifecycle",
        event_data={
            "vendor_id": vendor.id,
            "company_name": vendor.company_name,
        },
        session_context=session_context,
        summary=f"Switched to vendor: {vendor.company_name}",
    )

    return {
        "success": True,
        "message": "Vendor switched successfully",
        "current_vendor": {
            "id": vendor.id,
            "company_name": vendor.company_name,
            "vendor_category": vendor.vendor_category,
            "industry": vendor.industry,
            "status": vendor.status,
        },
    }


# Dashboard metrics
@router.get("/dashboard/metrics")
async def get_dashboard_metrics(
    session_context: SessionContext = Depends(get_session_context),
):
    """Get dashboard metrics for current vendor"""
    db = next(get_db())

    invoice_repo = InvoiceRepository(db, session_context)
    msg_repo = VendorMessageRepository(db, session_context)

    invoice_stats = invoice_repo.get_current_vendor_invoice_stats()
    message_stats = msg_repo.get_message_stats_for_current_vendor()

    recent_messages = msg_repo.list_messages_for_current_vendor(limit=5)
    recent_invoices = invoice_repo.list_invoices_for_current_vendor()[:5]

    payment_summary = {}
    try:
        from finbot.mcp.servers.finstripe.repositories import (
            PaymentTransactionRepository,
        )

        txn_repo = PaymentTransactionRepository(db, session_context)
        transactions = txn_repo.list_for_vendor(
            session_context.current_vendor_id, limit=1000
        )
        payment_summary = {
            "total_paid": sum(
                t.amount for t in transactions if t.status == "completed"
            ),
            "total_pending": sum(
                t.amount for t in transactions if t.status == "pending"
            ),
            "completed_count": sum(
                1 for t in transactions if t.status == "completed"
            ),
            "pending_count": sum(
                1 for t in transactions if t.status == "pending"
            ),
            "failed_count": sum(
                1 for t in transactions if t.status == "failed"
            ),
            "transaction_count": len(transactions),
        }
    except Exception:
        payment_summary = {
            "total_paid": 0,
            "total_pending": 0,
            "completed_count": 0,
            "pending_count": 0,
            "failed_count": 0,
            "transaction_count": 0,
        }

    file_count = 0
    try:
        from finbot.mcp.servers.findrive.repositories import FinDriveFileRepository

        file_repo = FinDriveFileRepository(db, session_context)
        files = file_repo.list_files(
            vendor_id=session_context.current_vendor_id, limit=1000
        )
        file_count = len(files)
    except Exception:
        pass

    return {
        "vendor_context": session_context.current_vendor,
        "metrics": {
            "invoices": invoice_stats,
            "payments": payment_summary,
            "messages": message_stats,
            "files": {"total_count": file_count},
            "completion_rate": (
                invoice_stats["paid_count"]
                / max(invoice_stats["total_count"], 1)
                * 100
            ),
        },
        "recent_invoices": [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "amount": float(inv.amount),
                "status": inv.status,
                "description": inv.description,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "created_at": inv.created_at.isoformat()
                if inv.created_at
                else None,
            }
            for inv in recent_invoices
        ],
        "recent_messages": [m.to_dict() for m in recent_messages],
    }


# Invoice endpoints (vendor-scoped)
@router.get("/invoices")
async def get_invoices(
    status: str | None = None,
    session_context: SessionContext = Depends(get_session_context),
):
    """Get invoices for current vendor"""
    db = next(get_db())
    invoice_repo = InvoiceRepository(db, session_context)

    invoices = invoice_repo.list_invoices_for_current_vendor(status)

    return {
        "invoices": [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "amount": float(inv.amount),
                "status": inv.status,
                "description": inv.description,
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "created_at": inv.created_at.isoformat(),
            }
            for inv in invoices
        ],
        "vendor_context": session_context.current_vendor,
        "total_count": len(invoices),
    }


@router.post("/invoices")
async def create_invoice(
    invoice_data: InvoiceCreateRequest,
    background_tasks: BackgroundTasks,
    session_context: SessionContext = Depends(get_session_context),
):
    """Create invoice for current vendor"""
    db = next(get_db())
    invoice_repo = InvoiceRepository(db, session_context)

    try:
        # Parse date strings to datetime objects
        invoice_dict = invoice_data.model_dump()
        invoice_dict["invoice_date"] = datetime.fromisoformat(invoice_data.invoice_date)
        invoice_dict["due_date"] = datetime.fromisoformat(invoice_data.due_date)

        invoice = invoice_repo.create_invoice_for_current_vendor(**invoice_dict)

        workflow_id = f"wf_{secrets.token_urlsafe(12)}"

        background_tasks.add_task(
            run_orchestrator_agent,
            task_data={
                "invoice_id": invoice.id,
                "vendor_id": session_context.current_vendor_id,
                "description": "A new invoice has been submitted. Process the invoice and notify the vendor of the decision.",
            },
            session_context=session_context,
            workflow_id=workflow_id,
        )

        await event_bus.emit_business_event(
            event_type="invoice.created",
            event_subtype="lifecycle",
            event_data={
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "amount": float(invoice.amount),
                "description": invoice.description,
                "invoice_date": invoice.invoice_date.isoformat()
                if invoice.invoice_date
                else None,
                "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            },
            session_context=session_context,
            workflow_id=workflow_id,
            summary=f"Invoice submitted: ${float(invoice.amount):,.2f} (#{invoice.invoice_number})",
        )

        return {
            "success": True,
            "message": "Invoice created successfully",
            "invoice": {
                "id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "amount": float(invoice.amount),
                "status": invoice.status,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: int,
    session_context: SessionContext = Depends(get_session_context),
):
    """Get specific invoice"""
    db = next(get_db())
    invoice_repo = InvoiceRepository(db, session_context)

    invoice = invoice_repo.get_invoice(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Verify invoice belongs to current vendor
    if invoice.vendor_id != session_context.current_vendor_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "invoice": {
            "id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "amount": float(invoice.amount),
            "status": invoice.status,
            "description": invoice.description,
            "invoice_date": invoice.invoice_date.isoformat()
            if invoice.invoice_date
            else None,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            "agent_notes": invoice.agent_notes,
            "created_at": invoice.created_at.isoformat()
            if invoice.created_at
            else None,
            "updated_at": invoice.updated_at.isoformat()
            if invoice.updated_at
            else None,
        }
    }


class InvoiceUpdateRequest(BaseModel):
    """Invoice update request - status not editable by vendors"""

    invoice_number: str | None = None
    amount: float | None = None
    description: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None


@router.put("/invoices/{invoice_id}")
async def update_invoice(
    invoice_id: int,
    invoice_data: InvoiceUpdateRequest,
    session_context: SessionContext = Depends(get_session_context),
):
    """Update specific invoice"""
    db = next(get_db())
    invoice_repo = InvoiceRepository(db, session_context)

    # First get the invoice to verify ownership
    invoice = invoice_repo.get_invoice(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Verify invoice belongs to current vendor
    if invoice.vendor_id != session_context.current_vendor_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Build update dict from non-None values (status not editable by vendors)
    updates = {}
    if invoice_data.invoice_number is not None:
        updates["invoice_number"] = invoice_data.invoice_number
    if invoice_data.amount is not None:
        updates["amount"] = invoice_data.amount
    if invoice_data.description is not None:
        updates["description"] = invoice_data.description
    if invoice_data.invoice_date is not None:
        updates["invoice_date"] = datetime.fromisoformat(invoice_data.invoice_date)
    if invoice_data.due_date is not None:
        updates["due_date"] = datetime.fromisoformat(invoice_data.due_date)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Update the invoice
    updated_invoice = invoice_repo.update_invoice(invoice_id, **updates)

    return {
        "success": True,
        "message": "Invoice updated successfully",
        "invoice": {
            "id": updated_invoice.id,
            "invoice_number": updated_invoice.invoice_number,
            "amount": float(updated_invoice.amount),
            "status": updated_invoice.status,
            "description": updated_invoice.description,
            "invoice_date": updated_invoice.invoice_date.isoformat()
            if updated_invoice.invoice_date
            else None,
            "due_date": updated_invoice.due_date.isoformat()
            if updated_invoice.due_date
            else None,
        },
    }


@router.post("/invoices/{invoice_id}/reprocess")
async def reprocess_invoice(
    invoice_id: int,
    background_tasks: BackgroundTasks,
    session_context: SessionContext = Depends(get_session_context),
):
    """Request re-processing of an invoice by the AI agent"""
    db = next(get_db())
    invoice_repo = InvoiceRepository(db, session_context)

    # Get the invoice
    invoice = invoice_repo.get_invoice(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Verify invoice belongs to current vendor
    if invoice.vendor_id != session_context.current_vendor_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Create workflow ID for tracking
    workflow_id = f"wf_{secrets.token_urlsafe(12)}"

    background_tasks.add_task(
        run_orchestrator_agent,
        task_data={
            "invoice_id": invoice.id,
            "vendor_id": session_context.current_vendor_id,
            "description": "Vendor requested invoice re-processing. Re-evaluate the invoice and notify the vendor of the updated decision.",
        },
        session_context=session_context,
        workflow_id=workflow_id,
    )

    # Emit event for re-processing
    await event_bus.emit_business_event(
        event_type="invoice.reprocessed",
        event_subtype="lifecycle",
        event_data={
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "amount": float(invoice.amount),
            "status": invoice.status,
            "description": invoice.description,
            "invoice_date": invoice.invoice_date.isoformat()
            if invoice.invoice_date
            else None,
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            "agent_notes": invoice.agent_notes,
            "created_at": invoice.created_at.isoformat()
            if invoice.created_at
            else None,
            "updated_at": invoice.updated_at.isoformat()
            if invoice.updated_at
            else None,
        },
        session_context=session_context,
        workflow_id=workflow_id,
        summary=f"Invoice reprocessed: ${float(invoice.amount):,.2f} (#{invoice.invoice_number})",
    )

    return {
        "success": True,
        "message": "Invoice re-processing has been queued. The AI agent will review it shortly.",
        "workflow_id": workflow_id,
    }


# =============================================================================
# Payment endpoints (vendor-scoped)
# =============================================================================


@router.get("/payments/summary")
async def get_payment_summary(
    session_context: SessionContext = Depends(get_session_context),
):
    """Get payment summary for current vendor -- stats and mock account balance."""
    if not session_context.current_vendor_id:
        raise HTTPException(status_code=400, detail="Vendor context required")

    from finbot.mcp.servers.finstripe.repositories import PaymentTransactionRepository

    db = next(get_db())
    txn_repo = PaymentTransactionRepository(db, session_context)
    transactions = txn_repo.list_for_vendor(session_context.current_vendor_id, limit=1000)

    total_paid = sum(t.amount for t in transactions if t.status == "completed")
    total_pending = sum(t.amount for t in transactions if t.status == "pending")
    total_failed = sum(t.amount for t in transactions if t.status == "failed")

    completed_count = sum(1 for t in transactions if t.status == "completed")
    pending_count = sum(1 for t in transactions if t.status == "pending")
    failed_count = sum(1 for t in transactions if t.status == "failed")

    return {
        "summary": {
            "total_paid": total_paid,
            "total_pending": total_pending,
            "total_failed": total_failed,
            "completed_count": completed_count,
            "pending_count": pending_count,
            "failed_count": failed_count,
            "transaction_count": len(transactions),
        },
        "vendor_context": session_context.current_vendor,
    }


@router.get("/payments/transactions")
async def get_payment_transactions(
    limit: int = 50,
    offset: int = 0,
    session_context: SessionContext = Depends(get_session_context),
):
    """List payment transactions for current vendor."""
    if not session_context.current_vendor_id:
        raise HTTPException(status_code=400, detail="Vendor context required")

    from finbot.mcp.servers.finstripe.repositories import PaymentTransactionRepository

    db = next(get_db())
    txn_repo = PaymentTransactionRepository(db, session_context)
    transactions = txn_repo.list_for_vendor(
        session_context.current_vendor_id, limit=limit, offset=offset
    )

    return {
        "transactions": [t.to_dict() for t in transactions],
        "total_count": len(transactions),
        "vendor_context": session_context.current_vendor,
    }


# =============================================================================
# FinDrive file endpoints (vendor-scoped)
# =============================================================================


class FileCreateRequest(BaseModel):
    filename: str
    content: str
    folder: str = "/invoices"


class FileUpdateRequest(BaseModel):
    filename: str | None = None
    content: str | None = None


@router.get("/findrive")
async def list_vendor_files(
    limit: int = 100,
    session_context: SessionContext = Depends(get_session_context),
):
    """List files for current vendor from FinDrive."""
    if not session_context.current_vendor_id:
        raise HTTPException(status_code=400, detail="Vendor context required")

    from finbot.mcp.servers.findrive.repositories import FinDriveFileRepository

    db = next(get_db())
    repo = FinDriveFileRepository(db, session_context)
    files = repo.list_files(vendor_id=session_context.current_vendor_id, limit=limit)

    return {
        "files": [f.to_dict() for f in files],
        "total_count": len(files),
        "vendor_context": session_context.current_vendor,
    }


@router.post("/findrive")
async def create_vendor_file(
    file_data: FileCreateRequest,
    session_context: SessionContext = Depends(get_session_context),
):
    """Upload a file to FinDrive for current vendor."""
    if not session_context.current_vendor_id:
        raise HTTPException(status_code=400, detail="Vendor context required")

    from finbot.mcp.servers.findrive.repositories import FinDriveFileRepository

    db = next(get_db())
    repo = FinDriveFileRepository(db, session_context)
    f = repo.create_file(
        filename=file_data.filename,
        content_text=file_data.content,
        vendor_id=session_context.current_vendor_id,
        folder_path=file_data.folder,
    )

    return {
        "success": True,
        "file": f.to_dict(),
    }


@router.get("/findrive/{file_id}")
async def get_vendor_file(
    file_id: int,
    session_context: SessionContext = Depends(get_session_context),
):
    """Get a file's content from FinDrive."""
    if not session_context.current_vendor_id:
        raise HTTPException(status_code=400, detail="Vendor context required")

    from finbot.mcp.servers.findrive.repositories import FinDriveFileRepository

    db = next(get_db())
    repo = FinDriveFileRepository(db, session_context)
    f = repo.get_file(file_id)

    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    if f.vendor_id != session_context.current_vendor_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return {"file": f.to_dict_with_content()}


@router.put("/findrive/{file_id}")
async def update_vendor_file(
    file_id: int,
    file_data: FileUpdateRequest,
    session_context: SessionContext = Depends(get_session_context),
):
    """Update a file in FinDrive."""
    if not session_context.current_vendor_id:
        raise HTTPException(status_code=400, detail="Vendor context required")

    from finbot.mcp.servers.findrive.repositories import FinDriveFileRepository

    db = next(get_db())
    repo = FinDriveFileRepository(db, session_context)
    f = repo.get_file(file_id)

    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    if f.vendor_id != session_context.current_vendor_id:
        raise HTTPException(status_code=403, detail="Access denied")

    updated = repo.update_file(
        file_id,
        filename=file_data.filename,
        content_text=file_data.content,
    )

    return {"success": True, "file": updated.to_dict() if updated else None}


@router.delete("/findrive/{file_id}")
async def delete_vendor_file(
    file_id: int,
    session_context: SessionContext = Depends(get_session_context),
):
    """Delete a file from FinDrive."""
    if not session_context.current_vendor_id:
        raise HTTPException(status_code=400, detail="Vendor context required")

    from finbot.mcp.servers.findrive.repositories import FinDriveFileRepository

    db = next(get_db())
    repo = FinDriveFileRepository(db, session_context)
    f = repo.get_file(file_id)

    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    if f.vendor_id != session_context.current_vendor_id:
        raise HTTPException(status_code=403, detail="Access denied")

    repo.delete_file(file_id)

    return {"success": True, "deleted": True}


# =============================================================================
# Message endpoints (vendor-scoped)
# =============================================================================


@router.get("/messages")
async def get_messages(
    message_type: str | None = None,
    is_read: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    session_context: SessionContext = Depends(get_session_context),
):
    """Get messages for current vendor"""
    db = next(get_db())
    msg_repo = VendorMessageRepository(db, session_context)

    messages = msg_repo.list_messages_for_current_vendor(
        message_type=message_type,
        is_read=is_read,
        limit=limit,
        offset=offset,
    )
    stats = msg_repo.get_message_stats_for_current_vendor()

    return {
        "messages": [m.to_dict() for m in messages],
        "stats": stats,
        "vendor_context": session_context.current_vendor,
    }


@router.get("/messages/stats")
async def get_message_stats(
    session_context: SessionContext = Depends(get_session_context),
):
    """Get message stats for current vendor (unread count, type breakdown)"""
    db = next(get_db())
    msg_repo = VendorMessageRepository(db, session_context)

    return msg_repo.get_message_stats_for_current_vendor()


@router.get("/messages/{message_id}")
async def get_message(
    message_id: int,
    session_context: SessionContext = Depends(get_session_context),
):
    """Get a specific message"""
    db = next(get_db())
    msg_repo = VendorMessageRepository(db, session_context)

    msg = msg_repo.get_message(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    if msg.vendor_id != session_context.current_vendor_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return {"message": msg.to_dict()}


@router.post("/messages/{message_id}/read")
async def mark_message_read(
    message_id: int,
    session_context: SessionContext = Depends(get_session_context),
):
    """Mark a message as read"""
    db = next(get_db())
    msg_repo = VendorMessageRepository(db, session_context)

    msg = msg_repo.get_message(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    if msg.vendor_id != session_context.current_vendor_id:
        raise HTTPException(status_code=403, detail="Access denied")

    msg = msg_repo.mark_as_read(message_id)
    return {"success": True, "message": msg.to_dict()}


@router.post("/messages/read-all")
async def mark_all_messages_read(
    session_context: SessionContext = Depends(get_session_context),
):
    """Mark all messages as read for current vendor"""
    db = next(get_db())
    msg_repo = VendorMessageRepository(db, session_context)

    count = msg_repo.mark_all_as_read()
    return {"success": True, "messages_updated": count}


# =============================================================================
# Chat Assistant endpoints
# =============================================================================


class ChatRequest(BaseModel):
    """Chat message request"""

    message: str


@router.post("/chat")
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    session_context: SessionContext = Depends(get_session_context),
):
    """Stream a chat response from the AI assistant"""
    from finbot.agents.chat import ChatAssistant  # pylint: disable=import-outside-toplevel

    assistant = ChatAssistant(
        session_context=session_context,
        background_tasks=background_tasks,
    )

    return StreamingResponse(
        assistant.stream_response(request.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chat/history")
async def get_chat_history(
    limit: int = 100,
    session_context: SessionContext = Depends(get_session_context),
):
    """Get chat history for the current user and vendor"""
    db = next(get_db())
    repo = ChatMessageRepository(db, session_context)
    messages = repo.get_history(limit=limit)
    return {"messages": [m.to_dict() for m in messages]}


@router.delete("/chat/history")
async def clear_chat_history(
    session_context: SessionContext = Depends(get_session_context),
):
    """Clear chat history for the current user and vendor"""
    db = next(get_db())
    repo = ChatMessageRepository(db, session_context)
    count = repo.clear_history()
    return {"success": True, "messages_deleted": count}
