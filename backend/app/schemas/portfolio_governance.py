"""Pydantic schemas for Portfolio & Project Governance.

Manages program lifecycles, stage-gate decisions, cross-functional team
structures, resource allocation, portfolio prioritization, risk registers,
and executive governance dashboards for clinical trial portfolio management.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ProgramPhase(str, Enum):
    """Phase of a drug development program."""

    DISCOVERY = "discovery"
    PRECLINICAL = "preclinical"
    PHASE_1 = "phase_1"
    PHASE_2 = "phase_2"
    PHASE_3 = "phase_3"
    NDA_SUBMISSION = "nda_submission"
    POST_APPROVAL = "post_approval"
    LIFECYCLE_MANAGEMENT = "lifecycle_management"


class StageGateDecision(str, Enum):
    """Decision outcome at a stage gate review."""

    GO = "go"
    CONDITIONAL_GO = "conditional_go"
    HOLD = "hold"
    NO_GO = "no_go"
    DEFERRED = "deferred"


class GovernanceRole(str, Enum):
    """Role on a cross-functional governance team."""

    EXECUTIVE_SPONSOR = "executive_sponsor"
    PROGRAM_LEAD = "program_lead"
    MEDICAL_LEAD = "medical_lead"
    REGULATORY_LEAD = "regulatory_lead"
    CMC_LEAD = "cmc_lead"
    COMMERCIAL_LEAD = "commercial_lead"
    FINANCE_LEAD = "finance_lead"


class PriorityLevel(str, Enum):
    """Strategic priority level for a program."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ResourceType(str, Enum):
    """Type of resource allocated to a program."""

    FTE = "fte"
    BUDGET = "budget"
    EQUIPMENT = "equipment"
    VENDOR = "vendor"
    FACILITY = "facility"


class ProgramStatus(str, Enum):
    """Lifecycle status of a program."""

    ACTIVE = "active"
    ON_HOLD = "on_hold"
    TERMINATED = "terminated"
    COMPLETED = "completed"


class RiskCategory(str, Enum):
    """Category of a program risk."""

    SCIENTIFIC = "scientific"
    REGULATORY = "regulatory"
    COMMERCIAL = "commercial"
    OPERATIONAL = "operational"
    FINANCIAL = "financial"
    SUPPLY_CHAIN = "supply_chain"


class RiskStatus(str, Enum):
    """Status of a risk register entry."""

    OPEN = "open"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    ACCEPTED = "accepted"


# ---------------------------------------------------------------------------
# Core records
# ---------------------------------------------------------------------------


class Program(BaseModel):
    """A drug development program in the portfolio."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique program identifier")
    name: str = Field(..., description="Program name")
    therapeutic_area: str = Field(..., description="Therapeutic area (e.g. Ophthalmology)")
    indication: str = Field(..., description="Target indication")
    molecule: str = Field(..., description="Molecule or compound name")
    modality: str = Field(..., description="Treatment modality (e.g. mAb, small molecule)")
    phase: ProgramPhase = Field(..., description="Current development phase")
    start_date: date = Field(..., description="Program start date")
    target_approval_date: date | None = Field(None, description="Target regulatory approval date")
    program_lead: str = Field(..., description="Program lead name")
    executive_sponsor: str = Field(..., description="Executive sponsor name")
    total_budget: float = Field(ge=0, description="Total program budget in millions USD")
    spent_budget: float = Field(ge=0, description="Budget spent to date in millions USD")
    strategic_priority: PriorityLevel = Field(..., description="Strategic priority classification")
    status: ProgramStatus = Field(default=ProgramStatus.ACTIVE, description="Program lifecycle status")
    description: str = Field(default="", description="Program description and objectives")
    created_at: datetime = Field(..., description="Record creation timestamp")
    updated_at: datetime = Field(..., description="Record last updated timestamp")


class StageGate(BaseModel):
    """A stage-gate decision point for a program."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique stage gate identifier")
    program_id: str = Field(..., description="Associated program ID")
    gate_name: str = Field(..., description="Gate name (e.g. IND Filing Gate)")
    phase_from: ProgramPhase = Field(..., description="Phase transitioning from")
    phase_to: ProgramPhase = Field(..., description="Phase transitioning to")
    scheduled_date: date = Field(..., description="Scheduled gate review date")
    actual_date: date | None = Field(None, description="Actual gate review date")
    decision: StageGateDecision | None = Field(None, description="Gate decision outcome")
    decision_rationale: str | None = Field(None, description="Rationale for the decision")
    conditions: list[str] = Field(default_factory=list, description="Conditions for conditional go")
    decision_makers: list[str] = Field(default_factory=list, description="Names of decision makers")
    key_data_reviewed: list[str] = Field(default_factory=list, description="Key data packages reviewed")
    next_gate_date: date | None = Field(None, description="Next gate review date")
    created_at: datetime = Field(..., description="Record creation timestamp")


class TeamMember(BaseModel):
    """A cross-functional team member assigned to a program."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique team member assignment ID")
    program_id: str = Field(..., description="Associated program ID")
    name: str = Field(..., description="Team member name")
    role: GovernanceRole = Field(..., description="Governance role on the team")
    department: str = Field(..., description="Department or function")
    allocation_pct: float = Field(ge=0, le=100, description="Percentage of time allocated")
    start_date: date = Field(..., description="Assignment start date")
    end_date: date | None = Field(None, description="Assignment end date")
    active: bool = Field(default=True, description="Whether assignment is active")


class ResourceAllocation(BaseModel):
    """A resource allocation to a program."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique resource allocation ID")
    program_id: str = Field(..., description="Associated program ID")
    resource_type: ResourceType = Field(..., description="Type of resource")
    description: str = Field(..., description="Resource description")
    quantity: float = Field(ge=0, description="Quantity of resource units")
    unit_cost: float = Field(ge=0, description="Cost per unit in thousands USD")
    total_cost: float = Field(ge=0, description="Total cost in thousands USD")
    period_start: date = Field(..., description="Allocation period start")
    period_end: date = Field(..., description="Allocation period end")
    approved: bool = Field(default=False, description="Whether allocation is approved")
    approved_by: str | None = Field(None, description="Name of approver")
    created_at: datetime = Field(..., description="Record creation timestamp")


class PortfolioPrioritization(BaseModel):
    """Portfolio prioritization scoring for a program."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique prioritization ID")
    program_id: str = Field(..., description="Associated program ID")
    strategic_alignment_score: float = Field(
        ge=0, le=100, description="Strategic alignment score (0-100)"
    )
    probability_of_success: float = Field(
        ge=0, le=100, description="Probability of technical and regulatory success (%)"
    )
    npv_estimate: float = Field(description="Net present value estimate in millions USD")
    peak_revenue_estimate: float = Field(
        ge=0, description="Peak annual revenue estimate in millions USD"
    )
    unmet_need_score: float = Field(
        ge=0, le=100, description="Unmet medical need score (0-100)"
    )
    competitive_position_score: float = Field(
        ge=0, le=100, description="Competitive landscape position score (0-100)"
    )
    overall_priority_score: float = Field(
        ge=0, le=100, description="Computed overall priority score (0-100)"
    )
    rank: int = Field(ge=1, description="Portfolio rank (1=highest priority)")
    assessment_date: date = Field(..., description="Date of assessment")
    assessed_by: str = Field(..., description="Name of assessor or committee")


class RiskRegister(BaseModel):
    """A risk entry in the program risk register."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique risk ID")
    program_id: str = Field(..., description="Associated program ID")
    risk_description: str = Field(..., description="Description of the risk")
    category: RiskCategory = Field(..., description="Risk category")
    probability: float = Field(ge=0, le=1, description="Probability of occurrence (0-1)")
    impact: float = Field(ge=1, le=5, description="Impact severity (1-5)")
    risk_score: float = Field(ge=0, le=5, description="Computed risk score (probability x impact)")
    mitigation_plan: str = Field(..., description="Mitigation plan description")
    owner: str = Field(..., description="Risk owner name")
    status: RiskStatus = Field(default=RiskStatus.OPEN, description="Risk status")
    identified_date: date = Field(..., description="Date risk was identified")
    target_resolution_date: date | None = Field(None, description="Target date for resolution")
    created_at: datetime = Field(..., description="Record creation timestamp")


class GovernanceMetrics(BaseModel):
    """Aggregated portfolio governance metrics for executive dashboard."""

    model_config = ConfigDict(from_attributes=True)

    total_programs: int = Field(ge=0, description="Total programs in portfolio")
    active_programs: int = Field(ge=0, description="Number of active programs")
    programs_by_phase: dict[str, int] = Field(
        default_factory=dict, description="Program counts by development phase"
    )
    programs_by_priority: dict[str, int] = Field(
        default_factory=dict, description="Program counts by priority level"
    )
    total_portfolio_budget: float = Field(
        ge=0, description="Total portfolio budget in millions USD"
    )
    total_portfolio_spent: float = Field(
        ge=0, description="Total budget spent across portfolio in millions USD"
    )
    budget_utilization_pct: float = Field(
        ge=0, le=100, description="Portfolio budget utilization percentage"
    )
    upcoming_stage_gates: int = Field(
        ge=0, description="Number of stage gates scheduled in next 90 days"
    )
    overdue_stage_gates: int = Field(
        ge=0, description="Number of stage gates past scheduled date without decision"
    )
    total_team_members: int = Field(ge=0, description="Total team member assignments")
    avg_team_allocation: float = Field(
        ge=0, le=100, description="Average team member allocation percentage"
    )
    open_risks: int = Field(ge=0, description="Number of open risks across portfolio")
    high_impact_risks: int = Field(
        ge=0, description="Number of high-impact risks (score >= 3.0)"
    )
    total_resource_allocations: int = Field(
        ge=0, description="Total resource allocations"
    )
    pending_approvals: int = Field(
        ge=0, description="Number of resource allocations pending approval"
    )
    avg_probability_of_success: float = Field(
        ge=0, le=100, description="Average probability of success across portfolio"
    )
    total_npv: float = Field(description="Sum of NPV estimates across portfolio")


# ---------------------------------------------------------------------------
# Request / response wrappers
# ---------------------------------------------------------------------------


class ProgramCreate(BaseModel):
    """Request to create a new program."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Program name")
    therapeutic_area: str = Field(..., description="Therapeutic area")
    indication: str = Field(..., description="Target indication")
    molecule: str = Field(..., description="Molecule or compound name")
    modality: str = Field(..., description="Treatment modality")
    phase: ProgramPhase = Field(..., description="Current development phase")
    start_date: date = Field(..., description="Program start date")
    target_approval_date: date | None = Field(None, description="Target approval date")
    program_lead: str = Field(..., description="Program lead name")
    executive_sponsor: str = Field(..., description="Executive sponsor name")
    total_budget: float = Field(ge=0, description="Total budget in millions USD")
    strategic_priority: PriorityLevel = Field(..., description="Priority classification")
    description: str = Field(default="", description="Program description")


class ProgramUpdate(BaseModel):
    """Request to update a program."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(None, description="Program name")
    therapeutic_area: str | None = Field(None, description="Therapeutic area")
    indication: str | None = Field(None, description="Target indication")
    molecule: str | None = Field(None, description="Molecule name")
    modality: str | None = Field(None, description="Treatment modality")
    phase: ProgramPhase | None = Field(None, description="Current phase")
    target_approval_date: date | None = Field(None, description="Target approval date")
    program_lead: str | None = Field(None, description="Program lead name")
    executive_sponsor: str | None = Field(None, description="Executive sponsor name")
    total_budget: float | None = Field(None, ge=0, description="Total budget")
    spent_budget: float | None = Field(None, ge=0, description="Spent budget")
    strategic_priority: PriorityLevel | None = Field(None, description="Priority")
    status: ProgramStatus | None = Field(None, description="Program status")
    description: str | None = Field(None, description="Description")


class StageGateCreate(BaseModel):
    """Request to create a stage gate."""

    model_config = ConfigDict(from_attributes=True)

    program_id: str = Field(..., description="Program ID")
    gate_name: str = Field(..., description="Gate name")
    phase_from: ProgramPhase = Field(..., description="Phase from")
    phase_to: ProgramPhase = Field(..., description="Phase to")
    scheduled_date: date = Field(..., description="Scheduled review date")
    decision_makers: list[str] = Field(default_factory=list, description="Decision makers")


class StageGateUpdate(BaseModel):
    """Request to update a stage gate."""

    model_config = ConfigDict(from_attributes=True)

    gate_name: str | None = Field(None, description="Gate name")
    scheduled_date: date | None = Field(None, description="Scheduled date")
    actual_date: date | None = Field(None, description="Actual review date")
    decision: StageGateDecision | None = Field(None, description="Decision outcome")
    decision_rationale: str | None = Field(None, description="Decision rationale")
    conditions: list[str] | None = Field(None, description="Conditions for conditional go")
    decision_makers: list[str] | None = Field(None, description="Decision makers")
    key_data_reviewed: list[str] | None = Field(None, description="Key data reviewed")
    next_gate_date: date | None = Field(None, description="Next gate date")


class AdvanceStageGateRequest(BaseModel):
    """Request to advance a stage gate with a decision."""

    model_config = ConfigDict(from_attributes=True)

    decision: StageGateDecision = Field(..., description="Gate decision")
    decision_rationale: str = Field(..., description="Rationale for the decision")
    actual_date: date = Field(..., description="Actual review date")
    conditions: list[str] = Field(default_factory=list, description="Conditions if conditional go")
    key_data_reviewed: list[str] = Field(default_factory=list, description="Key data reviewed")
    next_gate_date: date | None = Field(None, description="Next gate date")


class TeamMemberCreate(BaseModel):
    """Request to add a team member to a program."""

    model_config = ConfigDict(from_attributes=True)

    program_id: str = Field(..., description="Program ID")
    name: str = Field(..., description="Team member name")
    role: GovernanceRole = Field(..., description="Governance role")
    department: str = Field(..., description="Department")
    allocation_pct: float = Field(ge=0, le=100, description="Allocation percentage")
    start_date: date = Field(..., description="Start date")
    end_date: date | None = Field(None, description="End date")


class TeamMemberUpdate(BaseModel):
    """Request to update a team member assignment."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(None, description="Name")
    role: GovernanceRole | None = Field(None, description="Role")
    department: str | None = Field(None, description="Department")
    allocation_pct: float | None = Field(None, ge=0, le=100, description="Allocation %")
    start_date: date | None = Field(None, description="Start date")
    end_date: date | None = Field(None, description="End date")
    active: bool | None = Field(None, description="Active status")


class ResourceAllocationCreate(BaseModel):
    """Request to allocate a resource to a program."""

    model_config = ConfigDict(from_attributes=True)

    program_id: str = Field(..., description="Program ID")
    resource_type: ResourceType = Field(..., description="Resource type")
    description: str = Field(..., description="Description")
    quantity: float = Field(ge=0, description="Quantity")
    unit_cost: float = Field(ge=0, description="Unit cost in thousands USD")
    period_start: date = Field(..., description="Period start")
    period_end: date = Field(..., description="Period end")


class ResourceAllocationUpdate(BaseModel):
    """Request to update a resource allocation."""

    model_config = ConfigDict(from_attributes=True)

    resource_type: ResourceType | None = Field(None, description="Resource type")
    description: str | None = Field(None, description="Description")
    quantity: float | None = Field(None, ge=0, description="Quantity")
    unit_cost: float | None = Field(None, ge=0, description="Unit cost")
    period_start: date | None = Field(None, description="Period start")
    period_end: date | None = Field(None, description="Period end")
    approved: bool | None = Field(None, description="Approved status")
    approved_by: str | None = Field(None, description="Approver name")


class PortfolioPrioritizationCreate(BaseModel):
    """Request to create a portfolio prioritization assessment."""

    model_config = ConfigDict(from_attributes=True)

    program_id: str = Field(..., description="Program ID")
    strategic_alignment_score: float = Field(ge=0, le=100, description="Strategic alignment (0-100)")
    probability_of_success: float = Field(ge=0, le=100, description="POS (%)")
    npv_estimate: float = Field(description="NPV in millions USD")
    peak_revenue_estimate: float = Field(ge=0, description="Peak revenue in millions USD")
    unmet_need_score: float = Field(ge=0, le=100, description="Unmet need (0-100)")
    competitive_position_score: float = Field(ge=0, le=100, description="Competitive position (0-100)")
    assessed_by: str = Field(..., description="Assessor name or committee")


class RiskRegisterCreate(BaseModel):
    """Request to register a new risk."""

    model_config = ConfigDict(from_attributes=True)

    program_id: str = Field(..., description="Program ID")
    risk_description: str = Field(..., description="Risk description")
    category: RiskCategory = Field(..., description="Risk category")
    probability: float = Field(ge=0, le=1, description="Probability (0-1)")
    impact: float = Field(ge=1, le=5, description="Impact severity (1-5)")
    mitigation_plan: str = Field(..., description="Mitigation plan")
    owner: str = Field(..., description="Risk owner")
    target_resolution_date: date | None = Field(None, description="Target resolution date")


class RiskRegisterUpdate(BaseModel):
    """Request to update a risk register entry."""

    model_config = ConfigDict(from_attributes=True)

    risk_description: str | None = Field(None, description="Risk description")
    category: RiskCategory | None = Field(None, description="Risk category")
    probability: float | None = Field(None, ge=0, le=1, description="Probability")
    impact: float | None = Field(None, ge=1, le=5, description="Impact")
    mitigation_plan: str | None = Field(None, description="Mitigation plan")
    owner: str | None = Field(None, description="Risk owner")
    status: RiskStatus | None = Field(None, description="Risk status")
    target_resolution_date: date | None = Field(None, description="Target resolution date")


# ---------------------------------------------------------------------------
# List responses
# ---------------------------------------------------------------------------


class ProgramListResponse(BaseModel):
    """List of programs."""

    model_config = ConfigDict(from_attributes=True)

    items: list[Program] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class StageGateListResponse(BaseModel):
    """List of stage gates."""

    model_config = ConfigDict(from_attributes=True)

    items: list[StageGate] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class TeamMemberListResponse(BaseModel):
    """List of team members."""

    model_config = ConfigDict(from_attributes=True)

    items: list[TeamMember] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class ResourceAllocationListResponse(BaseModel):
    """List of resource allocations."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ResourceAllocation] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class PortfolioPrioritizationListResponse(BaseModel):
    """List of portfolio prioritizations."""

    model_config = ConfigDict(from_attributes=True)

    items: list[PortfolioPrioritization] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


class RiskRegisterListResponse(BaseModel):
    """List of risk register entries."""

    model_config = ConfigDict(from_attributes=True)

    items: list[RiskRegister] = Field(default_factory=list)
    total: int = Field(ge=0, description="Total matching records")


# ---------------------------------------------------------------------------
# Portfolio dashboard
# ---------------------------------------------------------------------------


class PortfolioDashboard(BaseModel):
    """Executive portfolio dashboard summary."""

    model_config = ConfigDict(from_attributes=True)

    metrics: GovernanceMetrics = Field(..., description="Aggregated governance metrics")
    programs: list[Program] = Field(default_factory=list, description="All active programs")
    upcoming_gates: list[StageGate] = Field(
        default_factory=list, description="Stage gates in next 90 days"
    )
    top_risks: list[RiskRegister] = Field(
        default_factory=list, description="Top risks by score"
    )
    priority_rankings: list[PortfolioPrioritization] = Field(
        default_factory=list, description="Portfolio priority rankings"
    )
