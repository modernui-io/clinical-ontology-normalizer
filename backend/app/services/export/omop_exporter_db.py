"""Database-backed OMOP export utilities.

Provides functions to convert database models to OMOP format
for export to NOTE and NOTE_NLP tables.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from app.models.document import Document
from app.models.mention import Mention, MentionConceptCandidate
from app.services.export.omop_exporter import (
    BaseOMOPExporter,
    NoteExport,
    NoteNLPExport,
)

# OMOP note type concept IDs
NOTE_TYPE_CONCEPTS = {
    "progress_note": 44814645,  # EHR note
    "discharge_summary": 44814646,  # Discharge summary
    "admission_note": 44814647,  # Admission note
    "h_and_p": 44814648,  # History and physical
    "operative_note": 44814649,  # Operative note
    "consult_note": 44814650,  # Consultation note
    "radiology_report": 44814651,  # Radiology report
    "pathology_report": 44814652,  # Pathology report
    "nursing_note": 44814653,  # Nursing note
    "default": 44814645,  # Default to EHR note
}


def patient_id_to_person_id(patient_id: str) -> int:
    """Convert patient ID string to OMOP person_id integer.

    OMOP requires integer person_id. This generates a deterministic
    integer from the patient ID string.

    Args:
        patient_id: String patient identifier (e.g., "P001")

    Returns:
        Integer person_id derived from the patient ID
    """
    # Use hash for deterministic conversion
    # In production, this would map to an actual OMOP person table
    return abs(hash(patient_id)) % (10**9)


def document_id_to_note_id(document_id: str | UUID) -> int:
    """Convert document UUID to OMOP note_id integer.

    Args:
        document_id: UUID document identifier

    Returns:
        Integer note_id derived from the UUID
    """
    if isinstance(document_id, UUID):
        return abs(hash(document_id.hex)) % (10**12)
    return abs(hash(str(document_id))) % (10**12)


def mention_id_to_note_nlp_id(mention_id: str | UUID) -> int:
    """Convert mention UUID to OMOP note_nlp_id integer.

    Args:
        mention_id: UUID mention identifier

    Returns:
        Integer note_nlp_id derived from the UUID
    """
    if isinstance(mention_id, UUID):
        return abs(hash(mention_id.hex)) % (10**12)
    return abs(hash(str(mention_id))) % (10**12)


def note_type_to_concept_id(note_type: str) -> int:
    """Map note type string to OMOP note_type_concept_id.

    Args:
        note_type: Note type string (e.g., "Progress Note")

    Returns:
        OMOP concept ID for the note type
    """
    # Normalize to lowercase with underscores
    key = note_type.lower().replace(" ", "_")
    return NOTE_TYPE_CONCEPTS.get(key, NOTE_TYPE_CONCEPTS["default"])


def document_to_note_export(document: Document) -> NoteExport:
    """Convert a Document model to OMOP NoteExport.

    Maps the Document fields to OMOP NOTE table format,
    including document metadata and text content.

    Args:
        document: Document model instance

    Returns:
        NoteExport containing OMOP NOTE row data
    """
    return NoteExport(
        note_id=document_id_to_note_id(document.id),
        person_id=patient_id_to_person_id(document.patient_id),
        note_date=document.created_at.date() if document.created_at else date.today(),
        note_datetime=document.created_at,
        note_type_concept_id=note_type_to_concept_id(document.note_type),
        note_title=document.note_type,
        note_text=document.text,
        note_source_value=str(document.id),
    )


def mention_to_note_nlp_export(
    mention: Mention,
    note_id: int | None = None,
    concept_candidate: MentionConceptCandidate | None = None,
) -> NoteNLPExport:
    """Convert a Mention model to OMOP NoteNLPExport.

    Maps the Mention fields to OMOP NOTE_NLP table format,
    preserving assertion (negation), temporality, and experiencer info.

    IMPORTANT: Negated mentions (assertion=ABSENT) are exported with
    term_exists='N' to preserve negation information in OMOP format.

    Args:
        mention: Mention model instance
        note_id: Optional pre-computed OMOP note_id for the document
        concept_candidate: Optional best concept mapping candidate

    Returns:
        NoteNLPExport containing OMOP NOTE_NLP row data
    """
    # Determine note_id from document if not provided
    if note_id is None:
        note_id = document_id_to_note_id(mention.document_id)

    # Get concept ID from candidate or default to 0
    concept_id = 0
    if concept_candidate:
        concept_id = concept_candidate.omop_concept_id
    elif mention.concept_candidates:
        # Get top-ranked candidate
        top_candidate = min(mention.concept_candidates, key=lambda c: c.rank)
        concept_id = top_candidate.omop_concept_id

    # Convert assertion to term_exists (Y/N)
    term_exists = BaseOMOPExporter.assertion_to_term_exists(mention.assertion.value)

    # Convert temporality to OMOP format
    term_temporal = BaseOMOPExporter.temporality_to_term_temporal(
        mention.temporality.value
    )

    # Build term_modifiers from experiencer and confidence
    modifiers = []
    if mention.experiencer:
        modifiers.append(f"experiencer:{mention.experiencer.value}")
    if mention.confidence < 1.0:
        modifiers.append(f"confidence:{mention.confidence:.2f}")
    term_modifiers = ",".join(modifiers) if modifiers else None

    return NoteNLPExport(
        note_nlp_id=mention_id_to_note_nlp_id(mention.id),
        note_id=note_id,
        section_concept_id=None,  # Section mapping not implemented yet
        snippet=mention.text,
        offset=mention.start_offset,
        lexical_variant=mention.lexical_variant,
        note_nlp_concept_id=concept_id,
        nlp_date=mention.created_at.date() if mention.created_at else date.today(),
        nlp_datetime=mention.created_at,
        term_exists=term_exists,
        term_temporal=term_temporal,
        term_modifiers=term_modifiers,
    )


def get_best_concept_candidate(mention: Mention) -> MentionConceptCandidate | None:
    """Get the best concept candidate for a mention.

    Returns the top-ranked concept candidate based on score and rank.

    Args:
        mention: Mention model with loaded concept_candidates relationship

    Returns:
        Best MentionConceptCandidate or None if no candidates
    """
    if not mention.concept_candidates:
        return None

    # Return the highest-ranked (lowest rank number) candidate
    return min(mention.concept_candidates, key=lambda c: c.rank)
