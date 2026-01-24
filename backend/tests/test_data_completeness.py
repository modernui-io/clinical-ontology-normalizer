"""Tests for Data Completeness Reporting Service.

Tests verify:
- Completeness calculation with known data
- Per-field breakdown accuracy
- Trend tracking stores history
- API returns correct format
"""

import pytest

from app.services.data_completeness_service import (
    DataCompletenessService,
    reset_data_completeness_service,
)


@pytest.fixture(autouse=True)
def reset():
    reset_data_completeness_service()
    yield
    reset_data_completeness_service()


@pytest.fixture
def service():
    return DataCompletenessService()


def person_record(person_id=1, gender=1, year=1980, race=None, ethnicity=None,
                  month=None, day=None, source_value=None):
    return {
        "person_id": person_id,
        "gender_concept_id": gender,
        "year_of_birth": year,
        "race_concept_id": race,
        "ethnicity_concept_id": ethnicity,
        "month_of_birth": month,
        "day_of_birth": day,
        "birth_datetime": None,
        "person_source_value": source_value,
        "gender_source_value": None,
    }


class TestCompletenessCalculation:
    """Test completeness calculation with known data."""

    def test_empty_table_zero_completeness(self, service):
        service.set_table_data("person", [])
        report = service.get_completeness(table_name="person")
        assert report.overall_completeness_pct == 0.0

    def test_fully_complete_required_fields(self, service):
        records = [
            person_record(person_id=1, gender=1, year=1980, race=8527, ethnicity=38003564),
            person_record(person_id=2, gender=2, year=1990, race=8516, ethnicity=38003564),
        ]
        service.set_table_data("person", records)
        report = service.get_completeness(table_name="person")
        person_table = report.tables[0]
        assert person_table.required_completeness_pct == 100.0

    def test_partial_completeness(self, service):
        records = [
            person_record(person_id=1, gender=1, year=1980, race=8527, ethnicity=38003564),
            person_record(person_id=2, gender=2, year=1990, race=None, ethnicity=None),
        ]
        service.set_table_data("person", records)
        report = service.get_completeness(table_name="person")
        person_table = report.tables[0]
        # 3 required always filled + 2 partially filled = not 100%
        assert person_table.required_completeness_pct < 100.0
        assert person_table.required_completeness_pct > 0.0

    def test_overall_across_multiple_tables(self, service):
        service.set_table_data("person", [
            person_record(person_id=1, gender=1, year=1980, race=1, ethnicity=1),
        ])
        service.set_table_data("death", [
            {"person_id": 1, "death_date": "2024-01-01", "death_type_concept_id": 1,
             "cause_concept_id": None, "cause_source_value": None, "death_datetime": None},
        ])
        report = service.get_completeness()
        # Should have results for both tables
        table_names = [t.table_name for t in report.tables]
        assert "person" in table_names
        assert "death" in table_names
        assert report.overall_completeness_pct > 0

    def test_report_has_id_and_timestamp(self, service):
        service.set_table_data("person", [person_record()])
        report = service.get_completeness()
        assert report.id is not None
        assert report.timestamp > 0

    def test_all_tables_reported_when_no_filter(self, service):
        report = service.get_completeness()
        # Should report on all defined tables (even if empty)
        assert len(report.tables) == 8  # 8 OMOP tables defined


class TestFieldBreakdown:
    """Test per-field breakdown accuracy."""

    def test_required_field_identified(self, service):
        service.set_table_data("person", [person_record()])
        report = service.get_completeness(table_name="person")
        fields = report.tables[0].fields
        person_id_field = next(f for f in fields if f.field_name == "person_id")
        assert person_id_field.is_required is True

    def test_optional_field_identified(self, service):
        service.set_table_data("person", [person_record()])
        report = service.get_completeness(table_name="person")
        fields = report.tables[0].fields
        month_field = next(f for f in fields if f.field_name == "month_of_birth")
        assert month_field.is_required is False

    def test_null_count_correct(self, service):
        records = [
            person_record(person_id=1, race=1),
            person_record(person_id=2, race=None),
            person_record(person_id=3, race=None),
        ]
        service.set_table_data("person", records)
        report = service.get_completeness(table_name="person")
        fields = report.tables[0].fields
        race_field = next(f for f in fields if f.field_name == "race_concept_id")
        assert race_field.non_null_count == 1
        assert race_field.null_count == 2
        assert race_field.completeness_pct == pytest.approx(33.33, abs=0.01)

    def test_all_null_zero_percent(self, service):
        records = [
            person_record(month=None),
            person_record(month=None),
        ]
        service.set_table_data("person", records)
        report = service.get_completeness(table_name="person")
        fields = report.tables[0].fields
        month_field = next(f for f in fields if f.field_name == "month_of_birth")
        assert month_field.completeness_pct == 0.0

    def test_all_populated_hundred_percent(self, service):
        records = [
            person_record(person_id=1, gender=1, year=1980, race=1, ethnicity=1),
            person_record(person_id=2, gender=2, year=1990, race=2, ethnicity=2),
        ]
        service.set_table_data("person", records)
        report = service.get_completeness(table_name="person")
        fields = report.tables[0].fields
        pid_field = next(f for f in fields if f.field_name == "person_id")
        assert pid_field.completeness_pct == 100.0

    def test_empty_string_treated_as_null(self, service):
        records = [{"person_id": 1, "gender_concept_id": 1, "year_of_birth": 1980,
                    "race_concept_id": "", "ethnicity_concept_id": 1}]
        service.set_table_data("person", records)
        report = service.get_completeness(table_name="person")
        fields = report.tables[0].fields
        race_field = next(f for f in fields if f.field_name == "race_concept_id")
        assert race_field.non_null_count == 0


class TestTrendTracking:
    """Test trend tracking stores history."""

    def test_no_history_initially(self, service):
        trends = service.get_trends()
        assert trends == []

    def test_get_completeness_records_snapshot(self, service):
        service.set_table_data("person", [person_record()])
        service.get_completeness()
        trends = service.get_trends()
        assert len(trends) == 1

    def test_multiple_snapshots_stored(self, service):
        service.set_table_data("person", [person_record()])
        service.get_completeness()
        service.get_completeness()
        service.get_completeness()
        trends = service.get_trends()
        assert len(trends) == 3

    def test_snapshot_has_table_scores(self, service):
        service.set_table_data("person", [person_record(person_id=1, gender=1, year=1980, race=1, ethnicity=1)])
        service.get_completeness()
        trends = service.get_trends()
        assert "person" in trends[0].table_scores
        assert trends[0].table_scores["person"] > 0

    def test_trend_limit(self, service):
        service.set_table_data("person", [person_record()])
        for _ in range(10):
            service.get_completeness()
        trends = service.get_trends(limit=5)
        assert len(trends) == 5

    def test_trend_returns_most_recent(self, service):
        service.set_table_data("person", [person_record()])
        for _ in range(10):
            service.get_completeness()
        trends = service.get_trends(limit=3)
        # Last 3 should have increasing timestamps
        assert trends[0].timestamp <= trends[1].timestamp <= trends[2].timestamp


class TestSourceCompleteness:
    """Test per-source completeness breakdown."""

    def test_source_completeness_reported(self, service):
        service.set_source_data("hospital_a", "person", [
            person_record(person_id=1, gender=1, year=1980, race=1, ethnicity=1),
        ])
        report = service.get_completeness()
        assert len(report.sources) == 1
        assert report.sources[0].source_name == "hospital_a"

    def test_multiple_sources(self, service):
        service.set_source_data("hospital_a", "person", [person_record()])
        service.set_source_data("hospital_b", "person", [person_record()])
        report = service.get_completeness()
        source_names = [s.source_name for s in report.sources]
        assert "hospital_a" in source_names
        assert "hospital_b" in source_names

    def test_source_record_count(self, service):
        service.set_source_data("clinic", "person", [
            person_record(person_id=1),
            person_record(person_id=2),
            person_record(person_id=3),
        ])
        report = service.get_completeness()
        clinic_source = next(s for s in report.sources if s.source_name == "clinic")
        assert clinic_source.record_count == 3


class TestTableSpecificQuery:
    """Test querying completeness for a specific table."""

    def test_get_specific_table(self, service):
        service.set_table_data("person", [person_record()])
        result = service.get_table_completeness("person")
        assert result is not None
        assert result.table_name == "person"

    def test_unknown_table_returns_none(self, service):
        result = service.get_table_completeness("nonexistent_table")
        assert result is None

    def test_table_total_records(self, service):
        service.set_table_data("person", [person_record(), person_record(person_id=2)])
        result = service.get_table_completeness("person")
        assert result.total_records == 2


class TestAPIFormat:
    """Test API endpoint format using the service directly."""

    def test_report_serializable(self, service):
        service.set_table_data("person", [person_record()])
        report = service.get_completeness()
        # Verify all fields are serializable types
        assert isinstance(report.id, str)
        assert isinstance(report.timestamp, float)
        assert isinstance(report.overall_completeness_pct, float)
        assert isinstance(report.tables, list)
        assert isinstance(report.sources, list)

    def test_field_completeness_serializable(self, service):
        service.set_table_data("person", [person_record()])
        report = service.get_completeness(table_name="person")
        field = report.tables[0].fields[0]
        assert isinstance(field.field_name, str)
        assert isinstance(field.total_records, int)
        assert isinstance(field.non_null_count, int)
        assert isinstance(field.null_count, int)
        assert isinstance(field.completeness_pct, float)
        assert isinstance(field.is_required, bool)
