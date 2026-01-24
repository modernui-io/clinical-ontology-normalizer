"""Tests for session management enhancements.

Tests verify:
- GET /auth/sessions/current returns session info
- DELETE /auth/sessions bulk revokes all sessions
- expires_in field present in responses
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth_sessions import router


def create_test_app():
    """Create a minimal FastAPI app with just the auth_sessions router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client():
    app = create_test_app()
    return TestClient(app, raise_server_exceptions=False)


def _mock_session_service():
    """Create a mock session service."""
    svc = MagicMock()
    svc.get_session.return_value = {
        "session_id": "sess-123",
        "user_id": "user-456",
        "created_at": "2026-01-24T10:00:00Z",
        "expires_at": "2026-01-24T11:00:00Z",
        "expires_in": 3600,
        "is_active": True,
    }
    svc.list_active_sessions.return_value = [
        {"session_id": "sess-123", "user_id": "user-456", "is_active": True},
        {"session_id": "sess-456", "user_id": "user-456", "is_active": True},
    ]
    svc.revoke_session.return_value = True
    svc.refresh_session.return_value = {
        "session_id": "sess-new",
        "access_token": "new-access",
        "refresh_token": "new-refresh",
        "expires_in": 3600,
    }
    return svc


class TestGetCurrentSession:
    """Test GET /auth/sessions/current endpoint."""

    @patch("app.api.auth_sessions.get_session_service")
    def test_get_session_by_id(self, mock_svc, client):
        mock_svc.return_value = _mock_session_service()

        response = client.get("/auth/sessions/current", params={"session_id": "sess-123"})
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "sess-123"
        assert "expires_in" in data

    @patch("app.api.auth_sessions.get_session_service")
    def test_get_session_by_user_id(self, mock_svc, client):
        mock_svc.return_value = _mock_session_service()

        response = client.get("/auth/sessions/current", params={"user_id": "user-456"})
        assert response.status_code == 200

    @patch("app.api.auth_sessions.get_session_service")
    def test_get_session_not_found(self, mock_svc, client):
        svc = _mock_session_service()
        svc.get_session.return_value = None
        mock_svc.return_value = svc

        response = client.get("/auth/sessions/current", params={"session_id": "nonexistent"})
        assert response.status_code == 404

    @patch("app.api.auth_sessions.get_session_service")
    def test_get_session_no_params_returns_400(self, mock_svc, client):
        mock_svc.return_value = _mock_session_service()
        response = client.get("/auth/sessions/current")
        assert response.status_code == 400


class TestBulkRevokeSession:
    """Test DELETE /auth/sessions bulk revoke."""

    @patch("app.api.auth_sessions.get_session_service")
    def test_bulk_revoke_all(self, mock_svc, client):
        mock_svc.return_value = _mock_session_service()

        response = client.delete("/auth/sessions", params={"user_id": "user-456"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "revoked"
        assert data["revoked_count"] == 2

    @patch("app.api.auth_sessions.get_session_service")
    def test_bulk_revoke_no_sessions(self, mock_svc, client):
        svc = _mock_session_service()
        svc.list_active_sessions.return_value = []
        mock_svc.return_value = svc

        response = client.delete("/auth/sessions", params={"user_id": "user-789"})
        assert response.status_code == 200
        data = response.json()
        assert data["revoked_count"] == 0

    @patch("app.api.auth_sessions.get_session_service")
    def test_bulk_revoke_without_user_id(self, mock_svc, client):
        mock_svc.return_value = _mock_session_service()

        response = client.delete("/auth/sessions")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "revoked"


class TestRefreshToken:
    """Test POST /auth/refresh includes expires_in."""

    @patch("app.api.auth_sessions.get_session_service")
    def test_refresh_includes_expires_in(self, mock_svc, client):
        mock_svc.return_value = _mock_session_service()

        response = client.post(
            "/auth/refresh",
            json={"refresh_token": "valid-refresh-token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "expires_in" in data
        assert data["expires_in"] == 3600

    @patch("app.api.auth_sessions.get_session_service")
    def test_refresh_invalid_token(self, mock_svc, client):
        svc = _mock_session_service()
        svc.refresh_session.return_value = None
        mock_svc.return_value = svc

        response = client.post(
            "/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert response.status_code == 401


class TestListSessions:
    """Test GET /auth/sessions returns sessions with metadata."""

    @patch("app.api.auth_sessions.get_session_service")
    def test_list_sessions(self, mock_svc, client):
        mock_svc.return_value = _mock_session_service()

        response = client.get("/auth/sessions", params={"user_id": "user-456"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @patch("app.api.auth_sessions.get_session_service")
    def test_list_sessions_without_filter(self, mock_svc, client):
        mock_svc.return_value = _mock_session_service()

        response = client.get("/auth/sessions")
        assert response.status_code == 200
