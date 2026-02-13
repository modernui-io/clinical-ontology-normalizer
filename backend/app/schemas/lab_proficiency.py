"""Pydantic schemas for Lab Proficiency (LAB-PROF).

Manages laboratory proficiency operations: proficiency test tracking, inter-lab
comparison results, accreditation records, lab corrective actions, and
proficiency metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TestCategory(str, Enum):
    CLINICAL_CHEMISTRY = "clinical_chemistry"
    HEMATOLOGY = "hematology"
    IMMUNOLOGY = "immunology"
    MICROBIOLOGY = "microbiology"
    URINALYSIS = "urinalysis"
    MOLECULAR = "molecular"


class TestResult(str, Enum):
    SATISFACTORY = "satisfactory"
    UNSATISFACTORY = "unsatisfactory"
    MARGINAL = "marginal"
    NOT_GRADED = "not_graded"
    PENDING = "pending"
    WITHDRAWN = "withdrawn"


class ComparisonStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    INCONCLUSIVE = "inconclusive"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AccreditationStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    PENDING_RENEWAL = "pending_renewal"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    PROVISIONAL = "provisional"


class CorrectiveActionPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


# --- Main entities ---

class ProficiencyTest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    lab_id: str
    lab_name: str
    test_category: TestCategory
    test_name: str
    test_result: TestResult = TestResult.PENDING
    test_date: datetime
    reporting_deadline: datetime | None = None
    analyte_name: str
    reported_value: float | None = None
    expected_value: float | None = None
    acceptable_range_low: float | None = None
    acceptable_range_high: float | None = None
    z_score: float | None = None
    pt_provider: str
    cycle_number: str
    notes: str | None = None
    created_at: datetime


class LabComparison(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    reference_lab_id: str
    comparison_lab_id: str
    comparison_status: ComparisonStatus = ComparisonStatus.SCHEDULED
    analyte_name: str
    sample_count: int = Field(ge=0, default=0)
    mean_bias_pct: float | None = None
    cv_pct: float | None = None
    correlation_coefficient: float | None = None
    within_tolerance: bool | None = None
    tolerance_limit_pct: float = Field(ge=0, default=15.0)
    comparison_date: datetime | None = None
    completed_date: datetime | None = None
    reviewed_by: str | None = None
    notes: str | None = None
    created_at: datetime


class AccreditationRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    lab_id: str
    lab_name: str
    accrediting_body: str
    accreditation_number: str
    accreditation_status: AccreditationStatus = AccreditationStatus.ACTIVE
    scope: str
    issue_date: datetime
    expiry_date: datetime
    last_inspection_date: datetime | None = None
    next_inspection_date: datetime | None = None
    conditions: str | None = None
    certificate_url: str | None = None
    verified_by: str
    notes: str | None = None
    created_at: datetime


class LabCorrectiveAction(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    lab_id: str
    related_test_id: str | None = None
    related_comparison_id: str | None = None
    priority: CorrectiveActionPriority = CorrectiveActionPriority.MEDIUM
    finding_description: str
    root_cause: str | None = None
    corrective_action: str
    preventive_action: str | None = None
    assigned_to: str
    due_date: datetime
    completed_date: datetime | None = None
    is_completed: bool = False
    effectiveness_verified: bool = False
    verified_by: str | None = None
    notes: str | None = None
    created_at: datetime


# --- Create / Update schemas ---

class ProficiencyTestCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    lab_id: str
    lab_name: str
    test_category: TestCategory
    test_name: str
    analyte_name: str
    pt_provider: str
    cycle_number: str
    test_date: datetime


class ProficiencyTestUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    test_result: TestResult | None = None
    reported_value: float | None = None
    expected_value: float | None = None
    acceptable_range_low: float | None = None
    acceptable_range_high: float | None = None
    z_score: float | None = None
    notes: str | None = None


class LabComparisonCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    reference_lab_id: str
    comparison_lab_id: str
    analyte_name: str
    tolerance_limit_pct: float = Field(ge=0, default=15.0)
    sample_count: int = Field(ge=0, default=0)


class LabComparisonUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    comparison_status: ComparisonStatus | None = None
    mean_bias_pct: float | None = None
    cv_pct: float | None = None
    correlation_coefficient: float | None = None
    within_tolerance: bool | None = None
    reviewed_by: str | None = None
    notes: str | None = None


class AccreditationRecordCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    lab_id: str
    lab_name: str
    accrediting_body: str
    accreditation_number: str
    scope: str
    issue_date: datetime
    expiry_date: datetime
    verified_by: str


class AccreditationRecordUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    accreditation_status: AccreditationStatus | None = None
    last_inspection_date: datetime | None = None
    next_inspection_date: datetime | None = None
    conditions: str | None = None
    certificate_url: str | None = None
    notes: str | None = None


class LabCorrectiveActionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    lab_id: str
    finding_description: str
    corrective_action: str
    assigned_to: str
    due_date: datetime
    priority: CorrectiveActionPriority = CorrectiveActionPriority.MEDIUM
    related_test_id: str | None = None
    related_comparison_id: str | None = None


class LabCorrectiveActionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    root_cause: str | None = None
    preventive_action: str | None = None
    is_completed: bool | None = None
    completed_date: datetime | None = None
    effectiveness_verified: bool | None = None
    verified_by: str | None = None
    notes: str | None = None


# --- List responses ---

class ProficiencyTestListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ProficiencyTest] = Field(default_factory=list)
    total: int = Field(ge=0)


class LabComparisonListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[LabComparison] = Field(default_factory=list)
    total: int = Field(ge=0)


class AccreditationRecordListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[AccreditationRecord] = Field(default_factory=list)
    total: int = Field(ge=0)


class LabCorrectiveActionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[LabCorrectiveAction] = Field(default_factory=list)
    total: int = Field(ge=0)


# --- Metrics ---

class LabProficiencyMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_proficiency_tests: int = Field(ge=0)
    tests_by_category: dict[str, int] = Field(default_factory=dict)
    tests_by_result: dict[str, int] = Field(default_factory=dict)
    satisfactory_rate: float = Field(ge=0)
    total_comparisons: int = Field(ge=0)
    comparisons_by_status: dict[str, int] = Field(default_factory=dict)
    within_tolerance_rate: float = Field(ge=0)
    total_accreditations: int = Field(ge=0)
    accreditations_by_status: dict[str, int] = Field(default_factory=dict)
    active_accreditation_rate: float = Field(ge=0)
    total_corrective_actions: int = Field(ge=0)
    corrective_actions_by_priority: dict[str, int] = Field(default_factory=dict)
    corrective_action_completion_rate: float = Field(ge=0)
