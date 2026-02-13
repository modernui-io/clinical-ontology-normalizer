"""Pydantic schemas for CRF Management (CRF-MGT).

Manages case report form operations: CRF version control, field definitions,
edit check rules, CRF deployment tracking, CRF annotations, and CRF metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class CRFStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    DEPLOYED = "deployed"
    RETIRED = "retired"
    SUPERSEDED = "superseded"


class FieldType(str, Enum):
    TEXT = "text"
    NUMERIC = "numeric"
    DATE = "date"
    DROPDOWN = "dropdown"
    CHECKBOX = "checkbox"
    RADIO = "radio"


class EditCheckSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFORMATIONAL = "informational"
    HARD_STOP = "hard_stop"
    SOFT_CHECK = "soft_check"


class DeploymentStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"
    SCHEDULED = "scheduled"


class AnnotationType(str, Enum):
    SDTM_MAPPING = "sdtm_mapping"
    ADAM_MAPPING = "adam_mapping"
    COMPLETION_INSTRUCTION = "completion_instruction"
    REGULATORY_NOTE = "regulatory_note"
    VALIDATION_RULE = "validation_rule"
    CODING_DICTIONARY = "coding_dictionary"


# --- Main entities ---

class CRFVersion(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    crf_name: str
    version_number: str
    crf_status: CRFStatus = CRFStatus.DRAFT
    total_fields: int = Field(ge=0, default=0)
    total_pages: int = Field(ge=0, default=1)
    authored_by: str
    reviewed_by: str | None = None
    approved_by: str | None = None
    effective_date: datetime | None = None
    retirement_date: datetime | None = None
    change_summary: str | None = None
    notes: str | None = None
    created_at: datetime


class CRFField(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    crf_version_id: str
    field_name: str
    field_label: str
    field_type: FieldType
    page_number: int = Field(ge=1, default=1)
    display_order: int = Field(ge=0, default=0)
    is_required: bool = False
    is_key_field: bool = False
    sdtm_domain: str | None = None
    sdtm_variable: str | None = None
    codelist_name: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    default_value: str | None = None
    notes: str | None = None
    created_at: datetime


class EditCheckRule(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    crf_version_id: str
    rule_name: str
    rule_expression: str
    edit_check_severity: EditCheckSeverity = EditCheckSeverity.WARNING
    target_field_id: str
    error_message: str
    is_active: bool = True
    fire_on_save: bool = True
    fire_on_submit: bool = True
    cross_form_check: bool = False
    reference_field_id: str | None = None
    authored_by: str
    notes: str | None = None
    created_at: datetime


class CRFDeployment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    crf_version_id: str
    deployment_status: DeploymentStatus = DeploymentStatus.PENDING
    target_environment: str
    deployed_by: str
    deployment_date: datetime | None = None
    scheduled_date: datetime | None = None
    sites_affected: int = Field(ge=0, default=0)
    subjects_affected: int = Field(ge=0, default=0)
    rollback_available: bool = True
    validation_passed: bool = False
    notes: str | None = None
    created_at: datetime


class CRFAnnotation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    crf_version_id: str
    field_id: str | None = None
    annotation_type: AnnotationType
    annotation_text: str
    sdtm_dataset: str | None = None
    sdtm_variable: str | None = None
    adam_dataset: str | None = None
    adam_variable: str | None = None
    coding_dictionary: str | None = None
    annotated_by: str
    reviewed: bool = False
    reviewed_by: str | None = None
    notes: str | None = None
    created_at: datetime


# --- Create / Update schemas ---

class CRFVersionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    crf_name: str
    version_number: str
    authored_by: str
    total_pages: int = Field(ge=0, default=1)


class CRFVersionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    crf_status: CRFStatus | None = None
    reviewed_by: str | None = None
    approved_by: str | None = None
    effective_date: datetime | None = None
    change_summary: str | None = None
    notes: str | None = None


class CRFFieldCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    crf_version_id: str
    field_name: str
    field_label: str
    field_type: FieldType
    page_number: int = Field(ge=1, default=1)
    display_order: int = Field(ge=0, default=0)
    is_required: bool = False


class CRFFieldUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    is_key_field: bool | None = None
    sdtm_domain: str | None = None
    sdtm_variable: str | None = None
    codelist_name: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    notes: str | None = None


class EditCheckRuleCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    crf_version_id: str
    rule_name: str
    rule_expression: str
    target_field_id: str
    error_message: str
    edit_check_severity: EditCheckSeverity = EditCheckSeverity.WARNING
    authored_by: str


class EditCheckRuleUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    is_active: bool | None = None
    fire_on_save: bool | None = None
    fire_on_submit: bool | None = None
    error_message: str | None = None
    notes: str | None = None


class CRFDeploymentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    crf_version_id: str
    target_environment: str
    deployed_by: str
    sites_affected: int = Field(ge=0, default=0)


class CRFDeploymentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    deployment_status: DeploymentStatus | None = None
    deployment_date: datetime | None = None
    subjects_affected: int | None = None
    validation_passed: bool | None = None
    notes: str | None = None


class CRFAnnotationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    crf_version_id: str
    annotation_type: AnnotationType
    annotation_text: str
    annotated_by: str
    field_id: str | None = None


class CRFAnnotationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sdtm_dataset: str | None = None
    sdtm_variable: str | None = None
    adam_dataset: str | None = None
    adam_variable: str | None = None
    reviewed: bool | None = None
    reviewed_by: str | None = None
    notes: str | None = None


# --- List responses ---

class CRFVersionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CRFVersion] = Field(default_factory=list)
    total: int = Field(ge=0)


class CRFFieldListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CRFField] = Field(default_factory=list)
    total: int = Field(ge=0)


class EditCheckRuleListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[EditCheckRule] = Field(default_factory=list)
    total: int = Field(ge=0)


class CRFDeploymentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CRFDeployment] = Field(default_factory=list)
    total: int = Field(ge=0)


class CRFAnnotationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CRFAnnotation] = Field(default_factory=list)
    total: int = Field(ge=0)


# --- Metrics ---

class CRFManagementMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_crf_versions: int = Field(ge=0)
    versions_by_status: dict[str, int] = Field(default_factory=dict)
    total_fields: int = Field(ge=0)
    fields_by_type: dict[str, int] = Field(default_factory=dict)
    required_field_pct: float = Field(ge=0)
    total_edit_checks: int = Field(ge=0)
    edit_checks_by_severity: dict[str, int] = Field(default_factory=dict)
    active_edit_check_pct: float = Field(ge=0)
    total_deployments: int = Field(ge=0)
    deployments_by_status: dict[str, int] = Field(default_factory=dict)
    total_annotations: int = Field(ge=0)
    annotations_by_type: dict[str, int] = Field(default_factory=dict)
    annotation_review_rate: float = Field(ge=0)
