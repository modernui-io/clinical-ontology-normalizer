"""Data Review & Lock API endpoints (CLINICAL-DL).

Provides comprehensive database lock management for clinical trials: lock CRUD,
lifecycle transitions (plan, start, soft lock, hard lock, unlock, cancel),
pre-lock validation, data cuts, clean data workflows, unblinding procedures,
lock checklists, and aggregated lock metrics.

Endpoints:
    GET    /data-locks/locks                                          - List locks
    GET    /data-locks/locks/{lock_id}                                - Get single lock
    POST   /data-locks/locks                                          - Create lock
    PUT    /data-locks/locks/{lock_id}                                - Update lock
    DELETE /data-locks/locks/{lock_id}                                - Delete lock
    POST   /data-locks/locks/{lock_id}/start                          - Start lock process
    POST   /data-locks/locks/{lock_id}/soft-lock                      - Execute soft lock
    POST   /data-locks/locks/{lock_id}/hard-lock                      - Execute hard lock
    POST   /data-locks/locks/{lock_id}/unlock                         - Unlock database
    POST   /data-locks/locks/{lock_id}/cancel                         - Cancel lock
    GET    /data-locks/locks/{lock_id}/pre-lock-checks                - Run pre-lock checks
    GET    /data-locks/data-cuts                                      - List data cuts
    GET    /data-locks/data-cuts/{cut_id}                             - Get single data cut
    POST   /data-locks/locks/{lock_id}/data-cuts                      - Create data cut
    DELETE /data-locks/data-cuts/{cut_id}                             - Delete data cut
    GET    /data-locks/clean-data                                     - List clean data records
    GET    /data-locks/clean-data/{record_id}                         - Get single record
    POST   /data-locks/locks/{lock_id}/clean-data                     - Create clean data record
    PUT    /data-locks/clean-data/{record_id}                         - Update clean data record
    POST   /data-locks/clean-data/{record_id}/flag                    - Flag data record
    POST   /data-locks/clean-data/{record_id}/mark-clean              - Mark data as clean
    GET    /data-locks/locks/{lock_id}/clean-data-summary             - Clean data summary
    GET    /data-locks/unblinding-requests                            - List unblinding requests
    GET    /data-locks/unblinding-requests/{request_id}               - Get single request
    POST   /data-locks/locks/{lock_id}/unblinding-requests            - Create unblinding request
    POST   /data-locks/unblinding-requests/{request_id}/approve       - Approve unblinding
    POST   /data-locks/unblinding-requests/{request_id}/execute       - Execute unblinding
    GET    /data-locks/locks/{lock_id}/unblinding-audit               - Unblinding audit trail
    GET    /data-locks/checklists                                     - List checklists
    GET    /data-locks/checklists/{checklist_id}                      - Get single checklist
    POST   /data-locks/locks/{lock_id}/checklists                     - Create checklist
    PUT    /data-locks/checklists/{checklist_id}/items/{item_id}      - Update checklist item
    GET    /data-locks/checklists/{checklist_id}/completion           - Checklist completion stats
    GET    /data-locks/metrics                                        - Lock metrics dashboard
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.data_lock import (
    CleanDataRecord,
    CleanDataRecordCreate,
    CleanDataRecordListResponse,
    CleanDataRecordUpdate,
    CleanDataStatus,
    DataCut,
    DataCutCreate,
    DataCutListResponse,
    DataLock,
    DataLockCreate,
    DataLockListResponse,
    DataLockMetrics,
    DataLockUpdate,
    LockChecklist,
    LockChecklistCreate,
    LockChecklistItemUpdate,
    LockChecklistListResponse,
    LockExecute,
    LockStatus,
    LockType,
    LockUnlock,
    PreLockSummary,
    UnblindingApproval,
    UnblindingExecute,
    UnblindingRequest,
    UnblindingRequestCreate,
    UnblindingRequestListResponse,
)
from app.services.data_lock_service import get_data_lock_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/data-locks",
    tags=["Data Review & Lock"],
)


# ---------------------------------------------------------------------------
# Lock CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/locks",
    response_model=DataLockListResponse,
    summary="List database locks",
    description="Retrieve database locks with optional filtering by trial, status, and lock type.",
)
async def list_locks(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[LockStatus] = Query(None, description="Filter by lock status"),
    lock_type: Optional[LockType] = Query(None, description="Filter by lock type"),
) -> DataLockListResponse:
    svc = get_data_lock_service()
    items = svc.list_locks(trial_id=trial_id, status=status, lock_type=lock_type)
    return DataLockListResponse(items=items, total=len(items))


@router.get(
    "/locks/{lock_id}",
    response_model=DataLock,
    summary="Get a database lock",
)
async def get_lock(lock_id: str) -> DataLock:
    svc = get_data_lock_service()
    lock = svc.get_lock(lock_id)
    if lock is None:
        raise HTTPException(status_code=404, detail=f"Lock '{lock_id}' not found")
    return lock


@router.post(
    "/locks",
    response_model=DataLock,
    status_code=201,
    summary="Create a database lock",
)
async def create_lock(payload: DataLockCreate) -> DataLock:
    svc = get_data_lock_service()
    return svc.create_lock(payload)


@router.put(
    "/locks/{lock_id}",
    response_model=DataLock,
    summary="Update a database lock",
)
async def update_lock(lock_id: str, payload: DataLockUpdate) -> DataLock:
    svc = get_data_lock_service()
    try:
        updated = svc.update_lock(lock_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Lock '{lock_id}' not found")
    return updated


@router.delete(
    "/locks/{lock_id}",
    status_code=204,
    summary="Delete a database lock",
)
async def delete_lock(lock_id: str) -> None:
    svc = get_data_lock_service()
    try:
        deleted = svc.delete_lock(lock_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Lock '{lock_id}' not found")


# ---------------------------------------------------------------------------
# Lock Lifecycle
# ---------------------------------------------------------------------------


@router.post(
    "/locks/{lock_id}/start",
    response_model=DataLock,
    summary="Start lock process",
    description="Transition a planned lock to in_progress to begin pre-lock activities.",
)
async def start_lock_process(lock_id: str) -> DataLock:
    svc = get_data_lock_service()
    try:
        result = svc.start_lock_process(lock_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Lock '{lock_id}' not found")
    return result


@router.post(
    "/locks/{lock_id}/soft-lock",
    response_model=DataLock,
    summary="Execute soft lock",
    description="Execute a soft lock on the database. Data entry is restricted but corrections allowed.",
)
async def execute_soft_lock(lock_id: str, payload: LockExecute) -> DataLock:
    svc = get_data_lock_service()
    try:
        result = svc.execute_soft_lock(lock_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Lock '{lock_id}' not found")
    return result


@router.post(
    "/locks/{lock_id}/hard-lock",
    response_model=DataLock,
    summary="Execute hard lock",
    description="Execute a hard lock on the database. No further data modifications allowed.",
)
async def execute_hard_lock(lock_id: str, payload: LockExecute) -> DataLock:
    svc = get_data_lock_service()
    try:
        result = svc.execute_hard_lock(lock_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Lock '{lock_id}' not found")
    return result


@router.post(
    "/locks/{lock_id}/unlock",
    response_model=DataLock,
    summary="Unlock database",
    description="Remove a lock from a previously locked database. Requires justification and audit trail.",
)
async def unlock_database(lock_id: str, payload: LockUnlock) -> DataLock:
    svc = get_data_lock_service()
    try:
        result = svc.unlock(lock_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Lock '{lock_id}' not found")
    return result


@router.post(
    "/locks/{lock_id}/cancel",
    response_model=DataLock,
    summary="Cancel lock",
    description="Cancel a planned or in-progress lock.",
)
async def cancel_lock(lock_id: str) -> DataLock:
    svc = get_data_lock_service()
    try:
        result = svc.cancel_lock(lock_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Lock '{lock_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Pre-Lock Validation
# ---------------------------------------------------------------------------


@router.get(
    "/locks/{lock_id}/pre-lock-checks",
    response_model=PreLockSummary,
    summary="Run pre-lock validation checks",
    description="Run pre-lock validation including open queries, SDV completion, deviations, and clean data status.",
)
async def run_pre_lock_checks(lock_id: str) -> PreLockSummary:
    svc = get_data_lock_service()
    result = svc.run_pre_lock_checks(lock_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Lock '{lock_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Data Cuts
# ---------------------------------------------------------------------------


@router.get(
    "/data-cuts",
    response_model=DataCutListResponse,
    summary="List data cuts",
    description="Retrieve data cuts with optional filtering by lock.",
)
async def list_data_cuts(
    lock_id: Optional[str] = Query(None, description="Filter by lock ID"),
) -> DataCutListResponse:
    svc = get_data_lock_service()
    items = svc.list_data_cuts(lock_id=lock_id)
    return DataCutListResponse(items=items, total=len(items))


@router.get(
    "/data-cuts/{cut_id}",
    response_model=DataCut,
    summary="Get a data cut",
)
async def get_data_cut(cut_id: str) -> DataCut:
    svc = get_data_lock_service()
    cut = svc.get_data_cut(cut_id)
    if cut is None:
        raise HTTPException(status_code=404, detail=f"Data cut '{cut_id}' not found")
    return cut


@router.post(
    "/locks/{lock_id}/data-cuts",
    response_model=DataCut,
    status_code=201,
    summary="Create a data cut for a lock",
)
async def create_data_cut(lock_id: str, payload: DataCutCreate) -> DataCut:
    svc = get_data_lock_service()
    try:
        return svc.create_data_cut(lock_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete(
    "/data-cuts/{cut_id}",
    status_code=204,
    summary="Delete a data cut",
)
async def delete_data_cut(cut_id: str) -> None:
    svc = get_data_lock_service()
    deleted = svc.delete_data_cut(cut_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Data cut '{cut_id}' not found")


# ---------------------------------------------------------------------------
# Clean Data Records
# ---------------------------------------------------------------------------


@router.get(
    "/clean-data",
    response_model=CleanDataRecordListResponse,
    summary="List clean data records",
    description="Retrieve clean data records with optional filtering by lock, status, and subject.",
)
async def list_clean_data_records(
    lock_id: Optional[str] = Query(None, description="Filter by lock ID"),
    status: Optional[CleanDataStatus] = Query(None, description="Filter by clean data status"),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
) -> CleanDataRecordListResponse:
    svc = get_data_lock_service()
    items = svc.list_clean_data_records(lock_id=lock_id, status=status, subject_id=subject_id)
    return CleanDataRecordListResponse(items=items, total=len(items))


@router.get(
    "/clean-data/{record_id}",
    response_model=CleanDataRecord,
    summary="Get a clean data record",
)
async def get_clean_data_record(record_id: str) -> CleanDataRecord:
    svc = get_data_lock_service()
    record = svc.get_clean_data_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Clean data record '{record_id}' not found")
    return record


@router.post(
    "/locks/{lock_id}/clean-data",
    response_model=CleanDataRecord,
    status_code=201,
    summary="Create a clean data record for a lock",
)
async def create_clean_data_record(lock_id: str, payload: CleanDataRecordCreate) -> CleanDataRecord:
    svc = get_data_lock_service()
    try:
        return svc.create_clean_data_record(lock_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/clean-data/{record_id}",
    response_model=CleanDataRecord,
    summary="Update a clean data record",
)
async def update_clean_data_record(record_id: str, payload: CleanDataRecordUpdate) -> CleanDataRecord:
    svc = get_data_lock_service()
    updated = svc.update_clean_data_record(record_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Clean data record '{record_id}' not found")
    return updated


@router.post(
    "/clean-data/{record_id}/flag",
    response_model=CleanDataRecord,
    summary="Flag a data record",
    description="Flag specific fields in a data record for review.",
)
async def flag_data_record(
    record_id: str,
    flagged_fields: list[str],
    notes: Optional[str] = Query(None, description="Review notes"),
) -> CleanDataRecord:
    svc = get_data_lock_service()
    result = svc.flag_data(record_id, flagged_fields, notes)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Clean data record '{record_id}' not found")
    return result


@router.post(
    "/clean-data/{record_id}/mark-clean",
    response_model=CleanDataRecord,
    summary="Mark data record as clean",
    description="Mark a data record as clean after review.",
)
async def mark_data_clean(
    record_id: str,
    reviewer: str = Query(..., description="Reviewer name"),
) -> CleanDataRecord:
    svc = get_data_lock_service()
    result = svc.mark_clean(record_id, reviewer)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Clean data record '{record_id}' not found")
    return result


@router.get(
    "/locks/{lock_id}/clean-data-summary",
    response_model=dict,
    summary="Get clean data summary for a lock",
    description="Get aggregated clean data status counts for a specific lock.",
)
async def get_clean_data_summary(lock_id: str) -> dict:
    svc = get_data_lock_service()
    lock = svc.get_lock(lock_id)
    if lock is None:
        raise HTTPException(status_code=404, detail=f"Lock '{lock_id}' not found")
    return svc.get_clean_data_summary(lock_id)


# ---------------------------------------------------------------------------
# Unblinding Requests
# ---------------------------------------------------------------------------


@router.get(
    "/unblinding-requests",
    response_model=UnblindingRequestListResponse,
    summary="List unblinding requests",
    description="Retrieve unblinding requests with optional filtering by lock and execution status.",
)
async def list_unblinding_requests(
    lock_id: Optional[str] = Query(None, description="Filter by lock ID"),
    executed: Optional[bool] = Query(None, description="Filter by execution status"),
) -> UnblindingRequestListResponse:
    svc = get_data_lock_service()
    items = svc.list_unblinding_requests(lock_id=lock_id, executed=executed)
    return UnblindingRequestListResponse(items=items, total=len(items))


@router.get(
    "/unblinding-requests/{request_id}",
    response_model=UnblindingRequest,
    summary="Get an unblinding request",
)
async def get_unblinding_request(request_id: str) -> UnblindingRequest:
    svc = get_data_lock_service()
    req = svc.get_unblinding_request(request_id)
    if req is None:
        raise HTTPException(status_code=404, detail=f"Unblinding request '{request_id}' not found")
    return req


@router.post(
    "/locks/{lock_id}/unblinding-requests",
    response_model=UnblindingRequest,
    status_code=201,
    summary="Create an unblinding request",
    description="Request unblinding for a locked database. Requires justification.",
)
async def request_unblinding(lock_id: str, payload: UnblindingRequestCreate) -> UnblindingRequest:
    svc = get_data_lock_service()
    try:
        return svc.request_unblinding(lock_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/unblinding-requests/{request_id}/approve",
    response_model=UnblindingRequest,
    summary="Approve an unblinding request",
)
async def approve_unblinding(request_id: str, payload: UnblindingApproval) -> UnblindingRequest:
    svc = get_data_lock_service()
    try:
        result = svc.approve_unblinding(request_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unblinding request '{request_id}' not found")
    return result


@router.post(
    "/unblinding-requests/{request_id}/execute",
    response_model=UnblindingRequest,
    summary="Execute an approved unblinding",
    description="Execute an approved unblinding request, specifying which subjects to unblind.",
)
async def execute_unblinding(request_id: str, payload: UnblindingExecute) -> UnblindingRequest:
    svc = get_data_lock_service()
    try:
        result = svc.execute_unblinding(request_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unblinding request '{request_id}' not found")
    return result


@router.get(
    "/locks/{lock_id}/unblinding-audit",
    response_model=UnblindingRequestListResponse,
    summary="Get unblinding audit trail",
    description="Get complete unblinding audit trail for a lock.",
)
async def get_unblinding_audit(lock_id: str) -> UnblindingRequestListResponse:
    svc = get_data_lock_service()
    lock = svc.get_lock(lock_id)
    if lock is None:
        raise HTTPException(status_code=404, detail=f"Lock '{lock_id}' not found")
    items = svc.get_unblinding_audit(lock_id)
    return UnblindingRequestListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Lock Checklists
# ---------------------------------------------------------------------------


@router.get(
    "/checklists",
    response_model=LockChecklistListResponse,
    summary="List lock checklists",
    description="Retrieve lock checklists with optional filtering by lock.",
)
async def list_checklists(
    lock_id: Optional[str] = Query(None, description="Filter by lock ID"),
) -> LockChecklistListResponse:
    svc = get_data_lock_service()
    items = svc.list_checklists(lock_id=lock_id)
    return LockChecklistListResponse(items=items, total=len(items))


@router.get(
    "/checklists/{checklist_id}",
    response_model=LockChecklist,
    summary="Get a lock checklist",
)
async def get_checklist(checklist_id: str) -> LockChecklist:
    svc = get_data_lock_service()
    checklist = svc.get_checklist(checklist_id)
    if checklist is None:
        raise HTTPException(status_code=404, detail=f"Checklist '{checklist_id}' not found")
    return checklist


@router.post(
    "/locks/{lock_id}/checklists",
    response_model=LockChecklist,
    status_code=201,
    summary="Create a lock checklist",
)
async def create_checklist(lock_id: str, payload: LockChecklistCreate) -> LockChecklist:
    svc = get_data_lock_service()
    try:
        return svc.create_checklist(lock_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/checklists/{checklist_id}/items/{item_id}",
    response_model=LockChecklist,
    summary="Update a checklist item",
    description="Update the status, responsible person, or completion date of a checklist item.",
)
async def update_checklist_item(
    checklist_id: str,
    item_id: str,
    payload: LockChecklistItemUpdate,
) -> LockChecklist:
    svc = get_data_lock_service()
    try:
        result = svc.update_checklist_item(checklist_id, item_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Checklist '{checklist_id}' not found")
    return result


@router.get(
    "/checklists/{checklist_id}/completion",
    response_model=dict,
    summary="Get checklist completion stats",
    description="Get completion statistics for a lock checklist.",
)
async def get_checklist_completion(checklist_id: str) -> dict:
    svc = get_data_lock_service()
    result = svc.get_checklist_completion(checklist_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Checklist '{checklist_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=DataLockMetrics,
    summary="Get data lock metrics",
    description="Aggregated data lock metrics across all trials.",
)
async def get_metrics() -> DataLockMetrics:
    svc = get_data_lock_service()
    return svc.get_metrics()
