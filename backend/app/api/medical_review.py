"""Medical Review & Lab Data Review API endpoints (CLINICAL-14).

Provides comprehensive medical review operations: review task assignment and
tracking, medical coding (MedDRA, WHODrug) with auto-coding confidence scoring,
data listing generation and management, medical signal detection with risk ratio
calculation, review prioritization, and overdue escalation.

Endpoints:
    GET    /medical-review/tasks                              - List review tasks
    GET    /medical-review/tasks/{task_id}                    - Get single task
    POST   /medical-review/tasks                              - Create review task
    PUT    /medical-review/tasks/{task_id}                    - Update review task
    DELETE /medical-review/tasks/{task_id}                    - Delete review task
    GET    /medical-review/tasks/overdue                      - Overdue review tasks
    POST   /medical-review/tasks/escalate-overdue             - Auto-escalate overdue
    GET    /medical-review/coding                             - List coding tasks
    GET    /medical-review/coding/{task_id}                   - Get single coding task
    POST   /medical-review/coding                             - Create coding task (auto-code)
    PUT    /medical-review/coding/{task_id}                   - Update coding task
    GET    /medical-review/listings                           - List data listings
    GET    /medical-review/listings/{listing_id}              - Get single listing
    POST   /medical-review/listings                           - Generate data listing
    DELETE /medical-review/listings/{listing_id}              - Delete listing
    GET    /medical-review/signals                            - List medical signals
    GET    /medical-review/signals/{signal_id}                - Get single signal
    POST   /medical-review/signals                            - Create signal
    PUT    /medical-review/signals/{signal_id}                - Update signal
    DELETE /medical-review/signals/{signal_id}                - Delete signal
    POST   /medical-review/signals/detect/{trial_id}         - Run signal detection
    GET    /medical-review/metrics                            - Dashboard metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.medical_review import (
    CodingDictionary,
    CodingStatus,
    CodingTask,
    CodingTaskCreate,
    CodingTaskListResponse,
    CodingTaskUpdate,
    DataListing,
    DataListingCreate,
    DataListingListResponse,
    ListingType,
    MedicalReviewMetrics,
    MedicalReviewTask,
    MedicalReviewTaskCreate,
    MedicalReviewTaskListResponse,
    MedicalReviewTaskUpdate,
    MedicalSignal,
    MedicalSignalCreate,
    MedicalSignalListResponse,
    MedicalSignalUpdate,
    ReviewPriority,
    ReviewStatus,
    ReviewType,
    SignalCategory,
)
from app.services.medical_review_service import get_medical_review_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/medical-review",
    tags=["Medical Review"],
)


# ---------------------------------------------------------------------------
# Review Task Management
# ---------------------------------------------------------------------------


@router.get(
    "/tasks",
    response_model=MedicalReviewTaskListResponse,
    summary="List medical review tasks",
    description="Retrieve review tasks with optional filtering by trial, type, status, priority, and reviewer.",
)
async def list_review_tasks(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    review_type: Optional[ReviewType] = Query(None, description="Filter by review type"),
    status: Optional[ReviewStatus] = Query(None, description="Filter by status"),
    priority: Optional[ReviewPriority] = Query(None, description="Filter by priority"),
    assigned_reviewer: Optional[str] = Query(None, description="Filter by assigned reviewer"),
) -> MedicalReviewTaskListResponse:
    svc = get_medical_review_service()
    items = svc.list_review_tasks(
        trial_id=trial_id,
        review_type=review_type,
        status=status,
        priority=priority,
        assigned_reviewer=assigned_reviewer,
    )
    return MedicalReviewTaskListResponse(items=items, total=len(items))


@router.get(
    "/tasks/overdue",
    response_model=MedicalReviewTaskListResponse,
    summary="Get overdue review tasks",
    description="Retrieve review tasks pending for more than 48 hours.",
)
async def get_overdue_reviews() -> MedicalReviewTaskListResponse:
    svc = get_medical_review_service()
    items = svc.get_overdue_reviews()
    return MedicalReviewTaskListResponse(items=items, total=len(items))


@router.post(
    "/tasks/escalate-overdue",
    response_model=MedicalReviewTaskListResponse,
    summary="Auto-escalate overdue review tasks",
    description="Automatically escalate all review tasks pending for more than 48 hours.",
)
async def escalate_overdue_reviews() -> MedicalReviewTaskListResponse:
    svc = get_medical_review_service()
    items = svc.escalate_overdue_reviews()
    return MedicalReviewTaskListResponse(items=items, total=len(items))


@router.get(
    "/tasks/{task_id}",
    response_model=MedicalReviewTask,
    summary="Get a medical review task",
)
async def get_review_task(task_id: str) -> MedicalReviewTask:
    svc = get_medical_review_service()
    task = svc.get_review_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Review task '{task_id}' not found")
    return task


@router.post(
    "/tasks",
    response_model=MedicalReviewTask,
    status_code=201,
    summary="Create a medical review task",
)
async def create_review_task(payload: MedicalReviewTaskCreate) -> MedicalReviewTask:
    svc = get_medical_review_service()
    return svc.create_review_task(payload)


@router.put(
    "/tasks/{task_id}",
    response_model=MedicalReviewTask,
    summary="Update a medical review task",
)
async def update_review_task(task_id: str, payload: MedicalReviewTaskUpdate) -> MedicalReviewTask:
    svc = get_medical_review_service()
    updated = svc.update_review_task(task_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Review task '{task_id}' not found")
    return updated


@router.delete(
    "/tasks/{task_id}",
    status_code=204,
    summary="Delete a medical review task",
)
async def delete_review_task(task_id: str) -> None:
    svc = get_medical_review_service()
    deleted = svc.delete_review_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Review task '{task_id}' not found")


# ---------------------------------------------------------------------------
# Coding Tasks
# ---------------------------------------------------------------------------


@router.get(
    "/coding",
    response_model=CodingTaskListResponse,
    summary="List coding tasks",
    description="Retrieve coding tasks with optional filtering by dictionary, status, and auto-coded flag.",
)
async def list_coding_tasks(
    dictionary: Optional[CodingDictionary] = Query(None, description="Filter by dictionary"),
    status: Optional[CodingStatus] = Query(None, description="Filter by coding status"),
    auto_coded: Optional[bool] = Query(None, description="Filter by auto-coded flag"),
) -> CodingTaskListResponse:
    svc = get_medical_review_service()
    items = svc.list_coding_tasks(
        dictionary=dictionary, status=status, auto_coded=auto_coded,
    )
    return CodingTaskListResponse(items=items, total=len(items))


@router.get(
    "/coding/{task_id}",
    response_model=CodingTask,
    summary="Get a coding task",
)
async def get_coding_task(task_id: str) -> CodingTask:
    svc = get_medical_review_service()
    task = svc.get_coding_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Coding task '{task_id}' not found")
    return task


@router.post(
    "/coding",
    response_model=CodingTask,
    status_code=201,
    summary="Create a coding task (with auto-coding)",
    description="Create a coding task. The system will attempt auto-coding: "
                "confidence > 0.9 is auto-accepted, 0.7-0.9 needs manual review, < 0.7 raises a query.",
)
async def create_coding_task(payload: CodingTaskCreate) -> CodingTask:
    svc = get_medical_review_service()
    return svc.create_coding_task(payload)


@router.put(
    "/coding/{task_id}",
    response_model=CodingTask,
    summary="Update a coding task",
    description="Update coding task details including manual coding, verification.",
)
async def update_coding_task(task_id: str, payload: CodingTaskUpdate) -> CodingTask:
    svc = get_medical_review_service()
    updated = svc.update_coding_task(task_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Coding task '{task_id}' not found")
    return updated


# ---------------------------------------------------------------------------
# Data Listings
# ---------------------------------------------------------------------------


@router.get(
    "/listings",
    response_model=DataListingListResponse,
    summary="List data listings",
    description="Retrieve generated data listings with optional filtering by trial and listing type.",
)
async def list_data_listings(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    listing_type: Optional[ListingType] = Query(None, description="Filter by listing type"),
) -> DataListingListResponse:
    svc = get_medical_review_service()
    items = svc.list_data_listings(trial_id=trial_id, listing_type=listing_type)
    return DataListingListResponse(items=items, total=len(items))


@router.get(
    "/listings/{listing_id}",
    response_model=DataListing,
    summary="Get a data listing",
)
async def get_data_listing(listing_id: str) -> DataListing:
    svc = get_medical_review_service()
    listing = svc.get_data_listing(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail=f"Data listing '{listing_id}' not found")
    return listing


@router.post(
    "/listings",
    response_model=DataListing,
    status_code=201,
    summary="Generate a data listing",
    description="Generate a new data listing for review based on trial and listing type.",
)
async def create_data_listing(payload: DataListingCreate) -> DataListing:
    svc = get_medical_review_service()
    return svc.create_data_listing(payload)


@router.delete(
    "/listings/{listing_id}",
    status_code=204,
    summary="Delete a data listing",
)
async def delete_data_listing(listing_id: str) -> None:
    svc = get_medical_review_service()
    deleted = svc.delete_data_listing(listing_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Data listing '{listing_id}' not found")


# ---------------------------------------------------------------------------
# Medical Signals
# ---------------------------------------------------------------------------


@router.get(
    "/signals",
    response_model=MedicalSignalListResponse,
    summary="List medical signals",
    description="Retrieve medical signals with optional filtering by trial, category, and action required.",
)
async def list_signals(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    signal_category: Optional[SignalCategory] = Query(None, description="Filter by signal category"),
    action_required: Optional[bool] = Query(None, description="Filter by action required"),
) -> MedicalSignalListResponse:
    svc = get_medical_review_service()
    items = svc.list_signals(
        trial_id=trial_id, signal_category=signal_category, action_required=action_required,
    )
    return MedicalSignalListResponse(items=items, total=len(items))


@router.get(
    "/signals/{signal_id}",
    response_model=MedicalSignal,
    summary="Get a medical signal",
)
async def get_signal(signal_id: str) -> MedicalSignal:
    svc = get_medical_review_service()
    signal = svc.get_signal(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail=f"Signal '{signal_id}' not found")
    return signal


@router.post(
    "/signals",
    response_model=MedicalSignal,
    status_code=201,
    summary="Create a medical signal",
    description="Create a medical signal record. Risk ratio and p-value are auto-calculated.",
)
async def create_signal(payload: MedicalSignalCreate) -> MedicalSignal:
    svc = get_medical_review_service()
    return svc.create_signal(payload)


@router.put(
    "/signals/{signal_id}",
    response_model=MedicalSignal,
    summary="Update a medical signal",
)
async def update_signal(signal_id: str, payload: MedicalSignalUpdate) -> MedicalSignal:
    svc = get_medical_review_service()
    updated = svc.update_signal(signal_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Signal '{signal_id}' not found")
    return updated


@router.delete(
    "/signals/{signal_id}",
    status_code=204,
    summary="Delete a medical signal",
)
async def delete_signal(signal_id: str) -> None:
    svc = get_medical_review_service()
    deleted = svc.delete_signal(signal_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Signal '{signal_id}' not found")


@router.post(
    "/signals/detect/{trial_id}",
    response_model=MedicalSignalListResponse,
    summary="Run signal detection for a trial",
    description="Detect signals where risk ratio > 1.5 and p-value < 0.05 for a given trial.",
)
async def detect_signals(trial_id: str) -> MedicalSignalListResponse:
    svc = get_medical_review_service()
    items = svc.detect_signals(trial_id)
    return MedicalSignalListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=MedicalReviewMetrics,
    summary="Get medical review dashboard metrics",
    description="Aggregated medical review metrics including task counts, coding accuracy, and signal status.",
)
async def get_metrics() -> MedicalReviewMetrics:
    svc = get_medical_review_service()
    return svc.get_metrics()
