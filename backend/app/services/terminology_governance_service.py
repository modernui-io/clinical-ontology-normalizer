"""Terminology Governance Workflow Service.

Dir-CI-3.1: Terminology Governance Workflow - routes low-confidence OMOP
mappings to a review queue for terminology expert review. Tracks review
history, reviewer decisions, and provides aggregate statistics.

In production this would persist to the database; for now it uses
in-memory storage with a singleton pattern.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.terminology_governance import (
    ReviewDecision,
    ReviewItemResponse,
    ReviewStats,
    ReviewStatus,
)

logger = logging.getLogger(__name__)

# Default confidence threshold below which mappings are auto-submitted
DEFAULT_CONFIDENCE_THRESHOLD = 0.7


class TerminologyGovernanceService:
    """Service for managing the terminology mapping review workflow.

    Maintains an in-memory queue of review items, supporting submission,
    approval, rejection, escalation, filtering, and statistics.
    """

    def __init__(self, confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> None:
        self.confidence_threshold = confidence_threshold
        # In-memory store: review_id -> ReviewItemResponse
        self._reviews: dict[str, ReviewItemResponse] = {}

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def submit_for_review(
        self,
        mention_id: str,
        candidate_id: str,
        concept_name: str,
        concept_id: int,
        confidence: float,
        domain: str,
        reason: str = "",
        submitted_by: str = "system",
    ) -> ReviewItemResponse:
        """Submit a mapping for terminology review.

        Args:
            mention_id: ID of the mention.
            candidate_id: ID of the concept candidate mapping.
            concept_name: Name of the OMOP concept.
            concept_id: OMOP concept ID.
            confidence: Mapping confidence score.
            domain: OMOP domain (condition, drug, etc.).
            reason: Reason for submission.
            submitted_by: User or system that submitted.

        Returns:
            The created ReviewItemResponse.
        """
        review_id = str(uuid4())
        now = datetime.now(timezone.utc)

        item = ReviewItemResponse(
            id=review_id,
            mention_id=mention_id,
            candidate_id=candidate_id,
            concept_name=concept_name,
            concept_id=concept_id,
            confidence=confidence,
            domain=domain,
            status=ReviewStatus.PENDING,
            reason=reason,
            submitted_at=now,
            submitted_by=submitted_by,
            reviewed_at=None,
            reviewer_id=None,
            notes=None,
            suggested_concept_id=None,
        )

        self._reviews[review_id] = item
        logger.info(
            "Submitted mapping for review: review_id=%s, concept=%s (%.2f)",
            review_id,
            concept_name,
            confidence,
        )
        return item

    def auto_submit_if_low_confidence(
        self,
        mention_id: str,
        candidate_id: str,
        concept_name: str,
        concept_id: int,
        confidence: float,
        domain: str,
    ) -> ReviewItemResponse | None:
        """Auto-submit a mapping for review if confidence is below threshold.

        Called by the mapping pipeline after creating a concept candidate.

        Args:
            mention_id: ID of the mention.
            candidate_id: ID of the concept candidate mapping.
            concept_name: Name of the OMOP concept.
            concept_id: OMOP concept ID.
            confidence: Mapping confidence score.
            domain: OMOP domain.

        Returns:
            ReviewItemResponse if submitted, None if confidence is sufficient.
        """
        if confidence < self.confidence_threshold:
            return self.submit_for_review(
                mention_id=mention_id,
                candidate_id=candidate_id,
                concept_name=concept_name,
                concept_id=concept_id,
                confidence=confidence,
                domain=domain,
                reason=f"Auto-submitted: confidence {confidence:.2f} below threshold {self.confidence_threshold:.2f}",
                submitted_by="system",
            )
        return None

    def get_review_queue(
        self,
        status: ReviewStatus | None = None,
        domain: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ReviewItemResponse]:
        """Get items from the review queue with optional filtering.

        Args:
            status: Filter by review status.
            domain: Filter by OMOP domain.
            limit: Maximum number of items to return.
            offset: Number of items to skip.

        Returns:
            List of ReviewItemResponse matching the filters.
        """
        items = list(self._reviews.values())

        # Apply filters
        if status is not None:
            items = [i for i in items if i.status == status]
        if domain is not None:
            items = [i for i in items if i.domain == domain]

        # Sort by submitted_at descending (newest first)
        items.sort(key=lambda i: i.submitted_at, reverse=True)

        # Apply pagination
        return items[offset : offset + limit]

    def get_review_by_id(self, review_id: str) -> ReviewItemResponse | None:
        """Get a single review item by ID.

        Args:
            review_id: The review item ID.

        Returns:
            ReviewItemResponse or None if not found.
        """
        return self._reviews.get(review_id)

    def approve_mapping(
        self,
        review_id: str,
        reviewer_id: str,
        notes: str = "",
    ) -> ReviewItemResponse | None:
        """Approve a mapping in the review queue.

        Args:
            review_id: ID of the review item.
            reviewer_id: ID of the reviewer.
            notes: Optional reviewer notes.

        Returns:
            Updated ReviewItemResponse, or None if not found.
        """
        item = self._reviews.get(review_id)
        if item is None:
            return None

        now = datetime.now(timezone.utc)
        updated = item.model_copy(
            update={
                "status": ReviewStatus.APPROVED,
                "reviewed_at": now,
                "reviewer_id": reviewer_id,
                "notes": notes,
            }
        )
        self._reviews[review_id] = updated

        logger.info(
            "Mapping approved: review_id=%s by reviewer=%s",
            review_id,
            reviewer_id,
        )
        return updated

    def reject_mapping(
        self,
        review_id: str,
        reviewer_id: str,
        reason: str = "",
        suggested_concept_id: int | None = None,
    ) -> ReviewItemResponse | None:
        """Reject a mapping in the review queue.

        Args:
            review_id: ID of the review item.
            reviewer_id: ID of the reviewer.
            reason: Reason for rejection.
            suggested_concept_id: Alternative OMOP concept ID suggestion.

        Returns:
            Updated ReviewItemResponse, or None if not found.
        """
        item = self._reviews.get(review_id)
        if item is None:
            return None

        now = datetime.now(timezone.utc)
        updated = item.model_copy(
            update={
                "status": ReviewStatus.REJECTED,
                "reviewed_at": now,
                "reviewer_id": reviewer_id,
                "notes": reason,
                "suggested_concept_id": suggested_concept_id,
            }
        )
        self._reviews[review_id] = updated

        logger.info(
            "Mapping rejected: review_id=%s by reviewer=%s, suggested=%s",
            review_id,
            reviewer_id,
            suggested_concept_id,
        )
        return updated

    def escalate_mapping(
        self,
        review_id: str,
        reviewer_id: str,
        reason: str = "",
    ) -> ReviewItemResponse | None:
        """Escalate a mapping for senior review.

        Args:
            review_id: ID of the review item.
            reviewer_id: ID of the reviewer escalating.
            reason: Reason for escalation.

        Returns:
            Updated ReviewItemResponse, or None if not found.
        """
        item = self._reviews.get(review_id)
        if item is None:
            return None

        now = datetime.now(timezone.utc)
        updated = item.model_copy(
            update={
                "status": ReviewStatus.ESCALATED,
                "reviewed_at": now,
                "reviewer_id": reviewer_id,
                "notes": reason,
            }
        )
        self._reviews[review_id] = updated

        logger.info(
            "Mapping escalated: review_id=%s by reviewer=%s",
            review_id,
            reviewer_id,
        )
        return updated

    def get_review_stats(self) -> ReviewStats:
        """Compute aggregate review statistics.

        Returns:
            ReviewStats with counts and average review time.
        """
        items = list(self._reviews.values())
        total = len(items)
        pending = sum(1 for i in items if i.status == ReviewStatus.PENDING)
        approved = sum(1 for i in items if i.status == ReviewStatus.APPROVED)
        rejected = sum(1 for i in items if i.status == ReviewStatus.REJECTED)
        escalated = sum(1 for i in items if i.status == ReviewStatus.ESCALATED)

        # Average review time (only for reviewed items)
        review_times: list[float] = []
        for item in items:
            if item.reviewed_at is not None:
                delta = item.reviewed_at - item.submitted_at
                review_times.append(delta.total_seconds() / 3600.0)

        avg_review_hours = (
            sum(review_times) / len(review_times) if review_times else 0.0
        )

        return ReviewStats(
            total=total,
            pending=pending,
            approved=approved,
            rejected=rejected,
            escalated=escalated,
            avg_review_hours=round(avg_review_hours, 2),
        )

    def clear(self) -> None:
        """Clear all review items (for testing)."""
        self._reviews.clear()


# ------------------------------------------------------------------
# Module-level singleton
# ------------------------------------------------------------------

_service: TerminologyGovernanceService | None = None


def get_terminology_governance_service() -> TerminologyGovernanceService:
    """Get or create the terminology governance service singleton."""
    global _service
    if _service is None:
        _service = TerminologyGovernanceService()
    return _service


def reset_terminology_governance_service() -> None:
    """Reset the singleton (for testing)."""
    global _service
    _service = None
