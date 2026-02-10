"""DSMB (Data Safety Monitoring Board) Management API endpoints.

Provides comprehensive DSMB operations: charter management, member tracking,
meeting lifecycle, safety review workflows, recommendation voting with records,
unblinding request processing, quorum validation, and operational metrics.

Endpoints:
    GET    /dsmb/charters                                     - List charters
    GET    /dsmb/charters/{charter_id}                        - Get single charter
    POST   /dsmb/charters                                     - Create charter
    PUT    /dsmb/charters/{charter_id}                        - Update charter
    DELETE /dsmb/charters/{charter_id}                        - Delete charter
    GET    /dsmb/members                                      - List members
    GET    /dsmb/members/{member_id}                          - Get single member
    POST   /dsmb/members                                      - Create member
    PUT    /dsmb/members/{member_id}                          - Update member
    DELETE /dsmb/members/{member_id}                          - Delete member
    GET    /dsmb/meetings                                     - List meetings
    GET    /dsmb/meetings/{meeting_id}                        - Get single meeting
    POST   /dsmb/meetings                                     - Schedule meeting
    PUT    /dsmb/meetings/{meeting_id}                        - Update meeting
    DELETE /dsmb/meetings/{meeting_id}                        - Delete meeting
    GET    /dsmb/meetings/{meeting_id}/quorum                 - Check quorum
    GET    /dsmb/safety-reviews                               - List safety reviews
    GET    /dsmb/safety-reviews/{review_id}                   - Get single safety review
    POST   /dsmb/safety-reviews                               - Conduct safety review
    PUT    /dsmb/safety-reviews/{review_id}                   - Update safety review
    DELETE /dsmb/safety-reviews/{review_id}                   - Delete safety review
    GET    /dsmb/recommendations                              - List recommendations
    GET    /dsmb/recommendations/{recommendation_id}          - Get single recommendation
    POST   /dsmb/recommendations                              - Record recommendation
    PUT    /dsmb/recommendations/{recommendation_id}          - Update recommendation
    DELETE /dsmb/recommendations/{recommendation_id}          - Delete recommendation
    GET    /dsmb/unblinding-requests                           - List unblinding requests
    GET    /dsmb/unblinding-requests/{request_id}              - Get single unblinding request
    POST   /dsmb/unblinding-requests                           - Create unblinding request
    PUT    /dsmb/unblinding-requests/{request_id}              - Update unblinding request
    DELETE /dsmb/unblinding-requests/{request_id}              - Delete unblinding request
    GET    /dsmb/metrics                                      - DSMB metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.dsmb_management import (
    DSMBCharter,
    DSMBCharterCreate,
    DSMBCharterListResponse,
    DSMBCharterUpdate,
    DSMBMeeting,
    DSMBMeetingCreate,
    DSMBMeetingListResponse,
    DSMBMeetingUpdate,
    DSMBMember,
    DSMBMemberCreate,
    DSMBMemberListResponse,
    DSMBMemberUpdate,
    DSMBMetrics,
    DSMBRecommendation,
    DSMBRecommendationCreate,
    DSMBRecommendationListResponse,
    DSMBRecommendationUpdate,
    MeetingStatus,
    MeetingType,
    MemberRole,
    QuorumCheckResult,
    RecommendationType,
    SafetyReview,
    SafetyReviewCreate,
    SafetyReviewListResponse,
    SafetyReviewUpdate,
    UnblindingRequest,
    UnblindingRequestCreate,
    UnblindingRequestListResponse,
    UnblindingRequestUpdate,
    UnblindingStatus,
)
from app.services.dsmb_management_service import get_dsmb_management_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/dsmb",
    tags=["DSMB Management"],
)


# ---------------------------------------------------------------------------
# Charter Management
# ---------------------------------------------------------------------------


@router.get(
    "/charters",
    response_model=DSMBCharterListResponse,
    summary="List DSMB charters",
    description="Retrieve DSMB charters with optional filtering by trial.",
)
async def list_charters(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> DSMBCharterListResponse:
    svc = get_dsmb_management_service()
    items = svc.list_charters(trial_id=trial_id)
    return DSMBCharterListResponse(items=items, total=len(items))


@router.get(
    "/charters/{charter_id}",
    response_model=DSMBCharter,
    summary="Get a DSMB charter",
)
async def get_charter(charter_id: str) -> DSMBCharter:
    svc = get_dsmb_management_service()
    charter = svc.get_charter(charter_id)
    if charter is None:
        raise HTTPException(status_code=404, detail=f"Charter '{charter_id}' not found")
    return charter


@router.post(
    "/charters",
    response_model=DSMBCharter,
    status_code=201,
    summary="Create a DSMB charter",
)
async def create_charter(payload: DSMBCharterCreate) -> DSMBCharter:
    svc = get_dsmb_management_service()
    return svc.create_charter(payload)


@router.put(
    "/charters/{charter_id}",
    response_model=DSMBCharter,
    summary="Update a DSMB charter",
)
async def update_charter(charter_id: str, payload: DSMBCharterUpdate) -> DSMBCharter:
    svc = get_dsmb_management_service()
    updated = svc.update_charter(charter_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Charter '{charter_id}' not found")
    return updated


@router.delete(
    "/charters/{charter_id}",
    status_code=204,
    summary="Delete a DSMB charter",
)
async def delete_charter(charter_id: str) -> None:
    svc = get_dsmb_management_service()
    deleted = svc.delete_charter(charter_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Charter '{charter_id}' not found")


# ---------------------------------------------------------------------------
# Member Management
# ---------------------------------------------------------------------------


@router.get(
    "/members",
    response_model=DSMBMemberListResponse,
    summary="List DSMB members",
    description="Retrieve DSMB members with optional filtering by charter, role, and active status.",
)
async def list_members(
    charter_id: Optional[str] = Query(None, description="Filter by charter ID"),
    role: Optional[MemberRole] = Query(None, description="Filter by member role"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
) -> DSMBMemberListResponse:
    svc = get_dsmb_management_service()
    items = svc.list_members(charter_id=charter_id, role=role, active=active)
    return DSMBMemberListResponse(items=items, total=len(items))


@router.get(
    "/members/{member_id}",
    response_model=DSMBMember,
    summary="Get a DSMB member",
)
async def get_member(member_id: str) -> DSMBMember:
    svc = get_dsmb_management_service()
    member = svc.get_member(member_id)
    if member is None:
        raise HTTPException(status_code=404, detail=f"Member '{member_id}' not found")
    return member


@router.post(
    "/members",
    response_model=DSMBMember,
    status_code=201,
    summary="Create a DSMB member",
)
async def create_member(payload: DSMBMemberCreate) -> DSMBMember:
    svc = get_dsmb_management_service()
    try:
        return svc.create_member(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/members/{member_id}",
    response_model=DSMBMember,
    summary="Update a DSMB member",
)
async def update_member(member_id: str, payload: DSMBMemberUpdate) -> DSMBMember:
    svc = get_dsmb_management_service()
    updated = svc.update_member(member_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Member '{member_id}' not found")
    return updated


@router.delete(
    "/members/{member_id}",
    status_code=204,
    summary="Delete a DSMB member",
)
async def delete_member(member_id: str) -> None:
    svc = get_dsmb_management_service()
    deleted = svc.delete_member(member_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Member '{member_id}' not found")


# ---------------------------------------------------------------------------
# Meeting Management
# ---------------------------------------------------------------------------


@router.get(
    "/meetings",
    response_model=DSMBMeetingListResponse,
    summary="List DSMB meetings",
    description="Retrieve DSMB meetings with optional filtering by charter, trial, status, and type.",
)
async def list_meetings(
    charter_id: Optional[str] = Query(None, description="Filter by charter ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[MeetingStatus] = Query(None, description="Filter by meeting status"),
    meeting_type: Optional[MeetingType] = Query(None, description="Filter by meeting type"),
) -> DSMBMeetingListResponse:
    svc = get_dsmb_management_service()
    items = svc.list_meetings(
        charter_id=charter_id, trial_id=trial_id, status=status, meeting_type=meeting_type
    )
    return DSMBMeetingListResponse(items=items, total=len(items))


@router.get(
    "/meetings/{meeting_id}",
    response_model=DSMBMeeting,
    summary="Get a DSMB meeting",
)
async def get_meeting(meeting_id: str) -> DSMBMeeting:
    svc = get_dsmb_management_service()
    meeting = svc.get_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail=f"Meeting '{meeting_id}' not found")
    return meeting


@router.post(
    "/meetings",
    response_model=DSMBMeeting,
    status_code=201,
    summary="Schedule a DSMB meeting",
    description="Schedule a new DSMB meeting. The meeting will be created with status 'scheduled'.",
)
async def schedule_meeting(payload: DSMBMeetingCreate) -> DSMBMeeting:
    svc = get_dsmb_management_service()
    try:
        return svc.schedule_meeting(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/meetings/{meeting_id}",
    response_model=DSMBMeeting,
    summary="Update a DSMB meeting",
    description="Update meeting details including status, attendees, and minutes.",
)
async def update_meeting(meeting_id: str, payload: DSMBMeetingUpdate) -> DSMBMeeting:
    svc = get_dsmb_management_service()
    updated = svc.update_meeting(meeting_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Meeting '{meeting_id}' not found")
    return updated


@router.delete(
    "/meetings/{meeting_id}",
    status_code=204,
    summary="Delete a DSMB meeting",
)
async def delete_meeting(meeting_id: str) -> None:
    svc = get_dsmb_management_service()
    deleted = svc.delete_meeting(meeting_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Meeting '{meeting_id}' not found")


@router.get(
    "/meetings/{meeting_id}/quorum",
    response_model=QuorumCheckResult,
    summary="Check meeting quorum",
    description="Check whether quorum requirements are met for a DSMB meeting. "
                "Quorum requires minimum attendees and representation of Chair, Statistician, and Clinician roles.",
)
async def check_quorum(meeting_id: str) -> QuorumCheckResult:
    svc = get_dsmb_management_service()
    result = svc.check_quorum(meeting_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Meeting '{meeting_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Safety Reviews
# ---------------------------------------------------------------------------


@router.get(
    "/safety-reviews",
    response_model=SafetyReviewListResponse,
    summary="List safety reviews",
    description="Retrieve safety reviews with optional filtering by meeting.",
)
async def list_safety_reviews(
    meeting_id: Optional[str] = Query(None, description="Filter by meeting ID"),
) -> SafetyReviewListResponse:
    svc = get_dsmb_management_service()
    items = svc.list_safety_reviews(meeting_id=meeting_id)
    return SafetyReviewListResponse(items=items, total=len(items))


@router.get(
    "/safety-reviews/{review_id}",
    response_model=SafetyReview,
    summary="Get a safety review",
)
async def get_safety_review(review_id: str) -> SafetyReview:
    svc = get_dsmb_management_service()
    review = svc.get_safety_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail=f"Safety review '{review_id}' not found")
    return review


@router.post(
    "/safety-reviews",
    response_model=SafetyReview,
    status_code=201,
    summary="Conduct a safety review",
    description="Create a safety review record for a DSMB meeting with AE/SAE/mortality summaries.",
)
async def conduct_safety_review(payload: SafetyReviewCreate) -> SafetyReview:
    svc = get_dsmb_management_service()
    try:
        return svc.conduct_safety_review(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/safety-reviews/{review_id}",
    response_model=SafetyReview,
    summary="Update a safety review",
)
async def update_safety_review(review_id: str, payload: SafetyReviewUpdate) -> SafetyReview:
    svc = get_dsmb_management_service()
    updated = svc.update_safety_review(review_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Safety review '{review_id}' not found")
    return updated


@router.delete(
    "/safety-reviews/{review_id}",
    status_code=204,
    summary="Delete a safety review",
)
async def delete_safety_review(review_id: str) -> None:
    svc = get_dsmb_management_service()
    deleted = svc.delete_safety_review(review_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Safety review '{review_id}' not found")


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


@router.get(
    "/recommendations",
    response_model=DSMBRecommendationListResponse,
    summary="List DSMB recommendations",
    description="Retrieve DSMB recommendations with optional filtering by meeting and type.",
)
async def list_recommendations(
    meeting_id: Optional[str] = Query(None, description="Filter by meeting ID"),
    recommendation_type: Optional[RecommendationType] = Query(
        None, description="Filter by recommendation type"
    ),
) -> DSMBRecommendationListResponse:
    svc = get_dsmb_management_service()
    items = svc.list_recommendations(
        meeting_id=meeting_id, recommendation_type=recommendation_type
    )
    return DSMBRecommendationListResponse(items=items, total=len(items))


@router.get(
    "/recommendations/{recommendation_id}",
    response_model=DSMBRecommendation,
    summary="Get a DSMB recommendation",
)
async def get_recommendation(recommendation_id: str) -> DSMBRecommendation:
    svc = get_dsmb_management_service()
    rec = svc.get_recommendation(recommendation_id)
    if rec is None:
        raise HTTPException(
            status_code=404, detail=f"Recommendation '{recommendation_id}' not found"
        )
    return rec


@router.post(
    "/recommendations",
    response_model=DSMBRecommendation,
    status_code=201,
    summary="Record a DSMB recommendation",
    description="Record a new DSMB recommendation with voting results.",
)
async def record_recommendation(payload: DSMBRecommendationCreate) -> DSMBRecommendation:
    svc = get_dsmb_management_service()
    try:
        return svc.record_recommendation(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/recommendations/{recommendation_id}",
    response_model=DSMBRecommendation,
    summary="Update a DSMB recommendation",
    description="Update recommendation details including sponsor communication and response.",
)
async def update_recommendation(
    recommendation_id: str, payload: DSMBRecommendationUpdate
) -> DSMBRecommendation:
    svc = get_dsmb_management_service()
    updated = svc.update_recommendation(recommendation_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Recommendation '{recommendation_id}' not found"
        )
    return updated


@router.delete(
    "/recommendations/{recommendation_id}",
    status_code=204,
    summary="Delete a DSMB recommendation",
)
async def delete_recommendation(recommendation_id: str) -> None:
    svc = get_dsmb_management_service()
    deleted = svc.delete_recommendation(recommendation_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Recommendation '{recommendation_id}' not found"
        )


# ---------------------------------------------------------------------------
# Unblinding Requests
# ---------------------------------------------------------------------------


@router.get(
    "/unblinding-requests",
    response_model=UnblindingRequestListResponse,
    summary="List unblinding requests",
    description="Retrieve unblinding requests with optional filtering by trial and status.",
)
async def list_unblinding_requests(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[UnblindingStatus] = Query(None, description="Filter by status"),
) -> UnblindingRequestListResponse:
    svc = get_dsmb_management_service()
    items = svc.list_unblinding_requests(trial_id=trial_id, status=status)
    return UnblindingRequestListResponse(items=items, total=len(items))


@router.get(
    "/unblinding-requests/{request_id}",
    response_model=UnblindingRequest,
    summary="Get an unblinding request",
)
async def get_unblinding_request(request_id: str) -> UnblindingRequest:
    svc = get_dsmb_management_service()
    request = svc.get_unblinding_request(request_id)
    if request is None:
        raise HTTPException(
            status_code=404, detail=f"Unblinding request '{request_id}' not found"
        )
    return request


@router.post(
    "/unblinding-requests",
    response_model=UnblindingRequest,
    status_code=201,
    summary="Create an unblinding request",
    description="Submit a new unblinding request with justification and scope.",
)
async def request_unblinding(payload: UnblindingRequestCreate) -> UnblindingRequest:
    svc = get_dsmb_management_service()
    return svc.request_unblinding(payload)


@router.put(
    "/unblinding-requests/{request_id}",
    response_model=UnblindingRequest,
    summary="Update an unblinding request",
    description="Update an unblinding request including approval, denial, or completion.",
)
async def update_unblinding_request(
    request_id: str, payload: UnblindingRequestUpdate
) -> UnblindingRequest:
    svc = get_dsmb_management_service()
    updated = svc.update_unblinding_request(request_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Unblinding request '{request_id}' not found"
        )
    return updated


@router.delete(
    "/unblinding-requests/{request_id}",
    status_code=204,
    summary="Delete an unblinding request",
)
async def delete_unblinding_request(request_id: str) -> None:
    svc = get_dsmb_management_service()
    deleted = svc.delete_unblinding_request(request_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Unblinding request '{request_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=DSMBMetrics,
    summary="Get DSMB metrics",
    description="Aggregated DSMB operational metrics across all charters and trials.",
)
async def get_metrics() -> DSMBMetrics:
    svc = get_dsmb_management_service()
    return svc.get_metrics()
