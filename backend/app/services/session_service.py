"""Session Management Service.

Provides token refresh, session timeout tracking, session listing,
revocation, and refresh token rotation.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_SESSION_TIMEOUT = 1800  # 30 minutes idle timeout
DEFAULT_REFRESH_TOKEN_TTL = 86400  # 24 hours
DEFAULT_ABSOLUTE_TIMEOUT = 28800  # 8 hours max session lifetime


@dataclass
class Session:
    """Represents an active user session.

    VP-Security-2: Enhanced with idle and absolute timeout validation.
    """

    session_id: str
    user_id: str
    access_token: str
    refresh_token: str
    created_at: float
    last_activity: float
    timeout_seconds: int = DEFAULT_SESSION_TIMEOUT
    absolute_timeout_seconds: int = DEFAULT_ABSOLUTE_TIMEOUT
    revoked: bool = False
    refresh_count: int = 0

    @property
    def is_idle_expired(self) -> bool:
        """VP-Security-2: Check if session exceeded idle timeout."""
        return (time.time() - self.last_activity) > self.timeout_seconds

    @property
    def is_absolute_expired(self) -> bool:
        """VP-Security-2: Check if session exceeded absolute lifetime."""
        return (time.time() - self.created_at) > self.absolute_timeout_seconds

    @property
    def is_expired(self) -> bool:
        """VP-Security-2: Session is expired if either timeout exceeded."""
        return self.is_idle_expired or self.is_absolute_expired

    @property
    def is_active(self) -> bool:
        return not self.revoked and not self.is_expired

    def get_expiration_reason(self) -> str | None:
        """VP-Security-2: Get reason for expiration if expired."""
        if self.revoked:
            return "revoked"
        if self.is_absolute_expired:
            return "absolute_timeout"
        if self.is_idle_expired:
            return "idle_timeout"
        return None

    def time_until_idle_expiry(self) -> float:
        """Seconds until idle timeout."""
        return max(0, self.timeout_seconds - (time.time() - self.last_activity))

    def time_until_absolute_expiry(self) -> float:
        """Seconds until absolute timeout."""
        return max(0, self.absolute_timeout_seconds - (time.time() - self.created_at))


class SessionService:
    """Manages user sessions with token refresh and rotation.

    Features:
    - Token refresh with rotation (new refresh token on each use)
    - Session timeout tracking (configurable, default 30min)
    - Active session listing
    - Session revocation
    """

    def __init__(self, session_timeout: int = DEFAULT_SESSION_TIMEOUT):
        self._sessions: dict[str, Session] = {}
        self._refresh_tokens: dict[str, str] = {}  # refresh_token -> session_id
        self._lock = Lock()
        self._session_timeout = session_timeout

    def create_session(self, user_id: str) -> dict[str, str]:
        """Create a new session with access and refresh tokens.

        Returns dict with session_id, access_token, refresh_token.
        """
        with self._lock:
            session_id = secrets.token_urlsafe(32)
            access_token = secrets.token_urlsafe(48)
            refresh_token = secrets.token_urlsafe(48)

            session = Session(
                session_id=session_id,
                user_id=user_id,
                access_token=access_token,
                refresh_token=refresh_token,
                created_at=time.time(),
                last_activity=time.time(),
                timeout_seconds=self._session_timeout,
            )

            self._sessions[session_id] = session
            self._refresh_tokens[refresh_token] = session_id

            return {
                "session_id": session_id,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_in": self._session_timeout,
            }

    def refresh_session(self, refresh_token: str) -> dict[str, str] | None:
        """Refresh a session using a refresh token.

        VP-Security-2: Enforces absolute timeout - cannot refresh past max lifetime.

        Implements token rotation: the old refresh token is invalidated
        and a new one is issued.

        Returns new tokens or None if refresh token is invalid/expired.
        """
        with self._lock:
            session_id = self._refresh_tokens.get(refresh_token)
            if session_id is None:
                return None

            session = self._sessions.get(session_id)
            if session is None or session.revoked:
                return None

            # VP-Security-2: Cannot refresh if absolute timeout exceeded
            if session.is_absolute_expired:
                logger.info(
                    f"Refresh denied: session {session_id} exceeded absolute timeout, "
                    f"user_id={session.user_id}"
                )
                session.revoked = True
                self._refresh_tokens.pop(session.refresh_token, None)
                return None

            # Check if refresh token matches current session token
            if session.refresh_token != refresh_token:
                # Token was already rotated - possible replay attack
                logger.warning(
                    f"Possible token replay detected for session {session_id}"
                )
                return None

            # Rotate tokens
            del self._refresh_tokens[refresh_token]

            new_access_token = secrets.token_urlsafe(48)
            new_refresh_token = secrets.token_urlsafe(48)

            session.access_token = new_access_token
            session.refresh_token = new_refresh_token
            session.last_activity = time.time()
            session.refresh_count += 1

            self._refresh_tokens[new_refresh_token] = session_id

            return {
                "session_id": session_id,
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "expires_in": self._session_timeout,
            }

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session by ID with expiration enforcement.

        VP-Security-2: Enforces session expiration by:
        - Checking both idle and absolute timeouts
        - Auto-revoking expired sessions
        - Returning None for invalid/expired sessions

        Args:
            session_id: The session ID to look up.

        Returns:
            Session info dict or None if not found/expired.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None

            # VP-Security-2: Enforce expiration
            if session.is_expired:
                expiry_reason = session.get_expiration_reason()
                logger.info(
                    f"Session {session_id} expired due to {expiry_reason}, "
                    f"user_id={session.user_id}"
                )
                # Auto-revoke expired session
                session.revoked = True
                self._refresh_tokens.pop(session.refresh_token, None)
                return None

            if session.revoked:
                return None

            # Return session info with timeout warnings
            return {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "created_at": session.created_at,
                "last_activity": session.last_activity,
                "refresh_count": session.refresh_count,
                "expires_in": min(
                    session.time_until_idle_expiry(),
                    session.time_until_absolute_expiry(),
                ),
                "idle_expires_in": session.time_until_idle_expiry(),
                "absolute_expires_in": session.time_until_absolute_expiry(),
            }

    def validate_access_token(self, access_token: str) -> Session | None:
        """Validate an access token and return the session if valid.

        VP-Security-2: Also enforces expiration and auto-revokes.
        """
        with self._lock:
            for session in self._sessions.values():
                if session.access_token == access_token:
                    # VP-Security-2: Check expiration before validating
                    if session.is_expired:
                        expiry_reason = session.get_expiration_reason()
                        logger.info(
                            f"Access token validation failed: session {session.session_id} "
                            f"expired due to {expiry_reason}"
                        )
                        session.revoked = True
                        self._refresh_tokens.pop(session.refresh_token, None)
                        return None

                    if session.revoked:
                        return None

                    session.last_activity = time.time()
                    return session
            return None

    def is_session_timed_out(self, session_id: str) -> bool:
        """Check if a session has timed out."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return True
            return session.is_expired

    def revoke_session(self, session_id: str) -> bool:
        """Revoke a session, invalidating all its tokens.

        Returns True if session was found and revoked.
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False

            session.revoked = True
            # Remove refresh token mapping
            self._refresh_tokens.pop(session.refresh_token, None)
            return True

    def list_active_sessions(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """List active sessions, optionally filtered by user_id."""
        with self._lock:
            sessions = []
            for session in self._sessions.values():
                if session.is_active:
                    if user_id and session.user_id != user_id:
                        continue
                    sessions.append({
                        "session_id": session.session_id,
                        "user_id": session.user_id,
                        "created_at": session.created_at,
                        "last_activity": session.last_activity,
                        "refresh_count": session.refresh_count,
                    })
            return sessions

    def cleanup_expired(self) -> int:
        """Remove expired sessions. Returns count of removed sessions."""
        with self._lock:
            expired = [
                sid for sid, s in self._sessions.items()
                if not s.is_active
            ]
            for sid in expired:
                session = self._sessions.pop(sid)
                self._refresh_tokens.pop(session.refresh_token, None)
            return len(expired)


# Singleton
_session_service: SessionService | None = None


def get_session_service() -> SessionService:
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
    return _session_service


def reset_session_service() -> None:
    global _session_service
    _session_service = None
