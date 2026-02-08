"""Workforce Capacity Planning API (COO-4).

Endpoints for workforce analytics on a pharma-regulated clinical trial
patient recruitment platform:
- Team member management (CRUD)
- Capacity requirements tracking
- Hiring pipeline management
- Workforce KPIs and metrics
- Capacity projections
- Utilization analysis
- Skill gap identification
- Department capacity overview
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.workforce_planning import (
    CapacityProjectionResponse,
    CapacityRequirement,
    CapacityRequirementCreate,
    CapacityRequirementListResponse,
    CapacityRequirementUpdate,
    Department,
    DepartmentCapacity,
    HiringPlan,
    HiringPlanCreate,
    HiringPlanListResponse,
    HiringPlanUpdate,
    HiringStatus,
    SkillGapReport,
    TeamMember,
    TeamMemberCreate,
    TeamMemberListResponse,
    TeamMemberUpdate,
    UtilizationReport,
    WorkforceMetrics,
)
from app.services.workforce_planning_service import get_workforce_planning_service

router = APIRouter(prefix="/workforce-planning", tags=["Workforce Planning"])


# ============================================================================
# Workforce Metrics (Dashboard)
# ============================================================================


@router.get(
    "/metrics",
    response_model=WorkforceMetrics,
    summary="Workforce KPIs",
    description="Aggregated workforce metrics: headcount, FTE, utilization, gaps, hiring pipeline, tenure, PHI certification, cost per FTE.",
)
async def get_metrics() -> WorkforceMetrics:
    """Return workforce KPI metrics."""
    service = get_workforce_planning_service()
    return service.get_metrics()


# ============================================================================
# Team Members
# ============================================================================


@router.get(
    "/team-members",
    response_model=TeamMemberListResponse,
    summary="List team members",
    description="List all team members, optionally filtered by department.",
)
async def list_team_members(
    department: Department | None = Query(
        None, description="Filter by department"
    ),
) -> TeamMemberListResponse:
    """List team members."""
    service = get_workforce_planning_service()
    return service.list_team_members(department=department)


@router.get(
    "/team-members/{member_id}",
    response_model=TeamMember,
    summary="Get team member",
    description="Return a single team member by ID.",
)
async def get_team_member(member_id: str) -> TeamMember:
    """Get a team member."""
    service = get_workforce_planning_service()
    try:
        return service.get_team_member(member_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/team-members",
    response_model=TeamMember,
    status_code=201,
    summary="Add a team member",
    description="Create a new team member.",
)
async def add_team_member(body: TeamMemberCreate) -> TeamMember:
    """Add a new team member."""
    service = get_workforce_planning_service()
    return service.add_team_member(
        name=body.name,
        department=body.department,
        role=body.role,
        skill_level=body.skill_level,
        fte_equivalent=body.fte_equivalent,
        hire_date=body.hire_date,
        annual_cost=body.annual_cost,
        utilization_pct=body.utilization_pct,
        certifications=body.certifications,
        can_handle_phi=body.can_handle_phi,
    )


@router.put(
    "/team-members/{member_id}",
    response_model=TeamMember,
    summary="Update a team member",
    description="Update fields on an existing team member.",
)
async def update_team_member(member_id: str, body: TeamMemberUpdate) -> TeamMember:
    """Update an existing team member."""
    service = get_workforce_planning_service()
    try:
        return service.update_team_member(
            member_id,
            name=body.name,
            department=body.department,
            role=body.role,
            skill_level=body.skill_level,
            fte_equivalent=body.fte_equivalent,
            hire_date=body.hire_date,
            annual_cost=body.annual_cost,
            utilization_pct=body.utilization_pct,
            certifications=body.certifications,
            can_handle_phi=body.can_handle_phi,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete(
    "/team-members/{member_id}",
    status_code=204,
    summary="Remove a team member",
    description="Delete a team member by ID.",
)
async def delete_team_member(member_id: str) -> None:
    """Remove a team member."""
    service = get_workforce_planning_service()
    try:
        service.remove_team_member(member_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ============================================================================
# Capacity Requirements
# ============================================================================


@router.get(
    "/capacity-requirements",
    response_model=CapacityRequirementListResponse,
    summary="List capacity requirements",
    description="List all capacity requirements, optionally filtered by department.",
)
async def list_capacity_requirements(
    department: Department | None = Query(
        None, description="Filter by department"
    ),
) -> CapacityRequirementListResponse:
    """List capacity requirements."""
    service = get_workforce_planning_service()
    return service.list_capacity_requirements(department=department)


@router.get(
    "/capacity-requirements/{req_id}",
    response_model=CapacityRequirement,
    summary="Get capacity requirement",
    description="Return a single capacity requirement by ID.",
)
async def get_capacity_requirement(req_id: str) -> CapacityRequirement:
    """Get a capacity requirement."""
    service = get_workforce_planning_service()
    try:
        return service.get_capacity_requirement(req_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/capacity-requirements",
    response_model=CapacityRequirement,
    status_code=201,
    summary="Add a capacity requirement",
    description="Create a new capacity requirement (staffing gap).",
)
async def add_capacity_requirement(body: CapacityRequirementCreate) -> CapacityRequirement:
    """Add a new capacity requirement."""
    service = get_workforce_planning_service()
    return service.add_capacity_requirement(
        department=body.department,
        role=body.role,
        skill_level=body.skill_level,
        required_fte=body.required_fte,
        current_fte=body.current_fte,
        priority=body.priority,
        justification=body.justification,
        timeline_months=body.timeline_months,
    )


@router.put(
    "/capacity-requirements/{req_id}",
    response_model=CapacityRequirement,
    summary="Update a capacity requirement",
    description="Update fields on an existing capacity requirement.",
)
async def update_capacity_requirement(
    req_id: str, body: CapacityRequirementUpdate
) -> CapacityRequirement:
    """Update an existing capacity requirement."""
    service = get_workforce_planning_service()
    try:
        return service.update_capacity_requirement(
            req_id,
            department=body.department,
            role=body.role,
            skill_level=body.skill_level,
            required_fte=body.required_fte,
            current_fte=body.current_fte,
            priority=body.priority,
            justification=body.justification,
            timeline_months=body.timeline_months,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete(
    "/capacity-requirements/{req_id}",
    status_code=204,
    summary="Remove a capacity requirement",
    description="Delete a capacity requirement by ID.",
)
async def delete_capacity_requirement(req_id: str) -> None:
    """Remove a capacity requirement."""
    service = get_workforce_planning_service()
    try:
        service.remove_capacity_requirement(req_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ============================================================================
# Hiring Plans
# ============================================================================


@router.get(
    "/hiring-plans",
    response_model=HiringPlanListResponse,
    summary="List hiring plans",
    description="List all hiring plans, optionally filtered by department and/or status.",
)
async def list_hiring_plans(
    department: Department | None = Query(None, description="Filter by department"),
    status: HiringStatus | None = Query(None, description="Filter by status"),
) -> HiringPlanListResponse:
    """List hiring plans."""
    service = get_workforce_planning_service()
    return service.list_hiring_plans(department=department, status=status)


@router.get(
    "/hiring-plans/{plan_id}",
    response_model=HiringPlan,
    summary="Get hiring plan",
    description="Return a single hiring plan by ID.",
)
async def get_hiring_plan(plan_id: str) -> HiringPlan:
    """Get a hiring plan."""
    service = get_workforce_planning_service()
    try:
        return service.get_hiring_plan(plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/hiring-plans",
    response_model=HiringPlan,
    status_code=201,
    summary="Add a hiring plan",
    description="Create a new hiring plan / requisition.",
)
async def add_hiring_plan(body: HiringPlanCreate) -> HiringPlan:
    """Add a new hiring plan."""
    service = get_workforce_planning_service()
    return service.add_hiring_plan(
        department=body.department,
        role=body.role,
        skill_level=body.skill_level,
        planned_start=body.planned_start,
        estimated_salary=body.estimated_salary,
        status=body.status,
        requisition_id=body.requisition_id,
    )


@router.put(
    "/hiring-plans/{plan_id}",
    response_model=HiringPlan,
    summary="Update a hiring plan",
    description="Update fields on an existing hiring plan.",
)
async def update_hiring_plan(plan_id: str, body: HiringPlanUpdate) -> HiringPlan:
    """Update an existing hiring plan."""
    service = get_workforce_planning_service()
    try:
        return service.update_hiring_plan(
            plan_id,
            department=body.department,
            role=body.role,
            skill_level=body.skill_level,
            planned_start=body.planned_start,
            estimated_salary=body.estimated_salary,
            status=body.status,
            requisition_id=body.requisition_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete(
    "/hiring-plans/{plan_id}",
    status_code=204,
    summary="Remove a hiring plan",
    description="Delete a hiring plan by ID.",
)
async def delete_hiring_plan(plan_id: str) -> None:
    """Remove a hiring plan."""
    service = get_workforce_planning_service()
    try:
        service.remove_hiring_plan(plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ============================================================================
# Analytics
# ============================================================================


@router.get(
    "/capacity-by-department",
    response_model=list[DepartmentCapacity],
    summary="Capacity by department",
    description="Current vs required FTE per department.",
)
async def get_capacity_by_department() -> list[DepartmentCapacity]:
    """Return capacity breakdown by department."""
    service = get_workforce_planning_service()
    return service.get_capacity_by_department()


@router.get(
    "/capacity-projection",
    response_model=CapacityProjectionResponse,
    summary="Capacity projection",
    description="Monthly capacity projections accounting for hiring pipeline.",
)
async def get_capacity_projection(
    months: int = Query(12, ge=1, le=36, description="Number of months to project"),
) -> CapacityProjectionResponse:
    """Project workforce capacity over time."""
    service = get_workforce_planning_service()
    return service.project_capacity(months=months)


@router.get(
    "/utilization",
    response_model=UtilizationReport,
    summary="Utilization report",
    description="Utilization analysis by department with over/under-utilized counts.",
)
async def get_utilization_report() -> UtilizationReport:
    """Return utilization analysis."""
    service = get_workforce_planning_service()
    return service.get_utilization_report()


@router.get(
    "/skill-gaps",
    response_model=SkillGapReport,
    summary="Skill gap analysis",
    description="Identify skill gaps and provide hiring recommendations.",
)
async def get_skill_gaps() -> SkillGapReport:
    """Return skill gap analysis."""
    service = get_workforce_planning_service()
    return service.identify_skill_gaps()
