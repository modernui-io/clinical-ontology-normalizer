"""Prediction Calibration API endpoints.

Provides endpoints to fit and apply calibration for prediction models.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.prediction_calibration_service import (
    CalibrationMethod,
    get_prediction_calibration_service,
)

router = APIRouter(prefix="/predictions/calibration", tags=["Prediction Calibration"])


# ============================================================================
# Request/Response Models
# ============================================================================


class FitCalibrationRequest(BaseModel):
    """Request to fit a calibration model."""

    model_version: str = Field(..., description="Model version")
    method: str = Field(default=CalibrationMethod.PLATT.value, description="Calibration method")
    y_true: list[int | float] = Field(..., min_length=2, description="Ground truth labels (0/1)")
    y_pred: list[float] = Field(..., min_length=2, description="Predicted probabilities")
    n_bins: int = Field(default=10, ge=2, le=50, description="Number of calibration bins")


class ApplyCalibrationRequest(BaseModel):
    """Request to apply a calibration model."""

    model_version: str = Field(..., description="Model version")
    scores: list[float] = Field(..., min_length=1, description="Predicted probabilities")
    strict: bool = Field(default=True, description="Raise if calibration is missing")


class CalibrationMetricsResponse(BaseModel):
    """Calibration metrics response."""

    brier_score: float
    expected_calibration_error: float
    calibration_slope: float | None = None
    calibration_intercept: float | None = None


class CalibrationCurveResponse(BaseModel):
    """Calibration curve response."""

    prob_true: list[float]
    prob_pred: list[float]


class CalibrationResponse(BaseModel):
    """Response for a calibration record."""

    id: str
    model_name: str
    model_version: str
    method: str
    sample_count: int
    created_at: str
    updated_at: str
    metrics: CalibrationMetricsResponse
    curve: CalibrationCurveResponse
    parameters: dict[str, Any] = Field(default_factory=dict)


class CalibrationSummaryResponse(BaseModel):
    """Summary response for a calibration record."""

    id: str
    model_name: str
    model_version: str
    method: str
    sample_count: int
    updated_at: str
    brier_score: float
    expected_calibration_error: float


class CalibrationListResponse(BaseModel):
    """Response for calibration list."""

    total: int
    calibrations: list[CalibrationSummaryResponse]


class ApplyCalibrationResponse(BaseModel):
    """Response for calibrated scores."""

    model_name: str
    model_version: str
    scores: list[float]
    calibrated_scores: list[float]


class MethodsResponse(BaseModel):
    """Response for available calibration methods."""

    methods: list[dict[str, str]]


# ============================================================================
# Helpers
# ============================================================================


def _record_to_response(record) -> CalibrationResponse:
    return CalibrationResponse(
        id=record.id,
        model_name=record.model_name,
        model_version=record.model_version,
        method=record.method.value,
        sample_count=record.sample_count,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
        metrics=CalibrationMetricsResponse(
            brier_score=record.metrics.brier_score,
            expected_calibration_error=record.metrics.expected_calibration_error,
            calibration_slope=record.metrics.calibration_slope,
            calibration_intercept=record.metrics.calibration_intercept,
        ),
        curve=CalibrationCurveResponse(
            prob_true=record.curve.prob_true,
            prob_pred=record.curve.prob_pred,
        ),
        parameters=record.parameters,
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "",
    response_model=CalibrationListResponse,
    summary="List calibrations",
    description="List all stored calibration records.",
)
async def list_calibrations() -> CalibrationListResponse:
    service = get_prediction_calibration_service()
    records = service.list_calibrations()
    summaries = [
        CalibrationSummaryResponse(
            id=r.id,
            model_name=r.model_name,
            model_version=r.model_version,
            method=r.method.value,
            sample_count=r.sample_count,
            updated_at=r.updated_at.isoformat(),
            brier_score=r.metrics.brier_score,
            expected_calibration_error=r.metrics.expected_calibration_error,
        )
        for r in records
    ]
    return CalibrationListResponse(total=len(summaries), calibrations=summaries)


@router.get(
    "/methods",
    response_model=MethodsResponse,
    summary="List calibration methods",
    description="Get supported calibration methods.",
)
async def list_methods() -> MethodsResponse:
    methods = [
        {"value": m.value, "label": m.value.replace("_", " ").title()}
        for m in CalibrationMethod
    ]
    return MethodsResponse(methods=methods)


@router.get(
    "/{model_name}",
    response_model=CalibrationResponse,
    summary="Get calibration",
    description="Get calibration for a model and version.",
)
async def get_calibration(
    model_name: str,
    version: str = Query(..., description="Model version"),
) -> CalibrationResponse:
    service = get_prediction_calibration_service()
    record = service.get_calibration(model_name, version)
    if record is None:
        raise HTTPException(status_code=404, detail="Calibration not found")
    return _record_to_response(record)


@router.post(
    "/{model_name}/fit",
    response_model=CalibrationResponse,
    summary="Fit calibration",
    description="Fit and store calibration for a model version.",
)
async def fit_calibration(
    model_name: str,
    request: FitCalibrationRequest,
) -> CalibrationResponse:
    service = get_prediction_calibration_service()
    try:
        method = CalibrationMethod(request.method)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid method: {request.method}")

    try:
        record = service.fit_calibration(
            model_name=model_name,
            model_version=request.model_version,
            y_true=request.y_true,
            y_pred=request.y_pred,
            method=method,
            n_bins=request.n_bins,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return _record_to_response(record)


@router.post(
    "/{model_name}/apply",
    response_model=ApplyCalibrationResponse,
    summary="Apply calibration",
    description="Apply calibration to predicted probabilities.",
)
async def apply_calibration(
    model_name: str,
    request: ApplyCalibrationRequest,
) -> ApplyCalibrationResponse:
    service = get_prediction_calibration_service()
    try:
        calibrated = service.apply_calibration(
            model_name=model_name,
            model_version=request.model_version,
            scores=request.scores,
            strict=request.strict,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return ApplyCalibrationResponse(
        model_name=model_name,
        model_version=request.model_version,
        scores=request.scores,
        calibrated_scores=[round(float(v), 6) for v in calibrated],
    )
