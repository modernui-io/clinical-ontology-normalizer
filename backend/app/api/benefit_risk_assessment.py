"""Benefit-Risk Assessment API endpoints (CLINICAL-8).

Provides comprehensive benefit-risk assessment operations: assessment lifecycle
(draft through finalization/supersession), benefit outcome quantification with
effect sizes and clinical significance, risk outcome characterization with
incidence rates and management strategies, multi-criteria decision analysis
frameworks (FDA BRF, EMA Effects Table, MCDA, PrOACT-URL, Incremental Net
Benefit), and aggregate benefit-risk metrics.

Endpoints:
    GET    /benefit-risk-assessment/assessments                                - List assessments
    GET    /benefit-risk-assessment/assessments/{assessment_id}                - Get single assessment
    POST   /benefit-risk-assessment/assessments                                - Create assessment
    PUT    /benefit-risk-assessment/assessments/{assessment_id}                - Update assessment
    DELETE /benefit-risk-assessment/assessments/{assessment_id}                - Delete assessment
    POST   /benefit-risk-assessment/assessments/{assessment_id}/finalize       - Finalize assessment
    POST   /benefit-risk-assessment/assessments/{assessment_id}/supersede      - Supersede assessment
    GET    /benefit-risk-assessment/assessments/{assessment_id}/benefits       - List benefits for assessment
    POST   /benefit-risk-assessment/assessments/{assessment_id}/benefits       - Create benefit for assessment
    GET    /benefit-risk-assessment/benefits/{benefit_id}                      - Get single benefit
    PUT    /benefit-risk-assessment/benefits/{benefit_id}                      - Update benefit
    DELETE /benefit-risk-assessment/benefits/{benefit_id}                      - Delete benefit
    GET    /benefit-risk-assessment/assessments/{assessment_id}/risks          - List risks for assessment
    POST   /benefit-risk-assessment/assessments/{assessment_id}/risks          - Create risk for assessment
    GET    /benefit-risk-assessment/risks/{risk_id}                            - Get single risk
    PUT    /benefit-risk-assessment/risks/{risk_id}                            - Update risk
    DELETE /benefit-risk-assessment/risks/{risk_id}                            - Delete risk
    GET    /benefit-risk-assessment/metrics                                    - Benefit-risk metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.benefit_risk_assessment import (
    AssessmentCreate,
    AssessmentFramework,
    AssessmentListResponse,
    AssessmentStatus,
    AssessmentUpdate,
    BenefitOutcome,
    BenefitOutcomeCreate,
    BenefitOutcomeListResponse,
    BenefitOutcomeUpdate,
    BenefitRiskAssessment,
    BenefitRiskMetrics,
    RiskOutcome,
    RiskOutcomeCreate,
    RiskOutcomeListResponse,
    RiskOutcomeUpdate,
)
from app.services.benefit_risk_assessment_service import (
    get_benefit_risk_assessment_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/benefit-risk-assessment",
    tags=["Benefit-Risk Assessment"],
)


# ---------------------------------------------------------------------------
# Assessment CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/assessments",
    response_model=AssessmentListResponse,
    summary="List benefit-risk assessments",
    description="Retrieve benefit-risk assessments with optional filtering by trial, status, framework, or drug name.",
)
async def list_assessments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[AssessmentStatus] = Query(None, description="Filter by status"),
    framework: Optional[AssessmentFramework] = Query(None, description="Filter by framework"),
    drug_name: Optional[str] = Query(None, description="Filter by drug name (partial match)"),
) -> AssessmentListResponse:
    svc = get_benefit_risk_assessment_service()
    items = svc.list_assessments(
        trial_id=trial_id, status=status, framework=framework, drug_name=drug_name,
    )
    return AssessmentListResponse(items=items, total=len(items))


@router.get(
    "/assessments/{assessment_id}",
    response_model=BenefitRiskAssessment,
    summary="Get a benefit-risk assessment",
)
async def get_assessment(assessment_id: str) -> BenefitRiskAssessment:
    svc = get_benefit_risk_assessment_service()
    assessment = svc.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")
    return assessment


@router.post(
    "/assessments",
    response_model=BenefitRiskAssessment,
    status_code=201,
    summary="Create a benefit-risk assessment",
)
async def create_assessment(payload: AssessmentCreate) -> BenefitRiskAssessment:
    svc = get_benefit_risk_assessment_service()
    return svc.create_assessment(payload)


@router.put(
    "/assessments/{assessment_id}",
    response_model=BenefitRiskAssessment,
    summary="Update a benefit-risk assessment",
)
async def update_assessment(
    assessment_id: str, payload: AssessmentUpdate
) -> BenefitRiskAssessment:
    svc = get_benefit_risk_assessment_service()
    try:
        updated = svc.update_assessment(assessment_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")
    return updated


@router.delete(
    "/assessments/{assessment_id}",
    status_code=204,
    summary="Delete a benefit-risk assessment",
)
async def delete_assessment(assessment_id: str) -> None:
    svc = get_benefit_risk_assessment_service()
    try:
        deleted = svc.delete_assessment(assessment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")


@router.post(
    "/assessments/{assessment_id}/finalize",
    response_model=BenefitRiskAssessment,
    summary="Finalize a benefit-risk assessment",
    description="Transition a draft or in-review assessment to finalized status.",
)
async def finalize_assessment(assessment_id: str) -> BenefitRiskAssessment:
    svc = get_benefit_risk_assessment_service()
    try:
        result = svc.finalize_assessment(assessment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")
    return result


@router.post(
    "/assessments/{assessment_id}/supersede",
    response_model=BenefitRiskAssessment,
    summary="Supersede a benefit-risk assessment",
    description="Mark a finalized assessment as superseded by a newer version.",
)
async def supersede_assessment(assessment_id: str) -> BenefitRiskAssessment:
    svc = get_benefit_risk_assessment_service()
    try:
        result = svc.supersede_assessment(assessment_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Benefit Outcomes
# ---------------------------------------------------------------------------


@router.get(
    "/assessments/{assessment_id}/benefits",
    response_model=BenefitOutcomeListResponse,
    summary="List benefit outcomes for an assessment",
)
async def list_benefits(assessment_id: str) -> BenefitOutcomeListResponse:
    svc = get_benefit_risk_assessment_service()
    assessment = svc.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")
    items = svc.list_benefits(assessment_id)
    return BenefitOutcomeListResponse(items=items, total=len(items))


@router.post(
    "/assessments/{assessment_id}/benefits",
    response_model=BenefitOutcome,
    status_code=201,
    summary="Create a benefit outcome for an assessment",
)
async def create_benefit(
    assessment_id: str, payload: BenefitOutcomeCreate
) -> BenefitOutcome:
    svc = get_benefit_risk_assessment_service()
    assessment = svc.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")
    return svc.create_benefit(assessment_id, payload)


@router.get(
    "/benefits/{benefit_id}",
    response_model=BenefitOutcome,
    summary="Get a benefit outcome",
)
async def get_benefit(benefit_id: str) -> BenefitOutcome:
    svc = get_benefit_risk_assessment_service()
    benefit = svc.get_benefit(benefit_id)
    if benefit is None:
        raise HTTPException(status_code=404, detail=f"Benefit '{benefit_id}' not found")
    return benefit


@router.put(
    "/benefits/{benefit_id}",
    response_model=BenefitOutcome,
    summary="Update a benefit outcome",
)
async def update_benefit(
    benefit_id: str, payload: BenefitOutcomeUpdate
) -> BenefitOutcome:
    svc = get_benefit_risk_assessment_service()
    updated = svc.update_benefit(benefit_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Benefit '{benefit_id}' not found")
    return updated


@router.delete(
    "/benefits/{benefit_id}",
    status_code=204,
    summary="Delete a benefit outcome",
)
async def delete_benefit(benefit_id: str) -> None:
    svc = get_benefit_risk_assessment_service()
    deleted = svc.delete_benefit(benefit_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Benefit '{benefit_id}' not found")


# ---------------------------------------------------------------------------
# Risk Outcomes
# ---------------------------------------------------------------------------


@router.get(
    "/assessments/{assessment_id}/risks",
    response_model=RiskOutcomeListResponse,
    summary="List risk outcomes for an assessment",
)
async def list_risks(assessment_id: str) -> RiskOutcomeListResponse:
    svc = get_benefit_risk_assessment_service()
    assessment = svc.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")
    items = svc.list_risks(assessment_id)
    return RiskOutcomeListResponse(items=items, total=len(items))


@router.post(
    "/assessments/{assessment_id}/risks",
    response_model=RiskOutcome,
    status_code=201,
    summary="Create a risk outcome for an assessment",
)
async def create_risk(
    assessment_id: str, payload: RiskOutcomeCreate
) -> RiskOutcome:
    svc = get_benefit_risk_assessment_service()
    assessment = svc.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")
    return svc.create_risk(assessment_id, payload)


@router.get(
    "/risks/{risk_id}",
    response_model=RiskOutcome,
    summary="Get a risk outcome",
)
async def get_risk(risk_id: str) -> RiskOutcome:
    svc = get_benefit_risk_assessment_service()
    risk = svc.get_risk(risk_id)
    if risk is None:
        raise HTTPException(status_code=404, detail=f"Risk '{risk_id}' not found")
    return risk


@router.put(
    "/risks/{risk_id}",
    response_model=RiskOutcome,
    summary="Update a risk outcome",
)
async def update_risk(
    risk_id: str, payload: RiskOutcomeUpdate
) -> RiskOutcome:
    svc = get_benefit_risk_assessment_service()
    updated = svc.update_risk(risk_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Risk '{risk_id}' not found")
    return updated


@router.delete(
    "/risks/{risk_id}",
    status_code=204,
    summary="Delete a risk outcome",
)
async def delete_risk(risk_id: str) -> None:
    svc = get_benefit_risk_assessment_service()
    deleted = svc.delete_risk(risk_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Risk '{risk_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=BenefitRiskMetrics,
    summary="Get benefit-risk assessment metrics",
    description="Aggregated metrics across benefit-risk assessments including counts by status "
                "and framework, outcome totals, and finalization statistics.",
)
async def get_metrics() -> BenefitRiskMetrics:
    svc = get_benefit_risk_assessment_service()
    return svc.get_metrics()
