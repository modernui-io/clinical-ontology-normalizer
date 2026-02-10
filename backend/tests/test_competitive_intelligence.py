"""Tests for Competitive Intelligence (CI-INTEL) module.

Covers:
- Seed data verification (programs, market intel, patents, conference intel, alerts)
- Competitor Program CRUD (create, read, update, delete, list, filters)
- Market Intelligence CRUD (create, read, update, delete, list, filters)
- Patent Landscape CRUD (create, read, update, delete, list, filters)
- Conference Intelligence CRUD (create, read, update, delete, list, filters)
- Competitive Alerts CRUD (create, read, update, delete, list, filters, acknowledge)
- Metrics computation
- Error handling (404s)
- Edge cases
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.competitive_intelligence_service import (
    CompetitiveIntelligenceService,
    get_competitive_intelligence_service,
    reset_competitive_intelligence_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1/competitive-intelligence"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_competitive_intelligence_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> CompetitiveIntelligenceService:
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


def _make_program_create(**overrides) -> dict:
    defaults = {
        "competitor_name": "Test Pharma",
        "drug_name": "Testinib",
        "mechanism_of_action": "Kinase inhibitor",
        "therapeutic_area": "Oncology",
        "indication": "NSCLC",
        "status": "phase_iii",
        "threat_level": "moderate",
        "our_competing_program": "Libtayo (cemiplimab)",
        "key_differentiators": ["Novel MOA", "Oral administration"],
        "notes": "Monitoring Phase III results",
    }
    defaults.update(overrides)
    return defaults


def _make_market_intel_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "source": "press_release",
        "title": "Test Competitor Earnings Report",
        "summary": "Competitor reported strong Q4 revenue growth in key therapeutic areas.",
        "competitor_name": "Test Pharma",
        "therapeutic_area": "Oncology",
        "event_date": now.isoformat(),
        "impact_assessment": "Moderate competitive impact expected.",
        "threat_level": "moderate",
        "source_url": "https://example.com/report",
        "analyzed_by": "Test Analyst",
    }
    defaults.update(overrides)
    return defaults


def _make_patent_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "patent_number": "US99,999,999",
        "title": "Test Patent for Novel Antibody",
        "assignee": "Test Pharma",
        "filing_date": now.isoformat(),
        "status": "filed",
        "therapeutic_area": "Oncology",
        "claims_summary": "Claims covering novel antibody formulations.",
        "relevance_to_portfolio": "Low relevance to current portfolio.",
    }
    defaults.update(overrides)
    return defaults


def _make_conference_intel_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "conference_name": "Test Medical Conference 2026",
        "conference_type": "medical",
        "conference_date": now.isoformat(),
        "location": "New York, NY",
        "presentation_title": "Phase III Results for Testinib",
        "presenter": "Dr. Test Presenter",
        "company": "Test Pharma",
        "therapeutic_area": "Oncology",
        "key_findings": ["Primary endpoint met", "Favorable safety profile"],
        "competitive_implications": "Potential new entrant in IO space.",
        "threat_level": "moderate",
        "attended_by": "Medical Affairs Team",
    }
    defaults.update(overrides)
    return defaults


def _make_alert_create(**overrides) -> dict:
    defaults = {
        "title": "Test Competitive Alert",
        "description": "A test competitive alert for monitoring purposes.",
        "competitor_name": "Test Pharma",
        "therapeutic_area": "Oncology",
        "priority": "high",
        "source": "press_release",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_programs_count(self, svc: CompetitiveIntelligenceService):
        programs = svc.list_competitor_programs()
        assert len(programs) == 12

    def test_seed_programs_have_regeneron_competitors(self, svc: CompetitiveIntelligenceService):
        programs = svc.list_competitor_programs()
        our_programs = {p.our_competing_program for p in programs if p.our_competing_program}
        assert any("EYLEA" in p for p in our_programs)
        assert any("Dupixent" in p for p in our_programs)
        assert any("Libtayo" in p for p in our_programs)

    def test_seed_market_intel_count(self, svc: CompetitiveIntelligenceService):
        intel = svc.list_market_intelligence()
        assert len(intel) == 5

    def test_seed_patents_count(self, svc: CompetitiveIntelligenceService):
        patents = svc.list_patents()
        assert len(patents) == 4

    def test_seed_conference_intel_count(self, svc: CompetitiveIntelligenceService):
        conferences = svc.list_conference_intelligence()
        assert len(conferences) == 4

    def test_seed_alerts_count(self, svc: CompetitiveIntelligenceService):
        alerts = svc.list_alerts()
        assert len(alerts) == 5

    def test_seed_has_critical_threat(self, svc: CompetitiveIntelligenceService):
        from app.schemas.competitive_intelligence import ThreatLevel
        programs = svc.list_competitor_programs(threat_level=ThreatLevel.CRITICAL)
        assert len(programs) >= 1

    def test_seed_has_unacknowledged_alerts(self, svc: CompetitiveIntelligenceService):
        alerts = svc.list_alerts(acknowledged=False)
        assert len(alerts) >= 1

    def test_seed_has_acknowledged_alerts(self, svc: CompetitiveIntelligenceService):
        alerts = svc.list_alerts(acknowledged=True)
        assert len(alerts) >= 1

    def test_seed_program_fields(self, svc: CompetitiveIntelligenceService):
        program = svc.get_competitor_program("CP-001")
        assert program is not None
        assert program.competitor_name == "Roche/Genentech"
        assert program.drug_name == "Vabysmo (faricimab)"
        assert program.therapeutic_area == "Ophthalmology"


# =====================================================================
# COMPETITOR PROGRAM CRUD
# =====================================================================


class TestCompetitorProgramCrud:
    """Test competitor program CRUD operations."""

    @pytest.mark.anyio
    async def test_list_programs(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/programs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_programs_filter_therapeutic_area(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/programs",
            params={"therapeutic_area": "Ophthalmology"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["therapeutic_area"] == "Ophthalmology"

    @pytest.mark.anyio
    async def test_list_programs_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/programs",
            params={"status": "approved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "approved"

    @pytest.mark.anyio
    async def test_list_programs_filter_threat_level(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/programs",
            params={"threat_level": "critical"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["threat_level"] == "critical"

    @pytest.mark.anyio
    async def test_get_program(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/programs/CP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CP-001"
        assert data["competitor_name"] == "Roche/Genentech"

    @pytest.mark.anyio
    async def test_get_program_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/programs/CP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_program(self, client: AsyncClient):
        payload = _make_program_create()
        resp = await client.post(f"{API_PREFIX}/programs", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["drug_name"] == "Testinib"
        assert data["id"].startswith("CP-")
        assert data["status"] == "phase_iii"

    @pytest.mark.anyio
    async def test_update_program(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/programs/CP-001",
            json={"threat_level": "high", "notes": "Updated threat assessment"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["threat_level"] == "high"
        assert data["notes"] == "Updated threat assessment"

    @pytest.mark.anyio
    async def test_update_program_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/programs/CP-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_program(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/programs/CP-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/programs/CP-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_program_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/programs/CP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# MARKET INTELLIGENCE CRUD
# =====================================================================


class TestMarketIntelligenceCrud:
    """Test market intelligence CRUD operations."""

    @pytest.mark.anyio
    async def test_list_market_intel(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/market-intel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_market_intel_filter_source(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/market-intel",
            params={"source": "sec_filing"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["source"] == "sec_filing"

    @pytest.mark.anyio
    async def test_list_market_intel_filter_threat_level(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/market-intel",
            params={"threat_level": "high"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["threat_level"] == "high"

    @pytest.mark.anyio
    async def test_get_market_intel(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/market-intel/MI-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MI-001"
        assert data["source"] == "sec_filing"

    @pytest.mark.anyio
    async def test_get_market_intel_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/market-intel/MI-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_market_intel(self, client: AsyncClient):
        payload = _make_market_intel_create()
        resp = await client.post(f"{API_PREFIX}/market-intel", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Competitor Earnings Report"
        assert data["id"].startswith("MI-")

    @pytest.mark.anyio
    async def test_update_market_intel(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/market-intel/MI-001",
            json={"threat_level": "critical", "action_required": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["threat_level"] == "critical"
        assert data["action_required"] is True

    @pytest.mark.anyio
    async def test_update_market_intel_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/market-intel/MI-NONEXISTENT",
            json={"title": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_market_intel(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/market-intel/MI-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/market-intel/MI-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_market_intel_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/market-intel/MI-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# PATENT LANDSCAPE CRUD
# =====================================================================


class TestPatentLandscapeCrud:
    """Test patent landscape CRUD operations."""

    @pytest.mark.anyio
    async def test_list_patents(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4

    @pytest.mark.anyio
    async def test_list_patents_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/patents",
            params={"status": "granted"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "granted"

    @pytest.mark.anyio
    async def test_list_patents_filter_therapeutic_area(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/patents",
            params={"therapeutic_area": "Ophthalmology"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["therapeutic_area"] == "Ophthalmology"

    @pytest.mark.anyio
    async def test_get_patent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patents/PAT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PAT-001"
        assert data["assignee"] == "Roche/Genentech"

    @pytest.mark.anyio
    async def test_get_patent_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patents/PAT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_patent(self, client: AsyncClient):
        payload = _make_patent_create()
        resp = await client.post(f"{API_PREFIX}/patents", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patent_number"] == "US99,999,999"
        assert data["id"].startswith("PAT-")

    @pytest.mark.anyio
    async def test_update_patent(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/patents/PAT-003",
            json={"status": "published", "reviewed_by": "IP Counsel"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "published"
        assert data["reviewed_by"] == "IP Counsel"

    @pytest.mark.anyio
    async def test_update_patent_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/patents/PAT-NONEXISTENT",
            json={"status": "granted"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_patent(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/patents/PAT-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/patents/PAT-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_patent_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/patents/PAT-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CONFERENCE INTELLIGENCE CRUD
# =====================================================================


class TestConferenceIntelligenceCrud:
    """Test conference intelligence CRUD operations."""

    @pytest.mark.anyio
    async def test_list_conference_intel(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/conference-intel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4

    @pytest.mark.anyio
    async def test_list_conference_intel_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/conference-intel",
            params={"conference_type": "medical"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["conference_type"] == "medical"

    @pytest.mark.anyio
    async def test_list_conference_intel_filter_threat_level(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/conference-intel",
            params={"threat_level": "high"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["threat_level"] == "high"

    @pytest.mark.anyio
    async def test_get_conference_intel(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/conference-intel/CI-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CI-001"
        assert data["conference_name"] == "AAO 2025 Annual Meeting"

    @pytest.mark.anyio
    async def test_get_conference_intel_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/conference-intel/CI-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_conference_intel(self, client: AsyncClient):
        payload = _make_conference_intel_create()
        resp = await client.post(f"{API_PREFIX}/conference-intel", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["conference_name"] == "Test Medical Conference 2026"
        assert data["id"].startswith("CI-")

    @pytest.mark.anyio
    async def test_update_conference_intel(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/conference-intel/CI-001",
            json={"threat_level": "critical", "key_findings": ["Updated finding 1"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["threat_level"] == "critical"
        assert data["key_findings"] == ["Updated finding 1"]

    @pytest.mark.anyio
    async def test_update_conference_intel_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/conference-intel/CI-NONEXISTENT",
            json={"threat_level": "high"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_conference_intel(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/conference-intel/CI-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/conference-intel/CI-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_conference_intel_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/conference-intel/CI-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# COMPETITIVE ALERTS CRUD
# =====================================================================


class TestCompetitiveAlertsCrud:
    """Test competitive alert CRUD operations."""

    @pytest.mark.anyio
    async def test_list_alerts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_alerts_filter_priority(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/alerts",
            params={"priority": "urgent"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["priority"] == "urgent"

    @pytest.mark.anyio
    async def test_list_alerts_filter_acknowledged(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/alerts",
            params={"acknowledged": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["acknowledged"] is False

    @pytest.mark.anyio
    async def test_list_alerts_filter_therapeutic_area(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/alerts",
            params={"therapeutic_area": "Ophthalmology"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["therapeutic_area"] == "Ophthalmology"

    @pytest.mark.anyio
    async def test_get_alert(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts/CA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CA-001"
        assert data["priority"] == "urgent"

    @pytest.mark.anyio
    async def test_get_alert_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts/CA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_alert(self, client: AsyncClient):
        payload = _make_alert_create()
        resp = await client.post(f"{API_PREFIX}/alerts", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Competitive Alert"
        assert data["id"].startswith("CA-")
        assert data["acknowledged"] is False

    @pytest.mark.anyio
    async def test_update_alert(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/alerts/CA-003",
            json={"priority": "urgent", "action_taken": "Reviewed and escalated"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["priority"] == "urgent"
        assert data["action_taken"] == "Reviewed and escalated"

    @pytest.mark.anyio
    async def test_update_alert_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/alerts/CA-NONEXISTENT",
            json={"priority": "high"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_acknowledge_alert(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/alerts/CA-003/acknowledge",
            params={"acknowledged_by": "Test User"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["acknowledged"] is True
        assert data["acknowledged_by"] == "Test User"

    @pytest.mark.anyio
    async def test_acknowledge_alert_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/alerts/CA-NONEXISTENT/acknowledge",
            params={"acknowledged_by": "Test User"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_alert(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/alerts/CA-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/alerts/CA-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_alert_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/alerts/CA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test competitive intelligence metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_competitor_programs"] == 12
        assert data["total_market_intel"] == 5
        assert data["total_patents"] == 4
        assert data["total_conference_intel"] == 4
        assert data["total_alerts"] == 5
        assert data["unacknowledged_alerts"] >= 1
        assert data["high_priority_alerts"] >= 1
        assert data["critical_threats"] >= 1

    def test_metrics_programs_by_status(self, svc: CompetitiveIntelligenceService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.programs_by_status.values())
        assert total_by_status == metrics.total_competitor_programs

    def test_metrics_programs_by_threat_level(self, svc: CompetitiveIntelligenceService):
        metrics = svc.get_metrics()
        total_by_threat = sum(metrics.programs_by_threat_level.values())
        assert total_by_threat == metrics.total_competitor_programs

    def test_metrics_programs_by_therapeutic_area(self, svc: CompetitiveIntelligenceService):
        metrics = svc.get_metrics()
        total_by_area = sum(metrics.programs_by_therapeutic_area.values())
        assert total_by_area == metrics.total_competitor_programs

    def test_metrics_intel_by_source(self, svc: CompetitiveIntelligenceService):
        metrics = svc.get_metrics()
        total_by_source = sum(metrics.intel_by_source.values())
        assert total_by_source == metrics.total_market_intel

    def test_metrics_patents_by_status(self, svc: CompetitiveIntelligenceService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.patents_by_status.values())
        assert total_by_status == metrics.total_patents

    def test_metrics_unacknowledged_alerts_count(self, svc: CompetitiveIntelligenceService):
        metrics = svc.get_metrics()
        actual_unack = len(svc.list_alerts(acknowledged=False))
        assert metrics.unacknowledged_alerts == actual_unack

    def test_metrics_high_priority_count(self, svc: CompetitiveIntelligenceService):
        metrics = svc.get_metrics()
        from app.schemas.competitive_intelligence import AlertPriority
        high = len(svc.list_alerts(priority=AlertPriority.HIGH))
        urgent = len(svc.list_alerts(priority=AlertPriority.URGENT))
        assert metrics.high_priority_alerts == high + urgent


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_competitive_intelligence_service()
        svc2 = get_competitive_intelligence_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_competitive_intelligence_service()
        svc2 = reset_competitive_intelligence_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_competitive_intelligence_service()
        svc.delete_competitor_program("CP-001")
        assert svc.get_competitor_program("CP-001") is None
        svc2 = reset_competitive_intelligence_service()
        assert svc2.get_competitor_program("CP-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_programs_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/programs")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_market_intel_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/market-intel")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_patents_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patents")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_conference_intel_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/conference-intel")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_alerts_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/alerts")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_program_all_statuses(self, client: AsyncClient):
        for status in ["preclinical", "phase_i", "phase_ii", "phase_iii", "submitted", "approved", "withdrawn", "discontinued"]:
            payload = _make_program_create(status=status, drug_name=f"Drug-{status}")
            resp = await client.post(f"{API_PREFIX}/programs", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["status"] == status

    @pytest.mark.anyio
    async def test_create_alert_all_priorities(self, client: AsyncClient):
        for priority in ["low", "medium", "high", "urgent"]:
            payload = _make_alert_create(priority=priority, title=f"Alert-{priority}")
            resp = await client.post(f"{API_PREFIX}/alerts", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["priority"] == priority

    @pytest.mark.anyio
    async def test_create_patent_all_statuses(self, client: AsyncClient):
        for status in ["filed", "published", "granted", "expired", "challenged"]:
            payload = _make_patent_create(status=status, patent_number=f"US-{status}")
            resp = await client.post(f"{API_PREFIX}/patents", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["status"] == status

    @pytest.mark.anyio
    async def test_create_conference_all_types(self, client: AsyncClient):
        for conf_type in ["medical", "scientific", "regulatory", "investor"]:
            payload = _make_conference_intel_create(
                conference_type=conf_type,
                conference_name=f"Conf-{conf_type}",
            )
            resp = await client.post(f"{API_PREFIX}/conference-intel", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["conference_type"] == conf_type

    @pytest.mark.anyio
    async def test_create_market_intel_all_sources(self, client: AsyncClient):
        for source in ["clinical_trials_gov", "sec_filing", "press_release", "conference", "patent_filing", "publication", "analyst_report", "fda_database"]:
            payload = _make_market_intel_create(source=source, title=f"Intel-{source}")
            resp = await client.post(f"{API_PREFIX}/market-intel", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["source"] == source

    @pytest.mark.anyio
    async def test_program_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/programs/CP-001")
        data = resp.json()
        assert "id" in data
        assert "competitor_name" in data
        assert "drug_name" in data
        assert "mechanism_of_action" in data
        assert "therapeutic_area" in data
        assert "indication" in data
        assert "status" in data
        assert "threat_level" in data
        assert "key_differentiators" in data
        assert "last_updated" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_competitor_programs" in data
        assert "programs_by_status" in data
        assert "programs_by_threat_level" in data
        assert "programs_by_therapeutic_area" in data
        assert "total_market_intel" in data
        assert "intel_by_source" in data
        assert "total_patents" in data
        assert "patents_by_status" in data
        assert "total_conference_intel" in data
        assert "total_alerts" in data
        assert "unacknowledged_alerts" in data
        assert "high_priority_alerts" in data
        assert "critical_threats" in data

    @pytest.mark.anyio
    async def test_list_programs_nonexistent_therapeutic_area(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/programs",
            params={"therapeutic_area": "NONEXISTENT"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
