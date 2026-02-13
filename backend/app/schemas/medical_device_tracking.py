"""Pydantic schemas for Medical Device Tracking (MDT-TRK).

Manages medical device tracking operations: device registrations, device
deployment records, maintenance logs, device incident reports, and device
tracking metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DeviceClassification(str, Enum):
    CLASS_I = "class_i"
    CLASS_II = "class_ii"
    CLASS_III = "class_iii"
    COMBINATION = "combination"
    INVESTIGATIONAL = "investigational"
    EXEMPT = "exempt"


class DeploymentStatus(str, Enum):
    DEPLOYED = "deployed"
    IN_TRANSIT = "in_transit"
    IN_STORAGE = "in_storage"
    RETURNED = "returned"
    DECOMMISSIONED = "decommissioned"
    QUARANTINED = "quarantined"


class MaintenanceType(str, Enum):
    PREVENTIVE = "preventive"
    CORRECTIVE = "corrective"
    CALIBRATION = "calibration"
    SOFTWARE_UPDATE = "software_update"
    INSPECTION = "inspection"
    EMERGENCY = "emergency"


class MaintenanceResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    CONDITIONAL = "conditional"
    DEFERRED = "deferred"
    NOT_APPLICABLE = "not_applicable"
    PENDING = "pending"


class IncidentSeverity(str, Enum):
    CRITICAL = "critical"
    SERIOUS = "serious"
    MODERATE = "moderate"
    MINOR = "minor"
    NEAR_MISS = "near_miss"
    INFORMATIONAL = "informational"


# --- Main entities ---

class DeviceRegistration(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    device_name: str
    manufacturer: str
    model_number: str
    serial_number: str
    device_classification: DeviceClassification = DeviceClassification.INVESTIGATIONAL
    udi_number: str | None = None
    firmware_version: str | None = None
    calibration_due_date: datetime | None = None
    regulatory_approval_id: str | None = None
    purchase_date: datetime | None = None
    warranty_expiry: datetime | None = None
    registered_by: str
    notes: str | None = None
    created_at: datetime


class DeviceDeployment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    device_id: str
    site_id: str
    deployment_status: DeploymentStatus = DeploymentStatus.IN_STORAGE
    deployed_date: datetime | None = None
    returned_date: datetime | None = None
    assigned_to: str | None = None
    location_description: str | None = None
    subjects_using: int = Field(ge=0, default=0)
    condition_on_deploy: str | None = None
    condition_on_return: str | None = None
    shipped_by: str | None = None
    tracking_number: str | None = None
    notes: str | None = None
    created_at: datetime


class MaintenanceLog(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    device_id: str
    maintenance_type: MaintenanceType
    maintenance_result: MaintenanceResult = MaintenanceResult.PENDING
    scheduled_date: datetime
    completed_date: datetime | None = None
    performed_by: str
    service_provider: str | None = None
    parts_replaced: str | None = None
    downtime_hours: float = Field(ge=0, default=0.0)
    next_maintenance_date: datetime | None = None
    cost_usd: float = Field(ge=0, default=0.0)
    certificate_id: str | None = None
    notes: str | None = None
    created_at: datetime


class DeviceIncidentReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    device_id: str
    site_id: str
    incident_severity: IncidentSeverity = IncidentSeverity.INFORMATIONAL
    incident_date: datetime
    description: str
    subject_affected: str | None = None
    patient_harm: bool = False
    root_cause: str | None = None
    corrective_action: str | None = None
    regulatory_reported: bool = False
    regulatory_report_date: datetime | None = None
    mdr_report_number: str | None = None
    reported_by: str
    investigated_by: str | None = None
    resolution_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


# --- Create / Update schemas ---

class DeviceRegistrationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    device_name: str
    manufacturer: str
    model_number: str
    serial_number: str
    registered_by: str
    device_classification: DeviceClassification = DeviceClassification.INVESTIGATIONAL


class DeviceRegistrationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    firmware_version: str | None = None
    calibration_due_date: datetime | None = None
    udi_number: str | None = None
    warranty_expiry: datetime | None = None
    notes: str | None = None


class DeviceDeploymentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    device_id: str
    site_id: str
    deployment_status: DeploymentStatus = DeploymentStatus.IN_STORAGE


class DeviceDeploymentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    deployment_status: DeploymentStatus | None = None
    deployed_date: datetime | None = None
    returned_date: datetime | None = None
    assigned_to: str | None = None
    subjects_using: int | None = None
    tracking_number: str | None = None
    notes: str | None = None


class MaintenanceLogCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    device_id: str
    maintenance_type: MaintenanceType
    scheduled_date: datetime
    performed_by: str


class MaintenanceLogUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    maintenance_result: MaintenanceResult | None = None
    completed_date: datetime | None = None
    parts_replaced: str | None = None
    downtime_hours: float | None = None
    next_maintenance_date: datetime | None = None
    cost_usd: float | None = None
    notes: str | None = None


class DeviceIncidentReportCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    device_id: str
    site_id: str
    incident_date: datetime
    description: str
    reported_by: str
    incident_severity: IncidentSeverity = IncidentSeverity.INFORMATIONAL


class DeviceIncidentReportUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    root_cause: str | None = None
    corrective_action: str | None = None
    patient_harm: bool | None = None
    regulatory_reported: bool | None = None
    regulatory_report_date: datetime | None = None
    investigated_by: str | None = None
    resolution_date: datetime | None = None
    notes: str | None = None


# --- List responses ---

class DeviceRegistrationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DeviceRegistration] = Field(default_factory=list)
    total: int = Field(ge=0)


class DeviceDeploymentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DeviceDeployment] = Field(default_factory=list)
    total: int = Field(ge=0)


class MaintenanceLogListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[MaintenanceLog] = Field(default_factory=list)
    total: int = Field(ge=0)


class DeviceIncidentReportListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DeviceIncidentReport] = Field(default_factory=list)
    total: int = Field(ge=0)


# --- Metrics ---

class MedicalDeviceTrackingMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_devices: int = Field(ge=0)
    devices_by_classification: dict[str, int] = Field(default_factory=dict)
    total_deployments: int = Field(ge=0)
    deployments_by_status: dict[str, int] = Field(default_factory=dict)
    total_maintenance_logs: int = Field(ge=0)
    maintenance_by_type: dict[str, int] = Field(default_factory=dict)
    maintenance_pass_rate: float = Field(ge=0)
    total_incidents: int = Field(ge=0)
    incidents_by_severity: dict[str, int] = Field(default_factory=dict)
    patient_harm_rate: float = Field(ge=0)
