"""Pydantic schemas for Language & Translation Services.

Manages document translations for global clinical trials: translation project
lifecycle, translation task assignment and tracking, linguistic validation with
forward-backward and cognitive debriefing methods, certified translator
management with qualification tracking, multilingual glossary maintenance,
and translation metrics.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TranslationStatus(str, Enum):
    """Lifecycle status of a translation project or task."""

    REQUESTED = "requested"
    IN_PROGRESS = "in_progress"
    TRANSLATED = "translated"
    BACK_TRANSLATED = "back_translated"
    RECONCILED = "reconciled"
    CERTIFIED = "certified"
    DELIVERED = "delivered"


class DocumentCategory(str, Enum):
    """Category of the document being translated."""

    PROTOCOL = "protocol"
    ICF = "icf"
    PATIENT_DIARY = "patient_diary"
    QUESTIONNAIRE = "questionnaire"
    LABEL = "label"
    PACKAGING = "packaging"
    REGULATORY_SUBMISSION = "regulatory_submission"
    TRAINING_MATERIAL = "training_material"


class ValidationMethod(str, Enum):
    """Linguistic validation methodology."""

    FORWARD_BACKWARD = "forward_backward"
    DUAL_FORWARD = "dual_forward"
    COGNITIVE_DEBRIEFING = "cognitive_debriefing"
    CLINICIAN_REVIEW = "clinician_review"
    HARMONIZATION = "harmonization"


class CertificationLevel(str, Enum):
    """Certification level of a translator."""

    STANDARD = "standard"
    CERTIFIED = "certified"
    SWORN = "sworn"
    NOTARIZED = "notarized"


class TranslatorStatus(str, Enum):
    """Operational status of a translator."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING_QUALIFICATION = "pending_qualification"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class TranslationProject(BaseModel):
    """A translation project encompassing multiple language tasks for a trial."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique project identifier")
    trial_id: str = Field(..., description="Associated clinical trial identifier")
    project_name: str = Field(..., description="Descriptive project name")
    source_language: str = Field(..., description="ISO 639-1 source language code (e.g., en)")
    target_languages: list[str] = Field(
        default_factory=list,
        description="ISO 639-1 target language codes",
    )
    document_category: DocumentCategory = Field(
        ..., description="Category of document being translated"
    )
    status: TranslationStatus = Field(
        default=TranslationStatus.REQUESTED, description="Current project status"
    )
    requested_date: datetime = Field(..., description="Date the project was requested")
    due_date: datetime = Field(..., description="Target delivery date")
    completed_date: datetime | None = Field(
        None, description="Date the project was fully delivered"
    )
    requestor: str = Field(..., description="Person or department that requested the translation")
    priority: str = Field(
        default="normal", description="Priority level (low, normal, high, urgent)"
    )


class TranslationTask(BaseModel):
    """A single language translation task within a project."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique task identifier")
    project_id: str = Field(..., description="Parent project identifier")
    source_document: str = Field(..., description="Source document reference or filename")
    source_language: str = Field(..., description="ISO 639-1 source language code")
    target_language: str = Field(..., description="ISO 639-1 target language code")
    status: TranslationStatus = Field(
        default=TranslationStatus.REQUESTED, description="Current task status"
    )
    translator_id: str | None = Field(None, description="Assigned translator identifier")
    reviewer_id: str | None = Field(None, description="Assigned reviewer identifier")
    word_count: int = Field(default=0, ge=0, description="Word count of source document")
    translated_text_reference: str | None = Field(
        None, description="Reference to the translated document"
    )
    back_translation_reference: str | None = Field(
        None, description="Reference to the back-translated document"
    )
    reconciliation_notes: str | None = Field(
        None, description="Notes from reconciliation between forward and back translation"
    )
    started_date: datetime | None = Field(None, description="Date work started on this task")
    completed_date: datetime | None = Field(None, description="Date this task was completed")


class LinguisticValidation(BaseModel):
    """Linguistic validation record for a translation task."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique validation identifier")
    task_id: str = Field(..., description="Associated translation task identifier")
    method: ValidationMethod = Field(..., description="Validation methodology used")
    validation_date: datetime = Field(..., description="Date validation was performed")
    validator: str = Field(..., description="Name of the validator or validation lead")
    cognitive_debriefing_participants: int | None = Field(
        None, ge=0, description="Number of participants in cognitive debriefing"
    )
    issues_found: int = Field(default=0, ge=0, description="Number of issues identified")
    issues_resolved: int = Field(default=0, ge=0, description="Number of issues resolved")
    conceptual_equivalence_score: float = Field(
        ..., ge=0.0, le=100.0,
        description="Score for conceptual equivalence between source and target (0-100)",
    )
    cultural_appropriateness_score: float = Field(
        ..., ge=0.0, le=100.0,
        description="Score for cultural appropriateness of the translation (0-100)",
    )
    readability_score: float = Field(
        ..., ge=0.0, le=100.0,
        description="Readability score of the translated text (0-100)",
    )
    overall_pass: bool = Field(
        ..., description="Whether the translation passed overall linguistic validation"
    )
    notes: str | None = Field(None, description="Additional notes from the validation")


class CertifiedTranslator(BaseModel):
    """A certified translator qualified for clinical trial documentation."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique translator identifier")
    name: str = Field(..., description="Full name of the translator")
    email: str = Field(..., description="Contact email address")
    languages: list[str] = Field(
        default_factory=list,
        description="ISO 639-1 language codes the translator is qualified for",
    )
    specializations: list[str] = Field(
        default_factory=list,
        description="Domain specializations (e.g., oncology, cardiology, regulatory)",
    )
    certification_level: CertificationLevel = Field(
        ..., description="Level of translation certification"
    )
    certifying_body: str = Field(..., description="Organization that issued the certification")
    certification_expiry: datetime = Field(
        ..., description="Expiration date of the certification"
    )
    status: TranslatorStatus = Field(
        default=TranslatorStatus.ACTIVE, description="Current operational status"
    )
    projects_completed: int = Field(
        default=0, ge=0, description="Total number of projects completed"
    )
    quality_rating: float = Field(
        default=0.0, ge=0.0, le=5.0,
        description="Average quality rating (0-5 stars)",
    )


class TranslationGlossary(BaseModel):
    """A glossary entry mapping a source term to translations across languages."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique glossary entry identifier")
    trial_id: str = Field(..., description="Associated trial identifier")
    source_term: str = Field(..., description="Source language term")
    source_language: str = Field(..., description="ISO 639-1 source language code")
    translations: dict[str, str] = Field(
        default_factory=dict,
        description="Map of target language code to translated term",
    )
    context: str = Field(..., description="Context or usage notes for the term")
    approved: bool = Field(default=False, description="Whether the glossary entry is approved")
    approved_by: str | None = Field(None, description="Person who approved the entry")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class TranslationProjectCreate(BaseModel):
    """Request to create a new translation project."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    project_name: str = Field(..., description="Project name")
    source_language: str = Field(..., description="Source language code")
    target_languages: list[str] = Field(..., description="Target language codes")
    document_category: DocumentCategory = Field(..., description="Document category")
    due_date: datetime = Field(..., description="Target delivery date")
    requestor: str = Field(..., description="Requestor name or department")
    priority: str = Field(default="normal", description="Priority level")


class TranslationProjectUpdate(BaseModel):
    """Request to update a translation project."""

    model_config = ConfigDict(from_attributes=True)

    project_name: str | None = Field(None, description="Project name")
    target_languages: list[str] | None = Field(None, description="Target language codes")
    status: TranslationStatus | None = Field(None, description="Project status")
    due_date: datetime | None = Field(None, description="Target delivery date")
    priority: str | None = Field(None, description="Priority level")


class TranslationTaskCreate(BaseModel):
    """Request to create a new translation task."""

    model_config = ConfigDict(from_attributes=True)

    project_id: str = Field(..., description="Parent project identifier")
    source_document: str = Field(..., description="Source document reference")
    source_language: str = Field(..., description="Source language code")
    target_language: str = Field(..., description="Target language code")
    word_count: int = Field(default=0, ge=0, description="Source word count")


class TranslationTaskUpdate(BaseModel):
    """Request to update a translation task."""

    model_config = ConfigDict(from_attributes=True)

    status: TranslationStatus | None = Field(None, description="Task status")
    translator_id: str | None = Field(None, description="Translator identifier")
    reviewer_id: str | None = Field(None, description="Reviewer identifier")
    translated_text_reference: str | None = Field(None, description="Translated doc reference")
    back_translation_reference: str | None = Field(
        None, description="Back-translated doc reference"
    )
    reconciliation_notes: str | None = Field(None, description="Reconciliation notes")


class LinguisticValidationCreate(BaseModel):
    """Request to create a linguistic validation record."""

    model_config = ConfigDict(from_attributes=True)

    task_id: str = Field(..., description="Translation task identifier")
    method: ValidationMethod = Field(..., description="Validation method")
    validator: str = Field(..., description="Validator name")
    cognitive_debriefing_participants: int | None = Field(
        None, ge=0, description="Number of cognitive debriefing participants"
    )
    issues_found: int = Field(default=0, ge=0, description="Issues found")
    issues_resolved: int = Field(default=0, ge=0, description="Issues resolved")
    conceptual_equivalence_score: float = Field(
        ..., ge=0.0, le=100.0, description="Conceptual equivalence score"
    )
    cultural_appropriateness_score: float = Field(
        ..., ge=0.0, le=100.0, description="Cultural appropriateness score"
    )
    readability_score: float = Field(
        ..., ge=0.0, le=100.0, description="Readability score"
    )
    overall_pass: bool = Field(..., description="Whether validation passed")
    notes: str | None = Field(None, description="Additional notes")


class LinguisticValidationUpdate(BaseModel):
    """Request to update a linguistic validation record."""

    model_config = ConfigDict(from_attributes=True)

    issues_found: int | None = Field(None, ge=0, description="Issues found")
    issues_resolved: int | None = Field(None, ge=0, description="Issues resolved")
    conceptual_equivalence_score: float | None = Field(
        None, ge=0.0, le=100.0, description="Conceptual equivalence score"
    )
    cultural_appropriateness_score: float | None = Field(
        None, ge=0.0, le=100.0, description="Cultural appropriateness score"
    )
    readability_score: float | None = Field(
        None, ge=0.0, le=100.0, description="Readability score"
    )
    overall_pass: bool | None = Field(None, description="Whether validation passed")
    notes: str | None = Field(None, description="Additional notes")


class CertifiedTranslatorCreate(BaseModel):
    """Request to register a new certified translator."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    languages: list[str] = Field(..., description="Qualified language codes")
    specializations: list[str] = Field(default_factory=list, description="Specializations")
    certification_level: CertificationLevel = Field(..., description="Certification level")
    certifying_body: str = Field(..., description="Certifying organization")
    certification_expiry: datetime = Field(..., description="Certification expiry date")


class CertifiedTranslatorUpdate(BaseModel):
    """Request to update a certified translator."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(None, description="Full name")
    email: str | None = Field(None, description="Email address")
    languages: list[str] | None = Field(None, description="Qualified language codes")
    specializations: list[str] | None = Field(None, description="Specializations")
    certification_level: CertificationLevel | None = Field(
        None, description="Certification level"
    )
    certifying_body: str | None = Field(None, description="Certifying organization")
    certification_expiry: datetime | None = Field(None, description="Certification expiry date")
    status: TranslatorStatus | None = Field(None, description="Operational status")
    quality_rating: float | None = Field(None, ge=0.0, le=5.0, description="Quality rating")


class TranslationGlossaryCreate(BaseModel):
    """Request to create a glossary entry."""

    model_config = ConfigDict(from_attributes=True)

    trial_id: str = Field(..., description="Trial identifier")
    source_term: str = Field(..., description="Source term")
    source_language: str = Field(..., description="Source language code")
    translations: dict[str, str] = Field(
        default_factory=dict, description="Language-to-term translations"
    )
    context: str = Field(..., description="Context or usage notes")


class TranslationGlossaryUpdate(BaseModel):
    """Request to update a glossary entry."""

    model_config = ConfigDict(from_attributes=True)

    source_term: str | None = Field(None, description="Source term")
    translations: dict[str, str] | None = Field(None, description="Translations")
    context: str | None = Field(None, description="Context or usage notes")
    approved: bool | None = Field(None, description="Approval status")
    approved_by: str | None = Field(None, description="Approver name")


class TranslatorAssignment(BaseModel):
    """Request to assign a translator to a task."""

    model_config = ConfigDict(from_attributes=True)

    translator_id: str = Field(..., description="Translator identifier to assign")
    reviewer_id: str | None = Field(None, description="Optional reviewer identifier")


class TranslationSubmission(BaseModel):
    """Request to submit a translation for a task."""

    model_config = ConfigDict(from_attributes=True)

    translated_text_reference: str = Field(
        ..., description="Reference to the translated document"
    )
    back_translation_reference: str | None = Field(
        None, description="Reference to the back-translated document"
    )
    reconciliation_notes: str | None = Field(None, description="Reconciliation notes")


class TranslationCertification(BaseModel):
    """Request to certify a completed translation."""

    model_config = ConfigDict(from_attributes=True)

    certified_by: str = Field(..., description="Name of the certifying authority")
    certification_notes: str | None = Field(None, description="Certification notes")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class TranslationProjectListResponse(BaseModel):
    """List of translation projects."""

    model_config = ConfigDict(from_attributes=True)

    items: list[TranslationProject] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class TranslationTaskListResponse(BaseModel):
    """List of translation tasks."""

    model_config = ConfigDict(from_attributes=True)

    items: list[TranslationTask] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class LinguisticValidationListResponse(BaseModel):
    """List of linguistic validations."""

    model_config = ConfigDict(from_attributes=True)

    items: list[LinguisticValidation] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class CertifiedTranslatorListResponse(BaseModel):
    """List of certified translators."""

    model_config = ConfigDict(from_attributes=True)

    items: list[CertifiedTranslator] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class TranslationGlossaryListResponse(BaseModel):
    """List of glossary entries."""

    model_config = ConfigDict(from_attributes=True)

    items: list[TranslationGlossary] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Project progress & metrics
# ---------------------------------------------------------------------------


class ProjectProgress(BaseModel):
    """Progress summary for a translation project."""

    model_config = ConfigDict(from_attributes=True)

    project_id: str = Field(..., description="Project identifier")
    project_name: str = Field(..., description="Project name")
    status: TranslationStatus = Field(..., description="Overall project status")
    total_tasks: int = Field(ge=0, description="Total translation tasks")
    tasks_completed: int = Field(ge=0, description="Tasks completed (certified or delivered)")
    tasks_in_progress: int = Field(ge=0, description="Tasks currently in progress")
    tasks_pending: int = Field(ge=0, description="Tasks not yet started")
    completion_percentage: float = Field(
        ge=0.0, le=100.0, description="Percentage of tasks completed"
    )
    total_word_count: int = Field(ge=0, description="Total word count across all tasks")
    languages_completed: list[str] = Field(
        default_factory=list, description="Languages with completed translations"
    )
    languages_pending: list[str] = Field(
        default_factory=list, description="Languages still awaiting translation"
    )
    validations_passed: int = Field(ge=0, description="Number of validations passed")
    validations_failed: int = Field(ge=0, description="Number of validations failed")


class LanguageMetrics(BaseModel):
    """Aggregated Language & Translation Services metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_projects: int = Field(ge=0, description="Total translation projects")
    projects_by_status: dict[str, int] = Field(
        default_factory=dict, description="Project counts by status"
    )
    total_tasks: int = Field(ge=0, description="Total translation tasks")
    tasks_by_status: dict[str, int] = Field(
        default_factory=dict, description="Task counts by status"
    )
    total_translators: int = Field(ge=0, description="Total registered translators")
    active_translators: int = Field(ge=0, description="Currently active translators")
    total_validations: int = Field(ge=0, description="Total linguistic validations performed")
    validations_passed: int = Field(ge=0, description="Validations that passed")
    validations_failed: int = Field(ge=0, description="Validations that failed")
    avg_conceptual_equivalence: float = Field(
        ge=0.0, description="Average conceptual equivalence score"
    )
    avg_cultural_appropriateness: float = Field(
        ge=0.0, description="Average cultural appropriateness score"
    )
    avg_readability: float = Field(ge=0.0, description="Average readability score")
    total_glossary_entries: int = Field(ge=0, description="Total glossary entries")
    approved_glossary_entries: int = Field(ge=0, description="Approved glossary entries")
    total_word_count: int = Field(ge=0, description="Total words across all tasks")
    languages_supported: list[str] = Field(
        default_factory=list, description="All unique target languages"
    )
    avg_translator_rating: float = Field(
        ge=0.0, le=5.0, description="Average translator quality rating"
    )
