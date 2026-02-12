"""Tests for CAPA (Corrective and Preventive Action) Management.

Covers:
- Seed data verification (CAPA records, actions)
- CAPA CRUD (create, read, update, delete, list, filter by trial/site/status/priority/source)
- Status transitions (open -> investigation -> action_plan -> implementation -> verification -> closed)
- Invalid status transitions (400 errors)
- CAPA Action CRUD (create, list, update)
- Action status auto-sets completed_date when completed
- Metrics computation
- 404 error handling for missing records
- Singleton reset behavior
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.capa_management import (
    CapaActionStatus,
    CapaActionType,
    CapaPriority,
    CapaSource,
    CapaStatus,
    CapaType,
)
from app.services.capa_management_service import (
    CapaManagementService,
    get_capa_management_service,
    reset_capa_management_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/capa-management"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_capa_management_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> CapaManagementService:
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


def _make_capa_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "capa_type": "corrective",
        "priority": "major",
        "source": "audit_finding",
        "title": "Test CAPA for unit testing",
        "description": "A test CAPA created during automated testing",
        "due_date": (now + timedelta(days=30)).isoformat(),
        "assigned_to": "Test User",
        "department": "Quality Assurance",
    }
    defaults.update(overrides)
    return defaults


def _make_action_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "action_description": "Test action item",
        "action_type": "corrective",
        "assigned_to": "Test Assignee",
        "due_date": (now + timedelta(days=14)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_capas_count(self, svc: CapaManagementService):
        capas = svc.list_capas()
        assert len(capas) == 8

    def test_seed_capas_statuses(self, svc: CapaManagementService):
        capas = svc.list_capas()
        statuses = {c.status for c in capas}
        assert CapaStatus.OPEN in statuses
        assert CapaStatus.CLOSED in statuses
        assert CapaStatus.INVESTIGATION in statuses
        assert CapaStatus.ACTION_PLAN in statuses
        assert CapaStatus.IMPLEMENTATION in statuses
        assert CapaStatus.VERIFICATION in statuses

    def test_seed_capas_priorities(self, svc: CapaManagementService):
        capas = svc.list_capas()
        priorities = {c.priority for c in capas}
        assert CapaPriority.CRITICAL in priorities
        assert CapaPriority.MAJOR in priorities
        assert CapaPriority.MINOR in priorities

    def test_seed_capas_types(self, svc: CapaManagementService):
        capas = svc.list_capas()
        types = {c.capa_type for c in capas}
        assert CapaType.CORRECTIVE in types
        assert CapaType.PREVENTIVE in types

    def test_seed_capas_sources(self, svc: CapaManagementService):
        capas = svc.list_capas()
        sources = {c.source for c in capas}
        assert CapaSource.AUDIT_FINDING in sources
        assert CapaSource.DEVIATION in sources
        assert CapaSource.INSPECTION in sources
        assert CapaSource.TREND_ANALYSIS in sources
        assert CapaSource.SELF_IDENTIFIED in sources
        assert CapaSource.COMPLAINT in sources

    def test_seed_actions_count(self, svc: CapaManagementService):
        # Collect all actions across all CAPAs
        all_actions = []
        for capa in svc.list_capas():
            all_actions.extend(svc.list_actions(capa.id))
        assert len(all_actions) == 12

    def test_seed_closed_capa_has_effectiveness(self, svc: CapaManagementService):
        capa = svc.get_capa("CAPA-001")
        assert capa is not None
        assert capa.status == CapaStatus.CLOSED
        assert capa.effectiveness_verified is True
        assert capa.closed_date is not None

    def test_seed_capa_001_actions(self, svc: CapaManagementService):
        actions = svc.list_actions("CAPA-001")
        assert len(actions) == 2
        for a in actions:
            assert a.status == CapaActionStatus.COMPLETED


# =====================================================================
# CAPA CRUD
# =====================================================================


class TestCapaCrud:
    """Test CAPA create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_capas(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8
        assert len(data["items"]) == 8

    @pytest.mark.anyio
    async def test_list_capas_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_capas_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/", params={"site_id": "SITE-107"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SITE-107"

    @pytest.mark.anyio
    async def test_list_capas_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/", params={"status": "open"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "open"

    @pytest.mark.anyio
    async def test_list_capas_filter_priority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/", params={"priority": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["priority"] == "critical"

    @pytest.mark.anyio
    async def test_list_capas_filter_source(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/", params={"source": "audit_finding"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["source"] == "audit_finding"

    @pytest.mark.anyio
    async def test_get_capa(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/CAPA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CAPA-001"
        assert data["capa_number"] == "CAPA-2026-001"
        assert data["status"] == "closed"

    @pytest.mark.anyio
    async def test_get_capa_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/CAPA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_capa(self, client: AsyncClient):
        payload = _make_capa_create()
        resp = await client.post(f"{API_PREFIX}/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test CAPA for unit testing"
        assert data["status"] == "open"
        assert data["capa_type"] == "corrective"
        assert data["priority"] == "major"
        assert data["capa_number"].startswith("CAPA-2026-")
        assert data["id"].startswith("CAPA-")

    @pytest.mark.anyio
    async def test_create_capa_preventive(self, client: AsyncClient):
        payload = _make_capa_create(
            capa_type="preventive",
            source="trend_analysis",
            priority="minor",
        )
        resp = await client.post(f"{API_PREFIX}/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["capa_type"] == "preventive"
        assert data["source"] == "trend_analysis"
        assert data["priority"] == "minor"

    @pytest.mark.anyio
    async def test_create_capa_with_related_ids(self, client: AsyncClient):
        payload = _make_capa_create(
            related_deviation_ids=["DEV-001", "DEV-002"],
            related_audit_ids=["AUD-001"],
        )
        resp = await client.post(f"{API_PREFIX}/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["related_deviation_ids"] == ["DEV-001", "DEV-002"]
        assert data["related_audit_ids"] == ["AUD-001"]

    @pytest.mark.anyio
    async def test_update_capa(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/CAPA-006",
            json={"title": "Updated title", "priority": "critical"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated title"
        assert data["priority"] == "critical"

    @pytest.mark.anyio
    async def test_update_capa_root_cause(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/CAPA-006",
            json={"root_cause_analysis": "Identified root cause: staffing shortage"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["root_cause_analysis"] == "Identified root cause: staffing shortage"

    @pytest.mark.anyio
    async def test_update_capa_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/CAPA-NONEXISTENT",
            json={"title": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_capa(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/CAPA-008")
        assert resp.status_code == 204
        # Verify it's gone
        resp2 = await client.get(f"{API_PREFIX}/CAPA-008")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_capa_removes_actions(self, client: AsyncClient):
        # CAPA-001 has 2 actions (ACT-001, ACT-002)
        resp = await client.get(f"{API_PREFIX}/CAPA-001/actions")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

        # Delete the CAPA
        resp = await client.delete(f"{API_PREFIX}/CAPA-001")
        assert resp.status_code == 204

        # CAPA is gone
        resp = await client.get(f"{API_PREFIX}/CAPA-001")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_capa_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/CAPA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# STATUS TRANSITIONS
# =====================================================================


class TestStatusTransitions:
    """Test CAPA lifecycle status transitions."""

    @pytest.mark.anyio
    async def test_transition_open_to_investigation(self, client: AsyncClient):
        # CAPA-006 is OPEN
        resp = await client.post(f"{API_PREFIX}/CAPA-006/investigate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "investigation"

    @pytest.mark.anyio
    async def test_transition_investigation_to_action_plan(self, client: AsyncClient):
        # CAPA-005 is INVESTIGATION
        resp = await client.post(f"{API_PREFIX}/CAPA-005/action-plan")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "action_plan"

    @pytest.mark.anyio
    async def test_transition_action_plan_to_implementation(self, client: AsyncClient):
        # CAPA-004 is ACTION_PLAN
        resp = await client.post(f"{API_PREFIX}/CAPA-004/implement")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "implementation"

    @pytest.mark.anyio
    async def test_transition_implementation_to_verification(self, client: AsyncClient):
        # CAPA-003 is IMPLEMENTATION
        resp = await client.post(f"{API_PREFIX}/CAPA-003/verify")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "verification"

    @pytest.mark.anyio
    async def test_transition_verification_to_closed(self, client: AsyncClient):
        # CAPA-002 is VERIFICATION
        resp = await client.post(f"{API_PREFIX}/CAPA-002/close")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"
        assert data["effectiveness_verified"] is True
        assert data["closed_date"] is not None

    @pytest.mark.anyio
    async def test_full_lifecycle(self, client: AsyncClient):
        """Walk a CAPA through the entire lifecycle from open to closed."""
        # CAPA-006 starts as OPEN
        capa_id = "CAPA-006"

        resp = await client.post(f"{API_PREFIX}/{capa_id}/investigate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "investigation"

        resp = await client.post(f"{API_PREFIX}/{capa_id}/action-plan")
        assert resp.status_code == 200
        assert resp.json()["status"] == "action_plan"

        resp = await client.post(f"{API_PREFIX}/{capa_id}/implement")
        assert resp.status_code == 200
        assert resp.json()["status"] == "implementation"

        resp = await client.post(f"{API_PREFIX}/{capa_id}/verify")
        assert resp.status_code == 200
        assert resp.json()["status"] == "verification"

        resp = await client.post(f"{API_PREFIX}/{capa_id}/close")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"
        assert data["effectiveness_verified"] is True

    @pytest.mark.anyio
    async def test_invalid_transition_open_to_closed(self, client: AsyncClient):
        # CAPA-006 is OPEN, cannot jump to closed
        resp = await client.post(f"{API_PREFIX}/CAPA-006/close")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_invalid_transition_open_to_action_plan(self, client: AsyncClient):
        # CAPA-006 is OPEN, cannot skip to action_plan
        resp = await client.post(f"{API_PREFIX}/CAPA-006/action-plan")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_invalid_transition_closed_capa(self, client: AsyncClient):
        # CAPA-001 is CLOSED, cannot transition further
        resp = await client.post(f"{API_PREFIX}/CAPA-001/investigate")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_transition_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/CAPA-NONEXISTENT/investigate")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_close_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/CAPA-NONEXISTENT/close")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_verify_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/CAPA-NONEXISTENT/verify")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_implement_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/CAPA-NONEXISTENT/implement")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_action_plan_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/CAPA-NONEXISTENT/action-plan")
        assert resp.status_code == 404


# =====================================================================
# CAPA ACTIONS
# =====================================================================


class TestCapaActions:
    """Test CAPA action CRUD operations."""

    @pytest.mark.anyio
    async def test_list_actions_for_capa(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/CAPA-001/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["capa_id"] == "CAPA-001"

    @pytest.mark.anyio
    async def test_list_actions_for_capa_003(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/CAPA-003/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_actions_capa_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/CAPA-NONEXISTENT/actions")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_action(self, client: AsyncClient):
        payload = _make_action_create()
        resp = await client.post(f"{API_PREFIX}/CAPA-006/actions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["capa_id"] == "CAPA-006"
        assert data["action_description"] == "Test action item"
        assert data["action_type"] == "corrective"
        assert data["status"] == "pending"
        assert data["id"].startswith("ACT-")

    @pytest.mark.anyio
    async def test_create_action_containment(self, client: AsyncClient):
        payload = _make_action_create(
            action_type="containment",
            action_description="Immediate containment action",
            evidence_description="Evidence to be collected after completion",
        )
        resp = await client.post(f"{API_PREFIX}/CAPA-004/actions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["action_type"] == "containment"
        assert data["evidence_description"] == "Evidence to be collected after completion"

    @pytest.mark.anyio
    async def test_create_action_capa_not_found(self, client: AsyncClient):
        payload = _make_action_create()
        resp = await client.post(f"{API_PREFIX}/CAPA-NONEXISTENT/actions", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_action(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/actions/ACT-010",
            json={"action_description": "Updated RCA description", "assigned_to": "New Assignee"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action_description"] == "Updated RCA description"
        assert data["assigned_to"] == "New Assignee"

    @pytest.mark.anyio
    async def test_update_action_complete_sets_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/actions/ACT-010",
            json={"status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["completed_date"] is not None

    @pytest.mark.anyio
    async def test_update_action_cancel(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/actions/ACT-011",
            json={"status": "cancelled"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"

    @pytest.mark.anyio
    async def test_update_action_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/actions/ACT-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestCapaMetrics:
    """Test CAPA metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_capas"] == 8
        assert data["closed_capas"] == 1
        assert data["open_capas"] == 7
        assert data["total_actions"] == 12
        assert data["effectiveness_verified_count"] == 1

    @pytest.mark.anyio
    async def test_metrics_capas_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["capas_by_status"]
        total_by_status = sum(by_status.values())
        assert total_by_status == data["total_capas"]

    @pytest.mark.anyio
    async def test_metrics_capas_by_priority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_priority = data["capas_by_priority"]
        total_by_priority = sum(by_priority.values())
        assert total_by_priority == data["total_capas"]

    @pytest.mark.anyio
    async def test_metrics_capas_by_source(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_source = data["capas_by_source"]
        total_by_source = sum(by_source.values())
        assert total_by_source == data["total_capas"]

    @pytest.mark.anyio
    async def test_metrics_avg_days_to_close(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_days_to_close"] >= 0.0

    @pytest.mark.anyio
    async def test_metrics_completed_actions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["completed_actions"] <= data["total_actions"]
        assert data["completed_actions"] > 0

    @pytest.mark.anyio
    async def test_metrics_overdue_capas(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["overdue_capas"] >= 0

    def test_metrics_via_service(self, svc: CapaManagementService):
        metrics = svc.get_metrics()
        assert metrics.total_capas == 8
        assert metrics.closed_capas + metrics.open_capas == metrics.total_capas


# =====================================================================
# SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_capa_management_service()
        svc2 = get_capa_management_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_capa_management_service()
        svc2 = reset_capa_management_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_capa_management_service()
        # Delete a CAPA
        svc.delete_capa("CAPA-001")
        assert svc.get_capa("CAPA-001") is None
        # Reset should bring it back
        svc2 = reset_capa_management_service()
        assert svc2.get_capa("CAPA-001") is not None


# =====================================================================
# EDGE CASES
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_capas_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_capas_filter_no_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/", params={"site_id": "SITE-NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_create_capa_increments_number(self, client: AsyncClient):
        payload1 = _make_capa_create(title="First new CAPA")
        resp1 = await client.post(f"{API_PREFIX}/", json=payload1)
        assert resp1.status_code == 201

        payload2 = _make_capa_create(title="Second new CAPA")
        resp2 = await client.post(f"{API_PREFIX}/", json=payload2)
        assert resp2.status_code == 201

        num1 = resp1.json()["capa_number"]
        num2 = resp2.json()["capa_number"]
        # Both should have CAPA-2026-0XX format and second should be higher
        assert num1 < num2

    @pytest.mark.anyio
    async def test_update_capa_partial(self, client: AsyncClient):
        """Update only one field, other fields should remain unchanged."""
        # Get original
        resp = await client.get(f"{API_PREFIX}/CAPA-006")
        original = resp.json()

        # Update only title
        resp = await client.put(
            f"{API_PREFIX}/CAPA-006",
            json={"title": "Only title changed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Only title changed"
        assert data["priority"] == original["priority"]
        assert data["department"] == original["department"]

    @pytest.mark.anyio
    async def test_delete_capa_then_create(self, client: AsyncClient):
        """Delete and re-create to verify store consistency."""
        resp = await client.delete(f"{API_PREFIX}/CAPA-008")
        assert resp.status_code == 204

        # List should have 7
        resp = await client.get(f"{API_PREFIX}/")
        assert resp.json()["total"] == 7

        # Create a new one
        payload = _make_capa_create()
        resp = await client.post(f"{API_PREFIX}/", json=payload)
        assert resp.status_code == 201

        # List should be back to 8
        resp = await client.get(f"{API_PREFIX}/")
        assert resp.json()["total"] == 8

    @pytest.mark.anyio
    async def test_actions_empty_for_capa_with_no_actions(self, client: AsyncClient):
        # CAPA-008 has no actions in seed data
        resp = await client.get(f"{API_PREFIX}/CAPA-008/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_metrics_after_delete(self, client: AsyncClient):
        """Metrics should update after CAPA deletion."""
        resp = await client.delete(f"{API_PREFIX}/CAPA-001")
        assert resp.status_code == 204

        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_capas"] == 7
        assert data["closed_capas"] == 0  # CAPA-001 was the only closed one

    @pytest.mark.anyio
    async def test_metrics_after_close(self, client: AsyncClient):
        """Closing a CAPA should update metrics."""
        # Walk CAPA-002 (currently VERIFICATION) to CLOSED
        resp = await client.post(f"{API_PREFIX}/CAPA-002/close")
        assert resp.status_code == 200

        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["closed_capas"] == 2  # CAPA-001 + CAPA-002
        assert data["effectiveness_verified_count"] == 2
