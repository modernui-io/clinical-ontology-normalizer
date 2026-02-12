"""Pydantic schemas for Environmental Monitoring (ENV-MON).

Manages environmental conditions for investigational products: temperature
monitoring, storage facility management, excursion tracking, calibration
records, cold chain compliance, and environmental monitoring metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class StorageCondition(str, Enum):
    FROZEN = "frozen_minus_20"
    ULTRA_FROZEN = "ultra_frozen_minus_80"
    REFRIGERATED = "refrigerated_2_8"
    CONTROLLED_ROOM = "controlled_room_15_25"
    AMBIENT = "ambient"
    CRYOGENIC = "cryogenic_minus_196"


class SensorType(str, Enum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    LIGHT = "light"
    VIBRATION = "vibration"
    PRESSURE = "pressure"


class ExcursionSeverity(str, Enum):
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"


class ExcursionStatus(str, Enum):
    DETECTED = "detected"
    UNDER_INVESTIGATION = "under_investigation"
    ASSESSED = "assessed"
    RESOLVED = "resolved"
    PRODUCT_IMPACTED = "product_impacted"


class CalibrationStatus(str, Enum):
    CURRENT = "current"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"
    OUT_OF_SERVICE = "out_of_service"


class StorageFacility(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    facility_name: str
    facility_type: str
    location: str
    storage_condition: StorageCondition
    temperature_min: float
    temperature_max: float
    humidity_min_pct: float | None = None
    humidity_max_pct: float | None = None
    capacity_units: int = Field(ge=0, default=0)
    current_occupancy: int = Field(ge=0, default=0)
    qualified: bool = True
    qualification_date: datetime | None = None
    next_qualification_date: datetime | None = None
    responsible_person: str
    site_id: str | None = None
    created_at: datetime


class MonitoringSensor(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    facility_id: str
    sensor_type: SensorType
    sensor_serial: str
    location_in_facility: str
    active: bool = True
    reading_interval_minutes: int = Field(ge=1, default=15)
    alert_threshold_low: float | None = None
    alert_threshold_high: float | None = None
    last_reading_value: float | None = None
    last_reading_time: datetime | None = None
    calibration_status: CalibrationStatus = CalibrationStatus.CURRENT
    calibration_due_date: datetime | None = None
    installed_date: datetime
    installed_by: str


class TemperatureExcursion(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    facility_id: str
    sensor_id: str
    trial_id: str
    severity: ExcursionSeverity
    status: ExcursionStatus = ExcursionStatus.DETECTED
    excursion_start: datetime
    excursion_end: datetime | None = None
    duration_minutes: int = Field(ge=0, default=0)
    min_temperature: float | None = None
    max_temperature: float | None = None
    allowed_min: float
    allowed_max: float
    products_affected: int = Field(ge=0, default=0)
    root_cause: str | None = None
    corrective_action: str | None = None
    product_disposition: str | None = None
    reported_by: str
    investigated_by: str | None = None
    created_at: datetime


class CalibrationRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sensor_id: str
    calibration_date: datetime
    next_due_date: datetime
    performed_by: str
    reference_standard: str
    pre_calibration_offset: float | None = None
    post_calibration_offset: float | None = None
    passed: bool = True
    certificate_number: str | None = None
    notes: str | None = None


class ColdChainShipment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    shipment_id: str
    origin_facility_id: str
    destination_facility_id: str | None = None
    storage_condition: StorageCondition
    shipper_type: str
    monitoring_device: str | None = None
    departure_date: datetime
    arrival_date: datetime | None = None
    transit_duration_hours: float | None = None
    min_temp_recorded: float | None = None
    max_temp_recorded: float | None = None
    excursion_detected: bool = False
    units_shipped: int = Field(ge=0, default=0)
    status: str = "in_transit"
    carrier: str
    created_at: datetime


class StorageFacilityCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    facility_name: str
    facility_type: str
    location: str
    storage_condition: StorageCondition
    temperature_min: float
    temperature_max: float
    responsible_person: str
    site_id: str | None = None


class StorageFacilityUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    current_occupancy: int | None = None
    qualified: bool | None = None
    capacity_units: int | None = None
    humidity_min_pct: float | None = None
    humidity_max_pct: float | None = None


class MonitoringSensorCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    facility_id: str
    sensor_type: SensorType
    sensor_serial: str
    location_in_facility: str
    reading_interval_minutes: int = Field(ge=1, default=15)
    installed_by: str
    alert_threshold_low: float | None = None
    alert_threshold_high: float | None = None


class MonitoringSensorUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    active: bool | None = None
    last_reading_value: float | None = None
    calibration_status: CalibrationStatus | None = None
    alert_threshold_low: float | None = None
    alert_threshold_high: float | None = None


class TemperatureExcursionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    facility_id: str
    sensor_id: str
    trial_id: str
    severity: ExcursionSeverity
    excursion_start: datetime
    allowed_min: float
    allowed_max: float
    reported_by: str


class TemperatureExcursionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: ExcursionStatus | None = None
    root_cause: str | None = None
    corrective_action: str | None = None
    product_disposition: str | None = None
    investigated_by: str | None = None
    products_affected: int | None = None


class CalibrationRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sensor_id: str
    next_due_date: datetime
    performed_by: str
    reference_standard: str
    passed: bool = True
    certificate_number: str | None = None


class ColdChainShipmentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    shipment_id: str
    origin_facility_id: str
    storage_condition: StorageCondition
    shipper_type: str
    units_shipped: int = Field(ge=0, default=0)
    carrier: str
    destination_facility_id: str | None = None


class ColdChainShipmentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    min_temp_recorded: float | None = None
    max_temp_recorded: float | None = None
    excursion_detected: bool | None = None
    transit_duration_hours: float | None = None


class StorageFacilityListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[StorageFacility] = Field(default_factory=list)
    total: int = Field(ge=0)


class MonitoringSensorListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[MonitoringSensor] = Field(default_factory=list)
    total: int = Field(ge=0)


class TemperatureExcursionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[TemperatureExcursion] = Field(default_factory=list)
    total: int = Field(ge=0)


class CalibrationRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CalibrationRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class ColdChainShipmentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ColdChainShipment] = Field(default_factory=list)
    total: int = Field(ge=0)


class EnvironmentalMonitoringMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_facilities: int = Field(ge=0)
    qualified_facilities: int = Field(ge=0)
    facilities_by_condition: dict[str, int] = Field(default_factory=dict)
    total_sensors: int = Field(ge=0)
    active_sensors: int = Field(ge=0)
    sensors_by_calibration: dict[str, int] = Field(default_factory=dict)
    total_excursions: int = Field(ge=0)
    excursions_by_severity: dict[str, int] = Field(default_factory=dict)
    excursions_by_status: dict[str, int] = Field(default_factory=dict)
    open_excursions: int = Field(ge=0)
    total_calibrations: int = Field(ge=0)
    calibrations_passed_pct: float = Field(ge=0, le=100)
    total_shipments: int = Field(ge=0)
    shipments_with_excursions: int = Field(ge=0)
