"""Investigator Meeting Management API endpoints (INV-MTG).

Provides comprehensive investigator meeting operations: meeting planning,
attendance tracking, training session records, presentation materials
management, and action item tracking with meeting metrics.

Endpoints:
    GET    /investigator-meeting/meeting-plans                              - List meeting plans
    GET    /investigator-meeting/meeting-plans/{plan_id}                    - Get single plan
    POST   /investigator-meeting/meeting-plans                              - Create plan
    PUT    /investigator-meeting/meeting-plans/{plan_id}                    - Update plan
    DELETE /investigator-meeting/meeting-plans/{plan_id}                    - Delete plan
    GET    /investigator-meeting/attendance-records                          - List attendance records
    GET    /investigator-meeting/attendance-records/{record_id}             - Get single record
    POST   /investigator-meeting/attendance-records                          - Create record
    PUT    /investigator-meeting/attendance-records/{record_id}             - Update record
    DELETE /investigator-meeting/attendance-records/{record_id}             - Delete record
    GET    /investigator-meeting/training-sessions                           - List training sessions
    GET    /investigator-meeting/training-sessions/{session_id}             - Get single session
    POST   /investigator-meeting/training-sessions                           - Create session
    PUT    /investigator-meeting/training-sessions/{session_id}             - Update session
    DELETE /investigator-meeting/training-sessions/{session_id}             - Delete session
    GET    /investigator-meeting/presentation-materials                      - List materials
    GET    /investigator-meeting/presentation-materials/{material_id}       - Get single material
    POST   /investigator-meeting/presentation-materials                      - Create material
    PUT    /investigator-meeting/presentation-materials/{material_id}       - Update material
    DELETE /investigator-meeting/presentation-materials/{material_id}       - Delete material
    GET    /investigator-meeting/action-items                                - List action items
    GET    /investigator-meeting/action-items/{item_id}                     - Get single item
    POST   /investigator-meeting/action-items                                - Create item
    PUT    /investigator-meeting/action-items/{item_id}                     - Update item
    DELETE /investigator-meeting/action-items/{item_id}                     - Delete item
    GET    /investigator-meeting/metrics                                     - Meeting metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.investigator_meeting import (
    ActionItem,
    ActionItemCreate,
    ActionItemListResponse,
    ActionItemUpdate,
    ActionPriority,
    AttendanceRecord,
    AttendanceRecordCreate,
    AttendanceRecordListResponse,
    AttendanceRecordUpdate,
    AttendanceStatus,
    InvestigatorMeetingMetrics,
    MeetingFormat,
    MeetingPlan,
    MeetingPlanCreate,
    MeetingPlanListResponse,
    MeetingPlanUpdate,
    MeetingStatus,
    MeetingType,
    PresentationMaterial,
    PresentationMaterialCreate,
    PresentationMaterialListResponse,
    PresentationMaterialUpdate,
    TrainingSession,
    TrainingSessionCreate,
    TrainingSessionListResponse,
    TrainingSessionUpdate,
)
from app.services.investigator_meeting_service import get_investigator_meeting_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/investigator-meeting",
    tags=["Investigator Meeting"],
)


# ---------------------------------------------------------------------------
# Meeting Plans
# ---------------------------------------------------------------------------


@router.get(
    "/meeting-plans",
    response_model=MeetingPlanListResponse,
    summary="List meeting plans",
    description="Retrieve meeting plans with optional filtering by trial, type, status, and format.",
)
async def list_meeting_plans(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    meeting_type: Optional[MeetingType] = Query(None, description="Filter by meeting type"),
    status: Optional[MeetingStatus] = Query(None, description="Filter by meeting status"),
    meeting_format: Optional[MeetingFormat] = Query(None, description="Filter by meeting format"),
) -> MeetingPlanListResponse:
    svc = get_investigator_meeting_service()
    items = svc.list_meeting_plans(
        trial_id=trial_id, meeting_type=meeting_type, status=status, meeting_format=meeting_format
    )
    return MeetingPlanListResponse(items=items, total=len(items))


@router.get(
    "/meeting-plans/{plan_id}",
    response_model=MeetingPlan,
    summary="Get a meeting plan",
)
async def get_meeting_plan(plan_id: str) -> MeetingPlan:
    svc = get_investigator_meeting_service()
    plan = svc.get_meeting_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Meeting plan '{plan_id}' not found")
    return plan


@router.post(
    "/meeting-plans",
    response_model=MeetingPlan,
    status_code=201,
    summary="Create a meeting plan",
)
async def create_meeting_plan(payload: MeetingPlanCreate) -> MeetingPlan:
    svc = get_investigator_meeting_service()
    return svc.create_meeting_plan(payload)


@router.put(
    "/meeting-plans/{plan_id}",
    response_model=MeetingPlan,
    summary="Update a meeting plan",
)
async def update_meeting_plan(
    plan_id: str, payload: MeetingPlanUpdate
) -> MeetingPlan:
    svc = get_investigator_meeting_service()
    updated = svc.update_meeting_plan(plan_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Meeting plan '{plan_id}' not found")
    return updated


@router.delete(
    "/meeting-plans/{plan_id}",
    status_code=204,
    summary="Delete a meeting plan",
)
async def delete_meeting_plan(plan_id: str) -> None:
    svc = get_investigator_meeting_service()
    deleted = svc.delete_meeting_plan(plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Meeting plan '{plan_id}' not found")


# ---------------------------------------------------------------------------
# Attendance Records
# ---------------------------------------------------------------------------


@router.get(
    "/attendance-records",
    response_model=AttendanceRecordListResponse,
    summary="List attendance records",
    description="Retrieve attendance records with optional filtering by trial, meeting, and status.",
)
async def list_attendance_records(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    meeting_id: Optional[str] = Query(None, description="Filter by meeting ID"),
    attendance_status: Optional[AttendanceStatus] = Query(
        None, description="Filter by attendance status"
    ),
) -> AttendanceRecordListResponse:
    svc = get_investigator_meeting_service()
    items = svc.list_attendance_records(
        trial_id=trial_id, meeting_id=meeting_id, attendance_status=attendance_status
    )
    return AttendanceRecordListResponse(items=items, total=len(items))


@router.get(
    "/attendance-records/{record_id}",
    response_model=AttendanceRecord,
    summary="Get an attendance record",
)
async def get_attendance_record(record_id: str) -> AttendanceRecord:
    svc = get_investigator_meeting_service()
    record = svc.get_attendance_record(record_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Attendance record '{record_id}' not found"
        )
    return record


@router.post(
    "/attendance-records",
    response_model=AttendanceRecord,
    status_code=201,
    summary="Create an attendance record",
)
async def create_attendance_record(payload: AttendanceRecordCreate) -> AttendanceRecord:
    svc = get_investigator_meeting_service()
    return svc.create_attendance_record(payload)


@router.put(
    "/attendance-records/{record_id}",
    response_model=AttendanceRecord,
    summary="Update an attendance record",
)
async def update_attendance_record(
    record_id: str, payload: AttendanceRecordUpdate
) -> AttendanceRecord:
    svc = get_investigator_meeting_service()
    updated = svc.update_attendance_record(record_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Attendance record '{record_id}' not found"
        )
    return updated


@router.delete(
    "/attendance-records/{record_id}",
    status_code=204,
    summary="Delete an attendance record",
)
async def delete_attendance_record(record_id: str) -> None:
    svc = get_investigator_meeting_service()
    deleted = svc.delete_attendance_record(record_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Attendance record '{record_id}' not found"
        )


# ---------------------------------------------------------------------------
# Training Sessions
# ---------------------------------------------------------------------------


@router.get(
    "/training-sessions",
    response_model=TrainingSessionListResponse,
    summary="List training sessions",
    description="Retrieve training sessions with optional filtering by trial, meeting, and GCP training.",
)
async def list_training_sessions(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    meeting_id: Optional[str] = Query(None, description="Filter by meeting ID"),
    gcp_training: Optional[bool] = Query(None, description="Filter by GCP training flag"),
) -> TrainingSessionListResponse:
    svc = get_investigator_meeting_service()
    items = svc.list_training_sessions(
        trial_id=trial_id, meeting_id=meeting_id, gcp_training=gcp_training
    )
    return TrainingSessionListResponse(items=items, total=len(items))


@router.get(
    "/training-sessions/{session_id}",
    response_model=TrainingSession,
    summary="Get a training session",
)
async def get_training_session(session_id: str) -> TrainingSession:
    svc = get_investigator_meeting_service()
    session = svc.get_training_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=404, detail=f"Training session '{session_id}' not found"
        )
    return session


@router.post(
    "/training-sessions",
    response_model=TrainingSession,
    status_code=201,
    summary="Create a training session",
)
async def create_training_session(payload: TrainingSessionCreate) -> TrainingSession:
    svc = get_investigator_meeting_service()
    return svc.create_training_session(payload)


@router.put(
    "/training-sessions/{session_id}",
    response_model=TrainingSession,
    summary="Update a training session",
)
async def update_training_session(
    session_id: str, payload: TrainingSessionUpdate
) -> TrainingSession:
    svc = get_investigator_meeting_service()
    updated = svc.update_training_session(session_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Training session '{session_id}' not found"
        )
    return updated


@router.delete(
    "/training-sessions/{session_id}",
    status_code=204,
    summary="Delete a training session",
)
async def delete_training_session(session_id: str) -> None:
    svc = get_investigator_meeting_service()
    deleted = svc.delete_training_session(session_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Training session '{session_id}' not found"
        )


# ---------------------------------------------------------------------------
# Presentation Materials
# ---------------------------------------------------------------------------


@router.get(
    "/presentation-materials",
    response_model=PresentationMaterialListResponse,
    summary="List presentation materials",
    description="Retrieve presentation materials with optional filtering by trial, meeting, and approval status.",
)
async def list_presentation_materials(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    meeting_id: Optional[str] = Query(None, description="Filter by meeting ID"),
    approved_for_distribution: Optional[bool] = Query(
        None, description="Filter by approval status"
    ),
) -> PresentationMaterialListResponse:
    svc = get_investigator_meeting_service()
    items = svc.list_presentation_materials(
        trial_id=trial_id,
        meeting_id=meeting_id,
        approved_for_distribution=approved_for_distribution,
    )
    return PresentationMaterialListResponse(items=items, total=len(items))


@router.get(
    "/presentation-materials/{material_id}",
    response_model=PresentationMaterial,
    summary="Get a presentation material",
)
async def get_presentation_material(material_id: str) -> PresentationMaterial:
    svc = get_investigator_meeting_service()
    material = svc.get_presentation_material(material_id)
    if material is None:
        raise HTTPException(
            status_code=404,
            detail=f"Presentation material '{material_id}' not found",
        )
    return material


@router.post(
    "/presentation-materials",
    response_model=PresentationMaterial,
    status_code=201,
    summary="Create a presentation material",
)
async def create_presentation_material(
    payload: PresentationMaterialCreate,
) -> PresentationMaterial:
    svc = get_investigator_meeting_service()
    return svc.create_presentation_material(payload)


@router.put(
    "/presentation-materials/{material_id}",
    response_model=PresentationMaterial,
    summary="Update a presentation material",
)
async def update_presentation_material(
    material_id: str, payload: PresentationMaterialUpdate
) -> PresentationMaterial:
    svc = get_investigator_meeting_service()
    updated = svc.update_presentation_material(material_id, payload)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Presentation material '{material_id}' not found",
        )
    return updated


@router.delete(
    "/presentation-materials/{material_id}",
    status_code=204,
    summary="Delete a presentation material",
)
async def delete_presentation_material(material_id: str) -> None:
    svc = get_investigator_meeting_service()
    deleted = svc.delete_presentation_material(material_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Presentation material '{material_id}' not found",
        )


# ---------------------------------------------------------------------------
# Action Items
# ---------------------------------------------------------------------------


@router.get(
    "/action-items",
    response_model=ActionItemListResponse,
    summary="List action items",
    description="Retrieve action items with optional filtering by trial, meeting, priority, and status.",
)
async def list_action_items(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    meeting_id: Optional[str] = Query(None, description="Filter by meeting ID"),
    priority: Optional[ActionPriority] = Query(None, description="Filter by priority"),
    status: Optional[str] = Query(None, description="Filter by status"),
) -> ActionItemListResponse:
    svc = get_investigator_meeting_service()
    items = svc.list_action_items(
        trial_id=trial_id, meeting_id=meeting_id, priority=priority, status=status
    )
    return ActionItemListResponse(items=items, total=len(items))


@router.get(
    "/action-items/{item_id}",
    response_model=ActionItem,
    summary="Get an action item",
)
async def get_action_item(item_id: str) -> ActionItem:
    svc = get_investigator_meeting_service()
    item = svc.get_action_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Action item '{item_id}' not found")
    return item


@router.post(
    "/action-items",
    response_model=ActionItem,
    status_code=201,
    summary="Create an action item",
)
async def create_action_item(payload: ActionItemCreate) -> ActionItem:
    svc = get_investigator_meeting_service()
    return svc.create_action_item(payload)


@router.put(
    "/action-items/{item_id}",
    response_model=ActionItem,
    summary="Update an action item",
)
async def update_action_item(
    item_id: str, payload: ActionItemUpdate
) -> ActionItem:
    svc = get_investigator_meeting_service()
    updated = svc.update_action_item(item_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Action item '{item_id}' not found")
    return updated


@router.delete(
    "/action-items/{item_id}",
    status_code=204,
    summary="Delete an action item",
)
async def delete_action_item(item_id: str) -> None:
    svc = get_investigator_meeting_service()
    deleted = svc.delete_action_item(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Action item '{item_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=InvestigatorMeetingMetrics,
    summary="Get investigator meeting metrics",
    description="Aggregated metrics across all investigator meeting operations.",
)
async def get_metrics() -> InvestigatorMeetingMetrics:
    svc = get_investigator_meeting_service()
    return svc.get_metrics()
