"""Tests for P1-001/002/005/006/019: Clinical response enrichment fields.

Covers:
- P1-001: Evidence-weighted confidence with rationale
- P1-002: Standardized confidence semantics schema
- P1-005: Note processing coverage metrics
- P1-006: Data freshness and ingestion timestamp
- P1-019: Fallback indicator for degraded responses
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.api.clinical_agent import (
    HybridQueryResponse,
    compute_evidence_weighted_confidence,
)
from app.schemas.confidence_semantics import (
    ConfidenceBreakdown,
    ConfidenceComponent,
    ConfidenceSource,
)


# ---------------------------------------------------------------------------
# Helpers: build a minimal valid HybridQueryResponse
# ---------------------------------------------------------------------------

def _minimal_response(**overrides) -> HybridQueryResponse:
    """Return a HybridQueryResponse with all required fields and any overrides."""
    defaults = {
        "question": "What medications is the patient taking?",
        "answer": "The patient is taking metformin.",
        "confidence": 0.85,
        "sources": ["Document: note-1"],
        "entities_found": [],
    }
    defaults.update(overrides)
    return HybridQueryResponse(**defaults)


# =============================================================================
# P1-001: Evidence-weighted confidence with rationale
# =============================================================================

class TestP1001EvidenceWeightedConfidence:
    """P1-001: compute_evidence_weighted_confidence helper and rationale field."""

    def test_compute_returns_tuple(self):
        score, rationale = compute_evidence_weighted_confidence(
            kg_node_count=5,
            document_count=3,
            guideline_count=2,
            extraction_quality=0.8,
        )
        assert isinstance(score, float)
        assert isinstance(rationale, str)

    def test_score_in_valid_range(self):
        score, _ = compute_evidence_weighted_confidence(
            kg_node_count=100,
            document_count=50,
            guideline_count=20,
            extraction_quality=1.0,
            graph_path_count=50,
            consensus_strong_count=10,
            calculator_count=10,
        )
        assert 0.0 <= score <= 0.95

    def test_zero_evidence_gives_base_score(self):
        score, _ = compute_evidence_weighted_confidence(
            kg_node_count=0,
            document_count=0,
            guideline_count=0,
            extraction_quality=0.0,
        )
        # With all zeros the weighted sum is 0, so score = 0.4
        assert score == pytest.approx(0.4, abs=0.01)

    def test_rationale_contains_component_labels(self):
        _, rationale = compute_evidence_weighted_confidence(
            kg_node_count=3,
            document_count=2,
            guideline_count=1,
            extraction_quality=0.9,
        )
        assert "evidence_weighted:" in rationale
        assert "KG nodes" in rationale
        assert "documents" in rationale
        assert "guidelines" in rationale
        assert "extraction quality" in rationale

    def test_rationale_includes_optional_parts(self):
        _, rationale = compute_evidence_weighted_confidence(
            kg_node_count=1,
            document_count=1,
            guideline_count=1,
            extraction_quality=0.5,
            graph_path_count=3,
            consensus_strong_count=2,
            calculator_count=1,
        )
        assert "graph paths" in rationale
        assert "strong consensus" in rationale
        assert "calculators" in rationale

    def test_rationale_omits_zero_optional_parts(self):
        _, rationale = compute_evidence_weighted_confidence(
            kg_node_count=1,
            document_count=1,
            guideline_count=1,
            extraction_quality=0.5,
            graph_path_count=0,
            consensus_strong_count=0,
            calculator_count=0,
        )
        assert "graph paths" not in rationale
        assert "strong consensus" not in rationale
        assert "calculators" not in rationale

    def test_more_evidence_yields_higher_score(self):
        low_score, _ = compute_evidence_weighted_confidence(
            kg_node_count=1,
            document_count=0,
            guideline_count=0,
            extraction_quality=0.3,
        )
        high_score, _ = compute_evidence_weighted_confidence(
            kg_node_count=10,
            document_count=5,
            guideline_count=3,
            extraction_quality=0.9,
            graph_path_count=5,
        )
        assert high_score > low_score

    def test_response_confidence_rationale_field_default(self):
        resp = _minimal_response()
        assert resp.confidence_rationale is None

    def test_response_confidence_rationale_field_set(self):
        resp = _minimal_response(confidence_rationale="evidence_weighted: 3 KG nodes (0.25)")
        assert resp.confidence_rationale == "evidence_weighted: 3 KG nodes (0.25)"


# =============================================================================
# P1-002: Standardized confidence semantics
# =============================================================================

class TestP1002ConfidenceSemantics:
    """P1-002: ConfidenceComponent, ConfidenceBreakdown, and response field."""

    def test_confidence_component_valid(self):
        comp = ConfidenceComponent(
            source=ConfidenceSource.EXTRACTION,
            score=0.75,
            weight=0.3,
            method="entity_count_heuristic",
        )
        assert comp.source == ConfidenceSource.EXTRACTION
        assert comp.score == 0.75
        assert comp.weight == 0.3
        assert comp.method == "entity_count_heuristic"

    def test_confidence_component_rejects_out_of_range_score(self):
        with pytest.raises(ValidationError):
            ConfidenceComponent(
                source=ConfidenceSource.KG,
                score=1.5,
                weight=0.3,
                method="test",
            )

    def test_confidence_component_rejects_negative_weight(self):
        with pytest.raises(ValidationError):
            ConfidenceComponent(
                source=ConfidenceSource.KG,
                score=0.5,
                weight=-0.1,
                method="test",
            )

    def test_confidence_breakdown_valid(self):
        bd = ConfidenceBreakdown(
            components=[
                ConfidenceComponent(
                    source=ConfidenceSource.EXTRACTION,
                    score=0.6,
                    weight=0.25,
                    method="entity_count",
                ),
                ConfidenceComponent(
                    source=ConfidenceSource.KG,
                    score=0.8,
                    weight=0.25,
                    method="graph_paths",
                ),
            ],
            aggregate_score=0.7,
            aggregate_method="weighted_mean",
        )
        assert len(bd.components) == 2
        assert bd.aggregate_score == 0.7
        assert bd.aggregate_method == "weighted_mean"

    def test_confidence_breakdown_default_method(self):
        bd = ConfidenceBreakdown(
            components=[],
            aggregate_score=0.5,
        )
        assert bd.aggregate_method == "weighted_mean"

    def test_confidence_source_enum_values(self):
        assert ConfidenceSource.EXTRACTION.value == "extraction"
        assert ConfidenceSource.KG.value == "kg"
        assert ConfidenceSource.REASONING.value == "reasoning"
        assert ConfidenceSource.FINAL.value == "final"

    def test_response_confidence_breakdown_default_none(self):
        resp = _minimal_response()
        assert resp.confidence_breakdown is None

    def test_response_confidence_breakdown_populated(self):
        bd = ConfidenceBreakdown(
            components=[
                ConfidenceComponent(
                    source=ConfidenceSource.EXTRACTION,
                    score=0.6,
                    weight=0.25,
                    method="entity_count",
                ),
            ],
            aggregate_score=0.6,
        )
        resp = _minimal_response(confidence_breakdown=bd)
        assert resp.confidence_breakdown is not None
        assert len(resp.confidence_breakdown.components) == 1
        assert resp.confidence_breakdown.aggregate_score == 0.6


# =============================================================================
# P1-005: Note processing coverage metrics
# =============================================================================

class TestP1005CoverageMetrics:
    """P1-005: notes_processed, notes_failed, coverage_percent."""

    def test_defaults(self):
        resp = _minimal_response()
        assert resp.notes_processed == 0
        assert resp.notes_failed == 0
        assert resp.coverage_percent == 100.0

    def test_custom_values(self):
        resp = _minimal_response(
            notes_processed=8,
            notes_failed=2,
            coverage_percent=80.0,
        )
        assert resp.notes_processed == 8
        assert resp.notes_failed == 2
        assert resp.coverage_percent == 80.0

    def test_all_failed(self):
        resp = _minimal_response(
            notes_processed=0,
            notes_failed=5,
            coverage_percent=0.0,
        )
        assert resp.notes_processed == 0
        assert resp.notes_failed == 5
        assert resp.coverage_percent == 0.0

    def test_types(self):
        resp = _minimal_response(
            notes_processed=10,
            notes_failed=0,
            coverage_percent=100.0,
        )
        assert isinstance(resp.notes_processed, int)
        assert isinstance(resp.notes_failed, int)
        assert isinstance(resp.coverage_percent, float)


# =============================================================================
# P1-006: Data freshness and ingestion timestamp
# =============================================================================

class TestP1006DataFreshness:
    """P1-006: data_freshness_iso, last_ingestion_ts."""

    def test_defaults_none(self):
        resp = _minimal_response()
        assert resp.data_freshness_iso is None
        assert resp.last_ingestion_ts is None

    def test_with_iso_timestamps(self):
        ts = "2026-02-15T10:30:00+00:00"
        resp = _minimal_response(
            data_freshness_iso=ts,
            last_ingestion_ts=ts,
        )
        assert resp.data_freshness_iso == ts
        assert resp.last_ingestion_ts == ts

    def test_types(self):
        resp = _minimal_response(
            data_freshness_iso="2026-01-01T00:00:00Z",
            last_ingestion_ts="2026-01-01T00:00:00Z",
        )
        assert isinstance(resp.data_freshness_iso, str)
        assert isinstance(resp.last_ingestion_ts, str)

    def test_independent_values(self):
        resp = _minimal_response(
            data_freshness_iso="2026-02-15T10:00:00Z",
            last_ingestion_ts="2026-02-14T08:00:00Z",
        )
        assert resp.data_freshness_iso != resp.last_ingestion_ts


# =============================================================================
# P1-019: Fallback used and reason code
# =============================================================================

class TestP1019FallbackIndicator:
    """P1-019: fallback_used, fallback_reason_code."""

    def test_defaults(self):
        resp = _minimal_response()
        assert resp.fallback_used is False
        assert resp.fallback_reason_code is None

    def test_fallback_set(self):
        resp = _minimal_response(
            fallback_used=True,
            fallback_reason_code="llm_unavailable",
        )
        assert resp.fallback_used is True
        assert resp.fallback_reason_code == "llm_unavailable"

    def test_fallback_reason_without_flag(self):
        """Reason code can technically be set without fallback_used for flexibility."""
        resp = _minimal_response(
            fallback_used=False,
            fallback_reason_code="partial_degradation",
        )
        assert resp.fallback_used is False
        assert resp.fallback_reason_code == "partial_degradation"

    def test_types(self):
        resp = _minimal_response(
            fallback_used=True,
            fallback_reason_code="llm_timeout",
        )
        assert isinstance(resp.fallback_used, bool)
        assert isinstance(resp.fallback_reason_code, str)


# =============================================================================
# Integration: all P1 fields coexist with existing P0 fields
# =============================================================================

class TestAllFieldsCoexist:
    """Verify all new P1 fields coexist with existing P0 fields."""

    def test_full_response_with_all_fields(self):
        bd = ConfidenceBreakdown(
            components=[
                ConfidenceComponent(
                    source=ConfidenceSource.EXTRACTION,
                    score=0.5,
                    weight=0.25,
                    method="test",
                ),
            ],
            aggregate_score=0.85,
        )
        resp = _minimal_response(
            # Existing P0 fields
            declined=False,
            decline_reason=None,
            escalation_path=None,
            source_document_ids=["doc-1"],
            provenance_complete=True,
            dependency_state={"kg_available": True, "documents_available": True, "llm_available": True},
            action_gate={"action": "recommend", "confidence_threshold": 0.7, "allowed": True},
            # P1-001
            confidence_rationale="evidence_weighted: 5 KG nodes (0.25), 3 documents (0.25)",
            # P1-002
            confidence_breakdown=bd,
            # P1-005
            notes_processed=10,
            notes_failed=1,
            coverage_percent=90.91,
            # P1-006
            data_freshness_iso="2026-02-15T12:00:00Z",
            last_ingestion_ts="2026-02-15T12:00:00Z",
            # P1-019
            fallback_used=False,
            fallback_reason_code=None,
        )
        # Spot-check all P1 fields
        assert resp.confidence_rationale is not None
        assert resp.confidence_breakdown is not None
        assert resp.notes_processed == 10
        assert resp.notes_failed == 1
        assert resp.coverage_percent == 90.91
        assert resp.data_freshness_iso is not None
        assert resp.last_ingestion_ts is not None
        assert resp.fallback_used is False
        assert resp.fallback_reason_code is None

        # Spot-check P0 fields still work
        assert resp.declined is False
        assert resp.provenance_complete is True
        assert resp.action_gate is not None

    def test_serialization_roundtrip(self):
        """Ensure the model can serialize to dict and back."""
        resp = _minimal_response(
            confidence_rationale="test rationale",
            notes_processed=5,
            notes_failed=0,
            coverage_percent=100.0,
            fallback_used=True,
            fallback_reason_code="llm_unavailable",
        )
        data = resp.model_dump()
        assert data["confidence_rationale"] == "test rationale"
        assert data["notes_processed"] == 5
        assert data["fallback_used"] is True
        assert data["fallback_reason_code"] == "llm_unavailable"

        # Roundtrip
        resp2 = HybridQueryResponse(**data)
        assert resp2.confidence_rationale == resp.confidence_rationale
        assert resp2.fallback_used == resp.fallback_used
