"""Tests for Site Communication (SCM-MGT).

Covers:
- Seed data verification (communication logs, newsletter distributions,
  site query threads, site broadcast alerts)
- Communication log CRUD (create, read, update, delete, list, filter by
  trial/channel/priority/site)
- Newsletter distribution CRUD (create, read, update, delete, list, filter by
  trial/status)
- Site query thread CRUD (create, read, update, delete, list, filter by
  trial/status/site)
- Site broadcast alert CRUD (create, read, update, delete, list, filter by
  trial/level)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.site_communication import (
    AlertLevel,
    CommunicationChannel,
    CommunicationPriority,
    DistributionStatus,
    QueryStatus,
)
from app.services.site_communication_service import (
    SiteCommunicationService,
    get_site_communication_service,
    reset_site_communication_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/site-communication"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_site_communication_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> SiteCommunicationService:
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


def _make_log_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-TEST-001",
        "communication_channel": "email",
        "subject": "Test Communication",
        "summary": "Test communication summary for unit testing.",
        "initiated_by": "Test User",
        "recipient_name": "Test Recipient",
        "communication_date": "2026-01-15T09:00:00Z",
    }
    defaults.update(overrides)
    return defaults


def _make_newsletter_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "newsletter_title": "Test Newsletter",
        "edition_number": "Vol. 1, Issue 1",
        "target_audience": "All Site Staff",
        "authored_by": "Test Author",
        "recipients_count": 25,
    }
    defaults.update(overrides)
    return defaults


def _make_query_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-TEST-001",
        "subject": "Test Query Subject",
        "query_text": "This is a test query for unit testing purposes.",
        "queried_by": "Test Coordinator",
        "query_date": "2026-01-15T09:00:00Z",
    }
    defaults.update(overrides)
    return defaults


def _make_alert_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "alert_level": "advisory",
        "alert_title": "Test Alert Title",
        "alert_message": "This is a test broadcast alert for unit testing.",
        "issued_by": "Test Manager",
        "issued_date": "2026-01-15T09:00:00Z",
        "sites_targeted": 10,
    }
    defaults.update(overrides)
    return defaults


# ===================================================================
# SEED DATA VERIFICATION
# ===================================================================


class TestSeedData:
    """Verify all 4 entity types are seeded with 12 records each."""

    @pytest.mark.anyio
    async def test_seed_communication_logs(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communication-logs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_seed_newsletter_distributions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/newsletter-distributions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_site_query_threads(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-query-threads")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_site_broadcast_alerts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-broadcast-alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12


# ===================================================================
# COMMUNICATION LOGS CRUD
# ===================================================================


class TestCommunicationLogCRUD:
    @pytest.mark.anyio
    async def test_list_communication_logs(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communication-logs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_communication_log(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communication-logs/CML-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CML-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_communication_log_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communication-logs/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_communication_log(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/communication-logs", json=_make_log_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("CML-")
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["communication_channel"] == "email"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/communication-logs")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/communication-logs", json=_make_log_create())
        resp2 = await client.get(f"{API_PREFIX}/communication-logs")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_communication_log(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/communication-logs/CML-001",
            json={"duration_minutes": 30, "notes": "Updated note"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["duration_minutes"] == 30
        assert data["notes"] == "Updated note"

    @pytest.mark.anyio
    async def test_update_communication_log_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/communication-logs/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_communication_log(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/communication-logs/CML-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/communication-logs/CML-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_communication_log_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/communication-logs/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/communication-logs", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_communication_channel(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/communication-logs", params={"communication_channel": "email"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["communication_channel"] == "email"

    @pytest.mark.anyio
    async def test_filter_by_communication_priority(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/communication-logs", params={"communication_priority": "urgent"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["communication_priority"] == "urgent"

    @pytest.mark.anyio
    async def test_filter_by_site_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/communication-logs", params={"site_id": "SITE-NY-001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["site_id"] == "SITE-NY-001"


# ===================================================================
# NEWSLETTER DISTRIBUTIONS CRUD
# ===================================================================


class TestNewsletterDistributionCRUD:
    @pytest.mark.anyio
    async def test_list_newsletter_distributions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/newsletter-distributions")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_newsletter_distribution(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/newsletter-distributions/NWS-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "NWS-001"

    @pytest.mark.anyio
    async def test_get_newsletter_distribution_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/newsletter-distributions/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_newsletter_distribution(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/newsletter-distributions", json=_make_newsletter_create()
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("NWS-")
        assert data["distribution_status"] == "draft"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/newsletter-distributions")
        before = resp1.json()["total"]
        await client.post(
            f"{API_PREFIX}/newsletter-distributions", json=_make_newsletter_create()
        )
        resp2 = await client.get(f"{API_PREFIX}/newsletter-distributions")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_newsletter_distribution(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/newsletter-distributions/NWS-001",
            json={"distribution_status": "sent", "notes": "Distribution complete"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["distribution_status"] == "sent"
        assert data["notes"] == "Distribution complete"

    @pytest.mark.anyio
    async def test_update_newsletter_distribution_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/newsletter-distributions/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_newsletter_distribution(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/newsletter-distributions/NWS-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_newsletter_distribution_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/newsletter-distributions/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_distribution_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/newsletter-distributions",
            params={"distribution_status": "delivered"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["distribution_status"] == "delivered"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/newsletter-distributions", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL


# ===================================================================
# SITE QUERY THREADS CRUD
# ===================================================================


class TestSiteQueryThreadCRUD:
    @pytest.mark.anyio
    async def test_list_site_query_threads(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-query-threads")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_site_query_thread(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-query-threads/SQT-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "SQT-001"

    @pytest.mark.anyio
    async def test_get_site_query_thread_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-query-threads/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_site_query_thread(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/site-query-threads", json=_make_query_create()
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("SQT-")
        assert data["query_status"] == "open"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/site-query-threads")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/site-query-threads", json=_make_query_create())
        resp2 = await client.get(f"{API_PREFIX}/site-query-threads")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_site_query_thread(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-query-threads/SQT-001",
            json={"query_status": "closed", "notes": "Resolved and closed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["query_status"] == "closed"
        assert data["notes"] == "Resolved and closed"

    @pytest.mark.anyio
    async def test_update_site_query_thread_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-query-threads/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_site_query_thread(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/site-query-threads/SQT-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/site-query-threads/SQT-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_site_query_thread_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/site-query-threads/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_query_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-query-threads", params={"query_status": "resolved"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["query_status"] == "resolved"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-query-threads", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_site_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-query-threads", params={"site_id": "SITE-CHI-001"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["site_id"] == "SITE-CHI-001"


# ===================================================================
# SITE BROADCAST ALERTS CRUD
# ===================================================================


class TestSiteBroadcastAlertCRUD:
    @pytest.mark.anyio
    async def test_list_site_broadcast_alerts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-broadcast-alerts")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_site_broadcast_alert(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-broadcast-alerts/SBA-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "SBA-001"

    @pytest.mark.anyio
    async def test_get_site_broadcast_alert_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-broadcast-alerts/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_site_broadcast_alert(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/site-broadcast-alerts", json=_make_alert_create()
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("SBA-")
        assert data["alert_level"] == "advisory"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/site-broadcast-alerts")
        before = resp1.json()["total"]
        await client.post(f"{API_PREFIX}/site-broadcast-alerts", json=_make_alert_create())
        resp2 = await client.get(f"{API_PREFIX}/site-broadcast-alerts")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_site_broadcast_alert(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-broadcast-alerts/SBA-001",
            json={"sites_acknowledged": 15, "notes": "All sites confirmed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sites_acknowledged"] == 15
        assert data["notes"] == "All sites confirmed"

    @pytest.mark.anyio
    async def test_update_site_broadcast_alert_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/site-broadcast-alerts/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_site_broadcast_alert(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/site-broadcast-alerts/SBA-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_site_broadcast_alert_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/site-broadcast-alerts/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_alert_level(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-broadcast-alerts", params={"alert_level": "warning"}
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["alert_level"] == "warning"

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/site-broadcast-alerts", params={"trial_id": LIBTAYO_TRIAL}
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
        assert "total_communications" in data
        assert "total_newsletters" in data
        assert "total_queries" in data
        assert "total_alerts" in data
        assert "avg_newsletter_open_rate" in data
        assert "avg_query_response_hours" in data
        assert "alert_acknowledgment_rate" in data

    @pytest.mark.anyio
    async def test_metrics_total_communications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_communications"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_newsletters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_newsletters"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_queries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_queries"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_alerts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_alerts"] == 12

    @pytest.mark.anyio
    async def test_metrics_has_breakdowns(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert isinstance(data["communications_by_channel"], dict)
        assert isinstance(data["communications_by_priority"], dict)
        assert isinstance(data["newsletters_by_status"], dict)
        assert isinstance(data["queries_by_status"], dict)
        assert isinstance(data["alerts_by_level"], dict)

    def test_metrics_service_level(self, svc: SiteCommunicationService):
        metrics = svc.get_metrics()
        assert metrics.total_communications == 12
        assert metrics.total_newsletters == 12
        assert metrics.total_queries == 12
        assert metrics.total_alerts == 12


# ===================================================================
# EDGE CASES & UPDATE PRESERVATION
# ===================================================================


class TestEdgeCases:
    @pytest.mark.anyio
    async def test_update_log_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communication-logs/CML-001")
        original = resp.json()
        original_channel = original["communication_channel"]

        resp2 = await client.put(
            f"{API_PREFIX}/communication-logs/CML-001",
            json={"notes": "Partial update"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["communication_channel"] == original_channel
        assert updated["notes"] == "Partial update"

    @pytest.mark.anyio
    async def test_update_newsletter_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/newsletter-distributions/NWS-001")
        original = resp.json()
        original_title = original["newsletter_title"]

        resp2 = await client.put(
            f"{API_PREFIX}/newsletter-distributions/NWS-001",
            json={"notes": "Updated newsletter note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["newsletter_title"] == original_title

    @pytest.mark.anyio
    async def test_update_query_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-query-threads/SQT-001")
        original = resp.json()
        original_subject = original["subject"]

        resp2 = await client.put(
            f"{API_PREFIX}/site-query-threads/SQT-001",
            json={"notes": "Updated query note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["subject"] == original_subject

    @pytest.mark.anyio
    async def test_update_alert_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-broadcast-alerts/SBA-001")
        original = resp.json()
        original_title = original["alert_title"]

        resp2 = await client.put(
            f"{API_PREFIX}/site-broadcast-alerts/SBA-001",
            json={"notes": "Updated alert note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["alert_title"] == original_title


# ===================================================================
# SINGLETON PATTERN
# ===================================================================


class TestSingleton:
    def test_get_returns_same_instance(self):
        svc1 = get_site_communication_service()
        svc2 = get_site_communication_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        svc1 = get_site_communication_service()
        svc2 = reset_site_communication_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_site_communication_service()
        svc.delete_communication_log("CML-001")
        assert svc.get_communication_log("CML-001") is None
        svc2 = reset_site_communication_service()
        assert svc2.get_communication_log("CML-001") is not None


# ===================================================================
# SERVICE-LEVEL CRUD
# ===================================================================


class TestServiceLevelCRUD:
    def test_list_communication_logs_service(self, svc: SiteCommunicationService):
        items = svc.list_communication_logs()
        assert len(items) == 12

    def test_get_communication_log_service(self, svc: SiteCommunicationService):
        record = svc.get_communication_log("CML-001")
        assert record is not None
        assert record.id == "CML-001"

    def test_list_newsletter_distributions_service(self, svc: SiteCommunicationService):
        items = svc.list_newsletter_distributions()
        assert len(items) == 12

    def test_get_newsletter_distribution_service(self, svc: SiteCommunicationService):
        record = svc.get_newsletter_distribution("NWS-001")
        assert record is not None
        assert record.id == "NWS-001"

    def test_list_site_query_threads_service(self, svc: SiteCommunicationService):
        items = svc.list_site_query_threads()
        assert len(items) == 12

    def test_get_site_query_thread_service(self, svc: SiteCommunicationService):
        record = svc.get_site_query_thread("SQT-001")
        assert record is not None
        assert record.id == "SQT-001"

    def test_list_site_broadcast_alerts_service(self, svc: SiteCommunicationService):
        items = svc.list_site_broadcast_alerts()
        assert len(items) == 12

    def test_get_site_broadcast_alert_service(self, svc: SiteCommunicationService):
        record = svc.get_site_broadcast_alert("SBA-001")
        assert record is not None
        assert record.id == "SBA-001"

    def test_delete_communication_log_service(self, svc: SiteCommunicationService):
        assert svc.delete_communication_log("CML-001") is True
        assert svc.get_communication_log("CML-001") is None

    def test_delete_nonexistent_returns_false(self, svc: SiteCommunicationService):
        assert svc.delete_communication_log("NONEXISTENT") is False

    def test_filter_logs_by_trial(self, svc: SiteCommunicationService):
        items = svc.list_communication_logs(trial_id=EYLEA_TRIAL)
        for item in items:
            assert item.trial_id == EYLEA_TRIAL

    def test_filter_logs_by_channel(self, svc: SiteCommunicationService):
        items = svc.list_communication_logs(communication_channel=CommunicationChannel.EMAIL)
        for item in items:
            assert item.communication_channel == CommunicationChannel.EMAIL

    def test_filter_newsletters_by_status(self, svc: SiteCommunicationService):
        items = svc.list_newsletter_distributions(distribution_status=DistributionStatus.DELIVERED)
        for item in items:
            assert item.distribution_status == DistributionStatus.DELIVERED

    def test_filter_queries_by_status(self, svc: SiteCommunicationService):
        items = svc.list_site_query_threads(query_status=QueryStatus.RESOLVED)
        for item in items:
            assert item.query_status == QueryStatus.RESOLVED

    def test_filter_alerts_by_level(self, svc: SiteCommunicationService):
        items = svc.list_site_broadcast_alerts(alert_level=AlertLevel.WARNING)
        for item in items:
            assert item.alert_level == AlertLevel.WARNING


# ===================================================================
# BULK / MULTI-ENTITY
# ===================================================================


class TestBulkOperations:
    @pytest.mark.anyio
    async def test_create_multiple_communication_logs(self, client: AsyncClient):
        for i in range(3):
            resp = await client.post(
                f"{API_PREFIX}/communication-logs",
                json=_make_log_create(subject=f"Bulk Log {i}"),
            )
            assert resp.status_code == 201
        resp = await client.get(f"{API_PREFIX}/communication-logs")
        assert resp.json()["total"] == 15  # 12 seed + 3 new

    @pytest.mark.anyio
    async def test_delete_multiple_alerts(self, client: AsyncClient):
        for alert_id in ["SBA-001", "SBA-002", "SBA-003"]:
            resp = await client.delete(f"{API_PREFIX}/site-broadcast-alerts/{alert_id}")
            assert resp.status_code == 204
        resp = await client.get(f"{API_PREFIX}/site-broadcast-alerts")
        assert resp.json()["total"] == 9  # 12 seed - 3 deleted


# ===================================================================
# RESPONSE STRUCTURE
# ===================================================================


class TestAPIResponseStructure:
    @pytest.mark.anyio
    async def test_communication_log_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communication-logs/CML-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "site_id", "communication_channel",
            "communication_priority", "subject", "summary",
            "initiated_by", "recipient_name", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_newsletter_distribution_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/newsletter-distributions/NWS-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "newsletter_title", "edition_number",
            "distribution_status", "target_audience", "authored_by", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_site_query_thread_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-query-threads/SQT-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "site_id", "query_status",
            "subject", "query_text", "queried_by", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_site_broadcast_alert_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/site-broadcast-alerts/SBA-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "alert_level", "alert_title",
            "alert_message", "issued_by", "sites_targeted", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_list_response_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communication-logs")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
