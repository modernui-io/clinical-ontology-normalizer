"""Site Resource Planning (SRP-PLN) API endpoints.

Manages site resource planning operations: staff allocations, equipment
inventories, capacity assessments, workload distributions, and metrics.

Endpoints:
    GET    /site-resource-planning/staff-allocations                       - List staff allocations
    GET    /site-resource-planning/staff-allocations/{allocation_id}       - Get single allocation
    POST   /site-resource-planning/staff-allocations                       - Create allocation
    PUT    /site-resource-planning/staff-allocations/{allocation_id}       - Update allocation
    DELETE /site-resource-planning/staff-allocations/{allocation_id}       - Delete allocation
    GET    /site-resource-planning/equipment-inventories                   - List equipment
    GET    /site-resource-planning/equipment-inventories/{equipment_id}    - Get single equipment
    POST   /site-resource-planning/equipment-inventories                   - Create equipment
    PUT    /site-resource-planning/equipment-inventories/{equipment_id}    - Update equipment
    DELETE /site-resource-planning/equipment-inventories/{equipment_id}    - Delete equipment
    GET    /site-resource-planning/capacity-assessments                    - List assessments
    GET    /site-resource-planning/capacity-assessments/{assessment_id}    - Get single assessment
    POST   /site-resource-planning/capacity-assessments                    - Create assessment
    PUT    /site-resource-planning/capacity-assessments/{assessment_id}    - Update assessment
    DELETE /site-resource-planning/capacity-assessments/{assessment_id}    - Delete assessment
    GET    /site-resource-planning/workload-distributions                  - List workloads
    GET    /site-resource-planning/workload-distributions/{workload_id}    - Get single workload
    POST   /site-resource-planning/workload-distributions                  - Create workload
    PUT    /site-resource-planning/workload-distributions/{workload_id}    - Update workload
    DELETE /site-resource-planning/workload-distributions/{workload_id}    - Delete workload
    GET    /site-resource-planning/metrics                                 - Metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.site_resource_planning import (
    CapacityAssessment,
    CapacityAssessmentCreate,
    CapacityAssessmentListResponse,
    CapacityAssessmentUpdate,
    EquipmentInventory,
    EquipmentInventoryCreate,
    EquipmentInventoryListResponse,
    EquipmentInventoryUpdate,
    SiteResourcePlanningMetrics,
    StaffAllocation,
    StaffAllocationCreate,
    StaffAllocationListResponse,
    StaffAllocationUpdate,
    WorkloadDistribution,
    WorkloadDistributionCreate,
    WorkloadDistributionListResponse,
    WorkloadDistributionUpdate,
)
from app.services.site_resource_planning_service import get_site_resource_planning_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/site-resource-planning",
    tags=["Site Resource Planning"],
)


# ---------------------------------------------------------------------------
# Staff Allocations
# ---------------------------------------------------------------------------


@router.get(
    "/staff-allocations",
    response_model=StaffAllocationListResponse,
    summary="List staff allocations",
    description="Retrieve staff allocations with optional filtering by trial.",
)
async def list_staff_allocations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> StaffAllocationListResponse:
    svc = get_site_resource_planning_service()
    items = svc.list_staff_allocations(trial_id=trial_id)
    return StaffAllocationListResponse(items=items, total=len(items))


@router.get(
    "/staff-allocations/{allocation_id}",
    response_model=StaffAllocation,
    summary="Get a staff allocation",
)
async def get_staff_allocation(allocation_id: str) -> StaffAllocation:
    svc = get_site_resource_planning_service()
    allocation = svc.get_staff_allocation(allocation_id)
    if allocation is None:
        raise HTTPException(status_code=404, detail=f"Staff allocation '{allocation_id}' not found")
    return allocation


@router.post(
    "/staff-allocations",
    response_model=StaffAllocation,
    status_code=201,
    summary="Create a staff allocation",
)
async def create_staff_allocation(payload: StaffAllocationCreate) -> StaffAllocation:
    svc = get_site_resource_planning_service()
    return svc.create_staff_allocation(payload)


@router.put(
    "/staff-allocations/{allocation_id}",
    response_model=StaffAllocation,
    summary="Update a staff allocation",
)
async def update_staff_allocation(
    allocation_id: str, payload: StaffAllocationUpdate
) -> StaffAllocation:
    svc = get_site_resource_planning_service()
    updated = svc.update_staff_allocation(allocation_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Staff allocation '{allocation_id}' not found")
    return updated


@router.delete(
    "/staff-allocations/{allocation_id}",
    status_code=204,
    summary="Delete a staff allocation",
)
async def delete_staff_allocation(allocation_id: str) -> None:
    svc = get_site_resource_planning_service()
    deleted = svc.delete_staff_allocation(allocation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Staff allocation '{allocation_id}' not found")


# ---------------------------------------------------------------------------
# Equipment Inventories
# ---------------------------------------------------------------------------


@router.get(
    "/equipment-inventories",
    response_model=EquipmentInventoryListResponse,
    summary="List equipment inventories",
    description="Retrieve equipment inventories with optional filtering by trial.",
)
async def list_equipment_inventories(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> EquipmentInventoryListResponse:
    svc = get_site_resource_planning_service()
    items = svc.list_equipment_inventories(trial_id=trial_id)
    return EquipmentInventoryListResponse(items=items, total=len(items))


@router.get(
    "/equipment-inventories/{equipment_id}",
    response_model=EquipmentInventory,
    summary="Get an equipment inventory entry",
)
async def get_equipment_inventory(equipment_id: str) -> EquipmentInventory:
    svc = get_site_resource_planning_service()
    equipment = svc.get_equipment_inventory(equipment_id)
    if equipment is None:
        raise HTTPException(
            status_code=404, detail=f"Equipment inventory '{equipment_id}' not found"
        )
    return equipment


@router.post(
    "/equipment-inventories",
    response_model=EquipmentInventory,
    status_code=201,
    summary="Create an equipment inventory entry",
)
async def create_equipment_inventory(payload: EquipmentInventoryCreate) -> EquipmentInventory:
    svc = get_site_resource_planning_service()
    return svc.create_equipment_inventory(payload)


@router.put(
    "/equipment-inventories/{equipment_id}",
    response_model=EquipmentInventory,
    summary="Update an equipment inventory entry",
)
async def update_equipment_inventory(
    equipment_id: str, payload: EquipmentInventoryUpdate
) -> EquipmentInventory:
    svc = get_site_resource_planning_service()
    updated = svc.update_equipment_inventory(equipment_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Equipment inventory '{equipment_id}' not found"
        )
    return updated


@router.delete(
    "/equipment-inventories/{equipment_id}",
    status_code=204,
    summary="Delete an equipment inventory entry",
)
async def delete_equipment_inventory(equipment_id: str) -> None:
    svc = get_site_resource_planning_service()
    deleted = svc.delete_equipment_inventory(equipment_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Equipment inventory '{equipment_id}' not found"
        )


# ---------------------------------------------------------------------------
# Capacity Assessments
# ---------------------------------------------------------------------------


@router.get(
    "/capacity-assessments",
    response_model=CapacityAssessmentListResponse,
    summary="List capacity assessments",
    description="Retrieve capacity assessments with optional filtering by trial.",
)
async def list_capacity_assessments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> CapacityAssessmentListResponse:
    svc = get_site_resource_planning_service()
    items = svc.list_capacity_assessments(trial_id=trial_id)
    return CapacityAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/capacity-assessments/{assessment_id}",
    response_model=CapacityAssessment,
    summary="Get a capacity assessment",
)
async def get_capacity_assessment(assessment_id: str) -> CapacityAssessment:
    svc = get_site_resource_planning_service()
    assessment = svc.get_capacity_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(
            status_code=404, detail=f"Capacity assessment '{assessment_id}' not found"
        )
    return assessment


@router.post(
    "/capacity-assessments",
    response_model=CapacityAssessment,
    status_code=201,
    summary="Create a capacity assessment",
)
async def create_capacity_assessment(payload: CapacityAssessmentCreate) -> CapacityAssessment:
    svc = get_site_resource_planning_service()
    return svc.create_capacity_assessment(payload)


@router.put(
    "/capacity-assessments/{assessment_id}",
    response_model=CapacityAssessment,
    summary="Update a capacity assessment",
)
async def update_capacity_assessment(
    assessment_id: str, payload: CapacityAssessmentUpdate
) -> CapacityAssessment:
    svc = get_site_resource_planning_service()
    updated = svc.update_capacity_assessment(assessment_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Capacity assessment '{assessment_id}' not found"
        )
    return updated


@router.delete(
    "/capacity-assessments/{assessment_id}",
    status_code=204,
    summary="Delete a capacity assessment",
)
async def delete_capacity_assessment(assessment_id: str) -> None:
    svc = get_site_resource_planning_service()
    deleted = svc.delete_capacity_assessment(assessment_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Capacity assessment '{assessment_id}' not found"
        )


# ---------------------------------------------------------------------------
# Workload Distributions
# ---------------------------------------------------------------------------


@router.get(
    "/workload-distributions",
    response_model=WorkloadDistributionListResponse,
    summary="List workload distributions",
    description="Retrieve workload distributions with optional filtering by trial.",
)
async def list_workload_distributions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> WorkloadDistributionListResponse:
    svc = get_site_resource_planning_service()
    items = svc.list_workload_distributions(trial_id=trial_id)
    return WorkloadDistributionListResponse(items=items, total=len(items))


@router.get(
    "/workload-distributions/{workload_id}",
    response_model=WorkloadDistribution,
    summary="Get a workload distribution",
)
async def get_workload_distribution(workload_id: str) -> WorkloadDistribution:
    svc = get_site_resource_planning_service()
    workload = svc.get_workload_distribution(workload_id)
    if workload is None:
        raise HTTPException(
            status_code=404, detail=f"Workload distribution '{workload_id}' not found"
        )
    return workload


@router.post(
    "/workload-distributions",
    response_model=WorkloadDistribution,
    status_code=201,
    summary="Create a workload distribution",
)
async def create_workload_distribution(
    payload: WorkloadDistributionCreate,
) -> WorkloadDistribution:
    svc = get_site_resource_planning_service()
    return svc.create_workload_distribution(payload)


@router.put(
    "/workload-distributions/{workload_id}",
    response_model=WorkloadDistribution,
    summary="Update a workload distribution",
)
async def update_workload_distribution(
    workload_id: str, payload: WorkloadDistributionUpdate
) -> WorkloadDistribution:
    svc = get_site_resource_planning_service()
    updated = svc.update_workload_distribution(workload_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Workload distribution '{workload_id}' not found"
        )
    return updated


@router.delete(
    "/workload-distributions/{workload_id}",
    status_code=204,
    summary="Delete a workload distribution",
)
async def delete_workload_distribution(workload_id: str) -> None:
    svc = get_site_resource_planning_service()
    deleted = svc.delete_workload_distribution(workload_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Workload distribution '{workload_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=SiteResourcePlanningMetrics,
    summary="Get site resource planning metrics",
    description="Aggregated site resource planning metrics across all entities.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> SiteResourcePlanningMetrics:
    svc = get_site_resource_planning_service()
    return svc.get_metrics(trial_id=trial_id)
