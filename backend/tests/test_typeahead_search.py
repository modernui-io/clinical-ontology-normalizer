"""Tests for typeahead search endpoint.

Tests verify:
- Basic search returns results
- Filtering by type works
- Limit parameter works
- Highlight formatting
- Empty query handling
- Graceful fallback on errors
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.search import router


def create_test_app():
    """Create a minimal FastAPI app with just the search router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client():
    app = create_test_app()
    return TestClient(app, raise_server_exceptions=False)


class TestTypeaheadEndpoint:
    """Test GET /search/typeahead endpoint."""

    def test_endpoint_exists(self, client):
        response = client.get("/search/typeahead", params={"q": "diabetes"})
        # Should not be 404/405 (endpoint exists)
        assert response.status_code != 404
        assert response.status_code != 405

    def test_missing_query_returns_422(self, client):
        response = client.get("/search/typeahead")
        assert response.status_code == 422

    def test_empty_query_returns_422(self, client):
        response = client.get("/search/typeahead", params={"q": ""})
        assert response.status_code == 422

    @patch("app.api.search.get_sync_engine")
    @patch("app.services.vocabulary.get_vocabulary_service")
    def test_returns_response_structure(self, mock_vocab, mock_engine, client):
        mock_vocab_svc = MagicMock()
        mock_vocab_svc.search_concepts.return_value = [
            {"concept_id": 123, "concept_name": "Diabetes mellitus", "domain_id": "Condition", "vocabulary_id": "SNOMED", "score": 0.9}
        ]
        mock_vocab.return_value = mock_vocab_svc

        # Mock DB to raise (graceful fallback)
        mock_engine.side_effect = Exception("No DB")

        response = client.get("/search/typeahead", params={"q": "diabetes"})
        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert "results" in data
        assert "total" in data
        assert "groups" in data
        assert data["query"] == "diabetes"

    @patch("app.api.search.get_sync_engine")
    @patch("app.services.vocabulary.get_vocabulary_service")
    def test_concept_results_have_required_fields(self, mock_vocab, mock_engine, client):
        mock_vocab_svc = MagicMock()
        mock_vocab_svc.search_concepts.return_value = [
            {"concept_id": 123, "concept_name": "Diabetes mellitus", "domain_id": "Condition", "vocabulary_id": "SNOMED", "score": 0.95}
        ]
        mock_vocab.return_value = mock_vocab_svc
        mock_engine.side_effect = Exception("No DB")

        response = client.get("/search/typeahead", params={"q": "diabetes"})
        data = response.json()
        assert len(data["results"]) == 1
        result = data["results"][0]
        assert result["id"] == "123"
        assert result["text"] == "Diabetes mellitus"
        assert result["type"] == "concept"
        assert "score" in result

    @patch("app.api.search.get_sync_engine")
    @patch("app.services.vocabulary.get_vocabulary_service")
    def test_type_filter(self, mock_vocab, mock_engine, client):
        mock_vocab_svc = MagicMock()
        mock_vocab_svc.search_concepts.return_value = [
            {"concept_id": 1, "concept_name": "Test", "domain_id": "Condition", "vocabulary_id": "SNOMED", "score": 0.8}
        ]
        mock_vocab.return_value = mock_vocab_svc
        mock_engine.side_effect = Exception("No DB")

        # Only search concepts
        response = client.get("/search/typeahead", params={"q": "test", "types": "concept"})
        data = response.json()
        for r in data["results"]:
            assert r["type"] == "concept"

    @patch("app.api.search.get_sync_engine")
    @patch("app.services.vocabulary.get_vocabulary_service")
    def test_limit_parameter(self, mock_vocab, mock_engine, client):
        mock_vocab_svc = MagicMock()
        mock_vocab_svc.search_concepts.return_value = [
            {"concept_id": i, "concept_name": f"Concept {i}", "domain_id": "Condition", "vocabulary_id": "SNOMED", "score": 0.8}
            for i in range(20)
        ]
        mock_vocab.return_value = mock_vocab_svc
        mock_engine.side_effect = Exception("No DB")

        response = client.get("/search/typeahead", params={"q": "concept", "limit": "5"})
        data = response.json()
        assert len(data["results"]) <= 5

    @patch("app.api.search.get_sync_engine")
    @patch("app.services.vocabulary.get_vocabulary_service")
    def test_results_sorted_by_score(self, mock_vocab, mock_engine, client):
        mock_vocab_svc = MagicMock()
        mock_vocab_svc.search_concepts.return_value = [
            {"concept_id": 1, "concept_name": "Low", "domain_id": "Condition", "vocabulary_id": "SNOMED", "score": 0.3},
            {"concept_id": 2, "concept_name": "High", "domain_id": "Condition", "vocabulary_id": "SNOMED", "score": 0.9},
        ]
        mock_vocab.return_value = mock_vocab_svc
        mock_engine.side_effect = Exception("No DB")

        response = client.get("/search/typeahead", params={"q": "test"})
        data = response.json()
        scores = [r["score"] for r in data["results"]]
        assert scores == sorted(scores, reverse=True)

    @patch("app.api.search.get_sync_engine")
    @patch("app.services.vocabulary.get_vocabulary_service")
    def test_graceful_fallback_on_all_failures(self, mock_vocab, mock_engine, client):
        """When all services fail, return empty results (not error)."""
        mock_vocab.side_effect = Exception("fail")
        mock_engine.side_effect = Exception("fail")

        response = client.get("/search/typeahead", params={"q": "test"})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["results"] == []


class TestTypeaheadHighlighting:
    """Test result highlighting."""

    @patch("app.api.search.get_sync_engine")
    @patch("app.services.vocabulary.get_vocabulary_service")
    def test_highlight_contains_em_tags(self, mock_vocab, mock_engine, client):
        mock_vocab_svc = MagicMock()
        mock_vocab_svc.search_concepts.return_value = [
            {"concept_id": 1, "concept_name": "Diabetes mellitus", "domain_id": "Condition", "vocabulary_id": "SNOMED", "score": 0.9}
        ]
        mock_vocab.return_value = mock_vocab_svc
        mock_engine.side_effect = Exception("No DB")

        response = client.get("/search/typeahead", params={"q": "Diabetes"})
        data = response.json()
        result = data["results"][0]
        assert "<em>" in result["highlight"]
        assert "Diabetes" in result["highlight"]


class TestTypeaheadGrouping:
    """Test result grouping by type."""

    @patch("app.api.search.get_sync_engine")
    @patch("app.services.vocabulary.get_vocabulary_service")
    def test_groups_count_by_type(self, mock_vocab, mock_engine, client):
        mock_vocab_svc = MagicMock()
        mock_vocab_svc.search_concepts.return_value = [
            {"concept_id": 1, "concept_name": "Test", "domain_id": "Condition", "vocabulary_id": "SNOMED", "score": 0.8},
            {"concept_id": 2, "concept_name": "Test 2", "domain_id": "Condition", "vocabulary_id": "SNOMED", "score": 0.7},
        ]
        mock_vocab.return_value = mock_vocab_svc
        mock_engine.side_effect = Exception("No DB")

        response = client.get("/search/typeahead", params={"q": "test"})
        data = response.json()
        assert data["groups"]["concept"] == 2
