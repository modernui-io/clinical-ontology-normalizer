"""Tests for Calibration Service (P3-005)."""

import pytest

from app.services.calibration_service import (
    Prediction,
    CalibrationBin,
    CalibrationReport,
    compute_calibration_bins,
    expected_calibration_error,
    max_calibration_error,
    generate_calibration_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_predictions(n: int, confidence: float, accuracy: float) -> list[Prediction]:
    """Generate n predictions at a fixed confidence with given accuracy rate."""
    correct_count = int(n * accuracy)
    preds = []
    for i in range(n):
        preds.append(Prediction(
            predicted_confidence=confidence,
            actual_outcome=i < correct_count,
        ))
    return preds


# ---------------------------------------------------------------------------
# CalibrationBin
# ---------------------------------------------------------------------------


class TestCalibrationBin:
    def test_calibration_gap(self):
        b = CalibrationBin(0.0, 0.1, 0.05, 0.10, 10)
        assert abs(b.calibration_gap - 0.05) < 1e-6

    def test_overconfident(self):
        b = CalibrationBin(0.8, 0.9, 0.85, 0.60, 20)
        assert b.is_overconfident
        assert not b.is_underconfident

    def test_underconfident(self):
        b = CalibrationBin(0.2, 0.3, 0.25, 0.50, 15)
        assert b.is_underconfident
        assert not b.is_overconfident

    def test_perfectly_calibrated(self):
        b = CalibrationBin(0.5, 0.6, 0.55, 0.55, 10)
        assert b.calibration_gap == 0.0
        assert not b.is_overconfident
        assert not b.is_underconfident

    def test_to_dict(self):
        b = CalibrationBin(0.0, 0.1, 0.05, 0.08, 5)
        d = b.to_dict()
        assert "bin_start" in d
        assert "calibration_gap" in d


# ---------------------------------------------------------------------------
# compute_calibration_bins
# ---------------------------------------------------------------------------


class TestComputeCalibrationBins:
    def test_returns_correct_number_of_bins(self):
        preds = _make_predictions(100, 0.5, 0.5)
        bins = compute_calibration_bins(preds, num_bins=10)
        assert len(bins) == 10

    def test_custom_bin_count(self):
        preds = _make_predictions(50, 0.3, 0.3)
        bins = compute_calibration_bins(preds, num_bins=5)
        assert len(bins) == 5

    def test_empty_predictions(self):
        bins = compute_calibration_bins([], num_bins=10)
        assert len(bins) == 10
        for b in bins:
            assert b.count == 0

    def test_all_predictions_in_one_bin(self):
        preds = _make_predictions(20, 0.55, 0.80)
        bins = compute_calibration_bins(preds, num_bins=10)
        # All preds at 0.55 should be in bin [0.5, 0.6)
        counts = [b.count for b in bins]
        assert sum(counts) == 20
        assert bins[5].count == 20  # bin index 5 = [0.5, 0.6)

    def test_invalid_num_bins(self):
        with pytest.raises(ValueError):
            compute_calibration_bins([], num_bins=0)

    def test_confidence_1_0_goes_in_last_bin(self):
        preds = [Prediction(predicted_confidence=1.0, actual_outcome=True)]
        bins = compute_calibration_bins(preds, num_bins=10)
        assert bins[9].count == 1


# ---------------------------------------------------------------------------
# expected_calibration_error
# ---------------------------------------------------------------------------


class TestExpectedCalibrationError:
    def test_perfectly_calibrated(self):
        bins = [CalibrationBin(0.0, 1.0, 0.5, 0.5, 100)]
        assert expected_calibration_error(bins) == 0.0

    def test_worst_case(self):
        bins = [CalibrationBin(0.0, 1.0, 1.0, 0.0, 100)]
        assert expected_calibration_error(bins) == 1.0

    def test_empty_bins(self):
        bins = [CalibrationBin(0.0, 0.5, 0.25, 0.0, 0)]
        assert expected_calibration_error(bins) == 0.0

    def test_weighted_average(self):
        bins = [
            CalibrationBin(0.0, 0.5, 0.25, 0.25, 80),  # gap=0
            CalibrationBin(0.5, 1.0, 0.75, 0.50, 20),  # gap=0.25
        ]
        ece = expected_calibration_error(bins)
        # (80*0 + 20*0.25) / 100 = 0.05
        assert abs(ece - 0.05) < 1e-4


# ---------------------------------------------------------------------------
# max_calibration_error
# ---------------------------------------------------------------------------


class TestMaxCalibrationError:
    def test_single_bin(self):
        bins = [CalibrationBin(0.0, 1.0, 0.9, 0.3, 50)]
        assert abs(max_calibration_error(bins) - 0.6) < 1e-4

    def test_ignores_empty_bins(self):
        bins = [
            CalibrationBin(0.0, 0.5, 0.25, 0.25, 10),
            CalibrationBin(0.5, 1.0, 0.75, 0.0, 0),  # empty
        ]
        assert max_calibration_error(bins) == 0.0  # only non-empty bin has gap 0


# ---------------------------------------------------------------------------
# generate_calibration_report
# ---------------------------------------------------------------------------


class TestGenerateCalibrationReport:
    def test_empty_predictions(self):
        report = generate_calibration_report([])
        assert isinstance(report, CalibrationReport)
        assert report.total_predictions == 0
        assert report.ece == 0.0

    def test_full_report_structure(self):
        preds = _make_predictions(50, 0.7, 0.5)
        report = generate_calibration_report(preds)
        assert report.total_predictions == 50
        assert 0.0 <= report.ece <= 1.0
        assert 0.0 <= report.max_calibration_error <= 1.0
        assert isinstance(report.overconfident_bins, list)
        assert isinstance(report.underconfident_bins, list)

    def test_overconfident_model(self):
        # High confidence, low accuracy -> overconfident
        preds = _make_predictions(100, 0.95, 0.20)
        report = generate_calibration_report(preds)
        assert len(report.overconfident_bins) > 0
        assert report.ece > 0.5

    def test_well_calibrated_model(self):
        # Confidence matches accuracy
        preds = _make_predictions(100, 0.55, 0.55)
        report = generate_calibration_report(preds)
        # ECE should be very low
        assert report.ece < 0.05

    def test_to_dict(self):
        preds = _make_predictions(30, 0.6, 0.6)
        report = generate_calibration_report(preds)
        d = report.to_dict()
        assert "ece" in d
        assert "bins" in d
        assert "total_predictions" in d
        assert d["total_predictions"] == 30
