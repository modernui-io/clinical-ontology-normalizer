"""Pydantic schemas for Medical Information Services (MED-INFO).

Manages medical information operations: inquiry management, standard response
documents, product FAQ libraries, field medical insights, scientific
communication tracking, and medical information operational metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class InquirySource(str, Enum):
    HCP = "healthcare_professional"
    PATIENT = "patient"
    CAREGIVER = "caregiver"
    PAYER = "payer"
    REGULATORY = "regulatory"
    INTERNAL = "internal"
    PHARMACIST = "pharmacist"


class InquiryCategory(str, Enum):
    EFFICACY = "efficacy"
    SAFETY = "safety"
    DOSING = "dosing"
    DRUG_INTERACTIONS = "drug_interactions"
    STORAGE = "storage_handling"
    AVAILABILITY = "availability"
    OFF_LABEL = "off_label"
    CLINICAL_TRIAL = "clinical_trial"
    REIMBURSEMENT = "reimbursement"


class InquiryStatus(str, Enum):
    RECEIVED = "received"
    IN_REVIEW = "in_review"
    RESPONSE_DRAFTED = "response_drafted"
    QC_REVIEW = "qc_review"
    APPROVED = "approved"
    SENT = "sent"
    CLOSED = "closed"


class ResponseType(str, Enum):
    STANDARD = "standard"
    CUSTOM = "custom"
    LITERATURE_SEARCH = "literature_search"
    EXPERT_CONSULT = "expert_consult"


class DocumentType(str, Enum):
    STANDARD_RESPONSE = "standard_response"
    FAQ = "faq"
    PRODUCT_MONOGRAPH = "product_monograph"
    SCIENTIFIC_RESPONSE = "scientific_response"
    FIELD_ALERT = "field_alert"


class MedicalInquiry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    trial_id: str | None = None
    product_name: str
    inquiry_source: InquirySource
    category: InquiryCategory
    status: InquiryStatus = InquiryStatus.RECEIVED
    question_text: str
    response_text: str | None = None
    response_type: ResponseType | None = None
    requester_name: str | None = None
    requester_institution: str | None = None
    requester_country: str | None = None
    assigned_to: str | None = None
    received_date: datetime
    response_date: datetime | None = None
    turnaround_days: int | None = None
    follow_up_required: bool = False
    adverse_event_reported: bool = False
    created_at: datetime


class StandardResponseDoc(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    product_name: str
    document_type: DocumentType
    title: str
    version: str
    content_summary: str
    category: InquiryCategory
    effective_date: datetime
    expiry_date: datetime | None = None
    active: bool = True
    usage_count: int = Field(ge=0, default=0)
    author: str
    reviewer: str | None = None
    approved_by: str | None = None
    approved_date: datetime | None = None
    created_at: datetime


class ProductFAQ(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    product_name: str
    category: InquiryCategory
    question: str
    answer: str
    version: str = "1.0"
    active: bool = True
    view_count: int = Field(ge=0, default=0)
    helpful_count: int = Field(ge=0, default=0)
    last_updated: datetime
    author: str


class FieldMedicalInsight(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    product_name: str
    trial_id: str | None = None
    insight_type: str
    description: str
    therapeutic_area: str
    region: str | None = None
    source: str
    impact_assessment: str | None = None
    action_required: bool = False
    action_taken: str | None = None
    reported_by: str
    reported_date: datetime
    reviewed_by: str | None = None
    created_at: datetime


class ScientificCommunication(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    product_name: str
    communication_type: str
    title: str
    audience: str
    channel: str
    content_summary: str
    status: str = "draft"
    scheduled_date: datetime | None = None
    sent_date: datetime | None = None
    recipients_count: int = Field(ge=0, default=0)
    open_rate_pct: float | None = None
    author: str
    approved_by: str | None = None
    created_at: datetime


class MedicalInquiryCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    trial_id: str | None = None
    product_name: str
    inquiry_source: InquirySource
    category: InquiryCategory
    question_text: str
    requester_name: str | None = None
    requester_institution: str | None = None
    requester_country: str | None = None


class MedicalInquiryUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: InquiryStatus | None = None
    response_text: str | None = None
    response_type: ResponseType | None = None
    assigned_to: str | None = None
    follow_up_required: bool | None = None
    adverse_event_reported: bool | None = None


class StandardResponseDocCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_name: str
    document_type: DocumentType
    title: str
    version: str
    content_summary: str
    category: InquiryCategory
    effective_date: datetime
    author: str


class StandardResponseDocUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    active: bool | None = None
    reviewer: str | None = None
    approved_by: str | None = None
    expiry_date: datetime | None = None


class ProductFAQCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_name: str
    category: InquiryCategory
    question: str
    answer: str
    author: str


class ProductFAQUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    answer: str | None = None
    active: bool | None = None
    version: str | None = None


class FieldMedicalInsightCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_name: str
    trial_id: str | None = None
    insight_type: str
    description: str
    therapeutic_area: str
    source: str
    reported_by: str
    region: str | None = None


class FieldMedicalInsightUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    impact_assessment: str | None = None
    action_required: bool | None = None
    action_taken: str | None = None
    reviewed_by: str | None = None


class ScientificCommunicationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_name: str
    communication_type: str
    title: str
    audience: str
    channel: str
    content_summary: str
    author: str


class ScientificCommunicationUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    status: str | None = None
    approved_by: str | None = None
    recipients_count: int | None = None
    open_rate_pct: float | None = None


class MedicalInquiryListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[MedicalInquiry] = Field(default_factory=list)
    total: int = Field(ge=0)


class StandardResponseDocListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[StandardResponseDoc] = Field(default_factory=list)
    total: int = Field(ge=0)


class ProductFAQListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ProductFAQ] = Field(default_factory=list)
    total: int = Field(ge=0)


class FieldMedicalInsightListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[FieldMedicalInsight] = Field(default_factory=list)
    total: int = Field(ge=0)


class ScientificCommunicationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    items: list[ScientificCommunication] = Field(default_factory=list)
    total: int = Field(ge=0)


class MedicalInformationMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_inquiries: int = Field(ge=0)
    inquiries_by_source: dict[str, int] = Field(default_factory=dict)
    inquiries_by_category: dict[str, int] = Field(default_factory=dict)
    inquiries_by_status: dict[str, int] = Field(default_factory=dict)
    avg_turnaround_days: float = Field(ge=0)
    total_standard_responses: int = Field(ge=0)
    active_standard_responses: int = Field(ge=0)
    total_faqs: int = Field(ge=0)
    active_faqs: int = Field(ge=0)
    total_insights: int = Field(ge=0)
    actionable_insights: int = Field(ge=0)
    total_communications: int = Field(ge=0)
    communications_sent: int = Field(ge=0)
