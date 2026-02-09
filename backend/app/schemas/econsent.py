"""Pydantic schemas for Electronic Informed Consent (eConsent) Management (CLINICAL-18).

Manages electronic informed consent operations: consent document definitions with
versioned elements, patient consent lifecycle (not_started through signed/withdrawn),
21 CFR Part 11 compliant audit trails, quiz-based comprehension verification,
withdrawal management with data retention preferences, re-consent tracking for
protocol amendments, and multi-language support.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ConsentType(str, Enum):
    """Type of informed consent document."""

    MAIN_STUDY = "main_study"
    SUB_STUDY = "sub_study"
    BIOBANKING = "biobanking"
    GENETIC_TESTING = "genetic_testing"
    FUTURE_RESEARCH = "future_research"
    PEDIATRIC_ASSENT = "pediatric_assent"
    LAR_CONSENT = "lar_consent"


class ConsentStatus(str, Enum):
    """Lifecycle status of a patient consent."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SIGNED = "signed"
    RE_CONSENTED = "re_consented"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"


class ConsentElementType(str, Enum):
    """Type of element within a consent document."""

    TEXT = "text"
    VIDEO = "video"
    QUIZ = "quiz"
    SIGNATURE = "signature"
    CHECKBOX = "checkbox"
    ACKNOWLEDGMENT = "acknowledgment"


class DocumentLanguage(str, Enum):
    """Supported languages for consent documents."""

    EN = "en"
    ES = "es"
    FR = "fr"
    DE = "de"
    JA = "ja"
    ZH = "zh"
    KO = "ko"
    PT = "pt"


class DataRetentionPreference(str, Enum):
    """Data retention preference upon consent withdrawal."""

    DELETE_ALL = "delete_all"
    RETAIN_ANONYMIZED = "retain_anonymized"
    RETAIN_IDENTIFIED = "retain_identified"


class ConsentAuditAction(str, Enum):
    """Action types for the consent audit trail."""

    VIEWED = "viewed"
    SIGNED = "signed"
    WITHDRAWN = "withdrawn"
    RE_CONSENTED = "re_consented"
    VERSION_UPDATED = "version_updated"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class ConsentElement(BaseModel):
    """An element within a consent document (text, video, quiz, signature, etc.)."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique element identifier")
    element_type: ConsentElementType = Field(..., description="Type of consent element")
    page_number: int = Field(..., ge=1, description="Page number where element appears")
    content_summary: str = Field(..., description="Summary of the element content")
    required: bool = Field(default=True, description="Whether this element must be completed")
    quiz_question: str | None = Field(None, description="Quiz question text (for quiz elements)")
    quiz_correct_answer: str | None = Field(None, description="Correct answer for quiz elements")
    quiz_options: list[str] | None = Field(None, description="Multiple choice options for quiz")


class ConsentDocument(BaseModel):
    """A versioned consent document definition."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique document identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    version: str = Field(..., description="Document version (e.g., 1.0, 2.1)")
    title: str = Field(..., description="Document title")
    consent_type: ConsentType = Field(..., description="Type of consent")
    effective_date: datetime = Field(..., description="Date this version became effective")
    language: DocumentLanguage = Field(
        default=DocumentLanguage.EN, description="Document language"
    )
    elements: list[ConsentElement] = Field(
        default_factory=list, description="Ordered list of document elements"
    )
    irb_approval_date: datetime = Field(..., description="IRB/Ethics committee approval date")
    total_pages: int = Field(..., ge=1, description="Total number of pages")
    estimated_read_time_minutes: int = Field(
        ..., ge=1, description="Estimated time to read in minutes"
    )


class PatientConsent(BaseModel):
    """A patient's consent record tracking completion status."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique patient consent identifier")
    patient_id: str = Field(..., description="Patient identifier")
    trial_id: str = Field(..., description="Trial identifier")
    document_id: str = Field(..., description="Consent document identifier")
    site_id: str = Field(..., description="Site identifier")
    status: ConsentStatus = Field(
        default=ConsentStatus.NOT_STARTED, description="Consent lifecycle status"
    )
    started_at: datetime | None = Field(None, description="When patient began consent process")
    completed_at: datetime | None = Field(None, description="When consent process completed")
    signature_date: datetime | None = Field(None, description="Date of signature")
    witness_name: str | None = Field(None, description="Witness name")
    witness_signature_date: datetime | None = Field(
        None, description="Date witness signed"
    )
    ip_address: str | None = Field(None, description="IP address at time of signature")
    device_info: str | None = Field(None, description="Device/browser info at signing")
    time_spent_minutes: float | None = Field(
        None, ge=0, description="Total time spent on consent in minutes"
    )
    quiz_score: float | None = Field(
        None, ge=0, le=100, description="Quiz comprehension score (percentage)"
    )
    elements_viewed: list[str] = Field(
        default_factory=list, description="List of element IDs viewed"
    )
    elements_completed: list[str] = Field(
        default_factory=list, description="List of element IDs completed"
    )
    re_consent_reason: str | None = Field(
        None, description="Reason for re-consent (protocol amendment, etc.)"
    )


class ConsentWithdrawal(BaseModel):
    """A record of consent withdrawal by a patient."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique withdrawal identifier")
    patient_consent_id: str = Field(..., description="Associated patient consent ID")
    patient_id: str = Field(..., description="Patient identifier")
    withdrawal_date: datetime = Field(..., description="Date of withdrawal")
    reason: str = Field(..., description="Reason for withdrawal")
    data_retention_preference: DataRetentionPreference = Field(
        ..., description="Patient's data retention preference"
    )
    specimens_disposition: str | None = Field(
        None, description="Disposition instructions for collected specimens"
    )
    acknowledged_by: str | None = Field(
        None, description="Name of staff who acknowledged withdrawal"
    )


class ConsentAuditEntry(BaseModel):
    """21 CFR Part 11 compliant audit trail entry for consent actions."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique audit entry identifier")
    patient_consent_id: str = Field(..., description="Associated patient consent ID")
    action: ConsentAuditAction = Field(..., description="Audit action type")
    timestamp: datetime = Field(..., description="When the action occurred")
    ip_address: str | None = Field(None, description="IP address of the action")
    details: str | None = Field(None, description="Additional details about the action")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class ConsentDocumentCreate(BaseModel):
    """Request to create a new consent document."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    version: str = Field(..., description="Document version")
    title: str = Field(..., description="Document title")
    consent_type: ConsentType = Field(..., description="Type of consent")
    effective_date: datetime = Field(..., description="Effective date")
    language: DocumentLanguage = Field(
        default=DocumentLanguage.EN, description="Document language"
    )
    irb_approval_date: datetime = Field(..., description="IRB approval date")
    total_pages: int = Field(..., ge=1, description="Total pages")
    estimated_read_time_minutes: int = Field(..., ge=1, description="Estimated read time")


class ConsentDocumentUpdate(BaseModel):
    """Request to update a consent document."""

    model_config = ConfigDict(from_attributes=True)

    version: str | None = Field(None, description="Version")
    title: str | None = Field(None, description="Title")
    effective_date: datetime | None = Field(None, description="Effective date")
    language: DocumentLanguage | None = Field(None, description="Language")
    irb_approval_date: datetime | None = Field(None, description="IRB approval date")
    total_pages: int | None = Field(None, ge=1, description="Total pages")
    estimated_read_time_minutes: int | None = Field(None, ge=1, description="Read time")


class ConsentElementCreate(BaseModel):
    """Request to add an element to a consent document."""

    model_config = ConfigDict(from_attributes=True)

    element_type: ConsentElementType = Field(..., description="Element type")
    page_number: int = Field(..., ge=1, description="Page number")
    content_summary: str = Field(..., description="Content summary")
    required: bool = Field(default=True, description="Required?")
    quiz_question: str | None = Field(None, description="Quiz question")
    quiz_correct_answer: str | None = Field(None, description="Correct answer")
    quiz_options: list[str] | None = Field(None, description="Quiz options")


class PatientConsentCreate(BaseModel):
    """Request to create a patient consent record."""

    model_config = ConfigDict(from_attributes=True)

    patient_id: str = Field(..., description="Patient ID")
    trial_id: str = Field(..., description="Trial ID")
    document_id: str = Field(..., description="Document ID")
    site_id: str = Field(..., description="Site ID")


class PatientConsentUpdate(BaseModel):
    """Request to update a patient consent record."""

    model_config = ConfigDict(from_attributes=True)

    status: ConsentStatus | None = Field(None, description="Status")
    witness_name: str | None = Field(None, description="Witness name")
    witness_signature_date: datetime | None = Field(None, description="Witness sig date")
    ip_address: str | None = Field(None, description="IP address")
    device_info: str | None = Field(None, description="Device info")
    re_consent_reason: str | None = Field(None, description="Re-consent reason")


class ConsentSignRequest(BaseModel):
    """Request to sign a patient consent."""

    model_config = ConfigDict(from_attributes=True)

    ip_address: str = Field(..., description="IP address at signing")
    device_info: str = Field(..., description="Device/browser info")
    witness_name: str | None = Field(None, description="Witness name")
    quiz_answers: dict[str, str] | None = Field(
        None, description="Quiz element ID -> answer mapping"
    )


class ConsentWithdrawalCreate(BaseModel):
    """Request to withdraw consent."""

    model_config = ConfigDict(from_attributes=True)

    reason: str = Field(..., description="Reason for withdrawal")
    data_retention_preference: DataRetentionPreference = Field(
        ..., description="Data retention preference"
    )
    specimens_disposition: str | None = Field(None, description="Specimens disposition")


class ViewElementRequest(BaseModel):
    """Request to record viewing of a consent element."""

    model_config = ConfigDict(from_attributes=True)

    element_id: str = Field(..., description="Element ID being viewed")
    time_spent_seconds: float = Field(
        default=0, ge=0, description="Time spent on element in seconds"
    )


class CompleteElementRequest(BaseModel):
    """Request to record completion of a consent element."""

    model_config = ConfigDict(from_attributes=True)

    element_id: str = Field(..., description="Element ID being completed")
    quiz_answer: str | None = Field(None, description="Answer for quiz elements")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class ConsentDocumentListResponse(BaseModel):
    """List of consent documents."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ConsentDocument] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class PatientConsentListResponse(BaseModel):
    """List of patient consents."""

    model_config = ConfigDict(from_attributes=True)

    items: list[PatientConsent] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ConsentWithdrawalListResponse(BaseModel):
    """List of consent withdrawals."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ConsentWithdrawal] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ConsentAuditListResponse(BaseModel):
    """List of consent audit entries."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ConsentAuditEntry] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Metrics / dashboard
# ---------------------------------------------------------------------------


class EConsentMetrics(BaseModel):
    """Aggregated eConsent operational metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_documents: int = Field(ge=0, description="Total consent documents")
    total_consents: int = Field(ge=0, description="Total patient consent records")
    consents_by_status: dict[str, int] = Field(
        default_factory=dict, description="Consent counts by status"
    )
    avg_completion_time_minutes: float = Field(
        ge=0, description="Average time to complete consent in minutes"
    )
    avg_quiz_score: float = Field(
        ge=0, le=100, description="Average quiz comprehension score"
    )
    withdrawal_rate: float = Field(
        ge=0, le=100, description="Percentage of consents that were withdrawn"
    )
    re_consent_pending: int = Field(
        ge=0, description="Number of patients needing re-consent"
    )
    language_distribution: dict[str, int] = Field(
        default_factory=dict, description="Consent counts by language"
    )


# ---------------------------------------------------------------------------
# Comprehension analytics
# ---------------------------------------------------------------------------


class ComprehensionAnalytics(BaseModel):
    """Comprehension analytics for consent quiz performance."""

    model_config = ConfigDict(from_attributes=True)

    total_quizzes_taken: int = Field(ge=0, description="Total quizzes completed")
    avg_score: float = Field(ge=0, le=100, description="Average quiz score")
    pass_rate: float = Field(ge=0, le=100, description="Percentage meeting 80% threshold")
    score_distribution: dict[str, int] = Field(
        default_factory=dict, description="Score ranges and counts"
    )
    avg_time_spent_minutes: float = Field(
        ge=0, description="Average time spent on consent process"
    )
    elements_with_lowest_completion: list[str] = Field(
        default_factory=list, description="Element IDs with lowest completion rates"
    )
