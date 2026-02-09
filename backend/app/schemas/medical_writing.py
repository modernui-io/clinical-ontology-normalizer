"""Pydantic schemas for Medical Writing & CSR Generation (CLINICAL-11).

Manages medical writing operations: document lifecycle management for CSRs, SAPs,
protocols, and investigator brochures; ICH E3-structured section tracking; review
comment workflow (scientific, medical, statistical, regulatory, quality); TLF shell
programming and validation tracking; and writing metrics/dashboards.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DocumentType(str, Enum):
    """Type of medical writing document."""

    CSR = "csr"
    SAP = "sap"
    PROTOCOL = "protocol"
    IB = "ib"
    ICF = "icf"
    CSR_SYNOPSIS = "csr_synopsis"
    TLF_SHELL = "tlf_shell"
    PERIODIC_SAFETY_REPORT = "periodic_safety_report"
    DEVELOPMENT_SAFETY_UPDATE = "development_safety_update"


class DocumentStatus(str, Enum):
    """Lifecycle status of a medical writing document."""

    DRAFT = "draft"
    INTERNAL_REVIEW = "internal_review"
    MEDICAL_REVIEW = "medical_review"
    QC = "qc"
    FINAL = "final"
    APPROVED = "approved"
    SUBMITTED = "submitted"


class ReviewType(str, Enum):
    """Type of review for a document."""

    SCIENTIFIC = "scientific"
    MEDICAL = "medical"
    STATISTICAL = "statistical"
    REGULATORY = "regulatory"
    QUALITY = "quality"


class TLFType(str, Enum):
    """Type of Table, Listing, or Figure."""

    TABLE = "table"
    LISTING = "listing"
    FIGURE = "figure"


class ICHSection(str, Enum):
    """ICH E3 Clinical Study Report section structure."""

    S1_TITLE = "1_title"
    S2_SYNOPSIS = "2_synopsis"
    S3_TABLE_OF_CONTENTS = "3_table_of_contents"
    S4_LIST_OF_ABBREVIATIONS = "4_list_of_abbreviations"
    S5_ETHICS = "5_ethics"
    S6_INVESTIGATORS = "6_investigators"
    S7_INTRODUCTION = "7_introduction"
    S8_STUDY_OBJECTIVES = "8_study_objectives"
    S9_INVESTIGATIONAL_PLAN = "9_investigational_plan"
    S10_STUDY_PATIENTS = "10_study_patients"
    S11_EFFICACY_EVALUATION = "11_efficacy_evaluation"
    S12_SAFETY_EVALUATION = "12_safety_evaluation"
    S13_DISCUSSION = "13_discussion"
    S14_TABLES_FIGURES_GRAPHS = "14_tables_figures_graphs"
    S15_REFERENCES = "15_references"
    S16_APPENDICES = "16_appendices"


class ProgrammingStatus(str, Enum):
    """Programming/validation status for TLF shells."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    VALIDATED = "validated"
    FINAL = "final"


class SectionStatus(str, Enum):
    """Status of a document section."""

    NOT_STARTED = "not_started"
    DRAFTING = "drafting"
    REVIEW = "review"
    REVISED = "revised"
    FINAL = "final"


class ResolutionStatus(str, Enum):
    """Resolution status of a review comment."""

    OPEN = "open"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFERRED = "deferred"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class MedicalDocument(BaseModel):
    """A medical writing document (CSR, SAP, protocol, IB, etc.)."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique document identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    document_type: DocumentType = Field(..., description="Type of document")
    title: str = Field(..., description="Document title")
    version: str = Field(..., description="Document version (e.g., 1.0, 2.0)")
    status: DocumentStatus = Field(
        default=DocumentStatus.DRAFT, description="Current lifecycle status"
    )
    author: str = Field(..., description="Primary author name")
    reviewer: str | None = Field(None, description="Current reviewer name")
    created_date: datetime = Field(..., description="Document creation date")
    last_modified: datetime = Field(..., description="Last modification date")
    target_date: datetime = Field(..., description="Target completion date")
    word_count: int = Field(default=0, ge=0, description="Current word count")
    sections: list[str] = Field(
        default_factory=list, description="List of section IDs in this document"
    )
    comments_count: int = Field(
        default=0, ge=0, description="Number of review comments"
    )


class DocumentSection(BaseModel):
    """A section within a medical writing document."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique section identifier")
    document_id: str = Field(..., description="Parent document identifier")
    section_number: str = Field(..., description="Section number (e.g., 11.1, 12.2)")
    title: str = Field(..., description="Section title")
    content_summary: str = Field(
        default="", description="Brief summary of section content"
    )
    word_count: int = Field(default=0, ge=0, description="Section word count")
    status: SectionStatus = Field(
        default=SectionStatus.NOT_STARTED, description="Section status"
    )
    assigned_to: str | None = Field(None, description="Assigned writer/reviewer")
    ich_section: ICHSection | None = Field(
        None, description="ICH E3 section mapping (for CSRs)"
    )


class ReviewComment(BaseModel):
    """A review comment on a document or section."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique comment identifier")
    document_id: str = Field(..., description="Associated document identifier")
    section_id: str | None = Field(
        None, description="Associated section identifier (optional)"
    )
    reviewer: str = Field(..., description="Reviewer name")
    review_type: ReviewType = Field(..., description="Type of review")
    comment_text: str = Field(..., description="Comment text")
    resolution: ResolutionStatus = Field(
        default=ResolutionStatus.OPEN, description="Resolution status"
    )
    created_date: datetime = Field(..., description="Comment creation date")
    resolved_date: datetime | None = Field(
        None, description="Date the comment was resolved"
    )


class TLFShell(BaseModel):
    """A Table, Listing, or Figure shell definition."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique TLF identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    tlf_type: TLFType = Field(..., description="Type (table, listing, or figure)")
    number: str = Field(..., description="TLF number (e.g., 14.1.1, 16.2.1)")
    title: str = Field(..., description="TLF title")
    population: str = Field(..., description="Analysis population (e.g., ITT, Safety, PP)")
    dataset: str = Field(..., description="Source dataset (e.g., ADSL, ADAE, ADEFF)")
    programming_status: ProgrammingStatus = Field(
        default=ProgrammingStatus.NOT_STARTED,
        description="Programming/validation status",
    )
    programmer: str | None = Field(None, description="Assigned programmer")
    validator: str | None = Field(None, description="Assigned validator")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class DocumentCreate(BaseModel):
    """Request to create a new medical document."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    document_type: DocumentType = Field(..., description="Document type")
    title: str = Field(..., description="Document title")
    version: str = Field(default="1.0", description="Version")
    author: str = Field(..., description="Primary author")
    target_date: datetime = Field(..., description="Target completion date")


class DocumentUpdate(BaseModel):
    """Request to update a medical document."""

    model_config = ConfigDict(from_attributes=True)

    title: str | None = Field(None, description="Document title")
    version: str | None = Field(None, description="Version")
    status: DocumentStatus | None = Field(None, description="Status")
    author: str | None = Field(None, description="Author")
    reviewer: str | None = Field(None, description="Reviewer")
    target_date: datetime | None = Field(None, description="Target date")
    word_count: int | None = Field(None, ge=0, description="Word count")


class SectionCreate(BaseModel):
    """Request to create a document section."""

    model_config = ConfigDict(from_attributes=True)

    document_id: str = Field(..., description="Parent document ID")
    section_number: str = Field(..., description="Section number")
    title: str = Field(..., description="Section title")
    content_summary: str = Field(default="", description="Content summary")
    assigned_to: str | None = Field(None, description="Assigned writer")
    ich_section: ICHSection | None = Field(None, description="ICH E3 section")


class SectionUpdate(BaseModel):
    """Request to update a document section."""

    model_config = ConfigDict(from_attributes=True)

    title: str | None = Field(None, description="Title")
    content_summary: str | None = Field(None, description="Content summary")
    word_count: int | None = Field(None, ge=0, description="Word count")
    status: SectionStatus | None = Field(None, description="Status")
    assigned_to: str | None = Field(None, description="Assigned writer")


class ReviewCommentCreate(BaseModel):
    """Request to create a review comment."""

    model_config = ConfigDict(from_attributes=True)

    document_id: str = Field(..., description="Document ID")
    section_id: str | None = Field(None, description="Section ID")
    reviewer: str = Field(..., description="Reviewer name")
    review_type: ReviewType = Field(..., description="Review type")
    comment_text: str = Field(..., description="Comment text")


class ReviewCommentUpdate(BaseModel):
    """Request to update a review comment."""

    model_config = ConfigDict(from_attributes=True)

    comment_text: str | None = Field(None, description="Comment text")
    resolution: ResolutionStatus | None = Field(None, description="Resolution")


class TLFShellCreate(BaseModel):
    """Request to create a TLF shell."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial ID")
    tlf_type: TLFType = Field(..., description="TLF type")
    number: str = Field(..., description="TLF number")
    title: str = Field(..., description="TLF title")
    population: str = Field(..., description="Analysis population")
    dataset: str = Field(..., description="Source dataset")
    programmer: str | None = Field(None, description="Programmer")
    validator: str | None = Field(None, description="Validator")


class TLFShellUpdate(BaseModel):
    """Request to update a TLF shell."""

    model_config = ConfigDict(from_attributes=True)

    title: str | None = Field(None, description="Title")
    population: str | None = Field(None, description="Population")
    dataset: str | None = Field(None, description="Dataset")
    programming_status: ProgrammingStatus | None = Field(
        None, description="Programming status"
    )
    programmer: str | None = Field(None, description="Programmer")
    validator: str | None = Field(None, description="Validator")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class DocumentListResponse(BaseModel):
    """List of medical documents."""

    model_config = ConfigDict(from_attributes=True)

    items: list[MedicalDocument] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class SectionListResponse(BaseModel):
    """List of document sections."""

    model_config = ConfigDict(from_attributes=True)

    items: list[DocumentSection] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ReviewCommentListResponse(BaseModel):
    """List of review comments."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ReviewComment] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class TLFShellListResponse(BaseModel):
    """List of TLF shells."""

    model_config = ConfigDict(from_attributes=True)

    items: list[TLFShell] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class WritingMetrics(BaseModel):
    """Aggregated medical writing operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_documents: int = Field(ge=0, description="Total documents")
    documents_by_status: dict[str, int] = Field(
        default_factory=dict, description="Document counts by status"
    )
    documents_by_type: dict[str, int] = Field(
        default_factory=dict, description="Document counts by type"
    )
    avg_review_cycle_days: float = Field(
        ge=0.0, description="Average days from draft to approved"
    )
    overdue_documents: int = Field(
        ge=0, description="Documents past target date and not approved"
    )
    tlf_completion_pct: float = Field(
        ge=0.0, le=100.0, description="Percentage of TLF shells validated or final"
    )
    active_reviews: int = Field(
        ge=0, description="Number of unresolved review comments"
    )
