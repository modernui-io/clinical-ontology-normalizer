"""Drift Detection API endpoints.

Provides endpoints for monitoring model and data drift
in clinical trial patient screening pipelines:
- Capture and manage baseline snapshots
- Run drift analysis against baselines
- Generate drift reports
- List and manage drift monitors
- Record data points for monitoring
- View drift history over time
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.drift_detection import (
    BaselineCreate,
    BaselineListResponse,
    BaselineResponse,
    DataPointRecord,
    DataPointResponse,
    DriftAnalysis,
    DriftAnalysisRequest,
    DriftHistory,
    DriftReport,
    MonitorListResponse,
)
from app.services.drift_detection_service import get_drift_detection_service

router = APIRouter(prefix="/drift", tags=["Drift Detection"])


# ============================================================================
# Baseline management
# ============================================================================


@router.post(
    "/baselines",
    response_model=BaselineResponse,
    summary="Capture baseline snapshot",
    description="Capture the current data distribution as a reference baseline.",
)
async def create_baseline(request: BaselineCreate) -> BaselineResponse:
    """Create a new baseline snapshot."""
    service = get_drift_detection_service()
    return service.create_baseline(
        name=request.name,
        feature_distributions=request.feature_distributions,
        sample_count=request.sample_count,
    )


@router.get(
    "/baselines",
    response_model=BaselineListResponse,
    summary="List baselines",
    description="List all stored baseline snapshots.",
)
async def list_baselines() -> BaselineListResponse:
    """List all baselines."""
    service = get_drift_detection_service()
    baselines = service.list_baselines()
    return BaselineListResponse(total=len(baselines), baselines=baselines)


@router.get(
    "/baselines/{baseline_id}",
    response_model=BaselineResponse,
    summary="Get baseline detail",
    description="Get a specific baseline by ID.",
)
async def get_baseline(baseline_id: str) -> BaselineResponse:
    """Get baseline detail."""
    service = get_drift_detection_service()
    baseline = service.get_baseline(baseline_id)
    if baseline is None:
        raise HTTPException(status_code=404, detail=f"Baseline '{baseline_id}' not found")
    return baseline


# ============================================================================
# Drift analysis
# ============================================================================


@router.post(
    "/analyze",
    response_model=DriftAnalysis,
    summary="Run drift analysis",
    description="Run drift analysis comparing current distributions against a baseline.",
)
async def analyze_drift(request: DriftAnalysisRequest) -> DriftAnalysis:
    """Run drift analysis against a baseline."""
    service = get_drift_detection_service()
    try:
        return service.analyze_drift(
            baseline_id=request.baseline_id,
            current_distributions=request.current_distributions,
            current_sample_count=request.current_sample_count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ============================================================================
# Drift report
# ============================================================================


@router.get(
    "/report",
    response_model=DriftReport | None,
    summary="Latest drift report",
    description="Get the most recently generated drift report.",
)
async def get_drift_report() -> DriftReport | None:
    """Get the latest drift report."""
    service = get_drift_detection_service()
    report = service.get_latest_report()
    if report is None:
        raise HTTPException(status_code=404, detail="No drift report available yet")
    return report


# ============================================================================
# Monitors
# ============================================================================


@router.get(
    "/monitors",
    response_model=MonitorListResponse,
    summary="List active monitors",
    description="List all drift monitors with their current status.",
)
async def list_monitors() -> MonitorListResponse:
    """List all monitors."""
    service = get_drift_detection_service()
    monitors = service.list_monitors()
    return MonitorListResponse(total=len(monitors), monitors=monitors)


# ============================================================================
# Data recording
# ============================================================================


@router.post(
    "/record",
    response_model=DataPointResponse,
    summary="Record data point",
    description="Record a new data point for a drift monitor.",
)
async def record_data_point(request: DataPointRecord) -> DataPointResponse:
    """Record a data point for a monitor."""
    service = get_drift_detection_service()
    return service.record_data_point(
        monitor_name=request.monitor_name,
        value=request.value,
        metadata=request.metadata,
        timestamp=request.timestamp,
    )


# ============================================================================
# Drift history
# ============================================================================


@router.get(
    "/history",
    response_model=DriftHistory,
    summary="Drift score over time",
    description="Get drift score history entries.",
)
async def get_drift_history(
    limit: int = Query(100, ge=1, le=1000, description="Max entries to return"),
) -> DriftHistory:
    """Get drift score over time."""
    service = get_drift_detection_service()
    return service.get_drift_history(limit=limit)
