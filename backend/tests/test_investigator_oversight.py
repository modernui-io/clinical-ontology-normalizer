"""Tests for Investigator Oversight (INV-OVS).

Covers:
- Seed data verification (performances, supervisions, compliance checks, communications)
- Investigator performance CRUD (create, read, update, delete, list, filter by trial/rating/site)
- Site supervision CRUD (create, read, update, delete, list, filter by trial/type/site)
- GCP compliance check CRUD (create, read, update, delete, list, filter by trial/result/site)
- Investigator communication CRUD (create, read, update, delete, list, filter by trial/type/status)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.investigator_oversight import (
    CommunicationStatus,
    CommunicationType,
    ComplianceResult,
    PerformanceRating,
    SupervisionType,
)
from app.services.investigator_oversight_service import (
    InvestigatorOversightService,
    get_investigator_oversight_service,
    reset_investigator_oversight_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/investigator-oversight"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_investigator_oversight_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> InvestigatorOversightService:
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


def _make_performance_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-TEST-001",
        "investigator_name": "Dr. Test Investigator",
        "reviewed_by": "Dr. Test Reviewer",
        "review_period_start": "2026-01-01T00:00:00Z",
        "review_period_end": "2026-06-30T00:00:00Z",
        "enrollment_target": 20,
    }
    defaults.update(overrides)
    return defaults


def _make_supervision_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-TEST-001",
        "supervision_type": "routine_monitoring",
        "visit_date": "2026-01-15T09:00:00Z",
        "monitor_name": "Test Monitor, CRA",
        "duration_hours": 8.0,
    }
    defaults.update(overrides)
    return defaults


def _make_compliance_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-TEST-001",
        "investigator_name": "Dr. Test Investigator",
        "gcp_area": "Informed Consent",
        "check_date": "2026-01-15T09:00:00Z",
        "assessed_by": "QA Test Lead",
    }
    defaults.update(overrides)
    return defaults


def _make_communication_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "communication_type": "protocol_update",
        "subject_line": "Test Communication Subject",
        "content_summary": "Test communication content summary.",
        "sent_by": "Test Sender",
    }
    defaults.update(overrides)
    return defaults


# ===================================================================
# SEED DATA VERIFICATION
# ===================================================================


class TestSeedData:
    """Verify all 4 entity types are seeded with 12 records each."""

    @pytest.mark.anyio
    async def test_seed_performances(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/performances")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_seed_supervisions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/supervisions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_compliance_checks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-checks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_communications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12


# ===================================================================
# INVESTIGATOR PERFORMANCE CRUD
# ===================================================================


class TestInvestigatorPerformanceCRUD:
    @pytest.mark.anyio
    async def test_list_performances(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/performances")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_performance(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/performances/IP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "IP-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_performance_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/performances/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_performance(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/performances", json=_make_performance_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("IP-")
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["performance_rating"] == "not_evaluated"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/performances")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/performances", json=_make_performance_create())
        resp2 = await client.get(f"{API_PREFIX}/performances")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_performance(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/performances/IP-001",
            json={"performance_rating": "meets_expectations", "notes": "Updated review"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["performance_rating"] == "meets_expectations"
        assert data["notes"] == "Updated review"

    @pytest.mark.anyio
    async def test_update_performance_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/performances/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_performance(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/performances/IP-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/performances/IP-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_performance_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/performances/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/performances", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_performance_rating(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/performances", params={"performance_rating": "outstanding"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["performance_rating"] == "outstanding"

    @pytest.mark.anyio
    async def test_filter_by_site_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/performances", params={"site_id": "SITE-NY-001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["site_id"] == "SITE-NY-001"


# ===================================================================
# SITE SUPERVISION CRUD
# ===================================================================


class TestSiteSupervisionCRUD:
    @pytest.mark.anyio
    async def test_list_supervisions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/supervisions")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_supervision(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/supervisions/SS-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "SS-001"

    @pytest.mark.anyio
    async def test_get_supervision_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/supervisions/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_supervision(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/supervisions", json=_make_supervision_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("SS-")
        assert data["supervision_type"] == "routine_monitoring"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/supervisions")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/supervisions", json=_make_supervision_create())
        resp2 = await client.get(f"{API_PREFIX}/supervisions")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_supervision(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/supervisions/SS-001",
            json={"findings_count": 5, "notes": "Updated findings"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["findings_count"] == 5
        assert data["notes"] == "Updated findings"

    @pytest.mark.anyio
    async def test_update_supervision_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/supervisions/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_supervision(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/supervisions/SS-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_supervision_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/supervisions/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_supervision_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/supervisions", params={"supervision_type": "routine_monitoring"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["supervision_type"] == "routine_monitoring"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/supervisions", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_site_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/supervisions", params={"site_id": "SITE-HOU-001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["site_id"] == "SITE-HOU-001"


# ===================================================================
# GCP COMPLIANCE CHECK CRUD
# ===================================================================


class TestGCPComplianceCheckCRUD:
    @pytest.mark.anyio
    async def test_list_compliance_checks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-checks")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_compliance_check(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-checks/GCP-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "GCP-001"

    @pytest.mark.anyio
    async def test_get_compliance_check_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-checks/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_compliance_check(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/compliance-checks", json=_make_compliance_create()
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("GCP-")
        assert data["gcp_area"] == "Informed Consent"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/compliance-checks")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/compliance-checks", json=_make_compliance_create())
        resp2 = await client.get(f"{API_PREFIX}/compliance-checks")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_compliance_check(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/compliance-checks/GCP-001",
            json={"compliance_result": "minor_finding", "notes": "Updated finding"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["compliance_result"] == "minor_finding"
        assert data["notes"] == "Updated finding"

    @pytest.mark.anyio
    async def test_update_compliance_check_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/compliance-checks/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_compliance_check(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/compliance-checks/GCP-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/compliance-checks/GCP-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_compliance_check_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/compliance-checks/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_compliance_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compliance-checks", params={"compliance_result": "compliant"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["compliance_result"] == "compliant"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compliance-checks", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_site_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compliance-checks", params={"site_id": "SITE-NY-001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["site_id"] == "SITE-NY-001"


# ===================================================================
# INVESTIGATOR COMMUNICATION CRUD
# ===================================================================


class TestInvestigatorCommunicationCRUD:
    @pytest.mark.anyio
    async def test_list_communications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_communication(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications/IC-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "IC-001"

    @pytest.mark.anyio
    async def test_get_communication_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_communication(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/communications", json=_make_communication_create()
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("IC-")
        assert data["communication_type"] == "protocol_update"
        assert data["communication_status"] == "draft"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/communications")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/communications", json=_make_communication_create())
        resp2 = await client.get(f"{API_PREFIX}/communications")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_communication(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/communications/IC-001",
            json={"communication_status": "sent", "notes": "Updated status"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["communication_status"] == "sent"
        assert data["notes"] == "Updated status"

    @pytest.mark.anyio
    async def test_update_communication_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/communications/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_communication(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/communications/IC-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/communications/IC-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_communication_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/communications/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_communication_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/communications", params={"communication_type": "safety_alert"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["communication_type"] == "safety_alert"

    @pytest.mark.anyio
    async def test_filter_by_communication_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/communications", params={"communication_status": "acknowledged"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["communication_status"] == "acknowledged"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/communications", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL


# ===================================================================
# METRICS
# ===================================================================


class TestMetrics:
    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_performance_reviews" in data
        assert "reviews_by_rating" in data
        assert "avg_enrollment_achievement_pct" in data
        assert "total_supervisions" in data
        assert "supervisions_by_type" in data
        assert "total_compliance_checks" in data
        assert "checks_by_result" in data
        assert "compliance_rate" in data
        assert "total_communications" in data
        assert "communications_by_type" in data
        assert "communication_acknowledgment_rate" in data

    @pytest.mark.anyio
    async def test_metrics_total_performance_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_performance_reviews"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_supervisions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_supervisions"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_compliance_checks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_compliance_checks"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_communications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_communications"] == 12

    @pytest.mark.anyio
    async def test_metrics_has_breakdowns(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert isinstance(data["reviews_by_rating"], dict)
        assert isinstance(data["supervisions_by_type"], dict)
        assert isinstance(data["checks_by_result"], dict)
        assert isinstance(data["communications_by_type"], dict)

    @pytest.mark.anyio
    async def test_metrics_compliance_rate_range(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0 <= data["compliance_rate"] <= 100

    @pytest.mark.anyio
    async def test_metrics_acknowledgment_rate_range(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0 <= data["communication_acknowledgment_rate"] <= 100

    def test_metrics_service_level(self, svc: InvestigatorOversightService):
        metrics = svc.get_metrics()
        assert metrics.total_performance_reviews == 12
        assert metrics.total_supervisions == 12
        assert metrics.total_compliance_checks == 12
        assert metrics.total_communications == 12


# ===================================================================
# EDGE CASES & UPDATE PRESERVATION
# ===================================================================


class TestEdgeCases:
    @pytest.mark.anyio
    async def test_update_performance_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/performances/IP-001")
        original = resp.json()
        original_name = original["investigator_name"]

        resp2 = await client.put(
            f"{API_PREFIX}/performances/IP-001",
            json={"notes": "Partial update"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["investigator_name"] == original_name
        assert updated["notes"] == "Partial update"

    @pytest.mark.anyio
    async def test_update_supervision_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/supervisions/SS-001")
        original = resp.json()
        original_type = original["supervision_type"]

        resp2 = await client.put(
            f"{API_PREFIX}/supervisions/SS-001",
            json={"notes": "Updated supervision note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["supervision_type"] == original_type

    @pytest.mark.anyio
    async def test_update_compliance_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-checks/GCP-001")
        original = resp.json()
        original_area = original["gcp_area"]

        resp2 = await client.put(
            f"{API_PREFIX}/compliance-checks/GCP-001",
            json={"notes": "Verified compliance"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["gcp_area"] == original_area

    @pytest.mark.anyio
    async def test_update_communication_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications/IC-001")
        original = resp.json()
        original_subject = original["subject_line"]

        resp2 = await client.put(
            f"{API_PREFIX}/communications/IC-001",
            json={"notes": "Updated communication note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["subject_line"] == original_subject


# ===================================================================
# SINGLETON PATTERN
# ===================================================================


class TestSingleton:
    def test_get_returns_same_instance(self):
        svc1 = get_investigator_oversight_service()
        svc2 = get_investigator_oversight_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        svc1 = get_investigator_oversight_service()
        svc2 = reset_investigator_oversight_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_investigator_oversight_service()
        svc.delete_investigator_performance("IP-001")
        assert svc.get_investigator_performance("IP-001") is None
        svc2 = reset_investigator_oversight_service()
        assert svc2.get_investigator_performance("IP-001") is not None


# ===================================================================
# SERVICE-LEVEL CRUD
# ===================================================================


class TestServiceLevelCRUD:
    def test_list_performances_service(self, svc: InvestigatorOversightService):
        items = svc.list_investigator_performances()
        assert len(items) == 12

    def test_get_performance_service(self, svc: InvestigatorOversightService):
        record = svc.get_investigator_performance("IP-001")
        assert record is not None
        assert record.id == "IP-001"

    def test_list_supervisions_service(self, svc: InvestigatorOversightService):
        items = svc.list_site_supervisions()
        assert len(items) == 12

    def test_get_supervision_service(self, svc: InvestigatorOversightService):
        record = svc.get_site_supervision("SS-001")
        assert record is not None
        assert record.id == "SS-001"

    def test_list_compliance_checks_service(self, svc: InvestigatorOversightService):
        items = svc.list_gcp_compliance_checks()
        assert len(items) == 12

    def test_get_compliance_check_service(self, svc: InvestigatorOversightService):
        record = svc.get_gcp_compliance_check("GCP-001")
        assert record is not None
        assert record.id == "GCP-001"

    def test_list_communications_service(self, svc: InvestigatorOversightService):
        items = svc.list_investigator_communications()
        assert len(items) == 12

    def test_get_communication_service(self, svc: InvestigatorOversightService):
        record = svc.get_investigator_communication("IC-001")
        assert record is not None
        assert record.id == "IC-001"

    def test_delete_performance_service(self, svc: InvestigatorOversightService):
        assert svc.delete_investigator_performance("IP-001") is True
        assert svc.get_investigator_performance("IP-001") is None

    def test_delete_nonexistent_returns_false(self, svc: InvestigatorOversightService):
        assert svc.delete_investigator_performance("NONEXISTENT") is False

    def test_filter_performance_by_trial(self, svc: InvestigatorOversightService):
        items = svc.list_investigator_performances(trial_id=EYLEA_TRIAL)
        for item in items:
            assert item.trial_id == EYLEA_TRIAL

    def test_filter_performance_by_rating(self, svc: InvestigatorOversightService):
        items = svc.list_investigator_performances(
            performance_rating=PerformanceRating.OUTSTANDING
        )
        for item in items:
            assert item.performance_rating == PerformanceRating.OUTSTANDING

    def test_filter_supervision_by_type(self, svc: InvestigatorOversightService):
        items = svc.list_site_supervisions(
            supervision_type=SupervisionType.ROUTINE_MONITORING
        )
        for item in items:
            assert item.supervision_type == SupervisionType.ROUTINE_MONITORING

    def test_filter_compliance_by_result(self, svc: InvestigatorOversightService):
        items = svc.list_gcp_compliance_checks(
            compliance_result=ComplianceResult.COMPLIANT
        )
        for item in items:
            assert item.compliance_result == ComplianceResult.COMPLIANT

    def test_filter_communication_by_type(self, svc: InvestigatorOversightService):
        items = svc.list_investigator_communications(
            communication_type=CommunicationType.SAFETY_ALERT
        )
        for item in items:
            assert item.communication_type == CommunicationType.SAFETY_ALERT

    def test_filter_communication_by_status(self, svc: InvestigatorOversightService):
        items = svc.list_investigator_communications(
            communication_status=CommunicationStatus.ACKNOWLEDGED
        )
        for item in items:
            assert item.communication_status == CommunicationStatus.ACKNOWLEDGED


# ===================================================================
# BULK / MULTI-ENTITY
# ===================================================================


class TestBulkOperations:
    @pytest.mark.anyio
    async def test_create_multiple_performances(self, client: AsyncClient):
        for i in range(3):
            resp = await client.post(
                f"{API_PREFIX}/performances",
                json=_make_performance_create(investigator_name=f"Dr. Bulk-{i}"),
            )
            assert resp.status_code == 201
        resp = await client.get(f"{API_PREFIX}/performances")
        assert resp.json()["total"] == 15  # 12 seed + 3 new

    @pytest.mark.anyio
    async def test_delete_multiple_compliance_checks(self, client: AsyncClient):
        for check_id in ["GCP-001", "GCP-002", "GCP-003"]:
            resp = await client.delete(f"{API_PREFIX}/compliance-checks/{check_id}")
            assert resp.status_code == 204
        resp = await client.get(f"{API_PREFIX}/compliance-checks")
        assert resp.json()["total"] == 9  # 12 seed - 3 deleted


# ===================================================================
# RESPONSE STRUCTURE
# ===================================================================


class TestAPIResponseStructure:
    @pytest.mark.anyio
    async def test_performance_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/performances/IP-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "site_id", "investigator_name",
            "performance_rating", "review_period_start", "review_period_end",
            "enrollment_target", "enrollment_actual", "protocol_deviations",
            "query_response_days", "sae_reporting_compliance_pct",
            "training_completion_pct", "reviewed_by", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_supervision_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/supervisions/SS-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "site_id", "supervision_type",
            "visit_date", "monitor_name", "duration_hours",
            "findings_count", "critical_findings", "report_finalized",
            "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_compliance_check_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-checks/GCP-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "site_id", "investigator_name",
            "compliance_result", "check_date", "gcp_area",
            "assessed_by", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_communication_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications/IC-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "communication_type", "communication_status",
            "subject_line", "content_summary", "sent_by", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_list_response_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/performances")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
