"""Tests for Tissue Tracking Management (TISSUE-TRK).

Covers:
- Seed data verification (specimens, blocks, slides, reviews, shipments)
- Specimen CRUD (create, read, update, delete, list, filter by trial/status/type)
- FFPE Block CRUD (create, read, update, delete, list, filter by specimen)
- Tissue Slide CRUD (create, read, update, delete, list, filter by specimen/block/status)
- Pathology Review CRUD (create, read, update, delete, list, filter by trial/specimen/result)
- Tissue Shipment CRUD (create, read, update, delete, list, filter by trial/status)
- Tissue tracking metrics computation
- Error handling (404s)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.tissue_tracking_service import (
    TissueTrackingService,
    get_tissue_tracking_service,
    reset_tissue_tracking_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/tissue-tracking"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_tissue_tracking_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> TissueTrackingService:
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


def _make_specimen_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "PT-9999",
        "site_id": "SITE-101",
        "tissue_type": "biopsy",
        "preservation_method": "formalin_fixed_paraffin_embedded",
        "body_site": "Retina",
        "collected_by": "Dr. Test Collector",
    }
    defaults.update(overrides)
    return defaults


def _make_block_create(**overrides) -> dict:
    defaults = {
        "specimen_id": "TSP-001",
        "block_identifier": "TSP-001-TEST",
        "fixation_time_hours": 20.0,
        "thickness_microns": 4.0,
    }
    defaults.update(overrides)
    return defaults


def _make_slide_create(**overrides) -> dict:
    defaults = {
        "block_id": "BLK-001",
        "specimen_id": "TSP-001",
        "slide_identifier": "TSP-001-A1-TEST",
        "stain_type": "H&E",
        "section_number": 1,
        "prepared_by": "Tech Test User",
    }
    defaults.update(overrides)
    return defaults


def _make_review_create(**overrides) -> dict:
    defaults = {
        "specimen_id": "TSP-001",
        "trial_id": EYLEA_TRIAL,
        "subject_id": "PT-1001",
        "reviewer": "Dr. Test Reviewer",
    }
    defaults.update(overrides)
    return defaults


def _make_shipment_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "origin_site_id": "SITE-101",
        "destination_lab": "Central Path Lab - Test",
        "courier": "World Courier",
        "temperature_condition": "Ambient (15-25C)",
        "specimen_count": 2,
        "tracking_number": "1Z999TEST123456",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_specimens_count(self, svc: TissueTrackingService):
        specimens = svc.list_specimens()
        assert len(specimens) == 12

    def test_seed_specimens_across_trials(self, svc: TissueTrackingService):
        eylea = svc.list_specimens(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_specimens(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_specimens(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 4
        assert len(dupixent) == 4
        assert len(libtayo) == 4

    def test_seed_blocks_count(self, svc: TissueTrackingService):
        blocks = svc.list_blocks()
        assert len(blocks) == 15

    def test_seed_slides_count(self, svc: TissueTrackingService):
        slides = svc.list_slides()
        assert len(slides) == 12

    def test_seed_reviews_count(self, svc: TissueTrackingService):
        reviews = svc.list_reviews()
        assert len(reviews) == 10

    def test_seed_shipments_count(self, svc: TissueTrackingService):
        shipments = svc.list_shipments()
        assert len(shipments) == 10

    def test_seed_specimen_has_required_fields(self, svc: TissueTrackingService):
        specimen = svc.get_specimen("TSP-001")
        assert specimen is not None
        assert specimen.trial_id == EYLEA_TRIAL
        assert specimen.subject_id == "PT-1001"
        assert specimen.tissue_type.value == "biopsy"
        assert specimen.preservation_method.value == "formalin_fixed_paraffin_embedded"
        assert specimen.body_site == "Retina"

    def test_seed_block_belongs_to_specimen(self, svc: TissueTrackingService):
        block = svc.get_block("BLK-001")
        assert block is not None
        assert block.specimen_id == "TSP-001"

    def test_seed_slide_belongs_to_block(self, svc: TissueTrackingService):
        slide = svc.get_slide("SLD-001")
        assert slide is not None
        assert slide.block_id == "BLK-001"
        assert slide.specimen_id == "TSP-001"

    def test_seed_review_references_specimen(self, svc: TissueTrackingService):
        review = svc.get_review("PRV-001")
        assert review is not None
        assert review.specimen_id == "TSP-001"
        assert review.trial_id == EYLEA_TRIAL

    def test_seed_shipment_has_tracking(self, svc: TissueTrackingService):
        shipment = svc.get_shipment("SHP-001")
        assert shipment is not None
        assert shipment.tracking_number is not None
        assert shipment.courier == "World Courier"


# =====================================================================
# SPECIMEN CRUD
# =====================================================================


class TestSpecimenCrud:
    """Test tissue specimen create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_specimens(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_specimens_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_specimens_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens", params={"status": "stored"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "stored"

    @pytest.mark.anyio
    async def test_list_specimens_filter_tissue_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens", params={"tissue_type": "punch"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["tissue_type"] == "punch"

    @pytest.mark.anyio
    async def test_get_specimen(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens/TSP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TSP-001"
        assert data["body_site"] == "Retina"

    @pytest.mark.anyio
    async def test_get_specimen_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens/TSP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_specimen(self, client: AsyncClient):
        payload = _make_specimen_create()
        resp = await client.post(f"{API_PREFIX}/specimens", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject_id"] == "PT-9999"
        assert data["status"] == "collected"
        assert data["id"].startswith("TSP-")

    @pytest.mark.anyio
    async def test_update_specimen(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/specimens/TSP-001",
            json={"status": "depleted", "quality_score": 0.99},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "depleted"
        assert data["quality_score"] == 0.99

    @pytest.mark.anyio
    async def test_update_specimen_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/specimens/TSP-NONEXISTENT",
            json={"status": "stored"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_specimen(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/specimens/TSP-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/specimens/TSP-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_specimen_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/specimens/TSP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# FFPE BLOCK CRUD
# =====================================================================


class TestBlockCrud:
    """Test FFPE block create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_blocks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/blocks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15
        assert len(data["items"]) == 15

    @pytest.mark.anyio
    async def test_list_blocks_filter_specimen(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/blocks", params={"specimen_id": "TSP-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["specimen_id"] == "TSP-001"

    @pytest.mark.anyio
    async def test_get_block(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/blocks/BLK-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "BLK-001"
        assert data["specimen_id"] == "TSP-001"

    @pytest.mark.anyio
    async def test_get_block_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/blocks/BLK-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_block(self, client: AsyncClient):
        payload = _make_block_create()
        resp = await client.post(f"{API_PREFIX}/blocks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["specimen_id"] == "TSP-001"
        assert data["block_identifier"] == "TSP-001-TEST"
        assert data["id"].startswith("BLK-")

    @pytest.mark.anyio
    async def test_update_block(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/blocks/BLK-001",
            json={"sections_cut": 10, "tumor_content_pct": 55.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sections_cut"] == 10
        assert data["tumor_content_pct"] == 55.0

    @pytest.mark.anyio
    async def test_update_block_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/blocks/BLK-NONEXISTENT",
            json={"sections_cut": 5},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_block(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/blocks/BLK-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/blocks/BLK-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_block_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/blocks/BLK-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# TISSUE SLIDE CRUD
# =====================================================================


class TestSlideCrud:
    """Test tissue slide create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_slides(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/slides")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_slides_filter_specimen(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/slides", params={"specimen_id": "TSP-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["specimen_id"] == "TSP-001"

    @pytest.mark.anyio
    async def test_list_slides_filter_block(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/slides", params={"block_id": "BLK-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["block_id"] == "BLK-001"

    @pytest.mark.anyio
    async def test_list_slides_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/slides", params={"status": "reviewed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "reviewed"

    @pytest.mark.anyio
    async def test_get_slide(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/slides/SLD-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SLD-001"
        assert data["stain_type"] == "H&E"

    @pytest.mark.anyio
    async def test_get_slide_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/slides/SLD-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_slide(self, client: AsyncClient):
        payload = _make_slide_create()
        resp = await client.post(f"{API_PREFIX}/slides", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["stain_type"] == "H&E"
        assert data["status"] == "prepared"
        assert data["id"].startswith("SLD-")

    @pytest.mark.anyio
    async def test_update_slide(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/slides/SLD-001",
            json={"status": "archived", "scanner_used": "Zeiss Axioscan"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "archived"
        assert data["scanner_used"] == "Zeiss Axioscan"

    @pytest.mark.anyio
    async def test_update_slide_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/slides/SLD-NONEXISTENT",
            json={"status": "archived"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_slide(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/slides/SLD-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/slides/SLD-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_slide_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/slides/SLD-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# PATHOLOGY REVIEW CRUD
# =====================================================================


class TestReviewCrud:
    """Test pathology review create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_reviews_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_reviews_filter_specimen(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews", params={"specimen_id": "TSP-005"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["specimen_id"] == "TSP-005"

    @pytest.mark.anyio
    async def test_list_reviews_filter_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews", params={"result": "positive"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["result"] == "positive"

    @pytest.mark.anyio
    async def test_get_review(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews/PRV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PRV-001"
        assert data["reviewer"] == "Dr. James Chen"

    @pytest.mark.anyio
    async def test_get_review_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews/PRV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_review(self, client: AsyncClient):
        payload = _make_review_create()
        resp = await client.post(f"{API_PREFIX}/reviews", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["reviewer"] == "Dr. Test Reviewer"
        assert data["result"] == "pending"
        assert data["id"].startswith("PRV-")

    @pytest.mark.anyio
    async def test_update_review(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reviews/PRV-010",
            json={"result": "positive", "diagnosis": "Confirmed pathology"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "positive"
        assert data["diagnosis"] == "Confirmed pathology"

    @pytest.mark.anyio
    async def test_update_review_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reviews/PRV-NONEXISTENT",
            json={"result": "positive"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_review(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reviews/PRV-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/reviews/PRV-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_review_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reviews/PRV-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# TISSUE SHIPMENT CRUD
# =====================================================================


class TestShipmentCrud:
    """Test tissue shipment create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_shipments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_shipments_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_shipments_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments", params={"status": "in_transit"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["status"] == "in_transit"

    @pytest.mark.anyio
    async def test_get_shipment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments/SHP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SHP-001"
        assert data["status"] == "delivered"

    @pytest.mark.anyio
    async def test_get_shipment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments/SHP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_shipment(self, client: AsyncClient):
        payload = _make_shipment_create()
        resp = await client.post(f"{API_PREFIX}/shipments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["destination_lab"] == "Central Path Lab - Test"
        assert data["status"] == "in_transit"
        assert data["id"].startswith("SHP-")

    @pytest.mark.anyio
    async def test_update_shipment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/shipments/SHP-003",
            json={"status": "delivered", "received_by": "Tech Test User"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "delivered"
        assert data["received_by"] == "Tech Test User"

    @pytest.mark.anyio
    async def test_update_shipment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/shipments/SHP-NONEXISTENT",
            json={"status": "delivered"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_shipment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/shipments/SHP-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/shipments/SHP-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_shipment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/shipments/SHP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestTissueTrackingMetrics:
    """Test tissue tracking metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_specimens"] == 12
        assert data["total_blocks"] == 15
        assert data["total_slides"] == 12
        assert data["total_reviews"] == 10
        assert data["total_shipments"] == 10

    @pytest.mark.anyio
    async def test_get_metrics_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_specimens"] == 4

    @pytest.mark.anyio
    async def test_metrics_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_specimens"] == 0
        assert data["total_blocks"] == 0

    def test_metrics_specimens_by_type(self, svc: TissueTrackingService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.specimens_by_type.values())
        assert total_by_type == metrics.total_specimens

    def test_metrics_specimens_by_status(self, svc: TissueTrackingService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.specimens_by_status.values())
        assert total_by_status == metrics.total_specimens

    def test_metrics_specimens_by_preservation(self, svc: TissueTrackingService):
        metrics = svc.get_metrics()
        total_by_preservation = sum(metrics.specimens_by_preservation.values())
        assert total_by_preservation == metrics.total_specimens

    def test_metrics_slides_by_status(self, svc: TissueTrackingService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.slides_by_status.values())
        assert total_by_status == metrics.total_slides

    def test_metrics_reviews_by_result(self, svc: TissueTrackingService):
        metrics = svc.get_metrics()
        total_by_result = sum(metrics.reviews_by_result.values())
        assert total_by_result == metrics.total_reviews

    def test_metrics_pending_reviews(self, svc: TissueTrackingService):
        metrics = svc.get_metrics()
        assert metrics.pending_reviews == 1  # PRV-010 is pending

    def test_metrics_shipments_with_excursions(self, svc: TissueTrackingService):
        metrics = svc.get_metrics()
        assert metrics.shipments_with_excursions == 2  # SHP-005 and SHP-010

    def test_metrics_by_trial_filters_correctly(self, svc: TissueTrackingService):
        metrics = svc.get_metrics(trial_id=LIBTAYO_TRIAL)
        assert metrics.total_specimens == 4
        # LIBTAYO specimens: TSP-009, TSP-010, TSP-011, TSP-012
        # Blocks for those: BLK-009..BLK-014 = 6
        assert metrics.total_blocks == 6
        # Shipments for LIBTAYO: SHP-007..SHP-010 = 4
        assert metrics.total_shipments == 4


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_tissue_tracking_service()
        svc2 = get_tissue_tracking_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_tissue_tracking_service()
        svc2 = reset_tissue_tracking_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_tissue_tracking_service()
        svc.delete_specimen("TSP-001")
        assert svc.get_specimen("TSP-001") is None
        svc2 = reset_tissue_tracking_service()
        assert svc2.get_specimen("TSP-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_specimens_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_blocks_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/blocks")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_slides_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/slides")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_reviews_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_shipments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_blocks_nonexistent_specimen(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/blocks", params={"specimen_id": "TSP-NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_slides_nonexistent_block(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/slides", params={"block_id": "BLK-NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_reviews_nonexistent_specimen(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews", params={"specimen_id": "TSP-NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_create_specimen_with_optional_fields(self, client: AsyncClient):
        payload = _make_specimen_create(
            laterality="Right",
            tumor_type="Melanoma",
        )
        resp = await client.post(f"{API_PREFIX}/specimens", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["laterality"] == "Right"
        assert data["tumor_type"] == "Melanoma"

    @pytest.mark.anyio
    async def test_create_shipment_minimal(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "origin_site_id": "SITE-101",
            "destination_lab": "Minimal Lab",
            "courier": "FedEx",
            "temperature_condition": "Ambient",
        }
        resp = await client.post(f"{API_PREFIX}/shipments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["specimen_count"] == 0
        assert data["tracking_number"] is None

    @pytest.mark.anyio
    async def test_update_shipment_excursion(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/shipments/SHP-003",
            json={"excursion_detected": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["excursion_detected"] is True

    @pytest.mark.anyio
    async def test_create_review_with_biomarker(self, client: AsyncClient):
        payload = _make_review_create(biomarker_name="PD-L1")
        resp = await client.post(f"{API_PREFIX}/reviews", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["biomarker_name"] == "PD-L1"

    @pytest.mark.anyio
    async def test_update_review_adjudication(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reviews/PRV-007",
            json={"adjudication_required": True, "adjudicated_by": "Dr. Expert"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["adjudication_required"] is True
        assert data["adjudicated_by"] == "Dr. Expert"


# =====================================================================
# DATA VALIDATION
# =====================================================================


class TestDataValidation:
    """Test detailed data validation across the system."""

    @pytest.mark.anyio
    async def test_specimen_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/specimens/TSP-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "subject_id" in data
        assert "site_id" in data
        assert "tissue_type" in data
        assert "preservation_method" in data
        assert "status" in data
        assert "collection_date" in data
        assert "body_site" in data
        assert "collected_by" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_block_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/blocks/BLK-001")
        data = resp.json()
        assert "id" in data
        assert "specimen_id" in data
        assert "block_identifier" in data
        assert "sections_cut" in data
        assert "sections_remaining" in data
        assert "thickness_microns" in data
        assert "quality_adequate" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_slide_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/slides/SLD-001")
        data = resp.json()
        assert "id" in data
        assert "block_id" in data
        assert "specimen_id" in data
        assert "slide_identifier" in data
        assert "stain_type" in data
        assert "status" in data
        assert "section_number" in data
        assert "preparation_date" in data
        assert "prepared_by" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_review_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews/PRV-001")
        data = resp.json()
        assert "id" in data
        assert "specimen_id" in data
        assert "trial_id" in data
        assert "subject_id" in data
        assert "reviewer" in data
        assert "review_date" in data
        assert "result" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_shipment_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/shipments/SHP-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "origin_site_id" in data
        assert "destination_lab" in data
        assert "shipment_date" in data
        assert "courier" in data
        assert "temperature_condition" in data
        assert "status" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_specimens" in data
        assert "specimens_by_type" in data
        assert "specimens_by_status" in data
        assert "specimens_by_preservation" in data
        assert "total_blocks" in data
        assert "total_slides" in data
        assert "slides_by_status" in data
        assert "total_reviews" in data
        assert "reviews_by_result" in data
        assert "pending_reviews" in data
        assert "total_shipments" in data
        assert "shipments_with_excursions" in data

    def test_stored_specimens_have_location(self, svc: TissueTrackingService):
        specimens = svc.list_specimens(status="stored")
        for s in specimens:
            assert s.storage_location is not None

    def test_reviewed_slides_have_reviewer(self, svc: TissueTrackingService):
        slides = svc.list_slides(status="reviewed")
        for s in slides:
            assert s.reviewed_by is not None
            assert s.review_date is not None

    def test_quality_failed_specimen_has_low_score(self, svc: TissueTrackingService):
        specimen = svc.get_specimen("TSP-007")
        assert specimen is not None
        assert specimen.status.value == "quality_failed"
        assert specimen.quality_score is not None
        assert specimen.quality_score < 0.5

    def test_excursion_shipments_detected(self, svc: TissueTrackingService):
        shp5 = svc.get_shipment("SHP-005")
        shp10 = svc.get_shipment("SHP-010")
        assert shp5 is not None and shp5.excursion_detected is True
        assert shp10 is not None and shp10.excursion_detected is True
