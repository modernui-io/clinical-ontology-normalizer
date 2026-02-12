"""Safety Signal Detection (Pharmacovigilance) API endpoints.

Provides comprehensive signal detection operations: signal CRUD, lifecycle
transitions (new -> under_evaluation -> confirmed/refuted -> closed),
signal evaluations, and aggregated detection metrics.

Endpoints:
    GET    /signal-detection/signals                          - List signals
    GET    /signal-detection/signals/{signal_id}              - Get single signal
    POST   /signal-detection/signals                          - Create signal
    PUT    /signal-detection/signals/{signal_id}              - Update signal
    DELETE /signal-detection/signals/{signal_id}              - Delete signal
    POST   /signal-detection/signals/{signal_id}/evaluate     - Transition to under_evaluation
    POST   /signal-detection/signals/{signal_id}/confirm      - Confirm signal
    POST   /signal-detection/signals/{signal_id}/refute       - Refute signal
    POST   /signal-detection/signals/{signal_id}/close        - Close signal
    GET    /signal-detection/signals/{signal_id}/evaluations  - List evaluations for signal
    POST   /signal-detection/signals/{signal_id}/evaluations  - Create evaluation for signal
    GET    /signal-detection/metrics                          - Signal detection metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.signal_detection import (
    SafetySignal,
    SignalCreate,
    SignalEvaluation,
    SignalEvaluationCreate,
    SignalEvaluationListResponse,
    SignalListResponse,
    SignalMetrics,
    SignalPriority,
    SignalSource,
    SignalStatus,
    SignalUpdate,
)
from app.services.signal_detection_service import get_signal_detection_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/signal-detection",
    tags=["Signal Detection"],
)


# ---------------------------------------------------------------------------
# Signal CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/signals",
    response_model=SignalListResponse,
    summary="List safety signals",
    description="Retrieve safety signals with optional filtering by status, priority, source, and drug name.",
)
async def list_signals(
    status: Optional[SignalStatus] = Query(None, description="Filter by lifecycle status"),
    priority: Optional[SignalPriority] = Query(None, description="Filter by priority"),
    source: Optional[SignalSource] = Query(None, description="Filter by detection source"),
    drug_name: Optional[str] = Query(None, description="Filter by drug name"),
) -> SignalListResponse:
    svc = get_signal_detection_service()
    items = svc.list_signals(
        status=status, priority=priority, source=source, drug_name=drug_name,
    )
    return SignalListResponse(items=items, total=len(items))


@router.get(
    "/signals/{signal_id}",
    response_model=SafetySignal,
    summary="Get a safety signal",
)
async def get_signal(signal_id: str) -> SafetySignal:
    svc = get_signal_detection_service()
    signal = svc.get_signal(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail=f"Signal '{signal_id}' not found")
    return signal


@router.post(
    "/signals",
    response_model=SafetySignal,
    status_code=201,
    summary="Create a safety signal",
)
async def create_signal(payload: SignalCreate) -> SafetySignal:
    svc = get_signal_detection_service()
    return svc.create_signal(payload)


@router.put(
    "/signals/{signal_id}",
    response_model=SafetySignal,
    summary="Update a safety signal",
)
async def update_signal(signal_id: str, payload: SignalUpdate) -> SafetySignal:
    svc = get_signal_detection_service()
    updated = svc.update_signal(signal_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Signal '{signal_id}' not found")
    return updated


@router.delete(
    "/signals/{signal_id}",
    status_code=204,
    summary="Delete a safety signal",
)
async def delete_signal(signal_id: str) -> None:
    svc = get_signal_detection_service()
    deleted = svc.delete_signal(signal_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Signal '{signal_id}' not found")


# ---------------------------------------------------------------------------
# Signal Lifecycle Transitions
# ---------------------------------------------------------------------------


@router.post(
    "/signals/{signal_id}/evaluate",
    response_model=SafetySignal,
    summary="Transition signal to under_evaluation",
    description="Move a signal from 'new' to 'under_evaluation' status.",
)
async def evaluate_signal(signal_id: str) -> SafetySignal:
    svc = get_signal_detection_service()
    try:
        result = svc.evaluate_signal(signal_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Signal '{signal_id}' not found")
    return result


@router.post(
    "/signals/{signal_id}/confirm",
    response_model=SafetySignal,
    summary="Confirm a safety signal",
    description="Confirm a signal that is currently under_evaluation.",
)
async def confirm_signal(signal_id: str) -> SafetySignal:
    svc = get_signal_detection_service()
    try:
        result = svc.confirm_signal(signal_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Signal '{signal_id}' not found")
    return result


@router.post(
    "/signals/{signal_id}/refute",
    response_model=SafetySignal,
    summary="Refute a safety signal",
    description="Refute a signal that is currently under_evaluation.",
)
async def refute_signal(signal_id: str) -> SafetySignal:
    svc = get_signal_detection_service()
    try:
        result = svc.refute_signal(signal_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Signal '{signal_id}' not found")
    return result


@router.post(
    "/signals/{signal_id}/close",
    response_model=SafetySignal,
    summary="Close a safety signal",
    description="Close a signal that is confirmed or refuted.",
)
async def close_signal(signal_id: str) -> SafetySignal:
    svc = get_signal_detection_service()
    try:
        result = svc.close_signal(signal_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Signal '{signal_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Signal Evaluations
# ---------------------------------------------------------------------------


@router.get(
    "/signals/{signal_id}/evaluations",
    response_model=SignalEvaluationListResponse,
    summary="List evaluations for a signal",
    description="Retrieve all evaluations associated with a specific signal.",
)
async def list_evaluations(signal_id: str) -> SignalEvaluationListResponse:
    svc = get_signal_detection_service()
    signal = svc.get_signal(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail=f"Signal '{signal_id}' not found")
    items = svc.list_evaluations(signal_id)
    return SignalEvaluationListResponse(items=items, total=len(items))


@router.post(
    "/signals/{signal_id}/evaluations",
    response_model=SignalEvaluation,
    status_code=201,
    summary="Create an evaluation for a signal",
    description="Submit an evaluation for a specific safety signal.",
)
async def create_evaluation(
    signal_id: str, payload: SignalEvaluationCreate
) -> SignalEvaluation:
    svc = get_signal_detection_service()
    try:
        return svc.create_evaluation(signal_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=SignalMetrics,
    summary="Get signal detection metrics",
    description="Aggregated safety signal detection metrics including counts by status, "
                "priority, source, average disproportionality score, and evaluation totals.",
)
async def get_metrics() -> SignalMetrics:
    svc = get_signal_detection_service()
    return svc.get_metrics()
