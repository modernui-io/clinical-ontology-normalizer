"""Health Economics & Outcomes Research (HEOR) API endpoints.

Provides HEOR study management, cost-effectiveness results, budget impact models,
value dossier generation, payer evidence packages, and HEOR operational metrics.

Endpoints:
    GET    /heor/studies                              - List HEOR studies
    GET    /heor/studies/{study_id}                   - Get single study
    POST   /heor/studies                              - Create study
    PUT    /heor/studies/{study_id}                   - Update study
    DELETE /heor/studies/{study_id}                   - Delete study
    GET    /heor/ce-results                           - List cost-effectiveness results
    GET    /heor/ce-results/{result_id}               - Get single CE result
    POST   /heor/ce-results                           - Create CE result
    PUT    /heor/ce-results/{result_id}               - Update CE result
    DELETE /heor/ce-results/{result_id}               - Delete CE result
    GET    /heor/budget-models                        - List budget impact models
    GET    /heor/budget-models/{model_id}             - Get single budget model
    POST   /heor/budget-models                        - Create budget model
    PUT    /heor/budget-models/{model_id}             - Update budget model
    DELETE /heor/budget-models/{model_id}             - Delete budget model
    GET    /heor/dossiers                             - List value dossiers
    GET    /heor/dossiers/{dossier_id}                - Get single dossier
    POST   /heor/dossiers                             - Create dossier
    PUT    /heor/dossiers/{dossier_id}                - Update dossier
    DELETE /heor/dossiers/{dossier_id}                - Delete dossier
    GET    /heor/payer-evidence                       - List payer evidence
    GET    /heor/payer-evidence/{evidence_id}         - Get single payer evidence
    POST   /heor/payer-evidence                       - Create payer evidence
    PUT    /heor/payer-evidence/{evidence_id}         - Update payer evidence
    DELETE /heor/payer-evidence/{evidence_id}         - Delete payer evidence
    GET    /heor/metrics                              - HEOR metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.heor import (
    AnalysisType,
    BudgetImpactModel,
    BudgetImpactModelCreate,
    BudgetImpactModelListResponse,
    BudgetImpactModelUpdate,
    CostEffectivenessResult,
    CostEffectivenessResultCreate,
    CostEffectivenessResultListResponse,
    CostEffectivenessResultUpdate,
    DossierStatus,
    EvidenceGrade,
    HEORMetrics,
    HEORStudy,
    HEORStudyCreate,
    HEORStudyListResponse,
    HEORStudyUpdate,
    ModelType,
    PayerEvidence,
    PayerEvidenceCreate,
    PayerEvidenceListResponse,
    PayerEvidenceUpdate,
    PayerType,
    StudyStatus,
    ValueDossier,
    ValueDossierCreate,
    ValueDossierListResponse,
    ValueDossierUpdate,
)
from app.services.heor_service import get_heor_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/heor",
    tags=["HEOR"],
)


# ---------------------------------------------------------------------------
# Studies
# ---------------------------------------------------------------------------


@router.get(
    "/studies",
    response_model=HEORStudyListResponse,
    summary="List HEOR studies",
    description="Retrieve HEOR studies with optional filtering.",
)
async def list_studies(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    analysis_type: Optional[AnalysisType] = Query(None, description="Filter by analysis type"),
    status: Optional[StudyStatus] = Query(None, description="Filter by study status"),
    country: Optional[str] = Query(None, description="Filter by country"),
):
    svc = get_heor_service()
    items = svc.list_studies(
        trial_id=trial_id,
        analysis_type=analysis_type,
        status=status,
        country=country,
    )
    return HEORStudyListResponse(items=items, total=len(items))


@router.get(
    "/studies/{study_id}",
    response_model=HEORStudy,
    summary="Get HEOR study",
    description="Retrieve a single HEOR study by ID.",
)
async def get_study(study_id: str):
    svc = get_heor_service()
    study = svc.get_study(study_id)
    if not study:
        raise HTTPException(status_code=404, detail=f"Study {study_id} not found")
    return study


@router.post(
    "/studies",
    response_model=HEORStudy,
    status_code=201,
    summary="Create HEOR study",
    description="Create a new HEOR study.",
)
async def create_study(data: HEORStudyCreate):
    svc = get_heor_service()
    return svc.create_study(data)


@router.put(
    "/studies/{study_id}",
    response_model=HEORStudy,
    summary="Update HEOR study",
    description="Update an existing HEOR study.",
)
async def update_study(study_id: str, data: HEORStudyUpdate):
    svc = get_heor_service()
    study = svc.update_study(study_id, data)
    if not study:
        raise HTTPException(status_code=404, detail=f"Study {study_id} not found")
    return study


@router.delete(
    "/studies/{study_id}",
    status_code=204,
    summary="Delete HEOR study",
    description="Delete an HEOR study by ID.",
)
async def delete_study(study_id: str):
    svc = get_heor_service()
    if not svc.delete_study(study_id):
        raise HTTPException(status_code=404, detail=f"Study {study_id} not found")


# ---------------------------------------------------------------------------
# Cost-Effectiveness Results
# ---------------------------------------------------------------------------


@router.get(
    "/ce-results",
    response_model=CostEffectivenessResultListResponse,
    summary="List cost-effectiveness results",
    description="Retrieve cost-effectiveness results with optional filtering.",
)
async def list_ce_results(
    study_id: Optional[str] = Query(None, description="Filter by study ID"),
    model_type: Optional[ModelType] = Query(None, description="Filter by model type"),
):
    svc = get_heor_service()
    items = svc.list_ce_results(study_id=study_id, model_type=model_type)
    return CostEffectivenessResultListResponse(items=items, total=len(items))


@router.get(
    "/ce-results/{result_id}",
    response_model=CostEffectivenessResult,
    summary="Get cost-effectiveness result",
    description="Retrieve a single cost-effectiveness result by ID.",
)
async def get_ce_result(result_id: str):
    svc = get_heor_service()
    result = svc.get_ce_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"CE result {result_id} not found")
    return result


@router.post(
    "/ce-results",
    response_model=CostEffectivenessResult,
    status_code=201,
    summary="Create cost-effectiveness result",
    description="Create a new cost-effectiveness result. Auto-computes cost_effective if icer and wtp_threshold are both set.",
)
async def create_ce_result(data: CostEffectivenessResultCreate):
    svc = get_heor_service()
    return svc.create_ce_result(data)


@router.put(
    "/ce-results/{result_id}",
    response_model=CostEffectivenessResult,
    summary="Update cost-effectiveness result",
    description="Update an existing cost-effectiveness result.",
)
async def update_ce_result(result_id: str, data: CostEffectivenessResultUpdate):
    svc = get_heor_service()
    result = svc.update_ce_result(result_id, data)
    if not result:
        raise HTTPException(status_code=404, detail=f"CE result {result_id} not found")
    return result


@router.delete(
    "/ce-results/{result_id}",
    status_code=204,
    summary="Delete cost-effectiveness result",
    description="Delete a cost-effectiveness result by ID.",
)
async def delete_ce_result(result_id: str):
    svc = get_heor_service()
    if not svc.delete_ce_result(result_id):
        raise HTTPException(status_code=404, detail=f"CE result {result_id} not found")


# ---------------------------------------------------------------------------
# Budget Impact Models
# ---------------------------------------------------------------------------


@router.get(
    "/budget-models",
    response_model=BudgetImpactModelListResponse,
    summary="List budget impact models",
    description="Retrieve budget impact models with optional filtering.",
)
async def list_budget_models(
    study_id: Optional[str] = Query(None, description="Filter by study ID"),
):
    svc = get_heor_service()
    items = svc.list_budget_models(study_id=study_id)
    return BudgetImpactModelListResponse(items=items, total=len(items))


@router.get(
    "/budget-models/{model_id}",
    response_model=BudgetImpactModel,
    summary="Get budget impact model",
    description="Retrieve a single budget impact model by ID.",
)
async def get_budget_model(model_id: str):
    svc = get_heor_service()
    model = svc.get_budget_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Budget model {model_id} not found")
    return model


@router.post(
    "/budget-models",
    response_model=BudgetImpactModel,
    status_code=201,
    summary="Create budget impact model",
    description="Create a new budget impact model.",
)
async def create_budget_model(data: BudgetImpactModelCreate):
    svc = get_heor_service()
    return svc.create_budget_model(data)


@router.put(
    "/budget-models/{model_id}",
    response_model=BudgetImpactModel,
    summary="Update budget impact model",
    description="Update an existing budget impact model.",
)
async def update_budget_model(model_id: str, data: BudgetImpactModelUpdate):
    svc = get_heor_service()
    model = svc.update_budget_model(model_id, data)
    if not model:
        raise HTTPException(status_code=404, detail=f"Budget model {model_id} not found")
    return model


@router.delete(
    "/budget-models/{model_id}",
    status_code=204,
    summary="Delete budget impact model",
    description="Delete a budget impact model by ID.",
)
async def delete_budget_model(model_id: str):
    svc = get_heor_service()
    if not svc.delete_budget_model(model_id):
        raise HTTPException(status_code=404, detail=f"Budget model {model_id} not found")


# ---------------------------------------------------------------------------
# Value Dossiers
# ---------------------------------------------------------------------------


@router.get(
    "/dossiers",
    response_model=ValueDossierListResponse,
    summary="List value dossiers",
    description="Retrieve value dossiers with optional filtering.",
)
async def list_dossiers(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[DossierStatus] = Query(None, description="Filter by dossier status"),
    target_market: Optional[str] = Query(None, description="Filter by target market"),
    target_payer_type: Optional[PayerType] = Query(None, description="Filter by target payer type"),
    evidence_grade: Optional[EvidenceGrade] = Query(None, description="Filter by evidence grade"),
):
    svc = get_heor_service()
    items = svc.list_dossiers(
        trial_id=trial_id,
        status=status,
        target_market=target_market,
        target_payer_type=target_payer_type,
        evidence_grade=evidence_grade,
    )
    return ValueDossierListResponse(items=items, total=len(items))


@router.get(
    "/dossiers/{dossier_id}",
    response_model=ValueDossier,
    summary="Get value dossier",
    description="Retrieve a single value dossier by ID.",
)
async def get_dossier(dossier_id: str):
    svc = get_heor_service()
    dossier = svc.get_dossier(dossier_id)
    if not dossier:
        raise HTTPException(status_code=404, detail=f"Dossier {dossier_id} not found")
    return dossier


@router.post(
    "/dossiers",
    response_model=ValueDossier,
    status_code=201,
    summary="Create value dossier",
    description="Create a new value dossier.",
)
async def create_dossier(data: ValueDossierCreate):
    svc = get_heor_service()
    return svc.create_dossier(data)


@router.put(
    "/dossiers/{dossier_id}",
    response_model=ValueDossier,
    summary="Update value dossier",
    description="Update an existing value dossier.",
)
async def update_dossier(dossier_id: str, data: ValueDossierUpdate):
    svc = get_heor_service()
    dossier = svc.update_dossier(dossier_id, data)
    if not dossier:
        raise HTTPException(status_code=404, detail=f"Dossier {dossier_id} not found")
    return dossier


@router.delete(
    "/dossiers/{dossier_id}",
    status_code=204,
    summary="Delete value dossier",
    description="Delete a value dossier by ID.",
)
async def delete_dossier(dossier_id: str):
    svc = get_heor_service()
    if not svc.delete_dossier(dossier_id):
        raise HTTPException(status_code=404, detail=f"Dossier {dossier_id} not found")


# ---------------------------------------------------------------------------
# Payer Evidence
# ---------------------------------------------------------------------------


@router.get(
    "/payer-evidence",
    response_model=PayerEvidenceListResponse,
    summary="List payer evidence",
    description="Retrieve payer evidence records with optional filtering.",
)
async def list_payer_evidence(
    dossier_id: Optional[str] = Query(None, description="Filter by dossier ID"),
    payer_type: Optional[PayerType] = Query(None, description="Filter by payer type"),
    country: Optional[str] = Query(None, description="Filter by country"),
):
    svc = get_heor_service()
    items = svc.list_payer_evidence(
        dossier_id=dossier_id,
        payer_type=payer_type,
        country=country,
    )
    return PayerEvidenceListResponse(items=items, total=len(items))


@router.get(
    "/payer-evidence/{evidence_id}",
    response_model=PayerEvidence,
    summary="Get payer evidence",
    description="Retrieve a single payer evidence record by ID.",
)
async def get_payer_evidence(evidence_id: str):
    svc = get_heor_service()
    evidence = svc.get_payer_evidence(evidence_id)
    if not evidence:
        raise HTTPException(status_code=404, detail=f"Payer evidence {evidence_id} not found")
    return evidence


@router.post(
    "/payer-evidence",
    response_model=PayerEvidence,
    status_code=201,
    summary="Create payer evidence",
    description="Create a new payer evidence record.",
)
async def create_payer_evidence(data: PayerEvidenceCreate):
    svc = get_heor_service()
    return svc.create_payer_evidence(data)


@router.put(
    "/payer-evidence/{evidence_id}",
    response_model=PayerEvidence,
    summary="Update payer evidence",
    description="Update an existing payer evidence record.",
)
async def update_payer_evidence(evidence_id: str, data: PayerEvidenceUpdate):
    svc = get_heor_service()
    evidence = svc.update_payer_evidence(evidence_id, data)
    if not evidence:
        raise HTTPException(status_code=404, detail=f"Payer evidence {evidence_id} not found")
    return evidence


@router.delete(
    "/payer-evidence/{evidence_id}",
    status_code=204,
    summary="Delete payer evidence",
    description="Delete a payer evidence record by ID.",
)
async def delete_payer_evidence(evidence_id: str):
    svc = get_heor_service()
    if not svc.delete_payer_evidence(evidence_id):
        raise HTTPException(status_code=404, detail=f"Payer evidence {evidence_id} not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=HEORMetrics,
    summary="HEOR metrics",
    description="Retrieve aggregated Health Economics & Outcomes Research metrics.",
)
async def get_metrics():
    svc = get_heor_service()
    return svc.get_metrics()
