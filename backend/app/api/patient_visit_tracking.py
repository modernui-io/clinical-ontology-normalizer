"""Patient Visit Tracking API endpoints (PVT-TRK).

Provides comprehensive patient visit tracking operations: visit schedules,
visit adherence records, visit window violations, missed visit follow-ups,
and visit tracking metrics.

Endpoints:
    GET    /patient-visit-tracking/visit-schedules                            - List visit schedules
    GET    /patient-visit-tracking/visit-schedules/{schedule_id}              - Get single schedule
    POST   /patient-visit-tracking/visit-schedules                            - Create schedule
    PUT    /patient-visit-tracking/visit-schedules/{schedule_id}              - Update schedule
    DELETE /patient-visit-tracking/visit-schedules/{schedule_id}              - Delete schedule
    GET    /patient-visit-tracking/visit-adherence                            - List adherence records
    GET    /patient-visit-tracking/visit-adherence/{adherence_id}             - Get single adherence
    POST   /patient-visit-tracking/visit-adherence                            - Create adherence
    PUT    /patient-visit-tracking/visit-adherence/{adherence_id}             - Update adherence
    DELETE /patient-visit-tracking/visit-adherence/{adherence_id}             - Delete adherence
    GET    /patient-visit-tracking/window-violations                          - List violations
    GET    /patient-visit-tracking/window-violations/{violation_id}           - Get single violation
    POST   /patient-visit-tracking/window-violations                          - Create violation
    PUT    /patient-visit-tracking/window-violations/{violation_id}           - Update violation
    DELETE /patient-visit-tracking/window-violations/{violation_id}           - Delete violation
    GET    /patient-visit-tracking/missed-visit-follow-ups                    - List follow-ups
    GET    /patient-visit-tracking/missed-visit-follow-ups/{follow_up_id}     - Get single follow-up
    POST   /patient-visit-tracking/missed-visit-follow-ups                    - Create follow-up
    PUT    /patient-visit-tracking/missed-visit-follow-ups/{follow_up_id}     - Update follow-up
    DELETE /patient-visit-tracking/missed-visit-follow-ups/{follow_up_id}     - Delete follow-up
    GET    /patient-visit-tracking/metrics                                    - Visit tracking metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.patient_visit_tracking import (
    AdherenceRating,
    FollowUpStatus,
    MissedVisitFollowUp,
    MissedVisitFollowUpCreate,
    MissedVisitFollowUpListResponse,
    MissedVisitFollowUpUpdate,
    PatientVisitTrackingMetrics,
    ViolationSeverity,
    VisitAdherence,
    VisitAdherenceCreate,
    VisitAdherenceListResponse,
    VisitAdherenceUpdate,
    VisitSchedule,
    VisitScheduleCreate,
    VisitScheduleListResponse,
    VisitScheduleUpdate,
    VisitStatus,
    VisitType,
    WindowViolation,
    WindowViolationCreate,
    WindowViolationListResponse,
    WindowViolationUpdate,
)
from app.services.patient_visit_tracking_service import get_patient_visit_tracking_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/patient-visit-tracking",
    tags=["Patient Visit Tracking"],
)


# ---------------------------------------------------------------------------
# Visit Schedules
# ---------------------------------------------------------------------------


@router.get(
    "/visit-schedules",
    response_model=VisitScheduleListResponse,
    summary="List visit schedules",
    description="Retrieve visit schedules with optional filtering by trial, visit type, visit status, and site.",
)
async def list_visit_schedules(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    visit_type: Optional[VisitType] = Query(None, description="Filter by visit type"),
    visit_status: Optional[VisitStatus] = Query(None, description="Filter by visit status"),
    site_id: Optional[str] = Query(None, description="Filter by site ID"),
) -> VisitScheduleListResponse:
    svc = get_patient_visit_tracking_service()
    items = svc.list_visit_schedules(
        trial_id=trial_id, visit_type=visit_type, visit_status=visit_status, site_id=site_id
    )
    return VisitScheduleListResponse(items=items, total=len(items))


@router.get(
    "/visit-schedules/{schedule_id}",
    response_model=VisitSchedule,
    summary="Get a visit schedule",
)
async def get_visit_schedule(schedule_id: str) -> VisitSchedule:
    svc = get_patient_visit_tracking_service()
    record = svc.get_visit_schedule(schedule_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Visit schedule '{schedule_id}' not found")
    return record


@router.post(
    "/visit-schedules",
    response_model=VisitSchedule,
    status_code=201,
    summary="Create a visit schedule",
)
async def create_visit_schedule(payload: VisitScheduleCreate) -> VisitSchedule:
    svc = get_patient_visit_tracking_service()
    return svc.create_visit_schedule(payload)


@router.put(
    "/visit-schedules/{schedule_id}",
    response_model=VisitSchedule,
    summary="Update a visit schedule",
)
async def update_visit_schedule(
    schedule_id: str, payload: VisitScheduleUpdate
) -> VisitSchedule:
    svc = get_patient_visit_tracking_service()
    updated = svc.update_visit_schedule(schedule_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Visit schedule '{schedule_id}' not found")
    return updated


@router.delete(
    "/visit-schedules/{schedule_id}",
    status_code=204,
    summary="Delete a visit schedule",
)
async def delete_visit_schedule(schedule_id: str) -> None:
    svc = get_patient_visit_tracking_service()
    deleted = svc.delete_visit_schedule(schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Visit schedule '{schedule_id}' not found")


# ---------------------------------------------------------------------------
# Visit Adherence
# ---------------------------------------------------------------------------


@router.get(
    "/visit-adherence",
    response_model=VisitAdherenceListResponse,
    summary="List visit adherence records",
    description="Retrieve visit adherence records with optional filtering by trial, adherence rating, and subject.",
)
async def list_visit_adherence(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    adherence_rating: Optional[AdherenceRating] = Query(None, description="Filter by adherence rating"),
    subject_id: Optional[str] = Query(None, description="Filter by subject ID"),
) -> VisitAdherenceListResponse:
    svc = get_patient_visit_tracking_service()
    items = svc.list_visit_adherence(
        trial_id=trial_id, adherence_rating=adherence_rating, subject_id=subject_id
    )
    return VisitAdherenceListResponse(items=items, total=len(items))


@router.get(
    "/visit-adherence/{adherence_id}",
    response_model=VisitAdherence,
    summary="Get a visit adherence record",
)
async def get_visit_adherence(adherence_id: str) -> VisitAdherence:
    svc = get_patient_visit_tracking_service()
    record = svc.get_visit_adherence(adherence_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Visit adherence '{adherence_id}' not found"
        )
    return record


@router.post(
    "/visit-adherence",
    response_model=VisitAdherence,
    status_code=201,
    summary="Create a visit adherence record",
)
async def create_visit_adherence(payload: VisitAdherenceCreate) -> VisitAdherence:
    svc = get_patient_visit_tracking_service()
    return svc.create_visit_adherence(payload)


@router.put(
    "/visit-adherence/{adherence_id}",
    response_model=VisitAdherence,
    summary="Update a visit adherence record",
)
async def update_visit_adherence(
    adherence_id: str, payload: VisitAdherenceUpdate
) -> VisitAdherence:
    svc = get_patient_visit_tracking_service()
    updated = svc.update_visit_adherence(adherence_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Visit adherence '{adherence_id}' not found"
        )
    return updated


@router.delete(
    "/visit-adherence/{adherence_id}",
    status_code=204,
    summary="Delete a visit adherence record",
)
async def delete_visit_adherence(adherence_id: str) -> None:
    svc = get_patient_visit_tracking_service()
    deleted = svc.delete_visit_adherence(adherence_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Visit adherence '{adherence_id}' not found"
        )


# ---------------------------------------------------------------------------
# Window Violations
# ---------------------------------------------------------------------------


@router.get(
    "/window-violations",
    response_model=WindowViolationListResponse,
    summary="List window violations",
    description="Retrieve window violations with optional filtering by trial and violation severity.",
)
async def list_window_violations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    violation_severity: Optional[ViolationSeverity] = Query(None, description="Filter by violation severity"),
) -> WindowViolationListResponse:
    svc = get_patient_visit_tracking_service()
    items = svc.list_window_violations(
        trial_id=trial_id, violation_severity=violation_severity
    )
    return WindowViolationListResponse(items=items, total=len(items))


@router.get(
    "/window-violations/{violation_id}",
    response_model=WindowViolation,
    summary="Get a window violation",
)
async def get_window_violation(violation_id: str) -> WindowViolation:
    svc = get_patient_visit_tracking_service()
    record = svc.get_window_violation(violation_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Window violation '{violation_id}' not found"
        )
    return record


@router.post(
    "/window-violations",
    response_model=WindowViolation,
    status_code=201,
    summary="Create a window violation",
)
async def create_window_violation(payload: WindowViolationCreate) -> WindowViolation:
    svc = get_patient_visit_tracking_service()
    return svc.create_window_violation(payload)


@router.put(
    "/window-violations/{violation_id}",
    response_model=WindowViolation,
    summary="Update a window violation",
)
async def update_window_violation(
    violation_id: str, payload: WindowViolationUpdate
) -> WindowViolation:
    svc = get_patient_visit_tracking_service()
    updated = svc.update_window_violation(violation_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Window violation '{violation_id}' not found"
        )
    return updated


@router.delete(
    "/window-violations/{violation_id}",
    status_code=204,
    summary="Delete a window violation",
)
async def delete_window_violation(violation_id: str) -> None:
    svc = get_patient_visit_tracking_service()
    deleted = svc.delete_window_violation(violation_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Window violation '{violation_id}' not found"
        )


# ---------------------------------------------------------------------------
# Missed Visit Follow-Ups
# ---------------------------------------------------------------------------


@router.get(
    "/missed-visit-follow-ups",
    response_model=MissedVisitFollowUpListResponse,
    summary="List missed visit follow-ups",
    description="Retrieve missed visit follow-ups with optional filtering by trial and follow-up status.",
)
async def list_missed_visit_follow_ups(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    follow_up_status: Optional[FollowUpStatus] = Query(None, description="Filter by follow-up status"),
) -> MissedVisitFollowUpListResponse:
    svc = get_patient_visit_tracking_service()
    items = svc.list_missed_visit_follow_ups(
        trial_id=trial_id, follow_up_status=follow_up_status
    )
    return MissedVisitFollowUpListResponse(items=items, total=len(items))


@router.get(
    "/missed-visit-follow-ups/{follow_up_id}",
    response_model=MissedVisitFollowUp,
    summary="Get a missed visit follow-up",
)
async def get_missed_visit_follow_up(follow_up_id: str) -> MissedVisitFollowUp:
    svc = get_patient_visit_tracking_service()
    record = svc.get_missed_visit_follow_up(follow_up_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Missed visit follow-up '{follow_up_id}' not found"
        )
    return record


@router.post(
    "/missed-visit-follow-ups",
    response_model=MissedVisitFollowUp,
    status_code=201,
    summary="Create a missed visit follow-up",
)
async def create_missed_visit_follow_up(
    payload: MissedVisitFollowUpCreate,
) -> MissedVisitFollowUp:
    svc = get_patient_visit_tracking_service()
    return svc.create_missed_visit_follow_up(payload)


@router.put(
    "/missed-visit-follow-ups/{follow_up_id}",
    response_model=MissedVisitFollowUp,
    summary="Update a missed visit follow-up",
)
async def update_missed_visit_follow_up(
    follow_up_id: str, payload: MissedVisitFollowUpUpdate
) -> MissedVisitFollowUp:
    svc = get_patient_visit_tracking_service()
    updated = svc.update_missed_visit_follow_up(follow_up_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Missed visit follow-up '{follow_up_id}' not found"
        )
    return updated


@router.delete(
    "/missed-visit-follow-ups/{follow_up_id}",
    status_code=204,
    summary="Delete a missed visit follow-up",
)
async def delete_missed_visit_follow_up(follow_up_id: str) -> None:
    svc = get_patient_visit_tracking_service()
    deleted = svc.delete_missed_visit_follow_up(follow_up_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Missed visit follow-up '{follow_up_id}' not found"
        )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=PatientVisitTrackingMetrics,
    summary="Get patient visit tracking metrics",
    description="Aggregated metrics across all patient visit tracking operations.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> PatientVisitTrackingMetrics:
    svc = get_patient_visit_tracking_service()
    return svc.get_metrics(trial_id=trial_id)
