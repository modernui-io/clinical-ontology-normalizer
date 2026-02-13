"""Lab Proficiency API endpoints (LAB-PROF).

Provides comprehensive lab proficiency operations: proficiency test tracking,
inter-lab comparison results, accreditation records, lab corrective actions,
and proficiency metrics.

Endpoints:
    GET    /lab-proficiency/proficiency-tests                           - List proficiency tests
    GET    /lab-proficiency/proficiency-tests/{test_id}                 - Get single test
    POST   /lab-proficiency/proficiency-tests                           - Create test
    PUT    /lab-proficiency/proficiency-tests/{test_id}                 - Update test
    DELETE /lab-proficiency/proficiency-tests/{test_id}                 - Delete test
    GET    /lab-proficiency/lab-comparisons                             - List lab comparisons
    GET    /lab-proficiency/lab-comparisons/{comparison_id}             - Get single comparison
    POST   /lab-proficiency/lab-comparisons                             - Create comparison
    PUT    /lab-proficiency/lab-comparisons/{comparison_id}             - Update comparison
    DELETE /lab-proficiency/lab-comparisons/{comparison_id}             - Delete comparison
    GET    /lab-proficiency/accreditation-records                       - List accreditation records
    GET    /lab-proficiency/accreditation-records/{record_id}           - Get single record
    POST   /lab-proficiency/accreditation-records                       - Create record
    PUT    /lab-proficiency/accreditation-records/{record_id}           - Update record
    DELETE /lab-proficiency/accreditation-records/{record_id}           - Delete record
    GET    /lab-proficiency/corrective-actions                          - List corrective actions
    GET    /lab-proficiency/corrective-actions/{action_id}              - Get single action
    POST   /lab-proficiency/corrective-actions                          - Create action
    PUT    /lab-proficiency/corrective-actions/{action_id}              - Update action
    DELETE /lab-proficiency/corrective-actions/{action_id}              - Delete action
    GET    /lab-proficiency/metrics                                     - Lab proficiency metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.lab_proficiency import (
    AccreditationRecord,
    AccreditationRecordCreate,
    AccreditationRecordListResponse,
    AccreditationRecordUpdate,
    AccreditationStatus,
    ComparisonStatus,
    CorrectiveActionPriority,
    LabComparison,
    LabComparisonCreate,
    LabComparisonListResponse,
    LabComparisonUpdate,
    LabCorrectiveAction,
    LabCorrectiveActionCreate,
    LabCorrectiveActionListResponse,
    LabCorrectiveActionUpdate,
    LabProficiencyMetrics,
    ProficiencyTest,
    ProficiencyTestCreate,
    ProficiencyTestListResponse,
    ProficiencyTestUpdate,
    TestCategory,
    TestResult,
)
from app.services.lab_proficiency_service import get_lab_proficiency_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/lab-proficiency",
    tags=["Lab Proficiency"],
)


# ---------------------------------------------------------------------------
# Proficiency Tests
# ---------------------------------------------------------------------------


@router.get(
    "/proficiency-tests",
    response_model=ProficiencyTestListResponse,
    summary="List proficiency tests",
    description="Retrieve proficiency tests with optional filtering by trial, category, and result.",
)
async def list_proficiency_tests(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    test_category: Optional[TestCategory] = Query(None, description="Filter by test category"),
    test_result: Optional[TestResult] = Query(None, description="Filter by test result"),
) -> ProficiencyTestListResponse:
    svc = get_lab_proficiency_service()
    items = svc.list_proficiency_tests(
        trial_id=trial_id, test_category=test_category, test_result=test_result
    )
    return ProficiencyTestListResponse(items=items, total=len(items))


@router.get(
    "/proficiency-tests/{test_id}",
    response_model=ProficiencyTest,
    summary="Get a proficiency test",
)
async def get_proficiency_test(test_id: str) -> ProficiencyTest:
    svc = get_lab_proficiency_service()
    record = svc.get_proficiency_test(test_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Proficiency test '{test_id}' not found")
    return record


@router.post(
    "/proficiency-tests",
    response_model=ProficiencyTest,
    status_code=201,
    summary="Create a proficiency test",
)
async def create_proficiency_test(payload: ProficiencyTestCreate) -> ProficiencyTest:
    svc = get_lab_proficiency_service()
    return svc.create_proficiency_test(payload)


@router.put(
    "/proficiency-tests/{test_id}",
    response_model=ProficiencyTest,
    summary="Update a proficiency test",
)
async def update_proficiency_test(
    test_id: str, payload: ProficiencyTestUpdate
) -> ProficiencyTest:
    svc = get_lab_proficiency_service()
    updated = svc.update_proficiency_test(test_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Proficiency test '{test_id}' not found")
    return updated


@router.delete(
    "/proficiency-tests/{test_id}",
    status_code=204,
    summary="Delete a proficiency test",
)
async def delete_proficiency_test(test_id: str) -> None:
    svc = get_lab_proficiency_service()
    deleted = svc.delete_proficiency_test(test_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Proficiency test '{test_id}' not found")


# ---------------------------------------------------------------------------
# Lab Comparisons
# ---------------------------------------------------------------------------


@router.get(
    "/lab-comparisons",
    response_model=LabComparisonListResponse,
    summary="List lab comparisons",
    description="Retrieve lab comparisons with optional filtering by trial and status.",
)
async def list_lab_comparisons(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    comparison_status: Optional[ComparisonStatus] = Query(
        None, description="Filter by comparison status"
    ),
) -> LabComparisonListResponse:
    svc = get_lab_proficiency_service()
    items = svc.list_lab_comparisons(trial_id=trial_id, comparison_status=comparison_status)
    return LabComparisonListResponse(items=items, total=len(items))


@router.get(
    "/lab-comparisons/{comparison_id}",
    response_model=LabComparison,
    summary="Get a lab comparison",
)
async def get_lab_comparison(comparison_id: str) -> LabComparison:
    svc = get_lab_proficiency_service()
    record = svc.get_lab_comparison(comparison_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Lab comparison '{comparison_id}' not found"
        )
    return record


@router.post(
    "/lab-comparisons",
    response_model=LabComparison,
    status_code=201,
    summary="Create a lab comparison",
)
async def create_lab_comparison(payload: LabComparisonCreate) -> LabComparison:
    svc = get_lab_proficiency_service()
    return svc.create_lab_comparison(payload)


@router.put(
    "/lab-comparisons/{comparison_id}",
    response_model=LabComparison,
    summary="Update a lab comparison",
)
async def update_lab_comparison(
    comparison_id: str, payload: LabComparisonUpdate
) -> LabComparison:
    svc = get_lab_proficiency_service()
    updated = svc.update_lab_comparison(comparison_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Lab comparison '{comparison_id}' not found"
        )
    return updated


@router.delete(
    "/lab-comparisons/{comparison_id}",
    status_code=204,
    summary="Delete a lab comparison",
)
async def delete_lab_comparison(comparison_id: str) -> None:
    svc = get_lab_proficiency_service()
    deleted = svc.delete_lab_comparison(comparison_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Lab comparison '{comparison_id}' not found"
        )


# ---------------------------------------------------------------------------
# Accreditation Records
# ---------------------------------------------------------------------------


@router.get(
    "/accreditation-records",
    response_model=AccreditationRecordListResponse,
    summary="List accreditation records",
    description="Retrieve accreditation records with optional filtering by trial and status.",
)
async def list_accreditation_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    accreditation_status: Optional[AccreditationStatus] = Query(
        None, description="Filter by accreditation status"
    ),
) -> AccreditationRecordListResponse:
    svc = get_lab_proficiency_service()
    items = svc.list_accreditation_records(
        trial_id=trial_id, accreditation_status=accreditation_status
    )
    return AccreditationRecordListResponse(items=items, total=len(items))


@router.get(
    "/accreditation-records/{record_id}",
    response_model=AccreditationRecord,
    summary="Get an accreditation record",
)
async def get_accreditation_record(record_id: str) -> AccreditationRecord:
    svc = get_lab_proficiency_service()
    record = svc.get_accreditation_record(record_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Accreditation record '{record_id}' not found"
        )
    return record


@router.post(
    "/accreditation-records",
    response_model=AccreditationRecord,
    status_code=201,
    summary="Create an accreditation record",
)
async def create_accreditation_record(
    payload: AccreditationRecordCreate,
) -> AccreditationRecord:
    svc = get_lab_proficiency_service()
    return svc.create_accreditation_record(payload)


@router.put(
    "/accreditation-records/{record_id}",
    response_model=AccreditationRecord,
    summary="Update an accreditation record",
)
async def update_accreditation_record(
    record_id: str, payload: AccreditationRecordUpdate
) -> AccreditationRecord:
    svc = get_lab_proficiency_service()
    updated = svc.update_accreditation_record(record_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Accreditation record '{record_id}' not found"
        )
    return updated


@router.delete(
    "/accreditation-records/{record_id}",
    status_code=204,
    summary="Delete an accreditation record",
)
async def delete_accreditation_record(record_id: str) -> None:
    svc = get_lab_proficiency_service()
    deleted = svc.delete_accreditation_record(record_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Accreditation record '{record_id}' not found"
        )


# ---------------------------------------------------------------------------
# Corrective Actions
# ---------------------------------------------------------------------------


@router.get(
    "/corrective-actions",
    response_model=LabCorrectiveActionListResponse,
    summary="List corrective actions",
    description="Retrieve corrective actions with optional filtering by trial, priority, and completion.",
)
async def list_corrective_actions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    priority: Optional[CorrectiveActionPriority] = Query(
        None, description="Filter by priority"
    ),
    is_completed: Optional[bool] = Query(None, description="Filter by completion status"),
) -> LabCorrectiveActionListResponse:
    svc = get_lab_proficiency_service()
    items = svc.list_corrective_actions(
        trial_id=trial_id, priority=priority, is_completed=is_completed
    )
    return LabCorrectiveActionListResponse(items=items, total=len(items))


@router.get(
    "/corrective-actions/{action_id}",
    response_model=LabCorrectiveAction,
    summary="Get a corrective action",
)
async def get_corrective_action(action_id: str) -> LabCorrectiveAction:
    svc = get_lab_proficiency_service()
    record = svc.get_corrective_action(action_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Corrective action '{action_id}' not found"
        )
    return record


@router.post(
    "/corrective-actions",
    response_model=LabCorrectiveAction,
    status_code=201,
    summary="Create a corrective action",
)
async def create_corrective_action(
    payload: LabCorrectiveActionCreate,
) -> LabCorrectiveAction:
    svc = get_lab_proficiency_service()
    return svc.create_corrective_action(payload)


@router.put(
    "/corrective-actions/{action_id}",
    response_model=LabCorrectiveAction,
    summary="Update a corrective action",
)
async def update_corrective_action(
    action_id: str, payload: LabCorrectiveActionUpdate
) -> LabCorrectiveAction:
    svc = get_lab_proficiency_service()
    updated = svc.update_corrective_action(action_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Corrective action '{action_id}' not found"
        )
    return updated


@router.delete(
    "/corrective-actions/{action_id}",
    status_code=204,
    summary="Delete a corrective action",
)
async def delete_corrective_action(action_id: str) -> None:
    svc = get_lab_proficiency_service()
    deleted = svc.delete_corrective_action(action_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Corrective action '{action_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=LabProficiencyMetrics,
    summary="Get lab proficiency metrics",
    description="Aggregated metrics across all lab proficiency operations.",
)
async def get_metrics() -> LabProficiencyMetrics:
    svc = get_lab_proficiency_service()
    return svc.get_metrics()
