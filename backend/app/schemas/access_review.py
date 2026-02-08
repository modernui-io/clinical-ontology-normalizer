"""Pydantic schemas for Access Review & Certification Management (CISO-11).

Defines periodic access review cycles, entitlements, review decisions,
metrics, and supporting enumerations for clinical trial patient recruitment
platform access governance.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class CycleType(str, Enum):
    """Frequency at which access reviews are conducted."""

    QUARTERLY = "QUARTERLY"
    SEMI_ANNUAL = "SEMI_ANNUAL"
    ANNUAL = "ANNUAL"


class CycleStatus(str, Enum):
    """Lifecycle status of an access review cycle."""

    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    OVERDUE = "OVERDUE"


class AccessLevel(str, Enum):
    """Granularity of access granted on a resource."""

    READ = "READ"
    WRITE = "WRITE"
    ADMIN = "ADMIN"
    OWNER = "OWNER"


class ReviewDecisionType(str, Enum):
    """Possible outcomes when a reviewer evaluates an entitlement."""

    CERTIFY = "CERTIFY"
    REVOKE = "REVOKE"
    MODIFY = "MODIFY"
    ESCALATE = "ESCALATE"


# ---------------------------------------------------------------------------
# Review Cycle
# ---------------------------------------------------------------------------


class ReviewCycle(BaseModel):
    """A periodic access review cycle."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="Unique cycle identifier")
    name: str = Field(description="Descriptive name for the review cycle")
    cycle_type: CycleType = Field(description="Frequency of this review cycle")
    status: CycleStatus = Field(description="Current lifecycle status")
    start_date: datetime = Field(description="When the cycle begins")
    end_date: datetime = Field(description="When the cycle is due to complete")
    reviewer: str = Field(description="Person responsible for conducting reviews")
    created_at: datetime = Field(description="Creation timestamp")


# ---------------------------------------------------------------------------
# Access Entitlement
# ---------------------------------------------------------------------------


class AccessEntitlement(BaseModel):
    """An access grant linking a user to a resource at a given level."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="Unique entitlement identifier")
    user_id: str = Field(description="User identifier")
    user_name: str = Field(description="Human-readable user name")
    user_role: str = Field(description="Role of the user (e.g. clinician, admin)")
    resource: str = Field(description="Resource or system being accessed")
    access_level: AccessLevel = Field(description="Level of access granted")
    granted_date: datetime = Field(description="When access was granted")
    granted_by: str = Field(description="Who approved this access")
    last_used: datetime | None = Field(
        default=None, description="When the access was last exercised"
    )
    justification: str = Field(
        default="", description="Business justification for access"
    )


# ---------------------------------------------------------------------------
# Review Decision
# ---------------------------------------------------------------------------


class ReviewDecision(BaseModel):
    """Outcome of reviewing a single entitlement within a cycle."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="Unique decision identifier")
    cycle_id: str = Field(description="Review cycle this decision belongs to")
    entitlement_id: str = Field(description="Entitlement being reviewed")
    decision: ReviewDecisionType = Field(description="Review decision")
    reviewer: str = Field(description="Person who made the decision")
    decided_at: datetime = Field(description="When the decision was made")
    comments: str = Field(default="", description="Reviewer comments")
    new_access_level: AccessLevel | None = Field(
        default=None,
        description="New access level if decision is MODIFY",
    )


# ---------------------------------------------------------------------------
# Access Review Metrics
# ---------------------------------------------------------------------------


class AccessReviewMetrics(BaseModel):
    """Aggregate metrics for the access review programme."""

    model_config = ConfigDict(populate_by_name=True)

    total_cycles: int = Field(description="Total number of review cycles")
    total_entitlements: int = Field(description="Total access entitlements tracked")
    certification_rate: float = Field(
        description="Percentage of decisions that certified access"
    )
    revocation_rate: float = Field(
        description="Percentage of decisions that revoked access"
    )
    avg_review_time_days: float = Field(
        description="Average time to complete a review cycle in days"
    )
    overdue_reviews: int = Field(
        description="Number of review cycles currently overdue"
    )
    by_decision: dict[str, int] = Field(
        default_factory=dict,
        description="Decision counts by type",
    )
    excessive_access_count: int = Field(
        description="Number of users flagged for excessive access"
    )


# ---------------------------------------------------------------------------
# Request / Response wrappers
# ---------------------------------------------------------------------------


class ReviewCycleCreateRequest(BaseModel):
    """Request to create a new review cycle."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(description="Cycle name")
    cycle_type: CycleType = Field(description="Review frequency")
    start_date: datetime = Field(description="Cycle start date")
    end_date: datetime = Field(description="Cycle end date")
    reviewer: str = Field(description="Reviewer name")


class ReviewCycleUpdateRequest(BaseModel):
    """Request to update a review cycle."""

    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, description="Updated name")
    status: CycleStatus | None = Field(default=None, description="Updated status")
    end_date: datetime | None = Field(default=None, description="Updated end date")
    reviewer: str | None = Field(default=None, description="Updated reviewer")


class EntitlementCreateRequest(BaseModel):
    """Request to create a new access entitlement."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(description="User identifier")
    user_name: str = Field(description="User name")
    user_role: str = Field(description="User role")
    resource: str = Field(description="Resource being accessed")
    access_level: AccessLevel = Field(description="Access level to grant")
    granted_by: str = Field(description="Approver name")
    justification: str = Field(default="", description="Business justification")


class DecisionSubmitRequest(BaseModel):
    """Request to submit a review decision for an entitlement."""

    model_config = ConfigDict(populate_by_name=True)

    entitlement_id: str = Field(description="Entitlement being reviewed")
    decision: ReviewDecisionType = Field(description="Review outcome")
    reviewer: str = Field(description="Reviewer name")
    comments: str = Field(default="", description="Reviewer comments")
    new_access_level: AccessLevel | None = Field(
        default=None,
        description="New access level if decision is MODIFY",
    )


class ReviewCycleListResponse(BaseModel):
    """Paginated list of review cycles."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[ReviewCycle] = Field(description="Review cycles")
    total: int = Field(description="Total matching cycles")


class EntitlementListResponse(BaseModel):
    """Paginated list of access entitlements."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[AccessEntitlement] = Field(description="Entitlements")
    total: int = Field(description="Total matching entitlements")


class DecisionListResponse(BaseModel):
    """Paginated list of review decisions."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[ReviewDecision] = Field(description="Review decisions")
    total: int = Field(description="Total matching decisions")


class ExcessiveAccessEntry(BaseModel):
    """A user flagged for having excessive access."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(description="User identifier")
    user_name: str = Field(description="User name")
    user_role: str = Field(description="User role")
    reasons: list[str] = Field(description="Reasons for the flag")
    entitlements: list[AccessEntitlement] = Field(
        description="Entitlements contributing to the flag"
    )


class ExcessiveAccessResponse(BaseModel):
    """List of users flagged for excessive access."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[ExcessiveAccessEntry] = Field(description="Flagged users")
    total: int = Field(description="Total flagged users")
