"""Tests for Patient Travel & Logistics Management (OPS-TRAVEL).

Covers:
- Seed data verification (travel requests, bookings, reimbursements)
- Travel request CRUD (create, read, update, delete, list, filter by trial/status/patient)
- Approval workflow (approve travel request)
- Booking CRUD (create, read, update, delete, list, filter by travel request)
- Reimbursement CRUD (create, read, update, delete, list, filter by travel request/patient/status)
- Travel metrics computation
- Error handling (404s)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.patient_travel import (
    ReimbursementStatus,
    TravelRequestStatus,
)
from app.services.patient_travel_service import (
    PatientTravelService,
    get_patient_travel_service,
    reset_patient_travel_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/patient-travel"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_patient_travel_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> PatientTravelService:
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


def _make_travel_request_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "patient_id": "PT-9999",
        "traveler_type": "patient",
        "visit_type": "screening",
        "visit_date": (now + timedelta(days=14)).isoformat(),
        "origin_city": "Newark",
        "origin_country": "US",
        "destination_city": "Boston",
        "destination_country": "US",
        "transport_mode": "rail",
        "accommodation_type": "none_required",
        "accommodation_nights": 0,
        "estimated_cost": 150.0,
    }
    defaults.update(overrides)
    return defaults


def _make_booking_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "travel_request_id": "TR-001",
        "booking_type": "flight",
        "provider": "Delta Airlines",
        "confirmation_number": "DL-99887",
        "departure_date": (now + timedelta(days=7)).isoformat(),
        "return_date": (now + timedelta(days=8)).isoformat(),
        "cost": 350.0,
        "currency": "USD",
        "notes": "Economy round-trip",
    }
    defaults.update(overrides)
    return defaults


def _make_reimbursement_create(**overrides) -> dict:
    defaults = {
        "travel_request_id": "TR-001",
        "patient_id": "PT-1001",
        "expense_type": "transport",
        "amount": 200.0,
        "currency": "USD",
        "receipt_provided": True,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_travel_requests_count(self, svc: PatientTravelService):
        requests = svc.list_travel_requests()
        assert len(requests) == 12

    def test_seed_travel_requests_across_trials(self, svc: PatientTravelService):
        eylea = svc.list_travel_requests(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_travel_requests(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_travel_requests(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4

    def test_seed_bookings_count(self, svc: PatientTravelService):
        bookings = svc.list_bookings()
        assert len(bookings) == 10

    def test_seed_reimbursements_count(self, svc: PatientTravelService):
        reimbursements = svc.list_reimbursements()
        assert len(reimbursements) == 10

    def test_seed_has_all_request_statuses(self, svc: PatientTravelService):
        requests = svc.list_travel_requests()
        statuses = {r.status.value for r in requests}
        assert "requested" in statuses
        assert "approved" in statuses
        assert "completed" in statuses
        assert "cancelled" in statuses

    def test_seed_has_all_traveler_types(self, svc: PatientTravelService):
        requests = svc.list_travel_requests()
        types = {r.traveler_type.value for r in requests}
        assert "patient" in types
        assert "caregiver" in types
        assert "legal_guardian" in types

    def test_seed_has_multiple_transport_modes(self, svc: PatientTravelService):
        requests = svc.list_travel_requests()
        modes = {r.transport_mode.value for r in requests}
        assert len(modes) >= 4

    def test_seed_has_multiple_accommodation_types(self, svc: PatientTravelService):
        requests = svc.list_travel_requests()
        types = {r.accommodation_type.value for r in requests}
        assert len(types) >= 3

    def test_seed_has_all_reimbursement_statuses(self, svc: PatientTravelService):
        reimbursements = svc.list_reimbursements()
        statuses = {r.status.value for r in reimbursements}
        assert "pending" in statuses
        assert "paid" in statuses
        assert "denied" in statuses
        assert "under_review" in statuses
        assert "approved" in statuses

    def test_seed_completed_requests_have_actual_cost(self, svc: PatientTravelService):
        requests = svc.list_travel_requests(status=TravelRequestStatus.COMPLETED)
        for r in requests:
            assert r.actual_cost is not None


# =====================================================================
# TRAVEL REQUEST CRUD
# =====================================================================


class TestTravelRequestCrud:
    """Test travel request CRUD operations."""

    @pytest.mark.anyio
    async def test_list_travel_requests(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requests")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_travel_requests_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requests", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_travel_requests_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requests", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_travel_requests_filter_patient(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requests", params={"patient_id": "PT-1001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["patient_id"] == "PT-1001"

    @pytest.mark.anyio
    async def test_get_travel_request(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requests/TR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TR-001"
        assert data["patient_id"] == "PT-1001"

    @pytest.mark.anyio
    async def test_get_travel_request_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requests/TR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_travel_request(self, client: AsyncClient):
        payload = _make_travel_request_create()
        resp = await client.post(f"{API_PREFIX}/requests", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == "PT-9999"
        assert data["status"] == "requested"
        assert data["id"].startswith("TR-")

    @pytest.mark.anyio
    async def test_update_travel_request(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/requests/TR-008",
            json={"status": "approved", "approved_by": "Dr. Test Approver"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["approved_by"] == "Dr. Test Approver"

    @pytest.mark.anyio
    async def test_update_travel_request_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/requests/TR-NONEXISTENT",
            json={"status": "approved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_travel_request(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/requests/TR-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/requests/TR-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_travel_request_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/requests/TR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# APPROVAL WORKFLOW
# =====================================================================


class TestApprovalWorkflow:
    """Test travel request approval workflow."""

    @pytest.mark.anyio
    async def test_approve_travel_request(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/requests/TR-008/approve",
            params={"approved_by": "Dr. Maria Lopez"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["approved_by"] == "Dr. Maria Lopez"
        assert data["approved_date"] is not None

    @pytest.mark.anyio
    async def test_approve_travel_request_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/requests/TR-NONEXISTENT/approve",
            params={"approved_by": "Dr. Test"},
        )
        assert resp.status_code == 404

    def test_approve_sets_fields(self, svc: PatientTravelService):
        result = svc.approve_travel_request("TR-008", "Dr. Approval Test")
        assert result is not None
        assert result.status.value == "approved"
        assert result.approved_by == "Dr. Approval Test"
        assert result.approved_date is not None


# =====================================================================
# BOOKING CRUD
# =====================================================================


class TestBookingCrud:
    """Test booking CRUD operations."""

    @pytest.mark.anyio
    async def test_list_bookings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/bookings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_bookings_filter_travel_request(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/bookings", params={"travel_request_id": "TR-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["travel_request_id"] == "TR-001"

    @pytest.mark.anyio
    async def test_get_booking(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/bookings/BK-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "BK-001"
        assert data["booking_type"] == "car_service"

    @pytest.mark.anyio
    async def test_get_booking_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/bookings/BK-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_booking(self, client: AsyncClient):
        payload = _make_booking_create()
        resp = await client.post(f"{API_PREFIX}/bookings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["provider"] == "Delta Airlines"
        assert data["id"].startswith("BK-")
        assert data["cancelled"] is False

    @pytest.mark.anyio
    async def test_update_booking(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/bookings/BK-001",
            json={"cancelled": True, "notes": "Patient cancelled visit"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["cancelled"] is True
        assert data["notes"] == "Patient cancelled visit"

    @pytest.mark.anyio
    async def test_update_booking_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/bookings/BK-NONEXISTENT",
            json={"cancelled": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_booking(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/bookings/BK-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/bookings/BK-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_booking_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/bookings/BK-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# REIMBURSEMENT CRUD
# =====================================================================


class TestReimbursementCrud:
    """Test reimbursement CRUD operations."""

    @pytest.mark.anyio
    async def test_list_reimbursements(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reimbursements")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_reimbursements_filter_travel_request(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reimbursements", params={"travel_request_id": "TR-009"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["travel_request_id"] == "TR-009"

    @pytest.mark.anyio
    async def test_list_reimbursements_filter_patient(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reimbursements", params={"patient_id": "PT-3001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["patient_id"] == "PT-3001"

    @pytest.mark.anyio
    async def test_list_reimbursements_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reimbursements", params={"status": "paid"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "paid"

    @pytest.mark.anyio
    async def test_get_reimbursement(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reimbursements/RE-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RE-001"
        assert data["expense_type"] == "transport"

    @pytest.mark.anyio
    async def test_get_reimbursement_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reimbursements/RE-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_reimbursement(self, client: AsyncClient):
        payload = _make_reimbursement_create()
        resp = await client.post(f"{API_PREFIX}/reimbursements", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["expense_type"] == "transport"
        assert data["status"] == "pending"
        assert data["id"].startswith("RE-")

    @pytest.mark.anyio
    async def test_update_reimbursement(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reimbursements/RE-005",
            json={"status": "approved", "reviewed_by": "Finance Team - Test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["reviewed_by"] == "Finance Team - Test"
        assert data["reviewed_date"] is not None

    @pytest.mark.anyio
    async def test_update_reimbursement_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reimbursements/RE-NONEXISTENT",
            json={"status": "approved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_reimbursement_to_paid(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reimbursements/RE-003",
            json={"status": "paid", "payment_method": "direct_deposit"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "paid"
        assert data["paid_date"] is not None
        assert data["payment_method"] == "direct_deposit"

    @pytest.mark.anyio
    async def test_update_reimbursement_deny(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reimbursements/RE-005",
            json={"status": "denied", "reviewed_by": "Finance - Reviewer", "denial_reason": "Duplicate submission"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "denied"
        assert data["denial_reason"] == "Duplicate submission"

    @pytest.mark.anyio
    async def test_delete_reimbursement(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reimbursements/RE-004")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/reimbursements/RE-004")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_reimbursement_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reimbursements/RE-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestTravelMetrics:
    """Test travel metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_requests"] == 12
        assert data["total_bookings"] == 10
        assert data["total_reimbursements"] == 10
        assert data["total_travel_cost"] > 0
        assert data["avg_cost_per_visit"] > 0
        assert data["total_patients_traveled"] > 0

    @pytest.mark.anyio
    async def test_get_metrics_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_requests"] == 4

    def test_metrics_requests_by_status(self, svc: PatientTravelService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.requests_by_status.values())
        assert total_by_status == metrics.total_requests

    def test_metrics_requests_by_transport(self, svc: PatientTravelService):
        metrics = svc.get_metrics()
        total_by_transport = sum(metrics.requests_by_transport.values())
        assert total_by_transport == metrics.total_requests

    def test_metrics_reimbursements_by_status(self, svc: PatientTravelService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.reimbursements_by_status.values())
        assert total_by_status == metrics.total_reimbursements

    def test_metrics_active_bookings(self, svc: PatientTravelService):
        metrics = svc.get_metrics()
        assert metrics.active_bookings + metrics.cancelled_bookings == metrics.total_bookings

    def test_metrics_pending_reimbursement_amount(self, svc: PatientTravelService):
        metrics = svc.get_metrics()
        assert metrics.pending_reimbursement_amount >= 0
        assert metrics.pending_reimbursement_amount <= metrics.total_reimbursement_amount

    def test_metrics_nonexistent_trial(self, svc: PatientTravelService):
        metrics = svc.get_metrics(trial_id="NONEXISTENT")
        assert metrics.total_requests == 0
        assert metrics.total_bookings == 0
        assert metrics.total_reimbursements == 0

    @pytest.mark.anyio
    async def test_metrics_nonexistent_trial_api(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_requests"] == 0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_patient_travel_service()
        svc2 = get_patient_travel_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_patient_travel_service()
        svc2 = reset_patient_travel_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_patient_travel_service()
        svc.delete_travel_request("TR-001")
        assert svc.get_travel_request("TR-001") is None
        svc2 = reset_patient_travel_service()
        assert svc2.get_travel_request("TR-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_requests_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requests")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_bookings_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/bookings")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_reimbursements_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reimbursements")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_travel_request_all_transport_modes(self, client: AsyncClient):
        for mode in ["air", "rail", "car_service", "rideshare", "personal_vehicle", "public_transit", "medical_transport"]:
            payload = _make_travel_request_create(
                transport_mode=mode,
                patient_id=f"PT-{mode}",
            )
            resp = await client.post(f"{API_PREFIX}/requests", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["transport_mode"] == mode

    @pytest.mark.anyio
    async def test_create_travel_request_all_accommodation_types(self, client: AsyncClient):
        for acc_type in ["hotel", "extended_stay", "patient_housing", "none_required"]:
            payload = _make_travel_request_create(
                accommodation_type=acc_type,
                patient_id=f"PT-{acc_type}",
            )
            resp = await client.post(f"{API_PREFIX}/requests", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["accommodation_type"] == acc_type

    @pytest.mark.anyio
    async def test_create_travel_request_all_traveler_types(self, client: AsyncClient):
        for ttype in ["patient", "caregiver", "legal_guardian"]:
            payload = _make_travel_request_create(
                traveler_type=ttype,
                patient_id=f"PT-{ttype}",
            )
            resp = await client.post(f"{API_PREFIX}/requests", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["traveler_type"] == ttype

    @pytest.mark.anyio
    async def test_create_travel_request_with_special_needs(self, client: AsyncClient):
        payload = _make_travel_request_create(
            special_needs="Wheelchair accessible transport, oxygen support required",
        )
        resp = await client.post(f"{API_PREFIX}/requests", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["special_needs"] is not None

    @pytest.mark.anyio
    async def test_booking_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/bookings/BK-001")
        data = resp.json()
        assert "id" in data
        assert "travel_request_id" in data
        assert "booking_type" in data
        assert "provider" in data
        assert "confirmation_number" in data
        assert "departure_date" in data
        assert "cost" in data
        assert "currency" in data
        assert "cancelled" in data

    @pytest.mark.anyio
    async def test_reimbursement_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reimbursements/RE-001")
        data = resp.json()
        assert "id" in data
        assert "travel_request_id" in data
        assert "patient_id" in data
        assert "expense_type" in data
        assert "amount" in data
        assert "currency" in data
        assert "receipt_provided" in data
        assert "status" in data
        assert "submitted_date" in data

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_requests" in data
        assert "requests_by_status" in data
        assert "requests_by_transport" in data
        assert "total_bookings" in data
        assert "active_bookings" in data
        assert "cancelled_bookings" in data
        assert "total_reimbursements" in data
        assert "reimbursements_by_status" in data
        assert "total_reimbursement_amount" in data
        assert "pending_reimbursement_amount" in data
        assert "total_travel_cost" in data
        assert "avg_cost_per_visit" in data
        assert "total_patients_traveled" in data
        assert "total_caregivers_traveled" in data

    def test_travel_request_has_required_fields(self, svc: PatientTravelService):
        request = svc.get_travel_request("TR-001")
        assert request is not None
        assert request.id
        assert request.trial_id
        assert request.site_id
        assert request.patient_id
        assert request.traveler_type is not None
        assert request.visit_type
        assert request.visit_date is not None
        assert request.origin_city
        assert request.destination_city
        assert request.transport_mode is not None
        assert request.status is not None

    def test_reimbursement_paid_has_payment_fields(self, svc: PatientTravelService):
        paid = svc.list_reimbursements(status=ReimbursementStatus.PAID)
        assert len(paid) > 0
        for r in paid:
            assert r.paid_date is not None
            assert r.payment_method is not None

    def test_reimbursement_denied_has_reason(self, svc: PatientTravelService):
        denied = svc.list_reimbursements(status=ReimbursementStatus.DENIED)
        assert len(denied) > 0
        for r in denied:
            assert r.denial_reason is not None
