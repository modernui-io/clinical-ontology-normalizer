"""Clinical Trial Management System (CTMS) Core API endpoints (CLINICAL-22).

Provides comprehensive CTMS operations: trial lifecycle management, site activation
and enrollment tracking, patient/subject management, visit scheduling and window
compliance, source data verification, enrollment summaries, and CTMS metrics.

Endpoints:
    GET    /ctms/trials                                 - List trials
    GET    /ctms/trials/{trial_id}                      - Get single trial
    POST   /ctms/trials                                 - Create trial
    PUT    /ctms/trials/{trial_id}                      - Update trial
    DELETE /ctms/trials/{trial_id}                      - Delete trial
    GET    /ctms/trials/{trial_id}/enrollment-summary   - Enrollment summary
    GET    /ctms/trials/{trial_id}/visit-compliance     - Visit compliance metrics
    GET    /ctms/sites                                  - List sites
    GET    /ctms/sites/{site_id}                        - Get single site
    POST   /ctms/sites                                  - Create site
    PUT    /ctms/sites/{site_id}                        - Update site
    DELETE /ctms/sites/{site_id}                        - Delete site
    GET    /ctms/sites/{site_id}/enrollment             - Site enrollment details
    GET    /ctms/patients                               - List patients
    GET    /ctms/patients/{patient_id}                  - Get single patient
    POST   /ctms/patients                               - Screen new patient
    PUT    /ctms/patients/{patient_id}                  - Update patient
    DELETE /ctms/patients/{patient_id}                  - Delete patient
    GET    /ctms/visits                                 - List visits
    GET    /ctms/visits/{visit_id}                      - Get single visit
    POST   /ctms/visits                                 - Schedule visit
    PUT    /ctms/visits/{visit_id}                      - Update visit
    DELETE /ctms/visits/{visit_id}                      - Delete visit
    GET    /ctms/metrics                                - CTMS dashboard metrics
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.ctms_core import (
    CTMSMetrics,
    CTMSPatient,
    CTMSSite,
    CTMSTrial,
    CTMSVisit,
    PatientCreate,
    PatientListResponse,
    PatientStatus,
    PatientUpdate,
    SiteCreate,
    SiteListResponse,
    SiteStatus,
    SiteUpdate,
    StudyDesign,
    TherapeuticArea,
    TrialCreate,
    TrialListResponse,
    TrialPhase,
    TrialStatus,
    TrialUpdate,
    VisitCreate,
    VisitListResponse,
    VisitStatus,
    VisitUpdate,
)
from app.services.ctms_core_service import get_ctms_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ctms",
    tags=["Clinical Trial Management"],
)


# ---------------------------------------------------------------------------
# Trial Management
# ---------------------------------------------------------------------------


@router.get(
    "/trials",
    response_model=TrialListResponse,
    summary="List clinical trials",
    description="Retrieve trials with optional filtering by phase, status, and therapeutic area.",
)
async def list_trials(
    phase: Optional[TrialPhase] = Query(None, description="Filter by trial phase"),
    status: Optional[TrialStatus] = Query(None, description="Filter by trial status"),
    therapeutic_area: Optional[TherapeuticArea] = Query(
        None, description="Filter by therapeutic area"
    ),
) -> TrialListResponse:
    svc = get_ctms_service()
    items = svc.list_trials(phase=phase, status=status, therapeutic_area=therapeutic_area)
    return TrialListResponse(items=items, total=len(items))


@router.get(
    "/trials/{trial_id}",
    response_model=CTMSTrial,
    summary="Get a clinical trial",
)
async def get_trial(trial_id: str) -> CTMSTrial:
    svc = get_ctms_service()
    trial = svc.get_trial(trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail=f"Trial '{trial_id}' not found")
    return trial


@router.post(
    "/trials",
    response_model=CTMSTrial,
    status_code=201,
    summary="Create a clinical trial",
)
async def create_trial(payload: TrialCreate) -> CTMSTrial:
    svc = get_ctms_service()
    return svc.create_trial(payload)


@router.put(
    "/trials/{trial_id}",
    response_model=CTMSTrial,
    summary="Update a clinical trial",
)
async def update_trial(trial_id: str, payload: TrialUpdate) -> CTMSTrial:
    svc = get_ctms_service()
    updated = svc.update_trial(trial_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Trial '{trial_id}' not found")
    return updated


@router.delete(
    "/trials/{trial_id}",
    status_code=204,
    summary="Delete a clinical trial",
)
async def delete_trial(trial_id: str) -> None:
    svc = get_ctms_service()
    deleted = svc.delete_trial(trial_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Trial '{trial_id}' not found")


@router.get(
    "/trials/{trial_id}/enrollment-summary",
    response_model=dict[str, Any],
    summary="Get trial enrollment summary",
    description="Retrieve enrollment metrics including screen failure rate, enrollment rate, and patient status breakdown.",
)
async def get_enrollment_summary(trial_id: str) -> dict[str, Any]:
    svc = get_ctms_service()
    summary = svc.get_enrollment_summary(trial_id)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"Trial '{trial_id}' not found")
    return summary


@router.get(
    "/trials/{trial_id}/visit-compliance",
    response_model=dict[str, Any],
    summary="Get visit compliance metrics",
    description="Retrieve visit compliance metrics including in-window rate, SDV rate, and visit status breakdown.",
)
async def get_visit_compliance(trial_id: str) -> dict[str, Any]:
    svc = get_ctms_service()
    compliance = svc.get_visit_compliance(trial_id)
    if compliance is None:
        raise HTTPException(status_code=404, detail=f"Trial '{trial_id}' not found")
    return compliance


# ---------------------------------------------------------------------------
# Site Management
# ---------------------------------------------------------------------------


@router.get(
    "/sites",
    response_model=SiteListResponse,
    summary="List trial sites",
    description="Retrieve sites with optional filtering by trial, status, and country.",
)
async def list_sites(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[SiteStatus] = Query(None, description="Filter by site status"),
    country: Optional[str] = Query(None, description="Filter by country code"),
) -> SiteListResponse:
    svc = get_ctms_service()
    items = svc.list_sites(trial_id=trial_id, status=status, country=country)
    return SiteListResponse(items=items, total=len(items))


@router.get(
    "/sites/{site_id}",
    response_model=CTMSSite,
    summary="Get a trial site",
)
async def get_site(site_id: str) -> CTMSSite:
    svc = get_ctms_service()
    site = svc.get_site(site_id)
    if site is None:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")
    return site


@router.post(
    "/sites",
    response_model=CTMSSite,
    status_code=201,
    summary="Create a trial site",
)
async def create_site(payload: SiteCreate) -> CTMSSite:
    svc = get_ctms_service()
    return svc.create_site(payload)


@router.put(
    "/sites/{site_id}",
    response_model=CTMSSite,
    summary="Update a trial site",
)
async def update_site(site_id: str, payload: SiteUpdate) -> CTMSSite:
    svc = get_ctms_service()
    updated = svc.update_site(site_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")
    return updated


@router.delete(
    "/sites/{site_id}",
    status_code=204,
    summary="Delete a trial site",
)
async def delete_site(site_id: str) -> None:
    svc = get_ctms_service()
    deleted = svc.delete_site(site_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")


@router.get(
    "/sites/{site_id}/enrollment",
    response_model=dict[str, Any],
    summary="Get site enrollment details",
    description="Retrieve enrollment details for a specific site including patient status breakdown.",
)
async def get_site_enrollment(site_id: str) -> dict[str, Any]:
    svc = get_ctms_service()
    enrollment = svc.get_site_enrollment(site_id)
    if enrollment is None:
        raise HTTPException(status_code=404, detail=f"Site '{site_id}' not found")
    return enrollment


# ---------------------------------------------------------------------------
# Patient Management
# ---------------------------------------------------------------------------


@router.get(
    "/patients",
    response_model=PatientListResponse,
    summary="List trial patients",
    description="Retrieve patients with optional filtering by trial, site, and status.",
)
async def list_patients(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    status: Optional[PatientStatus] = Query(None, description="Filter by patient status"),
) -> PatientListResponse:
    svc = get_ctms_service()
    items = svc.list_patients(trial_id=trial_id, site_id=site_id, status=status)
    return PatientListResponse(items=items, total=len(items))


@router.get(
    "/patients/{patient_id}",
    response_model=CTMSPatient,
    summary="Get a trial patient",
)
async def get_patient(patient_id: str) -> CTMSPatient:
    svc = get_ctms_service()
    patient = svc.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found")
    return patient


@router.post(
    "/patients",
    response_model=CTMSPatient,
    status_code=201,
    summary="Screen a new patient",
)
async def create_patient(payload: PatientCreate) -> CTMSPatient:
    svc = get_ctms_service()
    return svc.create_patient(payload)


@router.put(
    "/patients/{patient_id}",
    response_model=CTMSPatient,
    summary="Update a patient",
)
async def update_patient(patient_id: str, payload: PatientUpdate) -> CTMSPatient:
    svc = get_ctms_service()
    updated = svc.update_patient(patient_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found")
    return updated


@router.delete(
    "/patients/{patient_id}",
    status_code=204,
    summary="Delete a patient record",
)
async def delete_patient(patient_id: str) -> None:
    svc = get_ctms_service()
    deleted = svc.delete_patient(patient_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found")


# ---------------------------------------------------------------------------
# Visit Management
# ---------------------------------------------------------------------------


@router.get(
    "/visits",
    response_model=VisitListResponse,
    summary="List visits",
    description="Retrieve visits with optional filtering by patient, trial, and status.",
)
async def list_visits(
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[VisitStatus] = Query(None, description="Filter by visit status"),
) -> VisitListResponse:
    svc = get_ctms_service()
    items = svc.list_visits(patient_id=patient_id, trial_id=trial_id, status=status)
    return VisitListResponse(items=items, total=len(items))


@router.get(
    "/visits/{visit_id}",
    response_model=CTMSVisit,
    summary="Get a visit",
)
async def get_visit(visit_id: str) -> CTMSVisit:
    svc = get_ctms_service()
    visit = svc.get_visit(visit_id)
    if visit is None:
        raise HTTPException(status_code=404, detail=f"Visit '{visit_id}' not found")
    return visit


@router.post(
    "/visits",
    response_model=CTMSVisit,
    status_code=201,
    summary="Schedule a visit",
)
async def create_visit(payload: VisitCreate) -> CTMSVisit:
    svc = get_ctms_service()
    return svc.create_visit(payload)


@router.put(
    "/visits/{visit_id}",
    response_model=CTMSVisit,
    summary="Update a visit",
    description="Update visit details including actual date, status, and SDV flag.",
)
async def update_visit(visit_id: str, payload: VisitUpdate) -> CTMSVisit:
    svc = get_ctms_service()
    updated = svc.update_visit(visit_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Visit '{visit_id}' not found")
    return updated


@router.delete(
    "/visits/{visit_id}",
    status_code=204,
    summary="Delete a visit",
)
async def delete_visit(visit_id: str) -> None:
    svc = get_ctms_service()
    deleted = svc.delete_visit(visit_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Visit '{visit_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=CTMSMetrics,
    summary="Get CTMS dashboard metrics",
    description="Aggregated CTMS metrics across all trials, sites, and patients.",
)
async def get_metrics() -> CTMSMetrics:
    svc = get_ctms_service()
    return svc.get_metrics()
