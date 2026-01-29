"""Prediction Calibration Service for ML model outputs.

Provides calibration fitting and application for predicted probabilities.
Supports Platt scaling and isotonic regression.
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss

logger = logging.getLogger(__name__)


class CalibrationMethod(str, Enum):
    """Supported calibration methods."""

    PLATT = "platt"
    ISOTONIC = "isotonic"


@dataclass
class CalibrationMetrics:
    """Calibration quality metrics."""

    brier_score: float
    expected_calibration_error: float
    calibration_slope: float | None = None
    calibration_intercept: float | None = None


@dataclass
class CalibrationCurve:
    """Calibration curve data."""

    prob_true: list[float]
    prob_pred: list[float]


@dataclass
class CalibrationRecord:
    """Stored calibration record for a model/version."""

    id: str
    model_name: str
    model_version: str
    method: CalibrationMethod
    sample_count: int
    created_at: datetime
    updated_at: datetime
    metrics: CalibrationMetrics
    curve: CalibrationCurve
    parameters: dict[str, Any] = field(default_factory=dict)
    calibrator: Any | None = None


class PredictionCalibrationService:
    """Service for fitting and applying calibration models."""

    def __init__(self) -> None:
        """Initialize calibration service."""
        self._records: dict[tuple[str, str], CalibrationRecord] = {}
        self._lock = threading.Lock()

    def list_calibrations(self) -> list[CalibrationRecord]:
        """List all calibration records."""
        return list(self._records.values())

    def get_calibration(self, model_name: str, model_version: str) -> CalibrationRecord | None:
        """Get calibration for model/version."""
        return self._records.get((model_name, model_version))

    def fit_calibration(
        self,
        model_name: str,
        model_version: str,
        y_true: list[int | float],
        y_pred: list[float],
        method: CalibrationMethod = CalibrationMethod.PLATT,
        n_bins: int = 10,
    ) -> CalibrationRecord:
        """Fit a calibration model and store it.

        Args:
            model_name: Model name.
            model_version: Model version.
            y_true: Ground-truth labels (0/1).
            y_pred: Predicted probabilities.
            method: Calibration method.
            n_bins: Bins for calibration curve/ECE.
        """
        y_true_arr, y_pred_arr = self._validate_inputs(y_true, y_pred)

        if method == CalibrationMethod.PLATT:
            record = self._fit_platt(
                model_name, model_version, y_true_arr, y_pred_arr, n_bins
            )
        elif method == CalibrationMethod.ISOTONIC:
            record = self._fit_isotonic(
                model_name, model_version, y_true_arr, y_pred_arr, n_bins
            )
        else:
            raise ValueError(f"Unsupported calibration method: {method}")

        with self._lock:
            self._records[(model_name, model_version)] = record

        return record

    def apply_calibration(
        self,
        model_name: str,
        model_version: str,
        scores: list[float],
        strict: bool = True,
    ) -> list[float]:
        """Apply calibration to a list of scores.

        Args:
            model_name: Model name.
            model_version: Model version.
            scores: Predicted probabilities to calibrate.
            strict: If True, raise when calibration is missing.
        """
        record = self.get_calibration(model_name, model_version)
        if record is None:
            if strict:
                raise KeyError(f"No calibration found for {model_name}:{model_version}")
            return scores

        scores_arr = np.asarray(scores, dtype=float)
        scores_arr = np.clip(scores_arr, 1e-6, 1 - 1e-6)

        if record.method == CalibrationMethod.PLATT:
            slope = float(record.parameters.get("slope", 1.0))
            intercept = float(record.parameters.get("intercept", 0.0))
            logits = self._logit(scores_arr)
            calibrated = self._sigmoid(slope * logits + intercept)
        elif record.method == CalibrationMethod.ISOTONIC:
            if record.calibrator is None:
                raise ValueError("Isotonic calibrator not available")
            calibrated = record.calibrator.predict(scores_arr)
        else:
            calibrated = scores_arr

        return calibrated.tolist()

    def _fit_platt(
        self,
        model_name: str,
        model_version: str,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        n_bins: int,
    ) -> CalibrationRecord:
        """Fit Platt scaling."""
        logits = self._logit(y_pred).reshape(-1, 1)
        lr = LogisticRegression(solver="lbfgs")
        lr.fit(logits, y_true)
        slope = float(lr.coef_[0][0])
        intercept = float(lr.intercept_[0])

        calibrated = self._sigmoid(slope * self._logit(y_pred) + intercept)

        metrics = self._compute_metrics(y_true, calibrated, n_bins, slope, intercept)
        curve = self._compute_curve(y_true, calibrated, n_bins)

        now = datetime.now(UTC)
        return CalibrationRecord(
            id=str(uuid4()),
            model_name=model_name,
            model_version=model_version,
            method=CalibrationMethod.PLATT,
            sample_count=len(y_true),
            created_at=now,
            updated_at=now,
            metrics=metrics,
            curve=curve,
            parameters={"slope": slope, "intercept": intercept},
            calibrator=lr,
        )

    def _fit_isotonic(
        self,
        model_name: str,
        model_version: str,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        n_bins: int,
    ) -> CalibrationRecord:
        """Fit isotonic regression calibration."""
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(y_pred, y_true)
        calibrated = iso.predict(y_pred)

        metrics = self._compute_metrics(y_true, calibrated, n_bins)
        curve = self._compute_curve(y_true, calibrated, n_bins)

        now = datetime.now(UTC)
        return CalibrationRecord(
            id=str(uuid4()),
            model_name=model_name,
            model_version=model_version,
            method=CalibrationMethod.ISOTONIC,
            sample_count=len(y_true),
            created_at=now,
            updated_at=now,
            metrics=metrics,
            curve=curve,
            parameters={"x_min": float(y_pred.min()), "x_max": float(y_pred.max())},
            calibrator=iso,
        )

    def _validate_inputs(
        self, y_true: list[int | float], y_pred: list[float]
    ) -> tuple[np.ndarray, np.ndarray]:
        if len(y_true) != len(y_pred):
            raise ValueError("y_true and y_pred must have the same length")
        if len(y_true) < 2:
            raise ValueError("At least two samples are required")

        y_true_arr = np.asarray(y_true, dtype=float)
        y_pred_arr = np.asarray(y_pred, dtype=float)

        if np.any((y_pred_arr < 0) | (y_pred_arr > 1)):
            raise ValueError("y_pred values must be between 0 and 1")

        if np.any((y_true_arr < 0) | (y_true_arr > 1)) or not np.all(
            np.isin(y_true_arr, [0, 1])
        ):
            raise ValueError("y_true values must be 0 or 1")

        unique = np.unique(y_true_arr)
        if len(unique) < 2:
            raise ValueError("y_true must contain at least two classes")

        return y_true_arr, np.clip(y_pred_arr, 1e-6, 1 - 1e-6)

    def _compute_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        n_bins: int,
        slope: float | None = None,
        intercept: float | None = None,
    ) -> CalibrationMetrics:
        brier = float(brier_score_loss(y_true, y_pred))
        ece = float(self._expected_calibration_error(y_true, y_pred, n_bins))
        return CalibrationMetrics(
            brier_score=round(brier, 4),
            expected_calibration_error=round(ece, 4),
            calibration_slope=round(slope, 4) if slope is not None else None,
            calibration_intercept=round(intercept, 4) if intercept is not None else None,
        )

    def _compute_curve(
        self, y_true: np.ndarray, y_pred: np.ndarray, n_bins: int
    ) -> CalibrationCurve:
        prob_true, prob_pred = calibration_curve(
            y_true, y_pred, n_bins=n_bins, strategy="uniform"
        )
        return CalibrationCurve(
            prob_true=[float(v) for v in prob_true],
            prob_pred=[float(v) for v in prob_pred],
        )

    def _expected_calibration_error(
        self, y_true: np.ndarray, y_pred: np.ndarray, n_bins: int
    ) -> float:
        bins = np.linspace(0.0, 1.0, n_bins + 1)
        ece = 0.0
        total = len(y_true)

        for i in range(n_bins):
            mask = (y_pred >= bins[i]) & (y_pred < bins[i + 1])
            if not np.any(mask):
                continue
            bin_true = y_true[mask]
            bin_pred = y_pred[mask]
            accuracy = float(np.mean(bin_true))
            confidence = float(np.mean(bin_pred))
            ece += abs(accuracy - confidence) * (len(bin_true) / total)

        return ece

    @staticmethod
    def _logit(values: np.ndarray) -> np.ndarray:
        return np.log(values / (1 - values))

    @staticmethod
    def _sigmoid(values: np.ndarray) -> np.ndarray:
        return 1 / (1 + np.exp(-values))


_prediction_calibration_service: PredictionCalibrationService | None = None
_prediction_calibration_lock = threading.Lock()


def get_prediction_calibration_service() -> PredictionCalibrationService:
    """Get singleton prediction calibration service."""
    global _prediction_calibration_service
    if _prediction_calibration_service is None:
        with _prediction_calibration_lock:
            if _prediction_calibration_service is None:
                _prediction_calibration_service = PredictionCalibrationService()
    return _prediction_calibration_service


def reset_prediction_calibration_service() -> None:
    """Reset prediction calibration service (testing only)."""
    global _prediction_calibration_service
    with _prediction_calibration_lock:
        _prediction_calibration_service = None
