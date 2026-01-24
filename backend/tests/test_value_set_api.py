"""Tests for Value Set CRUD API endpoints.

Tests verify:
- GET /valuesets returns paginated list
- POST /valuesets creates a new value set
- GET /valuesets/{id} returns a value set
- PUT /valuesets/{id} updates a value set
- DELETE /valuesets/{id} deletes a value set
- POST /valuesets/{id}/expand expands to codes
- POST /valuesets/{id}/validate checks code membership
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, UTC
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.valuesets import router


def create_test_app():
    """Create a minimal FastAPI app with just the valuesets router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client():
    app = create_test_app()
    return TestClient(app, raise_server_exceptions=False)


def _mock_value_set(
    vs_id="vs-001",
    name="TestValueSet",
    status="active",
    vs_type="extensional",
    codes=None,
    rules=None,
):
    """Create a mock value set object."""
    vs = MagicMock()
    vs.id = vs_id
    vs.name = name
    vs.title = "Test Value Set"
    vs.description = "A test value set"
    vs.url = "http://example.org/vs/test"
    vs.version = "1.0.0"

    status_mock = MagicMock()
    status_mock.value = status
    vs.status = status_mock

    type_mock = MagicMock()
    type_mock.value = vs_type
    vs.value_set_type = type_mock

    vs.codes = codes or []
    vs.rules = rules or []
    vs.publisher = "Test Publisher"
    vs.purpose = "Testing"
    vs.copyright = None
    vs.experimental = False
    vs.immutable = False
    vs.created_at = datetime(2026, 1, 24, 10, 0, 0, tzinfo=UTC)
    vs.updated_at = datetime(2026, 1, 24, 10, 0, 0, tzinfo=UTC)
    return vs


def _mock_expansion_result():
    """Create a mock expansion result."""
    code = MagicMock()
    code.system = "http://snomed.info/sct"
    code.code = "73211009"
    code.display = "Diabetes mellitus"
    code.version = None
    code.inactive = False
    code.abstract = False
    return code


class TestListValueSets:
    """Test GET /valuesets endpoint."""

    @patch("app.api.valuesets.get_value_set_service")
    def test_list_returns_200(self, mock_svc, client):
        svc = MagicMock()
        svc.list.return_value = ([_mock_value_set()], 1)
        mock_svc.return_value = svc

        response = client.get("/valuesets")
        assert response.status_code == 200

    @patch("app.api.valuesets.get_value_set_service")
    def test_list_response_structure(self, mock_svc, client):
        svc = MagicMock()
        svc.list.return_value = ([_mock_value_set()], 1)
        mock_svc.return_value = svc

        data = client.get("/valuesets").json()
        assert "value_sets" in data
        assert "total" in data
        assert "offset" in data
        assert "limit" in data
        assert data["total"] == 1

    @patch("app.api.valuesets.get_value_set_service")
    def test_list_with_status_filter(self, mock_svc, client):
        svc = MagicMock()
        svc.list.return_value = ([], 0)
        mock_svc.return_value = svc

        response = client.get("/valuesets", params={"status": "active"})
        assert response.status_code == 200

    @patch("app.api.valuesets.get_value_set_service")
    def test_list_with_invalid_status(self, mock_svc, client):
        mock_svc.return_value = MagicMock()

        response = client.get("/valuesets", params={"status": "bogus"})
        assert response.status_code == 400

    @patch("app.api.valuesets.get_value_set_service")
    def test_list_pagination(self, mock_svc, client):
        svc = MagicMock()
        svc.list.return_value = ([], 0)
        mock_svc.return_value = svc

        client.get("/valuesets", params={"offset": 10, "limit": 5})
        call_kwargs = svc.list.call_args.kwargs
        assert call_kwargs["offset"] == 10
        assert call_kwargs["limit"] == 5


class TestCreateValueSet:
    """Test POST /valuesets endpoint."""

    @patch("app.api.valuesets.get_value_set_service")
    def test_create_returns_200(self, mock_svc, client):
        svc = MagicMock()
        svc.create.return_value = _mock_value_set()
        mock_svc.return_value = svc

        response = client.post(
            "/valuesets",
            json={
                "name": "TestVS",
                "value_set_type": "extensional",
                "status": "draft",
            },
        )
        assert response.status_code == 200

    @patch("app.api.valuesets.get_value_set_service")
    def test_create_with_codes(self, mock_svc, client):
        codes = [MagicMock()]
        codes[0].system = "http://snomed.info/sct"
        codes[0].code = "73211009"

        svc = MagicMock()
        svc.create.return_value = _mock_value_set(codes=codes)
        mock_svc.return_value = svc

        response = client.post(
            "/valuesets",
            json={
                "name": "DiabetesVS",
                "value_set_type": "extensional",
                "codes": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "73211009",
                        "display": "Diabetes mellitus",
                    }
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code_count"] == 1

    @patch("app.api.valuesets.get_value_set_service")
    def test_create_invalid_status(self, mock_svc, client):
        mock_svc.return_value = MagicMock()

        response = client.post(
            "/valuesets",
            json={
                "name": "TestVS",
                "value_set_type": "extensional",
                "status": "invalid",
            },
        )
        assert response.status_code == 400

    def test_create_missing_name(self, client):
        response = client.post(
            "/valuesets",
            json={"value_set_type": "extensional"},
        )
        assert response.status_code == 422


class TestGetValueSet:
    """Test GET /valuesets/{id} endpoint."""

    @patch("app.api.valuesets.get_value_set_service")
    def test_get_returns_200(self, mock_svc, client):
        svc = MagicMock()
        svc.get.return_value = _mock_value_set()
        mock_svc.return_value = svc

        response = client.get("/valuesets/vs-001")
        assert response.status_code == 200

    @patch("app.api.valuesets.get_value_set_service")
    def test_get_response_fields(self, mock_svc, client):
        svc = MagicMock()
        svc.get.return_value = _mock_value_set()
        mock_svc.return_value = svc

        data = client.get("/valuesets/vs-001").json()
        assert data["id"] == "vs-001"
        assert data["name"] == "TestValueSet"
        assert data["status"] == "active"
        assert data["value_set_type"] == "extensional"

    @patch("app.api.valuesets.get_value_set_service")
    def test_get_not_found(self, mock_svc, client):
        svc = MagicMock()
        svc.get.return_value = None
        mock_svc.return_value = svc

        response = client.get("/valuesets/nonexistent")
        assert response.status_code == 404


class TestUpdateValueSet:
    """Test PUT /valuesets/{id} endpoint."""

    @patch("app.api.valuesets.get_value_set_service")
    def test_update_returns_200(self, mock_svc, client):
        svc = MagicMock()
        svc.update.return_value = _mock_value_set(name="Updated")
        mock_svc.return_value = svc

        response = client.put(
            "/valuesets/vs-001",
            json={"name": "Updated"},
        )
        assert response.status_code == 200

    @patch("app.api.valuesets.get_value_set_service")
    def test_update_not_found(self, mock_svc, client):
        svc = MagicMock()
        svc.update.return_value = None
        mock_svc.return_value = svc

        response = client.put(
            "/valuesets/nonexistent",
            json={"name": "Updated"},
        )
        assert response.status_code == 404


class TestDeleteValueSet:
    """Test DELETE /valuesets/{id} endpoint."""

    @patch("app.api.valuesets.get_value_set_service")
    def test_delete_returns_200(self, mock_svc, client):
        svc = MagicMock()
        svc.delete.return_value = True
        mock_svc.return_value = svc

        response = client.delete("/valuesets/vs-001")
        assert response.status_code == 200

    @patch("app.api.valuesets.get_value_set_service")
    def test_delete_not_found(self, mock_svc, client):
        svc = MagicMock()
        svc.delete.return_value = False
        mock_svc.return_value = svc

        response = client.delete("/valuesets/nonexistent")
        assert response.status_code == 404


class TestExpandValueSet:
    """Test POST /valuesets/{id}/expand endpoint."""

    @patch("app.api.valuesets.get_value_set_service")
    def test_expand_returns_200(self, mock_svc, client):
        svc = MagicMock()
        expansion = MagicMock()
        expansion.value_set_id = "vs-001"
        expansion.value_set_url = "http://example.org/vs/test"
        expansion.timestamp = datetime(2026, 1, 24, 10, 0, 0, tzinfo=UTC)
        expansion.total = 1
        expansion.offset = 0
        expansion.codes = [_mock_expansion_result()]
        svc.expand.return_value = expansion
        mock_svc.return_value = svc

        response = client.post(
            "/valuesets/vs-001/expand",
            json={},
        )
        assert response.status_code == 200

    @patch("app.api.valuesets.get_value_set_service")
    def test_expand_response_structure(self, mock_svc, client):
        svc = MagicMock()
        expansion = MagicMock()
        expansion.value_set_id = "vs-001"
        expansion.value_set_url = "http://example.org/vs/test"
        expansion.timestamp = datetime(2026, 1, 24, 10, 0, 0, tzinfo=UTC)
        expansion.total = 1
        expansion.offset = 0
        expansion.codes = [_mock_expansion_result()]
        svc.expand.return_value = expansion
        mock_svc.return_value = svc

        data = client.post("/valuesets/vs-001/expand", json={}).json()
        assert "value_set_id" in data
        assert "codes" in data
        assert "total" in data
        assert data["total"] == 1

    @patch("app.api.valuesets.get_value_set_service")
    def test_expand_not_found(self, mock_svc, client):
        svc = MagicMock()
        svc.expand.return_value = None
        mock_svc.return_value = svc

        response = client.post("/valuesets/nonexistent/expand", json={})
        assert response.status_code == 404


class TestValidateCode:
    """Test POST /valuesets/{id}/validate endpoint."""

    @patch("app.api.valuesets.get_value_set_service")
    def test_validate_valid_code(self, mock_svc, client):
        svc = MagicMock()
        result = MagicMock()
        result.valid = True
        result.message = "Code is a member of the value set"
        result.display = "Diabetes mellitus"
        result.code = "73211009"
        result.system = "http://snomed.info/sct"
        svc.validate_code.return_value = result
        mock_svc.return_value = svc

        response = client.post(
            "/valuesets/vs-001/validate",
            json={
                "system": "http://snomed.info/sct",
                "code": "73211009",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["display"] == "Diabetes mellitus"

    @patch("app.api.valuesets.get_value_set_service")
    def test_validate_invalid_code(self, mock_svc, client):
        svc = MagicMock()
        result = MagicMock()
        result.valid = False
        result.message = "Code not found in value set"
        result.display = None
        result.code = "99999"
        result.system = "http://snomed.info/sct"
        svc.validate_code.return_value = result
        mock_svc.return_value = svc

        response = client.post(
            "/valuesets/vs-001/validate",
            json={
                "system": "http://snomed.info/sct",
                "code": "99999",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False

    @patch("app.api.valuesets.get_value_set_service")
    def test_validate_value_set_not_found(self, mock_svc, client):
        """When value set not found, service returns valid=False."""
        svc = MagicMock()
        result = MagicMock()
        result.valid = False
        result.message = "Value set 'nonexistent' not found"
        result.display = None
        result.code = "73211009"
        result.system = "http://snomed.info/sct"
        svc.validate_code.return_value = result
        mock_svc.return_value = svc

        response = client.post(
            "/valuesets/nonexistent/validate",
            json={
                "system": "http://snomed.info/sct",
                "code": "73211009",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False

    def test_validate_missing_fields(self, client):
        response = client.post(
            "/valuesets/vs-001/validate",
            json={},
        )
        assert response.status_code == 422
