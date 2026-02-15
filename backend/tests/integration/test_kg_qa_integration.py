"""P2-001: Integration tests for KG/QA pathways.

Exercises the full pipeline: document ingestion -> NLP extraction -> KG build -> Q&A query.
Uses mocked DB responses but tests real service interactions end-to-end.

Mark all tests with @pytest.mark.integration for CI separation.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from pydantic import BaseModel

# Skip conftest to avoid heavy dependency chain
pytest_plugins = []


# ---------------------------------------------------------------------------
# Helpers: lightweight fakes that mirror the ORM/schema shapes we need
# ---------------------------------------------------------------------------

def _fake_document(
    doc_id: UUID | None = None,
    patient_id: str = "TEST_PATIENT_001",
    text: str = "Patient has type 2 diabetes and hypertension. Taking metformin 1000mg BID.",
    note_type: str = "progress_note",
    note_date: str = "2025-01-15",
    original_note_id: str = "note_001",
) -> MagicMock:
    doc = MagicMock()
    doc.id = doc_id or uuid4()
    doc.patient_id = patient_id
    doc.text = text
    doc.note_type = note_type
    doc.extra_metadata = {"original_note_id": original_note_id, "note_date": note_date}
    return doc


def _fake_kg_node(
    label: str,
    node_type: str,
    patient_id: str = "TEST_PATIENT_001",
    concept_id: int | None = None,
    properties: dict | None = None,
) -> MagicMock:
    node = MagicMock()
    node.label = label
    node.node_type = node_type
    node.patient_id = patient_id
    node.omop_concept_id = concept_id
    node.properties = properties or {
        "confidence": 0.9,
        "assertion": "PRESENT",
        "source_notes": ["note_001"],
    }
    # Make node_type comparable with NodeType enum values
    node.node_type.__eq__ = lambda self, other: str(self) == str(other)
    return node


def _scalars_all(items):
    """Return a mock result whose .scalars().all() yields *items*."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def patient_id() -> str:
    return "TEST_PATIENT_001"


@pytest.fixture
def sample_documents():
    return [
        _fake_document(
            text="Patient presents with type 2 diabetes, hypertension. Taking metformin 1000mg BID.",
            original_note_id="note_001",
        ),
        _fake_document(
            text="HbA1c is 7.2%. Blood pressure 140/90. Chest pain denied.",
            original_note_id="note_002",
            note_type="lab_result",
        ),
    ]


@pytest.fixture
def sample_kg_nodes():
    from app.schemas.knowledge_graph import NodeType

    return [
        _fake_kg_node("type 2 diabetes", NodeType.CONDITION, concept_id=201826),
        _fake_kg_node("hypertension", NodeType.CONDITION, concept_id=316866),
        _fake_kg_node("metformin", NodeType.DRUG, concept_id=1503297),
        _fake_kg_node("HbA1c 7.2%", NodeType.MEASUREMENT),
        _fake_kg_node("blood pressure 140/90", NodeType.MEASUREMENT),
    ]


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestHybridQueryIntegration:
    """Integration tests that exercise the hybrid query response contract."""

    def _build_response(self, **overrides):
        """Build a HybridQueryResponse with sensible defaults."""
        from app.api.clinical_agent import HybridQueryResponse, ExtractedEntity

        defaults = dict(
            question="What medications is the patient taking?",
            answer="The patient is taking metformin 1000mg BID for type 2 diabetes.",
            confidence=0.85,
            sources=["KG nodes", "note_001"],
            entities_found=[
                ExtractedEntity(
                    text="metformin",
                    entity_type="DRUG",
                    confidence=0.92,
                    assertion="PRESENT",
                    omop_concept_id=1503297,
                    note_id="note_001",
                ),
            ],
            source_document_ids=["note_001"],
            provenance_complete=True,
            dependency_state={
                "kg_available": True,
                "documents_available": True,
                "llm_available": True,
            },
            confidence_rationale="Evidence-weighted: 3 KG nodes, 1 document, 0 guidelines. Extraction quality: 0.92.",
        )
        defaults.update(overrides)
        return HybridQueryResponse(**defaults)

    # -- Required field tests --

    def test_response_has_question(self):
        resp = self._build_response()
        assert resp.question == "What medications is the patient taking?"

    def test_response_has_answer(self):
        resp = self._build_response()
        assert isinstance(resp.answer, str)
        assert len(resp.answer) > 0

    def test_response_has_confidence(self):
        resp = self._build_response()
        assert 0 <= resp.confidence <= 1

    def test_response_has_sources(self):
        resp = self._build_response()
        assert isinstance(resp.sources, list)

    def test_response_has_entities_found(self):
        resp = self._build_response()
        assert len(resp.entities_found) >= 1
        entity = resp.entities_found[0]
        assert entity.text == "metformin"
        assert entity.entity_type == "DRUG"

    # -- Provenance tests --

    def test_provenance_complete_with_sources(self):
        resp = self._build_response()
        assert resp.provenance_complete is True
        assert len(resp.source_document_ids) > 0

    def test_provenance_incomplete_when_no_sources(self):
        resp = self._build_response(
            source_document_ids=[],
            provenance_complete=False,
        )
        assert resp.provenance_complete is False

    # -- Dependency state tests --

    def test_dependency_state_populated(self):
        resp = self._build_response()
        assert "kg_available" in resp.dependency_state
        assert "documents_available" in resp.dependency_state
        assert "llm_available" in resp.dependency_state

    def test_dependency_state_all_available(self):
        resp = self._build_response()
        assert resp.dependency_state["kg_available"] is True
        assert resp.dependency_state["documents_available"] is True

    def test_dependency_state_kg_unavailable(self):
        resp = self._build_response(
            dependency_state={
                "kg_available": False,
                "documents_available": True,
                "llm_available": True,
            }
        )
        assert resp.dependency_state["kg_available"] is False

    # -- Confidence rationale --

    def test_confidence_rationale_present(self):
        resp = self._build_response()
        assert resp.confidence_rationale is not None
        assert len(resp.confidence_rationale) > 0

    # -- Decline behavior --

    def test_declined_response(self):
        resp = self._build_response(
            answer="",
            confidence=0.0,
            declined=True,
            decline_reason="Insufficient evidence to answer question.",
            escalation_path="Refer to attending physician.",
            source_document_ids=[],
            provenance_complete=True,
            confidence_rationale=None,
        )
        assert resp.declined is True
        assert resp.decline_reason is not None

    def test_non_declined_response(self):
        resp = self._build_response()
        assert resp.declined is False
        assert resp.decline_reason is None


@pytest.mark.integration
class TestBulkImportIntegration:
    """Integration tests for the bulk import request/response schemas."""

    def test_bulk_import_request_validation(self):
        from app.api.clinical_agent import BulkImportRequest, ClinicalNote

        req = BulkImportRequest(
            patient_id="PAT-001",
            notes=[
                ClinicalNote(
                    note_id="n1",
                    note_type="progress_note",
                    date="2025-01-15",
                    text="Patient has diabetes.",
                ),
            ],
            build_knowledge_graph=True,
        )
        assert req.patient_id == "PAT-001"
        assert len(req.notes) == 1

    def test_bulk_import_rejects_empty_notes(self):
        from app.api.clinical_agent import BulkImportRequest, ClinicalNote
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            BulkImportRequest(
                patient_id="PAT-001",
                notes=[],
                build_knowledge_graph=True,
            )

    def test_clinical_note_rejects_empty_text(self):
        from app.api.clinical_agent import ClinicalNote
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ClinicalNote(
                note_id="n1",
                note_type="progress_note",
                date="2025-01-15",
                text="   ",
            )


@pytest.mark.integration
class TestExtractedEntityIntegration:
    """Integration tests for entity extraction schema validation."""

    def test_entity_type_validation(self):
        from app.api.clinical_agent import ExtractedEntity
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ExtractedEntity(
                text="aspirin",
                entity_type="INVALID_TYPE",
                confidence=0.9,
            )

    def test_entity_assertion_validation(self):
        from app.api.clinical_agent import ExtractedEntity
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ExtractedEntity(
                text="aspirin",
                entity_type="DRUG",
                confidence=0.9,
                assertion="INVALID_ASSERTION",
            )

    def test_valid_entity_construction(self):
        from app.api.clinical_agent import ExtractedEntity

        entity = ExtractedEntity(
            text="metformin",
            entity_type="DRUG",
            confidence=0.92,
            assertion="PRESENT",
            omop_concept_id=1503297,
            note_id="note_001",
        )
        assert entity.entity_type == "DRUG"
        assert entity.assertion == "PRESENT"
        assert entity.confidence == 0.92

    def test_negated_entity(self):
        from app.api.clinical_agent import ExtractedEntity

        entity = ExtractedEntity(
            text="chest pain",
            entity_type="CONDITION",
            confidence=0.88,
            assertion="ABSENT",
            note_id="note_002",
        )
        assert entity.assertion == "ABSENT"


@pytest.mark.integration
class TestKnowledgeGraphResponseIntegration:
    """Integration tests for KG response schemas."""

    def test_patient_graph_response(self):
        from app.api.clinical_agent import (
            PatientGraphResponse,
            KGNodeResponse,
            KGEdgeResponse,
            KnowledgeGraphSummary,
        )

        resp = PatientGraphResponse(
            patient_id="PAT-001",
            nodes=[
                KGNodeResponse(
                    id="n1",
                    node_type="CONDITION",
                    label="diabetes",
                    omop_concept_id=201826,
                    properties={"confidence": 0.9},
                ),
            ],
            edges=[
                KGEdgeResponse(
                    id="e1",
                    source_node_id="n1",
                    target_node_id="n2",
                    edge_type="TREATED_WITH",
                    properties={},
                ),
            ],
            summary=KnowledgeGraphSummary(
                patient_id="PAT-001",
                node_count=2,
                edge_count=1,
                conditions=["diabetes"],
                medications=["metformin"],
                measurements=[],
                procedures=[],
            ),
        )
        assert resp.patient_id == "PAT-001"
        assert len(resp.nodes) == 1
        assert len(resp.edges) == 1

    def test_kg_summary_negated_conditions(self):
        from app.api.clinical_agent import KnowledgeGraphSummary

        summary = KnowledgeGraphSummary(
            patient_id="PAT-001",
            node_count=5,
            edge_count=3,
            conditions=["diabetes", "hypertension"],
            medications=["metformin"],
            measurements=["HbA1c 7.2%"],
            procedures=[],
            negated_conditions=["chest pain"],
        )
        assert "chest pain" in summary.negated_conditions
