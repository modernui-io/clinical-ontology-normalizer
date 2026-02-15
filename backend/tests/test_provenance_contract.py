"""P2-002: Contract tests for answer provenance completeness.

Contract: every non-empty clinical answer MUST have:
  - source_document_ids (non-empty list)
  - provenance_complete (boolean)
  - confidence > 0
  - confidence_rationale (non-empty string)

Declined answers have their own contract:
  - declined=True, decline_reason present

Tests validate the HybridQueryResponse schema directly (not through HTTP).
"""

from __future__ import annotations

import pytest

# Skip conftest to avoid heavy dependency chain
pytest_plugins = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_response(**overrides):
    """Build a HybridQueryResponse with minimal valid defaults."""
    from app.api.clinical_agent import HybridQueryResponse, ExtractedEntity

    defaults = dict(
        question="What conditions does the patient have?",
        answer="The patient has type 2 diabetes and hypertension.",
        confidence=0.87,
        sources=["KG nodes", "note_001"],
        entities_found=[
            ExtractedEntity(
                text="type 2 diabetes",
                entity_type="CONDITION",
                confidence=0.93,
                assertion="PRESENT",
                omop_concept_id=201826,
                note_id="note_001",
            ),
        ],
        source_document_ids=["note_001", "note_002"],
        provenance_complete=True,
        dependency_state={
            "kg_available": True,
            "documents_available": True,
            "llm_available": True,
        },
        confidence_rationale="Evidence-weighted: 5 KG nodes, 2 documents, 1 guideline.",
    )
    defaults.update(overrides)
    return HybridQueryResponse(**defaults)


# ---------------------------------------------------------------------------
# Full evidence contract (non-empty answer with complete provenance)
# ---------------------------------------------------------------------------


class TestFullEvidenceContract:
    """Contract: non-empty answer -> all provenance fields present."""

    def test_source_document_ids_non_empty(self):
        resp = _build_response()
        assert isinstance(resp.source_document_ids, list)
        assert len(resp.source_document_ids) > 0

    def test_provenance_complete_true(self):
        resp = _build_response()
        assert resp.provenance_complete is True

    def test_confidence_positive(self):
        resp = _build_response()
        assert resp.confidence > 0

    def test_confidence_rationale_non_empty(self):
        resp = _build_response()
        assert resp.confidence_rationale is not None
        assert len(resp.confidence_rationale.strip()) > 0

    def test_full_contract_satisfied(self):
        """All four provenance fields present together."""
        resp = _build_response()
        assert len(resp.source_document_ids) > 0
        assert resp.provenance_complete is True
        assert resp.confidence > 0
        assert resp.confidence_rationale and len(resp.confidence_rationale.strip()) > 0

    def test_multiple_source_documents(self):
        resp = _build_response(source_document_ids=["note_001", "note_002", "note_003"])
        assert len(resp.source_document_ids) == 3

    def test_high_confidence_answer(self):
        resp = _build_response(confidence=0.95, confidence_rationale="Strong multi-source evidence.")
        assert resp.confidence == 0.95
        assert "Strong" in resp.confidence_rationale

    def test_entities_have_note_ids(self):
        """Every entity in a full-evidence response should reference a source note."""
        resp = _build_response()
        for entity in resp.entities_found:
            assert entity.note_id is not None


# ---------------------------------------------------------------------------
# Partial evidence contract (answer with incomplete provenance)
# ---------------------------------------------------------------------------


class TestPartialEvidenceContract:
    """Contract: partial evidence -> provenance_complete=False, source_document_ids may be partial."""

    def test_provenance_incomplete_flag(self):
        resp = _build_response(
            provenance_complete=False,
            confidence_rationale="Partial evidence: only KG nodes available, no document text.",
        )
        assert resp.provenance_complete is False

    def test_partial_source_documents(self):
        resp = _build_response(
            source_document_ids=["note_001"],
            provenance_complete=False,
            confidence_rationale="Partial evidence: 1 of 3 sources available.",
        )
        assert len(resp.source_document_ids) == 1
        assert resp.provenance_complete is False

    def test_low_confidence_with_partial_evidence(self):
        resp = _build_response(
            confidence=0.35,
            provenance_complete=False,
            confidence_rationale="Low confidence: limited evidence sources.",
        )
        assert resp.confidence < 0.5
        assert resp.provenance_complete is False

    def test_empty_sources_provenance_incomplete(self):
        """Empty source_document_ids with non-empty answer -> provenance_complete=False."""
        resp = _build_response(
            source_document_ids=[],
            provenance_complete=False,
            confidence_rationale="No source documents found despite answer generation.",
        )
        assert len(resp.source_document_ids) == 0
        assert resp.provenance_complete is False

    def test_partial_with_confidence_rationale(self):
        resp = _build_response(
            provenance_complete=False,
            confidence_rationale="Based on KG only; documents unavailable.",
        )
        assert resp.confidence_rationale is not None
        assert len(resp.confidence_rationale) > 0


# ---------------------------------------------------------------------------
# Declined answer contract
# ---------------------------------------------------------------------------


class TestDeclinedAnswerContract:
    """Contract: declined answer -> declined=True, decline_reason present."""

    def test_declined_flag_true(self):
        resp = _build_response(
            answer="",
            confidence=0.0,
            declined=True,
            decline_reason="Insufficient evidence to provide a clinical answer.",
            source_document_ids=[],
            provenance_complete=True,
            confidence_rationale=None,
        )
        assert resp.declined is True

    def test_decline_reason_present(self):
        resp = _build_response(
            answer="",
            confidence=0.0,
            declined=True,
            decline_reason="No relevant data found for this patient.",
            source_document_ids=[],
            provenance_complete=True,
            confidence_rationale=None,
        )
        assert resp.decline_reason is not None
        assert len(resp.decline_reason) > 0

    def test_declined_with_escalation_path(self):
        resp = _build_response(
            answer="",
            confidence=0.0,
            declined=True,
            decline_reason="Unable to determine with available data.",
            escalation_path="Refer to attending physician for clinical review.",
            source_document_ids=[],
            provenance_complete=True,
            confidence_rationale=None,
        )
        assert resp.escalation_path is not None
        assert "physician" in resp.escalation_path.lower()

    def test_declined_empty_answer(self):
        resp = _build_response(
            answer="",
            confidence=0.0,
            declined=True,
            decline_reason="Insufficient evidence.",
            source_document_ids=[],
            provenance_complete=True,
            confidence_rationale=None,
        )
        assert resp.answer == ""

    def test_declined_zero_confidence(self):
        resp = _build_response(
            answer="",
            confidence=0.0,
            declined=True,
            decline_reason="No data.",
            source_document_ids=[],
            provenance_complete=True,
            confidence_rationale=None,
        )
        assert resp.confidence == 0.0


# ---------------------------------------------------------------------------
# Dependency state contract
# ---------------------------------------------------------------------------


class TestDependencyStateContract:
    """Contract: dependency_state always populated with boolean availability flags."""

    def test_dependency_state_is_dict(self):
        resp = _build_response()
        assert isinstance(resp.dependency_state, dict)

    def test_dependency_state_has_kg_flag(self):
        resp = _build_response()
        assert "kg_available" in resp.dependency_state
        assert isinstance(resp.dependency_state["kg_available"], bool)

    def test_dependency_state_has_documents_flag(self):
        resp = _build_response()
        assert "documents_available" in resp.dependency_state
        assert isinstance(resp.dependency_state["documents_available"], bool)

    def test_dependency_state_has_llm_flag(self):
        resp = _build_response()
        assert "llm_available" in resp.dependency_state
        assert isinstance(resp.dependency_state["llm_available"], bool)

    def test_degraded_kg_unavailable(self):
        resp = _build_response(
            dependency_state={
                "kg_available": False,
                "documents_available": True,
                "llm_available": True,
            },
        )
        assert resp.dependency_state["kg_available"] is False

    def test_degraded_documents_unavailable(self):
        resp = _build_response(
            dependency_state={
                "kg_available": True,
                "documents_available": False,
                "llm_available": True,
            },
        )
        assert resp.dependency_state["documents_available"] is False

    def test_degraded_llm_unavailable(self):
        resp = _build_response(
            dependency_state={
                "kg_available": True,
                "documents_available": True,
                "llm_available": False,
            },
        )
        assert resp.dependency_state["llm_available"] is False


# ---------------------------------------------------------------------------
# Evidence source contract
# ---------------------------------------------------------------------------


class TestEvidenceSourceContract:
    """Contract: evidence sources have required fields."""

    def test_evidence_source_fields(self):
        from app.api.clinical_agent import EvidenceSource

        ev = EvidenceSource(
            note_id="note_001",
            note_type="progress_note",
            note_date="2025-01-15",
            excerpt="Patient has type 2 diabetes...",
            relevance_score=0.85,
        )
        assert ev.note_id == "note_001"
        assert ev.note_type == "progress_note"
        assert 0 <= ev.relevance_score <= 1

    def test_evidence_in_response(self):
        from app.api.clinical_agent import EvidenceSource

        resp = _build_response(
            evidence=[
                EvidenceSource(
                    note_id="note_001",
                    note_type="progress_note",
                    note_date="2025-01-15",
                    excerpt="Patient has diabetes.",
                    relevance_score=0.9,
                ),
            ],
        )
        assert len(resp.evidence) == 1
        assert resp.evidence[0].relevance_score > 0


# ---------------------------------------------------------------------------
# Confidence breakdown contract (P1-002)
# ---------------------------------------------------------------------------


class TestConfidenceBreakdownContract:
    """Contract: confidence_breakdown, when present, is well-formed."""

    def test_no_breakdown_is_valid(self):
        resp = _build_response(confidence_breakdown=None)
        assert resp.confidence_breakdown is None

    def test_breakdown_present(self):
        from app.schemas.confidence_semantics import (
            ConfidenceBreakdown,
            ConfidenceComponent,
            ConfidenceSource,
        )

        breakdown = ConfidenceBreakdown(
            aggregate_score=0.87,
            components=[
                ConfidenceComponent(
                    source=ConfidenceSource.KG,
                    score=0.90,
                    weight=0.4,
                    method="entity_count_heuristic",
                ),
                ConfidenceComponent(
                    source=ConfidenceSource.EXTRACTION,
                    score=0.85,
                    weight=0.35,
                    method="extraction_quality",
                ),
            ],
        )
        resp = _build_response(confidence_breakdown=breakdown)
        assert resp.confidence_breakdown is not None
        assert resp.confidence_breakdown.aggregate_score == 0.87
        assert len(resp.confidence_breakdown.components) == 2


# ---------------------------------------------------------------------------
# Fallback indicator contract (P1-019)
# ---------------------------------------------------------------------------


class TestFallbackIndicatorContract:
    """Contract: fallback fields present in degraded responses."""

    def test_no_fallback_by_default(self):
        resp = _build_response()
        assert resp.fallback_used is False
        assert resp.fallback_reason_code is None

    def test_fallback_with_reason(self):
        resp = _build_response(
            fallback_used=True,
            fallback_reason_code="llm_unavailable",
        )
        assert resp.fallback_used is True
        assert resp.fallback_reason_code == "llm_unavailable"
