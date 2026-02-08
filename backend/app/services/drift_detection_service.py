"""Drift Detection Service.

Monitors model and data drift for clinical trial patient screening pipelines.
Implements:
- Population Stability Index (PSI) for categorical/histogram features
- Kolmogorov-Smirnov test for continuous distributions
- Chi-squared test for categorical count distributions
- Baseline snapshot management
- Feature-level drift tracking
- Model performance drift detection (rolling accuracy windows)
- Aggregated drift reports with recommendations

All statistical calculations use only the ``math`` module (no scipy/numpy).
"""

from __future__ import annotations

import logging
import math
import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.schemas.drift_detection import (
    BaselineResponse,
    DataPointResponse,
    DriftAnalysis,
    DriftHistory,
    DriftHistoryEntry,
    DriftRecommendation,
    DriftReport,
    DriftSeverity,
    FeatureDrift,
    MonitorStatus,
    MonitorType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers (pure math, no external deps)
# ---------------------------------------------------------------------------

_EPS = 1e-10  # guard against log(0)


def _normalize(values: list[float]) -> list[float]:
    """Normalize a list of values so they sum to 1 (probability distribution)."""
    total = sum(values)
    if total <= 0:
        n = len(values) if values else 1
        return [1.0 / n] * n
    return [v / total for v in values]


def calculate_psi(expected: list[float], actual: list[float]) -> float:
    """Calculate Population Stability Index between two distributions.

    Both ``expected`` and ``actual`` are bin counts or proportions.
    They are internally normalised so raw counts work too.

    PSI = SUM( (actual_i - expected_i) * ln(actual_i / expected_i) )

    Returns 0.0 if both distributions are empty.
    """
    if not expected and not actual:
        return 0.0

    # Pad shorter list with zeros
    max_len = max(len(expected), len(actual))
    exp = list(expected) + [0.0] * (max_len - len(expected))
    act = list(actual) + [0.0] * (max_len - len(actual))

    p = _normalize(exp)
    q = _normalize(act)

    psi = 0.0
    for pi, qi in zip(p, q):
        pi = max(pi, _EPS)
        qi = max(qi, _EPS)
        psi += (qi - pi) * math.log(qi / pi)

    return max(psi, 0.0)


def calculate_ks_statistic(
    sample_a: list[float], sample_b: list[float]
) -> tuple[float, float]:
    """Kolmogorov-Smirnov two-sample test.

    Returns (ks_statistic, approximate_p_value).

    The p-value is an asymptotic approximation using the Kolmogorov distribution:
        p ~ 2 * exp(-2 * lambda^2)  where lambda = D * sqrt(n*m / (n+m))

    This is accurate for large samples and conservative for small ones.
    """
    n = len(sample_a)
    m = len(sample_b)

    if n == 0 or m == 0:
        return (0.0, 1.0)

    all_values = sorted(set(sample_a + sample_b))

    # Build empirical CDFs
    cdf_a = 0.0
    cdf_b = 0.0
    max_diff = 0.0

    idx_a = 0
    idx_b = 0
    sorted_a = sorted(sample_a)
    sorted_b = sorted(sample_b)

    for val in all_values:
        while idx_a < n and sorted_a[idx_a] <= val:
            idx_a += 1
        while idx_b < m and sorted_b[idx_b] <= val:
            idx_b += 1
        cdf_a = idx_a / n
        cdf_b = idx_b / m
        diff = abs(cdf_a - cdf_b)
        if diff > max_diff:
            max_diff = diff

    # Asymptotic p-value approximation
    en = math.sqrt(n * m / (n + m))
    lam = (en + 0.12 + 0.11 / en) * max_diff

    if lam <= 0:
        p_value = 1.0
    else:
        # Kolmogorov distribution approximation
        p_value = 2.0 * math.exp(-2.0 * lam * lam)
        p_value = min(max(p_value, 0.0), 1.0)

    return (max_diff, p_value)


def calculate_chi_squared(observed: list[float], expected: list[float]) -> tuple[float, float]:
    """Chi-squared goodness-of-fit test.

    Returns (chi2_statistic, approximate_p_value).

    The p-value uses Wilson-Hilferty approximation for the chi-squared CDF.
    """
    if not observed or not expected:
        return (0.0, 1.0)

    max_len = max(len(observed), len(expected))
    obs = list(observed) + [0.0] * (max_len - len(observed))
    exp = list(expected) + [0.0] * (max_len - len(expected))

    # Scale expected to match observed total
    obs_total = sum(obs)
    exp_total = sum(exp)

    if exp_total <= 0 or obs_total <= 0:
        return (0.0, 1.0)

    scale = obs_total / exp_total
    exp_scaled = [e * scale for e in exp]

    chi2 = 0.0
    df = 0
    for o, e in zip(obs, exp_scaled):
        if e > _EPS:
            chi2 += (o - e) ** 2 / e
            df += 1

    df = max(df - 1, 1)  # degrees of freedom

    # Wilson-Hilferty approximation for chi-squared CDF
    # P(X > chi2) ~ P(Z > z) where z = ((chi2/df)^(1/3) - (1 - 2/(9*df))) / sqrt(2/(9*df))
    if df > 0 and chi2 > 0:
        term = 2.0 / (9.0 * df)
        z = ((chi2 / df) ** (1.0 / 3.0) - (1.0 - term)) / math.sqrt(term)
        # Approximate standard normal CDF using error function
        p_value = 0.5 * (1.0 - _erf(z / math.sqrt(2.0)))
        p_value = min(max(p_value, 0.0), 1.0)
    else:
        p_value = 1.0

    return (chi2, p_value)


def _erf(x: float) -> float:
    """Approximation of the error function (Abramowitz and Stegun 7.1.26)."""
    sign = 1 if x >= 0 else -1
    x = abs(x)
    a1, a2, a3, a4, a5 = (
        0.254829592,
        -0.284496736,
        1.421413741,
        -1.453152027,
        1.061405429,
    )
    p = 0.3275911
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    return sign * y


def classify_severity(psi: float) -> DriftSeverity:
    """Classify drift severity based on PSI thresholds.

    NONE:     PSI < 0.1
    LOW:      0.1 <= PSI < 0.25
    MODERATE: 0.25 <= PSI < 0.5
    HIGH:     PSI >= 0.5
    """
    if psi < 0.1:
        return DriftSeverity.NONE
    elif psi < 0.25:
        return DriftSeverity.LOW
    elif psi < 0.5:
        return DriftSeverity.MODERATE
    else:
        return DriftSeverity.HIGH


def _recommend(severity: DriftSeverity) -> DriftRecommendation:
    """Map overall severity to a recommendation."""
    if severity == DriftSeverity.HIGH:
        return DriftRecommendation.RETRAIN
    elif severity in (DriftSeverity.MODERATE, DriftSeverity.LOW):
        return DriftRecommendation.MONITOR
    else:
        return DriftRecommendation.STABLE


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------


class _MonitorData:
    """Internal state for a single monitor."""

    __slots__ = (
        "name",
        "monitor_type",
        "description",
        "is_active",
        "data_points",
        "created_at",
    )

    def __init__(
        self,
        name: str,
        monitor_type: MonitorType,
        description: str = "",
    ) -> None:
        self.name = name
        self.monitor_type = monitor_type
        self.description = description
        self.is_active = True
        self.data_points: list[tuple[datetime, float, dict[str, Any]]] = []
        self.created_at = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class DriftDetectionService:
    """In-memory drift detection and monitoring service."""

    def __init__(self) -> None:
        # Baselines: id -> BaselineResponse
        self._baselines: dict[str, BaselineResponse] = {}
        # Monitors: name -> _MonitorData
        self._monitors: dict[str, _MonitorData] = {}
        # Drift history entries (global)
        self._drift_history: list[DriftHistoryEntry] = []
        # Latest drift report
        self._latest_report: DriftReport | None = None
        # Model accuracy tracking: list of (timestamp, predicted, actual)
        self._model_outcomes: list[tuple[datetime, bool, bool]] = []
        self._lock = threading.Lock()

        # Initialise pre-defined monitors
        self._init_predefined_monitors()

    # ------------------------------------------------------------------
    # Pre-defined monitors
    # ------------------------------------------------------------------

    def _init_predefined_monitors(self) -> None:
        """Set up pre-defined monitors for clinical trial screening."""
        predefined = [
            (
                "patient_age_distribution",
                MonitorType.CONTINUOUS,
                "Track age distribution of screened patients",
            ),
            (
                "condition_prevalence",
                MonitorType.CATEGORICAL,
                "Track prevalence of key conditions (DME, AD, CSCC)",
            ),
            (
                "screening_pass_rate",
                MonitorType.RATE,
                "Track pass rate per trial over time",
            ),
            (
                "match_score_distribution",
                MonitorType.CONTINUOUS,
                "Track distribution of match scores",
            ),
            (
                "lab_value_ranges",
                MonitorType.CONTINUOUS,
                "Track HbA1c, eGFR distributions",
            ),
        ]
        for name, mtype, desc in predefined:
            self._monitors[name] = _MonitorData(name, mtype, desc)

    # ------------------------------------------------------------------
    # Baseline management
    # ------------------------------------------------------------------

    def create_baseline(
        self,
        name: str,
        feature_distributions: dict[str, list[float]],
        sample_count: int,
    ) -> BaselineResponse:
        """Capture a new baseline snapshot."""
        baseline_id = str(uuid4())
        baseline = BaselineResponse(
            id=baseline_id,
            name=name,
            created_at=datetime.now(timezone.utc),
            feature_distributions=feature_distributions,
            sample_count=sample_count,
        )
        with self._lock:
            self._baselines[baseline_id] = baseline
        logger.info(f"Created baseline '{name}' (id={baseline_id}, samples={sample_count})")
        return baseline

    def list_baselines(self) -> list[BaselineResponse]:
        """Return all stored baselines."""
        return list(self._baselines.values())

    def get_baseline(self, baseline_id: str) -> BaselineResponse | None:
        """Return a single baseline by ID, or None if not found."""
        return self._baselines.get(baseline_id)

    # ------------------------------------------------------------------
    # Drift analysis
    # ------------------------------------------------------------------

    def analyze_drift(
        self,
        baseline_id: str,
        current_distributions: dict[str, list[float]],
        current_sample_count: int = 0,
    ) -> DriftAnalysis:
        """Run drift analysis comparing current distributions against a baseline.

        Raises:
            ValueError: If baseline_id is not found.
        """
        baseline = self._baselines.get(baseline_id)
        if baseline is None:
            raise ValueError(f"Baseline '{baseline_id}' not found")

        feature_drifts: list[FeatureDrift] = []

        # Analyse features present in both baseline and current
        all_features = set(baseline.feature_distributions.keys()) | set(
            current_distributions.keys()
        )

        for feature in sorted(all_features):
            base_dist = baseline.feature_distributions.get(feature, [])
            curr_dist = current_distributions.get(feature, [])

            if not base_dist and not curr_dist:
                continue

            psi = calculate_psi(base_dist, curr_dist)
            severity = classify_severity(psi)

            # Also run KS test when both distributions have data
            p_value: float | None = None
            test_used = "psi"

            if base_dist and curr_dist:
                # Use raw bin counts as pseudo-samples for KS
                _, p_val = calculate_ks_statistic(base_dist, curr_dist)
                p_value = p_val
                test_used = "psi+ks"

            feature_drifts.append(
                FeatureDrift(
                    feature=feature,
                    psi=round(psi, 6),
                    severity=severity,
                    p_value=round(p_value, 6) if p_value is not None else None,
                    test_used=test_used,
                )
            )

        # Overall drift score = mean PSI across features
        if feature_drifts:
            overall_score = sum(fd.psi for fd in feature_drifts) / len(feature_drifts)
        else:
            overall_score = 0.0

        overall_severity = classify_severity(overall_score)
        recommendation = _recommend(overall_severity)

        analysis = DriftAnalysis(
            baseline_id=baseline_id,
            baseline_name=baseline.name,
            overall_drift_score=round(overall_score, 6),
            overall_severity=overall_severity,
            feature_drifts=feature_drifts,
            recommendation=recommendation,
        )

        # Record in history
        with self._lock:
            self._drift_history.append(
                DriftHistoryEntry(
                    timestamp=analysis.analyzed_at,
                    drift_score=round(overall_score, 6),
                    severity=overall_severity,
                )
            )

        return analysis

    # ------------------------------------------------------------------
    # Feature drift helpers
    # ------------------------------------------------------------------

    def compute_feature_psi(
        self, baseline_dist: list[float], current_dist: list[float]
    ) -> FeatureDrift:
        """Compute PSI drift for a single feature."""
        psi = calculate_psi(baseline_dist, current_dist)
        severity = classify_severity(psi)
        return FeatureDrift(
            feature="unknown",
            psi=round(psi, 6),
            severity=severity,
        )

    def identify_top_drifting_features(
        self,
        baseline_distributions: dict[str, list[float]],
        current_distributions: dict[str, list[float]],
        top_n: int = 5,
    ) -> list[FeatureDrift]:
        """Identify the top-N most drifting features by PSI."""
        drifts: list[FeatureDrift] = []
        all_features = set(baseline_distributions.keys()) & set(
            current_distributions.keys()
        )
        for feature in all_features:
            psi = calculate_psi(
                baseline_distributions[feature], current_distributions[feature]
            )
            severity = classify_severity(psi)
            drifts.append(
                FeatureDrift(
                    feature=feature,
                    psi=round(psi, 6),
                    severity=severity,
                )
            )
        drifts.sort(key=lambda d: d.psi, reverse=True)
        return drifts[:top_n]

    # ------------------------------------------------------------------
    # Model drift detection
    # ------------------------------------------------------------------

    def record_model_outcome(
        self,
        predicted: bool,
        actual: bool,
        timestamp: datetime | None = None,
    ) -> None:
        """Record a predicted vs actual screening outcome."""
        ts = timestamp or datetime.now(timezone.utc)
        with self._lock:
            self._model_outcomes.append((ts, predicted, actual))

    def get_model_accuracy(
        self, window_days: int | None = None
    ) -> float:
        """Calculate model accuracy, optionally within a rolling window.

        Returns accuracy as a float between 0 and 1.
        Returns 0.0 if no outcomes have been recorded.
        """
        outcomes = self._model_outcomes
        if window_days is not None:
            now = datetime.now(timezone.utc)
            cutoff_seconds = window_days * 86400
            outcomes = [
                (ts, pred, act)
                for ts, pred, act in outcomes
                if (now - ts).total_seconds() <= cutoff_seconds
            ]

        if not outcomes:
            return 0.0

        correct = sum(1 for _, pred, act in outcomes if pred == act)
        return correct / len(outcomes)

    def check_model_drift(
        self, accuracy_threshold: float = 0.8
    ) -> dict[str, Any]:
        """Check whether model accuracy has dropped below threshold.

        Returns a dict with accuracy windows and alert status.
        """
        acc_7d = self.get_model_accuracy(window_days=7)
        acc_30d = self.get_model_accuracy(window_days=30)
        acc_all = self.get_model_accuracy()

        alert = acc_7d < accuracy_threshold if self._model_outcomes else False

        return {
            "accuracy_7d": round(acc_7d, 4),
            "accuracy_30d": round(acc_30d, 4),
            "accuracy_all": round(acc_all, 4),
            "threshold": accuracy_threshold,
            "alert": alert,
            "total_outcomes": len(self._model_outcomes),
        }

    # ------------------------------------------------------------------
    # Monitor management
    # ------------------------------------------------------------------

    def list_monitors(self) -> list[MonitorStatus]:
        """Return status of all monitors."""
        result: list[MonitorStatus] = []
        for m in self._monitors.values():
            last_val = m.data_points[-1][1] if m.data_points else None
            result.append(
                MonitorStatus(
                    name=m.name,
                    monitor_type=m.monitor_type,
                    description=m.description,
                    is_active=m.is_active,
                    last_value=last_val,
                    data_points=len(m.data_points),
                    created_at=m.created_at,
                )
            )
        return result

    def get_monitor(self, name: str) -> MonitorStatus | None:
        """Return a single monitor status or None."""
        m = self._monitors.get(name)
        if m is None:
            return None
        last_val = m.data_points[-1][1] if m.data_points else None
        return MonitorStatus(
            name=m.name,
            monitor_type=m.monitor_type,
            description=m.description,
            is_active=m.is_active,
            last_value=last_val,
            data_points=len(m.data_points),
            created_at=m.created_at,
        )

    def record_data_point(
        self,
        monitor_name: str,
        value: float,
        metadata: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> DataPointResponse:
        """Record a new data point for a monitor.

        If the monitor doesn't exist, it is auto-created as a continuous monitor.
        """
        ts = timestamp or datetime.now(timezone.utc)
        with self._lock:
            if monitor_name not in self._monitors:
                self._monitors[monitor_name] = _MonitorData(
                    monitor_name, MonitorType.CONTINUOUS
                )
            m = self._monitors[monitor_name]
            m.data_points.append((ts, value, metadata or {}))

        return DataPointResponse(
            monitor_name=monitor_name,
            value=value,
            timestamp=ts,
            total_points=len(m.data_points),
        )

    def get_monitor_values(self, monitor_name: str) -> list[float]:
        """Return all recorded values for a monitor."""
        m = self._monitors.get(monitor_name)
        if m is None:
            return []
        return [v for _, v, _ in m.data_points]

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def generate_report(
        self,
        baseline_id: str | None = None,
        current_distributions: dict[str, list[float]] | None = None,
    ) -> DriftReport:
        """Generate an aggregated drift report.

        If baseline_id and current_distributions are provided, runs a fresh
        analysis. Otherwise, synthesises a report from existing monitor data.
        """
        feature_drifts: list[FeatureDrift] = []
        overall_score = 0.0
        model_acc_current: float | None = None
        model_acc_baseline: float | None = None

        if baseline_id and current_distributions:
            analysis = self.analyze_drift(baseline_id, current_distributions)
            feature_drifts = analysis.feature_drifts
            overall_score = analysis.overall_drift_score
        elif self._drift_history:
            # Use latest drift analysis
            latest = self._drift_history[-1]
            overall_score = latest.drift_score

        # Model accuracy if we have outcomes
        if self._model_outcomes:
            model_acc_current = self.get_model_accuracy(window_days=7)
            model_acc_baseline = self.get_model_accuracy()

        overall_severity = classify_severity(overall_score)
        recommendation = _recommend(overall_severity)

        top_features = sorted(feature_drifts, key=lambda d: d.psi, reverse=True)
        top_names = [fd.feature for fd in top_features[:5]]

        # Build summary
        summary_parts = [f"Overall drift score: {overall_score:.4f} ({overall_severity.value})."]
        if top_names:
            summary_parts.append(f"Top drifting features: {', '.join(top_names)}.")
        summary_parts.append(f"Recommendation: {recommendation.value}.")

        report = DriftReport(
            report_id=str(uuid4()),
            generated_at=datetime.now(timezone.utc),
            overall_drift_score=round(overall_score, 6),
            overall_severity=overall_severity,
            recommendation=recommendation,
            feature_drifts=feature_drifts,
            model_accuracy_current=model_acc_current,
            model_accuracy_baseline=model_acc_baseline,
            top_drifting_features=top_names,
            summary=" ".join(summary_parts),
        )

        with self._lock:
            self._latest_report = report

        return report

    def get_latest_report(self) -> DriftReport | None:
        """Return the most recently generated report."""
        return self._latest_report

    # ------------------------------------------------------------------
    # Drift history
    # ------------------------------------------------------------------

    def get_drift_history(
        self, limit: int = 100
    ) -> DriftHistory:
        """Return drift score history entries."""
        entries = self._drift_history[-limit:] if self._drift_history else []
        return DriftHistory(
            entries=entries,
            total=len(entries),
        )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return service statistics."""
        return {
            "baselines": len(self._baselines),
            "monitors": len(self._monitors),
            "drift_history_entries": len(self._drift_history),
            "model_outcomes": len(self._model_outcomes),
            "has_latest_report": self._latest_report is not None,
        }


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------

_service: DriftDetectionService | None = None
_service_lock = threading.Lock()


def get_drift_detection_service() -> DriftDetectionService:
    """Return the singleton DriftDetectionService instance."""
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = DriftDetectionService()
    return _service


def reset_drift_detection_service() -> None:
    """Reset the singleton (useful for test isolation)."""
    global _service
    with _service_lock:
        _service = None
