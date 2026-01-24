"""Tests for terminology operation-level pagination.

Tests verify that _count and _offset parameters work correctly
on $lookup, $validate-code, $translate, and $subsumes GET endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def _mock_parameters_result(count: int = 5):
    """Create a mock FHIR Parameters response with N parameters."""
    return {
        "resourceType": "Parameters",
        "parameter": [{"name": f"param{i}", "valueString": f"value{i}"} for i in range(count)],
    }


class TestLookupPagination:
    """Test pagination on $lookup GET endpoint."""

    @patch("app.api.terminology.get_fhir_terminology_service")
    def test_lookup_default_pagination(self, mock_svc, client):
        svc = MagicMock()
        svc.lookup.return_value = {"display": "test"}
        mock_svc.return_value = svc

        with patch("app.api.terminology.FHIRParametersBuilder.build_lookup_parameters") as mock_build:
            mock_build.return_value = _mock_parameters_result(10)
            response = client.get(
                "/api/v1/fhir/CodeSystem/$lookup",
                params={"system": "http://snomed.info/sct", "code": "73211009"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "_pagination" in data
        assert data["_pagination"]["total"] == 10

    @patch("app.api.terminology.get_fhir_terminology_service")
    def test_lookup_with_count(self, mock_svc, client):
        svc = MagicMock()
        svc.lookup.return_value = {"display": "test"}
        mock_svc.return_value = svc

        with patch("app.api.terminology.FHIRParametersBuilder.build_lookup_parameters") as mock_build:
            mock_build.return_value = _mock_parameters_result(10)
            response = client.get(
                "/api/v1/fhir/CodeSystem/$lookup",
                params={"system": "http://snomed.info/sct", "code": "73211009", "_count": "3"},
            )

        data = response.json()
        assert len(data["parameter"]) == 3
        assert data["_pagination"]["count"] == 3
        assert data["_pagination"]["total"] == 10

    @patch("app.api.terminology.get_fhir_terminology_service")
    def test_lookup_with_offset(self, mock_svc, client):
        svc = MagicMock()
        svc.lookup.return_value = {"display": "test"}
        mock_svc.return_value = svc

        with patch("app.api.terminology.FHIRParametersBuilder.build_lookup_parameters") as mock_build:
            mock_build.return_value = _mock_parameters_result(10)
            response = client.get(
                "/api/v1/fhir/CodeSystem/$lookup",
                params={
                    "system": "http://snomed.info/sct",
                    "code": "73211009",
                    "_offset": "5",
                    "_count": "3",
                },
            )

        data = response.json()
        assert len(data["parameter"]) == 3
        assert data["_pagination"]["offset"] == 5

    @patch("app.api.terminology.get_fhir_terminology_service")
    def test_lookup_offset_beyond_total(self, mock_svc, client):
        svc = MagicMock()
        svc.lookup.return_value = {"display": "test"}
        mock_svc.return_value = svc

        with patch("app.api.terminology.FHIRParametersBuilder.build_lookup_parameters") as mock_build:
            mock_build.return_value = _mock_parameters_result(5)
            response = client.get(
                "/api/v1/fhir/CodeSystem/$lookup",
                params={
                    "system": "http://snomed.info/sct",
                    "code": "73211009",
                    "_offset": "10",
                },
            )

        data = response.json()
        assert len(data["parameter"]) == 0


class TestValidateCodePagination:
    """Test pagination on $validate-code GET endpoint."""

    @patch("app.api.terminology.get_fhir_terminology_service")
    def test_validate_code_with_pagination(self, mock_svc, client):
        svc = MagicMock()
        svc.validate_code.return_value = {"result": True, "display": "Test"}
        mock_svc.return_value = svc

        with patch("app.api.terminology.FHIRParametersBuilder.build_validate_code_parameters") as mock_build:
            mock_build.return_value = _mock_parameters_result(4)
            response = client.get(
                "/api/v1/fhir/CodeSystem/$validate-code",
                params={"system": "http://snomed.info/sct", "code": "73211009", "_count": "2"},
            )

        data = response.json()
        assert len(data["parameter"]) == 2
        assert data["_pagination"]["total"] == 4


class TestTranslatePagination:
    """Test pagination on $translate GET endpoint."""

    @patch("app.api.terminology.get_fhir_terminology_service")
    def test_translate_with_pagination(self, mock_svc, client):
        svc = MagicMock()
        svc.translate.return_value = {"result": True, "matches": []}
        mock_svc.return_value = svc

        with patch("app.api.terminology.FHIRParametersBuilder.build_translate_parameters") as mock_build:
            mock_build.return_value = _mock_parameters_result(8)
            response = client.get(
                "/api/v1/fhir/ConceptMap/$translate",
                params={
                    "system": "http://snomed.info/sct",
                    "code": "73211009",
                    "targetSystem": "http://hl7.org/fhir/sid/icd-10-cm",
                    "_count": "3",
                    "_offset": "2",
                },
            )

        data = response.json()
        assert len(data["parameter"]) == 3
        assert data["_pagination"]["offset"] == 2


class TestSubsumesPagination:
    """Test pagination on $subsumes GET endpoint."""

    @patch("app.api.terminology.get_fhir_terminology_service")
    def test_subsumes_with_pagination(self, mock_svc, client):
        svc = MagicMock()
        svc.subsumes.return_value = {"outcome": "subsumes"}
        mock_svc.return_value = svc

        with patch("app.api.terminology.FHIRParametersBuilder.build_subsumes_parameters") as mock_build:
            mock_build.return_value = _mock_parameters_result(3)
            response = client.get(
                "/api/v1/fhir/CodeSystem/$subsumes",
                params={
                    "system": "http://snomed.info/sct",
                    "codeA": "73211009",
                    "codeB": "46635009",
                    "_count": "2",
                },
            )

        data = response.json()
        assert len(data["parameter"]) == 2
        assert data["_pagination"]["total"] == 3


class TestPaginationValidation:
    """Test that invalid pagination params are rejected."""

    def test_negative_offset_rejected(self, client):
        response = client.get(
            "/api/v1/fhir/CodeSystem/$lookup",
            params={"system": "test", "code": "test", "_offset": "-1"},
        )
        assert response.status_code == 422

    def test_zero_count_rejected(self, client):
        response = client.get(
            "/api/v1/fhir/CodeSystem/$lookup",
            params={"system": "test", "code": "test", "_count": "0"},
        )
        assert response.status_code == 422

    def test_count_over_max_rejected(self, client):
        response = client.get(
            "/api/v1/fhir/CodeSystem/$lookup",
            params={"system": "test", "code": "test", "_count": "1001"},
        )
        assert response.status_code == 422
