"""Tests for Product Licensure & Market Authorization.

Covers:
- Seed data verification (applications, country authorizations, labels, changes, timelines)
- Regulatory application CRUD (create, read, update, delete, list, filter)
- Application lifecycle (submit, approve, status transitions)
- Country authorization CRUD and workflow
- Product label management (create, update, approve, supersede)
- Post-approval change filing and lifecycle
- Market access timeline milestones
- Product status by country (aggregate view)
- Licensure metrics computation
- Error handling (404s, 400s, invalid state transitions)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.product_licensure import (
    ApplicationApproval,
    ApplicationStatus,
    ApplicationSubmit,
    ApplicationType,
    ChangeType,
    CountryAuthorizationCreate,
    CountryAuthorizationUpdate,
    LabelStatus,
    MarketAccessTimelineCreate,
    MarketAccessTimelineUpdate,
    MarketStatus,
    MilestoneStatus,
    PostApprovalChangeCreate,
    PostApprovalChangeUpdate,
    ProductLabelCreate,
    ProductLabelUpdate,
    RegulatoryApplicationCreate,
    RegulatoryApplicationUpdate,
    SubmissionType,
)
from app.services.product_licensure_service import (
    ProductLicensureService,
    get_product_licensure_service,
    reset_product_licensure_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1/product-licensure"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_product_licensure_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ProductLicensureService:
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


def _make_app_create(**overrides) -> dict:
    defaults = {
        "product_name": "TestDrug (testumab)",
        "application_type": "nda",
        "application_number": "NDA-999999",
        "regulatory_authority": "FDA",
        "country": "US",
        "review_type": "standard",
        "therapeutic_area": "Cardiology",
        "indication": "Chronic heart failure",
        "sponsor_contact": "Dr. Test Contact",
    }
    defaults.update(overrides)
    return defaults


def _make_ca_create(**overrides) -> dict:
    defaults = {
        "application_id": "APP-001",
        "country": "KR",
        "authority_name": "MFDS (Ministry of Food and Drug Safety)",
    }
    defaults.update(overrides)
    return defaults


def _make_label_create(**overrides) -> dict:
    defaults = {
        "application_id": "APP-001",
        "product_name": "Dupixent (dupilumab)",
        "version": "4.0",
        "country": "US",
        "language": "en",
        "sections_changed": ["Dosage and Administration"],
        "safety_updates": ["New pediatric safety data"],
    }
    defaults.update(overrides)
    return defaults


def _make_pac_create(**overrides) -> dict:
    defaults = {
        "application_id": "APP-001",
        "change_type": "labeling",
        "description": "Update to include new drug interaction data",
        "impact_assessment": "Low impact on prescribing behavior",
        "affected_countries": ["US", "CA"],
        "regulatory_reference": "CBE-0 Supplement",
    }
    defaults.update(overrides)
    return defaults


def _make_timeline_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "application_id": "APP-002",
        "country": "US",
        "milestone_name": "Pre-Launch Manufacturing Validation",
        "planned_date": (now + timedelta(days=90)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_applications_count(self, svc: ProductLicensureService):
        apps = svc.list_applications()
        assert len(apps) == 5

    def test_seed_applications_types(self, svc: ProductLicensureService):
        apps = svc.list_applications()
        types = {a.application_type for a in apps}
        assert ApplicationType.BLA in types
        assert ApplicationType.NDA in types
        assert ApplicationType.IND in types
        assert ApplicationType.MAA in types

    def test_seed_applications_statuses(self, svc: ProductLicensureService):
        apps = svc.list_applications()
        statuses = {a.status for a in apps}
        assert ApplicationStatus.APPROVED in statuses
        assert ApplicationStatus.UNDER_REVIEW in statuses
        assert ApplicationStatus.SUBMITTED in statuses
        assert ApplicationStatus.PRE_SUBMISSION in statuses

    def test_seed_country_authorizations_count(self, svc: ProductLicensureService):
        cas = svc.list_country_authorizations()
        assert len(cas) == 9

    def test_seed_country_authorizations_statuses(self, svc: ProductLicensureService):
        cas = svc.list_country_authorizations()
        statuses = {c.market_status for c in cas}
        assert MarketStatus.LAUNCHED in statuses
        assert MarketStatus.APPROVED in statuses
        assert MarketStatus.UNDER_REVIEW in statuses
        assert MarketStatus.FILED in statuses
        assert MarketStatus.NOT_FILED in statuses

    def test_seed_labels_count(self, svc: ProductLicensureService):
        labels = svc.list_labels()
        assert len(labels) == 4

    def test_seed_labels_statuses(self, svc: ProductLicensureService):
        labels = svc.list_labels()
        statuses = {l.status for l in labels}
        assert LabelStatus.EFFECTIVE in statuses
        assert LabelStatus.SUPERSEDED in statuses
        assert LabelStatus.DRAFT in statuses

    def test_seed_post_approval_changes_count(self, svc: ProductLicensureService):
        pacs = svc.list_post_approval_changes()
        assert len(pacs) == 3

    def test_seed_post_approval_change_types(self, svc: ProductLicensureService):
        pacs = svc.list_post_approval_changes()
        types = {p.change_type for p in pacs}
        assert ChangeType.LABELING in types
        assert ChangeType.MANUFACTURING in types
        assert ChangeType.INDICATION in types

    def test_seed_timelines_count(self, svc: ProductLicensureService):
        tls = svc.list_timelines()
        assert len(tls) == 10

    def test_seed_timelines_statuses(self, svc: ProductLicensureService):
        tls = svc.list_timelines()
        statuses = {t.status for t in tls}
        assert MilestoneStatus.COMPLETED in statuses
        assert MilestoneStatus.IN_PROGRESS in statuses
        assert MilestoneStatus.NOT_STARTED in statuses
        assert MilestoneStatus.DELAYED in statuses
        assert MilestoneStatus.AT_RISK in statuses

    def test_seed_dupixent_bla_approved(self, svc: ProductLicensureService):
        app = svc.get_application("APP-001")
        assert app is not None
        assert app.product_name == "Dupixent (dupilumab)"
        assert app.application_type == ApplicationType.BLA
        assert app.status == ApplicationStatus.APPROVED

    def test_seed_eylea_under_review(self, svc: ProductLicensureService):
        app = svc.get_application("APP-002")
        assert app is not None
        assert app.product_name == "Eylea (aflibercept)"
        assert app.status == ApplicationStatus.UNDER_REVIEW


# =====================================================================
# APPLICATION CRUD
# =====================================================================


class TestApplicationCrud:
    """Test application create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_applications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/applications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 5

    @pytest.mark.anyio
    async def test_list_applications_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/applications", params={"application_type": "bla"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["application_type"] == "bla"

    @pytest.mark.anyio
    async def test_list_applications_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/applications", params={"status": "approved"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "approved"

    @pytest.mark.anyio
    async def test_list_applications_filter_product_name(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/applications", params={"product_name": "Dupixent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert "Dupixent" in item["product_name"]

    @pytest.mark.anyio
    async def test_list_applications_filter_country(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/applications", params={"country": "EU"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["country"] == "EU"

    @pytest.mark.anyio
    async def test_get_application(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/applications/APP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "APP-001"
        assert data["product_name"] == "Dupixent (dupilumab)"

    @pytest.mark.anyio
    async def test_get_application_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/applications/APP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_application(self, client: AsyncClient):
        payload = _make_app_create()
        resp = await client.post(f"{API_PREFIX}/applications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["product_name"] == "TestDrug (testumab)"
        assert data["application_type"] == "nda"
        assert data["id"].startswith("APP-")
        assert data["status"] == "pre_submission"

    @pytest.mark.anyio
    async def test_create_application_bla(self, client: AsyncClient):
        payload = _make_app_create(application_type="bla", application_number="BLA-999999")
        resp = await client.post(f"{API_PREFIX}/applications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["application_type"] == "bla"

    @pytest.mark.anyio
    async def test_update_application(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/applications/APP-002",
            json={"review_type": "priority", "assigned_reviewer": "Dr. New Reviewer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["review_type"] == "priority"
        assert data["assigned_reviewer"] == "Dr. New Reviewer"

    @pytest.mark.anyio
    async def test_update_application_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/applications/APP-NONEXISTENT",
            json={"review_type": "priority"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_application(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/applications/APP-005")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/applications/APP-005")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_application_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/applications/APP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# APPLICATION LIFECYCLE
# =====================================================================


class TestApplicationLifecycle:
    """Test application submission and approval workflows."""

    @pytest.mark.anyio
    async def test_submit_application(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {"submission_date": now.isoformat()}
        resp = await client.post(f"{API_PREFIX}/applications/APP-005/submit", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "submitted"
        assert data["submission_date"] is not None

    @pytest.mark.anyio
    async def test_submit_application_not_found(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {"submission_date": now.isoformat()}
        resp = await client.post(f"{API_PREFIX}/applications/APP-NONEXISTENT/submit", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_submit_application_invalid_status(self, client: AsyncClient):
        """Cannot submit an already approved application."""
        now = datetime.now(timezone.utc)
        payload = {"submission_date": now.isoformat()}
        resp = await client.post(f"{API_PREFIX}/applications/APP-001/submit", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_record_approval(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {
            "approval_date": now.isoformat(),
            "conditions": "Post-marketing study required",
            "assigned_reviewer": "Dr. Approval Reviewer",
        }
        resp = await client.post(f"{API_PREFIX}/applications/APP-002/approve", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"

    @pytest.mark.anyio
    async def test_record_approval_not_found(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {"approval_date": now.isoformat()}
        resp = await client.post(f"{API_PREFIX}/applications/APP-NONEXISTENT/approve", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_record_approval_invalid_status(self, client: AsyncClient):
        """Cannot approve a pre-submission application."""
        now = datetime.now(timezone.utc)
        payload = {"approval_date": now.isoformat()}
        resp = await client.post(f"{API_PREFIX}/applications/APP-005/approve", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_record_approval_already_approved(self, client: AsyncClient):
        """Cannot approve an already approved application."""
        now = datetime.now(timezone.utc)
        payload = {"approval_date": now.isoformat()}
        resp = await client.post(f"{API_PREFIX}/applications/APP-001/approve", json=payload)
        assert resp.status_code == 400

    def test_submit_from_complete_response(self, svc: ProductLicensureService):
        """Can re-submit from complete_response status."""
        # First set status to complete_response
        svc.update_application(
            "APP-003",
            RegulatoryApplicationUpdate(status=ApplicationStatus.COMPLETE_RESPONSE),
        )
        now = datetime.now(timezone.utc)
        result = svc.submit_application(
            "APP-003", ApplicationSubmit(submission_date=now)
        )
        assert result is not None
        assert result.status == ApplicationStatus.SUBMITTED

    def test_approve_from_submitted(self, svc: ProductLicensureService):
        """Can approve from submitted status."""
        now = datetime.now(timezone.utc)
        result = svc.record_approval(
            "APP-003", ApplicationApproval(approval_date=now)
        )
        assert result is not None
        assert result.status == ApplicationStatus.APPROVED


# =====================================================================
# COUNTRY AUTHORIZATIONS
# =====================================================================


class TestCountryAuthorizations:
    """Test country authorization CRUD operations."""

    @pytest.mark.anyio
    async def test_list_country_authorizations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/country-authorizations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 9

    @pytest.mark.anyio
    async def test_list_ca_filter_application(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/country-authorizations", params={"application_id": "APP-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["application_id"] == "APP-001"

    @pytest.mark.anyio
    async def test_list_ca_filter_country(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/country-authorizations", params={"country": "US"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["country"] == "US"

    @pytest.mark.anyio
    async def test_list_ca_filter_market_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/country-authorizations", params={"market_status": "launched"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["market_status"] == "launched"

    @pytest.mark.anyio
    async def test_get_country_authorization(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/country-authorizations/CA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CA-001"
        assert data["country"] == "US"
        assert data["market_status"] == "launched"

    @pytest.mark.anyio
    async def test_get_ca_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/country-authorizations/CA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_country_authorization(self, client: AsyncClient):
        payload = _make_ca_create()
        resp = await client.post(f"{API_PREFIX}/country-authorizations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["country"] == "KR"
        assert data["market_status"] == "not_filed"
        assert data["id"].startswith("CA-")

    @pytest.mark.anyio
    async def test_create_ca_invalid_application(self, client: AsyncClient):
        payload = _make_ca_create(application_id="APP-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/country-authorizations", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_country_authorization(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/country-authorizations/CA-004",
            json={
                "market_status": "launched",
                "launch_date": now.isoformat(),
                "label_approved": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["market_status"] == "launched"
        assert data["label_approved"] is True
        assert data["launch_date"] is not None

    @pytest.mark.anyio
    async def test_update_ca_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/country-authorizations/CA-NONEXISTENT",
            json={"market_status": "approved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_country_authorization(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/country-authorizations/CA-009")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/country-authorizations/CA-009")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_ca_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/country-authorizations/CA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# PRODUCT LABELS
# =====================================================================


class TestProductLabels:
    """Test product label management."""

    @pytest.mark.anyio
    async def test_list_labels(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labels")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4

    @pytest.mark.anyio
    async def test_list_labels_filter_application(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labels", params={"application_id": "APP-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["application_id"] == "APP-001"

    @pytest.mark.anyio
    async def test_list_labels_filter_country(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labels", params={"country": "US"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["country"] == "US"

    @pytest.mark.anyio
    async def test_list_labels_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labels", params={"status": "effective"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "effective"

    @pytest.mark.anyio
    async def test_get_label(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labels/LBL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "LBL-001"
        assert data["version"] == "3.0"
        assert data["status"] == "effective"

    @pytest.mark.anyio
    async def test_get_label_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labels/LBL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_label(self, client: AsyncClient):
        payload = _make_label_create()
        resp = await client.post(f"{API_PREFIX}/labels", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["version"] == "4.0"
        assert data["status"] == "draft"
        assert data["id"].startswith("LBL-")

    @pytest.mark.anyio
    async def test_create_label_invalid_application(self, client: AsyncClient):
        payload = _make_label_create(application_id="APP-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/labels", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_label_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/labels/LBL-004",
            json={"status": "under_review"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "under_review"

    @pytest.mark.anyio
    async def test_update_label_approve_auto_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/labels/LBL-004",
            json={"status": "approved", "approved_by": "Dr. Test Approver"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["approved_date"] is not None
        assert data["approved_by"] == "Dr. Test Approver"

    @pytest.mark.anyio
    async def test_update_label_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/labels/LBL-NONEXISTENT",
            json={"status": "approved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_label(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/labels/LBL-002")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/labels/LBL-002")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_label_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/labels/LBL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_label_has_contraindications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labels/LBL-004")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["contraindications"]) > 0

    @pytest.mark.anyio
    async def test_label_sections_changed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labels/LBL-001")
        data = resp.json()
        assert len(data["sections_changed"]) > 0

    @pytest.mark.anyio
    async def test_label_safety_updates(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labels/LBL-001")
        data = resp.json()
        assert len(data["safety_updates"]) > 0


# =====================================================================
# LABEL LIFECYCLE
# =====================================================================


class TestLabelLifecycle:
    """Test label lifecycle: draft -> under_review -> approved -> effective -> superseded."""

    def test_label_lifecycle_full(self, svc: ProductLicensureService):
        # Start with draft label
        label = svc.get_label("LBL-004")
        assert label is not None
        assert label.status == LabelStatus.DRAFT

        # Move to under_review
        updated = svc.update_label("LBL-004", ProductLabelUpdate(status=LabelStatus.UNDER_REVIEW))
        assert updated is not None
        assert updated.status == LabelStatus.UNDER_REVIEW

        # Approve
        updated = svc.update_label(
            "LBL-004",
            ProductLabelUpdate(status=LabelStatus.APPROVED, approved_by="Dr. Reviewer"),
        )
        assert updated is not None
        assert updated.status == LabelStatus.APPROVED
        assert updated.approved_date is not None
        assert updated.approved_by == "Dr. Reviewer"

        # Make effective
        now = datetime.now(timezone.utc)
        updated = svc.update_label(
            "LBL-004",
            ProductLabelUpdate(status=LabelStatus.EFFECTIVE, effective_date=now),
        )
        assert updated is not None
        assert updated.status == LabelStatus.EFFECTIVE

        # Supersede
        updated = svc.update_label("LBL-004", ProductLabelUpdate(status=LabelStatus.SUPERSEDED))
        assert updated is not None
        assert updated.status == LabelStatus.SUPERSEDED


# =====================================================================
# POST-APPROVAL CHANGES
# =====================================================================


class TestPostApprovalChanges:
    """Test post-approval change filing and management."""

    @pytest.mark.anyio
    async def test_list_post_approval_changes(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/post-approval-changes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_pac_filter_application(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/post-approval-changes", params={"application_id": "APP-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["application_id"] == "APP-001"

    @pytest.mark.anyio
    async def test_list_pac_filter_change_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/post-approval-changes", params={"change_type": "labeling"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["change_type"] == "labeling"

    @pytest.mark.anyio
    async def test_list_pac_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/post-approval-changes", params={"status": "under_review"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "under_review"

    @pytest.mark.anyio
    async def test_get_post_approval_change(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/post-approval-changes/PAC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PAC-001"
        assert data["change_type"] == "labeling"
        assert data["status"] == "approved"

    @pytest.mark.anyio
    async def test_get_pac_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/post-approval-changes/PAC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_file_post_approval_change(self, client: AsyncClient):
        payload = _make_pac_create()
        resp = await client.post(f"{API_PREFIX}/post-approval-changes", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["change_type"] == "labeling"
        assert data["status"] == "pre_submission"
        assert data["id"].startswith("PAC-")

    @pytest.mark.anyio
    async def test_file_pac_invalid_application(self, client: AsyncClient):
        payload = _make_pac_create(application_id="APP-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/post-approval-changes", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_post_approval_change(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/post-approval-changes/PAC-002",
            json={
                "status": "approved",
                "approval_date": now.isoformat(),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["approval_date"] is not None

    @pytest.mark.anyio
    async def test_update_pac_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/post-approval-changes/PAC-NONEXISTENT",
            json={"status": "approved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_post_approval_change(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/post-approval-changes/PAC-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/post-approval-changes/PAC-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_pac_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/post-approval-changes/PAC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_pac_affected_countries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/post-approval-changes/PAC-002")
        data = resp.json()
        assert len(data["affected_countries"]) > 0
        assert "US" in data["affected_countries"]

    @pytest.mark.anyio
    async def test_file_pac_manufacturing(self, client: AsyncClient):
        payload = _make_pac_create(
            change_type="manufacturing",
            description="New packaging facility qualification",
            affected_countries=["US"],
        )
        resp = await client.post(f"{API_PREFIX}/post-approval-changes", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["change_type"] == "manufacturing"


# =====================================================================
# MARKET ACCESS TIMELINES
# =====================================================================


class TestMarketAccessTimelines:
    """Test market access timeline milestone management."""

    @pytest.mark.anyio
    async def test_list_timelines(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/timelines")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_timelines_filter_application(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/timelines", params={"application_id": "APP-002"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["application_id"] == "APP-002"

    @pytest.mark.anyio
    async def test_list_timelines_filter_country(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/timelines", params={"country": "JP"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["country"] == "JP"

    @pytest.mark.anyio
    async def test_list_timelines_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/timelines", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_timelines_sorted_by_planned_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/timelines")
        data = resp.json()
        dates = [item["planned_date"] for item in data["items"]]
        assert dates == sorted(dates)

    @pytest.mark.anyio
    async def test_get_timeline(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/timelines/TL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TL-001"
        assert data["milestone_name"] == "Pre-NDA Meeting with FDA"
        assert data["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_timeline_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/timelines/TL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_timeline(self, client: AsyncClient):
        payload = _make_timeline_create()
        resp = await client.post(f"{API_PREFIX}/timelines", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["milestone_name"] == "Pre-Launch Manufacturing Validation"
        assert data["status"] == "not_started"
        assert data["id"].startswith("TL-")

    @pytest.mark.anyio
    async def test_create_timeline_invalid_application(self, client: AsyncClient):
        payload = _make_timeline_create(application_id="APP-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/timelines", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_timeline(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/timelines/TL-005",
            json={"status": "completed", "notes": "Advisory committee approved unanimously"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["actual_date"] is not None

    @pytest.mark.anyio
    async def test_update_timeline_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/timelines/TL-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_timeline(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/timelines/TL-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/timelines/TL-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_timeline_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/timelines/TL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_timeline_has_dependencies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/timelines/TL-002")
        data = resp.json()
        assert "TL-001" in data["dependencies"]

    @pytest.mark.anyio
    async def test_create_timeline_with_dependencies(self, client: AsyncClient):
        payload = _make_timeline_create(
            milestone_name="Post-Approval Monitoring",
            dependencies=["TL-006"],
            notes="Dependent on PDUFA outcome",
        )
        resp = await client.post(f"{API_PREFIX}/timelines", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert "TL-006" in data["dependencies"]

    def test_update_timeline_auto_date_on_complete(self, svc: ProductLicensureService):
        """Completing a milestone should auto-set actual_date."""
        tl = svc.get_timeline("TL-005")
        assert tl is not None
        assert tl.actual_date is None

        updated = svc.update_timeline(
            "TL-005", MarketAccessTimelineUpdate(status=MilestoneStatus.COMPLETED)
        )
        assert updated is not None
        assert updated.actual_date is not None


# =====================================================================
# PRODUCT STATUS BY COUNTRY
# =====================================================================


class TestProductCountryStatus:
    """Test aggregated product status by country."""

    @pytest.mark.anyio
    async def test_get_country_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/applications/APP-001/country-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["product_name"] == "Dupixent (dupilumab)"
        assert data["application_id"] == "APP-001"
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_get_country_status_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/applications/APP-NONEXISTENT/country-status")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_country_status_has_market_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/applications/APP-001/country-status")
        data = resp.json()
        for country in data["countries"]:
            assert "market_status" in country
            assert "authority_name" in country
            assert "country" in country

    @pytest.mark.anyio
    async def test_country_status_app_004_has_multiple_countries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/applications/APP-004/country-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 5  # DE, FR, GB, JP, AU, BR
        countries = {c["country"] for c in data["countries"]}
        assert "DE" in countries
        assert "FR" in countries

    @pytest.mark.anyio
    async def test_country_status_pending_changes(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/applications/APP-004/country-status")
        data = resp.json()
        # PAC-002 (manufacturing) affects EU countries, PAC-003 (indication) affects DE, FR, GB
        de_status = next(c for c in data["countries"] if c["country"] == "DE")
        assert de_status["pending_changes"] >= 1

    @pytest.mark.anyio
    async def test_country_status_next_milestone(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/applications/APP-002/country-status")
        data = resp.json()
        us_status = next(c for c in data["countries"] if c["country"] == "US")
        assert us_status["next_milestone"] is not None


# =====================================================================
# METRICS
# =====================================================================


class TestLicensureMetrics:
    """Test licensure metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_applications"] == 5
        assert data["total_country_authorizations"] == 9
        assert data["total_labels"] == 4
        assert data["total_post_approval_changes"] == 3
        assert data["total_milestones"] == 10

    @pytest.mark.anyio
    async def test_metrics_applications_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_type = data["applications_by_type"]
        total_by_type = sum(by_type.values())
        assert total_by_type == data["total_applications"]

    @pytest.mark.anyio
    async def test_metrics_applications_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["applications_by_status"]
        total_by_status = sum(by_status.values())
        assert total_by_status == data["total_applications"]

    @pytest.mark.anyio
    async def test_metrics_countries_approved(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["countries_approved"] >= data["countries_launched"]

    @pytest.mark.anyio
    async def test_metrics_labels_effective(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["labels_effective"] <= data["total_labels"]

    @pytest.mark.anyio
    async def test_metrics_pending_changes(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["pending_changes"] <= data["total_post_approval_changes"]

    @pytest.mark.anyio
    async def test_metrics_milestone_counts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["milestones_completed"] >= 0
        assert data["milestones_delayed"] >= 0
        assert data["milestones_at_risk"] >= 0

    def test_metrics_avg_approval_time(self, svc: ProductLicensureService):
        metrics = svc.get_metrics()
        assert metrics.avg_approval_time_days is not None
        assert metrics.avg_approval_time_days > 0

    def test_metrics_consistency(self, svc: ProductLicensureService):
        metrics = svc.get_metrics()
        # Approved + launched counts
        cas = svc.list_country_authorizations()
        approved_or_launched = sum(
            1 for c in cas
            if c.market_status in (MarketStatus.APPROVED, MarketStatus.LAUNCHED)
        )
        assert metrics.countries_approved == approved_or_launched


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_product_licensure_service()
        svc2 = get_product_licensure_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_product_licensure_service()
        svc2 = reset_product_licensure_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_product_licensure_service()
        svc.delete_application("APP-001")
        assert svc.get_application("APP-001") is None
        svc2 = reset_product_licensure_service()
        assert svc2.get_application("APP-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_applications_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/applications")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_ca_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/country-authorizations")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_labels_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labels")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_pac_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/post-approval-changes")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_timelines_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/timelines")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_application_all_fields(self, client: AsyncClient):
        payload = _make_app_create(
            product_name="FullDrug",
            application_type="maa",
            application_number="MAA-123456",
            regulatory_authority="EMA",
            country="EU",
            review_type="accelerated",
            therapeutic_area="Oncology",
            indication="Melanoma",
            sponsor_contact="Dr. Full Contact",
            submission_type="amendment",
        )
        resp = await client.post(f"{API_PREFIX}/applications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["application_type"] == "maa"
        assert data["submission_type"] == "amendment"

    @pytest.mark.anyio
    async def test_create_label_with_boxed_warning(self, client: AsyncClient):
        payload = _make_label_create(
            boxed_warning="WARNING: Risk of serious infections",
            contraindications=["Active serious infection", "Known hypersensitivity"],
        )
        resp = await client.post(f"{API_PREFIX}/labels", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["boxed_warning"] == "WARNING: Risk of serious infections"
        assert len(data["contraindications"]) == 2

    @pytest.mark.anyio
    async def test_create_ca_with_patent_expiry(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = _make_ca_create(
            patent_expiry=(now + timedelta(days=3650)).isoformat(),
        )
        resp = await client.post(f"{API_PREFIX}/country-authorizations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patent_expiry"] is not None

    @pytest.mark.anyio
    async def test_update_ca_filing_date(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/country-authorizations/CA-009",
            json={
                "filing_date": now.isoformat(),
                "market_status": "filed",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["market_status"] == "filed"
        assert data["filing_date"] is not None

    @pytest.mark.anyio
    async def test_pac_with_regulatory_reference(self, client: AsyncClient):
        payload = _make_pac_create(
            change_type="safety_update",
            regulatory_reference="FDA Safety Communication 2026-01",
        )
        resp = await client.post(f"{API_PREFIX}/post-approval-changes", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["regulatory_reference"] == "FDA Safety Communication 2026-01"

    def test_application_updated_at_changes(self, svc: ProductLicensureService):
        app = svc.get_application("APP-002")
        assert app is not None
        original_updated = app.updated_at

        import time
        time.sleep(0.01)

        updated = svc.update_application(
            "APP-002",
            RegulatoryApplicationUpdate(review_type="priority"),
        )
        assert updated is not None
        assert updated.updated_at > original_updated

    def test_create_and_retrieve_application(self, svc: ProductLicensureService):
        created = svc.create_application(
            RegulatoryApplicationCreate(
                product_name="NewDrug",
                application_type=ApplicationType.ABBREVIATED_NDA,
                application_number="ANDA-888888",
                regulatory_authority="FDA",
                country="US",
                therapeutic_area="Neurology",
                indication="Epilepsy",
                sponsor_contact="Dr. New",
            )
        )
        assert created.id.startswith("APP-")
        retrieved = svc.get_application(created.id)
        assert retrieved is not None
        assert retrieved.product_name == "NewDrug"
        assert retrieved.application_type == ApplicationType.ABBREVIATED_NDA

    def test_list_applications_filter_no_match(self, svc: ProductLicensureService):
        result = svc.list_applications(product_name="NonexistentDrug")
        assert len(result) == 0

    def test_list_ca_filter_no_match(self, svc: ProductLicensureService):
        result = svc.list_country_authorizations(country="ZZ")
        assert len(result) == 0

    def test_list_labels_filter_no_match(self, svc: ProductLicensureService):
        result = svc.list_labels(country="ZZ")
        assert len(result) == 0

    def test_list_timelines_filter_no_match(self, svc: ProductLicensureService):
        result = svc.list_timelines(country="ZZ")
        assert len(result) == 0

    def test_list_pac_filter_no_match(self, svc: ProductLicensureService):
        result = svc.list_post_approval_changes(
            change_type=ChangeType.FORMULATION
        )
        assert len(result) == 0


# =====================================================================
# APPLICATION TYPE ENUMS
# =====================================================================


class TestApplicationTypeEnums:
    """Test all application types are correctly handled."""

    @pytest.mark.anyio
    async def test_create_ind(self, client: AsyncClient):
        payload = _make_app_create(application_type="ind", application_number="IND-111")
        resp = await client.post(f"{API_PREFIX}/applications", json=payload)
        assert resp.status_code == 201
        assert resp.json()["application_type"] == "ind"

    @pytest.mark.anyio
    async def test_create_bla(self, client: AsyncClient):
        payload = _make_app_create(application_type="bla", application_number="BLA-222")
        resp = await client.post(f"{API_PREFIX}/applications", json=payload)
        assert resp.status_code == 201
        assert resp.json()["application_type"] == "bla"

    @pytest.mark.anyio
    async def test_create_maa(self, client: AsyncClient):
        payload = _make_app_create(application_type="maa", application_number="MAA-333")
        resp = await client.post(f"{API_PREFIX}/applications", json=payload)
        assert resp.status_code == 201
        assert resp.json()["application_type"] == "maa"

    @pytest.mark.anyio
    async def test_create_jnda(self, client: AsyncClient):
        payload = _make_app_create(application_type="jnda", application_number="JNDA-444")
        resp = await client.post(f"{API_PREFIX}/applications", json=payload)
        assert resp.status_code == 201
        assert resp.json()["application_type"] == "jnda"

    @pytest.mark.anyio
    async def test_create_supplemental_nda(self, client: AsyncClient):
        payload = _make_app_create(
            application_type="supplemental_nda", application_number="sNDA-555"
        )
        resp = await client.post(f"{API_PREFIX}/applications", json=payload)
        assert resp.status_code == 201
        assert resp.json()["application_type"] == "supplemental_nda"

    @pytest.mark.anyio
    async def test_create_abbreviated_nda(self, client: AsyncClient):
        payload = _make_app_create(
            application_type="abbreviated_nda", application_number="ANDA-666"
        )
        resp = await client.post(f"{API_PREFIX}/applications", json=payload)
        assert resp.status_code == 201
        assert resp.json()["application_type"] == "abbreviated_nda"


# =====================================================================
# MARKET STATUS WORKFLOW
# =====================================================================


class TestMarketStatusWorkflow:
    """Test country authorization market status transitions."""

    @pytest.mark.anyio
    async def test_market_status_not_filed_to_filed(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/country-authorizations/CA-009",
            json={"market_status": "filed", "filing_date": now.isoformat()},
        )
        assert resp.status_code == 200
        assert resp.json()["market_status"] == "filed"

    @pytest.mark.anyio
    async def test_market_status_filed_to_under_review(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/country-authorizations/CA-008",
            json={"market_status": "under_review"},
        )
        assert resp.status_code == 200
        assert resp.json()["market_status"] == "under_review"

    @pytest.mark.anyio
    async def test_market_status_approved_to_launched(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/country-authorizations/CA-004",
            json={"market_status": "launched", "launch_date": now.isoformat()},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["market_status"] == "launched"
        assert data["launch_date"] is not None

    @pytest.mark.anyio
    async def test_market_status_withdrawn(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/country-authorizations/CA-009",
            json={"market_status": "withdrawn"},
        )
        assert resp.status_code == 200
        assert resp.json()["market_status"] == "withdrawn"


# =====================================================================
# CHANGE TYPE ENUMS
# =====================================================================


class TestChangeTypeEnums:
    """Test all post-approval change types."""

    @pytest.mark.anyio
    async def test_file_manufacturing_change(self, client: AsyncClient):
        payload = _make_pac_create(
            change_type="manufacturing",
            description="New API supplier qualification",
        )
        resp = await client.post(f"{API_PREFIX}/post-approval-changes", json=payload)
        assert resp.status_code == 201
        assert resp.json()["change_type"] == "manufacturing"

    @pytest.mark.anyio
    async def test_file_formulation_change(self, client: AsyncClient):
        payload = _make_pac_create(
            change_type="formulation",
            description="Extended-release formulation development",
        )
        resp = await client.post(f"{API_PREFIX}/post-approval-changes", json=payload)
        assert resp.status_code == 201
        assert resp.json()["change_type"] == "formulation"

    @pytest.mark.anyio
    async def test_file_indication_change(self, client: AsyncClient):
        payload = _make_pac_create(
            change_type="indication",
            description="New pediatric indication",
        )
        resp = await client.post(f"{API_PREFIX}/post-approval-changes", json=payload)
        assert resp.status_code == 201
        assert resp.json()["change_type"] == "indication"

    @pytest.mark.anyio
    async def test_file_safety_update_change(self, client: AsyncClient):
        payload = _make_pac_create(
            change_type="safety_update",
            description="Updated safety information from post-marketing surveillance",
        )
        resp = await client.post(f"{API_PREFIX}/post-approval-changes", json=payload)
        assert resp.status_code == 201
        assert resp.json()["change_type"] == "safety_update"

    @pytest.mark.anyio
    async def test_file_packaging_change(self, client: AsyncClient):
        payload = _make_pac_create(
            change_type="packaging",
            description="New unit-dose blister packaging",
        )
        resp = await client.post(f"{API_PREFIX}/post-approval-changes", json=payload)
        assert resp.status_code == 201
        assert resp.json()["change_type"] == "packaging"

    @pytest.mark.anyio
    async def test_file_supplier_change(self, client: AsyncClient):
        payload = _make_pac_create(
            change_type="supplier",
            description="Alternate excipient supplier qualification",
        )
        resp = await client.post(f"{API_PREFIX}/post-approval-changes", json=payload)
        assert resp.status_code == 201
        assert resp.json()["change_type"] == "supplier"


# =====================================================================
# MILESTONE STATUS ENUMS
# =====================================================================


class TestMilestoneStatusEnums:
    """Test all milestone status values."""

    def test_milestone_not_started(self, svc: ProductLicensureService):
        tl = svc.get_timeline("TL-006")
        assert tl is not None
        assert tl.status == MilestoneStatus.NOT_STARTED

    def test_milestone_in_progress(self, svc: ProductLicensureService):
        tl = svc.get_timeline("TL-005")
        assert tl is not None
        assert tl.status == MilestoneStatus.IN_PROGRESS

    def test_milestone_completed(self, svc: ProductLicensureService):
        tl = svc.get_timeline("TL-001")
        assert tl is not None
        assert tl.status == MilestoneStatus.COMPLETED
        assert tl.actual_date is not None

    def test_milestone_delayed(self, svc: ProductLicensureService):
        tl = svc.get_timeline("TL-009")
        assert tl is not None
        assert tl.status == MilestoneStatus.DELAYED

    def test_milestone_at_risk(self, svc: ProductLicensureService):
        tl = svc.get_timeline("TL-010")
        assert tl is not None
        assert tl.status == MilestoneStatus.AT_RISK


# =====================================================================
# CROSS-ENTITY OPERATIONS
# =====================================================================


class TestCrossEntityOperations:
    """Test operations that span multiple entity types."""

    @pytest.mark.anyio
    async def test_create_full_workflow(self, client: AsyncClient):
        """Create application, authorization, label, change, and timeline."""
        # 1. Create application
        app_payload = _make_app_create()
        resp = await client.post(f"{API_PREFIX}/applications", json=app_payload)
        assert resp.status_code == 201
        app_id = resp.json()["id"]

        # 2. Create country authorization
        ca_payload = _make_ca_create(application_id=app_id, country="IN")
        ca_payload["authority_name"] = "CDSCO"
        resp = await client.post(f"{API_PREFIX}/country-authorizations", json=ca_payload)
        assert resp.status_code == 201

        # 3. Create label
        label_payload = _make_label_create(application_id=app_id)
        resp = await client.post(f"{API_PREFIX}/labels", json=label_payload)
        assert resp.status_code == 201

        # 4. File post-approval change
        pac_payload = _make_pac_create(application_id=app_id)
        resp = await client.post(f"{API_PREFIX}/post-approval-changes", json=pac_payload)
        assert resp.status_code == 201

        # 5. Create timeline milestone
        now = datetime.now(timezone.utc)
        tl_payload = _make_timeline_create(
            application_id=app_id,
            milestone_name="Regulatory Submission India",
            planned_date=(now + timedelta(days=60)).isoformat(),
        )
        resp = await client.post(f"{API_PREFIX}/timelines", json=tl_payload)
        assert resp.status_code == 201

        # Verify country status
        resp = await client.get(f"{API_PREFIX}/applications/{app_id}/country-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_application_deletion_preserves_orphans(self, client: AsyncClient):
        """Deleting application does not cascade-delete related entities (in-memory)."""
        # Country authorizations linked to APP-001 should still exist after delete
        resp = await client.delete(f"{API_PREFIX}/applications/APP-001")
        assert resp.status_code == 204

        # CAs still there
        resp = await client.get(f"{API_PREFIX}/country-authorizations/CA-001")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_metrics_after_operations(self, client: AsyncClient):
        """Metrics should reflect newly created entities."""
        # Create a new application
        payload = _make_app_create()
        resp = await client.post(f"{API_PREFIX}/applications", json=payload)
        assert resp.status_code == 201

        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_applications"] == 6  # 5 seed + 1 new
