"""Tests for jobs API endpoints."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.schemas import JobStatus


class TestGetJobStatus:
    """Test job status endpoint."""

    @pytest.mark.asyncio
    async def test_get_job_status_returns_404_when_not_found(
        self,
        client_with_mock_db: AsyncClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test getting status of nonexistent job returns 404."""
        # Mock execute to return no results
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        job_id = uuid4()
        response = await client_with_mock_db.get(f"/jobs/{job_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_job_status_returns_job_info(
        self,
        client_with_mock_db: AsyncClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test getting status of existing job."""
        from datetime import datetime, timezone

        # Create mock document
        mock_document = MagicMock()
        mock_document.id = str(uuid4())
        mock_document.status = JobStatus.QUEUED
        mock_document.created_at = datetime.now(timezone.utc)
        mock_document.processed_at = None
        mock_document.job_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client_with_mock_db.get(f"/jobs/{mock_document.job_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["job_id"] == str(mock_document.job_id)
        assert data["document_id"] == mock_document.id
        assert data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_get_job_status_includes_created_at(
        self,
        client_with_mock_db: AsyncClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test job status includes created_at timestamp."""
        from datetime import datetime, timezone

        mock_document = MagicMock()
        mock_document.id = str(uuid4())
        mock_document.status = JobStatus.PROCESSING
        mock_document.created_at = datetime(2026, 1, 14, 10, 30, 0, tzinfo=timezone.utc)
        mock_document.processed_at = None
        mock_document.job_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client_with_mock_db.get(f"/jobs/{mock_document.job_id}")
        data = response.json()

        assert "created_at" in data
        assert "2026-01-14" in data["created_at"]

    @pytest.mark.asyncio
    async def test_get_job_status_includes_processed_at_when_completed(
        self,
        client_with_mock_db: AsyncClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test completed job includes processed_at timestamp."""
        from datetime import datetime, timezone

        mock_document = MagicMock()
        mock_document.id = str(uuid4())
        mock_document.status = JobStatus.COMPLETED
        mock_document.created_at = datetime(2026, 1, 14, 10, 30, 0, tzinfo=timezone.utc)
        mock_document.processed_at = datetime(2026, 1, 14, 10, 35, 0, tzinfo=timezone.utc)
        mock_document.job_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client_with_mock_db.get(f"/jobs/{mock_document.job_id}")
        data = response.json()

        assert "processed_at" in data
        assert data["processed_at"] is not None

    @pytest.mark.asyncio
    async def test_get_job_status_invalid_uuid_returns_422(
        self,
        client_with_mock_db: AsyncClient,
    ) -> None:
        """Test invalid UUID returns 422 validation error."""
        response = await client_with_mock_db.get("/jobs/not-a-uuid")
        assert response.status_code == 422


class TestGetJobResult:
    """Test job result endpoint."""

    @pytest.mark.asyncio
    async def test_get_job_result_returns_404_when_not_found(
        self,
        client_with_mock_db: AsyncClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test getting result of nonexistent job returns 404."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        job_id = uuid4()
        response = await client_with_mock_db.get(f"/jobs/{job_id}/result")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_job_result_returns_400_when_not_completed(
        self,
        client_with_mock_db: AsyncClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test getting result of incomplete job returns 400."""
        from datetime import datetime, timezone

        mock_document = MagicMock()
        mock_document.id = str(uuid4())
        mock_document.status = JobStatus.PROCESSING
        mock_document.created_at = datetime.now(timezone.utc)
        mock_document.processed_at = None
        mock_document.job_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client_with_mock_db.get(f"/jobs/{mock_document.job_id}/result")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_job_result_returns_result_when_completed(
        self,
        client_with_mock_db: AsyncClient,
        mock_db_session: MagicMock,
    ) -> None:
        """Test getting result of completed job."""
        from datetime import datetime, timezone

        mock_document = MagicMock()
        mock_document.id = str(uuid4())
        mock_document.status = JobStatus.COMPLETED
        mock_document.created_at = datetime(2026, 1, 14, 10, 30, 0, tzinfo=timezone.utc)
        mock_document.processed_at = datetime(2026, 1, 14, 10, 35, 0, tzinfo=timezone.utc)
        mock_document.job_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        response = await client_with_mock_db.get(f"/jobs/{mock_document.job_id}/result")
        assert response.status_code == 200

        data = response.json()
        assert data["job_id"] == str(mock_document.job_id)
        assert data["status"] == "completed"
        assert "processed_at" in data
