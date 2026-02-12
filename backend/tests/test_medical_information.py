"""Tests for Medical Information Services (MED-INFO).

Covers:
- Seed data verification (inquiries, standard responses, FAQs, insights, communications)
- Medical Inquiry CRUD (create, read, update, delete, list, filter by trial/product)
- Standard Response Document CRUD (create, read, update, delete, list, filter)
- Product FAQ CRUD (create, read, update, delete, list, filter)
- Field Medical Insight CRUD (create, read, update, delete, list, filter)
- Scientific Communication CRUD (create, read, update, delete, list, filter)
- Medical information metrics computation
- Error handling (404s)
- Edge cases (filters, empty results)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.medical_information_service import (
    MedicalInformationService,
    get_medical_information_service,
    reset_medical_information_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/medical-information"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_medical_information_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> MedicalInformationService:
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


def _make_inquiry_create(**overrides) -> dict:
    defaults = {
        "product_name": "EYLEA HD",
        "inquiry_source": "healthcare_professional",
        "category": "dosing",
        "question_text": "What is the loading dose for EYLEA HD?",
        "requester_name": "Dr. Test User",
    }
    defaults.update(overrides)
    return defaults


def _make_standard_response_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "product_name": "Dupixent",
        "document_type": "standard_response",
        "title": "Test Standard Response",
        "version": "1.0",
        "content_summary": "Test content summary for standard response document.",
        "category": "dosing",
        "effective_date": now.isoformat(),
        "author": "Dr. Test Author",
    }
    defaults.update(overrides)
    return defaults


def _make_faq_create(**overrides) -> dict:
    defaults = {
        "product_name": "Libtayo",
        "category": "dosing",
        "question": "What is the recommended dose?",
        "answer": "350 mg every 3 weeks.",
        "author": "Medical Information Team",
    }
    defaults.update(overrides)
    return defaults


def _make_insight_create(**overrides) -> dict:
    defaults = {
        "product_name": "EYLEA HD",
        "insight_type": "Unmet Need",
        "description": "Test insight description for field medical observation.",
        "therapeutic_area": "Ophthalmology",
        "source": "KOL Meeting",
        "reported_by": "MSL Dr. Test",
    }
    defaults.update(overrides)
    return defaults


def _make_communication_create(**overrides) -> dict:
    defaults = {
        "product_name": "Dupixent",
        "communication_type": "Medical Letter",
        "title": "Test Communication",
        "audience": "Healthcare Professionals",
        "channel": "Email",
        "content_summary": "Test scientific communication content.",
        "author": "Medical Communications Team",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_inquiries_count(self, svc: MedicalInformationService):
        inquiries = svc.list_inquiries()
        assert len(inquiries) == 12

    def test_seed_standard_responses_count(self, svc: MedicalInformationService):
        responses = svc.list_standard_responses()
        assert len(responses) == 12

    def test_seed_faqs_count(self, svc: MedicalInformationService):
        faqs = svc.list_faqs()
        assert len(faqs) == 12

    def test_seed_insights_count(self, svc: MedicalInformationService):
        insights = svc.list_insights()
        assert len(insights) == 12

    def test_seed_communications_count(self, svc: MedicalInformationService):
        communications = svc.list_communications()
        assert len(communications) == 12

    def test_seed_inquiries_have_all_products(self, svc: MedicalInformationService):
        products = {inq.product_name for inq in svc.list_inquiries()}
        assert "EYLEA HD" in products
        assert "Dupixent" in products
        assert "Libtayo" in products

    def test_seed_inquiries_have_multiple_statuses(self, svc: MedicalInformationService):
        statuses = {inq.status.value for inq in svc.list_inquiries()}
        assert "closed" in statuses
        assert "received" in statuses

    def test_seed_faqs_have_active_and_inactive(self, svc: MedicalInformationService):
        faqs = svc.list_faqs()
        active = [f for f in faqs if f.active]
        inactive = [f for f in faqs if not f.active]
        assert len(active) > 0
        assert len(inactive) > 0

    def test_seed_standard_responses_have_active_and_inactive(self, svc: MedicalInformationService):
        responses = svc.list_standard_responses()
        active = [r for r in responses if r.active]
        inactive = [r for r in responses if not r.active]
        assert len(active) > 0
        assert len(inactive) > 0

    def test_seed_insights_have_actionable(self, svc: MedicalInformationService):
        insights = svc.list_insights()
        actionable = [i for i in insights if i.action_required]
        assert len(actionable) > 0


# =====================================================================
# MEDICAL INQUIRY CRUD
# =====================================================================


class TestInquiryCrud:
    """Test medical inquiry CRUD operations."""

    @pytest.mark.anyio
    async def test_list_inquiries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inquiries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_inquiries_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inquiries", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_inquiries_filter_product(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inquiries", params={"product_name": "Dupixent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["product_name"] == "Dupixent"

    @pytest.mark.anyio
    async def test_get_inquiry(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inquiries/INQ-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "INQ-001"
        assert data["product_name"] == "EYLEA HD"

    @pytest.mark.anyio
    async def test_get_inquiry_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inquiries/INQ-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_inquiry(self, client: AsyncClient):
        payload = _make_inquiry_create()
        resp = await client.post(f"{API_PREFIX}/inquiries", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["product_name"] == "EYLEA HD"
        assert data["status"] == "received"
        assert data["id"].startswith("INQ-")

    @pytest.mark.anyio
    async def test_update_inquiry(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/inquiries/INQ-010",
            json={"status": "response_drafted", "response_text": "Draft response provided."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "response_drafted"
        assert data["response_text"] == "Draft response provided."

    @pytest.mark.anyio
    async def test_update_inquiry_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/inquiries/INQ-NONEXISTENT",
            json={"status": "closed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_inquiry(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/inquiries/INQ-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/inquiries/INQ-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_inquiry_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/inquiries/INQ-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# STANDARD RESPONSE DOCUMENT CRUD
# =====================================================================


class TestStandardResponseCrud:
    """Test standard response document CRUD operations."""

    @pytest.mark.anyio
    async def test_list_standard_responses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/standard-responses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_standard_responses_filter_product(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/standard-responses",
            params={"product_name": "Libtayo"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["product_name"] == "Libtayo"

    @pytest.mark.anyio
    async def test_get_standard_response(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/standard-responses/SRD-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SRD-001"
        assert data["product_name"] == "EYLEA HD"

    @pytest.mark.anyio
    async def test_get_standard_response_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/standard-responses/SRD-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_standard_response(self, client: AsyncClient):
        payload = _make_standard_response_create()
        resp = await client.post(f"{API_PREFIX}/standard-responses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Standard Response"
        assert data["id"].startswith("SRD-")

    @pytest.mark.anyio
    async def test_update_standard_response(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/standard-responses/SRD-012",
            json={"active": True, "reviewer": "Dr. New Reviewer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is True
        assert data["reviewer"] == "Dr. New Reviewer"

    @pytest.mark.anyio
    async def test_update_standard_response_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/standard-responses/SRD-NONEXISTENT",
            json={"active": False},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_standard_response(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/standard-responses/SRD-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/standard-responses/SRD-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_standard_response_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/standard-responses/SRD-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# PRODUCT FAQ CRUD
# =====================================================================


class TestFaqCrud:
    """Test product FAQ CRUD operations."""

    @pytest.mark.anyio
    async def test_list_faqs(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/faqs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_faqs_filter_product(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/faqs", params={"product_name": "EYLEA HD"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["product_name"] == "EYLEA HD"

    @pytest.mark.anyio
    async def test_get_faq(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/faqs/FAQ-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "FAQ-001"
        assert data["product_name"] == "EYLEA HD"

    @pytest.mark.anyio
    async def test_get_faq_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/faqs/FAQ-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_faq(self, client: AsyncClient):
        payload = _make_faq_create()
        resp = await client.post(f"{API_PREFIX}/faqs", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["product_name"] == "Libtayo"
        assert data["id"].startswith("FAQ-")

    @pytest.mark.anyio
    async def test_update_faq(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/faqs/FAQ-012",
            json={"active": True, "version": "5.0"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is True
        assert data["version"] == "5.0"

    @pytest.mark.anyio
    async def test_update_faq_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/faqs/FAQ-NONEXISTENT",
            json={"active": False},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_faq(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/faqs/FAQ-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/faqs/FAQ-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_faq_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/faqs/FAQ-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# FIELD MEDICAL INSIGHT CRUD
# =====================================================================


class TestInsightCrud:
    """Test field medical insight CRUD operations."""

    @pytest.mark.anyio
    async def test_list_insights(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/insights")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_insights_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/insights", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_insights_filter_product(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/insights", params={"product_name": "Libtayo"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["product_name"] == "Libtayo"

    @pytest.mark.anyio
    async def test_get_insight(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/insights/FMI-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "FMI-001"
        assert data["product_name"] == "EYLEA HD"

    @pytest.mark.anyio
    async def test_get_insight_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/insights/FMI-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_insight(self, client: AsyncClient):
        payload = _make_insight_create()
        resp = await client.post(f"{API_PREFIX}/insights", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["product_name"] == "EYLEA HD"
        assert data["id"].startswith("FMI-")

    @pytest.mark.anyio
    async def test_update_insight(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/insights/FMI-003",
            json={"action_required": True, "action_taken": "Escalated to access team"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action_required"] is True
        assert data["action_taken"] == "Escalated to access team"

    @pytest.mark.anyio
    async def test_update_insight_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/insights/FMI-NONEXISTENT",
            json={"action_required": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_insight(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/insights/FMI-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/insights/FMI-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_insight_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/insights/FMI-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# SCIENTIFIC COMMUNICATION CRUD
# =====================================================================


class TestCommunicationCrud:
    """Test scientific communication CRUD operations."""

    @pytest.mark.anyio
    async def test_list_communications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_communications_filter_product(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/communications",
            params={"product_name": "Libtayo"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["product_name"] == "Libtayo"

    @pytest.mark.anyio
    async def test_get_communication(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications/SCI-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SCI-001"
        assert data["product_name"] == "EYLEA HD"

    @pytest.mark.anyio
    async def test_get_communication_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications/SCI-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_communication(self, client: AsyncClient):
        payload = _make_communication_create()
        resp = await client.post(f"{API_PREFIX}/communications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["product_name"] == "Dupixent"
        assert data["status"] == "draft"
        assert data["id"].startswith("SCI-")

    @pytest.mark.anyio
    async def test_update_communication(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/communications/SCI-010",
            json={"status": "approved", "approved_by": "Dr. Approver"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["approved_by"] == "Dr. Approver"

    @pytest.mark.anyio
    async def test_update_communication_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/communications/SCI-NONEXISTENT",
            json={"status": "sent"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_communication(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/communications/SCI-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/communications/SCI-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_communication_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/communications/SCI-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test medical information metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_inquiries"] == 12
        assert data["total_standard_responses"] == 12
        assert data["total_faqs"] == 12
        assert data["total_insights"] == 12
        assert data["total_communications"] == 12

    @pytest.mark.anyio
    async def test_metrics_active_counts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["active_standard_responses"] > 0
        assert data["active_standard_responses"] <= data["total_standard_responses"]
        assert data["active_faqs"] > 0
        assert data["active_faqs"] <= data["total_faqs"]

    @pytest.mark.anyio
    async def test_metrics_actionable_insights(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["actionable_insights"] > 0
        assert data["actionable_insights"] <= data["total_insights"]

    @pytest.mark.anyio
    async def test_metrics_communications_sent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["communications_sent"] > 0
        assert data["communications_sent"] <= data["total_communications"]

    @pytest.mark.anyio
    async def test_metrics_avg_turnaround(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_turnaround_days"] > 0

    @pytest.mark.anyio
    async def test_metrics_inquiries_by_source(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert len(data["inquiries_by_source"]) > 0
        total_by_source = sum(data["inquiries_by_source"].values())
        assert total_by_source == data["total_inquiries"]

    @pytest.mark.anyio
    async def test_metrics_inquiries_by_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert len(data["inquiries_by_category"]) > 0
        total_by_category = sum(data["inquiries_by_category"].values())
        assert total_by_category == data["total_inquiries"]

    @pytest.mark.anyio
    async def test_metrics_inquiries_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert len(data["inquiries_by_status"]) > 0
        total_by_status = sum(data["inquiries_by_status"].values())
        assert total_by_status == data["total_inquiries"]

    def test_metrics_service_direct(self, svc: MedicalInformationService):
        metrics = svc.get_metrics()
        assert metrics.total_inquiries == 12
        assert metrics.total_standard_responses == 12
        assert metrics.total_faqs == 12
        assert metrics.total_insights == 12
        assert metrics.total_communications == 12


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_medical_information_service()
        svc2 = get_medical_information_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_medical_information_service()
        svc2 = reset_medical_information_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_medical_information_service()
        svc.delete_inquiry("INQ-001")
        assert svc.get_inquiry("INQ-001") is None
        svc2 = reset_medical_information_service()
        assert svc2.get_inquiry("INQ-001") is not None


# =====================================================================
# EDGE CASES
# =====================================================================


class TestEdgeCases:
    """Test edge cases and additional validation."""

    @pytest.mark.anyio
    async def test_list_inquiries_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inquiries")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_inquiries_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/inquiries",
            params={"trial_id": "NONEXISTENT"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_faqs_nonexistent_product(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/faqs",
            params={"product_name": "NonexistentDrug"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_insights_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/insights",
            params={"trial_id": "NONEXISTENT"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_create_inquiry_with_trial_id(self, client: AsyncClient):
        payload = _make_inquiry_create(trial_id=EYLEA_TRIAL)
        resp = await client.post(f"{API_PREFIX}/inquiries", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_insight_with_trial_id(self, client: AsyncClient):
        payload = _make_insight_create(trial_id=DUPIXENT_TRIAL)
        resp = await client.post(f"{API_PREFIX}/insights", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_inquiry_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inquiries/INQ-001")
        data = resp.json()
        assert "id" in data
        assert "product_name" in data
        assert "inquiry_source" in data
        assert "category" in data
        assert "status" in data
        assert "question_text" in data
        assert "received_date" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_standard_response_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/standard-responses/SRD-001")
        data = resp.json()
        assert "id" in data
        assert "product_name" in data
        assert "document_type" in data
        assert "title" in data
        assert "version" in data
        assert "content_summary" in data
        assert "active" in data
        assert "usage_count" in data

    @pytest.mark.anyio
    async def test_faq_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/faqs/FAQ-001")
        data = resp.json()
        assert "id" in data
        assert "product_name" in data
        assert "question" in data
        assert "answer" in data
        assert "active" in data
        assert "view_count" in data

    @pytest.mark.anyio
    async def test_insight_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/insights/FMI-001")
        data = resp.json()
        assert "id" in data
        assert "product_name" in data
        assert "insight_type" in data
        assert "description" in data
        assert "therapeutic_area" in data
        assert "reported_by" in data

    @pytest.mark.anyio
    async def test_communication_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/communications/SCI-001")
        data = resp.json()
        assert "id" in data
        assert "product_name" in data
        assert "communication_type" in data
        assert "title" in data
        assert "audience" in data
        assert "channel" in data
        assert "status" in data

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_inquiries" in data
        assert "inquiries_by_source" in data
        assert "inquiries_by_category" in data
        assert "inquiries_by_status" in data
        assert "avg_turnaround_days" in data
        assert "total_standard_responses" in data
        assert "active_standard_responses" in data
        assert "total_faqs" in data
        assert "active_faqs" in data
        assert "total_insights" in data
        assert "actionable_insights" in data
        assert "total_communications" in data
        assert "communications_sent" in data

    def test_inquiry_adverse_event_flag(self, svc: MedicalInformationService):
        inquiries = svc.list_inquiries()
        ae_reported = [inq for inq in inquiries if inq.adverse_event_reported]
        assert len(ae_reported) > 0

    def test_inquiry_follow_up_required(self, svc: MedicalInformationService):
        inquiries = svc.list_inquiries()
        follow_up = [inq for inq in inquiries if inq.follow_up_required]
        assert len(follow_up) > 0

    def test_communications_sent_count(self, svc: MedicalInformationService):
        communications = svc.list_communications()
        sent = [c for c in communications if c.status == "sent"]
        assert len(sent) == 8

    def test_communications_draft_count(self, svc: MedicalInformationService):
        communications = svc.list_communications()
        drafts = [c for c in communications if c.status == "draft"]
        assert len(drafts) > 0
