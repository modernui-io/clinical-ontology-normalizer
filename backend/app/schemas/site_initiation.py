"""Pydantic schemas for Site Initiation & Activation (CLINICAL-17).

Manages the full lifecycle of clinical trial site initiation: site selection
and identification, qualification visits, regulatory document collection,
site readiness assessment, activation milestones, and essential documents
tracking from the CRO perspective.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SiteStatus(str, Enum):
    """Lifecycle status of a clinical trial site."""

    IDENTIFIED = "identified"
    SELECTED = "selected"
    QUALIFICATION_VISIT = "qualification_visit"
    REGULATORY_SUBMITTED = "regulatory_submitted"
    ACTIVATED = "activated"
    ENROLLING = "enrolling"
    CLOSED = "closed"


class DocumentType(str, Enum):
    """Type of essential regulatory document."""

    INFORMED_CONSENT = "informed_consent"
    IRB_APPROVAL = "irb_approval"
    CV_PRINCIPAL_INVESTIGATOR = "cv_principal_investigator"
    MEDICAL_LICENSE = "medical_license"
    FINANCIAL_DISCLOSURE = "financial_disclosure"
    FDA_1572 = "fda_1572"
    PROTOCOL_SIGNATURE_PAGE = "protocol_signature_page"
    DELEGATION_LOG = "delegation_log"
    TRAINING_CERTIFICATE = "training_certificate"
    LAB_CERTIFICATION = "lab_certification"
    INSURANCE_CERTIFICATE = "insurance_certificate"
    SITE_CONTRACT = "site_contract"
    BUDGET_AGREEMENT = "budget_agreement"


class DocumentStatus(str, Enum):
    """Status of a regulatory document."""

    NOT_SUBMITTED = "not_submitted"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    EXPIRED = "expired"
    REJECTED = "rejected"


class MilestoneType(str, Enum):
    """Type of site activation milestone."""

    SITE_IDENTIFIED = "site_identified"
    CONFIDENTIALITY_AGREEMENT = "confidentiality_agreement"
    FEASIBILITY_COMPLETE = "feasibility_complete"
    SITE_SELECTED = "site_selected"
    QUALIFICATION_VISIT_SCHEDULED = "qualification_visit_scheduled"
    QUALIFICATION_VISIT_COMPLETE = "qualification_visit_complete"
    IRB_SUBMISSION = "irb_submission"
    IRB_APPROVAL = "irb_approval"
    CONTRACT_EXECUTED = "contract_executed"
    BUDGET_FINALIZED = "budget_finalized"
    REGULATORY_PACKAGE_COMPLETE = "regulatory_package_complete"
    SITE_INITIATION_VISIT = "site_initiation_visit"
    SITE_ACTIVATED = "site_activated"
    FIRST_PATIENT_SCREENED = "first_patient_screened"


class MilestoneStatus(str, Enum):
    """Status of a milestone."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    WAIVED = "waived"


class ReadinessCategory(str, Enum):
    """Category for site readiness assessment."""

    REGULATORY = "regulatory"
    STAFFING = "staffing"
    FACILITIES = "facilities"
    EQUIPMENT = "equipment"
    PHARMACY = "pharmacy"
    LABORATORY = "laboratory"
    TRAINING = "training"
    IT_SYSTEMS = "it_systems"


class QualificationRecommendation(str, Enum):
    """Recommendation from a qualification visit."""

    APPROVED = "approved"
    APPROVED_WITH_CONDITIONS = "approved_with_conditions"
    NOT_RECOMMENDED = "not_recommended"
    DEFERRED = "deferred"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class QualificationVisit(BaseModel):
    """A qualification visit record for a clinical trial site."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique qualification visit identifier")
    site_id: str = Field(..., description="Parent site initiation identifier")
    visit_date: datetime = Field(..., description="Date of the qualification visit")
    attendees: list[str] = Field(
        default_factory=list, description="List of attendees at the visit"
    )
    findings: str = Field(..., description="Key findings from the visit")
    recommendation: QualificationRecommendation = Field(
        ..., description="Visit recommendation outcome"
    )
    action_items: list[str] = Field(
        default_factory=list, description="Action items arising from the visit"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")


class RegulatoryDocument(BaseModel):
    """A regulatory document tracked for site initiation."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique document identifier")
    site_id: str = Field(..., description="Parent site initiation identifier")
    doc_type: DocumentType = Field(..., description="Type of regulatory document")
    status: DocumentStatus = Field(
        default=DocumentStatus.NOT_SUBMITTED, description="Document status"
    )
    submitted_date: datetime | None = Field(None, description="Date document was submitted")
    approved_date: datetime | None = Field(None, description="Date document was approved")
    expiry_date: datetime | None = Field(None, description="Document expiry date")
    notes: str | None = Field(None, description="Additional notes about the document")
    version: str | None = Field(None, description="Document version")


class SiteMilestone(BaseModel):
    """A milestone in the site activation process."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique milestone identifier")
    site_id: str = Field(..., description="Parent site initiation identifier")
    milestone_type: MilestoneType = Field(..., description="Type of milestone")
    target_date: datetime = Field(..., description="Target completion date")
    actual_date: datetime | None = Field(None, description="Actual completion date")
    status: MilestoneStatus = Field(
        default=MilestoneStatus.PENDING, description="Milestone status"
    )
    notes: str | None = Field(None, description="Milestone notes")


class ReadinessAssessment(BaseModel):
    """Site readiness assessment with category scores."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Site initiation identifier")
    category_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Readiness scores by category (0.0-100.0)",
    )
    overall_score: float = Field(
        ..., ge=0.0, le=100.0, description="Overall readiness score (0-100)"
    )
    blockers: list[str] = Field(
        default_factory=list, description="List of blocking issues preventing activation"
    )
    assessed_date: datetime = Field(..., description="Date of last assessment")
    assessed_by: str = Field(..., description="Person who performed the assessment")


class SiteInitiation(BaseModel):
    """A site initiation and activation record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique site initiation identifier")
    trial_id: str = Field(..., description="Trial identifier")
    site_number: str = Field(..., description="Site number (e.g., '1001')")
    site_name: str = Field(..., description="Full site name")
    principal_investigator: str = Field(..., description="Principal investigator name")
    institution: str = Field(..., description="Institution or facility name")
    country: str = Field(default="US", description="Country code")
    status: SiteStatus = Field(
        default=SiteStatus.IDENTIFIED, description="Site lifecycle status"
    )
    target_enrollment: int = Field(
        default=0, ge=0, description="Target enrollment count for this site"
    )
    current_enrollment: int = Field(
        default=0, ge=0, description="Current enrollment count"
    )
    qualification_visits: list[QualificationVisit] = Field(
        default_factory=list, description="Qualification visit records"
    )
    regulatory_documents: list[RegulatoryDocument] = Field(
        default_factory=list, description="Regulatory document records"
    )
    milestones: list[SiteMilestone] = Field(
        default_factory=list, description="Activation milestones"
    )
    activation_date: datetime | None = Field(None, description="Date site was activated")
    created_at: datetime = Field(..., description="Record creation timestamp")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class SiteInitiationCreate(BaseModel):
    """Request to create a new site initiation record."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    site_number: str = Field(..., description="Site number")
    site_name: str = Field(..., description="Full site name")
    principal_investigator: str = Field(..., description="Principal investigator name")
    institution: str = Field(..., description="Institution or facility name")
    country: str = Field(default="US", description="Country code")
    target_enrollment: int = Field(default=0, ge=0, description="Target enrollment count")


class SiteInitiationUpdate(BaseModel):
    """Request to update a site initiation record."""

    model_config = ConfigDict(from_attributes=True)

    site_name: str | None = Field(None, description="Full site name")
    principal_investigator: str | None = Field(None, description="Principal investigator name")
    institution: str | None = Field(None, description="Institution or facility name")
    country: str | None = Field(None, description="Country code")
    target_enrollment: int | None = Field(None, ge=0, description="Target enrollment count")
    current_enrollment: int | None = Field(None, ge=0, description="Current enrollment count")


class QualificationVisitCreate(BaseModel):
    """Request to create a qualification visit record."""

    model_config = ConfigDict(from_attributes=True)

    visit_date: datetime = Field(..., description="Date of the qualification visit")
    attendees: list[str] = Field(
        default_factory=list, description="List of attendees"
    )
    findings: str = Field(..., description="Key findings from the visit")
    recommendation: QualificationRecommendation = Field(
        ..., description="Visit recommendation outcome"
    )
    action_items: list[str] = Field(
        default_factory=list, description="Action items from the visit"
    )


class RegulatoryDocumentCreate(BaseModel):
    """Request to create a regulatory document record."""

    model_config = ConfigDict(from_attributes=True)

    doc_type: DocumentType = Field(..., description="Type of regulatory document")
    submitted_date: datetime | None = Field(None, description="Submission date")
    notes: str | None = Field(None, description="Document notes")
    version: str | None = Field(None, description="Document version")


class RegulatoryDocumentUpdate(BaseModel):
    """Request to update a regulatory document record."""

    model_config = ConfigDict(from_attributes=True)

    status: DocumentStatus | None = Field(None, description="Document status")
    submitted_date: datetime | None = Field(None, description="Submission date")
    approved_date: datetime | None = Field(None, description="Approval date")
    expiry_date: datetime | None = Field(None, description="Expiry date")
    notes: str | None = Field(None, description="Document notes")
    version: str | None = Field(None, description="Document version")


class MilestoneUpdate(BaseModel):
    """Request to update a site milestone."""

    model_config = ConfigDict(from_attributes=True)

    target_date: datetime | None = Field(None, description="Target date")
    actual_date: datetime | None = Field(None, description="Actual completion date")
    status: MilestoneStatus | None = Field(None, description="Milestone status")
    notes: str | None = Field(None, description="Milestone notes")


class ReadinessUpdate(BaseModel):
    """Request to update readiness assessment."""

    model_config = ConfigDict(from_attributes=True)

    category_scores: dict[str, float] = Field(
        ..., description="Readiness scores by category (0.0-100.0)"
    )
    blockers: list[str] = Field(
        default_factory=list, description="List of blocking issues"
    )
    assessed_by: str = Field(..., description="Person performing the assessment")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class SiteInitiationListResponse(BaseModel):
    """List of site initiation records."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SiteInitiation] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class QualificationVisitListResponse(BaseModel):
    """List of qualification visits."""

    model_config = ConfigDict(from_attributes=True)

    items: list[QualificationVisit] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class RegulatoryDocumentListResponse(BaseModel):
    """List of regulatory documents."""

    model_config = ConfigDict(from_attributes=True)

    items: list[RegulatoryDocument] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class MilestoneListResponse(BaseModel):
    """List of site milestones."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SiteMilestone] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class SiteActivationMetrics(BaseModel):
    """Aggregated site activation metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_sites: int = Field(ge=0, description="Total sites tracked")
    sites_by_status: dict[str, int] = Field(
        default_factory=dict, description="Site counts by status"
    )
    avg_days_to_activate: float = Field(
        ge=0.0, description="Average days from identification to activation"
    )
    sites_activated: int = Field(ge=0, description="Sites currently activated or enrolling")
    sites_pending_activation: int = Field(
        ge=0, description="Sites not yet activated"
    )
    avg_readiness_score: float = Field(
        ge=0.0, le=100.0, description="Average readiness score across sites"
    )
    total_regulatory_documents: int = Field(
        ge=0, description="Total regulatory documents tracked"
    )
    documents_by_status: dict[str, int] = Field(
        default_factory=dict, description="Document counts by status"
    )
    bottleneck_categories: list[str] = Field(
        default_factory=list,
        description="Readiness categories most often blocking activation",
    )
    avg_target_enrollment: float = Field(
        ge=0.0, description="Average target enrollment per site"
    )
