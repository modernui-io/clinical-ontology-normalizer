"""Pydantic schemas for Product Licensure & Market Authorization.

Manages regulatory application lifecycles (IND/NDA/BLA/MAA), country-by-country
approval status tracking, product label management, post-approval change control,
and market access timeline monitoring across global regulatory authorities.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ApplicationType(str, Enum):
    """Type of regulatory application."""

    IND = "ind"
    NDA = "nda"
    BLA = "bla"
    MAA = "maa"
    JNDA = "jnda"
    SUPPLEMENTAL_NDA = "supplemental_nda"
    ABBREVIATED_NDA = "abbreviated_nda"


class ApplicationStatus(str, Enum):
    """Lifecycle status of a regulatory application."""

    PRE_SUBMISSION = "pre_submission"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    COMPLETE_RESPONSE = "complete_response"
    APPROVED = "approved"
    REFUSED = "refused"
    WITHDRAWN = "withdrawn"


class SubmissionType(str, Enum):
    """Type of regulatory submission."""

    ORIGINAL = "original"
    AMENDMENT = "amendment"
    SUPPLEMENT = "supplement"
    ANNUAL_REPORT = "annual_report"


class LabelStatus(str, Enum):
    """Lifecycle status of a product label."""

    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    EFFECTIVE = "effective"
    SUPERSEDED = "superseded"


class MarketStatus(str, Enum):
    """Market authorization status for a country."""

    NOT_FILED = "not_filed"
    FILED = "filed"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    LAUNCHED = "launched"
    WITHDRAWN = "withdrawn"


class ChangeType(str, Enum):
    """Type of post-approval change."""

    MANUFACTURING = "manufacturing"
    LABELING = "labeling"
    FORMULATION = "formulation"
    INDICATION = "indication"
    SAFETY_UPDATE = "safety_update"
    PACKAGING = "packaging"
    SUPPLIER = "supplier"


class MilestoneStatus(str, Enum):
    """Status of a market access timeline milestone."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELAYED = "delayed"
    AT_RISK = "at_risk"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class RegulatoryApplication(BaseModel):
    """A regulatory application (IND, NDA, BLA, MAA, etc.) submitted to an authority."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique application identifier")
    product_name: str = Field(..., description="Name of the pharmaceutical product")
    application_type: ApplicationType = Field(..., description="Type of regulatory application")
    application_number: str = Field(..., description="Official application number assigned by authority")
    regulatory_authority: str = Field(..., description="Regulatory authority (e.g., FDA, EMA, PMDA)")
    country: str = Field(..., description="Country of submission (ISO 3166-1 alpha-2)")
    submission_date: datetime | None = Field(None, description="Date of submission to authority")
    acceptance_date: datetime | None = Field(None, description="Date application was accepted for review")
    review_type: str = Field(default="standard", description="Review type (standard, priority, accelerated, breakthrough)")
    pdufa_date: datetime | None = Field(None, description="Prescription Drug User Fee Act target action date")
    status: ApplicationStatus = Field(
        default=ApplicationStatus.PRE_SUBMISSION, description="Current application status"
    )
    assigned_reviewer: str | None = Field(None, description="Assigned regulatory reviewer name")
    division: str | None = Field(None, description="Reviewing division within the authority")
    therapeutic_area: str = Field(..., description="Therapeutic area (e.g., Ophthalmology, Dermatology)")
    indication: str = Field(..., description="Target indication for the application")
    sponsor_contact: str = Field(..., description="Primary sponsor contact for this application")
    submission_type: SubmissionType = Field(
        default=SubmissionType.ORIGINAL, description="Type of submission"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last update timestamp")


class CountryAuthorization(BaseModel):
    """Country-specific market authorization record linked to a regulatory application."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique authorization identifier")
    application_id: str = Field(..., description="Parent regulatory application ID")
    country: str = Field(..., description="Country code (ISO 3166-1 alpha-2)")
    authority_name: str = Field(..., description="Local regulatory authority name")
    local_application_number: str | None = Field(
        None, description="Local application/registration number"
    )
    filing_date: datetime | None = Field(None, description="Date of filing in this country")
    approval_date: datetime | None = Field(None, description="Date of marketing authorization approval")
    market_status: MarketStatus = Field(
        default=MarketStatus.NOT_FILED, description="Current market authorization status"
    )
    conditions: str | None = Field(None, description="Conditions of approval or restrictions")
    label_approved: bool = Field(default=False, description="Whether the local label has been approved")
    launch_date: datetime | None = Field(None, description="Actual or planned product launch date")
    patent_expiry: datetime | None = Field(None, description="Patent expiry date in this country")
    created_at: datetime = Field(..., description="Record creation timestamp")


class ProductLabel(BaseModel):
    """A product label version for a specific country and language."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique label identifier")
    application_id: str = Field(..., description="Parent regulatory application ID")
    product_name: str = Field(..., description="Product name on the label")
    version: str = Field(..., description="Label version (e.g., 1.0, 2.1)")
    country: str = Field(..., description="Country code (ISO 3166-1 alpha-2)")
    language: str = Field(default="en", description="Label language (ISO 639-1)")
    status: LabelStatus = Field(default=LabelStatus.DRAFT, description="Label lifecycle status")
    effective_date: datetime | None = Field(None, description="Date label becomes effective")
    sections_changed: list[str] = Field(
        default_factory=list, description="List of label sections that were modified"
    )
    safety_updates: list[str] = Field(
        default_factory=list, description="Safety-related updates in this label version"
    )
    boxed_warning: str | None = Field(None, description="Boxed warning text, if any")
    contraindications: list[str] = Field(
        default_factory=list, description="List of contraindications"
    )
    approved_by: str | None = Field(None, description="Name of person who approved the label")
    approved_date: datetime | None = Field(None, description="Date of label approval")
    created_at: datetime = Field(..., description="Record creation timestamp")


class PostApprovalChange(BaseModel):
    """A post-approval change (supplement, variation) filed with regulators."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique change identifier")
    application_id: str = Field(..., description="Parent regulatory application ID")
    change_type: ChangeType = Field(..., description="Type of post-approval change")
    description: str = Field(..., description="Detailed description of the change")
    submission_date: datetime | None = Field(None, description="Date change was submitted")
    approval_date: datetime | None = Field(None, description="Date change was approved")
    status: ApplicationStatus = Field(
        default=ApplicationStatus.PRE_SUBMISSION, description="Current change status"
    )
    impact_assessment: str | None = Field(
        None, description="Assessment of impact on product quality, safety, efficacy"
    )
    affected_countries: list[str] = Field(
        default_factory=list, description="Countries affected by this change"
    )
    regulatory_reference: str | None = Field(
        None, description="Regulatory guidance or reference number"
    )
    created_at: datetime = Field(..., description="Record creation timestamp")


class MarketAccessTimeline(BaseModel):
    """A milestone in the market access timeline for a product in a given country."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique timeline milestone identifier")
    application_id: str = Field(..., description="Parent regulatory application ID")
    country: str = Field(..., description="Country code (ISO 3166-1 alpha-2)")
    milestone_name: str = Field(..., description="Name of the milestone")
    planned_date: datetime = Field(..., description="Planned date for the milestone")
    actual_date: datetime | None = Field(None, description="Actual completion date")
    status: MilestoneStatus = Field(
        default=MilestoneStatus.NOT_STARTED, description="Milestone status"
    )
    dependencies: list[str] = Field(
        default_factory=list, description="IDs of prerequisite milestones"
    )
    notes: str | None = Field(None, description="Additional notes or context")
    created_at: datetime = Field(..., description="Record creation timestamp")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class RegulatoryApplicationCreate(BaseModel):
    """Request to create a new regulatory application."""

    model_config = ConfigDict(from_attributes=True)

    product_name: str = Field(..., description="Product name")
    application_type: ApplicationType = Field(..., description="Application type")
    application_number: str = Field(..., description="Application number")
    regulatory_authority: str = Field(..., description="Regulatory authority")
    country: str = Field(..., description="Country code")
    review_type: str = Field(default="standard", description="Review type")
    therapeutic_area: str = Field(..., description="Therapeutic area")
    indication: str = Field(..., description="Target indication")
    sponsor_contact: str = Field(..., description="Sponsor contact")
    submission_type: SubmissionType = Field(
        default=SubmissionType.ORIGINAL, description="Submission type"
    )


class RegulatoryApplicationUpdate(BaseModel):
    """Request to update a regulatory application."""

    model_config = ConfigDict(from_attributes=True)

    product_name: str | None = Field(None, description="Product name")
    application_number: str | None = Field(None, description="Application number")
    review_type: str | None = Field(None, description="Review type")
    pdufa_date: datetime | None = Field(None, description="PDUFA target date")
    status: ApplicationStatus | None = Field(None, description="Application status")
    assigned_reviewer: str | None = Field(None, description="Assigned reviewer")
    division: str | None = Field(None, description="Reviewing division")
    indication: str | None = Field(None, description="Target indication")
    sponsor_contact: str | None = Field(None, description="Sponsor contact")


class ApplicationSubmit(BaseModel):
    """Request to formally submit an application."""

    model_config = ConfigDict(from_attributes=True)

    submission_date: datetime = Field(..., description="Date of submission")
    notes: str | None = Field(None, description="Submission notes")


class ApplicationApproval(BaseModel):
    """Request to record an application approval."""

    model_config = ConfigDict(from_attributes=True)

    approval_date: datetime = Field(..., description="Date of approval")
    conditions: str | None = Field(None, description="Conditions of approval")
    assigned_reviewer: str | None = Field(None, description="Approving reviewer")


class CountryAuthorizationCreate(BaseModel):
    """Request to create a country authorization record."""

    model_config = ConfigDict(from_attributes=True)

    application_id: str = Field(..., description="Parent application ID")
    country: str = Field(..., description="Country code")
    authority_name: str = Field(..., description="Local authority name")
    local_application_number: str | None = Field(None, description="Local application number")
    patent_expiry: datetime | None = Field(None, description="Patent expiry date")


class CountryAuthorizationUpdate(BaseModel):
    """Request to update a country authorization."""

    model_config = ConfigDict(from_attributes=True)

    local_application_number: str | None = Field(None, description="Local application number")
    filing_date: datetime | None = Field(None, description="Filing date")
    approval_date: datetime | None = Field(None, description="Approval date")
    market_status: MarketStatus | None = Field(None, description="Market status")
    conditions: str | None = Field(None, description="Conditions")
    label_approved: bool | None = Field(None, description="Label approved")
    launch_date: datetime | None = Field(None, description="Launch date")
    patent_expiry: datetime | None = Field(None, description="Patent expiry")


class ProductLabelCreate(BaseModel):
    """Request to create a new product label."""

    model_config = ConfigDict(from_attributes=True)

    application_id: str = Field(..., description="Parent application ID")
    product_name: str = Field(..., description="Product name on label")
    version: str = Field(..., description="Label version")
    country: str = Field(..., description="Country code")
    language: str = Field(default="en", description="Language code")
    sections_changed: list[str] = Field(default_factory=list, description="Sections changed")
    safety_updates: list[str] = Field(default_factory=list, description="Safety updates")
    boxed_warning: str | None = Field(None, description="Boxed warning")
    contraindications: list[str] = Field(default_factory=list, description="Contraindications")


class ProductLabelUpdate(BaseModel):
    """Request to update a product label."""

    model_config = ConfigDict(from_attributes=True)

    version: str | None = Field(None, description="Label version")
    status: LabelStatus | None = Field(None, description="Label status")
    effective_date: datetime | None = Field(None, description="Effective date")
    sections_changed: list[str] | None = Field(None, description="Sections changed")
    safety_updates: list[str] | None = Field(None, description="Safety updates")
    boxed_warning: str | None = Field(None, description="Boxed warning")
    contraindications: list[str] | None = Field(None, description="Contraindications")
    approved_by: str | None = Field(None, description="Approved by")
    approved_date: datetime | None = Field(None, description="Approved date")


class PostApprovalChangeCreate(BaseModel):
    """Request to file a post-approval change."""

    model_config = ConfigDict(from_attributes=True)

    application_id: str = Field(..., description="Parent application ID")
    change_type: ChangeType = Field(..., description="Type of change")
    description: str = Field(..., description="Change description")
    impact_assessment: str | None = Field(None, description="Impact assessment")
    affected_countries: list[str] = Field(default_factory=list, description="Affected countries")
    regulatory_reference: str | None = Field(None, description="Regulatory reference")


class PostApprovalChangeUpdate(BaseModel):
    """Request to update a post-approval change."""

    model_config = ConfigDict(from_attributes=True)

    description: str | None = Field(None, description="Description")
    submission_date: datetime | None = Field(None, description="Submission date")
    approval_date: datetime | None = Field(None, description="Approval date")
    status: ApplicationStatus | None = Field(None, description="Status")
    impact_assessment: str | None = Field(None, description="Impact assessment")
    affected_countries: list[str] | None = Field(None, description="Affected countries")
    regulatory_reference: str | None = Field(None, description="Regulatory reference")


class MarketAccessTimelineCreate(BaseModel):
    """Request to create a market access timeline milestone."""

    model_config = ConfigDict(from_attributes=True)

    application_id: str = Field(..., description="Parent application ID")
    country: str = Field(..., description="Country code")
    milestone_name: str = Field(..., description="Milestone name")
    planned_date: datetime = Field(..., description="Planned date")
    dependencies: list[str] = Field(default_factory=list, description="Dependency milestone IDs")
    notes: str | None = Field(None, description="Notes")


class MarketAccessTimelineUpdate(BaseModel):
    """Request to update a timeline milestone."""

    model_config = ConfigDict(from_attributes=True)

    milestone_name: str | None = Field(None, description="Milestone name")
    planned_date: datetime | None = Field(None, description="Planned date")
    actual_date: datetime | None = Field(None, description="Actual completion date")
    status: MilestoneStatus | None = Field(None, description="Milestone status")
    dependencies: list[str] | None = Field(None, description="Dependency IDs")
    notes: str | None = Field(None, description="Notes")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class RegulatoryApplicationListResponse(BaseModel):
    """List of regulatory applications."""

    model_config = ConfigDict(from_attributes=True)

    items: list[RegulatoryApplication] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class CountryAuthorizationListResponse(BaseModel):
    """List of country authorizations."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CountryAuthorization] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ProductLabelListResponse(BaseModel):
    """List of product labels."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ProductLabel] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class PostApprovalChangeListResponse(BaseModel):
    """List of post-approval changes."""

    model_config = ConfigDict(from_attributes=True)

    items: list[PostApprovalChange] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class MarketAccessTimelineListResponse(BaseModel):
    """List of market access timeline milestones."""

    model_config = ConfigDict(from_attributes=True)

    items: list[MarketAccessTimeline] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Product status by country (aggregate view)
# ---------------------------------------------------------------------------


class ProductCountryStatus(BaseModel):
    """Aggregated product status for a specific country."""

    model_config = ConfigDict(from_attributes=True)

    country: str = Field(..., description="Country code")
    authority_name: str = Field(..., description="Regulatory authority name")
    application_status: ApplicationStatus = Field(..., description="Application status")
    market_status: MarketStatus = Field(..., description="Market authorization status")
    label_approved: bool = Field(default=False, description="Whether label is approved")
    approval_date: datetime | None = Field(None, description="Approval date")
    launch_date: datetime | None = Field(None, description="Launch date")
    pending_changes: int = Field(default=0, ge=0, description="Number of pending post-approval changes")
    next_milestone: str | None = Field(None, description="Next upcoming milestone name")
    next_milestone_date: datetime | None = Field(None, description="Date of next milestone")


class ProductCountryStatusListResponse(BaseModel):
    """List of product status by country."""

    model_config = ConfigDict(from_attributes=True)

    product_name: str = Field(..., description="Product name")
    application_id: str = Field(..., description="Application ID")
    countries: list[ProductCountryStatus] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total countries")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class LicensureMetrics(BaseModel):
    """Aggregated Product Licensure & Market Authorization metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_applications: int = Field(ge=0, description="Total regulatory applications")
    applications_by_type: dict[str, int] = Field(
        default_factory=dict, description="Application counts by type"
    )
    applications_by_status: dict[str, int] = Field(
        default_factory=dict, description="Application counts by status"
    )
    total_country_authorizations: int = Field(
        ge=0, description="Total country-level authorizations"
    )
    countries_approved: int = Field(ge=0, description="Number of countries with approved status")
    countries_launched: int = Field(ge=0, description="Number of countries with launched products")
    total_labels: int = Field(ge=0, description="Total product labels")
    labels_effective: int = Field(ge=0, description="Number of effective labels")
    total_post_approval_changes: int = Field(ge=0, description="Total post-approval changes")
    pending_changes: int = Field(ge=0, description="Changes awaiting approval")
    total_milestones: int = Field(ge=0, description="Total timeline milestones")
    milestones_completed: int = Field(ge=0, description="Completed milestones")
    milestones_delayed: int = Field(ge=0, description="Delayed milestones")
    milestones_at_risk: int = Field(ge=0, description="At-risk milestones")
    avg_approval_time_days: float | None = Field(
        None, description="Average days from submission to approval"
    )
