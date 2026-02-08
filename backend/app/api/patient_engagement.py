"""Patient Engagement and Communication Tracking API endpoints.

Provides communication recording, template management, campaign tracking,
patient preference management, engagement scoring, and analytics for the
clinical trial recruitment platform.

Endpoints:
    POST /api/v1/engagement/communications           - Record communication
    GET  /api/v1/engagement/communications            - List communications
    GET  /api/v1/engagement/communications/{id}       - Communication detail
    PUT  /api/v1/engagement/communications/{id}       - Update status
    GET  /api/v1/engagement/templates                 - List templates
    GET  /api/v1/engagement/patients/{id}/score       - Engagement score
    GET  /api/v1/engagement/patients/{id}/preferences - Get preferences
    PUT  /api/v1/engagement/patients/{id}/preferences - Update preferences
    GET  /api/v1/engagement/analytics                 - Analytics
    POST /api/v1/engagement/campaigns                 - Create campaign
    GET  /api/v1/engagement/campaigns                 - List campaigns
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.patient_engagement import (
    Campaign,
    CampaignCreateRequest,
    CampaignListResponse,
    CampaignStatus,
    ChannelEffectiveness,
    CommunicationChannel,
    CommunicationCreateRequest,
    CommunicationDirection,
    CommunicationListResponse,
    CommunicationRecord,
    CommunicationStatus,
    CommunicationTemplate,
    CommunicationUpdateRequest,
    EngagementAnalytics,
    EngagementScore,
    PatientPreferences,
    PreferencesUpdateRequest,
    TemplateType,
)
from app.services.patient_engagement_service import (
    get_patient_engagement_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/engagement",
    tags=["Patient Engagement"],
)


# ==============================================================================
# Communications
# ==============================================================================


@router.post(
    "/communications",
    response_model=CommunicationRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Record a communication",
    description=(
        "Record a new patient communication event. No PHI should be "
        "stored in the content_summary field -- only metadata and "
        "non-identifying summaries."
    ),
)
async def record_communication(
    request: CommunicationCreateRequest,
) -> CommunicationRecord:
    """Record a new patient communication."""
    svc = get_patient_engagement_service()
    return svc.record_communication(request)


@router.get(
    "/communications",
    response_model=CommunicationListResponse,
    summary="List communications",
    description=(
        "List communication records with optional filters by patient, "
        "trial, channel, status, campaign, and direction."
    ),
)
async def list_communications(
    patient_id: str | None = Query(None, description="Filter by patient"),
    trial_id: str | None = Query(None, description="Filter by trial"),
    channel: CommunicationChannel | None = Query(
        None, description="Filter by channel"
    ),
    comm_status: CommunicationStatus | None = Query(
        None, alias="status", description="Filter by status"
    ),
    campaign_id: str | None = Query(None, description="Filter by campaign"),
    direction: CommunicationDirection | None = Query(
        None, description="Filter by direction"
    ),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Results offset"),
) -> CommunicationListResponse:
    """List communications with filters."""
    svc = get_patient_engagement_service()
    return svc.list_communications(
        patient_id=patient_id,
        trial_id=trial_id,
        channel=channel,
        status=comm_status,
        campaign_id=campaign_id,
        direction=direction,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/communications/{comm_id}",
    response_model=CommunicationRecord,
    summary="Get communication detail",
    description="Retrieve a single communication record by ID.",
)
async def get_communication(comm_id: str) -> CommunicationRecord:
    """Get a communication by ID."""
    svc = get_patient_engagement_service()
    record = svc.get_communication(comm_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Communication not found: {comm_id}",
        )
    return record


@router.put(
    "/communications/{comm_id}",
    response_model=CommunicationRecord,
    summary="Update communication status",
    description=(
        "Update the delivery/engagement status of a communication. "
        "Timestamps are automatically set based on the new status."
    ),
)
async def update_communication(
    comm_id: str,
    request: CommunicationUpdateRequest,
) -> CommunicationRecord:
    """Update a communication's status."""
    svc = get_patient_engagement_service()
    try:
        return svc.update_communication_status(comm_id, request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


# ==============================================================================
# Templates
# ==============================================================================


@router.get(
    "/templates",
    response_model=list[CommunicationTemplate],
    summary="List communication templates",
    description=(
        "List available communication templates with optional filters "
        "by template type and channel."
    ),
)
async def list_templates(
    template_type: TemplateType | None = Query(
        None, description="Filter by template type"
    ),
    channel: CommunicationChannel | None = Query(
        None, description="Filter by channel"
    ),
    active_only: bool = Query(True, description="Only active templates"),
) -> list[CommunicationTemplate]:
    """List communication templates."""
    svc = get_patient_engagement_service()
    return svc.list_templates(
        template_type=template_type,
        channel=channel,
        active_only=active_only,
    )


# ==============================================================================
# Engagement scoring
# ==============================================================================


@router.get(
    "/patients/{patient_id}/score",
    response_model=EngagementScore,
    summary="Get patient engagement score",
    description=(
        "Calculate and return the engagement score for a patient based on "
        "response rate, response time, appointment adherence, and "
        "communication channel preference satisfaction."
    ),
)
async def get_engagement_score(patient_id: str) -> EngagementScore:
    """Get the engagement score for a patient."""
    svc = get_patient_engagement_service()
    return svc.get_engagement_score(patient_id)


# ==============================================================================
# Patient preferences
# ==============================================================================


@router.get(
    "/patients/{patient_id}/preferences",
    response_model=PatientPreferences,
    summary="Get communication preferences",
    description=(
        "Get the communication preferences for a patient, including "
        "preferred channel, frequency limits, and opt-out status."
    ),
)
async def get_preferences(patient_id: str) -> PatientPreferences:
    """Get communication preferences for a patient."""
    svc = get_patient_engagement_service()
    return svc.get_preferences(patient_id)


@router.put(
    "/patients/{patient_id}/preferences",
    response_model=PatientPreferences,
    summary="Update communication preferences",
    description=(
        "Update the communication preferences for a patient. Only "
        "provided fields are updated; others remain unchanged."
    ),
)
async def update_preferences(
    patient_id: str,
    request: PreferencesUpdateRequest,
) -> PatientPreferences:
    """Update communication preferences for a patient."""
    svc = get_patient_engagement_service()
    return svc.update_preferences(patient_id, request)


# ==============================================================================
# Analytics
# ==============================================================================


@router.get(
    "/analytics",
    response_model=EngagementAnalytics,
    summary="Get engagement analytics",
    description=(
        "Get comprehensive engagement analytics including channel "
        "effectiveness, template performance, best send times, "
        "and engagement funnel metrics."
    ),
)
async def get_analytics(
    trial_id: str | None = Query(None, description="Filter by trial"),
) -> EngagementAnalytics:
    """Get engagement analytics."""
    svc = get_patient_engagement_service()
    return svc.get_analytics(trial_id=trial_id)


# ==============================================================================
# Campaigns
# ==============================================================================


@router.post(
    "/campaigns",
    response_model=Campaign,
    status_code=status.HTTP_201_CREATED,
    summary="Create a campaign",
    description=(
        "Create a new communication campaign for grouped messaging. "
        "Campaigns start in DRAFT status."
    ),
)
async def create_campaign(
    request: CampaignCreateRequest,
) -> Campaign:
    """Create a new communication campaign."""
    svc = get_patient_engagement_service()
    return svc.create_campaign(request)


@router.get(
    "/campaigns",
    response_model=CampaignListResponse,
    summary="List campaigns",
    description="List communication campaigns with optional filters.",
)
async def list_campaigns(
    trial_id: str | None = Query(None, description="Filter by trial"),
    campaign_status: CampaignStatus | None = Query(
        None, alias="status", description="Filter by status"
    ),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Results offset"),
) -> CampaignListResponse:
    """List campaigns with filters."""
    svc = get_patient_engagement_service()
    return svc.list_campaigns(
        trial_id=trial_id,
        status=campaign_status,
        limit=limit,
        offset=offset,
    )
