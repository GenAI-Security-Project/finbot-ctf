"""Tools for the FinBot platform"""

from finbot.tools.data import (
    flag_invoice_for_review,
    get_invoice_details,
    get_invoice_for_payment,
    get_vendor_details,
    get_vendor_invoices,
    get_vendor_payment_summary,
    get_vendor_risk_profile,
    process_payment,
    update_fraud_agent_notes,
    update_invoice_agent_notes,
    update_invoice_status,
    update_payment_agent_notes,
    update_vendor_agent_notes,
    update_vendor_risk,
    update_vendor_status,
)
from finbot.tools.fn import (
    calculate_tax,
    get_vendor_contact_info,
    send_invoice_notification,
    send_vendor_notification,
)

__all__ = [
    # Vendor tools
    "get_vendor_details",
    "update_vendor_status",
    "update_vendor_agent_notes",
    # Invoice tools
    "get_invoice_details",
    "update_invoice_status",
    "update_invoice_agent_notes",
    # Payment tools
    "get_invoice_for_payment",
    "process_payment",
    "get_vendor_payment_summary",
    "update_payment_agent_notes",
    # Fraud tools
    "get_vendor_risk_profile",
    "get_vendor_invoices",
    "update_vendor_risk",
    "flag_invoice_for_review",
    "update_fraud_agent_notes",
    # Function tools
    "calculate_tax",
    "send_vendor_notification",
    "send_invoice_notification",
    "get_vendor_contact_info",
]
