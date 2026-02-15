"""Clinician Feedback API (P2-009).

Captures clinician ratings and corrections on clinical AI responses
and exposes aggregated summary statistics.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Query, status

from app.schemas.clinician_feedback import (
    ClinicianFeedbackCreate,
    ClinicianFeedbackResponse,
    CorrectionType,
    FeedbackSummaryResponse,
)

router = APIRouter(prefix="/clinician-feedback", tags=["clinician-feedback"])

# ---------------------------------------------------------------------------
# In-memory store (swap for DB in production)
# ---------------------------------------------------------------------------

_feedback_store: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=ClinicianFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit clinician feedback",
    description="Record a clinician's rating and correction on a clinical response.",
)
def submit_clinician_feedback(
    body: ClinicianFeedbackCreate,
) -> ClinicianFeedbackResponse:
    """Record clinician feedback for a clinical AI response."""
    record = {
        "id": str(uuid.uuid4()),
        "query_id": body.query_id,
        "response_id": body.response_id,
        "rating": body.rating,
        "feedback_text": body.feedback_text,
        "correction_type": body.correction_type.value,
        "created_at": datetime.now(timezone.utc),
    }
    _feedback_store.append(record)

    return ClinicianFeedbackResponse(
        id=record["id"],
        query_id=record["query_id"],
        response_id=record["response_id"],
        rating=record["rating"],
        feedback_text=record["feedback_text"],
        correction_type=CorrectionType(record["correction_type"]),
        created_at=record["created_at"],
    )


@router.get(
    "/summary",
    response_model=FeedbackSummaryResponse,
    summary="Get feedback summary",
    description="Return aggregated clinician feedback statistics.",
)
def get_feedback_summary() -> FeedbackSummaryResponse:
    """Return aggregated feedback stats."""
    total = len(_feedback_store)

    if total == 0:
        return FeedbackSummaryResponse(
            total_feedbacks=0,
            average_rating=0.0,
            rating_distribution={1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
            correction_type_counts={ct.value: 0 for ct in CorrectionType},
            recent_feedback_count=0,
        )

    # Average rating
    avg = sum(f["rating"] for f in _feedback_store) / total

    # Rating distribution
    dist: dict[int, int] = {i: 0 for i in range(1, 6)}
    for f in _feedback_store:
        dist[f["rating"]] = dist.get(f["rating"], 0) + 1

    # Correction type counts
    ct_counts: dict[str, int] = {ct.value: 0 for ct in CorrectionType}
    for f in _feedback_store:
        ct_counts[f["correction_type"]] = ct_counts.get(f["correction_type"], 0) + 1

    # Recent (last 7 days)
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    recent = sum(1 for f in _feedback_store if f["created_at"] >= cutoff)

    return FeedbackSummaryResponse(
        total_feedbacks=total,
        average_rating=round(avg, 2),
        rating_distribution=dist,
        correction_type_counts=ct_counts,
        recent_feedback_count=recent,
    )
