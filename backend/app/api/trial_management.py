"""Trial Management Office (TMO) & Multi-Site Coordination API endpoints (CLINICAL-10).

Provides comprehensive TMO operations: site activation tracking with status
transition validation, site blocker management with auto-escalation, country
regulatory status tracking, trial milestones with critical path analysis and
Gantt chart data, site communications with acknowledgment tracking, cross-trial
resource allocation and utilization reporting, enrollment forecasting, and
TMO dashboard aggregation.

Endpoints:
    GET    /trial-management/sites                                    - List site activations
    GET    /trial-management/sites/{site_id}                          - Get site activation detail
    PUT    /trial-management/sites/{site_id}/status                   - Update site activation status
    GET    /trial-management/sites/delayed                            - List delayed site activations
    POST   /trial-management/sites/{site_id}/blockers                 - Raise a site blocker
    GET    /trial-management/blockers                                 - List blockers
    GET    /trial-management/blockers/{blocker_id}                    - Get a single blocker
    POST   /trial-management/blockers/{blocker_id}/resolve            - Resolve a blocker
    POST   /trial-management/blockers/auto-escalate                   - Auto-escalate open blockers
    GET    /trial-management/countries                                - List country regulatory records
    GET    /trial-management/countries/{country_id}                   - Get country regulatory detail
    PUT    /trial-management/countries/{country_id}/status             - Update country regulatory status
    GET    /trial-management/milestones                               - List milestones
    GET    /trial-management/milestones/{milestone_id}                - Get a milestone
    POST   /trial-management/milestones                               - Create a milestone
    PUT    /trial-management/milestones/{milestone_id}                - Update a milestone
    GET    /trial-management/milestones/critical-path/{trial_id}      - Critical path analysis
    GET    /trial-management/milestones/gantt/{trial_id}              - Gantt chart data
    GET    /trial-management/communications                           - List communications
    GET    /trial-management/communications/{comm_id}                 - Get a communication
    POST   /trial-management/communications                           - Send a communication
    POST   /trial-management/communications/{comm_id}/acknowledge     - Acknowledge a communication
    GET    /trial-management/dashboard/{trial_id}                     - TMO dashboard
    GET    /trial-management/enrollment-projections                   - Enrollment projections
    GET    /trial-management/resources                                - List cross-trial resources
    GET    /trial-management/resources/{resource_id}                  - Get a resource
    POST   /trial-management/resources                                - Add a cross-trial resource
    GET    /trial-management/resources/utilization                    - Resource utilization report
    GET    /trial-management/stats                                    - Service statistics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.trial_management import (
    CountryRegulatory,
    CountryRegulatoryListResponse,
    CountryStatus,
    CountryStatusUpdate,
    CriticalPathResult,
    CrossTrialResource,
    CrossTrialResourceCreate,
    CrossTrialResourceListResponse,
    EnrollmentProjection,
    EnrollmentProjectionListResponse,
    GanttChartData,
    MilestoneCategory,
    MilestoneStatus,
    ResourceUtilization,
    SiteActivation,
    SiteActivationListResponse,
    SiteActivationStatus,
    SiteActivationUpdate,
    SiteBlocker,
    SiteBlockerCreate,
    SiteBlockerListResponse,
    SiteCommunication,
    SiteCommunicationCreate,
    SiteCommunicationListResponse,
    TMODashboard,
    TrialMilestone,
    TrialMilestoneCreate,
    TrialMilestoneListResponse,
    TrialMilestoneUpdate,
)
from app.services.trial_management_service import get_tmo_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/trial-management",
    tags=["Trial Management Office"],
)


# ---------------------------------------------------------------------------
# Site Activations
# ---------------------------------------------------------------------------


@router.get(
    "/sites",
    response_model=SiteActivationListResponse,
    summary="List site activations",
    description="Retrieve site activations with optional filtering by trial, country, and status.",
)
async def list_site_activations(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    country: Optional[str] = Query(None, description="Filter by country code"),
    status: Optional[SiteActivationStatus] = Query(None, description="Filter by activation status"),
) -> SiteActivationListResponse:
    svc = get_tmo_service()
    items = svc.list_site_activations(trial_id=trial_id, country=country, status=status)
    return SiteActivationListResponse(items=items, total=len(items))


@router.get(
    "/sites/delayed",
    response_model=list[dict],
    summary="List delayed site activations",
    description="Find sites where activation is delayed more than 2 weeks from planned date.",
)
async def list_delayed_sites() -> list[dict]:
    svc = get_tmo_service()
    return svc.get_delayed_sites()


@router.get(
    "/sites/{site_id}",
    response_model=SiteActivation,
    summary="Get a site activation",
    description="Retrieve detailed site activation information by site ID.",
)
async def get_site_activation(site_id: str) -> SiteActivation:
    svc = get_tmo_service()
    site = svc.get_site_activation(site_id)
    if site is None:
        raise HTTPException(status_code=404, detail=f"Site activation '{site_id}' not found")
    return site


@router.put(
    "/sites/{site_id}/status",
    response_model=SiteActivation,
    summary="Update site activation status",
    description="Update a site activation status with transition validation. Only valid transitions are allowed.",
)
async def update_site_status(site_id: str, payload: SiteActivationUpdate) -> SiteActivation:
    svc = get_tmo_service()
    try:
        return svc.update_site_status(site_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Site Blockers
# ---------------------------------------------------------------------------


@router.post(
    "/sites/{site_id}/blockers",
    response_model=SiteBlocker,
    status_code=201,
    summary="Raise a site blocker",
    description="Raise a new blocker for a site that is impeding activation or operation.",
)
async def raise_blocker(
    site_id: str,
    payload: SiteBlockerCreate,
    trial_id: str = Query(..., description="Trial ID for the blocker"),
) -> SiteBlocker:
    svc = get_tmo_service()
    return svc.raise_blocker(site_id, trial_id, payload)


@router.get(
    "/blockers",
    response_model=SiteBlockerListResponse,
    summary="List blockers",
    description="Retrieve site blockers with optional filtering by trial and open/resolved status.",
)
async def list_blockers(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    open_only: bool = Query(False, description="Show only open (unresolved) blockers"),
) -> SiteBlockerListResponse:
    svc = get_tmo_service()
    items = svc.list_blockers(trial_id=trial_id, open_only=open_only)
    return SiteBlockerListResponse(items=items, total=len(items))


@router.get(
    "/blockers/{blocker_id}",
    response_model=SiteBlocker,
    summary="Get a blocker",
    description="Retrieve detailed information about a specific site blocker.",
)
async def get_blocker(blocker_id: str) -> SiteBlocker:
    svc = get_tmo_service()
    blocker = svc.get_blocker(blocker_id)
    if blocker is None:
        raise HTTPException(status_code=404, detail=f"Blocker '{blocker_id}' not found")
    return blocker


@router.post(
    "/blockers/{blocker_id}/resolve",
    response_model=SiteBlocker,
    summary="Resolve a blocker",
    description="Mark a blocker as resolved with the current timestamp.",
)
async def resolve_blocker(blocker_id: str) -> SiteBlocker:
    svc = get_tmo_service()
    try:
        return svc.resolve_blocker(blocker_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/blockers/auto-escalate",
    response_model=SiteBlockerListResponse,
    summary="Auto-escalate open blockers",
    description="Auto-escalate blockers that have been open for more than 14 days and are not already escalated.",
)
async def auto_escalate_blockers() -> SiteBlockerListResponse:
    svc = get_tmo_service()
    escalated = svc.auto_escalate_blockers()
    return SiteBlockerListResponse(items=escalated, total=len(escalated))


# ---------------------------------------------------------------------------
# Country Regulatory
# ---------------------------------------------------------------------------


@router.get(
    "/countries",
    response_model=CountryRegulatoryListResponse,
    summary="List country regulatory records",
    description="Retrieve country regulatory records with optional filtering by trial and status.",
)
async def list_country_regulatory(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    status: Optional[CountryStatus] = Query(None, description="Filter by country status"),
) -> CountryRegulatoryListResponse:
    svc = get_tmo_service()
    items = svc.list_country_regulatory(trial_id=trial_id, status=status)
    return CountryRegulatoryListResponse(items=items, total=len(items))


@router.get(
    "/countries/{country_id}",
    response_model=CountryRegulatory,
    summary="Get a country regulatory record",
    description="Retrieve detailed country regulatory information by record ID.",
)
async def get_country_regulatory(country_id: str) -> CountryRegulatory:
    svc = get_tmo_service()
    record = svc.get_country_regulatory(country_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Country regulatory record '{country_id}' not found")
    return record


@router.put(
    "/countries/{country_id}/status",
    response_model=CountryRegulatory,
    summary="Update country regulatory status",
    description="Update the regulatory status for a country in a trial.",
)
async def update_country_status(country_id: str, payload: CountryStatusUpdate) -> CountryRegulatory:
    svc = get_tmo_service()
    try:
        return svc.update_country_status(country_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------


@router.get(
    "/milestones",
    response_model=TrialMilestoneListResponse,
    summary="List trial milestones",
    description="Retrieve milestones with optional filtering by trial, category, and status.",
)
async def list_milestones(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    category: Optional[MilestoneCategory] = Query(None, description="Filter by milestone category"),
    status: Optional[MilestoneStatus] = Query(None, description="Filter by milestone status"),
) -> TrialMilestoneListResponse:
    svc = get_tmo_service()
    items = svc.list_milestones(trial_id=trial_id, category=category, status=status)
    return TrialMilestoneListResponse(items=items, total=len(items))


@router.get(
    "/milestones/critical-path/{trial_id}",
    response_model=CriticalPathResult,
    summary="Get critical path for a trial",
    description="Compute the critical path (longest chain of dependent milestones) for a trial.",
)
async def get_critical_path(trial_id: str) -> CriticalPathResult:
    svc = get_tmo_service()
    return svc.get_critical_path(trial_id)


@router.get(
    "/milestones/gantt/{trial_id}",
    response_model=GanttChartData,
    summary="Get Gantt chart data for a trial",
    description="Generate Gantt chart visualization data including critical path markers.",
)
async def get_gantt_data(trial_id: str) -> GanttChartData:
    svc = get_tmo_service()
    return svc.get_gantt_data(trial_id)


@router.get(
    "/milestones/{milestone_id}",
    response_model=TrialMilestone,
    summary="Get a trial milestone",
    description="Retrieve detailed milestone information by milestone ID.",
)
async def get_milestone(milestone_id: str) -> TrialMilestone:
    svc = get_tmo_service()
    milestone = svc.get_milestone(milestone_id)
    if milestone is None:
        raise HTTPException(status_code=404, detail=f"Milestone '{milestone_id}' not found")
    return milestone


@router.post(
    "/milestones",
    response_model=TrialMilestone,
    status_code=201,
    summary="Create a trial milestone",
    description="Create a new milestone for a trial with optional dependencies.",
)
async def create_milestone(payload: TrialMilestoneCreate) -> TrialMilestone:
    svc = get_tmo_service()
    try:
        return svc.create_milestone(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/milestones/{milestone_id}",
    response_model=TrialMilestone,
    summary="Update a trial milestone",
    description="Update milestone fields including status, dates, and dependencies.",
)
async def update_milestone(milestone_id: str, payload: TrialMilestoneUpdate) -> TrialMilestone:
    svc = get_tmo_service()
    try:
        result = svc.update_milestone(milestone_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result


# ---------------------------------------------------------------------------
# Communications
# ---------------------------------------------------------------------------


@router.get(
    "/communications",
    response_model=SiteCommunicationListResponse,
    summary="List site communications",
    description="Retrieve site communications with optional filtering by trial and type.",
)
async def list_communications(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
    comm_type: Optional[str] = Query(None, description="Filter by communication type"),
) -> SiteCommunicationListResponse:
    svc = get_tmo_service()
    from app.schemas.trial_management import CommunicationType
    ct = CommunicationType(comm_type) if comm_type else None
    items = svc.list_communications(trial_id=trial_id, comm_type=ct)
    return SiteCommunicationListResponse(items=items, total=len(items))


@router.get(
    "/communications/{comm_id}",
    response_model=SiteCommunication,
    summary="Get a site communication",
    description="Retrieve detailed communication information including recipients and acknowledgments.",
)
async def get_communication(comm_id: str) -> SiteCommunication:
    svc = get_tmo_service()
    comm = svc.get_communication(comm_id)
    if comm is None:
        raise HTTPException(status_code=404, detail=f"Communication '{comm_id}' not found")
    return comm


@router.post(
    "/communications",
    response_model=SiteCommunication,
    status_code=201,
    summary="Send a site communication",
    description="Send a new communication to specified site recipients.",
)
async def send_communication(payload: SiteCommunicationCreate) -> SiteCommunication:
    svc = get_tmo_service()
    return svc.send_communication(payload)


@router.post(
    "/communications/{comm_id}/acknowledge",
    response_model=SiteCommunication,
    summary="Acknowledge a communication",
    description="Record acknowledgment of a communication from a specific site.",
)
async def acknowledge_communication(
    comm_id: str,
    site_id: str = Query(..., description="Site ID acknowledging the communication"),
) -> SiteCommunication:
    svc = get_tmo_service()
    try:
        return svc.acknowledge_communication(comm_id, site_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# TMO Dashboard
# ---------------------------------------------------------------------------


@router.get(
    "/dashboard/{trial_id}",
    response_model=TMODashboard,
    summary="Get TMO dashboard for a trial",
    description="Aggregated TMO dashboard with site metrics, enrollment progress, "
                "milestone status, and open blockers.",
)
async def get_dashboard(trial_id: str) -> TMODashboard:
    svc = get_tmo_service()
    return svc.get_dashboard(trial_id)


# ---------------------------------------------------------------------------
# Enrollment Projections
# ---------------------------------------------------------------------------


@router.get(
    "/enrollment-projections",
    response_model=EnrollmentProjectionListResponse,
    summary="Get enrollment projections",
    description="Get enrollment projections with forecasted completion dates, "
                "optionally filtered by trial ID.",
)
async def get_enrollment_projections(
    trial_id: Optional[str] = Query(None, description="Filter by trial ID"),
) -> EnrollmentProjectionListResponse:
    svc = get_tmo_service()
    items = svc.get_enrollment_projection(trial_id=trial_id)
    return EnrollmentProjectionListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Cross-Trial Resources
# ---------------------------------------------------------------------------


@router.get(
    "/resources",
    response_model=CrossTrialResourceListResponse,
    summary="List cross-trial resources",
    description="Retrieve all cross-trial resources (personnel shared across trials).",
)
async def list_resources() -> CrossTrialResourceListResponse:
    svc = get_tmo_service()
    items = svc.list_resources()
    return CrossTrialResourceListResponse(items=items, total=len(items))


@router.get(
    "/resources/utilization",
    response_model=ResourceUtilization,
    summary="Get resource utilization report",
    description="Generate a utilization report showing over/under-utilized resources "
                "and average utilization by role.",
)
async def get_utilization_report() -> ResourceUtilization:
    svc = get_tmo_service()
    return svc.get_utilization_report()


@router.get(
    "/resources/{resource_id}",
    response_model=CrossTrialResource,
    summary="Get a cross-trial resource",
    description="Retrieve detailed information about a specific cross-trial resource.",
)
async def get_resource(resource_id: str) -> CrossTrialResource:
    svc = get_tmo_service()
    resource = svc.get_resource(resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail=f"Resource '{resource_id}' not found")
    return resource


@router.post(
    "/resources",
    response_model=CrossTrialResource,
    status_code=201,
    summary="Add a cross-trial resource",
    description="Register a new person or resource that can be shared across trials.",
)
async def add_resource(payload: CrossTrialResourceCreate) -> CrossTrialResource:
    svc = get_tmo_service()
    return svc.add_resource(payload)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@router.get(
    "/stats",
    response_model=dict,
    summary="Get TMO service statistics",
    description="Return counts of all TMO data entities for operational monitoring.",
)
async def get_stats() -> dict:
    svc = get_tmo_service()
    return svc.get_stats()
