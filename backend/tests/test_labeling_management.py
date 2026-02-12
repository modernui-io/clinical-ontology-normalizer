"""Tests for Labeling Management (LABEL-MGMT).

Covers:
- Seed data verification (labels, negotiations, artworks, changes, country labels)
- Label content CRUD (create, read, update, delete, list, filter by trial/status/section)
- Label negotiation CRUD (create, read, update, delete, list, filter by trial/label/status)
- Label artwork CRUD (create, read, update, delete, list, filter by label/status)
- Label change CRUD (create, read, update, delete, list, filter by trial/label/category)
- Country label CRUD (create, read, update, delete, list, filter by label/country)
- Labeling metrics computation
- Error handling (404s, validation errors)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.labeling_management import (
    ArtworkStatus,
    ChangeCategory,
    LabelSection,
    LabelStatus,
    NegotiationStatus,
)
from app.services.labeling_management_service import (
    LabelingManagementService,
    get_labeling_management_service,
    reset_labeling_management_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/labeling-management"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_labeling_management_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> LabelingManagementService:
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


def _make_label_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "product_name": "Test Product",
        "version": "1.0",
        "section": "indications_and_usage",
        "content_text": "Test label content text for indications.",
        "language": "en",
        "author": "test_author",
    }
    defaults.update(overrides)
    return defaults


def _make_negotiation_create(**overrides) -> dict:
    defaults = {
        "label_id": "LC-001",
        "trial_id": EYLEA_TRIAL,
        "health_authority": "FDA",
        "section": "warnings_and_precautions",
        "proposed_text": "Updated warnings for test negotiation.",
        "regulatory_contact": "fda_reviewer",
        "internal_lead": "internal_lead",
    }
    defaults.update(overrides)
    return defaults


def _make_artwork_create(**overrides) -> dict:
    defaults = {
        "label_id": "LC-001",
        "artwork_type": "carton_label",
        "file_name": "test_artwork.ai",
        "version": "1.0",
        "language": "en",
        "designer": "test_designer",
    }
    defaults.update(overrides)
    return defaults


def _make_change_create(**overrides) -> dict:
    defaults = {
        "label_id": "LC-001",
        "trial_id": EYLEA_TRIAL,
        "change_category": "safety_update",
        "description": "Test safety update change.",
        "affected_sections": ["warnings_and_precautions"],
        "rationale": "New safety signal identified.",
        "safety_impact": True,
        "requested_by": "test_requester",
    }
    defaults.update(overrides)
    return defaults


def _make_country_label_create(**overrides) -> dict:
    defaults = {
        "label_id": "LC-001",
        "country": "DE",
        "language": "de",
        "regulatory_authority": "BfArM",
        "responsible_person": "de_regulatory_lead",
        "local_product_name": "Test Product DE",
        "local_requirements": ["German language labeling"],
    }
    defaults.update(overrides)
    return defaults


# ===========================================================================
# SEED DATA VERIFICATION
# ===========================================================================


class TestSeedData:
    """Verify that demo data is seeded correctly."""

    def test_seed_labels_count(self, svc: LabelingManagementService):
        labels = svc.list_labels()
        assert len(labels) == 12

    def test_seed_negotiations_count(self, svc: LabelingManagementService):
        negotiations = svc.list_negotiations()
        assert len(negotiations) == 10

    def test_seed_artworks_count(self, svc: LabelingManagementService):
        artworks = svc.list_artworks()
        assert len(artworks) == 12

    def test_seed_changes_count(self, svc: LabelingManagementService):
        changes = svc.list_changes()
        assert len(changes) == 12

    def test_seed_country_labels_count(self, svc: LabelingManagementService):
        country_labels = svc.list_country_labels()
        assert len(country_labels) == 12

    def test_seed_labels_have_eylea(self, svc: LabelingManagementService):
        labels = svc.list_labels(trial_id=EYLEA_TRIAL)
        assert len(labels) >= 3

    def test_seed_labels_have_dupixent(self, svc: LabelingManagementService):
        labels = svc.list_labels(trial_id=DUPIXENT_TRIAL)
        assert len(labels) >= 3

    def test_seed_labels_have_libtayo(self, svc: LabelingManagementService):
        labels = svc.list_labels(trial_id=LIBTAYO_TRIAL)
        assert len(labels) >= 3

    def test_seed_label_lc001_details(self, svc: LabelingManagementService):
        label = svc.get_label("LC-001")
        assert label is not None
        assert label.trial_id == EYLEA_TRIAL
        assert label.product_name == "EYLEA (aflibercept)"
        assert label.section == LabelSection.INDICATIONS
        assert label.status == LabelStatus.EFFECTIVE

    def test_seed_label_lc005_details(self, svc: LabelingManagementService):
        label = svc.get_label("LC-005")
        assert label is not None
        assert label.trial_id == DUPIXENT_TRIAL
        assert label.product_name == "DUPIXENT (dupilumab)"

    def test_seed_label_lc009_details(self, svc: LabelingManagementService):
        label = svc.get_label("LC-009")
        assert label is not None
        assert label.trial_id == LIBTAYO_TRIAL
        assert label.product_name == "LIBTAYO (cemiplimab-rwlc)"

    def test_seed_negotiation_ln001_details(self, svc: LabelingManagementService):
        neg = svc.get_negotiation("LN-001")
        assert neg is not None
        assert neg.label_id == "LC-003"
        assert neg.health_authority == "FDA"
        assert neg.status == NegotiationStatus.UNDER_DISCUSSION

    def test_seed_negotiation_ln003_agreed(self, svc: LabelingManagementService):
        neg = svc.get_negotiation("LN-003")
        assert neg is not None
        assert neg.status == NegotiationStatus.AGREED
        assert neg.agreed_text is not None

    def test_seed_artwork_la001_details(self, svc: LabelingManagementService):
        artwork = svc.get_artwork("LA-001")
        assert artwork is not None
        assert artwork.label_id == "LC-001"
        assert artwork.artwork_type == "carton_label"
        assert artwork.status == ArtworkStatus.APPROVED

    def test_seed_change_lch001_details(self, svc: LabelingManagementService):
        change = svc.get_change("LCH-001")
        assert change is not None
        assert change.label_id == "LC-001"
        assert change.change_category == ChangeCategory.SAFETY_UPDATE
        assert change.safety_impact is True

    def test_seed_country_label_cl001_details(self, svc: LabelingManagementService):
        cl = svc.get_country_label("CL-001")
        assert cl is not None
        assert cl.label_id == "LC-001"
        assert cl.country == "US"
        assert cl.translation_status == "approved"

    def test_seed_labels_sorted_by_id(self, svc: LabelingManagementService):
        labels = svc.list_labels()
        ids = [lbl.id for lbl in labels]
        assert ids == sorted(ids)

    def test_seed_negotiations_sorted_by_id(self, svc: LabelingManagementService):
        negotiations = svc.list_negotiations()
        ids = [n.id for n in negotiations]
        assert ids == sorted(ids)

    def test_seed_artworks_sorted_by_id(self, svc: LabelingManagementService):
        artworks = svc.list_artworks()
        ids = [a.id for a in artworks]
        assert ids == sorted(ids)

    def test_seed_changes_sorted_by_id(self, svc: LabelingManagementService):
        changes = svc.list_changes()
        ids = [c.id for c in changes]
        assert ids == sorted(ids)

    def test_seed_country_labels_sorted_by_id(self, svc: LabelingManagementService):
        cls = svc.list_country_labels()
        ids = [cl.id for cl in cls]
        assert ids == sorted(ids)


# ===========================================================================
# LABEL CONTENT CRUD
# ===========================================================================


class TestLabelContentCRUD:
    """Test CRUD operations for label content."""

    def test_list_all_labels(self, svc: LabelingManagementService):
        labels = svc.list_labels()
        assert len(labels) == 12

    def test_get_label_by_id(self, svc: LabelingManagementService):
        label = svc.get_label("LC-001")
        assert label is not None
        assert label.id == "LC-001"

    def test_get_label_not_found(self, svc: LabelingManagementService):
        label = svc.get_label("NONEXISTENT")
        assert label is None

    def test_filter_labels_by_trial(self, svc: LabelingManagementService):
        labels = svc.list_labels(trial_id=EYLEA_TRIAL)
        assert all(lbl.trial_id == EYLEA_TRIAL for lbl in labels)
        assert len(labels) >= 3

    def test_filter_labels_by_status(self, svc: LabelingManagementService):
        labels = svc.list_labels(status=LabelStatus.EFFECTIVE)
        assert all(lbl.status == LabelStatus.EFFECTIVE for lbl in labels)
        assert len(labels) >= 4

    def test_filter_labels_by_section(self, svc: LabelingManagementService):
        labels = svc.list_labels(section=LabelSection.INDICATIONS)
        assert all(lbl.section == LabelSection.INDICATIONS for lbl in labels)
        assert len(labels) >= 3

    def test_filter_labels_combined(self, svc: LabelingManagementService):
        labels = svc.list_labels(trial_id=EYLEA_TRIAL, status=LabelStatus.EFFECTIVE)
        assert all(lbl.trial_id == EYLEA_TRIAL and lbl.status == LabelStatus.EFFECTIVE for lbl in labels)

    def test_filter_labels_no_match(self, svc: LabelingManagementService):
        labels = svc.list_labels(trial_id="nonexistent-trial")
        assert len(labels) == 0

    def test_delete_label(self, svc: LabelingManagementService):
        assert svc.delete_label("LC-001") is True
        assert svc.get_label("LC-001") is None

    def test_delete_label_not_found(self, svc: LabelingManagementService):
        assert svc.delete_label("NONEXISTENT") is False

    def test_delete_label_reduces_count(self, svc: LabelingManagementService):
        count_before = len(svc.list_labels())
        svc.delete_label("LC-001")
        count_after = len(svc.list_labels())
        assert count_after == count_before - 1


# ===========================================================================
# LABEL NEGOTIATION CRUD
# ===========================================================================


class TestLabelNegotiationCRUD:
    """Test CRUD operations for label negotiations."""

    def test_list_all_negotiations(self, svc: LabelingManagementService):
        items = svc.list_negotiations()
        assert len(items) == 10

    def test_get_negotiation_by_id(self, svc: LabelingManagementService):
        neg = svc.get_negotiation("LN-001")
        assert neg is not None
        assert neg.id == "LN-001"

    def test_get_negotiation_not_found(self, svc: LabelingManagementService):
        assert svc.get_negotiation("NONEXISTENT") is None

    def test_filter_negotiations_by_trial(self, svc: LabelingManagementService):
        items = svc.list_negotiations(trial_id=EYLEA_TRIAL)
        assert all(n.trial_id == EYLEA_TRIAL for n in items)

    def test_filter_negotiations_by_label(self, svc: LabelingManagementService):
        items = svc.list_negotiations(label_id="LC-003")
        assert all(n.label_id == "LC-003" for n in items)

    def test_filter_negotiations_by_status(self, svc: LabelingManagementService):
        items = svc.list_negotiations(status=NegotiationStatus.AGREED)
        assert all(n.status == NegotiationStatus.AGREED for n in items)
        assert len(items) >= 2

    def test_filter_negotiations_combined(self, svc: LabelingManagementService):
        items = svc.list_negotiations(trial_id=DUPIXENT_TRIAL, status=NegotiationStatus.AGREED)
        assert all(n.trial_id == DUPIXENT_TRIAL and n.status == NegotiationStatus.AGREED for n in items)

    def test_filter_negotiations_no_match(self, svc: LabelingManagementService):
        items = svc.list_negotiations(trial_id="nonexistent")
        assert len(items) == 0

    def test_delete_negotiation(self, svc: LabelingManagementService):
        assert svc.delete_negotiation("LN-001") is True
        assert svc.get_negotiation("LN-001") is None

    def test_delete_negotiation_not_found(self, svc: LabelingManagementService):
        assert svc.delete_negotiation("NONEXISTENT") is False

    def test_delete_negotiation_reduces_count(self, svc: LabelingManagementService):
        count_before = len(svc.list_negotiations())
        svc.delete_negotiation("LN-001")
        count_after = len(svc.list_negotiations())
        assert count_after == count_before - 1


# ===========================================================================
# LABEL ARTWORK CRUD
# ===========================================================================


class TestLabelArtworkCRUD:
    """Test CRUD operations for label artworks."""

    def test_list_all_artworks(self, svc: LabelingManagementService):
        items = svc.list_artworks()
        assert len(items) == 12

    def test_get_artwork_by_id(self, svc: LabelingManagementService):
        artwork = svc.get_artwork("LA-001")
        assert artwork is not None
        assert artwork.id == "LA-001"

    def test_get_artwork_not_found(self, svc: LabelingManagementService):
        assert svc.get_artwork("NONEXISTENT") is None

    def test_filter_artworks_by_label(self, svc: LabelingManagementService):
        items = svc.list_artworks(label_id="LC-001")
        assert all(a.label_id == "LC-001" for a in items)
        assert len(items) >= 3

    def test_filter_artworks_by_status(self, svc: LabelingManagementService):
        items = svc.list_artworks(status=ArtworkStatus.APPROVED)
        assert all(a.status == ArtworkStatus.APPROVED for a in items)

    def test_filter_artworks_combined(self, svc: LabelingManagementService):
        items = svc.list_artworks(label_id="LC-001", status=ArtworkStatus.APPROVED)
        assert all(a.label_id == "LC-001" and a.status == ArtworkStatus.APPROVED for a in items)

    def test_filter_artworks_no_match(self, svc: LabelingManagementService):
        items = svc.list_artworks(label_id="nonexistent")
        assert len(items) == 0

    def test_delete_artwork(self, svc: LabelingManagementService):
        assert svc.delete_artwork("LA-001") is True
        assert svc.get_artwork("LA-001") is None

    def test_delete_artwork_not_found(self, svc: LabelingManagementService):
        assert svc.delete_artwork("NONEXISTENT") is False

    def test_delete_artwork_reduces_count(self, svc: LabelingManagementService):
        count_before = len(svc.list_artworks())
        svc.delete_artwork("LA-001")
        count_after = len(svc.list_artworks())
        assert count_after == count_before - 1


# ===========================================================================
# LABEL CHANGE CRUD
# ===========================================================================


class TestLabelChangeCRUD:
    """Test CRUD operations for label changes."""

    def test_list_all_changes(self, svc: LabelingManagementService):
        items = svc.list_changes()
        assert len(items) == 12

    def test_get_change_by_id(self, svc: LabelingManagementService):
        change = svc.get_change("LCH-001")
        assert change is not None
        assert change.id == "LCH-001"

    def test_get_change_not_found(self, svc: LabelingManagementService):
        assert svc.get_change("NONEXISTENT") is None

    def test_filter_changes_by_trial(self, svc: LabelingManagementService):
        items = svc.list_changes(trial_id=EYLEA_TRIAL)
        assert all(c.trial_id == EYLEA_TRIAL for c in items)

    def test_filter_changes_by_label(self, svc: LabelingManagementService):
        items = svc.list_changes(label_id="LC-001")
        assert all(c.label_id == "LC-001" for c in items)

    def test_filter_changes_by_category(self, svc: LabelingManagementService):
        items = svc.list_changes(change_category=ChangeCategory.SAFETY_UPDATE)
        assert all(c.change_category == ChangeCategory.SAFETY_UPDATE for c in items)
        assert len(items) >= 3

    def test_filter_changes_combined(self, svc: LabelingManagementService):
        items = svc.list_changes(trial_id=LIBTAYO_TRIAL, change_category=ChangeCategory.SAFETY_UPDATE)
        assert all(c.trial_id == LIBTAYO_TRIAL and c.change_category == ChangeCategory.SAFETY_UPDATE for c in items)

    def test_filter_changes_no_match(self, svc: LabelingManagementService):
        items = svc.list_changes(trial_id="nonexistent")
        assert len(items) == 0

    def test_delete_change(self, svc: LabelingManagementService):
        assert svc.delete_change("LCH-001") is True
        assert svc.get_change("LCH-001") is None

    def test_delete_change_not_found(self, svc: LabelingManagementService):
        assert svc.delete_change("NONEXISTENT") is False

    def test_delete_change_reduces_count(self, svc: LabelingManagementService):
        count_before = len(svc.list_changes())
        svc.delete_change("LCH-001")
        count_after = len(svc.list_changes())
        assert count_after == count_before - 1


# ===========================================================================
# COUNTRY LABEL CRUD
# ===========================================================================


class TestCountryLabelCRUD:
    """Test CRUD operations for country labels."""

    def test_list_all_country_labels(self, svc: LabelingManagementService):
        items = svc.list_country_labels()
        assert len(items) == 12

    def test_get_country_label_by_id(self, svc: LabelingManagementService):
        cl = svc.get_country_label("CL-001")
        assert cl is not None
        assert cl.id == "CL-001"

    def test_get_country_label_not_found(self, svc: LabelingManagementService):
        assert svc.get_country_label("NONEXISTENT") is None

    def test_filter_country_labels_by_label(self, svc: LabelingManagementService):
        items = svc.list_country_labels(label_id="LC-001")
        assert all(cl.label_id == "LC-001" for cl in items)
        assert len(items) >= 3

    def test_filter_country_labels_by_country(self, svc: LabelingManagementService):
        items = svc.list_country_labels(country="US")
        assert all(cl.country == "US" for cl in items)
        assert len(items) >= 3

    def test_filter_country_labels_combined(self, svc: LabelingManagementService):
        items = svc.list_country_labels(label_id="LC-001", country="US")
        assert all(cl.label_id == "LC-001" and cl.country == "US" for cl in items)

    def test_filter_country_labels_no_match(self, svc: LabelingManagementService):
        items = svc.list_country_labels(label_id="nonexistent")
        assert len(items) == 0

    def test_delete_country_label(self, svc: LabelingManagementService):
        assert svc.delete_country_label("CL-001") is True
        assert svc.get_country_label("CL-001") is None

    def test_delete_country_label_not_found(self, svc: LabelingManagementService):
        assert svc.delete_country_label("NONEXISTENT") is False

    def test_delete_country_label_reduces_count(self, svc: LabelingManagementService):
        count_before = len(svc.list_country_labels())
        svc.delete_country_label("CL-001")
        count_after = len(svc.list_country_labels())
        assert count_after == count_before - 1


# ===========================================================================
# METRICS
# ===========================================================================


class TestMetrics:
    """Test labeling metrics computation."""

    def test_metrics_total_labels(self, svc: LabelingManagementService):
        metrics = svc.get_metrics()
        assert metrics.total_labels == 12

    def test_metrics_labels_by_status(self, svc: LabelingManagementService):
        metrics = svc.get_metrics()
        assert sum(metrics.labels_by_status.values()) == 12
        assert "effective" in metrics.labels_by_status

    def test_metrics_labels_by_section(self, svc: LabelingManagementService):
        metrics = svc.get_metrics()
        assert sum(metrics.labels_by_section.values()) == 12
        assert "indications_and_usage" in metrics.labels_by_section

    def test_metrics_total_negotiations(self, svc: LabelingManagementService):
        metrics = svc.get_metrics()
        assert metrics.total_negotiations == 10

    def test_metrics_negotiations_by_status(self, svc: LabelingManagementService):
        metrics = svc.get_metrics()
        assert sum(metrics.negotiations_by_status.values()) == 10

    def test_metrics_avg_negotiation_rounds(self, svc: LabelingManagementService):
        metrics = svc.get_metrics()
        assert metrics.avg_negotiation_rounds >= 0

    def test_metrics_total_artworks(self, svc: LabelingManagementService):
        metrics = svc.get_metrics()
        assert metrics.total_artworks == 12

    def test_metrics_artworks_by_status(self, svc: LabelingManagementService):
        metrics = svc.get_metrics()
        assert sum(metrics.artworks_by_status.values()) == 12

    def test_metrics_total_changes(self, svc: LabelingManagementService):
        metrics = svc.get_metrics()
        assert metrics.total_changes == 12

    def test_metrics_changes_by_category(self, svc: LabelingManagementService):
        metrics = svc.get_metrics()
        assert sum(metrics.changes_by_category.values()) == 12
        assert "safety_update" in metrics.changes_by_category

    def test_metrics_safety_changes(self, svc: LabelingManagementService):
        metrics = svc.get_metrics()
        assert metrics.safety_changes >= 4

    def test_metrics_total_country_labels(self, svc: LabelingManagementService):
        metrics = svc.get_metrics()
        assert metrics.total_country_labels == 12

    def test_metrics_countries_covered(self, svc: LabelingManagementService):
        metrics = svc.get_metrics()
        assert metrics.countries_covered >= 6

    def test_metrics_filter_by_trial_eylea(self, svc: LabelingManagementService):
        metrics = svc.get_metrics(trial_id=EYLEA_TRIAL)
        assert metrics.total_labels >= 3
        assert metrics.total_labels < 12

    def test_metrics_filter_by_trial_dupixent(self, svc: LabelingManagementService):
        metrics = svc.get_metrics(trial_id=DUPIXENT_TRIAL)
        assert metrics.total_labels >= 3

    def test_metrics_filter_by_trial_libtayo(self, svc: LabelingManagementService):
        metrics = svc.get_metrics(trial_id=LIBTAYO_TRIAL)
        assert metrics.total_labels >= 3

    def test_metrics_filter_nonexistent_trial(self, svc: LabelingManagementService):
        metrics = svc.get_metrics(trial_id="nonexistent")
        assert metrics.total_labels == 0
        assert metrics.total_negotiations == 0

    def test_metrics_after_delete(self, svc: LabelingManagementService):
        svc.delete_label("LC-001")
        metrics = svc.get_metrics()
        assert metrics.total_labels == 11


# ===========================================================================
# API: LABEL CONTENT ENDPOINTS
# ===========================================================================


class TestLabelContentAPI:
    """Test label content HTTP endpoints."""

    @pytest.mark.anyio
    async def test_list_labels(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labels")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_labels_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labels", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        assert all(item["trial_id"] == EYLEA_TRIAL for item in data["items"])

    @pytest.mark.anyio
    async def test_list_labels_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labels", params={"status": "effective"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(item["status"] == "effective" for item in data["items"])

    @pytest.mark.anyio
    async def test_list_labels_filter_section(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labels", params={"section": "indications_and_usage"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(item["section"] == "indications_and_usage" for item in data["items"])

    @pytest.mark.anyio
    async def test_list_labels_filter_no_match(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labels", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_label(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labels/LC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "LC-001"
        assert data["product_name"] == "EYLEA (aflibercept)"

    @pytest.mark.anyio
    async def test_get_label_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labels/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_label(self, client: AsyncClient):
        payload = _make_label_create()
        resp = await client.post(f"{API_PREFIX}/labels", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["product_name"] == "Test Product"
        assert data["status"] == "draft"
        assert data["id"].startswith("LC-")

    @pytest.mark.anyio
    async def test_create_label_increases_count(self, client: AsyncClient):
        payload = _make_label_create()
        await client.post(f"{API_PREFIX}/labels", json=payload)
        resp = await client.get(f"{API_PREFIX}/labels")
        assert resp.json()["total"] == 13

    @pytest.mark.anyio
    async def test_update_label(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/labels/LC-001", json={"content_text": "Updated content"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["content_text"] == "Updated content"

    @pytest.mark.anyio
    async def test_update_label_status(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/labels/LC-004", json={"status": "approved"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    @pytest.mark.anyio
    async def test_update_label_not_found(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/labels/NONEXISTENT", json={"content_text": "X"})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_label_approved_by_sets_date(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/labels/LC-004", json={"approved_by": "test_approver"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["approved_by"] == "test_approver"
        assert data["approved_date"] is not None

    @pytest.mark.anyio
    async def test_delete_label(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/labels/LC-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_label_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/labels/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_label_then_get_404(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/labels/LC-001")
        resp = await client.get(f"{API_PREFIX}/labels/LC-001")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_label_missing_fields(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/labels", json={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_label_invalid_section(self, client: AsyncClient):
        payload = _make_label_create(section="invalid_section")
        resp = await client.post(f"{API_PREFIX}/labels", json=payload)
        assert resp.status_code == 422


# ===========================================================================
# API: LABEL NEGOTIATION ENDPOINTS
# ===========================================================================


class TestLabelNegotiationAPI:
    """Test label negotiation HTTP endpoints."""

    @pytest.mark.anyio
    async def test_list_negotiations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/negotiations")
        assert resp.status_code == 200
        assert resp.json()["total"] == 10

    @pytest.mark.anyio
    async def test_list_negotiations_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/negotiations", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        assert all(item["trial_id"] == EYLEA_TRIAL for item in resp.json()["items"])

    @pytest.mark.anyio
    async def test_list_negotiations_filter_label(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/negotiations", params={"label_id": "LC-003"})
        assert resp.status_code == 200
        assert all(item["label_id"] == "LC-003" for item in resp.json()["items"])

    @pytest.mark.anyio
    async def test_list_negotiations_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/negotiations", params={"status": "agreed"})
        assert resp.status_code == 200
        assert all(item["status"] == "agreed" for item in resp.json()["items"])

    @pytest.mark.anyio
    async def test_list_negotiations_no_match(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/negotiations", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_negotiation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/negotiations/LN-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "LN-001"

    @pytest.mark.anyio
    async def test_get_negotiation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/negotiations/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_negotiation(self, client: AsyncClient):
        payload = _make_negotiation_create()
        resp = await client.post(f"{API_PREFIX}/negotiations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["health_authority"] == "FDA"
        assert data["status"] == "proposed"
        assert data["negotiation_rounds"] == 0
        assert data["id"].startswith("LN-")

    @pytest.mark.anyio
    async def test_create_negotiation_increases_count(self, client: AsyncClient):
        payload = _make_negotiation_create()
        await client.post(f"{API_PREFIX}/negotiations", json=payload)
        resp = await client.get(f"{API_PREFIX}/negotiations")
        assert resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_update_negotiation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/negotiations/LN-001",
            json={"status": "agreed", "agreed_text": "Agreed upon text."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "agreed"
        assert data["agreed_text"] == "Agreed upon text."

    @pytest.mark.anyio
    async def test_update_negotiation_rounds(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/negotiations/LN-001",
            json={"negotiation_rounds": 5},
        )
        assert resp.status_code == 200
        assert resp.json()["negotiation_rounds"] == 5

    @pytest.mark.anyio
    async def test_update_negotiation_not_found(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/negotiations/NONEXISTENT", json={"notes": "X"})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_negotiation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/negotiations/LN-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_negotiation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/negotiations/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_negotiation_then_get_404(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/negotiations/LN-001")
        resp = await client.get(f"{API_PREFIX}/negotiations/LN-001")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_negotiation_missing_fields(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/negotiations", json={"label_id": "LC-001"})
        assert resp.status_code == 422


# ===========================================================================
# API: LABEL ARTWORK ENDPOINTS
# ===========================================================================


class TestLabelArtworkAPI:
    """Test label artwork HTTP endpoints."""

    @pytest.mark.anyio
    async def test_list_artworks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/artworks")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_list_artworks_filter_label(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/artworks", params={"label_id": "LC-001"})
        assert resp.status_code == 200
        assert all(item["label_id"] == "LC-001" for item in resp.json()["items"])

    @pytest.mark.anyio
    async def test_list_artworks_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/artworks", params={"status": "approved"})
        assert resp.status_code == 200
        assert all(item["status"] == "approved" for item in resp.json()["items"])

    @pytest.mark.anyio
    async def test_list_artworks_no_match(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/artworks", params={"label_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_artwork(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/artworks/LA-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "LA-001"

    @pytest.mark.anyio
    async def test_get_artwork_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/artworks/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_artwork(self, client: AsyncClient):
        payload = _make_artwork_create()
        resp = await client.post(f"{API_PREFIX}/artworks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["artwork_type"] == "carton_label"
        assert data["status"] == "design"
        assert data["id"].startswith("LA-")

    @pytest.mark.anyio
    async def test_create_artwork_increases_count(self, client: AsyncClient):
        payload = _make_artwork_create()
        await client.post(f"{API_PREFIX}/artworks", json=payload)
        resp = await client.get(f"{API_PREFIX}/artworks")
        assert resp.json()["total"] == 13

    @pytest.mark.anyio
    async def test_update_artwork(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/artworks/LA-006",
            json={"status": "approved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["approved_date"] is not None

    @pytest.mark.anyio
    async def test_update_artwork_reviewer(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/artworks/LA-009",
            json={"reviewer": "new_reviewer"},
        )
        assert resp.status_code == 200
        assert resp.json()["reviewer"] == "new_reviewer"

    @pytest.mark.anyio
    async def test_update_artwork_not_found(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/artworks/NONEXISTENT", json={"reviewer": "X"})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_artwork(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/artworks/LA-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_artwork_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/artworks/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_artwork_then_get_404(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/artworks/LA-001")
        resp = await client.get(f"{API_PREFIX}/artworks/LA-001")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_artwork_missing_fields(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/artworks", json={"label_id": "LC-001"})
        assert resp.status_code == 422


# ===========================================================================
# API: LABEL CHANGE ENDPOINTS
# ===========================================================================


class TestLabelChangeAPI:
    """Test label change HTTP endpoints."""

    @pytest.mark.anyio
    async def test_list_changes(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/changes")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_list_changes_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/changes", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        assert all(item["trial_id"] == EYLEA_TRIAL for item in resp.json()["items"])

    @pytest.mark.anyio
    async def test_list_changes_filter_label(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/changes", params={"label_id": "LC-001"})
        assert resp.status_code == 200
        assert all(item["label_id"] == "LC-001" for item in resp.json()["items"])

    @pytest.mark.anyio
    async def test_list_changes_filter_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/changes", params={"change_category": "safety_update"})
        assert resp.status_code == 200
        assert all(item["change_category"] == "safety_update" for item in resp.json()["items"])

    @pytest.mark.anyio
    async def test_list_changes_no_match(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/changes", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_change(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/changes/LCH-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "LCH-001"

    @pytest.mark.anyio
    async def test_get_change_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/changes/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_change(self, client: AsyncClient):
        payload = _make_change_create()
        resp = await client.post(f"{API_PREFIX}/changes", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["change_category"] == "safety_update"
        assert data["status"] == "pending"
        assert data["safety_impact"] is True
        assert data["id"].startswith("LCH-")

    @pytest.mark.anyio
    async def test_create_change_increases_count(self, client: AsyncClient):
        payload = _make_change_create()
        await client.post(f"{API_PREFIX}/changes", json=payload)
        resp = await client.get(f"{API_PREFIX}/changes")
        assert resp.json()["total"] == 13

    @pytest.mark.anyio
    async def test_update_change(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/changes/LCH-001",
            json={"status": "completed", "approved_by": "vp_regulatory"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["approved_by"] == "vp_regulatory"

    @pytest.mark.anyio
    async def test_update_change_not_found(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/changes/NONEXISTENT", json={"status": "completed"})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_change(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/changes/LCH-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_change_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/changes/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_change_then_get_404(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/changes/LCH-001")
        resp = await client.get(f"{API_PREFIX}/changes/LCH-001")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_change_missing_fields(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/changes", json={"label_id": "LC-001"})
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_change_invalid_category(self, client: AsyncClient):
        payload = _make_change_create(change_category="invalid_category")
        resp = await client.post(f"{API_PREFIX}/changes", json=payload)
        assert resp.status_code == 422


# ===========================================================================
# API: COUNTRY LABEL ENDPOINTS
# ===========================================================================


class TestCountryLabelAPI:
    """Test country label HTTP endpoints."""

    @pytest.mark.anyio
    async def test_list_country_labels(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/country-labels")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_list_country_labels_filter_label(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/country-labels", params={"label_id": "LC-001"})
        assert resp.status_code == 200
        assert all(item["label_id"] == "LC-001" for item in resp.json()["items"])

    @pytest.mark.anyio
    async def test_list_country_labels_filter_country(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/country-labels", params={"country": "US"})
        assert resp.status_code == 200
        assert all(item["country"] == "US" for item in resp.json()["items"])

    @pytest.mark.anyio
    async def test_list_country_labels_no_match(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/country-labels", params={"label_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_country_label(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/country-labels/CL-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "CL-001"

    @pytest.mark.anyio
    async def test_get_country_label_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/country-labels/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_country_label(self, client: AsyncClient):
        payload = _make_country_label_create()
        resp = await client.post(f"{API_PREFIX}/country-labels", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["country"] == "DE"
        assert data["translation_status"] == "pending"
        assert data["id"].startswith("CL-")

    @pytest.mark.anyio
    async def test_create_country_label_increases_count(self, client: AsyncClient):
        payload = _make_country_label_create()
        await client.post(f"{API_PREFIX}/country-labels", json=payload)
        resp = await client.get(f"{API_PREFIX}/country-labels")
        assert resp.json()["total"] == 13

    @pytest.mark.anyio
    async def test_update_country_label(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/country-labels/CL-006",
            json={"translation_status": "in_progress"},
        )
        assert resp.status_code == 200
        assert resp.json()["translation_status"] == "in_progress"

    @pytest.mark.anyio
    async def test_update_country_label_deviation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/country-labels/CL-001",
            json={"deviation_from_core": "Minor difference in formulation statement"},
        )
        assert resp.status_code == 200
        assert resp.json()["deviation_from_core"] == "Minor difference in formulation statement"

    @pytest.mark.anyio
    async def test_update_country_label_not_found(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/country-labels/NONEXISTENT", json={"translation_status": "X"})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_country_label(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/country-labels/CL-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_country_label_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/country-labels/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_country_label_then_get_404(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/country-labels/CL-001")
        resp = await client.get(f"{API_PREFIX}/country-labels/CL-001")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_country_label_missing_fields(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/country-labels", json={"label_id": "LC-001"})
        assert resp.status_code == 422


# ===========================================================================
# API: METRICS ENDPOINT
# ===========================================================================


class TestMetricsAPI:
    """Test labeling metrics HTTP endpoint."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_labels"] == 12
        assert data["total_negotiations"] == 10
        assert data["total_artworks"] == 12
        assert data["total_changes"] == 12
        assert data["total_country_labels"] == 12

    @pytest.mark.anyio
    async def test_get_metrics_with_trial_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_labels"] >= 3
        assert data["total_labels"] < 12

    @pytest.mark.anyio
    async def test_get_metrics_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_labels"] == 0

    @pytest.mark.anyio
    async def test_metrics_labels_by_status_keys(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "effective" in data["labels_by_status"]

    @pytest.mark.anyio
    async def test_metrics_changes_by_category_keys(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "safety_update" in data["changes_by_category"]

    @pytest.mark.anyio
    async def test_metrics_countries_covered(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["countries_covered"] >= 6

    @pytest.mark.anyio
    async def test_metrics_safety_changes_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["safety_changes"] >= 4

    @pytest.mark.anyio
    async def test_metrics_avg_negotiation_rounds(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_negotiation_rounds"] >= 0


# ===========================================================================
# EDGE CASES & ADDITIONAL COVERAGE
# ===========================================================================


class TestEdgeCases:
    """Test edge cases and additional scenarios."""

    @pytest.mark.anyio
    async def test_create_and_read_back_label(self, client: AsyncClient):
        payload = _make_label_create(product_name="Edge Case Product")
        create_resp = await client.post(f"{API_PREFIX}/labels", json=payload)
        created_id = create_resp.json()["id"]
        get_resp = await client.get(f"{API_PREFIX}/labels/{created_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["product_name"] == "Edge Case Product"

    @pytest.mark.anyio
    async def test_create_and_delete_label(self, client: AsyncClient):
        payload = _make_label_create()
        create_resp = await client.post(f"{API_PREFIX}/labels", json=payload)
        created_id = create_resp.json()["id"]
        del_resp = await client.delete(f"{API_PREFIX}/labels/{created_id}")
        assert del_resp.status_code == 204
        get_resp = await client.get(f"{API_PREFIX}/labels/{created_id}")
        assert get_resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_and_read_back_negotiation(self, client: AsyncClient):
        payload = _make_negotiation_create(health_authority="PMDA")
        create_resp = await client.post(f"{API_PREFIX}/negotiations", json=payload)
        created_id = create_resp.json()["id"]
        get_resp = await client.get(f"{API_PREFIX}/negotiations/{created_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["health_authority"] == "PMDA"

    @pytest.mark.anyio
    async def test_create_and_read_back_artwork(self, client: AsyncClient):
        payload = _make_artwork_create(file_name="edge_test.ai")
        create_resp = await client.post(f"{API_PREFIX}/artworks", json=payload)
        created_id = create_resp.json()["id"]
        get_resp = await client.get(f"{API_PREFIX}/artworks/{created_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["file_name"] == "edge_test.ai"

    @pytest.mark.anyio
    async def test_create_and_read_back_change(self, client: AsyncClient):
        payload = _make_change_create(description="Edge case change")
        create_resp = await client.post(f"{API_PREFIX}/changes", json=payload)
        created_id = create_resp.json()["id"]
        get_resp = await client.get(f"{API_PREFIX}/changes/{created_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["description"] == "Edge case change"

    @pytest.mark.anyio
    async def test_create_and_read_back_country_label(self, client: AsyncClient):
        payload = _make_country_label_create(country="IN")
        create_resp = await client.post(f"{API_PREFIX}/country-labels", json=payload)
        created_id = create_resp.json()["id"]
        get_resp = await client.get(f"{API_PREFIX}/country-labels/{created_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["country"] == "IN"

    @pytest.mark.anyio
    async def test_update_then_verify_label(self, client: AsyncClient):
        await client.put(f"{API_PREFIX}/labels/LC-001", json={"reviewer": "new_reviewer"})
        resp = await client.get(f"{API_PREFIX}/labels/LC-001")
        assert resp.json()["reviewer"] == "new_reviewer"

    @pytest.mark.anyio
    async def test_update_then_verify_negotiation(self, client: AsyncClient):
        await client.put(f"{API_PREFIX}/negotiations/LN-002", json={"notes": "Test notes"})
        resp = await client.get(f"{API_PREFIX}/negotiations/LN-002")
        assert resp.json()["notes"] == "Test notes"

    @pytest.mark.anyio
    async def test_update_then_verify_artwork(self, client: AsyncClient):
        await client.put(f"{API_PREFIX}/artworks/LA-009", json={"print_specification": "New spec"})
        resp = await client.get(f"{API_PREFIX}/artworks/LA-009")
        assert resp.json()["print_specification"] == "New spec"

    @pytest.mark.anyio
    async def test_update_then_verify_change(self, client: AsyncClient):
        await client.put(f"{API_PREFIX}/changes/LCH-002", json={"status": "in_progress"})
        resp = await client.get(f"{API_PREFIX}/changes/LCH-002")
        assert resp.json()["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_update_then_verify_country_label(self, client: AsyncClient):
        await client.put(f"{API_PREFIX}/country-labels/CL-006", json={"translation_status": "completed"})
        resp = await client.get(f"{API_PREFIX}/country-labels/CL-006")
        assert resp.json()["translation_status"] == "completed"

    @pytest.mark.anyio
    async def test_double_delete_label(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/labels/LC-001")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/labels/LC-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_negotiation(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/negotiations/LN-001")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/negotiations/LN-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_artwork(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/artworks/LA-001")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/artworks/LA-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_change(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/changes/LCH-001")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/changes/LCH-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_country_label(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/country-labels/CL-001")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/country-labels/CL-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_create_label_with_optional_country(self, client: AsyncClient):
        payload = _make_label_create(country="EU")
        resp = await client.post(f"{API_PREFIX}/labels", json=payload)
        assert resp.status_code == 201
        assert resp.json()["country"] == "EU"

    @pytest.mark.anyio
    async def test_create_artwork_with_country(self, client: AsyncClient):
        payload = _make_artwork_create(country="JP")
        resp = await client.post(f"{API_PREFIX}/artworks", json=payload)
        assert resp.status_code == 201
        assert resp.json()["country"] == "JP"

    @pytest.mark.anyio
    async def test_create_change_no_safety_impact(self, client: AsyncClient):
        payload = _make_change_create(safety_impact=False, change_category="administrative")
        resp = await client.post(f"{API_PREFIX}/changes", json=payload)
        assert resp.status_code == 201
        assert resp.json()["safety_impact"] is False

    @pytest.mark.anyio
    async def test_create_change_with_affected_sections(self, client: AsyncClient):
        payload = _make_change_create(
            affected_sections=["warnings_and_precautions", "adverse_reactions", "boxed_warning"]
        )
        resp = await client.post(f"{API_PREFIX}/changes", json=payload)
        assert resp.status_code == 201
        assert len(resp.json()["affected_sections"]) == 3

    @pytest.mark.anyio
    async def test_create_country_label_with_requirements(self, client: AsyncClient):
        payload = _make_country_label_create(
            local_requirements=["Req 1", "Req 2", "Req 3"]
        )
        resp = await client.post(f"{API_PREFIX}/country-labels", json=payload)
        assert resp.status_code == 201
        assert len(resp.json()["local_requirements"]) == 3

    def test_service_singleton(self):
        svc1 = get_labeling_management_service()
        svc2 = get_labeling_management_service()
        assert svc1 is svc2

    def test_service_reset(self):
        svc1 = get_labeling_management_service()
        svc2 = reset_labeling_management_service()
        assert svc1 is not svc2

    @pytest.mark.anyio
    async def test_list_labels_with_all_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/labels",
            params={"trial_id": EYLEA_TRIAL, "status": "effective", "section": "indications_and_usage"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["status"] == "effective"
            assert item["section"] == "indications_and_usage"

    @pytest.mark.anyio
    async def test_list_negotiations_combined_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/negotiations",
            params={"trial_id": EYLEA_TRIAL, "label_id": "LC-003", "status": "under_discussion"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["label_id"] == "LC-003"
            assert item["status"] == "under_discussion"

    @pytest.mark.anyio
    async def test_list_artworks_combined_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/artworks",
            params={"label_id": "LC-001", "status": "approved"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["label_id"] == "LC-001"
            assert item["status"] == "approved"

    @pytest.mark.anyio
    async def test_list_changes_combined_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/changes",
            params={"trial_id": EYLEA_TRIAL, "label_id": "LC-001", "change_category": "safety_update"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["label_id"] == "LC-001"
            assert item["change_category"] == "safety_update"

    @pytest.mark.anyio
    async def test_list_country_labels_combined_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/country-labels",
            params={"label_id": "LC-001", "country": "US"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["label_id"] == "LC-001"
            assert item["country"] == "US"

    @pytest.mark.anyio
    async def test_get_label_has_created_at(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labels/LC-001")
        assert resp.status_code == 200
        assert "created_at" in resp.json()

    @pytest.mark.anyio
    async def test_get_negotiation_has_created_at(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/negotiations/LN-001")
        assert resp.status_code == 200
        assert "created_at" in resp.json()

    @pytest.mark.anyio
    async def test_get_artwork_has_created_at(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/artworks/LA-001")
        assert resp.status_code == 200
        assert "created_at" in resp.json()

    @pytest.mark.anyio
    async def test_get_change_has_created_at(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/changes/LCH-001")
        assert resp.status_code == 200
        assert "created_at" in resp.json()

    @pytest.mark.anyio
    async def test_get_country_label_has_created_at(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/country-labels/CL-001")
        assert resp.status_code == 200
        assert "created_at" in resp.json()

    @pytest.mark.anyio
    async def test_metrics_after_creating_records(self, client: AsyncClient):
        # Create new records
        await client.post(f"{API_PREFIX}/labels", json=_make_label_create())
        await client.post(f"{API_PREFIX}/negotiations", json=_make_negotiation_create())
        await client.post(f"{API_PREFIX}/artworks", json=_make_artwork_create())
        await client.post(f"{API_PREFIX}/changes", json=_make_change_create())
        await client.post(f"{API_PREFIX}/country-labels", json=_make_country_label_create())
        # Check metrics
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_labels"] == 13
        assert data["total_negotiations"] == 11
        assert data["total_artworks"] == 13
        assert data["total_changes"] == 13
        assert data["total_country_labels"] == 13

    @pytest.mark.anyio
    async def test_metrics_after_deleting_records(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/labels/LC-001")
        await client.delete(f"{API_PREFIX}/negotiations/LN-001")
        await client.delete(f"{API_PREFIX}/artworks/LA-001")
        await client.delete(f"{API_PREFIX}/changes/LCH-001")
        await client.delete(f"{API_PREFIX}/country-labels/CL-001")
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_labels"] == 11
        assert data["total_negotiations"] == 9
        assert data["total_artworks"] == 11
        assert data["total_changes"] == 11
        assert data["total_country_labels"] == 11

    @pytest.mark.anyio
    async def test_label_superseded_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labels", params={"status": "superseded"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1
        assert all(item["status"] == "superseded" for item in items)

    @pytest.mark.anyio
    async def test_negotiation_disputed_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/negotiations", params={"status": "disputed"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1

    @pytest.mark.anyio
    async def test_artwork_design_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/artworks", params={"status": "design"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 2

    @pytest.mark.anyio
    async def test_change_new_indication_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/changes", params={"change_category": "new_indication"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 2

    @pytest.mark.anyio
    async def test_country_labels_japan(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/country-labels", params={"country": "JP"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1

    @pytest.mark.anyio
    async def test_create_label_all_sections(self, client: AsyncClient):
        """Test creating labels for each section type."""
        for section in LabelSection:
            payload = _make_label_create(section=section.value)
            resp = await client.post(f"{API_PREFIX}/labels", json=payload)
            assert resp.status_code == 201
            assert resp.json()["section"] == section.value

    @pytest.mark.anyio
    async def test_create_negotiation_all_statuses_via_update(self, client: AsyncClient):
        """Test updating negotiation through all statuses."""
        payload = _make_negotiation_create()
        resp = await client.post(f"{API_PREFIX}/negotiations", json=payload)
        neg_id = resp.json()["id"]
        for status in NegotiationStatus:
            resp = await client.put(f"{API_PREFIX}/negotiations/{neg_id}", json={"status": status.value})
            assert resp.status_code == 200
            assert resp.json()["status"] == status.value

    @pytest.mark.anyio
    async def test_create_artwork_all_statuses_via_update(self, client: AsyncClient):
        """Test updating artwork through all statuses."""
        payload = _make_artwork_create()
        resp = await client.post(f"{API_PREFIX}/artworks", json=payload)
        art_id = resp.json()["id"]
        for status in ArtworkStatus:
            resp = await client.put(f"{API_PREFIX}/artworks/{art_id}", json={"status": status.value})
            assert resp.status_code == 200
            assert resp.json()["status"] == status.value

    @pytest.mark.anyio
    async def test_create_change_all_categories(self, client: AsyncClient):
        """Test creating changes for each category."""
        for cat in ChangeCategory:
            payload = _make_change_create(change_category=cat.value)
            resp = await client.post(f"{API_PREFIX}/changes", json=payload)
            assert resp.status_code == 201
            assert resp.json()["change_category"] == cat.value
