"""
Detector configuration validation tests.

Covers the list-typed detector config keys that are validated in
_validate_config() and then read back with a default in check_event().
A key present with a None value has to be rejected at construction,
otherwise the default never applies and check_event() iterates over None.

Test IDs match the ones named in the bug reports:
  DET-POL-NEG-001  prohibited_keywords=None
  DET-VSF-NEG-001  prohibited_indicators=None
"""

import pytest

from finbot.ctf.detectors.implementations.gradual_status_flip import (
    GradualStatusFlipDetector,
)
from finbot.ctf.detectors.implementations.policy_bypass_non_compliant import (
    DEFAULT_PROHIBITED_KEYWORDS,
    PolicyBypassNonCompliantDetector,
)
from finbot.ctf.detectors.implementations.vendor_status_flip import (
    DEFAULT_PROHIBITED_INDICATORS,
    VendorStatusFlipDetector,
)

LIST_CONFIG_KEYS = [
    (PolicyBypassNonCompliantDetector, "prohibited_keywords", DEFAULT_PROHIBITED_KEYWORDS),
    (VendorStatusFlipDetector, "prohibited_indicators", DEFAULT_PROHIBITED_INDICATORS),
    (GradualStatusFlipDetector, "prohibited_indicators", DEFAULT_PROHIBITED_INDICATORS),
]


class TestNegativeCases:
    """A present-but-None list config must not reach check_event()."""

    def test_det_pol_neg_001_prohibited_keywords_none(self) -> None:
        with pytest.raises(ValueError, match="list"):
            PolicyBypassNonCompliantDetector(challenge_id="c", config={"prohibited_keywords": None})

    def test_det_vsf_neg_001_prohibited_indicators_none(self) -> None:
        with pytest.raises(ValueError, match="list"):
            VendorStatusFlipDetector(challenge_id="c", config={"prohibited_indicators": None})

    def test_gradual_status_flip_prohibited_indicators_none(self) -> None:
        with pytest.raises(ValueError, match="list"):
            GradualStatusFlipDetector(challenge_id="c", config={"prohibited_indicators": None})

    @pytest.mark.parametrize("detector_cls, key, _default", LIST_CONFIG_KEYS)
    def test_non_list_config_still_rejected(self, detector_cls, key, _default) -> None:
        with pytest.raises(ValueError, match="list"):
            detector_cls(challenge_id="c", config={key: 42})


class TestValidConfigs:
    """The accepted shapes keep working."""

    @pytest.mark.parametrize("detector_cls, key, _default", LIST_CONFIG_KEYS)
    def test_list_value_accepted(self, detector_cls, key, _default) -> None:
        detector = detector_cls(challenge_id="c", config={key: ["casino"]})
        assert detector.config[key] == ["casino"]

    @pytest.mark.parametrize("detector_cls, key, default", LIST_CONFIG_KEYS)
    def test_omitted_key_falls_back_to_default(self, detector_cls, key, default) -> None:
        detector = detector_cls(challenge_id="c", config={})
        assert detector.config.get(key, default) == default

    @pytest.mark.parametrize("detector_cls, key, default", LIST_CONFIG_KEYS)
    def test_no_config_falls_back_to_default(self, detector_cls, key, default) -> None:
        detector = detector_cls(challenge_id="c")
        assert detector.config.get(key, default) == default
