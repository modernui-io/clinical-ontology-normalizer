"""Tests for Data Consistency Validation Service.

Tests verify:
- Cross-table reference validation
- Temporal ordering checks
- Future date detection
- Orphan record detection
- API trigger and results format
"""

import time

import pytest

from app.services.data_consistency_service import (
    CheckStatus,
    CheckType,
    DataConsistencyService,
    Severity,
    reset_data_consistency_service,
)


@pytest.fixture(autouse=True)
def reset():
    reset_data_consistency_service()
    yield
    reset_data_consistency_service()


@pytest.fixture
def service():
    svc = DataConsistencyService()
    # Set a fixed "current time" for future date checks
    svc.set_current_time(time.mktime(time.strptime("2025-06-15", "%Y-%m-%d")))
    return svc


class TestReferentialIntegrity:
    """Test cross-table reference validation."""

    def test_valid_person_references_pass(self, service):
        service.set_table_data("person", [{"person_id": 1}, {"person_id": 2}])
        service.set_table_data("visit_occurrence", [
            {"visit_occurrence_id": 10, "person_id": 1, "visit_start_date": "2024-01-01"},
            {"visit_occurrence_id": 11, "person_id": 2, "visit_start_date": "2024-02-01"},
        ])
        report = service.run_checks()
        person_check = next(r for r in report.results if r.check_id == "ref_person")
        assert person_check.status == CheckStatus.PASSED
        assert person_check.issues_found == 0

    def test_invalid_person_reference_detected(self, service):
        service.set_table_data("person", [{"person_id": 1}])
        service.set_table_data("condition_occurrence", [
            {"condition_occurrence_id": 100, "person_id": 999, "condition_start_date": "2024-01-01"},
        ])
        report = service.run_checks()
        person_check = next(r for r in report.results if r.check_id == "ref_person")
        assert person_check.status == CheckStatus.FAILED
        assert person_check.issues_found == 1
        assert person_check.issues[0].severity == Severity.CRITICAL

    def test_invalid_visit_reference_detected(self, service):
        service.set_table_data("person", [{"person_id": 1}])
        service.set_table_data("visit_occurrence", [
            {"visit_occurrence_id": 10, "person_id": 1, "visit_start_date": "2024-01-01"},
        ])
        service.set_table_data("measurement", [
            {"measurement_id": 200, "person_id": 1, "visit_occurrence_id": 999,
             "measurement_date": "2024-01-01"},
        ])
        report = service.run_checks()
        visit_check = next(r for r in report.results if r.check_id == "ref_visit")
        assert visit_check.status == CheckStatus.FAILED
        assert visit_check.issues[0].severity == Severity.HIGH

    def test_null_visit_reference_not_flagged(self, service):
        service.set_table_data("person", [{"person_id": 1}])
        service.set_table_data("visit_occurrence", [])
        service.set_table_data("drug_exposure", [
            {"drug_exposure_id": 300, "person_id": 1, "visit_occurrence_id": None,
             "drug_exposure_start_date": "2024-01-01"},
        ])
        report = service.run_checks()
        visit_check = next(r for r in report.results if r.check_id == "ref_visit")
        assert visit_check.issues_found == 0

    def test_multiple_tables_checked(self, service):
        service.set_table_data("person", [{"person_id": 1}])
        service.set_table_data("drug_exposure", [
            {"drug_exposure_id": 1, "person_id": 999, "drug_exposure_start_date": "2024-01-01"},
        ])
        service.set_table_data("procedure_occurrence", [
            {"procedure_occurrence_id": 1, "person_id": 888, "procedure_date": "2024-01-01"},
        ])
        report = service.run_checks()
        person_check = next(r for r in report.results if r.check_id == "ref_person")
        assert person_check.issues_found == 2


class TestTemporalOrdering:
    """Test temporal ordering checks."""

    def test_valid_ordering_passes(self, service):
        service.set_table_data("visit_occurrence", [
            {"visit_occurrence_id": 1, "person_id": 1,
             "visit_start_date": "2024-01-01", "visit_end_date": "2024-01-05"},
        ])
        report = service.run_checks()
        order_check = next(r for r in report.results if r.check_id == "temporal_order")
        assert order_check.status == CheckStatus.PASSED

    def test_end_before_start_detected(self, service):
        service.set_table_data("visit_occurrence", [
            {"visit_occurrence_id": 1, "person_id": 1,
             "visit_start_date": "2024-01-10", "visit_end_date": "2024-01-05"},
        ])
        report = service.run_checks()
        order_check = next(r for r in report.results if r.check_id == "temporal_order")
        assert order_check.status == CheckStatus.FAILED
        assert order_check.issues_found == 1
        assert order_check.issues[0].severity == Severity.HIGH

    def test_same_start_and_end_passes(self, service):
        service.set_table_data("condition_occurrence", [
            {"condition_occurrence_id": 1, "person_id": 1,
             "condition_start_date": "2024-03-15", "condition_end_date": "2024-03-15"},
        ])
        report = service.run_checks()
        order_check = next(r for r in report.results if r.check_id == "temporal_order")
        assert order_check.status == CheckStatus.PASSED

    def test_null_end_date_not_flagged(self, service):
        service.set_table_data("drug_exposure", [
            {"drug_exposure_id": 1, "person_id": 1,
             "drug_exposure_start_date": "2024-01-01", "drug_exposure_end_date": None},
        ])
        report = service.run_checks()
        order_check = next(r for r in report.results if r.check_id == "temporal_order")
        assert order_check.issues_found == 0


class TestFutureDateDetection:
    """Test future date detection."""

    def test_past_date_passes(self, service):
        service.set_table_data("measurement", [
            {"measurement_id": 1, "person_id": 1, "measurement_date": "2024-01-01"},
        ])
        report = service.run_checks()
        future_check = next(r for r in report.results if r.check_id == "temporal_future")
        assert future_check.status == CheckStatus.PASSED

    def test_future_date_detected(self, service):
        service.set_table_data("observation", [
            {"observation_id": 1, "person_id": 1, "observation_date": "2030-01-01"},
        ])
        report = service.run_checks()
        future_check = next(r for r in report.results if r.check_id == "temporal_future")
        assert future_check.status == CheckStatus.WARNING
        assert future_check.issues_found == 1
        assert future_check.issues[0].severity == Severity.MEDIUM

    def test_future_visit_date_detected(self, service):
        service.set_table_data("visit_occurrence", [
            {"visit_occurrence_id": 1, "person_id": 1,
             "visit_start_date": "2030-06-01", "visit_end_date": None},
        ])
        report = service.run_checks()
        future_check = next(r for r in report.results if r.check_id == "temporal_future")
        assert future_check.issues_found == 1

    def test_null_date_not_flagged(self, service):
        service.set_table_data("death", [
            {"person_id": 1, "death_date": None, "death_type_concept_id": 1},
        ])
        report = service.run_checks()
        future_check = next(r for r in report.results if r.check_id == "temporal_future")
        issues_for_death = [i for i in future_check.issues if i.table == "death"]
        assert len(issues_for_death) == 0


class TestOrphanRecordDetection:
    """Test orphan record detection."""

    def test_visit_with_events_not_orphan(self, service):
        service.set_table_data("visit_occurrence", [
            {"visit_occurrence_id": 1, "person_id": 1, "visit_start_date": "2024-01-01"},
        ])
        service.set_table_data("condition_occurrence", [
            {"condition_occurrence_id": 100, "person_id": 1,
             "visit_occurrence_id": 1, "condition_start_date": "2024-01-01"},
        ])
        report = service.run_checks()
        orphan_check = next(r for r in report.results if r.check_id == "orphan_visits")
        assert orphan_check.issues_found == 0

    def test_visit_without_events_is_orphan(self, service):
        service.set_table_data("visit_occurrence", [
            {"visit_occurrence_id": 1, "person_id": 1, "visit_start_date": "2024-01-01"},
        ])
        # No clinical events reference this visit
        report = service.run_checks()
        orphan_check = next(r for r in report.results if r.check_id == "orphan_visits")
        assert orphan_check.issues_found == 1
        assert orphan_check.issues[0].severity == Severity.LOW

    def test_multiple_orphan_visits(self, service):
        service.set_table_data("visit_occurrence", [
            {"visit_occurrence_id": 1, "person_id": 1, "visit_start_date": "2024-01-01"},
            {"visit_occurrence_id": 2, "person_id": 1, "visit_start_date": "2024-02-01"},
            {"visit_occurrence_id": 3, "person_id": 1, "visit_start_date": "2024-03-01"},
        ])
        service.set_table_data("measurement", [
            {"measurement_id": 1, "person_id": 1, "visit_occurrence_id": 1,
             "measurement_date": "2024-01-01"},
        ])
        report = service.run_checks()
        orphan_check = next(r for r in report.results if r.check_id == "orphan_visits")
        # Visits 2 and 3 are orphans
        assert orphan_check.issues_found == 2


class TestCrossTableConsistency:
    """Test event-within-visit date consistency."""

    def test_event_within_visit_passes(self, service):
        service.set_table_data("person", [{"person_id": 1}])
        service.set_table_data("visit_occurrence", [
            {"visit_occurrence_id": 1, "person_id": 1,
             "visit_start_date": "2024-01-01", "visit_end_date": "2024-01-10"},
        ])
        service.set_table_data("condition_occurrence", [
            {"condition_occurrence_id": 1, "person_id": 1,
             "visit_occurrence_id": 1, "condition_start_date": "2024-01-05"},
        ])
        report = service.run_checks()
        cross_check = next(r for r in report.results if r.check_id == "cross_event_visit")
        assert cross_check.issues_found == 0

    def test_event_before_visit_start_flagged(self, service):
        service.set_table_data("person", [{"person_id": 1}])
        service.set_table_data("visit_occurrence", [
            {"visit_occurrence_id": 1, "person_id": 1,
             "visit_start_date": "2024-01-05", "visit_end_date": "2024-01-10"},
        ])
        service.set_table_data("procedure_occurrence", [
            {"procedure_occurrence_id": 1, "person_id": 1,
             "visit_occurrence_id": 1, "procedure_date": "2024-01-01"},
        ])
        report = service.run_checks()
        cross_check = next(r for r in report.results if r.check_id == "cross_event_visit")
        assert cross_check.issues_found == 1
        assert cross_check.issues[0].severity == Severity.MEDIUM

    def test_event_after_visit_end_flagged(self, service):
        service.set_table_data("person", [{"person_id": 1}])
        service.set_table_data("visit_occurrence", [
            {"visit_occurrence_id": 1, "person_id": 1,
             "visit_start_date": "2024-01-01", "visit_end_date": "2024-01-05"},
        ])
        service.set_table_data("measurement", [
            {"measurement_id": 1, "person_id": 1,
             "visit_occurrence_id": 1, "measurement_date": "2024-01-20"},
        ])
        report = service.run_checks()
        cross_check = next(r for r in report.results if r.check_id == "cross_event_visit")
        assert cross_check.issues_found == 1
        assert cross_check.issues[0].severity == Severity.LOW


class TestReportFormat:
    """Test API trigger and results format."""

    def test_report_has_id_and_timestamp(self, service):
        report = service.run_checks()
        assert report.id is not None
        assert report.timestamp > 0

    def test_report_counts_correct(self, service):
        service.set_table_data("person", [{"person_id": 1}])
        service.set_table_data("visit_occurrence", [
            {"visit_occurrence_id": 1, "person_id": 1,
             "visit_start_date": "2024-01-01", "visit_end_date": "2024-01-05"},
        ])
        service.set_table_data("condition_occurrence", [
            {"condition_occurrence_id": 1, "person_id": 1,
             "visit_occurrence_id": 1, "condition_start_date": "2024-01-03"},
        ])
        report = service.run_checks()
        assert report.total_checks == 6
        assert report.checks_passed + report.checks_failed + report.checks_warning == 6

    def test_get_results_returns_none_before_run(self, service):
        assert service.get_results() is None

    def test_get_results_returns_last_report(self, service):
        report = service.run_checks()
        assert service.get_results() is not None
        assert service.get_results().id == report.id

    def test_issue_severity_counts(self, service):
        service.set_table_data("person", [])
        service.set_table_data("visit_occurrence", [
            {"visit_occurrence_id": 1, "person_id": 999,
             "visit_start_date": "2024-01-10", "visit_end_date": "2024-01-05"},
        ])
        report = service.run_checks()
        # person_id 999 not in person table = CRITICAL
        # end before start = HIGH
        assert report.critical_issues >= 1
        assert report.high_issues >= 1

    def test_all_check_types_present(self, service):
        report = service.run_checks()
        check_types = {r.check_type for r in report.results}
        assert CheckType.REFERENTIAL_INTEGRITY in check_types
        assert CheckType.TEMPORAL_PLAUSIBILITY in check_types
        assert CheckType.CROSS_TABLE_CONSISTENCY in check_types
        assert CheckType.ORPHAN_RECORD in check_types
