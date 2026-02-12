"""Clinical Pharmacology Operations API endpoints (CLIN-PHARM).

Provides comprehensive clinical pharmacology operations: PK study management,
bioanalytical sample tracking, dose escalation decisions, exposure-response
analyses, drug-drug interaction assessments, and pharmacology metrics.

Endpoints:
    GET    /clinical-pharmacology/studies                      - List PK studies
    GET    /clinical-pharmacology/studies/{study_id}           - Get single study
    POST   /clinical-pharmacology/studies                      - Create study
    PUT    /clinical-pharmacology/studies/{study_id}           - Update study
    DELETE /clinical-pharmacology/studies/{study_id}           - Delete study
    GET    /clinical-pharmacology/samples                      - List PK samples
    GET    /clinical-pharmacology/samples/{sample_id}          - Get single sample
    POST   /clinical-pharmacology/samples                      - Create sample
    PUT    /clinical-pharmacology/samples/{sample_id}          - Update sample
    DELETE /clinical-pharmacology/samples/{sample_id}          - Delete sample
    GET    /clinical-pharmacology/escalations                  - List dose escalations
    GET    /clinical-pharmacology/escalations/{escalation_id}  - Get single escalation
    POST   /clinical-pharmacology/escalations                  - Create escalation
    PUT    /clinical-pharmacology/escalations/{escalation_id}  - Update escalation
    DELETE /clinical-pharmacology/escalations/{escalation_id}  - Delete escalation
    GET    /clinical-pharmacology/exposure-analyses             - List exposure-response analyses
    GET    /clinical-pharmacology/exposure-analyses/{id}        - Get single analysis
    POST   /clinical-pharmacology/exposure-analyses             - Create analysis
    PUT    /clinical-pharmacology/exposure-analyses/{id}        - Update analysis
    DELETE /clinical-pharmacology/exposure-analyses/{id}        - Delete analysis
    GET    /clinical-pharmacology/ddi-assessments               - List DDI assessments
    GET    /clinical-pharmacology/ddi-assessments/{id}          - Get single assessment
    POST   /clinical-pharmacology/ddi-assessments               - Create assessment
    PUT    /clinical-pharmacology/ddi-assessments/{id}          - Update assessment
    DELETE /clinical-pharmacology/ddi-assessments/{id}          - Delete assessment
    GET    /clinical-pharmacology/metrics                       - Clinical pharmacology metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.clinical_pharmacology import (
    AnalysisStatus,
    ClinicalPharmacologyMetrics,
    DDIAssessment,
    DDIAssessmentCreate,
    DDIAssessmentListResponse,
    DDIAssessmentUpdate,
    DDIRisk,
    DoseEscalation,
    DoseEscalationCreate,
    DoseEscalationListResponse,
    DoseEscalationUpdate,
    EscalationDecision,
    ExposureResponse,
    ExposureResponseCreate,
    ExposureResponseListResponse,
    ExposureResponseUpdate,
    PKSample,
    PKSampleCreate,
    PKSampleListResponse,
    PKSampleUpdate,
    PKStudy,
    PKStudyCreate,
    PKStudyListResponse,
    PKStudyUpdate,
    SampleMatrix,
    SampleStatus,
    StudyType,
)
from app.services.clinical_pharmacology_service import get_clinical_pharmacology_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/clinical-pharmacology",
    tags=["Clinical Pharmacology"],
)


# ---------------------------------------------------------------------------
# PK Studies
# ---------------------------------------------------------------------------


@router.get(
    "/studies",
    response_model=PKStudyListResponse,
    summary="List PK studies",
    description="Retrieve PK studies with optional filtering by trial, study type, and status.",
)
async def list_studies(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    study_type: Optional[StudyType] = Query(None, description="Filter by study type"),
    status: Optional[AnalysisStatus] = Query(None, description="Filter by status"),
) -> PKStudyListResponse:
    svc = get_clinical_pharmacology_service()
    items = svc.list_studies(trial_id=trial_id, study_type=study_type, status=status)
    return PKStudyListResponse(items=items, total=len(items))


@router.get(
    "/studies/{study_id}",
    response_model=PKStudy,
    summary="Get a PK study",
)
async def get_study(study_id: str) -> PKStudy:
    svc = get_clinical_pharmacology_service()
    study = svc.get_study(study_id)
    if study is None:
        raise HTTPException(status_code=404, detail=f"Study '{study_id}' not found")
    return study


@router.post(
    "/studies",
    response_model=PKStudy,
    status_code=201,
    summary="Create a PK study",
)
async def create_study(payload: PKStudyCreate) -> PKStudy:
    svc = get_clinical_pharmacology_service()
    return svc.create_study(payload)


@router.put(
    "/studies/{study_id}",
    response_model=PKStudy,
    summary="Update a PK study",
)
async def update_study(study_id: str, payload: PKStudyUpdate) -> PKStudy:
    svc = get_clinical_pharmacology_service()
    updated = svc.update_study(study_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Study '{study_id}' not found")
    return updated


@router.delete(
    "/studies/{study_id}",
    status_code=204,
    summary="Delete a PK study",
)
async def delete_study(study_id: str) -> None:
    svc = get_clinical_pharmacology_service()
    deleted = svc.delete_study(study_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Study '{study_id}' not found")


# ---------------------------------------------------------------------------
# PK Samples
# ---------------------------------------------------------------------------


@router.get(
    "/samples",
    response_model=PKSampleListResponse,
    summary="List PK samples",
    description="Retrieve PK samples with optional filtering by study, matrix, and sample status.",
)
async def list_samples(
    study_id: Optional[str] = Query(None, description="Filter by study ID"),
    matrix: Optional[SampleMatrix] = Query(None, description="Filter by sample matrix"),
    sample_status: Optional[SampleStatus] = Query(None, description="Filter by sample status"),
) -> PKSampleListResponse:
    svc = get_clinical_pharmacology_service()
    items = svc.list_samples(study_id=study_id, matrix=matrix, sample_status=sample_status)
    return PKSampleListResponse(items=items, total=len(items))


@router.get(
    "/samples/{sample_id}",
    response_model=PKSample,
    summary="Get a PK sample",
)
async def get_sample(sample_id: str) -> PKSample:
    svc = get_clinical_pharmacology_service()
    sample = svc.get_sample(sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail=f"Sample '{sample_id}' not found")
    return sample


@router.post(
    "/samples",
    response_model=PKSample,
    status_code=201,
    summary="Create a PK sample",
    description="Create a new PK sample. The referenced study_id must exist.",
)
async def create_sample(payload: PKSampleCreate) -> PKSample:
    svc = get_clinical_pharmacology_service()
    try:
        return svc.create_sample(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/samples/{sample_id}",
    response_model=PKSample,
    summary="Update a PK sample",
)
async def update_sample(sample_id: str, payload: PKSampleUpdate) -> PKSample:
    svc = get_clinical_pharmacology_service()
    updated = svc.update_sample(sample_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Sample '{sample_id}' not found")
    return updated


@router.delete(
    "/samples/{sample_id}",
    status_code=204,
    summary="Delete a PK sample",
)
async def delete_sample(sample_id: str) -> None:
    svc = get_clinical_pharmacology_service()
    deleted = svc.delete_sample(sample_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Sample '{sample_id}' not found")


# ---------------------------------------------------------------------------
# Dose Escalations
# ---------------------------------------------------------------------------


@router.get(
    "/escalations",
    response_model=DoseEscalationListResponse,
    summary="List dose escalations",
    description="Retrieve dose escalations with optional filtering by study and decision.",
)
async def list_escalations(
    study_id: Optional[str] = Query(None, description="Filter by study ID"),
    decision: Optional[EscalationDecision] = Query(None, description="Filter by decision"),
) -> DoseEscalationListResponse:
    svc = get_clinical_pharmacology_service()
    items = svc.list_escalations(study_id=study_id, decision=decision)
    return DoseEscalationListResponse(items=items, total=len(items))


@router.get(
    "/escalations/{escalation_id}",
    response_model=DoseEscalation,
    summary="Get a dose escalation",
)
async def get_escalation(escalation_id: str) -> DoseEscalation:
    svc = get_clinical_pharmacology_service()
    escalation = svc.get_escalation(escalation_id)
    if escalation is None:
        raise HTTPException(status_code=404, detail=f"Escalation '{escalation_id}' not found")
    return escalation


@router.post(
    "/escalations",
    response_model=DoseEscalation,
    status_code=201,
    summary="Create a dose escalation",
    description="Create a new dose escalation. The referenced study_id must exist.",
)
async def create_escalation(payload: DoseEscalationCreate) -> DoseEscalation:
    svc = get_clinical_pharmacology_service()
    try:
        return svc.create_escalation(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/escalations/{escalation_id}",
    response_model=DoseEscalation,
    summary="Update a dose escalation",
)
async def update_escalation(escalation_id: str, payload: DoseEscalationUpdate) -> DoseEscalation:
    svc = get_clinical_pharmacology_service()
    updated = svc.update_escalation(escalation_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Escalation '{escalation_id}' not found")
    return updated


@router.delete(
    "/escalations/{escalation_id}",
    status_code=204,
    summary="Delete a dose escalation",
)
async def delete_escalation(escalation_id: str) -> None:
    svc = get_clinical_pharmacology_service()
    deleted = svc.delete_escalation(escalation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Escalation '{escalation_id}' not found")


# ---------------------------------------------------------------------------
# Exposure-Response Analyses
# ---------------------------------------------------------------------------


@router.get(
    "/exposure-analyses",
    response_model=ExposureResponseListResponse,
    summary="List exposure-response analyses",
    description="Retrieve exposure-response analyses with optional filtering by study and status.",
)
async def list_exposure_analyses(
    study_id: Optional[str] = Query(None, description="Filter by study ID"),
    status: Optional[AnalysisStatus] = Query(None, description="Filter by analysis status"),
) -> ExposureResponseListResponse:
    svc = get_clinical_pharmacology_service()
    items = svc.list_exposure_analyses(study_id=study_id, status=status)
    return ExposureResponseListResponse(items=items, total=len(items))


@router.get(
    "/exposure-analyses/{analysis_id}",
    response_model=ExposureResponse,
    summary="Get an exposure-response analysis",
)
async def get_exposure_analysis(analysis_id: str) -> ExposureResponse:
    svc = get_clinical_pharmacology_service()
    analysis = svc.get_exposure_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail=f"Exposure analysis '{analysis_id}' not found")
    return analysis


@router.post(
    "/exposure-analyses",
    response_model=ExposureResponse,
    status_code=201,
    summary="Create an exposure-response analysis",
)
async def create_exposure_analysis(payload: ExposureResponseCreate) -> ExposureResponse:
    svc = get_clinical_pharmacology_service()
    return svc.create_exposure_analysis(payload)


@router.put(
    "/exposure-analyses/{analysis_id}",
    response_model=ExposureResponse,
    summary="Update an exposure-response analysis",
)
async def update_exposure_analysis(analysis_id: str, payload: ExposureResponseUpdate) -> ExposureResponse:
    svc = get_clinical_pharmacology_service()
    updated = svc.update_exposure_analysis(analysis_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Exposure analysis '{analysis_id}' not found")
    return updated


@router.delete(
    "/exposure-analyses/{analysis_id}",
    status_code=204,
    summary="Delete an exposure-response analysis",
)
async def delete_exposure_analysis(analysis_id: str) -> None:
    svc = get_clinical_pharmacology_service()
    deleted = svc.delete_exposure_analysis(analysis_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Exposure analysis '{analysis_id}' not found")


# ---------------------------------------------------------------------------
# DDI Assessments
# ---------------------------------------------------------------------------


@router.get(
    "/ddi-assessments",
    response_model=DDIAssessmentListResponse,
    summary="List DDI assessments",
    description="Retrieve DDI assessments with optional filtering by trial and risk classification.",
)
async def list_ddi_assessments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    risk_classification: Optional[DDIRisk] = Query(None, description="Filter by risk classification"),
) -> DDIAssessmentListResponse:
    svc = get_clinical_pharmacology_service()
    items = svc.list_ddi_assessments(trial_id=trial_id, risk_classification=risk_classification)
    return DDIAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/ddi-assessments/{assessment_id}",
    response_model=DDIAssessment,
    summary="Get a DDI assessment",
)
async def get_ddi_assessment(assessment_id: str) -> DDIAssessment:
    svc = get_clinical_pharmacology_service()
    assessment = svc.get_ddi_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"DDI assessment '{assessment_id}' not found")
    return assessment


@router.post(
    "/ddi-assessments",
    response_model=DDIAssessment,
    status_code=201,
    summary="Create a DDI assessment",
)
async def create_ddi_assessment(payload: DDIAssessmentCreate) -> DDIAssessment:
    svc = get_clinical_pharmacology_service()
    return svc.create_ddi_assessment(payload)


@router.put(
    "/ddi-assessments/{assessment_id}",
    response_model=DDIAssessment,
    summary="Update a DDI assessment",
)
async def update_ddi_assessment(assessment_id: str, payload: DDIAssessmentUpdate) -> DDIAssessment:
    svc = get_clinical_pharmacology_service()
    updated = svc.update_ddi_assessment(assessment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"DDI assessment '{assessment_id}' not found")
    return updated


@router.delete(
    "/ddi-assessments/{assessment_id}",
    status_code=204,
    summary="Delete a DDI assessment",
)
async def delete_ddi_assessment(assessment_id: str) -> None:
    svc = get_clinical_pharmacology_service()
    deleted = svc.delete_ddi_assessment(assessment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"DDI assessment '{assessment_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=ClinicalPharmacologyMetrics,
    summary="Get clinical pharmacology metrics",
    description="Aggregated clinical pharmacology operational metrics across all studies.",
)
async def get_metrics() -> ClinicalPharmacologyMetrics:
    svc = get_clinical_pharmacology_service()
    return svc.get_metrics()
