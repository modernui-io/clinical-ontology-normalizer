"""Tests for lab reference API endpoints.

Tests verify:
- Lab test listing and filtering
- Reference range lookup
- Lab value interpretation
- Category listing
- Statistics endpoint
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.lab_reference import (
    get_lab_reference_service,
    reset_lab_reference_service,
)


class TestLabReferenceListTests:
    """Test lab test listing endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_lab_reference_service()
        yield
        reset_lab_reference_service()

    @pytest.mark.asyncio
    async def test_list_all_tests(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/lab-reference/tests")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "tests" in data
        assert data["total"] > 0
        assert len(data["tests"]) > 0

    @pytest.mark.asyncio
    async def test_list_tests_by_category(self, client):
        async with client as ac:
            response = await ac.get(
                "/api/v1/lab-reference/tests",
                params={"category": "hematology"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "tests" in data
        for test in data["tests"]:
            assert test["category"] == "hematology"

    @pytest.mark.asyncio
    async def test_list_tests_invalid_category(self, client):
        async with client as ac:
            response = await ac.get(
                "/api/v1/lab-reference/tests",
                params={"category": "invalid_category"},
            )

        assert response.status_code == 400


class TestLabReferenceGetTest:
    """Test getting individual lab tests."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_get_test_by_code(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/lab-reference/tests/Na")

        assert response.status_code == 200
        data = response.json()
        assert data["test_code"] == "Na"
        assert data["test_name"] == "Sodium"
        assert data["unit"] == "mEq/L"

    @pytest.mark.asyncio
    async def test_get_test_by_alias(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/lab-reference/tests/potassium")

        assert response.status_code == 200
        data = response.json()
        assert data["test_code"] == "K"

    @pytest.mark.asyncio
    async def test_get_test_not_found(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/lab-reference/tests/NONEXISTENT")

        assert response.status_code == 404


class TestLabReferenceSearch:
    """Test lab test search."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_search_tests(self, client):
        async with client as ac:
            response = await ac.get(
                "/api/v1/lab-reference/search",
                params={"q": "glucose"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] > 0
        # Should find glucose test
        test_names = [t["test_name"].lower() for t in data["tests"]]
        assert any("glucose" in name for name in test_names)

    @pytest.mark.asyncio
    async def test_search_with_limit(self, client):
        async with client as ac:
            response = await ac.get(
                "/api/v1/lab-reference/search",
                params={"q": "a", "limit": 3},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["tests"]) <= 3


class TestLabReferenceInterpret:
    """Test lab value interpretation."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_interpret_normal_value(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/lab-reference/interpret",
                json={"test": "Na", "value": 140},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["level"] == "normal"
        assert data["is_critical"] is False

    @pytest.mark.asyncio
    async def test_interpret_low_value(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/lab-reference/interpret",
                json={"test": "sodium", "value": 130},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["level"] == "low"
        assert data["is_critical"] is False
        assert len(data["possible_causes"]) > 0

    @pytest.mark.asyncio
    async def test_interpret_critical_high_value(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/lab-reference/interpret",
                json={"test": "K", "value": 7.0},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["level"] == "critical_high"
        assert data["is_critical"] is True

    @pytest.mark.asyncio
    async def test_interpret_with_gender(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/lab-reference/interpret",
                json={"test": "Hgb", "value": 13.0, "gender": "female"},
            )

        assert response.status_code == 200
        data = response.json()
        # 13.0 g/dL is normal for females (12.0-16.0)
        assert data["level"] == "normal"

    @pytest.mark.asyncio
    async def test_interpret_unknown_test(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/lab-reference/interpret",
                json={"test": "UNKNOWN_TEST", "value": 100},
            )

        assert response.status_code == 404


class TestLabReferencePanelInterpret:
    """Test panel interpretation."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_interpret_panel(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/lab-reference/interpret-panel",
                json={
                    "values": {
                        "Na": 140,
                        "K": 4.0,
                        "Glucose": 95,
                    }
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3
        # All should be normal
        for interp in data:
            assert interp["level"] == "normal"

    @pytest.mark.asyncio
    async def test_interpret_panel_with_abnormals(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/lab-reference/interpret-panel",
                json={
                    "values": {
                        "Na": 125,  # Low
                        "K": 4.0,  # Normal
                        "Glucose": 250,  # High
                    },
                    "gender": "male",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        levels = {d["test_name"]: d["level"] for d in data}
        assert levels.get("Sodium") == "low"
        assert levels.get("Potassium") == "normal"
        assert levels.get("Glucose") == "high"


class TestLabReferenceCategories:
    """Test category listing."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_list_categories(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/lab-reference/categories")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        # Each category should have required fields
        for cat in data:
            assert "value" in cat
            assert "name" in cat
            assert "test_count" in cat


class TestLabReferenceStats:
    """Test statistics endpoint."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_get_stats(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/lab-reference/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_tests" in data
        assert "by_category" in data
        assert "gender_specific_count" in data
        assert "with_critical_ranges" in data
        assert "total_aliases" in data
        assert data["total_tests"] > 0
