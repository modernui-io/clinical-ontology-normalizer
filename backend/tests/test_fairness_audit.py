"""Tests for FairnessAuditService (VP-DS-5).

Covers:
- Demographic parity: equal rates (pass), unequal rates (flag)
- Four-fifths rule: at boundary, below boundary
- Equal opportunity calculation
- Predictive parity calculation
- Individual fairness: similar patients, different outcomes
- Intersectional analysis
- Bias mitigation recommendations
- FDA diversity compliance
- Historical trend tracking
- Empty/single-group edge cases
- Platform-wide aggregation
- Audit lifecycle (create, retrieve, list)
- Configurable thresholds
- Thread safety
- API endpoint smoke tests
"""

from __future__ import annotations

import threading

import pytest

from app.schemas.fairness_audit import (
    AuditStatus,
    BiasRecommendationType,
    FairnessAuditConfig,
    FairnessAuditCreate,
    FairnessAuditResponse,
    FairnessMetrics,
    FairnessTrend,
    IndividualFairnessResult,
    PlatformFairnessSummary,
    ProtectedAttribute,
    RecordScreeningOutcomeRequest,
    ScreeningOutcome,
    ScreeningOutcomeRecord,
)
from app.services.fairness_audit_service import FairnessAuditService


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def service() -> FairnessAuditService:
    """Fresh fairness audit service for each test."""
    return FairnessAuditService()


TRIAL_ID = "trial-fairness-001"


def _outcome(
    patient_id: str = "p1",
    trial_id: str = TRIAL_ID,
    result: ScreeningOutcome = ScreeningOutcome.PASSED,
    actually_eligible: bool | None = None,
    age_group: str | None = "31-45",
    sex: str | None = "Male",
    race: str | None = "White",
    ethnicity: str | None = "Not Hispanic/Latino",
    clinical_features: dict[str, float] | None = None,
) -> ScreeningOutcomeRecord:
    """Helper to build a ScreeningOutcomeRecord."""
    return ScreeningOutcomeRecord(
        patient_id=patient_id,
        trial_id=trial_id,
        screening_result=result,
        actually_eligible=actually_eligible,
        age_group=age_group,
        sex=sex,
        race=race,
        ethnicity=ethnicity,
        clinical_features=clinical_features,
    )


def _seed_equal_groups(service: FairnessAuditService, trial_id: str = TRIAL_ID) -> None:
    """Seed perfectly balanced groups: equal pass rates across race."""
    groups = ["White", "Black/African American", "Asian", "Hispanic/Latino"]
    for i, race in enumerate(groups):
        for j in range(10):
            pid = f"eq-{race}-{j}"
            # 8 out of 10 pass for every group
            result = ScreeningOutcome.PASSED if j < 8 else ScreeningOutcome.FAILED
            service.record_screening_outcome(
                _outcome(
                    patient_id=pid,
                    trial_id=trial_id,
                    result=result,
                    race=race,
                    sex="Male" if j % 2 == 0 else "Female",
                    age_group="31-45",
                    ethnicity="Not Hispanic/Latino",
                )
            )


def _seed_biased_groups(service: FairnessAuditService, trial_id: str = TRIAL_ID) -> None:
    """Seed groups with biased pass rates (White: 90%, Black: 50%)."""
    # White group: 9/10 pass
    for j in range(10):
        service.record_screening_outcome(
            _outcome(
                patient_id=f"bias-w-{j}",
                trial_id=trial_id,
                result=ScreeningOutcome.PASSED if j < 9 else ScreeningOutcome.FAILED,
                race="White",
                sex="Male" if j % 2 == 0 else "Female",
            )
        )
    # Black group: 5/10 pass
    for j in range(10):
        service.record_screening_outcome(
            _outcome(
                patient_id=f"bias-b-{j}",
                trial_id=trial_id,
                result=ScreeningOutcome.PASSED if j < 5 else ScreeningOutcome.FAILED,
                race="Black/African American",
                sex="Male" if j % 2 == 0 else "Female",
            )
        )


# =============================================================================
# Demographic Parity Tests
# =============================================================================


class TestDemographicParity:
    """Tests for demographic parity analysis."""

    def test_equal_pass_rates_no_violation(self, service: FairnessAuditService) -> None:
        """When all groups have equal pass rates, no violation is flagged."""
        _seed_equal_groups(service)
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))
        race_dp = next(
            dp for dp in audit.metrics.demographic_parity
            if dp.attribute == ProtectedAttribute.RACE
        )
        assert not race_dp.four_fifths_violated
        assert race_dp.disparity_ratio == 1.0

    def test_unequal_pass_rates_flags_violation(self, service: FairnessAuditService) -> None:
        """When one group has much lower pass rate, violation is flagged."""
        _seed_biased_groups(service)
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))
        race_dp = next(
            dp for dp in audit.metrics.demographic_parity
            if dp.attribute == ProtectedAttribute.RACE
        )
        assert race_dp.four_fifths_violated
        # 0.5 / 0.9 ~= 0.555
        assert race_dp.disparity_ratio < 0.8

    def test_disparity_ratio_calculation(self, service: FairnessAuditService) -> None:
        """Disparity ratio is correctly computed as min_rate/max_rate."""
        _seed_biased_groups(service)
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))
        race_dp = next(
            dp for dp in audit.metrics.demographic_parity
            if dp.attribute == ProtectedAttribute.RACE
        )
        expected_ratio = 0.5 / 0.9
        assert abs(race_dp.disparity_ratio - expected_ratio) < 0.01

    def test_group_rates_populated(self, service: FairnessAuditService) -> None:
        """Group rates contain correct totals and pass counts."""
        _seed_equal_groups(service)
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))
        race_dp = next(
            dp for dp in audit.metrics.demographic_parity
            if dp.attribute == ProtectedAttribute.RACE
        )
        for gr in race_dp.group_rates:
            assert gr.total == 10
            assert gr.passed == 8
            assert abs(gr.rate - 0.8) < 0.01


class TestFourFifthsRule:
    """Tests for the four-fifths (80%) rule."""

    def test_at_boundary_no_violation(self, service: FairnessAuditService) -> None:
        """At exactly 0.8 ratio, no violation should be flagged."""
        # Group A: 10/10 pass, Group B: 8/10 pass -> ratio = 0.8
        for j in range(10):
            service.record_screening_outcome(
                _outcome(patient_id=f"a-{j}", race="White", result=ScreeningOutcome.PASSED)
            )
        for j in range(10):
            result = ScreeningOutcome.PASSED if j < 8 else ScreeningOutcome.FAILED
            service.record_screening_outcome(
                _outcome(patient_id=f"b-{j}", race="Asian", result=result)
            )
        config = FairnessAuditConfig(
            attributes_to_audit=[ProtectedAttribute.RACE],
            min_group_size=1,
        )
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        race_dp = audit.metrics.demographic_parity[0]
        # ratio = 0.8 / 1.0 = 0.8, which is NOT < 0.8
        assert not race_dp.four_fifths_violated

    def test_below_boundary_violation(self, service: FairnessAuditService) -> None:
        """Below 0.8 ratio, violation should be flagged."""
        # Group A: 10/10 pass, Group B: 7/10 pass -> ratio = 0.7
        for j in range(10):
            service.record_screening_outcome(
                _outcome(patient_id=f"a-{j}", race="White", result=ScreeningOutcome.PASSED)
            )
        for j in range(10):
            result = ScreeningOutcome.PASSED if j < 7 else ScreeningOutcome.FAILED
            service.record_screening_outcome(
                _outcome(patient_id=f"b-{j}", race="Asian", result=result)
            )
        config = FairnessAuditConfig(
            attributes_to_audit=[ProtectedAttribute.RACE],
            min_group_size=1,
        )
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        race_dp = audit.metrics.demographic_parity[0]
        assert race_dp.four_fifths_violated
        assert race_dp.disparity_ratio == pytest.approx(0.7, abs=0.01)

    def test_custom_threshold(self, service: FairnessAuditService) -> None:
        """Custom threshold changes when violation is flagged."""
        # ratio = 0.7, custom threshold = 0.6 => no violation
        for j in range(10):
            service.record_screening_outcome(
                _outcome(patient_id=f"a-{j}", race="White", result=ScreeningOutcome.PASSED)
            )
        for j in range(10):
            result = ScreeningOutcome.PASSED if j < 7 else ScreeningOutcome.FAILED
            service.record_screening_outcome(
                _outcome(patient_id=f"b-{j}", race="Asian", result=result)
            )
        config = FairnessAuditConfig(
            four_fifths_threshold=0.6,
            attributes_to_audit=[ProtectedAttribute.RACE],
            min_group_size=1,
        )
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        race_dp = audit.metrics.demographic_parity[0]
        assert not race_dp.four_fifths_violated


# =============================================================================
# Equal Opportunity Tests
# =============================================================================


class TestEqualOpportunity:
    """Tests for equal opportunity (TPR) analysis."""

    def test_equal_tpr_no_violation(self, service: FairnessAuditService) -> None:
        """Equal TPR across groups means no violation."""
        # Both groups: all actually eligible patients pass
        for j in range(10):
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"eo-w-{j}",
                    race="White",
                    result=ScreeningOutcome.PASSED,
                    actually_eligible=True,
                )
            )
        for j in range(10):
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"eo-b-{j}",
                    race="Black/African American",
                    result=ScreeningOutcome.PASSED,
                    actually_eligible=True,
                )
            )
        config = FairnessAuditConfig(
            attributes_to_audit=[ProtectedAttribute.RACE],
            min_group_size=1,
        )
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        eo = audit.metrics.equal_opportunity[0]
        assert not eo.four_fifths_violated
        assert eo.disparity_ratio == pytest.approx(1.0, abs=0.01)

    def test_unequal_tpr_flags_violation(self, service: FairnessAuditService) -> None:
        """Unequal TPR across groups flags violation."""
        # White: 10/10 eligible pass, Black: 5/10 eligible pass
        for j in range(10):
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"eo-w-{j}",
                    race="White",
                    result=ScreeningOutcome.PASSED,
                    actually_eligible=True,
                )
            )
        for j in range(10):
            result = ScreeningOutcome.PASSED if j < 5 else ScreeningOutcome.FAILED
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"eo-b-{j}",
                    race="Black/African American",
                    result=result,
                    actually_eligible=True,
                )
            )
        config = FairnessAuditConfig(
            attributes_to_audit=[ProtectedAttribute.RACE],
            min_group_size=1,
        )
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        eo = audit.metrics.equal_opportunity[0]
        assert eo.four_fifths_violated
        assert eo.disparity_ratio < 0.8

    def test_only_eligible_patients_considered(self, service: FairnessAuditService) -> None:
        """Only patients marked as actually_eligible=True are counted."""
        # Record 10 ineligible + 5 eligible for White
        for j in range(10):
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"eo-ine-w-{j}",
                    race="White",
                    result=ScreeningOutcome.PASSED,
                    actually_eligible=False,
                )
            )
        for j in range(5):
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"eo-eli-w-{j}",
                    race="White",
                    result=ScreeningOutcome.PASSED,
                    actually_eligible=True,
                )
            )
        config = FairnessAuditConfig(
            attributes_to_audit=[ProtectedAttribute.RACE],
            min_group_size=1,
        )
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        eo = audit.metrics.equal_opportunity[0]
        # Only 5 eligible considered, all passed => TPR = 1.0
        assert len(eo.group_tpr) == 1
        assert eo.group_tpr[0].total == 5


# =============================================================================
# Predictive Parity Tests
# =============================================================================


class TestPredictiveParity:
    """Tests for predictive parity (PPV) analysis."""

    def test_equal_ppv_no_violation(self, service: FairnessAuditService) -> None:
        """Equal PPV across groups means no violation."""
        for j in range(10):
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"pp-w-{j}",
                    race="White",
                    result=ScreeningOutcome.PASSED,
                    actually_eligible=True,
                )
            )
        for j in range(10):
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"pp-b-{j}",
                    race="Black/African American",
                    result=ScreeningOutcome.PASSED,
                    actually_eligible=True,
                )
            )
        config = FairnessAuditConfig(
            attributes_to_audit=[ProtectedAttribute.RACE],
            min_group_size=1,
        )
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        pp = audit.metrics.predictive_parity[0]
        assert not pp.four_fifths_violated

    def test_unequal_ppv_flags_violation(self, service: FairnessAuditService) -> None:
        """Unequal PPV across groups flags violation."""
        # White: 10/10 who passed are actually eligible (PPV=1.0)
        for j in range(10):
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"pp-w-{j}",
                    race="White",
                    result=ScreeningOutcome.PASSED,
                    actually_eligible=True,
                )
            )
        # Black: 5/10 who passed are actually eligible (PPV=0.5)
        for j in range(10):
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"pp-b-{j}",
                    race="Black/African American",
                    result=ScreeningOutcome.PASSED,
                    actually_eligible=j < 5,
                )
            )
        config = FairnessAuditConfig(
            attributes_to_audit=[ProtectedAttribute.RACE],
            min_group_size=1,
        )
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        pp = audit.metrics.predictive_parity[0]
        assert pp.four_fifths_violated
        assert pp.disparity_ratio == pytest.approx(0.5, abs=0.01)

    def test_only_passed_patients_counted(self, service: FairnessAuditService) -> None:
        """Only patients who passed screening are counted for PPV."""
        # 5 failed (should be excluded), 5 passed
        for j in range(5):
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"pp-fail-{j}",
                    race="White",
                    result=ScreeningOutcome.FAILED,
                    actually_eligible=True,
                )
            )
        for j in range(5):
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"pp-pass-{j}",
                    race="White",
                    result=ScreeningOutcome.PASSED,
                    actually_eligible=True,
                )
            )
        config = FairnessAuditConfig(
            attributes_to_audit=[ProtectedAttribute.RACE],
            min_group_size=1,
        )
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        pp = audit.metrics.predictive_parity[0]
        assert len(pp.group_ppv) == 1
        assert pp.group_ppv[0].total == 5


# =============================================================================
# Individual Fairness Tests
# =============================================================================


class TestIndividualFairness:
    """Tests for individual fairness analysis."""

    def test_similar_patients_same_outcome(self, service: FairnessAuditService) -> None:
        """Similar patients with same outcome -> high consistency."""
        features = {"lab_a": 5.0, "lab_b": 3.0, "age_score": 0.8}
        for j in range(5):
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"if-{j}",
                    result=ScreeningOutcome.PASSED,
                    clinical_features=features,
                )
            )
        config = FairnessAuditConfig(min_group_size=1)
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        ifa = audit.metrics.individual_fairness
        assert ifa is not None
        assert ifa.consistency_rate == 1.0
        assert ifa.inconsistent_pairs == 0

    def test_similar_patients_different_outcomes_flagged(self, service: FairnessAuditService) -> None:
        """Similar patients with different outcomes should be flagged."""
        features = {"lab_a": 5.0, "lab_b": 3.0}
        # 3 pass, 2 fail with same features
        for j in range(3):
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"if-pass-{j}",
                    result=ScreeningOutcome.PASSED,
                    clinical_features=features,
                )
            )
        for j in range(2):
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"if-fail-{j}",
                    result=ScreeningOutcome.FAILED,
                    clinical_features=features,
                )
            )
        config = FairnessAuditConfig(min_group_size=1, similarity_threshold=0.99)
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        ifa = audit.metrics.individual_fairness
        assert ifa is not None
        assert ifa.inconsistent_pairs > 0
        assert len(ifa.flagged_pairs) > 0
        assert ifa.consistency_rate < 1.0

    def test_dissimilar_patients_not_compared(self, service: FairnessAuditService) -> None:
        """Dissimilar patients should not be compared."""
        service.record_screening_outcome(
            _outcome(
                patient_id="if-a",
                result=ScreeningOutcome.PASSED,
                clinical_features={"lab_a": 10.0, "lab_b": 0.0},
            )
        )
        service.record_screening_outcome(
            _outcome(
                patient_id="if-b",
                result=ScreeningOutcome.FAILED,
                clinical_features={"lab_a": 0.0, "lab_b": 10.0},
            )
        )
        config = FairnessAuditConfig(min_group_size=1, similarity_threshold=0.9)
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        ifa = audit.metrics.individual_fairness
        assert ifa is not None
        # These are dissimilar (cosine ~0), so no pairs checked at high threshold
        assert ifa.total_pairs_checked == 0

    def test_no_clinical_features(self, service: FairnessAuditService) -> None:
        """Without clinical features, individual fairness returns empty."""
        for j in range(5):
            service.record_screening_outcome(
                _outcome(patient_id=f"no-feat-{j}", clinical_features=None)
            )
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))
        ifa = audit.metrics.individual_fairness
        assert ifa is not None
        assert ifa.total_pairs_checked == 0


# =============================================================================
# Intersectional Analysis Tests
# =============================================================================


class TestIntersectionalAnalysis:
    """Tests for intersectional analysis."""

    def test_race_sex_intersection(self, service: FairnessAuditService) -> None:
        """Intersectional analysis across race + sex."""
        # White Male: 10/10 pass, Black Female: 5/10 pass
        for j in range(10):
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"int-wm-{j}",
                    race="White",
                    sex="Male",
                    result=ScreeningOutcome.PASSED,
                )
            )
        for j in range(10):
            result = ScreeningOutcome.PASSED if j < 5 else ScreeningOutcome.FAILED
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"int-bf-{j}",
                    race="Black/African American",
                    sex="Female",
                    result=result,
                )
            )
        config = FairnessAuditConfig(
            attributes_to_audit=[ProtectedAttribute.RACE, ProtectedAttribute.SEX],
            intersectional_attributes=[
                [ProtectedAttribute.RACE, ProtectedAttribute.SEX]
            ],
            min_group_size=1,
        )
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        assert len(audit.metrics.intersectional) >= 1
        intersect = audit.metrics.intersectional[0]
        assert intersect.four_fifths_violated
        assert intersect.disparity_ratio < 0.8

    def test_default_pairwise_intersections(self, service: FairnessAuditService) -> None:
        """When no intersectional_attributes specified, defaults to pairwise."""
        _seed_equal_groups(service)
        config = FairnessAuditConfig(
            attributes_to_audit=[ProtectedAttribute.RACE, ProtectedAttribute.SEX],
            min_group_size=1,
        )
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        # Should have at least 1 pairwise intersection (race x sex)
        assert len(audit.metrics.intersectional) >= 1


# =============================================================================
# Bias Mitigation Recommendations Tests
# =============================================================================


class TestBiasRecommendations:
    """Tests for bias mitigation recommendations."""

    def test_criteria_review_on_dp_violation(self, service: FairnessAuditService) -> None:
        """CRITERIA_REVIEW recommended when demographic parity is violated."""
        _seed_biased_groups(service)
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))
        rec_types = [r.recommendation_type for r in audit.recommendations]
        assert BiasRecommendationType.CRITERIA_REVIEW in rec_types

    def test_threshold_adjustment_on_eo_violation(self, service: FairnessAuditService) -> None:
        """THRESHOLD_ADJUSTMENT recommended when equal opportunity violated."""
        # White: all eligible pass, Black: half eligible pass
        for j in range(10):
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"rec-w-{j}",
                    race="White",
                    result=ScreeningOutcome.PASSED,
                    actually_eligible=True,
                )
            )
        for j in range(10):
            result = ScreeningOutcome.PASSED if j < 5 else ScreeningOutcome.FAILED
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"rec-b-{j}",
                    race="Black/African American",
                    result=result,
                    actually_eligible=True,
                )
            )
        config = FairnessAuditConfig(
            attributes_to_audit=[ProtectedAttribute.RACE],
            min_group_size=1,
        )
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        rec_types = [r.recommendation_type for r in audit.recommendations]
        assert BiasRecommendationType.THRESHOLD_ADJUSTMENT in rec_types

    def test_data_collection_for_small_groups(self, service: FairnessAuditService) -> None:
        """DATA_COLLECTION recommended for groups near min_group_size."""
        # Only 6 records for a group (default min_group_size=5, threshold=2*5=10)
        for j in range(6):
            service.record_screening_outcome(
                _outcome(patient_id=f"small-{j}", race="White", result=ScreeningOutcome.PASSED)
            )
        config = FairnessAuditConfig(
            attributes_to_audit=[ProtectedAttribute.RACE],
            min_group_size=5,
        )
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        rec_types = [r.recommendation_type for r in audit.recommendations]
        assert BiasRecommendationType.DATA_COLLECTION in rec_types

    def test_no_action_when_fair(self, service: FairnessAuditService) -> None:
        """NO_ACTION recommended when all metrics are within range."""
        # Perfectly balanced: 20 patients per group, all 100% pass rate
        for race in ["White", "Black/African American"]:
            for j in range(20):
                service.record_screening_outcome(
                    _outcome(
                        patient_id=f"fair-{race}-{j}",
                        race=race,
                        result=ScreeningOutcome.PASSED,
                    )
                )
        config = FairnessAuditConfig(
            attributes_to_audit=[ProtectedAttribute.RACE],
            min_group_size=1,
        )
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        rec_types = [r.recommendation_type for r in audit.recommendations]
        assert BiasRecommendationType.NO_ACTION in rec_types

    def test_individual_fairness_low_consistency_recommendation(
        self, service: FairnessAuditService
    ) -> None:
        """Recommendation when individual fairness consistency is low."""
        features = {"lab_a": 5.0, "lab_b": 3.0}
        # 3 pass, 7 fail with same features (consistency = 3*7 fail pairs)
        for j in range(3):
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"if-rec-pass-{j}",
                    result=ScreeningOutcome.PASSED,
                    clinical_features=features,
                )
            )
        for j in range(7):
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"if-rec-fail-{j}",
                    result=ScreeningOutcome.FAILED,
                    clinical_features=features,
                )
            )
        config = FairnessAuditConfig(min_group_size=1, similarity_threshold=0.99)
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        descs = [r.description for r in audit.recommendations]
        assert any("consistency" in d.lower() for d in descs)


# =============================================================================
# FDA Diversity Compliance Tests
# =============================================================================


class TestFDACompliance:
    """Tests for FDA diversity plan compliance checking."""

    def test_compliant_demographics(self, service: FairnessAuditService) -> None:
        """When demographics meet plan targets, is_compliant is True."""
        for j in range(50):
            service.record_screening_outcome(
                _outcome(patient_id=f"fda-w-{j}", race="White")
            )
        for j in range(50):
            service.record_screening_outcome(
                _outcome(patient_id=f"fda-b-{j}", race="Black/African American")
            )
        plan = {"race": {"White": 40.0, "Black/African American": 40.0}}
        audit = service.run_audit(
            FairnessAuditCreate(trial_id=TRIAL_ID, plan_demographics=plan)
        )
        assert audit.fda_compliance is not None
        assert audit.fda_compliance.is_compliant

    def test_non_compliant_demographics(self, service: FairnessAuditService) -> None:
        """When demographics miss plan targets, gaps are reported."""
        for j in range(90):
            service.record_screening_outcome(
                _outcome(patient_id=f"fda-w-{j}", race="White")
            )
        for j in range(10):
            service.record_screening_outcome(
                _outcome(patient_id=f"fda-b-{j}", race="Black/African American")
            )
        plan = {"race": {"Black/African American": 30.0}}
        audit = service.run_audit(
            FairnessAuditCreate(trial_id=TRIAL_ID, plan_demographics=plan)
        )
        assert audit.fda_compliance is not None
        assert not audit.fda_compliance.is_compliant
        assert len(audit.fda_compliance.compliance_gaps) > 0


# =============================================================================
# Historical Trend Tracking Tests
# =============================================================================


class TestTrendTracking:
    """Tests for fairness metric trends over time."""

    def test_trend_data_points(self, service: FairnessAuditService) -> None:
        """Each audit creates a trend data point."""
        _seed_equal_groups(service)
        service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))
        service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))

        trend = service.get_trends(TRIAL_ID)
        assert len(trend.data_points) == 2

    def test_stable_trend(self, service: FairnessAuditService) -> None:
        """Stable fairness scores show 'stable' direction."""
        _seed_equal_groups(service)
        service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))
        service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))

        trend = service.get_trends(TRIAL_ID)
        assert trend.trend_direction == "stable"

    def test_improving_trend(self, service: FairnessAuditService) -> None:
        """Improving fairness scores show 'improving' direction."""
        # First audit: biased
        _seed_biased_groups(service, TRIAL_ID)
        service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))

        # Add more balanced data for second audit (overwrite patient records)
        for j in range(10):
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"bias-b-{j}",
                    trial_id=TRIAL_ID,
                    result=ScreeningOutcome.PASSED,
                    race="Black/African American",
                )
            )
        service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))

        trend = service.get_trends(TRIAL_ID)
        assert trend.trend_direction == "improving"

    def test_empty_trial_trend(self, service: FairnessAuditService) -> None:
        """Empty trial returns empty trend."""
        trend = service.get_trends("nonexistent")
        assert len(trend.data_points) == 0
        assert trend.trend_direction == "stable"


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_trial_audit(self, service: FairnessAuditService) -> None:
        """Audit on empty trial completes without error."""
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))
        assert audit.status == AuditStatus.COMPLETED
        assert audit.total_records == 0
        assert audit.metrics.overall_fairness_score == 1.0

    def test_single_group_no_disparity(self, service: FairnessAuditService) -> None:
        """Single group can't have disparity."""
        for j in range(10):
            service.record_screening_outcome(
                _outcome(patient_id=f"single-{j}", race="White")
            )
        config = FairnessAuditConfig(
            attributes_to_audit=[ProtectedAttribute.RACE],
            min_group_size=1,
        )
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        race_dp = audit.metrics.demographic_parity[0]
        assert race_dp.disparity_ratio == 1.0
        assert not race_dp.four_fifths_violated

    def test_all_fail_zero_rate(self, service: FairnessAuditService) -> None:
        """When all patients fail, rate is 0 and disparity ratio is 1.0."""
        for j in range(10):
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"allfail-w-{j}",
                    race="White",
                    result=ScreeningOutcome.FAILED,
                )
            )
        for j in range(10):
            service.record_screening_outcome(
                _outcome(
                    patient_id=f"allfail-b-{j}",
                    race="Black/African American",
                    result=ScreeningOutcome.FAILED,
                )
            )
        config = FairnessAuditConfig(
            attributes_to_audit=[ProtectedAttribute.RACE],
            min_group_size=1,
        )
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        race_dp = audit.metrics.demographic_parity[0]
        assert race_dp.min_rate == 0.0
        assert race_dp.max_rate == 0.0
        # 0/0 => 1.0 per our definition
        assert race_dp.disparity_ratio == 1.0

    def test_missing_attribute_excluded(self, service: FairnessAuditService) -> None:
        """Records with None attribute values are excluded from that analysis."""
        for j in range(10):
            service.record_screening_outcome(
                _outcome(patient_id=f"no-race-{j}", race=None)
            )
        config = FairnessAuditConfig(
            attributes_to_audit=[ProtectedAttribute.RACE],
            min_group_size=1,
        )
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        race_dp = audit.metrics.demographic_parity[0]
        assert len(race_dp.group_rates) == 0

    def test_min_group_size_filters_small_groups(self, service: FairnessAuditService) -> None:
        """Groups below min_group_size are excluded."""
        # White: 10 records, Asian: 2 records
        for j in range(10):
            service.record_screening_outcome(
                _outcome(patient_id=f"mingrp-w-{j}", race="White")
            )
        for j in range(2):
            service.record_screening_outcome(
                _outcome(patient_id=f"mingrp-a-{j}", race="Asian")
            )
        config = FairnessAuditConfig(
            attributes_to_audit=[ProtectedAttribute.RACE],
            min_group_size=5,
        )
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        race_dp = audit.metrics.demographic_parity[0]
        # Asian group should be filtered out
        group_names = [gr.group_value for gr in race_dp.group_rates]
        assert "Asian" not in group_names
        assert "White" in group_names

    def test_patient_deduplication(self, service: FairnessAuditService) -> None:
        """Recording same patient multiple times keeps latest."""
        service.record_screening_outcome(
            _outcome(patient_id="dup-1", result=ScreeningOutcome.FAILED, race="White")
        )
        service.record_screening_outcome(
            _outcome(patient_id="dup-1", result=ScreeningOutcome.PASSED, race="White")
        )
        config = FairnessAuditConfig(
            attributes_to_audit=[ProtectedAttribute.RACE],
            min_group_size=1,
        )
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        assert audit.total_records == 1
        race_dp = audit.metrics.demographic_parity[0]
        assert race_dp.group_rates[0].passed == 1


# =============================================================================
# Platform-wide Aggregation Tests
# =============================================================================


class TestPlatformSummary:
    """Tests for platform-wide fairness summary."""

    def test_platform_summary_empty(self, service: FairnessAuditService) -> None:
        """Platform summary with no data."""
        summary = service.get_platform_summary()
        assert summary.total_trials_audited == 0
        assert summary.total_audits == 0
        assert summary.average_fairness_score == 0.0

    def test_platform_summary_multiple_trials(self, service: FairnessAuditService) -> None:
        """Platform summary aggregates across multiple trials."""
        for trial_id in ["trial-a", "trial-b"]:
            _seed_equal_groups(service, trial_id)
            service.run_audit(FairnessAuditCreate(trial_id=trial_id))

        summary = service.get_platform_summary()
        assert summary.total_trials_audited == 2
        assert summary.total_audits == 2
        assert len(summary.trial_summaries) == 2

    def test_platform_summary_counts_violations(self, service: FairnessAuditService) -> None:
        """Platform summary counts trials with violations."""
        # Fair trial
        _seed_equal_groups(service, "fair-trial")
        service.run_audit(FairnessAuditCreate(trial_id="fair-trial"))

        # Biased trial
        _seed_biased_groups(service, "biased-trial")
        service.run_audit(FairnessAuditCreate(trial_id="biased-trial"))

        summary = service.get_platform_summary()
        assert summary.trials_with_violations >= 1


# =============================================================================
# Audit Lifecycle Tests
# =============================================================================


class TestAuditLifecycle:
    """Tests for audit CRUD operations."""

    def test_create_audit(self, service: FairnessAuditService) -> None:
        """Creating an audit returns a complete response."""
        _seed_equal_groups(service)
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))
        assert audit.audit_id
        assert audit.trial_id == TRIAL_ID
        assert audit.status == AuditStatus.COMPLETED
        assert audit.created_at is not None

    def test_retrieve_audit(self, service: FairnessAuditService) -> None:
        """Retrieve a specific audit by ID."""
        _seed_equal_groups(service)
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))
        retrieved = service.get_audit(audit.audit_id)
        assert retrieved is not None
        assert retrieved.audit_id == audit.audit_id

    def test_retrieve_nonexistent_audit(self, service: FairnessAuditService) -> None:
        """Retrieving nonexistent audit returns None."""
        result = service.get_audit("nonexistent-id")
        assert result is None

    def test_list_audits_by_trial(self, service: FairnessAuditService) -> None:
        """List audits filtered by trial."""
        _seed_equal_groups(service, "trial-a")
        _seed_equal_groups(service, "trial-b")
        service.run_audit(FairnessAuditCreate(trial_id="trial-a"))
        service.run_audit(FairnessAuditCreate(trial_id="trial-b"))

        audits_a = service.list_audits(trial_id="trial-a")
        assert len(audits_a) == 1
        assert audits_a[0].trial_id == "trial-a"

    def test_list_all_audits(self, service: FairnessAuditService) -> None:
        """List all audits across trials."""
        _seed_equal_groups(service, "trial-a")
        _seed_equal_groups(service, "trial-b")
        service.run_audit(FairnessAuditCreate(trial_id="trial-a"))
        service.run_audit(FairnessAuditCreate(trial_id="trial-b"))

        all_audits = service.list_audits()
        assert len(all_audits) == 2

    def test_get_recommendations_for_audit(self, service: FairnessAuditService) -> None:
        """Get recommendations for a specific audit."""
        _seed_biased_groups(service)
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))
        recs = service.get_recommendations(audit.audit_id)
        assert len(recs) > 0

    def test_get_recommendations_nonexistent(self, service: FairnessAuditService) -> None:
        """Recommendations for nonexistent audit returns empty."""
        recs = service.get_recommendations("nonexistent")
        assert recs == []


# =============================================================================
# Overall Fairness Score Tests
# =============================================================================


class TestOverallFairnessScore:
    """Tests for overall fairness score computation."""

    def test_perfect_fairness_score(self, service: FairnessAuditService) -> None:
        """Perfectly fair screening yields score near 1.0."""
        _seed_equal_groups(service)
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))
        assert audit.metrics.overall_fairness_score >= 0.95

    def test_biased_fairness_score_lower(self, service: FairnessAuditService) -> None:
        """Biased screening yields lower score."""
        _seed_biased_groups(service)
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))
        assert audit.metrics.overall_fairness_score < 0.9

    def test_score_between_zero_and_one(self, service: FairnessAuditService) -> None:
        """Score is always between 0 and 1."""
        _seed_biased_groups(service)
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))
        assert 0.0 <= audit.metrics.overall_fairness_score <= 1.0


# =============================================================================
# Configuration Tests
# =============================================================================


class TestConfiguration:
    """Tests for audit configuration."""

    def test_default_config(self, service: FairnessAuditService) -> None:
        """Default config uses all attributes and 0.8 threshold."""
        _seed_equal_groups(service)
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))
        assert audit.config.four_fifths_threshold == 0.8
        assert len(audit.config.attributes_to_audit) == 4

    def test_specific_attributes_only(self, service: FairnessAuditService) -> None:
        """Can audit specific attributes only."""
        _seed_equal_groups(service)
        config = FairnessAuditConfig(
            attributes_to_audit=[ProtectedAttribute.RACE],
        )
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        assert len(audit.metrics.demographic_parity) == 1
        assert audit.metrics.demographic_parity[0].attribute == ProtectedAttribute.RACE

    def test_custom_similarity_threshold(self, service: FairnessAuditService) -> None:
        """Custom similarity threshold is applied."""
        features = {"lab_a": 5.0}
        for j in range(5):
            service.record_screening_outcome(
                _outcome(patient_id=f"sim-{j}", clinical_features=features)
            )
        config = FairnessAuditConfig(similarity_threshold=0.5, min_group_size=1)
        audit = service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID, config=config))
        assert audit.metrics.individual_fairness is not None
        assert audit.metrics.individual_fairness.similarity_threshold == 0.5


# =============================================================================
# Thread Safety Tests
# =============================================================================


class TestThreadSafety:
    """Basic thread safety tests."""

    def test_concurrent_record_and_audit(self, service: FairnessAuditService) -> None:
        """Concurrent recording and auditing does not crash."""
        errors: list[Exception] = []

        def recorder() -> None:
            try:
                for j in range(20):
                    service.record_screening_outcome(
                        _outcome(
                            patient_id=f"thread-rec-{threading.current_thread().name}-{j}",
                            result=ScreeningOutcome.PASSED,
                        )
                    )
            except Exception as e:
                errors.append(e)

        def auditor() -> None:
            try:
                service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=recorder, name=f"r{i}") for i in range(3)]
        threads.append(threading.Thread(target=auditor, name="a"))
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0


# =============================================================================
# Service Stats Tests
# =============================================================================


class TestServiceStats:
    """Tests for service statistics."""

    def test_stats_empty(self, service: FairnessAuditService) -> None:
        """Stats on fresh service."""
        stats = service.get_stats()
        assert stats["total_trials_tracked"] == 0
        assert stats["total_screening_records"] == 0
        assert stats["total_audits"] == 0

    def test_stats_after_recording(self, service: FairnessAuditService) -> None:
        """Stats update after recording outcomes."""
        _seed_equal_groups(service)
        service.run_audit(FairnessAuditCreate(trial_id=TRIAL_ID))
        stats = service.get_stats()
        assert stats["total_trials_tracked"] == 1
        assert stats["total_screening_records"] == 40
        assert stats["total_audits"] == 1


# =============================================================================
# API Endpoint Smoke Tests
# =============================================================================


class TestAPIEndpoints:
    """Smoke tests for API endpoint functions (no HTTP server needed)."""

    @pytest.mark.asyncio
    async def test_run_audit_endpoint(self, service: FairnessAuditService) -> None:
        """The run_fairness_audit endpoint should return an audit response."""
        from app.api.fairness_audit import run_fairness_audit
        from unittest.mock import MagicMock

        import app.api.fairness_audit as api_module
        original = api_module.get_fairness_audit_service
        api_module.get_fairness_audit_service = lambda: service

        try:
            request = MagicMock()
            body = FairnessAuditCreate(trial_id="api-test-trial")
            result = await run_fairness_audit(request=request, body=body)
            assert isinstance(result, FairnessAuditResponse)
            assert result.trial_id == "api-test-trial"
            assert result.status == AuditStatus.COMPLETED
        finally:
            api_module.get_fairness_audit_service = original

    @pytest.mark.asyncio
    async def test_list_audits_endpoint(self, service: FairnessAuditService) -> None:
        """The list_audits endpoint should return a list."""
        from app.api.fairness_audit import list_audits
        from unittest.mock import MagicMock

        import app.api.fairness_audit as api_module
        original = api_module.get_fairness_audit_service
        api_module.get_fairness_audit_service = lambda: service

        try:
            request = MagicMock()
            result = await list_audits(request=request, trial_id=None)
            assert isinstance(result, list)
        finally:
            api_module.get_fairness_audit_service = original

    @pytest.mark.asyncio
    async def test_record_outcome_endpoint(self, service: FairnessAuditService) -> None:
        """The record_screening_outcome endpoint should record and return status."""
        from app.api.fairness_audit import record_screening_outcome
        from unittest.mock import MagicMock

        import app.api.fairness_audit as api_module
        original = api_module.get_fairness_audit_service
        api_module.get_fairness_audit_service = lambda: service

        try:
            request = MagicMock()
            body = RecordScreeningOutcomeRequest(
                outcome=_outcome(patient_id="api-p1", trial_id="api-trial")
            )
            result = await record_screening_outcome(request=request, body=body)
            assert result["status"] == "recorded"
            assert result["patient_id"] == "api-p1"
        finally:
            api_module.get_fairness_audit_service = original

    @pytest.mark.asyncio
    async def test_get_trends_endpoint(self, service: FairnessAuditService) -> None:
        """The get_trends endpoint should return a FairnessTrend."""
        from app.api.fairness_audit import get_trends
        from app.schemas.fairness_audit import FairnessTrend
        from unittest.mock import MagicMock

        import app.api.fairness_audit as api_module
        original = api_module.get_fairness_audit_service
        api_module.get_fairness_audit_service = lambda: service

        try:
            request = MagicMock()
            result = await get_trends(request=request, trial_id="api-trial")
            assert isinstance(result, FairnessTrend)
        finally:
            api_module.get_fairness_audit_service = original

    @pytest.mark.asyncio
    async def test_platform_summary_endpoint(self, service: FairnessAuditService) -> None:
        """The get_platform_summary endpoint should return summary."""
        from app.api.fairness_audit import get_platform_summary
        from unittest.mock import MagicMock

        import app.api.fairness_audit as api_module
        original = api_module.get_fairness_audit_service
        api_module.get_fairness_audit_service = lambda: service

        try:
            request = MagicMock()
            result = await get_platform_summary(request=request)
            assert isinstance(result, PlatformFairnessSummary)
        finally:
            api_module.get_fairness_audit_service = original

    @pytest.mark.asyncio
    async def test_get_audit_not_found(self, service: FairnessAuditService) -> None:
        """Getting a nonexistent audit should raise HTTPException."""
        from app.api.fairness_audit import get_audit
        from fastapi import HTTPException
        from unittest.mock import MagicMock

        import app.api.fairness_audit as api_module
        original = api_module.get_fairness_audit_service
        api_module.get_fairness_audit_service = lambda: service

        try:
            request = MagicMock()
            with pytest.raises(HTTPException) as exc_info:
                await get_audit(audit_id="nonexistent-id", request=request)
            assert exc_info.value.status_code == 404
        finally:
            api_module.get_fairness_audit_service = original

    @pytest.mark.asyncio
    async def test_get_recommendations_not_found(self, service: FairnessAuditService) -> None:
        """Getting recommendations for nonexistent audit should raise HTTPException."""
        from app.api.fairness_audit import get_recommendations
        from fastapi import HTTPException
        from unittest.mock import MagicMock

        import app.api.fairness_audit as api_module
        original = api_module.get_fairness_audit_service
        api_module.get_fairness_audit_service = lambda: service

        try:
            request = MagicMock()
            with pytest.raises(HTTPException) as exc_info:
                await get_recommendations(audit_id="nonexistent-id", request=request)
            assert exc_info.value.status_code == 404
        finally:
            api_module.get_fairness_audit_service = original
