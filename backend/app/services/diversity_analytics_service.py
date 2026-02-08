"""Diversity and Inclusion Analytics Service (VP-Product-4).

Tracks demographic representation across the clinical trial screening
and enrollment pipeline to support FDA diversity action plan requirements.

All storage is in-memory. Thread-safe via a reentrant lock.

Usage:
    from app.services.diversity_analytics_service import get_diversity_analytics_service

    service = get_diversity_analytics_service()
    service.record_demographic("trial-1", DemographicRecord(...))
    report = service.get_diversity_report("trial-1")
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.schemas.diversity import (
    AGE_BUCKETS,
    DemographicRecord,
    DistributionEntry,
    DiversityReport,
    DropoutAnalysis,
    Ethnicity,
    FDADiversitySummary,
    PipelineDemographics,
    PipelineStage,
    Race,
    RepresentationCheck,
    RepresentationTarget,
    Sex,
    SetDiversityTargetsRequest,
    StageDemographics,
    age_to_bucket,
)

logger = logging.getLogger(__name__)


# =============================================================================
# In-memory storage
# =============================================================================


class _TrialDiversityStore:
    """Internal per-trial storage for demographic records and targets."""

    def __init__(self) -> None:
        # patient_id -> {stage -> DemographicRecord}
        self.records: dict[str, dict[PipelineStage, DemographicRecord]] = {}
        # Diversity targets
        self.targets: list[RepresentationTarget] = []


# =============================================================================
# Service
# =============================================================================


class DiversityAnalyticsService:
    """Tracks demographic representation for FDA diversity compliance.

    Provides:
    - record_demographic: Record a patient's demographics at a pipeline stage
    - get_diversity_report: Aggregate diversity report for a trial
    - check_representation: Compare enrollment against targets
    - get_pipeline_demographics: Demographics at each pipeline stage
    - generate_fda_diversity_summary: FDA-format diversity summary
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        # trial_id -> _TrialDiversityStore
        self._stores: dict[str, _TrialDiversityStore] = {}

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _get_store(self, trial_id: str) -> _TrialDiversityStore:
        """Get or create the store for a trial."""
        if trial_id not in self._stores:
            self._stores[trial_id] = _TrialDiversityStore()
        return self._stores[trial_id]

    def _get_records_for_stage(
        self, store: _TrialDiversityStore, stage: PipelineStage | None = None
    ) -> list[DemographicRecord]:
        """Get all records, optionally filtered to a specific stage."""
        results = []
        for patient_id, stage_map in store.records.items():
            if stage is not None:
                if stage in stage_map:
                    results.append(stage_map[stage])
            else:
                # Return the latest stage record for each patient
                # Priority: enrolled > eligible > screened
                for s in [PipelineStage.ENROLLED, PipelineStage.ELIGIBLE, PipelineStage.SCREENED]:
                    if s in stage_map:
                        results.append(stage_map[s])
                        break
        return results

    @staticmethod
    def _build_distribution(
        records: list[DemographicRecord],
        extractor: Any,
        categories: list[str],
    ) -> list[DistributionEntry]:
        """Build a distribution from records using the given extractor function."""
        total = len(records)
        counts: dict[str, int] = defaultdict(int)
        for rec in records:
            key = extractor(rec)
            counts[key] += 1

        entries = []
        for cat in categories:
            count = counts.get(cat, 0)
            pct = (count / total * 100.0) if total > 0 else 0.0
            entries.append(DistributionEntry(category=cat, count=count, percentage=round(pct, 2)))
        return entries

    def _build_stage_demographics(
        self, records: list[DemographicRecord], stage: PipelineStage
    ) -> StageDemographics:
        """Build demographics summary for a pipeline stage."""
        return StageDemographics(
            stage=stage,
            total_patients=len(records),
            age_distribution=self._build_distribution(
                records, lambda r: age_to_bucket(r.age), AGE_BUCKETS
            ),
            sex_distribution=self._build_distribution(
                records, lambda r: r.sex.value, [s.value for s in Sex]
            ),
            race_distribution=self._build_distribution(
                records, lambda r: r.race.value, [r.value for r in Race]
            ),
            ethnicity_distribution=self._build_distribution(
                records, lambda r: r.ethnicity.value, [e.value for e in Ethnicity]
            ),
        )

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def record_demographic(
        self,
        trial_id: str,
        record: DemographicRecord,
    ) -> None:
        """Record a patient's demographic data for a trial at a pipeline stage.

        If the same patient_id is recorded at the same stage, the record is
        overwritten (last-write-wins).
        """
        with self._lock:
            store = self._get_store(trial_id)
            patient_id = record.patient_id
            if patient_id not in store.records:
                store.records[patient_id] = {}
            store.records[patient_id][record.pipeline_stage] = record
            logger.debug(
                "Recorded demographic: trial=%s patient=%s stage=%s",
                trial_id,
                patient_id,
                record.pipeline_stage.value,
            )

    def get_diversity_report(
        self,
        trial_id: str,
        stage: PipelineStage | None = None,
    ) -> DiversityReport:
        """Get an aggregate diversity report for a trial.

        If stage is None, uses the latest stage record for each patient.
        """
        with self._lock:
            store = self._get_store(trial_id)
            records = self._get_records_for_stage(store, stage)

            return DiversityReport(
                trial_id=trial_id,
                total_patients=len(records),
                age_distribution=self._build_distribution(
                    records, lambda r: age_to_bucket(r.age), AGE_BUCKETS
                ),
                sex_distribution=self._build_distribution(
                    records, lambda r: r.sex.value, [s.value for s in Sex]
                ),
                race_distribution=self._build_distribution(
                    records, lambda r: r.race.value, [r.value for r in Race]
                ),
                ethnicity_distribution=self._build_distribution(
                    records, lambda r: r.ethnicity.value, [e.value for e in Ethnicity]
                ),
                generated_at=datetime.now(timezone.utc),
            )

    def set_targets(
        self,
        trial_id: str,
        targets: list[RepresentationTarget],
    ) -> None:
        """Set diversity representation targets for a trial."""
        with self._lock:
            store = self._get_store(trial_id)
            store.targets = targets
            logger.info(
                "Set %d diversity targets for trial %s",
                len(targets),
                trial_id,
            )

    def check_representation(
        self,
        trial_id: str,
        targets: list[RepresentationTarget] | None = None,
    ) -> RepresentationCheck:
        """Compare actual enrollment demographics against diversity targets.

        If targets is None, uses the trial's stored targets.
        """
        with self._lock:
            store = self._get_store(trial_id)

            # Use provided targets or fall back to stored
            check_targets = targets if targets is not None else store.targets

            # Get all records (latest stage per patient)
            records = self._get_records_for_stage(store)
            total = len(records)

            # Build lookup: group -> category -> actual count
            group_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
            for rec in records:
                group_counts["race"][rec.race.value] += 1
                group_counts["sex"][rec.sex.value] += 1
                group_counts["ethnicity"][rec.ethnicity.value] += 1
                group_counts["age"][age_to_bucket(rec.age)] += 1

            evaluated_targets: list[RepresentationTarget] = []
            underrepresented: list[str] = []
            met_count = 0

            for target in check_targets:
                actual_count = group_counts.get(target.group, {}).get(target.category, 0)
                actual_pct = (actual_count / total * 100.0) if total > 0 else 0.0
                actual_pct = round(actual_pct, 2)
                gap = round(target.target_pct - actual_pct, 2)
                is_met = actual_pct >= target.target_pct

                if is_met:
                    met_count += 1
                else:
                    underrepresented.append(f"{target.group}:{target.category}")

                evaluated_targets.append(
                    RepresentationTarget(
                        group=target.group,
                        category=target.category,
                        target_pct=target.target_pct,
                        actual_pct=actual_pct,
                        is_met=is_met,
                        gap=gap,
                    )
                )

            # Overall score: percentage of targets met
            total_targets = len(evaluated_targets)
            overall_score = (met_count / total_targets * 100.0) if total_targets > 0 else 0.0

            return RepresentationCheck(
                trial_id=trial_id,
                targets=evaluated_targets,
                overall_diversity_score=round(overall_score, 2),
                underrepresented_groups=underrepresented,
                checked_at=datetime.now(timezone.utc),
            )

    def get_pipeline_demographics(self, trial_id: str) -> PipelineDemographics:
        """Get demographics at each pipeline stage with dropout analysis.

        Detects if screening criteria disproportionately exclude certain
        demographic groups by comparing representation across stages.
        """
        with self._lock:
            store = self._get_store(trial_id)

            # Collect records for each stage
            stage_records: dict[PipelineStage, list[DemographicRecord]] = {}
            for stage in PipelineStage:
                stage_records[stage] = self._get_records_for_stage(store, stage)

            # Build stage demographics
            screened_demo = self._build_stage_demographics(
                stage_records[PipelineStage.SCREENED], PipelineStage.SCREENED
            ) if stage_records[PipelineStage.SCREENED] else None

            eligible_demo = self._build_stage_demographics(
                stage_records[PipelineStage.ELIGIBLE], PipelineStage.ELIGIBLE
            ) if stage_records[PipelineStage.ELIGIBLE] else None

            enrolled_demo = self._build_stage_demographics(
                stage_records[PipelineStage.ENROLLED], PipelineStage.ENROLLED
            ) if stage_records[PipelineStage.ENROLLED] else None

            # Dropout analysis: compare consecutive stages
            dropout_analysis: list[DropoutAnalysis] = []
            stage_pairs = [
                (PipelineStage.SCREENED, PipelineStage.ELIGIBLE, screened_demo, eligible_demo),
                (PipelineStage.ELIGIBLE, PipelineStage.ENROLLED, eligible_demo, enrolled_demo),
            ]

            for from_stage, to_stage, from_demo, to_demo in stage_pairs:
                if from_demo is None or to_demo is None:
                    continue
                if from_demo.total_patients == 0 or to_demo.total_patients == 0:
                    continue

                # Compare each demographic dimension
                dimension_pairs = [
                    ("race", from_demo.race_distribution, to_demo.race_distribution),
                    ("sex", from_demo.sex_distribution, to_demo.sex_distribution),
                    ("ethnicity", from_demo.ethnicity_distribution, to_demo.ethnicity_distribution),
                    ("age", from_demo.age_distribution, to_demo.age_distribution),
                ]

                for group, from_dist, to_dist in dimension_pairs:
                    from_lookup = {e.category: e.percentage for e in from_dist}
                    to_lookup = {e.category: e.percentage for e in to_dist}

                    for category in from_lookup:
                        from_pct = from_lookup.get(category, 0.0)
                        to_pct = to_lookup.get(category, 0.0)
                        change = round(to_pct - from_pct, 2)

                        # A group is disproportionately dropping if its
                        # representation decreases by more than 5 percentage
                        # points between stages
                        disproportionate = change < -5.0

                        dropout_analysis.append(
                            DropoutAnalysis(
                                from_stage=from_stage.value,
                                to_stage=to_stage.value,
                                group=group,
                                category=category,
                                from_pct=from_pct,
                                to_pct=to_pct,
                                change_pct=change,
                                disproportionate=disproportionate,
                            )
                        )

            return PipelineDemographics(
                trial_id=trial_id,
                screened_demographics=screened_demo,
                eligible_demographics=eligible_demo,
                enrolled_demographics=enrolled_demo,
                dropout_analysis=dropout_analysis,
            )

    def generate_fda_diversity_summary(
        self,
        trial_id: str,
        enrollment_target: int | None = None,
    ) -> FDADiversitySummary:
        """Generate an FDA-format diversity summary for regulatory submission.

        Focuses on enrolled patients and provides recommendations for
        improving diversity where targets are not met.
        """
        with self._lock:
            store = self._get_store(trial_id)

            # Get enrolled records (or all records if none enrolled)
            enrolled_records = self._get_records_for_stage(store, PipelineStage.ENROLLED)
            if not enrolled_records:
                # Fall back to latest stage
                enrolled_records = self._get_records_for_stage(store)

            total = len(enrolled_records)

            # Build distribution tables
            sex_table = self._build_distribution(
                enrolled_records, lambda r: r.sex.value, [s.value for s in Sex]
            )
            race_table = self._build_distribution(
                enrolled_records, lambda r: r.race.value, [r.value for r in Race]
            )
            ethnicity_table = self._build_distribution(
                enrolled_records, lambda r: r.ethnicity.value, [e.value for e in Ethnicity]
            )
            age_table = self._build_distribution(
                enrolled_records, lambda r: age_to_bucket(r.age), AGE_BUCKETS
            )

            # Check targets
            targets_met = 0
            targets_total = len(store.targets)
            underrepresented: list[str] = []
            recommendations: list[str] = []

            if store.targets:
                check = self.check_representation(trial_id)
                targets_met = sum(1 for t in check.targets if t.is_met)
                underrepresented = check.underrepresented_groups

                for group_label in underrepresented:
                    parts = group_label.split(":", 1)
                    if len(parts) == 2:
                        group, category = parts
                        recommendations.append(
                            f"Increase recruitment efforts targeting {category} "
                            f"({group}) to meet diversity target."
                        )

            if total == 0:
                recommendations.append(
                    "No patients enrolled yet. Consider community outreach "
                    "strategies to ensure diverse enrollment."
                )

            return FDADiversitySummary(
                trial_id=trial_id,
                report_date=datetime.now(timezone.utc),
                total_enrolled=total,
                enrollment_target=enrollment_target,
                sex_table=sex_table,
                race_table=race_table,
                ethnicity_table=ethnicity_table,
                age_table=age_table,
                diversity_targets_met=targets_met,
                diversity_targets_total=targets_total,
                underrepresented_groups=underrepresented,
                recommendations=recommendations,
            )

    def get_stats(self) -> dict[str, Any]:
        """Get aggregate service statistics."""
        with self._lock:
            total_trials = len(self._stores)
            total_records = sum(
                len(store.records) for store in self._stores.values()
            )
            return {
                "total_trials_tracked": total_trials,
                "total_patient_records": total_records,
            }


# =============================================================================
# Singleton accessor
# =============================================================================

_service_instance: DiversityAnalyticsService | None = None
_service_lock = threading.Lock()


def get_diversity_analytics_service() -> DiversityAnalyticsService:
    """Get or create the singleton DiversityAnalyticsService."""
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = DiversityAnalyticsService()
                logger.info("DiversityAnalyticsService initialized")
    return _service_instance
