"""False Negative Monitoring Service for clinical trial screening.

CMO-6: False Negative Monitoring (P2 - clinical safety critical)

A false negative occurs when a patient IS eligible for a clinical trial but
the screening engine says they are NOT eligible. This is worse than a false
positive because the patient misses a potentially life-saving trial.

This service is a MONITORING system -- it does NOT change screening results.
It records every screening outcome, allows clinicians to flag potential false
negatives, and provides aggregated reports for quality monitoring.

Data is stored in-memory (dict-based singleton) to avoid requiring a DB
migration at this stage.

Usage:
    from app.services.fn_monitoring_service import get_fn_monitoring_service

    fn_service = get_fn_monitoring_service()
    fn_service.record_screening_result(trial_id, patient_id, eligibility_result)
    fn_service.flag_potential_false_negative(trial_id, patient_id, reason, flagged_by)
    report = fn_service.get_fn_report(trial_id)
"""

from __future__ import annotations

import logging
import threading
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from app.schemas.fn_monitoring import (
    FNFlag,
    FNReport,
    MissReason,
    UnknownCriteriaAnalysis,
)
from app.schemas.trial import PatientEligibility

logger = logging.getLogger(__name__)

# Dedicated logger for false-negative safety events.  These are emitted at
# WARNING level so they surface in monitoring dashboards alongside the
# existing patient_safety logger.
fn_safety_logger = logging.getLogger("patient_safety.fn_monitoring")


class _ScreeningRecord:
    """Internal record of a single screening outcome."""

    __slots__ = ("trial_id", "patient_id", "eligible", "match_score",
                 "criteria_details", "screened_at")

    def __init__(
        self,
        trial_id: str,
        patient_id: str,
        eligible: bool,
        match_score: float,
        criteria_details: list[dict[str, Any]],
    ):
        self.trial_id = trial_id
        self.patient_id = patient_id
        self.eligible = eligible
        self.match_score = match_score
        self.criteria_details = criteria_details
        self.screened_at = datetime.now(timezone.utc)


class FalseNegativeMonitoringService:
    """Monitors screening outcomes and tracks potential false negatives.

    Thread-safe singleton.  All data is held in-memory (no DB migration
    required).

    Key invariant: this service NEVER modifies screening results.  It is
    purely observational.
    """

    def __init__(self) -> None:
        # trial_id -> {patient_id -> _ScreeningRecord}
        self._screening_records: dict[str, dict[str, _ScreeningRecord]] = {}
        # trial_id -> {patient_id -> FNFlag}
        self._fn_flags: dict[str, dict[str, FNFlag]] = {}
        self._lock = threading.Lock()

    # =========================================================================
    # Recording
    # =========================================================================

    def record_screening_result(
        self,
        trial_id: str,
        patient_id: str,
        result: PatientEligibility,
    ) -> None:
        """Record a screening outcome for monitoring purposes.

        Called after every call to check_patient_eligibility.  Overwrites
        any previous result for the same (trial_id, patient_id) pair so
        that the latest screening is always stored.
        """
        criteria_details = [
            {
                "criterion_name": cr.criterion_name,
                "criterion_type": cr.criterion_type,
                "status": cr.status,
                "confidence": cr.confidence,
            }
            for cr in (result.criteria_details or [])
        ]

        record = _ScreeningRecord(
            trial_id=trial_id,
            patient_id=patient_id,
            eligible=result.eligible,
            match_score=result.match_score,
            criteria_details=criteria_details,
        )

        with self._lock:
            if trial_id not in self._screening_records:
                self._screening_records[trial_id] = {}
            self._screening_records[trial_id][patient_id] = record

        logger.debug(
            "FN-monitor: recorded screening for patient %s in trial %s "
            "(eligible=%s, score=%.3f)",
            patient_id, trial_id, result.eligible, result.match_score,
        )

    # =========================================================================
    # Flagging
    # =========================================================================

    def flag_potential_false_negative(
        self,
        trial_id: str,
        patient_id: str,
        reason: str,
        flagged_by: str,
    ) -> FNFlag:
        """Flag a patient as a potential false negative for a trial.

        A clinician believes this patient IS eligible but the system said
        they were NOT.  This does not change the screening result -- it
        records the clinician's assessment for quality monitoring.

        If the same (trial_id, patient_id) is flagged again, the new flag
        replaces the old one.

        Returns the created FNFlag.
        """
        flag = FNFlag(
            trial_id=trial_id,
            patient_id=patient_id,
            reason=reason,
            flagged_by=flagged_by,
            flagged_at=datetime.now(timezone.utc),
        )

        with self._lock:
            if trial_id not in self._fn_flags:
                self._fn_flags[trial_id] = {}
            self._fn_flags[trial_id][patient_id] = flag

        # Emit to the patient_safety logger so this surfaces in dashboards
        fn_safety_logger.warning(
            "FN FLAG: Clinician %s flagged patient %s as potential false "
            "negative for trial %s. Reason: %s",
            flagged_by, patient_id, trial_id, reason,
            extra={
                "event_type": "FalseNegativeFlag",
                "trial_id": trial_id,
                "patient_id": patient_id,
                "flagged_by": flagged_by,
                "reason": reason,
            },
        )

        return flag

    # =========================================================================
    # Reporting
    # =========================================================================

    def get_fn_report(self, trial_id: str) -> FNReport:
        """Generate an aggregated false-negative monitoring report for a trial.

        Returns:
            FNReport with total_screened, total_flagged, fn_rate,
            top_miss_reasons, and unknown_criteria_gaps.
        """
        with self._lock:
            records = self._screening_records.get(trial_id, {})
            flags = self._fn_flags.get(trial_id, {})

        total_screened = len(records)
        total_flagged = len(flags)
        fn_rate = total_flagged / total_screened if total_screened > 0 else 0.0

        # --- Top miss reasons (from FN flags) ---
        reason_counter: Counter[str] = Counter()
        for flag in flags.values():
            reason_counter[flag.reason] += 1

        top_miss_reasons = [
            MissReason(reason=reason, count=count)
            for reason, count in reason_counter.most_common(10)
        ]

        # --- Unknown criteria gaps ---
        unknown_gaps = self.analyze_unknown_criteria(trial_id)

        # Log a warning if FN rate exceeds 5% threshold
        if fn_rate > 0.05 and total_screened >= 10:
            fn_safety_logger.warning(
                "FN RATE ALERT: Trial %s has FN rate of %.1f%% "
                "(%d flagged / %d screened). Exceeds 5%% threshold.",
                trial_id, fn_rate * 100, total_flagged, total_screened,
                extra={
                    "event_type": "FalseNegativeRateAlert",
                    "trial_id": trial_id,
                    "fn_rate": fn_rate,
                    "total_screened": total_screened,
                    "total_flagged": total_flagged,
                },
            )

        return FNReport(
            trial_id=trial_id,
            total_screened=total_screened,
            total_flagged=total_flagged,
            fn_rate=round(fn_rate, 4),
            top_miss_reasons=top_miss_reasons,
            unknown_criteria_gaps=unknown_gaps,
        )

    # =========================================================================
    # Unknown Criteria Analysis
    # =========================================================================

    def analyze_unknown_criteria(
        self,
        trial_id: str,
    ) -> list[UnknownCriteriaAnalysis]:
        """Find criteria that evaluate to UNKNOWN most often for a trial.

        Criteria with high UNKNOWN rates indicate data completeness gaps --
        the system lacks data to evaluate whether the patient meets the
        criterion.  These are the highest-risk criteria for false negatives
        because we cannot say "not met" with confidence.

        Returns a list ordered by unknown_rate descending.
        """
        with self._lock:
            records = self._screening_records.get(trial_id, {})

        if not records:
            return []

        # criterion_name -> {total: int, unknown: int}
        criterion_stats: dict[str, dict[str, int]] = {}

        for record in records.values():
            for cr in record.criteria_details:
                name = cr["criterion_name"]
                if name not in criterion_stats:
                    criterion_stats[name] = {"total": 0, "unknown": 0}
                criterion_stats[name]["total"] += 1
                if cr["status"] == "UNKNOWN":
                    criterion_stats[name]["unknown"] += 1

        results = []
        for name, stats in criterion_stats.items():
            total = stats["total"]
            unknown = stats["unknown"]
            if total == 0:
                continue
            rate = unknown / total
            results.append(
                UnknownCriteriaAnalysis(
                    criterion_description=name,
                    unknown_count=unknown,
                    total_evaluations=total,
                    unknown_rate=round(rate, 4),
                )
            )

        # Sort by unknown_rate descending, then by unknown_count descending
        results.sort(key=lambda x: (-x.unknown_rate, -x.unknown_count))
        return results

    # =========================================================================
    # Utilities
    # =========================================================================

    def get_flags_for_trial(self, trial_id: str) -> list[FNFlag]:
        """Return all FN flags for a trial, ordered by flagged_at descending."""
        with self._lock:
            flags = self._fn_flags.get(trial_id, {})
        return sorted(flags.values(), key=lambda f: f.flagged_at, reverse=True)

    def get_screening_count(self, trial_id: str) -> int:
        """Return the number of unique patients screened for a trial."""
        with self._lock:
            return len(self._screening_records.get(trial_id, {}))

    def clear(self) -> None:
        """Clear all monitoring data.  For testing only."""
        with self._lock:
            self._screening_records.clear()
            self._fn_flags.clear()


# ==============================================================================
# Singleton
# ==============================================================================

_fn_service: FalseNegativeMonitoringService | None = None
_fn_lock = threading.Lock()


def get_fn_monitoring_service() -> FalseNegativeMonitoringService:
    """Get singleton false-negative monitoring service instance."""
    global _fn_service
    if _fn_service is None:
        with _fn_lock:
            if _fn_service is None:
                _fn_service = FalseNegativeMonitoringService()
                logger.info("Initialized FalseNegativeMonitoringService")
    return _fn_service
