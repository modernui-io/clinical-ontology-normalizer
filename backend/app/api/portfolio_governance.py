"""Portfolio & Project Governance API endpoints.

Provides comprehensive portfolio governance operations: program lifecycle
management, stage-gate decisions, cross-functional team structures, resource
allocation, portfolio prioritization, risk register management, executive
governance dashboards, and portfolio metrics.

Endpoints:
    GET    /portfolio-governance/programs                          - List programs
    GET    /portfolio-governance/programs/{program_id}             - Get single program
    POST   /portfolio-governance/programs                          - Create program
    PUT    /portfolio-governance/programs/{program_id}             - Update program
    DELETE /portfolio-governance/programs/{program_id}             - Delete program
    GET    /portfolio-governance/stage-gates                       - List stage gates
    GET    /portfolio-governance/stage-gates/{gate_id}             - Get single stage gate
    POST   /portfolio-governance/stage-gates                       - Create stage gate
    PUT    /portfolio-governance/stage-gates/{gate_id}             - Update stage gate
    DELETE /portfolio-governance/stage-gates/{gate_id}             - Delete stage gate
    POST   /portfolio-governance/stage-gates/{gate_id}/advance     - Advance stage gate
    GET    /portfolio-governance/team-members                      - List team members
    GET    /portfolio-governance/team-members/{member_id}          - Get single team member
    POST   /portfolio-governance/team-members                      - Create team member
    PUT    /portfolio-governance/team-members/{member_id}          - Update team member
    DELETE /portfolio-governance/team-members/{member_id}          - Delete team member
    GET    /portfolio-governance/resources                         - List resource allocations
    GET    /portfolio-governance/resources/{allocation_id}         - Get single allocation
    POST   /portfolio-governance/resources                         - Create resource allocation
    PUT    /portfolio-governance/resources/{allocation_id}         - Update allocation
    DELETE /portfolio-governance/resources/{allocation_id}         - Delete allocation
    GET    /portfolio-governance/prioritizations                   - List prioritizations
    GET    /portfolio-governance/prioritizations/{prio_id}         - Get single prioritization
    POST   /portfolio-governance/prioritizations                   - Create prioritization
    POST   /portfolio-governance/prioritizations/rerank            - Re-rank portfolio
    GET    /portfolio-governance/risks                             - List risk register
    GET    /portfolio-governance/risks/{risk_id}                   - Get single risk
    POST   /portfolio-governance/risks                             - Register risk
    PUT    /portfolio-governance/risks/{risk_id}                   - Update risk
    DELETE /portfolio-governance/risks/{risk_id}                   - Delete risk
    GET    /portfolio-governance/dashboard                         - Portfolio dashboard
    GET    /portfolio-governance/metrics                           - Governance metrics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.portfolio_governance import (
    AdvanceStageGateRequest,
    GovernanceMetrics,
    GovernanceRole,
    PortfolioDashboard,
    PortfolioPrioritization,
    PortfolioPrioritizationCreate,
    PortfolioPrioritizationListResponse,
    PriorityLevel,
    Program,
    ProgramCreate,
    ProgramListResponse,
    ProgramPhase,
    ProgramStatus,
    ProgramUpdate,
    ResourceAllocation,
    ResourceAllocationCreate,
    ResourceAllocationListResponse,
    ResourceAllocationUpdate,
    ResourceType,
    RiskCategory,
    RiskRegister,
    RiskRegisterCreate,
    RiskRegisterListResponse,
    RiskRegisterUpdate,
    RiskStatus,
    StageGate,
    StageGateCreate,
    StageGateDecision,
    StageGateListResponse,
    StageGateUpdate,
    TeamMember,
    TeamMemberCreate,
    TeamMemberListResponse,
    TeamMemberUpdate,
)
from app.services.portfolio_governance_service import get_portfolio_governance_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/portfolio-governance",
    tags=["Portfolio Governance"],
)


# ---------------------------------------------------------------------------
# Programs
# ---------------------------------------------------------------------------


@router.get(
    "/programs",
    response_model=ProgramListResponse,
    summary="List programs",
    description="Retrieve drug development programs with optional filtering by phase, status, priority, or therapeutic area.",
)
async def list_programs(
    phase: Optional[ProgramPhase] = Query(None, description="Filter by development phase"),
    status: Optional[ProgramStatus] = Query(None, description="Filter by program status"),
    priority: Optional[PriorityLevel] = Query(None, description="Filter by priority level"),
    therapeutic_area: Optional[str] = Query(None, description="Filter by therapeutic area"),
) -> ProgramListResponse:
    svc = get_portfolio_governance_service()
    items = svc.list_programs(
        phase=phase, status=status, priority=priority, therapeutic_area=therapeutic_area
    )
    return ProgramListResponse(items=items, total=len(items))


@router.get(
    "/programs/{program_id}",
    response_model=Program,
    summary="Get a program",
)
async def get_program(program_id: str) -> Program:
    svc = get_portfolio_governance_service()
    program = svc.get_program(program_id)
    if program is None:
        raise HTTPException(status_code=404, detail=f"Program '{program_id}' not found")
    return program


@router.post(
    "/programs",
    response_model=Program,
    status_code=201,
    summary="Create a program",
)
async def create_program(payload: ProgramCreate) -> Program:
    svc = get_portfolio_governance_service()
    return svc.create_program(payload)


@router.put(
    "/programs/{program_id}",
    response_model=Program,
    summary="Update a program",
)
async def update_program(program_id: str, payload: ProgramUpdate) -> Program:
    svc = get_portfolio_governance_service()
    updated = svc.update_program(program_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Program '{program_id}' not found")
    return updated


@router.delete(
    "/programs/{program_id}",
    status_code=204,
    summary="Delete a program",
)
async def delete_program(program_id: str) -> None:
    svc = get_portfolio_governance_service()
    deleted = svc.delete_program(program_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Program '{program_id}' not found")


# ---------------------------------------------------------------------------
# Stage Gates
# ---------------------------------------------------------------------------


@router.get(
    "/stage-gates",
    response_model=StageGateListResponse,
    summary="List stage gates",
    description="Retrieve stage gates with optional filtering by program, decision, or pending status.",
)
async def list_stage_gates(
    program_id: Optional[str] = Query(None, description="Filter by program ID"),
    decision: Optional[StageGateDecision] = Query(None, description="Filter by decision"),
    pending: Optional[bool] = Query(None, description="Filter for pending gates (no decision)"),
) -> StageGateListResponse:
    svc = get_portfolio_governance_service()
    items = svc.list_stage_gates(program_id=program_id, decision=decision, pending=pending)
    return StageGateListResponse(items=items, total=len(items))


@router.get(
    "/stage-gates/{gate_id}",
    response_model=StageGate,
    summary="Get a stage gate",
)
async def get_stage_gate(gate_id: str) -> StageGate:
    svc = get_portfolio_governance_service()
    gate = svc.get_stage_gate(gate_id)
    if gate is None:
        raise HTTPException(status_code=404, detail=f"Stage gate '{gate_id}' not found")
    return gate


@router.post(
    "/stage-gates",
    response_model=StageGate,
    status_code=201,
    summary="Create a stage gate",
)
async def create_stage_gate(payload: StageGateCreate) -> StageGate:
    svc = get_portfolio_governance_service()
    try:
        return svc.create_stage_gate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/stage-gates/{gate_id}",
    response_model=StageGate,
    summary="Update a stage gate",
)
async def update_stage_gate(gate_id: str, payload: StageGateUpdate) -> StageGate:
    svc = get_portfolio_governance_service()
    updated = svc.update_stage_gate(gate_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Stage gate '{gate_id}' not found")
    return updated


@router.delete(
    "/stage-gates/{gate_id}",
    status_code=204,
    summary="Delete a stage gate",
)
async def delete_stage_gate(gate_id: str) -> None:
    svc = get_portfolio_governance_service()
    deleted = svc.delete_stage_gate(gate_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Stage gate '{gate_id}' not found")


@router.post(
    "/stage-gates/{gate_id}/advance",
    response_model=StageGate,
    summary="Advance a stage gate with a decision",
    description="Record a stage-gate decision. GO decisions advance the program phase. HOLD puts program on hold. NO_GO terminates the program.",
)
async def advance_stage_gate(gate_id: str, payload: AdvanceStageGateRequest) -> StageGate:
    svc = get_portfolio_governance_service()
    try:
        result = svc.advance_stage_gate(gate_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Stage gate '{gate_id}' not found")
    return result


# ---------------------------------------------------------------------------
# Team Members
# ---------------------------------------------------------------------------


@router.get(
    "/team-members",
    response_model=TeamMemberListResponse,
    summary="List team members",
    description="Retrieve cross-functional team members with optional filtering by program, role, or active status.",
)
async def list_team_members(
    program_id: Optional[str] = Query(None, description="Filter by program ID"),
    role: Optional[GovernanceRole] = Query(None, description="Filter by governance role"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
) -> TeamMemberListResponse:
    svc = get_portfolio_governance_service()
    items = svc.list_team_members(program_id=program_id, role=role, active=active)
    return TeamMemberListResponse(items=items, total=len(items))


@router.get(
    "/team-members/{member_id}",
    response_model=TeamMember,
    summary="Get a team member",
)
async def get_team_member(member_id: str) -> TeamMember:
    svc = get_portfolio_governance_service()
    member = svc.get_team_member(member_id)
    if member is None:
        raise HTTPException(status_code=404, detail=f"Team member '{member_id}' not found")
    return member


@router.post(
    "/team-members",
    response_model=TeamMember,
    status_code=201,
    summary="Add a team member to a program",
)
async def create_team_member(payload: TeamMemberCreate) -> TeamMember:
    svc = get_portfolio_governance_service()
    try:
        return svc.create_team_member(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/team-members/{member_id}",
    response_model=TeamMember,
    summary="Update a team member assignment",
)
async def update_team_member(member_id: str, payload: TeamMemberUpdate) -> TeamMember:
    svc = get_portfolio_governance_service()
    updated = svc.update_team_member(member_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Team member '{member_id}' not found")
    return updated


@router.delete(
    "/team-members/{member_id}",
    status_code=204,
    summary="Delete a team member assignment",
)
async def delete_team_member(member_id: str) -> None:
    svc = get_portfolio_governance_service()
    deleted = svc.delete_team_member(member_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Team member '{member_id}' not found")


# ---------------------------------------------------------------------------
# Resource Allocations
# ---------------------------------------------------------------------------


@router.get(
    "/resources",
    response_model=ResourceAllocationListResponse,
    summary="List resource allocations",
    description="Retrieve resource allocations with optional filtering by program, type, or approval status.",
)
async def list_resource_allocations(
    program_id: Optional[str] = Query(None, description="Filter by program ID"),
    resource_type: Optional[ResourceType] = Query(None, description="Filter by resource type"),
    approved: Optional[bool] = Query(None, description="Filter by approval status"),
) -> ResourceAllocationListResponse:
    svc = get_portfolio_governance_service()
    items = svc.list_resource_allocations(
        program_id=program_id, resource_type=resource_type, approved=approved
    )
    return ResourceAllocationListResponse(items=items, total=len(items))


@router.get(
    "/resources/{allocation_id}",
    response_model=ResourceAllocation,
    summary="Get a resource allocation",
)
async def get_resource_allocation(allocation_id: str) -> ResourceAllocation:
    svc = get_portfolio_governance_service()
    alloc = svc.get_resource_allocation(allocation_id)
    if alloc is None:
        raise HTTPException(status_code=404, detail=f"Resource allocation '{allocation_id}' not found")
    return alloc


@router.post(
    "/resources",
    response_model=ResourceAllocation,
    status_code=201,
    summary="Create a resource allocation",
)
async def create_resource_allocation(payload: ResourceAllocationCreate) -> ResourceAllocation:
    svc = get_portfolio_governance_service()
    try:
        return svc.create_resource_allocation(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/resources/{allocation_id}",
    response_model=ResourceAllocation,
    summary="Update a resource allocation",
)
async def update_resource_allocation(
    allocation_id: str,
    payload: ResourceAllocationUpdate,
) -> ResourceAllocation:
    svc = get_portfolio_governance_service()
    updated = svc.update_resource_allocation(allocation_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Resource allocation '{allocation_id}' not found")
    return updated


@router.delete(
    "/resources/{allocation_id}",
    status_code=204,
    summary="Delete a resource allocation",
)
async def delete_resource_allocation(allocation_id: str) -> None:
    svc = get_portfolio_governance_service()
    deleted = svc.delete_resource_allocation(allocation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Resource allocation '{allocation_id}' not found")


# ---------------------------------------------------------------------------
# Portfolio Prioritization
# ---------------------------------------------------------------------------


@router.get(
    "/prioritizations",
    response_model=PortfolioPrioritizationListResponse,
    summary="List portfolio prioritizations",
    description="Retrieve portfolio prioritization rankings with optional program filter.",
)
async def list_prioritizations(
    program_id: Optional[str] = Query(None, description="Filter by program ID"),
) -> PortfolioPrioritizationListResponse:
    svc = get_portfolio_governance_service()
    items = svc.list_prioritizations(program_id=program_id)
    return PortfolioPrioritizationListResponse(items=items, total=len(items))


@router.get(
    "/prioritizations/{prio_id}",
    response_model=PortfolioPrioritization,
    summary="Get a portfolio prioritization",
)
async def get_prioritization(prio_id: str) -> PortfolioPrioritization:
    svc = get_portfolio_governance_service()
    prio = svc.get_prioritization(prio_id)
    if prio is None:
        raise HTTPException(status_code=404, detail=f"Prioritization '{prio_id}' not found")
    return prio


@router.post(
    "/prioritizations",
    response_model=PortfolioPrioritization,
    status_code=201,
    summary="Create a portfolio prioritization",
    description="Score and rank a program in the portfolio. Overall priority score is computed from weighted component scores.",
)
async def create_prioritization(payload: PortfolioPrioritizationCreate) -> PortfolioPrioritization:
    svc = get_portfolio_governance_service()
    try:
        return svc.create_prioritization(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/prioritizations/rerank",
    response_model=PortfolioPrioritizationListResponse,
    summary="Re-rank the portfolio",
    description="Re-rank all prioritizations by overall priority score. Returns the updated ranked list.",
)
async def rerank_portfolio() -> PortfolioPrioritizationListResponse:
    svc = get_portfolio_governance_service()
    items = svc.prioritize_portfolio()
    return PortfolioPrioritizationListResponse(items=items, total=len(items))


# ---------------------------------------------------------------------------
# Risk Register
# ---------------------------------------------------------------------------


@router.get(
    "/risks",
    response_model=RiskRegisterListResponse,
    summary="List risk register entries",
    description="Retrieve risk register entries with optional filtering by program, category, or status.",
)
async def list_risks(
    program_id: Optional[str] = Query(None, description="Filter by program ID"),
    category: Optional[RiskCategory] = Query(None, description="Filter by risk category"),
    status: Optional[RiskStatus] = Query(None, description="Filter by risk status"),
) -> RiskRegisterListResponse:
    svc = get_portfolio_governance_service()
    items = svc.list_risks(program_id=program_id, category=category, status=status)
    return RiskRegisterListResponse(items=items, total=len(items))


@router.get(
    "/risks/{risk_id}",
    response_model=RiskRegister,
    summary="Get a risk register entry",
)
async def get_risk(risk_id: str) -> RiskRegister:
    svc = get_portfolio_governance_service()
    risk = svc.get_risk(risk_id)
    if risk is None:
        raise HTTPException(status_code=404, detail=f"Risk '{risk_id}' not found")
    return risk


@router.post(
    "/risks",
    response_model=RiskRegister,
    status_code=201,
    summary="Register a new risk",
    description="Add a new risk to the program risk register. Risk score is computed as probability x impact.",
)
async def register_risk(payload: RiskRegisterCreate) -> RiskRegister:
    svc = get_portfolio_governance_service()
    try:
        return svc.register_risk(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.put(
    "/risks/{risk_id}",
    response_model=RiskRegister,
    summary="Update a risk register entry",
)
async def update_risk(risk_id: str, payload: RiskRegisterUpdate) -> RiskRegister:
    svc = get_portfolio_governance_service()
    updated = svc.update_risk(risk_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Risk '{risk_id}' not found")
    return updated


@router.delete(
    "/risks/{risk_id}",
    status_code=204,
    summary="Delete a risk register entry",
)
async def delete_risk(risk_id: str) -> None:
    svc = get_portfolio_governance_service()
    deleted = svc.delete_risk(risk_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Risk '{risk_id}' not found")


# ---------------------------------------------------------------------------
# Dashboard & Metrics
# ---------------------------------------------------------------------------


@router.get(
    "/dashboard",
    response_model=PortfolioDashboard,
    summary="Get executive portfolio dashboard",
    description="Comprehensive executive dashboard with metrics, active programs, upcoming gates, top risks, and priority rankings.",
)
async def get_portfolio_dashboard() -> PortfolioDashboard:
    svc = get_portfolio_governance_service()
    return svc.get_portfolio_dashboard()


@router.get(
    "/metrics",
    response_model=GovernanceMetrics,
    summary="Get portfolio governance metrics",
    description="Aggregated metrics: program counts, budget utilization, stage gate status, team stats, risk summary, and prioritization stats.",
)
async def get_metrics() -> GovernanceMetrics:
    svc = get_portfolio_governance_service()
    return svc.get_metrics()
