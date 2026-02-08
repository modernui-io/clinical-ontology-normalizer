"""ROI Summary Dashboard API endpoint.

The "money slide" for the Regeneron pitch: screening volume, eligibility
rates, projected enrollment uplift, cost analysis, and time-series trends.

Endpoints:
    GET /api/v1/dashboard/roi-summary - ROI summary with query-param filters
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import Permission, PermissionChecker
from app.schemas.roi_dashboard import ROISummaryResponse
from app.services.roi_dashboard_service import build_roi_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Dashboards"])


@router.get(
    "/roi-summary",
    response_model=ROISummaryResponse,
    summary="ROI summary dashboard",
    description=(
        "Aggregated screening volume, eligibility rates, dual-enrollment "
        "opportunities, projected enrollment uplift, cost analysis, and "
        "time-series trends across all trials (or filtered to one trial)."
    ),
)
async def get_roi_summary(
    request: Request,
    trial_id: str | None = Query(None, description="Filter to a single trial"),
    conversion_rate: float = Query(
        0.15, ge=0.0, le=1.0,
        description="Expected eligible-to-enrolled conversion rate",
    ),
    screening_cost_per_patient: float = Query(
        1.0, ge=0.0,
        description="Metriport cost per patient screened ($)",
    ),
    estimated_value_per_enrollment: float = Query(
        50_000.0, ge=0.0,
        description="Revenue value per enrolled patient ($)",
    ),
    time_bucket: str = Query(
        "day",
        regex="^(day|week)$",
        description="Time-series grouping: 'day' or 'week'",
    ),
    session: AsyncSession = Depends(get_db),
    _perm: None = Depends(PermissionChecker([Permission.READ_ANALYTICS])),
) -> ROISummaryResponse:
    """Return the ROI summary dashboard."""
    return await build_roi_summary(
        session,
        trial_id=trial_id,
        conversion_rate=conversion_rate,
        screening_cost_per_patient=screening_cost_per_patient,
        estimated_value_per_enrollment=estimated_value_per_enrollment,
        time_bucket=time_bucket,
    )
