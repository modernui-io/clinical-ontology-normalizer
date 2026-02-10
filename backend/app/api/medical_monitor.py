"""Medical Monitor Dashboard API endpoints.

Provides medical monitors with tools for safety signal review, benefit-risk
assessments, medical queries, patient case reviews, safety trend analysis,
monitor notes, and operational metrics.

Endpoints:
    GET    /medical-monitor/signals                              - List safety signals
    POST   /medical-monitor/signals                              - Create safety signal
    GET    /medical-monitor/signals/{signal_id}                   - Get safety signal
    PUT    /medical-monitor/signals/{signal_id}                   - Update safety signal
    POST   /medical-monitor/signals/{signal_id}/escalate          - Escalate safety signal
    GET    /medical-monitor/benefit-risk-assessments               - List assessments
    POST   /medical-monitor/benefit-risk-assessments               - Create assessment
    GET    /medical-monitor/assessments/{assessment_id}            - Get assessment
    PUT    /medical-monitor/assessments/{assessment_id}            - Update assessment
    GET    /medical-monitor/queries                               - List medical queries
    POST   /medical-monitor/queries                               - Create medical query
    GET    /medical-monitor/queries/{query_id}                    - Get medical query
    PUT    /medical-monitor/queries/{query_id}                    - Update medical query
    POST   /medical-monitor/queries/{query_id}/respond            - Respond to query
    GET    /medical-monitor/case-reviews                          - List case reviews
    POST   /medical-monitor/case-reviews                          - Create case review
    GET    /medical-monitor/case-reviews/{review_id}              - Get case review
    PUT    /medical-monitor/case-reviews/{review_id}              - Update case review
    POST   /medical-monitor/case-reviews/{review_id}/complete     - Complete case review
    GET    /medical-monitor/safety-trends                        - List safety trends
    GET    /medical-monitor/safety-trends/{trial_id}             - Get trial trends
    GET    /medical-monitor/notes                                - List monitor notes
    POST   /medical-monitor/notes                                - Create monitor note
    GET    /medical-monitor/metrics                              - Dashboard metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.medical_monitor import (
    BenefitRiskAssessment,
    BenefitRiskAssessmentCreate,
    BenefitRiskAssessmentListResponse,
    BenefitRiskAssessmentUpdate,
    CaseReviewCompletion,
    CaseReviewStatus,
    MedicalMonitorMetrics,
    MedicalMonitorNote,
    MedicalMonitorNoteCreate,
    MedicalMonitorNoteListResponse,
    MedicalQuery,
    MedicalQueryCreate,
    MedicalQueryListResponse,
    MedicalQueryResponse,
    MedicalQueryUpdate,
    NoteCategory,
    PatientCaseReview,
    PatientCaseReviewCreate,
    PatientCaseReviewListResponse,
    PatientCaseReviewUpdate,
    QueryCategory,
    QueryStatus,
    ReviewPriority,
    RiskLevel,
    SafetySignal,
    SafetySignalCreate,
    SafetySignalListResponse,
    SafetySignalUpdate,
    SafetyTrendListResponse,
    SignalEscalation,
    SignalStatus,
)
from app.services.medical_monitor_service import get_medical_monitor_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/medical-monitor",
    tags=["Medical Monitor"],
)


# ---------------------------------------------------------------------------
# Safety Signals
# ---------------------------------------------------------------------------


@router.get(
    "/signals",
    response_model=SafetySignalListResponse,
    summary="List safety signals",
    description="Retrieve safety signals with optional filtering by trial, status, and risk level.",
)
async def list_signals(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[SignalStatus] = Query(None, description="Filter by signal status"),
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk level"),
) -> SafetySignalListResponse:
    svc = get_medical_monitor_service()
    items = svc.list_signals(trial_id=trial_id, status=status, risk_level=risk_level)
    return SafetySignalListResponse(items=items, total=len(items))


@router.post(
    "/signals",
    response_model=SafetySignal,
    status_code=201,
    summary="Create a safety signal",
)
async def create_signal(payload: SafetySignalCreate) -> SafetySignal:
    svc = get_medical_monitor_service()
    return svc.create_signal(payload)


@router.get(
    "/signals/{signal_id}",
    response_model=SafetySignal,
    summary="Get a safety signal",
)
async def get_signal(signal_id: str) -> SafetySignal:
    svc = get_medical_monitor_service()
    signal = svc.get_signal(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail=f"Signal '{signal_id}' not found")
    return signal


@router.put(
    "/signals/{signal_id}",
    response_model=SafetySignal,
    summary="Update a safety signal",
)
async def update_signal(signal_id: str, payload: SafetySignalUpdate) -> SafetySignal:
    svc = get_medical_monitor_service()
    updated = svc.update_signal(signal_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Signal '{signal_id}' not found")
    return updated


@router.post(
    "/signals/{signal_id}/escalate",
    response_model=SafetySignal,
    summary="Escalate a safety signal",
    description="Escalate a safety signal to a higher authority or committee.",
)
async def escalate_signal(signal_id: str, payload: SignalEscalation) -> SafetySignal:
    svc = get_medical_monitor_service()
    try:
        result = svc.escalate_signal(signal_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Signal '{signal_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Benefit-Risk Assessments
# ---------------------------------------------------------------------------


@router.get(
    "/benefit-risk-assessments",
    response_model=BenefitRiskAssessmentListResponse,
    summary="List benefit-risk assessments",
    description="Retrieve benefit-risk assessments with optional trial filter.",
)
async def list_assessments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> BenefitRiskAssessmentListResponse:
    svc = get_medical_monitor_service()
    items = svc.list_assessments(trial_id=trial_id)
    return BenefitRiskAssessmentListResponse(items=items, total=len(items))


@router.post(
    "/benefit-risk-assessments",
    response_model=BenefitRiskAssessment,
    status_code=201,
    summary="Create a benefit-risk assessment",
)
async def create_assessment(payload: BenefitRiskAssessmentCreate) -> BenefitRiskAssessment:
    svc = get_medical_monitor_service()
    return svc.create_assessment(payload)


@router.get(
    "/assessments/{assessment_id}",
    response_model=BenefitRiskAssessment,
    summary="Get a benefit-risk assessment",
)
async def get_assessment(assessment_id: str) -> BenefitRiskAssessment:
    svc = get_medical_monitor_service()
    assessment = svc.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")
    return assessment


@router.put(
    "/assessments/{assessment_id}",
    response_model=BenefitRiskAssessment,
    summary="Update a benefit-risk assessment",
)
async def update_assessment(
    assessment_id: str, payload: BenefitRiskAssessmentUpdate
) -> BenefitRiskAssessment:
    svc = get_medical_monitor_service()
    updated = svc.update_assessment(assessment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Assessment '{assessment_id}' not found")
    return updated


# ---------------------------------------------------------------------------
# Medical Queries
# ---------------------------------------------------------------------------


@router.get(
    "/queries",
    response_model=MedicalQueryListResponse,
    summary="List medical queries",
    description="Retrieve medical queries with optional filtering by trial, site, category, status, and priority.",
)
async def list_queries(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
    category: Optional[QueryCategory] = Query(None, description="Filter by category"),
    status: Optional[QueryStatus] = Query(None, description="Filter by status"),
    priority: Optional[ReviewPriority] = Query(None, description="Filter by priority"),
) -> MedicalQueryListResponse:
    svc = get_medical_monitor_service()
    items = svc.list_queries(
        trial_id=trial_id, site_id=site_id, category=category,
        status=status, priority=priority,
    )
    return MedicalQueryListResponse(items=items, total=len(items))


@router.post(
    "/queries",
    response_model=MedicalQuery,
    status_code=201,
    summary="Create a medical query",
)
async def create_query(payload: MedicalQueryCreate) -> MedicalQuery:
    svc = get_medical_monitor_service()
    return svc.create_query(payload)


@router.get(
    "/queries/{query_id}",
    response_model=MedicalQuery,
    summary="Get a medical query",
)
async def get_query(query_id: str) -> MedicalQuery:
    svc = get_medical_monitor_service()
    query = svc.get_query(query_id)
    if query is None:
        raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found")
    return query


@router.put(
    "/queries/{query_id}",
    response_model=MedicalQuery,
    summary="Update a medical query",
)
async def update_query(query_id: str, payload: MedicalQueryUpdate) -> MedicalQuery:
    svc = get_medical_monitor_service()
    updated = svc.update_query(query_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found")
    return updated


@router.post(
    "/queries/{query_id}/respond",
    response_model=MedicalQuery,
    summary="Respond to a medical query",
    description="Provide a medical monitor response to a query.",
)
async def respond_to_query(query_id: str, payload: MedicalQueryResponse) -> MedicalQuery:
    svc = get_medical_monitor_service()
    try:
        result = svc.respond_to_query(query_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Query '{query_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Patient Case Reviews
# ---------------------------------------------------------------------------


@router.get(
    "/case-reviews",
    response_model=PatientCaseReviewListResponse,
    summary="List patient case reviews",
    description="Retrieve case reviews with optional filtering by trial, status, and priority.",
)
async def list_case_reviews(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[CaseReviewStatus] = Query(None, description="Filter by status"),
    priority: Optional[ReviewPriority] = Query(None, description="Filter by priority"),
) -> PatientCaseReviewListResponse:
    svc = get_medical_monitor_service()
    items = svc.list_case_reviews(trial_id=trial_id, status=status, priority=priority)
    return PatientCaseReviewListResponse(items=items, total=len(items))


@router.post(
    "/case-reviews",
    response_model=PatientCaseReview,
    status_code=201,
    summary="Create a patient case review",
)
async def create_case_review(payload: PatientCaseReviewCreate) -> PatientCaseReview:
    svc = get_medical_monitor_service()
    return svc.create_case_review(payload)


@router.get(
    "/case-reviews/{review_id}",
    response_model=PatientCaseReview,
    summary="Get a patient case review",
)
async def get_case_review(review_id: str) -> PatientCaseReview:
    svc = get_medical_monitor_service()
    review = svc.get_case_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail=f"Case review '{review_id}' not found")
    return review


@router.put(
    "/case-reviews/{review_id}",
    response_model=PatientCaseReview,
    summary="Update a patient case review",
)
async def update_case_review(
    review_id: str, payload: PatientCaseReviewUpdate
) -> PatientCaseReview:
    svc = get_medical_monitor_service()
    updated = svc.update_case_review(review_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Case review '{review_id}' not found")
    return updated


@router.post(
    "/case-reviews/{review_id}/complete",
    response_model=PatientCaseReview,
    summary="Complete a patient case review",
    description="Complete a case review with findings, recommendations, and action items.",
)
async def complete_case_review(
    review_id: str, payload: CaseReviewCompletion
) -> PatientCaseReview:
    svc = get_medical_monitor_service()
    try:
        result = svc.complete_case_review(review_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Case review '{review_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Safety Trends
# ---------------------------------------------------------------------------


@router.get(
    "/safety-trends",
    response_model=SafetyTrendListResponse,
    summary="List safety trends",
    description="Retrieve safety trends across all trials or filtered by trial.",
)
async def list_safety_trends(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> SafetyTrendListResponse:
    svc = get_medical_monitor_service()
    items = svc.list_trends(trial_id=trial_id)
    return SafetyTrendListResponse(items=items, total=len(items))


@router.get(
    "/safety-trends/{trial_id}",
    response_model=SafetyTrendListResponse,
    summary="Get safety trends for a trial",
    description="Retrieve all safety trends for a specific trial, including trend analysis.",
)
async def get_trial_safety_trends(trial_id: str) -> SafetyTrendListResponse:
    svc = get_medical_monitor_service()
    items = svc.get_trial_trends(trial_id)
    return SafetyTrendListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Medical Monitor Notes
# ---------------------------------------------------------------------------


@router.get(
    "/notes",
    response_model=MedicalMonitorNoteListResponse,
    summary="List medical monitor notes",
    description="Retrieve monitor notes with optional filtering by trial and category.",
)
async def list_notes(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    category: Optional[NoteCategory] = Query(None, description="Filter by category"),
) -> MedicalMonitorNoteListResponse:
    svc = get_medical_monitor_service()
    items = svc.list_notes(trial_id=trial_id, category=category)
    return MedicalMonitorNoteListResponse(items=items, total=len(items))


@router.post(
    "/notes",
    response_model=MedicalMonitorNote,
    status_code=201,
    summary="Create a medical monitor note",
)
async def create_note(payload: MedicalMonitorNoteCreate) -> MedicalMonitorNote:
    svc = get_medical_monitor_service()
    return svc.create_note(payload)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=MedicalMonitorMetrics,
    summary="Get medical monitor dashboard metrics",
    description="Aggregated operational metrics for the medical monitor dashboard.",
)
async def get_metrics() -> MedicalMonitorMetrics:
    svc = get_medical_monitor_service()
    return svc.get_metrics()
