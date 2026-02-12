"""Pydantic schemas for Decentralized Trial Operations (DCT-OPS).

Manages decentralized/hybrid trial components: remote visit scheduling,
home nursing visit coordination, wearable device management, telemedicine
sessions, eSource data capture, and DCT operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class VisitType(str, Enum):
    HOME_NURSING = "home_nursing"
    TELEMEDICINE = "telemedicine"
    LOCAL_LAB = "local_lab"
    LOCAL_IMAGING = "local_imaging"
    MOBILE_UNIT = "mobile_unit"
    SELF_ADMINISTERED = "self_administered"


class VisitStatus(str, Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"
    NO_SHOW = "no_show"


class DeviceType(str, Enum):
    SMARTWATCH = "smartwatch"
    CONTINUOUS_GLUCOSE = "continuous_glucose_monitor"
    BLOOD_PRESSURE = "blood_pressure_monitor"
    PULSE_OXIMETER = "pulse_oximeter"
    ECG_PATCH = "ecg_patch"
    ACTIVITY_TRACKER = "activity_tracker"
    SPIROMETER = "spirometer"
    SCALE = "digital_scale"
    THERMOMETER = "smart_thermometer"


class DeviceStatus(str, Enum):
    PROVISIONED = "provisioned"
    SHIPPED = "shipped"
    ACTIVATED = "activated"
    COLLECTING_DATA = "collecting_data"
    DEACTIVATED = "deactivated"
    RETURNED = "returned"
    LOST = "lost"
    MALFUNCTIONING = "malfunctioning"


class SessionPlatform(str, Enum):
    ZOOM_HEALTHCARE = "zoom_healthcare"
    TEAMS = "microsoft_teams"
    DOXY_ME = "doxy_me"
    CUSTOM_PLATFORM = "custom_platform"
    PHONE_CALL = "phone_call"


class DataQuality(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    UNUSABLE = "unusable"


class RemoteVisit(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    visit_type: VisitType
    scheduled_date: datetime
    actual_date: datetime | None = None
    status: VisitStatus = VisitStatus.SCHEDULED
    provider_name: str | None = None
    provider_organization: str | None = None
    procedures: list[str] = Field(default_factory=list)
    location_address: str | None = None
    duration_minutes: int | None = None
    notes: str | None = None
    created_at: datetime


class WearableDevice(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    device_type: DeviceType
    manufacturer: str
    model: str
    serial_number: str
    firmware_version: str | None = None
    status: DeviceStatus = DeviceStatus.PROVISIONED
    activation_date: datetime | None = None
    last_sync_date: datetime | None = None
    data_points_collected: int = Field(ge=0, default=0)
    battery_level_pct: float | None = None
    data_quality: DataQuality | None = None
    compliance_rate_pct: float | None = None
    assigned_date: datetime


class TelemedicineSession(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    visit_id: str | None = None
    platform: SessionPlatform
    scheduled_date: datetime
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    duration_minutes: int | None = None
    provider_name: str
    provider_role: str
    status: VisitStatus = VisitStatus.SCHEDULED
    recording_available: bool = False
    consent_documented: bool = False
    connection_quality: DataQuality | None = None
    clinical_notes: str | None = None


class ESourceCapture(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    visit_id: str | None = None
    device_id: str | None = None
    data_type: str
    capture_date: datetime
    value: str
    unit: str | None = None
    data_quality: DataQuality = DataQuality.GOOD
    source_system: str
    verified: bool = False
    verified_by: str | None = None
    verified_date: datetime | None = None


class RemoteVisitCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    visit_type: VisitType
    scheduled_date: datetime
    provider_name: str | None = None
    provider_organization: str | None = None
    procedures: list[str] = Field(default_factory=list)
    location_address: str | None = None


class RemoteVisitUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: VisitStatus | None = None
    actual_date: datetime | None = None
    duration_minutes: int | None = None
    notes: str | None = None
    provider_name: str | None = None


class WearableDeviceCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    device_type: DeviceType
    manufacturer: str
    model: str
    serial_number: str
    firmware_version: str | None = None


class WearableDeviceUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: DeviceStatus | None = None
    firmware_version: str | None = None
    data_points_collected: int | None = None
    battery_level_pct: float | None = None
    data_quality: DataQuality | None = None
    compliance_rate_pct: float | None = None


class TelemedicineSessionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    visit_id: str | None = None
    platform: SessionPlatform
    scheduled_date: datetime
    provider_name: str
    provider_role: str


class TelemedicineSessionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: VisitStatus | None = None
    actual_start: datetime | None = None
    actual_end: datetime | None = None
    duration_minutes: int | None = None
    recording_available: bool | None = None
    consent_documented: bool | None = None
    connection_quality: DataQuality | None = None
    clinical_notes: str | None = None


class ESourceCaptureCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    visit_id: str | None = None
    device_id: str | None = None
    data_type: str
    value: str
    unit: str | None = None
    source_system: str


class ESourceCaptureUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    data_quality: DataQuality | None = None
    verified: bool | None = None
    verified_by: str | None = None


class RemoteVisitListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[RemoteVisit] = Field(default_factory=list)
    total: int = Field(ge=0)


class WearableDeviceListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[WearableDevice] = Field(default_factory=list)
    total: int = Field(ge=0)


class TelemedicineSessionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TelemedicineSession] = Field(default_factory=list)
    total: int = Field(ge=0)


class ESourceCaptureListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ESourceCapture] = Field(default_factory=list)
    total: int = Field(ge=0)


class DecentralizedTrialMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_remote_visits: int = Field(ge=0)
    visits_by_type: dict[str, int] = Field(default_factory=dict)
    visits_by_status: dict[str, int] = Field(default_factory=dict)
    visit_completion_rate: float = Field(ge=0, le=100)
    total_devices: int = Field(ge=0)
    devices_by_type: dict[str, int] = Field(default_factory=dict)
    devices_by_status: dict[str, int] = Field(default_factory=dict)
    avg_device_compliance_pct: float = Field(ge=0, le=100)
    total_telemedicine_sessions: int = Field(ge=0)
    sessions_by_status: dict[str, int] = Field(default_factory=dict)
    avg_session_duration_minutes: float = Field(ge=0)
    total_esource_captures: int = Field(ge=0)
    verified_captures: int = Field(ge=0)
    data_quality_distribution: dict[str, int] = Field(default_factory=dict)
