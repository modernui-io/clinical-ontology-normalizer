"""Tests for Veeva Vault CDMS integration.

Tests cover:
    - Schema validation
    - Service methods (demo mode)
    - API endpoint responses
    - Authentication flow
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.schemas.veeva_vault import (
    VeevaConnectionTestResponse,
    VeevaEnrollmentSyncResponse,
    VeevaIntegrationStatus,
    VeevaScreeningPushRequest,
    VeevaScreeningPushResponse,
    VeevaStudyImportRequest,
    VeevaStudyImportResponse,
    VeevaStudyListResponse,
    VeevaStudySummary,
    VeevaSubjectListResponse,
    VaultEnrollmentStatus,
    VaultStudyStatus,
)
from app.services.veeva_vault_service import (
    VeevaVaultService,
    get_veeva_vault_service,
)


# ==============================================================================
# Schema Validation Tests
# ==============================================================================


class TestSchemas:
    """Test Pydantic schema validation."""

    def test_study_summary_schema(self):
        """Validate VeevaStudySummary schema."""
        study = VeevaStudySummary(
            name="REG-ONCO-3001",
            title="Fianlimab + Cemiplimab in Melanoma",
            phase="Phase 3",
            status=VaultStudyStatus.ACTIVE,
            sponsor="Regeneron Pharmaceuticals",
            therapeutic_area="Oncology",
            subject_count=1580,
        )
        assert study.name == "REG-ONCO-3001"
        assert study.subject_count == 1580

    def test_study_summary_minimal(self):
        """Validate VeevaStudySummary with minimal fields."""
        study = VeevaStudySummary(
            name="S1",
            title="Minimal Study",
        )
        assert study.phase is None
        assert study.subject_count == 0
        assert study.status == VaultStudyStatus.ACTIVE

    def test_connection_test_response(self):
        """Validate VeevaConnectionTestResponse schema."""
        resp = VeevaConnectionTestResponse(
            connected=True,
            version="v24.3",
            studies_count=5,
            latency_ms=10.2,
            session_valid=True,
            demo_mode=True,
        )
        assert resp.connected is True
        assert resp.session_valid is True
        assert resp.demo_mode is True

    def test_import_response_schema(self):
        """Validate VeevaStudyImportResponse schema."""
        resp = VeevaStudyImportResponse(
            study_name="REG-ONCO-3001",
            study_title="Fianlimab Study",
            criteria_count=10,
            forms_count=5,
            demo_mode=True,
        )
        assert resp.trial_id is None
        assert resp.criteria == []

    def test_screening_push_request(self):
        """Validate VeevaScreeningPushRequest schema."""
        req = VeevaScreeningPushRequest(
            trial_id="trial-001",
            patient_ids=["pat-001", "pat-002"],
            include_details=True,
        )
        assert len(req.patient_ids) == 2

    def test_enrollment_status_enum(self):
        """Validate enrollment status enum values."""
        assert VaultEnrollmentStatus.ENROLLED == "Enrolled"
        assert VaultEnrollmentStatus.SCREEN_FAILED == "Screen Failed"
        assert VaultEnrollmentStatus.RANDOMIZED == "Randomized"

    def test_study_status_enum(self):
        """Validate study status enum values."""
        assert VaultStudyStatus.ACTIVE == "active"
        assert VaultStudyStatus.LOCKED == "locked"
        assert VaultStudyStatus.CLOSED == "closed"

    def test_integration_status_defaults(self):
        """Validate VeevaIntegrationStatus defaults."""
        status = VeevaIntegrationStatus()
        assert status.configured is False
        assert status.demo_mode is False
        assert status.studies_imported == 0


# ==============================================================================
# Service Tests (Demo Mode)
# ==============================================================================


class TestVeevaVaultService:
    """Test VeevaVaultService in demo mode."""

    @pytest.mark.asyncio
    async def test_demo_mode_detection(self):
        """Service detects demo mode when no credentials configured."""
        service = VeevaVaultService(vault_url="", username="", password="")
        assert service.demo_mode is True
        await service.close()

    @pytest.mark.asyncio
    async def test_configured_mode_detection(self):
        """Service detects configured mode with credentials."""
        service = VeevaVaultService(
            vault_url="https://myvault.veevavault.com",
            username="user",
            password="pass",
        )
        assert service.demo_mode is False
        await service.close()

    @pytest.mark.asyncio
    async def test_authenticate_demo(self):
        """Authenticate returns demo session ID."""
        service = VeevaVaultService(vault_url="", username="", password="")
        session_id = await service.authenticate()

        assert session_id == "DEMO-SESSION-ID"
        await service.close()

    @pytest.mark.asyncio
    async def test_test_connection_demo(self):
        """Test connection returns demo data."""
        service = VeevaVaultService(vault_url="", username="", password="")
        result = await service.test_connection()

        assert result["connected"] is True
        assert result["demo_mode"] is True
        assert result["session_valid"] is True
        assert result["studies_count"] > 0
        assert result["latency_ms"] > 0
        await service.close()

    @pytest.mark.asyncio
    async def test_list_studies_demo(self):
        """List studies returns demo data."""
        service = VeevaVaultService(vault_url="", username="", password="")
        studies = await service.list_studies()

        assert len(studies) == 5
        assert all("name" in s for s in studies)
        assert all("title" in s for s in studies)
        # Should include Regeneron studies
        names = [s["name"] for s in studies]
        assert "REG-ONCO-3001" in names
        assert "REG-HEM-2001" in names
        assert "REG-RESP-3002" in names
        assert "REG-DRM-3003" in names
        assert "REG-NHL-3001" in names
        await service.close()

    @pytest.mark.asyncio
    async def test_import_study_demo(self):
        """Import study returns demo criteria."""
        service = VeevaVaultService(vault_url="", username="", password="")
        result = await service.import_study("REG-ONCO-3001")

        assert result["demo_mode"] is True
        assert result["study_name"] == "REG-ONCO-3001"
        assert result["criteria_count"] > 0
        assert len(result["criteria"]) == result["criteria_count"]

        # Verify criteria types
        inclusion = [c for c in result["criteria"] if c["criterion_type"] == "inclusion"]
        exclusion = [c for c in result["criteria"] if c["criterion_type"] == "exclusion"]
        assert len(inclusion) > 0
        assert len(exclusion) > 0
        await service.close()

    @pytest.mark.asyncio
    async def test_import_study_demo_unknown(self):
        """Import unknown study returns default criteria."""
        service = VeevaVaultService(vault_url="", username="", password="")
        result = await service.import_study("UNKNOWN-STUDY")

        assert result["demo_mode"] is True
        assert result["study_name"] == "UNKNOWN-STUDY"
        assert result["criteria_count"] == 10  # default criteria count
        await service.close()

    @pytest.mark.asyncio
    async def test_push_screening_demo(self):
        """Push screening result returns demo success."""
        service = VeevaVaultService(vault_url="", username="", password="")
        result = await service.push_screening_result(
            trial_id="trial-001",
            patient_id="pat-001",
            eligibility_result={},
        )

        assert result["success"] is True
        assert result["vault_subject_id"] is not None
        assert result["error"] is None
        await service.close()

    @pytest.mark.asyncio
    async def test_sync_enrollment_demo(self):
        """Sync enrollment returns demo status updates."""
        service = VeevaVaultService(vault_url="", username="", password="")
        result = await service.sync_enrollment_status("trial-001")

        assert result["demo_mode"] is True
        assert result["synced_count"] > 0
        assert len(result["status_updates"]) > 0

        statuses = {u["status"] for u in result["status_updates"]}
        assert "Enrolled" in statuses
        await service.close()

    @pytest.mark.asyncio
    async def test_list_subjects_demo(self):
        """List subjects returns demo data."""
        service = VeevaVaultService(vault_url="", username="", password="")
        subjects = await service.list_subjects("REG-ONCO-3001")

        assert len(subjects) > 0
        assert all("subject_id" in s for s in subjects)
        await service.close()

    @pytest.mark.asyncio
    async def test_singleton_accessor(self):
        """Singleton accessor returns same instance."""
        svc1 = get_veeva_vault_service()
        svc2 = get_veeva_vault_service()
        assert svc1 is svc2

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Service works as async context manager."""
        async with VeevaVaultService(vault_url="", username="", password="") as service:
            assert service.demo_mode is True
            result = await service.test_connection()
            assert result["connected"] is True


# ==============================================================================
# API Endpoint Tests
# ==============================================================================


class TestVeevaVaultAPI:
    """Test Veeva Vault CDMS API endpoints."""

    @pytest.fixture
    def app(self):
        """Create test FastAPI app."""
        from fastapi import FastAPI
        from app.api.veeva_vault import router

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        return app

    @pytest.fixture
    async def client(self, app):
        """Create test HTTP client."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client

    @pytest.mark.asyncio
    async def test_connection_test_endpoint(self, client):
        """POST /connection/test returns demo data."""
        resp = await client.post("/api/v1/veeva-vault/connection/test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is True
        assert data["demo_mode"] is True
        assert data["session_valid"] is True

    @pytest.mark.asyncio
    async def test_list_studies_endpoint(self, client):
        """GET /studies returns study list."""
        resp = await client.get("/api/v1/veeva-vault/studies")
        assert resp.status_code == 200
        data = resp.json()
        assert "studies" in data
        assert len(data["studies"]) == 5
        assert data["total_count"] == 5

    @pytest.mark.asyncio
    async def test_import_study_endpoint(self, client):
        """POST /studies/{name}/import returns imported criteria."""
        resp = await client.post(
            "/api/v1/veeva-vault/studies/REG-ONCO-3001/import",
            json={
                "study_name": "REG-ONCO-3001",
                "auto_create_trial": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["study_name"] == "REG-ONCO-3001"
        assert data["criteria_count"] > 0
        assert len(data["criteria"]) > 0

    @pytest.mark.asyncio
    async def test_import_study_no_body(self, client):
        """POST /studies/{name}/import works without request body."""
        resp = await client.post(
            "/api/v1/veeva-vault/studies/REG-HEM-2001/import",
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_subjects_endpoint(self, client):
        """GET /studies/{name}/subjects returns subjects."""
        resp = await client.get(
            "/api/v1/veeva-vault/studies/REG-ONCO-3001/subjects",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "subjects" in data
        assert len(data["subjects"]) > 0

    @pytest.mark.asyncio
    async def test_push_screening_endpoint(self, client):
        """POST /screening/push returns push results."""
        resp = await client.post(
            "/api/v1/veeva-vault/screening/push",
            json={
                "trial_id": "trial-001",
                "patient_ids": ["pat-001", "pat-002"],
                "include_details": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["pushed_count"] == 2
        assert data["failed_count"] == 0
        assert len(data["results"]) == 2

    @pytest.mark.asyncio
    async def test_enrollment_sync_endpoint(self, client):
        """POST /enrollment/sync returns sync results."""
        resp = await client.post(
            "/api/v1/veeva-vault/enrollment/sync",
            params={"trial_id": "trial-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["synced_count"] > 0
        assert len(data["status_updates"]) > 0

    @pytest.mark.asyncio
    async def test_status_endpoint(self, client):
        """GET /status returns integration status."""
        resp = await client.get("/api/v1/veeva-vault/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "configured" in data
        assert "demo_mode" in data
