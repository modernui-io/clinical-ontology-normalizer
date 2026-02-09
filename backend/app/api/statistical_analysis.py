"""Statistical Analysis & Interim Analysis Management API endpoints (CLINICAL-25).

Provides comprehensive statistical analysis operations: SAP definitions & management,
analysis result recording with multiplicity adjustments, interim analysis with
O'Brien-Fleming alpha spending, sample size calculations, subgroup analyses with
interaction testing, multiplicity summaries, and statistical metrics dashboards.

Endpoints:
    GET    /statistical-analysis/saps                                 - List SAPs
    GET    /statistical-analysis/saps/{sap_id}                        - Get single SAP
    POST   /statistical-analysis/saps                                 - Create SAP
    PUT    /statistical-analysis/saps/{sap_id}                        - Update SAP
    DELETE /statistical-analysis/saps/{sap_id}                        - Delete SAP
    GET    /statistical-analysis/results                              - List analysis results
    GET    /statistical-analysis/results/{result_id}                  - Get single result
    POST   /statistical-analysis/results                              - Record analysis result
    DELETE /statistical-analysis/results/{result_id}                  - Delete analysis result
    GET    /statistical-analysis/interim                              - List interim analyses
    GET    /statistical-analysis/interim/{ia_id}                      - Get single interim analysis
    POST   /statistical-analysis/interim                              - Record interim analysis
    GET    /statistical-analysis/interim/alpha-spending/{trial_id}    - Alpha spending summary
    GET    /statistical-analysis/sample-size                          - List sample size calcs
    GET    /statistical-analysis/sample-size/{calc_id}                - Get sample size calc
    GET    /statistical-analysis/subgroups                            - List subgroup analyses
    GET    /statistical-analysis/subgroups/{sg_id}                    - Get single subgroup analysis
    POST   /statistical-analysis/subgroups                            - Record subgroup analysis
    GET    /statistical-analysis/multiplicity/{plan_id}               - Multiplicity summary
    GET    /statistical-analysis/metrics                              - Statistical metrics dashboard
    GET    /statistical-analysis/trials/{trial_id}/results            - Results by trial
    GET    /statistical-analysis/trials/{trial_id}/forest-plot-data   - Forest plot data for trial
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.statistical_analysis import (
    AnalysisResult,
    AnalysisResultCreate,
    AnalysisResultListResponse,
    AnalysisType,
    InterimAnalysis,
    InterimAnalysisCreate,
    InterimAnalysisListResponse,
    PopulationType,
    SAPCreate,
    SAPListResponse,
    SAPUpdate,
    SampleSizeCalc,
    SampleSizeCalcListResponse,
    StatisticalAnalysisPlan,
    StatisticalMetrics,
    SubgroupAnalysis,
    SubgroupAnalysisCreate,
    SubgroupAnalysisListResponse,
)
from app.services.statistical_analysis_service import get_stats_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/statistical-analysis",
    tags=["Statistical Analysis"],
)


# ---------------------------------------------------------------------------
# SAP Management
# ---------------------------------------------------------------------------


@router.get(
    "/saps",
    response_model=SAPListResponse,
    summary="List Statistical Analysis Plans",
    description="Retrieve SAPs with optional filtering by trial and status.",
)
async def list_saps(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[str] = Query(None, description="Filter by SAP status (draft, final, amended)"),
) -> SAPListResponse:
    svc = get_stats_service()
    items = svc.list_saps(trial_id=trial_id, status=status)
    return SAPListResponse(items=items, total=len(items))


@router.get(
    "/saps/{sap_id}",
    response_model=StatisticalAnalysisPlan,
    summary="Get a Statistical Analysis Plan",
)
async def get_sap(sap_id: str) -> StatisticalAnalysisPlan:
    svc = get_stats_service()
    sap = svc.get_sap(sap_id)
    if sap is None:
        raise HTTPException(status_code=404, detail=f"SAP '{sap_id}' not found")
    return sap


@router.post(
    "/saps",
    response_model=StatisticalAnalysisPlan,
    status_code=201,
    summary="Create a Statistical Analysis Plan",
)
async def create_sap(payload: SAPCreate) -> StatisticalAnalysisPlan:
    svc = get_stats_service()
    return svc.create_sap(payload)


@router.put(
    "/saps/{sap_id}",
    response_model=StatisticalAnalysisPlan,
    summary="Update a Statistical Analysis Plan",
)
async def update_sap(sap_id: str, payload: SAPUpdate) -> StatisticalAnalysisPlan:
    svc = get_stats_service()
    updated = svc.update_sap(sap_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"SAP '{sap_id}' not found")
    return updated


@router.delete(
    "/saps/{sap_id}",
    status_code=204,
    summary="Delete a Statistical Analysis Plan",
)
async def delete_sap(sap_id: str) -> None:
    svc = get_stats_service()
    deleted = svc.delete_sap(sap_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"SAP '{sap_id}' not found")


# ---------------------------------------------------------------------------
# Analysis Results
# ---------------------------------------------------------------------------


@router.get(
    "/results",
    response_model=AnalysisResultListResponse,
    summary="List analysis results",
    description="Retrieve analysis results with optional filtering by trial, plan, type, population, and significance.",
)
async def list_analysis_results(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    plan_id: Optional[str] = Query(None, description="Filter by SAP ID"),
    analysis_type: Optional[AnalysisType] = Query(None, description="Filter by analysis type"),
    population: Optional[PopulationType] = Query(None, description="Filter by population type"),
    significant_only: Optional[bool] = Query(None, description="Filter for statistically significant results only"),
) -> AnalysisResultListResponse:
    svc = get_stats_service()
    items = svc.list_analysis_results(
        trial_id=trial_id,
        plan_id=plan_id,
        analysis_type=analysis_type,
        population=population,
        significant_only=significant_only,
    )
    return AnalysisResultListResponse(items=items, total=len(items))


@router.get(
    "/results/{result_id}",
    response_model=AnalysisResult,
    summary="Get a single analysis result",
)
async def get_analysis_result(result_id: str) -> AnalysisResult:
    svc = get_stats_service()
    result = svc.get_analysis_result(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Analysis result '{result_id}' not found")
    return result


@router.post(
    "/results",
    response_model=AnalysisResult,
    status_code=201,
    summary="Record an analysis result",
    description="Record a new statistical analysis result. Validates that the referenced SAP exists.",
)
async def create_analysis_result(payload: AnalysisResultCreate) -> AnalysisResult:
    svc = get_stats_service()
    try:
        return svc.create_analysis_result(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete(
    "/results/{result_id}",
    status_code=204,
    summary="Delete an analysis result",
)
async def delete_analysis_result(result_id: str) -> None:
    svc = get_stats_service()
    deleted = svc.delete_analysis_result(result_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Analysis result '{result_id}' not found")


# ---------------------------------------------------------------------------
# Interim Analyses
# ---------------------------------------------------------------------------


@router.get(
    "/interim",
    response_model=InterimAnalysisListResponse,
    summary="List interim analyses",
    description="Retrieve interim analyses with optional trial filter.",
)
async def list_interim_analyses(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> InterimAnalysisListResponse:
    svc = get_stats_service()
    items = svc.list_interim_analyses(trial_id=trial_id)
    return InterimAnalysisListResponse(items=items, total=len(items))


@router.get(
    "/interim/alpha-spending/{trial_id}",
    summary="Get alpha spending summary for a trial",
    description="Get cumulative alpha spending across interim looks and remaining alpha budget.",
)
async def get_alpha_spending(trial_id: str) -> dict:
    svc = get_stats_service()
    return svc.get_alpha_spending_summary(trial_id)


@router.get(
    "/interim/{ia_id}",
    response_model=InterimAnalysis,
    summary="Get a single interim analysis",
)
async def get_interim_analysis(ia_id: str) -> InterimAnalysis:
    svc = get_stats_service()
    ia = svc.get_interim_analysis(ia_id)
    if ia is None:
        raise HTTPException(status_code=404, detail=f"Interim analysis '{ia_id}' not found")
    return ia


@router.post(
    "/interim",
    response_model=InterimAnalysis,
    status_code=201,
    summary="Record an interim analysis",
    description="Record a new interim analysis with alpha spending and DSMB recommendation.",
)
async def create_interim_analysis(payload: InterimAnalysisCreate) -> InterimAnalysis:
    svc = get_stats_service()
    return svc.create_interim_analysis(payload)


# ---------------------------------------------------------------------------
# Sample Size Calculations
# ---------------------------------------------------------------------------


@router.get(
    "/sample-size",
    response_model=SampleSizeCalcListResponse,
    summary="List sample size calculations",
    description="Retrieve sample size calculations with optional trial filter.",
)
async def list_sample_size_calcs(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> SampleSizeCalcListResponse:
    svc = get_stats_service()
    items = svc.list_sample_size_calcs(trial_id=trial_id)
    return SampleSizeCalcListResponse(items=items, total=len(items))


@router.get(
    "/sample-size/{calc_id}",
    response_model=SampleSizeCalc,
    summary="Get a sample size calculation",
)
async def get_sample_size_calc(calc_id: str) -> SampleSizeCalc:
    svc = get_stats_service()
    calc = svc.get_sample_size_calc(calc_id)
    if calc is None:
        raise HTTPException(status_code=404, detail=f"Sample size calculation '{calc_id}' not found")
    return calc


# ---------------------------------------------------------------------------
# Subgroup Analyses
# ---------------------------------------------------------------------------


@router.get(
    "/subgroups",
    response_model=SubgroupAnalysisListResponse,
    summary="List subgroup analyses",
    description="Retrieve subgroup analyses with optional filtering by result and variable.",
)
async def list_subgroup_analyses(
    result_id: Optional[str] = Query(None, description="Filter by parent analysis result ID"),
    subgroup_variable: Optional[str] = Query(None, description="Filter by subgroup variable name"),
) -> SubgroupAnalysisListResponse:
    svc = get_stats_service()
    items = svc.list_subgroup_analyses(
        result_id=result_id, subgroup_variable=subgroup_variable
    )
    return SubgroupAnalysisListResponse(items=items, total=len(items))


@router.get(
    "/subgroups/{sg_id}",
    response_model=SubgroupAnalysis,
    summary="Get a subgroup analysis",
)
async def get_subgroup_analysis(sg_id: str) -> SubgroupAnalysis:
    svc = get_stats_service()
    sg = svc.get_subgroup_analysis(sg_id)
    if sg is None:
        raise HTTPException(status_code=404, detail=f"Subgroup analysis '{sg_id}' not found")
    return sg


@router.post(
    "/subgroups",
    response_model=SubgroupAnalysis,
    status_code=201,
    summary="Record a subgroup analysis",
    description="Record a subgroup analysis result with interaction testing. Validates parent result exists.",
)
async def create_subgroup_analysis(payload: SubgroupAnalysisCreate) -> SubgroupAnalysis:
    svc = get_stats_service()
    try:
        return svc.create_subgroup_analysis(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Multiplicity & Trial-Level Summaries
# ---------------------------------------------------------------------------


@router.get(
    "/multiplicity/{plan_id}",
    summary="Get multiplicity adjustment summary",
    description="Get multiplicity correction summary for a SAP including counts of significant tests.",
)
async def get_multiplicity_summary(plan_id: str) -> dict:
    svc = get_stats_service()
    summary = svc.get_multiplicity_summary(plan_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"SAP '{plan_id}' not found")
    return summary


@router.get(
    "/trials/{trial_id}/results",
    response_model=AnalysisResultListResponse,
    summary="Get all results for a trial",
    description="Retrieve all analysis results for a specific trial.",
)
async def get_trial_results(trial_id: str) -> AnalysisResultListResponse:
    svc = get_stats_service()
    items = svc.list_analysis_results(trial_id=trial_id)
    return AnalysisResultListResponse(items=items, total=len(items))


@router.get(
    "/trials/{trial_id}/forest-plot-data",
    summary="Get forest plot data for a trial",
    description="Get analysis results formatted for forest plot visualization including "
                "subgroup analyses with interaction p-values.",
)
async def get_forest_plot_data(trial_id: str) -> dict:
    svc = get_stats_service()
    results = svc.list_analysis_results(trial_id=trial_id)

    if not results:
        return {"trial_id": trial_id, "primary": [], "subgroups": []}

    # Build forest plot data
    primary_data = []
    for r in results:
        if r.analysis_type in (AnalysisType.PRIMARY, AnalysisType.SECONDARY):
            primary_data.append({
                "result_id": r.id,
                "endpoint": r.endpoint,
                "analysis_type": r.analysis_type.value,
                "estimate": r.estimate,
                "ci_lower": r.confidence_interval_lower,
                "ci_upper": r.confidence_interval_upper,
                "p_value": r.p_value,
                "n_treatment": r.n_treatment,
                "n_control": r.n_control,
            })

    # Get subgroup data
    subgroup_data = []
    for r in results:
        sgs = svc.list_subgroup_analyses(result_id=r.id)
        for sg in sgs:
            subgroup_data.append({
                "result_id": r.id,
                "endpoint": r.endpoint,
                "subgroup_variable": sg.subgroup_variable,
                "subgroup_value": sg.subgroup_value,
                "estimate": sg.estimate,
                "ci_lower": sg.ci_lower,
                "ci_upper": sg.ci_upper,
                "p_value": sg.p_value,
                "n": sg.n,
                "interaction_p_value": sg.interaction_p_value,
            })

    return {
        "trial_id": trial_id,
        "primary": primary_data,
        "subgroups": subgroup_data,
    }


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=StatisticalMetrics,
    summary="Get statistical analysis metrics",
    description="Aggregated statistical analysis metrics across all trials and SAPs.",
)
async def get_metrics() -> StatisticalMetrics:
    svc = get_stats_service()
    return svc.get_metrics()
