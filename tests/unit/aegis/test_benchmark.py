# ============================================================
# File: tests/unit/aegis/test_benchmark.py
# Purpose: Unit tests for detector precision/recall/F1 utilities
# Author: Jean Francois Regis MUKIZA
# GSoC Week: 8
# OWASP Category: ASI09 Human Trust Exploitation (measurement)
# ============================================================
"""Tests for the red-team harness detector benchmark."""

import pytest

from finbot.aegis.harness.benchmark import benchmark_detector, compute_f1


class TestComputeF1:
    def test_perfect_detector(self):
        assert compute_f1(tp=5, fp=0, fn=0) == (1.0, 1.0, 1.0)

    def test_mixed_counts(self):
        precision, recall, f1 = compute_f1(tp=3, fp=1, fn=2)
        assert precision == pytest.approx(0.75)
        assert recall == pytest.approx(0.6)
        assert f1 == pytest.approx(2 * 0.75 * 0.6 / (0.75 + 0.6))

    def test_no_positives_does_not_divide_by_zero(self):
        assert compute_f1(tp=0, fp=0, fn=0) == (0.0, 0.0, 0.0)

    def test_only_false_positives(self):
        assert compute_f1(tp=0, fp=4, fn=0) == (0.0, 0.0, 0.0)


class TestBenchmarkDetector:
    def test_counts_and_scores(self):
        predictions = [True, True, False, True, False]
        ground_truth = [True, False, True, True, False]
        result = benchmark_detector("vendor_risk_downplay", predictions, ground_truth)
        assert result.detector_id == "vendor_risk_downplay"
        assert (result.true_positive, result.false_positive, result.false_negative) == (2, 1, 1)
        assert result.precision == pytest.approx(2 / 3)
        assert result.recall == pytest.approx(2 / 3)
        assert result.f1 == pytest.approx(2 / 3)

    def test_length_mismatch_is_rejected(self):
        with pytest.raises(ValueError):
            benchmark_detector("d", [True, False], [True])
