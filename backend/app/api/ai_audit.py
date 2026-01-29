"""AI Audit API endpoints.

Provides:
- GET /ai/audit - List AI interactions with filters
- GET /ai/audit/stats - Get aggregate statistics
- POST /ai/audit/{id}/feedback - Submit feedback for an interaction
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.ai_audit_service import get_ai_audit_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai-audit"])


class FeedbackRequest(BaseModel):
    """Feedback submission request."""

    feedback: str = Field(..., description="Feedback type: thumbs_up or thumbs_down")
    comment: str | None = Field(None, description="Optional feedback comment")

    class Config:
        json_schema_extra = {
            "example": {
                "feedback": "thumbs_up",
                "comment": "Accurate response",
            }
        }


@router.get("/audit")
async def list_ai_interactions(
    user_id: str | None = Query(None, description="Filter by user ID"),
    model_name: str | None = Query(None, description="Filter by model name"),
    status: str | None = Query(None, description="Filter by status: success, error, timeout"),
    limit: int = Query(50, ge=1, le=500, description="Maximum entries"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> dict[str, Any]:
    """List AI interactions with optional filters.

    Returns paginated audit entries showing AI model usage,
    token counts, latency, and feedback.
    """
    service = get_ai_audit_service()
    entries, total = service.get_entries(
        user_id=user_id,
        model_name=model_name,
        status=status,
        limit=limit,
        offset=offset,
    )

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "entries": [
            {
                "id": entry.id,
                "user_id": entry.user_id,
                "model_name": entry.model_name,
                "prompt_hash": entry.prompt_hash,
                "prompt_tokens": entry.prompt_tokens,
                "response_tokens": entry.response_tokens,
                "total_tokens": entry.total_tokens,
                "latency_ms": entry.latency_ms,
                "status": entry.status,
                "feedback": entry.feedback,
                "created_at": entry.created_at,
            }
            for entry in entries
        ],
    }


@router.get("/audit/stats")
async def get_ai_stats(
    user_id: str | None = Query(None, description="Filter stats by user ID"),
) -> dict[str, Any]:
    """Get aggregate AI usage statistics.

    Returns total interactions, token usage, latency averages,
    success rates, and model distribution.
    """
    service = get_ai_audit_service()
    stats = service.get_stats(user_id=user_id)

    return {
        "total_interactions": stats.total_interactions,
        "total_tokens": stats.total_tokens,
        "avg_latency_ms": stats.avg_latency_ms,
        "success_rate": stats.success_rate,
        "feedback_positive": stats.feedback_positive,
        "feedback_negative": stats.feedback_negative,
        "model_distribution": stats.model_distribution,
    }


@router.post("/audit/{entry_id}/feedback")
async def submit_feedback(entry_id: str, request: FeedbackRequest) -> dict[str, Any]:
    """Submit feedback for an AI interaction.

    Allows users to rate AI responses with thumbs up/down
    and an optional comment.
    """
    if request.feedback not in ("thumbs_up", "thumbs_down"):
        raise HTTPException(
            status_code=400,
            detail="feedback must be 'thumbs_up' or 'thumbs_down'",
        )

    service = get_ai_audit_service()
    entry = service.submit_feedback(
        entry_id=entry_id,
        feedback=request.feedback,
        comment=request.comment,
    )

    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"Audit entry '{entry_id}' not found",
        )

    return {
        "id": entry.id,
        "feedback": entry.feedback,
        "feedback_comment": entry.feedback_comment,
        "status": "updated",
    }
