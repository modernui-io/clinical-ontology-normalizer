"""Tests for Session Management.

Tests verify:
- Token refresh returns new access + refresh tokens
- Expired refresh token returns 401
- Session timeout detection
- Session revocation invalidates tokens
- Refresh token rotation (old token invalid after use)
"""

import time

import pytest

from app.services.session_service import SessionService, reset_session_service


@pytest.fixture(autouse=True)
def reset():
    reset_session_service()
    yield
    reset_session_service()


@pytest.fixture
def service():
    return SessionService(session_timeout=5)  # 5 second timeout for tests


class TestTokenRefresh:
    """Test token refresh returns new access + refresh tokens."""

    def test_refresh_returns_new_access_token(self, service):
        session = service.create_session("user1")
        old_access = session["access_token"]
        result = service.refresh_session(session["refresh_token"])
        assert result is not None
        assert result["access_token"] != old_access

    def test_refresh_returns_new_refresh_token(self, service):
        session = service.create_session("user1")
        old_refresh = session["refresh_token"]
        result = service.refresh_session(old_refresh)
        assert result is not None
        assert result["refresh_token"] != old_refresh

    def test_refresh_returns_same_session_id(self, service):
        session = service.create_session("user1")
        result = service.refresh_session(session["refresh_token"])
        assert result["session_id"] == session["session_id"]

    def test_refresh_includes_expires_in(self, service):
        session = service.create_session("user1")
        result = service.refresh_session(session["refresh_token"])
        assert "expires_in" in result
        assert result["expires_in"] == 5


class TestExpiredRefreshToken:
    """Test expired/invalid refresh token returns None (401 at API level)."""

    def test_invalid_refresh_token(self, service):
        result = service.refresh_session("invalid-token-xyz")
        assert result is None

    def test_empty_refresh_token(self, service):
        result = service.refresh_session("")
        assert result is None

    def test_revoked_session_refresh_fails(self, service):
        session = service.create_session("user1")
        service.revoke_session(session["session_id"])
        result = service.refresh_session(session["refresh_token"])
        assert result is None


class TestSessionTimeout:
    """Test session timeout detection."""

    def test_new_session_not_timed_out(self, service):
        session = service.create_session("user1")
        assert not service.is_session_timed_out(session["session_id"])

    def test_session_times_out_after_inactivity(self):
        # Very short timeout for testing
        svc = SessionService(session_timeout=0)
        session = svc.create_session("user1")
        time.sleep(0.01)
        assert svc.is_session_timed_out(session["session_id"])

    def test_nonexistent_session_is_timed_out(self, service):
        assert service.is_session_timed_out("nonexistent-id")

    def test_validate_expired_session_returns_none(self):
        svc = SessionService(session_timeout=0)
        session = svc.create_session("user1")
        time.sleep(0.01)
        result = svc.validate_access_token(session["access_token"])
        assert result is None


class TestSessionRevocation:
    """Test session revocation invalidates tokens."""

    def test_revoke_returns_true(self, service):
        session = service.create_session("user1")
        assert service.revoke_session(session["session_id"]) is True

    def test_revoke_nonexistent_returns_false(self, service):
        assert service.revoke_session("nonexistent") is False

    def test_revoked_session_access_token_invalid(self, service):
        session = service.create_session("user1")
        service.revoke_session(session["session_id"])
        result = service.validate_access_token(session["access_token"])
        assert result is None

    def test_revoked_session_not_in_active_list(self, service):
        session = service.create_session("user1")
        service.revoke_session(session["session_id"])
        active = service.list_active_sessions()
        assert all(s["session_id"] != session["session_id"] for s in active)

    def test_revoke_does_not_affect_other_sessions(self, service):
        s1 = service.create_session("user1")
        s2 = service.create_session("user2")
        service.revoke_session(s1["session_id"])
        result = service.validate_access_token(s2["access_token"])
        assert result is not None


class TestRefreshTokenRotation:
    """Test refresh token rotation (old token invalid after use)."""

    def test_old_refresh_token_invalid_after_rotation(self, service):
        session = service.create_session("user1")
        old_refresh = session["refresh_token"]
        service.refresh_session(old_refresh)
        # Old token should now be invalid
        result = service.refresh_session(old_refresh)
        assert result is None

    def test_new_refresh_token_works_after_rotation(self, service):
        session = service.create_session("user1")
        result1 = service.refresh_session(session["refresh_token"])
        result2 = service.refresh_session(result1["refresh_token"])
        assert result2 is not None
        assert result2["access_token"] != result1["access_token"]

    def test_multiple_rotations_chain(self, service):
        session = service.create_session("user1")
        current_refresh = session["refresh_token"]
        for _ in range(5):
            result = service.refresh_session(current_refresh)
            assert result is not None
            current_refresh = result["refresh_token"]

    def test_old_tokens_from_chain_all_invalid(self, service):
        session = service.create_session("user1")
        old_tokens = [session["refresh_token"]]
        current = session["refresh_token"]
        for _ in range(3):
            result = service.refresh_session(current)
            old_tokens.append(current)
            current = result["refresh_token"]

        # All old tokens should be invalid
        for old_token in old_tokens:
            assert service.refresh_session(old_token) is None


class TestSessionListing:
    """Test active session listing."""

    def test_list_empty(self, service):
        assert service.list_active_sessions() == []

    def test_list_shows_active_session(self, service):
        service.create_session("user1")
        sessions = service.list_active_sessions()
        assert len(sessions) == 1
        assert sessions[0]["user_id"] == "user1"

    def test_list_filters_by_user(self, service):
        service.create_session("user1")
        service.create_session("user2")
        sessions = service.list_active_sessions(user_id="user1")
        assert len(sessions) == 1
        assert sessions[0]["user_id"] == "user1"
