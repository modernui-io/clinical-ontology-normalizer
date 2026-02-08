"""OHDSI Data Quality Dashboard (DQD) check service.

CDO-3: Implements a subset of OHDSI DQD checks adapted for the platform's
OMOP-aligned clinical facts. Covers three standard DQD categories:

- Completeness: Are expected data elements populated?
- Conformance: Do values conform to expected formats and valid concept IDs?
- Plausibility: Are values clinically plausible?

Each check queries the ClinicalFact table (and optionally the Concept table)
using async SQLAlchemy and returns structured results.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical_fact import ClinicalFact
from app.models.vocabulary import Concept
from app.schemas.base import Domain
from app.schemas.dqd import (
    DQDCategory,
    DQDCheckDefinition,
    DQDCheckResult,
    DQDFailingExample,
    DQDReport,
    DQDStatus,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Check Definitions
# =============================================================================

CHECK_DEFINITIONS: list[DQDCheckDefinition] = [
    # --- Completeness Checks ---
    DQDCheckDefinition(
        check_id="COMP-001",
        name="patients_with_condition",
        category=DQDCategory.COMPLETENESS,
        description="Percentage of patients with at least one condition fact",
        threshold=0.80,
        warn_threshold=0.60,
    ),
    DQDCheckDefinition(
        check_id="COMP-002",
        name="patients_with_measurement",
        category=DQDCategory.COMPLETENESS,
        description="Percentage of patients with at least one measurement fact",
        threshold=0.70,
        warn_threshold=0.50,
    ),
    DQDCheckDefinition(
        check_id="COMP-003",
        name="patients_with_demographics",
        category=DQDCategory.COMPLETENESS,
        description="Percentage of patients with demographic data (DOB or sex recorded as observations)",
        threshold=0.90,
        warn_threshold=0.70,
    ),
    DQDCheckDefinition(
        check_id="COMP-004",
        name="facts_with_valid_concept_id",
        category=DQDCategory.COMPLETENESS,
        description="Percentage of clinical facts with a valid (non-zero) OMOP concept ID",
        threshold=0.95,
        warn_threshold=0.85,
    ),
    # --- Conformance Checks ---
    DQDCheckDefinition(
        check_id="CONF-001",
        name="concept_ids_reference_valid_concepts",
        category=DQDCategory.CONFORMANCE,
        description="All non-zero concept IDs reference entries in the concepts table",
        threshold=0.95,
        warn_threshold=0.85,
    ),
    DQDCheckDefinition(
        check_id="CONF-002",
        name="valid_date_ranges",
        category=DQDCategory.CONFORMANCE,
        description="start_date is before or equal to end_date when both are present",
        threshold=0.99,
        warn_threshold=0.95,
    ),
    DQDCheckDefinition(
        check_id="CONF-003",
        name="required_fields_populated",
        category=DQDCategory.CONFORMANCE,
        description="Required fields (patient_id, domain, concept_name) are populated on all facts",
        threshold=1.0,
        warn_threshold=0.99,
    ),
    DQDCheckDefinition(
        check_id="CONF-004",
        name="values_within_plausible_ranges",
        category=DQDCategory.CONFORMANCE,
        description="Numeric measurement values are within plausible clinical ranges (e.g. HbA1c 2-20%)",
        threshold=0.95,
        warn_threshold=0.85,
    ),
    # --- Plausibility Checks ---
    DQDCheckDefinition(
        check_id="PLAUS-001",
        name="no_future_dates",
        category=DQDCategory.PLAUSIBILITY,
        description="No clinical fact start_dates are in the future",
        threshold=0.99,
        warn_threshold=0.95,
    ),
    DQDCheckDefinition(
        check_id="PLAUS-002",
        name="temporal_ordering",
        category=DQDCategory.PLAUSIBILITY,
        description="For conditions with start and end dates, start is before end (temporal ordering)",
        threshold=0.99,
        warn_threshold=0.95,
    ),
    DQDCheckDefinition(
        check_id="PLAUS-003",
        name="age_appropriate_conditions",
        category=DQDCategory.PLAUSIBILITY,
        description="Age-appropriate conditions (pediatric conditions appear in younger patients)",
        threshold=0.95,
        warn_threshold=0.85,
    ),
    DQDCheckDefinition(
        check_id="PLAUS-004",
        name="gender_appropriate_conditions",
        category=DQDCategory.PLAUSIBILITY,
        description="Gender-appropriate conditions (e.g. prostate conditions in male patients)",
        threshold=0.95,
        warn_threshold=0.85,
    ),
]

_DEFINITIONS_BY_ID: dict[str, DQDCheckDefinition] = {d.check_id: d for d in CHECK_DEFINITIONS}

# Plausible measurement ranges: concept_name_substring -> (min, max)
PLAUSIBLE_RANGES: dict[str, tuple[float, float]] = {
    "hba1c": (2.0, 20.0),
    "hemoglobin a1c": (2.0, 20.0),
    "glucose": (10.0, 1000.0),
    "blood glucose": (10.0, 1000.0),
    "systolic": (40.0, 300.0),
    "diastolic": (20.0, 200.0),
    "heart rate": (20.0, 300.0),
    "temperature": (85.0, 115.0),  # Fahrenheit
    "body temperature": (85.0, 115.0),
    "bmi": (5.0, 100.0),
    "body mass index": (5.0, 100.0),
    "creatinine": (0.1, 30.0),
    "potassium": (1.0, 10.0),
    "sodium": (100.0, 200.0),
    "white blood cell": (0.1, 200.0),
    "wbc": (0.1, 200.0),
    "hemoglobin": (1.0, 25.0),
    "platelet": (5.0, 2000.0),
    "alt": (1.0, 10000.0),
    "ast": (1.0, 10000.0),
    "ldl": (10.0, 500.0),
    "hdl": (5.0, 200.0),
    "total cholesterol": (50.0, 600.0),
    "triglycerides": (10.0, 5000.0),
    "egfr": (1.0, 200.0),
}

# Gender-specific conditions (concept_name substrings -> required gender observation)
MALE_ONLY_CONDITIONS = [
    "prostate",
    "testicular",
    "erectile",
    "benign prostatic",
]

FEMALE_ONLY_CONDITIONS = [
    "ovarian",
    "cervical cancer",
    "endometrial",
    "uterine",
    "pregnancy",
    "preeclampsia",
    "eclampsia",
]

# Pediatric conditions (concept_name substrings)
PEDIATRIC_CONDITIONS = [
    "neonatal",
    "congenital",
    "infantile",
    "pediatric",
    "childhood",
]


def _determine_status(
    pass_rate: float, threshold: float, warn_threshold: float
) -> DQDStatus:
    """Determine check status based on pass rate and thresholds."""
    if pass_rate >= threshold:
        return DQDStatus.PASS
    if pass_rate >= warn_threshold:
        return DQDStatus.WARN
    return DQDStatus.FAIL


# =============================================================================
# Service Class
# =============================================================================


class DQDCheckService:
    """Service for running OHDSI DQD checks against ClinicalFact data."""

    def get_check_definitions(self) -> list[DQDCheckDefinition]:
        """Return all available check definitions."""
        return list(CHECK_DEFINITIONS)

    async def run_check(
        self, check_id: str, session: AsyncSession
    ) -> DQDCheckResult:
        """Run a single check by ID.

        Args:
            check_id: The check identifier (e.g. 'COMP-001')
            session: Async database session

        Returns:
            DQDCheckResult with pass/fail counts and status

        Raises:
            ValueError: If check_id is not recognized
        """
        definition = _DEFINITIONS_BY_ID.get(check_id)
        if definition is None:
            raise ValueError(f"Unknown check ID: {check_id}")

        check_fn = _CHECK_FUNCTIONS.get(check_id)
        if check_fn is None:
            raise ValueError(f"No implementation for check ID: {check_id}")

        return await check_fn(session, definition)

    async def run_all_checks(self, session: AsyncSession) -> DQDReport:
        """Run all DQD checks and return a full report.

        Args:
            session: Async database session

        Returns:
            DQDReport with all check results and overall score
        """
        results: list[DQDCheckResult] = []

        for definition in CHECK_DEFINITIONS:
            check_fn = _CHECK_FUNCTIONS.get(definition.check_id)
            if check_fn is None:
                logger.warning("No implementation for check %s", definition.check_id)
                continue
            try:
                result = await check_fn(session, definition)
                results.append(result)
            except Exception:
                logger.exception("Error running check %s", definition.check_id)
                # Record a failing result for errored checks
                results.append(
                    DQDCheckResult(
                        check_id=definition.check_id,
                        check_name=definition.name,
                        category=definition.category,
                        description=definition.description,
                        passed=0,
                        failed=0,
                        total=0,
                        pass_rate=0.0,
                        threshold=definition.threshold,
                        status=DQDStatus.FAIL,
                        failing_examples=[
                            DQDFailingExample(reason="Check execution error")
                        ],
                    )
                )

        passed_count = sum(1 for r in results if r.status == DQDStatus.PASS)
        warned_count = sum(1 for r in results if r.status == DQDStatus.WARN)
        failed_count = sum(1 for r in results if r.status == DQDStatus.FAIL)
        total = len(results)
        overall_score = passed_count / total if total > 0 else 0.0

        return DQDReport(
            timestamp=datetime.now(timezone.utc),
            total_checks=total,
            passed=passed_count,
            warned=warned_count,
            failed=failed_count,
            results=results,
            overall_score=round(overall_score, 4),
        )


# =============================================================================
# Check Implementations
# =============================================================================


async def _check_patients_with_condition(
    session: AsyncSession, definition: DQDCheckDefinition
) -> DQDCheckResult:
    """COMP-001: % of patients with at least one condition."""
    # Total distinct patients
    total_q = select(func.count(distinct(ClinicalFact.patient_id)))
    total_result = await session.execute(total_q)
    total_patients = total_result.scalar() or 0

    # Patients with at least one condition
    with_condition_q = select(
        func.count(distinct(ClinicalFact.patient_id))
    ).where(ClinicalFact.domain == Domain.CONDITION)
    with_cond_result = await session.execute(with_condition_q)
    patients_with_condition = with_cond_result.scalar() or 0

    passed = patients_with_condition
    failed = total_patients - patients_with_condition
    pass_rate = passed / total_patients if total_patients > 0 else 1.0

    examples: list[DQDFailingExample] = []
    if failed > 0:
        # Get sample of patients without conditions
        patients_with_cond_subq = (
            select(ClinicalFact.patient_id)
            .where(ClinicalFact.domain == Domain.CONDITION)
            .distinct()
        )
        missing_q = (
            select(distinct(ClinicalFact.patient_id))
            .where(ClinicalFact.patient_id.notin_(patients_with_cond_subq))
            .limit(5)
        )
        missing_result = await session.execute(missing_q)
        for row in missing_result:
            examples.append(
                DQDFailingExample(
                    patient_id=row[0],
                    reason="Patient has no condition facts",
                )
            )

    return DQDCheckResult(
        check_id=definition.check_id,
        check_name=definition.name,
        category=definition.category,
        description=definition.description,
        passed=passed,
        failed=failed,
        total=total_patients,
        pass_rate=round(pass_rate, 4),
        threshold=definition.threshold,
        status=_determine_status(pass_rate, definition.threshold, definition.warn_threshold),
        failing_examples=examples,
    )


async def _check_patients_with_measurement(
    session: AsyncSession, definition: DQDCheckDefinition
) -> DQDCheckResult:
    """COMP-002: % of patients with at least one measurement."""
    total_q = select(func.count(distinct(ClinicalFact.patient_id)))
    total_result = await session.execute(total_q)
    total_patients = total_result.scalar() or 0

    with_meas_q = select(
        func.count(distinct(ClinicalFact.patient_id))
    ).where(ClinicalFact.domain == Domain.MEASUREMENT)
    with_meas_result = await session.execute(with_meas_q)
    patients_with_meas = with_meas_result.scalar() or 0

    passed = patients_with_meas
    failed = total_patients - patients_with_meas
    pass_rate = passed / total_patients if total_patients > 0 else 1.0

    examples: list[DQDFailingExample] = []
    if failed > 0:
        patients_with_meas_subq = (
            select(ClinicalFact.patient_id)
            .where(ClinicalFact.domain == Domain.MEASUREMENT)
            .distinct()
        )
        missing_q = (
            select(distinct(ClinicalFact.patient_id))
            .where(ClinicalFact.patient_id.notin_(patients_with_meas_subq))
            .limit(5)
        )
        missing_result = await session.execute(missing_q)
        for row in missing_result:
            examples.append(
                DQDFailingExample(
                    patient_id=row[0],
                    reason="Patient has no measurement facts",
                )
            )

    return DQDCheckResult(
        check_id=definition.check_id,
        check_name=definition.name,
        category=definition.category,
        description=definition.description,
        passed=passed,
        failed=failed,
        total=total_patients,
        pass_rate=round(pass_rate, 4),
        threshold=definition.threshold,
        status=_determine_status(pass_rate, definition.threshold, definition.warn_threshold),
        failing_examples=examples,
    )


async def _check_patients_with_demographics(
    session: AsyncSession, definition: DQDCheckDefinition
) -> DQDCheckResult:
    """COMP-003: % of patients with demographic data.

    Demographics are stored as observation-domain clinical facts with
    concept_name containing 'date of birth', 'dob', 'sex', 'gender', or 'age'.
    """
    total_q = select(func.count(distinct(ClinicalFact.patient_id)))
    total_result = await session.execute(total_q)
    total_patients = total_result.scalar() or 0

    demographic_keywords = ["date of birth", "dob", "sex", "gender", "age", "birth"]
    # Build OR conditions for demographic concept names
    conditions = []
    for kw in demographic_keywords:
        conditions.append(func.lower(ClinicalFact.concept_name).like(f"%{kw}%"))

    with_demo_q = select(
        func.count(distinct(ClinicalFact.patient_id))
    ).where(or_(*conditions))
    with_demo_result = await session.execute(with_demo_q)
    patients_with_demo = with_demo_result.scalar() or 0

    passed = patients_with_demo
    failed = total_patients - patients_with_demo
    pass_rate = passed / total_patients if total_patients > 0 else 1.0

    return DQDCheckResult(
        check_id=definition.check_id,
        check_name=definition.name,
        category=definition.category,
        description=definition.description,
        passed=passed,
        failed=failed,
        total=total_patients,
        pass_rate=round(pass_rate, 4),
        threshold=definition.threshold,
        status=_determine_status(pass_rate, definition.threshold, definition.warn_threshold),
    )


async def _check_facts_with_valid_concept_id(
    session: AsyncSession, definition: DQDCheckDefinition
) -> DQDCheckResult:
    """COMP-004: % of facts with a valid (non-zero) OMOP concept ID."""
    total_q = select(func.count(ClinicalFact.id))
    total_result = await session.execute(total_q)
    total_facts = total_result.scalar() or 0

    valid_q = select(func.count(ClinicalFact.id)).where(
        ClinicalFact.omop_concept_id != 0
    )
    valid_result = await session.execute(valid_q)
    valid_count = valid_result.scalar() or 0

    passed = valid_count
    failed = total_facts - valid_count
    pass_rate = passed / total_facts if total_facts > 0 else 1.0

    examples: list[DQDFailingExample] = []
    if failed > 0:
        bad_q = (
            select(ClinicalFact.id, ClinicalFact.patient_id, ClinicalFact.concept_name)
            .where(ClinicalFact.omop_concept_id == 0)
            .limit(5)
        )
        bad_result = await session.execute(bad_q)
        for row in bad_result:
            examples.append(
                DQDFailingExample(
                    record_id=str(row[0]),
                    patient_id=str(row[1]),
                    field="omop_concept_id",
                    value="0",
                    reason="OMOP concept ID is 0 (unmapped)",
                )
            )

    return DQDCheckResult(
        check_id=definition.check_id,
        check_name=definition.name,
        category=definition.category,
        description=definition.description,
        passed=passed,
        failed=failed,
        total=total_facts,
        pass_rate=round(pass_rate, 4),
        threshold=definition.threshold,
        status=_determine_status(pass_rate, definition.threshold, definition.warn_threshold),
        failing_examples=examples,
    )


# --- Conformance Checks ---


async def _check_concept_ids_valid(
    session: AsyncSession, definition: DQDCheckDefinition
) -> DQDCheckResult:
    """CONF-001: All non-zero concept IDs reference valid OMOP concepts."""
    # Count facts with non-zero concept IDs
    nonzero_q = select(func.count(ClinicalFact.id)).where(
        ClinicalFact.omop_concept_id != 0
    )
    nonzero_result = await session.execute(nonzero_q)
    total_nonzero = nonzero_result.scalar() or 0

    if total_nonzero == 0:
        return DQDCheckResult(
            check_id=definition.check_id,
            check_name=definition.name,
            category=definition.category,
            description=definition.description,
            passed=0,
            failed=0,
            total=0,
            pass_rate=1.0,
            threshold=definition.threshold,
            status=DQDStatus.PASS,
        )

    # Count facts whose concept IDs exist in the concepts table
    valid_q = (
        select(func.count(ClinicalFact.id))
        .select_from(ClinicalFact)
        .join(
            Concept,
            ClinicalFact.omop_concept_id == Concept.concept_id,
        )
        .where(ClinicalFact.omop_concept_id != 0)
    )
    valid_result = await session.execute(valid_q)
    valid_count = valid_result.scalar() or 0

    passed = valid_count
    failed = total_nonzero - valid_count
    pass_rate = passed / total_nonzero if total_nonzero > 0 else 1.0

    examples: list[DQDFailingExample] = []
    if failed > 0:
        # Get concept IDs not in concepts table
        valid_concepts_subq = select(Concept.concept_id)
        bad_q = (
            select(
                ClinicalFact.id,
                ClinicalFact.patient_id,
                ClinicalFact.omop_concept_id,
            )
            .where(
                and_(
                    ClinicalFact.omop_concept_id != 0,
                    ClinicalFact.omop_concept_id.notin_(valid_concepts_subq),
                )
            )
            .limit(5)
        )
        bad_result = await session.execute(bad_q)
        for row in bad_result:
            examples.append(
                DQDFailingExample(
                    record_id=str(row[0]),
                    patient_id=str(row[1]),
                    field="omop_concept_id",
                    value=str(row[2]),
                    reason="Concept ID does not exist in concepts table",
                )
            )

    return DQDCheckResult(
        check_id=definition.check_id,
        check_name=definition.name,
        category=definition.category,
        description=definition.description,
        passed=passed,
        failed=failed,
        total=total_nonzero,
        pass_rate=round(pass_rate, 4),
        threshold=definition.threshold,
        status=_determine_status(pass_rate, definition.threshold, definition.warn_threshold),
        failing_examples=examples,
    )


async def _check_valid_date_ranges(
    session: AsyncSession, definition: DQDCheckDefinition
) -> DQDCheckResult:
    """CONF-002: start_date <= end_date when both are present."""
    # Facts with both start and end dates
    both_dates_q = select(func.count(ClinicalFact.id)).where(
        and_(
            ClinicalFact.start_date.isnot(None),
            ClinicalFact.end_date.isnot(None),
        )
    )
    both_result = await session.execute(both_dates_q)
    total_with_both = both_result.scalar() or 0

    if total_with_both == 0:
        return DQDCheckResult(
            check_id=definition.check_id,
            check_name=definition.name,
            category=definition.category,
            description=definition.description,
            passed=0,
            failed=0,
            total=0,
            pass_rate=1.0,
            threshold=definition.threshold,
            status=DQDStatus.PASS,
        )

    # Facts where start > end (invalid)
    invalid_q = select(func.count(ClinicalFact.id)).where(
        and_(
            ClinicalFact.start_date.isnot(None),
            ClinicalFact.end_date.isnot(None),
            ClinicalFact.start_date > ClinicalFact.end_date,
        )
    )
    invalid_result = await session.execute(invalid_q)
    invalid_count = invalid_result.scalar() or 0

    passed = total_with_both - invalid_count
    failed = invalid_count
    pass_rate = passed / total_with_both if total_with_both > 0 else 1.0

    examples: list[DQDFailingExample] = []
    if failed > 0:
        bad_q = (
            select(
                ClinicalFact.id,
                ClinicalFact.patient_id,
                ClinicalFact.start_date,
                ClinicalFact.end_date,
            )
            .where(
                and_(
                    ClinicalFact.start_date.isnot(None),
                    ClinicalFact.end_date.isnot(None),
                    ClinicalFact.start_date > ClinicalFact.end_date,
                )
            )
            .limit(5)
        )
        bad_result = await session.execute(bad_q)
        for row in bad_result:
            examples.append(
                DQDFailingExample(
                    record_id=str(row[0]),
                    patient_id=str(row[1]),
                    field="start_date/end_date",
                    value=f"{row[2]} > {row[3]}",
                    reason="start_date is after end_date",
                )
            )

    return DQDCheckResult(
        check_id=definition.check_id,
        check_name=definition.name,
        category=definition.category,
        description=definition.description,
        passed=passed,
        failed=failed,
        total=total_with_both,
        pass_rate=round(pass_rate, 4),
        threshold=definition.threshold,
        status=_determine_status(pass_rate, definition.threshold, definition.warn_threshold),
        failing_examples=examples,
    )


async def _check_required_fields(
    session: AsyncSession, definition: DQDCheckDefinition
) -> DQDCheckResult:
    """CONF-003: Required fields (patient_id, domain, concept_name) populated."""
    total_q = select(func.count(ClinicalFact.id))
    total_result = await session.execute(total_q)
    total_facts = total_result.scalar() or 0

    if total_facts == 0:
        return DQDCheckResult(
            check_id=definition.check_id,
            check_name=definition.name,
            category=definition.category,
            description=definition.description,
            passed=0,
            failed=0,
            total=0,
            pass_rate=1.0,
            threshold=definition.threshold,
            status=DQDStatus.PASS,
        )

    # Count facts missing required fields
    # patient_id and domain are NOT NULL in the schema, but concept_name could
    # theoretically be empty string
    missing_q = select(func.count(ClinicalFact.id)).where(
        or_(
            ClinicalFact.patient_id == "",
            ClinicalFact.patient_id.is_(None),
            ClinicalFact.concept_name == "",
            ClinicalFact.concept_name.is_(None),
        )
    )
    missing_result = await session.execute(missing_q)
    missing_count = missing_result.scalar() or 0

    passed = total_facts - missing_count
    failed = missing_count
    pass_rate = passed / total_facts if total_facts > 0 else 1.0

    examples: list[DQDFailingExample] = []
    if failed > 0:
        bad_q = (
            select(ClinicalFact.id, ClinicalFact.patient_id, ClinicalFact.concept_name)
            .where(
                or_(
                    ClinicalFact.patient_id == "",
                    ClinicalFact.patient_id.is_(None),
                    ClinicalFact.concept_name == "",
                    ClinicalFact.concept_name.is_(None),
                )
            )
            .limit(5)
        )
        bad_result = await session.execute(bad_q)
        for row in bad_result:
            missing_fields = []
            if not row[1]:
                missing_fields.append("patient_id")
            if not row[2]:
                missing_fields.append("concept_name")
            examples.append(
                DQDFailingExample(
                    record_id=str(row[0]),
                    field=", ".join(missing_fields),
                    reason=f"Missing required fields: {', '.join(missing_fields)}",
                )
            )

    return DQDCheckResult(
        check_id=definition.check_id,
        check_name=definition.name,
        category=definition.category,
        description=definition.description,
        passed=passed,
        failed=failed,
        total=total_facts,
        pass_rate=round(pass_rate, 4),
        threshold=definition.threshold,
        status=_determine_status(pass_rate, definition.threshold, definition.warn_threshold),
        failing_examples=examples,
    )


async def _check_values_in_range(
    session: AsyncSession, definition: DQDCheckDefinition
) -> DQDCheckResult:
    """CONF-004: Measurement values within plausible clinical ranges."""
    # Get all measurement facts with numeric values
    meas_q = select(
        ClinicalFact.id,
        ClinicalFact.patient_id,
        ClinicalFact.concept_name,
        ClinicalFact.value,
    ).where(
        and_(
            ClinicalFact.domain == Domain.MEASUREMENT,
            ClinicalFact.value.isnot(None),
            ClinicalFact.value != "",
        )
    )
    meas_result = await session.execute(meas_q)
    rows = meas_result.all()

    total = 0
    failed = 0
    examples: list[DQDFailingExample] = []

    for row in rows:
        fact_id, patient_id, concept_name, value_str = row
        concept_lower = (concept_name or "").lower()

        # Check if this measurement has a defined plausible range
        matched_range: tuple[float, float] | None = None
        for key, range_vals in PLAUSIBLE_RANGES.items():
            if key in concept_lower:
                matched_range = range_vals
                break

        if matched_range is None:
            # No range defined for this measurement type - skip
            continue

        total += 1
        try:
            numeric_val = float(value_str)
        except (ValueError, TypeError):
            # Non-numeric value for a measurement - count as failure
            failed += 1
            if len(examples) < 5:
                examples.append(
                    DQDFailingExample(
                        record_id=str(fact_id),
                        patient_id=str(patient_id),
                        field="value",
                        value=str(value_str),
                        reason=f"Non-numeric value for measurement '{concept_name}'",
                    )
                )
            continue

        min_val, max_val = matched_range
        if numeric_val < min_val or numeric_val > max_val:
            failed += 1
            if len(examples) < 5:
                examples.append(
                    DQDFailingExample(
                        record_id=str(fact_id),
                        patient_id=str(patient_id),
                        field="value",
                        value=str(value_str),
                        reason=f"Value {numeric_val} outside plausible range [{min_val}, {max_val}] for '{concept_name}'",
                    )
                )

    passed = total - failed
    pass_rate = passed / total if total > 0 else 1.0

    return DQDCheckResult(
        check_id=definition.check_id,
        check_name=definition.name,
        category=definition.category,
        description=definition.description,
        passed=passed,
        failed=failed,
        total=total,
        pass_rate=round(pass_rate, 4),
        threshold=definition.threshold,
        status=_determine_status(pass_rate, definition.threshold, definition.warn_threshold),
        failing_examples=examples,
    )


# --- Plausibility Checks ---


async def _check_no_future_dates(
    session: AsyncSession, definition: DQDCheckDefinition
) -> DQDCheckResult:
    """PLAUS-001: No clinical fact start_dates in the future."""
    now = datetime.now(timezone.utc)

    # Facts with start_date
    has_date_q = select(func.count(ClinicalFact.id)).where(
        ClinicalFact.start_date.isnot(None)
    )
    has_date_result = await session.execute(has_date_q)
    total_with_date = has_date_result.scalar() or 0

    if total_with_date == 0:
        return DQDCheckResult(
            check_id=definition.check_id,
            check_name=definition.name,
            category=definition.category,
            description=definition.description,
            passed=0,
            failed=0,
            total=0,
            pass_rate=1.0,
            threshold=definition.threshold,
            status=DQDStatus.PASS,
        )

    # Facts with future start_date
    future_q = select(func.count(ClinicalFact.id)).where(
        and_(
            ClinicalFact.start_date.isnot(None),
            ClinicalFact.start_date > now,
        )
    )
    future_result = await session.execute(future_q)
    future_count = future_result.scalar() or 0

    passed = total_with_date - future_count
    failed = future_count
    pass_rate = passed / total_with_date if total_with_date > 0 else 1.0

    examples: list[DQDFailingExample] = []
    if failed > 0:
        bad_q = (
            select(ClinicalFact.id, ClinicalFact.patient_id, ClinicalFact.start_date)
            .where(
                and_(
                    ClinicalFact.start_date.isnot(None),
                    ClinicalFact.start_date > now,
                )
            )
            .limit(5)
        )
        bad_result = await session.execute(bad_q)
        for row in bad_result:
            examples.append(
                DQDFailingExample(
                    record_id=str(row[0]),
                    patient_id=str(row[1]),
                    field="start_date",
                    value=str(row[2]),
                    reason="start_date is in the future",
                )
            )

    return DQDCheckResult(
        check_id=definition.check_id,
        check_name=definition.name,
        category=definition.category,
        description=definition.description,
        passed=passed,
        failed=failed,
        total=total_with_date,
        pass_rate=round(pass_rate, 4),
        threshold=definition.threshold,
        status=_determine_status(pass_rate, definition.threshold, definition.warn_threshold),
        failing_examples=examples,
    )


async def _check_temporal_ordering(
    session: AsyncSession, definition: DQDCheckDefinition
) -> DQDCheckResult:
    """PLAUS-002: Condition start dates before resolution (end) dates.

    Same logic as CONF-002 but specifically for condition-domain facts,
    checking clinical plausibility of temporal ordering.
    """
    both_dates_q = select(func.count(ClinicalFact.id)).where(
        and_(
            ClinicalFact.domain == Domain.CONDITION,
            ClinicalFact.start_date.isnot(None),
            ClinicalFact.end_date.isnot(None),
        )
    )
    both_result = await session.execute(both_dates_q)
    total = both_result.scalar() or 0

    if total == 0:
        return DQDCheckResult(
            check_id=definition.check_id,
            check_name=definition.name,
            category=definition.category,
            description=definition.description,
            passed=0,
            failed=0,
            total=0,
            pass_rate=1.0,
            threshold=definition.threshold,
            status=DQDStatus.PASS,
        )

    invalid_q = select(func.count(ClinicalFact.id)).where(
        and_(
            ClinicalFact.domain == Domain.CONDITION,
            ClinicalFact.start_date.isnot(None),
            ClinicalFact.end_date.isnot(None),
            ClinicalFact.start_date > ClinicalFact.end_date,
        )
    )
    invalid_result = await session.execute(invalid_q)
    invalid_count = invalid_result.scalar() or 0

    passed = total - invalid_count
    failed = invalid_count
    pass_rate = passed / total if total > 0 else 1.0

    examples: list[DQDFailingExample] = []
    if failed > 0:
        bad_q = (
            select(
                ClinicalFact.id,
                ClinicalFact.patient_id,
                ClinicalFact.concept_name,
                ClinicalFact.start_date,
                ClinicalFact.end_date,
            )
            .where(
                and_(
                    ClinicalFact.domain == Domain.CONDITION,
                    ClinicalFact.start_date.isnot(None),
                    ClinicalFact.end_date.isnot(None),
                    ClinicalFact.start_date > ClinicalFact.end_date,
                )
            )
            .limit(5)
        )
        bad_result = await session.execute(bad_q)
        for row in bad_result:
            examples.append(
                DQDFailingExample(
                    record_id=str(row[0]),
                    patient_id=str(row[1]),
                    field="start_date/end_date",
                    value=f"{row[3]} > {row[4]}",
                    reason=f"Condition '{row[2]}' resolved before it started",
                )
            )

    return DQDCheckResult(
        check_id=definition.check_id,
        check_name=definition.name,
        category=definition.category,
        description=definition.description,
        passed=passed,
        failed=failed,
        total=total,
        pass_rate=round(pass_rate, 4),
        threshold=definition.threshold,
        status=_determine_status(pass_rate, definition.threshold, definition.warn_threshold),
        failing_examples=examples,
    )


async def _check_age_appropriate_conditions(
    session: AsyncSession, definition: DQDCheckDefinition
) -> DQDCheckResult:
    """PLAUS-003: Age-appropriate conditions.

    Checks that pediatric-specific conditions only appear in patients who
    also have age/DOB observations indicating they are children (age < 18).
    This is a heuristic check since we don't have a dedicated patient table.
    """
    # Find all facts with pediatric condition keywords
    pediatric_conditions = []
    for kw in PEDIATRIC_CONDITIONS:
        pediatric_conditions.append(func.lower(ClinicalFact.concept_name).like(f"%{kw}%"))

    pediatric_q = select(
        ClinicalFact.id,
        ClinicalFact.patient_id,
        ClinicalFact.concept_name,
    ).where(
        and_(
            ClinicalFact.domain == Domain.CONDITION,
            or_(*pediatric_conditions),
        )
    )
    pediatric_result = await session.execute(pediatric_q)
    pediatric_rows = pediatric_result.all()

    total = len(pediatric_rows)
    if total == 0:
        return DQDCheckResult(
            check_id=definition.check_id,
            check_name=definition.name,
            category=definition.category,
            description=definition.description,
            passed=0,
            failed=0,
            total=0,
            pass_rate=1.0,
            threshold=definition.threshold,
            status=DQDStatus.PASS,
        )

    # For each patient with pediatric conditions, check if they have an age observation
    # We consider it a pass if there's an age < 18, or we can't determine age
    # (can't fail without evidence of adult age)
    failed = 0
    examples: list[DQDFailingExample] = []

    patient_ids = {row[1] for row in pediatric_rows}
    # Get age observations for these patients
    age_q = select(
        ClinicalFact.patient_id,
        ClinicalFact.value,
    ).where(
        and_(
            ClinicalFact.patient_id.in_(list(patient_ids)),
            func.lower(ClinicalFact.concept_name).like("%age%"),
            ClinicalFact.value.isnot(None),
        )
    )
    age_result = await session.execute(age_q)
    age_rows = age_result.all()

    # Build map of patient_id -> age
    patient_ages: dict[str, float | None] = {}
    for pid, val in age_rows:
        try:
            patient_ages[pid] = float(val)
        except (ValueError, TypeError):
            pass

    for fact_id, patient_id, concept_name in pediatric_rows:
        age = patient_ages.get(patient_id)
        if age is not None and age >= 18:
            failed += 1
            if len(examples) < 5:
                examples.append(
                    DQDFailingExample(
                        record_id=str(fact_id),
                        patient_id=patient_id,
                        field="concept_name",
                        value=concept_name,
                        reason=f"Pediatric condition '{concept_name}' in patient age {age}",
                    )
                )

    passed = total - failed
    pass_rate = passed / total if total > 0 else 1.0

    return DQDCheckResult(
        check_id=definition.check_id,
        check_name=definition.name,
        category=definition.category,
        description=definition.description,
        passed=passed,
        failed=failed,
        total=total,
        pass_rate=round(pass_rate, 4),
        threshold=definition.threshold,
        status=_determine_status(pass_rate, definition.threshold, definition.warn_threshold),
        failing_examples=examples,
    )


async def _check_gender_appropriate_conditions(
    session: AsyncSession, definition: DQDCheckDefinition
) -> DQDCheckResult:
    """PLAUS-004: Gender-appropriate conditions.

    Checks that gender-specific conditions appear only in the appropriate
    gender (e.g. prostate conditions only in male patients). Gender is
    determined from observation-domain facts.
    """
    # Build query for gender-specific conditions
    male_conds = [func.lower(ClinicalFact.concept_name).like(f"%{kw}%") for kw in MALE_ONLY_CONDITIONS]
    female_conds = [func.lower(ClinicalFact.concept_name).like(f"%{kw}%") for kw in FEMALE_ONLY_CONDITIONS]

    gender_q = select(
        ClinicalFact.id,
        ClinicalFact.patient_id,
        ClinicalFact.concept_name,
    ).where(
        and_(
            ClinicalFact.domain == Domain.CONDITION,
            or_(*(male_conds + female_conds)),
        )
    )
    gender_result = await session.execute(gender_q)
    gender_rows = gender_result.all()

    total = len(gender_rows)
    if total == 0:
        return DQDCheckResult(
            check_id=definition.check_id,
            check_name=definition.name,
            category=definition.category,
            description=definition.description,
            passed=0,
            failed=0,
            total=0,
            pass_rate=1.0,
            threshold=definition.threshold,
            status=DQDStatus.PASS,
        )

    # Get gender observations for relevant patients
    patient_ids = {row[1] for row in gender_rows}
    gender_obs_q = select(
        ClinicalFact.patient_id,
        ClinicalFact.value,
    ).where(
        and_(
            ClinicalFact.patient_id.in_(list(patient_ids)),
            or_(
                func.lower(ClinicalFact.concept_name).like("%sex%"),
                func.lower(ClinicalFact.concept_name).like("%gender%"),
            ),
            ClinicalFact.value.isnot(None),
        )
    )
    gender_obs_result = await session.execute(gender_obs_q)

    # Build map: patient_id -> gender_value (male/female)
    patient_genders: dict[str, str] = {}
    for pid, val in gender_obs_result:
        val_lower = (val or "").lower().strip()
        if val_lower in ("male", "m"):
            patient_genders[pid] = "male"
        elif val_lower in ("female", "f"):
            patient_genders[pid] = "female"

    failed = 0
    examples: list[DQDFailingExample] = []

    for fact_id, patient_id, concept_name in gender_rows:
        concept_lower = concept_name.lower()
        patient_gender = patient_genders.get(patient_id)

        if patient_gender is None:
            # Can't determine gender - pass by default
            continue

        is_male_condition = any(kw in concept_lower for kw in MALE_ONLY_CONDITIONS)
        is_female_condition = any(kw in concept_lower for kw in FEMALE_ONLY_CONDITIONS)

        if is_male_condition and patient_gender != "male":
            failed += 1
            if len(examples) < 5:
                examples.append(
                    DQDFailingExample(
                        record_id=str(fact_id),
                        patient_id=patient_id,
                        field="concept_name",
                        value=concept_name,
                        reason=f"Male-specific condition '{concept_name}' in {patient_gender} patient",
                    )
                )
        elif is_female_condition and patient_gender != "female":
            failed += 1
            if len(examples) < 5:
                examples.append(
                    DQDFailingExample(
                        record_id=str(fact_id),
                        patient_id=patient_id,
                        field="concept_name",
                        value=concept_name,
                        reason=f"Female-specific condition '{concept_name}' in {patient_gender} patient",
                    )
                )

    passed = total - failed
    pass_rate = passed / total if total > 0 else 1.0

    return DQDCheckResult(
        check_id=definition.check_id,
        check_name=definition.name,
        category=definition.category,
        description=definition.description,
        passed=passed,
        failed=failed,
        total=total,
        pass_rate=round(pass_rate, 4),
        threshold=definition.threshold,
        status=_determine_status(pass_rate, definition.threshold, definition.warn_threshold),
        failing_examples=examples,
    )


# =============================================================================
# Check Function Registry
# =============================================================================

_CHECK_FUNCTIONS = {
    "COMP-001": _check_patients_with_condition,
    "COMP-002": _check_patients_with_measurement,
    "COMP-003": _check_patients_with_demographics,
    "COMP-004": _check_facts_with_valid_concept_id,
    "CONF-001": _check_concept_ids_valid,
    "CONF-002": _check_valid_date_ranges,
    "CONF-003": _check_required_fields,
    "CONF-004": _check_values_in_range,
    "PLAUS-001": _check_no_future_dates,
    "PLAUS-002": _check_temporal_ordering,
    "PLAUS-003": _check_age_appropriate_conditions,
    "PLAUS-004": _check_gender_appropriate_conditions,
}
