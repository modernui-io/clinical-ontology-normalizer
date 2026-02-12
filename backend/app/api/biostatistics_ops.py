"""Biostatistics Operations (BIOSTATS-OPS) API endpoints.

Provides comprehensive biostatistics operations: interim analysis management,
adaptive design decisions, multiplicity adjustments, statistical report
generation, futility assessments, and biostatistics operational metrics.

Endpoints:
    GET    /biostatistics-ops/analyses                          - List interim analyses
    GET    /biostatistics-ops/analyses/{analysis_id}            - Get single analysis
    POST   /biostatistics-ops/analyses                          - Create analysis
    PUT    /biostatistics-ops/analyses/{analysis_id}            - Update analysis
    DELETE /biostatistics-ops/analyses/{analysis_id}            - Delete analysis
    GET    /biostatistics-ops/decisions                         - List adaptive decisions
    GET    /biostatistics-ops/decisions/{decision_id}           - Get single decision
    POST   /biostatistics-ops/decisions                         - Create decision
    DELETE /biostatistics-ops/decisions/{decision_id}           - Delete decision
    GET    /biostatistics-ops/adjustments                       - List multiplicity adjustments
    GET    /biostatistics-ops/adjustments/{adjustment_id}       - Get single adjustment
    POST   /biostatistics-ops/adjustments                       - Create adjustment
    PUT    /biostatistics-ops/adjustments/{adjustment_id}       - Update adjustment
    DELETE /biostatistics-ops/adjustments/{adjustment_id}       - Delete adjustment
    GET    /biostatistics-ops/reports                           - List statistical reports
    GET    /biostatistics-ops/reports/{report_id}               - Get single report
    POST   /biostatistics-ops/reports                           - Create report
    PUT    /biostatistics-ops/reports/{report_id}               - Update report
    DELETE /biostatistics-ops/reports/{report_id}               - Delete report
    GET    /biostatistics-ops/futility-assessments              - List futility assessments
    GET    /biostatistics-ops/futility-assessments/{id}         - Get single futility assessment
    POST   /biostatistics-ops/futility-assessments              - Create futility assessment
    DELETE /biostatistics-ops/futility-assessments/{id}         - Delete futility assessment
    GET    /biostatistics-ops/metrics                           - Biostatistics metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.biostatistics_ops import (
    AdaptiveDecision,
    AdaptiveDecisionCreate,
    AdaptiveDecisionListResponse,
    AnalysisStatus,
    AnalysisType,
    BiostatisticsMetrics,
    DecisionOutcome,
    FutilityAssessment,
    FutilityAssessmentCreate,
    FutilityAssessmentListResponse,
    InterimAnalysis,
    InterimAnalysisCreate,
    InterimAnalysisListResponse,
    InterimAnalysisUpdate,
    MultiplicityAdjustment,
    MultiplicityAdjustmentCreate,
    MultiplicityAdjustmentListResponse,
    MultiplicityAdjustmentUpdate,
    MultiplicityMethod,
    ReportType,
    StatisticalReport,
    StatisticalReportCreate,
    StatisticalReportListResponse,
    StatisticalReportUpdate,
)
from app.services.biostatistics_ops_service import get_biostatistics_ops_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/biostatistics-ops",
    tags=["Biostatistics Operations"],
)


# ---------------------------------------------------------------------------
# Interim Analysis Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/analyses",
    response_model=InterimAnalysisListResponse,
    summary="List interim analyses",
    description="Retrieve interim analyses with optional filtering by trial, type, and status.",
)
async def list_analyses(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    analysis_type: Optional[AnalysisType] = Query(None, description="Filter by analysis type"),
    status: Optional[AnalysisStatus] = Query(None, description="Filter by status"),
) -> InterimAnalysisListResponse:
    svc = get_biostatistics_ops_service()
    items = svc.list_analyses(trial_id=trial_id, analysis_type=analysis_type, status=status)
    return InterimAnalysisListResponse(items=items, total=len(items))


@router.get(
    "/analyses/{analysis_id}",
    response_model=InterimAnalysis,
    summary="Get an interim analysis",
)
async def get_analysis(analysis_id: str) -> InterimAnalysis:
    svc = get_biostatistics_ops_service()
    analysis = svc.get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' not found")
    return analysis


@router.post(
    "/analyses",
    response_model=InterimAnalysis,
    status_code=201,
    summary="Create an interim analysis",
)
async def create_analysis(payload: InterimAnalysisCreate) -> InterimAnalysis:
    svc = get_biostatistics_ops_service()
    return svc.create_analysis(payload)


@router.put(
    "/analyses/{analysis_id}",
    response_model=InterimAnalysis,
    summary="Update an interim analysis",
)
async def update_analysis(
    analysis_id: str, payload: InterimAnalysisUpdate
) -> InterimAnalysis:
    svc = get_biostatistics_ops_service()
    updated = svc.update_analysis(analysis_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' not found")
    return updated


@router.delete(
    "/analyses/{analysis_id}",
    status_code=204,
    summary="Delete an interim analysis",
)
async def delete_analysis(analysis_id: str) -> None:
    svc = get_biostatistics_ops_service()
    deleted = svc.delete_analysis(analysis_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' not found")


# ---------------------------------------------------------------------------
# Adaptive Decision Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/decisions",
    response_model=AdaptiveDecisionListResponse,
    summary="List adaptive decisions",
    description="Retrieve adaptive decisions with optional filtering by analysis and outcome.",
)
async def list_decisions(
    analysis_id: Optional[str] = Query(None, description="Filter by analysis ID"),
    outcome: Optional[DecisionOutcome] = Query(None, description="Filter by outcome"),
) -> AdaptiveDecisionListResponse:
    svc = get_biostatistics_ops_service()
    items = svc.list_decisions(analysis_id=analysis_id, outcome=outcome)
    return AdaptiveDecisionListResponse(items=items, total=len(items))


@router.get(
    "/decisions/{decision_id}",
    response_model=AdaptiveDecision,
    summary="Get an adaptive decision",
)
async def get_decision(decision_id: str) -> AdaptiveDecision:
    svc = get_biostatistics_ops_service()
    decision = svc.get_decision(decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail=f"Decision '{decision_id}' not found")
    return decision


@router.post(
    "/decisions",
    response_model=AdaptiveDecision,
    status_code=201,
    summary="Create an adaptive decision",
)
async def create_decision(payload: AdaptiveDecisionCreate) -> AdaptiveDecision:
    svc = get_biostatistics_ops_service()
    return svc.create_decision(payload)


@router.delete(
    "/decisions/{decision_id}",
    status_code=204,
    summary="Delete an adaptive decision",
)
async def delete_decision(decision_id: str) -> None:
    svc = get_biostatistics_ops_service()
    deleted = svc.delete_decision(decision_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Decision '{decision_id}' not found")


# ---------------------------------------------------------------------------
# Multiplicity Adjustment Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/adjustments",
    response_model=MultiplicityAdjustmentListResponse,
    summary="List multiplicity adjustments",
    description="Retrieve multiplicity adjustments with optional filtering by trial and method.",
)
async def list_adjustments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    method: Optional[MultiplicityMethod] = Query(None, description="Filter by multiplicity method"),
) -> MultiplicityAdjustmentListResponse:
    svc = get_biostatistics_ops_service()
    items = svc.list_adjustments(trial_id=trial_id, method=method)
    return MultiplicityAdjustmentListResponse(items=items, total=len(items))


@router.get(
    "/adjustments/{adjustment_id}",
    response_model=MultiplicityAdjustment,
    summary="Get a multiplicity adjustment",
)
async def get_adjustment(adjustment_id: str) -> MultiplicityAdjustment:
    svc = get_biostatistics_ops_service()
    adjustment = svc.get_adjustment(adjustment_id)
    if adjustment is None:
        raise HTTPException(status_code=404, detail=f"Adjustment '{adjustment_id}' not found")
    return adjustment


@router.post(
    "/adjustments",
    response_model=MultiplicityAdjustment,
    status_code=201,
    summary="Create a multiplicity adjustment",
)
async def create_adjustment(payload: MultiplicityAdjustmentCreate) -> MultiplicityAdjustment:
    svc = get_biostatistics_ops_service()
    return svc.create_adjustment(payload)


@router.put(
    "/adjustments/{adjustment_id}",
    response_model=MultiplicityAdjustment,
    summary="Update a multiplicity adjustment",
)
async def update_adjustment(
    adjustment_id: str, payload: MultiplicityAdjustmentUpdate
) -> MultiplicityAdjustment:
    svc = get_biostatistics_ops_service()
    updated = svc.update_adjustment(adjustment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Adjustment '{adjustment_id}' not found")
    return updated


@router.delete(
    "/adjustments/{adjustment_id}",
    status_code=204,
    summary="Delete a multiplicity adjustment",
)
async def delete_adjustment(adjustment_id: str) -> None:
    svc = get_biostatistics_ops_service()
    deleted = svc.delete_adjustment(adjustment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Adjustment '{adjustment_id}' not found")


# ---------------------------------------------------------------------------
# Statistical Report Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/reports",
    response_model=StatisticalReportListResponse,
    summary="List statistical reports",
    description="Retrieve statistical reports with optional filtering by trial, analysis, and type.",
)
async def list_reports(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    analysis_id: Optional[str] = Query(None, description="Filter by analysis ID"),
    report_type: Optional[ReportType] = Query(None, description="Filter by report type"),
) -> StatisticalReportListResponse:
    svc = get_biostatistics_ops_service()
    items = svc.list_reports(trial_id=trial_id, analysis_id=analysis_id, report_type=report_type)
    return StatisticalReportListResponse(items=items, total=len(items))


@router.get(
    "/reports/{report_id}",
    response_model=StatisticalReport,
    summary="Get a statistical report",
)
async def get_report(report_id: str) -> StatisticalReport:
    svc = get_biostatistics_ops_service()
    report = svc.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return report


@router.post(
    "/reports",
    response_model=StatisticalReport,
    status_code=201,
    summary="Create a statistical report",
)
async def create_report(payload: StatisticalReportCreate) -> StatisticalReport:
    svc = get_biostatistics_ops_service()
    return svc.create_report(payload)


@router.put(
    "/reports/{report_id}",
    response_model=StatisticalReport,
    summary="Update a statistical report",
)
async def update_report(
    report_id: str, payload: StatisticalReportUpdate
) -> StatisticalReport:
    svc = get_biostatistics_ops_service()
    updated = svc.update_report(report_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return updated


@router.delete(
    "/reports/{report_id}",
    status_code=204,
    summary="Delete a statistical report",
)
async def delete_report(report_id: str) -> None:
    svc = get_biostatistics_ops_service()
    deleted = svc.delete_report(report_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")


# ---------------------------------------------------------------------------
# Futility Assessment Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/futility-assessments",
    response_model=FutilityAssessmentListResponse,
    summary="List futility assessments",
    description="Retrieve futility assessments with optional filtering by analysis and futility status.",
)
async def list_futility_assessments(
    analysis_id: Optional[str] = Query(None, description="Filter by analysis ID"),
    futility_met: Optional[bool] = Query(None, description="Filter by futility met status"),
) -> FutilityAssessmentListResponse:
    svc = get_biostatistics_ops_service()
    items = svc.list_futility_assessments(analysis_id=analysis_id, futility_met=futility_met)
    return FutilityAssessmentListResponse(items=items, total=len(items))


@router.get(
    "/futility-assessments/{assessment_id}",
    response_model=FutilityAssessment,
    summary="Get a futility assessment",
)
async def get_futility_assessment(assessment_id: str) -> FutilityAssessment:
    svc = get_biostatistics_ops_service()
    assessment = svc.get_futility_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Futility assessment '{assessment_id}' not found")
    return assessment


@router.post(
    "/futility-assessments",
    response_model=FutilityAssessment,
    status_code=201,
    summary="Create a futility assessment",
)
async def create_futility_assessment(payload: FutilityAssessmentCreate) -> FutilityAssessment:
    svc = get_biostatistics_ops_service()
    return svc.create_futility_assessment(payload)


@router.delete(
    "/futility-assessments/{assessment_id}",
    status_code=204,
    summary="Delete a futility assessment",
)
async def delete_futility_assessment(assessment_id: str) -> None:
    svc = get_biostatistics_ops_service()
    deleted = svc.delete_futility_assessment(assessment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Futility assessment '{assessment_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=BiostatisticsMetrics,
    summary="Get biostatistics metrics",
    description="Aggregated biostatistics metrics including analysis counts by type/status, "
                "decision outcomes, multiplicity methods, report types, and futility statistics.",
)
async def get_metrics() -> BiostatisticsMetrics:
    svc = get_biostatistics_ops_service()
    return svc.get_metrics()
