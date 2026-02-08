"""Regulatory Submission Tracking API endpoints (CLO-5).

Provides CRUD operations, submission workflow, milestone management,
regulatory calendar, metrics, and deadline tracking for clinical
trial regulatory submissions.

Endpoints:
    GET    /regulatory-submissions/submissions                         - List with filters
    GET    /regulatory-submissions/submissions/metrics                 - Aggregated metrics
    GET    /regulatory-submissions/submissions/calendar                - Regulatory calendar
    GET    /regulatory-submissions/submissions/information-requests    - Pending info requests
    GET    /regulatory-submissions/submissions/deadlines               - Approaching/overdue deadlines
    GET    /regulatory-submissions/submissions/{id}                    - Detail
    POST   /regulatory-submissions/submissions                         - Create
    PUT    /regulatory-submissions/submissions/{id}                    - Update
    DELETE /regulatory-submissions/submissions/{id}                    - Delete
    POST   /regulatory-submissions/submissions/{id}/submit             - Submit to regulatory body
    POST   /regulatory-submissions/submissions/{id}/record-response    - Record regulatory response
    GET    /regulatory-submissions/submissions/{id}/milestones         - List milestones
    POST   /regulatory-submissions/submissions/{id}/milestones         - Create milestone
    PUT    /regulatory-submissions/milestones/{milestone_id}           - Update milestone
    DELETE /regulatory-submissions/milestones/{milestone_id}           - Delete milestone
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.regulatory_submissions import (
    DeadlineAlert,
    MilestoneCreate,
    MilestoneListResponse,
    MilestoneUpdate,
    RecordResponseRequest,
    RegulatoryBody,
    RegulatoryCalendar,
    RegulatorySubmission,
    SubmissionCreate,
    SubmissionListResponse,
    SubmissionMetrics,
    SubmissionMilestone,
    SubmissionPriority,
    SubmissionStatus,
    SubmissionType,
    SubmissionUpdate,
)
from app.services.regulatory_submission_service import (
    get_regulatory_submission_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/regulatory-submissions",
    tags=["Regulatory Submissions"],
)


# ---------------------------------------------------------------------------
# List / filter
# ---------------------------------------------------------------------------


@router.get(
    "/submissions",
    response_model=SubmissionListResponse,
    summary="List regulatory submissions",
    description="Retrieve regulatory submissions with optional filtering.",
)
async def list_submissions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    submission_type: Optional[SubmissionType] = Query(None, description="Filter by submission type"),
    regulatory_body: Optional[RegulatoryBody] = Query(None, description="Filter by regulatory body"),
    status: Optional[SubmissionStatus] = Query(None, description="Filter by status"),
    priority: Optional[SubmissionPriority] = Query(None, description="Filter by priority"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> SubmissionListResponse:
    """List regulatory submissions with filtering and pagination."""
    svc = get_regulatory_submission_service()
    items, total = svc.list_submissions(
        trial_id=trial_id,
        submission_type=submission_type,
        regulatory_body=regulatory_body,
        status=status,
        priority=priority,
        limit=limit,
        offset=offset,
    )
    return SubmissionListResponse(items=items, total=total, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/submissions/metrics",
    response_model=SubmissionMetrics,
    summary="Submission metrics",
    description="Aggregated regulatory submission metrics.",
)
async def get_metrics() -> SubmissionMetrics:
    """Return aggregated submission metrics."""
    svc = get_regulatory_submission_service()
    return svc.get_metrics()


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------


@router.get(
    "/submissions/calendar",
    response_model=RegulatoryCalendar,
    summary="Regulatory calendar",
    description="Calendar view of upcoming, overdue, and pending deadlines.",
)
async def get_calendar() -> RegulatoryCalendar:
    """Return regulatory calendar."""
    svc = get_regulatory_submission_service()
    return svc.get_calendar()


# ---------------------------------------------------------------------------
# Information requests
# ---------------------------------------------------------------------------


@router.get(
    "/submissions/information-requests",
    response_model=list[RegulatorySubmission],
    summary="Pending information requests",
    description="Submissions with pending information requests from regulatory bodies.",
)
async def get_information_requests() -> list[RegulatorySubmission]:
    """Return submissions awaiting information."""
    svc = get_regulatory_submission_service()
    return svc.get_information_requests()


# ---------------------------------------------------------------------------
# Deadlines
# ---------------------------------------------------------------------------


@router.get(
    "/submissions/deadlines",
    response_model=list[DeadlineAlert],
    summary="Approaching and overdue deadlines",
    description="Flag milestones approaching or past their due date.",
)
async def check_deadlines(
    days_ahead: int = Query(14, ge=1, le=90, description="Days ahead to check"),
) -> list[DeadlineAlert]:
    """Return approaching and overdue deadline alerts."""
    svc = get_regulatory_submission_service()
    return svc.check_deadlines(days_ahead=days_ahead)


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------


@router.get(
    "/submissions/{submission_id}",
    response_model=RegulatorySubmission,
    summary="Get submission detail",
    description="Retrieve a single regulatory submission by ID.",
)
async def get_submission(submission_id: str) -> RegulatorySubmission:
    """Get a single submission by ID."""
    svc = get_regulatory_submission_service()
    try:
        return svc.get_submission(submission_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@router.post(
    "/submissions",
    response_model=RegulatorySubmission,
    status_code=201,
    summary="Create submission",
    description="Create a new regulatory submission.",
)
async def create_submission(payload: SubmissionCreate) -> RegulatorySubmission:
    """Create a new regulatory submission."""
    svc = get_regulatory_submission_service()
    return svc.create_submission(payload)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@router.put(
    "/submissions/{submission_id}",
    response_model=RegulatorySubmission,
    summary="Update submission",
    description="Update an existing regulatory submission.",
)
async def update_submission(
    submission_id: str, payload: SubmissionUpdate
) -> RegulatorySubmission:
    """Update an existing submission."""
    svc = get_regulatory_submission_service()
    try:
        return svc.update_submission(submission_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@router.delete(
    "/submissions/{submission_id}",
    status_code=204,
    summary="Delete submission",
    description="Delete a regulatory submission and its milestones.",
)
async def delete_submission(submission_id: str) -> None:
    """Delete a submission."""
    svc = get_regulatory_submission_service()
    try:
        svc.delete_submission(submission_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Submit workflow
# ---------------------------------------------------------------------------


@router.post(
    "/submissions/{submission_id}/submit",
    response_model=RegulatorySubmission,
    summary="Submit to regulatory body",
    description="Transition a submission to SUBMITTED status with timestamp.",
)
async def submit_submission(submission_id: str) -> RegulatorySubmission:
    """Submit a regulatory submission."""
    svc = get_regulatory_submission_service()
    try:
        return svc.submit(submission_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Record response
# ---------------------------------------------------------------------------


@router.post(
    "/submissions/{submission_id}/record-response",
    response_model=RegulatorySubmission,
    summary="Record regulatory response",
    description="Record a regulatory body's response to a submission.",
)
async def record_response(
    submission_id: str, request: RecordResponseRequest
) -> RegulatorySubmission:
    """Record a regulatory body response."""
    svc = get_regulatory_submission_service()
    try:
        return svc.record_response(submission_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Milestones: List
# ---------------------------------------------------------------------------


@router.get(
    "/submissions/{submission_id}/milestones",
    response_model=MilestoneListResponse,
    summary="List milestones",
    description="List milestones for a submission.",
)
async def list_milestones(submission_id: str) -> MilestoneListResponse:
    """List milestones for a submission."""
    svc = get_regulatory_submission_service()
    try:
        items = svc.list_milestones(submission_id)
        return MilestoneListResponse(items=items, total=len(items))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Milestones: Create
# ---------------------------------------------------------------------------


@router.post(
    "/submissions/{submission_id}/milestones",
    response_model=SubmissionMilestone,
    status_code=201,
    summary="Create milestone",
    description="Create a new milestone for a submission.",
)
async def create_milestone(
    submission_id: str, payload: MilestoneCreate
) -> SubmissionMilestone:
    """Create a milestone."""
    svc = get_regulatory_submission_service()
    try:
        return svc.create_milestone(submission_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Milestones: Update
# ---------------------------------------------------------------------------


@router.put(
    "/milestones/{milestone_id}",
    response_model=SubmissionMilestone,
    summary="Update milestone",
    description="Update an existing milestone.",
)
async def update_milestone(
    milestone_id: str, payload: MilestoneUpdate
) -> SubmissionMilestone:
    """Update a milestone."""
    svc = get_regulatory_submission_service()
    try:
        return svc.update_milestone(milestone_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Milestones: Delete
# ---------------------------------------------------------------------------


@router.delete(
    "/milestones/{milestone_id}",
    status_code=204,
    summary="Delete milestone",
    description="Delete a milestone.",
)
async def delete_milestone(milestone_id: str) -> None:
    """Delete a milestone."""
    svc = get_regulatory_submission_service()
    try:
        svc.delete_milestone(milestone_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
