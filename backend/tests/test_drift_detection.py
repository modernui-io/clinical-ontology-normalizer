"""Tests for Drift Detection Service.

Tests cover:
- PSI calculation: identical distributions, shifted distributions, edge cases
- KS test: same distribution, different distributions, empty inputs
- Chi-squared test: same counts, different counts, edge cases
- Drift severity classification at all boundaries
- Baseline creation, listing, retrieval
- Feature drift identification
- Model drift: accuracy degradation detection
- Rolling window accuracy calculations
- Report generation with recommendations
- Pre-defined monitors
- Data recording and aggregation
- Drift history tracking
- API endpoints
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.drift_detection import (
    DriftRecommendation,
    DriftSeverity,
)
from app.services.drift_detection_service import (
    DriftDetectionService,
    calculate_chi_squared,
    calculate_ks_statistic,
    calculate_psi,
    classify_severity,
    get_drift_detection_service,
    reset_drift_detection_service,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_service():
    """Reset the singleton service before and after each test."""
    reset_drift_detection_service()
    yield
    reset_drift_detection_service()


@pytest.fixture
def service() -> DriftDetectionService:
    return get_drift_detection_service()


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ============================================================================
# PSI Calculation Tests
# ============================================================================


class TestPSICalculation:
    """Tests for Population Stability Index calculation."""

    def test_identical_distributions_psi_zero(self):
        """PSI of identical distributions should be 0 (or very near 0)."""
        dist = [10.0, 20.0, 30.0, 20.0, 10.0]
        psi = calculate_psi(dist, dist)
        assert psi < 0.001, f"PSI should be ~0 for identical distributions, got {psi}"

    def test_shifted_distribution_psi_positive(self):
        """PSI of shifted distributions should be positive."""
        baseline = [100.0, 200.0, 300.0, 200.0, 100.0]
        current = [50.0, 100.0, 300.0, 300.0, 150.0]
        psi = calculate_psi(baseline, current)
        assert psi > 0.0, "PSI should be positive for shifted distributions"

    def test_highly_shifted_distribution_high_psi(self):
        """Dramatically shifted distribution should yield high PSI."""
        baseline = [100.0, 100.0, 100.0, 100.0, 100.0]
        current = [1.0, 1.0, 1.0, 1.0, 500.0]
        psi = calculate_psi(baseline, current)
        assert psi > 0.5, f"PSI should be high for dramatic shift, got {psi}"

    def test_psi_symmetric(self):
        """PSI is NOT symmetric, but both directions should be >= 0."""
        a = [10.0, 20.0, 30.0]
        b = [30.0, 20.0, 10.0]
        psi_ab = calculate_psi(a, b)
        psi_ba = calculate_psi(b, a)
        assert psi_ab >= 0
        assert psi_ba >= 0

    def test_psi_empty_distributions(self):
        """PSI of two empty distributions should be 0."""
        assert calculate_psi([], []) == 0.0

    def test_psi_with_zeros(self):
        """PSI handles zeros in distributions gracefully (epsilon guard)."""
        baseline = [100.0, 0.0, 100.0]
        current = [0.0, 100.0, 100.0]
        psi = calculate_psi(baseline, current)
        assert psi >= 0.0
        assert not (psi != psi)  # not NaN

    def test_psi_different_lengths(self):
        """PSI handles distributions of different lengths by padding."""
        baseline = [100.0, 200.0, 300.0]
        current = [100.0, 200.0, 300.0, 100.0, 50.0]
        psi = calculate_psi(baseline, current)
        assert psi > 0.0  # Should be non-zero due to different shape

    def test_psi_single_bin(self):
        """PSI with single-bin distributions should be near zero."""
        psi = calculate_psi([100.0], [200.0])
        assert psi < 0.001  # Single bin = all probability in one bin


# ============================================================================
# KS Test Tests
# ============================================================================


class TestKSTest:
    """Tests for Kolmogorov-Smirnov two-sample test."""

    def test_same_distribution_high_p_value(self):
        """KS test on identical samples should give high p-value."""
        sample = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        ks_stat, p_value = calculate_ks_statistic(sample, sample)
        assert ks_stat == 0.0
        assert p_value >= 0.05

    def test_different_distributions_low_p_value(self):
        """KS test on very different samples should give low p-value."""
        sample_a = [float(i) for i in range(100)]
        sample_b = [float(i + 50) for i in range(100)]
        ks_stat, p_value = calculate_ks_statistic(sample_a, sample_b)
        assert ks_stat > 0.0
        assert p_value < 0.05, f"p-value should be < 0.05 for different distributions, got {p_value}"

    def test_ks_empty_samples(self):
        """KS test with empty samples should return (0, 1)."""
        ks_stat, p_value = calculate_ks_statistic([], [1.0, 2.0])
        assert ks_stat == 0.0
        assert p_value == 1.0

    def test_ks_both_empty(self):
        """KS test with both empty should return (0, 1)."""
        ks_stat, p_value = calculate_ks_statistic([], [])
        assert ks_stat == 0.0
        assert p_value == 1.0

    def test_ks_stat_range(self):
        """KS statistic should be between 0 and 1."""
        a = [1.0, 3.0, 5.0, 7.0, 9.0]
        b = [2.0, 4.0, 6.0, 8.0, 10.0]
        ks_stat, p_value = calculate_ks_statistic(a, b)
        assert 0.0 <= ks_stat <= 1.0
        assert 0.0 <= p_value <= 1.0


# ============================================================================
# Chi-Squared Test Tests
# ============================================================================


class TestChiSquaredTest:
    """Tests for chi-squared goodness-of-fit test."""

    def test_same_counts_high_p_value(self):
        """Chi-squared test on identical counts should give high p-value."""
        counts = [50.0, 50.0, 50.0, 50.0]
        chi2, p_value = calculate_chi_squared(counts, counts)
        assert chi2 < 0.001
        assert p_value > 0.05

    def test_different_counts_low_p_value(self):
        """Chi-squared test on very different counts should give low p-value."""
        observed = [100.0, 10.0, 10.0, 10.0]
        expected = [30.0, 30.0, 30.0, 30.0]
        chi2, p_value = calculate_chi_squared(observed, expected)
        assert chi2 > 0.0
        assert p_value < 0.05, f"p-value should be < 0.05, got {p_value}"

    def test_chi_squared_empty(self):
        """Chi-squared with empty lists should return (0, 1)."""
        chi2, p_value = calculate_chi_squared([], [])
        assert chi2 == 0.0
        assert p_value == 1.0

    def test_chi_squared_positive(self):
        """Chi-squared statistic should always be non-negative."""
        observed = [25.0, 35.0, 20.0, 20.0]
        expected = [25.0, 25.0, 25.0, 25.0]
        chi2, _ = calculate_chi_squared(observed, expected)
        assert chi2 >= 0.0


# ============================================================================
# Drift Severity Classification Tests
# ============================================================================


class TestDriftSeverity:
    """Tests for drift severity classification at boundaries."""

    def test_severity_none(self):
        """PSI < 0.1 should be NONE."""
        assert classify_severity(0.0) == DriftSeverity.NONE
        assert classify_severity(0.05) == DriftSeverity.NONE
        assert classify_severity(0.099) == DriftSeverity.NONE

    def test_severity_low(self):
        """0.1 <= PSI < 0.25 should be LOW."""
        assert classify_severity(0.1) == DriftSeverity.LOW
        assert classify_severity(0.15) == DriftSeverity.LOW
        assert classify_severity(0.249) == DriftSeverity.LOW

    def test_severity_moderate(self):
        """0.25 <= PSI < 0.5 should be MODERATE."""
        assert classify_severity(0.25) == DriftSeverity.MODERATE
        assert classify_severity(0.35) == DriftSeverity.MODERATE
        assert classify_severity(0.499) == DriftSeverity.MODERATE

    def test_severity_high(self):
        """PSI >= 0.5 should be HIGH."""
        assert classify_severity(0.5) == DriftSeverity.HIGH
        assert classify_severity(1.0) == DriftSeverity.HIGH
        assert classify_severity(5.0) == DriftSeverity.HIGH

    def test_severity_boundary_0_1(self):
        """Exact boundary at 0.1."""
        assert classify_severity(0.1) == DriftSeverity.LOW

    def test_severity_boundary_0_25(self):
        """Exact boundary at 0.25."""
        assert classify_severity(0.25) == DriftSeverity.MODERATE

    def test_severity_boundary_0_5(self):
        """Exact boundary at 0.5."""
        assert classify_severity(0.5) == DriftSeverity.HIGH


# ============================================================================
# Baseline Management Tests
# ============================================================================


class TestBaselineManagement:
    """Tests for baseline creation, listing, and retrieval."""

    def test_create_baseline(self, service: DriftDetectionService):
        baseline = service.create_baseline(
            name="initial-baseline",
            feature_distributions={"age": [10.0, 20.0, 30.0], "hba1c": [5.0, 15.0, 10.0]},
            sample_count=500,
        )
        assert baseline.id is not None
        assert baseline.name == "initial-baseline"
        assert baseline.sample_count == 500
        assert "age" in baseline.feature_distributions
        assert baseline.created_at is not None

    def test_list_baselines(self, service: DriftDetectionService):
        service.create_baseline("b1", {"f": [1.0]}, 10)
        service.create_baseline("b2", {"f": [2.0]}, 20)
        baselines = service.list_baselines()
        assert len(baselines) == 2

    def test_get_baseline_by_id(self, service: DriftDetectionService):
        baseline = service.create_baseline("test", {"f": [1.0]}, 10)
        retrieved = service.get_baseline(baseline.id)
        assert retrieved is not None
        assert retrieved.id == baseline.id
        assert retrieved.name == "test"

    def test_get_baseline_not_found(self, service: DriftDetectionService):
        assert service.get_baseline("nonexistent-id") is None

    def test_baseline_comparison(self, service: DriftDetectionService):
        """Compare two baselines via drift analysis."""
        b1 = service.create_baseline(
            "baseline-v1",
            {"age": [100.0, 200.0, 300.0], "score": [50.0, 50.0]},
            600,
        )
        # Analyse with shifted data
        analysis = service.analyze_drift(
            baseline_id=b1.id,
            current_distributions={"age": [50.0, 100.0, 400.0], "score": [80.0, 20.0]},
        )
        assert analysis.baseline_id == b1.id
        assert len(analysis.feature_drifts) == 2


# ============================================================================
# Drift Analysis Tests
# ============================================================================


class TestDriftAnalysis:
    """Tests for drift analysis."""

    def test_no_drift_identical_data(self, service: DriftDetectionService):
        """Identical distributions should show no drift."""
        dist = {"age": [100.0, 200.0, 300.0], "hba1c": [50.0, 50.0]}
        b = service.create_baseline("base", dist, 650)
        analysis = service.analyze_drift(b.id, dist)
        assert analysis.overall_severity == DriftSeverity.NONE
        assert analysis.recommendation == DriftRecommendation.STABLE

    def test_high_drift(self, service: DriftDetectionService):
        """Dramatically shifted distributions should trigger high drift."""
        baseline_dist = {"f1": [100.0, 100.0, 100.0, 100.0, 100.0]}
        current_dist = {"f1": [1.0, 1.0, 1.0, 1.0, 500.0]}
        b = service.create_baseline("base", baseline_dist, 500)
        analysis = service.analyze_drift(b.id, current_dist)
        assert analysis.overall_drift_score > 0.5
        assert analysis.overall_severity == DriftSeverity.HIGH
        assert analysis.recommendation == DriftRecommendation.RETRAIN

    def test_analysis_nonexistent_baseline(self, service: DriftDetectionService):
        """Analysing against a non-existent baseline should raise."""
        with pytest.raises(ValueError, match="not found"):
            service.analyze_drift("fake-id", {"f": [1.0]})

    def test_analysis_multiple_features(self, service: DriftDetectionService):
        """Analysis should cover all features from both baseline and current."""
        b = service.create_baseline(
            "base",
            {"age": [100.0, 200.0], "score": [50.0, 50.0]},
            350,
        )
        analysis = service.analyze_drift(
            b.id,
            {"age": [100.0, 200.0], "score": [50.0, 50.0], "new_feat": [10.0, 20.0]},
        )
        feature_names = [fd.feature for fd in analysis.feature_drifts]
        assert "age" in feature_names
        assert "score" in feature_names
        assert "new_feat" in feature_names


# ============================================================================
# Feature Drift Tests
# ============================================================================


class TestFeatureDrift:
    """Tests for feature-level drift identification."""

    def test_identify_drifting_features(self, service: DriftDetectionService):
        """Should identify which features are drifting most."""
        baseline = {
            "age": [100.0, 100.0, 100.0],
            "score": [100.0, 100.0, 100.0],
            "stable": [100.0, 100.0, 100.0],
        }
        current = {
            "age": [1.0, 1.0, 500.0],  # highly drifted
            "score": [90.0, 100.0, 110.0],  # slightly drifted
            "stable": [100.0, 100.0, 100.0],  # no drift
        }
        top = service.identify_top_drifting_features(baseline, current, top_n=2)
        assert len(top) == 2
        assert top[0].psi >= top[1].psi  # sorted descending
        assert top[0].feature == "age"  # age drifted most

    def test_feature_psi_computation(self, service: DriftDetectionService):
        """compute_feature_psi should return a FeatureDrift object."""
        fd = service.compute_feature_psi([100.0, 100.0], [100.0, 100.0])
        assert fd.severity == DriftSeverity.NONE
        assert fd.psi < 0.001


# ============================================================================
# Model Drift Tests
# ============================================================================


class TestModelDrift:
    """Tests for model accuracy drift detection."""

    def test_perfect_accuracy(self, service: DriftDetectionService):
        """All correct predictions should give accuracy 1.0."""
        for _ in range(10):
            service.record_model_outcome(predicted=True, actual=True)
        assert service.get_model_accuracy() == 1.0

    def test_zero_accuracy(self, service: DriftDetectionService):
        """All wrong predictions should give accuracy 0.0."""
        for _ in range(10):
            service.record_model_outcome(predicted=True, actual=False)
        assert service.get_model_accuracy() == 0.0

    def test_mixed_accuracy(self, service: DriftDetectionService):
        """Mixed predictions should give correct accuracy."""
        for _ in range(7):
            service.record_model_outcome(predicted=True, actual=True)
        for _ in range(3):
            service.record_model_outcome(predicted=True, actual=False)
        accuracy = service.get_model_accuracy()
        assert abs(accuracy - 0.7) < 0.01

    def test_accuracy_no_outcomes(self, service: DriftDetectionService):
        """No recorded outcomes should return 0.0."""
        assert service.get_model_accuracy() == 0.0

    def test_accuracy_degradation_alert(self, service: DriftDetectionService):
        """Alert should trigger when accuracy drops below threshold."""
        for _ in range(5):
            service.record_model_outcome(predicted=True, actual=True)
        for _ in range(15):
            service.record_model_outcome(predicted=True, actual=False)
        result = service.check_model_drift(accuracy_threshold=0.5)
        assert result["alert"] is True

    def test_no_alert_when_above_threshold(self, service: DriftDetectionService):
        """No alert when accuracy is above threshold."""
        for _ in range(9):
            service.record_model_outcome(predicted=True, actual=True)
        for _ in range(1):
            service.record_model_outcome(predicted=True, actual=False)
        result = service.check_model_drift(accuracy_threshold=0.8)
        assert result["alert"] is False


# ============================================================================
# Rolling Window Tests
# ============================================================================


class TestRollingWindow:
    """Tests for rolling window accuracy calculations."""

    def test_7_day_window(self, service: DriftDetectionService):
        """Only recent outcomes should count in 7-day window."""
        old_ts = datetime.now(timezone.utc) - timedelta(days=30)
        # Old accurate predictions
        for _ in range(10):
            service.record_model_outcome(predicted=True, actual=True, timestamp=old_ts)

        recent_ts = datetime.now(timezone.utc) - timedelta(hours=1)
        # Recent inaccurate predictions
        for _ in range(10):
            service.record_model_outcome(predicted=True, actual=False, timestamp=recent_ts)

        # 7-day window should only see the recent bad predictions
        acc_7d = service.get_model_accuracy(window_days=7)
        assert acc_7d == 0.0

        # Overall should include old good predictions too
        acc_all = service.get_model_accuracy()
        assert acc_all == 0.5

    def test_30_day_window(self, service: DriftDetectionService):
        """30-day window should include data from the past month."""
        recent_ts = datetime.now(timezone.utc) - timedelta(days=15)
        for _ in range(5):
            service.record_model_outcome(predicted=True, actual=True, timestamp=recent_ts)

        old_ts = datetime.now(timezone.utc) - timedelta(days=60)
        for _ in range(5):
            service.record_model_outcome(predicted=True, actual=False, timestamp=old_ts)

        acc_30d = service.get_model_accuracy(window_days=30)
        assert acc_30d == 1.0  # Only recent correct predictions in window


# ============================================================================
# Report Generation Tests
# ============================================================================


class TestReportGeneration:
    """Tests for drift report generation."""

    def test_generate_report_with_analysis(self, service: DriftDetectionService):
        """Report with baseline analysis should contain drift data."""
        b = service.create_baseline(
            "base",
            {"age": [100.0, 200.0, 300.0]},
            600,
        )
        report = service.generate_report(
            baseline_id=b.id,
            current_distributions={"age": [100.0, 200.0, 300.0]},
        )
        assert report.report_id is not None
        assert report.generated_at is not None
        assert report.recommendation in list(DriftRecommendation)
        assert report.summary != ""

    def test_report_retrain_recommendation(self, service: DriftDetectionService):
        """High drift should recommend retrain."""
        b = service.create_baseline(
            "base",
            {"f1": [100.0, 100.0, 100.0, 100.0, 100.0]},
            500,
        )
        report = service.generate_report(
            baseline_id=b.id,
            current_distributions={"f1": [1.0, 1.0, 1.0, 1.0, 500.0]},
        )
        assert report.recommendation == DriftRecommendation.RETRAIN

    def test_report_stable_recommendation(self, service: DriftDetectionService):
        """No drift should recommend stable."""
        dist = {"f1": [100.0, 100.0, 100.0]}
        b = service.create_baseline("base", dist, 300)
        report = service.generate_report(
            baseline_id=b.id,
            current_distributions=dist,
        )
        assert report.recommendation == DriftRecommendation.STABLE

    def test_report_top_drifting_features(self, service: DriftDetectionService):
        """Report should list top drifting features."""
        b = service.create_baseline(
            "base",
            {"age": [100.0, 100.0], "score": [100.0, 100.0]},
            200,
        )
        report = service.generate_report(
            baseline_id=b.id,
            current_distributions={"age": [1.0, 500.0], "score": [100.0, 100.0]},
        )
        assert len(report.top_drifting_features) > 0

    def test_get_latest_report(self, service: DriftDetectionService):
        """get_latest_report should return the last generated report."""
        assert service.get_latest_report() is None
        dist = {"f1": [100.0, 100.0]}
        b = service.create_baseline("base", dist, 200)
        service.generate_report(baseline_id=b.id, current_distributions=dist)
        report = service.get_latest_report()
        assert report is not None

    def test_report_includes_model_accuracy(self, service: DriftDetectionService):
        """Report should include model accuracy when outcomes are recorded."""
        for _ in range(10):
            service.record_model_outcome(predicted=True, actual=True)
        dist = {"f1": [100.0, 100.0]}
        b = service.create_baseline("base", dist, 200)
        report = service.generate_report(baseline_id=b.id, current_distributions=dist)
        assert report.model_accuracy_current is not None
        assert report.model_accuracy_baseline is not None


# ============================================================================
# Pre-defined Monitors Tests
# ============================================================================


class TestPredefinedMonitors:
    """Tests for pre-defined clinical trial monitors."""

    def test_predefined_monitors_exist(self, service: DriftDetectionService):
        """All 5 pre-defined monitors should be present."""
        monitors = service.list_monitors()
        names = {m.name for m in monitors}
        assert "patient_age_distribution" in names
        assert "condition_prevalence" in names
        assert "screening_pass_rate" in names
        assert "match_score_distribution" in names
        assert "lab_value_ranges" in names

    def test_predefined_monitor_count(self, service: DriftDetectionService):
        """Should have exactly 5 pre-defined monitors."""
        monitors = service.list_monitors()
        assert len(monitors) == 5

    def test_predefined_monitors_active(self, service: DriftDetectionService):
        """All pre-defined monitors should be active."""
        monitors = service.list_monitors()
        assert all(m.is_active for m in monitors)


# ============================================================================
# Data Recording Tests
# ============================================================================


class TestDataRecording:
    """Tests for recording data points to monitors."""

    def test_record_to_existing_monitor(self, service: DriftDetectionService):
        """Recording to an existing monitor should succeed."""
        result = service.record_data_point("patient_age_distribution", 45.0)
        assert result.monitor_name == "patient_age_distribution"
        assert result.value == 45.0
        assert result.total_points == 1

    def test_record_to_new_monitor(self, service: DriftDetectionService):
        """Recording to a non-existent monitor should auto-create it."""
        result = service.record_data_point("custom_metric", 0.95)
        assert result.monitor_name == "custom_metric"
        assert result.total_points == 1
        # Verify it was created
        monitors = service.list_monitors()
        names = {m.name for m in monitors}
        assert "custom_metric" in names

    def test_record_multiple_points(self, service: DriftDetectionService):
        """Multiple recordings should accumulate."""
        service.record_data_point("screening_pass_rate", 0.8)
        service.record_data_point("screening_pass_rate", 0.75)
        result = service.record_data_point("screening_pass_rate", 0.7)
        assert result.total_points == 3

    def test_get_monitor_values(self, service: DriftDetectionService):
        """Should retrieve all recorded values for a monitor."""
        service.record_data_point("lab_value_ranges", 6.5)
        service.record_data_point("lab_value_ranges", 7.0)
        service.record_data_point("lab_value_ranges", 7.5)
        values = service.get_monitor_values("lab_value_ranges")
        assert values == [6.5, 7.0, 7.5]

    def test_get_monitor_values_empty(self, service: DriftDetectionService):
        """Non-existent monitor should return empty list."""
        assert service.get_monitor_values("nonexistent") == []


# ============================================================================
# Drift History Tests
# ============================================================================


class TestDriftHistory:
    """Tests for drift history tracking."""

    def test_history_populated_after_analysis(self, service: DriftDetectionService):
        """Drift history should grow after each analysis."""
        dist = {"f1": [100.0, 100.0]}
        b = service.create_baseline("base", dist, 200)
        service.analyze_drift(b.id, dist)
        history = service.get_drift_history()
        assert history.total == 1
        assert len(history.entries) == 1

    def test_history_limit(self, service: DriftDetectionService):
        """History should respect the limit parameter."""
        dist = {"f1": [100.0, 100.0]}
        b = service.create_baseline("base", dist, 200)
        for _ in range(5):
            service.analyze_drift(b.id, dist)
        history = service.get_drift_history(limit=3)
        assert len(history.entries) == 3

    def test_history_empty(self, service: DriftDetectionService):
        """Empty history should return 0 entries."""
        history = service.get_drift_history()
        assert history.total == 0


# ============================================================================
# Service Stats Tests
# ============================================================================


class TestServiceStats:
    """Tests for service statistics."""

    def test_initial_stats(self, service: DriftDetectionService):
        """Fresh service should have correct initial stats."""
        stats = service.get_stats()
        assert stats["baselines"] == 0
        assert stats["monitors"] == 5  # pre-defined
        assert stats["drift_history_entries"] == 0
        assert stats["model_outcomes"] == 0
        assert stats["has_latest_report"] is False


# ============================================================================
# API Endpoint Tests
# ============================================================================


class TestAPIEndpoints:
    """Tests for the REST API layer."""

    @pytest.mark.asyncio
    async def test_create_baseline_api(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/drift/baselines",
                json={
                    "name": "test-baseline",
                    "feature_distributions": {"age": [10.0, 20.0, 30.0]},
                    "sample_count": 60,
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test-baseline"
        assert data["sample_count"] == 60
        assert "id" in data

    @pytest.mark.asyncio
    async def test_list_baselines_api(self, client):
        svc = get_drift_detection_service()
        svc.create_baseline("b1", {"f": [1.0]}, 10)

        async with client as ac:
            response = await ac.get("/api/v1/drift/baselines")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_get_baseline_api(self, client):
        svc = get_drift_detection_service()
        baseline = svc.create_baseline("b1", {"f": [1.0]}, 10)

        async with client as ac:
            response = await ac.get(f"/api/v1/drift/baselines/{baseline.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == baseline.id

    @pytest.mark.asyncio
    async def test_get_baseline_not_found_api(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/drift/baselines/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_analyze_drift_api(self, client):
        svc = get_drift_detection_service()
        baseline = svc.create_baseline("b1", {"age": [100.0, 200.0]}, 300)

        async with client as ac:
            response = await ac.post(
                "/api/v1/drift/analyze",
                json={
                    "baseline_id": baseline.id,
                    "current_distributions": {"age": [100.0, 200.0]},
                    "current_sample_count": 300,
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert "overall_drift_score" in data
        assert "feature_drifts" in data

    @pytest.mark.asyncio
    async def test_analyze_drift_not_found_api(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/drift/analyze",
                json={
                    "baseline_id": "fake",
                    "current_distributions": {"f": [1.0]},
                },
            )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_monitors_api(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/drift/monitors")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5  # pre-defined monitors

    @pytest.mark.asyncio
    async def test_record_data_point_api(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/drift/record",
                json={
                    "monitor_name": "patient_age_distribution",
                    "value": 55.0,
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["monitor_name"] == "patient_age_distribution"
        assert data["value"] == 55.0

    @pytest.mark.asyncio
    async def test_drift_history_api(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/drift/history")
        assert response.status_code == 200
        data = response.json()
        assert "entries" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_drift_report_not_found_api(self, client):
        """Should return 404 when no report has been generated yet."""
        async with client as ac:
            response = await ac.get("/api/v1/drift/report")
        assert response.status_code == 404
