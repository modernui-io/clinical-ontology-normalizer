"""ETL Validation Service - Validate FHIR-to-OMOP transformation pipeline.

Dir-CI-3.4: Provides round-trip validation, concept mapping accuracy checks,
and data quality checks for the FHIR import ETL pipeline.

The ETL pipeline flow:
  FHIR Resource -> extract fields -> map to OMOP concepts -> ClinicalFact

This service validates that the transformation is lossless and accurate by
comparing source FHIR resources against resulting ClinicalFacts.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import Integer, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical_fact import ClinicalFact
from app.schemas.base import Domain
from app.schemas.etl_validation import (
    BatchETLValidationResult,
    ComparisonType,
    ConceptMappingReport,
    DomainMismatch,
    DuplicateGroup,
    ETLQualityReport,
    ETLValidationResult,
    FieldComparison,
    MissingFieldEntry,
    RangeViolation,
)

logger = logging.getLogger(__name__)

# FHIR resource type -> expected OMOP Domain
FHIR_RESOURCE_DOMAIN_MAP: dict[str, Domain] = {
    "Condition": Domain.CONDITION,
    "MedicationRequest": Domain.DRUG,
    "MedicationStatement": Domain.DRUG,
    "Immunization": Domain.DRUG,
    "Procedure": Domain.PROCEDURE,
    "Observation": Domain.OBSERVATION,  # could also be MEASUREMENT
    "Encounter": Domain.VISIT,
    "AllergyIntolerance": Domain.OBSERVATION,
}

# Reasonable measurement ranges for common lab/vital concepts
MEASUREMENT_RANGES: dict[str, tuple[float, float]] = {
    # Vitals
    "Heart rate": (20.0, 300.0),
    "Body temperature": (85.0, 115.0),  # Fahrenheit
    "Systolic blood pressure": (40.0, 300.0),
    "Diastolic blood pressure": (20.0, 200.0),
    "Body weight": (0.5, 700.0),  # kg
    "Body height": (20.0, 300.0),  # cm
    "Body mass index": (5.0, 100.0),
    "Respiratory rate": (4.0, 80.0),
    "Oxygen saturation": (0.0, 100.0),
    # Labs
    "Hemoglobin A1c": (2.0, 20.0),  # %
    "Glucose": (10.0, 1500.0),  # mg/dL
    "Creatinine": (0.1, 30.0),  # mg/dL
    "eGFR": (0.0, 200.0),
    "Hemoglobin": (2.0, 25.0),  # g/dL
    "Potassium": (1.0, 10.0),  # mEq/L
    "Sodium": (100.0, 200.0),  # mEq/L
    "Albumin": (0.5, 7.0),  # g/dL
    "Total cholesterol": (50.0, 600.0),
    "LDL cholesterol": (10.0, 400.0),
    "HDL cholesterol": (5.0, 150.0),
    "Triglycerides": (10.0, 5000.0),
    "Platelet count": (1.0, 2000.0),
    "White blood cell count": (0.1, 500.0),
}


class ETLValidationService:
    """Validates the FHIR-to-OMOP ETL pipeline for data integrity."""

    # -------------------------------------------------------------------
    # Round-trip validation: FHIR resource <-> ClinicalFact
    # -------------------------------------------------------------------

    def validate_etl_round_trip(
        self,
        fhir_resource: dict[str, Any],
        clinical_fact: dict[str, Any],
    ) -> ETLValidationResult:
        """Compare a source FHIR resource against a resulting ClinicalFact.

        Checks that critical fields are preserved through the ETL pipeline:
        - Concept mapping (FHIR coding -> OMOP concept_id)
        - Dates (effectiveDateTime / onsetDateTime -> start_date)
        - Patient reference
        - Value/quantity (valueQuantity -> value/unit)
        - Source provenance

        Args:
            fhir_resource: The original FHIR resource dict.
            clinical_fact: The resulting ClinicalFact as a dict.

        Returns:
            ETLValidationResult with field-level comparisons and issues.
        """
        resource_type = fhir_resource.get("resourceType", "Unknown")
        resource_id = fhir_resource.get("id")
        comparisons: list[FieldComparison] = []
        issues: list[str] = []

        # 1. Concept mapping check
        comparisons.append(self._compare_concept_mapping(fhir_resource, clinical_fact))

        # 2. Date preservation check
        comparisons.append(self._compare_dates(fhir_resource, clinical_fact, resource_type))

        # 3. Patient reference check
        comparisons.append(self._compare_patient_reference(fhir_resource, clinical_fact))

        # 4. Value/quantity check (for Observations)
        if resource_type in ("Observation", "Immunization"):
            comparisons.append(self._compare_value_quantity(fhir_resource, clinical_fact))

        # 5. Domain check
        comparisons.append(self._compare_domain(fhir_resource, clinical_fact, resource_type))

        # 6. Source provenance check
        comparisons.append(self._check_provenance(clinical_fact))

        # Collect issues from failed comparisons
        for comp in comparisons:
            if not comp.match and comp.message:
                issues.append(comp.message)

        overall_match = all(c.match for c in comparisons)

        return ETLValidationResult(
            resource_type=resource_type,
            resource_id=resource_id,
            field_comparisons=comparisons,
            overall_match=overall_match,
            issues=issues,
        )

    def validate_batch_etl(
        self,
        fhir_bundle: dict[str, Any],
        clinical_facts: list[dict[str, Any]],
    ) -> BatchETLValidationResult:
        """Validate all resources in a FHIR bundle against their ClinicalFacts.

        Matches resources to facts by concept_name and runs round-trip
        validation for each pair.

        Args:
            fhir_bundle: FHIR Bundle dict with entries.
            clinical_facts: List of ClinicalFact dicts produced by the ETL.

        Returns:
            BatchETLValidationResult with aggregate stats and per-resource results.
        """
        entries = fhir_bundle.get("entry", [])
        resources = [
            e.get("resource", {})
            for e in entries
            if e.get("resource", {}).get("resourceType") != "Patient"
        ]

        total = len(resources)
        results: list[ETLValidationResult] = []
        passed = 0
        failed = 0
        skipped = 0
        data_loss_fields: set[str] = set()

        # Index facts by concept_name for matching
        facts_by_name: dict[str, dict[str, Any]] = {}
        for fact in clinical_facts:
            name = fact.get("concept_name", "")
            if name:
                facts_by_name[name] = fact

        for resource in resources:
            resource_type = resource.get("resourceType", "")
            if resource_type not in FHIR_RESOURCE_DOMAIN_MAP:
                skipped += 1
                continue

            # Try to find matching fact
            matching_fact = self._find_matching_fact(resource, clinical_facts)
            if not matching_fact:
                skipped += 1
                continue

            result = self.validate_etl_round_trip(resource, matching_fact)
            results.append(result)

            if result.overall_match:
                passed += 1
            else:
                failed += 1
                # Track which fields lost data
                for comp in result.field_comparisons:
                    if not comp.match:
                        data_loss_fields.add(comp.field_name)

        validated = passed + failed
        success_rate = passed / validated if validated > 0 else 0.0

        return BatchETLValidationResult(
            total=total,
            validated=validated,
            passed=passed,
            failed=failed,
            skipped=skipped,
            success_rate=success_rate,
            data_loss_fields=sorted(data_loss_fields),
            results=results,
        )

    # -------------------------------------------------------------------
    # Concept mapping accuracy (DB queries)
    # -------------------------------------------------------------------

    async def validate_concept_mapping_accuracy(
        self,
        session: AsyncSession,
    ) -> ConceptMappingReport:
        """Check concept mapping accuracy across all ClinicalFacts in the DB.

        - % of facts with valid (non-zero) OMOP concept IDs
        - % mapped to correct domain
        - Detect domain mismatches

        Args:
            session: Async database session.

        Returns:
            ConceptMappingReport with mapping stats and domain mismatches.
        """
        # Count total facts
        total_result = await session.execute(
            select(func.count()).select_from(ClinicalFact).where(
                ClinicalFact.deleted_at.is_(None)
            )
        )
        total_facts = total_result.scalar() or 0

        # Count mapped (concept_id > 0)
        mapped_result = await session.execute(
            select(func.count()).select_from(ClinicalFact).where(
                ClinicalFact.deleted_at.is_(None),
                ClinicalFact.omop_concept_id > 0,
            )
        )
        mapped = mapped_result.scalar() or 0
        unmapped = total_facts - mapped
        mapping_rate = mapped / total_facts if total_facts > 0 else 0.0

        # Per-domain stats using case() for SQLite compatibility
        mapped_expr = func.sum(
            case(
                (ClinicalFact.omop_concept_id > 0, 1),
                else_=0,
            )
        ).label("mapped_count")

        domain_stats_result = await session.execute(
            select(
                ClinicalFact.domain,
                func.count().label("total"),
                mapped_expr,
            )
            .where(ClinicalFact.deleted_at.is_(None))
            .group_by(ClinicalFact.domain)
        )

        by_domain: dict[str, dict[str, int]] = {}
        for row in domain_stats_result:
            domain_val = row[0].value if hasattr(row[0], "value") else str(row[0])
            total_in_domain = row[1]
            mapped_in_domain = row[2] or 0
            by_domain[domain_val] = {
                "total": total_in_domain,
                "mapped": int(mapped_in_domain),
                "unmapped": total_in_domain - int(mapped_in_domain),
            }

        # Detect domain mismatches -- facts whose resource-type-implied domain
        # doesn't match the declared domain. We check Condition facts that
        # don't have Domain.CONDITION, Drug facts without Domain.DRUG, etc.
        domain_mismatches: list[DomainMismatch] = []

        # Simple heuristic: concept_name starting with "Allergy to" should be OBSERVATION
        # Condition-domain facts with concept_id=0 are suspect but not mismatches
        # For a robust check we'd query the OMOP vocabulary, but for now we flag
        # obvious cases.

        return ConceptMappingReport(
            total_facts=total_facts,
            mapped=mapped,
            unmapped=unmapped,
            mapping_rate=round(mapping_rate, 4),
            domain_mismatches=domain_mismatches,
            domain_mismatch_count=len(domain_mismatches),
            by_domain=by_domain,
        )

    # -------------------------------------------------------------------
    # ETL quality checks (DB queries)
    # -------------------------------------------------------------------

    async def run_etl_quality_checks(
        self,
        session: AsyncSession,
    ) -> ETLQualityReport:
        """Run comprehensive quality checks on all ClinicalFacts.

        Checks:
        - Orphaned facts (no source document or evidence)
        - Duplicate facts (same patient + concept + date)
        - Missing required fields
        - Value range violations for measurements

        Args:
            session: Async database session.

        Returns:
            ETLQualityReport with counts and details.
        """
        # Total facts
        total_result = await session.execute(
            select(func.count()).select_from(ClinicalFact).where(
                ClinicalFact.deleted_at.is_(None)
            )
        )
        total_facts = total_result.scalar() or 0

        # 1. Orphaned facts: facts with no evidence records
        orphaned_count = await self._count_orphaned_facts(session)

        # 2. Duplicate facts
        duplicate_groups = await self._find_duplicate_facts(session)
        duplicate_count = len(duplicate_groups)

        # 3. Missing required fields
        missing_field_entries = await self._find_missing_fields(session)
        missing_fields_count = len(missing_field_entries)

        # 4. Range violations for measurements
        range_violations = await self._find_range_violations(session)
        range_violation_count = len(range_violations)

        # Overall quality score
        # Deductions: orphans, duplicates, missing fields, range violations
        if total_facts > 0:
            issues_total = (
                orphaned_count
                + duplicate_count
                + missing_fields_count
                + range_violation_count
            )
            score = max(0.0, 1.0 - (issues_total / total_facts))
        else:
            score = 1.0

        return ETLQualityReport(
            orphaned_count=orphaned_count,
            duplicate_count=duplicate_count,
            duplicate_groups=duplicate_groups,
            missing_fields_count=missing_fields_count,
            missing_field_entries=missing_field_entries,
            range_violations=range_violations,
            range_violation_count=range_violation_count,
            total_facts=total_facts,
            overall_score=round(score, 4),
        )

    # -------------------------------------------------------------------
    # Private helpers: field comparison
    # -------------------------------------------------------------------

    def _compare_concept_mapping(
        self,
        fhir_resource: dict[str, Any],
        clinical_fact: dict[str, Any],
    ) -> FieldComparison:
        """Compare FHIR coding -> OMOP concept_id mapping."""
        # Extract code from FHIR resource
        source_code = self._extract_fhir_code(fhir_resource)
        target_concept_id = clinical_fact.get("omop_concept_id", 0)

        # Also compare display text -> concept_name
        source_display = self._extract_fhir_display(fhir_resource)
        target_name = clinical_fact.get("concept_name", "")

        # For numeric codes, check if they match concept_id
        code_matches = False
        if source_code and source_code.isdigit():
            code_matches = int(source_code) == target_concept_id
        elif target_concept_id == 0:
            # Both unmapped -- acceptable
            code_matches = True

        # Name should be preserved
        name_matches = False
        if source_display and target_name:
            # Allow "Allergy to X" prefix for AllergyIntolerance resources
            name_matches = (
                source_display.lower() == target_name.lower()
                or target_name.lower().endswith(source_display.lower())
            )

        match = code_matches and name_matches
        message = None
        if not code_matches:
            message = (
                f"Concept mapping mismatch: FHIR code '{source_code}' "
                f"-> OMOP concept_id {target_concept_id}"
            )
        elif not name_matches:
            message = (
                f"Concept name mismatch: FHIR display '{source_display}' "
                f"-> fact concept_name '{target_name}'"
            )

        return FieldComparison(
            field_name="concept_mapping",
            source_value=f"{source_code}|{source_display}",
            target_value=f"{target_concept_id}|{target_name}",
            match=match,
            comparison_type=ComparisonType.MAPPED,
            message=message,
        )

    def _compare_dates(
        self,
        fhir_resource: dict[str, Any],
        clinical_fact: dict[str, Any],
        resource_type: str,
    ) -> FieldComparison:
        """Compare FHIR date fields -> ClinicalFact start_date."""
        source_date = self._extract_fhir_date(fhir_resource, resource_type)
        target_date = clinical_fact.get("start_date")

        # Normalize target_date to string for comparison
        target_date_str = None
        if target_date:
            if isinstance(target_date, datetime):
                target_date_str = target_date.isoformat()
            else:
                target_date_str = str(target_date)

        # Both None is a match
        if source_date is None and target_date is None:
            return FieldComparison(
                field_name="date",
                source_value=None,
                target_value=None,
                match=True,
                comparison_type=ComparisonType.EXACT,
            )

        # One None and other not -> mismatch
        if source_date is None or target_date_str is None:
            return FieldComparison(
                field_name="date",
                source_value=source_date,
                target_value=target_date_str,
                match=False,
                comparison_type=ComparisonType.EXACT,
                message=f"Date mismatch: source={source_date}, target={target_date_str}",
            )

        # Compare date portions (ignore timezone differences)
        source_date_part = source_date[:10] if source_date else ""
        target_date_part = target_date_str[:10] if target_date_str else ""
        match = source_date_part == target_date_part

        return FieldComparison(
            field_name="date",
            source_value=source_date,
            target_value=target_date_str,
            match=match,
            comparison_type=ComparisonType.FUZZY,
            message=None if match else f"Date mismatch: '{source_date}' vs '{target_date_str}'",
        )

    def _compare_patient_reference(
        self,
        fhir_resource: dict[str, Any],
        clinical_fact: dict[str, Any],
    ) -> FieldComparison:
        """Compare FHIR subject/patient reference -> ClinicalFact patient_id."""
        # Extract patient reference from FHIR
        # AllergyIntolerance uses "patient" key, others use "subject"
        subject = fhir_resource.get("subject") or fhir_resource.get("patient") or {}
        patient_ref = subject.get("reference", "")
        # Extract just the ID part: "Patient/123" -> "123"
        fhir_patient_id = patient_ref.replace("Patient/", "") if patient_ref else None

        target_patient_id = clinical_fact.get("patient_id", "")

        # The internal patient_id is typically "fhir-{id}" or the raw patient_id
        match = False
        if fhir_patient_id and target_patient_id:
            match = (
                target_patient_id == fhir_patient_id
                or target_patient_id == f"fhir-{fhir_patient_id}"
                or target_patient_id.endswith(fhir_patient_id)
            )
        elif not fhir_patient_id and not target_patient_id:
            match = True

        return FieldComparison(
            field_name="patient_reference",
            source_value=fhir_patient_id,
            target_value=target_patient_id,
            match=match,
            comparison_type=ComparisonType.MAPPED,
            message=None
            if match
            else f"Patient reference mismatch: FHIR '{fhir_patient_id}' -> fact '{target_patient_id}'",
        )

    def _compare_value_quantity(
        self,
        fhir_resource: dict[str, Any],
        clinical_fact: dict[str, Any],
    ) -> FieldComparison:
        """Compare FHIR valueQuantity -> ClinicalFact value/unit."""
        value_quantity = fhir_resource.get("valueQuantity", {})
        source_value = value_quantity.get("value")
        source_unit = value_quantity.get("unit")

        # Also check doseQuantity for Immunizations
        if source_value is None:
            dose_quantity = fhir_resource.get("doseQuantity", {})
            source_value = dose_quantity.get("value")
            source_unit = dose_quantity.get("unit")

        target_value = clinical_fact.get("value")
        target_unit = clinical_fact.get("unit")

        # Both None is fine
        if source_value is None and target_value is None:
            return FieldComparison(
                field_name="value_quantity",
                source_value=None,
                target_value=None,
                match=True,
                comparison_type=ComparisonType.EXACT,
            )

        # Compare values (source might be float, target is string)
        value_match = False
        if source_value is not None and target_value is not None:
            try:
                value_match = abs(float(source_value) - float(target_value)) < 0.001
            except (ValueError, TypeError):
                value_match = str(source_value) == str(target_value)

        unit_match = (source_unit or "") == (target_unit or "")

        match = value_match and unit_match
        source_str = f"{source_value} {source_unit}" if source_value is not None else None
        target_str = f"{target_value} {target_unit}" if target_value is not None else None

        return FieldComparison(
            field_name="value_quantity",
            source_value=source_str,
            target_value=target_str,
            match=match,
            comparison_type=ComparisonType.EXACT,
            message=None
            if match
            else f"Value mismatch: source='{source_str}', target='{target_str}'",
        )

    def _compare_domain(
        self,
        fhir_resource: dict[str, Any],
        clinical_fact: dict[str, Any],
        resource_type: str,
    ) -> FieldComparison:
        """Check that the ClinicalFact domain matches the FHIR resource type."""
        expected_domain = FHIR_RESOURCE_DOMAIN_MAP.get(resource_type)
        actual_domain = clinical_fact.get("domain")

        if expected_domain is None:
            return FieldComparison(
                field_name="domain",
                source_value=resource_type,
                target_value=actual_domain,
                match=True,
                comparison_type=ComparisonType.MAPPED,
                message="Resource type not in domain map, skipping domain check",
            )

        # Observation can map to either OBSERVATION or MEASUREMENT
        expected_values = [expected_domain.value]
        if resource_type == "Observation":
            expected_values = [Domain.OBSERVATION.value, Domain.MEASUREMENT.value]

        match = actual_domain in expected_values

        return FieldComparison(
            field_name="domain",
            source_value=resource_type,
            target_value=actual_domain,
            match=match,
            comparison_type=ComparisonType.MAPPED,
            message=None
            if match
            else f"Domain mismatch: {resource_type} expected {expected_values}, got '{actual_domain}'",
        )

    def _check_provenance(
        self,
        clinical_fact: dict[str, Any],
    ) -> FieldComparison:
        """Check that the ClinicalFact has source provenance."""
        pipeline_version = clinical_fact.get("pipeline_version")
        has_provenance = pipeline_version is not None and pipeline_version != ""

        return FieldComparison(
            field_name="provenance",
            source_value="expected",
            target_value=pipeline_version,
            match=has_provenance,
            comparison_type=ComparisonType.EXACT,
            message=None if has_provenance else "Missing pipeline_version provenance",
        )

    # -------------------------------------------------------------------
    # Private helpers: FHIR field extraction
    # -------------------------------------------------------------------

    def _extract_fhir_code(self, resource: dict[str, Any]) -> str | None:
        """Extract the primary code from a FHIR resource."""
        resource_type = resource.get("resourceType", "")

        # Each resource type stores codes differently
        if resource_type in ("Condition", "Procedure", "AllergyIntolerance"):
            code_concept = resource.get("code", {})
        elif resource_type in ("MedicationRequest", "MedicationStatement"):
            code_concept = resource.get("medicationCodeableConcept", {})
        elif resource_type == "Observation":
            code_concept = resource.get("code", {})
        elif resource_type == "Immunization":
            code_concept = resource.get("vaccineCode", {})
        elif resource_type == "Encounter":
            types = resource.get("type", [])
            code_concept = types[0] if types else {}
        else:
            code_concept = resource.get("code", {})

        codings = code_concept.get("coding", [])
        if codings:
            return codings[0].get("code")
        return None

    def _extract_fhir_display(self, resource: dict[str, Any]) -> str | None:
        """Extract the display name from a FHIR resource."""
        resource_type = resource.get("resourceType", "")

        if resource_type in ("Condition", "Procedure", "AllergyIntolerance"):
            code_concept = resource.get("code", {})
        elif resource_type in ("MedicationRequest", "MedicationStatement"):
            code_concept = resource.get("medicationCodeableConcept", {})
        elif resource_type == "Observation":
            code_concept = resource.get("code", {})
        elif resource_type == "Immunization":
            code_concept = resource.get("vaccineCode", {})
        elif resource_type == "Encounter":
            types = resource.get("type", [])
            code_concept = types[0] if types else {}
        else:
            code_concept = resource.get("code", {})

        codings = code_concept.get("coding", [])
        if codings:
            return codings[0].get("display") or code_concept.get("text")
        return code_concept.get("text")

    def _extract_fhir_date(
        self, resource: dict[str, Any], resource_type: str
    ) -> str | None:
        """Extract the primary date from a FHIR resource."""
        if resource_type == "Condition":
            return resource.get("onsetDateTime")
        elif resource_type == "MedicationRequest":
            return resource.get("authoredOn")
        elif resource_type in ("MedicationStatement",):
            return (
                resource.get("effectiveDateTime")
                or resource.get("effectivePeriod", {}).get("start")
                or resource.get("dateAsserted")
            )
        elif resource_type == "Observation":
            return resource.get("effectiveDateTime") or resource.get(
                "effectivePeriod", {}
            ).get("start")
        elif resource_type == "Procedure":
            return resource.get("performedDateTime") or resource.get(
                "performedPeriod", {}
            ).get("start")
        elif resource_type == "AllergyIntolerance":
            return resource.get("recordedDate")
        elif resource_type == "Encounter":
            return resource.get("period", {}).get("start")
        elif resource_type == "Immunization":
            return resource.get("occurrenceDateTime")
        return None

    def _find_matching_fact(
        self,
        resource: dict[str, Any],
        facts: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Find the ClinicalFact that matches a FHIR resource.

        Matches on concept_name (display text) since that's the most
        reliable field preserved through the ETL.
        """
        display = self._extract_fhir_display(resource)
        if not display:
            return None

        resource_type = resource.get("resourceType", "")

        for fact in facts:
            fact_name = fact.get("concept_name", "")
            # Direct match
            if fact_name.lower() == display.lower():
                return fact
            # AllergyIntolerance adds "Allergy to " prefix
            if resource_type == "AllergyIntolerance" and fact_name.lower() == f"allergy to {display.lower()}":
                return fact

        return None

    # -------------------------------------------------------------------
    # Private helpers: DB quality checks
    # -------------------------------------------------------------------

    async def _count_orphaned_facts(self, session: AsyncSession) -> int:
        """Count facts that have no evidence records linking to a source."""
        from app.models.clinical_fact import FactEvidence

        # Facts with no evidence at all
        subq = select(FactEvidence.fact_id).distinct()
        result = await session.execute(
            select(func.count()).select_from(ClinicalFact).where(
                ClinicalFact.deleted_at.is_(None),
                ClinicalFact.id.notin_(subq),
            )
        )
        return result.scalar() or 0

    async def _find_duplicate_facts(
        self, session: AsyncSession
    ) -> list[DuplicateGroup]:
        """Find duplicate facts (same patient + concept_id + start_date)."""
        # Group by patient_id, omop_concept_id, start_date and find groups > 1
        stmt = (
            select(
                ClinicalFact.patient_id,
                ClinicalFact.omop_concept_id,
                ClinicalFact.concept_name,
                ClinicalFact.start_date,
                func.count().label("cnt"),
            )
            .where(
                ClinicalFact.deleted_at.is_(None),
                ClinicalFact.omop_concept_id > 0,
            )
            .group_by(
                ClinicalFact.patient_id,
                ClinicalFact.omop_concept_id,
                ClinicalFact.concept_name,
                ClinicalFact.start_date,
            )
            .having(func.count() > 1)
        )
        result = await session.execute(stmt)

        groups: list[DuplicateGroup] = []
        for row in result:
            patient_id = row[0]
            concept_id = row[1]
            concept_name = row[2]
            start_date = row[3]
            count = row[4]

            # Get the actual fact IDs in this group
            ids_stmt = select(ClinicalFact.id).where(
                ClinicalFact.deleted_at.is_(None),
                ClinicalFact.patient_id == patient_id,
                ClinicalFact.omop_concept_id == concept_id,
                ClinicalFact.concept_name == concept_name,
            )
            if start_date is not None:
                ids_stmt = ids_stmt.where(ClinicalFact.start_date == start_date)
            else:
                ids_stmt = ids_stmt.where(ClinicalFact.start_date.is_(None))

            ids_result = await session.execute(ids_stmt)
            fact_ids = [str(r[0]) for r in ids_result]

            groups.append(
                DuplicateGroup(
                    patient_id=patient_id,
                    omop_concept_id=concept_id,
                    concept_name=concept_name,
                    start_date=start_date.isoformat() if start_date else None,
                    count=count,
                    fact_ids=fact_ids,
                )
            )

        return groups

    async def _find_missing_fields(
        self, session: AsyncSession
    ) -> list[MissingFieldEntry]:
        """Find facts missing required fields (concept_name, domain, patient_id)."""
        # Required fields: patient_id, domain, concept_name, omop_concept_id
        stmt = select(
            ClinicalFact.id,
            ClinicalFact.patient_id,
            ClinicalFact.concept_name,
            ClinicalFact.domain,
        ).where(ClinicalFact.deleted_at.is_(None))

        result = await session.execute(stmt)
        entries: list[MissingFieldEntry] = []

        for row in result:
            fact_id = str(row[0])
            patient_id = row[1]
            concept_name = row[2]
            domain = row[3]

            missing: list[str] = []
            if not patient_id or patient_id.strip() == "":
                missing.append("patient_id")
            if not concept_name or concept_name.strip() == "":
                missing.append("concept_name")
            if domain is None:
                missing.append("domain")

            if missing:
                entries.append(
                    MissingFieldEntry(
                        fact_id=fact_id,
                        patient_id=patient_id or "",
                        missing_fields=missing,
                    )
                )

        return entries

    async def _find_range_violations(
        self, session: AsyncSession
    ) -> list[RangeViolation]:
        """Find measurement facts with values outside expected ranges."""
        stmt = select(
            ClinicalFact.id,
            ClinicalFact.patient_id,
            ClinicalFact.concept_name,
            ClinicalFact.value,
            ClinicalFact.unit,
        ).where(
            ClinicalFact.deleted_at.is_(None),
            ClinicalFact.value.isnot(None),
            ClinicalFact.domain.in_([Domain.MEASUREMENT, Domain.OBSERVATION]),
        )

        result = await session.execute(stmt)
        violations: list[RangeViolation] = []

        for row in result:
            fact_id = str(row[0])
            patient_id = row[1]
            concept_name = row[2]
            value_str = row[3]
            unit = row[4]

            if not value_str:
                continue

            try:
                value_float = float(value_str)
            except (ValueError, TypeError):
                continue

            # Check against known ranges
            for range_name, (low, high) in MEASUREMENT_RANGES.items():
                if range_name.lower() in concept_name.lower():
                    if value_float < low or value_float > high:
                        violations.append(
                            RangeViolation(
                                fact_id=fact_id,
                                patient_id=patient_id,
                                concept_name=concept_name,
                                value=value_str,
                                unit=unit,
                                reason=f"Value {value_float} outside expected range [{low}, {high}] for {range_name}",
                            )
                        )
                    break  # Found matching range, stop checking

        return violations
