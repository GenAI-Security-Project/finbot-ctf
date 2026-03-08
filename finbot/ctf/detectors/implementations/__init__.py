"""Detector Implementations"""

# Imports trigger registration via decorators
from finbot.ctf.detectors.implementations.invoice_threshold_bypass import (
    InvoiceThresholdBypassDetector,
)
from finbot.ctf.detectors.implementations.invoice_trust_override import (
    InvoiceTrustOverrideDetector,
)
from finbot.ctf.detectors.implementations.policy_bypass_non_compliant import (
    PolicyBypassNonCompliantDetector,
)
from finbot.ctf.detectors.implementations.system_prompt_leak import (
    SystemPromptLeakDetector,
)
from finbot.ctf.detectors.implementations.vendor_risk_downplay import (
    VendorRiskDownplayDetector,
)
from finbot.ctf.detectors.implementations.vendor_status_flip import (
    VendorStatusFlipDetector,
)

__all__ = [
    "InvoiceThresholdBypassDetector",
    "InvoiceTrustOverrideDetector",
    "PolicyBypassNonCompliantDetector",
    "SystemPromptLeakDetector",
    "VendorRiskDownplayDetector",
    "VendorStatusFlipDetector",
]
