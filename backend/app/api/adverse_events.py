"""Adverse Event Monitoring & Safety Reporting API endpoints (CMO-9).

Provides CRUD operations for adverse events, safety signal detection and
management, expedited regulatory reporting, causality assessment (Naranjo),
narrative generation, and aggregated safety metrics.

Endpoints:
    GET  /adverse-events/events                              - List with filters
    GET  /adverse-events/events/metrics                      - Aggregated metrics
    GET  /adverse-events/events/{ae_id}                      - Get single AE
    POST /adverse-events/events                              - Report new AE
    PUT  /adverse-events/events/{ae_id}                      - Update AE
    GET  /adverse-events/events/{ae_id}/causality            - Causality assessment
    GET  /adverse-events/events/{ae_id}/narrative            - Narrative generation
    GET  /adverse-events/events/by-category/{category}       - Events by SOC category
    GET  /adverse-events/signals                             - List safety signals
    GET  /adverse-events/signals/{signal_id}                 - Get single signal
    PUT  /adverse-events/signals/{signal_id}                 - Update signal status
    POST /adverse-events/signals/detect                      - Run signal detection
    GET  /adverse-events/expedited-reports                   - List expedited reports
    POST /adverse-events/expedited-reports/{ae_id}/submit    - Submit expedited report
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.adverse_events import (
    AdverseEvent,
    AECategory,
    AECreate,
    AEListResponse,
    AEMetrics,
    AESeverity,
    AEStatus,
    AEUpdate,
    CausalityAssessment,
    ExpeditedReport,
    ExpeditedReportListResponse,
    ExpeditedReportStatus,
    ExpeditedReportSubmitRequest,
    NarrativeReport,
    SafetySignal,
    SafetySignalListResponse,
    SafetySignalStatus,
    SafetySignalUpdateRequest,
)
from app.services.adverse_event_service import get_adverse_event_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/adverse-events",
    tags=["Adverse Events"],
)


# ---------------------------------------------------------------------------
# Adverse event CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/events",
    response_model=AEListResponse,
    summary="List adverse events",
    description="Retrieve adverse events with optional filtering by trial, severity, status, category, and seriousness.",
)
async def list_events(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    severity: Optional[AESeverity] = Query(None, description="Filter by severity"),
    status: Optional[AEStatus] = Query(None, description="Filter by status"),
    category: Optional[AECategory] = Query(None, description="Filter by SOC category"),
    serious: Optional[bool] = Query(None, description="Filter by seriousness"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> AEListResponse:
    """List adverse events with filtering and pagination."""
    svc = get_adverse_event_service()
    items, total = svc.list_events(
        trial_id=trial_id,
        severity=severity,
        status=status,
        category=category,
        serious=serious,
        limit=limit,
        offset=offset,
    )
    return AEListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/events/metrics",
    response_model=AEMetrics,
    summary="Adverse event metrics",
    description="Aggregated safety metrics for the dashboard, optionally filtered by trial.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> AEMetrics:
    """Return aggregated AE metrics."""
    svc = get_adverse_event_service()
    return svc.get_metrics(trial_id=trial_id)


@router.get(
    "/events/by-category/{category}",
    response_model=list[AdverseEvent],
    summary="Events by SOC category",
    description="Return all adverse events in a specific System Organ Class category.",
)
async def get_events_by_category(category: AECategory) -> list[AdverseEvent]:
    """Return all events in a SOC category."""
    svc = get_adverse_event_service()
    return svc.get_events_by_category(category)


@router.get(
    "/events/{ae_id}",
    response_model=AdverseEvent,
    summary="Get adverse event",
    description="Retrieve a single adverse event by ID.",
)
async def get_event(ae_id: str) -> AdverseEvent:
    """Return a single adverse event."""
    svc = get_adverse_event_service()
    try:
        return svc.get_event(ae_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Adverse event {ae_id} not found")


@router.post(
    "/events",
    response_model=AdverseEvent,
    status_code=201,
    summary="Report adverse event",
    description="Report a new adverse event. Auto-detects expedited reporting requirements.",
)
async def report_event(data: AECreate) -> AdverseEvent:
    """Report a new adverse event."""
    svc = get_adverse_event_service()
    return svc.report_event(data)


@router.put(
    "/events/{ae_id}",
    response_model=AdverseEvent,
    summary="Update adverse event",
    description="Update an adverse event with status transition validation.",
)
async def update_event(ae_id: str, data: AEUpdate) -> AdverseEvent:
    """Update an existing adverse event."""
    svc = get_adverse_event_service()
    try:
        return svc.update_event(ae_id, data)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Adverse event {ae_id} not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Causality assessment
# ---------------------------------------------------------------------------


@router.get(
    "/events/{ae_id}/causality",
    response_model=CausalityAssessment,
    summary="Causality assessment",
    description="Run a Naranjo-based causality assessment for an adverse event.",
)
async def assess_causality(ae_id: str) -> CausalityAssessment:
    """Assess causality using the Naranjo algorithm."""
    svc = get_adverse_event_service()
    try:
        return svc.assess_causality(ae_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Adverse event {ae_id} not found")


# ---------------------------------------------------------------------------
# Narrative generation
# ---------------------------------------------------------------------------


@router.get(
    "/events/{ae_id}/narrative",
    response_model=NarrativeReport,
    summary="Generate narrative",
    description="Generate a MedWatch-style narrative report for an adverse event.",
)
async def generate_narrative(ae_id: str) -> NarrativeReport:
    """Generate a narrative report for an adverse event."""
    svc = get_adverse_event_service()
    try:
        return svc.generate_narrative(ae_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Adverse event {ae_id} not found")


# ---------------------------------------------------------------------------
# Safety signals
# ---------------------------------------------------------------------------


@router.get(
    "/signals",
    response_model=SafetySignalListResponse,
    summary="List safety signals",
    description="List all safety signals, optionally filtered by status.",
)
async def list_signals(
    status: Optional[SafetySignalStatus] = Query(None, description="Filter by signal status"),
) -> SafetySignalListResponse:
    """List safety signals."""
    svc = get_adverse_event_service()
    signals = svc.list_signals(status=status)
    return SafetySignalListResponse(items=signals, total=len(signals))


@router.get(
    "/signals/{signal_id}",
    response_model=SafetySignal,
    summary="Get safety signal",
    description="Retrieve a specific safety signal by ID.",
)
async def get_signal(signal_id: str) -> SafetySignal:
    """Get a specific safety signal."""
    svc = get_adverse_event_service()
    try:
        return svc.get_signal(signal_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Safety signal {signal_id} not found")


@router.put(
    "/signals/{signal_id}",
    response_model=SafetySignal,
    summary="Update signal status",
    description="Update the status and assessor of a safety signal.",
)
async def update_signal(signal_id: str, data: SafetySignalUpdateRequest) -> SafetySignal:
    """Update signal status."""
    svc = get_adverse_event_service()
    try:
        return svc.update_signal_status(signal_id, data.status, data.assessed_by)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Safety signal {signal_id} not found")


@router.post(
    "/signals/detect",
    response_model=list[SafetySignal],
    summary="Detect safety signals",
    description="Run statistical safety signal detection, optionally scoped to a trial.",
)
async def detect_signals(
    trial_id: Optional[str] = Query(None, description="Limit detection to a specific trial"),
) -> list[SafetySignal]:
    """Run safety signal detection."""
    svc = get_adverse_event_service()
    return svc.detect_safety_signals(trial_id=trial_id)


# ---------------------------------------------------------------------------
# Expedited reporting
# ---------------------------------------------------------------------------


@router.get(
    "/expedited-reports",
    response_model=ExpeditedReportListResponse,
    summary="List expedited reports",
    description="List expedited regulatory reports, optionally filtered by status.",
)
async def list_expedited_reports(
    status: Optional[ExpeditedReportStatus] = Query(None, description="Filter by report status"),
) -> ExpeditedReportListResponse:
    """List expedited reports."""
    svc = get_adverse_event_service()
    reports = svc.get_expedited_reports(status=status)
    return ExpeditedReportListResponse(items=reports, total=len(reports))


@router.post(
    "/expedited-reports/{ae_id}/submit",
    response_model=ExpeditedReport,
    summary="Submit expedited report",
    description="Submit an expedited regulatory report for an adverse event.",
)
async def submit_expedited_report(
    ae_id: str, data: ExpeditedReportSubmitRequest
) -> ExpeditedReport:
    """Submit an expedited report."""
    svc = get_adverse_event_service()
    try:
        return svc.submit_expedited_report(ae_id, data.report_type, data.regulatory_body)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Adverse event {ae_id} not found")
