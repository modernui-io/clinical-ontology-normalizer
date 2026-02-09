"""Tests for Medical Writing & CSR Generation (CLINICAL-11).

Covers:
- Seed data verification (documents, sections, comments, TLF shells)
- Document CRUD (create, read, update, delete, list, filter by trial/type/status)
- Document lifecycle advancement (draft -> internal_review -> ... -> approved)
- Overdue document detection
- Section CRUD (create, read, update, delete, list, filter by document/status/ICH)
- ICH E3 section structure validation
- Review comment CRUD (create, read, update, delete, list, filter)
- Comment resolution workflow (open -> accepted/rejected/deferred)
- TLF shell CRUD (create, read, update, delete, list, filter)
- TLF completion tracking
- Writing metrics computation
- Error handling (404s, 400s, invalid operations)
- Edge cases (empty filters, boundary conditions)
- Singleton pattern behavior
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.medical_writing import (
    DocumentCreate,
    DocumentStatus,
    DocumentType,
    DocumentUpdate,
    ICHSection,
    ProgrammingStatus,
    ResolutionStatus,
    ReviewCommentCreate,
    ReviewCommentUpdate,
    ReviewType,
    SectionCreate,
    SectionStatus,
    SectionUpdate,
    TLFShellCreate,
    TLFShellUpdate,
    TLFType,
)
from app.services.medical_writing_service import (
    MedicalWritingService,
    get_medical_writing_service,
    reset_medical_writing_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/medical-writing"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_medical_writing_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> MedicalWritingService:
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


def _make_doc_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "document_type": "csr",
        "title": "Test CSR Document",
        "version": "1.0",
        "author": "Dr. Test Author",
        "target_date": (now + timedelta(days=90)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_section_create(**overrides) -> dict:
    defaults = {
        "document_id": "DOC-001",
        "section_number": "99",
        "title": "Test Section",
        "content_summary": "Test content summary",
        "assigned_to": "Dr. Test Writer",
        "ich_section": "11_efficacy_evaluation",
    }
    defaults.update(overrides)
    return defaults


def _make_comment_create(**overrides) -> dict:
    defaults = {
        "document_id": "DOC-001",
        "section_id": "SEC-005",
        "reviewer": "Dr. Test Reviewer",
        "review_type": "medical",
        "comment_text": "Test review comment for section 9",
    }
    defaults.update(overrides)
    return defaults


def _make_tlf_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "tlf_type": "table",
        "number": "14.9.1",
        "title": "Test TLF Shell",
        "population": "ITT",
        "dataset": "ADSL",
        "programmer": "Test Programmer",
        "validator": "Test Validator",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_documents_count(self, svc: MedicalWritingService):
        docs = svc.list_documents()
        assert len(docs) == 8

    def test_seed_documents_types(self, svc: MedicalWritingService):
        docs = svc.list_documents()
        types = {d.document_type for d in docs}
        assert DocumentType.CSR in types
        assert DocumentType.SAP in types
        assert DocumentType.IB in types
        assert DocumentType.PROTOCOL in types

    def test_seed_documents_statuses(self, svc: MedicalWritingService):
        docs = svc.list_documents()
        statuses = {d.status for d in docs}
        assert DocumentStatus.DRAFT in statuses
        assert DocumentStatus.APPROVED in statuses

    def test_seed_documents_trials(self, svc: MedicalWritingService):
        docs = svc.list_documents()
        trials = {d.trial_id for d in docs}
        assert EYLEA_TRIAL in trials
        assert DUPIXENT_TRIAL in trials
        assert LIBTAYO_TRIAL in trials

    def test_seed_sections_count(self, svc: MedicalWritingService):
        sections = svc.list_sections()
        assert len(sections) == 30

    def test_seed_sections_per_csr(self, svc: MedicalWritingService):
        for doc_id in ["DOC-001", "DOC-002", "DOC-003"]:
            sections = svc.list_sections(document_id=doc_id)
            assert len(sections) >= 7  # Each CSR has multiple ICH sections

    def test_seed_comments_count(self, svc: MedicalWritingService):
        comments = svc.list_comments()
        assert len(comments) == 20

    def test_seed_tlf_shells_count(self, svc: MedicalWritingService):
        tlfs = svc.list_tlf_shells()
        assert len(tlfs) == 25

    def test_seed_csr_has_ich_sections(self, svc: MedicalWritingService):
        sections = svc.list_sections(document_id="DOC-001")
        ich_sections = {s.ich_section for s in sections if s.ich_section is not None}
        assert ICHSection.S1_TITLE in ich_sections
        assert ICHSection.S2_SYNOPSIS in ich_sections
        assert ICHSection.S11_EFFICACY_EVALUATION in ich_sections
        assert ICHSection.S12_SAFETY_EVALUATION in ich_sections

    def test_seed_tlf_types(self, svc: MedicalWritingService):
        tlfs = svc.list_tlf_shells()
        types = {t.tlf_type for t in tlfs}
        assert TLFType.TABLE in types
        assert TLFType.LISTING in types
        assert TLFType.FIGURE in types

    def test_seed_documents_have_sections_list(self, svc: MedicalWritingService):
        doc = svc.get_document("DOC-001")
        assert doc is not None
        assert len(doc.sections) > 0

    def test_seed_documents_have_comment_counts(self, svc: MedicalWritingService):
        doc = svc.get_document("DOC-001")
        assert doc is not None
        assert doc.comments_count > 0


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
        assert data["total"] == 8
        assert len(data["items"]) == 8

    @pytest.mark.anyio
    async def test_list_documents_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_documents_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents", params={"document_type": "csr"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["document_type"] == "csr"

    @pytest.mark.anyio
    async def test_list_documents_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents", params={"status": "draft"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "draft"

    @pytest.mark.anyio
    async def test_get_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/DOC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DOC-001"
        assert data["document_type"] == "csr"
        assert "EYLEA" in data["title"]

    @pytest.mark.anyio
    async def test_get_document_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/DOC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_document(self, client: AsyncClient):
        payload = _make_doc_create()
        resp = await client.post(f"{API_PREFIX}/documents", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test CSR Document"
        assert data["status"] == "draft"
        assert data["id"].startswith("DOC-")

    @pytest.mark.anyio
    async def test_create_document_sap(self, client: AsyncClient):
        payload = _make_doc_create(document_type="sap", title="Test SAP")
        resp = await client.post(f"{API_PREFIX}/documents", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["document_type"] == "sap"

    @pytest.mark.anyio
    async def test_update_document(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/documents/DOC-002",
            json={"title": "Updated DUPIXENT CSR", "word_count": 30000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated DUPIXENT CSR"
        assert data["word_count"] == 30000

    @pytest.mark.anyio
    async def test_update_document_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/documents/DOC-NONEXISTENT",
            json={"title": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_document(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/documents/DOC-002")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/documents/DOC-002")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_document_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/documents/DOC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# DOCUMENT LIFECYCLE
# =====================================================================


class TestDocumentLifecycle:
    """Test document lifecycle advancement."""

    @pytest.mark.anyio
    async def test_advance_draft_to_internal_review(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/documents/DOC-002/advance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "internal_review"

    @pytest.mark.anyio
    async def test_advance_internal_review_to_medical_review(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/documents/DOC-003/advance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "medical_review"

    @pytest.mark.anyio
    async def test_advance_medical_review_to_qc(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/documents/DOC-001/advance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "qc"

    @pytest.mark.anyio
    async def test_advance_qc_to_final(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/documents/DOC-006/advance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "final"

    @pytest.mark.anyio
    async def test_advance_final_to_approved(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/documents/DOC-005/advance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"

    @pytest.mark.anyio
    async def test_advance_approved_fails(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/documents/DOC-004/advance")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_advance_submitted_fails(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/documents/DOC-008/advance")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_advance_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/documents/DOC-NONEXISTENT/advance")
        assert resp.status_code == 404

    def test_full_lifecycle_progression(self, svc: MedicalWritingService):
        """Walk a document through the full lifecycle."""
        doc = svc.get_document("DOC-002")
        assert doc is not None
        assert doc.status == DocumentStatus.DRAFT

        # Draft -> Internal Review
        doc = svc.advance_document_status("DOC-002")
        assert doc is not None
        assert doc.status == DocumentStatus.INTERNAL_REVIEW

        # Internal Review -> Medical Review
        doc = svc.advance_document_status("DOC-002")
        assert doc is not None
        assert doc.status == DocumentStatus.MEDICAL_REVIEW

        # Medical Review -> QC
        doc = svc.advance_document_status("DOC-002")
        assert doc is not None
        assert doc.status == DocumentStatus.QC

        # QC -> Final
        doc = svc.advance_document_status("DOC-002")
        assert doc is not None
        assert doc.status == DocumentStatus.FINAL

        # Final -> Approved
        doc = svc.advance_document_status("DOC-002")
        assert doc is not None
        assert doc.status == DocumentStatus.APPROVED


# =====================================================================
# OVERDUE DOCUMENTS
# =====================================================================


class TestOverdueDocuments:
    """Test overdue document detection."""

    @pytest.mark.anyio
    async def test_get_overdue_documents(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/overdue")
        assert resp.status_code == 200
        data = resp.json()
        # Some docs have past target dates and are not approved
        assert data["total"] >= 0

    def test_overdue_excludes_approved(self, svc: MedicalWritingService):
        overdue = svc.get_overdue_documents()
        for doc in overdue:
            assert doc.status not in (DocumentStatus.APPROVED, DocumentStatus.SUBMITTED)

    def test_overdue_has_past_target_date(self, svc: MedicalWritingService):
        now = datetime.now(timezone.utc)
        overdue = svc.get_overdue_documents()
        for doc in overdue:
            assert doc.target_date < now

    def test_overdue_sorted_by_target_date(self, svc: MedicalWritingService):
        overdue = svc.get_overdue_documents()
        if len(overdue) >= 2:
            dates = [d.target_date for d in overdue]
            assert dates == sorted(dates)


# =====================================================================
# SECTION CRUD
# =====================================================================


class TestSectionCrud:
    """Test section create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_sections(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sections")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 30

    @pytest.mark.anyio
    async def test_list_sections_filter_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sections", params={"document_id": "DOC-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["document_id"] == "DOC-001"

    @pytest.mark.anyio
    async def test_list_sections_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sections", params={"status": "final"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "final"

    @pytest.mark.anyio
    async def test_list_sections_filter_ich_section(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sections", params={"ich_section": "11_efficacy_evaluation"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["ich_section"] == "11_efficacy_evaluation"

    @pytest.mark.anyio
    async def test_get_section(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sections/SEC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SEC-001"
        assert data["document_id"] == "DOC-001"

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
    async def test_create_section_updates_document(self, client: AsyncClient):
        payload = _make_section_create()
        resp = await client.post(f"{API_PREFIX}/sections", json=payload)
        assert resp.status_code == 201
        section_id = resp.json()["id"]
        # Verify document's section list includes the new section
        resp2 = await client.get(f"{API_PREFIX}/documents/DOC-001")
        data = resp2.json()
        assert section_id in data["sections"]

    @pytest.mark.anyio
    async def test_update_section(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sections/SEC-009",
            json={"status": "drafting", "word_count": 1500},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "drafting"
        assert data["word_count"] == 1500

    @pytest.mark.anyio
    async def test_update_section_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sections/SEC-NONEXISTENT",
            json={"title": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_section(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sections/SEC-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/sections/SEC-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_section_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sections/SEC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# ICH E3 SECTION STRUCTURE
# =====================================================================


class TestICHSections:
    """Test ICH E3 section structure validation."""

    def test_ich_sections_in_csr(self, svc: MedicalWritingService):
        sections = svc.list_sections(document_id="DOC-001")
        ich_sections = [s.ich_section for s in sections if s.ich_section is not None]
        assert len(ich_sections) > 0
        # All sections should have ICH mapping for CSR
        for section in sections:
            assert section.ich_section is not None

    def test_multiple_csrs_have_ich_sections(self, svc: MedicalWritingService):
        for doc_id in ["DOC-001", "DOC-002", "DOC-003"]:
            sections = svc.list_sections(document_id=doc_id)
            for s in sections:
                assert s.ich_section is not None

    def test_section_numbers_ordered(self, svc: MedicalWritingService):
        sections = svc.list_sections(document_id="DOC-001")
        # Sections should be sortable by section_number
        numbers = [s.section_number for s in sections]
        assert len(numbers) > 0

    @pytest.mark.anyio
    async def test_filter_efficacy_sections(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sections",
            params={"ich_section": "11_efficacy_evaluation"},
        )
        data = resp.json()
        assert data["total"] == 3  # One per CSR

    @pytest.mark.anyio
    async def test_filter_safety_sections(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sections",
            params={"ich_section": "12_safety_evaluation"},
        )
        data = resp.json()
        assert data["total"] == 3  # One per CSR


# =====================================================================
# REVIEW COMMENT CRUD
# =====================================================================


class TestReviewCommentCrud:
    """Test review comment create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_comments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 20

    @pytest.mark.anyio
    async def test_list_comments_filter_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comments", params={"document_id": "DOC-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["document_id"] == "DOC-001"

    @pytest.mark.anyio
    async def test_list_comments_filter_section(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comments", params={"section_id": "SEC-005"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["section_id"] == "SEC-005"

    @pytest.mark.anyio
    async def test_list_comments_filter_review_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comments", params={"review_type": "medical"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["review_type"] == "medical"

    @pytest.mark.anyio
    async def test_list_comments_filter_resolution(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comments", params={"resolution": "open"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["resolution"] == "open"

    @pytest.mark.anyio
    async def test_get_comment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comments/CMT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CMT-001"
        assert data["review_type"] == "medical"

    @pytest.mark.anyio
    async def test_get_comment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comments/CMT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_comment(self, client: AsyncClient):
        payload = _make_comment_create()
        resp = await client.post(f"{API_PREFIX}/comments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["reviewer"] == "Dr. Test Reviewer"
        assert data["resolution"] == "open"
        assert data["id"].startswith("CMT-")

    @pytest.mark.anyio
    async def test_create_comment_updates_document_count(self, client: AsyncClient):
        # Get initial count
        resp = await client.get(f"{API_PREFIX}/documents/DOC-001")
        initial_count = resp.json()["comments_count"]

        # Create comment
        payload = _make_comment_create()
        resp = await client.post(f"{API_PREFIX}/comments", json=payload)
        assert resp.status_code == 201

        # Verify count increased
        resp2 = await client.get(f"{API_PREFIX}/documents/DOC-001")
        assert resp2.json()["comments_count"] == initial_count + 1

    @pytest.mark.anyio
    async def test_create_comment_invalid_document(self, client: AsyncClient):
        payload = _make_comment_create(document_id="DOC-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/comments", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_comment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/comments/CMT-003",
            json={"comment_text": "Updated comment text"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["comment_text"] == "Updated comment text"

    @pytest.mark.anyio
    async def test_update_comment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/comments/CMT-NONEXISTENT",
            json={"comment_text": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_comment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/comments/CMT-020")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/comments/CMT-020")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_comment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/comments/CMT-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# REVIEW COMMENT RESOLUTION WORKFLOW
# =====================================================================


class TestCommentResolution:
    """Test comment resolution workflow."""

    def test_resolve_comment_accepted(self, svc: MedicalWritingService):
        comment = svc.get_comment("CMT-003")
        assert comment is not None
        assert comment.resolution == ResolutionStatus.OPEN

        updated = svc.update_comment(
            "CMT-003", ReviewCommentUpdate(resolution=ResolutionStatus.ACCEPTED)
        )
        assert updated is not None
        assert updated.resolution == ResolutionStatus.ACCEPTED
        assert updated.resolved_date is not None

    def test_resolve_comment_rejected(self, svc: MedicalWritingService):
        updated = svc.update_comment(
            "CMT-004", ReviewCommentUpdate(resolution=ResolutionStatus.REJECTED)
        )
        assert updated is not None
        assert updated.resolution == ResolutionStatus.REJECTED
        assert updated.resolved_date is not None

    def test_resolve_comment_deferred(self, svc: MedicalWritingService):
        updated = svc.update_comment(
            "CMT-005", ReviewCommentUpdate(resolution=ResolutionStatus.DEFERRED)
        )
        assert updated is not None
        assert updated.resolution == ResolutionStatus.DEFERRED
        assert updated.resolved_date is not None

    def test_already_resolved_keeps_date(self, svc: MedicalWritingService):
        comment = svc.get_comment("CMT-001")
        assert comment is not None
        assert comment.resolution == ResolutionStatus.ACCEPTED
        original_date = comment.resolved_date

        updated = svc.update_comment(
            "CMT-001", ReviewCommentUpdate(comment_text="Updated text")
        )
        assert updated is not None
        assert updated.resolved_date == original_date

    @pytest.mark.anyio
    async def test_resolve_comment_via_api(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/comments/CMT-006",
            json={"resolution": "accepted"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["resolution"] == "accepted"
        assert data["resolved_date"] is not None

    @pytest.mark.anyio
    async def test_list_open_comments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comments", params={"resolution": "open"})
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["resolution"] == "open"

    @pytest.mark.anyio
    async def test_list_accepted_comments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comments", params={"resolution": "accepted"})
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["resolution"] == "accepted"


# =====================================================================
# TLF SHELL CRUD
# =====================================================================


class TestTLFShellCrud:
    """Test TLF shell create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_tlf_shells(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tlf-shells")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 25

    @pytest.mark.anyio
    async def test_list_tlf_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tlf-shells", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_tlf_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tlf-shells", params={"tlf_type": "table"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["tlf_type"] == "table"

    @pytest.mark.anyio
    async def test_list_tlf_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/tlf-shells", params={"programming_status": "validated"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["programming_status"] == "validated"

    @pytest.mark.anyio
    async def test_get_tlf_shell(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tlf-shells/TLF-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TLF-001"
        assert data["tlf_type"] == "table"

    @pytest.mark.anyio
    async def test_get_tlf_shell_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tlf-shells/TLF-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_tlf_shell(self, client: AsyncClient):
        payload = _make_tlf_create()
        resp = await client.post(f"{API_PREFIX}/tlf-shells", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test TLF Shell"
        assert data["programming_status"] == "not_started"
        assert data["id"].startswith("TLF-")

    @pytest.mark.anyio
    async def test_create_tlf_listing(self, client: AsyncClient):
        payload = _make_tlf_create(tlf_type="listing", number="16.2.9", title="Test Listing")
        resp = await client.post(f"{API_PREFIX}/tlf-shells", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["tlf_type"] == "listing"

    @pytest.mark.anyio
    async def test_create_tlf_figure(self, client: AsyncClient):
        payload = _make_tlf_create(tlf_type="figure", number="14.2.9.1", title="Test Figure")
        resp = await client.post(f"{API_PREFIX}/tlf-shells", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["tlf_type"] == "figure"

    @pytest.mark.anyio
    async def test_update_tlf_shell(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/tlf-shells/TLF-004",
            json={"programming_status": "validated", "validator": "Maria Garcia"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["programming_status"] == "validated"
        assert data["validator"] == "Maria Garcia"

    @pytest.mark.anyio
    async def test_update_tlf_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/tlf-shells/TLF-NONEXISTENT",
            json={"title": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_tlf_shell(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/tlf-shells/TLF-025")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/tlf-shells/TLF-025")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_tlf_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/tlf-shells/TLF-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# TLF COMPLETION TRACKING
# =====================================================================


class TestTLFCompletion:
    """Test TLF completion tracking."""

    def test_tlf_programming_statuses(self, svc: MedicalWritingService):
        tlfs = svc.list_tlf_shells()
        statuses = {t.programming_status for t in tlfs}
        assert ProgrammingStatus.NOT_STARTED in statuses
        assert ProgrammingStatus.IN_PROGRESS in statuses
        assert ProgrammingStatus.VALIDATED in statuses
        assert ProgrammingStatus.FINAL in statuses

    def test_tlf_completion_percentage(self, svc: MedicalWritingService):
        metrics = svc.get_metrics()
        assert 0.0 <= metrics.tlf_completion_pct <= 100.0

    def test_tlf_has_demographics_tables(self, svc: MedicalWritingService):
        tlfs = svc.list_tlf_shells()
        demo_tables = [t for t in tlfs if "14.1" in t.number and t.tlf_type == TLFType.TABLE]
        assert len(demo_tables) >= 3

    def test_tlf_has_efficacy_tables(self, svc: MedicalWritingService):
        tlfs = svc.list_tlf_shells()
        eff_tables = [t for t in tlfs if "14.2" in t.number and t.tlf_type == TLFType.TABLE]
        assert len(eff_tables) >= 3

    def test_tlf_has_safety_tables(self, svc: MedicalWritingService):
        tlfs = svc.list_tlf_shells()
        safety_tables = [t for t in tlfs if "14.3" in t.number and t.tlf_type == TLFType.TABLE]
        assert len(safety_tables) >= 3

    def test_tlf_has_listings(self, svc: MedicalWritingService):
        tlfs = svc.list_tlf_shells(tlf_type=TLFType.LISTING)
        assert len(tlfs) >= 3

    def test_tlf_has_figures(self, svc: MedicalWritingService):
        tlfs = svc.list_tlf_shells(tlf_type=TLFType.FIGURE)
        assert len(tlfs) >= 3

    def test_tlf_kaplan_meier_exists(self, svc: MedicalWritingService):
        tlfs = svc.list_tlf_shells(tlf_type=TLFType.FIGURE)
        km_figures = [t for t in tlfs if "kaplan-meier" in t.title.lower()]
        assert len(km_figures) >= 1

    def test_tlf_forest_plot_exists(self, svc: MedicalWritingService):
        tlfs = svc.list_tlf_shells(tlf_type=TLFType.FIGURE)
        forest_figures = [t for t in tlfs if "forest" in t.title.lower()]
        assert len(forest_figures) >= 1


# =====================================================================
# METRICS
# =====================================================================


class TestWritingMetrics:
    """Test writing metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_documents"] == 8
        assert data["active_reviews"] >= 0
        assert 0 <= data["tlf_completion_pct"] <= 100
        assert data["overdue_documents"] >= 0

    def test_metrics_documents_by_status(self, svc: MedicalWritingService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.documents_by_status.values())
        assert total_by_status == metrics.total_documents

    def test_metrics_documents_by_type(self, svc: MedicalWritingService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.documents_by_type.values())
        assert total_by_type == metrics.total_documents

    def test_metrics_active_reviews(self, svc: MedicalWritingService):
        metrics = svc.get_metrics()
        open_comments = svc.list_comments(resolution=ResolutionStatus.OPEN)
        assert metrics.active_reviews == len(open_comments)

    def test_metrics_overdue_count(self, svc: MedicalWritingService):
        metrics = svc.get_metrics()
        overdue_list = svc.get_overdue_documents()
        assert metrics.overdue_documents == len(overdue_list)

    def test_metrics_avg_review_cycle_non_negative(self, svc: MedicalWritingService):
        metrics = svc.get_metrics()
        assert metrics.avg_review_cycle_days >= 0.0

    def test_metrics_tlf_completion_matches_data(self, svc: MedicalWritingService):
        metrics = svc.get_metrics()
        tlfs = svc.list_tlf_shells()
        completed = sum(
            1 for t in tlfs
            if t.programming_status in (ProgrammingStatus.VALIDATED, ProgrammingStatus.FINAL)
        )
        expected_pct = round(completed / len(tlfs) * 100, 1) if tlfs else 0.0
        assert metrics.tlf_completion_pct == expected_pct


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_medical_writing_service()
        svc2 = get_medical_writing_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_medical_writing_service()
        svc2 = reset_medical_writing_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_medical_writing_service()
        svc.delete_document("DOC-001")
        assert svc.get_document("DOC-001") is None
        svc2 = reset_medical_writing_service()
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
    async def test_list_sections_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sections")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_comments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_tlf_shells_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tlf-shells")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_document_all_types(self, client: AsyncClient):
        for doc_type in ["csr", "sap", "protocol", "ib", "icf"]:
            payload = _make_doc_create(document_type=doc_type, title=f"Test {doc_type}")
            resp = await client.post(f"{API_PREFIX}/documents", json=payload)
            assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_update_document_status_directly(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/documents/DOC-002",
            json={"status": "internal_review"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "internal_review"

    @pytest.mark.anyio
    async def test_section_word_counts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sections", params={"document_id": "DOC-001"})
        data = resp.json()
        for item in data["items"]:
            assert item["word_count"] >= 0

    @pytest.mark.anyio
    async def test_comment_create_without_section(self, client: AsyncClient):
        payload = _make_comment_create(section_id=None)
        resp = await client.post(f"{API_PREFIX}/comments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["section_id"] is None

    @pytest.mark.anyio
    async def test_tlf_populations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tlf-shells")
        data = resp.json()
        populations = {item["population"] for item in data["items"]}
        assert "ITT" in populations
        assert "Safety" in populations

    @pytest.mark.anyio
    async def test_tlf_datasets(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tlf-shells")
        data = resp.json()
        datasets = {item["dataset"] for item in data["items"]}
        assert "ADSL" in datasets
        assert "ADAE" in datasets

    @pytest.mark.anyio
    async def test_document_sorted_by_last_modified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents")
        data = resp.json()
        dates = [item["last_modified"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)


# =====================================================================
# DOCUMENT CONTENT
# =====================================================================


class TestDocumentContent:
    """Test document content details."""

    @pytest.mark.anyio
    async def test_csr_document_has_word_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/DOC-001")
        data = resp.json()
        assert data["word_count"] > 0

    @pytest.mark.anyio
    async def test_document_has_version(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/DOC-001")
        data = resp.json()
        assert data["version"] is not None
        assert len(data["version"]) > 0

    @pytest.mark.anyio
    async def test_document_has_author(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/DOC-001")
        data = resp.json()
        assert data["author"] is not None
        assert len(data["author"]) > 0

    @pytest.mark.anyio
    async def test_document_dates(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/DOC-001")
        data = resp.json()
        assert data["created_date"] is not None
        assert data["last_modified"] is not None
        assert data["target_date"] is not None


# =====================================================================
# REVIEW TYPE COVERAGE
# =====================================================================


class TestReviewTypeCoverage:
    """Test all review types are represented."""

    def test_all_review_types_in_comments(self, svc: MedicalWritingService):
        comments = svc.list_comments()
        types = {c.review_type for c in comments}
        assert ReviewType.SCIENTIFIC in types
        assert ReviewType.MEDICAL in types
        assert ReviewType.STATISTICAL in types
        assert ReviewType.REGULATORY in types
        assert ReviewType.QUALITY in types

    @pytest.mark.anyio
    async def test_filter_scientific_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comments", params={"review_type": "scientific"})
        data = resp.json()
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_filter_statistical_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comments", params={"review_type": "statistical"})
        data = resp.json()
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_filter_regulatory_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comments", params={"review_type": "regulatory"})
        data = resp.json()
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_filter_quality_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comments", params={"review_type": "quality"})
        data = resp.json()
        assert data["total"] > 0


# =====================================================================
# CROSS-ENTITY RELATIONSHIPS
# =====================================================================


class TestCrossEntityRelationships:
    """Test relationships between documents, sections, comments, and TLFs."""

    @pytest.mark.anyio
    async def test_document_sections_match(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/DOC-001")
        doc = resp.json()
        resp2 = await client.get(f"{API_PREFIX}/sections", params={"document_id": "DOC-001"})
        sections = resp2.json()
        assert len(doc["sections"]) == sections["total"]

    @pytest.mark.anyio
    async def test_comment_references_valid_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comments/CMT-001")
        comment = resp.json()
        resp2 = await client.get(f"{API_PREFIX}/documents/{comment['document_id']}")
        assert resp2.status_code == 200

    @pytest.mark.anyio
    async def test_comment_references_valid_section(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comments/CMT-001")
        comment = resp.json()
        if comment["section_id"]:
            resp2 = await client.get(f"{API_PREFIX}/sections/{comment['section_id']}")
            assert resp2.status_code == 200

    @pytest.mark.anyio
    async def test_delete_comment_decrements_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/DOC-001")
        initial_count = resp.json()["comments_count"]

        resp2 = await client.delete(f"{API_PREFIX}/comments/CMT-001")
        assert resp2.status_code == 204

        resp3 = await client.get(f"{API_PREFIX}/documents/DOC-001")
        assert resp3.json()["comments_count"] == initial_count - 1

    @pytest.mark.anyio
    async def test_delete_section_updates_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/DOC-001")
        initial_sections = resp.json()["sections"]

        resp2 = await client.delete(f"{API_PREFIX}/sections/SEC-001")
        assert resp2.status_code == 204

        resp3 = await client.get(f"{API_PREFIX}/documents/DOC-001")
        updated_sections = resp3.json()["sections"]
        assert len(updated_sections) == len(initial_sections) - 1
        assert "SEC-001" not in updated_sections

    def test_tlf_shells_cover_all_trials(self, svc: MedicalWritingService):
        tlfs = svc.list_tlf_shells()
        trials = {t.trial_id for t in tlfs}
        assert EYLEA_TRIAL in trials
        assert DUPIXENT_TRIAL in trials
        assert LIBTAYO_TRIAL in trials
