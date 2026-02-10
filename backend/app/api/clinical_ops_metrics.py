"""Clinical Operations Metrics Dashboard API endpoints.

Provides comprehensive operational KPIs, performance tracking, trend analysis,
benchmarking, operational alerts, executive reporting, and dashboard metrics
across the clinical trial portfolio.

Endpoints:
    GET    /clinical-ops-metrics/kpis                              - List KPIs
    GET    /clinical-ops-metrics/kpis/{kpi_id}                     - Get single KPI
    POST   /clinical-ops-metrics/kpis                              - Create KPI
    PUT    /clinical-ops-metrics/kpis/{kpi_id}                     - Update KPI
    DELETE /clinical-ops-metrics/kpis/{kpi_id}                     - Delete KPI
    POST   /clinical-ops-metrics/kpis/{kpi_id}/calculate           - Calculate KPI
    GET    /clinical-ops-metrics/trends                            - List trends
    GET    /clinical-ops-metrics/trends/{trend_id}                 - Get single trend
    POST   /clinical-ops-metrics/trends                            - Create trend
    DELETE /clinical-ops-metrics/trends/{trend_id}                 - Delete trend
    GET    /clinical-ops-metrics/scorecards                        - List scorecards
    GET    /clinical-ops-metrics/scorecards/{scorecard_id}         - Get single scorecard
    POST   /clinical-ops-metrics/scorecards                        - Create scorecard
    POST   /clinical-ops-metrics/scorecards/{scorecard_id}/generate - Regenerate scorecard
    DELETE /clinical-ops-metrics/scorecards/{scorecard_id}         - Delete scorecard
    GET    /clinical-ops-metrics/portfolio-summary                 - Portfolio summary
    GET    /clinical-ops-metrics/benchmarks                        - List benchmarks
    GET    /clinical-ops-metrics/benchmarks/{benchmark_id}         - Get single benchmark
    POST   /clinical-ops-metrics/benchmarks                        - Create benchmark
    PUT    /clinical-ops-metrics/benchmarks/{benchmark_id}         - Update benchmark
    DELETE /clinical-ops-metrics/benchmarks/{benchmark_id}         - Delete benchmark
    GET    /clinical-ops-metrics/benchmarks/compare                - Compare benchmarks
    GET    /clinical-ops-metrics/alerts                            - List alerts
    GET    /clinical-ops-metrics/alerts/{alert_id}                 - Get single alert
    POST   /clinical-ops-metrics/alerts                            - Create alert
    POST   /clinical-ops-metrics/alerts/{alert_id}/acknowledge     - Acknowledge alert
    POST   /clinical-ops-metrics/alerts/{alert_id}/resolve         - Resolve alert
    DELETE /clinical-ops-metrics/alerts/{alert_id}                 - Delete alert
    GET    /clinical-ops-metrics/reports                           - List reports
    GET    /clinical-ops-metrics/reports/{report_id}               - Get single report
    POST   /clinical-ops-metrics/reports/generate                  - Generate report
    DELETE /clinical-ops-metrics/reports/{report_id}               - Delete report
    GET    /clinical-ops-metrics/dashboard                         - Dashboard metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.clinical_ops_metrics import (
    AlertAcknowledge,
    AlertResolve,
    AlertSeverity,
    Benchmark,
    BenchmarkCreate,
    BenchmarkListResponse,
    BenchmarkSource,
    BenchmarkUpdate,
    DashboardMetrics,
    ExecutiveReport,
    ExecutiveReportGenerate,
    ExecutiveReportListResponse,
    KPIStatus,
    MetricCategory,
    OperationalAlert,
    OperationalAlertCreate,
    OperationalAlertListResponse,
    OperationalKPI,
    OperationalKPICreate,
    OperationalKPIListResponse,
    OperationalKPIUpdate,
    PerformanceTrend,
    PerformanceTrendCreate,
    PerformanceTrendListResponse,
    PortfolioSummary,
    ReportPeriod,
    TrialScorecard,
    TrialScorecardCreate,
    TrialScorecardListResponse,
)
from app.services.clinical_ops_metrics_service import get_clinical_ops_metrics_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/clinical-ops-metrics",
    tags=["Clinical Operations Metrics"],
)


# ---------------------------------------------------------------------------
# KPI Management
# ---------------------------------------------------------------------------


@router.get(
    "/kpis",
    response_model=OperationalKPIListResponse,
    summary="List operational KPIs",
    description="Retrieve operational KPIs with optional filtering by trial, category, and status.",
)
async def list_kpis(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    category: Optional[MetricCategory] = Query(None, description="Filter by metric category"),
    status: Optional[KPIStatus] = Query(None, description="Filter by KPI status"),
) -> OperationalKPIListResponse:
    svc = get_clinical_ops_metrics_service()
    items = svc.list_kpis(trial_id=trial_id, category=category, status=status)
    return OperationalKPIListResponse(items=items, total=len(items))


@router.get(
    "/kpis/{kpi_id}",
    response_model=OperationalKPI,
    summary="Get an operational KPI",
)
async def get_kpi(kpi_id: str) -> OperationalKPI:
    svc = get_clinical_ops_metrics_service()
    kpi = svc.get_kpi(kpi_id)
    if kpi is None:
        raise HTTPException(status_code=404, detail=f"KPI '{kpi_id}' not found")
    return kpi


@router.post(
    "/kpis",
    response_model=OperationalKPI,
    status_code=201,
    summary="Create an operational KPI",
)
async def create_kpi(payload: OperationalKPICreate) -> OperationalKPI:
    svc = get_clinical_ops_metrics_service()
    return svc.create_kpi(payload)


@router.put(
    "/kpis/{kpi_id}",
    response_model=OperationalKPI,
    summary="Update an operational KPI",
)
async def update_kpi(kpi_id: str, payload: OperationalKPIUpdate) -> OperationalKPI:
    svc = get_clinical_ops_metrics_service()
    updated = svc.update_kpi(kpi_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"KPI '{kpi_id}' not found")
    return updated


@router.delete(
    "/kpis/{kpi_id}",
    status_code=204,
    summary="Delete an operational KPI",
)
async def delete_kpi(kpi_id: str) -> None:
    svc = get_clinical_ops_metrics_service()
    deleted = svc.delete_kpi(kpi_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"KPI '{kpi_id}' not found")


@router.post(
    "/kpis/{kpi_id}/calculate",
    response_model=OperationalKPI,
    summary="Calculate KPI metrics",
    description="Recalculate KPI variance, status, and trend direction from associated trend data.",
)
async def calculate_kpi(kpi_id: str) -> OperationalKPI:
    svc = get_clinical_ops_metrics_service()
    result = svc.calculate_kpi(kpi_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"KPI '{kpi_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Performance Trends
# ---------------------------------------------------------------------------


@router.get(
    "/trends",
    response_model=PerformanceTrendListResponse,
    summary="List performance trends",
    description="Retrieve performance trend data points with optional KPI filter.",
)
async def list_trends(
    kpi_id: Optional[str] = Query(None, description="Filter by KPI ID"),
) -> PerformanceTrendListResponse:
    svc = get_clinical_ops_metrics_service()
    items = svc.list_trends(kpi_id=kpi_id)
    return PerformanceTrendListResponse(items=items, total=len(items))


@router.get(
    "/trends/{trend_id}",
    response_model=PerformanceTrend,
    summary="Get a performance trend data point",
)
async def get_trend(trend_id: str) -> PerformanceTrend:
    svc = get_clinical_ops_metrics_service()
    trend = svc.get_trend(trend_id)
    if trend is None:
        raise HTTPException(status_code=404, detail=f"Trend '{trend_id}' not found")
    return trend


@router.post(
    "/trends",
    response_model=PerformanceTrend,
    status_code=201,
    summary="Create a performance trend data point",
)
async def create_trend(payload: PerformanceTrendCreate) -> PerformanceTrend:
    svc = get_clinical_ops_metrics_service()
    return svc.create_trend(payload)


@router.delete(
    "/trends/{trend_id}",
    status_code=204,
    summary="Delete a performance trend data point",
)
async def delete_trend(trend_id: str) -> None:
    svc = get_clinical_ops_metrics_service()
    deleted = svc.delete_trend(trend_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Trend '{trend_id}' not found")


# ---------------------------------------------------------------------------
# Trial Scorecards
# ---------------------------------------------------------------------------


@router.get(
    "/scorecards",
    response_model=TrialScorecardListResponse,
    summary="List trial scorecards",
    description="Retrieve trial scorecards with optional filtering by trial, phase, and therapeutic area.",
)
async def list_scorecards(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    phase: Optional[str] = Query(None, description="Filter by trial phase"),
    therapeutic_area: Optional[str] = Query(None, description="Filter by therapeutic area"),
) -> TrialScorecardListResponse:
    svc = get_clinical_ops_metrics_service()
    items = svc.list_scorecards(trial_id=trial_id, phase=phase, therapeutic_area=therapeutic_area)
    return TrialScorecardListResponse(items=items, total=len(items))


@router.get(
    "/scorecards/{scorecard_id}",
    response_model=TrialScorecard,
    summary="Get a trial scorecard",
)
async def get_scorecard(scorecard_id: str) -> TrialScorecard:
    svc = get_clinical_ops_metrics_service()
    scorecard = svc.get_scorecard(scorecard_id)
    if scorecard is None:
        raise HTTPException(status_code=404, detail=f"Scorecard '{scorecard_id}' not found")
    return scorecard


@router.post(
    "/scorecards",
    response_model=TrialScorecard,
    status_code=201,
    summary="Create a trial scorecard",
    description="Create a new trial scorecard with auto-generated dimension scores from KPI data.",
)
async def create_scorecard(payload: TrialScorecardCreate) -> TrialScorecard:
    svc = get_clinical_ops_metrics_service()
    return svc.create_scorecard(payload)


@router.post(
    "/scorecards/{scorecard_id}/generate",
    response_model=TrialScorecard,
    summary="Regenerate scorecard scores",
    description="Regenerate dimension scores for a scorecard from current KPI data.",
)
async def generate_scorecard(scorecard_id: str) -> TrialScorecard:
    svc = get_clinical_ops_metrics_service()
    result = svc.generate_scorecard(scorecard_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Scorecard '{scorecard_id}' not found")
    return result


@router.delete(
    "/scorecards/{scorecard_id}",
    status_code=204,
    summary="Delete a trial scorecard",
)
async def delete_scorecard(scorecard_id: str) -> None:
    svc = get_clinical_ops_metrics_service()
    deleted = svc.delete_scorecard(scorecard_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Scorecard '{scorecard_id}' not found")


# ---------------------------------------------------------------------------
# Portfolio Summary
# ---------------------------------------------------------------------------


@router.get(
    "/portfolio-summary",
    response_model=PortfolioSummary,
    summary="Get portfolio summary",
    description="Compute portfolio-level summary metrics from current scorecard and KPI data.",
)
async def get_portfolio_summary() -> PortfolioSummary:
    svc = get_clinical_ops_metrics_service()
    return svc.get_portfolio_summary()


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------


@router.get(
    "/benchmarks/compare",
    response_model=BenchmarkListResponse,
    summary="Compare benchmarks",
    description="Get benchmark comparisons sorted by percentile rank (worst performing first).",
)
async def compare_benchmarks(
    category: Optional[MetricCategory] = Query(None, description="Filter by metric category"),
) -> BenchmarkListResponse:
    svc = get_clinical_ops_metrics_service()
    items = svc.compare_benchmarks(category=category)
    return BenchmarkListResponse(items=items, total=len(items))


@router.get(
    "/benchmarks",
    response_model=BenchmarkListResponse,
    summary="List benchmarks",
    description="Retrieve benchmark comparisons with optional filtering by category and source.",
)
async def list_benchmarks(
    category: Optional[MetricCategory] = Query(None, description="Filter by metric category"),
    source: Optional[BenchmarkSource] = Query(None, description="Filter by benchmark source"),
) -> BenchmarkListResponse:
    svc = get_clinical_ops_metrics_service()
    items = svc.list_benchmarks(category=category, source=source)
    return BenchmarkListResponse(items=items, total=len(items))


@router.get(
    "/benchmarks/{benchmark_id}",
    response_model=Benchmark,
    summary="Get a benchmark",
)
async def get_benchmark(benchmark_id: str) -> Benchmark:
    svc = get_clinical_ops_metrics_service()
    benchmark = svc.get_benchmark(benchmark_id)
    if benchmark is None:
        raise HTTPException(status_code=404, detail=f"Benchmark '{benchmark_id}' not found")
    return benchmark


@router.post(
    "/benchmarks",
    response_model=Benchmark,
    status_code=201,
    summary="Create a benchmark comparison",
)
async def create_benchmark(payload: BenchmarkCreate) -> Benchmark:
    svc = get_clinical_ops_metrics_service()
    return svc.create_benchmark(payload)


@router.put(
    "/benchmarks/{benchmark_id}",
    response_model=Benchmark,
    summary="Update a benchmark comparison",
)
async def update_benchmark(benchmark_id: str, payload: BenchmarkUpdate) -> Benchmark:
    svc = get_clinical_ops_metrics_service()
    updated = svc.update_benchmark(benchmark_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Benchmark '{benchmark_id}' not found")
    return updated


@router.delete(
    "/benchmarks/{benchmark_id}",
    status_code=204,
    summary="Delete a benchmark comparison",
)
async def delete_benchmark(benchmark_id: str) -> None:
    svc = get_clinical_ops_metrics_service()
    deleted = svc.delete_benchmark(benchmark_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Benchmark '{benchmark_id}' not found")


# ---------------------------------------------------------------------------
# Operational Alerts
# ---------------------------------------------------------------------------


@router.get(
    "/alerts",
    response_model=OperationalAlertListResponse,
    summary="List operational alerts",
    description="Retrieve operational alerts with optional filtering by trial, severity, and status.",
)
async def list_alerts(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity"),
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledged status"),
    resolved: Optional[bool] = Query(None, description="Filter by resolved status"),
) -> OperationalAlertListResponse:
    svc = get_clinical_ops_metrics_service()
    items = svc.list_alerts(
        trial_id=trial_id, severity=severity, acknowledged=acknowledged, resolved=resolved
    )
    return OperationalAlertListResponse(items=items, total=len(items))


@router.get(
    "/alerts/{alert_id}",
    response_model=OperationalAlert,
    summary="Get an operational alert",
)
async def get_alert(alert_id: str) -> OperationalAlert:
    svc = get_clinical_ops_metrics_service()
    alert = svc.get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return alert


@router.post(
    "/alerts",
    response_model=OperationalAlert,
    status_code=201,
    summary="Create an operational alert",
)
async def create_alert(payload: OperationalAlertCreate) -> OperationalAlert:
    svc = get_clinical_ops_metrics_service()
    return svc.create_alert(payload)


@router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=OperationalAlert,
    summary="Acknowledge an operational alert",
)
async def acknowledge_alert(alert_id: str, payload: AlertAcknowledge) -> OperationalAlert:
    svc = get_clinical_ops_metrics_service()
    try:
        result = svc.acknowledge_alert(alert_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return result


@router.post(
    "/alerts/{alert_id}/resolve",
    response_model=OperationalAlert,
    summary="Resolve an operational alert",
)
async def resolve_alert(alert_id: str, payload: AlertResolve) -> OperationalAlert:
    svc = get_clinical_ops_metrics_service()
    try:
        result = svc.resolve_alert(alert_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return result


@router.delete(
    "/alerts/{alert_id}",
    status_code=204,
    summary="Delete an operational alert",
)
async def delete_alert(alert_id: str) -> None:
    svc = get_clinical_ops_metrics_service()
    deleted = svc.delete_alert(alert_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")


# ---------------------------------------------------------------------------
# Executive Reports
# ---------------------------------------------------------------------------


@router.get(
    "/reports",
    response_model=ExecutiveReportListResponse,
    summary="List executive reports",
    description="Retrieve executive reports with optional filtering by report period.",
)
async def list_reports(
    report_period: Optional[ReportPeriod] = Query(None, description="Filter by report period"),
) -> ExecutiveReportListResponse:
    svc = get_clinical_ops_metrics_service()
    items = svc.list_reports(report_period=report_period)
    return ExecutiveReportListResponse(items=items, total=len(items))


@router.get(
    "/reports/{report_id}",
    response_model=ExecutiveReport,
    summary="Get an executive report",
)
async def get_report(report_id: str) -> ExecutiveReport:
    svc = get_clinical_ops_metrics_service()
    report = svc.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return report


@router.post(
    "/reports/generate",
    response_model=ExecutiveReport,
    status_code=201,
    summary="Generate an executive report",
    description="Generate a new executive report with portfolio summary, achievements, risks, and recommendations.",
)
async def generate_executive_report(payload: ExecutiveReportGenerate) -> ExecutiveReport:
    svc = get_clinical_ops_metrics_service()
    return svc.generate_executive_report(payload)


@router.delete(
    "/reports/{report_id}",
    status_code=204,
    summary="Delete an executive report",
)
async def delete_report(report_id: str) -> None:
    svc = get_clinical_ops_metrics_service()
    deleted = svc.delete_report(report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get(
    "/dashboard",
    response_model=DashboardMetrics,
    summary="Get dashboard metrics",
    description="Aggregated dashboard metrics including portfolio summary, KPI status breakdown, "
                "alert counts, scorecard averages, and top risks.",
)
async def get_dashboard_metrics() -> DashboardMetrics:
    svc = get_clinical_ops_metrics_service()
    return svc.get_dashboard_metrics()
