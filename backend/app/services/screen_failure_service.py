"""Screen Failure Analytics Service.

Manages screening records and provides analytics for screen failure tracking.
"""

from __future__ import annotations

import logging
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
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

# Trial IDs
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ScreenFailureService:
    """In-memory screen failure analytics engine."""

    def __init__(self) -> None:
        self._records: dict[str, ScreeningRecord] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Seed data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Populate with 24 demo screening records across 3 trials."""
        now = datetime.now(timezone.utc)

        # ---- EYLEA: 10 records (3 eligible, 5 ineligible, 1 pending, 1 error) ----
        eylea_records = [
            ScreeningRecord(
                id="SCR-001",
                trial_id=EYLEA_TRIAL,
                patient_id="PAT-1001",
                outcome=ScreeningOutcome.ELIGIBLE,
                failing_criteria=[],
                match_score=0.95,
                timestamp=now - timedelta(days=20),
                metadata={"site": "SITE-101"},
            ),
            ScreeningRecord(
                id="SCR-002",
                trial_id=EYLEA_TRIAL,
                patient_id="PAT-1002",
                outcome=ScreeningOutcome.INELIGIBLE,
                failing_criteria=[
                    FailingCriterion(
                        criterion_name="HbA1c < 7.0",
                        criterion_type=CriterionType.MEASUREMENT,
                        details="Patient HbA1c was 8.2",
                    ),
                ],
                match_score=0.72,
                timestamp=now - timedelta(days=19),
            ),
            ScreeningRecord(
                id="SCR-003",
                trial_id=EYLEA_TRIAL,
                patient_id="PAT-1003",
                outcome=ScreeningOutcome.ELIGIBLE,
                failing_criteria=[],
                match_score=0.91,
                timestamp=now - timedelta(days=18),
            ),
            ScreeningRecord(
                id="SCR-004",
                trial_id=EYLEA_TRIAL,
                patient_id="PAT-1004",
                outcome=ScreeningOutcome.INELIGIBLE,
                failing_criteria=[
                    FailingCriterion(
                        criterion_name="Age >= 18",
                        criterion_type=CriterionType.DEMOGRAPHIC,
                        details="Patient is 16 years old",
                    ),
                    FailingCriterion(
                        criterion_name="HbA1c < 7.0",
                        criterion_type=CriterionType.MEASUREMENT,
                        details="Patient HbA1c was 7.5",
                    ),
                ],
                match_score=0.40,
                timestamp=now - timedelta(days=17),
            ),
            ScreeningRecord(
                id="SCR-005",
                trial_id=EYLEA_TRIAL,
                patient_id="PAT-1005",
                outcome=ScreeningOutcome.INELIGIBLE,
                failing_criteria=[
                    FailingCriterion(
                        criterion_name="No active cancer",
                        criterion_type=CriterionType.CONDITION,
                        details="Patient has active melanoma",
                    ),
                ],
                match_score=0.55,
                timestamp=now - timedelta(days=16),
            ),
            ScreeningRecord(
                id="SCR-006",
                trial_id=EYLEA_TRIAL,
                patient_id="PAT-1006",
                outcome=ScreeningOutcome.ELIGIBLE,
                failing_criteria=[],
                match_score=0.88,
                timestamp=now - timedelta(days=15),
            ),
            ScreeningRecord(
                id="SCR-007",
                trial_id=EYLEA_TRIAL,
                patient_id="PAT-1007",
                outcome=ScreeningOutcome.INELIGIBLE,
                failing_criteria=[
                    FailingCriterion(
                        criterion_name="HbA1c < 7.0",
                        criterion_type=CriterionType.MEASUREMENT,
                        details="Patient HbA1c was 9.1",
                    ),
                    FailingCriterion(
                        criterion_name="No active cancer",
                        criterion_type=CriterionType.CONDITION,
                        details="Patient has prostate cancer",
                    ),
                    FailingCriterion(
                        criterion_name="No prior anti-VEGF therapy",
                        criterion_type=CriterionType.DRUG,
                        details="Patient was on bevacizumab",
                    ),
                ],
                match_score=0.22,
                timestamp=now - timedelta(days=14),
            ),
            ScreeningRecord(
                id="SCR-008",
                trial_id=EYLEA_TRIAL,
                patient_id="PAT-1008",
                outcome=ScreeningOutcome.INELIGIBLE,
                failing_criteria=[
                    FailingCriterion(
                        criterion_name="eGFR >= 60",
                        criterion_type=CriterionType.MEASUREMENT,
                        details="Patient eGFR was 45",
                    ),
                ],
                match_score=0.60,
                timestamp=now - timedelta(days=13),
            ),
            ScreeningRecord(
                id="SCR-009",
                trial_id=EYLEA_TRIAL,
                patient_id="PAT-1009",
                outcome=ScreeningOutcome.PENDING,
                failing_criteria=[],
                match_score=None,
                timestamp=now - timedelta(days=12),
            ),
            ScreeningRecord(
                id="SCR-010",
                trial_id=EYLEA_TRIAL,
                patient_id="PAT-1010",
                outcome=ScreeningOutcome.ERROR,
                failing_criteria=[],
                match_score=None,
                timestamp=now - timedelta(days=11),
            ),
        ]

        # ---- DUPIXENT: 8 records (2 eligible, 4 ineligible, 1 pending, 1 error) ----
        dupixent_records = [
            ScreeningRecord(
                id="SCR-011",
                trial_id=DUPIXENT_TRIAL,
                patient_id="PAT-2001",
                outcome=ScreeningOutcome.ELIGIBLE,
                failing_criteria=[],
                match_score=0.93,
                timestamp=now - timedelta(days=10),
            ),
            ScreeningRecord(
                id="SCR-012",
                trial_id=DUPIXENT_TRIAL,
                patient_id="PAT-2002",
                outcome=ScreeningOutcome.INELIGIBLE,
                failing_criteria=[
                    FailingCriterion(
                        criterion_name="No prior biologic therapy",
                        criterion_type=CriterionType.DRUG,
                        details="Patient was on adalimumab",
                    ),
                ],
                match_score=0.68,
                timestamp=now - timedelta(days=9),
            ),
            ScreeningRecord(
                id="SCR-013",
                trial_id=DUPIXENT_TRIAL,
                patient_id="PAT-2003",
                outcome=ScreeningOutcome.INELIGIBLE,
                failing_criteria=[
                    FailingCriterion(
                        criterion_name="Age >= 18",
                        criterion_type=CriterionType.DEMOGRAPHIC,
                        details="Patient is 15 years old",
                    ),
                    FailingCriterion(
                        criterion_name="Body weight >= 40 kg",
                        criterion_type=CriterionType.MEASUREMENT,
                        details="Patient weighs 35 kg",
                    ),
                ],
                match_score=0.35,
                timestamp=now - timedelta(days=8),
            ),
            ScreeningRecord(
                id="SCR-014",
                trial_id=DUPIXENT_TRIAL,
                patient_id="PAT-2004",
                outcome=ScreeningOutcome.ELIGIBLE,
                failing_criteria=[],
                match_score=0.89,
                timestamp=now - timedelta(days=7),
            ),
            ScreeningRecord(
                id="SCR-015",
                trial_id=DUPIXENT_TRIAL,
                patient_id="PAT-2005",
                outcome=ScreeningOutcome.INELIGIBLE,
                failing_criteria=[
                    FailingCriterion(
                        criterion_name="No active infection",
                        criterion_type=CriterionType.CONDITION,
                        details="Patient has active TB",
                    ),
                ],
                match_score=0.50,
                timestamp=now - timedelta(days=6),
            ),
            ScreeningRecord(
                id="SCR-016",
                trial_id=DUPIXENT_TRIAL,
                patient_id="PAT-2006",
                outcome=ScreeningOutcome.INELIGIBLE,
                failing_criteria=[
                    FailingCriterion(
                        criterion_name="No immunosuppressants",
                        criterion_type=CriterionType.DRUG,
                        details="Patient on cyclosporine",
                    ),
                    FailingCriterion(
                        criterion_name="No active infection",
                        criterion_type=CriterionType.CONDITION,
                        details="Patient has hepatitis B",
                    ),
                ],
                match_score=0.30,
                timestamp=now - timedelta(days=5),
            ),
            ScreeningRecord(
                id="SCR-017",
                trial_id=DUPIXENT_TRIAL,
                patient_id="PAT-2007",
                outcome=ScreeningOutcome.PENDING,
                failing_criteria=[],
                match_score=None,
                timestamp=now - timedelta(days=4),
            ),
            ScreeningRecord(
                id="SCR-018",
                trial_id=DUPIXENT_TRIAL,
                patient_id="PAT-2008",
                outcome=ScreeningOutcome.ERROR,
                failing_criteria=[],
                match_score=None,
                timestamp=now - timedelta(days=3),
            ),
        ]

        # ---- LIBTAYO: 6 records (1 eligible, 4 ineligible, 1 pending) ----
        libtayo_records = [
            ScreeningRecord(
                id="SCR-019",
                trial_id=LIBTAYO_TRIAL,
                patient_id="PAT-3001",
                outcome=ScreeningOutcome.ELIGIBLE,
                failing_criteria=[],
                match_score=0.97,
                timestamp=now - timedelta(days=6),
            ),
            ScreeningRecord(
                id="SCR-020",
                trial_id=LIBTAYO_TRIAL,
                patient_id="PAT-3002",
                outcome=ScreeningOutcome.INELIGIBLE,
                failing_criteria=[
                    FailingCriterion(
                        criterion_name="ECOG PS <= 1",
                        criterion_type=CriterionType.OBSERVATION,
                        details="Patient ECOG PS is 3",
                    ),
                    FailingCriterion(
                        criterion_name="No autoimmune disease",
                        criterion_type=CriterionType.CONDITION,
                        details="Patient has lupus",
                    ),
                ],
                match_score=0.25,
                timestamp=now - timedelta(days=5),
            ),
            ScreeningRecord(
                id="SCR-021",
                trial_id=LIBTAYO_TRIAL,
                patient_id="PAT-3003",
                outcome=ScreeningOutcome.INELIGIBLE,
                failing_criteria=[
                    FailingCriterion(
                        criterion_name="Platelet count >= 100k",
                        criterion_type=CriterionType.MEASUREMENT,
                        details="Patient platelets at 80k",
                    ),
                ],
                match_score=0.70,
                timestamp=now - timedelta(days=4),
            ),
            ScreeningRecord(
                id="SCR-022",
                trial_id=LIBTAYO_TRIAL,
                patient_id="PAT-3004",
                outcome=ScreeningOutcome.INELIGIBLE,
                failing_criteria=[
                    FailingCriterion(
                        criterion_name="No prior checkpoint inhibitor",
                        criterion_type=CriterionType.DRUG,
                        details="Patient was on pembrolizumab",
                    ),
                    FailingCriterion(
                        criterion_name="ECOG PS <= 1",
                        criterion_type=CriterionType.OBSERVATION,
                        details="Patient ECOG PS is 2",
                    ),
                ],
                match_score=0.38,
                timestamp=now - timedelta(days=3),
            ),
            ScreeningRecord(
                id="SCR-023",
                trial_id=LIBTAYO_TRIAL,
                patient_id="PAT-3005",
                outcome=ScreeningOutcome.INELIGIBLE,
                failing_criteria=[
                    FailingCriterion(
                        criterion_name="No autoimmune disease",
                        criterion_type=CriterionType.CONDITION,
                        details="Patient has rheumatoid arthritis",
                    ),
                ],
                match_score=0.65,
                timestamp=now - timedelta(days=2),
            ),
            ScreeningRecord(
                id="SCR-024",
                trial_id=LIBTAYO_TRIAL,
                patient_id="PAT-3006",
                outcome=ScreeningOutcome.PENDING,
                failing_criteria=[],
                match_score=None,
                timestamp=now - timedelta(days=1),
            ),
        ]

        for rec in eylea_records + dupixent_records + libtayo_records:
            self._records[rec.id] = rec

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def list_screening_records(
        self,
        *,
        trial_id: str | None = None,
        outcome: ScreeningOutcome | None = None,
    ) -> list[ScreeningRecord]:
        with self._lock:
            items = list(self._records.values())
        if trial_id:
            items = [r for r in items if r.trial_id == trial_id]
        if outcome:
            items = [r for r in items if r.outcome == outcome]
        items.sort(key=lambda r: r.timestamp, reverse=True)
        return items

    def get_screening_record(self, record_id: str) -> ScreeningRecord | None:
        with self._lock:
            return self._records.get(record_id)

    def create_screening_record(
        self,
        *,
        trial_id: str,
        patient_id: str,
        outcome: ScreeningOutcome,
        failing_criteria: list[FailingCriterion] | None = None,
        match_score: float | None = None,
        metadata: dict | None = None,
    ) -> ScreeningRecord:
        now = datetime.now(timezone.utc)
        record_id = f"SCR-{uuid4().hex[:8].upper()}"
        record = ScreeningRecord(
            id=record_id,
            trial_id=trial_id,
            patient_id=patient_id,
            outcome=outcome,
            failing_criteria=failing_criteria or [],
            match_score=match_score,
            timestamp=now,
            metadata=metadata,
        )
        with self._lock:
            self._records[record_id] = record
        return record

    def update_screening_record(self, record_id: str, **kwargs) -> ScreeningRecord | None:
        with self._lock:
            existing = self._records.get(record_id)
            if existing is None:
                return None
            data = existing.model_dump()
            data.update({k: v for k, v in kwargs.items() if v is not None})
            updated = ScreeningRecord(**data)
            self._records[record_id] = updated
        return updated

    def delete_screening_record(self, record_id: str) -> bool:
        with self._lock:
            if record_id in self._records:
                del self._records[record_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _filter_records(
        self,
        trial_id: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[ScreeningRecord]:
        """Get records for a trial with optional date filter."""
        records = self.list_screening_records(trial_id=trial_id)
        if date_from:
            records = [r for r in records if r.timestamp >= date_from]
        if date_to:
            records = [r for r in records if r.timestamp <= date_to]
        return records

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def get_failure_analytics(
        self,
        trial_id: str,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        top_n: int = 10,
    ) -> FailureAnalyticsReport:
        records = self._filter_records(trial_id, date_from, date_to)

        total = len(records)
        eligible = sum(1 for r in records if r.outcome == ScreeningOutcome.ELIGIBLE)
        ineligible = sum(1 for r in records if r.outcome == ScreeningOutcome.INELIGIBLE)
        pending = sum(1 for r in records if r.outcome == ScreeningOutcome.PENDING)
        error = sum(1 for r in records if r.outcome == ScreeningOutcome.ERROR)

        # Top failing criteria
        criteria_counter: Counter[tuple[str, CriterionType]] = Counter()
        for r in records:
            if r.outcome == ScreeningOutcome.INELIGIBLE:
                for fc in r.failing_criteria:
                    criteria_counter[(fc.criterion_name, fc.criterion_type)] += 1

        top_failing = [
            TopFailingCriterion(
                criterion_name=name,
                criterion_type=ctype,
                failure_count=count,
                failure_rate=count / total if total else 0.0,
            )
            for (name, ctype), count in criteria_counter.most_common(top_n)
        ]

        # Failure by type
        type_counter: Counter[CriterionType] = Counter()
        for r in records:
            if r.outcome == ScreeningOutcome.INELIGIBLE:
                for fc in r.failing_criteria:
                    type_counter[fc.criterion_type] += 1
        type_total = sum(type_counter.values())
        failure_by_type = [
            FailureByType(
                criterion_type=ctype,
                failure_count=count,
                percentage=(count / type_total * 100.0) if type_total else 0.0,
            )
            for ctype, count in type_counter.most_common()
        ]

        # Daily trend
        daily_data: dict[str, dict[str, int]] = {}
        for r in records:
            day_str = r.timestamp.strftime("%Y-%m-%d")
            if day_str not in daily_data:
                daily_data[day_str] = {"screened": 0, "failed": 0}
            daily_data[day_str]["screened"] += 1
            if r.outcome == ScreeningOutcome.INELIGIBLE:
                daily_data[day_str]["failed"] += 1
        daily_trend = [
            DailyTrend(
                date=day,
                screened=counts["screened"],
                failed=counts["failed"],
                failure_rate=counts["failed"] / counts["screened"] if counts["screened"] else 0.0,
            )
            for day, counts in sorted(daily_data.items())
        ]

        # Near-miss count (failing exactly 1 criterion)
        near_miss_count = sum(
            1
            for r in records
            if r.outcome == ScreeningOutcome.INELIGIBLE and len(r.failing_criteria) == 1
        )

        return FailureAnalyticsReport(
            trial_id=trial_id,
            date_from=date_from,
            date_to=date_to,
            total_screened=total,
            total_eligible=eligible,
            total_ineligible=ineligible,
            total_pending=pending,
            total_error=error,
            failure_rate=ineligible / total if total else 0.0,
            top_failing_criteria=top_failing,
            failure_by_type=failure_by_type,
            daily_trend=daily_trend,
            near_miss_count=near_miss_count,
        )

    def get_recruitment_funnel(
        self, trial_id: str, *, enrolled_count: int | None = None
    ) -> RecruitmentFunnel:
        records = self.list_screening_records(trial_id=trial_id)
        total = len(records)
        # "Passed Inclusion" = eligible + pending (passed initial screen but not confirmed)
        passed_inclusion = sum(
            1
            for r in records
            if r.outcome in (ScreeningOutcome.ELIGIBLE, ScreeningOutcome.PENDING)
        )
        eligible = sum(1 for r in records if r.outcome == ScreeningOutcome.ELIGIBLE)
        enrolled = enrolled_count if enrolled_count is not None else 0

        stages = [
            FunnelStage(name="Screened", count=total, conversion_rate=None),
            FunnelStage(
                name="Passed Inclusion",
                count=passed_inclusion,
                conversion_rate=passed_inclusion / total if total else 0.0,
            ),
            FunnelStage(
                name="Eligible",
                count=eligible,
                conversion_rate=eligible / passed_inclusion if passed_inclusion else 0.0,
            ),
            FunnelStage(
                name="Enrolled",
                count=enrolled,
                conversion_rate=enrolled / eligible if eligible else 0.0,
            ),
        ]
        return RecruitmentFunnel(trial_id=trial_id, stages=stages)

    def get_criteria_difficulty(self, trial_id: str) -> CriteriaDifficultyReport:
        records = self.list_screening_records(trial_id=trial_id)
        if not records:
            return CriteriaDifficultyReport(trial_id=trial_id, criteria=[])

        total = len(records)

        # Collect all unique criteria from ineligible records
        all_criteria: dict[str, CriterionType] = {}
        fail_counter: Counter[str] = Counter()
        for r in records:
            if r.outcome == ScreeningOutcome.INELIGIBLE:
                for fc in r.failing_criteria:
                    all_criteria[fc.criterion_name] = fc.criterion_type
                    fail_counter[fc.criterion_name] += 1

        criteria = []
        for crit_name, crit_type in all_criteria.items():
            fail_count = fail_counter[crit_name]
            pass_count = total - fail_count
            criteria.append(
                CriteriaDifficulty(
                    criterion_name=crit_name,
                    criterion_type=crit_type,
                    pass_count=pass_count,
                    fail_count=fail_count,
                    unknown_count=0,
                    pass_rate=pass_count / total if total else 0.0,
                )
            )

        # Sort by pass_rate ascending (hardest first)
        criteria.sort(key=lambda c: c.pass_rate)
        return CriteriaDifficultyReport(trial_id=trial_id, criteria=criteria)

    def get_near_miss_patients(
        self, trial_id: str, max_failures: int = 2
    ) -> NearMissReport:
        records = self.list_screening_records(trial_id=trial_id)
        near_miss = [
            r
            for r in records
            if r.outcome == ScreeningOutcome.INELIGIBLE
            and 1 <= len(r.failing_criteria) <= max_failures
        ]
        patients = [
            NearMissPatient(
                patient_id=r.patient_id,
                failing_criteria=r.failing_criteria,
                match_score=r.match_score,
                num_failing=len(r.failing_criteria),
            )
            for r in near_miss
        ]
        # Sort by fewest failures first
        patients.sort(key=lambda p: p.num_failing)
        return NearMissReport(
            trial_id=trial_id,
            max_failures=max_failures,
            patients=patients,
            total=len(patients),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ScreenFailureService | None = None
_instance_lock = threading.Lock()


def get_screen_failure_service() -> ScreenFailureService:
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ScreenFailureService()
    return _instance


def reset_screen_failure_service() -> ScreenFailureService:
    global _instance
    with _instance_lock:
        _instance = ScreenFailureService()
    return _instance
