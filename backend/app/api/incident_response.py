"""Incident Response Playbooks API endpoints (CISO-12).

Provides comprehensive incident response management including playbook CRUD,
incident lifecycle management, regulatory notification tracking, escalation
handling, post-incident reviews, and aggregated metrics.

Endpoints:
    GET    /incident-response/playbooks                       - List playbooks
    GET    /incident-response/playbooks/{id}                  - Get playbook
    POST   /incident-response/playbooks                      - Create playbook
    PUT    /incident-response/playbooks/{id}                  - Update playbook
    DELETE /incident-response/playbooks/{id}                  - Delete playbook
    POST   /incident-response/playbooks/{id}/test             - Record playbook test
    GET    /incident-response/playbooks/schedule              - Testing schedule
    GET    /incident-response/incidents                       - List incidents
    GET    /incident-response/incidents/active                - Active incidents
    GET    /incident-response/incidents/metrics               - Incident metrics
    GET    /incident-response/incidents/{id}                  - Get incident
    POST   /incident-response/incidents                      - Create incident
    PUT    /incident-response/incidents/{id}                  - Update incident
    GET    /incident-response/incidents/{id}/timeline         - Event timeline
    POST   /incident-response/incidents/{id}/events           - Log event
    GET    /incident-response/incidents/{id}/notifications    - Get notifications
    POST   /incident-response/incidents/{id}/notifications    - Create notification
    PUT    /incident-response/incidents/{id}/notifications/{nid}/send - Send notification
    POST   /incident-response/incidents/{id}/escalate         - Escalate incident
    GET    /incident-response/escalation-matrix               - Escalation matrix
    GET    /incident-response/sla-breaches                    - Check SLA breaches
    GET    /incident-response/notifications/overdue           - Overdue notifications
    GET    /incident-response/reviews                         - List reviews
    GET    /incident-response/reviews/{id}                    - Get review
    POST   /incident-response/incidents/{id}/review           - Create review
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.incident_response import (
    EscalationLevel,
    EscalationMatrix,
    EventCreateRequest,
    IncidentCategory,
    IncidentCreateRequest,
    IncidentEvent,
    IncidentListResponse,
    IncidentMetrics,
    IncidentPhase,
    IncidentRecord,
    IncidentSeverity,
    IncidentUpdateRequest,
    NotificationCreateRequest,
    Playbook,
    PlaybookStep,
    PlaybookTestResult,
    PlaybookType,
    PostIncidentReview,
    PostIncidentReviewRequest,
    RegulatoryNotification,
)
from app.services.incident_response_service import get_incident_response_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/incident-response",
    tags=["Incident Response"],
)


# ---------------------------------------------------------------------------
# Playbook endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/playbooks/schedule",
    response_model=list[dict],
    summary="Get playbook testing schedule",
    description="Get the testing schedule for all playbooks with overdue indicators.",
)
async def get_playbook_testing_schedule() -> list[dict]:
    """Get playbook testing schedule."""
    svc = get_incident_response_service()
    return svc.get_playbook_testing_schedule()


@router.get(
    "/playbooks",
    summary="List playbooks",
    description="List incident response playbooks with optional type filtering.",
)
async def list_playbooks(
    playbook_type: Optional[PlaybookType] = Query(None, description="Filter by playbook type"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> dict:
    """List playbooks with filtering and pagination."""
    svc = get_incident_response_service()
    items, total = svc.list_playbooks(playbook_type=playbook_type, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get(
    "/playbooks/{playbook_id}",
    response_model=Playbook,
    summary="Get playbook",
    description="Retrieve a specific incident response playbook by ID.",
)
async def get_playbook(playbook_id: str) -> Playbook:
    """Get a specific playbook."""
    svc = get_incident_response_service()
    try:
        return svc.get_playbook(playbook_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Playbook {playbook_id} not found")


@router.post(
    "/playbooks",
    response_model=Playbook,
    status_code=201,
    summary="Create playbook",
    description="Create a new incident response playbook with steps.",
)
async def create_playbook(
    playbook_type: PlaybookType,
    title: str,
    description: str,
    severity_threshold: IncidentSeverity,
    steps: list[PlaybookStep],
    test_frequency_days: int = 90,
) -> Playbook:
    """Create a new playbook."""
    svc = get_incident_response_service()
    return svc.create_playbook(
        playbook_type=playbook_type,
        title=title,
        description=description,
        severity_threshold=severity_threshold,
        steps=steps,
        test_frequency_days=test_frequency_days,
    )


@router.put(
    "/playbooks/{playbook_id}",
    response_model=Playbook,
    summary="Update playbook",
    description="Update an existing incident response playbook.",
)
async def update_playbook(
    playbook_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    severity_threshold: Optional[IncidentSeverity] = None,
    steps: Optional[list[PlaybookStep]] = None,
    test_frequency_days: Optional[int] = None,
) -> Playbook:
    """Update a playbook."""
    svc = get_incident_response_service()
    try:
        return svc.update_playbook(
            playbook_id,
            title=title,
            description=description,
            steps=steps,
            severity_threshold=severity_threshold,
            test_frequency_days=test_frequency_days,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Playbook {playbook_id} not found")


@router.delete(
    "/playbooks/{playbook_id}",
    status_code=204,
    summary="Delete playbook",
    description="Delete an incident response playbook.",
)
async def delete_playbook(playbook_id: str) -> None:
    """Delete a playbook."""
    svc = get_incident_response_service()
    try:
        svc.delete_playbook(playbook_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Playbook {playbook_id} not found")


@router.post(
    "/playbooks/{playbook_id}/test",
    response_model=PlaybookTestResult,
    summary="Record playbook test",
    description="Record a tabletop exercise or playbook test result.",
)
async def record_playbook_test(
    playbook_id: str,
    participants: list[str],
    findings: list[str],
    passed: bool,
) -> PlaybookTestResult:
    """Record a playbook test result."""
    svc = get_incident_response_service()
    try:
        return svc.record_playbook_test(
            playbook_id=playbook_id,
            participants=participants,
            findings=findings,
            passed=passed,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Playbook {playbook_id} not found")


# ---------------------------------------------------------------------------
# Incident endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/incidents/active",
    response_model=list[IncidentRecord],
    summary="Active incidents dashboard",
    description="Get all currently active (non-closed) incidents for the dashboard.",
)
async def get_active_incidents() -> list[IncidentRecord]:
    """Get active incidents."""
    svc = get_incident_response_service()
    return svc.get_active_incidents()


@router.get(
    "/incidents/metrics",
    response_model=IncidentMetrics,
    summary="Incident metrics",
    description="Aggregated incident response metrics including MTTD, MTTC, MTTR, and SLA compliance.",
)
async def get_incident_metrics() -> IncidentMetrics:
    """Get incident metrics."""
    svc = get_incident_response_service()
    return svc.get_metrics()


@router.get(
    "/incidents",
    response_model=IncidentListResponse,
    summary="List incidents",
    description="List incidents with optional filtering by severity, category, phase, and active status.",
)
async def list_incidents(
    severity: Optional[IncidentSeverity] = Query(None, description="Filter by severity"),
    category: Optional[IncidentCategory] = Query(None, description="Filter by category"),
    phase: Optional[IncidentPhase] = Query(None, description="Filter by phase"),
    active_only: bool = Query(False, description="Show only active incidents"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> IncidentListResponse:
    """List incidents with filtering and pagination."""
    svc = get_incident_response_service()
    items, total = svc.list_incidents(
        severity=severity,
        category=category,
        phase=phase,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
    return IncidentListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/incidents/{incident_id}",
    response_model=IncidentRecord,
    summary="Get incident",
    description="Retrieve a specific incident record by ID.",
)
async def get_incident(incident_id: str) -> IncidentRecord:
    """Get a specific incident."""
    svc = get_incident_response_service()
    try:
        return svc.get_incident(incident_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")


@router.post(
    "/incidents",
    response_model=IncidentRecord,
    status_code=201,
    summary="Create incident",
    description="Report a new security incident. Auto-assigns playbook and escalation level.",
)
async def create_incident(request: IncidentCreateRequest) -> IncidentRecord:
    """Create a new incident."""
    svc = get_incident_response_service()
    return svc.create_incident(request)


@router.put(
    "/incidents/{incident_id}",
    response_model=IncidentRecord,
    summary="Update incident",
    description="Update an incident record. Validates phase transitions.",
)
async def update_incident(incident_id: str, request: IncidentUpdateRequest) -> IncidentRecord:
    """Update an incident."""
    svc = get_incident_response_service()
    try:
        return svc.update_incident(incident_id, request)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Event timeline endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/incidents/{incident_id}/timeline",
    response_model=list[IncidentEvent],
    summary="Get incident timeline",
    description="Get the full event timeline for an incident.",
)
async def get_incident_timeline(incident_id: str) -> list[IncidentEvent]:
    """Get incident event timeline."""
    svc = get_incident_response_service()
    try:
        return svc.get_incident_timeline(incident_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")


@router.post(
    "/incidents/{incident_id}/events",
    response_model=IncidentEvent,
    status_code=201,
    summary="Log incident event",
    description="Log a new timeline event for an incident.",
)
async def log_incident_event(incident_id: str, request: EventCreateRequest) -> IncidentEvent:
    """Log an incident event."""
    svc = get_incident_response_service()
    try:
        return svc.add_event(incident_id, request)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")


# ---------------------------------------------------------------------------
# Notification endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/notifications/overdue",
    response_model=list[RegulatoryNotification],
    summary="Overdue notifications",
    description="Get all overdue regulatory notifications across all incidents.",
)
async def get_overdue_notifications() -> list[RegulatoryNotification]:
    """Get overdue notifications."""
    svc = get_incident_response_service()
    return svc.get_overdue_notifications()


@router.get(
    "/incidents/{incident_id}/notifications",
    response_model=list[RegulatoryNotification],
    summary="Get incident notifications",
    description="Get all regulatory notifications for a specific incident.",
)
async def get_incident_notifications(incident_id: str) -> list[RegulatoryNotification]:
    """Get notifications for an incident."""
    svc = get_incident_response_service()
    try:
        return svc.get_incident_notifications(incident_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")


@router.post(
    "/incidents/{incident_id}/notifications",
    response_model=RegulatoryNotification,
    status_code=201,
    summary="Create notification",
    description="Create a regulatory notification for an incident. Deadline auto-calculated.",
)
async def create_notification(
    incident_id: str, request: NotificationCreateRequest
) -> RegulatoryNotification:
    """Create a regulatory notification."""
    svc = get_incident_response_service()
    try:
        return svc.create_notification(incident_id, request)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")


@router.put(
    "/incidents/{incident_id}/notifications/{notification_id}/send",
    response_model=RegulatoryNotification,
    summary="Send notification",
    description="Mark a regulatory notification as sent.",
)
async def send_notification(incident_id: str, notification_id: str) -> RegulatoryNotification:
    """Mark a notification as sent."""
    svc = get_incident_response_service()
    try:
        return svc.send_notification(incident_id, notification_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Escalation endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/escalation-matrix",
    response_model=list[EscalationMatrix],
    summary="Get escalation matrix",
    description="Get the full incident escalation matrix with contacts.",
)
async def get_escalation_matrix() -> list[EscalationMatrix]:
    """Get escalation matrix."""
    svc = get_incident_response_service()
    return svc.get_escalation_matrix()


@router.post(
    "/incidents/{incident_id}/escalate",
    response_model=IncidentRecord,
    summary="Escalate incident",
    description="Escalate an incident to a specified escalation level.",
)
async def escalate_incident(incident_id: str, level: EscalationLevel) -> IncidentRecord:
    """Escalate an incident."""
    svc = get_incident_response_service()
    try:
        return svc.escalate_incident(incident_id, level)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")


@router.get(
    "/sla-breaches",
    summary="Check SLA breaches",
    description="Check for SLA breaches on all active incidents.",
)
async def check_sla_breaches() -> list[dict]:
    """Check SLA breaches."""
    svc = get_incident_response_service()
    return svc.check_sla_breaches()


# ---------------------------------------------------------------------------
# Post-incident review endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/reviews",
    summary="List reviews",
    description="List post-incident reviews with optional incident filtering.",
)
async def list_reviews(
    incident_id: Optional[str] = Query(None, description="Filter by incident ID"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> dict:
    """List post-incident reviews."""
    svc = get_incident_response_service()
    items, total = svc.list_reviews(incident_id=incident_id, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get(
    "/reviews/{review_id}",
    response_model=PostIncidentReview,
    summary="Get review",
    description="Get a specific post-incident review.",
)
async def get_review(review_id: str) -> PostIncidentReview:
    """Get a specific review."""
    svc = get_incident_response_service()
    try:
        return svc.get_review(review_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Review {review_id} not found")


@router.post(
    "/incidents/{incident_id}/review",
    response_model=PostIncidentReview,
    status_code=201,
    summary="Create post-incident review",
    description="Create a post-incident review for an incident in POST_INCIDENT or CLOSED phase.",
)
async def create_review(
    incident_id: str, request: PostIncidentReviewRequest
) -> PostIncidentReview:
    """Create a post-incident review."""
    svc = get_incident_response_service()
    try:
        return svc.create_review(incident_id, request)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
