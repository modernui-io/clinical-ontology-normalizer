"""ROI Dashboard Service.

Aggregates data from screening_results, trials, sites, and enrollments
to produce the ROI summary used in the Regeneron pitch deck.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from sqlalchemy import case, cast, func, select, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.screening_result import OverallScreeningStatus, ScreeningResult
from app.schemas.roi_dashboard import (
    CostAnalysis,
    DualEnrollmentCandidate,
    ProjectedEnrollment,
    ROISummaryResponse,
    ScreeningOverview,
    SiteTrialBreakdown,
    TimeSeriesBucket,
    TrialEligibilitySummary,
)

logger = logging.getLogger(__name__)


async def build_roi_summary(
    session: AsyncSession,
    *,
    trial_id: str | None = None,
    conversion_rate: float = 0.15,
    screening_cost_per_patient: float = 1.0,
    estimated_value_per_enrollment: float = 50_000.0,
    time_bucket: str = "day",
) -> ROISummaryResponse:
    """Build the full ROI summary from screening_results and related tables.

    Args:
        session: Async DB session.
        trial_id: Optional filter to a single trial.
        conversion_rate: Fraction of eligible patients expected to enroll.
        screening_cost_per_patient: Cost per Metriport query ($).
        estimated_value_per_enrollment: Revenue per enrolled patient ($).
        time_bucket: "day" or "week" for the time-series grouping.
    """

    base_filters: list = []
    if trial_id:
        base_filters.append(ScreeningResult.trial_id == trial_id)

    # ------------------------------------------------------------------
    # 1. Screening overview
    # ------------------------------------------------------------------
    overview_stmt = select(
        func.count(ScreeningResult.id).label("total_screenings"),
        func.count(func.distinct(ScreeningResult.patient_id)).label("total_patients"),
        func.count(func.distinct(ScreeningResult.trial_id)).label("unique_trials"),
        func.sum(
            case(
                (ScreeningResult.overall_status == OverallScreeningStatus.ELIGIBLE, 1),
                else_=0,
            )
        ).label("eligible"),
        func.sum(
            case(
                (ScreeningResult.overall_status == OverallScreeningStatus.INELIGIBLE, 1),
                else_=0,
            )
        ).label("ineligible"),
        func.sum(
            case(
                (ScreeningResult.overall_status == OverallScreeningStatus.UNKNOWN, 1),
                else_=0,
            )
        ).label("unknown"),
    ).where(*base_filters)

    row = (await session.execute(overview_stmt)).one()
    total_screenings = row.total_screenings or 0
    total_patients = row.total_patients or 0
    unique_trials = row.unique_trials or 0
    total_eligible = row.eligible or 0
    total_ineligible = row.ineligible or 0
    total_unknown = row.unknown or 0
    overall_pass_rate = (
        round(total_eligible / total_screenings, 4) if total_screenings else 0.0
    )

    overview = ScreeningOverview(
        total_screenings=total_screenings,
        total_patients_screened=total_patients,
        unique_trials_screened=unique_trials,
        total_eligible=total_eligible,
        total_ineligible=total_ineligible,
        total_unknown=total_unknown,
        overall_pass_rate=overall_pass_rate,
    )

    # ------------------------------------------------------------------
    # 2. Eligibility by trial
    # ------------------------------------------------------------------
    trial_stmt = (
        select(
            ScreeningResult.trial_id,
            func.max(ScreeningResult.trial_name).label("trial_name"),
            func.count(ScreeningResult.id).label("total"),
            func.sum(
                case(
                    (ScreeningResult.overall_status == OverallScreeningStatus.ELIGIBLE, 1),
                    else_=0,
                )
            ).label("eligible"),
            func.sum(
                case(
                    (ScreeningResult.overall_status == OverallScreeningStatus.INELIGIBLE, 1),
                    else_=0,
                )
            ).label("ineligible"),
            func.sum(
                case(
                    (ScreeningResult.overall_status == OverallScreeningStatus.UNKNOWN, 1),
                    else_=0,
                )
            ).label("unknown"),
        )
        .where(*base_filters)
        .group_by(ScreeningResult.trial_id)
        .order_by(func.count(ScreeningResult.id).desc())
    )
    trial_rows = (await session.execute(trial_stmt)).all()
    eligibility_by_trial = [
        TrialEligibilitySummary(
            trial_id=r.trial_id,
            trial_name=r.trial_name,
            total_screened=r.total or 0,
            eligible_count=r.eligible or 0,
            ineligible_count=r.ineligible or 0,
            unknown_count=r.unknown or 0,
            pass_rate=round((r.eligible or 0) / r.total, 4) if r.total else 0.0,
        )
        for r in trial_rows
    ]

    # ------------------------------------------------------------------
    # 3. Site breakdown (gracefully degrade if tables are empty)
    # ------------------------------------------------------------------
    site_breakdown: list[SiteTrialBreakdown] = []
    try:
        from app.models.site import PatientSiteAssignment, Site

        site_stmt = (
            select(
                PatientSiteAssignment.site_id,
                func.max(Site.name).label("site_name"),
                ScreeningResult.trial_id,
                func.max(ScreeningResult.trial_name).label("trial_name"),
                func.count(func.distinct(ScreeningResult.patient_id)).label("eligible_count"),
            )
            .join(
                PatientSiteAssignment,
                PatientSiteAssignment.patient_id == ScreeningResult.patient_id,
            )
            .join(Site, Site.id == PatientSiteAssignment.site_id)
            .where(
                ScreeningResult.overall_status == OverallScreeningStatus.ELIGIBLE,
                *base_filters,
            )
            .group_by(PatientSiteAssignment.site_id, ScreeningResult.trial_id)
            .order_by(func.count(func.distinct(ScreeningResult.patient_id)).desc())
        )
        site_rows = (await session.execute(site_stmt)).all()
        site_breakdown = [
            SiteTrialBreakdown(
                site_id=r.site_id,
                site_name=r.site_name,
                trial_id=r.trial_id,
                trial_name=r.trial_name,
                eligible_count=r.eligible_count or 0,
            )
            for r in site_rows
        ]
    except Exception:
        logger.debug("Site breakdown unavailable (table may be empty)", exc_info=True)

    # ------------------------------------------------------------------
    # 4. Dual enrollment opportunities
    # ------------------------------------------------------------------
    dual_sub = (
        select(
            ScreeningResult.patient_id,
            func.array_agg(func.distinct(ScreeningResult.trial_id)).label("trial_ids"),
            func.array_agg(func.distinct(ScreeningResult.trial_name)).label("trial_names"),
            func.count(func.distinct(ScreeningResult.trial_id)).label("trial_count"),
        )
        .where(
            ScreeningResult.overall_status == OverallScreeningStatus.ELIGIBLE,
            *base_filters,
        )
        .group_by(ScreeningResult.patient_id)
        .having(func.count(func.distinct(ScreeningResult.trial_id)) > 1)
        .order_by(func.count(func.distinct(ScreeningResult.trial_id)).desc())
        .limit(100)
    )
    dual_rows = (await session.execute(dual_sub)).all()
    dual_candidates = [
        DualEnrollmentCandidate(
            patient_id=r.patient_id,
            eligible_trial_ids=r.trial_ids or [],
            eligible_trial_names=[n for n in (r.trial_names or []) if n],
            trial_count=r.trial_count or 0,
        )
        for r in dual_rows
    ]

    # ------------------------------------------------------------------
    # 5. Projected enrollment uplift
    # ------------------------------------------------------------------
    projected_enrollments = math.floor(total_eligible * conversion_rate)
    projected = ProjectedEnrollment(
        eligible_patients=total_eligible,
        conversion_rate=conversion_rate,
        projected_enrollments=projected_enrollments,
    )

    # ------------------------------------------------------------------
    # 6. Cost analysis
    # ------------------------------------------------------------------
    total_screening_cost = total_patients * screening_cost_per_patient
    projected_value = projected_enrollments * estimated_value_per_enrollment
    roi_ratio = (
        round(projected_value / total_screening_cost, 2)
        if total_screening_cost > 0
        else None
    )
    cost = CostAnalysis(
        patients_screened=total_patients,
        screening_cost_per_patient=screening_cost_per_patient,
        total_screening_cost=total_screening_cost,
        projected_enrollments=projected_enrollments,
        estimated_value_per_enrollment=estimated_value_per_enrollment,
        projected_enrollment_value=projected_value,
        roi_ratio=roi_ratio,
    )

    # ------------------------------------------------------------------
    # 7. Time series
    # ------------------------------------------------------------------
    date_col = cast(ScreeningResult.screening_date, Date)
    ts_stmt = (
        select(
            date_col.label("period"),
            func.count(ScreeningResult.id).label("screenings"),
            func.sum(
                case(
                    (ScreeningResult.overall_status == OverallScreeningStatus.ELIGIBLE, 1),
                    else_=0,
                )
            ).label("eligible"),
        )
        .where(*base_filters)
        .group_by(date_col)
        .order_by(date_col)
    )
    ts_rows = (await session.execute(ts_stmt)).all()
    time_series = [
        TimeSeriesBucket(
            period=str(r.period),
            screenings=r.screenings or 0,
            eligible=r.eligible or 0,
            match_rate=(
                round((r.eligible or 0) / r.screenings, 4) if r.screenings else 0.0
            ),
        )
        for r in ts_rows
    ]

    return ROISummaryResponse(
        generated_at=datetime.now(timezone.utc),
        screening_overview=overview,
        eligibility_by_trial=eligibility_by_trial,
        site_breakdown=site_breakdown,
        dual_enrollment_candidates=dual_candidates,
        dual_enrollment_count=len(dual_candidates),
        projected_enrollment=projected,
        cost_analysis=cost,
        time_series=time_series,
    )
