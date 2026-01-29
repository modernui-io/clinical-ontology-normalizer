"""Session Management API endpoints.

Provides endpoints for:
- POST /auth/sessions/refresh - Token refresh with rotation
- GET /auth/sessions - List active sessions
- DELETE /auth/sessions/{session_id} - Revoke a session
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.session_service import get_session_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["sessions"])


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str = Field(..., description="The refresh token to use")


class RefreshResponse(BaseModel):
    """Token refresh response."""

    session_id: str
    access_token: str
    refresh_token: str
    expires_in: int


@router.post("/sessions/refresh", response_model=RefreshResponse)
async def refresh_token(request: RefreshRequest) -> dict[str, Any]:
    """Refresh an access token using a refresh token.

    Implements token rotation: the old refresh token is invalidated
    and a new pair of access + refresh tokens is issued.
    """
    service = get_session_service()
    result = service.refresh_session(request.refresh_token)

    if result is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token"
        )

    return result


@router.get("/sessions")
async def list_sessions(user_id: str | None = None) -> list[dict[str, Any]]:
    """List active sessions, optionally filtered by user_id."""
    service = get_session_service()
    return service.list_active_sessions(user_id=user_id)


@router.get("/sessions/current")
async def get_current_session(session_id: str | None = None, user_id: str | None = None) -> dict[str, Any]:
    """Get information about the current active session.

    Returns session details including expiration and timeout warning.

    Args:
        session_id: Optional session ID to query.
        user_id: Optional user ID to find active session.

    Returns:
        Session info with expires_in field for timeout warning.
    """
    service = get_session_service()

    if session_id:
        session = service.get_session(session_id)
    elif user_id:
        sessions = service.list_active_sessions(user_id=user_id)
        session = sessions[0] if sessions else None
    else:
        raise HTTPException(
            status_code=400,
            detail="Either session_id or user_id is required"
        )

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="No active session found"
        )

    return session


@router.delete("/sessions/{session_id}")
async def revoke_session(session_id: str) -> dict[str, str]:
    """Revoke a session, invalidating all its tokens."""
    service = get_session_service()
    success = service.revoke_session(session_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )

    return {"status": "revoked", "session_id": session_id}


@router.delete("/sessions")
async def revoke_all_sessions(user_id: str | None = None) -> dict[str, Any]:
    """Revoke all sessions for a user (bulk revoke).

    Args:
        user_id: Optional user_id to revoke all sessions for.
            If not provided, revokes all sessions.

    Returns:
        Count of revoked sessions.
    """
    service = get_session_service()
    sessions = service.list_active_sessions(user_id=user_id)
    revoked_count = 0

    for session in sessions:
        sid = session.get("session_id") or session.get("id")
        if sid and service.revoke_session(sid):
            revoked_count += 1

    return {
        "status": "revoked",
        "revoked_count": revoked_count,
        "user_id": user_id,
    }
