"""Real-World Evidence (RWE) Integration & Analysis API endpoints.

Provides comprehensive RWE operations: data source management, study lifecycle
(initiate through publication/submission), real-world outcome recording,
comparative effectiveness analyses, health economic evaluations (CEA/CUA/CBA),
regulatory submission package preparation, and RWE operational metrics.

Endpoints:
    GET    /real-world-evidence/data-sources                              - List data sources
    GET    /real-world-evidence/data-sources/{ds_id}                      - Get single data source
    POST   /real-world-evidence/data-sources                              - Create data source
    PUT    /real-world-evidence/data-sources/{ds_id}                      - Update data source
    DELETE /real-world-evidence/data-sources/{ds_id}                      - Delete data source
    GET    /real-world-evidence/studies                                    - List studies
    GET    /real-world-evidence/studies/{study_id}                         - Get single study
    POST   /real-world-evidence/studies                                    - Initiate study
    PUT    /real-world-evidence/studies/{study_id}                         - Update study
    DELETE /real-world-evidence/studies/{study_id}                         - Delete study
    GET    /real-world-evidence/outcomes                                   - List outcomes
    GET    /real-world-evidence/outcomes/{outcome_id}                      - Get single outcome
    POST   /real-world-evidence/outcomes                                   - Record outcome
    PUT    /real-world-evidence/outcomes/{outcome_id}                      - Update outcome
    DELETE /real-world-evidence/outcomes/{outcome_id}                      - Delete outcome
    GET    /real-world-evidence/comparative                                - List comparative analyses
    GET    /real-world-evidence/comparative/{ce_id}                        - Get single comparative analysis
    POST   /real-world-evidence/comparative                                - Run comparative analysis
    PUT    /real-world-evidence/comparative/{ce_id}                        - Update comparative analysis
    DELETE /real-world-evidence/comparative/{ce_id}                        - Delete comparative analysis
    GET    /real-world-evidence/health-economics                           - List health economics
    GET    /real-world-evidence/health-economics/{he_id}                   - Get single health economic analysis
    POST   /real-world-evidence/health-economics                           - Calculate health economics
    PUT    /real-world-evidence/health-economics/{he_id}                   - Update health economic analysis
    DELETE /real-world-evidence/health-economics/{he_id}                   - Delete health economic analysis
    GET    /real-world-evidence/submissions                                - List submission packages
    GET    /real-world-evidence/submissions/{sub_id}                       - Get single submission package
    POST   /real-world-evidence/submissions                                - Prepare submission package
    PUT    /real-world-evidence/submissions/{sub_id}                       - Update submission package
    DELETE /real-world-evidence/submissions/{sub_id}                       - Delete submission package
    GET    /real-world-evidence/metrics                                    - RWE dashboard metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.real_world_evidence import (
    AnalysisStatus,
    ComparativeEffectiveness,
    ComparativeEffectivenessCreate,
    ComparativeEffectivenessListResponse,
    ComparativeEffectivenessUpdate,
    DataSourceType,
    EvidenceGrade,
    HealthEconomicAnalysis,
    HealthEconomicAnalysisCreate,
    HealthEconomicAnalysisListResponse,
    HealthEconomicAnalysisUpdate,
    OutcomeType,
    RWEDataSource,
    RWEDataSourceCreate,
    RWEDataSourceListResponse,
    RWEDataSourceUpdate,
    RWEMetrics,
    RWEStudy,
    RWEStudyCreate,
    RWEStudyListResponse,
    RWEStudyUpdate,
    RWESubmissionPackage,
    RWESubmissionPackageCreate,
    RWESubmissionPackageListResponse,
    RWESubmissionPackageUpdate,
    RealWorldOutcome,
    RealWorldOutcomeCreate,
    RealWorldOutcomeListResponse,
    RealWorldOutcomeUpdate,
    StudyDesign,
)
from app.services.real_world_evidence_service import get_rwe_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/real-world-evidence",
    tags=["Real-World Evidence"],
)


# ---------------------------------------------------------------------------
# Data Source Management
# ---------------------------------------------------------------------------


@router.get(
    "/data-sources",
    response_model=RWEDataSourceListResponse,
    summary="List RWE data sources",
    description="Retrieve registered real-world data sources with optional type filtering.",
)
async def list_data_sources(
    data_source_type: Optional[DataSourceType] = Query(None, description="Filter by data source type"),
) -> RWEDataSourceListResponse:
    svc = get_rwe_service()
    items = svc.list_data_sources(data_source_type=data_source_type)
    return RWEDataSourceListResponse(items=items, total=len(items))


@router.get(
    "/data-sources/{ds_id}",
    response_model=RWEDataSource,
    summary="Get an RWE data source",
)
async def get_data_source(ds_id: str) -> RWEDataSource:
    svc = get_rwe_service()
    ds = svc.get_data_source(ds_id)
    if ds is None:
        raise HTTPException(status_code=404, detail=f"Data source '{ds_id}' not found")
    return ds


@router.post(
    "/data-sources",
    response_model=RWEDataSource,
    status_code=201,
    summary="Create an RWE data source",
)
async def create_data_source(payload: RWEDataSourceCreate) -> RWEDataSource:
    svc = get_rwe_service()
    return svc.create_data_source(payload)


@router.put(
    "/data-sources/{ds_id}",
    response_model=RWEDataSource,
    summary="Update an RWE data source",
)
async def update_data_source(ds_id: str, payload: RWEDataSourceUpdate) -> RWEDataSource:
    svc = get_rwe_service()
    updated = svc.update_data_source(ds_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Data source '{ds_id}' not found")
    return updated


@router.delete(
    "/data-sources/{ds_id}",
    status_code=204,
    summary="Delete an RWE data source",
)
async def delete_data_source(ds_id: str) -> None:
    svc = get_rwe_service()
    deleted = svc.delete_data_source(ds_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Data source '{ds_id}' not found")


# ---------------------------------------------------------------------------
# Study Management
# ---------------------------------------------------------------------------


@router.get(
    "/studies",
    response_model=RWEStudyListResponse,
    summary="List RWE studies",
    description="Retrieve RWE studies with optional filtering by trial, status, and study design.",
)
async def list_studies(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[AnalysisStatus] = Query(None, description="Filter by study status"),
    study_design: Optional[StudyDesign] = Query(None, description="Filter by study design"),
) -> RWEStudyListResponse:
    svc = get_rwe_service()
    items = svc.list_studies(trial_id=trial_id, status=status, study_design=study_design)
    return RWEStudyListResponse(items=items, total=len(items))


@router.get(
    "/studies/{study_id}",
    response_model=RWEStudy,
    summary="Get an RWE study",
)
async def get_study(study_id: str) -> RWEStudy:
    svc = get_rwe_service()
    study = svc.get_study(study_id)
    if study is None:
        raise HTTPException(status_code=404, detail=f"Study '{study_id}' not found")
    return study


@router.post(
    "/studies",
    response_model=RWEStudy,
    status_code=201,
    summary="Initiate an RWE study",
    description="Create and initiate a new real-world evidence study.",
)
async def initiate_study(payload: RWEStudyCreate) -> RWEStudy:
    svc = get_rwe_service()
    return svc.initiate_study(payload)


@router.put(
    "/studies/{study_id}",
    response_model=RWEStudy,
    summary="Update an RWE study",
)
async def update_study(study_id: str, payload: RWEStudyUpdate) -> RWEStudy:
    svc = get_rwe_service()
    updated = svc.update_study(study_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Study '{study_id}' not found")
    return updated


@router.delete(
    "/studies/{study_id}",
    status_code=204,
    summary="Delete an RWE study",
)
async def delete_study(study_id: str) -> None:
    svc = get_rwe_service()
    deleted = svc.delete_study(study_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Study '{study_id}' not found")


# ---------------------------------------------------------------------------
# Outcome Recording
# ---------------------------------------------------------------------------


@router.get(
    "/outcomes",
    response_model=RealWorldOutcomeListResponse,
    summary="List real-world outcomes",
    description="Retrieve outcomes with optional filtering by study, outcome type, and evidence grade.",
)
async def list_outcomes(
    study_id: Optional[str] = Query(None, description="Filter by study ID"),
    outcome_type: Optional[OutcomeType] = Query(None, description="Filter by outcome type"),
    evidence_grade: Optional[EvidenceGrade] = Query(None, description="Filter by evidence grade"),
) -> RealWorldOutcomeListResponse:
    svc = get_rwe_service()
    items = svc.list_outcomes(study_id=study_id, outcome_type=outcome_type, evidence_grade=evidence_grade)
    return RealWorldOutcomeListResponse(items=items, total=len(items))


@router.get(
    "/outcomes/{outcome_id}",
    response_model=RealWorldOutcome,
    summary="Get a real-world outcome",
)
async def get_outcome(outcome_id: str) -> RealWorldOutcome:
    svc = get_rwe_service()
    outcome = svc.get_outcome(outcome_id)
    if outcome is None:
        raise HTTPException(status_code=404, detail=f"Outcome '{outcome_id}' not found")
    return outcome


@router.post(
    "/outcomes",
    response_model=RealWorldOutcome,
    status_code=201,
    summary="Record a real-world outcome",
    description="Record a new outcome measurement from an RWE study.",
)
async def record_outcome(payload: RealWorldOutcomeCreate) -> RealWorldOutcome:
    svc = get_rwe_service()
    try:
        return svc.record_outcome(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/outcomes/{outcome_id}",
    response_model=RealWorldOutcome,
    summary="Update a real-world outcome",
)
async def update_outcome(outcome_id: str, payload: RealWorldOutcomeUpdate) -> RealWorldOutcome:
    svc = get_rwe_service()
    updated = svc.update_outcome(outcome_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Outcome '{outcome_id}' not found")
    return updated


@router.delete(
    "/outcomes/{outcome_id}",
    status_code=204,
    summary="Delete a real-world outcome",
)
async def delete_outcome(outcome_id: str) -> None:
    svc = get_rwe_service()
    deleted = svc.delete_outcome(outcome_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Outcome '{outcome_id}' not found")


# ---------------------------------------------------------------------------
# Comparative Effectiveness
# ---------------------------------------------------------------------------


@router.get(
    "/comparative",
    response_model=ComparativeEffectivenessListResponse,
    summary="List comparative effectiveness analyses",
    description="Retrieve comparative effectiveness analyses with optional study filter.",
)
async def list_comparative_analyses(
    study_id: Optional[str] = Query(None, description="Filter by study ID"),
) -> ComparativeEffectivenessListResponse:
    svc = get_rwe_service()
    items = svc.list_comparative_analyses(study_id=study_id)
    return ComparativeEffectivenessListResponse(items=items, total=len(items))


@router.get(
    "/comparative/{ce_id}",
    response_model=ComparativeEffectiveness,
    summary="Get a comparative effectiveness analysis",
)
async def get_comparative_analysis(ce_id: str) -> ComparativeEffectiveness:
    svc = get_rwe_service()
    ce = svc.get_comparative_analysis(ce_id)
    if ce is None:
        raise HTTPException(status_code=404, detail=f"Comparative analysis '{ce_id}' not found")
    return ce


@router.post(
    "/comparative",
    response_model=ComparativeEffectiveness,
    status_code=201,
    summary="Run a comparative effectiveness analysis",
    description="Record results from a comparative effectiveness analysis between treatment arms.",
)
async def run_comparative_analysis(payload: ComparativeEffectivenessCreate) -> ComparativeEffectiveness:
    svc = get_rwe_service()
    try:
        return svc.run_comparative_analysis(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/comparative/{ce_id}",
    response_model=ComparativeEffectiveness,
    summary="Update a comparative effectiveness analysis",
)
async def update_comparative_analysis(ce_id: str, payload: ComparativeEffectivenessUpdate) -> ComparativeEffectiveness:
    svc = get_rwe_service()
    updated = svc.update_comparative_analysis(ce_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Comparative analysis '{ce_id}' not found")
    return updated


@router.delete(
    "/comparative/{ce_id}",
    status_code=204,
    summary="Delete a comparative effectiveness analysis",
)
async def delete_comparative_analysis(ce_id: str) -> None:
    svc = get_rwe_service()
    deleted = svc.delete_comparative_analysis(ce_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Comparative analysis '{ce_id}' not found")


# ---------------------------------------------------------------------------
# Health Economics
# ---------------------------------------------------------------------------


@router.get(
    "/health-economics",
    response_model=HealthEconomicAnalysisListResponse,
    summary="List health economic analyses",
    description="Retrieve health economic analyses (CEA/CUA/CBA) with optional study filter.",
)
async def list_health_economics(
    study_id: Optional[str] = Query(None, description="Filter by study ID"),
) -> HealthEconomicAnalysisListResponse:
    svc = get_rwe_service()
    items = svc.list_health_economics(study_id=study_id)
    return HealthEconomicAnalysisListResponse(items=items, total=len(items))


@router.get(
    "/health-economics/{he_id}",
    response_model=HealthEconomicAnalysis,
    summary="Get a health economic analysis",
)
async def get_health_economic(he_id: str) -> HealthEconomicAnalysis:
    svc = get_rwe_service()
    he = svc.get_health_economic(he_id)
    if he is None:
        raise HTTPException(status_code=404, detail=f"Health economic analysis '{he_id}' not found")
    return he


@router.post(
    "/health-economics",
    response_model=HealthEconomicAnalysis,
    status_code=201,
    summary="Calculate health economics",
    description="Record results from a health economic analysis (cost-effectiveness, cost-utility, or cost-benefit).",
)
async def calculate_health_economics(payload: HealthEconomicAnalysisCreate) -> HealthEconomicAnalysis:
    svc = get_rwe_service()
    try:
        return svc.calculate_health_economics(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/health-economics/{he_id}",
    response_model=HealthEconomicAnalysis,
    summary="Update a health economic analysis",
)
async def update_health_economic(he_id: str, payload: HealthEconomicAnalysisUpdate) -> HealthEconomicAnalysis:
    svc = get_rwe_service()
    updated = svc.update_health_economic(he_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Health economic analysis '{he_id}' not found")
    return updated


@router.delete(
    "/health-economics/{he_id}",
    status_code=204,
    summary="Delete a health economic analysis",
)
async def delete_health_economic(he_id: str) -> None:
    svc = get_rwe_service()
    deleted = svc.delete_health_economic(he_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Health economic analysis '{he_id}' not found")


# ---------------------------------------------------------------------------
# Submission Packages
# ---------------------------------------------------------------------------


@router.get(
    "/submissions",
    response_model=RWESubmissionPackageListResponse,
    summary="List RWE submission packages",
    description="Retrieve regulatory submission packages with optional filtering by study, authority, and status.",
)
async def list_submission_packages(
    study_id: Optional[str] = Query(None, description="Filter by study ID"),
    regulatory_authority: Optional[str] = Query(None, description="Filter by regulatory authority"),
    status: Optional[AnalysisStatus] = Query(None, description="Filter by status"),
) -> RWESubmissionPackageListResponse:
    svc = get_rwe_service()
    items = svc.list_submission_packages(
        study_id=study_id, regulatory_authority=regulatory_authority, status=status
    )
    return RWESubmissionPackageListResponse(items=items, total=len(items))


@router.get(
    "/submissions/{sub_id}",
    response_model=RWESubmissionPackage,
    summary="Get an RWE submission package",
)
async def get_submission_package(sub_id: str) -> RWESubmissionPackage:
    svc = get_rwe_service()
    sub = svc.get_submission_package(sub_id)
    if sub is None:
        raise HTTPException(status_code=404, detail=f"Submission package '{sub_id}' not found")
    return sub


@router.post(
    "/submissions",
    response_model=RWESubmissionPackage,
    status_code=201,
    summary="Prepare an RWE submission package",
    description="Prepare a new RWE data package for regulatory submission.",
)
async def prepare_submission_package(payload: RWESubmissionPackageCreate) -> RWESubmissionPackage:
    svc = get_rwe_service()
    try:
        return svc.prepare_submission_package(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/submissions/{sub_id}",
    response_model=RWESubmissionPackage,
    summary="Update an RWE submission package",
)
async def update_submission_package(sub_id: str, payload: RWESubmissionPackageUpdate) -> RWESubmissionPackage:
    svc = get_rwe_service()
    updated = svc.update_submission_package(sub_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Submission package '{sub_id}' not found")
    return updated


@router.delete(
    "/submissions/{sub_id}",
    status_code=204,
    summary="Delete an RWE submission package",
)
async def delete_submission_package(sub_id: str) -> None:
    svc = get_rwe_service()
    deleted = svc.delete_submission_package(sub_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Submission package '{sub_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=RWEMetrics,
    summary="Get RWE dashboard metrics",
    description="Aggregated real-world evidence metrics across data sources, studies, outcomes, and submissions.",
)
async def get_metrics() -> RWEMetrics:
    svc = get_rwe_service()
    return svc.get_metrics()
