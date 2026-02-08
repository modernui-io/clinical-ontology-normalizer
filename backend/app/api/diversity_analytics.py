"""Diversity and Inclusion Analytics API endpoints (VP-Product-4).

Endpoints for tracking demographic representation in clinical trial
screening and enrollment to support FDA diversity action plan requirements.

Endpoints:
    GET  /api/v1/analytics/diversity/{trial_id}                - Diversity report
    GET  /api/v1/analytics/diversity/{trial_id}/representation - Representation check
    GET  /api/v1/analytics/diversity/{trial_id}/pipeline       - Pipeline demographics
    POST /api/v1/analytics/diversity/{trial_id}/targets        - Set diversity targets
    GET  /api/v1/analytics/diversity/{trial_id}/fda-summary    - FDA diversity summary
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Request

from app.core.permissions import Permission, PermissionChecker
from app.schemas.diversity import (
    DiversityReport,
    FDADiversitySummary,
    PipelineDemographics,
    PipelineStage,
    RepresentationCheck,
    SetDiversityTargetsRequest,
)
from app.services.diversity_analytics_service import get_diversity_analytics_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/analytics/diversity",
    tags=["Diversity Analytics"],
)


@router.get(
    "/{trial_id}",
    response_model=DiversityReport,
    summary="Get diversity report for a trial",
    description=(
        "Returns aggregate demographic breakdowns (age, sex, race, ethnicity) "
        "for all patients tracked in the trial. Optionally filter by pipeline stage."
    ),
)
async def get_diversity_report(
    trial_id: str,
    request: Request,
    stage: PipelineStage | None = Query(
        None,
        description="Filter to a specific pipeline stage (screened, eligible, enrolled)",
    ),
    _perm: None = Depends(PermissionChecker([Permission.READ_ANALYTICS])),
) -> DiversityReport:
    """Get diversity report for a trial."""
    service = get_diversity_analytics_service()
    return service.get_diversity_report(trial_id, stage=stage)


@router.get(
    "/{trial_id}/representation",
    response_model=RepresentationCheck,
    summary="Check representation against diversity targets",
    description=(
        "Compares actual enrollment demographics against the diversity targets "
        "set for the trial. Returns per-group gap analysis and an overall "
        "diversity score."
    ),
)
async def check_representation(
    trial_id: str,
    request: Request,
    _perm: None = Depends(PermissionChecker([Permission.READ_ANALYTICS])),
) -> RepresentationCheck:
    """Check enrollment representation against diversity targets."""
    service = get_diversity_analytics_service()
    return service.check_representation(trial_id)


@router.get(
    "/{trial_id}/pipeline",
    response_model=PipelineDemographics,
    summary="Get demographics across pipeline stages",
    description=(
        "Returns demographics at each stage (screened, eligible, enrolled) "
        "with dropout analysis to detect if screening criteria "
        "disproportionately exclude certain demographic groups."
    ),
)
async def get_pipeline_demographics(
    trial_id: str,
    request: Request,
    _perm: None = Depends(PermissionChecker([Permission.READ_ANALYTICS])),
) -> PipelineDemographics:
    """Get demographics across pipeline stages."""
    service = get_diversity_analytics_service()
    return service.get_pipeline_demographics(trial_id)


@router.post(
    "/{trial_id}/targets",
    response_model=RepresentationCheck,
    summary="Set diversity targets for a trial",
    description=(
        "Set diversity representation targets for a trial. Returns the "
        "current representation check against the newly set targets. "
        "Supports FDA Diversity Action Plan requirements."
    ),
)
async def set_diversity_targets(
    trial_id: str,
    request: Request,
    body: SetDiversityTargetsRequest,
    _perm: None = Depends(PermissionChecker([Permission.READ_ANALYTICS])),
) -> RepresentationCheck:
    """Set diversity targets and return current representation check."""
    service = get_diversity_analytics_service()
    service.set_targets(trial_id, body.targets)
    return service.check_representation(trial_id)


@router.get(
    "/{trial_id}/fda-summary",
    response_model=FDADiversitySummary,
    summary="Generate FDA diversity summary",
    description=(
        "Generates an FDA-format diversity summary suitable for regulatory "
        "submissions. Includes demographic tables, target compliance, and "
        "actionable recommendations."
    ),
)
async def get_fda_diversity_summary(
    trial_id: str,
    request: Request,
    enrollment_target: int | None = Query(
        None,
        description="Override enrollment target for the summary",
    ),
    _perm: None = Depends(PermissionChecker([Permission.READ_ANALYTICS])),
) -> FDADiversitySummary:
    """Generate FDA-format diversity summary."""
    service = get_diversity_analytics_service()
    return service.generate_fda_diversity_summary(
        trial_id, enrollment_target=enrollment_target
    )
