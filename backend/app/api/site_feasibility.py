"""Site Feasibility Management API endpoints (SITE-FEAS).

Provides comprehensive site feasibility operations: site assessments,
investigator qualification, patient pool analysis, capability evaluations,
feasibility surveys, and site feasibility operational metrics.

Endpoints:
    POST   /site-feasibility/site-assessments                              - Create site assessment
    GET    /site-feasibility/site-assessments                              - List site assessments
    GET    /site-feasibility/site-assessments/{assessment_id}              - Get single assessment
    PUT    /site-feasibility/site-assessments/{assessment_id}              - Update assessment
    DELETE /site-feasibility/site-assessments/{assessment_id}              - Delete assessment

    POST   /site-feasibility/investigator-qualifications                   - Create qualification
    GET    /site-feasibility/investigator-qualifications                   - List qualifications
    GET    /site-feasibility/investigator-qualifications/{qualification_id} - Get single qualification
    PUT    /site-feasibility/investigator-qualifications/{qualification_id} - Update qualification
    DELETE /site-feasibility/investigator-qualifications/{qualification_id} - Delete qualification

    POST   /site-feasibility/patient-pool-analyses                         - Create analysis
    GET    /site-feasibility/patient-pool-analyses                         - List analyses
    GET    /site-feasibility/patient-pool-analyses/{analysis_id}           - Get single analysis
    PUT    /site-feasibility/patient-pool-analyses/{analysis_id}           - Update analysis
    DELETE /site-feasibility/patient-pool-analyses/{analysis_id}           - Delete analysis

    POST   /site-feasibility/capability-evaluations                        - Create evaluation
    GET    /site-feasibility/capability-evaluations                        - List evaluations
    GET    /site-feasibility/capability-evaluations/{evaluation_id}        - Get single evaluation
    PUT    /site-feasibility/capability-evaluations/{evaluation_id}        - Update evaluation
    DELETE /site-feasibility/capability-evaluations/{evaluation_id}        - Delete evaluation

    POST   /site-feasibility/feasibility-surveys                           - Create survey
    GET    /site-feasibility/feasibility-surveys                           - List surveys
    GET    /site-feasibility/feasibility-surveys/{survey_id}               - Get single survey
    PUT    /site-feasibility/feasibility-surveys/{survey_id}               - Update survey
    DELETE /site-feasibility/feasibility-surveys/{survey_id}               - Delete survey

    GET    /site-feasibility/metrics                                       - Feasibility metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.site_feasibility import (
    CapabilityEvaluation,
    CapabilityEvaluationCreate,
    CapabilityEvaluationListResponse,
    CapabilityEvaluationUpdate,
    FeasibilitySurvey,
    FeasibilitySurveyCreate,
    FeasibilitySurveyListResponse,
    FeasibilitySurveyUpdate,
    InvestigatorQualification,
    InvestigatorQualificationCreate,
    InvestigatorQualificationListResponse,
    InvestigatorQualificationUpdate,
    PatientPoolAnalysis,
    PatientPoolAnalysisCreate,
    PatientPoolAnalysisListResponse,
    PatientPoolAnalysisUpdate,
    SiteAssessment,
    SiteAssessmentCreate,
    SiteAssessmentListResponse,
    SiteAssessmentUpdate,
    SiteFeasibilityMetrics,
)
from app.services.site_feasibility_service import get_site_feasibility_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/site-feasibility",
    tags=["Site Feasibility"],
)


# ---------------------------------------------------------------------------
# Site Assessments
# ---------------------------------------------------------------------------


@router.post(
    "/site-assessments",
    response_model=SiteAssessment,
    status_code=201,
    summary="Create a site assessment",
)
async def create_site_assessment(payload: SiteAssessmentCreate) -> SiteAssessment:
    svc = get_site_feasibility_service()
    return svc.create_site_assessment(payload)


@router.get(
    "/site-assessments",
    response_model=SiteAssessmentListResponse,
    summary="List site assessments",
    description="Retrieve site assessments with optional filtering by trial ID.",
)
async def list_site_assessments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> SiteAssessmentListResponse:
    svc = get_site_feasibility_service()
    items = svc.list_site_assessments(trial_id=trial_id)
    return SiteAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/site-assessments/{assessment_id}",
    response_model=SiteAssessment,
    summary="Get a site assessment",
)
async def get_site_assessment(assessment_id: str) -> SiteAssessment:
    svc = get_site_feasibility_service()
    assessment = svc.get_site_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Site assessment '{assessment_id}' not found")
    return assessment


@router.put(
    "/site-assessments/{assessment_id}",
    response_model=SiteAssessment,
    summary="Update a site assessment",
)
async def update_site_assessment(
    assessment_id: str, payload: SiteAssessmentUpdate
) -> SiteAssessment:
    svc = get_site_feasibility_service()
    updated = svc.update_site_assessment(assessment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Site assessment '{assessment_id}' not found")
    return updated


@router.delete(
    "/site-assessments/{assessment_id}",
    status_code=204,
    summary="Delete a site assessment",
)
async def delete_site_assessment(assessment_id: str) -> None:
    svc = get_site_feasibility_service()
    deleted = svc.delete_site_assessment(assessment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Site assessment '{assessment_id}' not found")


# ---------------------------------------------------------------------------
# Investigator Qualifications
# ---------------------------------------------------------------------------


@router.post(
    "/investigator-qualifications",
    response_model=InvestigatorQualification,
    status_code=201,
    summary="Create an investigator qualification",
)
async def create_investigator_qualification(
    payload: InvestigatorQualificationCreate,
) -> InvestigatorQualification:
    svc = get_site_feasibility_service()
    return svc.create_investigator_qualification(payload)


@router.get(
    "/investigator-qualifications",
    response_model=InvestigatorQualificationListResponse,
    summary="List investigator qualifications",
    description="Retrieve investigator qualifications with optional filtering by trial ID.",
)
async def list_investigator_qualifications(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> InvestigatorQualificationListResponse:
    svc = get_site_feasibility_service()
    items = svc.list_investigator_qualifications(trial_id=trial_id)
    return InvestigatorQualificationListResponse(items=items, total=len(items))


@router.get(
    "/investigator-qualifications/{qualification_id}",
    response_model=InvestigatorQualification,
    summary="Get an investigator qualification",
)
async def get_investigator_qualification(
    qualification_id: str,
) -> InvestigatorQualification:
    svc = get_site_feasibility_service()
    qualification = svc.get_investigator_qualification(qualification_id)
    if qualification is None:
        raise HTTPException(
            status_code=404,
            detail=f"Investigator qualification '{qualification_id}' not found",
        )
    return qualification


@router.put(
    "/investigator-qualifications/{qualification_id}",
    response_model=InvestigatorQualification,
    summary="Update an investigator qualification",
)
async def update_investigator_qualification(
    qualification_id: str, payload: InvestigatorQualificationUpdate
) -> InvestigatorQualification:
    svc = get_site_feasibility_service()
    updated = svc.update_investigator_qualification(qualification_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Investigator qualification '{qualification_id}' not found",
        )
    return updated


@router.delete(
    "/investigator-qualifications/{qualification_id}",
    status_code=204,
    summary="Delete an investigator qualification",
)
async def delete_investigator_qualification(qualification_id: str) -> None:
    svc = get_site_feasibility_service()
    deleted = svc.delete_investigator_qualification(qualification_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Investigator qualification '{qualification_id}' not found",
        )


# ---------------------------------------------------------------------------
# Patient Pool Analyses
# ---------------------------------------------------------------------------


@router.post(
    "/patient-pool-analyses",
    response_model=PatientPoolAnalysis,
    status_code=201,
    summary="Create a patient pool analysis",
)
async def create_patient_pool_analysis(
    payload: PatientPoolAnalysisCreate,
) -> PatientPoolAnalysis:
    svc = get_site_feasibility_service()
    return svc.create_patient_pool_analysis(payload)


@router.get(
    "/patient-pool-analyses",
    response_model=PatientPoolAnalysisListResponse,
    summary="List patient pool analyses",
    description="Retrieve patient pool analyses with optional filtering by trial ID.",
)
async def list_patient_pool_analyses(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> PatientPoolAnalysisListResponse:
    svc = get_site_feasibility_service()
    items = svc.list_patient_pool_analyses(trial_id=trial_id)
    return PatientPoolAnalysisListResponse(items=items, total=len(items))


@router.get(
    "/patient-pool-analyses/{analysis_id}",
    response_model=PatientPoolAnalysis,
    summary="Get a patient pool analysis",
)
async def get_patient_pool_analysis(analysis_id: str) -> PatientPoolAnalysis:
    svc = get_site_feasibility_service()
    analysis = svc.get_patient_pool_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail=f"Patient pool analysis '{analysis_id}' not found",
        )
    return analysis


@router.put(
    "/patient-pool-analyses/{analysis_id}",
    response_model=PatientPoolAnalysis,
    summary="Update a patient pool analysis",
)
async def update_patient_pool_analysis(
    analysis_id: str, payload: PatientPoolAnalysisUpdate
) -> PatientPoolAnalysis:
    svc = get_site_feasibility_service()
    updated = svc.update_patient_pool_analysis(analysis_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Patient pool analysis '{analysis_id}' not found",
        )
    return updated


@router.delete(
    "/patient-pool-analyses/{analysis_id}",
    status_code=204,
    summary="Delete a patient pool analysis",
)
async def delete_patient_pool_analysis(analysis_id: str) -> None:
    svc = get_site_feasibility_service()
    deleted = svc.delete_patient_pool_analysis(analysis_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Patient pool analysis '{analysis_id}' not found",
        )


# ---------------------------------------------------------------------------
# Capability Evaluations
# ---------------------------------------------------------------------------


@router.post(
    "/capability-evaluations",
    response_model=CapabilityEvaluation,
    status_code=201,
    summary="Create a capability evaluation",
)
async def create_capability_evaluation(
    payload: CapabilityEvaluationCreate,
) -> CapabilityEvaluation:
    svc = get_site_feasibility_service()
    return svc.create_capability_evaluation(payload)


@router.get(
    "/capability-evaluations",
    response_model=CapabilityEvaluationListResponse,
    summary="List capability evaluations",
    description="Retrieve capability evaluations with optional filtering by trial ID.",
)
async def list_capability_evaluations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> CapabilityEvaluationListResponse:
    svc = get_site_feasibility_service()
    items = svc.list_capability_evaluations(trial_id=trial_id)
    return CapabilityEvaluationListResponse(items=items, total=len(items))


@router.get(
    "/capability-evaluations/{evaluation_id}",
    response_model=CapabilityEvaluation,
    summary="Get a capability evaluation",
)
async def get_capability_evaluation(evaluation_id: str) -> CapabilityEvaluation:
    svc = get_site_feasibility_service()
    evaluation = svc.get_capability_evaluation(evaluation_id)
    if evaluation is None:
        raise HTTPException(
            status_code=404,
            detail=f"Capability evaluation '{evaluation_id}' not found",
        )
    return evaluation


@router.put(
    "/capability-evaluations/{evaluation_id}",
    response_model=CapabilityEvaluation,
    summary="Update a capability evaluation",
)
async def update_capability_evaluation(
    evaluation_id: str, payload: CapabilityEvaluationUpdate
) -> CapabilityEvaluation:
    svc = get_site_feasibility_service()
    updated = svc.update_capability_evaluation(evaluation_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Capability evaluation '{evaluation_id}' not found",
        )
    return updated


@router.delete(
    "/capability-evaluations/{evaluation_id}",
    status_code=204,
    summary="Delete a capability evaluation",
)
async def delete_capability_evaluation(evaluation_id: str) -> None:
    svc = get_site_feasibility_service()
    deleted = svc.delete_capability_evaluation(evaluation_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Capability evaluation '{evaluation_id}' not found",
        )


# ---------------------------------------------------------------------------
# Feasibility Surveys
# ---------------------------------------------------------------------------


@router.post(
    "/feasibility-surveys",
    response_model=FeasibilitySurvey,
    status_code=201,
    summary="Create a feasibility survey",
)
async def create_feasibility_survey(
    payload: FeasibilitySurveyCreate,
) -> FeasibilitySurvey:
    svc = get_site_feasibility_service()
    return svc.create_feasibility_survey(payload)


@router.get(
    "/feasibility-surveys",
    response_model=FeasibilitySurveyListResponse,
    summary="List feasibility surveys",
    description="Retrieve feasibility surveys with optional filtering by trial ID.",
)
async def list_feasibility_surveys(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> FeasibilitySurveyListResponse:
    svc = get_site_feasibility_service()
    items = svc.list_feasibility_surveys(trial_id=trial_id)
    return FeasibilitySurveyListResponse(items=items, total=len(items))


@router.get(
    "/feasibility-surveys/{survey_id}",
    response_model=FeasibilitySurvey,
    summary="Get a feasibility survey",
)
async def get_feasibility_survey(survey_id: str) -> FeasibilitySurvey:
    svc = get_site_feasibility_service()
    survey = svc.get_feasibility_survey(survey_id)
    if survey is None:
        raise HTTPException(
            status_code=404, detail=f"Feasibility survey '{survey_id}' not found"
        )
    return survey


@router.put(
    "/feasibility-surveys/{survey_id}",
    response_model=FeasibilitySurvey,
    summary="Update a feasibility survey",
)
async def update_feasibility_survey(
    survey_id: str, payload: FeasibilitySurveyUpdate
) -> FeasibilitySurvey:
    svc = get_site_feasibility_service()
    updated = svc.update_feasibility_survey(survey_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Feasibility survey '{survey_id}' not found"
        )
    return updated


@router.delete(
    "/feasibility-surveys/{survey_id}",
    status_code=204,
    summary="Delete a feasibility survey",
)
async def delete_feasibility_survey(survey_id: str) -> None:
    svc = get_site_feasibility_service()
    deleted = svc.delete_feasibility_survey(survey_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Feasibility survey '{survey_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=SiteFeasibilityMetrics,
    summary="Get site feasibility metrics",
    description="Aggregated site feasibility metrics across all assessments, investigators, "
    "patient pools, capability evaluations, and surveys.",
)
async def get_metrics() -> SiteFeasibilityMetrics:
    svc = get_site_feasibility_service()
    return svc.get_metrics()
