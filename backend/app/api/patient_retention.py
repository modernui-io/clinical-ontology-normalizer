"""Patient Retention Analytics API endpoints (CMO-12).

Provides patient retention tracking, dropout risk prediction, Kaplan-Meier
retention curves, intervention management, site retention comparisons,
cohort analysis, and comprehensive retention dashboards for clinical trials.

Endpoints:
    GET    /patient-retention/profiles                         - List all retention profiles
    POST   /patient-retention/profiles                         - Create a profile
    GET    /patient-retention/profiles/{profile_id}             - Get a profile
    PUT    /patient-retention/profiles/{profile_id}             - Update a profile
    DELETE /patient-retention/profiles/{profile_id}             - Delete a profile
    GET    /patient-retention/profiles/patient/{patient_id}     - Get profile by patient ID
    GET    /patient-retention/predictions/{patient_id}          - Predict dropout risk
    GET    /patient-retention/curves/{trial_id}                 - Retention survival curve
    GET    /patient-retention/interventions                     - List interventions
    POST   /patient-retention/interventions                     - Create intervention
    GET    /patient-retention/interventions/{intervention_id}   - Get intervention
    PUT    /patient-retention/interventions/{intervention_id}   - Update intervention
    GET    /patient-retention/sites                             - Site retention comparison
    GET    /patient-retention/metrics                           - Aggregate metrics
    GET    /patient-retention/dashboard                         - Full retention dashboard
    GET    /patient-retention/cohorts                           - Cohort analysis
    GET    /patient-retention/effectiveness                     - Intervention effectiveness
    GET    /patient-retention/cost-per-retained                 - Cost per retained patient
    POST   /patient-retention/recalculate-risks                - Recalculate all risk scores
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.patient_retention import (
    CohortAnalysis,
    DropoutPrediction,
    InterventionCreateRequest,
    InterventionEffectiveness,
    InterventionListResponse,
    InterventionType,
    InterventionUpdateRequest,
    PatientPhase,
    PatientRetentionProfile,
    ProfileCreateRequest,
    ProfileListResponse,
    ProfileUpdateRequest,
    RetentionCurve,
    RetentionDashboard,
    RetentionIntervention,
    RetentionMetricType,
    RetentionMetrics,
    RetentionRiskLevel,
    SiteRetentionComparison,
)
from app.services.patient_retention_service import get_patient_retention_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/patient-retention",
    tags=["Patient Retention"],
)


# ---------------------------------------------------------------------------
# Profile CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/profiles",
    response_model=ProfileListResponse,
    summary="List all patient retention profiles",
    description="Retrieve retention profiles with optional filtering by trial, site, phase, or risk level.",
)
async def list_profiles(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    phase: Optional[PatientPhase] = Query(None, description="Filter by patient phase"),
    risk_level: Optional[RetentionRiskLevel] = Query(None, description="Filter by risk level"),
) -> ProfileListResponse:
    """List all patient retention profiles."""
    svc = get_patient_retention_service()
    items = svc.list_profiles(trial_id=trial_id, site_id=site_id, phase=phase, risk_level=risk_level)
    return ProfileListResponse(items=items, total=len(items))


@router.post(
    "/profiles",
    response_model=PatientRetentionProfile,
    summary="Create a patient retention profile",
    description="Create a new retention profile for a patient in a clinical trial.",
    status_code=201,
)
async def create_profile(request: ProfileCreateRequest) -> PatientRetentionProfile:
    """Create a new patient retention profile."""
    svc = get_patient_retention_service()
    return svc.create_profile(request)


@router.get(
    "/profiles/patient/{patient_id}",
    response_model=PatientRetentionProfile,
    summary="Get profile by patient ID",
    description="Retrieve a retention profile by patient identifier.",
)
async def get_profile_by_patient(
    patient_id: str,
    trial_id: Optional[str] = Query(None, description="Optional trial ID to narrow search"),
) -> PatientRetentionProfile:
    """Get a retention profile by patient ID."""
    svc = get_patient_retention_service()
    profile = svc.get_profile_by_patient(patient_id, trial_id=trial_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"No profile found for patient {patient_id}")
    return profile


@router.get(
    "/profiles/{profile_id}",
    response_model=PatientRetentionProfile,
    summary="Get a patient retention profile",
    description="Retrieve a specific retention profile by its identifier.",
)
async def get_profile(profile_id: str) -> PatientRetentionProfile:
    """Get a single retention profile."""
    svc = get_patient_retention_service()
    profile = svc.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    return profile


@router.put(
    "/profiles/{profile_id}",
    response_model=PatientRetentionProfile,
    summary="Update a patient retention profile",
    description="Update an existing retention profile with new visit or status data.",
)
async def update_profile(profile_id: str, request: ProfileUpdateRequest) -> PatientRetentionProfile:
    """Update a retention profile."""
    svc = get_patient_retention_service()
    profile = svc.update_profile(profile_id, request)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    return profile


@router.delete(
    "/profiles/{profile_id}",
    summary="Delete a patient retention profile",
    description="Remove a retention profile from the system.",
    status_code=204,
)
async def delete_profile(profile_id: str) -> None:
    """Delete a retention profile."""
    svc = get_patient_retention_service()
    deleted = svc.delete_profile(profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")


# ---------------------------------------------------------------------------
# Dropout prediction
# ---------------------------------------------------------------------------


@router.get(
    "/predictions/{patient_id}",
    response_model=DropoutPrediction,
    summary="Predict dropout risk for a patient",
    description="Generate a weighted dropout risk prediction with recommended interventions.",
)
async def predict_dropout(patient_id: str) -> DropoutPrediction:
    """Generate a dropout prediction for a patient."""
    svc = get_patient_retention_service()
    prediction = svc.predict_dropout(patient_id)
    if prediction is None:
        raise HTTPException(status_code=404, detail=f"No profile found for patient {patient_id}")
    return prediction


# ---------------------------------------------------------------------------
# Retention curve
# ---------------------------------------------------------------------------


@router.get(
    "/curves/{trial_id}",
    response_model=RetentionCurve,
    summary="Generate retention survival curve",
    description="Generate a Kaplan-Meier retention survival curve for a trial.",
)
async def get_retention_curve(trial_id: str) -> RetentionCurve:
    """Generate a Kaplan-Meier retention curve."""
    svc = get_patient_retention_service()
    curve = svc.generate_retention_curve(trial_id)
    if curve is None:
        raise HTTPException(status_code=404, detail=f"No profiles found for trial {trial_id}")
    return curve


# ---------------------------------------------------------------------------
# Intervention management
# ---------------------------------------------------------------------------


@router.get(
    "/interventions",
    response_model=InterventionListResponse,
    summary="List retention interventions",
    description="List all retention interventions with optional filtering.",
)
async def list_interventions(
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    intervention_type: Optional[InterventionType] = Query(None, description="Filter by intervention type"),
) -> InterventionListResponse:
    """List all interventions."""
    svc = get_patient_retention_service()
    items = svc.list_interventions(patient_id=patient_id, intervention_type=intervention_type)
    return InterventionListResponse(items=items, total=len(items))


@router.post(
    "/interventions",
    response_model=RetentionIntervention,
    summary="Create a retention intervention",
    description="Record a new retention intervention applied to a patient.",
    status_code=201,
)
async def create_intervention(request: InterventionCreateRequest) -> RetentionIntervention:
    """Create a new retention intervention."""
    svc = get_patient_retention_service()
    return svc.create_intervention(request)


@router.get(
    "/interventions/{intervention_id}",
    response_model=RetentionIntervention,
    summary="Get a retention intervention",
    description="Retrieve a specific intervention by its identifier.",
)
async def get_intervention(intervention_id: str) -> RetentionIntervention:
    """Get a single intervention."""
    svc = get_patient_retention_service()
    intv = svc.get_intervention(intervention_id)
    if intv is None:
        raise HTTPException(status_code=404, detail=f"Intervention {intervention_id} not found")
    return intv


@router.put(
    "/interventions/{intervention_id}",
    response_model=RetentionIntervention,
    summary="Update a retention intervention",
    description="Update the outcome or notes for an existing intervention.",
)
async def update_intervention(intervention_id: str, request: InterventionUpdateRequest) -> RetentionIntervention:
    """Update an intervention."""
    svc = get_patient_retention_service()
    intv = svc.update_intervention(intervention_id, request)
    if intv is None:
        raise HTTPException(status_code=404, detail=f"Intervention {intervention_id} not found")
    return intv


# ---------------------------------------------------------------------------
# Site retention comparison
# ---------------------------------------------------------------------------


@router.get(
    "/sites",
    response_model=list[SiteRetentionComparison],
    summary="Compare site retention rates",
    description="Compare retention performance across trial sites.",
)
async def get_site_comparisons(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> list[SiteRetentionComparison]:
    """Get site retention comparisons."""
    svc = get_patient_retention_service()
    return svc.get_site_comparisons(trial_id=trial_id)


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=RetentionMetrics,
    summary="Get aggregate retention metrics",
    description="Retrieve aggregate retention metrics across all trials or a specific trial.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> RetentionMetrics:
    """Get aggregate retention metrics."""
    svc = get_patient_retention_service()
    return svc.get_retention_metrics(trial_id=trial_id)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get(
    "/dashboard",
    response_model=RetentionDashboard,
    summary="Get comprehensive retention dashboard",
    description="Retrieve a full retention dashboard with metrics, distributions, curves, and comparisons.",
)
async def get_dashboard(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> RetentionDashboard:
    """Get the comprehensive retention dashboard."""
    svc = get_patient_retention_service()
    return svc.get_dashboard(trial_id=trial_id)


# ---------------------------------------------------------------------------
# Cohort analysis
# ---------------------------------------------------------------------------


@router.get(
    "/cohorts",
    response_model=list[CohortAnalysis],
    summary="Analyze retention by cohort",
    description="Perform cohort analysis grouped by trial, site, phase, or demographics.",
)
async def get_cohort_analysis(
    group_by: RetentionMetricType = Query(RetentionMetricType.BY_TRIAL, description="Grouping dimension"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> list[CohortAnalysis]:
    """Get cohort analysis."""
    svc = get_patient_retention_service()
    return svc.get_cohort_analysis(group_by=group_by, trial_id=trial_id)


# ---------------------------------------------------------------------------
# Intervention effectiveness
# ---------------------------------------------------------------------------


@router.get(
    "/effectiveness",
    response_model=list[InterventionEffectiveness],
    summary="Analyze intervention effectiveness",
    description="Analyze the effectiveness and ROI of each intervention type.",
)
async def get_effectiveness(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> list[InterventionEffectiveness]:
    """Get intervention effectiveness analysis."""
    svc = get_patient_retention_service()
    return svc.get_intervention_effectiveness(trial_id=trial_id)


# ---------------------------------------------------------------------------
# Cost per retained patient
# ---------------------------------------------------------------------------


@router.get(
    "/cost-per-retained",
    summary="Calculate cost per retained patient",
    description="Calculate cost-per-retained-patient metrics with breakdown by intervention type.",
)
async def get_cost_per_retained(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> dict:
    """Get cost per retained patient metrics."""
    svc = get_patient_retention_service()
    return svc.get_cost_per_retained(trial_id=trial_id)


# ---------------------------------------------------------------------------
# Recalculate risks
# ---------------------------------------------------------------------------


@router.post(
    "/recalculate-risks",
    summary="Recalculate all risk scores",
    description="Trigger a batch recalculation of all patient risk scores.",
)
async def recalculate_risks() -> dict:
    """Recalculate risk scores for all profiles."""
    svc = get_patient_retention_service()
    return svc.recalculate_all_risks()
