"""Electronic Patient-Reported Outcomes (ePRO) & Questionnaire Management API endpoints (CLINICAL-9).

Manages validated PRO instruments (EQ-5D-5L, EORTC QLQ-C30, DLQI, NEI-VFQ-25,
PRO-CTCAE, WPAI), patient assignments, questionnaire responses with scoring,
compliance monitoring, MCID detection, trend analysis, and reminder generation.

Endpoints:
    GET    /epro/instruments                                    - List instruments
    GET    /epro/instruments/{instrument_id}                    - Get single instrument
    POST   /epro/instruments                                    - Create instrument
    PUT    /epro/instruments/{instrument_id}                    - Update instrument
    DELETE /epro/instruments/{instrument_id}                    - Delete instrument
    GET    /epro/instruments/{instrument_id}/questions          - Get instrument questions
    POST   /epro/schedules                                      - Create schedule template
    GET    /epro/schedules                                      - List schedule templates
    POST   /epro/assignments                                    - Create patient assignment
    GET    /epro/patients/{patient_id}/assignments              - Get patient assignments
    POST   /epro/assignments/{assignment_id}/deactivate         - Deactivate assignment
    POST   /epro/responses                                      - Submit questionnaire response
    GET    /epro/responses/{response_id}                        - Get single response
    GET    /epro/responses/{response_id}/scored                 - Get scored response
    GET    /epro/patients/{patient_id}/responses                - Get patient responses
    GET    /epro/patients/{patient_id}/compliance               - Patient compliance report
    GET    /epro/trials/{trial_id}/compliance                   - Trial compliance report
    GET    /epro/reminders                                      - Get reminders
    GET    /epro/patients/{patient_id}/trends                   - Patient score trends
    GET    /epro/mcid-alerts                                    - Get MCID alerts
    GET    /epro/metrics                                        - ePRO dashboard metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.epro import (
    AssignmentCreate,
    AssignmentListResponse,
    ComplianceReport,
    EPROMetrics,
    Instrument,
    InstrumentCategory,
    InstrumentCreate,
    InstrumentListResponse,
    InstrumentUpdate,
    MCIDAlertListResponse,
    PatientAssignment,
    PatientScoreTrend,
    Question,
    QuestionnaireResponse,
    ReminderListResponse,
    ResponseListResponse,
    ResponseSubmit,
    ScheduleCreate,
    ScheduleListResponse,
    ScheduleTemplate,
    ScoredResponse,
    TrialComplianceReport,
)
from app.services.epro_service import get_epro_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/epro",
    tags=["Electronic Patient-Reported Outcomes"],
)


# ---------------------------------------------------------------------------
# Instrument Management
# ---------------------------------------------------------------------------


@router.get(
    "/instruments",
    response_model=InstrumentListResponse,
    summary="List PRO instruments",
    description="Retrieve validated PRO instruments with optional filtering by category.",
)
async def list_instruments(
    category: Optional[InstrumentCategory] = Query(None, description="Filter by instrument category"),
) -> InstrumentListResponse:
    svc = get_epro_service()
    items = svc.list_instruments(category=category)
    return InstrumentListResponse(items=items, total=len(items))


@router.get(
    "/instruments/{instrument_id}",
    response_model=Instrument,
    summary="Get a PRO instrument",
)
async def get_instrument(instrument_id: str) -> Instrument:
    svc = get_epro_service()
    try:
        return svc.get_instrument(instrument_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Instrument '{instrument_id}' not found")


@router.post(
    "/instruments",
    response_model=Instrument,
    status_code=201,
    summary="Create a PRO instrument",
)
async def create_instrument(payload: InstrumentCreate) -> Instrument:
    svc = get_epro_service()
    return svc.create_instrument(payload)


@router.put(
    "/instruments/{instrument_id}",
    response_model=Instrument,
    summary="Update a PRO instrument",
)
async def update_instrument(instrument_id: str, payload: InstrumentUpdate) -> Instrument:
    svc = get_epro_service()
    try:
        return svc.update_instrument(instrument_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Instrument '{instrument_id}' not found")


@router.delete(
    "/instruments/{instrument_id}",
    status_code=204,
    summary="Delete a PRO instrument",
)
async def delete_instrument(instrument_id: str) -> None:
    svc = get_epro_service()
    try:
        svc.delete_instrument(instrument_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Instrument '{instrument_id}' not found")


@router.get(
    "/instruments/{instrument_id}/questions",
    response_model=list[Question],
    summary="Get questions for a PRO instrument",
)
async def get_instrument_questions(instrument_id: str) -> list[Question]:
    svc = get_epro_service()
    try:
        return svc.get_instrument_questions(instrument_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Instrument '{instrument_id}' not found")


# ---------------------------------------------------------------------------
# Schedule Templates
# ---------------------------------------------------------------------------


@router.post(
    "/schedules",
    response_model=ScheduleTemplate,
    status_code=201,
    summary="Create a schedule template",
    description="Create a schedule template defining when questionnaires should be administered.",
)
async def create_schedule(payload: ScheduleCreate) -> ScheduleTemplate:
    svc = get_epro_service()
    try:
        return svc.create_schedule(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/schedules",
    response_model=ScheduleListResponse,
    summary="List schedule templates",
    description="Retrieve schedule templates with optional filtering by trial.",
)
async def list_schedules(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> ScheduleListResponse:
    svc = get_epro_service()
    items = svc.list_schedules(trial_id=trial_id)
    return ScheduleListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Patient Assignments
# ---------------------------------------------------------------------------


@router.post(
    "/assignments",
    response_model=PatientAssignment,
    status_code=201,
    summary="Assign an instrument to a patient",
)
async def create_assignment(payload: AssignmentCreate) -> PatientAssignment:
    svc = get_epro_service()
    try:
        return svc.create_assignment(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/patients/{patient_id}/assignments",
    response_model=AssignmentListResponse,
    summary="Get patient assignments",
    description="Retrieve instrument assignments for a patient, optionally including inactive.",
)
async def get_patient_assignments(
    patient_id: str,
    active_only: bool = Query(True, description="Show only active assignments"),
) -> AssignmentListResponse:
    svc = get_epro_service()
    items = svc.get_patient_assignments(patient_id, active_only=active_only)
    return AssignmentListResponse(items=items, total=len(items))


@router.post(
    "/assignments/{assignment_id}/deactivate",
    response_model=PatientAssignment,
    summary="Deactivate a patient assignment",
)
async def deactivate_assignment(assignment_id: str) -> PatientAssignment:
    svc = get_epro_service()
    try:
        return svc.deactivate_assignment(assignment_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Assignment '{assignment_id}' not found")


# ---------------------------------------------------------------------------
# Questionnaire Responses
# ---------------------------------------------------------------------------


@router.post(
    "/responses",
    response_model=QuestionnaireResponse,
    status_code=201,
    summary="Submit a questionnaire response",
    description="Submit patient answers for a questionnaire. Automatically scores the response.",
)
async def submit_response(payload: ResponseSubmit) -> QuestionnaireResponse:
    svc = get_epro_service()
    try:
        return svc.submit_response(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/responses/{response_id}",
    response_model=QuestionnaireResponse,
    summary="Get a questionnaire response",
)
async def get_response(response_id: str) -> QuestionnaireResponse:
    svc = get_epro_service()
    try:
        return svc.get_response(response_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Response '{response_id}' not found")


@router.get(
    "/responses/{response_id}/scored",
    response_model=ScoredResponse,
    summary="Get scored response with domain breakdown",
    description="Retrieve a scored response with domain-level breakdowns and clinical interpretation.",
)
async def get_scored_response(response_id: str) -> ScoredResponse:
    svc = get_epro_service()
    try:
        return svc.get_scored_response(response_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Response '{response_id}' not found")


@router.get(
    "/patients/{patient_id}/responses",
    response_model=ResponseListResponse,
    summary="Get patient response history",
    description="Retrieve questionnaire responses for a patient with optional instrument filter and pagination.",
)
async def get_patient_responses(
    patient_id: str,
    instrument_id: Optional[str] = Query(None, description="Filter by instrument ID"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> ResponseListResponse:
    svc = get_epro_service()
    items, total = svc.get_patient_responses(
        patient_id, instrument_id=instrument_id, limit=limit, offset=offset
    )
    return ResponseListResponse(items=items, total=total)


# ---------------------------------------------------------------------------
# Compliance Monitoring
# ---------------------------------------------------------------------------


@router.get(
    "/patients/{patient_id}/compliance",
    response_model=list[ComplianceReport],
    summary="Get patient compliance report",
    description="Compliance reports for a patient across all assigned instruments.",
)
async def get_patient_compliance(patient_id: str) -> list[ComplianceReport]:
    svc = get_epro_service()
    return svc.get_patient_compliance(patient_id)


@router.get(
    "/trials/{trial_id}/compliance",
    response_model=TrialComplianceReport,
    summary="Get trial-level compliance report",
    description="Aggregated compliance summary for a trial including per-instrument breakdown.",
)
async def get_trial_compliance(trial_id: str) -> TrialComplianceReport:
    svc = get_epro_service()
    return svc.get_trial_compliance(trial_id)


# ---------------------------------------------------------------------------
# Reminders
# ---------------------------------------------------------------------------


@router.get(
    "/reminders",
    response_model=ReminderListResponse,
    summary="Get upcoming and overdue reminders",
    description="Retrieve reminders for upcoming and overdue questionnaires with optional patient/trial filters.",
)
async def get_reminders(
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> ReminderListResponse:
    svc = get_epro_service()
    items, total_upcoming, total_overdue = svc.get_reminders(
        patient_id=patient_id, trial_id=trial_id
    )
    return ReminderListResponse(
        items=items, total_upcoming=total_upcoming, total_overdue=total_overdue
    )


# ---------------------------------------------------------------------------
# Trend Analysis
# ---------------------------------------------------------------------------


@router.get(
    "/patients/{patient_id}/trends",
    response_model=list[PatientScoreTrend],
    summary="Get patient score trends",
    description="Score trends over time for a patient, optionally filtered by instrument.",
)
async def get_patient_trends(
    patient_id: str,
    instrument_id: Optional[str] = Query(None, description="Filter by instrument ID"),
) -> list[PatientScoreTrend]:
    svc = get_epro_service()
    return svc.get_patient_trends(patient_id, instrument_id=instrument_id)


# ---------------------------------------------------------------------------
# MCID Alerts
# ---------------------------------------------------------------------------


@router.get(
    "/mcid-alerts",
    response_model=MCIDAlertListResponse,
    summary="Get MCID alerts",
    description="Retrieve all patients with clinically significant score changes exceeding the MCID threshold.",
)
async def get_mcid_alerts() -> MCIDAlertListResponse:
    svc = get_epro_service()
    items = svc.get_mcid_alerts()
    return MCIDAlertListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=EPROMetrics,
    summary="Get ePRO dashboard metrics",
    description="Aggregated ePRO metrics including compliance rates, completion rates, and MCID alerts.",
)
async def get_epro_metrics() -> EPROMetrics:
    svc = get_epro_service()
    return svc.get_metrics()
