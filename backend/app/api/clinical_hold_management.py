"""Clinical Hold Management (CHM-MGT) API endpoints.

Manages clinical hold operations: hold events, impact assessments, corrective
action plans, restart authorizations, and clinical hold metrics.

Endpoints:
    GET    /clinical-hold-management/hold-events                        - List hold events
    GET    /clinical-hold-management/hold-events/{hold_event_id}        - Get single hold event
    POST   /clinical-hold-management/hold-events                        - Create hold event
    PUT    /clinical-hold-management/hold-events/{hold_event_id}        - Update hold event
    DELETE /clinical-hold-management/hold-events/{hold_event_id}        - Delete hold event
    GET    /clinical-hold-management/impact-assessments                 - List impact assessments
    GET    /clinical-hold-management/impact-assessments/{assessment_id} - Get single assessment
    POST   /clinical-hold-management/impact-assessments                 - Create impact assessment
    PUT    /clinical-hold-management/impact-assessments/{assessment_id} - Update impact assessment
    DELETE /clinical-hold-management/impact-assessments/{assessment_id} - Delete impact assessment
    GET    /clinical-hold-management/corrective-action-plans            - List corrective action plans
    GET    /clinical-hold-management/corrective-action-plans/{plan_id}  - Get single plan
    POST   /clinical-hold-management/corrective-action-plans            - Create corrective action plan
    PUT    /clinical-hold-management/corrective-action-plans/{plan_id}  - Update corrective action plan
    DELETE /clinical-hold-management/corrective-action-plans/{plan_id}  - Delete corrective action plan
    GET    /clinical-hold-management/restart-authorizations             - List restart authorizations
    GET    /clinical-hold-management/restart-authorizations/{auth_id}   - Get single authorization
    POST   /clinical-hold-management/restart-authorizations             - Create restart authorization
    PUT    /clinical-hold-management/restart-authorizations/{auth_id}   - Update restart authorization
    DELETE /clinical-hold-management/restart-authorizations/{auth_id}   - Delete restart authorization
    GET    /clinical-hold-management/metrics                            - Clinical hold metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.clinical_hold_management import (
    ClinicalHoldMetrics,
    CorrectiveActionPlan,
    CorrectiveActionPlanCreate,
    CorrectiveActionPlanListResponse,
    CorrectiveActionPlanUpdate,
    HoldEvent,
    HoldEventCreate,
    HoldEventListResponse,
    HoldEventUpdate,
    ImpactAssessment,
    ImpactAssessmentCreate,
    ImpactAssessmentListResponse,
    ImpactAssessmentUpdate,
    RestartAuthorization,
    RestartAuthorizationCreate,
    RestartAuthorizationListResponse,
    RestartAuthorizationUpdate,
)
from app.services.clinical_hold_management_service import get_clinical_hold_management_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/clinical-hold-management",
    tags=["Clinical Hold Management"],
)


# ---------------------------------------------------------------------------
# Hold Events
# ---------------------------------------------------------------------------


@router.get(
    "/hold-events",
    response_model=HoldEventListResponse,
    summary="List hold events",
    description="Retrieve hold events with optional filtering by trial ID.",
)
async def list_hold_events(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> HoldEventListResponse:
    svc = get_clinical_hold_management_service()
    items = svc.list_hold_events(trial_id=trial_id)
    return HoldEventListResponse(items=items, total=len(items))


@router.get(
    "/hold-events/{hold_event_id}",
    response_model=HoldEvent,
    summary="Get a hold event",
)
async def get_hold_event(hold_event_id: str) -> HoldEvent:
    svc = get_clinical_hold_management_service()
    event = svc.get_hold_event(hold_event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"Hold event '{hold_event_id}' not found")
    return event


@router.post(
    "/hold-events",
    response_model=HoldEvent,
    status_code=201,
    summary="Create a hold event",
)
async def create_hold_event(payload: HoldEventCreate) -> HoldEvent:
    svc = get_clinical_hold_management_service()
    return svc.create_hold_event(payload)


@router.put(
    "/hold-events/{hold_event_id}",
    response_model=HoldEvent,
    summary="Update a hold event",
)
async def update_hold_event(hold_event_id: str, payload: HoldEventUpdate) -> HoldEvent:
    svc = get_clinical_hold_management_service()
    updated = svc.update_hold_event(hold_event_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Hold event '{hold_event_id}' not found")
    return updated


@router.delete(
    "/hold-events/{hold_event_id}",
    status_code=204,
    summary="Delete a hold event",
)
async def delete_hold_event(hold_event_id: str) -> None:
    svc = get_clinical_hold_management_service()
    deleted = svc.delete_hold_event(hold_event_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Hold event '{hold_event_id}' not found")


# ---------------------------------------------------------------------------
# Impact Assessments
# ---------------------------------------------------------------------------


@router.get(
    "/impact-assessments",
    response_model=ImpactAssessmentListResponse,
    summary="List impact assessments",
    description="Retrieve impact assessments with optional filtering by trial ID.",
)
async def list_impact_assessments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> ImpactAssessmentListResponse:
    svc = get_clinical_hold_management_service()
    items = svc.list_impact_assessments(trial_id=trial_id)
    return ImpactAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/impact-assessments/{assessment_id}",
    response_model=ImpactAssessment,
    summary="Get an impact assessment",
)
async def get_impact_assessment(assessment_id: str) -> ImpactAssessment:
    svc = get_clinical_hold_management_service()
    assessment = svc.get_impact_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Impact assessment '{assessment_id}' not found")
    return assessment


@router.post(
    "/impact-assessments",
    response_model=ImpactAssessment,
    status_code=201,
    summary="Create an impact assessment",
)
async def create_impact_assessment(payload: ImpactAssessmentCreate) -> ImpactAssessment:
    svc = get_clinical_hold_management_service()
    return svc.create_impact_assessment(payload)


@router.put(
    "/impact-assessments/{assessment_id}",
    response_model=ImpactAssessment,
    summary="Update an impact assessment",
)
async def update_impact_assessment(assessment_id: str, payload: ImpactAssessmentUpdate) -> ImpactAssessment:
    svc = get_clinical_hold_management_service()
    updated = svc.update_impact_assessment(assessment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Impact assessment '{assessment_id}' not found")
    return updated


@router.delete(
    "/impact-assessments/{assessment_id}",
    status_code=204,
    summary="Delete an impact assessment",
)
async def delete_impact_assessment(assessment_id: str) -> None:
    svc = get_clinical_hold_management_service()
    deleted = svc.delete_impact_assessment(assessment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Impact assessment '{assessment_id}' not found")


# ---------------------------------------------------------------------------
# Corrective Action Plans
# ---------------------------------------------------------------------------


@router.get(
    "/corrective-action-plans",
    response_model=CorrectiveActionPlanListResponse,
    summary="List corrective action plans",
    description="Retrieve corrective action plans with optional filtering by trial ID.",
)
async def list_corrective_action_plans(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> CorrectiveActionPlanListResponse:
    svc = get_clinical_hold_management_service()
    items = svc.list_corrective_action_plans(trial_id=trial_id)
    return CorrectiveActionPlanListResponse(items=items, total=len(items))


@router.get(
    "/corrective-action-plans/{plan_id}",
    response_model=CorrectiveActionPlan,
    summary="Get a corrective action plan",
)
async def get_corrective_action_plan(plan_id: str) -> CorrectiveActionPlan:
    svc = get_clinical_hold_management_service()
    plan = svc.get_corrective_action_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Corrective action plan '{plan_id}' not found")
    return plan


@router.post(
    "/corrective-action-plans",
    response_model=CorrectiveActionPlan,
    status_code=201,
    summary="Create a corrective action plan",
)
async def create_corrective_action_plan(payload: CorrectiveActionPlanCreate) -> CorrectiveActionPlan:
    svc = get_clinical_hold_management_service()
    return svc.create_corrective_action_plan(payload)


@router.put(
    "/corrective-action-plans/{plan_id}",
    response_model=CorrectiveActionPlan,
    summary="Update a corrective action plan",
)
async def update_corrective_action_plan(plan_id: str, payload: CorrectiveActionPlanUpdate) -> CorrectiveActionPlan:
    svc = get_clinical_hold_management_service()
    updated = svc.update_corrective_action_plan(plan_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Corrective action plan '{plan_id}' not found")
    return updated


@router.delete(
    "/corrective-action-plans/{plan_id}",
    status_code=204,
    summary="Delete a corrective action plan",
)
async def delete_corrective_action_plan(plan_id: str) -> None:
    svc = get_clinical_hold_management_service()
    deleted = svc.delete_corrective_action_plan(plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Corrective action plan '{plan_id}' not found")


# ---------------------------------------------------------------------------
# Restart Authorizations
# ---------------------------------------------------------------------------


@router.get(
    "/restart-authorizations",
    response_model=RestartAuthorizationListResponse,
    summary="List restart authorizations",
    description="Retrieve restart authorizations with optional filtering by trial ID.",
)
async def list_restart_authorizations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> RestartAuthorizationListResponse:
    svc = get_clinical_hold_management_service()
    items = svc.list_restart_authorizations(trial_id=trial_id)
    return RestartAuthorizationListResponse(items=items, total=len(items))


@router.get(
    "/restart-authorizations/{auth_id}",
    response_model=RestartAuthorization,
    summary="Get a restart authorization",
)
async def get_restart_authorization(auth_id: str) -> RestartAuthorization:
    svc = get_clinical_hold_management_service()
    auth = svc.get_restart_authorization(auth_id)
    if auth is None:
        raise HTTPException(status_code=404, detail=f"Restart authorization '{auth_id}' not found")
    return auth


@router.post(
    "/restart-authorizations",
    response_model=RestartAuthorization,
    status_code=201,
    summary="Create a restart authorization",
)
async def create_restart_authorization(payload: RestartAuthorizationCreate) -> RestartAuthorization:
    svc = get_clinical_hold_management_service()
    return svc.create_restart_authorization(payload)


@router.put(
    "/restart-authorizations/{auth_id}",
    response_model=RestartAuthorization,
    summary="Update a restart authorization",
)
async def update_restart_authorization(auth_id: str, payload: RestartAuthorizationUpdate) -> RestartAuthorization:
    svc = get_clinical_hold_management_service()
    updated = svc.update_restart_authorization(auth_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Restart authorization '{auth_id}' not found")
    return updated


@router.delete(
    "/restart-authorizations/{auth_id}",
    status_code=204,
    summary="Delete a restart authorization",
)
async def delete_restart_authorization(auth_id: str) -> None:
    svc = get_clinical_hold_management_service()
    deleted = svc.delete_restart_authorization(auth_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Restart authorization '{auth_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=ClinicalHoldMetrics,
    summary="Get clinical hold metrics",
    description="Aggregated clinical hold metrics across all entities, optionally filtered by trial.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> ClinicalHoldMetrics:
    svc = get_clinical_hold_management_service()
    return svc.get_metrics(trial_id=trial_id)
