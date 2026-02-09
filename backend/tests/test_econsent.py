"""Tests for Electronic Informed Consent (eConsent) Management (CLINICAL-18).

Covers:
- Seed data verification (documents, consents, withdrawals, audit entries)
- Consent document CRUD (create, read, update, delete, list, filter by trial/type/language)
- Element management (add elements to documents, quiz elements)
- Patient consent CRUD (create, read, update, list, filter by patient/trial/site/status)
- Consent signing with 21 CFR Part 11 compliance
- Quiz validation with 80% pass threshold
- Element viewing and completion tracking
- Consent withdrawal with data retention preferences
- Audit trail verification (viewed, signed, withdrawn, re-consented)
- Re-consent tracking for protocol amendments
- Comprehension analytics (scores, pass rates, distribution)
- eConsent metrics computation
- Error handling (404s, 400s, invalid operations)
- Edge cases (empty filters, boundary conditions, already-signed/withdrawn)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.econsent import (
    ComprehensionAnalytics,
    ConsentAuditAction,
    ConsentDocumentCreate,
    ConsentDocumentUpdate,
    ConsentElementCreate,
    ConsentElementType,
    ConsentSignRequest,
    ConsentStatus,
    ConsentType,
    ConsentWithdrawalCreate,
    DataRetentionPreference,
    DocumentLanguage,
    PatientConsentCreate,
    PatientConsentUpdate,
    ViewElementRequest,
    CompleteElementRequest,
)
from app.services.econsent_service import (
    EConsentService,
    QUIZ_PASS_THRESHOLD,
    get_econsent_service,
    reset_econsent_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/econsent"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_econsent_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> EConsentService:
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
        "version": "4.0",
        "title": "Test Consent Document",
        "consent_type": "main_study",
        "effective_date": now.isoformat(),
        "language": "en",
        "irb_approval_date": (now - timedelta(days=10)).isoformat(),
        "total_pages": 12,
        "estimated_read_time_minutes": 25,
    }
    defaults.update(overrides)
    return defaults


def _make_consent_create(**overrides) -> dict:
    defaults = {
        "patient_id": "PAT-9999",
        "trial_id": EYLEA_TRIAL,
        "document_id": "CDOC-001",
        "site_id": "SITE-101",
    }
    defaults.update(overrides)
    return defaults


def _make_sign_request(**overrides) -> dict:
    defaults = {
        "ip_address": "10.0.0.1",
        "device_info": "Chrome 121 / macOS 15",
        "witness_name": "Dr. Test Witness",
    }
    defaults.update(overrides)
    return defaults


def _make_element_create(**overrides) -> dict:
    defaults = {
        "element_type": "text",
        "page_number": 1,
        "content_summary": "Test element content",
        "required": True,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_documents_count(self, svc: EConsentService):
        docs = svc.list_documents()
        assert len(docs) == 6

    def test_seed_documents_types(self, svc: EConsentService):
        docs = svc.list_documents()
        types = {d.consent_type for d in docs}
        assert ConsentType.MAIN_STUDY in types
        assert ConsentType.BIOBANKING in types
        assert ConsentType.GENETIC_TESTING in types
        assert ConsentType.PEDIATRIC_ASSENT in types

    def test_seed_documents_have_elements(self, svc: EConsentService):
        doc = svc.get_document("CDOC-001")
        assert doc is not None
        assert len(doc.elements) == 8

    def test_seed_documents_have_quiz_elements(self, svc: EConsentService):
        doc = svc.get_document("CDOC-001")
        assert doc is not None
        quiz_elements = [e for e in doc.elements if e.element_type == ConsentElementType.QUIZ]
        assert len(quiz_elements) >= 2
        for qe in quiz_elements:
            assert qe.quiz_question is not None
            assert qe.quiz_correct_answer is not None
            assert qe.quiz_options is not None
            assert len(qe.quiz_options) == 4

    def test_seed_consents_count(self, svc: EConsentService):
        consents = svc.list_consents()
        assert len(consents) == 40

    def test_seed_consents_statuses(self, svc: EConsentService):
        consents = svc.list_consents()
        statuses = {c.status for c in consents}
        assert ConsentStatus.SIGNED in statuses
        assert ConsentStatus.IN_PROGRESS in statuses
        assert ConsentStatus.NOT_STARTED in statuses
        assert ConsentStatus.RE_CONSENTED in statuses
        assert ConsentStatus.WITHDRAWN in statuses

    def test_seed_withdrawals_count(self, svc: EConsentService):
        withdrawals = svc.list_withdrawals()
        assert len(withdrawals) == 5

    def test_seed_audit_entries_count(self, svc: EConsentService):
        entries = svc.list_audit_entries()
        assert len(entries) >= 60

    def test_seed_signed_consents_have_quiz_scores(self, svc: EConsentService):
        signed = svc.list_consents(status=ConsentStatus.SIGNED)
        scored = [c for c in signed if c.quiz_score is not None]
        assert len(scored) > 0
        for c in scored:
            assert 0 <= c.quiz_score <= 100

    def test_seed_re_consented_have_reason(self, svc: EConsentService):
        re_consented = svc.list_consents(status=ConsentStatus.RE_CONSENTED)
        assert len(re_consented) == 3
        for c in re_consented:
            assert c.re_consent_reason is not None

    def test_seed_withdrawn_consents_match_withdrawals(self, svc: EConsentService):
        withdrawn = svc.list_consents(status=ConsentStatus.WITHDRAWN)
        withdrawals = svc.list_withdrawals()
        withdrawn_ids = {c.id for c in withdrawn}
        withdrawal_consent_ids = {w.patient_consent_id for w in withdrawals}
        assert withdrawal_consent_ids.issubset(withdrawn_ids)


# =====================================================================
# DOCUMENT CRUD
# =====================================================================


class TestDocumentCrud:
    """Test consent document CRUD operations."""

    @pytest.mark.anyio
    async def test_list_documents(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6
        assert len(data["items"]) == 6

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
        resp = await client.get(f"{API_PREFIX}/documents", params={"consent_type": "biobanking"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["consent_type"] == "biobanking"

    @pytest.mark.anyio
    async def test_list_documents_filter_language(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents", params={"language": "en"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6  # all seeded docs are English

    @pytest.mark.anyio
    async def test_get_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/CDOC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CDOC-001"
        assert data["consent_type"] == "main_study"
        assert "elements" in data
        assert len(data["elements"]) == 8

    @pytest.mark.anyio
    async def test_get_document_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/CDOC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_document(self, client: AsyncClient):
        payload = _make_doc_create()
        resp = await client.post(f"{API_PREFIX}/documents", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Consent Document"
        assert data["id"].startswith("CDOC-")
        assert data["consent_type"] == "main_study"

    @pytest.mark.anyio
    async def test_create_document_biobanking(self, client: AsyncClient):
        payload = _make_doc_create(consent_type="biobanking", title="Biobanking Consent")
        resp = await client.post(f"{API_PREFIX}/documents", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["consent_type"] == "biobanking"

    @pytest.mark.anyio
    async def test_update_document(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/documents/CDOC-001",
            json={"title": "Updated EYLEA Consent", "version": "3.1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated EYLEA Consent"
        assert data["version"] == "3.1"

    @pytest.mark.anyio
    async def test_update_document_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/documents/CDOC-NONEXISTENT",
            json={"title": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_document(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/documents/CDOC-006")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/documents/CDOC-006")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_document_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/documents/CDOC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# ELEMENT MANAGEMENT
# =====================================================================


class TestElementManagement:
    """Test adding elements to consent documents."""

    @pytest.mark.anyio
    async def test_add_text_element(self, client: AsyncClient):
        payload = _make_element_create(element_type="text", content_summary="New text section")
        resp = await client.post(f"{API_PREFIX}/documents/CDOC-004/elements", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["elements"]) == 4  # was 3, now 4

    @pytest.mark.anyio
    async def test_add_quiz_element(self, client: AsyncClient):
        payload = _make_element_create(
            element_type="quiz",
            page_number=5,
            content_summary="New quiz question",
            quiz_question="What is the purpose of biobanking?",
            quiz_correct_answer="To store biological samples for future research",
            quiz_options=[
                "To store biological samples for future research",
                "To create genetic clones",
                "To sell samples commercially",
                "To replace standard lab tests",
            ],
        )
        resp = await client.post(f"{API_PREFIX}/documents/CDOC-004/elements", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        quiz_elements = [e for e in data["elements"] if e["element_type"] == "quiz"]
        assert len(quiz_elements) >= 1

    @pytest.mark.anyio
    async def test_add_signature_element(self, client: AsyncClient):
        payload = _make_element_create(
            element_type="signature",
            page_number=10,
            content_summary="Additional signature block",
        )
        resp = await client.post(f"{API_PREFIX}/documents/CDOC-004/elements", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_add_video_element(self, client: AsyncClient):
        payload = _make_element_create(
            element_type="video",
            page_number=2,
            content_summary="Overview video",
        )
        resp = await client.post(f"{API_PREFIX}/documents/CDOC-004/elements", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_add_checkbox_element(self, client: AsyncClient):
        payload = _make_element_create(
            element_type="checkbox",
            page_number=7,
            content_summary="Acknowledge risks checkbox",
        )
        resp = await client.post(f"{API_PREFIX}/documents/CDOC-004/elements", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_add_acknowledgment_element(self, client: AsyncClient):
        payload = _make_element_create(
            element_type="acknowledgment",
            page_number=9,
            content_summary="HIPAA acknowledgment",
        )
        resp = await client.post(f"{API_PREFIX}/documents/CDOC-004/elements", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_add_element_document_not_found(self, client: AsyncClient):
        payload = _make_element_create()
        resp = await client.post(f"{API_PREFIX}/documents/CDOC-NONEXISTENT/elements", json=payload)
        assert resp.status_code == 404


# =====================================================================
# PATIENT CONSENT CRUD
# =====================================================================


class TestPatientConsentCrud:
    """Test patient consent CRUD operations."""

    @pytest.mark.anyio
    async def test_list_consents(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 40

    @pytest.mark.anyio
    async def test_list_consents_filter_patient(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consents", params={"patient_id": "PAT-0001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["patient_id"] == "PAT-0001"

    @pytest.mark.anyio
    async def test_list_consents_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consents", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_consents_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consents", params={"site_id": "SITE-101"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_consents_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consents", params={"status": "signed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "signed"

    @pytest.mark.anyio
    async def test_list_consents_filter_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consents", params={"document_id": "CDOC-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["document_id"] == "CDOC-001"

    @pytest.mark.anyio
    async def test_get_consent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consents/PC-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PC-0001"
        assert data["status"] in ("signed", "withdrawn")

    @pytest.mark.anyio
    async def test_get_consent_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consents/PC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_consent(self, client: AsyncClient):
        payload = _make_consent_create()
        resp = await client.post(f"{API_PREFIX}/consents", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == "PAT-9999"
        assert data["status"] == "not_started"
        assert data["id"].startswith("PC-")

    @pytest.mark.anyio
    async def test_update_consent(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/consents/PC-0034",
            json={"witness_name": "Dr. New Witness"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["witness_name"] == "Dr. New Witness"

    @pytest.mark.anyio
    async def test_update_consent_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/consents/PC-NONEXISTENT",
            json={"witness_name": "Test"},
        )
        assert resp.status_code == 404


# =====================================================================
# CONSENT SIGNING (21 CFR Part 11)
# =====================================================================


class TestConsentSigning:
    """Test consent signing with 21 CFR Part 11 compliance."""

    @pytest.mark.anyio
    async def test_sign_consent_in_progress(self, client: AsyncClient):
        """Sign a consent that is in_progress (LIBTAYO, PC-0026)."""
        # PC-0026 is in_progress for CDOC-003 which has 1 quiz element
        payload = _make_sign_request(
            quiz_answers={"EL-003-03": "An immune checkpoint inhibitor"},
        )
        resp = await client.post(f"{API_PREFIX}/consents/PC-0026/sign", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "signed"
        assert data["signature_date"] is not None
        assert data["ip_address"] == "10.0.0.1"
        assert data["device_info"] == "Chrome 121 / macOS 15"
        assert data["quiz_score"] == 100.0

    @pytest.mark.anyio
    async def test_sign_consent_with_witness(self, client: AsyncClient):
        payload = _make_sign_request(
            witness_name="Dr. Jane Smith",
            quiz_answers={"EL-003-03": "An immune checkpoint inhibitor"},
        )
        resp = await client.post(f"{API_PREFIX}/consents/PC-0027/sign", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["witness_name"] == "Dr. Jane Smith"
        assert data["witness_signature_date"] is not None

    @pytest.mark.anyio
    async def test_sign_consent_quiz_fail(self, client: AsyncClient):
        """Quiz score below 80% should fail."""
        payload = _make_sign_request(
            quiz_answers={"EL-003-03": "A dietary supplement"},  # Wrong answer
        )
        resp = await client.post(f"{API_PREFIX}/consents/PC-0028/sign", json=payload)
        assert resp.status_code == 400
        body = resp.json()
        detail = body.get("detail", body.get("message", str(body)))
        assert "threshold" in detail.lower()

    @pytest.mark.anyio
    async def test_sign_consent_already_signed(self, client: AsyncClient):
        """Signing already-signed consent should fail."""
        payload = _make_sign_request()
        resp = await client.post(f"{API_PREFIX}/consents/PC-0001/sign", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_sign_consent_not_found(self, client: AsyncClient):
        payload = _make_sign_request()
        resp = await client.post(f"{API_PREFIX}/consents/PC-NONEXISTENT/sign", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_sign_consent_no_quiz(self, client: AsyncClient):
        """Sign consent without quiz answers (document without quiz elements)."""
        # First create a consent for CDOC-004 (biobanking, no quiz)
        create_payload = _make_consent_create(document_id="CDOC-004", patient_id="PAT-9998")
        create_resp = await client.post(f"{API_PREFIX}/consents", json=create_payload)
        assert create_resp.status_code == 201
        consent_id = create_resp.json()["id"]

        # Sign without quiz answers
        sign_payload = _make_sign_request()
        resp = await client.post(f"{API_PREFIX}/consents/{consent_id}/sign", json=sign_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "signed"

    @pytest.mark.anyio
    async def test_sign_re_consent(self, client: AsyncClient):
        """Signing a consent with re_consent_reason should set status to re_consented."""
        # Create a consent with re_consent_reason
        create_payload = _make_consent_create(patient_id="PAT-9997")
        create_resp = await client.post(f"{API_PREFIX}/consents", json=create_payload)
        consent_id = create_resp.json()["id"]

        # Update with re_consent_reason
        await client.put(
            f"{API_PREFIX}/consents/{consent_id}",
            json={"re_consent_reason": "Protocol Amendment 4"},
        )

        # Sign with correct quiz answers
        sign_payload = _make_sign_request(
            quiz_answers={
                "EL-001-04": "To evaluate the efficacy of EYLEA HD for wet AMD",
                "EL-001-05": "Eye infection or inflammation",
            },
        )
        resp = await client.post(f"{API_PREFIX}/consents/{consent_id}/sign", json=sign_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "re_consented"

    def test_sign_consent_records_time_spent(self, svc: EConsentService):
        """Signing should calculate time_spent_minutes from started_at."""
        # PC-0026 is in_progress with started_at
        consent = svc.get_consent("PC-0026")
        assert consent is not None
        assert consent.started_at is not None

        result = svc.sign_consent(
            "PC-0026",
            ConsentSignRequest(
                ip_address="10.0.0.1",
                device_info="Test",
                quiz_answers={"EL-003-03": "An immune checkpoint inhibitor"},
            ),
        )
        assert result is not None
        assert result.time_spent_minutes is not None
        assert result.time_spent_minutes > 0

    def test_sign_consent_creates_audit_entry(self, svc: EConsentService):
        """Signing should create an audit trail entry."""
        initial_audit_count = len(svc.list_audit_entries())
        svc.sign_consent(
            "PC-0027",
            ConsentSignRequest(
                ip_address="10.0.0.2",
                device_info="Test",
                quiz_answers={"EL-003-03": "An immune checkpoint inhibitor"},
            ),
        )
        new_audit_count = len(svc.list_audit_entries())
        assert new_audit_count > initial_audit_count


# =====================================================================
# ELEMENT VIEWING & COMPLETION
# =====================================================================


class TestElementTracking:
    """Test element viewing and completion tracking."""

    @pytest.mark.anyio
    async def test_view_element(self, client: AsyncClient):
        payload = {"element_id": "EL-003-04", "time_spent_seconds": 30.0}
        resp = await client.post(f"{API_PREFIX}/consents/PC-0026/view-element", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "EL-003-04" in data["elements_viewed"]

    @pytest.mark.anyio
    async def test_view_element_starts_consent(self, client: AsyncClient):
        """Viewing an element on a not_started consent should set it to in_progress."""
        # PC-0034 is not_started
        payload = {"element_id": "EL-003-01", "time_spent_seconds": 10.0}
        resp = await client.post(f"{API_PREFIX}/consents/PC-0034/view-element", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["started_at"] is not None

    @pytest.mark.anyio
    async def test_view_element_idempotent(self, client: AsyncClient):
        """Viewing the same element twice should not duplicate it."""
        payload = {"element_id": "EL-003-01", "time_spent_seconds": 15.0}
        await client.post(f"{API_PREFIX}/consents/PC-0026/view-element", json=payload)
        resp = await client.post(f"{API_PREFIX}/consents/PC-0026/view-element", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        count = data["elements_viewed"].count("EL-003-01")
        assert count == 1

    @pytest.mark.anyio
    async def test_view_element_not_found(self, client: AsyncClient):
        payload = {"element_id": "EL-001-01", "time_spent_seconds": 5.0}
        resp = await client.post(f"{API_PREFIX}/consents/PC-NONEXISTENT/view-element", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_complete_element(self, client: AsyncClient):
        payload = {"element_id": "EL-003-04"}
        resp = await client.post(f"{API_PREFIX}/consents/PC-0026/complete-element", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "EL-003-04" in data["elements_completed"]

    @pytest.mark.anyio
    async def test_complete_element_idempotent(self, client: AsyncClient):
        payload = {"element_id": "EL-003-01"}
        await client.post(f"{API_PREFIX}/consents/PC-0026/complete-element", json=payload)
        resp = await client.post(f"{API_PREFIX}/consents/PC-0026/complete-element", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        count = data["elements_completed"].count("EL-003-01")
        assert count == 1

    @pytest.mark.anyio
    async def test_complete_element_not_found(self, client: AsyncClient):
        payload = {"element_id": "EL-001-01"}
        resp = await client.post(f"{API_PREFIX}/consents/PC-NONEXISTENT/complete-element", json=payload)
        assert resp.status_code == 404


# =====================================================================
# WITHDRAWAL MANAGEMENT
# =====================================================================


class TestWithdrawalManagement:
    """Test consent withdrawal operations."""

    @pytest.mark.anyio
    async def test_list_withdrawals(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_withdrawals_filter_patient(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawals", params={"patient_id": "PAT-0005"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["patient_id"] == "PAT-0005"

    @pytest.mark.anyio
    async def test_get_withdrawal(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawals/WD-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "WD-001"
        assert data["data_retention_preference"] == "retain_anonymized"

    @pytest.mark.anyio
    async def test_get_withdrawal_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawals/WD-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_withdraw_consent(self, client: AsyncClient):
        # PC-0026 is in_progress
        payload = {
            "reason": "Changed mind about participation",
            "data_retention_preference": "delete_all",
            "specimens_disposition": "Destroy all samples",
        }
        resp = await client.post(f"{API_PREFIX}/consents/PC-0026/withdraw", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["reason"] == "Changed mind about participation"
        assert data["data_retention_preference"] == "delete_all"

        # Verify consent status is now withdrawn
        resp2 = await client.get(f"{API_PREFIX}/consents/PC-0026")
        assert resp2.json()["status"] == "withdrawn"

    @pytest.mark.anyio
    async def test_withdraw_consent_already_withdrawn(self, client: AsyncClient):
        """Cannot withdraw an already-withdrawn consent."""
        payload = {
            "reason": "Test",
            "data_retention_preference": "retain_anonymized",
        }
        # PC-0005 was already withdrawn in seed data
        resp = await client.post(f"{API_PREFIX}/consents/PC-0005/withdraw", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_withdraw_consent_not_found(self, client: AsyncClient):
        payload = {
            "reason": "Test",
            "data_retention_preference": "retain_anonymized",
        }
        resp = await client.post(f"{API_PREFIX}/consents/PC-NONEXISTENT/withdraw", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_withdraw_creates_audit_entry(self, client: AsyncClient):
        """Withdrawing should create an audit trail entry."""
        resp_before = await client.get(f"{API_PREFIX}/audit")
        count_before = resp_before.json()["total"]

        payload = {
            "reason": "Moving away",
            "data_retention_preference": "retain_identified",
        }
        await client.post(f"{API_PREFIX}/consents/PC-0027/withdraw", json=payload)

        resp_after = await client.get(f"{API_PREFIX}/audit")
        count_after = resp_after.json()["total"]
        assert count_after > count_before

    @pytest.mark.anyio
    async def test_withdrawal_data_retention_preferences(self, client: AsyncClient):
        """Test different data retention preferences."""
        # retain_anonymized
        payload = {
            "reason": "Test 1",
            "data_retention_preference": "retain_anonymized",
        }
        resp = await client.post(f"{API_PREFIX}/consents/PC-0028/withdraw", json=payload)
        assert resp.status_code == 200
        assert resp.json()["data_retention_preference"] == "retain_anonymized"


# =====================================================================
# AUDIT TRAIL (21 CFR Part 11)
# =====================================================================


class TestAuditTrail:
    """Test 21 CFR Part 11 compliant audit trail."""

    @pytest.mark.anyio
    async def test_list_audit_entries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 60

    @pytest.mark.anyio
    async def test_list_audit_filter_consent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit", params={"patient_consent_id": "PC-0001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["patient_consent_id"] == "PC-0001"

    @pytest.mark.anyio
    async def test_list_audit_filter_action(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit", params={"action": "signed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["action"] == "signed"

    @pytest.mark.anyio
    async def test_get_audit_entry(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit/AUD-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "AUD-0001"

    @pytest.mark.anyio
    async def test_get_audit_entry_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit/AUD-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_audit_entries_have_timestamps(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit")
        data = resp.json()
        for item in data["items"]:
            assert item["timestamp"] is not None

    @pytest.mark.anyio
    async def test_audit_entries_sorted_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit")
        data = resp.json()
        timestamps = [item["timestamp"] for item in data["items"]]
        assert timestamps == sorted(timestamps, reverse=True)

    @pytest.mark.anyio
    async def test_audit_has_viewed_actions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit", params={"action": "viewed"})
        data = resp.json()
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_audit_has_signed_actions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit", params={"action": "signed"})
        data = resp.json()
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_audit_has_withdrawn_actions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit", params={"action": "withdrawn"})
        data = resp.json()
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_audit_has_re_consented_actions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit", params={"action": "re_consented"})
        data = resp.json()
        assert data["total"] > 0


# =====================================================================
# RE-CONSENT TRACKING
# =====================================================================


class TestReConsentTracking:
    """Test re-consent tracking for protocol amendments."""

    @pytest.mark.anyio
    async def test_re_consent_pending_list(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/re-consent-pending")
        assert resp.status_code == 200
        data = resp.json()
        # May be empty if no version mismatches in seed data
        assert "total" in data
        assert "items" in data

    @pytest.mark.anyio
    async def test_re_consent_pending_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/re-consent-pending",
            params={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 200

    def test_re_consented_patients_exist(self, svc: EConsentService):
        re_consented = svc.list_consents(status=ConsentStatus.RE_CONSENTED)
        assert len(re_consented) == 3
        for c in re_consented:
            assert c.re_consent_reason is not None
            assert "Amendment" in c.re_consent_reason


# =====================================================================
# COMPREHENSION ANALYTICS
# =====================================================================


class TestComprehensionAnalytics:
    """Test comprehension analytics for quiz performance."""

    @pytest.mark.anyio
    async def test_get_comprehension_analytics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comprehension-analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_quizzes_taken"] > 0
        assert 0 <= data["avg_score"] <= 100
        assert 0 <= data["pass_rate"] <= 100
        assert "score_distribution" in data

    @pytest.mark.anyio
    async def test_comprehension_analytics_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/comprehension-analytics",
            params={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_quizzes_taken"] > 0

    @pytest.mark.anyio
    async def test_comprehension_score_distribution_keys(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comprehension-analytics")
        data = resp.json()
        dist = data["score_distribution"]
        expected_keys = {"0-59", "60-69", "70-79", "80-89", "90-100"}
        assert set(dist.keys()) == expected_keys

    def test_comprehension_analytics_pass_rate(self, svc: EConsentService):
        analytics = svc.get_comprehension_analytics()
        assert analytics.pass_rate >= 0
        assert analytics.pass_rate <= 100

    def test_comprehension_analytics_avg_time(self, svc: EConsentService):
        analytics = svc.get_comprehension_analytics()
        assert analytics.avg_time_spent_minutes >= 0

    def test_comprehension_analytics_empty_trial(self, svc: EConsentService):
        analytics = svc.get_comprehension_analytics(trial_id="NONEXISTENT-TRIAL")
        assert analytics.total_quizzes_taken == 0
        assert analytics.avg_score == 0.0
        assert analytics.pass_rate == 0.0


# =====================================================================
# METRICS
# =====================================================================


class TestEConsentMetrics:
    """Test eConsent metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_documents"] == 6
        assert data["total_consents"] == 40
        assert data["avg_completion_time_minutes"] > 0
        assert 0 <= data["avg_quiz_score"] <= 100
        assert 0 <= data["withdrawal_rate"] <= 100
        assert data["re_consent_pending"] >= 0

    def test_metrics_consents_by_status(self, svc: EConsentService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.consents_by_status.values())
        assert total_by_status == metrics.total_consents

    def test_metrics_language_distribution(self, svc: EConsentService):
        metrics = svc.get_metrics()
        assert "en" in metrics.language_distribution

    def test_metrics_withdrawal_rate_calculation(self, svc: EConsentService):
        metrics = svc.get_metrics()
        assert metrics.withdrawal_rate > 0  # We have 5 withdrawals

    def test_metrics_avg_quiz_score_within_range(self, svc: EConsentService):
        metrics = svc.get_metrics()
        assert 0 <= metrics.avg_quiz_score <= 100


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_econsent_service()
        svc2 = get_econsent_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_econsent_service()
        svc2 = reset_econsent_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_econsent_service()
        svc.delete_document("CDOC-001")
        assert svc.get_document("CDOC-001") is None
        svc2 = reset_econsent_service()
        assert svc2.get_document("CDOC-001") is not None


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
    async def test_list_consents_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consents")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_withdrawals_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawals")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_audit_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_document_all_consent_types(self, client: AsyncClient):
        for ct in ["main_study", "sub_study", "biobanking", "genetic_testing",
                    "future_research", "pediatric_assent", "lar_consent"]:
            payload = _make_doc_create(consent_type=ct, title=f"Test {ct}")
            resp = await client.post(f"{API_PREFIX}/documents", json=payload)
            assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_create_document_all_languages(self, client: AsyncClient):
        for lang in ["en", "es", "fr", "de", "ja", "zh", "ko", "pt"]:
            payload = _make_doc_create(language=lang, title=f"Test {lang}")
            resp = await client.post(f"{API_PREFIX}/documents", json=payload)
            assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_withdraw_and_verify_count(self, client: AsyncClient):
        """Withdrawal should increase the withdrawal count."""
        resp1 = await client.get(f"{API_PREFIX}/withdrawals")
        count_before = resp1.json()["total"]

        payload = {
            "reason": "Moving to another country",
            "data_retention_preference": "delete_all",
        }
        await client.post(f"{API_PREFIX}/consents/PC-0029/withdraw", json=payload)

        resp2 = await client.get(f"{API_PREFIX}/withdrawals")
        count_after = resp2.json()["total"]
        assert count_after == count_before + 1

    @pytest.mark.anyio
    async def test_signed_consent_has_all_metadata(self, client: AsyncClient):
        """Verify signed consents have complete metadata."""
        resp = await client.get(f"{API_PREFIX}/consents", params={"status": "signed"})
        data = resp.json()
        for item in data["items"]:
            assert item["signature_date"] is not None
            assert item["ip_address"] is not None
            assert item["device_info"] is not None

    @pytest.mark.anyio
    async def test_not_started_consent_has_no_metadata(self, client: AsyncClient):
        """Not-started consents should have minimal metadata."""
        resp = await client.get(f"{API_PREFIX}/consents", params={"status": "not_started"})
        data = resp.json()
        for item in data["items"]:
            assert item["signature_date"] is None
            assert item["started_at"] is None
            assert item["completed_at"] is None

    @pytest.mark.anyio
    async def test_in_progress_consent_has_started_at(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consents", params={"status": "in_progress"})
        data = resp.json()
        for item in data["items"]:
            assert item["started_at"] is not None
            assert item["signature_date"] is None

    @pytest.mark.anyio
    async def test_document_elements_have_required_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/CDOC-001")
        data = resp.json()
        for element in data["elements"]:
            assert "id" in element
            assert "element_type" in element
            assert "page_number" in element
            assert "content_summary" in element
            assert "required" in element


# =====================================================================
# DOCUMENT DETAILS
# =====================================================================


class TestDocumentDetails:
    """Test detailed document structure."""

    @pytest.mark.anyio
    async def test_document_has_version(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/CDOC-001")
        data = resp.json()
        assert data["version"] == "3.0"

    @pytest.mark.anyio
    async def test_document_has_irb_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/CDOC-001")
        data = resp.json()
        assert data["irb_approval_date"] is not None

    @pytest.mark.anyio
    async def test_document_has_read_time(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/CDOC-001")
        data = resp.json()
        assert data["estimated_read_time_minutes"] == 35

    @pytest.mark.anyio
    async def test_document_has_pages(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/CDOC-001")
        data = resp.json()
        assert data["total_pages"] == 18

    @pytest.mark.anyio
    async def test_document_element_types(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/CDOC-001")
        data = resp.json()
        types = {e["element_type"] for e in data["elements"]}
        assert "text" in types
        assert "video" in types
        assert "quiz" in types
        assert "signature" in types
        assert "checkbox" in types
        assert "acknowledgment" in types

    @pytest.mark.anyio
    async def test_quiz_element_has_options(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/CDOC-001")
        data = resp.json()
        quiz_elements = [e for e in data["elements"] if e["element_type"] == "quiz"]
        for qe in quiz_elements:
            assert qe["quiz_question"] is not None
            assert qe["quiz_correct_answer"] is not None
            assert qe["quiz_options"] is not None
            assert len(qe["quiz_options"]) == 4

    @pytest.mark.anyio
    async def test_pediatric_assent_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/CDOC-006")
        data = resp.json()
        assert data["consent_type"] == "pediatric_assent"
        assert data["estimated_read_time_minutes"] == 10
        assert data["total_pages"] == 6


# =====================================================================
# CONSENT STATUS ENUMERATION
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout the system."""

    @pytest.mark.anyio
    async def test_all_consent_statuses_represented(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/consents")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "signed" in statuses
        assert "in_progress" in statuses
        assert "not_started" in statuses
        assert "re_consented" in statuses
        assert "withdrawn" in statuses

    @pytest.mark.anyio
    async def test_all_consent_types_in_documents(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents")
        data = resp.json()
        types = {item["consent_type"] for item in data["items"]}
        assert "main_study" in types
        assert "biobanking" in types
        assert "genetic_testing" in types
        assert "pediatric_assent" in types

    @pytest.mark.anyio
    async def test_all_element_types_in_documents(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/CDOC-001")
        data = resp.json()
        types = {e["element_type"] for e in data["elements"]}
        assert "text" in types
        assert "video" in types
        assert "quiz" in types
        assert "signature" in types
        assert "checkbox" in types
        assert "acknowledgment" in types

    @pytest.mark.anyio
    async def test_audit_action_types(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/audit")
        data = resp.json()
        actions = {item["action"] for item in data["items"]}
        assert "viewed" in actions
        assert "signed" in actions

    @pytest.mark.anyio
    async def test_data_retention_preferences_in_withdrawals(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/withdrawals")
        data = resp.json()
        prefs = {item["data_retention_preference"] for item in data["items"]}
        assert "retain_anonymized" in prefs
        assert "retain_identified" in prefs
        assert "delete_all" in prefs
