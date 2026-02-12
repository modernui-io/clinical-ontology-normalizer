"""Clinical Data Review Management API endpoints (DATA-REV).

Provides comprehensive clinical data review operations: data review listings,
data query management, data cleaning tasks, edit check management, reviewer
assignments, and data review operational metrics.

Endpoints:
    GET    /clinical-data-review/listings                           - List data review listings
    GET    /clinical-data-review/listings/{listing_id}              - Get single listing
    POST   /clinical-data-review/listings                           - Create listing
    PUT    /clinical-data-review/listings/{listing_id}              - Update listing
    DELETE /clinical-data-review/listings/{listing_id}              - Delete listing
    GET    /clinical-data-review/queries                            - List data queries
    GET    /clinical-data-review/queries/{query_id}                 - Get single query
    POST   /clinical-data-review/queries                            - Create query
    PUT    /clinical-data-review/queries/{query_id}                 - Update query
    DELETE /clinical-data-review/queries/{query_id}                 - Delete query
    GET    /clinical-data-review/cleaning-tasks                     - List cleaning tasks
    GET    /clinical-data-review/cleaning-tasks/{task_id}           - Get single task
    POST   /clinical-data-review/cleaning-tasks                     - Create task
    PUT    /clinical-data-review/cleaning-tasks/{task_id}           - Update task
    DELETE /clinical-data-review/cleaning-tasks/{task_id}           - Delete task
    GET    /clinical-data-review/edit-checks                        - List edit checks
    GET    /clinical-data-review/edit-checks/{check_id}             - Get single check
    POST   /clinical-data-review/edit-checks                        - Create check
    PUT    /clinical-data-review/edit-checks/{check_id}             - Update check
    DELETE /clinical-data-review/edit-checks/{check_id}             - Delete check
    GET    /clinical-data-review/reviewer-assignments               - List assignments
    GET    /clinical-data-review/reviewer-assignments/{id}          - Get single assignment
    POST   /clinical-data-review/reviewer-assignments               - Create assignment
    PUT    /clinical-data-review/reviewer-assignments/{id}          - Update assignment
    DELETE /clinical-data-review/reviewer-assignments/{id}          - Delete assignment
    GET    /clinical-data-review/metrics                            - Review metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.clinical_data_review import (
    ClinicalDataReviewMetrics,
    DataCleaningTask,
    DataCleaningTaskCreate,
    DataCleaningTaskListResponse,
    DataCleaningTaskUpdate,
    DataQuery,
    DataQueryCreate,
    DataQueryListResponse,
    DataQueryUpdate,
    DataReviewListing,
    DataReviewListingCreate,
    DataReviewListingListResponse,
    DataReviewListingUpdate,
    EditCheck,
    EditCheckCreate,
    EditCheckListResponse,
    EditCheckUpdate,
    ReviewerAssignment,
    ReviewerAssignmentCreate,
    ReviewerAssignmentListResponse,
    ReviewerAssignmentUpdate,
)
from app.services.clinical_data_review_service import get_clinical_data_review_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/clinical-data-review",
    tags=["Clinical Data Review"],
)


# ---------------------------------------------------------------------------
# Data Review Listings
# ---------------------------------------------------------------------------


@router.get(
    "/listings",
    response_model=DataReviewListingListResponse,
    summary="List data review listings",
    description="Retrieve data review listings with optional filtering by trial ID.",
)
async def list_data_review_listings(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> DataReviewListingListResponse:
    svc = get_clinical_data_review_service()
    items = svc.list_data_review_listings(trial_id=trial_id)
    return DataReviewListingListResponse(items=items, total=len(items))


@router.get(
    "/listings/{listing_id}",
    response_model=DataReviewListing,
    summary="Get a data review listing",
)
async def get_data_review_listing(listing_id: str) -> DataReviewListing:
    svc = get_clinical_data_review_service()
    listing = svc.get_data_review_listing(listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail=f"Listing '{listing_id}' not found")
    return listing


@router.post(
    "/listings",
    response_model=DataReviewListing,
    status_code=201,
    summary="Create a data review listing",
)
async def create_data_review_listing(payload: DataReviewListingCreate) -> DataReviewListing:
    svc = get_clinical_data_review_service()
    return svc.create_data_review_listing(payload)


@router.put(
    "/listings/{listing_id}",
    response_model=DataReviewListing,
    summary="Update a data review listing",
)
async def update_data_review_listing(
    listing_id: str, payload: DataReviewListingUpdate
) -> DataReviewListing:
    svc = get_clinical_data_review_service()
    updated = svc.update_data_review_listing(listing_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Listing '{listing_id}' not found")
    return updated


@router.delete(
    "/listings/{listing_id}",
    status_code=204,
    summary="Delete a data review listing",
)
async def delete_data_review_listing(listing_id: str) -> None:
    svc = get_clinical_data_review_service()
    deleted = svc.delete_data_review_listing(listing_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Listing '{listing_id}' not found")


# ---------------------------------------------------------------------------
# Data Queries
# ---------------------------------------------------------------------------


@router.get(
    "/queries",
    response_model=DataQueryListResponse,
    summary="List data queries",
    description="Retrieve data queries with optional filtering by trial ID.",
)
async def list_data_queries(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> DataQueryListResponse:
    svc = get_clinical_data_review_service()
    items = svc.list_data_queries(trial_id=trial_id)
    return DataQueryListResponse(items=items, total=len(items))


@router.get(
    "/queries/{query_id}",
    response_model=DataQuery,
    summary="Get a data query",
)
async def get_data_query(query_id: str) -> DataQuery:
    svc = get_clinical_data_review_service()
    query = svc.get_data_query(query_id)
    if query is None:
        raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found")
    return query


@router.post(
    "/queries",
    response_model=DataQuery,
    status_code=201,
    summary="Create a data query",
)
async def create_data_query(payload: DataQueryCreate) -> DataQuery:
    svc = get_clinical_data_review_service()
    return svc.create_data_query(payload)


@router.put(
    "/queries/{query_id}",
    response_model=DataQuery,
    summary="Update a data query",
)
async def update_data_query(query_id: str, payload: DataQueryUpdate) -> DataQuery:
    svc = get_clinical_data_review_service()
    updated = svc.update_data_query(query_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found")
    return updated


@router.delete(
    "/queries/{query_id}",
    status_code=204,
    summary="Delete a data query",
)
async def delete_data_query(query_id: str) -> None:
    svc = get_clinical_data_review_service()
    deleted = svc.delete_data_query(query_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found")


# ---------------------------------------------------------------------------
# Data Cleaning Tasks
# ---------------------------------------------------------------------------


@router.get(
    "/cleaning-tasks",
    response_model=DataCleaningTaskListResponse,
    summary="List data cleaning tasks",
    description="Retrieve data cleaning tasks with optional filtering by trial ID.",
)
async def list_data_cleaning_tasks(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> DataCleaningTaskListResponse:
    svc = get_clinical_data_review_service()
    items = svc.list_data_cleaning_tasks(trial_id=trial_id)
    return DataCleaningTaskListResponse(items=items, total=len(items))


@router.get(
    "/cleaning-tasks/{task_id}",
    response_model=DataCleaningTask,
    summary="Get a data cleaning task",
)
async def get_data_cleaning_task(task_id: str) -> DataCleaningTask:
    svc = get_clinical_data_review_service()
    task = svc.get_data_cleaning_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Cleaning task '{task_id}' not found")
    return task


@router.post(
    "/cleaning-tasks",
    response_model=DataCleaningTask,
    status_code=201,
    summary="Create a data cleaning task",
)
async def create_data_cleaning_task(payload: DataCleaningTaskCreate) -> DataCleaningTask:
    svc = get_clinical_data_review_service()
    return svc.create_data_cleaning_task(payload)


@router.put(
    "/cleaning-tasks/{task_id}",
    response_model=DataCleaningTask,
    summary="Update a data cleaning task",
)
async def update_data_cleaning_task(
    task_id: str, payload: DataCleaningTaskUpdate
) -> DataCleaningTask:
    svc = get_clinical_data_review_service()
    updated = svc.update_data_cleaning_task(task_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Cleaning task '{task_id}' not found")
    return updated


@router.delete(
    "/cleaning-tasks/{task_id}",
    status_code=204,
    summary="Delete a data cleaning task",
)
async def delete_data_cleaning_task(task_id: str) -> None:
    svc = get_clinical_data_review_service()
    deleted = svc.delete_data_cleaning_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Cleaning task '{task_id}' not found")


# ---------------------------------------------------------------------------
# Edit Checks
# ---------------------------------------------------------------------------


@router.get(
    "/edit-checks",
    response_model=EditCheckListResponse,
    summary="List edit checks",
    description="Retrieve edit checks with optional filtering by trial ID.",
)
async def list_edit_checks(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> EditCheckListResponse:
    svc = get_clinical_data_review_service()
    items = svc.list_edit_checks(trial_id=trial_id)
    return EditCheckListResponse(items=items, total=len(items))


@router.get(
    "/edit-checks/{check_id}",
    response_model=EditCheck,
    summary="Get an edit check",
)
async def get_edit_check(check_id: str) -> EditCheck:
    svc = get_clinical_data_review_service()
    check = svc.get_edit_check(check_id)
    if check is None:
        raise HTTPException(status_code=404, detail=f"Edit check '{check_id}' not found")
    return check


@router.post(
    "/edit-checks",
    response_model=EditCheck,
    status_code=201,
    summary="Create an edit check",
)
async def create_edit_check(payload: EditCheckCreate) -> EditCheck:
    svc = get_clinical_data_review_service()
    return svc.create_edit_check(payload)


@router.put(
    "/edit-checks/{check_id}",
    response_model=EditCheck,
    summary="Update an edit check",
)
async def update_edit_check(check_id: str, payload: EditCheckUpdate) -> EditCheck:
    svc = get_clinical_data_review_service()
    updated = svc.update_edit_check(check_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Edit check '{check_id}' not found")
    return updated


@router.delete(
    "/edit-checks/{check_id}",
    status_code=204,
    summary="Delete an edit check",
)
async def delete_edit_check(check_id: str) -> None:
    svc = get_clinical_data_review_service()
    deleted = svc.delete_edit_check(check_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Edit check '{check_id}' not found")


# ---------------------------------------------------------------------------
# Reviewer Assignments
# ---------------------------------------------------------------------------


@router.get(
    "/reviewer-assignments",
    response_model=ReviewerAssignmentListResponse,
    summary="List reviewer assignments",
    description="Retrieve reviewer assignments with optional filtering by trial ID.",
)
async def list_reviewer_assignments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> ReviewerAssignmentListResponse:
    svc = get_clinical_data_review_service()
    items = svc.list_reviewer_assignments(trial_id=trial_id)
    return ReviewerAssignmentListResponse(items=items, total=len(items))


@router.get(
    "/reviewer-assignments/{assignment_id}",
    response_model=ReviewerAssignment,
    summary="Get a reviewer assignment",
)
async def get_reviewer_assignment(assignment_id: str) -> ReviewerAssignment:
    svc = get_clinical_data_review_service()
    assignment = svc.get_reviewer_assignment(assignment_id)
    if assignment is None:
        raise HTTPException(
            status_code=404, detail=f"Reviewer assignment '{assignment_id}' not found"
        )
    return assignment


@router.post(
    "/reviewer-assignments",
    response_model=ReviewerAssignment,
    status_code=201,
    summary="Create a reviewer assignment",
)
async def create_reviewer_assignment(payload: ReviewerAssignmentCreate) -> ReviewerAssignment:
    svc = get_clinical_data_review_service()
    return svc.create_reviewer_assignment(payload)


@router.put(
    "/reviewer-assignments/{assignment_id}",
    response_model=ReviewerAssignment,
    summary="Update a reviewer assignment",
)
async def update_reviewer_assignment(
    assignment_id: str, payload: ReviewerAssignmentUpdate
) -> ReviewerAssignment:
    svc = get_clinical_data_review_service()
    updated = svc.update_reviewer_assignment(assignment_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Reviewer assignment '{assignment_id}' not found"
        )
    return updated


@router.delete(
    "/reviewer-assignments/{assignment_id}",
    status_code=204,
    summary="Delete a reviewer assignment",
)
async def delete_reviewer_assignment(assignment_id: str) -> None:
    svc = get_clinical_data_review_service()
    deleted = svc.delete_reviewer_assignment(assignment_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Reviewer assignment '{assignment_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=ClinicalDataReviewMetrics,
    summary="Get clinical data review metrics",
    description="Aggregated clinical data review metrics across all listings, queries, tasks, checks, and reviewers.",
)
async def get_metrics() -> ClinicalDataReviewMetrics:
    svc = get_clinical_data_review_service()
    return svc.get_metrics()
