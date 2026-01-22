"""Tests for health and root API endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


class TestHealthEndpoint:
    """Test health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client: AsyncClient) -> None:
        """Test health endpoint returns 200 OK."""
        response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_returns_healthy_status(self, client: AsyncClient) -> None:
        """Test health endpoint returns healthy status."""
        response = await client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_health_returns_service_name(self, client: AsyncClient) -> None:
        """Test health endpoint returns service name."""
        response = await client.get("/health")
        data = response.json()
        assert data["service"] == "clinical-ontology-normalizer"

    @pytest.mark.asyncio
    async def test_health_returns_version(self, client: AsyncClient) -> None:
        """Test health endpoint returns version."""
        response = await client.get("/health")
        data = response.json()
        assert "version" in data
        assert len(data["version"]) > 0

    @pytest.mark.asyncio
    async def test_health_returns_timestamp(self, client: AsyncClient) -> None:
        """Test health endpoint returns timestamp."""
        response = await client.get("/health")
        data = response.json()
        assert "timestamp" in data
        # Should be ISO format
        assert "T" in data["timestamp"]


class TestRootEndpoint:
    """Test root endpoint."""

    @pytest.mark.asyncio
    async def test_root_returns_200(self, client: AsyncClient) -> None:
        """Test root endpoint returns 200 OK."""
        response = await client.get("/")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_root_returns_service_info(self, client: AsyncClient) -> None:
        """Test root endpoint returns service info."""
        response = await client.get("/")
        data = response.json()
        assert "service" in data
        assert "Clinical Ontology Normalizer" in data["service"]

    @pytest.mark.asyncio
    async def test_root_returns_docs_link(self, client: AsyncClient) -> None:
        """Test root endpoint returns docs link."""
        response = await client.get("/")
        data = response.json()
        assert "docs" in data["docs"]  # Accept /docs or /api/v1/docs

    @pytest.mark.asyncio
    async def test_root_returns_health_link(self, client: AsyncClient) -> None:
        """Test root endpoint returns health link."""
        response = await client.get("/")
        data = response.json()
        assert "health" in data["health"]  # Accept /health or /api/v1/health


class TestAPIMetadata:
    """Test API metadata and configuration."""

    def test_app_title(self) -> None:
        """Test app has correct title."""
        assert app.title == "Clinical Ontology Normalizer"

    def test_app_version(self) -> None:
        """Test app has version set."""
        assert app.version is not None
        assert len(app.version) > 0

    def test_app_has_description(self) -> None:
        """Test app has description."""
        assert app.description is not None
        assert "OMOP" in app.description
