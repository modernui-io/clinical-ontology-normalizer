"""Tests for Clinical Site Payments & Grant Management (CLINICAL-21).

Covers:
- Seed data verification (grants, line items, invoices)
- Grant CRUD (create, read, update, delete, list, filter by trial/site/currency)
- Payment line item CRUD (create, read, update, delete, list, filter by grant/site/type/status/patient)
- Invoice CRUD (create, read, update, delete, list, filter by site/trial/status)
- Invoice lifecycle (approve, pay, auto-date setting)
- Site payment summaries (per-site and all sites)
- Overdue payment detection
- Payment metrics computation
- Payment type distribution
- Holdback calculations
- Error handling (404s, 400s, invalid operations)
- Edge cases (empty filters, boundary conditions, protocol deviation credits)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.site_payments import (
    CurrencyCode,
    PaymentScheduleType,
    PaymentStatus,
    PaymentType,
)
from app.services.site_payments_service import (
    SitePaymentsService,
    get_site_payments_service,
    reset_site_payments_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/site-payments"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_site_payments_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> SitePaymentsService:
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


def _make_grant_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-NEW",
        "site_name": "New Test Site",
        "total_budget": 300000.0,
        "currency": "USD",
        "payment_schedule_type": "monthly",
        "per_patient_amount": 3500.0,
        "screen_failure_amount": 750.0,
        "startup_fee": 20000.0,
        "annual_fee": 10000.0,
        "holdback_pct": 10.0,
        "effective_date": now.isoformat(),
        "end_date": (now + timedelta(days=365)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_line_item_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "grant_id": "GRT-001",
        "site_id": "SITE-101",
        "patient_id": "PAT-TEST-001",
        "payment_type": "per_patient",
        "description": "Test per-patient payment",
        "amount": 3500.0,
        "currency": "USD",
        "accrual_date": now.isoformat(),
        "visit_number": 1,
    }
    defaults.update(overrides)
    return defaults


def _make_invoice_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "site_id": "SITE-101",
        "trial_id": EYLEA_TRIAL,
        "invoice_number": "TEST-INV-001",
        "period_start": (now - timedelta(days=90)).isoformat(),
        "period_end": now.isoformat(),
        "line_item_ids": [],
        "tax": 0.0,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_grants_count(self, svc: SitePaymentsService):
        grants = svc.list_grants()
        assert len(grants) == 8

    def test_seed_grants_cover_all_trials(self, svc: SitePaymentsService):
        grants = svc.list_grants()
        trial_ids = {g.trial_id for g in grants}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_grants_cover_all_sites(self, svc: SitePaymentsService):
        grants = svc.list_grants()
        site_ids = {g.site_id for g in grants}
        for i in range(101, 109):
            assert f"SITE-{i}" in site_ids

    def test_seed_line_items_count(self, svc: SitePaymentsService):
        items = svc.list_line_items()
        assert len(items) == 60

    def test_seed_invoices_count(self, svc: SitePaymentsService):
        invoices = svc.list_invoices()
        assert len(invoices) == 12

    def test_seed_has_per_patient_payments(self, svc: SitePaymentsService):
        items = svc.list_line_items(payment_type=PaymentType.PER_PATIENT)
        assert len(items) == 24

    def test_seed_has_startup_fees(self, svc: SitePaymentsService):
        items = svc.list_line_items(payment_type=PaymentType.STARTUP_FEE)
        assert len(items) == 8

    def test_seed_has_screen_failure_fees(self, svc: SitePaymentsService):
        items = svc.list_line_items(payment_type=PaymentType.SCREEN_FAILURE_FEE)
        assert len(items) == 6

    def test_seed_has_milestone_payments(self, svc: SitePaymentsService):
        items = svc.list_line_items(payment_type=PaymentType.MILESTONE)
        assert len(items) == 4

    def test_seed_has_pass_through_costs(self, svc: SitePaymentsService):
        items = svc.list_line_items(payment_type=PaymentType.PASS_THROUGH)
        # 5 regular + 1 disputed
        assert len(items) == 6

    def test_seed_has_protocol_deviation_credits(self, svc: SitePaymentsService):
        items = svc.list_line_items(payment_type=PaymentType.PROTOCOL_DEVIATION_CREDIT)
        assert len(items) == 3

    def test_seed_has_holdback_release(self, svc: SitePaymentsService):
        items = svc.list_line_items(payment_type=PaymentType.HOLDBACK_RELEASE)
        assert len(items) == 1

    def test_seed_has_annual_fees(self, svc: SitePaymentsService):
        items = svc.list_line_items(payment_type=PaymentType.ANNUAL_FEE)
        assert len(items) == 8

    def test_seed_has_disputed_item(self, svc: SitePaymentsService):
        items = svc.list_line_items(status=PaymentStatus.DISPUTED)
        assert len(items) == 1

    def test_seed_eylea_per_patient_rate(self, svc: SitePaymentsService):
        items = svc.list_line_items(grant_id="GRT-001", payment_type=PaymentType.PER_PATIENT)
        for item in items:
            assert item.amount == 3500.0

    def test_seed_dupixent_per_patient_rate(self, svc: SitePaymentsService):
        items = svc.list_line_items(grant_id="GRT-003", payment_type=PaymentType.PER_PATIENT)
        for item in items:
            assert item.amount == 2800.0

    def test_seed_libtayo_per_patient_rate(self, svc: SitePaymentsService):
        items = svc.list_line_items(grant_id="GRT-005", payment_type=PaymentType.PER_PATIENT)
        for item in items:
            assert item.amount == 4200.0

    def test_seed_eur_grant_exists(self, svc: SitePaymentsService):
        grants = svc.list_grants(currency=CurrencyCode.EUR)
        assert len(grants) >= 1
        assert grants[0].site_id == "SITE-107"

    def test_seed_paid_invoices_have_dates(self, svc: SitePaymentsService):
        invoices = svc.list_invoices(status=PaymentStatus.PAID)
        for inv in invoices:
            assert inv.paid_date is not None
            assert inv.approved_date is not None


# =====================================================================
# GRANT CRUD
# =====================================================================


class TestGrantCrud:
    """Test grant create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_grants(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/grants")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8
        assert len(data["items"]) == 8

    @pytest.mark.anyio
    async def test_list_grants_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/grants", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_grants_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/grants", params={"site_id": "SITE-101"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_grants_filter_currency(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/grants", params={"currency": "EUR"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["currency"] == "EUR"

    @pytest.mark.anyio
    async def test_get_grant(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/grants/GRT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "GRT-001"
        assert data["site_name"] == "Memorial Hermann Hospital"

    @pytest.mark.anyio
    async def test_get_grant_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/grants/GRT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_grant(self, client: AsyncClient):
        payload = _make_grant_create()
        resp = await client.post(f"{API_PREFIX}/grants", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_name"] == "New Test Site"
        assert data["id"].startswith("GRT-")
        assert data["amendment_count"] == 0

    @pytest.mark.anyio
    async def test_update_grant(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/grants/GRT-001",
            json={"total_budget": 600000.0, "per_patient_amount": 4000.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_budget"] == 600000.0
        assert data["per_patient_amount"] == 4000.0
        assert data["amendment_count"] == 2  # was 1, incremented

    @pytest.mark.anyio
    async def test_update_grant_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/grants/GRT-NONEXISTENT",
            json={"total_budget": 100000.0},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_grant(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/grants/GRT-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/grants/GRT-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_grant_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/grants/GRT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_grant_amendment_count_increments(self, client: AsyncClient):
        # First update
        resp1 = await client.put(
            f"{API_PREFIX}/grants/GRT-002",
            json={"total_budget": 700000.0},
        )
        assert resp1.status_code == 200
        assert resp1.json()["amendment_count"] == 1  # was 0

        # Second update
        resp2 = await client.put(
            f"{API_PREFIX}/grants/GRT-002",
            json={"total_budget": 750000.0},
        )
        assert resp2.status_code == 200
        assert resp2.json()["amendment_count"] == 2


# =====================================================================
# PAYMENT LINE ITEM CRUD
# =====================================================================


class TestLineItemCrud:
    """Test payment line item CRUD operations."""

    @pytest.mark.anyio
    async def test_list_line_items(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-items")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 60

    @pytest.mark.anyio
    async def test_list_line_items_filter_grant(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-items", params={"grant_id": "GRT-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["grant_id"] == "GRT-001"

    @pytest.mark.anyio
    async def test_list_line_items_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-items", params={"site_id": "SITE-101"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_line_items_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/line-items", params={"payment_type": "per_patient"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 24
        for item in data["items"]:
            assert item["payment_type"] == "per_patient"

    @pytest.mark.anyio
    async def test_list_line_items_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/line-items", params={"status": "paid"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "paid"

    @pytest.mark.anyio
    async def test_list_line_items_filter_patient(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/line-items", params={"patient_id": "PAT-1001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["patient_id"] == "PAT-1001"

    @pytest.mark.anyio
    async def test_get_line_item(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-items/PLI-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PLI-0001"
        assert data["payment_type"] == "startup_fee"

    @pytest.mark.anyio
    async def test_get_line_item_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-items/PLI-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_line_item(self, client: AsyncClient):
        payload = _make_line_item_create()
        resp = await client.post(f"{API_PREFIX}/line-items", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["payment_type"] == "per_patient"
        assert data["amount"] == 3500.0
        assert data["status"] == "accrued"
        assert data["id"].startswith("PLI-")

    @pytest.mark.anyio
    async def test_create_line_item_invalid_grant(self, client: AsyncClient):
        payload = _make_line_item_create(grant_id="GRT-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/line-items", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_line_item_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/line-items/PLI-0017",
            json={"status": "approved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"

    @pytest.mark.anyio
    async def test_update_line_item_auto_payment_date(self, client: AsyncClient):
        # Create a fresh line item first
        payload = _make_line_item_create()
        create_resp = await client.post(f"{API_PREFIX}/line-items", json=payload)
        item_id = create_resp.json()["id"]

        # Pay it
        resp = await client.put(
            f"{API_PREFIX}/line-items/{item_id}",
            json={"status": "paid"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "paid"
        assert data["payment_date"] is not None

    @pytest.mark.anyio
    async def test_update_line_item_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/line-items/PLI-NONEXISTENT",
            json={"status": "paid"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_line_item(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/line-items/PLI-0060")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/line-items/PLI-0060")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_line_item_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/line-items/PLI-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# INVOICE CRUD
# =====================================================================


class TestInvoiceCrud:
    """Test invoice CRUD operations."""

    @pytest.mark.anyio
    async def test_list_invoices(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/invoices")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_invoices_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/invoices", params={"site_id": "SITE-101"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_invoices_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/invoices", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_invoices_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/invoices", params={"status": "paid"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "paid"

    @pytest.mark.anyio
    async def test_get_invoice(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/invoices/INV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "INV-001"
        assert data["invoice_number"] == "MHH-2025-Q3-001"

    @pytest.mark.anyio
    async def test_get_invoice_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/invoices/INV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_invoice(self, client: AsyncClient):
        payload = _make_invoice_create()
        resp = await client.post(f"{API_PREFIX}/invoices", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["invoice_number"] == "TEST-INV-001"
        assert data["status"] == "invoice_received"
        assert data["id"].startswith("INV-")

    @pytest.mark.anyio
    async def test_create_invoice_with_line_items(self, client: AsyncClient):
        payload = _make_invoice_create(line_item_ids=["PLI-0001", "PLI-0017"])
        resp = await client.post(f"{API_PREFIX}/invoices", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["subtotal"] > 0
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_update_invoice(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/invoices/INV-010",
            json={"status": "under_review"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "under_review"

    @pytest.mark.anyio
    async def test_update_invoice_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/invoices/INV-NONEXISTENT",
            json={"status": "approved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_invoice(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/invoices/INV-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/invoices/INV-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_invoice_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/invoices/INV-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# INVOICE LIFECYCLE
# =====================================================================


class TestInvoiceLifecycle:
    """Test invoice approve and pay operations."""

    @pytest.mark.anyio
    async def test_approve_invoice(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/invoices/INV-010/approve")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["approved_date"] is not None

    @pytest.mark.anyio
    async def test_approve_invoice_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/invoices/INV-NONEXISTENT/approve")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_approve_already_approved(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/invoices/INV-005/approve")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_approve_already_paid(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/invoices/INV-001/approve")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_pay_invoice(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/invoices/INV-005/pay")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "paid"
        assert data["paid_date"] is not None

    @pytest.mark.anyio
    async def test_pay_invoice_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/invoices/INV-NONEXISTENT/pay")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_pay_already_paid(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/invoices/INV-001/pay")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_pay_unapproved_invoice_auto_approves(self, client: AsyncClient):
        # INV-010 is invoice_received (not yet approved)
        resp = await client.post(f"{API_PREFIX}/invoices/INV-010/pay")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "paid"
        assert data["approved_date"] is not None
        assert data["paid_date"] is not None

    @pytest.mark.anyio
    async def test_invoice_full_lifecycle(self, client: AsyncClient):
        # Create
        payload = _make_invoice_create()
        resp = await client.post(f"{API_PREFIX}/invoices", json=payload)
        assert resp.status_code == 201
        inv_id = resp.json()["id"]
        assert resp.json()["status"] == "invoice_received"

        # Approve
        resp2 = await client.post(f"{API_PREFIX}/invoices/{inv_id}/approve")
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "approved"

        # Pay
        resp3 = await client.post(f"{API_PREFIX}/invoices/{inv_id}/pay")
        assert resp3.status_code == 200
        assert resp3.json()["status"] == "paid"

    def test_approve_invoice_service_level(self, svc: SitePaymentsService):
        result = svc.approve_invoice("INV-012")
        assert result is not None
        assert result.status == PaymentStatus.APPROVED
        assert result.approved_date is not None

    def test_pay_invoice_service_level(self, svc: SitePaymentsService):
        result = svc.pay_invoice("INV-012")
        assert result is not None
        assert result.status == PaymentStatus.PAID
        assert result.paid_date is not None


# =====================================================================
# SITE PAYMENT SUMMARIES
# =====================================================================


class TestSitePaymentSummaries:
    """Test site payment summary computation."""

    @pytest.mark.anyio
    async def test_get_site_summary(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-101/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["site_id"] == "SITE-101"
        assert data["total_accrued"] > 0
        assert data["total_paid"] > 0
        assert data["patients_enrolled"] > 0
        assert len(data["payments_by_type"]) > 0

    @pytest.mark.anyio
    async def test_get_site_summary_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-NONEXISTENT/summary")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_site_summaries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/summaries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8

    @pytest.mark.anyio
    async def test_site_summary_has_holdback(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-101/summary")
        data = resp.json()
        assert data["holdback_amount"] > 0

    @pytest.mark.anyio
    async def test_site_summary_outstanding_calculation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-101/summary")
        data = resp.json()
        expected_outstanding = round(data["total_accrued"] - data["total_paid"], 2)
        assert data["total_outstanding"] == expected_outstanding

    def test_site_summary_payments_by_type(self, svc: SitePaymentsService):
        summary = svc.get_site_summary("SITE-101")
        assert summary is not None
        assert "startup_fee" in summary.payments_by_type
        assert "per_patient" in summary.payments_by_type

    def test_site_summary_patient_count(self, svc: SitePaymentsService):
        summary = svc.get_site_summary("SITE-101")
        assert summary is not None
        # SITE-101 has PAT-1001, PAT-1002, PAT-1003 per-patient payments
        assert summary.patients_enrolled >= 2

    def test_all_summaries_have_site_names(self, svc: SitePaymentsService):
        summaries = svc.list_site_summaries()
        for s in summaries:
            assert s.site_name
            assert len(s.site_name) > 0


# =====================================================================
# OVERDUE PAYMENTS
# =====================================================================


class TestOverduePayments:
    """Test overdue payment detection."""

    @pytest.mark.anyio
    async def test_get_overdue_payments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/overdue")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["items"], list)

    def test_overdue_items_are_unpaid(self, svc: SitePaymentsService):
        overdue = svc.get_overdue_payments()
        for item in overdue:
            assert item.status != PaymentStatus.PAID
            assert item.status != PaymentStatus.WRITTEN_OFF

    def test_overdue_items_are_old(self, svc: SitePaymentsService):
        now = datetime.now(timezone.utc)
        overdue = svc.get_overdue_payments()
        for item in overdue:
            age_days = (now - item.accrual_date).days
            assert age_days > 90

    def test_overdue_items_sorted_by_accrual(self, svc: SitePaymentsService):
        overdue = svc.get_overdue_payments()
        if len(overdue) > 1:
            dates = [item.accrual_date for item in overdue]
            assert dates == sorted(dates)


# =====================================================================
# PAYMENT METRICS
# =====================================================================


class TestPaymentMetrics:
    """Test aggregated payment metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_grants"] == 8
        assert data["total_accrued_amount"] > 0
        assert data["total_paid_amount"] > 0
        assert data["avg_payment_cycle_days"] >= 0
        assert data["holdback_total"] > 0

    def test_metrics_total_accrued(self, svc: SitePaymentsService):
        metrics = svc.get_metrics()
        items = svc.list_line_items()
        expected_total = round(sum(li.amount for li in items), 2)
        assert metrics.total_accrued_amount == expected_total

    def test_metrics_total_paid(self, svc: SitePaymentsService):
        metrics = svc.get_metrics()
        items = svc.list_line_items(status=PaymentStatus.PAID)
        expected_paid = round(sum(li.amount for li in items), 2)
        assert metrics.total_paid_amount == expected_paid

    def test_metrics_overdue_matches_list(self, svc: SitePaymentsService):
        metrics = svc.get_metrics()
        overdue = svc.get_overdue_payments()
        assert metrics.overdue_payments == len(overdue)

    def test_metrics_holdback_positive(self, svc: SitePaymentsService):
        metrics = svc.get_metrics()
        assert metrics.holdback_total > 0

    def test_metrics_avg_cycle_realistic(self, svc: SitePaymentsService):
        metrics = svc.get_metrics()
        assert 0 <= metrics.avg_payment_cycle_days <= 365

    def test_metrics_sites_with_outstanding(self, svc: SitePaymentsService):
        metrics = svc.get_metrics()
        assert metrics.sites_with_outstanding >= 0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_site_payments_service()
        svc2 = get_site_payments_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_site_payments_service()
        svc2 = reset_site_payments_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_site_payments_service()
        # Delete a grant
        svc.delete_grant("GRT-001")
        assert svc.get_grant("GRT-001") is None
        # Reset should bring it back
        svc2 = reset_site_payments_service()
        assert svc2.get_grant("GRT-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_grants_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/grants")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_line_items_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-items")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_invoices_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/invoices")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_grant_with_all_fields(self, client: AsyncClient):
        payload = _make_grant_create(
            site_name="Full Grant Site",
            total_budget=500000.0,
            currency="EUR",
            payment_schedule_type="quarterly",
            per_patient_amount=4000.0,
            screen_failure_amount=800.0,
            startup_fee=30000.0,
            annual_fee=15000.0,
            holdback_pct=15.0,
        )
        resp = await client.post(f"{API_PREFIX}/grants", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["currency"] == "EUR"
        assert data["payment_schedule_type"] == "quarterly"

    @pytest.mark.anyio
    async def test_create_line_item_milestone(self, client: AsyncClient):
        payload = _make_line_item_create(
            payment_type="milestone",
            description="Test milestone payment",
            amount=15000.0,
            patient_id=None,
            visit_number=None,
        )
        resp = await client.post(f"{API_PREFIX}/line-items", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["payment_type"] == "milestone"

    @pytest.mark.anyio
    async def test_create_line_item_screen_failure(self, client: AsyncClient):
        payload = _make_line_item_create(
            payment_type="screen_failure_fee",
            description="Screen failure reimbursement",
            amount=750.0,
        )
        resp = await client.post(f"{API_PREFIX}/line-items", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["payment_type"] == "screen_failure_fee"

    @pytest.mark.anyio
    async def test_create_line_item_protocol_deviation_credit(self, client: AsyncClient):
        payload = _make_line_item_create(
            payment_type="protocol_deviation_credit",
            description="Protocol deviation credit",
            amount=-500.0,
            patient_id=None,
            visit_number=None,
        )
        resp = await client.post(f"{API_PREFIX}/line-items", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["payment_type"] == "protocol_deviation_credit"
        assert data["amount"] == -500.0

    def test_protocol_deviation_credits_are_negative(self, svc: SitePaymentsService):
        items = svc.list_line_items(payment_type=PaymentType.PROTOCOL_DEVIATION_CREDIT)
        for item in items:
            assert item.amount < 0

    @pytest.mark.anyio
    async def test_invoice_with_tax(self, client: AsyncClient):
        payload = _make_invoice_create(tax=150.0, line_item_ids=["PLI-0001"])
        resp = await client.post(f"{API_PREFIX}/invoices", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["tax"] == 150.0
        assert data["total"] == data["subtotal"] + 150.0

    @pytest.mark.anyio
    async def test_update_invoice_tax(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/invoices/INV-010",
            json={"tax": 100.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tax"] == 100.0

    def test_line_items_sorted_by_accrual_desc(self, svc: SitePaymentsService):
        items = svc.list_line_items()
        dates = [li.accrual_date for li in items]
        assert dates == sorted(dates, reverse=True)

    def test_invoices_sorted_by_submitted_desc(self, svc: SitePaymentsService):
        invoices = svc.list_invoices()
        dates = [inv.submitted_date for inv in invoices]
        assert dates == sorted(dates, reverse=True)

    def test_grants_sorted_by_id(self, svc: SitePaymentsService):
        grants = svc.list_grants()
        ids = [g.id for g in grants]
        assert ids == sorted(ids)


# =====================================================================
# PAYMENT TYPE DISTRIBUTION
# =====================================================================


class TestPaymentTypeDistribution:
    """Test payment type coverage and distribution."""

    def test_all_payment_types_present(self, svc: SitePaymentsService):
        items = svc.list_line_items()
        types = {li.payment_type for li in items}
        assert PaymentType.PER_PATIENT in types
        assert PaymentType.MILESTONE in types
        assert PaymentType.STARTUP_FEE in types
        assert PaymentType.ANNUAL_FEE in types
        assert PaymentType.SCREEN_FAILURE_FEE in types
        assert PaymentType.PROTOCOL_DEVIATION_CREDIT in types
        assert PaymentType.PASS_THROUGH in types
        assert PaymentType.HOLDBACK_RELEASE in types

    def test_per_patient_has_patient_ids(self, svc: SitePaymentsService):
        items = svc.list_line_items(payment_type=PaymentType.PER_PATIENT)
        for item in items:
            assert item.patient_id is not None

    def test_startup_fees_have_no_patient(self, svc: SitePaymentsService):
        items = svc.list_line_items(payment_type=PaymentType.STARTUP_FEE)
        for item in items:
            assert item.patient_id is None

    def test_per_patient_has_visit_number(self, svc: SitePaymentsService):
        items = svc.list_line_items(payment_type=PaymentType.PER_PATIENT)
        for item in items:
            assert item.visit_number is not None
            assert item.visit_number >= 1


# =====================================================================
# PAYMENT STATUS DISTRIBUTION
# =====================================================================


class TestPaymentStatusDistribution:
    """Test payment status coverage."""

    def test_multiple_statuses_present(self, svc: SitePaymentsService):
        items = svc.list_line_items()
        statuses = {li.status for li in items}
        assert PaymentStatus.PAID in statuses
        assert PaymentStatus.ACCRUED in statuses

    def test_paid_items_have_payment_date(self, svc: SitePaymentsService):
        items = svc.list_line_items(status=PaymentStatus.PAID)
        for item in items:
            assert item.payment_date is not None

    def test_accrued_items_no_payment_date(self, svc: SitePaymentsService):
        items = svc.list_line_items(status=PaymentStatus.ACCRUED)
        for item in items:
            assert item.payment_date is None

    @pytest.mark.anyio
    async def test_all_invoice_statuses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/invoices")
        data = resp.json()
        statuses = {inv["status"] for inv in data["items"]}
        assert "paid" in statuses
        assert "invoice_received" in statuses


# =====================================================================
# HOLDBACK CALCULATIONS
# =====================================================================


class TestHoldbackCalculations:
    """Test holdback percentage and amount calculations."""

    def test_holdback_pct_within_bounds(self, svc: SitePaymentsService):
        grants = svc.list_grants()
        for grant in grants:
            assert 0 <= grant.holdback_pct <= 100

    def test_summary_holdback_matches_grant_pct(self, svc: SitePaymentsService):
        grant = svc.get_grant("GRT-001")
        assert grant is not None
        summary = svc.get_site_summary("SITE-101")
        assert summary is not None
        expected_holdback = round(summary.total_accrued * grant.holdback_pct / 100.0, 2)
        assert summary.holdback_amount == expected_holdback

    def test_metrics_holdback_is_aggregate(self, svc: SitePaymentsService):
        metrics = svc.get_metrics()
        # Holdback total should be sum across all grants
        assert metrics.holdback_total > 0
        # Should be less than total accrued (can't hold back more than 100%)
        assert metrics.holdback_total < metrics.total_accrued_amount


# =====================================================================
# CURRENCY HANDLING
# =====================================================================


class TestCurrencyHandling:
    """Test multi-currency support."""

    def test_eur_grant_line_items(self, svc: SitePaymentsService):
        items = svc.list_line_items(site_id="SITE-107")
        for item in items:
            assert item.currency == CurrencyCode.EUR

    def test_usd_is_default(self, svc: SitePaymentsService):
        items = svc.list_line_items(site_id="SITE-101")
        for item in items:
            assert item.currency == CurrencyCode.USD

    @pytest.mark.anyio
    async def test_filter_grants_by_currency(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/grants", params={"currency": "USD"})
        data = resp.json()
        for item in data["items"]:
            assert item["currency"] == "USD"

    @pytest.mark.anyio
    async def test_filter_grants_by_eur(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/grants", params={"currency": "EUR"})
        data = resp.json()
        assert data["total"] >= 1


# =====================================================================
# GRANT SCHEDULE TYPES
# =====================================================================


class TestGrantScheduleTypes:
    """Test payment schedule type coverage."""

    def test_multiple_schedule_types(self, svc: SitePaymentsService):
        grants = svc.list_grants()
        types = {g.payment_schedule_type for g in grants}
        assert PaymentScheduleType.MONTHLY in types
        assert PaymentScheduleType.QUARTERLY in types
        assert PaymentScheduleType.UPON_MILESTONE in types

    def test_grant_has_per_patient_amount(self, svc: SitePaymentsService):
        grant = svc.get_grant("GRT-001")
        assert grant is not None
        assert grant.per_patient_amount == 3500.0

    def test_grant_has_screen_failure_amount(self, svc: SitePaymentsService):
        grant = svc.get_grant("GRT-001")
        assert grant is not None
        assert grant.screen_failure_amount == 750.0

    def test_grant_effective_date_before_end(self, svc: SitePaymentsService):
        grants = svc.list_grants()
        for grant in grants:
            if grant.end_date is not None:
                assert grant.effective_date < grant.end_date


# =====================================================================
# MULTIPLE OPERATIONS
# =====================================================================


class TestMultipleOperations:
    """Test sequences of operations."""

    @pytest.mark.anyio
    async def test_create_grant_then_line_items(self, client: AsyncClient):
        # Create grant
        grant_payload = _make_grant_create()
        resp = await client.post(f"{API_PREFIX}/grants", json=grant_payload)
        assert resp.status_code == 201
        grant_id = resp.json()["id"]

        # Create line items for this grant
        for i in range(3):
            li_payload = _make_line_item_create(
                grant_id=grant_id,
                site_id="SITE-NEW",
                patient_id=f"PAT-NEW-{i+1}",
                amount=3500.0,
                visit_number=1,
            )
            resp2 = await client.post(f"{API_PREFIX}/line-items", json=li_payload)
            assert resp2.status_code == 201

        # Verify they appear in the list
        resp3 = await client.get(
            f"{API_PREFIX}/line-items", params={"grant_id": grant_id}
        )
        assert resp3.status_code == 200
        assert resp3.json()["total"] == 3

    @pytest.mark.anyio
    async def test_create_then_invoice_line_items(self, client: AsyncClient):
        # Create a line item
        li_payload = _make_line_item_create()
        resp = await client.post(f"{API_PREFIX}/line-items", json=li_payload)
        assert resp.status_code == 201
        li_id = resp.json()["id"]

        # Create an invoice referencing it
        inv_payload = _make_invoice_create(line_item_ids=[li_id])
        resp2 = await client.post(f"{API_PREFIX}/invoices", json=inv_payload)
        assert resp2.status_code == 201
        assert resp2.json()["subtotal"] == 3500.0

    @pytest.mark.anyio
    async def test_delete_grant_preserves_line_items(self, client: AsyncClient):
        # Count line items for GRT-001
        resp = await client.get(
            f"{API_PREFIX}/line-items", params={"grant_id": "GRT-001"}
        )
        initial_count = resp.json()["total"]
        assert initial_count > 0

        # Delete the grant
        resp2 = await client.delete(f"{API_PREFIX}/grants/GRT-001")
        assert resp2.status_code == 204

        # Line items still exist (orphaned)
        resp3 = await client.get(
            f"{API_PREFIX}/line-items", params={"grant_id": "GRT-001"}
        )
        assert resp3.json()["total"] == initial_count
