"""Tests for Drug Accountability Management (DRUG-ACCT).

Covers:
- Seed data verification (dispensation records, drug returns, destruction records,
  reconciliations, deviations)
- Dispensation record CRUD (create, read, update, delete, list, filter by trial_id)
- Drug return CRUD (create, read, update, delete, list, filter by trial_id)
- Destruction record CRUD (create, read, update, delete, list, filter by trial_id)
- Accountability reconciliation CRUD (create, read, update, delete, list, filter)
- Accountability deviation CRUD (create, read, update, delete, list, filter)
- Drug accountability metrics computation
- Error handling (404s, 422s)
- Service singleton pattern
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.drug_accountability import (
    DestructionMethod,
    DeviationSeverity,
    DispensationType,
    DrugStatus,
    ReconciliationStatus,
)
from app.services.drug_accountability_service import (
    DrugAccountabilityService,
    get_drug_accountability_service,
    reset_drug_accountability_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/drug-accountability"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_drug_accountability_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> DrugAccountabilityService:
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


def _make_dispensation_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "subject_id": "SUBJ-9001",
        "dispensation_type": "initial",
        "drug_name": "Test Drug 100mg",
        "batch_number": "BATCH-TEST-001",
        "quantity_dispensed": 10,
        "dispensed_by": "PharmD Test User",
    }
    defaults.update(overrides)
    return defaults


def _make_drug_return_create(**overrides) -> dict:
    defaults = {
        "dispensation_id": "DISP-001",
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "subject_id": "SUBJ-1001",
        "quantity_returned": 3,
        "quantity_used": 7,
        "returned_to": "PharmD Test User",
    }
    defaults.update(overrides)
    return defaults


def _make_destruction_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "drug_name": "Test Drug 100mg",
        "destruction_method": "incineration",
        "quantity_destroyed": 5,
        "witness_1": "PharmD Test Witness",
        "approved_by": "Dr. Test Approver",
        "batch_numbers": ["BATCH-TEST-001"],
    }
    defaults.update(overrides)
    return defaults


def _make_reconciliation_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "period_start": (now - timedelta(days=30)).isoformat(),
        "period_end": now.isoformat(),
        "performed_by": "PharmD Test Reconciler",
        "total_received": 50,
    }
    defaults.update(overrides)
    return defaults


def _make_deviation_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "description": "Test deviation for unit testing purposes",
        "severity": "minor",
        "reported_by": "CRA Test Reporter",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_dispensation_records_count(self, svc: DrugAccountabilityService):
        records = svc.list_dispensation_records()
        assert len(records) == 12

    def test_seed_drug_returns_count(self, svc: DrugAccountabilityService):
        returns = svc.list_drug_returns()
        assert len(returns) == 10

    def test_seed_destruction_records_count(self, svc: DrugAccountabilityService):
        records = svc.list_destruction_records()
        assert len(records) == 10

    def test_seed_reconciliations_count(self, svc: DrugAccountabilityService):
        records = svc.list_accountability_reconciliations()
        assert len(records) == 10

    def test_seed_deviations_count(self, svc: DrugAccountabilityService):
        records = svc.list_accountability_deviations()
        assert len(records) == 10

    def test_seed_dispensation_has_all_trials(self, svc: DrugAccountabilityService):
        records = svc.list_dispensation_records()
        trial_ids = {r.trial_id for r in records}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_dispensation_types_variety(self, svc: DrugAccountabilityService):
        records = svc.list_dispensation_records()
        types = {r.dispensation_type for r in records}
        assert DispensationType.INITIAL in types
        assert DispensationType.REFILL in types
        assert DispensationType.EMERGENCY in types
        assert DispensationType.OPEN_LABEL in types

    def test_seed_destruction_methods_variety(self, svc: DrugAccountabilityService):
        records = svc.list_destruction_records()
        methods = {r.destruction_method for r in records}
        assert DestructionMethod.INCINERATION in methods
        assert DestructionMethod.PHARMACY_DISPOSAL in methods
        assert DestructionMethod.RETURN_TO_SPONSOR in methods
        assert DestructionMethod.WITNESSED_DESTRUCTION in methods
        assert DestructionMethod.CHEMICAL in methods

    def test_seed_deviation_severities_variety(self, svc: DrugAccountabilityService):
        deviations = svc.list_accountability_deviations()
        severities = {d.severity for d in deviations}
        assert DeviationSeverity.MINOR in severities
        assert DeviationSeverity.MODERATE in severities
        assert DeviationSeverity.MAJOR in severities
        assert DeviationSeverity.CRITICAL in severities

    def test_seed_reconciliation_has_discrepancy(self, svc: DrugAccountabilityService):
        """At least one reconciliation should have a discrepancy."""
        records = svc.list_accountability_reconciliations()
        has_discrepancy = any(r.discrepancy != 0 for r in records)
        assert has_discrepancy

    def test_seed_returns_has_temperature_excursion(self, svc: DrugAccountabilityService):
        """At least one return should have a temperature excursion."""
        returns = svc.list_drug_returns()
        has_excursion = any(r.temperature_excursion for r in returns)
        assert has_excursion

    def test_seed_deviations_has_open_items(self, svc: DrugAccountabilityService):
        """At least one deviation should be unresolved."""
        deviations = svc.list_accountability_deviations()
        open_devs = [d for d in deviations if d.resolution_date is None]
        assert len(open_devs) > 0


# =====================================================================
# DISPENSATION RECORD CRUD
# =====================================================================


class TestDispensationRecordCrud:
    """Test dispensation record CRUD operations."""

    @pytest.mark.anyio
    async def test_list_dispensation_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dispensation-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_dispensation_records_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/dispensation-records", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_dispensation_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dispensation-records/DISP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DISP-001"
        assert data["drug_name"] == "Aflibercept (EYLEA) 2mg"
        assert data["status"] == "administered"

    @pytest.mark.anyio
    async def test_get_dispensation_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dispensation-records/DISP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_dispensation_record(self, client: AsyncClient):
        payload = _make_dispensation_create()
        resp = await client.post(f"{API_PREFIX}/dispensation-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["drug_name"] == "Test Drug 100mg"
        assert data["quantity_dispensed"] == 10
        assert data["status"] == "dispensed"
        assert data["id"].startswith("DISP-")

    @pytest.mark.anyio
    async def test_create_dispensation_record_with_optional_fields(self, client: AsyncClient):
        payload = _make_dispensation_create(
            kit_number="KIT-TEST-001",
            visit_id="VISIT-TEST",
        )
        resp = await client.post(f"{API_PREFIX}/dispensation-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["kit_number"] == "KIT-TEST-001"
        assert data["visit_id"] == "VISIT-TEST"

    @pytest.mark.anyio
    async def test_update_dispensation_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/dispensation-records/DISP-003",
            json={"status": "administered", "verified_by": "Dr. Test Verifier"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "administered"
        assert data["verified_by"] == "Dr. Test Verifier"

    @pytest.mark.anyio
    async def test_update_dispensation_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/dispensation-records/DISP-NONEXISTENT",
            json={"status": "administered"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_dispensation_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/dispensation-records/DISP-012")
        assert resp.status_code == 204
        # Verify it's gone
        resp2 = await client.get(f"{API_PREFIX}/dispensation-records/DISP-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_dispensation_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/dispensation-records/DISP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_dispensation_validation_error(self, client: AsyncClient):
        """Missing required fields should return 422."""
        resp = await client.post(
            f"{API_PREFIX}/dispensation-records",
            json={"trial_id": EYLEA_TRIAL},  # Missing many required fields
        )
        assert resp.status_code == 422


# =====================================================================
# DRUG RETURN CRUD
# =====================================================================


class TestDrugReturnCrud:
    """Test drug return CRUD operations."""

    @pytest.mark.anyio
    async def test_list_drug_returns(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-returns")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_drug_returns_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/drug-returns", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_drug_return(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-returns/RET-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RET-001"
        assert data["dispensation_id"] == "DISP-001"

    @pytest.mark.anyio
    async def test_get_drug_return_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-returns/RET-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_drug_return(self, client: AsyncClient):
        payload = _make_drug_return_create()
        resp = await client.post(f"{API_PREFIX}/drug-returns", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["quantity_returned"] == 3
        assert data["quantity_used"] == 7
        assert data["id"].startswith("RET-")

    @pytest.mark.anyio
    async def test_update_drug_return(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/drug-returns/RET-007",
            json={"verified_by": "PharmD Test Verifier", "notes": "Verified post-excursion"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["verified_by"] == "PharmD Test Verifier"
        assert data["notes"] == "Verified post-excursion"

    @pytest.mark.anyio
    async def test_update_drug_return_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/drug-returns/RET-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_drug_return(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/drug-returns/RET-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/drug-returns/RET-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_drug_return_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/drug-returns/RET-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_drug_return_validation_error(self, client: AsyncClient):
        """Missing required fields should return 422."""
        resp = await client.post(
            f"{API_PREFIX}/drug-returns",
            json={"dispensation_id": "DISP-001"},  # Missing many required fields
        )
        assert resp.status_code == 422


# =====================================================================
# DESTRUCTION RECORD CRUD
# =====================================================================


class TestDestructionRecordCrud:
    """Test destruction record CRUD operations."""

    @pytest.mark.anyio
    async def test_list_destruction_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/destruction-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_destruction_records_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/destruction-records", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_destruction_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/destruction-records/DEST-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DEST-001"
        assert data["documentation_complete"] is True

    @pytest.mark.anyio
    async def test_get_destruction_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/destruction-records/DEST-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_destruction_record(self, client: AsyncClient):
        payload = _make_destruction_create()
        resp = await client.post(f"{API_PREFIX}/destruction-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["drug_name"] == "Test Drug 100mg"
        assert data["quantity_destroyed"] == 5
        assert data["destruction_method"] == "incineration"
        assert data["id"].startswith("DEST-")

    @pytest.mark.anyio
    async def test_update_destruction_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/destruction-records/DEST-005",
            json={
                "witness_2": "CRA Test Witness",
                "certificate_number": "DEST-CERT-005-UPDATED",
                "documentation_complete": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["witness_2"] == "CRA Test Witness"
        assert data["certificate_number"] == "DEST-CERT-005-UPDATED"
        assert data["documentation_complete"] is True

    @pytest.mark.anyio
    async def test_update_destruction_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/destruction-records/DEST-NONEXISTENT",
            json={"documentation_complete": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_destruction_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/destruction-records/DEST-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/destruction-records/DEST-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_destruction_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/destruction-records/DEST-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_destruction_validation_error(self, client: AsyncClient):
        """Missing required fields should return 422."""
        resp = await client.post(
            f"{API_PREFIX}/destruction-records",
            json={"trial_id": EYLEA_TRIAL},  # Missing many required fields
        )
        assert resp.status_code == 422


# =====================================================================
# ACCOUNTABILITY RECONCILIATION CRUD
# =====================================================================


class TestReconciliationCrud:
    """Test accountability reconciliation CRUD operations."""

    @pytest.mark.anyio
    async def test_list_reconciliations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_reconciliations_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/reconciliations", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_reconciliation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliations/RECON-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RECON-001"
        assert data["status"] == "reconciled"
        assert data["discrepancy"] == 0

    @pytest.mark.anyio
    async def test_get_reconciliation_with_discrepancy(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliations/RECON-006")
        assert resp.status_code == 200
        data = resp.json()
        assert data["discrepancy"] == -1
        assert data["status"] == "discrepancy"

    @pytest.mark.anyio
    async def test_get_reconciliation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliations/RECON-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_reconciliation(self, client: AsyncClient):
        payload = _make_reconciliation_create()
        resp = await client.post(f"{API_PREFIX}/reconciliations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["total_received"] == 50
        assert data["id"].startswith("RECON-")

    @pytest.mark.anyio
    async def test_update_reconciliation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reconciliations/RECON-010",
            json={
                "status": "reconciled",
                "verified_by": "CRA Test Verifier",
                "notes": "Verified and reconciled",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "reconciled"
        assert data["verified_by"] == "CRA Test Verifier"

    @pytest.mark.anyio
    async def test_update_reconciliation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reconciliations/RECON-NONEXISTENT",
            json={"status": "reconciled"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_reconciliation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reconciliations/RECON-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/reconciliations/RECON-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_reconciliation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reconciliations/RECON-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_reconciliation_validation_error(self, client: AsyncClient):
        """Missing required fields should return 422."""
        resp = await client.post(
            f"{API_PREFIX}/reconciliations",
            json={"trial_id": EYLEA_TRIAL},  # Missing many required fields
        )
        assert resp.status_code == 422


# =====================================================================
# ACCOUNTABILITY DEVIATION CRUD
# =====================================================================


class TestDeviationCrud:
    """Test accountability deviation CRUD operations."""

    @pytest.mark.anyio
    async def test_list_deviations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deviations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_deviations_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/deviations", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_deviation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deviations/DEV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DEV-001"
        assert data["severity"] == "moderate"
        assert data["sponsor_notified"] is True

    @pytest.mark.anyio
    async def test_get_deviation_critical(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deviations/DEV-007")
        assert resp.status_code == 200
        data = resp.json()
        assert data["severity"] == "critical"
        assert data["irb_notified"] is True

    @pytest.mark.anyio
    async def test_get_deviation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deviations/DEV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_deviation(self, client: AsyncClient):
        payload = _make_deviation_create()
        resp = await client.post(f"{API_PREFIX}/deviations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["severity"] == "minor"
        assert data["reported_by"] == "CRA Test Reporter"
        assert data["id"].startswith("DEV-")

    @pytest.mark.anyio
    async def test_create_deviation_with_optional_fields(self, client: AsyncClient):
        payload = _make_deviation_create(
            subject_id="SUBJ-9999",
            batch_number="BATCH-OPT-001",
            severity="critical",
        )
        resp = await client.post(f"{API_PREFIX}/deviations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject_id"] == "SUBJ-9999"
        assert data["batch_number"] == "BATCH-OPT-001"
        assert data["severity"] == "critical"

    @pytest.mark.anyio
    async def test_update_deviation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/deviations/DEV-003",
            json={
                "root_cause": "Updated root cause after investigation",
                "corrective_action": "New corrective measures implemented",
                "sponsor_notified": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["root_cause"] == "Updated root cause after investigation"
        assert data["corrective_action"] == "New corrective measures implemented"

    @pytest.mark.anyio
    async def test_update_deviation_resolve(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/deviations/DEV-009",
            json={"resolved_by": "QA Manager Test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolved_by"] == "QA Manager Test"

    @pytest.mark.anyio
    async def test_update_deviation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/deviations/DEV-NONEXISTENT",
            json={"root_cause": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_deviation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/deviations/DEV-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/deviations/DEV-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_deviation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/deviations/DEV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_deviation_validation_error(self, client: AsyncClient):
        """Missing required fields should return 422."""
        resp = await client.post(
            f"{API_PREFIX}/deviations",
            json={"trial_id": EYLEA_TRIAL},  # Missing many required fields
        )
        assert resp.status_code == 422


# =====================================================================
# METRICS
# =====================================================================


class TestDrugAccountabilityMetrics:
    """Test drug accountability metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_dispensations"] == 12
        assert data["total_returns"] == 10
        assert data["destruction_records"] == 10
        assert data["total_reconciliations"] == 10
        assert data["total_deviations"] == 10
        assert data["total_quantity_dispensed"] > 0
        assert data["total_quantity_returned"] >= 0
        assert data["total_quantity_destroyed"] > 0

    @pytest.mark.anyio
    async def test_metrics_dispensations_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_type = data["dispensations_by_type"]
        assert "initial" in by_type
        assert "refill" in by_type
        total_by_type = sum(by_type.values())
        assert total_by_type == data["total_dispensations"]

    @pytest.mark.anyio
    async def test_metrics_dispensations_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["dispensations_by_status"]
        assert len(by_status) > 0
        total_by_status = sum(by_status.values())
        assert total_by_status == data["total_dispensations"]

    @pytest.mark.anyio
    async def test_metrics_deviations_by_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_severity = data["deviations_by_severity"]
        assert "minor" in by_severity
        assert "moderate" in by_severity
        assert "major" in by_severity
        assert "critical" in by_severity
        total_by_severity = sum(by_severity.values())
        assert total_by_severity == data["total_deviations"]

    @pytest.mark.anyio
    async def test_metrics_reconciliations_with_discrepancy(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["reconciliations_with_discrepancy"] >= 1

    @pytest.mark.anyio
    async def test_metrics_open_deviations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["open_deviations"] >= 1

    def test_metrics_open_deviations_matches_service(self, svc: DrugAccountabilityService):
        metrics = svc.get_metrics()
        deviations = svc.list_accountability_deviations()
        open_count = sum(1 for d in deviations if d.resolution_date is None)
        assert metrics.open_deviations == open_count

    def test_metrics_quantity_totals(self, svc: DrugAccountabilityService):
        metrics = svc.get_metrics()
        dispensations = svc.list_dispensation_records()
        expected_dispensed = sum(d.quantity_dispensed for d in dispensations)
        assert metrics.total_quantity_dispensed == expected_dispensed

        returns = svc.list_drug_returns()
        expected_returned = sum(r.quantity_returned for r in returns)
        assert metrics.total_quantity_returned == expected_returned


# =====================================================================
# LIST FILTERING
# =====================================================================


class TestListFiltering:
    """Test list filtering across all entity types."""

    @pytest.mark.anyio
    async def test_dispensation_filter_dupixent(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/dispensation-records", params={"trial_id": DUPIXENT_TRIAL}
        )
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_dispensation_filter_libtayo(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/dispensation-records", params={"trial_id": LIBTAYO_TRIAL}
        )
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_returns_filter_eylea(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/drug-returns", params={"trial_id": EYLEA_TRIAL}
        )
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_destruction_filter_eylea(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/destruction-records", params={"trial_id": EYLEA_TRIAL}
        )
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_reconciliation_filter_libtayo(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/reconciliations", params={"trial_id": LIBTAYO_TRIAL}
        )
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_deviations_filter_dupixent(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/deviations", params={"trial_id": DUPIXENT_TRIAL}
        )
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_filter_nonexistent_trial_returns_empty(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/dispensation-records",
            params={"trial_id": "00000000-0000-0000-0000-000000000000"},
        )
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_drug_accountability_service()
        svc2 = get_drug_accountability_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_drug_accountability_service()
        svc2 = reset_drug_accountability_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_drug_accountability_service()
        # Delete a record
        svc.delete_dispensation_record("DISP-001")
        assert svc.get_dispensation_record("DISP-001") is None
        # Reset should bring it back
        svc2 = reset_drug_accountability_service()
        assert svc2.get_dispensation_record("DISP-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_dispensation_records_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dispensation-records")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_drug_returns_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-returns")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_destruction_records_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/destruction-records")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_reconciliations_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reconciliations")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_deviations_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deviations")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_and_retrieve_dispensation(self, client: AsyncClient):
        """Create a record and immediately retrieve it."""
        payload = _make_dispensation_create()
        create_resp = await client.post(f"{API_PREFIX}/dispensation-records", json=payload)
        assert create_resp.status_code == 201
        record_id = create_resp.json()["id"]

        get_resp = await client.get(f"{API_PREFIX}/dispensation-records/{record_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == record_id

    @pytest.mark.anyio
    async def test_create_and_delete_drug_return(self, client: AsyncClient):
        """Create a return then delete it."""
        payload = _make_drug_return_create()
        create_resp = await client.post(f"{API_PREFIX}/drug-returns", json=payload)
        assert create_resp.status_code == 201
        return_id = create_resp.json()["id"]

        delete_resp = await client.delete(f"{API_PREFIX}/drug-returns/{return_id}")
        assert delete_resp.status_code == 204

        get_resp = await client.get(f"{API_PREFIX}/drug-returns/{return_id}")
        assert get_resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_partial_fields_only(self, client: AsyncClient):
        """Updating only one field should not affect other fields."""
        # Get original
        resp = await client.get(f"{API_PREFIX}/dispensation-records/DISP-001")
        original = resp.json()

        # Update only storage_instructions
        resp2 = await client.put(
            f"{API_PREFIX}/dispensation-records/DISP-001",
            json={"storage_instructions": "Updated storage instructions"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["storage_instructions"] == "Updated storage instructions"
        # Other fields should remain the same
        assert updated["drug_name"] == original["drug_name"]
        assert updated["batch_number"] == original["batch_number"]
        assert updated["quantity_dispensed"] == original["quantity_dispensed"]

    @pytest.mark.anyio
    async def test_dispensation_record_has_all_fields(self, client: AsyncClient):
        """Verify a dispensation record returns all expected fields."""
        resp = await client.get(f"{API_PREFIX}/dispensation-records/DISP-001")
        data = resp.json()
        expected_fields = [
            "id", "trial_id", "site_id", "subject_id", "dispensation_type",
            "drug_name", "batch_number", "quantity_dispensed", "quantity_units",
            "dispensation_date", "dispensed_by", "status", "created_at",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

    @pytest.mark.anyio
    async def test_destruction_record_batch_numbers_list(self, client: AsyncClient):
        """Verify batch_numbers is a list."""
        resp = await client.get(f"{API_PREFIX}/destruction-records/DEST-006")
        data = resp.json()
        assert isinstance(data["batch_numbers"], list)
        assert len(data["batch_numbers"]) == 2

    @pytest.mark.anyio
    async def test_reconciliation_balance_fields(self, client: AsyncClient):
        """Verify reconciliation balance fields are consistent."""
        resp = await client.get(f"{API_PREFIX}/reconciliations/RECON-001")
        data = resp.json()
        assert data["balance_expected"] == data["balance_actual"]
        assert data["discrepancy"] == 0

    @pytest.mark.anyio
    async def test_deviation_with_no_subject(self, client: AsyncClient):
        """Deviations can have null subject_id (site-level deviations)."""
        resp = await client.get(f"{API_PREFIX}/deviations/DEV-004")
        data = resp.json()
        assert data["subject_id"] is None

    @pytest.mark.anyio
    async def test_metrics_after_create(self, client: AsyncClient):
        """Metrics should reflect newly created records."""
        # Get initial metrics
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        initial = resp1.json()

        # Create a new dispensation
        payload = _make_dispensation_create()
        await client.post(f"{API_PREFIX}/dispensation-records", json=payload)

        # Get updated metrics
        resp2 = await client.get(f"{API_PREFIX}/metrics")
        updated = resp2.json()
        assert updated["total_dispensations"] == initial["total_dispensations"] + 1

    @pytest.mark.anyio
    async def test_metrics_after_delete(self, client: AsyncClient):
        """Metrics should reflect deleted records."""
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        initial = resp1.json()

        await client.delete(f"{API_PREFIX}/dispensation-records/DISP-001")

        resp2 = await client.get(f"{API_PREFIX}/metrics")
        updated = resp2.json()
        assert updated["total_dispensations"] == initial["total_dispensations"] - 1
