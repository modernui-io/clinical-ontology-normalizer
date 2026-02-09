"""CI/CD Pipeline Configuration & Management API endpoints (DEVOPS-5).

Provides endpoints for managing pipeline configurations, triggering runs,
viewing run results, and analyzing pipeline metrics and optimizations.

Endpoints:
    GET    /api/v1/cicd-pipeline/configs                        - List configs
    POST   /api/v1/cicd-pipeline/configs                        - Create config
    GET    /api/v1/cicd-pipeline/configs/{id}                   - Get config
    PUT    /api/v1/cicd-pipeline/configs/{id}                   - Update config
    DELETE /api/v1/cicd-pipeline/configs/{id}                   - Delete config
    POST   /api/v1/cicd-pipeline/configs/{id}/trigger           - Trigger run
    GET    /api/v1/cicd-pipeline/configs/{id}/metrics           - Config metrics
    GET    /api/v1/cicd-pipeline/configs/{id}/optimizations     - Optimizations
    GET    /api/v1/cicd-pipeline/configs/{id}/duration-estimate - Duration estimate
    GET    /api/v1/cicd-pipeline/runs                           - List runs
    GET    /api/v1/cicd-pipeline/runs/{id}                      - Get run
    GET    /api/v1/cicd-pipeline/metrics                        - Aggregate metrics
    GET    /api/v1/cicd-pipeline/flaky-stages                   - Flaky stages
    GET    /api/v1/cicd-pipeline/stages                         - List stage enum values
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.cicd_pipeline import (
    DurationEstimate,
    FlakyStagesResponse,
    PipelineConfig,
    PipelineConfigCreateRequest,
    PipelineConfigListResponse,
    PipelineConfigUpdateRequest,
    PipelineMetrics,
    PipelineOptimizationListResponse,
    PipelineRun,
    PipelineRunListResponse,
    PipelineStage,
    PipelineStatus,
    TriggerPipelineRequest,
    TriggerType,
)
from app.services.cicd_pipeline_service import get_cicd_pipeline_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/cicd-pipeline",
    tags=["CI/CD Pipeline"],
)


# ============================================================================
# Config CRUD
# ============================================================================


@router.get(
    "/configs",
    response_model=PipelineConfigListResponse,
    summary="List pipeline configurations",
)
async def list_configs(
    trigger: TriggerType | None = Query(None, description="Filter by trigger type"),
) -> PipelineConfigListResponse:
    """List all pipeline configurations with optional filtering."""
    svc = get_cicd_pipeline_service()
    items = svc.list_configs(trigger=trigger)
    return PipelineConfigListResponse(items=items, total=len(items))


@router.post(
    "/configs",
    response_model=PipelineConfig,
    status_code=status.HTTP_201_CREATED,
    summary="Create a pipeline configuration",
)
async def create_config(req: PipelineConfigCreateRequest) -> PipelineConfig:
    """Create a new CI/CD pipeline configuration."""
    svc = get_cicd_pipeline_service()
    return svc.create_config(req)


@router.get(
    "/configs/{config_id}",
    response_model=PipelineConfig,
    summary="Get a pipeline configuration",
)
async def get_config(config_id: str) -> PipelineConfig:
    """Get a pipeline configuration by ID."""
    svc = get_cicd_pipeline_service()
    config = svc.get_config(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Pipeline config {config_id} not found")
    return config


@router.put(
    "/configs/{config_id}",
    response_model=PipelineConfig,
    summary="Update a pipeline configuration",
)
async def update_config(config_id: str, req: PipelineConfigUpdateRequest) -> PipelineConfig:
    """Update an existing pipeline configuration."""
    svc = get_cicd_pipeline_service()
    updated = svc.update_config(config_id, req)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Pipeline config {config_id} not found")
    return updated


@router.delete(
    "/configs/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a pipeline configuration",
)
async def delete_config(config_id: str) -> None:
    """Delete a pipeline configuration and its associated runs."""
    svc = get_cicd_pipeline_service()
    deleted = svc.delete_config(config_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Pipeline config {config_id} not found")


# ============================================================================
# Trigger / Run
# ============================================================================


@router.post(
    "/configs/{config_id}/trigger",
    response_model=PipelineRun,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger a pipeline run",
)
async def trigger_pipeline(config_id: str, req: TriggerPipelineRequest) -> PipelineRun:
    """Manually trigger a pipeline run for the given configuration."""
    svc = get_cicd_pipeline_service()
    run = svc.trigger_pipeline(
        config_id=config_id,
        branch=req.branch,
        commit_sha=req.commit_sha,
        triggered_by=req.triggered_by,
    )
    if run is None:
        raise HTTPException(status_code=404, detail=f"Pipeline config {config_id} not found")
    return run


@router.get(
    "/configs/{config_id}/metrics",
    response_model=PipelineMetrics,
    summary="Get metrics for a pipeline configuration",
)
async def get_config_metrics(config_id: str) -> PipelineMetrics:
    """Get pipeline performance metrics scoped to a specific configuration."""
    svc = get_cicd_pipeline_service()
    config = svc.get_config(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Pipeline config {config_id} not found")
    return svc.get_metrics(config_id=config_id)


@router.get(
    "/configs/{config_id}/optimizations",
    response_model=PipelineOptimizationListResponse,
    summary="Analyze optimizations for a pipeline",
)
async def get_optimizations(config_id: str) -> PipelineOptimizationListResponse:
    """Analyze and recommend optimizations for a pipeline configuration."""
    svc = get_cicd_pipeline_service()
    config = svc.get_config(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Pipeline config {config_id} not found")
    opts = svc.analyze_optimizations(config_id)
    total_savings = sum(o.estimated_savings_seconds for o in opts)
    return PipelineOptimizationListResponse(
        config_id=config_id,
        optimizations=opts,
        total_estimated_savings_seconds=round(total_savings, 2),
    )


@router.get(
    "/configs/{config_id}/duration-estimate",
    response_model=DurationEstimate,
    summary="Estimate pipeline duration",
)
async def get_duration_estimate(config_id: str) -> DurationEstimate:
    """Estimate pipeline duration based on historical p50/p95 data."""
    svc = get_cicd_pipeline_service()
    config = svc.get_config(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Pipeline config {config_id} not found")
    return svc.estimate_pipeline_duration(config_id)


# ============================================================================
# Runs
# ============================================================================


@router.get(
    "/runs",
    response_model=PipelineRunListResponse,
    summary="List pipeline runs",
)
async def list_runs(
    config_id: str | None = Query(None, description="Filter by config ID"),
    run_status: PipelineStatus | None = Query(None, alias="status", description="Filter by status"),
    branch: str | None = Query(None, description="Filter by branch"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
) -> PipelineRunListResponse:
    """List pipeline runs with optional filters, sorted newest-first."""
    svc = get_cicd_pipeline_service()
    items = svc.list_runs(config_id=config_id, status=run_status, branch=branch, limit=limit)
    return PipelineRunListResponse(items=items, total=len(items))


@router.get(
    "/runs/{run_id}",
    response_model=PipelineRun,
    summary="Get a pipeline run",
)
async def get_run(run_id: str) -> PipelineRun:
    """Get a pipeline run by ID."""
    svc = get_cicd_pipeline_service()
    run = svc.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Pipeline run {run_id} not found")
    return run


# ============================================================================
# Aggregate Analytics
# ============================================================================


@router.get(
    "/metrics",
    response_model=PipelineMetrics,
    summary="Get aggregate pipeline metrics",
)
async def get_aggregate_metrics() -> PipelineMetrics:
    """Get aggregate metrics across all pipeline configurations."""
    svc = get_cicd_pipeline_service()
    return svc.get_metrics()


@router.get(
    "/flaky-stages",
    response_model=FlakyStagesResponse,
    summary="Detect flaky stages",
)
async def get_flaky_stages() -> FlakyStagesResponse:
    """Detect stages that intermittently fail across pipeline runs."""
    svc = get_cicd_pipeline_service()
    entries = svc.get_flaky_stages()
    return FlakyStagesResponse(flaky_stages=entries, total=len(entries))


@router.get(
    "/stages",
    summary="List available pipeline stages",
)
async def list_stages() -> list[dict[str, str]]:
    """Return all available pipeline stage types."""
    return [{"value": s.value, "label": s.value.replace("_", " ").title()} for s in PipelineStage]
