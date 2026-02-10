"""Central IRB/EC Management API endpoints (CLINICAL-8).

Provides comprehensive IRB/EC management operations: board registration,
submission lifecycle (draft -> submitted -> under_review -> approved/disapproved),
continuing review tracking, reportable event filing, regulatory document
management, correspondence tracking, expiring approval alerts, and IRB metrics.

Endpoints:
    GET    /central-irb/boards                                       - List boards
    POST   /central-irb/boards                                      - Create board
    GET    /central-irb/boards/{board_id}                            - Get board
    PUT    /central-irb/boards/{board_id}                            - Update board
    GET    /central-irb/submissions                                  - List submissions
    POST   /central-irb/submissions                                  - Create submission
    GET    /central-irb/submissions/{submission_id}                  - Get submission
    PUT    /central-irb/submissions/{submission_id}                  - Update submission
    POST   /central-irb/submissions/{submission_id}/submit           - Submit for review
    POST   /central-irb/submissions/{submission_id}/record-outcome   - Record outcome
    GET    /central-irb/submissions/{submission_id}/continuing-reviews   - List CRs for submission
    POST   /central-irb/submissions/{submission_id}/continuing-reviews   - Create CR
    GET    /central-irb/continuing-reviews/{review_id}               - Get single CR
    PUT    /central-irb/continuing-reviews/{review_id}               - Update CR
    GET    /central-irb/reportable-events                            - List events
    POST   /central-irb/reportable-events                            - File event
    GET    /central-irb/reportable-events/{event_id}                 - Get event
    PUT    /central-irb/reportable-events/{event_id}                 - Update event
    GET    /central-irb/submissions/{submission_id}/documents        - List docs for submission
    POST   /central-irb/submissions/{submission_id}/documents        - Create doc
    GET    /central-irb/documents/{document_id}                      - Get document
    GET    /central-irb/submissions/{submission_id}/correspondence   - List correspondence
    POST   /central-irb/submissions/{submission_id}/correspondence   - Create correspondence
    GET    /central-irb/expiring-approvals                           - Expiring approvals
    GET    /central-irb/metrics                                      - IRB metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.central_irb import (
    BoardType,
    ContinuingReview,
    ContinuingReviewCreate,
    ContinuingReviewListResponse,
    ContinuingReviewUpdate,
    DocumentStatus,
    DocumentType,
    EventSeverity,
    EventStatus,
    IRBBoard,
    IRBBoardCreate,
    IRBBoardListResponse,
    IRBBoardUpdate,
    IRBCorrespondence,
    IRBCorrespondenceCreate,
    IRBCorrespondenceListResponse,
    IRBMetrics,
    IRBSubmission,
    IRBSubmissionCreate,
    IRBSubmissionListResponse,
    IRBSubmissionUpdate,
    RecordOutcomeRequest,
    RegulatoryDocument,
    RegulatoryDocumentCreate,
    RegulatoryDocumentListResponse,
    ReportableEvent,
    ReportableEventCreate,
    ReportableEventListResponse,
    ReportableEventUpdate,
    ReviewStatus,
    SubmissionSubmitRequest,
    SubmissionType,
)
from app.services.central_irb_service import get_central_irb_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/central-irb",
    tags=["Central IRB/EC"],
)


# ---------------------------------------------------------------------------
# Board Management
# ---------------------------------------------------------------------------


@router.get(
    "/boards",
    response_model=IRBBoardListResponse,
    summary="List IRB/EC boards",
    description="Retrieve registered boards with optional filtering by type and active status.",
)
async def list_boards(
    board_type: Optional[BoardType] = Query(None, description="Filter by board type"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
) -> IRBBoardListResponse:
    svc = get_central_irb_service()
    items = svc.list_boards(board_type=board_type, active=active)
    return IRBBoardListResponse(items=items, total=len(items))


@router.post(
    "/boards",
    response_model=IRBBoard,
    status_code=201,
    summary="Register a new IRB/EC board",
)
async def create_board(payload: IRBBoardCreate) -> IRBBoard:
    svc = get_central_irb_service()
    return svc.create_board(payload)


@router.get(
    "/boards/{board_id}",
    response_model=IRBBoard,
    summary="Get an IRB/EC board",
)
async def get_board(board_id: str) -> IRBBoard:
    svc = get_central_irb_service()
    board = svc.get_board(board_id)
    if board is None:
        raise HTTPException(status_code=404, detail=f"Board '{board_id}' not found")
    return board


@router.put(
    "/boards/{board_id}",
    response_model=IRBBoard,
    summary="Update an IRB/EC board",
)
async def update_board(board_id: str, payload: IRBBoardUpdate) -> IRBBoard:
    svc = get_central_irb_service()
    updated = svc.update_board(board_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Board '{board_id}' not found")
    return updated


# ---------------------------------------------------------------------------
# Submission Management
# ---------------------------------------------------------------------------


@router.get(
    "/submissions",
    response_model=IRBSubmissionListResponse,
    summary="List IRB submissions",
    description="Retrieve submissions with optional filtering by board, trial, status, and type.",
)
async def list_submissions(
    board_id: Optional[str] = Query(None, description="Filter by board ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[ReviewStatus] = Query(None, description="Filter by status"),
    submission_type: Optional[SubmissionType] = Query(
        None, description="Filter by submission type"
    ),
) -> IRBSubmissionListResponse:
    svc = get_central_irb_service()
    items = svc.list_submissions(
        board_id=board_id,
        trial_id=trial_id,
        status=status,
        submission_type=submission_type,
    )
    return IRBSubmissionListResponse(items=items, total=len(items))


@router.post(
    "/submissions",
    response_model=IRBSubmission,
    status_code=201,
    summary="Create a new IRB submission",
)
async def create_submission(payload: IRBSubmissionCreate) -> IRBSubmission:
    svc = get_central_irb_service()
    return svc.create_submission(payload)


@router.get(
    "/submissions/{submission_id}",
    response_model=IRBSubmission,
    summary="Get an IRB submission",
)
async def get_submission(submission_id: str) -> IRBSubmission:
    svc = get_central_irb_service()
    submission = svc.get_submission(submission_id)
    if submission is None:
        raise HTTPException(
            status_code=404, detail=f"Submission '{submission_id}' not found"
        )
    return submission


@router.put(
    "/submissions/{submission_id}",
    response_model=IRBSubmission,
    summary="Update an IRB submission",
)
async def update_submission(
    submission_id: str, payload: IRBSubmissionUpdate
) -> IRBSubmission:
    svc = get_central_irb_service()
    updated = svc.update_submission(submission_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Submission '{submission_id}' not found"
        )
    return updated


@router.post(
    "/submissions/{submission_id}/submit",
    response_model=IRBSubmission,
    summary="Submit for board review",
    description="Transition a draft submission to submitted status.",
)
async def submit_for_review(
    submission_id: str, payload: SubmissionSubmitRequest
) -> IRBSubmission:
    svc = get_central_irb_service()
    try:
        result = svc.submit_for_review(submission_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Submission '{submission_id}' not found"
        )
    return result


@router.post(
    "/submissions/{submission_id}/record-outcome",
    response_model=IRBSubmission,
    summary="Record board review outcome",
    description="Record the board's review outcome including approval, conditional approval, deferral, or disapproval.",
)
async def record_outcome(
    submission_id: str, payload: RecordOutcomeRequest
) -> IRBSubmission:
    svc = get_central_irb_service()
    try:
        result = svc.record_outcome(submission_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Submission '{submission_id}' not found"
        )
    return result


# ---------------------------------------------------------------------------
# Continuing Reviews
# ---------------------------------------------------------------------------


@router.get(
    "/submissions/{submission_id}/continuing-reviews",
    response_model=ContinuingReviewListResponse,
    summary="List continuing reviews for a submission",
)
async def list_continuing_reviews_for_submission(
    submission_id: str,
) -> ContinuingReviewListResponse:
    svc = get_central_irb_service()
    items = svc.list_continuing_reviews(submission_id=submission_id)
    return ContinuingReviewListResponse(items=items, total=len(items))


@router.post(
    "/submissions/{submission_id}/continuing-reviews",
    response_model=ContinuingReview,
    status_code=201,
    summary="Create a continuing review",
)
async def create_continuing_review(
    submission_id: str, payload: ContinuingReviewCreate
) -> ContinuingReview:
    svc = get_central_irb_service()
    # Verify submission exists
    if svc.get_submission(submission_id) is None:
        raise HTTPException(
            status_code=404, detail=f"Submission '{submission_id}' not found"
        )
    return svc.create_continuing_review(submission_id, payload)


@router.get(
    "/continuing-reviews/{review_id}",
    response_model=ContinuingReview,
    summary="Get a continuing review",
)
async def get_continuing_review(review_id: str) -> ContinuingReview:
    svc = get_central_irb_service()
    cr = svc.get_continuing_review(review_id)
    if cr is None:
        raise HTTPException(
            status_code=404, detail=f"Continuing review '{review_id}' not found"
        )
    return cr


@router.put(
    "/continuing-reviews/{review_id}",
    response_model=ContinuingReview,
    summary="Update a continuing review",
)
async def update_continuing_review(
    review_id: str, payload: ContinuingReviewUpdate
) -> ContinuingReview:
    svc = get_central_irb_service()
    updated = svc.update_continuing_review(review_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Continuing review '{review_id}' not found"
        )
    return updated


# ---------------------------------------------------------------------------
# Reportable Events
# ---------------------------------------------------------------------------


@router.get(
    "/reportable-events",
    response_model=ReportableEventListResponse,
    summary="List reportable events",
    description="Retrieve reportable events with optional filtering by board, trial, status, and severity.",
)
async def list_reportable_events(
    board_id: Optional[str] = Query(None, description="Filter by board ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[EventStatus] = Query(None, description="Filter by status"),
    severity: Optional[EventSeverity] = Query(None, description="Filter by severity"),
) -> ReportableEventListResponse:
    svc = get_central_irb_service()
    items = svc.list_reportable_events(
        board_id=board_id, trial_id=trial_id, status=status, severity=severity
    )
    return ReportableEventListResponse(items=items, total=len(items))


@router.post(
    "/reportable-events",
    response_model=ReportableEvent,
    status_code=201,
    summary="File a reportable event",
)
async def file_reportable_event(payload: ReportableEventCreate) -> ReportableEvent:
    svc = get_central_irb_service()
    return svc.file_reportable_event(payload)


@router.get(
    "/reportable-events/{event_id}",
    response_model=ReportableEvent,
    summary="Get a reportable event",
)
async def get_reportable_event(event_id: str) -> ReportableEvent:
    svc = get_central_irb_service()
    event = svc.get_reportable_event(event_id)
    if event is None:
        raise HTTPException(
            status_code=404, detail=f"Reportable event '{event_id}' not found"
        )
    return event


@router.put(
    "/reportable-events/{event_id}",
    response_model=ReportableEvent,
    summary="Update a reportable event",
)
async def update_reportable_event(
    event_id: str, payload: ReportableEventUpdate
) -> ReportableEvent:
    svc = get_central_irb_service()
    updated = svc.update_reportable_event(event_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Reportable event '{event_id}' not found"
        )
    return updated


# ---------------------------------------------------------------------------
# Regulatory Documents
# ---------------------------------------------------------------------------


@router.get(
    "/submissions/{submission_id}/documents",
    response_model=RegulatoryDocumentListResponse,
    summary="List documents for a submission",
)
async def list_documents_for_submission(
    submission_id: str,
    document_type: Optional[DocumentType] = Query(None, description="Filter by document type"),
    status: Optional[DocumentStatus] = Query(None, description="Filter by status"),
) -> RegulatoryDocumentListResponse:
    svc = get_central_irb_service()
    items = svc.list_documents(
        submission_id=submission_id, document_type=document_type, status=status
    )
    return RegulatoryDocumentListResponse(items=items, total=len(items))


@router.post(
    "/submissions/{submission_id}/documents",
    response_model=RegulatoryDocument,
    status_code=201,
    summary="Upload a regulatory document",
)
async def create_document(
    submission_id: str, payload: RegulatoryDocumentCreate
) -> RegulatoryDocument:
    svc = get_central_irb_service()
    # Verify submission exists
    if svc.get_submission(submission_id) is None:
        raise HTTPException(
            status_code=404, detail=f"Submission '{submission_id}' not found"
        )
    return svc.create_document(submission_id, payload)


@router.get(
    "/documents/{document_id}",
    response_model=RegulatoryDocument,
    summary="Get a regulatory document",
)
async def get_document(document_id: str) -> RegulatoryDocument:
    svc = get_central_irb_service()
    doc = svc.get_document(document_id)
    if doc is None:
        raise HTTPException(
            status_code=404, detail=f"Document '{document_id}' not found"
        )
    return doc


# ---------------------------------------------------------------------------
# Correspondence
# ---------------------------------------------------------------------------


@router.get(
    "/submissions/{submission_id}/correspondence",
    response_model=IRBCorrespondenceListResponse,
    summary="List correspondence for a submission",
)
async def list_correspondence_for_submission(
    submission_id: str,
) -> IRBCorrespondenceListResponse:
    svc = get_central_irb_service()
    items = svc.list_correspondence(submission_id=submission_id)
    return IRBCorrespondenceListResponse(items=items, total=len(items))


@router.post(
    "/submissions/{submission_id}/correspondence",
    response_model=IRBCorrespondence,
    status_code=201,
    summary="Create correspondence for a submission",
)
async def create_correspondence(
    submission_id: str, payload: IRBCorrespondenceCreate
) -> IRBCorrespondence:
    svc = get_central_irb_service()
    # Verify submission exists
    if svc.get_submission(submission_id) is None:
        raise HTTPException(
            status_code=404, detail=f"Submission '{submission_id}' not found"
        )
    return svc.create_correspondence(submission_id, payload)


# ---------------------------------------------------------------------------
# Expiring Approvals & Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/expiring-approvals",
    response_model=IRBSubmissionListResponse,
    summary="Get expiring approvals",
    description="Retrieve submissions with approvals expiring within the specified number of days (default 30).",
)
async def get_expiring_approvals(
    days: int = Query(30, ge=1, le=365, description="Number of days to look ahead"),
) -> IRBSubmissionListResponse:
    svc = get_central_irb_service()
    items = svc.get_expiring_approvals(days=days)
    return IRBSubmissionListResponse(items=items, total=len(items))


@router.get(
    "/metrics",
    response_model=IRBMetrics,
    summary="Get IRB/EC operational metrics",
    description="Aggregated metrics for IRB/EC management including submission counts, review times, and open events.",
)
async def get_metrics() -> IRBMetrics:
    svc = get_central_irb_service()
    return svc.get_metrics()
