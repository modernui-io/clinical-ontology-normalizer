"""Pharmacovigilance Signal Management API endpoints (CLINICAL-4).

Provides comprehensive pharmacovigilance lifecycle management including
ICSR intake and management, signal detection via disproportionality analysis,
MedDRA coding/hierarchy, periodic safety report generation, regulatory action
tracking, and aggregated dashboard metrics.

Endpoints:
    GET  /pharmacovigilance/icsrs                              - List ICSRs
    GET  /pharmacovigilance/icsrs/search                       - Search ICSRs
    GET  /pharmacovigilance/icsrs/{icsr_id}                    - Get single ICSR
    POST /pharmacovigilance/icsrs                              - Create ICSR
    PUT  /pharmacovigilance/icsrs/{icsr_id}                    - Update ICSR
    DELETE /pharmacovigilance/icsrs/{icsr_id}                  - Delete ICSR
    POST /pharmacovigilance/signals/detect                     - Run signal detection
    GET  /pharmacovigilance/signals                            - List signals
    GET  /pharmacovigilance/signals/{signal_id}                - Get single signal
    POST /pharmacovigilance/signals                            - Create signal
    PUT  /pharmacovigilance/signals/{signal_id}                - Update signal
    DELETE /pharmacovigilance/signals/{signal_id}              - Delete signal
    GET  /pharmacovigilance/meddra/search                      - Search MedDRA terms
    GET  /pharmacovigilance/meddra/{code}                      - Get MedDRA term
    GET  /pharmacovigilance/meddra/{code}/hierarchy            - Get MedDRA hierarchy
    POST /pharmacovigilance/meddra/code                        - Map text to MedDRA
    GET  /pharmacovigilance/periodic-reports                   - List periodic reports
    GET  /pharmacovigilance/periodic-reports/{report_id}       - Get single report
    POST /pharmacovigilance/periodic-reports/generate          - Generate report
    GET  /pharmacovigilance/regulatory-actions                 - List regulatory actions
    GET  /pharmacovigilance/regulatory-actions/{action_id}     - Get single action
    POST /pharmacovigilance/regulatory-actions                 - Create action
    PUT  /pharmacovigilance/regulatory-actions/{action_id}/status - Update action status
    GET  /pharmacovigilance/case-series                        - Case series analysis
    GET  /pharmacovigilance/metrics                            - Dashboard metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.schemas.pharmacovigilance import (
    ICSR,
    CaseSeriesResult,
    CausalityCategory,
    DisproportionalityAnalysisResponse,
    DisproportionalityMethod,
    GenerateReportRequest,
    ICSRCreate,
    ICSRListResponse,
    ICSRStatus,
    ICSRUpdate,
    MedDRAHierarchyResponse,
    MedDRALevel,
    MedDRASearchResponse,
    MedDRATerm,
    PeriodicSafetyReport,
    PeriodicSafetyReportListResponse,
    PharmacovigilanceMetrics,
    RegulatoryAction,
    RegulatoryActionCreate,
    RegulatoryActionListResponse,
    RegulatoryActionStatus,
    RegulatoryActionType,
    ReportType,
    SignalClassification,
    SignalCreate,
    SignalDetectionRequest,
    SignalListResponse,
    SignalRecord,
    SignalSource,
    SignalUpdate,
)
from app.services.pharmacovigilance_service import get_pharmacovigilance_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/pharmacovigilance",
    tags=["Pharmacovigilance"],
)


# ---------------------------------------------------------------------------
# Helper request models
# ---------------------------------------------------------------------------


class MedDRACodeRequest(BaseModel):
    """Request body for MedDRA coding."""
    event_term: str = Field(..., description="Free-text event term to map")


class StatusUpdateRequest(BaseModel):
    """Request body for updating regulatory action status."""
    status: RegulatoryActionStatus = Field(..., description="New status")


# ---------------------------------------------------------------------------
# ICSR endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/icsrs",
    response_model=ICSRListResponse,
    summary="List ICSRs",
    description="Retrieve Individual Case Safety Reports with optional filtering.",
)
async def list_icsrs(
    drug_name: Optional[str] = Query(None, description="Filter by drug name"),
    status: Optional[ICSRStatus] = Query(None, description="Filter by status"),
    source: Optional[SignalSource] = Query(None, description="Filter by source"),
    country: Optional[str] = Query(None, description="Filter by country"),
    causality: Optional[CausalityCategory] = Query(None, description="Filter by causality"),
    serious: Optional[bool] = Query(None, description="Filter by seriousness"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> ICSRListResponse:
    """List ICSRs with filters and pagination."""
    svc = get_pharmacovigilance_service()
    return svc.list_icsrs(
        drug_name=drug_name,
        status=status,
        source=source,
        country=country,
        causality=causality,
        serious=serious,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/icsrs/search",
    response_model=ICSRListResponse,
    summary="Search ICSRs",
    description="Full-text search across ICSR fields.",
)
async def search_icsrs(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> ICSRListResponse:
    """Search ICSRs by text query."""
    svc = get_pharmacovigilance_service()
    return svc.search_icsrs(query=q, limit=limit, offset=offset)


@router.get(
    "/icsrs/{icsr_id}",
    response_model=ICSR,
    summary="Get ICSR",
    description="Retrieve a single ICSR by ID.",
)
async def get_icsr(icsr_id: str) -> ICSR:
    """Get a single ICSR by ID."""
    svc = get_pharmacovigilance_service()
    icsr = svc.get_icsr(icsr_id)
    if not icsr:
        raise HTTPException(status_code=404, detail=f"ICSR {icsr_id} not found")
    return icsr


@router.post(
    "/icsrs",
    response_model=ICSR,
    status_code=201,
    summary="Create ICSR",
    description="Create a new Individual Case Safety Report.",
)
async def create_icsr(payload: ICSRCreate) -> ICSR:
    """Create a new ICSR."""
    svc = get_pharmacovigilance_service()
    return svc.create_icsr(payload)


@router.put(
    "/icsrs/{icsr_id}",
    response_model=ICSR,
    summary="Update ICSR",
    description="Update an existing ICSR.",
)
async def update_icsr(icsr_id: str, payload: ICSRUpdate) -> ICSR:
    """Update an existing ICSR."""
    svc = get_pharmacovigilance_service()
    try:
        result = svc.update_icsr(icsr_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail=f"ICSR {icsr_id} not found")
    return result


@router.delete(
    "/icsrs/{icsr_id}",
    status_code=204,
    summary="Delete ICSR",
    description="Delete (nullify) an ICSR.",
)
async def delete_icsr(icsr_id: str) -> None:
    """Delete an ICSR."""
    svc = get_pharmacovigilance_service()
    if not svc.delete_icsr(icsr_id):
        raise HTTPException(status_code=404, detail=f"ICSR {icsr_id} not found")


# ---------------------------------------------------------------------------
# Signal detection & management endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/signals/detect",
    response_model=DisproportionalityAnalysisResponse,
    summary="Detect safety signal",
    description="Run disproportionality analysis for a drug-event pair using PRR, ROR, BCPNN, and/or EBGM.",
)
async def detect_signal(request: SignalDetectionRequest) -> DisproportionalityAnalysisResponse:
    """Run signal detection via disproportionality analysis."""
    svc = get_pharmacovigilance_service()
    return svc.detect_signal(request)


@router.get(
    "/signals",
    response_model=SignalListResponse,
    summary="List signals",
    description="Retrieve pharmacovigilance signals with optional filtering.",
)
async def list_signals(
    drug_name: Optional[str] = Query(None, description="Filter by drug"),
    classification: Optional[SignalClassification] = Query(None, description="Filter by classification"),
    source: Optional[SignalSource] = Query(None, description="Filter by source"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> SignalListResponse:
    """List signals with filters and pagination."""
    svc = get_pharmacovigilance_service()
    return svc.list_signals(
        drug_name=drug_name,
        classification=classification,
        source=source,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/signals/{signal_id}",
    response_model=SignalRecord,
    summary="Get signal",
    description="Retrieve a single signal by ID.",
)
async def get_signal(signal_id: str) -> SignalRecord:
    """Get a single signal by ID."""
    svc = get_pharmacovigilance_service()
    signal = svc.get_signal(signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")
    return signal


@router.post(
    "/signals",
    response_model=SignalRecord,
    status_code=201,
    summary="Create signal",
    description="Create a new pharmacovigilance signal record.",
)
async def create_signal(payload: SignalCreate) -> SignalRecord:
    """Create a new signal record."""
    svc = get_pharmacovigilance_service()
    return svc.create_signal(payload)


@router.put(
    "/signals/{signal_id}",
    response_model=SignalRecord,
    summary="Update signal",
    description="Update an existing signal record (classification, assessment, etc.).",
)
async def update_signal(signal_id: str, payload: SignalUpdate) -> SignalRecord:
    """Update an existing signal."""
    svc = get_pharmacovigilance_service()
    try:
        result = svc.update_signal(signal_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")
    return result


@router.delete(
    "/signals/{signal_id}",
    status_code=204,
    summary="Delete signal",
    description="Delete a signal record.",
)
async def delete_signal(signal_id: str) -> None:
    """Delete a signal record."""
    svc = get_pharmacovigilance_service()
    if not svc.delete_signal(signal_id):
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")


# ---------------------------------------------------------------------------
# MedDRA coding endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/meddra/search",
    response_model=MedDRASearchResponse,
    summary="Search MedDRA terms",
    description="Search MedDRA terminology by text query with optional level filter.",
)
async def search_meddra(
    q: str = Query(..., min_length=1, description="Search query"),
    level: Optional[MedDRALevel] = Query(None, description="Filter by hierarchy level"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
) -> MedDRASearchResponse:
    """Search MedDRA terms."""
    svc = get_pharmacovigilance_service()
    return svc.search_meddra(query=q, level=level, limit=limit)


@router.get(
    "/meddra/{code}",
    response_model=MedDRATerm,
    summary="Get MedDRA term",
    description="Retrieve a MedDRA term by code.",
)
async def get_meddra_term(code: str) -> MedDRATerm:
    """Get a MedDRA term by code."""
    svc = get_pharmacovigilance_service()
    term = svc.get_meddra_term(code)
    if not term:
        raise HTTPException(status_code=404, detail=f"MedDRA term {code} not found")
    return term


@router.get(
    "/meddra/{code}/hierarchy",
    response_model=MedDRAHierarchyResponse,
    summary="Get MedDRA hierarchy",
    description="Get ancestors and children for a MedDRA term.",
)
async def get_meddra_hierarchy(code: str) -> MedDRAHierarchyResponse:
    """Get MedDRA hierarchy for a term."""
    svc = get_pharmacovigilance_service()
    result = svc.get_meddra_hierarchy(code)
    if not result:
        raise HTTPException(status_code=404, detail=f"MedDRA term {code} not found")
    return result


@router.post(
    "/meddra/code",
    response_model=MedDRATerm,
    summary="Map text to MedDRA",
    description="Map a free-text event term to a MedDRA Preferred Term.",
)
async def code_to_meddra(request: MedDRACodeRequest) -> MedDRATerm:
    """Map free-text event term to MedDRA PT."""
    svc = get_pharmacovigilance_service()
    term = svc.code_to_meddra(request.event_term)
    if not term:
        raise HTTPException(status_code=404, detail=f"No MedDRA match for '{request.event_term}'")
    return term


# ---------------------------------------------------------------------------
# Periodic Safety Report endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/periodic-reports",
    response_model=PeriodicSafetyReportListResponse,
    summary="List periodic safety reports",
    description="Retrieve periodic safety reports with optional filtering.",
)
async def list_periodic_reports(
    drug_name: Optional[str] = Query(None, description="Filter by drug"),
    report_type: Optional[ReportType] = Query(None, description="Filter by report type"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> PeriodicSafetyReportListResponse:
    """List periodic safety reports."""
    svc = get_pharmacovigilance_service()
    return svc.list_periodic_reports(
        drug_name=drug_name,
        report_type=report_type,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/periodic-reports/{report_id}",
    response_model=PeriodicSafetyReport,
    summary="Get periodic safety report",
    description="Retrieve a single periodic safety report.",
)
async def get_periodic_report(report_id: str) -> PeriodicSafetyReport:
    """Get a single periodic safety report."""
    svc = get_pharmacovigilance_service()
    report = svc.get_periodic_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return report


@router.post(
    "/periodic-reports/generate",
    response_model=PeriodicSafetyReport,
    status_code=201,
    summary="Generate periodic safety report",
    description="Generate a PSUR/PBRER/DSUR for a drug over a specified period.",
)
async def generate_periodic_report(request: GenerateReportRequest) -> PeriodicSafetyReport:
    """Generate a periodic safety report."""
    svc = get_pharmacovigilance_service()
    return svc.generate_periodic_report(
        drug_name=request.drug_name,
        report_type=request.report_type,
        period_start=request.period_start,
        period_end=request.period_end,
    )


# ---------------------------------------------------------------------------
# Regulatory Action endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/regulatory-actions",
    response_model=RegulatoryActionListResponse,
    summary="List regulatory actions",
    description="Retrieve regulatory actions with optional filtering.",
)
async def list_regulatory_actions(
    signal_id: Optional[str] = Query(None, description="Filter by signal ID"),
    action_type: Optional[RegulatoryActionType] = Query(None, description="Filter by action type"),
    agency: Optional[str] = Query(None, description="Filter by agency"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> RegulatoryActionListResponse:
    """List regulatory actions."""
    svc = get_pharmacovigilance_service()
    return svc.list_regulatory_actions(
        signal_id=signal_id,
        action_type=action_type,
        agency=agency,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/regulatory-actions/{action_id}",
    response_model=RegulatoryAction,
    summary="Get regulatory action",
    description="Retrieve a single regulatory action.",
)
async def get_regulatory_action(action_id: str) -> RegulatoryAction:
    """Get a single regulatory action."""
    svc = get_pharmacovigilance_service()
    action = svc.get_regulatory_action(action_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"Action {action_id} not found")
    return action


@router.post(
    "/regulatory-actions",
    response_model=RegulatoryAction,
    status_code=201,
    summary="Create regulatory action",
    description="Create a new regulatory action for a signal.",
)
async def create_regulatory_action(payload: RegulatoryActionCreate) -> RegulatoryAction:
    """Create a new regulatory action."""
    svc = get_pharmacovigilance_service()
    try:
        return svc.create_regulatory_action(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/regulatory-actions/{action_id}/status",
    response_model=RegulatoryAction,
    summary="Update regulatory action status",
    description="Update the status of a regulatory action.",
)
async def update_regulatory_action_status(
    action_id: str,
    request: StatusUpdateRequest,
) -> RegulatoryAction:
    """Update regulatory action status."""
    svc = get_pharmacovigilance_service()
    result = svc.update_regulatory_action_status(action_id, request.status)
    if not result:
        raise HTTPException(status_code=404, detail=f"Action {action_id} not found")
    return result


# ---------------------------------------------------------------------------
# Case Series Analysis
# ---------------------------------------------------------------------------


@router.get(
    "/case-series",
    response_model=CaseSeriesResult,
    summary="Case series analysis",
    description="Perform case series analysis for a drug-event pair, including demographic breakdown.",
)
async def case_series_analysis(
    drug_name: str = Query(..., description="Drug name"),
    event_term: str = Query(..., description="Event term"),
) -> CaseSeriesResult:
    """Run case series analysis."""
    svc = get_pharmacovigilance_service()
    return svc.case_series_analysis(drug_name, event_term)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=PharmacovigilanceMetrics,
    summary="Pharmacovigilance metrics",
    description="Get aggregated pharmacovigilance dashboard metrics.",
)
async def get_metrics() -> PharmacovigilanceMetrics:
    """Get pharmacovigilance dashboard metrics."""
    svc = get_pharmacovigilance_service()
    return svc.get_metrics()
