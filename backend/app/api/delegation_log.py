"""Delegation Log API endpoints (DELEG-LOG).

Provides comprehensive delegation of authority operations: delegation entries,
authority records, training verifications, delegation audits, and delegation
metrics.

Endpoints:
    GET    /delegation-log/delegation-entries                          - List delegation entries
    GET    /delegation-log/delegation-entries/{entry_id}               - Get single entry
    POST   /delegation-log/delegation-entries                          - Create entry
    PUT    /delegation-log/delegation-entries/{entry_id}               - Update entry
    DELETE /delegation-log/delegation-entries/{entry_id}               - Delete entry
    GET    /delegation-log/authority-records                           - List authority records
    GET    /delegation-log/authority-records/{record_id}               - Get single record
    POST   /delegation-log/authority-records                           - Create record
    PUT    /delegation-log/authority-records/{record_id}               - Update record
    DELETE /delegation-log/authority-records/{record_id}               - Delete record
    GET    /delegation-log/training-verifications                      - List training verifications
    GET    /delegation-log/training-verifications/{training_id}        - Get single verification
    POST   /delegation-log/training-verifications                      - Create verification
    PUT    /delegation-log/training-verifications/{training_id}        - Update verification
    DELETE /delegation-log/training-verifications/{training_id}        - Delete verification
    GET    /delegation-log/delegation-audits                           - List audits
    GET    /delegation-log/delegation-audits/{audit_id}                - Get single audit
    POST   /delegation-log/delegation-audits                           - Create audit
    PUT    /delegation-log/delegation-audits/{audit_id}                - Update audit
    DELETE /delegation-log/delegation-audits/{audit_id}                - Delete audit
    GET    /delegation-log/metrics                                     - Delegation metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.delegation_log import (
    AuditResult,
    AuthorityLevel,
    AuthorityRecord,
    AuthorityRecordCreate,
    AuthorityRecordListResponse,
    AuthorityRecordUpdate,
    DelegationAudit,
    DelegationAuditCreate,
    DelegationAuditListResponse,
    DelegationAuditUpdate,
    DelegationCategory,
    DelegationEntry,
    DelegationEntryCreate,
    DelegationEntryListResponse,
    DelegationEntryUpdate,
    DelegationLogMetrics,
    DelegationStatus,
    TrainingStatus,
    TrainingVerification,
    TrainingVerificationCreate,
    TrainingVerificationListResponse,
    TrainingVerificationUpdate,
)
from app.services.delegation_log_service import get_delegation_log_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/delegation-log",
    tags=["Delegation Log"],
)


# ---------------------------------------------------------------------------
# Delegation Entries
# ---------------------------------------------------------------------------


@router.get(
    "/delegation-entries",
    response_model=DelegationEntryListResponse,
    summary="List delegation entries",
    description="Retrieve delegation entries with optional filtering by trial, category, and status.",
)
async def list_delegation_entries(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    delegation_category: Optional[DelegationCategory] = Query(
        None, description="Filter by delegation category"
    ),
    delegation_status: Optional[DelegationStatus] = Query(
        None, description="Filter by delegation status"
    ),
) -> DelegationEntryListResponse:
    svc = get_delegation_log_service()
    items = svc.list_delegation_entries(
        trial_id=trial_id,
        delegation_category=delegation_category,
        delegation_status=delegation_status,
    )
    return DelegationEntryListResponse(items=items, total=len(items))


@router.get(
    "/delegation-entries/{entry_id}",
    response_model=DelegationEntry,
    summary="Get a delegation entry",
)
async def get_delegation_entry(entry_id: str) -> DelegationEntry:
    svc = get_delegation_log_service()
    entry = svc.get_delegation_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Delegation entry '{entry_id}' not found")
    return entry


@router.post(
    "/delegation-entries",
    response_model=DelegationEntry,
    status_code=201,
    summary="Create a delegation entry",
)
async def create_delegation_entry(payload: DelegationEntryCreate) -> DelegationEntry:
    svc = get_delegation_log_service()
    return svc.create_delegation_entry(payload)


@router.put(
    "/delegation-entries/{entry_id}",
    response_model=DelegationEntry,
    summary="Update a delegation entry",
)
async def update_delegation_entry(
    entry_id: str, payload: DelegationEntryUpdate
) -> DelegationEntry:
    svc = get_delegation_log_service()
    updated = svc.update_delegation_entry(entry_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Delegation entry '{entry_id}' not found")
    return updated


@router.delete(
    "/delegation-entries/{entry_id}",
    status_code=204,
    summary="Delete a delegation entry",
)
async def delete_delegation_entry(entry_id: str) -> None:
    svc = get_delegation_log_service()
    deleted = svc.delete_delegation_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Delegation entry '{entry_id}' not found")


# ---------------------------------------------------------------------------
# Authority Records
# ---------------------------------------------------------------------------


@router.get(
    "/authority-records",
    response_model=AuthorityRecordListResponse,
    summary="List authority records",
    description="Retrieve authority records with optional filtering by trial, authority level, and qualification.",
)
async def list_authority_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    authority_level: Optional[AuthorityLevel] = Query(
        None, description="Filter by authority level"
    ),
    is_qualified: Optional[bool] = Query(None, description="Filter by qualification status"),
) -> AuthorityRecordListResponse:
    svc = get_delegation_log_service()
    items = svc.list_authority_records(
        trial_id=trial_id, authority_level=authority_level, is_qualified=is_qualified
    )
    return AuthorityRecordListResponse(items=items, total=len(items))


@router.get(
    "/authority-records/{record_id}",
    response_model=AuthorityRecord,
    summary="Get an authority record",
)
async def get_authority_record(record_id: str) -> AuthorityRecord:
    svc = get_delegation_log_service()
    record = svc.get_authority_record(record_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Authority record '{record_id}' not found"
        )
    return record


@router.post(
    "/authority-records",
    response_model=AuthorityRecord,
    status_code=201,
    summary="Create an authority record",
)
async def create_authority_record(payload: AuthorityRecordCreate) -> AuthorityRecord:
    svc = get_delegation_log_service()
    return svc.create_authority_record(payload)


@router.put(
    "/authority-records/{record_id}",
    response_model=AuthorityRecord,
    summary="Update an authority record",
)
async def update_authority_record(
    record_id: str, payload: AuthorityRecordUpdate
) -> AuthorityRecord:
    svc = get_delegation_log_service()
    updated = svc.update_authority_record(record_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Authority record '{record_id}' not found"
        )
    return updated


@router.delete(
    "/authority-records/{record_id}",
    status_code=204,
    summary="Delete an authority record",
)
async def delete_authority_record(record_id: str) -> None:
    svc = get_delegation_log_service()
    deleted = svc.delete_authority_record(record_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Authority record '{record_id}' not found"
        )


# ---------------------------------------------------------------------------
# Training Verifications
# ---------------------------------------------------------------------------


@router.get(
    "/training-verifications",
    response_model=TrainingVerificationListResponse,
    summary="List training verifications",
    description="Retrieve training verifications with optional filtering by trial, status, and GCP training.",
)
async def list_training_verifications(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    training_status: Optional[TrainingStatus] = Query(
        None, description="Filter by training status"
    ),
    is_gcp_training: Optional[bool] = Query(None, description="Filter by GCP training flag"),
) -> TrainingVerificationListResponse:
    svc = get_delegation_log_service()
    items = svc.list_training_verifications(
        trial_id=trial_id, training_status=training_status, is_gcp_training=is_gcp_training
    )
    return TrainingVerificationListResponse(items=items, total=len(items))


@router.get(
    "/training-verifications/{training_id}",
    response_model=TrainingVerification,
    summary="Get a training verification",
)
async def get_training_verification(training_id: str) -> TrainingVerification:
    svc = get_delegation_log_service()
    record = svc.get_training_verification(training_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Training verification '{training_id}' not found"
        )
    return record


@router.post(
    "/training-verifications",
    response_model=TrainingVerification,
    status_code=201,
    summary="Create a training verification",
)
async def create_training_verification(
    payload: TrainingVerificationCreate,
) -> TrainingVerification:
    svc = get_delegation_log_service()
    return svc.create_training_verification(payload)


@router.put(
    "/training-verifications/{training_id}",
    response_model=TrainingVerification,
    summary="Update a training verification",
)
async def update_training_verification(
    training_id: str, payload: TrainingVerificationUpdate
) -> TrainingVerification:
    svc = get_delegation_log_service()
    updated = svc.update_training_verification(training_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Training verification '{training_id}' not found"
        )
    return updated


@router.delete(
    "/training-verifications/{training_id}",
    status_code=204,
    summary="Delete a training verification",
)
async def delete_training_verification(training_id: str) -> None:
    svc = get_delegation_log_service()
    deleted = svc.delete_training_verification(training_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Training verification '{training_id}' not found"
        )


# ---------------------------------------------------------------------------
# Delegation Audits
# ---------------------------------------------------------------------------


@router.get(
    "/delegation-audits",
    response_model=DelegationAuditListResponse,
    summary="List delegation audits",
    description="Retrieve delegation audits with optional filtering by trial and result.",
)
async def list_delegation_audits(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    audit_result: Optional[AuditResult] = Query(None, description="Filter by audit result"),
) -> DelegationAuditListResponse:
    svc = get_delegation_log_service()
    items = svc.list_delegation_audits(trial_id=trial_id, audit_result=audit_result)
    return DelegationAuditListResponse(items=items, total=len(items))


@router.get(
    "/delegation-audits/{audit_id}",
    response_model=DelegationAudit,
    summary="Get a delegation audit",
)
async def get_delegation_audit(audit_id: str) -> DelegationAudit:
    svc = get_delegation_log_service()
    record = svc.get_delegation_audit(audit_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Delegation audit '{audit_id}' not found"
        )
    return record


@router.post(
    "/delegation-audits",
    response_model=DelegationAudit,
    status_code=201,
    summary="Create a delegation audit",
)
async def create_delegation_audit(payload: DelegationAuditCreate) -> DelegationAudit:
    svc = get_delegation_log_service()
    return svc.create_delegation_audit(payload)


@router.put(
    "/delegation-audits/{audit_id}",
    response_model=DelegationAudit,
    summary="Update a delegation audit",
)
async def update_delegation_audit(
    audit_id: str, payload: DelegationAuditUpdate
) -> DelegationAudit:
    svc = get_delegation_log_service()
    updated = svc.update_delegation_audit(audit_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Delegation audit '{audit_id}' not found"
        )
    return updated


@router.delete(
    "/delegation-audits/{audit_id}",
    status_code=204,
    summary="Delete a delegation audit",
)
async def delete_delegation_audit(audit_id: str) -> None:
    svc = get_delegation_log_service()
    deleted = svc.delete_delegation_audit(audit_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Delegation audit '{audit_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=DelegationLogMetrics,
    summary="Get delegation log metrics",
    description="Retrieve aggregated delegation log metrics including delegation rates, training completion, and compliance.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> DelegationLogMetrics:
    svc = get_delegation_log_service()
    return svc.get_metrics(trial_id=trial_id)
