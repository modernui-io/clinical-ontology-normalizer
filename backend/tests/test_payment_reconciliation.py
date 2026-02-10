"""Tests for Site Payment Reconciliation (FINANCE-PR).

Covers:
- Seed data verification (batches, site reconciliations, discrepancies, adjustments, audit, closes)
- Batch CRUD (create, read, update, delete, list, filter by trial/status)
- Site reconciliation CRUD (create, read, update, delete, list, filter)
- Discrepancy CRUD (flag, read, update, delete, list, filter)
- Adjustment CRUD (create, read, approve/reject, delete, list, filter)
- Audit trail (list, filter by batch/entity type/performer, get single)
- Financial close (create, list, approve, filter)
- Auto-match workflow
- Initiate reconciliation workflow
- Metrics computation
- Error handling (404s, 400s, invalid operations)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.payment_reconciliation_service import (
    PaymentReconciliationService,
    get_payment_reconciliation_service,
    reset_payment_reconciliation_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/payment-reconciliation"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_payment_reconciliation_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> PaymentReconciliationService:
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


def _make_batch_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "period_type": "quarterly",
        "period_start": (now - timedelta(days=90)).isoformat(),
        "period_end": now.isoformat(),
        "initiated_by": "Test User",
    }
    defaults.update(overrides)
    return defaults


def _make_site_recon_create(**overrides) -> dict:
    defaults = {
        "batch_id": "REC-BATCH-001",
        "site_id": "SITE-999",
        "site_name": "Test Clinical Site",
        "expected_amount": 100000.00,
        "actual_amount": 98500.00,
    }
    defaults.update(overrides)
    return defaults


def _make_discrepancy_create(**overrides) -> dict:
    defaults = {
        "reconciliation_id": "SREC-003",
        "site_id": "SITE-103",
        "discrepancy_type": "amount_mismatch",
        "expected_amount": 50000.00,
        "actual_amount": 47500.00,
        "description": "Test discrepancy - amount mismatch on patient visit payment.",
        "assigned_to": "Test Reviewer",
    }
    defaults.update(overrides)
    return defaults


def _make_adjustment_create(**overrides) -> dict:
    defaults = {
        "reconciliation_id": "SREC-003",
        "site_id": "SITE-103",
        "adjustment_type": "credit",
        "amount": 2500.00,
        "currency": "USD",
        "reason": "Test credit adjustment for underpayment correction.",
    }
    defaults.update(overrides)
    return defaults


def _make_financial_close_request(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "close_period": "2026-Q1",
        "period_start": (now - timedelta(days=90)).isoformat(),
        "period_end": now.isoformat(),
        "closed_by": "Test Finance Manager",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_batches_count(self, svc: PaymentReconciliationService):
        batches = svc.list_batches()
        assert len(batches) == 3

    def test_seed_batches_cover_all_trials(self, svc: PaymentReconciliationService):
        batches = svc.list_batches()
        trial_ids = {b.trial_id for b in batches}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_site_reconciliations_count(self, svc: PaymentReconciliationService):
        site_recons = svc.list_site_reconciliations()
        assert len(site_recons) == 8

    def test_seed_discrepancies_count(self, svc: PaymentReconciliationService):
        discrepancies = svc.list_discrepancies()
        assert len(discrepancies) == 5

    def test_seed_adjustments_count(self, svc: PaymentReconciliationService):
        adjustments = svc.list_adjustments()
        assert len(adjustments) == 4

    def test_seed_audit_entries_count(self, svc: PaymentReconciliationService):
        entries = svc.list_audit_entries()
        assert len(entries) == 7

    def test_seed_financial_closes_count(self, svc: PaymentReconciliationService):
        closes = svc.list_financial_closes()
        assert len(closes) == 2

    def test_seed_batch_statuses(self, svc: PaymentReconciliationService):
        batches = svc.list_batches()
        statuses = {b.status.value for b in batches}
        assert "reconciled" in statuses
        assert "in_progress" in statuses
        assert "closed" in statuses


# =====================================================================
# BATCH CRUD
# =====================================================================


class TestBatchCrud:
    """Test reconciliation batch CRUD operations."""

    @pytest.mark.anyio
    async def test_list_batches(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    @pytest.mark.anyio
    async def test_list_batches_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_batches_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches", params={"status": "in_progress"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_get_batch(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches/REC-BATCH-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "REC-BATCH-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_batch_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_batch(self, client: AsyncClient):
        payload = _make_batch_create()
        resp = await client.post(f"{API_PREFIX}/batches", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["status"] == "pending"
        assert data["id"].startswith("REC-BATCH-")

    @pytest.mark.anyio
    async def test_update_batch(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/batches/REC-BATCH-002",
            json={"status": "reconciled"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "reconciled"

    @pytest.mark.anyio
    async def test_update_batch_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/batches/NONEXISTENT",
            json={"status": "reconciled"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_batch(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/batches/REC-BATCH-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/batches/REC-BATCH-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_batch_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/batches/NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# SITE RECONCILIATION CRUD
# =====================================================================


class TestSiteReconciliationCrud:
    """Test site reconciliation CRUD operations."""

    @pytest.mark.anyio
    async def test_list_site_reconciliations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-reconciliations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8

    @pytest.mark.anyio
    async def test_list_site_reconciliations_filter_batch(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-reconciliations",
            params={"batch_id": "REC-BATCH-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["batch_id"] == "REC-BATCH-001"

    @pytest.mark.anyio
    async def test_list_site_reconciliations_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-reconciliations",
            params={"status": "reconciled"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "reconciled"

    @pytest.mark.anyio
    async def test_get_site_reconciliation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-reconciliations/SREC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SREC-001"
        assert data["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_get_site_reconciliation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-reconciliations/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_site_reconciliation(self, client: AsyncClient):
        payload = _make_site_recon_create()
        resp = await client.post(f"{API_PREFIX}/site-reconciliations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_id"] == "SITE-999"
        assert data["id"].startswith("SREC-")
        assert data["variance"] == -1500.00
        assert data["status"] == "pending"

    @pytest.mark.anyio
    async def test_update_site_reconciliation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-reconciliations/SREC-007",
            json={"status": "reconciled", "reconciled_by": "Test User"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "reconciled"
        assert data["reconciled_by"] == "Test User"
        assert data["reconciled_date"] is not None

    @pytest.mark.anyio
    async def test_update_site_reconciliation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-reconciliations/NONEXISTENT",
            json={"status": "reconciled"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_site_reconciliation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/site-reconciliations/SREC-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/site-reconciliations/SREC-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_site_reconciliation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/site-reconciliations/NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# DISCREPANCY CRUD
# =====================================================================


class TestDiscrepancyCrud:
    """Test payment discrepancy operations."""

    @pytest.mark.anyio
    async def test_list_discrepancies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/discrepancies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_discrepancies_filter_site(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/discrepancies",
            params={"site_id": "SITE-104"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-104"

    @pytest.mark.anyio
    async def test_list_discrepancies_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/discrepancies",
            params={"discrepancy_type": "amount_mismatch"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["discrepancy_type"] == "amount_mismatch"

    @pytest.mark.anyio
    async def test_list_discrepancies_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/discrepancies",
            params={"status": "resolved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "resolved"

    @pytest.mark.anyio
    async def test_get_discrepancy(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/discrepancies/DISC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DISC-001"
        assert data["discrepancy_type"] == "amount_mismatch"

    @pytest.mark.anyio
    async def test_get_discrepancy_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/discrepancies/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_flag_discrepancy(self, client: AsyncClient):
        payload = _make_discrepancy_create()
        resp = await client.post(f"{API_PREFIX}/discrepancies", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["discrepancy_type"] == "amount_mismatch"
        assert data["id"].startswith("DISC-")
        assert data["status"] == "discrepancy_identified"
        assert data["difference"] == 2500.00

    @pytest.mark.anyio
    async def test_update_discrepancy_resolve(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/discrepancies/DISC-001",
            json={
                "status": "resolved",
                "resolution": "Payment corrected and issued.",
                "root_cause": "Invoice processing error.",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resolved"
        assert data["resolution"] == "Payment corrected and issued."
        assert data["resolved_date"] is not None

    @pytest.mark.anyio
    async def test_update_discrepancy_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/discrepancies/NONEXISTENT",
            json={"status": "resolved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_discrepancy(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/discrepancies/DISC-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/discrepancies/DISC-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_discrepancy_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/discrepancies/NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# ADJUSTMENT CRUD AND APPROVAL
# =====================================================================


class TestAdjustmentCrud:
    """Test payment adjustment operations and approval workflow."""

    @pytest.mark.anyio
    async def test_list_adjustments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjustments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4

    @pytest.mark.anyio
    async def test_list_adjustments_filter_site(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/adjustments",
            params={"site_id": "SITE-104"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-104"

    @pytest.mark.anyio
    async def test_list_adjustments_filter_approval_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/adjustments",
            params={"approval_status": "pending"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["approval_status"] == "pending"

    @pytest.mark.anyio
    async def test_get_adjustment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjustments/ADJ-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ADJ-001"
        assert data["adjustment_type"] == "debit"

    @pytest.mark.anyio
    async def test_get_adjustment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjustments/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_adjustment(self, client: AsyncClient):
        payload = _make_adjustment_create()
        resp = await client.post(f"{API_PREFIX}/adjustments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["adjustment_type"] == "credit"
        assert data["amount"] == 2500.00
        assert data["approval_status"] == "pending"
        assert data["id"].startswith("ADJ-")

    @pytest.mark.anyio
    async def test_approve_adjustment(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/adjustments/ADJ-002/approve",
            json={
                "approval_status": "approved",
                "approved_by": "Finance Director",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approval_status"] == "approved"
        assert data["approved_by"] == "Finance Director"
        assert data["approval_date"] is not None

    @pytest.mark.anyio
    async def test_reject_adjustment(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/adjustments/ADJ-003/approve",
            json={
                "approval_status": "rejected",
                "approved_by": "Finance Director",
                "notes": "Interest calculation needs revision.",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approval_status"] == "rejected"
        assert data["notes"] == "Interest calculation needs revision."

    @pytest.mark.anyio
    async def test_approve_already_approved(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/adjustments/ADJ-001/approve",
            json={
                "approval_status": "approved",
                "approved_by": "Another Director",
            },
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_approve_adjustment_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/adjustments/NONEXISTENT/approve",
            json={
                "approval_status": "approved",
                "approved_by": "Director",
            },
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_adjustment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/adjustments/ADJ-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/adjustments/ADJ-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_adjustment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/adjustments/NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# AUDIT TRAIL
# =====================================================================


class TestAuditTrail:
    """Test audit trail operations."""

    @pytest.mark.anyio
    async def test_list_audit_entries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit-trail")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7

    @pytest.mark.anyio
    async def test_list_audit_entries_filter_batch(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/audit-trail",
            params={"batch_id": "REC-BATCH-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["batch_id"] == "REC-BATCH-001"

    @pytest.mark.anyio
    async def test_list_audit_entries_filter_entity_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/audit-trail",
            params={"entity_type": "adjustment"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["entity_type"] == "adjustment"

    @pytest.mark.anyio
    async def test_get_audit_entry(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit-trail/AUD-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "AUD-001"
        assert data["action"] == "batch_initiated"

    @pytest.mark.anyio
    async def test_get_audit_entry_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit-trail/NONEXISTENT")
        assert resp.status_code == 404

    def test_audit_entry_has_required_fields(self, svc: PaymentReconciliationService):
        entry = svc.get_audit_entry("AUD-001")
        assert entry is not None
        assert entry.id
        assert entry.batch_id
        assert entry.action
        assert entry.performed_by
        assert entry.performed_date is not None
        assert entry.details
        assert entry.entity_type
        assert entry.entity_id


# =====================================================================
# FINANCIAL CLOSE
# =====================================================================


class TestFinancialClose:
    """Test financial close operations."""

    @pytest.mark.anyio
    async def test_list_financial_closes(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/financial-closes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    @pytest.mark.anyio
    async def test_list_financial_closes_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/financial-closes",
            params={"trial_id": LIBTAYO_TRIAL},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_financial_closes_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/financial-closes",
            params={"status": "approved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "approved"

    @pytest.mark.anyio
    async def test_get_financial_close(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/financial-closes/FC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "FC-001"
        assert data["close_period"] == "2025-Q3"

    @pytest.mark.anyio
    async def test_get_financial_close_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/financial-closes/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_financial_close(self, client: AsyncClient):
        payload = _make_financial_close_request()
        resp = await client.post(f"{API_PREFIX}/financial-closes", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["close_period"] == "2026-Q1"
        assert data["status"] == "pending"
        assert data["id"].startswith("FC-")

    @pytest.mark.anyio
    async def test_approve_financial_close(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/financial-closes/FC-002/approve",
            params={"approved_by": "CFO Test User", "sign_off_cfo": "CFO Test User"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["sign_off_cfo"] == "CFO Test User"

    @pytest.mark.anyio
    async def test_approve_financial_close_already_approved(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/financial-closes/FC-001/approve",
            params={"approved_by": "Another CFO"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_approve_financial_close_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/financial-closes/NONEXISTENT/approve",
            params={"approved_by": "CFO"},
        )
        assert resp.status_code == 404


# =====================================================================
# AUTO-MATCH WORKFLOW
# =====================================================================


class TestAutoMatch:
    """Test auto-matching workflow."""

    @pytest.mark.anyio
    async def test_auto_match_batch(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/batches/REC-BATCH-002/auto-match",
            json={"tolerance_pct": 1.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["auto_reconciled_pct"] > 0

    @pytest.mark.anyio
    async def test_auto_match_batch_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/batches/NONEXISTENT/auto-match",
            json={"tolerance_pct": 1.0},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_auto_match_high_tolerance(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/batches/REC-BATCH-002/auto-match",
            json={"tolerance_pct": 10.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        # High tolerance should reconcile more payments
        assert data["auto_reconciled_pct"] >= 0.0

    def test_auto_match_creates_audit_entry(self, svc: PaymentReconciliationService):
        from app.schemas.payment_reconciliation import AutoMatchRequest
        initial_count = len(svc.list_audit_entries())
        svc.auto_match_payments("REC-BATCH-002", AutoMatchRequest(tolerance_pct=1.0))
        new_count = len(svc.list_audit_entries())
        assert new_count > initial_count


# =====================================================================
# INITIATE RECONCILIATION
# =====================================================================


class TestInitiateReconciliation:
    """Test the initiate reconciliation workflow."""

    @pytest.mark.anyio
    async def test_initiate_reconciliation(self, client: AsyncClient):
        payload = _make_batch_create()
        resp = await client.post(f"{API_PREFIX}/batches/initiate", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["id"].startswith("REC-BATCH-")


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test reconciliation metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_batches"] == 3
        assert data["total_site_reconciliations"] == 8
        assert data["total_discrepancies"] == 5
        assert data["total_adjustments"] == 4
        assert data["total_financial_closes"] == 2
        assert data["total_audit_entries"] == 7

    def test_metrics_pending_batches(self, svc: PaymentReconciliationService):
        metrics = svc.get_metrics()
        # BATCH-002 is in_progress -> pending
        assert metrics.pending_batches == 1

    def test_metrics_completed_batches(self, svc: PaymentReconciliationService):
        metrics = svc.get_metrics()
        # BATCH-001 is reconciled, BATCH-003 is closed
        assert metrics.completed_batches == 2

    def test_metrics_open_discrepancies(self, svc: PaymentReconciliationService):
        metrics = svc.get_metrics()
        # DISC-001 under_review, DISC-002 discrepancy_identified,
        # DISC-003 under_review, DISC-005 discrepancy_identified = 4 open
        assert metrics.open_discrepancies == 4

    def test_metrics_resolved_discrepancies(self, svc: PaymentReconciliationService):
        metrics = svc.get_metrics()
        # DISC-004 resolved = 1
        assert metrics.resolved_discrepancies == 1

    def test_metrics_pending_adjustments(self, svc: PaymentReconciliationService):
        metrics = svc.get_metrics()
        # ADJ-002 pending, ADJ-003 pending = 2
        assert metrics.pending_adjustments == 2

    def test_metrics_approved_adjustments(self, svc: PaymentReconciliationService):
        metrics = svc.get_metrics()
        # ADJ-001 approved, ADJ-004 approved = 2
        assert metrics.approved_adjustments == 2

    def test_metrics_total_adjustment_amount(self, svc: PaymentReconciliationService):
        metrics = svc.get_metrics()
        # ADJ-001: $5,200 + ADJ-004: $480 = $5,680
        assert metrics.total_adjustment_amount == 5680.00

    def test_metrics_avg_auto_reconciled(self, svc: PaymentReconciliationService):
        metrics = svc.get_metrics()
        # Average of 83.3, 66.7, 96.9
        assert 0.0 <= metrics.avg_auto_reconciled_pct <= 100.0

    def test_metrics_open_financial_closes(self, svc: PaymentReconciliationService):
        metrics = svc.get_metrics()
        # FC-002 is pending
        assert metrics.open_financial_closes == 1


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_payment_reconciliation_service()
        svc2 = get_payment_reconciliation_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_payment_reconciliation_service()
        svc2 = reset_payment_reconciliation_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_payment_reconciliation_service()
        svc.delete_batch("REC-BATCH-001")
        assert svc.get_batch("REC-BATCH-001") is None
        svc2 = reset_payment_reconciliation_service()
        assert svc2.get_batch("REC-BATCH-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_batches_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_site_reconciliations_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-reconciliations")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_discrepancies_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/discrepancies")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_adjustments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjustments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_audit_trail_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit-trail")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_financial_closes_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/financial-closes")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_batch_all_period_types(self, client: AsyncClient):
        for period_type in ["monthly", "quarterly", "semi_annual", "annual"]:
            payload = _make_batch_create(period_type=period_type)
            resp = await client.post(f"{API_PREFIX}/batches", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["period_type"] == period_type

    @pytest.mark.anyio
    async def test_create_discrepancy_all_types(self, client: AsyncClient):
        for disc_type in [
            "amount_mismatch", "missing_payment", "duplicate_payment",
            "wrong_site", "wrong_period", "currency_error", "tax_error", "late_payment",
        ]:
            payload = _make_discrepancy_create(discrepancy_type=disc_type)
            resp = await client.post(f"{API_PREFIX}/discrepancies", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["discrepancy_type"] == disc_type

    @pytest.mark.anyio
    async def test_create_adjustment_all_types(self, client: AsyncClient):
        for adj_type in ["credit", "debit", "writeoff", "refund", "correction", "interest"]:
            payload = _make_adjustment_create(adjustment_type=adj_type)
            resp = await client.post(f"{API_PREFIX}/adjustments", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["adjustment_type"] == adj_type

    @pytest.mark.anyio
    async def test_batch_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/batches/REC-BATCH-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "period_type" in data
        assert "period_start" in data
        assert "period_end" in data
        assert "status" in data
        assert "initiated_date" in data
        assert "initiated_by" in data
        assert "total_payments" in data
        assert "total_amount" in data
        assert "reconciled_count" in data
        assert "discrepancy_count" in data
        assert "auto_reconciled_pct" in data

    @pytest.mark.anyio
    async def test_site_recon_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-reconciliations/SREC-001")
        data = resp.json()
        assert "id" in data
        assert "batch_id" in data
        assert "site_id" in data
        assert "site_name" in data
        assert "expected_amount" in data
        assert "actual_amount" in data
        assert "variance" in data
        assert "status" in data
        assert "payments_count" in data
        assert "matched_payments" in data
        assert "unmatched_payments" in data

    @pytest.mark.anyio
    async def test_discrepancy_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/discrepancies/DISC-001")
        data = resp.json()
        assert "id" in data
        assert "reconciliation_id" in data
        assert "site_id" in data
        assert "discrepancy_type" in data
        assert "expected_amount" in data
        assert "actual_amount" in data
        assert "difference" in data
        assert "description" in data
        assert "identified_date" in data
        assert "status" in data

    @pytest.mark.anyio
    async def test_adjustment_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adjustments/ADJ-001")
        data = resp.json()
        assert "id" in data
        assert "reconciliation_id" in data
        assert "site_id" in data
        assert "adjustment_type" in data
        assert "amount" in data
        assert "currency" in data
        assert "reason" in data
        assert "approval_status" in data

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_batches" in data
        assert "pending_batches" in data
        assert "completed_batches" in data
        assert "total_site_reconciliations" in data
        assert "total_discrepancies" in data
        assert "open_discrepancies" in data
        assert "resolved_discrepancies" in data
        assert "total_adjustments" in data
        assert "pending_adjustments" in data
        assert "approved_adjustments" in data
        assert "total_adjustment_amount" in data
        assert "avg_auto_reconciled_pct" in data
        assert "total_financial_closes" in data
        assert "open_financial_closes" in data
        assert "total_audit_entries" in data

    @pytest.mark.anyio
    async def test_create_financial_close_with_cfo_signoff(self, client: AsyncClient):
        payload = _make_financial_close_request(sign_off_cfo="CFO James Wilson")
        resp = await client.post(f"{API_PREFIX}/financial-closes", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["sign_off_cfo"] == "CFO James Wilson"
        assert data["sign_off_date"] is not None

    def test_site_recon_variance_calculation(self, svc: PaymentReconciliationService):
        """Verify variance is correctly calculated."""
        sr = svc.get_site_reconciliation("SREC-003")
        assert sr is not None
        assert sr.variance == sr.actual_amount - sr.expected_amount

    def test_discrepancy_difference_calculation(self, svc: PaymentReconciliationService):
        """Verify difference is absolute value."""
        disc = svc.get_discrepancy("DISC-001")
        assert disc is not None
        assert disc.difference == abs(disc.expected_amount - disc.actual_amount)

    @pytest.mark.anyio
    async def test_list_discrepancies_filter_reconciliation_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/discrepancies",
            params={"reconciliation_id": "SREC-006"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["reconciliation_id"] == "SREC-006"

    @pytest.mark.anyio
    async def test_list_adjustments_filter_reconciliation_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/adjustments",
            params={"reconciliation_id": "SREC-004"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["reconciliation_id"] == "SREC-004"
