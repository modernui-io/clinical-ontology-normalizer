"""Tests for alert rules API endpoints.

Tests verify:
- Rule CRUD operations
- Rule evaluation
- Patient evaluation
- Metadata endpoints
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.alert_rules_service import reset_alert_rules_service


class TestAlertRulesList:
    """Test alert rules listing."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_alert_rules_service()
        yield
        reset_alert_rules_service()

    @pytest.mark.asyncio
    async def test_list_rules(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/alert-rules")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "rules" in data
        # Should have default rules
        assert data["total"] > 0

    @pytest.mark.asyncio
    async def test_list_rules_by_category(self, client):
        async with client as ac:
            response = await ac.get(
                "/api/v1/alert-rules",
                params={"category": "risk_score"},
            )

        assert response.status_code == 200
        data = response.json()
        for rule in data["rules"]:
            assert rule["category"] == "risk_score"

    @pytest.mark.asyncio
    async def test_list_rules_by_status(self, client):
        async with client as ac:
            response = await ac.get(
                "/api/v1/alert-rules",
                params={"status": "active"},
            )

        assert response.status_code == 200
        data = response.json()
        for rule in data["rules"]:
            assert rule["status"] == "active"

    @pytest.mark.asyncio
    async def test_list_rules_invalid_category(self, client):
        async with client as ac:
            response = await ac.get(
                "/api/v1/alert-rules",
                params={"category": "invalid"},
            )

        assert response.status_code == 400


class TestAlertRulesCRUD:
    """Test alert rules CRUD operations."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_alert_rules_service()
        yield
        reset_alert_rules_service()

    @pytest.mark.asyncio
    async def test_create_rule(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/alert-rules",
                json={
                    "name": "Test Rule",
                    "description": "A test alert rule",
                    "category": "lab_value",
                    "severity": "high",
                    "conditions": [
                        {
                            "field": "glucose",
                            "operator": "gt",
                            "value": 200,
                            "label": "High glucose",
                        }
                    ],
                    "actions": [
                        {"type": "notify", "config": {"channel": "test"}},
                    ],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Rule"
        assert data["category"] == "lab_value"
        assert data["severity"] == "high"
        assert data["status"] == "active"
        assert len(data["conditions"]) == 1
        assert len(data["actions"]) == 1

    @pytest.mark.asyncio
    async def test_create_rule_invalid_category(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/alert-rules",
                json={
                    "name": "Test Rule",
                    "category": "invalid",
                    "severity": "high",
                    "conditions": [
                        {"field": "test", "operator": "eq", "value": 1},
                    ],
                },
            )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_rule_invalid_operator(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/alert-rules",
                json={
                    "name": "Test Rule",
                    "category": "lab_value",
                    "severity": "high",
                    "conditions": [
                        {"field": "test", "operator": "invalid_op", "value": 1},
                    ],
                },
            )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_rule(self, client):
        async with client as ac:
            # Create a rule first
            create_response = await ac.post(
                "/api/v1/alert-rules",
                json={
                    "name": "Get Test Rule",
                    "category": "vital_sign",
                    "severity": "medium",
                    "conditions": [
                        {"field": "heart_rate", "operator": "gt", "value": 100},
                    ],
                },
            )
            rule_id = create_response.json()["id"]

            # Get the rule
            response = await ac.get(f"/api/v1/alert-rules/{rule_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == rule_id
        assert data["name"] == "Get Test Rule"

    @pytest.mark.asyncio
    async def test_get_rule_not_found(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/alert-rules/nonexistent-id")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_rule(self, client):
        async with client as ac:
            # Create a rule
            create_response = await ac.post(
                "/api/v1/alert-rules",
                json={
                    "name": "Update Test Rule",
                    "category": "lab_value",
                    "severity": "low",
                    "conditions": [
                        {"field": "test", "operator": "eq", "value": 1},
                    ],
                },
            )
            rule_id = create_response.json()["id"]

            # Update the rule
            response = await ac.put(
                f"/api/v1/alert-rules/{rule_id}",
                json={
                    "name": "Updated Rule Name",
                    "severity": "high",
                    "status": "inactive",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Rule Name"
        assert data["severity"] == "high"
        assert data["status"] == "inactive"

    @pytest.mark.asyncio
    async def test_delete_rule(self, client):
        async with client as ac:
            # Create a rule
            create_response = await ac.post(
                "/api/v1/alert-rules",
                json={
                    "name": "Delete Test Rule",
                    "category": "medication",
                    "severity": "high",
                    "conditions": [
                        {"field": "interaction_count", "operator": "gt", "value": 0},
                    ],
                },
            )
            rule_id = create_response.json()["id"]

            # Delete the rule
            response = await ac.delete(f"/api/v1/alert-rules/{rule_id}")

        assert response.status_code == 200
        assert response.json()["deleted"] is True

    @pytest.mark.asyncio
    async def test_delete_rule_not_found(self, client):
        async with client as ac:
            response = await ac.delete("/api/v1/alert-rules/nonexistent-id")

        assert response.status_code == 404


class TestAlertRulesEvaluation:
    """Test rule evaluation."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_alert_rules_service()
        yield
        reset_alert_rules_service()

    @pytest.mark.asyncio
    async def test_evaluate_rule_triggered(self, client):
        async with client as ac:
            # Create a rule
            create_response = await ac.post(
                "/api/v1/alert-rules",
                json={
                    "name": "High Glucose Alert",
                    "category": "lab_value",
                    "severity": "high",
                    "conditions": [
                        {"field": "glucose", "operator": "gt", "value": 200},
                    ],
                },
            )
            rule_id = create_response.json()["id"]

            # Evaluate with data that triggers
            response = await ac.post(
                f"/api/v1/alert-rules/{rule_id}/evaluate",
                json={
                    "patient_data": {"glucose": 250},
                    "patient_id": "patient-123",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["triggered"] is True
        assert data["severity"] == "high"
        assert len(data["matched_conditions"]) == 1

    @pytest.mark.asyncio
    async def test_evaluate_rule_not_triggered(self, client):
        async with client as ac:
            # Create a rule
            create_response = await ac.post(
                "/api/v1/alert-rules",
                json={
                    "name": "High Glucose Alert",
                    "category": "lab_value",
                    "severity": "high",
                    "conditions": [
                        {"field": "glucose", "operator": "gt", "value": 200},
                    ],
                },
            )
            rule_id = create_response.json()["id"]

            # Evaluate with data that doesn't trigger
            response = await ac.post(
                f"/api/v1/alert-rules/{rule_id}/evaluate",
                json={
                    "patient_data": {"glucose": 95},
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["triggered"] is False
        assert len(data["matched_conditions"]) == 0

    @pytest.mark.asyncio
    async def test_evaluate_patient(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/alert-rules/evaluate-patient",
                json={
                    "patient_data": {
                        "readmission_risk_score": 0.85,
                        "potassium": 4.0,
                        "mortality_risk_tier": "low",
                    },
                    "patient_id": "patient-456",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "total_rules" in data
        assert "triggered_count" in data
        assert "evaluations" in data
        assert data["total_rules"] > 0

    @pytest.mark.asyncio
    async def test_evaluate_patient_by_category(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/alert-rules/evaluate-patient",
                json={
                    "patient_data": {"readmission_risk_score": 0.85},
                    "category": "risk_score",
                },
            )

        assert response.status_code == 200
        data = response.json()
        # All evaluations should be for risk_score category
        assert data["total_rules"] > 0


class TestAlertRulesMeta:
    """Test metadata endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_list_operators(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/alert-rules/meta/operators")

        assert response.status_code == 200
        data = response.json()
        assert "operators" in data
        assert len(data["operators"]) > 0
        # Should have common operators
        values = [op["value"] for op in data["operators"]]
        assert "eq" in values
        assert "gt" in values
        assert "lt" in values

    @pytest.mark.asyncio
    async def test_list_categories(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/alert-rules/meta/categories")

        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert len(data["categories"]) > 0
        values = [cat["value"] for cat in data["categories"]]
        assert "risk_score" in values
        assert "lab_value" in values

    @pytest.mark.asyncio
    async def test_list_severities(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/alert-rules/meta/severities")

        assert response.status_code == 200
        data = response.json()
        assert "severities" in data
        assert len(data["severities"]) > 0
        values = [sev["value"] for sev in data["severities"]]
        assert "critical" in values
        assert "high" in values
        assert "medium" in values
        assert "low" in values


class TestAlertRulesStats:
    """Test statistics endpoint."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_alert_rules_service()
        yield
        reset_alert_rules_service()

    @pytest.mark.asyncio
    async def test_get_stats(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/alert-rules/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_rules" in data
        assert "by_category" in data
        assert "by_severity" in data
        assert "by_status" in data
        assert "active_rules" in data
        assert data["total_rules"] > 0
