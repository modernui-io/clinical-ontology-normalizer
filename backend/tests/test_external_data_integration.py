"""Tests for External Data Integration (EXT-DATA).

Covers:
- Seed data verification (data sources, pipelines, validations, mappings, transfer logs)
- Data source CRUD (create, read, update, delete, list, filter by trial/type/protocol/active)
- Pipeline CRUD (create, read, update, delete, list, filter by trial/status/source)
- Validation CRUD (create, read, update, delete, list, filter by trial/severity/pipeline/resolved)
- Mapping CRUD (create, read, update, delete, list, filter by trial/source/validated)
- Transfer log CRUD (create, read, update, delete, list, filter by trial/pipeline/direction/status)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.external_data_integration import (
    ConnectionProtocol,
    PipelineStatus,
    SourceType,
    TransferDirection,
    ValidationSeverity,
)
from app.services.external_data_integration_service import (
    ExternalDataIntegrationService,
    get_external_data_integration_service,
    reset_external_data_integration_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/external-data-integration"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_external_data_integration_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ExternalDataIntegrationService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_data_source_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "source_name": "Test Data Source",
        "source_type": "edc",
        "connection_protocol": "rest_api",
        "registered_by": "Test User",
        "vendor_name": "Test Vendor",
        "data_format": "JSON",
    }
    defaults.update(overrides)
    return defaults


def _make_pipeline_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "source_id": "DS-001",
        "pipeline_name": "Test Pipeline",
        "managed_by": "Test Manager",
        "direction": "inbound",
        "schedule_cron": "0 */6 * * *",
    }
    defaults.update(overrides)
    return defaults


def _make_validation_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "pipeline_id": "PIP-001",
        "validation_name": "Test Validation",
        "rule_description": "Validate test data quality",
        "validated_by": "Test Validator",
        "records_validated": 100,
        "severity": "info",
    }
    defaults.update(overrides)
    return defaults


def _make_mapping_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "source_id": "DS-001",
        "mapping_name": "Test Mapping",
        "source_field": "source.field",
        "target_field": "target.field",
        "created_by": "Test Creator",
        "transformation_rule": "direct",
    }
    defaults.update(overrides)
    return defaults


def _make_transfer_log_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "pipeline_id": "PIP-001",
        "direction": "inbound",
        "initiated_by": "Test Initiator",
        "records_sent": 0,
        "records_received": 500,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_data_sources_count(self, svc: ExternalDataIntegrationService):
        sources = svc.list_data_sources()
        assert len(sources) == 12

    def test_seed_data_sources_ids(self, svc: ExternalDataIntegrationService):
        sources = svc.list_data_sources()
        ids = {s.id for s in sources}
        for i in range(1, 13):
            assert f"DS-{i:03d}" in ids

    def test_seed_pipelines_count(self, svc: ExternalDataIntegrationService):
        pipelines = svc.list_pipelines()
        assert len(pipelines) == 12

    def test_seed_pipelines_ids(self, svc: ExternalDataIntegrationService):
        pipelines = svc.list_pipelines()
        ids = {p.id for p in pipelines}
        for i in range(1, 13):
            assert f"PIP-{i:03d}" in ids

    def test_seed_validations_count(self, svc: ExternalDataIntegrationService):
        validations = svc.list_validations()
        assert len(validations) == 12

    def test_seed_validations_ids(self, svc: ExternalDataIntegrationService):
        validations = svc.list_validations()
        ids = {v.id for v in validations}
        for i in range(1, 13):
            assert f"DQV-{i:03d}" in ids

    def test_seed_mappings_count(self, svc: ExternalDataIntegrationService):
        mappings = svc.list_mappings()
        assert len(mappings) == 12

    def test_seed_mappings_ids(self, svc: ExternalDataIntegrationService):
        mappings = svc.list_mappings()
        ids = {m.id for m in mappings}
        for i in range(1, 13):
            assert f"MAP-{i:03d}" in ids

    def test_seed_transfer_logs_count(self, svc: ExternalDataIntegrationService):
        logs = svc.list_transfer_logs()
        assert len(logs) == 12

    def test_seed_transfer_logs_ids(self, svc: ExternalDataIntegrationService):
        logs = svc.list_transfer_logs()
        ids = {t.id for t in logs}
        for i in range(1, 13):
            assert f"TL-{i:03d}" in ids

    def test_seed_data_sources_have_all_trials(self, svc: ExternalDataIntegrationService):
        sources = svc.list_data_sources()
        trial_ids = {s.trial_id for s in sources}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_data_sources_have_all_types(self, svc: ExternalDataIntegrationService):
        sources = svc.list_data_sources()
        types = {s.source_type for s in sources}
        assert SourceType.EDC in types
        assert SourceType.LABORATORY in types
        assert SourceType.IMAGING in types
        assert SourceType.WEARABLE in types
        assert SourceType.EHR in types
        assert SourceType.REGISTRY in types

    def test_seed_pipelines_have_multiple_statuses(self, svc: ExternalDataIntegrationService):
        pipelines = svc.list_pipelines()
        statuses = {p.status for p in pipelines}
        assert PipelineStatus.ACTIVE in statuses
        assert PipelineStatus.PAUSED in statuses
        assert PipelineStatus.TESTING in statuses

    def test_seed_validations_have_multiple_severities(self, svc: ExternalDataIntegrationService):
        validations = svc.list_validations()
        severities = {v.severity for v in validations}
        assert ValidationSeverity.INFO in severities
        assert ValidationSeverity.WARNING in severities
        assert ValidationSeverity.ERROR in severities
        assert ValidationSeverity.CRITICAL in severities
        assert ValidationSeverity.BLOCKING in severities

    def test_seed_transfer_logs_have_multiple_statuses(self, svc: ExternalDataIntegrationService):
        logs = svc.list_transfer_logs()
        statuses = {t.status for t in logs}
        assert "completed" in statuses
        assert "failed" in statuses
        assert "completed_with_warnings" in statuses


# =====================================================================
# DATA SOURCE CRUD
# =====================================================================


class TestDataSourceCRUD:
    """Test data source create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_data_sources(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_data_sources_filter_trial_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_data_sources_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_data_sources_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_data_sources_filter_type_edc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources", params={"source_type": "edc"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["source_type"] == "edc"

    @pytest.mark.anyio
    async def test_list_data_sources_filter_type_laboratory(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources", params={"source_type": "laboratory"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["source_type"] == "laboratory"

    @pytest.mark.anyio
    async def test_list_data_sources_filter_type_imaging(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources", params={"source_type": "imaging"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["source_type"] == "imaging"

    @pytest.mark.anyio
    async def test_list_data_sources_filter_type_wearable(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources", params={"source_type": "wearable"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["source_type"] == "wearable"

    @pytest.mark.anyio
    async def test_list_data_sources_filter_type_ehr(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources", params={"source_type": "ehr"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["source_type"] == "ehr"

    @pytest.mark.anyio
    async def test_list_data_sources_filter_type_registry(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources", params={"source_type": "registry"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["source_type"] == "registry"

    @pytest.mark.anyio
    async def test_list_data_sources_filter_protocol_rest_api(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/data-sources", params={"connection_protocol": "rest_api"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["connection_protocol"] == "rest_api"

    @pytest.mark.anyio
    async def test_list_data_sources_filter_protocol_sftp(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/data-sources", params={"connection_protocol": "sftp"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["connection_protocol"] == "sftp"

    @pytest.mark.anyio
    async def test_list_data_sources_filter_protocol_hl7_fhir(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/data-sources", params={"connection_protocol": "hl7_fhir"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["connection_protocol"] == "hl7_fhir"

    @pytest.mark.anyio
    async def test_list_data_sources_filter_protocol_cdisc_odm(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/data-sources", params={"connection_protocol": "cdisc_odm"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["connection_protocol"] == "cdisc_odm"

    @pytest.mark.anyio
    async def test_list_data_sources_filter_protocol_database_link(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/data-sources", params={"connection_protocol": "database_link"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["connection_protocol"] == "database_link"

    @pytest.mark.anyio
    async def test_list_data_sources_filter_protocol_file_import(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/data-sources", params={"connection_protocol": "file_import"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["connection_protocol"] == "file_import"

    @pytest.mark.anyio
    async def test_list_data_sources_filter_active_true(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources", params={"is_active": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["is_active"] is True

    @pytest.mark.anyio
    async def test_list_data_sources_filter_active_false(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources", params={"is_active": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["is_active"] is False

    @pytest.mark.anyio
    async def test_list_data_sources_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/data-sources",
            params={"trial_id": EYLEA_TRIAL, "source_type": "edc", "is_active": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["source_type"] == "edc"
            assert item["is_active"] is True

    @pytest.mark.anyio
    async def test_list_data_sources_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/data-sources",
            params={"trial_id": "nonexistent-trial"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_data_source(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources/DS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DS-001"
        assert data["source_name"] == "Medidata Rave EDC"
        assert data["source_type"] == "edc"
        assert data["connection_protocol"] == "rest_api"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_data_source_ds002(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources/DS-002")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DS-002"
        assert data["source_type"] == "laboratory"

    @pytest.mark.anyio
    async def test_get_data_source_ds007(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources/DS-007")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DS-007"
        assert data["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_data_source_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources/DS-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_data_source(self, client: AsyncClient):
        payload = _make_data_source_create()
        resp = await client.post(f"{API_PREFIX}/data-sources", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["source_name"] == "Test Data Source"
        assert data["source_type"] == "edc"
        assert data["connection_protocol"] == "rest_api"
        assert data["vendor_name"] == "Test Vendor"
        assert data["data_format"] == "JSON"
        assert data["is_active"] is True
        assert data["id"].startswith("DS-")
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_data_source_laboratory(self, client: AsyncClient):
        payload = _make_data_source_create(
            source_name="New Lab Source",
            source_type="laboratory",
            connection_protocol="hl7_fhir",
        )
        resp = await client.post(f"{API_PREFIX}/data-sources", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["source_type"] == "laboratory"
        assert data["connection_protocol"] == "hl7_fhir"

    @pytest.mark.anyio
    async def test_create_data_source_appears_in_list(self, client: AsyncClient):
        payload = _make_data_source_create(source_name="Unique New Source")
        resp = await client.post(f"{API_PREFIX}/data-sources", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/data-sources")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert data["total"] == 13
        ids = {item["id"] for item in data["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_data_source_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/data-sources/DS-001",
            json={"notes": "Updated notes for testing"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated notes for testing"

    @pytest.mark.anyio
    async def test_update_data_source_active_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/data-sources/DS-001",
            json={"is_active": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_active"] is False

    @pytest.mark.anyio
    async def test_update_data_source_refresh_frequency(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/data-sources/DS-001",
            json={"refresh_frequency": "weekly"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["refresh_frequency"] == "weekly"

    @pytest.mark.anyio
    async def test_update_data_source_total_records_synced(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/data-sources/DS-001",
            json={"total_records_synced": 200000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_records_synced"] == 200000

    @pytest.mark.anyio
    async def test_update_data_source_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/data-sources/DS-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_data_source(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/data-sources/DS-001")
        assert resp.status_code == 204
        # Verify it's gone
        resp2 = await client.get(f"{API_PREFIX}/data-sources/DS-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_data_source_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/data-sources/DS-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/data-sources")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_data_source_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/data-sources/DS-NONEXISTENT")
        assert resp.status_code == 404

    # --- Service-level tests ---

    def test_service_list_data_sources_filter_type(self, svc: ExternalDataIntegrationService):
        sources = svc.list_data_sources(source_type=SourceType.EDC)
        assert len(sources) > 0
        for s in sources:
            assert s.source_type == SourceType.EDC

    def test_service_list_data_sources_filter_protocol(self, svc: ExternalDataIntegrationService):
        sources = svc.list_data_sources(connection_protocol=ConnectionProtocol.REST_API)
        assert len(sources) > 0
        for s in sources:
            assert s.connection_protocol == ConnectionProtocol.REST_API

    def test_service_list_data_sources_filter_active(self, svc: ExternalDataIntegrationService):
        active = svc.list_data_sources(is_active=True)
        inactive = svc.list_data_sources(is_active=False)
        assert len(active) + len(inactive) == 12
        assert len(inactive) > 0  # DS-010 is inactive

    def test_service_get_data_source_none(self, svc: ExternalDataIntegrationService):
        result = svc.get_data_source("DS-NONEXISTENT")
        assert result is None

    def test_service_delete_data_source_nonexistent(self, svc: ExternalDataIntegrationService):
        result = svc.delete_data_source("DS-NONEXISTENT")
        assert result is False


# =====================================================================
# PIPELINE CRUD
# =====================================================================


class TestPipelineCRUD:
    """Test pipeline create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_pipelines(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pipelines")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_pipelines_filter_trial_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pipelines", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_pipelines_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pipelines", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_pipelines_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pipelines", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_pipelines_filter_status_active(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pipelines", params={"status": "active"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "active"

    @pytest.mark.anyio
    async def test_list_pipelines_filter_status_paused(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pipelines", params={"status": "paused"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "paused"

    @pytest.mark.anyio
    async def test_list_pipelines_filter_status_testing(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pipelines", params={"status": "testing"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "testing"

    @pytest.mark.anyio
    async def test_list_pipelines_filter_source_ds001(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pipelines", params={"source_id": "DS-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["source_id"] == "DS-001"

    @pytest.mark.anyio
    async def test_list_pipelines_filter_source_ds004(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pipelines", params={"source_id": "DS-004"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["source_id"] == "DS-004"

    @pytest.mark.anyio
    async def test_list_pipelines_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/pipelines",
            params={"trial_id": EYLEA_TRIAL, "status": "active"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["status"] == "active"

    @pytest.mark.anyio
    async def test_list_pipelines_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/pipelines", params={"trial_id": "nonexistent-trial"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_pipeline(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pipelines/PIP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PIP-001"
        assert data["pipeline_name"] == "EYLEA EDC Incremental Sync"
        assert data["status"] == "active"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_pipeline_pip004(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pipelines/PIP-004")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PIP-004"
        assert data["direction"] == "bidirectional"

    @pytest.mark.anyio
    async def test_get_pipeline_pip012(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pipelines/PIP-012")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PIP-012"
        assert data["status"] == "testing"

    @pytest.mark.anyio
    async def test_get_pipeline_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pipelines/PIP-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_pipeline(self, client: AsyncClient):
        payload = _make_pipeline_create()
        resp = await client.post(f"{API_PREFIX}/pipelines", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["pipeline_name"] == "Test Pipeline"
        assert data["status"] == "configured"
        assert data["direction"] == "inbound"
        assert data["source_id"] == "DS-001"
        assert data["id"].startswith("PIP-")
        assert data["total_runs"] == 0
        assert data["successful_runs"] == 0
        assert data["failed_runs"] == 0

    @pytest.mark.anyio
    async def test_create_pipeline_outbound(self, client: AsyncClient):
        payload = _make_pipeline_create(
            pipeline_name="Outbound Export",
            direction="outbound",
        )
        resp = await client.post(f"{API_PREFIX}/pipelines", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["direction"] == "outbound"

    @pytest.mark.anyio
    async def test_create_pipeline_appears_in_list(self, client: AsyncClient):
        payload = _make_pipeline_create(pipeline_name="Unique Pipeline")
        resp = await client.post(f"{API_PREFIX}/pipelines", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/pipelines")
        assert list_resp.json()["total"] == 13
        ids = {item["id"] for item in list_resp.json()["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_pipeline_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/pipelines/PIP-006",
            json={"status": "active"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"

    @pytest.mark.anyio
    async def test_update_pipeline_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/pipelines/PIP-001",
            json={"notes": "Updated pipeline notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated pipeline notes"

    @pytest.mark.anyio
    async def test_update_pipeline_auto_retry(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/pipelines/PIP-001",
            json={"auto_retry": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["auto_retry"] is False

    @pytest.mark.anyio
    async def test_update_pipeline_runs(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/pipelines/PIP-001",
            json={"successful_runs": 5000, "failed_runs": 30},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["successful_runs"] == 5000
        assert data["failed_runs"] == 30

    @pytest.mark.anyio
    async def test_update_pipeline_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/pipelines/PIP-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_pipeline(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/pipelines/PIP-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/pipelines/PIP-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_pipeline_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/pipelines/PIP-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/pipelines")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_pipeline_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/pipelines/PIP-NONEXISTENT")
        assert resp.status_code == 404

    # --- Service-level tests ---

    def test_service_list_pipelines_filter_status(self, svc: ExternalDataIntegrationService):
        pipelines = svc.list_pipelines(status=PipelineStatus.ACTIVE)
        assert len(pipelines) > 0
        for p in pipelines:
            assert p.status == PipelineStatus.ACTIVE

    def test_service_list_pipelines_filter_source(self, svc: ExternalDataIntegrationService):
        pipelines = svc.list_pipelines(source_id="DS-001")
        assert len(pipelines) > 0
        for p in pipelines:
            assert p.source_id == "DS-001"

    def test_service_get_pipeline_none(self, svc: ExternalDataIntegrationService):
        result = svc.get_pipeline("PIP-NONEXISTENT")
        assert result is None

    def test_service_delete_pipeline_nonexistent(self, svc: ExternalDataIntegrationService):
        result = svc.delete_pipeline("PIP-NONEXISTENT")
        assert result is False


# =====================================================================
# VALIDATION CRUD
# =====================================================================


class TestValidationCRUD:
    """Test validation create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_validations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_validations_filter_trial_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_validations_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_validations_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_validations_filter_severity_info(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"severity": "info"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["severity"] == "info"

    @pytest.mark.anyio
    async def test_list_validations_filter_severity_warning(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"severity": "warning"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["severity"] == "warning"

    @pytest.mark.anyio
    async def test_list_validations_filter_severity_error(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"severity": "error"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["severity"] == "error"

    @pytest.mark.anyio
    async def test_list_validations_filter_severity_critical(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"severity": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["severity"] == "critical"

    @pytest.mark.anyio
    async def test_list_validations_filter_severity_blocking(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"severity": "blocking"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["severity"] == "blocking"

    @pytest.mark.anyio
    async def test_list_validations_filter_pipeline_pip001(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"pipeline_id": "PIP-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["pipeline_id"] == "PIP-001"

    @pytest.mark.anyio
    async def test_list_validations_filter_pipeline_pip004(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"pipeline_id": "PIP-004"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["pipeline_id"] == "PIP-004"

    @pytest.mark.anyio
    async def test_list_validations_filter_resolved_true(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"resolved": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["resolved"] is True

    @pytest.mark.anyio
    async def test_list_validations_filter_resolved_false(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"resolved": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["resolved"] is False

    @pytest.mark.anyio
    async def test_list_validations_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/validations",
            params={"trial_id": EYLEA_TRIAL, "resolved": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["resolved"] is False

    @pytest.mark.anyio
    async def test_list_validations_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/validations", params={"trial_id": "nonexistent-trial"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_validation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations/DQV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DQV-001"
        assert data["validation_name"] == "EDC Subject ID Consistency"
        assert data["severity"] == "info"
        assert data["resolved"] is True

    @pytest.mark.anyio
    async def test_get_validation_dqv006(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations/DQV-006")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DQV-006"
        assert data["severity"] == "critical"
        assert data["pass_rate_pct"] == 0.0

    @pytest.mark.anyio
    async def test_get_validation_dqv012(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations/DQV-012")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DQV-012"
        assert data["severity"] == "blocking"

    @pytest.mark.anyio
    async def test_get_validation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations/DQV-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_validation(self, client: AsyncClient):
        payload = _make_validation_create()
        resp = await client.post(f"{API_PREFIX}/validations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["validation_name"] == "Test Validation"
        assert data["severity"] == "info"
        assert data["records_validated"] == 100
        assert data["records_passed"] == 100
        assert data["records_failed"] == 0
        assert data["pass_rate_pct"] == 100.0
        assert data["resolved"] is False
        assert data["id"].startswith("DQV-")

    @pytest.mark.anyio
    async def test_create_validation_warning(self, client: AsyncClient):
        payload = _make_validation_create(
            validation_name="Warning Validation",
            severity="warning",
            records_validated=500,
        )
        resp = await client.post(f"{API_PREFIX}/validations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["severity"] == "warning"
        assert data["records_validated"] == 500

    @pytest.mark.anyio
    async def test_create_validation_appears_in_list(self, client: AsyncClient):
        payload = _make_validation_create(validation_name="Unique Validation")
        resp = await client.post(f"{API_PREFIX}/validations", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/validations")
        assert list_resp.json()["total"] == 13
        ids = {item["id"] for item in list_resp.json()["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_validation_resolved(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/validations/DQV-002",
            json={"resolved": True, "resolved_by": "Test Resolver"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolved"] is True
        assert data["resolved_by"] == "Test Resolver"

    @pytest.mark.anyio
    async def test_update_validation_severity(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/validations/DQV-002",
            json={"severity": "error"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["severity"] == "error"

    @pytest.mark.anyio
    async def test_update_validation_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/validations/DQV-001",
            json={"notes": "Updated validation notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated validation notes"

    @pytest.mark.anyio
    async def test_update_validation_records_failed(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/validations/DQV-002",
            json={"records_failed": 20},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["records_failed"] == 20

    @pytest.mark.anyio
    async def test_update_validation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/validations/DQV-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_validation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/validations/DQV-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/validations/DQV-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_validation_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/validations/DQV-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/validations")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_validation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/validations/DQV-NONEXISTENT")
        assert resp.status_code == 404

    # --- Service-level tests ---

    def test_service_list_validations_filter_severity(self, svc: ExternalDataIntegrationService):
        validations = svc.list_validations(severity=ValidationSeverity.WARNING)
        assert len(validations) > 0
        for v in validations:
            assert v.severity == ValidationSeverity.WARNING

    def test_service_list_validations_filter_pipeline(self, svc: ExternalDataIntegrationService):
        validations = svc.list_validations(pipeline_id="PIP-001")
        assert len(validations) > 0
        for v in validations:
            assert v.pipeline_id == "PIP-001"

    def test_service_list_validations_filter_resolved(self, svc: ExternalDataIntegrationService):
        resolved = svc.list_validations(resolved=True)
        unresolved = svc.list_validations(resolved=False)
        assert len(resolved) + len(unresolved) == 12

    def test_service_get_validation_none(self, svc: ExternalDataIntegrationService):
        result = svc.get_validation("DQV-NONEXISTENT")
        assert result is None

    def test_service_delete_validation_nonexistent(self, svc: ExternalDataIntegrationService):
        result = svc.delete_validation("DQV-NONEXISTENT")
        assert result is False


# =====================================================================
# MAPPING CRUD
# =====================================================================


class TestMappingCRUD:
    """Test mapping configuration create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_mappings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mappings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_mappings_filter_trial_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mappings", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_mappings_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mappings", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_mappings_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mappings", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_mappings_filter_source_ds001(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mappings", params={"source_id": "DS-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["source_id"] == "DS-001"

    @pytest.mark.anyio
    async def test_list_mappings_filter_source_ds002(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mappings", params={"source_id": "DS-002"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["source_id"] == "DS-002"

    @pytest.mark.anyio
    async def test_list_mappings_filter_source_ds007(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mappings", params={"source_id": "DS-007"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["source_id"] == "DS-007"

    @pytest.mark.anyio
    async def test_list_mappings_filter_validated_true(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mappings", params={"validated": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["validated"] is True

    @pytest.mark.anyio
    async def test_list_mappings_filter_validated_false(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mappings", params={"validated": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["validated"] is False

    @pytest.mark.anyio
    async def test_list_mappings_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/mappings",
            params={"trial_id": EYLEA_TRIAL, "validated": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["validated"] is True

    @pytest.mark.anyio
    async def test_list_mappings_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/mappings", params={"trial_id": "nonexistent-trial"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_mapping(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mappings/MAP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MAP-001"
        assert data["mapping_name"] == "EDC Subject ID to CDASH SUBJID"
        assert data["transformation_rule"] == "direct"
        assert data["validated"] is True

    @pytest.mark.anyio
    async def test_get_mapping_map006(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mappings/MAP-006")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MAP-006"
        assert data["validated"] is False

    @pytest.mark.anyio
    async def test_get_mapping_map012(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mappings/MAP-012")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MAP-012"
        assert data["validated"] is False
        assert data["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_mapping_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mappings/MAP-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_mapping(self, client: AsyncClient):
        payload = _make_mapping_create()
        resp = await client.post(f"{API_PREFIX}/mappings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["mapping_name"] == "Test Mapping"
        assert data["source_field"] == "source.field"
        assert data["target_field"] == "target.field"
        assert data["transformation_rule"] == "direct"
        assert data["validated"] is False
        assert data["id"].startswith("MAP-")

    @pytest.mark.anyio
    async def test_create_mapping_lookup(self, client: AsyncClient):
        payload = _make_mapping_create(
            mapping_name="Lookup Mapping",
            transformation_rule="lookup",
        )
        resp = await client.post(f"{API_PREFIX}/mappings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["transformation_rule"] == "lookup"

    @pytest.mark.anyio
    async def test_create_mapping_appears_in_list(self, client: AsyncClient):
        payload = _make_mapping_create(mapping_name="Unique Mapping")
        resp = await client.post(f"{API_PREFIX}/mappings", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/mappings")
        assert list_resp.json()["total"] == 13
        ids = {item["id"] for item in list_resp.json()["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_mapping_validated(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/mappings/MAP-006",
            json={"validated": True, "approved_by": "Dr. Test Approver"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["validated"] is True
        assert data["approved_by"] == "Dr. Test Approver"

    @pytest.mark.anyio
    async def test_update_mapping_transformation_rule(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/mappings/MAP-001",
            json={"transformation_rule": "regex_extract"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["transformation_rule"] == "regex_extract"

    @pytest.mark.anyio
    async def test_update_mapping_default_value(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/mappings/MAP-001",
            json={"default_value": "N/A"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["default_value"] == "N/A"

    @pytest.mark.anyio
    async def test_update_mapping_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/mappings/MAP-001",
            json={"notes": "Updated mapping notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated mapping notes"

    @pytest.mark.anyio
    async def test_update_mapping_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/mappings/MAP-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_mapping(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/mappings/MAP-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/mappings/MAP-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_mapping_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/mappings/MAP-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/mappings")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_mapping_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/mappings/MAP-NONEXISTENT")
        assert resp.status_code == 404

    # --- Service-level tests ---

    def test_service_list_mappings_filter_source(self, svc: ExternalDataIntegrationService):
        mappings = svc.list_mappings(source_id="DS-002")
        assert len(mappings) > 0
        for m in mappings:
            assert m.source_id == "DS-002"

    def test_service_list_mappings_filter_validated(self, svc: ExternalDataIntegrationService):
        validated = svc.list_mappings(validated=True)
        unvalidated = svc.list_mappings(validated=False)
        assert len(validated) + len(unvalidated) == 12
        assert len(unvalidated) > 0  # MAP-006 and MAP-012 are unvalidated

    def test_service_get_mapping_none(self, svc: ExternalDataIntegrationService):
        result = svc.get_mapping("MAP-NONEXISTENT")
        assert result is None

    def test_service_delete_mapping_nonexistent(self, svc: ExternalDataIntegrationService):
        result = svc.delete_mapping("MAP-NONEXISTENT")
        assert result is False


# =====================================================================
# TRANSFER LOG CRUD
# =====================================================================


class TestTransferLogCRUD:
    """Test transfer log create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_transfer_logs(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/transfer-logs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_transfer_logs_filter_trial_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/transfer-logs", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_transfer_logs_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/transfer-logs", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_transfer_logs_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/transfer-logs", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_transfer_logs_filter_pipeline_pip001(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/transfer-logs", params={"pipeline_id": "PIP-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["pipeline_id"] == "PIP-001"

    @pytest.mark.anyio
    async def test_list_transfer_logs_filter_pipeline_pip004(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/transfer-logs", params={"pipeline_id": "PIP-004"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["pipeline_id"] == "PIP-004"

    @pytest.mark.anyio
    async def test_list_transfer_logs_filter_direction_inbound(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/transfer-logs", params={"direction": "inbound"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["direction"] == "inbound"

    @pytest.mark.anyio
    async def test_list_transfer_logs_filter_direction_bidirectional(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/transfer-logs", params={"direction": "bidirectional"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["direction"] == "bidirectional"

    @pytest.mark.anyio
    async def test_list_transfer_logs_filter_status_completed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/transfer-logs", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_transfer_logs_filter_status_failed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/transfer-logs", params={"status": "failed"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "failed"

    @pytest.mark.anyio
    async def test_list_transfer_logs_filter_status_completed_with_warnings(
        self, client: AsyncClient
    ):
        resp = await client.get(
            f"{API_PREFIX}/transfer-logs", params={"status": "completed_with_warnings"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "completed_with_warnings"

    @pytest.mark.anyio
    async def test_list_transfer_logs_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/transfer-logs",
            params={"trial_id": EYLEA_TRIAL, "direction": "inbound"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["direction"] == "inbound"

    @pytest.mark.anyio
    async def test_list_transfer_logs_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/transfer-logs", params={"trial_id": "nonexistent-trial"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_transfer_log(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/transfer-logs/TL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TL-001"
        assert data["status"] == "completed"
        assert data["direction"] == "inbound"
        assert data["records_received"] == 342
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_transfer_log_tl004(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/transfer-logs/TL-004")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TL-004"
        assert data["direction"] == "bidirectional"
        assert data["records_sent"] == 45
        assert data["records_received"] == 180

    @pytest.mark.anyio
    async def test_get_transfer_log_tl006(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/transfer-logs/TL-006")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TL-006"
        assert data["status"] == "failed"
        assert data["records_rejected"] == 520

    @pytest.mark.anyio
    async def test_get_transfer_log_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/transfer-logs/TL-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_transfer_log(self, client: AsyncClient):
        payload = _make_transfer_log_create()
        resp = await client.post(f"{API_PREFIX}/transfer-logs", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["direction"] == "inbound"
        assert data["records_sent"] == 0
        assert data["records_received"] == 500
        assert data["status"] == "in_progress"
        assert data["records_rejected"] == 0
        assert data["acknowledged_by_target"] is False
        assert data["id"].startswith("TL-")

    @pytest.mark.anyio
    async def test_create_transfer_log_outbound(self, client: AsyncClient):
        payload = _make_transfer_log_create(
            direction="outbound",
            records_sent=200,
            records_received=0,
        )
        resp = await client.post(f"{API_PREFIX}/transfer-logs", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["direction"] == "outbound"
        assert data["records_sent"] == 200

    @pytest.mark.anyio
    async def test_create_transfer_log_appears_in_list(self, client: AsyncClient):
        payload = _make_transfer_log_create()
        resp = await client.post(f"{API_PREFIX}/transfer-logs", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/transfer-logs")
        assert list_resp.json()["total"] == 13
        ids = {item["id"] for item in list_resp.json()["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_transfer_log_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/transfer-logs/TL-001",
            json={"status": "archived"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "archived"

    @pytest.mark.anyio
    async def test_update_transfer_log_acknowledged(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/transfer-logs/TL-006",
            json={"acknowledged_by_target": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["acknowledged_by_target"] is True

    @pytest.mark.anyio
    async def test_update_transfer_log_records_rejected(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/transfer-logs/TL-001",
            json={"records_rejected": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["records_rejected"] == 5

    @pytest.mark.anyio
    async def test_update_transfer_log_error_message(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/transfer-logs/TL-001",
            json={"error_message": "Timeout during transfer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["error_message"] == "Timeout during transfer"

    @pytest.mark.anyio
    async def test_update_transfer_log_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/transfer-logs/TL-001",
            json={"notes": "Updated transfer notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated transfer notes"

    @pytest.mark.anyio
    async def test_update_transfer_log_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/transfer-logs/TL-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_transfer_log(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/transfer-logs/TL-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/transfer-logs/TL-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_transfer_log_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/transfer-logs/TL-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/transfer-logs")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_transfer_log_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/transfer-logs/TL-NONEXISTENT")
        assert resp.status_code == 404

    # --- Service-level tests ---

    def test_service_list_transfer_logs_filter_pipeline(
        self, svc: ExternalDataIntegrationService
    ):
        logs = svc.list_transfer_logs(pipeline_id="PIP-001")
        assert len(logs) > 0
        for t in logs:
            assert t.pipeline_id == "PIP-001"

    def test_service_list_transfer_logs_filter_direction(
        self, svc: ExternalDataIntegrationService
    ):
        logs = svc.list_transfer_logs(direction=TransferDirection.INBOUND)
        assert len(logs) > 0
        for t in logs:
            assert t.direction == TransferDirection.INBOUND

    def test_service_list_transfer_logs_filter_status(
        self, svc: ExternalDataIntegrationService
    ):
        logs = svc.list_transfer_logs(status="completed")
        assert len(logs) > 0
        for t in logs:
            assert t.status == "completed"

    def test_service_list_transfer_logs_filter_bidirectional(
        self, svc: ExternalDataIntegrationService
    ):
        logs = svc.list_transfer_logs(direction=TransferDirection.BIDIRECTIONAL)
        assert len(logs) > 0
        for t in logs:
            assert t.direction == TransferDirection.BIDIRECTIONAL

    def test_service_get_transfer_log_none(self, svc: ExternalDataIntegrationService):
        result = svc.get_transfer_log("TL-NONEXISTENT")
        assert result is None

    def test_service_delete_transfer_log_nonexistent(self, svc: ExternalDataIntegrationService):
        result = svc.delete_transfer_log("TL-NONEXISTENT")
        assert result is False


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test external data integration metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_data_sources"] == 12
        assert data["total_pipelines"] == 12
        assert data["total_validations"] == 12
        assert data["total_mappings"] == 12
        assert data["total_transfers"] == 12

    @pytest.mark.anyio
    async def test_metrics_active_sources(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        # DS-010 is inactive, so active_sources should be 11
        assert data["active_sources"] == 11

    @pytest.mark.anyio
    async def test_metrics_active_pipelines(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["active_pipelines"] > 0

    @pytest.mark.anyio
    async def test_metrics_sources_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        sources_by_type = data["sources_by_type"]
        assert "edc" in sources_by_type
        assert "laboratory" in sources_by_type
        assert "imaging" in sources_by_type
        total_by_type = sum(sources_by_type.values())
        assert total_by_type == 12

    @pytest.mark.anyio
    async def test_metrics_sources_by_protocol(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        sources_by_protocol = data["sources_by_protocol"]
        assert "rest_api" in sources_by_protocol
        total_by_protocol = sum(sources_by_protocol.values())
        assert total_by_protocol == 12

    @pytest.mark.anyio
    async def test_metrics_pipelines_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        pipelines_by_status = data["pipelines_by_status"]
        assert "active" in pipelines_by_status
        total_by_status = sum(pipelines_by_status.values())
        assert total_by_status == 12

    @pytest.mark.anyio
    async def test_metrics_validations_by_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        validations_by_severity = data["validations_by_severity"]
        assert "info" in validations_by_severity
        assert "warning" in validations_by_severity
        total_by_severity = sum(validations_by_severity.values())
        assert total_by_severity == 12

    @pytest.mark.anyio
    async def test_metrics_unresolved_validations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["unresolved_validations"] > 0
        # Verify count matches service
        svc = get_external_data_integration_service()
        unresolved = svc.list_validations(resolved=False)
        assert data["unresolved_validations"] == len(unresolved)

    @pytest.mark.anyio
    async def test_metrics_validated_mappings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["validated_mappings"] > 0
        svc = get_external_data_integration_service()
        validated = svc.list_mappings(validated=True)
        assert data["validated_mappings"] == len(validated)

    @pytest.mark.anyio
    async def test_metrics_transfers_by_direction(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        transfers_by_direction = data["transfers_by_direction"]
        assert "inbound" in transfers_by_direction
        total_by_direction = sum(transfers_by_direction.values())
        assert total_by_direction == 12

    @pytest.mark.anyio
    async def test_metrics_total_records_transferred(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_records_transferred"] > 0

    def test_service_metrics_total_records_transferred(
        self, svc: ExternalDataIntegrationService
    ):
        metrics = svc.get_metrics()
        logs = svc.list_transfer_logs()
        expected = sum(t.records_received + t.records_sent for t in logs)
        assert metrics.total_records_transferred == expected

    def test_service_metrics_active_sources_count(self, svc: ExternalDataIntegrationService):
        metrics = svc.get_metrics()
        active = svc.list_data_sources(is_active=True)
        assert metrics.active_sources == len(active)

    def test_service_metrics_active_pipelines_count(self, svc: ExternalDataIntegrationService):
        metrics = svc.get_metrics()
        active = svc.list_pipelines(status=PipelineStatus.ACTIVE)
        assert metrics.active_pipelines == len(active)

    def test_service_metrics_after_create(self, svc: ExternalDataIntegrationService):
        """Metrics should update after creating a new data source."""
        from app.schemas.external_data_integration import DataSourceRegistryCreate

        initial_metrics = svc.get_metrics()
        svc.create_data_source(
            DataSourceRegistryCreate(
                trial_id=EYLEA_TRIAL,
                source_name="New Source",
                source_type=SourceType.EDC,
                connection_protocol=ConnectionProtocol.REST_API,
                registered_by="Test User",
            )
        )
        updated_metrics = svc.get_metrics()
        assert updated_metrics.total_data_sources == initial_metrics.total_data_sources + 1

    def test_service_metrics_after_delete(self, svc: ExternalDataIntegrationService):
        """Metrics should update after deleting a data source."""
        initial_metrics = svc.get_metrics()
        svc.delete_data_source("DS-001")
        updated_metrics = svc.get_metrics()
        assert updated_metrics.total_data_sources == initial_metrics.total_data_sources - 1


# =====================================================================
# SINGLETON PATTERN
# =====================================================================


class TestSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_external_data_integration_service()
        svc2 = get_external_data_integration_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_external_data_integration_service()
        svc2 = reset_external_data_integration_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_external_data_integration_service()
        # Delete a data source
        svc.delete_data_source("DS-001")
        assert svc.get_data_source("DS-001") is None
        # Reset should bring it back
        svc2 = reset_external_data_integration_service()
        assert svc2.get_data_source("DS-001") is not None

    def test_reset_reseeds_pipelines(self):
        svc = get_external_data_integration_service()
        svc.delete_pipeline("PIP-001")
        assert svc.get_pipeline("PIP-001") is None
        svc2 = reset_external_data_integration_service()
        assert svc2.get_pipeline("PIP-001") is not None

    def test_reset_reseeds_validations(self):
        svc = get_external_data_integration_service()
        svc.delete_validation("DQV-001")
        assert svc.get_validation("DQV-001") is None
        svc2 = reset_external_data_integration_service()
        assert svc2.get_validation("DQV-001") is not None

    def test_reset_reseeds_mappings(self):
        svc = get_external_data_integration_service()
        svc.delete_mapping("MAP-001")
        assert svc.get_mapping("MAP-001") is None
        svc2 = reset_external_data_integration_service()
        assert svc2.get_mapping("MAP-001") is not None

    def test_reset_reseeds_transfer_logs(self):
        svc = get_external_data_integration_service()
        svc.delete_transfer_log("TL-001")
        assert svc.get_transfer_log("TL-001") is None
        svc2 = reset_external_data_integration_service()
        assert svc2.get_transfer_log("TL-001") is not None

    def test_get_after_reset_returns_new_instance(self):
        svc1 = get_external_data_integration_service()
        reset_external_data_integration_service()
        svc2 = get_external_data_integration_service()
        assert svc1 is not svc2
