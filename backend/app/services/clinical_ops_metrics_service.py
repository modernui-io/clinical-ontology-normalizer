"""Clinical Operations Metrics Dashboard Service.

Manages operational KPIs, performance trends, trial scorecards, portfolio
summary, benchmarking, operational alerts, executive reports, and dashboard
metrics across the clinical trial portfolio.

Usage:
    from app.services.clinical_ops_metrics_service import (
        get_clinical_ops_metrics_service,
    )

    svc = get_clinical_ops_metrics_service()
    dashboard = svc.get_dashboard_metrics()
    summary = svc.get_portfolio_summary()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.clinical_ops_metrics import (
    AlertAcknowledge,
    AlertResolve,
    AlertSeverity,
    Benchmark,
    BenchmarkCreate,
    BenchmarkSource,
    BenchmarkUpdate,
    DashboardMetrics,
    ExecutiveReport,
    ExecutiveReportGenerate,
    KPIStatus,
    MetricCategory,
    OperationalAlert,
    OperationalAlertCreate,
    OperationalKPI,
    OperationalKPICreate,
    OperationalKPIUpdate,
    PerformanceTrend,
    PerformanceTrendCreate,
    PortfolioSummary,
    ReportPeriod,
    TrendDirection,
    TrialScorecard,
    TrialScorecardCreate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"
ODLISIO_TRIAL = "00000000-de00-0004-0000-000000000004"
KEVZARA_TRIAL = "00000000-de00-0005-0000-000000000005"

# Variance thresholds for KPI status
VARIANCE_ON_TARGET = -5.0   # <= -5% from target is still on target
VARIANCE_AT_RISK = -15.0    # <= -15% from target is at risk
# Below -15% is off target


class ClinicalOpsMetricsService:
    """In-memory Clinical Operations Metrics engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._kpis: dict[str, OperationalKPI] = {}
        self._trends: dict[str, PerformanceTrend] = {}
        self._scorecards: dict[str, TrialScorecard] = {}
        self._benchmarks: dict[str, Benchmark] = {}
        self._alerts: dict[str, OperationalAlert] = {}
        self._reports: dict[str, ExecutiveReport] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic clinical operations metrics data."""
        now = datetime.now(timezone.utc)

        # --- 12 Operational KPIs ---
        kpis_data = [
            {
                "id": "KPI-001",
                "trial_id": EYLEA_TRIAL,
                "category": MetricCategory.ENROLLMENT,
                "metric_name": "Screen-to-Randomization Rate",
                "current_value": 72.5,
                "target_value": 80.0,
                "unit": "%",
                "trend_direction": TrendDirection.IMPROVING,
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "calculated_date": now,
                "variance_pct": -9.4,
                "status": KPIStatus.AT_RISK,
            },
            {
                "id": "KPI-002",
                "trial_id": EYLEA_TRIAL,
                "category": MetricCategory.ENROLLMENT,
                "metric_name": "Monthly Enrollment Rate",
                "current_value": 8.2,
                "target_value": 10.0,
                "unit": "patients/site/month",
                "trend_direction": TrendDirection.STABLE,
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "calculated_date": now,
                "variance_pct": -18.0,
                "status": KPIStatus.OFF_TARGET,
            },
            {
                "id": "KPI-003",
                "trial_id": DUPIXENT_TRIAL,
                "category": MetricCategory.QUALITY,
                "metric_name": "Data Query Rate",
                "current_value": 2.1,
                "target_value": 3.0,
                "unit": "queries/100 fields",
                "trend_direction": TrendDirection.IMPROVING,
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "calculated_date": now,
                "variance_pct": 30.0,
                "status": KPIStatus.ON_TARGET,
            },
            {
                "id": "KPI-004",
                "trial_id": DUPIXENT_TRIAL,
                "category": MetricCategory.TIMELINE,
                "metric_name": "Database Lock Readiness",
                "current_value": 85.0,
                "target_value": 95.0,
                "unit": "%",
                "trend_direction": TrendDirection.DECLINING,
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "calculated_date": now,
                "variance_pct": -10.5,
                "status": KPIStatus.AT_RISK,
            },
            {
                "id": "KPI-005",
                "trial_id": LIBTAYO_TRIAL,
                "category": MetricCategory.BUDGET,
                "metric_name": "Budget Utilization",
                "current_value": 92.0,
                "target_value": 100.0,
                "unit": "%",
                "trend_direction": TrendDirection.STABLE,
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "calculated_date": now,
                "variance_pct": -8.0,
                "status": KPIStatus.AT_RISK,
            },
            {
                "id": "KPI-006",
                "trial_id": LIBTAYO_TRIAL,
                "category": MetricCategory.SAFETY,
                "metric_name": "SAE Reporting Compliance",
                "current_value": 98.5,
                "target_value": 100.0,
                "unit": "%",
                "trend_direction": TrendDirection.STABLE,
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "calculated_date": now,
                "variance_pct": -1.5,
                "status": KPIStatus.ON_TARGET,
            },
            {
                "id": "KPI-007",
                "trial_id": EYLEA_TRIAL,
                "category": MetricCategory.COMPLIANCE,
                "metric_name": "Protocol Deviation Rate",
                "current_value": 4.2,
                "target_value": 3.0,
                "unit": "per 100 patient-months",
                "trend_direction": TrendDirection.DECLINING,
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "calculated_date": now,
                "variance_pct": -40.0,
                "status": KPIStatus.OFF_TARGET,
            },
            {
                "id": "KPI-008",
                "trial_id": DUPIXENT_TRIAL,
                "category": MetricCategory.SITE_PERFORMANCE,
                "metric_name": "Site Activation Rate",
                "current_value": 88.0,
                "target_value": 90.0,
                "unit": "%",
                "trend_direction": TrendDirection.IMPROVING,
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "calculated_date": now,
                "variance_pct": -2.2,
                "status": KPIStatus.ON_TARGET,
            },
            {
                "id": "KPI-009",
                "trial_id": LIBTAYO_TRIAL,
                "category": MetricCategory.DATA_MANAGEMENT,
                "metric_name": "CRF Completion Rate",
                "current_value": 91.0,
                "target_value": 95.0,
                "unit": "%",
                "trend_direction": TrendDirection.STABLE,
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "calculated_date": now,
                "variance_pct": -4.2,
                "status": KPIStatus.ON_TARGET,
            },
            {
                "id": "KPI-010",
                "trial_id": ODLISIO_TRIAL,
                "category": MetricCategory.ENROLLMENT,
                "metric_name": "Retention Rate",
                "current_value": 78.0,
                "target_value": 85.0,
                "unit": "%",
                "trend_direction": TrendDirection.DECLINING,
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "calculated_date": now,
                "variance_pct": -8.2,
                "status": KPIStatus.AT_RISK,
            },
            {
                "id": "KPI-011",
                "trial_id": KEVZARA_TRIAL,
                "category": MetricCategory.QUALITY,
                "metric_name": "Source Data Verification Rate",
                "current_value": 55.0,
                "target_value": 80.0,
                "unit": "%",
                "trend_direction": TrendDirection.CRITICAL,
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "calculated_date": now,
                "variance_pct": -31.3,
                "status": KPIStatus.OFF_TARGET,
            },
            {
                "id": "KPI-012",
                "trial_id": KEVZARA_TRIAL,
                "category": MetricCategory.TIMELINE,
                "metric_name": "Milestone Adherence",
                "current_value": 60.0,
                "target_value": 90.0,
                "unit": "%",
                "trend_direction": TrendDirection.CRITICAL,
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "calculated_date": now,
                "variance_pct": -33.3,
                "status": KPIStatus.OFF_TARGET,
            },
        ]

        for k in kpis_data:
            self._kpis[k["id"]] = OperationalKPI(**k)

        # --- 24 Performance Trends (4 periods x 6 KPIs) ---
        months = [
            (now - timedelta(days=120), now - timedelta(days=90)),
            (now - timedelta(days=90), now - timedelta(days=60)),
            (now - timedelta(days=60), now - timedelta(days=30)),
            (now - timedelta(days=30), now),
        ]

        trend_kpis = [
            ("KPI-001", [65.0, 68.0, 70.5, 72.5], 80.0),
            ("KPI-002", [9.0, 8.8, 8.5, 8.2], 10.0),
            ("KPI-003", [3.5, 3.0, 2.5, 2.1], 3.0),
            ("KPI-004", [92.0, 90.0, 88.0, 85.0], 95.0),
            ("KPI-005", [88.0, 90.0, 91.0, 92.0], 100.0),
            ("KPI-010", [84.0, 82.0, 80.0, 78.0], 85.0),
        ]

        trend_counter = 0
        for kpi_id, values, target in trend_kpis:
            for i, (ps, pe) in enumerate(months):
                trend_counter += 1
                val = values[i]
                variance = round(((val - target) / target) * 100, 1) if target != 0 else 0.0
                trend = PerformanceTrend(
                    id=f"TRN-{trend_counter:04d}",
                    kpi_id=kpi_id,
                    period_start=ps,
                    period_end=pe,
                    value=val,
                    target=target,
                    variance_pct=variance,
                    notes=None if i < 3 else "Current period",
                )
                self._trends[trend.id] = trend

        # --- 5 Trial Scorecards ---
        scorecards_data = [
            {
                "id": "SC-001",
                "trial_id": EYLEA_TRIAL,
                "trial_name": "EYLEA HD Phase III - Wet AMD",
                "phase": "Phase III",
                "therapeutic_area": "Ophthalmology",
                "overall_score": 78.5,
                "enrollment_score": 72.0,
                "quality_score": 85.0,
                "timeline_score": 80.0,
                "budget_score": 82.0,
                "safety_score": 90.0,
                "compliance_score": 62.0,
                "last_updated": now,
                "risk_flags": ["Enrollment below target", "Protocol deviation rate elevated"],
            },
            {
                "id": "SC-002",
                "trial_id": DUPIXENT_TRIAL,
                "trial_name": "DUPIXENT Phase III - Atopic Dermatitis",
                "phase": "Phase III",
                "therapeutic_area": "Immunology",
                "overall_score": 85.2,
                "enrollment_score": 88.0,
                "quality_score": 90.0,
                "timeline_score": 78.0,
                "budget_score": 85.0,
                "safety_score": 92.0,
                "compliance_score": 88.0,
                "last_updated": now,
                "risk_flags": ["Database lock readiness declining"],
            },
            {
                "id": "SC-003",
                "trial_id": LIBTAYO_TRIAL,
                "trial_name": "LIBTAYO Phase II - NSCLC",
                "phase": "Phase II",
                "therapeutic_area": "Oncology",
                "overall_score": 82.0,
                "enrollment_score": 80.0,
                "quality_score": 84.0,
                "timeline_score": 82.0,
                "budget_score": 78.0,
                "safety_score": 95.0,
                "compliance_score": 75.0,
                "last_updated": now,
                "risk_flags": [],
            },
            {
                "id": "SC-004",
                "trial_id": ODLISIO_TRIAL,
                "trial_name": "Odlisio Phase I - Rare Disease",
                "phase": "Phase I",
                "therapeutic_area": "Rare Disease",
                "overall_score": 70.0,
                "enrollment_score": 65.0,
                "quality_score": 72.0,
                "timeline_score": 68.0,
                "budget_score": 75.0,
                "safety_score": 88.0,
                "compliance_score": 62.0,
                "last_updated": now,
                "risk_flags": ["Retention rate declining", "Enrollment challenges"],
            },
            {
                "id": "SC-005",
                "trial_id": KEVZARA_TRIAL,
                "trial_name": "KEVZARA Phase III - Rheumatoid Arthritis",
                "phase": "Phase III",
                "therapeutic_area": "Immunology",
                "overall_score": 55.0,
                "enrollment_score": 60.0,
                "quality_score": 48.0,
                "timeline_score": 45.0,
                "budget_score": 58.0,
                "safety_score": 72.0,
                "compliance_score": 50.0,
                "last_updated": now,
                "risk_flags": [
                    "SDV rate critically low",
                    "Milestone adherence critical",
                    "Quality score below threshold",
                ],
            },
        ]

        for sc in scorecards_data:
            self._scorecards[sc["id"]] = TrialScorecard(**sc)

        # --- 7 Benchmarks ---
        benchmarks_data = [
            {
                "id": "BM-001",
                "category": MetricCategory.ENROLLMENT,
                "metric_name": "Screen-to-Randomization Rate",
                "internal_value": 72.5,
                "industry_value": 68.0,
                "sponsor_target": 80.0,
                "percentile_rank": 62.0,
                "comparison_period": "Q4 2025",
                "source": BenchmarkSource.INDUSTRY,
            },
            {
                "id": "BM-002",
                "category": MetricCategory.QUALITY,
                "metric_name": "Data Query Rate",
                "internal_value": 2.1,
                "industry_value": 3.5,
                "sponsor_target": 3.0,
                "percentile_rank": 78.0,
                "comparison_period": "Q4 2025",
                "source": BenchmarkSource.INDUSTRY,
            },
            {
                "id": "BM-003",
                "category": MetricCategory.TIMELINE,
                "metric_name": "Site Activation Time (days)",
                "internal_value": 95.0,
                "industry_value": 120.0,
                "sponsor_target": 90.0,
                "percentile_rank": 72.0,
                "comparison_period": "Q4 2025",
                "source": BenchmarkSource.SPONSOR_TARGET,
            },
            {
                "id": "BM-004",
                "category": MetricCategory.BUDGET,
                "metric_name": "Cost per Patient ($K)",
                "internal_value": 42.0,
                "industry_value": 48.0,
                "sponsor_target": 40.0,
                "percentile_rank": 65.0,
                "comparison_period": "Q4 2025",
                "source": BenchmarkSource.INTERNAL,
            },
            {
                "id": "BM-005",
                "category": MetricCategory.SAFETY,
                "metric_name": "SAE Reporting Timeliness (hours)",
                "internal_value": 18.0,
                "industry_value": 22.0,
                "sponsor_target": 24.0,
                "percentile_rank": 80.0,
                "comparison_period": "Q4 2025",
                "source": BenchmarkSource.INDUSTRY,
            },
            {
                "id": "BM-006",
                "category": MetricCategory.DATA_MANAGEMENT,
                "metric_name": "CRF Completion Rate",
                "internal_value": 91.0,
                "industry_value": 88.0,
                "sponsor_target": 95.0,
                "percentile_rank": 68.0,
                "comparison_period": "Q4 2025",
                "source": BenchmarkSource.SPONSOR_TARGET,
            },
            {
                "id": "BM-007",
                "category": MetricCategory.COMPLIANCE,
                "metric_name": "Protocol Deviation Rate",
                "internal_value": 4.2,
                "industry_value": 3.8,
                "sponsor_target": 3.0,
                "percentile_rank": 42.0,
                "comparison_period": "Q4 2025",
                "source": BenchmarkSource.INDUSTRY,
            },
        ]

        for bm in benchmarks_data:
            self._benchmarks[bm["id"]] = Benchmark(**bm)

        # --- 6 Operational Alerts ---
        alerts_data = [
            {
                "id": "OA-001",
                "trial_id": EYLEA_TRIAL,
                "category": MetricCategory.ENROLLMENT,
                "severity": AlertSeverity.WARNING,
                "message": "Monthly enrollment rate 18% below target for EYLEA HD trial",
                "metric_value": 8.2,
                "threshold_value": 10.0,
                "created_date": now - timedelta(days=5),
                "acknowledged": True,
                "acknowledged_by": "Dr. Sarah Chen",
                "resolved_date": None,
            },
            {
                "id": "OA-002",
                "trial_id": EYLEA_TRIAL,
                "category": MetricCategory.COMPLIANCE,
                "severity": AlertSeverity.CRITICAL,
                "message": "Protocol deviation rate exceeds threshold across 3 sites in EYLEA trial",
                "metric_value": 4.2,
                "threshold_value": 3.0,
                "created_date": now - timedelta(days=3),
                "acknowledged": False,
                "acknowledged_by": None,
                "resolved_date": None,
            },
            {
                "id": "OA-003",
                "trial_id": DUPIXENT_TRIAL,
                "category": MetricCategory.TIMELINE,
                "severity": AlertSeverity.WARNING,
                "message": "Database lock readiness declining for DUPIXENT - at 85% vs 95% target",
                "metric_value": 85.0,
                "threshold_value": 95.0,
                "created_date": now - timedelta(days=7),
                "acknowledged": True,
                "acknowledged_by": "Michael Torres",
                "resolved_date": None,
            },
            {
                "id": "OA-004",
                "trial_id": KEVZARA_TRIAL,
                "category": MetricCategory.QUALITY,
                "severity": AlertSeverity.CRITICAL,
                "message": "Source data verification rate critically low at 55% for KEVZARA trial",
                "metric_value": 55.0,
                "threshold_value": 80.0,
                "created_date": now - timedelta(days=2),
                "acknowledged": False,
                "acknowledged_by": None,
                "resolved_date": None,
            },
            {
                "id": "OA-005",
                "trial_id": KEVZARA_TRIAL,
                "category": MetricCategory.TIMELINE,
                "severity": AlertSeverity.CRITICAL,
                "message": "Milestone adherence at 60% for KEVZARA - trial at risk of delay",
                "metric_value": 60.0,
                "threshold_value": 90.0,
                "created_date": now - timedelta(days=1),
                "acknowledged": False,
                "acknowledged_by": None,
                "resolved_date": None,
            },
            {
                "id": "OA-006",
                "trial_id": ODLISIO_TRIAL,
                "category": MetricCategory.ENROLLMENT,
                "severity": AlertSeverity.INFO,
                "message": "Retention rate trending downward for Odlisio rare disease trial",
                "metric_value": 78.0,
                "threshold_value": 85.0,
                "created_date": now - timedelta(days=10),
                "acknowledged": True,
                "acknowledged_by": "Dr. Lisa Park",
                "resolved_date": now - timedelta(days=4),
            },
        ]

        for a in alerts_data:
            self._alerts[a["id"]] = OperationalAlert(**a)

        # --- 2 Executive Reports ---
        reports_data = [
            {
                "id": "RPT-001",
                "report_period": ReportPeriod.MONTHLY,
                "period_start": now - timedelta(days=60),
                "period_end": now - timedelta(days=30),
                "generated_date": now - timedelta(days=28),
                "generated_by": "VP Clinical Operations",
                "portfolio_summary": PortfolioSummary(
                    total_trials=5,
                    trials_by_phase={"Phase I": 1, "Phase II": 1, "Phase III": 3},
                    total_sites=42,
                    total_patients=1280,
                    overall_enrollment_rate=7.5,
                    budget_utilization_pct=89.0,
                    avg_data_quality_score=82.0,
                    critical_alerts_count=2,
                    trials_on_track_pct=60.0,
                ),
                "key_achievements": [
                    "DUPIXENT trial enrollment ahead of schedule by 8%",
                    "SAE reporting compliance maintained above 98% across portfolio",
                    "Three new sites activated for LIBTAYO trial",
                ],
                "key_risks": [
                    "KEVZARA trial milestone adherence declining rapidly",
                    "Protocol deviation rate elevated in EYLEA trial",
                    "Retention challenges in Odlisio rare disease program",
                ],
                "recommendations": [
                    "Initiate CAPA for KEVZARA site quality issues",
                    "Deploy targeted monitoring for EYLEA protocol compliance",
                    "Implement patient engagement program for Odlisio retention",
                ],
            },
            {
                "id": "RPT-002",
                "report_period": ReportPeriod.QUARTERLY,
                "period_start": now - timedelta(days=90),
                "period_end": now,
                "generated_date": now - timedelta(days=1),
                "generated_by": "system",
                "portfolio_summary": PortfolioSummary(
                    total_trials=5,
                    trials_by_phase={"Phase I": 1, "Phase II": 1, "Phase III": 3},
                    total_sites=45,
                    total_patients=1350,
                    overall_enrollment_rate=8.0,
                    budget_utilization_pct=91.0,
                    avg_data_quality_score=80.5,
                    critical_alerts_count=3,
                    trials_on_track_pct=60.0,
                ),
                "key_achievements": [
                    "Portfolio enrollment reached 1350 patients milestone",
                    "Data query rate improved 40% for DUPIXENT",
                    "Budget utilization improved across 3 trials",
                ],
                "key_risks": [
                    "KEVZARA trial requires executive intervention",
                    "Overall data quality trending downward",
                    "Three critical alerts unacknowledged",
                ],
                "recommendations": [
                    "Escalate KEVZARA to steering committee",
                    "Conduct portfolio-wide data quality audit",
                    "Implement real-time alert notification system",
                    "Review and update enrollment strategies for underperforming trials",
                ],
            },
        ]

        for r in reports_data:
            self._reports[r["id"]] = ExecutiveReport(**r)

    # ------------------------------------------------------------------
    # KPI Management
    # ------------------------------------------------------------------

    def list_kpis(
        self,
        *,
        trial_id: str | None = None,
        category: MetricCategory | None = None,
        status: KPIStatus | None = None,
    ) -> list[OperationalKPI]:
        """List operational KPIs with optional filters."""
        with self._lock:
            result = list(self._kpis.values())

        if trial_id is not None:
            result = [k for k in result if k.trial_id == trial_id]
        if category is not None:
            result = [k for k in result if k.category == category]
        if status is not None:
            result = [k for k in result if k.status == status]

        return sorted(result, key=lambda k: k.id)

    def get_kpi(self, kpi_id: str) -> OperationalKPI | None:
        """Get a single KPI by ID."""
        with self._lock:
            return self._kpis.get(kpi_id)

    def create_kpi(self, payload: OperationalKPICreate) -> OperationalKPI:
        """Create a new operational KPI with automatic status/trend calculation."""
        now = datetime.now(timezone.utc)
        kpi_id = f"KPI-{uuid4().hex[:8].upper()}"

        variance = self._calculate_variance(payload.current_value, payload.target_value)
        status = self._variance_to_status(variance)
        trend = TrendDirection.STABLE  # Default for new KPIs

        kpi = OperationalKPI(
            id=kpi_id,
            trial_id=payload.trial_id,
            category=payload.category,
            metric_name=payload.metric_name,
            current_value=payload.current_value,
            target_value=payload.target_value,
            unit=payload.unit,
            trend_direction=trend,
            period_start=payload.period_start,
            period_end=payload.period_end,
            calculated_date=now,
            variance_pct=variance,
            status=status,
        )

        with self._lock:
            self._kpis[kpi_id] = kpi
        logger.info("Created KPI %s: %s", kpi_id, payload.metric_name)
        return kpi

    def update_kpi(self, kpi_id: str, payload: OperationalKPIUpdate) -> OperationalKPI | None:
        """Update an existing KPI."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._kpis.get(kpi_id)
            if existing is None:
                return None

            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            data["calculated_date"] = now

            # Recalculate variance and status
            current_val = data["current_value"]
            target_val = data["target_value"]
            data["variance_pct"] = self._calculate_variance(current_val, target_val)
            data["status"] = self._variance_to_status(data["variance_pct"])

            updated = OperationalKPI(**data)
            self._kpis[kpi_id] = updated

        return updated

    def delete_kpi(self, kpi_id: str) -> bool:
        """Delete a KPI. Returns True if deleted, False if not found."""
        with self._lock:
            if kpi_id in self._kpis:
                del self._kpis[kpi_id]
                return True
            return False

    def calculate_kpi(self, kpi_id: str) -> OperationalKPI | None:
        """Recalculate KPI variance, status, and trend direction from trend data."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._kpis.get(kpi_id)
            if existing is None:
                return None

            # Gather trend data for this KPI
            kpi_trends = sorted(
                [t for t in self._trends.values() if t.kpi_id == kpi_id],
                key=lambda t: t.period_end,
            )

        variance = self._calculate_variance(existing.current_value, existing.target_value)
        status = self._variance_to_status(variance)

        # Calculate trend direction from trend data
        trend_direction = self._compute_trend_direction(kpi_trends)

        data = existing.model_dump()
        data["variance_pct"] = variance
        data["status"] = status
        data["trend_direction"] = trend_direction
        data["calculated_date"] = now

        updated = OperationalKPI(**data)
        with self._lock:
            self._kpis[kpi_id] = updated

        return updated

    # ------------------------------------------------------------------
    # Performance Trends
    # ------------------------------------------------------------------

    def list_trends(
        self,
        *,
        kpi_id: str | None = None,
    ) -> list[PerformanceTrend]:
        """List performance trend data points with optional KPI filter."""
        with self._lock:
            result = list(self._trends.values())

        if kpi_id is not None:
            result = [t for t in result if t.kpi_id == kpi_id]

        return sorted(result, key=lambda t: (t.kpi_id, t.period_start))

    def get_trend(self, trend_id: str) -> PerformanceTrend | None:
        """Get a single trend data point by ID."""
        with self._lock:
            return self._trends.get(trend_id)

    def create_trend(self, payload: PerformanceTrendCreate) -> PerformanceTrend:
        """Create a new performance trend data point."""
        trend_id = f"TRN-{uuid4().hex[:8].upper()}"

        variance = self._calculate_variance(payload.value, payload.target)

        trend = PerformanceTrend(
            id=trend_id,
            kpi_id=payload.kpi_id,
            period_start=payload.period_start,
            period_end=payload.period_end,
            value=payload.value,
            target=payload.target,
            variance_pct=variance,
            notes=payload.notes,
        )

        with self._lock:
            self._trends[trend_id] = trend
        logger.info("Created trend %s for KPI %s", trend_id, payload.kpi_id)
        return trend

    def delete_trend(self, trend_id: str) -> bool:
        """Delete a trend data point. Returns True if deleted."""
        with self._lock:
            if trend_id in self._trends:
                del self._trends[trend_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Trial Scorecards
    # ------------------------------------------------------------------

    def list_scorecards(
        self,
        *,
        trial_id: str | None = None,
        phase: str | None = None,
        therapeutic_area: str | None = None,
    ) -> list[TrialScorecard]:
        """List trial scorecards with optional filters."""
        with self._lock:
            result = list(self._scorecards.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if phase is not None:
            result = [s for s in result if s.phase == phase]
        if therapeutic_area is not None:
            result = [s for s in result if s.therapeutic_area == therapeutic_area]

        return sorted(result, key=lambda s: s.overall_score, reverse=True)

    def get_scorecard(self, scorecard_id: str) -> TrialScorecard | None:
        """Get a single scorecard by ID."""
        with self._lock:
            return self._scorecards.get(scorecard_id)

    def create_scorecard(self, payload: TrialScorecardCreate) -> TrialScorecard:
        """Create a new trial scorecard with auto-generated scores."""
        now = datetime.now(timezone.utc)
        sc_id = f"SC-{uuid4().hex[:8].upper()}"

        # Compute scores from KPI data for this trial
        scores = self._compute_scorecard_scores(payload.trial_id)

        scorecard = TrialScorecard(
            id=sc_id,
            trial_id=payload.trial_id,
            trial_name=payload.trial_name,
            phase=payload.phase,
            therapeutic_area=payload.therapeutic_area,
            overall_score=scores["overall"],
            enrollment_score=scores["enrollment"],
            quality_score=scores["quality"],
            timeline_score=scores["timeline"],
            budget_score=scores["budget"],
            safety_score=scores["safety"],
            compliance_score=scores["compliance"],
            last_updated=now,
            risk_flags=scores["risk_flags"],
        )

        with self._lock:
            self._scorecards[sc_id] = scorecard
        logger.info("Created scorecard %s for trial %s", sc_id, payload.trial_id)
        return scorecard

    def generate_scorecard(self, scorecard_id: str) -> TrialScorecard | None:
        """Regenerate scores for an existing scorecard from current KPI data."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._scorecards.get(scorecard_id)
            if existing is None:
                return None

        scores = self._compute_scorecard_scores(existing.trial_id)

        data = existing.model_dump()
        data["overall_score"] = scores["overall"]
        data["enrollment_score"] = scores["enrollment"]
        data["quality_score"] = scores["quality"]
        data["timeline_score"] = scores["timeline"]
        data["budget_score"] = scores["budget"]
        data["safety_score"] = scores["safety"]
        data["compliance_score"] = scores["compliance"]
        data["risk_flags"] = scores["risk_flags"]
        data["last_updated"] = now

        updated = TrialScorecard(**data)
        with self._lock:
            self._scorecards[scorecard_id] = updated

        return updated

    def delete_scorecard(self, scorecard_id: str) -> bool:
        """Delete a scorecard. Returns True if deleted."""
        with self._lock:
            if scorecard_id in self._scorecards:
                del self._scorecards[scorecard_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Portfolio Summary
    # ------------------------------------------------------------------

    def get_portfolio_summary(self) -> PortfolioSummary:
        """Compute portfolio-level summary from current scorecard and KPI data."""
        with self._lock:
            scorecards = list(self._scorecards.values())
            kpis = list(self._kpis.values())
            alerts = list(self._alerts.values())

        total_trials = len(scorecards)
        trials_by_phase: dict[str, int] = {}
        for sc in scorecards:
            trials_by_phase[sc.phase] = trials_by_phase.get(sc.phase, 0) + 1

        # Compute aggregate metrics
        total_sites = 45  # Portfolio-level constant for demo
        total_patients = 1350

        # Enrollment rate from enrollment KPIs
        enrollment_kpis = [k for k in kpis if k.category == MetricCategory.ENROLLMENT]
        overall_enrollment = (
            round(sum(k.current_value for k in enrollment_kpis) / len(enrollment_kpis), 1)
            if enrollment_kpis else 0.0
        )

        # Budget from budget KPIs
        budget_kpis = [k for k in kpis if k.category == MetricCategory.BUDGET]
        budget_util = (
            round(sum(k.current_value for k in budget_kpis) / len(budget_kpis), 1)
            if budget_kpis else 0.0
        )

        # Data quality from quality KPIs
        quality_kpis = [k for k in kpis if k.category == MetricCategory.QUALITY]
        avg_quality = (
            round(sum(k.current_value for k in quality_kpis) / len(quality_kpis), 1)
            if quality_kpis else 0.0
        )

        # Critical alerts
        critical_count = sum(
            1 for a in alerts
            if a.severity == AlertSeverity.CRITICAL and a.resolved_date is None
        )

        # Trials on track (scorecard overall_score >= 70)
        on_track = sum(1 for sc in scorecards if sc.overall_score >= 70.0)
        on_track_pct = round((on_track / max(1, total_trials)) * 100, 1)

        return PortfolioSummary(
            total_trials=total_trials,
            trials_by_phase=trials_by_phase,
            total_sites=total_sites,
            total_patients=total_patients,
            overall_enrollment_rate=overall_enrollment,
            budget_utilization_pct=budget_util,
            avg_data_quality_score=avg_quality,
            critical_alerts_count=critical_count,
            trials_on_track_pct=on_track_pct,
        )

    # ------------------------------------------------------------------
    # Benchmarks
    # ------------------------------------------------------------------

    def list_benchmarks(
        self,
        *,
        category: MetricCategory | None = None,
        source: BenchmarkSource | None = None,
    ) -> list[Benchmark]:
        """List benchmarks with optional filters."""
        with self._lock:
            result = list(self._benchmarks.values())

        if category is not None:
            result = [b for b in result if b.category == category]
        if source is not None:
            result = [b for b in result if b.source == source]

        return sorted(result, key=lambda b: b.id)

    def get_benchmark(self, benchmark_id: str) -> Benchmark | None:
        """Get a single benchmark by ID."""
        with self._lock:
            return self._benchmarks.get(benchmark_id)

    def create_benchmark(self, payload: BenchmarkCreate) -> Benchmark:
        """Create a new benchmark comparison."""
        bm_id = f"BM-{uuid4().hex[:8].upper()}"

        # Calculate percentile rank
        percentile = self._calculate_percentile(
            payload.internal_value, payload.industry_value
        )

        benchmark = Benchmark(
            id=bm_id,
            category=payload.category,
            metric_name=payload.metric_name,
            internal_value=payload.internal_value,
            industry_value=payload.industry_value,
            sponsor_target=payload.sponsor_target,
            percentile_rank=percentile,
            comparison_period=payload.comparison_period,
            source=payload.source,
        )

        with self._lock:
            self._benchmarks[bm_id] = benchmark
        logger.info("Created benchmark %s: %s", bm_id, payload.metric_name)
        return benchmark

    def update_benchmark(self, benchmark_id: str, payload: BenchmarkUpdate) -> Benchmark | None:
        """Update an existing benchmark."""
        with self._lock:
            existing = self._benchmarks.get(benchmark_id)
            if existing is None:
                return None

            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)

            # Recalculate percentile
            data["percentile_rank"] = self._calculate_percentile(
                data["internal_value"], data["industry_value"]
            )

            updated = Benchmark(**data)
            self._benchmarks[benchmark_id] = updated

        return updated

    def delete_benchmark(self, benchmark_id: str) -> bool:
        """Delete a benchmark. Returns True if deleted."""
        with self._lock:
            if benchmark_id in self._benchmarks:
                del self._benchmarks[benchmark_id]
                return True
            return False

    def compare_benchmarks(
        self,
        category: MetricCategory | None = None,
    ) -> list[Benchmark]:
        """Get benchmark comparisons, optionally filtered by category.

        Returns benchmarks sorted by percentile rank (worst performing first).
        """
        benchmarks = self.list_benchmarks(category=category)
        return sorted(benchmarks, key=lambda b: b.percentile_rank)

    # ------------------------------------------------------------------
    # Operational Alerts
    # ------------------------------------------------------------------

    def list_alerts(
        self,
        *,
        trial_id: str | None = None,
        severity: AlertSeverity | None = None,
        acknowledged: bool | None = None,
        resolved: bool | None = None,
    ) -> list[OperationalAlert]:
        """List operational alerts with optional filters."""
        with self._lock:
            result = list(self._alerts.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if severity is not None:
            result = [a for a in result if a.severity == severity]
        if acknowledged is not None:
            result = [a for a in result if a.acknowledged == acknowledged]
        if resolved is not None:
            if resolved:
                result = [a for a in result if a.resolved_date is not None]
            else:
                result = [a for a in result if a.resolved_date is None]

        return sorted(result, key=lambda a: a.created_date, reverse=True)

    def get_alert(self, alert_id: str) -> OperationalAlert | None:
        """Get a single alert by ID."""
        with self._lock:
            return self._alerts.get(alert_id)

    def create_alert(self, payload: OperationalAlertCreate) -> OperationalAlert:
        """Create a new operational alert."""
        now = datetime.now(timezone.utc)
        alert_id = f"OA-{uuid4().hex[:8].upper()}"

        alert = OperationalAlert(
            id=alert_id,
            trial_id=payload.trial_id,
            category=payload.category,
            severity=payload.severity,
            message=payload.message,
            metric_value=payload.metric_value,
            threshold_value=payload.threshold_value,
            created_date=now,
            acknowledged=False,
            acknowledged_by=None,
            resolved_date=None,
        )

        with self._lock:
            self._alerts[alert_id] = alert
        logger.info("Created alert %s: %s", alert_id, payload.message)
        return alert

    def acknowledge_alert(self, alert_id: str, payload: AlertAcknowledge) -> OperationalAlert | None:
        """Acknowledge an operational alert."""
        with self._lock:
            existing = self._alerts.get(alert_id)
            if existing is None:
                return None

            if existing.acknowledged:
                raise ValueError(f"Alert '{alert_id}' is already acknowledged")

            data = existing.model_dump()
            data["acknowledged"] = True
            data["acknowledged_by"] = payload.acknowledged_by
            updated = OperationalAlert(**data)
            self._alerts[alert_id] = updated

        return updated

    def resolve_alert(self, alert_id: str, payload: AlertResolve) -> OperationalAlert | None:
        """Resolve an operational alert."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._alerts.get(alert_id)
            if existing is None:
                return None

            if existing.resolved_date is not None:
                raise ValueError(f"Alert '{alert_id}' is already resolved")

            data = existing.model_dump()
            data["resolved_date"] = now
            data["acknowledged"] = True
            data["acknowledged_by"] = data["acknowledged_by"] or payload.resolved_by
            updated = OperationalAlert(**data)
            self._alerts[alert_id] = updated

        logger.info("Resolved alert %s by %s", alert_id, payload.resolved_by)
        return updated

    def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert. Returns True if deleted."""
        with self._lock:
            if alert_id in self._alerts:
                del self._alerts[alert_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Executive Reports
    # ------------------------------------------------------------------

    def list_reports(
        self,
        *,
        report_period: ReportPeriod | None = None,
    ) -> list[ExecutiveReport]:
        """List executive reports with optional period filter."""
        with self._lock:
            result = list(self._reports.values())

        if report_period is not None:
            result = [r for r in result if r.report_period == report_period]

        return sorted(result, key=lambda r: r.generated_date, reverse=True)

    def get_report(self, report_id: str) -> ExecutiveReport | None:
        """Get a single executive report by ID."""
        with self._lock:
            return self._reports.get(report_id)

    def generate_executive_report(self, payload: ExecutiveReportGenerate) -> ExecutiveReport:
        """Generate a new executive report from current portfolio data."""
        now = datetime.now(timezone.utc)
        report_id = f"RPT-{uuid4().hex[:8].upper()}"

        portfolio = self.get_portfolio_summary()

        # Auto-generate achievements, risks, and recommendations
        achievements = self._generate_achievements()
        risks = self._generate_risks()
        recommendations = self._generate_recommendations(risks)

        report = ExecutiveReport(
            id=report_id,
            report_period=payload.report_period,
            period_start=payload.period_start,
            period_end=payload.period_end,
            generated_date=now,
            generated_by=payload.generated_by,
            portfolio_summary=portfolio,
            key_achievements=achievements,
            key_risks=risks,
            recommendations=recommendations,
        )

        with self._lock:
            self._reports[report_id] = report
        logger.info("Generated executive report %s for period %s", report_id, payload.report_period.value)
        return report

    def delete_report(self, report_id: str) -> bool:
        """Delete a report. Returns True if deleted."""
        with self._lock:
            if report_id in self._reports:
                del self._reports[report_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def get_dashboard_metrics(self) -> DashboardMetrics:
        """Compute aggregated dashboard metrics."""
        with self._lock:
            kpis = list(self._kpis.values())
            alerts = list(self._alerts.values())
            scorecards = list(self._scorecards.values())
            benchmarks = list(self._benchmarks.values())

        portfolio = self.get_portfolio_summary()

        on_target = sum(1 for k in kpis if k.status == KPIStatus.ON_TARGET)
        at_risk = sum(1 for k in kpis if k.status == KPIStatus.AT_RISK)
        off_target = sum(1 for k in kpis if k.status == KPIStatus.OFF_TARGET)

        active_alerts = sum(1 for a in alerts if a.resolved_date is None)
        critical_alerts = sum(
            1 for a in alerts
            if a.severity == AlertSeverity.CRITICAL and a.resolved_date is None
        )

        avg_score = (
            round(sum(s.overall_score for s in scorecards) / len(scorecards), 1)
            if scorecards else 0.0
        )

        # Top risks from scorecards
        top_risks: list[str] = []
        for sc in sorted(scorecards, key=lambda s: s.overall_score):
            for flag in sc.risk_flags:
                if flag not in top_risks:
                    top_risks.append(flag)
                if len(top_risks) >= 5:
                    break
            if len(top_risks) >= 5:
                break

        return DashboardMetrics(
            portfolio_summary=portfolio,
            total_kpis=len(kpis),
            kpis_on_target=on_target,
            kpis_at_risk=at_risk,
            kpis_off_target=off_target,
            active_alerts=active_alerts,
            critical_alerts=critical_alerts,
            total_scorecards=len(scorecards),
            avg_overall_score=avg_score,
            total_benchmarks=len(benchmarks),
            top_risks=top_risks,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_variance(current: float, target: float) -> float:
        """Calculate variance percentage from target."""
        if target == 0:
            return 0.0
        return round(((current - target) / abs(target)) * 100, 1)

    @staticmethod
    def _variance_to_status(variance: float) -> KPIStatus:
        """Map variance percentage to KPI status."""
        if variance >= VARIANCE_ON_TARGET:
            return KPIStatus.ON_TARGET
        elif variance >= VARIANCE_AT_RISK:
            return KPIStatus.AT_RISK
        else:
            return KPIStatus.OFF_TARGET

    @staticmethod
    def _compute_trend_direction(trends: list[PerformanceTrend]) -> TrendDirection:
        """Compute trend direction from recent trend data points."""
        if len(trends) < 2:
            return TrendDirection.STABLE

        recent = trends[-2:]
        diff = recent[-1].variance_pct - recent[0].variance_pct

        if recent[-1].variance_pct < -30:
            return TrendDirection.CRITICAL
        elif diff > 3:
            return TrendDirection.IMPROVING
        elif diff < -3:
            return TrendDirection.DECLINING
        else:
            return TrendDirection.STABLE

    @staticmethod
    def _calculate_percentile(internal: float, industry: float) -> float:
        """Calculate a percentile rank based on internal vs industry comparison.

        Simple heuristic: if internal equals industry, rank is 50.
        Better performance pushes toward 100, worse toward 0.
        """
        if industry == 0:
            return 50.0
        ratio = internal / industry
        # Map ratio to percentile (1.0 = 50th percentile)
        percentile = min(100.0, max(0.0, ratio * 50.0))
        return round(percentile, 1)

    def _compute_scorecard_scores(self, trial_id: str) -> dict:
        """Compute dimension scores for a trial from its KPI data."""
        with self._lock:
            trial_kpis = [k for k in self._kpis.values() if k.trial_id == trial_id]

        # Map categories to dimension scores
        category_map = {
            MetricCategory.ENROLLMENT: "enrollment",
            MetricCategory.QUALITY: "quality",
            MetricCategory.TIMELINE: "timeline",
            MetricCategory.BUDGET: "budget",
            MetricCategory.SAFETY: "safety",
            MetricCategory.COMPLIANCE: "compliance",
        }

        dimension_scores: dict[str, list[float]] = {
            dim: [] for dim in category_map.values()
        }

        risk_flags: list[str] = []

        for kpi in trial_kpis:
            dim = category_map.get(kpi.category)
            if dim is None:
                continue

            # Convert KPI to a 0-100 score
            score = self._kpi_to_score(kpi)
            dimension_scores[dim].append(score)

            # Generate risk flags for poor performers
            if kpi.status == KPIStatus.OFF_TARGET:
                risk_flags.append(f"{kpi.metric_name} off target ({kpi.variance_pct:+.1f}%)")
            elif kpi.trend_direction == TrendDirection.CRITICAL:
                risk_flags.append(f"{kpi.metric_name} trending critical")

        # Calculate averages, default to 75 if no data for a dimension
        result: dict[str, float] = {}
        for dim, scores_list in dimension_scores.items():
            if scores_list:
                result[dim] = round(sum(scores_list) / len(scores_list), 1)
            else:
                result[dim] = 75.0

        # Overall is weighted average of all dimensions
        all_scores = list(result.values())
        result["overall"] = round(sum(all_scores) / max(1, len(all_scores)), 1)
        result["risk_flags"] = risk_flags  # type: ignore[assignment]

        return result

    @staticmethod
    def _kpi_to_score(kpi: OperationalKPI) -> float:
        """Convert a KPI to a 0-100 score based on variance from target."""
        # ON_TARGET: 80-100, AT_RISK: 50-80, OFF_TARGET: 0-50
        if kpi.status == KPIStatus.ON_TARGET:
            return min(100.0, 80.0 + max(0.0, kpi.variance_pct + 5) * 2)
        elif kpi.status == KPIStatus.AT_RISK:
            return max(50.0, 80.0 + kpi.variance_pct)
        else:
            return max(0.0, 50.0 + kpi.variance_pct)

    def _generate_achievements(self) -> list[str]:
        """Generate key achievements from current data."""
        achievements = []

        with self._lock:
            kpis = list(self._kpis.values())
            scorecards = list(self._scorecards.values())

        # Find top-performing KPIs
        on_target_kpis = [k for k in kpis if k.status == KPIStatus.ON_TARGET]
        for kpi in on_target_kpis[:3]:
            achievements.append(
                f"{kpi.metric_name} on target at {kpi.current_value}{kpi.unit}"
            )

        # Top scoring trial
        if scorecards:
            best = max(scorecards, key=lambda s: s.overall_score)
            achievements.append(
                f"{best.trial_name} leading portfolio with {best.overall_score:.0f}% overall score"
            )

        return achievements

    def _generate_risks(self) -> list[str]:
        """Generate key risks from current data."""
        risks = []

        with self._lock:
            kpis = list(self._kpis.values())
            alerts = list(self._alerts.values())

        # Off-target KPIs
        off_target = [k for k in kpis if k.status == KPIStatus.OFF_TARGET]
        for kpi in off_target:
            risks.append(
                f"{kpi.metric_name} {kpi.variance_pct:+.1f}% from target"
            )

        # Unresolved critical alerts
        critical = [a for a in alerts if a.severity == AlertSeverity.CRITICAL and a.resolved_date is None]
        if critical:
            risks.append(f"{len(critical)} unresolved critical alert(s)")

        return risks

    def _generate_recommendations(self, risks: list[str]) -> list[str]:
        """Generate recommendations based on identified risks."""
        recommendations = []

        if any("enrollment" in r.lower() for r in risks):
            recommendations.append("Review and optimize enrollment strategies across underperforming sites")
        if any("deviation" in r.lower() or "compliance" in r.lower() for r in risks):
            recommendations.append("Implement enhanced protocol training at sites with elevated deviation rates")
        if any("critical alert" in r.lower() for r in risks):
            recommendations.append("Escalate unresolved critical alerts to steering committee immediately")
        if any("quality" in r.lower() or "sdv" in r.lower() for r in risks):
            recommendations.append("Conduct targeted data quality audit at underperforming sites")
        if any("milestone" in r.lower() or "timeline" in r.lower() for r in risks):
            recommendations.append("Reassess timelines and resource allocation for at-risk trials")

        if not recommendations:
            recommendations.append("Continue monitoring current performance trends")

        return recommendations


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ClinicalOpsMetricsService | None = None
_instance_lock = threading.Lock()


def get_clinical_ops_metrics_service() -> ClinicalOpsMetricsService:
    """Return the singleton ClinicalOpsMetricsService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ClinicalOpsMetricsService()
    return _instance


def reset_clinical_ops_metrics_service() -> ClinicalOpsMetricsService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ClinicalOpsMetricsService()
    return _instance
