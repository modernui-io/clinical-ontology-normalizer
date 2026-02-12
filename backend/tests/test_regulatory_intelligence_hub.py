"""Tests for Regulatory Intelligence Hub (REG-INTEL).

Covers:
- Seed data verification (landscape monitors, guideline trackers, authority communications,
  impact assessments, compliance alerts)
- Landscape monitor CRUD (create, read, update, delete, list, filter by trial/type/region/impact)
- Guideline tracker CRUD (create, read, update, delete, list, filter by trial/region/gap)
- Authority communication CRUD (create, read, update, delete, list, filter by trial/type/region)
- Impact assessment CRUD (create, read, update, delete, list, filter by trial/impact)
- Compliance alert CRUD (create, read, update, delete, list, filter by trial/severity/region/resolved)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.regulatory_intelligence_hub import (
    AlertSeverity,
    CommunicationType,
    ImpactLevel,
    IntelligenceType,
    RegionScope,
)
from app.services.regulatory_intelligence_hub_service import (
    RegulatoryIntelligenceHubService,
    get_regulatory_intelligence_hub_service,
    reset_regulatory_intelligence_hub_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/regulatory-intelligence-hub"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_regulatory_intelligence_hub_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> RegulatoryIntelligenceHubService:
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


def _make_landscape_monitor_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "intelligence_type": "guidance_update",
        "region": "us_fda",
        "title": "Test Guidance Update",
        "description": "Test description for guidance update",
        "monitored_by": "Dr. Test Monitor",
        "publication_date": (now - timedelta(days=5)).isoformat(),
        "impact_level": "moderate",
    }
    defaults.update(overrides)
    return defaults


def _make_guideline_tracker_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "guideline_name": "Test Guideline",
        "issuing_authority": "Test Authority",
        "region": "eu_ema",
        "version": "1.0",
        "effective_date": (now + timedelta(days=30)).isoformat(),
        "tracked_by": "Dr. Test Tracker",
    }
    defaults.update(overrides)
    return defaults


def _make_authority_communication_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": LIBTAYO_TRIAL,
        "communication_type": "type_b_meeting",
        "authority": "Test Authority",
        "region": "us_fda",
        "subject": "Test Meeting Subject",
        "managed_by": "Dr. Test Manager",
        "communication_date": (now - timedelta(days=10)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_impact_assessment_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "assessment_name": "Test Impact Assessment",
        "assessed_by": "Dr. Test Assessor",
        "impact_level": "moderate",
    }
    defaults.update(overrides)
    return defaults


def _make_compliance_alert_create(**overrides) -> dict:
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "alert_title": "Test Compliance Alert",
        "description": "Test alert description",
        "region": "global",
        "created_by": "Dr. Test Creator",
        "severity": "warning",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_landscape_monitors_count(self, svc: RegulatoryIntelligenceHubService):
        monitors = svc.list_landscape_monitors()
        assert len(monitors) == 12

    def test_seed_guideline_trackers_count(self, svc: RegulatoryIntelligenceHubService):
        trackers = svc.list_guideline_trackers()
        assert len(trackers) == 12

    def test_seed_authority_communications_count(self, svc: RegulatoryIntelligenceHubService):
        comms = svc.list_authority_communications()
        assert len(comms) == 12

    def test_seed_impact_assessments_count(self, svc: RegulatoryIntelligenceHubService):
        assessments = svc.list_impact_assessments()
        assert len(assessments) == 12

    def test_seed_compliance_alerts_count(self, svc: RegulatoryIntelligenceHubService):
        alerts = svc.list_compliance_alerts()
        assert len(alerts) == 12

    def test_seed_monitors_cover_all_trials(self, svc: RegulatoryIntelligenceHubService):
        monitors = svc.list_landscape_monitors()
        trial_ids = {m.trial_id for m in monitors}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_monitors_have_multiple_types(self, svc: RegulatoryIntelligenceHubService):
        monitors = svc.list_landscape_monitors()
        types = {m.intelligence_type for m in monitors}
        assert len(types) >= 4

    def test_seed_monitors_have_multiple_regions(self, svc: RegulatoryIntelligenceHubService):
        monitors = svc.list_landscape_monitors()
        regions = {m.region for m in monitors}
        assert len(regions) >= 4

    def test_seed_monitors_have_multiple_impact_levels(self, svc: RegulatoryIntelligenceHubService):
        monitors = svc.list_landscape_monitors()
        levels = {m.impact_level for m in monitors}
        assert ImpactLevel.HIGH in levels
        assert ImpactLevel.MODERATE in levels
        assert ImpactLevel.LOW in levels

    def test_seed_guidelines_have_compliance_gaps(self, svc: RegulatoryIntelligenceHubService):
        trackers = svc.list_guideline_trackers()
        has_gap = any(g.compliance_gap_identified for g in trackers)
        no_gap = any(not g.compliance_gap_identified for g in trackers)
        assert has_gap
        assert no_gap

    def test_seed_communications_have_multiple_types(self, svc: RegulatoryIntelligenceHubService):
        comms = svc.list_authority_communications()
        types = {c.communication_type for c in comms}
        assert len(types) >= 4

    def test_seed_communications_have_favorable_outcomes(self, svc: RegulatoryIntelligenceHubService):
        comms = svc.list_authority_communications()
        outcomes = {c.outcome_favorable for c in comms}
        assert True in outcomes

    def test_seed_assessments_have_critical_impact(self, svc: RegulatoryIntelligenceHubService):
        assessments = svc.list_impact_assessments()
        levels = {a.impact_level for a in assessments}
        assert ImpactLevel.CRITICAL in levels
        assert ImpactLevel.HIGH in levels

    def test_seed_alerts_have_multiple_severities(self, svc: RegulatoryIntelligenceHubService):
        alerts = svc.list_compliance_alerts()
        severities = {a.severity for a in alerts}
        assert AlertSeverity.EMERGENCY in severities
        assert AlertSeverity.URGENT in severities
        assert AlertSeverity.ACTION_REQUIRED in severities
        assert AlertSeverity.WARNING in severities
        assert AlertSeverity.INFORMATIONAL in severities

    def test_seed_alerts_have_resolved_and_unresolved(self, svc: RegulatoryIntelligenceHubService):
        alerts = svc.list_compliance_alerts()
        resolved = any(a.resolved for a in alerts)
        unresolved = any(not a.resolved for a in alerts)
        assert resolved
        assert unresolved


# =====================================================================
# LANDSCAPE MONITOR CRUD
# =====================================================================


class TestLandscapeMonitorCrud:
    """Test landscape monitor CRUD operations."""

    @pytest.mark.anyio
    async def test_list_landscape_monitors(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/landscape-monitors")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_landscape_monitors_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/landscape-monitors", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_landscape_monitors_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/landscape-monitors", params={"intelligence_type": "guidance_update"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["intelligence_type"] == "guidance_update"

    @pytest.mark.anyio
    async def test_list_landscape_monitors_filter_region(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/landscape-monitors", params={"region": "us_fda"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["region"] == "us_fda"

    @pytest.mark.anyio
    async def test_list_landscape_monitors_filter_impact(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/landscape-monitors", params={"impact_level": "high"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["impact_level"] == "high"

    @pytest.mark.anyio
    async def test_get_landscape_monitor(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/landscape-monitors/LM-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "LM-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["intelligence_type"] == "guidance_update"

    @pytest.mark.anyio
    async def test_get_landscape_monitor_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/landscape-monitors/LM-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_landscape_monitor(self, client: AsyncClient):
        payload = _make_landscape_monitor_create()
        resp = await client.post(f"{API_PREFIX}/landscape-monitors", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["intelligence_type"] == "guidance_update"
        assert data["impact_level"] == "moderate"
        assert data["analyzed"] is False
        assert data["id"].startswith("LM-")

    @pytest.mark.anyio
    async def test_update_landscape_monitor(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/landscape-monitors/LM-007",
            json={"analyzed": True, "analyzed_by": "Dr. Reviewer", "impact_level": "critical"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["analyzed"] is True
        assert data["analyzed_by"] == "Dr. Reviewer"
        assert data["impact_level"] == "critical"

    @pytest.mark.anyio
    async def test_update_landscape_monitor_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/landscape-monitors/LM-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_landscape_monitor(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/landscape-monitors/LM-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/landscape-monitors/LM-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_landscape_monitor_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/landscape-monitors/LM-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# GUIDELINE TRACKER CRUD
# =====================================================================


class TestGuidelineTrackerCrud:
    """Test guideline tracker CRUD operations."""

    @pytest.mark.anyio
    async def test_list_guideline_trackers(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/guideline-trackers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_guideline_trackers_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/guideline-trackers", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_guideline_trackers_filter_region(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/guideline-trackers", params={"region": "global"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["region"] == "global"

    @pytest.mark.anyio
    async def test_list_guideline_trackers_filter_gap(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/guideline-trackers", params={"compliance_gap_identified": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["compliance_gap_identified"] is True

    @pytest.mark.anyio
    async def test_get_guideline_tracker(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/guideline-trackers/GT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "GT-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["region"] == "global"

    @pytest.mark.anyio
    async def test_get_guideline_tracker_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/guideline-trackers/GT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_guideline_tracker(self, client: AsyncClient):
        payload = _make_guideline_tracker_create()
        resp = await client.post(f"{API_PREFIX}/guideline-trackers", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["guideline_name"] == "Test Guideline"
        assert data["compliance_gap_identified"] is False
        assert data["id"].startswith("GT-")

    @pytest.mark.anyio
    async def test_update_guideline_tracker(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/guideline-trackers/GT-006",
            json={
                "compliance_gap_identified": True,
                "remediation_plan": "Update training materials",
                "reviewed_by": "Dr. Reviewer",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["compliance_gap_identified"] is True
        assert data["remediation_plan"] == "Update training materials"
        assert data["reviewed_by"] == "Dr. Reviewer"

    @pytest.mark.anyio
    async def test_update_guideline_tracker_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/guideline-trackers/GT-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_guideline_tracker(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/guideline-trackers/GT-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/guideline-trackers/GT-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_guideline_tracker_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/guideline-trackers/GT-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# AUTHORITY COMMUNICATION CRUD
# =====================================================================


class TestAuthorityCommunicationCrud:
    """Test authority communication CRUD operations."""

    @pytest.mark.anyio
    async def test_list_authority_communications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authority-communications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_authority_communications_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/authority-communications", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_authority_communications_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/authority-communications",
            params={"communication_type": "type_b_meeting"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["communication_type"] == "type_b_meeting"

    @pytest.mark.anyio
    async def test_list_authority_communications_filter_region(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/authority-communications", params={"region": "eu_ema"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["region"] == "eu_ema"

    @pytest.mark.anyio
    async def test_get_authority_communication(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authority-communications/AC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "AC-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["communication_type"] == "type_b_meeting"

    @pytest.mark.anyio
    async def test_get_authority_communication_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authority-communications/AC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_authority_communication(self, client: AsyncClient):
        payload = _make_authority_communication_create()
        resp = await client.post(f"{API_PREFIX}/authority-communications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["communication_type"] == "type_b_meeting"
        assert data["questions_submitted"] == 0
        assert data["outcome_favorable"] is None
        assert data["id"].startswith("AC-")

    @pytest.mark.anyio
    async def test_update_authority_communication(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/authority-communications/AC-006",
            json={
                "outcome_favorable": True,
                "questions_answered": 5,
                "meeting_minutes_filed": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome_favorable"] is True
        assert data["questions_answered"] == 5
        assert data["meeting_minutes_filed"] is True

    @pytest.mark.anyio
    async def test_update_authority_communication_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/authority-communications/AC-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_authority_communication(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/authority-communications/AC-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/authority-communications/AC-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_authority_communication_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/authority-communications/AC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# IMPACT ASSESSMENT CRUD
# =====================================================================


class TestImpactAssessmentCrud:
    """Test impact assessment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_impact_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/impact-assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_impact_assessments_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/impact-assessments", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_impact_assessments_filter_impact_level(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/impact-assessments", params={"impact_level": "high"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["impact_level"] == "high"

    @pytest.mark.anyio
    async def test_get_impact_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/impact-assessments/IA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "IA-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["impact_level"] == "high"

    @pytest.mark.anyio
    async def test_get_impact_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/impact-assessments/IA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_impact_assessment(self, client: AsyncClient):
        payload = _make_impact_assessment_create()
        resp = await client.post(f"{API_PREFIX}/impact-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["impact_level"] == "moderate"
        assert data["protocol_change_needed"] is False
        assert data["stakeholders_notified"] is False
        assert data["id"].startswith("IA-")

    @pytest.mark.anyio
    async def test_create_impact_assessment_with_intelligence_id(self, client: AsyncClient):
        payload = _make_impact_assessment_create(intelligence_id="LM-001")
        resp = await client.post(f"{API_PREFIX}/impact-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["intelligence_id"] == "LM-001"

    @pytest.mark.anyio
    async def test_create_impact_assessment_with_guideline_id(self, client: AsyncClient):
        payload = _make_impact_assessment_create(guideline_id="GT-001")
        resp = await client.post(f"{API_PREFIX}/impact-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["guideline_id"] == "GT-001"

    @pytest.mark.anyio
    async def test_update_impact_assessment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/impact-assessments/IA-007",
            json={
                "impact_level": "critical",
                "stakeholders_notified": True,
                "approved_by": "VP Regulatory",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["impact_level"] == "critical"
        assert data["stakeholders_notified"] is True
        assert data["approved_by"] == "VP Regulatory"

    @pytest.mark.anyio
    async def test_update_impact_assessment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/impact-assessments/IA-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_impact_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/impact-assessments/IA-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/impact-assessments/IA-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_impact_assessment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/impact-assessments/IA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# COMPLIANCE ALERT CRUD
# =====================================================================


class TestComplianceAlertCrud:
    """Test compliance alert CRUD operations."""

    @pytest.mark.anyio
    async def test_list_compliance_alerts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_compliance_alerts_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compliance-alerts", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_compliance_alerts_filter_severity(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compliance-alerts", params={"severity": "emergency"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["severity"] == "emergency"

    @pytest.mark.anyio
    async def test_list_compliance_alerts_filter_region(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compliance-alerts", params={"region": "us_fda"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["region"] == "us_fda"

    @pytest.mark.anyio
    async def test_list_compliance_alerts_filter_resolved(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compliance-alerts", params={"resolved": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["resolved"] is True

    @pytest.mark.anyio
    async def test_list_compliance_alerts_filter_unresolved(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compliance-alerts", params={"resolved": False}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["resolved"] is False

    @pytest.mark.anyio
    async def test_get_compliance_alert(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-alerts/CA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CA-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["severity"] == "action_required"

    @pytest.mark.anyio
    async def test_get_compliance_alert_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-alerts/CA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_compliance_alert(self, client: AsyncClient):
        payload = _make_compliance_alert_create()
        resp = await client.post(f"{API_PREFIX}/compliance-alerts", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["severity"] == "warning"
        assert data["acknowledged"] is False
        assert data["resolved"] is False
        assert data["id"].startswith("CA-")

    @pytest.mark.anyio
    async def test_create_compliance_alert_with_source(self, client: AsyncClient):
        payload = _make_compliance_alert_create(source_intelligence_id="LM-001")
        resp = await client.post(f"{API_PREFIX}/compliance-alerts", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["source_intelligence_id"] == "LM-001"

    @pytest.mark.anyio
    async def test_update_compliance_alert(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/compliance-alerts/CA-005",
            json={
                "acknowledged": True,
                "acknowledged_by": "Dr. Acknowledger",
                "resolved": True,
                "resolution_details": "Audit completed successfully",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["acknowledged"] is True
        assert data["acknowledged_by"] == "Dr. Acknowledger"
        assert data["resolved"] is True
        assert data["resolution_details"] == "Audit completed successfully"

    @pytest.mark.anyio
    async def test_update_compliance_alert_severity(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/compliance-alerts/CA-004",
            json={"severity": "action_required"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["severity"] == "action_required"

    @pytest.mark.anyio
    async def test_update_compliance_alert_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/compliance-alerts/CA-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_compliance_alert(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/compliance-alerts/CA-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/compliance-alerts/CA-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_compliance_alert_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/compliance-alerts/CA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestRegulatoryIntelligenceMetrics:
    """Test regulatory intelligence metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_intelligence_items"] == 12
        assert data["total_guidelines"] == 12
        assert data["total_communications"] == 12
        assert data["total_impact_assessments"] == 12
        assert data["total_alerts"] == 12

    @pytest.mark.anyio
    async def test_metrics_items_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_type = data["items_by_type"]
        total = sum(by_type.values())
        assert total == data["total_intelligence_items"]

    @pytest.mark.anyio
    async def test_metrics_items_by_region(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_region = data["items_by_region"]
        total = sum(by_region.values())
        assert total == data["total_intelligence_items"]

    @pytest.mark.anyio
    async def test_metrics_items_by_impact(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_impact = data["items_by_impact"]
        total = sum(by_impact.values())
        assert total == data["total_intelligence_items"]

    @pytest.mark.anyio
    async def test_metrics_unanalyzed_items(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["unanalyzed_items"] > 0
        assert data["unanalyzed_items"] <= data["total_intelligence_items"]

    @pytest.mark.anyio
    async def test_metrics_guidelines_with_gaps(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["guidelines_with_gaps"] > 0
        assert data["guidelines_with_gaps"] <= data["total_guidelines"]

    @pytest.mark.anyio
    async def test_metrics_communications_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_type = data["communications_by_type"]
        total = sum(by_type.values())
        assert total == data["total_communications"]

    @pytest.mark.anyio
    async def test_metrics_favorable_outcomes(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["favorable_outcomes"] > 0
        assert data["favorable_outcomes"] <= data["total_communications"]

    @pytest.mark.anyio
    async def test_metrics_high_impact_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["high_impact_assessments"] > 0
        assert data["high_impact_assessments"] <= data["total_impact_assessments"]

    @pytest.mark.anyio
    async def test_metrics_alerts_by_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_severity = data["alerts_by_severity"]
        total = sum(by_severity.values())
        assert total == data["total_alerts"]

    @pytest.mark.anyio
    async def test_metrics_unresolved_alerts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["unresolved_alerts"] > 0
        assert data["unresolved_alerts"] <= data["total_alerts"]

    def test_metrics_via_service(self, svc: RegulatoryIntelligenceHubService):
        metrics = svc.get_metrics()
        assert metrics.total_intelligence_items == 12
        assert metrics.total_guidelines == 12
        assert metrics.total_communications == 12
        assert metrics.total_impact_assessments == 12
        assert metrics.total_alerts == 12


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_regulatory_intelligence_hub_service()
        svc2 = get_regulatory_intelligence_hub_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_regulatory_intelligence_hub_service()
        svc2 = reset_regulatory_intelligence_hub_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_regulatory_intelligence_hub_service()
        # Delete a monitor
        svc.delete_landscape_monitor("LM-001")
        assert svc.get_landscape_monitor("LM-001") is None
        # Reset should bring it back
        svc2 = reset_regulatory_intelligence_hub_service()
        assert svc2.get_landscape_monitor("LM-001") is not None


# =====================================================================
# FILTERING AND EDGE CASES
# =====================================================================


class TestFilteringAndEdgeCases:
    """Test filtering combinations and edge cases."""

    @pytest.mark.anyio
    async def test_list_monitors_empty_filter(self, client: AsyncClient):
        """Filter by a trial that has no monitors."""
        resp = await client.get(
            f"{API_PREFIX}/landscape-monitors",
            params={"trial_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_list_guidelines_empty_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/guideline-trackers",
            params={"compliance_gap_identified": True, "region": "china_nmpa"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Only GT-012 is NMPA with gap
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_list_alerts_combined_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compliance-alerts",
            params={"severity": "emergency", "resolved": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["severity"] == "emergency"
            assert item["resolved"] is False

    @pytest.mark.anyio
    async def test_create_monitor_then_retrieve(self, client: AsyncClient):
        """Create a monitor and verify it shows in the list."""
        payload = _make_landscape_monitor_create()
        resp = await client.post(f"{API_PREFIX}/landscape-monitors", json=payload)
        assert resp.status_code == 201
        created_id = resp.json()["id"]

        resp2 = await client.get(f"{API_PREFIX}/landscape-monitors/{created_id}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == created_id

    @pytest.mark.anyio
    async def test_create_alert_then_acknowledge_and_resolve(self, client: AsyncClient):
        """Create an alert, then acknowledge and resolve it."""
        payload = _make_compliance_alert_create()
        resp = await client.post(f"{API_PREFIX}/compliance-alerts", json=payload)
        assert resp.status_code == 201
        alert_id = resp.json()["id"]
        assert resp.json()["acknowledged"] is False
        assert resp.json()["resolved"] is False

        # Acknowledge
        resp2 = await client.put(
            f"{API_PREFIX}/compliance-alerts/{alert_id}",
            json={"acknowledged": True, "acknowledged_by": "Dr. Reviewer"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["acknowledged"] is True
        assert resp2.json()["acknowledged_by"] == "Dr. Reviewer"

        # Resolve
        resp3 = await client.put(
            f"{API_PREFIX}/compliance-alerts/{alert_id}",
            json={"resolved": True, "resolution_details": "Issue addressed"},
        )
        assert resp3.status_code == 200
        assert resp3.json()["resolved"] is True
        assert resp3.json()["resolution_details"] == "Issue addressed"

    @pytest.mark.anyio
    async def test_create_and_delete_guideline_tracker(self, client: AsyncClient):
        """Create a guideline tracker and then delete it."""
        payload = _make_guideline_tracker_create()
        resp = await client.post(f"{API_PREFIX}/guideline-trackers", json=payload)
        assert resp.status_code == 201
        tracker_id = resp.json()["id"]

        resp2 = await client.delete(f"{API_PREFIX}/guideline-trackers/{tracker_id}")
        assert resp2.status_code == 204

        resp3 = await client.get(f"{API_PREFIX}/guideline-trackers/{tracker_id}")
        assert resp3.status_code == 404

    @pytest.mark.anyio
    async def test_create_communication_then_update(self, client: AsyncClient):
        """Create a communication and update its outcome."""
        payload = _make_authority_communication_create()
        resp = await client.post(f"{API_PREFIX}/authority-communications", json=payload)
        assert resp.status_code == 201
        comm_id = resp.json()["id"]
        assert resp.json()["outcome_favorable"] is None

        resp2 = await client.put(
            f"{API_PREFIX}/authority-communications/{comm_id}",
            json={"outcome_favorable": True, "meeting_minutes_filed": True},
        )
        assert resp2.status_code == 200
        assert resp2.json()["outcome_favorable"] is True
        assert resp2.json()["meeting_minutes_filed"] is True

    @pytest.mark.anyio
    async def test_monitors_sorted_by_publication_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/landscape-monitors")
        data = resp.json()
        dates = [item["publication_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_guidelines_sorted_by_effective_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/guideline-trackers")
        data = resp.json()
        dates = [item["effective_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_communications_sorted_by_communication_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authority-communications")
        data = resp.json()
        dates = [item["communication_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_assessments_sorted_by_assessment_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/impact-assessments")
        data = resp.json()
        dates = [item["assessment_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_alerts_sorted_by_alert_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-alerts")
        data = resp.json()
        dates = [item["alert_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_metrics_after_create_and_delete(self, client: AsyncClient):
        """Metrics should reflect dynamic changes."""
        # Get baseline metrics
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        baseline = resp1.json()

        # Create a new monitor
        payload = _make_landscape_monitor_create()
        await client.post(f"{API_PREFIX}/landscape-monitors", json=payload)

        resp2 = await client.get(f"{API_PREFIX}/metrics")
        after_create = resp2.json()
        assert after_create["total_intelligence_items"] == baseline["total_intelligence_items"] + 1

        # Delete a monitor
        await client.delete(f"{API_PREFIX}/landscape-monitors/LM-012")
        resp3 = await client.get(f"{API_PREFIX}/metrics")
        after_delete = resp3.json()
        assert after_delete["total_intelligence_items"] == baseline["total_intelligence_items"]


# =====================================================================
# ENUM COVERAGE
# =====================================================================


class TestEnumCoverage:
    """Verify enum values are represented in seed data."""

    @pytest.mark.anyio
    async def test_intelligence_types_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/landscape-monitors")
        data = resp.json()
        types = {item["intelligence_type"] for item in data["items"]}
        assert "guidance_update" in types
        assert "regulation_change" in types
        assert "policy_shift" in types
        assert "enforcement_action" in types
        assert "advisory_notice" in types
        assert "industry_trend" in types

    @pytest.mark.anyio
    async def test_regions_in_seed_monitors(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/landscape-monitors")
        data = resp.json()
        regions = {item["region"] for item in data["items"]}
        assert "us_fda" in regions
        assert "eu_ema" in regions
        assert "uk_mhra" in regions
        assert "japan_pmda" in regions
        assert "china_nmpa" in regions
        assert "global" in regions

    @pytest.mark.anyio
    async def test_impact_levels_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/landscape-monitors")
        data = resp.json()
        levels = {item["impact_level"] for item in data["items"]}
        assert "low" in levels
        assert "moderate" in levels
        assert "high" in levels
        assert "critical" in levels

    @pytest.mark.anyio
    async def test_communication_types_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/authority-communications")
        data = resp.json()
        types = {item["communication_type"] for item in data["items"]}
        assert "written_inquiry" in types
        assert "pre_submission" in types
        assert "type_a_meeting" in types
        assert "type_b_meeting" in types
        assert "type_c_meeting" in types
        assert "scientific_advice" in types

    @pytest.mark.anyio
    async def test_alert_severities_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-alerts")
        data = resp.json()
        severities = {item["severity"] for item in data["items"]}
        assert "informational" in severities
        assert "warning" in severities
        assert "action_required" in severities
        assert "urgent" in severities
        assert "emergency" in severities

    @pytest.mark.anyio
    async def test_regions_in_seed_guidelines(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/guideline-trackers")
        data = resp.json()
        regions = {item["region"] for item in data["items"]}
        assert "global" in regions
        assert "us_fda" in regions
        assert "eu_ema" in regions
        assert "japan_pmda" in regions
        assert "china_nmpa" in regions

    @pytest.mark.anyio
    async def test_impact_levels_in_seed_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/impact-assessments")
        data = resp.json()
        levels = {item["impact_level"] for item in data["items"]}
        assert "low" in levels
        assert "moderate" in levels
        assert "high" in levels
        assert "critical" in levels
