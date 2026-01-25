"""Tests for Data Consistency API endpoints.

Tests verify:
- Running consistency checks
- Getting results
- Getting summary
- Filtering issues
- Metadata endpoints
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.data_consistency_service import (
    get_data_consistency_service,
    reset_data_consistency_service,
)


class TestDataConsistencyRun:
    """Test running consistency checks."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_data_consistency_service()
        yield
        reset_data_consistency_service()

    @pytest.mark.asyncio
    async def test_run_checks(self, client):
        async with client as ac:
            response = await ac.post("/api/v1/data-consistency/run")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "timestamp" in data
        assert "total_checks" in data
        assert data["total_checks"] > 0
        assert "results" in data

    @pytest.mark.asyncio
    async def test_run_checks_with_data(self, client):
        # Load test data with an issue
        service = get_data_consistency_service()
        service.set_table_data("person", [{"person_id": 1}])
        service.set_table_data("visit_occurrence", [
            {"visit_occurrence_id": 10, "person_id": 999,  # Invalid person_id
             "visit_start_date": "2024-01-01"},
        ])

        async with client as ac:
            response = await ac.post("/api/v1/data-consistency/run")

        assert response.status_code == 200
        data = response.json()
        # Should have found at least one referential integrity issue
        assert data["total_issues"] > 0


class TestDataConsistencyResults:
    """Test getting results."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_data_consistency_service()
        yield
        reset_data_consistency_service()

    @pytest.mark.asyncio
    async def test_get_results_no_run(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/data-consistency/results")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_results_after_run(self, client):
        async with client as ac:
            # Run checks first
            await ac.post("/api/v1/data-consistency/run")

            # Then get results
            response = await ac.get("/api/v1/data-consistency/results")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "results" in data


class TestDataConsistencySummary:
    """Test summary endpoint."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_data_consistency_service()
        yield
        reset_data_consistency_service()

    @pytest.mark.asyncio
    async def test_get_summary_no_results(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/data-consistency/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["has_results"] is False

    @pytest.mark.asyncio
    async def test_get_summary_with_results(self, client):
        async with client as ac:
            # Run checks first
            await ac.post("/api/v1/data-consistency/run")

            # Get summary
            response = await ac.get("/api/v1/data-consistency/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["has_results"] is True
        assert "report_id" in data
        assert "total_checks" in data


class TestDataConsistencyMeta:
    """Test metadata endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_list_check_types(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/data-consistency/check-types")

        assert response.status_code == 200
        data = response.json()
        assert "check_types" in data
        values = [ct["value"] for ct in data["check_types"]]
        assert "referential_integrity" in values
        assert "temporal_plausibility" in values

    @pytest.mark.asyncio
    async def test_list_severities(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/data-consistency/severities")

        assert response.status_code == 200
        data = response.json()
        assert "severities" in data
        values = [s["value"] for s in data["severities"]]
        assert "critical" in values
        assert "high" in values
        assert "medium" in values
        assert "low" in values

    @pytest.mark.asyncio
    async def test_list_statuses(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/data-consistency/statuses")

        assert response.status_code == 200
        data = response.json()
        assert "statuses" in data
        values = [s["value"] for s in data["statuses"]]
        assert "passed" in values
        assert "failed" in values
        assert "warning" in values


class TestDataConsistencyIssues:
    """Test issue filtering endpoint."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_data_consistency_service()
        yield
        reset_data_consistency_service()

    @pytest.mark.asyncio
    async def test_get_issues_no_run(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/data-consistency/issues")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    @pytest.mark.asyncio
    async def test_get_issues_with_data(self, client):
        # Load test data with issues
        service = get_data_consistency_service()
        service.set_table_data("person", [{"person_id": 1}])
        service.set_table_data("visit_occurrence", [
            {"visit_occurrence_id": 10, "person_id": 999,
             "visit_start_date": "2024-01-01"},
        ])

        async with client as ac:
            # Run checks first
            await ac.post("/api/v1/data-consistency/run")

            # Get issues
            response = await ac.get("/api/v1/data-consistency/issues")

        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert "issue_id" in data[0]
        assert "severity" in data[0]

    @pytest.mark.asyncio
    async def test_get_issues_filter_by_severity(self, client):
        # Load test data
        service = get_data_consistency_service()
        service.set_table_data("person", [{"person_id": 1}])
        service.set_table_data("visit_occurrence", [
            {"visit_occurrence_id": 10, "person_id": 999,
             "visit_start_date": "2024-01-01"},
        ])

        async with client as ac:
            await ac.post("/api/v1/data-consistency/run")

            response = await ac.get(
                "/api/v1/data-consistency/issues",
                params={"severity": "critical"},
            )

        assert response.status_code == 200
        data = response.json()
        for issue in data:
            assert issue["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_get_issues_invalid_severity(self, client):
        async with client as ac:
            await ac.post("/api/v1/data-consistency/run")

            response = await ac.get(
                "/api/v1/data-consistency/issues",
                params={"severity": "invalid"},
            )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_issues_filter_by_table(self, client):
        service = get_data_consistency_service()
        service.set_table_data("person", [{"person_id": 1}])
        service.set_table_data("visit_occurrence", [
            {"visit_occurrence_id": 10, "person_id": 999,
             "visit_start_date": "2024-01-01"},
        ])

        async with client as ac:
            await ac.post("/api/v1/data-consistency/run")

            response = await ac.get(
                "/api/v1/data-consistency/issues",
                params={"table": "visit_occurrence"},
            )

        assert response.status_code == 200
        data = response.json()
        for issue in data:
            assert issue["table"] == "visit_occurrence"
