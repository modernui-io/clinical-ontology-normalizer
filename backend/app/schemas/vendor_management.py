"""Pydantic schemas for Vendor Risk Management (COO-3).

Defines vendor records, risk assessments, compliance certifications,
and portfolio metrics for third-party vendor risk management
in the clinical trial patient recruitment platform.

COO-3: Vendor Risk Management
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class VendorCategory(str, Enum):
    """Category of vendor/third-party service."""

    CLOUD_INFRASTRUCTURE = "CLOUD_INFRASTRUCTURE"
    DATA_PROCESSING = "DATA_PROCESSING"
    CLINICAL_OPERATIONS = "CLINICAL_OPERATIONS"
    SECURITY = "SECURITY"
    COMPLIANCE = "COMPLIANCE"
    INTEGRATION = "INTEGRATION"
    ANALYTICS = "ANALYTICS"


class RiskLevel(str, Enum):
    """Risk level classification for vendors."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    MINIMAL = "MINIMAL"


class VendorStatus(str, Enum):
    """Lifecycle status of a vendor relationship."""

    ACTIVE = "ACTIVE"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    SUSPENDED = "SUSPENDED"
    OFFBOARDING = "OFFBOARDING"
    TERMINATED = "TERMINATED"


class DataAccessLevel(str, Enum):
    """Level of data access granted to a vendor."""

    NONE = "NONE"
    METADATA = "METADATA"
    PHI = "PHI"
    FULL = "FULL"


class CertificationName(str, Enum):
    """Recognized compliance certifications."""

    SOC2 = "SOC2"
    HITRUST = "HITRUST"
    ISO27001 = "ISO27001"
    HIPAA_BAA = "HIPAA_BAA"
    GDPR_DPA = "GDPR_DPA"
    FEDRAMP = "FedRAMP"


class CertificationStatus(str, Enum):
    """Verification status of a compliance certification."""

    VERIFIED = "VERIFIED"
    PENDING = "PENDING"
    EXPIRED = "EXPIRED"
    NOT_REQUIRED = "NOT_REQUIRED"


# ---------------------------------------------------------------------------
# Compliance Certification
# ---------------------------------------------------------------------------


class ComplianceCertification(BaseModel):
    """A compliance certification held by a vendor."""

    name: CertificationName = Field(..., description="Certification name")
    status: CertificationStatus = Field(..., description="Verification status")
    verified_date: datetime | None = Field(
        default=None, description="Date certification was verified"
    )
    expiry_date: datetime | None = Field(
        default=None, description="Certification expiry date"
    )


# ---------------------------------------------------------------------------
# Vendor Record
# ---------------------------------------------------------------------------


class VendorRecord(BaseModel):
    """A vendor/third-party service record."""

    id: str = Field(..., description="Unique vendor identifier")
    name: str = Field(..., description="Vendor name")
    category: VendorCategory = Field(..., description="Vendor category")
    description: str = Field(default="", description="Vendor description")
    contact_email: str = Field(default="", description="Primary contact email")
    contract_start: datetime | None = Field(
        default=None, description="Contract start date"
    )
    contract_end: datetime | None = Field(
        default=None, description="Contract end date"
    )
    annual_cost: float = Field(default=0.0, description="Annual cost in USD")
    risk_level: RiskLevel = Field(
        default=RiskLevel.MEDIUM, description="Current risk level"
    )
    status: VendorStatus = Field(
        default=VendorStatus.ACTIVE, description="Vendor lifecycle status"
    )
    data_access_level: DataAccessLevel = Field(
        default=DataAccessLevel.NONE, description="Level of data access"
    )
    certifications: list[ComplianceCertification] = Field(
        default_factory=list, description="Compliance certifications"
    )
    risk_score: float = Field(
        default=0.0, description="Calculated risk score (0-100)"
    )
    last_assessment_date: datetime | None = Field(
        default=None, description="Date of last risk assessment"
    )
    next_assessment_due: datetime | None = Field(
        default=None, description="Date next risk assessment is due"
    )
    notes: str = Field(default="", description="Additional notes")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last update timestamp")


# ---------------------------------------------------------------------------
# Vendor Create / Update
# ---------------------------------------------------------------------------


class VendorCreate(BaseModel):
    """Request to create a new vendor record."""

    name: str = Field(..., description="Vendor name")
    category: VendorCategory = Field(..., description="Vendor category")
    description: str = Field(default="", description="Vendor description")
    contact_email: str = Field(default="", description="Primary contact email")
    contract_start: datetime | None = Field(
        default=None, description="Contract start date"
    )
    contract_end: datetime | None = Field(
        default=None, description="Contract end date"
    )
    annual_cost: float = Field(default=0.0, description="Annual cost in USD")
    risk_level: RiskLevel = Field(
        default=RiskLevel.MEDIUM, description="Initial risk level"
    )
    status: VendorStatus = Field(
        default=VendorStatus.ACTIVE, description="Initial status"
    )
    data_access_level: DataAccessLevel = Field(
        default=DataAccessLevel.NONE, description="Level of data access"
    )
    certifications: list[ComplianceCertification] = Field(
        default_factory=list, description="Initial certifications"
    )
    notes: str = Field(default="", description="Additional notes")


class VendorUpdate(BaseModel):
    """Request to update an existing vendor record."""

    name: str | None = Field(default=None, description="Updated vendor name")
    category: VendorCategory | None = Field(
        default=None, description="Updated category"
    )
    description: str | None = Field(
        default=None, description="Updated description"
    )
    contact_email: str | None = Field(
        default=None, description="Updated contact email"
    )
    contract_start: datetime | None = Field(
        default=None, description="Updated contract start"
    )
    contract_end: datetime | None = Field(
        default=None, description="Updated contract end"
    )
    annual_cost: float | None = Field(
        default=None, description="Updated annual cost"
    )
    risk_level: RiskLevel | None = Field(
        default=None, description="Updated risk level"
    )
    status: VendorStatus | None = Field(
        default=None, description="Updated status"
    )
    data_access_level: DataAccessLevel | None = Field(
        default=None, description="Updated data access level"
    )
    certifications: list[ComplianceCertification] | None = Field(
        default=None, description="Updated certifications"
    )
    notes: str | None = Field(default=None, description="Updated notes")


# ---------------------------------------------------------------------------
# Risk Assessment
# ---------------------------------------------------------------------------


class VendorRiskAssessment(BaseModel):
    """A risk assessment conducted on a vendor."""

    id: str = Field(..., description="Assessment unique identifier")
    vendor_id: str = Field(..., description="Assessed vendor ID")
    assessment_date: datetime = Field(..., description="Date of assessment")
    assessed_by: str = Field(..., description="Person who conducted the assessment")
    data_handling_score: float = Field(
        ..., description="Data handling practices score (0-10)"
    )
    security_posture_score: float = Field(
        ..., description="Security posture score (0-10)"
    )
    compliance_score: float = Field(
        ..., description="Compliance adherence score (0-10)"
    )
    business_continuity_score: float = Field(
        ..., description="Business continuity score (0-10)"
    )
    overall_risk_score: float = Field(
        ..., description="Weighted overall risk score (0-100)"
    )
    findings: list[str] = Field(
        default_factory=list, description="Assessment findings"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Recommendations"
    )
    risk_level: RiskLevel = Field(
        ..., description="Calculated risk level from score"
    )


class AssessmentRequest(BaseModel):
    """Request to conduct a vendor risk assessment."""

    assessed_by: str = Field(..., description="Person conducting the assessment")
    data_handling_score: float = Field(
        ..., description="Data handling practices score (0-10)"
    )
    security_posture_score: float = Field(
        ..., description="Security posture score (0-10)"
    )
    compliance_score: float = Field(
        ..., description="Compliance adherence score (0-10)"
    )
    business_continuity_score: float = Field(
        ..., description="Business continuity score (0-10)"
    )
    findings: list[str] = Field(
        default_factory=list, description="Assessment findings"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Recommendations"
    )


# ---------------------------------------------------------------------------
# Vendor Metrics
# ---------------------------------------------------------------------------


class VendorMetrics(BaseModel):
    """Aggregated vendor portfolio metrics."""

    total_vendors: int = Field(..., description="Total number of vendors")
    by_category: dict[str, int] = Field(
        ..., description="Vendor count by category"
    )
    by_risk_level: dict[str, int] = Field(
        ..., description="Vendor count by risk level"
    )
    by_status: dict[str, int] = Field(
        ..., description="Vendor count by status"
    )
    total_annual_spend: float = Field(
        ..., description="Total annual vendor spend"
    )
    assessments_due_30days: int = Field(
        ..., description="Assessments due in next 30 days"
    )
    expired_certifications: int = Field(
        ..., description="Count of expired certifications"
    )
    average_risk_score: float = Field(
        ..., description="Average risk score across all vendors"
    )


# ---------------------------------------------------------------------------
# Certification Alert
# ---------------------------------------------------------------------------


class CertificationAlert(BaseModel):
    """Alert for expiring or expired vendor certification."""

    vendor_id: str = Field(..., description="Vendor ID")
    vendor_name: str = Field(..., description="Vendor name")
    certification: ComplianceCertification = Field(
        ..., description="The certification in question"
    )
    days_until_expiry: int | None = Field(
        default=None, description="Days until expiry (negative if expired)"
    )


# ---------------------------------------------------------------------------
# Contract Renewal
# ---------------------------------------------------------------------------


class ContractRenewal(BaseModel):
    """Contract renewal notification."""

    vendor_id: str = Field(..., description="Vendor ID")
    vendor_name: str = Field(..., description="Vendor name")
    contract_end: datetime = Field(..., description="Contract end date")
    days_until_expiry: int = Field(..., description="Days until contract expires")
    annual_cost: float = Field(..., description="Annual cost")
    risk_level: RiskLevel = Field(..., description="Current risk level")


# ---------------------------------------------------------------------------
# Response Wrappers
# ---------------------------------------------------------------------------


class VendorListResponse(BaseModel):
    """Paginated vendor list response."""

    items: list[VendorRecord] = Field(..., description="Vendor records")
    total: int = Field(..., description="Total matching records")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Page offset")


class AssessmentListResponse(BaseModel):
    """List of assessments for a vendor."""

    items: list[VendorRiskAssessment] = Field(..., description="Assessments")
    total: int = Field(..., description="Total assessments")
    vendor_id: str = Field(..., description="Vendor ID")
