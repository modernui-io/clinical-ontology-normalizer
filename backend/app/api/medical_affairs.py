"""Medical Affairs & Publication Planning API endpoints (CLINICAL-12).

Provides comprehensive medical affairs operations: publication lifecycle tracking,
ICMJE compliance checking, congress planning and ROI analysis, publication plans
with milestones, author management, impact factor analysis, and operational metrics.

Endpoints:
    GET    /medical-affairs/publications                                  - List publications
    GET    /medical-affairs/publications/search                           - Search publications
    GET    /medical-affairs/publications/{pub_id}                         - Get single publication
    POST   /medical-affairs/publications                                  - Create publication
    PUT    /medical-affairs/publications/{pub_id}                         - Update publication
    DELETE /medical-affairs/publications/{pub_id}                         - Delete publication
    POST   /medical-affairs/publications/{pub_id}/advance-status          - Advance status
    POST   /medical-affairs/publications/{pub_id}/check-icmje             - Check ICMJE compliance
    GET    /medical-affairs/congresses                                    - List congress plans
    GET    /medical-affairs/congresses/{congress_id}                      - Get single congress plan
    POST   /medical-affairs/congresses                                    - Create congress plan
    PUT    /medical-affairs/congresses/{congress_id}                      - Update congress plan
    DELETE /medical-affairs/congresses/{congress_id}                      - Delete congress plan
    GET    /medical-affairs/congresses/{congress_id}/roi                  - Congress ROI
    GET    /medical-affairs/publication-plans                             - List publication plans
    GET    /medical-affairs/publication-plans/{plan_id}                   - Get single plan
    POST   /medical-affairs/publication-plans                             - Create publication plan
    PUT    /medical-affairs/publication-plans/{plan_id}                   - Update publication plan
    DELETE /medical-affairs/publication-plans/{plan_id}                   - Delete publication plan
    GET    /medical-affairs/metrics                                       - Medical affairs metrics
    GET    /medical-affairs/impact-factor-weighted-count                  - Impact factor count
    GET    /medical-affairs/journal-tier/{impact_factor}                  - Classify journal tier
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.medical_affairs import (
    CongressPlan,
    CongressPlanCreate,
    CongressPlanListResponse,
    CongressPlanUpdate,
    CongressTier,
    ICMJEComplianceResult,
    MedicalAffairsMetrics,
    Publication,
    PublicationCreate,
    PublicationListResponse,
    PublicationPlan,
    PublicationPlanCreate,
    PublicationPlanListResponse,
    PublicationPlanUpdate,
    PublicationStatus,
    PublicationType,
    PublicationUpdate,
)
from app.services.medical_affairs_service import get_medical_affairs_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/medical-affairs",
    tags=["Medical Affairs"],
)


# ---------------------------------------------------------------------------
# Publication Management
# ---------------------------------------------------------------------------


@router.get(
    "/publications",
    response_model=PublicationListResponse,
    summary="List publications",
    description="Retrieve publications with optional filtering by trial, status, and type.",
)
async def list_publications(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[PublicationStatus] = Query(None, description="Filter by status"),
    publication_type: Optional[PublicationType] = Query(None, description="Filter by type"),
) -> PublicationListResponse:
    svc = get_medical_affairs_service()
    items = svc.list_publications(
        trial_id=trial_id, status=status, publication_type=publication_type
    )
    return PublicationListResponse(items=items, total=len(items))


@router.get(
    "/publications/search",
    response_model=PublicationListResponse,
    summary="Search publications",
    description="Search publications by title text.",
)
async def search_publications(
    q: str = Query(..., description="Search query"),
) -> PublicationListResponse:
    svc = get_medical_affairs_service()
    items = svc.search_publications(q)
    return PublicationListResponse(items=items, total=len(items))


@router.get(
    "/publications/{pub_id}",
    response_model=Publication,
    summary="Get a publication",
)
async def get_publication(pub_id: str) -> Publication:
    svc = get_medical_affairs_service()
    pub = svc.get_publication(pub_id)
    if pub is None:
        raise HTTPException(status_code=404, detail=f"Publication '{pub_id}' not found")
    return pub


@router.post(
    "/publications",
    response_model=Publication,
    status_code=201,
    summary="Create a publication",
)
async def create_publication(payload: PublicationCreate) -> Publication:
    svc = get_medical_affairs_service()
    return svc.create_publication(payload)


@router.put(
    "/publications/{pub_id}",
    response_model=Publication,
    summary="Update a publication",
)
async def update_publication(pub_id: str, payload: PublicationUpdate) -> Publication:
    svc = get_medical_affairs_service()
    updated = svc.update_publication(pub_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Publication '{pub_id}' not found")
    return updated


@router.delete(
    "/publications/{pub_id}",
    status_code=204,
    summary="Delete a publication",
)
async def delete_publication(pub_id: str) -> None:
    svc = get_medical_affairs_service()
    deleted = svc.delete_publication(pub_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Publication '{pub_id}' not found")


@router.post(
    "/publications/{pub_id}/advance-status",
    response_model=Publication,
    summary="Advance publication status",
    description="Advance a publication through its lifecycle. Automatically sets relevant dates.",
)
async def advance_publication_status(
    pub_id: str,
    status: PublicationStatus = Query(..., description="New status"),
) -> Publication:
    svc = get_medical_affairs_service()
    result = svc.advance_publication_status(pub_id, status)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Publication '{pub_id}' not found")
    return result


@router.post(
    "/publications/{pub_id}/check-icmje",
    response_model=ICMJEComplianceResult,
    summary="Check ICMJE compliance",
    description="Check whether a publication meets ICMJE authorship criteria.",
)
async def check_icmje_compliance(pub_id: str) -> ICMJEComplianceResult:
    svc = get_medical_affairs_service()
    result = svc.check_icmje_compliance(pub_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Publication '{pub_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Congress Plans
# ---------------------------------------------------------------------------


@router.get(
    "/congresses",
    response_model=CongressPlanListResponse,
    summary="List congress plans",
    description="Retrieve congress plans with optional tier filtering.",
)
async def list_congress_plans(
    tier: Optional[CongressTier] = Query(None, description="Filter by congress tier"),
) -> CongressPlanListResponse:
    svc = get_medical_affairs_service()
    items = svc.list_congress_plans(tier=tier)
    return CongressPlanListResponse(items=items, total=len(items))


@router.get(
    "/congresses/{congress_id}",
    response_model=CongressPlan,
    summary="Get a congress plan",
)
async def get_congress_plan(congress_id: str) -> CongressPlan:
    svc = get_medical_affairs_service()
    plan = svc.get_congress_plan(congress_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Congress plan '{congress_id}' not found")
    return plan


@router.post(
    "/congresses",
    response_model=CongressPlan,
    status_code=201,
    summary="Create a congress plan",
)
async def create_congress_plan(payload: CongressPlanCreate) -> CongressPlan:
    svc = get_medical_affairs_service()
    return svc.create_congress_plan(payload)


@router.put(
    "/congresses/{congress_id}",
    response_model=CongressPlan,
    summary="Update a congress plan",
)
async def update_congress_plan(congress_id: str, payload: CongressPlanUpdate) -> CongressPlan:
    svc = get_medical_affairs_service()
    updated = svc.update_congress_plan(congress_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Congress plan '{congress_id}' not found")
    return updated


@router.delete(
    "/congresses/{congress_id}",
    status_code=204,
    summary="Delete a congress plan",
)
async def delete_congress_plan(congress_id: str) -> None:
    svc = get_medical_affairs_service()
    deleted = svc.delete_congress_plan(congress_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Congress plan '{congress_id}' not found")


@router.get(
    "/congresses/{congress_id}/roi",
    response_model=dict[str, Any],
    summary="Get congress ROI",
    description="Calculate return on investment metrics for a congress including acceptance rate and cost per presentation.",
)
async def get_congress_roi(congress_id: str) -> dict[str, Any]:
    svc = get_medical_affairs_service()
    roi = svc.get_congress_roi(congress_id)
    if roi is None:
        raise HTTPException(status_code=404, detail=f"Congress plan '{congress_id}' not found")
    return roi


# ---------------------------------------------------------------------------
# Publication Plans
# ---------------------------------------------------------------------------


@router.get(
    "/publication-plans",
    response_model=PublicationPlanListResponse,
    summary="List publication plans",
    description="Retrieve publication plans with optional trial filtering.",
)
async def list_publication_plans(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> PublicationPlanListResponse:
    svc = get_medical_affairs_service()
    items = svc.list_publication_plans(trial_id=trial_id)
    return PublicationPlanListResponse(items=items, total=len(items))


@router.get(
    "/publication-plans/{plan_id}",
    response_model=PublicationPlan,
    summary="Get a publication plan",
)
async def get_publication_plan(plan_id: str) -> PublicationPlan:
    svc = get_medical_affairs_service()
    plan = svc.get_publication_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Publication plan '{plan_id}' not found")
    return plan


@router.post(
    "/publication-plans",
    response_model=PublicationPlan,
    status_code=201,
    summary="Create a publication plan",
)
async def create_publication_plan(payload: PublicationPlanCreate) -> PublicationPlan:
    svc = get_medical_affairs_service()
    return svc.create_publication_plan(payload)


@router.put(
    "/publication-plans/{plan_id}",
    response_model=PublicationPlan,
    summary="Update a publication plan",
)
async def update_publication_plan(plan_id: str, payload: PublicationPlanUpdate) -> PublicationPlan:
    svc = get_medical_affairs_service()
    updated = svc.update_publication_plan(plan_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Publication plan '{plan_id}' not found")
    return updated


@router.delete(
    "/publication-plans/{plan_id}",
    status_code=204,
    summary="Delete a publication plan",
)
async def delete_publication_plan(plan_id: str) -> None:
    svc = get_medical_affairs_service()
    deleted = svc.delete_publication_plan(plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Publication plan '{plan_id}' not found")


# ---------------------------------------------------------------------------
# Metrics & Analytics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=MedicalAffairsMetrics,
    summary="Get medical affairs metrics",
    description="Aggregated medical affairs metrics across all publications and congresses.",
)
async def get_metrics() -> MedicalAffairsMetrics:
    svc = get_medical_affairs_service()
    return svc.get_metrics()


@router.get(
    "/impact-factor-weighted-count",
    response_model=dict[str, float],
    summary="Get impact factor weighted count",
    description="Sum of impact factors for all published/accepted publications.",
)
async def get_impact_factor_weighted_count() -> dict[str, float]:
    svc = get_medical_affairs_service()
    count = svc.get_impact_factor_weighted_count()
    return {"impact_factor_weighted_count": count}


@router.get(
    "/journal-tier/{impact_factor}",
    response_model=dict[str, str],
    summary="Classify journal impact tier",
    description="Classify a journal's impact tier based on its impact factor.",
)
async def classify_journal_tier(impact_factor: float) -> dict[str, str]:
    svc = get_medical_affairs_service()
    tier = svc.classify_journal_tier(impact_factor)
    return {"impact_factor": str(impact_factor), "tier": tier.value}
