"""Patient Stratification API endpoints (STRAT-MGT).

Provides comprehensive patient stratification operations: stratification factor
management, balance assessments, covariate analysis, arm assignments,
randomization balance monitoring, and stratification metrics.

Endpoints:
    GET    /patient-stratification/factors                          - List stratification factors
    GET    /patient-stratification/factors/{factor_id}              - Get single factor
    POST   /patient-stratification/factors                          - Create factor
    PUT    /patient-stratification/factors/{factor_id}              - Update factor
    DELETE /patient-stratification/factors/{factor_id}              - Delete factor
    GET    /patient-stratification/assessments                      - List balance assessments
    GET    /patient-stratification/assessments/{assessment_id}      - Get single assessment
    POST   /patient-stratification/assessments                      - Create assessment
    PUT    /patient-stratification/assessments/{assessment_id}      - Update assessment
    DELETE /patient-stratification/assessments/{assessment_id}      - Delete assessment
    GET    /patient-stratification/covariates                       - List covariate analyses
    GET    /patient-stratification/covariates/{covariate_id}        - Get single covariate
    POST   /patient-stratification/covariates                       - Create covariate analysis
    PUT    /patient-stratification/covariates/{covariate_id}        - Update covariate analysis
    DELETE /patient-stratification/covariates/{covariate_id}        - Delete covariate analysis
    GET    /patient-stratification/assignments                      - List arm assignments
    GET    /patient-stratification/assignments/{assignment_id}      - Get single assignment
    POST   /patient-stratification/assignments                      - Create arm assignment
    PUT    /patient-stratification/assignments/{assignment_id}      - Update arm assignment
    DELETE /patient-stratification/assignments/{assignment_id}      - Delete arm assignment
    GET    /patient-stratification/balances                         - List randomization balances
    GET    /patient-stratification/balances/{balance_id}            - Get single balance
    POST   /patient-stratification/balances                         - Create balance report
    PUT    /patient-stratification/balances/{balance_id}            - Update balance report
    DELETE /patient-stratification/balances/{balance_id}            - Delete balance report
    GET    /patient-stratification/metrics                          - Stratification metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.patient_stratification import (
    ArmAssignment,
    ArmAssignmentCreate,
    ArmAssignmentListResponse,
    ArmAssignmentUpdate,
    AssignmentMethod,
    BalanceAssessment,
    BalanceAssessmentCreate,
    BalanceAssessmentListResponse,
    BalanceAssessmentUpdate,
    BalanceStatus,
    CovariateAnalysis,
    CovariateAnalysisCreate,
    CovariateAnalysisListResponse,
    CovariateAnalysisUpdate,
    CovariateStatus,
    PatientStratificationMetrics,
    RandomizationBalance,
    RandomizationBalanceCreate,
    RandomizationBalanceListResponse,
    RandomizationBalanceUpdate,
    StratFactorType,
    StratificationFactor,
    StratificationFactorCreate,
    StratificationFactorListResponse,
    StratificationFactorUpdate,
)
from app.services.patient_stratification_service import get_patient_stratification_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/patient-stratification",
    tags=["Patient Stratification"],
)


# ---------------------------------------------------------------------------
# Stratification Factors
# ---------------------------------------------------------------------------


@router.get(
    "/factors",
    response_model=StratificationFactorListResponse,
    summary="List stratification factors",
    description="Retrieve stratification factors with optional filtering by trial, type, and active status.",
)
async def list_factors(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    factor_type: Optional[StratFactorType] = Query(None, description="Filter by factor type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
) -> StratificationFactorListResponse:
    svc = get_patient_stratification_service()
    items = svc.list_stratification_factors(
        trial_id=trial_id, factor_type=factor_type, is_active=is_active
    )
    return StratificationFactorListResponse(items=items, total=len(items))


@router.get(
    "/factors/{factor_id}",
    response_model=StratificationFactor,
    summary="Get a stratification factor",
)
async def get_factor(factor_id: str) -> StratificationFactor:
    svc = get_patient_stratification_service()
    factor = svc.get_stratification_factor(factor_id)
    if factor is None:
        raise HTTPException(status_code=404, detail=f"Stratification factor '{factor_id}' not found")
    return factor


@router.post(
    "/factors",
    response_model=StratificationFactor,
    status_code=201,
    summary="Create a stratification factor",
)
async def create_factor(payload: StratificationFactorCreate) -> StratificationFactor:
    svc = get_patient_stratification_service()
    return svc.create_stratification_factor(payload)


@router.put(
    "/factors/{factor_id}",
    response_model=StratificationFactor,
    summary="Update a stratification factor",
)
async def update_factor(factor_id: str, payload: StratificationFactorUpdate) -> StratificationFactor:
    svc = get_patient_stratification_service()
    updated = svc.update_stratification_factor(factor_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Stratification factor '{factor_id}' not found")
    return updated


@router.delete(
    "/factors/{factor_id}",
    status_code=204,
    summary="Delete a stratification factor",
)
async def delete_factor(factor_id: str) -> None:
    svc = get_patient_stratification_service()
    deleted = svc.delete_stratification_factor(factor_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Stratification factor '{factor_id}' not found")


# ---------------------------------------------------------------------------
# Balance Assessments
# ---------------------------------------------------------------------------


@router.get(
    "/assessments",
    response_model=BalanceAssessmentListResponse,
    summary="List balance assessments",
    description="Retrieve balance assessments with optional filtering by trial, factor, and status.",
)
async def list_assessments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    factor_id: Optional[str] = Query(None, description="Filter by factor ID"),
    balance_status: Optional[BalanceStatus] = Query(None, description="Filter by balance status"),
) -> BalanceAssessmentListResponse:
    svc = get_patient_stratification_service()
    items = svc.list_balance_assessments(
        trial_id=trial_id, factor_id=factor_id, balance_status=balance_status
    )
    return BalanceAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/assessments/{assessment_id}",
    response_model=BalanceAssessment,
    summary="Get a balance assessment",
)
async def get_assessment(assessment_id: str) -> BalanceAssessment:
    svc = get_patient_stratification_service()
    assessment = svc.get_balance_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Balance assessment '{assessment_id}' not found")
    return assessment


@router.post(
    "/assessments",
    response_model=BalanceAssessment,
    status_code=201,
    summary="Create a balance assessment",
)
async def create_assessment(payload: BalanceAssessmentCreate) -> BalanceAssessment:
    svc = get_patient_stratification_service()
    return svc.create_balance_assessment(payload)


@router.put(
    "/assessments/{assessment_id}",
    response_model=BalanceAssessment,
    summary="Update a balance assessment",
)
async def update_assessment(
    assessment_id: str, payload: BalanceAssessmentUpdate
) -> BalanceAssessment:
    svc = get_patient_stratification_service()
    updated = svc.update_balance_assessment(assessment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Balance assessment '{assessment_id}' not found")
    return updated


@router.delete(
    "/assessments/{assessment_id}",
    status_code=204,
    summary="Delete a balance assessment",
)
async def delete_assessment(assessment_id: str) -> None:
    svc = get_patient_stratification_service()
    deleted = svc.delete_balance_assessment(assessment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Balance assessment '{assessment_id}' not found")


# ---------------------------------------------------------------------------
# Covariate Analyses
# ---------------------------------------------------------------------------


@router.get(
    "/covariates",
    response_model=CovariateAnalysisListResponse,
    summary="List covariate analyses",
    description="Retrieve covariate analyses with optional filtering by trial and status.",
)
async def list_covariates(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[CovariateStatus] = Query(None, description="Filter by status"),
) -> CovariateAnalysisListResponse:
    svc = get_patient_stratification_service()
    items = svc.list_covariate_analyses(trial_id=trial_id, status=status)
    return CovariateAnalysisListResponse(items=items, total=len(items))


@router.get(
    "/covariates/{covariate_id}",
    response_model=CovariateAnalysis,
    summary="Get a covariate analysis",
)
async def get_covariate(covariate_id: str) -> CovariateAnalysis:
    svc = get_patient_stratification_service()
    covariate = svc.get_covariate_analysis(covariate_id)
    if covariate is None:
        raise HTTPException(status_code=404, detail=f"Covariate analysis '{covariate_id}' not found")
    return covariate


@router.post(
    "/covariates",
    response_model=CovariateAnalysis,
    status_code=201,
    summary="Create a covariate analysis",
)
async def create_covariate(payload: CovariateAnalysisCreate) -> CovariateAnalysis:
    svc = get_patient_stratification_service()
    return svc.create_covariate_analysis(payload)


@router.put(
    "/covariates/{covariate_id}",
    response_model=CovariateAnalysis,
    summary="Update a covariate analysis",
)
async def update_covariate(
    covariate_id: str, payload: CovariateAnalysisUpdate
) -> CovariateAnalysis:
    svc = get_patient_stratification_service()
    updated = svc.update_covariate_analysis(covariate_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Covariate analysis '{covariate_id}' not found")
    return updated


@router.delete(
    "/covariates/{covariate_id}",
    status_code=204,
    summary="Delete a covariate analysis",
)
async def delete_covariate(covariate_id: str) -> None:
    svc = get_patient_stratification_service()
    deleted = svc.delete_covariate_analysis(covariate_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Covariate analysis '{covariate_id}' not found")


# ---------------------------------------------------------------------------
# Arm Assignments
# ---------------------------------------------------------------------------


@router.get(
    "/assignments",
    response_model=ArmAssignmentListResponse,
    summary="List arm assignments",
    description="Retrieve arm assignments with optional filtering by trial, site, arm, method, and confirmation status.",
)
async def list_assignments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    arm_name: Optional[str] = Query(None, description="Filter by arm name"),
    assignment_method: Optional[AssignmentMethod] = Query(None, description="Filter by method"),
    is_confirmed: Optional[bool] = Query(None, description="Filter by confirmation status"),
) -> ArmAssignmentListResponse:
    svc = get_patient_stratification_service()
    items = svc.list_arm_assignments(
        trial_id=trial_id,
        site_id=site_id,
        arm_name=arm_name,
        assignment_method=assignment_method,
        is_confirmed=is_confirmed,
    )
    return ArmAssignmentListResponse(items=items, total=len(items))


@router.get(
    "/assignments/{assignment_id}",
    response_model=ArmAssignment,
    summary="Get an arm assignment",
)
async def get_assignment(assignment_id: str) -> ArmAssignment:
    svc = get_patient_stratification_service()
    assignment = svc.get_arm_assignment(assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail=f"Arm assignment '{assignment_id}' not found")
    return assignment


@router.post(
    "/assignments",
    response_model=ArmAssignment,
    status_code=201,
    summary="Create an arm assignment",
)
async def create_assignment(payload: ArmAssignmentCreate) -> ArmAssignment:
    svc = get_patient_stratification_service()
    return svc.create_arm_assignment(payload)


@router.put(
    "/assignments/{assignment_id}",
    response_model=ArmAssignment,
    summary="Update an arm assignment",
)
async def update_assignment(
    assignment_id: str, payload: ArmAssignmentUpdate
) -> ArmAssignment:
    svc = get_patient_stratification_service()
    updated = svc.update_arm_assignment(assignment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Arm assignment '{assignment_id}' not found")
    return updated


@router.delete(
    "/assignments/{assignment_id}",
    status_code=204,
    summary="Delete an arm assignment",
)
async def delete_assignment(assignment_id: str) -> None:
    svc = get_patient_stratification_service()
    deleted = svc.delete_arm_assignment(assignment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Arm assignment '{assignment_id}' not found")


# ---------------------------------------------------------------------------
# Randomization Balance
# ---------------------------------------------------------------------------


@router.get(
    "/balances",
    response_model=RandomizationBalanceListResponse,
    summary="List randomization balance reports",
    description="Retrieve randomization balance reports with optional filtering by trial and status.",
)
async def list_balances(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    overall_balance_status: Optional[BalanceStatus] = Query(
        None, description="Filter by balance status"
    ),
) -> RandomizationBalanceListResponse:
    svc = get_patient_stratification_service()
    items = svc.list_randomization_balances(
        trial_id=trial_id, overall_balance_status=overall_balance_status
    )
    return RandomizationBalanceListResponse(items=items, total=len(items))


@router.get(
    "/balances/{balance_id}",
    response_model=RandomizationBalance,
    summary="Get a randomization balance report",
)
async def get_balance(balance_id: str) -> RandomizationBalance:
    svc = get_patient_stratification_service()
    balance = svc.get_randomization_balance(balance_id)
    if balance is None:
        raise HTTPException(
            status_code=404, detail=f"Randomization balance '{balance_id}' not found"
        )
    return balance


@router.post(
    "/balances",
    response_model=RandomizationBalance,
    status_code=201,
    summary="Create a randomization balance report",
)
async def create_balance(payload: RandomizationBalanceCreate) -> RandomizationBalance:
    svc = get_patient_stratification_service()
    return svc.create_randomization_balance(payload)


@router.put(
    "/balances/{balance_id}",
    response_model=RandomizationBalance,
    summary="Update a randomization balance report",
)
async def update_balance(
    balance_id: str, payload: RandomizationBalanceUpdate
) -> RandomizationBalance:
    svc = get_patient_stratification_service()
    updated = svc.update_randomization_balance(balance_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Randomization balance '{balance_id}' not found"
        )
    return updated


@router.delete(
    "/balances/{balance_id}",
    status_code=204,
    summary="Delete a randomization balance report",
)
async def delete_balance(balance_id: str) -> None:
    svc = get_patient_stratification_service()
    deleted = svc.delete_randomization_balance(balance_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Randomization balance '{balance_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=PatientStratificationMetrics,
    summary="Get patient stratification metrics",
    description="Aggregated patient stratification operational metrics.",
)
async def get_metrics() -> PatientStratificationMetrics:
    svc = get_patient_stratification_service()
    return svc.get_metrics()
