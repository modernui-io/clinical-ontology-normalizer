"""Screen Failure Analytics API endpoints (VP-Product-3).

Exposes analytics on why patients fail trial screening so that sites
can optimise recruitment strategies.

Endpoints:
    GET /analytics/screening/{trial_id}/failures       - Failure analytics report
    GET /analytics/screening/{trial_id}/funnel          - Recruitment funnel
    GET /analytics/screening/{trial_id}/criteria-difficulty - Per-criterion pass rates
    GET /analytics/screening/{trial_id}/near-misses     - Near-miss patients
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from app.core.permissions import Permission, PermissionChecker
from app.schemas.screen_failure import (
    CriteriaDifficultyReport,
    FailureAnalyticsReport,
    NearMissReport,
    RecruitmentFunnel,
)
from app.services.screen_failure_analytics_service import (
    get_screen_failure_analytics_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/analytics/screening",
    tags=["Screen Failure Analytics"],
)

# ---------------------------------------------------------------------------
# Permission dependency
# ---------------------------------------------------------------------------
# PermissionChecker uses ``from __future__ import annotations`` which causes
# its ``request: Request`` parameter to be a string at runtime. FastAPI
# 0.123 cannot resolve this string annotation when used as a callable class
# dependency, treating ``request`` as a query parameter (422 errors).
#
# Work-around: wrap the checker in a plain async function whose annotations
# are evaluated eagerly (no PEP 563).
# ---------------------------------------------------------------------------

_analytics_perm_checker = PermissionChecker([Permission.READ_ANALYTICS])


async def _require_analytics_perm(request: Request) -> None:
    return await _analytics_perm_checker(request)


@router.get(
    "/{trial_id}/failures",
    response_model=FailureAnalyticsReport,
    summary="Failure analytics report",
    description=(
        "Aggregated screen-failure analytics for a trial: top failing "
        "criteria, failure rate over time, failure distribution by "
        "criterion type, and near-miss count."
    ),
)
async def get_failure_analytics(
    trial_id: str,
    date_from: Optional[datetime] = Query(None, description="Start of date range (inclusive)"),
    date_to: Optional[datetime] = Query(None, description="End of date range (inclusive)"),
    top_n: int = Query(10, ge=1, le=100, description="Number of top failing criteria to return"),
    _perm: None = Depends(_require_analytics_perm),
) -> FailureAnalyticsReport:
    """Return failure analytics for a trial."""
    svc = get_screen_failure_analytics_service()
    return svc.get_failure_analytics(trial_id, date_from=date_from, date_to=date_to, top_n=top_n)


@router.get(
    "/{trial_id}/funnel",
    response_model=RecruitmentFunnel,
    summary="Recruitment funnel",
    description=(
        "End-to-end recruitment funnel for a trial: Screened -> "
        "Passed Inclusion -> Passed Exclusion -> Eligible -> Enrolled."
    ),
)
async def get_trial_funnel(
    trial_id: str,
    enrolled_count: Optional[int] = Query(None, ge=0, description="Externally-provided enrolled count"),
    _perm: None = Depends(_require_analytics_perm),
) -> RecruitmentFunnel:
    """Return the recruitment funnel for a trial."""
    svc = get_screen_failure_analytics_service()
    return svc.get_trial_funnel(trial_id, enrolled_count=enrolled_count)


@router.get(
    "/{trial_id}/criteria-difficulty",
    response_model=CriteriaDifficultyReport,
    summary="Per-criterion pass rates",
    description=(
        "Per-criterion pass rate showing which criteria are hardest to "
        "satisfy. Sorted by pass rate ascending (hardest first)."
    ),
)
async def get_criteria_difficulty(
    trial_id: str,
    _perm: None = Depends(_require_analytics_perm),
) -> CriteriaDifficultyReport:
    """Return criteria difficulty for a trial."""
    svc = get_screen_failure_analytics_service()
    return svc.get_criteria_difficulty(trial_id)


@router.get(
    "/{trial_id}/near-misses",
    response_model=NearMissReport,
    summary="Near-miss patients",
    description=(
        "Patients who failed by 1-2 criteria -- high-value leads that "
        "might qualify with updated criteria or additional data."
    ),
)
async def get_near_miss_patients(
    trial_id: str,
    max_failures: int = Query(2, ge=1, le=10, description="Maximum failing criteria to count as near miss"),
    _perm: None = Depends(_require_analytics_perm),
) -> NearMissReport:
    """Return near-miss patients for a trial."""
    svc = get_screen_failure_analytics_service()
    return svc.get_near_miss_patients(trial_id, max_failures=max_failures)
