"""Tests for Concomitant Medication Tracking (CMT-TRK).

Covers:
- Seed data verification (medication records, drug interaction checks,
  prohibited medication alerts, medication reconciliations)
- Medication record CRUD (create, read, update, delete, list, filter by trial/status/subject)
- Drug interaction check CRUD (create, read, update, delete, list, filter by trial/severity/subject)
- Prohibited medication alert CRUD (create, read, update, delete, list, filter by trial/priority/status)
- Medication reconciliation CRUD (create, read, update, delete, list, filter by trial/outcome/subject)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.concomitant_medication import (
    AlertPriority,
    AlertStatus,
    InteractionSeverity,
    MedicationStatus,
    ReconciliationOutcome,
)
from app.services.concomitant_medication_service import (
    ConcomitantMedicationService,
    get_concomitant_medication_service,
    reset_concomitant_medication_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/concomitant-medication"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_concomitant_medication_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ConcomitantMedicationService:
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


def _make_medication_record_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-TEST-001",
        "site_id": "SITE-TEST-001",
        "medication_name": "Test Medication",
        "indication": "Test Indication",
        "dose": "100",
        "dose_unit": "mg",
        "frequency": "Once daily",
        "route": "Oral",
        "start_date": "2026-01-15T09:00:00Z",
        "recorded_by": "Test CRC",
    }
    defaults.update(overrides)
    return defaults


def _make_interaction_check_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-TEST-001",
        "medication_record_id": "MED-001",
        "study_drug_name": "Aflibercept (Eylea)",
        "interaction_description": "No known interaction.",
        "checked_date": "2026-01-15T10:00:00Z",
        "checked_by": "Clinical Pharmacist",
        "interaction_severity": "none_known",
    }
    defaults.update(overrides)
    return defaults


def _make_prohibited_alert_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-TEST-001",
        "site_id": "SITE-TEST-001",
        "medication_name": "Prohibited Drug X",
        "prohibition_reason": "Protocol Section 4.2 prohibits concurrent use.",
        "detected_date": "2026-01-15T11:00:00Z",
        "alert_priority": "high",
    }
    defaults.update(overrides)
    return defaults


def _make_reconciliation_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-TEST-001",
        "site_id": "SITE-TEST-001",
        "reconciliation_date": "2026-01-15T12:00:00Z",
        "performed_by": "Test CRC",
        "visit_number": 1,
    }
    defaults.update(overrides)
    return defaults


# ===================================================================
# SEED DATA VERIFICATION
# ===================================================================


class TestSeedData:
    """Verify all 4 entity types are seeded with 12 records each."""

    @pytest.mark.anyio
    async def test_seed_medication_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/medication-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_seed_drug_interaction_checks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-interaction-checks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_prohibited_medication_alerts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/prohibited-medication-alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_medication_reconciliations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/medication-reconciliations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12


# ===================================================================
# MEDICATION RECORDS CRUD
# ===================================================================


class TestMedicationRecordCRUD:
    @pytest.mark.anyio
    async def test_list_medication_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/medication-records")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_medication_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/medication-records/MED-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MED-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_medication_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/medication-records/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_medication_record(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/medication-records", json=_make_medication_record_create()
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("MED-")
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["medication_name"] == "Test Medication"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/medication-records")
        before = resp1.json()["total"]
        await client.post(
            f"{API_PREFIX}/medication-records", json=_make_medication_record_create()
        )
        resp2 = await client.get(f"{API_PREFIX}/medication-records")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_medication_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/medication-records/MED-001",
            json={"medication_status": "completed", "notes": "Updated note"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["medication_status"] == "completed"
        assert data["notes"] == "Updated note"

    @pytest.mark.anyio
    async def test_update_medication_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/medication-records/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_medication_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/medication-records/MED-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/medication-records/MED-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_medication_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/medication-records/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/medication-records", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_medication_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/medication-records", params={"medication_status": "ongoing"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["medication_status"] == "ongoing"

    @pytest.mark.anyio
    async def test_filter_by_subject_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/medication-records", params={"subject_id": "SUBJ-E001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["subject_id"] == "SUBJ-E001"


# ===================================================================
# DRUG INTERACTION CHECKS CRUD
# ===================================================================


class TestDrugInteractionCheckCRUD:
    @pytest.mark.anyio
    async def test_list_drug_interaction_checks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-interaction-checks")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_drug_interaction_check(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-interaction-checks/DIC-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "DIC-001"

    @pytest.mark.anyio
    async def test_get_drug_interaction_check_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-interaction-checks/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_drug_interaction_check(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/drug-interaction-checks",
            json=_make_interaction_check_create(),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("DIC-")
        assert data["study_drug_name"] == "Aflibercept (Eylea)"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/drug-interaction-checks")
        before = resp1.json()["total"]
        await client.post(
            f"{API_PREFIX}/drug-interaction-checks",
            json=_make_interaction_check_create(),
        )
        resp2 = await client.get(f"{API_PREFIX}/drug-interaction-checks")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_drug_interaction_check(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/drug-interaction-checks/DIC-001",
            json={"clinical_significance": "Updated significance", "notes": "Updated note"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["clinical_significance"] == "Updated significance"
        assert data["notes"] == "Updated note"

    @pytest.mark.anyio
    async def test_update_drug_interaction_check_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/drug-interaction-checks/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_drug_interaction_check(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/drug-interaction-checks/DIC-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/drug-interaction-checks/DIC-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_drug_interaction_check_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/drug-interaction-checks/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_interaction_severity(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/drug-interaction-checks",
            params={"interaction_severity": "none_known"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["interaction_severity"] == "none_known"

    @pytest.mark.anyio
    async def test_filter_by_subject_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/drug-interaction-checks",
            params={"subject_id": "SUBJ-E001"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["subject_id"] == "SUBJ-E001"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/drug-interaction-checks",
            params={"trial_id": DUPIXENT_TRIAL},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL


# ===================================================================
# PROHIBITED MEDICATION ALERTS CRUD
# ===================================================================


class TestProhibitedMedicationAlertCRUD:
    @pytest.mark.anyio
    async def test_list_prohibited_medication_alerts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/prohibited-medication-alerts")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_prohibited_medication_alert(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/prohibited-medication-alerts/PMA-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "PMA-001"

    @pytest.mark.anyio
    async def test_get_prohibited_medication_alert_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/prohibited-medication-alerts/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_prohibited_medication_alert(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/prohibited-medication-alerts",
            json=_make_prohibited_alert_create(),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("PMA-")
        assert data["medication_name"] == "Prohibited Drug X"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/prohibited-medication-alerts")
        before = resp1.json()["total"]
        await client.post(
            f"{API_PREFIX}/prohibited-medication-alerts",
            json=_make_prohibited_alert_create(),
        )
        resp2 = await client.get(f"{API_PREFIX}/prohibited-medication-alerts")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_prohibited_medication_alert(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/prohibited-medication-alerts/PMA-001",
            json={"alert_status": "resolved", "notes": "Issue resolved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["alert_status"] == "resolved"
        assert data["notes"] == "Issue resolved"

    @pytest.mark.anyio
    async def test_update_prohibited_medication_alert_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/prohibited-medication-alerts/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_prohibited_medication_alert(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/prohibited-medication-alerts/PMA-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/prohibited-medication-alerts/PMA-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_prohibited_medication_alert_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/prohibited-medication-alerts/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_alert_priority(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/prohibited-medication-alerts",
            params={"alert_priority": "critical"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["alert_priority"] == "critical"

    @pytest.mark.anyio
    async def test_filter_by_alert_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/prohibited-medication-alerts",
            params={"alert_status": "active"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["alert_status"] == "active"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/prohibited-medication-alerts",
            params={"trial_id": LIBTAYO_TRIAL},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL


# ===================================================================
# MEDICATION RECONCILIATIONS CRUD
# ===================================================================


class TestMedicationReconciliationCRUD:
    @pytest.mark.anyio
    async def test_list_medication_reconciliations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/medication-reconciliations")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_medication_reconciliation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/medication-reconciliations/MRC-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "MRC-001"

    @pytest.mark.anyio
    async def test_get_medication_reconciliation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/medication-reconciliations/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_medication_reconciliation(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/medication-reconciliations",
            json=_make_reconciliation_create(),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("MRC-")
        assert data["performed_by"] == "Test CRC"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/medication-reconciliations")
        before = resp1.json()["total"]
        await client.post(
            f"{API_PREFIX}/medication-reconciliations",
            json=_make_reconciliation_create(),
        )
        resp2 = await client.get(f"{API_PREFIX}/medication-reconciliations")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_medication_reconciliation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/medication-reconciliations/MRC-001",
            json={"reconciliation_outcome": "reconciled", "notes": "All clear"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reconciliation_outcome"] == "reconciled"
        assert data["notes"] == "All clear"

    @pytest.mark.anyio
    async def test_update_medication_reconciliation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/medication-reconciliations/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_medication_reconciliation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/medication-reconciliations/MRC-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/medication-reconciliations/MRC-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_medication_reconciliation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/medication-reconciliations/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_reconciliation_outcome(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/medication-reconciliations",
            params={"reconciliation_outcome": "reconciled"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["reconciliation_outcome"] == "reconciled"

    @pytest.mark.anyio
    async def test_filter_by_subject_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/medication-reconciliations",
            params={"subject_id": "SUBJ-E001"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["subject_id"] == "SUBJ-E001"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/medication-reconciliations",
            params={"trial_id": LIBTAYO_TRIAL},
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
        assert "total_medication_records" in data
        assert "total_interaction_checks" in data
        assert "total_prohibited_alerts" in data
        assert "total_reconciliations" in data
        assert "override_rate" in data
        assert "reconciliation_rate" in data

    @pytest.mark.anyio
    async def test_metrics_total_medication_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_medication_records"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_interaction_checks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_interaction_checks"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_prohibited_alerts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_prohibited_alerts"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_reconciliations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_reconciliations"] == 12

    @pytest.mark.anyio
    async def test_metrics_has_breakdowns(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert isinstance(data["records_by_status"], dict)
        assert isinstance(data["interactions_by_severity"], dict)
        assert isinstance(data["alerts_by_priority"], dict)
        assert isinstance(data["alerts_by_status"], dict)
        assert isinstance(data["reconciliations_by_outcome"], dict)

    def test_metrics_service_level(self, svc: ConcomitantMedicationService):
        metrics = svc.get_metrics()
        assert metrics.total_medication_records == 12
        assert metrics.total_interaction_checks == 12
        assert metrics.total_prohibited_alerts == 12
        assert metrics.total_reconciliations == 12


# ===================================================================
# EDGE CASES & UPDATE PRESERVATION
# ===================================================================


class TestEdgeCases:
    @pytest.mark.anyio
    async def test_update_medication_record_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/medication-records/MED-001")
        original = resp.json()
        original_name = original["medication_name"]

        resp2 = await client.put(
            f"{API_PREFIX}/medication-records/MED-001",
            json={"notes": "Partial update"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["medication_name"] == original_name
        assert updated["notes"] == "Partial update"

    @pytest.mark.anyio
    async def test_update_interaction_check_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-interaction-checks/DIC-001")
        original = resp.json()
        original_desc = original["interaction_description"]

        resp2 = await client.put(
            f"{API_PREFIX}/drug-interaction-checks/DIC-001",
            json={"notes": "Updated interaction note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["interaction_description"] == original_desc

    @pytest.mark.anyio
    async def test_update_alert_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/prohibited-medication-alerts/PMA-001")
        original = resp.json()
        original_reason = original["prohibition_reason"]

        resp2 = await client.put(
            f"{API_PREFIX}/prohibited-medication-alerts/PMA-001",
            json={"notes": "Updated alert note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["prohibition_reason"] == original_reason

    @pytest.mark.anyio
    async def test_update_reconciliation_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/medication-reconciliations/MRC-001")
        original = resp.json()
        original_performer = original["performed_by"]

        resp2 = await client.put(
            f"{API_PREFIX}/medication-reconciliations/MRC-001",
            json={"notes": "Updated reconciliation note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["performed_by"] == original_performer


# ===================================================================
# SINGLETON PATTERN
# ===================================================================


class TestSingleton:
    def test_get_returns_same_instance(self):
        svc1 = get_concomitant_medication_service()
        svc2 = get_concomitant_medication_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        svc1 = get_concomitant_medication_service()
        svc2 = reset_concomitant_medication_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_concomitant_medication_service()
        svc.delete_medication_record("MED-001")
        assert svc.get_medication_record("MED-001") is None
        svc2 = reset_concomitant_medication_service()
        assert svc2.get_medication_record("MED-001") is not None


# ===================================================================
# SERVICE-LEVEL CRUD
# ===================================================================


class TestServiceLevelCRUD:
    def test_list_medication_records_service(self, svc: ConcomitantMedicationService):
        items = svc.list_medication_records()
        assert len(items) == 12

    def test_get_medication_record_service(self, svc: ConcomitantMedicationService):
        record = svc.get_medication_record("MED-001")
        assert record is not None
        assert record.id == "MED-001"

    def test_list_drug_interaction_checks_service(self, svc: ConcomitantMedicationService):
        items = svc.list_drug_interaction_checks()
        assert len(items) == 12

    def test_get_drug_interaction_check_service(self, svc: ConcomitantMedicationService):
        record = svc.get_drug_interaction_check("DIC-001")
        assert record is not None
        assert record.id == "DIC-001"

    def test_list_prohibited_medication_alerts_service(self, svc: ConcomitantMedicationService):
        items = svc.list_prohibited_medication_alerts()
        assert len(items) == 12

    def test_get_prohibited_medication_alert_service(self, svc: ConcomitantMedicationService):
        record = svc.get_prohibited_medication_alert("PMA-001")
        assert record is not None
        assert record.id == "PMA-001"

    def test_list_medication_reconciliations_service(self, svc: ConcomitantMedicationService):
        items = svc.list_medication_reconciliations()
        assert len(items) == 12

    def test_get_medication_reconciliation_service(self, svc: ConcomitantMedicationService):
        record = svc.get_medication_reconciliation("MRC-001")
        assert record is not None
        assert record.id == "MRC-001"

    def test_delete_medication_record_service(self, svc: ConcomitantMedicationService):
        assert svc.delete_medication_record("MED-001") is True
        assert svc.get_medication_record("MED-001") is None

    def test_delete_nonexistent_returns_false(self, svc: ConcomitantMedicationService):
        assert svc.delete_medication_record("NONEXISTENT") is False

    def test_filter_records_by_trial(self, svc: ConcomitantMedicationService):
        items = svc.list_medication_records(trial_id=EYLEA_TRIAL)
        for item in items:
            assert item.trial_id == EYLEA_TRIAL

    def test_filter_records_by_status(self, svc: ConcomitantMedicationService):
        items = svc.list_medication_records(medication_status=MedicationStatus.ONGOING)
        for item in items:
            assert item.medication_status == MedicationStatus.ONGOING

    def test_filter_interactions_by_severity(self, svc: ConcomitantMedicationService):
        items = svc.list_drug_interaction_checks(
            interaction_severity=InteractionSeverity.SEVERE
        )
        for item in items:
            assert item.interaction_severity == InteractionSeverity.SEVERE

    def test_filter_alerts_by_priority(self, svc: ConcomitantMedicationService):
        items = svc.list_prohibited_medication_alerts(
            alert_priority=AlertPriority.CRITICAL
        )
        for item in items:
            assert item.alert_priority == AlertPriority.CRITICAL

    def test_filter_alerts_by_status(self, svc: ConcomitantMedicationService):
        items = svc.list_prohibited_medication_alerts(alert_status=AlertStatus.ACTIVE)
        for item in items:
            assert item.alert_status == AlertStatus.ACTIVE

    def test_filter_reconciliations_by_outcome(self, svc: ConcomitantMedicationService):
        items = svc.list_medication_reconciliations(
            reconciliation_outcome=ReconciliationOutcome.RECONCILED
        )
        for item in items:
            assert item.reconciliation_outcome == ReconciliationOutcome.RECONCILED


# ===================================================================
# BULK / MULTI-ENTITY
# ===================================================================


class TestBulkOperations:
    @pytest.mark.anyio
    async def test_create_multiple_medication_records(self, client: AsyncClient):
        for i in range(3):
            resp = await client.post(
                f"{API_PREFIX}/medication-records",
                json=_make_medication_record_create(subject_id=f"BULK-{i}"),
            )
            assert resp.status_code == 201
        resp = await client.get(f"{API_PREFIX}/medication-records")
        assert resp.json()["total"] == 15  # 12 seed + 3 new

    @pytest.mark.anyio
    async def test_delete_multiple_interaction_checks(self, client: AsyncClient):
        for check_id in ["DIC-001", "DIC-002", "DIC-003"]:
            resp = await client.delete(f"{API_PREFIX}/drug-interaction-checks/{check_id}")
            assert resp.status_code == 204
        resp = await client.get(f"{API_PREFIX}/drug-interaction-checks")
        assert resp.json()["total"] == 9  # 12 seed - 3 deleted


# ===================================================================
# RESPONSE STRUCTURE
# ===================================================================


class TestAPIResponseStructure:
    @pytest.mark.anyio
    async def test_medication_record_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/medication-records/MED-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "subject_id", "site_id", "medication_name",
            "medication_status", "indication", "dose", "dose_unit",
            "frequency", "route", "start_date", "recorded_by", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_drug_interaction_check_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-interaction-checks/DIC-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "subject_id", "medication_record_id",
            "study_drug_name", "interaction_severity", "interaction_description",
            "checked_date", "checked_by", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_prohibited_medication_alert_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/prohibited-medication-alerts/PMA-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "subject_id", "site_id",
            "alert_priority", "alert_status", "medication_name",
            "prohibition_reason", "detected_date", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_medication_reconciliation_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/medication-reconciliations/MRC-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "subject_id", "site_id",
            "reconciliation_outcome", "visit_number", "reconciliation_date",
            "performed_by", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_list_response_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/medication-records")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
