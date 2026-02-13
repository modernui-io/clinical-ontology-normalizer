"""Interim Analysis API endpoints (IA-MGT).

Provides comprehensive interim analysis management operations: analysis plans,
data cut definitions, DSMB review records, statistical review outcomes, and
interim analysis metrics.

Endpoints:
    GET    /interim-analysis/analysis-plans                                 - List analysis plans
    GET    /interim-analysis/analysis-plans/{plan_id}                       - Get single plan
    POST   /interim-analysis/analysis-plans                                 - Create plan
    PUT    /interim-analysis/analysis-plans/{plan_id}                       - Update plan
    DELETE /interim-analysis/analysis-plans/{plan_id}                       - Delete plan
    GET    /interim-analysis/data-cut-definitions                           - List data cuts
    GET    /interim-analysis/data-cut-definitions/{cut_id}                  - Get single data cut
    POST   /interim-analysis/data-cut-definitions                           - Create data cut
    PUT    /interim-analysis/data-cut-definitions/{cut_id}                  - Update data cut
    DELETE /interim-analysis/data-cut-definitions/{cut_id}                  - Delete data cut
    GET    /interim-analysis/dsmb-reviews                                   - List DSMB reviews
    GET    /interim-analysis/dsmb-reviews/{review_id}                       - Get single review
    POST   /interim-analysis/dsmb-reviews                                   - Create review
    PUT    /interim-analysis/dsmb-reviews/{review_id}                       - Update review
    DELETE /interim-analysis/dsmb-reviews/{review_id}                       - Delete review
    GET    /interim-analysis/statistical-review-outcomes                    - List outcomes
    GET    /interim-analysis/statistical-review-outcomes/{outcome_id}       - Get single outcome
    POST   /interim-analysis/statistical-review-outcomes                    - Create outcome
    PUT    /interim-analysis/statistical-review-outcomes/{outcome_id}       - Update outcome
    DELETE /interim-analysis/statistical-review-outcomes/{outcome_id}       - Delete outcome
    GET    /interim-analysis/metrics                                        - Interim analysis metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.interim_analysis import (
    AnalysisPlan,
    AnalysisPlanCreate,
    AnalysisPlanListResponse,
    AnalysisPlanStatus,
    AnalysisPlanUpdate,
    DSMBRecommendation,
    DSMBReview,
    DSMBReviewCreate,
    DSMBReviewListResponse,
    DSMBReviewUpdate,
    DataCutDefinition,
    DataCutDefinitionCreate,
    DataCutDefinitionListResponse,
    DataCutDefinitionUpdate,
    DataCutStatus,
    InterimAnalysisMetrics,
    ReviewOutcome,
    StatisticalReviewOutcome,
    StatisticalReviewOutcomeCreate,
    StatisticalReviewOutcomeListResponse,
    StatisticalReviewOutcomeUpdate,
)
from app.services.interim_analysis_service import get_interim_analysis_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/interim-analysis",
    tags=["Interim Analysis"],
)


# ---------------------------------------------------------------------------
# Analysis Plans
# ---------------------------------------------------------------------------


@router.get(
    "/analysis-plans",
    response_model=AnalysisPlanListResponse,
    summary="List analysis plans",
    description="Retrieve analysis plans with optional filtering by trial and status.",
)
async def list_analysis_plans(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    analysis_plan_status: Optional[AnalysisPlanStatus] = Query(None, description="Filter by plan status"),
) -> AnalysisPlanListResponse:
    svc = get_interim_analysis_service()
    items = svc.list_analysis_plans(
        trial_id=trial_id, analysis_plan_status=analysis_plan_status
    )
    return AnalysisPlanListResponse(items=items, total=len(items))


@router.get(
    "/analysis-plans/{plan_id}",
    response_model=AnalysisPlan,
    summary="Get an analysis plan",
)
async def get_analysis_plan(plan_id: str) -> AnalysisPlan:
    svc = get_interim_analysis_service()
    record = svc.get_analysis_plan(plan_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Analysis plan '{plan_id}' not found")
    return record


@router.post(
    "/analysis-plans",
    response_model=AnalysisPlan,
    status_code=201,
    summary="Create an analysis plan",
)
async def create_analysis_plan(payload: AnalysisPlanCreate) -> AnalysisPlan:
    svc = get_interim_analysis_service()
    return svc.create_analysis_plan(payload)


@router.put(
    "/analysis-plans/{plan_id}",
    response_model=AnalysisPlan,
    summary="Update an analysis plan",
)
async def update_analysis_plan(
    plan_id: str, payload: AnalysisPlanUpdate
) -> AnalysisPlan:
    svc = get_interim_analysis_service()
    updated = svc.update_analysis_plan(plan_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Analysis plan '{plan_id}' not found")
    return updated


@router.delete(
    "/analysis-plans/{plan_id}",
    status_code=204,
    summary="Delete an analysis plan",
)
async def delete_analysis_plan(plan_id: str) -> None:
    svc = get_interim_analysis_service()
    deleted = svc.delete_analysis_plan(plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Analysis plan '{plan_id}' not found")


# ---------------------------------------------------------------------------
# Data Cut Definitions
# ---------------------------------------------------------------------------


@router.get(
    "/data-cut-definitions",
    response_model=DataCutDefinitionListResponse,
    summary="List data cut definitions",
    description="Retrieve data cut definitions with optional filtering by trial, status, and analysis plan.",
)
async def list_data_cut_definitions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    data_cut_status: Optional[DataCutStatus] = Query(None, description="Filter by data cut status"),
    analysis_plan_id: Optional[str] = Query(None, description="Filter by analysis plan ID"),
) -> DataCutDefinitionListResponse:
    svc = get_interim_analysis_service()
    items = svc.list_data_cut_definitions(
        trial_id=trial_id, data_cut_status=data_cut_status, analysis_plan_id=analysis_plan_id
    )
    return DataCutDefinitionListResponse(items=items, total=len(items))


@router.get(
    "/data-cut-definitions/{cut_id}",
    response_model=DataCutDefinition,
    summary="Get a data cut definition",
)
async def get_data_cut_definition(cut_id: str) -> DataCutDefinition:
    svc = get_interim_analysis_service()
    record = svc.get_data_cut_definition(cut_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Data cut definition '{cut_id}' not found"
        )
    return record


@router.post(
    "/data-cut-definitions",
    response_model=DataCutDefinition,
    status_code=201,
    summary="Create a data cut definition",
)
async def create_data_cut_definition(payload: DataCutDefinitionCreate) -> DataCutDefinition:
    svc = get_interim_analysis_service()
    return svc.create_data_cut_definition(payload)


@router.put(
    "/data-cut-definitions/{cut_id}",
    response_model=DataCutDefinition,
    summary="Update a data cut definition",
)
async def update_data_cut_definition(
    cut_id: str, payload: DataCutDefinitionUpdate
) -> DataCutDefinition:
    svc = get_interim_analysis_service()
    updated = svc.update_data_cut_definition(cut_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Data cut definition '{cut_id}' not found"
        )
    return updated


@router.delete(
    "/data-cut-definitions/{cut_id}",
    status_code=204,
    summary="Delete a data cut definition",
)
async def delete_data_cut_definition(cut_id: str) -> None:
    svc = get_interim_analysis_service()
    deleted = svc.delete_data_cut_definition(cut_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Data cut definition '{cut_id}' not found"
        )


# ---------------------------------------------------------------------------
# DSMB Reviews
# ---------------------------------------------------------------------------


@router.get(
    "/dsmb-reviews",
    response_model=DSMBReviewListResponse,
    summary="List DSMB reviews",
    description="Retrieve DSMB reviews with optional filtering by trial, recommendation, and data cut.",
)
async def list_dsmb_reviews(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    dsmb_recommendation: Optional[DSMBRecommendation] = Query(None, description="Filter by DSMB recommendation"),
    data_cut_id: Optional[str] = Query(None, description="Filter by data cut ID"),
) -> DSMBReviewListResponse:
    svc = get_interim_analysis_service()
    items = svc.list_dsmb_reviews(
        trial_id=trial_id, dsmb_recommendation=dsmb_recommendation, data_cut_id=data_cut_id
    )
    return DSMBReviewListResponse(items=items, total=len(items))


@router.get(
    "/dsmb-reviews/{review_id}",
    response_model=DSMBReview,
    summary="Get a DSMB review",
)
async def get_dsmb_review(review_id: str) -> DSMBReview:
    svc = get_interim_analysis_service()
    record = svc.get_dsmb_review(review_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"DSMB review '{review_id}' not found"
        )
    return record


@router.post(
    "/dsmb-reviews",
    response_model=DSMBReview,
    status_code=201,
    summary="Create a DSMB review",
)
async def create_dsmb_review(payload: DSMBReviewCreate) -> DSMBReview:
    svc = get_interim_analysis_service()
    return svc.create_dsmb_review(payload)


@router.put(
    "/dsmb-reviews/{review_id}",
    response_model=DSMBReview,
    summary="Update a DSMB review",
)
async def update_dsmb_review(
    review_id: str, payload: DSMBReviewUpdate
) -> DSMBReview:
    svc = get_interim_analysis_service()
    updated = svc.update_dsmb_review(review_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"DSMB review '{review_id}' not found"
        )
    return updated


@router.delete(
    "/dsmb-reviews/{review_id}",
    status_code=204,
    summary="Delete a DSMB review",
)
async def delete_dsmb_review(review_id: str) -> None:
    svc = get_interim_analysis_service()
    deleted = svc.delete_dsmb_review(review_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"DSMB review '{review_id}' not found"
        )


# ---------------------------------------------------------------------------
# Statistical Review Outcomes
# ---------------------------------------------------------------------------


@router.get(
    "/statistical-review-outcomes",
    response_model=StatisticalReviewOutcomeListResponse,
    summary="List statistical review outcomes",
    description="Retrieve statistical review outcomes with optional filtering by trial, outcome, and data cut.",
)
async def list_statistical_review_outcomes(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    review_outcome: Optional[ReviewOutcome] = Query(None, description="Filter by review outcome"),
    data_cut_id: Optional[str] = Query(None, description="Filter by data cut ID"),
) -> StatisticalReviewOutcomeListResponse:
    svc = get_interim_analysis_service()
    items = svc.list_statistical_review_outcomes(
        trial_id=trial_id, review_outcome=review_outcome, data_cut_id=data_cut_id
    )
    return StatisticalReviewOutcomeListResponse(items=items, total=len(items))


@router.get(
    "/statistical-review-outcomes/{outcome_id}",
    response_model=StatisticalReviewOutcome,
    summary="Get a statistical review outcome",
)
async def get_statistical_review_outcome(outcome_id: str) -> StatisticalReviewOutcome:
    svc = get_interim_analysis_service()
    record = svc.get_statistical_review_outcome(outcome_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Statistical review outcome '{outcome_id}' not found"
        )
    return record


@router.post(
    "/statistical-review-outcomes",
    response_model=StatisticalReviewOutcome,
    status_code=201,
    summary="Create a statistical review outcome",
)
async def create_statistical_review_outcome(
    payload: StatisticalReviewOutcomeCreate,
) -> StatisticalReviewOutcome:
    svc = get_interim_analysis_service()
    return svc.create_statistical_review_outcome(payload)


@router.put(
    "/statistical-review-outcomes/{outcome_id}",
    response_model=StatisticalReviewOutcome,
    summary="Update a statistical review outcome",
)
async def update_statistical_review_outcome(
    outcome_id: str, payload: StatisticalReviewOutcomeUpdate
) -> StatisticalReviewOutcome:
    svc = get_interim_analysis_service()
    updated = svc.update_statistical_review_outcome(outcome_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Statistical review outcome '{outcome_id}' not found"
        )
    return updated


@router.delete(
    "/statistical-review-outcomes/{outcome_id}",
    status_code=204,
    summary="Delete a statistical review outcome",
)
async def delete_statistical_review_outcome(outcome_id: str) -> None:
    svc = get_interim_analysis_service()
    deleted = svc.delete_statistical_review_outcome(outcome_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Statistical review outcome '{outcome_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=InterimAnalysisMetrics,
    summary="Get interim analysis metrics",
    description="Aggregated metrics across all interim analysis operations, optionally filtered by trial.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> InterimAnalysisMetrics:
    svc = get_interim_analysis_service()
    return svc.get_metrics(trial_id=trial_id)
