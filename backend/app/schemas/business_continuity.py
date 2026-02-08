"""Pydantic schemas for Business Continuity Testing (COO-2).

Defines tabletop exercise scenarios, exercise tracking records,
recovery procedure validation, and BC program metrics for clinical
trial patient recruitment platform resilience.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    """Scenario severity classification."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExerciseStatus(str, Enum):
    """Exercise lifecycle status."""

    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


# ---------------------------------------------------------------------------
# Recovery Step
# ---------------------------------------------------------------------------


class RecoveryStep(BaseModel):
    """A single step in a recovery procedure."""

    order: int = Field(description="Step execution order")
    action: str = Field(description="Description of the recovery action")
    responsible_role: str = Field(description="Role responsible for this step")
    estimated_duration_minutes: int = Field(
        default=15, description="Estimated duration in minutes"
    )
    documentation_ref: str | None = Field(
        default=None, description="Reference to supporting documentation"
    )
    requires_approval: bool = Field(
        default=False, description="Whether this step requires management approval"
    )


# ---------------------------------------------------------------------------
# Success Criterion
# ---------------------------------------------------------------------------


class SuccessCriterion(BaseModel):
    """Criteria for determining if an exercise/recovery was successful."""

    id: str = Field(description="Criterion identifier")
    description: str = Field(description="What constitutes success")
    measurement: str = Field(description="How to measure/verify")
    met: bool | None = Field(
        default=None, description="Whether criterion was met (null=not evaluated)"
    )


# ---------------------------------------------------------------------------
# Tabletop Scenario
# ---------------------------------------------------------------------------


class TabletopScenario(BaseModel):
    """A pre-defined tabletop exercise scenario."""

    id: str = Field(description="Unique scenario identifier")
    title: str = Field(description="Scenario title")
    description: str = Field(description="Detailed scenario description")
    severity: Severity = Field(description="Severity classification")
    affected_systems: list[str] = Field(
        default_factory=list, description="Systems/services affected"
    )
    expected_rto: str = Field(
        description="Expected Recovery Time Objective (e.g. '4 hours')"
    )
    expected_rpo: str = Field(
        description="Expected Recovery Point Objective (e.g. '1 hour')"
    )
    recovery_steps: list[RecoveryStep] = Field(
        default_factory=list, description="Ordered recovery procedure steps"
    )
    roles_involved: list[str] = Field(
        default_factory=list, description="Roles required during recovery"
    )
    success_criteria: list[SuccessCriterion] = Field(
        default_factory=list, description="Success criteria for the exercise"
    )

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Action Item
# ---------------------------------------------------------------------------


class ActionItem(BaseModel):
    """An action item arising from an exercise."""

    id: str = Field(description="Action item unique identifier")
    description: str = Field(description="What needs to be done")
    assignee: str = Field(description="Person/role assigned")
    due_date: datetime | None = Field(
        default=None, description="Due date for completion"
    )
    status: str = Field(
        default="OPEN", description="Status: OPEN, IN_PROGRESS, CLOSED"
    )
    closed_at: datetime | None = Field(
        default=None, description="When the item was closed"
    )


# ---------------------------------------------------------------------------
# Exercise Record
# ---------------------------------------------------------------------------


class ExerciseCreate(BaseModel):
    """Request schema to schedule a new exercise."""

    scenario_id: str = Field(description="ID of the tabletop scenario")
    scheduled_date: datetime = Field(description="When the exercise is scheduled")
    participants: list[str] = Field(
        default_factory=list, description="List of participant names/roles"
    )
    notes: str | None = Field(
        default=None, description="Additional planning notes"
    )


class ExerciseUpdate(BaseModel):
    """Request schema to update an exercise (conduct, record results)."""

    status: ExerciseStatus | None = Field(
        default=None, description="Updated exercise status"
    )
    conducted_date: datetime | None = Field(
        default=None, description="When the exercise was actually conducted"
    )
    participants: list[str] | None = Field(
        default=None, description="Updated participant list"
    )
    actual_rto: str | None = Field(
        default=None, description="Actual Recovery Time Objective achieved"
    )
    actual_rpo: str | None = Field(
        default=None, description="Actual Recovery Point Objective achieved"
    )
    findings: list[str] | None = Field(
        default=None, description="Key findings from the exercise"
    )
    action_items: list[ActionItem] | None = Field(
        default=None, description="Action items arising from the exercise"
    )
    success_criteria_results: list[SuccessCriterion] | None = Field(
        default=None, description="Evaluated success criteria"
    )
    notes: str | None = Field(
        default=None, description="Additional notes"
    )


class ExerciseResponse(BaseModel):
    """Full exercise record response."""

    id: str
    scenario_id: str
    scenario_title: str
    scheduled_date: datetime
    conducted_date: datetime | None = None
    participants: list[str] = Field(default_factory=list)
    status: ExerciseStatus
    actual_rto: str | None = None
    actual_rpo: str | None = None
    findings: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    success_criteria_results: list[SuccessCriterion] = Field(default_factory=list)
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExerciseListResponse(BaseModel):
    """Paginated list of exercises."""

    exercises: list[ExerciseResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Procedure Validation
# ---------------------------------------------------------------------------


class ProcedureCheck(BaseModel):
    """Result of validating a single aspect of a recovery procedure."""

    check_name: str = Field(description="Name of the validation check")
    passed: bool = Field(description="Whether the check passed")
    details: str = Field(description="Details about the check result")


class ProcedureValidationResult(BaseModel):
    """Result of validating recovery procedures for a scenario."""

    scenario_id: str = Field(description="Scenario that was validated")
    scenario_title: str = Field(description="Title of the scenario")
    validated_at: datetime = Field(description="When validation was performed")
    overall_valid: bool = Field(
        description="Whether all recovery procedures are valid"
    )
    checks: list[ProcedureCheck] = Field(
        default_factory=list, description="Individual check results"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Recommendations for improvement"
    )


class ProcedureValidationReport(BaseModel):
    """Full report of procedure validation across all scenarios."""

    validated_at: datetime
    total_scenarios: int
    valid_scenarios: int
    invalid_scenarios: int
    results: list[ProcedureValidationResult]


# ---------------------------------------------------------------------------
# BC Metrics
# ---------------------------------------------------------------------------


class ScenarioCoverage(BaseModel):
    """Coverage information for a single scenario."""

    scenario_id: str
    scenario_title: str
    severity: Severity
    total_exercises: int
    completed_exercises: int
    last_exercise_date: datetime | None = None
    days_since_last_exercise: int | None = None
    rto_compliant: bool | None = None
    rpo_compliant: bool | None = None


class BCMetrics(BaseModel):
    """Business continuity program metrics."""

    total_scenarios: int = Field(description="Total number of BC scenarios")
    total_exercises: int = Field(description="Total number of exercises")
    completed_exercises: int = Field(description="Number of completed exercises")
    exercises_last_quarter: int = Field(
        description="Exercises completed in the last 90 days"
    )
    exercise_frequency_target: str = Field(
        default="Quarterly per scenario",
        description="Target exercise frequency",
    )
    exercise_frequency_met: bool = Field(
        description="Whether the quarterly exercise target is met"
    )
    rto_compliance_rate: float = Field(
        description="Percentage of exercises meeting RTO"
    )
    rpo_compliance_rate: float = Field(
        description="Percentage of exercises meeting RPO"
    )
    total_action_items: int = Field(
        description="Total action items from all exercises"
    )
    open_action_items: int = Field(
        description="Action items still open"
    )
    closed_action_items: int = Field(
        description="Action items that have been closed"
    )
    action_item_closure_rate: float = Field(
        description="Percentage of action items that are closed"
    )
    scenario_coverage: list[ScenarioCoverage] = Field(
        default_factory=list, description="Coverage per scenario"
    )
    overall_readiness_score: float = Field(
        description="Overall BC readiness score (0-100)"
    )
