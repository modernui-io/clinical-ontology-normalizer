"""Central Monitoring Management Service (CTR-MON).

Manages central/remote monitoring operations: remote monitoring visits,
KRI signal detection, site risk indicators, monitoring action items,
centralized review activities, and central monitoring operational metrics.

Usage:
    from app.services.central_monitoring_service import (
        get_central_monitoring_service,
        reset_central_monitoring_service,
    )

    svc = get_central_monitoring_service()
    visits = svc.list_monitoring_visits()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.central_monitoring import (
    ActionStatus,
    CentralMonitoringMetrics,
    CentralReview,
    CentralReviewCreate,
    CentralReviewUpdate,
    KRISignal,
    KRISignalCreate,
    KRISignalUpdate,
    MonitoringAction,
    MonitoringActionCreate,
    MonitoringActionUpdate,
    MonitoringType,
    MonitoringVisit,
    MonitoringVisitCreate,
    MonitoringVisitUpdate,
    ReviewOutcome,
    RiskLevel,
    SignalCategory,
    SiteRiskIndicator,
    SiteRiskIndicatorCreate,
    SiteRiskIndicatorUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class CentralMonitoringService:
    """In-memory Central Monitoring engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._monitoring_visits: dict[str, MonitoringVisit] = {}
        self._kri_signals: dict[str, KRISignal] = {}
        self._site_risk_indicators: dict[str, SiteRiskIndicator] = {}
        self._monitoring_actions: dict[str, MonitoringAction] = {}
        self._central_reviews: dict[str, CentralReview] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901 PLR0915
        """Pre-populate realistic central monitoring data across Regeneron trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Monitoring Visits ---
        visits_data = [
            {
                "id": "CMV-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "monitoring_type": MonitoringType.REMOTE,
                "visit_date": now - timedelta(days=90),
                "completed_date": now - timedelta(days=89),
                "monitor": "Sarah Mitchell",
                "subjects_reviewed": 25,
                "queries_generated": 4,
                "findings_count": 1,
                "critical_findings": 0,
                "data_points_reviewed": 480,
                "deviations_identified": 0,
                "review_outcome": ReviewOutcome.NO_ACTION,
                "follow_up_required": False,
                "report_finalized": True,
                "next_review_date": now - timedelta(days=30),
                "notes": "Routine remote monitoring. Site performing well.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "CMV-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "monitoring_type": MonitoringType.CENTRALIZED,
                "visit_date": now - timedelta(days=75),
                "completed_date": now - timedelta(days=74),
                "monitor": "David Park",
                "subjects_reviewed": 32,
                "queries_generated": 8,
                "findings_count": 2,
                "critical_findings": 0,
                "data_points_reviewed": 640,
                "deviations_identified": 1,
                "review_outcome": ReviewOutcome.ACTION_REQUIRED,
                "follow_up_required": True,
                "report_finalized": True,
                "next_review_date": now - timedelta(days=15),
                "notes": "Minor data quality issues detected in lab data entry.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "CMV-003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "monitoring_type": MonitoringType.RISK_BASED,
                "visit_date": now - timedelta(days=60),
                "completed_date": now - timedelta(days=59),
                "monitor": "Jennifer Lee",
                "subjects_reviewed": 18,
                "queries_generated": 12,
                "findings_count": 4,
                "critical_findings": 1,
                "data_points_reviewed": 360,
                "deviations_identified": 2,
                "review_outcome": ReviewOutcome.SITE_CONTACT,
                "follow_up_required": True,
                "report_finalized": True,
                "next_review_date": now - timedelta(days=5),
                "notes": "Elevated protocol deviation rate. Site contacted for remediation.",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "CMV-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "monitoring_type": MonitoringType.STATISTICAL,
                "visit_date": now - timedelta(days=45),
                "completed_date": now - timedelta(days=44),
                "monitor": "Sarah Mitchell",
                "subjects_reviewed": 22,
                "queries_generated": 6,
                "findings_count": 2,
                "critical_findings": 0,
                "data_points_reviewed": 440,
                "deviations_identified": 1,
                "review_outcome": ReviewOutcome.ACTION_REQUIRED,
                "follow_up_required": True,
                "report_finalized": True,
                "next_review_date": now + timedelta(days=15),
                "notes": "Statistical outlier detection flagged consent timing anomaly.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "CMV-005",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "monitoring_type": MonitoringType.REMOTE,
                "visit_date": now - timedelta(days=30),
                "completed_date": now - timedelta(days=29),
                "monitor": "David Park",
                "subjects_reviewed": 15,
                "queries_generated": 18,
                "findings_count": 5,
                "critical_findings": 2,
                "data_points_reviewed": 300,
                "deviations_identified": 3,
                "review_outcome": ReviewOutcome.TRIGGERED_VISIT,
                "follow_up_required": True,
                "report_finalized": True,
                "next_review_date": now + timedelta(days=7),
                "notes": "Critical SAE reporting gaps. Triggered on-site visit recommended.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "CMV-006",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "monitoring_type": MonitoringType.CENTRALIZED,
                "visit_date": now - timedelta(days=20),
                "completed_date": now - timedelta(days=19),
                "monitor": "Jennifer Lee",
                "subjects_reviewed": 28,
                "queries_generated": 10,
                "findings_count": 3,
                "critical_findings": 1,
                "data_points_reviewed": 560,
                "deviations_identified": 2,
                "review_outcome": ReviewOutcome.ESCALATED,
                "follow_up_required": True,
                "report_finalized": True,
                "next_review_date": now + timedelta(days=10),
                "notes": "Systematic consent form errors escalated to medical monitor.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "CMV-007",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-107",
                "monitoring_type": MonitoringType.RISK_BASED,
                "visit_date": now - timedelta(days=14),
                "completed_date": now - timedelta(days=13),
                "monitor": "David Park",
                "subjects_reviewed": 20,
                "queries_generated": 22,
                "findings_count": 6,
                "critical_findings": 3,
                "data_points_reviewed": 400,
                "deviations_identified": 4,
                "review_outcome": ReviewOutcome.ESCALATED,
                "follow_up_required": True,
                "report_finalized": False,
                "next_review_date": now + timedelta(days=3),
                "notes": "Multiple critical findings. Report pending finalization.",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "CMV-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-108",
                "monitoring_type": MonitoringType.DATA_DRIVEN,
                "visit_date": now - timedelta(days=10),
                "completed_date": now - timedelta(days=9),
                "monitor": "Sarah Mitchell",
                "subjects_reviewed": 30,
                "queries_generated": 3,
                "findings_count": 1,
                "critical_findings": 0,
                "data_points_reviewed": 600,
                "deviations_identified": 0,
                "review_outcome": ReviewOutcome.NO_ACTION,
                "follow_up_required": False,
                "report_finalized": True,
                "next_review_date": now + timedelta(days=60),
                "notes": "Data-driven review. Site in good standing.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "CMV-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-101",
                "monitoring_type": MonitoringType.REMOTE,
                "visit_date": now - timedelta(days=5),
                "completed_date": None,
                "monitor": "Jennifer Lee",
                "subjects_reviewed": 0,
                "queries_generated": 0,
                "findings_count": 0,
                "critical_findings": 0,
                "data_points_reviewed": 0,
                "deviations_identified": 0,
                "review_outcome": ReviewOutcome.NO_ACTION,
                "follow_up_required": False,
                "report_finalized": False,
                "next_review_date": None,
                "notes": None,
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "CMV-010",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "monitoring_type": MonitoringType.CENTRALIZED,
                "visit_date": now + timedelta(days=7),
                "completed_date": None,
                "monitor": "David Park",
                "subjects_reviewed": 0,
                "queries_generated": 0,
                "findings_count": 0,
                "critical_findings": 0,
                "data_points_reviewed": 0,
                "deviations_identified": 0,
                "review_outcome": ReviewOutcome.NO_ACTION,
                "follow_up_required": False,
                "report_finalized": False,
                "next_review_date": None,
                "notes": None,
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "CMV-011",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "monitoring_type": MonitoringType.RISK_BASED,
                "visit_date": now + timedelta(days=14),
                "completed_date": None,
                "monitor": "Jennifer Lee",
                "subjects_reviewed": 0,
                "queries_generated": 0,
                "findings_count": 0,
                "critical_findings": 0,
                "data_points_reviewed": 0,
                "deviations_identified": 0,
                "review_outcome": ReviewOutcome.NO_ACTION,
                "follow_up_required": False,
                "report_finalized": False,
                "next_review_date": None,
                "notes": None,
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "CMV-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "monitoring_type": MonitoringType.RISK_BASED,
                "visit_date": now + timedelta(days=3),
                "completed_date": None,
                "monitor": "David Park",
                "subjects_reviewed": 0,
                "queries_generated": 0,
                "findings_count": 0,
                "critical_findings": 0,
                "data_points_reviewed": 0,
                "deviations_identified": 0,
                "review_outcome": ReviewOutcome.NO_ACTION,
                "follow_up_required": False,
                "report_finalized": False,
                "next_review_date": None,
                "notes": "Follow-up for critical findings from CMV-007.",
                "created_at": now - timedelta(days=1),
            },
        ]

        for v in visits_data:
            self._monitoring_visits[v["id"]] = MonitoringVisit(**v)

        # --- 12 KRI Signals ---
        signals_data = [
            {
                "id": "KRS-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "signal_category": SignalCategory.DATA_QUALITY,
                "kri_name": "Query Resolution Rate",
                "kri_value": 78.5,
                "threshold_value": 80.0,
                "breach_direction": "below",
                "risk_level": RiskLevel.LOW,
                "detection_date": now - timedelta(days=60),
                "consecutive_breaches": 1,
                "trend_direction": "stable",
                "benchmark_value": 88.0,
                "percentile_rank": 35.0,
                "acknowledged": True,
                "acknowledged_by": "Sarah Mitchell",
                "resolution_date": now - timedelta(days=45),
                "resolution_notes": "Site retrained on query resolution SOP.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "KRS-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "signal_category": SignalCategory.ENROLLMENT,
                "kri_name": "Enrollment Rate vs Target",
                "kri_value": 62.0,
                "threshold_value": 75.0,
                "breach_direction": "below",
                "risk_level": RiskLevel.MEDIUM,
                "detection_date": now - timedelta(days=45),
                "consecutive_breaches": 2,
                "trend_direction": "worsening",
                "benchmark_value": 95.0,
                "percentile_rank": 20.0,
                "acknowledged": True,
                "acknowledged_by": "David Park",
                "resolution_date": None,
                "resolution_notes": None,
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "KRS-003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "signal_category": SignalCategory.PROTOCOL_DEVIATION,
                "kri_name": "Protocol Deviation Rate",
                "kri_value": 7.2,
                "threshold_value": 5.0,
                "breach_direction": "above",
                "risk_level": RiskLevel.HIGH,
                "detection_date": now - timedelta(days=40),
                "consecutive_breaches": 3,
                "trend_direction": "worsening",
                "benchmark_value": 2.5,
                "percentile_rank": 92.0,
                "acknowledged": True,
                "acknowledged_by": "Jennifer Lee",
                "resolution_date": None,
                "resolution_notes": None,
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "KRS-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "signal_category": SignalCategory.SAFETY,
                "kri_name": "SAE Reporting Timeliness",
                "kri_value": 65.0,
                "threshold_value": 85.0,
                "breach_direction": "below",
                "risk_level": RiskLevel.CRITICAL,
                "detection_date": now - timedelta(days=35),
                "consecutive_breaches": 2,
                "trend_direction": "worsening",
                "benchmark_value": 95.0,
                "percentile_rank": 5.0,
                "acknowledged": True,
                "acknowledged_by": "Jennifer Lee",
                "resolution_date": None,
                "resolution_notes": None,
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "KRS-005",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "signal_category": SignalCategory.DATA_QUALITY,
                "kri_name": "Data Entry Lag",
                "kri_value": 12.5,
                "threshold_value": 7.0,
                "breach_direction": "above",
                "risk_level": RiskLevel.HIGH,
                "detection_date": now - timedelta(days=30),
                "consecutive_breaches": 4,
                "trend_direction": "worsening",
                "benchmark_value": 3.5,
                "percentile_rank": 95.0,
                "acknowledged": False,
                "acknowledged_by": None,
                "resolution_date": None,
                "resolution_notes": None,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "KRS-006",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "signal_category": SignalCategory.SAFETY,
                "kri_name": "AE Reporting Completeness",
                "kri_value": 68.0,
                "threshold_value": 90.0,
                "breach_direction": "below",
                "risk_level": RiskLevel.CRITICAL,
                "detection_date": now - timedelta(days=28),
                "consecutive_breaches": 3,
                "trend_direction": "worsening",
                "benchmark_value": 95.0,
                "percentile_rank": 3.0,
                "acknowledged": True,
                "acknowledged_by": "David Park",
                "resolution_date": None,
                "resolution_notes": None,
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "KRS-007",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "signal_category": SignalCategory.CONSENT,
                "kri_name": "Consent Form Compliance",
                "kri_value": 88.0,
                "threshold_value": 95.0,
                "breach_direction": "below",
                "risk_level": RiskLevel.MEDIUM,
                "detection_date": now - timedelta(days=25),
                "consecutive_breaches": 2,
                "trend_direction": "stable",
                "benchmark_value": 98.0,
                "percentile_rank": 15.0,
                "acknowledged": True,
                "acknowledged_by": "Jennifer Lee",
                "resolution_date": None,
                "resolution_notes": None,
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "KRS-008",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-107",
                "signal_category": SignalCategory.PROTOCOL_DEVIATION,
                "kri_name": "Randomization Error Rate",
                "kri_value": 6.5,
                "threshold_value": 3.0,
                "breach_direction": "above",
                "risk_level": RiskLevel.CRITICAL,
                "detection_date": now - timedelta(days=20),
                "consecutive_breaches": 3,
                "trend_direction": "worsening",
                "benchmark_value": 1.0,
                "percentile_rank": 98.0,
                "acknowledged": True,
                "acknowledged_by": "David Park",
                "resolution_date": None,
                "resolution_notes": None,
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "KRS-009",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-107",
                "signal_category": SignalCategory.SAFETY,
                "kri_name": "SAE Reporting Timeliness",
                "kri_value": 55.0,
                "threshold_value": 85.0,
                "breach_direction": "below",
                "risk_level": RiskLevel.CRITICAL,
                "detection_date": now - timedelta(days=18),
                "consecutive_breaches": 4,
                "trend_direction": "worsening",
                "benchmark_value": 95.0,
                "percentile_rank": 2.0,
                "acknowledged": True,
                "acknowledged_by": "David Park",
                "resolution_date": None,
                "resolution_notes": None,
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "KRS-010",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "signal_category": SignalCategory.OPERATIONAL,
                "kri_name": "Visit Completion Rate",
                "kri_value": 72.0,
                "threshold_value": 85.0,
                "breach_direction": "below",
                "risk_level": RiskLevel.MEDIUM,
                "detection_date": now - timedelta(days=15),
                "consecutive_breaches": 2,
                "trend_direction": "stable",
                "benchmark_value": 92.0,
                "percentile_rank": 25.0,
                "acknowledged": False,
                "acknowledged_by": None,
                "resolution_date": None,
                "resolution_notes": None,
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "KRS-011",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-108",
                "signal_category": SignalCategory.ENROLLMENT,
                "kri_name": "Screen Failure Rate",
                "kri_value": 42.0,
                "threshold_value": 40.0,
                "breach_direction": "above",
                "risk_level": RiskLevel.LOW,
                "detection_date": now - timedelta(days=10),
                "consecutive_breaches": 1,
                "trend_direction": "improving",
                "benchmark_value": 30.0,
                "percentile_rank": 55.0,
                "acknowledged": True,
                "acknowledged_by": "Sarah Mitchell",
                "resolution_date": now - timedelta(days=5),
                "resolution_notes": "Screening criteria clarified with site.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "KRS-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "signal_category": SignalCategory.REGULATORY,
                "kri_name": "Drug Accountability Compliance",
                "kri_value": 78.0,
                "threshold_value": 90.0,
                "breach_direction": "below",
                "risk_level": RiskLevel.HIGH,
                "detection_date": now - timedelta(days=8),
                "consecutive_breaches": 2,
                "trend_direction": "worsening",
                "benchmark_value": 96.0,
                "percentile_rank": 10.0,
                "acknowledged": False,
                "acknowledged_by": None,
                "resolution_date": None,
                "resolution_notes": None,
                "created_at": now - timedelta(days=8),
            },
        ]

        for s in signals_data:
            self._kri_signals[s["id"]] = KRISignal(**s)

        # --- 10 Site Risk Indicators ---
        risk_indicators_data = [
            {
                "id": "SRI-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "assessment_date": now - timedelta(days=7),
                "overall_risk_score": 18.0,
                "risk_level": RiskLevel.LOW,
                "enrollment_score": 15.0,
                "data_quality_score": 20.0,
                "safety_score": 10.0,
                "compliance_score": 22.0,
                "operational_score": 18.0,
                "active_signals": 0,
                "open_actions": 0,
                "days_since_last_review": 7,
                "triggered_visit_recommended": False,
                "assessed_by": "Sarah Mitchell",
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "SRI-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "assessment_date": now - timedelta(days=5),
                "overall_risk_score": 32.0,
                "risk_level": RiskLevel.MEDIUM,
                "enrollment_score": 45.0,
                "data_quality_score": 25.0,
                "safety_score": 20.0,
                "compliance_score": 30.0,
                "operational_score": 35.0,
                "active_signals": 1,
                "open_actions": 1,
                "days_since_last_review": 5,
                "triggered_visit_recommended": False,
                "assessed_by": "David Park",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "SRI-003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "assessment_date": now - timedelta(days=3),
                "overall_risk_score": 68.0,
                "risk_level": RiskLevel.HIGH,
                "enrollment_score": 55.0,
                "data_quality_score": 60.0,
                "safety_score": 80.0,
                "compliance_score": 72.0,
                "operational_score": 65.0,
                "active_signals": 2,
                "open_actions": 3,
                "days_since_last_review": 3,
                "triggered_visit_recommended": True,
                "assessed_by": "Jennifer Lee",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "SRI-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "assessment_date": now - timedelta(days=4),
                "overall_risk_score": 42.0,
                "risk_level": RiskLevel.MEDIUM,
                "enrollment_score": 35.0,
                "data_quality_score": 40.0,
                "safety_score": 30.0,
                "compliance_score": 50.0,
                "operational_score": 55.0,
                "active_signals": 1,
                "open_actions": 1,
                "days_since_last_review": 4,
                "triggered_visit_recommended": False,
                "assessed_by": "Sarah Mitchell",
                "created_at": now - timedelta(days=4),
            },
            {
                "id": "SRI-005",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "assessment_date": now - timedelta(days=2),
                "overall_risk_score": 82.0,
                "risk_level": RiskLevel.CRITICAL,
                "enrollment_score": 70.0,
                "data_quality_score": 88.0,
                "safety_score": 92.0,
                "compliance_score": 75.0,
                "operational_score": 80.0,
                "active_signals": 2,
                "open_actions": 4,
                "days_since_last_review": 2,
                "triggered_visit_recommended": True,
                "assessed_by": "David Park",
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "SRI-006",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "assessment_date": now - timedelta(days=1),
                "overall_risk_score": 58.0,
                "risk_level": RiskLevel.HIGH,
                "enrollment_score": 40.0,
                "data_quality_score": 50.0,
                "safety_score": 55.0,
                "compliance_score": 70.0,
                "operational_score": 65.0,
                "active_signals": 2,
                "open_actions": 2,
                "days_since_last_review": 1,
                "triggered_visit_recommended": False,
                "assessed_by": "Jennifer Lee",
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "SRI-007",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-107",
                "assessment_date": now - timedelta(days=1),
                "overall_risk_score": 90.0,
                "risk_level": RiskLevel.CRITICAL,
                "enrollment_score": 80.0,
                "data_quality_score": 85.0,
                "safety_score": 95.0,
                "compliance_score": 92.0,
                "operational_score": 88.0,
                "active_signals": 2,
                "open_actions": 5,
                "days_since_last_review": 1,
                "triggered_visit_recommended": True,
                "assessed_by": "David Park",
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "SRI-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-108",
                "assessment_date": now - timedelta(days=6),
                "overall_risk_score": 22.0,
                "risk_level": RiskLevel.LOW,
                "enrollment_score": 20.0,
                "data_quality_score": 18.0,
                "safety_score": 15.0,
                "compliance_score": 25.0,
                "operational_score": 28.0,
                "active_signals": 0,
                "open_actions": 0,
                "days_since_last_review": 6,
                "triggered_visit_recommended": False,
                "assessed_by": "Sarah Mitchell",
                "created_at": now - timedelta(days=6),
            },
            {
                "id": "SRI-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-101",
                "assessment_date": now - timedelta(days=10),
                "overall_risk_score": 25.0,
                "risk_level": RiskLevel.LOW,
                "enrollment_score": 22.0,
                "data_quality_score": 28.0,
                "safety_score": 18.0,
                "compliance_score": 30.0,
                "operational_score": 25.0,
                "active_signals": 0,
                "open_actions": 0,
                "days_since_last_review": 10,
                "triggered_visit_recommended": False,
                "assessed_by": "Jennifer Lee",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "SRI-010",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-105",
                "assessment_date": now - timedelta(days=30),
                "overall_risk_score": 55.0,
                "risk_level": RiskLevel.HIGH,
                "enrollment_score": 50.0,
                "data_quality_score": 60.0,
                "safety_score": 65.0,
                "compliance_score": 45.0,
                "operational_score": 50.0,
                "active_signals": 1,
                "open_actions": 2,
                "days_since_last_review": 30,
                "triggered_visit_recommended": False,
                "assessed_by": "David Park",
                "created_at": now - timedelta(days=30),
            },
        ]

        for ri in risk_indicators_data:
            self._site_risk_indicators[ri["id"]] = SiteRiskIndicator(**ri)

        # --- 12 Monitoring Actions ---
        actions_data = [
            {
                "id": "CMA-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "signal_id": "KRS-002",
                "visit_id": "CMV-002",
                "action_description": "Develop enrollment acceleration plan with site PI",
                "category": SignalCategory.ENROLLMENT,
                "priority": RiskLevel.MEDIUM,
                "status": ActionStatus.IN_PROGRESS,
                "assigned_to": "David Park",
                "due_date": now + timedelta(days=14),
                "completed_date": None,
                "response_text": "Site PI contacted. Meeting scheduled for next week.",
                "escalated_to": None,
                "escalation_date": None,
                "days_open": 30,
                "created_by": "Sarah Mitchell",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "CMA-002",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "signal_id": "KRS-003",
                "visit_id": "CMV-003",
                "action_description": "Implement protocol deviation reduction CAPA",
                "category": SignalCategory.PROTOCOL_DEVIATION,
                "priority": RiskLevel.HIGH,
                "status": ActionStatus.PENDING_RESPONSE,
                "assigned_to": "Jennifer Lee",
                "due_date": now + timedelta(days=7),
                "completed_date": None,
                "response_text": None,
                "escalated_to": None,
                "escalation_date": None,
                "days_open": 25,
                "created_by": "David Park",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "CMA-003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "signal_id": "KRS-004",
                "visit_id": "CMV-003",
                "action_description": "Retrain site staff on SAE reporting procedures",
                "category": SignalCategory.SAFETY,
                "priority": RiskLevel.CRITICAL,
                "status": ActionStatus.ESCALATED,
                "assigned_to": "Jennifer Lee",
                "due_date": now - timedelta(days=5),
                "completed_date": None,
                "response_text": "Training materials prepared.",
                "escalated_to": "Dr. Robert Chen (Medical Monitor)",
                "escalation_date": now - timedelta(days=3),
                "days_open": 28,
                "created_by": "Jennifer Lee",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "CMA-004",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "signal_id": "KRS-005",
                "visit_id": "CMV-005",
                "action_description": "Address data entry lag by implementing real-time entry procedures",
                "category": SignalCategory.DATA_QUALITY,
                "priority": RiskLevel.HIGH,
                "status": ActionStatus.OPEN,
                "assigned_to": "David Park",
                "due_date": now + timedelta(days=10),
                "completed_date": None,
                "response_text": None,
                "escalated_to": None,
                "escalation_date": None,
                "days_open": 20,
                "created_by": "David Park",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "CMA-005",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "signal_id": "KRS-006",
                "visit_id": "CMV-005",
                "action_description": "Urgent: remediate AE reporting completeness deficiency",
                "category": SignalCategory.SAFETY,
                "priority": RiskLevel.CRITICAL,
                "status": ActionStatus.ESCALATED,
                "assigned_to": "David Park",
                "due_date": now - timedelta(days=3),
                "completed_date": None,
                "response_text": "Immediate corrective action initiated.",
                "escalated_to": "Dr. Robert Chen (Medical Monitor)",
                "escalation_date": now - timedelta(days=1),
                "days_open": 22,
                "created_by": "Jennifer Lee",
                "created_at": now - timedelta(days=22),
            },
            {
                "id": "CMA-006",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "signal_id": "KRS-007",
                "visit_id": "CMV-006",
                "action_description": "Conduct consent form audit and retraining",
                "category": SignalCategory.CONSENT,
                "priority": RiskLevel.MEDIUM,
                "status": ActionStatus.IN_PROGRESS,
                "assigned_to": "Jennifer Lee",
                "due_date": now + timedelta(days=21),
                "completed_date": None,
                "response_text": "Audit initiated. Preliminary results expected next week.",
                "escalated_to": None,
                "escalation_date": None,
                "days_open": 15,
                "created_by": "Jennifer Lee",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "CMA-007",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-107",
                "signal_id": "KRS-008",
                "visit_id": "CMV-007",
                "action_description": "Investigate and remediate randomization errors",
                "category": SignalCategory.PROTOCOL_DEVIATION,
                "priority": RiskLevel.CRITICAL,
                "status": ActionStatus.OPEN,
                "assigned_to": "David Park",
                "due_date": now + timedelta(days=5),
                "completed_date": None,
                "response_text": None,
                "escalated_to": None,
                "escalation_date": None,
                "days_open": 12,
                "created_by": "David Park",
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "CMA-008",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-107",
                "signal_id": "KRS-009",
                "visit_id": "CMV-007",
                "action_description": "Implement immediate SAE reporting corrective action",
                "category": SignalCategory.SAFETY,
                "priority": RiskLevel.CRITICAL,
                "status": ActionStatus.OPEN,
                "assigned_to": "David Park",
                "due_date": now + timedelta(days=3),
                "completed_date": None,
                "response_text": None,
                "escalated_to": None,
                "escalation_date": None,
                "days_open": 10,
                "created_by": "David Park",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "CMA-009",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "signal_id": "KRS-001",
                "visit_id": "CMV-001",
                "action_description": "Verify query resolution rate improvement after retraining",
                "category": SignalCategory.DATA_QUALITY,
                "priority": RiskLevel.LOW,
                "status": ActionStatus.RESOLVED,
                "assigned_to": "Sarah Mitchell",
                "due_date": now - timedelta(days=30),
                "completed_date": now - timedelta(days=35),
                "response_text": "Query resolution rate improved to 92% after retraining.",
                "escalated_to": None,
                "escalation_date": None,
                "days_open": 25,
                "created_by": "Sarah Mitchell",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "CMA-010",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "signal_id": "KRS-010",
                "visit_id": "CMV-004",
                "action_description": "Review and improve visit scheduling process",
                "category": SignalCategory.OPERATIONAL,
                "priority": RiskLevel.MEDIUM,
                "status": ActionStatus.IN_PROGRESS,
                "assigned_to": "Sarah Mitchell",
                "due_date": now + timedelta(days=28),
                "completed_date": None,
                "response_text": "Working with site coordinator on scheduling optimization.",
                "escalated_to": None,
                "escalation_date": None,
                "days_open": 10,
                "created_by": "Sarah Mitchell",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "CMA-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "signal_id": "KRS-012",
                "visit_id": "CMV-006",
                "action_description": "Conduct drug accountability reconciliation audit",
                "category": SignalCategory.REGULATORY,
                "priority": RiskLevel.HIGH,
                "status": ActionStatus.OPEN,
                "assigned_to": "Jennifer Lee",
                "due_date": now + timedelta(days=14),
                "completed_date": None,
                "response_text": None,
                "escalated_to": None,
                "escalation_date": None,
                "days_open": 5,
                "created_by": "Jennifer Lee",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "CMA-012",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-108",
                "signal_id": "KRS-011",
                "visit_id": None,
                "action_description": "Monitor screen failure rate trend over next cycle",
                "category": SignalCategory.ENROLLMENT,
                "priority": RiskLevel.LOW,
                "status": ActionStatus.CLOSED,
                "assigned_to": "Sarah Mitchell",
                "due_date": now - timedelta(days=3),
                "completed_date": now - timedelta(days=5),
                "response_text": "Screen failure rate normalized after criteria clarification.",
                "escalated_to": None,
                "escalation_date": None,
                "days_open": 5,
                "created_by": "Sarah Mitchell",
                "created_at": now - timedelta(days=8),
            },
        ]

        for a in actions_data:
            self._monitoring_actions[a["id"]] = MonitoringAction(**a)

        # --- 10 Central Reviews ---
        reviews_data = [
            {
                "id": "CRV-001",
                "trial_id": EYLEA_TRIAL,
                "review_period_start": now - timedelta(days=120),
                "review_period_end": now - timedelta(days=91),
                "reviewer": "Sarah Mitchell",
                "review_date": now - timedelta(days=88),
                "sites_reviewed": 4,
                "total_signals_reviewed": 3,
                "new_actions_created": 1,
                "escalations": 0,
                "triggered_visits_recommended": 0,
                "summary": "Q3 central review. All EYLEA sites performing within acceptable range.",
                "attendees": ["Sarah Mitchell", "David Park", "Dr. Lisa Wang"],
                "minutes_document_id": "DOC-CR-001",
                "next_review_date": now - timedelta(days=58),
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "CRV-002",
                "trial_id": DUPIXENT_TRIAL,
                "review_period_start": now - timedelta(days=90),
                "review_period_end": now - timedelta(days=61),
                "reviewer": "Jennifer Lee",
                "review_date": now - timedelta(days=58),
                "sites_reviewed": 3,
                "total_signals_reviewed": 5,
                "new_actions_created": 3,
                "escalations": 1,
                "triggered_visits_recommended": 1,
                "summary": "DUPIXENT trial showing elevated risk at SITE-103. Protocol deviation pattern identified.",
                "attendees": ["Jennifer Lee", "David Park", "Dr. Robert Chen"],
                "minutes_document_id": "DOC-CR-002",
                "next_review_date": now - timedelta(days=28),
                "created_at": now - timedelta(days=58),
            },
            {
                "id": "CRV-003",
                "trial_id": LIBTAYO_TRIAL,
                "review_period_start": now - timedelta(days=60),
                "review_period_end": now - timedelta(days=31),
                "reviewer": "David Park",
                "review_date": now - timedelta(days=28),
                "sites_reviewed": 3,
                "total_signals_reviewed": 6,
                "new_actions_created": 4,
                "escalations": 2,
                "triggered_visits_recommended": 2,
                "summary": "LIBTAYO trial critical review. SITE-105 and SITE-106 require immediate intervention.",
                "attendees": ["David Park", "Jennifer Lee", "Dr. Robert Chen", "Dr. Lisa Wang"],
                "minutes_document_id": "DOC-CR-003",
                "next_review_date": now - timedelta(days=7),
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "CRV-004",
                "trial_id": EYLEA_TRIAL,
                "review_period_start": now - timedelta(days=90),
                "review_period_end": now - timedelta(days=61),
                "reviewer": "Sarah Mitchell",
                "review_date": now - timedelta(days=55),
                "sites_reviewed": 4,
                "total_signals_reviewed": 2,
                "new_actions_created": 1,
                "escalations": 0,
                "triggered_visits_recommended": 0,
                "summary": "EYLEA Q4 review. Minor enrollment signal at SITE-102 being monitored.",
                "attendees": ["Sarah Mitchell", "Dr. Lisa Wang"],
                "minutes_document_id": "DOC-CR-004",
                "next_review_date": now - timedelta(days=25),
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "CRV-005",
                "trial_id": DUPIXENT_TRIAL,
                "review_period_start": now - timedelta(days=60),
                "review_period_end": now - timedelta(days=31),
                "reviewer": "Jennifer Lee",
                "review_date": now - timedelta(days=25),
                "sites_reviewed": 3,
                "total_signals_reviewed": 4,
                "new_actions_created": 2,
                "escalations": 1,
                "triggered_visits_recommended": 0,
                "summary": "DUPIXENT monthly review. SAE reporting concerns at SITE-103 escalated.",
                "attendees": ["Jennifer Lee", "Dr. Robert Chen"],
                "minutes_document_id": "DOC-CR-005",
                "next_review_date": now + timedelta(days=5),
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "CRV-006",
                "trial_id": EYLEA_TRIAL,
                "review_period_start": now - timedelta(days=60),
                "review_period_end": now - timedelta(days=31),
                "reviewer": "David Park",
                "review_date": now - timedelta(days=20),
                "sites_reviewed": 4,
                "total_signals_reviewed": 4,
                "new_actions_created": 2,
                "escalations": 1,
                "triggered_visits_recommended": 1,
                "summary": "EYLEA review flagging critical issues at SITE-107. Immediate for-cause visit scheduled.",
                "attendees": ["David Park", "Sarah Mitchell", "Dr. Lisa Wang", "Dr. Robert Chen"],
                "minutes_document_id": "DOC-CR-006",
                "next_review_date": now + timedelta(days=10),
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "CRV-007",
                "trial_id": LIBTAYO_TRIAL,
                "review_period_start": now - timedelta(days=30),
                "review_period_end": now - timedelta(days=1),
                "reviewer": "Jennifer Lee",
                "review_date": now - timedelta(days=7),
                "sites_reviewed": 3,
                "total_signals_reviewed": 5,
                "new_actions_created": 3,
                "escalations": 2,
                "triggered_visits_recommended": 1,
                "summary": "LIBTAYO emergency review. SITE-105 AE reporting and SITE-106 regulatory compliance critical.",
                "attendees": ["Jennifer Lee", "David Park", "Dr. Robert Chen"],
                "minutes_document_id": "DOC-CR-007",
                "next_review_date": now + timedelta(days=7),
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "CRV-008",
                "trial_id": EYLEA_TRIAL,
                "review_period_start": now - timedelta(days=30),
                "review_period_end": now - timedelta(days=1),
                "reviewer": "David Park",
                "review_date": now - timedelta(days=3),
                "sites_reviewed": 4,
                "total_signals_reviewed": 3,
                "new_actions_created": 2,
                "escalations": 1,
                "triggered_visits_recommended": 1,
                "summary": "EYLEA monthly. SITE-107 remains critical. Second for-cause visit planned.",
                "attendees": ["David Park", "Sarah Mitchell"],
                "minutes_document_id": "DOC-CR-008",
                "next_review_date": now + timedelta(days=14),
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "CRV-009",
                "trial_id": DUPIXENT_TRIAL,
                "review_period_start": now - timedelta(days=30),
                "review_period_end": now - timedelta(days=1),
                "reviewer": "Sarah Mitchell",
                "review_date": now - timedelta(days=2),
                "sites_reviewed": 3,
                "total_signals_reviewed": 3,
                "new_actions_created": 1,
                "escalations": 0,
                "triggered_visits_recommended": 0,
                "summary": "DUPIXENT monthly review. SITE-104 visit completion improving. SITE-108 stable.",
                "attendees": ["Sarah Mitchell", "Jennifer Lee"],
                "minutes_document_id": "DOC-CR-009",
                "next_review_date": now + timedelta(days=28),
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "CRV-010",
                "trial_id": LIBTAYO_TRIAL,
                "review_period_start": now - timedelta(days=14),
                "review_period_end": now,
                "reviewer": "David Park",
                "review_date": now,
                "sites_reviewed": 3,
                "total_signals_reviewed": 4,
                "new_actions_created": 2,
                "escalations": 1,
                "triggered_visits_recommended": 1,
                "summary": "LIBTAYO bi-weekly follow-up. SITE-105 showing initial improvement. SITE-106 drug accountability under review.",
                "attendees": ["David Park", "Jennifer Lee", "Dr. Robert Chen"],
                "minutes_document_id": None,
                "next_review_date": now + timedelta(days=14),
                "created_at": now,
            },
        ]

        for r in reviews_data:
            self._central_reviews[r["id"]] = CentralReview(**r)

    # ------------------------------------------------------------------
    # Monitoring Visits
    # ------------------------------------------------------------------

    def list_monitoring_visits(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[MonitoringVisit]:
        """List monitoring visits with optional trial_id filter."""
        with self._lock:
            result = list(self._monitoring_visits.values())

        if trial_id is not None:
            result = [v for v in result if v.trial_id == trial_id]

        return sorted(result, key=lambda v: v.visit_date, reverse=True)

    def get_monitoring_visit(self, visit_id: str) -> MonitoringVisit | None:
        """Get a single monitoring visit by ID."""
        with self._lock:
            return self._monitoring_visits.get(visit_id)

    def create_monitoring_visit(self, payload: MonitoringVisitCreate) -> MonitoringVisit:
        """Create a new monitoring visit."""
        now = datetime.now(timezone.utc)
        visit_id = f"CMV-{uuid4().hex[:8].upper()}"
        visit = MonitoringVisit(
            id=visit_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            monitoring_type=payload.monitoring_type,
            visit_date=now,
            completed_date=None,
            monitor=payload.monitor,
            subjects_reviewed=payload.subjects_reviewed,
            queries_generated=0,
            findings_count=0,
            critical_findings=0,
            data_points_reviewed=0,
            deviations_identified=0,
            review_outcome=ReviewOutcome.NO_ACTION,
            follow_up_required=False,
            report_finalized=False,
            next_review_date=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._monitoring_visits[visit_id] = visit
        logger.info("Created monitoring visit %s for site %s", visit_id, payload.site_id)
        return visit

    def update_monitoring_visit(
        self, visit_id: str, payload: MonitoringVisitUpdate
    ) -> MonitoringVisit | None:
        """Update an existing monitoring visit."""
        with self._lock:
            existing = self._monitoring_visits.get(visit_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MonitoringVisit(**data)
            self._monitoring_visits[visit_id] = updated
        return updated

    def delete_monitoring_visit(self, visit_id: str) -> bool:
        """Delete a monitoring visit. Returns True if deleted, False if not found."""
        with self._lock:
            if visit_id in self._monitoring_visits:
                del self._monitoring_visits[visit_id]
                return True
            return False

    # ------------------------------------------------------------------
    # KRI Signals
    # ------------------------------------------------------------------

    def list_kri_signals(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[KRISignal]:
        """List KRI signals with optional trial_id filter."""
        with self._lock:
            result = list(self._kri_signals.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]

        return sorted(result, key=lambda s: s.detection_date, reverse=True)

    def get_kri_signal(self, signal_id: str) -> KRISignal | None:
        """Get a single KRI signal by ID."""
        with self._lock:
            return self._kri_signals.get(signal_id)

    def create_kri_signal(self, payload: KRISignalCreate) -> KRISignal:
        """Create a new KRI signal."""
        now = datetime.now(timezone.utc)
        signal_id = f"KRS-{uuid4().hex[:8].upper()}"
        signal = KRISignal(
            id=signal_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            signal_category=payload.signal_category,
            kri_name=payload.kri_name,
            kri_value=payload.kri_value,
            threshold_value=payload.threshold_value,
            breach_direction=payload.breach_direction,
            risk_level=RiskLevel.MEDIUM,
            detection_date=now,
            consecutive_breaches=1,
            trend_direction=None,
            benchmark_value=None,
            percentile_rank=None,
            acknowledged=False,
            acknowledged_by=None,
            resolution_date=None,
            resolution_notes=None,
            created_at=now,
        )
        with self._lock:
            self._kri_signals[signal_id] = signal
        logger.info("Created KRI signal %s: %s", signal_id, payload.kri_name)
        return signal

    def update_kri_signal(
        self, signal_id: str, payload: KRISignalUpdate
    ) -> KRISignal | None:
        """Update an existing KRI signal."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._kri_signals.get(signal_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set resolution_date when acknowledged and resolution notes provided
            if "resolution_notes" in updates and updates["resolution_notes"] and existing.resolution_date is None:
                data["resolution_date"] = now

            data.update(updates)
            updated = KRISignal(**data)
            self._kri_signals[signal_id] = updated
        return updated

    def delete_kri_signal(self, signal_id: str) -> bool:
        """Delete a KRI signal. Returns True if deleted, False if not found."""
        with self._lock:
            if signal_id in self._kri_signals:
                del self._kri_signals[signal_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Site Risk Indicators
    # ------------------------------------------------------------------

    def list_site_risk_indicators(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[SiteRiskIndicator]:
        """List site risk indicators with optional trial_id filter."""
        with self._lock:
            result = list(self._site_risk_indicators.values())

        if trial_id is not None:
            result = [ri for ri in result if ri.trial_id == trial_id]

        return sorted(result, key=lambda ri: ri.overall_risk_score, reverse=True)

    def get_site_risk_indicator(self, indicator_id: str) -> SiteRiskIndicator | None:
        """Get a single site risk indicator by ID."""
        with self._lock:
            return self._site_risk_indicators.get(indicator_id)

    def create_site_risk_indicator(
        self, payload: SiteRiskIndicatorCreate
    ) -> SiteRiskIndicator:
        """Create a new site risk indicator."""
        now = datetime.now(timezone.utc)
        indicator_id = f"SRI-{uuid4().hex[:8].upper()}"

        # Calculate overall risk score as average of component scores
        scores = [
            payload.enrollment_score,
            payload.data_quality_score,
            payload.safety_score,
            payload.compliance_score,
        ]
        overall = round(sum(scores) / len(scores), 1)

        # Determine risk level from overall score
        if overall < 25:
            risk_level = RiskLevel.LOW
        elif overall < 50:
            risk_level = RiskLevel.MEDIUM
        elif overall < 75:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.CRITICAL

        indicator = SiteRiskIndicator(
            id=indicator_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            assessment_date=now,
            overall_risk_score=overall,
            risk_level=risk_level,
            enrollment_score=payload.enrollment_score,
            data_quality_score=payload.data_quality_score,
            safety_score=payload.safety_score,
            compliance_score=payload.compliance_score,
            operational_score=0.0,
            active_signals=0,
            open_actions=0,
            days_since_last_review=0,
            triggered_visit_recommended=False,
            assessed_by=payload.assessed_by,
            created_at=now,
        )
        with self._lock:
            self._site_risk_indicators[indicator_id] = indicator
        logger.info(
            "Created site risk indicator %s for site %s (score=%.1f)",
            indicator_id, payload.site_id, overall,
        )
        return indicator

    def update_site_risk_indicator(
        self, indicator_id: str, payload: SiteRiskIndicatorUpdate
    ) -> SiteRiskIndicator | None:
        """Update an existing site risk indicator."""
        with self._lock:
            existing = self._site_risk_indicators.get(indicator_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SiteRiskIndicator(**data)
            self._site_risk_indicators[indicator_id] = updated
        return updated

    def delete_site_risk_indicator(self, indicator_id: str) -> bool:
        """Delete a site risk indicator. Returns True if deleted, False if not found."""
        with self._lock:
            if indicator_id in self._site_risk_indicators:
                del self._site_risk_indicators[indicator_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Monitoring Actions
    # ------------------------------------------------------------------

    def list_monitoring_actions(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[MonitoringAction]:
        """List monitoring actions with optional trial_id filter."""
        with self._lock:
            result = list(self._monitoring_actions.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]

        return sorted(result, key=lambda a: a.created_at, reverse=True)

    def get_monitoring_action(self, action_id: str) -> MonitoringAction | None:
        """Get a single monitoring action by ID."""
        with self._lock:
            return self._monitoring_actions.get(action_id)

    def create_monitoring_action(self, payload: MonitoringActionCreate) -> MonitoringAction:
        """Create a new monitoring action."""
        now = datetime.now(timezone.utc)
        action_id = f"CMA-{uuid4().hex[:8].upper()}"
        action = MonitoringAction(
            id=action_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            signal_id=payload.signal_id,
            visit_id=payload.visit_id,
            action_description=payload.action_description,
            category=payload.category,
            priority=RiskLevel.MEDIUM,
            status=ActionStatus.OPEN,
            assigned_to=payload.assigned_to,
            due_date=payload.due_date,
            completed_date=None,
            response_text=None,
            escalated_to=None,
            escalation_date=None,
            days_open=0,
            created_by=payload.created_by,
            created_at=now,
        )
        with self._lock:
            self._monitoring_actions[action_id] = action
        logger.info("Created monitoring action %s for site %s", action_id, payload.site_id)
        return action

    def update_monitoring_action(
        self, action_id: str, payload: MonitoringActionUpdate
    ) -> MonitoringAction | None:
        """Update an existing monitoring action."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._monitoring_actions.get(action_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set completed_date when status changes to resolved/closed
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = ActionStatus(new_status)
                if new_status in (ActionStatus.RESOLVED, ActionStatus.CLOSED) and existing.completed_date is None:
                    data["completed_date"] = now

                # Auto-set escalation_date when status goes to escalated
                if new_status == ActionStatus.ESCALATED and existing.escalation_date is None:
                    data["escalation_date"] = now

            data.update(updates)
            updated = MonitoringAction(**data)
            self._monitoring_actions[action_id] = updated
        return updated

    def delete_monitoring_action(self, action_id: str) -> bool:
        """Delete a monitoring action. Returns True if deleted, False if not found."""
        with self._lock:
            if action_id in self._monitoring_actions:
                del self._monitoring_actions[action_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Central Reviews
    # ------------------------------------------------------------------

    def list_central_reviews(
        self,
        *,
        trial_id: str | None = None,
    ) -> list[CentralReview]:
        """List central reviews with optional trial_id filter."""
        with self._lock:
            result = list(self._central_reviews.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]

        return sorted(result, key=lambda r: r.review_date, reverse=True)

    def get_central_review(self, review_id: str) -> CentralReview | None:
        """Get a single central review by ID."""
        with self._lock:
            return self._central_reviews.get(review_id)

    def create_central_review(self, payload: CentralReviewCreate) -> CentralReview:
        """Create a new central review."""
        now = datetime.now(timezone.utc)
        review_id = f"CRV-{uuid4().hex[:8].upper()}"
        review = CentralReview(
            id=review_id,
            trial_id=payload.trial_id,
            review_period_start=payload.review_period_start,
            review_period_end=payload.review_period_end,
            reviewer=payload.reviewer,
            review_date=now,
            sites_reviewed=payload.sites_reviewed,
            total_signals_reviewed=0,
            new_actions_created=0,
            escalations=0,
            triggered_visits_recommended=0,
            summary=None,
            attendees=[],
            minutes_document_id=None,
            next_review_date=None,
            created_at=now,
        )
        with self._lock:
            self._central_reviews[review_id] = review
        logger.info("Created central review %s for trial %s", review_id, payload.trial_id)
        return review

    def update_central_review(
        self, review_id: str, payload: CentralReviewUpdate
    ) -> CentralReview | None:
        """Update an existing central review."""
        with self._lock:
            existing = self._central_reviews.get(review_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CentralReview(**data)
            self._central_reviews[review_id] = updated
        return updated

    def delete_central_review(self, review_id: str) -> bool:
        """Delete a central review. Returns True if deleted, False if not found."""
        with self._lock:
            if review_id in self._central_reviews:
                del self._central_reviews[review_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> CentralMonitoringMetrics:
        """Compute aggregated central monitoring operational metrics."""
        now = datetime.now(timezone.utc)

        with self._lock:
            visits = list(self._monitoring_visits.values())
            signals = list(self._kri_signals.values())
            indicators = list(self._site_risk_indicators.values())
            actions = list(self._monitoring_actions.values())
            reviews = list(self._central_reviews.values())

        # Visits by type
        visits_by_type: dict[str, int] = {}
        for v in visits:
            key = v.monitoring_type.value
            visits_by_type[key] = visits_by_type.get(key, 0) + 1

        # Visits by outcome
        visits_by_outcome: dict[str, int] = {}
        for v in visits:
            key = v.review_outcome.value
            visits_by_outcome[key] = visits_by_outcome.get(key, 0) + 1

        # Signals by category
        signals_by_category: dict[str, int] = {}
        for s in signals:
            key = s.signal_category.value
            signals_by_category[key] = signals_by_category.get(key, 0) + 1

        # Signals by risk level
        signals_by_risk: dict[str, int] = {}
        for s in signals:
            key = s.risk_level.value
            signals_by_risk[key] = signals_by_risk.get(key, 0) + 1

        # Unresolved signals
        unresolved_signals = sum(1 for s in signals if s.resolution_date is None)

        # Actions by status
        actions_by_status: dict[str, int] = {}
        for a in actions:
            key = a.status.value
            actions_by_status[key] = actions_by_status.get(key, 0) + 1

        # Overdue actions
        overdue_actions = sum(
            1 for a in actions
            if a.status in (ActionStatus.OPEN, ActionStatus.IN_PROGRESS, ActionStatus.PENDING_RESPONSE)
            and a.due_date < now
        )

        # Average action resolution days (for resolved/closed actions)
        resolved_actions = [
            a for a in actions
            if a.completed_date is not None and a.created_at is not None
        ]
        if resolved_actions:
            total_days = sum(
                (a.completed_date - a.created_at).days
                for a in resolved_actions
            )
            avg_resolution = round(total_days / len(resolved_actions), 1)
        else:
            avg_resolution = 0.0

        # Sites at high risk (high or critical)
        sites_at_high_risk = sum(
            1 for ri in indicators
            if ri.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        )

        return CentralMonitoringMetrics(
            total_visits=len(visits),
            visits_by_type=visits_by_type,
            visits_by_outcome=visits_by_outcome,
            total_signals=len(signals),
            signals_by_category=signals_by_category,
            signals_by_risk=signals_by_risk,
            unresolved_signals=unresolved_signals,
            total_actions=len(actions),
            actions_by_status=actions_by_status,
            overdue_actions=overdue_actions,
            avg_action_resolution_days=avg_resolution,
            total_reviews=len(reviews),
            sites_at_high_risk=sites_at_high_risk,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: CentralMonitoringService | None = None
_instance_lock = threading.Lock()


def get_central_monitoring_service() -> CentralMonitoringService:
    """Return the singleton CentralMonitoringService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = CentralMonitoringService()
    return _instance


def reset_central_monitoring_service() -> CentralMonitoringService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = CentralMonitoringService()
    return _instance
