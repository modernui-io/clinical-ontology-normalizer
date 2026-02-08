"""Dir-CI-3.2: FHIR R4 resource validation and US Core conformance testing.

Tests FHIR resource validation against R4 base spec and US Core profiles.
~30 tests covering Patient, Condition, Observation, MedicationRequest,
Procedure, Bundle, coding systems, references, and API endpoints.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.schemas.fhir_validation import IssueSeverity
from app.services.fhir_validator import FHIRValidator, get_fhir_validator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def validator() -> FHIRValidator:
    return get_fhir_validator()


def _make_patient(**overrides) -> dict:
    """Build a valid FHIR Patient resource with optional overrides."""
    base = {
        "resourceType": "Patient",
        "id": "pat-001",
        "identifier": [
            {"system": "http://hospital.example/mrn", "value": "MRN-12345"}
        ],
        "name": [{"family": "Doe", "given": ["Jane"]}],
        "gender": "female",
        "birthDate": "1990-05-15",
    }
    base.update(overrides)
    return base


def _make_condition(**overrides) -> dict:
    base = {
        "resourceType": "Condition",
        "id": "cond-001",
        "clinicalStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": "active",
                }
            ]
        },
        "verificationStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                    "code": "confirmed",
                }
            ]
        },
        "code": {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": "44054006",
                    "display": "Type 2 diabetes mellitus",
                }
            ]
        },
        "subject": {"reference": "Patient/pat-001"},
    }
    base.update(overrides)
    return base


def _make_observation(**overrides) -> dict:
    base = {
        "resourceType": "Observation",
        "id": "obs-001",
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "laboratory",
                    }
                ]
            }
        ],
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "4548-4",
                    "display": "Hemoglobin A1c",
                }
            ]
        },
        "subject": {"reference": "Patient/pat-001"},
        "effectiveDateTime": "2024-06-15T10:30:00Z",
        "valueQuantity": {
            "value": 7.2,
            "unit": "%",
            "system": "http://unitsofmeasure.org",
            "code": "%",
        },
    }
    base.update(overrides)
    return base


def _make_medication_request(**overrides) -> dict:
    base = {
        "resourceType": "MedicationRequest",
        "id": "medrq-001",
        "status": "active",
        "intent": "order",
        "medicationCodeableConcept": {
            "coding": [
                {
                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code": "860975",
                    "display": "Metformin 500 MG Oral Tablet",
                }
            ]
        },
        "subject": {"reference": "Patient/pat-001"},
        "authoredOn": "2024-06-01T09:00:00Z",
    }
    base.update(overrides)
    return base


def _make_procedure(**overrides) -> dict:
    base = {
        "resourceType": "Procedure",
        "id": "proc-001",
        "status": "completed",
        "code": {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": "29303009",
                    "display": "Electrocardiographic procedure",
                }
            ]
        },
        "subject": {"reference": "Patient/pat-001"},
        "performedDateTime": "2024-05-20T14:00:00Z",
    }
    base.update(overrides)
    return base


def _make_bundle(resources: list[dict] | None = None) -> dict:
    if resources is None:
        resources = [_make_patient(), _make_condition(), _make_observation()]
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": r} for r in resources],
    }


# ===========================================================================
# 1. Base FHIR R4 validation tests
# ===========================================================================

class TestValidateResource:
    """Tests for FHIRValidator.validate_resource()."""

    def test_valid_patient_passes(self, validator: FHIRValidator):
        result = validator.validate_resource(_make_patient())
        assert result.is_valid is True
        assert result.resource_type == "Patient"
        errors = [i for i in result.issues if i.severity == IssueSeverity.ERROR]
        assert len(errors) == 0

    def test_missing_resource_type_fails(self, validator: FHIRValidator):
        resource = {"id": "no-type"}
        result = validator.validate_resource(resource)
        assert result.is_valid is False
        assert any("resourceType" in i.message for i in result.issues)

    def test_unknown_resource_type_fails(self, validator: FHIRValidator):
        resource = {"resourceType": "FakeResource", "id": "fake-1"}
        result = validator.validate_resource(resource)
        assert result.is_valid is False
        assert any("Unknown resourceType" in i.message for i in result.issues)

    def test_missing_id_warning(self, validator: FHIRValidator):
        """Patient without id gets a warning (not an error)."""
        patient = _make_patient()
        del patient["id"]
        result = validator.validate_resource(patient)
        assert result.is_valid is True
        warnings = [i for i in result.issues if i.severity == IssueSeverity.WARNING]
        assert any("id" in i.path for i in warnings)

    def test_valid_condition_passes(self, validator: FHIRValidator):
        result = validator.validate_resource(_make_condition())
        assert result.is_valid is True
        assert result.resource_type == "Condition"

    def test_valid_observation_passes(self, validator: FHIRValidator):
        result = validator.validate_resource(_make_observation())
        assert result.is_valid is True
        assert result.resource_type == "Observation"

    def test_valid_medication_request_passes(self, validator: FHIRValidator):
        result = validator.validate_resource(_make_medication_request())
        assert result.is_valid is True
        assert result.resource_type == "MedicationRequest"

    def test_valid_procedure_passes(self, validator: FHIRValidator):
        result = validator.validate_resource(_make_procedure())
        assert result.is_valid is True
        assert result.resource_type == "Procedure"

    def test_invalid_date_format_fails(self, validator: FHIRValidator):
        patient = _make_patient(birthDate="06/15/1990")
        result = validator.validate_resource(patient)
        assert result.is_valid is False
        assert any(
            "birthDate" in i.path and "date" in i.message.lower()
            for i in result.issues
        )

    def test_invalid_datetime_format_fails(self, validator: FHIRValidator):
        obs = _make_observation(effectiveDateTime="2024-06-15 10:30:00")
        result = validator.validate_resource(obs)
        assert result.is_valid is False
        assert any("effectiveDateTime" in i.path for i in result.issues)

    def test_valid_date_only_passes(self, validator: FHIRValidator):
        """Date-only value for dateTime fields should be accepted."""
        obs = _make_observation(effectiveDateTime="2024-06-15")
        result = validator.validate_resource(obs)
        assert result.is_valid is True

    def test_valid_partial_date_passes(self, validator: FHIRValidator):
        """Year-month and year-only dates should be accepted."""
        patient = _make_patient(birthDate="1990-05")
        result = validator.validate_resource(patient)
        assert result.is_valid is True

        patient2 = _make_patient(birthDate="1990")
        result2 = validator.validate_resource(patient2)
        assert result2.is_valid is True


# ===========================================================================
# 2. Coding system validation tests
# ===========================================================================

class TestCodingValidation:
    """Tests for coding system and code format validation."""

    def test_valid_snomed_code(self, validator: FHIRValidator):
        condition = _make_condition()
        result = validator.validate_resource(condition)
        code_issues = [
            i for i in result.issues
            if "code" in i.path and i.rule_id == "fhir-r4-coding-code-format"
        ]
        assert len(code_issues) == 0

    def test_invalid_snomed_code_warns(self, validator: FHIRValidator):
        condition = _make_condition(
            code={
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "ABC",
                        "display": "Bad code",
                    }
                ]
            }
        )
        result = validator.validate_resource(condition)
        code_issues = [
            i for i in result.issues
            if i.rule_id == "fhir-r4-coding-code-format"
        ]
        assert len(code_issues) >= 1
        assert "SNOMED" in code_issues[0].message

    def test_valid_loinc_code(self, validator: FHIRValidator):
        obs = _make_observation()
        result = validator.validate_resource(obs)
        code_issues = [
            i for i in result.issues
            if i.rule_id == "fhir-r4-coding-code-format"
        ]
        assert len(code_issues) == 0

    def test_invalid_loinc_code_warns(self, validator: FHIRValidator):
        obs = _make_observation(
            code={
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "INVALID",
                        "display": "Bad LOINC",
                    }
                ]
            }
        )
        result = validator.validate_resource(obs)
        code_issues = [
            i for i in result.issues
            if i.rule_id == "fhir-r4-coding-code-format"
        ]
        assert len(code_issues) >= 1

    def test_invalid_coding_system_uri_warns(self, validator: FHIRValidator):
        condition = _make_condition(
            code={
                "coding": [
                    {"system": "not-a-uri", "code": "12345", "display": "Bad system"}
                ]
            }
        )
        result = validator.validate_resource(condition)
        system_issues = [
            i for i in result.issues
            if i.rule_id == "fhir-r4-coding-system-uri"
        ]
        assert len(system_issues) >= 1

    def test_valid_rxnorm_code(self, validator: FHIRValidator):
        med = _make_medication_request()
        result = validator.validate_resource(med)
        code_issues = [
            i for i in result.issues
            if i.rule_id == "fhir-r4-coding-code-format"
        ]
        assert len(code_issues) == 0


# ===========================================================================
# 3. Reference format validation tests
# ===========================================================================

class TestReferenceValidation:
    """Tests for FHIR reference format validation."""

    def test_valid_relative_reference(self, validator: FHIRValidator):
        condition = _make_condition(subject={"reference": "Patient/pat-001"})
        result = validator.validate_resource(condition)
        ref_issues = [
            i for i in result.issues
            if i.rule_id == "fhir-r4-reference-format"
        ]
        assert len(ref_issues) == 0

    def test_valid_absolute_reference(self, validator: FHIRValidator):
        condition = _make_condition(
            subject={"reference": "https://fhir.example.com/Patient/pat-001"}
        )
        result = validator.validate_resource(condition)
        ref_issues = [
            i for i in result.issues
            if i.rule_id == "fhir-r4-reference-format"
        ]
        assert len(ref_issues) == 0

    def test_invalid_reference_format_warns(self, validator: FHIRValidator):
        condition = _make_condition(
            subject={"reference": "just-an-id-no-type"}
        )
        result = validator.validate_resource(condition)
        ref_issues = [
            i for i in result.issues
            if i.rule_id == "fhir-r4-reference-format"
        ]
        assert len(ref_issues) >= 1


# ===========================================================================
# 4. Bundle validation tests
# ===========================================================================

class TestValidateBundle:
    """Tests for FHIRValidator.validate_bundle()."""

    def test_valid_bundle_passes(self, validator: FHIRValidator):
        bundle = _make_bundle()
        result = validator.validate_bundle(bundle)
        assert result.valid_count == 3
        assert result.invalid_count == 0
        assert result.total_resources == 3

    def test_bundle_not_bundle_type(self, validator: FHIRValidator):
        bundle = {"resourceType": "Patient", "id": "not-a-bundle"}
        result = validator.validate_bundle(bundle)
        assert len(result.bundle_issues) > 0
        assert any("Bundle" in i.message for i in result.bundle_issues)

    def test_bundle_missing_type_field(self, validator: FHIRValidator):
        bundle = {
            "resourceType": "Bundle",
            "entry": [{"resource": _make_patient()}],
        }
        result = validator.validate_bundle(bundle)
        assert any(
            i.rule_id == "fhir-r4-bundle-type-required" for i in result.bundle_issues
        )

    def test_bundle_mixed_valid_invalid(self, validator: FHIRValidator):
        resources = [
            _make_patient(),
            {"resourceType": "FakeType", "id": "bad"},
            _make_observation(effectiveDateTime="NOT-A-DATE"),
        ]
        bundle = _make_bundle(resources)
        result = validator.validate_bundle(bundle)
        assert result.total_resources == 3
        assert result.valid_count == 1  # Only Patient is fully valid
        assert result.invalid_count == 2

    def test_bundle_empty_entries(self, validator: FHIRValidator):
        bundle = {"resourceType": "Bundle", "type": "collection", "entry": []}
        result = validator.validate_bundle(bundle)
        assert result.total_resources == 0
        assert result.valid_count == 0
        assert result.invalid_count == 0

    def test_bundle_entry_without_resource(self, validator: FHIRValidator):
        bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [{"fullUrl": "urn:uuid:abc"}],
        }
        result = validator.validate_bundle(bundle)
        assert any(
            i.rule_id == "fhir-r4-bundle-entry-resource" for i in result.bundle_issues
        )


# ===========================================================================
# 5. US Core profile conformance tests
# ===========================================================================

class TestUSCoreConformance:
    """Tests for FHIRValidator.check_us_core_conformance()."""

    def test_us_core_patient_valid(self, validator: FHIRValidator):
        result = validator.check_us_core_conformance(_make_patient())
        assert result.is_conformant is True
        assert result.resource_type == "Patient"
        assert "us-core-patient" in result.profile
        assert len(result.missing_elements) == 0

    def test_us_core_patient_missing_identifier(self, validator: FHIRValidator):
        patient = _make_patient()
        del patient["identifier"]
        result = validator.check_us_core_conformance(patient)
        assert result.is_conformant is False
        assert "identifier" in result.missing_elements

    def test_us_core_patient_missing_name(self, validator: FHIRValidator):
        patient = _make_patient()
        del patient["name"]
        result = validator.check_us_core_conformance(patient)
        assert result.is_conformant is False
        assert "name" in result.missing_elements

    def test_us_core_patient_missing_gender(self, validator: FHIRValidator):
        patient = _make_patient()
        del patient["gender"]
        result = validator.check_us_core_conformance(patient)
        assert result.is_conformant is False
        assert "gender" in result.missing_elements

    def test_us_core_patient_invalid_gender_value(self, validator: FHIRValidator):
        patient = _make_patient(gender="nonbinary")
        result = validator.check_us_core_conformance(patient)
        assert result.is_conformant is False
        assert any("gender" in i.path and "value" in i.rule_id for i in result.issues)

    def test_us_core_condition_valid(self, validator: FHIRValidator):
        result = validator.check_us_core_conformance(_make_condition())
        assert result.is_conformant is True
        assert "us-core-condition" in result.profile

    def test_us_core_condition_missing_clinical_status(self, validator: FHIRValidator):
        condition = _make_condition()
        del condition["clinicalStatus"]
        result = validator.check_us_core_conformance(condition)
        assert result.is_conformant is False
        assert "clinicalStatus" in result.missing_elements

    def test_us_core_condition_missing_code(self, validator: FHIRValidator):
        condition = _make_condition()
        del condition["code"]
        result = validator.check_us_core_conformance(condition)
        assert result.is_conformant is False
        assert "code" in result.missing_elements

    def test_us_core_condition_missing_subject(self, validator: FHIRValidator):
        condition = _make_condition()
        del condition["subject"]
        result = validator.check_us_core_conformance(condition)
        assert result.is_conformant is False
        assert "subject" in result.missing_elements

    def test_us_core_observation_valid(self, validator: FHIRValidator):
        result = validator.check_us_core_conformance(_make_observation())
        assert result.is_conformant is True
        assert "us-core-observation" in result.profile

    def test_us_core_observation_missing_status(self, validator: FHIRValidator):
        obs = _make_observation()
        del obs["status"]
        result = validator.check_us_core_conformance(obs)
        assert result.is_conformant is False
        assert "status" in result.missing_elements

    def test_us_core_observation_missing_category(self, validator: FHIRValidator):
        obs = _make_observation()
        del obs["category"]
        result = validator.check_us_core_conformance(obs)
        assert result.is_conformant is False
        assert "category" in result.missing_elements

    def test_us_core_observation_invalid_status_value(self, validator: FHIRValidator):
        obs = _make_observation(status="bogus-status")
        result = validator.check_us_core_conformance(obs)
        assert result.is_conformant is False
        assert any("status" in i.path for i in result.issues)

    def test_us_core_medication_request_valid(self, validator: FHIRValidator):
        result = validator.check_us_core_conformance(_make_medication_request())
        assert result.is_conformant is True
        assert "us-core-medicationrequest" in result.profile

    def test_us_core_medication_request_missing_medication(self, validator: FHIRValidator):
        med = _make_medication_request()
        del med["medicationCodeableConcept"]
        result = validator.check_us_core_conformance(med)
        assert result.is_conformant is False
        assert "medication[x]" in result.missing_elements

    def test_us_core_medication_request_with_reference(self, validator: FHIRValidator):
        """MedicationRequest with medicationReference (instead of CC) is valid."""
        med = _make_medication_request()
        del med["medicationCodeableConcept"]
        med["medicationReference"] = {"reference": "Medication/med-001"}
        result = validator.check_us_core_conformance(med)
        assert result.is_conformant is True

    def test_us_core_medication_request_missing_intent(self, validator: FHIRValidator):
        med = _make_medication_request()
        del med["intent"]
        result = validator.check_us_core_conformance(med)
        assert result.is_conformant is False
        assert "intent" in result.missing_elements

    def test_us_core_procedure_valid(self, validator: FHIRValidator):
        result = validator.check_us_core_conformance(_make_procedure())
        assert result.is_conformant is True
        assert "us-core-procedure" in result.profile

    def test_us_core_procedure_missing_status(self, validator: FHIRValidator):
        proc = _make_procedure()
        del proc["status"]
        result = validator.check_us_core_conformance(proc)
        assert result.is_conformant is False
        assert "status" in result.missing_elements

    def test_us_core_procedure_missing_code(self, validator: FHIRValidator):
        proc = _make_procedure()
        del proc["code"]
        result = validator.check_us_core_conformance(proc)
        assert result.is_conformant is False
        assert "code" in result.missing_elements

    def test_us_core_unsupported_resource_type(self, validator: FHIRValidator):
        resource = {"resourceType": "Encounter", "id": "enc-001"}
        result = validator.check_us_core_conformance(resource)
        assert result.is_conformant is False
        assert any("Supported" in i.message for i in result.issues)

    def test_us_core_must_support_generates_info(self, validator: FHIRValidator):
        """Must-support elements that are absent produce information-level issues."""
        patient = _make_patient()
        result = validator.check_us_core_conformance(patient)
        assert result.is_conformant is True
        info_issues = [
            i for i in result.issues if i.severity == IssueSeverity.INFORMATION
        ]
        must_support_paths = {i.path for i in info_issues}
        assert "address" in must_support_paths or "telecom" in must_support_paths


# ===========================================================================
# 6. API endpoint tests
# ===========================================================================

class TestFHIRValidationAPI:
    """Tests for the FHIR validation API endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client with the FHIR validation router."""
        from fastapi import FastAPI
        from app.api.fhir_validation import router

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        return TestClient(app)

    def test_validate_endpoint_valid_resource(self, client: TestClient):
        response = client.post(
            "/api/v1/fhir/validate",
            json={"resource": _make_patient()},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True
        assert data["resource_type"] == "Patient"

    def test_validate_endpoint_invalid_resource(self, client: TestClient):
        response = client.post(
            "/api/v1/fhir/validate",
            json={"resource": {"id": "no-type"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is False

    def test_validate_bundle_endpoint(self, client: TestClient):
        response = client.post(
            "/api/v1/fhir/validate-bundle",
            json={"bundle": _make_bundle()},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_resources"] == 3
        assert data["valid_count"] == 3

    def test_us_core_check_endpoint_valid(self, client: TestClient):
        response = client.post(
            "/api/v1/fhir/us-core-check",
            json={"resource": _make_patient()},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_conformant"] is True
        assert "us-core-patient" in data["profile"]

    def test_us_core_check_endpoint_invalid(self, client: TestClient):
        patient = _make_patient()
        del patient["gender"]
        response = client.post(
            "/api/v1/fhir/us-core-check",
            json={"resource": patient},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_conformant"] is False
        assert "gender" in data["missing_elements"]
