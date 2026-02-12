"""Pydantic schemas for Reference Safety Information Management (RSI-MGT).

Manages reference safety information: Investigator's Brochure sections,
Development Safety Update Reports, safety reference documents, labeling
safety updates, safety narrative management, and RSI operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DocumentCategory(str, Enum):
    INVESTIGATORS_BROCHURE = "investigators_brochure"
    DSUR = "development_safety_update_report"
    PSUR = "periodic_safety_update_report"
    RSI_TABLE = "reference_safety_information_table"
    SAFETY_LABEL = "safety_label"
    CORE_DATA_SHEET = "core_data_sheet"


class SectionType(str, Enum):
    CLINICAL_SAFETY = "clinical_safety"
    NONCLINICAL_SAFETY = "nonclinical_safety"
    PHARMACOLOGY = "pharmacology"
    PHARMACOKINETICS = "pharmacokinetics"
    TOXICOLOGY = "toxicology"
    SPECIAL_POPULATIONS = "special_populations"
    DRUG_INTERACTIONS = "drug_interactions"
    OVERDOSE = "overdose"


class UpdateType(str, Enum):
    NEW_SIGNAL = "new_signal"
    FREQUENCY_CHANGE = "frequency_change"
    SEVERITY_UPGRADE = "severity_upgrade"
    NEW_RISK = "new_risk"
    REMOVED_RISK = "removed_risk"
    LABELING_CHANGE = "labeling_change"
    REGULATORY_REQUEST = "regulatory_request"


class ReviewStatus(str, Enum):
    DRAFT = "draft"
    MEDICAL_REVIEW = "medical_review"
    SAFETY_REVIEW = "safety_review"
    LEGAL_REVIEW = "legal_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"


class NarrativeType(str, Enum):
    SAE_NARRATIVE = "sae_narrative"
    SUSAR_NARRATIVE = "susar_narrative"
    DEATH_NARRATIVE = "death_narrative"
    PREGNANCY_NARRATIVE = "pregnancy_narrative"
    SPECIAL_INTEREST = "special_interest"


class SafetyDocument(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str | None = None
    product_name: str
    category: DocumentCategory
    title: str
    version: str
    status: ReviewStatus = ReviewStatus.DRAFT
    effective_date: datetime | None = None
    expiry_date: datetime | None = None
    total_pages: int = Field(ge=0, default=0)
    data_lock_date: datetime | None = None
    reporting_period_start: datetime | None = None
    reporting_period_end: datetime | None = None
    author: str
    medical_reviewer: str | None = None
    approved_by: str | None = None
    approved_date: datetime | None = None
    created_at: datetime


class IBSection(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    document_id: str
    section_number: str
    section_type: SectionType
    title: str
    content_summary: str
    word_count: int = Field(ge=0, default=0)
    tables_count: int = Field(ge=0, default=0)
    figures_count: int = Field(ge=0, default=0)
    references_count: int = Field(ge=0, default=0)
    last_updated: datetime
    updated_by: str
    change_description: str | None = None
    created_at: datetime


class SafetyUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    document_id: str
    trial_id: str | None = None
    product_name: str
    update_type: UpdateType
    safety_topic: str
    previous_information: str | None = None
    updated_information: str
    rationale: str
    affected_sections: list[str] = Field(default_factory=list)
    regulatory_notification_required: bool = False
    investigator_notification_required: bool = False
    irb_notification_required: bool = False
    proposed_by: str
    approved_by: str | None = None
    implementation_date: datetime | None = None
    created_at: datetime


class SafetyNarrative(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str
    subject_id: str
    narrative_type: NarrativeType
    case_number: str
    event_term: str
    narrative_text: str
    word_count: int = Field(ge=0, default=0)
    status: ReviewStatus = ReviewStatus.DRAFT
    author: str
    medical_reviewer: str | None = None
    review_date: datetime | None = None
    regulatory_submission_required: bool = False
    submitted_date: datetime | None = None
    created_at: datetime


class RSILineItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    document_id: str
    product_name: str
    adverse_event_term: str
    system_organ_class: str
    frequency_category: str
    incidence_pct: float | None = None
    seriousness: str | None = None
    expectedness: str = "expected"
    source: str
    first_reported_date: datetime | None = None
    last_updated: datetime
    notes: str | None = None
    created_at: datetime


class SafetyDocumentCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_name: str
    category: DocumentCategory
    title: str
    version: str
    author: str
    trial_id: str | None = None


class SafetyDocumentUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: ReviewStatus | None = None
    medical_reviewer: str | None = None
    approved_by: str | None = None
    total_pages: int | None = None
    data_lock_date: datetime | None = None


class IBSectionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    document_id: str
    section_number: str
    section_type: SectionType
    title: str
    content_summary: str
    updated_by: str


class IBSectionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    content_summary: str | None = None
    word_count: int | None = None
    change_description: str | None = None
    updated_by: str | None = None


class SafetyUpdateCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    document_id: str
    product_name: str
    update_type: UpdateType
    safety_topic: str
    updated_information: str
    rationale: str
    proposed_by: str
    trial_id: str | None = None


class SafetyUpdateModify(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    approved_by: str | None = None
    regulatory_notification_required: bool | None = None
    investigator_notification_required: bool | None = None
    implementation_date: datetime | None = None


class SafetyNarrativeCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str
    subject_id: str
    narrative_type: NarrativeType
    case_number: str
    event_term: str
    narrative_text: str
    author: str


class SafetyNarrativeUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: ReviewStatus | None = None
    narrative_text: str | None = None
    medical_reviewer: str | None = None
    regulatory_submission_required: bool | None = None


class RSILineItemCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    document_id: str
    product_name: str
    adverse_event_term: str
    system_organ_class: str
    frequency_category: str
    source: str
    incidence_pct: float | None = None


class RSILineItemUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    frequency_category: str | None = None
    incidence_pct: float | None = None
    expectedness: str | None = None
    notes: str | None = None


class SafetyDocumentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SafetyDocument] = Field(default_factory=list)
    total: int = Field(ge=0)


class IBSectionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[IBSection] = Field(default_factory=list)
    total: int = Field(ge=0)


class SafetyUpdateListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SafetyUpdate] = Field(default_factory=list)
    total: int = Field(ge=0)


class SafetyNarrativeListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[SafetyNarrative] = Field(default_factory=list)
    total: int = Field(ge=0)


class RSILineItemListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[RSILineItem] = Field(default_factory=list)
    total: int = Field(ge=0)


class RSIMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_documents: int = Field(ge=0)
    documents_by_category: dict[str, int] = Field(default_factory=dict)
    documents_by_status: dict[str, int] = Field(default_factory=dict)
    active_documents: int = Field(ge=0)
    total_ib_sections: int = Field(ge=0)
    total_safety_updates: int = Field(ge=0)
    updates_by_type: dict[str, int] = Field(default_factory=dict)
    pending_notifications: int = Field(ge=0)
    total_narratives: int = Field(ge=0)
    narratives_by_type: dict[str, int] = Field(default_factory=dict)
    narratives_pending_review: int = Field(ge=0)
    total_rsi_line_items: int = Field(ge=0)
    expected_events: int = Field(ge=0)
