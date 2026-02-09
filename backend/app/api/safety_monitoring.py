"""Data Safety Monitoring Board (DSMB) API endpoints (CLINICAL-3).

Provides comprehensive DSMB management: board membership, meeting governance,
interim analyses with group-sequential stopping rules, event adjudication
workflows, safety report generation, charter management, and operational metrics.

Endpoints:
    GET    /safety-monitoring/members                         - List DSMB members
    GET    /safety-monitoring/members/{member_id}             - Get single member
    POST   /safety-monitoring/members                         - Create member
    PUT    /safety-monitoring/members/{member_id}             - Update member
    GET    /safety-monitoring/meetings                        - List meetings
    GET    /safety-monitoring/meetings/upcoming               - Upcoming meetings
    GET    /safety-monitoring/meetings/{meeting_id}           - Get single meeting
    POST   /safety-monitoring/meetings                        - Schedule meeting
    PUT    /safety-monitoring/meetings/{meeting_id}           - Update meeting
    GET    /safety-monitoring/interim-analyses                - List interim analyses
    GET    /safety-monitoring/interim-analyses/{analysis_id}  - Get single analysis
    POST   /safety-monitoring/interim-analyses                - Create analysis
    GET    /safety-monitoring/adjudications                   - List adjudications
    GET    /safety-monitoring/adjudications/overdue           - Overdue adjudications
    GET    /safety-monitoring/adjudications/{adj_id}          - Get single adjudication
    POST   /safety-monitoring/adjudications                   - Submit adjudication
    PUT    /safety-monitoring/adjudications/{adj_id}          - Update adjudication
    GET    /safety-monitoring/safety-reports                  - List safety reports
    GET    /safety-monitoring/safety-reports/{report_id}      - Get single report
    POST   /safety-monitoring/safety-reports                  - Generate report
    GET    /safety-monitoring/charters                        - List charters
    GET    /safety-monitoring/charters/{charter_id}           - Get single charter
    POST   /safety-monitoring/charters                        - Create charter
    PUT    /safety-monitoring/charters/{charter_id}           - Update charter
    GET    /safety-monitoring/metrics                         - DSMB metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.safety_monitoring import (
    DSMBCharter,
    DSMBCharterCreate,
    DSMBCharterListResponse,
    DSMBCharterUpdate,
    DSMBMeeting,
    DSMBMeetingCreate,
    DSMBMeetingListResponse,
    DSMBMeetingUpdate,
    DSMBMember,
    DSMBMemberCreate,
    DSMBMemberListResponse,
    DSMBMemberUpdate,
    DSMBMetrics,
    DSMBRole,
    EventAdjudication,
    EventAdjudicationCreate,
    EventAdjudicationListResponse,
    EventAdjudicationStatus,
    EventAdjudicationUpdate,
    InterimAnalysis,
    InterimAnalysisCreate,
    InterimAnalysisListResponse,
    InterimAnalysisType,
    MeetingType,
    ReportAccessLevel,
    SafetyReport,
    SafetyReportCreate,
    SafetyReportListResponse,
)
from app.services.safety_monitoring_service import get_safety_monitoring_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/safety-monitoring",
    tags=["Safety Monitoring (DSMB)"],
)


# ---------------------------------------------------------------------------
# DSMB Members
# ---------------------------------------------------------------------------


@router.get(
    "/members",
    response_model=DSMBMemberListResponse,
    summary="List DSMB members",
    description="Retrieve DSMB members with optional filtering by role and active status.",
)
async def list_members(
    role: Optional[DSMBRole] = Query(None, description="Filter by role"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
) -> DSMBMemberListResponse:
    svc = get_safety_monitoring_service()
    items = svc.list_members(role=role, active=active)
    return DSMBMemberListResponse(items=items, total=len(items))


@router.get(
    "/members/{member_id}",
    response_model=DSMBMember,
    summary="Get a DSMB member",
)
async def get_member(member_id: str) -> DSMBMember:
    svc = get_safety_monitoring_service()
    member = svc.get_member(member_id)
    if member is None:
        raise HTTPException(status_code=404, detail=f"DSMB member '{member_id}' not found")
    return member


@router.post(
    "/members",
    response_model=DSMBMember,
    status_code=201,
    summary="Create a DSMB member",
)
async def create_member(payload: DSMBMemberCreate) -> DSMBMember:
    svc = get_safety_monitoring_service()
    return svc.create_member(payload)


@router.put(
    "/members/{member_id}",
    response_model=DSMBMember,
    summary="Update a DSMB member",
)
async def update_member(member_id: str, payload: DSMBMemberUpdate) -> DSMBMember:
    svc = get_safety_monitoring_service()
    updated = svc.update_member(member_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"DSMB member '{member_id}' not found")
    return updated


# ---------------------------------------------------------------------------
# DSMB Meetings
# ---------------------------------------------------------------------------


@router.get(
    "/meetings",
    response_model=DSMBMeetingListResponse,
    summary="List DSMB meetings",
    description="Retrieve meetings with optional filtering by trial and meeting type.",
)
async def list_meetings(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    meeting_type: Optional[MeetingType] = Query(None, description="Filter by meeting type"),
) -> DSMBMeetingListResponse:
    svc = get_safety_monitoring_service()
    items = svc.list_meetings(trial_id=trial_id, meeting_type=meeting_type)
    return DSMBMeetingListResponse(items=items, total=len(items))


@router.get(
    "/meetings/upcoming",
    response_model=DSMBMeetingListResponse,
    summary="Get upcoming DSMB meetings",
    description="Retrieve meetings scheduled within the next N days.",
)
async def get_upcoming_meetings(
    days: int = Query(30, ge=1, le=365, description="Number of days to look ahead"),
) -> DSMBMeetingListResponse:
    svc = get_safety_monitoring_service()
    items = svc.get_upcoming_meetings(days=days)
    return DSMBMeetingListResponse(items=items, total=len(items))


@router.get(
    "/meetings/{meeting_id}",
    response_model=DSMBMeeting,
    summary="Get a DSMB meeting",
)
async def get_meeting(meeting_id: str) -> DSMBMeeting:
    svc = get_safety_monitoring_service()
    meeting = svc.get_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail=f"DSMB meeting '{meeting_id}' not found")
    return meeting


@router.post(
    "/meetings",
    response_model=DSMBMeeting,
    status_code=201,
    summary="Schedule a DSMB meeting",
)
async def create_meeting(payload: DSMBMeetingCreate) -> DSMBMeeting:
    svc = get_safety_monitoring_service()
    return svc.create_meeting(payload)


@router.put(
    "/meetings/{meeting_id}",
    response_model=DSMBMeeting,
    summary="Update a DSMB meeting",
    description="Update meeting details including minutes, outcome, and recommendations.",
)
async def update_meeting(meeting_id: str, payload: DSMBMeetingUpdate) -> DSMBMeeting:
    svc = get_safety_monitoring_service()
    updated = svc.update_meeting(meeting_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"DSMB meeting '{meeting_id}' not found")
    return updated


# ---------------------------------------------------------------------------
# Interim Analyses
# ---------------------------------------------------------------------------


@router.get(
    "/interim-analyses",
    response_model=InterimAnalysisListResponse,
    summary="List interim analyses",
    description="Retrieve interim analyses with optional filtering by trial and type.",
)
async def list_interim_analyses(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    analysis_type: Optional[InterimAnalysisType] = Query(None, description="Filter by analysis type"),
) -> InterimAnalysisListResponse:
    svc = get_safety_monitoring_service()
    items = svc.list_interim_analyses(trial_id=trial_id, analysis_type=analysis_type)
    return InterimAnalysisListResponse(items=items, total=len(items))


@router.get(
    "/interim-analyses/{analysis_id}",
    response_model=InterimAnalysis,
    summary="Get an interim analysis",
)
async def get_interim_analysis(analysis_id: str) -> InterimAnalysis:
    svc = get_safety_monitoring_service()
    analysis = svc.get_interim_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail=f"Interim analysis '{analysis_id}' not found")
    return analysis


@router.post(
    "/interim-analyses",
    response_model=InterimAnalysis,
    status_code=201,
    summary="Create an interim analysis",
    description="Create a new interim analysis with stopping rule evaluation using O'Brien-Fleming, Pocock, or Lan-DeMets methods.",
)
async def create_interim_analysis(payload: InterimAnalysisCreate) -> InterimAnalysis:
    svc = get_safety_monitoring_service()
    return svc.create_interim_analysis(payload)


# ---------------------------------------------------------------------------
# Event Adjudications
# ---------------------------------------------------------------------------


@router.get(
    "/adjudications",
    response_model=EventAdjudicationListResponse,
    summary="List event adjudications",
    description="Retrieve adjudications with optional filtering by trial, status, and patient.",
)
async def list_adjudications(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[EventAdjudicationStatus] = Query(None, description="Filter by status"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
) -> EventAdjudicationListResponse:
    svc = get_safety_monitoring_service()
    items = svc.list_adjudications(trial_id=trial_id, status=status, patient_id=patient_id)
    return EventAdjudicationListResponse(items=items, total=len(items))


@router.get(
    "/adjudications/overdue",
    response_model=EventAdjudicationListResponse,
    summary="Get overdue adjudications",
    description="Retrieve adjudications that have been PENDING for more than 30 days.",
)
async def get_overdue_adjudications() -> EventAdjudicationListResponse:
    svc = get_safety_monitoring_service()
    items = svc.get_overdue_adjudications()
    return EventAdjudicationListResponse(items=items, total=len(items))


@router.get(
    "/adjudications/{adjudication_id}",
    response_model=EventAdjudication,
    summary="Get an event adjudication",
)
async def get_adjudication(adjudication_id: str) -> EventAdjudication:
    svc = get_safety_monitoring_service()
    adj = svc.get_adjudication(adjudication_id)
    if adj is None:
        raise HTTPException(status_code=404, detail=f"Adjudication '{adjudication_id}' not found")
    return adj


@router.post(
    "/adjudications",
    response_model=EventAdjudication,
    status_code=201,
    summary="Submit an event for adjudication",
)
async def create_adjudication(payload: EventAdjudicationCreate) -> EventAdjudication:
    svc = get_safety_monitoring_service()
    return svc.create_adjudication(payload)


@router.put(
    "/adjudications/{adjudication_id}",
    response_model=EventAdjudication,
    summary="Update an event adjudication",
    description="Update adjudication status, assign adjudicator, or provide classification. Enforces valid status transitions.",
)
async def update_adjudication(
    adjudication_id: str,
    payload: EventAdjudicationUpdate,
) -> EventAdjudication:
    svc = get_safety_monitoring_service()
    try:
        updated = svc.update_adjudication(adjudication_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Adjudication '{adjudication_id}' not found")
    return updated


# ---------------------------------------------------------------------------
# Safety Reports
# ---------------------------------------------------------------------------


@router.get(
    "/safety-reports",
    response_model=SafetyReportListResponse,
    summary="List safety reports",
    description="Retrieve safety reports with optional filtering by trial and access level.",
)
async def list_safety_reports(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    access_level: Optional[ReportAccessLevel] = Query(None, description="Filter by access level"),
) -> SafetyReportListResponse:
    svc = get_safety_monitoring_service()
    items = svc.list_safety_reports(trial_id=trial_id, access_level=access_level)
    return SafetyReportListResponse(items=items, total=len(items))


@router.get(
    "/safety-reports/{report_id}",
    response_model=SafetyReport,
    summary="Get a safety report",
)
async def get_safety_report(report_id: str) -> SafetyReport:
    svc = get_safety_monitoring_service()
    report = svc.get_safety_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Safety report '{report_id}' not found")
    return report


@router.post(
    "/safety-reports",
    response_model=SafetyReport,
    status_code=201,
    summary="Generate a safety report",
    description="Generate a new safety report with blinded or unblinded views.",
)
async def generate_safety_report(payload: SafetyReportCreate) -> SafetyReport:
    svc = get_safety_monitoring_service()
    return svc.generate_safety_report(payload)


# ---------------------------------------------------------------------------
# DSMB Charters
# ---------------------------------------------------------------------------


@router.get(
    "/charters",
    response_model=DSMBCharterListResponse,
    summary="List DSMB charters",
    description="Retrieve charters with optional filtering by trial.",
)
async def list_charters(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> DSMBCharterListResponse:
    svc = get_safety_monitoring_service()
    items = svc.list_charters(trial_id=trial_id)
    return DSMBCharterListResponse(items=items, total=len(items))


@router.get(
    "/charters/{charter_id}",
    response_model=DSMBCharter,
    summary="Get a DSMB charter",
)
async def get_charter(charter_id: str) -> DSMBCharter:
    svc = get_safety_monitoring_service()
    charter = svc.get_charter(charter_id)
    if charter is None:
        raise HTTPException(status_code=404, detail=f"DSMB charter '{charter_id}' not found")
    return charter


@router.post(
    "/charters",
    response_model=DSMBCharter,
    status_code=201,
    summary="Create a DSMB charter",
)
async def create_charter(payload: DSMBCharterCreate) -> DSMBCharter:
    svc = get_safety_monitoring_service()
    return svc.create_charter(payload)


@router.put(
    "/charters/{charter_id}",
    response_model=DSMBCharter,
    summary="Update a DSMB charter",
)
async def update_charter(charter_id: str, payload: DSMBCharterUpdate) -> DSMBCharter:
    svc = get_safety_monitoring_service()
    updated = svc.update_charter(charter_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"DSMB charter '{charter_id}' not found")
    return updated


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=DSMBMetrics,
    summary="Get DSMB operational metrics",
    description="Aggregated metrics across all DSMB operations.",
)
async def get_metrics() -> DSMBMetrics:
    svc = get_safety_monitoring_service()
    return svc.get_metrics()
