"""Health Authority Meeting Tracker (HA-MEET) API endpoints.

Provides comprehensive HA meeting operations: meeting management, briefing
document preparation, meeting minutes, action item tracking, commitment
management, and operational metrics.

Endpoints:
    GET    /ha-meeting-tracker/meetings                       - List meetings
    GET    /ha-meeting-tracker/meetings/{meeting_id}          - Get single meeting
    POST   /ha-meeting-tracker/meetings                       - Create meeting
    PUT    /ha-meeting-tracker/meetings/{meeting_id}          - Update meeting
    DELETE /ha-meeting-tracker/meetings/{meeting_id}          - Delete meeting
    GET    /ha-meeting-tracker/briefing-docs                  - List briefing documents
    GET    /ha-meeting-tracker/briefing-docs/{doc_id}         - Get single briefing doc
    POST   /ha-meeting-tracker/briefing-docs                  - Create briefing doc
    PUT    /ha-meeting-tracker/briefing-docs/{doc_id}         - Update briefing doc
    DELETE /ha-meeting-tracker/briefing-docs/{doc_id}         - Delete briefing doc
    GET    /ha-meeting-tracker/minutes                        - List meeting minutes
    GET    /ha-meeting-tracker/minutes/{minutes_id}           - Get single minutes
    POST   /ha-meeting-tracker/minutes                        - Create minutes
    PUT    /ha-meeting-tracker/minutes/{minutes_id}           - Update minutes
    DELETE /ha-meeting-tracker/minutes/{minutes_id}           - Delete minutes
    GET    /ha-meeting-tracker/action-items                   - List action items
    GET    /ha-meeting-tracker/action-items/{item_id}         - Get single action item
    POST   /ha-meeting-tracker/action-items                   - Create action item
    PUT    /ha-meeting-tracker/action-items/{item_id}         - Update action item
    DELETE /ha-meeting-tracker/action-items/{item_id}         - Delete action item
    GET    /ha-meeting-tracker/commitments                    - List commitments
    GET    /ha-meeting-tracker/commitments/{commitment_id}    - Get single commitment
    POST   /ha-meeting-tracker/commitments                    - Create commitment
    PUT    /ha-meeting-tracker/commitments/{commitment_id}    - Update commitment
    DELETE /ha-meeting-tracker/commitments/{commitment_id}    - Delete commitment
    GET    /ha-meeting-tracker/metrics                        - HA meeting metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.ha_meeting_tracker import (
    BriefingDocument,
    BriefingDocumentCreate,
    BriefingDocumentListResponse,
    BriefingDocumentUpdate,
    HACommitment,
    HACommitmentCreate,
    HACommitmentListResponse,
    HACommitmentUpdate,
    HAMeeting,
    HAMeetingCreate,
    HAMeetingListResponse,
    HAMeetingMetrics,
    HAMeetingUpdate,
    MeetingActionItem,
    MeetingActionItemCreate,
    MeetingActionItemListResponse,
    MeetingActionItemUpdate,
    MeetingMinutes,
    MeetingMinutesCreate,
    MeetingMinutesListResponse,
    MeetingMinutesUpdate,
)
from app.services.ha_meeting_tracker_service import get_ha_meeting_tracker_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ha-meeting-tracker",
    tags=["Health Authority Meeting Tracker"],
)


# ---------------------------------------------------------------------------
# Meeting Management
# ---------------------------------------------------------------------------


@router.get(
    "/meetings",
    response_model=HAMeetingListResponse,
    summary="List HA meetings",
    description="Retrieve HA meetings with optional filtering by trial.",
)
async def list_meetings(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> HAMeetingListResponse:
    svc = get_ha_meeting_tracker_service()
    items = svc.list_meetings(trial_id=trial_id)
    return HAMeetingListResponse(items=items, total=len(items))


@router.get(
    "/meetings/{meeting_id}",
    response_model=HAMeeting,
    summary="Get an HA meeting",
)
async def get_meeting(meeting_id: str) -> HAMeeting:
    svc = get_ha_meeting_tracker_service()
    meeting = svc.get_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail=f"Meeting '{meeting_id}' not found")
    return meeting


@router.post(
    "/meetings",
    response_model=HAMeeting,
    status_code=201,
    summary="Create an HA meeting",
)
async def create_meeting(payload: HAMeetingCreate) -> HAMeeting:
    svc = get_ha_meeting_tracker_service()
    return svc.create_meeting(payload)


@router.put(
    "/meetings/{meeting_id}",
    response_model=HAMeeting,
    summary="Update an HA meeting",
)
async def update_meeting(
    meeting_id: str, payload: HAMeetingUpdate
) -> HAMeeting:
    svc = get_ha_meeting_tracker_service()
    updated = svc.update_meeting(meeting_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Meeting '{meeting_id}' not found")
    return updated


@router.delete(
    "/meetings/{meeting_id}",
    status_code=204,
    summary="Delete an HA meeting",
)
async def delete_meeting(meeting_id: str) -> None:
    svc = get_ha_meeting_tracker_service()
    deleted = svc.delete_meeting(meeting_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Meeting '{meeting_id}' not found")


# ---------------------------------------------------------------------------
# Briefing Document Management
# ---------------------------------------------------------------------------


@router.get(
    "/briefing-docs",
    response_model=BriefingDocumentListResponse,
    summary="List briefing documents",
    description="Retrieve briefing documents with optional filtering by meeting.",
)
async def list_briefing_docs(
    meeting_id: Optional[str] = Query(None, description="Filter by meeting ID"),
) -> BriefingDocumentListResponse:
    svc = get_ha_meeting_tracker_service()
    items = svc.list_briefing_docs(meeting_id=meeting_id)
    return BriefingDocumentListResponse(items=items, total=len(items))


@router.get(
    "/briefing-docs/{doc_id}",
    response_model=BriefingDocument,
    summary="Get a briefing document",
)
async def get_briefing_doc(doc_id: str) -> BriefingDocument:
    svc = get_ha_meeting_tracker_service()
    doc = svc.get_briefing_doc(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Briefing document '{doc_id}' not found")
    return doc


@router.post(
    "/briefing-docs",
    response_model=BriefingDocument,
    status_code=201,
    summary="Create a briefing document",
)
async def create_briefing_doc(payload: BriefingDocumentCreate) -> BriefingDocument:
    svc = get_ha_meeting_tracker_service()
    return svc.create_briefing_doc(payload)


@router.put(
    "/briefing-docs/{doc_id}",
    response_model=BriefingDocument,
    summary="Update a briefing document",
)
async def update_briefing_doc(
    doc_id: str, payload: BriefingDocumentUpdate
) -> BriefingDocument:
    svc = get_ha_meeting_tracker_service()
    updated = svc.update_briefing_doc(doc_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Briefing document '{doc_id}' not found")
    return updated


@router.delete(
    "/briefing-docs/{doc_id}",
    status_code=204,
    summary="Delete a briefing document",
)
async def delete_briefing_doc(doc_id: str) -> None:
    svc = get_ha_meeting_tracker_service()
    deleted = svc.delete_briefing_doc(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Briefing document '{doc_id}' not found")


# ---------------------------------------------------------------------------
# Meeting Minutes Management
# ---------------------------------------------------------------------------


@router.get(
    "/minutes",
    response_model=MeetingMinutesListResponse,
    summary="List meeting minutes",
    description="Retrieve meeting minutes with optional filtering by meeting.",
)
async def list_minutes(
    meeting_id: Optional[str] = Query(None, description="Filter by meeting ID"),
) -> MeetingMinutesListResponse:
    svc = get_ha_meeting_tracker_service()
    items = svc.list_minutes(meeting_id=meeting_id)
    return MeetingMinutesListResponse(items=items, total=len(items))


@router.get(
    "/minutes/{minutes_id}",
    response_model=MeetingMinutes,
    summary="Get meeting minutes",
)
async def get_minutes(minutes_id: str) -> MeetingMinutes:
    svc = get_ha_meeting_tracker_service()
    minutes = svc.get_minutes(minutes_id)
    if minutes is None:
        raise HTTPException(status_code=404, detail=f"Meeting minutes '{minutes_id}' not found")
    return minutes


@router.post(
    "/minutes",
    response_model=MeetingMinutes,
    status_code=201,
    summary="Create meeting minutes",
)
async def create_minutes(payload: MeetingMinutesCreate) -> MeetingMinutes:
    svc = get_ha_meeting_tracker_service()
    return svc.create_minutes(payload)


@router.put(
    "/minutes/{minutes_id}",
    response_model=MeetingMinutes,
    summary="Update meeting minutes",
)
async def update_minutes(
    minutes_id: str, payload: MeetingMinutesUpdate
) -> MeetingMinutes:
    svc = get_ha_meeting_tracker_service()
    updated = svc.update_minutes(minutes_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Meeting minutes '{minutes_id}' not found")
    return updated


@router.delete(
    "/minutes/{minutes_id}",
    status_code=204,
    summary="Delete meeting minutes",
)
async def delete_minutes(minutes_id: str) -> None:
    svc = get_ha_meeting_tracker_service()
    deleted = svc.delete_minutes(minutes_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Meeting minutes '{minutes_id}' not found")


# ---------------------------------------------------------------------------
# Action Item Management
# ---------------------------------------------------------------------------


@router.get(
    "/action-items",
    response_model=MeetingActionItemListResponse,
    summary="List action items",
    description="Retrieve action items with optional filtering by meeting.",
)
async def list_action_items(
    meeting_id: Optional[str] = Query(None, description="Filter by meeting ID"),
) -> MeetingActionItemListResponse:
    svc = get_ha_meeting_tracker_service()
    items = svc.list_action_items(meeting_id=meeting_id)
    return MeetingActionItemListResponse(items=items, total=len(items))


@router.get(
    "/action-items/{item_id}",
    response_model=MeetingActionItem,
    summary="Get an action item",
)
async def get_action_item(item_id: str) -> MeetingActionItem:
    svc = get_ha_meeting_tracker_service()
    item = svc.get_action_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Action item '{item_id}' not found")
    return item


@router.post(
    "/action-items",
    response_model=MeetingActionItem,
    status_code=201,
    summary="Create an action item",
)
async def create_action_item(payload: MeetingActionItemCreate) -> MeetingActionItem:
    svc = get_ha_meeting_tracker_service()
    return svc.create_action_item(payload)


@router.put(
    "/action-items/{item_id}",
    response_model=MeetingActionItem,
    summary="Update an action item",
)
async def update_action_item(
    item_id: str, payload: MeetingActionItemUpdate
) -> MeetingActionItem:
    svc = get_ha_meeting_tracker_service()
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
    svc = get_ha_meeting_tracker_service()
    deleted = svc.delete_action_item(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Action item '{item_id}' not found")


# ---------------------------------------------------------------------------
# Commitment Management
# ---------------------------------------------------------------------------


@router.get(
    "/commitments",
    response_model=HACommitmentListResponse,
    summary="List HA commitments",
    description="Retrieve HA commitments with optional filtering by trial.",
)
async def list_commitments(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> HACommitmentListResponse:
    svc = get_ha_meeting_tracker_service()
    items = svc.list_commitments(trial_id=trial_id)
    return HACommitmentListResponse(items=items, total=len(items))


@router.get(
    "/commitments/{commitment_id}",
    response_model=HACommitment,
    summary="Get an HA commitment",
)
async def get_commitment(commitment_id: str) -> HACommitment:
    svc = get_ha_meeting_tracker_service()
    commitment = svc.get_commitment(commitment_id)
    if commitment is None:
        raise HTTPException(status_code=404, detail=f"Commitment '{commitment_id}' not found")
    return commitment


@router.post(
    "/commitments",
    response_model=HACommitment,
    status_code=201,
    summary="Create an HA commitment",
)
async def create_commitment(payload: HACommitmentCreate) -> HACommitment:
    svc = get_ha_meeting_tracker_service()
    return svc.create_commitment(payload)


@router.put(
    "/commitments/{commitment_id}",
    response_model=HACommitment,
    summary="Update an HA commitment",
)
async def update_commitment(
    commitment_id: str, payload: HACommitmentUpdate
) -> HACommitment:
    svc = get_ha_meeting_tracker_service()
    updated = svc.update_commitment(commitment_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Commitment '{commitment_id}' not found")
    return updated


@router.delete(
    "/commitments/{commitment_id}",
    status_code=204,
    summary="Delete an HA commitment",
)
async def delete_commitment(commitment_id: str) -> None:
    svc = get_ha_meeting_tracker_service()
    deleted = svc.delete_commitment(commitment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Commitment '{commitment_id}' not found")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=HAMeetingMetrics,
    summary="Get HA meeting metrics",
    description="Aggregated HA meeting metrics including meeting counts by type/status/authority, "
                "briefing document status, action item tracking, and commitment status.",
)
async def get_metrics(
    trial_id: Optional[str] = Query(None, description="Filter metrics by trial ID"),
) -> HAMeetingMetrics:
    svc = get_ha_meeting_tracker_service()
    return svc.get_metrics(trial_id=trial_id)
