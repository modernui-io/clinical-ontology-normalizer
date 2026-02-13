"""Tests for Post-Marketing Surveillance (PMS).

Covers:
- Seed data verification (safety signals, PSUR records, risk management plans,
  product quality reviews, post-marketing commitments)
- Safety signal CRUD (create, read, update, delete, list, filter by trial/source/status)
- PSUR record CRUD (create, read, update, delete, list, filter by trial/status)
- Risk management plan CRUD (create, read, update, delete, list, filter by trial/category)
- Product quality review CRUD (create, read, update, delete, list, filter by trial)
- Post-marketing commitment CRUD (create, read, update, delete, list, filter by trial/type)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.post_marketing_surveillance import (
    CommitmentType,
    PSURStatus,
    RiskCategory,
    SignalSource,
    SignalStatus,
)
from app.services.post_marketing_surveillance_service import (
    PostMarketingSurveillanceService,
    get_post_marketing_surveillance_service,
    reset_post_marketing_surveillance_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/post-marketing-surveillance"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_post_marketing_surveillance_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> PostMarketingSurveillanceService:
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


def _make_safety_signal_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "signal_name": "Test Signal",
        "signal_source": "spontaneous_report",
        "product_name": "Test Product",
        "event_term": "Test Event",
        "assessed_by": "Dr. Test",
        "case_count": 5,
    }
    defaults.update(overrides)
    return defaults


def _make_psur_record_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "psur_number": 99,
        "reporting_period_start": "2024-01-01T00:00:00Z",
        "reporting_period_end": "2024-06-30T23:59:59Z",
        "product_name": "Test Product",
        "submission_deadline": "2024-09-30T00:00:00Z",
        "regulatory_authority": "FDA",
        "prepared_by": "Dr. Test",
    }
    defaults.update(overrides)
    return defaults


def _make_risk_management_plan_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "plan_version": "1.0",
        "product_name": "Test Product",
        "risk_category": "identified_risk",
        "risk_description": "Test risk description",
        "pharmacovigilance_activity": "Routine pharmacovigilance",
        "managed_by": "Dr. Test",
    }
    defaults.update(overrides)
    return defaults


def _make_product_quality_review_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "product_name": "Test Product",
        "batch_number": "BATCH-TEST-001",
        "review_period": "2024-H1",
        "batches_reviewed": 10,
        "reviewed_by": "Dr. Test",
    }
    defaults.update(overrides)
    return defaults


def _make_post_marketing_commitment_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "commitment_type": "clinical_study",
        "commitment_number": "PMR-TEST-001",
        "description": "Test commitment description",
        "regulatory_authority": "FDA",
        "product_name": "Test Product",
        "due_date": "2025-12-31T00:00:00Z",
        "responsible_party": "Dr. Test",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_safety_signals_count(self, svc: PostMarketingSurveillanceService):
        signals = svc.list_safety_signals()
        assert len(signals) == 12

    def test_seed_safety_signal_ids(self, svc: PostMarketingSurveillanceService):
        signals = svc.list_safety_signals()
        ids = {s.id for s in signals}
        for i in range(1, 13):
            assert f"SIG-{i:03d}" in ids

    def test_seed_safety_signals_sources(self, svc: PostMarketingSurveillanceService):
        signals = svc.list_safety_signals()
        sources = {s.signal_source for s in signals}
        assert SignalSource.SPONTANEOUS_REPORT in sources
        assert SignalSource.CLINICAL_TRIAL in sources
        assert SignalSource.LITERATURE in sources
        assert SignalSource.REGISTRY in sources
        assert SignalSource.SOCIAL_MEDIA in sources
        assert SignalSource.HEALTH_AUTHORITY in sources

    def test_seed_safety_signals_statuses(self, svc: PostMarketingSurveillanceService):
        signals = svc.list_safety_signals()
        statuses = {s.status for s in signals}
        assert SignalStatus.DETECTED in statuses
        assert SignalStatus.UNDER_EVALUATION in statuses
        assert SignalStatus.CONFIRMED in statuses
        assert SignalStatus.REFUTED in statuses
        assert SignalStatus.MONITORING in statuses
        assert SignalStatus.CLOSED in statuses

    def test_seed_psur_records_count(self, svc: PostMarketingSurveillanceService):
        psurs = svc.list_psur_records()
        assert len(psurs) == 12

    def test_seed_psur_record_ids(self, svc: PostMarketingSurveillanceService):
        psurs = svc.list_psur_records()
        ids = {p.id for p in psurs}
        for i in range(1, 13):
            assert f"PSUR-{i:03d}" in ids

    def test_seed_risk_management_plans_count(self, svc: PostMarketingSurveillanceService):
        plans = svc.list_risk_management_plans()
        assert len(plans) == 12

    def test_seed_risk_management_plan_ids(self, svc: PostMarketingSurveillanceService):
        plans = svc.list_risk_management_plans()
        ids = {r.id for r in plans}
        for i in range(1, 13):
            assert f"RMP-{i:03d}" in ids

    def test_seed_product_quality_reviews_count(self, svc: PostMarketingSurveillanceService):
        reviews = svc.list_product_quality_reviews()
        assert len(reviews) == 12

    def test_seed_product_quality_review_ids(self, svc: PostMarketingSurveillanceService):
        reviews = svc.list_product_quality_reviews()
        ids = {q.id for q in reviews}
        for i in range(1, 13):
            assert f"PQR-{i:03d}" in ids

    def test_seed_post_marketing_commitments_count(self, svc: PostMarketingSurveillanceService):
        commitments = svc.list_post_marketing_commitments()
        assert len(commitments) == 12

    def test_seed_post_marketing_commitment_ids(self, svc: PostMarketingSurveillanceService):
        commitments = svc.list_post_marketing_commitments()
        ids = {c.id for c in commitments}
        for i in range(1, 13):
            assert f"PMC-{i:03d}" in ids

    def test_seed_signals_across_trials(self, svc: PostMarketingSurveillanceService):
        eylea = svc.list_safety_signals(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_safety_signals(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_safety_signals(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4

    def test_seed_psurs_across_trials(self, svc: PostMarketingSurveillanceService):
        eylea = svc.list_psur_records(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_psur_records(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_psur_records(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4

    def test_seed_rmps_across_trials(self, svc: PostMarketingSurveillanceService):
        eylea = svc.list_risk_management_plans(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_risk_management_plans(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_risk_management_plans(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4

    def test_seed_pqrs_across_trials(self, svc: PostMarketingSurveillanceService):
        eylea = svc.list_product_quality_reviews(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_product_quality_reviews(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_product_quality_reviews(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4

    def test_seed_commitments_across_trials(self, svc: PostMarketingSurveillanceService):
        eylea = svc.list_post_marketing_commitments(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_post_marketing_commitments(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_post_marketing_commitments(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4


# =====================================================================
# SAFETY SIGNAL CRUD
# =====================================================================


class TestSafetySignalCRUD:
    """Test safety signal create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_safety_signals(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/safety-signals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_safety_signals_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/safety-signals", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_safety_signals_filter_source(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/safety-signals",
            params={"signal_source": "spontaneous_report"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["signal_source"] == "spontaneous_report"

    @pytest.mark.anyio
    async def test_list_safety_signals_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/safety-signals", params={"status": "confirmed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "confirmed"

    @pytest.mark.anyio
    async def test_list_safety_signals_filter_trial_and_source(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/safety-signals",
            params={"trial_id": DUPIXENT_TRIAL, "signal_source": "spontaneous_report"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL
            assert item["signal_source"] == "spontaneous_report"

    @pytest.mark.anyio
    async def test_list_safety_signals_filter_trial_and_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/safety-signals",
            params={"trial_id": LIBTAYO_TRIAL, "status": "confirmed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL
            assert item["status"] == "confirmed"

    @pytest.mark.anyio
    async def test_list_safety_signals_filter_source_clinical_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/safety-signals",
            params={"signal_source": "clinical_trial"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["signal_source"] == "clinical_trial"

    @pytest.mark.anyio
    async def test_list_safety_signals_filter_source_literature(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/safety-signals",
            params={"signal_source": "literature"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["signal_source"] == "literature"

    @pytest.mark.anyio
    async def test_list_safety_signals_filter_source_registry(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/safety-signals",
            params={"signal_source": "registry"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["signal_source"] == "registry"

    @pytest.mark.anyio
    async def test_list_safety_signals_filter_source_social_media(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/safety-signals",
            params={"signal_source": "social_media"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["signal_source"] == "social_media"

    @pytest.mark.anyio
    async def test_list_safety_signals_filter_source_health_authority(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/safety-signals",
            params={"signal_source": "health_authority"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["signal_source"] == "health_authority"

    @pytest.mark.anyio
    async def test_list_safety_signals_filter_status_detected(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/safety-signals", params={"status": "detected"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "detected"

    @pytest.mark.anyio
    async def test_list_safety_signals_filter_status_under_evaluation(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/safety-signals", params={"status": "under_evaluation"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "under_evaluation"

    @pytest.mark.anyio
    async def test_list_safety_signals_filter_status_monitoring(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/safety-signals", params={"status": "monitoring"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "monitoring"

    @pytest.mark.anyio
    async def test_list_safety_signals_filter_status_refuted(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/safety-signals", params={"status": "refuted"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "refuted"

    @pytest.mark.anyio
    async def test_list_safety_signals_filter_status_closed(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/safety-signals", params={"status": "closed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "closed"

    @pytest.mark.anyio
    async def test_get_safety_signal(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/safety-signals/SIG-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SIG-001"
        assert data["signal_name"] == "Endophthalmitis post-injection"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["status"] == "confirmed"
        assert data["signal_source"] == "spontaneous_report"

    @pytest.mark.anyio
    async def test_get_safety_signal_sig005(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/safety-signals/SIG-005")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SIG-005"
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["signal_name"] == "Conjunctivitis"

    @pytest.mark.anyio
    async def test_get_safety_signal_sig009(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/safety-signals/SIG-009")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SIG-009"
        assert data["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_safety_signal_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/safety-signals/SIG-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_safety_signal(self, client: AsyncClient):
        payload = _make_safety_signal_create()
        resp = await client.post(f"{API_PREFIX}/safety-signals", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["signal_name"] == "Test Signal"
        assert data["signal_source"] == "spontaneous_report"
        assert data["status"] == "detected"
        assert data["case_count"] == 5
        assert data["id"].startswith("SIG-")
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_safety_signal_dupixent(self, client: AsyncClient):
        payload = _make_safety_signal_create(
            trial_id=DUPIXENT_TRIAL,
            signal_name="Dupixent Signal",
            signal_source="literature",
        )
        resp = await client.post(f"{API_PREFIX}/safety-signals", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["signal_source"] == "literature"

    @pytest.mark.anyio
    async def test_create_safety_signal_increases_count(self, client: AsyncClient):
        payload = _make_safety_signal_create()
        await client.post(f"{API_PREFIX}/safety-signals", json=payload)
        resp = await client.get(f"{API_PREFIX}/safety-signals")
        data = resp.json()
        assert data["total"] == 13

    @pytest.mark.anyio
    async def test_update_safety_signal(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/safety-signals/SIG-001",
            json={"status": "closed", "case_count": 55},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"
        assert data["case_count"] == 55

    @pytest.mark.anyio
    async def test_update_safety_signal_label_change(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/safety-signals/SIG-002",
            json={"label_change_needed": True, "clinical_significance": "Confirmed serious"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["label_change_needed"] is True
        assert data["clinical_significance"] == "Confirmed serious"

    @pytest.mark.anyio
    async def test_update_safety_signal_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/safety-signals/SIG-003",
            json={"notes": "Updated monitoring notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated monitoring notes"

    @pytest.mark.anyio
    async def test_update_safety_signal_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/safety-signals/SIG-NONEXISTENT",
            json={"status": "closed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_safety_signal(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/safety-signals/SIG-012")
        assert resp.status_code == 204
        # Verify it's gone
        resp2 = await client.get(f"{API_PREFIX}/safety-signals/SIG-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_safety_signal_decreases_count(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/safety-signals/SIG-001")
        resp = await client.get(f"{API_PREFIX}/safety-signals")
        data = resp.json()
        assert data["total"] == 11

    @pytest.mark.anyio
    async def test_delete_safety_signal_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/safety-signals/SIG-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# PSUR RECORD CRUD
# =====================================================================


class TestPSURRecordCRUD:
    """Test PSUR record create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_psur_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/psur-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_psur_records_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/psur-records", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_psur_records_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/psur-records", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_psur_records_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/psur-records", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_psur_records_filter_status_acknowledged(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/psur-records", params={"status": "acknowledged"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "acknowledged"

    @pytest.mark.anyio
    async def test_list_psur_records_filter_status_drafting(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/psur-records", params={"status": "drafting"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "drafting"

    @pytest.mark.anyio
    async def test_list_psur_records_filter_status_planning(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/psur-records", params={"status": "planning"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "planning"

    @pytest.mark.anyio
    async def test_list_psur_records_filter_status_submitted(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/psur-records", params={"status": "submitted"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "submitted"

    @pytest.mark.anyio
    async def test_list_psur_records_filter_status_medical_review(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/psur-records", params={"status": "medical_review"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "medical_review"

    @pytest.mark.anyio
    async def test_list_psur_records_filter_status_data_collection(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/psur-records", params={"status": "data_collection"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "data_collection"

    @pytest.mark.anyio
    async def test_list_psur_records_filter_trial_and_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/psur-records",
            params={"trial_id": EYLEA_TRIAL, "status": "acknowledged"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["status"] == "acknowledged"

    @pytest.mark.anyio
    async def test_get_psur_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/psur-records/PSUR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PSUR-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["psur_number"] == 1
        assert data["status"] == "acknowledged"
        assert data["regulatory_authority"] == "FDA"

    @pytest.mark.anyio
    async def test_get_psur_record_psur005(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/psur-records/PSUR-005")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PSUR-005"
        assert data["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_psur_record_psur009(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/psur-records/PSUR-009")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PSUR-009"
        assert data["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_psur_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/psur-records/PSUR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_psur_record(self, client: AsyncClient):
        payload = _make_psur_record_create()
        resp = await client.post(f"{API_PREFIX}/psur-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["psur_number"] == 99
        assert data["status"] == "planning"
        assert data["regulatory_authority"] == "FDA"
        assert data["id"].startswith("PSUR-")
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_psur_record_dupixent(self, client: AsyncClient):
        payload = _make_psur_record_create(
            trial_id=DUPIXENT_TRIAL,
            psur_number=50,
            regulatory_authority="EMA",
        )
        resp = await client.post(f"{API_PREFIX}/psur-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["regulatory_authority"] == "EMA"

    @pytest.mark.anyio
    async def test_create_psur_record_increases_count(self, client: AsyncClient):
        payload = _make_psur_record_create()
        await client.post(f"{API_PREFIX}/psur-records", json=payload)
        resp = await client.get(f"{API_PREFIX}/psur-records")
        data = resp.json()
        assert data["total"] == 13

    @pytest.mark.anyio
    async def test_update_psur_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/psur-records/PSUR-002",
            json={"status": "medical_review", "total_cases_reviewed": 1200},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "medical_review"
        assert data["total_cases_reviewed"] == 1200

    @pytest.mark.anyio
    async def test_update_psur_record_benefit_risk(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/psur-records/PSUR-010",
            json={"benefit_risk_conclusion": "favorable with observations"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["benefit_risk_conclusion"] == "favorable with observations"

    @pytest.mark.anyio
    async def test_update_psur_record_reviewer(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/psur-records/PSUR-004",
            json={"reviewed_by": "Dr. New Reviewer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reviewed_by"] == "Dr. New Reviewer"

    @pytest.mark.anyio
    async def test_update_psur_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/psur-records/PSUR-NONEXISTENT",
            json={"status": "submitted"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_psur_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/psur-records/PSUR-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/psur-records/PSUR-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_psur_record_decreases_count(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/psur-records/PSUR-001")
        resp = await client.get(f"{API_PREFIX}/psur-records")
        data = resp.json()
        assert data["total"] == 11

    @pytest.mark.anyio
    async def test_delete_psur_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/psur-records/PSUR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# RISK MANAGEMENT PLAN CRUD
# =====================================================================


class TestRiskManagementPlanCRUD:
    """Test risk management plan create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_risk_management_plans(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risk-management-plans")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_risk_management_plans_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/risk-management-plans", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_risk_management_plans_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/risk-management-plans",
            params={"trial_id": DUPIXENT_TRIAL},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_risk_management_plans_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/risk-management-plans",
            params={"trial_id": LIBTAYO_TRIAL},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_risk_management_plans_filter_category_identified_risk(
        self, client: AsyncClient
    ):
        resp = await client.get(
            f"{API_PREFIX}/risk-management-plans",
            params={"risk_category": "identified_risk"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["risk_category"] == "identified_risk"

    @pytest.mark.anyio
    async def test_list_risk_management_plans_filter_category_potential_risk(
        self, client: AsyncClient
    ):
        resp = await client.get(
            f"{API_PREFIX}/risk-management-plans",
            params={"risk_category": "potential_risk"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["risk_category"] == "potential_risk"

    @pytest.mark.anyio
    async def test_list_risk_management_plans_filter_category_missing_information(
        self, client: AsyncClient
    ):
        resp = await client.get(
            f"{API_PREFIX}/risk-management-plans",
            params={"risk_category": "missing_information"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["risk_category"] == "missing_information"

    @pytest.mark.anyio
    async def test_list_risk_management_plans_filter_category_important_identified(
        self, client: AsyncClient
    ):
        resp = await client.get(
            f"{API_PREFIX}/risk-management-plans",
            params={"risk_category": "important_identified"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["risk_category"] == "important_identified"

    @pytest.mark.anyio
    async def test_list_risk_management_plans_filter_category_important_potential(
        self, client: AsyncClient
    ):
        resp = await client.get(
            f"{API_PREFIX}/risk-management-plans",
            params={"risk_category": "important_potential"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["risk_category"] == "important_potential"

    @pytest.mark.anyio
    async def test_list_risk_management_plans_filter_trial_and_category(
        self, client: AsyncClient
    ):
        resp = await client.get(
            f"{API_PREFIX}/risk-management-plans",
            params={"trial_id": EYLEA_TRIAL, "risk_category": "important_identified"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["risk_category"] == "important_identified"

    @pytest.mark.anyio
    async def test_get_risk_management_plan(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risk-management-plans/RMP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RMP-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["risk_category"] == "important_identified"
        assert data["plan_version"] == "3.0"

    @pytest.mark.anyio
    async def test_get_risk_management_plan_rmp005(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risk-management-plans/RMP-005")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RMP-005"
        assert data["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_risk_management_plan_rmp009(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risk-management-plans/RMP-009")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RMP-009"
        assert data["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_risk_management_plan_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risk-management-plans/RMP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_risk_management_plan(self, client: AsyncClient):
        payload = _make_risk_management_plan_create()
        resp = await client.post(f"{API_PREFIX}/risk-management-plans", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["risk_category"] == "identified_risk"
        assert data["plan_version"] == "1.0"
        assert data["milestone_status"] == "on_track"
        assert data["id"].startswith("RMP-")
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_risk_management_plan_potential_risk(self, client: AsyncClient):
        payload = _make_risk_management_plan_create(
            trial_id=DUPIXENT_TRIAL,
            risk_category="potential_risk",
            risk_description="Potential cardiac risk",
        )
        resp = await client.post(f"{API_PREFIX}/risk-management-plans", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["risk_category"] == "potential_risk"
        assert data["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_create_risk_management_plan_increases_count(self, client: AsyncClient):
        payload = _make_risk_management_plan_create()
        await client.post(f"{API_PREFIX}/risk-management-plans", json=payload)
        resp = await client.get(f"{API_PREFIX}/risk-management-plans")
        data = resp.json()
        assert data["total"] == 13

    @pytest.mark.anyio
    async def test_update_risk_management_plan(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/risk-management-plans/RMP-006",
            json={"milestone_status": "completed", "approved_by": "Dr. Head of PV"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["milestone_status"] == "completed"
        assert data["approved_by"] == "Dr. Head of PV"

    @pytest.mark.anyio
    async def test_update_risk_management_plan_minimization_measure(
        self, client: AsyncClient
    ):
        resp = await client.put(
            f"{API_PREFIX}/risk-management-plans/RMP-003",
            json={"risk_minimization_measure": "New minimization measure implemented"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_minimization_measure"] == "New minimization measure implemented"

    @pytest.mark.anyio
    async def test_update_risk_management_plan_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/risk-management-plans/RMP-011",
            json={"notes": "Updated notes for myocarditis plan"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated notes for myocarditis plan"

    @pytest.mark.anyio
    async def test_update_risk_management_plan_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/risk-management-plans/RMP-NONEXISTENT",
            json={"milestone_status": "delayed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_risk_management_plan(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/risk-management-plans/RMP-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/risk-management-plans/RMP-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_risk_management_plan_decreases_count(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/risk-management-plans/RMP-001")
        resp = await client.get(f"{API_PREFIX}/risk-management-plans")
        data = resp.json()
        assert data["total"] == 11

    @pytest.mark.anyio
    async def test_delete_risk_management_plan_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/risk-management-plans/RMP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# PRODUCT QUALITY REVIEW CRUD
# =====================================================================


class TestProductQualityReviewCRUD:
    """Test product quality review create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_product_quality_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/product-quality-reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_product_quality_reviews_filter_trial_eylea(
        self, client: AsyncClient
    ):
        resp = await client.get(
            f"{API_PREFIX}/product-quality-reviews", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_product_quality_reviews_filter_trial_dupixent(
        self, client: AsyncClient
    ):
        resp = await client.get(
            f"{API_PREFIX}/product-quality-reviews",
            params={"trial_id": DUPIXENT_TRIAL},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_product_quality_reviews_filter_trial_libtayo(
        self, client: AsyncClient
    ):
        resp = await client.get(
            f"{API_PREFIX}/product-quality-reviews",
            params={"trial_id": LIBTAYO_TRIAL},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_product_quality_review(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/product-quality-reviews/PQR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PQR-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["overall_compliance"] == "compliant"
        assert data["batches_reviewed"] == 24

    @pytest.mark.anyio
    async def test_get_product_quality_review_pqr005(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/product-quality-reviews/PQR-005")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PQR-005"
        assert data["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_product_quality_review_pqr009(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/product-quality-reviews/PQR-009")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PQR-009"
        assert data["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_product_quality_review_non_compliant(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/product-quality-reviews/PQR-010")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_compliance"] == "non_compliant"
        assert data["out_of_spec_events"] == 1
        assert data["capa_required"] is True

    @pytest.mark.anyio
    async def test_get_product_quality_review_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/product-quality-reviews/PQR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_product_quality_review(self, client: AsyncClient):
        payload = _make_product_quality_review_create()
        resp = await client.post(f"{API_PREFIX}/product-quality-reviews", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["batch_number"] == "BATCH-TEST-001"
        assert data["batches_reviewed"] == 10
        assert data["overall_compliance"] == "compliant"
        assert data["id"].startswith("PQR-")
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_product_quality_review_dupixent(self, client: AsyncClient):
        payload = _make_product_quality_review_create(
            trial_id=DUPIXENT_TRIAL,
            batch_number="DUP-TEST-001",
            review_period="2025-Q2",
        )
        resp = await client.post(f"{API_PREFIX}/product-quality-reviews", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["batch_number"] == "DUP-TEST-001"

    @pytest.mark.anyio
    async def test_create_product_quality_review_increases_count(self, client: AsyncClient):
        payload = _make_product_quality_review_create()
        await client.post(f"{API_PREFIX}/product-quality-reviews", json=payload)
        resp = await client.get(f"{API_PREFIX}/product-quality-reviews")
        data = resp.json()
        assert data["total"] == 13

    @pytest.mark.anyio
    async def test_update_product_quality_review(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/product-quality-reviews/PQR-003",
            json={
                "overall_compliance": "compliant_with_observations",
                "capa_required": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_compliance"] == "compliant_with_observations"
        assert data["capa_required"] is True

    @pytest.mark.anyio
    async def test_update_product_quality_review_trend_analysis(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/product-quality-reviews/PQR-008",
            json={"trend_analysis_performed": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["trend_analysis_performed"] is True

    @pytest.mark.anyio
    async def test_update_product_quality_review_approver(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/product-quality-reviews/PQR-002",
            json={"approved_by": "Dr. QA Director"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approved_by"] == "Dr. QA Director"

    @pytest.mark.anyio
    async def test_update_product_quality_review_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/product-quality-reviews/PQR-012",
            json={"notes": "Updated review notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated review notes"

    @pytest.mark.anyio
    async def test_update_product_quality_review_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/product-quality-reviews/PQR-NONEXISTENT",
            json={"overall_compliance": "non_compliant"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_product_quality_review(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/product-quality-reviews/PQR-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/product-quality-reviews/PQR-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_product_quality_review_decreases_count(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/product-quality-reviews/PQR-001")
        resp = await client.get(f"{API_PREFIX}/product-quality-reviews")
        data = resp.json()
        assert data["total"] == 11

    @pytest.mark.anyio
    async def test_delete_product_quality_review_not_found(self, client: AsyncClient):
        resp = await client.delete(
            f"{API_PREFIX}/product-quality-reviews/PQR-NONEXISTENT"
        )
        assert resp.status_code == 404


# =====================================================================
# POST-MARKETING COMMITMENT CRUD
# =====================================================================


class TestPostMarketingCommitmentCRUD:
    """Test post-marketing commitment create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_commitments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/commitments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_commitments_filter_trial_eylea(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/commitments", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_commitments_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/commitments", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_commitments_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/commitments", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_commitments_filter_type_clinical_study(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/commitments",
            params={"commitment_type": "clinical_study"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["commitment_type"] == "clinical_study"

    @pytest.mark.anyio
    async def test_list_commitments_filter_type_safety_study(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/commitments",
            params={"commitment_type": "safety_study"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["commitment_type"] == "safety_study"

    @pytest.mark.anyio
    async def test_list_commitments_filter_type_label_update(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/commitments",
            params={"commitment_type": "label_update"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["commitment_type"] == "label_update"

    @pytest.mark.anyio
    async def test_list_commitments_filter_type_registry(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/commitments",
            params={"commitment_type": "registry"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["commitment_type"] == "registry"

    @pytest.mark.anyio
    async def test_list_commitments_filter_type_rems(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/commitments",
            params={"commitment_type": "rems"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["commitment_type"] == "rems"

    @pytest.mark.anyio
    async def test_list_commitments_filter_type_effectiveness_study(
        self, client: AsyncClient
    ):
        resp = await client.get(
            f"{API_PREFIX}/commitments",
            params={"commitment_type": "effectiveness_study"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["commitment_type"] == "effectiveness_study"

    @pytest.mark.anyio
    async def test_list_commitments_filter_trial_and_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/commitments",
            params={"trial_id": LIBTAYO_TRIAL, "commitment_type": "safety_study"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL
            assert item["commitment_type"] == "safety_study"

    @pytest.mark.anyio
    async def test_get_commitment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/commitments/PMC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PMC-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["commitment_type"] == "safety_study"
        assert data["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_get_commitment_pmc002_completed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/commitments/PMC-002")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PMC-002"
        assert data["status"] == "completed"
        assert data["progress_pct"] == 100.0
        assert data["milestone_met"] is True

    @pytest.mark.anyio
    async def test_get_commitment_pmc005(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/commitments/PMC-005")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PMC-005"
        assert data["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_commitment_pmc009(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/commitments/PMC-009")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PMC-009"
        assert data["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_commitment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/commitments/PMC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_commitment(self, client: AsyncClient):
        payload = _make_post_marketing_commitment_create()
        resp = await client.post(f"{API_PREFIX}/commitments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["commitment_type"] == "clinical_study"
        assert data["status"] == "open"
        assert data["progress_pct"] == 0.0
        assert data["id"].startswith("PMC-")
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["regulatory_authority"] == "FDA"

    @pytest.mark.anyio
    async def test_create_commitment_rems(self, client: AsyncClient):
        payload = _make_post_marketing_commitment_create(
            trial_id=LIBTAYO_TRIAL,
            commitment_type="rems",
            commitment_number="PMR-TEST-REMS",
            description="REMS commitment",
        )
        resp = await client.post(f"{API_PREFIX}/commitments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["commitment_type"] == "rems"
        assert data["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_create_commitment_increases_count(self, client: AsyncClient):
        payload = _make_post_marketing_commitment_create()
        await client.post(f"{API_PREFIX}/commitments", json=payload)
        resp = await client.get(f"{API_PREFIX}/commitments")
        data = resp.json()
        assert data["total"] == 13

    @pytest.mark.anyio
    async def test_update_commitment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/commitments/PMC-001",
            json={"status": "completed", "progress_pct": 100.0, "milestone_met": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["progress_pct"] == 100.0
        assert data["milestone_met"] is True

    @pytest.mark.anyio
    async def test_update_commitment_progress(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/commitments/PMC-006",
            json={"progress_pct": 45.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["progress_pct"] == 45.0

    @pytest.mark.anyio
    async def test_update_commitment_annual_report(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/commitments/PMC-004",
            json={"annual_report_included": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["annual_report_included"] is True

    @pytest.mark.anyio
    async def test_update_commitment_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/commitments/PMC-010",
            json={"notes": "Updated commitment notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated commitment notes"

    @pytest.mark.anyio
    async def test_update_commitment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/commitments/PMC-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_commitment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/commitments/PMC-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/commitments/PMC-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_commitment_decreases_count(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/commitments/PMC-001")
        resp = await client.get(f"{API_PREFIX}/commitments")
        data = resp.json()
        assert data["total"] == 11

    @pytest.mark.anyio
    async def test_delete_commitment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/commitments/PMC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test PMS metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_signals"] == 12
        assert data["total_psurs"] == 12
        assert data["total_risk_plans"] == 12
        assert data["total_quality_reviews"] == 12
        assert data["total_commitments"] == 12
        assert data["confirmed_signals"] > 0
        assert data["open_commitments"] > 0
        assert data["psurs_pending_submission"] > 0
        assert data["out_of_spec_reviews"] > 0

    @pytest.mark.anyio
    async def test_get_metrics_filter_trial_eylea(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_signals"] == 4
        assert data["total_psurs"] == 4
        assert data["total_risk_plans"] == 4
        assert data["total_quality_reviews"] == 4
        assert data["total_commitments"] == 4

    @pytest.mark.anyio
    async def test_get_metrics_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/metrics", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_signals"] == 4
        assert data["total_psurs"] == 4
        assert data["total_risk_plans"] == 4
        assert data["total_quality_reviews"] == 4
        assert data["total_commitments"] == 4

    @pytest.mark.anyio
    async def test_get_metrics_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/metrics", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_signals"] == 4
        assert data["total_psurs"] == 4
        assert data["total_risk_plans"] == 4
        assert data["total_quality_reviews"] == 4
        assert data["total_commitments"] == 4

    def test_metrics_signals_by_source(self, svc: PostMarketingSurveillanceService):
        metrics = svc.get_metrics()
        total_by_source = sum(metrics.signals_by_source.values())
        assert total_by_source == metrics.total_signals

    def test_metrics_signals_by_status(self, svc: PostMarketingSurveillanceService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.signals_by_status.values())
        assert total_by_status == metrics.total_signals

    def test_metrics_confirmed_signals(self, svc: PostMarketingSurveillanceService):
        metrics = svc.get_metrics()
        confirmed_list = svc.list_safety_signals(status=SignalStatus.CONFIRMED)
        assert metrics.confirmed_signals == len(confirmed_list)

    def test_metrics_psurs_by_status(self, svc: PostMarketingSurveillanceService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.psurs_by_status.values())
        assert total_by_status == metrics.total_psurs

    def test_metrics_psurs_pending_submission(self, svc: PostMarketingSurveillanceService):
        metrics = svc.get_metrics()
        psurs = svc.list_psur_records()
        pending = sum(
            1
            for p in psurs
            if p.status not in (PSURStatus.SUBMITTED, PSURStatus.ACKNOWLEDGED)
        )
        assert metrics.psurs_pending_submission == pending

    def test_metrics_risks_by_category(self, svc: PostMarketingSurveillanceService):
        metrics = svc.get_metrics()
        total_by_category = sum(metrics.risks_by_category.values())
        assert total_by_category == metrics.total_risk_plans

    def test_metrics_out_of_spec_reviews(self, svc: PostMarketingSurveillanceService):
        metrics = svc.get_metrics()
        reviews = svc.list_product_quality_reviews()
        oos = sum(1 for q in reviews if q.out_of_spec_events > 0)
        assert metrics.out_of_spec_reviews == oos

    def test_metrics_commitments_by_type(self, svc: PostMarketingSurveillanceService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.commitments_by_type.values())
        assert total_by_type == metrics.total_commitments

    def test_metrics_open_commitments(self, svc: PostMarketingSurveillanceService):
        metrics = svc.get_metrics()
        commitments = svc.list_post_marketing_commitments()
        open_count = sum(1 for c in commitments if c.status in ("open", "in_progress"))
        assert metrics.open_commitments == open_count

    def test_metrics_trial_filter_reduces_counts(
        self, svc: PostMarketingSurveillanceService
    ):
        full_metrics = svc.get_metrics()
        trial_metrics = svc.get_metrics(trial_id=EYLEA_TRIAL)
        assert trial_metrics.total_signals < full_metrics.total_signals
        assert trial_metrics.total_psurs < full_metrics.total_psurs
        assert trial_metrics.total_risk_plans < full_metrics.total_risk_plans

    def test_metrics_nonexistent_trial_empty(
        self, svc: PostMarketingSurveillanceService
    ):
        metrics = svc.get_metrics(trial_id="nonexistent-trial-id")
        assert metrics.total_signals == 0
        assert metrics.total_psurs == 0
        assert metrics.total_risk_plans == 0
        assert metrics.total_quality_reviews == 0
        assert metrics.total_commitments == 0


# =====================================================================
# SINGLETON
# =====================================================================


class TestSingleton:
    """Verify get/reset singleton behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_post_marketing_surveillance_service()
        svc2 = get_post_marketing_surveillance_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_post_marketing_surveillance_service()
        svc2 = reset_post_marketing_surveillance_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_post_marketing_surveillance_service()
        # Delete a signal
        svc.delete_safety_signal("SIG-001")
        assert svc.get_safety_signal("SIG-001") is None
        # Reset should bring it back
        svc2 = reset_post_marketing_surveillance_service()
        assert svc2.get_safety_signal("SIG-001") is not None

    def test_reset_reseeds_psurs(self):
        svc = get_post_marketing_surveillance_service()
        svc.delete_psur_record("PSUR-001")
        assert svc.get_psur_record("PSUR-001") is None
        svc2 = reset_post_marketing_surveillance_service()
        assert svc2.get_psur_record("PSUR-001") is not None

    def test_reset_reseeds_risk_plans(self):
        svc = get_post_marketing_surveillance_service()
        svc.delete_risk_management_plan("RMP-001")
        assert svc.get_risk_management_plan("RMP-001") is None
        svc2 = reset_post_marketing_surveillance_service()
        assert svc2.get_risk_management_plan("RMP-001") is not None

    def test_reset_reseeds_quality_reviews(self):
        svc = get_post_marketing_surveillance_service()
        svc.delete_product_quality_review("PQR-001")
        assert svc.get_product_quality_review("PQR-001") is None
        svc2 = reset_post_marketing_surveillance_service()
        assert svc2.get_product_quality_review("PQR-001") is not None

    def test_reset_reseeds_commitments(self):
        svc = get_post_marketing_surveillance_service()
        svc.delete_post_marketing_commitment("PMC-001")
        assert svc.get_post_marketing_commitment("PMC-001") is None
        svc2 = reset_post_marketing_surveillance_service()
        assert svc2.get_post_marketing_commitment("PMC-001") is not None

    def test_get_after_reset_returns_new_instance(self):
        original = get_post_marketing_surveillance_service()
        reset_post_marketing_surveillance_service()
        new = get_post_marketing_surveillance_service()
        assert original is not new


# =====================================================================
# SERVICE LAYER DIRECT TESTS
# =====================================================================


class TestServiceLayerDirect:
    """Direct service layer tests for completeness."""

    def test_list_safety_signals_no_filters(self, svc: PostMarketingSurveillanceService):
        signals = svc.list_safety_signals()
        assert len(signals) == 12

    def test_list_safety_signals_filter_source_enum(
        self, svc: PostMarketingSurveillanceService
    ):
        signals = svc.list_safety_signals(signal_source=SignalSource.SPONTANEOUS_REPORT)
        assert len(signals) > 0
        for s in signals:
            assert s.signal_source == SignalSource.SPONTANEOUS_REPORT

    def test_list_safety_signals_filter_status_enum(
        self, svc: PostMarketingSurveillanceService
    ):
        signals = svc.list_safety_signals(status=SignalStatus.CONFIRMED)
        assert len(signals) > 0
        for s in signals:
            assert s.status == SignalStatus.CONFIRMED

    def test_list_psur_records_filter_status_enum(
        self, svc: PostMarketingSurveillanceService
    ):
        psurs = svc.list_psur_records(status=PSURStatus.ACKNOWLEDGED)
        assert len(psurs) > 0
        for p in psurs:
            assert p.status == PSURStatus.ACKNOWLEDGED

    def test_list_risk_management_plans_filter_category_enum(
        self, svc: PostMarketingSurveillanceService
    ):
        plans = svc.list_risk_management_plans(risk_category=RiskCategory.MISSING_INFORMATION)
        assert len(plans) > 0
        for p in plans:
            assert p.risk_category == RiskCategory.MISSING_INFORMATION

    def test_list_commitments_filter_type_enum(
        self, svc: PostMarketingSurveillanceService
    ):
        commitments = svc.list_post_marketing_commitments(
            commitment_type=CommitmentType.REMS
        )
        assert len(commitments) > 0
        for c in commitments:
            assert c.commitment_type == CommitmentType.REMS

    def test_safety_signal_sorted_by_detection_date_desc(
        self, svc: PostMarketingSurveillanceService
    ):
        signals = svc.list_safety_signals()
        dates = [s.detection_date for s in signals]
        assert dates == sorted(dates, reverse=True)

    def test_psur_records_sorted_by_deadline_desc(
        self, svc: PostMarketingSurveillanceService
    ):
        psurs = svc.list_psur_records()
        deadlines = [p.submission_deadline for p in psurs]
        assert deadlines == sorted(deadlines, reverse=True)

    def test_risk_plans_sorted_by_effective_date_desc(
        self, svc: PostMarketingSurveillanceService
    ):
        plans = svc.list_risk_management_plans()
        dates = [r.effective_date for r in plans]
        assert dates == sorted(dates, reverse=True)

    def test_quality_reviews_sorted_by_review_date_desc(
        self, svc: PostMarketingSurveillanceService
    ):
        reviews = svc.list_product_quality_reviews()
        dates = [q.review_date for q in reviews]
        assert dates == sorted(dates, reverse=True)

    def test_commitments_sorted_by_due_date_desc(
        self, svc: PostMarketingSurveillanceService
    ):
        commitments = svc.list_post_marketing_commitments()
        dates = [c.due_date for c in commitments]
        assert dates == sorted(dates, reverse=True)

    def test_create_signal_sets_detected_status(
        self, svc: PostMarketingSurveillanceService
    ):
        from app.schemas.post_marketing_surveillance import SafetySignalTrackerCreate

        payload = SafetySignalTrackerCreate(
            trial_id=EYLEA_TRIAL,
            signal_name="Test",
            signal_source=SignalSource.LITERATURE,
            product_name="Test",
            event_term="Test",
            assessed_by="Tester",
            case_count=3,
        )
        signal = svc.create_safety_signal(payload)
        assert signal.status == SignalStatus.DETECTED

    def test_create_psur_sets_planning_status(
        self, svc: PostMarketingSurveillanceService
    ):
        from datetime import datetime, timezone

        from app.schemas.post_marketing_surveillance import PSURRecordCreate

        now = datetime.now(timezone.utc)
        payload = PSURRecordCreate(
            trial_id=EYLEA_TRIAL,
            psur_number=100,
            product_name="Test",
            regulatory_authority="FDA",
            submission_deadline=now,
            prepared_by="Tester",
            reporting_period_start=now,
            reporting_period_end=now,
        )
        psur = svc.create_psur_record(payload)
        assert psur.status == PSURStatus.PLANNING

    def test_create_commitment_sets_open_status(
        self, svc: PostMarketingSurveillanceService
    ):
        from datetime import datetime, timezone

        from app.schemas.post_marketing_surveillance import PostMarketingCommitmentCreate

        now = datetime.now(timezone.utc)
        payload = PostMarketingCommitmentCreate(
            trial_id=EYLEA_TRIAL,
            commitment_type=CommitmentType.CLINICAL_STUDY,
            commitment_number="TEST-001",
            description="Test",
            regulatory_authority="FDA",
            product_name="Test",
            due_date=now,
            responsible_party="Tester",
        )
        commitment = svc.create_post_marketing_commitment(payload)
        assert commitment.status == "open"
        assert commitment.progress_pct == 0.0

    def test_create_risk_plan_sets_on_track(
        self, svc: PostMarketingSurveillanceService
    ):
        from app.schemas.post_marketing_surveillance import RiskManagementPlanCreate

        payload = RiskManagementPlanCreate(
            trial_id=EYLEA_TRIAL,
            plan_version="1.0",
            product_name="Test",
            risk_category=RiskCategory.IDENTIFIED_RISK,
            risk_description="Test",
            pharmacovigilance_activity="Test",
            managed_by="Tester",
        )
        plan = svc.create_risk_management_plan(payload)
        assert plan.milestone_status == "on_track"

    def test_create_quality_review_defaults(
        self, svc: PostMarketingSurveillanceService
    ):
        from app.schemas.post_marketing_surveillance import ProductQualityReviewCreate

        payload = ProductQualityReviewCreate(
            trial_id=EYLEA_TRIAL,
            product_name="Test",
            batch_number="B-001",
            review_period="2025-Q1",
            reviewed_by="Tester",
            batches_reviewed=5,
        )
        review = svc.create_product_quality_review(payload)
        assert review.overall_compliance == "compliant"
        assert review.capa_required is False
        assert review.out_of_spec_events == 0
        assert review.batches_reviewed == 5

    def test_update_safety_signal_returns_none_missing(
        self, svc: PostMarketingSurveillanceService
    ):
        from app.schemas.post_marketing_surveillance import SafetySignalTrackerUpdate

        result = svc.update_safety_signal(
            "NONEXISTENT", SafetySignalTrackerUpdate(notes="test")
        )
        assert result is None

    def test_update_psur_returns_none_missing(
        self, svc: PostMarketingSurveillanceService
    ):
        from app.schemas.post_marketing_surveillance import PSURRecordUpdate

        result = svc.update_psur_record("NONEXISTENT", PSURRecordUpdate(notes="test"))
        assert result is None

    def test_update_risk_plan_returns_none_missing(
        self, svc: PostMarketingSurveillanceService
    ):
        from app.schemas.post_marketing_surveillance import RiskManagementPlanUpdate

        result = svc.update_risk_management_plan(
            "NONEXISTENT", RiskManagementPlanUpdate(notes="test")
        )
        assert result is None

    def test_update_quality_review_returns_none_missing(
        self, svc: PostMarketingSurveillanceService
    ):
        from app.schemas.post_marketing_surveillance import ProductQualityReviewUpdate

        result = svc.update_product_quality_review(
            "NONEXISTENT", ProductQualityReviewUpdate(notes="test")
        )
        assert result is None

    def test_update_commitment_returns_none_missing(
        self, svc: PostMarketingSurveillanceService
    ):
        from app.schemas.post_marketing_surveillance import PostMarketingCommitmentUpdate

        result = svc.update_post_marketing_commitment(
            "NONEXISTENT", PostMarketingCommitmentUpdate(notes="test")
        )
        assert result is None

    def test_delete_safety_signal_returns_false_missing(
        self, svc: PostMarketingSurveillanceService
    ):
        assert svc.delete_safety_signal("NONEXISTENT") is False

    def test_delete_psur_returns_false_missing(
        self, svc: PostMarketingSurveillanceService
    ):
        assert svc.delete_psur_record("NONEXISTENT") is False

    def test_delete_risk_plan_returns_false_missing(
        self, svc: PostMarketingSurveillanceService
    ):
        assert svc.delete_risk_management_plan("NONEXISTENT") is False

    def test_delete_quality_review_returns_false_missing(
        self, svc: PostMarketingSurveillanceService
    ):
        assert svc.delete_product_quality_review("NONEXISTENT") is False

    def test_delete_commitment_returns_false_missing(
        self, svc: PostMarketingSurveillanceService
    ):
        assert svc.delete_post_marketing_commitment("NONEXISTENT") is False

    def test_get_safety_signal_returns_none_missing(
        self, svc: PostMarketingSurveillanceService
    ):
        assert svc.get_safety_signal("NONEXISTENT") is None

    def test_get_psur_record_returns_none_missing(
        self, svc: PostMarketingSurveillanceService
    ):
        assert svc.get_psur_record("NONEXISTENT") is None

    def test_get_risk_plan_returns_none_missing(
        self, svc: PostMarketingSurveillanceService
    ):
        assert svc.get_risk_management_plan("NONEXISTENT") is None

    def test_get_quality_review_returns_none_missing(
        self, svc: PostMarketingSurveillanceService
    ):
        assert svc.get_product_quality_review("NONEXISTENT") is None

    def test_get_commitment_returns_none_missing(
        self, svc: PostMarketingSurveillanceService
    ):
        assert svc.get_post_marketing_commitment("NONEXISTENT") is None

    def test_signal_fields_populated(self, svc: PostMarketingSurveillanceService):
        signal = svc.get_safety_signal("SIG-001")
        assert signal is not None
        assert signal.product_name == "EYLEA (aflibercept)"
        assert signal.event_term == "Endophthalmitis"
        assert signal.case_count == 47
        assert signal.regulatory_impact is True
        assert signal.label_change_needed is True

    def test_psur_fields_populated(self, svc: PostMarketingSurveillanceService):
        psur = svc.get_psur_record("PSUR-001")
        assert psur is not None
        assert psur.product_name == "EYLEA (aflibercept)"
        assert psur.total_cases_reviewed == 1245
        assert psur.benefit_risk_conclusion == "favorable"

    def test_commitment_completed_has_milestone_met(
        self, svc: PostMarketingSurveillanceService
    ):
        commitment = svc.get_post_marketing_commitment("PMC-002")
        assert commitment is not None
        assert commitment.status == "completed"
        assert commitment.milestone_met is True
        assert commitment.progress_pct == 100.0
