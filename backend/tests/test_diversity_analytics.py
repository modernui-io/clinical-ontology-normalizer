"""Tests for DiversityAnalyticsService (VP-Product-4).

Covers:
- Demographic recording (single and multiple patients)
- Age distribution bucketing (all five buckets)
- Sex distribution
- Race distribution (FDA categories)
- Ethnicity distribution
- Representation checking (targets met and unmet)
- Overall diversity score calculation
- Underrepresentation detection
- Pipeline demographic analysis (screened -> eligible -> enrolled)
- Disproportionate dropout detection
- FDA diversity summary generation
- Diversity target persistence
- Stage filtering
- Empty trial edge cases
- Overwrite semantics (re-recording same patient/stage)
- Thread safety (basic)
- API endpoint smoke tests
"""

from __future__ import annotations

import threading

import pytest

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
    StageDemographics,
    age_to_bucket,
)
from app.services.diversity_analytics_service import DiversityAnalyticsService


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def service() -> DiversityAnalyticsService:
    """Fresh diversity analytics service for each test."""
    return DiversityAnalyticsService()


def _record(
    patient_id: str = "patient-1",
    age: int = 45,
    sex: Sex = Sex.FEMALE,
    race: Race = Race.WHITE,
    ethnicity: Ethnicity = Ethnicity.NOT_HISPANIC_LATINO,
    stage: PipelineStage = PipelineStage.SCREENED,
) -> DemographicRecord:
    """Helper to build a DemographicRecord."""
    return DemographicRecord(
        patient_id=patient_id,
        age=age,
        sex=sex,
        race=race,
        ethnicity=ethnicity,
        pipeline_stage=stage,
    )


TRIAL_ID = "trial-diversity-001"


# =============================================================================
# Age bucket tests
# =============================================================================


class TestAgeBucketing:
    """Test age-to-bucket mapping."""

    def test_age_bucket_18_30(self) -> None:
        assert age_to_bucket(18) == "18-30"
        assert age_to_bucket(25) == "18-30"
        assert age_to_bucket(30) == "18-30"

    def test_age_bucket_31_45(self) -> None:
        assert age_to_bucket(31) == "31-45"
        assert age_to_bucket(38) == "31-45"
        assert age_to_bucket(45) == "31-45"

    def test_age_bucket_46_60(self) -> None:
        assert age_to_bucket(46) == "46-60"
        assert age_to_bucket(53) == "46-60"
        assert age_to_bucket(60) == "46-60"

    def test_age_bucket_61_75(self) -> None:
        assert age_to_bucket(61) == "61-75"
        assert age_to_bucket(68) == "61-75"
        assert age_to_bucket(75) == "61-75"

    def test_age_bucket_75_plus(self) -> None:
        assert age_to_bucket(76) == "75+"
        assert age_to_bucket(85) == "75+"
        assert age_to_bucket(100) == "75+"


# =============================================================================
# Recording and report tests
# =============================================================================


class TestDemographicRecording:
    """Test recording demographics and generating reports."""

    def test_record_single_patient(self, service: DiversityAnalyticsService) -> None:
        """A single patient record should appear in the report."""
        service.record_demographic(TRIAL_ID, _record(patient_id="p1", age=25))
        report = service.get_diversity_report(TRIAL_ID)

        assert report.trial_id == TRIAL_ID
        assert report.total_patients == 1
        assert report.generated_at is not None

    def test_record_multiple_patients(self, service: DiversityAnalyticsService) -> None:
        """Multiple patients should all be counted."""
        for i in range(5):
            service.record_demographic(
                TRIAL_ID, _record(patient_id=f"p{i}", age=30 + i * 5)
            )
        report = service.get_diversity_report(TRIAL_ID)
        assert report.total_patients == 5

    def test_overwrite_same_patient_same_stage(self, service: DiversityAnalyticsService) -> None:
        """Re-recording the same patient at the same stage overwrites."""
        service.record_demographic(TRIAL_ID, _record(patient_id="p1", age=25, sex=Sex.MALE))
        service.record_demographic(TRIAL_ID, _record(patient_id="p1", age=26, sex=Sex.FEMALE))

        report = service.get_diversity_report(TRIAL_ID)
        assert report.total_patients == 1

        # Should reflect the updated record
        female_entry = next(e for e in report.sex_distribution if e.category == "Female")
        assert female_entry.count == 1

    def test_empty_trial_report(self, service: DiversityAnalyticsService) -> None:
        """An empty trial should return zero-count report."""
        report = service.get_diversity_report("nonexistent-trial")
        assert report.total_patients == 0
        assert all(e.count == 0 for e in report.age_distribution)
        assert all(e.count == 0 for e in report.sex_distribution)
        assert all(e.count == 0 for e in report.race_distribution)
        assert all(e.count == 0 for e in report.ethnicity_distribution)


# =============================================================================
# Distribution tests
# =============================================================================


class TestDistributions:
    """Test age, sex, race, and ethnicity distribution calculations."""

    def test_age_distribution(self, service: DiversityAnalyticsService) -> None:
        """Age distribution should bucket patients correctly."""
        ages = [20, 35, 50, 65, 80]
        for i, age in enumerate(ages):
            service.record_demographic(TRIAL_ID, _record(patient_id=f"p{i}", age=age))

        report = service.get_diversity_report(TRIAL_ID)
        age_dist = {e.category: e.count for e in report.age_distribution}

        assert age_dist["18-30"] == 1
        assert age_dist["31-45"] == 1
        assert age_dist["46-60"] == 1
        assert age_dist["61-75"] == 1
        assert age_dist["75+"] == 1

    def test_age_distribution_percentages(self, service: DiversityAnalyticsService) -> None:
        """Percentages should sum to 100%."""
        ages = [20, 35, 50, 65, 80]
        for i, age in enumerate(ages):
            service.record_demographic(TRIAL_ID, _record(patient_id=f"p{i}", age=age))

        report = service.get_diversity_report(TRIAL_ID)
        total_pct = sum(e.percentage for e in report.age_distribution)
        assert abs(total_pct - 100.0) < 0.1

    def test_sex_distribution(self, service: DiversityAnalyticsService) -> None:
        """Sex distribution should correctly count each category."""
        service.record_demographic(TRIAL_ID, _record(patient_id="p1", sex=Sex.MALE))
        service.record_demographic(TRIAL_ID, _record(patient_id="p2", sex=Sex.FEMALE))
        service.record_demographic(TRIAL_ID, _record(patient_id="p3", sex=Sex.FEMALE))
        service.record_demographic(TRIAL_ID, _record(patient_id="p4", sex=Sex.OTHER))

        report = service.get_diversity_report(TRIAL_ID)
        sex_dist = {e.category: e for e in report.sex_distribution}

        assert sex_dist["Male"].count == 1
        assert sex_dist["Female"].count == 2
        assert sex_dist["Other"].count == 1
        assert sex_dist["Unknown"].count == 0
        assert sex_dist["Female"].percentage == 50.0

    def test_race_distribution_fda_categories(self, service: DiversityAnalyticsService) -> None:
        """Race distribution should include all FDA standard categories."""
        service.record_demographic(
            TRIAL_ID, _record(patient_id="p1", race=Race.BLACK_AFRICAN_AMERICAN)
        )
        service.record_demographic(
            TRIAL_ID, _record(patient_id="p2", race=Race.WHITE)
        )
        service.record_demographic(
            TRIAL_ID, _record(patient_id="p3", race=Race.ASIAN)
        )
        service.record_demographic(
            TRIAL_ID, _record(patient_id="p4", race=Race.WHITE)
        )

        report = service.get_diversity_report(TRIAL_ID)
        race_dist = {e.category: e for e in report.race_distribution}

        # All 7 FDA categories should be present
        assert len(report.race_distribution) == 7
        assert race_dist["White"].count == 2
        assert race_dist["Black/African American"].count == 1
        assert race_dist["Asian"].count == 1
        assert race_dist["American Indian/Alaska Native"].count == 0
        assert race_dist["Native Hawaiian/Pacific Islander"].count == 0
        assert race_dist["Multiple"].count == 0
        assert race_dist["Unknown"].count == 0

    def test_ethnicity_distribution(self, service: DiversityAnalyticsService) -> None:
        """Ethnicity distribution should track Hispanic/Latino and Not."""
        service.record_demographic(
            TRIAL_ID, _record(patient_id="p1", ethnicity=Ethnicity.HISPANIC_LATINO)
        )
        service.record_demographic(
            TRIAL_ID, _record(patient_id="p2", ethnicity=Ethnicity.NOT_HISPANIC_LATINO)
        )
        service.record_demographic(
            TRIAL_ID, _record(patient_id="p3", ethnicity=Ethnicity.NOT_HISPANIC_LATINO)
        )

        report = service.get_diversity_report(TRIAL_ID)
        eth_dist = {e.category: e for e in report.ethnicity_distribution}

        assert eth_dist["Hispanic/Latino"].count == 1
        assert eth_dist["Not Hispanic/Latino"].count == 2
        assert abs(eth_dist["Hispanic/Latino"].percentage - 33.33) < 0.1


# =============================================================================
# Representation checking tests
# =============================================================================


class TestRepresentationChecking:
    """Test representation target checking."""

    def _seed_diverse_trial(self, service: DiversityAnalyticsService) -> None:
        """Seed a trial with diverse demographics."""
        patients = [
            _record(patient_id="p1", race=Race.WHITE, sex=Sex.MALE, age=30),
            _record(patient_id="p2", race=Race.WHITE, sex=Sex.FEMALE, age=45),
            _record(patient_id="p3", race=Race.BLACK_AFRICAN_AMERICAN, sex=Sex.FEMALE, age=55),
            _record(patient_id="p4", race=Race.ASIAN, sex=Sex.MALE, age=65),
            _record(patient_id="p5", race=Race.WHITE, sex=Sex.FEMALE, age=25),
            _record(patient_id="p6", race=Race.BLACK_AFRICAN_AMERICAN, sex=Sex.MALE, age=40),
            _record(patient_id="p7", race=Race.WHITE, sex=Sex.FEMALE, age=50),
            _record(patient_id="p8", race=Race.ASIAN, sex=Sex.FEMALE, age=35),
            _record(patient_id="p9", race=Race.WHITE, sex=Sex.MALE, age=70),
            _record(patient_id="p10", race=Race.NATIVE_HAWAIIAN_PACIFIC_ISLANDER, sex=Sex.FEMALE, age=28),
        ]
        for p in patients:
            service.record_demographic(TRIAL_ID, p)

    def test_target_met(self, service: DiversityAnalyticsService) -> None:
        """Targets that are met should be marked as such."""
        self._seed_diverse_trial(service)

        targets = [
            RepresentationTarget(group="race", category="White", target_pct=40.0),
        ]
        check = service.check_representation(TRIAL_ID, targets=targets)

        assert check.trial_id == TRIAL_ID
        assert len(check.targets) == 1
        assert check.targets[0].is_met is True
        assert check.targets[0].actual_pct == 50.0
        assert check.targets[0].gap < 0  # exceeded target
        assert len(check.underrepresented_groups) == 0

    def test_target_not_met(self, service: DiversityAnalyticsService) -> None:
        """Targets that are not met should flag underrepresentation."""
        self._seed_diverse_trial(service)

        targets = [
            RepresentationTarget(group="race", category="Black/African American", target_pct=30.0),
        ]
        check = service.check_representation(TRIAL_ID, targets=targets)

        assert check.targets[0].is_met is False
        assert check.targets[0].actual_pct == 20.0
        assert check.targets[0].gap == 10.0
        assert "race:Black/African American" in check.underrepresented_groups

    def test_overall_diversity_score(self, service: DiversityAnalyticsService) -> None:
        """Overall score should reflect percentage of targets met."""
        self._seed_diverse_trial(service)

        targets = [
            RepresentationTarget(group="race", category="White", target_pct=40.0),
            RepresentationTarget(group="race", category="Black/African American", target_pct=30.0),
            RepresentationTarget(group="sex", category="Female", target_pct=50.0),
            RepresentationTarget(group="race", category="Asian", target_pct=15.0),
        ]
        check = service.check_representation(TRIAL_ID, targets=targets)

        # White (50% >= 40%), Black (20% < 30%), Female (50% >= 50%), Asian (20% >= 15%)
        # 3 out of 4 met
        assert check.overall_diversity_score == 75.0
        assert len(check.underrepresented_groups) == 1

    def test_stored_targets(self, service: DiversityAnalyticsService) -> None:
        """set_targets should persist targets for later check_representation calls."""
        self._seed_diverse_trial(service)

        targets = [
            RepresentationTarget(group="race", category="White", target_pct=40.0),
            RepresentationTarget(group="sex", category="Male", target_pct=30.0),
        ]
        service.set_targets(TRIAL_ID, targets)

        # Call without explicit targets - should use stored
        check = service.check_representation(TRIAL_ID)
        assert len(check.targets) == 2
        assert check.overall_diversity_score == 100.0

    def test_empty_trial_representation(self, service: DiversityAnalyticsService) -> None:
        """Checking representation on empty trial should return 0% for all targets."""
        targets = [
            RepresentationTarget(group="race", category="White", target_pct=50.0),
        ]
        check = service.check_representation(TRIAL_ID, targets=targets)

        assert check.targets[0].actual_pct == 0.0
        assert check.targets[0].is_met is False
        assert check.overall_diversity_score == 0.0


# =============================================================================
# Pipeline demographics tests
# =============================================================================


class TestPipelineDemographics:
    """Test demographics across pipeline stages."""

    def test_pipeline_all_stages(self, service: DiversityAnalyticsService) -> None:
        """Demographics should be tracked at each stage independently."""
        # Screened: 4 patients
        for i in range(4):
            service.record_demographic(
                TRIAL_ID,
                _record(patient_id=f"p{i}", age=30 + i * 10, stage=PipelineStage.SCREENED),
            )

        # Eligible: 3 patients (one dropped)
        for i in range(3):
            service.record_demographic(
                TRIAL_ID,
                _record(patient_id=f"p{i}", age=30 + i * 10, stage=PipelineStage.ELIGIBLE),
            )

        # Enrolled: 2 patients
        for i in range(2):
            service.record_demographic(
                TRIAL_ID,
                _record(patient_id=f"p{i}", age=30 + i * 10, stage=PipelineStage.ENROLLED),
            )

        pipeline = service.get_pipeline_demographics(TRIAL_ID)
        assert pipeline.trial_id == TRIAL_ID
        assert pipeline.screened_demographics is not None
        assert pipeline.screened_demographics.total_patients == 4
        assert pipeline.eligible_demographics is not None
        assert pipeline.eligible_demographics.total_patients == 3
        assert pipeline.enrolled_demographics is not None
        assert pipeline.enrolled_demographics.total_patients == 2

    def test_disproportionate_dropout_detection(self, service: DiversityAnalyticsService) -> None:
        """Should detect when a group disproportionately drops out."""
        # Screened: 50% Black, 50% White
        service.record_demographic(
            TRIAL_ID,
            _record(patient_id="p1", race=Race.BLACK_AFRICAN_AMERICAN, stage=PipelineStage.SCREENED),
        )
        service.record_demographic(
            TRIAL_ID,
            _record(patient_id="p2", race=Race.BLACK_AFRICAN_AMERICAN, stage=PipelineStage.SCREENED),
        )
        service.record_demographic(
            TRIAL_ID,
            _record(patient_id="p3", race=Race.WHITE, stage=PipelineStage.SCREENED),
        )
        service.record_demographic(
            TRIAL_ID,
            _record(patient_id="p4", race=Race.WHITE, stage=PipelineStage.SCREENED),
        )

        # Eligible: only White patients remain (disproportionate dropout of Black)
        service.record_demographic(
            TRIAL_ID,
            _record(patient_id="p3", race=Race.WHITE, stage=PipelineStage.ELIGIBLE),
        )
        service.record_demographic(
            TRIAL_ID,
            _record(patient_id="p4", race=Race.WHITE, stage=PipelineStage.ELIGIBLE),
        )

        pipeline = service.get_pipeline_demographics(TRIAL_ID)

        # Find the dropout analysis for Black/African American
        black_dropout = [
            d
            for d in pipeline.dropout_analysis
            if d.category == "Black/African American"
            and d.from_stage == "screened"
            and d.to_stage == "eligible"
        ]
        assert len(black_dropout) == 1
        assert black_dropout[0].disproportionate is True
        assert black_dropout[0].from_pct == 50.0
        assert black_dropout[0].to_pct == 0.0
        assert black_dropout[0].change_pct == -50.0

    def test_empty_pipeline(self, service: DiversityAnalyticsService) -> None:
        """Empty trial pipeline should return None for all stages."""
        pipeline = service.get_pipeline_demographics("empty-trial")
        assert pipeline.screened_demographics is None
        assert pipeline.eligible_demographics is None
        assert pipeline.enrolled_demographics is None
        assert pipeline.dropout_analysis == []


# =============================================================================
# FDA diversity summary tests
# =============================================================================


class TestFDADiversitySummary:
    """Test FDA-format diversity summary generation."""

    def test_fda_summary_with_enrolled(self, service: DiversityAnalyticsService) -> None:
        """FDA summary should focus on enrolled patients."""
        # Record as enrolled
        service.record_demographic(
            TRIAL_ID,
            _record(patient_id="p1", race=Race.WHITE, stage=PipelineStage.ENROLLED),
        )
        service.record_demographic(
            TRIAL_ID,
            _record(patient_id="p2", race=Race.BLACK_AFRICAN_AMERICAN, stage=PipelineStage.ENROLLED),
        )

        summary = service.generate_fda_diversity_summary(TRIAL_ID, enrollment_target=100)

        assert summary.trial_id == TRIAL_ID
        assert summary.total_enrolled == 2
        assert summary.enrollment_target == 100
        assert summary.report_date is not None
        assert len(summary.race_table) == 7
        assert len(summary.sex_table) == 4
        assert len(summary.ethnicity_table) == 3
        assert len(summary.age_table) == 5

    def test_fda_summary_empty_trial(self, service: DiversityAnalyticsService) -> None:
        """Empty trial should generate recommendations."""
        summary = service.generate_fda_diversity_summary("empty-trial")

        assert summary.total_enrolled == 0
        assert len(summary.recommendations) > 0

    def test_fda_summary_with_unmet_targets(self, service: DiversityAnalyticsService) -> None:
        """Summary should include recommendations for unmet targets."""
        # Seed all White patients
        for i in range(10):
            service.record_demographic(
                TRIAL_ID,
                _record(
                    patient_id=f"p{i}",
                    race=Race.WHITE,
                    stage=PipelineStage.ENROLLED,
                ),
            )

        # Set target for Black representation
        service.set_targets(TRIAL_ID, [
            RepresentationTarget(group="race", category="Black/African American", target_pct=20.0),
        ])

        summary = service.generate_fda_diversity_summary(TRIAL_ID)

        assert summary.diversity_targets_total == 1
        assert summary.diversity_targets_met == 0
        assert len(summary.underrepresented_groups) == 1
        assert len(summary.recommendations) > 0


# =============================================================================
# Stage filtering tests
# =============================================================================


class TestStageFiltering:
    """Test filtering reports by pipeline stage."""

    def test_report_filtered_by_stage(self, service: DiversityAnalyticsService) -> None:
        """Report should only include patients at the specified stage."""
        service.record_demographic(
            TRIAL_ID,
            _record(patient_id="p1", sex=Sex.MALE, stage=PipelineStage.SCREENED),
        )
        service.record_demographic(
            TRIAL_ID,
            _record(patient_id="p2", sex=Sex.FEMALE, stage=PipelineStage.ELIGIBLE),
        )

        screened_report = service.get_diversity_report(TRIAL_ID, stage=PipelineStage.SCREENED)
        assert screened_report.total_patients == 1

        eligible_report = service.get_diversity_report(TRIAL_ID, stage=PipelineStage.ELIGIBLE)
        assert eligible_report.total_patients == 1

    def test_report_unfiltered_uses_latest_stage(self, service: DiversityAnalyticsService) -> None:
        """Without stage filter, report should use latest stage per patient."""
        # Patient p1 has screened AND eligible records
        service.record_demographic(
            TRIAL_ID,
            _record(patient_id="p1", sex=Sex.MALE, stage=PipelineStage.SCREENED),
        )
        service.record_demographic(
            TRIAL_ID,
            _record(patient_id="p1", sex=Sex.MALE, stage=PipelineStage.ELIGIBLE),
        )
        # Patient p2 only screened
        service.record_demographic(
            TRIAL_ID,
            _record(patient_id="p2", sex=Sex.FEMALE, stage=PipelineStage.SCREENED),
        )

        # Unfiltered should return 2 patients (latest stage per patient)
        report = service.get_diversity_report(TRIAL_ID)
        assert report.total_patients == 2


# =============================================================================
# Thread safety test
# =============================================================================


class TestThreadSafety:
    """Basic thread safety tests."""

    def test_concurrent_recording(self, service: DiversityAnalyticsService) -> None:
        """Concurrent recording should not lose data."""
        errors: list[Exception] = []

        def record_batch(start: int) -> None:
            try:
                for i in range(start, start + 50):
                    service.record_demographic(
                        TRIAL_ID,
                        _record(patient_id=f"p{i}", age=20 + (i % 60)),
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_batch, args=(i * 50,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        report = service.get_diversity_report(TRIAL_ID)
        assert report.total_patients == 200


# =============================================================================
# Service stats test
# =============================================================================


class TestServiceStats:
    """Test service statistics."""

    def test_stats(self, service: DiversityAnalyticsService) -> None:
        """Stats should reflect recorded data."""
        service.record_demographic(TRIAL_ID, _record(patient_id="p1"))
        service.record_demographic("trial-2", _record(patient_id="p2"))

        stats = service.get_stats()
        assert stats["total_trials_tracked"] == 2
        assert stats["total_patient_records"] == 2


# =============================================================================
# API endpoint tests (unit-level, no HTTP server)
# =============================================================================


class TestAPIEndpoints:
    """Smoke tests for API endpoint functions (no HTTP server needed)."""

    @pytest.mark.asyncio
    async def test_get_diversity_report_endpoint(self, service: DiversityAnalyticsService) -> None:
        """The report endpoint function should return a DiversityReport."""
        from app.api.diversity_analytics import get_diversity_report

        service.record_demographic(TRIAL_ID, _record(patient_id="p1"))

        # Monkey-patch the service getter
        import app.api.diversity_analytics as api_module
        original = api_module.get_diversity_analytics_service
        api_module.get_diversity_analytics_service = lambda: service

        try:
            # Create a mock request
            from unittest.mock import MagicMock
            request = MagicMock()

            report = await get_diversity_report(TRIAL_ID, request=request, stage=None)
            assert isinstance(report, DiversityReport)
            assert report.total_patients == 1
        finally:
            api_module.get_diversity_analytics_service = original

    @pytest.mark.asyncio
    async def test_check_representation_endpoint(self, service: DiversityAnalyticsService) -> None:
        """The representation check endpoint should return a RepresentationCheck."""
        from app.api.diversity_analytics import check_representation

        service.record_demographic(TRIAL_ID, _record(patient_id="p1", race=Race.WHITE))
        service.set_targets(TRIAL_ID, [
            RepresentationTarget(group="race", category="White", target_pct=50.0),
        ])

        import app.api.diversity_analytics as api_module
        original = api_module.get_diversity_analytics_service
        api_module.get_diversity_analytics_service = lambda: service

        try:
            from unittest.mock import MagicMock
            request = MagicMock()

            check = await check_representation(TRIAL_ID, request=request)
            assert isinstance(check, RepresentationCheck)
            assert check.targets[0].actual_pct == 100.0
        finally:
            api_module.get_diversity_analytics_service = original

    @pytest.mark.asyncio
    async def test_set_targets_endpoint(self, service: DiversityAnalyticsService) -> None:
        """The set targets endpoint should persist targets and return check."""
        from app.api.diversity_analytics import set_diversity_targets
        from app.schemas.diversity import SetDiversityTargetsRequest

        import app.api.diversity_analytics as api_module
        original = api_module.get_diversity_analytics_service
        api_module.get_diversity_analytics_service = lambda: service

        try:
            from unittest.mock import MagicMock
            request = MagicMock()

            body = SetDiversityTargetsRequest(targets=[
                RepresentationTarget(group="race", category="White", target_pct=50.0),
            ])
            result = await set_diversity_targets(TRIAL_ID, request=request, body=body)
            assert isinstance(result, RepresentationCheck)
            assert len(result.targets) == 1
        finally:
            api_module.get_diversity_analytics_service = original
