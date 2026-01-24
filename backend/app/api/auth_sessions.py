"""Session Management API endpoints.

Provides endpoints for:
- POST /auth/refresh - Token refresh with rotation
- GET /auth/sessions - List active sessions
- DELETE /auth/sessions/{session_id} - Revoke a session
"""

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


@router.post("/refresh", response_model=RefreshResponse)
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
