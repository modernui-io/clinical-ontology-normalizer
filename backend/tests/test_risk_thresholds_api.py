"""Tests for risk thresholds API endpoints.

Tests verify:
- Threshold listing and retrieval
- Threshold updates
- Score classification
- Default reset
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.risk_thresholds_service import reset_risk_thresholds_service


class TestRiskThresholdsList:
    """Test threshold listing endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_risk_thresholds_service()
        yield
        reset_risk_thresholds_service()

    @pytest.mark.asyncio
    async def test_list_all_thresholds(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/risk-thresholds")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "thresholds" in data
        assert data["total"] > 0
        assert len(data["thresholds"]) == data["total"]

    @pytest.mark.asyncio
    async def test_list_models(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/risk-thresholds/models")

        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert "total" in data
        assert "mortality" in data["models"]
        assert "readmission_30day" in data["models"]

    @pytest.mark.asyncio
    async def test_list_tiers(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/risk-thresholds/tiers")

        assert response.status_code == 200
        data = response.json()
        assert "tiers" in data
        tier_values = [t["value"] for t in data["tiers"]]
        assert "low" in tier_values
        assert "medium" in tier_values
        assert "high" in tier_values
        assert "critical" in tier_values


class TestRiskThresholdsGet:
    """Test threshold retrieval endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_risk_thresholds_service()
        yield
        reset_risk_thresholds_service()

    @pytest.mark.asyncio
    async def test_get_mortality_thresholds(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/risk-thresholds/mortality")

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "mortality"
        assert len(data["thresholds"]) == 4
        assert data["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_get_readmission_thresholds(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/risk-thresholds/readmission_30day")

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "readmission_30day"
        assert len(data["thresholds"]) == 4

    @pytest.mark.asyncio
    async def test_get_unknown_model(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/risk-thresholds/unknown_model")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_defaults(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/risk-thresholds/mortality/defaults")

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "mortality"
        assert data["version"] == "1.0.0"


class TestRiskThresholdsUpdate:
    """Test threshold update endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_risk_thresholds_service()
        yield
        reset_risk_thresholds_service()

    @pytest.mark.asyncio
    async def test_update_thresholds(self, client):
        async with client as ac:
            response = await ac.put(
                "/api/v1/risk-thresholds/mortality",
                json={
                    "thresholds": [
                        {"tier": "low", "min_score": 0.0, "max_score": 0.25, "color": "#4CAF50", "label": "Low"},
                        {"tier": "medium", "min_score": 0.25, "max_score": 0.55, "color": "#FFC107", "label": "Medium"},
                        {"tier": "high", "min_score": 0.55, "max_score": 0.85, "color": "#FF9800", "label": "High"},
                        {"tier": "critical", "min_score": 0.85, "max_score": 1.0, "color": "#F44336", "label": "Critical"},
                    ],
                    "description": "Custom thresholds",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "mortality"
        assert data["description"] == "Custom thresholds"
        # Version should be incremented
        assert data["version"] == "1.0.1"
        # Check threshold values updated
        assert data["thresholds"][0]["max_score"] == 0.25

    @pytest.mark.asyncio
    async def test_update_thresholds_invalid_gap(self, client):
        async with client as ac:
            response = await ac.put(
                "/api/v1/risk-thresholds/mortality",
                json={
                    "thresholds": [
                        {"tier": "low", "min_score": 0.0, "max_score": 0.2, "color": "#4CAF50", "label": "Low"},
                        # Gap between 0.2 and 0.3
                        {"tier": "high", "min_score": 0.3, "max_score": 1.0, "color": "#FF9800", "label": "High"},
                    ],
                },
            )

        assert response.status_code == 400
        data = response.json()
        # Check message field (from error handler) or detail field (from HTTPException)
        error_msg = data.get("message", data.get("detail", "")).lower()
        assert "gap" in error_msg or "overlap" in error_msg

    @pytest.mark.asyncio
    async def test_update_thresholds_invalid_range(self, client):
        async with client as ac:
            response = await ac.put(
                "/api/v1/risk-thresholds/mortality",
                json={
                    "thresholds": [
                        # Doesn't start at 0
                        {"tier": "low", "min_score": 0.1, "max_score": 0.5, "color": "#4CAF50", "label": "Low"},
                        {"tier": "high", "min_score": 0.5, "max_score": 1.0, "color": "#FF9800", "label": "High"},
                    ],
                },
            )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_reset_to_defaults(self, client):
        async with client as ac:
            # First update
            await ac.put(
                "/api/v1/risk-thresholds/mortality",
                json={
                    "thresholds": [
                        {"tier": "low", "min_score": 0.0, "max_score": 0.5, "color": "#4CAF50", "label": "Low"},
                        {"tier": "critical", "min_score": 0.5, "max_score": 1.0, "color": "#F44336", "label": "Critical"},
                    ],
                },
            )

            # Then reset
            response = await ac.post("/api/v1/risk-thresholds/mortality/reset")

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1.0.0"
        assert len(data["thresholds"]) == 4  # Back to 4 tiers


class TestRiskThresholdsClassify:
    """Test score classification endpoint."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_risk_thresholds_service()
        yield
        reset_risk_thresholds_service()

    @pytest.mark.asyncio
    async def test_classify_low_risk(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/risk-thresholds/mortality/classify",
                json={"score": 0.1},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["score"] == 0.1
        assert data["tier"] == "low"

    @pytest.mark.asyncio
    async def test_classify_high_risk(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/risk-thresholds/mortality/classify",
                json={"score": 0.65},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "high"

    @pytest.mark.asyncio
    async def test_classify_critical_risk(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/risk-thresholds/mortality/classify",
                json={"score": 0.95},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "critical"

    @pytest.mark.asyncio
    async def test_classify_unknown_model(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/risk-thresholds/unknown/classify",
                json={"score": 0.5},
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_classify_returns_color(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/risk-thresholds/sepsis/classify",
                json={"score": 0.7},
            )

        assert response.status_code == 200
        data = response.json()
        assert "color" in data
        assert data["color"].startswith("#")
