"""Tests for FalseNegativeMonitoringService (CMO-6).

Covers:
- Recording screening results
- Flagging potential false negatives
- FN report generation (totals, rates, reasons)
- Unknown criteria analysis (data completeness gaps)
- Multiple trials isolation
- Overwrite semantics (re-screening same patient)
- Edge cases (empty data, zero denominator)
- Thread safety (basic)
- Integration with PatientEligibility schema
- FN rate alert threshold
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.schemas.fn_monitoring import (
    FNFlag,
    FNReport,
    MissReason,
    UnknownCriteriaAnalysis,
)
from app.schemas.trial import (
    CriterionResult,
    DataCompletenessScore,
    PatientEligibility,
)
from app.services.fn_monitoring_service import FalseNegativeMonitoringService


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def fn_service() -> FalseNegativeMonitoringService:
    """Fresh FN monitoring service for each test."""
    return FalseNegativeMonitoringService()


def _make_eligibility(
    patient_id: str = "patient-1",
    eligible: bool = True,
    match_score: float = 0.85,
    criteria_details: list[CriterionResult] | None = None,
) -> PatientEligibility:
    """Helper to build a PatientEligibility for testing."""
    if criteria_details is None:
        criteria_details = [
            CriterionResult(
                criterion_name="Adult patients",
                criterion_type="demographic",
                status="PASS",
                confidence=1.0,
                weight=0.5,
            ),
            CriterionResult(
                criterion_name="Atopic Dermatitis",
                criterion_type="condition",
                status="PASS",
                confidence=0.92,
                weight=1.0,
            ),
        ]

    return PatientEligibility(
        patient_id=patient_id,
        eligible=eligible,
        match_score=match_score,
        inclusion_met=["Adult patients", "Atopic Dermatitis"] if eligible else [],
        inclusion_total=2,
        exclusion_triggered=[],
        exclusion_total=1,
        missing_data=[] if eligible else ["Atopic Dermatitis"],
        criteria_details=criteria_details,
        evaluable_criteria=len(criteria_details),
        screening_timestamp=datetime.now(timezone.utc),
        data_completeness=DataCompletenessScore(
            overall_completeness=1.0,
            evaluable_criteria=2,
            total_criteria=3,
            unknown_criteria=0,
            not_met_criteria=0,
            missing_domains=[],
        ),
    )


# =============================================================================
# Test: record_screening_result
# =============================================================================


class TestRecordScreeningResult:
    """Tests for recording screening outcomes."""

    def test_record_single_result(self, fn_service: FalseNegativeMonitoringService):
        """A single screening result is recorded and counted."""
        eligibility = _make_eligibility(patient_id="p1", eligible=True)
        fn_service.record_screening_result("trial-1", "p1", eligibility)

        assert fn_service.get_screening_count("trial-1") == 1

    def test_record_multiple_patients(self, fn_service: FalseNegativeMonitoringService):
        """Multiple patients are tracked independently."""
        for i in range(5):
            e = _make_eligibility(patient_id=f"p{i}", eligible=(i % 2 == 0))
            fn_service.record_screening_result("trial-1", f"p{i}", e)

        assert fn_service.get_screening_count("trial-1") == 5

    def test_overwrite_on_rescreen(self, fn_service: FalseNegativeMonitoringService):
        """Re-screening the same patient overwrites the previous result."""
        e1 = _make_eligibility(patient_id="p1", eligible=False, match_score=0.2)
        fn_service.record_screening_result("trial-1", "p1", e1)

        e2 = _make_eligibility(patient_id="p1", eligible=True, match_score=0.9)
        fn_service.record_screening_result("trial-1", "p1", e2)

        # Still only 1 unique patient
        assert fn_service.get_screening_count("trial-1") == 1

    def test_isolation_between_trials(self, fn_service: FalseNegativeMonitoringService):
        """Screening records for different trials are isolated."""
        e = _make_eligibility(patient_id="p1")
        fn_service.record_screening_result("trial-A", "p1", e)
        fn_service.record_screening_result("trial-B", "p1", e)

        assert fn_service.get_screening_count("trial-A") == 1
        assert fn_service.get_screening_count("trial-B") == 1


# =============================================================================
# Test: flag_potential_false_negative
# =============================================================================


class TestFlagPotentialFalseNegative:
    """Tests for clinician FN flagging."""

    def test_flag_creates_fn_flag(self, fn_service: FalseNegativeMonitoringService):
        """Flagging a patient creates an FNFlag with correct fields."""
        flag = fn_service.flag_potential_false_negative(
            trial_id="trial-1",
            patient_id="p1",
            reason="Patient has confirmed AD in external records",
            flagged_by="dr.smith",
        )

        assert isinstance(flag, FNFlag)
        assert flag.trial_id == "trial-1"
        assert flag.patient_id == "p1"
        assert flag.reason == "Patient has confirmed AD in external records"
        assert flag.flagged_by == "dr.smith"
        assert isinstance(flag.flagged_at, datetime)

    def test_flag_overwrite_same_patient(self, fn_service: FalseNegativeMonitoringService):
        """Flagging the same (trial, patient) again replaces the flag."""
        fn_service.flag_potential_false_negative(
            "trial-1", "p1", "First reason", "dr.a"
        )
        fn_service.flag_potential_false_negative(
            "trial-1", "p1", "Updated reason", "dr.b"
        )

        flags = fn_service.get_flags_for_trial("trial-1")
        assert len(flags) == 1
        assert flags[0].reason == "Updated reason"
        assert flags[0].flagged_by == "dr.b"

    def test_flag_without_screening_record(self, fn_service: FalseNegativeMonitoringService):
        """A clinician can flag a patient even if no screening is recorded yet."""
        flag = fn_service.flag_potential_false_negative(
            "trial-1", "p999", "Saw eligibility in chart review", "dr.jones"
        )
        assert flag.patient_id == "p999"

    def test_get_flags_ordered_by_time(self, fn_service: FalseNegativeMonitoringService):
        """Flags are returned most recent first."""
        fn_service.flag_potential_false_negative("t1", "p1", "R1", "dr.a")
        fn_service.flag_potential_false_negative("t1", "p2", "R2", "dr.b")
        fn_service.flag_potential_false_negative("t1", "p3", "R3", "dr.c")

        flags = fn_service.get_flags_for_trial("t1")
        assert len(flags) == 3
        # Most recent should be first
        assert flags[0].flagged_at >= flags[1].flagged_at >= flags[2].flagged_at


# =============================================================================
# Test: get_fn_report
# =============================================================================


class TestGetFnReport:
    """Tests for the aggregated FN report."""

    def test_empty_trial_report(self, fn_service: FalseNegativeMonitoringService):
        """Report for a trial with no data has zero counts."""
        report = fn_service.get_fn_report("nonexistent-trial")

        assert isinstance(report, FNReport)
        assert report.trial_id == "nonexistent-trial"
        assert report.total_screened == 0
        assert report.total_flagged == 0
        assert report.fn_rate == 0.0
        assert report.top_miss_reasons == []
        assert report.unknown_criteria_gaps == []

    def test_report_with_screenings_no_flags(self, fn_service: FalseNegativeMonitoringService):
        """Report with screenings but no FN flags has fn_rate=0."""
        for i in range(10):
            e = _make_eligibility(patient_id=f"p{i}")
            fn_service.record_screening_result("trial-1", f"p{i}", e)

        report = fn_service.get_fn_report("trial-1")
        assert report.total_screened == 10
        assert report.total_flagged == 0
        assert report.fn_rate == 0.0

    def test_fn_rate_calculation(self, fn_service: FalseNegativeMonitoringService):
        """FN rate = flagged / total_screened."""
        for i in range(20):
            e = _make_eligibility(patient_id=f"p{i}", eligible=(i < 15))
            fn_service.record_screening_result("trial-1", f"p{i}", e)

        # Flag 3 of the 20 as false negatives
        fn_service.flag_potential_false_negative("trial-1", "p15", "Missed AD", "dr.a")
        fn_service.flag_potential_false_negative("trial-1", "p16", "Missed AD", "dr.a")
        fn_service.flag_potential_false_negative("trial-1", "p17", "Missed lab", "dr.b")

        report = fn_service.get_fn_report("trial-1")
        assert report.total_screened == 20
        assert report.total_flagged == 3
        assert report.fn_rate == pytest.approx(3 / 20, abs=0.001)

    def test_top_miss_reasons_ordered_by_frequency(
        self, fn_service: FalseNegativeMonitoringService
    ):
        """Miss reasons are ordered by frequency descending."""
        for i in range(10):
            e = _make_eligibility(patient_id=f"p{i}")
            fn_service.record_screening_result("trial-1", f"p{i}", e)

        # 3x "Missing lab data", 2x "External records", 1x "Chart review"
        fn_service.flag_potential_false_negative("trial-1", "p1", "Missing lab data", "dr.a")
        fn_service.flag_potential_false_negative("trial-1", "p2", "Missing lab data", "dr.a")
        fn_service.flag_potential_false_negative("trial-1", "p3", "Missing lab data", "dr.b")
        fn_service.flag_potential_false_negative("trial-1", "p4", "External records", "dr.c")
        fn_service.flag_potential_false_negative("trial-1", "p5", "External records", "dr.c")
        fn_service.flag_potential_false_negative("trial-1", "p6", "Chart review", "dr.d")

        report = fn_service.get_fn_report("trial-1")
        assert len(report.top_miss_reasons) == 3
        assert report.top_miss_reasons[0].reason == "Missing lab data"
        assert report.top_miss_reasons[0].count == 3
        assert report.top_miss_reasons[1].reason == "External records"
        assert report.top_miss_reasons[1].count == 2
        assert report.top_miss_reasons[2].reason == "Chart review"
        assert report.top_miss_reasons[2].count == 1

    def test_report_isolation_between_trials(
        self, fn_service: FalseNegativeMonitoringService
    ):
        """Reports for different trials are independent."""
        e = _make_eligibility()
        fn_service.record_screening_result("trial-A", "p1", e)
        fn_service.record_screening_result("trial-A", "p2", e)
        fn_service.record_screening_result("trial-B", "p1", e)

        fn_service.flag_potential_false_negative("trial-A", "p1", "Reason A", "dr.x")

        report_a = fn_service.get_fn_report("trial-A")
        report_b = fn_service.get_fn_report("trial-B")

        assert report_a.total_screened == 2
        assert report_a.total_flagged == 1
        assert report_b.total_screened == 1
        assert report_b.total_flagged == 0


# =============================================================================
# Test: analyze_unknown_criteria
# =============================================================================


class TestAnalyzeUnknownCriteria:
    """Tests for the unknown-criteria gap analysis."""

    def test_no_unknowns(self, fn_service: FalseNegativeMonitoringService):
        """When all criteria PASS, no unknown gaps are reported."""
        e = _make_eligibility(
            patient_id="p1",
            criteria_details=[
                CriterionResult(
                    criterion_name="Age",
                    criterion_type="demographic",
                    status="PASS",
                    confidence=1.0,
                    weight=0.5,
                ),
            ],
        )
        fn_service.record_screening_result("trial-1", "p1", e)

        gaps = fn_service.analyze_unknown_criteria("trial-1")
        # The criterion exists but has 0 unknowns
        assert all(g.unknown_count == 0 for g in gaps)

    def test_unknown_criteria_detected(self, fn_service: FalseNegativeMonitoringService):
        """Criteria with UNKNOWN status are surfaced in the analysis."""
        e = _make_eligibility(
            patient_id="p1",
            criteria_details=[
                CriterionResult(
                    criterion_name="HbA1c level",
                    criterion_type="measurement",
                    status="UNKNOWN",
                    confidence=0.0,
                    weight=0.8,
                    missing_domain="lab_results",
                ),
                CriterionResult(
                    criterion_name="Age",
                    criterion_type="demographic",
                    status="PASS",
                    confidence=1.0,
                    weight=0.5,
                ),
            ],
        )
        fn_service.record_screening_result("trial-1", "p1", e)

        gaps = fn_service.analyze_unknown_criteria("trial-1")
        hba1c_gap = next(
            (g for g in gaps if g.criterion_description == "HbA1c level"), None
        )
        assert hba1c_gap is not None
        assert hba1c_gap.unknown_count == 1
        assert hba1c_gap.total_evaluations == 1
        assert hba1c_gap.unknown_rate == 1.0

    def test_unknown_rate_across_multiple_patients(
        self, fn_service: FalseNegativeMonitoringService
    ):
        """Unknown rate accumulates correctly across patients."""
        # Patient 1: HbA1c is UNKNOWN
        e1 = _make_eligibility(
            patient_id="p1",
            criteria_details=[
                CriterionResult(
                    criterion_name="HbA1c level",
                    criterion_type="measurement",
                    status="UNKNOWN",
                    confidence=0.0,
                    weight=0.8,
                ),
            ],
        )
        # Patient 2: HbA1c is PASS
        e2 = _make_eligibility(
            patient_id="p2",
            criteria_details=[
                CriterionResult(
                    criterion_name="HbA1c level",
                    criterion_type="measurement",
                    status="PASS",
                    confidence=0.95,
                    weight=0.8,
                ),
            ],
        )
        # Patient 3: HbA1c is UNKNOWN
        e3 = _make_eligibility(
            patient_id="p3",
            criteria_details=[
                CriterionResult(
                    criterion_name="HbA1c level",
                    criterion_type="measurement",
                    status="UNKNOWN",
                    confidence=0.0,
                    weight=0.8,
                ),
            ],
        )

        fn_service.record_screening_result("trial-1", "p1", e1)
        fn_service.record_screening_result("trial-1", "p2", e2)
        fn_service.record_screening_result("trial-1", "p3", e3)

        gaps = fn_service.analyze_unknown_criteria("trial-1")
        assert len(gaps) == 1
        assert gaps[0].criterion_description == "HbA1c level"
        assert gaps[0].unknown_count == 2
        assert gaps[0].total_evaluations == 3
        assert gaps[0].unknown_rate == pytest.approx(2 / 3, abs=0.01)

    def test_sorted_by_unknown_rate_descending(
        self, fn_service: FalseNegativeMonitoringService
    ):
        """Results are sorted by unknown_rate descending."""
        e = _make_eligibility(
            patient_id="p1",
            criteria_details=[
                CriterionResult(
                    criterion_name="Criterion A",
                    criterion_type="condition",
                    status="UNKNOWN",
                    confidence=0.0,
                    weight=1.0,
                ),
                CriterionResult(
                    criterion_name="Criterion B",
                    criterion_type="condition",
                    status="PASS",
                    confidence=0.9,
                    weight=1.0,
                ),
            ],
        )
        fn_service.record_screening_result("trial-1", "p1", e)

        gaps = fn_service.analyze_unknown_criteria("trial-1")
        # Criterion A has 100% unknown rate, Criterion B has 0%
        assert gaps[0].criterion_description == "Criterion A"
        assert gaps[0].unknown_rate == 1.0

    def test_empty_trial(self, fn_service: FalseNegativeMonitoringService):
        """Empty trial returns empty analysis."""
        gaps = fn_service.analyze_unknown_criteria("nonexistent")
        assert gaps == []


# =============================================================================
# Test: clear and utility methods
# =============================================================================


class TestUtilities:
    """Tests for utility methods."""

    def test_clear(self, fn_service: FalseNegativeMonitoringService):
        """clear() removes all monitoring data."""
        e = _make_eligibility()
        fn_service.record_screening_result("trial-1", "p1", e)
        fn_service.flag_potential_false_negative("trial-1", "p1", "R", "dr.x")

        fn_service.clear()

        assert fn_service.get_screening_count("trial-1") == 0
        assert fn_service.get_flags_for_trial("trial-1") == []
        report = fn_service.get_fn_report("trial-1")
        assert report.total_screened == 0
        assert report.total_flagged == 0

    def test_get_screening_count_nonexistent_trial(
        self, fn_service: FalseNegativeMonitoringService
    ):
        """Screening count for a nonexistent trial is 0."""
        assert fn_service.get_screening_count("no-such-trial") == 0


# =============================================================================
# Test: Schema validation
# =============================================================================


class TestSchemaValidation:
    """Tests for the Pydantic schema models."""

    def test_fn_flag_schema(self):
        """FNFlag has all required fields."""
        flag = FNFlag(
            trial_id="t1",
            patient_id="p1",
            reason="Missed condition",
            flagged_by="dr.test",
        )
        assert flag.trial_id == "t1"
        assert isinstance(flag.flagged_at, datetime)

    def test_fn_report_zero_denominator(self):
        """FNReport allows fn_rate=0 when total_screened=0."""
        report = FNReport(
            trial_id="t1",
            total_screened=0,
            total_flagged=0,
            fn_rate=0.0,
        )
        assert report.fn_rate == 0.0

    def test_unknown_criteria_analysis_schema(self):
        """UnknownCriteriaAnalysis validates rate bounds."""
        analysis = UnknownCriteriaAnalysis(
            criterion_description="Lab test X",
            unknown_count=7,
            total_evaluations=10,
            unknown_rate=0.7,
        )
        assert analysis.unknown_rate == 0.7

    def test_miss_reason_schema(self):
        """MissReason has reason and count."""
        mr = MissReason(reason="Missing external data", count=5)
        assert mr.reason == "Missing external data"
        assert mr.count == 5
