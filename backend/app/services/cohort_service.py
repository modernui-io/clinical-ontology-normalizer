"""Cohort Builder Service for Visual Cohort Building.

This module provides comprehensive cohort definition and execution capabilities
for clinical research and population health analytics. It supports:

- Multiple criterion types (demographics, conditions, drugs, procedures, measurements, visits)
- Complex boolean logic (AND, OR, NOT)
- Temporal constraints (X days before/after Y)
- OMOP CDM-compatible SQL generation
- Cohort comparison and analytics

Usage:
    from app.services.cohort_service import get_cohort_service

    service = get_cohort_service()

    # Create a cohort definition
    cohort = service.create_cohort(CohortDefinitionCreate(
        name="Diabetic Patients",
        criteria=[
            ConditionCriterion(codes=["E11"], code_system="ICD10CM")
        ]
    ))

    # Get patient count
    count = service.get_patient_count(cohort.id)
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from abc import ABC, abstractmethod
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# ==============================================================================
# Enums
# ==============================================================================


class LogicOperator(str, Enum):
    """Boolean logic operators for combining criteria."""
    AND = "AND"
    OR = "OR"
    NOT = "NOT"


class TemporalOperator(str, Enum):
    """Temporal relationship operators."""
    BEFORE = "before"
    AFTER = "after"
    DURING = "during"
    STARTS_BEFORE = "starts_before"
    STARTS_AFTER = "starts_after"
    ENDS_BEFORE = "ends_before"
    ENDS_AFTER = "ends_after"
    OVERLAPS = "overlaps"


class CohortStatus(str, Enum):
    """Cohort definition status."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class CriterionType(str, Enum):
    """Types of cohort criteria."""
    DEMOGRAPHIC = "demographic"
    CONDITION = "condition"
    DRUG = "drug"
    PROCEDURE = "procedure"
    MEASUREMENT = "measurement"
    VISIT = "visit"
    GROUP = "group"


class Gender(str, Enum):
    """Gender values for demographic criteria."""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNKNOWN = "unknown"


class Race(str, Enum):
    """Race values for demographic criteria."""
    WHITE = "white"
    BLACK = "black"
    ASIAN = "asian"
    NATIVE_AMERICAN = "native_american"
    PACIFIC_ISLANDER = "pacific_islander"
    OTHER = "other"
    UNKNOWN = "unknown"


class Ethnicity(str, Enum):
    """Ethnicity values for demographic criteria."""
    HISPANIC = "hispanic"
    NOT_HISPANIC = "not_hispanic"
    UNKNOWN = "unknown"


class VisitType(str, Enum):
    """Visit type values."""
    INPATIENT = "inpatient"
    OUTPATIENT = "outpatient"
    EMERGENCY = "emergency"
    LONG_TERM_CARE = "long_term_care"
    HOME_HEALTH = "home_health"
    TELEHEALTH = "telehealth"
    OTHER = "other"


# ==============================================================================
# Value Range Models
# ==============================================================================


class NumericRange(BaseModel):
    """Numeric range for measurements."""
    min_value: float | None = None
    max_value: float | None = None
    include_min: bool = True
    include_max: bool = True


class DateRange(BaseModel):
    """Date range for temporal filtering."""
    start_date: date | None = None
    end_date: date | None = None
    relative_days_before: int | None = None  # Relative to index date
    relative_days_after: int | None = None


class AgeRange(BaseModel):
    """Age range for demographic criteria."""
    min_age: int | None = None
    max_age: int | None = None


# ==============================================================================
# Temporal Constraint
# ==============================================================================


class TemporalConstraint(BaseModel):
    """Temporal relationship between criteria."""
    operator: TemporalOperator
    reference_criterion_id: str
    days_before: int | None = None
    days_after: int | None = None
    allow_same_day: bool = True


# ==============================================================================
# Code Entry Model
# ==============================================================================


class CodeEntry(BaseModel):
    """A clinical code with optional description."""
    code: str
    display: str | None = None
    system: str | None = None  # ICD10CM, SNOMED, RxNorm, CPT, LOINC

    # VP-Security: Validate code to prevent SQL injection
    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Validate code contains only safe characters for SQL queries.

        Valid clinical codes (ICD10, SNOMED, RxNorm, CPT, LOINC) contain
        only alphanumeric characters, dots, hyphens, underscores, and colons.
        """
        if not v or not re.match(r"^[A-Za-z0-9._:\-]+$", v):
            raise ValueError(
                "Code must contain only alphanumeric characters, dots, hyphens, underscores, or colons"
            )
        if len(v) > 50:
            raise ValueError("Code must be 50 characters or fewer")
        return v


# ==============================================================================
# Base Criterion
# ==============================================================================


class CohortCriterion(BaseModel, ABC):
    """Base class for all cohort criteria."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    criterion_type: CriterionType
    name: str | None = None
    description: str | None = None
    negated: bool = False  # NOT operator
    temporal_constraint: TemporalConstraint | None = None
    occurrence_count: int | None = None  # Minimum occurrences required

    @abstractmethod
    def to_sql_fragment(self, alias: str = "p") -> str:
        """Generate SQL fragment for this criterion."""
        pass

    @abstractmethod
    def get_display_text(self) -> str:
        """Get human-readable description of criterion."""
        pass


# ==============================================================================
# Specific Criterion Types
# ==============================================================================


class DemographicCriterion(CohortCriterion):
    """Demographic-based criterion (age, gender, race, ethnicity)."""
    criterion_type: Literal[CriterionType.DEMOGRAPHIC] = CriterionType.DEMOGRAPHIC
    age_range: AgeRange | None = None
    genders: list[Gender] | None = None
    races: list[Race] | None = None
    ethnicities: list[Ethnicity] | None = None

    def to_sql_fragment(self, alias: str = "p") -> str:
        conditions = []

        if self.age_range:
            if self.age_range.min_age is not None:
                conditions.append(
                    f"EXTRACT(YEAR FROM CURRENT_DATE) - {alias}.year_of_birth >= {self.age_range.min_age}"
                )
            if self.age_range.max_age is not None:
                conditions.append(
                    f"EXTRACT(YEAR FROM CURRENT_DATE) - {alias}.year_of_birth <= {self.age_range.max_age}"
                )

        if self.genders:
            gender_concept_ids = self._get_gender_concept_ids()
            conditions.append(f"{alias}.gender_concept_id IN ({','.join(map(str, gender_concept_ids))})")

        if self.races:
            race_concept_ids = self._get_race_concept_ids()
            conditions.append(f"{alias}.race_concept_id IN ({','.join(map(str, race_concept_ids))})")

        if self.ethnicities:
            ethnicity_concept_ids = self._get_ethnicity_concept_ids()
            conditions.append(f"{alias}.ethnicity_concept_id IN ({','.join(map(str, ethnicity_concept_ids))})")

        if not conditions:
            return "1=1"

        sql = " AND ".join(conditions)
        if self.negated:
            sql = f"NOT ({sql})"
        return sql

    def _get_gender_concept_ids(self) -> list[int]:
        """Map gender values to OMOP concept IDs."""
        mapping = {
            Gender.MALE: 8507,
            Gender.FEMALE: 8532,
            Gender.OTHER: 8551,
            Gender.UNKNOWN: 8551,
        }
        return [mapping.get(g, 0) for g in (self.genders or [])]

    def _get_race_concept_ids(self) -> list[int]:
        """Map race values to OMOP concept IDs."""
        mapping = {
            Race.WHITE: 8527,
            Race.BLACK: 8516,
            Race.ASIAN: 8515,
            Race.NATIVE_AMERICAN: 8657,
            Race.PACIFIC_ISLANDER: 8557,
            Race.OTHER: 8522,
            Race.UNKNOWN: 8552,
        }
        return [mapping.get(r, 0) for r in (self.races or [])]

    def _get_ethnicity_concept_ids(self) -> list[int]:
        """Map ethnicity values to OMOP concept IDs."""
        mapping = {
            Ethnicity.HISPANIC: 38003563,
            Ethnicity.NOT_HISPANIC: 38003564,
            Ethnicity.UNKNOWN: 0,
        }
        return [mapping.get(e, 0) for e in (self.ethnicities or [])]

    def get_display_text(self) -> str:
        parts = []
        if self.age_range:
            if self.age_range.min_age and self.age_range.max_age:
                parts.append(f"Age {self.age_range.min_age}-{self.age_range.max_age}")
            elif self.age_range.min_age:
                parts.append(f"Age >= {self.age_range.min_age}")
            elif self.age_range.max_age:
                parts.append(f"Age <= {self.age_range.max_age}")
        if self.genders:
            parts.append(f"Gender: {', '.join(g.value for g in self.genders)}")
        if self.races:
            parts.append(f"Race: {', '.join(r.value for r in self.races)}")
        if self.ethnicities:
            parts.append(f"Ethnicity: {', '.join(e.value for e in self.ethnicities)}")

        text = "; ".join(parts) if parts else "Any demographics"
        return f"NOT ({text})" if self.negated else text


class ConditionCriterion(CohortCriterion):
    """Condition/diagnosis-based criterion."""
    criterion_type: Literal[CriterionType.CONDITION] = CriterionType.CONDITION
    codes: list[CodeEntry] = Field(default_factory=list)
    code_system: str = "ICD10CM"  # ICD10CM, SNOMED
    include_descendants: bool = True
    date_range: DateRange | None = None
    primary_only: bool = False  # Only primary diagnoses

    def to_sql_fragment(self, alias: str = "p") -> str:
        if not self.codes:
            return "1=0"  # No codes = no matches

        code_list = ", ".join(f"'{c.code}'" for c in self.codes)

        conditions = [f"co.condition_source_value IN ({code_list})"]

        if self.date_range:
            if self.date_range.start_date:
                conditions.append(f"co.condition_start_date >= '{self.date_range.start_date}'")
            if self.date_range.end_date:
                conditions.append(f"co.condition_start_date <= '{self.date_range.end_date}'")

        subquery = f"""
        EXISTS (
            SELECT 1 FROM condition_occurrence co
            WHERE co.person_id = {alias}.person_id
            AND {' AND '.join(conditions)}
        )
        """

        if self.negated:
            subquery = f"NOT {subquery}"
        return subquery.strip()

    def get_display_text(self) -> str:
        code_text = ", ".join(f"{c.code}" + (f" ({c.display})" if c.display else "") for c in self.codes[:3])
        if len(self.codes) > 3:
            code_text += f" +{len(self.codes) - 3} more"
        text = f"Condition: {code_text}"
        if self.date_range and (self.date_range.start_date or self.date_range.end_date):
            text += f" [{self.date_range.start_date or '*'} to {self.date_range.end_date or '*'}]"
        return f"NOT ({text})" if self.negated else text


class DrugCriterion(CohortCriterion):
    """Drug/medication-based criterion."""
    criterion_type: Literal[CriterionType.DRUG] = CriterionType.DRUG
    codes: list[CodeEntry] = Field(default_factory=list)
    code_system: str = "RxNorm"
    include_descendants: bool = True
    date_range: DateRange | None = None
    min_days_supply: int | None = None
    min_quantity: float | None = None

    def to_sql_fragment(self, alias: str = "p") -> str:
        if not self.codes:
            return "1=0"

        code_list = ", ".join(f"'{c.code}'" for c in self.codes)

        conditions = [f"de.drug_source_value IN ({code_list})"]

        if self.date_range:
            if self.date_range.start_date:
                conditions.append(f"de.drug_exposure_start_date >= '{self.date_range.start_date}'")
            if self.date_range.end_date:
                conditions.append(f"de.drug_exposure_start_date <= '{self.date_range.end_date}'")

        if self.min_days_supply:
            conditions.append(f"de.days_supply >= {self.min_days_supply}")

        if self.min_quantity:
            conditions.append(f"de.quantity >= {self.min_quantity}")

        subquery = f"""
        EXISTS (
            SELECT 1 FROM drug_exposure de
            WHERE de.person_id = {alias}.person_id
            AND {' AND '.join(conditions)}
        )
        """

        if self.negated:
            subquery = f"NOT {subquery}"
        return subquery.strip()

    def get_display_text(self) -> str:
        code_text = ", ".join(f"{c.code}" + (f" ({c.display})" if c.display else "") for c in self.codes[:3])
        if len(self.codes) > 3:
            code_text += f" +{len(self.codes) - 3} more"
        text = f"Drug: {code_text}"
        if self.date_range and (self.date_range.start_date or self.date_range.end_date):
            text += f" [{self.date_range.start_date or '*'} to {self.date_range.end_date or '*'}]"
        return f"NOT ({text})" if self.negated else text


class ProcedureCriterion(CohortCriterion):
    """Procedure-based criterion."""
    criterion_type: Literal[CriterionType.PROCEDURE] = CriterionType.PROCEDURE
    codes: list[CodeEntry] = Field(default_factory=list)
    code_system: str = "CPT"  # CPT, ICD10PCS, SNOMED
    include_descendants: bool = True
    date_range: DateRange | None = None

    def to_sql_fragment(self, alias: str = "p") -> str:
        if not self.codes:
            return "1=0"

        code_list = ", ".join(f"'{c.code}'" for c in self.codes)

        conditions = [f"po.procedure_source_value IN ({code_list})"]

        if self.date_range:
            if self.date_range.start_date:
                conditions.append(f"po.procedure_date >= '{self.date_range.start_date}'")
            if self.date_range.end_date:
                conditions.append(f"po.procedure_date <= '{self.date_range.end_date}'")

        subquery = f"""
        EXISTS (
            SELECT 1 FROM procedure_occurrence po
            WHERE po.person_id = {alias}.person_id
            AND {' AND '.join(conditions)}
        )
        """

        if self.negated:
            subquery = f"NOT {subquery}"
        return subquery.strip()

    def get_display_text(self) -> str:
        code_text = ", ".join(f"{c.code}" + (f" ({c.display})" if c.display else "") for c in self.codes[:3])
        if len(self.codes) > 3:
            code_text += f" +{len(self.codes) - 3} more"
        text = f"Procedure: {code_text}"
        if self.date_range and (self.date_range.start_date or self.date_range.end_date):
            text += f" [{self.date_range.start_date or '*'} to {self.date_range.end_date or '*'}]"
        return f"NOT ({text})" if self.negated else text


class MeasurementCriterion(CohortCriterion):
    """Measurement/lab-based criterion."""
    criterion_type: Literal[CriterionType.MEASUREMENT] = CriterionType.MEASUREMENT
    codes: list[CodeEntry] = Field(default_factory=list)
    code_system: str = "LOINC"
    value_range: NumericRange | None = None
    unit: str | None = None
    date_range: DateRange | None = None
    abnormal_only: bool = False

    def to_sql_fragment(self, alias: str = "p") -> str:
        if not self.codes:
            return "1=0"

        code_list = ", ".join(f"'{c.code}'" for c in self.codes)

        conditions = [f"m.measurement_source_value IN ({code_list})"]

        if self.value_range:
            if self.value_range.min_value is not None:
                op = ">=" if self.value_range.include_min else ">"
                conditions.append(f"m.value_as_number {op} {self.value_range.min_value}")
            if self.value_range.max_value is not None:
                op = "<=" if self.value_range.include_max else "<"
                conditions.append(f"m.value_as_number {op} {self.value_range.max_value}")

        if self.date_range:
            if self.date_range.start_date:
                conditions.append(f"m.measurement_date >= '{self.date_range.start_date}'")
            if self.date_range.end_date:
                conditions.append(f"m.measurement_date <= '{self.date_range.end_date}'")

        if self.abnormal_only:
            conditions.append("(m.value_as_number < m.range_low OR m.value_as_number > m.range_high)")

        subquery = f"""
        EXISTS (
            SELECT 1 FROM measurement m
            WHERE m.person_id = {alias}.person_id
            AND {' AND '.join(conditions)}
        )
        """

        if self.negated:
            subquery = f"NOT {subquery}"
        return subquery.strip()

    def get_display_text(self) -> str:
        code_text = ", ".join(f"{c.code}" + (f" ({c.display})" if c.display else "") for c in self.codes[:3])
        if len(self.codes) > 3:
            code_text += f" +{len(self.codes) - 3} more"
        text = f"Measurement: {code_text}"
        if self.value_range:
            if self.value_range.min_value is not None and self.value_range.max_value is not None:
                text += f" [{self.value_range.min_value}-{self.value_range.max_value}]"
            elif self.value_range.min_value is not None:
                text += f" [>= {self.value_range.min_value}]"
            elif self.value_range.max_value is not None:
                text += f" [<= {self.value_range.max_value}]"
        return f"NOT ({text})" if self.negated else text


class VisitCriterion(CohortCriterion):
    """Visit/encounter-based criterion."""
    criterion_type: Literal[CriterionType.VISIT] = CriterionType.VISIT
    visit_types: list[VisitType] = Field(default_factory=list)
    date_range: DateRange | None = None
    min_length_of_stay: int | None = None  # Days
    max_length_of_stay: int | None = None

    def to_sql_fragment(self, alias: str = "p") -> str:
        conditions = []

        if self.visit_types:
            visit_concept_ids = self._get_visit_concept_ids()
            if visit_concept_ids:
                conditions.append(f"vo.visit_concept_id IN ({','.join(map(str, visit_concept_ids))})")

        if self.date_range:
            if self.date_range.start_date:
                conditions.append(f"vo.visit_start_date >= '{self.date_range.start_date}'")
            if self.date_range.end_date:
                conditions.append(f"vo.visit_start_date <= '{self.date_range.end_date}'")

        if self.min_length_of_stay:
            conditions.append(f"vo.visit_end_date - vo.visit_start_date >= {self.min_length_of_stay}")

        if self.max_length_of_stay:
            conditions.append(f"vo.visit_end_date - vo.visit_start_date <= {self.max_length_of_stay}")

        if not conditions:
            conditions = ["1=1"]

        subquery = f"""
        EXISTS (
            SELECT 1 FROM visit_occurrence vo
            WHERE vo.person_id = {alias}.person_id
            AND {' AND '.join(conditions)}
        )
        """

        if self.negated:
            subquery = f"NOT {subquery}"
        return subquery.strip()

    def _get_visit_concept_ids(self) -> list[int]:
        """Map visit types to OMOP concept IDs."""
        mapping = {
            VisitType.INPATIENT: 9201,
            VisitType.OUTPATIENT: 9202,
            VisitType.EMERGENCY: 9203,
            VisitType.LONG_TERM_CARE: 42898160,
            VisitType.HOME_HEALTH: 581476,
            VisitType.TELEHEALTH: 5083,
            VisitType.OTHER: 0,
        }
        return [mapping.get(vt, 0) for vt in self.visit_types]

    def get_display_text(self) -> str:
        parts = []
        if self.visit_types:
            parts.append(f"Visit types: {', '.join(vt.value for vt in self.visit_types)}")
        if self.date_range and (self.date_range.start_date or self.date_range.end_date):
            parts.append(f"[{self.date_range.start_date or '*'} to {self.date_range.end_date or '*'}]")
        if self.min_length_of_stay:
            parts.append(f"LOS >= {self.min_length_of_stay} days")
        if self.max_length_of_stay:
            parts.append(f"LOS <= {self.max_length_of_stay} days")
        text = "; ".join(parts) if parts else "Any visit"
        return f"NOT ({text})" if self.negated else text


class CriteriaGroup(CohortCriterion):
    """Group of criteria combined with a logic operator."""
    criterion_type: Literal[CriterionType.GROUP] = CriterionType.GROUP
    operator: LogicOperator = LogicOperator.AND
    criteria: list["AnyCriterion"] = Field(default_factory=list)

    def to_sql_fragment(self, alias: str = "p") -> str:
        if not self.criteria:
            return "1=1"

        fragments = [c.to_sql_fragment(alias) for c in self.criteria]

        if self.operator == LogicOperator.NOT:
            # NOT applies to the entire group
            sql = " AND ".join(f"({f})" for f in fragments)
            sql = f"NOT ({sql})"
        else:
            connector = f" {self.operator.value} "
            sql = connector.join(f"({f})" for f in fragments)

        if self.negated and self.operator != LogicOperator.NOT:
            sql = f"NOT ({sql})"

        return sql

    def get_display_text(self) -> str:
        if not self.criteria:
            return "Empty group"

        parts = [c.get_display_text() for c in self.criteria]
        text = f" {self.operator.value} ".join(parts)

        if len(self.criteria) > 1:
            text = f"({text})"

        return f"NOT {text}" if self.negated else text


# Type union for all criterion types
AnyCriterion = (
    DemographicCriterion
    | ConditionCriterion
    | DrugCriterion
    | ProcedureCriterion
    | MeasurementCriterion
    | VisitCriterion
    | CriteriaGroup
)

# Update forward reference
CriteriaGroup.model_rebuild()


# ==============================================================================
# Cohort Definition Models
# ==============================================================================


class CohortDefinition(BaseModel):
    """Complete cohort definition."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str | None = None
    version: str = "1.0.0"
    status: CohortStatus = CohortStatus.DRAFT
    criteria: list[AnyCriterion] = Field(default_factory=list)
    root_operator: LogicOperator = LogicOperator.AND
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str | None = None
    tags: list[str] = Field(default_factory=list)

    def to_sql(self) -> str:
        """Generate complete SQL query for cohort."""
        if not self.criteria:
            return "SELECT person_id FROM person"

        fragments = [c.to_sql_fragment("p") for c in self.criteria]

        if self.root_operator == LogicOperator.NOT:
            where_clause = " AND ".join(f"({f})" for f in fragments)
            where_clause = f"NOT ({where_clause})"
        else:
            connector = f" {self.root_operator.value} "
            where_clause = connector.join(f"({f})" for f in fragments)

        sql = f"""
SELECT DISTINCT p.person_id
FROM person p
WHERE {where_clause}
        """
        return sql.strip()

    def to_count_sql(self) -> str:
        """Generate SQL query for patient count."""
        base_sql = self.to_sql()
        return f"SELECT COUNT(*) as patient_count FROM ({base_sql}) cohort"


class CohortDefinitionCreate(BaseModel):
    """Request model for creating a cohort."""
    name: str
    description: str | None = None
    criteria: list[AnyCriterion] = Field(default_factory=list)
    root_operator: LogicOperator = LogicOperator.AND
    tags: list[str] = Field(default_factory=list)


class CohortDefinitionUpdate(BaseModel):
    """Request model for updating a cohort."""
    name: str | None = None
    description: str | None = None
    criteria: list[AnyCriterion] | None = None
    root_operator: LogicOperator | None = None
    status: CohortStatus | None = None
    tags: list[str] | None = None


class CohortVersion(BaseModel):
    """Version history entry for a cohort."""
    version: str
    created_at: datetime
    created_by: str | None = None
    changes: str | None = None
    definition_snapshot: dict[str, Any]


# ==============================================================================
# Execution Results
# ==============================================================================


class CohortCountResult(BaseModel):
    """Result of counting patients in a cohort."""
    cohort_id: str
    count: int
    execution_time_ms: float
    sql_query: str
    cached: bool = False


class PatientListResult(BaseModel):
    """Result of executing a cohort to get patient list."""
    cohort_id: str
    patient_ids: list[int]
    total_count: int
    page: int
    page_size: int
    execution_time_ms: float


class DemographicBreakdown(BaseModel):
    """Demographic breakdown of a cohort."""
    total_patients: int
    by_gender: dict[str, int] = Field(default_factory=dict)
    by_race: dict[str, int] = Field(default_factory=dict)
    by_ethnicity: dict[str, int] = Field(default_factory=dict)
    by_age_group: dict[str, int] = Field(default_factory=dict)
    mean_age: float | None = None
    median_age: float | None = None


class ConditionPrevalence(BaseModel):
    """Condition prevalence in a cohort."""
    condition_code: str
    condition_name: str | None = None
    patient_count: int
    prevalence_percent: float


class DrugUtilization(BaseModel):
    """Drug utilization in a cohort."""
    drug_code: str
    drug_name: str | None = None
    patient_count: int
    utilization_percent: float


class CohortComparisonResult(BaseModel):
    """Result of comparing two cohorts."""
    cohort_a_id: str
    cohort_b_id: str
    cohort_a_count: int
    cohort_b_count: int
    overlap_count: int
    cohort_a_only_count: int
    cohort_b_only_count: int
    demographics_a: DemographicBreakdown | None = None
    demographics_b: DemographicBreakdown | None = None
    top_conditions_a: list[ConditionPrevalence] = Field(default_factory=list)
    top_conditions_b: list[ConditionPrevalence] = Field(default_factory=list)
    top_drugs_a: list[DrugUtilization] = Field(default_factory=list)
    top_drugs_b: list[DrugUtilization] = Field(default_factory=list)


# ==============================================================================
# Criteria Library
# ==============================================================================


class SavedCriterion(BaseModel):
    """A saved criterion in the criteria library."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str | None = None
    category: str  # e.g., "Demographics", "Chronic Conditions", "Common Labs"
    criterion: AnyCriterion
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str | None = None
    usage_count: int = 0
    is_public: bool = True


# ==============================================================================
# Cohort Service
# ==============================================================================


class CohortService:
    """Service for managing cohort definitions and execution."""

    def __init__(self):
        self._cohorts: dict[str, CohortDefinition] = {}
        self._versions: dict[str, list[CohortVersion]] = {}
        self._criteria_library: dict[str, SavedCriterion] = {}
        self._init_default_criteria_library()
        self._init_demo_cohorts()

    def _init_default_criteria_library(self):
        """Initialize default criteria library with common criteria."""
        default_criteria = [
            SavedCriterion(
                name="Adults (18+)",
                description="Patients 18 years or older",
                category="Demographics",
                criterion=DemographicCriterion(
                    name="Adults",
                    age_range=AgeRange(min_age=18)
                )
            ),
            SavedCriterion(
                name="Elderly (65+)",
                description="Patients 65 years or older",
                category="Demographics",
                criterion=DemographicCriterion(
                    name="Elderly",
                    age_range=AgeRange(min_age=65)
                )
            ),
            SavedCriterion(
                name="Pediatric (<18)",
                description="Patients under 18 years",
                category="Demographics",
                criterion=DemographicCriterion(
                    name="Pediatric",
                    age_range=AgeRange(max_age=17)
                )
            ),
            SavedCriterion(
                name="Type 2 Diabetes",
                description="Patients with Type 2 Diabetes diagnosis",
                category="Chronic Conditions",
                criterion=ConditionCriterion(
                    name="Type 2 Diabetes",
                    codes=[
                        CodeEntry(code="E11", display="Type 2 diabetes mellitus"),
                        CodeEntry(code="E11.9", display="Type 2 diabetes mellitus without complications"),
                    ],
                    code_system="ICD10CM"
                )
            ),
            SavedCriterion(
                name="Hypertension",
                description="Patients with essential hypertension",
                category="Chronic Conditions",
                criterion=ConditionCriterion(
                    name="Hypertension",
                    codes=[
                        CodeEntry(code="I10", display="Essential (primary) hypertension"),
                    ],
                    code_system="ICD10CM"
                )
            ),
            SavedCriterion(
                name="Heart Failure",
                description="Patients with heart failure diagnosis",
                category="Chronic Conditions",
                criterion=ConditionCriterion(
                    name="Heart Failure",
                    codes=[
                        CodeEntry(code="I50", display="Heart failure"),
                        CodeEntry(code="I50.9", display="Heart failure, unspecified"),
                    ],
                    code_system="ICD10CM"
                )
            ),
            SavedCriterion(
                name="Metformin Use",
                description="Patients taking metformin",
                category="Medications",
                criterion=DrugCriterion(
                    name="Metformin",
                    codes=[
                        CodeEntry(code="6809", display="Metformin"),
                    ],
                    code_system="RxNorm"
                )
            ),
            SavedCriterion(
                name="Elevated HbA1c",
                description="HbA1c >= 6.5%",
                category="Lab Values",
                criterion=MeasurementCriterion(
                    name="Elevated HbA1c",
                    codes=[
                        CodeEntry(code="4548-4", display="Hemoglobin A1c/Hemoglobin.total in Blood"),
                    ],
                    code_system="LOINC",
                    value_range=NumericRange(min_value=6.5)
                )
            ),
            SavedCriterion(
                name="Inpatient Visit",
                description="Patients with any inpatient hospitalization",
                category="Encounters",
                criterion=VisitCriterion(
                    name="Inpatient Visit",
                    visit_types=[VisitType.INPATIENT]
                )
            ),
            SavedCriterion(
                name="Emergency Visit",
                description="Patients with any emergency department visit",
                category="Encounters",
                criterion=VisitCriterion(
                    name="Emergency Visit",
                    visit_types=[VisitType.EMERGENCY]
                )
            ),
        ]

        for criterion in default_criteria:
            self._criteria_library[criterion.id] = criterion

    def _init_demo_cohorts(self):
        """Initialize demo cohorts for testing."""
        demo_cohorts = [
            CohortDefinition(
                name="Diabetic Adults",
                description="Adults 18+ with Type 2 Diabetes",
                status=CohortStatus.ACTIVE,
                tags=["diabetes", "chronic-disease"],
                criteria=[
                    DemographicCriterion(
                        name="Adults",
                        age_range=AgeRange(min_age=18)
                    ),
                    ConditionCriterion(
                        name="Type 2 Diabetes",
                        codes=[
                            CodeEntry(code="E11", display="Type 2 diabetes mellitus"),
                        ],
                        code_system="ICD10CM"
                    )
                ]
            ),
            CohortDefinition(
                name="Heart Failure with Hospitalization",
                description="Patients with heart failure who had an inpatient stay",
                status=CohortStatus.ACTIVE,
                tags=["cardiology", "hospitalization"],
                criteria=[
                    ConditionCriterion(
                        name="Heart Failure",
                        codes=[
                            CodeEntry(code="I50", display="Heart failure"),
                        ],
                        code_system="ICD10CM"
                    ),
                    VisitCriterion(
                        name="Inpatient Stay",
                        visit_types=[VisitType.INPATIENT]
                    )
                ]
            ),
            CohortDefinition(
                name="Uncontrolled Diabetes",
                description="Diabetic patients with HbA1c >= 9.0%",
                status=CohortStatus.DRAFT,
                tags=["diabetes", "quality"],
                criteria=[
                    ConditionCriterion(
                        name="Diabetes",
                        codes=[
                            CodeEntry(code="E11", display="Type 2 diabetes mellitus"),
                            CodeEntry(code="E10", display="Type 1 diabetes mellitus"),
                        ],
                        code_system="ICD10CM"
                    ),
                    MeasurementCriterion(
                        name="Poor HbA1c",
                        codes=[
                            CodeEntry(code="4548-4", display="Hemoglobin A1c"),
                        ],
                        code_system="LOINC",
                        value_range=NumericRange(min_value=9.0)
                    )
                ]
            ),
        ]

        for cohort in demo_cohorts:
            self._cohorts[cohort.id] = cohort
            self._versions[cohort.id] = [
                CohortVersion(
                    version=cohort.version,
                    created_at=cohort.created_at,
                    created_by=cohort.created_by,
                    changes="Initial creation",
                    definition_snapshot=cohort.model_dump()
                )
            ]

    # ==========================================================================
    # CRUD Operations
    # ==========================================================================

    def list_cohorts(
        self,
        status: CohortStatus | None = None,
        search: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[list[CohortDefinition], int]:
        """List all cohort definitions with filtering."""
        cohorts = list(self._cohorts.values())

        if status:
            cohorts = [c for c in cohorts if c.status == status]

        if search:
            search_lower = search.lower()
            cohorts = [
                c for c in cohorts
                if search_lower in c.name.lower()
                or (c.description and search_lower in c.description.lower())
            ]

        if tags:
            cohorts = [c for c in cohorts if any(t in c.tags for t in tags)]

        # Sort by updated_at descending
        cohorts.sort(key=lambda c: c.updated_at, reverse=True)

        total = len(cohorts)
        cohorts = cohorts[offset:offset + limit]

        return cohorts, total

    def get_cohort(self, cohort_id: str) -> CohortDefinition | None:
        """Get a cohort by ID."""
        return self._cohorts.get(cohort_id)

    def create_cohort(self, create: CohortDefinitionCreate, created_by: str | None = None) -> CohortDefinition:
        """Create a new cohort definition."""
        cohort = CohortDefinition(
            name=create.name,
            description=create.description,
            criteria=create.criteria,
            root_operator=create.root_operator,
            tags=create.tags,
            created_by=created_by
        )

        self._cohorts[cohort.id] = cohort
        self._versions[cohort.id] = [
            CohortVersion(
                version=cohort.version,
                created_at=cohort.created_at,
                created_by=created_by,
                changes="Initial creation",
                definition_snapshot=cohort.model_dump()
            )
        ]

        logger.info(f"Created cohort: {cohort.id} - {cohort.name}")
        return cohort

    def update_cohort(
        self,
        cohort_id: str,
        update: CohortDefinitionUpdate,
        updated_by: str | None = None
    ) -> CohortDefinition | None:
        """Update an existing cohort definition."""
        cohort = self._cohorts.get(cohort_id)
        if not cohort:
            return None

        changes = []

        if update.name is not None:
            cohort.name = update.name
            changes.append("name")

        if update.description is not None:
            cohort.description = update.description
            changes.append("description")

        if update.criteria is not None:
            cohort.criteria = update.criteria
            changes.append("criteria")

        if update.root_operator is not None:
            cohort.root_operator = update.root_operator
            changes.append("root_operator")

        if update.status is not None:
            cohort.status = update.status
            changes.append("status")

        if update.tags is not None:
            cohort.tags = update.tags
            changes.append("tags")

        # Increment version if criteria changed
        if "criteria" in changes or "root_operator" in changes:
            parts = cohort.version.split(".")
            parts[-1] = str(int(parts[-1]) + 1)
            cohort.version = ".".join(parts)

        cohort.updated_at = datetime.now(timezone.utc)

        # Save version history
        self._versions.setdefault(cohort_id, []).append(
            CohortVersion(
                version=cohort.version,
                created_at=cohort.updated_at,
                created_by=updated_by,
                changes=f"Updated: {', '.join(changes)}",
                definition_snapshot=cohort.model_dump()
            )
        )

        logger.info(f"Updated cohort: {cohort_id} - {changes}")
        return cohort

    def delete_cohort(self, cohort_id: str) -> bool:
        """Delete a cohort definition."""
        if cohort_id in self._cohorts:
            del self._cohorts[cohort_id]
            self._versions.pop(cohort_id, None)
            logger.info(f"Deleted cohort: {cohort_id}")
            return True
        return False

    def get_cohort_versions(self, cohort_id: str) -> list[CohortVersion]:
        """Get version history for a cohort."""
        return self._versions.get(cohort_id, [])

    # ==========================================================================
    # Execution
    # ==========================================================================

    def get_patient_count(self, cohort_id: str) -> CohortCountResult | None:
        """Get patient count for a cohort (mock implementation)."""
        import random
        import time

        cohort = self._cohorts.get(cohort_id)
        if not cohort:
            return None

        start_time = time.perf_counter()

        # Mock patient count based on criteria complexity
        base_count = 10000
        for criterion in cohort.criteria:
            if isinstance(criterion, DemographicCriterion):
                if criterion.age_range:
                    base_count = int(base_count * 0.3)
                if criterion.genders:
                    base_count = int(base_count * 0.5)
            elif isinstance(criterion, ConditionCriterion):
                base_count = int(base_count * 0.15)
            elif isinstance(criterion, DrugCriterion):
                base_count = int(base_count * 0.2)
            elif isinstance(criterion, MeasurementCriterion):
                base_count = int(base_count * 0.25)
            elif isinstance(criterion, VisitCriterion):
                base_count = int(base_count * 0.4)

        # Add some randomness
        count = max(0, base_count + random.randint(-100, 100))

        execution_time = (time.perf_counter() - start_time) * 1000

        return CohortCountResult(
            cohort_id=cohort_id,
            count=count,
            execution_time_ms=execution_time,
            sql_query=cohort.to_count_sql(),
            cached=False
        )

    def execute_cohort(
        self,
        cohort_id: str,
        page: int = 1,
        page_size: int = 100
    ) -> PatientListResult | None:
        """Execute cohort and get patient list (mock implementation)."""
        import random
        import time

        cohort = self._cohorts.get(cohort_id)
        if not cohort:
            return None

        start_time = time.perf_counter()

        # Get total count
        count_result = self.get_patient_count(cohort_id)
        total_count = count_result.count if count_result else 0

        # Generate mock patient IDs
        offset = (page - 1) * page_size
        patient_ids = list(range(1000 + offset, min(1000 + offset + page_size, 1000 + total_count)))

        execution_time = (time.perf_counter() - start_time) * 1000

        return PatientListResult(
            cohort_id=cohort_id,
            patient_ids=patient_ids,
            total_count=total_count,
            page=page,
            page_size=page_size,
            execution_time_ms=execution_time
        )

    def get_demographics(self, cohort_id: str) -> DemographicBreakdown | None:
        """Get demographic breakdown for a cohort (mock implementation)."""
        import random

        cohort = self._cohorts.get(cohort_id)
        if not cohort:
            return None

        count_result = self.get_patient_count(cohort_id)
        total = count_result.count if count_result else 0

        # Mock demographic distributions
        return DemographicBreakdown(
            total_patients=total,
            by_gender={
                "Male": int(total * 0.48),
                "Female": int(total * 0.51),
                "Other": int(total * 0.01),
            },
            by_race={
                "White": int(total * 0.60),
                "Black": int(total * 0.18),
                "Asian": int(total * 0.08),
                "Hispanic": int(total * 0.10),
                "Other": int(total * 0.04),
            },
            by_ethnicity={
                "Hispanic": int(total * 0.18),
                "Not Hispanic": int(total * 0.78),
                "Unknown": int(total * 0.04),
            },
            by_age_group={
                "18-29": int(total * 0.15),
                "30-44": int(total * 0.25),
                "45-59": int(total * 0.30),
                "60-74": int(total * 0.20),
                "75+": int(total * 0.10),
            },
            mean_age=52.3 + random.uniform(-5, 5),
            median_age=54.0 + random.uniform(-5, 5),
        )

    def compare_cohorts(
        self,
        cohort_a_id: str,
        cohort_b_id: str
    ) -> CohortComparisonResult | None:
        """Compare two cohorts (mock implementation)."""
        import random

        cohort_a = self._cohorts.get(cohort_a_id)
        cohort_b = self._cohorts.get(cohort_b_id)

        if not cohort_a or not cohort_b:
            return None

        count_a = self.get_patient_count(cohort_a_id)
        count_b = self.get_patient_count(cohort_b_id)

        if not count_a or not count_b:
            return None

        # Calculate overlap (mock)
        smaller_count = min(count_a.count, count_b.count)
        overlap = int(smaller_count * random.uniform(0.1, 0.4))

        demographics_a = self.get_demographics(cohort_a_id)
        demographics_b = self.get_demographics(cohort_b_id)

        # Mock top conditions
        top_conditions_a = [
            ConditionPrevalence(
                condition_code="E11",
                condition_name="Type 2 Diabetes",
                patient_count=int(count_a.count * 0.45),
                prevalence_percent=45.0
            ),
            ConditionPrevalence(
                condition_code="I10",
                condition_name="Essential Hypertension",
                patient_count=int(count_a.count * 0.38),
                prevalence_percent=38.0
            ),
            ConditionPrevalence(
                condition_code="E78.5",
                condition_name="Hyperlipidemia",
                patient_count=int(count_a.count * 0.32),
                prevalence_percent=32.0
            ),
        ]

        top_conditions_b = [
            ConditionPrevalence(
                condition_code="I10",
                condition_name="Essential Hypertension",
                patient_count=int(count_b.count * 0.52),
                prevalence_percent=52.0
            ),
            ConditionPrevalence(
                condition_code="E11",
                condition_name="Type 2 Diabetes",
                patient_count=int(count_b.count * 0.28),
                prevalence_percent=28.0
            ),
            ConditionPrevalence(
                condition_code="J44.9",
                condition_name="COPD",
                patient_count=int(count_b.count * 0.18),
                prevalence_percent=18.0
            ),
        ]

        # Mock top drugs
        top_drugs_a = [
            DrugUtilization(
                drug_code="6809",
                drug_name="Metformin",
                patient_count=int(count_a.count * 0.42),
                utilization_percent=42.0
            ),
            DrugUtilization(
                drug_code="29046",
                drug_name="Lisinopril",
                patient_count=int(count_a.count * 0.35),
                utilization_percent=35.0
            ),
        ]

        top_drugs_b = [
            DrugUtilization(
                drug_code="29046",
                drug_name="Lisinopril",
                patient_count=int(count_b.count * 0.48),
                utilization_percent=48.0
            ),
            DrugUtilization(
                drug_code="36567",
                drug_name="Amlodipine",
                patient_count=int(count_b.count * 0.32),
                utilization_percent=32.0
            ),
        ]

        return CohortComparisonResult(
            cohort_a_id=cohort_a_id,
            cohort_b_id=cohort_b_id,
            cohort_a_count=count_a.count,
            cohort_b_count=count_b.count,
            overlap_count=overlap,
            cohort_a_only_count=count_a.count - overlap,
            cohort_b_only_count=count_b.count - overlap,
            demographics_a=demographics_a,
            demographics_b=demographics_b,
            top_conditions_a=top_conditions_a,
            top_conditions_b=top_conditions_b,
            top_drugs_a=top_drugs_a,
            top_drugs_b=top_drugs_b,
        )

    # ==========================================================================
    # Export
    # ==========================================================================

    def export_cohort(
        self,
        cohort_id: str,
        format: Literal["json", "sql"] = "json"
    ) -> dict[str, Any] | str | None:
        """Export cohort definition."""
        cohort = self._cohorts.get(cohort_id)
        if not cohort:
            return None

        if format == "json":
            return cohort.model_dump()
        elif format == "sql":
            return cohort.to_sql()

        return None

    # ==========================================================================
    # Criteria Library
    # ==========================================================================

    def list_criteria_library(
        self,
        category: str | None = None,
        search: str | None = None
    ) -> list[SavedCriterion]:
        """List saved criteria from the library."""
        criteria = list(self._criteria_library.values())

        if category:
            criteria = [c for c in criteria if c.category == category]

        if search:
            search_lower = search.lower()
            criteria = [
                c for c in criteria
                if search_lower in c.name.lower()
                or (c.description and search_lower in c.description.lower())
            ]

        # Sort by usage count descending
        criteria.sort(key=lambda c: c.usage_count, reverse=True)

        return criteria

    def get_criteria_categories(self) -> list[str]:
        """Get list of unique criteria categories."""
        categories = set(c.category for c in self._criteria_library.values())
        return sorted(list(categories))

    def save_criterion_to_library(
        self,
        criterion: AnyCriterion,
        name: str,
        description: str | None = None,
        category: str = "Custom",
        created_by: str | None = None
    ) -> SavedCriterion:
        """Save a criterion to the library."""
        saved = SavedCriterion(
            name=name,
            description=description,
            category=category,
            criterion=criterion,
            created_by=created_by
        )

        self._criteria_library[saved.id] = saved
        logger.info(f"Saved criterion to library: {saved.id} - {saved.name}")

        return saved

    def get_criterion_from_library(self, criterion_id: str) -> SavedCriterion | None:
        """Get a saved criterion from the library."""
        criterion = self._criteria_library.get(criterion_id)
        if criterion:
            criterion.usage_count += 1
        return criterion

    def delete_criterion_from_library(self, criterion_id: str) -> bool:
        """Delete a criterion from the library."""
        if criterion_id in self._criteria_library:
            del self._criteria_library[criterion_id]
            return True
        return False

    # ==========================================================================
    # Statistics
    # ==========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        cohorts_by_status = {}
        for cohort in self._cohorts.values():
            status = cohort.status.value
            cohorts_by_status[status] = cohorts_by_status.get(status, 0) + 1

        return {
            "total_cohorts": len(self._cohorts),
            "cohorts_by_status": cohorts_by_status,
            "total_saved_criteria": len(self._criteria_library),
            "criteria_categories": len(self.get_criteria_categories()),
        }


# ==============================================================================
# Singleton Instance
# ==============================================================================

_cohort_service: CohortService | None = None
_cohort_lock = threading.Lock()


def get_cohort_service() -> CohortService:
    """Get singleton cohort service instance."""
    global _cohort_service
    # VP-ThreadSafety: Double-checked locking for thread safety
    if _cohort_service is None:
        with _cohort_lock:
            if _cohort_service is None:
                _cohort_service = CohortService()
                logger.info("Initialized CohortService")
    return _cohort_service
