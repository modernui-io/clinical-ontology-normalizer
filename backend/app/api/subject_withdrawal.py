"""Subject Withdrawal API endpoints (SWD-MGT).

Provides comprehensive subject withdrawal operations: withdrawal requests,
withdrawal assessments, follow-up tracking, data disposition records, and
withdrawal metrics.

Endpoints:
    GET    /subject-withdrawal/withdrawal-requests                           - List withdrawal requests
    GET    /subject-withdrawal/withdrawal-requests/{request_id}              - Get single request
    POST   /subject-withdrawal/withdrawal-requests                           - Create request
    PUT    /subject-withdrawal/withdrawal-requests/{request_id}              - Update request
    DELETE /subject-withdrawal/withdrawal-requests/{request_id}              - Delete request
    GET    /subject-withdrawal/withdrawal-assessments                        - List assessments
    GET    /subject-withdrawal/withdrawal-assessments/{assessment_id}        - Get single assessment
    POST   /subject-withdrawal/withdrawal-assessments                        - Create assessment
    PUT    /subject-withdrawal/withdrawal-assessments/{assessment_id}        - Update assessment
    DELETE /subject-withdrawal/withdrawal-assessments/{assessment_id}        - Delete assessment
    GET    /subject-withdrawal/withdrawal-follow-ups                         - List follow-ups
    GET    /subject-withdrawal/withdrawal-follow-ups/{follow_up_id}          - Get single follow-up
    POST   /subject-withdrawal/withdrawal-follow-ups                         - Create follow-up
    PUT    /subject-withdrawal/withdrawal-follow-ups/{follow_up_id}          - Update follow-up
    DELETE /subject-withdrawal/withdrawal-follow-ups/{follow_up_id}          - Delete follow-up
    GET    /subject-withdrawal/data-disposition-records                      - List dispositions
    GET    /subject-withdrawal/data-disposition-records/{disposition_id}     - Get single disposition
    POST   /subject-withdrawal/data-disposition-records                      - Create disposition
    PUT    /subject-withdrawal/data-disposition-records/{disposition_id}     - Update disposition
    DELETE /subject-withdrawal/data-disposition-records/{disposition_id}     - Delete disposition
    GET    /subject-withdrawal/metrics                                       - Withdrawal metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.subject_withdrawal import (
    AssessmentType,
    DataDisposition,
    DataDispositionRecord,
    DataDispositionRecordCreate,
    DataDispositionRecordListResponse,
    DataDispositionRecordUpdate,
    FollowUpOutcome,
    SubjectWithdrawalMetrics,
    WithdrawalAssessment,
    WithdrawalAssessmentCreate,
    WithdrawalAssessmentListResponse,
    WithdrawalAssessmentUpdate,
    WithdrawalFollowUp,
    WithdrawalFollowUpCreate,
    WithdrawalFollowUpListResponse,
    WithdrawalFollowUpUpdate,
    WithdrawalReason,
    WithdrawalRequest,
    WithdrawalRequestCreate,
    WithdrawalRequestListResponse,
    WithdrawalRequestUpdate,
    WithdrawalStatus,
)
from app.services.subject_withdrawal_service import get_subject_withdrawal_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/subject-withdrawal",
    tags=["Subject Withdrawal"],
)


# ---------------------------------------------------------------------------
# Withdrawal Requests
# ---------------------------------------------------------------------------


@router.get(
    "/withdrawal-requests",
    response_model=WithdrawalRequestListResponse,
    summary="List withdrawal requests",
    description="Retrieve withdrawal requests with optional filtering by trial, reason, and status.",
)
async def list_withdrawal_requests(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    withdrawal_reason: Optional[WithdrawalReason] = Query(None, description="Filter by withdrawal reason"),
    withdrawal_status: Optional[WithdrawalStatus] = Query(None, description="Filter by withdrawal status"),
) -> WithdrawalRequestListResponse:
    svc = get_subject_withdrawal_service()
    items = svc.list_withdrawal_requests(
        trial_id=trial_id, withdrawal_reason=withdrawal_reason, withdrawal_status=withdrawal_status
    )
    return WithdrawalRequestListResponse(items=items, total=len(items))


@router.get(
    "/withdrawal-requests/{request_id}",
    response_model=WithdrawalRequest,
    summary="Get a withdrawal request",
)
async def get_withdrawal_request(request_id: str) -> WithdrawalRequest:
    svc = get_subject_withdrawal_service()
    record = svc.get_withdrawal_request(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Withdrawal request '{request_id}' not found")
    return record


@router.post(
    "/withdrawal-requests",
    response_model=WithdrawalRequest,
    status_code=201,
    summary="Create a withdrawal request",
)
async def create_withdrawal_request(payload: WithdrawalRequestCreate) -> WithdrawalRequest:
    svc = get_subject_withdrawal_service()
    return svc.create_withdrawal_request(payload)


@router.put(
    "/withdrawal-requests/{request_id}",
    response_model=WithdrawalRequest,
    summary="Update a withdrawal request",
)
async def update_withdrawal_request(
    request_id: str, payload: WithdrawalRequestUpdate
) -> WithdrawalRequest:
    svc = get_subject_withdrawal_service()
    updated = svc.update_withdrawal_request(request_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Withdrawal request '{request_id}' not found")
    return updated


@router.delete(
    "/withdrawal-requests/{request_id}",
    status_code=204,
    summary="Delete a withdrawal request",
)
async def delete_withdrawal_request(request_id: str) -> None:
    svc = get_subject_withdrawal_service()
    deleted = svc.delete_withdrawal_request(request_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Withdrawal request '{request_id}' not found")


# ---------------------------------------------------------------------------
# Withdrawal Assessments
# ---------------------------------------------------------------------------


@router.get(
    "/withdrawal-assessments",
    response_model=WithdrawalAssessmentListResponse,
    summary="List withdrawal assessments",
    description="Retrieve withdrawal assessments with optional filtering by trial, type, and request.",
)
async def list_withdrawal_assessments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    assessment_type: Optional[AssessmentType] = Query(None, description="Filter by assessment type"),
    withdrawal_request_id: Optional[str] = Query(None, description="Filter by withdrawal request ID"),
) -> WithdrawalAssessmentListResponse:
    svc = get_subject_withdrawal_service()
    items = svc.list_withdrawal_assessments(
        trial_id=trial_id, assessment_type=assessment_type, withdrawal_request_id=withdrawal_request_id
    )
    return WithdrawalAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/withdrawal-assessments/{assessment_id}",
    response_model=WithdrawalAssessment,
    summary="Get a withdrawal assessment",
)
async def get_withdrawal_assessment(assessment_id: str) -> WithdrawalAssessment:
    svc = get_subject_withdrawal_service()
    record = svc.get_withdrawal_assessment(assessment_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Withdrawal assessment '{assessment_id}' not found"
        )
    return record


@router.post(
    "/withdrawal-assessments",
    response_model=WithdrawalAssessment,
    status_code=201,
    summary="Create a withdrawal assessment",
)
async def create_withdrawal_assessment(payload: WithdrawalAssessmentCreate) -> WithdrawalAssessment:
    svc = get_subject_withdrawal_service()
    return svc.create_withdrawal_assessment(payload)


@router.put(
    "/withdrawal-assessments/{assessment_id}",
    response_model=WithdrawalAssessment,
    summary="Update a withdrawal assessment",
)
async def update_withdrawal_assessment(
    assessment_id: str, payload: WithdrawalAssessmentUpdate
) -> WithdrawalAssessment:
    svc = get_subject_withdrawal_service()
    updated = svc.update_withdrawal_assessment(assessment_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Withdrawal assessment '{assessment_id}' not found"
        )
    return updated


@router.delete(
    "/withdrawal-assessments/{assessment_id}",
    status_code=204,
    summary="Delete a withdrawal assessment",
)
async def delete_withdrawal_assessment(assessment_id: str) -> None:
    svc = get_subject_withdrawal_service()
    deleted = svc.delete_withdrawal_assessment(assessment_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Withdrawal assessment '{assessment_id}' not found"
        )


# ---------------------------------------------------------------------------
# Withdrawal Follow-Ups
# ---------------------------------------------------------------------------


@router.get(
    "/withdrawal-follow-ups",
    response_model=WithdrawalFollowUpListResponse,
    summary="List withdrawal follow-ups",
    description="Retrieve withdrawal follow-ups with optional filtering by trial, outcome, and subject.",
)
async def list_withdrawal_follow_ups(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    follow_up_outcome: Optional[FollowUpOutcome] = Query(None, description="Filter by follow-up outcome"),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
) -> WithdrawalFollowUpListResponse:
    svc = get_subject_withdrawal_service()
    items = svc.list_withdrawal_follow_ups(
        trial_id=trial_id, follow_up_outcome=follow_up_outcome, subject_id=subject_id
    )
    return WithdrawalFollowUpListResponse(items=items, total=len(items))


@router.get(
    "/withdrawal-follow-ups/{follow_up_id}",
    response_model=WithdrawalFollowUp,
    summary="Get a withdrawal follow-up",
)
async def get_withdrawal_follow_up(follow_up_id: str) -> WithdrawalFollowUp:
    svc = get_subject_withdrawal_service()
    record = svc.get_withdrawal_follow_up(follow_up_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Withdrawal follow-up '{follow_up_id}' not found"
        )
    return record


@router.post(
    "/withdrawal-follow-ups",
    response_model=WithdrawalFollowUp,
    status_code=201,
    summary="Create a withdrawal follow-up",
)
async def create_withdrawal_follow_up(payload: WithdrawalFollowUpCreate) -> WithdrawalFollowUp:
    svc = get_subject_withdrawal_service()
    return svc.create_withdrawal_follow_up(payload)


@router.put(
    "/withdrawal-follow-ups/{follow_up_id}",
    response_model=WithdrawalFollowUp,
    summary="Update a withdrawal follow-up",
)
async def update_withdrawal_follow_up(
    follow_up_id: str, payload: WithdrawalFollowUpUpdate
) -> WithdrawalFollowUp:
    svc = get_subject_withdrawal_service()
    updated = svc.update_withdrawal_follow_up(follow_up_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Withdrawal follow-up '{follow_up_id}' not found"
        )
    return updated


@router.delete(
    "/withdrawal-follow-ups/{follow_up_id}",
    status_code=204,
    summary="Delete a withdrawal follow-up",
)
async def delete_withdrawal_follow_up(follow_up_id: str) -> None:
    svc = get_subject_withdrawal_service()
    deleted = svc.delete_withdrawal_follow_up(follow_up_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Withdrawal follow-up '{follow_up_id}' not found"
        )


# ---------------------------------------------------------------------------
# Data Disposition Records
# ---------------------------------------------------------------------------


@router.get(
    "/data-disposition-records",
    response_model=DataDispositionRecordListResponse,
    summary="List data disposition records",
    description="Retrieve data disposition records with optional filtering by trial, disposition type, and subject.",
)
async def list_data_disposition_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    data_disposition: Optional[DataDisposition] = Query(None, description="Filter by data disposition"),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
) -> DataDispositionRecordListResponse:
    svc = get_subject_withdrawal_service()
    items = svc.list_data_disposition_records(
        trial_id=trial_id, data_disposition=data_disposition, subject_id=subject_id
    )
    return DataDispositionRecordListResponse(items=items, total=len(items))


@router.get(
    "/data-disposition-records/{disposition_id}",
    response_model=DataDispositionRecord,
    summary="Get a data disposition record",
)
async def get_data_disposition_record(disposition_id: str) -> DataDispositionRecord:
    svc = get_subject_withdrawal_service()
    record = svc.get_data_disposition_record(disposition_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Data disposition record '{disposition_id}' not found"
        )
    return record


@router.post(
    "/data-disposition-records",
    response_model=DataDispositionRecord,
    status_code=201,
    summary="Create a data disposition record",
)
async def create_data_disposition_record(payload: DataDispositionRecordCreate) -> DataDispositionRecord:
    svc = get_subject_withdrawal_service()
    return svc.create_data_disposition_record(payload)


@router.put(
    "/data-disposition-records/{disposition_id}",
    response_model=DataDispositionRecord,
    summary="Update a data disposition record",
)
async def update_data_disposition_record(
    disposition_id: str, payload: DataDispositionRecordUpdate
) -> DataDispositionRecord:
    svc = get_subject_withdrawal_service()
    updated = svc.update_data_disposition_record(disposition_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Data disposition record '{disposition_id}' not found"
        )
    return updated


@router.delete(
    "/data-disposition-records/{disposition_id}",
    status_code=204,
    summary="Delete a data disposition record",
)
async def delete_data_disposition_record(disposition_id: str) -> None:
    svc = get_subject_withdrawal_service()
    deleted = svc.delete_data_disposition_record(disposition_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Data disposition record '{disposition_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=SubjectWithdrawalMetrics,
    summary="Get subject withdrawal metrics",
    description="Aggregated metrics across all subject withdrawal operations, optionally filtered by trial.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> SubjectWithdrawalMetrics:
    svc = get_subject_withdrawal_service()
    return svc.get_metrics(trial_id=trial_id)
