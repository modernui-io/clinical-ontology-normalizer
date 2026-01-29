"""Tests for prediction calibration API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.prediction_calibration_service import reset_prediction_calibration_service


class TestPredictionCalibrationList:
    """Test calibration listing endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_prediction_calibration_service()
        yield
        reset_prediction_calibration_service()

    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/predictions/calibration")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["calibrations"] == []

    @pytest.mark.asyncio
    async def test_list_methods(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/predictions/calibration/methods")

        assert response.status_code == 200
        data = response.json()
        methods = [m["value"] for m in data["methods"]]
        assert "platt" in methods
        assert "isotonic" in methods


class TestPredictionCalibrationFit:
    """Test calibration fitting."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_prediction_calibration_service()
        yield
        reset_prediction_calibration_service()

    @pytest.mark.asyncio
    async def test_fit_platt(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/predictions/calibration/readmission-risk-v1/fit",
                json={
                    "model_version": "1.0.0",
                    "method": "platt",
                    "y_true": [0, 0, 1, 1, 0, 1],
                    "y_pred": [0.05, 0.2, 0.65, 0.85, 0.3, 0.9],
                    "n_bins": 5,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["model_name"] == "readmission-risk-v1"
        assert data["model_version"] == "1.0.0"
        assert data["method"] == "platt"
        assert data["metrics"]["brier_score"] >= 0
        assert len(data["curve"]["prob_true"]) > 0

    @pytest.mark.asyncio
    async def test_fit_invalid_method(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/predictions/calibration/readmission-risk-v1/fit",
                json={
                    "model_version": "1.0.0",
                    "method": "invalid",
                    "y_true": [0, 1, 0, 1],
                    "y_pred": [0.2, 0.8, 0.3, 0.7],
                },
            )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_fit_length_mismatch(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/predictions/calibration/readmission-risk-v1/fit",
                json={
                    "model_version": "1.0.0",
                    "method": "platt",
                    "y_true": [0, 1, 0],
                    "y_pred": [0.2, 0.8],
                },
            )

        assert response.status_code == 400


class TestPredictionCalibrationApply:
    """Test calibration application."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_prediction_calibration_service()
        yield
        reset_prediction_calibration_service()

    @pytest.mark.asyncio
    async def test_apply_calibration(self, client):
        async with client as ac:
            await ac.post(
                "/api/v1/predictions/calibration/mortality-risk-v1/fit",
                json={
                    "model_version": "1.0.0",
                    "method": "isotonic",
                    "y_true": [0, 0, 1, 1, 1, 0],
                    "y_pred": [0.1, 0.2, 0.6, 0.8, 0.9, 0.3],
                },
            )
            response = await ac.post(
                "/api/v1/predictions/calibration/mortality-risk-v1/apply",
                json={"model_version": "1.0.0", "scores": [0.1, 0.5, 0.9]},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["calibrated_scores"]) == 3
        assert all(0 <= s <= 1 for s in data["calibrated_scores"])

    @pytest.mark.asyncio
    async def test_apply_missing_strict(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/predictions/calibration/unknown-model/apply",
                json={"model_version": "1.0.0", "scores": [0.2]},
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_apply_missing_non_strict(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/predictions/calibration/unknown-model/apply",
                json={"model_version": "1.0.0", "scores": [0.2], "strict": False},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["scores"] == data["calibrated_scores"]
