"""Tests for Data Completeness API endpoints.

Tests verify:
- Completeness report retrieval
- Table listing
- Trends retrieval
- Per-table completeness
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.data_completeness_service import (
    get_data_completeness_service,
    reset_data_completeness_service,
)


class TestDataCompletenessReport:
    """Test completeness report endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_data_completeness_service()
        yield
        reset_data_completeness_service()

    @pytest.mark.asyncio
    async def test_get_completeness_report(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/data-completeness")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "timestamp" in data
        assert "overall_completeness_pct" in data
        assert "tables" in data
        assert "sources" in data

    @pytest.mark.asyncio
    async def test_completeness_report_with_data(self, client):
        # Load some test data
        service = get_data_completeness_service()
        service.set_table_data("person", [
            {"person_id": 1, "gender_concept_id": 8507, "year_of_birth": 1980,
             "race_concept_id": 8527, "ethnicity_concept_id": 38003564},
            {"person_id": 2, "gender_concept_id": 8532, "year_of_birth": 1990,
             "race_concept_id": None, "ethnicity_concept_id": None},
        ])

        async with client as ac:
            response = await ac.get("/api/v1/data-completeness")

        assert response.status_code == 200
        data = response.json()
        # Should have person table with data
        person_tables = [t for t in data["tables"] if t["table_name"] == "person"]
        assert len(person_tables) == 1
        assert person_tables[0]["total_records"] == 2


class TestDataCompletenessTables:
    """Test table listing endpoint."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_data_completeness_service()
        yield
        reset_data_completeness_service()

    @pytest.mark.asyncio
    async def test_list_tables(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/data-completeness/tables")

        assert response.status_code == 200
        data = response.json()
        assert "tables" in data
        table_values = [t["value"] for t in data["tables"]]
        assert "person" in table_values
        assert "visit_occurrence" in table_values
        assert "condition_occurrence" in table_values


class TestDataCompletenessTrends:
    """Test trends endpoint."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_data_completeness_service()
        yield
        reset_data_completeness_service()

    @pytest.mark.asyncio
    async def test_get_trends_empty(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/data-completeness/trends")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["snapshots"] == []

    @pytest.mark.asyncio
    async def test_get_trends_after_report(self, client):
        # Generate a report first to create a snapshot
        service = get_data_completeness_service()
        service.get_completeness()

        async with client as ac:
            response = await ac.get("/api/v1/data-completeness/trends")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["snapshots"]) >= 1
        assert "id" in data["snapshots"][0]
        assert "timestamp" in data["snapshots"][0]
        assert "overall_completeness_pct" in data["snapshots"][0]

    @pytest.mark.asyncio
    async def test_get_trends_with_limit(self, client):
        # Generate multiple reports
        service = get_data_completeness_service()
        for _ in range(5):
            service.get_completeness()

        async with client as ac:
            response = await ac.get("/api/v1/data-completeness/trends", params={"limit": 2})

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2


class TestTableCompleteness:
    """Test per-table completeness endpoint."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_data_completeness_service()
        yield
        reset_data_completeness_service()

    @pytest.mark.asyncio
    async def test_get_table_completeness(self, client):
        # Load test data
        service = get_data_completeness_service()
        service.set_table_data("person", [
            {"person_id": 1, "gender_concept_id": 8507, "year_of_birth": 1980,
             "race_concept_id": 8527, "ethnicity_concept_id": 38003564},
        ])

        async with client as ac:
            response = await ac.get("/api/v1/data-completeness/person")

        assert response.status_code == 200
        data = response.json()
        assert data["table_name"] == "person"
        assert data["total_records"] == 1
        assert "fields" in data
        assert len(data["fields"]) > 0

    @pytest.mark.asyncio
    async def test_get_table_completeness_not_found(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/data-completeness/invalid_table")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_field_level_completeness(self, client):
        # Load test data with some null values
        service = get_data_completeness_service()
        service.set_table_data("person", [
            {"person_id": 1, "gender_concept_id": 8507, "year_of_birth": 1980,
             "race_concept_id": 8527, "ethnicity_concept_id": 38003564,
             "month_of_birth": 6, "day_of_birth": 15},
            {"person_id": 2, "gender_concept_id": 8532, "year_of_birth": 1990,
             "race_concept_id": None, "ethnicity_concept_id": None,
             "month_of_birth": None, "day_of_birth": None},
        ])

        async with client as ac:
            response = await ac.get("/api/v1/data-completeness/person")

        assert response.status_code == 200
        data = response.json()

        # Find month_of_birth field
        month_field = next(
            (f for f in data["fields"] if f["field_name"] == "month_of_birth"),
            None
        )
        assert month_field is not None
        assert month_field["non_null_count"] == 1
        assert month_field["null_count"] == 1
        assert month_field["completeness_pct"] == 50.0
