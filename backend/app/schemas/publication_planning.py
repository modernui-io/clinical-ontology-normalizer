"""Pydantic schemas for Publication Planning & Management (PUB-PLAN).

Manages scientific publication lifecycle: publication planning, manuscript
tracking, congress abstract submissions, author management, journal
submissions, and publication operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class PublicationType(str, Enum):
    PRIMARY_MANUSCRIPT = "primary_manuscript"
    SECONDARY_MANUSCRIPT = "secondary_manuscript"
    CONGRESS_ABSTRACT = "congress_abstract"
    POSTER = "poster"
    ORAL_PRESENTATION = "oral_presentation"
    REVIEW_ARTICLE = "review_article"
    CASE_REPORT = "case_report"
    LETTER_TO_EDITOR = "letter_to_editor"


class PublicationStatus(str, Enum):
    PLANNED = "planned"
    IN_DEVELOPMENT = "in_development"
    INTERNAL_REVIEW = "internal_review"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    REVISION_REQUESTED = "revision_requested"
    ACCEPTED = "accepted"
    PUBLISHED = "published"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class AuthorRole(str, Enum):
    FIRST_AUTHOR = "first_author"
    CORRESPONDING = "corresponding"
    SENIOR_AUTHOR = "senior_author"
    CO_AUTHOR = "co_author"
    STATISTICIAN = "statistician"
    MEDICAL_WRITER = "medical_writer"


class CongressTier(str, Enum):
    TIER_1 = "tier_1_major"
    TIER_2 = "tier_2_regional"
    TIER_3 = "tier_3_specialty"
    INTERNAL = "internal"


class JournalTier(str, Enum):
    HIGH_IMPACT = "high_impact"
    MID_IMPACT = "mid_impact"
    SPECIALTY = "specialty"
    OPEN_ACCESS = "open_access"


class PublicationPlan(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    plan_name: str
    therapeutic_area: str
    target_publications: int = Field(ge=0, default=0)
    completed_publications: int = Field(ge=0, default=0)
    status: str = "active"
    publication_lead: str
    medical_writer: str | None = None
    created_at: datetime


class Manuscript(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    plan_id: str
    trial_id: str
    title: str
    publication_type: PublicationType
    status: PublicationStatus = PublicationStatus.PLANNED
    target_journal: str | None = None
    journal_tier: JournalTier | None = None
    impact_factor: float | None = None
    submission_date: datetime | None = None
    acceptance_date: datetime | None = None
    publication_date: datetime | None = None
    doi: str | None = None
    pmid: str | None = None
    word_count: int = Field(ge=0, default=0)
    figure_count: int = Field(ge=0, default=0)
    table_count: int = Field(ge=0, default=0)
    icmje_compliant: bool = True
    created_at: datetime


class Author(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    manuscript_id: str
    name: str
    institution: str
    role: AuthorRole
    orcid: str | None = None
    email: str | None = None
    order_position: int = Field(ge=1)
    disclosure_statement: str | None = None
    contribution_statement: str | None = None
    approved_final: bool = False


class CongressSubmission(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    plan_id: str
    trial_id: str
    congress_name: str
    congress_date: datetime
    congress_tier: CongressTier
    abstract_title: str
    submission_type: PublicationType
    status: PublicationStatus = PublicationStatus.PLANNED
    submission_deadline: datetime | None = None
    submission_date: datetime | None = None
    acceptance_date: datetime | None = None
    presentation_date: datetime | None = None
    presenter: str | None = None
    abstract_number: str | None = None
    created_at: datetime


class JournalSubmission(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    manuscript_id: str
    journal_name: str
    submission_date: datetime
    decision_date: datetime | None = None
    decision: str | None = None
    reviewer_comments: list[str] = Field(default_factory=list)
    revision_due_date: datetime | None = None
    revision_submitted_date: datetime | None = None
    round_number: int = Field(ge=1, default=1)
    tracking_id: str | None = None


class PublicationPlanCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    plan_name: str
    therapeutic_area: str
    publication_lead: str
    medical_writer: str | None = None


class PublicationPlanUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    target_publications: int | None = None
    completed_publications: int | None = None
    status: str | None = None


class ManuscriptCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    plan_id: str
    trial_id: str
    title: str
    publication_type: PublicationType
    target_journal: str | None = None
    journal_tier: JournalTier | None = None


class ManuscriptUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: PublicationStatus | None = None
    target_journal: str | None = None
    journal_tier: JournalTier | None = None
    impact_factor: float | None = None
    doi: str | None = None
    pmid: str | None = None
    word_count: int | None = None
    figure_count: int | None = None
    table_count: int | None = None


class AuthorCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    manuscript_id: str
    name: str
    institution: str
    role: AuthorRole
    order_position: int = Field(ge=1)
    orcid: str | None = None
    email: str | None = None


class AuthorUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    role: AuthorRole | None = None
    order_position: int | None = None
    disclosure_statement: str | None = None
    contribution_statement: str | None = None
    approved_final: bool | None = None


class CongressSubmissionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    plan_id: str
    trial_id: str
    congress_name: str
    congress_date: datetime
    congress_tier: CongressTier
    abstract_title: str
    submission_type: PublicationType


class CongressSubmissionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: PublicationStatus | None = None
    presenter: str | None = None
    abstract_number: str | None = None
    submission_date: datetime | None = None


class JournalSubmissionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    manuscript_id: str
    journal_name: str


class JournalSubmissionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    decision: str | None = None
    reviewer_comments: list[str] | None = None
    revision_due_date: datetime | None = None


class PublicationPlanListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[PublicationPlan] = Field(default_factory=list)
    total: int = Field(ge=0)


class ManuscriptListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[Manuscript] = Field(default_factory=list)
    total: int = Field(ge=0)


class AuthorListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[Author] = Field(default_factory=list)
    total: int = Field(ge=0)


class CongressSubmissionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[CongressSubmission] = Field(default_factory=list)
    total: int = Field(ge=0)


class JournalSubmissionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[JournalSubmission] = Field(default_factory=list)
    total: int = Field(ge=0)


class PublicationMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_plans: int = Field(ge=0)
    active_plans: int = Field(ge=0)
    total_manuscripts: int = Field(ge=0)
    manuscripts_by_status: dict[str, int] = Field(default_factory=dict)
    manuscripts_by_type: dict[str, int] = Field(default_factory=dict)
    published_count: int = Field(ge=0)
    total_authors: int = Field(ge=0)
    total_congress_submissions: int = Field(ge=0)
    congress_by_tier: dict[str, int] = Field(default_factory=dict)
    accepted_congress_rate_pct: float = Field(ge=0, le=100)
    total_journal_submissions: int = Field(ge=0)
    avg_review_rounds: float = Field(ge=0)
    avg_submission_to_acceptance_days: float = Field(ge=0)
