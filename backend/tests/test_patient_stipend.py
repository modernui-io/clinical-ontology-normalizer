"""Tests for Patient Stipend Management.

Covers:
- Seed data verification (schedules, stipends, travel reimbursements, tax records)
- Stipend schedule CRUD (create, read, update, delete, list, filter)
- Patient stipend CRUD (create, read, update, delete, list, filter)
- Payment processing lifecycle (scheduled -> approved -> paid)
- Receipt submission and verification workflow
- Travel reimbursement CRUD and total calculation
- Tax record tracking and threshold checking
- Patient payment summary generation
- Stipend metrics computation
- Error handling (404s, 400s, invalid operations)
- Edge cases (boundary conditions, empty filters)
- Service singleton pattern
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.patient_stipend import router as patient_stipend_router
from app.main import app
from app.schemas.patient_stipend import (
    PatientStipendCreate,
    PatientStipendUpdate,
    PaymentMethod,
    ProcessPaymentRequest,
    StipendScheduleCreate,
    StipendScheduleUpdate,
    StipendStatus,
    StipendType,
    TaxFormType,
    TravelReimbursementCreate,
    TravelReimbursementUpdate,
)
from app.services.patient_stipend_service import (
    PatientStipendService,
    get_patient_stipend_service,
    reset_patient_stipend_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/patient-stipends"

# ---------------------------------------------------------------------------
# Router registration (module-level, idempotent)
# ---------------------------------------------------------------------------

# Register the patient stipend router with the FastAPI app for tests.
# The router must be inserted before the legacy catch-all redirect route
# (/api/{path:path}) which otherwise matches first and creates redirect loops.
_registered = False
if not _registered:
    # Find the catch-all redirect index
    _catch_all_idx: int | None = None
    for _i, _r in enumerate(app.routes):
        if hasattr(_r, "path") and _r.path == "/api/{path:path}":
            _catch_all_idx = _i
            break

    # Add the router to the app (this appends routes at the end)
    app.include_router(patient_stipend_router, prefix="/api/v1")

    # If catch-all exists, move new routes before it
    if _catch_all_idx is not None:
        _new_routes = app.routes[_catch_all_idx + 1:]
        del app.routes[_catch_all_idx + 1:]
        for _nr in reversed(_new_routes):
            app.routes.insert(_catch_all_idx, _nr)

    _registered = True


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_patient_stipend_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> PatientStipendService:
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


def _make_schedule_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "stipend_type": "visit_compensation",
        "amount": 85.00,
        "currency": "USD",
        "description": "Test visit compensation schedule",
        "requires_receipt": False,
    }
    defaults.update(overrides)
    return defaults


def _make_stipend_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "patient_id": "PAT-9999",
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "stipend_type": "visit_compensation",
        "visit_number": 1,
        "visit_date": now.isoformat(),
        "amount": 75.00,
        "currency": "USD",
    }
    defaults.update(overrides)
    return defaults


def _make_travel_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "patient_id": "PAT-9999",
        "trial_id": EYLEA_TRIAL,
        "visit_number": 1,
        "travel_date": now.isoformat(),
        "distance_miles": 50.0,
        "mileage_rate": 0.67,
        "parking_amount": 10.00,
        "tolls_amount": 5.00,
        "lodging_amount": 0.0,
        "meal_amount": 15.00,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_schedules_count(self, svc: PatientStipendService):
        schedules = svc.list_schedules()
        assert len(schedules) == 6

    def test_seed_stipends_count(self, svc: PatientStipendService):
        stipends = svc.list_stipends()
        assert len(stipends) == 14

    def test_seed_travel_reimbursements_count(self, svc: PatientStipendService):
        travel = svc.list_travel_reimbursements()
        assert len(travel) == 5

    def test_seed_tax_records_count(self, svc: PatientStipendService):
        tax_records = svc.list_tax_records()
        assert len(tax_records) == 3

    def test_seed_schedules_have_multiple_trials(self, svc: PatientStipendService):
        schedules = svc.list_schedules()
        trial_ids = {s.trial_id for s in schedules}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_stipends_have_multiple_statuses(self, svc: PatientStipendService):
        stipends = svc.list_stipends()
        statuses = {s.status for s in stipends}
        assert StipendStatus.PAID in statuses
        assert StipendStatus.SCHEDULED in statuses
        assert StipendStatus.APPROVED in statuses

    def test_seed_stipends_have_multiple_types(self, svc: PatientStipendService):
        stipends = svc.list_stipends()
        types = {s.stipend_type for s in stipends}
        assert StipendType.VISIT_COMPENSATION in types
        assert StipendType.MEAL_ALLOWANCE in types
        assert StipendType.SCREEN_FAILURE_COMPENSATION in types

    def test_seed_travel_has_paid_and_approved(self, svc: PatientStipendService):
        travel = svc.list_travel_reimbursements()
        statuses = {t.status for t in travel}
        assert StipendStatus.PAID in statuses
        assert StipendStatus.APPROVED in statuses

    def test_seed_tax_records_have_w9_and_w8ben(self, svc: PatientStipendService):
        records = svc.list_tax_records()
        forms = {r.form_type for r in records}
        assert TaxFormType.W9 in forms
        assert TaxFormType.W8BEN in forms


# =====================================================================
# STIPEND SCHEDULE CRUD
# =====================================================================


class TestStipendScheduleCrud:
    """Test stipend schedule create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_schedules(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6
        assert len(data["items"]) == 6

    @pytest.mark.anyio
    async def test_list_schedules_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_schedules_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules", params={"stipend_type": "visit_compensation"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["stipend_type"] == "visit_compensation"

    @pytest.mark.anyio
    async def test_get_schedule(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules/SCHED-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SCHED-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["stipend_type"] == "visit_compensation"

    @pytest.mark.anyio
    async def test_get_schedule_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules/SCHED-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_schedule(self, client: AsyncClient):
        payload = _make_schedule_create()
        resp = await client.post(f"{API_PREFIX}/schedules", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["amount"] == 85.00
        assert data["stipend_type"] == "visit_compensation"
        assert data["id"].startswith("SCHED-")

    @pytest.mark.anyio
    async def test_create_schedule_with_max_amount(self, client: AsyncClient):
        payload = _make_schedule_create(
            stipend_type="travel_reimbursement",
            requires_receipt=True,
            max_amount=200.00,
        )
        resp = await client.post(f"{API_PREFIX}/schedules", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["requires_receipt"] is True
        assert data["max_amount"] == 200.00

    @pytest.mark.anyio
    async def test_update_schedule(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/schedules/SCHED-001",
            json={"amount": 90.00, "description": "Updated compensation"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["amount"] == 90.00
        assert data["description"] == "Updated compensation"

    @pytest.mark.anyio
    async def test_update_schedule_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/schedules/SCHED-NONEXISTENT",
            json={"amount": 100.00},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_schedule(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/schedules/SCHED-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/schedules/SCHED-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_schedule_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/schedules/SCHED-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# PATIENT STIPEND CRUD
# =====================================================================


class TestPatientStipendCrud:
    """Test patient stipend create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_stipends(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stipends")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 14
        assert len(data["items"]) == 14

    @pytest.mark.anyio
    async def test_list_stipends_filter_patient(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stipends", params={"patient_id": "PAT-1001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["patient_id"] == "PAT-1001"

    @pytest.mark.anyio
    async def test_list_stipends_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stipends", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_stipends_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stipends", params={"site_id": "SITE-101"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_stipends_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stipends", params={"status": "paid"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "paid"

    @pytest.mark.anyio
    async def test_list_stipends_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stipends", params={"stipend_type": "meal_allowance"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["stipend_type"] == "meal_allowance"

    @pytest.mark.anyio
    async def test_get_stipend(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stipends/STIP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "STIP-001"
        assert data["patient_id"] == "PAT-1001"
        assert data["status"] == "paid"

    @pytest.mark.anyio
    async def test_get_stipend_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stipends/STIP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_stipend(self, client: AsyncClient):
        payload = _make_stipend_create()
        resp = await client.post(f"{API_PREFIX}/stipends", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == "PAT-9999"
        assert data["amount"] == 75.00
        assert data["status"] == "scheduled"
        assert data["id"].startswith("STIP-")

    @pytest.mark.anyio
    async def test_create_stipend_with_payment_method(self, client: AsyncClient):
        payload = _make_stipend_create(payment_method="direct_deposit")
        resp = await client.post(f"{API_PREFIX}/stipends", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["payment_method"] == "direct_deposit"

    @pytest.mark.anyio
    async def test_update_stipend(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/stipends/STIP-005",
            json={"status": "approved", "notes": "Approved for payment"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["notes"] == "Approved for payment"

    @pytest.mark.anyio
    async def test_update_stipend_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/stipends/STIP-NONEXISTENT",
            json={"status": "approved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_stipend(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/stipends/STIP-013")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/stipends/STIP-013")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_stipend_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/stipends/STIP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# PAYMENT PROCESSING
# =====================================================================


class TestPaymentProcessing:
    """Test payment processing lifecycle."""

    @pytest.mark.anyio
    async def test_process_payment_from_approved(self, client: AsyncClient):
        payload = {
            "payment_method": "direct_deposit",
            "payment_reference": "ACH-TEST-001",
            "notes": "Payment processed",
        }
        resp = await client.post(f"{API_PREFIX}/stipends/STIP-004/process-payment", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "paid"
        assert data["payment_method"] == "direct_deposit"
        assert data["payment_reference"] == "ACH-TEST-001"
        assert data["payment_date"] is not None

    @pytest.mark.anyio
    async def test_process_payment_from_scheduled(self, client: AsyncClient):
        payload = {
            "payment_method": "prepaid_card",
        }
        resp = await client.post(f"{API_PREFIX}/stipends/STIP-005/process-payment", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "paid"
        assert data["payment_method"] == "prepaid_card"
        assert data["payment_reference"] is not None  # Auto-generated

    @pytest.mark.anyio
    async def test_process_payment_already_paid(self, client: AsyncClient):
        payload = {"payment_method": "check"}
        resp = await client.post(f"{API_PREFIX}/stipends/STIP-001/process-payment", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_process_payment_on_hold(self, client: AsyncClient):
        payload = {"payment_method": "direct_deposit"}
        resp = await client.post(f"{API_PREFIX}/stipends/STIP-014/process-payment", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_process_payment_not_found(self, client: AsyncClient):
        payload = {"payment_method": "check"}
        resp = await client.post(f"{API_PREFIX}/stipends/STIP-NONEXISTENT/process-payment", json=payload)
        assert resp.status_code == 404

    def test_process_payment_updates_tax_ytd(self, svc: PatientStipendService):
        """Processing a payment should update the patient's YTD tax total."""
        # Get initial tax record for PAT-1001
        tax_before = svc.check_tax_threshold("PAT-1001", EYLEA_TRIAL)
        assert tax_before is not None
        initial_ytd = tax_before.total_paid_ytd

        # Process the approved stipend STIP-004
        svc.process_payment(
            "STIP-004",
            ProcessPaymentRequest(payment_method=PaymentMethod.DIRECT_DEPOSIT),
        )

        tax_after = svc.check_tax_threshold("PAT-1001", EYLEA_TRIAL)
        assert tax_after is not None
        assert tax_after.total_paid_ytd == initial_ytd + 75.00

    def test_process_payment_auto_generates_reference(self, svc: PatientStipendService):
        result = svc.process_payment(
            "STIP-005",
            ProcessPaymentRequest(payment_method=PaymentMethod.CHECK),
        )
        assert result.payment_reference is not None
        assert result.payment_reference.startswith("PAY-")

    @pytest.mark.anyio
    async def test_process_payment_with_all_methods(self, client: AsyncClient):
        """Verify all payment methods can be used."""
        # Create a stipend for each method to test
        for method in ["check", "direct_deposit", "prepaid_card", "wire_transfer", "gift_card"]:
            create_payload = _make_stipend_create(patient_id=f"PAT-METHOD-{method}")
            create_resp = await client.post(f"{API_PREFIX}/stipends", json=create_payload)
            assert create_resp.status_code == 201
            stipend_id = create_resp.json()["id"]

            process_payload = {"payment_method": method}
            resp = await client.post(f"{API_PREFIX}/stipends/{stipend_id}/process-payment", json=process_payload)
            assert resp.status_code == 200
            assert resp.json()["payment_method"] == method


# =====================================================================
# RECEIPT WORKFLOW
# =====================================================================


class TestReceiptWorkflow:
    """Test receipt submission and verification workflow."""

    @pytest.mark.anyio
    async def test_submit_receipt(self, client: AsyncClient):
        payload = {
            "receipt_path": "/receipts/test-receipt.pdf",
            "notes": "Lunch receipt",
        }
        resp = await client.post(f"{API_PREFIX}/stipends/STIP-004/submit-receipt", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["receipt_submitted"] is True

    @pytest.mark.anyio
    async def test_submit_receipt_not_found(self, client: AsyncClient):
        payload = {"receipt_path": "/receipts/test.pdf"}
        resp = await client.post(f"{API_PREFIX}/stipends/STIP-NONEXISTENT/submit-receipt", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_verify_receipt_approved(self, client: AsyncClient):
        # First submit a receipt
        submit_payload = {"receipt_path": "/receipts/test.pdf"}
        await client.post(f"{API_PREFIX}/stipends/STIP-004/submit-receipt", json=submit_payload)

        # Now verify it
        resp = await client.post(
            f"{API_PREFIX}/stipends/STIP-004/verify-receipt",
            params={"verified": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["receipt_verified"] is True

    @pytest.mark.anyio
    async def test_verify_receipt_rejected(self, client: AsyncClient):
        # First submit a receipt
        submit_payload = {"receipt_path": "/receipts/test.pdf"}
        await client.post(f"{API_PREFIX}/stipends/STIP-004/submit-receipt", json=submit_payload)

        # Reject the receipt
        resp = await client.post(
            f"{API_PREFIX}/stipends/STIP-004/verify-receipt",
            params={"verified": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["receipt_verified"] is False

    @pytest.mark.anyio
    async def test_verify_receipt_not_submitted(self, client: AsyncClient):
        # STIP-005 has no receipt submitted
        resp = await client.post(
            f"{API_PREFIX}/stipends/STIP-005/verify-receipt",
            params={"verified": True},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_verify_receipt_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/stipends/STIP-NONEXISTENT/verify-receipt",
            params={"verified": True},
        )
        assert resp.status_code == 404

    def test_receipt_already_verified(self, svc: PatientStipendService):
        """STIP-009 already has receipt submitted and verified in seed data."""
        stipend = svc.get_stipend("STIP-009")
        assert stipend is not None
        assert stipend.receipt_submitted is True
        assert stipend.receipt_verified is True

    def test_submit_receipt_service_direct(self, svc: PatientStipendService):
        result = svc.submit_receipt("STIP-004", "/receipts/direct-test.pdf", "Direct test")
        assert result.receipt_submitted is True

    def test_verify_receipt_service_direct(self, svc: PatientStipendService):
        svc.submit_receipt("STIP-004", "/receipts/test.pdf")
        result = svc.verify_receipt("STIP-004", verified=True)
        assert result.receipt_verified is True


# =====================================================================
# TRAVEL REIMBURSEMENT CRUD
# =====================================================================


class TestTravelReimbursementCrud:
    """Test travel reimbursement operations."""

    @pytest.mark.anyio
    async def test_list_travel_reimbursements(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/travel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_travel_filter_patient(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/travel", params={"patient_id": "PAT-1001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["patient_id"] == "PAT-1001"

    @pytest.mark.anyio
    async def test_list_travel_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/travel", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_travel_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/travel", params={"status": "paid"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "paid"

    @pytest.mark.anyio
    async def test_get_travel_reimbursement(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/travel/TRVL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TRVL-001"
        assert data["patient_id"] == "PAT-1001"
        assert data["total_amount"] > 0

    @pytest.mark.anyio
    async def test_get_travel_reimbursement_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/travel/TRVL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_travel_reimbursement(self, client: AsyncClient):
        payload = _make_travel_create()
        resp = await client.post(f"{API_PREFIX}/travel", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == "PAT-9999"
        assert data["distance_miles"] == 50.0
        # Total should be: (50 * 0.67) + 10 + 5 + 0 + 15 = 63.50
        assert data["total_amount"] == 63.50
        assert data["status"] == "scheduled"

    @pytest.mark.anyio
    async def test_create_travel_with_lodging(self, client: AsyncClient):
        payload = _make_travel_create(
            distance_miles=200.0,
            lodging_amount=189.00,
            meal_amount=45.00,
        )
        resp = await client.post(f"{API_PREFIX}/travel", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["lodging_amount"] == 189.00
        assert data["total_amount"] > 200.0  # Should include mileage + lodging + meals

    @pytest.mark.anyio
    async def test_update_travel_reimbursement(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/travel/TRVL-005",
            json={"parking_amount": 20.00, "status": "paid"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["parking_amount"] == 20.00
        assert data["status"] == "paid"
        # Total should be recalculated
        assert data["total_amount"] > 0

    @pytest.mark.anyio
    async def test_update_travel_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/travel/TRVL-NONEXISTENT",
            json={"parking_amount": 10.00},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_travel_reimbursement(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/travel/TRVL-005")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/travel/TRVL-005")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_travel_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/travel/TRVL-NONEXISTENT")
        assert resp.status_code == 404

    def test_travel_total_calculation(self, svc: PatientStipendService):
        """Verify total amount is correctly calculated from components."""
        result = svc.create_travel_reimbursement(TravelReimbursementCreate(
            patient_id="PAT-CALC",
            trial_id=EYLEA_TRIAL,
            visit_number=1,
            travel_date=datetime.now(timezone.utc),
            distance_miles=100.0,
            mileage_rate=0.67,
            parking_amount=15.00,
            tolls_amount=10.00,
            lodging_amount=120.00,
            meal_amount=30.00,
        ))
        expected_total = round((100.0 * 0.67) + 15.00 + 10.00 + 120.00 + 30.00, 2)
        assert result.total_amount == expected_total

    def test_travel_update_recalculates_total(self, svc: PatientStipendService):
        """Updating travel components should recalculate the total."""
        original = svc.get_travel_reimbursement("TRVL-001")
        assert original is not None
        old_total = original.total_amount

        updated = svc.update_travel_reimbursement(
            "TRVL-001",
            TravelReimbursementUpdate(parking_amount=50.00),
        )
        assert updated is not None
        assert updated.total_amount != old_total
        assert updated.parking_amount == 50.00


# =====================================================================
# TAX RECORD TRACKING
# =====================================================================


class TestTaxRecordTracking:
    """Test tax record operations and threshold checking."""

    @pytest.mark.anyio
    async def test_list_tax_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tax-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_tax_records_filter_patient(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tax-records", params={"patient_id": "PAT-1001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["patient_id"] == "PAT-1001"

    @pytest.mark.anyio
    async def test_list_tax_records_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tax-records", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_tax_records_filter_year(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tax-records", params={"tax_year": 2026})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["tax_year"] == 2026

    @pytest.mark.anyio
    async def test_get_tax_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tax-records/TAX-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TAX-001"
        assert data["patient_id"] == "PAT-1001"
        assert data["form_type"] == "w9"
        assert data["form_submitted"] is True

    @pytest.mark.anyio
    async def test_get_tax_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tax-records/TAX-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_check_tax_threshold(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/tax-records/check-threshold",
            params={"patient_id": "PAT-1001", "trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["patient_id"] == "PAT-1001"
        assert data["threshold_amount"] == 600.0
        assert "threshold_exceeded" in data

    @pytest.mark.anyio
    async def test_check_tax_threshold_not_found(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/tax-records/check-threshold",
            params={"patient_id": "PAT-NONEXISTENT", "trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 404

    def test_tax_threshold_not_exceeded(self, svc: PatientStipendService):
        """PAT-1001 has $225 YTD, below $600 threshold."""
        record = svc.check_tax_threshold("PAT-1001", EYLEA_TRIAL)
        assert record is not None
        assert record.threshold_exceeded is False

    def test_tax_withholding_required_for_w8ben(self, svc: PatientStipendService):
        """PAT-1004 has W-8BEN form requiring withholding."""
        record = svc.check_tax_threshold("PAT-1004", LIBTAYO_TRIAL)
        assert record is not None
        assert record.form_type == TaxFormType.W8BEN
        assert record.withholding_required is True

    def test_tax_form_not_submitted(self, svc: PatientStipendService):
        """PAT-1004 has not submitted their W-8BEN."""
        record = svc.check_tax_threshold("PAT-1004", LIBTAYO_TRIAL)
        assert record is not None
        assert record.form_submitted is False


# =====================================================================
# PATIENT PAYMENT SUMMARY
# =====================================================================


class TestPatientPaymentSummary:
    """Test patient payment summary generation."""

    @pytest.mark.anyio
    async def test_get_patient_summary(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/patients/PAT-1001/summary",
            params={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["patient_id"] == "PAT-1001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["total_earned"] > 0
        assert data["total_paid"] > 0
        assert data["visits_completed"] > 0

    @pytest.mark.anyio
    async def test_get_patient_summary_not_found(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/patients/PAT-NONEXISTENT/summary",
            params={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 404

    def test_patient_summary_totals(self, svc: PatientStipendService):
        """Verify PAT-1001 summary totals are correct."""
        summary = svc.get_patient_summary("PAT-1001", EYLEA_TRIAL)
        assert summary is not None
        # PAT-1001 has 5 stipends: 3 paid ($75 each), 1 approved ($75), 1 scheduled ($75)
        assert summary.total_earned == 375.00
        assert summary.total_paid == 225.00
        assert summary.total_pending == 150.00
        assert summary.visits_completed == 3

    def test_patient_summary_payments_by_type(self, svc: PatientStipendService):
        """Verify payments are broken down by type."""
        summary = svc.get_patient_summary("PAT-1001", EYLEA_TRIAL)
        assert summary is not None
        assert "visit_compensation" in summary.payments_by_type
        assert summary.payments_by_type["visit_compensation"] == 375.00

    def test_patient_summary_dupixent(self, svc: PatientStipendService):
        """Verify PAT-1003 summary for Dupixent trial."""
        summary = svc.get_patient_summary("PAT-1003", DUPIXENT_TRIAL)
        assert summary is not None
        assert summary.total_earned > 0
        assert "meal_allowance" in summary.payments_by_type

    def test_patient_summary_multiple_types(self, svc: PatientStipendService):
        """PAT-1003 has both visit compensation and meal allowance."""
        summary = svc.get_patient_summary("PAT-1003", DUPIXENT_TRIAL)
        assert summary is not None
        assert len(summary.payments_by_type) >= 2

    @pytest.mark.anyio
    async def test_patient_summary_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/patients/PAT-1001/summary",
            params={"trial_id": "NONEXISTENT-TRIAL"},
        )
        assert resp.status_code == 404


# =====================================================================
# STIPEND METRICS
# =====================================================================


class TestStipendMetrics:
    """Test stipend metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_schedules"] == 6
        assert data["total_stipends"] == 14
        assert data["total_paid_amount"] > 0
        assert data["total_travel_reimbursements"] == 5
        assert data["total_tax_records"] == 3
        assert data["unique_patients"] > 0

    def test_metrics_stipends_by_status(self, svc: PatientStipendService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.stipends_by_status.values())
        assert total_by_status == metrics.total_stipends

    def test_metrics_stipends_by_type(self, svc: PatientStipendService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.stipends_by_type.values())
        assert total_by_type == metrics.total_stipends

    def test_metrics_paid_amount_positive(self, svc: PatientStipendService):
        metrics = svc.get_metrics()
        assert metrics.total_paid_amount > 0

    def test_metrics_pending_amount(self, svc: PatientStipendService):
        metrics = svc.get_metrics()
        assert metrics.total_pending_amount > 0

    def test_metrics_travel_amount(self, svc: PatientStipendService):
        metrics = svc.get_metrics()
        assert metrics.total_travel_amount > 0

    def test_metrics_avg_payment_per_visit(self, svc: PatientStipendService):
        metrics = svc.get_metrics()
        assert metrics.avg_payment_per_visit > 0

    def test_metrics_unique_patients(self, svc: PatientStipendService):
        metrics = svc.get_metrics()
        assert metrics.unique_patients == 5  # PAT-1001 through PAT-1005

    def test_metrics_patients_exceeding_threshold(self, svc: PatientStipendService):
        """No patients should exceed the $600 threshold in seed data."""
        metrics = svc.get_metrics()
        assert metrics.patients_exceeding_threshold == 0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_patient_stipend_service()
        svc2 = get_patient_stipend_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_patient_stipend_service()
        svc2 = reset_patient_stipend_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_patient_stipend_service()
        svc.delete_schedule("SCHED-001")
        assert svc.get_schedule("SCHED-001") is None
        svc2 = reset_patient_stipend_service()
        assert svc2.get_schedule("SCHED-001") is not None

    def test_reset_restores_stipends(self):
        svc = get_patient_stipend_service()
        svc.delete_stipend("STIP-001")
        assert svc.get_stipend("STIP-001") is None
        svc2 = reset_patient_stipend_service()
        assert svc2.get_stipend("STIP-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_schedules_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_stipends_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stipends")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_travel_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/travel")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_tax_records_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tax-records")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_schedule_all_fields(self, client: AsyncClient):
        payload = _make_schedule_create(
            stipend_type="lodging",
            visit_number=5,
            amount=200.00,
            requires_receipt=True,
            max_amount=250.00,
        )
        resp = await client.post(f"{API_PREFIX}/schedules", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["stipend_type"] == "lodging"
        assert data["visit_number"] == 5

    @pytest.mark.anyio
    async def test_create_stipend_screen_failure(self, client: AsyncClient):
        payload = _make_stipend_create(
            stipend_type="screen_failure_compensation",
            visit_number=None,
            amount=50.00,
        )
        resp = await client.post(f"{API_PREFIX}/stipends", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["stipend_type"] == "screen_failure_compensation"

    @pytest.mark.anyio
    async def test_create_travel_zero_distance(self, client: AsyncClient):
        payload = _make_travel_create(distance_miles=0.0, parking_amount=20.00)
        resp = await client.post(f"{API_PREFIX}/travel", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["distance_miles"] == 0.0
        # Total should still include parking, tolls, meals
        assert data["total_amount"] > 0

    @pytest.mark.anyio
    async def test_stipend_sorted_by_created_at_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stipends")
        data = resp.json()
        dates = [item["created_at"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_travel_sorted_by_travel_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/travel")
        data = resp.json()
        dates = [item["travel_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_schedules_sorted_by_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules")
        data = resp.json()
        ids = [item["id"] for item in data["items"]]
        assert ids == sorted(ids)

    def test_multiple_stipends_same_patient(self, svc: PatientStipendService):
        """PAT-1001 should have multiple stipends."""
        stipends = svc.list_stipends(patient_id="PAT-1001")
        assert len(stipends) >= 5

    def test_empty_patient_filter(self, svc: PatientStipendService):
        stipends = svc.list_stipends(patient_id="NONEXISTENT")
        assert len(stipends) == 0

    def test_empty_trial_filter_schedules(self, svc: PatientStipendService):
        schedules = svc.list_schedules(trial_id="NONEXISTENT")
        assert len(schedules) == 0

    def test_on_hold_stipend_exists(self, svc: PatientStipendService):
        """STIP-014 should be on hold."""
        stipend = svc.get_stipend("STIP-014")
        assert stipend is not None
        assert stipend.status == StipendStatus.ON_HOLD

    def test_processing_stipend_exists(self, svc: PatientStipendService):
        """STIP-010 should be in processing."""
        stipend = svc.get_stipend("STIP-010")
        assert stipend is not None
        assert stipend.status == StipendStatus.PROCESSING


# =====================================================================
# STIPEND TYPE COVERAGE
# =====================================================================


class TestStipendTypeCoverage:
    """Test various stipend types are correctly handled."""

    @pytest.mark.anyio
    async def test_visit_compensation_stipends(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stipends", params={"stipend_type": "visit_compensation"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_meal_allowance_stipends(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stipends", params={"stipend_type": "meal_allowance"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_screen_failure_stipends(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stipends", params={"stipend_type": "screen_failure_compensation"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0

    def test_create_completion_bonus(self, svc: PatientStipendService):
        result = svc.create_stipend(PatientStipendCreate(
            patient_id="PAT-BONUS",
            trial_id=EYLEA_TRIAL,
            site_id="SITE-101",
            schedule_id="SCHED-003",
            stipend_type=StipendType.COMPLETION_BONUS,
            amount=200.00,
        ))
        assert result.stipend_type == StipendType.COMPLETION_BONUS
        assert result.amount == 200.00

    def test_create_parking_stipend(self, svc: PatientStipendService):
        result = svc.create_stipend(PatientStipendCreate(
            patient_id="PAT-PARK",
            trial_id=EYLEA_TRIAL,
            site_id="SITE-101",
            stipend_type=StipendType.PARKING,
            visit_number=1,
            amount=15.00,
        ))
        assert result.stipend_type == StipendType.PARKING

    def test_create_lost_wages_stipend(self, svc: PatientStipendService):
        result = svc.create_stipend(PatientStipendCreate(
            patient_id="PAT-WAGES",
            trial_id=DUPIXENT_TRIAL,
            site_id="SITE-103",
            stipend_type=StipendType.LOST_WAGES,
            visit_number=1,
            amount=300.00,
        ))
        assert result.stipend_type == StipendType.LOST_WAGES
        assert result.amount == 300.00

    def test_create_lodging_stipend(self, svc: PatientStipendService):
        result = svc.create_stipend(PatientStipendCreate(
            patient_id="PAT-LODGE",
            trial_id=LIBTAYO_TRIAL,
            site_id="SITE-105",
            stipend_type=StipendType.LODGING,
            visit_number=1,
            amount=175.00,
        ))
        assert result.stipend_type == StipendType.LODGING


# =====================================================================
# PAYMENT METHOD COVERAGE
# =====================================================================


class TestPaymentMethodCoverage:
    """Test all payment methods are supported."""

    def test_direct_deposit_in_seed(self, svc: PatientStipendService):
        stipend = svc.get_stipend("STIP-001")
        assert stipend is not None
        assert stipend.payment_method == PaymentMethod.DIRECT_DEPOSIT

    def test_prepaid_card_in_seed(self, svc: PatientStipendService):
        stipend = svc.get_stipend("STIP-006")
        assert stipend is not None
        assert stipend.payment_method == PaymentMethod.PREPAID_CARD

    def test_check_in_seed(self, svc: PatientStipendService):
        stipend = svc.get_stipend("STIP-008")
        assert stipend is not None
        assert stipend.payment_method == PaymentMethod.CHECK

    def test_gift_card_in_seed(self, svc: PatientStipendService):
        stipend = svc.get_stipend("STIP-013")
        assert stipend is not None
        assert stipend.payment_method == PaymentMethod.GIFT_CARD


# =====================================================================
# STATUS TRANSITIONS
# =====================================================================


class TestStatusTransitions:
    """Test stipend status transitions."""

    def test_scheduled_to_approved(self, svc: PatientStipendService):
        result = svc.update_stipend("STIP-005", PatientStipendUpdate(status=StipendStatus.APPROVED))
        assert result is not None
        assert result.status == StipendStatus.APPROVED

    def test_approved_to_processing(self, svc: PatientStipendService):
        result = svc.update_stipend("STIP-004", PatientStipendUpdate(status=StipendStatus.PROCESSING))
        assert result is not None
        assert result.status == StipendStatus.PROCESSING

    def test_scheduled_to_cancelled(self, svc: PatientStipendService):
        result = svc.update_stipend("STIP-005", PatientStipendUpdate(status=StipendStatus.CANCELLED))
        assert result is not None
        assert result.status == StipendStatus.CANCELLED

    def test_on_hold_status(self, svc: PatientStipendService):
        stipend = svc.get_stipend("STIP-014")
        assert stipend is not None
        assert stipend.status == StipendStatus.ON_HOLD

    def test_update_to_returned(self, svc: PatientStipendService):
        result = svc.update_stipend("STIP-001", PatientStipendUpdate(status=StipendStatus.RETURNED))
        assert result is not None
        assert result.status == StipendStatus.RETURNED


# =====================================================================
# CROSS-DOMAIN INTEGRATION
# =====================================================================


class TestCrossDomainIntegration:
    """Test interactions between different data domains."""

    def test_payment_processing_updates_summary(self, svc: PatientStipendService):
        """Processing a payment should be reflected in the patient summary."""
        summary_before = svc.get_patient_summary("PAT-1001", EYLEA_TRIAL)
        assert summary_before is not None
        paid_before = summary_before.total_paid

        svc.process_payment(
            "STIP-004",
            ProcessPaymentRequest(payment_method=PaymentMethod.DIRECT_DEPOSIT),
        )

        summary_after = svc.get_patient_summary("PAT-1001", EYLEA_TRIAL)
        assert summary_after is not None
        assert summary_after.total_paid == paid_before + 75.00

    def test_payment_processing_updates_metrics(self, svc: PatientStipendService):
        """Processing a payment should increase total paid in metrics."""
        metrics_before = svc.get_metrics()
        paid_before = metrics_before.total_paid_amount

        svc.process_payment(
            "STIP-004",
            ProcessPaymentRequest(payment_method=PaymentMethod.DIRECT_DEPOSIT),
        )

        metrics_after = svc.get_metrics()
        assert metrics_after.total_paid_amount == paid_before + 75.00

    def test_new_stipend_updates_metrics(self, svc: PatientStipendService):
        """Creating a new stipend should increase count in metrics."""
        metrics_before = svc.get_metrics()
        count_before = metrics_before.total_stipends

        svc.create_stipend(PatientStipendCreate(
            patient_id="PAT-NEW",
            trial_id=EYLEA_TRIAL,
            site_id="SITE-101",
            stipend_type=StipendType.VISIT_COMPENSATION,
            amount=75.00,
        ))

        metrics_after = svc.get_metrics()
        assert metrics_after.total_stipends == count_before + 1

    def test_new_travel_updates_metrics(self, svc: PatientStipendService):
        """Creating a travel reimbursement should update metrics."""
        metrics_before = svc.get_metrics()
        count_before = metrics_before.total_travel_reimbursements

        svc.create_travel_reimbursement(TravelReimbursementCreate(
            patient_id="PAT-TRAVEL",
            trial_id=EYLEA_TRIAL,
            visit_number=1,
            travel_date=datetime.now(timezone.utc),
            distance_miles=30.0,
        ))

        metrics_after = svc.get_metrics()
        assert metrics_after.total_travel_reimbursements == count_before + 1

    def test_delete_stipend_updates_metrics(self, svc: PatientStipendService):
        """Deleting a stipend should decrease count in metrics."""
        metrics_before = svc.get_metrics()
        count_before = metrics_before.total_stipends

        svc.delete_stipend("STIP-013")

        metrics_after = svc.get_metrics()
        assert metrics_after.total_stipends == count_before - 1
