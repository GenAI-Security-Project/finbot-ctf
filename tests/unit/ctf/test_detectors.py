"""
Unit tests for BaseDetector config validation.

Covers:
- DET-THR-NEG-001: Non-dict config raises TypeError
"""

import pytest

from finbot.ctf.detectors.implementations.invoice_threshold_bypass import (
    InvoiceThresholdBypassDetector,
)


class TestNegativeCases:
    """Negative-path tests for detector initialisation."""

    @pytest.mark.parametrize(
        "bad_config",
        [
            "not_a_dict",
            ["a", "list"],
            42,
            True,
            (1, 2),
        ],
        ids=["string", "list", "int", "bool", "tuple"],
    )
    def test_det_thr_neg_001_invalid_config_type(self, bad_config):
        """BaseDetector must raise TypeError when config is not a dict."""
        with pytest.raises(TypeError, match="config must be a dict"):
            InvoiceThresholdBypassDetector(
                challenge_id="test", config=bad_config
            )

    def test_none_config_is_accepted(self):
        """config=None (the default) must still work."""
        det = InvoiceThresholdBypassDetector(challenge_id="test", config=None)
        assert det.config == {}

    def test_empty_dict_config_is_accepted(self):
        """config={} must still work."""
        det = InvoiceThresholdBypassDetector(challenge_id="test", config={})
        assert det.config == {}
