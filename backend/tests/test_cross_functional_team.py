"""Tests for Cross-Functional Team Management (CFT-MGT).

Covers:
- Seed data verification (team formations, role assignments, meeting cadence records,
  deliverable trackers, performance reviews)
- Team formation CRUD (create, read, update, delete, list, filter by trial/type/status)
- Role assignment CRUD (create, read, update, delete, list, filter by trial/team/role)
- Meeting cadence record CRUD (create, read, update, delete, list, filter by trial/team/cadence)
- Deliverable tracker CRUD (create, read, update, delete, list, filter by trial/team/status)
- Performance review CRUD (create, read, update, delete, list, filter by trial/team)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.cross_functional_team import (
    DeliverableStatus,
    FunctionalRole,
    MeetingCadence,
    TeamStatus,
    TeamType,
)
from app.services.cross_functional_team_service import (
    CrossFunctionalTeamService,
    get_cross_functional_team_service,
    reset_cross_functional_team_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/cross-functional-team"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_cross_functional_team_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> CrossFunctionalTeamService:
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


def _make_team_formation_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "team_name": "Test Team",
        "team_type": "core_team",
        "sponsor_name": "Test Sponsor",
        "created_by": "Test User",
        "max_members": 10,
    }
    defaults.update(overrides)
    return defaults


def _make_role_assignment_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "team_id": "TF-001",
        "member_name": "Test Member",
        "functional_role": "clinical_lead",
        "department": "Test Department",
        "assigned_by": "Test Assigner",
        "time_commitment_pct": 50.0,
    }
    defaults.update(overrides)
    return defaults


def _make_meeting_cadence_record_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "team_id": "TF-001",
        "cadence": "weekly",
        "managed_by": "Test Manager",
        "meeting_day": "Monday",
        "duration_minutes": 60,
    }
    defaults.update(overrides)
    return defaults


def _make_deliverable_tracker_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "team_id": "TF-001",
        "deliverable_name": "Test Deliverable",
        "description": "A test deliverable for unit testing",
        "owner": "Test Owner",
        "due_date": (now + timedelta(days=30)).isoformat(),
        "created_by": "Test Creator",
        "priority": "medium",
    }
    defaults.update(overrides)
    return defaults


def _make_performance_review_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "team_id": "TF-001",
        "review_period": "Q1 2026",
        "reviewed_by": "Test Reviewer",
        "overall_rating": 4.0,
        "collaboration_score": 4.0,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    # -- Team Formations --

    def test_seed_team_formations_count(self, svc: CrossFunctionalTeamService):
        items = svc.list_team_formations()
        assert len(items) == 12

    def test_seed_team_formation_ids(self, svc: CrossFunctionalTeamService):
        items = svc.list_team_formations()
        ids = {t.id for t in items}
        for i in range(1, 13):
            assert f"TF-{i:03d}" in ids

    def test_seed_team_formation_types(self, svc: CrossFunctionalTeamService):
        items = svc.list_team_formations()
        types = {t.team_type for t in items}
        assert TeamType.CORE_TEAM in types
        assert TeamType.GOVERNANCE in types
        assert TeamType.SUB_TEAM in types
        assert TeamType.ADVISORY in types
        assert TeamType.TASK_FORCE in types
        assert TeamType.EXTENDED_TEAM in types

    def test_seed_team_formation_statuses(self, svc: CrossFunctionalTeamService):
        items = svc.list_team_formations()
        statuses = {t.status for t in items}
        assert TeamStatus.ACTIVE in statuses
        assert TeamStatus.FORMING in statuses
        assert TeamStatus.DISBANDED in statuses
        assert TeamStatus.ON_HOLD in statuses

    # -- Role Assignments --

    def test_seed_role_assignments_count(self, svc: CrossFunctionalTeamService):
        items = svc.list_role_assignments()
        assert len(items) == 12

    def test_seed_role_assignment_ids(self, svc: CrossFunctionalTeamService):
        items = svc.list_role_assignments()
        ids = {r.id for r in items}
        for i in range(1, 13):
            assert f"RA-{i:03d}" in ids

    def test_seed_role_assignment_roles(self, svc: CrossFunctionalTeamService):
        items = svc.list_role_assignments()
        roles = {r.functional_role for r in items}
        assert FunctionalRole.CLINICAL_LEAD in roles
        assert FunctionalRole.SAFETY_OFFICER in roles
        assert FunctionalRole.BIOSTATISTICIAN in roles
        assert FunctionalRole.MEDICAL_MONITOR in roles
        assert FunctionalRole.REGULATORY_LEAD in roles
        assert FunctionalRole.DATA_MANAGER in roles

    # -- Meeting Cadence Records --

    def test_seed_meeting_cadence_records_count(self, svc: CrossFunctionalTeamService):
        items = svc.list_meeting_cadence_records()
        assert len(items) == 12

    def test_seed_meeting_cadence_record_ids(self, svc: CrossFunctionalTeamService):
        items = svc.list_meeting_cadence_records()
        ids = {m.id for m in items}
        for i in range(1, 13):
            assert f"MC-{i:03d}" in ids

    def test_seed_meeting_cadences(self, svc: CrossFunctionalTeamService):
        items = svc.list_meeting_cadence_records()
        cadences = {m.cadence for m in items}
        assert MeetingCadence.WEEKLY in cadences
        assert MeetingCadence.BIWEEKLY in cadences
        assert MeetingCadence.MONTHLY in cadences
        assert MeetingCadence.QUARTERLY in cadences
        assert MeetingCadence.AD_HOC in cadences

    # -- Deliverable Trackers --

    def test_seed_deliverable_trackers_count(self, svc: CrossFunctionalTeamService):
        items = svc.list_deliverable_trackers()
        assert len(items) == 12

    def test_seed_deliverable_tracker_ids(self, svc: CrossFunctionalTeamService):
        items = svc.list_deliverable_trackers()
        ids = {d.id for d in items}
        for i in range(1, 13):
            assert f"DT-{i:03d}" in ids

    def test_seed_deliverable_statuses(self, svc: CrossFunctionalTeamService):
        items = svc.list_deliverable_trackers()
        statuses = {d.status for d in items}
        assert DeliverableStatus.APPROVED in statuses
        assert DeliverableStatus.IN_PROGRESS in statuses
        assert DeliverableStatus.UNDER_REVIEW in statuses
        assert DeliverableStatus.OVERDUE in statuses
        assert DeliverableStatus.NOT_STARTED in statuses
        assert DeliverableStatus.CANCELLED in statuses

    # -- Performance Reviews --

    def test_seed_performance_reviews_count(self, svc: CrossFunctionalTeamService):
        items = svc.list_performance_reviews()
        assert len(items) == 12

    def test_seed_performance_review_ids(self, svc: CrossFunctionalTeamService):
        items = svc.list_performance_reviews()
        ids = {r.id for r in items}
        for i in range(1, 13):
            assert f"PR-{i:03d}" in ids

    def test_seed_performance_review_ratings(self, svc: CrossFunctionalTeamService):
        items = svc.list_performance_reviews()
        ratings = [r.overall_rating for r in items]
        assert all(1.0 <= r <= 5.0 for r in ratings)

    def test_seed_performance_review_trials(self, svc: CrossFunctionalTeamService):
        items = svc.list_performance_reviews()
        trial_ids = {r.trial_id for r in items}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids


# =====================================================================
# TEAM FORMATION CRUD
# =====================================================================


class TestTeamFormationCRUD:
    """Test team formation create, read, update, delete operations."""

    # -- List --

    @pytest.mark.anyio
    async def test_list_team_formations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/team-formations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_team_formations_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/team-formations", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_team_formations_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/team-formations", params={"team_type": "core_team"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["team_type"] == "core_team"

    @pytest.mark.anyio
    async def test_list_team_formations_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/team-formations", params={"status": "active"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "active"

    @pytest.mark.anyio
    async def test_list_team_formations_filter_multiple(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/team-formations",
            params={"trial_id": EYLEA_TRIAL, "status": "active"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["status"] == "active"

    @pytest.mark.anyio
    async def test_list_team_formations_filter_disbanded(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/team-formations", params={"status": "disbanded"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == "TF-011"

    @pytest.mark.anyio
    async def test_list_team_formations_filter_governance(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/team-formations", params={"team_type": "governance"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == "TF-002"

    @pytest.mark.anyio
    async def test_list_team_formations_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/team-formations", params={"status": "archived"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    # -- Get --

    @pytest.mark.anyio
    async def test_get_team_formation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/team-formations/TF-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TF-001"
        assert data["team_name"] == "EYLEA Phase III Core Team"
        assert data["team_type"] == "core_team"
        assert data["status"] == "active"

    @pytest.mark.anyio
    async def test_get_team_formation_tf010(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/team-formations/TF-010")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TF-010"
        assert data["status"] == "forming"
        assert data["charter_approved"] is False

    @pytest.mark.anyio
    async def test_get_team_formation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/team-formations/TF-NONEXISTENT")
        assert resp.status_code == 404

    # -- Create --

    @pytest.mark.anyio
    async def test_create_team_formation(self, client: AsyncClient):
        payload = _make_team_formation_create()
        resp = await client.post(f"{API_PREFIX}/team-formations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["team_name"] == "Test Team"
        assert data["team_type"] == "core_team"
        assert data["status"] == "forming"
        assert data["charter_approved"] is False
        assert data["current_members"] == 0
        assert data["id"].startswith("TF-")

    @pytest.mark.anyio
    async def test_create_team_formation_advisory(self, client: AsyncClient):
        payload = _make_team_formation_create(
            team_name="Advisory Board",
            team_type="advisory",
            trial_id=DUPIXENT_TRIAL,
        )
        resp = await client.post(f"{API_PREFIX}/team-formations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["team_type"] == "advisory"
        assert data["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_create_team_formation_appears_in_list(self, client: AsyncClient):
        payload = _make_team_formation_create(team_name="Unique New Team")
        resp = await client.post(f"{API_PREFIX}/team-formations", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        resp2 = await client.get(f"{API_PREFIX}/team-formations/{new_id}")
        assert resp2.status_code == 200
        assert resp2.json()["team_name"] == "Unique New Team"

    # -- Update --

    @pytest.mark.anyio
    async def test_update_team_formation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/team-formations/TF-001",
            json={"notes": "Updated notes for TF-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated notes for TF-001"
        assert data["id"] == "TF-001"

    @pytest.mark.anyio
    async def test_update_team_formation_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/team-formations/TF-010",
            json={"status": "active"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"

    @pytest.mark.anyio
    async def test_update_team_formation_charter(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/team-formations/TF-010",
            json={"charter_approved": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["charter_approved"] is True

    @pytest.mark.anyio
    async def test_update_team_formation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/team-formations/TF-NONEXISTENT",
            json={"notes": "Should not work"},
        )
        assert resp.status_code == 404

    # -- Delete --

    @pytest.mark.anyio
    async def test_delete_team_formation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/team-formations/TF-012")
        assert resp.status_code == 204
        # Verify it's gone
        resp2 = await client.get(f"{API_PREFIX}/team-formations/TF-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_team_formation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/team-formations/TF-NONEXISTENT")
        assert resp.status_code == 404

    # -- Service-level tests --

    def test_service_list_team_formations_trial_filter(self, svc: CrossFunctionalTeamService):
        items = svc.list_team_formations(trial_id=DUPIXENT_TRIAL)
        assert len(items) > 0
        for t in items:
            assert t.trial_id == DUPIXENT_TRIAL

    def test_service_list_team_formations_type_filter(self, svc: CrossFunctionalTeamService):
        items = svc.list_team_formations(team_type=TeamType.CORE_TEAM)
        assert len(items) == 3
        for t in items:
            assert t.team_type == TeamType.CORE_TEAM

    def test_service_list_team_formations_status_filter(self, svc: CrossFunctionalTeamService):
        items = svc.list_team_formations(status=TeamStatus.ACTIVE)
        assert len(items) == 9
        for t in items:
            assert t.status == TeamStatus.ACTIVE

    def test_service_get_team_formation(self, svc: CrossFunctionalTeamService):
        team = svc.get_team_formation("TF-001")
        assert team is not None
        assert team.id == "TF-001"
        assert team.team_name == "EYLEA Phase III Core Team"

    def test_service_get_team_formation_none(self, svc: CrossFunctionalTeamService):
        team = svc.get_team_formation("TF-NONEXISTENT")
        assert team is None

    def test_service_delete_team_formation(self, svc: CrossFunctionalTeamService):
        assert svc.delete_team_formation("TF-001") is True
        assert svc.get_team_formation("TF-001") is None

    def test_service_delete_team_formation_nonexistent(self, svc: CrossFunctionalTeamService):
        assert svc.delete_team_formation("TF-NONEXISTENT") is False


# =====================================================================
# ROLE ASSIGNMENT CRUD
# =====================================================================


class TestRoleAssignmentCRUD:
    """Test role assignment create, read, update, delete operations."""

    # -- List --

    @pytest.mark.anyio
    async def test_list_role_assignments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/role-assignments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_role_assignments_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/role-assignments", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_role_assignments_filter_team(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/role-assignments", params={"team_id": "TF-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["team_id"] == "TF-001"

    @pytest.mark.anyio
    async def test_list_role_assignments_filter_role(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/role-assignments", params={"functional_role": "clinical_lead"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["functional_role"] == "clinical_lead"

    @pytest.mark.anyio
    async def test_list_role_assignments_filter_multiple(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/role-assignments",
            params={"trial_id": LIBTAYO_TRIAL, "team_id": "TF-007"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL
            assert item["team_id"] == "TF-007"

    @pytest.mark.anyio
    async def test_list_role_assignments_filter_biostatistician(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/role-assignments", params={"functional_role": "biostatistician"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    @pytest.mark.anyio
    async def test_list_role_assignments_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/role-assignments", params={"team_id": "TF-NONEXISTENT"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # -- Get --

    @pytest.mark.anyio
    async def test_get_role_assignment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/role-assignments/RA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RA-001"
        assert data["member_name"] == "Dr. Sarah Chen"
        assert data["functional_role"] == "clinical_lead"

    @pytest.mark.anyio
    async def test_get_role_assignment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/role-assignments/RA-NONEXISTENT")
        assert resp.status_code == 404

    # -- Create --

    @pytest.mark.anyio
    async def test_create_role_assignment(self, client: AsyncClient):
        payload = _make_role_assignment_create()
        resp = await client.post(f"{API_PREFIX}/role-assignments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["member_name"] == "Test Member"
        assert data["functional_role"] == "clinical_lead"
        assert data["is_primary"] is True
        assert data["id"].startswith("RA-")

    @pytest.mark.anyio
    async def test_create_role_assignment_safety_officer(self, client: AsyncClient):
        payload = _make_role_assignment_create(
            member_name="Dr. New Safety",
            functional_role="safety_officer",
            trial_id=LIBTAYO_TRIAL,
        )
        resp = await client.post(f"{API_PREFIX}/role-assignments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["functional_role"] == "safety_officer"

    @pytest.mark.anyio
    async def test_create_role_assignment_appears_in_list(self, client: AsyncClient):
        payload = _make_role_assignment_create(member_name="Unique Member Name")
        resp = await client.post(f"{API_PREFIX}/role-assignments", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        resp2 = await client.get(f"{API_PREFIX}/role-assignments/{new_id}")
        assert resp2.status_code == 200
        assert resp2.json()["member_name"] == "Unique Member Name"

    # -- Update --

    @pytest.mark.anyio
    async def test_update_role_assignment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/role-assignments/RA-001",
            json={"notes": "Updated notes for RA-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated notes for RA-001"

    @pytest.mark.anyio
    async def test_update_role_assignment_time_commitment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/role-assignments/RA-001",
            json={"time_commitment_pct": 100.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["time_commitment_pct"] == 100.0

    @pytest.mark.anyio
    async def test_update_role_assignment_backup(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/role-assignments/RA-003",
            json={"backup_member": "Dr. New Backup"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["backup_member"] == "Dr. New Backup"

    @pytest.mark.anyio
    async def test_update_role_assignment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/role-assignments/RA-NONEXISTENT",
            json={"notes": "Should not work"},
        )
        assert resp.status_code == 404

    # -- Delete --

    @pytest.mark.anyio
    async def test_delete_role_assignment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/role-assignments/RA-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/role-assignments/RA-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_role_assignment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/role-assignments/RA-NONEXISTENT")
        assert resp.status_code == 404

    # -- Service-level tests --

    def test_service_list_role_assignments_trial_filter(self, svc: CrossFunctionalTeamService):
        items = svc.list_role_assignments(trial_id=LIBTAYO_TRIAL)
        assert len(items) > 0
        for r in items:
            assert r.trial_id == LIBTAYO_TRIAL

    def test_service_list_role_assignments_team_filter(self, svc: CrossFunctionalTeamService):
        items = svc.list_role_assignments(team_id="TF-004")
        assert len(items) > 0
        for r in items:
            assert r.team_id == "TF-004"

    def test_service_list_role_assignments_role_filter(self, svc: CrossFunctionalTeamService):
        items = svc.list_role_assignments(functional_role=FunctionalRole.CLINICAL_LEAD)
        assert len(items) == 3
        for r in items:
            assert r.functional_role == FunctionalRole.CLINICAL_LEAD

    def test_service_get_role_assignment(self, svc: CrossFunctionalTeamService):
        ra = svc.get_role_assignment("RA-001")
        assert ra is not None
        assert ra.member_name == "Dr. Sarah Chen"

    def test_service_get_role_assignment_none(self, svc: CrossFunctionalTeamService):
        ra = svc.get_role_assignment("RA-NONEXISTENT")
        assert ra is None

    def test_service_delete_role_assignment(self, svc: CrossFunctionalTeamService):
        assert svc.delete_role_assignment("RA-001") is True
        assert svc.get_role_assignment("RA-001") is None

    def test_service_delete_role_assignment_nonexistent(self, svc: CrossFunctionalTeamService):
        assert svc.delete_role_assignment("RA-NONEXISTENT") is False


# =====================================================================
# MEETING CADENCE RECORD CRUD
# =====================================================================


class TestMeetingCadenceRecordCRUD:
    """Test meeting cadence record create, read, update, delete operations."""

    # -- List --

    @pytest.mark.anyio
    async def test_list_meeting_cadence_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meeting-cadence-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_meeting_cadence_records_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/meeting-cadence-records", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_meeting_cadence_records_filter_team(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/meeting-cadence-records", params={"team_id": "TF-004"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["team_id"] == "TF-004"

    @pytest.mark.anyio
    async def test_list_meeting_cadence_records_filter_cadence(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/meeting-cadence-records", params={"cadence": "weekly"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["cadence"] == "weekly"

    @pytest.mark.anyio
    async def test_list_meeting_cadence_records_filter_biweekly(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/meeting-cadence-records", params={"cadence": "biweekly"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_meeting_cadence_records_filter_quarterly(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/meeting-cadence-records", params={"cadence": "quarterly"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    @pytest.mark.anyio
    async def test_list_meeting_cadence_records_filter_multiple(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/meeting-cadence-records",
            params={"trial_id": LIBTAYO_TRIAL, "cadence": "weekly"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL
            assert item["cadence"] == "weekly"

    @pytest.mark.anyio
    async def test_list_meeting_cadence_records_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/meeting-cadence-records", params={"team_id": "TF-NONEXISTENT"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # -- Get --

    @pytest.mark.anyio
    async def test_get_meeting_cadence_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meeting-cadence-records/MC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MC-001"
        assert data["cadence"] == "weekly"
        assert data["meeting_day"] == "Tuesday"

    @pytest.mark.anyio
    async def test_get_meeting_cadence_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/meeting-cadence-records/MC-NONEXISTENT")
        assert resp.status_code == 404

    # -- Create --

    @pytest.mark.anyio
    async def test_create_meeting_cadence_record(self, client: AsyncClient):
        payload = _make_meeting_cadence_record_create()
        resp = await client.post(f"{API_PREFIX}/meeting-cadence-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["cadence"] == "weekly"
        assert data["meeting_day"] == "Monday"
        assert data["total_meetings_held"] == 0
        assert data["id"].startswith("MC-")

    @pytest.mark.anyio
    async def test_create_meeting_cadence_record_monthly(self, client: AsyncClient):
        payload = _make_meeting_cadence_record_create(
            cadence="monthly",
            meeting_day="Thursday",
            trial_id=DUPIXENT_TRIAL,
        )
        resp = await client.post(f"{API_PREFIX}/meeting-cadence-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["cadence"] == "monthly"

    @pytest.mark.anyio
    async def test_create_meeting_cadence_record_appears_in_list(self, client: AsyncClient):
        payload = _make_meeting_cadence_record_create()
        resp = await client.post(f"{API_PREFIX}/meeting-cadence-records", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        resp2 = await client.get(f"{API_PREFIX}/meeting-cadence-records/{new_id}")
        assert resp2.status_code == 200

    # -- Update --

    @pytest.mark.anyio
    async def test_update_meeting_cadence_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/meeting-cadence-records/MC-001",
            json={"notes": "Updated meeting notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated meeting notes"

    @pytest.mark.anyio
    async def test_update_meeting_cadence_record_cadence(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/meeting-cadence-records/MC-010",
            json={"cadence": "monthly"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["cadence"] == "monthly"

    @pytest.mark.anyio
    async def test_update_meeting_cadence_record_attendance(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/meeting-cadence-records/MC-001",
            json={"total_meetings_held": 50, "average_attendance": 11},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_meetings_held"] == 50
        assert data["average_attendance"] == 11

    @pytest.mark.anyio
    async def test_update_meeting_cadence_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/meeting-cadence-records/MC-NONEXISTENT",
            json={"notes": "Should not work"},
        )
        assert resp.status_code == 404

    # -- Delete --

    @pytest.mark.anyio
    async def test_delete_meeting_cadence_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/meeting-cadence-records/MC-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/meeting-cadence-records/MC-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_meeting_cadence_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/meeting-cadence-records/MC-NONEXISTENT")
        assert resp.status_code == 404

    # -- Service-level tests --

    def test_service_list_meeting_cadence_records_trial_filter(
        self, svc: CrossFunctionalTeamService
    ):
        items = svc.list_meeting_cadence_records(trial_id=DUPIXENT_TRIAL)
        assert len(items) > 0
        for m in items:
            assert m.trial_id == DUPIXENT_TRIAL

    def test_service_list_meeting_cadence_records_team_filter(
        self, svc: CrossFunctionalTeamService
    ):
        items = svc.list_meeting_cadence_records(team_id="TF-007")
        assert len(items) == 1
        assert items[0].id == "MC-007"

    def test_service_list_meeting_cadence_records_cadence_filter(
        self, svc: CrossFunctionalTeamService
    ):
        items = svc.list_meeting_cadence_records(cadence=MeetingCadence.WEEKLY)
        assert len(items) > 0
        for m in items:
            assert m.cadence == MeetingCadence.WEEKLY

    def test_service_get_meeting_cadence_record(self, svc: CrossFunctionalTeamService):
        record = svc.get_meeting_cadence_record("MC-001")
        assert record is not None
        assert record.cadence == MeetingCadence.WEEKLY

    def test_service_get_meeting_cadence_record_none(self, svc: CrossFunctionalTeamService):
        record = svc.get_meeting_cadence_record("MC-NONEXISTENT")
        assert record is None

    def test_service_delete_meeting_cadence_record(self, svc: CrossFunctionalTeamService):
        assert svc.delete_meeting_cadence_record("MC-001") is True
        assert svc.get_meeting_cadence_record("MC-001") is None

    def test_service_delete_meeting_cadence_record_nonexistent(
        self, svc: CrossFunctionalTeamService
    ):
        assert svc.delete_meeting_cadence_record("MC-NONEXISTENT") is False


# =====================================================================
# DELIVERABLE TRACKER CRUD
# =====================================================================


class TestDeliverableTrackerCRUD:
    """Test deliverable tracker create, read, update, delete operations."""

    # -- List --

    @pytest.mark.anyio
    async def test_list_deliverable_trackers(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deliverable-trackers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_deliverable_trackers_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/deliverable-trackers", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_deliverable_trackers_filter_team(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/deliverable-trackers", params={"team_id": "TF-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["team_id"] == "TF-001"

    @pytest.mark.anyio
    async def test_list_deliverable_trackers_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/deliverable-trackers", params={"status": "in_progress"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_list_deliverable_trackers_filter_overdue(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/deliverable-trackers", params={"status": "overdue"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    @pytest.mark.anyio
    async def test_list_deliverable_trackers_filter_approved(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/deliverable-trackers", params={"status": "approved"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["status"] == "approved"

    @pytest.mark.anyio
    async def test_list_deliverable_trackers_filter_multiple(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/deliverable-trackers",
            params={"trial_id": LIBTAYO_TRIAL, "status": "in_progress"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL
            assert item["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_list_deliverable_trackers_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/deliverable-trackers", params={"team_id": "TF-NONEXISTENT"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # -- Get --

    @pytest.mark.anyio
    async def test_get_deliverable_tracker(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deliverable-trackers/DT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DT-001"
        assert data["deliverable_name"] == "EYLEA Phase III Protocol Final"
        assert data["status"] == "approved"
        assert data["pct_complete"] == 100.0

    @pytest.mark.anyio
    async def test_get_deliverable_tracker_overdue(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deliverable-trackers/DT-006")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "overdue"

    @pytest.mark.anyio
    async def test_get_deliverable_tracker_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/deliverable-trackers/DT-NONEXISTENT")
        assert resp.status_code == 404

    # -- Create --

    @pytest.mark.anyio
    async def test_create_deliverable_tracker(self, client: AsyncClient):
        payload = _make_deliverable_tracker_create()
        resp = await client.post(f"{API_PREFIX}/deliverable-trackers", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["deliverable_name"] == "Test Deliverable"
        assert data["status"] == "not_started"
        assert data["pct_complete"] == 0.0
        assert data["id"].startswith("DT-")

    @pytest.mark.anyio
    async def test_create_deliverable_tracker_high_priority(self, client: AsyncClient):
        payload = _make_deliverable_tracker_create(
            deliverable_name="Urgent Deliverable",
            priority="high",
            trial_id=LIBTAYO_TRIAL,
        )
        resp = await client.post(f"{API_PREFIX}/deliverable-trackers", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["priority"] == "high"

    @pytest.mark.anyio
    async def test_create_deliverable_tracker_appears_in_list(self, client: AsyncClient):
        payload = _make_deliverable_tracker_create(deliverable_name="Unique Deliverable")
        resp = await client.post(f"{API_PREFIX}/deliverable-trackers", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        resp2 = await client.get(f"{API_PREFIX}/deliverable-trackers/{new_id}")
        assert resp2.status_code == 200
        assert resp2.json()["deliverable_name"] == "Unique Deliverable"

    # -- Update --

    @pytest.mark.anyio
    async def test_update_deliverable_tracker(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/deliverable-trackers/DT-003",
            json={"notes": "Updated deliverable notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated deliverable notes"

    @pytest.mark.anyio
    async def test_update_deliverable_tracker_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/deliverable-trackers/DT-010",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_update_deliverable_tracker_pct_complete(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/deliverable-trackers/DT-005",
            json={"pct_complete": 75.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["pct_complete"] == 75.0

    @pytest.mark.anyio
    async def test_update_deliverable_tracker_reviewer(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/deliverable-trackers/DT-009",
            json={"reviewer": "Dr. New Reviewer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reviewer"] == "Dr. New Reviewer"

    @pytest.mark.anyio
    async def test_update_deliverable_tracker_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/deliverable-trackers/DT-NONEXISTENT",
            json={"notes": "Should not work"},
        )
        assert resp.status_code == 404

    # -- Delete --

    @pytest.mark.anyio
    async def test_delete_deliverable_tracker(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/deliverable-trackers/DT-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/deliverable-trackers/DT-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_deliverable_tracker_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/deliverable-trackers/DT-NONEXISTENT")
        assert resp.status_code == 404

    # -- Service-level tests --

    def test_service_list_deliverable_trackers_trial_filter(
        self, svc: CrossFunctionalTeamService
    ):
        items = svc.list_deliverable_trackers(trial_id=DUPIXENT_TRIAL)
        assert len(items) > 0
        for d in items:
            assert d.trial_id == DUPIXENT_TRIAL

    def test_service_list_deliverable_trackers_team_filter(
        self, svc: CrossFunctionalTeamService
    ):
        items = svc.list_deliverable_trackers(team_id="TF-001")
        assert len(items) > 0
        for d in items:
            assert d.team_id == "TF-001"

    def test_service_list_deliverable_trackers_status_filter(
        self, svc: CrossFunctionalTeamService
    ):
        items = svc.list_deliverable_trackers(status=DeliverableStatus.IN_PROGRESS)
        assert len(items) > 0
        for d in items:
            assert d.status == DeliverableStatus.IN_PROGRESS

    def test_service_list_deliverable_trackers_overdue(
        self, svc: CrossFunctionalTeamService
    ):
        items = svc.list_deliverable_trackers(status=DeliverableStatus.OVERDUE)
        assert len(items) == 2

    def test_service_get_deliverable_tracker(self, svc: CrossFunctionalTeamService):
        dt = svc.get_deliverable_tracker("DT-001")
        assert dt is not None
        assert dt.deliverable_name == "EYLEA Phase III Protocol Final"

    def test_service_get_deliverable_tracker_none(self, svc: CrossFunctionalTeamService):
        dt = svc.get_deliverable_tracker("DT-NONEXISTENT")
        assert dt is None

    def test_service_delete_deliverable_tracker(self, svc: CrossFunctionalTeamService):
        assert svc.delete_deliverable_tracker("DT-001") is True
        assert svc.get_deliverable_tracker("DT-001") is None

    def test_service_delete_deliverable_tracker_nonexistent(
        self, svc: CrossFunctionalTeamService
    ):
        assert svc.delete_deliverable_tracker("DT-NONEXISTENT") is False


# =====================================================================
# PERFORMANCE REVIEW CRUD
# =====================================================================


class TestPerformanceReviewCRUD:
    """Test performance review create, read, update, delete operations."""

    # -- List --

    @pytest.mark.anyio
    async def test_list_performance_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/performance-reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_performance_reviews_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/performance-reviews", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_performance_reviews_filter_team(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/performance-reviews", params={"team_id": "TF-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["team_id"] == "TF-001"

    @pytest.mark.anyio
    async def test_list_performance_reviews_filter_multiple(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/performance-reviews",
            params={"trial_id": LIBTAYO_TRIAL, "team_id": "TF-007"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL
            assert item["team_id"] == "TF-007"

    @pytest.mark.anyio
    async def test_list_performance_reviews_filter_eylea_team001(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/performance-reviews",
            params={"trial_id": EYLEA_TRIAL, "team_id": "TF-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    @pytest.mark.anyio
    async def test_list_performance_reviews_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/performance-reviews", params={"team_id": "TF-NONEXISTENT"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    # -- Get --

    @pytest.mark.anyio
    async def test_get_performance_review(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/performance-reviews/PR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PR-001"
        assert data["review_period"] == "Q3 2025"
        assert data["overall_rating"] == 4.5

    @pytest.mark.anyio
    async def test_get_performance_review_top_rated(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/performance-reviews/PR-008")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_rating"] == 4.8

    @pytest.mark.anyio
    async def test_get_performance_review_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/performance-reviews/PR-NONEXISTENT")
        assert resp.status_code == 404

    # -- Create --

    @pytest.mark.anyio
    async def test_create_performance_review(self, client: AsyncClient):
        payload = _make_performance_review_create()
        resp = await client.post(f"{API_PREFIX}/performance-reviews", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["review_period"] == "Q1 2026"
        assert data["overall_rating"] == 4.0
        assert data["acknowledged"] is False
        assert data["id"].startswith("PR-")

    @pytest.mark.anyio
    async def test_create_performance_review_libtayo(self, client: AsyncClient):
        payload = _make_performance_review_create(
            trial_id=LIBTAYO_TRIAL,
            team_id="TF-007",
            review_period="Q1 2026",
            overall_rating=4.9,
            collaboration_score=5.0,
        )
        resp = await client.post(f"{API_PREFIX}/performance-reviews", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["overall_rating"] == 4.9
        assert data["collaboration_score"] == 5.0

    @pytest.mark.anyio
    async def test_create_performance_review_appears_in_list(self, client: AsyncClient):
        payload = _make_performance_review_create(review_period="Q2 2026")
        resp = await client.post(f"{API_PREFIX}/performance-reviews", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        resp2 = await client.get(f"{API_PREFIX}/performance-reviews/{new_id}")
        assert resp2.status_code == 200
        assert resp2.json()["review_period"] == "Q2 2026"

    # -- Update --

    @pytest.mark.anyio
    async def test_update_performance_review(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/performance-reviews/PR-001",
            json={"notes": "Updated review notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated review notes"

    @pytest.mark.anyio
    async def test_update_performance_review_acknowledged(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/performance-reviews/PR-002",
            json={"acknowledged": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["acknowledged"] is True

    @pytest.mark.anyio
    async def test_update_performance_review_rating(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/performance-reviews/PR-012",
            json={"overall_rating": 3.5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_rating"] == 3.5

    @pytest.mark.anyio
    async def test_update_performance_review_goals(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/performance-reviews/PR-004",
            json={"goals_met_pct": 85.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["goals_met_pct"] == 85.0

    @pytest.mark.anyio
    async def test_update_performance_review_delivery_score(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/performance-reviews/PR-006",
            json={"delivery_score": 3.5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["delivery_score"] == 3.5

    @pytest.mark.anyio
    async def test_update_performance_review_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/performance-reviews/PR-NONEXISTENT",
            json={"notes": "Should not work"},
        )
        assert resp.status_code == 404

    # -- Delete --

    @pytest.mark.anyio
    async def test_delete_performance_review(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/performance-reviews/PR-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/performance-reviews/PR-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_performance_review_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/performance-reviews/PR-NONEXISTENT")
        assert resp.status_code == 404

    # -- Service-level tests --

    def test_service_list_performance_reviews_trial_filter(
        self, svc: CrossFunctionalTeamService
    ):
        items = svc.list_performance_reviews(trial_id=LIBTAYO_TRIAL)
        assert len(items) > 0
        for r in items:
            assert r.trial_id == LIBTAYO_TRIAL

    def test_service_list_performance_reviews_team_filter(
        self, svc: CrossFunctionalTeamService
    ):
        items = svc.list_performance_reviews(team_id="TF-007")
        assert len(items) == 2
        for r in items:
            assert r.team_id == "TF-007"

    def test_service_list_performance_reviews_combined_filter(
        self, svc: CrossFunctionalTeamService
    ):
        items = svc.list_performance_reviews(trial_id=DUPIXENT_TRIAL, team_id="TF-004")
        assert len(items) == 2
        for r in items:
            assert r.trial_id == DUPIXENT_TRIAL
            assert r.team_id == "TF-004"

    def test_service_get_performance_review(self, svc: CrossFunctionalTeamService):
        review = svc.get_performance_review("PR-001")
        assert review is not None
        assert review.review_period == "Q3 2025"
        assert review.overall_rating == 4.5

    def test_service_get_performance_review_none(self, svc: CrossFunctionalTeamService):
        review = svc.get_performance_review("PR-NONEXISTENT")
        assert review is None

    def test_service_delete_performance_review(self, svc: CrossFunctionalTeamService):
        assert svc.delete_performance_review("PR-001") is True
        assert svc.get_performance_review("PR-001") is None

    def test_service_delete_performance_review_nonexistent(
        self, svc: CrossFunctionalTeamService
    ):
        assert svc.delete_performance_review("PR-NONEXISTENT") is False


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test cross-functional team metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_teams"] == 12
        assert data["total_role_assignments"] == 12
        assert data["total_meeting_records"] == 12
        assert data["total_deliverables"] == 12
        assert data["total_reviews"] == 12

    @pytest.mark.anyio
    async def test_get_metrics_active_teams(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["active_teams"] == 9

    @pytest.mark.anyio
    async def test_get_metrics_overdue_deliverables(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["overdue_deliverables"] == 2

    @pytest.mark.anyio
    async def test_get_metrics_avg_rating(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_overall_rating"] > 0
        assert data["avg_overall_rating"] <= 5.0

    @pytest.mark.anyio
    async def test_get_metrics_teams_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        teams_by_type = data["teams_by_type"]
        assert "core_team" in teams_by_type
        assert teams_by_type["core_team"] == 3

    @pytest.mark.anyio
    async def test_get_metrics_teams_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        teams_by_status = data["teams_by_status"]
        assert "active" in teams_by_status
        assert teams_by_status["active"] == 9

    @pytest.mark.anyio
    async def test_get_metrics_assignments_by_role(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assignments_by_role = data["assignments_by_role"]
        assert "clinical_lead" in assignments_by_role
        assert assignments_by_role["clinical_lead"] == 3

    @pytest.mark.anyio
    async def test_get_metrics_meetings_by_cadence(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        meetings_by_cadence = data["meetings_by_cadence"]
        assert "weekly" in meetings_by_cadence

    @pytest.mark.anyio
    async def test_get_metrics_deliverables_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        deliverables_by_status = data["deliverables_by_status"]
        assert "in_progress" in deliverables_by_status
        assert "overdue" in deliverables_by_status
        assert "approved" in deliverables_by_status

    def test_metrics_teams_by_type_sum(self, svc: CrossFunctionalTeamService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.teams_by_type.values())
        assert total_by_type == metrics.total_teams

    def test_metrics_teams_by_status_sum(self, svc: CrossFunctionalTeamService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.teams_by_status.values())
        assert total_by_status == metrics.total_teams

    def test_metrics_assignments_by_role_sum(self, svc: CrossFunctionalTeamService):
        metrics = svc.get_metrics()
        total_by_role = sum(metrics.assignments_by_role.values())
        assert total_by_role == metrics.total_role_assignments

    def test_metrics_meetings_by_cadence_sum(self, svc: CrossFunctionalTeamService):
        metrics = svc.get_metrics()
        total_by_cadence = sum(metrics.meetings_by_cadence.values())
        assert total_by_cadence == metrics.total_meeting_records

    def test_metrics_deliverables_by_status_sum(self, svc: CrossFunctionalTeamService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.deliverables_by_status.values())
        assert total_by_status == metrics.total_deliverables

    def test_metrics_avg_rating_calculation(self, svc: CrossFunctionalTeamService):
        metrics = svc.get_metrics()
        reviews = svc.list_performance_reviews()
        expected_avg = round(
            sum(r.overall_rating for r in reviews) / len(reviews), 2
        )
        assert metrics.avg_overall_rating == expected_avg

    def test_metrics_after_team_deletion(self, svc: CrossFunctionalTeamService):
        svc.delete_team_formation("TF-001")
        metrics = svc.get_metrics()
        assert metrics.total_teams == 11

    def test_metrics_after_deliverable_deletion(self, svc: CrossFunctionalTeamService):
        svc.delete_deliverable_tracker("DT-006")
        metrics = svc.get_metrics()
        assert metrics.total_deliverables == 11
        assert metrics.overdue_deliverables == 1


# =====================================================================
# SINGLETON PATTERN
# =====================================================================


class TestSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_cross_functional_team_service()
        svc2 = get_cross_functional_team_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_cross_functional_team_service()
        svc2 = reset_cross_functional_team_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_cross_functional_team_service()
        # Delete a team formation
        svc.delete_team_formation("TF-001")
        assert svc.get_team_formation("TF-001") is None
        # Reset should bring it back
        svc2 = reset_cross_functional_team_service()
        assert svc2.get_team_formation("TF-001") is not None

    def test_get_after_reset_returns_reset_instance(self):
        svc1 = reset_cross_functional_team_service()
        svc2 = get_cross_functional_team_service()
        assert svc1 is svc2

    def test_reset_restores_role_assignments(self):
        svc = get_cross_functional_team_service()
        svc.delete_role_assignment("RA-001")
        assert svc.get_role_assignment("RA-001") is None
        svc2 = reset_cross_functional_team_service()
        assert svc2.get_role_assignment("RA-001") is not None

    def test_reset_restores_meeting_cadence_records(self):
        svc = get_cross_functional_team_service()
        svc.delete_meeting_cadence_record("MC-001")
        assert svc.get_meeting_cadence_record("MC-001") is None
        svc2 = reset_cross_functional_team_service()
        assert svc2.get_meeting_cadence_record("MC-001") is not None

    def test_reset_restores_deliverable_trackers(self):
        svc = get_cross_functional_team_service()
        svc.delete_deliverable_tracker("DT-001")
        assert svc.get_deliverable_tracker("DT-001") is None
        svc2 = reset_cross_functional_team_service()
        assert svc2.get_deliverable_tracker("DT-001") is not None

    def test_reset_restores_performance_reviews(self):
        svc = get_cross_functional_team_service()
        svc.delete_performance_review("PR-001")
        assert svc.get_performance_review("PR-001") is None
        svc2 = reset_cross_functional_team_service()
        assert svc2.get_performance_review("PR-001") is not None
