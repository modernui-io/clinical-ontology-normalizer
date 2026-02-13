"""Pydantic schemas for Site Resource Planning (SRP-PLN).

Manages site resource planning operations: staff allocations, equipment
inventories, capacity assessments, and workload distributions with metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AllocationStatus(str, Enum):
    ALLOCATED = "allocated"
    PENDING = "pending"
    RELEASED = "released"
    ON_HOLD = "on_hold"
    REQUESTED = "requested"
    DENIED = "denied"


class StaffRole(str, Enum):
    PRINCIPAL_INVESTIGATOR = "principal_investigator"
    SUB_INVESTIGATOR = "sub_investigator"
    STUDY_COORDINATOR = "study_coordinator"
    RESEARCH_NURSE = "research_nurse"
    PHARMACIST = "pharmacist"
    DATA_ENTRY = "data_entry"


class EquipmentStatus(str, Enum):
    AVAILABLE = "available"
    IN_USE = "in_use"
    MAINTENANCE = "maintenance"
    CALIBRATION_DUE = "calibration_due"
    DECOMMISSIONED = "decommissioned"
    ON_ORDER = "on_order"


class CapacityLevel(str, Enum):
    UNDER_CAPACITY = "under_capacity"
    OPTIMAL = "optimal"
    NEAR_CAPACITY = "near_capacity"
    AT_CAPACITY = "at_capacity"
    OVER_CAPACITY = "over_capacity"
    UNKNOWN = "unknown"


class WorkloadPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    DEFERRED = "deferred"
    ROUTINE = "routine"


# --- Main entities ---

class StaffAllocation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    allocation_status: AllocationStatus = AllocationStatus.PENDING
    staff_name: str
    staff_role: StaffRole
    fte_percentage: float = Field(ge=0, le=100, default=100.0)
    start_date: datetime
    end_date: datetime | None = None
    supervisor_name: str | None = None
    certification_verified: bool = False
    training_completed: bool = False
    delegation_log_entry: str | None = None
    allocated_by: str
    notes: str | None = None
    created_at: datetime


class EquipmentInventory(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    equipment_status: EquipmentStatus = EquipmentStatus.AVAILABLE
    equipment_name: str
    equipment_type: str
    serial_number: str | None = None
    manufacturer: str | None = None
    calibration_date: datetime | None = None
    next_calibration_date: datetime | None = None
    location: str | None = None
    assigned_to_trial: bool = False
    maintenance_contract: bool = False
    acquisition_date: datetime | None = None
    managed_by: str
    notes: str | None = None
    created_at: datetime


class CapacityAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    capacity_level: CapacityLevel = CapacityLevel.UNKNOWN
    assessment_date: datetime
    max_subjects: int = Field(ge=0, default=0)
    current_subjects: int = Field(ge=0, default=0)
    available_staff_fte: float = Field(ge=0, default=0.0)
    required_staff_fte: float = Field(ge=0, default=0.0)
    available_exam_rooms: int = Field(ge=0, default=0)
    storage_capacity_adequate: bool = True
    pharmacy_capacity_adequate: bool = True
    assessed_by: str
    recommendations: str | None = None
    next_assessment_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


class WorkloadDistribution(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    site_id: str
    workload_priority: WorkloadPriority = WorkloadPriority.MEDIUM
    task_category: str
    assigned_staff: str
    estimated_hours: float = Field(ge=0, default=0.0)
    actual_hours: float = Field(ge=0, default=0.0)
    week_start_date: datetime
    week_end_date: datetime
    tasks_assigned: int = Field(ge=0, default=0)
    tasks_completed: int = Field(ge=0, default=0)
    overdue_tasks: int = Field(ge=0, default=0)
    utilization_pct: float = Field(ge=0, le=100, default=0.0)
    distributed_by: str
    notes: str | None = None
    created_at: datetime


# --- Create / Update schemas ---

class StaffAllocationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    staff_name: str
    staff_role: StaffRole
    start_date: datetime
    allocated_by: str
    allocation_status: AllocationStatus = AllocationStatus.PENDING
    fte_percentage: float = Field(ge=0, le=100, default=100.0)


class StaffAllocationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    allocation_status: AllocationStatus | None = None
    fte_percentage: float | None = None
    end_date: datetime | None = None
    certification_verified: bool | None = None
    training_completed: bool | None = None
    notes: str | None = None


class EquipmentInventoryCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    equipment_name: str
    equipment_type: str
    managed_by: str
    equipment_status: EquipmentStatus = EquipmentStatus.AVAILABLE


class EquipmentInventoryUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    equipment_status: EquipmentStatus | None = None
    calibration_date: datetime | None = None
    next_calibration_date: datetime | None = None
    location: str | None = None
    assigned_to_trial: bool | None = None
    notes: str | None = None


class CapacityAssessmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    assessment_date: datetime
    assessed_by: str
    max_subjects: int = Field(ge=0, default=0)
    capacity_level: CapacityLevel = CapacityLevel.UNKNOWN


class CapacityAssessmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    capacity_level: CapacityLevel | None = None
    current_subjects: int | None = None
    available_staff_fte: float | None = None
    required_staff_fte: float | None = None
    recommendations: str | None = None
    notes: str | None = None


class WorkloadDistributionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    site_id: str
    task_category: str
    assigned_staff: str
    week_start_date: datetime
    week_end_date: datetime
    distributed_by: str
    workload_priority: WorkloadPriority = WorkloadPriority.MEDIUM


class WorkloadDistributionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    workload_priority: WorkloadPriority | None = None
    estimated_hours: float | None = None
    actual_hours: float | None = None
    tasks_completed: int | None = None
    overdue_tasks: int | None = None
    notes: str | None = None


# --- List responses ---

class StaffAllocationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[StaffAllocation] = Field(default_factory=list)
    total: int = Field(ge=0)


class EquipmentInventoryListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[EquipmentInventory] = Field(default_factory=list)
    total: int = Field(ge=0)


class CapacityAssessmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CapacityAssessment] = Field(default_factory=list)
    total: int = Field(ge=0)


class WorkloadDistributionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[WorkloadDistribution] = Field(default_factory=list)
    total: int = Field(ge=0)


# --- Metrics ---

class SiteResourcePlanningMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_staff_allocations: int = Field(ge=0)
    allocations_by_status: dict[str, int] = Field(default_factory=dict)
    allocations_by_role: dict[str, int] = Field(default_factory=dict)
    avg_fte_utilization: float = Field(ge=0)
    total_equipment: int = Field(ge=0)
    equipment_by_status: dict[str, int] = Field(default_factory=dict)
    total_capacity_assessments: int = Field(ge=0)
    assessments_by_level: dict[str, int] = Field(default_factory=dict)
    total_workload_entries: int = Field(ge=0)
    workloads_by_priority: dict[str, int] = Field(default_factory=dict)
    avg_utilization_pct: float = Field(ge=0)
