"""OHDSI-style Data Quality Dashboard Service.

Implements Data Quality Dashboard (DQD) checks following OHDSI specifications:
https://ohdsi.github.io/DataQualityDashboard/

Check Categories:
1. Completeness - Required fields populated
2. Conformance - Values within expected ranges and valid concepts
3. Plausibility - Temporal consistency and reasonable values

Supports OMOP CDM tables:
- PERSON
- VISIT_OCCURRENCE
- CONDITION_OCCURRENCE
- DRUG_EXPOSURE
- PROCEDURE_OCCURRENCE
- MEASUREMENT
- OBSERVATION
- NOTE
- NOTE_NLP
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone, timedelta
from enum import Enum
from functools import lru_cache
from typing import Any
import hashlib
import logging
import threading
import time

logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Constants
# ============================================================================


class DQDCategory(str, Enum):
    """Data quality check categories following OHDSI DQD."""

    COMPLETENESS = "completeness"
    CONFORMANCE = "conformance"
    PLAUSIBILITY = "plausibility"


class DQDSubcategory(str, Enum):
    """Data quality check subcategories."""

    # Completeness subcategories
    COMPLETENESS_REQUIRED = "required_fields"
    COMPLETENESS_OPTIONAL = "optional_fields"

    # Conformance subcategories
    CONFORMANCE_VALUE = "value_conformance"
    CONFORMANCE_RELATIONAL = "relational_conformance"
    CONFORMANCE_COMPUTATIONAL = "computational_conformance"

    # Plausibility subcategories
    PLAUSIBILITY_TEMPORAL = "temporal_plausibility"
    PLAUSIBILITY_ATEMPORAL = "atemporal_plausibility"
    PLAUSIBILITY_UNIQUENESS = "uniqueness_plausibility"


class DQDSeverity(str, Enum):
    """Severity levels for data quality issues."""

    CRITICAL = "critical"  # Data integrity compromised
    HIGH = "high"  # Significant quality issues
    MEDIUM = "medium"  # Notable quality concerns
    LOW = "low"  # Minor quality observations


class DQDStatus(str, Enum):
    """Status of a quality check."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    ERROR = "error"  # Check execution failed
    NOT_APPLICABLE = "not_applicable"


class OMOPTable(str, Enum):
    """OMOP CDM tables for quality checks."""

    PERSON = "person"
    VISIT_OCCURRENCE = "visit_occurrence"
    CONDITION_OCCURRENCE = "condition_occurrence"
    DRUG_EXPOSURE = "drug_exposure"
    PROCEDURE_OCCURRENCE = "procedure_occurrence"
    MEASUREMENT = "measurement"
    OBSERVATION = "observation"
    NOTE = "note"
    NOTE_NLP = "note_nlp"
    DEATH = "death"
    PROVIDER = "provider"
    CARE_SITE = "care_site"


# OMOP CDM required fields per table
OMOP_REQUIRED_FIELDS: dict[OMOPTable, list[str]] = {
    OMOPTable.PERSON: [
        "person_id",
        "gender_concept_id",
        "year_of_birth",
        "race_concept_id",
        "ethnicity_concept_id",
    ],
    OMOPTable.VISIT_OCCURRENCE: [
        "visit_occurrence_id",
        "person_id",
        "visit_concept_id",
        "visit_start_date",
        "visit_type_concept_id",
    ],
    OMOPTable.CONDITION_OCCURRENCE: [
        "condition_occurrence_id",
        "person_id",
        "condition_concept_id",
        "condition_start_date",
        "condition_type_concept_id",
    ],
    OMOPTable.DRUG_EXPOSURE: [
        "drug_exposure_id",
        "person_id",
        "drug_concept_id",
        "drug_exposure_start_date",
        "drug_type_concept_id",
    ],
    OMOPTable.PROCEDURE_OCCURRENCE: [
        "procedure_occurrence_id",
        "person_id",
        "procedure_concept_id",
        "procedure_date",
        "procedure_type_concept_id",
    ],
    OMOPTable.MEASUREMENT: [
        "measurement_id",
        "person_id",
        "measurement_concept_id",
        "measurement_date",
        "measurement_type_concept_id",
    ],
    OMOPTable.OBSERVATION: [
        "observation_id",
        "person_id",
        "observation_concept_id",
        "observation_date",
        "observation_type_concept_id",
    ],
    OMOPTable.NOTE: [
        "note_id",
        "person_id",
        "note_date",
        "note_type_concept_id",
        "note_text",
    ],
    OMOPTable.NOTE_NLP: [
        "note_nlp_id",
        "note_id",
        "nlp_date",
    ],
}

# Valid concept ranges (0 is always valid for unknown)
VALID_GENDER_CONCEPTS = {0, 8507, 8532}  # Unknown, Male, Female
VALID_RACE_CONCEPTS = {0, 8515, 8516, 8522, 8527, 8557}  # Major race categories
VALID_ETHNICITY_CONCEPTS = {0, 38003563, 38003564}  # Unknown, Hispanic, Not Hispanic


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class DQDCheckDefinition:
    """Definition of a data quality check."""

    check_id: str
    check_name: str
    description: str
    category: DQDCategory
    subcategory: DQDSubcategory
    table: OMOPTable
    field: str | None = None
    threshold_value: float = 0.0  # Pass if metric >= threshold
    severity: DQDSeverity = DQDSeverity.MEDIUM
    is_active: bool = True


@dataclass
class DQDCheckResult:
    """Result of executing a data quality check."""

    check_id: str
    check_name: str
    category: DQDCategory
    subcategory: DQDSubcategory
    table: OMOPTable
    field: str | None

    status: DQDStatus
    severity: DQDSeverity
    score: float  # 0-100 scale

    # Statistics
    records_total: int = 0
    records_passed: int = 0
    records_failed: int = 0
    percent_passed: float = 0.0

    # Threshold
    threshold_value: float = 0.0

    # Details
    message: str = ""
    failed_examples: list[dict[str, Any]] = field(default_factory=list)

    # Timing
    execution_time_ms: float = 0.0
    executed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class DQDIssue:
    """A specific data quality issue found."""

    issue_id: str
    check_id: str
    table: OMOPTable
    field: str | None
    record_id: str | None
    severity: DQDSeverity
    category: DQDCategory

    description: str
    current_value: Any = None
    expected_value: Any = None
    recommendation: str = ""

    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved: bool = False
    resolved_at: str | None = None


@dataclass
class DQDCategorySummary:
    """Summary of quality scores for a category."""

    category: DQDCategory
    score: float  # 0-100 aggregate score
    checks_total: int
    checks_passed: int
    checks_failed: int
    checks_warning: int
    critical_issues: int
    high_issues: int

    # Trend
    previous_score: float | None = None
    score_change: float | None = None


@dataclass
class DQDTableSummary:
    """Summary of quality scores for a table."""

    table: OMOPTable
    record_count: int
    score: float  # 0-100 aggregate score
    completeness_score: float
    conformance_score: float
    plausibility_score: float
    issues_count: int
    critical_issues: int


@dataclass
class DQDSummary:
    """Overall data quality summary."""

    overall_score: float  # 0-100 aggregate score
    executed_at: str
    execution_time_ms: float

    # By category
    completeness_score: float
    conformance_score: float
    plausibility_score: float

    # Counts
    total_checks: int
    checks_passed: int
    checks_failed: int
    checks_warning: int
    checks_error: int

    # Issues
    total_issues: int
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int

    # By category detail
    category_summaries: list[DQDCategorySummary] = field(default_factory=list)

    # By table detail
    table_summaries: list[DQDTableSummary] = field(default_factory=list)


@dataclass
class DQDRunResult:
    """Complete result of a DQD run."""

    run_id: str
    summary: DQDSummary
    check_results: list[DQDCheckResult]
    issues: list[DQDIssue]

    # Run metadata
    started_at: str
    completed_at: str
    duration_ms: float


@dataclass
class DQDHistoryEntry:
    """Historical quality score entry."""

    run_id: str
    timestamp: str
    overall_score: float
    completeness_score: float
    conformance_score: float
    plausibility_score: float
    total_checks: int
    checks_passed: int
    total_issues: int


# ============================================================================
# Mock Data Generator (for demo purposes)
# ============================================================================


class MockOMOPData:
    """Mock OMOP data for quality checks (for demonstration)."""

    def __init__(self):
        """Initialize mock data."""
        self._generate_mock_data()

    def _generate_mock_data(self):
        """Generate realistic mock OMOP data."""
        import random

        random.seed(42)  # Reproducible

        # Person records
        self.persons = []
        for i in range(1, 5001):
            # Introduce some quality issues
            has_gender = random.random() > 0.02  # 2% missing
            has_race = random.random() > 0.05  # 5% missing
            has_valid_birthyear = random.random() > 0.01  # 1% invalid

            self.persons.append({
                "person_id": i,
                "gender_concept_id": random.choice([8507, 8532]) if has_gender else None,
                "year_of_birth": random.randint(1920, 2020) if has_valid_birthyear else 1800,
                "month_of_birth": random.randint(1, 12) if random.random() > 0.3 else None,
                "day_of_birth": random.randint(1, 28) if random.random() > 0.4 else None,
                "race_concept_id": random.choice([8515, 8516, 8522, 8527, 8557]) if has_race else 0,
                "ethnicity_concept_id": random.choice([38003563, 38003564, 0]),
            })

        # Visit records
        self.visits = []
        visit_id = 1
        for person in self.persons[:3000]:  # 3000 patients with visits
            num_visits = random.randint(1, 10)
            for _ in range(num_visits):
                start_date = date(
                    random.randint(2020, 2024),
                    random.randint(1, 12),
                    random.randint(1, 28)
                )
                # Some visits have end before start (plausibility issue)
                has_valid_dates = random.random() > 0.01
                end_date = start_date + timedelta(days=random.randint(0, 14)) if has_valid_dates else start_date - timedelta(days=1)

                self.visits.append({
                    "visit_occurrence_id": visit_id,
                    "person_id": person["person_id"],
                    "visit_concept_id": random.choice([9201, 9202, 9203]),  # IP, OP, ER
                    "visit_start_date": start_date,
                    "visit_end_date": end_date,
                    "visit_type_concept_id": 32817 if random.random() > 0.03 else None,
                })
                visit_id += 1

        # Condition records
        self.conditions = []
        cond_id = 1
        condition_concepts = [4116491, 201826, 4185932, 320128, 4024552]
        for visit in self.visits[:8000]:
            if random.random() > 0.3:  # 70% of visits have conditions
                num_conditions = random.randint(1, 5)
                for _ in range(num_conditions):
                    # Some conditions reference non-existent persons
                    has_valid_person = random.random() > 0.005
                    self.conditions.append({
                        "condition_occurrence_id": cond_id,
                        "person_id": visit["person_id"] if has_valid_person else 999999,
                        "condition_concept_id": random.choice(condition_concepts) if random.random() > 0.02 else 0,
                        "condition_start_date": visit["visit_start_date"],
                        "condition_type_concept_id": 32817,
                        "visit_occurrence_id": visit["visit_occurrence_id"],
                    })
                    cond_id += 1

        # Measurement records
        self.measurements = []
        meas_id = 1
        measurement_concepts = [
            (3004249, "Systolic BP", 70, 200),
            (3012888, "Diastolic BP", 40, 120),
            (3023314, "Body weight", 2, 300),
            (3036277, "BMI", 10, 60),
            (3004410, "Heart rate", 30, 200),
        ]
        for visit in self.visits[:6000]:
            if random.random() > 0.4:
                num_measurements = random.randint(1, 8)
                for _ in range(num_measurements):
                    concept = random.choice(measurement_concepts)
                    # Some measurements have implausible values
                    has_plausible_value = random.random() > 0.02
                    if has_plausible_value:
                        value = random.uniform(concept[2], concept[3])
                    else:
                        value = random.uniform(concept[3] * 2, concept[3] * 3)

                    self.measurements.append({
                        "measurement_id": meas_id,
                        "person_id": visit["person_id"],
                        "measurement_concept_id": concept[0],
                        "measurement_date": visit["visit_start_date"],
                        "measurement_type_concept_id": 32817,
                        "value_as_number": value,
                        "unit_concept_id": 8876 if random.random() > 0.1 else None,
                        "visit_occurrence_id": visit["visit_occurrence_id"],
                    })
                    meas_id += 1

        # Drug exposure records
        self.drug_exposures = []
        drug_id = 1
        drug_concepts = [1125315, 1154343, 1308216, 1713332, 1724117]
        for visit in self.visits[:7000]:
            if random.random() > 0.5:
                num_drugs = random.randint(1, 6)
                for _ in range(num_drugs):
                    start_date = visit["visit_start_date"]
                    # Some drugs have impossible durations
                    has_valid_duration = random.random() > 0.01
                    days_supply = random.randint(1, 90) if has_valid_duration else random.randint(1000, 2000)

                    self.drug_exposures.append({
                        "drug_exposure_id": drug_id,
                        "person_id": visit["person_id"],
                        "drug_concept_id": random.choice(drug_concepts) if random.random() > 0.01 else 0,
                        "drug_exposure_start_date": start_date,
                        "drug_exposure_end_date": start_date + timedelta(days=days_supply),
                        "drug_type_concept_id": 32817,
                        "days_supply": days_supply if random.random() > 0.05 else None,
                        "quantity": random.randint(30, 180) if random.random() > 0.1 else None,
                        "visit_occurrence_id": visit["visit_occurrence_id"],
                    })
                    drug_id += 1

        logger.info(
            f"Generated mock OMOP data: {len(self.persons)} persons, "
            f"{len(self.visits)} visits, {len(self.conditions)} conditions, "
            f"{len(self.measurements)} measurements, {len(self.drug_exposures)} drug exposures"
        )

    def get_table_data(self, table: OMOPTable) -> list[dict[str, Any]]:
        """Get data for a specific table."""
        table_map = {
            OMOPTable.PERSON: self.persons,
            OMOPTable.VISIT_OCCURRENCE: self.visits,
            OMOPTable.CONDITION_OCCURRENCE: self.conditions,
            OMOPTable.MEASUREMENT: self.measurements,
            OMOPTable.DRUG_EXPOSURE: self.drug_exposures,
        }
        return table_map.get(table, [])

    def get_table_count(self, table: OMOPTable) -> int:
        """Get record count for a table."""
        return len(self.get_table_data(table))


# ============================================================================
# Data Quality Service
# ============================================================================


class DataQualityService:
    """OHDSI-style Data Quality Dashboard service."""

    def __init__(self):
        """Initialize the service."""
        self._mock_data = MockOMOPData()
        self._check_definitions = self._build_check_definitions()
        self._run_history: list[DQDHistoryEntry] = []
        self._issues_cache: list[DQDIssue] = []
        self._last_run: DQDRunResult | None = None
        self._cache_lock = threading.Lock()
        self._cache_expiry: float = 0
        self._cache_ttl_seconds: int = 300  # 5 minutes

        # Pre-warm with initial run
        self._warm_cache()

        logger.info(
            f"DataQualityService initialized with {len(self._check_definitions)} checks"
        )

    def _warm_cache(self):
        """Pre-warm the cache with an initial run."""
        try:
            self._last_run = self._execute_all_checks()
            self._cache_expiry = time.time() + self._cache_ttl_seconds

            # Add to history
            self._run_history.append(DQDHistoryEntry(
                run_id=self._last_run.run_id,
                timestamp=self._last_run.started_at,
                overall_score=self._last_run.summary.overall_score,
                completeness_score=self._last_run.summary.completeness_score,
                conformance_score=self._last_run.summary.conformance_score,
                plausibility_score=self._last_run.summary.plausibility_score,
                total_checks=self._last_run.summary.total_checks,
                checks_passed=self._last_run.summary.checks_passed,
                total_issues=self._last_run.summary.total_issues,
            ))

            # Generate some historical data for trends
            self._generate_historical_data()
        except Exception as e:
            logger.error(f"Failed to warm cache: {e}")

    def _generate_historical_data(self):
        """Generate historical data for trend visualization."""
        import random
        random.seed(42)

        base_scores = {
            "overall": 85.0,
            "completeness": 92.0,
            "conformance": 88.0,
            "plausibility": 75.0,
        }

        for days_ago in range(30, 0, -1):
            timestamp = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
            run_id = f"historical-{days_ago}"

            # Add some variance to scores
            variance = random.uniform(-5, 5)

            self._run_history.append(DQDHistoryEntry(
                run_id=run_id,
                timestamp=timestamp,
                overall_score=min(100, max(0, base_scores["overall"] + variance + (30 - days_ago) * 0.2)),
                completeness_score=min(100, max(0, base_scores["completeness"] + variance * 0.5)),
                conformance_score=min(100, max(0, base_scores["conformance"] + variance * 0.8)),
                plausibility_score=min(100, max(0, base_scores["plausibility"] + variance * 1.2)),
                total_checks=len(self._check_definitions),
                checks_passed=int(len(self._check_definitions) * (0.8 + random.uniform(-0.1, 0.1))),
                total_issues=int(50 + random.randint(-10, 10) - (30 - days_ago) * 0.5),
            ))

    def _build_check_definitions(self) -> list[DQDCheckDefinition]:
        """Build the list of DQD check definitions."""
        checks = []

        # ====================
        # COMPLETENESS CHECKS
        # ====================

        # Required field checks for each table
        for table, fields in OMOP_REQUIRED_FIELDS.items():
            for field_name in fields:
                checks.append(DQDCheckDefinition(
                    check_id=f"completeness_{table.value}_{field_name}",
                    check_name=f"{table.value}.{field_name} populated",
                    description=f"Percentage of {table.value} records with {field_name} populated",
                    category=DQDCategory.COMPLETENESS,
                    subcategory=DQDSubcategory.COMPLETENESS_REQUIRED,
                    table=table,
                    field=field_name,
                    threshold_value=95.0,  # 95% minimum
                    severity=DQDSeverity.HIGH if "id" in field_name else DQDSeverity.MEDIUM,
                ))

        # ====================
        # CONFORMANCE CHECKS
        # ====================

        # Gender concept validity
        checks.append(DQDCheckDefinition(
            check_id="conformance_person_gender_valid",
            check_name="Valid gender concepts",
            description="Percentage of persons with valid gender_concept_id values",
            category=DQDCategory.CONFORMANCE,
            subcategory=DQDSubcategory.CONFORMANCE_VALUE,
            table=OMOPTable.PERSON,
            field="gender_concept_id",
            threshold_value=99.0,
            severity=DQDSeverity.HIGH,
        ))

        # Race concept validity
        checks.append(DQDCheckDefinition(
            check_id="conformance_person_race_valid",
            check_name="Valid race concepts",
            description="Percentage of persons with valid race_concept_id values",
            category=DQDCategory.CONFORMANCE,
            subcategory=DQDSubcategory.CONFORMANCE_VALUE,
            table=OMOPTable.PERSON,
            field="race_concept_id",
            threshold_value=95.0,
            severity=DQDSeverity.MEDIUM,
        ))

        # Condition concept non-zero
        checks.append(DQDCheckDefinition(
            check_id="conformance_condition_concept_nonzero",
            check_name="Non-zero condition concepts",
            description="Percentage of conditions with non-zero concept_id (mapped)",
            category=DQDCategory.CONFORMANCE,
            subcategory=DQDSubcategory.CONFORMANCE_VALUE,
            table=OMOPTable.CONDITION_OCCURRENCE,
            field="condition_concept_id",
            threshold_value=98.0,
            severity=DQDSeverity.HIGH,
        ))

        # Drug concept non-zero
        checks.append(DQDCheckDefinition(
            check_id="conformance_drug_concept_nonzero",
            check_name="Non-zero drug concepts",
            description="Percentage of drug exposures with non-zero concept_id (mapped)",
            category=DQDCategory.CONFORMANCE,
            subcategory=DQDSubcategory.CONFORMANCE_VALUE,
            table=OMOPTable.DRUG_EXPOSURE,
            field="drug_concept_id",
            threshold_value=98.0,
            severity=DQDSeverity.HIGH,
        ))

        # FK: Condition -> Person exists
        checks.append(DQDCheckDefinition(
            check_id="conformance_condition_person_fk",
            check_name="Condition person_id references existing person",
            description="Percentage of conditions with valid person_id foreign key",
            category=DQDCategory.CONFORMANCE,
            subcategory=DQDSubcategory.CONFORMANCE_RELATIONAL,
            table=OMOPTable.CONDITION_OCCURRENCE,
            field="person_id",
            threshold_value=100.0,
            severity=DQDSeverity.CRITICAL,
        ))

        # FK: Measurement -> Person exists
        checks.append(DQDCheckDefinition(
            check_id="conformance_measurement_person_fk",
            check_name="Measurement person_id references existing person",
            description="Percentage of measurements with valid person_id foreign key",
            category=DQDCategory.CONFORMANCE,
            subcategory=DQDSubcategory.CONFORMANCE_RELATIONAL,
            table=OMOPTable.MEASUREMENT,
            field="person_id",
            threshold_value=100.0,
            severity=DQDSeverity.CRITICAL,
        ))

        # ====================
        # PLAUSIBILITY CHECKS
        # ====================

        # Birth year reasonable
        checks.append(DQDCheckDefinition(
            check_id="plausibility_person_birthyear",
            check_name="Plausible birth year",
            description="Percentage of persons with birth year between 1900 and current year",
            category=DQDCategory.PLAUSIBILITY,
            subcategory=DQDSubcategory.PLAUSIBILITY_ATEMPORAL,
            table=OMOPTable.PERSON,
            field="year_of_birth",
            threshold_value=99.0,
            severity=DQDSeverity.HIGH,
        ))

        # Visit end >= start
        checks.append(DQDCheckDefinition(
            check_id="plausibility_visit_dates",
            check_name="Visit end date >= start date",
            description="Percentage of visits where end_date is on or after start_date",
            category=DQDCategory.PLAUSIBILITY,
            subcategory=DQDSubcategory.PLAUSIBILITY_TEMPORAL,
            table=OMOPTable.VISIT_OCCURRENCE,
            field="visit_end_date",
            threshold_value=99.0,
            severity=DQDSeverity.HIGH,
        ))

        # Drug duration reasonable
        checks.append(DQDCheckDefinition(
            check_id="plausibility_drug_duration",
            check_name="Reasonable drug exposure duration",
            description="Percentage of drug exposures with duration <= 365 days",
            category=DQDCategory.PLAUSIBILITY,
            subcategory=DQDSubcategory.PLAUSIBILITY_ATEMPORAL,
            table=OMOPTable.DRUG_EXPOSURE,
            field="days_supply",
            threshold_value=99.0,
            severity=DQDSeverity.MEDIUM,
        ))

        # Measurement values within range
        checks.append(DQDCheckDefinition(
            check_id="plausibility_measurement_values",
            check_name="Measurement values within plausible ranges",
            description="Percentage of measurements with values in clinically plausible ranges",
            category=DQDCategory.PLAUSIBILITY,
            subcategory=DQDSubcategory.PLAUSIBILITY_ATEMPORAL,
            table=OMOPTable.MEASUREMENT,
            field="value_as_number",
            threshold_value=98.0,
            severity=DQDSeverity.MEDIUM,
        ))

        # Condition date within patient lifespan
        checks.append(DQDCheckDefinition(
            check_id="plausibility_condition_date_lifespan",
            check_name="Condition dates within patient lifespan",
            description="Percentage of conditions with dates after patient birth year",
            category=DQDCategory.PLAUSIBILITY,
            subcategory=DQDSubcategory.PLAUSIBILITY_TEMPORAL,
            table=OMOPTable.CONDITION_OCCURRENCE,
            field="condition_start_date",
            threshold_value=100.0,
            severity=DQDSeverity.CRITICAL,
        ))

        return checks

    def get_summary(self) -> DQDSummary:
        """Get the current quality summary (cached)."""
        with self._cache_lock:
            if self._last_run and time.time() < self._cache_expiry:
                return self._last_run.summary

        # Cache expired or no run, execute fresh
        run_result = self._execute_all_checks()
        with self._cache_lock:
            self._last_run = run_result
            self._cache_expiry = time.time() + self._cache_ttl_seconds
        return run_result.summary

    def get_checks(
        self,
        category: DQDCategory | None = None,
    ) -> list[DQDCheckResult]:
        """Get check results, optionally filtered by category."""
        with self._cache_lock:
            if self._last_run and time.time() < self._cache_expiry:
                results = self._last_run.check_results
            else:
                # Refresh cache
                run_result = self._execute_all_checks()
                self._last_run = run_result
                self._cache_expiry = time.time() + self._cache_ttl_seconds
                results = run_result.check_results

        if category:
            results = [r for r in results if r.category == category]

        return results

    def get_checks_by_category(
        self,
        category: DQDCategory,
    ) -> list[DQDCheckResult]:
        """Get check results for a specific category."""
        return self.get_checks(category=category)

    def run_checks(self) -> DQDRunResult:
        """Trigger a fresh quality check run."""
        run_result = self._execute_all_checks()

        with self._cache_lock:
            self._last_run = run_result
            self._cache_expiry = time.time() + self._cache_ttl_seconds

            # Add to history
            self._run_history.append(DQDHistoryEntry(
                run_id=run_result.run_id,
                timestamp=run_result.started_at,
                overall_score=run_result.summary.overall_score,
                completeness_score=run_result.summary.completeness_score,
                conformance_score=run_result.summary.conformance_score,
                plausibility_score=run_result.summary.plausibility_score,
                total_checks=run_result.summary.total_checks,
                checks_passed=run_result.summary.checks_passed,
                total_issues=run_result.summary.total_issues,
            ))

            # Keep only last 100 entries
            if len(self._run_history) > 100:
                self._run_history = self._run_history[-100:]

        return run_result

    def get_history(
        self,
        limit: int = 30,
    ) -> list[DQDHistoryEntry]:
        """Get historical quality scores."""
        with self._cache_lock:
            return sorted(
                self._run_history[-limit:],
                key=lambda x: x.timestamp,
                reverse=True
            )

    def get_issues(
        self,
        severity: DQDSeverity | None = None,
        limit: int = 100,
    ) -> list[DQDIssue]:
        """Get current issues, optionally filtered by severity."""
        with self._cache_lock:
            if not self._last_run:
                return []

            issues = self._last_run.issues
            if severity:
                issues = [i for i in issues if i.severity == severity]

            return issues[:limit]

    def _execute_all_checks(self) -> DQDRunResult:
        """Execute all quality checks."""
        start_time = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()
        run_id = hashlib.md5(started_at.encode()).hexdigest()[:12]

        check_results: list[DQDCheckResult] = []
        all_issues: list[DQDIssue] = []

        for check_def in self._check_definitions:
            if not check_def.is_active:
                continue

            try:
                result, issues = self._execute_check(check_def)
                check_results.append(result)
                all_issues.extend(issues)
            except Exception as e:
                logger.error(f"Check {check_def.check_id} failed: {e}")
                check_results.append(DQDCheckResult(
                    check_id=check_def.check_id,
                    check_name=check_def.check_name,
                    category=check_def.category,
                    subcategory=check_def.subcategory,
                    table=check_def.table,
                    field=check_def.field,
                    status=DQDStatus.ERROR,
                    severity=check_def.severity,
                    score=0.0,
                    message=f"Check execution failed: {str(e)}",
                ))

        # Build summary
        summary = self._build_summary(check_results, all_issues, start_time)

        completed_at = datetime.now(timezone.utc).isoformat()
        duration_ms = (time.perf_counter() - start_time) * 1000

        return DQDRunResult(
            run_id=run_id,
            summary=summary,
            check_results=check_results,
            issues=all_issues,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=round(duration_ms, 2),
        )

    def _execute_check(
        self,
        check_def: DQDCheckDefinition,
    ) -> tuple[DQDCheckResult, list[DQDIssue]]:
        """Execute a single quality check."""
        start_time = time.perf_counter()
        issues: list[DQDIssue] = []

        data = self._mock_data.get_table_data(check_def.table)
        total_records = len(data)

        if total_records == 0:
            return DQDCheckResult(
                check_id=check_def.check_id,
                check_name=check_def.check_name,
                category=check_def.category,
                subcategory=check_def.subcategory,
                table=check_def.table,
                field=check_def.field,
                status=DQDStatus.NOT_APPLICABLE,
                severity=check_def.severity,
                score=100.0,
                records_total=0,
                message="No records to check",
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            ), issues

        # Execute check based on type
        passed_records = 0
        failed_examples = []

        if check_def.subcategory == DQDSubcategory.COMPLETENESS_REQUIRED:
            passed_records, failed_examples = self._check_completeness(
                data, check_def.field
            )
        elif check_def.check_id == "conformance_person_gender_valid":
            passed_records, failed_examples = self._check_gender_valid(data)
        elif check_def.check_id == "conformance_person_race_valid":
            passed_records, failed_examples = self._check_race_valid(data)
        elif check_def.check_id == "conformance_condition_concept_nonzero":
            passed_records, failed_examples = self._check_concept_nonzero(
                data, "condition_concept_id"
            )
        elif check_def.check_id == "conformance_drug_concept_nonzero":
            passed_records, failed_examples = self._check_concept_nonzero(
                data, "drug_concept_id"
            )
        elif check_def.check_id == "conformance_condition_person_fk":
            passed_records, failed_examples = self._check_person_fk(data)
        elif check_def.check_id == "conformance_measurement_person_fk":
            passed_records, failed_examples = self._check_person_fk(data)
        elif check_def.check_id == "plausibility_person_birthyear":
            passed_records, failed_examples = self._check_birthyear_plausible(data)
        elif check_def.check_id == "plausibility_visit_dates":
            passed_records, failed_examples = self._check_visit_dates(data)
        elif check_def.check_id == "plausibility_drug_duration":
            passed_records, failed_examples = self._check_drug_duration(data)
        elif check_def.check_id == "plausibility_measurement_values":
            passed_records, failed_examples = self._check_measurement_values(data)
        elif check_def.check_id == "plausibility_condition_date_lifespan":
            passed_records, failed_examples = self._check_condition_date_lifespan(data)
        else:
            # Generic completeness check
            passed_records, failed_examples = self._check_completeness(
                data, check_def.field
            )

        failed_records = total_records - passed_records
        percent_passed = (passed_records / total_records) * 100 if total_records > 0 else 0
        score = percent_passed

        # Determine status
        if percent_passed >= check_def.threshold_value:
            status = DQDStatus.PASSED
        elif percent_passed >= check_def.threshold_value - 5:
            status = DQDStatus.WARNING
        else:
            status = DQDStatus.FAILED

        # Create issues for failed records
        if failed_records > 0:
            issue_id = f"issue_{check_def.check_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            issues.append(DQDIssue(
                issue_id=issue_id,
                check_id=check_def.check_id,
                table=check_def.table,
                field=check_def.field,
                record_id=None,
                severity=check_def.severity if status == DQDStatus.FAILED else DQDSeverity.LOW,
                category=check_def.category,
                description=f"{failed_records} records failed check: {check_def.check_name}",
                current_value=f"{percent_passed:.1f}% passed",
                expected_value=f">= {check_def.threshold_value}%",
                recommendation=f"Review {check_def.table.value}.{check_def.field} for {failed_records} records",
            ))

        execution_time = (time.perf_counter() - start_time) * 1000

        return DQDCheckResult(
            check_id=check_def.check_id,
            check_name=check_def.check_name,
            category=check_def.category,
            subcategory=check_def.subcategory,
            table=check_def.table,
            field=check_def.field,
            status=status,
            severity=check_def.severity,
            score=round(score, 2),
            records_total=total_records,
            records_passed=passed_records,
            records_failed=failed_records,
            percent_passed=round(percent_passed, 2),
            threshold_value=check_def.threshold_value,
            message=f"{percent_passed:.1f}% of records passed (threshold: {check_def.threshold_value}%)",
            failed_examples=failed_examples[:5],  # Limit examples
            execution_time_ms=round(execution_time, 2),
        ), issues

    def _check_completeness(
        self,
        data: list[dict],
        field: str | None,
    ) -> tuple[int, list[dict]]:
        """Check field completeness."""
        if not field:
            return len(data), []

        passed = 0
        failed_examples = []
        for record in data:
            value = record.get(field)
            if value is not None and value != "" and value != 0:
                passed += 1
            elif len(failed_examples) < 5:
                failed_examples.append({
                    "record_id": record.get("person_id") or record.get(f"{field.split('_')[0]}_id"),
                    "field": field,
                    "value": value,
                })
        return passed, failed_examples

    def _check_gender_valid(
        self,
        data: list[dict],
    ) -> tuple[int, list[dict]]:
        """Check gender concept validity."""
        passed = 0
        failed_examples = []
        for record in data:
            value = record.get("gender_concept_id")
            if value in VALID_GENDER_CONCEPTS or value is None:
                passed += 1
            elif len(failed_examples) < 5:
                failed_examples.append({
                    "person_id": record.get("person_id"),
                    "gender_concept_id": value,
                })
        return passed, failed_examples

    def _check_race_valid(
        self,
        data: list[dict],
    ) -> tuple[int, list[dict]]:
        """Check race concept validity."""
        passed = 0
        failed_examples = []
        for record in data:
            value = record.get("race_concept_id")
            if value in VALID_RACE_CONCEPTS or value is None or value == 0:
                passed += 1
            elif len(failed_examples) < 5:
                failed_examples.append({
                    "person_id": record.get("person_id"),
                    "race_concept_id": value,
                })
        return passed, failed_examples

    def _check_concept_nonzero(
        self,
        data: list[dict],
        field: str,
    ) -> tuple[int, list[dict]]:
        """Check that concept IDs are non-zero (mapped)."""
        passed = 0
        failed_examples = []
        for record in data:
            value = record.get(field)
            if value and value != 0:
                passed += 1
            elif len(failed_examples) < 5:
                id_field = f"{field.replace('_concept_id', '')}_id"
                failed_examples.append({
                    "record_id": record.get(id_field),
                    field: value,
                })
        return passed, failed_examples

    def _check_person_fk(
        self,
        data: list[dict],
    ) -> tuple[int, list[dict]]:
        """Check person_id foreign key references valid person."""
        valid_person_ids = {p["person_id"] for p in self._mock_data.persons}
        passed = 0
        failed_examples = []
        for record in data:
            person_id = record.get("person_id")
            if person_id in valid_person_ids:
                passed += 1
            elif len(failed_examples) < 5:
                failed_examples.append({
                    "person_id": person_id,
                    "valid": False,
                })
        return passed, failed_examples

    def _check_birthyear_plausible(
        self,
        data: list[dict],
    ) -> tuple[int, list[dict]]:
        """Check birth year is plausible (1900 - current year)."""
        current_year = datetime.now(timezone.utc).year
        passed = 0
        failed_examples = []
        for record in data:
            year = record.get("year_of_birth")
            if year and 1900 <= year <= current_year:
                passed += 1
            elif len(failed_examples) < 5:
                failed_examples.append({
                    "person_id": record.get("person_id"),
                    "year_of_birth": year,
                })
        return passed, failed_examples

    def _check_visit_dates(
        self,
        data: list[dict],
    ) -> tuple[int, list[dict]]:
        """Check visit end date >= start date."""
        passed = 0
        failed_examples = []
        for record in data:
            start = record.get("visit_start_date")
            end = record.get("visit_end_date")
            if end is None or (start and end and end >= start):
                passed += 1
            elif len(failed_examples) < 5:
                failed_examples.append({
                    "visit_occurrence_id": record.get("visit_occurrence_id"),
                    "visit_start_date": str(start),
                    "visit_end_date": str(end),
                })
        return passed, failed_examples

    def _check_drug_duration(
        self,
        data: list[dict],
    ) -> tuple[int, list[dict]]:
        """Check drug exposure duration is reasonable (<= 365 days)."""
        passed = 0
        failed_examples = []
        for record in data:
            days_supply = record.get("days_supply")
            if days_supply is None or days_supply <= 365:
                passed += 1
            elif len(failed_examples) < 5:
                failed_examples.append({
                    "drug_exposure_id": record.get("drug_exposure_id"),
                    "days_supply": days_supply,
                })
        return passed, failed_examples

    def _check_measurement_values(
        self,
        data: list[dict],
    ) -> tuple[int, list[dict]]:
        """Check measurement values are within plausible ranges."""
        # Simplified plausibility check
        passed = 0
        failed_examples = []
        for record in data:
            value = record.get("value_as_number")
            concept = record.get("measurement_concept_id")

            # Basic range checks
            is_plausible = True
            if value is not None:
                if concept == 3004249 and (value < 0 or value > 300):  # Systolic BP
                    is_plausible = False
                elif concept == 3012888 and (value < 0 or value > 200):  # Diastolic BP
                    is_plausible = False
                elif concept == 3023314 and (value < 0 or value > 500):  # Weight kg
                    is_plausible = False
                elif concept == 3036277 and (value < 5 or value > 80):  # BMI
                    is_plausible = False
                elif concept == 3004410 and (value < 20 or value > 250):  # Heart rate
                    is_plausible = False

            if is_plausible:
                passed += 1
            elif len(failed_examples) < 5:
                failed_examples.append({
                    "measurement_id": record.get("measurement_id"),
                    "measurement_concept_id": concept,
                    "value_as_number": value,
                })

        return passed, failed_examples

    def _check_condition_date_lifespan(
        self,
        data: list[dict],
    ) -> tuple[int, list[dict]]:
        """Check condition dates are after patient birth."""
        person_birth_years = {
            p["person_id"]: p["year_of_birth"]
            for p in self._mock_data.persons
        }
        passed = 0
        failed_examples = []
        for record in data:
            person_id = record.get("person_id")
            cond_date = record.get("condition_start_date")
            birth_year = person_birth_years.get(person_id)

            if cond_date is None or birth_year is None:
                passed += 1
            elif cond_date.year >= birth_year:
                passed += 1
            elif len(failed_examples) < 5:
                failed_examples.append({
                    "condition_occurrence_id": record.get("condition_occurrence_id"),
                    "person_id": person_id,
                    "condition_start_date": str(cond_date),
                    "birth_year": birth_year,
                })

        return passed, failed_examples

    def _build_summary(
        self,
        check_results: list[DQDCheckResult],
        issues: list[DQDIssue],
        start_time: float,
    ) -> DQDSummary:
        """Build summary from check results."""
        # Count by status
        passed = sum(1 for r in check_results if r.status == DQDStatus.PASSED)
        failed = sum(1 for r in check_results if r.status == DQDStatus.FAILED)
        warning = sum(1 for r in check_results if r.status == DQDStatus.WARNING)
        error = sum(1 for r in check_results if r.status == DQDStatus.ERROR)

        # Count issues by severity
        critical = sum(1 for i in issues if i.severity == DQDSeverity.CRITICAL)
        high = sum(1 for i in issues if i.severity == DQDSeverity.HIGH)
        medium = sum(1 for i in issues if i.severity == DQDSeverity.MEDIUM)
        low = sum(1 for i in issues if i.severity == DQDSeverity.LOW)

        # Calculate category scores
        def calc_category_score(cat: DQDCategory) -> float:
            cat_results = [r for r in check_results if r.category == cat]
            if not cat_results:
                return 100.0
            return sum(r.score for r in cat_results) / len(cat_results)

        completeness_score = calc_category_score(DQDCategory.COMPLETENESS)
        conformance_score = calc_category_score(DQDCategory.CONFORMANCE)
        plausibility_score = calc_category_score(DQDCategory.PLAUSIBILITY)

        # Overall score (weighted average)
        overall_score = (
            completeness_score * 0.35 +
            conformance_score * 0.35 +
            plausibility_score * 0.30
        )

        # Category summaries
        category_summaries = []
        for cat in DQDCategory:
            cat_results = [r for r in check_results if r.category == cat]
            cat_issues = [i for i in issues if i.category == cat]
            cat_passed = sum(1 for r in cat_results if r.status == DQDStatus.PASSED)
            cat_failed = sum(1 for r in cat_results if r.status == DQDStatus.FAILED)
            cat_warning = sum(1 for r in cat_results if r.status == DQDStatus.WARNING)
            cat_critical = sum(1 for i in cat_issues if i.severity == DQDSeverity.CRITICAL)
            cat_high = sum(1 for i in cat_issues if i.severity == DQDSeverity.HIGH)

            category_summaries.append(DQDCategorySummary(
                category=cat,
                score=round(calc_category_score(cat), 2),
                checks_total=len(cat_results),
                checks_passed=cat_passed,
                checks_failed=cat_failed,
                checks_warning=cat_warning,
                critical_issues=cat_critical,
                high_issues=cat_high,
            ))

        # Table summaries
        table_summaries = []
        for table in [
            OMOPTable.PERSON,
            OMOPTable.VISIT_OCCURRENCE,
            OMOPTable.CONDITION_OCCURRENCE,
            OMOPTable.DRUG_EXPOSURE,
            OMOPTable.MEASUREMENT,
        ]:
            table_results = [r for r in check_results if r.table == table]
            table_issues = [i for i in issues if i.table == table]

            def calc_table_category_score(cat: DQDCategory) -> float:
                cat_results = [r for r in table_results if r.category == cat]
                if not cat_results:
                    return 100.0
                return sum(r.score for r in cat_results) / len(cat_results)

            table_comp = calc_table_category_score(DQDCategory.COMPLETENESS)
            table_conf = calc_table_category_score(DQDCategory.CONFORMANCE)
            table_plaus = calc_table_category_score(DQDCategory.PLAUSIBILITY)
            table_score = (table_comp * 0.35 + table_conf * 0.35 + table_plaus * 0.30)

            table_summaries.append(DQDTableSummary(
                table=table,
                record_count=self._mock_data.get_table_count(table),
                score=round(table_score, 2),
                completeness_score=round(table_comp, 2),
                conformance_score=round(table_conf, 2),
                plausibility_score=round(table_plaus, 2),
                issues_count=len(table_issues),
                critical_issues=sum(1 for i in table_issues if i.severity == DQDSeverity.CRITICAL),
            ))

        execution_time = (time.perf_counter() - start_time) * 1000

        return DQDSummary(
            overall_score=round(overall_score, 2),
            executed_at=datetime.now(timezone.utc).isoformat(),
            execution_time_ms=round(execution_time, 2),
            completeness_score=round(completeness_score, 2),
            conformance_score=round(conformance_score, 2),
            plausibility_score=round(plausibility_score, 2),
            total_checks=len(check_results),
            checks_passed=passed,
            checks_failed=failed,
            checks_warning=warning,
            checks_error=error,
            total_issues=len(issues),
            critical_issues=critical,
            high_issues=high,
            medium_issues=medium,
            low_issues=low,
            category_summaries=category_summaries,
            table_summaries=table_summaries,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "total_checks": len(self._check_definitions),
            "active_checks": sum(1 for c in self._check_definitions if c.is_active),
            "history_entries": len(self._run_history),
            "cache_valid": time.time() < self._cache_expiry,
            "tables_monitored": len(set(c.table for c in self._check_definitions)),
        }


# ============================================================================
# Singleton Pattern
# ============================================================================

_service_instance: DataQualityService | None = None
_service_lock = threading.Lock()


def get_data_quality_service() -> DataQualityService:
    """Get singleton instance of DataQualityService."""
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = DataQualityService()
    return _service_instance


def reset_data_quality_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _service_instance
    with _service_lock:
        _service_instance = None
