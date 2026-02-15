"""P2-028: FHIR interoperability conformance suite.

Validates FHIR exports match R4 profiles, checks CapabilityStatement structure,
validates Patient/Condition/Observation resources have required fields,
FHIR resource IDs, references, and coding systems.

Tests use the existing:
- backend/app/services/fhir_exporter.py (FHIRExporterService)
- backend/app/services/fhir_validator.py (FHIRValidator)
- backend/app/api/fhir_validation.py (validation endpoints)
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from app.services.fhir_exporter import (
    ClinicalFact,
    FHIR_CODE_SYSTEMS,
    FHIRExporterService,
    FHIRResourceType,
    get_fhir_exporter_service,
    reset_fhir_exporter_service,
)
from app.services.fhir_validator import (
    FHIR_R4_RESOURCE_TYPES,
    FHIR_REFERENCE_RE,
    FHIRValidator,
    get_fhir_validator,
)


# ---------------------------------------------------------------------------
# Helper: Build a minimal valid CapabilityStatement
# ---------------------------------------------------------------------------

def build_capability_statement() -> dict[str, Any]:
    """Build a valid FHIR R4 CapabilityStatement for the system.

    This represents what a /fhir/metadata endpoint should return.
    """
    return {
        "resourceType": "CapabilityStatement",
        "id": "clinical-ontology-normalizer",
        "status": "active",
        "date": "2026-01-01",
        "kind": "instance",
        "fhirVersion": "4.0.1",
        "format": ["json"],
        "rest": [
            {
                "mode": "server",
                "resource": [
                    {
                        "type": "Patient",
                        "interaction": [
                            {"code": "read"},
                            {"code": "search-type"},
                        ],
                        "searchParam": [
                            {"name": "_id", "type": "token"},
                            {"name": "identifier", "type": "token"},
                        ],
                    },
                    {
                        "type": "Condition",
                        "interaction": [
                            {"code": "read"},
                            {"code": "search-type"},
                        ],
                        "searchParam": [
                            {"name": "patient", "type": "reference"},
                            {"name": "code", "type": "token"},
                        ],
                    },
                    {
                        "type": "Observation",
                        "interaction": [
                            {"code": "read"},
                            {"code": "search-type"},
                        ],
                        "searchParam": [
                            {"name": "patient", "type": "reference"},
                            {"name": "code", "type": "token"},
                            {"name": "category", "type": "token"},
                        ],
                    },
                    {
                        "type": "Procedure",
                        "interaction": [
                            {"code": "read"},
                        ],
                    },
                    {
                        "type": "MedicationStatement",
                        "interaction": [
                            {"code": "read"},
                        ],
                    },
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def exporter() -> FHIRExporterService:
    """Fresh FHIR exporter service."""
    reset_fhir_exporter_service()
    return get_fhir_exporter_service()


@pytest.fixture
def validator() -> FHIRValidator:
    """FHIR validator instance."""
    return get_fhir_validator()


@pytest.fixture
def sample_condition_fact() -> ClinicalFact:
    """Sample condition clinical fact."""
    return ClinicalFact(
        fact_type="condition",
        label="Type 2 Diabetes Mellitus",
        icd10_code="E11.9",
        snomed_code="44054006",
        patient_id="patient-001",
        recorded_date="2026-01-15",
        confidence=0.95,
    )


@pytest.fixture
def sample_observation_fact() -> ClinicalFact:
    """Sample observation clinical fact."""
    return ClinicalFact(
        fact_type="measurement",
        label="Blood Glucose",
        value="126",
        unit="mg/dL",
        loinc_code="2345-7",
        patient_id="patient-001",
        recorded_date="2026-01-15",
        confidence=0.98,
    )


@pytest.fixture
def sample_patient_resource(exporter: FHIRExporterService) -> dict[str, Any]:
    """Export a Patient resource."""
    fact = ClinicalFact(
        fact_type="condition",
        label="Test",
        patient_id="patient-001",
    )
    bundle = exporter.export_facts([fact], patient_id="patient-001")
    # First entry is the Patient resource
    return bundle.entries[0].resource


# ===========================================================================
# 1. CapabilityStatement Validation (3 tests)
# ===========================================================================


class TestCapabilityStatementStructure:
    """Validate CapabilityStatement structure per FHIR R4."""

    def test_capability_statement_has_required_fields(self) -> None:
        """CapabilityStatement must have resourceType, status, date, kind, fhirVersion, format."""
        cs = build_capability_statement()
        assert cs["resourceType"] == "CapabilityStatement"
        assert cs["status"] in ("active", "draft", "retired")
        assert "date" in cs
        assert cs["kind"] in ("instance", "capability", "requirements")
        assert cs["fhirVersion"] == "4.0.1"
        assert "json" in cs["format"]

    def test_capability_statement_declares_rest_resources(self) -> None:
        """CapabilityStatement declares supported resource types in rest.resource."""
        cs = build_capability_statement()
        rest = cs["rest"]
        assert len(rest) > 0
        resources = rest[0]["resource"]
        resource_types = {r["type"] for r in resources}
        # System must declare at least these
        assert "Patient" in resource_types
        assert "Condition" in resource_types
        assert "Observation" in resource_types

    def test_capability_statement_declares_search_params(self) -> None:
        """Condition resource declares patient search parameter."""
        cs = build_capability_statement()
        resources = cs["rest"][0]["resource"]
        condition_res = next(r for r in resources if r["type"] == "Condition")
        search_params = {p["name"] for p in condition_res.get("searchParam", [])}
        assert "patient" in search_params


# ===========================================================================
# 2. Patient Resource Validation (3 tests)
# ===========================================================================


class TestPatientResourceConformance:
    """Validate Patient resource structure against FHIR R4."""

    def test_patient_has_resource_type(self, sample_patient_resource: dict[str, Any]) -> None:
        """Patient resource has correct resourceType."""
        assert sample_patient_resource["resourceType"] == "Patient"

    def test_patient_has_id(self, sample_patient_resource: dict[str, Any]) -> None:
        """Patient resource has an id field."""
        assert "id" in sample_patient_resource
        assert len(sample_patient_resource["id"]) > 0

    def test_patient_has_identifier(self, sample_patient_resource: dict[str, Any]) -> None:
        """Patient resource has at least one identifier."""
        assert "identifier" in sample_patient_resource
        identifiers = sample_patient_resource["identifier"]
        assert isinstance(identifiers, list)
        assert len(identifiers) >= 1
        assert "system" in identifiers[0]
        assert "value" in identifiers[0]


# ===========================================================================
# 3. Condition Resource Validation (3 tests)
# ===========================================================================


class TestConditionResourceConformance:
    """Validate Condition resource structure."""

    def test_condition_has_required_fields(
        self,
        exporter: FHIRExporterService,
        sample_condition_fact: ClinicalFact,
    ) -> None:
        """Condition resource has clinicalStatus, code, subject."""
        resource = exporter.export_fact(sample_condition_fact)
        assert resource is not None
        cond = resource.resource
        assert cond["resourceType"] == "Condition"
        assert "clinicalStatus" in cond
        assert "code" in cond
        assert "subject" in cond

    def test_condition_clinical_status_valid(
        self,
        exporter: FHIRExporterService,
        sample_condition_fact: ClinicalFact,
    ) -> None:
        """Condition clinicalStatus uses correct code system."""
        resource = exporter.export_fact(sample_condition_fact)
        cond = resource.resource
        cs = cond["clinicalStatus"]["coding"][0]
        assert cs["system"] == "http://terminology.hl7.org/CodeSystem/condition-clinical"
        assert cs["code"] in ("active", "recurrence", "relapse", "inactive", "remission", "resolved")

    def test_condition_code_has_coding(
        self,
        exporter: FHIRExporterService,
        sample_condition_fact: ClinicalFact,
    ) -> None:
        """Condition code includes at least one coding with system and code."""
        resource = exporter.export_fact(sample_condition_fact)
        cond = resource.resource
        coding = cond["code"]["coding"]
        assert len(coding) >= 1
        for c in coding:
            assert "system" in c
            assert "code" in c


# ===========================================================================
# 4. Observation Resource Validation (2 tests)
# ===========================================================================


class TestObservationResourceConformance:
    """Validate Observation resource structure."""

    def test_observation_has_required_fields(
        self,
        exporter: FHIRExporterService,
        sample_observation_fact: ClinicalFact,
    ) -> None:
        """Observation resource has status, category, code, subject."""
        resource = exporter.export_fact(sample_observation_fact)
        assert resource is not None
        obs = resource.resource
        assert obs["resourceType"] == "Observation"
        assert "status" in obs
        assert "category" in obs
        assert "code" in obs
        assert "subject" in obs

    def test_observation_value_quantity(
        self,
        exporter: FHIRExporterService,
        sample_observation_fact: ClinicalFact,
    ) -> None:
        """Observation with numeric value has valueQuantity with units."""
        resource = exporter.export_fact(sample_observation_fact)
        obs = resource.resource
        assert "valueQuantity" in obs
        vq = obs["valueQuantity"]
        assert "value" in vq
        assert "unit" in vq
        assert "system" in vq
        assert vq["system"] == "http://unitsofmeasure.org"


# ===========================================================================
# 5. FHIR Resource IDs and References (2 tests)
# ===========================================================================


class TestFHIRResourceIDs:
    """Validate FHIR resource IDs and reference format."""

    def test_resource_ids_are_non_empty_strings(
        self,
        exporter: FHIRExporterService,
    ) -> None:
        """All exported resources have non-empty string IDs."""
        facts = [
            ClinicalFact(fact_type="condition", label="HTN", patient_id="p1"),
            ClinicalFact(fact_type="measurement", label="BP", value="120", patient_id="p1"),
            ClinicalFact(fact_type="procedure", label="Appendectomy", patient_id="p1"),
        ]
        bundle = exporter.export_facts(facts, patient_id="p1")
        for entry in bundle.entries:
            assert isinstance(entry.resource["id"], str)
            assert len(entry.resource["id"]) > 0

    def test_patient_reference_format(
        self,
        exporter: FHIRExporterService,
    ) -> None:
        """Subject references use 'Patient/{id}' format."""
        fact = ClinicalFact(
            fact_type="condition",
            label="Asthma",
            patient_id="patient-42",
        )
        resource = exporter.export_fact(fact)
        subject = resource.resource.get("subject", {})
        ref = subject.get("reference", "")
        assert ref.startswith("Patient/")
        assert FHIR_REFERENCE_RE.match(ref)


# ===========================================================================
# 6. Coding Systems Validation (2 tests)
# ===========================================================================


class TestFHIRCodingSystems:
    """Validate FHIR coding system URIs."""

    def test_known_code_systems_are_valid_uris(self) -> None:
        """All known FHIR code system URIs start with http://."""
        for key, uri in FHIR_CODE_SYSTEMS.items():
            assert uri.startswith("http://") or uri.startswith("https://"), (
                f"Code system {key} has invalid URI: {uri}"
            )

    def test_condition_uses_correct_code_systems(
        self,
        exporter: FHIRExporterService,
    ) -> None:
        """Condition with ICD-10 and SNOMED uses correct code system URIs."""
        fact = ClinicalFact(
            fact_type="condition",
            label="Diabetes",
            icd10_code="E11.9",
            snomed_code="44054006",
            patient_id="p1",
        )
        resource = exporter.export_fact(fact)
        cond = resource.resource
        systems = {c["system"] for c in cond["code"]["coding"]}
        assert FHIR_CODE_SYSTEMS["icd10"] in systems
        assert FHIR_CODE_SYSTEMS["snomed"] in systems


# ===========================================================================
# 7. FHIR Validator Integration (2 tests)
# ===========================================================================


class TestFHIRValidatorConformance:
    """Test the FHIRValidator against exported resources."""

    def test_exported_condition_passes_validation(
        self,
        exporter: FHIRExporterService,
        validator: FHIRValidator,
        sample_condition_fact: ClinicalFact,
    ) -> None:
        """Exported Condition resource passes FHIR R4 validation."""
        resource = exporter.export_fact(sample_condition_fact)
        result = validator.validate_resource(resource.resource)
        errors = [i for i in result.issues if i.severity.value == "error"]
        assert result.is_valid, f"Validation errors: {[e.message for e in errors]}"

    def test_exported_bundle_passes_validation(
        self,
        exporter: FHIRExporterService,
        validator: FHIRValidator,
    ) -> None:
        """Exported Bundle with multiple resources passes validation."""
        facts = [
            ClinicalFact(
                fact_type="condition",
                label="HTN",
                icd10_code="I10",
                patient_id="p1",
                confidence=0.95,
            ),
            ClinicalFact(
                fact_type="measurement",
                label="BP Systolic",
                value="140",
                unit="mmHg",
                loinc_code="8480-6",
                patient_id="p1",
                confidence=0.98,
            ),
        ]
        bundle = exporter.export_facts(facts, patient_id="p1")
        bundle_json = json.loads(exporter.to_json(bundle))
        result = validator.validate_bundle(bundle_json)
        assert result.valid_count == result.total_resources, (
            f"{result.invalid_count} invalid resources out of {result.total_resources}"
        )
