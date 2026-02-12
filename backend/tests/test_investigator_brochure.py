"""Tests for Investigator Brochure Management (IB-MGMT).

Covers:
- Seed data verification (IB versions, safety updates, distributions, revisions, acknowledgments)
- IB version CRUD (create, read, update, delete, list, filter by trial/status)
- Safety update CRUD (create, read, update, delete, list, filter by trial/type)
- Distribution record CRUD (create, read, update, delete, list, filter by trial/method)
- Revision history CRUD (create, read, update, delete, list, filter by trial/scope)
- Acknowledgment record CRUD (create, read, update, delete, list, filter by trial/status)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.investigator_brochure import (
    AcknowledgmentStatus,
    DistributionMethod,
    IBStatus,
    RevisionScope,
    UpdateType,
)
from app.services.investigator_brochure_service import (
    InvestigatorBrochureService,
    get_investigator_brochure_service,
    reset_investigator_brochure_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/investigator-brochure"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_investigator_brochure_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> InvestigatorBrochureService:
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


def _make_ib_version_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "version_number": "4.0",
        "authored_by": "Dr. Test Author",
        "edition_number": 5,
        "page_count": 300,
    }
    defaults.update(overrides)
    return defaults


def _make_safety_update_create(**overrides) -> dict:
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "update_type": "safety_driven",
        "safety_signal": "Test safety signal for evaluation",
        "prepared_by": "Dr. Test Preparer",
        "new_risk_identified": False,
    }
    defaults.update(overrides)
    return defaults


def _make_distribution_record_create(**overrides) -> dict:
    defaults = {
        "trial_id": LIBTAYO_TRIAL,
        "ib_version_id": "IBV-009",
        "site_id": "SITE-999",
        "investigator_name": "Dr. Test Investigator",
        "distribution_method": "electronic",
        "distributed_by": "Test Distribution Team",
    }
    defaults.update(overrides)
    return defaults


def _make_revision_history_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "ib_version_id": "IBV-003",
        "section_number": "9.1",
        "section_title": "Test Section",
        "change_description": "Test change for evaluation purposes",
        "rationale": "Required for testing",
        "revision_scope": "minor",
        "revised_by": "Dr. Test Reviser",
        "pages_affected": 3,
    }
    defaults.update(overrides)
    return defaults


def _make_acknowledgment_record_create(**overrides) -> dict:
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "ib_version_id": "IBV-005",
        "investigator_name": "Dr. Test Acknowledger",
        "site_id": "SITE-999",
        "managed_by": "Test Management Team",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_ib_versions_count(self, svc: InvestigatorBrochureService):
        versions = svc.list_ib_versions()
        assert len(versions) == 12

    def test_seed_safety_updates_count(self, svc: InvestigatorBrochureService):
        updates = svc.list_safety_updates()
        assert len(updates) == 12

    def test_seed_distribution_records_count(self, svc: InvestigatorBrochureService):
        records = svc.list_distribution_records()
        assert len(records) == 12

    def test_seed_revision_histories_count(self, svc: InvestigatorBrochureService):
        revisions = svc.list_revision_histories()
        assert len(revisions) == 12

    def test_seed_acknowledgment_records_count(self, svc: InvestigatorBrochureService):
        records = svc.list_acknowledgment_records()
        assert len(records) == 12

    def test_seed_versions_cover_all_trials(self, svc: InvestigatorBrochureService):
        versions = svc.list_ib_versions()
        trial_ids = {v.trial_id for v in versions}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_versions_have_multiple_statuses(self, svc: InvestigatorBrochureService):
        versions = svc.list_ib_versions()
        statuses = {v.status for v in versions}
        assert IBStatus.DRAFT in statuses
        assert IBStatus.DISTRIBUTED in statuses
        assert IBStatus.SUPERSEDED in statuses

    def test_seed_safety_updates_have_multiple_types(self, svc: InvestigatorBrochureService):
        updates = svc.list_safety_updates()
        types = {u.update_type for u in updates}
        assert UpdateType.SAFETY_DRIVEN in types
        assert UpdateType.SCHEDULED in types
        assert UpdateType.NEW_DATA in types

    def test_seed_distributions_have_multiple_methods(self, svc: InvestigatorBrochureService):
        records = svc.list_distribution_records()
        methods = {r.distribution_method for r in records}
        assert DistributionMethod.ELECTRONIC in methods
        assert DistributionMethod.PORTAL in methods

    def test_seed_revisions_have_multiple_scopes(self, svc: InvestigatorBrochureService):
        revisions = svc.list_revision_histories()
        scopes = {r.revision_scope for r in revisions}
        assert RevisionScope.MAJOR in scopes
        assert RevisionScope.MINOR in scopes
        assert RevisionScope.SAFETY_ADDENDUM in scopes

    def test_seed_acknowledgments_have_multiple_statuses(self, svc: InvestigatorBrochureService):
        records = svc.list_acknowledgment_records()
        statuses = {r.status for r in records}
        assert AcknowledgmentStatus.ACKNOWLEDGED in statuses
        assert AcknowledgmentStatus.OVERDUE in statuses
        assert AcknowledgmentStatus.PENDING in statuses


# =====================================================================
# IB VERSION CRUD
# =====================================================================


class TestIBVersionCrud:
    """Test IB version CRUD operations."""

    @pytest.mark.anyio
    async def test_list_ib_versions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ib-versions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_ib_versions_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/ib-versions", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_ib_versions_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/ib-versions", params={"status": "distributed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "distributed"

    @pytest.mark.anyio
    async def test_get_ib_version(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ib-versions/IBV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "IBV-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["version_number"] == "1.0"

    @pytest.mark.anyio
    async def test_get_ib_version_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ib-versions/IBV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_ib_version(self, client: AsyncClient):
        payload = _make_ib_version_create()
        resp = await client.post(f"{API_PREFIX}/ib-versions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["version_number"] == "4.0"
        assert data["status"] == "draft"
        assert data["id"].startswith("IBV-")

    @pytest.mark.anyio
    async def test_update_ib_version(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/ib-versions/IBV-010",
            json={"status": "under_review", "notes": "Submitted for review"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "under_review"
        assert data["notes"] == "Submitted for review"

    @pytest.mark.anyio
    async def test_update_ib_version_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/ib-versions/IBV-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_ib_version(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/ib-versions/IBV-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/ib-versions/IBV-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_ib_version_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/ib-versions/IBV-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# SAFETY UPDATE CRUD
# =====================================================================


class TestSafetyUpdateCrud:
    """Test safety update CRUD operations."""

    @pytest.mark.anyio
    async def test_list_safety_updates(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/safety-updates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_safety_updates_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/safety-updates", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_safety_updates_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/safety-updates", params={"update_type": "safety_driven"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["update_type"] == "safety_driven"

    @pytest.mark.anyio
    async def test_get_safety_update(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/safety-updates/SU-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SU-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["update_type"] == "safety_driven"

    @pytest.mark.anyio
    async def test_get_safety_update_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/safety-updates/SU-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_safety_update(self, client: AsyncClient):
        payload = _make_safety_update_create()
        resp = await client.post(f"{API_PREFIX}/safety-updates", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["update_type"] == "safety_driven"
        assert data["id"].startswith("SU-")

    @pytest.mark.anyio
    async def test_update_safety_update(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/safety-updates/SU-009",
            json={"reviewed_by": "Dr. Review Expert", "regulatory_notified": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reviewed_by"] == "Dr. Review Expert"
        assert data["regulatory_notified"] is True

    @pytest.mark.anyio
    async def test_update_safety_update_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/safety-updates/SU-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_safety_update(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/safety-updates/SU-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/safety-updates/SU-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_safety_update_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/safety-updates/SU-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# DISTRIBUTION RECORD CRUD
# =====================================================================


class TestDistributionRecordCrud:
    """Test distribution record CRUD operations."""

    @pytest.mark.anyio
    async def test_list_distribution_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/distribution-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_distribution_records_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/distribution-records", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_distribution_records_filter_method(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/distribution-records", params={"distribution_method": "electronic"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["distribution_method"] == "electronic"

    @pytest.mark.anyio
    async def test_get_distribution_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/distribution-records/DR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DR-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_distribution_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/distribution-records/DR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_distribution_record(self, client: AsyncClient):
        payload = _make_distribution_record_create()
        resp = await client.post(f"{API_PREFIX}/distribution-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["distribution_method"] == "electronic"
        assert data["id"].startswith("DR-")

    @pytest.mark.anyio
    async def test_update_distribution_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/distribution-records/DR-006",
            json={"receipt_confirmed": True, "tracking_number": "UPD-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["receipt_confirmed"] is True
        assert data["tracking_number"] == "UPD-001"

    @pytest.mark.anyio
    async def test_update_distribution_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/distribution-records/DR-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_distribution_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/distribution-records/DR-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/distribution-records/DR-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_distribution_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/distribution-records/DR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# REVISION HISTORY CRUD
# =====================================================================


class TestRevisionHistoryCrud:
    """Test revision history CRUD operations."""

    @pytest.mark.anyio
    async def test_list_revision_histories(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/revision-histories")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_revision_histories_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/revision-histories", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_revision_histories_filter_scope(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/revision-histories", params={"revision_scope": "major"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["revision_scope"] == "major"

    @pytest.mark.anyio
    async def test_get_revision_history(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/revision-histories/RH-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RH-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_revision_history_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/revision-histories/RH-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_revision_history(self, client: AsyncClient):
        payload = _make_revision_history_create()
        resp = await client.post(f"{API_PREFIX}/revision-histories", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["revision_scope"] == "minor"
        assert data["id"].startswith("RH-")

    @pytest.mark.anyio
    async def test_update_revision_history(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/revision-histories/RH-012",
            json={"approved_by": "Dr. Approval Authority", "safety_driven": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approved_by"] == "Dr. Approval Authority"
        assert data["safety_driven"] is True

    @pytest.mark.anyio
    async def test_update_revision_history_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/revision-histories/RH-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_revision_history(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/revision-histories/RH-011")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/revision-histories/RH-011")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_revision_history_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/revision-histories/RH-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# ACKNOWLEDGMENT RECORD CRUD
# =====================================================================


class TestAcknowledgmentRecordCrud:
    """Test acknowledgment record CRUD operations."""

    @pytest.mark.anyio
    async def test_list_acknowledgment_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/acknowledgment-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_acknowledgment_records_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/acknowledgment-records", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_acknowledgment_records_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/acknowledgment-records", params={"status": "acknowledged"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "acknowledged"

    @pytest.mark.anyio
    async def test_get_acknowledgment_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/acknowledgment-records/ACK-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ACK-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_acknowledgment_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/acknowledgment-records/ACK-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_acknowledgment_record(self, client: AsyncClient):
        payload = _make_acknowledgment_record_create()
        resp = await client.post(f"{API_PREFIX}/acknowledgment-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["status"] == "pending"
        assert data["id"].startswith("ACK-")

    @pytest.mark.anyio
    async def test_update_acknowledgment_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/acknowledgment-records/ACK-011",
            json={"status": "acknowledged", "signature_on_file": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "acknowledged"
        assert data["signature_on_file"] is True

    @pytest.mark.anyio
    async def test_update_acknowledgment_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/acknowledgment-records/ACK-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_acknowledgment_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/acknowledgment-records/ACK-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/acknowledgment-records/ACK-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_acknowledgment_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/acknowledgment-records/ACK-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestInvestigatorBrochureMetrics:
    """Test investigator brochure metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_versions"] == 12
        assert data["total_safety_updates"] == 12
        assert data["total_distributions"] == 12
        assert data["total_revisions"] == 12
        assert data["total_acknowledgments"] == 12

    @pytest.mark.anyio
    async def test_metrics_versions_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["versions_by_status"]
        total = sum(by_status.values())
        assert total == data["total_versions"]

    @pytest.mark.anyio
    async def test_metrics_current_versions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["current_versions"] > 0
        assert data["current_versions"] <= data["total_versions"]

    @pytest.mark.anyio
    async def test_metrics_updates_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_type = data["updates_by_type"]
        total = sum(by_type.values())
        assert total == data["total_safety_updates"]

    @pytest.mark.anyio
    async def test_metrics_new_risks_identified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["new_risks_identified"] > 0
        assert data["new_risks_identified"] <= data["total_safety_updates"]

    @pytest.mark.anyio
    async def test_metrics_distributions_confirmed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["distributions_confirmed"] > 0
        assert data["distributions_confirmed"] <= data["total_distributions"]

    @pytest.mark.anyio
    async def test_metrics_revisions_by_scope(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_scope = data["revisions_by_scope"]
        total = sum(by_scope.values())
        assert total == data["total_revisions"]

    @pytest.mark.anyio
    async def test_metrics_acknowledgments_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["acknowledgments_by_status"]
        total = sum(by_status.values())
        assert total == data["total_acknowledgments"]

    @pytest.mark.anyio
    async def test_metrics_overdue_acknowledgments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["overdue_acknowledgments"] >= 1


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_investigator_brochure_service()
        svc2 = get_investigator_brochure_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_investigator_brochure_service()
        svc2 = reset_investigator_brochure_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_investigator_brochure_service()
        # Delete a version
        svc.delete_ib_version("IBV-001")
        assert svc.get_ib_version("IBV-001") is None
        # Reset should bring it back
        svc2 = reset_investigator_brochure_service()
        assert svc2.get_ib_version("IBV-001") is not None


# =====================================================================
# FILTERING AND EDGE CASES
# =====================================================================


class TestFilteringAndEdgeCases:
    """Test filtering combinations and edge cases."""

    @pytest.mark.anyio
    async def test_list_versions_empty_filter(self, client: AsyncClient):
        """Filter by a trial that has no versions."""
        resp = await client.get(
            f"{API_PREFIX}/ib-versions",
            params={"trial_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_list_safety_updates_empty_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/safety-updates",
            params={"update_type": "correction", "trial_id": LIBTAYO_TRIAL},
        )
        assert resp.status_code == 200
        data = resp.json()
        # LIBTAYO doesn't have correction updates
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_acknowledgments_escalated(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/acknowledgment-records", params={"status": "escalated"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["status"] == "escalated"

    @pytest.mark.anyio
    async def test_create_version_then_retrieve(self, client: AsyncClient):
        """Create a version and verify it shows in the list."""
        payload = _make_ib_version_create()
        resp = await client.post(f"{API_PREFIX}/ib-versions", json=payload)
        assert resp.status_code == 201
        created_id = resp.json()["id"]

        resp2 = await client.get(f"{API_PREFIX}/ib-versions/{created_id}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == created_id

    @pytest.mark.anyio
    async def test_create_version_then_update_status(self, client: AsyncClient):
        """Create a version, then update its status through lifecycle."""
        payload = _make_ib_version_create()
        resp = await client.post(f"{API_PREFIX}/ib-versions", json=payload)
        assert resp.status_code == 201
        version_id = resp.json()["id"]
        assert resp.json()["status"] == "draft"

        # Update to under_review
        resp2 = await client.put(
            f"{API_PREFIX}/ib-versions/{version_id}",
            json={"status": "under_review"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "under_review"

        # Update to approved
        resp3 = await client.put(
            f"{API_PREFIX}/ib-versions/{version_id}",
            json={"status": "approved", "approved_by": "Dr. Approver"},
        )
        assert resp3.status_code == 200
        assert resp3.json()["status"] == "approved"
        assert resp3.json()["approved_by"] == "Dr. Approver"

    @pytest.mark.anyio
    async def test_create_and_delete_safety_update(self, client: AsyncClient):
        """Create an update and then delete it."""
        payload = _make_safety_update_create()
        resp = await client.post(f"{API_PREFIX}/safety-updates", json=payload)
        assert resp.status_code == 201
        update_id = resp.json()["id"]

        resp2 = await client.delete(f"{API_PREFIX}/safety-updates/{update_id}")
        assert resp2.status_code == 204

        resp3 = await client.get(f"{API_PREFIX}/safety-updates/{update_id}")
        assert resp3.status_code == 404

    @pytest.mark.anyio
    async def test_create_distribution_with_ib_version(self, client: AsyncClient):
        """Create a distribution linked to an IB version."""
        payload = _make_distribution_record_create(ib_version_id="IBV-003")
        resp = await client.post(f"{API_PREFIX}/distribution-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["ib_version_id"] == "IBV-003"

    @pytest.mark.anyio
    async def test_create_acknowledgment_with_distribution(self, client: AsyncClient):
        """Create an acknowledgment linked to a distribution."""
        payload = _make_acknowledgment_record_create(distribution_id="DR-005")
        resp = await client.post(f"{API_PREFIX}/acknowledgment-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["distribution_id"] == "DR-005"

    @pytest.mark.anyio
    async def test_versions_sorted_by_created_at_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ib-versions")
        data = resp.json()
        dates = [item["created_at"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_safety_updates_sorted_by_update_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/safety-updates")
        data = resp.json()
        dates = [item["update_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_metrics_after_create_and_delete(self, client: AsyncClient):
        """Metrics should reflect dynamic changes."""
        # Get baseline metrics
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        baseline = resp1.json()

        # Create a new version
        payload = _make_ib_version_create()
        await client.post(f"{API_PREFIX}/ib-versions", json=payload)

        resp2 = await client.get(f"{API_PREFIX}/metrics")
        after_create = resp2.json()
        assert after_create["total_versions"] == baseline["total_versions"] + 1

        # Delete a version
        await client.delete(f"{API_PREFIX}/ib-versions/IBV-012")
        resp3 = await client.get(f"{API_PREFIX}/metrics")
        after_delete = resp3.json()
        assert after_delete["total_versions"] == baseline["total_versions"]


# =====================================================================
# ENUM COVERAGE
# =====================================================================


class TestEnumCoverage:
    """Verify enum values are represented in seed data."""

    @pytest.mark.anyio
    async def test_ib_statuses_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ib-versions")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "draft" in statuses
        assert "under_review" in statuses
        assert "approved" in statuses
        assert "distributed" in statuses
        assert "superseded" in statuses
        assert "retired" in statuses

    @pytest.mark.anyio
    async def test_update_types_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/safety-updates")
        data = resp.json()
        types = {item["update_type"] for item in data["items"]}
        assert "scheduled" in types
        assert "safety_driven" in types
        assert "regulatory_request" in types
        assert "new_data" in types
        assert "correction" in types

    @pytest.mark.anyio
    async def test_distribution_methods_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/distribution-records")
        data = resp.json()
        methods = {item["distribution_method"] for item in data["items"]}
        assert "electronic" in methods
        assert "paper" in methods
        assert "portal" in methods
        assert "registered_mail" in methods
        assert "hybrid" in methods

    @pytest.mark.anyio
    async def test_revision_scopes_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/revision-histories")
        data = resp.json()
        scopes = {item["revision_scope"] for item in data["items"]}
        assert "minor" in scopes
        assert "major" in scopes
        assert "safety_addendum" in scopes
        assert "full_rewrite" in scopes
        assert "administrative" in scopes

    @pytest.mark.anyio
    async def test_acknowledgment_statuses_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/acknowledgment-records")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "pending" in statuses
        assert "acknowledged" in statuses
        assert "overdue" in statuses
        assert "waived" in statuses
        assert "escalated" in statuses
