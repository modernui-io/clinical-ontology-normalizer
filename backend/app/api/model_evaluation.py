"""Model Evaluation API endpoints.

Provides endpoints for ML model evaluation tracking:
- Register models
- Record evaluation runs
- Retrieve evaluation history
- Compare model versions
- Check for performance regressions
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.model_evaluation import (
    ComparisonResult,
    EvaluationRun,
    ModelInfo,
    ModelListResponse,
    RecordEvaluationRequest,
    RegressionCheck,
    RegisterModelRequest,
)
from app.services.model_evaluation_service import get_model_evaluation_service

router = APIRouter(prefix="/ml", tags=["ML Model Evaluation"])


# ============================================================================
# Model registration
# ============================================================================


@router.post(
    "/models",
    response_model=ModelInfo,
    summary="Register a model",
    description="Register a new model with metadata for evaluation tracking.",
)
async def register_model(request: RegisterModelRequest) -> ModelInfo:
    """Register a model for evaluation tracking."""
    service = get_model_evaluation_service()
    return service.register_model(
        name=request.name,
        version=request.version,
        model_type=request.model_type,
        description=request.description,
    )


@router.get(
    "/models",
    response_model=ModelListResponse,
    summary="List registered models",
    description="List all registered models and their versions.",
)
async def list_models() -> ModelListResponse:
    """List all registered models."""
    service = get_model_evaluation_service()
    models = service.list_models()
    return ModelListResponse(total=len(models), models=models)


# ============================================================================
# Evaluation runs
# ============================================================================


@router.post(
    "/evaluations",
    response_model=EvaluationRun,
    summary="Record an evaluation run",
    description="Record metrics from an evaluation run for a model version.",
)
async def record_evaluation(request: RecordEvaluationRequest) -> EvaluationRun:
    """Record an evaluation run."""
    service = get_model_evaluation_service()
    return service.record_evaluation(
        model_name=request.model_name,
        model_version=request.model_version,
        dataset_name=request.dataset_name,
        metrics=request.metrics,
        metadata=request.metadata,
    )


# ============================================================================
# History & comparison
# ============================================================================


@router.get(
    "/models/{name}/history",
    response_model=list[EvaluationRun],
    summary="Get evaluation history",
    description="Get the evaluation history for a model, optionally filtered by version.",
)
async def get_model_history(
    name: str,
    version: str | None = Query(None, description="Filter by model version"),
) -> list[EvaluationRun]:
    """Get evaluation history for a model."""
    service = get_model_evaluation_service()
    return service.get_model_history(name, version=version)


@router.get(
    "/models/{name}/compare",
    response_model=ComparisonResult,
    summary="Compare two versions",
    description="Compare evaluation metrics between two versions of a model.",
)
async def compare_versions(
    name: str,
    version_a: str = Query(..., description="Baseline version"),
    version_b: str = Query(..., description="Comparison version"),
) -> ComparisonResult:
    """Compare two model versions."""
    service = get_model_evaluation_service()
    try:
        return service.compare_versions(name, version_a, version_b)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/models/{name}/best",
    response_model=EvaluationRun | None,
    summary="Get best model version",
    description="Get the evaluation run with the highest value for a given metric.",
)
async def get_best_model(
    name: str,
    metric: str = Query(..., description="Metric to optimize"),
) -> EvaluationRun | None:
    """Get the best model version by a metric."""
    service = get_model_evaluation_service()
    result = service.get_best_model(name, metric)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No evaluations with metric '{metric}' found for model '{name}'",
        )
    return result


@router.get(
    "/models/{name}/regression-check",
    response_model=RegressionCheck,
    summary="Check for regression",
    description="Check whether the latest evaluation regressed on a given metric.",
)
async def check_regression(
    name: str,
    metric: str = Query(..., description="Metric to check"),
    threshold: float = Query(0.0, description="Acceptable degradation threshold"),
) -> RegressionCheck:
    """Check for metric regression."""
    service = get_model_evaluation_service()
    try:
        return service.check_regression(name, metric, threshold)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
