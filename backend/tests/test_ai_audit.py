"""Tests for AI audit API endpoints.

Tests verify:
- GET /ai/audit lists interactions with filters
- GET /ai/audit/stats returns aggregate stats
- POST /ai/audit/{id}/feedback submits feedback
- Service logs and retrieves interactions correctly
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.ai_audit import router
from app.services.ai_audit_service import AiAuditService, AiAuditEntry, AiAuditStats


def create_test_app():
    """Create a minimal FastAPI app with just the ai_audit router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client():
    app = create_test_app()
    return TestClient(app, raise_server_exceptions=False)


def _mock_entry(entry_id="entry-001", user_id="user-1", model="gpt-4"):
    """Create a mock audit entry."""
    entry = MagicMock()
    entry.id = entry_id
    entry.user_id = user_id
    entry.model_name = model
    entry.prompt_hash = "abc123"
    entry.prompt_tokens = 100
    entry.response_tokens = 200
    entry.total_tokens = 300
    entry.latency_ms = 450.0
    entry.status = "success"
    entry.feedback = None
    entry.feedback_comment = None
    entry.created_at = "2026-01-24T10:00:00+00:00"
    return entry


def _mock_stats():
    """Create mock stats."""
    stats = MagicMock()
    stats.total_interactions = 100
    stats.total_tokens = 30000
    stats.avg_latency_ms = 400.0
    stats.success_rate = 0.95
    stats.feedback_positive = 10
    stats.feedback_negative = 2
    stats.model_distribution = {"gpt-4": 80, "claude-3": 20}
    return stats


class TestListAiInteractions:
    """Test GET /ai/audit endpoint."""

    @patch("app.api.ai_audit.get_ai_audit_service")
    def test_list_returns_200(self, mock_svc, client):
        svc = MagicMock()
        svc.get_entries.return_value = ([_mock_entry()], 1)
        mock_svc.return_value = svc

        response = client.get("/ai/audit")
        assert response.status_code == 200

    @patch("app.api.ai_audit.get_ai_audit_service")
    def test_list_response_structure(self, mock_svc, client):
        svc = MagicMock()
        svc.get_entries.return_value = ([_mock_entry()], 1)
        mock_svc.return_value = svc

        data = client.get("/ai/audit").json()
        assert "total" in data
        assert "entries" in data
        assert "offset" in data
        assert "limit" in data
        assert data["total"] == 1

    @patch("app.api.ai_audit.get_ai_audit_service")
    def test_list_entry_fields(self, mock_svc, client):
        svc = MagicMock()
        svc.get_entries.return_value = ([_mock_entry()], 1)
        mock_svc.return_value = svc

        data = client.get("/ai/audit").json()
        entry = data["entries"][0]
        assert entry["id"] == "entry-001"
        assert entry["user_id"] == "user-1"
        assert entry["model_name"] == "gpt-4"
        assert entry["prompt_tokens"] == 100
        assert entry["response_tokens"] == 200
        assert entry["latency_ms"] == 450.0
        assert entry["status"] == "success"

    @patch("app.api.ai_audit.get_ai_audit_service")
    def test_list_with_user_filter(self, mock_svc, client):
        svc = MagicMock()
        svc.get_entries.return_value = ([], 0)
        mock_svc.return_value = svc

        client.get("/ai/audit", params={"user_id": "user-1"})
        svc.get_entries.assert_called_once_with(
            user_id="user-1",
            model_name=None,
            status=None,
            limit=50,
            offset=0,
        )

    @patch("app.api.ai_audit.get_ai_audit_service")
    def test_list_with_pagination(self, mock_svc, client):
        svc = MagicMock()
        svc.get_entries.return_value = ([], 0)
        mock_svc.return_value = svc

        client.get("/ai/audit", params={"limit": 10, "offset": 20})
        svc.get_entries.assert_called_once_with(
            user_id=None,
            model_name=None,
            status=None,
            limit=10,
            offset=20,
        )

    @patch("app.api.ai_audit.get_ai_audit_service")
    def test_list_empty(self, mock_svc, client):
        svc = MagicMock()
        svc.get_entries.return_value = ([], 0)
        mock_svc.return_value = svc

        data = client.get("/ai/audit").json()
        assert data["total"] == 0
        assert data["entries"] == []


class TestAiStats:
    """Test GET /ai/audit/stats endpoint."""

    @patch("app.api.ai_audit.get_ai_audit_service")
    def test_stats_returns_200(self, mock_svc, client):
        svc = MagicMock()
        svc.get_stats.return_value = _mock_stats()
        mock_svc.return_value = svc

        response = client.get("/ai/audit/stats")
        assert response.status_code == 200

    @patch("app.api.ai_audit.get_ai_audit_service")
    def test_stats_fields(self, mock_svc, client):
        svc = MagicMock()
        svc.get_stats.return_value = _mock_stats()
        mock_svc.return_value = svc

        data = client.get("/ai/audit/stats").json()
        assert data["total_interactions"] == 100
        assert data["total_tokens"] == 30000
        assert data["avg_latency_ms"] == 400.0
        assert data["success_rate"] == 0.95
        assert data["feedback_positive"] == 10
        assert data["model_distribution"]["gpt-4"] == 80

    @patch("app.api.ai_audit.get_ai_audit_service")
    def test_stats_with_user_filter(self, mock_svc, client):
        svc = MagicMock()
        svc.get_stats.return_value = _mock_stats()
        mock_svc.return_value = svc

        client.get("/ai/audit/stats", params={"user_id": "user-1"})
        svc.get_stats.assert_called_once_with(user_id="user-1")


class TestSubmitFeedback:
    """Test POST /ai/audit/{id}/feedback endpoint."""

    @patch("app.api.ai_audit.get_ai_audit_service")
    def test_submit_thumbs_up(self, mock_svc, client):
        svc = MagicMock()
        entry = _mock_entry()
        entry.feedback = "thumbs_up"
        entry.feedback_comment = "Great!"
        svc.submit_feedback.return_value = entry
        mock_svc.return_value = svc

        response = client.post(
            "/ai/audit/entry-001/feedback",
            json={"feedback": "thumbs_up", "comment": "Great!"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["feedback"] == "thumbs_up"
        assert data["status"] == "updated"

    @patch("app.api.ai_audit.get_ai_audit_service")
    def test_submit_thumbs_down(self, mock_svc, client):
        svc = MagicMock()
        entry = _mock_entry()
        entry.feedback = "thumbs_down"
        entry.feedback_comment = None
        svc.submit_feedback.return_value = entry
        mock_svc.return_value = svc

        response = client.post(
            "/ai/audit/entry-001/feedback",
            json={"feedback": "thumbs_down"},
        )
        assert response.status_code == 200

    @patch("app.api.ai_audit.get_ai_audit_service")
    def test_submit_invalid_feedback(self, mock_svc, client):
        mock_svc.return_value = MagicMock()

        response = client.post(
            "/ai/audit/entry-001/feedback",
            json={"feedback": "invalid"},
        )
        assert response.status_code == 400

    @patch("app.api.ai_audit.get_ai_audit_service")
    def test_submit_not_found(self, mock_svc, client):
        svc = MagicMock()
        svc.submit_feedback.return_value = None
        mock_svc.return_value = svc

        response = client.post(
            "/ai/audit/nonexistent/feedback",
            json={"feedback": "thumbs_up"},
        )
        assert response.status_code == 404


class TestAiAuditService:
    """Unit tests for AiAuditService."""

    def test_log_interaction(self):
        svc = AiAuditService()
        entry = svc.log_interaction(
            user_id="user-1",
            model_name="gpt-4",
            prompt_text="What is diabetes?",
            prompt_tokens=10,
            response_tokens=50,
            latency_ms=200.0,
        )
        assert entry.user_id == "user-1"
        assert entry.model_name == "gpt-4"
        assert entry.total_tokens == 60
        assert entry.prompt_hash != ""

    def test_get_entries(self):
        svc = AiAuditService()
        svc.log_interaction(user_id="user-1", model_name="gpt-4")
        svc.log_interaction(user_id="user-2", model_name="claude-3")

        entries, total = svc.get_entries()
        assert total == 2

        entries, total = svc.get_entries(user_id="user-1")
        assert total == 1
        assert entries[0].user_id == "user-1"

    def test_submit_feedback(self):
        svc = AiAuditService()
        entry = svc.log_interaction(user_id="user-1", model_name="gpt-4")

        updated = svc.submit_feedback(entry.id, "thumbs_up", "Good")
        assert updated is not None
        assert updated.feedback == "thumbs_up"
        assert updated.feedback_comment == "Good"

    def test_submit_feedback_not_found(self):
        svc = AiAuditService()
        result = svc.submit_feedback("nonexistent", "thumbs_up")
        assert result is None

    def test_get_stats(self):
        svc = AiAuditService()
        svc.log_interaction(user_id="user-1", model_name="gpt-4", prompt_tokens=10, response_tokens=20, latency_ms=100)
        svc.log_interaction(user_id="user-1", model_name="gpt-4", prompt_tokens=20, response_tokens=30, latency_ms=200)
        svc.log_interaction(user_id="user-2", model_name="claude-3", prompt_tokens=15, response_tokens=25, latency_ms=150)

        stats = svc.get_stats()
        assert stats.total_interactions == 3
        assert stats.total_tokens == 120  # 30+50+40
        assert stats.success_rate == 1.0
        assert "gpt-4" in stats.model_distribution

    def test_max_entries_cap(self):
        svc = AiAuditService()
        svc._max_entries = 5
        for i in range(10):
            svc.log_interaction(user_id=f"user-{i}", model_name="test")

        entries, total = svc.get_entries(limit=100)
        assert total == 5
