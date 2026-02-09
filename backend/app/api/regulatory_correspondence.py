"""Regulatory Correspondence Tracking API endpoints (CLO-7).

Provides CRUD operations, correspondence workflow, action item management,
regulatory timeline tracking, agency contact management, deadline reporting,
metrics, and agency relationship summaries.

Endpoints:
    GET    /regulatory-correspondence/correspondence                          - List with filters
    GET    /regulatory-correspondence/correspondence/metrics                  - Aggregated metrics
    GET    /regulatory-correspondence/correspondence/deadlines                - Deadline report
    GET    /regulatory-correspondence/correspondence/{id}                     - Detail
    POST   /regulatory-correspondence/correspondence                          - Create
    PUT    /regulatory-correspondence/correspondence/{id}                     - Update
    DELETE /regulatory-correspondence/correspondence/{id}                     - Delete
    POST   /regulatory-correspondence/correspondence/{id}/submit              - Submit to agency
    POST   /regulatory-correspondence/correspondence/{id}/link                - Link correspondence
    GET    /regulatory-correspondence/correspondence/{id}/action-items        - List action items
    POST   /regulatory-correspondence/correspondence/{id}/action-items        - Create action item
    GET    /regulatory-correspondence/action-items/{id}                       - Get action item
    PUT    /regulatory-correspondence/action-items/{id}                       - Update action item
    DELETE /regulatory-correspondence/action-items/{id}                       - Delete action item
    GET    /regulatory-correspondence/action-items                            - List all action items
    GET    /regulatory-correspondence/timelines                               - List timelines
    GET    /regulatory-correspondence/timelines/{id}                          - Get timeline
    POST   /regulatory-correspondence/timelines                               - Create timeline
    PUT    /regulatory-correspondence/timelines/{id}                          - Update timeline
    DELETE /regulatory-correspondence/timelines/{id}                          - Delete timeline
    POST   /regulatory-correspondence/timelines/{id}/milestones               - Add milestone
    PUT    /regulatory-correspondence/timelines/{id}/milestones/{index}       - Update milestone
    DELETE /regulatory-correspondence/timelines/{id}/milestones/{index}       - Delete milestone
    GET    /regulatory-correspondence/contacts                                - List contacts
    GET    /regulatory-correspondence/contacts/{id}                           - Get contact
    POST   /regulatory-correspondence/contacts                                - Create contact
    PUT    /regulatory-correspondence/contacts/{id}                           - Update contact
    DELETE /regulatory-correspondence/contacts/{id}                           - Delete contact
    GET    /regulatory-correspondence/agency/{agency}/summary                 - Agency relationship
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.regulatory_correspondence import (
    ActionItem,
    ActionItemCreate,
    ActionItemListResponse,
    ActionItemUpdate,
    AgencyContact,
    AgencyContactCreate,
    AgencyContactListResponse,
    AgencyContactUpdate,
    AgencyRelationshipSummary,
    Correspondence,
    CorrespondenceCreate,
    CorrespondenceListResponse,
    CorrespondenceMetrics,
    CorrespondenceStatus,
    CorrespondenceType,
    CorrespondenceUpdate,
    DeadlineReport,
    LinkCorrespondenceRequest,
    MilestoneCreate,
    MilestoneUpdate,
    Priority,
    RegulatoryAgency,
    RegulatoryTimeline,
    TimelineCreate,
    TimelineListResponse,
    TimelineUpdate,
)
from app.services.regulatory_correspondence_service import (
    get_regulatory_correspondence_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/regulatory-correspondence",
    tags=["Regulatory Correspondence"],
)


# ---------------------------------------------------------------------------
# Correspondence CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/correspondence",
    response_model=CorrespondenceListResponse,
    summary="List regulatory correspondence",
    description="Retrieve correspondence records with optional filtering.",
)
async def list_correspondence(
    agency: Optional[RegulatoryAgency] = Query(None, description="Filter by agency"),
    correspondence_type: Optional[CorrespondenceType] = Query(
        None, description="Filter by type"
    ),
    status: Optional[CorrespondenceStatus] = Query(None, description="Filter by status"),
    priority: Optional[Priority] = Query(None, description="Filter by priority"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    search: Optional[str] = Query(None, description="Search in title/description"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> CorrespondenceListResponse:
    """List correspondence with filters and pagination."""
    svc = get_regulatory_correspondence_service()
    items, total = svc.list_correspondence(
        agency=agency,
        correspondence_type=correspondence_type,
        status=status,
        priority=priority,
        trial_id=trial_id,
        search=search,
        limit=limit,
        offset=offset,
    )
    return CorrespondenceListResponse(
        items=items, total=total, limit=limit, offset=offset
    )


@router.get(
    "/correspondence/metrics",
    response_model=CorrespondenceMetrics,
    summary="Correspondence metrics",
    description="Get aggregated correspondence metrics.",
)
async def get_metrics() -> CorrespondenceMetrics:
    """Retrieve aggregated correspondence metrics."""
    svc = get_regulatory_correspondence_service()
    return svc.get_metrics()


@router.get(
    "/correspondence/deadlines",
    response_model=DeadlineReport,
    summary="Deadline report",
    description="Get upcoming and overdue deadlines.",
)
async def get_deadlines(
    days_ahead: int = Query(30, ge=1, le=365, description="Days to look ahead"),
) -> DeadlineReport:
    """Retrieve deadline report with upcoming and overdue items."""
    svc = get_regulatory_correspondence_service()
    return svc.get_deadline_report(days_ahead=days_ahead)


@router.get(
    "/correspondence/{correspondence_id}",
    response_model=Correspondence,
    summary="Get correspondence detail",
    description="Retrieve a single correspondence record.",
)
async def get_correspondence(correspondence_id: str) -> Correspondence:
    """Get a single correspondence record by ID."""
    svc = get_regulatory_correspondence_service()
    try:
        return svc.get_correspondence(correspondence_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/correspondence",
    response_model=Correspondence,
    status_code=201,
    summary="Create correspondence",
    description="Create a new correspondence record.",
)
async def create_correspondence(payload: CorrespondenceCreate) -> Correspondence:
    """Create a new correspondence record."""
    svc = get_regulatory_correspondence_service()
    return svc.create_correspondence(payload)


@router.put(
    "/correspondence/{correspondence_id}",
    response_model=Correspondence,
    summary="Update correspondence",
    description="Update an existing correspondence record.",
)
async def update_correspondence(
    correspondence_id: str, payload: CorrespondenceUpdate
) -> Correspondence:
    """Update an existing correspondence record."""
    svc = get_regulatory_correspondence_service()
    try:
        return svc.update_correspondence(correspondence_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/correspondence/{correspondence_id}",
    status_code=204,
    summary="Delete correspondence",
    description="Delete a correspondence record and its action items.",
)
async def delete_correspondence(correspondence_id: str) -> None:
    """Delete a correspondence record."""
    svc = get_regulatory_correspondence_service()
    try:
        svc.delete_correspondence(correspondence_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/correspondence/{correspondence_id}/submit",
    response_model=Correspondence,
    summary="Submit correspondence",
    description="Transition correspondence to SUBMITTED status.",
)
async def submit_correspondence(correspondence_id: str) -> Correspondence:
    """Submit correspondence to regulatory agency."""
    svc = get_regulatory_correspondence_service()
    try:
        return svc.submit_correspondence(correspondence_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/correspondence/{correspondence_id}/link",
    response_model=Correspondence,
    summary="Link correspondence",
    description="Link two correspondence records together.",
)
async def link_correspondence(
    correspondence_id: str, payload: LinkCorrespondenceRequest
) -> Correspondence:
    """Link correspondence to a related record."""
    svc = get_regulatory_correspondence_service()
    try:
        return svc.link_correspondence(correspondence_id, payload.related_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Action items
# ---------------------------------------------------------------------------


@router.get(
    "/action-items",
    response_model=ActionItemListResponse,
    summary="List all action items",
    description="List action items across all correspondence.",
)
async def list_all_action_items(
    completed: Optional[bool] = Query(None, description="Filter by completion"),
    overdue_only: bool = Query(False, description="Show only overdue items"),
) -> ActionItemListResponse:
    """List all action items with optional filters."""
    svc = get_regulatory_correspondence_service()
    items = svc.list_action_items(completed=completed, overdue_only=overdue_only)
    return ActionItemListResponse(items=items, total=len(items))


@router.get(
    "/correspondence/{correspondence_id}/action-items",
    response_model=ActionItemListResponse,
    summary="List action items for correspondence",
    description="List action items for a specific correspondence.",
)
async def list_correspondence_action_items(
    correspondence_id: str,
) -> ActionItemListResponse:
    """List action items for a correspondence record."""
    svc = get_regulatory_correspondence_service()
    try:
        svc.get_correspondence(correspondence_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    items = svc.list_action_items(correspondence_id=correspondence_id)
    return ActionItemListResponse(items=items, total=len(items))


@router.post(
    "/correspondence/{correspondence_id}/action-items",
    response_model=ActionItem,
    status_code=201,
    summary="Create action item",
    description="Create an action item for a correspondence.",
)
async def create_action_item(
    correspondence_id: str, payload: ActionItemCreate
) -> ActionItem:
    """Create an action item."""
    svc = get_regulatory_correspondence_service()
    try:
        return svc.create_action_item(correspondence_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/action-items/{action_item_id}",
    response_model=ActionItem,
    summary="Get action item",
    description="Retrieve a single action item.",
)
async def get_action_item(action_item_id: str) -> ActionItem:
    """Get a single action item by ID."""
    svc = get_regulatory_correspondence_service()
    try:
        return svc.get_action_item(action_item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put(
    "/action-items/{action_item_id}",
    response_model=ActionItem,
    summary="Update action item",
    description="Update an action item.",
)
async def update_action_item(
    action_item_id: str, payload: ActionItemUpdate
) -> ActionItem:
    """Update an action item."""
    svc = get_regulatory_correspondence_service()
    try:
        return svc.update_action_item(action_item_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete(
    "/action-items/{action_item_id}",
    status_code=204,
    summary="Delete action item",
    description="Delete an action item.",
)
async def delete_action_item(action_item_id: str) -> None:
    """Delete an action item."""
    svc = get_regulatory_correspondence_service()
    try:
        svc.delete_action_item(action_item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Timelines
# ---------------------------------------------------------------------------


@router.get(
    "/timelines",
    response_model=TimelineListResponse,
    summary="List timelines",
    description="List all regulatory timelines.",
)
async def list_timelines() -> TimelineListResponse:
    """List all regulatory timelines."""
    svc = get_regulatory_correspondence_service()
    items = svc.list_timelines()
    return TimelineListResponse(items=items, total=len(items))


@router.get(
    "/timelines/{timeline_id}",
    response_model=RegulatoryTimeline,
    summary="Get timeline",
    description="Retrieve a regulatory timeline.",
)
async def get_timeline(timeline_id: str) -> RegulatoryTimeline:
    """Get a timeline by ID."""
    svc = get_regulatory_correspondence_service()
    try:
        return svc.get_timeline(timeline_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/timelines",
    response_model=RegulatoryTimeline,
    status_code=201,
    summary="Create timeline",
    description="Create a new regulatory timeline.",
)
async def create_timeline(payload: TimelineCreate) -> RegulatoryTimeline:
    """Create a new regulatory timeline."""
    svc = get_regulatory_correspondence_service()
    return svc.create_timeline(payload)


@router.put(
    "/timelines/{timeline_id}",
    response_model=RegulatoryTimeline,
    summary="Update timeline",
    description="Update a regulatory timeline.",
)
async def update_timeline(
    timeline_id: str, payload: TimelineUpdate
) -> RegulatoryTimeline:
    """Update a timeline."""
    svc = get_regulatory_correspondence_service()
    try:
        return svc.update_timeline(timeline_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete(
    "/timelines/{timeline_id}",
    status_code=204,
    summary="Delete timeline",
    description="Delete a regulatory timeline.",
)
async def delete_timeline(timeline_id: str) -> None:
    """Delete a timeline."""
    svc = get_regulatory_correspondence_service()
    try:
        svc.delete_timeline(timeline_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/timelines/{timeline_id}/milestones",
    response_model=RegulatoryTimeline,
    status_code=201,
    summary="Add milestone",
    description="Add a milestone to a timeline.",
)
async def add_milestone(
    timeline_id: str, payload: MilestoneCreate
) -> RegulatoryTimeline:
    """Add a milestone to a timeline."""
    svc = get_regulatory_correspondence_service()
    try:
        return svc.add_milestone(timeline_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put(
    "/timelines/{timeline_id}/milestones/{milestone_index}",
    response_model=RegulatoryTimeline,
    summary="Update milestone",
    description="Update a milestone within a timeline.",
)
async def update_milestone(
    timeline_id: str, milestone_index: int, payload: MilestoneUpdate
) -> RegulatoryTimeline:
    """Update a milestone."""
    svc = get_regulatory_correspondence_service()
    try:
        return svc.update_milestone(timeline_id, milestone_index, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/timelines/{timeline_id}/milestones/{milestone_index}",
    response_model=RegulatoryTimeline,
    summary="Delete milestone",
    description="Delete a milestone from a timeline.",
)
async def delete_milestone(
    timeline_id: str, milestone_index: int
) -> RegulatoryTimeline:
    """Delete a milestone from a timeline."""
    svc = get_regulatory_correspondence_service()
    try:
        return svc.delete_milestone(timeline_id, milestone_index)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Agency contacts
# ---------------------------------------------------------------------------


@router.get(
    "/contacts",
    response_model=AgencyContactListResponse,
    summary="List agency contacts",
    description="List agency contacts with optional agency filter.",
)
async def list_contacts(
    agency: Optional[RegulatoryAgency] = Query(None, description="Filter by agency"),
) -> AgencyContactListResponse:
    """List agency contacts."""
    svc = get_regulatory_correspondence_service()
    items = svc.list_contacts(agency=agency)
    return AgencyContactListResponse(items=items, total=len(items))


@router.get(
    "/contacts/{contact_id}",
    response_model=AgencyContact,
    summary="Get contact",
    description="Retrieve an agency contact.",
)
async def get_contact(contact_id: str) -> AgencyContact:
    """Get a contact by ID."""
    svc = get_regulatory_correspondence_service()
    try:
        return svc.get_contact(contact_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/contacts",
    response_model=AgencyContact,
    status_code=201,
    summary="Create contact",
    description="Create a new agency contact.",
)
async def create_contact(payload: AgencyContactCreate) -> AgencyContact:
    """Create a new agency contact."""
    svc = get_regulatory_correspondence_service()
    return svc.create_contact(payload)


@router.put(
    "/contacts/{contact_id}",
    response_model=AgencyContact,
    summary="Update contact",
    description="Update an agency contact.",
)
async def update_contact(
    contact_id: str, payload: AgencyContactUpdate
) -> AgencyContact:
    """Update a contact."""
    svc = get_regulatory_correspondence_service()
    try:
        return svc.update_contact(contact_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete(
    "/contacts/{contact_id}",
    status_code=204,
    summary="Delete contact",
    description="Delete an agency contact.",
)
async def delete_contact(contact_id: str) -> None:
    """Delete a contact."""
    svc = get_regulatory_correspondence_service()
    try:
        svc.delete_contact(contact_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Agency relationship summary
# ---------------------------------------------------------------------------


@router.get(
    "/agency/{agency}/summary",
    response_model=AgencyRelationshipSummary,
    summary="Agency relationship summary",
    description="Get relationship summary for a specific agency.",
)
async def get_agency_summary(agency: RegulatoryAgency) -> AgencyRelationshipSummary:
    """Get agency relationship summary."""
    svc = get_regulatory_correspondence_service()
    return svc.get_agency_relationship_summary(agency)
