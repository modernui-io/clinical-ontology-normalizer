"""Cross-Functional Team Management API endpoints (CFT-MGT).

Provides comprehensive cross-functional team operations: team formation,
role assignments, meeting cadence records, deliverable tracking,
performance reviews, and team metrics.

Endpoints:
    GET    /cross-functional-team/team-formations                       - List team formations
    GET    /cross-functional-team/team-formations/{team_id}             - Get single team
    POST   /cross-functional-team/team-formations                       - Create team
    PUT    /cross-functional-team/team-formations/{team_id}             - Update team
    DELETE /cross-functional-team/team-formations/{team_id}             - Delete team
    GET    /cross-functional-team/role-assignments                      - List role assignments
    GET    /cross-functional-team/role-assignments/{assignment_id}      - Get single assignment
    POST   /cross-functional-team/role-assignments                      - Create assignment
    PUT    /cross-functional-team/role-assignments/{assignment_id}      - Update assignment
    DELETE /cross-functional-team/role-assignments/{assignment_id}      - Delete assignment
    GET    /cross-functional-team/meeting-cadence-records               - List meeting records
    GET    /cross-functional-team/meeting-cadence-records/{record_id}   - Get single record
    POST   /cross-functional-team/meeting-cadence-records               - Create record
    PUT    /cross-functional-team/meeting-cadence-records/{record_id}   - Update record
    DELETE /cross-functional-team/meeting-cadence-records/{record_id}   - Delete record
    GET    /cross-functional-team/deliverable-trackers                  - List deliverables
    GET    /cross-functional-team/deliverable-trackers/{deliverable_id} - Get single deliverable
    POST   /cross-functional-team/deliverable-trackers                  - Create deliverable
    PUT    /cross-functional-team/deliverable-trackers/{deliverable_id} - Update deliverable
    DELETE /cross-functional-team/deliverable-trackers/{deliverable_id} - Delete deliverable
    GET    /cross-functional-team/performance-reviews                   - List reviews
    GET    /cross-functional-team/performance-reviews/{review_id}       - Get single review
    POST   /cross-functional-team/performance-reviews                   - Create review
    PUT    /cross-functional-team/performance-reviews/{review_id}       - Update review
    DELETE /cross-functional-team/performance-reviews/{review_id}       - Delete review
    GET    /cross-functional-team/metrics                               - Team metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.cross_functional_team import (
    CrossFunctionalTeamMetrics,
    DeliverableStatus,
    DeliverableTracker,
    DeliverableTrackerCreate,
    DeliverableTrackerListResponse,
    DeliverableTrackerUpdate,
    FunctionalRole,
    MeetingCadence,
    MeetingCadenceRecord,
    MeetingCadenceRecordCreate,
    MeetingCadenceRecordListResponse,
    MeetingCadenceRecordUpdate,
    PerformanceReview,
    PerformanceReviewCreate,
    PerformanceReviewListResponse,
    PerformanceReviewUpdate,
    RoleAssignment,
    RoleAssignmentCreate,
    RoleAssignmentListResponse,
    RoleAssignmentUpdate,
    TeamFormation,
    TeamFormationCreate,
    TeamFormationListResponse,
    TeamFormationUpdate,
    TeamStatus,
    TeamType,
)
from app.services.cross_functional_team_service import get_cross_functional_team_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/cross-functional-team",
    tags=["Cross-Functional Team"],
)


# ---------------------------------------------------------------------------
# Team Formations
# ---------------------------------------------------------------------------


@router.get(
    "/team-formations",
    response_model=TeamFormationListResponse,
    summary="List team formations",
    description="Retrieve team formations with optional filtering by trial, type, and status.",
)
async def list_team_formations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    team_type: Optional[TeamType] = Query(None, description="Filter by team type"),
    status: Optional[TeamStatus] = Query(None, description="Filter by team status"),
) -> TeamFormationListResponse:
    svc = get_cross_functional_team_service()
    items = svc.list_team_formations(trial_id=trial_id, team_type=team_type, status=status)
    return TeamFormationListResponse(items=items, total=len(items))


@router.get(
    "/team-formations/{team_id}",
    response_model=TeamFormation,
    summary="Get a team formation",
)
async def get_team_formation(team_id: str) -> TeamFormation:
    svc = get_cross_functional_team_service()
    team = svc.get_team_formation(team_id)
    if team is None:
        raise HTTPException(status_code=404, detail=f"Team formation '{team_id}' not found")
    return team


@router.post(
    "/team-formations",
    response_model=TeamFormation,
    status_code=201,
    summary="Create a team formation",
)
async def create_team_formation(payload: TeamFormationCreate) -> TeamFormation:
    svc = get_cross_functional_team_service()
    return svc.create_team_formation(payload)


@router.put(
    "/team-formations/{team_id}",
    response_model=TeamFormation,
    summary="Update a team formation",
)
async def update_team_formation(
    team_id: str, payload: TeamFormationUpdate
) -> TeamFormation:
    svc = get_cross_functional_team_service()
    updated = svc.update_team_formation(team_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Team formation '{team_id}' not found")
    return updated


@router.delete(
    "/team-formations/{team_id}",
    status_code=204,
    summary="Delete a team formation",
)
async def delete_team_formation(team_id: str) -> None:
    svc = get_cross_functional_team_service()
    deleted = svc.delete_team_formation(team_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Team formation '{team_id}' not found")


# ---------------------------------------------------------------------------
# Role Assignments
# ---------------------------------------------------------------------------


@router.get(
    "/role-assignments",
    response_model=RoleAssignmentListResponse,
    summary="List role assignments",
    description="Retrieve role assignments with optional filtering by trial, team, and role.",
)
async def list_role_assignments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    functional_role: Optional[FunctionalRole] = Query(None, description="Filter by functional role"),
) -> RoleAssignmentListResponse:
    svc = get_cross_functional_team_service()
    items = svc.list_role_assignments(
        trial_id=trial_id, team_id=team_id, functional_role=functional_role
    )
    return RoleAssignmentListResponse(items=items, total=len(items))


@router.get(
    "/role-assignments/{assignment_id}",
    response_model=RoleAssignment,
    summary="Get a role assignment",
)
async def get_role_assignment(assignment_id: str) -> RoleAssignment:
    svc = get_cross_functional_team_service()
    assignment = svc.get_role_assignment(assignment_id)
    if assignment is None:
        raise HTTPException(
            status_code=404, detail=f"Role assignment '{assignment_id}' not found"
        )
    return assignment


@router.post(
    "/role-assignments",
    response_model=RoleAssignment,
    status_code=201,
    summary="Create a role assignment",
)
async def create_role_assignment(payload: RoleAssignmentCreate) -> RoleAssignment:
    svc = get_cross_functional_team_service()
    return svc.create_role_assignment(payload)


@router.put(
    "/role-assignments/{assignment_id}",
    response_model=RoleAssignment,
    summary="Update a role assignment",
)
async def update_role_assignment(
    assignment_id: str, payload: RoleAssignmentUpdate
) -> RoleAssignment:
    svc = get_cross_functional_team_service()
    updated = svc.update_role_assignment(assignment_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Role assignment '{assignment_id}' not found"
        )
    return updated


@router.delete(
    "/role-assignments/{assignment_id}",
    status_code=204,
    summary="Delete a role assignment",
)
async def delete_role_assignment(assignment_id: str) -> None:
    svc = get_cross_functional_team_service()
    deleted = svc.delete_role_assignment(assignment_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Role assignment '{assignment_id}' not found"
        )


# ---------------------------------------------------------------------------
# Meeting Cadence Records
# ---------------------------------------------------------------------------


@router.get(
    "/meeting-cadence-records",
    response_model=MeetingCadenceRecordListResponse,
    summary="List meeting cadence records",
    description="Retrieve meeting cadence records with optional filtering by trial, team, and cadence.",
)
async def list_meeting_cadence_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    cadence: Optional[MeetingCadence] = Query(None, description="Filter by cadence"),
) -> MeetingCadenceRecordListResponse:
    svc = get_cross_functional_team_service()
    items = svc.list_meeting_cadence_records(
        trial_id=trial_id, team_id=team_id, cadence=cadence
    )
    return MeetingCadenceRecordListResponse(items=items, total=len(items))


@router.get(
    "/meeting-cadence-records/{record_id}",
    response_model=MeetingCadenceRecord,
    summary="Get a meeting cadence record",
)
async def get_meeting_cadence_record(record_id: str) -> MeetingCadenceRecord:
    svc = get_cross_functional_team_service()
    record = svc.get_meeting_cadence_record(record_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Meeting cadence record '{record_id}' not found"
        )
    return record


@router.post(
    "/meeting-cadence-records",
    response_model=MeetingCadenceRecord,
    status_code=201,
    summary="Create a meeting cadence record",
)
async def create_meeting_cadence_record(
    payload: MeetingCadenceRecordCreate,
) -> MeetingCadenceRecord:
    svc = get_cross_functional_team_service()
    return svc.create_meeting_cadence_record(payload)


@router.put(
    "/meeting-cadence-records/{record_id}",
    response_model=MeetingCadenceRecord,
    summary="Update a meeting cadence record",
)
async def update_meeting_cadence_record(
    record_id: str, payload: MeetingCadenceRecordUpdate
) -> MeetingCadenceRecord:
    svc = get_cross_functional_team_service()
    updated = svc.update_meeting_cadence_record(record_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Meeting cadence record '{record_id}' not found"
        )
    return updated


@router.delete(
    "/meeting-cadence-records/{record_id}",
    status_code=204,
    summary="Delete a meeting cadence record",
)
async def delete_meeting_cadence_record(record_id: str) -> None:
    svc = get_cross_functional_team_service()
    deleted = svc.delete_meeting_cadence_record(record_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Meeting cadence record '{record_id}' not found"
        )


# ---------------------------------------------------------------------------
# Deliverable Trackers
# ---------------------------------------------------------------------------


@router.get(
    "/deliverable-trackers",
    response_model=DeliverableTrackerListResponse,
    summary="List deliverable trackers",
    description="Retrieve deliverable trackers with optional filtering by trial, team, and status.",
)
async def list_deliverable_trackers(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
    status: Optional[DeliverableStatus] = Query(None, description="Filter by status"),
) -> DeliverableTrackerListResponse:
    svc = get_cross_functional_team_service()
    items = svc.list_deliverable_trackers(trial_id=trial_id, team_id=team_id, status=status)
    return DeliverableTrackerListResponse(items=items, total=len(items))


@router.get(
    "/deliverable-trackers/{deliverable_id}",
    response_model=DeliverableTracker,
    summary="Get a deliverable tracker",
)
async def get_deliverable_tracker(deliverable_id: str) -> DeliverableTracker:
    svc = get_cross_functional_team_service()
    deliverable = svc.get_deliverable_tracker(deliverable_id)
    if deliverable is None:
        raise HTTPException(
            status_code=404,
            detail=f"Deliverable tracker '{deliverable_id}' not found",
        )
    return deliverable


@router.post(
    "/deliverable-trackers",
    response_model=DeliverableTracker,
    status_code=201,
    summary="Create a deliverable tracker",
)
async def create_deliverable_tracker(payload: DeliverableTrackerCreate) -> DeliverableTracker:
    svc = get_cross_functional_team_service()
    return svc.create_deliverable_tracker(payload)


@router.put(
    "/deliverable-trackers/{deliverable_id}",
    response_model=DeliverableTracker,
    summary="Update a deliverable tracker",
)
async def update_deliverable_tracker(
    deliverable_id: str, payload: DeliverableTrackerUpdate
) -> DeliverableTracker:
    svc = get_cross_functional_team_service()
    updated = svc.update_deliverable_tracker(deliverable_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Deliverable tracker '{deliverable_id}' not found",
        )
    return updated


@router.delete(
    "/deliverable-trackers/{deliverable_id}",
    status_code=204,
    summary="Delete a deliverable tracker",
)
async def delete_deliverable_tracker(deliverable_id: str) -> None:
    svc = get_cross_functional_team_service()
    deleted = svc.delete_deliverable_tracker(deliverable_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Deliverable tracker '{deliverable_id}' not found",
        )


# ---------------------------------------------------------------------------
# Performance Reviews
# ---------------------------------------------------------------------------


@router.get(
    "/performance-reviews",
    response_model=PerformanceReviewListResponse,
    summary="List performance reviews",
    description="Retrieve performance reviews with optional filtering by trial and team.",
)
async def list_performance_reviews(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    team_id: Optional[str] = Query(None, description="Filter by team ID"),
) -> PerformanceReviewListResponse:
    svc = get_cross_functional_team_service()
    items = svc.list_performance_reviews(trial_id=trial_id, team_id=team_id)
    return PerformanceReviewListResponse(items=items, total=len(items))


@router.get(
    "/performance-reviews/{review_id}",
    response_model=PerformanceReview,
    summary="Get a performance review",
)
async def get_performance_review(review_id: str) -> PerformanceReview:
    svc = get_cross_functional_team_service()
    review = svc.get_performance_review(review_id)
    if review is None:
        raise HTTPException(
            status_code=404, detail=f"Performance review '{review_id}' not found"
        )
    return review


@router.post(
    "/performance-reviews",
    response_model=PerformanceReview,
    status_code=201,
    summary="Create a performance review",
)
async def create_performance_review(payload: PerformanceReviewCreate) -> PerformanceReview:
    svc = get_cross_functional_team_service()
    return svc.create_performance_review(payload)


@router.put(
    "/performance-reviews/{review_id}",
    response_model=PerformanceReview,
    summary="Update a performance review",
)
async def update_performance_review(
    review_id: str, payload: PerformanceReviewUpdate
) -> PerformanceReview:
    svc = get_cross_functional_team_service()
    updated = svc.update_performance_review(review_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Performance review '{review_id}' not found"
        )
    return updated


@router.delete(
    "/performance-reviews/{review_id}",
    status_code=204,
    summary="Delete a performance review",
)
async def delete_performance_review(review_id: str) -> None:
    svc = get_cross_functional_team_service()
    deleted = svc.delete_performance_review(review_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Performance review '{review_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=CrossFunctionalTeamMetrics,
    summary="Get cross-functional team metrics",
    description="Aggregated metrics across all cross-functional team operations.",
)
async def get_metrics() -> CrossFunctionalTeamMetrics:
    svc = get_cross_functional_team_service()
    return svc.get_metrics()
