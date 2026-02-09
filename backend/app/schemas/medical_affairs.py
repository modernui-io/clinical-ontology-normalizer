"""Pydantic schemas for Medical Affairs & Publication Planning (CLINICAL-12).

Manages medical affairs operations: publication lifecycle tracking, congress
planning, ICMJE compliance checking, author management, impact factor analysis,
publication plans with milestones, and medical affairs operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PublicationType(str, Enum):
    """Type of scientific publication."""

    PRIMARY_MANUSCRIPT = "primary_manuscript"
    SECONDARY_ANALYSIS = "secondary_analysis"
    POST_HOC = "post_hoc"
    REVIEW_ARTICLE = "review_article"
    CASE_REPORT = "case_report"
    LETTER = "letter"
    ABSTRACT = "abstract"
    POSTER = "poster"
    ORAL_PRESENTATION = "oral_presentation"


class PublicationStatus(str, Enum):
    """Lifecycle status of a publication."""

    PLANNED = "planned"
    DRAFTING = "drafting"
    INTERNAL_REVIEW = "internal_review"
    JOURNAL_SUBMITTED = "journal_submitted"
    UNDER_REVIEW = "under_review"
    REVISION_REQUESTED = "revision_requested"
    ACCEPTED = "accepted"
    PUBLISHED = "published"
    REJECTED = "rejected"


class CongressTier(str, Enum):
    """Tier classification for a medical congress."""

    TIER1 = "tier1"
    TIER2 = "tier2"
    TIER3 = "tier3"


class JournalImpactTier(str, Enum):
    """Impact tier classification for a target journal."""

    HIGH_IMPACT = "high_impact"
    MID_IMPACT = "mid_impact"
    SPECIALIZED = "specialized"


class AuthorRole(str, Enum):
    """Role of an author on a publication."""

    FIRST_AUTHOR = "first_author"
    SENIOR_AUTHOR = "senior_author"
    CORRESPONDING = "corresponding"
    CONTRIBUTING = "contributing"
    MEDICAL_WRITER = "medical_writer"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class AuthorEntry(BaseModel):
    """An author on a publication with ICMJE-related metadata."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Author full name")
    affiliation: str = Field(..., description="Author institutional affiliation")
    role: AuthorRole = Field(..., description="Role on the publication")
    orcid: str | None = Field(None, description="ORCID identifier")
    contributions: list[str] = Field(
        default_factory=list, description="List of ICMJE contributions"
    )
    conflicts_disclosed: bool = Field(
        default=False, description="Whether conflicts of interest have been disclosed"
    )


class Publication(BaseModel):
    """A scientific publication record."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique publication identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    publication_type: PublicationType = Field(..., description="Type of publication")
    title: str = Field(..., description="Publication title")
    status: PublicationStatus = Field(..., description="Current lifecycle status")
    target_journal: str | None = Field(None, description="Target journal name")
    impact_factor: float | None = Field(None, description="Journal impact factor")
    congress_name: str | None = Field(None, description="Congress name for abstracts/posters")
    congress_date: datetime | None = Field(None, description="Congress date")
    submission_date: datetime | None = Field(None, description="Date submitted to journal")
    acceptance_date: datetime | None = Field(None, description="Date accepted by journal")
    publication_date: datetime | None = Field(None, description="Date published")
    doi: str | None = Field(None, description="Digital Object Identifier")
    authors: list[AuthorEntry] = Field(
        default_factory=list, description="List of authors"
    )
    icmje_compliant: bool = Field(
        default=False, description="Whether the publication meets ICMJE criteria"
    )


class CongressPlan(BaseModel):
    """A congress participation plan."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique congress plan identifier")
    congress_name: str = Field(..., description="Congress name")
    tier: CongressTier = Field(..., description="Congress tier classification")
    date: datetime = Field(..., description="Congress date")
    location: str = Field(..., description="Congress location")
    abstracts_submitted: int = Field(default=0, ge=0, description="Number of abstracts submitted")
    abstracts_accepted: int = Field(default=0, ge=0, description="Number of abstracts accepted")
    posters: int = Field(default=0, ge=0, description="Number of poster presentations")
    orals: int = Field(default=0, ge=0, description="Number of oral presentations")
    booth_reserved: bool = Field(default=False, description="Whether a booth is reserved")
    budget: float = Field(default=0.0, ge=0.0, description="Congress budget in USD")


class PublicationMilestone(BaseModel):
    """A milestone within a publication plan."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Milestone name")
    target_date: datetime = Field(..., description="Target completion date")
    completed: bool = Field(default=False, description="Whether the milestone is completed")


class PublicationPlan(BaseModel):
    """A publication plan for a trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique publication plan identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    planned_publications: list[str] = Field(
        default_factory=list, description="List of planned publication IDs"
    )
    timeline: str = Field(..., description="Overall publication timeline description")
    milestones: list[PublicationMilestone] = Field(
        default_factory=list, description="Key milestones in the publication plan"
    )


class MedicalAffairsMetrics(BaseModel):
    """Aggregated medical affairs operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_publications: int = Field(ge=0, description="Total publications")
    publications_by_status: dict[str, int] = Field(
        default_factory=dict, description="Publication counts by status"
    )
    publications_by_type: dict[str, int] = Field(
        default_factory=dict, description="Publication counts by type"
    )
    avg_submission_to_acceptance_days: float | None = Field(
        None, description="Average days from submission to acceptance"
    )
    congress_roi: dict[str, float] = Field(
        default_factory=dict, description="Congress ROI: acceptance rate per congress"
    )
    icmje_compliance_rate: float = Field(
        ge=0.0, le=100.0, description="Percentage of publications meeting ICMJE criteria"
    )
    impact_factor_weighted_count: float = Field(
        ge=0.0, description="Sum of impact factors for published/accepted publications"
    )


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class PublicationCreate(BaseModel):
    """Request to create a new publication."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    publication_type: PublicationType = Field(..., description="Publication type")
    title: str = Field(..., description="Publication title")
    target_journal: str | None = Field(None, description="Target journal")
    impact_factor: float | None = Field(None, description="Journal impact factor")
    congress_name: str | None = Field(None, description="Congress name")
    congress_date: datetime | None = Field(None, description="Congress date")
    authors: list[AuthorEntry] = Field(default_factory=list, description="Authors")


class PublicationUpdate(BaseModel):
    """Request to update a publication."""

    model_config = ConfigDict(from_attributes=True)

    title: str | None = Field(None, description="Title")
    status: PublicationStatus | None = Field(None, description="Status")
    target_journal: str | None = Field(None, description="Target journal")
    impact_factor: float | None = Field(None, description="Impact factor")
    congress_name: str | None = Field(None, description="Congress name")
    congress_date: datetime | None = Field(None, description="Congress date")
    submission_date: datetime | None = Field(None, description="Submission date")
    acceptance_date: datetime | None = Field(None, description="Acceptance date")
    publication_date: datetime | None = Field(None, description="Publication date")
    doi: str | None = Field(None, description="DOI")
    authors: list[AuthorEntry] | None = Field(None, description="Authors")


class CongressPlanCreate(BaseModel):
    """Request to create a congress plan."""

    model_config = ConfigDict(from_attributes=True)

    congress_name: str = Field(..., description="Congress name")
    tier: CongressTier = Field(..., description="Congress tier")
    date: datetime = Field(..., description="Congress date")
    location: str = Field(..., description="Location")
    budget: float = Field(default=0.0, ge=0.0, description="Budget")
    booth_reserved: bool = Field(default=False, description="Booth reserved")


class CongressPlanUpdate(BaseModel):
    """Request to update a congress plan."""

    model_config = ConfigDict(from_attributes=True)

    congress_name: str | None = Field(None, description="Congress name")
    tier: CongressTier | None = Field(None, description="Congress tier")
    date: datetime | None = Field(None, description="Congress date")
    location: str | None = Field(None, description="Location")
    abstracts_submitted: int | None = Field(None, ge=0, description="Abstracts submitted")
    abstracts_accepted: int | None = Field(None, ge=0, description="Abstracts accepted")
    posters: int | None = Field(None, ge=0, description="Posters")
    orals: int | None = Field(None, ge=0, description="Orals")
    booth_reserved: bool | None = Field(None, description="Booth reserved")
    budget: float | None = Field(None, ge=0.0, description="Budget")


class PublicationPlanCreate(BaseModel):
    """Request to create a publication plan."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    planned_publications: list[str] = Field(default_factory=list, description="Planned publication IDs")
    timeline: str = Field(..., description="Timeline description")
    milestones: list[PublicationMilestone] = Field(default_factory=list, description="Milestones")


class PublicationPlanUpdate(BaseModel):
    """Request to update a publication plan."""

    model_config = ConfigDict(from_attributes=True)

    planned_publications: list[str] | None = Field(None, description="Planned publication IDs")
    timeline: str | None = Field(None, description="Timeline")
    milestones: list[PublicationMilestone] | None = Field(None, description="Milestones")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class PublicationListResponse(BaseModel):
    """List of publications."""

    model_config = ConfigDict(from_attributes=True)

    items: list[Publication] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class CongressPlanListResponse(BaseModel):
    """List of congress plans."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CongressPlan] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class PublicationPlanListResponse(BaseModel):
    """List of publication plans."""

    model_config = ConfigDict(from_attributes=True)

    items: list[PublicationPlan] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# ICMJE compliance check result
# ---------------------------------------------------------------------------


class ICMJEComplianceResult(BaseModel):
    """Result of an ICMJE compliance check for a publication."""

    model_config = ConfigDict(from_attributes=True)

    publication_id: str = Field(..., description="Publication identifier")
    compliant: bool = Field(..., description="Whether the publication is ICMJE compliant")
    issues: list[str] = Field(default_factory=list, description="List of compliance issues")
