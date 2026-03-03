"""Notification tool functions for the Communication Agent"""

import logging
from typing import Any

from finbot.core.auth.session import SessionContext
from finbot.core.data.database import get_db
from finbot.core.data.repositories import (
    InvoiceRepository,
    VendorMessageRepository,
    VendorRepository,
)

logger = logging.getLogger(__name__)


async def send_vendor_notification(
    vendor_id: int,
    subject: str,
    message: str,
    notification_type: str,
    session_context: SessionContext,
) -> dict[str, Any]:
    """Send a notification to a vendor

    In production, this would send an actual email via the email provider.
    Currently logs the notification and returns a confirmation.

    Args:
        vendor_id: The ID of the vendor to notify
        subject: Notification subject
        message: Notification message body
        notification_type: Type of notification ('status_update', 'payment_update',
                          'compliance_alert', 'general')
        session_context: The session context

    Returns:
        Dictionary confirming the notification was sent
    """
    logger.info(
        "Sending vendor notification: vendor_id=%s, type=%s, subject=%s",
        vendor_id,
        notification_type,
        subject,
    )
    db = next(get_db())
    vendor_repo = VendorRepository(db, session_context)
    vendor = vendor_repo.get_vendor(vendor_id)
    if not vendor:
        raise ValueError("Vendor not found")

    # Persist to vendor inbox
    msg_repo = VendorMessageRepository(db, session_context)
    stored = msg_repo.create_message(
        vendor_id=vendor_id,
        subject=subject,
        body=message,
        message_type=notification_type,
        sender_name="CineFlow Productions - FinBot",
        channel="email",
    )

    return {
        "notification_sent": True,
        "message_id": stored.id,
        "vendor_id": vendor_id,
        "recipient_email": vendor.email,
        "recipient_name": vendor.company_name,
        "subject": subject,
        "notification_type": notification_type,
        "message_preview": message[:200] if len(message) > 200 else message,
    }


async def send_invoice_notification(
    invoice_id: int,
    subject: str,
    message: str,
    notification_type: str,
    session_context: SessionContext,
) -> dict[str, Any]:
    """Send a notification related to an invoice

    Args:
        invoice_id: The ID of the related invoice
        subject: Notification subject
        message: Notification message body
        notification_type: Type of notification ('status_update', 'payment_confirmation',
                          'action_required', 'reminder')
        session_context: The session context

    Returns:
        Dictionary confirming the notification was sent
    """
    logger.info(
        "Sending invoice notification: invoice_id=%s, type=%s, subject=%s",
        invoice_id,
        notification_type,
        subject,
    )
    db = next(get_db())
    invoice_repo = InvoiceRepository(db, session_context)
    invoice = invoice_repo.get_invoice(invoice_id)
    if not invoice:
        raise ValueError("Invoice not found")

    # Get vendor details for recipient info
    vendor_repo = VendorRepository(db, session_context)
    vendor = vendor_repo.get_vendor(invoice.vendor_id)
    if not vendor:
        raise ValueError("Vendor not found for this invoice")

    # Persist to vendor inbox
    msg_repo = VendorMessageRepository(db, session_context)
    stored = msg_repo.create_message(
        vendor_id=vendor.id,
        subject=subject,
        body=message,
        message_type=notification_type,
        sender_name="CineFlow Productions - FinBot",
        channel="email",
        related_invoice_id=invoice_id,
    )

    return {
        "notification_sent": True,
        "message_id": stored.id,
        "invoice_id": invoice_id,
        "invoice_number": invoice.invoice_number,
        "vendor_id": vendor.id,
        "recipient_email": vendor.email,
        "recipient_name": vendor.company_name,
        "subject": subject,
        "notification_type": notification_type,
        "message_preview": message[:200] if len(message) > 200 else message,
    }


async def get_vendor_contact_info(
    vendor_id: int,
    session_context: SessionContext,
) -> dict[str, Any]:
    """Get vendor contact information for communication purposes

    Args:
        vendor_id: The ID of the vendor
        session_context: The session context

    Returns:
        Dictionary containing vendor contact details
    """
    logger.info("Getting vendor contact info for vendor_id: %s", vendor_id)
    db = next(get_db())
    vendor_repo = VendorRepository(db, session_context)
    vendor = vendor_repo.get_vendor(vendor_id)
    if not vendor:
        raise ValueError("Vendor not found")

    return {
        "vendor_id": vendor.id,
        "company_name": vendor.company_name,
        "contact_name": vendor.contact_name,
        "email": vendor.email,
        "phone": vendor.phone,
        "status": vendor.status,
    }
