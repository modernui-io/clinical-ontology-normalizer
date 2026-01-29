"""Model Registry API endpoints.

Provides endpoints for ML model lifecycle management:
- Model registration and listing
- Version management
- Stage transitions (dev -> staging -> production)
- Model metadata and metrics
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.model_registry_service import (
    ModelStage,
    ModelType,
    get_model_registry_service,
)

router = APIRouter(prefix="/model-registry", tags=["ML Model Registry"])


# ============================================================================
# Request/Response Models
# ============================================================================


class RegisterModelRequest(BaseModel):
    """Request to register a new model."""

    name: str = Field(..., min_length=1, max_length=255, description="Model name")
    model_type: str = Field(..., description="Model type: classification, regression, etc.")
    description: str = Field(default="", description="Model description")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "sepsis_risk_model",
                "model_type": "classification",
                "description": "Sepsis risk prediction model",
                "tags": ["risk", "sepsis", "clinical"],
            }
        }
    }


class AddVersionRequest(BaseModel):
    """Request to add a new version."""

    version: str = Field(..., description="Version string (e.g., 1.0.0)")
    description: str = Field(default="", description="Version description")
    metrics: dict[str, float] = Field(default_factory=dict, description="Performance metrics")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Model parameters")
    artifact_path: str | None = Field(None, description="Path to model artifacts")
    signature: dict[str, Any] | None = Field(None, description="Input/output schema")


class TransitionStageRequest(BaseModel):
    """Request to transition model stage."""

    stage: str = Field(..., description="Target stage: development, staging, production, archived")


class VersionResponse(BaseModel):
    """Response for a model version."""

    version: str = Field(..., description="Version string")
    stage: str = Field(..., description="Lifecycle stage")
    created_at: str = Field(..., description="Creation timestamp")
    created_by: str = Field(..., description="Creator")
    description: str = Field(..., description="Description")
    metrics: dict[str, float] = Field(..., description="Performance metrics")
    parameters: dict[str, Any] = Field(..., description="Model parameters")
    artifact_path: str | None = Field(None, description="Artifact path")
    signature: dict[str, Any] | None = Field(None, description="I/O signature")
    is_current: bool = Field(..., description="Is current version")


class ModelResponse(BaseModel):
    """Response for a registered model."""

    id: str = Field(..., description="Model ID")
    name: str = Field(..., description="Model name")
    model_type: str = Field(..., description="Model type")
    description: str = Field(..., description="Description")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Update timestamp")
    created_by: str = Field(..., description="Creator")
    tags: list[str] = Field(..., description="Tags")
    versions: list[VersionResponse] = Field(..., description="Model versions")
    latest_version: str | None = Field(None, description="Latest version")
    production_version: str | None = Field(None, description="Production version")


class ModelListResponse(BaseModel):
    """Response for model list."""

    total: int = Field(..., description="Total models")
    models: list[ModelResponse] = Field(..., description="Model list")


class StatsResponse(BaseModel):
    """Response for registry statistics."""

    total_models: int = Field(..., description="Total registered models")
    total_versions: int = Field(..., description="Total model versions")
    production_models: int = Field(..., description="Models in production")
    models_by_type: dict[str, int] = Field(..., description="Models by type")


class ModelTypesResponse(BaseModel):
    """Response for model types."""

    model_types: list[dict[str, str]] = Field(..., description="Available model types")


class StagesResponse(BaseModel):
    """Response for lifecycle stages."""

    stages: list[dict[str, str]] = Field(..., description="Available stages")


# ============================================================================
# Helper Functions
# ============================================================================


def _version_to_response(v) -> VersionResponse:
    """Convert ModelVersion to response model."""
    return VersionResponse(
        version=v.version,
        stage=v.stage.value,
        created_at=v.created_at.isoformat(),
        created_by=v.created_by,
        description=v.description,
        metrics=v.metrics,
        parameters=v.parameters,
        artifact_path=v.artifact_path,
        signature=v.signature,
        is_current=v.is_current,
    )


def _model_to_response(m) -> ModelResponse:
    """Convert RegisteredModel to response model."""
    return ModelResponse(
        id=m.id,
        name=m.name,
        model_type=m.model_type.value,
        description=m.description,
        created_at=m.created_at.isoformat(),
        updated_at=m.updated_at.isoformat(),
        created_by=m.created_by,
        tags=m.tags,
        versions=[_version_to_response(v) for v in m.versions],
        latest_version=m.latest_version,
        production_version=m.production_version,
    )


# ============================================================================
# Endpoints - Static routes first
# ============================================================================


@router.get(
    "",
    response_model=ModelListResponse,
    summary="List models",
    description="Get a list of registered ML models.",
)
async def list_models(
    model_type: str | None = Query(None, description="Filter by model type"),
    stage: str | None = Query(None, description="Filter by stage"),
    tag: str | None = Query(None, description="Filter by tag"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
) -> ModelListResponse:
    """List registered models."""
    service = get_model_registry_service()

    model_type_enum = None
    if model_type:
        try:
            model_type_enum = ModelType(model_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid model_type: {model_type}")

    stage_enum = None
    if stage:
        try:
            stage_enum = ModelStage(stage)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid stage: {stage}")

    models = service.list_models(
        model_type=model_type_enum,
        stage=stage_enum,
        tag=tag,
        limit=limit,
    )

    return ModelListResponse(
        total=len(models),
        models=[_model_to_response(m) for m in models],
    )


@router.post(
    "",
    response_model=ModelResponse,
    summary="Register model",
    description="Register a new ML model.",
)
async def register_model(request: RegisterModelRequest) -> ModelResponse:
    """Register a new model."""
    service = get_model_registry_service()

    try:
        model_type = ModelType(request.model_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid model_type: {request.model_type}")

    model = service.register_model(
        name=request.name,
        model_type=model_type,
        description=request.description,
        created_by="api",
        tags=request.tags,
        metadata=request.metadata,
    )

    return _model_to_response(model)


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Get statistics",
    description="Get model registry statistics.",
)
async def get_stats() -> StatsResponse:
    """Get registry statistics."""
    service = get_model_registry_service()
    stats = service.get_stats()
    return StatsResponse(**stats)


@router.get(
    "/types",
    response_model=ModelTypesResponse,
    summary="List model types",
    description="Get available model types.",
)
async def list_model_types() -> ModelTypesResponse:
    """List available model types."""
    model_types = [
        {"value": t.value, "name": t.name.replace("_", " ").title()}
        for t in ModelType
    ]
    return ModelTypesResponse(model_types=model_types)


@router.get(
    "/stages",
    response_model=StagesResponse,
    summary="List stages",
    description="Get available lifecycle stages.",
)
async def list_stages() -> StagesResponse:
    """List available stages."""
    stages = [
        {"value": s.value, "name": s.name.replace("_", " ").title()}
        for s in ModelStage
    ]
    return StagesResponse(stages=stages)


# ============================================================================
# Endpoints - Parameterized routes
# ============================================================================


@router.get(
    "/{model_id}",
    response_model=ModelResponse,
    summary="Get model",
    description="Get a specific model by ID.",
)
async def get_model(model_id: str) -> ModelResponse:
    """Get a specific model."""
    service = get_model_registry_service()
    model = service.get_model(model_id)

    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    return _model_to_response(model)


@router.delete(
    "/{model_id}",
    summary="Delete model",
    description="Delete a model and all its versions.",
)
async def delete_model(model_id: str) -> dict[str, bool]:
    """Delete a model."""
    service = get_model_registry_service()
    deleted = service.delete_model(model_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Model not found")

    return {"deleted": True}


@router.post(
    "/{model_id}/versions",
    response_model=VersionResponse,
    summary="Add version",
    description="Add a new version to a model.",
)
async def add_version(model_id: str, request: AddVersionRequest) -> VersionResponse:
    """Add a new version to a model."""
    service = get_model_registry_service()

    version = service.add_version(
        model_id=model_id,
        version=request.version,
        description=request.description,
        created_by="api",
        metrics=request.metrics,
        parameters=request.parameters,
        artifact_path=request.artifact_path,
        signature=request.signature,
    )

    if not version:
        raise HTTPException(
            status_code=400,
            detail="Failed to add version. Model not found or version already exists.",
        )

    return _version_to_response(version)


@router.post(
    "/{model_id}/versions/{version}/stage",
    response_model=VersionResponse,
    summary="Transition stage",
    description="Transition a model version to a new stage.",
)
async def transition_stage(
    model_id: str,
    version: str,
    request: TransitionStageRequest,
) -> VersionResponse:
    """Transition a model version to a new stage."""
    service = get_model_registry_service()

    try:
        new_stage = ModelStage(request.stage)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid stage: {request.stage}")

    version_obj = service.transition_stage(model_id, version, new_stage)

    if not version_obj:
        raise HTTPException(
            status_code=404,
            detail="Model or version not found",
        )

    return _version_to_response(version_obj)
