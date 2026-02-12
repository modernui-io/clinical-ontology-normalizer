"""Pydantic schemas for Manufacturing Operations & Batch Record (MFG-OPS).

Manages GMP batch records, equipment qualification, environmental monitoring,
process validation, deviation management, and batch release for clinical supply
manufacturing operations.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BatchStatus(str, Enum):
    """Lifecycle status of a GMP manufacturing batch."""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    RELEASED = "released"
    REJECTED = "rejected"
    QUARANTINE = "quarantine"
    UNDER_INVESTIGATION = "under_investigation"


class EquipmentStatus(str, Enum):
    """Qualification status of manufacturing equipment."""

    QUALIFIED = "qualified"
    DUE_FOR_REQUALIFICATION = "due_for_requalification"
    OUT_OF_SERVICE = "out_of_service"
    UNDER_MAINTENANCE = "under_maintenance"
    RETIRED = "retired"


class DeviationType(str, Enum):
    """Severity classification for manufacturing deviations."""

    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class ValidationStatus(str, Enum):
    """Status of a process validation activity."""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    EXPIRED = "expired"


class EnvironmentalZone(str, Enum):
    """EU GMP cleanroom classification zone."""

    GRADE_A = "grade_a"
    GRADE_B = "grade_b"
    GRADE_C = "grade_c"
    GRADE_D = "grade_d"
    UNCLASSIFIED = "unclassified"


class MonitoringResult(str, Enum):
    """Result of an environmental monitoring event."""

    PASS = "pass"
    ALERT = "alert"
    ACTION_REQUIRED = "action_required"
    FAIL = "fail"


class DeviationStatus(str, Enum):
    """Lifecycle status of a manufacturing deviation."""

    OPEN = "open"
    UNDER_INVESTIGATION = "under_investigation"
    CORRECTIVE_ACTION = "corrective_action"
    CLOSED = "closed"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class BatchRecord(BaseModel):
    """GMP batch manufacturing record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique batch record identifier")
    product_name: str = Field(..., description="Name of the product being manufactured")
    batch_number: str = Field(..., description="GMP batch number")
    lot_number: str = Field(..., description="Lot number for traceability")
    manufacturing_site: str = Field(..., description="Manufacturing facility name")
    batch_size: float = Field(..., gt=0, description="Planned batch size")
    unit_of_measure: str = Field(..., description="Unit of measure for batch size (kg, L, units)")
    start_date: datetime | None = Field(None, description="Batch manufacturing start date")
    end_date: datetime | None = Field(None, description="Batch manufacturing end date")
    status: BatchStatus = Field(default=BatchStatus.PLANNED, description="Batch lifecycle status")
    yield_actual: float | None = Field(None, ge=0, description="Actual yield quantity")
    yield_theoretical: float | None = Field(None, ge=0, description="Theoretical yield quantity")
    yield_pct: float | None = Field(None, ge=0, le=200, description="Yield percentage (actual/theoretical)")
    master_batch_record_version: str = Field(..., description="Version of the master batch record used")
    reviewed_by: str | None = Field(None, description="QA reviewer name")
    released_by: str | None = Field(None, description="QP/QA person who authorized release")
    release_date: datetime | None = Field(None, description="Date of batch release")


class Equipment(BaseModel):
    """Manufacturing equipment record with qualification tracking."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique equipment identifier")
    name: str = Field(..., description="Equipment name")
    equipment_type: str = Field(..., description="Type of equipment (reactor, lyophilizer, filler, etc.)")
    serial_number: str = Field(..., description="Equipment serial number")
    location: str = Field(..., description="Physical location in the facility")
    status: EquipmentStatus = Field(default=EquipmentStatus.QUALIFIED, description="Current qualification status")
    last_qualification_date: datetime | None = Field(None, description="Date of last qualification")
    next_qualification_date: datetime | None = Field(None, description="Date next qualification is due")
    calibration_due_date: datetime | None = Field(None, description="Date calibration is next due")
    maintenance_schedule: str | None = Field(None, description="Maintenance schedule description")
    assigned_area: str | None = Field(None, description="Assigned cleanroom or production area")


class EnvironmentalMonitoring(BaseModel):
    """Environmental monitoring record for cleanroom areas."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique monitoring record identifier")
    zone: EnvironmentalZone = Field(..., description="Cleanroom zone classification")
    room_name: str = Field(..., description="Room or area name")
    monitoring_date: datetime = Field(..., description="Date and time of monitoring")
    temperature: float | None = Field(None, description="Temperature reading in Celsius")
    humidity: float | None = Field(None, ge=0, le=100, description="Relative humidity percentage")
    particle_count_05um: int | None = Field(None, ge=0, description="Particle count >= 0.5um per m3")
    particle_count_5um: int | None = Field(None, ge=0, description="Particle count >= 5.0um per m3")
    viable_count: int | None = Field(None, ge=0, description="Viable organism count (CFU)")
    result: MonitoringResult = Field(..., description="Overall monitoring result")
    alert_limit: float | None = Field(None, description="Alert limit value for primary parameter")
    action_limit: float | None = Field(None, description="Action limit value for primary parameter")
    monitored_by: str = Field(..., description="Name of person who performed monitoring")


class ProcessValidation(BaseModel):
    """Process validation record for manufacturing processes."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique validation record identifier")
    product_name: str = Field(..., description="Product name being validated")
    process_step: str = Field(..., description="Manufacturing process step being validated")
    validation_protocol: str = Field(..., description="Validation protocol document reference")
    status: ValidationStatus = Field(default=ValidationStatus.PLANNED, description="Validation lifecycle status")
    start_date: datetime | None = Field(None, description="Validation start date")
    completion_date: datetime | None = Field(None, description="Validation completion date")
    batches_required: int = Field(..., ge=1, description="Number of consecutive batches required")
    batches_completed: int = Field(default=0, ge=0, description="Number of batches completed so far")
    acceptance_criteria: str = Field(..., description="Acceptance criteria for validation")
    results_summary: str | None = Field(None, description="Summary of validation results")
    approved_by: str | None = Field(None, description="Name of person who approved the validation")


class ManufacturingDeviation(BaseModel):
    """Manufacturing deviation record with root cause and CAPA tracking."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique deviation identifier")
    batch_id: str | None = Field(None, description="Associated batch record ID")
    deviation_type: DeviationType = Field(..., description="Severity classification of the deviation")
    description: str = Field(..., description="Detailed description of the deviation")
    root_cause: str | None = Field(None, description="Identified root cause")
    impact_assessment: str | None = Field(None, description="Impact assessment on product quality and patient safety")
    corrective_action: str | None = Field(None, description="Corrective action taken")
    preventive_action: str | None = Field(None, description="Preventive action to avoid recurrence")
    reported_by: str = Field(..., description="Name of person who reported the deviation")
    reported_date: datetime = Field(..., description="Date the deviation was reported")
    resolved_date: datetime | None = Field(None, description="Date the deviation was resolved")
    status: DeviationStatus = Field(default=DeviationStatus.OPEN, description="Deviation lifecycle status")


class BatchReleaseChecklist(BaseModel):
    """Individual checklist item for batch release authorization."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique checklist item identifier")
    batch_id: str = Field(..., description="Associated batch record ID")
    item_description: str = Field(..., description="Description of the release check item")
    required: bool = Field(default=True, description="Whether this item is mandatory for release")
    checked: bool = Field(default=False, description="Whether this item has been verified")
    checked_by: str | None = Field(None, description="Name of person who verified the item")
    checked_date: datetime | None = Field(None, description="Date the item was verified")
    notes: str | None = Field(None, description="Additional notes or comments")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class ManufacturingMetrics(BaseModel):
    """Aggregated manufacturing operations metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_batches: int = Field(ge=0, description="Total number of batch records")
    batches_by_status: dict[str, int] = Field(default_factory=dict, description="Batch counts by status")
    avg_yield_pct: float = Field(ge=0, description="Average yield percentage across completed batches")
    total_equipment: int = Field(ge=0, description="Total equipment items tracked")
    equipment_by_status: dict[str, int] = Field(default_factory=dict, description="Equipment counts by status")
    equipment_due_for_requalification: int = Field(ge=0, description="Equipment items due for requalification")
    total_environmental_records: int = Field(ge=0, description="Total environmental monitoring records")
    environmental_excursions: int = Field(ge=0, description="Environmental records with action_required or fail")
    total_validations: int = Field(ge=0, description="Total process validation records")
    validations_in_progress: int = Field(ge=0, description="Active validation activities")
    total_deviations: int = Field(ge=0, description="Total manufacturing deviations")
    open_deviations: int = Field(ge=0, description="Unresolved deviations")
    deviations_by_type: dict[str, int] = Field(default_factory=dict, description="Deviation counts by severity type")
    total_checklist_items: int = Field(ge=0, description="Total batch release checklist items")
    checklist_completion_pct: float = Field(ge=0, le=100, description="Percentage of checklist items completed")
    batches_released: int = Field(ge=0, description="Number of batches released")
    batches_rejected: int = Field(ge=0, description="Number of batches rejected")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class BatchRecordCreate(BaseModel):
    """Request to create a new batch record."""

    model_config = ConfigDict(from_attributes=True)

    product_name: str = Field(..., description="Product name")
    batch_number: str = Field(..., description="GMP batch number")
    lot_number: str = Field(..., description="Lot number")
    manufacturing_site: str = Field(..., description="Manufacturing site")
    batch_size: float = Field(..., gt=0, description="Batch size")
    unit_of_measure: str = Field(..., description="Unit of measure")
    master_batch_record_version: str = Field(..., description="Master batch record version")
    yield_theoretical: float | None = Field(None, ge=0, description="Theoretical yield")


class BatchRecordUpdate(BaseModel):
    """Request to update a batch record."""

    model_config = ConfigDict(from_attributes=True)

    product_name: str | None = Field(None, description="Product name")
    batch_size: float | None = Field(None, gt=0, description="Batch size")
    unit_of_measure: str | None = Field(None, description="Unit of measure")
    yield_actual: float | None = Field(None, ge=0, description="Actual yield")
    yield_theoretical: float | None = Field(None, ge=0, description="Theoretical yield")
    master_batch_record_version: str | None = Field(None, description="MBR version")
    status: BatchStatus | None = Field(None, description="Batch status")
    reviewed_by: str | None = Field(None, description="QA reviewer")


class EquipmentCreate(BaseModel):
    """Request to create an equipment record."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Equipment name")
    equipment_type: str = Field(..., description="Equipment type")
    serial_number: str = Field(..., description="Serial number")
    location: str = Field(..., description="Physical location")
    maintenance_schedule: str | None = Field(None, description="Maintenance schedule")
    assigned_area: str | None = Field(None, description="Assigned area")


class EquipmentUpdate(BaseModel):
    """Request to update an equipment record."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(None, description="Equipment name")
    location: str | None = Field(None, description="Location")
    status: EquipmentStatus | None = Field(None, description="Qualification status")
    maintenance_schedule: str | None = Field(None, description="Maintenance schedule")
    assigned_area: str | None = Field(None, description="Assigned area")
    calibration_due_date: datetime | None = Field(None, description="Calibration due date")
    next_qualification_date: datetime | None = Field(None, description="Next qualification date")


class EnvironmentalMonitoringCreate(BaseModel):
    """Request to log an environmental monitoring event."""

    model_config = ConfigDict(from_attributes=True)

    zone: EnvironmentalZone = Field(..., description="Cleanroom zone")
    room_name: str = Field(..., description="Room name")
    temperature: float | None = Field(None, description="Temperature (Celsius)")
    humidity: float | None = Field(None, ge=0, le=100, description="Relative humidity %")
    particle_count_05um: int | None = Field(None, ge=0, description="Particle count >= 0.5um per m3")
    particle_count_5um: int | None = Field(None, ge=0, description="Particle count >= 5.0um per m3")
    viable_count: int | None = Field(None, ge=0, description="Viable organism count (CFU)")
    alert_limit: float | None = Field(None, description="Alert limit")
    action_limit: float | None = Field(None, description="Action limit")
    monitored_by: str = Field(..., description="Person who performed monitoring")


class ProcessValidationCreate(BaseModel):
    """Request to create a process validation record."""

    model_config = ConfigDict(from_attributes=True)

    product_name: str = Field(..., description="Product name")
    process_step: str = Field(..., description="Process step")
    validation_protocol: str = Field(..., description="Validation protocol reference")
    batches_required: int = Field(..., ge=1, description="Batches required")
    acceptance_criteria: str = Field(..., description="Acceptance criteria")


class ProcessValidationUpdate(BaseModel):
    """Request to update a process validation record."""

    model_config = ConfigDict(from_attributes=True)

    status: ValidationStatus | None = Field(None, description="Validation status")
    batches_completed: int | None = Field(None, ge=0, description="Batches completed")
    results_summary: str | None = Field(None, description="Results summary")
    approved_by: str | None = Field(None, description="Approved by")


class DeviationCreate(BaseModel):
    """Request to create a manufacturing deviation."""

    model_config = ConfigDict(from_attributes=True)

    batch_id: str | None = Field(None, description="Associated batch ID")
    deviation_type: DeviationType = Field(..., description="Deviation severity")
    description: str = Field(..., description="Deviation description")
    reported_by: str = Field(..., description="Reported by")
    impact_assessment: str | None = Field(None, description="Impact assessment")


class DeviationUpdate(BaseModel):
    """Request to update a manufacturing deviation."""

    model_config = ConfigDict(from_attributes=True)

    deviation_type: DeviationType | None = Field(None, description="Deviation type")
    description: str | None = Field(None, description="Description")
    root_cause: str | None = Field(None, description="Root cause")
    impact_assessment: str | None = Field(None, description="Impact assessment")
    corrective_action: str | None = Field(None, description="Corrective action")
    preventive_action: str | None = Field(None, description="Preventive action")
    status: DeviationStatus | None = Field(None, description="Status")


class ChecklistItemCreate(BaseModel):
    """Request to create a batch release checklist item."""

    model_config = ConfigDict(from_attributes=True)

    batch_id: str = Field(..., description="Batch ID")
    item_description: str = Field(..., description="Check item description")
    required: bool = Field(default=True, description="Whether required for release")


class ChecklistItemUpdate(BaseModel):
    """Request to update a batch release checklist item."""

    model_config = ConfigDict(from_attributes=True)

    checked: bool | None = Field(None, description="Checked status")
    checked_by: str | None = Field(None, description="Checked by")
    notes: str | None = Field(None, description="Notes")


class BatchReleaseRequest(BaseModel):
    """Request to release a batch."""

    model_config = ConfigDict(from_attributes=True)

    released_by: str = Field(..., description="QP/QA person authorizing release")
    reviewed_by: str = Field(..., description="QA reviewer name")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class BatchRecordListResponse(BaseModel):
    """List of batch records."""

    model_config = ConfigDict(from_attributes=True)

    items: list[BatchRecord] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class EquipmentListResponse(BaseModel):
    """List of equipment records."""

    model_config = ConfigDict(from_attributes=True)

    items: list[Equipment] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class EnvironmentalMonitoringListResponse(BaseModel):
    """List of environmental monitoring records."""

    model_config = ConfigDict(from_attributes=True)

    items: list[EnvironmentalMonitoring] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ProcessValidationListResponse(BaseModel):
    """List of process validation records."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ProcessValidation] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class DeviationListResponse(BaseModel):
    """List of manufacturing deviations."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ManufacturingDeviation] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ChecklistListResponse(BaseModel):
    """List of batch release checklist items."""

    model_config = ConfigDict(from_attributes=True)

    items: list[BatchReleaseChecklist] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")
