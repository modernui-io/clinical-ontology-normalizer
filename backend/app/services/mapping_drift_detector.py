"""Mapping Drift Detector Service.

P2-010: Detects drift in terminology mapping distributions over time
using chi-squared statistical testing to compare current vs baseline
concept frequency distributions.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# Configurable thresholds (can be overridden via env/config)
DRIFT_WARNING_THRESHOLD: float = 0.1
DRIFT_CRITICAL_THRESHOLD: float = 0.3


class DriftSeverity(str, Enum):
    """Severity classification for mapping drift."""

    NONE = "none"
    MINOR = "minor"
    SIGNIFICANT = "significant"
    CRITICAL = "critical"


@dataclass
class MappingDistribution:
    """A single concept's count and percentage within a distribution."""

    concept_id: int
    count: int
    percentage: float
    period: str


@dataclass
class DriftResult:
    """Result of a drift detection analysis."""

    drifted: bool
    drift_score: float
    affected_concepts: list[int] = field(default_factory=list)
    severity: DriftSeverity = DriftSeverity.NONE


def _kl_divergence(p: list[float], q: list[float]) -> float:
    """Compute KL divergence D(P || Q) with smoothing.

    Applies additive (Laplace) smoothing to avoid division by zero
    and log(0) when either distribution has zero-probability bins.

    Args:
        p: Current distribution probabilities.
        q: Baseline distribution probabilities.

    Returns:
        KL divergence score (non-negative float).
    """
    epsilon = 1e-10
    total = 0.0
    for pi, qi in zip(p, q):
        pi_s = pi + epsilon
        qi_s = qi + epsilon
        total += pi_s * math.log(pi_s / qi_s)
    return max(total, 0.0)


def _chi_squared(observed: list[float], expected: list[float]) -> float:
    """Compute chi-squared statistic for two distributions.

    Args:
        observed: Observed frequency proportions.
        expected: Expected (baseline) frequency proportions.

    Returns:
        Chi-squared statistic (non-negative float).
    """
    epsilon = 1e-10
    total = 0.0
    for o, e in zip(observed, expected):
        e_s = e + epsilon
        total += (o - e_s) ** 2 / e_s
    return max(total, 0.0)


def _classify_severity(
    drift_score: float,
    warning_threshold: float = DRIFT_WARNING_THRESHOLD,
    critical_threshold: float = DRIFT_CRITICAL_THRESHOLD,
) -> DriftSeverity:
    """Classify drift severity based on score thresholds.

    Args:
        drift_score: Computed drift score.
        warning_threshold: Threshold above which drift is minor.
        critical_threshold: Threshold above which drift is critical.

    Returns:
        DriftSeverity classification.
    """
    if drift_score >= critical_threshold:
        return DriftSeverity.CRITICAL
    if drift_score >= warning_threshold:
        return DriftSeverity.SIGNIFICANT
    if drift_score > 0.01:
        return DriftSeverity.MINOR
    return DriftSeverity.NONE


def detect_drift(
    current_distribution: list[MappingDistribution],
    baseline_distribution: list[MappingDistribution],
    *,
    warning_threshold: float = DRIFT_WARNING_THRESHOLD,
    critical_threshold: float = DRIFT_CRITICAL_THRESHOLD,
    method: str = "chi_squared",
) -> DriftResult:
    """Detect drift between current and baseline mapping distributions.

    Aligns both distributions by concept_id, fills missing concepts with
    zero counts, and computes a divergence score using the specified method.

    Args:
        current_distribution: Current period concept distribution.
        baseline_distribution: Baseline period concept distribution.
        warning_threshold: Score threshold for significant drift.
        critical_threshold: Score threshold for critical drift.
        method: Statistical method - "chi_squared" or "kl_divergence".

    Returns:
        DriftResult with drift score, severity, and affected concepts.
    """
    if not baseline_distribution:
        logger.warning("Empty baseline distribution; cannot detect drift")
        return DriftResult(drifted=False, drift_score=0.0, severity=DriftSeverity.NONE)

    if not current_distribution:
        logger.warning("Empty current distribution; cannot detect drift")
        return DriftResult(drifted=False, drift_score=0.0, severity=DriftSeverity.NONE)

    # Build lookup maps keyed by concept_id
    all_concept_ids = sorted(
        {d.concept_id for d in current_distribution}
        | {d.concept_id for d in baseline_distribution}
    )

    current_map = {d.concept_id: d.percentage for d in current_distribution}
    baseline_map = {d.concept_id: d.percentage for d in baseline_distribution}

    current_vec: list[float] = []
    baseline_vec: list[float] = []
    affected: list[int] = []

    for cid in all_concept_ids:
        c_pct = current_map.get(cid, 0.0)
        b_pct = baseline_map.get(cid, 0.0)
        current_vec.append(c_pct)
        baseline_vec.append(b_pct)

        # A concept is "affected" if its share changed by more than 5pp
        if abs(c_pct - b_pct) > 5.0:
            affected.append(cid)

    # Normalise to probability vectors (sum to 1)
    c_total = sum(current_vec) or 1.0
    b_total = sum(baseline_vec) or 1.0
    c_prob = [v / c_total for v in current_vec]
    b_prob = [v / b_total for v in baseline_vec]

    if method == "kl_divergence":
        drift_score = _kl_divergence(c_prob, b_prob)
    else:
        drift_score = _chi_squared(c_prob, b_prob)

    severity = _classify_severity(drift_score, warning_threshold, critical_threshold)
    drifted = severity not in (DriftSeverity.NONE, DriftSeverity.MINOR)

    logger.info(
        "Drift detection complete: score=%.4f severity=%s affected=%d concepts method=%s",
        drift_score,
        severity.value,
        len(affected),
        method,
    )

    return DriftResult(
        drifted=drifted,
        drift_score=round(drift_score, 6),
        affected_concepts=affected,
        severity=severity,
    )
