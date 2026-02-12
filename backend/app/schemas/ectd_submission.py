"""Pydantic schemas for eCTD Submission Management (eCTD-MGMT).

Manages electronic Common Technical Document submissions: eCTD sequence
planning, module assembly, document lifecycle, submission tracking,
health authority responses, and eCTD operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class CTDModule(str, Enum):
    MODULE_1 = "module_1_regional"
    MODULE_2 = "module_2_summaries"
    MODULE_3 = "module_3_quality"
    MODULE_4 = "module_4_nonclinical"
    MODULE_5 = "module_5_clinical"


class SubmissionType(str, Enum):
    INITIAL = "initial"
    AMENDMENT = "amendment"
    SUPPLEMENT = "supplement"
    ANNUAL_REPORT = "annual_report"
    RESPONSE = "response_to_questions"
    VARIATION = "variation"
    RENEWAL = "renewal"


class SequenceStatus(str, Enum):
    PLANNING = "planning"
    AUTHORING = "authoring"
    QC_REVIEW = "qc_review"
    PUBLISHING = "publishing"
    READY = "ready"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"


class DocumentLifecycle(str, Enum):
    NEW = "new"
    APPEND = "append"
    REPLACE = "replace"
    DELETE = "delete"


class HAResponseType(str, Enum):
    ACKNOWLEDGMENT = "acknowledgment"
    INFORMATION_REQUEST = "information_request"
    REFUSE_TO_FILE = "refuse_to_file"
    COMPLETE_RESPONSE = "complete_response"
    APPROVAL = "approval"
    APPROVABLE = "approvable"
    NOT_APPROVABLE = "not_approvable"


class RegulatoryRegion(str, Enum):
    US_FDA = "us_fda"
    EU_EMA = "eu_ema"
    JAPAN_PMDA = "japan_pmda"
    CHINA_NMPA = "china_nmpa"
    CANADA_HC = "canada_hc"
    UK_MHRA = "uk_mhra"
    AUSTRALIA_TGA = "australia_tga"


class ECTDSequence(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    sequence_number: str
    submission_type: SubmissionType
    region: RegulatoryRegion
    status: SequenceStatus = SequenceStatus.PLANNING
    title: str
    description: str | None = None
    target_date: datetime
    actual_submission_date: datetime | None = None
    acknowledgment_date: datetime | None = None
    tracking_number: str | None = None
    ectd_version: str = "4.0"
    total_documents: int = Field(ge=0, default=0)
    total_size_mb: float = Field(ge=0, default=0)
    publisher: str
    created_at: datetime


class ECTDDocument(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sequence_id: str
    module: CTDModule
    section_number: str
    title: str
    file_name: str
    lifecycle_operation: DocumentLifecycle = DocumentLifecycle.NEW
    version: str = "1.0"
    page_count: int = Field(ge=0, default=0)
    size_kb: float = Field(ge=0, default=0)
    checksum: str | None = None
    author: str
    reviewer: str | None = None
    approved: bool = False
    approved_date: datetime | None = None
    created_at: datetime


class ECTDValidation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sequence_id: str
    validation_tool: str
    validation_date: datetime
    passed: bool
    errors: int = Field(ge=0, default=0)
    warnings: int = Field(ge=0, default=0)
    error_details: list[str] = Field(default_factory=list)
    validator: str
    report_reference: str | None = None


class HAResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sequence_id: str
    response_type: HAResponseType
    response_date: datetime
    due_date: datetime | None = None
    summary: str
    questions: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    assigned_to: str | None = None
    status: str = "open"
    resolved_date: datetime | None = None
    created_at: datetime


class SubmissionPlan(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    plan_name: str
    target_regions: list[RegulatoryRegion] = Field(default_factory=list)
    planned_sequences: int = Field(ge=0, default=0)
    completed_sequences: int = Field(ge=0, default=0)
    primary_contact: str
    regulatory_lead: str
    status: str = "active"
    notes: str | None = None
    created_at: datetime


class ECTDSequenceCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    sequence_number: str
    submission_type: SubmissionType
    region: RegulatoryRegion
    title: str
    description: str | None = None
    target_date: datetime
    publisher: str


class ECTDSequenceUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: SequenceStatus | None = None
    actual_submission_date: datetime | None = None
    tracking_number: str | None = None
    total_documents: int | None = None
    total_size_mb: float | None = None


class ECTDDocumentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sequence_id: str
    module: CTDModule
    section_number: str
    title: str
    file_name: str
    lifecycle_operation: DocumentLifecycle = DocumentLifecycle.NEW
    author: str


class ECTDDocumentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    version: str | None = None
    reviewer: str | None = None
    approved: bool | None = None
    page_count: int | None = None
    size_kb: float | None = None
    checksum: str | None = None


class ECTDValidationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sequence_id: str
    validation_tool: str
    passed: bool
    errors: int = Field(ge=0, default=0)
    warnings: int = Field(ge=0, default=0)
    error_details: list[str] = Field(default_factory=list)
    validator: str


class HAResponseCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sequence_id: str
    response_type: HAResponseType
    summary: str
    questions: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    assigned_to: str | None = None
    due_date: datetime | None = None


class HAResponseUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    assigned_to: str | None = None
    action_items: list[str] | None = None


class SubmissionPlanCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    plan_name: str
    target_regions: list[RegulatoryRegion] = Field(default_factory=list)
    primary_contact: str
    regulatory_lead: str


class SubmissionPlanUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    planned_sequences: int | None = None
    completed_sequences: int | None = None
    status: str | None = None
    notes: str | None = None


class ECTDSequenceListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ECTDSequence] = Field(default_factory=list)
    total: int = Field(ge=0)


class ECTDDocumentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ECTDDocument] = Field(default_factory=list)
    total: int = Field(ge=0)


class ECTDValidationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ECTDValidation] = Field(default_factory=list)
    total: int = Field(ge=0)


class HAResponseListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[HAResponse] = Field(default_factory=list)
    total: int = Field(ge=0)


class SubmissionPlanListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SubmissionPlan] = Field(default_factory=list)
    total: int = Field(ge=0)


class ECTDMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_sequences: int = Field(ge=0)
    sequences_by_status: dict[str, int] = Field(default_factory=dict)
    sequences_by_type: dict[str, int] = Field(default_factory=dict)
    sequences_by_region: dict[str, int] = Field(default_factory=dict)
    total_documents: int = Field(ge=0)
    documents_by_module: dict[str, int] = Field(default_factory=dict)
    approved_documents: int = Field(ge=0)
    total_validations: int = Field(ge=0)
    validation_pass_rate_pct: float = Field(ge=0, le=100)
    total_ha_responses: int = Field(ge=0)
    responses_by_type: dict[str, int] = Field(default_factory=dict)
    open_responses: int = Field(ge=0)
    total_plans: int = Field(ge=0)
    active_plans: int = Field(ge=0)
