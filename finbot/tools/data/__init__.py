"""Data tools to fetch/write model data from/to various data sources"""

from finbot.tools.data.fraud import (
    flag_invoice_for_review,
    get_vendor_invoices,
    get_vendor_risk_profile,
    update_fraud_agent_notes,
    update_vendor_risk,
)
from finbot.tools.data.invoice import (
    get_invoice_details,
    update_invoice_agent_notes,
    update_invoice_status,
)
from finbot.tools.data.payment import (
    get_invoice_for_payment,
    get_vendor_payment_summary,
    process_payment,
    update_payment_agent_notes,
)
from finbot.tools.data.vendor import (
    get_vendor_details,
    update_vendor_agent_notes,
    update_vendor_status,
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
]
