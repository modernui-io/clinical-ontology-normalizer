"""Pydantic schemas for Country-Level Regulatory Requirements (REG-COUNTRY).

Manages country-specific regulatory requirements, ethics committee submissions,
import/export licenses, local regulatory agent assignments, country activation
tracking, and regulatory compliance metrics per jurisdiction.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SubmissionType(str, Enum):
    ETHICS_COMMITTEE = "ethics_committee"
    REGULATORY_AUTHORITY = "regulatory_authority"
    IMPORT_LICENSE = "import_license"
    EXPORT_LICENSE = "export_license"
    LOCAL_LABELING = "local_labeling"
    SAFETY_REPORTING = "safety_reporting"


class ApprovalStatus(str, Enum):
    NOT_SUBMITTED = "not_submitted"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    CONDITIONALLY_APPROVED = "conditionally_approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ActivationStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    ACTIVATED = "activated"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class AgentRole(str, Enum):
    LOCAL_REGULATORY_AGENT = "local_regulatory_agent"
    LEGAL_REPRESENTATIVE = "legal_representative"
    PHARMACOVIGILANCE_CONTACT = "pharmacovigilance_contact"
    IMPORT_AGENT = "import_agent"


class CountryRequirement(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    country: str
    country_code: str
    requirement_type: SubmissionType
    description: str
    regulatory_authority: str
    submission_deadline: datetime
    approval_status: ApprovalStatus = ApprovalStatus.NOT_SUBMITTED
    submission_date: datetime | None = None
    approval_date: datetime | None = None
    approval_reference: str | None = None
    conditions: list[str] = Field(default_factory=list)
    documents_required: list[str] = Field(default_factory=list)
    responsible_person: str
    created_at: datetime


class EthicsSubmission(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    country: str
    committee_name: str
    submission_date: datetime
    protocol_version: str
    icf_version: str
    approval_status: ApprovalStatus = ApprovalStatus.SUBMITTED
    approval_date: datetime | None = None
    approval_reference: str | None = None
    expiry_date: datetime | None = None
    conditions: list[str] = Field(default_factory=list)
    annual_renewal_due: datetime | None = None
    submitted_by: str


class ImportExportLicense(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    country: str
    license_type: str
    license_number: str | None = None
    product_name: str
    quantity_authorized: int = Field(ge=0)
    status: ApprovalStatus = ApprovalStatus.SUBMITTED
    application_date: datetime
    approval_date: datetime | None = None
    expiry_date: datetime | None = None
    customs_reference: str | None = None
    responsible_person: str


class LocalAgent(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    country: str
    agent_name: str
    organization: str
    role: AgentRole
    contact_email: str
    contact_phone: str | None = None
    contract_start: datetime
    contract_end: datetime | None = None
    active: bool = True


class CountryActivation(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    country: str
    country_code: str
    status: ActivationStatus = ActivationStatus.PLANNED
    planned_activation_date: datetime
    actual_activation_date: datetime | None = None
    regulatory_approved: bool = False
    ethics_approved: bool = False
    import_license_obtained: bool = False
    local_agent_assigned: bool = False
    sites_planned: int = Field(ge=0, default=0)
    sites_activated: int = Field(ge=0, default=0)
    target_enrollment: int = Field(ge=0, default=0)
    current_enrollment: int = Field(ge=0, default=0)


class CountryRequirementCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    country: str
    country_code: str
    requirement_type: SubmissionType
    description: str
    regulatory_authority: str
    submission_deadline: datetime
    responsible_person: str
    documents_required: list[str] = Field(default_factory=list)


class CountryRequirementUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    approval_status: ApprovalStatus | None = None
    submission_date: datetime | None = None
    approval_date: datetime | None = None
    approval_reference: str | None = None
    conditions: list[str] | None = None


class EthicsSubmissionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    country: str
    committee_name: str
    protocol_version: str
    icf_version: str
    submitted_by: str


class EthicsSubmissionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    approval_status: ApprovalStatus | None = None
    approval_date: datetime | None = None
    approval_reference: str | None = None
    expiry_date: datetime | None = None
    conditions: list[str] | None = None


class ImportExportLicenseCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    country: str
    license_type: str
    product_name: str
    quantity_authorized: int = Field(ge=0)
    responsible_person: str


class ImportExportLicenseUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: ApprovalStatus | None = None
    license_number: str | None = None
    approval_date: datetime | None = None
    expiry_date: datetime | None = None
    customs_reference: str | None = None


class LocalAgentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    country: str
    agent_name: str
    organization: str
    role: AgentRole
    contact_email: str
    contact_phone: str | None = None
    contract_start: datetime
    contract_end: datetime | None = None


class LocalAgentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    agent_name: str | None = None
    organization: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    contract_end: datetime | None = None
    active: bool | None = None


class CountryActivationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    country: str
    country_code: str
    planned_activation_date: datetime
    sites_planned: int = Field(ge=0, default=0)
    target_enrollment: int = Field(ge=0, default=0)


class CountryActivationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: ActivationStatus | None = None
    regulatory_approved: bool | None = None
    ethics_approved: bool | None = None
    import_license_obtained: bool | None = None
    local_agent_assigned: bool | None = None
    sites_activated: int | None = None
    current_enrollment: int | None = None


class CountryRequirementListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CountryRequirement] = Field(default_factory=list)
    total: int = Field(ge=0)


class EthicsSubmissionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[EthicsSubmission] = Field(default_factory=list)
    total: int = Field(ge=0)


class ImportExportLicenseListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ImportExportLicense] = Field(default_factory=list)
    total: int = Field(ge=0)


class LocalAgentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[LocalAgent] = Field(default_factory=list)
    total: int = Field(ge=0)


class CountryActivationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CountryActivation] = Field(default_factory=list)
    total: int = Field(ge=0)


class CountryRegulatoryMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_requirements: int = Field(ge=0)
    requirements_by_status: dict[str, int] = Field(default_factory=dict)
    requirements_by_type: dict[str, int] = Field(default_factory=dict)
    total_ethics_submissions: int = Field(ge=0)
    ethics_by_status: dict[str, int] = Field(default_factory=dict)
    total_licenses: int = Field(ge=0)
    licenses_by_status: dict[str, int] = Field(default_factory=dict)
    total_agents: int = Field(ge=0)
    active_agents: int = Field(ge=0)
    total_countries: int = Field(ge=0)
    countries_activated: int = Field(ge=0)
    countries_by_status: dict[str, int] = Field(default_factory=dict)
    overall_activation_pct: float = Field(ge=0, le=100)
