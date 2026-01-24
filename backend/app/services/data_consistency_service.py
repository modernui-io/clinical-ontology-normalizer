"""Data Consistency Validation Service.

Performs cross-table consistency checks on OMOP CDM data:
- Referential integrity (person exists, visit exists)
- Temporal plausibility (no future dates, logical ordering)
- Cross-table date alignment (events within visit dates)
- Orphan record detection
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class CheckType(str, Enum):
    REFERENTIAL_INTEGRITY = "referential_integrity"
    TEMPORAL_PLAUSIBILITY = "temporal_plausibility"
    CROSS_TABLE_CONSISTENCY = "cross_table_consistency"
    ORPHAN_RECORD = "orphan_record"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CheckStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"


@dataclass
class ConsistencyIssue:
    """A single consistency issue found."""

    issue_id: str
    check_type: CheckType
    severity: Severity
    table: str
    field: str | None
    record_id: str | None
    description: str
    current_value: str | None = None
    expected_value: str | None = None


@dataclass
class ConsistencyCheckResult:
    """Result of a single consistency check."""

    check_id: str
    check_name: str
    check_type: CheckType
    status: CheckStatus
    records_checked: int
    issues_found: int
    issues: list[ConsistencyIssue]


@dataclass
class ConsistencyReport:
    """Full consistency validation report."""

    id: str
    timestamp: float
    total_checks: int
    checks_passed: int
    checks_failed: int
    checks_warning: int
    total_issues: int
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    results: list[ConsistencyCheckResult]


class DataConsistencyService:
    """Service for validating data consistency across OMOP tables."""

    def __init__(self):
        self._lock = Lock()
        self._table_data: dict[str, list[dict[str, Any]]] = {}
        self._last_report: ConsistencyReport | None = None
        self._current_time: float | None = None  # Override for testing

    def set_table_data(self, table_name: str, records: list[dict[str, Any]]) -> None:
        """Load data for a table."""
        with self._lock:
            self._table_data[table_name] = records

    def set_current_time(self, timestamp: float) -> None:
        """Override current time for testing."""
        self._current_time = timestamp

    def get_results(self) -> ConsistencyReport | None:
        """Get the last consistency check results."""
        with self._lock:
            return self._last_report

    def run_checks(self) -> ConsistencyReport:
        """Run all consistency checks and return report."""
        with self._lock:
            results = []

            # Referential integrity checks
            results.append(self._check_person_references())
            results.append(self._check_visit_references())

            # Temporal plausibility checks
            results.append(self._check_future_dates())
            results.append(self._check_temporal_ordering())

            # Cross-table consistency
            results.append(self._check_event_within_visit())

            # Orphan records
            results.append(self._check_orphan_visits())

            # Build report
            total_issues = sum(r.issues_found for r in results)
            critical = sum(1 for r in results for i in r.issues if i.severity == Severity.CRITICAL)
            high = sum(1 for r in results for i in r.issues if i.severity == Severity.HIGH)
            medium = sum(1 for r in results for i in r.issues if i.severity == Severity.MEDIUM)
            low = sum(1 for r in results for i in r.issues if i.severity == Severity.LOW)

            report = ConsistencyReport(
                id=str(uuid.uuid4()),
                timestamp=time.time(),
                total_checks=len(results),
                checks_passed=sum(1 for r in results if r.status == CheckStatus.PASSED),
                checks_failed=sum(1 for r in results if r.status == CheckStatus.FAILED),
                checks_warning=sum(1 for r in results if r.status == CheckStatus.WARNING),
                total_issues=total_issues,
                critical_issues=critical,
                high_issues=high,
                medium_issues=medium,
                low_issues=low,
                results=results,
            )

            self._last_report = report
            return report

    def _check_person_references(self) -> ConsistencyCheckResult:
        """Check that all person_id references point to existing persons."""
        person_ids = {r.get("person_id") for r in self._table_data.get("person", [])}
        issues = []
        records_checked = 0

        for table_name in ["visit_occurrence", "condition_occurrence", "drug_exposure",
                           "procedure_occurrence", "measurement", "observation"]:
            records = self._table_data.get(table_name, [])
            records_checked += len(records)
            for r in records:
                pid = r.get("person_id")
                if pid is not None and pid not in person_ids:
                    issues.append(ConsistencyIssue(
                        issue_id=str(uuid.uuid4()),
                        check_type=CheckType.REFERENTIAL_INTEGRITY,
                        severity=Severity.CRITICAL,
                        table=table_name,
                        field="person_id",
                        record_id=str(r.get(f"{table_name}_id", r.get("person_id"))),
                        description=f"person_id {pid} not found in person table",
                        current_value=str(pid),
                    ))

        status = CheckStatus.PASSED if not issues else CheckStatus.FAILED
        return ConsistencyCheckResult(
            check_id="ref_person",
            check_name="Person reference integrity",
            check_type=CheckType.REFERENTIAL_INTEGRITY,
            status=status,
            records_checked=records_checked,
            issues_found=len(issues),
            issues=issues,
        )

    def _check_visit_references(self) -> ConsistencyCheckResult:
        """Check that visit_occurrence_id references point to existing visits."""
        visit_ids = {r.get("visit_occurrence_id") for r in self._table_data.get("visit_occurrence", [])}
        issues = []
        records_checked = 0

        for table_name in ["condition_occurrence", "drug_exposure",
                           "procedure_occurrence", "measurement", "observation"]:
            records = self._table_data.get(table_name, [])
            records_checked += len(records)
            for r in records:
                vid = r.get("visit_occurrence_id")
                if vid is not None and vid not in visit_ids:
                    issues.append(ConsistencyIssue(
                        issue_id=str(uuid.uuid4()),
                        check_type=CheckType.REFERENTIAL_INTEGRITY,
                        severity=Severity.HIGH,
                        table=table_name,
                        field="visit_occurrence_id",
                        record_id=str(r.get(f"{table_name}_id")),
                        description=f"visit_occurrence_id {vid} not found in visit_occurrence table",
                        current_value=str(vid),
                    ))

        status = CheckStatus.PASSED if not issues else CheckStatus.FAILED
        return ConsistencyCheckResult(
            check_id="ref_visit",
            check_name="Visit reference integrity",
            check_type=CheckType.REFERENTIAL_INTEGRITY,
            status=status,
            records_checked=records_checked,
            issues_found=len(issues),
            issues=issues,
        )

    def _check_future_dates(self) -> ConsistencyCheckResult:
        """Check for dates in the future."""
        now = self._current_time if self._current_time else time.time()
        # Convert to date string YYYY-MM-DD format for comparison
        from datetime import datetime
        now_str = datetime.fromtimestamp(now).strftime("%Y-%m-%d")

        issues = []
        records_checked = 0

        date_fields = {
            "visit_occurrence": ["visit_start_date", "visit_end_date"],
            "condition_occurrence": ["condition_start_date", "condition_end_date"],
            "drug_exposure": ["drug_exposure_start_date", "drug_exposure_end_date"],
            "procedure_occurrence": ["procedure_date", "procedure_end_date"],
            "measurement": ["measurement_date"],
            "observation": ["observation_date"],
            "death": ["death_date"],
        }

        for table_name, fields in date_fields.items():
            records = self._table_data.get(table_name, [])
            records_checked += len(records)
            for r in records:
                for field_name in fields:
                    date_val = r.get(field_name)
                    if date_val and isinstance(date_val, str) and date_val > now_str:
                        issues.append(ConsistencyIssue(
                            issue_id=str(uuid.uuid4()),
                            check_type=CheckType.TEMPORAL_PLAUSIBILITY,
                            severity=Severity.MEDIUM,
                            table=table_name,
                            field=field_name,
                            record_id=str(r.get(f"{table_name}_id", r.get("person_id"))),
                            description=f"Future date detected: {date_val}",
                            current_value=date_val,
                            expected_value=f"<= {now_str}",
                        ))

        status = CheckStatus.PASSED if not issues else CheckStatus.WARNING
        return ConsistencyCheckResult(
            check_id="temporal_future",
            check_name="No future dates",
            check_type=CheckType.TEMPORAL_PLAUSIBILITY,
            status=status,
            records_checked=records_checked,
            issues_found=len(issues),
            issues=issues,
        )

    def _check_temporal_ordering(self) -> ConsistencyCheckResult:
        """Check that start dates come before end dates."""
        issues = []
        records_checked = 0

        date_pairs = {
            "visit_occurrence": ("visit_start_date", "visit_end_date"),
            "condition_occurrence": ("condition_start_date", "condition_end_date"),
            "drug_exposure": ("drug_exposure_start_date", "drug_exposure_end_date"),
            "procedure_occurrence": ("procedure_date", "procedure_end_date"),
        }

        for table_name, (start_field, end_field) in date_pairs.items():
            records = self._table_data.get(table_name, [])
            records_checked += len(records)
            for r in records:
                start = r.get(start_field)
                end = r.get(end_field)
                if start and end and isinstance(start, str) and isinstance(end, str) and start > end:
                    issues.append(ConsistencyIssue(
                        issue_id=str(uuid.uuid4()),
                        check_type=CheckType.TEMPORAL_PLAUSIBILITY,
                        severity=Severity.HIGH,
                        table=table_name,
                        field=end_field,
                        record_id=str(r.get(f"{table_name}_id")),
                        description=f"End date {end} is before start date {start}",
                        current_value=f"start={start}, end={end}",
                        expected_value=f"end >= start",
                    ))

        status = CheckStatus.PASSED if not issues else CheckStatus.FAILED
        return ConsistencyCheckResult(
            check_id="temporal_order",
            check_name="Temporal ordering (start <= end)",
            check_type=CheckType.TEMPORAL_PLAUSIBILITY,
            status=status,
            records_checked=records_checked,
            issues_found=len(issues),
            issues=issues,
        )

    def _check_event_within_visit(self) -> ConsistencyCheckResult:
        """Check that clinical events fall within their visit's date range."""
        visits = {}
        for v in self._table_data.get("visit_occurrence", []):
            vid = v.get("visit_occurrence_id")
            if vid:
                visits[vid] = {
                    "start": v.get("visit_start_date"),
                    "end": v.get("visit_end_date"),
                }

        issues = []
        records_checked = 0

        event_tables = {
            "condition_occurrence": "condition_start_date",
            "drug_exposure": "drug_exposure_start_date",
            "procedure_occurrence": "procedure_date",
            "measurement": "measurement_date",
        }

        for table_name, date_field in event_tables.items():
            records = self._table_data.get(table_name, [])
            records_checked += len(records)
            for r in records:
                vid = r.get("visit_occurrence_id")
                if vid and vid in visits:
                    event_date = r.get(date_field)
                    visit = visits[vid]
                    if event_date and isinstance(event_date, str):
                        if visit["start"] and event_date < visit["start"]:
                            issues.append(ConsistencyIssue(
                                issue_id=str(uuid.uuid4()),
                                check_type=CheckType.CROSS_TABLE_CONSISTENCY,
                                severity=Severity.MEDIUM,
                                table=table_name,
                                field=date_field,
                                record_id=str(r.get(f"{table_name}_id")),
                                description=f"Event date {event_date} is before visit start {visit['start']}",
                                current_value=event_date,
                                expected_value=f">= {visit['start']}",
                            ))
                        elif visit["end"] and event_date > visit["end"]:
                            issues.append(ConsistencyIssue(
                                issue_id=str(uuid.uuid4()),
                                check_type=CheckType.CROSS_TABLE_CONSISTENCY,
                                severity=Severity.LOW,
                                table=table_name,
                                field=date_field,
                                record_id=str(r.get(f"{table_name}_id")),
                                description=f"Event date {event_date} is after visit end {visit['end']}",
                                current_value=event_date,
                                expected_value=f"<= {visit['end']}",
                            ))

        status = CheckStatus.PASSED if not issues else CheckStatus.WARNING
        return ConsistencyCheckResult(
            check_id="cross_event_visit",
            check_name="Events within visit dates",
            check_type=CheckType.CROSS_TABLE_CONSISTENCY,
            status=status,
            records_checked=records_checked,
            issues_found=len(issues),
            issues=issues,
        )

    def _check_orphan_visits(self) -> ConsistencyCheckResult:
        """Check for visits with no associated clinical events."""
        visit_ids = {r.get("visit_occurrence_id") for r in self._table_data.get("visit_occurrence", [])}
        referenced_visits = set()

        for table_name in ["condition_occurrence", "drug_exposure",
                           "procedure_occurrence", "measurement", "observation"]:
            for r in self._table_data.get(table_name, []):
                vid = r.get("visit_occurrence_id")
                if vid:
                    referenced_visits.add(vid)

        orphan_visits = visit_ids - referenced_visits
        issues = []
        for vid in orphan_visits:
            if vid is not None:
                issues.append(ConsistencyIssue(
                    issue_id=str(uuid.uuid4()),
                    check_type=CheckType.ORPHAN_RECORD,
                    severity=Severity.LOW,
                    table="visit_occurrence",
                    field=None,
                    record_id=str(vid),
                    description=f"Visit {vid} has no associated clinical events",
                ))

        records_checked = len(visit_ids)
        status = CheckStatus.PASSED if not issues else CheckStatus.WARNING
        return ConsistencyCheckResult(
            check_id="orphan_visits",
            check_name="Orphan visit detection",
            check_type=CheckType.ORPHAN_RECORD,
            status=status,
            records_checked=records_checked,
            issues_found=len(issues),
            issues=issues,
        )


# Singleton
_data_consistency_service: DataConsistencyService | None = None


def get_data_consistency_service() -> DataConsistencyService:
    global _data_consistency_service
    if _data_consistency_service is None:
        _data_consistency_service = DataConsistencyService()
    return _data_consistency_service


def reset_data_consistency_service() -> None:
    global _data_consistency_service
    _data_consistency_service = None
