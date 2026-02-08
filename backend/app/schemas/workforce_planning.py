"""Pydantic v2 schemas for COO-4: Workforce Capacity Planning.

Defines schemas for team members, capacity requirements, hiring plans,
workforce metrics, capacity projections, utilization reports, and skill
gap analysis for a clinical trial patient recruitment platform.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Department(str, Enum):
    """Organisational department."""

    ENGINEERING = "engineering"
    CLINICAL_OPS = "clinical_ops"
    DATA_SCIENCE = "data_science"
    PRODUCT = "product"
    COMPLIANCE = "compliance"
    SALES = "sales"
    SUPPORT = "support"
    EXECUTIVE = "executive"


class SkillLevel(str, Enum):
    """Individual contributor seniority band."""

    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    PRINCIPAL = "principal"


class Priority(str, Enum):
    """Priority level for capacity requirements."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class HiringStatus(str, Enum):
    """Hiring pipeline status."""

    OPEN = "open"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    FILLED = "filled"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Team Member
# ---------------------------------------------------------------------------


class TeamMember(BaseModel):
    """A single team member in the organisation."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique identifier for this team member")
    name: str = Field(..., description="Full name")
    department: Department
    role: str = Field(..., description="Job title / role")
    skill_level: SkillLevel
    fte_equivalent: float = Field(
        ..., ge=0.0, le=1.0, description="FTE fraction (0.0-1.0)"
    )
    hire_date: date = Field(..., description="Date the member joined")
    annual_cost: float = Field(..., ge=0, description="Fully loaded annual cost ($)")
    utilization_pct: float = Field(
        ..., ge=0, le=100, description="Current utilization percentage"
    )
    certifications: list[str] = Field(
        default_factory=list, description="Professional certifications held"
    )
    can_handle_phi: bool = Field(
        default=False, description="Whether the member is cleared for PHI access"
    )


class TeamMemberCreate(BaseModel):
    """Request body to create a new team member."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    department: Department
    role: str
    skill_level: SkillLevel
    fte_equivalent: float = Field(..., ge=0.0, le=1.0)
    hire_date: date
    annual_cost: float = Field(..., ge=0)
    utilization_pct: float = Field(default=80.0, ge=0, le=100)
    certifications: list[str] = Field(default_factory=list)
    can_handle_phi: bool = False


class TeamMemberUpdate(BaseModel):
    """Request body to update an existing team member."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = None
    department: Department | None = None
    role: str | None = None
    skill_level: SkillLevel | None = None
    fte_equivalent: float | None = Field(default=None, ge=0.0, le=1.0)
    hire_date: date | None = None
    annual_cost: float | None = Field(default=None, ge=0)
    utilization_pct: float | None = Field(default=None, ge=0, le=100)
    certifications: list[str] | None = None
    can_handle_phi: bool | None = None


class TeamMemberListResponse(BaseModel):
    """Paginated list of team members."""

    total: int = 0
    members: list[TeamMember] = []


# ---------------------------------------------------------------------------
# Capacity Requirement
# ---------------------------------------------------------------------------


class CapacityRequirement(BaseModel):
    """A staffing gap / capacity requirement."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique requirement identifier")
    department: Department
    role: str = Field(..., description="Role needed")
    skill_level: SkillLevel
    required_fte: float = Field(..., ge=0, description="FTE required for this role")
    current_fte: float = Field(..., ge=0, description="FTE currently filled")
    gap: float = Field(..., description="FTE gap (required - current)")
    priority: Priority = Field(default=Priority.MEDIUM)
    justification: str = Field(default="", description="Business justification")
    timeline_months: int = Field(
        default=3, ge=1, description="Target fill timeline in months"
    )


class CapacityRequirementCreate(BaseModel):
    """Request body to create a capacity requirement."""

    model_config = ConfigDict(from_attributes=True)

    department: Department
    role: str
    skill_level: SkillLevel
    required_fte: float = Field(..., ge=0)
    current_fte: float = Field(..., ge=0)
    priority: Priority = Field(default=Priority.MEDIUM)
    justification: str = ""
    timeline_months: int = Field(default=3, ge=1)


class CapacityRequirementUpdate(BaseModel):
    """Request body to update an existing capacity requirement."""

    model_config = ConfigDict(from_attributes=True)

    department: Department | None = None
    role: str | None = None
    skill_level: SkillLevel | None = None
    required_fte: float | None = Field(default=None, ge=0)
    current_fte: float | None = Field(default=None, ge=0)
    priority: Priority | None = None
    justification: str | None = None
    timeline_months: int | None = Field(default=None, ge=1)


class CapacityRequirementListResponse(BaseModel):
    """List of capacity requirements."""

    total: int = 0
    requirements: list[CapacityRequirement] = []


# ---------------------------------------------------------------------------
# Hiring Plan
# ---------------------------------------------------------------------------


class HiringPlan(BaseModel):
    """A single hiring plan / requisition."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Unique hiring plan identifier")
    department: Department
    role: str = Field(..., description="Role to fill")
    skill_level: SkillLevel
    planned_start: date = Field(..., description="Target start date")
    estimated_salary: float = Field(..., ge=0, description="Estimated annual salary ($)")
    status: HiringStatus = Field(default=HiringStatus.OPEN)
    requisition_id: str = Field(default="", description="External ATS requisition ID")


class HiringPlanCreate(BaseModel):
    """Request body to create a hiring plan."""

    model_config = ConfigDict(from_attributes=True)

    department: Department
    role: str
    skill_level: SkillLevel
    planned_start: date
    estimated_salary: float = Field(..., ge=0)
    status: HiringStatus = Field(default=HiringStatus.OPEN)
    requisition_id: str = ""


class HiringPlanUpdate(BaseModel):
    """Request body to update a hiring plan."""

    model_config = ConfigDict(from_attributes=True)

    department: Department | None = None
    role: str | None = None
    skill_level: SkillLevel | None = None
    planned_start: date | None = None
    estimated_salary: float | None = Field(default=None, ge=0)
    status: HiringStatus | None = None
    requisition_id: str | None = None


class HiringPlanListResponse(BaseModel):
    """List of hiring plans."""

    total: int = 0
    plans: list[HiringPlan] = []


# ---------------------------------------------------------------------------
# Workforce Metrics
# ---------------------------------------------------------------------------


class WorkforceMetrics(BaseModel):
    """Workforce KPIs / dashboard metrics."""

    total_headcount: int = 0
    total_fte: float = 0.0
    by_department: dict[str, int] = Field(
        default_factory=dict, description="Headcount by department"
    )
    avg_utilization: float = Field(default=0.0, description="Average utilization %")
    capacity_gap_total_fte: float = Field(
        default=0.0, description="Total FTE gap across all requirements"
    )
    hiring_pipeline_count: int = Field(
        default=0, description="Number of active hiring plans (non-filled/cancelled)"
    )
    avg_tenure_months: float = Field(default=0.0, description="Average tenure in months")
    phi_certified_count: int = Field(
        default=0, description="Number of team members cleared for PHI"
    )
    cost_per_fte: float = Field(default=0.0, description="Average annual cost per FTE ($)")
    projected_headcount_12mo: int = Field(
        default=0, description="Projected headcount in 12 months"
    )


# ---------------------------------------------------------------------------
# Capacity Projection
# ---------------------------------------------------------------------------


class CapacityProjection(BaseModel):
    """Monthly capacity projection point."""

    month: int = Field(..., ge=1, description="Month number from now")
    required_fte: float = Field(..., ge=0)
    available_fte: float = Field(..., ge=0)
    gap: float = Field(..., description="required - available")
    hires_needed: int = Field(..., ge=0)


class CapacityProjectionResponse(BaseModel):
    """Multi-month capacity projection."""

    months: int = 0
    projections: list[CapacityProjection] = []
    total_hires_needed: int = 0


# ---------------------------------------------------------------------------
# Utilization Report
# ---------------------------------------------------------------------------


class DepartmentUtilization(BaseModel):
    """Utilization summary for a single department."""

    department: Department
    headcount: int = 0
    total_fte: float = 0.0
    avg_utilization: float = 0.0
    min_utilization: float = 0.0
    max_utilization: float = 0.0
    over_utilized_count: int = Field(
        default=0, description="Members with utilization > 90%"
    )
    under_utilized_count: int = Field(
        default=0, description="Members with utilization < 50%"
    )


class UtilizationReport(BaseModel):
    """Organisation-wide utilization report."""

    overall_avg_utilization: float = 0.0
    departments: list[DepartmentUtilization] = []
    total_over_utilized: int = 0
    total_under_utilized: int = 0


# ---------------------------------------------------------------------------
# Skill Gap
# ---------------------------------------------------------------------------


class SkillGap(BaseModel):
    """A single identified skill gap."""

    department: Department
    role: str
    skill_level: SkillLevel
    required_fte: float = 0.0
    current_fte: float = 0.0
    gap_fte: float = 0.0
    priority: Priority = Priority.MEDIUM
    recommendation: str = ""


class SkillGapReport(BaseModel):
    """Skill gap analysis report."""

    total_gaps: int = 0
    critical_gaps: int = 0
    gaps: list[SkillGap] = []


# ---------------------------------------------------------------------------
# Department Capacity
# ---------------------------------------------------------------------------


class DepartmentCapacity(BaseModel):
    """Capacity summary for a single department."""

    department: Department
    current_fte: float = 0.0
    required_fte: float = 0.0
    gap: float = 0.0
    headcount: int = 0
    open_reqs: int = 0
