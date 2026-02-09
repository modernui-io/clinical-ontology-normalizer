"""Tests for Interactive Response Technology (IRT/IWRS) (CLINICAL-19).

Covers:
- Seed data verification (configurations, transactions, assignments, visits, stratification, kits)
- IRT transaction CRUD (create, read, list, filter by trial/site/patient/type)
- Drug assignment CRUD (create, read, update, list, filter by patient/arm)
- Drug kit management (list, filter by site/trial/status, get by kit number)
- Drug accountability (summary per site, resupply detection)
- Drug resupply workflow (request, kit creation, transaction logging)
- Visit schedule management (create, read, list, filter)
- Visit confirmation with window calculation (early, on_time, late)
- Dose modification workflow
- Emergency unblinding workflow
- Stratification entry management (create, read, list, filter)
- IRT configuration management (list, get, update)
- Patient compliance tracking (drug and visit compliance)
- IRT metrics computation
- Error handling (404s, 400s, duplicate confirmation)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.irt_system import (
    DoseModificationRequest,
    DrugAssignmentCreate,
    DrugAssignmentUpdate,
    DrugResupplyRequest,
    DrugSupplyStatus,
    IRTTransactionCreate,
    IRTTransactionType,
    StratificationEntryCreate,
    StratificationFactor,
    UnblindingRequest,
    VisitConfirmation,
    VisitScheduleCreate,
    VisitWindow,
)
from app.services.irt_service import (
    IRTService,
    get_irt_service,
    reset_irt_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/irt"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_irt_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> IRTService:
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


def _make_transaction_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "patient_id": "PAT-0001",
        "transaction_type": "screening",
        "details": "Patient screened for eligibility",
        "performed_by": "Dr. Test",
    }
    defaults.update(overrides)
    return defaults


def _make_drug_assignment_create(**overrides) -> dict:
    defaults = {
        "patient_id": "PAT-0001",
        "treatment_arm": "Eylea 2mg",
        "kit_number": "KIT-TEST-001",
        "lot_number": "LOT-2026-T001",
    }
    defaults.update(overrides)
    return defaults


def _make_visit_schedule_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "patient_id": "PAT-0001",
        "trial_id": EYLEA_TRIAL,
        "visit_number": 1,
        "visit_name": "Test Visit",
        "window_open": (now + timedelta(days=10)).isoformat(),
        "window_close": (now + timedelta(days=18)).isoformat(),
        "scheduled_date": (now + timedelta(days=14)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_configurations_count(self, svc: IRTService):
        configs = svc.list_configurations()
        assert len(configs) == 3

    def test_seed_configurations_trials(self, svc: IRTService):
        configs = svc.list_configurations()
        trial_ids = {c.trial_id for c in configs}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_transactions_count(self, svc: IRTService):
        txs = svc.list_transactions()
        assert len(txs) == 50

    def test_seed_transactions_types_present(self, svc: IRTService):
        txs = svc.list_transactions()
        types = {t.transaction_type for t in txs}
        assert IRTTransactionType.SCREENING in types
        assert IRTTransactionType.RANDOMIZATION in types
        assert IRTTransactionType.DRUG_ASSIGNMENT in types

    def test_seed_drug_assignments_count(self, svc: IRTService):
        das = svc.list_drug_assignments()
        assert len(das) == 30

    def test_seed_visit_schedules_count(self, svc: IRTService):
        visits = svc.list_visit_schedules()
        assert len(visits) == 40

    def test_seed_stratification_entries_count(self, svc: IRTService):
        entries = svc.list_stratification_entries()
        assert len(entries) == 30

    def test_seed_drug_kits_exist(self, svc: IRTService):
        kits = svc.list_drug_kits()
        assert len(kits) > 0

    def test_seed_drug_kits_multiple_statuses(self, svc: IRTService):
        kits = svc.list_drug_kits()
        statuses = {k.status for k in kits}
        assert DrugSupplyStatus.AVAILABLE in statuses

    def test_seed_configurations_have_stratification(self, svc: IRTService):
        cfg = svc.get_configuration(EYLEA_TRIAL)
        assert cfg is not None
        assert len(cfg.stratification_factors) > 0

    def test_seed_configurations_have_dose_levels(self, svc: IRTService):
        cfg = svc.get_configuration(EYLEA_TRIAL)
        assert cfg is not None
        assert len(cfg.dose_levels) > 0

    def test_seed_configurations_have_visit_windows(self, svc: IRTService):
        cfg = svc.get_configuration(DUPIXENT_TRIAL)
        assert cfg is not None
        assert len(cfg.visit_windows) > 0


# =====================================================================
# IRT TRANSACTIONS
# =====================================================================


class TestIRTTransactions:
    """Test IRT transaction operations."""

    @pytest.mark.anyio
    async def test_list_transactions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 50
        assert len(data["items"]) == 50

    @pytest.mark.anyio
    async def test_list_transactions_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/transactions", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_transactions_filter_site(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/transactions", params={"site_id": "SITE-101"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_transactions_filter_patient(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/transactions", params={"patient_id": "PAT-0001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["patient_id"] == "PAT-0001"

    @pytest.mark.anyio
    async def test_list_transactions_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/transactions", params={"transaction_type": "screening"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["transaction_type"] == "screening"

    @pytest.mark.anyio
    async def test_get_transaction(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/transactions/IRT-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "IRT-0001"
        assert "confirmation_number" in data

    @pytest.mark.anyio
    async def test_get_transaction_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/transactions/IRT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_transaction(self, client: AsyncClient):
        payload = _make_transaction_create()
        resp = await client.post(f"{API_PREFIX}/transactions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == "PAT-0001"
        assert data["transaction_type"] == "screening"
        assert data["id"].startswith("IRT-")
        assert data["confirmation_number"].startswith("CNF-")

    @pytest.mark.anyio
    async def test_create_transaction_randomization(self, client: AsyncClient):
        payload = _make_transaction_create(transaction_type="randomization")
        resp = await client.post(f"{API_PREFIX}/transactions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["transaction_type"] == "randomization"
        assert "randomized" in data["system_response"].lower()

    @pytest.mark.anyio
    async def test_create_transaction_discontinuation(self, client: AsyncClient):
        payload = _make_transaction_create(transaction_type="discontinuation")
        resp = await client.post(f"{API_PREFIX}/transactions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["transaction_type"] == "discontinuation"

    @pytest.mark.anyio
    async def test_transactions_sorted_by_timestamp(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/transactions")
        data = resp.json()
        timestamps = [item["timestamp"] for item in data["items"]]
        assert timestamps == sorted(timestamps, reverse=True)


# =====================================================================
# DRUG ASSIGNMENTS
# =====================================================================


class TestDrugAssignments:
    """Test drug assignment operations."""

    @pytest.mark.anyio
    async def test_list_drug_assignments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-assignments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 30

    @pytest.mark.anyio
    async def test_list_drug_assignments_filter_patient(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/drug-assignments", params={"patient_id": "PAT-0001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["patient_id"] == "PAT-0001"

    @pytest.mark.anyio
    async def test_get_drug_assignment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-assignments/DA-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DA-0001"
        assert "kit_number" in data
        assert "lot_number" in data

    @pytest.mark.anyio
    async def test_get_drug_assignment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-assignments/DA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_drug_assignment(self, client: AsyncClient):
        payload = _make_drug_assignment_create()
        resp = await client.post(f"{API_PREFIX}/drug-assignments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == "PAT-0001"
        assert data["treatment_arm"] == "Eylea 2mg"
        assert data["compliance_pct"] == 100.0

    @pytest.mark.anyio
    async def test_update_drug_assignment_return(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/drug-assignments/DA-0001",
            json={"return_date": now.isoformat()},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["return_date"] is not None

    @pytest.mark.anyio
    async def test_update_drug_assignment_compliance(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/drug-assignments/DA-0001",
            json={"compliance_pct": 85.5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["compliance_pct"] == 85.5

    @pytest.mark.anyio
    async def test_update_drug_assignment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/drug-assignments/DA-NONEXISTENT",
            json={"compliance_pct": 90.0},
        )
        assert resp.status_code == 404

    def test_drug_assignment_has_transaction_id(self, svc: IRTService):
        da = svc.get_drug_assignment("DA-0001")
        assert da is not None
        assert da.transaction_id.startswith("IRT-")


# =====================================================================
# DRUG KITS
# =====================================================================


class TestDrugKits:
    """Test drug kit management."""

    @pytest.mark.anyio
    async def test_list_drug_kits(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-kits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_list_drug_kits_filter_site(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/drug-kits", params={"site_id": "SITE-101"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_drug_kits_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/drug-kits", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_drug_kits_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/drug-kits", params={"status": "available"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "available"

    @pytest.mark.anyio
    async def test_get_drug_kit(self, client: AsyncClient):
        # Get first kit from list
        resp = await client.get(f"{API_PREFIX}/drug-kits")
        data = resp.json()
        kit_number = data["items"][0]["kit_number"]

        resp2 = await client.get(f"{API_PREFIX}/drug-kits/{kit_number}")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["kit_number"] == kit_number

    @pytest.mark.anyio
    async def test_get_drug_kit_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-kits/KIT-NONEXISTENT")
        assert resp.status_code == 404

    def test_drug_kit_has_expiry_date(self, svc: IRTService):
        kits = svc.list_drug_kits()
        for kit in kits[:5]:
            assert kit.expiry_date is not None


# =====================================================================
# DRUG ACCOUNTABILITY
# =====================================================================


class TestDrugAccountability:
    """Test drug accountability operations."""

    @pytest.mark.anyio
    async def test_get_drug_accountability(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-101/drug-accountability")
        assert resp.status_code == 200
        data = resp.json()
        assert data["site_id"] == "SITE-101"
        assert data["total_kits"] > 0
        assert "available" in data
        assert "dispensed" in data
        assert "returned" in data
        assert "destroyed" in data
        assert "expired" in data
        assert "buffer_weeks_remaining" in data

    @pytest.mark.anyio
    async def test_get_drug_accountability_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-NONEXISTENT/drug-accountability")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_sites_needing_resupply(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/resupply-needed")
        assert resp.status_code == 200
        data = resp.json()
        for site in data:
            assert site["resupply_needed"] is True

    def test_accountability_total_matches(self, svc: IRTService):
        summary = svc.get_drug_accountability("SITE-101")
        assert summary is not None
        total = (
            summary.available + summary.assigned + summary.dispensed
            + summary.returned + summary.destroyed + summary.expired
        )
        assert total == summary.total_kits

    def test_resupply_threshold(self, svc: IRTService):
        summary = svc.get_drug_accountability("SITE-101")
        assert summary is not None
        if summary.resupply_needed:
            assert summary.buffer_weeks_remaining < 4  # Default buffer


# =====================================================================
# DRUG RESUPPLY
# =====================================================================


class TestDrugResupply:
    """Test drug resupply workflow."""

    @pytest.mark.anyio
    async def test_request_drug_resupply(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "site_id": "SITE-101",
            "kit_count": 10,
            "performed_by": "Dr. Supply Manager",
        }
        resp = await client.post(f"{API_PREFIX}/drug-resupply", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["transaction_type"] == "drug_resupply"
        assert "10 kits" in data["details"]

    @pytest.mark.anyio
    async def test_resupply_creates_new_kits(self, client: AsyncClient):
        # Count kits before
        resp_before = await client.get(
            f"{API_PREFIX}/drug-kits", params={"site_id": "SITE-102"}
        )
        count_before = resp_before.json()["total"]

        # Request resupply
        payload = {
            "trial_id": EYLEA_TRIAL,
            "site_id": "SITE-102",
            "kit_count": 5,
            "performed_by": "Supply Mgr",
        }
        await client.post(f"{API_PREFIX}/drug-resupply", json=payload)

        # Count kits after
        resp_after = await client.get(
            f"{API_PREFIX}/drug-kits", params={"site_id": "SITE-102"}
        )
        count_after = resp_after.json()["total"]
        assert count_after == count_before + 5

    def test_resupply_kits_are_available(self, svc: IRTService):
        payload = DrugResupplyRequest(
            trial_id=EYLEA_TRIAL,
            site_id="SITE-103",
            kit_count=3,
            performed_by="test",
        )
        svc.request_drug_resupply(payload)
        kits = svc.list_drug_kits(site_id="SITE-103", status=DrugSupplyStatus.AVAILABLE)
        assert len(kits) >= 3


# =====================================================================
# VISIT SCHEDULES
# =====================================================================


class TestVisitSchedules:
    """Test visit schedule management."""

    @pytest.mark.anyio
    async def test_list_visit_schedules(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visit-schedules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 40

    @pytest.mark.anyio
    async def test_list_visit_schedules_filter_patient(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/visit-schedules", params={"patient_id": "PAT-0001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["patient_id"] == "PAT-0001"

    @pytest.mark.anyio
    async def test_list_visit_schedules_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/visit-schedules", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_visit_schedules_filter_window_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/visit-schedules", params={"window_status": "on_time"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["window_status"] == "on_time"

    @pytest.mark.anyio
    async def test_get_visit_schedule(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visit-schedules/VS-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "VS-0001"
        assert "visit_name" in data
        assert "window_open" in data
        assert "window_close" in data

    @pytest.mark.anyio
    async def test_get_visit_schedule_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visit-schedules/VS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_visit_schedule(self, client: AsyncClient):
        payload = _make_visit_schedule_create()
        resp = await client.post(f"{API_PREFIX}/visit-schedules", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == "PAT-0001"
        assert data["visit_name"] == "Test Visit"
        assert data["id"].startswith("VS-")

    def test_visit_schedule_has_windows(self, svc: IRTService):
        vs = svc.get_visit_schedule("VS-0001")
        assert vs is not None
        assert vs.window_open < vs.window_close


# =====================================================================
# VISIT CONFIRMATION
# =====================================================================


class TestVisitConfirmation:
    """Test visit confirmation with window calculations."""

    def _find_unconfirmed_visit(self, svc: IRTService) -> str | None:
        """Find a visit that hasn't been confirmed yet."""
        visits = svc.list_visit_schedules()
        for v in visits:
            if v.actual_date is None:
                return v.id
        return None

    @pytest.mark.anyio
    async def test_confirm_visit_on_time(self, client: AsyncClient, svc: IRTService):
        visit_id = self._find_unconfirmed_visit(svc)
        if visit_id is None:
            pytest.skip("No unconfirmed visits available")
        vs = svc.get_visit_schedule(visit_id)
        assert vs is not None
        # Use scheduled date (within window)
        payload = {"actual_date": vs.scheduled_date.isoformat()}
        resp = await client.post(
            f"{API_PREFIX}/visit-schedules/{visit_id}/confirm", json=payload
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["actual_date"] is not None
        assert data["window_status"] == "on_time"

    @pytest.mark.anyio
    async def test_confirm_visit_early(self, client: AsyncClient, svc: IRTService):
        visit_id = self._find_unconfirmed_visit(svc)
        if visit_id is None:
            pytest.skip("No unconfirmed visits available")
        vs = svc.get_visit_schedule(visit_id)
        assert vs is not None
        early_date = vs.window_open - timedelta(days=2)
        payload = {"actual_date": early_date.isoformat()}
        resp = await client.post(
            f"{API_PREFIX}/visit-schedules/{visit_id}/confirm", json=payload
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["window_status"] == "early"

    @pytest.mark.anyio
    async def test_confirm_visit_late(self, client: AsyncClient, svc: IRTService):
        visit_id = self._find_unconfirmed_visit(svc)
        if visit_id is None:
            pytest.skip("No unconfirmed visits available")
        vs = svc.get_visit_schedule(visit_id)
        assert vs is not None
        late_date = vs.window_close + timedelta(days=2)
        payload = {"actual_date": late_date.isoformat()}
        resp = await client.post(
            f"{API_PREFIX}/visit-schedules/{visit_id}/confirm", json=payload
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["window_status"] == "late"

    @pytest.mark.anyio
    async def test_confirm_visit_not_found(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {"actual_date": now.isoformat()}
        resp = await client.post(
            f"{API_PREFIX}/visit-schedules/VS-NONEXISTENT/confirm", json=payload
        )
        assert resp.status_code == 404

    def test_confirm_already_confirmed_visit(self, svc: IRTService):
        """Confirming an already-confirmed visit should raise ValueError."""
        # Find a visit with actual_date set
        visits = svc.list_visit_schedules()
        confirmed = [v for v in visits if v.actual_date is not None]
        if not confirmed:
            pytest.skip("No confirmed visits available")

        with pytest.raises(ValueError, match="already confirmed"):
            svc.confirm_visit(
                confirmed[0].id,
                VisitConfirmation(actual_date=datetime.now(timezone.utc)),
            )

    def test_window_calculation_logic(self, svc: IRTService):
        """Create a visit and verify window calculations."""
        now = datetime.now(timezone.utc)
        vs = svc.create_visit_schedule(VisitScheduleCreate(
            patient_id="PAT-TEST",
            trial_id=EYLEA_TRIAL,
            visit_number=1,
            visit_name="Test Window",
            window_open=now + timedelta(days=10),
            window_close=now + timedelta(days=18),
            scheduled_date=now + timedelta(days=14),
        ))

        # Confirm on-time
        result = svc.confirm_visit(
            vs.id,
            VisitConfirmation(actual_date=now + timedelta(days=14)),
        )
        assert result is not None
        assert result.window_status == VisitWindow.ON_TIME


# =====================================================================
# DOSE MODIFICATION
# =====================================================================


class TestDoseModification:
    """Test dose modification workflow."""

    @pytest.mark.anyio
    async def test_request_dose_modification(self, client: AsyncClient):
        payload = {
            "patient_id": "PAT-0001",
            "trial_id": EYLEA_TRIAL,
            "current_dose": "2mg",
            "new_dose": "4mg",
            "reason": "Insufficient response at current dose",
            "performed_by": "Dr. Investigator",
        }
        resp = await client.post(f"{API_PREFIX}/dose-modification", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["transaction_type"] == "dose_modification"
        assert "2mg" in data["details"]
        assert "4mg" in data["details"]

    @pytest.mark.anyio
    async def test_dose_modification_creates_transaction(self, client: AsyncClient, svc: IRTService):
        initial_count = len(svc.list_transactions())
        payload = {
            "patient_id": "PAT-0002",
            "trial_id": DUPIXENT_TRIAL,
            "current_dose": "200mg",
            "new_dose": "300mg",
            "reason": "Tolerability improvement",
            "performed_by": "Dr. Test",
        }
        await client.post(f"{API_PREFIX}/dose-modification", json=payload)
        assert len(svc.list_transactions()) == initial_count + 1

    def test_dose_modification_service(self, svc: IRTService):
        tx = svc.request_dose_modification(DoseModificationRequest(
            patient_id="PAT-0003",
            trial_id=LIBTAYO_TRIAL,
            current_dose="350mg q3w",
            new_dose="350mg q3w + chemo",
            reason="Disease progression",
            performed_by="PI",
        ))
        assert tx.transaction_type == IRTTransactionType.DOSE_MODIFICATION
        assert "350mg q3w" in tx.details


# =====================================================================
# UNBLINDING
# =====================================================================


class TestUnblinding:
    """Test emergency unblinding workflow."""

    @pytest.mark.anyio
    async def test_request_unblinding(self, client: AsyncClient):
        payload = {
            "patient_id": "PAT-0001",
            "trial_id": EYLEA_TRIAL,
            "reason": "Serious adverse event requiring treatment decision",
            "performed_by": "Dr. Emergency",
        }
        resp = await client.post(f"{API_PREFIX}/unblinding", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["transaction_type"] == "unblinding"
        assert "unblinding" in data["details"].lower()

    @pytest.mark.anyio
    async def test_unblinding_reveals_treatment(self, client: AsyncClient):
        payload = {
            "patient_id": "PAT-0001",
            "trial_id": EYLEA_TRIAL,
            "reason": "Medical emergency",
            "performed_by": "Dr. Test",
        }
        resp = await client.post(f"{API_PREFIX}/unblinding", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert "safety review" in data["system_response"].lower()

    def test_unblinding_service(self, svc: IRTService):
        tx = svc.request_unblinding(UnblindingRequest(
            patient_id="PAT-0005",
            trial_id=DUPIXENT_TRIAL,
            reason="SAE requiring treatment info",
            performed_by="PI",
        ))
        assert tx.transaction_type == IRTTransactionType.UNBLINDING


# =====================================================================
# STRATIFICATION
# =====================================================================


class TestStratification:
    """Test stratification entry management."""

    @pytest.mark.anyio
    async def test_list_stratification(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stratification")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 30

    @pytest.mark.anyio
    async def test_get_stratification_entry(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stratification/PAT-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["patient_id"] == "PAT-0001"
        assert "factors" in data
        assert "stratum_id" in data

    @pytest.mark.anyio
    async def test_get_stratification_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stratification/PAT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_stratification_entry(self, client: AsyncClient):
        payload = {
            "patient_id": "PAT-NEW-001",
            "factors": {
                "age_group": "41-60",
                "sex": "female",
                "disease_severity": "moderate",
            },
        }
        resp = await client.post(f"{API_PREFIX}/stratification", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == "PAT-NEW-001"
        assert data["stratum_id"].startswith("STR-")

    def test_stratification_has_all_factors(self, svc: IRTService):
        entry = svc.get_stratification_entry("PAT-0001")
        assert entry is not None
        assert StratificationFactor.AGE_GROUP.value in entry.factors
        assert StratificationFactor.SEX.value in entry.factors
        assert StratificationFactor.DISEASE_SEVERITY.value in entry.factors

    @pytest.mark.anyio
    async def test_list_stratification_filter_stratum(self, client: AsyncClient, svc: IRTService):
        # Get a stratum ID from an existing entry
        entry = svc.get_stratification_entry("PAT-0001")
        assert entry is not None
        resp = await client.get(
            f"{API_PREFIX}/stratification",
            params={"stratum_id": entry.stratum_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["stratum_id"] == entry.stratum_id


# =====================================================================
# IRT CONFIGURATIONS
# =====================================================================


class TestIRTConfigurations:
    """Test IRT configuration management."""

    @pytest.mark.anyio
    async def test_list_configurations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/configurations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_get_configuration(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/configurations/{EYLEA_TRIAL}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["randomization_ratio"] == "2:1"
        assert len(data["stratification_factors"]) > 0
        assert len(data["dose_levels"]) > 0

    @pytest.mark.anyio
    async def test_get_configuration_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/configurations/NONEXISTENT-TRIAL")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_configuration(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/configurations/{EYLEA_TRIAL}",
            json={"randomization_ratio": "3:1", "drug_supply_buffer_weeks": 8},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["randomization_ratio"] == "3:1"
        assert data["drug_supply_buffer_weeks"] == 8

    @pytest.mark.anyio
    async def test_update_configuration_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/configurations/NONEXISTENT-TRIAL",
            json={"randomization_ratio": "1:1"},
        )
        assert resp.status_code == 404

    def test_dupixent_configuration(self, svc: IRTService):
        cfg = svc.get_configuration(DUPIXENT_TRIAL)
        assert cfg is not None
        assert cfg.randomization_ratio == "1:1"

    def test_libtayo_configuration(self, svc: IRTService):
        cfg = svc.get_configuration(LIBTAYO_TRIAL)
        assert cfg is not None
        assert cfg.randomization_ratio == "1:1:1"


# =====================================================================
# PATIENT COMPLIANCE
# =====================================================================


class TestPatientCompliance:
    """Test patient compliance tracking."""

    @pytest.mark.anyio
    async def test_get_patient_compliance(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/PAT-0001/compliance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["patient_id"] == "PAT-0001"
        assert "drug_assignments" in data
        assert "avg_drug_compliance_pct" in data
        assert "total_visits" in data
        assert "completed_visits" in data
        assert "visit_compliance_rate" in data
        assert "on_time_visits" in data
        assert "late_visits" in data
        assert "missed_visits" in data

    @pytest.mark.anyio
    async def test_get_patient_compliance_unknown_patient(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/PAT-UNKNOWN/compliance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["drug_assignments"] == 0
        assert data["total_visits"] == 0

    def test_patient_compliance_values_in_range(self, svc: IRTService):
        compliance = svc.get_patient_compliance("PAT-0001")
        assert 0.0 <= compliance["avg_drug_compliance_pct"] <= 100.0
        assert 0.0 <= compliance["visit_compliance_rate"] <= 100.0

    def test_patient_compliance_visit_counts_consistent(self, svc: IRTService):
        compliance = svc.get_patient_compliance("PAT-0001")
        total_categorized = (
            compliance["on_time_visits"]
            + compliance["late_visits"]
            + compliance["early_visits"]
            + compliance["missed_visits"]
        )
        # Every visit should have a status category
        assert total_categorized <= compliance["total_visits"]


# =====================================================================
# METRICS
# =====================================================================


class TestIRTMetrics:
    """Test IRT metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_transactions"] == 50
        assert data["active_patients"] >= 0
        assert data["drug_kits_available"] >= 0
        assert data["drug_kits_dispensed"] >= 0
        assert 0 <= data["visit_compliance_rate"] <= 100
        assert 0 <= data["avg_drug_compliance_pct"] <= 100
        assert data["missed_visits_30d"] >= 0

    def test_metrics_transactions_by_type(self, svc: IRTService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.transactions_by_type.values())
        assert total_by_type == metrics.total_transactions

    def test_metrics_drug_kits_consistency(self, svc: IRTService):
        metrics = svc.get_metrics()
        assert metrics.drug_kits_available >= 0
        assert metrics.drug_kits_dispensed >= 0

    def test_metrics_visit_compliance_range(self, svc: IRTService):
        metrics = svc.get_metrics()
        assert 0.0 <= metrics.visit_compliance_rate <= 100.0

    def test_metrics_drug_compliance_range(self, svc: IRTService):
        metrics = svc.get_metrics()
        assert 0.0 <= metrics.avg_drug_compliance_pct <= 100.0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_irt_service()
        svc2 = get_irt_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_irt_service()
        svc2 = reset_irt_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_irt_service()
        # Delete a transaction
        initial_count = len(svc.list_transactions())
        tx = svc.list_transactions()[0]
        with svc._lock:
            del svc._transactions[tx.id]
        assert len(svc.list_transactions()) == initial_count - 1

        # Reset should restore
        svc2 = reset_irt_service()
        assert len(svc2.list_transactions()) == 50


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_transactions_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/transactions")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_drug_assignments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-assignments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_visit_schedules_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visit-schedules")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_drug_kits_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-kits")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_stratification_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stratification")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_transaction_all_types(self, client: AsyncClient):
        for tx_type in IRTTransactionType:
            payload = _make_transaction_create(transaction_type=tx_type.value)
            resp = await client.post(f"{API_PREFIX}/transactions", json=payload)
            assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_create_multiple_drug_assignments(self, client: AsyncClient):
        for i in range(3):
            payload = _make_drug_assignment_create(
                kit_number=f"KIT-MULTI-{i:03d}",
                patient_id=f"PAT-MULTI-{i:03d}",
            )
            resp = await client.post(f"{API_PREFIX}/drug-assignments", json=payload)
            assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_create_visit_schedule_multiple(self, client: AsyncClient):
        for i in range(3):
            payload = _make_visit_schedule_create(
                patient_id=f"PAT-MULTI-{i:03d}",
                visit_number=i + 1,
                visit_name=f"Visit {i + 1}",
            )
            resp = await client.post(f"{API_PREFIX}/visit-schedules", json=payload)
            assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_transaction_has_confirmation_number(self, client: AsyncClient):
        payload = _make_transaction_create()
        resp = await client.post(f"{API_PREFIX}/transactions", json=payload)
        data = resp.json()
        assert data["confirmation_number"].startswith("CNF-")
        assert len(data["confirmation_number"]) > 4

    @pytest.mark.anyio
    async def test_drug_assignment_create_sets_full_compliance(self, client: AsyncClient):
        payload = _make_drug_assignment_create()
        resp = await client.post(f"{API_PREFIX}/drug-assignments", json=payload)
        data = resp.json()
        assert data["compliance_pct"] == 100.0
        assert data["return_date"] is None

    @pytest.mark.anyio
    async def test_visit_schedule_create_sets_on_time(self, client: AsyncClient):
        payload = _make_visit_schedule_create()
        resp = await client.post(f"{API_PREFIX}/visit-schedules", json=payload)
        data = resp.json()
        assert data["window_status"] == "on_time"
        assert data["actual_date"] is None


# =====================================================================
# TRANSACTION TYPE ENUMERATION
# =====================================================================


class TestTransactionTypes:
    """Test all transaction types are represented."""

    @pytest.mark.anyio
    async def test_all_transaction_types_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/transactions")
        data = resp.json()
        types = {item["transaction_type"] for item in data["items"]}
        assert "screening" in types
        assert "randomization" in types
        assert "drug_assignment" in types

    @pytest.mark.anyio
    async def test_transaction_types_in_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "transactions_by_type" in data
        assert len(data["transactions_by_type"]) > 0


# =====================================================================
# DRUG SUPPLY STATUS
# =====================================================================


class TestDrugSupplyStatus:
    """Test drug supply status values."""

    @pytest.mark.anyio
    async def test_available_kits_exist(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/drug-kits", params={"status": "available"}
        )
        data = resp.json()
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_dispensed_kits_exist(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/drug-kits", params={"status": "dispensed"}
        )
        data = resp.json()
        assert data["total"] > 0

    def test_kit_statuses_in_seed(self, svc: IRTService):
        kits = svc.list_drug_kits()
        statuses = {k.status for k in kits}
        assert DrugSupplyStatus.AVAILABLE in statuses


# =====================================================================
# VISIT WINDOW COMPLIANCE
# =====================================================================


class TestVisitWindowCompliance:
    """Test visit window compliance values."""

    @pytest.mark.anyio
    async def test_on_time_visits_exist(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/visit-schedules", params={"window_status": "on_time"}
        )
        data = resp.json()
        assert data["total"] > 0

    def test_visit_window_statuses_in_seed(self, svc: IRTService):
        visits = svc.list_visit_schedules()
        statuses = {v.window_status for v in visits}
        # At minimum, on_time should exist
        assert VisitWindow.ON_TIME in statuses

    def test_visit_window_dates_valid(self, svc: IRTService):
        visits = svc.list_visit_schedules()
        for v in visits:
            assert v.window_open <= v.scheduled_date <= v.window_close


# =====================================================================
# CONFIGURATION DETAILS
# =====================================================================


class TestConfigurationDetails:
    """Test IRT configuration details."""

    @pytest.mark.anyio
    async def test_eylea_config_details(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/configurations/{EYLEA_TRIAL}")
        data = resp.json()
        assert data["randomization_ratio"] == "2:1"
        assert "age_group" in data["stratification_factors"]
        assert len(data["dose_levels"]) == 3

    @pytest.mark.anyio
    async def test_dupixent_config_details(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/configurations/{DUPIXENT_TRIAL}")
        data = resp.json()
        assert data["randomization_ratio"] == "1:1"
        assert data["drug_supply_buffer_weeks"] == 6

    @pytest.mark.anyio
    async def test_libtayo_config_details(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/configurations/{LIBTAYO_TRIAL}")
        data = resp.json()
        assert data["randomization_ratio"] == "1:1:1"
        assert len(data["visit_windows"]) > 0

    @pytest.mark.anyio
    async def test_update_dose_levels(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/configurations/{EYLEA_TRIAL}",
            json={"dose_levels": ["1mg", "2mg", "4mg", "8mg"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["dose_levels"]) == 4
        assert "1mg" in data["dose_levels"]

    @pytest.mark.anyio
    async def test_update_stratification_factors(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/configurations/{EYLEA_TRIAL}",
            json={"stratification_factors": ["age_group", "sex"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["stratification_factors"]) == 2


# =====================================================================
# COMPREHENSIVE WORKFLOW TESTS
# =====================================================================


class TestComprehensiveWorkflow:
    """Test end-to-end IRT workflows."""

    @pytest.mark.anyio
    async def test_screening_to_randomization_workflow(self, client: AsyncClient):
        """Test the screening -> randomization -> drug assignment flow."""
        # Step 1: Screening
        screening = _make_transaction_create(transaction_type="screening")
        resp = await client.post(f"{API_PREFIX}/transactions", json=screening)
        assert resp.status_code == 201

        # Step 2: Randomization
        randomization = _make_transaction_create(transaction_type="randomization")
        resp = await client.post(f"{API_PREFIX}/transactions", json=randomization)
        assert resp.status_code == 201

        # Step 3: Drug Assignment
        drug = _make_drug_assignment_create()
        resp = await client.post(f"{API_PREFIX}/drug-assignments", json=drug)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_resupply_and_accountability_workflow(self, client: AsyncClient):
        """Test drug resupply -> accountability check."""
        # Check initial accountability
        resp = await client.get(f"{API_PREFIX}/sites/SITE-104/drug-accountability")
        initial = resp.json()

        # Request resupply
        payload = {
            "trial_id": EYLEA_TRIAL,
            "site_id": "SITE-104",
            "kit_count": 8,
            "performed_by": "Supply Mgr",
        }
        resp = await client.post(f"{API_PREFIX}/drug-resupply", json=payload)
        assert resp.status_code == 201

        # Check updated accountability
        resp = await client.get(f"{API_PREFIX}/sites/SITE-104/drug-accountability")
        updated = resp.json()
        assert updated["available"] >= initial["available"]

    @pytest.mark.anyio
    async def test_visit_and_compliance_workflow(self, client: AsyncClient, svc: IRTService):
        """Test visit scheduling -> confirmation -> compliance check."""
        # Create a visit schedule
        payload = _make_visit_schedule_create(patient_id="PAT-WORKFLOW")
        resp = await client.post(f"{API_PREFIX}/visit-schedules", json=payload)
        assert resp.status_code == 201
        schedule_id = resp.json()["id"]

        # Confirm the visit on scheduled date
        vs = svc.get_visit_schedule(schedule_id)
        assert vs is not None
        confirm_payload = {"actual_date": vs.scheduled_date.isoformat()}
        resp = await client.post(
            f"{API_PREFIX}/visit-schedules/{schedule_id}/confirm",
            json=confirm_payload,
        )
        assert resp.status_code == 200
        assert resp.json()["window_status"] == "on_time"

    @pytest.mark.anyio
    async def test_discontinuation_workflow(self, client: AsyncClient):
        """Test patient discontinuation flow."""
        payload = _make_transaction_create(
            transaction_type="discontinuation",
            details="Patient withdrew consent",
        )
        resp = await client.post(f"{API_PREFIX}/transactions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert "discontinu" in data["system_response"].lower()
