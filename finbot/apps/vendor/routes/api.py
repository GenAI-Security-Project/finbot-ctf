"""Vendor Portal API Routes"""

import secrets
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from finbot.agents.runner import run_invoice_agent, run_onboarding_agent
from finbot.core.auth.middleware import get_session_context
from finbot.core.auth.session import SessionContext
from finbot.core.data.database import get_db
from finbot.core.data.repositories import InvoiceRepository, VendorRepository
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

        # Run the onboarding agent
        workflow_id = f"wf_{secrets.token_urlsafe(12)}"

        # queue background task to run the onboarding agent
        background_tasks.add_task(
            run_onboarding_agent,
            task_data={
                "vendor_id": vendor.id,
                "description": "Evaluate and onboard a new vendor with provided vendor_id",
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

    success = vendor_repo.delete_vendor(vendor_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete vendor")

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

        # Queue background task to run the onboarding agent
        background_tasks.add_task(
            run_onboarding_agent,
            task_data={
                "vendor_id": vendor.id,
                "description": "Re-evaluate vendor profile and update status based on current data",
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

    invoice_stats = invoice_repo.get_current_vendor_invoice_stats()

    return {
        "vendor_context": session_context.current_vendor,
        "metrics": {
            "invoices": invoice_stats,
            "completion_rate": (
                invoice_stats["paid_count"] / max(invoice_stats["total_count"], 1) * 100
            ),
        },
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

        # Run the invoice processing agent
        workflow_id = f"wf_{secrets.token_urlsafe(12)}"

        # queue background task to run the process invoice
        background_tasks.add_task(
            run_invoice_agent,
            task_data={
                "invoice_id": invoice.id,
                "description": "Please process a new invoice for this vendor with provided invoice_id",
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

    # Queue background task to run the invoice processing agent
    background_tasks.add_task(
        run_invoice_agent,
        task_data={
            "invoice_id": invoice.id,
            "description": "Please re-process this invoice and update the status and review notes",
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
