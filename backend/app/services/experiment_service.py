"""A/B Testing / Experiment Service (VP-DS-3).

Manages the full lifecycle of A/B experiments for clinical trial patient
recruitment, including deterministic variant assignment, outcome tracking,
and statistical analysis with sequential testing support.

Usage:
    from app.services.experiment_service import get_experiment_service

    svc = get_experiment_service()
    exp = svc.create_experiment(ExperimentCreate(...))
    svc.start_experiment(exp.id)
    assignment = svc.assign_variant(exp.id, "patient-123")
    svc.record_outcome(exp.id, OutcomeRecord(...))
    results = svc.get_results(exp.id)
"""

from __future__ import annotations

import hashlib
import logging
import math
import threading
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.schemas.experiment import (
    AssignmentResponse,
    ExperimentCreate,
    ExperimentResponse,
    ExperimentResults,
    ExperimentStatus,
    ExperimentTemplate,
    MetricType,
    OutcomeRecord,
    PowerAnalysis,
    SequentialTestResult,
    StatisticalResult,
    TemplateListResponse,
    VariantDefinition,
    VariantStats,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Math helpers (no external dependencies)
# ---------------------------------------------------------------------------


def _erf(x: float) -> float:
    """Approximate the error function using Abramowitz & Stegun formula 7.1.26.

    Maximum error: 1.5e-7.
    """
    sign = 1 if x >= 0 else -1
    x = abs(x)
    t = 1.0 / (1.0 + 0.3275911 * x)
    y = 1.0 - (
        ((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t
        + 0.254829592
    ) * t * math.exp(-x * x)
    return sign * y


def _norm_cdf(x: float) -> float:
    """Standard normal CDF."""
    return 0.5 * (1.0 + _erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """Inverse of the standard normal CDF (percent-point function).

    Uses the rational approximation by Peter Acklam.
    Accurate to about 1.15e-9 in the central region.
    """
    if p <= 0:
        return -math.inf
    if p >= 1:
        return math.inf

    # Coefficients
    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    ]

    p_low = 0.02425
    p_high = 1.0 - p_low

    if p < p_low:
        # Lower tail
        q = math.sqrt(-2.0 * math.log(p))
        return (
            ((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]
        ) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    elif p <= p_high:
        # Central region
        q = p - 0.5
        r = q * q
        return (
            (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
        ) / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    else:
        # Upper tail
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        )


def _two_sample_t_test(
    n1: int,
    mean1: float,
    std1: float,
    n2: int,
    mean2: float,
    std2: float,
) -> tuple[float, float]:
    """Welch's two-sample t-test.

    Returns (t_statistic, p_value).
    """
    if n1 < 2 or n2 < 2:
        return 0.0, 1.0

    se1 = (std1 ** 2) / n1
    se2 = (std2 ** 2) / n2
    se = math.sqrt(se1 + se2)

    if se < 1e-15:
        return 0.0, 1.0

    t_stat = (mean1 - mean2) / se

    # Welch-Satterthwaite degrees of freedom
    num = (se1 + se2) ** 2
    denom = (se1 ** 2) / (n1 - 1) + (se2 ** 2) / (n2 - 1)
    if denom < 1e-15:
        df = n1 + n2 - 2
    else:
        df = num / denom

    # Approximate p-value using normal distribution for large df
    # For smaller df, use a t-distribution approximation
    if df > 30:
        p_value = 2.0 * (1.0 - _norm_cdf(abs(t_stat)))
    else:
        # Use the approximation: t-distribution -> normal for df > 30
        # For smaller df, use a correction factor
        x = abs(t_stat)
        g1 = df / (df + x * x)
        # Regularized incomplete beta approximation
        p_value = _t_distribution_p_value(x, df)

    return t_stat, p_value


def _t_distribution_p_value(t_abs: float, df: float) -> float:
    """Approximate two-tailed p-value for t-distribution.

    Uses a series expansion for the regularized incomplete beta function.
    """
    if df <= 0:
        return 1.0

    x = df / (df + t_abs * t_abs)

    # Use a simple but effective approximation
    # For large df, converges to normal
    if df > 100:
        return 2.0 * (1.0 - _norm_cdf(t_abs))

    # Cornish-Fisher expansion for moderate df
    g1 = 0.0
    g2 = 0.0
    z = t_abs

    # Adjustment for t -> z conversion
    a = df - 0.5
    b = 48.0 * a * a
    z2 = z * z

    # Wilson-Hilferty approximation
    y = z2 / df
    if y > 0:
        correction = (
            1.0
            + (4.0 * y - 3.0) / (20.0 * df)
            - (25.0 * y * y - 56.0 * y + 21.0) / (840.0 * df * df)
        )
        z_approx = z * math.sqrt(correction) if correction > 0 else z
    else:
        z_approx = z

    p_value = 2.0 * (1.0 - _norm_cdf(abs(z_approx)))
    return max(0.0, min(1.0, p_value))


def _two_proportion_z_test(
    n1: int,
    p1: float,
    n2: int,
    p2: float,
) -> tuple[float, float]:
    """Two-proportion z-test.

    Returns (z_statistic, p_value).
    """
    if n1 < 1 or n2 < 1:
        return 0.0, 1.0

    # Pooled proportion
    p_pool = (p1 * n1 + p2 * n2) / (n1 + n2)

    if p_pool <= 0.0 or p_pool >= 1.0:
        return 0.0, 1.0

    se = math.sqrt(p_pool * (1.0 - p_pool) * (1.0 / n1 + 1.0 / n2))

    if se < 1e-15:
        return 0.0, 1.0

    z_stat = (p1 - p2) / se
    p_value = 2.0 * (1.0 - _norm_cdf(abs(z_stat)))

    return z_stat, p_value


def _cohens_d(mean1: float, std1: float, mean2: float, std2: float) -> float:
    """Cohen's d effect size for two groups."""
    pooled_std = math.sqrt((std1 ** 2 + std2 ** 2) / 2.0)
    if pooled_std < 1e-15:
        return 0.0
    return (mean1 - mean2) / pooled_std


def _cohens_h(p1: float, p2: float) -> float:
    """Cohen's h effect size for two proportions."""
    return 2.0 * (math.asin(math.sqrt(p1)) - math.asin(math.sqrt(p2)))


def _interpret_effect_size(d: float) -> str:
    """Interpret effect size magnitude."""
    d_abs = abs(d)
    if d_abs < 0.2:
        return "negligible"
    elif d_abs < 0.5:
        return "small"
    elif d_abs < 0.8:
        return "medium"
    else:
        return "large"


def _obrien_fleming_boundary(information_fraction: float, alpha: float = 0.05) -> float:
    """O'Brien-Fleming spending function.

    The O'Brien-Fleming spending function is:
        alpha*(t) = 2 - 2 * Phi(z_{alpha/2} / sqrt(t))

    where t is the information fraction and z_{alpha/2} is the critical value.
    """
    if information_fraction <= 0.0:
        return 0.0
    if information_fraction >= 1.0:
        return alpha

    z_alpha_half = _norm_ppf(1.0 - alpha / 2.0)
    boundary = 2.0 * (1.0 - _norm_cdf(z_alpha_half / math.sqrt(information_fraction)))

    return max(0.0, min(alpha, boundary))


def _estimate_power(
    n: int,
    effect_size: float,
    alpha: float = 0.05,
) -> float:
    """Estimate statistical power for a two-sample test.

    Parameters
    ----------
    n : int
        Sample size per group.
    effect_size : float
        Expected Cohen's d effect size.
    alpha : float
        Significance level.

    Returns
    -------
    float
        Estimated power (0 to 1).
    """
    if n < 2 or abs(effect_size) < 1e-15:
        return 0.0

    z_alpha = _norm_ppf(1.0 - alpha / 2.0)
    noncentrality = abs(effect_size) * math.sqrt(n / 2.0)
    power = 1.0 - _norm_cdf(z_alpha - noncentrality)

    return max(0.0, min(1.0, power))


def _samples_for_power(
    effect_size: float,
    power: float = 0.80,
    alpha: float = 0.05,
) -> int:
    """Calculate samples per variant needed for desired power.

    Uses the formula: n = 2 * ((z_alpha + z_beta) / d)^2
    """
    if abs(effect_size) < 1e-15:
        return 999999  # Very large number if no effect

    z_alpha = _norm_ppf(1.0 - alpha / 2.0)
    z_beta = _norm_ppf(power)

    n = 2.0 * ((z_alpha + z_beta) / effect_size) ** 2
    return max(2, math.ceil(n))


def _minimum_detectable_effect(
    n: int,
    power: float = 0.80,
    alpha: float = 0.05,
) -> float:
    """Calculate minimum detectable effect size given sample size."""
    if n < 2:
        return float("inf")

    z_alpha = _norm_ppf(1.0 - alpha / 2.0)
    z_beta = _norm_ppf(power)

    mde = (z_alpha + z_beta) * math.sqrt(2.0 / n)
    return mde


# ---------------------------------------------------------------------------
# Experiment Templates
# ---------------------------------------------------------------------------

EXPERIMENT_TEMPLATES: dict[str, ExperimentTemplate] = {
    "screening_algorithm_comparison": ExperimentTemplate(
        template_id="screening_algorithm_comparison",
        name="Screening Algorithm Comparison",
        description=(
            "Compare two screening algorithms to determine which "
            "yields higher pass rates while maintaining quality."
        ),
        hypothesis=(
            "The new screening algorithm will increase the screening pass "
            "rate by at least 10% compared to the current algorithm."
        ),
        metric="screening_pass_rate",
        metric_type=MetricType.BINARY,
        default_variants=[
            VariantDefinition(name="control", weight=50),
            VariantDefinition(name="treatment", weight=50),
        ],
        target_sample_size=200,
    ),
    "nlp_pipeline_comparison": ExperimentTemplate(
        template_id="nlp_pipeline_comparison",
        name="NLP Pipeline Comparison",
        description=(
            "Compare NLP extraction approaches to determine which "
            "produces more accurate clinical entity extraction."
        ),
        hypothesis=(
            "The transformer-based NLP pipeline will achieve higher "
            "extraction accuracy than the rule-based pipeline."
        ),
        metric="extraction_accuracy",
        metric_type=MetricType.CONTINUOUS,
        default_variants=[
            VariantDefinition(name="rule_based", weight=50),
            VariantDefinition(name="transformer", weight=50),
        ],
        target_sample_size=150,
    ),
    "match_score_threshold": ExperimentTemplate(
        template_id="match_score_threshold",
        name="Match Score Threshold Test",
        description=(
            "Test different match score cutoffs to find the optimal "
            "balance between sensitivity and specificity."
        ),
        hypothesis=(
            "Lowering the match score threshold from 0.8 to 0.7 will "
            "increase eligible patient yield without significantly "
            "increasing false positives."
        ),
        metric="match_score",
        metric_type=MetricType.CONTINUOUS,
        default_variants=[
            VariantDefinition(name="threshold_80", weight=50),
            VariantDefinition(name="threshold_70", weight=50),
        ],
        target_sample_size=100,
    ),
    "criteria_weighting": ExperimentTemplate(
        template_id="criteria_weighting",
        name="Criteria Weighting Test",
        description=(
            "Test different importance weights for eligibility criteria "
            "to optimize patient-trial matching."
        ),
        hypothesis=(
            "Using data-driven criteria weights will produce better "
            "match scores than uniform weighting."
        ),
        metric="time_to_eligible",
        metric_type=MetricType.CONTINUOUS,
        default_variants=[
            VariantDefinition(name="uniform_weights", weight=33.34),
            VariantDefinition(name="clinical_weights", weight=33.33),
            VariantDefinition(name="data_driven_weights", weight=33.33),
        ],
        target_sample_size=120,
    ),
}


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------


class _ExperimentData:
    """Internal mutable experiment state."""

    __slots__ = (
        "id",
        "name",
        "description",
        "hypothesis",
        "status",
        "variants",
        "metric",
        "metric_type",
        "target_sample_size",
        "start_date",
        "end_date",
        "created_at",
        "updated_at",
        "assignments",
        "outcomes",
    )

    def __init__(
        self,
        *,
        id: str,
        name: str,
        description: str | None,
        hypothesis: str | None,
        variants: list[VariantDefinition],
        metric: str,
        metric_type: MetricType,
        target_sample_size: int,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> None:
        self.id = id
        self.name = name
        self.description = description
        self.hypothesis = hypothesis
        self.status = ExperimentStatus.DRAFT
        self.variants = variants
        self.metric = metric
        self.metric_type = metric_type
        self.target_sample_size = target_sample_size
        self.start_date = start_date
        self.end_date = end_date
        now = datetime.now(timezone.utc)
        self.created_at = now
        self.updated_at = now
        # patient_id -> variant_name
        self.assignments: dict[str, str] = {}
        # variant_name -> list of values
        self.outcomes: dict[str, list[float]] = {v.name: [] for v in variants}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ExperimentService:
    """In-memory A/B experiment management service.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    # Valid state transitions
    VALID_TRANSITIONS: dict[ExperimentStatus, set[ExperimentStatus]] = {
        ExperimentStatus.DRAFT: {ExperimentStatus.RUNNING, ExperimentStatus.ARCHIVED},
        ExperimentStatus.RUNNING: {ExperimentStatus.PAUSED, ExperimentStatus.COMPLETED},
        ExperimentStatus.PAUSED: {ExperimentStatus.RUNNING, ExperimentStatus.COMPLETED, ExperimentStatus.ARCHIVED},
        ExperimentStatus.COMPLETED: {ExperimentStatus.ARCHIVED},
        ExperimentStatus.ARCHIVED: set(),
    }

    def __init__(self) -> None:
        self._experiments: dict[str, _ExperimentData] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _to_response(self, exp: _ExperimentData) -> ExperimentResponse:
        total_outcomes = sum(len(v) for v in exp.outcomes.values())
        return ExperimentResponse(
            id=exp.id,
            name=exp.name,
            description=exp.description,
            hypothesis=exp.hypothesis,
            status=exp.status,
            variants=exp.variants,
            metric=exp.metric,
            metric_type=exp.metric_type,
            target_sample_size=exp.target_sample_size,
            start_date=exp.start_date,
            end_date=exp.end_date,
            created_at=exp.created_at,
            updated_at=exp.updated_at,
            total_assignments=len(exp.assignments),
            total_outcomes=total_outcomes,
        )

    def _get_experiment(self, experiment_id: str) -> _ExperimentData:
        exp = self._experiments.get(experiment_id)
        if exp is None:
            raise KeyError(f"Experiment '{experiment_id}' not found")
        return exp

    def _transition(self, exp: _ExperimentData, target: ExperimentStatus) -> None:
        allowed = self.VALID_TRANSITIONS.get(exp.status, set())
        if target not in allowed:
            raise ValueError(
                f"Invalid transition: {exp.status.value} -> {target.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )
        exp.status = target
        exp.updated_at = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_experiment(self, create: ExperimentCreate) -> ExperimentResponse:
        """Create a new experiment in DRAFT status."""
        # Validate weights sum to 100
        total_weight = sum(v.weight for v in create.variants)
        if abs(total_weight - 100.0) > 0.01:
            raise ValueError(
                f"Variant weights must sum to 100, got {total_weight}"
            )

        # Validate unique variant names
        names = [v.name for v in create.variants]
        if len(names) != len(set(names)):
            raise ValueError("Variant names must be unique")

        exp_id = str(uuid4())
        exp = _ExperimentData(
            id=exp_id,
            name=create.name,
            description=create.description,
            hypothesis=create.hypothesis,
            variants=create.variants,
            metric=create.metric,
            metric_type=create.metric_type,
            target_sample_size=create.target_sample_size,
            start_date=create.start_date,
            end_date=create.end_date,
        )

        with self._lock:
            self._experiments[exp_id] = exp

        logger.info("Created experiment %s: %s", exp_id, create.name)
        return self._to_response(exp)

    def get_experiment(self, experiment_id: str) -> ExperimentResponse:
        """Get experiment by ID."""
        with self._lock:
            exp = self._get_experiment(experiment_id)
            return self._to_response(exp)

    def list_experiments(
        self,
        status: ExperimentStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[ExperimentResponse], int]:
        """List experiments with optional status filter."""
        with self._lock:
            experiments = list(self._experiments.values())

        if status is not None:
            experiments = [e for e in experiments if e.status == status]

        total = len(experiments)
        # Sort by created_at descending
        experiments.sort(key=lambda e: e.created_at, reverse=True)
        page = experiments[offset : offset + limit]
        return [self._to_response(e) for e in page], total

    def delete_experiment(self, experiment_id: str) -> None:
        """Delete an experiment (only if DRAFT or ARCHIVED)."""
        with self._lock:
            exp = self._get_experiment(experiment_id)
            if exp.status not in (ExperimentStatus.DRAFT, ExperimentStatus.ARCHIVED):
                raise ValueError(
                    f"Cannot delete experiment in {exp.status.value} status. "
                    "Must be DRAFT or ARCHIVED."
                )
            del self._experiments[experiment_id]
        logger.info("Deleted experiment %s", experiment_id)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_experiment(self, experiment_id: str) -> ExperimentResponse:
        """Transition experiment to RUNNING."""
        with self._lock:
            exp = self._get_experiment(experiment_id)
            self._transition(exp, ExperimentStatus.RUNNING)
            if exp.start_date is None:
                exp.start_date = datetime.now(timezone.utc)
        return self._to_response(exp)

    def pause_experiment(self, experiment_id: str) -> ExperimentResponse:
        """Transition experiment to PAUSED."""
        with self._lock:
            exp = self._get_experiment(experiment_id)
            self._transition(exp, ExperimentStatus.PAUSED)
        return self._to_response(exp)

    def complete_experiment(self, experiment_id: str) -> ExperimentResponse:
        """Transition experiment to COMPLETED and lock results."""
        with self._lock:
            exp = self._get_experiment(experiment_id)
            self._transition(exp, ExperimentStatus.COMPLETED)
            if exp.end_date is None:
                exp.end_date = datetime.now(timezone.utc)
        return self._to_response(exp)

    def archive_experiment(self, experiment_id: str) -> ExperimentResponse:
        """Transition experiment to ARCHIVED."""
        with self._lock:
            exp = self._get_experiment(experiment_id)
            self._transition(exp, ExperimentStatus.ARCHIVED)
        return self._to_response(exp)

    # ------------------------------------------------------------------
    # Assignment
    # ------------------------------------------------------------------

    def assign_variant(
        self,
        experiment_id: str,
        patient_id: str,
    ) -> AssignmentResponse:
        """Deterministically assign a patient to a variant.

        Uses hash(experiment_id + patient_id) mod 100 to produce a bucket,
        then maps the bucket to a variant based on cumulative weights.
        The same patient always receives the same variant.
        """
        with self._lock:
            exp = self._get_experiment(experiment_id)
            if exp.status != ExperimentStatus.RUNNING:
                raise ValueError(
                    f"Cannot assign variants: experiment is {exp.status.value}, "
                    "must be RUNNING"
                )

            # Check if already assigned
            if patient_id in exp.assignments:
                variant_name = exp.assignments[patient_id]
                bucket = self._compute_bucket(experiment_id, patient_id)
                return AssignmentResponse(
                    experiment_id=experiment_id,
                    patient_id=patient_id,
                    variant=variant_name,
                    bucket=bucket,
                )

            bucket = self._compute_bucket(experiment_id, patient_id)
            variant_name = self._bucket_to_variant(exp.variants, bucket)

            exp.assignments[patient_id] = variant_name

        return AssignmentResponse(
            experiment_id=experiment_id,
            patient_id=patient_id,
            variant=variant_name,
            bucket=bucket,
        )

    @staticmethod
    def _compute_bucket(experiment_id: str, patient_id: str) -> int:
        """Deterministic hash bucket (0-99)."""
        raw = f"{experiment_id}:{patient_id}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return int(digest, 16) % 100

    @staticmethod
    def _bucket_to_variant(
        variants: list[VariantDefinition], bucket: int
    ) -> str:
        """Map a bucket (0-99) to a variant based on cumulative weights."""
        cumulative = 0.0
        for variant in variants:
            cumulative += variant.weight
            if bucket < cumulative:
                return variant.name
        # Fallback to last variant (should not happen with valid weights)
        return variants[-1].name

    # ------------------------------------------------------------------
    # Outcome recording
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        experiment_id: str,
        outcome: OutcomeRecord,
    ) -> dict[str, Any]:
        """Record an outcome event for an experiment."""
        with self._lock:
            exp = self._get_experiment(experiment_id)
            if exp.status not in (ExperimentStatus.RUNNING, ExperimentStatus.PAUSED):
                raise ValueError(
                    f"Cannot record outcomes: experiment is {exp.status.value}, "
                    "must be RUNNING or PAUSED"
                )

            if outcome.metric_name != exp.metric:
                raise ValueError(
                    f"Metric mismatch: expected '{exp.metric}', "
                    f"got '{outcome.metric_name}'"
                )

            # Patient must be assigned
            if outcome.patient_id not in exp.assignments:
                raise ValueError(
                    f"Patient '{outcome.patient_id}' is not assigned to this experiment"
                )

            variant_name = exp.assignments[outcome.patient_id]
            exp.outcomes[variant_name].append(outcome.value)

        return {
            "experiment_id": experiment_id,
            "patient_id": outcome.patient_id,
            "variant": variant_name,
            "metric_name": outcome.metric_name,
            "value": outcome.value,
            "recorded": True,
        }

    # ------------------------------------------------------------------
    # Statistical Analysis
    # ------------------------------------------------------------------

    def get_results(
        self,
        experiment_id: str,
        total_planned_looks: int = 5,
    ) -> ExperimentResults:
        """Compute full statistical results for an experiment."""
        with self._lock:
            exp = self._get_experiment(experiment_id)
            variant_stats = self._compute_variant_stats(exp)
            pairwise = self._compute_pairwise(exp, variant_stats)
            sequential = self._compute_sequential_test(
                exp, variant_stats, total_planned_looks
            )
            power = self._compute_power_analysis(exp, variant_stats)
            recommendation = self._generate_recommendation(
                exp, pairwise, sequential, power
            )

        return ExperimentResults(
            experiment_id=exp.id,
            experiment_name=exp.name,
            status=exp.status,
            variant_stats=variant_stats,
            pairwise_comparisons=pairwise,
            sequential_test=sequential,
            power_analysis=power,
            recommendation=recommendation,
        )

    def get_power_analysis(
        self,
        experiment_id: str,
        effect_size: float = 0.5,
    ) -> PowerAnalysis:
        """Compute power analysis for an experiment."""
        with self._lock:
            exp = self._get_experiment(experiment_id)
            variant_stats = self._compute_variant_stats(exp)
            return self._compute_power_analysis(
                exp, variant_stats, assumed_effect_size=effect_size
            )

    def _compute_variant_stats(self, exp: _ExperimentData) -> list[VariantStats]:
        """Compute per-variant statistics."""
        stats = []
        for variant in exp.variants:
            values = exp.outcomes.get(variant.name, [])
            n = len(values)
            if n == 0:
                stats.append(VariantStats(name=variant.name))
                continue

            mean = sum(values) / n
            if n > 1:
                variance = sum((x - mean) ** 2 for x in values) / (n - 1)
                std_dev = math.sqrt(variance)
            else:
                std_dev = 0.0

            stats.append(
                VariantStats(
                    name=variant.name,
                    count=n,
                    mean=mean,
                    std_dev=std_dev,
                    min_value=min(values),
                    max_value=max(values),
                )
            )
        return stats

    def _compute_pairwise(
        self,
        exp: _ExperimentData,
        variant_stats: list[VariantStats],
    ) -> list[StatisticalResult]:
        """Compute pairwise statistical comparisons."""
        results = []

        # Compare all pairs (for A/B this is just one comparison)
        for i in range(len(variant_stats)):
            for j in range(i + 1, len(variant_stats)):
                va = variant_stats[i]
                vb = variant_stats[j]

                if va.count < 2 or vb.count < 2:
                    # Not enough data
                    results.append(
                        StatisticalResult(
                            variant_a=va,
                            variant_b=vb,
                            test_type="insufficient_data",
                            test_statistic=0.0,
                            p_value=1.0,
                            significant=False,
                            effect_size=0.0,
                            effect_size_interpretation="negligible",
                            confidence_interval_lower=0.0,
                            confidence_interval_upper=0.0,
                        )
                    )
                    continue

                if exp.metric_type == MetricType.BINARY:
                    stat, p_val = _two_proportion_z_test(
                        va.count, va.mean, vb.count, vb.mean
                    )
                    effect = _cohens_h(va.mean, vb.mean)
                    test_type = "z-test"
                else:
                    stat, p_val = _two_sample_t_test(
                        va.count, va.mean, va.std_dev,
                        vb.count, vb.mean, vb.std_dev,
                    )
                    effect = _cohens_d(va.mean, va.std_dev, vb.mean, vb.std_dev)
                    test_type = "t-test"

                # Confidence interval for difference in means
                diff = va.mean - vb.mean
                if exp.metric_type == MetricType.BINARY:
                    se = math.sqrt(
                        (va.mean * (1 - va.mean) / va.count if va.count > 0 else 0)
                        + (vb.mean * (1 - vb.mean) / vb.count if vb.count > 0 else 0)
                    )
                else:
                    se = math.sqrt(
                        (va.std_dev ** 2 / va.count if va.count > 0 else 0)
                        + (vb.std_dev ** 2 / vb.count if vb.count > 0 else 0)
                    )

                z_95 = _norm_ppf(0.975)
                ci_lower = diff - z_95 * se
                ci_upper = diff + z_95 * se

                results.append(
                    StatisticalResult(
                        variant_a=va,
                        variant_b=vb,
                        test_type=test_type,
                        test_statistic=stat,
                        p_value=p_val,
                        significant=p_val < 0.05,
                        effect_size=effect,
                        effect_size_interpretation=_interpret_effect_size(effect),
                        confidence_interval_lower=ci_lower,
                        confidence_interval_upper=ci_upper,
                    )
                )

        return results

    def _compute_sequential_test(
        self,
        exp: _ExperimentData,
        variant_stats: list[VariantStats],
        total_planned_looks: int,
    ) -> SequentialTestResult | None:
        """Compute sequential testing with O'Brien-Fleming boundary."""
        if len(variant_stats) < 2:
            return None

        va = variant_stats[0]
        vb = variant_stats[1]

        min_count = min(va.count, vb.count)
        if min_count < 2:
            return None

        # Information fraction: proportion of target sample collected
        info_fraction = min(1.0, min_count / exp.target_sample_size)

        # Determine which look this is
        current_look = max(1, min(
            total_planned_looks,
            int(info_fraction * total_planned_looks) + (1 if info_fraction > 0 else 0),
        ))

        # Compute adjusted alpha using O'Brien-Fleming spending function
        adjusted_alpha = _obrien_fleming_boundary(info_fraction, alpha=0.05)

        # Get observed p-value
        if exp.metric_type == MetricType.BINARY:
            _, p_val = _two_proportion_z_test(va.count, va.mean, vb.count, vb.mean)
        else:
            _, p_val = _two_sample_t_test(
                va.count, va.mean, va.std_dev,
                vb.count, vb.mean, vb.std_dev,
            )

        can_stop = p_val < adjusted_alpha and adjusted_alpha > 0

        return SequentialTestResult(
            current_look=current_look,
            total_planned_looks=total_planned_looks,
            nominal_alpha=0.05,
            adjusted_alpha=adjusted_alpha,
            observed_p_value=p_val,
            can_stop_early=can_stop,
            cumulative_information_fraction=info_fraction,
        )

    def _compute_power_analysis(
        self,
        exp: _ExperimentData,
        variant_stats: list[VariantStats],
        assumed_effect_size: float = 0.5,
    ) -> PowerAnalysis:
        """Compute power analysis."""
        min_count = 0
        if variant_stats:
            counts = [vs.count for vs in variant_stats if vs.count > 0]
            min_count = min(counts) if counts else 0

        # Compute observed effect size if we have data
        observed_effect = assumed_effect_size
        if len(variant_stats) >= 2 and variant_stats[0].count >= 2 and variant_stats[1].count >= 2:
            va, vb = variant_stats[0], variant_stats[1]
            if exp.metric_type == MetricType.BINARY:
                observed_effect = abs(_cohens_h(va.mean, vb.mean))
            else:
                observed_effect = abs(_cohens_d(va.mean, va.std_dev, vb.mean, vb.std_dev))

            # Use observed effect if it is meaningful, otherwise fall back
            if observed_effect < 1e-10:
                observed_effect = assumed_effect_size

        power = _estimate_power(min_count, observed_effect)
        mde = _minimum_detectable_effect(min_count) if min_count >= 2 else 99.0
        needed = _samples_for_power(observed_effect)

        # Cap MDE to a JSON-serializable value
        if not math.isfinite(mde):
            mde = 99.0

        return PowerAnalysis(
            current_sample_per_variant=min_count,
            target_sample_per_variant=exp.target_sample_size,
            estimated_power=round(power, 4),
            is_adequately_powered=power >= 0.80,
            minimum_detectable_effect=round(mde, 4),
            samples_needed_for_80_power=needed,
        )

    def _generate_recommendation(
        self,
        exp: _ExperimentData,
        pairwise: list[StatisticalResult],
        sequential: SequentialTestResult | None,
        power: PowerAnalysis | None,
    ) -> str:
        """Generate a human-readable recommendation."""
        if not pairwise:
            return "Insufficient data to make a recommendation. Continue collecting observations."

        total_outcomes = sum(len(v) for v in exp.outcomes.values())
        if total_outcomes < 10:
            return (
                f"Only {total_outcomes} observations recorded. "
                "Need more data before drawing conclusions."
            )

        # Check sequential test first
        if sequential and sequential.can_stop_early:
            sig = [p for p in pairwise if p.significant]
            if sig:
                winner = sig[0]
                better = (
                    winner.variant_a.name
                    if winner.variant_a.mean > winner.variant_b.mean
                    else winner.variant_b.name
                )
                return (
                    f"Sequential test indicates early stopping is justified. "
                    f"Variant '{better}' shows a statistically significant "
                    f"improvement (p={winner.p_value:.4f}, "
                    f"effect size={abs(winner.effect_size):.3f} "
                    f"[{winner.effect_size_interpretation}])."
                )

        # Check power
        if power and not power.is_adequately_powered:
            return (
                f"The experiment is underpowered (power={power.estimated_power:.2f}). "
                f"Need at least {power.samples_needed_for_80_power} samples per "
                f"variant for 80% power. Currently have "
                f"{power.current_sample_per_variant} per variant."
            )

        # Check significance
        sig_results = [p for p in pairwise if p.significant]
        if sig_results:
            r = sig_results[0]
            better = (
                r.variant_a.name
                if r.variant_a.mean > r.variant_b.mean
                else r.variant_b.name
            )
            return (
                f"Variant '{better}' is significantly better "
                f"(p={r.p_value:.4f}, effect size={abs(r.effect_size):.3f} "
                f"[{r.effect_size_interpretation}]). "
                f"Consider adopting this variant."
            )

        return (
            "No statistically significant difference detected between variants. "
            "Continue collecting data or consider concluding with no winner."
        )

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------

    def get_templates(self) -> TemplateListResponse:
        """Return all pre-defined experiment templates."""
        return TemplateListResponse(
            templates=list(EXPERIMENT_TEMPLATES.values())
        )

    def create_from_template(
        self,
        template_id: str,
        name: str | None = None,
    ) -> ExperimentResponse:
        """Create an experiment from a template."""
        template = EXPERIMENT_TEMPLATES.get(template_id)
        if template is None:
            raise KeyError(
                f"Template '{template_id}' not found. "
                f"Available: {list(EXPERIMENT_TEMPLATES.keys())}"
            )

        create = ExperimentCreate(
            name=name or template.name,
            description=template.description,
            hypothesis=template.hypothesis,
            variants=template.default_variants,
            metric=template.metric,
            metric_type=template.metric_type,
            target_sample_size=template.target_sample_size,
        )
        return self.create_experiment(create)

    # ------------------------------------------------------------------
    # Admin
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all experiments (for testing)."""
        with self._lock:
            self._experiments.clear()

    def get_stats(self) -> dict[str, Any]:
        """Service statistics."""
        with self._lock:
            by_status: dict[str, int] = {}
            for exp in self._experiments.values():
                by_status[exp.status.value] = by_status.get(exp.status.value, 0) + 1
            return {
                "total_experiments": len(self._experiments),
                "by_status": by_status,
                "templates_available": len(EXPERIMENT_TEMPLATES),
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_service: ExperimentService | None = None
_service_lock = threading.Lock()


def get_experiment_service() -> ExperimentService:
    """Get or create the singleton ExperimentService."""
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = ExperimentService()
    return _service
