"""Adaptive Trial Design Management API endpoints (ADAPT-TRIAL).

Provides comprehensive adaptive trial design operations: interim analysis
tracking, adaptation decision records, sample size re-estimation, futility
assessments, treatment arm modifications, and adaptive trial metrics.

Endpoints:
    GET    /adaptive-trial/interim-analyses                         - List interim analyses
    GET    /adaptive-trial/interim-analyses/{analysis_id}           - Get single analysis
    POST   /adaptive-trial/interim-analyses                         - Create analysis
    PUT    /adaptive-trial/interim-analyses/{analysis_id}           - Update analysis
    DELETE /adaptive-trial/interim-analyses/{analysis_id}           - Delete analysis
    GET    /adaptive-trial/adaptation-decisions                     - List decisions
    GET    /adaptive-trial/adaptation-decisions/{decision_id}       - Get single decision
    POST   /adaptive-trial/adaptation-decisions                     - Create decision
    PUT    /adaptive-trial/adaptation-decisions/{decision_id}       - Update decision
    DELETE /adaptive-trial/adaptation-decisions/{decision_id}       - Delete decision
    GET    /adaptive-trial/sample-size-reestimations                - List re-estimations
    GET    /adaptive-trial/sample-size-reestimations/{id}           - Get single re-estimation
    POST   /adaptive-trial/sample-size-reestimations                - Create re-estimation
    PUT    /adaptive-trial/sample-size-reestimations/{id}           - Update re-estimation
    DELETE /adaptive-trial/sample-size-reestimations/{id}           - Delete re-estimation
    GET    /adaptive-trial/futility-assessments                     - List assessments
    GET    /adaptive-trial/futility-assessments/{id}                - Get single assessment
    POST   /adaptive-trial/futility-assessments                     - Create assessment
    PUT    /adaptive-trial/futility-assessments/{id}                - Update assessment
    DELETE /adaptive-trial/futility-assessments/{id}                - Delete assessment
    GET    /adaptive-trial/treatment-arm-modifications              - List modifications
    GET    /adaptive-trial/treatment-arm-modifications/{id}         - Get single modification
    POST   /adaptive-trial/treatment-arm-modifications              - Create modification
    PUT    /adaptive-trial/treatment-arm-modifications/{id}         - Update modification
    DELETE /adaptive-trial/treatment-arm-modifications/{id}         - Delete modification
    GET    /adaptive-trial/metrics                                  - Adaptive trial metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.adaptive_trial import (
    AdaptationDecision,
    AdaptationDecisionCreate,
    AdaptationDecisionListResponse,
    AdaptationDecisionUpdate,
    AdaptationType,
    AdaptiveTrialMetrics,
    AnalysisOutcome,
    AnalysisType,
    DecisionStatus,
    FutilityAssessment,
    FutilityAssessmentCreate,
    FutilityAssessmentListResponse,
    FutilityAssessmentUpdate,
    FutilityResult,
    InterimAnalysis,
    InterimAnalysisCreate,
    InterimAnalysisListResponse,
    InterimAnalysisUpdate,
    SampleSizeReestimation,
    SampleSizeReestimationCreate,
    SampleSizeReestimationListResponse,
    SampleSizeReestimationUpdate,
    TreatmentArmModification,
    TreatmentArmModificationCreate,
    TreatmentArmModificationListResponse,
    TreatmentArmModificationUpdate,
)
from app.services.adaptive_trial_service import get_adaptive_trial_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/adaptive-trial",
    tags=["Adaptive Trial Design"],
)


# ---------------------------------------------------------------------------
# Interim Analyses
# ---------------------------------------------------------------------------


@router.get(
    "/interim-analyses",
    response_model=InterimAnalysisListResponse,
    summary="List interim analyses",
    description="Retrieve interim analyses with optional filtering by trial, analysis type, and outcome.",
)
async def list_interim_analyses(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    analysis_type: Optional[AnalysisType] = Query(None, description="Filter by analysis type"),
    outcome: Optional[AnalysisOutcome] = Query(None, description="Filter by outcome"),
) -> InterimAnalysisListResponse:
    svc = get_adaptive_trial_service()
    items = svc.list_interim_analyses(
        trial_id=trial_id, analysis_type=analysis_type, outcome=outcome
    )
    return InterimAnalysisListResponse(items=items, total=len(items))


@router.get(
    "/interim-analyses/{analysis_id}",
    response_model=InterimAnalysis,
    summary="Get an interim analysis",
)
async def get_interim_analysis(analysis_id: str) -> InterimAnalysis:
    svc = get_adaptive_trial_service()
    analysis = svc.get_interim_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail=f"Interim analysis '{analysis_id}' not found")
    return analysis


@router.post(
    "/interim-analyses",
    response_model=InterimAnalysis,
    status_code=201,
    summary="Create an interim analysis",
)
async def create_interim_analysis(payload: InterimAnalysisCreate) -> InterimAnalysis:
    svc = get_adaptive_trial_service()
    return svc.create_interim_analysis(payload)


@router.put(
    "/interim-analyses/{analysis_id}",
    response_model=InterimAnalysis,
    summary="Update an interim analysis",
)
async def update_interim_analysis(
    analysis_id: str, payload: InterimAnalysisUpdate
) -> InterimAnalysis:
    svc = get_adaptive_trial_service()
    updated = svc.update_interim_analysis(analysis_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Interim analysis '{analysis_id}' not found")
    return updated


@router.delete(
    "/interim-analyses/{analysis_id}",
    status_code=204,
    summary="Delete an interim analysis",
)
async def delete_interim_analysis(analysis_id: str) -> None:
    svc = get_adaptive_trial_service()
    deleted = svc.delete_interim_analysis(analysis_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Interim analysis '{analysis_id}' not found")


# ---------------------------------------------------------------------------
# Adaptation Decisions
# ---------------------------------------------------------------------------


@router.get(
    "/adaptation-decisions",
    response_model=AdaptationDecisionListResponse,
    summary="List adaptation decisions",
    description="Retrieve adaptation decisions with optional filtering by trial, type, and status.",
)
async def list_adaptation_decisions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    adaptation_type: Optional[AdaptationType] = Query(None, description="Filter by adaptation type"),
    status: Optional[DecisionStatus] = Query(None, description="Filter by decision status"),
) -> AdaptationDecisionListResponse:
    svc = get_adaptive_trial_service()
    items = svc.list_adaptation_decisions(
        trial_id=trial_id, adaptation_type=adaptation_type, status=status
    )
    return AdaptationDecisionListResponse(items=items, total=len(items))


@router.get(
    "/adaptation-decisions/{decision_id}",
    response_model=AdaptationDecision,
    summary="Get an adaptation decision",
)
async def get_adaptation_decision(decision_id: str) -> AdaptationDecision:
    svc = get_adaptive_trial_service()
    decision = svc.get_adaptation_decision(decision_id)
    if decision is None:
        raise HTTPException(
            status_code=404, detail=f"Adaptation decision '{decision_id}' not found"
        )
    return decision


@router.post(
    "/adaptation-decisions",
    response_model=AdaptationDecision,
    status_code=201,
    summary="Create an adaptation decision",
)
async def create_adaptation_decision(payload: AdaptationDecisionCreate) -> AdaptationDecision:
    svc = get_adaptive_trial_service()
    return svc.create_adaptation_decision(payload)


@router.put(
    "/adaptation-decisions/{decision_id}",
    response_model=AdaptationDecision,
    summary="Update an adaptation decision",
)
async def update_adaptation_decision(
    decision_id: str, payload: AdaptationDecisionUpdate
) -> AdaptationDecision:
    svc = get_adaptive_trial_service()
    updated = svc.update_adaptation_decision(decision_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Adaptation decision '{decision_id}' not found"
        )
    return updated


@router.delete(
    "/adaptation-decisions/{decision_id}",
    status_code=204,
    summary="Delete an adaptation decision",
)
async def delete_adaptation_decision(decision_id: str) -> None:
    svc = get_adaptive_trial_service()
    deleted = svc.delete_adaptation_decision(decision_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Adaptation decision '{decision_id}' not found"
        )


# ---------------------------------------------------------------------------
# Sample Size Re-estimations
# ---------------------------------------------------------------------------


@router.get(
    "/sample-size-reestimations",
    response_model=SampleSizeReestimationListResponse,
    summary="List sample size re-estimations",
    description="Retrieve sample size re-estimations with optional filtering by trial.",
)
async def list_sample_size_reestimations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> SampleSizeReestimationListResponse:
    svc = get_adaptive_trial_service()
    items = svc.list_sample_size_reestimations(trial_id=trial_id)
    return SampleSizeReestimationListResponse(items=items, total=len(items))


@router.get(
    "/sample-size-reestimations/{reestimation_id}",
    response_model=SampleSizeReestimation,
    summary="Get a sample size re-estimation",
)
async def get_sample_size_reestimation(reestimation_id: str) -> SampleSizeReestimation:
    svc = get_adaptive_trial_service()
    ssr = svc.get_sample_size_reestimation(reestimation_id)
    if ssr is None:
        raise HTTPException(
            status_code=404,
            detail=f"Sample size re-estimation '{reestimation_id}' not found",
        )
    return ssr


@router.post(
    "/sample-size-reestimations",
    response_model=SampleSizeReestimation,
    status_code=201,
    summary="Create a sample size re-estimation",
)
async def create_sample_size_reestimation(
    payload: SampleSizeReestimationCreate,
) -> SampleSizeReestimation:
    svc = get_adaptive_trial_service()
    return svc.create_sample_size_reestimation(payload)


@router.put(
    "/sample-size-reestimations/{reestimation_id}",
    response_model=SampleSizeReestimation,
    summary="Update a sample size re-estimation",
)
async def update_sample_size_reestimation(
    reestimation_id: str, payload: SampleSizeReestimationUpdate
) -> SampleSizeReestimation:
    svc = get_adaptive_trial_service()
    updated = svc.update_sample_size_reestimation(reestimation_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Sample size re-estimation '{reestimation_id}' not found",
        )
    return updated


@router.delete(
    "/sample-size-reestimations/{reestimation_id}",
    status_code=204,
    summary="Delete a sample size re-estimation",
)
async def delete_sample_size_reestimation(reestimation_id: str) -> None:
    svc = get_adaptive_trial_service()
    deleted = svc.delete_sample_size_reestimation(reestimation_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Sample size re-estimation '{reestimation_id}' not found",
        )


# ---------------------------------------------------------------------------
# Futility Assessments
# ---------------------------------------------------------------------------


@router.get(
    "/futility-assessments",
    response_model=FutilityAssessmentListResponse,
    summary="List futility assessments",
    description="Retrieve futility assessments with optional filtering by trial and result.",
)
async def list_futility_assessments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    result: Optional[FutilityResult] = Query(None, description="Filter by futility result"),
) -> FutilityAssessmentListResponse:
    svc = get_adaptive_trial_service()
    items = svc.list_futility_assessments(trial_id=trial_id, result=result)
    return FutilityAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/futility-assessments/{assessment_id}",
    response_model=FutilityAssessment,
    summary="Get a futility assessment",
)
async def get_futility_assessment(assessment_id: str) -> FutilityAssessment:
    svc = get_adaptive_trial_service()
    fa = svc.get_futility_assessment(assessment_id)
    if fa is None:
        raise HTTPException(
            status_code=404, detail=f"Futility assessment '{assessment_id}' not found"
        )
    return fa


@router.post(
    "/futility-assessments",
    response_model=FutilityAssessment,
    status_code=201,
    summary="Create a futility assessment",
)
async def create_futility_assessment(payload: FutilityAssessmentCreate) -> FutilityAssessment:
    svc = get_adaptive_trial_service()
    return svc.create_futility_assessment(payload)


@router.put(
    "/futility-assessments/{assessment_id}",
    response_model=FutilityAssessment,
    summary="Update a futility assessment",
)
async def update_futility_assessment(
    assessment_id: str, payload: FutilityAssessmentUpdate
) -> FutilityAssessment:
    svc = get_adaptive_trial_service()
    updated = svc.update_futility_assessment(assessment_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Futility assessment '{assessment_id}' not found"
        )
    return updated


@router.delete(
    "/futility-assessments/{assessment_id}",
    status_code=204,
    summary="Delete a futility assessment",
)
async def delete_futility_assessment(assessment_id: str) -> None:
    svc = get_adaptive_trial_service()
    deleted = svc.delete_futility_assessment(assessment_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Futility assessment '{assessment_id}' not found"
        )


# ---------------------------------------------------------------------------
# Treatment Arm Modifications
# ---------------------------------------------------------------------------


@router.get(
    "/treatment-arm-modifications",
    response_model=TreatmentArmModificationListResponse,
    summary="List treatment arm modifications",
    description="Retrieve treatment arm modifications with optional filtering by trial and type.",
)
async def list_treatment_arm_modifications(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    modification_type: Optional[str] = Query(None, description="Filter by modification type"),
) -> TreatmentArmModificationListResponse:
    svc = get_adaptive_trial_service()
    items = svc.list_treatment_arm_modifications(
        trial_id=trial_id, modification_type=modification_type
    )
    return TreatmentArmModificationListResponse(items=items, total=len(items))


@router.get(
    "/treatment-arm-modifications/{modification_id}",
    response_model=TreatmentArmModification,
    summary="Get a treatment arm modification",
)
async def get_treatment_arm_modification(modification_id: str) -> TreatmentArmModification:
    svc = get_adaptive_trial_service()
    tam = svc.get_treatment_arm_modification(modification_id)
    if tam is None:
        raise HTTPException(
            status_code=404,
            detail=f"Treatment arm modification '{modification_id}' not found",
        )
    return tam


@router.post(
    "/treatment-arm-modifications",
    response_model=TreatmentArmModification,
    status_code=201,
    summary="Create a treatment arm modification",
)
async def create_treatment_arm_modification(
    payload: TreatmentArmModificationCreate,
) -> TreatmentArmModification:
    svc = get_adaptive_trial_service()
    return svc.create_treatment_arm_modification(payload)


@router.put(
    "/treatment-arm-modifications/{modification_id}",
    response_model=TreatmentArmModification,
    summary="Update a treatment arm modification",
)
async def update_treatment_arm_modification(
    modification_id: str, payload: TreatmentArmModificationUpdate
) -> TreatmentArmModification:
    svc = get_adaptive_trial_service()
    updated = svc.update_treatment_arm_modification(modification_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Treatment arm modification '{modification_id}' not found",
        )
    return updated


@router.delete(
    "/treatment-arm-modifications/{modification_id}",
    status_code=204,
    summary="Delete a treatment arm modification",
)
async def delete_treatment_arm_modification(modification_id: str) -> None:
    svc = get_adaptive_trial_service()
    deleted = svc.delete_treatment_arm_modification(modification_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Treatment arm modification '{modification_id}' not found",
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=AdaptiveTrialMetrics,
    summary="Get adaptive trial design metrics",
    description="Aggregated metrics across all adaptive trial design operations.",
)
async def get_metrics() -> AdaptiveTrialMetrics:
    svc = get_adaptive_trial_service()
    return svc.get_metrics()
