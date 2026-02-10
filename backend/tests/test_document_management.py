"""Tests for Clinical Document Management (DOC-MGMT).

Covers:
- Seed data verification (documents, versions, reviews, filings)
- Document CRUD (create, read, update, delete, list, filter by trial/type/status/access_level)
- Version management (create, read, list, filter, parent document update)
- Review management (create, read, update, delete, list, filter, auto-completed_date)
- Filing management (create, read, delete, list, filter)
- Document management metrics computation
- Error handling (404s, invalid operations)
- Edge cases (empty filters, boundary conditions, enum coverage)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.document_management import (
    AccessLevel,
    DocumentStatus,
    DocumentType,
    ReviewDecision,
)
from app.services.document_management_service import (
    DocumentManagementService,
    get_document_management_service,
    reset_document_management_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/document-management"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_document_management_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> DocumentManagementService:
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
        "trial_id": EYLEA_TRIAL,
        "document_type": "protocol",
        "title": "Test Protocol Document",
        "document_number": "TEST-PROT-001",
        "version": "1.0",
        "author": "Dr. Test Author",
        "owner": "Clinical Development",
        "access_level": "internal",
        "tags": ["test", "protocol"],
    }
    defaults.update(overrides)
    return defaults


def _make_version_create(**overrides) -> dict:
    defaults = {
        "document_id": "DOC-001",
        "version": "4.0",
        "change_summary": "Test version update with minor changes",
        "changed_by": "Dr. Test Author",
    }
    defaults.update(overrides)
    return defaults


def _make_review_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "document_id": "DOC-001",
        "version_id": "VER-003",
        "reviewer": "Dr. Test Reviewer",
        "reviewer_role": "Medical Director",
        "due_date": (now + timedelta(days=14)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_filing_create(**overrides) -> dict:
    defaults = {
        "document_id": "DOC-001",
        "filing_location": "eTMF/Test Filing",
        "filed_by": "Test Filing Team",
        "regulatory_authority": "FDA",
        "filing_reference": "TEST-FIL-001",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_documents_count(self, svc: DocumentManagementService):
        documents = svc.list_documents()
        assert len(documents) == 12

    def test_seed_documents_across_trials(self, svc: DocumentManagementService):
        trials = {d.trial_id for d in svc.list_documents()}
        assert EYLEA_TRIAL in trials
        assert DUPIXENT_TRIAL in trials
        assert LIBTAYO_TRIAL in trials

    def test_seed_eylea_documents_count(self, svc: DocumentManagementService):
        docs = svc.list_documents(trial_id=EYLEA_TRIAL)
        assert len(docs) == 4

    def test_seed_dupixent_documents_count(self, svc: DocumentManagementService):
        docs = svc.list_documents(trial_id=DUPIXENT_TRIAL)
        assert len(docs) == 4

    def test_seed_libtayo_documents_count(self, svc: DocumentManagementService):
        docs = svc.list_documents(trial_id=LIBTAYO_TRIAL)
        assert len(docs) == 4

    def test_seed_versions_count(self, svc: DocumentManagementService):
        versions = svc.list_versions()
        assert len(versions) == 15

    def test_seed_reviews_count(self, svc: DocumentManagementService):
        reviews = svc.list_reviews()
        assert len(reviews) == 15

    def test_seed_filings_count(self, svc: DocumentManagementService):
        filings = svc.list_filings()
        assert len(filings) == 12

    def test_seed_document_types_present(self, svc: DocumentManagementService):
        docs = svc.list_documents()
        types = {d.document_type for d in docs}
        assert DocumentType.PROTOCOL in types
        assert DocumentType.INVESTIGATOR_BROCHURE in types
        assert DocumentType.ICF in types
        assert DocumentType.CSR in types
        assert DocumentType.SAP in types

    def test_seed_document_statuses_present(self, svc: DocumentManagementService):
        docs = svc.list_documents()
        statuses = {d.status for d in docs}
        assert DocumentStatus.DRAFT in statuses
        assert DocumentStatus.IN_REVIEW in statuses
        assert DocumentStatus.APPROVED in statuses
        assert DocumentStatus.EFFECTIVE in statuses
        assert DocumentStatus.SUPERSEDED in statuses
        assert DocumentStatus.ARCHIVED in statuses

    def test_seed_access_levels_present(self, svc: DocumentManagementService):
        docs = svc.list_documents()
        levels = {d.access_level for d in docs}
        assert AccessLevel.PUBLIC in levels
        assert AccessLevel.INTERNAL in levels
        assert AccessLevel.CONFIDENTIAL in levels
        assert AccessLevel.RESTRICTED in levels

    def test_seed_review_decisions_present(self, svc: DocumentManagementService):
        reviews = svc.list_reviews()
        decisions = {r.decision for r in reviews if r.decision is not None}
        assert ReviewDecision.APPROVED in decisions
        assert ReviewDecision.APPROVED_WITH_COMMENTS in decisions
        assert ReviewDecision.REVISION_REQUIRED in decisions

    def test_seed_pending_reviews_exist(self, svc: DocumentManagementService):
        reviews = svc.list_reviews()
        pending = [r for r in reviews if r.completed_date is None]
        assert len(pending) >= 2

    def test_seed_confirmed_filings_exist(self, svc: DocumentManagementService):
        filings = svc.list_filings()
        confirmed = [f for f in filings if f.confirmed]
        assert len(confirmed) >= 10

    def test_seed_unconfirmed_filing_exists(self, svc: DocumentManagementService):
        filings = svc.list_filings()
        unconfirmed = [f for f in filings if not f.confirmed]
        assert len(unconfirmed) >= 1


# =====================================================================
# DOCUMENT CRUD
# =====================================================================


class TestDocumentCrud:
    """Test document create, read, update, delete operations."""

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
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_documents_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents", params={"document_type": "protocol"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["document_type"] == "protocol"

    @pytest.mark.anyio
    async def test_list_documents_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents", params={"status": "effective"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "effective"

    @pytest.mark.anyio
    async def test_list_documents_filter_access_level(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents", params={"access_level": "confidential"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["access_level"] == "confidential"

    @pytest.mark.anyio
    async def test_list_documents_multiple_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/documents",
            params={"trial_id": EYLEA_TRIAL, "status": "effective"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["status"] == "effective"

    @pytest.mark.anyio
    async def test_get_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/DOC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DOC-001"
        assert data["document_type"] == "protocol"

    @pytest.mark.anyio
    async def test_get_document_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/DOC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_document(self, client: AsyncClient):
        payload = _make_document_create()
        resp = await client.post(f"{API_PREFIX}/documents", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Protocol Document"
        assert data["id"].startswith("DOC-")
        assert data["status"] == "draft"

    @pytest.mark.anyio
    async def test_create_document_defaults(self, client: AsyncClient):
        payload = _make_document_create()
        resp = await client.post(f"{API_PREFIX}/documents", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "draft"
        assert data["created_at"] is not None
        assert data["updated_at"] is not None

    @pytest.mark.anyio
    async def test_update_document(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/documents/DOC-001",
            json={"title": "Updated Protocol Title", "status": "approved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Protocol Title"
        assert data["status"] == "approved"

    @pytest.mark.anyio
    async def test_update_document_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/documents/DOC-NONEXISTENT",
            json={"title": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_document_updates_timestamp(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/documents/DOC-001")
        original_updated = resp1.json()["updated_at"]
        resp2 = await client.put(
            f"{API_PREFIX}/documents/DOC-001",
            json={"title": "Timestamp Test"},
        )
        assert resp2.status_code == 200
        new_updated = resp2.json()["updated_at"]
        assert new_updated >= original_updated

    @pytest.mark.anyio
    async def test_delete_document(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/documents/DOC-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/documents/DOC-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_document_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/documents/DOC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_document_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/DOC-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "document_type" in data
        assert "title" in data
        assert "document_number" in data
        assert "version" in data
        assert "status" in data
        assert "author" in data
        assert "owner" in data
        assert "access_level" in data
        assert "tags" in data
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.anyio
    async def test_create_document_with_tags(self, client: AsyncClient):
        payload = _make_document_create(tags=["urgent", "amendment", "phase-3"])
        resp = await client.post(f"{API_PREFIX}/documents", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["tags"]) == 3
        assert "urgent" in data["tags"]

    @pytest.mark.anyio
    async def test_update_document_tags(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/documents/DOC-001",
            json={"tags": ["updated-tag"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tags"] == ["updated-tag"]

    @pytest.mark.anyio
    async def test_update_document_access_level(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/documents/DOC-001",
            json={"access_level": "restricted"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_level"] == "restricted"

    def test_document_has_file_metadata(self, svc: DocumentManagementService):
        doc = svc.get_document("DOC-001")
        assert doc is not None
        assert doc.file_reference is not None
        assert doc.file_size_bytes is not None
        assert doc.file_size_bytes > 0
        assert doc.page_count is not None
        assert doc.page_count > 0


# =====================================================================
# VERSION MANAGEMENT
# =====================================================================


class TestVersionManagement:
    """Test document version management operations."""

    @pytest.mark.anyio
    async def test_list_versions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_versions_filter_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/versions", params={"document_id": "DOC-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["document_id"] == "DOC-001"

    @pytest.mark.anyio
    async def test_get_version(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/versions/VER-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "VER-001"
        assert data["document_id"] == "DOC-001"

    @pytest.mark.anyio
    async def test_get_version_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/versions/VER-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_version(self, client: AsyncClient):
        payload = _make_version_create()
        resp = await client.post(f"{API_PREFIX}/versions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["version"] == "4.0"
        assert data["document_id"] == "DOC-001"
        assert data["id"].startswith("VER-")

    @pytest.mark.anyio
    async def test_create_version_updates_parent_document(self, client: AsyncClient):
        payload = _make_version_create(version="5.0")
        resp = await client.post(f"{API_PREFIX}/versions", json=payload)
        assert resp.status_code == 201
        # Verify parent document was updated
        resp2 = await client.get(f"{API_PREFIX}/documents/DOC-001")
        data = resp2.json()
        assert data["version"] == "5.0"

    @pytest.mark.anyio
    async def test_create_version_nonexistent_document(self, client: AsyncClient):
        payload = _make_version_create(document_id="DOC-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/versions", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_version_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/versions/VER-001")
        data = resp.json()
        assert "id" in data
        assert "document_id" in data
        assert "version" in data
        assert "change_summary" in data
        assert "changed_by" in data
        assert "change_date" in data

    @pytest.mark.anyio
    async def test_versions_sorted_by_date_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/versions")
        data = resp.json()
        dates = [item["change_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    def test_version_has_previous_version_chain(self, svc: DocumentManagementService):
        ver3 = svc.get_version("VER-003")
        assert ver3 is not None
        assert ver3.previous_version_id == "VER-002"
        ver2 = svc.get_version("VER-002")
        assert ver2 is not None
        assert ver2.previous_version_id == "VER-001"

    def test_version_initial_has_no_previous(self, svc: DocumentManagementService):
        ver1 = svc.get_version("VER-001")
        assert ver1 is not None
        assert ver1.previous_version_id is None


# =====================================================================
# REVIEW MANAGEMENT
# =====================================================================


class TestReviewManagement:
    """Test document review management operations."""

    @pytest.mark.anyio
    async def test_list_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_reviews_filter_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews", params={"document_id": "DOC-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["document_id"] == "DOC-001"

    @pytest.mark.anyio
    async def test_list_reviews_filter_reviewer(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/reviews",
            params={"reviewer": "Dr. Leonard Schleifer"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["reviewer"] == "Dr. Leonard Schleifer"

    @pytest.mark.anyio
    async def test_list_reviews_filter_decision(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews", params={"decision": "approved"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["decision"] == "approved"

    @pytest.mark.anyio
    async def test_get_review(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews/REV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "REV-001"
        assert data["decision"] == "approved"

    @pytest.mark.anyio
    async def test_get_review_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews/REV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_review(self, client: AsyncClient):
        payload = _make_review_create()
        resp = await client.post(f"{API_PREFIX}/reviews", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["reviewer"] == "Dr. Test Reviewer"
        assert data["id"].startswith("REV-")
        assert data["completed_date"] is None
        assert data["decision"] is None

    @pytest.mark.anyio
    async def test_create_review_nonexistent_document(self, client: AsyncClient):
        payload = _make_review_create(document_id="DOC-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/reviews", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_review_with_decision(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reviews/REV-005",
            json={"decision": "approved", "comments": "SAP looks good."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "approved"
        assert data["comments"] == "SAP looks good."
        assert data["completed_date"] is not None

    @pytest.mark.anyio
    async def test_update_review_sets_completed_date(self, client: AsyncClient):
        # REV-005 has no completed_date
        resp = await client.put(
            f"{API_PREFIX}/reviews/REV-005",
            json={"decision": "revision_required"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["completed_date"] is not None

    @pytest.mark.anyio
    async def test_update_review_comments_only(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reviews/REV-005",
            json={"comments": "Still reviewing, need more time."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["comments"] == "Still reviewing, need more time."
        assert data["completed_date"] is None  # No decision, no completed_date

    @pytest.mark.anyio
    async def test_update_review_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reviews/REV-NONEXISTENT",
            json={"decision": "approved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_review(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reviews/REV-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/reviews/REV-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_review_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reviews/REV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_review_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews/REV-001")
        data = resp.json()
        assert "id" in data
        assert "document_id" in data
        assert "reviewer" in data
        assert "reviewer_role" in data
        assert "assigned_date" in data
        assert "due_date" in data
        assert "decision" in data
        assert "comments" in data

    def test_completed_reviews_have_decision(self, svc: DocumentManagementService):
        reviews = svc.list_reviews()
        for r in reviews:
            if r.completed_date is not None:
                assert r.decision is not None

    def test_pending_reviews_have_no_decision(self, svc: DocumentManagementService):
        reviews = svc.list_reviews()
        pending = [r for r in reviews if r.completed_date is None]
        for r in pending:
            assert r.decision is None


# =====================================================================
# FILING MANAGEMENT
# =====================================================================


class TestFilingManagement:
    """Test document filing management operations."""

    @pytest.mark.anyio
    async def test_list_filings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/filings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_filings_filter_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/filings", params={"document_id": "DOC-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["document_id"] == "DOC-001"

    @pytest.mark.anyio
    async def test_get_filing(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/filings/FIL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "FIL-001"
        assert data["regulatory_authority"] == "FDA"

    @pytest.mark.anyio
    async def test_get_filing_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/filings/FIL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_filing(self, client: AsyncClient):
        payload = _make_filing_create()
        resp = await client.post(f"{API_PREFIX}/filings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["document_id"] == "DOC-001"
        assert data["id"].startswith("FIL-")
        assert data["confirmed"] is False

    @pytest.mark.anyio
    async def test_create_filing_nonexistent_document(self, client: AsyncClient):
        payload = _make_filing_create(document_id="DOC-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/filings", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_filing_without_regulatory_authority(self, client: AsyncClient):
        payload = _make_filing_create(regulatory_authority=None, filing_reference=None)
        resp = await client.post(f"{API_PREFIX}/filings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["regulatory_authority"] is None
        assert data["filing_reference"] is None

    @pytest.mark.anyio
    async def test_delete_filing(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/filings/FIL-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/filings/FIL-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_filing_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/filings/FIL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filing_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/filings/FIL-001")
        data = resp.json()
        assert "id" in data
        assert "document_id" in data
        assert "filing_location" in data
        assert "filed_by" in data
        assert "filed_date" in data
        assert "regulatory_authority" in data
        assert "filing_reference" in data
        assert "confirmed" in data

    @pytest.mark.anyio
    async def test_filings_sorted_by_date_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/filings")
        data = resp.json()
        dates = [item["filed_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    def test_filing_confirmed_status(self, svc: DocumentManagementService):
        filing = svc.get_filing("FIL-001")
        assert filing is not None
        assert filing.confirmed is True

    def test_filing_unconfirmed_status(self, svc: DocumentManagementService):
        filing = svc.get_filing("FIL-010")
        assert filing is not None
        assert filing.confirmed is False


# =====================================================================
# METRICS
# =====================================================================


class TestDocumentMetrics:
    """Test document management metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_documents"] == 12
        assert data["total_versions"] == 15
        assert data["total_reviews"] == 15
        assert data["total_filings"] == 12
        assert data["pending_reviews"] >= 2
        assert data["confirmed_filings"] >= 10
        assert data["avg_review_days"] > 0

    @pytest.mark.anyio
    async def test_get_metrics_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_documents"] == 4

    @pytest.mark.anyio
    async def test_get_metrics_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_documents"] == 0
        assert data["total_versions"] == 0
        assert data["total_reviews"] == 0
        assert data["total_filings"] == 0

    def test_metrics_documents_by_type(self, svc: DocumentManagementService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.documents_by_type.values())
        assert total_by_type == metrics.total_documents

    def test_metrics_documents_by_status(self, svc: DocumentManagementService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.documents_by_status.values())
        assert total_by_status == metrics.total_documents

    def test_metrics_reviews_by_decision(self, svc: DocumentManagementService):
        metrics = svc.get_metrics()
        # Only completed reviews should be counted
        total_by_decision = sum(metrics.reviews_by_decision.values())
        completed = [r for r in svc.list_reviews() if r.decision is not None]
        assert total_by_decision == len(completed)

    def test_metrics_pending_reviews_count(self, svc: DocumentManagementService):
        metrics = svc.get_metrics()
        pending = [r for r in svc.list_reviews() if r.completed_date is None]
        assert metrics.pending_reviews == len(pending)

    def test_metrics_overdue_reviews_count(self, svc: DocumentManagementService):
        metrics = svc.get_metrics()
        now = datetime.now(timezone.utc)
        overdue = [
            r for r in svc.list_reviews()
            if r.completed_date is None and r.due_date < now
        ]
        assert metrics.overdue_reviews == len(overdue)

    def test_metrics_confirmed_filings_count(self, svc: DocumentManagementService):
        metrics = svc.get_metrics()
        confirmed = [f for f in svc.list_filings() if f.confirmed]
        assert metrics.confirmed_filings == len(confirmed)

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_documents" in data
        assert "documents_by_type" in data
        assert "documents_by_status" in data
        assert "total_versions" in data
        assert "total_reviews" in data
        assert "pending_reviews" in data
        assert "overdue_reviews" in data
        assert "reviews_by_decision" in data
        assert "total_filings" in data
        assert "confirmed_filings" in data
        assert "avg_review_days" in data

    def test_metrics_avg_review_days_reasonable(self, svc: DocumentManagementService):
        metrics = svc.get_metrics()
        assert 0 < metrics.avg_review_days < 30

    def test_metrics_by_trial_filters_correctly(self, svc: DocumentManagementService):
        metrics_eylea = svc.get_metrics(trial_id=EYLEA_TRIAL)
        metrics_dupixent = svc.get_metrics(trial_id=DUPIXENT_TRIAL)
        metrics_all = svc.get_metrics()
        assert metrics_eylea.total_documents + metrics_dupixent.total_documents <= metrics_all.total_documents


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_document_management_service()
        svc2 = get_document_management_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_document_management_service()
        svc2 = reset_document_management_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_document_management_service()
        svc.delete_document("DOC-001")
        assert svc.get_document("DOC-001") is None
        svc2 = reset_document_management_service()
        assert svc2.get_document("DOC-001") is not None


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
    async def test_list_versions_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/versions")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_reviews_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_filings_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/filings")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_document_all_types(self, client: AsyncClient):
        for dt in [
            "protocol", "investigator_brochure", "informed_consent_form",
            "clinical_study_report", "statistical_analysis_plan",
            "monitoring_plan", "data_management_plan", "safety_plan",
            "regulatory_submission", "site_training",
        ]:
            payload = _make_document_create(
                document_type=dt,
                document_number=f"TEST-{dt[:4].upper()}-001",
                title=f"Test {dt} Document",
            )
            resp = await client.post(f"{API_PREFIX}/documents", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["document_type"] == dt

    @pytest.mark.anyio
    async def test_create_document_all_access_levels(self, client: AsyncClient):
        for al in ["public", "internal", "confidential", "restricted"]:
            payload = _make_document_create(
                access_level=al,
                document_number=f"TEST-AL-{al[:4].upper()}",
                title=f"Test {al} Document",
            )
            resp = await client.post(f"{API_PREFIX}/documents", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["access_level"] == al

    @pytest.mark.anyio
    async def test_update_document_all_statuses(self, client: AsyncClient):
        for status in [
            "draft", "in_review", "approved", "effective",
            "superseded", "archived", "obsolete",
        ]:
            resp = await client.put(
                f"{API_PREFIX}/documents/DOC-001",
                json={"status": status},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == status

    @pytest.mark.anyio
    async def test_update_review_all_decisions(self, client: AsyncClient):
        # Create reviews to test each decision
        for decision in ["approved", "approved_with_comments", "revision_required", "rejected"]:
            # Create a fresh review
            payload = _make_review_create(reviewer=f"Reviewer-{decision}")
            resp = await client.post(f"{API_PREFIX}/reviews", json=payload)
            assert resp.status_code == 201
            review_id = resp.json()["id"]

            resp2 = await client.put(
                f"{API_PREFIX}/reviews/{review_id}",
                json={"decision": decision, "comments": f"Decision: {decision}"},
            )
            assert resp2.status_code == 200
            data = resp2.json()
            assert data["decision"] == decision

    @pytest.mark.anyio
    async def test_list_documents_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_versions_nonexistent_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/versions", params={"document_id": "DOC-NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_reviews_nonexistent_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews", params={"document_id": "DOC-NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_filings_nonexistent_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/filings", params={"document_id": "DOC-NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_create_document_empty_tags(self, client: AsyncClient):
        payload = _make_document_create(tags=[])
        resp = await client.post(f"{API_PREFIX}/documents", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["tags"] == []

    @pytest.mark.anyio
    async def test_create_version_and_verify_total_increments(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/versions")
        original_total = resp1.json()["total"]
        payload = _make_version_create()
        resp2 = await client.post(f"{API_PREFIX}/versions", json=payload)
        assert resp2.status_code == 201
        resp3 = await client.get(f"{API_PREFIX}/versions")
        assert resp3.json()["total"] == original_total + 1

    @pytest.mark.anyio
    async def test_create_review_and_verify_total_increments(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/reviews")
        original_total = resp1.json()["total"]
        payload = _make_review_create()
        resp2 = await client.post(f"{API_PREFIX}/reviews", json=payload)
        assert resp2.status_code == 201
        resp3 = await client.get(f"{API_PREFIX}/reviews")
        assert resp3.json()["total"] == original_total + 1

    @pytest.mark.anyio
    async def test_create_filing_and_verify_total_increments(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/filings")
        original_total = resp1.json()["total"]
        payload = _make_filing_create()
        resp2 = await client.post(f"{API_PREFIX}/filings", json=payload)
        assert resp2.status_code == 201
        resp3 = await client.get(f"{API_PREFIX}/filings")
        assert resp3.json()["total"] == original_total + 1

    @pytest.mark.anyio
    async def test_delete_document_then_list_shrinks(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/documents")
        original_total = resp1.json()["total"]
        await client.delete(f"{API_PREFIX}/documents/DOC-001")
        resp2 = await client.get(f"{API_PREFIX}/documents")
        assert resp2.json()["total"] == original_total - 1


# =====================================================================
# ENUMERATION COVERAGE
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout the system."""

    @pytest.mark.anyio
    async def test_all_document_types_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents")
        data = resp.json()
        types = {item["document_type"] for item in data["items"]}
        assert "protocol" in types
        assert "investigator_brochure" in types
        assert "informed_consent_form" in types

    @pytest.mark.anyio
    async def test_all_statuses_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "draft" in statuses
        assert "effective" in statuses
        assert "approved" in statuses

    @pytest.mark.anyio
    async def test_all_access_levels_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents")
        data = resp.json()
        levels = {item["access_level"] for item in data["items"]}
        assert "public" in levels
        assert "internal" in levels
        assert "confidential" in levels
        assert "restricted" in levels

    @pytest.mark.anyio
    async def test_review_decisions_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reviews")
        data = resp.json()
        decisions = {item["decision"] for item in data["items"] if item["decision"]}
        assert "approved" in decisions
        assert "approved_with_comments" in decisions
        assert "revision_required" in decisions


# =====================================================================
# DATA VALIDATION
# =====================================================================


class TestDataValidation:
    """Test detailed data validation across the system."""

    def test_effective_documents_have_effective_date(self, svc: DocumentManagementService):
        docs = svc.list_documents(status=DocumentStatus.EFFECTIVE)
        for d in docs:
            assert d.effective_date is not None

    def test_draft_document_has_no_effective_date(self, svc: DocumentManagementService):
        docs = svc.list_documents(status=DocumentStatus.DRAFT)
        for d in docs:
            assert d.effective_date is None

    def test_superseded_document_has_expiry_date(self, svc: DocumentManagementService):
        docs = svc.list_documents(status=DocumentStatus.SUPERSEDED)
        for d in docs:
            assert d.expiry_date is not None

    def test_all_documents_have_required_fields(self, svc: DocumentManagementService):
        for d in svc.list_documents():
            assert d.id
            assert d.trial_id
            assert d.document_type is not None
            assert d.title
            assert d.document_number
            assert d.version
            assert d.author
            assert d.owner

    def test_all_versions_have_required_fields(self, svc: DocumentManagementService):
        for v in svc.list_versions():
            assert v.id
            assert v.document_id
            assert v.version
            assert v.change_summary
            assert v.changed_by
            assert v.change_date is not None

    def test_all_reviews_have_required_fields(self, svc: DocumentManagementService):
        for r in svc.list_reviews():
            assert r.id
            assert r.document_id
            assert r.reviewer
            assert r.reviewer_role
            assert r.assigned_date is not None
            assert r.due_date is not None

    def test_all_filings_have_required_fields(self, svc: DocumentManagementService):
        for f in svc.list_filings():
            assert f.id
            assert f.document_id
            assert f.filing_location
            assert f.filed_by
            assert f.filed_date is not None

    def test_filing_regulatory_authorities(self, svc: DocumentManagementService):
        filings = svc.list_filings()
        authorities = {f.regulatory_authority for f in filings if f.regulatory_authority}
        assert "FDA" in authorities
        assert "EMA" in authorities

    def test_document_tags_are_lists(self, svc: DocumentManagementService):
        for d in svc.list_documents():
            assert isinstance(d.tags, list)

    def test_versions_reference_existing_documents(self, svc: DocumentManagementService):
        doc_ids = {d.id for d in svc.list_documents()}
        for v in svc.list_versions():
            assert v.document_id in doc_ids

    def test_reviews_reference_existing_documents(self, svc: DocumentManagementService):
        doc_ids = {d.id for d in svc.list_documents()}
        for r in svc.list_reviews():
            assert r.document_id in doc_ids

    def test_filings_reference_existing_documents(self, svc: DocumentManagementService):
        doc_ids = {d.id for d in svc.list_documents()}
        for f in svc.list_filings():
            assert f.document_id in doc_ids

    def test_documents_sorted_by_id(self, svc: DocumentManagementService):
        docs = svc.list_documents()
        ids = [d.id for d in docs]
        assert ids == sorted(ids)
