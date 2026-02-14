"""Tests for CRF Management (CRF-MGT).

Covers:
- Seed data verification (CRF versions, fields, edit check rules,
  deployments, annotations)
- CRF version CRUD (create, read, update, delete, list, filter by trial/status)
- CRF field CRUD (create, read, update, delete, list, filter by trial/version/type)
- Edit check rule CRUD (create, read, update, delete, list, filter by trial/version/severity/active)
- CRF deployment CRUD (create, read, update, delete, list, filter by trial/status/version)
- CRF annotation CRUD (create, read, update, delete, list, filter by trial/version/type)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
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


def _make_version_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "crf_name": "Test CRF Form",
        "version_number": "1.0",
        "authored_by": "Test Author",
        "total_pages": 2,
    }
    defaults.update(overrides)
    return defaults


def _make_field_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "crf_version_id": "CRF-001",
        "field_name": "test_field",
        "field_label": "Test Field Label",
        "field_type": "text",
        "page_number": 1,
        "display_order": 1,
        "is_required": False,
    }
    defaults.update(overrides)
    return defaults


def _make_edit_check_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "crf_version_id": "CRF-001",
        "rule_name": "TEST_RULE",
        "rule_expression": "test_field IS NOT NULL",
        "target_field_id": "FLD-001",
        "error_message": "Test field is required.",
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
        "deployed_by": "Test Admin",
        "sites_affected": 5,
    }
    defaults.update(overrides)
    return defaults


def _make_annotation_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "crf_version_id": "CRF-001",
        "annotation_type": "sdtm_mapping",
        "annotation_text": "Maps to DM.TEST - Test mapping.",
        "annotated_by": "Test Annotator",
        "field_id": None,
    }
    defaults.update(overrides)
    return defaults


# ===================================================================
# SEED DATA VERIFICATION
# ===================================================================


class TestSeedData:
    """Verify all 5 entity types are seeded with 12 records each."""

    @pytest.mark.anyio
    async def test_seed_crf_versions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_seed_crf_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/fields")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_edit_check_rules(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/edit-check-rules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_crf_deployments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deployments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_crf_annotations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/annotations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12


# ===================================================================
# CRF VERSIONS CRUD
# ===================================================================


class TestCRFVersionCRUD:
    @pytest.mark.anyio
    async def test_list_crf_versions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/versions")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_crf_version(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/versions/CRF-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CRF-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_crf_version_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/versions/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_crf_version(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/versions", json=_make_version_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("CRF-")
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["crf_status"] == "draft"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/versions")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/versions", json=_make_version_create())
        resp2 = await client.get(f"{API_PREFIX}/versions")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_crf_version(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/versions/CRF-001",
            json={"crf_status": "approved", "notes": "Updated note"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["crf_status"] == "approved"
        assert data["notes"] == "Updated note"

    @pytest.mark.anyio
    async def test_update_crf_version_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/versions/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_crf_version(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/versions/CRF-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/versions/CRF-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_crf_version_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/versions/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/versions", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_crf_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/versions", params={"crf_status": "deployed"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["crf_status"] == "deployed"


# ===================================================================
# CRF FIELDS CRUD
# ===================================================================


class TestCRFFieldCRUD:
    @pytest.mark.anyio
    async def test_list_crf_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/fields")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_crf_field(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/fields/FLD-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "FLD-001"

    @pytest.mark.anyio
    async def test_get_crf_field_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/fields/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_crf_field(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/fields", json=_make_field_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("FLD-")
        assert data["field_type"] == "text"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/fields")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/fields", json=_make_field_create())
        resp2 = await client.get(f"{API_PREFIX}/fields")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_crf_field(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/fields/FLD-001",
            json={"is_key_field": False, "notes": "Updated field note"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_key_field"] is False
        assert data["notes"] == "Updated field note"

    @pytest.mark.anyio
    async def test_update_crf_field_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/fields/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_crf_field(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/fields/FLD-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_crf_field_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/fields/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_field_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/fields", params={"field_type": "numeric"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["field_type"] == "numeric"

    @pytest.mark.anyio
    async def test_filter_by_crf_version_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/fields", params={"crf_version_id": "CRF-001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["crf_version_id"] == "CRF-001"


# ===================================================================
# EDIT CHECK RULES CRUD
# ===================================================================


class TestEditCheckRuleCRUD:
    @pytest.mark.anyio
    async def test_list_edit_check_rules(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/edit-check-rules")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_edit_check_rule(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/edit-check-rules/ECR-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "ECR-001"

    @pytest.mark.anyio
    async def test_get_edit_check_rule_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/edit-check-rules/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_edit_check_rule(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/edit-check-rules", json=_make_edit_check_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("ECR-")
        assert data["rule_name"] == "TEST_RULE"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/edit-check-rules")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/edit-check-rules", json=_make_edit_check_create())
        resp2 = await client.get(f"{API_PREFIX}/edit-check-rules")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_edit_check_rule(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/edit-check-rules/ECR-001",
            json={"is_active": False, "notes": "Disabled for testing"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_active"] is False
        assert data["notes"] == "Disabled for testing"

    @pytest.mark.anyio
    async def test_update_edit_check_rule_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/edit-check-rules/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_edit_check_rule(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/edit-check-rules/ECR-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_edit_check_rule_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/edit-check-rules/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_severity(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/edit-check-rules", params={"edit_check_severity": "hard_stop"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["edit_check_severity"] == "hard_stop"

    @pytest.mark.anyio
    async def test_filter_by_is_active(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/edit-check-rules", params={"is_active": True}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["is_active"] is True


# ===================================================================
# CRF DEPLOYMENTS CRUD
# ===================================================================


class TestCRFDeploymentCRUD:
    @pytest.mark.anyio
    async def test_list_crf_deployments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deployments")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_crf_deployment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deployments/DEP-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "DEP-001"

    @pytest.mark.anyio
    async def test_get_crf_deployment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deployments/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_crf_deployment(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/deployments", json=_make_deployment_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("DEP-")
        assert data["target_environment"] == "UAT"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/deployments")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/deployments", json=_make_deployment_create())
        resp2 = await client.get(f"{API_PREFIX}/deployments")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_crf_deployment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/deployments/DEP-001",
            json={"deployment_status": "completed", "notes": "Deployment verified"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deployment_status"] == "completed"
        assert data["notes"] == "Deployment verified"

    @pytest.mark.anyio
    async def test_update_crf_deployment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/deployments/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_crf_deployment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/deployments/DEP-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_crf_deployment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/deployments/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_deployment_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/deployments", params={"deployment_status": "completed"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["deployment_status"] == "completed"

    @pytest.mark.anyio
    async def test_filter_by_crf_version_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/deployments", params={"crf_version_id": "CRF-001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["crf_version_id"] == "CRF-001"


# ===================================================================
# CRF ANNOTATIONS CRUD
# ===================================================================


class TestCRFAnnotationCRUD:
    @pytest.mark.anyio
    async def test_list_crf_annotations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/annotations")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_crf_annotation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/annotations/ANN-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "ANN-001"

    @pytest.mark.anyio
    async def test_get_crf_annotation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/annotations/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_crf_annotation(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/annotations", json=_make_annotation_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("ANN-")
        assert data["annotation_type"] == "sdtm_mapping"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/annotations")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/annotations", json=_make_annotation_create())
        resp2 = await client.get(f"{API_PREFIX}/annotations")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_crf_annotation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/annotations/ANN-001",
            json={"reviewed": True, "reviewed_by": "Test Reviewer", "notes": "Verified"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reviewed"] is True
        assert data["reviewed_by"] == "Test Reviewer"
        assert data["notes"] == "Verified"

    @pytest.mark.anyio
    async def test_update_crf_annotation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/annotations/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_crf_annotation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/annotations/ANN-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/annotations/ANN-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_crf_annotation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/annotations/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_annotation_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/annotations", params={"annotation_type": "sdtm_mapping"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["annotation_type"] == "sdtm_mapping"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/annotations", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL


# ===================================================================
# METRICS
# ===================================================================


class TestMetrics:
    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_crf_versions" in data
        assert "total_fields" in data
        assert "total_edit_checks" in data
        assert "total_deployments" in data
        assert "total_annotations" in data
        assert "required_field_pct" in data
        assert "active_edit_check_pct" in data
        assert "annotation_review_rate" in data

    @pytest.mark.anyio
    async def test_metrics_total_versions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_crf_versions"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_fields"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_edit_checks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_edit_checks"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_deployments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_deployments"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_annotations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_annotations"] == 12

    @pytest.mark.anyio
    async def test_metrics_has_breakdowns(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert isinstance(data["versions_by_status"], dict)
        assert isinstance(data["fields_by_type"], dict)
        assert isinstance(data["edit_checks_by_severity"], dict)
        assert isinstance(data["deployments_by_status"], dict)
        assert isinstance(data["annotations_by_type"], dict)

    @pytest.mark.anyio
    async def test_metrics_with_trial_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        # EYLEA has 4 versions seeded
        assert data["total_crf_versions"] == 4

    def test_metrics_service_level(self, svc: CRFManagementService):
        metrics = svc.get_metrics()
        assert metrics.total_crf_versions == 12
        assert metrics.total_fields == 12
        assert metrics.total_edit_checks == 12
        assert metrics.total_deployments == 12
        assert metrics.total_annotations == 12


# ===================================================================
# EDGE CASES & UPDATE PRESERVATION
# ===================================================================


class TestEdgeCases:
    @pytest.mark.anyio
    async def test_update_version_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/versions/CRF-001")
        original = resp.json()
        original_name = original["crf_name"]

        resp2 = await client.put(
            f"{API_PREFIX}/versions/CRF-001",
            json={"notes": "Partial update"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["crf_name"] == original_name
        assert updated["notes"] == "Partial update"

    @pytest.mark.anyio
    async def test_update_field_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/fields/FLD-001")
        original = resp.json()
        original_type = original["field_type"]

        resp2 = await client.put(
            f"{API_PREFIX}/fields/FLD-001",
            json={"notes": "Updated field note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["field_type"] == original_type

    @pytest.mark.anyio
    async def test_update_edit_check_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/edit-check-rules/ECR-001")
        original = resp.json()
        original_name = original["rule_name"]

        resp2 = await client.put(
            f"{API_PREFIX}/edit-check-rules/ECR-001",
            json={"notes": "Updated rule note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["rule_name"] == original_name

    @pytest.mark.anyio
    async def test_update_deployment_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deployments/DEP-001")
        original = resp.json()
        original_env = original["target_environment"]

        resp2 = await client.put(
            f"{API_PREFIX}/deployments/DEP-001",
            json={"notes": "Updated deployment note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["target_environment"] == original_env

    @pytest.mark.anyio
    async def test_update_annotation_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/annotations/ANN-001")
        original = resp.json()
        original_text = original["annotation_text"]

        resp2 = await client.put(
            f"{API_PREFIX}/annotations/ANN-001",
            json={"notes": "Updated annotation note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["annotation_text"] == original_text


# ===================================================================
# SINGLETON PATTERN
# ===================================================================


class TestSingleton:
    def test_get_returns_same_instance(self):
        svc1 = get_crf_management_service()
        svc2 = get_crf_management_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        svc1 = get_crf_management_service()
        svc2 = reset_crf_management_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_crf_management_service()
        svc.delete_crf_version("CRF-001")
        assert svc.get_crf_version("CRF-001") is None
        svc2 = reset_crf_management_service()
        assert svc2.get_crf_version("CRF-001") is not None


# ===================================================================
# SERVICE-LEVEL CRUD
# ===================================================================


class TestServiceLevelCRUD:
    def test_list_crf_versions_service(self, svc: CRFManagementService):
        items = svc.list_crf_versions()
        assert len(items) == 12

    def test_get_crf_version_service(self, svc: CRFManagementService):
        record = svc.get_crf_version("CRF-001")
        assert record is not None
        assert record.id == "CRF-001"

    def test_list_crf_fields_service(self, svc: CRFManagementService):
        items = svc.list_crf_fields()
        assert len(items) == 12

    def test_get_crf_field_service(self, svc: CRFManagementService):
        record = svc.get_crf_field("FLD-001")
        assert record is not None
        assert record.id == "FLD-001"

    def test_list_edit_check_rules_service(self, svc: CRFManagementService):
        items = svc.list_edit_check_rules()
        assert len(items) == 12

    def test_get_edit_check_rule_service(self, svc: CRFManagementService):
        record = svc.get_edit_check_rule("ECR-001")
        assert record is not None
        assert record.id == "ECR-001"

    def test_list_crf_deployments_service(self, svc: CRFManagementService):
        items = svc.list_crf_deployments()
        assert len(items) == 12

    def test_get_crf_deployment_service(self, svc: CRFManagementService):
        record = svc.get_crf_deployment("DEP-001")
        assert record is not None
        assert record.id == "DEP-001"

    def test_list_crf_annotations_service(self, svc: CRFManagementService):
        items = svc.list_crf_annotations()
        assert len(items) == 12

    def test_get_crf_annotation_service(self, svc: CRFManagementService):
        record = svc.get_crf_annotation("ANN-001")
        assert record is not None
        assert record.id == "ANN-001"

    def test_delete_crf_version_service(self, svc: CRFManagementService):
        assert svc.delete_crf_version("CRF-001") is True
        assert svc.get_crf_version("CRF-001") is None

    def test_delete_nonexistent_returns_false(self, svc: CRFManagementService):
        assert svc.delete_crf_version("NONEXISTENT") is False

    def test_filter_versions_by_trial(self, svc: CRFManagementService):
        items = svc.list_crf_versions(trial_id=EYLEA_TRIAL)
        for item in items:
            assert item.trial_id == EYLEA_TRIAL

    def test_filter_fields_by_type(self, svc: CRFManagementService):
        items = svc.list_crf_fields(field_type=FieldType.NUMERIC)
        for item in items:
            assert item.field_type == FieldType.NUMERIC

    def test_filter_edit_checks_by_severity(self, svc: CRFManagementService):
        items = svc.list_edit_check_rules(edit_check_severity=EditCheckSeverity.HARD_STOP)
        for item in items:
            assert item.edit_check_severity == EditCheckSeverity.HARD_STOP

    def test_filter_deployments_by_status(self, svc: CRFManagementService):
        items = svc.list_crf_deployments(deployment_status=DeploymentStatus.COMPLETED)
        for item in items:
            assert item.deployment_status == DeploymentStatus.COMPLETED

    def test_filter_annotations_by_type(self, svc: CRFManagementService):
        items = svc.list_crf_annotations(annotation_type=AnnotationType.SDTM_MAPPING)
        for item in items:
            assert item.annotation_type == AnnotationType.SDTM_MAPPING


# ===================================================================
# BULK / MULTI-ENTITY
# ===================================================================


class TestBulkOperations:
    @pytest.mark.anyio
    async def test_create_multiple_crf_versions(self, client: AsyncClient):
        for i in range(3):
            resp = await client.post(
                f"{API_PREFIX}/versions",
                json=_make_version_create(crf_name=f"Bulk CRF {i}"),
            )
            assert resp.status_code == 201
        resp = await client.get(f"{API_PREFIX}/versions")
        assert resp.json()["total"] == 15  # 12 seed + 3 new

    @pytest.mark.anyio
    async def test_delete_multiple_annotations(self, client: AsyncClient):
        for ann_id in ["ANN-001", "ANN-002", "ANN-003"]:
            resp = await client.delete(f"{API_PREFIX}/annotations/{ann_id}")
            assert resp.status_code == 204
        resp = await client.get(f"{API_PREFIX}/annotations")
        assert resp.json()["total"] == 9  # 12 seed - 3 deleted


# ===================================================================
# RESPONSE STRUCTURE
# ===================================================================


class TestAPIResponseStructure:
    @pytest.mark.anyio
    async def test_version_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/versions/CRF-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "crf_name", "version_number",
                       "crf_status", "authored_by", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_field_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/fields/FLD-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "crf_version_id", "field_name",
                       "field_label", "field_type", "is_required", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_edit_check_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/edit-check-rules/ECR-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "crf_version_id", "rule_name",
                       "rule_expression", "edit_check_severity", "is_active", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_deployment_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deployments/DEP-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "crf_version_id", "deployment_status",
                       "target_environment", "deployed_by", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_annotation_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/annotations/ANN-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in ["id", "trial_id", "crf_version_id", "annotation_type",
                       "annotation_text", "annotated_by", "created_at"]:
            assert field in data

    @pytest.mark.anyio
    async def test_list_response_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
