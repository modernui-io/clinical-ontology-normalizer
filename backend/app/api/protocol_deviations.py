"""Protocol Deviation Tracking API endpoints (CMO-7).

Provides CRUD operations, notification tracking, CAPA linkage,
metrics, and trend analysis for clinical protocol deviations.

Endpoints:
    GET  /protocol-deviations/deviations                    - List with filters
    GET  /protocol-deviations/deviations/metrics             - Aggregated metrics
    GET  /protocol-deviations/deviations/trends              - Monthly trends
    GET  /protocol-deviations/deviations/overdue-notifications - Overdue notifications
    GET  /protocol-deviations/deviations/{id}                - Detail
    POST /protocol-deviations/deviations                    - Create
    PUT  /protocol-deviations/deviations/{id}                - Update
    POST /protocol-deviations/deviations/{id}/link-capa      - Link CAPA
    POST /protocol-deviations/deviations/{id}/irb-notification       - Record IRB notification
    POST /protocol-deviations/deviations/{id}/sponsor-notification   - Record sponsor notification
    POST /protocol-deviations/deviations/{id}/impact-assessment      - Record impact assessment
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.protocol_deviation import (
    CAPALinkRequest,
    DeviationCreate,
    DeviationListResponse,
    DeviationMetrics,
    DeviationRecord,
    DeviationSeverity,
    DeviationStatus,
    DeviationTrend,
    DeviationType,
    DeviationUpdate,
    ImpactAssessmentRequest,
    NotificationRequest,
)
from app.services.protocol_deviation_service import get_protocol_deviation_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/protocol-deviations",
    tags=["Protocol Deviations"],
)


# ---------------------------------------------------------------------------
# List / filter
# ---------------------------------------------------------------------------


@router.get(
    "/deviations",
    response_model=DeviationListResponse,
    summary="List protocol deviations",
    description="Retrieve protocol deviations with optional filtering by trial, severity, status, and type.",
)
async def list_deviations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    severity: Optional[DeviationSeverity] = Query(None, description="Filter by severity"),
    status: Optional[DeviationStatus] = Query(None, description="Filter by status"),
    deviation_type: Optional[DeviationType] = Query(None, description="Filter by deviation type"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> DeviationListResponse:
    """List protocol deviations with filtering and pagination."""
    svc = get_protocol_deviation_service()
    items, total = svc.list_deviations(
        trial_id=trial_id,
        severity=severity,
        status=status,
        deviation_type=deviation_type,
        limit=limit,
        offset=offset,
    )
    return DeviationListResponse(items=items, total=total, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/deviations/metrics",
    response_model=DeviationMetrics,
    summary="Deviation metrics",
    description="Aggregated protocol deviation metrics with optional trial filter.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> DeviationMetrics:
    """Return aggregated deviation metrics."""
    svc = get_protocol_deviation_service()
    return svc.get_metrics(trial_id=trial_id)


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------


@router.get(
    "/deviations/trends",
    response_model=list[DeviationTrend],
    summary="Deviation trends",
    description="Monthly deviation trend data for the last N months.",
)
async def get_trends(
    months: int = Query(12, ge=1, le=60, description="Number of months to include"),
) -> list[DeviationTrend]:
    """Return monthly deviation trends."""
    svc = get_protocol_deviation_service()
    return svc.get_trends(months=months)


# ---------------------------------------------------------------------------
# Overdue notifications
# ---------------------------------------------------------------------------


@router.get(
    "/deviations/overdue-notifications",
    response_model=list[DeviationRecord],
    summary="Overdue notifications",
    description=(
        "Deviations requiring IRB or sponsor notification that have "
        "exceeded their SLA deadlines."
    ),
)
async def get_overdue_notifications() -> list[DeviationRecord]:
    """Return deviations with overdue notifications."""
    svc = get_protocol_deviation_service()
    return svc.get_overdue_notifications()


# ---------------------------------------------------------------------------
# Single deviation CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/deviations/{deviation_id}",
    response_model=DeviationRecord,
    summary="Get deviation detail",
    description="Retrieve a single protocol deviation by ID.",
)
async def get_deviation(deviation_id: str) -> DeviationRecord:
    """Return a single deviation."""
    svc = get_protocol_deviation_service()
    try:
        return svc.get_deviation(deviation_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Deviation {deviation_id} not found")


@router.post(
    "/deviations",
    response_model=DeviationRecord,
    status_code=201,
    summary="Create deviation",
    description="Report a new protocol deviation.",
)
async def create_deviation(data: DeviationCreate) -> DeviationRecord:
    """Create a new protocol deviation."""
    svc = get_protocol_deviation_service()
    return svc.create_deviation(data)


@router.put(
    "/deviations/{deviation_id}",
    response_model=DeviationRecord,
    summary="Update deviation",
    description="Update deviation fields (status, severity, reviewer, etc.).",
)
async def update_deviation(
    deviation_id: str, data: DeviationUpdate
) -> DeviationRecord:
    """Update an existing deviation."""
    svc = get_protocol_deviation_service()
    try:
        return svc.update_deviation(deviation_id, data)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Deviation {deviation_id} not found")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# ---------------------------------------------------------------------------
# CAPA linkage
# ---------------------------------------------------------------------------


@router.post(
    "/deviations/{deviation_id}/link-capa",
    response_model=DeviationRecord,
    summary="Link CAPA",
    description="Link a deviation to a Corrective and Preventive Action (CAPA) record.",
)
async def link_capa(
    deviation_id: str, body: CAPALinkRequest
) -> DeviationRecord:
    """Link a deviation to a CAPA record."""
    svc = get_protocol_deviation_service()
    try:
        return svc.link_capa(deviation_id, body.capa_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Deviation {deviation_id} not found")


# ---------------------------------------------------------------------------
# Notification recording
# ---------------------------------------------------------------------------


@router.post(
    "/deviations/{deviation_id}/irb-notification",
    response_model=DeviationRecord,
    summary="Record IRB notification",
    description="Record the date an IRB notification was sent for this deviation.",
)
async def record_irb_notification(
    deviation_id: str, body: NotificationRequest
) -> DeviationRecord:
    """Record IRB notification date."""
    svc = get_protocol_deviation_service()
    try:
        return svc.record_irb_notification(deviation_id, body.notified_date)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Deviation {deviation_id} not found")


@router.post(
    "/deviations/{deviation_id}/sponsor-notification",
    response_model=DeviationRecord,
    summary="Record sponsor notification",
    description="Record the date a sponsor notification was sent for this deviation.",
)
async def record_sponsor_notification(
    deviation_id: str, body: NotificationRequest
) -> DeviationRecord:
    """Record sponsor notification date."""
    svc = get_protocol_deviation_service()
    try:
        return svc.record_sponsor_notification(deviation_id, body.notified_date)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Deviation {deviation_id} not found")


# ---------------------------------------------------------------------------
# Impact assessment
# ---------------------------------------------------------------------------


@router.post(
    "/deviations/{deviation_id}/impact-assessment",
    response_model=DeviationRecord,
    summary="Record impact assessment",
    description="Record the impact assessment for a deviation.",
)
async def record_impact_assessment(
    deviation_id: str, body: ImpactAssessmentRequest
) -> DeviationRecord:
    """Record impact assessment."""
    svc = get_protocol_deviation_service()
    try:
        return svc.assess_impact(deviation_id, body.impact_text)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Deviation {deviation_id} not found")
