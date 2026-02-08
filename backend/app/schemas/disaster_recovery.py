"""Pydantic schemas for Disaster Recovery Runbooks & RTO/RPO Management (VPE-7).

Defines disaster recovery runbooks, test results, metrics, and supporting
enumerations for clinical trial patient recruitment platform DR planning.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DisasterCategory(str, Enum):
    """Classification of disaster scenarios."""

    DATABASE_FAILURE = "DATABASE_FAILURE"
    APPLICATION_OUTAGE = "APPLICATION_OUTAGE"
    NETWORK_PARTITION = "NETWORK_PARTITION"
    DATA_CORRUPTION = "DATA_CORRUPTION"
    RANSOMWARE = "RANSOMWARE"
    CLOUD_REGION_FAILURE = "CLOUD_REGION_FAILURE"
    DNS_FAILURE = "DNS_FAILURE"
    CERTIFICATE_EXPIRY = "CERTIFICATE_EXPIRY"
    KEY_COMPROMISE = "KEY_COMPROMISE"
    THIRD_PARTY_OUTAGE = "THIRD_PARTY_OUTAGE"


class RunbookStatus(str, Enum):
    """Lifecycle status of a disaster recovery runbook."""

    DRAFT = "DRAFT"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    TESTED = "TESTED"
    OUTDATED = "OUTDATED"


class RecoveryTier(str, Enum):
    """Recovery tier based on RTO targets.

    TIER_1_CRITICAL: RTO < 1 hour
    TIER_2_HIGH:     RTO < 4 hours
    TIER_3_MEDIUM:   RTO < 24 hours
    TIER_4_LOW:      RTO < 72 hours
    """

    TIER_1_CRITICAL = "TIER_1_CRITICAL"
    TIER_2_HIGH = "TIER_2_HIGH"
    TIER_3_MEDIUM = "TIER_3_MEDIUM"
    TIER_4_LOW = "TIER_4_LOW"


class TestResult(str, Enum):
    """Outcome of a DR test execution."""

    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"


# ---------------------------------------------------------------------------
# Runbook Step
# ---------------------------------------------------------------------------


class RunbookStep(BaseModel):
    """A single step within a disaster recovery runbook."""

    model_config = ConfigDict(populate_by_name=True)

    step_number: int = Field(description="Execution order of this step")
    title: str = Field(description="Short title for the step")
    description: str = Field(description="Detailed description of the action")
    responsible_role: str = Field(description="Role responsible for execution")
    estimated_minutes: int = Field(description="Estimated time in minutes")
    commands: list[str] | None = Field(
        default=None, description="CLI commands to execute (optional)"
    )
    verification_criteria: str = Field(
        description="How to verify this step completed successfully"
    )
    rollback_instructions: str = Field(
        default="",
        description="How to rollback this step if it fails",
    )


# ---------------------------------------------------------------------------
# Disaster Recovery Runbook
# ---------------------------------------------------------------------------


class DisasterRecoveryRunbook(BaseModel):
    """Full disaster recovery runbook with steps, contacts, and test history."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="Unique runbook identifier")
    title: str = Field(description="Runbook title")
    category: DisasterCategory = Field(description="Disaster category")
    tier: RecoveryTier = Field(description="Recovery tier")
    status: RunbookStatus = Field(description="Current lifecycle status")
    rto_minutes: int = Field(description="Recovery Time Objective in minutes")
    rpo_minutes: int = Field(description="Recovery Point Objective in minutes")
    steps: list[RunbookStep] = Field(
        default_factory=list, description="Ordered recovery steps"
    )
    prerequisites: list[str] = Field(
        default_factory=list, description="Prerequisites before executing runbook"
    )
    communication_plan: list[str] = Field(
        default_factory=list,
        description="Communication steps during incident",
    )
    escalation_contacts: list[dict[str, str]] = Field(
        default_factory=list,
        description="Escalation contacts (name, role, phone, email)",
    )
    last_tested: datetime | None = Field(
        default=None, description="When runbook was last tested"
    )
    test_result: TestResult | None = Field(
        default=None, description="Result of the most recent test"
    )
    next_test_due: datetime | None = Field(
        default=None, description="When the next test is due"
    )
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    approved_by: str | None = Field(
        default=None, description="Who approved the runbook"
    )
    version: int = Field(default=1, description="Runbook version number")


# ---------------------------------------------------------------------------
# DR Test Result
# ---------------------------------------------------------------------------


class DRTestResult(BaseModel):
    """Record of a single disaster recovery test execution."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="Unique test result identifier")
    runbook_id: str = Field(description="ID of the runbook tested")
    test_date: datetime = Field(description="When the test was conducted")
    tester: str = Field(description="Person who conducted the test")
    actual_rto_minutes: float = Field(
        description="Actual recovery time achieved in minutes"
    )
    actual_rpo_minutes: float = Field(
        description="Actual recovery point achieved in minutes"
    )
    rto_met: bool = Field(description="Whether the RTO target was met")
    rpo_met: bool = Field(description="Whether the RPO target was met")
    result: TestResult = Field(description="Overall test result")
    issues_found: list[str] = Field(
        default_factory=list, description="Issues discovered during test"
    )
    lessons_learned: list[str] = Field(
        default_factory=list, description="Lessons learned from test"
    )
    steps_completed: int = Field(
        description="Number of steps completed successfully"
    )
    total_steps: int = Field(
        description="Total number of steps in the runbook"
    )


# ---------------------------------------------------------------------------
# DR Metrics
# ---------------------------------------------------------------------------


class DRMetrics(BaseModel):
    """Aggregate metrics for the DR program."""

    model_config = ConfigDict(populate_by_name=True)

    total_runbooks: int = Field(description="Total number of runbooks")
    by_category: dict[str, int] = Field(
        default_factory=dict,
        description="Runbook counts by disaster category",
    )
    by_tier: dict[str, int] = Field(
        default_factory=dict,
        description="Runbook counts by recovery tier",
    )
    by_status: dict[str, int] = Field(
        default_factory=dict,
        description="Runbook counts by status",
    )
    tested_percentage: float = Field(
        description="Percentage of runbooks that have been tested"
    )
    rto_compliance_rate: float = Field(
        description="Percentage of tests meeting RTO target"
    )
    rpo_compliance_rate: float = Field(
        description="Percentage of tests meeting RPO target"
    )
    mean_actual_rto: float = Field(
        description="Mean actual RTO across all tests (minutes)"
    )
    mean_actual_rpo: float = Field(
        description="Mean actual RPO across all tests (minutes)"
    )
    overdue_tests_count: int = Field(
        description="Number of runbooks with overdue tests"
    )
    last_full_dr_test: datetime | None = Field(
        default=None,
        description="When the last full DR test was conducted",
    )


# ---------------------------------------------------------------------------
# Validation Result
# ---------------------------------------------------------------------------


class RunbookValidation(BaseModel):
    """Result of validating a runbook for completeness."""

    model_config = ConfigDict(populate_by_name=True)

    runbook_id: str = Field(description="Runbook that was validated")
    is_valid: bool = Field(description="Whether runbook passes all checks")
    issues: list[str] = Field(
        default_factory=list,
        description="List of validation issues found",
    )
    checked_at: datetime = Field(description="When validation was performed")


# ---------------------------------------------------------------------------
# Communication Plan Response
# ---------------------------------------------------------------------------


class CommunicationPlanResponse(BaseModel):
    """Escalation and communication details for a runbook."""

    model_config = ConfigDict(populate_by_name=True)

    runbook_id: str = Field(description="Runbook identifier")
    runbook_title: str = Field(description="Runbook title")
    category: DisasterCategory = Field(description="Disaster category")
    tier: RecoveryTier = Field(description="Recovery tier")
    communication_plan: list[str] = Field(
        default_factory=list,
        description="Communication steps",
    )
    escalation_contacts: list[dict[str, str]] = Field(
        default_factory=list,
        description="Escalation contacts",
    )


# ---------------------------------------------------------------------------
# Request / Response Wrappers
# ---------------------------------------------------------------------------


class RunbookCreateRequest(BaseModel):
    """Request to create a new DR runbook."""

    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(description="Runbook title")
    category: DisasterCategory = Field(description="Disaster category")
    tier: RecoveryTier = Field(description="Recovery tier")
    rto_minutes: int = Field(description="Recovery Time Objective in minutes")
    rpo_minutes: int = Field(description="Recovery Point Objective in minutes")
    steps: list[RunbookStep] = Field(
        default_factory=list, description="Ordered recovery steps"
    )
    prerequisites: list[str] = Field(
        default_factory=list, description="Prerequisites"
    )
    communication_plan: list[str] = Field(
        default_factory=list, description="Communication steps"
    )
    escalation_contacts: list[dict[str, str]] = Field(
        default_factory=list, description="Escalation contacts"
    )
    approved_by: str | None = Field(default=None, description="Approver")


class RunbookUpdateRequest(BaseModel):
    """Request to update an existing DR runbook."""

    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, description="Updated title")
    status: RunbookStatus | None = Field(default=None, description="Updated status")
    rto_minutes: int | None = Field(default=None, description="Updated RTO")
    rpo_minutes: int | None = Field(default=None, description="Updated RPO")
    steps: list[RunbookStep] | None = Field(
        default=None, description="Updated steps"
    )
    prerequisites: list[str] | None = Field(
        default=None, description="Updated prerequisites"
    )
    communication_plan: list[str] | None = Field(
        default=None, description="Updated communication plan"
    )
    escalation_contacts: list[dict[str, str]] | None = Field(
        default=None, description="Updated escalation contacts"
    )
    approved_by: str | None = Field(default=None, description="Updated approver")


class RecordTestRequest(BaseModel):
    """Request to record a DR test result."""

    model_config = ConfigDict(populate_by_name=True)

    tester: str = Field(description="Person who conducted the test")
    actual_rto_minutes: float = Field(description="Actual recovery time in minutes")
    actual_rpo_minutes: float = Field(description="Actual recovery point in minutes")
    result: TestResult = Field(description="Overall test result")
    issues_found: list[str] = Field(
        default_factory=list, description="Issues discovered"
    )
    lessons_learned: list[str] = Field(
        default_factory=list, description="Lessons learned"
    )
    steps_completed: int = Field(description="Steps completed successfully")
    total_steps: int = Field(description="Total steps in runbook")


class RunbookListResponse(BaseModel):
    """Paginated list of runbooks."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[DisasterRecoveryRunbook] = Field(description="Runbook list")
    total: int = Field(description="Total matching runbooks")


class TestHistoryResponse(BaseModel):
    """Test result history for a runbook."""

    model_config = ConfigDict(populate_by_name=True)

    runbook_id: str = Field(description="Runbook identifier")
    tests: list[DRTestResult] = Field(description="Test results")
    total: int = Field(description="Total test count")
