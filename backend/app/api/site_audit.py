"""Site Audit Management API endpoints (QA-AUDIT).

Provides comprehensive site audit operations: audit planning, execution,
findings classification, CAPA tracking, audit report lifecycle, and metrics.

Endpoints:
    GET    /site-audit/audits                   - List audits
    GET    /site-audit/audits/{audit_id}        - Get single audit
    POST   /site-audit/audits                   - Create audit
    PUT    /site-audit/audits/{audit_id}        - Update audit
    DELETE /site-audit/audits/{audit_id}        - Delete audit
    GET    /site-audit/findings                 - List findings
    GET    /site-audit/findings/{finding_id}    - Get single finding
    POST   /site-audit/findings                 - Create finding
    PUT    /site-audit/findings/{finding_id}    - Update finding
    DELETE /site-audit/findings/{finding_id}    - Delete finding
    GET    /site-audit/capas                    - List CAPAs
    GET    /site-audit/capas/{capa_id}          - Get single CAPA
    POST   /site-audit/capas                    - Create CAPA
    PUT    /site-audit/capas/{capa_id}          - Update CAPA
    DELETE /site-audit/capas/{capa_id}          - Delete CAPA
    GET    /site-audit/reports                  - List reports
    GET    /site-audit/reports/{report_id}      - Get single report
    POST   /site-audit/reports                  - Create report
    PUT    /site-audit/reports/{report_id}      - Update report
    DELETE /site-audit/reports/{report_id}      - Delete report
    GET    /site-audit/metrics                  - Audit metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.site_audit import (
    AuditCAPA,
    AuditCAPACreate,
    AuditCAPAListResponse,
    AuditCAPAUpdate,
    AuditFinding,
    AuditFindingCreate,
    AuditFindingListResponse,
    AuditFindingUpdate,
    AuditReport,
    AuditReportCreate,
    AuditReportListResponse,
    AuditReportUpdate,
    AuditStatus,
    AuditType,
    CAPAStatus,
    FindingClassification,
    FindingStatus,
    ReportStatus,
    SiteAudit,
    SiteAuditCreate,
    SiteAuditListResponse,
    SiteAuditMetrics,
    SiteAuditUpdate,
)
from app.services.site_audit_service import get_site_audit_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/site-audit",
    tags=["Site Audit"],
)


# ---------------------------------------------------------------------------
# Audit CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/audits",
    response_model=SiteAuditListResponse,
    summary="List site audits",
    description="Retrieve site audits with optional filtering by trial, status, and type.",
)
async def list_audits(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[AuditStatus] = Query(None, description="Filter by status"),
    audit_type: Optional[AuditType] = Query(None, description="Filter by audit type"),
) -> SiteAuditListResponse:
    svc = get_site_audit_service()
    items = svc.list_audits(trial_id=trial_id, status=status, audit_type=audit_type)
    return SiteAuditListResponse(items=items, total=len(items))


@router.get(
    "/audits/{audit_id}",
    response_model=SiteAudit,
    summary="Get a site audit",
)
async def get_audit(audit_id: str) -> SiteAudit:
    svc = get_site_audit_service()
    audit = svc.get_audit(audit_id)
    if audit is None:
        raise HTTPException(status_code=404, detail=f"Audit '{audit_id}' not found")
    return audit


@router.post(
    "/audits",
    response_model=SiteAudit,
    status_code=201,
    summary="Create a site audit",
)
async def create_audit(payload: SiteAuditCreate) -> SiteAudit:
    svc = get_site_audit_service()
    return svc.create_audit(payload)


@router.put(
    "/audits/{audit_id}",
    response_model=SiteAudit,
    summary="Update a site audit",
)
async def update_audit(audit_id: str, payload: SiteAuditUpdate) -> SiteAudit:
    svc = get_site_audit_service()
    updated = svc.update_audit(audit_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Audit '{audit_id}' not found")
    return updated


@router.delete(
    "/audits/{audit_id}",
    status_code=204,
    summary="Delete a site audit",
)
async def delete_audit(audit_id: str) -> None:
    svc = get_site_audit_service()
    deleted = svc.delete_audit(audit_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Audit '{audit_id}' not found")


# ---------------------------------------------------------------------------
# Finding CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/findings",
    response_model=AuditFindingListResponse,
    summary="List audit findings",
    description="Retrieve audit findings with optional filtering by audit, classification, and status.",
)
async def list_findings(
    audit_id: Optional[str] = Query(None, description="Filter by audit ID"),
    classification: Optional[FindingClassification] = Query(None, description="Filter by classification"),
    status: Optional[FindingStatus] = Query(None, description="Filter by status"),
) -> AuditFindingListResponse:
    svc = get_site_audit_service()
    items = svc.list_findings(audit_id=audit_id, classification=classification, status=status)
    return AuditFindingListResponse(items=items, total=len(items))


@router.get(
    "/findings/{finding_id}",
    response_model=AuditFinding,
    summary="Get an audit finding",
)
async def get_finding(finding_id: str) -> AuditFinding:
    svc = get_site_audit_service()
    finding = svc.get_finding(finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found")
    return finding


@router.post(
    "/findings",
    response_model=AuditFinding,
    status_code=201,
    summary="Create an audit finding",
)
async def create_finding(payload: AuditFindingCreate) -> AuditFinding:
    svc = get_site_audit_service()
    return svc.create_finding(payload)


@router.put(
    "/findings/{finding_id}",
    response_model=AuditFinding,
    summary="Update an audit finding",
)
async def update_finding(finding_id: str, payload: AuditFindingUpdate) -> AuditFinding:
    svc = get_site_audit_service()
    updated = svc.update_finding(finding_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found")
    return updated


@router.delete(
    "/findings/{finding_id}",
    status_code=204,
    summary="Delete an audit finding",
)
async def delete_finding(finding_id: str) -> None:
    svc = get_site_audit_service()
    deleted = svc.delete_finding(finding_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found")


# ---------------------------------------------------------------------------
# CAPA CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/capas",
    response_model=AuditCAPAListResponse,
    summary="List CAPAs",
    description="Retrieve corrective/preventive actions with optional filtering by audit, finding, and status.",
)
async def list_capas(
    audit_id: Optional[str] = Query(None, description="Filter by audit ID"),
    finding_id: Optional[str] = Query(None, description="Filter by finding ID"),
    status: Optional[CAPAStatus] = Query(None, description="Filter by status"),
) -> AuditCAPAListResponse:
    svc = get_site_audit_service()
    items = svc.list_capas(audit_id=audit_id, finding_id=finding_id, status=status)
    return AuditCAPAListResponse(items=items, total=len(items))


@router.get(
    "/capas/{capa_id}",
    response_model=AuditCAPA,
    summary="Get a CAPA",
)
async def get_capa(capa_id: str) -> AuditCAPA:
    svc = get_site_audit_service()
    capa = svc.get_capa(capa_id)
    if capa is None:
        raise HTTPException(status_code=404, detail=f"CAPA '{capa_id}' not found")
    return capa


@router.post(
    "/capas",
    response_model=AuditCAPA,
    status_code=201,
    summary="Create a CAPA",
)
async def create_capa(payload: AuditCAPACreate) -> AuditCAPA:
    svc = get_site_audit_service()
    return svc.create_capa(payload)


@router.put(
    "/capas/{capa_id}",
    response_model=AuditCAPA,
    summary="Update a CAPA",
)
async def update_capa(capa_id: str, payload: AuditCAPAUpdate) -> AuditCAPA:
    svc = get_site_audit_service()
    updated = svc.update_capa(capa_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"CAPA '{capa_id}' not found")
    return updated


@router.delete(
    "/capas/{capa_id}",
    status_code=204,
    summary="Delete a CAPA",
)
async def delete_capa(capa_id: str) -> None:
    svc = get_site_audit_service()
    deleted = svc.delete_capa(capa_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"CAPA '{capa_id}' not found")


# ---------------------------------------------------------------------------
# Report CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/reports",
    response_model=AuditReportListResponse,
    summary="List audit reports",
    description="Retrieve audit reports with optional filtering by audit and status.",
)
async def list_reports(
    audit_id: Optional[str] = Query(None, description="Filter by audit ID"),
    status: Optional[ReportStatus] = Query(None, description="Filter by status"),
) -> AuditReportListResponse:
    svc = get_site_audit_service()
    items = svc.list_reports(audit_id=audit_id, status=status)
    return AuditReportListResponse(items=items, total=len(items))


@router.get(
    "/reports/{report_id}",
    response_model=AuditReport,
    summary="Get an audit report",
)
async def get_report(report_id: str) -> AuditReport:
    svc = get_site_audit_service()
    report = svc.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return report


@router.post(
    "/reports",
    response_model=AuditReport,
    status_code=201,
    summary="Create an audit report",
)
async def create_report(payload: AuditReportCreate) -> AuditReport:
    svc = get_site_audit_service()
    return svc.create_report(payload)


@router.put(
    "/reports/{report_id}",
    response_model=AuditReport,
    summary="Update an audit report",
)
async def update_report(report_id: str, payload: AuditReportUpdate) -> AuditReport:
    svc = get_site_audit_service()
    updated = svc.update_report(report_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return updated


@router.delete(
    "/reports/{report_id}",
    status_code=204,
    summary="Delete an audit report",
)
async def delete_report(report_id: str) -> None:
    svc = get_site_audit_service()
    deleted = svc.delete_report(report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=SiteAuditMetrics,
    summary="Get site audit metrics",
    description="Aggregated site audit metrics including audits by type/status, "
                "findings by classification, CAPA tracking, and report status.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> SiteAuditMetrics:
    svc = get_site_audit_service()
    return svc.get_metrics(trial_id=trial_id)
