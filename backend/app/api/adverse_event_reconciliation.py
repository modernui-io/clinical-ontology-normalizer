"""Adverse Event Reconciliation (AER-REC) API endpoints.

Provides CRUD operations for reconciliation tasks, discrepancy records,
line-item comparisons, reconciliation sign-offs, and aggregated metrics.

Endpoints:
    GET    /adverse-event-reconciliation/reconciliation-tasks              - List tasks
    GET    /adverse-event-reconciliation/reconciliation-tasks/{task_id}    - Get task
    POST   /adverse-event-reconciliation/reconciliation-tasks              - Create task
    PUT    /adverse-event-reconciliation/reconciliation-tasks/{task_id}    - Update task
    DELETE /adverse-event-reconciliation/reconciliation-tasks/{task_id}    - Delete task
    GET    /adverse-event-reconciliation/discrepancy-records               - List records
    GET    /adverse-event-reconciliation/discrepancy-records/{record_id}   - Get record
    POST   /adverse-event-reconciliation/discrepancy-records               - Create record
    PUT    /adverse-event-reconciliation/discrepancy-records/{record_id}   - Update record
    DELETE /adverse-event-reconciliation/discrepancy-records/{record_id}   - Delete record
    GET    /adverse-event-reconciliation/line-item-comparisons             - List comparisons
    GET    /adverse-event-reconciliation/line-item-comparisons/{id}        - Get comparison
    POST   /adverse-event-reconciliation/line-item-comparisons             - Create comparison
    PUT    /adverse-event-reconciliation/line-item-comparisons/{id}        - Update comparison
    DELETE /adverse-event-reconciliation/line-item-comparisons/{id}        - Delete comparison
    GET    /adverse-event-reconciliation/reconciliation-sign-offs          - List sign-offs
    GET    /adverse-event-reconciliation/reconciliation-sign-offs/{id}     - Get sign-off
    POST   /adverse-event-reconciliation/reconciliation-sign-offs          - Create sign-off
    PUT    /adverse-event-reconciliation/reconciliation-sign-offs/{id}     - Update sign-off
    DELETE /adverse-event-reconciliation/reconciliation-sign-offs/{id}     - Delete sign-off
    GET    /adverse-event-reconciliation/metrics                           - Get metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.adverse_event_reconciliation import (
    AdverseEventReconciliationMetrics,
    DiscrepancyRecord,
    DiscrepancyRecordCreate,
    DiscrepancyRecordListResponse,
    DiscrepancyRecordUpdate,
    LineItemComparison,
    LineItemComparisonCreate,
    LineItemComparisonListResponse,
    LineItemComparisonUpdate,
    ReconciliationSignOff,
    ReconciliationSignOffCreate,
    ReconciliationSignOffListResponse,
    ReconciliationSignOffUpdate,
    ReconciliationTask,
    ReconciliationTaskCreate,
    ReconciliationTaskListResponse,
    ReconciliationTaskUpdate,
)
from app.services.adverse_event_reconciliation_service import (
    get_adverse_event_reconciliation_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/adverse-event-reconciliation",
    tags=["Adverse Event Reconciliation"],
)


# ---------------------------------------------------------------------------
# Reconciliation Tasks
# ---------------------------------------------------------------------------


@router.get(
    "/reconciliation-tasks",
    response_model=ReconciliationTaskListResponse,
    summary="List reconciliation tasks",
    description="Retrieve reconciliation tasks with optional filtering by trial ID.",
)
async def list_reconciliation_tasks(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> ReconciliationTaskListResponse:
    svc = get_adverse_event_reconciliation_service()
    items = svc.list_reconciliation_tasks(trial_id=trial_id)
    return ReconciliationTaskListResponse(items=items, total=len(items))


@router.get(
    "/reconciliation-tasks/{task_id}",
    response_model=ReconciliationTask,
    summary="Get a reconciliation task",
)
async def get_reconciliation_task(task_id: str) -> ReconciliationTask:
    svc = get_adverse_event_reconciliation_service()
    task = svc.get_reconciliation_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Reconciliation task '{task_id}' not found")
    return task


@router.post(
    "/reconciliation-tasks",
    response_model=ReconciliationTask,
    status_code=201,
    summary="Create a reconciliation task",
)
async def create_reconciliation_task(payload: ReconciliationTaskCreate) -> ReconciliationTask:
    svc = get_adverse_event_reconciliation_service()
    return svc.create_reconciliation_task(payload)


@router.put(
    "/reconciliation-tasks/{task_id}",
    response_model=ReconciliationTask,
    summary="Update a reconciliation task",
)
async def update_reconciliation_task(
    task_id: str, payload: ReconciliationTaskUpdate
) -> ReconciliationTask:
    svc = get_adverse_event_reconciliation_service()
    updated = svc.update_reconciliation_task(task_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Reconciliation task '{task_id}' not found")
    return updated


@router.delete(
    "/reconciliation-tasks/{task_id}",
    status_code=204,
    summary="Delete a reconciliation task",
)
async def delete_reconciliation_task(task_id: str) -> None:
    svc = get_adverse_event_reconciliation_service()
    deleted = svc.delete_reconciliation_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Reconciliation task '{task_id}' not found")


# ---------------------------------------------------------------------------
# Discrepancy Records
# ---------------------------------------------------------------------------


@router.get(
    "/discrepancy-records",
    response_model=DiscrepancyRecordListResponse,
    summary="List discrepancy records",
    description="Retrieve discrepancy records with optional filtering by trial ID.",
)
async def list_discrepancy_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> DiscrepancyRecordListResponse:
    svc = get_adverse_event_reconciliation_service()
    items = svc.list_discrepancy_records(trial_id=trial_id)
    return DiscrepancyRecordListResponse(items=items, total=len(items))


@router.get(
    "/discrepancy-records/{record_id}",
    response_model=DiscrepancyRecord,
    summary="Get a discrepancy record",
)
async def get_discrepancy_record(record_id: str) -> DiscrepancyRecord:
    svc = get_adverse_event_reconciliation_service()
    record = svc.get_discrepancy_record(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Discrepancy record '{record_id}' not found")
    return record


@router.post(
    "/discrepancy-records",
    response_model=DiscrepancyRecord,
    status_code=201,
    summary="Create a discrepancy record",
)
async def create_discrepancy_record(payload: DiscrepancyRecordCreate) -> DiscrepancyRecord:
    svc = get_adverse_event_reconciliation_service()
    return svc.create_discrepancy_record(payload)


@router.put(
    "/discrepancy-records/{record_id}",
    response_model=DiscrepancyRecord,
    summary="Update a discrepancy record",
)
async def update_discrepancy_record(
    record_id: str, payload: DiscrepancyRecordUpdate
) -> DiscrepancyRecord:
    svc = get_adverse_event_reconciliation_service()
    updated = svc.update_discrepancy_record(record_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Discrepancy record '{record_id}' not found")
    return updated


@router.delete(
    "/discrepancy-records/{record_id}",
    status_code=204,
    summary="Delete a discrepancy record",
)
async def delete_discrepancy_record(record_id: str) -> None:
    svc = get_adverse_event_reconciliation_service()
    deleted = svc.delete_discrepancy_record(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Discrepancy record '{record_id}' not found")


# ---------------------------------------------------------------------------
# Line Item Comparisons
# ---------------------------------------------------------------------------


@router.get(
    "/line-item-comparisons",
    response_model=LineItemComparisonListResponse,
    summary="List line item comparisons",
    description="Retrieve line item comparisons with optional filtering by trial ID.",
)
async def list_line_item_comparisons(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> LineItemComparisonListResponse:
    svc = get_adverse_event_reconciliation_service()
    items = svc.list_line_item_comparisons(trial_id=trial_id)
    return LineItemComparisonListResponse(items=items, total=len(items))


@router.get(
    "/line-item-comparisons/{comparison_id}",
    response_model=LineItemComparison,
    summary="Get a line item comparison",
)
async def get_line_item_comparison(comparison_id: str) -> LineItemComparison:
    svc = get_adverse_event_reconciliation_service()
    comparison = svc.get_line_item_comparison(comparison_id)
    if comparison is None:
        raise HTTPException(
            status_code=404, detail=f"Line item comparison '{comparison_id}' not found"
        )
    return comparison


@router.post(
    "/line-item-comparisons",
    response_model=LineItemComparison,
    status_code=201,
    summary="Create a line item comparison",
)
async def create_line_item_comparison(payload: LineItemComparisonCreate) -> LineItemComparison:
    svc = get_adverse_event_reconciliation_service()
    return svc.create_line_item_comparison(payload)


@router.put(
    "/line-item-comparisons/{comparison_id}",
    response_model=LineItemComparison,
    summary="Update a line item comparison",
)
async def update_line_item_comparison(
    comparison_id: str, payload: LineItemComparisonUpdate
) -> LineItemComparison:
    svc = get_adverse_event_reconciliation_service()
    updated = svc.update_line_item_comparison(comparison_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Line item comparison '{comparison_id}' not found"
        )
    return updated


@router.delete(
    "/line-item-comparisons/{comparison_id}",
    status_code=204,
    summary="Delete a line item comparison",
)
async def delete_line_item_comparison(comparison_id: str) -> None:
    svc = get_adverse_event_reconciliation_service()
    deleted = svc.delete_line_item_comparison(comparison_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Line item comparison '{comparison_id}' not found"
        )


# ---------------------------------------------------------------------------
# Reconciliation Sign-Offs
# ---------------------------------------------------------------------------


@router.get(
    "/reconciliation-sign-offs",
    response_model=ReconciliationSignOffListResponse,
    summary="List reconciliation sign-offs",
    description="Retrieve reconciliation sign-offs with optional filtering by trial ID.",
)
async def list_reconciliation_sign_offs(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> ReconciliationSignOffListResponse:
    svc = get_adverse_event_reconciliation_service()
    items = svc.list_reconciliation_sign_offs(trial_id=trial_id)
    return ReconciliationSignOffListResponse(items=items, total=len(items))


@router.get(
    "/reconciliation-sign-offs/{sign_off_id}",
    response_model=ReconciliationSignOff,
    summary="Get a reconciliation sign-off",
)
async def get_reconciliation_sign_off(sign_off_id: str) -> ReconciliationSignOff:
    svc = get_adverse_event_reconciliation_service()
    sign_off = svc.get_reconciliation_sign_off(sign_off_id)
    if sign_off is None:
        raise HTTPException(
            status_code=404, detail=f"Reconciliation sign-off '{sign_off_id}' not found"
        )
    return sign_off


@router.post(
    "/reconciliation-sign-offs",
    response_model=ReconciliationSignOff,
    status_code=201,
    summary="Create a reconciliation sign-off",
)
async def create_reconciliation_sign_off(
    payload: ReconciliationSignOffCreate,
) -> ReconciliationSignOff:
    svc = get_adverse_event_reconciliation_service()
    return svc.create_reconciliation_sign_off(payload)


@router.put(
    "/reconciliation-sign-offs/{sign_off_id}",
    response_model=ReconciliationSignOff,
    summary="Update a reconciliation sign-off",
)
async def update_reconciliation_sign_off(
    sign_off_id: str, payload: ReconciliationSignOffUpdate
) -> ReconciliationSignOff:
    svc = get_adverse_event_reconciliation_service()
    updated = svc.update_reconciliation_sign_off(sign_off_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Reconciliation sign-off '{sign_off_id}' not found"
        )
    return updated


@router.delete(
    "/reconciliation-sign-offs/{sign_off_id}",
    status_code=204,
    summary="Delete a reconciliation sign-off",
)
async def delete_reconciliation_sign_off(sign_off_id: str) -> None:
    svc = get_adverse_event_reconciliation_service()
    deleted = svc.delete_reconciliation_sign_off(sign_off_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Reconciliation sign-off '{sign_off_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=AdverseEventReconciliationMetrics,
    summary="Get adverse event reconciliation metrics",
    description="Aggregated metrics across reconciliation tasks, discrepancies, comparisons, and sign-offs.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> AdverseEventReconciliationMetrics:
    svc = get_adverse_event_reconciliation_service()
    return svc.get_metrics(trial_id=trial_id)
