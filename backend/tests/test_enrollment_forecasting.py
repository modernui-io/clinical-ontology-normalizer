"""Tests for Enrollment Forecasting Engine (CMO-10).

Covers:
- Seed data verification (3 trials, data points, milestones, site rates)
- Forecast generation (all methods)
- Monte Carlo simulation (percentiles, convergence, distribution shape)
- Scenario analysis (3 scenarios, probability sum)
- Site-level analysis
- Milestone CRUD + variance
- Trend detection
- Risk scoring
- Aggregate metrics
- Data point management
- API integration (all endpoints)
- Error handling (404s, invalid inputs)
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.enrollment_forecasting import (
    ConfidenceLevel,
    DataPointCreateRequest,
    EnrollmentTrend,
    ForecastMethod,
    ForecastRequest,
    MilestoneCreateRequest,
    MilestoneStatus,
    MilestoneUpdateRequest,
    RiskFactor,
    ScenarioType,
)
from app.services.enrollment_forecasting_service import (
    DUPIXENT_TRIAL_ID,
    EYLEA_TRIAL_ID,
    EnrollmentForecastingService,
    LIBTAYO_TRIAL_ID,
    get_enrollment_forecasting_service,
    reset_enrollment_forecasting_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1/enrollment-forecasting"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_enrollment_forecasting_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> EnrollmentForecastingService:
    """Shorthand for the fresh service."""
    return fresh_service


# ===========================================================================
# Section 1: Seed data verification
# ===========================================================================


class TestSeedData:
    """Verify the seed data is loaded correctly on service init."""

    def test_seed_three_trials(self, svc: EnrollmentForecastingService):
        """Seed should contain exactly 3 trial forecasts."""
        forecasts = svc.list_forecasts()
        assert len(forecasts) == 3

    def test_seed_eylea_forecast(self, svc: EnrollmentForecastingService):
        """EYLEA forecast should have correct target and current enrollment."""
        fc = svc.get_forecast(EYLEA_TRIAL_ID)
        assert fc is not None
        assert fc.trial_name == "EYLEA HD (Aflibercept 8mg) - PHOTON Extension"
        assert fc.target_enrollment == 240
        assert fc.current_enrollment == 87

    def test_seed_dupixent_forecast(self, svc: EnrollmentForecastingService):
        """Dupixent forecast should have correct target and current enrollment."""
        fc = svc.get_forecast(DUPIXENT_TRIAL_ID)
        assert fc is not None
        assert fc.target_enrollment == 180
        assert fc.current_enrollment == 134

    def test_seed_libtayo_forecast(self, svc: EnrollmentForecastingService):
        """Libtayo forecast should have correct target and current enrollment."""
        fc = svc.get_forecast(LIBTAYO_TRIAL_ID)
        assert fc is not None
        assert fc.target_enrollment == 120
        assert fc.current_enrollment == 23

    def test_seed_eylea_sites(self, svc: EnrollmentForecastingService):
        """EYLEA should have 15 sites."""
        fc = svc.get_forecast(EYLEA_TRIAL_ID)
        assert len(fc.site_rates) == 15

    def test_seed_dupixent_sites(self, svc: EnrollmentForecastingService):
        """Dupixent should have 12 sites."""
        fc = svc.get_forecast(DUPIXENT_TRIAL_ID)
        assert len(fc.site_rates) == 12

    def test_seed_libtayo_sites(self, svc: EnrollmentForecastingService):
        """Libtayo should have 8 sites."""
        fc = svc.get_forecast(LIBTAYO_TRIAL_ID)
        assert len(fc.site_rates) == 8

    def test_seed_eylea_milestones(self, svc: EnrollmentForecastingService):
        """EYLEA should have 5 milestones."""
        ms = svc.get_milestones(EYLEA_TRIAL_ID)
        assert len(ms) == 5

    def test_seed_dupixent_milestones(self, svc: EnrollmentForecastingService):
        """Dupixent should have 5 milestones."""
        ms = svc.get_milestones(DUPIXENT_TRIAL_ID)
        assert len(ms) == 5

    def test_seed_libtayo_milestones(self, svc: EnrollmentForecastingService):
        """Libtayo should have 4 milestones."""
        ms = svc.get_milestones(LIBTAYO_TRIAL_ID)
        assert len(ms) == 4

    def test_seed_eylea_data_points(self, svc: EnrollmentForecastingService):
        """EYLEA should have 30+ data points."""
        dp = svc.get_data_points(EYLEA_TRIAL_ID)
        assert len(dp) >= 30

    def test_seed_dupixent_data_points(self, svc: EnrollmentForecastingService):
        """Dupixent should have 30+ data points."""
        dp = svc.get_data_points(DUPIXENT_TRIAL_ID)
        assert len(dp) >= 30

    def test_seed_libtayo_data_points(self, svc: EnrollmentForecastingService):
        """Libtayo should have data points."""
        dp = svc.get_data_points(LIBTAYO_TRIAL_ID)
        assert len(dp) > 0

    def test_seed_eylea_fpi_milestone_achieved(self, svc: EnrollmentForecastingService):
        """EYLEA FPI milestone should be achieved."""
        ms = svc.get_milestone(EYLEA_TRIAL_ID, "MS-0001")
        assert ms is not None
        assert ms.status == MilestoneStatus.ACHIEVED
        assert ms.milestone_name == "First Patient In (FPI)"

    def test_seed_milestone_ids_sequential(self, svc: EnrollmentForecastingService):
        """Milestone IDs should follow MS-NNNN pattern."""
        for trial_id in [EYLEA_TRIAL_ID, DUPIXENT_TRIAL_ID, LIBTAYO_TRIAL_ID]:
            ms_list = svc.get_milestones(trial_id)
            for ms in ms_list:
                assert ms.id.startswith("MS-")

    def test_seed_forecast_ids(self, svc: EnrollmentForecastingService):
        """Forecast IDs should be FC-0001, FC-0002, FC-0003."""
        fc1 = svc.get_forecast(EYLEA_TRIAL_ID)
        fc2 = svc.get_forecast(DUPIXENT_TRIAL_ID)
        fc3 = svc.get_forecast(LIBTAYO_TRIAL_ID)
        assert fc1.id == "FC-0001"
        assert fc2.id == "FC-0002"
        assert fc3.id == "FC-0003"

    def test_seed_data_points_cumulative_non_decreasing(self, svc: EnrollmentForecastingService):
        """Data points cumulative enrollment should be non-decreasing."""
        for trial_id in [EYLEA_TRIAL_ID, DUPIXENT_TRIAL_ID, LIBTAYO_TRIAL_ID]:
            dp = svc.get_data_points(trial_id)
            for i in range(1, len(dp)):
                assert dp[i].cumulative_enrolled >= dp[i - 1].cumulative_enrolled

    def test_seed_last_data_point_matches_current(self, svc: EnrollmentForecastingService):
        """Last data point should match forecast current enrollment."""
        for trial_id, expected in [
            (EYLEA_TRIAL_ID, 87),
            (DUPIXENT_TRIAL_ID, 134),
            (LIBTAYO_TRIAL_ID, 23),
        ]:
            dp = svc.get_data_points(trial_id)
            assert dp[-1].cumulative_enrolled == expected

    def test_seed_site_rates_all_active(self, svc: EnrollmentForecastingService):
        """All seed sites should be active."""
        for trial_id in [EYLEA_TRIAL_ID, DUPIXENT_TRIAL_ID, LIBTAYO_TRIAL_ID]:
            rates = svc.get_site_rates(trial_id)
            assert all(s.active for s in rates)

    def test_seed_eylea_trend(self, svc: EnrollmentForecastingService):
        """EYLEA should have STEADY trend."""
        fc = svc.get_forecast(EYLEA_TRIAL_ID)
        assert fc.trend == EnrollmentTrend.STEADY

    def test_seed_dupixent_trend(self, svc: EnrollmentForecastingService):
        """Dupixent should have ACCELERATING trend."""
        fc = svc.get_forecast(DUPIXENT_TRIAL_ID)
        assert fc.trend == EnrollmentTrend.ACCELERATING

    def test_seed_libtayo_trend(self, svc: EnrollmentForecastingService):
        """Libtayo should have DECELERATING trend."""
        fc = svc.get_forecast(LIBTAYO_TRIAL_ID)
        assert fc.trend == EnrollmentTrend.DECELERATING


# ===========================================================================
# Section 2: Forecast generation
# ===========================================================================


class TestForecastGeneration:
    """Test forecast generation with various methods."""

    def test_generate_forecast_monte_carlo(self, svc: EnrollmentForecastingService):
        """Generate forecast with Monte Carlo method."""
        req = ForecastRequest(method=ForecastMethod.MONTE_CARLO)
        result = svc.generate_forecast(EYLEA_TRIAL_ID, req)
        assert result is not None
        assert result.method == ForecastMethod.MONTE_CARLO
        assert result.trial_id == EYLEA_TRIAL_ID

    def test_generate_forecast_linear_regression(self, svc: EnrollmentForecastingService):
        """Generate forecast with linear regression method."""
        req = ForecastRequest(method=ForecastMethod.LINEAR_REGRESSION)
        result = svc.generate_forecast(DUPIXENT_TRIAL_ID, req)
        assert result is not None
        assert result.method == ForecastMethod.LINEAR_REGRESSION

    def test_generate_forecast_exponential_smoothing(self, svc: EnrollmentForecastingService):
        """Generate forecast with exponential smoothing method."""
        req = ForecastRequest(method=ForecastMethod.EXPONENTIAL_SMOOTHING)
        result = svc.generate_forecast(EYLEA_TRIAL_ID, req)
        assert result is not None
        assert result.method == ForecastMethod.EXPONENTIAL_SMOOTHING

    def test_generate_forecast_poisson_process(self, svc: EnrollmentForecastingService):
        """Generate forecast with Poisson process method."""
        req = ForecastRequest(method=ForecastMethod.POISSON_PROCESS)
        result = svc.generate_forecast(LIBTAYO_TRIAL_ID, req)
        assert result is not None
        assert result.method == ForecastMethod.POISSON_PROCESS

    def test_generate_forecast_bayesian(self, svc: EnrollmentForecastingService):
        """Generate forecast with Bayesian method."""
        req = ForecastRequest(method=ForecastMethod.BAYESIAN)
        result = svc.generate_forecast(EYLEA_TRIAL_ID, req)
        assert result is not None
        assert result.method == ForecastMethod.BAYESIAN

    def test_generate_forecast_weighted_moving_average(self, svc: EnrollmentForecastingService):
        """Generate forecast with weighted moving average method."""
        req = ForecastRequest(method=ForecastMethod.WEIGHTED_MOVING_AVERAGE)
        result = svc.generate_forecast(EYLEA_TRIAL_ID, req)
        assert result is not None
        assert result.method == ForecastMethod.WEIGHTED_MOVING_AVERAGE

    def test_generate_forecast_default_method(self, svc: EnrollmentForecastingService):
        """Generate forecast with default method (no request)."""
        result = svc.generate_forecast(EYLEA_TRIAL_ID)
        assert result is not None
        assert result.method == ForecastMethod.MONTE_CARLO

    def test_generate_forecast_not_found(self, svc: EnrollmentForecastingService):
        """Generate forecast for non-existent trial returns None."""
        result = svc.generate_forecast("non-existent-trial")
        assert result is None

    def test_forecast_has_target_enrollment(self, svc: EnrollmentForecastingService):
        """Forecast result should contain target enrollment."""
        result = svc.generate_forecast(EYLEA_TRIAL_ID)
        assert result.target_enrollment == 240

    def test_forecast_has_current_enrollment(self, svc: EnrollmentForecastingService):
        """Forecast result should contain current enrollment."""
        result = svc.generate_forecast(EYLEA_TRIAL_ID)
        assert result.current_enrollment == 87

    def test_forecast_days_to_target_positive(self, svc: EnrollmentForecastingService):
        """Days to target should be positive when not fully enrolled."""
        result = svc.generate_forecast(EYLEA_TRIAL_ID)
        assert result.days_to_target > 0

    def test_forecast_enrollment_rate_positive(self, svc: EnrollmentForecastingService):
        """Enrollment rate should be positive for active trial."""
        result = svc.generate_forecast(EYLEA_TRIAL_ID)
        assert result.enrollment_rate_per_month > 0

    def test_forecast_confidence_interval_ordering(self, svc: EnrollmentForecastingService):
        """Lower CI should be before upper CI."""
        result = svc.generate_forecast(EYLEA_TRIAL_ID)
        assert result.confidence_interval_lower <= result.projected_completion_date
        assert result.projected_completion_date <= result.confidence_interval_upper

    def test_forecast_data_points_used(self, svc: EnrollmentForecastingService):
        """Forecast should report number of data points used."""
        result = svc.generate_forecast(EYLEA_TRIAL_ID)
        assert result.data_points_used >= 30

    def test_forecast_has_confidence_level(self, svc: EnrollmentForecastingService):
        """Forecast should have a confidence level."""
        result = svc.generate_forecast(EYLEA_TRIAL_ID)
        assert result.confidence_level in list(ConfidenceLevel)

    def test_forecast_includes_scenarios(self, svc: EnrollmentForecastingService):
        """Forecast should include scenario analysis by default."""
        result = svc.generate_forecast(EYLEA_TRIAL_ID)
        assert len(result.scenarios) == 3

    def test_forecast_without_scenarios(self, svc: EnrollmentForecastingService):
        """Forecast without scenario analysis."""
        req = ForecastRequest(include_scenarios=False)
        result = svc.generate_forecast(EYLEA_TRIAL_ID, req)
        assert len(result.scenarios) == 0

    def test_forecast_updates_forecast_result(self, svc: EnrollmentForecastingService):
        """Generating a forecast should update the stored forecast result."""
        svc.generate_forecast(EYLEA_TRIAL_ID)
        fc = svc.get_forecast(EYLEA_TRIAL_ID)
        assert fc.forecast_result is not None

    def test_forecast_updates_method(self, svc: EnrollmentForecastingService):
        """Generating a forecast should update the stored method."""
        req = ForecastRequest(method=ForecastMethod.LINEAR_REGRESSION)
        svc.generate_forecast(EYLEA_TRIAL_ID, req)
        fc = svc.get_forecast(EYLEA_TRIAL_ID)
        assert fc.forecast_method == ForecastMethod.LINEAR_REGRESSION


# ===========================================================================
# Section 3: Monte Carlo simulation
# ===========================================================================


class TestMonteCarlo:
    """Test Monte Carlo simulation functionality."""

    def test_monte_carlo_basic(self, svc: EnrollmentForecastingService):
        """Monte Carlo should return valid results."""
        result = svc.run_monte_carlo(EYLEA_TRIAL_ID, n_simulations=200)
        assert result is not None
        assert result.simulations_run == 200

    def test_monte_carlo_percentile_ordering(self, svc: EnrollmentForecastingService):
        """Percentile dates should be in order: p10 <= p25 <= p50 <= p75 <= p90."""
        result = svc.run_monte_carlo(EYLEA_TRIAL_ID, n_simulations=500)
        assert result.p10_date <= result.p25_date
        assert result.p25_date <= result.p50_date
        assert result.p50_date <= result.p75_date
        assert result.p75_date <= result.p90_date

    def test_monte_carlo_mean_positive(self, svc: EnrollmentForecastingService):
        """Mean days to target should be positive for active trial."""
        result = svc.run_monte_carlo(EYLEA_TRIAL_ID, n_simulations=200)
        assert result.mean_days_to_target > 0

    def test_monte_carlo_std_dev_positive(self, svc: EnrollmentForecastingService):
        """Standard deviation should be positive for multiple simulations."""
        result = svc.run_monte_carlo(EYLEA_TRIAL_ID, n_simulations=200)
        assert result.std_dev_days > 0

    def test_monte_carlo_histogram_present(self, svc: EnrollmentForecastingService):
        """Histogram buckets should be generated."""
        result = svc.run_monte_carlo(EYLEA_TRIAL_ID, n_simulations=200)
        assert len(result.histogram_buckets) > 0

    def test_monte_carlo_histogram_counts_sum(self, svc: EnrollmentForecastingService):
        """Histogram counts should sum to total simulations."""
        result = svc.run_monte_carlo(EYLEA_TRIAL_ID, n_simulations=200)
        total = sum(b["count"] for b in result.histogram_buckets)
        assert total == 200

    def test_monte_carlo_stores_result(self, svc: EnrollmentForecastingService):
        """Monte Carlo result should be stored on the forecast."""
        svc.run_monte_carlo(EYLEA_TRIAL_ID, n_simulations=200)
        fc = svc.get_forecast(EYLEA_TRIAL_ID)
        assert fc.monte_carlo is not None

    def test_monte_carlo_not_found(self, svc: EnrollmentForecastingService):
        """Monte Carlo on non-existent trial returns None."""
        result = svc.run_monte_carlo("non-existent")
        assert result is None

    def test_monte_carlo_deterministic(self, svc: EnrollmentForecastingService):
        """Monte Carlo with same seed should produce deterministic results."""
        r1 = svc.run_monte_carlo(EYLEA_TRIAL_ID, n_simulations=200)
        reset_enrollment_forecasting_service()
        svc2 = get_enrollment_forecasting_service()
        r2 = svc2.run_monte_carlo(EYLEA_TRIAL_ID, n_simulations=200)
        assert r1.mean_days_to_target == r2.mean_days_to_target

    def test_monte_carlo_different_trials(self, svc: EnrollmentForecastingService):
        """Different trials should produce different Monte Carlo results."""
        r1 = svc.run_monte_carlo(EYLEA_TRIAL_ID, n_simulations=200)
        r2 = svc.run_monte_carlo(DUPIXENT_TRIAL_ID, n_simulations=200)
        # They should differ because the trials have different enrollment rates
        assert r1.mean_days_to_target != r2.mean_days_to_target

    def test_monte_carlo_p50_between_p25_p75(self, svc: EnrollmentForecastingService):
        """P50 date should be between P25 and P75."""
        result = svc.run_monte_carlo(EYLEA_TRIAL_ID, n_simulations=500)
        assert result.p25_date <= result.p50_date <= result.p75_date


# ===========================================================================
# Section 4: Scenario analysis
# ===========================================================================


class TestScenarioAnalysis:
    """Test scenario analysis functionality."""

    def test_scenarios_returns_three(self, svc: EnrollmentForecastingService):
        """Should return 3 scenarios: optimistic, base, pessimistic."""
        scenarios = svc.get_scenarios(EYLEA_TRIAL_ID)
        assert scenarios is not None
        assert len(scenarios) == 3

    def test_scenario_types(self, svc: EnrollmentForecastingService):
        """Should include all three scenario types."""
        scenarios = svc.get_scenarios(EYLEA_TRIAL_ID)
        types = {s.scenario_type for s in scenarios}
        assert ScenarioType.OPTIMISTIC in types
        assert ScenarioType.BASE_CASE in types
        assert ScenarioType.PESSIMISTIC in types

    def test_scenario_probability_sum(self, svc: EnrollmentForecastingService):
        """Scenario probabilities should sum to 1.0."""
        scenarios = svc.get_scenarios(EYLEA_TRIAL_ID)
        total = sum(s.probability for s in scenarios)
        assert abs(total - 1.0) < 0.01

    def test_optimistic_fastest(self, svc: EnrollmentForecastingService):
        """Optimistic scenario should complete earliest."""
        scenarios = svc.get_scenarios(EYLEA_TRIAL_ID)
        by_type = {s.scenario_type: s for s in scenarios}
        assert by_type[ScenarioType.OPTIMISTIC].projected_completion_date <= by_type[ScenarioType.BASE_CASE].projected_completion_date

    def test_pessimistic_slowest(self, svc: EnrollmentForecastingService):
        """Pessimistic scenario should complete latest."""
        scenarios = svc.get_scenarios(EYLEA_TRIAL_ID)
        by_type = {s.scenario_type: s for s in scenarios}
        assert by_type[ScenarioType.PESSIMISTIC].projected_completion_date >= by_type[ScenarioType.BASE_CASE].projected_completion_date

    def test_optimistic_rate_higher(self, svc: EnrollmentForecastingService):
        """Optimistic scenario should have higher enrollment rate."""
        scenarios = svc.get_scenarios(EYLEA_TRIAL_ID)
        by_type = {s.scenario_type: s for s in scenarios}
        assert by_type[ScenarioType.OPTIMISTIC].enrollment_rate > by_type[ScenarioType.BASE_CASE].enrollment_rate

    def test_pessimistic_rate_lower(self, svc: EnrollmentForecastingService):
        """Pessimistic scenario should have lower enrollment rate."""
        scenarios = svc.get_scenarios(EYLEA_TRIAL_ID)
        by_type = {s.scenario_type: s for s in scenarios}
        assert by_type[ScenarioType.PESSIMISTIC].enrollment_rate < by_type[ScenarioType.BASE_CASE].enrollment_rate

    def test_scenarios_have_assumptions(self, svc: EnrollmentForecastingService):
        """Each scenario should have assumptions."""
        scenarios = svc.get_scenarios(EYLEA_TRIAL_ID)
        for s in scenarios:
            assert len(s.assumptions) > 0

    def test_scenarios_not_found(self, svc: EnrollmentForecastingService):
        """Scenarios for non-existent trial returns None."""
        result = svc.get_scenarios("non-existent")
        assert result is None


# ===========================================================================
# Section 5: Site-level analysis
# ===========================================================================


class TestSiteAnalysis:
    """Test site-level enrollment analysis."""

    def test_site_rates_count(self, svc: EnrollmentForecastingService):
        """EYLEA should have 15 site rates."""
        rates = svc.get_site_rates(EYLEA_TRIAL_ID)
        assert len(rates) == 15

    def test_site_rates_have_names(self, svc: EnrollmentForecastingService):
        """All sites should have names."""
        rates = svc.get_site_rates(EYLEA_TRIAL_ID)
        for r in rates:
            assert r.site_name
            assert r.site_id

    def test_site_enrollment_rate_positive(self, svc: EnrollmentForecastingService):
        """All sites should have positive enrollment rates."""
        rates = svc.get_site_rates(EYLEA_TRIAL_ID)
        for r in rates:
            assert r.enrollment_rate_per_month > 0

    def test_site_screen_failure_rate_bounded(self, svc: EnrollmentForecastingService):
        """Screen failure rates should be between 0 and 1."""
        rates = svc.get_site_rates(EYLEA_TRIAL_ID)
        for r in rates:
            assert 0 <= r.screen_failure_rate <= 1.0

    def test_site_capacity_remaining_non_negative(self, svc: EnrollmentForecastingService):
        """Capacity remaining should be non-negative."""
        rates = svc.get_site_rates(EYLEA_TRIAL_ID)
        for r in rates:
            assert r.capacity_remaining >= 0

    def test_site_rates_not_found(self, svc: EnrollmentForecastingService):
        """Site rates for non-existent trial returns None."""
        result = svc.get_site_rates("non-existent")
        assert result is None

    def test_libtayo_high_screen_failure(self, svc: EnrollmentForecastingService):
        """Libtayo oncology sites should have higher screen failure rates."""
        rates = svc.get_site_rates(LIBTAYO_TRIAL_ID)
        avg_sfr = sum(r.screen_failure_rate for r in rates) / len(rates)
        assert avg_sfr > 0.25  # Oncology trials typically have higher screen failures


# ===========================================================================
# Section 6: Milestone management
# ===========================================================================


class TestMilestones:
    """Test milestone CRUD and variance tracking."""

    def test_list_milestones(self, svc: EnrollmentForecastingService):
        """Should list milestones for a trial."""
        ms = svc.get_milestones(EYLEA_TRIAL_ID)
        assert len(ms) == 5

    def test_get_single_milestone(self, svc: EnrollmentForecastingService):
        """Should get a specific milestone by ID."""
        ms = svc.get_milestone(EYLEA_TRIAL_ID, "MS-0001")
        assert ms is not None
        assert ms.milestone_name == "First Patient In (FPI)"

    def test_add_milestone(self, svc: EnrollmentForecastingService):
        """Should add a new milestone."""
        req = MilestoneCreateRequest(
            milestone_name="Interim Analysis",
            target_count=100,
            target_date=date.today() + timedelta(days=90),
        )
        ms = svc.add_milestone(EYLEA_TRIAL_ID, req)
        assert ms is not None
        assert ms.id.startswith("MS-")
        assert ms.milestone_name == "Interim Analysis"
        assert ms.status == MilestoneStatus.PENDING

    def test_add_milestone_increments_count(self, svc: EnrollmentForecastingService):
        """Adding milestone should increase milestone count."""
        before = len(svc.get_milestones(EYLEA_TRIAL_ID))
        req = MilestoneCreateRequest(
            milestone_name="Test",
            target_count=50,
            target_date=date.today() + timedelta(days=30),
        )
        svc.add_milestone(EYLEA_TRIAL_ID, req)
        after = len(svc.get_milestones(EYLEA_TRIAL_ID))
        assert after == before + 1

    def test_update_milestone_actual_count(self, svc: EnrollmentForecastingService):
        """Should update milestone actual count."""
        req = MilestoneUpdateRequest(actual_count=65)
        ms = svc.update_milestone(EYLEA_TRIAL_ID, "MS-0003", req)
        assert ms is not None
        assert ms.actual_count == 65

    def test_update_milestone_actual_date_and_variance(self, svc: EnrollmentForecastingService):
        """Should update milestone actual date and compute variance."""
        original = svc.get_milestone(EYLEA_TRIAL_ID, "MS-0003")
        target_d = original.target_date
        actual_d = target_d - timedelta(days=5)
        req = MilestoneUpdateRequest(actual_date=actual_d)
        ms = svc.update_milestone(EYLEA_TRIAL_ID, "MS-0003", req)
        assert ms is not None
        assert ms.actual_date == actual_d
        assert ms.variance_days == 5  # 5 days ahead

    def test_update_milestone_status(self, svc: EnrollmentForecastingService):
        """Should update milestone status."""
        req = MilestoneUpdateRequest(status=MilestoneStatus.ACHIEVED)
        ms = svc.update_milestone(EYLEA_TRIAL_ID, "MS-0003", req)
        assert ms.status == MilestoneStatus.ACHIEVED

    def test_update_milestone_not_found(self, svc: EnrollmentForecastingService):
        """Should return None for non-existent milestone."""
        req = MilestoneUpdateRequest(actual_count=10)
        ms = svc.update_milestone(EYLEA_TRIAL_ID, "MS-9999", req)
        assert ms is None

    def test_add_milestone_not_found_trial(self, svc: EnrollmentForecastingService):
        """Should return None for non-existent trial."""
        req = MilestoneCreateRequest(
            milestone_name="Test",
            target_count=50,
            target_date=date.today() + timedelta(days=30),
        )
        ms = svc.add_milestone("non-existent", req)
        assert ms is None

    def test_milestone_variance_negative_for_late(self, svc: EnrollmentForecastingService):
        """Variance should be negative when actual date is after target date."""
        original = svc.get_milestone(EYLEA_TRIAL_ID, "MS-0003")
        actual_d = original.target_date + timedelta(days=10)
        req = MilestoneUpdateRequest(actual_date=actual_d)
        ms = svc.update_milestone(EYLEA_TRIAL_ID, "MS-0003", req)
        assert ms.variance_days == -10

    def test_seed_milestone_fpi_variance_zero(self, svc: EnrollmentForecastingService):
        """EYLEA FPI should have 0 variance (on time)."""
        ms = svc.get_milestone(EYLEA_TRIAL_ID, "MS-0001")
        assert ms.variance_days == 0

    def test_seed_milestone_25pct_variance_positive(self, svc: EnrollmentForecastingService):
        """EYLEA 25% milestone should have positive variance (ahead of schedule)."""
        ms = svc.get_milestone(EYLEA_TRIAL_ID, "MS-0002")
        assert ms.variance_days > 0


# ===========================================================================
# Section 7: Trend detection
# ===========================================================================


class TestTrendDetection:
    """Test enrollment trend detection."""

    def test_trend_detection_eylea(self, svc: EnrollmentForecastingService):
        """Should detect trend for EYLEA."""
        trend = svc.detect_trend(EYLEA_TRIAL_ID)
        assert trend is not None
        assert trend.trial_id == EYLEA_TRIAL_ID
        assert trend.trend in list(EnrollmentTrend)

    def test_trend_detection_description(self, svc: EnrollmentForecastingService):
        """Trend should have a human-readable description."""
        trend = svc.detect_trend(EYLEA_TRIAL_ID)
        assert len(trend.description) > 0

    def test_trend_detection_rates(self, svc: EnrollmentForecastingService):
        """Trend should report current and prior rates."""
        trend = svc.detect_trend(EYLEA_TRIAL_ID)
        assert trend.current_rate >= 0
        assert trend.prior_rate >= 0

    def test_trend_detection_not_found(self, svc: EnrollmentForecastingService):
        """Trend for non-existent trial returns None."""
        result = svc.detect_trend("non-existent")
        assert result is None

    def test_trend_updates_forecast(self, svc: EnrollmentForecastingService):
        """Detecting trend should update forecast's trend field."""
        trend = svc.detect_trend(EYLEA_TRIAL_ID)
        fc = svc.get_forecast(EYLEA_TRIAL_ID)
        assert fc.trend == trend.trend

    def test_trend_rate_change_pct(self, svc: EnrollmentForecastingService):
        """Rate change percentage should be a number."""
        trend = svc.detect_trend(EYLEA_TRIAL_ID)
        assert isinstance(trend.rate_change_pct, float)


# ===========================================================================
# Section 8: Risk scoring
# ===========================================================================


class TestRiskScoring:
    """Test enrollment risk scoring."""

    def test_risk_assessment_eylea(self, svc: EnrollmentForecastingService):
        """Should assess risk for EYLEA."""
        risk = svc.assess_risk(EYLEA_TRIAL_ID)
        assert risk is not None
        assert risk.trial_id == EYLEA_TRIAL_ID
        assert 0 <= risk.risk_score <= 100

    def test_risk_overall_level(self, svc: EnrollmentForecastingService):
        """Risk should have an overall level."""
        risk = svc.assess_risk(EYLEA_TRIAL_ID)
        assert risk.overall_risk in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_risk_has_recommendations(self, svc: EnrollmentForecastingService):
        """Risk assessment should include recommendations."""
        risk = svc.assess_risk(EYLEA_TRIAL_ID)
        assert len(risk.recommendations) > 0

    def test_risk_libtayo_higher_than_dupixent(self, svc: EnrollmentForecastingService):
        """Libtayo (higher screen failures, decelerating) should have higher risk than Dupixent."""
        risk_lib = svc.assess_risk(LIBTAYO_TRIAL_ID)
        risk_dup = svc.assess_risk(DUPIXENT_TRIAL_ID)
        assert risk_lib.risk_score > risk_dup.risk_score

    def test_risk_not_found(self, svc: EnrollmentForecastingService):
        """Risk for non-existent trial returns None."""
        result = svc.assess_risk("non-existent")
        assert result is None

    def test_risk_updates_forecast_score(self, svc: EnrollmentForecastingService):
        """Risk assessment should update forecast risk score."""
        risk = svc.assess_risk(EYLEA_TRIAL_ID)
        fc = svc.get_forecast(EYLEA_TRIAL_ID)
        assert fc.risk_score == risk.risk_score

    def test_risk_factors_list(self, svc: EnrollmentForecastingService):
        """Risk factors should be a list of dicts with correct keys."""
        risk = svc.assess_risk(LIBTAYO_TRIAL_ID)
        for factor in risk.risk_factors:
            assert "factor" in factor
            assert "severity" in factor
            assert "description" in factor

    def test_risk_libtayo_has_screen_failure_risk(self, svc: EnrollmentForecastingService):
        """Libtayo should flag high screen failure rate."""
        risk = svc.assess_risk(LIBTAYO_TRIAL_ID)
        factors = [f["factor"] for f in risk.risk_factors]
        assert RiskFactor.HIGH_SCREEN_FAILURE.value in factors


# ===========================================================================
# Section 9: Aggregate metrics
# ===========================================================================


class TestMetrics:
    """Test aggregate metrics computation."""

    def test_metrics_total_trials(self, svc: EnrollmentForecastingService):
        """Metrics should report 3 total trials."""
        metrics = svc.get_metrics()
        assert metrics.total_trials == 3

    def test_metrics_total_target(self, svc: EnrollmentForecastingService):
        """Total target enrollment: 240 + 180 + 120 = 540."""
        metrics = svc.get_metrics()
        assert metrics.total_target_enrollment == 540

    def test_metrics_total_current(self, svc: EnrollmentForecastingService):
        """Total current enrollment: 87 + 134 + 23 = 244."""
        metrics = svc.get_metrics()
        assert metrics.total_current_enrollment == 244

    def test_metrics_overall_pct(self, svc: EnrollmentForecastingService):
        """Overall enrollment percentage should be 244/540 * 100."""
        metrics = svc.get_metrics()
        expected = round(244 / 540 * 100, 1)
        assert metrics.overall_enrollment_pct == expected

    def test_metrics_total_sites(self, svc: EnrollmentForecastingService):
        """Total sites: 15 + 12 + 8 = 35."""
        metrics = svc.get_metrics()
        assert metrics.total_sites == 35

    def test_metrics_avg_risk_score(self, svc: EnrollmentForecastingService):
        """Average risk score should be (35 + 15 + 55) / 3."""
        metrics = svc.get_metrics()
        expected = round((35.0 + 15.0 + 55.0) / 3, 1)
        assert metrics.avg_risk_score == expected

    def test_metrics_avg_enrollment_rate(self, svc: EnrollmentForecastingService):
        """Average enrollment rate should be positive."""
        metrics = svc.get_metrics()
        assert metrics.avg_enrollment_rate > 0

    def test_metrics_screen_failure_rate_bounded(self, svc: EnrollmentForecastingService):
        """Average screen failure rate should be between 0 and 1."""
        metrics = svc.get_metrics()
        assert 0 <= metrics.avg_screen_failure_rate <= 1.0

    def test_metrics_trial_categories_sum(self, svc: EnrollmentForecastingService):
        """On track + at risk + behind should equal total trials."""
        metrics = svc.get_metrics()
        assert metrics.trials_on_track + metrics.trials_at_risk + metrics.trials_behind == 3


# ===========================================================================
# Section 10: Data point management
# ===========================================================================


class TestDataPoints:
    """Test enrollment data point management."""

    def test_get_data_points(self, svc: EnrollmentForecastingService):
        """Should get data points for a trial."""
        dp = svc.get_data_points(EYLEA_TRIAL_ID)
        assert dp is not None
        assert len(dp) > 0

    def test_add_data_point(self, svc: EnrollmentForecastingService):
        """Should add a new data point."""
        before = len(svc.get_data_points(EYLEA_TRIAL_ID))
        req = DataPointCreateRequest(
            date=date.today(),
            new_enrolled=3,
            screened=5,
            screen_failures=1,
            dropouts=0,
        )
        dp = svc.add_data_point(EYLEA_TRIAL_ID, req)
        assert dp is not None
        assert dp.new_enrolled == 3
        after = len(svc.get_data_points(EYLEA_TRIAL_ID))
        assert after == before + 1

    def test_add_data_point_updates_cumulative(self, svc: EnrollmentForecastingService):
        """Adding data point should update cumulative count."""
        last = svc.get_data_points(EYLEA_TRIAL_ID)[-1]
        req = DataPointCreateRequest(
            date=date.today(),
            new_enrolled=5,
        )
        dp = svc.add_data_point(EYLEA_TRIAL_ID, req)
        assert dp.cumulative_enrolled == last.cumulative_enrolled + 5

    def test_add_data_point_updates_forecast_enrollment(self, svc: EnrollmentForecastingService):
        """Adding data point should update forecast current enrollment."""
        req = DataPointCreateRequest(
            date=date.today(),
            new_enrolled=5,
        )
        svc.add_data_point(EYLEA_TRIAL_ID, req)
        fc = svc.get_forecast(EYLEA_TRIAL_ID)
        assert fc.current_enrollment == 87 + 5

    def test_add_data_point_not_found(self, svc: EnrollmentForecastingService):
        """Adding data point to non-existent trial returns None."""
        req = DataPointCreateRequest(
            date=date.today(),
            new_enrolled=1,
        )
        dp = svc.add_data_point("non-existent", req)
        assert dp is None

    def test_get_data_points_not_found(self, svc: EnrollmentForecastingService):
        """Getting data points for non-existent trial returns None."""
        dp = svc.get_data_points("non-existent")
        assert dp is None

    def test_data_point_with_site_id(self, svc: EnrollmentForecastingService):
        """Should accept site-level data point."""
        req = DataPointCreateRequest(
            date=date.today(),
            new_enrolled=2,
            site_id="SITE-101",
        )
        dp = svc.add_data_point(EYLEA_TRIAL_ID, req)
        assert dp.site_id == "SITE-101"


# ===========================================================================
# Section 11: Service stats
# ===========================================================================


class TestServiceStats:
    """Test service statistics."""

    def test_get_stats(self, svc: EnrollmentForecastingService):
        """Should return service stats."""
        stats = svc.get_stats()
        assert stats["total_forecasts"] == 3
        assert stats["total_data_points"] > 0
        assert len(stats["trial_ids"]) == 3


# ===========================================================================
# Section 12: API integration tests
# ===========================================================================


@pytest.mark.anyio
class TestAPIEndpoints:
    """Test all API endpoints via HTTP client."""

    async def test_api_list_forecasts(self):
        """GET /forecasts should return all forecasts."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"{API_PREFIX}/forecasts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    async def test_api_get_forecast(self):
        """GET /forecasts/{trial_id} should return a forecast."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"{API_PREFIX}/forecasts/{EYLEA_TRIAL_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL_ID
        assert data["target_enrollment"] == 240

    async def test_api_get_forecast_not_found(self):
        """GET /forecasts/{trial_id} should return 404 for unknown trial."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"{API_PREFIX}/forecasts/non-existent")
        assert resp.status_code == 404

    async def test_api_generate_forecast(self):
        """POST /forecasts/{trial_id}/generate should generate a forecast."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                f"{API_PREFIX}/forecasts/{EYLEA_TRIAL_ID}/generate",
                json={"method": "MONTE_CARLO"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL_ID
        assert data["method"] == "MONTE_CARLO"

    async def test_api_generate_forecast_not_found(self):
        """POST /forecasts/{trial_id}/generate should return 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(f"{API_PREFIX}/forecasts/non-existent/generate")
        assert resp.status_code == 404

    async def test_api_monte_carlo(self):
        """GET /forecasts/{trial_id}/monte-carlo should return MC results."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(
                f"{API_PREFIX}/forecasts/{EYLEA_TRIAL_ID}/monte-carlo",
                params={"simulations": 200},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["simulations_run"] == 200

    async def test_api_monte_carlo_not_found(self):
        """GET /forecasts/{trial_id}/monte-carlo should return 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"{API_PREFIX}/forecasts/non-existent/monte-carlo")
        assert resp.status_code == 404

    async def test_api_scenarios(self):
        """GET /forecasts/{trial_id}/scenarios should return scenarios."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"{API_PREFIX}/forecasts/{EYLEA_TRIAL_ID}/scenarios")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3

    async def test_api_scenarios_not_found(self):
        """GET /forecasts/{trial_id}/scenarios should return 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"{API_PREFIX}/forecasts/non-existent/scenarios")
        assert resp.status_code == 404

    async def test_api_sites(self):
        """GET /forecasts/{trial_id}/sites should return site rates."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"{API_PREFIX}/forecasts/{EYLEA_TRIAL_ID}/sites")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 15

    async def test_api_sites_not_found(self):
        """GET /forecasts/{trial_id}/sites should return 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"{API_PREFIX}/forecasts/non-existent/sites")
        assert resp.status_code == 404

    async def test_api_milestones(self):
        """GET /forecasts/{trial_id}/milestones should return milestones."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"{API_PREFIX}/forecasts/{EYLEA_TRIAL_ID}/milestones")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5

    async def test_api_add_milestone(self):
        """POST /forecasts/{trial_id}/milestones should add a milestone."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                f"{API_PREFIX}/forecasts/{EYLEA_TRIAL_ID}/milestones",
                json={
                    "milestone_name": "Safety Review",
                    "target_count": 100,
                    "target_date": str(date.today() + timedelta(days=60)),
                },
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["milestone_name"] == "Safety Review"

    async def test_api_add_milestone_not_found(self):
        """POST /forecasts/{trial_id}/milestones should return 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                f"{API_PREFIX}/forecasts/non-existent/milestones",
                json={
                    "milestone_name": "Test",
                    "target_count": 10,
                    "target_date": str(date.today()),
                },
            )
        assert resp.status_code == 404

    async def test_api_update_milestone(self):
        """PUT /forecasts/{trial_id}/milestones/{id} should update."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.put(
                f"{API_PREFIX}/forecasts/{EYLEA_TRIAL_ID}/milestones/MS-0003",
                json={"status": "ACHIEVED", "actual_count": 122},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ACHIEVED"
        assert data["actual_count"] == 122

    async def test_api_update_milestone_not_found(self):
        """PUT /forecasts/{trial_id}/milestones/{id} should return 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.put(
                f"{API_PREFIX}/forecasts/{EYLEA_TRIAL_ID}/milestones/MS-9999",
                json={"status": "ACHIEVED"},
            )
        assert resp.status_code == 404

    async def test_api_trend(self):
        """GET /forecasts/{trial_id}/trend should return trend analysis."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"{API_PREFIX}/forecasts/{EYLEA_TRIAL_ID}/trend")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL_ID
        assert "trend" in data

    async def test_api_trend_not_found(self):
        """GET /forecasts/{trial_id}/trend should return 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"{API_PREFIX}/forecasts/non-existent/trend")
        assert resp.status_code == 404

    async def test_api_risk(self):
        """GET /forecasts/{trial_id}/risk should return risk assessment."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"{API_PREFIX}/forecasts/{EYLEA_TRIAL_ID}/risk")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL_ID
        assert "risk_score" in data

    async def test_api_risk_not_found(self):
        """GET /forecasts/{trial_id}/risk should return 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"{API_PREFIX}/forecasts/non-existent/risk")
        assert resp.status_code == 404

    async def test_api_data_points(self):
        """GET /forecasts/{trial_id}/data-points should return data points."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"{API_PREFIX}/forecasts/{EYLEA_TRIAL_ID}/data-points")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 30

    async def test_api_data_points_not_found(self):
        """GET /forecasts/{trial_id}/data-points should return 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"{API_PREFIX}/forecasts/non-existent/data-points")
        assert resp.status_code == 404

    async def test_api_add_data_point(self):
        """POST /forecasts/{trial_id}/data-points should add a data point."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                f"{API_PREFIX}/forecasts/{EYLEA_TRIAL_ID}/data-points",
                json={
                    "date": str(date.today()),
                    "new_enrolled": 4,
                    "screened": 6,
                    "screen_failures": 1,
                    "dropouts": 0,
                },
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["new_enrolled"] == 4

    async def test_api_add_data_point_not_found(self):
        """POST /forecasts/{trial_id}/data-points should return 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post(
                f"{API_PREFIX}/forecasts/non-existent/data-points",
                json={
                    "date": str(date.today()),
                    "new_enrolled": 1,
                },
            )
        assert resp.status_code == 404

    async def test_api_metrics(self):
        """GET /metrics should return aggregate metrics."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_trials"] == 3
        assert data["total_target_enrollment"] == 540
        assert data["total_current_enrollment"] == 244
        assert data["total_sites"] == 35


# ===========================================================================
# Section 13: Error handling and edge cases
# ===========================================================================


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_get_forecast_none_for_missing(self, svc: EnrollmentForecastingService):
        """get_forecast should return None for missing trial."""
        assert svc.get_forecast("missing-trial") is None

    def test_get_milestones_none_for_missing(self, svc: EnrollmentForecastingService):
        """get_milestones should return None for missing trial."""
        assert svc.get_milestones("missing") is None

    def test_get_site_rates_none_for_missing(self, svc: EnrollmentForecastingService):
        """get_site_rates should return None for missing trial."""
        assert svc.get_site_rates("missing") is None

    def test_detect_trend_none_for_missing(self, svc: EnrollmentForecastingService):
        """detect_trend should return None for missing trial."""
        assert svc.detect_trend("missing") is None

    def test_assess_risk_none_for_missing(self, svc: EnrollmentForecastingService):
        """assess_risk should return None for missing trial."""
        assert svc.assess_risk("missing") is None

    def test_run_monte_carlo_none_for_missing(self, svc: EnrollmentForecastingService):
        """run_monte_carlo should return None for missing trial."""
        assert svc.run_monte_carlo("missing") is None

    def test_get_scenarios_none_for_missing(self, svc: EnrollmentForecastingService):
        """get_scenarios should return None for missing trial."""
        assert svc.get_scenarios("missing") is None

    def test_get_data_points_none_for_missing(self, svc: EnrollmentForecastingService):
        """get_data_points should return None for missing trial."""
        assert svc.get_data_points("missing") is None

    def test_add_data_point_none_for_missing(self, svc: EnrollmentForecastingService):
        """add_data_point should return None for missing trial."""
        req = DataPointCreateRequest(date=date.today(), new_enrolled=1)
        assert svc.add_data_point("missing", req) is None

    def test_reset_service_fresh_data(self):
        """Reset should produce fresh service with seed data."""
        svc = reset_enrollment_forecasting_service()
        forecasts = svc.list_forecasts()
        assert len(forecasts) == 3

    def test_singleton_returns_same_instance(self):
        """get_enrollment_forecasting_service should return singleton."""
        s1 = get_enrollment_forecasting_service()
        s2 = get_enrollment_forecasting_service()
        assert s1 is s2
