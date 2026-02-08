"""Fairness Audit Service (VP-DS-5).

Detects bias in clinical trial screening across protected demographic
groups using multiple fairness metrics:

- Demographic parity: equal screening pass rates
- Equal opportunity: equal true positive rates
- Predictive parity: equal positive predictive values
- Individual fairness: similar patients get similar outcomes
- Intersectional analysis: bias at intersection of attributes

All storage is in-memory.  Thread-safe via a reentrant lock.

Usage:
    from app.services.fairness_audit_service import get_fairness_audit_service

    service = get_fairness_audit_service()
    service.record_screening_outcome(outcome)
    audit = service.run_audit(FairnessAuditCreate(trial_id="t1"))
"""

from __future__ import annotations

import logging
import math
import threading
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.schemas.fairness_audit import (
    AuditStatus,
    BiasRecommendation,
    BiasRecommendationType,
    DemographicParityResult,
    EqualOpportunityResult,
    FairnessAuditConfig,
    FairnessAuditCreate,
    FairnessAuditResponse,
    FairnessMetrics,
    FairnessTrend,
    FairnessTrendPoint,
    FDAComplianceResult,
    GroupRate,
    IndividualFairnessPair,
    IndividualFairnessResult,
    IntersectionalAnalysisResult,
    IntersectionalGroupRate,
    PlatformFairnessSummary,
    PredictiveParityResult,
    ProtectedAttribute,
    ScreeningOutcome,
    ScreeningOutcomeRecord,
    TrialFairnessSummary,
)

logger = logging.getLogger(__name__)


# =============================================================================
# In-memory storage
# =============================================================================


class _TrialFairnessStore:
    """Per-trial storage for screening outcomes and audit history."""

    def __init__(self) -> None:
        # All screening outcome records for this trial
        self.outcomes: list[ScreeningOutcomeRecord] = []
        # patient_id -> latest outcome (dedup)
        self.outcome_by_patient: dict[str, ScreeningOutcomeRecord] = {}
        # Completed audit reports
        self.audits: list[FairnessAuditResponse] = []


# =============================================================================
# Service
# =============================================================================


class FairnessAuditService:
    """Detects bias in clinical trial screening.

    Provides:
    - record_screening_outcome: record a patient screening result
    - run_audit: run a comprehensive fairness audit for a trial
    - get_audit: retrieve a specific audit report
    - list_audits: list audit reports for a trial
    - get_recommendations: get recommendations for a specific audit
    - get_trends: get fairness metric trends over time
    - get_platform_summary: platform-wide fairness summary
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._stores: dict[str, _TrialFairnessStore] = {}

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _get_store(self, trial_id: str) -> _TrialFairnessStore:
        if trial_id not in self._stores:
            self._stores[trial_id] = _TrialFairnessStore()
        return self._stores[trial_id]

    @staticmethod
    def _get_attribute_value(
        record: ScreeningOutcomeRecord, attribute: ProtectedAttribute
    ) -> str | None:
        """Extract the value of a protected attribute from a record."""
        if attribute == ProtectedAttribute.AGE_GROUP:
            return record.age_group
        elif attribute == ProtectedAttribute.SEX:
            return record.sex
        elif attribute == ProtectedAttribute.RACE:
            return record.race
        elif attribute == ProtectedAttribute.ETHNICITY:
            return record.ethnicity
        return None

    @staticmethod
    def _compute_disparity_ratio(min_rate: float, max_rate: float) -> float:
        """Compute disparity ratio.  Returns 1.0 for edge cases."""
        if max_rate <= 0.0:
            return 1.0
        return round(min_rate / max_rate, 6)

    @staticmethod
    def _clinical_similarity(
        features_a: dict[str, float], features_b: dict[str, float]
    ) -> float:
        """Compute cosine similarity between two clinical feature vectors."""
        all_keys = set(features_a.keys()) | set(features_b.keys())
        if not all_keys:
            return 1.0
        dot = sum(features_a.get(k, 0.0) * features_b.get(k, 0.0) for k in all_keys)
        mag_a = math.sqrt(sum(v ** 2 for v in features_a.values())) or 1.0
        mag_b = math.sqrt(sum(v ** 2 for v in features_b.values())) or 1.0
        sim = dot / (mag_a * mag_b)
        return max(0.0, min(1.0, sim))

    # -------------------------------------------------------------------------
    # Demographic parity
    # -------------------------------------------------------------------------

    def _compute_demographic_parity(
        self,
        records: list[ScreeningOutcomeRecord],
        attribute: ProtectedAttribute,
        config: FairnessAuditConfig,
    ) -> DemographicParityResult:
        """Compute demographic parity for a single attribute."""
        groups: dict[str, list[ScreeningOutcomeRecord]] = defaultdict(list)
        for rec in records:
            val = self._get_attribute_value(rec, attribute)
            if val is not None:
                groups[val].append(rec)

        group_rates: list[GroupRate] = []
        for group_value, group_records in sorted(groups.items()):
            if len(group_records) < config.min_group_size:
                continue
            total = len(group_records)
            passed = sum(
                1 for r in group_records if r.screening_result == ScreeningOutcome.PASSED
            )
            rate = passed / total if total > 0 else 0.0
            group_rates.append(
                GroupRate(
                    group_value=group_value,
                    total=total,
                    passed=passed,
                    rate=round(rate, 6),
                )
            )

        if not group_rates:
            return DemographicParityResult(attribute=attribute)

        rates = [gr.rate for gr in group_rates]
        min_rate = min(rates)
        max_rate = max(rates)
        disparity = self._compute_disparity_ratio(min_rate, max_rate)

        return DemographicParityResult(
            attribute=attribute,
            group_rates=group_rates,
            min_rate=round(min_rate, 6),
            max_rate=round(max_rate, 6),
            disparity_ratio=disparity,
            four_fifths_violated=disparity < config.four_fifths_threshold,
        )

    # -------------------------------------------------------------------------
    # Equal opportunity
    # -------------------------------------------------------------------------

    def _compute_equal_opportunity(
        self,
        records: list[ScreeningOutcomeRecord],
        attribute: ProtectedAttribute,
        config: FairnessAuditConfig,
    ) -> EqualOpportunityResult:
        """Compute equal opportunity (TPR) for a single attribute.

        Only considers records where actually_eligible is True.
        TPR = passed / actually_eligible per group.
        """
        groups: dict[str, list[ScreeningOutcomeRecord]] = defaultdict(list)
        for rec in records:
            if rec.actually_eligible is not True:
                continue
            val = self._get_attribute_value(rec, attribute)
            if val is not None:
                groups[val].append(rec)

        group_tpr: list[GroupRate] = []
        for group_value, group_records in sorted(groups.items()):
            if len(group_records) < config.min_group_size:
                continue
            total = len(group_records)
            passed = sum(
                1 for r in group_records if r.screening_result == ScreeningOutcome.PASSED
            )
            rate = passed / total if total > 0 else 0.0
            group_tpr.append(
                GroupRate(
                    group_value=group_value,
                    total=total,
                    passed=passed,
                    rate=round(rate, 6),
                )
            )

        if not group_tpr:
            return EqualOpportunityResult(attribute=attribute)

        rates = [gr.rate for gr in group_tpr]
        min_tpr = min(rates)
        max_tpr = max(rates)
        disparity = self._compute_disparity_ratio(min_tpr, max_tpr)

        return EqualOpportunityResult(
            attribute=attribute,
            group_tpr=group_tpr,
            min_tpr=round(min_tpr, 6),
            max_tpr=round(max_tpr, 6),
            disparity_ratio=disparity,
            four_fifths_violated=disparity < config.four_fifths_threshold,
        )

    # -------------------------------------------------------------------------
    # Predictive parity
    # -------------------------------------------------------------------------

    def _compute_predictive_parity(
        self,
        records: list[ScreeningOutcomeRecord],
        attribute: ProtectedAttribute,
        config: FairnessAuditConfig,
    ) -> PredictiveParityResult:
        """Compute predictive parity (PPV) for a single attribute.

        Among patients who passed screening, what fraction are actually
        eligible? Computed per group.
        """
        groups: dict[str, list[ScreeningOutcomeRecord]] = defaultdict(list)
        for rec in records:
            if rec.screening_result != ScreeningOutcome.PASSED:
                continue
            if rec.actually_eligible is None:
                continue
            val = self._get_attribute_value(rec, attribute)
            if val is not None:
                groups[val].append(rec)

        group_ppv: list[GroupRate] = []
        for group_value, group_records in sorted(groups.items()):
            if len(group_records) < config.min_group_size:
                continue
            total = len(group_records)
            actually_eligible_count = sum(
                1 for r in group_records if r.actually_eligible is True
            )
            rate = actually_eligible_count / total if total > 0 else 0.0
            group_ppv.append(
                GroupRate(
                    group_value=group_value,
                    total=total,
                    passed=actually_eligible_count,
                    rate=round(rate, 6),
                )
            )

        if not group_ppv:
            return PredictiveParityResult(attribute=attribute)

        rates = [gr.rate for gr in group_ppv]
        min_ppv = min(rates)
        max_ppv = max(rates)
        disparity = self._compute_disparity_ratio(min_ppv, max_ppv)

        return PredictiveParityResult(
            attribute=attribute,
            group_ppv=group_ppv,
            min_ppv=round(min_ppv, 6),
            max_ppv=round(max_ppv, 6),
            disparity_ratio=disparity,
            four_fifths_violated=disparity < config.four_fifths_threshold,
        )

    # -------------------------------------------------------------------------
    # Individual fairness
    # -------------------------------------------------------------------------

    def _compute_individual_fairness(
        self,
        records: list[ScreeningOutcomeRecord],
        config: FairnessAuditConfig,
    ) -> IndividualFairnessResult:
        """Check if similar patients get similar outcomes.

        Compares all pairs of patients that have clinical_features set.
        """
        featured = [r for r in records if r.clinical_features]
        if len(featured) < 2:
            return IndividualFairnessResult(
                similarity_threshold=config.similarity_threshold
            )

        total_pairs = 0
        consistent = 0
        inconsistent = 0
        flagged: list[IndividualFairnessPair] = []

        for i in range(len(featured)):
            for j in range(i + 1, len(featured)):
                a = featured[i]
                b = featured[j]
                sim = self._clinical_similarity(
                    a.clinical_features,  # type: ignore[arg-type]
                    b.clinical_features,  # type: ignore[arg-type]
                )
                if sim >= config.similarity_threshold:
                    total_pairs += 1
                    same_outcome = a.screening_result == b.screening_result
                    if same_outcome:
                        consistent += 1
                    else:
                        inconsistent += 1
                        flagged.append(
                            IndividualFairnessPair(
                                patient_a_id=a.patient_id,
                                patient_b_id=b.patient_id,
                                similarity=round(sim, 6),
                                same_outcome=False,
                            )
                        )

        consistency_rate = consistent / total_pairs if total_pairs > 0 else 1.0

        return IndividualFairnessResult(
            total_pairs_checked=total_pairs,
            consistent_pairs=consistent,
            inconsistent_pairs=inconsistent,
            consistency_rate=round(consistency_rate, 6),
            flagged_pairs=flagged,
            similarity_threshold=config.similarity_threshold,
        )

    # -------------------------------------------------------------------------
    # Intersectional analysis
    # -------------------------------------------------------------------------

    def _compute_intersectional(
        self,
        records: list[ScreeningOutcomeRecord],
        attributes: list[ProtectedAttribute],
        config: FairnessAuditConfig,
    ) -> IntersectionalAnalysisResult:
        """Compute intersectional analysis across multiple attributes."""
        groups: dict[str, list[ScreeningOutcomeRecord]] = defaultdict(list)
        group_attrs: dict[str, dict[str, str]] = {}

        for rec in records:
            vals: dict[str, str] = {}
            skip = False
            for attr in attributes:
                val = self._get_attribute_value(rec, attr)
                if val is None:
                    skip = True
                    break
                vals[attr.value] = val
            if skip:
                continue
            key = "+".join(f"{a.value}={vals[a.value]}" for a in sorted(attributes, key=lambda x: x.value))
            groups[key].append(rec)
            group_attrs[key] = vals

        group_rates: list[IntersectionalGroupRate] = []
        for key, group_records in sorted(groups.items()):
            if len(group_records) < config.min_group_size:
                continue
            total = len(group_records)
            passed = sum(
                1 for r in group_records if r.screening_result == ScreeningOutcome.PASSED
            )
            rate = passed / total if total > 0 else 0.0
            group_rates.append(
                IntersectionalGroupRate(
                    group_key=key,
                    attributes=group_attrs[key],
                    total=total,
                    passed=passed,
                    rate=round(rate, 6),
                )
            )

        if not group_rates:
            return IntersectionalAnalysisResult(
                attribute_combination=attributes
            )

        rates = [gr.rate for gr in group_rates]
        min_rate = min(rates)
        max_rate = max(rates)
        disparity = self._compute_disparity_ratio(min_rate, max_rate)

        return IntersectionalAnalysisResult(
            attribute_combination=attributes,
            group_rates=group_rates,
            min_rate=round(min_rate, 6),
            max_rate=round(max_rate, 6),
            disparity_ratio=disparity,
            four_fifths_violated=disparity < config.four_fifths_threshold,
        )

    # -------------------------------------------------------------------------
    # Recommendations
    # -------------------------------------------------------------------------

    def _generate_recommendations(
        self,
        metrics: FairnessMetrics,
        records: list[ScreeningOutcomeRecord],
        config: FairnessAuditConfig,
    ) -> list[BiasRecommendation]:
        """Generate bias mitigation recommendations based on audit results."""
        recommendations: list[BiasRecommendation] = []

        # Check demographic parity violations
        for dp in metrics.demographic_parity:
            if dp.four_fifths_violated:
                recommendations.append(
                    BiasRecommendation(
                        recommendation_type=BiasRecommendationType.CRITERIA_REVIEW,
                        attribute=dp.attribute,
                        description=(
                            f"Screening criteria may have adverse impact on "
                            f"{dp.attribute.value} groups. Disparity ratio "
                            f"{dp.disparity_ratio:.3f} is below the four-fifths "
                            f"threshold of {config.four_fifths_threshold}. "
                            f"Review criteria for cultural bias."
                        ),
                        severity="high",
                        details={
                            "disparity_ratio": dp.disparity_ratio,
                            "threshold": config.four_fifths_threshold,
                        },
                    )
                )

            # Check for small groups that need more data
            for gr in dp.group_rates:
                if gr.total < config.min_group_size * 2:
                    recommendations.append(
                        BiasRecommendation(
                            recommendation_type=BiasRecommendationType.DATA_COLLECTION,
                            attribute=dp.attribute,
                            description=(
                                f"Group '{gr.group_value}' in {dp.attribute.value} "
                                f"has only {gr.total} records. Consider increasing "
                                f"recruitment for more reliable fairness analysis."
                            ),
                            severity="medium",
                            details={"group": gr.group_value, "count": float(gr.total)},
                        )
                    )

        # Check equal opportunity violations
        for eo in metrics.equal_opportunity:
            if eo.four_fifths_violated:
                recommendations.append(
                    BiasRecommendation(
                        recommendation_type=BiasRecommendationType.THRESHOLD_ADJUSTMENT,
                        attribute=eo.attribute,
                        description=(
                            f"Unequal true positive rates across {eo.attribute.value} "
                            f"groups (disparity ratio: {eo.disparity_ratio:.3f}). "
                            f"Consider adjusting match score thresholds."
                        ),
                        severity="high",
                        details={"disparity_ratio": eo.disparity_ratio},
                    )
                )

        # Check individual fairness
        if metrics.individual_fairness and metrics.individual_fairness.inconsistent_pairs > 0:
            consistency = metrics.individual_fairness.consistency_rate
            if consistency < 0.9:
                recommendations.append(
                    BiasRecommendation(
                        recommendation_type=BiasRecommendationType.CRITERIA_REVIEW,
                        attribute=None,
                        description=(
                            f"Individual fairness consistency rate is "
                            f"{consistency:.1%}. Similar patients are receiving "
                            f"different screening outcomes. Review screening "
                            f"criteria for hidden demographic proxies."
                        ),
                        severity="high" if consistency < 0.7 else "medium",
                        details={"consistency_rate": consistency},
                    )
                )

        # If no issues found
        if not recommendations:
            recommendations.append(
                BiasRecommendation(
                    recommendation_type=BiasRecommendationType.NO_ACTION,
                    attribute=None,
                    description=(
                        "All fairness metrics are within acceptable ranges. "
                        "No immediate bias mitigation action required."
                    ),
                    severity="low",
                )
            )

        return recommendations

    # -------------------------------------------------------------------------
    # FDA compliance
    # -------------------------------------------------------------------------

    def _check_fda_compliance(
        self,
        records: list[ScreeningOutcomeRecord],
        plan_demographics: dict[str, dict[str, float]],
    ) -> FDAComplianceResult:
        """Check screening demographics against FDA diversity plan."""
        actual: dict[str, dict[str, float]] = {}
        total = len(records)

        # Count per attribute per group
        for attr_key in plan_demographics:
            counts: dict[str, int] = defaultdict(int)
            for rec in records:
                try:
                    pa = ProtectedAttribute(attr_key)
                except ValueError:
                    continue
                val = self._get_attribute_value(rec, pa)
                if val is not None:
                    counts[val] += 1
            pcts: dict[str, float] = {}
            for group, count in counts.items():
                pcts[group] = round(count / total * 100.0, 2) if total > 0 else 0.0
            actual[attr_key] = pcts

        gaps: list[str] = []
        for attr_key, planned_groups in plan_demographics.items():
            actual_groups = actual.get(attr_key, {})
            for group, target_pct in planned_groups.items():
                actual_pct = actual_groups.get(group, 0.0)
                if actual_pct < target_pct:
                    gaps.append(f"{attr_key}:{group} (target={target_pct}%, actual={actual_pct}%)")

        return FDAComplianceResult(
            plan_demographics=plan_demographics,
            actual_demographics=actual,
            compliance_gaps=gaps,
            is_compliant=len(gaps) == 0,
        )

    # -------------------------------------------------------------------------
    # Overall fairness score
    # -------------------------------------------------------------------------

    @staticmethod
    def _compute_overall_score(metrics: FairnessMetrics) -> float:
        """Compute overall fairness score from component metrics."""
        scores: list[float] = []

        # Average demographic parity disparity ratios
        for dp in metrics.demographic_parity:
            if dp.group_rates:
                scores.append(dp.disparity_ratio)

        # Average equal opportunity disparity ratios
        for eo in metrics.equal_opportunity:
            if eo.group_tpr:
                scores.append(eo.disparity_ratio)

        # Average predictive parity disparity ratios
        for pp in metrics.predictive_parity:
            if pp.group_ppv:
                scores.append(pp.disparity_ratio)

        # Individual fairness consistency
        if metrics.individual_fairness and metrics.individual_fairness.total_pairs_checked > 0:
            scores.append(metrics.individual_fairness.consistency_rate)

        if not scores:
            return 1.0
        return round(sum(scores) / len(scores), 6)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def record_screening_outcome(
        self, outcome: ScreeningOutcomeRecord
    ) -> None:
        """Record a screening outcome with demographics."""
        with self._lock:
            store = self._get_store(outcome.trial_id)
            store.outcomes.append(outcome)
            store.outcome_by_patient[outcome.patient_id] = outcome
            logger.debug(
                "Recorded screening outcome: trial=%s patient=%s result=%s",
                outcome.trial_id,
                outcome.patient_id,
                outcome.screening_result.value,
            )

    def run_audit(self, request: FairnessAuditCreate) -> FairnessAuditResponse:
        """Run a comprehensive fairness audit for a trial."""
        with self._lock:
            store = self._get_store(request.trial_id)
            config = request.config or FairnessAuditConfig()

            # Use deduplicated records (latest per patient)
            records = list(store.outcome_by_patient.values())

            # Compute metrics
            demographic_parity = [
                self._compute_demographic_parity(records, attr, config)
                for attr in config.attributes_to_audit
            ]

            equal_opportunity = [
                self._compute_equal_opportunity(records, attr, config)
                for attr in config.attributes_to_audit
            ]

            predictive_parity = [
                self._compute_predictive_parity(records, attr, config)
                for attr in config.attributes_to_audit
            ]

            individual_fairness = self._compute_individual_fairness(records, config)

            # Intersectional analysis
            intersectional: list[IntersectionalAnalysisResult] = []
            if config.intersectional_attributes:
                for attr_combo in config.intersectional_attributes:
                    intersectional.append(
                        self._compute_intersectional(records, attr_combo, config)
                    )
            else:
                # Default: pairwise intersections
                attrs = config.attributes_to_audit
                for i in range(len(attrs)):
                    for j in range(i + 1, len(attrs)):
                        intersectional.append(
                            self._compute_intersectional(
                                records, [attrs[i], attrs[j]], config
                            )
                        )

            metrics = FairnessMetrics(
                demographic_parity=demographic_parity,
                equal_opportunity=equal_opportunity,
                predictive_parity=predictive_parity,
                individual_fairness=individual_fairness,
                intersectional=intersectional,
            )
            metrics.overall_fairness_score = self._compute_overall_score(metrics)

            recommendations = self._generate_recommendations(metrics, records, config)

            # FDA compliance
            fda_compliance = None
            if request.plan_demographics:
                fda_compliance = self._check_fda_compliance(
                    records, request.plan_demographics
                )

            audit = FairnessAuditResponse(
                audit_id=str(uuid.uuid4()),
                trial_id=request.trial_id,
                status=AuditStatus.COMPLETED,
                config=config,
                metrics=metrics,
                recommendations=recommendations,
                total_records=len(records),
                created_at=datetime.now(timezone.utc),
                fda_compliance=fda_compliance,
            )

            store.audits.append(audit)
            logger.info(
                "Completed fairness audit: trial=%s audit_id=%s score=%.3f records=%d",
                request.trial_id,
                audit.audit_id,
                metrics.overall_fairness_score,
                len(records),
            )
            return audit

    def get_audit(self, audit_id: str) -> FairnessAuditResponse | None:
        """Retrieve a specific audit report by ID."""
        with self._lock:
            for store in self._stores.values():
                for audit in store.audits:
                    if audit.audit_id == audit_id:
                        return audit
            return None

    def list_audits(
        self, trial_id: str | None = None
    ) -> list[FairnessAuditResponse]:
        """List audit reports, optionally filtered by trial."""
        with self._lock:
            if trial_id:
                store = self._get_store(trial_id)
                return list(store.audits)
            # All audits
            result: list[FairnessAuditResponse] = []
            for store in self._stores.values():
                result.extend(store.audits)
            return result

    def get_recommendations(
        self, audit_id: str
    ) -> list[BiasRecommendation]:
        """Get recommendations for a specific audit."""
        audit = self.get_audit(audit_id)
        if audit is None:
            return []
        return audit.recommendations

    def get_trends(self, trial_id: str) -> FairnessTrend:
        """Get fairness metric trends over time for a trial."""
        with self._lock:
            store = self._get_store(trial_id)
            data_points: list[FairnessTrendPoint] = []

            for audit in store.audits:
                dp_avg = 0.0
                dp_count = 0
                for dp in audit.metrics.demographic_parity:
                    if dp.group_rates:
                        dp_avg += dp.disparity_ratio
                        dp_count += 1
                dp_avg = dp_avg / dp_count if dp_count > 0 else 1.0

                eo_avg = 0.0
                eo_count = 0
                for eo in audit.metrics.equal_opportunity:
                    if eo.group_tpr:
                        eo_avg += eo.disparity_ratio
                        eo_count += 1
                eo_avg = eo_avg / eo_count if eo_count > 0 else 1.0

                pp_avg = 0.0
                pp_count = 0
                for pp in audit.metrics.predictive_parity:
                    if pp.group_ppv:
                        pp_avg += pp.disparity_ratio
                        pp_count += 1
                pp_avg = pp_avg / pp_count if pp_count > 0 else 1.0

                data_points.append(
                    FairnessTrendPoint(
                        audit_id=audit.audit_id,
                        timestamp=audit.created_at or datetime.now(timezone.utc),
                        overall_fairness_score=audit.metrics.overall_fairness_score,
                        demographic_parity_avg=round(dp_avg, 6),
                        equal_opportunity_avg=round(eo_avg, 6),
                        predictive_parity_avg=round(pp_avg, 6),
                    )
                )

            # Determine trend direction
            direction = "stable"
            if len(data_points) >= 2:
                first_score = data_points[0].overall_fairness_score
                last_score = data_points[-1].overall_fairness_score
                delta = last_score - first_score
                if delta > 0.05:
                    direction = "improving"
                elif delta < -0.05:
                    direction = "declining"

            return FairnessTrend(
                trial_id=trial_id,
                data_points=data_points,
                trend_direction=direction,
            )

    def get_platform_summary(self) -> PlatformFairnessSummary:
        """Get platform-wide fairness summary across all trials."""
        with self._lock:
            trial_summaries: list[TrialFairnessSummary] = []
            total_audits = 0
            total_scores: list[float] = []
            violations_count = 0

            for trial_id, store in self._stores.items():
                if not store.audits:
                    continue
                latest = store.audits[-1]
                has_violations = any(
                    dp.four_fifths_violated for dp in latest.metrics.demographic_parity
                )
                if has_violations:
                    violations_count += 1

                trial_summaries.append(
                    TrialFairnessSummary(
                        trial_id=trial_id,
                        latest_fairness_score=latest.metrics.overall_fairness_score,
                        total_audits=len(store.audits),
                        has_violations=has_violations,
                        last_audit_at=latest.created_at,
                    )
                )
                total_audits += len(store.audits)
                total_scores.append(latest.metrics.overall_fairness_score)

            avg_score = sum(total_scores) / len(total_scores) if total_scores else 0.0

            return PlatformFairnessSummary(
                total_trials_audited=len(trial_summaries),
                total_audits=total_audits,
                average_fairness_score=round(avg_score, 6),
                trials_with_violations=violations_count,
                trial_summaries=trial_summaries,
                generated_at=datetime.now(timezone.utc),
            )

    def get_stats(self) -> dict[str, Any]:
        """Get aggregate service statistics."""
        with self._lock:
            total_trials = len(self._stores)
            total_records = sum(
                len(store.outcomes) for store in self._stores.values()
            )
            total_audits = sum(
                len(store.audits) for store in self._stores.values()
            )
            return {
                "total_trials_tracked": total_trials,
                "total_screening_records": total_records,
                "total_audits": total_audits,
            }


# =============================================================================
# Singleton accessor
# =============================================================================

_service_instance: FairnessAuditService | None = None
_service_lock = threading.Lock()


def get_fairness_audit_service() -> FairnessAuditService:
    """Get or create the singleton FairnessAuditService."""
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = FairnessAuditService()
                logger.info("FairnessAuditService initialized")
    return _service_instance
