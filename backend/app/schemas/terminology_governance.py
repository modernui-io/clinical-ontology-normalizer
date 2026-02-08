"""Pydantic schemas for terminology governance workflow.

Dir-CI-3.1: Terminology Governance Workflow - schemas for mapping review
queue, review decisions, and review statistics. Supports human-in-the-loop
quality control for low-confidence OMOP concept mappings.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ReviewStatus(str, Enum):
    """Status of a mapping review item."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class ReviewDecisionType(str, Enum):
    """Type of review decision a reviewer can make."""

    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"


class ReviewItemResponse(BaseModel):
    """A mapping review item in the governance queue."""

    id: str = Field(..., description="Unique review item identifier")
    mention_id: str = Field(..., description="ID of the mention being reviewed")
    candidate_id: str = Field(..., description="ID of the concept candidate mapping")
    concept_name: str = Field(..., description="Name of the OMOP concept")
    concept_id: int = Field(..., description="OMOP concept ID")
    confidence: float = Field(..., description="Mapping confidence score (0.0-1.0)")
    domain: str = Field(..., description="OMOP domain (condition, drug, etc.)")
    status: ReviewStatus = Field(..., description="Current review status")
    reason: str = Field("", description="Reason for submission to review")
    submitted_at: datetime = Field(..., description="When the item was submitted for review")
    submitted_by: str = Field(..., description="User who submitted for review")
    reviewed_at: datetime | None = Field(None, description="When the review decision was made")
    reviewer_id: str | None = Field(None, description="Reviewer who made the decision")
    notes: str | None = Field(None, description="Reviewer notes or comments")
    suggested_concept_id: int | None = Field(
        None, description="Alternative concept suggested by reviewer on rejection"
    )


class ReviewSubmission(BaseModel):
    """Request to submit a mapping for review."""

    mention_id: str = Field(..., description="ID of the mention to review")
    candidate_id: str = Field(..., description="ID of the concept candidate")
    reason: str = Field("", description="Reason for submitting to review")
    submitted_by: str = Field("system", description="User or system submitting the review")


class ReviewDecision(BaseModel):
    """A reviewer's decision on a mapping review item."""

    reviewer_id: str = Field(..., description="ID of the reviewer making the decision")
    notes: str = Field("", description="Reviewer notes or rationale")
    suggested_concept_id: int | None = Field(
        None,
        description="Alternative OMOP concept ID (for rejections with suggestions)",
    )


class ReviewStats(BaseModel):
    """Aggregate statistics for the review queue."""

    total: int = Field(..., description="Total number of review items")
    pending: int = Field(..., description="Number of items awaiting review")
    approved: int = Field(..., description="Number of approved mappings")
    rejected: int = Field(..., description="Number of rejected mappings")
    escalated: int = Field(..., description="Number of escalated items")
    avg_review_hours: float = Field(
        ..., description="Average time from submission to review (hours)"
    )
