"""Tests for prediction audit API endpoints.

Tests verify:
- Prediction logging
- Audit retrieval and listing
- Outcome updates
- Feedback submission
- Drift metrics
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.prediction_audit_service import reset_prediction_audit_service


class TestPredictionAuditLog:
    """Test prediction logging endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_prediction_audit_service()
        yield
        reset_prediction_audit_service()

    @pytest.mark.asyncio
    async def test_log_prediction(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/predictions/audit",
                json={
                    "model_name": "mortality_risk",
                    "model_version": "1.0.0",
                    "prediction_type": "mortality",
                    "prediction_value": 0.75,
                    "inputs": [
                        {"feature_name": "age", "feature_value": 72, "feature_importance": 0.3},
                        {"feature_name": "charlson_score", "feature_value": 4, "feature_importance": 0.4},
                    ],
                    "patient_id": "P12345",
                    "prediction_confidence": 0.85,
                    "prediction_tier": "high",
                    "explanation": "High risk due to age and comorbidities",
                    "latency_ms": 42.5,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["model_name"] == "mortality_risk"
        assert data["prediction_value"] == 0.75
        assert len(data["inputs"]) == 2
        assert data["outcome"] == "pending"

    @pytest.mark.asyncio
    async def test_log_prediction_minimal(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/predictions/audit",
                json={
                    "model_name": "readmission_30day",
                    "prediction_type": "readmission",
                    "prediction_value": 0.35,
                    "inputs": [
                        {"feature_name": "los_days", "feature_value": 5},
                    ],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["model_name"] == "readmission_30day"
        assert data["prediction_confidence"] is None


class TestPredictionAuditList:
    """Test audit listing endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_prediction_audit_service()
        yield
        reset_prediction_audit_service()

    @pytest.mark.asyncio
    async def test_list_audits_empty(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/predictions/audit")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["predictions"] == []

    @pytest.mark.asyncio
    async def test_list_audits_with_data(self, client):
        async with client as ac:
            # Log some predictions
            await ac.post(
                "/api/v1/predictions/audit",
                json={
                    "model_name": "mortality_risk",
                    "prediction_type": "mortality",
                    "prediction_value": 0.5,
                    "inputs": [{"feature_name": "age", "feature_value": 60}],
                },
            )
            await ac.post(
                "/api/v1/predictions/audit",
                json={
                    "model_name": "mortality_risk",
                    "prediction_type": "mortality",
                    "prediction_value": 0.7,
                    "inputs": [{"feature_name": "age", "feature_value": 80}],
                },
            )

            response = await ac.get("/api/v1/predictions/audit")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_list_audits_filter_by_model(self, client):
        async with client as ac:
            # Log predictions for different models
            await ac.post(
                "/api/v1/predictions/audit",
                json={
                    "model_name": "mortality_risk",
                    "prediction_type": "mortality",
                    "prediction_value": 0.5,
                    "inputs": [{"feature_name": "age", "feature_value": 60}],
                },
            )
            await ac.post(
                "/api/v1/predictions/audit",
                json={
                    "model_name": "readmission_30day",
                    "prediction_type": "readmission",
                    "prediction_value": 0.3,
                    "inputs": [{"feature_name": "los", "feature_value": 3}],
                },
            )

            response = await ac.get(
                "/api/v1/predictions/audit",
                params={"model_name": "mortality_risk"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["predictions"][0]["model_name"] == "mortality_risk"


class TestPredictionAuditGet:
    """Test audit retrieval endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_prediction_audit_service()
        yield
        reset_prediction_audit_service()

    @pytest.mark.asyncio
    async def test_get_audit(self, client):
        async with client as ac:
            # Log a prediction
            create_response = await ac.post(
                "/api/v1/predictions/audit",
                json={
                    "model_name": "test_model",
                    "prediction_type": "test",
                    "prediction_value": 0.5,
                    "inputs": [{"feature_name": "x", "feature_value": 1}],
                },
            )
            audit_id = create_response.json()["id"]

            # Get the audit
            response = await ac.get(f"/api/v1/predictions/audit/{audit_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == audit_id

    @pytest.mark.asyncio
    async def test_get_audit_not_found(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/predictions/audit/nonexistent-id")

        assert response.status_code == 404


class TestPredictionAuditOutcome:
    """Test outcome update endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_prediction_audit_service()
        yield
        reset_prediction_audit_service()

    @pytest.mark.asyncio
    async def test_update_outcome(self, client):
        async with client as ac:
            # Log a prediction
            create_response = await ac.post(
                "/api/v1/predictions/audit",
                json={
                    "model_name": "test_model",
                    "prediction_type": "test",
                    "prediction_value": 0.8,
                    "inputs": [{"feature_name": "x", "feature_value": 1}],
                },
            )
            audit_id = create_response.json()["id"]

            # Update outcome
            response = await ac.put(
                f"/api/v1/predictions/audit/{audit_id}/outcome",
                json={"outcome": "correct"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["outcome"] == "correct"
        assert data["outcome_updated_at"] is not None

    @pytest.mark.asyncio
    async def test_update_outcome_invalid(self, client):
        async with client as ac:
            create_response = await ac.post(
                "/api/v1/predictions/audit",
                json={
                    "model_name": "test_model",
                    "prediction_type": "test",
                    "prediction_value": 0.5,
                    "inputs": [{"feature_name": "x", "feature_value": 1}],
                },
            )
            audit_id = create_response.json()["id"]

            response = await ac.put(
                f"/api/v1/predictions/audit/{audit_id}/outcome",
                json={"outcome": "invalid_outcome"},
            )

        assert response.status_code == 400


class TestPredictionAuditFeedback:
    """Test feedback endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_prediction_audit_service()
        yield
        reset_prediction_audit_service()

    @pytest.mark.asyncio
    async def test_add_feedback(self, client):
        async with client as ac:
            # Log a prediction
            create_response = await ac.post(
                "/api/v1/predictions/audit",
                json={
                    "model_name": "test_model",
                    "prediction_type": "test",
                    "prediction_value": 0.6,
                    "inputs": [{"feature_name": "x", "feature_value": 1}],
                },
            )
            audit_id = create_response.json()["id"]

            # Add feedback
            response = await ac.post(
                f"/api/v1/predictions/audit/{audit_id}/feedback",
                json={
                    "feedback_type": "thumbs_down",
                    "comment": "Prediction seemed too high",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["feedback_count"] == 1

    @pytest.mark.asyncio
    async def test_add_multiple_feedback(self, client):
        async with client as ac:
            create_response = await ac.post(
                "/api/v1/predictions/audit",
                json={
                    "model_name": "test_model",
                    "prediction_type": "test",
                    "prediction_value": 0.5,
                    "inputs": [{"feature_name": "x", "feature_value": 1}],
                },
            )
            audit_id = create_response.json()["id"]

            await ac.post(
                f"/api/v1/predictions/audit/{audit_id}/feedback",
                json={"feedback_type": "thumbs_up"},
            )
            response = await ac.post(
                f"/api/v1/predictions/audit/{audit_id}/feedback",
                json={"feedback_type": "comment", "comment": "Good prediction"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["feedback_count"] == 2


class TestPredictionAuditDrift:
    """Test drift metrics endpoint."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_prediction_audit_service()
        yield
        reset_prediction_audit_service()

    @pytest.mark.asyncio
    async def test_get_drift_metrics_empty(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/predictions/audit/drift/test_model")

        assert response.status_code == 200
        data = response.json()
        assert data["total_predictions"] == 0
        assert data["mean_confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_get_drift_metrics_with_data(self, client):
        async with client as ac:
            # Log some predictions
            for i in range(5):
                await ac.post(
                    "/api/v1/predictions/audit",
                    json={
                        "model_name": "drift_test_model",
                        "prediction_type": "test",
                        "prediction_value": 0.5 + i * 0.05,
                        "prediction_confidence": 0.8 + i * 0.02,
                        "prediction_tier": "medium" if i < 3 else "high",
                        "inputs": [{"feature_name": "x", "feature_value": i}],
                    },
                )

            response = await ac.get("/api/v1/predictions/audit/drift/drift_test_model")

        assert response.status_code == 200
        data = response.json()
        assert data["total_predictions"] == 5
        assert data["mean_confidence"] > 0


class TestPredictionAuditMeta:
    """Test metadata endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_list_outcomes(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/predictions/audit/outcomes")

        assert response.status_code == 200
        data = response.json()
        assert "outcomes" in data
        values = [o["value"] for o in data["outcomes"]]
        assert "pending" in values
        assert "correct" in values
        assert "incorrect" in values

    @pytest.mark.asyncio
    async def test_list_feedback_types(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/predictions/audit/feedback-types")

        assert response.status_code == 200
        data = response.json()
        assert "feedback_types" in data
        values = [ft["value"] for ft in data["feedback_types"]]
        assert "thumbs_up" in values
        assert "thumbs_down" in values
        assert "correction" in values

    @pytest.mark.asyncio
    async def test_get_stats(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/predictions/audit/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_predictions" in data
        assert "by_model" in data
        assert "by_type" in data
        assert "by_outcome" in data
