"""Defect Tracking & Test Environment Management API endpoints (QA-3).

Pharma-grade defect tracking with SLA enforcement, forward-only state
machine, MTTR metrics, trend analysis, SLA breach detection, duplicate
linking, and test environment health monitoring.

Endpoints:
    GET    /defect-tracking/defects                                    - List defects
    GET    /defect-tracking/defects/{defect_id}                        - Get defect by ID
    POST   /defect-tracking/defects                                    - Create defect
    PUT    /defect-tracking/defects/{defect_id}                        - Update defect fields
    DELETE /defect-tracking/defects/{defect_id}                        - Delete defect
    POST   /defect-tracking/defects/{defect_id}/transition             - Transition defect status
    GET    /defect-tracking/defects/{defect_id}/transitions            - Get transition history
    GET    /defect-tracking/defects/{defect_id}/comments               - List comments
    POST   /defect-tracking/defects/{defect_id}/comments               - Add comment
    DELETE /defect-tracking/defects/{defect_id}/comments/{comment_id}  - Delete comment
    POST   /defect-tracking/defects/{defect_id}/link-duplicate         - Link as duplicate
    GET    /defect-tracking/metrics                                    - Defect metrics
    GET    /defect-tracking/trends                                     - Trend analysis
    GET    /defect-tracking/sla-breaches                               - SLA breach detection
    GET    /defect-tracking/environments                               - List test environments
    GET    /defect-tracking/environments/{env_id}                      - Get environment
    POST   /defect-tracking/environments                               - Create environment
    PUT    /defect-tracking/environments/{env_id}                      - Update environment
    DELETE /defect-tracking/environments/{env_id}                      - Delete environment
    PUT    /defect-tracking/environments/{env_id}/health-checks        - Update health checks
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.defect_tracking import (
    DefectCategory,
    DefectComment,
    DefectCommentCreateRequest,
    DefectCommentListResponse,
    DefectCreateRequest,
    DefectLinkRequest,
    DefectListResponse,
    DefectMetrics,
    DefectPriority,
    DefectRecord,
    DefectSeverity,
    DefectStatus,
    DefectTransition,
    DefectTransitionListResponse,
    DefectTransitionRequest,
    DefectTrend,
    DefectUpdateRequest,
    EnvironmentStatus,
    EnvironmentType,
    HealthCheckUpdateRequest,
    SLABreachResponse,
    TestEnvironment,
    TestEnvironmentCreateRequest,
    TestEnvironmentListResponse,
    TestEnvironmentUpdateRequest,
)
from app.services.defect_tracking_service import get_defect_tracking_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/defect-tracking",
    tags=["Defect Tracking"],
)


# ---------------------------------------------------------------------------
# Defect CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/defects",
    response_model=DefectListResponse,
    summary="List defects",
    description="Retrieve defects with optional filtering by severity, status, category, assignee, or component.",
)
async def list_defects(
    severity: Optional[DefectSeverity] = Query(None, description="Filter by severity"),
    status: Optional[DefectStatus] = Query(None, description="Filter by status"),
    category: Optional[DefectCategory] = Query(None, description="Filter by category"),
    assigned_to: Optional[str] = Query(None, description="Filter by assignee"),
    component: Optional[str] = Query(None, description="Filter by component"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
) -> DefectListResponse:
    """List defects with optional filters and pagination."""
    svc = get_defect_tracking_service()
    records, total = svc.list_defects(
        severity=severity,
        status=status,
        category=category,
        assigned_to=assigned_to,
        component=component,
        limit=limit,
        offset=offset,
    )
    return DefectListResponse(
        defects=[svc.defect_to_schema(r) for r in records],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/defects/{defect_id}",
    response_model=DefectRecord,
    summary="Get defect by ID",
    description="Retrieve a single defect by its unique identifier.",
)
async def get_defect(defect_id: str) -> DefectRecord:
    """Get a defect by ID."""
    svc = get_defect_tracking_service()
    try:
        record = svc.get_defect(defect_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Defect {defect_id} not found")
    return svc.defect_to_schema(record)


@router.post(
    "/defects",
    response_model=DefectRecord,
    status_code=201,
    summary="Create a new defect",
    description="Create a new defect with auto-calculated SLA deadline based on severity.",
)
async def create_defect(body: DefectCreateRequest) -> DefectRecord:
    """Create a new defect."""
    svc = get_defect_tracking_service()
    record = svc.create_defect(
        title=body.title,
        description=body.description,
        severity=body.severity,
        priority=body.priority,
        category=body.category,
        component=body.component,
        reported_by=body.reported_by,
        assigned_to=body.assigned_to,
        steps_to_reproduce=body.steps_to_reproduce,
        expected_behavior=body.expected_behavior,
        actual_behavior=body.actual_behavior,
        environment=body.environment,
        build_version=body.build_version,
        tags=body.tags,
    )
    return svc.defect_to_schema(record)


@router.put(
    "/defects/{defect_id}",
    response_model=DefectRecord,
    summary="Update defect fields",
    description="Update defect metadata fields (not status - use the transition endpoint).",
)
async def update_defect(defect_id: str, body: DefectUpdateRequest) -> DefectRecord:
    """Update defect fields."""
    svc = get_defect_tracking_service()
    try:
        record = svc.update_defect(
            defect_id,
            title=body.title,
            description=body.description,
            priority=body.priority,
            category=body.category,
            component=body.component,
            assigned_to=body.assigned_to,
            steps_to_reproduce=body.steps_to_reproduce,
            expected_behavior=body.expected_behavior,
            actual_behavior=body.actual_behavior,
            resolution_notes=body.resolution_notes,
            tags=body.tags,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Defect {defect_id} not found")
    return svc.defect_to_schema(record)


@router.delete(
    "/defects/{defect_id}",
    status_code=204,
    summary="Delete a defect",
    description="Permanently delete a defect and its associated comments and transition history.",
)
async def delete_defect(defect_id: str) -> None:
    """Delete a defect."""
    svc = get_defect_tracking_service()
    try:
        svc.delete_defect(defect_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Defect {defect_id} not found")


# ---------------------------------------------------------------------------
# Status Transitions
# ---------------------------------------------------------------------------


@router.post(
    "/defects/{defect_id}/transition",
    response_model=DefectRecord,
    summary="Transition defect status",
    description="Transition a defect to a new status following the forward-only state machine. CLOSED -> REOPENED is allowed.",
)
async def transition_defect(defect_id: str, body: DefectTransitionRequest) -> DefectRecord:
    """Transition a defect's status."""
    svc = get_defect_tracking_service()
    try:
        record = svc.transition_defect(
            defect_id,
            to_status=body.to_status,
            transitioned_by=body.transitioned_by,
            reason=body.reason,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Defect {defect_id} not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return svc.defect_to_schema(record)


@router.get(
    "/defects/{defect_id}/transitions",
    response_model=DefectTransitionListResponse,
    summary="Get transition history",
    description="Retrieve the full status transition audit trail for a defect.",
)
async def get_transitions(defect_id: str) -> DefectTransitionListResponse:
    """Get transition history for a defect."""
    svc = get_defect_tracking_service()
    try:
        transitions = svc.get_transitions(defect_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Defect {defect_id} not found")
    return DefectTransitionListResponse(
        transitions=[svc.transition_to_schema(t) for t in transitions],
        total=len(transitions),
    )


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


@router.get(
    "/defects/{defect_id}/comments",
    response_model=DefectCommentListResponse,
    summary="List comments for a defect",
    description="Retrieve all comments associated with a defect.",
)
async def list_comments(defect_id: str) -> DefectCommentListResponse:
    """List comments for a defect."""
    svc = get_defect_tracking_service()
    try:
        comments = svc.get_comments(defect_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Defect {defect_id} not found")
    return DefectCommentListResponse(
        comments=[svc.comment_to_schema(c) for c in comments],
        total=len(comments),
    )


@router.post(
    "/defects/{defect_id}/comments",
    response_model=DefectComment,
    status_code=201,
    summary="Add a comment",
    description="Add a comment to an existing defect.",
)
async def add_comment(defect_id: str, body: DefectCommentCreateRequest) -> DefectComment:
    """Add a comment to a defect."""
    svc = get_defect_tracking_service()
    try:
        comment = svc.add_comment(defect_id, author=body.author, content=body.content)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Defect {defect_id} not found")
    return svc.comment_to_schema(comment)


@router.delete(
    "/defects/{defect_id}/comments/{comment_id}",
    status_code=204,
    summary="Delete a comment",
    description="Delete a specific comment from a defect.",
)
async def delete_comment(defect_id: str, comment_id: str) -> None:
    """Delete a comment."""
    svc = get_defect_tracking_service()
    try:
        svc.delete_comment(defect_id, comment_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Duplicate Linking
# ---------------------------------------------------------------------------


@router.post(
    "/defects/{defect_id}/link-duplicate",
    response_model=DefectRecord,
    summary="Link defect as duplicate",
    description="Mark a defect as a duplicate of another, creating a bidirectional link and transitioning to DUPLICATE status.",
)
async def link_duplicate(defect_id: str, body: DefectLinkRequest) -> DefectRecord:
    """Link a defect as duplicate of another."""
    svc = get_defect_tracking_service()
    try:
        record = svc.link_duplicate(
            defect_id,
            duplicate_of=body.duplicate_of,
            linked_by=body.linked_by,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return svc.defect_to_schema(record)


# ---------------------------------------------------------------------------
# Metrics & Analytics
# ---------------------------------------------------------------------------


@router.get(
    "/metrics",
    response_model=DefectMetrics,
    summary="Defect metrics",
    description="Compute aggregate defect metrics including MTTR, SLA compliance, reopen rate, and aging buckets.",
)
async def get_metrics() -> DefectMetrics:
    """Get aggregate defect metrics."""
    svc = get_defect_tracking_service()
    return svc.get_metrics()


@router.get(
    "/trends",
    response_model=DefectTrend,
    summary="Trend analysis",
    description="Analyze defect open/close trends over a specified period (default 30 days).",
)
async def get_trends(
    period_days: int = Query(30, ge=1, le=365, description="Trend period in days"),
) -> DefectTrend:
    """Get defect trend analysis."""
    svc = get_defect_tracking_service()
    return svc.get_trends(period_days=period_days)


@router.get(
    "/sla-breaches",
    response_model=SLABreachResponse,
    summary="SLA breach detection",
    description="Identify open defects that have breached or are at risk of breaching their SLA deadlines.",
)
async def get_sla_breaches() -> SLABreachResponse:
    """Get SLA breach report."""
    svc = get_defect_tracking_service()
    breaches = svc.get_sla_breaches()
    breached = [b for b in breaches if b.hours_overdue > 0]
    # At risk = within 20% of deadline (hours_overdue is negative but close to 0)
    at_risk = [b for b in breaches if b.hours_overdue <= 0]
    return SLABreachResponse(
        breaches=breaches,
        total=len(breaches),
        breached_count=len(breached),
        at_risk_count=len(at_risk),
    )


# ---------------------------------------------------------------------------
# Test Environment Management
# ---------------------------------------------------------------------------


@router.get(
    "/environments",
    response_model=TestEnvironmentListResponse,
    summary="List test environments",
    description="Retrieve test environments with optional filtering by type and status.",
)
async def list_environments(
    env_type: Optional[EnvironmentType] = Query(None, description="Filter by environment type"),
    status: Optional[EnvironmentStatus] = Query(None, description="Filter by status"),
) -> TestEnvironmentListResponse:
    """List test environments."""
    svc = get_defect_tracking_service()
    records = svc.list_environments(env_type=env_type, status=status)
    return TestEnvironmentListResponse(
        environments=[svc.environment_to_schema(r) for r in records],
        total=len(records),
    )


@router.get(
    "/environments/{env_id}",
    response_model=TestEnvironment,
    summary="Get test environment",
    description="Retrieve a single test environment by its unique identifier.",
)
async def get_environment(env_id: str) -> TestEnvironment:
    """Get a test environment by ID."""
    svc = get_defect_tracking_service()
    try:
        record = svc.get_environment(env_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Environment {env_id} not found")
    return svc.environment_to_schema(record)


@router.post(
    "/environments",
    response_model=TestEnvironment,
    status_code=201,
    summary="Create a test environment",
    description="Provision a new test environment.",
)
async def create_environment(body: TestEnvironmentCreateRequest) -> TestEnvironment:
    """Create a new test environment."""
    svc = get_defect_tracking_service()
    record = svc.create_environment(
        name=body.name,
        env_type=body.env_type,
        owner=body.owner,
        description=body.description,
        url=body.url,
        components=body.components,
    )
    return svc.environment_to_schema(record)


@router.put(
    "/environments/{env_id}",
    response_model=TestEnvironment,
    summary="Update a test environment",
    description="Update test environment fields.",
)
async def update_environment(env_id: str, body: TestEnvironmentUpdateRequest) -> TestEnvironment:
    """Update a test environment."""
    svc = get_defect_tracking_service()
    try:
        record = svc.update_environment(
            env_id,
            name=body.name,
            status=body.status,
            description=body.description,
            url=body.url,
            owner=body.owner,
            components=body.components,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Environment {env_id} not found")
    return svc.environment_to_schema(record)


@router.delete(
    "/environments/{env_id}",
    status_code=204,
    summary="Delete a test environment",
    description="Remove a test environment from the system.",
)
async def delete_environment(env_id: str) -> None:
    """Delete a test environment."""
    svc = get_defect_tracking_service()
    try:
        svc.delete_environment(env_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Environment {env_id} not found")


@router.put(
    "/environments/{env_id}/health-checks",
    response_model=TestEnvironment,
    summary="Update health checks",
    description="Update health check results for a test environment.",
)
async def update_health_checks(env_id: str, body: HealthCheckUpdateRequest) -> TestEnvironment:
    """Update health check results for an environment."""
    svc = get_defect_tracking_service()
    try:
        record = svc.update_health_checks(env_id, body.health_checks)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Environment {env_id} not found")
    return svc.environment_to_schema(record)
