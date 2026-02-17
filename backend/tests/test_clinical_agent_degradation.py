"""Tests for Phase 1 Safety Envelope: HybridQueryResponse degradation field."""

from __future__ import annotations

import pytest

from app.schemas.degradation import DegradationMetadata


class TestHybridQueryResponseDegradation:
    """Test that HybridQueryResponse includes degradation metadata."""

    def test_response_model_has_degradation_field(self):
        from app.api.clinical_agent import HybridQueryResponse

        fields = HybridQueryResponse.model_fields
        assert "degradation" in fields, "HybridQueryResponse must have a 'degradation' field"

    def test_degradation_field_is_optional(self):
        from app.api.clinical_agent import HybridQueryResponse

        response = HybridQueryResponse(
            question="test question",
            answer="test answer",
            confidence=0.5,
            sources=["test"],
            entities_found=[],
        )
        assert response.degradation is None

    def test_degradation_field_accepts_metadata(self):
        from app.api.clinical_agent import HybridQueryResponse

        meta = DegradationMetadata(
            degraded=True,
            degraded_components=["guideline_rag"],
            fallback_used=True,
            warnings=["guideline_rag: ConnectionError: timeout"],
            trace_id="req-test123",
        )
        response = HybridQueryResponse(
            question="test question",
            answer="test answer",
            confidence=0.5,
            sources=["test"],
            entities_found=[],
            degradation=meta,
        )
        assert response.degradation is not None
        assert response.degradation.degraded is True
        assert "guideline_rag" in response.degradation.degraded_components

    def test_degradation_serialization(self):
        from app.api.clinical_agent import HybridQueryResponse

        meta = DegradationMetadata(degraded=False)
        response = HybridQueryResponse(
            question="q",
            answer="a",
            confidence=1.0,
            sources=[],
            entities_found=[],
            degradation=meta,
        )
        data = response.model_dump()
        assert "degradation" in data
        assert data["degradation"]["degraded"] is False


class TestErrorCodeExtensions:
    """Test that ErrorCode enum has degradation-related codes."""

    def test_degraded_response_code_exists(self):
        from app.api.errors import ErrorCode

        assert hasattr(ErrorCode, "DEGRADED_RESPONSE")
        assert ErrorCode.DEGRADED_RESPONSE.value == "DEGRADED_RESPONSE"

    def test_critical_prewarm_failure_code_exists(self):
        from app.api.errors import ErrorCode

        assert hasattr(ErrorCode, "CRITICAL_PREWARM_FAILURE")
        assert ErrorCode.CRITICAL_PREWARM_FAILURE.value == "CRITICAL_PREWARM_FAILURE"
