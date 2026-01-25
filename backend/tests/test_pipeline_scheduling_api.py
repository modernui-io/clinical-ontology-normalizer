"""Tests for pipeline scheduling API endpoints.

Tests verify:
- Schedule CRUD operations
- Schedule pausing/resuming
- Run triggering
- Run listing
- Statistics
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.pipeline_scheduling_service import reset_pipeline_scheduling_service


class TestPipelineSchedulesList:
    """Test schedule listing endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_pipeline_scheduling_service()
        yield
        reset_pipeline_scheduling_service()

    @pytest.mark.asyncio
    async def test_list_schedules(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/pipeline-scheduling")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "schedules" in data
        # Should have sample schedules
        assert data["total"] > 0

    @pytest.mark.asyncio
    async def test_list_schedules_filter_status(self, client):
        async with client as ac:
            response = await ac.get(
                "/api/v1/pipeline-scheduling",
                params={"status": "active"},
            )

        assert response.status_code == 200
        data = response.json()
        for schedule in data["schedules"]:
            assert schedule["status"] == "active"

    @pytest.mark.asyncio
    async def test_list_schedules_invalid_status(self, client):
        async with client as ac:
            response = await ac.get(
                "/api/v1/pipeline-scheduling",
                params={"status": "invalid"},
            )

        assert response.status_code == 400


class TestPipelineSchedulesCRUD:
    """Test schedule CRUD operations."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_pipeline_scheduling_service()
        yield
        reset_pipeline_scheduling_service()

    @pytest.mark.asyncio
    async def test_create_schedule(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/pipeline-scheduling",
                json={
                    "pipeline_id": "pl-test",
                    "name": "Test Schedule",
                    "description": "A test schedule",
                    "frequency": "daily",
                    "timezone": "UTC",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_id"] == "pl-test"
        assert data["name"] == "Test Schedule"
        assert data["frequency"] == "daily"
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_create_schedule_invalid_frequency(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/pipeline-scheduling",
                json={
                    "pipeline_id": "pl-test",
                    "name": "Test Schedule",
                    "frequency": "invalid_freq",
                },
            )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_schedule(self, client):
        async with client as ac:
            # Create a schedule
            create_response = await ac.post(
                "/api/v1/pipeline-scheduling",
                json={
                    "pipeline_id": "pl-get-test",
                    "name": "Get Test",
                    "frequency": "hourly",
                },
            )
            schedule_id = create_response.json()["id"]

            # Get the schedule
            response = await ac.get(f"/api/v1/pipeline-scheduling/{schedule_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == schedule_id
        assert data["name"] == "Get Test"

    @pytest.mark.asyncio
    async def test_get_schedule_not_found(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/pipeline-scheduling/nonexistent-id")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_schedule(self, client):
        async with client as ac:
            # Create a schedule
            create_response = await ac.post(
                "/api/v1/pipeline-scheduling",
                json={
                    "pipeline_id": "pl-update-test",
                    "name": "Update Test",
                    "frequency": "daily",
                },
            )
            schedule_id = create_response.json()["id"]

            # Update the schedule
            response = await ac.put(
                f"/api/v1/pipeline-scheduling/{schedule_id}",
                json={
                    "name": "Updated Name",
                    "frequency": "hourly",
                    "timeout_minutes": 120,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["frequency"] == "hourly"
        assert data["timeout_minutes"] == 120

    @pytest.mark.asyncio
    async def test_delete_schedule(self, client):
        async with client as ac:
            # Create a schedule
            create_response = await ac.post(
                "/api/v1/pipeline-scheduling",
                json={
                    "pipeline_id": "pl-delete-test",
                    "name": "Delete Test",
                    "frequency": "daily",
                },
            )
            schedule_id = create_response.json()["id"]

            # Delete the schedule
            response = await ac.delete(f"/api/v1/pipeline-scheduling/{schedule_id}")

        assert response.status_code == 200
        assert response.json()["deleted"] is True


class TestPipelineSchedulesControl:
    """Test schedule control operations."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_pipeline_scheduling_service()
        yield
        reset_pipeline_scheduling_service()

    @pytest.mark.asyncio
    async def test_pause_schedule(self, client):
        async with client as ac:
            # Create a schedule
            create_response = await ac.post(
                "/api/v1/pipeline-scheduling",
                json={
                    "pipeline_id": "pl-pause-test",
                    "name": "Pause Test",
                    "frequency": "daily",
                },
            )
            schedule_id = create_response.json()["id"]

            # Pause the schedule
            response = await ac.post(f"/api/v1/pipeline-scheduling/{schedule_id}/pause")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paused"

    @pytest.mark.asyncio
    async def test_resume_schedule(self, client):
        async with client as ac:
            # Create and pause a schedule
            create_response = await ac.post(
                "/api/v1/pipeline-scheduling",
                json={
                    "pipeline_id": "pl-resume-test",
                    "name": "Resume Test",
                    "frequency": "daily",
                },
            )
            schedule_id = create_response.json()["id"]
            await ac.post(f"/api/v1/pipeline-scheduling/{schedule_id}/pause")

            # Resume the schedule
            response = await ac.post(f"/api/v1/pipeline-scheduling/{schedule_id}/resume")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_trigger_run(self, client):
        async with client as ac:
            # Create a schedule
            create_response = await ac.post(
                "/api/v1/pipeline-scheduling",
                json={
                    "pipeline_id": "pl-trigger-test",
                    "name": "Trigger Test",
                    "frequency": "daily",
                },
            )
            schedule_id = create_response.json()["id"]

            # Trigger a run
            response = await ac.post(f"/api/v1/pipeline-scheduling/{schedule_id}/trigger")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert data["triggered_by"] == "manual"


class TestPipelineRuns:
    """Test run listing endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_pipeline_scheduling_service()
        yield
        reset_pipeline_scheduling_service()

    @pytest.mark.asyncio
    async def test_list_runs_empty(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/pipeline-scheduling/runs")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_runs_after_trigger(self, client):
        async with client as ac:
            # Create a schedule and trigger a run
            create_response = await ac.post(
                "/api/v1/pipeline-scheduling",
                json={
                    "pipeline_id": "pl-runs-test",
                    "name": "Runs Test",
                    "frequency": "daily",
                },
            )
            schedule_id = create_response.json()["id"]
            await ac.post(f"/api/v1/pipeline-scheduling/{schedule_id}/trigger")

            # List runs
            response = await ac.get("/api/v1/pipeline-scheduling/runs")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_get_schedule_runs(self, client):
        async with client as ac:
            # Create a schedule and trigger runs
            create_response = await ac.post(
                "/api/v1/pipeline-scheduling",
                json={
                    "pipeline_id": "pl-sched-runs-test",
                    "name": "Schedule Runs Test",
                    "frequency": "daily",
                },
            )
            schedule_id = create_response.json()["id"]
            await ac.post(f"/api/v1/pipeline-scheduling/{schedule_id}/trigger")
            await ac.post(f"/api/v1/pipeline-scheduling/{schedule_id}/trigger")

            # Get schedule runs
            response = await ac.get(f"/api/v1/pipeline-scheduling/{schedule_id}/runs")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2


class TestPipelineSchedulingMeta:
    """Test metadata endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_list_frequencies(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/pipeline-scheduling/frequencies")

        assert response.status_code == 200
        data = response.json()
        assert "frequencies" in data
        values = [f["value"] for f in data["frequencies"]]
        assert "hourly" in values
        assert "daily" in values
        assert "weekly" in values

    @pytest.mark.asyncio
    async def test_list_statuses(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/pipeline-scheduling/statuses")

        assert response.status_code == 200
        data = response.json()
        assert "statuses" in data
        values = [s["value"] for s in data["statuses"]]
        assert "active" in values
        assert "paused" in values

    @pytest.mark.asyncio
    async def test_get_stats(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/pipeline-scheduling/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_schedules" in data
        assert "active_schedules" in data
        assert "schedules_by_status" in data
        assert "total_runs" in data
