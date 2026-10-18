"""
Numeric detector configuration validation tests.

Covers the numeric detector config keys that are validated in
_validate_config() and then read back with a default in check_event().
A key present with a None value has to be rejected at construction,
otherwise the default never applies and check_event() compares against
None, which raises TypeError and takes the detector out for the rest of
the process.

This is the numeric counterpart of the list-typed keys covered in
test_detector_config_validation.py.
"""

import pytest

from finbot.ctf.detectors.implementations.invoice_threshold_bypass import (
    DEFAULT_MAX_INVOICE_AMOUNT,
    InvoiceThresholdBypassDetector,
)
from finbot.ctf.detectors.implementations.invoice_trust_override import (
    DEFAULT_MIN_AMOUNT,
    InvoiceTrustOverrideDetector,
)

NUMERIC_CONFIG_KEYS = [
    (InvoiceThresholdBypassDetector, "max_invoice_amount", DEFAULT_MAX_INVOICE_AMOUNT),
    (InvoiceTrustOverrideDetector, "min_amount", DEFAULT_MIN_AMOUNT),
]


class TestNoneRejected:
    """A present-but-None numeric config must not reach check_event()."""

    @pytest.mark.parametrize("detector_cls, key, _default", NUMERIC_CONFIG_KEYS)
    def test_none_value_rejected(self, detector_cls, key, _default) -> None:
        with pytest.raises(ValueError, match="positive number"):
            detector_cls(challenge_id="c", config={key: None})

    @pytest.mark.parametrize("detector_cls, key, _default", NUMERIC_CONFIG_KEYS)
    def test_non_numeric_still_rejected(self, detector_cls, key, _default) -> None:
        with pytest.raises(ValueError, match="positive number"):
            detector_cls(challenge_id="c", config={key: "not a number"})

    @pytest.mark.parametrize("detector_cls, key, _default", NUMERIC_CONFIG_KEYS)
    def test_non_positive_still_rejected(self, detector_cls, key, _default) -> None:
        with pytest.raises(ValueError, match="positive number"):
            detector_cls(challenge_id="c", config={key: 0})


class TestValidConfigs:
    """The accepted shapes keep working."""

    @pytest.mark.parametrize("detector_cls, key, _default", NUMERIC_CONFIG_KEYS)
    def test_positive_value_accepted(self, detector_cls, key, _default) -> None:
        detector = detector_cls(challenge_id="c", config={key: 5000})
        assert detector.config[key] == 5000

    @pytest.mark.parametrize("detector_cls, key, default", NUMERIC_CONFIG_KEYS)
    def test_omitted_key_falls_back_to_default(self, detector_cls, key, default) -> None:
        detector = detector_cls(challenge_id="c", config={})
        assert detector.config.get(key, default) == default

    @pytest.mark.parametrize("detector_cls, key, default", NUMERIC_CONFIG_KEYS)
    def test_no_config_falls_back_to_default(self, detector_cls, key, default) -> None:
        detector = detector_cls(challenge_id="c")
        assert detector.config.get(key, default) == default
