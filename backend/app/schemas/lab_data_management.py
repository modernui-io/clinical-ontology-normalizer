"""Pydantic schemas for Lab Data Management (LAB-DATA).

Manages laboratory data operations: lab normal range definitions, lab alert
rules, specimen tracking, lab result management, reference range validation,
and lab data operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class LabCategory(str, Enum):
    HEMATOLOGY = "hematology"
    CHEMISTRY = "chemistry"
    COAGULATION = "coagulation"
    URINALYSIS = "urinalysis"
    IMMUNOLOGY = "immunology"
    ENDOCRINE = "endocrine"
    CARDIAC = "cardiac"
    HEPATIC = "hepatic"
    RENAL = "renal"
    LIPID = "lipid"


class AlertSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    PANIC = "panic"


class SpecimenStatus(str, Enum):
    COLLECTED = "collected"
    IN_TRANSIT = "in_transit"
    RECEIVED = "received"
    PROCESSING = "processing"
    ANALYZED = "analyzed"
    STORED = "stored"
    DISCARDED = "discarded"
    LOST = "lost"


class ResultStatus(str, Enum):
    PENDING = "pending"
    PRELIMINARY = "preliminary"
    FINAL = "final"
    AMENDED = "amended"
    CANCELLED = "cancelled"


class AbnormalFlag(str, Enum):
    NORMAL = "normal"
    LOW = "low"
    HIGH = "high"
    CRITICAL_LOW = "critical_low"
    CRITICAL_HIGH = "critical_high"
    ABNORMAL = "abnormal"


class GradeLevel(str, Enum):
    GRADE_0 = "grade_0"
    GRADE_1 = "grade_1_mild"
    GRADE_2 = "grade_2_moderate"
    GRADE_3 = "grade_3_severe"
    GRADE_4 = "grade_4_life_threatening"


class LabNormalRange(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    test_name: str
    test_code: str
    category: LabCategory
    unit: str
    lower_limit: float | None = None
    upper_limit: float | None = None
    critical_low: float | None = None
    critical_high: float | None = None
    gender_specific: bool = False
    gender: str | None = None
    age_min: int | None = None
    age_max: int | None = None
    lab_id: str | None = None
    effective_date: datetime
    source: str


class LabAlertRule(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    test_name: str
    test_code: str
    severity: AlertSeverity
    condition: str
    threshold_value: float | None = None
    threshold_unit: str | None = None
    grade_level: GradeLevel | None = None
    action_required: str
    notification_list: list[str] = Field(default_factory=list)
    active: bool = True
    created_by: str
    created_at: datetime


class LabSpecimen(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    visit: str
    specimen_type: str
    collection_date: datetime
    collection_time: str | None = None
    fasting: bool | None = None
    status: SpecimenStatus = SpecimenStatus.COLLECTED
    central_lab: str
    accession_number: str | None = None
    received_date: datetime | None = None
    condition_on_receipt: str | None = None
    storage_temperature: str | None = None
    site_id: str


class LabResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    specimen_id: str
    trial_id: str
    subject_id: str
    test_name: str
    test_code: str
    category: LabCategory
    value: float | None = None
    value_text: str | None = None
    unit: str
    reference_low: float | None = None
    reference_high: float | None = None
    abnormal_flag: AbnormalFlag = AbnormalFlag.NORMAL
    grade: GradeLevel | None = None
    status: ResultStatus = ResultStatus.PENDING
    result_date: datetime | None = None
    verified_by: str | None = None
    clinically_significant: bool | None = None
    investigator_comment: str | None = None


class LabAlert(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    result_id: str
    rule_id: str
    trial_id: str
    subject_id: str
    severity: AlertSeverity
    message: str
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_date: datetime | None = None
    action_taken: str | None = None
    generated_date: datetime


class LabNormalRangeCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    test_name: str
    test_code: str
    category: LabCategory
    unit: str
    lower_limit: float | None = None
    upper_limit: float | None = None
    critical_low: float | None = None
    critical_high: float | None = None
    gender_specific: bool = False
    gender: str | None = None
    source: str


class LabAlertRuleCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    test_name: str
    test_code: str
    severity: AlertSeverity
    condition: str
    threshold_value: float | None = None
    threshold_unit: str | None = None
    action_required: str
    notification_list: list[str] = Field(default_factory=list)
    created_by: str


class LabAlertRuleUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    severity: AlertSeverity | None = None
    threshold_value: float | None = None
    action_required: str | None = None
    active: bool | None = None


class LabSpecimenCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    visit: str
    specimen_type: str
    central_lab: str
    site_id: str
    fasting: bool | None = None


class LabSpecimenUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: SpecimenStatus | None = None
    accession_number: str | None = None
    condition_on_receipt: str | None = None


class LabResultCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    specimen_id: str
    trial_id: str
    subject_id: str
    test_name: str
    test_code: str
    category: LabCategory
    unit: str
    value: float | None = None
    value_text: str | None = None


class LabResultUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: ResultStatus | None = None
    abnormal_flag: AbnormalFlag | None = None
    grade: GradeLevel | None = None
    verified_by: str | None = None
    clinically_significant: bool | None = None
    investigator_comment: str | None = None


class LabAlertUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    acknowledged: bool | None = None
    acknowledged_by: str | None = None
    action_taken: str | None = None


class LabNormalRangeListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[LabNormalRange] = Field(default_factory=list)
    total: int = Field(ge=0)


class LabAlertRuleListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[LabAlertRule] = Field(default_factory=list)
    total: int = Field(ge=0)


class LabSpecimenListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[LabSpecimen] = Field(default_factory=list)
    total: int = Field(ge=0)


class LabResultListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[LabResult] = Field(default_factory=list)
    total: int = Field(ge=0)


class LabAlertListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[LabAlert] = Field(default_factory=list)
    total: int = Field(ge=0)


class LabDataMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_normal_ranges: int = Field(ge=0)
    ranges_by_category: dict[str, int] = Field(default_factory=dict)
    total_alert_rules: int = Field(ge=0)
    active_alert_rules: int = Field(ge=0)
    total_specimens: int = Field(ge=0)
    specimens_by_status: dict[str, int] = Field(default_factory=dict)
    total_results: int = Field(ge=0)
    results_by_status: dict[str, int] = Field(default_factory=dict)
    results_by_flag: dict[str, int] = Field(default_factory=dict)
    abnormal_rate_pct: float = Field(ge=0, le=100)
    critical_results: int = Field(ge=0)
    total_alerts: int = Field(ge=0)
    alerts_by_severity: dict[str, int] = Field(default_factory=dict)
    unacknowledged_alerts: int = Field(ge=0)
