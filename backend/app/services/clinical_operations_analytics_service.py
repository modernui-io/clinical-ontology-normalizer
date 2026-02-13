"""Clinical Operations Analytics Service (CLIN-OPS-ANLY).

Manages clinical operations analytics: enrollment velocity tracking,
site performance scorecards, protocol deviation trending, resource
utilization analysis, and milestone achievement with analytics metrics.

Usage:
    from app.services.clinical_operations_analytics_service import (
        get_clinical_operations_analytics_service,
    )

    svc = get_clinical_operations_analytics_service()
    velocities = svc.list_enrollment_velocities()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.clinical_operations_analytics import (
    ClinicalOperationsAnalyticsMetrics,
    DeviationCategory,
    EnrollmentVelocity,
    EnrollmentVelocityCreate,
    EnrollmentVelocityUpdate,
    MilestoneAchievement,
    MilestoneAchievementCreate,
    MilestoneAchievementUpdate,
    MilestoneCategory,
    PerformanceTier,
    ProtocolDeviationTrend,
    ProtocolDeviationTrendCreate,
    ProtocolDeviationTrendUpdate,
    ResourceType,
    ResourceUtilization,
    ResourceUtilizationCreate,
    ResourceUtilizationUpdate,
    SitePerformanceScorecard,
    SitePerformanceScorecardCreate,
    SitePerformanceScorecardUpdate,
    VelocityTrend,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ClinicalOperationsAnalyticsService:
    """In-memory Clinical Operations Analytics engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._enrollment_velocities: dict[str, EnrollmentVelocity] = {}
        self._site_performance_scorecards: dict[str, SitePerformanceScorecard] = {}
        self._protocol_deviation_trends: dict[str, ProtocolDeviationTrend] = {}
        self._resource_utilizations: dict[str, ResourceUtilization] = {}
        self._milestone_achievements: dict[str, MilestoneAchievement] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic clinical operations analytics data."""
        now = datetime.now(timezone.utc)

        # --- 12 Enrollment Velocities ---
        velocity_data = [
            {
                "id": "EV-001",
                "trial_id": EYLEA_TRIAL,
                "measurement_date": now - timedelta(days=180),
                "site_id": None,
                "period_days": 30,
                "patients_enrolled": 12,
                "patients_screened": 20,
                "screen_fail_rate_pct": 40.0,
                "enrollment_rate_per_site_month": 1.2,
                "velocity_trend": VelocityTrend.ACCELERATING,
                "days_to_target": 450,
                "target_enrollment": 300,
                "pct_target_achieved": 4.0,
                "forecast_completion_date": now + timedelta(days=270),
                "analyzed_by": "Dr. Sarah Chen",
                "notes": "Initial enrollment ramp-up. Sites activating on schedule.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "EV-002",
                "trial_id": EYLEA_TRIAL,
                "measurement_date": now - timedelta(days=150),
                "site_id": "SITE-101",
                "period_days": 30,
                "patients_enrolled": 25,
                "patients_screened": 38,
                "screen_fail_rate_pct": 34.2,
                "enrollment_rate_per_site_month": 2.5,
                "velocity_trend": VelocityTrend.ACCELERATING,
                "days_to_target": 330,
                "target_enrollment": 300,
                "pct_target_achieved": 12.3,
                "forecast_completion_date": now + timedelta(days=180),
                "analyzed_by": "Dr. Sarah Chen",
                "notes": "Strong site-level enrollment at SITE-101.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "EV-003",
                "trial_id": EYLEA_TRIAL,
                "measurement_date": now - timedelta(days=120),
                "site_id": None,
                "period_days": 30,
                "patients_enrolled": 45,
                "patients_screened": 62,
                "screen_fail_rate_pct": 27.4,
                "enrollment_rate_per_site_month": 3.0,
                "velocity_trend": VelocityTrend.STEADY,
                "days_to_target": 255,
                "target_enrollment": 300,
                "pct_target_achieved": 27.3,
                "forecast_completion_date": now + timedelta(days=135),
                "analyzed_by": "Dr. Sarah Chen",
                "notes": "Enrollment velocity stabilizing at target rate.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "EV-004",
                "trial_id": EYLEA_TRIAL,
                "measurement_date": now - timedelta(days=90),
                "site_id": None,
                "period_days": 30,
                "patients_enrolled": 52,
                "patients_screened": 70,
                "screen_fail_rate_pct": 25.7,
                "enrollment_rate_per_site_month": 3.5,
                "velocity_trend": VelocityTrend.ACCELERATING,
                "days_to_target": 170,
                "target_enrollment": 300,
                "pct_target_achieved": 44.7,
                "forecast_completion_date": now + timedelta(days=80),
                "analyzed_by": "Dr. James Wright",
                "notes": "Exceeding target rate. Competitive enrollment across sites.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "EV-005",
                "trial_id": DUPIXENT_TRIAL,
                "measurement_date": now - timedelta(days=160),
                "site_id": None,
                "period_days": 30,
                "patients_enrolled": 8,
                "patients_screened": 18,
                "screen_fail_rate_pct": 55.6,
                "enrollment_rate_per_site_month": 0.8,
                "velocity_trend": VelocityTrend.DECELERATING,
                "days_to_target": 600,
                "target_enrollment": 250,
                "pct_target_achieved": 3.2,
                "forecast_completion_date": now + timedelta(days=440),
                "analyzed_by": "Dr. Maria Lopez",
                "notes": "High screen fail rate impacting enrollment. Eligibility criteria review recommended.",
                "created_at": now - timedelta(days=160),
            },
            {
                "id": "EV-006",
                "trial_id": DUPIXENT_TRIAL,
                "measurement_date": now - timedelta(days=130),
                "site_id": "SITE-201",
                "period_days": 30,
                "patients_enrolled": 15,
                "patients_screened": 28,
                "screen_fail_rate_pct": 46.4,
                "enrollment_rate_per_site_month": 1.5,
                "velocity_trend": VelocityTrend.RECOVERING,
                "days_to_target": 470,
                "target_enrollment": 250,
                "pct_target_achieved": 9.2,
                "forecast_completion_date": now + timedelta(days=340),
                "analyzed_by": "Dr. Maria Lopez",
                "notes": "Improving after protocol amendment relaxed entry criteria.",
                "created_at": now - timedelta(days=130),
            },
            {
                "id": "EV-007",
                "trial_id": DUPIXENT_TRIAL,
                "measurement_date": now - timedelta(days=100),
                "site_id": None,
                "period_days": 30,
                "patients_enrolled": 22,
                "patients_screened": 35,
                "screen_fail_rate_pct": 37.1,
                "enrollment_rate_per_site_month": 2.2,
                "velocity_trend": VelocityTrend.ACCELERATING,
                "days_to_target": 310,
                "target_enrollment": 250,
                "pct_target_achieved": 18.0,
                "forecast_completion_date": now + timedelta(days=210),
                "analyzed_by": "Dr. Robert Kim",
                "notes": "Post-amendment acceleration. New sites contributing.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "EV-008",
                "trial_id": DUPIXENT_TRIAL,
                "measurement_date": now - timedelta(days=70),
                "site_id": None,
                "period_days": 30,
                "patients_enrolled": 30,
                "patients_screened": 45,
                "screen_fail_rate_pct": 33.3,
                "enrollment_rate_per_site_month": 2.5,
                "velocity_trend": VelocityTrend.STEADY,
                "days_to_target": 228,
                "target_enrollment": 250,
                "pct_target_achieved": 30.0,
                "forecast_completion_date": now + timedelta(days=158),
                "analyzed_by": "Dr. Robert Kim",
                "notes": "Enrollment velocity now at target rate.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "EV-009",
                "trial_id": LIBTAYO_TRIAL,
                "measurement_date": now - timedelta(days=140),
                "site_id": None,
                "period_days": 30,
                "patients_enrolled": 18,
                "patients_screened": 30,
                "screen_fail_rate_pct": 40.0,
                "enrollment_rate_per_site_month": 1.8,
                "velocity_trend": VelocityTrend.STEADY,
                "days_to_target": 500,
                "target_enrollment": 400,
                "pct_target_achieved": 4.5,
                "forecast_completion_date": now + timedelta(days=360),
                "analyzed_by": "Dr. Angela Park",
                "notes": "Steady enrollment in oncology population.",
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "EV-010",
                "trial_id": LIBTAYO_TRIAL,
                "measurement_date": now - timedelta(days=110),
                "site_id": "SITE-301",
                "period_days": 30,
                "patients_enrolled": 5,
                "patients_screened": 12,
                "screen_fail_rate_pct": 58.3,
                "enrollment_rate_per_site_month": 0.5,
                "velocity_trend": VelocityTrend.STALLED,
                "days_to_target": 720,
                "target_enrollment": 400,
                "pct_target_achieved": 5.8,
                "forecast_completion_date": now + timedelta(days=610),
                "analyzed_by": "Dr. Angela Park",
                "notes": "SITE-301 underperforming. Corrective action plan initiated.",
                "created_at": now - timedelta(days=110),
            },
            {
                "id": "EV-011",
                "trial_id": LIBTAYO_TRIAL,
                "measurement_date": now - timedelta(days=80),
                "site_id": None,
                "period_days": 30,
                "patients_enrolled": 28,
                "patients_screened": 42,
                "screen_fail_rate_pct": 33.3,
                "enrollment_rate_per_site_month": 2.3,
                "velocity_trend": VelocityTrend.RECOVERING,
                "days_to_target": 400,
                "target_enrollment": 400,
                "pct_target_achieved": 12.5,
                "forecast_completion_date": now + timedelta(days=320),
                "analyzed_by": "Dr. Angela Park",
                "notes": "Recovery after arm drop reduced competing enrollment.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "EV-012",
                "trial_id": LIBTAYO_TRIAL,
                "measurement_date": now - timedelta(days=50),
                "site_id": None,
                "period_days": 30,
                "patients_enrolled": 35,
                "patients_screened": 50,
                "screen_fail_rate_pct": 30.0,
                "enrollment_rate_per_site_month": 2.9,
                "velocity_trend": VelocityTrend.ACCELERATING,
                "days_to_target": 310,
                "target_enrollment": 400,
                "pct_target_achieved": 21.3,
                "forecast_completion_date": now + timedelta(days=260),
                "analyzed_by": "Dr. Angela Park",
                "notes": "Acceleration trend continuing. New sites in Asia-Pacific contributing.",
                "created_at": now - timedelta(days=50),
            },
        ]

        for v in velocity_data:
            self._enrollment_velocities[v["id"]] = EnrollmentVelocity(**v)

        # --- 12 Site Performance Scorecards ---
        scorecard_data = [
            {
                "id": "SPS-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "site_name": "Johns Hopkins Wilmer Eye Institute",
                "scorecard_date": now - timedelta(days=30),
                "performance_tier": PerformanceTier.TOP_PERFORMER,
                "enrollment_score": 95.0,
                "data_quality_score": 92.0,
                "compliance_score": 98.0,
                "safety_reporting_score": 96.0,
                "overall_score": 95.3,
                "query_rate_per_page": 0.02,
                "open_queries": 3,
                "overdue_queries": 0,
                "ranking": 1,
                "total_sites": 15,
                "evaluated_by": "Dr. Sarah Chen",
                "notes": "Consistently top performer. Model site for others.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SPS-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "site_name": "Bascom Palmer Eye Institute",
                "scorecard_date": now - timedelta(days=30),
                "performance_tier": PerformanceTier.ABOVE_AVERAGE,
                "enrollment_score": 82.0,
                "data_quality_score": 88.0,
                "compliance_score": 85.0,
                "safety_reporting_score": 90.0,
                "overall_score": 86.3,
                "query_rate_per_page": 0.05,
                "open_queries": 8,
                "overdue_queries": 1,
                "ranking": 3,
                "total_sites": 15,
                "evaluated_by": "Dr. Sarah Chen",
                "notes": "Strong data quality. Minor enrollment lag.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SPS-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "site_name": "Moorfields Eye Hospital",
                "scorecard_date": now - timedelta(days=30),
                "performance_tier": PerformanceTier.AVERAGE,
                "enrollment_score": 60.0,
                "data_quality_score": 70.0,
                "compliance_score": 65.0,
                "safety_reporting_score": 72.0,
                "overall_score": 66.8,
                "query_rate_per_page": 0.12,
                "open_queries": 18,
                "overdue_queries": 5,
                "ranking": 8,
                "total_sites": 15,
                "evaluated_by": "Dr. James Wright",
                "notes": "Average performance. Query resolution needs improvement.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SPS-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-104",
                "site_name": "Singapore National Eye Centre",
                "scorecard_date": now - timedelta(days=30),
                "performance_tier": PerformanceTier.BELOW_AVERAGE,
                "enrollment_score": 40.0,
                "data_quality_score": 55.0,
                "compliance_score": 48.0,
                "safety_reporting_score": 60.0,
                "overall_score": 50.8,
                "query_rate_per_page": 0.20,
                "open_queries": 25,
                "overdue_queries": 12,
                "ranking": 12,
                "total_sites": 15,
                "evaluated_by": "Dr. James Wright",
                "notes": "Below average. Corrective action plan in progress.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SPS-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-201",
                "site_name": "Mayo Clinic Dermatology",
                "scorecard_date": now - timedelta(days=30),
                "performance_tier": PerformanceTier.TOP_PERFORMER,
                "enrollment_score": 90.0,
                "data_quality_score": 94.0,
                "compliance_score": 96.0,
                "safety_reporting_score": 92.0,
                "overall_score": 93.0,
                "query_rate_per_page": 0.03,
                "open_queries": 2,
                "overdue_queries": 0,
                "ranking": 1,
                "total_sites": 12,
                "evaluated_by": "Dr. Maria Lopez",
                "notes": "Exemplary compliance and data quality.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SPS-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-202",
                "site_name": "Cleveland Clinic Dermatology",
                "scorecard_date": now - timedelta(days=30),
                "performance_tier": PerformanceTier.ABOVE_AVERAGE,
                "enrollment_score": 78.0,
                "data_quality_score": 85.0,
                "compliance_score": 80.0,
                "safety_reporting_score": 88.0,
                "overall_score": 82.8,
                "query_rate_per_page": 0.06,
                "open_queries": 6,
                "overdue_queries": 1,
                "ranking": 3,
                "total_sites": 12,
                "evaluated_by": "Dr. Maria Lopez",
                "notes": "Solid performer. Safety reporting particularly strong.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SPS-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-203",
                "site_name": "University of Pennsylvania Dermatology",
                "scorecard_date": now - timedelta(days=30),
                "performance_tier": PerformanceTier.UNDERPERFORMING,
                "enrollment_score": 30.0,
                "data_quality_score": 42.0,
                "compliance_score": 35.0,
                "safety_reporting_score": 45.0,
                "overall_score": 38.0,
                "query_rate_per_page": 0.30,
                "open_queries": 35,
                "overdue_queries": 20,
                "ranking": 12,
                "total_sites": 12,
                "evaluated_by": "Dr. Robert Kim",
                "notes": "Underperforming. Staff turnover impacting quality. Remediation plan required.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SPS-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-204",
                "site_name": "Charite Berlin Dermatology",
                "scorecard_date": now - timedelta(days=30),
                "performance_tier": PerformanceTier.NEW_SITE,
                "enrollment_score": 50.0,
                "data_quality_score": 50.0,
                "compliance_score": 50.0,
                "safety_reporting_score": 50.0,
                "overall_score": 50.0,
                "query_rate_per_page": 0.0,
                "open_queries": 0,
                "overdue_queries": 0,
                "ranking": 8,
                "total_sites": 12,
                "evaluated_by": "Dr. Robert Kim",
                "notes": "Newly activated. Baseline scores pending first monitoring visit.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SPS-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-301",
                "site_name": "Memorial Sloan Kettering Cancer Center",
                "scorecard_date": now - timedelta(days=30),
                "performance_tier": PerformanceTier.TOP_PERFORMER,
                "enrollment_score": 92.0,
                "data_quality_score": 96.0,
                "compliance_score": 94.0,
                "safety_reporting_score": 98.0,
                "overall_score": 95.0,
                "query_rate_per_page": 0.01,
                "open_queries": 1,
                "overdue_queries": 0,
                "ranking": 1,
                "total_sites": 18,
                "evaluated_by": "Dr. Angela Park",
                "notes": "Outstanding safety reporting. Benchmark site.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SPS-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-302",
                "site_name": "MD Anderson Cancer Center",
                "scorecard_date": now - timedelta(days=30),
                "performance_tier": PerformanceTier.ABOVE_AVERAGE,
                "enrollment_score": 85.0,
                "data_quality_score": 80.0,
                "compliance_score": 88.0,
                "safety_reporting_score": 82.0,
                "overall_score": 83.8,
                "query_rate_per_page": 0.07,
                "open_queries": 10,
                "overdue_queries": 2,
                "ranking": 4,
                "total_sites": 18,
                "evaluated_by": "Dr. Angela Park",
                "notes": "Strong enrollment and compliance. Data quality improving.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SPS-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-303",
                "site_name": "Dana-Farber Cancer Institute",
                "scorecard_date": now - timedelta(days=30),
                "performance_tier": PerformanceTier.AVERAGE,
                "enrollment_score": 65.0,
                "data_quality_score": 68.0,
                "compliance_score": 70.0,
                "safety_reporting_score": 75.0,
                "overall_score": 69.5,
                "query_rate_per_page": 0.10,
                "open_queries": 14,
                "overdue_queries": 4,
                "ranking": 9,
                "total_sites": 18,
                "evaluated_by": "Dr. Angela Park",
                "notes": "Average performance. Enrollment below potential.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SPS-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-304",
                "site_name": "Royal Marsden Hospital",
                "scorecard_date": now - timedelta(days=30),
                "performance_tier": PerformanceTier.BELOW_AVERAGE,
                "enrollment_score": 45.0,
                "data_quality_score": 52.0,
                "compliance_score": 50.0,
                "safety_reporting_score": 55.0,
                "overall_score": 50.5,
                "query_rate_per_page": 0.18,
                "open_queries": 22,
                "overdue_queries": 10,
                "ranking": 14,
                "total_sites": 18,
                "evaluated_by": "Dr. Angela Park",
                "notes": "Below average. Regulatory delays impacting activation timeline.",
                "created_at": now - timedelta(days=30),
            },
        ]

        for s in scorecard_data:
            self._site_performance_scorecards[s["id"]] = SitePerformanceScorecard(**s)

        # --- 12 Protocol Deviation Trends ---
        deviation_data = [
            {
                "id": "PDT-001",
                "trial_id": EYLEA_TRIAL,
                "reporting_period": "2025-Q1",
                "deviation_category": DeviationCategory.INFORMED_CONSENT,
                "total_deviations": 8,
                "major_deviations": 2,
                "minor_deviations": 6,
                "repeat_deviations": 1,
                "sites_affected": 3,
                "subjects_affected": 8,
                "root_causes": ["Staff training gap", "Outdated ICF version used"],
                "corrective_actions_initiated": 3,
                "trend_direction": "increasing",
                "deviation_rate_per_subject": 0.053,
                "analyzed_by": "Dr. Sarah Chen",
                "notes": "ICF version control issue identified at 2 sites.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "PDT-002",
                "trial_id": EYLEA_TRIAL,
                "reporting_period": "2025-Q1",
                "deviation_category": DeviationCategory.VISIT_WINDOW,
                "total_deviations": 15,
                "major_deviations": 3,
                "minor_deviations": 12,
                "repeat_deviations": 4,
                "sites_affected": 6,
                "subjects_affected": 14,
                "root_causes": ["Patient scheduling conflicts", "Holiday closures"],
                "corrective_actions_initiated": 2,
                "trend_direction": "stable",
                "deviation_rate_per_subject": 0.093,
                "analyzed_by": "Dr. James Wright",
                "notes": "Visit window deviations mostly minor. Flexible scheduling implemented.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "PDT-003",
                "trial_id": EYLEA_TRIAL,
                "reporting_period": "2025-Q2",
                "deviation_category": DeviationCategory.INFORMED_CONSENT,
                "total_deviations": 3,
                "major_deviations": 0,
                "minor_deviations": 3,
                "repeat_deviations": 0,
                "sites_affected": 2,
                "subjects_affected": 3,
                "root_causes": ["New staff onboarding"],
                "corrective_actions_initiated": 1,
                "trend_direction": "decreasing",
                "deviation_rate_per_subject": 0.017,
                "analyzed_by": "Dr. Sarah Chen",
                "notes": "ICF training initiative showing results. Significant reduction.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "PDT-004",
                "trial_id": EYLEA_TRIAL,
                "reporting_period": "2025-Q2",
                "deviation_category": DeviationCategory.STUDY_PROCEDURES,
                "total_deviations": 5,
                "major_deviations": 1,
                "minor_deviations": 4,
                "repeat_deviations": 0,
                "sites_affected": 3,
                "subjects_affected": 5,
                "root_causes": ["Equipment calibration missed", "Procedure sequence error"],
                "corrective_actions_initiated": 2,
                "trend_direction": "stable",
                "deviation_rate_per_subject": 0.028,
                "analyzed_by": "Dr. James Wright",
                "notes": "One major deviation related to OCT imaging equipment.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "PDT-005",
                "trial_id": DUPIXENT_TRIAL,
                "reporting_period": "2025-Q1",
                "deviation_category": DeviationCategory.INCLUSION_EXCLUSION,
                "total_deviations": 12,
                "major_deviations": 5,
                "minor_deviations": 7,
                "repeat_deviations": 3,
                "sites_affected": 4,
                "subjects_affected": 12,
                "root_causes": ["Complex eligibility criteria", "Lab result interpretation"],
                "corrective_actions_initiated": 4,
                "trend_direction": "increasing",
                "deviation_rate_per_subject": 0.120,
                "analyzed_by": "Dr. Maria Lopez",
                "notes": "High I/E deviation rate led to protocol amendment.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "PDT-006",
                "trial_id": DUPIXENT_TRIAL,
                "reporting_period": "2025-Q1",
                "deviation_category": DeviationCategory.DOSING,
                "total_deviations": 6,
                "major_deviations": 2,
                "minor_deviations": 4,
                "repeat_deviations": 1,
                "sites_affected": 3,
                "subjects_affected": 6,
                "root_causes": ["Weight-based dosing calculation error", "Drug accountability gap"],
                "corrective_actions_initiated": 3,
                "trend_direction": "stable",
                "deviation_rate_per_subject": 0.060,
                "analyzed_by": "Dr. Maria Lopez",
                "notes": "Dosing calculator tool deployed to all sites.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "PDT-007",
                "trial_id": DUPIXENT_TRIAL,
                "reporting_period": "2025-Q2",
                "deviation_category": DeviationCategory.INCLUSION_EXCLUSION,
                "total_deviations": 4,
                "major_deviations": 1,
                "minor_deviations": 3,
                "repeat_deviations": 0,
                "sites_affected": 2,
                "subjects_affected": 4,
                "root_causes": ["Protocol amendment lag at sites"],
                "corrective_actions_initiated": 1,
                "trend_direction": "decreasing",
                "deviation_rate_per_subject": 0.032,
                "analyzed_by": "Dr. Robert Kim",
                "notes": "Amendment-related improvement. Continued monitoring.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "PDT-008",
                "trial_id": DUPIXENT_TRIAL,
                "reporting_period": "2025-Q2",
                "deviation_category": DeviationCategory.SAFETY_REPORTING,
                "total_deviations": 7,
                "major_deviations": 3,
                "minor_deviations": 4,
                "repeat_deviations": 2,
                "sites_affected": 3,
                "subjects_affected": 7,
                "root_causes": ["SAE reporting timeline missed", "AE grading inconsistency"],
                "corrective_actions_initiated": 3,
                "trend_direction": "increasing",
                "deviation_rate_per_subject": 0.056,
                "analyzed_by": "Dr. Robert Kim",
                "notes": "Safety reporting deviations trending up. Focused training scheduled.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "PDT-009",
                "trial_id": LIBTAYO_TRIAL,
                "reporting_period": "2025-Q1",
                "deviation_category": DeviationCategory.STUDY_PROCEDURES,
                "total_deviations": 10,
                "major_deviations": 2,
                "minor_deviations": 8,
                "repeat_deviations": 2,
                "sites_affected": 5,
                "subjects_affected": 9,
                "root_causes": ["Biopsy timing window exceeded", "Lab sample handling"],
                "corrective_actions_initiated": 3,
                "trend_direction": "stable",
                "deviation_rate_per_subject": 0.045,
                "analyzed_by": "Dr. Angela Park",
                "notes": "Oncology procedure complexity contributing to deviations.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "PDT-010",
                "trial_id": LIBTAYO_TRIAL,
                "reporting_period": "2025-Q1",
                "deviation_category": DeviationCategory.VISIT_WINDOW,
                "total_deviations": 20,
                "major_deviations": 4,
                "minor_deviations": 16,
                "repeat_deviations": 6,
                "sites_affected": 8,
                "subjects_affected": 18,
                "root_causes": ["Infusion scheduling conflicts", "Patient travel logistics"],
                "corrective_actions_initiated": 4,
                "trend_direction": "increasing",
                "deviation_rate_per_subject": 0.100,
                "analyzed_by": "Dr. Angela Park",
                "notes": "High visit window deviation rate in oncology population.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "PDT-011",
                "trial_id": LIBTAYO_TRIAL,
                "reporting_period": "2025-Q2",
                "deviation_category": DeviationCategory.STUDY_PROCEDURES,
                "total_deviations": 6,
                "major_deviations": 1,
                "minor_deviations": 5,
                "repeat_deviations": 1,
                "sites_affected": 3,
                "subjects_affected": 6,
                "root_causes": ["Lab sample mislabeling"],
                "corrective_actions_initiated": 2,
                "trend_direction": "decreasing",
                "deviation_rate_per_subject": 0.025,
                "analyzed_by": "Dr. Angela Park",
                "notes": "Improvement from Q1. Lab training program effective.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "PDT-012",
                "trial_id": LIBTAYO_TRIAL,
                "reporting_period": "2025-Q2",
                "deviation_category": DeviationCategory.SAFETY_REPORTING,
                "total_deviations": 9,
                "major_deviations": 4,
                "minor_deviations": 5,
                "repeat_deviations": 2,
                "sites_affected": 4,
                "subjects_affected": 8,
                "root_causes": ["irAE reporting complexity", "Causality assessment delays"],
                "corrective_actions_initiated": 4,
                "trend_direction": "stable",
                "deviation_rate_per_subject": 0.038,
                "analyzed_by": "Dr. Angela Park",
                "notes": "Immune-related AE reporting is inherently complex for checkpoint inhibitors.",
                "created_at": now - timedelta(days=60),
            },
        ]

        for d in deviation_data:
            self._protocol_deviation_trends[d["id"]] = ProtocolDeviationTrend(**d)

        # --- 12 Resource Utilizations ---
        resource_data = [
            {
                "id": "RU-001",
                "trial_id": EYLEA_TRIAL,
                "resource_type": ResourceType.CRA,
                "reporting_period": "2025-Q2",
                "total_fte_allocated": 8.0,
                "total_fte_utilized": 7.2,
                "utilization_pct": 90.0,
                "overtime_hours": 120.0,
                "vacancy_count": 1,
                "contractor_count": 2,
                "training_hours": 40.0,
                "cost_per_fte": 125000.0,
                "budget_variance_pct": -3.5,
                "managed_by": "Dr. Sarah Chen",
                "notes": "High utilization. One vacancy being recruited.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "RU-002",
                "trial_id": EYLEA_TRIAL,
                "resource_type": ResourceType.DATA_MANAGER,
                "reporting_period": "2025-Q2",
                "total_fte_allocated": 4.0,
                "total_fte_utilized": 3.5,
                "utilization_pct": 87.5,
                "overtime_hours": 45.0,
                "vacancy_count": 0,
                "contractor_count": 1,
                "training_hours": 24.0,
                "cost_per_fte": 110000.0,
                "budget_variance_pct": -1.2,
                "managed_by": "Dr. James Wright",
                "notes": "Data management team well-staffed. Query resolution on target.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "RU-003",
                "trial_id": EYLEA_TRIAL,
                "resource_type": ResourceType.PROJECT_MANAGER,
                "reporting_period": "2025-Q2",
                "total_fte_allocated": 2.0,
                "total_fte_utilized": 1.9,
                "utilization_pct": 95.0,
                "overtime_hours": 30.0,
                "vacancy_count": 0,
                "contractor_count": 0,
                "training_hours": 16.0,
                "cost_per_fte": 145000.0,
                "budget_variance_pct": 2.0,
                "managed_by": "Dr. Sarah Chen",
                "notes": "High PM utilization reflecting trial complexity.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "RU-004",
                "trial_id": EYLEA_TRIAL,
                "resource_type": ResourceType.MEDICAL_MONITOR,
                "reporting_period": "2025-Q2",
                "total_fte_allocated": 1.5,
                "total_fte_utilized": 1.3,
                "utilization_pct": 86.7,
                "overtime_hours": 15.0,
                "vacancy_count": 0,
                "contractor_count": 0,
                "training_hours": 8.0,
                "cost_per_fte": 200000.0,
                "budget_variance_pct": -5.0,
                "managed_by": "Dr. James Wright",
                "notes": "Medical monitor capacity adequate for current safety caseload.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "RU-005",
                "trial_id": DUPIXENT_TRIAL,
                "resource_type": ResourceType.CRA,
                "reporting_period": "2025-Q2",
                "total_fte_allocated": 6.0,
                "total_fte_utilized": 5.8,
                "utilization_pct": 96.7,
                "overtime_hours": 200.0,
                "vacancy_count": 2,
                "contractor_count": 3,
                "training_hours": 32.0,
                "cost_per_fte": 125000.0,
                "budget_variance_pct": 8.5,
                "managed_by": "Dr. Maria Lopez",
                "notes": "CRA team stretched. Two vacancies creating overtime pressure.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "RU-006",
                "trial_id": DUPIXENT_TRIAL,
                "resource_type": ResourceType.DATA_MANAGER,
                "reporting_period": "2025-Q2",
                "total_fte_allocated": 3.0,
                "total_fte_utilized": 2.4,
                "utilization_pct": 80.0,
                "overtime_hours": 10.0,
                "vacancy_count": 0,
                "contractor_count": 0,
                "training_hours": 20.0,
                "cost_per_fte": 110000.0,
                "budget_variance_pct": -8.0,
                "managed_by": "Dr. Robert Kim",
                "notes": "Under-utilized due to enrollment delays. Cross-training in progress.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "RU-007",
                "trial_id": DUPIXENT_TRIAL,
                "resource_type": ResourceType.BIOSTATISTICIAN,
                "reporting_period": "2025-Q2",
                "total_fte_allocated": 2.0,
                "total_fte_utilized": 1.8,
                "utilization_pct": 90.0,
                "overtime_hours": 25.0,
                "vacancy_count": 0,
                "contractor_count": 1,
                "training_hours": 12.0,
                "cost_per_fte": 160000.0,
                "budget_variance_pct": 1.5,
                "managed_by": "Dr. Robert Kim",
                "notes": "SSR analysis work driving utilization. Contractor supporting interim analyses.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "RU-008",
                "trial_id": DUPIXENT_TRIAL,
                "resource_type": ResourceType.REGULATORY_SPECIALIST,
                "reporting_period": "2025-Q2",
                "total_fte_allocated": 1.0,
                "total_fte_utilized": 0.9,
                "utilization_pct": 90.0,
                "overtime_hours": 12.0,
                "vacancy_count": 0,
                "contractor_count": 0,
                "training_hours": 8.0,
                "cost_per_fte": 130000.0,
                "budget_variance_pct": 0.0,
                "managed_by": "Dr. Maria Lopez",
                "notes": "Protocol amendment submissions keeping regulatory team busy.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "RU-009",
                "trial_id": LIBTAYO_TRIAL,
                "resource_type": ResourceType.CRA,
                "reporting_period": "2025-Q2",
                "total_fte_allocated": 10.0,
                "total_fte_utilized": 8.5,
                "utilization_pct": 85.0,
                "overtime_hours": 80.0,
                "vacancy_count": 1,
                "contractor_count": 2,
                "training_hours": 48.0,
                "cost_per_fte": 125000.0,
                "budget_variance_pct": -2.0,
                "managed_by": "Dr. Angela Park",
                "notes": "CRA team sized for 18-site oncology trial. One vacancy planned.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "RU-010",
                "trial_id": LIBTAYO_TRIAL,
                "resource_type": ResourceType.MEDICAL_MONITOR,
                "reporting_period": "2025-Q2",
                "total_fte_allocated": 2.0,
                "total_fte_utilized": 1.9,
                "utilization_pct": 95.0,
                "overtime_hours": 40.0,
                "vacancy_count": 0,
                "contractor_count": 0,
                "training_hours": 12.0,
                "cost_per_fte": 200000.0,
                "budget_variance_pct": 5.0,
                "managed_by": "Dr. Angela Park",
                "notes": "High utilization from irAE review workload. Budget variance from overtime.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "RU-011",
                "trial_id": LIBTAYO_TRIAL,
                "resource_type": ResourceType.PROJECT_MANAGER,
                "reporting_period": "2025-Q2",
                "total_fte_allocated": 2.5,
                "total_fte_utilized": 2.3,
                "utilization_pct": 92.0,
                "overtime_hours": 35.0,
                "vacancy_count": 0,
                "contractor_count": 0,
                "training_hours": 16.0,
                "cost_per_fte": 145000.0,
                "budget_variance_pct": 3.0,
                "managed_by": "Dr. Angela Park",
                "notes": "Arm drop coordination drove temporary PM workload spike.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "RU-012",
                "trial_id": LIBTAYO_TRIAL,
                "resource_type": ResourceType.BIOSTATISTICIAN,
                "reporting_period": "2025-Q2",
                "total_fte_allocated": 3.0,
                "total_fte_utilized": 2.7,
                "utilization_pct": 90.0,
                "overtime_hours": 30.0,
                "vacancy_count": 0,
                "contractor_count": 1,
                "training_hours": 16.0,
                "cost_per_fte": 160000.0,
                "budget_variance_pct": 2.5,
                "managed_by": "Dr. Angela Park",
                "notes": "Adaptive design requiring more intensive biostatistics support.",
                "created_at": now - timedelta(days=30),
            },
        ]

        for r in resource_data:
            self._resource_utilizations[r["id"]] = ResourceUtilization(**r)

        # --- 12 Milestone Achievements ---
        milestone_data = [
            {
                "id": "MA-001",
                "trial_id": EYLEA_TRIAL,
                "milestone_name": "First Patient First Visit (FPFV)",
                "milestone_category": MilestoneCategory.ENROLLMENT,
                "planned_date": now - timedelta(days=200),
                "actual_date": now - timedelta(days=195),
                "achieved": True,
                "days_variance": -5,
                "on_track": True,
                "critical_path": True,
                "dependencies": [],
                "blockers": [],
                "owner": "Dr. Sarah Chen",
                "escalated": False,
                "notes": "FPFV achieved 5 days ahead of schedule.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "MA-002",
                "trial_id": EYLEA_TRIAL,
                "milestone_name": "50% Enrollment Target",
                "milestone_category": MilestoneCategory.ENROLLMENT,
                "planned_date": now - timedelta(days=100),
                "actual_date": now - timedelta(days=90),
                "achieved": True,
                "days_variance": -10,
                "on_track": True,
                "critical_path": True,
                "dependencies": ["MA-001"],
                "blockers": [],
                "owner": "Dr. Sarah Chen",
                "escalated": False,
                "notes": "50% target reached 10 days early due to strong site performance.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "MA-003",
                "trial_id": EYLEA_TRIAL,
                "milestone_name": "Database Lock",
                "milestone_category": MilestoneCategory.DATABASE_LOCK,
                "planned_date": now + timedelta(days=90),
                "actual_date": None,
                "achieved": False,
                "days_variance": 0,
                "on_track": True,
                "critical_path": True,
                "dependencies": ["MA-002"],
                "blockers": [],
                "owner": "Dr. James Wright",
                "escalated": False,
                "notes": "On track. Clean data rate above 95%.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "MA-004",
                "trial_id": EYLEA_TRIAL,
                "milestone_name": "Primary Analysis Report",
                "milestone_category": MilestoneCategory.ANALYSIS,
                "planned_date": now + timedelta(days=150),
                "actual_date": None,
                "achieved": False,
                "days_variance": 0,
                "on_track": True,
                "critical_path": True,
                "dependencies": ["MA-003"],
                "blockers": [],
                "owner": "Dr. Sarah Chen",
                "escalated": False,
                "notes": "Pending database lock. Statistical analysis plan finalized.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "MA-005",
                "trial_id": DUPIXENT_TRIAL,
                "milestone_name": "IND Approval",
                "milestone_category": MilestoneCategory.REGULATORY,
                "planned_date": now - timedelta(days=300),
                "actual_date": now - timedelta(days=310),
                "achieved": True,
                "days_variance": -10,
                "on_track": True,
                "critical_path": True,
                "dependencies": [],
                "blockers": [],
                "owner": "Dr. Maria Lopez",
                "escalated": False,
                "notes": "IND approved ahead of schedule. FDA feedback favorable.",
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "MA-006",
                "trial_id": DUPIXENT_TRIAL,
                "milestone_name": "First Site Activated",
                "milestone_category": MilestoneCategory.SITE_ACTIVATION,
                "planned_date": now - timedelta(days=180),
                "actual_date": now - timedelta(days=170),
                "achieved": True,
                "days_variance": -10,
                "on_track": True,
                "critical_path": True,
                "dependencies": ["MA-005"],
                "blockers": [],
                "owner": "Dr. Maria Lopez",
                "escalated": False,
                "notes": "First site activated ahead of plan.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "MA-007",
                "trial_id": DUPIXENT_TRIAL,
                "milestone_name": "Last Patient Last Visit (LPLV)",
                "milestone_category": MilestoneCategory.ENROLLMENT,
                "planned_date": now + timedelta(days=200),
                "actual_date": None,
                "achieved": False,
                "days_variance": 0,
                "on_track": False,
                "critical_path": True,
                "dependencies": ["MA-006"],
                "blockers": ["Enrollment velocity below target", "Screen fail rate elevated"],
                "owner": "Dr. Robert Kim",
                "escalated": True,
                "notes": "Projected 30-day delay. Protocol amendment expected to improve enrollment.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "MA-008",
                "trial_id": DUPIXENT_TRIAL,
                "milestone_name": "CSR Submission to Regulatory",
                "milestone_category": MilestoneCategory.SUBMISSION,
                "planned_date": now + timedelta(days=400),
                "actual_date": None,
                "achieved": False,
                "days_variance": 0,
                "on_track": False,
                "critical_path": True,
                "dependencies": ["MA-007"],
                "blockers": ["Upstream enrollment delay"],
                "owner": "Dr. Maria Lopez",
                "escalated": True,
                "notes": "Cascading delay from enrollment. Re-forecasting in progress.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "MA-009",
                "trial_id": LIBTAYO_TRIAL,
                "milestone_name": "Protocol Amendment (Arm Drop)",
                "milestone_category": MilestoneCategory.REGULATORY,
                "planned_date": now - timedelta(days=130),
                "actual_date": now - timedelta(days=120),
                "achieved": True,
                "days_variance": -10,
                "on_track": True,
                "critical_path": True,
                "dependencies": [],
                "blockers": [],
                "owner": "Dr. Angela Park",
                "escalated": False,
                "notes": "Protocol amendment for arm drop approved by all IRBs/ECs.",
                "created_at": now - timedelta(days=130),
            },
            {
                "id": "MA-010",
                "trial_id": LIBTAYO_TRIAL,
                "milestone_name": "75% Site Activation",
                "milestone_category": MilestoneCategory.SITE_ACTIVATION,
                "planned_date": now - timedelta(days=90),
                "actual_date": now - timedelta(days=80),
                "achieved": True,
                "days_variance": -10,
                "on_track": True,
                "critical_path": False,
                "dependencies": ["MA-009"],
                "blockers": [],
                "owner": "Dr. Angela Park",
                "escalated": False,
                "notes": "75% of sites activated. Remaining sites pending local regulatory.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "MA-011",
                "trial_id": LIBTAYO_TRIAL,
                "milestone_name": "Interim Analysis 3",
                "milestone_category": MilestoneCategory.ANALYSIS,
                "planned_date": now + timedelta(days=60),
                "actual_date": None,
                "achieved": False,
                "days_variance": 0,
                "on_track": True,
                "critical_path": True,
                "dependencies": ["MA-010"],
                "blockers": [],
                "owner": "Dr. Angela Park",
                "escalated": False,
                "notes": "Third interim analysis for remaining two arms.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "MA-012",
                "trial_id": LIBTAYO_TRIAL,
                "milestone_name": "NDA Submission",
                "milestone_category": MilestoneCategory.SUBMISSION,
                "planned_date": now + timedelta(days=365),
                "actual_date": None,
                "achieved": False,
                "days_variance": 0,
                "on_track": True,
                "critical_path": True,
                "dependencies": ["MA-011"],
                "blockers": [],
                "owner": "Dr. Angela Park",
                "escalated": False,
                "notes": "NDA filing timeline on track. Pre-NDA meeting scheduled.",
                "created_at": now - timedelta(days=30),
            },
        ]

        for m in milestone_data:
            self._milestone_achievements[m["id"]] = MilestoneAchievement(**m)

    # ------------------------------------------------------------------
    # Enrollment Velocities
    # ------------------------------------------------------------------

    def list_enrollment_velocities(
        self,
        *,
        trial_id: str | None = None,
        velocity_trend: VelocityTrend | None = None,
    ) -> list[EnrollmentVelocity]:
        """List enrollment velocities with optional filters."""
        with self._lock:
            result = list(self._enrollment_velocities.values())

        if trial_id is not None:
            result = [v for v in result if v.trial_id == trial_id]
        if velocity_trend is not None:
            result = [v for v in result if v.velocity_trend == velocity_trend]

        return sorted(result, key=lambda v: v.measurement_date, reverse=True)

    def get_enrollment_velocity(self, velocity_id: str) -> EnrollmentVelocity | None:
        """Get a single enrollment velocity by ID."""
        with self._lock:
            return self._enrollment_velocities.get(velocity_id)

    def create_enrollment_velocity(self, payload: EnrollmentVelocityCreate) -> EnrollmentVelocity:
        """Create a new enrollment velocity record."""
        now = datetime.now(timezone.utc)
        velocity_id = f"EV-{uuid4().hex[:8].upper()}"
        screen_fail = 0.0
        if payload.patients_screened > 0:
            screen_fail = round(
                (1 - payload.patients_enrolled / payload.patients_screened) * 100, 1
            )
        velocity = EnrollmentVelocity(
            id=velocity_id,
            trial_id=payload.trial_id,
            measurement_date=now,
            site_id=None,
            period_days=payload.period_days,
            patients_enrolled=payload.patients_enrolled,
            patients_screened=payload.patients_screened,
            screen_fail_rate_pct=screen_fail,
            enrollment_rate_per_site_month=0.0,
            velocity_trend=VelocityTrend.NOT_STARTED,
            days_to_target=None,
            target_enrollment=payload.target_enrollment,
            pct_target_achieved=0.0,
            forecast_completion_date=None,
            analyzed_by=payload.analyzed_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._enrollment_velocities[velocity_id] = velocity
        logger.info("Created enrollment velocity %s for trial %s", velocity_id, payload.trial_id)
        return velocity

    def update_enrollment_velocity(
        self, velocity_id: str, payload: EnrollmentVelocityUpdate
    ) -> EnrollmentVelocity | None:
        """Update an existing enrollment velocity."""
        with self._lock:
            existing = self._enrollment_velocities.get(velocity_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = EnrollmentVelocity(**data)
            self._enrollment_velocities[velocity_id] = updated
        return updated

    def delete_enrollment_velocity(self, velocity_id: str) -> bool:
        """Delete an enrollment velocity. Returns True if deleted."""
        with self._lock:
            if velocity_id in self._enrollment_velocities:
                del self._enrollment_velocities[velocity_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Site Performance Scorecards
    # ------------------------------------------------------------------

    def list_site_performance_scorecards(
        self,
        *,
        trial_id: str | None = None,
        performance_tier: PerformanceTier | None = None,
    ) -> list[SitePerformanceScorecard]:
        """List site performance scorecards with optional filters."""
        with self._lock:
            result = list(self._site_performance_scorecards.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if performance_tier is not None:
            result = [s for s in result if s.performance_tier == performance_tier]

        return sorted(result, key=lambda s: s.scorecard_date, reverse=True)

    def get_site_performance_scorecard(self, scorecard_id: str) -> SitePerformanceScorecard | None:
        """Get a single site performance scorecard by ID."""
        with self._lock:
            return self._site_performance_scorecards.get(scorecard_id)

    def create_site_performance_scorecard(
        self, payload: SitePerformanceScorecardCreate
    ) -> SitePerformanceScorecard:
        """Create a new site performance scorecard."""
        now = datetime.now(timezone.utc)
        scorecard_id = f"SPS-{uuid4().hex[:8].upper()}"
        overall = round((payload.enrollment_score + payload.data_quality_score + 50.0 + 50.0) / 4, 1)
        scorecard = SitePerformanceScorecard(
            id=scorecard_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            site_name=payload.site_name,
            scorecard_date=now,
            performance_tier=PerformanceTier.NEW_SITE,
            enrollment_score=payload.enrollment_score,
            data_quality_score=payload.data_quality_score,
            compliance_score=50.0,
            safety_reporting_score=50.0,
            overall_score=overall,
            query_rate_per_page=0.0,
            open_queries=0,
            overdue_queries=0,
            ranking=1,
            total_sites=1,
            evaluated_by=payload.evaluated_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._site_performance_scorecards[scorecard_id] = scorecard
        logger.info(
            "Created site performance scorecard %s for trial %s site %s",
            scorecard_id,
            payload.trial_id,
            payload.site_id,
        )
        return scorecard

    def update_site_performance_scorecard(
        self, scorecard_id: str, payload: SitePerformanceScorecardUpdate
    ) -> SitePerformanceScorecard | None:
        """Update an existing site performance scorecard."""
        with self._lock:
            existing = self._site_performance_scorecards.get(scorecard_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SitePerformanceScorecard(**data)
            self._site_performance_scorecards[scorecard_id] = updated
        return updated

    def delete_site_performance_scorecard(self, scorecard_id: str) -> bool:
        """Delete a site performance scorecard. Returns True if deleted."""
        with self._lock:
            if scorecard_id in self._site_performance_scorecards:
                del self._site_performance_scorecards[scorecard_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Protocol Deviation Trends
    # ------------------------------------------------------------------

    def list_protocol_deviation_trends(
        self,
        *,
        trial_id: str | None = None,
        deviation_category: DeviationCategory | None = None,
    ) -> list[ProtocolDeviationTrend]:
        """List protocol deviation trends with optional filters."""
        with self._lock:
            result = list(self._protocol_deviation_trends.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]
        if deviation_category is not None:
            result = [d for d in result if d.deviation_category == deviation_category]

        return sorted(result, key=lambda d: d.created_at, reverse=True)

    def get_protocol_deviation_trend(self, trend_id: str) -> ProtocolDeviationTrend | None:
        """Get a single protocol deviation trend by ID."""
        with self._lock:
            return self._protocol_deviation_trends.get(trend_id)

    def create_protocol_deviation_trend(
        self, payload: ProtocolDeviationTrendCreate
    ) -> ProtocolDeviationTrend:
        """Create a new protocol deviation trend."""
        now = datetime.now(timezone.utc)
        trend_id = f"PDT-{uuid4().hex[:8].upper()}"
        minor = max(0, payload.total_deviations - payload.major_deviations)
        trend = ProtocolDeviationTrend(
            id=trend_id,
            trial_id=payload.trial_id,
            reporting_period=payload.reporting_period,
            deviation_category=payload.deviation_category,
            total_deviations=payload.total_deviations,
            major_deviations=payload.major_deviations,
            minor_deviations=minor,
            repeat_deviations=0,
            sites_affected=0,
            subjects_affected=0,
            root_causes=[],
            corrective_actions_initiated=0,
            trend_direction="stable",
            deviation_rate_per_subject=0.0,
            analyzed_by=payload.analyzed_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._protocol_deviation_trends[trend_id] = trend
        logger.info(
            "Created protocol deviation trend %s for trial %s", trend_id, payload.trial_id
        )
        return trend

    def update_protocol_deviation_trend(
        self, trend_id: str, payload: ProtocolDeviationTrendUpdate
    ) -> ProtocolDeviationTrend | None:
        """Update an existing protocol deviation trend."""
        with self._lock:
            existing = self._protocol_deviation_trends.get(trend_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ProtocolDeviationTrend(**data)
            self._protocol_deviation_trends[trend_id] = updated
        return updated

    def delete_protocol_deviation_trend(self, trend_id: str) -> bool:
        """Delete a protocol deviation trend. Returns True if deleted."""
        with self._lock:
            if trend_id in self._protocol_deviation_trends:
                del self._protocol_deviation_trends[trend_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Resource Utilizations
    # ------------------------------------------------------------------

    def list_resource_utilizations(
        self,
        *,
        trial_id: str | None = None,
        resource_type: ResourceType | None = None,
    ) -> list[ResourceUtilization]:
        """List resource utilizations with optional filters."""
        with self._lock:
            result = list(self._resource_utilizations.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if resource_type is not None:
            result = [r for r in result if r.resource_type == resource_type]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_resource_utilization(self, utilization_id: str) -> ResourceUtilization | None:
        """Get a single resource utilization by ID."""
        with self._lock:
            return self._resource_utilizations.get(utilization_id)

    def create_resource_utilization(
        self, payload: ResourceUtilizationCreate
    ) -> ResourceUtilization:
        """Create a new resource utilization record."""
        now = datetime.now(timezone.utc)
        util_id = f"RU-{uuid4().hex[:8].upper()}"
        util_pct = 0.0
        if payload.total_fte_allocated > 0:
            util_pct = round(
                (payload.total_fte_utilized / payload.total_fte_allocated) * 100, 1
            )
        utilization = ResourceUtilization(
            id=util_id,
            trial_id=payload.trial_id,
            resource_type=payload.resource_type,
            reporting_period=payload.reporting_period,
            total_fte_allocated=payload.total_fte_allocated,
            total_fte_utilized=payload.total_fte_utilized,
            utilization_pct=util_pct,
            overtime_hours=0.0,
            vacancy_count=0,
            contractor_count=0,
            training_hours=0.0,
            cost_per_fte=0.0,
            budget_variance_pct=0.0,
            managed_by=payload.managed_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._resource_utilizations[util_id] = utilization
        logger.info(
            "Created resource utilization %s for trial %s", util_id, payload.trial_id
        )
        return utilization

    def update_resource_utilization(
        self, utilization_id: str, payload: ResourceUtilizationUpdate
    ) -> ResourceUtilization | None:
        """Update an existing resource utilization."""
        with self._lock:
            existing = self._resource_utilizations.get(utilization_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ResourceUtilization(**data)
            self._resource_utilizations[utilization_id] = updated
        return updated

    def delete_resource_utilization(self, utilization_id: str) -> bool:
        """Delete a resource utilization. Returns True if deleted."""
        with self._lock:
            if utilization_id in self._resource_utilizations:
                del self._resource_utilizations[utilization_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Milestone Achievements
    # ------------------------------------------------------------------

    def list_milestone_achievements(
        self,
        *,
        trial_id: str | None = None,
        milestone_category: MilestoneCategory | None = None,
    ) -> list[MilestoneAchievement]:
        """List milestone achievements with optional filters."""
        with self._lock:
            result = list(self._milestone_achievements.values())

        if trial_id is not None:
            result = [m for m in result if m.trial_id == trial_id]
        if milestone_category is not None:
            result = [m for m in result if m.milestone_category == milestone_category]

        return sorted(result, key=lambda m: m.planned_date, reverse=True)

    def get_milestone_achievement(self, milestone_id: str) -> MilestoneAchievement | None:
        """Get a single milestone achievement by ID."""
        with self._lock:
            return self._milestone_achievements.get(milestone_id)

    def create_milestone_achievement(
        self, payload: MilestoneAchievementCreate
    ) -> MilestoneAchievement:
        """Create a new milestone achievement."""
        now = datetime.now(timezone.utc)
        milestone_id = f"MA-{uuid4().hex[:8].upper()}"
        milestone = MilestoneAchievement(
            id=milestone_id,
            trial_id=payload.trial_id,
            milestone_name=payload.milestone_name,
            milestone_category=payload.milestone_category,
            planned_date=payload.planned_date,
            actual_date=None,
            achieved=False,
            days_variance=0,
            on_track=True,
            critical_path=payload.critical_path,
            dependencies=[],
            blockers=[],
            owner=payload.owner,
            escalated=False,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._milestone_achievements[milestone_id] = milestone
        logger.info(
            "Created milestone achievement %s for trial %s", milestone_id, payload.trial_id
        )
        return milestone

    def update_milestone_achievement(
        self, milestone_id: str, payload: MilestoneAchievementUpdate
    ) -> MilestoneAchievement | None:
        """Update an existing milestone achievement."""
        with self._lock:
            existing = self._milestone_achievements.get(milestone_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MilestoneAchievement(**data)
            self._milestone_achievements[milestone_id] = updated
        return updated

    def delete_milestone_achievement(self, milestone_id: str) -> bool:
        """Delete a milestone achievement. Returns True if deleted."""
        with self._lock:
            if milestone_id in self._milestone_achievements:
                del self._milestone_achievements[milestone_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> ClinicalOperationsAnalyticsMetrics:
        """Compute aggregated clinical operations analytics metrics."""
        with self._lock:
            velocities = list(self._enrollment_velocities.values())
            scorecards = list(self._site_performance_scorecards.values())
            deviations = list(self._protocol_deviation_trends.values())
            resources = list(self._resource_utilizations.values())
            milestones = list(self._milestone_achievements.values())

        # Velocity by trend
        velocity_by_trend: dict[str, int] = {}
        for v in velocities:
            key = v.velocity_trend.value
            velocity_by_trend[key] = velocity_by_trend.get(key, 0) + 1

        # Average enrollment rate
        rates = [v.enrollment_rate_per_site_month for v in velocities if v.enrollment_rate_per_site_month > 0]
        avg_enrollment_rate = round(sum(rates) / max(1, len(rates)), 2) if rates else 0.0

        # Scorecards by tier
        scorecards_by_tier: dict[str, int] = {}
        for s in scorecards:
            key = s.performance_tier.value
            scorecards_by_tier[key] = scorecards_by_tier.get(key, 0) + 1

        # Average overall score
        scores = [s.overall_score for s in scorecards]
        avg_overall_score = round(sum(scores) / max(1, len(scores)), 1) if scores else 0.0

        # Deviations by category
        deviations_by_category: dict[str, int] = {}
        for d in deviations:
            key = d.deviation_category.value
            deviations_by_category[key] = deviations_by_category.get(key, 0) + 1

        # Total major deviations
        total_major = sum(d.major_deviations for d in deviations)

        # Resources by type
        resources_by_type: dict[str, int] = {}
        for r in resources:
            key = r.resource_type.value
            resources_by_type[key] = resources_by_type.get(key, 0) + 1

        # Average utilization pct
        util_pcts = [r.utilization_pct for r in resources if r.utilization_pct > 0]
        avg_utilization_pct = round(sum(util_pcts) / max(1, len(util_pcts)), 1) if util_pcts else 0.0

        # Milestones by category
        milestones_by_category: dict[str, int] = {}
        for m in milestones:
            key = m.milestone_category.value
            milestones_by_category[key] = milestones_by_category.get(key, 0) + 1

        # Milestones achieved
        milestones_achieved = sum(1 for m in milestones if m.achieved)

        # Milestones overdue (not achieved and planned_date in the past)
        now = datetime.now(timezone.utc)
        milestones_overdue = sum(
            1 for m in milestones if not m.achieved and m.planned_date < now and not m.on_track
        )

        return ClinicalOperationsAnalyticsMetrics(
            total_velocity_records=len(velocities),
            velocity_by_trend=velocity_by_trend,
            avg_enrollment_rate=avg_enrollment_rate,
            total_scorecards=len(scorecards),
            scorecards_by_tier=scorecards_by_tier,
            avg_overall_score=avg_overall_score,
            total_deviation_trends=len(deviations),
            deviations_by_category=deviations_by_category,
            total_major_deviations=total_major,
            total_resource_records=len(resources),
            resources_by_type=resources_by_type,
            avg_utilization_pct=avg_utilization_pct,
            total_milestones=len(milestones),
            milestones_by_category=milestones_by_category,
            milestones_achieved=milestones_achieved,
            milestones_overdue=milestones_overdue,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ClinicalOperationsAnalyticsService | None = None
_instance_lock = threading.Lock()


def get_clinical_operations_analytics_service() -> ClinicalOperationsAnalyticsService:
    """Return the singleton ClinicalOperationsAnalyticsService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ClinicalOperationsAnalyticsService()
    return _instance


def reset_clinical_operations_analytics_service() -> ClinicalOperationsAnalyticsService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ClinicalOperationsAnalyticsService()
    return _instance
