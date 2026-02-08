"""Temporal Eligibility Service for clinical trial patient matching.

CMO-1.3: Temporal Reasoning Validation

Filters ClinicalFacts by temporal constraints before eligibility evaluation.
A 2-year-old HbA1c reading should not qualify a patient for a trial requiring
recent lab work.  This service applies time-window, active-status, date-range,
and duration filters to clinical facts.

Usage:
    from app.services.temporal_eligibility_service import TemporalEligibilityService

    svc = TemporalEligibilityService()
    result = svc.apply_temporal_filter(facts, criterion)
    # result.matched_fact_ids -> facts within the window
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

from sqlalchemy import and_, cast, or_, select, Float as SAFloat
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical_fact import ClinicalFact
from app.schemas.base import Assertion, Domain
from app.schemas.temporal import (
    MissingDatePolicy,
    TemporalCriterion,
    TemporalDirection,
    TemporalFilterConfig,
    TemporalReferencePoint,
    TemporalResult,
    TemporalStatus,
)

logger = logging.getLogger(__name__)


class TemporalEligibilityService:
    """Applies temporal reasoning to clinical trial eligibility screening.

    This service filters ClinicalFacts by time windows, active status,
    date ranges, and duration requirements.  It is consumed by the
    TrialEligibilityService as an optional pre-filter step.
    """

    def __init__(self, config: TemporalFilterConfig | None = None):
        self.config = config or TemporalFilterConfig()

    # ======================================================================
    # Public API
    # ======================================================================

    def apply_temporal_filter(
        self,
        facts: Sequence[Any],
        criterion: TemporalCriterion,
        *,
        reference_date: datetime | None = None,
    ) -> TemporalResult:
        """Filter a list of fact-like objects by temporal criterion.

        Each fact object must have:
          - id (str): unique identifier
          - start_date (datetime | None): when the fact was recorded/started
          - end_date (datetime | None): when the fact ended (if applicable)

        Args:
            facts: Sequence of ClinicalFact (or duck-typed objects with
                   id, start_date, end_date).
            criterion: The temporal constraint to apply.
            reference_date: Override for "now" or the reference point.
                            Defaults to datetime.now(timezone.utc).

        Returns:
            TemporalResult with matched/excluded/undated fact IDs and status.
        """
        ref = reference_date or datetime.now(timezone.utc)
        window_start, window_end = self._compute_window(criterion, ref)

        matched: list[str] = []
        excluded: list[str] = []
        undated: list[str] = []

        for fact in facts:
            fact_id = str(fact.id)
            fact_start = getattr(fact, "start_date", None)
            fact_end = getattr(fact, "end_date", None)

            classification = self._classify_fact(
                fact_start=fact_start,
                fact_end=fact_end,
                criterion=criterion,
                window_start=window_start,
                window_end=window_end,
                ref=ref,
            )

            if classification == "matched":
                matched.append(fact_id)
            elif classification == "excluded":
                excluded.append(fact_id)
            else:
                undated.append(fact_id)

        status = self._determine_status(
            matched=matched,
            excluded=excluded,
            undated=undated,
            criterion=criterion,
        )

        evidence = self._build_evidence_text(
            criterion=criterion,
            matched_count=len(matched),
            excluded_count=len(excluded),
            undated_count=len(undated),
            window_start=window_start,
            window_end=window_end,
            total=len(facts),
        )

        return TemporalResult(
            criterion=criterion,
            status=status,
            matched_fact_ids=matched,
            excluded_fact_ids=excluded,
            undated_fact_ids=undated,
            total_facts_evaluated=len(facts),
            evidence=evidence,
            window_start=window_start,
            window_end=window_end,
        )

    async def evaluate_temporal_criterion(
        self,
        patient_id: str,
        criterion: TemporalCriterion,
        session: AsyncSession,
        *,
        domain: Domain | None = None,
        concept_terms: list[str] | None = None,
        reference_date: datetime | None = None,
    ) -> TemporalResult:
        """Evaluate a temporal criterion against the database.

        Queries ClinicalFacts for the patient, filters by domain and
        concept terms if provided, then applies the temporal filter.

        Args:
            patient_id: The patient to evaluate.
            criterion: The temporal constraint.
            session: AsyncSession for database queries.
            domain: Optional domain filter (e.g., MEASUREMENT).
            concept_terms: Optional concept name search terms.
            reference_date: Override for reference point.

        Returns:
            TemporalResult with status and evidence.
        """
        filters = [
            ClinicalFact.patient_id == patient_id,
            ClinicalFact.assertion == Assertion.PRESENT,
        ]

        if domain is not None:
            filters.append(ClinicalFact.domain == domain)

        if concept_terms:
            like_clauses = [
                ClinicalFact.concept_name.ilike(f"%{term}%")
                for term in concept_terms
            ]
            filters.append(or_(*like_clauses))

        stmt = select(ClinicalFact).where(and_(*filters))
        result = await session.execute(stmt)
        facts = result.scalars().all()

        if not facts:
            return TemporalResult(
                criterion=criterion,
                status=TemporalStatus.INSUFFICIENT_DATA,
                total_facts_evaluated=0,
                evidence="No clinical facts found for this patient matching the criterion",
            )

        return self.apply_temporal_filter(
            facts, criterion, reference_date=reference_date,
        )

    # ======================================================================
    # Internal helpers
    # ======================================================================

    def _compute_window(
        self,
        criterion: TemporalCriterion,
        ref: datetime,
    ) -> tuple[datetime | None, datetime | None]:
        """Compute the start and end of the temporal window.

        Returns (window_start, window_end).  Either may be None when
        the window is open-ended (e.g., ACTIVE direction).
        """
        direction = criterion.direction

        if direction == TemporalDirection.WITHIN_LAST:
            days = criterion.time_window_days if criterion.time_window_days is not None else self.config.default_lookback_days
            window_start = ref - timedelta(days=days)
            window_end = ref
            return window_start, window_end

        if direction == TemporalDirection.BEFORE:
            days = criterion.time_window_days if criterion.time_window_days is not None else 0
            cutoff = ref - timedelta(days=days)
            return None, cutoff

        if direction == TemporalDirection.AFTER:
            days = criterion.time_window_days if criterion.time_window_days is not None else 0
            cutoff = ref - timedelta(days=days)
            return cutoff, None

        if direction == TemporalDirection.BETWEEN:
            return criterion.start_date, criterion.end_date

        if direction == TemporalDirection.ACTIVE:
            # For active: no explicit window; we check end_date logic
            return None, None

        return None, None

    def _classify_fact(
        self,
        *,
        fact_start: datetime | None,
        fact_end: datetime | None,
        criterion: TemporalCriterion,
        window_start: datetime | None,
        window_end: datetime | None,
        ref: datetime,
    ) -> str:
        """Classify a fact as 'matched', 'excluded', or 'undated'."""
        direction = criterion.direction

        # --- ACTIVE direction: check that condition has no end date or end > now ---
        if direction == TemporalDirection.ACTIVE:
            # If there's an end_date and it's in the past, it's resolved/inactive
            if fact_end is not None:
                end_aware = self._ensure_tz(fact_end)
                if end_aware < ref:
                    return "excluded"
            # Active means no end date or end date in the future
            # We also need to check min_duration_days if specified
            if criterion.min_duration_days is not None and fact_start is not None:
                start_aware = self._ensure_tz(fact_start)
                duration = (ref - start_aware).days
                if duration < criterion.min_duration_days:
                    return "excluded"
            # If start_date is missing, we can't verify duration but the
            # condition is still considered active
            return "matched"

        # --- Duration-based criteria (e.g., "diagnosed for >= 1 year") ---
        if criterion.min_duration_days is not None:
            if fact_start is None:
                return self._undated_or_policy(criterion)
            start_aware = self._ensure_tz(fact_start)
            duration = (ref - start_aware).days
            if duration < criterion.min_duration_days:
                return "excluded"

        # --- For WITHIN_LAST, BEFORE, AFTER, BETWEEN: need a date to evaluate ---
        # Use start_date as the primary date for temporal filtering
        fact_date = fact_start
        if fact_date is None:
            return self._undated_or_policy(criterion)

        fact_date_aware = self._ensure_tz(fact_date)

        # --- WITHIN_LAST ---
        if direction == TemporalDirection.WITHIN_LAST:
            if window_start is not None and window_end is not None:
                if window_start <= fact_date_aware <= window_end:
                    return "matched"
                return "excluded"

        # --- BEFORE ---
        if direction == TemporalDirection.BEFORE:
            if window_end is not None:
                if fact_date_aware <= window_end:
                    return "matched"
                return "excluded"

        # --- AFTER ---
        if direction == TemporalDirection.AFTER:
            if window_start is not None:
                if fact_date_aware >= window_start:
                    return "matched"
                return "excluded"

        # --- BETWEEN ---
        if direction == TemporalDirection.BETWEEN:
            in_range = True
            if window_start is not None:
                if fact_date_aware < self._ensure_tz(window_start):
                    in_range = False
            if window_end is not None:
                if fact_date_aware > self._ensure_tz(window_end):
                    in_range = False
            return "matched" if in_range else "excluded"

        return "matched"

    def _undated_or_policy(self, criterion: TemporalCriterion) -> str:
        """Apply missing-date policy to classify a fact without dates."""
        policy = criterion.missing_date_policy
        if self.config.require_dates:
            return "undated"
        if policy == MissingDatePolicy.INCLUDE:
            return "matched"
        if policy == MissingDatePolicy.EXCLUDE:
            return "excluded"
        return "undated"  # UNKNOWN policy

    @staticmethod
    def _ensure_tz(dt: datetime) -> datetime:
        """Ensure a datetime is timezone-aware (UTC if naive)."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def _determine_status(
        self,
        *,
        matched: list[str],
        excluded: list[str],
        undated: list[str],
        criterion: TemporalCriterion,
    ) -> TemporalStatus:
        """Determine the overall temporal evaluation status."""
        total = len(matched) + len(excluded) + len(undated)

        if total == 0:
            return TemporalStatus.INSUFFICIENT_DATA

        if matched:
            return TemporalStatus.MET

        # All facts are undated
        if undated and not excluded:
            return TemporalStatus.UNKNOWN

        # Some undated, some excluded, none matched
        if undated and excluded:
            return TemporalStatus.UNKNOWN

        # All excluded, none matched
        return TemporalStatus.NOT_MET

    def _build_evidence_text(
        self,
        *,
        criterion: TemporalCriterion,
        matched_count: int,
        excluded_count: int,
        undated_count: int,
        window_start: datetime | None,
        window_end: datetime | None,
        total: int,
    ) -> str:
        """Build human-readable evidence text for the temporal result."""
        direction = criterion.direction

        if total == 0:
            return "No facts available for temporal evaluation"

        parts: list[str] = []

        if direction == TemporalDirection.WITHIN_LAST:
            days = criterion.time_window_days or self.config.default_lookback_days
            parts.append(f"Temporal filter: within last {days} days")
        elif direction == TemporalDirection.ACTIVE:
            parts.append("Temporal filter: currently active (no end date or end date in future)")
        elif direction == TemporalDirection.BEFORE:
            days = criterion.time_window_days or 0
            parts.append(f"Temporal filter: before {days} days ago")
        elif direction == TemporalDirection.AFTER:
            days = criterion.time_window_days or 0
            parts.append(f"Temporal filter: after {days} days ago")
        elif direction == TemporalDirection.BETWEEN:
            start_str = window_start.strftime("%Y-%m-%d") if window_start else "unbounded"
            end_str = window_end.strftime("%Y-%m-%d") if window_end else "unbounded"
            parts.append(f"Temporal filter: between {start_str} and {end_str}")

        if criterion.min_duration_days is not None:
            parts.append(f"Minimum duration: {criterion.min_duration_days} days")

        parts.append(
            f"{matched_count}/{total} facts within window, "
            f"{excluded_count} outside, {undated_count} undated"
        )

        return ". ".join(parts)
