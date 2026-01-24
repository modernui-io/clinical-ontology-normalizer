"""FHIR R4 Terminology Services conformance tests.

Tests verify that all 6 FHIR operations match the R4 spec:
- Response structure (Parameters resource format)
- Required fields present
- Content-type headers correct
- Error handling for invalid inputs
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def _mock_service():
    """Create a mock FHIR terminology service."""
    svc = MagicMock()
    svc.lookup.return_value = {
        "name": "Diabetes mellitus",
        "system": "http://snomed.info/sct",
        "code": "73211009",
        "display": "Diabetes mellitus",
        "designations": [],
        "properties": [],
    }
    svc.validate_code.return_value = {
        "result": True,
        "display": "Diabetes mellitus",
        "system": "http://snomed.info/sct",
        "code": "73211009",
    }
    svc.expand.return_value = {
        "contains": [
            {"system": "http://snomed.info/sct", "code": "73211009", "display": "DM"}
        ],
        "total": 1,
    }
    svc.translate.return_value = {
        "result": True,
        "matches": [
            {"equivalence": "equivalent", "concept": {"system": "icd10", "code": "E11.9"}}
        ],
    }
    svc.subsumes.return_value = {"outcome": "subsumes"}
    svc.closure.return_value = {
        "name": "test-closure",
        "relationships": [],
    }
    svc.get_code_system.return_value = {
        "resourceType": "CodeSystem",
        "id": "snomed-ct",
        "url": "http://snomed.info/sct",
        "name": "SNOMED CT",
        "status": "active",
        "content": "complete",
    }
    svc.get_value_set.return_value = {
        "resourceType": "ValueSet",
        "id": "common-conditions",
        "url": "http://example.org/ValueSet/common-conditions",
        "status": "active",
    }
    svc.get_stats.return_value = {"code_systems": {"snomed-ct": {}}}
    return svc


# ============================================================================
# $lookup Conformance Tests
# ============================================================================


class TestLookupConformance:
    """Test $lookup operation conformance with FHIR R4 spec."""

    @patch("app.api.terminology.get_fhir_terminology_service")
    def test_lookup_returns_parameters_resource(self, mock_svc, client):
        mock_svc.return_value = _mock_service()

        with patch("app.api.terminology.FHIRParametersBuilder.build_lookup_parameters") as mock_build:
            mock_build.return_value = {
                "resourceType": "Parameters",
                "parameter": [
                    {"name": "name", "valueString": "Diabetes mellitus"},
                    {"name": "display", "valueString": "Diabetes mellitus"},
                ],
            }
            response = client.post(
                "/api/v1/fhir/CodeSystem/$lookup",
                json={"system": "http://snomed.info/sct", "code": "73211009"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["resourceType"] == "Parameters"
        assert "parameter" in data

    @patch("app.api.terminology.get_fhir_terminology_service")
    def test_lookup_content_type_json(self, mock_svc, client):
        mock_svc.return_value = _mock_service()

        with patch("app.api.terminology.FHIRParametersBuilder.build_lookup_parameters") as mock_build:
            mock_build.return_value = {"resourceType": "Parameters", "parameter": []}
            response = client.post(
                "/api/v1/fhir/CodeSystem/$lookup",
                json={"system": "http://snomed.info/sct", "code": "73211009"},
            )

        assert "application/json" in response.headers["content-type"]

    @patch("app.api.terminology.get_fhir_terminology_service")
    def test_lookup_not_found_returns_operation_outcome(self, mock_svc, client):
        svc = _mock_service()
        svc.lookup.return_value = None
        mock_svc.return_value = svc

        response = client.post(
            "/api/v1/fhir/CodeSystem/$lookup",
            json={"system": "http://snomed.info/sct", "code": "INVALID"},
        )

        assert response.status_code == 404

    def test_lookup_missing_required_fields(self, client):
        response = client.post(
            "/api/v1/fhir/CodeSystem/$lookup",
            json={"system": "http://snomed.info/sct"},  # missing code
        )
        assert response.status_code == 422


# ============================================================================
# $validate-code Conformance Tests
# ============================================================================


class TestValidateCodeConformance:
    """Test $validate-code operation conformance."""

    @patch("app.api.terminology.get_fhir_terminology_service")
    def test_validate_returns_parameters(self, mock_svc, client):
        mock_svc.return_value = _mock_service()

        with patch("app.api.terminology.FHIRParametersBuilder.build_validate_code_parameters") as mock_build:
            mock_build.return_value = {
                "resourceType": "Parameters",
                "parameter": [
                    {"name": "result", "valueBoolean": True},
                    {"name": "display", "valueString": "Diabetes mellitus"},
                ],
            }
            response = client.post(
                "/api/v1/fhir/CodeSystem/$validate-code",
                json={"system": "http://snomed.info/sct", "code": "73211009"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["resourceType"] == "Parameters"

    @patch("app.api.terminology.get_fhir_terminology_service")
    def test_validate_has_result_parameter(self, mock_svc, client):
        mock_svc.return_value = _mock_service()

        with patch("app.api.terminology.FHIRParametersBuilder.build_validate_code_parameters") as mock_build:
            mock_build.return_value = {
                "resourceType": "Parameters",
                "parameter": [{"name": "result", "valueBoolean": True}],
            }
            response = client.post(
                "/api/v1/fhir/CodeSystem/$validate-code",
                json={"system": "http://snomed.info/sct", "code": "73211009"},
            )

        data = response.json()
        result_params = [p for p in data["parameter"] if p["name"] == "result"]
        assert len(result_params) == 1
        assert "valueBoolean" in result_params[0]

    def test_validate_missing_code(self, client):
        response = client.post(
            "/api/v1/fhir/CodeSystem/$validate-code",
            json={"system": "http://snomed.info/sct"},
        )
        assert response.status_code == 422


# ============================================================================
# $expand Conformance Tests
# ============================================================================


class TestExpandConformance:
    """Test $expand operation conformance."""

    @patch("app.api.terminology.get_fhir_terminology_service")
    def test_expand_returns_valueset(self, mock_svc, client):
        mock_svc.return_value = _mock_service()

        with patch("app.api.terminology.FHIRParametersBuilder.build_expansion_valueset") as mock_build:
            mock_build.return_value = {
                "resourceType": "ValueSet",
                "expansion": {
                    "total": 1,
                    "offset": 0,
                    "contains": [
                        {"system": "http://snomed.info/sct", "code": "73211009", "display": "DM"}
                    ],
                },
            }
            response = client.post(
                "/api/v1/fhir/ValueSet/$expand",
                json={"url": "http://example.org/ValueSet/test"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["resourceType"] == "ValueSet"
        assert "expansion" in data

    @patch("app.api.terminology.get_fhir_terminology_service")
    def test_expand_not_found(self, mock_svc, client):
        svc = _mock_service()
        svc.expand.return_value = None
        mock_svc.return_value = svc

        response = client.post(
            "/api/v1/fhir/ValueSet/$expand",
            json={"url": "http://example.org/ValueSet/nonexistent"},
        )
        assert response.status_code == 404

    def test_expand_missing_url(self, client):
        response = client.post(
            "/api/v1/fhir/ValueSet/$expand",
            json={},
        )
        assert response.status_code == 422


# ============================================================================
# $translate Conformance Tests
# ============================================================================


class TestTranslateConformance:
    """Test $translate operation conformance."""

    @patch("app.api.terminology.get_fhir_terminology_service")
    def test_translate_returns_parameters(self, mock_svc, client):
        mock_svc.return_value = _mock_service()

        with patch("app.api.terminology.FHIRParametersBuilder.build_translate_parameters") as mock_build:
            mock_build.return_value = {
                "resourceType": "Parameters",
                "parameter": [
                    {"name": "result", "valueBoolean": True},
                    {"name": "match", "part": [
                        {"name": "equivalence", "valueCode": "equivalent"},
                        {"name": "concept", "valueCoding": {"code": "E11.9"}},
                    ]},
                ],
            }
            response = client.post(
                "/api/v1/fhir/ConceptMap/$translate",
                json={
                    "system": "http://snomed.info/sct",
                    "code": "73211009",
                    "targetSystem": "http://hl7.org/fhir/sid/icd-10-cm",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["resourceType"] == "Parameters"

    def test_translate_missing_target_system(self, client):
        response = client.post(
            "/api/v1/fhir/ConceptMap/$translate",
            json={"system": "http://snomed.info/sct", "code": "73211009"},
        )
        assert response.status_code == 422


# ============================================================================
# $subsumes Conformance Tests
# ============================================================================


class TestSubsumesConformance:
    """Test $subsumes operation conformance."""

    @patch("app.api.terminology.get_fhir_terminology_service")
    def test_subsumes_returns_parameters(self, mock_svc, client):
        mock_svc.return_value = _mock_service()

        with patch("app.api.terminology.FHIRParametersBuilder.build_subsumes_parameters") as mock_build:
            mock_build.return_value = {
                "resourceType": "Parameters",
                "parameter": [{"name": "outcome", "valueCode": "subsumes"}],
            }
            response = client.post(
                "/api/v1/fhir/CodeSystem/$subsumes",
                json={
                    "system": "http://snomed.info/sct",
                    "codeA": "73211009",
                    "codeB": "46635009",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["resourceType"] == "Parameters"
        outcomes = [p for p in data["parameter"] if p["name"] == "outcome"]
        assert len(outcomes) == 1

    def test_subsumes_missing_codeB(self, client):
        response = client.post(
            "/api/v1/fhir/CodeSystem/$subsumes",
            json={"system": "http://snomed.info/sct", "codeA": "73211009"},
        )
        assert response.status_code == 422


# ============================================================================
# $closure Conformance Tests
# ============================================================================


class TestClosureConformance:
    """Test $closure operation conformance."""

    @patch("app.api.terminology.get_fhir_terminology_service")
    def test_closure_returns_concept_map(self, mock_svc, client):
        mock_svc.return_value = _mock_service()

        with patch("app.api.terminology.FHIRParametersBuilder.build_closure_concept_map") as mock_build:
            mock_build.return_value = {
                "resourceType": "ConceptMap",
                "name": "test-closure",
                "status": "active",
            }
            response = client.post(
                "/api/v1/fhir/ConceptMap/$closure",
                json={
                    "name": "test-closure",
                    "concept": [
                        {"system": "http://snomed.info/sct", "code": "73211009", "display": "DM"},
                    ],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["resourceType"] == "ConceptMap"

    @patch("app.api.terminology.get_fhir_terminology_service")
    def test_closure_empty_concepts_rejected(self, mock_svc, client):
        mock_svc.return_value = _mock_service()

        response = client.post(
            "/api/v1/fhir/ConceptMap/$closure",
            json={"name": "test", "concept": []},
        )
        assert response.status_code == 400


# ============================================================================
# Response Content-Type Tests
# ============================================================================


class TestContentTypeHeaders:
    """Test that all responses have correct content-type."""

    @patch("app.api.terminology.get_fhir_terminology_service")
    def test_all_operations_return_json(self, mock_svc, client):
        mock_svc.return_value = _mock_service()

        endpoints = [
            ("/api/v1/fhir/CodeSystem/$lookup", {"system": "test", "code": "test"}),
            ("/api/v1/fhir/CodeSystem/$validate-code", {"system": "test", "code": "test"}),
            ("/api/v1/fhir/ValueSet/$expand", {"url": "http://test.org/vs"}),
            (
                "/api/v1/fhir/ConceptMap/$translate",
                {"system": "test", "code": "test", "targetSystem": "target"},
            ),
            ("/api/v1/fhir/CodeSystem/$subsumes", {"system": "test", "codeA": "a", "codeB": "b"}),
        ]

        # Mock all builders to return valid responses
        with patch("app.api.terminology.FHIRParametersBuilder") as MockBuilder:
            MockBuilder.build_lookup_parameters.return_value = {"resourceType": "Parameters", "parameter": []}
            MockBuilder.build_validate_code_parameters.return_value = {"resourceType": "Parameters", "parameter": []}
            MockBuilder.build_expansion_valueset.return_value = {"resourceType": "ValueSet", "expansion": {}}
            MockBuilder.build_translate_parameters.return_value = {"resourceType": "Parameters", "parameter": []}
            MockBuilder.build_subsumes_parameters.return_value = {"resourceType": "Parameters", "parameter": []}

            for url, body in endpoints:
                response = client.post(url, json=body)
                assert "application/json" in response.headers.get("content-type", ""), (
                    f"Expected JSON content-type for {url}"
                )
