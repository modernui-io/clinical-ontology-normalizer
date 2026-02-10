"""Pydantic schemas for Clinical Document Management (DOC-MGMT).

Manages clinical trial document lifecycle: document creation, version control,
review and approval workflows, regulatory filing, archival, document access
control, and document metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DocumentType(str, Enum):
    PROTOCOL = "protocol"
    INVESTIGATOR_BROCHURE = "investigator_brochure"
    ICF = "informed_consent_form"
    CSR = "clinical_study_report"
    SAP = "statistical_analysis_plan"
    MONITORING_PLAN = "monitoring_plan"
    DATA_MANAGEMENT_PLAN = "data_management_plan"
    SAFETY_PLAN = "safety_plan"
    REGULATORY_SUBMISSION = "regulatory_submission"
    SITE_TRAINING = "site_training"


class DocumentStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    EFFECTIVE = "effective"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"
    OBSOLETE = "obsolete"


class ReviewDecision(str, Enum):
    APPROVED = "approved"
    APPROVED_WITH_COMMENTS = "approved_with_comments"
    REVISION_REQUIRED = "revision_required"
    REJECTED = "rejected"


class AccessLevel(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class ClinicalDocument(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    document_type: DocumentType
    title: str
    document_number: str
    version: str
    status: DocumentStatus = DocumentStatus.DRAFT
    author: str
    owner: str
    access_level: AccessLevel = AccessLevel.INTERNAL
    effective_date: datetime | None = None
    expiry_date: datetime | None = None
    file_reference: str | None = None
    file_size_bytes: int | None = None
    page_count: int | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DocumentVersion(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    document_id: str
    version: str
    change_summary: str
    changed_by: str
    change_date: datetime
    previous_version_id: str | None = None
    file_reference: str | None = None


class DocumentReview(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    document_id: str
    version_id: str | None = None
    reviewer: str
    reviewer_role: str
    assigned_date: datetime
    due_date: datetime
    completed_date: datetime | None = None
    decision: ReviewDecision | None = None
    comments: str | None = None


class DocumentFiling(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    document_id: str
    filing_location: str
    filed_by: str
    filed_date: datetime
    regulatory_authority: str | None = None
    filing_reference: str | None = None
    confirmed: bool = False


class ClinicalDocumentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    document_type: DocumentType
    title: str
    document_number: str
    version: str = "1.0"
    author: str
    owner: str
    access_level: AccessLevel = AccessLevel.INTERNAL
    tags: list[str] = Field(default_factory=list)


class ClinicalDocumentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    title: str | None = None
    status: DocumentStatus | None = None
    owner: str | None = None
    access_level: AccessLevel | None = None
    effective_date: datetime | None = None
    expiry_date: datetime | None = None
    tags: list[str] | None = None


class DocumentVersionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    document_id: str
    version: str
    change_summary: str
    changed_by: str


class DocumentReviewCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    document_id: str
    version_id: str | None = None
    reviewer: str
    reviewer_role: str
    due_date: datetime


class DocumentReviewUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    decision: ReviewDecision | None = None
    comments: str | None = None


class DocumentFilingCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    document_id: str
    filing_location: str
    filed_by: str
    regulatory_authority: str | None = None
    filing_reference: str | None = None


class ClinicalDocumentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ClinicalDocument] = Field(default_factory=list)
    total: int = Field(ge=0)


class DocumentVersionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DocumentVersion] = Field(default_factory=list)
    total: int = Field(ge=0)


class DocumentReviewListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DocumentReview] = Field(default_factory=list)
    total: int = Field(ge=0)


class DocumentFilingListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[DocumentFiling] = Field(default_factory=list)
    total: int = Field(ge=0)


class DocumentManagementMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_documents: int = Field(ge=0)
    documents_by_type: dict[str, int] = Field(default_factory=dict)
    documents_by_status: dict[str, int] = Field(default_factory=dict)
    total_versions: int = Field(ge=0)
    total_reviews: int = Field(ge=0)
    pending_reviews: int = Field(ge=0)
    overdue_reviews: int = Field(ge=0)
    reviews_by_decision: dict[str, int] = Field(default_factory=dict)
    total_filings: int = Field(ge=0)
    confirmed_filings: int = Field(ge=0)
    avg_review_days: float = Field(ge=0)
