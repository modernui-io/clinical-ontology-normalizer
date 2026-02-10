"""Clinical Monitoring API endpoints (CLINICAL-18).

Provides comprehensive CRA monitoring operations: visit scheduling and
lifecycle (scheduled -> confirmed -> in_progress -> completed -> report_pending),
source data verification (SDV) tracking, monitoring findings with severity and
category classification, CAPA workflow integration, monitoring report management,
and aggregated monitoring metrics.

Endpoints:
    GET    /clinical-monitoring/visits                                - List monitoring visits
    GET    /clinical-monitoring/visits/{visit_id}                     - Get single visit
    POST   /clinical-monitoring/visits                                - Create/schedule visit
    PUT    /clinical-monitoring/visits/{visit_id}                     - Update visit
    DELETE /clinical-monitoring/visits/{visit_id}                     - Delete visit
    POST   /clinical-monitoring/visits/{visit_id}/confirm             - Confirm visit
    POST   /clinical-monitoring/visits/{visit_id}/start               - Start visit
    POST   /clinical-monitoring/visits/{visit_id}/complete            - Complete visit
    POST   /clinical-monitoring/visits/{visit_id}/cancel              - Cancel visit
    GET    /clinical-monitoring/findings                              - List findings
    GET    /clinical-monitoring/findings/{finding_id}                 - Get single finding
    POST   /clinical-monitoring/findings                              - Create finding
    PUT    /clinical-monitoring/findings/{finding_id}                 - Update finding
    POST   /clinical-monitoring/findings/{finding_id}/resolve         - Resolve finding
    POST   /clinical-monitoring/findings/{finding_id}/escalate        - Escalate finding
    GET    /clinical-monitoring/sdv                                   - List SDV records
    GET    /clinical-monitoring/sdv/{sdv_id}                          - Get single SDV record
    POST   /clinical-monitoring/sdv                                   - Record SDV
    GET    /clinical-monitoring/sdv/rate/{site_id}                    - Get SDV rate by site
    GET    /clinical-monitoring/sdv/summary                           - Get SDV summary
    GET    /clinical-monitoring/reports                               - List reports
    GET    /clinical-monitoring/reports/{report_id}                   - Get single report
    POST   /clinical-monitoring/reports                               - Create report
    PUT    /clinical-monitoring/reports/{report_id}                   - Update report
    POST   /clinical-monitoring/reports/{report_id}/submit            - Submit report
    POST   /clinical-monitoring/reports/{report_id}/approve           - Approve report
    GET    /clinical-monitoring/capas                                 - List CAPA items
    GET    /clinical-monitoring/capas/{capa_id}                       - Get single CAPA
    POST   /clinical-monitoring/capas                                 - Create CAPA
    PUT    /clinical-monitoring/capas/{capa_id}                       - Update CAPA
    POST   /clinical-monitoring/capas/{capa_id}/close                 - Close CAPA
    GET    /clinical-monitoring/metrics                               - Get monitoring metrics
    GET    /clinical-monitoring/site-summary/{site_id}                - Get site monitoring summary
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.clinical_monitoring import (
    CAPAItem,
    CAPAItemCreate,
    CAPAItemListResponse,
    CAPAItemUpdate,
    CAPAStatus,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
    MonitoringFinding,
    MonitoringFindingCreate,
    MonitoringFindingListResponse,
    MonitoringFindingUpdate,
    MonitoringMetrics,
    MonitoringReport,
    MonitoringReportCreate,
    MonitoringReportListResponse,
    MonitoringReportUpdate,
    MonitoringVisit,
    MonitoringVisitCreate,
    MonitoringVisitListResponse,
    MonitoringVisitUpdate,
    ReportStatus,
    ReportSubmitPayload,
    SDVRecord,
    SDVRecordCreate,
    SDVRecordListResponse,
    SDVSiteSummary,
    SDVStatus,
    SiteMonitoringSummary,
    VisitCompletePayload,
    VisitStartPayload,
    VisitStatus,
    VisitType,
)
from app.services.clinical_monitoring_service import get_clinical_monitoring_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/clinical-monitoring",
    tags=["Clinical Monitoring"],
)


# ---------------------------------------------------------------------------
# Visit CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/visits",
    response_model=MonitoringVisitListResponse,
    summary="List monitoring visits",
    description="Retrieve monitoring visits with optional filtering by trial, site, type, status, and CRA.",
)
async def list_visits(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    visit_type: Optional[VisitType] = Query(None, description="Filter by visit type"),
    status: Optional[VisitStatus] = Query(None, description="Filter by visit status"),
    cra_id: Optional[str] = Query(None, description="Filter by CRA ID"),
) -> MonitoringVisitListResponse:
    svc = get_clinical_monitoring_service()
    items = svc.list_visits(
        trial_id=trial_id, site_id=site_id, visit_type=visit_type,
        status=status, cra_id=cra_id,
    )
    return MonitoringVisitListResponse(items=items, total=len(items))


@router.get(
    "/visits/{visit_id}",
    response_model=MonitoringVisit,
    summary="Get a monitoring visit",
)
async def get_visit(visit_id: str) -> MonitoringVisit:
    svc = get_clinical_monitoring_service()
    visit = svc.get_visit(visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail=f"Visit '{visit_id}' not found")
    return visit


@router.post(
    "/visits",
    response_model=MonitoringVisit,
    status_code=201,
    summary="Schedule a monitoring visit",
    description="Create a new monitoring visit in scheduled status.",
)
async def create_visit(payload: MonitoringVisitCreate) -> MonitoringVisit:
    svc = get_clinical_monitoring_service()
    return svc.create_visit(payload)


@router.put(
    "/visits/{visit_id}",
    response_model=MonitoringVisit,
    summary="Update a monitoring visit",
)
async def update_visit(visit_id: str, payload: MonitoringVisitUpdate) -> MonitoringVisit:
    svc = get_clinical_monitoring_service()
    updated = svc.update_visit(visit_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Visit '{visit_id}' not found")
    return updated


@router.delete(
    "/visits/{visit_id}",
    status_code=204,
    summary="Delete a monitoring visit",
)
async def delete_visit(visit_id: str) -> None:
    svc = get_clinical_monitoring_service()
    deleted = svc.delete_visit(visit_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Visit '{visit_id}' not found")


# ---------------------------------------------------------------------------
# Visit Lifecycle
# ---------------------------------------------------------------------------


@router.post(
    "/visits/{visit_id}/confirm",
    response_model=MonitoringVisit,
    summary="Confirm a scheduled visit",
    description="Transition visit from scheduled to confirmed status.",
)
async def confirm_visit(visit_id: str) -> MonitoringVisit:
    svc = get_clinical_monitoring_service()
    try:
        result = svc.confirm_visit(visit_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Visit '{visit_id}' not found")
    return result


@router.post(
    "/visits/{visit_id}/start",
    response_model=MonitoringVisit,
    summary="Start a monitoring visit",
    description="Transition visit from scheduled/confirmed to in_progress status.",
)
async def start_visit(visit_id: str, payload: VisitStartPayload) -> MonitoringVisit:
    svc = get_clinical_monitoring_service()
    try:
        result = svc.start_visit(visit_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Visit '{visit_id}' not found")
    return result


@router.post(
    "/visits/{visit_id}/complete",
    response_model=MonitoringVisit,
    summary="Complete a monitoring visit",
    description="Transition visit from in_progress to completed status.",
)
async def complete_visit(visit_id: str, payload: VisitCompletePayload) -> MonitoringVisit:
    svc = get_clinical_monitoring_service()
    try:
        result = svc.complete_visit(visit_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Visit '{visit_id}' not found")
    return result


@router.post(
    "/visits/{visit_id}/cancel",
    response_model=MonitoringVisit,
    summary="Cancel a monitoring visit",
    description="Cancel a scheduled, confirmed, or in-progress visit.",
)
async def cancel_visit(visit_id: str) -> MonitoringVisit:
    svc = get_clinical_monitoring_service()
    try:
        result = svc.cancel_visit(visit_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Visit '{visit_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


@router.get(
    "/findings",
    response_model=MonitoringFindingListResponse,
    summary="List monitoring findings",
    description="Retrieve findings with optional filtering by visit, trial, site, severity, category, status.",
)
async def list_findings(
    visit_id: Optional[str] = Query(None, description="Filter by visit ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    severity: Optional[FindingSeverity] = Query(None, description="Filter by severity"),
    category: Optional[FindingCategory] = Query(None, description="Filter by category"),
    status: Optional[FindingStatus] = Query(None, description="Filter by status"),
) -> MonitoringFindingListResponse:
    svc = get_clinical_monitoring_service()
    items = svc.list_findings(
        visit_id=visit_id, trial_id=trial_id, site_id=site_id,
        severity=severity, category=category, status=status,
    )
    return MonitoringFindingListResponse(items=items, total=len(items))


@router.get(
    "/findings/{finding_id}",
    response_model=MonitoringFinding,
    summary="Get a monitoring finding",
)
async def get_finding(finding_id: str) -> MonitoringFinding:
    svc = get_clinical_monitoring_service()
    finding = svc.get_finding(finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found")
    return finding


@router.post(
    "/findings",
    response_model=MonitoringFinding,
    status_code=201,
    summary="Create a monitoring finding",
)
async def create_finding(payload: MonitoringFindingCreate) -> MonitoringFinding:
    svc = get_clinical_monitoring_service()
    try:
        return svc.create_finding(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/findings/{finding_id}",
    response_model=MonitoringFinding,
    summary="Update a monitoring finding",
)
async def update_finding(
    finding_id: str, payload: MonitoringFindingUpdate
) -> MonitoringFinding:
    svc = get_clinical_monitoring_service()
    updated = svc.update_finding(finding_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found")
    return updated


@router.post(
    "/findings/{finding_id}/resolve",
    response_model=MonitoringFinding,
    summary="Resolve a monitoring finding",
    description="Mark a finding as resolved with current timestamp.",
)
async def resolve_finding(finding_id: str) -> MonitoringFinding:
    svc = get_clinical_monitoring_service()
    try:
        result = svc.resolve_finding(finding_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found")
    return result


@router.post(
    "/findings/{finding_id}/escalate",
    response_model=MonitoringFinding,
    summary="Escalate a monitoring finding",
    description="Escalate a finding to higher management.",
)
async def escalate_finding(finding_id: str) -> MonitoringFinding:
    svc = get_clinical_monitoring_service()
    try:
        result = svc.escalate_finding(finding_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found")
    return result


# ---------------------------------------------------------------------------
# SDV Records
# ---------------------------------------------------------------------------


@router.get(
    "/sdv/summary",
    response_model=list[SDVSiteSummary],
    summary="Get SDV summary across all sites",
    description="Aggregated SDV verification statistics per site.",
)
async def get_sdv_summary() -> list[SDVSiteSummary]:
    svc = get_clinical_monitoring_service()
    return svc.get_sdv_summary()


@router.get(
    "/sdv/rate/{site_id}",
    response_model=dict,
    summary="Get SDV rate for a site",
    description="Calculate the SDV verification rate for a specific site.",
)
async def get_sdv_rate(site_id: str) -> dict:
    svc = get_clinical_monitoring_service()
    rate = svc.get_sdv_rate_by_site(site_id)
    return {"site_id": site_id, "sdv_rate": rate}


@router.get(
    "/sdv",
    response_model=SDVRecordListResponse,
    summary="List SDV records",
    description="Retrieve SDV records with optional filtering by visit, trial, site, subject, status.",
)
async def list_sdv_records(
    visit_id: Optional[str] = Query(None, description="Filter by visit ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
    status: Optional[SDVStatus] = Query(None, description="Filter by SDV status"),
) -> SDVRecordListResponse:
    svc = get_clinical_monitoring_service()
    items = svc.list_sdv_records(
        visit_id=visit_id, trial_id=trial_id, site_id=site_id,
        subject_id=subject_id, status=status,
    )
    return SDVRecordListResponse(items=items, total=len(items))


@router.get(
    "/sdv/{sdv_id}",
    response_model=SDVRecord,
    summary="Get an SDV record",
)
async def get_sdv_record(sdv_id: str) -> SDVRecord:
    svc = get_clinical_monitoring_service()
    rec = svc.get_sdv_record(sdv_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"SDV record '{sdv_id}' not found")
    return rec


@router.post(
    "/sdv",
    response_model=SDVRecord,
    status_code=201,
    summary="Record a source data verification",
    description="Create a new SDV record for a monitoring visit.",
)
async def record_sdv(payload: SDVRecordCreate) -> SDVRecord:
    svc = get_clinical_monitoring_service()
    try:
        return svc.record_sdv(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Monitoring Reports
# ---------------------------------------------------------------------------


@router.get(
    "/reports",
    response_model=MonitoringReportListResponse,
    summary="List monitoring reports",
    description="Retrieve reports with optional filtering by visit, trial, site, status.",
)
async def list_reports(
    visit_id: Optional[str] = Query(None, description="Filter by visit ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[ReportStatus] = Query(None, description="Filter by report status"),
) -> MonitoringReportListResponse:
    svc = get_clinical_monitoring_service()
    items = svc.list_reports(
        visit_id=visit_id, trial_id=trial_id, site_id=site_id, status=status,
    )
    return MonitoringReportListResponse(items=items, total=len(items))


@router.get(
    "/reports/{report_id}",
    response_model=MonitoringReport,
    summary="Get a monitoring report",
)
async def get_report(report_id: str) -> MonitoringReport:
    svc = get_clinical_monitoring_service()
    report = svc.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return report


@router.post(
    "/reports",
    response_model=MonitoringReport,
    status_code=201,
    summary="Create a monitoring report",
    description="Create a monitoring report for a visit. Automatically computes findings counts and SDV rate.",
)
async def create_report(payload: MonitoringReportCreate) -> MonitoringReport:
    svc = get_clinical_monitoring_service()
    try:
        return svc.create_report(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/reports/{report_id}",
    response_model=MonitoringReport,
    summary="Update a monitoring report",
)
async def update_report(
    report_id: str, payload: MonitoringReportUpdate
) -> MonitoringReport:
    svc = get_clinical_monitoring_service()
    updated = svc.update_report(report_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return updated


@router.post(
    "/reports/{report_id}/submit",
    response_model=MonitoringReport,
    summary="Submit a monitoring report",
    description="Submit a draft monitoring report for review.",
)
async def submit_report(report_id: str, payload: ReportSubmitPayload) -> MonitoringReport:
    svc = get_clinical_monitoring_service()
    try:
        result = svc.submit_report(report_id, payload.submitted_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return result


@router.post(
    "/reports/{report_id}/approve",
    response_model=MonitoringReport,
    summary="Approve a monitoring report",
    description="Approve a submitted or reviewed monitoring report.",
)
async def approve_report(report_id: str) -> MonitoringReport:
    svc = get_clinical_monitoring_service()
    try:
        result = svc.approve_report(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return result


# ---------------------------------------------------------------------------
# CAPA Items
# ---------------------------------------------------------------------------


@router.get(
    "/capas",
    response_model=CAPAItemListResponse,
    summary="List CAPA items",
    description="Retrieve CAPA items with optional filtering by trial, site, status, finding.",
)
async def list_capas(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[CAPAStatus] = Query(None, description="Filter by CAPA status"),
    finding_id: Optional[str] = Query(None, description="Filter by finding ID"),
) -> CAPAItemListResponse:
    svc = get_clinical_monitoring_service()
    items = svc.list_capas(
        trial_id=trial_id, site_id=site_id, status=status, finding_id=finding_id,
    )
    return CAPAItemListResponse(items=items, total=len(items))


@router.get(
    "/capas/{capa_id}",
    response_model=CAPAItem,
    summary="Get a CAPA item",
)
async def get_capa(capa_id: str) -> CAPAItem:
    svc = get_clinical_monitoring_service()
    capa = svc.get_capa(capa_id)
    if capa is None:
        raise HTTPException(status_code=404, detail=f"CAPA '{capa_id}' not found")
    return capa


@router.post(
    "/capas",
    response_model=CAPAItem,
    status_code=201,
    summary="Create a CAPA item",
    description="Create a CAPA item linked to a monitoring finding.",
)
async def create_capa(payload: CAPAItemCreate) -> CAPAItem:
    svc = get_clinical_monitoring_service()
    try:
        return svc.create_capa(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/capas/{capa_id}",
    response_model=CAPAItem,
    summary="Update a CAPA item",
)
async def update_capa(capa_id: str, payload: CAPAItemUpdate) -> CAPAItem:
    svc = get_clinical_monitoring_service()
    updated = svc.update_capa(capa_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"CAPA '{capa_id}' not found")
    return updated


@router.post(
    "/capas/{capa_id}/close",
    response_model=CAPAItem,
    summary="Close a CAPA item",
    description="Close a CAPA with effectiveness verification.",
)
async def close_capa(capa_id: str, effectiveness_check: str = Query(..., description="Effectiveness check notes")) -> CAPAItem:
    svc = get_clinical_monitoring_service()
    try:
        result = svc.close_capa(capa_id, effectiveness_check)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"CAPA '{capa_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Metrics & Summaries
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=MonitoringMetrics,
    summary="Get monitoring metrics",
    description="Aggregated clinical monitoring metrics across all trials and sites.",
)
async def get_metrics() -> MonitoringMetrics:
    svc = get_clinical_monitoring_service()
    return svc.get_monitoring_metrics()


@router.get(
    "/site-summary/{site_id}",
    response_model=SiteMonitoringSummary,
    summary="Get site monitoring summary",
    description="Monitoring summary for a specific site, optionally filtered by trial.",
)
async def get_site_summary(
    site_id: str,
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> SiteMonitoringSummary:
    svc = get_clinical_monitoring_service()
    summary = svc.get_site_monitoring_summary(site_id, trial_id=trial_id)
    if summary is None:
        raise HTTPException(
            status_code=404,
            detail=f"No monitoring data found for site '{site_id}'",
        )
    return summary
