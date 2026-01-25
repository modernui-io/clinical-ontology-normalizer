"""Tests for Model Registry API endpoints.

Tests verify:
- Model listing and retrieval
- Model registration
- Version management
- Stage transitions
- Statistics
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.model_registry_service import reset_model_registry_service


class TestModelRegistryList:
    """Test model listing endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_model_registry_service()
        yield
        reset_model_registry_service()

    @pytest.mark.asyncio
    async def test_list_models(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/model-registry")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "models" in data
        # Should have sample models
        assert data["total"] > 0

    @pytest.mark.asyncio
    async def test_list_models_filter_by_type(self, client):
        async with client as ac:
            response = await ac.get(
                "/api/v1/model-registry",
                params={"model_type": "classification"},
            )

        assert response.status_code == 200
        data = response.json()
        for model in data["models"]:
            assert model["model_type"] == "classification"

    @pytest.mark.asyncio
    async def test_list_models_filter_by_tag(self, client):
        async with client as ac:
            response = await ac.get(
                "/api/v1/model-registry",
                params={"tag": "risk"},
            )

        assert response.status_code == 200
        data = response.json()
        for model in data["models"]:
            assert "risk" in model["tags"]

    @pytest.mark.asyncio
    async def test_list_models_invalid_type(self, client):
        async with client as ac:
            response = await ac.get(
                "/api/v1/model-registry",
                params={"model_type": "invalid"},
            )

        assert response.status_code == 400


class TestModelRegistryCRUD:
    """Test model CRUD operations."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_model_registry_service()
        yield
        reset_model_registry_service()

    @pytest.mark.asyncio
    async def test_register_model(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/model-registry",
                json={
                    "name": "test_model",
                    "model_type": "classification",
                    "description": "A test model",
                    "tags": ["test"],
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test_model"
        assert data["model_type"] == "classification"
        assert "test" in data["tags"]

    @pytest.mark.asyncio
    async def test_register_model_invalid_type(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/model-registry",
                json={
                    "name": "test_model",
                    "model_type": "invalid_type",
                },
            )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_get_model(self, client):
        async with client as ac:
            # Create a model
            create_response = await ac.post(
                "/api/v1/model-registry",
                json={
                    "name": "get_test_model",
                    "model_type": "regression",
                },
            )
            model_id = create_response.json()["id"]

            # Get the model
            response = await ac.get(f"/api/v1/model-registry/{model_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == model_id
        assert data["name"] == "get_test_model"

    @pytest.mark.asyncio
    async def test_get_model_not_found(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/model-registry/nonexistent-id")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_model(self, client):
        async with client as ac:
            # Create a model
            create_response = await ac.post(
                "/api/v1/model-registry",
                json={
                    "name": "delete_test_model",
                    "model_type": "nlp",
                },
            )
            model_id = create_response.json()["id"]

            # Delete the model
            response = await ac.delete(f"/api/v1/model-registry/{model_id}")

        assert response.status_code == 200
        assert response.json()["deleted"] is True


class TestModelVersions:
    """Test model version management."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture(autouse=True)
    def reset_service(self):
        reset_model_registry_service()
        yield
        reset_model_registry_service()

    @pytest.mark.asyncio
    async def test_add_version(self, client):
        async with client as ac:
            # Create a model
            create_response = await ac.post(
                "/api/v1/model-registry",
                json={
                    "name": "version_test_model",
                    "model_type": "classification",
                },
            )
            model_id = create_response.json()["id"]

            # Add a version
            response = await ac.post(
                f"/api/v1/model-registry/{model_id}/versions",
                json={
                    "version": "1.0.0",
                    "description": "First version",
                    "metrics": {"auc": 0.85, "f1": 0.80},
                    "parameters": {"learning_rate": 0.01},
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1.0.0"
        assert data["stage"] == "development"
        assert data["metrics"]["auc"] == 0.85

    @pytest.mark.asyncio
    async def test_add_duplicate_version(self, client):
        async with client as ac:
            # Create a model and add a version
            create_response = await ac.post(
                "/api/v1/model-registry",
                json={
                    "name": "dup_version_model",
                    "model_type": "classification",
                },
            )
            model_id = create_response.json()["id"]

            # Add first version
            await ac.post(
                f"/api/v1/model-registry/{model_id}/versions",
                json={"version": "1.0.0", "description": "First"},
            )

            # Try to add duplicate
            response = await ac.post(
                f"/api/v1/model-registry/{model_id}/versions",
                json={"version": "1.0.0", "description": "Duplicate"},
            )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_transition_stage(self, client):
        async with client as ac:
            # Create a model and add a version
            create_response = await ac.post(
                "/api/v1/model-registry",
                json={
                    "name": "stage_test_model",
                    "model_type": "classification",
                },
            )
            model_id = create_response.json()["id"]

            await ac.post(
                f"/api/v1/model-registry/{model_id}/versions",
                json={"version": "1.0.0", "description": "First"},
            )

            # Transition to staging
            response = await ac.post(
                f"/api/v1/model-registry/{model_id}/versions/1.0.0/stage",
                json={"stage": "staging"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["stage"] == "staging"

    @pytest.mark.asyncio
    async def test_transition_to_production(self, client):
        async with client as ac:
            # Create a model and add a version
            create_response = await ac.post(
                "/api/v1/model-registry",
                json={
                    "name": "prod_test_model",
                    "model_type": "classification",
                },
            )
            model_id = create_response.json()["id"]

            await ac.post(
                f"/api/v1/model-registry/{model_id}/versions",
                json={"version": "1.0.0", "description": "First"},
            )

            # Transition to production
            await ac.post(
                f"/api/v1/model-registry/{model_id}/versions/1.0.0/stage",
                json={"stage": "production"},
            )

            # Get model and check production_version
            response = await ac.get(f"/api/v1/model-registry/{model_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["production_version"] == "1.0.0"


class TestModelRegistryMeta:
    """Test metadata endpoints."""

    @pytest.fixture
    def client(self):
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    @pytest.mark.asyncio
    async def test_get_stats(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/model-registry/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_models" in data
        assert "total_versions" in data
        assert "production_models" in data
        assert "models_by_type" in data

    @pytest.mark.asyncio
    async def test_list_model_types(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/model-registry/types")

        assert response.status_code == 200
        data = response.json()
        assert "model_types" in data
        values = [t["value"] for t in data["model_types"]]
        assert "classification" in values
        assert "regression" in values
        assert "nlp" in values

    @pytest.mark.asyncio
    async def test_list_stages(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/model-registry/stages")

        assert response.status_code == 200
        data = response.json()
        assert "stages" in data
        values = [s["value"] for s in data["stages"]]
        assert "development" in values
        assert "staging" in values
        assert "production" in values
        assert "archived" in values
