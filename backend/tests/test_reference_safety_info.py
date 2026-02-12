"""Tests for Reference Safety Information Management (RSI-MGT).

Covers:
- Seed data verification (documents, sections, updates, narratives, line items)
- Safety Document CRUD (create, read, update, delete, list, filters)
- IB Section CRUD (create, read, update, delete, list, filters)
- Safety Update CRUD (create, read, update, delete, list, filters)
- Safety Narrative CRUD (create, read, update, delete, list, filters)
- RSI Line Item CRUD (create, read, update, delete, list, filters)
- RSI metrics computation
- Error handling (404s)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.reference_safety_info import (
    DocumentCategory,
    NarrativeType,
    ReviewStatus,
    SectionType,
    UpdateType,
)
from app.services.reference_safety_info_service import (
    ReferenceSafetyInfoService,
    get_reference_safety_info_service,
    reset_reference_safety_info_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/reference-safety-info"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_reference_safety_info_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ReferenceSafetyInfoService:
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


def _make_document_create(**overrides) -> dict:
    defaults = {
        "product_name": "Test Product",
        "category": "investigators_brochure",
        "title": "Test IB v1",
        "version": "1.0",
        "author": "Dr. Test Author",
    }
    defaults.update(overrides)
    return defaults


def _make_section_create(**overrides) -> dict:
    defaults = {
        "document_id": "SDOC-001",
        "section_number": "9.1",
        "section_type": "clinical_safety",
        "title": "Test Section",
        "content_summary": "Test content summary for IB section.",
        "updated_by": "Dr. Test Author",
    }
    defaults.update(overrides)
    return defaults


def _make_update_create(**overrides) -> dict:
    defaults = {
        "document_id": "SDOC-001",
        "product_name": "EYLEA HD",
        "update_type": "new_signal",
        "safety_topic": "Test safety signal",
        "updated_information": "New safety information discovered.",
        "rationale": "Clinical data supports this update.",
        "proposed_by": "Dr. Test Proposer",
    }
    defaults.update(overrides)
    return defaults


def _make_narrative_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "PT-9999",
        "narrative_type": "sae_narrative",
        "case_number": "TEST-SAE-001",
        "event_term": "Test adverse event",
        "narrative_text": "A test patient experienced a test adverse event requiring narrative documentation.",
        "author": "Dr. Test Author",
    }
    defaults.update(overrides)
    return defaults


def _make_line_item_create(**overrides) -> dict:
    defaults = {
        "document_id": "SDOC-003",
        "product_name": "EYLEA HD",
        "adverse_event_term": "Test Event",
        "system_organ_class": "Test disorders",
        "frequency_category": "Common (>=1/100 to <1/10)",
        "source": "Test clinical trial",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_documents_count(self, svc: ReferenceSafetyInfoService):
        documents = svc.list_safety_documents()
        assert len(documents) == 12

    def test_seed_documents_products_present(self, svc: ReferenceSafetyInfoService):
        documents = svc.list_safety_documents()
        products = {d.product_name for d in documents}
        assert "EYLEA HD" in products
        assert "Dupixent" in products
        assert "Libtayo" in products

    def test_seed_documents_categories_present(self, svc: ReferenceSafetyInfoService):
        documents = svc.list_safety_documents()
        categories = {d.category for d in documents}
        assert DocumentCategory.INVESTIGATORS_BROCHURE in categories
        assert DocumentCategory.DSUR in categories
        assert DocumentCategory.RSI_TABLE in categories

    def test_seed_sections_count(self, svc: ReferenceSafetyInfoService):
        sections = svc.list_ib_sections()
        assert len(sections) == 15

    def test_seed_sections_types_present(self, svc: ReferenceSafetyInfoService):
        sections = svc.list_ib_sections()
        types = {s.section_type for s in sections}
        assert SectionType.CLINICAL_SAFETY in types
        assert SectionType.PHARMACOLOGY in types
        assert SectionType.TOXICOLOGY in types

    def test_seed_updates_count(self, svc: ReferenceSafetyInfoService):
        updates = svc.list_safety_updates()
        assert len(updates) == 12

    def test_seed_updates_types_present(self, svc: ReferenceSafetyInfoService):
        updates = svc.list_safety_updates()
        types = {u.update_type for u in updates}
        assert UpdateType.NEW_SIGNAL in types
        assert UpdateType.FREQUENCY_CHANGE in types
        assert UpdateType.SEVERITY_UPGRADE in types
        assert UpdateType.LABELING_CHANGE in types

    def test_seed_narratives_count(self, svc: ReferenceSafetyInfoService):
        narratives = svc.list_safety_narratives()
        assert len(narratives) == 12

    def test_seed_narratives_types_present(self, svc: ReferenceSafetyInfoService):
        narratives = svc.list_safety_narratives()
        types = {n.narrative_type for n in narratives}
        assert NarrativeType.SAE_NARRATIVE in types
        assert NarrativeType.SUSAR_NARRATIVE in types
        assert NarrativeType.DEATH_NARRATIVE in types
        assert NarrativeType.PREGNANCY_NARRATIVE in types

    def test_seed_line_items_count(self, svc: ReferenceSafetyInfoService):
        line_items = svc.list_rsi_line_items()
        assert len(line_items) == 15

    def test_seed_line_items_products_present(self, svc: ReferenceSafetyInfoService):
        line_items = svc.list_rsi_line_items()
        products = {li.product_name for li in line_items}
        assert "EYLEA HD" in products
        assert "Dupixent" in products
        assert "Libtayo" in products


# =====================================================================
# SAFETY DOCUMENT CRUD
# =====================================================================


class TestSafetyDocumentCrud:
    """Test safety document create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_documents(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_documents_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_documents_filter_product(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents", params={"product_name": "Dupixent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["product_name"] == "Dupixent"

    @pytest.mark.anyio
    async def test_list_documents_filter_category(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/documents",
            params={"category": "investigators_brochure"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["category"] == "investigators_brochure"

    @pytest.mark.anyio
    async def test_list_documents_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents", params={"status": "published"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "published"

    @pytest.mark.anyio
    async def test_get_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/SDOC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SDOC-001"
        assert data["product_name"] == "EYLEA HD"

    @pytest.mark.anyio
    async def test_get_document_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/SDOC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_document(self, client: AsyncClient):
        payload = _make_document_create()
        resp = await client.post(f"{API_PREFIX}/documents", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["product_name"] == "Test Product"
        assert data["status"] == "draft"
        assert data["id"].startswith("SDOC-")

    @pytest.mark.anyio
    async def test_create_document_with_trial(self, client: AsyncClient):
        payload = _make_document_create(trial_id=EYLEA_TRIAL)
        resp = await client.post(f"{API_PREFIX}/documents", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_update_document(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/documents/SDOC-012",
            json={"status": "medical_review", "medical_reviewer": "Dr. Test Reviewer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "medical_review"
        assert data["medical_reviewer"] == "Dr. Test Reviewer"

    @pytest.mark.anyio
    async def test_update_document_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/documents/SDOC-NONEXISTENT",
            json={"status": "draft"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_document_approved_by_sets_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/documents/SDOC-012",
            json={"approved_by": "Dr. Approver"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approved_by"] == "Dr. Approver"
        assert data["approved_date"] is not None

    @pytest.mark.anyio
    async def test_delete_document(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/documents/SDOC-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/documents/SDOC-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_document_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/documents/SDOC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# IB SECTION CRUD
# =====================================================================


class TestIBSectionCrud:
    """Test IB section create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_sections(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sections")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_sections_filter_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sections", params={"document_id": "SDOC-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        for item in data["items"]:
            assert item["document_id"] == "SDOC-001"

    @pytest.mark.anyio
    async def test_list_sections_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sections",
            params={"section_type": "clinical_safety"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["section_type"] == "clinical_safety"

    @pytest.mark.anyio
    async def test_get_section(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sections/SEC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SEC-001"
        assert data["document_id"] == "SDOC-001"

    @pytest.mark.anyio
    async def test_get_section_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sections/SEC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_section(self, client: AsyncClient):
        payload = _make_section_create()
        resp = await client.post(f"{API_PREFIX}/sections", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Section"
        assert data["id"].startswith("SEC-")

    @pytest.mark.anyio
    async def test_update_section(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sections/SEC-001",
            json={"content_summary": "Updated summary", "word_count": 9000, "change_description": "Major update"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["content_summary"] == "Updated summary"
        assert data["word_count"] == 9000
        assert data["change_description"] == "Major update"

    @pytest.mark.anyio
    async def test_update_section_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sections/SEC-NONEXISTENT",
            json={"content_summary": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_section(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sections/SEC-015")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/sections/SEC-015")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_section_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sections/SEC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# SAFETY UPDATE CRUD
# =====================================================================


class TestSafetyUpdateCrud:
    """Test safety update create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_updates(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/updates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_updates_filter_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/updates", params={"document_id": "SDOC-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["document_id"] == "SDOC-001"

    @pytest.mark.anyio
    async def test_list_updates_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/updates", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_updates_filter_product(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/updates", params={"product_name": "Libtayo"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["product_name"] == "Libtayo"

    @pytest.mark.anyio
    async def test_list_updates_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/updates",
            params={"update_type": "frequency_change"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["update_type"] == "frequency_change"

    @pytest.mark.anyio
    async def test_get_update(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/updates/UPD-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "UPD-001"
        assert data["product_name"] == "EYLEA HD"

    @pytest.mark.anyio
    async def test_get_update_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/updates/UPD-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_update(self, client: AsyncClient):
        payload = _make_update_create()
        resp = await client.post(f"{API_PREFIX}/updates", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["safety_topic"] == "Test safety signal"
        assert data["id"].startswith("UPD-")

    @pytest.mark.anyio
    async def test_update_safety_update(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/updates/UPD-012",
            json={"approved_by": "Dr. Approver", "regulatory_notification_required": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approved_by"] == "Dr. Approver"
        assert data["regulatory_notification_required"] is True

    @pytest.mark.anyio
    async def test_update_safety_update_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/updates/UPD-NONEXISTENT",
            json={"approved_by": "Dr. Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_update(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/updates/UPD-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/updates/UPD-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_update_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/updates/UPD-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# SAFETY NARRATIVE CRUD
# =====================================================================


class TestSafetyNarrativeCrud:
    """Test safety narrative create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_narratives(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/narratives")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_narratives_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/narratives", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_narratives_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/narratives",
            params={"narrative_type": "sae_narrative"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["narrative_type"] == "sae_narrative"

    @pytest.mark.anyio
    async def test_list_narratives_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/narratives", params={"status": "draft"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "draft"

    @pytest.mark.anyio
    async def test_get_narrative(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/narratives/NAR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "NAR-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_narrative_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/narratives/NAR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_narrative(self, client: AsyncClient):
        payload = _make_narrative_create()
        resp = await client.post(f"{API_PREFIX}/narratives", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["case_number"] == "TEST-SAE-001"
        assert data["status"] == "draft"
        assert data["id"].startswith("NAR-")
        assert data["word_count"] > 0

    @pytest.mark.anyio
    async def test_update_narrative(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/narratives/NAR-011",
            json={"status": "medical_review", "medical_reviewer": "Dr. Reviewer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "medical_review"
        assert data["medical_reviewer"] == "Dr. Reviewer"
        assert data["review_date"] is not None

    @pytest.mark.anyio
    async def test_update_narrative_text_updates_word_count(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/narratives/NAR-011",
            json={"narrative_text": "Short text here."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["word_count"] == 3

    @pytest.mark.anyio
    async def test_update_narrative_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/narratives/NAR-NONEXISTENT",
            json={"status": "draft"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_narrative(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/narratives/NAR-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/narratives/NAR-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_narrative_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/narratives/NAR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# RSI LINE ITEM CRUD
# =====================================================================


class TestRSILineItemCrud:
    """Test RSI line item create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_line_items(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-items")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_line_items_filter_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-items", params={"document_id": "SDOC-003"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        for item in data["items"]:
            assert item["document_id"] == "SDOC-003"

    @pytest.mark.anyio
    async def test_list_line_items_filter_product(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-items", params={"product_name": "Libtayo"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        for item in data["items"]:
            assert item["product_name"] == "Libtayo"

    @pytest.mark.anyio
    async def test_get_line_item(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-items/RSI-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RSI-001"
        assert data["product_name"] == "EYLEA HD"

    @pytest.mark.anyio
    async def test_get_line_item_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-items/RSI-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_line_item(self, client: AsyncClient):
        payload = _make_line_item_create()
        resp = await client.post(f"{API_PREFIX}/line-items", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["adverse_event_term"] == "Test Event"
        assert data["id"].startswith("RSI-")

    @pytest.mark.anyio
    async def test_create_line_item_with_incidence(self, client: AsyncClient):
        payload = _make_line_item_create(incidence_pct=5.5)
        resp = await client.post(f"{API_PREFIX}/line-items", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["incidence_pct"] == 5.5

    @pytest.mark.anyio
    async def test_update_line_item(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/line-items/RSI-015",
            json={"frequency_category": "Common (>=1/100 to <1/10)", "notes": "Updated note"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["frequency_category"] == "Common (>=1/100 to <1/10)"
        assert data["notes"] == "Updated note"

    @pytest.mark.anyio
    async def test_update_line_item_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/line-items/RSI-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_line_item(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/line-items/RSI-015")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/line-items/RSI-015")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_line_item_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/line-items/RSI-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestRSIMetrics:
    """Test RSI metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_documents"] == 12
        assert data["total_ib_sections"] == 15
        assert data["total_safety_updates"] == 12
        assert data["total_narratives"] == 12
        assert data["total_rsi_line_items"] == 15

    @pytest.mark.anyio
    async def test_get_metrics_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_documents"] == 3
        assert data["total_safety_updates"] == 3
        assert data["total_narratives"] == 3

    @pytest.mark.anyio
    async def test_metrics_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_documents"] == 0
        assert data["total_ib_sections"] == 0
        assert data["total_safety_updates"] == 0

    def test_metrics_documents_by_category(self, svc: ReferenceSafetyInfoService):
        metrics = svc.get_metrics()
        total_by_category = sum(metrics.documents_by_category.values())
        assert total_by_category == metrics.total_documents

    def test_metrics_documents_by_status(self, svc: ReferenceSafetyInfoService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.documents_by_status.values())
        assert total_by_status == metrics.total_documents

    def test_metrics_active_documents(self, svc: ReferenceSafetyInfoService):
        metrics = svc.get_metrics()
        documents = svc.list_safety_documents()
        expected_active = sum(
            1 for d in documents
            if d.status in (ReviewStatus.PUBLISHED, ReviewStatus.APPROVED)
        )
        assert metrics.active_documents == expected_active

    def test_metrics_updates_by_type(self, svc: ReferenceSafetyInfoService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.updates_by_type.values())
        assert total_by_type == metrics.total_safety_updates

    def test_metrics_pending_notifications(self, svc: ReferenceSafetyInfoService):
        metrics = svc.get_metrics()
        updates = svc.list_safety_updates()
        expected_pending = sum(
            1 for u in updates
            if (u.regulatory_notification_required or u.investigator_notification_required or u.irb_notification_required)
            and u.implementation_date is None
        )
        assert metrics.pending_notifications == expected_pending

    def test_metrics_narratives_by_type(self, svc: ReferenceSafetyInfoService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.narratives_by_type.values())
        assert total_by_type == metrics.total_narratives

    def test_metrics_narratives_pending_review(self, svc: ReferenceSafetyInfoService):
        metrics = svc.get_metrics()
        narratives = svc.list_safety_narratives()
        expected_pending = sum(
            1 for n in narratives
            if n.status in (ReviewStatus.DRAFT, ReviewStatus.MEDICAL_REVIEW, ReviewStatus.SAFETY_REVIEW)
        )
        assert metrics.narratives_pending_review == expected_pending

    def test_metrics_expected_events(self, svc: ReferenceSafetyInfoService):
        metrics = svc.get_metrics()
        line_items = svc.list_rsi_line_items()
        expected = sum(1 for li in line_items if li.expectedness == "expected")
        assert metrics.expected_events == expected


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_reference_safety_info_service()
        svc2 = get_reference_safety_info_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_reference_safety_info_service()
        svc2 = reset_reference_safety_info_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_reference_safety_info_service()
        svc.delete_safety_document("SDOC-001")
        assert svc.get_safety_document("SDOC-001") is None
        svc2 = reset_reference_safety_info_service()
        assert svc2.get_safety_document("SDOC-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_documents_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_sections_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sections")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_updates_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/updates")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_narratives_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/narratives")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_line_items_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-items")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_documents_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/documents",
            params={"product_name": "NonexistentProduct"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_list_sections_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sections",
            params={"document_id": "SDOC-NONEXISTENT"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_updates_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/updates",
            params={"trial_id": "NONEXISTENT"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_narratives_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/narratives",
            params={"trial_id": "NONEXISTENT"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_line_items_empty_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/line-items",
            params={"product_name": "NonexistentProduct"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_document_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/SDOC-001")
        data = resp.json()
        assert "id" in data
        assert "product_name" in data
        assert "category" in data
        assert "title" in data
        assert "version" in data
        assert "status" in data
        assert "author" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_section_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sections/SEC-001")
        data = resp.json()
        assert "id" in data
        assert "document_id" in data
        assert "section_number" in data
        assert "section_type" in data
        assert "title" in data
        assert "content_summary" in data
        assert "word_count" in data
        assert "last_updated" in data

    @pytest.mark.anyio
    async def test_update_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/updates/UPD-001")
        data = resp.json()
        assert "id" in data
        assert "document_id" in data
        assert "product_name" in data
        assert "update_type" in data
        assert "safety_topic" in data
        assert "updated_information" in data
        assert "rationale" in data
        assert "proposed_by" in data

    @pytest.mark.anyio
    async def test_narrative_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/narratives/NAR-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "subject_id" in data
        assert "narrative_type" in data
        assert "case_number" in data
        assert "event_term" in data
        assert "narrative_text" in data
        assert "word_count" in data
        assert "status" in data
        assert "author" in data

    @pytest.mark.anyio
    async def test_line_item_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/line-items/RSI-001")
        data = resp.json()
        assert "id" in data
        assert "document_id" in data
        assert "product_name" in data
        assert "adverse_event_term" in data
        assert "system_organ_class" in data
        assert "frequency_category" in data
        assert "expectedness" in data
        assert "source" in data

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_documents" in data
        assert "documents_by_category" in data
        assert "documents_by_status" in data
        assert "active_documents" in data
        assert "total_ib_sections" in data
        assert "total_safety_updates" in data
        assert "updates_by_type" in data
        assert "pending_notifications" in data
        assert "total_narratives" in data
        assert "narratives_by_type" in data
        assert "narratives_pending_review" in data
        assert "total_rsi_line_items" in data
        assert "expected_events" in data

    def test_published_documents_have_effective_date(self, svc: ReferenceSafetyInfoService):
        documents = svc.list_safety_documents(status=ReviewStatus.PUBLISHED)
        for d in documents:
            assert d.effective_date is not None

    def test_draft_document_has_no_approver(self, svc: ReferenceSafetyInfoService):
        documents = svc.list_safety_documents(status=ReviewStatus.DRAFT)
        for d in documents:
            assert d.approved_by is None

    def test_line_items_sorted_by_event_term(self, svc: ReferenceSafetyInfoService):
        items = svc.list_rsi_line_items()
        terms = [li.adverse_event_term for li in items]
        assert terms == sorted(terms)

    def test_unexpected_line_item_exists(self, svc: ReferenceSafetyInfoService):
        items = svc.list_rsi_line_items()
        unexpected = [li for li in items if li.expectedness == "unexpected"]
        assert len(unexpected) >= 1
