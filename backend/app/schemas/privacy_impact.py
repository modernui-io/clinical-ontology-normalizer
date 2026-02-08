"""Pydantic schemas for Privacy Impact Assessment (DPIA) framework.

CLO-4: GDPR Article 35 and HIPAA-compliant Privacy Impact Assessment
schemas for the clinical trial patient recruitment platform.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class PIAStatus(str, Enum):
    """PIA lifecycle status."""

    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REQUIRES_MITIGATION = "REQUIRES_MITIGATION"
    MITIGATIONS_IN_PROGRESS = "MITIGATIONS_IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class RiskLikelihood(int, Enum):
    """Likelihood of a privacy risk occurring."""

    RARE = 1
    UNLIKELY = 2
    POSSIBLE = 3
    LIKELY = 4
    ALMOST_CERTAIN = 5


class RiskImpact(int, Enum):
    """Impact severity of a privacy risk."""

    NEGLIGIBLE = 1
    MINOR = 2
    MODERATE = 3
    MAJOR = 4
    SEVERE = 5


class RiskLevel(str, Enum):
    """Calculated risk level based on risk score."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DataCategoryType(str, Enum):
    """Types of data categories processed."""

    DEMOGRAPHICS = "DEMOGRAPHICS"
    CLINICAL = "CLINICAL"
    GENETIC = "GENETIC"
    BEHAVIORAL = "BEHAVIORAL"
    FINANCIAL = "FINANCIAL"
    IDENTIFIERS = "IDENTIFIERS"


class LegalBasis(str, Enum):
    """Legal basis for processing under GDPR."""

    CONSENT = "CONSENT"
    LEGITIMATE_INTEREST = "LEGITIMATE_INTEREST"
    LEGAL_OBLIGATION = "LEGAL_OBLIGATION"
    VITAL_INTEREST = "VITAL_INTEREST"
    PUBLIC_INTEREST = "PUBLIC_INTEREST"


class DataSubjectType(str, Enum):
    """Types of data subjects."""

    PATIENTS = "PATIENTS"
    STAFF = "STAFF"
    CAREGIVERS = "CAREGIVERS"
    RESEARCHERS = "RESEARCHERS"


class AffectedRight(str, Enum):
    """Data subject rights potentially affected."""

    ACCESS = "ACCESS"
    RECTIFICATION = "RECTIFICATION"
    ERASURE = "ERASURE"
    PORTABILITY = "PORTABILITY"
    OBJECTION = "OBJECTION"
    RESTRICTION = "RESTRICTION"


class MitigationStatus(str, Enum):
    """Status of risk mitigation measures."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    IMPLEMENTED = "IMPLEMENTED"
    VERIFIED = "VERIFIED"


# ---------------------------------------------------------------------------
# Core Data Models
# ---------------------------------------------------------------------------


class DataProcessingActivity(BaseModel):
    """A data processing activity within a PIA."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="Unique activity identifier")
    name: str = Field(description="Name of the processing activity")
    description: str = Field(description="Description of the processing")
    data_categories: list[DataCategoryType] = Field(
        description="Categories of data processed"
    )
    processing_purpose: str = Field(description="Purpose of the processing")
    legal_basis: LegalBasis = Field(description="Legal basis for processing")
    data_subjects: list[DataSubjectType] = Field(
        description="Types of data subjects"
    )
    retention_period_months: int = Field(
        description="Data retention period in months"
    )
    cross_border_transfer: bool = Field(
        default=False, description="Whether data is transferred cross-border"
    )
    automated_decision_making: bool = Field(
        default=False, description="Whether automated decision-making is used"
    )
    third_party_sharing: bool = Field(
        default=False, description="Whether data is shared with third parties"
    )
    third_parties: list[str] = Field(
        default_factory=list, description="Names of third parties receiving data"
    )


class PrivacyRisk(BaseModel):
    """An identified privacy risk within a PIA."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="Unique risk identifier")
    title: str = Field(description="Risk title")
    description: str = Field(description="Risk description")
    likelihood: RiskLikelihood = Field(description="Likelihood of the risk")
    impact: RiskImpact = Field(description="Impact severity of the risk")
    risk_score: int = Field(description="Calculated risk score (likelihood * impact)")
    risk_level: RiskLevel = Field(description="Calculated risk level from score")
    affected_rights: list[AffectedRight] = Field(
        default_factory=list, description="Data subject rights affected"
    )
    mitigation_measures: list[str] = Field(
        default_factory=list, description="Planned or implemented mitigations"
    )
    residual_risk_score: int | None = Field(
        default=None, description="Risk score after mitigation"
    )
    mitigation_status: MitigationStatus = Field(
        default=MitigationStatus.PENDING, description="Status of mitigation"
    )


class PIARecord(BaseModel):
    """Full Privacy Impact Assessment record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="Unique PIA identifier")
    title: str = Field(description="PIA title")
    description: str = Field(description="PIA description")
    status: PIAStatus = Field(description="Current PIA status")
    processing_activities: list[DataProcessingActivity] = Field(
        default_factory=list, description="Data processing activities assessed"
    )
    identified_risks: list[PrivacyRisk] = Field(
        default_factory=list, description="Identified privacy risks"
    )
    assessor: str = Field(description="Person conducting the assessment")
    reviewer: str | None = Field(
        default=None, description="Person reviewing the assessment"
    )
    dpo_approval: bool = Field(
        default=False, description="Whether DPO has approved"
    )
    dpo_approval_date: datetime | None = Field(
        default=None, description="Date of DPO approval"
    )
    necessity_assessment: str | None = Field(
        default=None, description="Assessment of processing necessity"
    )
    proportionality_assessment: str | None = Field(
        default=None, description="Assessment of processing proportionality"
    )
    consultation_required: bool = Field(
        default=False,
        description="Whether supervisory authority consultation is required",
    )
    created_at: datetime = Field(description="Record creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    completed_at: datetime | None = Field(
        default=None, description="Assessment completion timestamp"
    )
    next_review_date: datetime | None = Field(
        default=None, description="Next scheduled review date"
    )


class PIAMetrics(BaseModel):
    """Aggregated PIA program metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_assessments: int = Field(description="Total number of PIAs")
    by_status: dict[str, int] = Field(description="Count by PIA status")
    high_risk_count: int = Field(
        description="Number of PIAs with HIGH or CRITICAL risks"
    )
    open_mitigations: int = Field(
        description="Number of risks with incomplete mitigations"
    )
    avg_risk_score: float = Field(
        description="Average risk score across all identified risks"
    )
    processing_activities_assessed: int = Field(
        description="Total processing activities assessed"
    )
    cross_border_count: int = Field(
        description="Activities involving cross-border transfers"
    )
    automated_decision_count: int = Field(
        description="Activities involving automated decision-making"
    )


class PIATemplateQuestion(BaseModel):
    """A template question for PIA assessment."""

    category: str = Field(description="Question category")
    question: str = Field(description="The assessment question")
    guidance: str = Field(description="Guidance for answering")


class PIATemplate(BaseModel):
    """PIA assessment template."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="Template identifier")
    name: str = Field(description="Template name")
    description: str = Field(description="Template description")
    default_questions: list[PIATemplateQuestion] = Field(
        default_factory=list, description="Default assessment questions"
    )


# ---------------------------------------------------------------------------
# Request / Response Wrappers
# ---------------------------------------------------------------------------


class PIACreateRequest(BaseModel):
    """Request to create a new PIA."""

    title: str = Field(..., min_length=1, max_length=500, description="PIA title")
    description: str = Field(..., min_length=1, description="PIA description")
    assessor: str = Field(..., min_length=1, description="Assessor name")


class PIAUpdateRequest(BaseModel):
    """Request to update a PIA."""

    title: str | None = Field(default=None, max_length=500, description="Updated title")
    description: str | None = Field(default=None, description="Updated description")
    assessor: str | None = Field(default=None, description="Updated assessor")
    reviewer: str | None = Field(default=None, description="Updated reviewer")
    necessity_assessment: str | None = Field(
        default=None, description="Updated necessity assessment"
    )
    proportionality_assessment: str | None = Field(
        default=None, description="Updated proportionality assessment"
    )
    next_review_date: datetime | None = Field(
        default=None, description="Updated next review date"
    )


class ProcessingActivityCreateRequest(BaseModel):
    """Request to add a processing activity to a PIA."""

    name: str = Field(..., min_length=1, description="Activity name")
    description: str = Field(..., min_length=1, description="Activity description")
    data_categories: list[DataCategoryType] = Field(
        ..., min_length=1, description="Data categories"
    )
    processing_purpose: str = Field(..., min_length=1, description="Processing purpose")
    legal_basis: LegalBasis = Field(..., description="Legal basis")
    data_subjects: list[DataSubjectType] = Field(
        ..., min_length=1, description="Data subjects"
    )
    retention_period_months: int = Field(
        ..., ge=1, description="Retention period in months"
    )
    cross_border_transfer: bool = Field(default=False)
    automated_decision_making: bool = Field(default=False)
    third_party_sharing: bool = Field(default=False)
    third_parties: list[str] = Field(default_factory=list)


class RiskCreateRequest(BaseModel):
    """Request to add a risk to a PIA."""

    title: str = Field(..., min_length=1, description="Risk title")
    description: str = Field(..., min_length=1, description="Risk description")
    likelihood: RiskLikelihood = Field(..., description="Risk likelihood")
    impact: RiskImpact = Field(..., description="Risk impact")
    affected_rights: list[AffectedRight] = Field(
        default_factory=list, description="Affected rights"
    )


class RiskMitigationUpdateRequest(BaseModel):
    """Request to update risk mitigation."""

    mitigation_measures: list[str] = Field(
        ..., min_length=1, description="Mitigation measures"
    )
    residual_risk_score: int = Field(
        ..., ge=1, le=25, description="Residual risk score after mitigation"
    )


class PIAApproveRequest(BaseModel):
    """Request to approve a PIA."""

    reviewer: str = Field(..., min_length=1, description="Reviewer name")


class PIAListResponse(BaseModel):
    """Paginated list of PIAs."""

    assessments: list[PIARecord]
    total: int
    limit: int
    offset: int


class PIATemplateListResponse(BaseModel):
    """List of PIA templates."""

    templates: list[PIATemplate]
    total: int


class ConsultationCheckResponse(BaseModel):
    """Result of supervisory authority consultation check."""

    consultation_required: bool = Field(
        description="Whether consultation is required"
    )
    reasons: list[str] = Field(
        default_factory=list,
        description="Reasons consultation is required",
    )
