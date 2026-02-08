"""Security incident management API endpoints (CISO-11).

Provides endpoints for creating, tracking, and managing security incidents
as part of the Incident Response Plan.

Endpoints:
    POST   /api/v1/security/incidents              - Create a new incident
    GET    /api/v1/security/incidents              - List incidents (filterable)
    GET    /api/v1/security/incidents/{id}         - Get incident detail
    PUT    /api/v1/security/incidents/{id}         - Update incident
    POST   /api/v1/security/incidents/{id}/timeline - Add timeline event
    GET    /api/v1/security/incidents/stats         - Get incident statistics
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.services.incident_service import (
    Incident,
    IncidentSeverity,
    IncidentService,
    IncidentStatus,
    IncidentType,
    TimelineEvent,
    get_incident_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/security/incidents", tags=["Security Incidents"])


# ============================================================================
# Request/Response Models
# ============================================================================


class CreateIncidentRequest(BaseModel):
    """Request body for creating a new incident."""

    title: str = Field(..., min_length=1, max_length=500, description="Brief incident title")
    description: str = Field(..., min_length=1, description="Detailed incident description")
    severity: IncidentSeverity = Field(..., description="Severity level (SEV1-SEV4)")
    incident_type: IncidentType = Field(..., description="Type of incident")
    reported_by: str = Field(..., min_length=1, description="Reporter identifier")
    affected_systems: list[str] = Field(default_factory=list, description="Affected system names")
    phi_involved: bool = Field(default=False, description="Whether PHI is potentially involved")
    incident_commander: str | None = Field(default=None, description="Assigned incident commander")


class UpdateIncidentRequest(BaseModel):
    """Request body for updating an incident."""

    status: IncidentStatus | None = Field(default=None, description="New status")
    severity: IncidentSeverity | None = Field(default=None, description="Updated severity")
    title: str | None = Field(default=None, max_length=500, description="Updated title")
    description: str | None = Field(default=None, description="Updated description")
    incident_commander: str | None = Field(default=None, description="Updated IC")
    assigned_responders: list[str] | None = Field(default=None, description="Updated responders")
    affected_systems: list[str] | None = Field(default=None, description="Updated affected systems")
    evidence_links: list[str] | None = Field(default=None, description="Updated evidence links")
    phi_involved: bool | None = Field(default=None, description="Updated PHI flag")
    estimated_affected_records: int | None = Field(default=None, description="Updated record count")
    updated_by: str | None = Field(default=None, description="Who is making this update")


class AddTimelineEventRequest(BaseModel):
    """Request body for adding a timeline event."""

    event_type: str = Field(..., min_length=1, description="Event type (e.g., note, action, escalation)")
    description: str = Field(..., min_length=1, description="Event description")
    actor: str | None = Field(default=None, description="Who performed the action")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional event data")


class TimelineEventResponse(BaseModel):
    """Response model for a timeline event."""

    id: str
    timestamp: datetime
    event_type: str
    description: str
    actor: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        from_attributes = True


class IncidentResponse(BaseModel):
    """Response model for an incident."""

    id: str
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus
    incident_type: IncidentType
    reported_by: str
    reported_at: datetime
    acknowledged_at: datetime | None = None
    contained_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    updated_at: datetime
    incident_commander: str | None = None
    assigned_responders: list[str] = Field(default_factory=list)
    affected_systems: list[str] = Field(default_factory=list)
    evidence_links: list[str] = Field(default_factory=list)
    phi_involved: bool = False
    estimated_affected_records: int | None = None
    timeline: list[TimelineEventResponse] = Field(default_factory=list)
    escalated: bool = False
    original_severity: IncidentSeverity | None = None

    class Config:
        from_attributes = True


class IncidentListResponse(BaseModel):
    """Response model for paginated incident list."""

    incidents: list[IncidentResponse]
    total: int
    limit: int
    offset: int


class IncidentStatsResponse(BaseModel):
    """Response model for incident statistics."""

    total_incidents: int
    open_incidents: int
    by_severity: dict[str, int]
    by_status: dict[str, int]
    phi_involved_count: int


# ============================================================================
# Helper functions
# ============================================================================


def _incident_to_response(incident: Incident) -> IncidentResponse:
    """Convert an Incident model to an IncidentResponse."""
    return IncidentResponse(
        id=incident.id,
        title=incident.title,
        description=incident.description,
        severity=incident.severity,
        status=incident.status,
        incident_type=incident.incident_type,
        reported_by=incident.reported_by,
        reported_at=incident.reported_at,
        acknowledged_at=incident.acknowledged_at,
        contained_at=incident.contained_at,
        resolved_at=incident.resolved_at,
        closed_at=incident.closed_at,
        updated_at=incident.updated_at,
        incident_commander=incident.incident_commander,
        assigned_responders=incident.assigned_responders,
        affected_systems=incident.affected_systems,
        evidence_links=incident.evidence_links,
        phi_involved=incident.phi_involved,
        estimated_affected_records=incident.estimated_affected_records,
        timeline=[
            TimelineEventResponse(
                id=e.id,
                timestamp=e.timestamp,
                event_type=e.event_type,
                description=e.description,
                actor=e.actor,
                metadata=e.metadata,
            )
            for e in incident.timeline
        ],
        escalated=incident.escalated,
        original_severity=incident.original_severity,
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a security incident",
    description="Create a new security incident record. Triggers incident response workflow.",
)
async def create_incident(request: CreateIncidentRequest) -> IncidentResponse:
    """Create a new security incident."""
    service = get_incident_service()

    incident = service.create_incident(
        title=request.title,
        description=request.description,
        severity=request.severity,
        incident_type=request.incident_type,
        reported_by=request.reported_by,
        affected_systems=request.affected_systems,
        phi_involved=request.phi_involved,
        incident_commander=request.incident_commander,
    )

    logger.info(f"Incident created via API: {incident.id}")
    return _incident_to_response(incident)


@router.get(
    "/stats",
    response_model=IncidentStatsResponse,
    summary="Get incident statistics",
    description="Get aggregated incident statistics including counts by severity and status.",
)
async def get_incident_stats() -> IncidentStatsResponse:
    """Get aggregated incident statistics."""
    service = get_incident_service()
    stats = service.get_stats()
    return IncidentStatsResponse(**stats)


@router.get(
    "",
    response_model=IncidentListResponse,
    summary="List security incidents",
    description="List security incidents with optional filtering by severity, status, and type.",
)
async def list_incidents(
    severity: IncidentSeverity | None = Query(default=None, description="Filter by severity"),
    incident_status: IncidentStatus | None = Query(
        default=None, alias="status", description="Filter by status"
    ),
    incident_type: IncidentType | None = Query(
        default=None, alias="type", description="Filter by incident type"
    ),
    phi_involved: bool | None = Query(default=None, description="Filter by PHI involvement"),
    limit: int = Query(default=100, ge=1, le=1000, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> IncidentListResponse:
    """List incidents with optional filters."""
    service = get_incident_service()

    incidents, total = service.list_incidents(
        severity=severity,
        status=incident_status,
        incident_type=incident_type,
        phi_involved=phi_involved,
        limit=limit,
        offset=offset,
    )

    return IncidentListResponse(
        incidents=[_incident_to_response(i) for i in incidents],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
    summary="Get incident detail",
    description="Get full details of a specific security incident including timeline.",
)
async def get_incident(incident_id: str) -> IncidentResponse:
    """Get a specific incident by ID."""
    service = get_incident_service()
    incident = service.get_incident(incident_id)

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident not found: {incident_id}",
        )

    return _incident_to_response(incident)


@router.put(
    "/{incident_id}",
    response_model=IncidentResponse,
    summary="Update a security incident",
    description="Update incident fields including status, severity, and responder assignments.",
)
async def update_incident(
    incident_id: str,
    request: UpdateIncidentRequest,
) -> IncidentResponse:
    """Update an existing incident."""
    service = get_incident_service()

    try:
        incident = service.update_incident(
            incident_id=incident_id,
            status=request.status,
            severity=request.severity,
            title=request.title,
            description=request.description,
            incident_commander=request.incident_commander,
            assigned_responders=request.assigned_responders,
            affected_systems=request.affected_systems,
            evidence_links=request.evidence_links,
            phi_involved=request.phi_involved,
            estimated_affected_records=request.estimated_affected_records,
            updated_by=request.updated_by,
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

    return _incident_to_response(incident)


@router.post(
    "/{incident_id}/timeline",
    response_model=TimelineEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add timeline event",
    description="Add a new event to an incident's timeline for tracking response actions.",
)
async def add_timeline_event(
    incident_id: str,
    request: AddTimelineEventRequest,
) -> TimelineEventResponse:
    """Add a timeline event to an incident."""
    service = get_incident_service()

    try:
        event = service.add_timeline_event(
            incident_id=incident_id,
            event_type=request.event_type,
            description=request.description,
            actor=request.actor,
            metadata=request.metadata,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return TimelineEventResponse(
        id=event.id,
        timestamp=event.timestamp,
        event_type=event.event_type,
        description=event.description,
        actor=event.actor,
        metadata=event.metadata,
    )
