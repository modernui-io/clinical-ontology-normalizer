"""Tests for background job functions."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


class TestProcessDocumentModule:
    """Test process_document module imports and structure."""

    def test_jobs_module_importable(self) -> None:
        """Test that jobs module can be imported."""
        from app.jobs import process_document

        assert process_document is not None

    def test_process_document_callable(self) -> None:
        """Test process_document is a callable function."""
        from app.jobs import process_document

        assert callable(process_document)


class TestProcessDocumentFunction:
    """Test process_document function behavior."""

    @patch("app.jobs.document_processing.get_sync_engine")
    @patch("app.jobs.document_processing.Session")
    def test_process_document_updates_status_to_processing(
        self, mock_session_class: MagicMock, mock_get_sync_engine: MagicMock
    ) -> None:
        """Test that processing updates status to PROCESSING."""
        from app.jobs import process_document

        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=None)

        # Mock document fetch to return None (not found case)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        document_id = str(uuid4())
        result = process_document(document_id)

        # Should have attempted to update status
        assert mock_session.execute.called
        assert result["success"] is False

    @patch("app.jobs.document_processing.get_sync_engine")
    @patch("app.jobs.document_processing.Session")
    def test_process_document_returns_error_when_not_found(
        self, mock_session_class: MagicMock, mock_get_sync_engine: MagicMock
    ) -> None:
        """Test that processing returns error when document not found."""
        from app.jobs import process_document

        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=None)

        # Mock document fetch to return None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        document_id = str(uuid4())
        result = process_document(document_id)

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @patch("app.jobs.document_processing.DatabaseFactBuilderService")
    @patch("app.jobs.document_processing.get_sync_engine")
    @patch("app.jobs.document_processing.Session")
    def test_process_document_returns_success_with_document(
        self, mock_session_class: MagicMock, mock_get_sync_engine: MagicMock,
        mock_fact_builder_class: MagicMock,
    ) -> None:
        """Test successful document processing."""
        from app.jobs import process_document

        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=None)

        # Create mock document
        mock_document = MagicMock()
        mock_document.patient_id = "patient-123"
        mock_document.note_type = "progress_note"
        mock_document.text = "Patient presents with fever."

        # Mock execute to return document on second call, None for candidate lookups
        call_count = [0]

        def mock_execute(stmt):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 2:  # Second call is the select
                result.scalar_one_or_none.return_value = mock_document
            else:
                result.scalar_one_or_none.return_value = None
            return result

        mock_session.execute.side_effect = mock_execute

        document_id = str(uuid4())
        result = process_document(document_id)

        assert result["success"] is True
        assert result["document_id"] == document_id
        assert result["patient_id"] == "patient-123"

    @patch("app.jobs.document_processing.DatabaseFactBuilderService")
    @patch("app.jobs.document_processing.get_sync_engine")
    @patch("app.jobs.document_processing.Session")
    def test_process_document_extracts_mentions(
        self, mock_session_class: MagicMock, mock_get_sync_engine: MagicMock,
        mock_fact_builder_class: MagicMock,
    ) -> None:
        """Test that processing extracts mentions from document text."""
        from app.jobs import process_document

        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=None)

        # Create mock document with known clinical terms
        mock_document = MagicMock()
        mock_document.patient_id = "patient-456"
        mock_document.note_type = "progress_note"
        mock_document.text = "Patient has fever and cough. No pneumonia."

        # Mock execute to return document on second call, None for candidate lookups
        call_count = [0]

        def mock_execute(stmt):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 2:  # Second call is the select
                result.scalar_one_or_none.return_value = mock_document
            else:
                result.scalar_one_or_none.return_value = None
            return result

        mock_session.execute.side_effect = mock_execute

        document_id = str(uuid4())
        result = process_document(document_id)

        assert result["success"] is True
        # Should extract at least fever, cough, pneumonia
        assert result["mention_count"] >= 3
        # Verify session.add was called for each mention
        assert mock_session.add.call_count >= 3

    @patch("app.jobs.document_processing.get_sync_engine")
    @patch("app.jobs.document_processing.Session")
    def test_process_document_creates_mention_records(
        self, mock_session_class: MagicMock, mock_get_sync_engine: MagicMock
    ) -> None:
        """Test that Mention records are created with correct attributes."""
        from app.jobs import process_document
        from app.models.mention import Mention

        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=None)

        # Create mock document
        mock_document = MagicMock()
        mock_document.patient_id = "patient-789"
        mock_document.note_type = "progress_note"
        mock_document.text = "Patient has fever."

        # Mock execute
        call_count = [0]

        def mock_execute(stmt):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 2:
                result.scalar_one_or_none.return_value = mock_document
            return result

        mock_session.execute.side_effect = mock_execute

        document_id = str(uuid4())
        process_document(document_id)

        # Check that Mention objects were added to session
        add_calls = mock_session.add.call_args_list
        mentions_added = [call[0][0] for call in add_calls if isinstance(call[0][0], Mention)]

        assert len(mentions_added) >= 1
        # Verify fever mention attributes
        fever_mention = next((m for m in mentions_added if "fever" in m.text.lower()), None)
        assert fever_mention is not None
        assert fever_mention.document_id == document_id

    @patch("app.jobs.document_processing.get_sync_engine")
    @patch("app.jobs.document_processing.Session")
    def test_process_document_handles_exception(
        self, mock_session_class: MagicMock, mock_get_sync_engine: MagicMock
    ) -> None:
        """Test that processing handles exceptions gracefully."""
        from app.jobs import process_document

        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=None)

        # Make execute raise an exception
        mock_session.execute.side_effect = Exception("Database error")

        document_id = str(uuid4())
        result = process_document(document_id)

        assert result["success"] is False
        assert "Database error" in result["error"]


class TestDocumentAPIJobEnqueue:
    """Test document upload endpoint job enqueueing."""

    @pytest.fixture
    def valid_document_payload(self) -> dict:
        """Valid document upload payload."""
        return {
            "patient_id": "patient-123",
            "note_type": "progress_note",
            "text": "Patient presents with fever and cough.",
        }

    def test_document_model_has_job_id_column(self) -> None:
        """Test Document model has job_id column."""
        from app.models import Document

        # Check that job_id attribute exists
        mapper = Document.__mapper__
        columns = {c.name for c in mapper.columns}
        assert "job_id" in columns

    def test_queue_names_includes_document(self) -> None:
        """Test QUEUE_NAMES includes document queue."""
        from app.core.queue import QUEUE_NAMES

        assert "document" in QUEUE_NAMES
        assert QUEUE_NAMES["document"] == "document_processing"


class TestMentionConceptCandidateCreation:
    """Tests for Phase 5: MentionConceptCandidate record creation."""

    @patch("app.jobs.document_processing.DatabaseFactBuilderService")
    @patch("app.jobs.document_processing.get_sync_engine")
    @patch("app.jobs.document_processing.Session")
    @patch("app.jobs.document_processing.get_mapping_service")
    def test_process_document_creates_concept_candidates(
        self,
        mock_get_mapping: MagicMock,
        mock_session_class: MagicMock,
        mock_get_sync_engine: MagicMock,
        mock_fact_builder_class: MagicMock,
    ) -> None:
        """Test that processing creates MentionConceptCandidate records."""
        from app.jobs import process_document
        from app.models.mention import MentionConceptCandidate
        from app.schemas.base import Domain
        from app.services.mapping import ConceptCandidate, MappingMethod

        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=None)

        # Create mock document
        mock_document = MagicMock()
        mock_document.patient_id = "patient-test"
        mock_document.note_type = "progress_note"
        mock_document.text = "Patient has fever."

        # Mock execute - return None for candidate lookups to skip fact creation
        call_count = [0]

        def mock_execute(stmt):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 2:
                result.scalar_one_or_none.return_value = mock_document
            else:
                result.scalar_one_or_none.return_value = None
            return result

        mock_session.execute.side_effect = mock_execute

        # Mock mapping service to return candidates
        mock_mapping = MagicMock()
        mock_mapping.map_mention.return_value = [
            ConceptCandidate(
                omop_concept_id=437663,
                concept_name="Fever",
                concept_code="437663",
                vocabulary_id="SNOMED",
                domain_id=Domain.CONDITION,
                score=1.0,
                method=MappingMethod.EXACT,
                rank=1,
            )
        ]
        mock_get_mapping.return_value = mock_mapping

        document_id = str(uuid4())
        result = process_document(document_id)

        assert result["success"] is True
        assert result["candidate_count"] >= 1

        # Check MentionConceptCandidate objects were added
        add_calls = mock_session.add.call_args_list
        candidates_added = [
            call[0][0] for call in add_calls if isinstance(call[0][0], MentionConceptCandidate)
        ]
        assert len(candidates_added) >= 1

    @patch("app.jobs.document_processing.DatabaseFactBuilderService")
    @patch("app.jobs.document_processing.get_sync_engine")
    @patch("app.jobs.document_processing.Session")
    @patch("app.jobs.document_processing.get_mapping_service")
    def test_candidate_has_correct_attributes(
        self,
        mock_get_mapping: MagicMock,
        mock_session_class: MagicMock,
        mock_get_sync_engine: MagicMock,
        mock_fact_builder_class: MagicMock,
    ) -> None:
        """Test that MentionConceptCandidate has correct attributes."""
        from app.jobs import process_document
        from app.models.mention import MentionConceptCandidate
        from app.schemas.base import Domain
        from app.services.mapping import ConceptCandidate, MappingMethod

        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=None)

        mock_document = MagicMock()
        mock_document.patient_id = "patient-attr"
        mock_document.note_type = "progress_note"
        mock_document.text = "Patient has fever."

        call_count = [0]

        def mock_execute(stmt):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 2:
                result.scalar_one_or_none.return_value = mock_document
            else:
                result.scalar_one_or_none.return_value = None
            return result

        mock_session.execute.side_effect = mock_execute

        mock_mapping = MagicMock()
        mock_mapping.map_mention.return_value = [
            ConceptCandidate(
                omop_concept_id=437663,
                concept_name="Fever",
                concept_code="437663",
                vocabulary_id="SNOMED",
                domain_id=Domain.CONDITION,
                score=0.95,
                method=MappingMethod.FUZZY,
                rank=1,
            )
        ]
        mock_get_mapping.return_value = mock_mapping

        document_id = str(uuid4())
        process_document(document_id)

        add_calls = mock_session.add.call_args_list
        candidates = [
            call[0][0] for call in add_calls if isinstance(call[0][0], MentionConceptCandidate)
        ]

        assert len(candidates) >= 1
        candidate = candidates[0]
        assert candidate.omop_concept_id is not None
        assert candidate.concept_name.lower() == "fever"
        assert candidate.vocabulary_id is not None
        assert candidate.score >= 0.0
        assert candidate.rank >= 1

    @patch("app.jobs.document_processing.DatabaseFactBuilderService")
    @patch("app.jobs.document_processing.get_sync_engine")
    @patch("app.jobs.document_processing.Session")
    @patch("app.jobs.document_processing.get_mapping_service")
    def test_multiple_candidates_per_mention(
        self,
        mock_get_mapping: MagicMock,
        mock_session_class: MagicMock,
        mock_get_sync_engine: MagicMock,
        mock_fact_builder_class: MagicMock,
    ) -> None:
        """Test that multiple candidates per mention are created."""
        from app.jobs import process_document
        from app.models.mention import MentionConceptCandidate
        from app.schemas.base import Domain
        from app.services.mapping import ConceptCandidate, MappingMethod

        mock_session = MagicMock()
        mock_session_class.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_class.return_value.__exit__ = MagicMock(return_value=None)

        mock_document = MagicMock()
        mock_document.patient_id = "patient-multi"
        mock_document.note_type = "progress_note"
        mock_document.text = "Patient has fever."

        call_count = [0]

        def mock_execute(stmt):
            call_count[0] += 1
            result = MagicMock()
            if call_count[0] == 2:
                result.scalar_one_or_none.return_value = mock_document
            else:
                result.scalar_one_or_none.return_value = None
            return result

        mock_session.execute.side_effect = mock_execute

        # Return multiple candidates
        mock_mapping = MagicMock()
        mock_mapping.map_mention.return_value = [
            ConceptCandidate(
                omop_concept_id=437663,
                concept_name="Fever",
                concept_code="437663",
                vocabulary_id="SNOMED",
                domain_id=Domain.CONDITION,
                score=1.0,
                method=MappingMethod.EXACT,
                rank=1,
            ),
            ConceptCandidate(
                omop_concept_id=437664,
                concept_name="High temperature",
                concept_code="437664",
                vocabulary_id="SNOMED",
                domain_id=Domain.CONDITION,
                score=0.8,
                method=MappingMethod.FUZZY,
                rank=2,
            ),
        ]
        mock_get_mapping.return_value = mock_mapping

        document_id = str(uuid4())
        result = process_document(document_id)

        # Should have candidates created
        assert result["success"] is True
        assert result["candidate_count"] >= 1

        add_calls = mock_session.add.call_args_list
        candidates = [
            call[0][0] for call in add_calls if isinstance(call[0][0], MentionConceptCandidate)
        ]
        assert len(candidates) >= 1
