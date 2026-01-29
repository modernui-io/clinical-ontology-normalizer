"""Tests for OMOP CDM export service (Phase 9).

These tests verify the OMOP export functionality:
- NoteExport schema for NOTE table
- NoteNLPExport schema for NOTE_NLP table
- Assertion/temporality conversion utilities
- Export result dataclass
- Document to NOTE export conversion (task 9.2)
- Mention to NOTE_NLP export conversion (task 9.3)
"""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from app.schemas.base import Assertion, Experiencer, Temporality
from app.services.export import (
    BaseOMOPExporter,
    DatabaseOMOPExporter,
    NoteExport,
    NoteNLPExport,
    OMOPExportResult,
    document_id_to_note_id,
    document_to_note_export,
    mention_id_to_note_nlp_id,
    mention_to_note_nlp_export,
    note_type_to_concept_id,
    patient_id_to_person_id,
)


class TestNoteExportSchema:
    """Tests for NoteExport Pydantic model."""

    def test_note_export_required_fields(self) -> None:
        """Test NoteExport with required fields only."""
        note = NoteExport(
            note_id=1,
            person_id=12345,
            note_date=date(2024, 1, 15),
            note_text="Patient presents with chest pain.",
        )
        assert note.note_id == 1
        assert note.person_id == 12345
        assert note.note_date == date(2024, 1, 15)
        assert note.note_text == "Patient presents with chest pain."
        # Check defaults
        assert note.note_type_concept_id == 44814645  # EHR note
        assert note.language_concept_id == 4180186  # English

    def test_note_export_all_fields(self) -> None:
        """Test NoteExport with all optional fields."""
        now = datetime.now(timezone.utc)
        note = NoteExport(
            note_id=100,
            person_id=999,
            note_date=date(2024, 6, 1),
            note_datetime=now,
            note_type_concept_id=44814646,
            note_class_concept_id=44814647,
            note_title="Progress Note",
            note_text="Follow-up visit.",
            encoding_concept_id=32678,
            language_concept_id=4182511,  # Spanish
            provider_id=500,
            visit_occurrence_id=1001,
            visit_detail_id=2001,
            note_source_value="PN-2024-001",
        )
        assert note.note_title == "Progress Note"
        assert note.provider_id == 500
        assert note.visit_occurrence_id == 1001
        assert note.note_source_value == "PN-2024-001"

    def test_note_export_serialization(self) -> None:
        """Test NoteExport serializes to dict correctly."""
        note = NoteExport(
            note_id=1,
            person_id=100,
            note_date=date(2024, 3, 15),
            note_text="Test note",
        )
        data = note.model_dump()
        assert data["note_id"] == 1
        assert data["person_id"] == 100
        assert data["note_text"] == "Test note"


class TestNoteNLPExportSchema:
    """Tests for NoteNLPExport Pydantic model."""

    def test_note_nlp_export_required_fields(self) -> None:
        """Test NoteNLPExport with required fields only."""
        nlp = NoteNLPExport(
            note_nlp_id=1,
            note_id=100,
            snippet="chest pain",
            offset=25,
            lexical_variant="chest pain",
            note_nlp_concept_id=4087709,  # Chest pain concept
            nlp_date=date(2024, 1, 15),
        )
        assert nlp.note_nlp_id == 1
        assert nlp.note_id == 100
        assert nlp.snippet == "chest pain"
        assert nlp.offset == 25
        assert nlp.lexical_variant == "chest pain"
        assert nlp.note_nlp_concept_id == 4087709
        # Check defaults
        assert nlp.nlp_system == "clinical_ontology_normalizer"
        assert nlp.term_exists == "Y"

    def test_note_nlp_export_negated(self) -> None:
        """Test NoteNLPExport with negation (term_exists=N)."""
        nlp = NoteNLPExport(
            note_nlp_id=2,
            note_id=100,
            snippet="no chest pain",
            offset=30,
            lexical_variant="chest pain",
            note_nlp_concept_id=4087709,
            nlp_date=date(2024, 1, 15),
            term_exists="N",  # Negated
            term_temporal="Current",
            term_modifiers="patient,certain",
        )
        assert nlp.term_exists == "N"
        assert nlp.term_temporal == "Current"
        assert nlp.term_modifiers == "patient,certain"

    def test_note_nlp_export_historical(self) -> None:
        """Test NoteNLPExport with historical temporality."""
        nlp = NoteNLPExport(
            note_nlp_id=3,
            note_id=100,
            snippet="history of diabetes",
            offset=50,
            lexical_variant="diabetes",
            note_nlp_concept_id=201826,  # Diabetes concept
            nlp_date=date(2024, 1, 15),
            term_temporal="Historical",
        )
        assert nlp.term_temporal == "Historical"

    def test_note_nlp_export_serialization(self) -> None:
        """Test NoteNLPExport serializes to dict correctly."""
        nlp = NoteNLPExport(
            note_nlp_id=1,
            note_id=100,
            snippet="test",
            offset=0,
            lexical_variant="test",
            note_nlp_concept_id=12345,
            nlp_date=date(2024, 1, 1),
        )
        data = nlp.model_dump()
        assert data["note_nlp_id"] == 1
        assert data["nlp_system"] == "clinical_ontology_normalizer"
        assert data["term_exists"] == "Y"


class TestOMOPExportResult:
    """Tests for OMOPExportResult dataclass."""

    def test_empty_export_result(self) -> None:
        """Test empty export result."""
        result = OMOPExportResult()
        assert result.notes == []
        assert result.note_nlp_records == []
        assert result.note_count == 0
        assert result.note_nlp_count == 0
        assert result.patient_id is None

    def test_export_result_with_data(self) -> None:
        """Test export result with notes and NLP records."""
        notes = [
            NoteExport(
                note_id=1,
                person_id=100,
                note_date=date(2024, 1, 1),
                note_text="Test",
            )
        ]
        nlp_records = [
            NoteNLPExport(
                note_nlp_id=1,
                note_id=1,
                snippet="test",
                offset=0,
                lexical_variant="test",
                note_nlp_concept_id=123,
                nlp_date=date(2024, 1, 1),
            ),
            NoteNLPExport(
                note_nlp_id=2,
                note_id=1,
                snippet="test2",
                offset=10,
                lexical_variant="test2",
                note_nlp_concept_id=456,
                nlp_date=date(2024, 1, 1),
            ),
        ]
        result = OMOPExportResult(
            notes=notes,
            note_nlp_records=nlp_records,
            patient_id="P001",
        )
        assert result.note_count == 1
        assert result.note_nlp_count == 2
        assert result.patient_id == "P001"

    def test_export_result_export_date(self) -> None:
        """Test export result has export_date timestamp."""
        result = OMOPExportResult()
        assert isinstance(result.export_date, datetime)


class TestBaseOMOPExporterUtilities:
    """Tests for BaseOMOPExporter utility methods."""

    def test_assertion_to_term_exists_present(self) -> None:
        """Test present assertion converts to Y."""
        assert BaseOMOPExporter.assertion_to_term_exists("present") == "Y"
        assert BaseOMOPExporter.assertion_to_term_exists("Present") == "Y"
        assert BaseOMOPExporter.assertion_to_term_exists("PRESENT") == "Y"

    def test_assertion_to_term_exists_absent(self) -> None:
        """Test absent assertion converts to N."""
        assert BaseOMOPExporter.assertion_to_term_exists("absent") == "N"
        assert BaseOMOPExporter.assertion_to_term_exists("Absent") == "N"
        assert BaseOMOPExporter.assertion_to_term_exists("ABSENT") == "N"

    def test_assertion_to_term_exists_possible(self) -> None:
        """Test possible assertion converts to Y (not negated)."""
        assert BaseOMOPExporter.assertion_to_term_exists("possible") == "Y"

    def test_temporality_to_term_temporal_current(self) -> None:
        """Test current temporality conversion."""
        assert BaseOMOPExporter.temporality_to_term_temporal("current") == "Current"
        assert BaseOMOPExporter.temporality_to_term_temporal("Current") == "Current"

    def test_temporality_to_term_temporal_past(self) -> None:
        """Test past temporality conversion."""
        assert BaseOMOPExporter.temporality_to_term_temporal("past") == "Historical"
        assert BaseOMOPExporter.temporality_to_term_temporal("Past") == "Historical"

    def test_temporality_to_term_temporal_future(self) -> None:
        """Test future temporality conversion."""
        assert BaseOMOPExporter.temporality_to_term_temporal("future") == "Future"

    def test_temporality_to_term_temporal_unknown(self) -> None:
        """Test unknown temporality returns None."""
        assert BaseOMOPExporter.temporality_to_term_temporal("unknown") is None
        assert BaseOMOPExporter.temporality_to_term_temporal("foo") is None


class TestDatabaseOMOPExporter:
    """Tests for DatabaseOMOPExporter concrete implementation."""

    def test_instantiation(self) -> None:
        """Test DatabaseOMOPExporter can be instantiated."""
        exporter = DatabaseOMOPExporter()
        assert isinstance(exporter, BaseOMOPExporter)

    def test_export_patient_notes_placeholder(self) -> None:
        """Test export_patient_notes returns empty result placeholder."""
        exporter = DatabaseOMOPExporter()
        result = exporter.export_patient_notes("P001")
        assert result.patient_id == "P001"
        assert result.note_count == 0

    def test_export_patient_nlp_placeholder(self) -> None:
        """Test export_patient_nlp returns empty result placeholder."""
        exporter = DatabaseOMOPExporter()
        result = exporter.export_patient_nlp("P002")
        assert result.patient_id == "P002"
        assert result.note_nlp_count == 0

    def test_export_patient_full_placeholder(self) -> None:
        """Test export_patient_full returns empty result placeholder."""
        exporter = DatabaseOMOPExporter()
        result = exporter.export_patient_full("P003")
        assert result.patient_id == "P003"

    def test_export_document_raises_not_implemented(self) -> None:
        """Test export_document raises NotImplementedError without session."""
        exporter = DatabaseOMOPExporter()
        with pytest.raises(NotImplementedError):
            exporter.export_document("doc-123")


class TestIDConversionFunctions:
    """Tests for ID conversion utilities (task 9.2, 9.3)."""

    def test_patient_id_to_person_id_string(self) -> None:
        """Test converting string patient ID to integer person ID."""
        person_id = patient_id_to_person_id("P001")
        assert isinstance(person_id, int)
        assert person_id > 0
        # Should be deterministic
        assert patient_id_to_person_id("P001") == person_id

    def test_patient_id_to_person_id_different_patients(self) -> None:
        """Test different patients get different person IDs."""
        id1 = patient_id_to_person_id("P001")
        id2 = patient_id_to_person_id("P002")
        assert id1 != id2

    def test_document_id_to_note_id_uuid(self) -> None:
        """Test converting UUID document ID to integer note ID."""
        doc_uuid = UUID("12345678-1234-5678-1234-567812345678")
        note_id = document_id_to_note_id(doc_uuid)
        assert isinstance(note_id, int)
        assert note_id > 0

    def test_document_id_to_note_id_string(self) -> None:
        """Test converting string document ID to integer note ID."""
        note_id = document_id_to_note_id("12345678-1234-5678-1234-567812345678")
        assert isinstance(note_id, int)
        assert note_id > 0

    def test_mention_id_to_note_nlp_id_uuid(self) -> None:
        """Test converting UUID mention ID to integer note_nlp ID."""
        mention_uuid = UUID("abcdefab-cdef-abcd-efab-cdefabcdefab")
        nlp_id = mention_id_to_note_nlp_id(mention_uuid)
        assert isinstance(nlp_id, int)
        assert nlp_id > 0

    def test_note_type_to_concept_id_progress_note(self) -> None:
        """Test mapping progress note to concept ID."""
        concept_id = note_type_to_concept_id("progress_note")
        assert concept_id == 44814645

    def test_note_type_to_concept_id_discharge_summary(self) -> None:
        """Test mapping discharge summary to concept ID."""
        concept_id = note_type_to_concept_id("discharge_summary")
        assert concept_id == 44814646

    def test_note_type_to_concept_id_with_spaces(self) -> None:
        """Test mapping note type with spaces."""
        concept_id = note_type_to_concept_id("Progress Note")
        assert concept_id == 44814645

    def test_note_type_to_concept_id_unknown(self) -> None:
        """Test unknown note type returns default."""
        concept_id = note_type_to_concept_id("Unknown Type")
        assert concept_id == 44814645  # Default


class TestDocumentToNoteExport:
    """Tests for document_to_note_export function (task 9.2)."""

    def _create_mock_document(self) -> MagicMock:
        """Create a mock Document model."""
        doc = MagicMock()
        doc.id = UUID("12345678-1234-5678-1234-567812345678")
        doc.patient_id = "P001"
        doc.note_type = "Progress Note"
        doc.text = "Patient presents with chest pain."
        doc.created_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        return doc

    def test_document_to_note_export_basic(self) -> None:
        """Test basic document to NOTE export."""
        doc = self._create_mock_document()
        note = document_to_note_export(doc)

        assert isinstance(note, NoteExport)
        assert note.note_text == "Patient presents with chest pain."
        assert note.note_date == date(2024, 1, 15)
        assert note.note_title == "Progress Note"
        assert isinstance(note.note_id, int)
        assert isinstance(note.person_id, int)

    def test_document_to_note_export_preserves_source_value(self) -> None:
        """Test note_source_value contains original document ID."""
        doc = self._create_mock_document()
        note = document_to_note_export(doc)

        assert note.note_source_value == str(doc.id)

    def test_document_to_note_export_maps_note_type(self) -> None:
        """Test note type is mapped to concept ID."""
        doc = self._create_mock_document()
        doc.note_type = "discharge_summary"
        note = document_to_note_export(doc)

        assert note.note_type_concept_id == 44814646


class TestMentionToNoteNLPExport:
    """Tests for mention_to_note_nlp_export function (task 9.3)."""

    def _create_mock_mention(self) -> MagicMock:
        """Create a mock Mention model."""
        mention = MagicMock()
        mention.id = UUID("abcdefab-cdef-abcd-efab-cdefabcdefab")
        mention.document_id = "12345678-1234-5678-1234-567812345678"
        mention.text = "chest pain"
        mention.start_offset = 25
        mention.end_offset = 35
        mention.lexical_variant = "chest pain"
        mention.assertion = Assertion.PRESENT
        mention.temporality = Temporality.CURRENT
        mention.experiencer = Experiencer.PATIENT
        mention.confidence = 0.95
        mention.created_at = datetime(2024, 1, 15, 10, 35, 0, tzinfo=timezone.utc)
        mention.concept_candidates = []
        return mention

    def test_mention_to_note_nlp_export_basic(self) -> None:
        """Test basic mention to NOTE_NLP export."""
        mention = self._create_mock_mention()
        nlp = mention_to_note_nlp_export(mention)

        assert isinstance(nlp, NoteNLPExport)
        assert nlp.snippet == "chest pain"
        assert nlp.offset == 25
        assert nlp.lexical_variant == "chest pain"
        assert nlp.nlp_date == date(2024, 1, 15)

    def test_mention_to_note_nlp_export_present_assertion(self) -> None:
        """Test present assertion maps to term_exists='Y'."""
        mention = self._create_mock_mention()
        mention.assertion = Assertion.PRESENT
        nlp = mention_to_note_nlp_export(mention)

        assert nlp.term_exists == "Y"

    def test_mention_to_note_nlp_export_absent_assertion(self) -> None:
        """Test absent/negated assertion maps to term_exists='N'.

        IMPORTANT: Negated findings must be preserved in OMOP export.
        """
        mention = self._create_mock_mention()
        mention.assertion = Assertion.ABSENT
        nlp = mention_to_note_nlp_export(mention)

        assert nlp.term_exists == "N"

    def test_mention_to_note_nlp_export_possible_assertion(self) -> None:
        """Test possible assertion maps to term_exists='Y'."""
        mention = self._create_mock_mention()
        mention.assertion = Assertion.POSSIBLE
        nlp = mention_to_note_nlp_export(mention)

        assert nlp.term_exists == "Y"

    def test_mention_to_note_nlp_export_current_temporality(self) -> None:
        """Test current temporality mapping."""
        mention = self._create_mock_mention()
        mention.temporality = Temporality.CURRENT
        nlp = mention_to_note_nlp_export(mention)

        assert nlp.term_temporal == "Current"

    def test_mention_to_note_nlp_export_past_temporality(self) -> None:
        """Test past temporality maps to Historical."""
        mention = self._create_mock_mention()
        mention.temporality = Temporality.PAST
        nlp = mention_to_note_nlp_export(mention)

        assert nlp.term_temporal == "Historical"

    def test_mention_to_note_nlp_export_future_temporality(self) -> None:
        """Test future temporality mapping."""
        mention = self._create_mock_mention()
        mention.temporality = Temporality.FUTURE
        nlp = mention_to_note_nlp_export(mention)

        assert nlp.term_temporal == "Future"

    def test_mention_to_note_nlp_export_term_modifiers(self) -> None:
        """Test term_modifiers includes experiencer and confidence."""
        mention = self._create_mock_mention()
        mention.experiencer = Experiencer.PATIENT
        mention.confidence = 0.85
        nlp = mention_to_note_nlp_export(mention)

        assert nlp.term_modifiers is not None
        assert "experiencer:patient" in nlp.term_modifiers
        assert "confidence:0.85" in nlp.term_modifiers

    def test_mention_to_note_nlp_export_with_concept_candidate(self) -> None:
        """Test mention export with concept candidate."""
        mention = self._create_mock_mention()

        # Create mock concept candidate
        candidate = MagicMock()
        candidate.omop_concept_id = 4087709
        candidate.rank = 1

        nlp = mention_to_note_nlp_export(mention, concept_candidate=candidate)

        assert nlp.note_nlp_concept_id == 4087709

    def test_mention_to_note_nlp_export_with_loaded_candidates(self) -> None:
        """Test mention export uses loaded concept_candidates."""
        mention = self._create_mock_mention()

        # Create mock concept candidates
        candidate1 = MagicMock()
        candidate1.omop_concept_id = 4087709
        candidate1.rank = 1

        candidate2 = MagicMock()
        candidate2.omop_concept_id = 123456
        candidate2.rank = 2

        mention.concept_candidates = [candidate2, candidate1]  # Out of order

        nlp = mention_to_note_nlp_export(mention)

        # Should use the top-ranked candidate
        assert nlp.note_nlp_concept_id == 4087709

    def test_mention_to_note_nlp_export_no_concept(self) -> None:
        """Test mention export with no concept defaults to 0."""
        mention = self._create_mock_mention()
        mention.concept_candidates = []

        nlp = mention_to_note_nlp_export(mention)

        assert nlp.note_nlp_concept_id == 0

    def test_mention_to_note_nlp_export_custom_note_id(self) -> None:
        """Test mention export with custom note_id."""
        mention = self._create_mock_mention()
        nlp = mention_to_note_nlp_export(mention, note_id=999999)

        assert nlp.note_id == 999999
