"""Risk Thresholds API endpoints.

Provides endpoints for configuring risk model thresholds for
patient risk classification (mortality, readmission, etc.).
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.risk_thresholds_service import (
    RiskModel,
    RiskTier,
    get_risk_thresholds_service,
)

router = APIRouter(prefix="/risk-thresholds", tags=["Risk Thresholds"])


# ============================================================================
# Request/Response Models
# ============================================================================


class ThresholdConfigRequest(BaseModel):
    """Request for a threshold configuration."""

    tier: str = Field(..., description="Risk tier: low, medium, high, critical")
    min_score: float = Field(..., ge=0, le=1, description="Minimum score for this tier")
    max_score: float = Field(..., ge=0, le=1, description="Maximum score for this tier")
    color: str = Field(default="#000000", description="Display color (hex)")
    label: str = Field(..., description="Human-readable label")
    alert_enabled: bool = Field(default=True, description="Whether alerts are enabled")

    model_config = {
        "json_schema_extra": {
            "example": {
                "tier": "high",
                "min_score": 0.5,
                "max_score": 0.8,
                "color": "#FF9800",
                "label": "High Risk",
                "alert_enabled": True,
            }
        }
    }


class UpdateThresholdsRequest(BaseModel):
    """Request to update model thresholds."""

    thresholds: list[ThresholdConfigRequest] = Field(
        ...,
        min_length=1,
        description="Threshold configurations (must cover 0-1 range without gaps)",
    )
    description: str | None = Field(None, description="Updated description")

    model_config = {
        "json_schema_extra": {
            "example": {
                "thresholds": [
                    {"tier": "low", "min_score": 0.0, "max_score": 0.2, "color": "#4CAF50", "label": "Low Risk"},
                    {"tier": "medium", "min_score": 0.2, "max_score": 0.5, "color": "#FFC107", "label": "Moderate Risk"},
                    {"tier": "high", "min_score": 0.5, "max_score": 0.8, "color": "#FF9800", "label": "High Risk"},
                    {"tier": "critical", "min_score": 0.8, "max_score": 1.0, "color": "#F44336", "label": "Critical Risk"},
                ],
                "description": "Custom mortality risk thresholds",
            }
        }
    }


class ClassifyRequest(BaseModel):
    """Request to classify a risk score."""

    score: float = Field(..., ge=0, le=1, description="Risk score to classify")

    model_config = {
        "json_schema_extra": {
            "example": {"score": 0.65}
        }
    }


class ThresholdConfigResponse(BaseModel):
    """Response for a threshold configuration."""

    tier: str
    min_score: float
    max_score: float
    color: str
    label: str
    alert_enabled: bool


class ModelThresholdsResponse(BaseModel):
    """Response for model thresholds."""

    model: str = Field(..., description="Risk model name")
    thresholds: list[ThresholdConfigResponse] = Field(..., description="Threshold configurations")
    description: str = Field(..., description="Model description")
    version: str = Field(..., description="Configuration version")
    updated_at: str = Field(..., description="Last update timestamp")
    updated_by: str = Field(..., description="User who made last update")


class ModelsListResponse(BaseModel):
    """Response for list of models."""

    models: list[str] = Field(..., description="Available risk models")
    total: int = Field(..., description="Total number of models")


class AllThresholdsResponse(BaseModel):
    """Response for all thresholds."""

    thresholds: list[ModelThresholdsResponse] = Field(..., description="All model thresholds")
    total: int = Field(..., description="Total number of models")


class ClassifyResponse(BaseModel):
    """Response for score classification."""

    score: float = Field(..., description="Input score")
    tier: str = Field(..., description="Risk tier")
    label: str = Field(..., description="Human-readable label")
    color: str = Field(..., description="Display color")
    alert_enabled: bool = Field(..., description="Whether alerts are enabled")


class TiersResponse(BaseModel):
    """Response for available tiers."""

    tiers: list[dict[str, str]] = Field(..., description="Available risk tiers")


# ============================================================================
# Helper Functions
# ============================================================================


def _thresholds_to_response(mt) -> ModelThresholdsResponse:
    """Convert ModelThresholds to response model."""
    return ModelThresholdsResponse(
        model=mt.model.value,
        thresholds=[
            ThresholdConfigResponse(
                tier=t.tier.value,
                min_score=t.min_score,
                max_score=t.max_score,
                color=t.color,
                label=t.label,
                alert_enabled=t.alert_enabled,
            )
            for t in mt.thresholds
        ],
        description=mt.description,
        version=mt.version,
        updated_at=mt.updated_at.isoformat(),
        updated_by=mt.updated_by,
    )


# ============================================================================
# Endpoints - Static routes first
# ============================================================================


@router.get(
    "",
    response_model=AllThresholdsResponse,
    summary="List all thresholds",
    description="Get threshold configurations for all risk models.",
)
async def list_all_thresholds() -> AllThresholdsResponse:
    """List thresholds for all risk models."""
    service = get_risk_thresholds_service()
    all_thresholds = service.list_all_thresholds()

    return AllThresholdsResponse(
        thresholds=[_thresholds_to_response(mt) for mt in all_thresholds],
        total=len(all_thresholds),
    )


@router.get(
    "/models",
    response_model=ModelsListResponse,
    summary="List risk models",
    description="Get list of available risk models.",
)
async def list_models() -> ModelsListResponse:
    """List all available risk models."""
    service = get_risk_thresholds_service()
    models = service.list_models()

    return ModelsListResponse(
        models=[m.value for m in models],
        total=len(models),
    )


@router.get(
    "/tiers",
    response_model=TiersResponse,
    summary="List risk tiers",
    description="Get list of available risk tiers.",
)
async def list_tiers() -> TiersResponse:
    """List available risk tiers."""
    tiers = [
        {"value": tier.value, "name": tier.name.replace("_", " ").title()}
        for tier in RiskTier
    ]
    return TiersResponse(tiers=tiers)


# ============================================================================
# Endpoints - Parameterized routes
# ============================================================================


@router.get(
    "/{model}",
    response_model=ModelThresholdsResponse,
    summary="Get model thresholds",
    description="Get threshold configuration for a specific risk model.",
)
async def get_thresholds(model: str) -> ModelThresholdsResponse:
    """Get thresholds for a specific model."""
    service = get_risk_thresholds_service()

    try:
        risk_model = RiskModel(model)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown model: {model}")

    thresholds = service.get_thresholds(risk_model)
    if not thresholds:
        raise HTTPException(status_code=404, detail=f"Thresholds not found for model: {model}")

    return _thresholds_to_response(thresholds)


@router.put(
    "/{model}",
    response_model=ModelThresholdsResponse,
    summary="Update model thresholds",
    description="Update threshold configuration for a risk model.",
)
async def update_thresholds(model: str, request: UpdateThresholdsRequest) -> ModelThresholdsResponse:
    """Update thresholds for a model."""
    service = get_risk_thresholds_service()

    try:
        risk_model = RiskModel(model)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown model: {model}")

    try:
        thresholds_data = [t.model_dump() for t in request.thresholds]
        updated = service.update_thresholds(
            model=risk_model,
            thresholds=thresholds_data,
            updated_by="anonymous",  # Would come from auth
            description=request.description,
        )
        return _thresholds_to_response(updated)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{model}/defaults",
    response_model=ModelThresholdsResponse,
    summary="Get default thresholds",
    description="Get the default threshold configuration for a model.",
)
async def get_defaults(model: str) -> ModelThresholdsResponse:
    """Get default thresholds for a model."""
    service = get_risk_thresholds_service()

    try:
        risk_model = RiskModel(model)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown model: {model}")

    defaults = service.get_defaults(risk_model)
    if not defaults:
        raise HTTPException(status_code=404, detail=f"Defaults not found for model: {model}")

    return _thresholds_to_response(defaults)


@router.post(
    "/{model}/reset",
    response_model=ModelThresholdsResponse,
    summary="Reset to defaults",
    description="Reset a model's thresholds to default values.",
)
async def reset_to_defaults(model: str) -> ModelThresholdsResponse:
    """Reset thresholds to defaults."""
    service = get_risk_thresholds_service()

    try:
        risk_model = RiskModel(model)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown model: {model}")

    reset = service.reset_to_defaults(risk_model, reset_by="anonymous")
    if not reset:
        raise HTTPException(status_code=404, detail=f"Cannot reset model: {model}")

    return _thresholds_to_response(reset)


@router.post(
    "/{model}/classify",
    response_model=ClassifyResponse,
    summary="Classify risk score",
    description="Classify a risk score using the model's thresholds.",
)
async def classify_score(model: str, request: ClassifyRequest) -> ClassifyResponse:
    """Classify a risk score using model thresholds."""
    service = get_risk_thresholds_service()

    try:
        risk_model = RiskModel(model)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown model: {model}")

    try:
        result = service.classify_score(risk_model, request.score)
        return ClassifyResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
