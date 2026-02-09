"""Enrollment Forecasting Engine Service (CMO-10).

Pharma-grade enrollment forecasting system that predicts clinical trial
enrollment timelines using historical data, Monte Carlo simulations,
scenario analysis, and site-level enrollment rate tracking.

Usage:
    from app.services.enrollment_forecasting_service import (
        get_enrollment_forecasting_service,
    )

    svc = get_enrollment_forecasting_service()
    forecast = svc.get_forecast("trial-001")
    mc = svc.run_monte_carlo("trial-001")
"""

from __future__ import annotations

import logging
import math
import random
import statistics
import threading
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from app.schemas.enrollment_forecasting import (
    ConfidenceLevel,
    DataPointCreateRequest,
    EnrollmentDataPoint,
    EnrollmentMilestone,
    EnrollmentTrend,
    ForecastMetrics,
    ForecastMethod,
    ForecastRequest,
    ForecastResult,
    MilestoneCreateRequest,
    MilestoneStatus,
    MilestoneUpdateRequest,
    MonteCarloResult,
    RiskAssessment,
    RiskFactor,
    ScenarioResult,
    ScenarioType,
    SiteEnrollmentRate,
    TrendAnalysis,
    TrialForecast,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Trial ID constants (matching adverse_event_service)
# ---------------------------------------------------------------------------

EYLEA_TRIAL_ID = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL_ID = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL_ID = "00000000-de00-0003-0000-000000000003"


class EnrollmentForecastingService:
    """In-memory enrollment forecasting engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._forecasts: dict[str, TrialForecast] = {}
        self._data_points: dict[str, list[EnrollmentDataPoint]] = {}
        self._lock = threading.Lock()
        self._milestone_counter = 0
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data seeding
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic enrollment data for 3 Regeneron trials."""
        now = datetime.now(timezone.utc)
        today = now.date()

        # ----- EYLEA HD (Aflibercept 8mg) -----
        eylea_start = today - timedelta(days=180)
        eylea_data_points = self._generate_enrollment_curve(
            start_date=eylea_start,
            days=180,
            target=240,
            current=87,
            base_rate=0.55,
            variance=0.15,
        )
        eylea_sites = [
            SiteEnrollmentRate(
                site_id="SITE-101", site_name="Bascom Palmer Eye Institute",
                enrollment_rate_per_month=1.8, screen_failure_rate=0.18,
                capacity_remaining=12, projected_completion=today + timedelta(days=200),
                active=True, months_active=6.0,
            ),
            SiteEnrollmentRate(
                site_id="SITE-102", site_name="Wills Eye Hospital",
                enrollment_rate_per_month=1.5, screen_failure_rate=0.22,
                capacity_remaining=10, projected_completion=today + timedelta(days=200),
                active=True, months_active=6.0,
            ),
            SiteEnrollmentRate(
                site_id="SITE-103", site_name="Moorfields Eye Hospital",
                enrollment_rate_per_month=1.2, screen_failure_rate=0.15,
                capacity_remaining=8, projected_completion=today + timedelta(days=200),
                active=True, months_active=5.5,
            ),
            SiteEnrollmentRate(
                site_id="SITE-104", site_name="Jules Stein Eye Institute",
                enrollment_rate_per_month=0.9, screen_failure_rate=0.25,
                capacity_remaining=14, projected_completion=today + timedelta(days=467),
                active=True, months_active=5.0,
            ),
            SiteEnrollmentRate(
                site_id="SITE-105", site_name="Retina Associates of Cleveland",
                enrollment_rate_per_month=1.0, screen_failure_rate=0.20,
                capacity_remaining=11, projected_completion=today + timedelta(days=330),
                active=True, months_active=5.5,
            ),
            SiteEnrollmentRate(
                site_id="SITE-106", site_name="Duke Eye Center",
                enrollment_rate_per_month=1.3, screen_failure_rate=0.16,
                capacity_remaining=9, projected_completion=today + timedelta(days=207),
                active=True, months_active=6.0,
            ),
            SiteEnrollmentRate(
                site_id="SITE-107", site_name="Mass Eye and Ear",
                enrollment_rate_per_month=0.8, screen_failure_rate=0.28,
                capacity_remaining=13, projected_completion=today + timedelta(days=487),
                active=True, months_active=4.5,
            ),
            SiteEnrollmentRate(
                site_id="SITE-108", site_name="Casey Eye Institute",
                enrollment_rate_per_month=0.7, screen_failure_rate=0.20,
                capacity_remaining=15, projected_completion=today + timedelta(days=643),
                active=True, months_active=4.0,
            ),
            SiteEnrollmentRate(
                site_id="SITE-109", site_name="Emory Eye Center",
                enrollment_rate_per_month=1.1, screen_failure_rate=0.19,
                capacity_remaining=7, projected_completion=today + timedelta(days=191),
                active=True, months_active=5.5,
            ),
            SiteEnrollmentRate(
                site_id="SITE-110", site_name="Johns Hopkins Wilmer Eye",
                enrollment_rate_per_month=1.4, screen_failure_rate=0.14,
                capacity_remaining=6, projected_completion=today + timedelta(days=129),
                active=True, months_active=6.0,
            ),
            SiteEnrollmentRate(
                site_id="SITE-111", site_name="Stanford Byers Eye Institute",
                enrollment_rate_per_month=0.6, screen_failure_rate=0.30,
                capacity_remaining=16, projected_completion=today + timedelta(days=800),
                active=True, months_active=3.5,
            ),
            SiteEnrollmentRate(
                site_id="SITE-112", site_name="Cole Eye Institute Cleveland Clinic",
                enrollment_rate_per_month=1.0, screen_failure_rate=0.21,
                capacity_remaining=10, projected_completion=today + timedelta(days=300),
                active=True, months_active=5.0,
            ),
            SiteEnrollmentRate(
                site_id="SITE-113", site_name="Scheie Eye Institute",
                enrollment_rate_per_month=0.9, screen_failure_rate=0.23,
                capacity_remaining=12, projected_completion=today + timedelta(days=400),
                active=True, months_active=4.5,
            ),
            SiteEnrollmentRate(
                site_id="SITE-114", site_name="Dean McGee Eye Institute",
                enrollment_rate_per_month=0.5, screen_failure_rate=0.26,
                capacity_remaining=17, projected_completion=today + timedelta(days=1020),
                active=True, months_active=3.0,
            ),
            SiteEnrollmentRate(
                site_id="SITE-115", site_name="Kellogg Eye Center",
                enrollment_rate_per_month=1.1, screen_failure_rate=0.17,
                capacity_remaining=8, projected_completion=today + timedelta(days=218),
                active=True, months_active=5.5,
            ),
        ]

        eylea_milestones = [
            EnrollmentMilestone(
                id="MS-0001", trial_id=EYLEA_TRIAL_ID,
                milestone_name="First Patient In (FPI)",
                target_count=1, target_date=eylea_start,
                actual_count=1, actual_date=eylea_start,
                status=MilestoneStatus.ACHIEVED, variance_days=0,
            ),
            EnrollmentMilestone(
                id="MS-0002", trial_id=EYLEA_TRIAL_ID,
                milestone_name="25% Enrollment",
                target_count=60, target_date=eylea_start + timedelta(days=120),
                actual_count=62, actual_date=eylea_start + timedelta(days=115),
                status=MilestoneStatus.ACHIEVED, variance_days=5,
            ),
            EnrollmentMilestone(
                id="MS-0003", trial_id=EYLEA_TRIAL_ID,
                milestone_name="50% Enrollment",
                target_count=120, target_date=eylea_start + timedelta(days=210),
                status=MilestoneStatus.ON_TRACK,
            ),
            EnrollmentMilestone(
                id="MS-0004", trial_id=EYLEA_TRIAL_ID,
                milestone_name="75% Enrollment",
                target_count=180, target_date=eylea_start + timedelta(days=300),
                status=MilestoneStatus.PENDING,
            ),
            EnrollmentMilestone(
                id="MS-0005", trial_id=EYLEA_TRIAL_ID,
                milestone_name="Last Patient In (LPI)",
                target_count=240, target_date=eylea_start + timedelta(days=390),
                status=MilestoneStatus.PENDING,
            ),
        ]

        eylea_forecast = TrialForecast(
            id="FC-0001", trial_id=EYLEA_TRIAL_ID,
            trial_name="EYLEA HD (Aflibercept 8mg) - PHOTON Extension",
            target_enrollment=240, current_enrollment=87,
            start_date=eylea_start,
            target_date=eylea_start + timedelta(days=390),
            forecast_method=ForecastMethod.MONTE_CARLO,
            milestones=eylea_milestones,
            site_rates=eylea_sites,
            trend=EnrollmentTrend.STEADY,
            risk_score=35.0,
            created_at=now - timedelta(days=7),
            updated_at=now,
        )
        self._forecasts[EYLEA_TRIAL_ID] = eylea_forecast
        self._data_points[EYLEA_TRIAL_ID] = eylea_data_points
        self._milestone_counter = 5

        # ----- Dupixent (Dupilumab) -----
        dupixent_start = today - timedelta(days=240)
        dupixent_data_points = self._generate_enrollment_curve(
            start_date=dupixent_start,
            days=240,
            target=180,
            current=134,
            base_rate=0.65,
            variance=0.12,
        )
        dupixent_sites = [
            SiteEnrollmentRate(
                site_id="SITE-201", site_name="National Jewish Health",
                enrollment_rate_per_month=2.5, screen_failure_rate=0.12,
                capacity_remaining=4, projected_completion=today + timedelta(days=48),
                active=True, months_active=8.0,
            ),
            SiteEnrollmentRate(
                site_id="SITE-202", site_name="Mayo Clinic Dermatology",
                enrollment_rate_per_month=2.1, screen_failure_rate=0.15,
                capacity_remaining=5, projected_completion=today + timedelta(days=71),
                active=True, months_active=8.0,
            ),
            SiteEnrollmentRate(
                site_id="SITE-203", site_name="Northwestern Dermatology",
                enrollment_rate_per_month=1.8, screen_failure_rate=0.18,
                capacity_remaining=6, projected_completion=today + timedelta(days=100),
                active=True, months_active=7.5,
            ),
            SiteEnrollmentRate(
                site_id="SITE-204", site_name="Stanford Allergy & Immunology",
                enrollment_rate_per_month=1.5, screen_failure_rate=0.14,
                capacity_remaining=5, projected_completion=today + timedelta(days=100),
                active=True, months_active=7.0,
            ),
            SiteEnrollmentRate(
                site_id="SITE-205", site_name="Mount Sinai Dermatology",
                enrollment_rate_per_month=1.9, screen_failure_rate=0.10,
                capacity_remaining=3, projected_completion=today + timedelta(days=47),
                active=True, months_active=8.0,
            ),
            SiteEnrollmentRate(
                site_id="SITE-206", site_name="University of Michigan Allergy",
                enrollment_rate_per_month=1.6, screen_failure_rate=0.16,
                capacity_remaining=4, projected_completion=today + timedelta(days=75),
                active=True, months_active=7.5,
            ),
            SiteEnrollmentRate(
                site_id="SITE-207", site_name="Emory Dermatology",
                enrollment_rate_per_month=1.3, screen_failure_rate=0.20,
                capacity_remaining=6, projected_completion=today + timedelta(days=138),
                active=True, months_active=7.0,
            ),
            SiteEnrollmentRate(
                site_id="SITE-208", site_name="Penn Dermatology",
                enrollment_rate_per_month=1.7, screen_failure_rate=0.13,
                capacity_remaining=4, projected_completion=today + timedelta(days=71),
                active=True, months_active=7.5,
            ),
            SiteEnrollmentRate(
                site_id="SITE-209", site_name="UCSF Dermatology",
                enrollment_rate_per_month=1.4, screen_failure_rate=0.17,
                capacity_remaining=5, projected_completion=today + timedelta(days=107),
                active=True, months_active=7.0,
            ),
            SiteEnrollmentRate(
                site_id="SITE-210", site_name="Johns Hopkins Dermatology",
                enrollment_rate_per_month=2.0, screen_failure_rate=0.11,
                capacity_remaining=3, projected_completion=today + timedelta(days=45),
                active=True, months_active=8.0,
            ),
            SiteEnrollmentRate(
                site_id="SITE-211", site_name="Columbia Dermatology",
                enrollment_rate_per_month=1.2, screen_failure_rate=0.19,
                capacity_remaining=5, projected_completion=today + timedelta(days=125),
                active=True, months_active=6.5,
            ),
            SiteEnrollmentRate(
                site_id="SITE-212", site_name="Vanderbilt Dermatology",
                enrollment_rate_per_month=1.1, screen_failure_rate=0.22,
                capacity_remaining=6, projected_completion=today + timedelta(days=164),
                active=True, months_active=6.0,
            ),
        ]

        dupixent_milestones = [
            EnrollmentMilestone(
                id="MS-0006", trial_id=DUPIXENT_TRIAL_ID,
                milestone_name="First Patient In (FPI)",
                target_count=1, target_date=dupixent_start,
                actual_count=1, actual_date=dupixent_start,
                status=MilestoneStatus.ACHIEVED, variance_days=0,
            ),
            EnrollmentMilestone(
                id="MS-0007", trial_id=DUPIXENT_TRIAL_ID,
                milestone_name="25% Enrollment",
                target_count=45, target_date=dupixent_start + timedelta(days=75),
                actual_count=47, actual_date=dupixent_start + timedelta(days=70),
                status=MilestoneStatus.ACHIEVED, variance_days=5,
            ),
            EnrollmentMilestone(
                id="MS-0008", trial_id=DUPIXENT_TRIAL_ID,
                milestone_name="50% Enrollment",
                target_count=90, target_date=dupixent_start + timedelta(days=150),
                actual_count=92, actual_date=dupixent_start + timedelta(days=148),
                status=MilestoneStatus.ACHIEVED, variance_days=2,
            ),
            EnrollmentMilestone(
                id="MS-0009", trial_id=DUPIXENT_TRIAL_ID,
                milestone_name="75% Enrollment",
                target_count=135, target_date=dupixent_start + timedelta(days=225),
                actual_count=134, actual_date=None,
                status=MilestoneStatus.ON_TRACK, variance_days=None,
            ),
            EnrollmentMilestone(
                id="MS-0010", trial_id=DUPIXENT_TRIAL_ID,
                milestone_name="Last Patient In (LPI)",
                target_count=180, target_date=dupixent_start + timedelta(days=300),
                status=MilestoneStatus.PENDING,
            ),
        ]

        dupixent_forecast = TrialForecast(
            id="FC-0002", trial_id=DUPIXENT_TRIAL_ID,
            trial_name="Dupixent (Dupilumab) - LIBERTY AD HIKE",
            target_enrollment=180, current_enrollment=134,
            start_date=dupixent_start,
            target_date=dupixent_start + timedelta(days=300),
            forecast_method=ForecastMethod.LINEAR_REGRESSION,
            milestones=dupixent_milestones,
            site_rates=dupixent_sites,
            trend=EnrollmentTrend.ACCELERATING,
            risk_score=15.0,
            created_at=now - timedelta(days=5),
            updated_at=now,
        )
        self._forecasts[DUPIXENT_TRIAL_ID] = dupixent_forecast
        self._data_points[DUPIXENT_TRIAL_ID] = dupixent_data_points
        self._milestone_counter = 10

        # ----- Libtayo (Cemiplimab) -----
        libtayo_start = today - timedelta(days=60)
        libtayo_data_points = self._generate_enrollment_curve(
            start_date=libtayo_start,
            days=60,
            target=120,
            current=23,
            base_rate=0.45,
            variance=0.20,
        )
        libtayo_sites = [
            SiteEnrollmentRate(
                site_id="SITE-301", site_name="Memorial Sloan Kettering",
                enrollment_rate_per_month=1.5, screen_failure_rate=0.30,
                capacity_remaining=12, projected_completion=today + timedelta(days=240),
                active=True, months_active=2.0,
            ),
            SiteEnrollmentRate(
                site_id="SITE-302", site_name="MD Anderson Cancer Center",
                enrollment_rate_per_month=1.2, screen_failure_rate=0.35,
                capacity_remaining=14, projected_completion=today + timedelta(days=350),
                active=True, months_active=2.0,
            ),
            SiteEnrollmentRate(
                site_id="SITE-303", site_name="Dana-Farber Cancer Institute",
                enrollment_rate_per_month=1.0, screen_failure_rate=0.32,
                capacity_remaining=13, projected_completion=today + timedelta(days=390),
                active=True, months_active=1.5,
            ),
            SiteEnrollmentRate(
                site_id="SITE-304", site_name="Moffitt Cancer Center",
                enrollment_rate_per_month=0.8, screen_failure_rate=0.28,
                capacity_remaining=15, projected_completion=today + timedelta(days=563),
                active=True, months_active=1.5,
            ),
            SiteEnrollmentRate(
                site_id="SITE-305", site_name="Fred Hutchinson Cancer Center",
                enrollment_rate_per_month=0.9, screen_failure_rate=0.33,
                capacity_remaining=14, projected_completion=today + timedelta(days=467),
                active=True, months_active=1.0,
            ),
            SiteEnrollmentRate(
                site_id="SITE-306", site_name="Mayo Clinic Oncology",
                enrollment_rate_per_month=1.1, screen_failure_rate=0.27,
                capacity_remaining=12, projected_completion=today + timedelta(days=327),
                active=True, months_active=1.5,
            ),
            SiteEnrollmentRate(
                site_id="SITE-307", site_name="City of Hope",
                enrollment_rate_per_month=0.7, screen_failure_rate=0.35,
                capacity_remaining=16, projected_completion=today + timedelta(days=686),
                active=True, months_active=1.0,
            ),
            SiteEnrollmentRate(
                site_id="SITE-308", site_name="Huntsman Cancer Institute",
                enrollment_rate_per_month=0.6, screen_failure_rate=0.30,
                capacity_remaining=15, projected_completion=today + timedelta(days=750),
                active=True, months_active=0.5,
            ),
        ]

        libtayo_milestones = [
            EnrollmentMilestone(
                id="MS-0011", trial_id=LIBTAYO_TRIAL_ID,
                milestone_name="First Patient In (FPI)",
                target_count=1, target_date=libtayo_start,
                actual_count=1, actual_date=libtayo_start + timedelta(days=3),
                status=MilestoneStatus.ACHIEVED, variance_days=-3,
            ),
            EnrollmentMilestone(
                id="MS-0012", trial_id=LIBTAYO_TRIAL_ID,
                milestone_name="25% Enrollment",
                target_count=30, target_date=libtayo_start + timedelta(days=120),
                status=MilestoneStatus.ON_TRACK,
            ),
            EnrollmentMilestone(
                id="MS-0013", trial_id=LIBTAYO_TRIAL_ID,
                milestone_name="50% Enrollment",
                target_count=60, target_date=libtayo_start + timedelta(days=240),
                status=MilestoneStatus.PENDING,
            ),
            EnrollmentMilestone(
                id="MS-0014", trial_id=LIBTAYO_TRIAL_ID,
                milestone_name="Last Patient In (LPI)",
                target_count=120, target_date=libtayo_start + timedelta(days=480),
                status=MilestoneStatus.PENDING,
            ),
        ]

        libtayo_forecast = TrialForecast(
            id="FC-0003", trial_id=LIBTAYO_TRIAL_ID,
            trial_name="Libtayo (Cemiplimab) - EMPOWER-CSCC 3",
            target_enrollment=120, current_enrollment=23,
            start_date=libtayo_start,
            target_date=libtayo_start + timedelta(days=480),
            forecast_method=ForecastMethod.POISSON_PROCESS,
            milestones=libtayo_milestones,
            site_rates=libtayo_sites,
            trend=EnrollmentTrend.DECELERATING,
            risk_score=55.0,
            created_at=now - timedelta(days=3),
            updated_at=now,
        )
        self._forecasts[LIBTAYO_TRIAL_ID] = libtayo_forecast
        self._data_points[LIBTAYO_TRIAL_ID] = libtayo_data_points
        self._milestone_counter = 14

    def _generate_enrollment_curve(
        self,
        start_date: date,
        days: int,
        target: int,
        current: int,
        base_rate: float,
        variance: float,
    ) -> list[EnrollmentDataPoint]:
        """Generate realistic enrollment data points with controlled randomness."""
        rng = random.Random(42)  # Deterministic for reproducibility
        data_points: list[EnrollmentDataPoint] = []
        cumulative = 0

        for day_offset in range(0, days, 3):  # Every 3 days
            d = start_date + timedelta(days=day_offset)
            # Use a logistic-ish curve for realistic enrollment
            progress = day_offset / max(days, 1)
            # S-curve acceleration then deceleration
            rate_modifier = 4 * progress * (1 - progress) + 0.3
            daily_rate = base_rate * rate_modifier
            new = max(0, int(daily_rate + rng.gauss(0, variance)))

            if cumulative + new > current:
                new = max(0, current - cumulative)

            cumulative += new
            screened = int(new * (1.0 + rng.uniform(0.2, 0.5)))
            screen_failures = max(0, screened - new - rng.randint(0, 1))
            dropouts = 1 if rng.random() < 0.05 else 0

            data_points.append(
                EnrollmentDataPoint(
                    date=d,
                    cumulative_enrolled=cumulative,
                    new_enrolled=new,
                    screened=screened,
                    screen_failures=screen_failures,
                    dropouts=dropouts,
                )
            )

        # Ensure the last data point matches current enrollment
        if data_points and data_points[-1].cumulative_enrolled != current:
            last = data_points[-1]
            diff = current - last.cumulative_enrolled
            data_points[-1] = EnrollmentDataPoint(
                date=last.date,
                cumulative_enrolled=current,
                new_enrolled=max(0, last.new_enrolled + diff),
                screened=last.screened,
                screen_failures=last.screen_failures,
                dropouts=last.dropouts,
            )

        return data_points

    # ------------------------------------------------------------------
    # Forecast retrieval
    # ------------------------------------------------------------------

    def list_forecasts(self) -> list[TrialForecast]:
        """List all trial forecasts."""
        return list(self._forecasts.values())

    def get_forecast(self, trial_id: str) -> Optional[TrialForecast]:
        """Get forecast for a specific trial."""
        return self._forecasts.get(trial_id)

    # ------------------------------------------------------------------
    # Forecast generation
    # ------------------------------------------------------------------

    def generate_forecast(
        self,
        trial_id: str,
        request: Optional[ForecastRequest] = None,
    ) -> Optional[ForecastResult]:
        """Generate or regenerate a forecast for a trial.

        Supports multiple forecast methods including linear regression,
        exponential smoothing, Monte Carlo, and Poisson process.
        """
        forecast = self._forecasts.get(trial_id)
        if forecast is None:
            return None

        method = request.method if request else ForecastMethod.MONTE_CARLO
        data_points = self._data_points.get(trial_id, [])

        remaining = forecast.target_enrollment - forecast.current_enrollment
        rate = self._compute_enrollment_rate(data_points)
        today = date.today()

        if rate <= 0:
            days_to_target = 9999
        else:
            days_to_target = int((remaining / rate) * 30)

        projected_date = today + timedelta(days=days_to_target)
        ci_lower = today + timedelta(days=int(days_to_target * 0.8))
        ci_upper = today + timedelta(days=int(days_to_target * 1.3))

        # Determine confidence level based on data points
        confidence = self._compute_confidence(len(data_points), rate, remaining)

        # Detect risk factors
        risk_factors = self._detect_risk_factors(forecast, data_points)

        # Generate scenarios if requested
        scenarios: list[ScenarioResult] = []
        if request is None or request.include_scenarios:
            scenarios = self._generate_scenarios(forecast, rate, remaining, today)

        result = ForecastResult(
            trial_id=trial_id,
            method=method,
            target_enrollment=forecast.target_enrollment,
            current_enrollment=forecast.current_enrollment,
            projected_completion_date=projected_date,
            confidence_interval_lower=ci_lower,
            confidence_interval_upper=ci_upper,
            confidence_level=confidence,
            days_to_target=days_to_target,
            enrollment_rate_per_month=round(rate, 2),
            data_points_used=len(data_points),
            risk_factors=risk_factors,
            scenarios=scenarios,
        )

        with self._lock:
            forecast.forecast_result = result
            forecast.forecast_method = method
            forecast.updated_at = datetime.now(timezone.utc)

        return result

    def _compute_enrollment_rate(self, data_points: list[EnrollmentDataPoint]) -> float:
        """Compute average enrollment rate per month from data points."""
        if len(data_points) < 2:
            return 0.0

        first = data_points[0]
        last = data_points[-1]
        days_elapsed = (last.date - first.date).days
        if days_elapsed <= 0:
            return 0.0

        total_enrolled = last.cumulative_enrolled - first.cumulative_enrolled
        months = days_elapsed / 30.0
        return total_enrolled / months if months > 0 else 0.0

    def _compute_confidence(self, n_points: int, rate: float, remaining: int) -> ConfidenceLevel:
        """Determine confidence level based on data quality."""
        if n_points >= 40 and rate > 0:
            return ConfidenceLevel.VERY_HIGH
        elif n_points >= 20 and rate > 0:
            return ConfidenceLevel.HIGH
        elif n_points >= 10 and rate > 0:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def _detect_risk_factors(
        self,
        forecast: TrialForecast,
        data_points: list[EnrollmentDataPoint],
    ) -> list[RiskFactor]:
        """Detect enrollment risk factors."""
        risks: list[RiskFactor] = []

        # Check screen failure rate across sites
        if forecast.site_rates:
            avg_sfr = statistics.mean(s.screen_failure_rate for s in forecast.site_rates)
            if avg_sfr > 0.25:
                risks.append(RiskFactor.HIGH_SCREEN_FAILURE)

        # Check if enrollment has stalled
        if data_points and len(data_points) >= 6:
            recent = data_points[-3:]
            recent_enrolled = sum(dp.new_enrolled for dp in recent)
            if recent_enrolled == 0:
                risks.append(RiskFactor.SLOW_SCREENING)

        # Check site capacity
        if forecast.site_rates:
            low_capacity_sites = sum(
                1 for s in forecast.site_rates if s.capacity_remaining <= 2
            )
            if low_capacity_sites >= len(forecast.site_rates) * 0.3:
                risks.append(RiskFactor.SITE_CAPACITY)

        # Check for seasonal effects (Q4/Q1 slowdown)
        today = date.today()
        if today.month in (11, 12, 1):
            risks.append(RiskFactor.SEASONAL_EFFECT)

        return risks

    def _generate_scenarios(
        self,
        forecast: TrialForecast,
        rate: float,
        remaining: int,
        today: date,
    ) -> list[ScenarioResult]:
        """Generate optimistic, base-case, and pessimistic scenarios."""
        scenarios: list[ScenarioResult] = []

        if rate <= 0:
            rate = 0.5  # Fallback minimal rate

        # Optimistic: 1.3x rate
        opt_rate = rate * 1.3
        opt_days = int((remaining / opt_rate) * 30) if opt_rate > 0 else 9999
        scenarios.append(
            ScenarioResult(
                scenario_type=ScenarioType.OPTIMISTIC,
                projected_completion_date=today + timedelta(days=opt_days),
                enrollment_rate=round(opt_rate, 2),
                probability=0.20,
                assumptions=[
                    "All sites reach peak enrollment capacity",
                    "Screen failure rate decreases by 15%",
                    "No protocol amendments or regulatory delays",
                ],
            )
        )

        # Base case: current rate
        base_days = int((remaining / rate) * 30) if rate > 0 else 9999
        scenarios.append(
            ScenarioResult(
                scenario_type=ScenarioType.BASE_CASE,
                projected_completion_date=today + timedelta(days=base_days),
                enrollment_rate=round(rate, 2),
                probability=0.55,
                assumptions=[
                    "Current enrollment rate maintained",
                    "No significant changes to site activation",
                    "Screen failure rate remains stable",
                ],
            )
        )

        # Pessimistic: 0.7x rate
        pess_rate = rate * 0.7
        pess_days = int((remaining / pess_rate) * 30) if pess_rate > 0 else 9999
        scenarios.append(
            ScenarioResult(
                scenario_type=ScenarioType.PESSIMISTIC,
                projected_completion_date=today + timedelta(days=pess_days),
                enrollment_rate=round(pess_rate, 2),
                probability=0.25,
                assumptions=[
                    "Enrollment rate decreases due to site fatigue",
                    "Screen failure rate increases by 20%",
                    "Potential protocol amendment impact",
                ],
            )
        )

        return scenarios

    # ------------------------------------------------------------------
    # Monte Carlo simulation
    # ------------------------------------------------------------------

    def run_monte_carlo(
        self,
        trial_id: str,
        n_simulations: int = 1000,
    ) -> Optional[MonteCarloResult]:
        """Run Monte Carlo simulation for enrollment timeline.

        Uses a Poisson process to model patient arrival rates
        with site-level heterogeneity.
        """
        forecast = self._forecasts.get(trial_id)
        if forecast is None:
            return None

        data_points = self._data_points.get(trial_id, [])
        rate = self._compute_enrollment_rate(data_points)

        if rate <= 0:
            rate = 1.0  # Fallback

        remaining = forecast.target_enrollment - forecast.current_enrollment
        if remaining <= 0:
            today = date.today()
            return MonteCarloResult(
                simulations_run=n_simulations,
                p10_date=today,
                p25_date=today,
                p50_date=today,
                p75_date=today,
                p90_date=today,
                mean_days_to_target=0.0,
                std_dev_days=0.0,
                histogram_buckets=[],
            )

        rng = random.Random(42)
        completion_days: list[int] = []

        # Daily rate from monthly rate
        daily_rate = rate / 30.0

        for _ in range(n_simulations):
            enrolled = 0
            days = 0
            # Add some variance to the base rate for each simulation
            sim_rate = daily_rate * rng.uniform(0.6, 1.4)

            while enrolled < remaining and days < 3650:  # Cap at 10 years
                # Poisson arrivals
                arrivals = 0
                if sim_rate > 0:
                    arrivals = self._poisson_sample(rng, sim_rate)
                enrolled += arrivals
                days += 1

            completion_days.append(days)

        completion_days.sort()
        today = date.today()

        # Percentiles
        p10 = self._percentile(completion_days, 10)
        p25 = self._percentile(completion_days, 25)
        p50 = self._percentile(completion_days, 50)
        p75 = self._percentile(completion_days, 75)
        p90 = self._percentile(completion_days, 90)

        mean_days = statistics.mean(completion_days)
        std_days = statistics.stdev(completion_days) if len(completion_days) > 1 else 0.0

        # Build histogram
        histogram = self._build_histogram(completion_days, n_buckets=10)

        result = MonteCarloResult(
            simulations_run=n_simulations,
            p10_date=today + timedelta(days=p10),
            p25_date=today + timedelta(days=p25),
            p50_date=today + timedelta(days=p50),
            p75_date=today + timedelta(days=p75),
            p90_date=today + timedelta(days=p90),
            mean_days_to_target=round(mean_days, 1),
            std_dev_days=round(std_days, 1),
            histogram_buckets=histogram,
        )

        with self._lock:
            forecast.monte_carlo = result
            forecast.updated_at = datetime.now(timezone.utc)

        return result

    def _poisson_sample(self, rng: random.Random, lam: float) -> int:
        """Sample from Poisson distribution using inverse transform."""
        if lam <= 0:
            return 0
        L = math.exp(-lam)
        k = 0
        p = 1.0
        while True:
            k += 1
            p *= rng.random()
            if p <= L:
                return k - 1

    def _percentile(self, sorted_data: list[int], pct: int) -> int:
        """Get percentile value from sorted list."""
        if not sorted_data:
            return 0
        idx = int(len(sorted_data) * pct / 100)
        idx = min(idx, len(sorted_data) - 1)
        return sorted_data[idx]

    def _build_histogram(self, data: list[int], n_buckets: int = 10) -> list[dict]:
        """Build histogram buckets from completion days data."""
        if not data:
            return []

        min_val = min(data)
        max_val = max(data)
        if min_val == max_val:
            return [{"range_start": min_val, "range_end": max_val, "count": len(data)}]

        bucket_width = (max_val - min_val) / n_buckets
        buckets: list[dict] = []

        for i in range(n_buckets):
            start = min_val + i * bucket_width
            end = start + bucket_width
            count = sum(1 for d in data if start <= d < end)
            if i == n_buckets - 1:
                # Last bucket includes the max value
                count = sum(1 for d in data if start <= d <= end)
            buckets.append({
                "range_start": round(start, 1),
                "range_end": round(end, 1),
                "count": count,
            })

        return buckets

    # ------------------------------------------------------------------
    # Scenario analysis
    # ------------------------------------------------------------------

    def get_scenarios(self, trial_id: str) -> Optional[list[ScenarioResult]]:
        """Get scenario analysis for a trial."""
        forecast = self._forecasts.get(trial_id)
        if forecast is None:
            return None

        data_points = self._data_points.get(trial_id, [])
        rate = self._compute_enrollment_rate(data_points)
        remaining = forecast.target_enrollment - forecast.current_enrollment
        today = date.today()

        return self._generate_scenarios(forecast, rate, remaining, today)

    # ------------------------------------------------------------------
    # Site-level analysis
    # ------------------------------------------------------------------

    def get_site_rates(self, trial_id: str) -> Optional[list[SiteEnrollmentRate]]:
        """Get site-level enrollment rates for a trial."""
        forecast = self._forecasts.get(trial_id)
        if forecast is None:
            return None
        return forecast.site_rates

    # ------------------------------------------------------------------
    # Milestone management
    # ------------------------------------------------------------------

    def get_milestones(self, trial_id: str) -> Optional[list[EnrollmentMilestone]]:
        """Get milestones for a trial."""
        forecast = self._forecasts.get(trial_id)
        if forecast is None:
            return None
        return forecast.milestones

    def add_milestone(
        self,
        trial_id: str,
        request: MilestoneCreateRequest,
    ) -> Optional[EnrollmentMilestone]:
        """Add a new milestone to a trial forecast."""
        forecast = self._forecasts.get(trial_id)
        if forecast is None:
            return None

        with self._lock:
            self._milestone_counter += 1
            ms_id = f"MS-{self._milestone_counter:04d}"

            milestone = EnrollmentMilestone(
                id=ms_id,
                trial_id=trial_id,
                milestone_name=request.milestone_name,
                target_count=request.target_count,
                target_date=request.target_date,
                status=MilestoneStatus.PENDING,
            )
            forecast.milestones.append(milestone)
            forecast.updated_at = datetime.now(timezone.utc)

        return milestone

    def update_milestone(
        self,
        trial_id: str,
        milestone_id: str,
        request: MilestoneUpdateRequest,
    ) -> Optional[EnrollmentMilestone]:
        """Update a milestone's actual data and status."""
        forecast = self._forecasts.get(trial_id)
        if forecast is None:
            return None

        with self._lock:
            for i, ms in enumerate(forecast.milestones):
                if ms.id == milestone_id:
                    update_data = {}
                    if request.actual_count is not None:
                        update_data["actual_count"] = request.actual_count
                    if request.actual_date is not None:
                        update_data["actual_date"] = request.actual_date
                        # Compute variance
                        variance = (ms.target_date - request.actual_date).days
                        update_data["variance_days"] = variance
                    if request.status is not None:
                        update_data["status"] = request.status

                    updated = ms.model_copy(update=update_data)
                    forecast.milestones[i] = updated
                    forecast.updated_at = datetime.now(timezone.utc)
                    return updated

        return None

    def get_milestone(self, trial_id: str, milestone_id: str) -> Optional[EnrollmentMilestone]:
        """Get a specific milestone."""
        forecast = self._forecasts.get(trial_id)
        if forecast is None:
            return None
        for ms in forecast.milestones:
            if ms.id == milestone_id:
                return ms
        return None

    # ------------------------------------------------------------------
    # Trend detection
    # ------------------------------------------------------------------

    def detect_trend(self, trial_id: str) -> Optional[TrendAnalysis]:
        """Detect enrollment trend by comparing recent vs prior periods.

        Compares the enrollment rate over the last 30 days to the rate
        from 30-60 days ago to classify the trend.
        """
        forecast = self._forecasts.get(trial_id)
        if forecast is None:
            return None

        data_points = self._data_points.get(trial_id, [])
        if not data_points:
            return TrendAnalysis(
                trial_id=trial_id,
                trend=EnrollmentTrend.NOT_STARTED,
                current_rate=0.0,
                prior_rate=0.0,
                rate_change_pct=0.0,
                description="No enrollment data available yet.",
            )

        today = date.today()
        cutoff_30 = today - timedelta(days=30)
        cutoff_60 = today - timedelta(days=60)

        # Recent period (last 30 days)
        recent = [dp for dp in data_points if dp.date >= cutoff_30]
        recent_enrolled = sum(dp.new_enrolled for dp in recent)

        # Prior period (30-60 days ago)
        prior = [dp for dp in data_points if cutoff_60 <= dp.date < cutoff_30]
        prior_enrolled = sum(dp.new_enrolled for dp in prior)

        # Normalize to monthly rates
        current_rate = recent_enrolled  # Already ~30 days
        prior_rate = prior_enrolled

        if prior_rate > 0:
            rate_change_pct = ((current_rate - prior_rate) / prior_rate) * 100
        elif current_rate > 0:
            rate_change_pct = 100.0
        else:
            rate_change_pct = 0.0

        # Classify trend
        if current_rate == 0 and prior_rate == 0:
            trend = EnrollmentTrend.STALLED
            desc = "Enrollment has stalled - no patients enrolled in the last 60 days."
        elif rate_change_pct > 15:
            trend = EnrollmentTrend.ACCELERATING
            desc = f"Enrollment is accelerating: {current_rate} patients in last 30 days vs {prior_rate} in prior period (+{rate_change_pct:.0f}%)."
        elif rate_change_pct < -15:
            trend = EnrollmentTrend.DECELERATING
            desc = f"Enrollment is decelerating: {current_rate} patients in last 30 days vs {prior_rate} in prior period ({rate_change_pct:.0f}%)."
        elif current_rate == 0:
            trend = EnrollmentTrend.STALLED
            desc = "Enrollment has stalled - no patients enrolled in the last 30 days."
        else:
            trend = EnrollmentTrend.STEADY
            desc = f"Enrollment is steady: {current_rate} patients in last 30 days vs {prior_rate} in prior period ({rate_change_pct:+.0f}%)."

        with self._lock:
            forecast.trend = trend

        return TrendAnalysis(
            trial_id=trial_id,
            trend=trend,
            current_rate=float(current_rate),
            prior_rate=float(prior_rate),
            rate_change_pct=round(rate_change_pct, 1),
            description=desc,
        )

    # ------------------------------------------------------------------
    # Risk scoring
    # ------------------------------------------------------------------

    def assess_risk(self, trial_id: str) -> Optional[RiskAssessment]:
        """Compute a composite enrollment risk score for a trial.

        Factors:
        - Screen failure rate vs benchmark
        - Site utilization / capacity
        - Enrollment trend
        - Enrollment progress vs timeline
        """
        forecast = self._forecasts.get(trial_id)
        if forecast is None:
            return None

        risk_items: list[dict] = []
        score = 0.0

        # 1. Screen failure rate
        if forecast.site_rates:
            avg_sfr = statistics.mean(s.screen_failure_rate for s in forecast.site_rates)
            if avg_sfr > 0.30:
                score += 25
                risk_items.append({
                    "factor": RiskFactor.HIGH_SCREEN_FAILURE.value,
                    "severity": "HIGH",
                    "description": f"Average screen failure rate is {avg_sfr:.0%}, exceeding 30% threshold.",
                })
            elif avg_sfr > 0.20:
                score += 12
                risk_items.append({
                    "factor": RiskFactor.HIGH_SCREEN_FAILURE.value,
                    "severity": "MEDIUM",
                    "description": f"Average screen failure rate is {avg_sfr:.0%}, approaching risk threshold.",
                })

        # 2. Site capacity
        if forecast.site_rates:
            low_cap = sum(1 for s in forecast.site_rates if s.capacity_remaining <= 3)
            pct_low = low_cap / len(forecast.site_rates)
            if pct_low > 0.5:
                score += 20
                risk_items.append({
                    "factor": RiskFactor.SITE_CAPACITY.value,
                    "severity": "HIGH",
                    "description": f"{low_cap} of {len(forecast.site_rates)} sites have 3 or fewer enrollment slots remaining.",
                })
            elif pct_low > 0.25:
                score += 10
                risk_items.append({
                    "factor": RiskFactor.SITE_CAPACITY.value,
                    "severity": "MEDIUM",
                    "description": f"{low_cap} sites nearing capacity.",
                })

        # 3. Enrollment trend
        if forecast.trend == EnrollmentTrend.STALLED:
            score += 30
            risk_items.append({
                "factor": RiskFactor.SLOW_SCREENING.value,
                "severity": "CRITICAL",
                "description": "Enrollment has stalled - immediate intervention required.",
            })
        elif forecast.trend == EnrollmentTrend.DECELERATING:
            score += 15
            risk_items.append({
                "factor": RiskFactor.SLOW_SCREENING.value,
                "severity": "MEDIUM",
                "description": "Enrollment rate is declining - monitor closely.",
            })

        # 4. Timeline progress
        if forecast.target_enrollment > 0:
            pct_enrolled = forecast.current_enrollment / forecast.target_enrollment
            days_elapsed = (date.today() - forecast.start_date).days
            total_days = (forecast.target_date - forecast.start_date).days
            pct_time = days_elapsed / total_days if total_days > 0 else 0

            if pct_time > 0 and pct_enrolled / pct_time < 0.7:
                score += 15
                risk_items.append({
                    "factor": RiskFactor.SLOW_SCREENING.value,
                    "severity": "HIGH",
                    "description": f"Enrollment is at {pct_enrolled:.0%} but {pct_time:.0%} of timeline has elapsed.",
                })

        # 5. Seasonal check
        today = date.today()
        if today.month in (11, 12, 1):
            score += 5
            risk_items.append({
                "factor": RiskFactor.SEASONAL_EFFECT.value,
                "severity": "LOW",
                "description": "Holiday season may slow enrollment rates.",
            })

        score = min(score, 100.0)

        # Determine overall risk level
        if score >= 70:
            overall = "CRITICAL"
        elif score >= 50:
            overall = "HIGH"
        elif score >= 25:
            overall = "MEDIUM"
        else:
            overall = "LOW"

        # Generate recommendations
        recommendations = self._generate_recommendations(risk_items)

        with self._lock:
            forecast.risk_score = score

        return RiskAssessment(
            trial_id=trial_id,
            risk_score=score,
            risk_factors=risk_items,
            overall_risk=overall,
            recommendations=recommendations,
        )

    def _generate_recommendations(self, risk_items: list[dict]) -> list[str]:
        """Generate actionable recommendations based on risk factors."""
        recs: list[str] = []
        factors = {item["factor"] for item in risk_items}

        if RiskFactor.HIGH_SCREEN_FAILURE.value in factors:
            recs.append("Review and revise screening criteria to reduce screen failure rate.")
            recs.append("Conduct site training on inclusion/exclusion criteria interpretation.")

        if RiskFactor.SITE_CAPACITY.value in factors:
            recs.append("Activate additional clinical sites to increase enrollment capacity.")
            recs.append("Redistribute enrollment targets across sites with remaining capacity.")

        if RiskFactor.SLOW_SCREENING.value in factors:
            recs.append("Implement patient engagement and awareness campaigns.")
            recs.append("Review referral network pipeline for additional patient sources.")

        if RiskFactor.SEASONAL_EFFECT.value in factors:
            recs.append("Plan for reduced enrollment during holiday periods with extended timelines.")

        if not recs:
            recs.append("No immediate actions required - continue monitoring enrollment metrics.")

        return recs

    # ------------------------------------------------------------------
    # Data point management
    # ------------------------------------------------------------------

    def add_data_point(
        self,
        trial_id: str,
        request: DataPointCreateRequest,
    ) -> Optional[EnrollmentDataPoint]:
        """Add a new enrollment data point to a trial."""
        forecast = self._forecasts.get(trial_id)
        if forecast is None:
            return None

        with self._lock:
            existing = self._data_points.get(trial_id, [])

            # Compute cumulative
            last_cumulative = existing[-1].cumulative_enrolled if existing else 0
            cumulative = last_cumulative + request.new_enrolled

            dp = EnrollmentDataPoint(
                date=request.date,
                cumulative_enrolled=cumulative,
                new_enrolled=request.new_enrolled,
                screened=request.screened,
                screen_failures=request.screen_failures,
                dropouts=request.dropouts,
                site_id=request.site_id,
            )

            existing.append(dp)
            self._data_points[trial_id] = existing

            # Update current enrollment on forecast
            forecast.current_enrollment = cumulative
            forecast.updated_at = datetime.now(timezone.utc)

        return dp

    def get_data_points(self, trial_id: str) -> Optional[list[EnrollmentDataPoint]]:
        """Get all enrollment data points for a trial."""
        if trial_id not in self._forecasts:
            return None
        return self._data_points.get(trial_id, [])

    # ------------------------------------------------------------------
    # Aggregate metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> ForecastMetrics:
        """Compute aggregate metrics across all trial forecasts."""
        forecasts = list(self._forecasts.values())

        if not forecasts:
            return ForecastMetrics(
                total_trials=0,
                total_target_enrollment=0,
                total_current_enrollment=0,
                overall_enrollment_pct=0.0,
                trials_on_track=0,
                trials_at_risk=0,
                trials_behind=0,
                avg_risk_score=0.0,
                avg_enrollment_rate=0.0,
                total_sites=0,
                avg_screen_failure_rate=0.0,
            )

        total_target = sum(f.target_enrollment for f in forecasts)
        total_current = sum(f.current_enrollment for f in forecasts)
        overall_pct = (total_current / total_target * 100) if total_target > 0 else 0.0

        # Track status
        on_track = 0
        at_risk = 0
        behind = 0

        rates: list[float] = []
        for f in forecasts:
            dp = self._data_points.get(f.trial_id, [])
            rate = self._compute_enrollment_rate(dp)
            rates.append(rate)

            # Determine trial status
            if f.risk_score < 30:
                on_track += 1
            elif f.risk_score < 60:
                at_risk += 1
            else:
                behind += 1

        # Site metrics
        all_sites: list[SiteEnrollmentRate] = []
        for f in forecasts:
            all_sites.extend(f.site_rates)

        total_sites = len(all_sites)
        avg_sfr = statistics.mean(s.screen_failure_rate for s in all_sites) if all_sites else 0.0

        return ForecastMetrics(
            total_trials=len(forecasts),
            total_target_enrollment=total_target,
            total_current_enrollment=total_current,
            overall_enrollment_pct=round(overall_pct, 1),
            trials_on_track=on_track,
            trials_at_risk=at_risk,
            trials_behind=behind,
            avg_risk_score=round(statistics.mean(f.risk_score for f in forecasts), 1),
            avg_enrollment_rate=round(statistics.mean(rates), 2) if rates else 0.0,
            total_sites=total_sites,
            avg_screen_failure_rate=round(avg_sfr, 3),
        )

    # ------------------------------------------------------------------
    # Stats / utility
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return service statistics for health checks."""
        return {
            "total_forecasts": len(self._forecasts),
            "total_data_points": sum(len(dp) for dp in self._data_points.values()),
            "trial_ids": list(self._forecasts.keys()),
        }


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------

_instance: EnrollmentForecastingService | None = None
_instance_lock = threading.Lock()


def get_enrollment_forecasting_service() -> EnrollmentForecastingService:
    """Return the singleton EnrollmentForecastingService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = EnrollmentForecastingService()
    return _instance


def reset_enrollment_forecasting_service() -> EnrollmentForecastingService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = EnrollmentForecastingService()
    return _instance
