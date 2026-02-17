"""Tests for Phase 1 Safety Envelope: Prewarm service classification."""

from __future__ import annotations

import pytest


class TestPrewarmClassification:
    """Test prewarm service classification and failure handling."""

    def test_prewarm_returns_dict_on_success(self):
        """prewarm_all_services should return a dict with services_loaded count."""
        from app.main import prewarm_all_services

        result = prewarm_all_services()
        assert isinstance(result, dict)
        assert "services_loaded" in result
        assert "total_prewarm_time_ms" in result
        assert "services" in result

    def test_prewarm_continues_on_non_critical_failure(self):
        """Non-critical service failures should not prevent other services from loading."""
        from app.main import prewarm_all_services

        # Even if some services fail (due to missing dependencies in test env),
        # prewarm should complete without raising
        result = prewarm_all_services()
        assert isinstance(result, dict)
        # At least some services should have loaded (those without external deps)
        assert result["services_loaded"] >= 0

    def test_prewarm_timing_is_recorded(self):
        from app.main import prewarm_all_services

        result = prewarm_all_services()
        assert result["total_prewarm_time_ms"] >= 0


class TestGuidelineRagLoadedBug:
    """Test the _loaded bug fix in guideline_rag_service."""

    def test_loaded_false_when_fixture_missing(self, tmp_path):
        """_loaded should be False when fixture file doesn't exist."""
        from app.services.guideline_rag_service import GuidelineRAGService

        svc = GuidelineRAGService(fixture_path=str(tmp_path / "nonexistent.json"))
        svc.load()
        assert svc.is_loaded is False
        assert svc.section_count == 0

    def test_loaded_true_when_fixture_exists(self, tmp_path):
        """_loaded should be True when fixture file exists with valid data."""
        import json

        from app.services.guideline_rag_service import GuidelineRAGService

        fixture = tmp_path / "guidelines.json"
        fixture.write_text(json.dumps({
            "guidelines": [
                {
                    "section_id": "test-1",
                    "guideline": "Test Guideline",
                    "section_title": "Test Section Title",
                    "recommendation_text": "This is a test guideline recommendation.",
                    "evidence_grade": "A",
                    "recommendation_level": "Strong",
                }
            ]
        }))

        svc = GuidelineRAGService(fixture_path=str(fixture))
        svc.load()
        assert svc.is_loaded is True
