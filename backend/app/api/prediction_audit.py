"""Prediction Audit API endpoints.

Provides endpoints for logging and querying ML model predictions
for auditing, explainability, and model performance tracking.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.prediction_audit_service import (
    FeedbackType,
    PredictionOutcome,
    get_prediction_audit_service,
)

router = APIRouter(prefix="/predictions/audit", tags=["Prediction Audit"])


# ============================================================================
# Request/Response Models
# ============================================================================


class PredictionInputRequest(BaseModel):
    """Input feature for a prediction."""

    feature_name: str = Field(..., description="Feature name")
    feature_value: Any = Field(..., description="Feature value")
    feature_importance: float = Field(default=0.0, ge=0, le=1, description="Feature importance score")


class LogPredictionRequest(BaseModel):
    """Request to log a prediction."""

    model_name: str = Field(..., description="Name of the ML model")
    model_version: str = Field(default="1.0.0", description="Model version")
    prediction_type: str = Field(..., description="Type of prediction (mortality, readmission, etc.)")
    prediction_value: float | str = Field(..., description="Predicted value")
    inputs: list[PredictionInputRequest] = Field(..., min_length=1, description="Input features")
    patient_id: str | None = Field(None, description="Patient identifier")
    prediction_confidence: float | None = Field(None, ge=0, le=1, description="Confidence score")
    prediction_tier: str | None = Field(None, description="Risk tier (low, medium, high, critical)")
    explanation: str | None = Field(None, description="Human-readable explanation")
    latency_ms: float = Field(default=0.0, ge=0, description="Prediction latency in ms")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = {
        "json_schema_extra": {
            "example": {
                "model_name": "mortality_risk_v2",
                "model_version": "2.1.0",
                "prediction_type": "mortality",
                "prediction_value": 0.72,
                "inputs": [
                    {"feature_name": "age", "feature_value": 75, "feature_importance": 0.25},
                    {"feature_name": "charlson_score", "feature_value": 4, "feature_importance": 0.35},
                    {"feature_name": "icu_admission", "feature_value": True, "feature_importance": 0.20},
                ],
                "patient_id": "P12345",
                "prediction_confidence": 0.89,
                "prediction_tier": "high",
                "explanation": "High risk due to advanced age and multiple comorbidities",
                "latency_ms": 45.3,
            }
        }
    }


class UpdateOutcomeRequest(BaseModel):
    """Request to update prediction outcome."""

    outcome: str = Field(..., description="Outcome: correct, incorrect, partial, unknown")

    model_config = {
        "json_schema_extra": {
            "example": {"outcome": "correct"}
        }
    }


class AddFeedbackRequest(BaseModel):
    """Request to add feedback to a prediction."""

    feedback_type: str = Field(..., description="Type: thumbs_up, thumbs_down, flag, correction, comment")
    value: Any | None = Field(None, description="Feedback value (e.g., corrected prediction)")
    comment: str | None = Field(None, description="Optional comment")

    model_config = {
        "json_schema_extra": {
            "example": {
                "feedback_type": "correction",
                "value": 0.45,
                "comment": "Actual risk was lower based on follow-up",
            }
        }
    }


class PredictionInputResponse(BaseModel):
    """Input feature in response."""

    feature_name: str
    feature_value: Any
    feature_importance: float


class PredictionAuditResponse(BaseModel):
    """Response for a prediction audit record."""

    id: str = Field(..., description="Audit record ID")
    model_name: str
    model_version: str
    patient_id: str | None
    prediction_type: str
    prediction_value: float | str
    prediction_confidence: float | None
    prediction_tier: str | None
    inputs: list[PredictionInputResponse]
    explanation: str | None
    created_at: str
    user_id: str | None
    latency_ms: float
    outcome: str
    outcome_updated_at: str | None
    feedback_count: int


class PredictionListResponse(BaseModel):
    """Response for list of predictions."""

    total: int
    predictions: list[PredictionAuditResponse]


class DriftMetricsResponse(BaseModel):
    """Response for model drift metrics."""

    model_name: str
    period_start: str
    period_end: str
    total_predictions: int
    mean_confidence: float
    confidence_std: float
    distribution: dict[str, int]
    accuracy: float | None


class StatsResponse(BaseModel):
    """Response for overall statistics."""

    total_predictions: int
    by_model: dict[str, int]
    by_type: dict[str, int]
    by_outcome: dict[str, int]
    with_feedback: int


class OutcomesResponse(BaseModel):
    """Response for available outcomes."""

    outcomes: list[dict[str, str]]


class FeedbackTypesResponse(BaseModel):
    """Response for available feedback types."""

    feedback_types: list[dict[str, str]]


# ============================================================================
# Helper Functions
# ============================================================================


def _audit_to_response(audit) -> PredictionAuditResponse:
    """Convert PredictionAudit to response model."""
    return PredictionAuditResponse(
        id=audit.id,
        model_name=audit.model_name,
        model_version=audit.model_version,
        patient_id=audit.patient_id,
        prediction_type=audit.prediction_type,
        prediction_value=audit.prediction_value,
        prediction_confidence=audit.prediction_confidence,
        prediction_tier=audit.prediction_tier,
        inputs=[
            PredictionInputResponse(
                feature_name=inp.feature_name,
                feature_value=inp.feature_value,
                feature_importance=inp.feature_importance,
            )
            for inp in audit.inputs
        ],
        explanation=audit.explanation,
        created_at=audit.created_at.isoformat(),
        user_id=audit.user_id,
        latency_ms=audit.latency_ms,
        outcome=audit.outcome.value,
        outcome_updated_at=audit.outcome_updated_at.isoformat() if audit.outcome_updated_at else None,
        feedback_count=len(audit.feedback),
    )


# ============================================================================
# Endpoints - Static routes first
# ============================================================================


@router.get(
    "",
    response_model=PredictionListResponse,
    summary="List prediction audits",
    description="Get a list of prediction audit records with optional filtering.",
)
async def list_audits(
    model_name: str | None = Query(None, description="Filter by model name"),
    patient_id: str | None = Query(None, description="Filter by patient ID"),
    prediction_type: str | None = Query(None, description="Filter by prediction type"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
) -> PredictionListResponse:
    """List prediction audit records."""
    service = get_prediction_audit_service()

    audits = service.list_audits(
        model_name=model_name,
        patient_id=patient_id,
        prediction_type=prediction_type,
        limit=limit,
    )

    return PredictionListResponse(
        total=len(audits),
        predictions=[_audit_to_response(a) for a in audits],
    )


@router.post(
    "",
    response_model=PredictionAuditResponse,
    summary="Log prediction",
    description="Log a new ML model prediction for audit.",
)
async def log_prediction(request: LogPredictionRequest) -> PredictionAuditResponse:
    """Log a new prediction."""
    service = get_prediction_audit_service()

    audit = service.log_prediction(
        model_name=request.model_name,
        model_version=request.model_version,
        prediction_type=request.prediction_type,
        prediction_value=request.prediction_value,
        inputs=[inp.model_dump() for inp in request.inputs],
        patient_id=request.patient_id,
        prediction_confidence=request.prediction_confidence,
        prediction_tier=request.prediction_tier,
        explanation=request.explanation,
        latency_ms=request.latency_ms,
        metadata=request.metadata,
    )

    return _audit_to_response(audit)


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Get statistics",
    description="Get overall prediction audit statistics.",
)
async def get_stats() -> StatsResponse:
    """Get prediction audit statistics."""
    service = get_prediction_audit_service()
    stats = service.get_stats()
    return StatsResponse(**stats)


@router.get(
    "/outcomes",
    response_model=OutcomesResponse,
    summary="List outcomes",
    description="Get list of available prediction outcomes.",
)
async def list_outcomes() -> OutcomesResponse:
    """List available prediction outcomes."""
    outcomes = [
        {"value": o.value, "name": o.name.replace("_", " ").title()}
        for o in PredictionOutcome
    ]
    return OutcomesResponse(outcomes=outcomes)


@router.get(
    "/feedback-types",
    response_model=FeedbackTypesResponse,
    summary="List feedback types",
    description="Get list of available feedback types.",
)
async def list_feedback_types() -> FeedbackTypesResponse:
    """List available feedback types."""
    feedback_types = [
        {"value": ft.value, "name": ft.name.replace("_", " ").title()}
        for ft in FeedbackType
    ]
    return FeedbackTypesResponse(feedback_types=feedback_types)


@router.get(
    "/drift/{model_name}",
    response_model=DriftMetricsResponse,
    summary="Get drift metrics",
    description="Get model drift metrics for a specified period.",
)
async def get_drift_metrics(
    model_name: str,
    period_days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
) -> DriftMetricsResponse:
    """Get drift metrics for a model."""
    service = get_prediction_audit_service()
    metrics = service.get_drift_metrics(model_name, period_days)

    return DriftMetricsResponse(
        model_name=metrics.model_name,
        period_start=metrics.period_start.isoformat(),
        period_end=metrics.period_end.isoformat(),
        total_predictions=metrics.total_predictions,
        mean_confidence=metrics.mean_confidence,
        confidence_std=metrics.confidence_std,
        distribution=metrics.distribution,
        accuracy=metrics.accuracy,
    )


# ============================================================================
# Endpoints - Parameterized routes
# ============================================================================


@router.get(
    "/{audit_id}",
    response_model=PredictionAuditResponse,
    summary="Get audit record",
    description="Get a specific prediction audit record.",
)
async def get_audit(audit_id: str) -> PredictionAuditResponse:
    """Get a specific audit record."""
    service = get_prediction_audit_service()
    audit = service.get_audit(audit_id)

    if not audit:
        raise HTTPException(status_code=404, detail="Audit record not found")

    return _audit_to_response(audit)


@router.put(
    "/{audit_id}/outcome",
    response_model=PredictionAuditResponse,
    summary="Update outcome",
    description="Update the outcome for a prediction after ground truth is known.",
)
async def update_outcome(audit_id: str, request: UpdateOutcomeRequest) -> PredictionAuditResponse:
    """Update prediction outcome."""
    service = get_prediction_audit_service()

    try:
        outcome = PredictionOutcome(request.outcome)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid outcome: {request.outcome}")

    audit = service.update_outcome(audit_id, outcome)
    if not audit:
        raise HTTPException(status_code=404, detail="Audit record not found")

    return _audit_to_response(audit)


@router.post(
    "/{audit_id}/feedback",
    response_model=PredictionAuditResponse,
    summary="Add feedback",
    description="Add user feedback to a prediction.",
)
async def add_feedback(audit_id: str, request: AddFeedbackRequest) -> PredictionAuditResponse:
    """Add feedback to a prediction."""
    service = get_prediction_audit_service()

    try:
        feedback_type = FeedbackType(request.feedback_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid feedback type: {request.feedback_type}")

    audit = service.add_feedback(
        audit_id=audit_id,
        feedback_type=feedback_type,
        value=request.value,
        comment=request.comment,
    )

    if not audit:
        raise HTTPException(status_code=404, detail="Audit record not found")

    return _audit_to_response(audit)
