"""Dose Escalation Management (DOSE-ESC) API endpoints.

Provides comprehensive dose-finding operations: dose level definitions,
escalation/de-escalation decisions, dose-limiting toxicity (DLT) tracking,
PK result management, RP2D recommendation, and operational metrics.

Endpoints:
    GET    /dose-escalation/dose-levels                     - List dose levels
    GET    /dose-escalation/dose-levels/{dose_level_id}     - Get single dose level
    POST   /dose-escalation/dose-levels                     - Create dose level
    PUT    /dose-escalation/dose-levels/{dose_level_id}     - Update dose level
    DELETE /dose-escalation/dose-levels/{dose_level_id}     - Delete dose level
    GET    /dose-escalation/dlt-events                      - List DLT events
    GET    /dose-escalation/dlt-events/{dlt_event_id}       - Get single DLT event
    POST   /dose-escalation/dlt-events                      - Create DLT event
    PUT    /dose-escalation/dlt-events/{dlt_event_id}       - Update DLT event
    DELETE /dose-escalation/dlt-events/{dlt_event_id}       - Delete DLT event
    GET    /dose-escalation/cohort-decisions                 - List cohort decisions
    GET    /dose-escalation/cohort-decisions/{decision_id}   - Get single decision
    POST   /dose-escalation/cohort-decisions                 - Create cohort decision
    PUT    /dose-escalation/cohort-decisions/{decision_id}   - Update cohort decision
    DELETE /dose-escalation/cohort-decisions/{decision_id}   - Delete cohort decision
    GET    /dose-escalation/pk-results                       - List PK results
    GET    /dose-escalation/pk-results/{pk_result_id}        - Get single PK result
    POST   /dose-escalation/pk-results                       - Create PK result
    PUT    /dose-escalation/pk-results/{pk_result_id}        - Update PK result
    DELETE /dose-escalation/pk-results/{pk_result_id}        - Delete PK result
    GET    /dose-escalation/rp2d-recommendations              - List RP2D recommendations
    GET    /dose-escalation/rp2d-recommendations/{rp2d_id}    - Get single RP2D
    POST   /dose-escalation/rp2d-recommendations              - Create RP2D
    PUT    /dose-escalation/rp2d-recommendations/{rp2d_id}    - Update RP2D
    DELETE /dose-escalation/rp2d-recommendations/{rp2d_id}    - Delete RP2D
    GET    /dose-escalation/metrics                           - Dose escalation metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.dose_escalation import (
    CohortDecision,
    CohortDecisionCreate,
    CohortDecisionListResponse,
    CohortDecisionUpdate,
    DLTEvent,
    DLTEventCreate,
    DLTEventListResponse,
    DLTEventUpdate,
    DoseEscalationMetrics,
    DoseLevel,
    DoseLevelCreate,
    DoseLevelListResponse,
    DoseLevelUpdate,
    PKResult,
    PKResultCreate,
    PKResultListResponse,
    PKResultUpdate,
    RP2DRecommendation,
    RP2DRecommendationCreate,
    RP2DRecommendationListResponse,
    RP2DRecommendationUpdate,
)
from app.services.dose_escalation_service import get_dose_escalation_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/dose-escalation",
    tags=["Dose Escalation Management"],
)


# ---------------------------------------------------------------------------
# Dose Level Management
# ---------------------------------------------------------------------------


@router.get(
    "/dose-levels",
    response_model=DoseLevelListResponse,
    summary="List dose levels",
    description="Retrieve dose levels with optional filtering by trial.",
)
async def list_dose_levels(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> DoseLevelListResponse:
    svc = get_dose_escalation_service()
    items = svc.list_dose_levels(trial_id=trial_id)
    return DoseLevelListResponse(items=items, total=len(items))


@router.get(
    "/dose-levels/{dose_level_id}",
    response_model=DoseLevel,
    summary="Get a dose level",
)
async def get_dose_level(dose_level_id: str) -> DoseLevel:
    svc = get_dose_escalation_service()
    dose_level = svc.get_dose_level(dose_level_id)
    if dose_level is None:
        raise HTTPException(status_code=404, detail=f"Dose level '{dose_level_id}' not found")
    return dose_level


@router.post(
    "/dose-levels",
    response_model=DoseLevel,
    status_code=201,
    summary="Create a dose level",
)
async def create_dose_level(payload: DoseLevelCreate) -> DoseLevel:
    svc = get_dose_escalation_service()
    return svc.create_dose_level(payload)


@router.put(
    "/dose-levels/{dose_level_id}",
    response_model=DoseLevel,
    summary="Update a dose level",
)
async def update_dose_level(
    dose_level_id: str, payload: DoseLevelUpdate
) -> DoseLevel:
    svc = get_dose_escalation_service()
    updated = svc.update_dose_level(dose_level_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Dose level '{dose_level_id}' not found")
    return updated


@router.delete(
    "/dose-levels/{dose_level_id}",
    status_code=204,
    summary="Delete a dose level",
)
async def delete_dose_level(dose_level_id: str) -> None:
    svc = get_dose_escalation_service()
    deleted = svc.delete_dose_level(dose_level_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Dose level '{dose_level_id}' not found")


# ---------------------------------------------------------------------------
# DLT Event Management
# ---------------------------------------------------------------------------


@router.get(
    "/dlt-events",
    response_model=DLTEventListResponse,
    summary="List DLT events",
    description="Retrieve dose-limiting toxicity events with optional filtering by trial.",
)
async def list_dlt_events(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> DLTEventListResponse:
    svc = get_dose_escalation_service()
    items = svc.list_dlt_events(trial_id=trial_id)
    return DLTEventListResponse(items=items, total=len(items))


@router.get(
    "/dlt-events/{dlt_event_id}",
    response_model=DLTEvent,
    summary="Get a DLT event",
)
async def get_dlt_event(dlt_event_id: str) -> DLTEvent:
    svc = get_dose_escalation_service()
    dlt_event = svc.get_dlt_event(dlt_event_id)
    if dlt_event is None:
        raise HTTPException(status_code=404, detail=f"DLT event '{dlt_event_id}' not found")
    return dlt_event


@router.post(
    "/dlt-events",
    response_model=DLTEvent,
    status_code=201,
    summary="Create a DLT event",
)
async def create_dlt_event(payload: DLTEventCreate) -> DLTEvent:
    svc = get_dose_escalation_service()
    return svc.create_dlt_event(payload)


@router.put(
    "/dlt-events/{dlt_event_id}",
    response_model=DLTEvent,
    summary="Update a DLT event",
)
async def update_dlt_event(
    dlt_event_id: str, payload: DLTEventUpdate
) -> DLTEvent:
    svc = get_dose_escalation_service()
    updated = svc.update_dlt_event(dlt_event_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"DLT event '{dlt_event_id}' not found")
    return updated


@router.delete(
    "/dlt-events/{dlt_event_id}",
    status_code=204,
    summary="Delete a DLT event",
)
async def delete_dlt_event(dlt_event_id: str) -> None:
    svc = get_dose_escalation_service()
    deleted = svc.delete_dlt_event(dlt_event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"DLT event '{dlt_event_id}' not found")


# ---------------------------------------------------------------------------
# Cohort Decision Management
# ---------------------------------------------------------------------------


@router.get(
    "/cohort-decisions",
    response_model=CohortDecisionListResponse,
    summary="List cohort decisions",
    description="Retrieve escalation/de-escalation decisions with optional filtering by trial.",
)
async def list_cohort_decisions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> CohortDecisionListResponse:
    svc = get_dose_escalation_service()
    items = svc.list_cohort_decisions(trial_id=trial_id)
    return CohortDecisionListResponse(items=items, total=len(items))


@router.get(
    "/cohort-decisions/{decision_id}",
    response_model=CohortDecision,
    summary="Get a cohort decision",
)
async def get_cohort_decision(decision_id: str) -> CohortDecision:
    svc = get_dose_escalation_service()
    decision = svc.get_cohort_decision(decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail=f"Cohort decision '{decision_id}' not found")
    return decision


@router.post(
    "/cohort-decisions",
    response_model=CohortDecision,
    status_code=201,
    summary="Create a cohort decision",
)
async def create_cohort_decision(payload: CohortDecisionCreate) -> CohortDecision:
    svc = get_dose_escalation_service()
    return svc.create_cohort_decision(payload)


@router.put(
    "/cohort-decisions/{decision_id}",
    response_model=CohortDecision,
    summary="Update a cohort decision",
)
async def update_cohort_decision(
    decision_id: str, payload: CohortDecisionUpdate
) -> CohortDecision:
    svc = get_dose_escalation_service()
    updated = svc.update_cohort_decision(decision_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Cohort decision '{decision_id}' not found")
    return updated


@router.delete(
    "/cohort-decisions/{decision_id}",
    status_code=204,
    summary="Delete a cohort decision",
)
async def delete_cohort_decision(decision_id: str) -> None:
    svc = get_dose_escalation_service()
    deleted = svc.delete_cohort_decision(decision_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Cohort decision '{decision_id}' not found")


# ---------------------------------------------------------------------------
# PK Result Management
# ---------------------------------------------------------------------------


@router.get(
    "/pk-results",
    response_model=PKResultListResponse,
    summary="List PK results",
    description="Retrieve pharmacokinetic results with optional filtering by trial.",
)
async def list_pk_results(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> PKResultListResponse:
    svc = get_dose_escalation_service()
    items = svc.list_pk_results(trial_id=trial_id)
    return PKResultListResponse(items=items, total=len(items))


@router.get(
    "/pk-results/{pk_result_id}",
    response_model=PKResult,
    summary="Get a PK result",
)
async def get_pk_result(pk_result_id: str) -> PKResult:
    svc = get_dose_escalation_service()
    pk_result = svc.get_pk_result(pk_result_id)
    if pk_result is None:
        raise HTTPException(status_code=404, detail=f"PK result '{pk_result_id}' not found")
    return pk_result


@router.post(
    "/pk-results",
    response_model=PKResult,
    status_code=201,
    summary="Create a PK result",
)
async def create_pk_result(payload: PKResultCreate) -> PKResult:
    svc = get_dose_escalation_service()
    return svc.create_pk_result(payload)


@router.put(
    "/pk-results/{pk_result_id}",
    response_model=PKResult,
    summary="Update a PK result",
)
async def update_pk_result(
    pk_result_id: str, payload: PKResultUpdate
) -> PKResult:
    svc = get_dose_escalation_service()
    updated = svc.update_pk_result(pk_result_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"PK result '{pk_result_id}' not found")
    return updated


@router.delete(
    "/pk-results/{pk_result_id}",
    status_code=204,
    summary="Delete a PK result",
)
async def delete_pk_result(pk_result_id: str) -> None:
    svc = get_dose_escalation_service()
    deleted = svc.delete_pk_result(pk_result_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"PK result '{pk_result_id}' not found")


# ---------------------------------------------------------------------------
# RP2D Recommendation Management
# ---------------------------------------------------------------------------


@router.get(
    "/rp2d-recommendations",
    response_model=RP2DRecommendationListResponse,
    summary="List RP2D recommendations",
    description="Retrieve recommended phase 2 dose recommendations with optional filtering by trial.",
)
async def list_rp2d_recommendations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> RP2DRecommendationListResponse:
    svc = get_dose_escalation_service()
    items = svc.list_rp2d_recommendations(trial_id=trial_id)
    return RP2DRecommendationListResponse(items=items, total=len(items))


@router.get(
    "/rp2d-recommendations/{rp2d_id}",
    response_model=RP2DRecommendation,
    summary="Get an RP2D recommendation",
)
async def get_rp2d_recommendation(rp2d_id: str) -> RP2DRecommendation:
    svc = get_dose_escalation_service()
    recommendation = svc.get_rp2d_recommendation(rp2d_id)
    if recommendation is None:
        raise HTTPException(status_code=404, detail=f"RP2D recommendation '{rp2d_id}' not found")
    return recommendation


@router.post(
    "/rp2d-recommendations",
    response_model=RP2DRecommendation,
    status_code=201,
    summary="Create an RP2D recommendation",
)
async def create_rp2d_recommendation(
    payload: RP2DRecommendationCreate,
) -> RP2DRecommendation:
    svc = get_dose_escalation_service()
    return svc.create_rp2d_recommendation(payload)


@router.put(
    "/rp2d-recommendations/{rp2d_id}",
    response_model=RP2DRecommendation,
    summary="Update an RP2D recommendation",
)
async def update_rp2d_recommendation(
    rp2d_id: str, payload: RP2DRecommendationUpdate
) -> RP2DRecommendation:
    svc = get_dose_escalation_service()
    updated = svc.update_rp2d_recommendation(rp2d_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"RP2D recommendation '{rp2d_id}' not found")
    return updated


@router.delete(
    "/rp2d-recommendations/{rp2d_id}",
    status_code=204,
    summary="Delete an RP2D recommendation",
)
async def delete_rp2d_recommendation(rp2d_id: str) -> None:
    svc = get_dose_escalation_service()
    deleted = svc.delete_rp2d_recommendation(rp2d_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"RP2D recommendation '{rp2d_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=DoseEscalationMetrics,
    summary="Get dose escalation metrics",
    description="Aggregated dose escalation metrics including DLT rates, "
                "escalation decisions, PK results, and RP2D status.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> DoseEscalationMetrics:
    svc = get_dose_escalation_service()
    return svc.get_metrics(trial_id=trial_id)
