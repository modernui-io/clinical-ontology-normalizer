"""Tests for Unblinding Management (CLINICAL-UBM).

Covers:
- Seed data verification (requests, policies)
- Request CRUD (create, read, update, list, filter by trial/site/status/type)
- Full lifecycle: requested -> approved -> executed
- Denial path: requested -> denied
- Cancel path: requested -> cancelled
- Cancel from approved: approved -> cancelled
- Invalid state transitions (400 errors)
- Policy CRUD (create, read, update, list, filter by trial)
- Metrics endpoint
- 404 error handling for missing resources
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.unblinding_management import (
    ApprovalAuthority,
    BlindingLevel,
    UnblindingStatus,
    UnblindingType,
)
from app.services.unblinding_management_service import (
    UnblindingManagementService,
    get_unblinding_management_service,
    reset_unblinding_management_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/unblinding-management"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_unblinding_management_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> UnblindingManagementService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "patient_id": "PAT-99999",
        "unblinding_type": "emergency",
        "blinding_level": "double_blind",
        "reason": "Patient experienced severe adverse event requiring treatment knowledge",
        "clinical_justification": "Grade 3 hepatotoxicity requiring urgent treatment decision",
        "requested_by": "Dr. Test Investigator",
        "was_emergency": True,
    }
    defaults.update(overrides)
    return defaults


def _make_policy_create(**overrides) -> dict:
    defaults = {
        "trial_id": "TRIAL-NEW-001",
        "blinding_level": "double_blind",
        "emergency_procedure": "Contact IRT system 24/7 for emergency code break",
        "interim_unblinding_plan": "DSMB interim analysis at 50% enrollment",
        "final_unblinding_plan": "Final unblinding after database lock",
        "authorized_unblinders": ["IRT System", "Lead Biostatistician"],
        "code_break_instructions": "Call IRT hotline at +1-800-555-0300",
        "notification_requirements": [
            "Medical Monitor within 4 hours",
            "DSMB within 24 hours",
        ],
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_requests_count(self, svc: UnblindingManagementService):
        requests = svc.list_requests()
        assert len(requests) == 6

    def test_seed_policies_count(self, svc: UnblindingManagementService):
        policies = svc.list_policies()
        assert len(policies) == 3

    def test_seed_has_all_statuses(self, svc: UnblindingManagementService):
        requests = svc.list_requests()
        statuses = {r.status for r in requests}
        assert UnblindingStatus.EXECUTED in statuses
        assert UnblindingStatus.APPROVED in statuses
        assert UnblindingStatus.DENIED in statuses
        assert UnblindingStatus.REQUESTED in statuses
        assert UnblindingStatus.CANCELLED in statuses

    def test_seed_has_emergency_requests(self, svc: UnblindingManagementService):
        requests = svc.list_requests()
        emergency = [r for r in requests if r.was_emergency]
        assert len(emergency) >= 1

    def test_seed_executed_request_has_treatment(self, svc: UnblindingManagementService):
        req = svc.get_request("UBR-001")
        assert req is not None
        assert req.status == UnblindingStatus.EXECUTED
        assert req.treatment_assignment is not None
        assert req.executed_by is not None
        assert req.executed_date is not None

    def test_seed_policies_cover_all_trials(self, svc: UnblindingManagementService):
        policies = svc.list_policies()
        trial_ids = {p.trial_id for p in policies}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids


# =====================================================================
# REQUEST CRUD
# =====================================================================


class TestRequestCrud:
    """Test unblinding request create, read, update, list operations."""

    @pytest.mark.anyio
    async def test_list_requests(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requests")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6
        assert len(data["items"]) == 6

    @pytest.mark.anyio
    async def test_list_requests_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/requests", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_requests_filter_site(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/requests", params={"site_id": "SITE-105"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-105"

    @pytest.mark.anyio
    async def test_list_requests_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/requests", params={"status": "executed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "executed"

    @pytest.mark.anyio
    async def test_list_requests_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/requests", params={"unblinding_type": "emergency"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["unblinding_type"] == "emergency"

    @pytest.mark.anyio
    async def test_get_request(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requests/UBR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "UBR-001"
        assert data["unblinding_type"] == "emergency"
        assert data["status"] == "executed"

    @pytest.mark.anyio
    async def test_get_request_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requests/UBR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_request(self, client: AsyncClient):
        payload = _make_request_create()
        resp = await client.post(f"{API_PREFIX}/requests", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "requested"
        assert data["unblinding_type"] == "emergency"
        assert data["requested_by"] == "Dr. Test Investigator"
        assert data["id"].startswith("UBR-")
        assert data["was_emergency"] is True

    @pytest.mark.anyio
    async def test_create_request_non_emergency(self, client: AsyncClient):
        payload = _make_request_create(
            unblinding_type="interim_analysis",
            was_emergency=False,
            patient_id=None,
            reason="DSMB requests interim analysis unblinding",
        )
        resp = await client.post(f"{API_PREFIX}/requests", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["unblinding_type"] == "interim_analysis"
        assert data["was_emergency"] is False

    @pytest.mark.anyio
    async def test_update_request(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/requests/UBR-005",
            json={
                "reason": "Updated FDA safety request reason",
                "notification_list": ["FDA", "Medical Monitor", "DSMB"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reason"] == "Updated FDA safety request reason"
        assert "FDA" in data["notification_list"]

    @pytest.mark.anyio
    async def test_update_request_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/requests/UBR-NONEXISTENT",
            json={"reason": "Test"},
        )
        assert resp.status_code == 404


# =====================================================================
# FULL LIFECYCLE: REQUESTED -> APPROVED -> EXECUTED
# =====================================================================


class TestFullLifecycle:
    """Test the complete unblinding request lifecycle."""

    @pytest.mark.anyio
    async def test_requested_to_approved_to_executed(self, client: AsyncClient):
        # Step 1: Create a new request
        create_payload = _make_request_create()
        resp = await client.post(f"{API_PREFIX}/requests", json=create_payload)
        assert resp.status_code == 201
        request_id = resp.json()["id"]
        assert resp.json()["status"] == "requested"

        # Step 2: Approve the request
        approve_payload = {
            "approved_by": "Dr. Senior Medical Officer",
            "approval_authority": "sponsor_medical_officer",
        }
        resp = await client.post(
            f"{API_PREFIX}/requests/{request_id}/approve", json=approve_payload
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["approved_by"] == "Dr. Senior Medical Officer"
        assert data["approval_authority"] == "sponsor_medical_officer"
        assert data["approved_date"] is not None

        # Step 3: Execute the unblinding
        execute_payload = {
            "executed_by": "Dr. Study Pharmacist",
            "treatment_assignment": "Placebo",
        }
        resp = await client.post(
            f"{API_PREFIX}/requests/{request_id}/execute", json=execute_payload
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "executed"
        assert data["executed_by"] == "Dr. Study Pharmacist"
        assert data["treatment_assignment"] == "Placebo"
        assert data["executed_date"] is not None

    @pytest.mark.anyio
    async def test_approve_already_approved(self, client: AsyncClient):
        """Cannot approve a request that is already approved."""
        approve_payload = {
            "approved_by": "Dr. Test",
            "approval_authority": "investigator",
        }
        # UBR-003 is already approved
        resp = await client.post(
            f"{API_PREFIX}/requests/UBR-003/approve", json=approve_payload
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_execute_non_approved(self, client: AsyncClient):
        """Cannot execute a request that is not approved."""
        execute_payload = {
            "executed_by": "Dr. Test",
            "treatment_assignment": "Active Drug",
        }
        # UBR-005 is in 'requested' status
        resp = await client.post(
            f"{API_PREFIX}/requests/UBR-005/execute", json=execute_payload
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_execute_already_executed(self, client: AsyncClient):
        """Cannot execute a request that is already executed."""
        execute_payload = {
            "executed_by": "Dr. Test",
            "treatment_assignment": "Active Drug",
        }
        # UBR-001 is already executed
        resp = await client.post(
            f"{API_PREFIX}/requests/UBR-001/execute", json=execute_payload
        )
        assert resp.status_code == 400


# =====================================================================
# DENIAL PATH
# =====================================================================


class TestDenialPath:
    """Test the denial path for unblinding requests."""

    @pytest.mark.anyio
    async def test_deny_request(self, client: AsyncClient):
        deny_payload = {
            "denied_by": "Dr. Medical Monitor",
            "denial_reason": "No clinical safety justification for unblinding",
        }
        # UBR-005 is in 'requested' status
        resp = await client.post(
            f"{API_PREFIX}/requests/UBR-005/deny", json=deny_payload
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "denied"
        assert "Dr. Medical Monitor" in data["impact_on_study"]

    @pytest.mark.anyio
    async def test_deny_already_denied(self, client: AsyncClient):
        """Cannot deny a request that is already denied."""
        deny_payload = {
            "denied_by": "Dr. Test",
            "denial_reason": "Test",
        }
        # UBR-004 is already denied
        resp = await client.post(
            f"{API_PREFIX}/requests/UBR-004/deny", json=deny_payload
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_deny_executed_request(self, client: AsyncClient):
        """Cannot deny a request that is already executed."""
        deny_payload = {
            "denied_by": "Dr. Test",
            "denial_reason": "Test",
        }
        # UBR-001 is already executed
        resp = await client.post(
            f"{API_PREFIX}/requests/UBR-001/deny", json=deny_payload
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_deny_not_found(self, client: AsyncClient):
        deny_payload = {
            "denied_by": "Dr. Test",
            "denial_reason": "Test",
        }
        resp = await client.post(
            f"{API_PREFIX}/requests/UBR-NONEXISTENT/deny", json=deny_payload
        )
        assert resp.status_code == 404


# =====================================================================
# CANCEL PATH
# =====================================================================


class TestCancelPath:
    """Test the cancellation path for unblinding requests."""

    @pytest.mark.anyio
    async def test_cancel_requested(self, client: AsyncClient):
        cancel_payload = {
            "cancelled_by": "Dr. Investigator",
            "cancellation_reason": "Clinical assessment determined unblinding unnecessary",
        }
        # UBR-005 is in 'requested' status
        resp = await client.post(
            f"{API_PREFIX}/requests/UBR-005/cancel", json=cancel_payload
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"
        assert "Dr. Investigator" in data["impact_on_study"]

    @pytest.mark.anyio
    async def test_cancel_approved(self, client: AsyncClient):
        """Can cancel a request that has been approved but not yet executed."""
        cancel_payload = {
            "cancelled_by": "Dr. Program Lead",
            "cancellation_reason": "Final unblinding postponed pending data validation",
        }
        # UBR-003 is in 'approved' status
        resp = await client.post(
            f"{API_PREFIX}/requests/UBR-003/cancel", json=cancel_payload
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"

    @pytest.mark.anyio
    async def test_cancel_executed_fails(self, client: AsyncClient):
        """Cannot cancel a request that is already executed."""
        cancel_payload = {
            "cancelled_by": "Dr. Test",
            "cancellation_reason": "Test",
        }
        # UBR-001 is already executed
        resp = await client.post(
            f"{API_PREFIX}/requests/UBR-001/cancel", json=cancel_payload
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_cancel_denied_fails(self, client: AsyncClient):
        """Cannot cancel a request that is already denied."""
        cancel_payload = {
            "cancelled_by": "Dr. Test",
            "cancellation_reason": "Test",
        }
        # UBR-004 is already denied
        resp = await client.post(
            f"{API_PREFIX}/requests/UBR-004/cancel", json=cancel_payload
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_cancel_not_found(self, client: AsyncClient):
        cancel_payload = {
            "cancelled_by": "Dr. Test",
            "cancellation_reason": "Test",
        }
        resp = await client.post(
            f"{API_PREFIX}/requests/UBR-NONEXISTENT/cancel", json=cancel_payload
        )
        assert resp.status_code == 404


# =====================================================================
# APPROVE / EXECUTE 404 HANDLING
# =====================================================================


class TestActionNotFound:
    """Test 404 handling for action endpoints."""

    @pytest.mark.anyio
    async def test_approve_not_found(self, client: AsyncClient):
        payload = {
            "approved_by": "Dr. Test",
            "approval_authority": "investigator",
        }
        resp = await client.post(
            f"{API_PREFIX}/requests/UBR-NONEXISTENT/approve", json=payload
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_execute_not_found(self, client: AsyncClient):
        payload = {
            "executed_by": "Dr. Test",
            "treatment_assignment": "Active Drug",
        }
        resp = await client.post(
            f"{API_PREFIX}/requests/UBR-NONEXISTENT/execute", json=payload
        )
        assert resp.status_code == 404


# =====================================================================
# POLICY CRUD
# =====================================================================


class TestPolicyCrud:
    """Test unblinding policy CRUD operations."""

    @pytest.mark.anyio
    async def test_list_policies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/policies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    @pytest.mark.anyio
    async def test_list_policies_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/policies", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_policy(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/policies/UBP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "UBP-001"
        assert data["blinding_level"] == "double_blind"
        assert len(data["authorized_unblinders"]) > 0

    @pytest.mark.anyio
    async def test_get_policy_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/policies/UBP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_policy(self, client: AsyncClient):
        payload = _make_policy_create()
        resp = await client.post(f"{API_PREFIX}/policies", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == "TRIAL-NEW-001"
        assert data["blinding_level"] == "double_blind"
        assert data["id"].startswith("UBP-")
        assert len(data["authorized_unblinders"]) == 2

    @pytest.mark.anyio
    async def test_update_policy(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/policies/UBP-001",
            json={
                "emergency_procedure": "Updated emergency procedure with new hotline",
                "authorized_unblinders": [
                    "IRT System",
                    "Lead Biostatistician",
                    "New Authorized Person",
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "Updated emergency procedure" in data["emergency_procedure"]
        assert len(data["authorized_unblinders"]) == 3

    @pytest.mark.anyio
    async def test_update_policy_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/policies/UBP-NONEXISTENT",
            json={"emergency_procedure": "Test"},
        )
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test unblinding management metrics."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_requests"] == 6
        assert data["total_policies"] == 3
        assert data["executed_count"] >= 1
        assert data["denied_count"] >= 1
        assert data["cancelled_count"] >= 1
        assert data["pending_requests"] >= 1
        assert data["emergency_unblinding_count"] >= 1

    @pytest.mark.anyio
    async def test_metrics_requests_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["requests_by_status"]
        total_by_status = sum(by_status.values())
        assert total_by_status == data["total_requests"]

    @pytest.mark.anyio
    async def test_metrics_requests_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_type = data["requests_by_type"]
        total_by_type = sum(by_type.values())
        assert total_by_type == data["total_requests"]

    @pytest.mark.anyio
    async def test_metrics_approval_time(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        # There are approved/executed requests with approval times
        assert data["average_approval_time_hours"] is not None
        assert data["average_approval_time_hours"] >= 0

    def test_metrics_consistency(self, svc: UnblindingManagementService):
        metrics = svc.get_metrics()
        assert (
            metrics.executed_count
            + metrics.denied_count
            + metrics.cancelled_count
            + metrics.pending_requests
            == metrics.total_requests
        )


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_unblinding_management_service()
        svc2 = get_unblinding_management_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_unblinding_management_service()
        svc2 = reset_unblinding_management_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_unblinding_management_service()
        # Create a new request to change state
        from app.schemas.unblinding_management import UnblindingRequestCreate

        svc.create_request(
            UnblindingRequestCreate(
                trial_id=EYLEA_TRIAL,
                site_id="SITE-101",
                unblinding_type=UnblindingType.EMERGENCY,
                blinding_level=BlindingLevel.DOUBLE_BLIND,
                reason="Test",
                requested_by="Test",
            )
        )
        assert len(svc.list_requests()) == 7
        # Reset should go back to 6
        svc2 = reset_unblinding_management_service()
        assert len(svc2.list_requests()) == 6


# =====================================================================
# EDGE CASES
# =====================================================================


class TestEdgeCases:
    """Test edge cases and additional scenarios."""

    @pytest.mark.anyio
    async def test_list_requests_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requests")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_policies_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/policies")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_request_minimal_fields(self, client: AsyncClient):
        """Create a request with only required fields."""
        payload = {
            "trial_id": DUPIXENT_TRIAL,
            "site_id": "SITE-103",
            "unblinding_type": "final",
            "blinding_level": "double_blind",
            "reason": "Final study analysis",
            "requested_by": "Dr. Minimal Test",
        }
        resp = await client.post(f"{API_PREFIX}/requests", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] is None
        assert data["clinical_justification"] is None
        assert data["was_emergency"] is False

    @pytest.mark.anyio
    async def test_requests_sorted_by_date_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requests")
        data = resp.json()
        dates = [item["requested_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_create_policy_with_all_fields(self, client: AsyncClient):
        payload = _make_policy_create(
            blinding_level="single_blind",
            interim_unblinding_plan="DSMB analysis at 25% and 50%",
        )
        resp = await client.post(f"{API_PREFIX}/policies", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["blinding_level"] == "single_blind"
        assert "DSMB analysis" in data["interim_unblinding_plan"]

    @pytest.mark.anyio
    async def test_update_request_impact_on_study(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/requests/UBR-005",
            json={
                "impact_on_study": "Minimal impact - single patient regulatory query",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "Minimal impact" in data["impact_on_study"]

    @pytest.mark.anyio
    async def test_filter_by_multiple_criteria(self, client: AsyncClient):
        """Filter requests by both trial_id and status."""
        resp = await client.get(
            f"{API_PREFIX}/requests",
            params={"trial_id": EYLEA_TRIAL, "status": "executed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["status"] == "executed"

    @pytest.mark.anyio
    async def test_all_unblinding_types_createable(self, client: AsyncClient):
        """Verify all unblinding types can be used in request creation."""
        for ub_type in [
            "emergency",
            "interim_analysis",
            "final",
            "regulatory_request",
            "dsmb_request",
            "individual_patient",
        ]:
            payload = _make_request_create(unblinding_type=ub_type)
            resp = await client.post(f"{API_PREFIX}/requests", json=payload)
            assert resp.status_code == 201
            assert resp.json()["unblinding_type"] == ub_type

    @pytest.mark.anyio
    async def test_all_blinding_levels_in_policy(self, client: AsyncClient):
        """Verify all blinding levels can be used in policy creation."""
        for level in ["double_blind", "single_blind", "open_label", "observer_blind"]:
            payload = _make_policy_create(blinding_level=level)
            resp = await client.post(f"{API_PREFIX}/policies", json=payload)
            assert resp.status_code == 201
            assert resp.json()["blinding_level"] == level
