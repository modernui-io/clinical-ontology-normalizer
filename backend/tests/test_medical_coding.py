"""Tests for Medical Coding Management (MED-CODE).

Covers:
- Seed data verification (dictionary versions, coding entries, auto-coding rules,
  coding queries, coding batches)
- Dictionary version CRUD (create, read, update, delete, list, filter by type/active)
- Coding entry CRUD (create, read, update, delete, list, filter by trial/status/type/priority)
- Auto-coding rule CRUD (create, read, update, delete, list, filter by trial/type/active)
- Coding query CRUD (create, read, update, delete, list, filter by trial/status/priority)
- Coding batch CRUD (create, read, update, delete, list, filter by trial/type/status)
- Medical coding metrics computation
- Error handling (404s, validation errors)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.medical_coding import (
    CodingPriority,
    CodingStatus,
    DictionaryType,
    QueryStatus,
)
from app.services.medical_coding_service import (
    MedicalCodingService,
    get_medical_coding_service,
    reset_medical_coding_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/medical-coding"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_medical_coding_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> MedicalCodingService:
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


def _make_dict_version_create(**overrides) -> dict:
    defaults = {
        "dictionary_type": "meddra",
        "version": "27.0",
        "release_date": datetime.now(timezone.utc).isoformat(),
        "effective_date": datetime.now(timezone.utc).isoformat(),
        "total_terms": 84000,
        "loaded_by": "test_admin",
    }
    defaults.update(overrides)
    return defaults


def _make_coding_entry_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "PT-9001",
        "source_term": "headache",
        "dictionary_type": "meddra",
        "dictionary_version": "26.1",
        "priority": "medium",
    }
    defaults.update(overrides)
    return defaults


def _make_auto_coding_rule_create(**overrides) -> dict:
    defaults = {
        "dictionary_type": "meddra",
        "source_pattern": "test_pattern",
        "target_code": "10099999",
        "target_term": "Test Term",
        "confidence_threshold": 0.9,
        "match_type": "exact",
        "created_by": "test_coder",
    }
    defaults.update(overrides)
    return defaults


def _make_coding_query_create(**overrides) -> dict:
    defaults = {
        "coding_entry_id": "CE-001",
        "trial_id": EYLEA_TRIAL,
        "subject_id": "PT-1001",
        "query_text": "Please clarify the source term for accurate coding.",
        "priority": "medium",
        "opened_by": "test_coder",
    }
    defaults.update(overrides)
    return defaults


def _make_coding_batch_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "dictionary_type": "meddra",
        "batch_name": "Test Batch",
        "started_by": "test_lead",
    }
    defaults.update(overrides)
    return defaults


# ===========================================================================
# SEED DATA VERIFICATION
# ===========================================================================


class TestSeedData:
    """Verify the seeded demo data is correct."""

    def test_seed_dictionary_versions_count(self, svc: MedicalCodingService):
        versions = svc.list_dictionary_versions()
        assert len(versions) == 12

    def test_seed_dictionary_versions_active(self, svc: MedicalCodingService):
        active = svc.list_dictionary_versions(active=True)
        assert len(active) == 6

    def test_seed_dictionary_versions_inactive(self, svc: MedicalCodingService):
        inactive = svc.list_dictionary_versions(active=False)
        assert len(inactive) == 6

    def test_seed_coding_entries_count(self, svc: MedicalCodingService):
        entries = svc.list_coding_entries()
        assert len(entries) == 15

    def test_seed_coding_entries_eylea(self, svc: MedicalCodingService):
        entries = svc.list_coding_entries(trial_id=EYLEA_TRIAL)
        assert len(entries) == 5

    def test_seed_coding_entries_dupixent(self, svc: MedicalCodingService):
        entries = svc.list_coding_entries(trial_id=DUPIXENT_TRIAL)
        assert len(entries) == 5

    def test_seed_coding_entries_libtayo(self, svc: MedicalCodingService):
        entries = svc.list_coding_entries(trial_id=LIBTAYO_TRIAL)
        assert len(entries) == 5

    def test_seed_auto_coding_rules_count(self, svc: MedicalCodingService):
        rules = svc.list_auto_coding_rules()
        assert len(rules) == 12

    def test_seed_auto_coding_rules_active(self, svc: MedicalCodingService):
        active = svc.list_auto_coding_rules(active=True)
        assert len(active) == 11

    def test_seed_coding_queries_count(self, svc: MedicalCodingService):
        queries = svc.list_coding_queries()
        assert len(queries) == 10

    def test_seed_coding_batches_count(self, svc: MedicalCodingService):
        batches = svc.list_coding_batches()
        assert len(batches) == 10

    def test_seed_coding_batches_completed(self, svc: MedicalCodingService):
        completed = svc.list_coding_batches(status="completed")
        assert len(completed) == 5

    def test_seed_coding_batches_in_progress(self, svc: MedicalCodingService):
        in_progress = svc.list_coding_batches(status="in_progress")
        assert len(in_progress) == 5

    def test_seed_dictionary_version_dv001(self, svc: MedicalCodingService):
        dv = svc.get_dictionary_version("DV-001")
        assert dv is not None
        assert dv.dictionary_type == DictionaryType.MEDDRA
        assert dv.version == "26.1"
        assert dv.active is True

    def test_seed_coding_entry_ce001(self, svc: MedicalCodingService):
        ce = svc.get_coding_entry("CE-001")
        assert ce is not None
        assert ce.trial_id == EYLEA_TRIAL
        assert ce.source_term == "eye pain"
        assert ce.status == CodingStatus.APPROVED

    def test_seed_auto_coding_rule_acr001(self, svc: MedicalCodingService):
        rule = svc.get_auto_coding_rule("ACR-001")
        assert rule is not None
        assert rule.source_pattern == "headache"
        assert rule.target_code == "10019211"

    def test_seed_coding_query_cq001(self, svc: MedicalCodingService):
        cq = svc.get_coding_query("CQ-001")
        assert cq is not None
        assert cq.status == QueryStatus.OPEN
        assert cq.trial_id == EYLEA_TRIAL

    def test_seed_coding_batch_cb001(self, svc: MedicalCodingService):
        cb = svc.get_coding_batch("CB-001")
        assert cb is not None
        assert cb.trial_id == EYLEA_TRIAL
        assert cb.status == "in_progress"


# ===========================================================================
# DICTIONARY VERSION CRUD - API
# ===========================================================================


class TestDictionaryVersionAPI:
    """Test dictionary version API endpoints."""

    @pytest.mark.anyio
    async def test_list_dictionary_versions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dictionary-versions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 12
        assert len(body["items"]) == 12

    @pytest.mark.anyio
    async def test_list_dictionary_versions_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dictionary-versions", params={"dictionary_type": "meddra"})
        assert resp.status_code == 200
        body = resp.json()
        assert all(item["dictionary_type"] == "meddra" for item in body["items"])

    @pytest.mark.anyio
    async def test_list_dictionary_versions_filter_active(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dictionary-versions", params={"active": True})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 6
        assert all(item["active"] is True for item in body["items"])

    @pytest.mark.anyio
    async def test_list_dictionary_versions_filter_inactive(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dictionary-versions", params={"active": False})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 6

    @pytest.mark.anyio
    async def test_list_dictionary_versions_filter_who_drug(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dictionary-versions", params={"dictionary_type": "who_drug"})
        assert resp.status_code == 200
        body = resp.json()
        assert all(item["dictionary_type"] == "who_drug" for item in body["items"])

    @pytest.mark.anyio
    async def test_get_dictionary_version(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dictionary-versions/DV-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "DV-001"
        assert body["dictionary_type"] == "meddra"
        assert body["version"] == "26.1"

    @pytest.mark.anyio
    async def test_get_dictionary_version_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dictionary-versions/DV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_dictionary_version(self, client: AsyncClient):
        payload = _make_dict_version_create()
        resp = await client.post(f"{API_PREFIX}/dictionary-versions", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["dictionary_type"] == "meddra"
        assert body["version"] == "27.0"
        assert body["active"] is True
        assert body["id"].startswith("DV-")

    @pytest.mark.anyio
    async def test_create_dictionary_version_who_drug(self, client: AsyncClient):
        payload = _make_dict_version_create(dictionary_type="who_drug", version="2025-Q1")
        resp = await client.post(f"{API_PREFIX}/dictionary-versions", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["dictionary_type"] == "who_drug"

    @pytest.mark.anyio
    async def test_update_dictionary_version(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/dictionary-versions/DV-001",
            json={"notes": "Updated notes for testing"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["notes"] == "Updated notes for testing"

    @pytest.mark.anyio
    async def test_update_dictionary_version_deactivate(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/dictionary-versions/DV-001",
            json={"active": False},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["active"] is False

    @pytest.mark.anyio
    async def test_update_dictionary_version_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/dictionary-versions/DV-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_dictionary_version(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/dictionary-versions/DV-012")
        assert resp.status_code == 204

        resp = await client.get(f"{API_PREFIX}/dictionary-versions/DV-012")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_dictionary_version_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/dictionary-versions/DV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_then_get_dictionary_version(self, client: AsyncClient):
        payload = _make_dict_version_create(version="99.0")
        create_resp = await client.post(f"{API_PREFIX}/dictionary-versions", json=payload)
        assert create_resp.status_code == 201
        created_id = create_resp.json()["id"]

        get_resp = await client.get(f"{API_PREFIX}/dictionary-versions/{created_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["version"] == "99.0"

    @pytest.mark.anyio
    async def test_list_filter_type_and_active(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/dictionary-versions",
            params={"dictionary_type": "meddra", "active": True},
        )
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert item["dictionary_type"] == "meddra"
            assert item["active"] is True


# ===========================================================================
# CODING ENTRY CRUD - API
# ===========================================================================


class TestCodingEntryAPI:
    """Test coding entry API endpoints."""

    @pytest.mark.anyio
    async def test_list_coding_entries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/entries")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 15
        assert len(body["items"]) == 15

    @pytest.mark.anyio
    async def test_list_coding_entries_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/entries", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5
        assert all(item["trial_id"] == EYLEA_TRIAL for item in body["items"])

    @pytest.mark.anyio
    async def test_list_coding_entries_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/entries", params={"status": "approved"})
        assert resp.status_code == 200
        body = resp.json()
        assert all(item["status"] == "approved" for item in body["items"])

    @pytest.mark.anyio
    async def test_list_coding_entries_filter_dictionary_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/entries", params={"dictionary_type": "who_drug"})
        assert resp.status_code == 200
        body = resp.json()
        assert all(item["dictionary_type"] == "who_drug" for item in body["items"])

    @pytest.mark.anyio
    async def test_list_coding_entries_filter_priority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/entries", params={"priority": "urgent"})
        assert resp.status_code == 200
        body = resp.json()
        assert all(item["priority"] == "urgent" for item in body["items"])

    @pytest.mark.anyio
    async def test_list_coding_entries_filter_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/entries", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5

    @pytest.mark.anyio
    async def test_list_coding_entries_filter_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/entries", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5

    @pytest.mark.anyio
    async def test_get_coding_entry(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/entries/CE-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "CE-001"
        assert body["source_term"] == "eye pain"

    @pytest.mark.anyio
    async def test_get_coding_entry_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/entries/CE-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_coding_entry(self, client: AsyncClient):
        payload = _make_coding_entry_create()
        resp = await client.post(f"{API_PREFIX}/entries", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["source_term"] == "headache"
        assert body["status"] == "pending"
        assert body["id"].startswith("CE-")

    @pytest.mark.anyio
    async def test_create_coding_entry_who_drug(self, client: AsyncClient):
        payload = _make_coding_entry_create(
            source_term="Metformin 500mg",
            dictionary_type="who_drug",
            dictionary_version="2024-Q3",
        )
        resp = await client.post(f"{API_PREFIX}/entries", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["dictionary_type"] == "who_drug"

    @pytest.mark.anyio
    async def test_create_coding_entry_urgent(self, client: AsyncClient):
        payload = _make_coding_entry_create(priority="urgent")
        resp = await client.post(f"{API_PREFIX}/entries", json=payload)
        assert resp.status_code == 201
        assert resp.json()["priority"] == "urgent"

    @pytest.mark.anyio
    async def test_update_coding_entry(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/entries/CE-004",
            json={
                "coded_term": "Headache",
                "coded_code": "10019211",
                "status": "manually_coded",
                "coded_by": "coder_test",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["coded_term"] == "Headache"
        assert body["status"] == "manually_coded"
        assert body["coded_by"] == "coder_test"

    @pytest.mark.anyio
    async def test_update_coding_entry_verified(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/entries/CE-003",
            json={
                "status": "verified",
                "verified_by": "dr.test",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "verified"
        assert body["verified_by"] == "dr.test"

    @pytest.mark.anyio
    async def test_update_coding_entry_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/entries/CE-NONEXISTENT",
            json={"status": "approved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_coding_entry(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/entries/CE-015")
        assert resp.status_code == 204

        resp = await client.get(f"{API_PREFIX}/entries/CE-015")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_coding_entry_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/entries/CE-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_then_list_coding_entry(self, client: AsyncClient):
        payload = _make_coding_entry_create(subject_id="PT-NEW")
        resp = await client.post(f"{API_PREFIX}/entries", json=payload)
        assert resp.status_code == 201

        list_resp = await client.get(f"{API_PREFIX}/entries")
        assert list_resp.json()["total"] == 16

    @pytest.mark.anyio
    async def test_list_entries_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/entries", params={"trial_id": "nonexistent-trial"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_list_entries_combined_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/entries",
            params={"trial_id": EYLEA_TRIAL, "dictionary_type": "meddra"},
        )
        assert resp.status_code == 200
        body = resp.json()
        for item in body["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["dictionary_type"] == "meddra"


# ===========================================================================
# AUTO-CODING RULE CRUD - API
# ===========================================================================


class TestAutoCodingRuleAPI:
    """Test auto-coding rule API endpoints."""

    @pytest.mark.anyio
    async def test_list_auto_coding_rules(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/auto-coding-rules")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 12
        assert len(body["items"]) == 12

    @pytest.mark.anyio
    async def test_list_auto_coding_rules_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/auto-coding-rules", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        body = resp.json()
        assert all(item["trial_id"] == EYLEA_TRIAL for item in body["items"])

    @pytest.mark.anyio
    async def test_list_auto_coding_rules_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/auto-coding-rules", params={"dictionary_type": "who_drug"})
        assert resp.status_code == 200
        body = resp.json()
        assert all(item["dictionary_type"] == "who_drug" for item in body["items"])

    @pytest.mark.anyio
    async def test_list_auto_coding_rules_filter_active(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/auto-coding-rules", params={"active": True})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 11
        assert all(item["active"] is True for item in body["items"])

    @pytest.mark.anyio
    async def test_list_auto_coding_rules_filter_inactive(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/auto-coding-rules", params={"active": False})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1

    @pytest.mark.anyio
    async def test_get_auto_coding_rule(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/auto-coding-rules/ACR-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "ACR-001"
        assert body["source_pattern"] == "headache"

    @pytest.mark.anyio
    async def test_get_auto_coding_rule_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/auto-coding-rules/ACR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_auto_coding_rule(self, client: AsyncClient):
        payload = _make_auto_coding_rule_create()
        resp = await client.post(f"{API_PREFIX}/auto-coding-rules", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["source_pattern"] == "test_pattern"
        assert body["active"] is True
        assert body["hit_count"] == 0
        assert body["id"].startswith("ACR-")

    @pytest.mark.anyio
    async def test_create_auto_coding_rule_with_trial(self, client: AsyncClient):
        payload = _make_auto_coding_rule_create(trial_id=DUPIXENT_TRIAL)
        resp = await client.post(f"{API_PREFIX}/auto-coding-rules", json=payload)
        assert resp.status_code == 201
        assert resp.json()["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_create_auto_coding_rule_who_drug(self, client: AsyncClient):
        payload = _make_auto_coding_rule_create(
            dictionary_type="who_drug",
            source_pattern="metformin%",
            target_code="A10BA02",
            target_term="Metformin",
        )
        resp = await client.post(f"{API_PREFIX}/auto-coding-rules", json=payload)
        assert resp.status_code == 201
        assert resp.json()["dictionary_type"] == "who_drug"

    @pytest.mark.anyio
    async def test_update_auto_coding_rule(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/auto-coding-rules/ACR-001",
            json={"confidence_threshold": 0.85},
        )
        assert resp.status_code == 200
        assert resp.json()["confidence_threshold"] == 0.85

    @pytest.mark.anyio
    async def test_update_auto_coding_rule_deactivate(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/auto-coding-rules/ACR-001",
            json={"active": False},
        )
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    @pytest.mark.anyio
    async def test_update_auto_coding_rule_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/auto-coding-rules/ACR-NONEXISTENT",
            json={"active": False},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_auto_coding_rule(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/auto-coding-rules/ACR-011")
        assert resp.status_code == 204

        resp = await client.get(f"{API_PREFIX}/auto-coding-rules/ACR-011")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_auto_coding_rule_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/auto-coding-rules/ACR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_then_get_rule(self, client: AsyncClient):
        payload = _make_auto_coding_rule_create(source_pattern="unique_test")
        create_resp = await client.post(f"{API_PREFIX}/auto-coding-rules", json=payload)
        assert create_resp.status_code == 201
        created_id = create_resp.json()["id"]

        get_resp = await client.get(f"{API_PREFIX}/auto-coding-rules/{created_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["source_pattern"] == "unique_test"

    @pytest.mark.anyio
    async def test_update_rule_target(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/auto-coding-rules/ACR-002",
            json={"target_code": "10099999", "target_term": "Updated Term"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["target_code"] == "10099999"
        assert body["target_term"] == "Updated Term"


# ===========================================================================
# CODING QUERY CRUD - API
# ===========================================================================


class TestCodingQueryAPI:
    """Test coding query API endpoints."""

    @pytest.mark.anyio
    async def test_list_coding_queries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 10
        assert len(body["items"]) == 10

    @pytest.mark.anyio
    async def test_list_coding_queries_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        body = resp.json()
        assert all(item["trial_id"] == EYLEA_TRIAL for item in body["items"])

    @pytest.mark.anyio
    async def test_list_coding_queries_filter_status_open(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries", params={"status": "open"})
        assert resp.status_code == 200
        body = resp.json()
        assert all(item["status"] == "open" for item in body["items"])

    @pytest.mark.anyio
    async def test_list_coding_queries_filter_status_closed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries", params={"status": "closed"})
        assert resp.status_code == 200
        body = resp.json()
        assert all(item["status"] == "closed" for item in body["items"])

    @pytest.mark.anyio
    async def test_list_coding_queries_filter_priority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries", params={"priority": "urgent"})
        assert resp.status_code == 200
        body = resp.json()
        assert all(item["priority"] == "urgent" for item in body["items"])

    @pytest.mark.anyio
    async def test_list_coding_queries_filter_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1

    @pytest.mark.anyio
    async def test_get_coding_query(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries/CQ-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "CQ-001"
        assert body["status"] == "open"

    @pytest.mark.anyio
    async def test_get_coding_query_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries/CQ-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_coding_query(self, client: AsyncClient):
        payload = _make_coding_query_create()
        resp = await client.post(f"{API_PREFIX}/queries", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "open"
        assert body["coding_entry_id"] == "CE-001"
        assert body["id"].startswith("CQ-")

    @pytest.mark.anyio
    async def test_create_coding_query_with_due_date(self, client: AsyncClient):
        due = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
        payload = _make_coding_query_create(due_date=due)
        resp = await client.post(f"{API_PREFIX}/queries", json=payload)
        assert resp.status_code == 201
        assert resp.json()["due_date"] is not None

    @pytest.mark.anyio
    async def test_create_coding_query_urgent(self, client: AsyncClient):
        payload = _make_coding_query_create(priority="urgent")
        resp = await client.post(f"{API_PREFIX}/queries", json=payload)
        assert resp.status_code == 201
        assert resp.json()["priority"] == "urgent"

    @pytest.mark.anyio
    async def test_update_coding_query_answer(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/queries/CQ-001",
            json={
                "status": "answered",
                "response_text": "Headache is a new onset AE.",
                "response_by": "site_crc_test",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "answered"
        assert body["response_text"] == "Headache is a new onset AE."

    @pytest.mark.anyio
    async def test_update_coding_query_close(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/queries/CQ-002",
            json={"status": "closed"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "closed"
        assert body["closed_date"] is not None

    @pytest.mark.anyio
    async def test_update_coding_query_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/queries/CQ-NONEXISTENT",
            json={"status": "closed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_coding_query(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/queries/CQ-008")
        assert resp.status_code == 204

        resp = await client.get(f"{API_PREFIX}/queries/CQ-008")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_coding_query_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/queries/CQ-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_then_list_queries(self, client: AsyncClient):
        payload = _make_coding_query_create(query_text="New test query")
        resp = await client.post(f"{API_PREFIX}/queries", json=payload)
        assert resp.status_code == 201

        list_resp = await client.get(f"{API_PREFIX}/queries")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_list_queries_empty_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_update_query_assigned_to(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/queries/CQ-003",
            json={"assigned_to": "new_assignee"},
        )
        assert resp.status_code == 200
        assert resp.json()["assigned_to"] == "new_assignee"


# ===========================================================================
# CODING BATCH CRUD - API
# ===========================================================================


class TestCodingBatchAPI:
    """Test coding batch API endpoints."""

    @pytest.mark.anyio
    async def test_list_coding_batches(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 10
        assert len(body["items"]) == 10

    @pytest.mark.anyio
    async def test_list_coding_batches_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        body = resp.json()
        assert all(item["trial_id"] == EYLEA_TRIAL for item in body["items"])

    @pytest.mark.anyio
    async def test_list_coding_batches_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches", params={"dictionary_type": "who_drug"})
        assert resp.status_code == 200
        body = resp.json()
        assert all(item["dictionary_type"] == "who_drug" for item in body["items"])

    @pytest.mark.anyio
    async def test_list_coding_batches_filter_status_completed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches", params={"status": "completed"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5
        assert all(item["status"] == "completed" for item in body["items"])

    @pytest.mark.anyio
    async def test_list_coding_batches_filter_status_in_progress(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches", params={"status": "in_progress"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5

    @pytest.mark.anyio
    async def test_list_coding_batches_filter_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 4

    @pytest.mark.anyio
    async def test_get_coding_batch(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches/CB-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "CB-001"
        assert body["batch_name"] == "EYLEA AE Batch Week 12"

    @pytest.mark.anyio
    async def test_get_coding_batch_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches/CB-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_coding_batch(self, client: AsyncClient):
        payload = _make_coding_batch_create()
        resp = await client.post(f"{API_PREFIX}/batches", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["batch_name"] == "Test Batch"
        assert body["status"] == "in_progress"
        assert body["total_entries"] == 0
        assert body["id"].startswith("CB-")

    @pytest.mark.anyio
    async def test_create_coding_batch_who_drug(self, client: AsyncClient):
        payload = _make_coding_batch_create(
            dictionary_type="who_drug",
            batch_name="ConMed Batch Test",
        )
        resp = await client.post(f"{API_PREFIX}/batches", json=payload)
        assert resp.status_code == 201
        assert resp.json()["dictionary_type"] == "who_drug"

    @pytest.mark.anyio
    async def test_update_coding_batch_progress(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/batches/CB-001",
            json={
                "coded_entries": 44,
                "auto_coded": 40,
                "manually_coded": 4,
                "pending_entries": 1,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["coded_entries"] == 44
        assert body["pending_entries"] == 1

    @pytest.mark.anyio
    async def test_update_coding_batch_complete(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/batches/CB-001",
            json={"status": "completed", "pending_entries": 0},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["completed_at"] is not None

    @pytest.mark.anyio
    async def test_update_coding_batch_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/batches/CB-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_coding_batch(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/batches/CB-010")
        assert resp.status_code == 204

        resp = await client.get(f"{API_PREFIX}/batches/CB-010")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_coding_batch_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/batches/CB-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_then_get_batch(self, client: AsyncClient):
        payload = _make_coding_batch_create(batch_name="Unique Test Batch")
        create_resp = await client.post(f"{API_PREFIX}/batches", json=payload)
        assert create_resp.status_code == 201
        created_id = create_resp.json()["id"]

        get_resp = await client.get(f"{API_PREFIX}/batches/{created_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["batch_name"] == "Unique Test Batch"

    @pytest.mark.anyio
    async def test_list_batches_empty_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_update_batch_queries_raised(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/batches/CB-001",
            json={"queries_raised": 5},
        )
        assert resp.status_code == 200
        assert resp.json()["queries_raised"] == 5


# ===========================================================================
# METRICS
# ===========================================================================


class TestMedicalCodingMetrics:
    """Test medical coding metrics endpoint."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_dictionary_versions"] == 12
        assert body["active_versions"] == 6
        assert body["total_coding_entries"] == 15
        assert body["total_auto_coding_rules"] > 0
        assert body["total_queries"] == 10
        assert body["total_batches"] == 10

    @pytest.mark.anyio
    async def test_get_metrics_has_entries_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert "entries_by_status" in body
        assert len(body["entries_by_status"]) > 0

    @pytest.mark.anyio
    async def test_get_metrics_has_entries_by_dictionary(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert "entries_by_dictionary" in body
        assert "meddra" in body["entries_by_dictionary"]

    @pytest.mark.anyio
    async def test_get_metrics_has_queries_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert "queries_by_status" in body
        assert len(body["queries_by_status"]) > 0

    @pytest.mark.anyio
    async def test_get_metrics_auto_code_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["auto_code_rate_pct"] >= 0
        assert body["auto_code_rate_pct"] <= 100

    @pytest.mark.anyio
    async def test_get_metrics_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_coding_entries"] == 5

    @pytest.mark.anyio
    async def test_get_metrics_filter_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_coding_entries"] == 5

    @pytest.mark.anyio
    async def test_get_metrics_filter_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_coding_entries"] == 5

    @pytest.mark.anyio
    async def test_get_metrics_open_queries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["open_queries"] >= 0

    @pytest.mark.anyio
    async def test_get_metrics_completed_batches(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["completed_batches"] == 5

    @pytest.mark.anyio
    async def test_get_metrics_avg_query_resolution(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["avg_query_resolution_days"] >= 0

    @pytest.mark.anyio
    async def test_get_metrics_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_coding_entries"] == 0
        assert body["total_queries"] == 0
        assert body["total_batches"] == 0

    @pytest.mark.anyio
    async def test_get_metrics_active_rules(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        body = resp.json()
        assert body["active_rules"] >= 1


# ===========================================================================
# SERVICE UNIT TESTS
# ===========================================================================


class TestServiceDictionaryVersions:
    """Direct service unit tests for dictionary versions."""

    def test_create_dictionary_version(self, svc: MedicalCodingService):
        from app.schemas.medical_coding import DictionaryVersionCreate
        payload = DictionaryVersionCreate(
            dictionary_type=DictionaryType.MEDDRA,
            version="28.0",
            release_date=datetime.now(timezone.utc),
            effective_date=datetime.now(timezone.utc),
            total_terms=85000,
            loaded_by="test",
        )
        created = svc.create_dictionary_version(payload)
        assert created.id.startswith("DV-")
        assert created.version == "28.0"
        assert created.active is True

    def test_get_nonexistent_version(self, svc: MedicalCodingService):
        assert svc.get_dictionary_version("DV-NOPE") is None

    def test_update_nonexistent_version(self, svc: MedicalCodingService):
        from app.schemas.medical_coding import DictionaryVersionUpdate
        result = svc.update_dictionary_version("DV-NOPE", DictionaryVersionUpdate(notes="test"))
        assert result is None

    def test_delete_nonexistent_version(self, svc: MedicalCodingService):
        assert svc.delete_dictionary_version("DV-NOPE") is False

    def test_delete_existing_version(self, svc: MedicalCodingService):
        assert svc.delete_dictionary_version("DV-001") is True
        assert svc.get_dictionary_version("DV-001") is None

    def test_list_filter_snomed(self, svc: MedicalCodingService):
        versions = svc.list_dictionary_versions(dictionary_type=DictionaryType.SNOMED)
        assert all(v.dictionary_type == DictionaryType.SNOMED for v in versions)

    def test_list_filter_loinc(self, svc: MedicalCodingService):
        versions = svc.list_dictionary_versions(dictionary_type=DictionaryType.LOINC)
        assert len(versions) == 1

    def test_list_filter_icd10(self, svc: MedicalCodingService):
        versions = svc.list_dictionary_versions(dictionary_type=DictionaryType.ICD10)
        assert len(versions) == 2


class TestServiceCodingEntries:
    """Direct service unit tests for coding entries."""

    def test_create_coding_entry(self, svc: MedicalCodingService):
        from app.schemas.medical_coding import CodingEntryCreate
        payload = CodingEntryCreate(
            trial_id=EYLEA_TRIAL,
            subject_id="PT-NEW",
            source_term="dizziness",
            dictionary_type=DictionaryType.MEDDRA,
            dictionary_version="26.1",
        )
        created = svc.create_coding_entry(payload)
        assert created.id.startswith("CE-")
        assert created.status == CodingStatus.PENDING

    def test_get_nonexistent_entry(self, svc: MedicalCodingService):
        assert svc.get_coding_entry("CE-NOPE") is None

    def test_update_nonexistent_entry(self, svc: MedicalCodingService):
        from app.schemas.medical_coding import CodingEntryUpdate
        result = svc.update_coding_entry("CE-NOPE", CodingEntryUpdate(status=CodingStatus.APPROVED))
        assert result is None

    def test_delete_nonexistent_entry(self, svc: MedicalCodingService):
        assert svc.delete_coding_entry("CE-NOPE") is False

    def test_delete_existing_entry(self, svc: MedicalCodingService):
        assert svc.delete_coding_entry("CE-001") is True
        assert svc.get_coding_entry("CE-001") is None

    def test_update_sets_coded_date(self, svc: MedicalCodingService):
        from app.schemas.medical_coding import CodingEntryUpdate
        result = svc.update_coding_entry("CE-009", CodingEntryUpdate(coded_by="test_coder"))
        assert result is not None
        assert result.coded_date is not None
        assert result.coded_by == "test_coder"

    def test_update_sets_verified_date(self, svc: MedicalCodingService):
        from app.schemas.medical_coding import CodingEntryUpdate
        result = svc.update_coding_entry("CE-005", CodingEntryUpdate(verified_by="dr.test"))
        assert result is not None
        assert result.verified_date is not None

    def test_list_filter_pending(self, svc: MedicalCodingService):
        entries = svc.list_coding_entries(status=CodingStatus.PENDING)
        assert all(e.status == CodingStatus.PENDING for e in entries)

    def test_list_filter_auto_coded(self, svc: MedicalCodingService):
        entries = svc.list_coding_entries(status=CodingStatus.AUTO_CODED)
        assert all(e.status == CodingStatus.AUTO_CODED for e in entries)

    def test_list_filter_meddra(self, svc: MedicalCodingService):
        entries = svc.list_coding_entries(dictionary_type=DictionaryType.MEDDRA)
        assert all(e.dictionary_type == DictionaryType.MEDDRA for e in entries)

    def test_list_filter_who_drug(self, svc: MedicalCodingService):
        entries = svc.list_coding_entries(dictionary_type=DictionaryType.WHO_DRUG)
        assert all(e.dictionary_type == DictionaryType.WHO_DRUG for e in entries)
        assert len(entries) == 3


class TestServiceAutoCodingRules:
    """Direct service unit tests for auto-coding rules."""

    def test_create_rule(self, svc: MedicalCodingService):
        from app.schemas.medical_coding import AutoCodingRuleCreate
        payload = AutoCodingRuleCreate(
            dictionary_type=DictionaryType.MEDDRA,
            source_pattern="test_service",
            target_code="10099999",
            target_term="Test",
            created_by="tester",
        )
        created = svc.create_auto_coding_rule(payload)
        assert created.id.startswith("ACR-")
        assert created.active is True
        assert created.hit_count == 0

    def test_get_nonexistent_rule(self, svc: MedicalCodingService):
        assert svc.get_auto_coding_rule("ACR-NOPE") is None

    def test_update_nonexistent_rule(self, svc: MedicalCodingService):
        from app.schemas.medical_coding import AutoCodingRuleUpdate
        result = svc.update_auto_coding_rule("ACR-NOPE", AutoCodingRuleUpdate(active=False))
        assert result is None

    def test_delete_nonexistent_rule(self, svc: MedicalCodingService):
        assert svc.delete_auto_coding_rule("ACR-NOPE") is False

    def test_delete_existing_rule(self, svc: MedicalCodingService):
        assert svc.delete_auto_coding_rule("ACR-001") is True
        assert svc.get_auto_coding_rule("ACR-001") is None

    def test_list_filter_meddra_rules(self, svc: MedicalCodingService):
        rules = svc.list_auto_coding_rules(dictionary_type=DictionaryType.MEDDRA)
        assert all(r.dictionary_type == DictionaryType.MEDDRA for r in rules)

    def test_list_filter_who_drug_rules(self, svc: MedicalCodingService):
        rules = svc.list_auto_coding_rules(dictionary_type=DictionaryType.WHO_DRUG)
        assert all(r.dictionary_type == DictionaryType.WHO_DRUG for r in rules)
        assert len(rules) == 3

    def test_list_filter_eylea_rules(self, svc: MedicalCodingService):
        rules = svc.list_auto_coding_rules(trial_id=EYLEA_TRIAL)
        assert all(r.trial_id == EYLEA_TRIAL for r in rules)


class TestServiceCodingQueries:
    """Direct service unit tests for coding queries."""

    def test_create_query(self, svc: MedicalCodingService):
        from app.schemas.medical_coding import CodingQueryCreate
        payload = CodingQueryCreate(
            coding_entry_id="CE-001",
            trial_id=EYLEA_TRIAL,
            subject_id="PT-1001",
            query_text="Test query text",
            opened_by="tester",
        )
        created = svc.create_coding_query(payload)
        assert created.id.startswith("CQ-")
        assert created.status == QueryStatus.OPEN

    def test_get_nonexistent_query(self, svc: MedicalCodingService):
        assert svc.get_coding_query("CQ-NOPE") is None

    def test_update_nonexistent_query(self, svc: MedicalCodingService):
        from app.schemas.medical_coding import CodingQueryUpdate
        result = svc.update_coding_query("CQ-NOPE", CodingQueryUpdate(status=QueryStatus.CLOSED))
        assert result is None

    def test_delete_nonexistent_query(self, svc: MedicalCodingService):
        assert svc.delete_coding_query("CQ-NOPE") is False

    def test_delete_existing_query(self, svc: MedicalCodingService):
        assert svc.delete_coding_query("CQ-001") is True
        assert svc.get_coding_query("CQ-001") is None

    def test_update_sets_response_date(self, svc: MedicalCodingService):
        from app.schemas.medical_coding import CodingQueryUpdate
        result = svc.update_coding_query("CQ-001", CodingQueryUpdate(response_by="responder"))
        assert result is not None
        assert result.response_date is not None

    def test_update_sets_closed_date(self, svc: MedicalCodingService):
        from app.schemas.medical_coding import CodingQueryUpdate
        result = svc.update_coding_query("CQ-001", CodingQueryUpdate(status=QueryStatus.CLOSED))
        assert result is not None
        assert result.closed_date is not None

    def test_list_filter_open(self, svc: MedicalCodingService):
        queries = svc.list_coding_queries(status=QueryStatus.OPEN)
        assert all(q.status == QueryStatus.OPEN for q in queries)

    def test_list_filter_answered(self, svc: MedicalCodingService):
        queries = svc.list_coding_queries(status=QueryStatus.ANSWERED)
        assert all(q.status == QueryStatus.ANSWERED for q in queries)

    def test_list_filter_high_priority(self, svc: MedicalCodingService):
        queries = svc.list_coding_queries(priority=CodingPriority.HIGH)
        assert all(q.priority == CodingPriority.HIGH for q in queries)


class TestServiceCodingBatches:
    """Direct service unit tests for coding batches."""

    def test_create_batch(self, svc: MedicalCodingService):
        from app.schemas.medical_coding import CodingBatchCreate
        payload = CodingBatchCreate(
            trial_id=EYLEA_TRIAL,
            dictionary_type=DictionaryType.MEDDRA,
            batch_name="Test Service Batch",
            started_by="tester",
        )
        created = svc.create_coding_batch(payload)
        assert created.id.startswith("CB-")
        assert created.status == "in_progress"
        assert created.total_entries == 0

    def test_get_nonexistent_batch(self, svc: MedicalCodingService):
        assert svc.get_coding_batch("CB-NOPE") is None

    def test_update_nonexistent_batch(self, svc: MedicalCodingService):
        from app.schemas.medical_coding import CodingBatchUpdate
        result = svc.update_coding_batch("CB-NOPE", CodingBatchUpdate(status="completed"))
        assert result is None

    def test_delete_nonexistent_batch(self, svc: MedicalCodingService):
        assert svc.delete_coding_batch("CB-NOPE") is False

    def test_delete_existing_batch(self, svc: MedicalCodingService):
        assert svc.delete_coding_batch("CB-001") is True
        assert svc.get_coding_batch("CB-001") is None

    def test_update_sets_completed_at(self, svc: MedicalCodingService):
        from app.schemas.medical_coding import CodingBatchUpdate
        result = svc.update_coding_batch("CB-001", CodingBatchUpdate(status="completed"))
        assert result is not None
        assert result.completed_at is not None

    def test_list_filter_meddra_batches(self, svc: MedicalCodingService):
        batches = svc.list_coding_batches(dictionary_type=DictionaryType.MEDDRA)
        assert all(b.dictionary_type == DictionaryType.MEDDRA for b in batches)

    def test_list_filter_who_drug_batches(self, svc: MedicalCodingService):
        batches = svc.list_coding_batches(dictionary_type=DictionaryType.WHO_DRUG)
        assert all(b.dictionary_type == DictionaryType.WHO_DRUG for b in batches)

    def test_list_filter_eylea_batches(self, svc: MedicalCodingService):
        batches = svc.list_coding_batches(trial_id=EYLEA_TRIAL)
        assert all(b.trial_id == EYLEA_TRIAL for b in batches)

    def test_list_filter_dupixent_batches(self, svc: MedicalCodingService):
        batches = svc.list_coding_batches(trial_id=DUPIXENT_TRIAL)
        assert all(b.trial_id == DUPIXENT_TRIAL for b in batches)


class TestServiceMetrics:
    """Direct service unit tests for metrics."""

    def test_metrics_totals(self, svc: MedicalCodingService):
        metrics = svc.get_metrics()
        assert metrics.total_dictionary_versions == 12
        assert metrics.active_versions == 6
        assert metrics.total_coding_entries == 15
        assert metrics.total_queries == 10
        assert metrics.total_batches == 10

    def test_metrics_entries_by_status(self, svc: MedicalCodingService):
        metrics = svc.get_metrics()
        assert len(metrics.entries_by_status) > 0
        total = sum(metrics.entries_by_status.values())
        assert total == 15

    def test_metrics_entries_by_dictionary(self, svc: MedicalCodingService):
        metrics = svc.get_metrics()
        assert "meddra" in metrics.entries_by_dictionary
        assert "who_drug" in metrics.entries_by_dictionary

    def test_metrics_auto_code_rate(self, svc: MedicalCodingService):
        metrics = svc.get_metrics()
        assert 0 <= metrics.auto_code_rate_pct <= 100

    def test_metrics_queries_by_status(self, svc: MedicalCodingService):
        metrics = svc.get_metrics()
        assert len(metrics.queries_by_status) > 0
        total = sum(metrics.queries_by_status.values())
        assert total == 10

    def test_metrics_open_queries(self, svc: MedicalCodingService):
        metrics = svc.get_metrics()
        assert metrics.open_queries == 2  # CQ-001 and CQ-003

    def test_metrics_completed_batches(self, svc: MedicalCodingService):
        metrics = svc.get_metrics()
        assert metrics.completed_batches == 5

    def test_metrics_avg_resolution(self, svc: MedicalCodingService):
        metrics = svc.get_metrics()
        assert metrics.avg_query_resolution_days > 0

    def test_metrics_trial_filter_entries(self, svc: MedicalCodingService):
        metrics = svc.get_metrics(trial_id=EYLEA_TRIAL)
        assert metrics.total_coding_entries == 5

    def test_metrics_trial_filter_queries(self, svc: MedicalCodingService):
        metrics = svc.get_metrics(trial_id=EYLEA_TRIAL)
        # EYLEA has CQ-001, CQ-004, CQ-006
        assert metrics.total_queries == 3

    def test_metrics_trial_filter_batches(self, svc: MedicalCodingService):
        metrics = svc.get_metrics(trial_id=EYLEA_TRIAL)
        assert metrics.total_batches == 3

    def test_metrics_empty_trial(self, svc: MedicalCodingService):
        metrics = svc.get_metrics(trial_id="nonexistent-trial")
        assert metrics.total_coding_entries == 0
        assert metrics.total_queries == 0
        assert metrics.total_batches == 0
        assert metrics.auto_code_rate_pct == 0.0
        assert metrics.avg_query_resolution_days == 0.0


# ===========================================================================
# SINGLETON PATTERN
# ===========================================================================


class TestSingleton:
    """Test the singleton pattern for the service."""

    def test_get_returns_same_instance(self):
        svc1 = get_medical_coding_service()
        svc2 = get_medical_coding_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        svc1 = get_medical_coding_service()
        svc2 = reset_medical_coding_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_medical_coding_service()
        svc.delete_coding_entry("CE-001")
        assert svc.get_coding_entry("CE-001") is None

        svc2 = reset_medical_coding_service()
        assert svc2.get_coding_entry("CE-001") is not None


# ===========================================================================
# EDGE CASES AND VALIDATION
# ===========================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.anyio
    async def test_empty_update_dictionary_version(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/dictionary-versions/DV-001",
            json={},
        )
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_empty_update_coding_entry(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/entries/CE-001",
            json={},
        )
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_empty_update_auto_coding_rule(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/auto-coding-rules/ACR-001",
            json={},
        )
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_empty_update_coding_query(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/queries/CQ-001",
            json={},
        )
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_empty_update_coding_batch(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/batches/CB-001",
            json={},
        )
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_entry_missing_required_field(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/entries",
            json={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_dictionary_version_missing_fields(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/dictionary-versions",
            json={"dictionary_type": "meddra"},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_rule_missing_fields(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/auto-coding-rules",
            json={"dictionary_type": "meddra"},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_query_missing_fields(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/queries",
            json={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_batch_missing_fields(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/batches",
            json={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_invalid_dictionary_type_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dictionary-versions", params={"dictionary_type": "invalid"})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_invalid_status_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/entries", params={"status": "invalid"})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_invalid_priority_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/entries", params={"priority": "invalid"})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_invalid_query_status_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/queries", params={"status": "invalid"})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_delete_then_delete_again_version(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/dictionary-versions/DV-012")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/dictionary-versions/DV-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_then_delete_again_entry(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/entries/CE-015")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/entries/CE-015")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_then_delete_again_rule(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/auto-coding-rules/ACR-011")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/auto-coding-rules/ACR-011")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_then_delete_again_query(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/queries/CQ-008")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/queries/CQ-008")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_then_delete_again_batch(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/batches/CB-010")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/batches/CB-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_create_and_delete_entry(self, client: AsyncClient):
        payload = _make_coding_entry_create()
        create_resp = await client.post(f"{API_PREFIX}/entries", json=payload)
        assert create_resp.status_code == 201
        entry_id = create_resp.json()["id"]

        del_resp = await client.delete(f"{API_PREFIX}/entries/{entry_id}")
        assert del_resp.status_code == 204

        get_resp = await client.get(f"{API_PREFIX}/entries/{entry_id}")
        assert get_resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_and_delete_rule(self, client: AsyncClient):
        payload = _make_auto_coding_rule_create()
        create_resp = await client.post(f"{API_PREFIX}/auto-coding-rules", json=payload)
        assert create_resp.status_code == 201
        rule_id = create_resp.json()["id"]

        del_resp = await client.delete(f"{API_PREFIX}/auto-coding-rules/{rule_id}")
        assert del_resp.status_code == 204

        get_resp = await client.get(f"{API_PREFIX}/auto-coding-rules/{rule_id}")
        assert get_resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_and_delete_query(self, client: AsyncClient):
        payload = _make_coding_query_create()
        create_resp = await client.post(f"{API_PREFIX}/queries", json=payload)
        assert create_resp.status_code == 201
        query_id = create_resp.json()["id"]

        del_resp = await client.delete(f"{API_PREFIX}/queries/{query_id}")
        assert del_resp.status_code == 204

        get_resp = await client.get(f"{API_PREFIX}/queries/{query_id}")
        assert get_resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_and_delete_batch(self, client: AsyncClient):
        payload = _make_coding_batch_create()
        create_resp = await client.post(f"{API_PREFIX}/batches", json=payload)
        assert create_resp.status_code == 201
        batch_id = create_resp.json()["id"]

        del_resp = await client.delete(f"{API_PREFIX}/batches/{batch_id}")
        assert del_resp.status_code == 204

        get_resp = await client.get(f"{API_PREFIX}/batches/{batch_id}")
        assert get_resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_entry_meddra_fields(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/entries/CE-004",
            json={
                "meddra_pt": "Headache",
                "meddra_soc": "Nervous system disorders",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["meddra_pt"] == "Headache"
        assert body["meddra_soc"] == "Nervous system disorders"

    @pytest.mark.anyio
    async def test_update_entry_who_drug_fields(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/entries/CE-008",
            json={
                "who_drug_name": "Ibuprofen Updated",
                "who_drug_atc": "M01AE01",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["who_drug_name"] == "Ibuprofen Updated"

    @pytest.mark.anyio
    async def test_create_entry_with_source_form(self, client: AsyncClient):
        payload = _make_coding_entry_create(source_form="AE_LOG", source_field="AETERM")
        resp = await client.post(f"{API_PREFIX}/entries", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["source_form"] == "AE_LOG"
        assert body["source_field"] == "AETERM"

    @pytest.mark.anyio
    async def test_create_rule_with_custom_threshold(self, client: AsyncClient):
        payload = _make_auto_coding_rule_create(confidence_threshold=0.75)
        resp = await client.post(f"{API_PREFIX}/auto-coding-rules", json=payload)
        assert resp.status_code == 201
        assert resp.json()["confidence_threshold"] == 0.75

    @pytest.mark.anyio
    async def test_create_query_with_site_id(self, client: AsyncClient):
        payload = _make_coding_query_create(site_id="SITE-101", assigned_to="site_crc")
        resp = await client.post(f"{API_PREFIX}/queries", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["site_id"] == "SITE-101"
        assert body["assigned_to"] == "site_crc"
