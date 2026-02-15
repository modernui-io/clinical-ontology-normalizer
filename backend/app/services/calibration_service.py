"""Confidence Calibration Service (P3-005).

Provides calibration analysis for clinical prediction confidence scores.
Computes calibration bins, Expected Calibration Error (ECE), and generates
reliability diagram reports for batch evaluation of model predictions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any

logger = logging.getLogger(__name__)

NUM_BINS = 10


@dataclass
class Prediction:
    """A single prediction with confidence and ground truth."""

    predicted_confidence: float  # model's confidence in [0, 1]
    actual_outcome: bool  # whether the prediction was correct


@dataclass
class CalibrationBin:
    """A single bin in a calibration histogram."""

    bin_start: float
    bin_end: float
    predicted_confidence: float  # mean predicted confidence in this bin
    actual_accuracy: float  # fraction of correct predictions in this bin
    count: int  # number of predictions in this bin

    @property
    def calibration_gap(self) -> float:
        """Absolute difference between predicted confidence and actual accuracy."""
        return abs(self.predicted_confidence - self.actual_accuracy)

    @property
    def is_overconfident(self) -> bool:
        """True when predicted confidence exceeds actual accuracy."""
        return self.predicted_confidence > self.actual_accuracy

    @property
    def is_underconfident(self) -> bool:
        """True when actual accuracy exceeds predicted confidence."""
        return self.actual_accuracy > self.predicted_confidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "bin_start": self.bin_start,
            "bin_end": self.bin_end,
            "predicted_confidence": round(self.predicted_confidence, 4),
            "actual_accuracy": round(self.actual_accuracy, 4),
            "count": self.count,
            "calibration_gap": round(self.calibration_gap, 4),
        }


@dataclass
class CalibrationReport:
    """Full calibration report for a batch of predictions."""

    bins: list[CalibrationBin]
    ece: float  # Expected Calibration Error
    max_calibration_error: float  # Maximum calibration error across bins
    overconfident_bins: list[CalibrationBin]
    underconfident_bins: list[CalibrationBin]
    total_predictions: int
    overall_accuracy: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "bins": [b.to_dict() for b in self.bins],
            "ece": round(self.ece, 4),
            "max_calibration_error": round(self.max_calibration_error, 4),
            "overconfident_bin_count": len(self.overconfident_bins),
            "underconfident_bin_count": len(self.underconfident_bins),
            "total_predictions": self.total_predictions,
            "overall_accuracy": round(self.overall_accuracy, 4),
        }


def compute_calibration_bins(
    predictions: list[Prediction],
    num_bins: int = NUM_BINS,
) -> list[CalibrationBin]:
    """Divide predictions into equal-width bins across [0, 1].

    Args:
        predictions: List of Prediction objects.
        num_bins: Number of bins to use (default 10).

    Returns:
        List of CalibrationBin objects, one per bin.
    """
    if num_bins <= 0:
        raise ValueError("num_bins must be positive")

    bin_width = 1.0 / num_bins
    bins: list[CalibrationBin] = []

    for i in range(num_bins):
        bin_start = i * bin_width
        bin_end = (i + 1) * bin_width

        # Collect predictions falling into this bin
        in_bin = [
            p for p in predictions
            if bin_start <= p.predicted_confidence < bin_end
            or (i == num_bins - 1 and p.predicted_confidence == 1.0)
        ]

        if in_bin:
            mean_conf = sum(p.predicted_confidence for p in in_bin) / len(in_bin)
            accuracy = sum(1 for p in in_bin if p.actual_outcome) / len(in_bin)
        else:
            mean_conf = (bin_start + bin_end) / 2.0
            accuracy = 0.0

        bins.append(
            CalibrationBin(
                bin_start=round(bin_start, 4),
                bin_end=round(bin_end, 4),
                predicted_confidence=round(mean_conf, 4),
                actual_accuracy=round(accuracy, 4),
                count=len(in_bin),
            )
        )

    return bins


def expected_calibration_error(bins: list[CalibrationBin]) -> float:
    """Compute the Expected Calibration Error (ECE).

    ECE is the weighted average of per-bin calibration gaps, weighted by
    the fraction of samples in each bin.

    Args:
        bins: List of CalibrationBin objects.

    Returns:
        The ECE as a float in [0, 1].
    """
    total = sum(b.count for b in bins)
    if total == 0:
        return 0.0

    ece = sum(b.count * b.calibration_gap for b in bins) / total
    return round(ece, 6)


def max_calibration_error(bins: list[CalibrationBin]) -> float:
    """Compute the Maximum Calibration Error (MCE) across non-empty bins.

    Args:
        bins: List of CalibrationBin objects.

    Returns:
        The MCE as a float in [0, 1].
    """
    non_empty = [b for b in bins if b.count > 0]
    if not non_empty:
        return 0.0
    return round(max(b.calibration_gap for b in non_empty), 6)


def generate_calibration_report(
    predictions: list[Prediction],
    num_bins: int = NUM_BINS,
) -> CalibrationReport:
    """Generate a full calibration report for a batch of predictions.

    Args:
        predictions: List of Prediction objects with confidence and outcome.
        num_bins: Number of bins for the calibration histogram.

    Returns:
        A CalibrationReport containing bins, ECE, MCE, and bin classification.
    """
    if not predictions:
        return CalibrationReport(
            bins=[],
            ece=0.0,
            max_calibration_error=0.0,
            overconfident_bins=[],
            underconfident_bins=[],
            total_predictions=0,
            overall_accuracy=0.0,
        )

    bins = compute_calibration_bins(predictions, num_bins)
    ece = expected_calibration_error(bins)
    mce = max_calibration_error(bins)

    non_empty = [b for b in bins if b.count > 0]
    overconfident = [b for b in non_empty if b.is_overconfident]
    underconfident = [b for b in non_empty if b.is_underconfident]

    total = len(predictions)
    correct = sum(1 for p in predictions if p.actual_outcome)
    overall_accuracy = correct / total if total > 0 else 0.0

    report = CalibrationReport(
        bins=bins,
        ece=ece,
        max_calibration_error=mce,
        overconfident_bins=overconfident,
        underconfident_bins=underconfident,
        total_predictions=total,
        overall_accuracy=round(overall_accuracy, 4),
    )

    logger.info(
        "Calibration report: %d predictions, ECE=%.4f, MCE=%.4f, accuracy=%.2f%%",
        total,
        ece,
        mce,
        overall_accuracy * 100,
    )

    return report
