"""Tests for Regulatory Intelligence (REG-INTEL).

Covers:
- Seed data verification (intelligence items, submissions, gaps, communications)
- Intelligence item CRUD (create, read, update, delete, list, filter)
- Submission tracker CRUD (create, read, update, delete, list, filter)
- Compliance gap CRUD (create, read, update, delete, list, filter)
- Authority communication CRUD (create, read, update, delete, list, filter)
- Metrics computation (items breakdown, submissions, gaps, communications)
- Error handling (404s for all entity types)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.regulatory_intelligence_service import (
    RegulatoryIntelligenceService,
    get_regulatory_intelligence_service,
    reset_regulatory_intelligence_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/regulatory-intelligence"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_regulatory_intelligence_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> RegulatoryIntelligenceService:
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


def _make_intelligence_item_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "authority": "fda",
        "intelligence_type": "guidance_update",
        "title": "Test Guidance Update",
        "summary": "Test summary of a regulatory guidance update.",
        "published_date": now.isoformat(),
        "impact_level": "medium",
        "affected_trials": [EYLEA_TRIAL],
        "affected_therapeutic_areas": ["Ophthalmology"],
    }
    defaults.update(overrides)
    return defaults


def _make_submission_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "authority": "fda",
        "submission_type": "bla",
        "submission_number": "BLA-TEST-001",
        "title": "Test BLA Submission",
        "planned_date": (now + timedelta(days=30)).isoformat(),
        "lead_reviewer": "Dr. Test Reviewer",
        "assigned_team": ["Dr. Test Reviewer", "Test Specialist"],
    }
    defaults.update(overrides)
    return defaults


def _make_compliance_gap_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "authority": "fda",
        "regulation_reference": "21 CFR 312.32",
        "gap_description": "Test compliance gap description.",
        "severity": "major",
        "identified_by": "Dr. Test Auditor",
    }
    defaults.update(overrides)
    return defaults


def _make_communication_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "authority": "fda",
        "direction": "inbound",
        "subject": "Test Communication Subject",
        "content_summary": "Test communication content summary.",
        "communication_date": now.isoformat(),
        "handled_by": "Dr. Test Handler",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_intelligence_items_count(self, svc: RegulatoryIntelligenceService):
        items = svc.list_intelligence_items()
        assert len(items) == 12

    def test_seed_submissions_count(self, svc: RegulatoryIntelligenceService):
        submissions = svc.list_submissions()
        assert len(submissions) == 10

    def test_seed_compliance_gaps_count(self, svc: RegulatoryIntelligenceService):
        gaps = svc.list_compliance_gaps()
        assert len(gaps) == 10

    def test_seed_communications_count(self, svc: RegulatoryIntelligenceService):
        comms = svc.list_communications()
        assert len(comms) == 10

    def test_seed_items_have_multiple_authorities(self, svc: RegulatoryIntelligenceService):
        items = svc.list_intelligence_items()
        authorities = {i.authority.value for i in items}
        assert "fda" in authorities
        assert "ema" in authorities
        assert "pmda" in authorities

    def test_seed_items_have_multiple_types(self, svc: RegulatoryIntelligenceService):
        items = svc.list_intelligence_items()
        types = {i.intelligence_type.value for i in items}
        assert "guidance_update" in types
        assert "regulation_change" in types
        assert "safety_alert" in types

    def test_seed_items_have_multiple_statuses(self, svc: RegulatoryIntelligenceService):
        items = svc.list_intelligence_items()
        statuses = {i.status.value for i in items}
        assert "new" in statuses
        assert "assessed" in statuses
        assert "action_required" in statuses

    def test_seed_submissions_have_multiple_statuses(self, svc: RegulatoryIntelligenceService):
        submissions = svc.list_submissions()
        statuses = {s.status.value for s in submissions}
        assert "drafting" in statuses
        assert "submitted" in statuses
        assert "approved" in statuses

    def test_seed_gaps_have_multiple_severities(self, svc: RegulatoryIntelligenceService):
        gaps = svc.list_compliance_gaps()
        severities = {g.severity.value for g in gaps}
        assert "minor" in severities
        assert "major" in severities
        assert "critical" in severities

    def test_seed_gaps_have_multiple_statuses(self, svc: RegulatoryIntelligenceService):
        gaps = svc.list_compliance_gaps()
        statuses = {g.status.value for g in gaps}
        assert "identified" in statuses
        assert "in_progress" in statuses
        assert "resolved" in statuses

    def test_seed_communications_have_both_directions(self, svc: RegulatoryIntelligenceService):
        comms = svc.list_communications()
        directions = {c.direction for c in comms}
        assert "inbound" in directions
        assert "outbound" in directions


# =====================================================================
# INTELLIGENCE ITEM CRUD
# =====================================================================


class TestIntelligenceItemCrud:
    """Test intelligence item CRUD operations."""

    @pytest.mark.anyio
    async def test_list_items(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/items")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_items_filter_authority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/items", params={"authority": "fda"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["authority"] == "fda"

    @pytest.mark.anyio
    async def test_list_items_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/items", params={"intelligence_type": "guidance_update"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["intelligence_type"] == "guidance_update"

    @pytest.mark.anyio
    async def test_list_items_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/items", params={"status": "new"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "new"

    @pytest.mark.anyio
    async def test_list_items_filter_impact(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/items", params={"impact_level": "high"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["impact_level"] == "high"

    @pytest.mark.anyio
    async def test_get_item(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/items/RI-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RI-001"
        assert data["authority"] == "fda"

    @pytest.mark.anyio
    async def test_get_item_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/items/RI-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_item(self, client: AsyncClient):
        payload = _make_intelligence_item_create()
        resp = await client.post(f"{API_PREFIX}/items", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Guidance Update"
        assert data["id"].startswith("RI-")
        assert data["status"] == "new"

    @pytest.mark.anyio
    async def test_update_item(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/items/RI-001",
            json={"title": "Updated Title", "impact_level": "critical"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Title"
        assert data["impact_level"] == "critical"

    @pytest.mark.anyio
    async def test_update_item_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/items/RI-NONEXISTENT",
            json={"title": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_item_set_assessed_by_auto_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/items/RI-007",
            json={"assessed_by": "Dr. New Assessor"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["assessed_by"] == "Dr. New Assessor"
        assert data["assessed_date"] is not None

    @pytest.mark.anyio
    async def test_delete_item(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/items/RI-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/items/RI-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_item_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/items/RI-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# SUBMISSION TRACKER CRUD
# =====================================================================


class TestSubmissionCrud:
    """Test submission tracker CRUD operations."""

    @pytest.mark.anyio
    async def test_list_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_submissions_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_submissions_filter_authority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions", params={"authority": "fda"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["authority"] == "fda"

    @pytest.mark.anyio
    async def test_list_submissions_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions", params={"status": "submitted"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "submitted"

    @pytest.mark.anyio
    async def test_get_submission(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions/SUB-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SUB-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_submission_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions/SUB-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_submission(self, client: AsyncClient):
        payload = _make_submission_create()
        resp = await client.post(f"{API_PREFIX}/submissions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test BLA Submission"
        assert data["id"].startswith("SUB-")
        assert data["status"] == "drafting"

    @pytest.mark.anyio
    async def test_update_submission(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/submissions/SUB-005",
            json={"status": "internal_review", "lead_reviewer": "Dr. Updated Reviewer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "internal_review"
        assert data["lead_reviewer"] == "Dr. Updated Reviewer"

    @pytest.mark.anyio
    async def test_update_submission_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/submissions/SUB-NONEXISTENT",
            json={"status": "submitted"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_submission(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/submissions/SUB-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/submissions/SUB-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_submission_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/submissions/SUB-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# COMPLIANCE GAP CRUD
# =====================================================================


class TestComplianceGapCrud:
    """Test compliance gap CRUD operations."""

    @pytest.mark.anyio
    async def test_list_gaps(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/gaps")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_gaps_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/gaps", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_gaps_filter_authority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/gaps", params={"authority": "fda"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["authority"] == "fda"

    @pytest.mark.anyio
    async def test_list_gaps_filter_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/gaps", params={"severity": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["severity"] == "critical"

    @pytest.mark.anyio
    async def test_list_gaps_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/gaps", params={"status": "resolved"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "resolved"

    @pytest.mark.anyio
    async def test_get_gap(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/gaps/GAP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "GAP-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_gap_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/gaps/GAP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_gap(self, client: AsyncClient):
        payload = _make_compliance_gap_create()
        resp = await client.post(f"{API_PREFIX}/gaps", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["gap_description"] == "Test compliance gap description."
        assert data["id"].startswith("GAP-")
        assert data["status"] == "identified"

    @pytest.mark.anyio
    async def test_update_gap(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/gaps/GAP-001",
            json={"status": "in_progress", "remediation_plan": "Updated plan"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["remediation_plan"] == "Updated plan"

    @pytest.mark.anyio
    async def test_update_gap_resolve_auto_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/gaps/GAP-006",
            json={"status": "resolved", "evidence_of_closure": "Verified and closed."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resolved"
        assert data["resolved_date"] is not None

    @pytest.mark.anyio
    async def test_update_gap_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/gaps/GAP-NONEXISTENT",
            json={"status": "resolved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_gap(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/gaps/GAP-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/gaps/GAP-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_gap_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/gaps/GAP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# AUTHORITY COMMUNICATION CRUD
# =====================================================================


class TestCommunicationCrud:
    """Test authority communication CRUD operations."""

    @pytest.mark.anyio
    async def test_list_communications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_communications_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_communications_filter_authority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications", params={"authority": "fda"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["authority"] == "fda"

    @pytest.mark.anyio
    async def test_list_communications_filter_submission(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications", params={"submission_id": "SUB-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["submission_id"] == "SUB-001"

    @pytest.mark.anyio
    async def test_get_communication(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications/COMM-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "COMM-001"
        assert data["direction"] == "inbound"

    @pytest.mark.anyio
    async def test_get_communication_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications/COMM-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_communication(self, client: AsyncClient):
        payload = _make_communication_create()
        resp = await client.post(f"{API_PREFIX}/communications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject"] == "Test Communication Subject"
        assert data["id"].startswith("COMM-")

    @pytest.mark.anyio
    async def test_update_communication(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/communications/COMM-005",
            json={"responded": True, "response_date": datetime.now(timezone.utc).isoformat()},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["responded"] is True
        assert data["response_date"] is not None

    @pytest.mark.anyio
    async def test_update_communication_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/communications/COMM-NONEXISTENT",
            json={"responded": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_communication(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/communications/COMM-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/communications/COMM-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_communication_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/communications/COMM-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test regulatory intelligence metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_intelligence_items"] == 12
        assert data["total_submissions"] == 10
        assert data["total_compliance_gaps"] == 10
        assert data["total_communications"] == 10

    @pytest.mark.anyio
    async def test_metrics_items_by_authority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "fda" in data["items_by_authority"]
        assert "ema" in data["items_by_authority"]
        total_by_authority = sum(data["items_by_authority"].values())
        assert total_by_authority == data["total_intelligence_items"]

    @pytest.mark.anyio
    async def test_metrics_items_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "guidance_update" in data["items_by_type"]
        total_by_type = sum(data["items_by_type"].values())
        assert total_by_type == data["total_intelligence_items"]

    @pytest.mark.anyio
    async def test_metrics_items_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_status = sum(data["items_by_status"].values())
        assert total_by_status == data["total_intelligence_items"]

    @pytest.mark.anyio
    async def test_metrics_items_by_impact(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_impact = sum(data["items_by_impact"].values())
        assert total_by_impact == data["total_intelligence_items"]

    @pytest.mark.anyio
    async def test_metrics_submissions_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_status = sum(data["submissions_by_status"].values())
        assert total_by_status == data["total_submissions"]

    @pytest.mark.anyio
    async def test_metrics_pending_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["pending_submissions"] > 0

    @pytest.mark.anyio
    async def test_metrics_open_gaps(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["open_gaps"] > 0

    @pytest.mark.anyio
    async def test_metrics_critical_gaps(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        # GAP-005 is critical and not resolved
        assert data["critical_gaps"] >= 1

    @pytest.mark.anyio
    async def test_metrics_gaps_by_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_severity = sum(data["gaps_by_severity"].values())
        assert total_by_severity == data["total_compliance_gaps"]

    @pytest.mark.anyio
    async def test_metrics_pending_responses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["pending_responses"] >= 0

    def test_metrics_service_direct(self, svc: RegulatoryIntelligenceService):
        metrics = svc.get_metrics()
        assert metrics.total_intelligence_items == 12
        assert metrics.total_submissions == 10
        assert metrics.total_compliance_gaps == 10
        assert metrics.total_communications == 10
        assert metrics.pending_submissions > 0
        assert metrics.open_gaps > 0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_regulatory_intelligence_service()
        svc2 = get_regulatory_intelligence_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_regulatory_intelligence_service()
        svc2 = reset_regulatory_intelligence_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_regulatory_intelligence_service()
        svc.delete_intelligence_item("RI-001")
        assert svc.get_intelligence_item("RI-001") is None
        svc2 = reset_regulatory_intelligence_service()
        assert svc2.get_intelligence_item("RI-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_items_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/items")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_submissions_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_gaps_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/gaps")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_communications_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_item_all_authorities(self, client: AsyncClient):
        for auth in ["fda", "ema", "pmda", "tga", "health_canada", "mhra", "anvisa", "nmpa"]:
            payload = _make_intelligence_item_create(authority=auth)
            resp = await client.post(f"{API_PREFIX}/items", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["authority"] == auth

    @pytest.mark.anyio
    async def test_create_item_all_types(self, client: AsyncClient):
        for itype in [
            "guidance_update", "regulation_change", "advisory_committee",
            "safety_alert", "approval_decision", "inspection_trend",
            "enforcement_action", "policy_announcement",
        ]:
            payload = _make_intelligence_item_create(intelligence_type=itype)
            resp = await client.post(f"{API_PREFIX}/items", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["intelligence_type"] == itype

    @pytest.mark.anyio
    async def test_create_item_all_impact_levels(self, client: AsyncClient):
        for level in ["low", "medium", "high", "critical"]:
            payload = _make_intelligence_item_create(impact_level=level)
            resp = await client.post(f"{API_PREFIX}/items", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["impact_level"] == level

    @pytest.mark.anyio
    async def test_create_submission_all_types(self, client: AsyncClient):
        for stype in ["ind", "nda", "bla", "anda", "cta", "maa", "amendment", "annual_report", "safety_report"]:
            payload = _make_submission_create(submission_type=stype, submission_number=f"TEST-{stype}")
            resp = await client.post(f"{API_PREFIX}/submissions", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["submission_type"] == stype

    @pytest.mark.anyio
    async def test_create_gap_all_severities(self, client: AsyncClient):
        for sev in ["minor", "major", "critical"]:
            payload = _make_compliance_gap_create(severity=sev)
            resp = await client.post(f"{API_PREFIX}/gaps", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["severity"] == sev

    @pytest.mark.anyio
    async def test_create_communication_with_submission(self, client: AsyncClient):
        payload = _make_communication_create(submission_id="SUB-001")
        resp = await client.post(f"{API_PREFIX}/communications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["submission_id"] == "SUB-001"

    @pytest.mark.anyio
    async def test_create_communication_with_deadline(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = _make_communication_create(
            response_deadline=(now + timedelta(days=30)).isoformat(),
        )
        resp = await client.post(f"{API_PREFIX}/communications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["response_deadline"] is not None

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_intelligence_items" in data
        assert "items_by_authority" in data
        assert "items_by_type" in data
        assert "items_by_status" in data
        assert "items_by_impact" in data
        assert "total_submissions" in data
        assert "submissions_by_status" in data
        assert "submissions_by_authority" in data
        assert "pending_submissions" in data
        assert "total_compliance_gaps" in data
        assert "open_gaps" in data
        assert "critical_gaps" in data
        assert "gaps_by_severity" in data
        assert "total_communications" in data
        assert "pending_responses" in data
        assert "overdue_responses" in data


# =====================================================================
# DATA VALIDATION
# =====================================================================


class TestDataValidation:
    """Test detailed data validation across the system."""

    @pytest.mark.anyio
    async def test_item_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/items/RI-001")
        data = resp.json()
        assert "id" in data
        assert "authority" in data
        assert "intelligence_type" in data
        assert "title" in data
        assert "summary" in data
        assert "published_date" in data
        assert "impact_level" in data
        assert "status" in data
        assert "affected_trials" in data

    @pytest.mark.anyio
    async def test_submission_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions/SUB-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "authority" in data
        assert "submission_type" in data
        assert "submission_number" in data
        assert "title" in data
        assert "status" in data
        assert "planned_date" in data
        assert "lead_reviewer" in data

    @pytest.mark.anyio
    async def test_gap_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/gaps/GAP-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "authority" in data
        assert "regulation_reference" in data
        assert "gap_description" in data
        assert "severity" in data
        assert "status" in data
        assert "identified_date" in data
        assert "identified_by" in data

    @pytest.mark.anyio
    async def test_communication_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications/COMM-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "authority" in data
        assert "direction" in data
        assert "subject" in data
        assert "content_summary" in data
        assert "communication_date" in data
        assert "handled_by" in data

    def test_resolved_gaps_have_resolved_date(self, svc: RegulatoryIntelligenceService):
        gaps = svc.list_compliance_gaps(status="resolved")
        for g in gaps:
            assert g.resolved_date is not None

    def test_approved_submissions_have_response(self, svc: RegulatoryIntelligenceService):
        submissions = svc.list_submissions(status="approved")
        for s in submissions:
            assert s.response_date is not None

    def test_items_sorted_by_published_date_descending(self, svc: RegulatoryIntelligenceService):
        items = svc.list_intelligence_items()
        dates = [i.published_date for i in items]
        assert dates == sorted(dates, reverse=True)

    def test_submissions_sorted_by_planned_date_descending(self, svc: RegulatoryIntelligenceService):
        submissions = svc.list_submissions()
        dates = [s.planned_date for s in submissions]
        assert dates == sorted(dates, reverse=True)

    def test_gaps_sorted_by_identified_date_descending(self, svc: RegulatoryIntelligenceService):
        gaps = svc.list_compliance_gaps()
        dates = [g.identified_date for g in gaps]
        assert dates == sorted(dates, reverse=True)

    def test_comms_sorted_by_communication_date_descending(self, svc: RegulatoryIntelligenceService):
        comms = svc.list_communications()
        dates = [c.communication_date for c in comms]
        assert dates == sorted(dates, reverse=True)
