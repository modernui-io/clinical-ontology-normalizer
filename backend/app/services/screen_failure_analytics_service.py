"""Screen Failure Analytics Service (VP-Product-3).

Tracks screening outcomes and produces analytics that help trial sites
understand *why* patients fail screening and identify near-miss patients
who might qualify with updated criteria or additional data.

Usage:
    from app.services.screen_failure_analytics_service import (
        get_screen_failure_analytics_service,
    )

    svc = get_screen_failure_analytics_service()
    record = svc.record_screening_outcome(...)
    report = svc.get_failure_analytics(trial_id)
"""

from __future__ import annotations

import logging
import threading
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.schemas.screen_failure import (
    CriteriaDifficulty,
    CriteriaDifficultyReport,
    CriterionType,
    DailyTrend,
    FailingCriterion,
    FailureAnalyticsReport,
    FailureByType,
    FunnelStage,
    NearMissPatient,
    NearMissReport,
    RecruitmentFunnel,
    ScreeningOutcome,
    ScreeningRecord,
    TopFailingCriterion,
)

logger = logging.getLogger(__name__)


class ScreenFailureAnalyticsService:
    """In-memory analytics engine for screen-failure tracking.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._records: list[ScreeningRecord] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_screening_outcome(
        self,
        trial_id: str,
        patient_id: str,
        outcome: ScreeningOutcome | str,
        failing_criteria: list[FailingCriterion] | list[dict] | None = None,
        metadata: dict | None = None,
        *,
        match_score: float | None = None,
        timestamp: datetime | None = None,
    ) -> ScreeningRecord:
        """Persist a single screening outcome.

        Parameters
        ----------
        trial_id:
            The trial that was screened.
        patient_id:
            The patient who was screened.
        outcome:
            ``ScreeningOutcome`` enum or its string value.
        failing_criteria:
            List of ``FailingCriterion`` objects *or* plain dicts with
            ``criterion_name`` and optional ``criterion_type`` / ``details``.
        metadata:
            Arbitrary extra data to attach to the record.
        match_score:
            Overall match score from the screening engine.
        timestamp:
            Override the recording timestamp (defaults to *now*).

        Returns
        -------
        ScreeningRecord
            The persisted record.
        """
        if isinstance(outcome, str):
            outcome = ScreeningOutcome(outcome)

        # Normalise failing_criteria from dicts if needed
        normalised: list[FailingCriterion] = []
        for item in (failing_criteria or []):
            if isinstance(item, dict):
                ctype = item.get("criterion_type", "other")
                if isinstance(ctype, str):
                    try:
                        ctype = CriterionType(ctype)
                    except ValueError:
                        ctype = CriterionType.OTHER
                normalised.append(FailingCriterion(
                    criterion_name=item["criterion_name"],
                    criterion_type=ctype,
                    details=item.get("details"),
                ))
            else:
                normalised.append(item)

        record = ScreeningRecord(
            id=str(uuid4()),
            trial_id=trial_id,
            patient_id=patient_id,
            outcome=outcome,
            failing_criteria=normalised,
            match_score=match_score,
            timestamp=timestamp or datetime.now(timezone.utc),
            metadata=metadata,
        )

        with self._lock:
            self._records.append(record)

        logger.debug(
            "Recorded screening outcome: trial=%s patient=%s outcome=%s failures=%d",
            trial_id,
            patient_id,
            outcome.value,
            len(normalised),
        )
        return record

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _filter_records(
        self,
        trial_id: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[ScreeningRecord]:
        """Return records for *trial_id* within the optional date range."""
        with self._lock:
            results = [r for r in self._records if r.trial_id == trial_id]
        if date_from:
            results = [r for r in results if r.timestamp >= date_from]
        if date_to:
            results = [r for r in results if r.timestamp <= date_to]
        return results

    # ------------------------------------------------------------------
    # Failure Analytics
    # ------------------------------------------------------------------

    def get_failure_analytics(
        self,
        trial_id: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        *,
        top_n: int = 10,
    ) -> FailureAnalyticsReport:
        """Build a comprehensive failure-analytics report for *trial_id*.

        Includes:
        - Counts by outcome
        - Top N failing criteria
        - Failure distribution by criterion type
        - Daily failure trend
        - Near-miss count (patients failing exactly 1 criterion)
        """
        records = self._filter_records(trial_id, date_from, date_to)

        total_screened = len(records)
        total_eligible = sum(1 for r in records if r.outcome == ScreeningOutcome.ELIGIBLE)
        total_ineligible = sum(1 for r in records if r.outcome == ScreeningOutcome.INELIGIBLE)
        total_pending = sum(1 for r in records if r.outcome == ScreeningOutcome.PENDING)
        total_error = sum(1 for r in records if r.outcome == ScreeningOutcome.ERROR)
        failure_rate = total_ineligible / total_screened if total_screened > 0 else 0.0

        # --- Top failing criteria ---
        criterion_counter: Counter[str] = Counter()
        criterion_types: dict[str, CriterionType] = {}
        for r in records:
            if r.outcome == ScreeningOutcome.INELIGIBLE:
                for fc in r.failing_criteria:
                    criterion_counter[fc.criterion_name] += 1
                    criterion_types[fc.criterion_name] = fc.criterion_type

        top_failing = [
            TopFailingCriterion(
                criterion_name=name,
                criterion_type=criterion_types.get(name, CriterionType.OTHER),
                failure_count=count,
                failure_rate=count / total_screened if total_screened > 0 else 0.0,
            )
            for name, count in criterion_counter.most_common(top_n)
        ]

        # --- Failure by type ---
        type_counter: Counter[CriterionType] = Counter()
        for r in records:
            if r.outcome == ScreeningOutcome.INELIGIBLE:
                for fc in r.failing_criteria:
                    type_counter[fc.criterion_type] += 1
        total_type_failures = sum(type_counter.values())

        failure_by_type = [
            FailureByType(
                criterion_type=ct,
                failure_count=count,
                percentage=(count / total_type_failures * 100) if total_type_failures > 0 else 0.0,
            )
            for ct, count in type_counter.most_common()
        ]

        # --- Daily trend ---
        day_screened: Counter[str] = Counter()
        day_failed: Counter[str] = Counter()
        for r in records:
            day_key = r.timestamp.strftime("%Y-%m-%d")
            day_screened[day_key] += 1
            if r.outcome == ScreeningOutcome.INELIGIBLE:
                day_failed[day_key] += 1

        daily_trend = []
        for day in sorted(day_screened.keys()):
            s = day_screened[day]
            f = day_failed[day]
            daily_trend.append(DailyTrend(
                date=day,
                screened=s,
                failed=f,
                failure_rate=f / s if s > 0 else 0.0,
            ))

        # --- Near-miss count ---
        near_miss_count = sum(
            1 for r in records
            if r.outcome == ScreeningOutcome.INELIGIBLE and len(r.failing_criteria) == 1
        )

        return FailureAnalyticsReport(
            trial_id=trial_id,
            date_from=date_from,
            date_to=date_to,
            total_screened=total_screened,
            total_eligible=total_eligible,
            total_ineligible=total_ineligible,
            total_pending=total_pending,
            total_error=total_error,
            failure_rate=round(failure_rate, 4),
            top_failing_criteria=top_failing,
            failure_by_type=failure_by_type,
            daily_trend=daily_trend,
            near_miss_count=near_miss_count,
        )

    # ------------------------------------------------------------------
    # Recruitment Funnel
    # ------------------------------------------------------------------

    def get_trial_funnel(
        self,
        trial_id: str,
        *,
        enrolled_count: int | None = None,
    ) -> RecruitmentFunnel:
        """Build a recruitment funnel for *trial_id*.

        Stages:
        1. Screened (total records for this trial)
        2. Passed Inclusion (eligible + ineligible due to exclusion only
           -- approximated as total - those failing inclusion criteria)
        3. Passed Exclusion (eligible patients)
        4. Eligible (same as passed exclusion for now)
        5. Enrolled (optional, provided externally)
        """
        records = self._filter_records(trial_id)

        total_screened = len(records)
        total_eligible = sum(1 for r in records if r.outcome == ScreeningOutcome.ELIGIBLE)
        total_ineligible = sum(1 for r in records if r.outcome == ScreeningOutcome.INELIGIBLE)

        # Patients who failed at least one inclusion criterion (demographic/condition/measurement)
        # We count patients who have at least one failing criterion with type in
        # {condition, demographic, measurement} as inclusion failures.
        # Others failed exclusion criteria only.
        inclusion_fail_types = {CriterionType.CONDITION, CriterionType.DEMOGRAPHIC, CriterionType.MEASUREMENT}
        failed_inclusion_count = 0
        for r in records:
            if r.outcome == ScreeningOutcome.INELIGIBLE:
                # Check if any failing criteria are of inclusion type
                has_inclusion_failure = any(
                    fc.criterion_type in inclusion_fail_types
                    for fc in r.failing_criteria
                )
                if has_inclusion_failure:
                    failed_inclusion_count += 1

        passed_inclusion = total_screened - failed_inclusion_count
        passed_exclusion = total_eligible
        enrolled = enrolled_count if enrolled_count is not None else 0

        stages: list[FunnelStage] = []

        # Stage 1: Screened
        stages.append(FunnelStage(
            name="Screened",
            count=total_screened,
            conversion_rate=None,  # First stage has no conversion
        ))

        # Stage 2: Passed Inclusion
        stages.append(FunnelStage(
            name="Passed Inclusion",
            count=passed_inclusion,
            conversion_rate=passed_inclusion / total_screened if total_screened > 0 else 0.0,
        ))

        # Stage 3: Passed Exclusion
        stages.append(FunnelStage(
            name="Passed Exclusion",
            count=passed_exclusion,
            conversion_rate=passed_exclusion / passed_inclusion if passed_inclusion > 0 else 0.0,
        ))

        # Stage 4: Eligible
        stages.append(FunnelStage(
            name="Eligible",
            count=total_eligible,
            conversion_rate=total_eligible / passed_exclusion if passed_exclusion > 0 else 0.0,
        ))

        # Stage 5: Enrolled
        stages.append(FunnelStage(
            name="Enrolled",
            count=enrolled,
            conversion_rate=enrolled / total_eligible if total_eligible > 0 else 0.0,
        ))

        return RecruitmentFunnel(trial_id=trial_id, stages=stages)

    # ------------------------------------------------------------------
    # Criteria Difficulty
    # ------------------------------------------------------------------

    def get_criteria_difficulty(
        self,
        trial_id: str,
    ) -> CriteriaDifficultyReport:
        """Compute per-criterion pass rate for *trial_id*.

        For every criterion name that appears in any failing_criteria list,
        counts how many screened patients passed vs failed that criterion.
        """
        records = self._filter_records(trial_id)

        # Collect all unique criterion names and their types
        criterion_names: dict[str, CriterionType] = {}
        for r in records:
            for fc in r.failing_criteria:
                criterion_names[fc.criterion_name] = fc.criterion_type

        if not criterion_names:
            return CriteriaDifficultyReport(trial_id=trial_id, criteria=[])

        total_evaluated = len(records)

        # Count failures per criterion
        fail_counts: Counter[str] = Counter()
        for r in records:
            for fc in r.failing_criteria:
                fail_counts[fc.criterion_name] += 1

        criteria: list[CriteriaDifficulty] = []
        for name, ctype in sorted(criterion_names.items()):
            fc = fail_counts[name]
            pc = total_evaluated - fc
            criteria.append(CriteriaDifficulty(
                criterion_name=name,
                criterion_type=ctype,
                pass_count=pc,
                fail_count=fc,
                unknown_count=0,
                pass_rate=pc / total_evaluated if total_evaluated > 0 else 0.0,
            ))

        # Sort by pass_rate ascending (hardest first)
        criteria.sort(key=lambda c: c.pass_rate)

        return CriteriaDifficultyReport(trial_id=trial_id, criteria=criteria)

    # ------------------------------------------------------------------
    # Near-Miss Patients
    # ------------------------------------------------------------------

    def get_near_miss_patients(
        self,
        trial_id: str,
        max_failures: int = 2,
    ) -> NearMissReport:
        """Find patients who failed by at most *max_failures* criteria.

        These are high-value leads: they almost qualified and might
        qualify with updated criteria, a protocol amendment, or
        additional clinical data.
        """
        records = self._filter_records(trial_id)

        patients: list[NearMissPatient] = []
        for r in records:
            if (
                r.outcome == ScreeningOutcome.INELIGIBLE
                and 1 <= len(r.failing_criteria) <= max_failures
            ):
                patients.append(NearMissPatient(
                    patient_id=r.patient_id,
                    failing_criteria=list(r.failing_criteria),
                    match_score=r.match_score,
                    num_failing=len(r.failing_criteria),
                ))

        # Sort by fewest failures first, then by match_score descending
        patients.sort(key=lambda p: (p.num_failing, -(p.match_score or 0.0)))

        return NearMissReport(
            trial_id=trial_id,
            max_failures=max_failures,
            patients=patients,
            total=len(patients),
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_records(
        self,
        trial_id: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[ScreeningRecord]:
        """Return raw screening records (useful for tests/debugging)."""
        return self._filter_records(trial_id, date_from, date_to)

    def clear(self) -> None:
        """Remove all records (useful for tests)."""
        with self._lock:
            self._records.clear()

    def get_stats(self) -> dict[str, Any]:
        """Service-level statistics."""
        with self._lock:
            total = len(self._records)
            trials = len({r.trial_id for r in self._records})
        return {
            "total_records": total,
            "trials_tracked": trials,
        }


# ==============================================================================
# Singleton
# ==============================================================================

_service: ScreenFailureAnalyticsService | None = None
_service_lock = threading.Lock()


def get_screen_failure_analytics_service() -> ScreenFailureAnalyticsService:
    """Get singleton screen-failure analytics service instance."""
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = ScreenFailureAnalyticsService()
                logger.info("Initialized ScreenFailureAnalyticsService")
    return _service
