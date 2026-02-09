"""Pydantic schemas for Protocol Amendment Management (CLINICAL-16).

Manages protocol amendment lifecycle: amendment creation and tracking, IRB
submission coordination across sites, impact assessment with operational/
enrollment/safety/cost/timeline dimensions, implementation tracking,
re-consent progress monitoring, and cross-trial amendment metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AmendmentType(str, Enum):
    """Type of protocol amendment."""

    SUBSTANTIAL = "substantial"
    NON_SUBSTANTIAL = "non_substantial"
    ADMINISTRATIVE = "administrative"
    GLOBAL = "global"
    LOCAL = "local"


class AmendmentStatus(str, Enum):
    """Lifecycle status of a protocol amendment."""

    DRAFT = "draft"
    SPONSOR_REVIEW = "sponsor_review"
    IRB_SUBMITTED = "irb_submitted"
    IRB_APPROVED = "irb_approved"
    IMPLEMENTED = "implemented"
    WITHDRAWN = "withdrawn"


class AmendmentImpact(str, Enum):
    """Area impacted by a protocol amendment."""

    ENROLLMENT_CRITERIA = "enrollment_criteria"
    ENDPOINTS = "endpoints"
    DOSING = "dosing"
    VISIT_SCHEDULE = "visit_schedule"
    SAFETY_MONITORING = "safety_monitoring"
    SAMPLE_SIZE = "sample_size"
    STATISTICAL_PLAN = "statistical_plan"
    INFORMED_CONSENT = "informed_consent"


class IRBStatus(str, Enum):
    """Status of an IRB submission."""

    PENDING = "pending"
    APPROVED = "approved"
    MODIFICATIONS_REQUIRED = "modifications_required"
    DEFERRED = "deferred"
    NOT_APPLICABLE = "not_applicable"


class ImpactSeverity(str, Enum):
    """Severity level for impact assessment dimensions."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class IRBSubmission(BaseModel):
    """An IRB submission for a protocol amendment at a specific site."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique IRB submission identifier")
    amendment_id: str = Field(..., description="Parent amendment identifier")
    irb_name: str = Field(..., description="Name of the IRB/ethics committee")
    site_id: str = Field(..., description="Site identifier for this submission")
    submitted_date: datetime = Field(..., description="Date submitted to IRB")
    status: IRBStatus = Field(default=IRBStatus.PENDING, description="IRB review status")
    approval_date: datetime | None = Field(None, description="Date of IRB approval")
    conditions: str | None = Field(None, description="Conditions or stipulations from IRB")
    continuing_review_date: datetime | None = Field(
        None, description="Next continuing review date"
    )


class ProtocolAmendment(BaseModel):
    """A protocol amendment record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique amendment identifier")
    trial_id: str = Field(..., description="Trial identifier")
    amendment_number: int = Field(..., ge=1, description="Sequential amendment number")
    version_from: str = Field(..., description="Protocol version being amended (e.g., '3.0')")
    version_to: str = Field(..., description="New protocol version (e.g., '4.0')")
    amendment_type: AmendmentType = Field(..., description="Type of amendment")
    status: AmendmentStatus = Field(
        default=AmendmentStatus.DRAFT, description="Amendment lifecycle status"
    )
    title: str = Field(..., description="Amendment title")
    rationale: str = Field(..., description="Rationale for the amendment")
    description: str = Field(..., description="Detailed description of changes")
    impacted_sections: list[str] = Field(
        default_factory=list, description="Protocol sections impacted (e.g., 'Section 5.2')"
    )
    impacted_areas: list[AmendmentImpact] = Field(
        default_factory=list, description="Areas of impact"
    )
    submitted_date: datetime | None = Field(None, description="Date submitted for review")
    approved_date: datetime | None = Field(None, description="Date of final approval")
    implementation_date: datetime | None = Field(None, description="Date of implementation")
    affected_sites: list[str] = Field(
        default_factory=list, description="List of affected site IDs"
    )
    irb_submissions: list[IRBSubmission] = Field(
        default_factory=list, description="IRB submissions for this amendment"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")


class AmendmentImpactAssessment(BaseModel):
    """Impact assessment for a protocol amendment."""

    model_config = ConfigDict(from_attributes=True)

    amendment_id: str = Field(..., description="Amendment identifier")
    operational_impact: ImpactSeverity = Field(
        ..., description="Operational impact severity"
    )
    enrollment_impact: ImpactSeverity = Field(
        ..., description="Enrollment impact severity"
    )
    safety_impact: ImpactSeverity = Field(
        ..., description="Safety impact severity"
    )
    cost_impact_estimate: float = Field(
        ..., description="Estimated cost impact in USD"
    )
    timeline_impact_weeks: int = Field(
        ..., ge=0, description="Estimated timeline impact in weeks"
    )
    re_consent_required: bool = Field(
        default=False, description="Whether re-consent of enrolled subjects is required"
    )
    training_required: bool = Field(
        default=False, description="Whether site staff re-training is required"
    )


class AmendmentTracker(BaseModel):
    """Dashboard tracker for amendments across a trial."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    total_amendments: int = Field(ge=0, description="Total amendments for this trial")
    amendments_by_status: dict[str, int] = Field(
        default_factory=dict, description="Amendment counts by status"
    )
    amendments_by_type: dict[str, int] = Field(
        default_factory=dict, description="Amendment counts by type"
    )
    avg_approval_days: float = Field(
        ge=0.0, description="Average days from submission to approval"
    )
    sites_pending_implementation: int = Field(
        ge=0, description="Number of sites with pending implementation"
    )
    re_consent_progress: dict[str, int] = Field(
        default_factory=dict,
        description="Re-consent progress: {total_required, completed, pending}",
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class AmendmentCreate(BaseModel):
    """Request to create a new protocol amendment."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    amendment_number: int = Field(..., ge=1, description="Sequential amendment number")
    version_from: str = Field(..., description="Protocol version being amended")
    version_to: str = Field(..., description="New protocol version")
    amendment_type: AmendmentType = Field(..., description="Type of amendment")
    title: str = Field(..., description="Amendment title")
    rationale: str = Field(..., description="Rationale for the amendment")
    description: str = Field(..., description="Detailed description of changes")
    impacted_sections: list[str] = Field(
        default_factory=list, description="Protocol sections impacted"
    )
    impacted_areas: list[AmendmentImpact] = Field(
        default_factory=list, description="Areas of impact"
    )
    affected_sites: list[str] = Field(
        default_factory=list, description="Affected site IDs"
    )


class AmendmentUpdate(BaseModel):
    """Request to update a protocol amendment."""

    model_config = ConfigDict(from_attributes=True)

    title: str | None = Field(None, description="Amendment title")
    rationale: str | None = Field(None, description="Rationale")
    description: str | None = Field(None, description="Description")
    amendment_type: AmendmentType | None = Field(None, description="Amendment type")
    status: AmendmentStatus | None = Field(None, description="Status")
    impacted_sections: list[str] | None = Field(None, description="Impacted sections")
    impacted_areas: list[AmendmentImpact] | None = Field(None, description="Impact areas")
    affected_sites: list[str] | None = Field(None, description="Affected sites")


class IRBSubmissionCreate(BaseModel):
    """Request to create an IRB submission."""

    model_config = ConfigDict(from_attributes=True)

    irb_name: str = Field(..., description="IRB/ethics committee name")
    site_id: str = Field(..., description="Site identifier")
    submitted_date: datetime = Field(..., description="Date submitted to IRB")


class IRBSubmissionUpdate(BaseModel):
    """Request to update an IRB submission."""

    model_config = ConfigDict(from_attributes=True)

    status: IRBStatus | None = Field(None, description="IRB review status")
    approval_date: datetime | None = Field(None, description="Approval date")
    conditions: str | None = Field(None, description="Conditions from IRB")
    continuing_review_date: datetime | None = Field(None, description="Continuing review date")


class AmendmentSubmit(BaseModel):
    """Request to submit an amendment for review."""

    model_config = ConfigDict(from_attributes=True)

    submitted_date: datetime = Field(..., description="Submission date")


class AmendmentImplement(BaseModel):
    """Request to mark an amendment as implemented."""

    model_config = ConfigDict(from_attributes=True)

    implementation_date: datetime = Field(..., description="Implementation date")


class SiteImplementationStatus(BaseModel):
    """Implementation status for a site."""

    model_config = ConfigDict(from_attributes=True)

    site_id: str = Field(..., description="Site identifier")
    irb_status: IRBStatus = Field(..., description="IRB status for this site")
    implemented: bool = Field(default=False, description="Whether amendment is implemented at site")
    implementation_date: datetime | None = Field(None, description="Site implementation date")
    re_consent_required: bool = Field(default=False, description="Whether re-consent required")
    re_consent_completed: int = Field(default=0, ge=0, description="Number of re-consents completed")
    re_consent_total: int = Field(default=0, ge=0, description="Total re-consents required")


class ReConsentUpdate(BaseModel):
    """Request to update re-consent progress for a site."""

    model_config = ConfigDict(from_attributes=True)

    completed: int = Field(..., ge=0, description="Number of re-consents completed")
    total: int = Field(..., ge=0, description="Total re-consents required")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class AmendmentListResponse(BaseModel):
    """List of protocol amendments."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ProtocolAmendment] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class IRBSubmissionListResponse(BaseModel):
    """List of IRB submissions."""

    model_config = ConfigDict(from_attributes=True)

    items: list[IRBSubmission] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SiteImplementationListResponse(BaseModel):
    """List of site implementation statuses."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SiteImplementationStatus] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class AmendmentMetrics(BaseModel):
    """Aggregated protocol amendment metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_amendments: int = Field(ge=0, description="Total amendments across all trials")
    amendments_by_status: dict[str, int] = Field(
        default_factory=dict, description="Amendment counts by status"
    )
    amendments_by_type: dict[str, int] = Field(
        default_factory=dict, description="Amendment counts by type"
    )
    avg_approval_days: float = Field(
        ge=0.0, description="Average days from submission to approval"
    )
    total_irb_submissions: int = Field(ge=0, description="Total IRB submissions")
    irb_submissions_by_status: dict[str, int] = Field(
        default_factory=dict, description="IRB submission counts by status"
    )
    amendments_requiring_re_consent: int = Field(
        ge=0, description="Amendments requiring re-consent"
    )
    total_sites_pending_implementation: int = Field(
        ge=0, description="Sites with pending implementation across all amendments"
    )
