"""A/B Testing / Experiments API endpoints (VP-DS-3).

Manages clinical trial experiment lifecycle, variant assignment,
outcome tracking, and statistical analysis.

Endpoints:
    POST /api/v1/experiments                      - Create new experiment
    GET  /api/v1/experiments                      - List experiments
    GET  /api/v1/experiments/templates             - List experiment templates
    POST /api/v1/experiments/from-template         - Create from template
    GET  /api/v1/experiments/{id}                  - Get experiment details
    POST /api/v1/experiments/{id}/start            - Start experiment
    POST /api/v1/experiments/{id}/pause            - Pause experiment
    POST /api/v1/experiments/{id}/complete         - Complete experiment
    POST /api/v1/experiments/{id}/archive          - Archive experiment
    POST /api/v1/experiments/{id}/assign           - Assign patient to variant
    POST /api/v1/experiments/{id}/record           - Record outcome
    GET  /api/v1/experiments/{id}/results          - Statistical results
    GET  /api/v1/experiments/{id}/power            - Power analysis
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.schemas.experiment import (
    AssignmentRequest,
    AssignmentResponse,
    ExperimentCreate,
    ExperimentListResponse,
    ExperimentResponse,
    ExperimentResults,
    ExperimentStatus,
    OutcomeRecord,
    PowerAnalysis,
    TemplateListResponse,
)
from app.services.experiment_service import get_experiment_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/experiments", tags=["Experiments"])


# ---------------------------------------------------------------------------
# Request/Response helpers
# ---------------------------------------------------------------------------


class TemplateCreateRequest(BaseModel):
    """Request to create experiment from template."""

    template_id: str = Field(..., description="Template ID to create from")
    name: str | None = Field(None, description="Override experiment name")


class OutcomeResponse(BaseModel):
    """Response after recording an outcome."""

    experiment_id: str
    patient_id: str
    variant: str
    metric_name: str
    value: float
    recorded: bool


# ---------------------------------------------------------------------------
# Experiment CRUD
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new experiment",
    description="Create a new A/B experiment in DRAFT status.",
)
async def create_experiment(body: ExperimentCreate) -> ExperimentResponse:
    svc = get_experiment_service()
    try:
        return svc.create_experiment(body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )


@router.get(
    "",
    response_model=ExperimentListResponse,
    summary="List experiments",
    description="List experiments with optional status filter.",
)
async def list_experiments(
    status_filter: ExperimentStatus | None = Query(
        None, alias="status", description="Filter by status"
    ),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> ExperimentListResponse:
    svc = get_experiment_service()
    experiments, total = svc.list_experiments(
        status=status_filter, offset=offset, limit=limit
    )
    return ExperimentListResponse(experiments=experiments, total=total)


@router.get(
    "/templates",
    response_model=TemplateListResponse,
    summary="List experiment templates",
    description="Return all pre-defined experiment templates.",
)
async def list_templates() -> TemplateListResponse:
    svc = get_experiment_service()
    return svc.get_templates()


@router.post(
    "/from-template",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create experiment from template",
    description="Create a new experiment from a pre-defined template.",
)
async def create_from_template(body: TemplateCreateRequest) -> ExperimentResponse:
    svc = get_experiment_service()
    try:
        return svc.create_from_template(body.template_id, name=body.name)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get(
    "/{experiment_id}",
    response_model=ExperimentResponse,
    summary="Get experiment details",
    description="Get full experiment details including assignment and outcome counts.",
)
async def get_experiment(experiment_id: str) -> ExperimentResponse:
    svc = get_experiment_service()
    try:
        return svc.get_experiment(experiment_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.delete(
    "/{experiment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete experiment",
    description="Delete an experiment (only DRAFT or ARCHIVED).",
)
async def delete_experiment(experiment_id: str) -> None:
    svc = get_experiment_service()
    try:
        svc.delete_experiment(experiment_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# Lifecycle transitions
# ---------------------------------------------------------------------------


@router.post(
    "/{experiment_id}/start",
    response_model=ExperimentResponse,
    summary="Start experiment",
    description="Transition experiment from DRAFT to RUNNING.",
)
async def start_experiment(experiment_id: str) -> ExperimentResponse:
    svc = get_experiment_service()
    try:
        return svc.start_experiment(experiment_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.post(
    "/{experiment_id}/pause",
    response_model=ExperimentResponse,
    summary="Pause experiment",
    description="Transition experiment from RUNNING to PAUSED.",
)
async def pause_experiment(experiment_id: str) -> ExperimentResponse:
    svc = get_experiment_service()
    try:
        return svc.pause_experiment(experiment_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.post(
    "/{experiment_id}/complete",
    response_model=ExperimentResponse,
    summary="Complete experiment",
    description="Transition experiment to COMPLETED and lock results.",
)
async def complete_experiment(experiment_id: str) -> ExperimentResponse:
    svc = get_experiment_service()
    try:
        return svc.complete_experiment(experiment_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.post(
    "/{experiment_id}/archive",
    response_model=ExperimentResponse,
    summary="Archive experiment",
    description="Archive a completed or draft experiment.",
)
async def archive_experiment(experiment_id: str) -> ExperimentResponse:
    svc = get_experiment_service()
    try:
        return svc.archive_experiment(experiment_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# Assignment & Outcome
# ---------------------------------------------------------------------------


@router.post(
    "/{experiment_id}/assign",
    response_model=AssignmentResponse,
    summary="Assign patient to variant",
    description=(
        "Deterministically assign a patient to a variant. "
        "Same patient always gets the same variant."
    ),
)
async def assign_variant(
    experiment_id: str,
    body: AssignmentRequest,
) -> AssignmentResponse:
    svc = get_experiment_service()
    try:
        return svc.assign_variant(experiment_id, body.patient_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.post(
    "/{experiment_id}/record",
    response_model=OutcomeResponse,
    summary="Record outcome event",
    description="Record an outcome metric value for a patient in an experiment.",
)
async def record_outcome(
    experiment_id: str,
    body: OutcomeRecord,
) -> OutcomeResponse:
    svc = get_experiment_service()
    try:
        result = svc.record_outcome(experiment_id, body)
        return OutcomeResponse(**result)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


@router.get(
    "/{experiment_id}/results",
    response_model=ExperimentResults,
    summary="Statistical analysis results",
    description="Get full statistical analysis including pairwise tests, sequential testing, and power analysis.",
)
async def get_results(
    experiment_id: str,
    total_planned_looks: int = Query(
        5, ge=1, le=20, description="Total planned interim looks"
    ),
) -> ExperimentResults:
    svc = get_experiment_service()
    try:
        return svc.get_results(experiment_id, total_planned_looks=total_planned_looks)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.get(
    "/{experiment_id}/power",
    response_model=PowerAnalysis,
    summary="Power analysis",
    description="Compute power analysis for the experiment.",
)
async def get_power(
    experiment_id: str,
    effect_size: float = Query(
        0.5, gt=0.0, description="Assumed effect size (Cohen's d)"
    ),
) -> PowerAnalysis:
    svc = get_experiment_service()
    try:
        return svc.get_power_analysis(experiment_id, effect_size=effect_size)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
