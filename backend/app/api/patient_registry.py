"""Patient Registry & Long-Term Follow-Up API endpoints (PAT-REG).

Provides registry management, patient enrollment, follow-up visit tracking,
outcome reporting, registry milestones, and operational metrics.

Endpoints:
    GET    /patient-registry/registries                            - List registries
    GET    /patient-registry/registries/{registry_id}              - Get single registry
    POST   /patient-registry/registries                            - Create registry
    PUT    /patient-registry/registries/{registry_id}              - Update registry
    DELETE /patient-registry/registries/{registry_id}              - Delete registry
    GET    /patient-registry/patients                              - List patients
    GET    /patient-registry/patients/{patient_id}                 - Get single patient
    POST   /patient-registry/patients                              - Enroll patient
    PUT    /patient-registry/patients/{patient_id}                 - Update patient
    DELETE /patient-registry/patients/{patient_id}                 - Delete patient
    GET    /patient-registry/visits                                - List follow-up visits
    GET    /patient-registry/visits/{visit_id}                     - Get single visit
    POST   /patient-registry/visits                                - Create visit
    PUT    /patient-registry/visits/{visit_id}                     - Update visit
    DELETE /patient-registry/visits/{visit_id}                     - Delete visit
    GET    /patient-registry/outcomes                              - List outcomes
    GET    /patient-registry/outcomes/{outcome_id}                 - Get single outcome
    POST   /patient-registry/outcomes                              - Create outcome
    DELETE /patient-registry/outcomes/{outcome_id}                 - Delete outcome
    GET    /patient-registry/milestones                            - List milestones
    GET    /patient-registry/milestones/{milestone_id}             - Get single milestone
    POST   /patient-registry/milestones                            - Create milestone
    PUT    /patient-registry/milestones/{milestone_id}             - Update milestone
    DELETE /patient-registry/milestones/{milestone_id}             - Delete milestone
    GET    /patient-registry/metrics                               - Registry metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.patient_registry import (
    EnrollmentStatus,
    FollowUpStatus,
    FollowUpType,
    FollowUpVisit,
    FollowUpVisitCreate,
    FollowUpVisitListResponse,
    FollowUpVisitUpdate,
    OutcomeCategory,
    OutcomeReport,
    OutcomeReportCreate,
    OutcomeReportListResponse,
    PatientRegistryMetrics,
    Registry,
    RegistryCreate,
    RegistryListResponse,
    RegistryMilestone,
    RegistryMilestoneCreate,
    RegistryMilestoneListResponse,
    RegistryMilestoneUpdate,
    RegistryPatient,
    RegistryPatientCreate,
    RegistryPatientListResponse,
    RegistryPatientUpdate,
    RegistryStatus,
    RegistryType,
    RegistryUpdate,
)
from app.services.patient_registry_service import get_patient_registry_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/patient-registry",
    tags=["Patient Registry"],
)


# ---------------------------------------------------------------------------
# Registries
# ---------------------------------------------------------------------------


@router.get(
    "/registries",
    response_model=RegistryListResponse,
    summary="List registries",
    description="Retrieve registries with optional filtering by trial, type, and status.",
)
async def list_registries(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    registry_type: Optional[RegistryType] = Query(None, description="Filter by registry type"),
    status: Optional[RegistryStatus] = Query(None, description="Filter by status"),
) -> RegistryListResponse:
    svc = get_patient_registry_service()
    items = svc.list_registries(trial_id=trial_id, registry_type=registry_type, status=status)
    return RegistryListResponse(items=items, total=len(items))


@router.get(
    "/registries/{registry_id}",
    response_model=Registry,
    summary="Get a registry",
)
async def get_registry(registry_id: str) -> Registry:
    svc = get_patient_registry_service()
    registry = svc.get_registry(registry_id)
    if registry is None:
        raise HTTPException(status_code=404, detail=f"Registry '{registry_id}' not found")
    return registry


@router.post(
    "/registries",
    response_model=Registry,
    status_code=201,
    summary="Create a registry",
)
async def create_registry(payload: RegistryCreate) -> Registry:
    svc = get_patient_registry_service()
    return svc.create_registry(payload)


@router.put(
    "/registries/{registry_id}",
    response_model=Registry,
    summary="Update a registry",
)
async def update_registry(registry_id: str, payload: RegistryUpdate) -> Registry:
    svc = get_patient_registry_service()
    updated = svc.update_registry(registry_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Registry '{registry_id}' not found")
    return updated


@router.delete(
    "/registries/{registry_id}",
    status_code=204,
    summary="Delete a registry",
)
async def delete_registry(registry_id: str) -> None:
    svc = get_patient_registry_service()
    deleted = svc.delete_registry(registry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Registry '{registry_id}' not found")


# ---------------------------------------------------------------------------
# Registry Patients
# ---------------------------------------------------------------------------


@router.get(
    "/patients",
    response_model=RegistryPatientListResponse,
    summary="List registry patients",
    description="Retrieve patients with optional filtering by registry, enrollment status, or patient ID.",
)
async def list_patients(
    registry_id: Optional[str] = Query(None, description="Filter by registry ID"),
    enrollment_status: Optional[EnrollmentStatus] = Query(None, description="Filter by enrollment status"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
) -> RegistryPatientListResponse:
    svc = get_patient_registry_service()
    items = svc.list_patients(
        registry_id=registry_id, enrollment_status=enrollment_status, patient_id=patient_id,
    )
    return RegistryPatientListResponse(items=items, total=len(items))


@router.get(
    "/patients/{patient_id}",
    response_model=RegistryPatient,
    summary="Get a registry patient",
)
async def get_patient(patient_id: str) -> RegistryPatient:
    svc = get_patient_registry_service()
    patient = svc.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail=f"Registry patient '{patient_id}' not found")
    return patient


@router.post(
    "/patients",
    response_model=RegistryPatient,
    status_code=201,
    summary="Enroll a patient in a registry",
)
async def create_patient(payload: RegistryPatientCreate) -> RegistryPatient:
    svc = get_patient_registry_service()
    try:
        return svc.create_patient(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/patients/{patient_id}",
    response_model=RegistryPatient,
    summary="Update a registry patient",
)
async def update_patient(patient_id: str, payload: RegistryPatientUpdate) -> RegistryPatient:
    svc = get_patient_registry_service()
    updated = svc.update_patient(patient_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Registry patient '{patient_id}' not found")
    return updated


@router.delete(
    "/patients/{patient_id}",
    status_code=204,
    summary="Delete a registry patient",
)
async def delete_patient(patient_id: str) -> None:
    svc = get_patient_registry_service()
    deleted = svc.delete_patient(patient_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Registry patient '{patient_id}' not found")


# ---------------------------------------------------------------------------
# Follow-Up Visits
# ---------------------------------------------------------------------------


@router.get(
    "/visits",
    response_model=FollowUpVisitListResponse,
    summary="List follow-up visits",
    description="Retrieve follow-up visits with optional filtering by patient, type, and status.",
)
async def list_visits(
    registry_patient_id: Optional[str] = Query(None, description="Filter by registry patient ID"),
    visit_type: Optional[FollowUpType] = Query(None, description="Filter by visit type"),
    visit_status: Optional[FollowUpStatus] = Query(None, description="Filter by visit status"),
) -> FollowUpVisitListResponse:
    svc = get_patient_registry_service()
    items = svc.list_visits(
        registry_patient_id=registry_patient_id, visit_type=visit_type, visit_status=visit_status,
    )
    return FollowUpVisitListResponse(items=items, total=len(items))


@router.get(
    "/visits/{visit_id}",
    response_model=FollowUpVisit,
    summary="Get a follow-up visit",
)
async def get_visit(visit_id: str) -> FollowUpVisit:
    svc = get_patient_registry_service()
    visit = svc.get_visit(visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail=f"Follow-up visit '{visit_id}' not found")
    return visit


@router.post(
    "/visits",
    response_model=FollowUpVisit,
    status_code=201,
    summary="Create a follow-up visit",
)
async def create_visit(payload: FollowUpVisitCreate) -> FollowUpVisit:
    svc = get_patient_registry_service()
    try:
        return svc.create_visit(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/visits/{visit_id}",
    response_model=FollowUpVisit,
    summary="Update a follow-up visit",
)
async def update_visit(visit_id: str, payload: FollowUpVisitUpdate) -> FollowUpVisit:
    svc = get_patient_registry_service()
    updated = svc.update_visit(visit_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Follow-up visit '{visit_id}' not found")
    return updated


@router.delete(
    "/visits/{visit_id}",
    status_code=204,
    summary="Delete a follow-up visit",
)
async def delete_visit(visit_id: str) -> None:
    svc = get_patient_registry_service()
    deleted = svc.delete_visit(visit_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Follow-up visit '{visit_id}' not found")


# ---------------------------------------------------------------------------
# Outcome Reports
# ---------------------------------------------------------------------------


@router.get(
    "/outcomes",
    response_model=OutcomeReportListResponse,
    summary="List outcome reports",
    description="Retrieve outcome reports with optional filtering by patient and category.",
)
async def list_outcomes(
    registry_patient_id: Optional[str] = Query(None, description="Filter by registry patient ID"),
    category: Optional[OutcomeCategory] = Query(None, description="Filter by outcome category"),
) -> OutcomeReportListResponse:
    svc = get_patient_registry_service()
    items = svc.list_outcomes(registry_patient_id=registry_patient_id, category=category)
    return OutcomeReportListResponse(items=items, total=len(items))


@router.get(
    "/outcomes/{outcome_id}",
    response_model=OutcomeReport,
    summary="Get an outcome report",
)
async def get_outcome(outcome_id: str) -> OutcomeReport:
    svc = get_patient_registry_service()
    outcome = svc.get_outcome(outcome_id)
    if outcome is None:
        raise HTTPException(status_code=404, detail=f"Outcome report '{outcome_id}' not found")
    return outcome


@router.post(
    "/outcomes",
    response_model=OutcomeReport,
    status_code=201,
    summary="Create an outcome report",
)
async def create_outcome(payload: OutcomeReportCreate) -> OutcomeReport:
    svc = get_patient_registry_service()
    try:
        return svc.create_outcome(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete(
    "/outcomes/{outcome_id}",
    status_code=204,
    summary="Delete an outcome report",
)
async def delete_outcome(outcome_id: str) -> None:
    svc = get_patient_registry_service()
    deleted = svc.delete_outcome(outcome_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Outcome report '{outcome_id}' not found")


# ---------------------------------------------------------------------------
# Registry Milestones
# ---------------------------------------------------------------------------


@router.get(
    "/milestones",
    response_model=RegistryMilestoneListResponse,
    summary="List registry milestones",
    description="Retrieve milestones with optional filtering by registry.",
)
async def list_milestones(
    registry_id: Optional[str] = Query(None, description="Filter by registry ID"),
) -> RegistryMilestoneListResponse:
    svc = get_patient_registry_service()
    items = svc.list_milestones(registry_id=registry_id)
    return RegistryMilestoneListResponse(items=items, total=len(items))


@router.get(
    "/milestones/{milestone_id}",
    response_model=RegistryMilestone,
    summary="Get a registry milestone",
)
async def get_milestone(milestone_id: str) -> RegistryMilestone:
    svc = get_patient_registry_service()
    milestone = svc.get_milestone(milestone_id)
    if milestone is None:
        raise HTTPException(status_code=404, detail=f"Milestone '{milestone_id}' not found")
    return milestone


@router.post(
    "/milestones",
    response_model=RegistryMilestone,
    status_code=201,
    summary="Create a registry milestone",
)
async def create_milestone(payload: RegistryMilestoneCreate) -> RegistryMilestone:
    svc = get_patient_registry_service()
    try:
        return svc.create_milestone(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/milestones/{milestone_id}",
    response_model=RegistryMilestone,
    summary="Update a registry milestone",
)
async def update_milestone(milestone_id: str, payload: RegistryMilestoneUpdate) -> RegistryMilestone:
    svc = get_patient_registry_service()
    updated = svc.update_milestone(milestone_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Milestone '{milestone_id}' not found")
    return updated


@router.delete(
    "/milestones/{milestone_id}",
    status_code=204,
    summary="Delete a registry milestone",
)
async def delete_milestone(milestone_id: str) -> None:
    svc = get_patient_registry_service()
    deleted = svc.delete_milestone(milestone_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Milestone '{milestone_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=PatientRegistryMetrics,
    summary="Get patient registry metrics",
    description="Aggregated patient registry operational metrics across all registries.",
)
async def get_metrics() -> PatientRegistryMetrics:
    svc = get_patient_registry_service()
    return svc.get_metrics()
