"""Data Completeness Reporting Service.

Calculates completeness metrics for OMOP CDM tables:
- Per-field completeness percentages
- Per-table completeness scores
- Per-source completeness breakdown
- Historical trend tracking
- Completeness scorecards
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class OMOPTable(str, Enum):
    PERSON = "person"
    VISIT_OCCURRENCE = "visit_occurrence"
    CONDITION_OCCURRENCE = "condition_occurrence"
    DRUG_EXPOSURE = "drug_exposure"
    PROCEDURE_OCCURRENCE = "procedure_occurrence"
    MEASUREMENT = "measurement"
    OBSERVATION = "observation"
    DEATH = "death"


# Required and optional fields per OMOP table
TABLE_FIELDS: dict[str, dict[str, list[str]]] = {
    "person": {
        "required": ["person_id", "gender_concept_id", "year_of_birth", "race_concept_id", "ethnicity_concept_id"],
        "optional": ["month_of_birth", "day_of_birth", "birth_datetime", "person_source_value", "gender_source_value"],
    },
    "visit_occurrence": {
        "required": ["visit_occurrence_id", "person_id", "visit_concept_id", "visit_start_date", "visit_type_concept_id"],
        "optional": ["visit_end_date", "visit_source_value", "admitted_from_concept_id", "discharged_to_concept_id", "preceding_visit_occurrence_id"],
    },
    "condition_occurrence": {
        "required": ["condition_occurrence_id", "person_id", "condition_concept_id", "condition_start_date", "condition_type_concept_id"],
        "optional": ["condition_end_date", "condition_status_concept_id", "condition_source_value", "condition_source_concept_id", "stop_reason"],
    },
    "drug_exposure": {
        "required": ["drug_exposure_id", "person_id", "drug_concept_id", "drug_exposure_start_date", "drug_type_concept_id"],
        "optional": ["drug_exposure_end_date", "quantity", "days_supply", "sig", "route_concept_id", "dose_unit_source_value"],
    },
    "procedure_occurrence": {
        "required": ["procedure_occurrence_id", "person_id", "procedure_concept_id", "procedure_date", "procedure_type_concept_id"],
        "optional": ["procedure_end_date", "modifier_concept_id", "quantity", "procedure_source_value", "procedure_source_concept_id"],
    },
    "measurement": {
        "required": ["measurement_id", "person_id", "measurement_concept_id", "measurement_date", "measurement_type_concept_id"],
        "optional": ["value_as_number", "value_as_concept_id", "unit_concept_id", "range_low", "range_high", "measurement_source_value"],
    },
    "observation": {
        "required": ["observation_id", "person_id", "observation_concept_id", "observation_date", "observation_type_concept_id"],
        "optional": ["value_as_number", "value_as_string", "value_as_concept_id", "unit_concept_id", "observation_source_value"],
    },
    "death": {
        "required": ["person_id", "death_date", "death_type_concept_id"],
        "optional": ["cause_concept_id", "cause_source_value", "death_datetime"],
    },
}


@dataclass
class FieldCompleteness:
    """Completeness data for a single field."""

    field_name: str
    total_records: int
    non_null_count: int
    null_count: int
    completeness_pct: float
    is_required: bool


@dataclass
class TableCompleteness:
    """Completeness scorecard for a table."""

    table_name: str
    total_records: int
    required_completeness_pct: float
    optional_completeness_pct: float
    overall_completeness_pct: float
    fields: list[FieldCompleteness]


@dataclass
class SourceCompleteness:
    """Completeness breakdown by source."""

    source_name: str
    record_count: int
    completeness_pct: float
    tables: dict[str, float]  # table -> completeness_pct


@dataclass
class CompletenessSnapshot:
    """A point-in-time completeness measurement."""

    id: str
    timestamp: float
    overall_completeness_pct: float
    table_scores: dict[str, float]  # table -> completeness_pct


@dataclass
class CompletenessReport:
    """Full completeness report."""

    id: str
    timestamp: float
    overall_completeness_pct: float
    tables: list[TableCompleteness]
    sources: list[SourceCompleteness]


class DataCompletenessService:
    """Service for calculating and tracking data completeness metrics."""

    def __init__(self):
        self._lock = Lock()
        self._history: list[CompletenessSnapshot] = []
        self._table_data: dict[str, list[dict[str, Any]]] = {}
        self._source_data: dict[str, dict[str, list[dict[str, Any]]]] = {}

    def set_table_data(self, table_name: str, records: list[dict[str, Any]]) -> None:
        """Load data for a table (used for testing and data ingestion)."""
        with self._lock:
            self._table_data[table_name] = records

    def set_source_data(self, source_name: str, table_name: str, records: list[dict[str, Any]]) -> None:
        """Load data for a source/table combination."""
        with self._lock:
            if source_name not in self._source_data:
                self._source_data[source_name] = {}
            self._source_data[source_name][table_name] = records

    def get_completeness(self, table_name: str | None = None) -> CompletenessReport:
        """Calculate completeness report.

        Args:
            table_name: Optional specific table to report on. If None, reports all tables.

        Returns:
            CompletenessReport with field-level completeness data.
        """
        with self._lock:
            tables_to_check = [table_name] if table_name else list(TABLE_FIELDS.keys())
            table_results = []

            for tbl in tables_to_check:
                if tbl not in TABLE_FIELDS:
                    continue
                tc = self._calculate_table_completeness(tbl)
                table_results.append(tc)

            # Calculate sources
            source_results = self._calculate_source_completeness()

            # Overall completeness
            if table_results:
                overall = sum(t.overall_completeness_pct for t in table_results) / len(table_results)
            else:
                overall = 0.0

            report = CompletenessReport(
                id=str(uuid.uuid4()),
                timestamp=time.time(),
                overall_completeness_pct=round(overall, 2),
                tables=table_results,
                sources=source_results,
            )

            # Record snapshot for trend tracking
            snapshot = CompletenessSnapshot(
                id=report.id,
                timestamp=report.timestamp,
                overall_completeness_pct=report.overall_completeness_pct,
                table_scores={t.table_name: t.overall_completeness_pct for t in table_results},
            )
            self._history.append(snapshot)

            return report

    def get_table_completeness(self, table_name: str) -> TableCompleteness | None:
        """Get completeness for a specific table."""
        if table_name not in TABLE_FIELDS:
            return None
        with self._lock:
            return self._calculate_table_completeness(table_name)

    def get_trends(self, limit: int = 30) -> list[CompletenessSnapshot]:
        """Get historical completeness snapshots."""
        with self._lock:
            return list(self._history[-limit:])

    def _calculate_table_completeness(self, table_name: str) -> TableCompleteness:
        """Calculate field-level completeness for a table."""
        records = self._table_data.get(table_name, [])
        schema = TABLE_FIELDS.get(table_name, {"required": [], "optional": []})
        total = len(records)

        fields = []
        required_scores = []
        optional_scores = []

        all_fields = [(f, True) for f in schema["required"]] + [(f, False) for f in schema["optional"]]

        for field_name, is_required in all_fields:
            if total == 0:
                pct = 0.0
                non_null = 0
            else:
                non_null = sum(
                    1 for r in records
                    if r.get(field_name) is not None and r.get(field_name) != ""
                )
                pct = round((non_null / total) * 100, 2)

            fc = FieldCompleteness(
                field_name=field_name,
                total_records=total,
                non_null_count=non_null,
                null_count=total - non_null,
                completeness_pct=pct,
                is_required=is_required,
            )
            fields.append(fc)

            if is_required:
                required_scores.append(pct)
            else:
                optional_scores.append(pct)

        req_avg = sum(required_scores) / len(required_scores) if required_scores else 0.0
        opt_avg = sum(optional_scores) / len(optional_scores) if optional_scores else 0.0
        all_scores = required_scores + optional_scores
        overall = sum(all_scores) / len(all_scores) if all_scores else 0.0

        return TableCompleteness(
            table_name=table_name,
            total_records=total,
            required_completeness_pct=round(req_avg, 2),
            optional_completeness_pct=round(opt_avg, 2),
            overall_completeness_pct=round(overall, 2),
            fields=fields,
        )

    def _calculate_source_completeness(self) -> list[SourceCompleteness]:
        """Calculate completeness breakdown by source."""
        results = []
        for source_name, tables in self._source_data.items():
            table_scores = {}
            total_records = 0
            for tbl_name, records in tables.items():
                total_records += len(records)
                if tbl_name in TABLE_FIELDS:
                    schema = TABLE_FIELDS[tbl_name]
                    all_fields = schema["required"] + schema["optional"]
                    if records and all_fields:
                        field_scores = []
                        for f in all_fields:
                            non_null = sum(
                                1 for r in records
                                if r.get(f) is not None and r.get(f) != ""
                            )
                            field_scores.append((non_null / len(records)) * 100)
                        table_scores[tbl_name] = round(sum(field_scores) / len(field_scores), 2)
                    else:
                        table_scores[tbl_name] = 0.0

            overall = sum(table_scores.values()) / len(table_scores) if table_scores else 0.0
            results.append(SourceCompleteness(
                source_name=source_name,
                record_count=total_records,
                completeness_pct=round(overall, 2),
                tables=table_scores,
            ))
        return results


# Singleton
_data_completeness_service: DataCompletenessService | None = None


def get_data_completeness_service() -> DataCompletenessService:
    global _data_completeness_service
    if _data_completeness_service is None:
        _data_completeness_service = DataCompletenessService()
    return _data_completeness_service


def reset_data_completeness_service() -> None:
    global _data_completeness_service
    _data_completeness_service = None
