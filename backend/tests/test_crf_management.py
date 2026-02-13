"""Tests for CRF Management (CRF-MGT).

Covers:
- Seed data verification (CRF versions, fields, edit check rules, deployments, annotations)
- CRF version CRUD (create, read, update, delete, list, filter by trial/status)
- CRF field CRUD (create, read, update, delete, list, filter by trial/version/type)
- Edit check rule CRUD (create, read, update, delete, list, filter by trial/version/severity/active)
- CRF deployment CRUD (create, read, update, delete, list, filter by trial/status/version)
- CRF annotation CRUD (create, read, update, delete, list, filter by trial/version/type)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
- Service-level CRUD operations
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.crf_management import (
    AnnotationType,
    CRFStatus,
    DeploymentStatus,
    EditCheckSeverity,
    FieldType,
)
from app.services.crf_management_service import (
    CRFManagementService,
    get_crf_management_service,
    reset_crf_management_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/crf-management"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_crf_management_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> CRFManagementService:
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


def _make_crf_version_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "crf_name": "Test CRF",
        "version_number": "1.0",
        "authored_by": "Test Author",
        "total_pages": 2,
    }
    defaults.update(overrides)
    return defaults


def _make_crf_field_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "crf_version_id": "CRF-001",
        "field_name": "TEST_FIELD",
        "field_label": "Test Field Label",
        "field_type": "text",
        "page_number": 1,
        "display_order": 10,
        "is_required": False,
    }
    defaults.update(overrides)
    return defaults


def _make_edit_check_rule_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "crf_version_id": "CRF-001",
        "rule_name": "TEST_RULE",
        "rule_expression": "TEST_FIELD IS NOT NULL",
        "target_field_id": "FLD-001",
        "error_message": "Test field must not be null.",
        "edit_check_severity": "warning",
        "authored_by": "Test Author",
    }
    defaults.update(overrides)
    return defaults


def _make_deployment_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "crf_version_id": "CRF-001",
        "target_environment": "UAT",
        "deployed_by": "Test Deployer",
        "sites_affected": 5,
    }
    defaults.update(overrides)
    return defaults


def _make_annotation_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "crf_version_id": "CRF-001",
        "annotation_type": "sdtm_mapping",
        "annotation_text": "Test annotation text for SDTM mapping.",
        "annotated_by": "Test Annotator",
        "field_id": "FLD-001",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_crf_versions_count(self, svc: CRFManagementService):
        versions = svc.list_crf_versions()
        assert len(versions) == 12

    def test_seed_crf_versions_ids(self, svc: CRFManagementService):
        versions = svc.list_crf_versions()
        ids = {v.id for v in versions}
        for i in range(1, 13):
            assert f"CRF-{i:03d}" in ids

    def test_seed_crf_fields_count(self, svc: CRFManagementService):
        fields = svc.list_crf_fields()
        assert len(fields) == 12

    def test_seed_crf_fields_ids(self, svc: CRFManagementService):
        fields = svc.list_crf_fields()
        ids = {f.id for f in fields}
        for i in range(1, 13):
            assert f"FLD-{i:03d}" in ids

    def test_seed_edit_check_rules_count(self, svc: CRFManagementService):
        rules = svc.list_edit_check_rules()
        assert len(rules) == 12

    def test_seed_edit_check_rules_ids(self, svc: CRFManagementService):
        rules = svc.list_edit_check_rules()
        ids = {r.id for r in rules}
        for i in range(1, 13):
            assert f"ECR-{i:03d}" in ids

    def test_seed_deployments_count(self, svc: CRFManagementService):
        deployments = svc.list_deployments()
        assert len(deployments) == 12

    def test_seed_deployments_ids(self, svc: CRFManagementService):
        deployments = svc.list_deployments()
        ids = {d.id for d in deployments}
        for i in range(1, 13):
            assert f"DEP-{i:03d}" in ids

    def test_seed_annotations_count(self, svc: CRFManagementService):
        annotations = svc.list_annotations()
        assert len(annotations) == 12

    def test_seed_annotations_ids(self, svc: CRFManagementService):
        annotations = svc.list_annotations()
        ids = {a.id for a in annotations}
        for i in range(1, 13):
            assert f"ANN-{i:03d}" in ids

    def test_seed_versions_have_all_trials(self, svc: CRFManagementService):
        versions = svc.list_crf_versions()
        trial_ids = {v.trial_id for v in versions}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_versions_have_multiple_statuses(self, svc: CRFManagementService):
        versions = svc.list_crf_versions()
        statuses = {v.crf_status for v in versions}
        assert CRFStatus.DEPLOYED in statuses
        assert CRFStatus.DRAFT in statuses
        assert CRFStatus.IN_REVIEW in statuses
        assert CRFStatus.APPROVED in statuses

    def test_seed_fields_have_multiple_types(self, svc: CRFManagementService):
        fields = svc.list_crf_fields()
        types = {f.field_type for f in fields}
        assert FieldType.TEXT in types
        assert FieldType.NUMERIC in types
        assert FieldType.DATE in types
        assert FieldType.DROPDOWN in types

    def test_seed_edit_checks_have_multiple_severities(self, svc: CRFManagementService):
        rules = svc.list_edit_check_rules()
        severities = {r.edit_check_severity for r in rules}
        assert EditCheckSeverity.ERROR in severities
        assert EditCheckSeverity.WARNING in severities
        assert EditCheckSeverity.HARD_STOP in severities

    def test_seed_deployments_have_multiple_statuses(self, svc: CRFManagementService):
        deployments = svc.list_deployments()
        statuses = {d.deployment_status for d in deployments}
        assert DeploymentStatus.COMPLETED in statuses
        assert DeploymentStatus.PENDING in statuses
        assert DeploymentStatus.FAILED in statuses

    def test_seed_annotations_have_multiple_types(self, svc: CRFManagementService):
        annotations = svc.list_annotations()
        types = {a.annotation_type for a in annotations}
        assert AnnotationType.SDTM_MAPPING in types
        assert AnnotationType.ADAM_MAPPING in types
        assert AnnotationType.COMPLETION_INSTRUCTION in types
        assert AnnotationType.REGULATORY_NOTE in types


# =====================================================================
# CRF VERSION CRUD
# =====================================================================


class TestCRFVersionCRUD:
    """Test CRF version create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_crf_versions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/crf-versions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_crf_versions_filter_trial_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/crf-versions", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_crf_versions_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/crf-versions", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_crf_versions_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/crf-versions", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_crf_versions_filter_status_deployed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/crf-versions", params={"crf_status": "deployed"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["crf_status"] == "deployed"

    @pytest.mark.anyio
    async def test_list_crf_versions_filter_status_draft(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/crf-versions", params={"crf_status": "draft"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["crf_status"] == "draft"

    @pytest.mark.anyio
    async def test_list_crf_versions_empty_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/crf-versions", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_crf_version(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/crf-versions/CRF-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CRF-001"
        assert data["crf_name"] == "Demographics"
        assert data["crf_status"] == "deployed"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_crf_version_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/crf-versions/CRF-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_crf_version(self, client: AsyncClient):
        payload = _make_crf_version_create()
        resp = await client.post(f"{API_PREFIX}/crf-versions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["crf_name"] == "Test CRF"
        assert data["crf_status"] == "draft"
        assert data["total_fields"] == 0
        assert data["id"].startswith("CRF-")
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_crf_version_appears_in_list(self, client: AsyncClient):
        payload = _make_crf_version_create(crf_name="Unique CRF")
        resp = await client.post(f"{API_PREFIX}/crf-versions", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/crf-versions")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert data["total"] == 13
        ids = {item["id"] for item in data["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_crf_version_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/crf-versions/CRF-004",
            json={"crf_status": "approved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["crf_status"] == "approved"

    @pytest.mark.anyio
    async def test_update_crf_version_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/crf-versions/CRF-001",
            json={"notes": "Updated notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated notes"

    @pytest.mark.anyio
    async def test_update_crf_version_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/crf-versions/CRF-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_crf_version(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/crf-versions/CRF-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/crf-versions/CRF-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_crf_version_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/crf-versions/CRF-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/crf-versions")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_crf_version_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/crf-versions/CRF-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CRF FIELD CRUD
# =====================================================================


class TestCRFFieldCRUD:
    """Test CRF field create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_crf_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/crf-fields")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_crf_fields_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/crf-fields", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_crf_fields_filter_version(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/crf-fields", params={"crf_version_id": "CRF-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["crf_version_id"] == "CRF-001"

    @pytest.mark.anyio
    async def test_list_crf_fields_filter_type_numeric(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/crf-fields", params={"field_type": "numeric"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["field_type"] == "numeric"

    @pytest.mark.anyio
    async def test_list_crf_fields_filter_type_dropdown(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/crf-fields", params={"field_type": "dropdown"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["field_type"] == "dropdown"

    @pytest.mark.anyio
    async def test_list_crf_fields_empty_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/crf-fields", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_crf_field(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/crf-fields/FLD-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "FLD-001"
        assert data["field_name"] == "SUBJID"
        assert data["field_type"] == "text"
        assert data["is_required"] is True

    @pytest.mark.anyio
    async def test_get_crf_field_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/crf-fields/FLD-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_crf_field(self, client: AsyncClient):
        payload = _make_crf_field_create()
        resp = await client.post(f"{API_PREFIX}/crf-fields", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["field_name"] == "TEST_FIELD"
        assert data["field_type"] == "text"
        assert data["is_key_field"] is False
        assert data["id"].startswith("FLD-")

    @pytest.mark.anyio
    async def test_create_crf_field_appears_in_list(self, client: AsyncClient):
        payload = _make_crf_field_create(field_name="UNIQUE_FIELD")
        resp = await client.post(f"{API_PREFIX}/crf-fields", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/crf-fields")
        assert list_resp.json()["total"] == 13
        ids = {item["id"] for item in list_resp.json()["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_crf_field_key_field(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/crf-fields/FLD-002",
            json={"is_key_field": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_key_field"] is True

    @pytest.mark.anyio
    async def test_update_crf_field_sdtm_mapping(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/crf-fields/FLD-001",
            json={"sdtm_domain": "DM", "sdtm_variable": "SUBJID"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sdtm_domain"] == "DM"
        assert data["sdtm_variable"] == "SUBJID"

    @pytest.mark.anyio
    async def test_update_crf_field_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/crf-fields/FLD-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_crf_field(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/crf-fields/FLD-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/crf-fields/FLD-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_crf_field_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/crf-fields/FLD-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/crf-fields")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_crf_field_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/crf-fields/FLD-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# EDIT CHECK RULE CRUD
# =====================================================================


class TestEditCheckRuleCRUD:
    """Test edit check rule create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_edit_check_rules(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/edit-check-rules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_edit_check_rules_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/edit-check-rules", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_edit_check_rules_filter_version(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/edit-check-rules", params={"crf_version_id": "CRF-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["crf_version_id"] == "CRF-001"

    @pytest.mark.anyio
    async def test_list_edit_check_rules_filter_severity_error(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/edit-check-rules", params={"edit_check_severity": "error"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["edit_check_severity"] == "error"

    @pytest.mark.anyio
    async def test_list_edit_check_rules_filter_severity_hard_stop(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/edit-check-rules", params={"edit_check_severity": "hard_stop"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["edit_check_severity"] == "hard_stop"

    @pytest.mark.anyio
    async def test_list_edit_check_rules_filter_active_true(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/edit-check-rules", params={"is_active": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["is_active"] is True

    @pytest.mark.anyio
    async def test_list_edit_check_rules_filter_active_false(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/edit-check-rules", params={"is_active": False}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["is_active"] is False

    @pytest.mark.anyio
    async def test_list_edit_check_rules_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/edit-check-rules", params={"trial_id": "nonexistent"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_edit_check_rule(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/edit-check-rules/ECR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ECR-001"
        assert data["rule_name"] == "DM_SUBJID_REQUIRED"
        assert data["edit_check_severity"] == "hard_stop"
        assert data["is_active"] is True

    @pytest.mark.anyio
    async def test_get_edit_check_rule_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/edit-check-rules/ECR-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_edit_check_rule(self, client: AsyncClient):
        payload = _make_edit_check_rule_create()
        resp = await client.post(f"{API_PREFIX}/edit-check-rules", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["rule_name"] == "TEST_RULE"
        assert data["edit_check_severity"] == "warning"
        assert data["is_active"] is True
        assert data["id"].startswith("ECR-")

    @pytest.mark.anyio
    async def test_create_edit_check_rule_appears_in_list(self, client: AsyncClient):
        payload = _make_edit_check_rule_create(rule_name="UNIQUE_RULE")
        resp = await client.post(f"{API_PREFIX}/edit-check-rules", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/edit-check-rules")
        assert list_resp.json()["total"] == 13
        ids = {item["id"] for item in list_resp.json()["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_edit_check_rule_active(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/edit-check-rules/ECR-008",
            json={"is_active": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_active"] is True

    @pytest.mark.anyio
    async def test_update_edit_check_rule_error_message(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/edit-check-rules/ECR-001",
            json={"error_message": "Updated error message"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["error_message"] == "Updated error message"

    @pytest.mark.anyio
    async def test_update_edit_check_rule_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/edit-check-rules/ECR-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_edit_check_rule(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/edit-check-rules/ECR-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/edit-check-rules/ECR-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_edit_check_rule_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/edit-check-rules/ECR-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/edit-check-rules")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_edit_check_rule_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/edit-check-rules/ECR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CRF DEPLOYMENT CRUD
# =====================================================================


class TestCRFDeploymentCRUD:
    """Test CRF deployment create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_deployments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deployments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_deployments_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deployments", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_deployments_filter_status_completed(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/deployments", params={"deployment_status": "completed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["deployment_status"] == "completed"

    @pytest.mark.anyio
    async def test_list_deployments_filter_status_pending(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/deployments", params={"deployment_status": "pending"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["deployment_status"] == "pending"

    @pytest.mark.anyio
    async def test_list_deployments_filter_version(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/deployments", params={"crf_version_id": "CRF-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["crf_version_id"] == "CRF-001"

    @pytest.mark.anyio
    async def test_list_deployments_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/deployments", params={"trial_id": "nonexistent"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_deployment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deployments/DEP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DEP-001"
        assert data["deployment_status"] == "completed"
        assert data["target_environment"] == "Production"

    @pytest.mark.anyio
    async def test_get_deployment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deployments/DEP-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_deployment(self, client: AsyncClient):
        payload = _make_deployment_create()
        resp = await client.post(f"{API_PREFIX}/deployments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["target_environment"] == "UAT"
        assert data["deployment_status"] == "pending"
        assert data["sites_affected"] == 5
        assert data["id"].startswith("DEP-")

    @pytest.mark.anyio
    async def test_create_deployment_appears_in_list(self, client: AsyncClient):
        payload = _make_deployment_create()
        resp = await client.post(f"{API_PREFIX}/deployments", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/deployments")
        assert list_resp.json()["total"] == 13
        ids = {item["id"] for item in list_resp.json()["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_deployment_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/deployments/DEP-007",
            json={"deployment_status": "in_progress"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deployment_status"] == "in_progress"

    @pytest.mark.anyio
    async def test_update_deployment_validation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/deployments/DEP-007",
            json={"validation_passed": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["validation_passed"] is True

    @pytest.mark.anyio
    async def test_update_deployment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/deployments/DEP-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_deployment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/deployments/DEP-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/deployments/DEP-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_deployment_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/deployments/DEP-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/deployments")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_deployment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/deployments/DEP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CRF ANNOTATION CRUD
# =====================================================================


class TestCRFAnnotationCRUD:
    """Test CRF annotation create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_annotations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/annotations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_annotations_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/annotations", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_annotations_filter_version(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/annotations", params={"crf_version_id": "CRF-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["crf_version_id"] == "CRF-001"

    @pytest.mark.anyio
    async def test_list_annotations_filter_type_sdtm(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/annotations", params={"annotation_type": "sdtm_mapping"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["annotation_type"] == "sdtm_mapping"

    @pytest.mark.anyio
    async def test_list_annotations_filter_type_adam(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/annotations", params={"annotation_type": "adam_mapping"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["annotation_type"] == "adam_mapping"

    @pytest.mark.anyio
    async def test_list_annotations_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/annotations", params={"trial_id": "nonexistent"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_annotation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/annotations/ANN-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ANN-001"
        assert data["annotation_type"] == "sdtm_mapping"
        assert data["reviewed"] is True

    @pytest.mark.anyio
    async def test_get_annotation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/annotations/ANN-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_annotation(self, client: AsyncClient):
        payload = _make_annotation_create()
        resp = await client.post(f"{API_PREFIX}/annotations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["annotation_type"] == "sdtm_mapping"
        assert data["reviewed"] is False
        assert data["id"].startswith("ANN-")

    @pytest.mark.anyio
    async def test_create_annotation_appears_in_list(self, client: AsyncClient):
        payload = _make_annotation_create(annotation_text="Unique annotation")
        resp = await client.post(f"{API_PREFIX}/annotations", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/annotations")
        assert list_resp.json()["total"] == 13
        ids = {item["id"] for item in list_resp.json()["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_annotation_reviewed(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/annotations/ANN-006",
            json={"reviewed": True, "reviewed_by": "Test Reviewer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reviewed"] is True
        assert data["reviewed_by"] == "Test Reviewer"

    @pytest.mark.anyio
    async def test_update_annotation_sdtm_dataset(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/annotations/ANN-001",
            json={"sdtm_dataset": "DM", "sdtm_variable": "SUBJID"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sdtm_dataset"] == "DM"
        assert data["sdtm_variable"] == "SUBJID"

    @pytest.mark.anyio
    async def test_update_annotation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/annotations/ANN-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_annotation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/annotations/ANN-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/annotations/ANN-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_annotation_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/annotations/ANN-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/annotations")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_annotation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/annotations/ANN-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test CRF management metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_crf_versions"] == 12
        assert data["total_fields"] == 12
        assert data["total_edit_checks"] == 12
        assert data["total_deployments"] == 12
        assert data["total_annotations"] == 12

    @pytest.mark.anyio
    async def test_metrics_versions_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        versions_by_status = data["versions_by_status"]
        assert "deployed" in versions_by_status
        total_by_status = sum(versions_by_status.values())
        assert total_by_status == 12

    @pytest.mark.anyio
    async def test_metrics_fields_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        fields_by_type = data["fields_by_type"]
        assert "text" in fields_by_type or "numeric" in fields_by_type
        total_by_type = sum(fields_by_type.values())
        assert total_by_type == 12

    @pytest.mark.anyio
    async def test_metrics_required_field_pct(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["required_field_pct"] > 0
        assert data["required_field_pct"] <= 100

    @pytest.mark.anyio
    async def test_metrics_edit_checks_by_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        edit_checks_by_severity = data["edit_checks_by_severity"]
        total_by_severity = sum(edit_checks_by_severity.values())
        assert total_by_severity == 12

    @pytest.mark.anyio
    async def test_metrics_active_edit_check_pct(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["active_edit_check_pct"] > 0
        assert data["active_edit_check_pct"] <= 100

    @pytest.mark.anyio
    async def test_metrics_deployments_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        deployments_by_status = data["deployments_by_status"]
        assert "completed" in deployments_by_status
        total_by_status = sum(deployments_by_status.values())
        assert total_by_status == 12

    @pytest.mark.anyio
    async def test_metrics_annotations_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        annotations_by_type = data["annotations_by_type"]
        assert "sdtm_mapping" in annotations_by_type
        total_by_type = sum(annotations_by_type.values())
        assert total_by_type == 12

    @pytest.mark.anyio
    async def test_metrics_annotation_review_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["annotation_review_rate"] > 0
        assert data["annotation_review_rate"] <= 100

    def test_service_metrics_after_create(self, svc: CRFManagementService):
        """Metrics should update after creating a new CRF version."""
        from app.schemas.crf_management import CRFVersionCreate

        initial_metrics = svc.get_metrics()
        svc.create_crf_version(
            CRFVersionCreate(
                trial_id=EYLEA_TRIAL,
                crf_name="New CRF",
                version_number="1.0",
                authored_by="Test User",
            )
        )
        updated_metrics = svc.get_metrics()
        assert updated_metrics.total_crf_versions == initial_metrics.total_crf_versions + 1

    def test_service_metrics_after_delete(self, svc: CRFManagementService):
        """Metrics should update after deleting a CRF version."""
        initial_metrics = svc.get_metrics()
        svc.delete_crf_version("CRF-001")
        updated_metrics = svc.get_metrics()
        assert updated_metrics.total_crf_versions == initial_metrics.total_crf_versions - 1


# =====================================================================
# EDGE CASES
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_get_nonexistent_version(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/crf-versions/DOES-NOT-EXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_nonexistent_field(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/crf-fields/DOES-NOT-EXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_nonexistent_rule(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/edit-check-rules/DOES-NOT-EXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_nonexistent_deployment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deployments/DOES-NOT-EXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_nonexistent_annotation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/annotations/DOES-NOT-EXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_nonexistent_version(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/crf-versions/DOES-NOT-EXIST",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_nonexistent_field(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/crf-fields/DOES-NOT-EXIST",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_nonexistent_rule(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/edit-check-rules/DOES-NOT-EXIST",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_nonexistent_deployment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/deployments/DOES-NOT-EXIST",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_nonexistent_annotation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/annotations/DOES-NOT-EXIST",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_nonexistent_version(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/crf-versions/DOES-NOT-EXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_nonexistent_field(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/crf-fields/DOES-NOT-EXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_nonexistent_rule(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/edit-check-rules/DOES-NOT-EXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_nonexistent_deployment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/deployments/DOES-NOT-EXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_nonexistent_annotation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/annotations/DOES-NOT-EXIST")
        assert resp.status_code == 404


# =====================================================================
# SINGLETON PATTERN
# =====================================================================


class TestSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_crf_management_service()
        svc2 = get_crf_management_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_crf_management_service()
        svc2 = reset_crf_management_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_crf_management_service()
        svc.delete_crf_version("CRF-001")
        assert svc.get_crf_version("CRF-001") is None
        svc2 = reset_crf_management_service()
        assert svc2.get_crf_version("CRF-001") is not None

    def test_reset_reseeds_fields(self):
        svc = get_crf_management_service()
        svc.delete_crf_field("FLD-001")
        assert svc.get_crf_field("FLD-001") is None
        svc2 = reset_crf_management_service()
        assert svc2.get_crf_field("FLD-001") is not None

    def test_reset_reseeds_edit_checks(self):
        svc = get_crf_management_service()
        svc.delete_edit_check_rule("ECR-001")
        assert svc.get_edit_check_rule("ECR-001") is None
        svc2 = reset_crf_management_service()
        assert svc2.get_edit_check_rule("ECR-001") is not None

    def test_reset_reseeds_deployments(self):
        svc = get_crf_management_service()
        svc.delete_deployment("DEP-001")
        assert svc.get_deployment("DEP-001") is None
        svc2 = reset_crf_management_service()
        assert svc2.get_deployment("DEP-001") is not None

    def test_reset_reseeds_annotations(self):
        svc = get_crf_management_service()
        svc.delete_annotation("ANN-001")
        assert svc.get_annotation("ANN-001") is None
        svc2 = reset_crf_management_service()
        assert svc2.get_annotation("ANN-001") is not None

    def test_get_after_reset_returns_new_instance(self):
        svc1 = get_crf_management_service()
        reset_crf_management_service()
        svc2 = get_crf_management_service()
        assert svc1 is not svc2


# =====================================================================
# SERVICE-LEVEL CRUD
# =====================================================================


class TestServiceLevelCRUD:
    """Test service-level CRUD operations directly."""

    # --- CRF Versions ---

    def test_service_list_versions_filter_status(self, svc: CRFManagementService):
        versions = svc.list_crf_versions(crf_status=CRFStatus.DEPLOYED)
        assert len(versions) > 0
        for v in versions:
            assert v.crf_status == CRFStatus.DEPLOYED

    def test_service_list_versions_filter_trial(self, svc: CRFManagementService):
        versions = svc.list_crf_versions(trial_id=EYLEA_TRIAL)
        assert len(versions) > 0
        for v in versions:
            assert v.trial_id == EYLEA_TRIAL

    def test_service_get_version_none(self, svc: CRFManagementService):
        result = svc.get_crf_version("CRF-NONEXISTENT")
        assert result is None

    def test_service_delete_version_nonexistent(self, svc: CRFManagementService):
        result = svc.delete_crf_version("CRF-NONEXISTENT")
        assert result is False

    # --- CRF Fields ---

    def test_service_list_fields_filter_type(self, svc: CRFManagementService):
        fields = svc.list_crf_fields(field_type=FieldType.NUMERIC)
        assert len(fields) > 0
        for f in fields:
            assert f.field_type == FieldType.NUMERIC

    def test_service_list_fields_filter_version(self, svc: CRFManagementService):
        fields = svc.list_crf_fields(crf_version_id="CRF-001")
        assert len(fields) > 0
        for f in fields:
            assert f.crf_version_id == "CRF-001"

    def test_service_get_field_none(self, svc: CRFManagementService):
        result = svc.get_crf_field("FLD-NONEXISTENT")
        assert result is None

    def test_service_delete_field_nonexistent(self, svc: CRFManagementService):
        result = svc.delete_crf_field("FLD-NONEXISTENT")
        assert result is False

    # --- Edit Check Rules ---

    def test_service_list_rules_filter_severity(self, svc: CRFManagementService):
        rules = svc.list_edit_check_rules(edit_check_severity=EditCheckSeverity.HARD_STOP)
        assert len(rules) > 0
        for r in rules:
            assert r.edit_check_severity == EditCheckSeverity.HARD_STOP

    def test_service_list_rules_filter_active(self, svc: CRFManagementService):
        active = svc.list_edit_check_rules(is_active=True)
        inactive = svc.list_edit_check_rules(is_active=False)
        assert len(active) + len(inactive) == 12
        assert len(inactive) > 0  # ECR-008 is inactive

    def test_service_get_rule_none(self, svc: CRFManagementService):
        result = svc.get_edit_check_rule("ECR-NONEXISTENT")
        assert result is None

    def test_service_delete_rule_nonexistent(self, svc: CRFManagementService):
        result = svc.delete_edit_check_rule("ECR-NONEXISTENT")
        assert result is False

    # --- Deployments ---

    def test_service_list_deployments_filter_status(self, svc: CRFManagementService):
        deployments = svc.list_deployments(deployment_status=DeploymentStatus.COMPLETED)
        assert len(deployments) > 0
        for d in deployments:
            assert d.deployment_status == DeploymentStatus.COMPLETED

    def test_service_list_deployments_filter_version(self, svc: CRFManagementService):
        deployments = svc.list_deployments(crf_version_id="CRF-001")
        assert len(deployments) > 0
        for d in deployments:
            assert d.crf_version_id == "CRF-001"

    def test_service_get_deployment_none(self, svc: CRFManagementService):
        result = svc.get_deployment("DEP-NONEXISTENT")
        assert result is None

    def test_service_delete_deployment_nonexistent(self, svc: CRFManagementService):
        result = svc.delete_deployment("DEP-NONEXISTENT")
        assert result is False

    # --- Annotations ---

    def test_service_list_annotations_filter_type(self, svc: CRFManagementService):
        annotations = svc.list_annotations(annotation_type=AnnotationType.SDTM_MAPPING)
        assert len(annotations) > 0
        for a in annotations:
            assert a.annotation_type == AnnotationType.SDTM_MAPPING

    def test_service_list_annotations_filter_version(self, svc: CRFManagementService):
        annotations = svc.list_annotations(crf_version_id="CRF-001")
        assert len(annotations) > 0
        for a in annotations:
            assert a.crf_version_id == "CRF-001"

    def test_service_get_annotation_none(self, svc: CRFManagementService):
        result = svc.get_annotation("ANN-NONEXISTENT")
        assert result is None

    def test_service_delete_annotation_nonexistent(self, svc: CRFManagementService):
        result = svc.delete_annotation("ANN-NONEXISTENT")
        assert result is False
