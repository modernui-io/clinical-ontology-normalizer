"""Pydantic schemas for Digital Biomarkers Management (DIGI-BIO).

Manages digital biomarker operations: digital endpoint definitions, wearable
data collection streams, algorithm validation, digital measure scoring,
regulatory qualification, and digital biomarker operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DeviceType(str, Enum):
    ACCELEROMETER = "accelerometer"
    GYROSCOPE = "gyroscope"
    PPG_SENSOR = "ppg_sensor"
    ECG_PATCH = "ecg_patch"
    CGM = "continuous_glucose_monitor"
    SPIROMETER = "spirometer"
    ACTIGRAPHY = "actigraphy"
    SMARTPHONE_SENSOR = "smartphone_sensor"
    SMARTWATCH = "smartwatch"
    BIOSENSOR_PATCH = "biosensor_patch"


class EndpointQualification(str, Enum):
    EXPLORATORY = "exploratory"
    FIT_FOR_PURPOSE = "fit_for_purpose"
    QUALIFIED = "qualified"
    REGULATORY_ACCEPTED = "regulatory_accepted"


class StreamStatus(str, Enum):
    CONFIGURED = "configured"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class AlgorithmStatus(str, Enum):
    DEVELOPMENT = "development"
    ANALYTICAL_VALIDATION = "analytical_validation"
    CLINICAL_VALIDATION = "clinical_validation"
    LOCKED = "locked"
    DEPRECATED = "deprecated"


class ScoringStatus(str, Enum):
    RAW = "raw"
    PREPROCESSED = "preprocessed"
    SCORED = "scored"
    QC_PASSED = "qc_passed"
    QC_FAILED = "qc_failed"
    ADJUDICATED = "adjudicated"


class DigitalEndpoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    endpoint_name: str
    description: str
    device_type: DeviceType
    measure_type: str
    unit: str
    collection_frequency: str
    qualification_level: EndpointQualification = EndpointQualification.EXPLORATORY
    clinically_meaningful_change: float | None = None
    test_retest_icc: float | None = None
    sensitivity_to_change: float | None = None
    regulatory_reference: str | None = None
    concept_of_interest: str
    context_of_use: str
    created_by: str
    created_at: datetime


class DataStream(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    endpoint_id: str
    trial_id: str
    subject_id: str
    device_type: DeviceType
    device_serial: str | None = None
    status: StreamStatus = StreamStatus.CONFIGURED
    start_date: datetime | None = None
    end_date: datetime | None = None
    sampling_rate_hz: float | None = None
    total_data_points: int = Field(ge=0, default=0)
    wear_time_hours: float = Field(ge=0, default=0)
    compliance_pct: float = Field(ge=0, le=100, default=0)
    data_quality_score: float | None = None
    site_id: str


class AlgorithmValidation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    endpoint_id: str
    algorithm_name: str
    version: str
    status: AlgorithmStatus = AlgorithmStatus.DEVELOPMENT
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1_score: float | None = None
    auc_roc: float | None = None
    training_samples: int = Field(ge=0, default=0)
    validation_samples: int = Field(ge=0, default=0)
    reference_method: str | None = None
    bland_altman_bias: float | None = None
    bland_altman_loa: float | None = None
    validated_by: str | None = None
    validation_date: datetime | None = None
    locked_date: datetime | None = None
    created_at: datetime


class DigitalMeasureScore(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    stream_id: str
    endpoint_id: str
    subject_id: str
    trial_id: str
    algorithm_id: str
    score_value: float | None = None
    score_unit: str
    scoring_status: ScoringStatus = ScoringStatus.RAW
    visit: str | None = None
    measurement_period_start: datetime
    measurement_period_end: datetime
    wear_time_hours: float = Field(ge=0, default=0)
    minimum_wear_met: bool = True
    qc_flag: str | None = None
    scored_date: datetime | None = None


class RegulatoryQualification(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    endpoint_id: str
    regulatory_authority: str
    qualification_type: str
    submission_date: datetime | None = None
    status: str = "planning"
    feedback: str | None = None
    qualification_date: datetime | None = None
    context_of_use: str
    evidence_package: list[str] = Field(default_factory=list)
    responsible_person: str
    created_at: datetime


class DigitalEndpointCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    endpoint_name: str
    description: str
    device_type: DeviceType
    measure_type: str
    unit: str
    collection_frequency: str
    concept_of_interest: str
    context_of_use: str
    created_by: str


class DigitalEndpointUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    qualification_level: EndpointQualification | None = None
    clinically_meaningful_change: float | None = None
    test_retest_icc: float | None = None
    sensitivity_to_change: float | None = None
    regulatory_reference: str | None = None


class DataStreamCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    endpoint_id: str
    trial_id: str
    subject_id: str
    device_type: DeviceType
    device_serial: str | None = None
    sampling_rate_hz: float | None = None
    site_id: str


class DataStreamUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: StreamStatus | None = None
    total_data_points: int | None = None
    wear_time_hours: float | None = None
    compliance_pct: float | None = None
    data_quality_score: float | None = None


class AlgorithmValidationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    endpoint_id: str
    algorithm_name: str
    version: str
    reference_method: str | None = None


class AlgorithmValidationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: AlgorithmStatus | None = None
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1_score: float | None = None
    auc_roc: float | None = None
    training_samples: int | None = None
    validation_samples: int | None = None
    validated_by: str | None = None


class DigitalMeasureScoreCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    stream_id: str
    endpoint_id: str
    subject_id: str
    trial_id: str
    algorithm_id: str
    score_unit: str
    measurement_period_start: datetime
    measurement_period_end: datetime
    score_value: float | None = None
    visit: str | None = None


class DigitalMeasureScoreUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    scoring_status: ScoringStatus | None = None
    score_value: float | None = None
    qc_flag: str | None = None
    minimum_wear_met: bool | None = None


class RegulatoryQualificationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    endpoint_id: str
    regulatory_authority: str
    qualification_type: str
    context_of_use: str
    responsible_person: str
    evidence_package: list[str] = Field(default_factory=list)


class RegulatoryQualificationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    feedback: str | None = None
    submission_date: datetime | None = None


class DigitalEndpointListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DigitalEndpoint] = Field(default_factory=list)
    total: int = Field(ge=0)


class DataStreamListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DataStream] = Field(default_factory=list)
    total: int = Field(ge=0)


class AlgorithmValidationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AlgorithmValidation] = Field(default_factory=list)
    total: int = Field(ge=0)


class DigitalMeasureScoreListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DigitalMeasureScore] = Field(default_factory=list)
    total: int = Field(ge=0)


class RegulatoryQualificationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[RegulatoryQualification] = Field(default_factory=list)
    total: int = Field(ge=0)


class DigitalBiomarkerMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_endpoints: int = Field(ge=0)
    endpoints_by_device: dict[str, int] = Field(default_factory=dict)
    endpoints_by_qualification: dict[str, int] = Field(default_factory=dict)
    total_streams: int = Field(ge=0)
    streams_by_status: dict[str, int] = Field(default_factory=dict)
    avg_compliance_pct: float = Field(ge=0, le=100)
    total_algorithms: int = Field(ge=0)
    algorithms_by_status: dict[str, int] = Field(default_factory=dict)
    locked_algorithms: int = Field(ge=0)
    total_scores: int = Field(ge=0)
    scores_by_status: dict[str, int] = Field(default_factory=dict)
    qc_pass_rate_pct: float = Field(ge=0, le=100)
    total_qualifications: int = Field(ge=0)
    qualifications_by_status: dict[str, int] = Field(default_factory=dict)
