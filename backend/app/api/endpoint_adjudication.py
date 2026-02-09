"""Clinical Endpoint Adjudication Committee (CEAC) Management API endpoints (CLINICAL-20).

Provides comprehensive adjudication operations: committee definitions & management,
member management, dual-reviewer event assignment, blinded review workflow, reviewer
assessments with confidence levels, event adjudication with tiebreaker logic,
consensus tracking, inter-rater agreement (Cohen's kappa), committee meetings,
turnaround time tracking, and adjudication metrics.

Endpoints:
    GET    /endpoint-adjudication/committees                                  - List committees
    GET    /endpoint-adjudication/committees/{committee_id}                   - Get single committee
    POST   /endpoint-adjudication/committees                                  - Create committee
    PUT    /endpoint-adjudication/committees/{committee_id}                   - Update committee
    DELETE /endpoint-adjudication/committees/{committee_id}                   - Delete committee
    GET    /endpoint-adjudication/members                                     - List all members
    GET    /endpoint-adjudication/members/{member_id}                         - Get single member
    POST   /endpoint-adjudication/committees/{committee_id}/members           - Add member to committee
    PUT    /endpoint-adjudication/members/{member_id}                         - Update member
    DELETE /endpoint-adjudication/committees/{committee_id}/members/{member_id} - Remove member
    GET    /endpoint-adjudication/events                                      - List events
    GET    /endpoint-adjudication/events/{event_id}                           - Get single event
    POST   /endpoint-adjudication/events                                      - Create event
    PUT    /endpoint-adjudication/events/{event_id}                           - Update event
    POST   /endpoint-adjudication/events/{event_id}/assign-reviewers          - Assign reviewers
    POST   /endpoint-adjudication/events/{event_id}/adjudicate                - Adjudicate event
    GET    /endpoint-adjudication/events/{event_id}/blinded                   - Get blinded event data
    GET    /endpoint-adjudication/events/consensus-required                   - Events needing consensus
    GET    /endpoint-adjudication/assessments                                 - List assessments
    GET    /endpoint-adjudication/assessments/{assessment_id}                 - Get single assessment
    POST   /endpoint-adjudication/assessments                                 - Submit assessment
    GET    /endpoint-adjudication/meetings                                    - List meetings
    GET    /endpoint-adjudication/meetings/{meeting_id}                       - Get single meeting
    POST   /endpoint-adjudication/meetings                                    - Create meeting
    GET    /endpoint-adjudication/metrics                                     - Adjudication metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.endpoint_adjudication import (
    AdjudicationCommittee,
    AdjudicationEvent,
    AdjudicationMeeting,
    AdjudicationMetrics,
    AdjudicationStatus,
    AdjudicatorRole,
    AssessmentCreate,
    AssessmentListResponse,
    BlindingStatus,
    CommitteeCreate,
    CommitteeListResponse,
    CommitteeMember,
    CommitteeUpdate,
    ConfidenceLevel,
    EndpointType,
    EventClassification,
    EventCreate,
    EventListResponse,
    EventUpdate,
    MeetingCreate,
    MeetingListResponse,
    MemberCreate,
    MemberListResponse,
    MemberUpdate,
    ReviewerAssessment,
)
from app.services.endpoint_adjudication_service import get_adjudication_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/endpoint-adjudication",
    tags=["Endpoint Adjudication"],
)


# ---------------------------------------------------------------------------
# Committee Management
# ---------------------------------------------------------------------------


@router.get(
    "/committees",
    response_model=CommitteeListResponse,
    summary="List adjudication committees",
    description="Retrieve adjudication committees with optional filtering by trial.",
)
async def list_committees(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> CommitteeListResponse:
    svc = get_adjudication_service()
    items = svc.list_committees(trial_id=trial_id)
    return CommitteeListResponse(items=items, total=len(items))


@router.get(
    "/committees/{committee_id}",
    response_model=AdjudicationCommittee,
    summary="Get an adjudication committee",
)
async def get_committee(committee_id: str) -> AdjudicationCommittee:
    svc = get_adjudication_service()
    committee = svc.get_committee(committee_id)
    if committee is None:
        raise HTTPException(status_code=404, detail=f"Committee '{committee_id}' not found")
    return committee


@router.post(
    "/committees",
    response_model=AdjudicationCommittee,
    status_code=201,
    summary="Create an adjudication committee",
)
async def create_committee(payload: CommitteeCreate) -> AdjudicationCommittee:
    svc = get_adjudication_service()
    return svc.create_committee(payload)


@router.put(
    "/committees/{committee_id}",
    response_model=AdjudicationCommittee,
    summary="Update an adjudication committee",
)
async def update_committee(
    committee_id: str, payload: CommitteeUpdate
) -> AdjudicationCommittee:
    svc = get_adjudication_service()
    updated = svc.update_committee(committee_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Committee '{committee_id}' not found")
    return updated


@router.delete(
    "/committees/{committee_id}",
    status_code=204,
    summary="Delete an adjudication committee",
)
async def delete_committee(committee_id: str) -> None:
    svc = get_adjudication_service()
    deleted = svc.delete_committee(committee_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Committee '{committee_id}' not found")


# ---------------------------------------------------------------------------
# Member Management
# ---------------------------------------------------------------------------


@router.get(
    "/members",
    response_model=MemberListResponse,
    summary="List committee members",
    description="Retrieve committee members with optional filtering by committee and role.",
)
async def list_members(
    committee_id: Optional[str] = Query(None, description="Filter by committee ID"),
    role: Optional[AdjudicatorRole] = Query(None, description="Filter by role"),
) -> MemberListResponse:
    svc = get_adjudication_service()
    items = svc.list_members(committee_id=committee_id, role=role)
    return MemberListResponse(items=items, total=len(items))


@router.get(
    "/members/{member_id}",
    response_model=CommitteeMember,
    summary="Get a committee member",
)
async def get_member(member_id: str) -> CommitteeMember:
    svc = get_adjudication_service()
    member = svc.get_member(member_id)
    if member is None:
        raise HTTPException(status_code=404, detail=f"Member '{member_id}' not found")
    return member


@router.post(
    "/committees/{committee_id}/members",
    response_model=CommitteeMember,
    status_code=201,
    summary="Add a member to a committee",
)
async def add_member_to_committee(
    committee_id: str, payload: MemberCreate
) -> CommitteeMember:
    svc = get_adjudication_service()
    member = svc.add_member_to_committee(committee_id, payload)
    if member is None:
        raise HTTPException(status_code=404, detail=f"Committee '{committee_id}' not found")
    return member


@router.put(
    "/members/{member_id}",
    response_model=CommitteeMember,
    summary="Update a committee member",
)
async def update_member(
    member_id: str, payload: MemberUpdate
) -> CommitteeMember:
    svc = get_adjudication_service()
    updated = svc.update_member(member_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Member '{member_id}' not found")
    return updated


@router.delete(
    "/committees/{committee_id}/members/{member_id}",
    status_code=204,
    summary="Remove a member from a committee",
)
async def remove_member_from_committee(
    committee_id: str, member_id: str
) -> None:
    svc = get_adjudication_service()
    removed = svc.remove_member_from_committee(committee_id, member_id)
    if not removed:
        raise HTTPException(
            status_code=404,
            detail=f"Member '{member_id}' not found in committee '{committee_id}'",
        )


# ---------------------------------------------------------------------------
# Event Management
# ---------------------------------------------------------------------------


@router.get(
    "/events",
    response_model=EventListResponse,
    summary="List adjudication events",
    description="Retrieve adjudication events with optional filtering by trial, status, type, and classification.",
)
async def list_events(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[AdjudicationStatus] = Query(None, description="Filter by status"),
    event_type: Optional[EndpointType] = Query(None, description="Filter by endpoint type"),
    classification: Optional[EventClassification] = Query(None, description="Filter by classification"),
) -> EventListResponse:
    svc = get_adjudication_service()
    items = svc.list_events(
        trial_id=trial_id, status=status, event_type=event_type,
        classification=classification,
    )
    return EventListResponse(items=items, total=len(items))


@router.get(
    "/events/consensus-required",
    response_model=EventListResponse,
    summary="Get events requiring consensus",
    description="Retrieve events where reviewers disagreed and consensus is needed.",
)
async def get_events_requiring_consensus(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> EventListResponse:
    svc = get_adjudication_service()
    items = svc.get_events_requiring_consensus(trial_id=trial_id)
    return EventListResponse(items=items, total=len(items))


@router.get(
    "/events/{event_id}",
    response_model=AdjudicationEvent,
    summary="Get an adjudication event",
)
async def get_event(event_id: str) -> AdjudicationEvent:
    svc = get_adjudication_service()
    event = svc.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")
    return event


@router.post(
    "/events",
    response_model=AdjudicationEvent,
    status_code=201,
    summary="Create an adjudication event",
)
async def create_event(payload: EventCreate) -> AdjudicationEvent:
    svc = get_adjudication_service()
    return svc.create_event(payload)


@router.put(
    "/events/{event_id}",
    response_model=AdjudicationEvent,
    summary="Update an adjudication event",
)
async def update_event(
    event_id: str, payload: EventUpdate
) -> AdjudicationEvent:
    svc = get_adjudication_service()
    updated = svc.update_event(event_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")
    return updated


@router.post(
    "/events/{event_id}/assign-reviewers",
    response_model=AdjudicationEvent,
    summary="Assign reviewers to an event",
    description="Assign dual reviewers to an event and transition to in_review status.",
)
async def assign_reviewers(
    event_id: str, reviewer_ids: list[str]
) -> AdjudicationEvent:
    svc = get_adjudication_service()
    try:
        result = svc.assign_reviewers(event_id, reviewer_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")
    return result


@router.post(
    "/events/{event_id}/adjudicate",
    response_model=AdjudicationEvent,
    summary="Adjudicate an event",
    description="Adjudicate an event based on reviewer assessments. Uses dual-reviewer "
                "consensus with tiebreaker when reviewers disagree.",
)
async def adjudicate_event(event_id: str) -> AdjudicationEvent:
    svc = get_adjudication_service()
    try:
        result = svc.adjudicate_event(event_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")
    return result


@router.get(
    "/events/{event_id}/blinded",
    summary="Get blinded event data",
    description="Retrieve event data with treatment-arm information redacted for blinded review.",
)
async def get_blinded_event(event_id: str) -> dict:
    svc = get_adjudication_service()
    result = svc.get_blinded_event(event_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Reviewer Assessments
# ---------------------------------------------------------------------------


@router.get(
    "/assessments",
    response_model=AssessmentListResponse,
    summary="List reviewer assessments",
    description="Retrieve reviewer assessments with optional filtering by event and reviewer.",
)
async def list_assessments(
    event_id: Optional[str] = Query(None, description="Filter by event ID"),
    reviewer_id: Optional[str] = Query(None, description="Filter by reviewer ID"),
) -> AssessmentListResponse:
    svc = get_adjudication_service()
    items = svc.list_assessments(event_id=event_id, reviewer_id=reviewer_id)
    return AssessmentListResponse(items=items, total=len(items))


@router.get(
    "/assessments/{assessment_id}",
    response_model=ReviewerAssessment,
    summary="Get a reviewer assessment",
)
async def get_assessment(assessment_id: str) -> ReviewerAssessment:
    svc = get_adjudication_service()
    assessment = svc.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")
    return assessment


@router.post(
    "/assessments",
    response_model=ReviewerAssessment,
    status_code=201,
    summary="Submit a reviewer assessment",
    description="Submit an individual reviewer's classification and rationale for an event.",
)
async def submit_assessment(payload: AssessmentCreate) -> ReviewerAssessment:
    svc = get_adjudication_service()
    try:
        return svc.submit_assessment(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Meetings
# ---------------------------------------------------------------------------


@router.get(
    "/meetings",
    response_model=MeetingListResponse,
    summary="List committee meetings",
    description="Retrieve committee meetings with optional filtering by committee.",
)
async def list_meetings(
    committee_id: Optional[str] = Query(None, description="Filter by committee ID"),
) -> MeetingListResponse:
    svc = get_adjudication_service()
    items = svc.list_meetings(committee_id=committee_id)
    return MeetingListResponse(items=items, total=len(items))


@router.get(
    "/meetings/{meeting_id}",
    response_model=AdjudicationMeeting,
    summary="Get a committee meeting",
)
async def get_meeting(meeting_id: str) -> AdjudicationMeeting:
    svc = get_adjudication_service()
    meeting = svc.get_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail=f"Meeting '{meeting_id}' not found")
    return meeting


@router.post(
    "/meetings",
    response_model=AdjudicationMeeting,
    status_code=201,
    summary="Create a committee meeting",
)
async def create_meeting(payload: MeetingCreate) -> AdjudicationMeeting:
    svc = get_adjudication_service()
    return svc.create_meeting(payload)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=AdjudicationMetrics,
    summary="Get adjudication metrics",
    description="Aggregated adjudication metrics including inter-rater agreement (Cohen's kappa), "
                "turnaround time, disagreement rate, and event status breakdown.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> AdjudicationMetrics:
    svc = get_adjudication_service()
    return svc.get_metrics(trial_id=trial_id)
