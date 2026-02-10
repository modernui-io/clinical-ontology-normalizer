"""Pydantic schemas for Clinical Trial Insurance management.

Manages insurance policies, coverage requirements, certificate tracking, claims
management, renewal workflows, and regulatory compliance for clinical trial
liability coverage across multiple jurisdictions.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PolicyType(str, Enum):
    """Type of insurance policy for clinical trials."""

    CLINICAL_TRIAL_LIABILITY = "clinical_trial_liability"
    PRODUCT_LIABILITY = "product_liability"
    PROFESSIONAL_INDEMNITY = "professional_indemnity"
    GENERAL_LIABILITY = "general_liability"
    NO_FAULT_COMPENSATION = "no_fault_compensation"


class PolicyStatus(str, Enum):
    """Lifecycle status of an insurance policy."""

    DRAFT = "draft"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    RENEWED = "renewed"
    PENDING_RENEWAL = "pending_renewal"


class CoverageScope(str, Enum):
    """Geographic scope of insurance coverage."""

    GLOBAL = "global"
    REGIONAL = "regional"
    COUNTRY_SPECIFIC = "country_specific"


class ClaimStatus(str, Enum):
    """Lifecycle status of an insurance claim."""

    FILED = "filed"
    UNDER_INVESTIGATION = "under_investigation"
    APPROVED = "approved"
    DENIED = "denied"
    SETTLED = "settled"
    CLOSED = "closed"


class CertificateStatus(str, Enum):
    """Status of an insurance certificate."""

    ACTIVE = "active"
    EXPIRED = "expired"
    PENDING = "pending"
    REVOKED = "revoked"


class RenewalStatus(str, Enum):
    """Status of an insurance renewal."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class InsurancePolicy(BaseModel):
    """An insurance policy covering a clinical trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique policy identifier")
    trial_id: str = Field(..., description="Associated clinical trial identifier")
    policy_number: str = Field(..., description="Insurance policy number")
    policy_type: PolicyType = Field(..., description="Type of insurance policy")
    insurer: str = Field(..., description="Insurance company name")
    coverage_scope: CoverageScope = Field(..., description="Geographic scope of coverage")
    countries_covered: list[str] = Field(
        default_factory=list, description="List of countries covered by the policy"
    )
    coverage_amount: float = Field(..., ge=0, description="Total coverage amount")
    deductible: float = Field(default=0.0, ge=0, description="Policy deductible amount")
    premium: float = Field(..., ge=0, description="Annual premium amount")
    premium_currency: str = Field(default="USD", description="Currency of premium and coverage amounts")
    effective_date: datetime = Field(..., description="Policy effective date")
    expiry_date: datetime = Field(..., description="Policy expiration date")
    renewal_date: datetime | None = Field(None, description="Scheduled renewal date")
    status: PolicyStatus = Field(default=PolicyStatus.DRAFT, description="Current policy status")
    broker: str | None = Field(None, description="Insurance broker name")
    special_conditions: str | None = Field(
        None, description="Special conditions or endorsements on the policy"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last update timestamp")


class InsuranceCertificate(BaseModel):
    """A certificate of insurance for a specific site or jurisdiction."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique certificate identifier")
    policy_id: str = Field(..., description="Associated policy identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    site_id: str = Field(..., description="Associated site identifier")
    certificate_number: str = Field(..., description="Certificate reference number")
    issued_date: datetime = Field(..., description="Certificate issue date")
    expiry_date: datetime = Field(..., description="Certificate expiration date")
    coverage_amount: float = Field(..., ge=0, description="Coverage amount on this certificate")
    status: CertificateStatus = Field(
        default=CertificateStatus.PENDING, description="Certificate status"
    )
    regulatory_requirement: str | None = Field(
        None, description="Regulatory requirement this certificate satisfies"
    )
    country: str = Field(..., description="Country this certificate applies to")
    filed_with_authority: bool = Field(
        default=False, description="Whether certificate has been filed with regulatory authority"
    )
    authority_name: str | None = Field(None, description="Name of the regulatory authority")
    filing_date: datetime | None = Field(None, description="Date filed with authority")
    created_at: datetime = Field(..., description="Record creation timestamp")


class InsuranceClaim(BaseModel):
    """An insurance claim filed against a clinical trial policy."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique claim identifier")
    policy_id: str = Field(..., description="Associated policy identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    site_id: str = Field(..., description="Site where the incident occurred")
    patient_id: str | None = Field(None, description="Affected patient identifier")
    claim_number: str = Field(..., description="Insurance claim reference number")
    claim_date: datetime = Field(..., description="Date the claim was filed")
    incident_date: datetime = Field(..., description="Date the incident occurred")
    incident_description: str = Field(..., description="Description of the incident")
    claim_amount: float = Field(..., ge=0, description="Claimed amount")
    settled_amount: float | None = Field(None, ge=0, description="Final settled amount")
    status: ClaimStatus = Field(default=ClaimStatus.FILED, description="Current claim status")
    adjuster: str | None = Field(None, description="Assigned claims adjuster")
    investigation_notes: str | None = Field(None, description="Investigation notes and findings")
    resolution_date: datetime | None = Field(None, description="Date the claim was resolved")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last update timestamp")


class CoverageRequirement(BaseModel):
    """A regulatory coverage requirement for a specific country/jurisdiction."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique requirement identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    country: str = Field(..., description="Country requiring coverage")
    regulatory_authority: str = Field(..., description="Regulatory authority name")
    required_policy_type: PolicyType = Field(
        ..., description="Required type of insurance policy"
    )
    minimum_coverage_amount: float = Field(
        ..., ge=0, description="Minimum required total coverage amount"
    )
    per_patient_minimum: float = Field(
        default=0.0, ge=0, description="Minimum coverage per patient"
    )
    aggregate_minimum: float = Field(
        default=0.0, ge=0, description="Minimum aggregate coverage"
    )
    proof_required: bool = Field(
        default=True, description="Whether proof of insurance must be filed"
    )
    deadline: datetime = Field(..., description="Deadline to meet this requirement")
    met: bool = Field(default=False, description="Whether this requirement is currently satisfied")
    notes: str | None = Field(None, description="Additional notes or instructions")
    created_at: datetime = Field(..., description="Record creation timestamp")


class InsuranceRenewal(BaseModel):
    """A renewal record for an insurance policy."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique renewal identifier")
    policy_id: str = Field(..., description="Associated policy identifier")
    renewal_date: datetime = Field(..., description="Target renewal date")
    new_premium: float = Field(..., ge=0, description="Premium amount for the renewal term")
    premium_change_pct: float = Field(
        ..., description="Percentage change in premium from prior term"
    )
    coverage_changes: str | None = Field(
        None, description="Description of coverage changes in the renewal"
    )
    approved_by: str | None = Field(None, description="Name of the person who approved the renewal")
    approved_date: datetime | None = Field(None, description="Date the renewal was approved")
    status: RenewalStatus = Field(
        default=RenewalStatus.PENDING, description="Renewal processing status"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class InsurancePolicyCreate(BaseModel):
    """Request to create a new insurance policy."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Associated trial identifier")
    policy_number: str = Field(..., description="Insurance policy number")
    policy_type: PolicyType = Field(..., description="Type of insurance policy")
    insurer: str = Field(..., description="Insurance company name")
    coverage_scope: CoverageScope = Field(..., description="Geographic scope of coverage")
    countries_covered: list[str] = Field(
        default_factory=list, description="List of countries covered"
    )
    coverage_amount: float = Field(..., ge=0, description="Total coverage amount")
    deductible: float = Field(default=0.0, ge=0, description="Policy deductible")
    premium: float = Field(..., ge=0, description="Annual premium")
    premium_currency: str = Field(default="USD", description="Premium currency")
    effective_date: datetime = Field(..., description="Policy effective date")
    expiry_date: datetime = Field(..., description="Policy expiration date")
    renewal_date: datetime | None = Field(None, description="Scheduled renewal date")
    broker: str | None = Field(None, description="Insurance broker name")
    special_conditions: str | None = Field(None, description="Special conditions")


class InsurancePolicyUpdate(BaseModel):
    """Request to update an insurance policy."""

    model_config = ConfigDict(from_attributes=True)

    policy_type: PolicyType | None = Field(None, description="Policy type")
    insurer: str | None = Field(None, description="Insurer name")
    coverage_scope: CoverageScope | None = Field(None, description="Coverage scope")
    countries_covered: list[str] | None = Field(None, description="Countries covered")
    coverage_amount: float | None = Field(None, ge=0, description="Coverage amount")
    deductible: float | None = Field(None, ge=0, description="Deductible")
    premium: float | None = Field(None, ge=0, description="Premium")
    premium_currency: str | None = Field(None, description="Premium currency")
    effective_date: datetime | None = Field(None, description="Effective date")
    expiry_date: datetime | None = Field(None, description="Expiry date")
    renewal_date: datetime | None = Field(None, description="Renewal date")
    status: PolicyStatus | None = Field(None, description="Policy status")
    broker: str | None = Field(None, description="Broker name")
    special_conditions: str | None = Field(None, description="Special conditions")


class InsuranceCertificateCreate(BaseModel):
    """Request to issue a new insurance certificate."""

    model_config = ConfigDict(from_attributes=True)

    policy_id: str = Field(..., description="Associated policy identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    site_id: str = Field(..., description="Associated site identifier")
    coverage_amount: float = Field(..., ge=0, description="Coverage amount on certificate")
    country: str = Field(..., description="Country this certificate applies to")
    regulatory_requirement: str | None = Field(None, description="Regulatory requirement")
    authority_name: str | None = Field(None, description="Regulatory authority name")


class InsuranceCertificateUpdate(BaseModel):
    """Request to update an insurance certificate."""

    model_config = ConfigDict(from_attributes=True)

    status: CertificateStatus | None = Field(None, description="Certificate status")
    coverage_amount: float | None = Field(None, ge=0, description="Coverage amount")
    filed_with_authority: bool | None = Field(None, description="Filed with authority flag")
    authority_name: str | None = Field(None, description="Authority name")
    filing_date: datetime | None = Field(None, description="Filing date")


class InsuranceClaimCreate(BaseModel):
    """Request to file a new insurance claim."""

    model_config = ConfigDict(from_attributes=True)

    policy_id: str = Field(..., description="Associated policy identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    site_id: str = Field(..., description="Site where incident occurred")
    patient_id: str | None = Field(None, description="Affected patient identifier")
    incident_date: datetime = Field(..., description="Date of the incident")
    incident_description: str = Field(..., description="Description of the incident")
    claim_amount: float = Field(..., ge=0, description="Claimed amount")


class InsuranceClaimUpdate(BaseModel):
    """Request to update an insurance claim."""

    model_config = ConfigDict(from_attributes=True)

    status: ClaimStatus | None = Field(None, description="Claim status")
    settled_amount: float | None = Field(None, ge=0, description="Settled amount")
    adjuster: str | None = Field(None, description="Claims adjuster")
    investigation_notes: str | None = Field(None, description="Investigation notes")
    resolution_date: datetime | None = Field(None, description="Resolution date")


class CoverageRequirementCreate(BaseModel):
    """Request to create a new coverage requirement."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Associated trial identifier")
    country: str = Field(..., description="Country requiring coverage")
    regulatory_authority: str = Field(..., description="Regulatory authority name")
    required_policy_type: PolicyType = Field(..., description="Required policy type")
    minimum_coverage_amount: float = Field(..., ge=0, description="Minimum coverage amount")
    per_patient_minimum: float = Field(default=0.0, ge=0, description="Per-patient minimum")
    aggregate_minimum: float = Field(default=0.0, ge=0, description="Aggregate minimum")
    proof_required: bool = Field(default=True, description="Whether proof is required")
    deadline: datetime = Field(..., description="Compliance deadline")
    notes: str | None = Field(None, description="Additional notes")


class CoverageRequirementUpdate(BaseModel):
    """Request to update a coverage requirement."""

    model_config = ConfigDict(from_attributes=True)

    minimum_coverage_amount: float | None = Field(None, ge=0, description="Minimum coverage")
    per_patient_minimum: float | None = Field(None, ge=0, description="Per-patient minimum")
    aggregate_minimum: float | None = Field(None, ge=0, description="Aggregate minimum")
    proof_required: bool | None = Field(None, description="Proof required flag")
    deadline: datetime | None = Field(None, description="Compliance deadline")
    met: bool | None = Field(None, description="Whether requirement is met")
    notes: str | None = Field(None, description="Notes")


class InsuranceRenewalCreate(BaseModel):
    """Request to initiate a policy renewal."""

    model_config = ConfigDict(from_attributes=True)

    policy_id: str = Field(..., description="Associated policy identifier")
    renewal_date: datetime = Field(..., description="Target renewal date")
    new_premium: float = Field(..., ge=0, description="New premium amount")
    premium_change_pct: float = Field(..., description="Premium change percentage")
    coverage_changes: str | None = Field(None, description="Coverage changes description")


class InsuranceRenewalUpdate(BaseModel):
    """Request to update a renewal record."""

    model_config = ConfigDict(from_attributes=True)

    new_premium: float | None = Field(None, ge=0, description="New premium")
    premium_change_pct: float | None = Field(None, description="Premium change %")
    coverage_changes: str | None = Field(None, description="Coverage changes")
    approved_by: str | None = Field(None, description="Approved by")
    approved_date: datetime | None = Field(None, description="Approval date")
    status: RenewalStatus | None = Field(None, description="Renewal status")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class InsurancePolicyListResponse(BaseModel):
    """List of insurance policies."""

    model_config = ConfigDict(from_attributes=True)

    items: list[InsurancePolicy] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class InsuranceCertificateListResponse(BaseModel):
    """List of insurance certificates."""

    model_config = ConfigDict(from_attributes=True)

    items: list[InsuranceCertificate] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class InsuranceClaimListResponse(BaseModel):
    """List of insurance claims."""

    model_config = ConfigDict(from_attributes=True)

    items: list[InsuranceClaim] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class CoverageRequirementListResponse(BaseModel):
    """List of coverage requirements."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CoverageRequirement] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class InsuranceRenewalListResponse(BaseModel):
    """List of insurance renewals."""

    model_config = ConfigDict(from_attributes=True)

    items: list[InsuranceRenewal] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Compliance check result
# ---------------------------------------------------------------------------


class CoverageComplianceResult(BaseModel):
    """Result of a coverage compliance check for a trial."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    total_requirements: int = Field(ge=0, description="Total coverage requirements")
    requirements_met: int = Field(ge=0, description="Number of requirements satisfied")
    requirements_unmet: int = Field(ge=0, description="Number of requirements not satisfied")
    compliance_pct: float = Field(
        ge=0.0, le=100.0, description="Overall compliance percentage"
    )
    fully_compliant: bool = Field(..., description="Whether all requirements are met")
    unmet_details: list[CoverageRequirement] = Field(
        default_factory=list, description="Details of unmet requirements"
    )


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class InsuranceMetrics(BaseModel):
    """Aggregated insurance operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_policies: int = Field(ge=0, description="Total insurance policies")
    active_policies: int = Field(ge=0, description="Number of active policies")
    policies_by_type: dict[str, int] = Field(
        default_factory=dict, description="Policy counts by type"
    )
    policies_by_status: dict[str, int] = Field(
        default_factory=dict, description="Policy counts by status"
    )
    total_coverage_amount: float = Field(ge=0, description="Sum of all active policy coverage")
    total_premium: float = Field(ge=0, description="Sum of all active policy premiums")
    total_certificates: int = Field(ge=0, description="Total certificates issued")
    active_certificates: int = Field(ge=0, description="Number of active certificates")
    total_claims: int = Field(ge=0, description="Total claims filed")
    open_claims: int = Field(ge=0, description="Number of open/active claims")
    total_claimed_amount: float = Field(ge=0, description="Sum of all claim amounts")
    total_settled_amount: float = Field(ge=0, description="Sum of all settled amounts")
    total_requirements: int = Field(ge=0, description="Total coverage requirements")
    requirements_met: int = Field(ge=0, description="Number of requirements met")
    compliance_pct: float = Field(
        ge=0.0, le=100.0, description="Overall compliance percentage"
    )
    pending_renewals: int = Field(ge=0, description="Number of pending renewals")
    expiring_within_30_days: int = Field(
        ge=0, description="Policies expiring within 30 days"
    )
    expiring_within_90_days: int = Field(
        ge=0, description="Policies expiring within 90 days"
    )
