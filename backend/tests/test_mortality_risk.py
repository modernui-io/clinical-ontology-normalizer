"""Tests for mortality risk API endpoints.

Tests verify:
- POST /risk/mortality calculates risk score
- GET /risk/mortality/{patient_id} retrieves stored risk
- POST /risk/charlson calculates Charlson index
- Invalid inputs return proper errors
"""

import pytest
from enum import Enum
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.api.risk import router


def create_test_app():
    """Create a minimal FastAPI app with just the risk router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client():
    app = create_test_app()
    return TestClient(app, raise_server_exceptions=False)


# Mock versions of the service classes
class MockAdmissionType(str, Enum):
    ELECTIVE = "elective"
    EMERGENCY = "emergency"
    URGENT = "urgent"
    TRANSFER = "transfer"


class MockMortalityFeatures(BaseModel):
    age: int = Field(..., ge=0, le=120)
    admission_type: MockAdmissionType = MockAdmissionType.EMERGENCY
    charlson_score: int = Field(default=0, ge=0)
    elixhauser_score: int = 0
    icu_admission: bool = False
    mechanical_ventilation: bool = False
    vasopressor_use: bool = False
    creatinine: float | None = None
    bilirubin: float | None = None
    albumin: float | None = None
    platelets: float | None = None
    inr: float | None = None


def _mock_risk_score(score=0.35, tier="medium", confidence=0.72, percentile=65.0):
    """Create a mock RiskScore."""
    result = MagicMock()
    result.score = score
    result.tier = MagicMock()
    result.tier.value = tier
    result.confidence = confidence
    result.percentile = percentile
    return result


def _make_imports_mock(service_mock=None, charlson_mock=None):
    """Create a mock _get_risk_imports that returns testable objects."""
    svc_factory = MagicMock()
    if service_mock:
        svc_factory.return_value = service_mock

    calc_fn = charlson_mock or MagicMock(return_value=0)

    def mock_imports():
        return MockAdmissionType, MockMortalityFeatures, calc_fn, svc_factory

    return mock_imports, svc_factory, calc_fn


class TestCalculateMortalityRisk:
    """Test POST /risk/mortality endpoint."""

    def test_returns_200(self, client):
        svc = MagicMock()
        svc.assess_mortality_risk.return_value = _mock_risk_score()
        mock_imports, _, _ = _make_imports_mock(service_mock=svc)

        with patch("app.api.risk._get_risk_imports", mock_imports):
            response = client.post(
                "/risk/mortality",
                json={"patient_id": "P12345", "age": 72, "charlson_score": 4},
            )
        assert response.status_code == 200

    def test_returns_risk_fields(self, client):
        svc = MagicMock()
        svc.assess_mortality_risk.return_value = _mock_risk_score(
            score=0.45, tier="high", confidence=0.8
        )
        mock_imports, _, _ = _make_imports_mock(service_mock=svc)

        with patch("app.api.risk._get_risk_imports", mock_imports):
            data = client.post(
                "/risk/mortality",
                json={
                    "patient_id": "P12345",
                    "age": 72,
                    "charlson_score": 4,
                    "elixhauser_score": 3,
                    "icu_admission": True,
                },
            ).json()

        assert data["patient_id"] == "P12345"
        assert data["risk_score"] == 0.45
        assert data["risk_tier"] == "high"
        assert data["confidence"] == 0.8
        assert data["charlson_score"] == 4
        assert data["elixhauser_score"] == 3

    def test_admission_type_parsed(self, client):
        svc = MagicMock()
        svc.assess_mortality_risk.return_value = _mock_risk_score()
        mock_imports, _, _ = _make_imports_mock(service_mock=svc)

        with patch("app.api.risk._get_risk_imports", mock_imports):
            response = client.post(
                "/risk/mortality",
                json={"patient_id": "P1", "age": 65, "admission_type": "elective"},
            )
        assert response.status_code == 200

    def test_invalid_admission_type(self, client):
        svc = MagicMock()
        mock_imports, _, _ = _make_imports_mock(service_mock=svc)

        with patch("app.api.risk._get_risk_imports", mock_imports):
            response = client.post(
                "/risk/mortality",
                json={"patient_id": "P1", "age": 65, "admission_type": "invalid_type"},
            )
        assert response.status_code == 400
        assert "admission_type" in response.json()["detail"]

    def test_missing_required_fields(self, client):
        response = client.post("/risk/mortality", json={})
        assert response.status_code == 422

    def test_age_out_of_range(self, client):
        response = client.post(
            "/risk/mortality",
            json={"patient_id": "P1", "age": 200},
        )
        assert response.status_code == 422

    def test_with_lab_values(self, client):
        svc = MagicMock()
        svc.assess_mortality_risk.return_value = _mock_risk_score(score=0.6, tier="high")
        mock_imports, _, _ = _make_imports_mock(service_mock=svc)

        with patch("app.api.risk._get_risk_imports", mock_imports):
            data = client.post(
                "/risk/mortality",
                json={
                    "patient_id": "P1",
                    "age": 80,
                    "charlson_score": 6,
                    "creatinine": 3.5,
                    "bilirubin": 4.0,
                    "albumin": 2.0,
                    "icu_admission": True,
                    "mechanical_ventilation": True,
                },
            ).json()

        assert data["risk_score"] == 0.6
        assert data["risk_tier"] == "high"


class TestGetMortalityRisk:
    """Test GET /risk/mortality/{patient_id} endpoint."""

    def test_returns_stored_risk(self, client):
        svc = MagicMock()
        svc.get_risk_history.return_value = [
            {"score": 0.35, "tier": "medium", "timestamp": "2026-01-24T10:00:00"}
        ]
        mock_imports, _, _ = _make_imports_mock(service_mock=svc)

        with patch("app.api.risk._get_risk_imports", mock_imports):
            response = client.get("/risk/mortality/P12345")
        assert response.status_code == 200
        data = response.json()
        assert data["patient_id"] == "P12345"
        assert data["risk_score"] == 0.35

    def test_not_found(self, client):
        svc = MagicMock()
        svc.get_risk_history.return_value = []
        mock_imports, _, _ = _make_imports_mock(service_mock=svc)

        with patch("app.api.risk._get_risk_imports", mock_imports):
            response = client.get("/risk/mortality/unknown_patient")
        assert response.status_code == 404


class TestCharlsonCalculation:
    """Test POST /risk/charlson endpoint."""

    def test_returns_score(self, client):
        calc_fn = MagicMock(return_value=5)
        mock_imports, _, _ = _make_imports_mock(charlson_mock=calc_fn)

        with patch("app.api.risk._get_risk_imports", mock_imports):
            response = client.post(
                "/risk/charlson",
                json={"icd10_codes": ["E11.9", "I10", "N18.3", "J44.1"]},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["score"] == 5
        assert data["icd10_codes_provided"] == 4

    def test_empty_codes(self, client):
        calc_fn = MagicMock(return_value=0)
        mock_imports, _, _ = _make_imports_mock(charlson_mock=calc_fn)

        with patch("app.api.risk._get_risk_imports", mock_imports):
            response = client.post(
                "/risk/charlson",
                json={"icd10_codes": []},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["score"] == 0

    def test_missing_codes_field(self, client):
        response = client.post("/risk/charlson", json={})
        assert response.status_code == 422
