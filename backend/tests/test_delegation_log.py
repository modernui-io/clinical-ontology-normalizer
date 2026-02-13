"""Tests for Delegation Log (DELEG-LOG).

Covers:
- Seed data verification (delegation entries, authority records, training
  verifications, delegation audits)
- Delegation entry CRUD (create, read, update, delete, list, filter by
  trial/category/status)
- Authority record CRUD (create, read, update, delete, list, filter by
  trial/authority_level/is_qualified)
- Training verification CRUD (create, read, update, delete, list, filter by
  trial/training_status/is_gcp_training)
- Delegation audit CRUD (create, read, update, delete, list, filter by
  trial/audit_result)
- Metrics computation (overall and filtered by trial)
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.delegation_log import (
    AuditResult,
    AuthorityLevel,
    DelegationCategory,
    DelegationStatus,
    TrainingStatus,
)
from app.services.delegation_log_service import (
    DelegationLogService,
    get_delegation_log_service,
    reset_delegation_log_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/delegation-log"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_delegation_log_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> DelegationLogService:
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


def _make_entry_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-TEST-001",
        "delegator_name": "Dr. Test PI",
        "delegate_name": "Nurse Test Delegate",
        "delegation_category": "informed_consent",
        "authority_level": "sub_investigator",
        "effective_date": "2026-01-15T09:00:00Z",
        "approved_by": "Dr. Test PI",
        "specific_tasks": ["Obtain consent"],
    }
    defaults.update(overrides)
    return defaults


def _make_authority_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-TEST-001",
        "person_name": "Dr. Test Person",
        "authority_level": "principal_investigator",
        "credential_type": "Medical License",
        "verified_by": "CRA Test Verifier",
        "verified_date": "2026-01-10T09:00:00Z",
        "qualifications": ["Board Certified"],
    }
    defaults.update(overrides)
    return defaults


def _make_training_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-TEST-001",
        "trainee_name": "Test Trainee",
        "training_topic": "Good Clinical Practice (GCP)",
        "trainer_name": "CITI Program",
        "is_gcp_training": True,
    }
    defaults.update(overrides)
    return defaults


def _make_audit_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-TEST-001",
        "auditor_name": "CRA Test Auditor",
        "entries_reviewed": 5,
    }
    defaults.update(overrides)
    return defaults


# ===================================================================
# SEED DATA VERIFICATION
# ===================================================================


class TestSeedData:
    """Verify all 4 entity types are seeded with 12 records each."""

    @pytest.mark.anyio
    async def test_seed_delegation_entries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/delegation-entries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_seed_authority_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authority-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_training_verifications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/training-verifications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_delegation_audits(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/delegation-audits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12


# ===================================================================
# DELEGATION ENTRIES CRUD
# ===================================================================


class TestDelegationEntryCRUD:
    @pytest.mark.anyio
    async def test_list_delegation_entries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/delegation-entries")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_delegation_entry(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/delegation-entries/DEL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DEL-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_delegation_entry_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/delegation-entries/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_delegation_entry(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/delegation-entries", json=_make_entry_create()
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("DEL-")
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["delegation_category"] == "informed_consent"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/delegation-entries")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/delegation-entries", json=_make_entry_create())
        resp2 = await client.get(f"{API_PREFIX}/delegation-entries")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_delegation_entry(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/delegation-entries/DEL-001",
            json={"delegation_status": "expired", "notes": "Updated note"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["delegation_status"] == "expired"
        assert data["notes"] == "Updated note"

    @pytest.mark.anyio
    async def test_update_delegation_entry_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/delegation-entries/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_delegation_entry(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/delegation-entries/DEL-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/delegation-entries/DEL-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_delegation_entry_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/delegation-entries/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/delegation-entries", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_delegation_category(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/delegation-entries",
            params={"delegation_category": "informed_consent"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["delegation_category"] == "informed_consent"

    @pytest.mark.anyio
    async def test_filter_by_delegation_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/delegation-entries",
            params={"delegation_status": "active"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["delegation_status"] == "active"


# ===================================================================
# AUTHORITY RECORDS CRUD
# ===================================================================


class TestAuthorityRecordCRUD:
    @pytest.mark.anyio
    async def test_list_authority_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authority-records")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_authority_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authority-records/AUTH-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "AUTH-001"

    @pytest.mark.anyio
    async def test_get_authority_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authority-records/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_authority_record(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/authority-records", json=_make_authority_create()
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("AUTH-")
        assert data["credential_type"] == "Medical License"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/authority-records")
        before = resp1.json()["total"]
        await client.post(
            f"{API_PREFIX}/authority-records", json=_make_authority_create()
        )
        resp2 = await client.get(f"{API_PREFIX}/authority-records")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_authority_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/authority-records/AUTH-001",
            json={"is_qualified": False, "notes": "Credential under review"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_qualified"] is False
        assert data["notes"] == "Credential under review"

    @pytest.mark.anyio
    async def test_update_authority_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/authority-records/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_authority_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/authority-records/AUTH-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_authority_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/authority-records/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_authority_level(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/authority-records",
            params={"authority_level": "principal_investigator"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["authority_level"] == "principal_investigator"

    @pytest.mark.anyio
    async def test_filter_by_is_qualified(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/authority-records", params={"is_qualified": True}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["is_qualified"] is True

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/authority-records", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL


# ===================================================================
# TRAINING VERIFICATIONS CRUD
# ===================================================================


class TestTrainingVerificationCRUD:
    @pytest.mark.anyio
    async def test_list_training_verifications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/training-verifications")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_training_verification(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/training-verifications/TRN-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "TRN-001"

    @pytest.mark.anyio
    async def test_get_training_verification_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/training-verifications/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_training_verification(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/training-verifications", json=_make_training_create()
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("TRN-")
        assert data["training_topic"] == "Good Clinical Practice (GCP)"
        assert data["is_gcp_training"] is True

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/training-verifications")
        before = resp1.json()["total"]
        await client.post(
            f"{API_PREFIX}/training-verifications", json=_make_training_create()
        )
        resp2 = await client.get(f"{API_PREFIX}/training-verifications")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_training_verification(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/training-verifications/TRN-001",
            json={"training_status": "expired", "notes": "Training expired"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["training_status"] == "expired"
        assert data["notes"] == "Training expired"

    @pytest.mark.anyio
    async def test_update_training_verification_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/training-verifications/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_training_verification(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/training-verifications/TRN-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/training-verifications/TRN-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_training_verification_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/training-verifications/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_training_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/training-verifications",
            params={"training_status": "completed"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["training_status"] == "completed"

    @pytest.mark.anyio
    async def test_filter_by_is_gcp_training(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/training-verifications", params={"is_gcp_training": True}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["is_gcp_training"] is True

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/training-verifications",
            params={"trial_id": LIBTAYO_TRIAL},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL


# ===================================================================
# DELEGATION AUDITS CRUD
# ===================================================================


class TestDelegationAuditCRUD:
    @pytest.mark.anyio
    async def test_list_delegation_audits(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/delegation-audits")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_delegation_audit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/delegation-audits/DAUD-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "DAUD-001"

    @pytest.mark.anyio
    async def test_get_delegation_audit_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/delegation-audits/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_delegation_audit(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/delegation-audits", json=_make_audit_create()
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("DAUD-")
        assert data["auditor_name"] == "CRA Test Auditor"
        assert data["entries_reviewed"] == 5

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/delegation-audits")
        before = resp1.json()["total"]
        await client.post(
            f"{API_PREFIX}/delegation-audits", json=_make_audit_create()
        )
        resp2 = await client.get(f"{API_PREFIX}/delegation-audits")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_delegation_audit(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/delegation-audits/DAUD-001",
            json={"audit_result": "non_compliant", "notes": "Updated finding"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["audit_result"] == "non_compliant"
        assert data["notes"] == "Updated finding"

    @pytest.mark.anyio
    async def test_update_delegation_audit_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/delegation-audits/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_delegation_audit(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/delegation-audits/DAUD-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/delegation-audits/DAUD-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_delegation_audit_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/delegation-audits/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_audit_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/delegation-audits",
            params={"audit_result": "compliant"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["audit_result"] == "compliant"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/delegation-audits", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL


# ===================================================================
# METRICS
# ===================================================================


class TestMetrics:
    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_delegations" in data
        assert "total_authority_records" in data
        assert "total_training_records" in data
        assert "total_audits" in data
        assert "active_delegation_rate" in data
        assert "training_completion_rate" in data
        assert "compliance_rate" in data

    @pytest.mark.anyio
    async def test_metrics_total_delegations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_delegations"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_authority_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_authority_records"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_training_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_training_records"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_audits(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_audits"] == 12

    @pytest.mark.anyio
    async def test_metrics_has_breakdowns(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert isinstance(data["delegations_by_category"], dict)
        assert isinstance(data["delegations_by_status"], dict)
        assert isinstance(data["training_by_status"], dict)
        assert isinstance(data["audits_by_result"], dict)

    @pytest.mark.anyio
    async def test_metrics_with_trial_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        # EYLEA has 4 delegation entries in seed data
        assert data["total_delegations"] == 4
        # EYLEA has 4 authority records in seed data
        assert data["total_authority_records"] == 4

    def test_metrics_service_level(self, svc: DelegationLogService):
        metrics = svc.get_metrics()
        assert metrics.total_delegations == 12
        assert metrics.total_authority_records == 12
        assert metrics.total_training_records == 12
        assert metrics.total_audits == 12

    def test_metrics_service_level_with_trial(self, svc: DelegationLogService):
        metrics = svc.get_metrics(trial_id=EYLEA_TRIAL)
        assert metrics.total_delegations == 4
        assert metrics.total_authority_records == 4
        assert metrics.total_training_records == 4
        assert metrics.total_audits == 4


# ===================================================================
# EDGE CASES & UPDATE PRESERVATION
# ===================================================================


class TestEdgeCases:
    @pytest.mark.anyio
    async def test_update_entry_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/delegation-entries/DEL-001")
        original = resp.json()
        original_category = original["delegation_category"]

        resp2 = await client.put(
            f"{API_PREFIX}/delegation-entries/DEL-001",
            json={"notes": "Partial update"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["delegation_category"] == original_category
        assert updated["notes"] == "Partial update"

    @pytest.mark.anyio
    async def test_update_authority_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authority-records/AUTH-001")
        original = resp.json()
        original_level = original["authority_level"]

        resp2 = await client.put(
            f"{API_PREFIX}/authority-records/AUTH-001",
            json={"notes": "Updated authority note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["authority_level"] == original_level

    @pytest.mark.anyio
    async def test_update_training_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/training-verifications/TRN-001")
        original = resp.json()
        original_topic = original["training_topic"]

        resp2 = await client.put(
            f"{API_PREFIX}/training-verifications/TRN-001",
            json={"notes": "Updated training note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["training_topic"] == original_topic

    @pytest.mark.anyio
    async def test_update_audit_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/delegation-audits/DAUD-001")
        original = resp.json()
        original_auditor = original["auditor_name"]

        resp2 = await client.put(
            f"{API_PREFIX}/delegation-audits/DAUD-001",
            json={"notes": "Updated audit note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["auditor_name"] == original_auditor


# ===================================================================
# SINGLETON PATTERN
# ===================================================================


class TestSingleton:
    def test_get_returns_same_instance(self):
        svc1 = get_delegation_log_service()
        svc2 = get_delegation_log_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        svc1 = get_delegation_log_service()
        svc2 = reset_delegation_log_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_delegation_log_service()
        svc.delete_delegation_entry("DEL-001")
        assert svc.get_delegation_entry("DEL-001") is None
        svc2 = reset_delegation_log_service()
        assert svc2.get_delegation_entry("DEL-001") is not None


# ===================================================================
# SERVICE-LEVEL CRUD
# ===================================================================


class TestServiceLevelCRUD:
    def test_list_delegation_entries_service(self, svc: DelegationLogService):
        items = svc.list_delegation_entries()
        assert len(items) == 12

    def test_get_delegation_entry_service(self, svc: DelegationLogService):
        record = svc.get_delegation_entry("DEL-001")
        assert record is not None
        assert record.id == "DEL-001"

    def test_list_authority_records_service(self, svc: DelegationLogService):
        items = svc.list_authority_records()
        assert len(items) == 12

    def test_get_authority_record_service(self, svc: DelegationLogService):
        record = svc.get_authority_record("AUTH-001")
        assert record is not None
        assert record.id == "AUTH-001"

    def test_list_training_verifications_service(self, svc: DelegationLogService):
        items = svc.list_training_verifications()
        assert len(items) == 12

    def test_get_training_verification_service(self, svc: DelegationLogService):
        record = svc.get_training_verification("TRN-001")
        assert record is not None
        assert record.id == "TRN-001"

    def test_list_delegation_audits_service(self, svc: DelegationLogService):
        items = svc.list_delegation_audits()
        assert len(items) == 12

    def test_get_delegation_audit_service(self, svc: DelegationLogService):
        record = svc.get_delegation_audit("DAUD-001")
        assert record is not None
        assert record.id == "DAUD-001"

    def test_delete_delegation_entry_service(self, svc: DelegationLogService):
        assert svc.delete_delegation_entry("DEL-001") is True
        assert svc.get_delegation_entry("DEL-001") is None

    def test_delete_nonexistent_returns_false(self, svc: DelegationLogService):
        assert svc.delete_delegation_entry("NONEXISTENT") is False

    def test_filter_entries_by_trial(self, svc: DelegationLogService):
        items = svc.list_delegation_entries(trial_id=EYLEA_TRIAL)
        for item in items:
            assert item.trial_id == EYLEA_TRIAL

    def test_filter_entries_by_category(self, svc: DelegationLogService):
        items = svc.list_delegation_entries(
            delegation_category=DelegationCategory.INFORMED_CONSENT
        )
        for item in items:
            assert item.delegation_category == DelegationCategory.INFORMED_CONSENT

    def test_filter_entries_by_status(self, svc: DelegationLogService):
        items = svc.list_delegation_entries(
            delegation_status=DelegationStatus.ACTIVE
        )
        for item in items:
            assert item.delegation_status == DelegationStatus.ACTIVE

    def test_filter_authority_by_level(self, svc: DelegationLogService):
        items = svc.list_authority_records(
            authority_level=AuthorityLevel.PRINCIPAL_INVESTIGATOR
        )
        for item in items:
            assert item.authority_level == AuthorityLevel.PRINCIPAL_INVESTIGATOR

    def test_filter_authority_by_qualified(self, svc: DelegationLogService):
        items = svc.list_authority_records(is_qualified=True)
        for item in items:
            assert item.is_qualified is True

    def test_filter_training_by_status(self, svc: DelegationLogService):
        items = svc.list_training_verifications(
            training_status=TrainingStatus.COMPLETED
        )
        for item in items:
            assert item.training_status == TrainingStatus.COMPLETED

    def test_filter_training_by_gcp(self, svc: DelegationLogService):
        items = svc.list_training_verifications(is_gcp_training=True)
        for item in items:
            assert item.is_gcp_training is True

    def test_filter_audits_by_result(self, svc: DelegationLogService):
        items = svc.list_delegation_audits(audit_result=AuditResult.COMPLIANT)
        for item in items:
            assert item.audit_result == AuditResult.COMPLIANT


# ===================================================================
# BULK / MULTI-ENTITY
# ===================================================================


class TestBulkOperations:
    @pytest.mark.anyio
    async def test_create_multiple_delegation_entries(self, client: AsyncClient):
        for i in range(3):
            resp = await client.post(
                f"{API_PREFIX}/delegation-entries",
                json=_make_entry_create(delegate_name=f"Delegate-{i}"),
            )
            assert resp.status_code == 201
        resp = await client.get(f"{API_PREFIX}/delegation-entries")
        assert resp.json()["total"] == 15  # 12 seed + 3 new

    @pytest.mark.anyio
    async def test_delete_multiple_audits(self, client: AsyncClient):
        for audit_id in ["DAUD-001", "DAUD-002", "DAUD-003"]:
            resp = await client.delete(f"{API_PREFIX}/delegation-audits/{audit_id}")
            assert resp.status_code == 204
        resp = await client.get(f"{API_PREFIX}/delegation-audits")
        assert resp.json()["total"] == 9  # 12 seed - 3 deleted


# ===================================================================
# RESPONSE STRUCTURE
# ===================================================================


class TestAPIResponseStructure:
    @pytest.mark.anyio
    async def test_delegation_entry_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/delegation-entries/DEL-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "site_id", "delegator_name", "delegate_name",
            "delegation_category", "delegation_status", "authority_level",
            "effective_date", "approved_by", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_authority_record_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authority-records/AUTH-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "site_id", "person_name", "authority_level",
            "credential_type", "is_qualified", "verified_by", "verified_date",
            "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_training_verification_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/training-verifications/TRN-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "site_id", "trainee_name", "training_topic",
            "training_status", "is_gcp_training", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_delegation_audit_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/delegation-audits/DAUD-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "site_id", "audit_date", "auditor_name",
            "audit_result", "entries_reviewed", "entries_compliant",
            "findings_count", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_list_response_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/delegation-entries")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
