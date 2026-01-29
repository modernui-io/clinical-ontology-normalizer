"""OMOP CDM export service for clinical documents and NLP results.

OMOP CDM (Common Data Model) defines standardized tables for clinical data.
This service exports documents and mentions to OMOP format:

- NOTE table: Clinical document metadata
- NOTE_NLP table: NLP-extracted mentions with assertion attributes

Reference: https://ohdsi.github.io/CommonDataModel/cdm54.html
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Get current UTC time using timezone-aware datetime."""
    return datetime.now(timezone.utc)


class NoteExport(BaseModel):
    """OMOP NOTE table row for clinical document metadata.

    Represents a clinical document in OMOP CDM format.
    """

    note_id: int = Field(..., description="Unique identifier for the note")
    person_id: int = Field(..., description="Patient identifier")
    note_date: date = Field(..., description="Date of the note")
    note_datetime: datetime | None = Field(
        None, description="Datetime of the note"
    )
    note_type_concept_id: int = Field(
        44814645,  # EHR note
        description="Type of note (OMOP concept ID)",
    )
    note_class_concept_id: int = Field(
        0, description="Class of note (e.g., progress note, discharge summary)"
    )
    note_title: str | None = Field(None, description="Title of the note")
    note_text: str = Field(..., description="Full text of the clinical note")
    encoding_concept_id: int = Field(
        0, description="Character encoding concept ID"
    )
    language_concept_id: int = Field(
        4180186,  # English
        description="Language of the note",
    )
    provider_id: int | None = Field(None, description="Provider ID")
    visit_occurrence_id: int | None = Field(
        None, description="Visit occurrence ID"
    )
    visit_detail_id: int | None = Field(None, description="Visit detail ID")
    note_source_value: str | None = Field(
        None, description="Source value from original system"
    )


class NoteNLPExport(BaseModel):
    """OMOP NOTE_NLP table row for NLP-extracted mentions.

    Represents an extracted clinical mention with its assertion attributes.
    The term_exists field captures negation: 'Y' for present, 'N' for absent.
    The term_temporal field captures temporality.
    """

    note_nlp_id: int = Field(..., description="Unique identifier for the NLP result")
    note_id: int = Field(..., description="Reference to the source note")
    section_concept_id: int | None = Field(
        None, description="Section where mention was found"
    )
    snippet: str = Field(
        ..., description="Text snippet containing the mention"
    )
    offset: int = Field(..., description="Character offset in the note text")
    lexical_variant: str = Field(
        ..., description="The actual text as it appears in the note"
    )
    note_nlp_concept_id: int = Field(
        ..., description="OMOP concept ID for the extracted entity"
    )
    note_nlp_source_concept_id: int | None = Field(
        None, description="Source concept ID before mapping"
    )
    nlp_system: str = Field(
        "clinical_ontology_normalizer",
        description="Name of the NLP system",
    )
    nlp_date: date = Field(..., description="Date when NLP was run")
    nlp_datetime: datetime | None = Field(
        None, description="Datetime when NLP was run"
    )
    term_exists: str = Field(
        "Y",
        description="Whether term exists (Y) or is negated (N)",
    )
    term_temporal: str | None = Field(
        None,
        description="Temporal context (past, current, future)",
    )
    term_modifiers: str | None = Field(
        None,
        description="Additional modifiers (experiencer, certainty, etc.)",
    )


@dataclass
class OMOPExportResult:
    """Result of an OMOP export operation."""

    notes: list[NoteExport] = field(default_factory=list)
    note_nlp_records: list[NoteNLPExport] = field(default_factory=list)
    note_count: int = 0
    note_nlp_count: int = 0
    patient_id: str | None = None
    export_date: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        """Update counts after initialization."""
        self.note_count = len(self.notes)
        self.note_nlp_count = len(self.note_nlp_records)


class BaseOMOPExporter(ABC):
    """Abstract base class for OMOP CDM export services.

    Defines the interface for exporting clinical documents and NLP results
    to OMOP CDM format.
    """

    @abstractmethod
    def export_patient_notes(self, patient_id: str) -> OMOPExportResult:
        """Export all notes for a patient in OMOP format.

        Args:
            patient_id: The patient identifier

        Returns:
            OMOPExportResult with NOTE table rows
        """
        ...

    @abstractmethod
    def export_patient_nlp(self, patient_id: str) -> OMOPExportResult:
        """Export all NLP results for a patient in OMOP format.

        Args:
            patient_id: The patient identifier

        Returns:
            OMOPExportResult with NOTE_NLP table rows
        """
        ...

    @abstractmethod
    def export_patient_full(self, patient_id: str) -> OMOPExportResult:
        """Export complete OMOP data for a patient (notes + NLP).

        Args:
            patient_id: The patient identifier

        Returns:
            OMOPExportResult with both NOTE and NOTE_NLP rows
        """
        ...

    @abstractmethod
    def export_document(self, document_id: str) -> NoteExport:
        """Export a single document as OMOP NOTE.

        Args:
            document_id: The document identifier

        Returns:
            NoteExport representing the NOTE table row
        """
        ...

    @staticmethod
    def assertion_to_term_exists(assertion: str) -> str:
        """Convert assertion attribute to OMOP term_exists value.

        OMOP uses 'Y' for present and 'N' for absent/negated.

        Args:
            assertion: The assertion value (present, absent, possible)

        Returns:
            'Y' for present/possible, 'N' for absent
        """
        if assertion.lower() == "absent":
            return "N"
        return "Y"

    @staticmethod
    def temporality_to_term_temporal(temporality: str) -> str | None:
        """Convert temporality attribute to OMOP term_temporal value.

        Args:
            temporality: The temporality value (current, past, future)

        Returns:
            Standardized temporality string
        """
        mapping = {
            "current": "Current",
            "past": "Historical",
            "future": "Future",
        }
        return mapping.get(temporality.lower())


class DatabaseOMOPExporter(BaseOMOPExporter):
    """OMOP exporter that reads from the database.

    This implementation queries the database for documents, mentions,
    and clinical facts to produce OMOP-formatted exports.
    """

    def __init__(self) -> None:
        """Initialize the database exporter."""
        # Database session will be obtained from the dependency injection
        # in the API layer. This class focuses on transformation logic.
        pass

    def export_patient_notes(self, patient_id: str) -> OMOPExportResult:
        """Export all notes for a patient in OMOP format.

        This is a placeholder implementation. The actual database queries
        will be performed in the API layer where session is available.
        """
        return OMOPExportResult(patient_id=patient_id)

    def export_patient_nlp(self, patient_id: str) -> OMOPExportResult:
        """Export all NLP results for a patient in OMOP format.

        This is a placeholder implementation. The actual database queries
        will be performed in the API layer where session is available.
        """
        return OMOPExportResult(patient_id=patient_id)

    def export_patient_full(self, patient_id: str) -> OMOPExportResult:
        """Export complete OMOP data for a patient (notes + NLP).

        This is a placeholder implementation. The actual database queries
        will be performed in the API layer where session is available.
        """
        return OMOPExportResult(patient_id=patient_id)

    def export_document(self, document_id: str) -> NoteExport:
        """Export a single document as OMOP NOTE.

        This is a placeholder implementation. The actual database queries
        will be performed in the API layer where session is available.
        """
        raise NotImplementedError("Requires database session")
