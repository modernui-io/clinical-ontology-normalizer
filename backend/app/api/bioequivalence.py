"""Bioequivalence Study Management API endpoints (BE-STUDY).

Provides comprehensive bioequivalence study operations: BE study tracking,
PK parameter analysis, formulation comparison, statistical assessments,
regulatory filing, and bioequivalence metrics.

Endpoints:
    GET    /bioequivalence/studies                                    - List BE studies
    GET    /bioequivalence/studies/{study_id}                         - Get single study
    POST   /bioequivalence/studies                                    - Create study
    PUT    /bioequivalence/studies/{study_id}                         - Update study
    DELETE /bioequivalence/studies/{study_id}                         - Delete study
    GET    /bioequivalence/pk-parameters                              - List PK parameters
    GET    /bioequivalence/pk-parameters/{pk_id}                      - Get single PK parameter
    POST   /bioequivalence/pk-parameters                              - Create PK parameter
    PUT    /bioequivalence/pk-parameters/{pk_id}                      - Update PK parameter
    DELETE /bioequivalence/pk-parameters/{pk_id}                      - Delete PK parameter
    GET    /bioequivalence/formulation-comparisons                    - List comparisons
    GET    /bioequivalence/formulation-comparisons/{comparison_id}    - Get single comparison
    POST   /bioequivalence/formulation-comparisons                    - Create comparison
    PUT    /bioequivalence/formulation-comparisons/{comparison_id}    - Update comparison
    DELETE /bioequivalence/formulation-comparisons/{comparison_id}    - Delete comparison
    GET    /bioequivalence/statistical-assessments                    - List assessments
    GET    /bioequivalence/statistical-assessments/{assessment_id}    - Get single assessment
    POST   /bioequivalence/statistical-assessments                    - Create assessment
    PUT    /bioequivalence/statistical-assessments/{assessment_id}    - Update assessment
    DELETE /bioequivalence/statistical-assessments/{assessment_id}    - Delete assessment
    GET    /bioequivalence/regulatory-filings                         - List filings
    GET    /bioequivalence/regulatory-filings/{filing_id}             - Get single filing
    POST   /bioequivalence/regulatory-filings                         - Create filing
    PUT    /bioequivalence/regulatory-filings/{filing_id}             - Update filing
    DELETE /bioequivalence/regulatory-filings/{filing_id}             - Delete filing
    GET    /bioequivalence/metrics                                    - Bioequivalence metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.bioequivalence import (
    BEResult,
    BEStudy,
    BEStudyCreate,
    BEStudyListResponse,
    BEStudyUpdate,
    BioequivalenceMetrics,
    FormulationComparison,
    FormulationComparisonCreate,
    FormulationComparisonListResponse,
    FormulationComparisonUpdate,
    PKParameter,
    PKParameterCreate,
    PKParameterListResponse,
    PKParameterName,
    PKParameterUpdate,
    RegulatoryFiling,
    RegulatoryFilingCreate,
    RegulatoryFilingListResponse,
    RegulatoryFilingUpdate,
    StatisticalAssessment,
    StatisticalAssessmentCreate,
    StatisticalAssessmentListResponse,
    StatisticalAssessmentUpdate,
    StudyDesign,
    StudyStatus,
)
from app.services.bioequivalence_service import get_bioequivalence_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/bioequivalence",
    tags=["Bioequivalence"],
)


# ---------------------------------------------------------------------------
# BE Studies
# ---------------------------------------------------------------------------


@router.get(
    "/studies",
    response_model=BEStudyListResponse,
    summary="List BE studies",
    description="Retrieve BE studies with optional filtering by trial, status, design, and result.",
)
async def list_be_studies(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[StudyStatus] = Query(None, description="Filter by study status"),
    study_design: Optional[StudyDesign] = Query(None, description="Filter by study design"),
    overall_result: Optional[BEResult] = Query(None, description="Filter by overall result"),
) -> BEStudyListResponse:
    svc = get_bioequivalence_service()
    items = svc.list_be_studies(
        trial_id=trial_id, status=status, study_design=study_design, overall_result=overall_result
    )
    return BEStudyListResponse(items=items, total=len(items))


@router.get(
    "/studies/{study_id}",
    response_model=BEStudy,
    summary="Get a BE study",
)
async def get_be_study(study_id: str) -> BEStudy:
    svc = get_bioequivalence_service()
    study = svc.get_be_study(study_id)
    if study is None:
        raise HTTPException(status_code=404, detail=f"BE study '{study_id}' not found")
    return study


@router.post(
    "/studies",
    response_model=BEStudy,
    status_code=201,
    summary="Create a BE study",
)
async def create_be_study(payload: BEStudyCreate) -> BEStudy:
    svc = get_bioequivalence_service()
    return svc.create_be_study(payload)


@router.put(
    "/studies/{study_id}",
    response_model=BEStudy,
    summary="Update a BE study",
)
async def update_be_study(study_id: str, payload: BEStudyUpdate) -> BEStudy:
    svc = get_bioequivalence_service()
    updated = svc.update_be_study(study_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"BE study '{study_id}' not found")
    return updated


@router.delete(
    "/studies/{study_id}",
    status_code=204,
    summary="Delete a BE study",
)
async def delete_be_study(study_id: str) -> None:
    svc = get_bioequivalence_service()
    deleted = svc.delete_be_study(study_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"BE study '{study_id}' not found")


# ---------------------------------------------------------------------------
# PK Parameters
# ---------------------------------------------------------------------------


@router.get(
    "/pk-parameters",
    response_model=PKParameterListResponse,
    summary="List PK parameters",
    description="Retrieve PK parameters with optional filtering by trial, study, and parameter name.",
)
async def list_pk_parameters(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    study_id: Optional[str] = Query(None, description="Filter by study ID"),
    parameter_name: Optional[PKParameterName] = Query(None, description="Filter by parameter name"),
) -> PKParameterListResponse:
    svc = get_bioequivalence_service()
    items = svc.list_pk_parameters(
        trial_id=trial_id, study_id=study_id, parameter_name=parameter_name
    )
    return PKParameterListResponse(items=items, total=len(items))


@router.get(
    "/pk-parameters/{pk_id}",
    response_model=PKParameter,
    summary="Get a PK parameter",
)
async def get_pk_parameter(pk_id: str) -> PKParameter:
    svc = get_bioequivalence_service()
    pk = svc.get_pk_parameter(pk_id)
    if pk is None:
        raise HTTPException(status_code=404, detail=f"PK parameter '{pk_id}' not found")
    return pk


@router.post(
    "/pk-parameters",
    response_model=PKParameter,
    status_code=201,
    summary="Create a PK parameter",
)
async def create_pk_parameter(payload: PKParameterCreate) -> PKParameter:
    svc = get_bioequivalence_service()
    return svc.create_pk_parameter(payload)


@router.put(
    "/pk-parameters/{pk_id}",
    response_model=PKParameter,
    summary="Update a PK parameter",
)
async def update_pk_parameter(pk_id: str, payload: PKParameterUpdate) -> PKParameter:
    svc = get_bioequivalence_service()
    updated = svc.update_pk_parameter(pk_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"PK parameter '{pk_id}' not found")
    return updated


@router.delete(
    "/pk-parameters/{pk_id}",
    status_code=204,
    summary="Delete a PK parameter",
)
async def delete_pk_parameter(pk_id: str) -> None:
    svc = get_bioequivalence_service()
    deleted = svc.delete_pk_parameter(pk_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"PK parameter '{pk_id}' not found")


# ---------------------------------------------------------------------------
# Formulation Comparisons
# ---------------------------------------------------------------------------


@router.get(
    "/formulation-comparisons",
    response_model=FormulationComparisonListResponse,
    summary="List formulation comparisons",
    description="Retrieve formulation comparisons with optional filtering by trial, study, and result.",
)
async def list_formulation_comparisons(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    study_id: Optional[str] = Query(None, description="Filter by study ID"),
    result: Optional[BEResult] = Query(None, description="Filter by comparison result"),
) -> FormulationComparisonListResponse:
    svc = get_bioequivalence_service()
    items = svc.list_formulation_comparisons(
        trial_id=trial_id, study_id=study_id, result=result
    )
    return FormulationComparisonListResponse(items=items, total=len(items))


@router.get(
    "/formulation-comparisons/{comparison_id}",
    response_model=FormulationComparison,
    summary="Get a formulation comparison",
)
async def get_formulation_comparison(comparison_id: str) -> FormulationComparison:
    svc = get_bioequivalence_service()
    fc = svc.get_formulation_comparison(comparison_id)
    if fc is None:
        raise HTTPException(
            status_code=404, detail=f"Formulation comparison '{comparison_id}' not found"
        )
    return fc


@router.post(
    "/formulation-comparisons",
    response_model=FormulationComparison,
    status_code=201,
    summary="Create a formulation comparison",
)
async def create_formulation_comparison(
    payload: FormulationComparisonCreate,
) -> FormulationComparison:
    svc = get_bioequivalence_service()
    return svc.create_formulation_comparison(payload)


@router.put(
    "/formulation-comparisons/{comparison_id}",
    response_model=FormulationComparison,
    summary="Update a formulation comparison",
)
async def update_formulation_comparison(
    comparison_id: str, payload: FormulationComparisonUpdate
) -> FormulationComparison:
    svc = get_bioequivalence_service()
    updated = svc.update_formulation_comparison(comparison_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Formulation comparison '{comparison_id}' not found"
        )
    return updated


@router.delete(
    "/formulation-comparisons/{comparison_id}",
    status_code=204,
    summary="Delete a formulation comparison",
)
async def delete_formulation_comparison(comparison_id: str) -> None:
    svc = get_bioequivalence_service()
    deleted = svc.delete_formulation_comparison(comparison_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Formulation comparison '{comparison_id}' not found"
        )


# ---------------------------------------------------------------------------
# Statistical Assessments
# ---------------------------------------------------------------------------


@router.get(
    "/statistical-assessments",
    response_model=StatisticalAssessmentListResponse,
    summary="List statistical assessments",
    description="Retrieve statistical assessments with optional filtering by trial and study.",
)
async def list_statistical_assessments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    study_id: Optional[str] = Query(None, description="Filter by study ID"),
) -> StatisticalAssessmentListResponse:
    svc = get_bioequivalence_service()
    items = svc.list_statistical_assessments(trial_id=trial_id, study_id=study_id)
    return StatisticalAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/statistical-assessments/{assessment_id}",
    response_model=StatisticalAssessment,
    summary="Get a statistical assessment",
)
async def get_statistical_assessment(assessment_id: str) -> StatisticalAssessment:
    svc = get_bioequivalence_service()
    sa = svc.get_statistical_assessment(assessment_id)
    if sa is None:
        raise HTTPException(
            status_code=404, detail=f"Statistical assessment '{assessment_id}' not found"
        )
    return sa


@router.post(
    "/statistical-assessments",
    response_model=StatisticalAssessment,
    status_code=201,
    summary="Create a statistical assessment",
)
async def create_statistical_assessment(
    payload: StatisticalAssessmentCreate,
) -> StatisticalAssessment:
    svc = get_bioequivalence_service()
    return svc.create_statistical_assessment(payload)


@router.put(
    "/statistical-assessments/{assessment_id}",
    response_model=StatisticalAssessment,
    summary="Update a statistical assessment",
)
async def update_statistical_assessment(
    assessment_id: str, payload: StatisticalAssessmentUpdate
) -> StatisticalAssessment:
    svc = get_bioequivalence_service()
    updated = svc.update_statistical_assessment(assessment_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Statistical assessment '{assessment_id}' not found"
        )
    return updated


@router.delete(
    "/statistical-assessments/{assessment_id}",
    status_code=204,
    summary="Delete a statistical assessment",
)
async def delete_statistical_assessment(assessment_id: str) -> None:
    svc = get_bioequivalence_service()
    deleted = svc.delete_statistical_assessment(assessment_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Statistical assessment '{assessment_id}' not found"
        )


# ---------------------------------------------------------------------------
# Regulatory Filings
# ---------------------------------------------------------------------------


@router.get(
    "/regulatory-filings",
    response_model=RegulatoryFilingListResponse,
    summary="List regulatory filings",
    description="Retrieve regulatory filings with optional filtering by trial, study, and status.",
)
async def list_regulatory_filings(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    study_id: Optional[str] = Query(None, description="Filter by study ID"),
    status: Optional[str] = Query(None, description="Filter by filing status"),
) -> RegulatoryFilingListResponse:
    svc = get_bioequivalence_service()
    items = svc.list_regulatory_filings(trial_id=trial_id, study_id=study_id, status=status)
    return RegulatoryFilingListResponse(items=items, total=len(items))


@router.get(
    "/regulatory-filings/{filing_id}",
    response_model=RegulatoryFiling,
    summary="Get a regulatory filing",
)
async def get_regulatory_filing(filing_id: str) -> RegulatoryFiling:
    svc = get_bioequivalence_service()
    rf = svc.get_regulatory_filing(filing_id)
    if rf is None:
        raise HTTPException(
            status_code=404, detail=f"Regulatory filing '{filing_id}' not found"
        )
    return rf


@router.post(
    "/regulatory-filings",
    response_model=RegulatoryFiling,
    status_code=201,
    summary="Create a regulatory filing",
)
async def create_regulatory_filing(payload: RegulatoryFilingCreate) -> RegulatoryFiling:
    svc = get_bioequivalence_service()
    return svc.create_regulatory_filing(payload)


@router.put(
    "/regulatory-filings/{filing_id}",
    response_model=RegulatoryFiling,
    summary="Update a regulatory filing",
)
async def update_regulatory_filing(
    filing_id: str, payload: RegulatoryFilingUpdate
) -> RegulatoryFiling:
    svc = get_bioequivalence_service()
    updated = svc.update_regulatory_filing(filing_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Regulatory filing '{filing_id}' not found"
        )
    return updated


@router.delete(
    "/regulatory-filings/{filing_id}",
    status_code=204,
    summary="Delete a regulatory filing",
)
async def delete_regulatory_filing(filing_id: str) -> None:
    svc = get_bioequivalence_service()
    deleted = svc.delete_regulatory_filing(filing_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Regulatory filing '{filing_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=BioequivalenceMetrics,
    summary="Get bioequivalence metrics",
    description="Aggregated metrics across all bioequivalence study operations.",
)
async def get_metrics() -> BioequivalenceMetrics:
    svc = get_bioequivalence_service()
    return svc.get_metrics()
