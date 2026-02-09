"""Risk-Based Monitoring (RBM) & Central Monitoring Service (CLINICAL-7).

Manages risk-based monitoring operations including KRI definitions, site risk
scoring with weighted KRI aggregation, KRI data point tracking, monitoring plan
lifecycle, finding management, central monitoring alerts, and auto-escalation.

Usage:
    from app.services.risk_based_monitoring_service import (
        get_rbm_service,
    )

    svc = get_rbm_service()
    scores = svc.list_site_risk_scores()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.risk_based_monitoring import (
    AlertResolve,
    CentralMonitoringAlert,
    FindingCategory,
    FindingCreate,
    FindingStatus,
    FindingUpdate,
    KRICategory,
    KRICreate,
    KRIDataPoint,
    KRIDataPointCreate,
    KRIScore,
    KRIStatus,
    KRIUpdate,
    KeyRiskIndicator,
    MonitoringAction,
    MonitoringFinding,
    MonitoringPlan,
    MonitoringPlanCreate,
    MonitoringPlanStatus,
    MonitoringPlanUpdate,
    MonitoringScheduleRecommendation,
    MonitoringVisitComplete,
    MonitoringVisitType,
    RBMMetrics,
    RiskLevel,
    SiteRiskScore,
    Trend,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# Risk level thresholds
RISK_THRESHOLD_LOW = 25.0
RISK_THRESHOLD_MEDIUM = 50.0
RISK_THRESHOLD_HIGH = 75.0

# Auto-escalation: if 3+ KRIs are red, site goes to critical
AUTO_ESCALATION_RED_COUNT = 3

# Finding overdue threshold
FINDING_OVERDUE_DAYS = 30


class RBMService:
    """In-memory Risk-Based Monitoring engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._kris: dict[str, KeyRiskIndicator] = {}
        self._site_risk_scores: dict[str, SiteRiskScore] = {}
        self._kri_data_points: dict[str, KRIDataPoint] = {}
        self._monitoring_plans: dict[str, MonitoringPlan] = {}
        self._findings: dict[str, MonitoringFinding] = {}
        self._alerts: dict[str, CentralMonitoringAlert] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic RBM data across clinical trial sites."""
        now = datetime.now(timezone.utc)

        # --- 12 Key Risk Indicators ---
        kris_data = [
            {
                "id": "KRI-001",
                "name": "SAE Reporting Timeliness",
                "category": KRICategory.SAFETY,
                "description": "Percentage of SAEs reported within 24 hours of site awareness",
                "threshold_yellow": 85.0,
                "threshold_red": 70.0,
                "unit": "%",
                "weight": 3.0,
                "active": True,
            },
            {
                "id": "KRI-002",
                "name": "Query Resolution Rate",
                "category": KRICategory.DATA_QUALITY,
                "description": "Percentage of data queries resolved within 5 business days",
                "threshold_yellow": 80.0,
                "threshold_red": 60.0,
                "unit": "%",
                "weight": 2.0,
                "active": True,
            },
            {
                "id": "KRI-003",
                "name": "Protocol Deviation Rate",
                "category": KRICategory.PROTOCOL_COMPLIANCE,
                "description": "Number of major protocol deviations per 100 patient-months",
                "threshold_yellow": 3.0,
                "threshold_red": 6.0,
                "unit": "per 100 pt-mo",
                "weight": 2.5,
                "active": True,
            },
            {
                "id": "KRI-004",
                "name": "Consent Form Compliance",
                "category": KRICategory.PROTOCOL_COMPLIANCE,
                "description": "Percentage of subjects with properly executed informed consent",
                "threshold_yellow": 95.0,
                "threshold_red": 90.0,
                "unit": "%",
                "weight": 3.0,
                "active": True,
            },
            {
                "id": "KRI-005",
                "name": "Enrollment Rate vs Target",
                "category": KRICategory.ENROLLMENT,
                "description": "Ratio of actual to target enrollment rate",
                "threshold_yellow": 75.0,
                "threshold_red": 50.0,
                "unit": "%",
                "weight": 1.5,
                "active": True,
            },
            {
                "id": "KRI-006",
                "name": "Data Entry Lag",
                "category": KRICategory.DATA_QUALITY,
                "description": "Median number of days between visit and data entry",
                "threshold_yellow": 5.0,
                "threshold_red": 10.0,
                "unit": "days",
                "weight": 1.5,
                "active": True,
            },
            {
                "id": "KRI-007",
                "name": "AE Reporting Completeness",
                "category": KRICategory.SAFETY,
                "description": "Percentage of AEs with complete required fields",
                "threshold_yellow": 90.0,
                "threshold_red": 75.0,
                "unit": "%",
                "weight": 2.5,
                "active": True,
            },
            {
                "id": "KRI-008",
                "name": "Source Data Verification Rate",
                "category": KRICategory.DATA_QUALITY,
                "description": "Percentage of critical data points verified against source",
                "threshold_yellow": 85.0,
                "threshold_red": 70.0,
                "unit": "%",
                "weight": 2.0,
                "active": True,
            },
            {
                "id": "KRI-009",
                "name": "Screen Failure Rate",
                "category": KRICategory.ENROLLMENT,
                "description": "Percentage of screened patients who fail screening",
                "threshold_yellow": 40.0,
                "threshold_red": 60.0,
                "unit": "%",
                "weight": 1.0,
                "active": True,
            },
            {
                "id": "KRI-010",
                "name": "Randomization Error Rate",
                "category": KRICategory.PROTOCOL_COMPLIANCE,
                "description": "Percentage of randomization errors per site",
                "threshold_yellow": 2.0,
                "threshold_red": 5.0,
                "unit": "%",
                "weight": 2.0,
                "active": True,
            },
            {
                "id": "KRI-011",
                "name": "Drug Accountability Compliance",
                "category": KRICategory.SITE_MANAGEMENT,
                "description": "Percentage of IP accountability logs correctly maintained",
                "threshold_yellow": 90.0,
                "threshold_red": 80.0,
                "unit": "%",
                "weight": 2.0,
                "active": True,
            },
            {
                "id": "KRI-012",
                "name": "Visit Completion Rate",
                "category": KRICategory.SITE_MANAGEMENT,
                "description": "Percentage of scheduled visits completed within window",
                "threshold_yellow": 85.0,
                "threshold_red": 70.0,
                "unit": "%",
                "weight": 1.5,
                "active": True,
            },
        ]

        for k in kris_data:
            self._kris[k["id"]] = KeyRiskIndicator(**k)

        # --- 8 Site Risk Profiles ---
        sites_data = [
            {
                "site_id": "SITE-101",
                "site_name": "Memorial Hermann Hospital",
                "overall_risk_score": 22.0,
                "risk_level": RiskLevel.LOW,
                "kri_scores": [
                    KRIScore(kri_id="KRI-001", kri_name="SAE Reporting Timeliness", value=95.0, status=KRIStatus.GREEN, score=10.0),
                    KRIScore(kri_id="KRI-002", kri_name="Query Resolution Rate", value=92.0, status=KRIStatus.GREEN, score=8.0),
                    KRIScore(kri_id="KRI-003", kri_name="Protocol Deviation Rate", value=1.2, status=KRIStatus.GREEN, score=5.0),
                    KRIScore(kri_id="KRI-005", kri_name="Enrollment Rate vs Target", value=110.0, status=KRIStatus.GREEN, score=0.0),
                ],
                "last_assessed": now - timedelta(days=7),
                "trend": Trend.STABLE,
            },
            {
                "site_id": "SITE-102",
                "site_name": "Cleveland Clinic Foundation",
                "overall_risk_score": 18.0,
                "risk_level": RiskLevel.LOW,
                "kri_scores": [
                    KRIScore(kri_id="KRI-001", kri_name="SAE Reporting Timeliness", value=98.0, status=KRIStatus.GREEN, score=5.0),
                    KRIScore(kri_id="KRI-002", kri_name="Query Resolution Rate", value=95.0, status=KRIStatus.GREEN, score=5.0),
                    KRIScore(kri_id="KRI-003", kri_name="Protocol Deviation Rate", value=0.8, status=KRIStatus.GREEN, score=3.0),
                    KRIScore(kri_id="KRI-005", kri_name="Enrollment Rate vs Target", value=95.0, status=KRIStatus.GREEN, score=5.0),
                ],
                "last_assessed": now - timedelta(days=5),
                "trend": Trend.IMPROVING,
            },
            {
                "site_id": "SITE-103",
                "site_name": "Johns Hopkins Research Center",
                "overall_risk_score": 38.0,
                "risk_level": RiskLevel.MEDIUM,
                "kri_scores": [
                    KRIScore(kri_id="KRI-001", kri_name="SAE Reporting Timeliness", value=82.0, status=KRIStatus.YELLOW, score=30.0),
                    KRIScore(kri_id="KRI-002", kri_name="Query Resolution Rate", value=78.0, status=KRIStatus.YELLOW, score=25.0),
                    KRIScore(kri_id="KRI-003", kri_name="Protocol Deviation Rate", value=3.5, status=KRIStatus.YELLOW, score=35.0),
                    KRIScore(kri_id="KRI-005", kri_name="Enrollment Rate vs Target", value=72.0, status=KRIStatus.YELLOW, score=30.0),
                ],
                "last_assessed": now - timedelta(days=3),
                "trend": Trend.WORSENING,
            },
            {
                "site_id": "SITE-104",
                "site_name": "Mayo Clinic Jacksonville",
                "overall_risk_score": 45.0,
                "risk_level": RiskLevel.MEDIUM,
                "kri_scores": [
                    KRIScore(kri_id="KRI-001", kri_name="SAE Reporting Timeliness", value=80.0, status=KRIStatus.YELLOW, score=35.0),
                    KRIScore(kri_id="KRI-002", kri_name="Query Resolution Rate", value=72.0, status=KRIStatus.YELLOW, score=40.0),
                    KRIScore(kri_id="KRI-003", kri_name="Protocol Deviation Rate", value=4.2, status=KRIStatus.YELLOW, score=45.0),
                    KRIScore(kri_id="KRI-006", kri_name="Data Entry Lag", value=7.0, status=KRIStatus.YELLOW, score=45.0),
                ],
                "last_assessed": now - timedelta(days=4),
                "trend": Trend.STABLE,
            },
            {
                "site_id": "SITE-105",
                "site_name": "Duke Clinical Research Institute",
                "overall_risk_score": 62.0,
                "risk_level": RiskLevel.HIGH,
                "kri_scores": [
                    KRIScore(kri_id="KRI-001", kri_name="SAE Reporting Timeliness", value=68.0, status=KRIStatus.RED, score=70.0),
                    KRIScore(kri_id="KRI-002", kri_name="Query Resolution Rate", value=58.0, status=KRIStatus.RED, score=65.0),
                    KRIScore(kri_id="KRI-003", kri_name="Protocol Deviation Rate", value=5.8, status=KRIStatus.YELLOW, score=55.0),
                    KRIScore(kri_id="KRI-005", kri_name="Enrollment Rate vs Target", value=48.0, status=KRIStatus.RED, score=70.0),
                ],
                "last_assessed": now - timedelta(days=2),
                "trend": Trend.WORSENING,
            },
            {
                "site_id": "SITE-106",
                "site_name": "Cedars-Sinai Medical Center",
                "overall_risk_score": 55.0,
                "risk_level": RiskLevel.HIGH,
                "kri_scores": [
                    KRIScore(kri_id="KRI-001", kri_name="SAE Reporting Timeliness", value=72.0, status=KRIStatus.YELLOW, score=50.0),
                    KRIScore(kri_id="KRI-004", kri_name="Consent Form Compliance", value=88.0, status=KRIStatus.RED, score=60.0),
                    KRIScore(kri_id="KRI-006", kri_name="Data Entry Lag", value=11.0, status=KRIStatus.RED, score=65.0),
                    KRIScore(kri_id="KRI-012", kri_name="Visit Completion Rate", value=68.0, status=KRIStatus.RED, score=60.0),
                ],
                "last_assessed": now - timedelta(days=1),
                "trend": Trend.WORSENING,
            },
            {
                "site_id": "SITE-107",
                "site_name": "Mass General Brigham",
                "overall_risk_score": 82.0,
                "risk_level": RiskLevel.CRITICAL,
                "kri_scores": [
                    KRIScore(kri_id="KRI-001", kri_name="SAE Reporting Timeliness", value=55.0, status=KRIStatus.RED, score=85.0),
                    KRIScore(kri_id="KRI-002", kri_name="Query Resolution Rate", value=45.0, status=KRIStatus.RED, score=80.0),
                    KRIScore(kri_id="KRI-003", kri_name="Protocol Deviation Rate", value=8.5, status=KRIStatus.RED, score=90.0),
                    KRIScore(kri_id="KRI-004", kri_name="Consent Form Compliance", value=82.0, status=KRIStatus.RED, score=80.0),
                    KRIScore(kri_id="KRI-010", kri_name="Randomization Error Rate", value=7.0, status=KRIStatus.RED, score=85.0),
                ],
                "last_assessed": now - timedelta(days=1),
                "trend": Trend.WORSENING,
            },
            {
                "site_id": "SITE-108",
                "site_name": "Stanford Health Care",
                "overall_risk_score": 28.0,
                "risk_level": RiskLevel.MEDIUM,
                "kri_scores": [
                    KRIScore(kri_id="KRI-001", kri_name="SAE Reporting Timeliness", value=90.0, status=KRIStatus.GREEN, score=15.0),
                    KRIScore(kri_id="KRI-002", kri_name="Query Resolution Rate", value=88.0, status=KRIStatus.GREEN, score=12.0),
                    KRIScore(kri_id="KRI-006", kri_name="Data Entry Lag", value=6.0, status=KRIStatus.YELLOW, score=35.0),
                    KRIScore(kri_id="KRI-009", kri_name="Screen Failure Rate", value=45.0, status=KRIStatus.YELLOW, score=40.0),
                ],
                "last_assessed": now - timedelta(days=6),
                "trend": Trend.IMPROVING,
            },
        ]

        for s in sites_data:
            self._site_risk_scores[s["site_id"]] = SiteRiskScore(**s)

        # --- KRI Data Points (sample historical data) ---
        periods = ["2025-10", "2025-11", "2025-12", "2026-01"]
        dp_counter = 0
        for site_id in ["SITE-105", "SITE-107"]:
            for kri_id in ["KRI-001", "KRI-002", "KRI-003"]:
                for i, period in enumerate(periods):
                    dp_counter += 1
                    base_val = 90.0 - (i * 8) if site_id == "SITE-107" else 85.0 - (i * 5)
                    kri = self._kris.get(kri_id)
                    if kri and kri.unit == "%":
                        status = self._evaluate_kri_status(base_val, kri)
                    else:
                        status = KRIStatus.GREEN
                    dp = KRIDataPoint(
                        id=f"KDP-{dp_counter:04d}",
                        kri_id=kri_id,
                        site_id=site_id,
                        value=round(base_val, 1),
                        period=period,
                        status=status,
                        recorded_at=now - timedelta(days=(4 - i) * 30),
                    )
                    self._kri_data_points[dp.id] = dp

        # --- 15 Monitoring Plans ---
        plans_data = [
            {
                "id": "MON-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "visit_type": MonitoringVisitType.SITE_INITIATION,
                "planned_date": now - timedelta(days=180),
                "actual_date": now - timedelta(days=178),
                "monitor_name": "Sarah Mitchell",
                "status": MonitoringPlanStatus.COMPLETED,
                "findings_count": 1,
                "notes": "Site initiation completed. Minor documentation finding.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "MON-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "visit_type": MonitoringVisitType.INTERIM,
                "planned_date": now - timedelta(days=90),
                "actual_date": now - timedelta(days=88),
                "monitor_name": "Sarah Mitchell",
                "status": MonitoringPlanStatus.COMPLETED,
                "findings_count": 0,
                "notes": "No findings. Site performing well.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "MON-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "visit_type": MonitoringVisitType.INTERIM,
                "planned_date": now - timedelta(days=60),
                "actual_date": now - timedelta(days=58),
                "monitor_name": "David Park",
                "status": MonitoringPlanStatus.COMPLETED,
                "findings_count": 3,
                "notes": "Multiple findings related to query resolution and protocol deviations.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "MON-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "visit_type": MonitoringVisitType.FOR_CAUSE,
                "planned_date": now - timedelta(days=30),
                "actual_date": now - timedelta(days=28),
                "monitor_name": "Jennifer Lee",
                "status": MonitoringPlanStatus.COMPLETED,
                "findings_count": 4,
                "notes": "For-cause visit due to high risk score. Critical findings identified.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "MON-005",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "visit_type": MonitoringVisitType.FOR_CAUSE,
                "planned_date": now - timedelta(days=15),
                "actual_date": now - timedelta(days=14),
                "monitor_name": "Jennifer Lee",
                "status": MonitoringPlanStatus.COMPLETED,
                "findings_count": 5,
                "notes": "Critical site visit. Multiple systemic issues identified.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "MON-006",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "visit_type": MonitoringVisitType.REMOTE,
                "planned_date": now - timedelta(days=45),
                "actual_date": now - timedelta(days=44),
                "monitor_name": "Sarah Mitchell",
                "status": MonitoringPlanStatus.COMPLETED,
                "findings_count": 0,
                "notes": "Remote monitoring visit. All metrics within acceptable range.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "MON-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "visit_type": MonitoringVisitType.INTERIM,
                "planned_date": now - timedelta(days=20),
                "actual_date": now - timedelta(days=19),
                "monitor_name": "David Park",
                "status": MonitoringPlanStatus.COMPLETED,
                "findings_count": 2,
                "notes": "Interim visit. Data entry lag and query resolution issues noted.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "MON-008",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "visit_type": MonitoringVisitType.INTERIM,
                "planned_date": now - timedelta(days=10),
                "actual_date": now - timedelta(days=9),
                "monitor_name": "David Park",
                "status": MonitoringPlanStatus.COMPLETED,
                "findings_count": 3,
                "notes": "Consent form and visit completion issues at this site.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "MON-009",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "visit_type": MonitoringVisitType.REMOTE,
                "planned_date": now + timedelta(days=15),
                "actual_date": None,
                "monitor_name": "Sarah Mitchell",
                "status": MonitoringPlanStatus.PLANNED,
                "findings_count": 0,
                "notes": None,
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "MON-010",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "visit_type": MonitoringVisitType.INTERIM,
                "planned_date": now + timedelta(days=7),
                "actual_date": None,
                "monitor_name": "Jennifer Lee",
                "status": MonitoringPlanStatus.PLANNED,
                "findings_count": 0,
                "notes": None,
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "MON-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "visit_type": MonitoringVisitType.FOR_CAUSE,
                "planned_date": now + timedelta(days=3),
                "actual_date": None,
                "monitor_name": "Jennifer Lee",
                "status": MonitoringPlanStatus.PLANNED,
                "findings_count": 0,
                "notes": None,
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "MON-012",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-108",
                "visit_type": MonitoringVisitType.REMOTE,
                "planned_date": now + timedelta(days=30),
                "actual_date": None,
                "monitor_name": "Sarah Mitchell",
                "status": MonitoringPlanStatus.PLANNED,
                "findings_count": 0,
                "notes": None,
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "MON-013",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "visit_type": MonitoringVisitType.INTERIM,
                "planned_date": now + timedelta(days=21),
                "actual_date": None,
                "monitor_name": "David Park",
                "status": MonitoringPlanStatus.PLANNED,
                "findings_count": 0,
                "notes": None,
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "MON-014",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "visit_type": MonitoringVisitType.INTERIM,
                "planned_date": now + timedelta(days=14),
                "actual_date": None,
                "monitor_name": "David Park",
                "status": MonitoringPlanStatus.PLANNED,
                "findings_count": 0,
                "notes": None,
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "MON-015",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-104",
                "visit_type": MonitoringVisitType.REMOTE,
                "planned_date": now - timedelta(days=5),
                "actual_date": None,
                "monitor_name": "David Park",
                "status": MonitoringPlanStatus.CANCELLED,
                "findings_count": 0,
                "notes": "Cancelled due to site unavailability; rescheduled.",
                "created_at": now - timedelta(days=15),
            },
        ]

        for p in plans_data:
            self._monitoring_plans[p["id"]] = MonitoringPlan(**p)

        # --- 10 Findings ---
        findings_data = [
            {
                "id": "FND-001",
                "plan_id": "MON-001",
                "site_id": "SITE-101",
                "category": FindingCategory.MINOR,
                "description": "Investigator site file missing updated protocol signature page",
                "response_due_date": now - timedelta(days=150),
                "resolved_date": now - timedelta(days=155),
                "capa_id": None,
                "status": FindingStatus.VERIFIED,
                "created_at": now - timedelta(days=178),
            },
            {
                "id": "FND-002",
                "plan_id": "MON-003",
                "site_id": "SITE-103",
                "category": FindingCategory.MAJOR,
                "description": "Query resolution exceeds 10 business days for 15% of queries",
                "response_due_date": now - timedelta(days=30),
                "resolved_date": now - timedelta(days=25),
                "capa_id": "CAPA-201",
                "status": FindingStatus.RESOLVED,
                "created_at": now - timedelta(days=58),
            },
            {
                "id": "FND-003",
                "plan_id": "MON-003",
                "site_id": "SITE-103",
                "category": FindingCategory.MAJOR,
                "description": "3 major protocol deviations in past 60 days without adequate documentation",
                "response_due_date": now - timedelta(days=28),
                "resolved_date": None,
                "capa_id": "CAPA-202",
                "status": FindingStatus.RESPONSE_REQUIRED,
                "created_at": now - timedelta(days=58),
            },
            {
                "id": "FND-004",
                "plan_id": "MON-003",
                "site_id": "SITE-103",
                "category": FindingCategory.OBSERVATION,
                "description": "Staff training records not centrally organized",
                "response_due_date": now + timedelta(days=30),
                "resolved_date": None,
                "capa_id": None,
                "status": FindingStatus.OPEN,
                "created_at": now - timedelta(days=58),
            },
            {
                "id": "FND-005",
                "plan_id": "MON-004",
                "site_id": "SITE-105",
                "category": FindingCategory.CRITICAL,
                "description": "SAE not reported to sponsor within 24 hours for 3 events",
                "response_due_date": now - timedelta(days=14),
                "resolved_date": None,
                "capa_id": "CAPA-301",
                "status": FindingStatus.RESPONSE_REQUIRED,
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "FND-006",
                "plan_id": "MON-004",
                "site_id": "SITE-105",
                "category": FindingCategory.MAJOR,
                "description": "Enrollment below 50% of target with no documented remediation plan",
                "response_due_date": now - timedelta(days=7),
                "resolved_date": None,
                "capa_id": None,
                "status": FindingStatus.OPEN,
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "FND-007",
                "plan_id": "MON-005",
                "site_id": "SITE-107",
                "category": FindingCategory.CRITICAL,
                "description": "Systematic consent form errors: 5 subjects with incorrect consent version",
                "response_due_date": now - timedelta(days=1),
                "resolved_date": None,
                "capa_id": "CAPA-401",
                "status": FindingStatus.OPEN,
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "FND-008",
                "plan_id": "MON-005",
                "site_id": "SITE-107",
                "category": FindingCategory.CRITICAL,
                "description": "Randomization errors: 3 patients assigned to wrong treatment arm",
                "response_due_date": now + timedelta(days=7),
                "resolved_date": None,
                "capa_id": "CAPA-402",
                "status": FindingStatus.OPEN,
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "FND-009",
                "plan_id": "MON-007",
                "site_id": "SITE-104",
                "category": FindingCategory.MAJOR,
                "description": "Data entry lag exceeds 7 days for 40% of recent visits",
                "response_due_date": now + timedelta(days=14),
                "resolved_date": None,
                "capa_id": None,
                "status": FindingStatus.OPEN,
                "created_at": now - timedelta(days=19),
            },
            {
                "id": "FND-010",
                "plan_id": "MON-008",
                "site_id": "SITE-106",
                "category": FindingCategory.MAJOR,
                "description": "Visit completion rate below 70% - 8 missed visit windows in past quarter",
                "response_due_date": now + timedelta(days=21),
                "resolved_date": None,
                "capa_id": "CAPA-501",
                "status": FindingStatus.OPEN,
                "created_at": now - timedelta(days=9),
            },
        ]

        for f in findings_data:
            self._findings[f["id"]] = MonitoringFinding(**f)

        # --- 6 Central Monitoring Alerts ---
        alerts_data = [
            {
                "id": "CMA-001",
                "site_id": "SITE-105",
                "kri_id": "KRI-001",
                "triggered_date": now - timedelta(days=35),
                "value": 65.0,
                "threshold_breached": "red",
                "action_taken": MonitoringAction.FOR_CAUSE,
                "resolved": True,
                "resolved_date": now - timedelta(days=28),
                "notes": "For-cause visit triggered and completed. Remediation plan in place.",
            },
            {
                "id": "CMA-002",
                "site_id": "SITE-105",
                "kri_id": "KRI-002",
                "triggered_date": now - timedelta(days=20),
                "value": 55.0,
                "threshold_breached": "red",
                "action_taken": MonitoringAction.TARGETED,
                "resolved": False,
                "resolved_date": None,
                "notes": "Targeted monitoring initiated. Follow-up visit scheduled.",
            },
            {
                "id": "CMA-003",
                "site_id": "SITE-107",
                "kri_id": "KRI-001",
                "triggered_date": now - timedelta(days=18),
                "value": 52.0,
                "threshold_breached": "red",
                "action_taken": MonitoringAction.FOR_CAUSE,
                "resolved": False,
                "resolved_date": None,
                "notes": "Critical alert. For-cause visit completed, CAPA in progress.",
            },
            {
                "id": "CMA-004",
                "site_id": "SITE-107",
                "kri_id": "KRI-003",
                "triggered_date": now - timedelta(days=15),
                "value": 8.5,
                "threshold_breached": "red",
                "action_taken": MonitoringAction.FOR_CAUSE,
                "resolved": False,
                "resolved_date": None,
                "notes": "Protocol deviation rate critical. Site under enhanced monitoring.",
            },
            {
                "id": "CMA-005",
                "site_id": "SITE-106",
                "kri_id": "KRI-006",
                "triggered_date": now - timedelta(days=12),
                "value": 11.0,
                "threshold_breached": "red",
                "action_taken": MonitoringAction.TARGETED,
                "resolved": False,
                "resolved_date": None,
                "notes": "Data entry lag exceeds red threshold. Site contacted.",
            },
            {
                "id": "CMA-006",
                "site_id": "SITE-103",
                "kri_id": "KRI-005",
                "triggered_date": now - timedelta(days=8),
                "value": 72.0,
                "threshold_breached": "yellow",
                "action_taken": None,
                "resolved": False,
                "resolved_date": None,
                "notes": None,
            },
        ]

        for a in alerts_data:
            self._alerts[a["id"]] = CentralMonitoringAlert(**a)

    # ------------------------------------------------------------------
    # KRI Management
    # ------------------------------------------------------------------

    def list_kris(
        self,
        *,
        category: KRICategory | None = None,
        active: bool | None = None,
    ) -> list[KeyRiskIndicator]:
        """List KRIs with optional filters."""
        with self._lock:
            result = list(self._kris.values())

        if category is not None:
            result = [k for k in result if k.category == category]
        if active is not None:
            result = [k for k in result if k.active == active]

        return sorted(result, key=lambda k: k.id)

    def get_kri(self, kri_id: str) -> KeyRiskIndicator | None:
        """Get a single KRI by ID."""
        with self._lock:
            return self._kris.get(kri_id)

    def create_kri(self, payload: KRICreate) -> KeyRiskIndicator:
        """Create a new KRI."""
        kri_id = f"KRI-{uuid4().hex[:8].upper()}"
        kri = KeyRiskIndicator(
            id=kri_id,
            **payload.model_dump(),
        )
        with self._lock:
            self._kris[kri_id] = kri
        logger.info("Created KRI %s: %s", kri_id, payload.name)
        return kri

    def update_kri(self, kri_id: str, payload: KRIUpdate) -> KeyRiskIndicator | None:
        """Update an existing KRI."""
        with self._lock:
            existing = self._kris.get(kri_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = KeyRiskIndicator(**data)
            self._kris[kri_id] = updated
        return updated

    def delete_kri(self, kri_id: str) -> bool:
        """Delete a KRI. Returns True if deleted, False if not found."""
        with self._lock:
            if kri_id in self._kris:
                del self._kris[kri_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Site Risk Scoring
    # ------------------------------------------------------------------

    def list_site_risk_scores(
        self,
        *,
        risk_level: RiskLevel | None = None,
    ) -> list[SiteRiskScore]:
        """List all site risk scores with optional risk level filter."""
        with self._lock:
            result = list(self._site_risk_scores.values())

        if risk_level is not None:
            result = [s for s in result if s.risk_level == risk_level]

        return sorted(result, key=lambda s: s.overall_risk_score, reverse=True)

    def get_site_risk_profile(self, site_id: str) -> SiteRiskScore | None:
        """Get detailed risk profile for a specific site."""
        with self._lock:
            return self._site_risk_scores.get(site_id)

    def recalculate_site_risk(self, site_id: str) -> SiteRiskScore | None:
        """Recalculate risk score for a site based on latest KRI data.

        Uses weighted KRI aggregation with auto-escalation:
        - Weighted average of KRI scores -> overall_risk_score (0-100)
        - If 3+ KRIs red -> site goes to critical
        - Trend analysis: compare current vs prior 3 periods
        """
        with self._lock:
            existing = self._site_risk_scores.get(site_id)
            if existing is None:
                return None

            # Get latest KRI data points for this site
            site_dps = [
                dp for dp in self._kri_data_points.values()
                if dp.site_id == site_id
            ]

        if not site_dps:
            return existing

        # Group by KRI, get latest period per KRI
        latest_by_kri: dict[str, KRIDataPoint] = {}
        for dp in sorted(site_dps, key=lambda x: x.period):
            latest_by_kri[dp.kri_id] = dp

        # Calculate weighted risk score
        total_weight = 0.0
        weighted_sum = 0.0
        red_count = 0
        kri_scores: list[KRIScore] = []

        for kri_id, dp in latest_by_kri.items():
            kri = self._kris.get(kri_id)
            if kri is None or not kri.active:
                continue

            status = self._evaluate_kri_status(dp.value, kri)
            score = self._value_to_score(dp.value, kri)

            kri_scores.append(KRIScore(
                kri_id=kri_id,
                kri_name=kri.name,
                value=dp.value,
                status=status,
                score=score,
            ))

            total_weight += kri.weight
            weighted_sum += score * kri.weight

            if status == KRIStatus.RED:
                red_count += 1

        if total_weight > 0:
            overall_score = round(weighted_sum / total_weight, 1)
        else:
            overall_score = existing.overall_risk_score

        # Determine risk level with auto-escalation
        risk_level = self._score_to_risk_level(overall_score)
        if red_count >= AUTO_ESCALATION_RED_COUNT:
            risk_level = RiskLevel.CRITICAL

        # Trend analysis
        trend = self._calculate_trend(site_id)

        now = datetime.now(timezone.utc)
        updated = SiteRiskScore(
            site_id=site_id,
            site_name=existing.site_name,
            overall_risk_score=overall_score,
            risk_level=risk_level,
            kri_scores=kri_scores,
            last_assessed=now,
            trend=trend,
        )

        with self._lock:
            self._site_risk_scores[site_id] = updated
        return updated

    def _evaluate_kri_status(self, value: float, kri: KeyRiskIndicator) -> KRIStatus:
        """Evaluate traffic-light status for a KRI value.

        Handles both "higher is better" (like %) and "lower is better" (like days).
        """
        if kri.threshold_yellow > kri.threshold_red:
            # Higher is better (e.g., %)
            if value >= kri.threshold_yellow:
                return KRIStatus.GREEN
            elif value >= kri.threshold_red:
                return KRIStatus.YELLOW
            else:
                return KRIStatus.RED
        else:
            # Lower is better (e.g., days, deviation rate)
            if value <= kri.threshold_yellow:
                return KRIStatus.GREEN
            elif value <= kri.threshold_red:
                return KRIStatus.YELLOW
            else:
                return KRIStatus.RED

    def _value_to_score(self, value: float, kri: KeyRiskIndicator) -> float:
        """Convert a KRI value to a normalized score (0-100, higher = worse risk)."""
        if kri.threshold_yellow > kri.threshold_red:
            # Higher is better (e.g., %)
            if value >= kri.threshold_yellow:
                return max(0.0, 100.0 - value)
            elif value >= kri.threshold_red:
                return 50.0 + (kri.threshold_yellow - value) / max(1.0, kri.threshold_yellow - kri.threshold_red) * 30.0
            else:
                return 80.0 + (kri.threshold_red - value) / max(1.0, kri.threshold_red) * 20.0
        else:
            # Lower is better (e.g., days, rate)
            if value <= kri.threshold_yellow:
                return min(100.0, value / max(0.01, kri.threshold_yellow) * 25.0)
            elif value <= kri.threshold_red:
                return 50.0 + (value - kri.threshold_yellow) / max(1.0, kri.threshold_red - kri.threshold_yellow) * 30.0
            else:
                return min(100.0, 80.0 + (value - kri.threshold_red) / max(1.0, kri.threshold_red) * 20.0)

    @staticmethod
    def _score_to_risk_level(score: float) -> RiskLevel:
        """Classify a numeric risk score into a risk level."""
        if score < RISK_THRESHOLD_LOW:
            return RiskLevel.LOW
        elif score < RISK_THRESHOLD_MEDIUM:
            return RiskLevel.MEDIUM
        elif score < RISK_THRESHOLD_HIGH:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

    def _calculate_trend(self, site_id: str) -> Trend:
        """Calculate trend by comparing current vs prior 3 periods of KRI data."""
        with self._lock:
            site_dps = [
                dp for dp in self._kri_data_points.values()
                if dp.site_id == site_id
            ]

        if len(site_dps) < 4:
            return Trend.STABLE

        # Sort by period descending
        sorted_dps = sorted(site_dps, key=lambda x: x.period, reverse=True)

        # Get unique periods
        periods = list(dict.fromkeys(dp.period for dp in sorted_dps))
        if len(periods) < 2:
            return Trend.STABLE

        # Average status score for latest vs earlier periods
        latest_period = periods[0]
        prior_periods = periods[1:4]

        latest_scores = [
            dp.value for dp in sorted_dps if dp.period == latest_period
        ]
        prior_scores = [
            dp.value for dp in sorted_dps if dp.period in prior_periods
        ]

        if not latest_scores or not prior_scores:
            return Trend.STABLE

        avg_latest = sum(latest_scores) / len(latest_scores)
        avg_prior = sum(prior_scores) / len(prior_scores)

        diff = avg_latest - avg_prior
        if abs(diff) < 3.0:
            return Trend.STABLE
        elif diff > 0:
            return Trend.IMPROVING  # Higher values generally better for %
        else:
            return Trend.WORSENING

    # ------------------------------------------------------------------
    # KRI Data Points
    # ------------------------------------------------------------------

    def submit_kri_data(self, payload: KRIDataPointCreate) -> KRIDataPoint:
        """Submit a KRI data point for a site."""
        now = datetime.now(timezone.utc)
        dp_id = f"KDP-{uuid4().hex[:8].upper()}"

        kri = self._kris.get(payload.kri_id)
        if kri is None:
            raise ValueError(f"KRI '{payload.kri_id}' not found")

        status = self._evaluate_kri_status(payload.value, kri)

        dp = KRIDataPoint(
            id=dp_id,
            kri_id=payload.kri_id,
            site_id=payload.site_id,
            value=payload.value,
            period=payload.period,
            status=status,
            recorded_at=now,
        )

        with self._lock:
            self._kri_data_points[dp_id] = dp

        # Check if alert should be triggered
        if status == KRIStatus.RED:
            self._trigger_alert(payload.site_id, payload.kri_id, payload.value, "red")
        elif status == KRIStatus.YELLOW:
            self._trigger_alert(payload.site_id, payload.kri_id, payload.value, "yellow")

        logger.info(
            "Submitted KRI data point %s: KRI=%s site=%s value=%.1f status=%s",
            dp_id, payload.kri_id, payload.site_id, payload.value, status.value,
        )
        return dp

    def get_kri_trends(self, site_id: str, kri_id: str | None = None) -> list[KRIDataPoint]:
        """Get KRI data points for a site over time."""
        with self._lock:
            result = [
                dp for dp in self._kri_data_points.values()
                if dp.site_id == site_id
            ]

        if kri_id is not None:
            result = [dp for dp in result if dp.kri_id == kri_id]

        return sorted(result, key=lambda dp: (dp.kri_id, dp.period))

    def _trigger_alert(
        self,
        site_id: str,
        kri_id: str,
        value: float,
        threshold_breached: str,
    ) -> None:
        """Create a central monitoring alert if one doesn't already exist."""
        now = datetime.now(timezone.utc)
        with self._lock:
            # Check for existing unresolved alert for same site/KRI
            for alert in self._alerts.values():
                if (
                    alert.site_id == site_id
                    and alert.kri_id == kri_id
                    and not alert.resolved
                ):
                    return  # Already alerted

            alert_id = f"CMA-{uuid4().hex[:8].upper()}"
            alert = CentralMonitoringAlert(
                id=alert_id,
                site_id=site_id,
                kri_id=kri_id,
                triggered_date=now,
                value=value,
                threshold_breached=threshold_breached,
                action_taken=None,
                resolved=False,
                resolved_date=None,
                notes=None,
            )
            self._alerts[alert_id] = alert
        logger.info(
            "Central monitoring alert %s triggered: site=%s KRI=%s value=%.1f breach=%s",
            alert_id, site_id, kri_id, value, threshold_breached,
        )

    # ------------------------------------------------------------------
    # Central Monitoring Alerts
    # ------------------------------------------------------------------

    def list_alerts(
        self,
        *,
        site_id: str | None = None,
        resolved: bool | None = None,
    ) -> list[CentralMonitoringAlert]:
        """List central monitoring alerts with optional filters."""
        with self._lock:
            result = list(self._alerts.values())

        if site_id is not None:
            result = [a for a in result if a.site_id == site_id]
        if resolved is not None:
            result = [a for a in result if a.resolved == resolved]

        return sorted(result, key=lambda a: a.triggered_date, reverse=True)

    def get_alert(self, alert_id: str) -> CentralMonitoringAlert | None:
        """Get a single alert by ID."""
        with self._lock:
            return self._alerts.get(alert_id)

    def resolve_alert(self, alert_id: str, payload: AlertResolve) -> CentralMonitoringAlert | None:
        """Resolve a central monitoring alert."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._alerts.get(alert_id)
            if existing is None:
                return None

            if existing.resolved:
                raise ValueError(f"Alert '{alert_id}' is already resolved")

            data = existing.model_dump()
            data["resolved"] = True
            data["resolved_date"] = now
            data["action_taken"] = payload.action_taken
            data["notes"] = payload.notes
            updated = CentralMonitoringAlert(**data)
            self._alerts[alert_id] = updated
        logger.info("Resolved alert %s with action %s", alert_id, payload.action_taken.value)
        return updated

    # ------------------------------------------------------------------
    # Monitoring Plans
    # ------------------------------------------------------------------

    def list_monitoring_plans(
        self,
        *,
        site_id: str | None = None,
        trial_id: str | None = None,
        status: MonitoringPlanStatus | None = None,
        visit_type: MonitoringVisitType | None = None,
    ) -> list[MonitoringPlan]:
        """List monitoring plans with optional filters."""
        with self._lock:
            result = list(self._monitoring_plans.values())

        if site_id is not None:
            result = [p for p in result if p.site_id == site_id]
        if trial_id is not None:
            result = [p for p in result if p.trial_id == trial_id]
        if status is not None:
            result = [p for p in result if p.status == status]
        if visit_type is not None:
            result = [p for p in result if p.visit_type == visit_type]

        return sorted(result, key=lambda p: p.planned_date, reverse=True)

    def get_monitoring_plan(self, plan_id: str) -> MonitoringPlan | None:
        """Get a single monitoring plan by ID."""
        with self._lock:
            return self._monitoring_plans.get(plan_id)

    def create_monitoring_plan(self, payload: MonitoringPlanCreate) -> MonitoringPlan:
        """Create a new monitoring plan/visit."""
        now = datetime.now(timezone.utc)
        plan_id = f"MON-{uuid4().hex[:8].upper()}"
        plan = MonitoringPlan(
            id=plan_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            visit_type=payload.visit_type,
            planned_date=payload.planned_date,
            actual_date=None,
            monitor_name=payload.monitor_name,
            status=MonitoringPlanStatus.PLANNED,
            findings_count=0,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._monitoring_plans[plan_id] = plan
        logger.info("Created monitoring plan %s for site %s", plan_id, payload.site_id)
        return plan

    def update_monitoring_plan(self, plan_id: str, payload: MonitoringPlanUpdate) -> MonitoringPlan | None:
        """Update a monitoring plan."""
        with self._lock:
            existing = self._monitoring_plans.get(plan_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MonitoringPlan(**data)
            self._monitoring_plans[plan_id] = updated
        return updated

    def complete_monitoring_visit(
        self,
        plan_id: str,
        payload: MonitoringVisitComplete,
    ) -> MonitoringPlan | None:
        """Complete a monitoring visit, optionally creating findings."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._monitoring_plans.get(plan_id)
            if existing is None:
                return None

            if existing.status == MonitoringPlanStatus.COMPLETED:
                raise ValueError(f"Plan '{plan_id}' is already completed")

            data = existing.model_dump()
            data["status"] = MonitoringPlanStatus.COMPLETED
            data["actual_date"] = payload.actual_date
            data["notes"] = payload.notes

            # Create findings if provided
            findings_created = 0
            if payload.findings:
                for fc in payload.findings:
                    finding_id = f"FND-{uuid4().hex[:8].upper()}"
                    finding = MonitoringFinding(
                        id=finding_id,
                        plan_id=plan_id,
                        site_id=existing.site_id,
                        category=fc.category,
                        description=fc.description,
                        response_due_date=fc.response_due_date,
                        resolved_date=None,
                        capa_id=fc.capa_id,
                        status=FindingStatus.OPEN,
                        created_at=now,
                    )
                    self._findings[finding_id] = finding
                    findings_created += 1

            data["findings_count"] = findings_created
            updated = MonitoringPlan(**data)
            self._monitoring_plans[plan_id] = updated

        logger.info(
            "Completed monitoring visit %s with %d findings",
            plan_id, findings_created,
        )
        return updated

    def delete_monitoring_plan(self, plan_id: str) -> bool:
        """Delete a monitoring plan. Returns True if deleted."""
        with self._lock:
            if plan_id in self._monitoring_plans:
                del self._monitoring_plans[plan_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Findings
    # ------------------------------------------------------------------

    def list_findings(
        self,
        *,
        site_id: str | None = None,
        plan_id: str | None = None,
        category: FindingCategory | None = None,
        status: FindingStatus | None = None,
    ) -> list[MonitoringFinding]:
        """List monitoring findings with optional filters."""
        with self._lock:
            result = list(self._findings.values())

        if site_id is not None:
            result = [f for f in result if f.site_id == site_id]
        if plan_id is not None:
            result = [f for f in result if f.plan_id == plan_id]
        if category is not None:
            result = [f for f in result if f.category == category]
        if status is not None:
            result = [f for f in result if f.status == status]

        return sorted(result, key=lambda f: f.created_at, reverse=True)

    def get_finding(self, finding_id: str) -> MonitoringFinding | None:
        """Get a single finding by ID."""
        with self._lock:
            return self._findings.get(finding_id)

    def update_finding(self, finding_id: str, payload: FindingUpdate) -> MonitoringFinding | None:
        """Update a monitoring finding."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._findings.get(finding_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set resolved_date when status goes to resolved
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = FindingStatus(new_status)
                if new_status == FindingStatus.RESOLVED and existing.status != FindingStatus.RESOLVED:
                    updates["resolved_date"] = now

            data.update(updates)
            updated = MonitoringFinding(**data)
            self._findings[finding_id] = updated
        return updated

    def get_overdue_findings(self) -> list[MonitoringFinding]:
        """Get findings that are past their response due date and not resolved."""
        now = datetime.now(timezone.utc)
        with self._lock:
            result = [
                f for f in self._findings.values()
                if f.status in (FindingStatus.OPEN, FindingStatus.RESPONSE_REQUIRED)
                and f.response_due_date < now
            ]
        return sorted(result, key=lambda f: f.response_due_date)

    # ------------------------------------------------------------------
    # Monitoring Schedule
    # ------------------------------------------------------------------

    def get_monitoring_schedule(self) -> list[MonitoringScheduleRecommendation]:
        """Generate recommended monitoring schedule based on site risk levels.

        - Critical: weekly for-cause visits
        - High: monthly on-site visits
        - Medium: quarterly remote + on-site mix
        - Low: quarterly remote visits
        """
        now = datetime.now(timezone.utc)
        recommendations: list[MonitoringScheduleRecommendation] = []

        with self._lock:
            sites = list(self._site_risk_scores.values())

        for site in sites:
            if site.risk_level == RiskLevel.CRITICAL:
                freq = "weekly"
                visit_type = MonitoringVisitType.FOR_CAUSE
                next_date = now + timedelta(days=7)
                rationale = f"Critical risk (score: {site.overall_risk_score:.0f}). Weekly for-cause monitoring required."
            elif site.risk_level == RiskLevel.HIGH:
                freq = "monthly"
                visit_type = MonitoringVisitType.INTERIM
                next_date = now + timedelta(days=30)
                rationale = f"High risk (score: {site.overall_risk_score:.0f}). Monthly on-site monitoring recommended."
            elif site.risk_level == RiskLevel.MEDIUM:
                freq = "quarterly"
                visit_type = MonitoringVisitType.REMOTE
                next_date = now + timedelta(days=90)
                rationale = f"Medium risk (score: {site.overall_risk_score:.0f}). Quarterly remote monitoring with periodic on-site."
            else:
                freq = "quarterly"
                visit_type = MonitoringVisitType.REMOTE
                next_date = now + timedelta(days=90)
                rationale = f"Low risk (score: {site.overall_risk_score:.0f}). Quarterly remote monitoring sufficient."

            recommendations.append(MonitoringScheduleRecommendation(
                site_id=site.site_id,
                site_name=site.site_name,
                risk_level=site.risk_level,
                recommended_frequency=freq,
                recommended_visit_type=visit_type,
                next_recommended_date=next_date,
                rationale=rationale,
            ))

        return sorted(recommendations, key=lambda r: {
            RiskLevel.CRITICAL: 0,
            RiskLevel.HIGH: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.LOW: 3,
        }.get(r.risk_level, 4))

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> RBMMetrics:
        """Compute aggregated RBM operational metrics."""
        now = datetime.now(timezone.utc)

        with self._lock:
            sites = list(self._site_risk_scores.values())
            kris = list(self._kris.values())
            alerts = list(self._alerts.values())
            plans = list(self._monitoring_plans.values())
            findings = list(self._findings.values())
            data_points = list(self._kri_data_points.values())

        # Sites by risk level
        sites_by_risk: dict[str, int] = {}
        total_score = 0.0
        for site in sites:
            key = site.risk_level.value
            sites_by_risk[key] = sites_by_risk.get(key, 0) + 1
            total_score += site.overall_risk_score

        avg_risk = round(total_score / max(1, len(sites)), 1)

        # Alerts
        active_alerts = sum(1 for a in alerts if not a.resolved)

        # Monitoring visits
        completed_visits = sum(
            1 for p in plans if p.status == MonitoringPlanStatus.COMPLETED
        )

        # Findings
        open_findings = sum(
            1 for f in findings
            if f.status in (FindingStatus.OPEN, FindingStatus.RESPONSE_REQUIRED)
        )
        overdue_findings = sum(
            1 for f in findings
            if f.status in (FindingStatus.OPEN, FindingStatus.RESPONSE_REQUIRED)
            and f.response_due_date < now
        )

        return RBMMetrics(
            total_sites=len(sites),
            sites_by_risk_level=sites_by_risk,
            total_kris=len(kris),
            active_alerts=active_alerts,
            avg_risk_score=avg_risk,
            monitoring_visits_completed=completed_visits,
            open_findings=open_findings,
            overdue_findings=overdue_findings,
            total_findings=len(findings),
            total_monitoring_plans=len(plans),
            kri_data_points=len(data_points),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: RBMService | None = None
_instance_lock = threading.Lock()


def get_rbm_service() -> RBMService:
    """Return the singleton RBMService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = RBMService()
    return _instance


def reset_rbm_service() -> RBMService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = RBMService()
    return _instance
