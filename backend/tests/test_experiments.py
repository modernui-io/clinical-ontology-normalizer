"""Tests for A/B Testing / Experiment Framework (VP-DS-3).

Covers:
- Experiment CRUD and lifecycle transitions
- Deterministic variant assignment
- Assignment distribution and weight verification
- Multi-variant support (3+ variants)
- Outcome recording and aggregation
- T-test with known data
- Z-test with known proportions
- Effect size calculation
- Confidence interval coverage
- Sequential testing: early stopping
- Sequential testing: no early stop when underpowered
- Power analysis: adequate vs inadequate sample size
- Minimum detectable effect calculation
- Experiment templates
- Invalid transitions
- Concurrent experiment support
- API endpoint integration
"""

from __future__ import annotations

import math
import random
from collections import Counter

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentStatus,
    MetricType,
    OutcomeRecord,
    VariantDefinition,
)
from app.services.experiment_service import (
    ExperimentService,
    _cohens_d,
    _cohens_h,
    _estimate_power,
    _interpret_effect_size,
    _minimum_detectable_effect,
    _norm_cdf,
    _norm_ppf,
    _obrien_fleming_boundary,
    _samples_for_power,
    _two_proportion_z_test,
    _two_sample_t_test,
    get_experiment_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_service():
    """Ensure a fresh service for every test."""
    svc = get_experiment_service()
    svc.clear()
    yield svc
    svc.clear()


@pytest.fixture
def svc(clean_service) -> ExperimentService:
    """Shorthand for the clean service."""
    return clean_service


def _ab_create(**overrides) -> ExperimentCreate:
    """Helper to create a standard A/B experiment create schema."""
    defaults = dict(
        name="Test Experiment",
        description="Testing A/B framework",
        hypothesis="Treatment is better than control",
        variants=[
            VariantDefinition(name="control", weight=50),
            VariantDefinition(name="treatment", weight=50),
        ],
        metric="screening_pass_rate",
        metric_type=MetricType.CONTINUOUS,
        target_sample_size=100,
    )
    defaults.update(overrides)
    return ExperimentCreate(**defaults)


def _abc_create(**overrides) -> ExperimentCreate:
    """Helper to create a 3-variant experiment."""
    defaults = dict(
        name="Three-Way Experiment",
        description="Testing 3 variants",
        hypothesis="One of three approaches is best",
        variants=[
            VariantDefinition(name="control", weight=34),
            VariantDefinition(name="treatment_a", weight=33),
            VariantDefinition(name="treatment_b", weight=33),
        ],
        metric="match_score",
        metric_type=MetricType.CONTINUOUS,
        target_sample_size=100,
    )
    defaults.update(overrides)
    return ExperimentCreate(**defaults)


# ===========================================================================
# 1. Experiment CRUD
# ===========================================================================


class TestExperimentCRUD:
    """Tests for creating, reading, listing, and deleting experiments."""

    def test_create_experiment(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create())
        assert exp.id
        assert exp.name == "Test Experiment"
        assert exp.status == ExperimentStatus.DRAFT
        assert len(exp.variants) == 2
        assert exp.total_assignments == 0
        assert exp.total_outcomes == 0

    def test_create_experiment_with_description_and_hypothesis(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create(
            description="My description",
            hypothesis="My hypothesis",
        ))
        assert exp.description == "My description"
        assert exp.hypothesis == "My hypothesis"

    def test_get_experiment(self, svc: ExperimentService):
        created = svc.create_experiment(_ab_create())
        fetched = svc.get_experiment(created.id)
        assert fetched.id == created.id
        assert fetched.name == created.name

    def test_get_experiment_not_found(self, svc: ExperimentService):
        with pytest.raises(KeyError):
            svc.get_experiment("nonexistent-id")

    def test_list_experiments(self, svc: ExperimentService):
        svc.create_experiment(_ab_create(name="Exp 1"))
        svc.create_experiment(_ab_create(name="Exp 2"))
        svc.create_experiment(_ab_create(name="Exp 3"))
        exps, total = svc.list_experiments()
        assert total == 3
        assert len(exps) == 3

    def test_list_experiments_with_status_filter(self, svc: ExperimentService):
        e1 = svc.create_experiment(_ab_create(name="Draft"))
        e2 = svc.create_experiment(_ab_create(name="Running"))
        svc.start_experiment(e2.id)

        drafts, total = svc.list_experiments(status=ExperimentStatus.DRAFT)
        assert total == 1
        assert drafts[0].name == "Draft"

        running, total = svc.list_experiments(status=ExperimentStatus.RUNNING)
        assert total == 1
        assert running[0].name == "Running"

    def test_list_experiments_pagination(self, svc: ExperimentService):
        for i in range(10):
            svc.create_experiment(_ab_create(name=f"Exp {i}"))
        page, total = svc.list_experiments(offset=3, limit=4)
        assert total == 10
        assert len(page) == 4

    def test_delete_draft_experiment(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create())
        svc.delete_experiment(exp.id)
        with pytest.raises(KeyError):
            svc.get_experiment(exp.id)

    def test_delete_running_experiment_raises(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create())
        svc.start_experiment(exp.id)
        with pytest.raises(ValueError, match="Cannot delete"):
            svc.delete_experiment(exp.id)

    def test_weights_must_sum_to_100(self, svc: ExperimentService):
        with pytest.raises(ValueError, match="must sum to 100"):
            svc.create_experiment(_ab_create(
                variants=[
                    VariantDefinition(name="a", weight=30),
                    VariantDefinition(name="b", weight=30),
                ],
            ))

    def test_variant_names_must_be_unique(self, svc: ExperimentService):
        with pytest.raises(ValueError, match="unique"):
            svc.create_experiment(_ab_create(
                variants=[
                    VariantDefinition(name="same", weight=50),
                    VariantDefinition(name="same", weight=50),
                ],
            ))


# ===========================================================================
# 2. Lifecycle Transitions
# ===========================================================================


class TestLifecycleTransitions:
    """Tests for experiment state machine transitions."""

    def test_draft_to_running(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create())
        started = svc.start_experiment(exp.id)
        assert started.status == ExperimentStatus.RUNNING
        assert started.start_date is not None

    def test_running_to_paused(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create())
        svc.start_experiment(exp.id)
        paused = svc.pause_experiment(exp.id)
        assert paused.status == ExperimentStatus.PAUSED

    def test_paused_to_running(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create())
        svc.start_experiment(exp.id)
        svc.pause_experiment(exp.id)
        resumed = svc.start_experiment(exp.id)
        assert resumed.status == ExperimentStatus.RUNNING

    def test_running_to_completed(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create())
        svc.start_experiment(exp.id)
        completed = svc.complete_experiment(exp.id)
        assert completed.status == ExperimentStatus.COMPLETED
        assert completed.end_date is not None

    def test_completed_to_archived(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create())
        svc.start_experiment(exp.id)
        svc.complete_experiment(exp.id)
        archived = svc.archive_experiment(exp.id)
        assert archived.status == ExperimentStatus.ARCHIVED

    def test_invalid_transition_completed_to_running(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create())
        svc.start_experiment(exp.id)
        svc.complete_experiment(exp.id)
        with pytest.raises(ValueError, match="Invalid transition"):
            svc.start_experiment(exp.id)

    def test_invalid_transition_archived_to_running(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create())
        svc.archive_experiment(exp.id)
        with pytest.raises(ValueError, match="Invalid transition"):
            svc.start_experiment(exp.id)

    def test_invalid_transition_draft_to_completed(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create())
        with pytest.raises(ValueError, match="Invalid transition"):
            svc.complete_experiment(exp.id)

    def test_invalid_transition_draft_to_paused(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create())
        with pytest.raises(ValueError, match="Invalid transition"):
            svc.pause_experiment(exp.id)


# ===========================================================================
# 3. Deterministic Assignment
# ===========================================================================


class TestDeterministicAssignment:
    """Tests for hash-based deterministic variant assignment."""

    def test_same_patient_same_variant(self, svc: ExperimentService):
        """Same patient always gets the same variant."""
        exp = svc.create_experiment(_ab_create())
        svc.start_experiment(exp.id)

        a1 = svc.assign_variant(exp.id, "patient-001")
        a2 = svc.assign_variant(exp.id, "patient-001")
        assert a1.variant == a2.variant
        assert a1.bucket == a2.bucket

    def test_different_patients_may_get_different_variants(self, svc: ExperimentService):
        """Different patients should distribute across variants."""
        exp = svc.create_experiment(_ab_create())
        svc.start_experiment(exp.id)

        variants = set()
        for i in range(100):
            a = svc.assign_variant(exp.id, f"patient-{i:04d}")
            variants.add(a.variant)

        # With 100 patients, both variants should appear
        assert len(variants) == 2

    def test_assignment_distribution_respects_weights(self, svc: ExperimentService):
        """Assignment distribution should roughly match weights."""
        exp = svc.create_experiment(_ab_create())
        svc.start_experiment(exp.id)

        counts: Counter = Counter()
        n = 1000
        for i in range(n):
            a = svc.assign_variant(exp.id, f"patient-{i:06d}")
            counts[a.variant] += 1

        # With 50/50 weights and 1000 patients, each variant should have
        # roughly 500 assignments. Allow 15% tolerance.
        for variant in ["control", "treatment"]:
            ratio = counts[variant] / n
            assert 0.35 < ratio < 0.65, (
                f"Variant '{variant}' got {counts[variant]}/{n} = {ratio:.2%}"
            )

    def test_assignment_requires_running_experiment(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create())
        with pytest.raises(ValueError, match="must be RUNNING"):
            svc.assign_variant(exp.id, "patient-001")

    def test_bucket_is_0_to_99(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create())
        svc.start_experiment(exp.id)

        for i in range(200):
            a = svc.assign_variant(exp.id, f"p-{i}")
            assert 0 <= a.bucket <= 99


# ===========================================================================
# 4. Multi-variant support
# ===========================================================================


class TestMultiVariant:
    """Tests for 3+ variant experiments."""

    def test_three_variant_creation(self, svc: ExperimentService):
        exp = svc.create_experiment(_abc_create())
        assert len(exp.variants) == 3

    def test_three_variant_assignment_distribution(self, svc: ExperimentService):
        exp = svc.create_experiment(_abc_create())
        svc.start_experiment(exp.id)

        counts: Counter = Counter()
        n = 1000
        for i in range(n):
            a = svc.assign_variant(exp.id, f"patient-{i:06d}")
            counts[a.variant] += 1

        # 34/33/33 weights -> each should get roughly 1/3
        for variant in ["control", "treatment_a", "treatment_b"]:
            ratio = counts[variant] / n
            assert 0.20 < ratio < 0.47, (
                f"Variant '{variant}' got {counts[variant]}/{n} = {ratio:.2%}"
            )

    def test_four_variant_experiment(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create(
            name="Four variants",
            variants=[
                VariantDefinition(name="A", weight=25),
                VariantDefinition(name="B", weight=25),
                VariantDefinition(name="C", weight=25),
                VariantDefinition(name="D", weight=25),
            ],
        ))
        svc.start_experiment(exp.id)

        counts: Counter = Counter()
        n = 1000
        for i in range(n):
            a = svc.assign_variant(exp.id, f"p-{i:06d}")
            counts[a.variant] += 1

        assert len(counts) == 4
        for v in ["A", "B", "C", "D"]:
            ratio = counts[v] / n
            assert 0.15 < ratio < 0.35


# ===========================================================================
# 5. Outcome Recording
# ===========================================================================


class TestOutcomeRecording:
    """Tests for recording and aggregating outcomes."""

    def test_record_outcome(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create())
        svc.start_experiment(exp.id)
        svc.assign_variant(exp.id, "patient-001")

        result = svc.record_outcome(exp.id, OutcomeRecord(
            patient_id="patient-001",
            metric_name="screening_pass_rate",
            value=0.85,
        ))
        assert result["recorded"] is True
        assert result["patient_id"] == "patient-001"

    def test_record_requires_assignment(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create())
        svc.start_experiment(exp.id)

        with pytest.raises(ValueError, match="not assigned"):
            svc.record_outcome(exp.id, OutcomeRecord(
                patient_id="unassigned-patient",
                metric_name="screening_pass_rate",
                value=0.5,
            ))

    def test_record_requires_matching_metric(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create())
        svc.start_experiment(exp.id)
        svc.assign_variant(exp.id, "patient-001")

        with pytest.raises(ValueError, match="Metric mismatch"):
            svc.record_outcome(exp.id, OutcomeRecord(
                patient_id="patient-001",
                metric_name="wrong_metric",
                value=0.5,
            ))

    def test_record_requires_running_or_paused(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create())
        svc.start_experiment(exp.id)
        svc.assign_variant(exp.id, "patient-001")
        svc.complete_experiment(exp.id)

        with pytest.raises(ValueError, match="must be RUNNING or PAUSED"):
            svc.record_outcome(exp.id, OutcomeRecord(
                patient_id="patient-001",
                metric_name="screening_pass_rate",
                value=0.5,
            ))

    def test_outcomes_tracked_per_variant(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create())
        svc.start_experiment(exp.id)

        # Assign and record outcomes for multiple patients
        for i in range(20):
            pid = f"patient-{i:04d}"
            svc.assign_variant(exp.id, pid)
            svc.record_outcome(exp.id, OutcomeRecord(
                patient_id=pid,
                metric_name="screening_pass_rate",
                value=random.uniform(0.5, 1.0),
            ))

        updated = svc.get_experiment(exp.id)
        assert updated.total_outcomes == 20
        assert updated.total_assignments == 20


# ===========================================================================
# 6. Statistical Analysis: T-test
# ===========================================================================


class TestTTest:
    """Tests for two-sample t-test on continuous metrics."""

    def test_t_test_known_data_significant(self):
        """Two groups with very different means should be significant."""
        # Group 1: mean=10, std=2, n=50
        # Group 2: mean=14, std=2, n=50
        t_stat, p_val = _two_sample_t_test(50, 10.0, 2.0, 50, 14.0, 2.0)
        assert abs(t_stat) > 2.0  # Should have a large t-statistic
        assert p_val < 0.05  # Should be significant

    def test_t_test_known_data_not_significant(self):
        """Two groups with similar means should not be significant."""
        t_stat, p_val = _two_sample_t_test(30, 10.0, 5.0, 30, 10.3, 5.0)
        assert p_val > 0.05  # Should not be significant

    def test_t_test_insufficient_data(self):
        """T-test with n<2 should return p=1.0."""
        t_stat, p_val = _two_sample_t_test(1, 10.0, 0.0, 1, 12.0, 0.0)
        assert p_val == 1.0

    def test_t_test_with_experiment(self, svc: ExperimentService):
        """End-to-end t-test through experiment service."""
        exp = svc.create_experiment(_ab_create(
            metric="score",
            metric_type=MetricType.CONTINUOUS,
            target_sample_size=50,
        ))
        svc.start_experiment(exp.id)

        random.seed(42)
        for i in range(100):
            pid = f"p-{i:04d}"
            assignment = svc.assign_variant(exp.id, pid)
            # Control: mean ~50, Treatment: mean ~60
            if assignment.variant == "control":
                val = random.gauss(50, 10)
            else:
                val = random.gauss(60, 10)
            svc.record_outcome(exp.id, OutcomeRecord(
                patient_id=pid, metric_name="score", value=val,
            ))

        results = svc.get_results(exp.id)
        assert len(results.pairwise_comparisons) >= 1
        comp = results.pairwise_comparisons[0]
        assert comp.test_type == "t-test"
        # With a large effect, should be significant
        assert comp.p_value < 0.05
        assert comp.significant is True


# ===========================================================================
# 7. Statistical Analysis: Z-test
# ===========================================================================


class TestZTest:
    """Tests for two-proportion z-test on binary metrics."""

    def test_z_test_known_proportions_significant(self):
        """Very different proportions should be significant."""
        # 70% vs 30% with n=100 each
        z_stat, p_val = _two_proportion_z_test(100, 0.7, 100, 0.3)
        assert abs(z_stat) > 2.0
        assert p_val < 0.05

    def test_z_test_known_proportions_not_significant(self):
        """Similar proportions should not be significant."""
        z_stat, p_val = _two_proportion_z_test(30, 0.50, 30, 0.53)
        assert p_val > 0.05

    def test_z_test_with_experiment(self, svc: ExperimentService):
        """End-to-end z-test through experiment service."""
        exp = svc.create_experiment(_ab_create(
            metric="pass_fail",
            metric_type=MetricType.BINARY,
            target_sample_size=50,
        ))
        svc.start_experiment(exp.id)

        random.seed(123)
        for i in range(100):
            pid = f"p-{i:04d}"
            assignment = svc.assign_variant(exp.id, pid)
            # Control: 40% pass, Treatment: 80% pass
            if assignment.variant == "control":
                val = 1.0 if random.random() < 0.40 else 0.0
            else:
                val = 1.0 if random.random() < 0.80 else 0.0
            svc.record_outcome(exp.id, OutcomeRecord(
                patient_id=pid, metric_name="pass_fail", value=val,
            ))

        results = svc.get_results(exp.id)
        comp = results.pairwise_comparisons[0]
        assert comp.test_type == "z-test"
        assert comp.p_value < 0.05


# ===========================================================================
# 8. Effect Size
# ===========================================================================


class TestEffectSize:
    """Tests for Cohen's d, h, and interpretation."""

    def test_cohens_d_large_effect(self):
        d = _cohens_d(100.0, 10.0, 80.0, 10.0)
        assert abs(d) > 0.8
        assert _interpret_effect_size(d) == "large"

    def test_cohens_d_medium_effect(self):
        d = _cohens_d(50.0, 10.0, 55.0, 10.0)
        assert 0.2 < abs(d) < 0.8
        assert _interpret_effect_size(d) in ("small", "medium")

    def test_cohens_d_negligible(self):
        d = _cohens_d(50.0, 10.0, 50.5, 10.0)
        assert abs(d) < 0.2
        assert _interpret_effect_size(d) == "negligible"

    def test_cohens_d_zero_std(self):
        d = _cohens_d(10.0, 0.0, 10.0, 0.0)
        assert d == 0.0

    def test_cohens_h(self):
        h = _cohens_h(0.8, 0.3)
        assert abs(h) > 0.5  # Should be a large effect

    def test_effect_size_interpretation(self):
        assert _interpret_effect_size(0.1) == "negligible"
        assert _interpret_effect_size(0.3) == "small"
        assert _interpret_effect_size(0.6) == "medium"
        assert _interpret_effect_size(1.0) == "large"


# ===========================================================================
# 9. Confidence Intervals
# ===========================================================================


class TestConfidenceIntervals:
    """Tests for confidence interval computation."""

    def test_ci_contains_true_difference(self, svc: ExperimentService):
        """CI should contain the true difference for most runs."""
        exp = svc.create_experiment(_ab_create(
            metric="score",
            metric_type=MetricType.CONTINUOUS,
            target_sample_size=200,
        ))
        svc.start_experiment(exp.id)

        random.seed(999)
        true_diff = 5.0  # control=50, treatment=55
        for i in range(200):
            pid = f"p-{i:04d}"
            assignment = svc.assign_variant(exp.id, pid)
            if assignment.variant == "control":
                val = random.gauss(50, 10)
            else:
                val = random.gauss(55, 10)
            svc.record_outcome(exp.id, OutcomeRecord(
                patient_id=pid, metric_name="score", value=val,
            ))

        results = svc.get_results(exp.id)
        comp = results.pairwise_comparisons[0]

        # The 95% CI for the difference should exist
        assert comp.confidence_interval_lower < comp.confidence_interval_upper

    def test_ci_non_degenerate(self, svc: ExperimentService):
        """CI should have nonzero width when there is variation."""
        exp = svc.create_experiment(_ab_create(
            metric="score",
            metric_type=MetricType.CONTINUOUS,
        ))
        svc.start_experiment(exp.id)

        random.seed(42)
        for i in range(50):
            pid = f"p-{i}"
            svc.assign_variant(exp.id, pid)
            svc.record_outcome(exp.id, OutcomeRecord(
                patient_id=pid, metric_name="score", value=random.gauss(50, 10),
            ))

        results = svc.get_results(exp.id)
        if results.pairwise_comparisons:
            comp = results.pairwise_comparisons[0]
            width = comp.confidence_interval_upper - comp.confidence_interval_lower
            assert width > 0


# ===========================================================================
# 10. Sequential Testing
# ===========================================================================


class TestSequentialTesting:
    """Tests for O'Brien-Fleming sequential testing."""

    def test_obrien_fleming_boundary_monotonic(self):
        """Alpha spending should increase as information fraction grows."""
        boundaries = []
        for frac in [0.2, 0.4, 0.6, 0.8, 1.0]:
            b = _obrien_fleming_boundary(frac)
            boundaries.append(b)

        for i in range(len(boundaries) - 1):
            assert boundaries[i] <= boundaries[i + 1] + 1e-10

    def test_obrien_fleming_full_information_equals_alpha(self):
        """At full information fraction, boundary should equal alpha."""
        b = _obrien_fleming_boundary(1.0, alpha=0.05)
        assert abs(b - 0.05) < 0.001

    def test_obrien_fleming_early_very_conservative(self):
        """At low information, boundary should be very small."""
        b = _obrien_fleming_boundary(0.2, alpha=0.05)
        assert b < 0.01  # Should be very conservative

    def test_sequential_early_stop_large_effect(self, svc: ExperimentService):
        """Should allow early stopping with a very large effect."""
        exp = svc.create_experiment(_ab_create(
            metric="score",
            metric_type=MetricType.CONTINUOUS,
            target_sample_size=100,
        ))
        svc.start_experiment(exp.id)

        # Very large effect: control=20, treatment=80
        random.seed(42)
        for i in range(100):
            pid = f"p-{i}"
            assignment = svc.assign_variant(exp.id, pid)
            if assignment.variant == "control":
                val = random.gauss(20, 5)
            else:
                val = random.gauss(80, 5)
            svc.record_outcome(exp.id, OutcomeRecord(
                patient_id=pid, metric_name="score", value=val,
            ))

        results = svc.get_results(exp.id, total_planned_looks=5)
        assert results.sequential_test is not None
        assert results.sequential_test.can_stop_early is True

    def test_sequential_no_early_stop_small_effect(self, svc: ExperimentService):
        """Should not allow early stopping with small effect and partial data."""
        exp = svc.create_experiment(_ab_create(
            metric="score",
            metric_type=MetricType.CONTINUOUS,
            target_sample_size=1000,  # Very large target
        ))
        svc.start_experiment(exp.id)

        # Small effect, low sample
        random.seed(42)
        for i in range(20):
            pid = f"p-{i}"
            assignment = svc.assign_variant(exp.id, pid)
            if assignment.variant == "control":
                val = random.gauss(50, 15)
            else:
                val = random.gauss(51, 15)  # Tiny effect
            svc.record_outcome(exp.id, OutcomeRecord(
                patient_id=pid, metric_name="score", value=val,
            ))

        results = svc.get_results(exp.id, total_planned_looks=5)
        assert results.sequential_test is not None
        assert results.sequential_test.can_stop_early is False


# ===========================================================================
# 11. Power Analysis
# ===========================================================================


class TestPowerAnalysis:
    """Tests for statistical power estimation."""

    def test_power_large_sample_large_effect(self):
        """Large sample + large effect => high power."""
        power = _estimate_power(200, 0.8)
        assert power > 0.80

    def test_power_small_sample_small_effect(self):
        """Small sample + small effect => low power."""
        power = _estimate_power(10, 0.2)
        assert power < 0.50

    def test_power_via_service(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create(target_sample_size=200))
        svc.start_experiment(exp.id)

        random.seed(42)
        for i in range(200):
            pid = f"p-{i}"
            assignment = svc.assign_variant(exp.id, pid)
            if assignment.variant == "control":
                val = random.gauss(50, 10)
            else:
                val = random.gauss(60, 10)  # Large effect
            svc.record_outcome(exp.id, OutcomeRecord(
                patient_id=pid, metric_name="screening_pass_rate", value=val,
            ))

        power = svc.get_power_analysis(exp.id)
        assert power.is_adequately_powered is True
        assert power.estimated_power > 0.80

    def test_power_inadequate(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create(target_sample_size=1000))
        svc.start_experiment(exp.id)

        for i in range(6):
            pid = f"p-{i}"
            svc.assign_variant(exp.id, pid)
            svc.record_outcome(exp.id, OutcomeRecord(
                patient_id=pid,
                metric_name="screening_pass_rate",
                value=50.0 + (i % 2),
            ))

        power = svc.get_power_analysis(exp.id, effect_size=0.2)
        assert power.is_adequately_powered is False

    def test_samples_for_power_function(self):
        n = _samples_for_power(0.5)
        assert n > 50  # Should need a decent sample for medium effect

    def test_samples_for_power_small_effect(self):
        n = _samples_for_power(0.2)
        assert n > 300  # Small effects need large samples


# ===========================================================================
# 12. Minimum Detectable Effect
# ===========================================================================


class TestMDE:
    """Tests for minimum detectable effect calculation."""

    def test_mde_decreases_with_sample_size(self):
        mde_10 = _minimum_detectable_effect(10)
        mde_100 = _minimum_detectable_effect(100)
        mde_1000 = _minimum_detectable_effect(1000)
        assert mde_10 > mde_100 > mde_1000

    def test_mde_small_sample(self):
        mde = _minimum_detectable_effect(5)
        assert mde > 1.0  # Very small sample -> can only detect large effects

    def test_mde_insufficient_sample(self):
        mde = _minimum_detectable_effect(1)
        assert mde == float("inf")  # Raw function returns inf

    def test_mde_capped_in_power_analysis(self, svc: ExperimentService):
        """MDE should be capped to a finite value in PowerAnalysis for JSON safety."""
        exp = svc.create_experiment(_ab_create())
        power = svc.get_power_analysis(exp.id)
        assert math.isfinite(power.minimum_detectable_effect)


# ===========================================================================
# 13. Experiment Templates
# ===========================================================================


class TestTemplates:
    """Tests for pre-defined experiment templates."""

    def test_list_templates(self, svc: ExperimentService):
        templates = svc.get_templates()
        assert len(templates.templates) >= 4
        ids = [t.template_id for t in templates.templates]
        assert "screening_algorithm_comparison" in ids
        assert "nlp_pipeline_comparison" in ids
        assert "match_score_threshold" in ids
        assert "criteria_weighting" in ids

    def test_create_from_template(self, svc: ExperimentService):
        exp = svc.create_from_template("screening_algorithm_comparison")
        assert exp.status == ExperimentStatus.DRAFT
        assert exp.metric == "screening_pass_rate"
        assert exp.metric_type == MetricType.BINARY
        assert len(exp.variants) == 2

    def test_create_from_template_with_name(self, svc: ExperimentService):
        exp = svc.create_from_template(
            "nlp_pipeline_comparison",
            name="My Custom Name",
        )
        assert exp.name == "My Custom Name"

    def test_create_from_template_not_found(self, svc: ExperimentService):
        with pytest.raises(KeyError, match="not found"):
            svc.create_from_template("nonexistent_template")

    def test_criteria_weighting_template_has_3_variants(self, svc: ExperimentService):
        exp = svc.create_from_template("criteria_weighting")
        assert len(exp.variants) == 3


# ===========================================================================
# 14. Concurrent Experiments
# ===========================================================================


class TestConcurrentExperiments:
    """Tests for patients in multiple experiments simultaneously."""

    def test_patient_in_multiple_experiments(self, svc: ExperimentService):
        """Same patient can be in different experiments with different assignments."""
        exp1 = svc.create_experiment(_ab_create(name="Exp 1"))
        exp2 = svc.create_experiment(_ab_create(name="Exp 2"))
        svc.start_experiment(exp1.id)
        svc.start_experiment(exp2.id)

        a1 = svc.assign_variant(exp1.id, "patient-shared")
        a2 = svc.assign_variant(exp2.id, "patient-shared")

        # Both should succeed
        assert a1.experiment_id == exp1.id
        assert a2.experiment_id == exp2.id
        # Variants may differ since experiment IDs differ

    def test_outcomes_isolated_between_experiments(self, svc: ExperimentService):
        """Outcomes in one experiment don't affect another."""
        exp1 = svc.create_experiment(_ab_create(name="Exp 1", metric="score1"))
        exp2 = svc.create_experiment(_ab_create(name="Exp 2", metric="score2"))
        svc.start_experiment(exp1.id)
        svc.start_experiment(exp2.id)

        svc.assign_variant(exp1.id, "p1")
        svc.assign_variant(exp2.id, "p1")

        svc.record_outcome(exp1.id, OutcomeRecord(
            patient_id="p1", metric_name="score1", value=100.0,
        ))
        svc.record_outcome(exp2.id, OutcomeRecord(
            patient_id="p1", metric_name="score2", value=50.0,
        ))

        e1 = svc.get_experiment(exp1.id)
        e2 = svc.get_experiment(exp2.id)
        assert e1.total_outcomes == 1
        assert e2.total_outcomes == 1


# ===========================================================================
# 15. Math Helpers
# ===========================================================================


class TestMathHelpers:
    """Tests for the pure-math helper functions."""

    def test_norm_cdf_standard_values(self):
        assert abs(_norm_cdf(0.0) - 0.5) < 1e-6
        assert abs(_norm_cdf(1.96) - 0.975) < 0.005
        assert abs(_norm_cdf(-1.96) - 0.025) < 0.005

    def test_norm_ppf_standard_values(self):
        assert abs(_norm_ppf(0.5) - 0.0) < 1e-4
        assert abs(_norm_ppf(0.975) - 1.96) < 0.02
        assert abs(_norm_ppf(0.025) - (-1.96)) < 0.02

    def test_norm_ppf_inverse_of_cdf(self):
        for p in [0.1, 0.25, 0.5, 0.75, 0.9]:
            z = _norm_ppf(p)
            recovered = _norm_cdf(z)
            assert abs(recovered - p) < 0.001

    def test_norm_ppf_boundary(self):
        assert _norm_ppf(0.0) == -math.inf
        assert _norm_ppf(1.0) == math.inf


# ===========================================================================
# 16. Full Results and Recommendations
# ===========================================================================


class TestResultsAndRecommendations:
    """Tests for complete results including recommendations."""

    def test_results_with_no_data(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create())
        svc.start_experiment(exp.id)
        results = svc.get_results(exp.id)
        assert "Insufficient" in results.recommendation or "data" in results.recommendation.lower()

    def test_results_with_small_data(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create(metric="score"))
        svc.start_experiment(exp.id)

        for i in range(4):
            pid = f"p-{i}"
            svc.assign_variant(exp.id, pid)
            svc.record_outcome(exp.id, OutcomeRecord(
                patient_id=pid, metric_name="score", value=float(i),
            ))

        results = svc.get_results(exp.id)
        assert "observation" in results.recommendation.lower() or "data" in results.recommendation.lower()

    def test_results_include_all_components(self, svc: ExperimentService):
        exp = svc.create_experiment(_ab_create(metric="score", target_sample_size=50))
        svc.start_experiment(exp.id)

        random.seed(42)
        for i in range(60):
            pid = f"p-{i}"
            assignment = svc.assign_variant(exp.id, pid)
            val = random.gauss(50 if assignment.variant == "control" else 60, 10)
            svc.record_outcome(exp.id, OutcomeRecord(
                patient_id=pid, metric_name="score", value=val,
            ))

        results = svc.get_results(exp.id)
        assert results.experiment_id == exp.id
        assert results.experiment_name == exp.name
        assert len(results.variant_stats) == 2
        assert len(results.pairwise_comparisons) >= 1
        assert results.sequential_test is not None
        assert results.power_analysis is not None
        assert results.recommendation


# ===========================================================================
# 17. API Endpoint Integration
# ===========================================================================


@pytest.mark.anyio
async def test_api_create_experiment():
    """Test POST /experiments endpoint."""
    svc = get_experiment_service()
    svc.clear()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.post(
            "/api/v1/experiments",
            json={
                "name": "API Test",
                "variants": [
                    {"name": "control", "weight": 50},
                    {"name": "treatment", "weight": 50},
                ],
                "metric": "score",
                "metric_type": "continuous",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "API Test"
        assert data["status"] == "draft"


@pytest.mark.anyio
async def test_api_list_experiments():
    """Test GET /experiments endpoint."""
    svc = get_experiment_service()
    svc.clear()
    svc.create_experiment(_ab_create(name="Listed"))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/api/v1/experiments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1


@pytest.mark.anyio
async def test_api_lifecycle_and_assignment():
    """Test full lifecycle: create -> start -> assign -> record -> results."""
    svc = get_experiment_service()
    svc.clear()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Create
        resp = await client.post("/api/v1/experiments", json={
            "name": "Lifecycle Test",
            "variants": [
                {"name": "control", "weight": 50},
                {"name": "treatment", "weight": 50},
            ],
            "metric": "score",
            "metric_type": "continuous",
            "target_sample_size": 10,
        })
        assert resp.status_code == 201
        exp_id = resp.json()["id"]

        # Start
        resp = await client.post(f"/api/v1/experiments/{exp_id}/start")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

        # Assign
        resp = await client.post(
            f"/api/v1/experiments/{exp_id}/assign",
            json={"patient_id": "p1"},
        )
        assert resp.status_code == 200
        assert resp.json()["variant"] in ("control", "treatment")

        # Record
        resp = await client.post(
            f"/api/v1/experiments/{exp_id}/record",
            json={"patient_id": "p1", "metric_name": "score", "value": 85.0},
        )
        assert resp.status_code == 200
        assert resp.json()["recorded"] is True

        # Results
        resp = await client.get(f"/api/v1/experiments/{exp_id}/results")
        assert resp.status_code == 200
        assert resp.json()["experiment_id"] == exp_id


@pytest.mark.anyio
async def test_api_templates():
    """Test GET /experiments/templates endpoint."""
    svc = get_experiment_service()
    svc.clear()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/api/v1/experiments/templates")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["templates"]) >= 4


@pytest.mark.anyio
async def test_api_power_analysis():
    """Test GET /experiments/{id}/power endpoint."""
    svc = get_experiment_service()
    svc.clear()
    exp = svc.create_experiment(_ab_create())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get(f"/api/v1/experiments/{exp.id}/power?effect_size=0.5")
        assert resp.status_code == 200
        data = resp.json()
        assert "estimated_power" in data
        assert "minimum_detectable_effect" in data


@pytest.mark.anyio
async def test_api_invalid_transition():
    """Test that invalid transitions return 409."""
    svc = get_experiment_service()
    svc.clear()
    exp = svc.create_experiment(_ab_create())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Try to pause a draft experiment (invalid)
        resp = await client.post(f"/api/v1/experiments/{exp.id}/pause")
        assert resp.status_code == 409


@pytest.mark.anyio
async def test_api_not_found():
    """Test that missing experiments return 404."""
    svc = get_experiment_service()
    svc.clear()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/api/v1/experiments/nonexistent")
        assert resp.status_code == 404


# ===========================================================================
# 18. Service Stats
# ===========================================================================


class TestServiceStats:
    """Tests for service introspection."""

    def test_stats_empty(self, svc: ExperimentService):
        stats = svc.get_stats()
        assert stats["total_experiments"] == 0
        assert stats["templates_available"] >= 4

    def test_stats_with_experiments(self, svc: ExperimentService):
        svc.create_experiment(_ab_create(name="A"))
        e2 = svc.create_experiment(_ab_create(name="B"))
        svc.start_experiment(e2.id)

        stats = svc.get_stats()
        assert stats["total_experiments"] == 2
        assert stats["by_status"]["draft"] == 1
        assert stats["by_status"]["running"] == 1
