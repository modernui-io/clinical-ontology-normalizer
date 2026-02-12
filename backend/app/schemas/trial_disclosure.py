"""Pydantic schemas for Trial Disclosure Management (TRIAL-DISC).

Manages trial disclosure operations: results disclosure tracking,
registry submission records, publication mandates, lay summaries,
and compliance timeline management with disclosure metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DisclosureType(str, Enum):
    RESULTS_POSTING = "results_posting"
    SUMMARY_REPORT = "summary_report"
    LAY_SUMMARY = "lay_summary"
    CSR_SYNOPSIS = "csr_synopsis"
    REGISTRY_UPDATE = "registry_update"
    PUBLICATION = "publication"


class DisclosureStatus(str, Enum):
    NOT_DUE = "not_due"
    PENDING = "pending"
    IN_PREPARATION = "in_preparation"
    UNDER_REVIEW = "under_review"
    SUBMITTED = "submitted"
    POSTED = "posted"
    OVERDUE = "overdue"


class RegistryName(str, Enum):
    CLINICALTRIALS_GOV = "clinicaltrials_gov"
    EUDRACT = "eudract"
    CTIS = "ctis"
    JAPIC = "japic"
    ANZCTR = "anzctr"
    ISRCTN = "isrctn"


class MandateType(str, Enum):
    FDAAA_801 = "fdaaa_801"
    EU_CTR = "eu_ctr"
    HEALTH_CANADA = "health_canada"
    ICMJE = "icmje"
    WHO_ICTRP = "who_ictrp"
    COMPANY_POLICY = "company_policy"


class SummaryAudience(str, Enum):
    GENERAL_PUBLIC = "general_public"
    PATIENTS = "patients"
    HEALTHCARE_PROVIDERS = "healthcare_providers"
    REGULATORS = "regulators"
    INVESTIGATORS = "investigators"


class ResultsDisclosure(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    disclosure_type: DisclosureType
    status: DisclosureStatus = DisclosureStatus.NOT_DUE
    registry_name: RegistryName | None = None
    registry_id: str | None = None
    primary_completion_date: datetime | None = None
    disclosure_deadline: datetime | None = None
    submission_date: datetime | None = None
    posting_date: datetime | None = None
    days_to_deadline: int | None = None
    days_overdue: int | None = None
    results_summary_approved: bool = False
    statistical_tables_included: bool = False
    adverse_events_included: bool = False
    protocol_amendments_noted: bool = False
    prepared_by: str
    approved_by: str | None = None
    notes: str | None = None
    created_at: datetime


class RegistrySubmission(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    registry_name: RegistryName
    registry_id: str
    submission_type: str = "initial"
    submission_date: datetime
    acknowledgment_date: datetime | None = None
    acceptance_date: datetime | None = None
    rejection_reason: str | None = None
    protocol_version_submitted: str | None = None
    amendments_included: int = Field(ge=0, default=0)
    qc_passed: bool = False
    prs_review_status: str | None = None
    submitted_by: str
    reviewer: str | None = None
    notes: str | None = None
    created_at: datetime


class PublicationMandate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    mandate_type: MandateType
    regulation_reference: str
    deadline_months_from_completion: int = Field(ge=0, default=12)
    applicable: bool = True
    exemption_claimed: bool = False
    exemption_reason: str | None = None
    exemption_approved: bool = False
    compliance_status: str = "on_track"
    penalty_risk: str = "none"
    penalty_amount: float | None = None
    responsible_party: str
    legal_review_required: bool = False
    legal_reviewed: bool = False
    notes: str | None = None
    created_at: datetime


class LaySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    target_audience: SummaryAudience
    language: str = "en"
    version: str = "1.0"
    status: DisclosureStatus = DisclosureStatus.PENDING
    word_count: int = Field(ge=0, default=0)
    reading_level_grade: float | None = None
    patient_reviewed: bool = False
    patient_review_date: datetime | None = None
    ethics_committee_approved: bool = False
    translated_languages: list[str] = Field(default_factory=list)
    distribution_date: datetime | None = None
    distribution_channels: list[str] = Field(default_factory=list)
    authored_by: str
    reviewed_by: str | None = None
    notes: str | None = None
    created_at: datetime


class ComplianceTimeline(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    milestone_name: str
    mandate_id: str | None = None
    target_date: datetime
    actual_date: datetime | None = None
    status: str = "upcoming"
    days_remaining: int | None = None
    days_late: int | None = None
    blocking_issues: list[str] = Field(default_factory=list)
    responsible_party: str
    escalation_required: bool = False
    escalated_to: str | None = None
    escalation_date: datetime | None = None
    managed_by: str
    notes: str | None = None
    created_at: datetime


class ResultsDisclosureCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    disclosure_type: DisclosureType
    prepared_by: str
    registry_name: RegistryName | None = None
    registry_id: str | None = None
    disclosure_deadline: datetime | None = None


class ResultsDisclosureUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: DisclosureStatus | None = None
    approved_by: str | None = None
    results_summary_approved: bool | None = None
    adverse_events_included: bool | None = None
    notes: str | None = None


class RegistrySubmissionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    registry_name: RegistryName
    registry_id: str
    submitted_by: str
    submission_type: str = "initial"


class RegistrySubmissionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    qc_passed: bool | None = None
    prs_review_status: str | None = None
    rejection_reason: str | None = None
    reviewer: str | None = None
    notes: str | None = None


class PublicationMandateCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    mandate_type: MandateType
    regulation_reference: str
    responsible_party: str
    deadline_months_from_completion: int = Field(ge=0, default=12)


class PublicationMandateUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    compliance_status: str | None = None
    exemption_claimed: bool | None = None
    exemption_reason: str | None = None
    legal_reviewed: bool | None = None
    notes: str | None = None


class LaySummaryCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    target_audience: SummaryAudience
    authored_by: str
    language: str = "en"
    word_count: int = Field(ge=0, default=0)


class LaySummaryUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: DisclosureStatus | None = None
    patient_reviewed: bool | None = None
    ethics_committee_approved: bool | None = None
    reviewed_by: str | None = None
    notes: str | None = None


class ComplianceTimelineCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    milestone_name: str
    target_date: datetime
    responsible_party: str
    managed_by: str
    mandate_id: str | None = None


class ComplianceTimelineUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    actual_date: datetime | None = None
    escalation_required: bool | None = None
    escalated_to: str | None = None
    notes: str | None = None


class ResultsDisclosureListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ResultsDisclosure] = Field(default_factory=list)
    total: int = Field(ge=0)


class RegistrySubmissionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[RegistrySubmission] = Field(default_factory=list)
    total: int = Field(ge=0)


class PublicationMandateListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[PublicationMandate] = Field(default_factory=list)
    total: int = Field(ge=0)


class LaySummaryListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[LaySummary] = Field(default_factory=list)
    total: int = Field(ge=0)


class ComplianceTimelineListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ComplianceTimeline] = Field(default_factory=list)
    total: int = Field(ge=0)


class TrialDisclosureMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_disclosures: int = Field(ge=0)
    disclosures_by_type: dict[str, int] = Field(default_factory=dict)
    disclosures_by_status: dict[str, int] = Field(default_factory=dict)
    overdue_disclosures: int = Field(ge=0)
    total_registry_submissions: int = Field(ge=0)
    submissions_by_registry: dict[str, int] = Field(default_factory=dict)
    total_mandates: int = Field(ge=0)
    mandates_by_type: dict[str, int] = Field(default_factory=dict)
    mandates_at_risk: int = Field(ge=0)
    total_lay_summaries: int = Field(ge=0)
    summaries_by_audience: dict[str, int] = Field(default_factory=dict)
    total_milestones: int = Field(ge=0)
    milestones_overdue: int = Field(ge=0)
    milestones_escalated: int = Field(ge=0)
