"""Clinical Event Adjudication API endpoints (CEA-ADJ).

Provides comprehensive clinical event adjudication operations: event submissions,
adjudicator assignments, adjudication decision records, consensus reviews, and
adjudication metrics.

Endpoints:
    GET    /clinical-event-adjudication/event-submissions                          - List event submissions
    GET    /clinical-event-adjudication/event-submissions/{submission_id}           - Get single submission
    POST   /clinical-event-adjudication/event-submissions                          - Create submission
    PUT    /clinical-event-adjudication/event-submissions/{submission_id}           - Update submission
    DELETE /clinical-event-adjudication/event-submissions/{submission_id}           - Delete submission
    GET    /clinical-event-adjudication/adjudicator-assignments                    - List assignments
    GET    /clinical-event-adjudication/adjudicator-assignments/{assignment_id}     - Get single assignment
    POST   /clinical-event-adjudication/adjudicator-assignments                    - Create assignment
    PUT    /clinical-event-adjudication/adjudicator-assignments/{assignment_id}     - Update assignment
    DELETE /clinical-event-adjudication/adjudicator-assignments/{assignment_id}     - Delete assignment
    GET    /clinical-event-adjudication/adjudication-decisions                     - List decisions
    GET    /clinical-event-adjudication/adjudication-decisions/{decision_id}        - Get single decision
    POST   /clinical-event-adjudication/adjudication-decisions                     - Create decision
    PUT    /clinical-event-adjudication/adjudication-decisions/{decision_id}        - Update decision
    DELETE /clinical-event-adjudication/adjudication-decisions/{decision_id}        - Delete decision
    GET    /clinical-event-adjudication/consensus-reviews                          - List consensus reviews
    GET    /clinical-event-adjudication/consensus-reviews/{consensus_id}            - Get single consensus
    POST   /clinical-event-adjudication/consensus-reviews                          - Create consensus
    PUT    /clinical-event-adjudication/consensus-reviews/{consensus_id}            - Update consensus
    DELETE /clinical-event-adjudication/consensus-reviews/{consensus_id}            - Delete consensus
    GET    /clinical-event-adjudication/metrics                                    - Adjudication metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.clinical_event_adjudication import (
    AdjudicationDecision,
    AdjudicationDecisionRecord,
    AdjudicationDecisionRecordCreate,
    AdjudicationDecisionRecordListResponse,
    AdjudicationDecisionRecordUpdate,
    AdjudicatorAssignment,
    AdjudicatorAssignmentCreate,
    AdjudicatorAssignmentListResponse,
    AdjudicatorAssignmentUpdate,
    AdjudicatorRole,
    ClinicalEventAdjudicationMetrics,
    ConsensusOutcome,
    ConsensusReview,
    ConsensusReviewCreate,
    ConsensusReviewListResponse,
    ConsensusReviewUpdate,
    EventCategory,
    EventStatus,
    EventSubmission,
    EventSubmissionCreate,
    EventSubmissionListResponse,
    EventSubmissionUpdate,
)
from app.services.clinical_event_adjudication_service import (
    get_clinical_event_adjudication_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/clinical-event-adjudication",
    tags=["Clinical Event Adjudication"],
)


# ---------------------------------------------------------------------------
# Event Submissions
# ---------------------------------------------------------------------------


@router.get(
    "/event-submissions",
    response_model=EventSubmissionListResponse,
    summary="List event submissions",
    description="Retrieve event submissions with optional filtering by trial, category, and status.",
)
async def list_event_submissions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    event_category: Optional[EventCategory] = Query(None, description="Filter by event category"),
    event_status: Optional[EventStatus] = Query(None, description="Filter by event status"),
) -> EventSubmissionListResponse:
    svc = get_clinical_event_adjudication_service()
    items = svc.list_event_submissions(
        trial_id=trial_id, event_category=event_category, event_status=event_status
    )
    return EventSubmissionListResponse(items=items, total=len(items))


@router.get(
    "/event-submissions/{submission_id}",
    response_model=EventSubmission,
    summary="Get an event submission",
)
async def get_event_submission(submission_id: str) -> EventSubmission:
    svc = get_clinical_event_adjudication_service()
    record = svc.get_event_submission(submission_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Event submission '{submission_id}' not found"
        )
    return record


@router.post(
    "/event-submissions",
    response_model=EventSubmission,
    status_code=201,
    summary="Create an event submission",
)
async def create_event_submission(payload: EventSubmissionCreate) -> EventSubmission:
    svc = get_clinical_event_adjudication_service()
    return svc.create_event_submission(payload)


@router.put(
    "/event-submissions/{submission_id}",
    response_model=EventSubmission,
    summary="Update an event submission",
)
async def update_event_submission(
    submission_id: str, payload: EventSubmissionUpdate
) -> EventSubmission:
    svc = get_clinical_event_adjudication_service()
    updated = svc.update_event_submission(submission_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Event submission '{submission_id}' not found"
        )
    return updated


@router.delete(
    "/event-submissions/{submission_id}",
    status_code=204,
    summary="Delete an event submission",
)
async def delete_event_submission(submission_id: str) -> None:
    svc = get_clinical_event_adjudication_service()
    deleted = svc.delete_event_submission(submission_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Event submission '{submission_id}' not found"
        )


# ---------------------------------------------------------------------------
# Adjudicator Assignments
# ---------------------------------------------------------------------------


@router.get(
    "/adjudicator-assignments",
    response_model=AdjudicatorAssignmentListResponse,
    summary="List adjudicator assignments",
    description="Retrieve adjudicator assignments with optional filtering by trial, role, and event submission.",
)
async def list_adjudicator_assignments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    adjudicator_role: Optional[AdjudicatorRole] = Query(
        None, description="Filter by adjudicator role"
    ),
    event_submission_id: Optional[str] = Query(
        None, description="Filter by event submission ID"
    ),
) -> AdjudicatorAssignmentListResponse:
    svc = get_clinical_event_adjudication_service()
    items = svc.list_adjudicator_assignments(
        trial_id=trial_id,
        adjudicator_role=adjudicator_role,
        event_submission_id=event_submission_id,
    )
    return AdjudicatorAssignmentListResponse(items=items, total=len(items))


@router.get(
    "/adjudicator-assignments/{assignment_id}",
    response_model=AdjudicatorAssignment,
    summary="Get an adjudicator assignment",
)
async def get_adjudicator_assignment(assignment_id: str) -> AdjudicatorAssignment:
    svc = get_clinical_event_adjudication_service()
    record = svc.get_adjudicator_assignment(assignment_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Adjudicator assignment '{assignment_id}' not found",
        )
    return record


@router.post(
    "/adjudicator-assignments",
    response_model=AdjudicatorAssignment,
    status_code=201,
    summary="Create an adjudicator assignment",
)
async def create_adjudicator_assignment(
    payload: AdjudicatorAssignmentCreate,
) -> AdjudicatorAssignment:
    svc = get_clinical_event_adjudication_service()
    return svc.create_adjudicator_assignment(payload)


@router.put(
    "/adjudicator-assignments/{assignment_id}",
    response_model=AdjudicatorAssignment,
    summary="Update an adjudicator assignment",
)
async def update_adjudicator_assignment(
    assignment_id: str, payload: AdjudicatorAssignmentUpdate
) -> AdjudicatorAssignment:
    svc = get_clinical_event_adjudication_service()
    updated = svc.update_adjudicator_assignment(assignment_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Adjudicator assignment '{assignment_id}' not found",
        )
    return updated


@router.delete(
    "/adjudicator-assignments/{assignment_id}",
    status_code=204,
    summary="Delete an adjudicator assignment",
)
async def delete_adjudicator_assignment(assignment_id: str) -> None:
    svc = get_clinical_event_adjudication_service()
    deleted = svc.delete_adjudicator_assignment(assignment_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Adjudicator assignment '{assignment_id}' not found",
        )


# ---------------------------------------------------------------------------
# Adjudication Decision Records
# ---------------------------------------------------------------------------


@router.get(
    "/adjudication-decisions",
    response_model=AdjudicationDecisionRecordListResponse,
    summary="List adjudication decision records",
    description="Retrieve adjudication decisions with optional filtering by trial, decision, and event submission.",
)
async def list_adjudication_decisions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    adjudication_decision: Optional[AdjudicationDecision] = Query(
        None, description="Filter by adjudication decision"
    ),
    event_submission_id: Optional[str] = Query(
        None, description="Filter by event submission ID"
    ),
) -> AdjudicationDecisionRecordListResponse:
    svc = get_clinical_event_adjudication_service()
    items = svc.list_adjudication_decision_records(
        trial_id=trial_id,
        adjudication_decision=adjudication_decision,
        event_submission_id=event_submission_id,
    )
    return AdjudicationDecisionRecordListResponse(items=items, total=len(items))


@router.get(
    "/adjudication-decisions/{decision_id}",
    response_model=AdjudicationDecisionRecord,
    summary="Get an adjudication decision record",
)
async def get_adjudication_decision(decision_id: str) -> AdjudicationDecisionRecord:
    svc = get_clinical_event_adjudication_service()
    record = svc.get_adjudication_decision_record(decision_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Adjudication decision '{decision_id}' not found",
        )
    return record


@router.post(
    "/adjudication-decisions",
    response_model=AdjudicationDecisionRecord,
    status_code=201,
    summary="Create an adjudication decision record",
)
async def create_adjudication_decision(
    payload: AdjudicationDecisionRecordCreate,
) -> AdjudicationDecisionRecord:
    svc = get_clinical_event_adjudication_service()
    return svc.create_adjudication_decision_record(payload)


@router.put(
    "/adjudication-decisions/{decision_id}",
    response_model=AdjudicationDecisionRecord,
    summary="Update an adjudication decision record",
)
async def update_adjudication_decision(
    decision_id: str, payload: AdjudicationDecisionRecordUpdate
) -> AdjudicationDecisionRecord:
    svc = get_clinical_event_adjudication_service()
    updated = svc.update_adjudication_decision_record(decision_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Adjudication decision '{decision_id}' not found",
        )
    return updated


@router.delete(
    "/adjudication-decisions/{decision_id}",
    status_code=204,
    summary="Delete an adjudication decision record",
)
async def delete_adjudication_decision(decision_id: str) -> None:
    svc = get_clinical_event_adjudication_service()
    deleted = svc.delete_adjudication_decision_record(decision_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Adjudication decision '{decision_id}' not found",
        )


# ---------------------------------------------------------------------------
# Consensus Reviews
# ---------------------------------------------------------------------------


@router.get(
    "/consensus-reviews",
    response_model=ConsensusReviewListResponse,
    summary="List consensus reviews",
    description="Retrieve consensus reviews with optional filtering by trial, outcome, and event submission.",
)
async def list_consensus_reviews(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    consensus_outcome: Optional[ConsensusOutcome] = Query(
        None, description="Filter by consensus outcome"
    ),
    event_submission_id: Optional[str] = Query(
        None, description="Filter by event submission ID"
    ),
) -> ConsensusReviewListResponse:
    svc = get_clinical_event_adjudication_service()
    items = svc.list_consensus_reviews(
        trial_id=trial_id,
        consensus_outcome=consensus_outcome,
        event_submission_id=event_submission_id,
    )
    return ConsensusReviewListResponse(items=items, total=len(items))


@router.get(
    "/consensus-reviews/{consensus_id}",
    response_model=ConsensusReview,
    summary="Get a consensus review",
)
async def get_consensus_review(consensus_id: str) -> ConsensusReview:
    svc = get_clinical_event_adjudication_service()
    record = svc.get_consensus_review(consensus_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Consensus review '{consensus_id}' not found",
        )
    return record


@router.post(
    "/consensus-reviews",
    response_model=ConsensusReview,
    status_code=201,
    summary="Create a consensus review",
)
async def create_consensus_review(payload: ConsensusReviewCreate) -> ConsensusReview:
    svc = get_clinical_event_adjudication_service()
    return svc.create_consensus_review(payload)


@router.put(
    "/consensus-reviews/{consensus_id}",
    response_model=ConsensusReview,
    summary="Update a consensus review",
)
async def update_consensus_review(
    consensus_id: str, payload: ConsensusReviewUpdate
) -> ConsensusReview:
    svc = get_clinical_event_adjudication_service()
    updated = svc.update_consensus_review(consensus_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Consensus review '{consensus_id}' not found",
        )
    return updated


@router.delete(
    "/consensus-reviews/{consensus_id}",
    status_code=204,
    summary="Delete a consensus review",
)
async def delete_consensus_review(consensus_id: str) -> None:
    svc = get_clinical_event_adjudication_service()
    deleted = svc.delete_consensus_review(consensus_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Consensus review '{consensus_id}' not found",
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=ClinicalEventAdjudicationMetrics,
    summary="Get clinical event adjudication metrics",
    description="Aggregated metrics across all clinical event adjudication operations.",
)
async def get_metrics() -> ClinicalEventAdjudicationMetrics:
    svc = get_clinical_event_adjudication_service()
    return svc.get_metrics()
