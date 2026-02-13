"""Pydantic schemas for Patient Insurance Verification (PIV-VER).

Manages patient insurance verification operations: eligibility checks,
pre-authorization requests, coverage determinations, and reimbursement
tracking with metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class EligibilityStatus(str, Enum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    PENDING_VERIFICATION = "pending_verification"
    EXPIRED = "expired"
    CONDITIONAL = "conditional"
    UNKNOWN = "unknown"


class PreAuthStatus(str, Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    DENIED = "denied"
    PENDING_REVIEW = "pending_review"
    PARTIALLY_APPROVED = "partially_approved"
    EXPIRED = "expired"


class CoverageType(str, Enum):
    PRIVATE = "private"
    MEDICARE = "medicare"
    MEDICAID = "medicaid"
    TRICARE = "tricare"
    VA = "va"
    UNINSURED = "uninsured"


class ReimbursementStatus(str, Enum):
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PARTIALLY_PAID = "partially_paid"
    DENIED = "denied"
    APPEALED = "appealed"


class DenialReason(str, Enum):
    NOT_MEDICALLY_NECESSARY = "not_medically_necessary"
    EXPERIMENTAL = "experimental"
    OUT_OF_NETWORK = "out_of_network"
    PRIOR_AUTH_REQUIRED = "prior_auth_required"
    COVERAGE_LAPSED = "coverage_lapsed"
    OTHER = "other"


# --- Main entities ---

class EligibilityCheck(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    eligibility_status: EligibilityStatus = EligibilityStatus.PENDING_VERIFICATION
    coverage_type: CoverageType
    insurance_provider: str
    policy_number: str | None = None
    group_number: str | None = None
    coverage_start_date: datetime | None = None
    coverage_end_date: datetime | None = None
    verification_date: datetime
    verified_by: str
    verification_method: str | None = None
    copay_amount: float = Field(ge=0, default=0.0)
    deductible_remaining: float = Field(ge=0, default=0.0)
    notes: str | None = None
    created_at: datetime


class PreAuthorizationRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    pre_auth_status: PreAuthStatus = PreAuthStatus.REQUESTED
    procedure_code: str
    procedure_description: str
    requesting_provider: str
    insurance_provider: str
    request_date: datetime
    decision_date: datetime | None = None
    authorization_number: str | None = None
    approved_units: int = Field(ge=0, default=0)
    expiration_date: datetime | None = None
    denial_reason: DenialReason | None = None
    appeal_deadline: datetime | None = None
    notes: str | None = None
    created_at: datetime


class CoverageDetermination(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    coverage_type: CoverageType
    procedure_category: str
    is_covered: bool = False
    sponsor_responsibility: bool = True
    patient_responsibility_pct: float = Field(ge=0, le=100, default=0.0)
    determination_date: datetime
    determined_by: str
    policy_reference: str | None = None
    qualifying_criteria: str | None = None
    exclusion_criteria: str | None = None
    effective_date: datetime | None = None
    review_date: datetime | None = None
    notes: str | None = None
    created_at: datetime


class ReimbursementTracking(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    site_id: str
    reimbursement_status: ReimbursementStatus = ReimbursementStatus.SUBMITTED
    claim_number: str | None = None
    procedure_code: str
    billed_amount: float = Field(ge=0, default=0.0)
    approved_amount: float = Field(ge=0, default=0.0)
    paid_amount: float = Field(ge=0, default=0.0)
    patient_responsibility: float = Field(ge=0, default=0.0)
    submission_date: datetime
    payment_date: datetime | None = None
    denial_reason: DenialReason | None = None
    appeal_filed: bool = False
    appeal_date: datetime | None = None
    processed_by: str
    notes: str | None = None
    created_at: datetime


# --- Create / Update schemas ---

class EligibilityCheckCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    coverage_type: CoverageType
    insurance_provider: str
    verification_date: datetime
    verified_by: str
    eligibility_status: EligibilityStatus = EligibilityStatus.PENDING_VERIFICATION


class EligibilityCheckUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    eligibility_status: EligibilityStatus | None = None
    policy_number: str | None = None
    coverage_start_date: datetime | None = None
    coverage_end_date: datetime | None = None
    copay_amount: float | None = None
    deductible_remaining: float | None = None
    notes: str | None = None


class PreAuthorizationRequestCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    procedure_code: str
    procedure_description: str
    requesting_provider: str
    insurance_provider: str
    request_date: datetime
    pre_auth_status: PreAuthStatus = PreAuthStatus.REQUESTED


class PreAuthorizationRequestUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    pre_auth_status: PreAuthStatus | None = None
    decision_date: datetime | None = None
    authorization_number: str | None = None
    approved_units: int | None = None
    denial_reason: DenialReason | None = None
    notes: str | None = None


class CoverageDeterminationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    coverage_type: CoverageType
    procedure_category: str
    determination_date: datetime
    determined_by: str


class CoverageDeterminationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    is_covered: bool | None = None
    sponsor_responsibility: bool | None = None
    patient_responsibility_pct: float | None = None
    qualifying_criteria: str | None = None
    exclusion_criteria: str | None = None
    notes: str | None = None


class ReimbursementTrackingCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    site_id: str
    procedure_code: str
    billed_amount: float = Field(ge=0, default=0.0)
    submission_date: datetime
    processed_by: str
    reimbursement_status: ReimbursementStatus = ReimbursementStatus.SUBMITTED


class ReimbursementTrackingUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    reimbursement_status: ReimbursementStatus | None = None
    approved_amount: float | None = None
    paid_amount: float | None = None
    payment_date: datetime | None = None
    denial_reason: DenialReason | None = None
    appeal_filed: bool | None = None
    notes: str | None = None


# --- List responses ---

class EligibilityCheckListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[EligibilityCheck] = Field(default_factory=list)
    total: int = Field(ge=0)


class PreAuthorizationRequestListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[PreAuthorizationRequest] = Field(default_factory=list)
    total: int = Field(ge=0)


class CoverageDeterminationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CoverageDetermination] = Field(default_factory=list)
    total: int = Field(ge=0)


class ReimbursementTrackingListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ReimbursementTracking] = Field(default_factory=list)
    total: int = Field(ge=0)


# --- Metrics ---

class PatientInsuranceVerificationMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_eligibility_checks: int = Field(ge=0)
    checks_by_status: dict[str, int] = Field(default_factory=dict)
    checks_by_coverage_type: dict[str, int] = Field(default_factory=dict)
    total_pre_authorizations: int = Field(ge=0)
    pre_auths_by_status: dict[str, int] = Field(default_factory=dict)
    pre_auth_approval_rate: float = Field(ge=0)
    total_coverage_determinations: int = Field(ge=0)
    coverage_rate: float = Field(ge=0)
    total_reimbursements: int = Field(ge=0)
    reimbursements_by_status: dict[str, int] = Field(default_factory=dict)
    total_billed_amount: float = Field(ge=0)
    total_paid_amount: float = Field(ge=0)
