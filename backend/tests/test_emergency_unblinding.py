"""Tests for Emergency Unblinding (EMRG-UBL).

Covers:
- Seed data verification (requests, approvals, notifications, audit logs)
- Unblinding request CRUD (create, read, update, delete, list, filter by trial/reason/status)
- Unblinding approval CRUD (create, read, update, delete, list, filter by trial/decision/request)
- Unblinding notification CRUD (create, read, update, delete, list, filter by trial/channel/acknowledged)
- Unblinding audit log CRUD (create, read, update, delete, list, filter by trial/action/request)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
- Service-level CRUD operations
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.emergency_unblinding import (
    ApprovalDecision,
    AuditAction,
    NotificationChannel,
    RequestStatus,
    UnblindingReason,
)
from app.services.emergency_unblinding_service import (
    EmergencyUnblindingService,
    get_emergency_unblinding_service,
    reset_emergency_unblinding_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/emergency-unblinding"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_emergency_unblinding_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> EmergencyUnblindingService:
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


def _make_request_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-NY-001",
        "subject_id": "SUBJ-TEST-001",
        "requestor_name": "Dr. Test User",
        "requestor_role": "Principal Investigator",
        "unblinding_reason": "medical_emergency",
        "clinical_justification": "Test clinical justification for unblinding request.",
        "is_emergency": True,
    }
    defaults.update(overrides)
    return defaults


def _make_approval_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "request_id": "UBR-001",
        "approver_name": "Dr. Test Approver",
        "approver_role": "Medical Monitor",
        "approval_decision": "approved",
        "rationale": "Test rationale for approval decision.",
        "response_time_minutes": 15,
    }
    defaults.update(overrides)
    return defaults


def _make_notification_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "request_id": "UBR-001",
        "recipient_name": "Dr. Test Recipient",
        "recipient_role": "Principal Investigator",
        "notification_channel": "email",
        "content_summary": "Test notification content summary.",
    }
    defaults.update(overrides)
    return defaults


def _make_audit_log_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "request_id": "UBR-001",
        "audit_action": "request_created",
        "performed_by": "Dr. Test User",
        "details": "Test audit log entry details.",
        "document_reference": "DOC-TEST-001",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_requests_count(self, svc: EmergencyUnblindingService):
        items = svc.list_requests()
        assert len(items) == 12

    def test_seed_requests_ids(self, svc: EmergencyUnblindingService):
        items = svc.list_requests()
        ids = {r.id for r in items}
        for i in range(1, 13):
            assert f"UBR-{i:03d}" in ids

    def test_seed_approvals_count(self, svc: EmergencyUnblindingService):
        items = svc.list_approvals()
        assert len(items) == 12

    def test_seed_approvals_ids(self, svc: EmergencyUnblindingService):
        items = svc.list_approvals()
        ids = {a.id for a in items}
        for i in range(1, 13):
            assert f"UBA-{i:03d}" in ids

    def test_seed_notifications_count(self, svc: EmergencyUnblindingService):
        items = svc.list_notifications()
        assert len(items) == 12

    def test_seed_notifications_ids(self, svc: EmergencyUnblindingService):
        items = svc.list_notifications()
        ids = {n.id for n in items}
        for i in range(1, 13):
            assert f"UBN-{i:03d}" in ids

    def test_seed_audit_logs_count(self, svc: EmergencyUnblindingService):
        items = svc.list_audit_logs()
        assert len(items) == 12

    def test_seed_audit_logs_ids(self, svc: EmergencyUnblindingService):
        items = svc.list_audit_logs()
        ids = {a.id for a in items}
        for i in range(1, 13):
            assert f"UBL-{i:03d}" in ids

    def test_seed_requests_have_all_trials(self, svc: EmergencyUnblindingService):
        items = svc.list_requests()
        trial_ids = {r.trial_id for r in items}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_requests_have_multiple_reasons(self, svc: EmergencyUnblindingService):
        items = svc.list_requests()
        reasons = {r.unblinding_reason for r in items}
        assert UnblindingReason.MEDICAL_EMERGENCY in reasons
        assert UnblindingReason.SERIOUS_ADVERSE_EVENT in reasons
        assert UnblindingReason.OVERDOSE in reasons
        assert UnblindingReason.PREGNANCY in reasons
        assert UnblindingReason.REGULATORY_REQUEST in reasons
        assert UnblindingReason.INVESTIGATOR_DECISION in reasons

    def test_seed_requests_have_multiple_statuses(self, svc: EmergencyUnblindingService):
        items = svc.list_requests()
        statuses = {r.request_status for r in items}
        assert RequestStatus.SUBMITTED in statuses
        assert RequestStatus.UNDER_REVIEW in statuses
        assert RequestStatus.APPROVED in statuses
        assert RequestStatus.DENIED in statuses
        assert RequestStatus.EXECUTED in statuses
        assert RequestStatus.CANCELLED in statuses

    def test_seed_approvals_have_multiple_decisions(self, svc: EmergencyUnblindingService):
        items = svc.list_approvals()
        decisions = {a.approval_decision for a in items}
        assert ApprovalDecision.APPROVED in decisions
        assert ApprovalDecision.DENIED in decisions
        assert ApprovalDecision.DEFERRED in decisions
        assert ApprovalDecision.CONDITIONAL in decisions
        assert ApprovalDecision.ESCALATED in decisions

    def test_seed_notifications_have_multiple_channels(self, svc: EmergencyUnblindingService):
        items = svc.list_notifications()
        channels = {n.notification_channel for n in items}
        assert NotificationChannel.EMAIL in channels
        assert NotificationChannel.PHONE in channels
        assert NotificationChannel.SMS in channels
        assert NotificationChannel.FAX in channels
        assert NotificationChannel.SYSTEM_ALERT in channels
        assert NotificationChannel.IN_PERSON in channels

    def test_seed_audit_logs_have_multiple_actions(self, svc: EmergencyUnblindingService):
        items = svc.list_audit_logs()
        actions = {a.audit_action for a in items}
        assert AuditAction.REQUEST_CREATED in actions
        assert AuditAction.APPROVAL_GRANTED in actions
        assert AuditAction.APPROVAL_DENIED in actions
        assert AuditAction.TREATMENT_REVEALED in actions
        assert AuditAction.NOTIFICATION_SENT in actions
        assert AuditAction.DOCUMENTATION_FILED in actions


# =====================================================================
# UNBLINDING REQUEST CRUD
# =====================================================================


class TestUnblindingRequestCRUD:
    """Test unblinding request create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_requests(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requests")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_requests_filter_trial_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requests", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_requests_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requests", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_requests_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requests", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_requests_filter_reason_medical_emergency(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/requests", params={"unblinding_reason": "medical_emergency"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["unblinding_reason"] == "medical_emergency"

    @pytest.mark.anyio
    async def test_list_requests_filter_reason_serious_adverse_event(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/requests", params={"unblinding_reason": "serious_adverse_event"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["unblinding_reason"] == "serious_adverse_event"

    @pytest.mark.anyio
    async def test_list_requests_filter_status_executed(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/requests", params={"request_status": "executed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["request_status"] == "executed"

    @pytest.mark.anyio
    async def test_list_requests_filter_status_submitted(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/requests", params={"request_status": "submitted"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["request_status"] == "submitted"

    @pytest.mark.anyio
    async def test_list_requests_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/requests",
            params={"trial_id": EYLEA_TRIAL, "request_status": "executed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["request_status"] == "executed"

    @pytest.mark.anyio
    async def test_list_requests_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/requests",
            params={"trial_id": "nonexistent-trial"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_request(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requests/UBR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "UBR-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["unblinding_reason"] == "medical_emergency"
        assert data["request_status"] == "executed"

    @pytest.mark.anyio
    async def test_get_request_ubr005(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requests/UBR-005")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "UBR-005"
        assert data["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_request_ubr009(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requests/UBR-009")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "UBR-009"
        assert data["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_request_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requests/UBR-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_request(self, client: AsyncClient):
        payload = _make_request_create()
        resp = await client.post(f"{API_PREFIX}/requests", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["requestor_name"] == "Dr. Test User"
        assert data["unblinding_reason"] == "medical_emergency"
        assert data["request_status"] == "submitted"
        assert data["is_emergency"] is True
        assert data["id"].startswith("UBR-")
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_request_serious_adverse_event(self, client: AsyncClient):
        payload = _make_request_create(
            unblinding_reason="serious_adverse_event",
            is_emergency=False,
        )
        resp = await client.post(f"{API_PREFIX}/requests", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["unblinding_reason"] == "serious_adverse_event"
        assert data["is_emergency"] is False

    @pytest.mark.anyio
    async def test_create_request_appears_in_list(self, client: AsyncClient):
        payload = _make_request_create(subject_id="SUBJ-UNIQUE-001")
        resp = await client.post(f"{API_PREFIX}/requests", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/requests")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert data["total"] == 13
        ids = {item["id"] for item in data["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_request_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/requests/UBR-001",
            json={"notes": "Updated notes for testing"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated notes for testing"

    @pytest.mark.anyio
    async def test_update_request_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/requests/UBR-003",
            json={"request_status": "approved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["request_status"] == "approved"

    @pytest.mark.anyio
    async def test_update_request_treatment_revealed(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/requests/UBR-002",
            json={"treatment_arm_revealed": "Active Drug 100mg"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["treatment_arm_revealed"] == "Active Drug 100mg"

    @pytest.mark.anyio
    async def test_update_request_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/requests/UBR-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_request(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/requests/UBR-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/requests/UBR-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_request_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/requests/UBR-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/requests")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_request_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/requests/UBR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# UNBLINDING APPROVAL CRUD
# =====================================================================


class TestUnblindingApprovalCRUD:
    """Test unblinding approval create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_approvals(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/approvals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_approvals_filter_trial_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/approvals", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_approvals_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/approvals", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_approvals_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/approvals", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_approvals_filter_decision_approved(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/approvals", params={"approval_decision": "approved"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["approval_decision"] == "approved"

    @pytest.mark.anyio
    async def test_list_approvals_filter_decision_denied(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/approvals", params={"approval_decision": "denied"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["approval_decision"] == "denied"

    @pytest.mark.anyio
    async def test_list_approvals_filter_decision_escalated(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/approvals", params={"approval_decision": "escalated"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["approval_decision"] == "escalated"

    @pytest.mark.anyio
    async def test_list_approvals_filter_request_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/approvals", params={"request_id": "UBR-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["request_id"] == "UBR-001"

    @pytest.mark.anyio
    async def test_list_approvals_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/approvals",
            params={"trial_id": "nonexistent-trial"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_approval(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/approvals/UBA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "UBA-001"
        assert data["approval_decision"] == "approved"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_approval_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/approvals/UBA-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_approval(self, client: AsyncClient):
        payload = _make_approval_create()
        resp = await client.post(f"{API_PREFIX}/approvals", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["approver_name"] == "Dr. Test Approver"
        assert data["approval_decision"] == "approved"
        assert data["id"].startswith("UBA-")
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_approval_denied(self, client: AsyncClient):
        payload = _make_approval_create(approval_decision="denied")
        resp = await client.post(f"{API_PREFIX}/approvals", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["approval_decision"] == "denied"

    @pytest.mark.anyio
    async def test_create_approval_appears_in_list(self, client: AsyncClient):
        payload = _make_approval_create()
        resp = await client.post(f"{API_PREFIX}/approvals", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/approvals")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert data["total"] == 13
        ids = {item["id"] for item in data["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_approval_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/approvals/UBA-001",
            json={"notes": "Updated approval notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated approval notes"

    @pytest.mark.anyio
    async def test_update_approval_conditions(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/approvals/UBA-001",
            json={"conditions": "New conditions added"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["conditions"] == "New conditions added"

    @pytest.mark.anyio
    async def test_update_approval_escalated_to(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/approvals/UBA-001",
            json={"escalated_to": "DSMB Chair"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["escalated_to"] == "DSMB Chair"

    @pytest.mark.anyio
    async def test_update_approval_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/approvals/UBA-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_approval(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/approvals/UBA-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/approvals/UBA-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_approval_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/approvals/UBA-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/approvals")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_approval_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/approvals/UBA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# UNBLINDING NOTIFICATION CRUD
# =====================================================================


class TestUnblindingNotificationCRUD:
    """Test unblinding notification create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_notifications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/notifications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_notifications_filter_trial_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/notifications", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_notifications_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/notifications", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_notifications_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/notifications", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_notifications_filter_channel_email(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/notifications", params={"notification_channel": "email"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["notification_channel"] == "email"

    @pytest.mark.anyio
    async def test_list_notifications_filter_channel_phone(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/notifications", params={"notification_channel": "phone"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["notification_channel"] == "phone"

    @pytest.mark.anyio
    async def test_list_notifications_filter_acknowledged_true(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/notifications", params={"acknowledged": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["acknowledged"] is True

    @pytest.mark.anyio
    async def test_list_notifications_filter_acknowledged_false(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/notifications", params={"acknowledged": False}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["acknowledged"] is False

    @pytest.mark.anyio
    async def test_list_notifications_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/notifications",
            params={"trial_id": "nonexistent-trial"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_notification(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/notifications/UBN-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "UBN-001"
        assert data["notification_channel"] == "phone"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_notification_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/notifications/UBN-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_notification(self, client: AsyncClient):
        payload = _make_notification_create()
        resp = await client.post(f"{API_PREFIX}/notifications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["recipient_name"] == "Dr. Test Recipient"
        assert data["notification_channel"] == "email"
        assert data["acknowledged"] is False
        assert data["id"].startswith("UBN-")
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_notification_sms(self, client: AsyncClient):
        payload = _make_notification_create(notification_channel="sms")
        resp = await client.post(f"{API_PREFIX}/notifications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["notification_channel"] == "sms"

    @pytest.mark.anyio
    async def test_create_notification_appears_in_list(self, client: AsyncClient):
        payload = _make_notification_create()
        resp = await client.post(f"{API_PREFIX}/notifications", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/notifications")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert data["total"] == 13
        ids = {item["id"] for item in data["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_notification_acknowledged(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/notifications/UBN-004",
            json={"acknowledged": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["acknowledged"] is True

    @pytest.mark.anyio
    async def test_update_notification_delivery_confirmed(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/notifications/UBN-012",
            json={"delivery_confirmed": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["delivery_confirmed"] is True

    @pytest.mark.anyio
    async def test_update_notification_retry_count(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/notifications/UBN-012",
            json={"retry_count": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["retry_count"] == 5

    @pytest.mark.anyio
    async def test_update_notification_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/notifications/UBN-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_notification(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/notifications/UBN-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/notifications/UBN-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_notification_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/notifications/UBN-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/notifications")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_notification_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/notifications/UBN-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# UNBLINDING AUDIT LOG CRUD
# =====================================================================


class TestUnblindingAuditLogCRUD:
    """Test unblinding audit log create, read, update, delete operations."""

    # --- List ---

    @pytest.mark.anyio
    async def test_list_audit_logs(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit-logs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_audit_logs_filter_trial_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit-logs", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_audit_logs_filter_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit-logs", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_audit_logs_filter_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit-logs", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_audit_logs_filter_action_request_created(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/audit-logs", params={"audit_action": "request_created"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["audit_action"] == "request_created"

    @pytest.mark.anyio
    async def test_list_audit_logs_filter_action_treatment_revealed(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/audit-logs", params={"audit_action": "treatment_revealed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["audit_action"] == "treatment_revealed"

    @pytest.mark.anyio
    async def test_list_audit_logs_filter_request_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/audit-logs", params={"request_id": "UBR-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["request_id"] == "UBR-001"

    @pytest.mark.anyio
    async def test_list_audit_logs_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/audit-logs",
            params={"trial_id": "nonexistent-trial"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # --- Get ---

    @pytest.mark.anyio
    async def test_get_audit_log(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit-logs/UBL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "UBL-001"
        assert data["audit_action"] == "request_created"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_audit_log_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit-logs/UBL-NONEXISTENT")
        assert resp.status_code == 404

    # --- Create ---

    @pytest.mark.anyio
    async def test_create_audit_log(self, client: AsyncClient):
        payload = _make_audit_log_create()
        resp = await client.post(f"{API_PREFIX}/audit-logs", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["performed_by"] == "Dr. Test User"
        assert data["audit_action"] == "request_created"
        assert data["regulatory_reported"] is False
        assert data["id"].startswith("UBL-")
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_audit_log_treatment_revealed(self, client: AsyncClient):
        payload = _make_audit_log_create(audit_action="treatment_revealed")
        resp = await client.post(f"{API_PREFIX}/audit-logs", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["audit_action"] == "treatment_revealed"

    @pytest.mark.anyio
    async def test_create_audit_log_appears_in_list(self, client: AsyncClient):
        payload = _make_audit_log_create()
        resp = await client.post(f"{API_PREFIX}/audit-logs", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/audit-logs")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert data["total"] == 13
        ids = {item["id"] for item in data["items"]}
        assert new_id in ids

    # --- Update ---

    @pytest.mark.anyio
    async def test_update_audit_log_regulatory_reported(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/audit-logs/UBL-004",
            json={"regulatory_reported": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["regulatory_reported"] is True

    @pytest.mark.anyio
    async def test_update_audit_log_notes(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/audit-logs/UBL-001",
            json={"notes": "Updated audit notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated audit notes"

    @pytest.mark.anyio
    async def test_update_audit_log_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/audit-logs/UBL-NONEXISTENT",
            json={"notes": "Should fail"},
        )
        assert resp.status_code == 404

    # --- Delete ---

    @pytest.mark.anyio
    async def test_delete_audit_log(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/audit-logs/UBL-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/audit-logs/UBL-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_audit_log_reduces_count(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/audit-logs/UBL-012")
        assert resp.status_code == 204
        list_resp = await client.get(f"{API_PREFIX}/audit-logs")
        assert list_resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_audit_log_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/audit-logs/UBL-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test emergency unblinding metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_requests"] == 12
        assert data["total_approvals"] == 12
        assert data["total_notifications"] == 12
        assert data["total_audit_entries"] == 12

    @pytest.mark.anyio
    async def test_metrics_requests_by_reason(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        requests_by_reason = data["requests_by_reason"]
        assert "medical_emergency" in requests_by_reason
        assert "serious_adverse_event" in requests_by_reason
        total_by_reason = sum(requests_by_reason.values())
        assert total_by_reason == 12

    @pytest.mark.anyio
    async def test_metrics_requests_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        requests_by_status = data["requests_by_status"]
        assert "executed" in requests_by_status
        assert "submitted" in requests_by_status
        total_by_status = sum(requests_by_status.values())
        assert total_by_status == 12

    @pytest.mark.anyio
    async def test_metrics_emergency_request_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["emergency_request_rate"] > 0
        assert data["emergency_request_rate"] <= 100

    @pytest.mark.anyio
    async def test_metrics_approvals_by_decision(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        approvals_by_decision = data["approvals_by_decision"]
        assert "approved" in approvals_by_decision
        total_by_decision = sum(approvals_by_decision.values())
        assert total_by_decision == 12

    @pytest.mark.anyio
    async def test_metrics_avg_response_time(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_response_time_minutes"] > 0

    @pytest.mark.anyio
    async def test_metrics_notification_acknowledgment_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["notification_acknowledgment_rate"] > 0
        assert data["notification_acknowledgment_rate"] <= 100

    @pytest.mark.anyio
    async def test_metrics_audit_actions_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        audit_actions_by_type = data["audit_actions_by_type"]
        assert "request_created" in audit_actions_by_type
        total_by_type = sum(audit_actions_by_type.values())
        assert total_by_type == 12

    @pytest.mark.anyio
    async def test_metrics_regulatory_reporting_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["regulatory_reporting_rate"] > 0
        assert data["regulatory_reporting_rate"] <= 100

    def test_service_metrics_emergency_rate(self, svc: EmergencyUnblindingService):
        metrics = svc.get_metrics()
        requests = svc.list_requests()
        emergency_count = sum(1 for r in requests if r.is_emergency)
        expected_rate = round((emergency_count / max(1, len(requests))) * 100, 1)
        assert metrics.emergency_request_rate == expected_rate

    def test_service_metrics_avg_response_time(self, svc: EmergencyUnblindingService):
        metrics = svc.get_metrics()
        approvals = svc.list_approvals()
        times = [a.response_time_minutes for a in approvals]
        expected = round(sum(times) / max(1, len(times)), 1)
        assert metrics.avg_response_time_minutes == expected

    def test_service_metrics_ack_rate(self, svc: EmergencyUnblindingService):
        metrics = svc.get_metrics()
        notifications = svc.list_notifications()
        acked = sum(1 for n in notifications if n.acknowledged)
        expected = round((acked / max(1, len(notifications))) * 100, 1)
        assert metrics.notification_acknowledgment_rate == expected

    def test_service_metrics_regulatory_rate(self, svc: EmergencyUnblindingService):
        metrics = svc.get_metrics()
        audit_logs = svc.list_audit_logs()
        reported = sum(1 for a in audit_logs if a.regulatory_reported)
        expected = round((reported / max(1, len(audit_logs))) * 100, 1)
        assert metrics.regulatory_reporting_rate == expected

    @pytest.mark.anyio
    async def test_metrics_with_trial_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_requests"] > 0
        assert data["total_requests"] < 12

    @pytest.mark.anyio
    async def test_metrics_with_trial_filter_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_requests"] > 0
        assert data["total_requests"] < 12

    def test_service_metrics_with_trial_filter(self, svc: EmergencyUnblindingService):
        metrics = svc.get_metrics(trial_id=EYLEA_TRIAL)
        assert metrics.total_requests > 0
        assert metrics.total_requests < 12

    def test_service_metrics_after_create(self, svc: EmergencyUnblindingService):
        """Metrics should update after creating a new request."""
        from app.schemas.emergency_unblinding import UnblindingRequestCreate

        initial_metrics = svc.get_metrics()
        svc.create_request(
            UnblindingRequestCreate(
                trial_id=EYLEA_TRIAL,
                site_id="SITE-NY-001",
                subject_id="SUBJ-NEW",
                requestor_name="Dr. New",
                requestor_role="PI",
                unblinding_reason=UnblindingReason.MEDICAL_EMERGENCY,
                clinical_justification="Test justification",
            )
        )
        updated_metrics = svc.get_metrics()
        assert updated_metrics.total_requests == initial_metrics.total_requests + 1

    def test_service_metrics_after_delete(self, svc: EmergencyUnblindingService):
        """Metrics should update after deleting a request."""
        initial_metrics = svc.get_metrics()
        svc.delete_request("UBR-001")
        updated_metrics = svc.get_metrics()
        assert updated_metrics.total_requests == initial_metrics.total_requests - 1


# =====================================================================
# EDGE CASES
# =====================================================================


class TestEdgeCases:
    @pytest.mark.anyio
    async def test_update_request_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requests/UBR-001")
        original = resp.json()
        original_reason = original["unblinding_reason"]

        resp2 = await client.put(
            f"{API_PREFIX}/requests/UBR-001",
            json={"notes": "Partial update"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["unblinding_reason"] == original_reason
        assert updated["notes"] == "Partial update"

    @pytest.mark.anyio
    async def test_update_approval_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/approvals/UBA-001")
        original = resp.json()
        original_decision = original["approval_decision"]

        resp2 = await client.put(
            f"{API_PREFIX}/approvals/UBA-001",
            json={"notes": "Updated approval note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["approval_decision"] == original_decision

    @pytest.mark.anyio
    async def test_update_notification_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/notifications/UBN-001")
        original = resp.json()
        original_channel = original["notification_channel"]

        resp2 = await client.put(
            f"{API_PREFIX}/notifications/UBN-001",
            json={"notes": "Updated notification note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["notification_channel"] == original_channel

    @pytest.mark.anyio
    async def test_update_audit_log_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit-logs/UBL-001")
        original = resp.json()
        original_action = original["audit_action"]

        resp2 = await client.put(
            f"{API_PREFIX}/audit-logs/UBL-001",
            json={"notes": "Updated audit note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["audit_action"] == original_action


# =====================================================================
# SINGLETON PATTERN
# =====================================================================


class TestSingleton:
    def test_get_returns_same_instance(self):
        svc1 = get_emergency_unblinding_service()
        svc2 = get_emergency_unblinding_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        svc1 = get_emergency_unblinding_service()
        svc2 = reset_emergency_unblinding_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_emergency_unblinding_service()
        svc.delete_request("UBR-001")
        assert svc.get_request("UBR-001") is None
        svc2 = reset_emergency_unblinding_service()
        assert svc2.get_request("UBR-001") is not None

    def test_reset_reseeds_approvals(self):
        svc = get_emergency_unblinding_service()
        svc.delete_approval("UBA-001")
        assert svc.get_approval("UBA-001") is None
        svc2 = reset_emergency_unblinding_service()
        assert svc2.get_approval("UBA-001") is not None

    def test_reset_reseeds_notifications(self):
        svc = get_emergency_unblinding_service()
        svc.delete_notification("UBN-001")
        assert svc.get_notification("UBN-001") is None
        svc2 = reset_emergency_unblinding_service()
        assert svc2.get_notification("UBN-001") is not None

    def test_reset_reseeds_audit_logs(self):
        svc = get_emergency_unblinding_service()
        svc.delete_audit_log("UBL-001")
        assert svc.get_audit_log("UBL-001") is None
        svc2 = reset_emergency_unblinding_service()
        assert svc2.get_audit_log("UBL-001") is not None

    def test_get_after_reset_returns_new_instance(self):
        svc1 = get_emergency_unblinding_service()
        reset_emergency_unblinding_service()
        svc2 = get_emergency_unblinding_service()
        assert svc1 is not svc2


# =====================================================================
# SERVICE-LEVEL CRUD
# =====================================================================


class TestServiceLevelCRUD:
    def test_list_requests_service(self, svc: EmergencyUnblindingService):
        items = svc.list_requests()
        assert len(items) == 12

    def test_get_request_service(self, svc: EmergencyUnblindingService):
        record = svc.get_request("UBR-001")
        assert record is not None
        assert record.id == "UBR-001"

    def test_list_approvals_service(self, svc: EmergencyUnblindingService):
        items = svc.list_approvals()
        assert len(items) == 12

    def test_get_approval_service(self, svc: EmergencyUnblindingService):
        record = svc.get_approval("UBA-001")
        assert record is not None
        assert record.id == "UBA-001"

    def test_list_notifications_service(self, svc: EmergencyUnblindingService):
        items = svc.list_notifications()
        assert len(items) == 12

    def test_get_notification_service(self, svc: EmergencyUnblindingService):
        record = svc.get_notification("UBN-001")
        assert record is not None
        assert record.id == "UBN-001"

    def test_list_audit_logs_service(self, svc: EmergencyUnblindingService):
        items = svc.list_audit_logs()
        assert len(items) == 12

    def test_get_audit_log_service(self, svc: EmergencyUnblindingService):
        record = svc.get_audit_log("UBL-001")
        assert record is not None
        assert record.id == "UBL-001"

    def test_delete_request_service(self, svc: EmergencyUnblindingService):
        assert svc.delete_request("UBR-001") is True
        assert svc.get_request("UBR-001") is None

    def test_delete_nonexistent_request_returns_false(self, svc: EmergencyUnblindingService):
        assert svc.delete_request("NONEXISTENT") is False

    def test_delete_approval_service(self, svc: EmergencyUnblindingService):
        assert svc.delete_approval("UBA-001") is True
        assert svc.get_approval("UBA-001") is None

    def test_delete_nonexistent_approval_returns_false(self, svc: EmergencyUnblindingService):
        assert svc.delete_approval("NONEXISTENT") is False

    def test_delete_notification_service(self, svc: EmergencyUnblindingService):
        assert svc.delete_notification("UBN-001") is True
        assert svc.get_notification("UBN-001") is None

    def test_delete_nonexistent_notification_returns_false(self, svc: EmergencyUnblindingService):
        assert svc.delete_notification("NONEXISTENT") is False

    def test_delete_audit_log_service(self, svc: EmergencyUnblindingService):
        assert svc.delete_audit_log("UBL-001") is True
        assert svc.get_audit_log("UBL-001") is None

    def test_delete_nonexistent_audit_log_returns_false(self, svc: EmergencyUnblindingService):
        assert svc.delete_audit_log("NONEXISTENT") is False

    def test_filter_requests_by_trial(self, svc: EmergencyUnblindingService):
        items = svc.list_requests(trial_id=EYLEA_TRIAL)
        for item in items:
            assert item.trial_id == EYLEA_TRIAL

    def test_filter_requests_by_reason(self, svc: EmergencyUnblindingService):
        items = svc.list_requests(unblinding_reason=UnblindingReason.MEDICAL_EMERGENCY)
        assert len(items) > 0
        for item in items:
            assert item.unblinding_reason == UnblindingReason.MEDICAL_EMERGENCY

    def test_filter_requests_by_status(self, svc: EmergencyUnblindingService):
        items = svc.list_requests(request_status=RequestStatus.EXECUTED)
        assert len(items) > 0
        for item in items:
            assert item.request_status == RequestStatus.EXECUTED

    def test_filter_approvals_by_decision(self, svc: EmergencyUnblindingService):
        items = svc.list_approvals(approval_decision=ApprovalDecision.APPROVED)
        assert len(items) > 0
        for item in items:
            assert item.approval_decision == ApprovalDecision.APPROVED

    def test_filter_notifications_by_channel(self, svc: EmergencyUnblindingService):
        items = svc.list_notifications(notification_channel=NotificationChannel.EMAIL)
        assert len(items) > 0
        for item in items:
            assert item.notification_channel == NotificationChannel.EMAIL

    def test_filter_notifications_by_acknowledged(self, svc: EmergencyUnblindingService):
        acked = svc.list_notifications(acknowledged=True)
        not_acked = svc.list_notifications(acknowledged=False)
        assert len(acked) + len(not_acked) == 12
        assert len(not_acked) > 0

    def test_filter_audit_logs_by_action(self, svc: EmergencyUnblindingService):
        items = svc.list_audit_logs(audit_action=AuditAction.REQUEST_CREATED)
        assert len(items) > 0
        for item in items:
            assert item.audit_action == AuditAction.REQUEST_CREATED

    def test_get_request_none(self, svc: EmergencyUnblindingService):
        result = svc.get_request("UBR-NONEXISTENT")
        assert result is None

    def test_get_approval_none(self, svc: EmergencyUnblindingService):
        result = svc.get_approval("UBA-NONEXISTENT")
        assert result is None

    def test_get_notification_none(self, svc: EmergencyUnblindingService):
        result = svc.get_notification("UBN-NONEXISTENT")
        assert result is None

    def test_get_audit_log_none(self, svc: EmergencyUnblindingService):
        result = svc.get_audit_log("UBL-NONEXISTENT")
        assert result is None
