"""Safety Signal Detection API endpoints (SAFETY-SIGNAL).

Provides pharmacovigilance signal detection operations: safety signal lifecycle,
signal evaluation, cumulative review tracking, disproportionality analysis,
aggregate safety reports, and signal detection operational metrics.

Endpoints:
    GET    /safety-signal-detection/signals                        - List signals
    POST   /safety-signal-detection/signals                        - Create signal
    GET    /safety-signal-detection/signals/{signal_id}            - Get signal
    PUT    /safety-signal-detection/signals/{signal_id}            - Update signal
    DELETE /safety-signal-detection/signals/{signal_id}            - Delete signal
    GET    /safety-signal-detection/evaluations                    - List evaluations
    POST   /safety-signal-detection/evaluations                    - Create evaluation
    GET    /safety-signal-detection/evaluations/{evaluation_id}    - Get evaluation
    DELETE /safety-signal-detection/evaluations/{evaluation_id}    - Delete evaluation
    GET    /safety-signal-detection/cumulative-reviews             - List reviews
    POST   /safety-signal-detection/cumulative-reviews             - Create review
    GET    /safety-signal-detection/cumulative-reviews/{review_id} - Get review
    DELETE /safety-signal-detection/cumulative-reviews/{review_id} - Delete review
    GET    /safety-signal-detection/analyses                       - List analyses
    POST   /safety-signal-detection/analyses                       - Create analysis
    GET    /safety-signal-detection/analyses/{analysis_id}         - Get analysis
    PUT    /safety-signal-detection/analyses/{analysis_id}         - Update analysis
    DELETE /safety-signal-detection/analyses/{analysis_id}         - Delete analysis
    GET    /safety-signal-detection/aggregate-reports              - List reports
    POST   /safety-signal-detection/aggregate-reports              - Create report
    GET    /safety-signal-detection/aggregate-reports/{report_id}  - Get report
    PUT    /safety-signal-detection/aggregate-reports/{report_id}  - Update report
    DELETE /safety-signal-detection/aggregate-reports/{report_id}  - Delete report
    GET    /safety-signal-detection/metrics                        - Metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.safety_signal_detection import (
    AggregateSafetyReport,
    AggregateSafetyReportCreate,
    AggregateSafetyReportListResponse,
    AggregateSafetyReportUpdate,
    CumulativeReview,
    CumulativeReviewCreate,
    CumulativeReviewListResponse,
    DisproportionalityAnalysis,
    DisproportionalityAnalysisCreate,
    DisproportionalityAnalysisListResponse,
    DisproportionalityAnalysisUpdate,
    SafetySignal,
    SafetySignalCreate,
    SafetySignalListResponse,
    SafetySignalMetrics,
    SafetySignalUpdate,
    SignalEvaluation,
    SignalEvaluationCreate,
    SignalEvaluationListResponse,
)
from app.services.safety_signal_detection_service import get_safety_signal_detection_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/safety-signal-detection",
    tags=["Safety Signal Detection"],
)


# ============================================================================
# Safety Signals
# ============================================================================


@router.get("/signals", response_model=SafetySignalListResponse)
def list_signals(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> SafetySignalListResponse:
    """List all safety signals, optionally filtered by trial."""
    svc = get_safety_signal_detection_service()
    items = svc.list_signals(trial_id=trial_id)
    return SafetySignalListResponse(items=items, total=len(items))


@router.post("/signals", response_model=SafetySignal, status_code=201)
def create_signal(payload: SafetySignalCreate) -> SafetySignal:
    """Create a new safety signal."""
    svc = get_safety_signal_detection_service()
    return svc.create_signal(payload)


@router.get("/signals/{signal_id}", response_model=SafetySignal)
def get_signal(signal_id: str) -> SafetySignal:
    """Get a safety signal by ID."""
    svc = get_safety_signal_detection_service()
    signal = svc.get_signal(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")
    return signal


@router.put("/signals/{signal_id}", response_model=SafetySignal)
def update_signal(signal_id: str, payload: SafetySignalUpdate) -> SafetySignal:
    """Update a safety signal."""
    svc = get_safety_signal_detection_service()
    updated = svc.update_signal(signal_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")
    return updated


@router.delete("/signals/{signal_id}", status_code=204)
def delete_signal(signal_id: str) -> None:
    """Delete a safety signal."""
    svc = get_safety_signal_detection_service()
    if not svc.delete_signal(signal_id):
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")


# ============================================================================
# Signal Evaluations
# ============================================================================


@router.get("/evaluations", response_model=SignalEvaluationListResponse)
def list_evaluations(
    signal_id: Optional[str] = Query(None, description="Filter by signal ID"),
) -> SignalEvaluationListResponse:
    """List all signal evaluations, optionally filtered by signal."""
    svc = get_safety_signal_detection_service()
    items = svc.list_evaluations(signal_id=signal_id)
    return SignalEvaluationListResponse(items=items, total=len(items))


@router.post("/evaluations", response_model=SignalEvaluation, status_code=201)
def create_evaluation(payload: SignalEvaluationCreate) -> SignalEvaluation:
    """Create a new signal evaluation."""
    svc = get_safety_signal_detection_service()
    return svc.create_evaluation(payload)


@router.get("/evaluations/{evaluation_id}", response_model=SignalEvaluation)
def get_evaluation(evaluation_id: str) -> SignalEvaluation:
    """Get a signal evaluation by ID."""
    svc = get_safety_signal_detection_service()
    evaluation = svc.get_evaluation(evaluation_id)
    if evaluation is None:
        raise HTTPException(status_code=404, detail=f"Evaluation {evaluation_id} not found")
    return evaluation


@router.delete("/evaluations/{evaluation_id}", status_code=204)
def delete_evaluation(evaluation_id: str) -> None:
    """Delete a signal evaluation."""
    svc = get_safety_signal_detection_service()
    if not svc.delete_evaluation(evaluation_id):
        raise HTTPException(status_code=404, detail=f"Evaluation {evaluation_id} not found")


# ============================================================================
# Cumulative Reviews
# ============================================================================


@router.get("/cumulative-reviews", response_model=CumulativeReviewListResponse)
def list_cumulative_reviews(
    signal_id: Optional[str] = Query(None, description="Filter by signal ID"),
) -> CumulativeReviewListResponse:
    """List all cumulative reviews, optionally filtered by signal."""
    svc = get_safety_signal_detection_service()
    items = svc.list_cumulative_reviews(signal_id=signal_id)
    return CumulativeReviewListResponse(items=items, total=len(items))


@router.post("/cumulative-reviews", response_model=CumulativeReview, status_code=201)
def create_cumulative_review(payload: CumulativeReviewCreate) -> CumulativeReview:
    """Create a new cumulative review."""
    svc = get_safety_signal_detection_service()
    return svc.create_cumulative_review(payload)


@router.get("/cumulative-reviews/{review_id}", response_model=CumulativeReview)
def get_cumulative_review(review_id: str) -> CumulativeReview:
    """Get a cumulative review by ID."""
    svc = get_safety_signal_detection_service()
    review = svc.get_cumulative_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail=f"Cumulative review {review_id} not found")
    return review


@router.delete("/cumulative-reviews/{review_id}", status_code=204)
def delete_cumulative_review(review_id: str) -> None:
    """Delete a cumulative review."""
    svc = get_safety_signal_detection_service()
    if not svc.delete_cumulative_review(review_id):
        raise HTTPException(status_code=404, detail=f"Cumulative review {review_id} not found")


# ============================================================================
# Disproportionality Analyses
# ============================================================================


@router.get("/analyses", response_model=DisproportionalityAnalysisListResponse)
def list_analyses(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> DisproportionalityAnalysisListResponse:
    """List all disproportionality analyses, optionally filtered by trial."""
    svc = get_safety_signal_detection_service()
    items = svc.list_analyses(trial_id=trial_id)
    return DisproportionalityAnalysisListResponse(items=items, total=len(items))


@router.post("/analyses", response_model=DisproportionalityAnalysis, status_code=201)
def create_analysis(payload: DisproportionalityAnalysisCreate) -> DisproportionalityAnalysis:
    """Create a new disproportionality analysis."""
    svc = get_safety_signal_detection_service()
    return svc.create_analysis(payload)


@router.get("/analyses/{analysis_id}", response_model=DisproportionalityAnalysis)
def get_analysis(analysis_id: str) -> DisproportionalityAnalysis:
    """Get a disproportionality analysis by ID."""
    svc = get_safety_signal_detection_service()
    analysis = svc.get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")
    return analysis


@router.put("/analyses/{analysis_id}", response_model=DisproportionalityAnalysis)
def update_analysis(analysis_id: str, payload: DisproportionalityAnalysisUpdate) -> DisproportionalityAnalysis:
    """Update a disproportionality analysis."""
    svc = get_safety_signal_detection_service()
    updated = svc.update_analysis(analysis_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")
    return updated


@router.delete("/analyses/{analysis_id}", status_code=204)
def delete_analysis(analysis_id: str) -> None:
    """Delete a disproportionality analysis."""
    svc = get_safety_signal_detection_service()
    if not svc.delete_analysis(analysis_id):
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")


# ============================================================================
# Aggregate Safety Reports
# ============================================================================


@router.get("/aggregate-reports", response_model=AggregateSafetyReportListResponse)
def list_aggregate_reports(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> AggregateSafetyReportListResponse:
    """List all aggregate safety reports, optionally filtered by trial."""
    svc = get_safety_signal_detection_service()
    items = svc.list_aggregate_reports(trial_id=trial_id)
    return AggregateSafetyReportListResponse(items=items, total=len(items))


@router.post("/aggregate-reports", response_model=AggregateSafetyReport, status_code=201)
def create_aggregate_report(payload: AggregateSafetyReportCreate) -> AggregateSafetyReport:
    """Create a new aggregate safety report."""
    svc = get_safety_signal_detection_service()
    return svc.create_aggregate_report(payload)


@router.get("/aggregate-reports/{report_id}", response_model=AggregateSafetyReport)
def get_aggregate_report(report_id: str) -> AggregateSafetyReport:
    """Get an aggregate safety report by ID."""
    svc = get_safety_signal_detection_service()
    report = svc.get_aggregate_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Aggregate report {report_id} not found")
    return report


@router.put("/aggregate-reports/{report_id}", response_model=AggregateSafetyReport)
def update_aggregate_report(report_id: str, payload: AggregateSafetyReportUpdate) -> AggregateSafetyReport:
    """Update an aggregate safety report."""
    svc = get_safety_signal_detection_service()
    updated = svc.update_aggregate_report(report_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Aggregate report {report_id} not found")
    return updated


@router.delete("/aggregate-reports/{report_id}", status_code=204)
def delete_aggregate_report(report_id: str) -> None:
    """Delete an aggregate safety report."""
    svc = get_safety_signal_detection_service()
    if not svc.delete_aggregate_report(report_id):
        raise HTTPException(status_code=404, detail=f"Aggregate report {report_id} not found")


# ============================================================================
# Metrics
# ============================================================================


@router.get("/metrics", response_model=SafetySignalMetrics)
def get_metrics() -> SafetySignalMetrics:
    """Get safety signal detection operational metrics."""
    svc = get_safety_signal_detection_service()
    return svc.get_metrics()
