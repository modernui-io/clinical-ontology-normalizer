"""Pydantic schemas for clinician feedback capture (P2-009)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class CorrectionType(str, Enum):
    """How the clinician rated the clinical response."""

    AGREE = "agree"
    DISAGREE = "disagree"
    PARTIAL = "partial"
    IRRELEVANT = "irrelevant"


class ClinicianFeedbackCreate(BaseModel):
    """Request body for submitting clinician feedback."""

    query_id: str = Field(..., description="ID of the original query")
    response_id: str = Field(..., description="ID of the clinical response")
    rating: int = Field(..., ge=1, le=5, description="Star rating 1-5")
    feedback_text: str | None = Field(None, description="Optional free-text correction")
    correction_type: CorrectionType = Field(
        ..., description="Clinician assessment of response accuracy"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "query_id": "q-abc-123",
                "response_id": "r-def-456",
                "rating": 4,
                "feedback_text": "Mostly correct but missed the allergy history.",
                "correction_type": "partial",
            }
        }
    }


class ClinicianFeedbackResponse(BaseModel):
    """Response body after recording clinician feedback."""

    id: str
    query_id: str
    response_id: str
    rating: int
    feedback_text: str | None
    correction_type: CorrectionType
    created_at: datetime


class FeedbackSummaryResponse(BaseModel):
    """Aggregated feedback statistics."""

    total_feedbacks: int
    average_rating: float
    rating_distribution: dict[int, int]
    correction_type_counts: dict[str, int]
    recent_feedback_count: int = Field(
        ..., description="Feedbacks in the last 7 days"
    )
