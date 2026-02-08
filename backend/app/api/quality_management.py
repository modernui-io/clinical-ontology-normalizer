"""Quality Management API endpoints (VP-Quality-2).

Provides endpoints for CAPA (Corrective and Preventive Action) tracking
and IQ/OQ/PQ qualification test execution.

Endpoints:
    GET    /api/v1/quality-management/capa              - List CAPAs
    GET    /api/v1/quality-management/capa/metrics       - CAPA dashboard metrics
    GET    /api/v1/quality-management/capa/{id}          - Get CAPA detail
    POST   /api/v1/quality-management/capa               - Create new CAPA
    PUT    /api/v1/quality-management/capa/{id}          - Update CAPA
    POST   /api/v1/quality-management/qualification/run  - Execute qualification suite
    GET    /api/v1/quality-management/qualification/reports     - List qualification reports
    GET    /api/v1/quality-management/qualification/reports/{id} - Get report detail
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.quality_management import (
    CAPACreate,
    CAPAListResponse,
    CAPAMetrics,
    CAPAResponse,
    CAPASeverity,
    CAPASource,
    CAPAStatus,
    CAPAType,
    CAPAUpdate,
    QualificationReport,
    QualificationReportListResponse,
    QualificationRunRequest,
)
from app.services.capa_service import get_capa_service
from app.services.qualification_runner_service import get_qualification_runner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quality-management", tags=["Quality Management"])


# ============================================================================
# Helper functions
# ============================================================================


def _capa_to_response(capa) -> CAPAResponse:
    """Convert a CAPARecord to a CAPAResponse."""
    return CAPAResponse(
        id=capa.id,
        title=capa.title,
        description=capa.description,
        capa_type=capa.capa_type,
        source=capa.source,
        severity=capa.severity,
        status=capa.status,
        root_cause_category=capa.root_cause_category,
        root_cause=capa.root_cause,
        corrective_action=capa.corrective_action,
        preventive_action=capa.preventive_action,
        assigned_to=capa.assigned_to,
        due_date=capa.due_date,
        created_at=capa.created_at,
        updated_at=capa.updated_at,
        closed_at=capa.closed_at,
        effectiveness_check_date=capa.effectiveness_check_date,
        recurrence_count=capa.recurrence_count,
    )


# ============================================================================
# CAPA Endpoints
# ============================================================================


@router.get(
    "/capa/metrics",
    response_model=CAPAMetrics,
    summary="Get CAPA metrics",
    description="Get aggregated CAPA metrics including counts by severity, status, and overdue tracking.",
)
async def get_capa_metrics() -> CAPAMetrics:
    """Get CAPA dashboard metrics."""
    service = get_capa_service()
    return service.get_metrics()


@router.get(
    "/capa",
    response_model=CAPAListResponse,
    summary="List CAPAs",
    description="List CAPAs with optional filtering by status, severity, type, and source.",
)
async def list_capas(
    capa_status: CAPAStatus | None = Query(default=None, alias="status", description="Filter by status"),
    severity: CAPASeverity | None = Query(default=None, description="Filter by severity"),
    capa_type: CAPAType | None = Query(default=None, alias="type", description="Filter by CAPA type"),
    source: CAPASource | None = Query(default=None, description="Filter by source"),
    limit: int = Query(default=100, ge=1, le=1000, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> CAPAListResponse:
    """List CAPAs with optional filters."""
    service = get_capa_service()
    capas, total = service.list_capas(
        status=capa_status,
        severity=severity,
        capa_type=capa_type,
        source=source,
        limit=limit,
        offset=offset,
    )
    return CAPAListResponse(
        capas=[_capa_to_response(c) for c in capas],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/capa/{capa_id}",
    response_model=CAPAResponse,
    summary="Get CAPA detail",
    description="Get full details of a specific CAPA record.",
)
async def get_capa(capa_id: str) -> CAPAResponse:
    """Get a specific CAPA by ID."""
    service = get_capa_service()
    capa = service.get_capa(capa_id)
    if capa is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CAPA not found: {capa_id}",
        )
    return _capa_to_response(capa)


@router.post(
    "/capa",
    response_model=CAPAResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a CAPA",
    description="Create a new Corrective and Preventive Action record.",
)
async def create_capa(request: CAPACreate) -> CAPAResponse:
    """Create a new CAPA."""
    service = get_capa_service()
    capa = service.create_capa(
        title=request.title,
        description=request.description,
        capa_type=request.capa_type,
        source=request.source,
        severity=request.severity,
        root_cause_category=request.root_cause_category,
        root_cause=request.root_cause,
        corrective_action=request.corrective_action,
        preventive_action=request.preventive_action,
        assigned_to=request.assigned_to,
        due_date=request.due_date,
    )
    logger.info("CAPA created via API: %s", capa.id)
    return _capa_to_response(capa)


@router.put(
    "/capa/{capa_id}",
    response_model=CAPAResponse,
    summary="Update a CAPA",
    description="Update CAPA fields including status transitions.",
)
async def update_capa(capa_id: str, request: CAPAUpdate) -> CAPAResponse:
    """Update an existing CAPA."""
    service = get_capa_service()
    try:
        capa = service.update_capa(
            capa_id=capa_id,
            title=request.title,
            description=request.description,
            status=request.status,
            severity=request.severity,
            root_cause_category=request.root_cause_category,
            root_cause=request.root_cause,
            corrective_action=request.corrective_action,
            preventive_action=request.preventive_action,
            assigned_to=request.assigned_to,
            due_date=request.due_date,
            effectiveness_check_date=request.effectiveness_check_date,
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    return _capa_to_response(capa)


# ============================================================================
# Qualification Endpoints
# ============================================================================


@router.post(
    "/qualification/run",
    response_model=QualificationReport,
    status_code=status.HTTP_201_CREATED,
    summary="Run qualification suite",
    description="Execute IQ, OQ, or PQ qualification checks and return a report.",
)
async def run_qualification(request: QualificationRunRequest) -> QualificationReport:
    """Execute a qualification test suite."""
    runner = get_qualification_runner()
    report = runner.run_qualification(
        qualification_type=request.qualification_type,
        executed_by=request.executed_by,
    )
    logger.info(
        "Qualification run completed via API: type=%s, result=%s",
        request.qualification_type.value,
        report.summary.overall_result,
    )
    return report


@router.get(
    "/qualification/reports",
    response_model=QualificationReportListResponse,
    summary="List qualification reports",
    description="List all qualification reports from previous runs.",
)
async def list_qualification_reports() -> QualificationReportListResponse:
    """List all qualification reports."""
    runner = get_qualification_runner()
    reports = runner.list_reports()
    return QualificationReportListResponse(
        reports=reports,
        total=len(reports),
    )


@router.get(
    "/qualification/reports/{report_id}",
    response_model=QualificationReport,
    summary="Get qualification report",
    description="Get full details of a specific qualification report.",
)
async def get_qualification_report(report_id: str) -> QualificationReport:
    """Get a specific qualification report by ID."""
    runner = get_qualification_runner()
    report = runner.get_report(report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Qualification report not found: {report_id}",
        )
    return report
