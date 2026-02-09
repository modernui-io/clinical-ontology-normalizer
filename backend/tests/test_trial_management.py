"""Tests for Trial Management Office (TMO) & Multi-Site Coordination (CLINICAL-10).

Covers:
- Seed data verification (sites, countries, milestones, communications, blockers, resources)
- Site activation CRUD (list, detail, filter by trial/country/status)
- Site activation status transitions (valid and invalid)
- Delayed site detection
- Blocker management (raise, resolve, list, filter open, auto-escalation)
- Country regulatory CRUD (list, detail, update status)
- Milestone CRUD (create, read, update, list, filter by trial/category/status)
- Critical path analysis
- Gantt chart data generation
- Communication management (send, list, filter, acknowledge)
- Acknowledgment rate computation
- TMO dashboard aggregation
- Enrollment projections and forecasting
- Cross-trial resource management (add, list, detail, utilization report)
- Service statistics
- Error handling (404s, 400s, invalid transitions)
- Edge cases (empty filters, boundary conditions)
- Service singleton and reset behavior
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.trial_management import (
    CommunicationType,
    CountryStatus,
    CountryStatusUpdate,
    MilestoneCategory,
    MilestoneStatus,
    SiteActivationStatus,
    SiteActivationUpdate,
    SiteBlockerCreate,
    TrialMilestoneCreate,
    TrialMilestoneUpdate,
)
from app.services.trial_management_service import (
    BLOCKER_ESCALATION_DAYS,
    CURRENT_ENROLLMENT,
    ENROLLMENT_TARGETS,
    TrialManagementService,
    get_tmo_service,
    reset_tmo_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/trial-management"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_tmo_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> TrialManagementService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_milestone_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "name": "Test Milestone",
        "category": "enrollment",
        "planned_date": (now + timedelta(days=60)).isoformat(),
        "responsible_party": "Test Team",
        "dependencies": [],
    }
    defaults.update(overrides)
    return defaults


def _make_communication_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "type": "newsletter",
        "subject": "Test Newsletter",
        "body": "This is a test communication body.",
        "recipients": ["SITE-EYL-001", "SITE-EYL-002"],
        "requires_acknowledgment": False,
    }
    defaults.update(overrides)
    return defaults


def _make_blocker_create(**overrides) -> dict:
    defaults = {
        "description": "Test blocker description",
        "category": "regulatory",
        "impact_description": "Test impact",
    }
    defaults.update(overrides)
    return defaults


def _make_resource_create(**overrides) -> dict:
    defaults = {
        "resource_name": "Test Resource",
        "role": "Clinical Research Associate",
        "assigned_trials": [EYLEA_TRIAL],
        "utilization_pct": 50.0,
        "skills": ["GCP", "Site Monitoring"],
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_site_activations_count(self, svc: TrialManagementService):
        sites = svc.list_site_activations()
        assert len(sites) == 30

    def test_seed_eylea_sites_count(self, svc: TrialManagementService):
        sites = svc.list_site_activations(trial_id=EYLEA_TRIAL)
        assert len(sites) == 12

    def test_seed_dupixent_sites_count(self, svc: TrialManagementService):
        sites = svc.list_site_activations(trial_id=DUPIXENT_TRIAL)
        assert len(sites) == 10

    def test_seed_libtayo_sites_count(self, svc: TrialManagementService):
        sites = svc.list_site_activations(trial_id=LIBTAYO_TRIAL)
        assert len(sites) == 8

    def test_seed_country_regulatory_count(self, svc: TrialManagementService):
        countries = svc.list_country_regulatory()
        assert len(countries) == 8

    def test_seed_milestones_count(self, svc: TrialManagementService):
        milestones = svc.list_milestones()
        assert len(milestones) == 40

    def test_seed_communications_count(self, svc: TrialManagementService):
        comms = svc.list_communications()
        assert len(comms) == 15

    def test_seed_blockers_count(self, svc: TrialManagementService):
        blockers = svc.list_blockers()
        assert len(blockers) == 8

    def test_seed_open_blockers_count(self, svc: TrialManagementService):
        blockers = svc.list_blockers(open_only=True)
        assert len(blockers) == 5

    def test_seed_resolved_blockers_count(self, svc: TrialManagementService):
        all_blockers = svc.list_blockers()
        resolved = [b for b in all_blockers if b.resolved_date is not None]
        assert len(resolved) == 3

    def test_seed_resources_count(self, svc: TrialManagementService):
        resources = svc.list_resources()
        assert len(resources) == 10

    def test_seed_site_statuses_variety(self, svc: TrialManagementService):
        sites = svc.list_site_activations()
        statuses = {s.status for s in sites}
        assert SiteActivationStatus.ENROLLING in statuses
        assert SiteActivationStatus.SITE_INITIATED in statuses
        assert SiteActivationStatus.CONTRACTS_EXECUTED in statuses

    def test_seed_eylea_milestones_count(self, svc: TrialManagementService):
        milestones = svc.list_milestones(trial_id=EYLEA_TRIAL)
        assert len(milestones) == 15

    def test_seed_dupixent_milestones_count(self, svc: TrialManagementService):
        milestones = svc.list_milestones(trial_id=DUPIXENT_TRIAL)
        assert len(milestones) == 13

    def test_seed_libtayo_milestones_count(self, svc: TrialManagementService):
        milestones = svc.list_milestones(trial_id=LIBTAYO_TRIAL)
        assert len(milestones) == 12


# =====================================================================
# SITE ACTIVATION CRUD
# =====================================================================


class TestSiteActivationCrud:
    """Test site activation list, detail, and filter operations."""

    @pytest.mark.anyio
    async def test_list_sites(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 30
        assert len(data["items"]) == 30

    @pytest.mark.anyio
    async def test_list_sites_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_sites_filter_country(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites", params={"country": "US"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["country"] == "US"

    @pytest.mark.anyio
    async def test_list_sites_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites", params={"status": "enrolling"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "enrolling"

    @pytest.mark.anyio
    async def test_list_sites_combined_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sites",
            params={"trial_id": EYLEA_TRIAL, "country": "US", "status": "enrolling"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["country"] == "US"
            assert item["status"] == "enrolling"

    @pytest.mark.anyio
    async def test_get_site_activation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-EYL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SITE-EYL-001"
        assert data["site_name"] == "Massachusetts Eye and Ear"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_site_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_sites_empty_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites", params={"country": "ZZ"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


# =====================================================================
# SITE ACTIVATION STATUS TRANSITIONS
# =====================================================================


class TestSiteActivationTransitions:
    """Test site activation status update with transition validation."""

    @pytest.mark.anyio
    async def test_valid_transition_irb_to_contracts(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sites/SITE-EYL-006/status",
            json={"status": "contracts_executed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "contracts_executed"
        assert data["contract_execution_date"] is not None

    @pytest.mark.anyio
    async def test_valid_transition_contracts_to_initiated(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sites/SITE-EYL-005/status",
            json={"status": "site_initiated"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "site_initiated"
        assert data["actual_activation_date"] is not None

    @pytest.mark.anyio
    async def test_valid_transition_initiated_to_enrolling(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sites/SITE-EYL-004/status",
            json={"status": "enrolling"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "enrolling"
        assert data["first_patient_date"] is not None

    @pytest.mark.anyio
    async def test_invalid_transition_enrolling_to_planned(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sites/SITE-EYL-001/status",
            json={"status": "planned"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_invalid_transition_skip_status(self, client: AsyncClient):
        # SITE-EYL-006 is IRB_APPROVED, cannot skip to ENROLLING
        resp = await client.put(
            f"{API_PREFIX}/sites/SITE-EYL-006/status",
            json={"status": "enrolling"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_nonexistent_site(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sites/SITE-NONEXISTENT/status",
            json={"status": "enrolling"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_valid_transition_enrolling_to_complete(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sites/SITE-EYL-001/status",
            json={"status": "enrollment_complete"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "enrollment_complete"

    @pytest.mark.anyio
    async def test_valid_transition_enrolling_to_closed(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sites/SITE-EYL-002/status",
            json={"status": "closed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"

    def test_status_transition_sets_irb_date(self, svc: TrialManagementService):
        # SITE-EYL-010 is REGULATORY_SUBMITTED
        result = svc.update_site_status(
            "SITE-EYL-010",
            SiteActivationUpdate(status=SiteActivationStatus.IRB_APPROVED),
        )
        assert result.irb_approval_date is not None


# =====================================================================
# DELAYED SITES
# =====================================================================


class TestDelayedSites:
    """Test delayed site detection."""

    @pytest.mark.anyio
    async def test_list_delayed_sites(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/delayed")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        for item in data:
            assert "site_id" in item
            assert "delay_days" in item
            assert item["delay_days"] > 14

    def test_delayed_sites_have_required_fields(self, svc: TrialManagementService):
        delayed = svc.get_delayed_sites()
        for d in delayed:
            assert "site_id" in d
            assert "site_name" in d
            assert "trial_id" in d
            assert "status" in d
            assert "delay_days" in d
            assert "planned_date" in d


# =====================================================================
# BLOCKER MANAGEMENT
# =====================================================================


class TestBlockerManagement:
    """Test blocker raise, resolve, list, and auto-escalation."""

    @pytest.mark.anyio
    async def test_list_blockers(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/blockers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8

    @pytest.mark.anyio
    async def test_list_blockers_open_only(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/blockers", params={"open_only": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        for item in data["items"]:
            assert item["resolved_date"] is None

    @pytest.mark.anyio
    async def test_list_blockers_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/blockers", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_blocker(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/blockers/BLK-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "BLK-001"
        assert data["resolved_date"] is not None

    @pytest.mark.anyio
    async def test_get_blocker_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/blockers/BLK-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_raise_blocker(self, client: AsyncClient):
        payload = _make_blocker_create()
        resp = await client.post(
            f"{API_PREFIX}/sites/SITE-EYL-001/blockers",
            json=payload,
            params={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_id"] == "SITE-EYL-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["description"] == "Test blocker description"
        assert data["resolved_date"] is None
        assert data["escalated"] is False

    @pytest.mark.anyio
    async def test_raise_blocker_adds_to_site(self, client: AsyncClient):
        payload = _make_blocker_create()
        resp = await client.post(
            f"{API_PREFIX}/sites/SITE-EYL-001/blockers",
            json=payload,
            params={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 201
        blocker_id = resp.json()["id"]

        # Check site now has the blocker
        resp2 = await client.get(f"{API_PREFIX}/sites/SITE-EYL-001")
        assert resp2.status_code == 200
        assert blocker_id in resp2.json()["blockers"]

    @pytest.mark.anyio
    async def test_resolve_blocker(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/blockers/BLK-004/resolve")
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolved_date"] is not None

    @pytest.mark.anyio
    async def test_resolve_already_resolved_blocker(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/blockers/BLK-001/resolve")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_resolve_nonexistent_blocker(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/blockers/BLK-NONEXISTENT/resolve")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_auto_escalate_blockers(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/blockers/auto-escalate")
        assert resp.status_code == 200
        data = resp.json()
        # Only blockers open > 14 days and not already escalated should be escalated
        for item in data["items"]:
            assert item["escalated"] is True

    def test_auto_escalate_threshold(self, svc: TrialManagementService):
        """Blockers open > 14 days should be escalated."""
        escalated = svc.auto_escalate_blockers()
        for b in escalated:
            now = datetime.now(timezone.utc)
            days_open = (now - b.raised_date).days
            assert days_open > BLOCKER_ESCALATION_DAYS

    def test_auto_escalate_skips_already_escalated(self, svc: TrialManagementService):
        """Already escalated blockers should not be re-escalated."""
        # First call escalates eligible ones
        first_round = svc.auto_escalate_blockers()
        # Second call should find none to escalate
        second_round = svc.auto_escalate_blockers()
        assert len(second_round) == 0

    def test_auto_escalate_skips_resolved(self, svc: TrialManagementService):
        """Resolved blockers should never be escalated."""
        escalated = svc.auto_escalate_blockers()
        for b in escalated:
            assert b.resolved_date is None

    def test_raise_blocker_service_level(self, svc: TrialManagementService):
        create = SiteBlockerCreate(
            description="Service-level test blocker",
            category="supply",
            impact_description="Testing impact",
        )
        blocker = svc.raise_blocker("SITE-EYL-001", EYLEA_TRIAL, create)
        assert blocker.id.startswith("BLK-")
        assert blocker.category == "supply"
        assert blocker.escalated is False


# =====================================================================
# COUNTRY REGULATORY
# =====================================================================


class TestCountryRegulatory:
    """Test country regulatory CRUD operations."""

    @pytest.mark.anyio
    async def test_list_countries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/countries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8

    @pytest.mark.anyio
    async def test_list_countries_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/countries", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_countries_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/countries", params={"status": "active"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "active"

    @pytest.mark.anyio
    async def test_get_country(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/countries/CR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CR-001"
        assert data["country_code"] == "US"
        assert data["regulatory_body"] == "FDA"

    @pytest.mark.anyio
    async def test_get_country_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/countries/CR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_country_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/countries/CR-003/status",
            json={"status": "active"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"

    @pytest.mark.anyio
    async def test_update_country_status_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/countries/CR-NONEXISTENT/status",
            json={"status": "active"},
        )
        assert resp.status_code == 400

    def test_update_country_sets_approval_date(self, svc: TrialManagementService):
        # CR-003 is APPROVED but has an approval date already
        # Update to ACTIVE should work
        result = svc.update_country_status(
            "CR-003", CountryStatusUpdate(status=CountryStatus.ACTIVE)
        )
        assert result.status == CountryStatus.ACTIVE


# =====================================================================
# MILESTONE CRUD
# =====================================================================


class TestMilestoneCrud:
    """Test milestone create, read, update, list, and filter."""

    @pytest.mark.anyio
    async def test_list_milestones(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 40

    @pytest.mark.anyio
    async def test_list_milestones_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_milestones_filter_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones", params={"category": "regulatory"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["category"] == "regulatory"

    @pytest.mark.anyio
    async def test_list_milestones_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_milestones_combined_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/milestones",
            params={"trial_id": EYLEA_TRIAL, "category": "enrollment"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["category"] == "enrollment"

    @pytest.mark.anyio
    async def test_get_milestone(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones/MS-EYL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MS-EYL-001"
        assert data["name"] == "Regulatory submission (US)"

    @pytest.mark.anyio
    async def test_get_milestone_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones/MS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_milestone(self, client: AsyncClient):
        payload = _make_milestone_create()
        resp = await client.post(f"{API_PREFIX}/milestones", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Milestone"
        assert data["category"] == "enrollment"
        assert data["status"] == "not_started"
        assert data["percent_complete"] == 0.0
        assert data["id"].startswith("MS-NEW-")

    @pytest.mark.anyio
    async def test_create_milestone_with_dependencies(self, client: AsyncClient):
        payload = _make_milestone_create(dependencies=["MS-EYL-001"])
        resp = await client.post(f"{API_PREFIX}/milestones", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert "MS-EYL-001" in data["dependencies"]

    @pytest.mark.anyio
    async def test_create_milestone_invalid_dependency(self, client: AsyncClient):
        payload = _make_milestone_create(dependencies=["MS-NONEXISTENT"])
        resp = await client.post(f"{API_PREFIX}/milestones", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_milestone(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/milestones/MS-EYL-010",
            json={"status": "completed", "percent_complete": 100.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["percent_complete"] == 100.0

    @pytest.mark.anyio
    async def test_update_milestone_name(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/milestones/MS-EYL-010",
            json={"name": "Updated 50% enrollment target"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated 50% enrollment target"

    @pytest.mark.anyio
    async def test_update_milestone_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/milestones/MS-NONEXISTENT",
            json={"name": "Test"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_milestone_invalid_dependency(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/milestones/MS-EYL-010",
            json={"dependencies": ["MS-NONEXISTENT"]},
        )
        assert resp.status_code == 400


# =====================================================================
# CRITICAL PATH ANALYSIS
# =====================================================================


class TestCriticalPath:
    """Test critical path analysis for trials."""

    @pytest.mark.anyio
    async def test_critical_path_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones/critical-path/{EYLEA_TRIAL}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert len(data["critical_path"]) > 0
        assert data["total_duration_days"] > 0
        assert data["earliest_completion"] is not None

    @pytest.mark.anyio
    async def test_critical_path_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones/critical-path/{DUPIXENT_TRIAL}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["critical_path"]) > 0

    @pytest.mark.anyio
    async def test_critical_path_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones/critical-path/{LIBTAYO_TRIAL}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["critical_path"]) > 0

    @pytest.mark.anyio
    async def test_critical_path_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones/critical-path/NONEXISTENT")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["critical_path"]) == 0
        assert data["total_duration_days"] == 0

    def test_critical_path_milestones_connected(self, svc: TrialManagementService):
        result = svc.get_critical_path(EYLEA_TRIAL)
        # Critical path milestones should form a dependency chain
        path_ids = [m.id for m in result.critical_path]
        for i in range(1, len(path_ids)):
            ms = result.critical_path[i]
            # Each milestone should depend on the previous one in the path
            assert any(dep in path_ids[:i] for dep in ms.dependencies) or len(ms.dependencies) == 0

    def test_critical_path_ends_with_latest_milestone(self, svc: TrialManagementService):
        result = svc.get_critical_path(EYLEA_TRIAL)
        if result.critical_path:
            last_ms = result.critical_path[-1]
            # The last milestone should have the latest planned date in the path
            latest_date = max(m.planned_date for m in result.critical_path)
            assert last_ms.planned_date == latest_date


# =====================================================================
# GANTT CHART DATA
# =====================================================================


class TestGanttChartData:
    """Test Gantt chart data generation."""

    @pytest.mark.anyio
    async def test_gantt_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones/gantt/{EYLEA_TRIAL}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert len(data["items"]) == 15  # All EYLEA milestones
        assert len(data["critical_path_ids"]) > 0

    @pytest.mark.anyio
    async def test_gantt_items_have_required_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones/gantt/{EYLEA_TRIAL}")
        data = resp.json()
        for item in data["items"]:
            assert "milestone_id" in item
            assert "name" in item
            assert "category" in item
            assert "status" in item
            assert "planned_start" in item
            assert "planned_end" in item
            assert "percent_complete" in item
            assert "is_critical_path" in item

    @pytest.mark.anyio
    async def test_gantt_critical_path_markers(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones/gantt/{EYLEA_TRIAL}")
        data = resp.json()
        cp_ids = set(data["critical_path_ids"])
        for item in data["items"]:
            if item["milestone_id"] in cp_ids:
                assert item["is_critical_path"] is True

    @pytest.mark.anyio
    async def test_gantt_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones/gantt/NONEXISTENT")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 0

    def test_gantt_planned_start_before_end_non_delayed(self, svc: TrialManagementService):
        gantt = svc.get_gantt_data(EYLEA_TRIAL)
        for item in gantt.items:
            # Delayed/at-risk milestones may have dependency start after planned end
            if item.status not in (MilestoneStatus.DELAYED, MilestoneStatus.AT_RISK):
                if not item.dependencies:
                    assert item.planned_start <= item.planned_end


# =====================================================================
# COMMUNICATIONS
# =====================================================================


class TestCommunications:
    """Test communication send, list, filter, and acknowledge."""

    @pytest.mark.anyio
    async def test_list_communications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_communications_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/communications", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_communications_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/communications", params={"comm_type": "newsletter"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["type"] == "newsletter"

    @pytest.mark.anyio
    async def test_get_communication(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications/COMM-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "COMM-001"
        assert data["type"] == "newsletter"

    @pytest.mark.anyio
    async def test_get_communication_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications/COMM-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_send_communication(self, client: AsyncClient):
        payload = _make_communication_create()
        resp = await client.post(f"{API_PREFIX}/communications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject"] == "Test Newsletter"
        assert data["type"] == "newsletter"
        assert len(data["recipients"]) == 2
        assert len(data["acknowledgments"]) == 0

    @pytest.mark.anyio
    async def test_send_communication_with_ack_required(self, client: AsyncClient):
        payload = _make_communication_create(
            type="safety_letter",
            subject="Safety Alert",
            requires_acknowledgment=True,
        )
        resp = await client.post(f"{API_PREFIX}/communications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["requires_acknowledgment"] is True

    @pytest.mark.anyio
    async def test_acknowledge_communication(self, client: AsyncClient):
        # COMM-002 requires acknowledgment; SITE-EYL-011 is a recipient but hasn't acked
        resp = await client.post(
            f"{API_PREFIX}/communications/COMM-002/acknowledge",
            params={"site_id": "SITE-EYL-011"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "SITE-EYL-011" in data["acknowledgments"]

    @pytest.mark.anyio
    async def test_acknowledge_not_a_recipient(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/communications/COMM-002/acknowledge",
            params={"site_id": "SITE-DUP-001"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_acknowledge_already_acknowledged(self, client: AsyncClient):
        # SITE-EYL-001 already acknowledged COMM-002
        resp = await client.post(
            f"{API_PREFIX}/communications/COMM-002/acknowledge",
            params={"site_id": "SITE-EYL-001"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_acknowledge_nonexistent_communication(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/communications/COMM-NONEXISTENT/acknowledge",
            params={"site_id": "SITE-EYL-001"},
        )
        assert resp.status_code == 400

    def test_acknowledgment_rate_computation(self, svc: TrialManagementService):
        """COMM-003 has all 12 sites acknowledged out of 12 recipients."""
        rate = svc.get_acknowledgment_rate("COMM-003")
        assert rate == 100.0

    def test_acknowledgment_rate_partial(self, svc: TrialManagementService):
        """COMM-002 has 10 out of 12 acknowledged."""
        rate = svc.get_acknowledgment_rate("COMM-002")
        assert 0.0 < rate < 100.0

    def test_acknowledgment_rate_nonexistent(self, svc: TrialManagementService):
        with pytest.raises(ValueError):
            svc.get_acknowledgment_rate("COMM-NONEXISTENT")


# =====================================================================
# TMO DASHBOARD
# =====================================================================


class TestTMODashboard:
    """Test TMO dashboard aggregation."""

    @pytest.mark.anyio
    async def test_dashboard_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dashboard/{EYLEA_TRIAL}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["total_sites"] == 12
        assert data["enrollment_target"] == 600
        assert data["current_enrollment"] == 342
        assert data["enrollment_rate_per_month"] >= 0.0
        assert data["milestones_on_track"] >= 0
        assert data["milestones_delayed"] >= 0
        assert data["open_blockers"] >= 0

    @pytest.mark.anyio
    async def test_dashboard_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dashboard/{DUPIXENT_TRIAL}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["total_sites"] == 10

    @pytest.mark.anyio
    async def test_dashboard_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dashboard/{LIBTAYO_TRIAL}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["total_sites"] == 8

    @pytest.mark.anyio
    async def test_dashboard_sites_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dashboard/{EYLEA_TRIAL}")
        data = resp.json()
        total_by_status = sum(data["sites_by_status"].values())
        assert total_by_status == data["total_sites"]

    @pytest.mark.anyio
    async def test_dashboard_countries_active(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dashboard/{EYLEA_TRIAL}")
        data = resp.json()
        assert data["countries_active"] > 0

    @pytest.mark.anyio
    async def test_dashboard_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dashboard/NONEXISTENT")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sites"] == 0
        assert data["enrollment_target"] == 0

    def test_dashboard_milestones_consistency(self, svc: TrialManagementService):
        dashboard = svc.get_dashboard(EYLEA_TRIAL)
        all_milestones = svc.list_milestones(trial_id=EYLEA_TRIAL)
        # on_track + delayed should cover all non-cancelled milestones
        cancelled = len([m for m in all_milestones if m.status == MilestoneStatus.CANCELLED])
        assert dashboard.milestones_on_track + dashboard.milestones_delayed == len(all_milestones) - cancelled

    def test_dashboard_open_blockers_matches_listing(self, svc: TrialManagementService):
        dashboard = svc.get_dashboard(EYLEA_TRIAL)
        open_blockers = svc.list_blockers(trial_id=EYLEA_TRIAL, open_only=True)
        assert dashboard.open_blockers == len(open_blockers)


# =====================================================================
# ENROLLMENT PROJECTIONS
# =====================================================================


class TestEnrollmentProjections:
    """Test enrollment projection forecasting."""

    @pytest.mark.anyio
    async def test_enrollment_projections_all(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/enrollment-projections")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3  # 3 trials

    @pytest.mark.anyio
    async def test_enrollment_projections_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/enrollment-projections",
            params={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        item = data["items"][0]
        assert item["trial_id"] == EYLEA_TRIAL
        assert item["enrollment_target"] == 600
        assert item["current_enrollment"] == 342

    @pytest.mark.anyio
    async def test_enrollment_projection_fields(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/enrollment-projections",
            params={"trial_id": EYLEA_TRIAL},
        )
        data = resp.json()
        item = data["items"][0]
        assert "enrollment_rate_per_month" in item
        assert "projected_completion_date" in item
        assert "months_remaining" in item
        assert "on_track" in item
        assert "sites_enrolling" in item
        assert item["enrollment_rate_per_month"] > 0
        assert item["sites_enrolling"] > 0

    def test_enrollment_projection_calculation(self, svc: TrialManagementService):
        projections = svc.get_enrollment_projection(trial_id=EYLEA_TRIAL)
        assert len(projections) == 1
        p = projections[0]
        # Rate should be sites_enrolling * 5
        enrolling_sites = len([
            s for s in svc.list_site_activations(trial_id=EYLEA_TRIAL)
            if s.status == SiteActivationStatus.ENROLLING
        ])
        assert p.enrollment_rate_per_month == enrolling_sites * 5.0

    def test_enrollment_months_remaining_positive(self, svc: TrialManagementService):
        projections = svc.get_enrollment_projection()
        for p in projections:
            if p.months_remaining is not None:
                assert p.months_remaining >= 0

    def test_enrollment_projected_completion_in_future(self, svc: TrialManagementService):
        now = datetime.now(timezone.utc)
        projections = svc.get_enrollment_projection()
        for p in projections:
            if p.projected_completion_date is not None:
                assert p.projected_completion_date > now


# =====================================================================
# CROSS-TRIAL RESOURCES
# =====================================================================


class TestCrossTrialResources:
    """Test cross-trial resource management."""

    @pytest.mark.anyio
    async def test_list_resources(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resources")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_get_resource(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resources/RES-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RES-001"
        assert data["resource_name"] == "Dr. Sarah Mitchell"

    @pytest.mark.anyio
    async def test_get_resource_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resources/RES-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_add_resource(self, client: AsyncClient):
        payload = _make_resource_create()
        resp = await client.post(f"{API_PREFIX}/resources", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["resource_name"] == "Test Resource"
        assert data["role"] == "Clinical Research Associate"
        assert data["id"].startswith("RES-")

    @pytest.mark.anyio
    async def test_add_resource_multiple_trials(self, client: AsyncClient):
        payload = _make_resource_create(
            assigned_trials=[EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL],
            utilization_pct=95.0,
        )
        resp = await client.post(f"{API_PREFIX}/resources", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["assigned_trials"]) == 3

    @pytest.mark.anyio
    async def test_utilization_report(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resources/utilization")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_resources"] == 10
        assert data["avg_utilization_pct"] > 0
        assert "over_utilized" in data
        assert "under_utilized" in data
        assert "by_role" in data

    def test_utilization_over_utilized(self, svc: TrialManagementService):
        report = svc.get_utilization_report()
        for r in report.over_utilized:
            assert r.utilization_pct > 90.0

    def test_utilization_under_utilized(self, svc: TrialManagementService):
        report = svc.get_utilization_report()
        for r in report.under_utilized:
            assert r.utilization_pct < 30.0

    def test_utilization_by_role(self, svc: TrialManagementService):
        report = svc.get_utilization_report()
        assert len(report.by_role) > 0
        for role, avg in report.by_role.items():
            assert 0.0 <= avg <= 100.0

    def test_utilization_avg_range(self, svc: TrialManagementService):
        report = svc.get_utilization_report()
        assert 0.0 <= report.avg_utilization_pct <= 100.0


# =====================================================================
# SERVICE STATISTICS
# =====================================================================


class TestStats:
    """Test service statistics endpoint."""

    @pytest.mark.anyio
    async def test_stats(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["site_activations"] == 30
        assert data["country_regulatory"] == 8
        assert data["milestones"] == 40
        assert data["communications"] == 15
        assert data["blockers"] == 8
        assert data["resources"] == 10
        assert data["open_blockers"] == 5


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_tmo_service()
        svc2 = get_tmo_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_tmo_service()
        svc2 = reset_tmo_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_tmo_service()
        # Resolve a blocker
        svc.resolve_blocker("BLK-004")
        blocker = svc.get_blocker("BLK-004")
        assert blocker is not None
        assert blocker.resolved_date is not None
        # Reset should bring it back as unresolved
        svc2 = reset_tmo_service()
        blocker2 = svc2.get_blocker("BLK-004")
        assert blocker2 is not None
        assert blocker2.resolved_date is None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_sites_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_blockers_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/blockers")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_milestones_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_communications_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_countries_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/countries")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_resources_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resources")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_enrollment_projections_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/enrollment-projections")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_raise_blocker_with_all_fields(self, client: AsyncClient):
        payload = _make_blocker_create(
            description="Full blocker with all fields",
            category="supply",
            impact_description="Critical supply chain disruption",
        )
        resp = await client.post(
            f"{API_PREFIX}/sites/SITE-EYL-001/blockers",
            json=payload,
            params={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_create_milestone_all_categories(self, client: AsyncClient):
        for category in ["regulatory", "site_activation", "enrollment", "data", "safety", "reporting"]:
            payload = _make_milestone_create(
                name=f"Test {category} milestone",
                category=category,
            )
            resp = await client.post(f"{API_PREFIX}/milestones", json=payload)
            assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_send_communication_all_types(self, client: AsyncClient):
        for comm_type in ["newsletter", "memo", "alert", "protocol_amendment", "safety_letter", "training_bulletin"]:
            payload = _make_communication_create(type=comm_type, subject=f"Test {comm_type}")
            resp = await client.post(f"{API_PREFIX}/communications", json=payload)
            assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_add_resource_with_availability(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = _make_resource_create(
            availability_start=now.isoformat(),
            utilization_pct=0.0,
        )
        resp = await client.post(f"{API_PREFIX}/resources", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["availability_start"] is not None

    def test_site_activation_all_status_values(self, svc: TrialManagementService):
        sites = svc.list_site_activations()
        statuses = {s.status for s in sites}
        # We should have a variety of statuses
        assert len(statuses) >= 4

    def test_country_regulatory_fields(self, svc: TrialManagementService):
        record = svc.get_country_regulatory("CR-001")
        assert record is not None
        assert record.country_code == "US"
        assert record.country_name == "United States"
        assert record.regulatory_body == "FDA"
        assert record.data_privacy_approval is True
        assert len(record.local_requirements) > 0

    def test_milestone_dependencies_valid(self, svc: TrialManagementService):
        """All milestone dependencies should reference existing milestones."""
        milestones = svc.list_milestones()
        all_ids = {m.id for m in milestones}
        for ms in milestones:
            for dep in ms.dependencies:
                assert dep in all_ids, f"Dependency {dep} not found for milestone {ms.id}"


# =====================================================================
# SITE ACTIVATION DETAIL VERIFICATION
# =====================================================================


class TestSiteActivationDetails:
    """Test site activation detail fields and dates."""

    @pytest.mark.anyio
    async def test_enrolling_site_has_first_patient_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-EYL-001")
        data = resp.json()
        assert data["status"] == "enrolling"
        assert data["first_patient_date"] is not None

    @pytest.mark.anyio
    async def test_irb_approved_site_has_irb_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-EYL-006")
        data = resp.json()
        assert data["status"] == "irb_approved"
        assert data["irb_approval_date"] is not None

    @pytest.mark.anyio
    async def test_contracts_executed_site_has_contract_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-EYL-005")
        data = resp.json()
        assert data["status"] == "contracts_executed"
        assert data["contract_execution_date"] is not None

    @pytest.mark.anyio
    async def test_site_initiated_has_activation_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SITE-EYL-004")
        data = resp.json()
        assert data["status"] == "site_initiated"
        assert data["actual_activation_date"] is not None

    def test_enrolling_sites_have_milestones(self, svc: TrialManagementService):
        site = svc.get_site_activation("SITE-EYL-001")
        assert site is not None
        assert len(site.milestones) > 0
        assert "First Patient Enrolled" in site.milestones


# =====================================================================
# COMMUNICATION DETAILS
# =====================================================================


class TestCommunicationDetails:
    """Test communication detail fields."""

    @pytest.mark.anyio
    async def test_protocol_amendment_requires_ack(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications/COMM-002")
        data = resp.json()
        assert data["type"] == "protocol_amendment"
        assert data["requires_acknowledgment"] is True

    @pytest.mark.anyio
    async def test_safety_letter_recipients(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications/COMM-003")
        data = resp.json()
        assert data["type"] == "safety_letter"
        assert len(data["recipients"]) == 12  # All EYLEA sites

    @pytest.mark.anyio
    async def test_alert_specific_recipients(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications/COMM-005")
        data = resp.json()
        assert data["type"] == "alert"
        assert len(data["recipients"]) < 12  # Only EU sites


# =====================================================================
# MILESTONE STATUS VARIETY
# =====================================================================


class TestMilestoneStatusVariety:
    """Test milestones have various statuses in seed data."""

    def test_completed_milestones_have_actual_dates(self, svc: TrialManagementService):
        milestones = svc.list_milestones(status=MilestoneStatus.COMPLETED)
        for ms in milestones:
            assert ms.actual_date is not None
            assert ms.percent_complete == 100.0

    def test_not_started_milestones_zero_percent(self, svc: TrialManagementService):
        milestones = svc.list_milestones(status=MilestoneStatus.NOT_STARTED)
        for ms in milestones:
            assert ms.percent_complete == 0.0
            assert ms.actual_date is None

    def test_delayed_milestone_exists(self, svc: TrialManagementService):
        milestones = svc.list_milestones(status=MilestoneStatus.DELAYED)
        assert len(milestones) > 0

    def test_at_risk_milestone_exists(self, svc: TrialManagementService):
        milestones = svc.list_milestones(status=MilestoneStatus.AT_RISK)
        assert len(milestones) > 0

    def test_in_progress_milestone_exists(self, svc: TrialManagementService):
        milestones = svc.list_milestones(status=MilestoneStatus.IN_PROGRESS)
        assert len(milestones) > 0
        for ms in milestones:
            assert 0 < ms.percent_complete < 100


# =====================================================================
# RESOURCE UTILIZATION DETAILS
# =====================================================================


class TestResourceUtilizationDetails:
    """Test detailed resource utilization reporting."""

    def test_resource_multi_trial_assignment(self, svc: TrialManagementService):
        resource = svc.get_resource("RES-004")
        assert resource is not None
        assert len(resource.assigned_trials) == 3  # All 3 trials

    def test_resource_skills_populated(self, svc: TrialManagementService):
        resource = svc.get_resource("RES-001")
        assert resource is not None
        assert len(resource.skills) > 0

    def test_resource_high_utilization(self, svc: TrialManagementService):
        resource = svc.get_resource("RES-007")
        assert resource is not None
        assert resource.utilization_pct == 97.0

    def test_resource_low_utilization(self, svc: TrialManagementService):
        resource = svc.get_resource("RES-010")
        assert resource is not None
        assert resource.utilization_pct == 25.0

    def test_utilization_report_total_matches(self, svc: TrialManagementService):
        report = svc.get_utilization_report()
        all_resources = svc.list_resources()
        assert report.total_resources == len(all_resources)


# =====================================================================
# ENROLLMENT PROJECTION DETAILS
# =====================================================================


class TestEnrollmentProjectionDetails:
    """Test detailed enrollment projection fields."""

    def test_eylea_enrollment_target(self, svc: TrialManagementService):
        projections = svc.get_enrollment_projection(trial_id=EYLEA_TRIAL)
        assert len(projections) == 1
        p = projections[0]
        assert p.enrollment_target == ENROLLMENT_TARGETS[EYLEA_TRIAL]
        assert p.current_enrollment == CURRENT_ENROLLMENT[EYLEA_TRIAL]

    def test_dupixent_enrollment_target(self, svc: TrialManagementService):
        projections = svc.get_enrollment_projection(trial_id=DUPIXENT_TRIAL)
        assert len(projections) == 1
        p = projections[0]
        assert p.enrollment_target == ENROLLMENT_TARGETS[DUPIXENT_TRIAL]

    def test_libtayo_enrollment_target(self, svc: TrialManagementService):
        projections = svc.get_enrollment_projection(trial_id=LIBTAYO_TRIAL)
        assert len(projections) == 1
        p = projections[0]
        assert p.enrollment_target == ENROLLMENT_TARGETS[LIBTAYO_TRIAL]

    def test_all_projections_have_rates(self, svc: TrialManagementService):
        projections = svc.get_enrollment_projection()
        for p in projections:
            assert p.enrollment_rate_per_month >= 0


# =====================================================================
# BLOCKER CATEGORY VERIFICATION
# =====================================================================


class TestBlockerCategories:
    """Test blocker category variety in seed data."""

    def test_regulatory_blockers_exist(self, svc: TrialManagementService):
        blockers = svc.list_blockers()
        regulatory = [b for b in blockers if b.category == "regulatory"]
        assert len(regulatory) > 0

    def test_staffing_blockers_exist(self, svc: TrialManagementService):
        blockers = svc.list_blockers()
        staffing = [b for b in blockers if b.category == "staffing"]
        assert len(staffing) > 0

    def test_supply_blockers_exist(self, svc: TrialManagementService):
        blockers = svc.list_blockers()
        supply = [b for b in blockers if b.category == "supply"]
        assert len(supply) > 0

    def test_contract_blockers_exist(self, svc: TrialManagementService):
        blockers = svc.list_blockers()
        contract = [b for b in blockers if b.category == "contract"]
        assert len(contract) > 0

    def test_escalated_blockers_exist(self, svc: TrialManagementService):
        blockers = svc.list_blockers()
        escalated = [b for b in blockers if b.escalated]
        assert len(escalated) > 0


# =====================================================================
# COUNTRY REGULATORY DETAILS
# =====================================================================


class TestCountryRegulatoryDetails:
    """Test country regulatory detail fields."""

    def test_us_fda_record(self, svc: TrialManagementService):
        record = svc.get_country_regulatory("CR-001")
        assert record is not None
        assert record.regulatory_body == "FDA"
        assert record.submission_date is not None
        assert record.approval_date is not None

    def test_japan_pmda_record(self, svc: TrialManagementService):
        record = svc.get_country_regulatory("CR-004")
        assert record is not None
        assert record.regulatory_body == "PMDA"
        assert record.import_license_date is not None

    def test_australia_tga_record(self, svc: TrialManagementService):
        record = svc.get_country_regulatory("CR-006")
        assert record is not None
        assert record.regulatory_body == "TGA"
        assert record.status == CountryStatus.APPROVED

    def test_canada_health_canada_record(self, svc: TrialManagementService):
        record = svc.get_country_regulatory("CR-008")
        assert record is not None
        assert record.regulatory_body == "Health Canada"
        assert record.status == CountryStatus.ACTIVE

    def test_countries_per_trial_eylea(self, svc: TrialManagementService):
        countries = svc.list_country_regulatory(trial_id=EYLEA_TRIAL)
        country_codes = {c.country_code for c in countries}
        assert "US" in country_codes
        assert "UK" in country_codes
        assert "DE" in country_codes
        assert "JP" in country_codes


# =====================================================================
# MULTIPLE OPERATIONS INTEGRATION
# =====================================================================


class TestIntegration:
    """Test multi-step integration scenarios."""

    @pytest.mark.anyio
    async def test_create_and_retrieve_milestone(self, client: AsyncClient):
        payload = _make_milestone_create(name="Integration Test Milestone")
        resp = await client.post(f"{API_PREFIX}/milestones", json=payload)
        assert resp.status_code == 201
        milestone_id = resp.json()["id"]

        resp2 = await client.get(f"{API_PREFIX}/milestones/{milestone_id}")
        assert resp2.status_code == 200
        assert resp2.json()["name"] == "Integration Test Milestone"

    @pytest.mark.anyio
    async def test_send_and_acknowledge_communication(self, client: AsyncClient):
        payload = _make_communication_create(
            requires_acknowledgment=True,
            recipients=["SITE-EYL-001"],
        )
        resp = await client.post(f"{API_PREFIX}/communications", json=payload)
        assert resp.status_code == 201
        comm_id = resp.json()["id"]

        resp2 = await client.post(
            f"{API_PREFIX}/communications/{comm_id}/acknowledge",
            params={"site_id": "SITE-EYL-001"},
        )
        assert resp2.status_code == 200
        assert "SITE-EYL-001" in resp2.json()["acknowledgments"]

    @pytest.mark.anyio
    async def test_raise_and_resolve_blocker(self, client: AsyncClient):
        payload = _make_blocker_create()
        resp = await client.post(
            f"{API_PREFIX}/sites/SITE-EYL-001/blockers",
            json=payload,
            params={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 201
        blocker_id = resp.json()["id"]

        resp2 = await client.post(f"{API_PREFIX}/blockers/{blocker_id}/resolve")
        assert resp2.status_code == 200
        assert resp2.json()["resolved_date"] is not None

    @pytest.mark.anyio
    async def test_add_and_list_resource(self, client: AsyncClient):
        initial_resp = await client.get(f"{API_PREFIX}/resources")
        initial_count = initial_resp.json()["total"]

        payload = _make_resource_create(resource_name="New Integration Resource")
        resp = await client.post(f"{API_PREFIX}/resources", json=payload)
        assert resp.status_code == 201

        final_resp = await client.get(f"{API_PREFIX}/resources")
        assert final_resp.json()["total"] == initial_count + 1

    @pytest.mark.anyio
    async def test_site_status_progression(self, client: AsyncClient):
        """Test full site activation progression: regulatory_submitted -> irb_approved -> contracts -> initiated -> enrolling."""
        site_id = "SITE-EYL-010"  # Currently REGULATORY_SUBMITTED

        # -> IRB_APPROVED
        resp = await client.put(
            f"{API_PREFIX}/sites/{site_id}/status",
            json={"status": "irb_approved"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "irb_approved"

        # -> CONTRACTS_EXECUTED
        resp = await client.put(
            f"{API_PREFIX}/sites/{site_id}/status",
            json={"status": "contracts_executed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "contracts_executed"

        # -> SITE_INITIATED
        resp = await client.put(
            f"{API_PREFIX}/sites/{site_id}/status",
            json={"status": "site_initiated"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "site_initiated"

        # -> ENROLLING
        resp = await client.put(
            f"{API_PREFIX}/sites/{site_id}/status",
            json={"status": "enrolling"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "enrolling"
        assert resp.json()["first_patient_date"] is not None
