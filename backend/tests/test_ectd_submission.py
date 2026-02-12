"""Tests for eCTD Submission Management (eCTD-MGMT).

Covers:
- Seed data verification (sequences, documents, validations, HA responses, plans)
- ECTDSequence CRUD (create, read, update, delete, list, filter)
- ECTDDocument CRUD (create, read, update, delete, list, filter)
- ECTDValidation CRUD (create, read, delete, list, filter)
- HAResponse CRUD (create, read, update, delete, list, filter)
- SubmissionPlan CRUD (create, read, update, delete, list, filter)
- ECTDMetrics computation
- Error handling (404s, validation errors)
- Edge cases and boundary conditions
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.ectd_submission import (
    CTDModule,
    DocumentLifecycle,
    ECTDDocumentCreate,
    ECTDDocumentUpdate,
    ECTDSequenceCreate,
    ECTDSequenceUpdate,
    ECTDValidationCreate,
    HAResponseCreate,
    HAResponseType,
    HAResponseUpdate,
    RegulatoryRegion,
    SequenceStatus,
    SubmissionPlanCreate,
    SubmissionPlanUpdate,
    SubmissionType,
)
from app.services.ectd_submission_service import (
    ECTDSubmissionService,
    get_ectd_submission_service,
    reset_ectd_submission_service,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/ectd-submission"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_ectd_submission_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ECTDSubmissionService:
    return fresh_service


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as c:
        yield c


# ===========================================================================
# Seed Data Verification
# ===========================================================================


class TestSeedData:
    """Verify demo data was seeded correctly."""

    def test_seed_sequences_count(self, svc: ECTDSubmissionService):
        assert len(svc._sequences) == 12

    def test_seed_documents_count(self, svc: ECTDSubmissionService):
        assert len(svc._documents) == 15

    def test_seed_validations_count(self, svc: ECTDSubmissionService):
        assert len(svc._validations) == 12

    def test_seed_ha_responses_count(self, svc: ECTDSubmissionService):
        assert len(svc._ha_responses) == 10

    def test_seed_plans_count(self, svc: ECTDSubmissionService):
        assert len(svc._plans) == 10

    def test_seed_sequence_001_exists(self, svc: ECTDSubmissionService):
        seq = svc.get_sequence("SEQ-001")
        assert seq is not None
        assert seq.trial_id == EYLEA_TRIAL
        assert seq.submission_type == SubmissionType.INITIAL
        assert seq.region == RegulatoryRegion.US_FDA
        assert seq.status == SequenceStatus.SUBMITTED

    def test_seed_sequence_004_dupixent(self, svc: ECTDSubmissionService):
        seq = svc.get_sequence("SEQ-004")
        assert seq is not None
        assert seq.trial_id == DUPIXENT_TRIAL
        assert seq.submission_type == SubmissionType.SUPPLEMENT

    def test_seed_sequence_008_libtayo(self, svc: ECTDSubmissionService):
        seq = svc.get_sequence("SEQ-008")
        assert seq is not None
        assert seq.trial_id == LIBTAYO_TRIAL
        assert seq.status == SequenceStatus.READY

    def test_seed_document_001(self, svc: ECTDSubmissionService):
        doc = svc.get_document("DOC-001")
        assert doc is not None
        assert doc.module == CTDModule.MODULE_1
        assert doc.approved is True

    def test_seed_document_005_module5(self, svc: ECTDSubmissionService):
        doc = svc.get_document("DOC-005")
        assert doc is not None
        assert doc.module == CTDModule.MODULE_5
        assert doc.page_count == 423

    def test_seed_validation_001_passed(self, svc: ECTDSubmissionService):
        val = svc.get_validation("VAL-001")
        assert val is not None
        assert val.passed is True
        assert val.errors == 0

    def test_seed_validation_005_failed(self, svc: ECTDSubmissionService):
        val = svc.get_validation("VAL-005")
        assert val is not None
        assert val.passed is False
        assert val.errors == 2
        assert len(val.error_details) == 2

    def test_seed_ha_response_002_open(self, svc: ECTDSubmissionService):
        har = svc.get_ha_response("HAR-002")
        assert har is not None
        assert har.response_type == HAResponseType.INFORMATION_REQUEST
        assert har.status == "open"
        assert len(har.questions) == 3

    def test_seed_plan_001(self, svc: ECTDSubmissionService):
        plan = svc.get_plan("PLAN-001")
        assert plan is not None
        assert plan.trial_id == EYLEA_TRIAL
        assert len(plan.target_regions) == 5
        assert plan.status == "active"

    def test_seed_plan_010_completed(self, svc: ECTDSubmissionService):
        plan = svc.get_plan("PLAN-010")
        assert plan is not None
        assert plan.status == "completed"

    def test_seed_eylea_sequences(self, svc: ECTDSubmissionService):
        seqs = svc.list_sequences(trial_id=EYLEA_TRIAL)
        assert len(seqs) >= 3

    def test_seed_dupixent_sequences(self, svc: ECTDSubmissionService):
        seqs = svc.list_sequences(trial_id=DUPIXENT_TRIAL)
        assert len(seqs) >= 3

    def test_seed_libtayo_sequences(self, svc: ECTDSubmissionService):
        seqs = svc.list_sequences(trial_id=LIBTAYO_TRIAL)
        assert len(seqs) >= 3


# ===========================================================================
# ECTDSequence CRUD - API
# ===========================================================================


class TestSequenceAPI:

    @pytest.mark.anyio
    async def test_list_sequences(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sequences")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_sequences_filter_trial_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sequences", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert all(s["trial_id"] == EYLEA_TRIAL for s in data["items"])

    @pytest.mark.anyio
    async def test_list_sequences_filter_region(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sequences", params={"region": "us_fda"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(s["region"] == "us_fda" for s in data["items"])

    @pytest.mark.anyio
    async def test_list_sequences_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sequences", params={"status": "submitted"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(s["status"] == "submitted" for s in data["items"])

    @pytest.mark.anyio
    async def test_list_sequences_filter_submission_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sequences", params={"submission_type": "initial"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(s["submission_type"] == "initial" for s in data["items"])

    @pytest.mark.anyio
    async def test_list_sequences_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sequences",
            params={"trial_id": EYLEA_TRIAL, "region": "us_fda"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for s in data["items"]:
            assert s["trial_id"] == EYLEA_TRIAL
            assert s["region"] == "us_fda"

    @pytest.mark.anyio
    async def test_list_sequences_no_results(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sequences",
            params={"trial_id": "nonexistent"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_sequence(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sequences/SEQ-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SEQ-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_sequence_404(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sequences/SEQ-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_sequence(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "sequence_number": "0099",
            "submission_type": "initial",
            "region": "us_fda",
            "title": "Test Sequence",
            "publisher": "Test Publisher",
            "target_date": datetime.now(timezone.utc).isoformat(),
        }
        resp = await client.post(f"{API_PREFIX}/sequences", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["title"] == "Test Sequence"
        assert data["status"] == "planning"

    @pytest.mark.anyio
    async def test_create_sequence_with_description(self, client: AsyncClient):
        payload = {
            "trial_id": DUPIXENT_TRIAL,
            "sequence_number": "0050",
            "submission_type": "supplement",
            "region": "eu_ema",
            "title": "Test with description",
            "description": "A detailed description",
            "publisher": "Pub Co",
            "target_date": datetime.now(timezone.utc).isoformat(),
        }
        resp = await client.post(f"{API_PREFIX}/sequences", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["description"] == "A detailed description"

    @pytest.mark.anyio
    async def test_create_sequence_appears_in_list(self, client: AsyncClient):
        payload = {
            "trial_id": LIBTAYO_TRIAL,
            "sequence_number": "0099",
            "submission_type": "annual_report",
            "region": "japan_pmda",
            "title": "New Test Seq",
            "publisher": "Test Pub",
            "target_date": datetime.now(timezone.utc).isoformat(),
        }
        resp = await client.post(f"{API_PREFIX}/sequences", json=payload)
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/sequences")
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] == 13

    @pytest.mark.anyio
    async def test_update_sequence_status(self, client: AsyncClient):
        payload = {"status": "authoring"}
        resp = await client.put(f"{API_PREFIX}/sequences/SEQ-009", json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "authoring"

    @pytest.mark.anyio
    async def test_update_sequence_tracking_number(self, client: AsyncClient):
        payload = {"tracking_number": "NDA-999-999"}
        resp = await client.put(f"{API_PREFIX}/sequences/SEQ-009", json=payload)
        assert resp.status_code == 200
        assert resp.json()["tracking_number"] == "NDA-999-999"

    @pytest.mark.anyio
    async def test_update_sequence_404(self, client: AsyncClient):
        payload = {"status": "submitted"}
        resp = await client.put(f"{API_PREFIX}/sequences/SEQ-NOPE", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_sequence_multiple_fields(self, client: AsyncClient):
        payload = {
            "status": "submitted",
            "tracking_number": "NDA-TEST-123",
            "total_documents": 50,
            "total_size_mb": 1234.5,
        }
        resp = await client.put(f"{API_PREFIX}/sequences/SEQ-009", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "submitted"
        assert data["tracking_number"] == "NDA-TEST-123"
        assert data["total_documents"] == 50
        assert data["total_size_mb"] == 1234.5

    @pytest.mark.anyio
    async def test_delete_sequence(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sequences/SEQ-012")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_sequence_gone(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/sequences/SEQ-012")
        resp = await client.get(f"{API_PREFIX}/sequences/SEQ-012")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sequence_reduces_count(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/sequences/SEQ-012")
        resp = await client.get(f"{API_PREFIX}/sequences")
        assert resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_delete_sequence_404(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sequences/SEQ-NOPE")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_sequence_missing_field(self, client: AsyncClient):
        payload = {"trial_id": EYLEA_TRIAL}
        resp = await client.post(f"{API_PREFIX}/sequences", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_sequence_invalid_region(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "sequence_number": "0001",
            "submission_type": "initial",
            "region": "invalid_region",
            "title": "Bad Region",
            "publisher": "P",
            "target_date": datetime.now(timezone.utc).isoformat(),
        }
        resp = await client.post(f"{API_PREFIX}/sequences", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_sequence_invalid_submission_type(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "sequence_number": "0001",
            "submission_type": "invalid_type",
            "region": "us_fda",
            "title": "Bad Type",
            "publisher": "P",
            "target_date": datetime.now(timezone.utc).isoformat(),
        }
        resp = await client.post(f"{API_PREFIX}/sequences", json=payload)
        assert resp.status_code == 422


# ===========================================================================
# ECTDDocument CRUD - API
# ===========================================================================


class TestDocumentAPI:

    @pytest.mark.anyio
    async def test_list_documents(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_documents_filter_sequence(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents", params={"sequence_id": "SEQ-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(d["sequence_id"] == "SEQ-001" for d in data["items"])
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_documents_filter_module(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents", params={"module": "module_5_clinical"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(d["module"] == "module_5_clinical" for d in data["items"])

    @pytest.mark.anyio
    async def test_list_documents_filter_approved_true(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents", params={"approved": True})
        assert resp.status_code == 200
        data = resp.json()
        assert all(d["approved"] is True for d in data["items"])

    @pytest.mark.anyio
    async def test_list_documents_filter_approved_false(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents", params={"approved": False})
        assert resp.status_code == 200
        data = resp.json()
        assert all(d["approved"] is False for d in data["items"])

    @pytest.mark.anyio
    async def test_list_documents_no_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents", params={"sequence_id": "SEQ-NOPE"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_document(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/DOC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DOC-001"
        assert data["module"] == "module_1_regional"

    @pytest.mark.anyio
    async def test_get_document_404(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents/DOC-NOPE")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_document(self, client: AsyncClient):
        payload = {
            "sequence_id": "SEQ-001",
            "module": "module_2_summaries",
            "section_number": "2.3",
            "title": "Quality Overall Summary",
            "file_name": "m2-3-qos.pdf",
            "author": "Test Author",
        }
        resp = await client.post(f"{API_PREFIX}/documents", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["sequence_id"] == "SEQ-001"
        assert data["module"] == "module_2_summaries"
        assert data["approved"] is False

    @pytest.mark.anyio
    async def test_create_document_with_lifecycle(self, client: AsyncClient):
        payload = {
            "sequence_id": "SEQ-002",
            "module": "module_3_quality",
            "section_number": "3.2.P.5",
            "title": "Control of Drug Product",
            "file_name": "m3-2-p-5-control.pdf",
            "lifecycle_operation": "replace",
            "author": "Author X",
        }
        resp = await client.post(f"{API_PREFIX}/documents", json=payload)
        assert resp.status_code == 201
        assert resp.json()["lifecycle_operation"] == "replace"

    @pytest.mark.anyio
    async def test_create_document_appears_in_list(self, client: AsyncClient):
        payload = {
            "sequence_id": "SEQ-009",
            "module": "module_1_regional",
            "section_number": "1.0",
            "title": "Cover Letter",
            "file_name": "m1-0-cover.pdf",
            "author": "A",
        }
        resp = await client.post(f"{API_PREFIX}/documents", json=payload)
        assert resp.status_code == 201

        list_resp = await client.get(f"{API_PREFIX}/documents")
        assert list_resp.json()["total"] == 16

    @pytest.mark.anyio
    async def test_update_document_reviewer(self, client: AsyncClient):
        payload = {"reviewer": "Dr. New Reviewer"}
        resp = await client.put(f"{API_PREFIX}/documents/DOC-006", json=payload)
        assert resp.status_code == 200
        assert resp.json()["reviewer"] == "Dr. New Reviewer"

    @pytest.mark.anyio
    async def test_update_document_approve(self, client: AsyncClient):
        payload = {"approved": True}
        resp = await client.put(f"{API_PREFIX}/documents/DOC-006", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["approved"] is True
        assert data["approved_date"] is not None

    @pytest.mark.anyio
    async def test_update_document_size_and_pages(self, client: AsyncClient):
        payload = {"page_count": 55, "size_kb": 2500.0}
        resp = await client.put(f"{API_PREFIX}/documents/DOC-006", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["page_count"] == 55
        assert data["size_kb"] == 2500.0

    @pytest.mark.anyio
    async def test_update_document_checksum(self, client: AsyncClient):
        payload = {"checksum": "sha256:newchecksum123"}
        resp = await client.put(f"{API_PREFIX}/documents/DOC-006", json=payload)
        assert resp.status_code == 200
        assert resp.json()["checksum"] == "sha256:newchecksum123"

    @pytest.mark.anyio
    async def test_update_document_404(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/documents/DOC-NOPE", json={"reviewer": "X"})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_document(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/documents/DOC-015")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_document_gone(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/documents/DOC-015")
        resp = await client.get(f"{API_PREFIX}/documents/DOC-015")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_document_404(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/documents/DOC-NOPE")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_document_missing_field(self, client: AsyncClient):
        payload = {"sequence_id": "SEQ-001"}
        resp = await client.post(f"{API_PREFIX}/documents", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_document_invalid_module(self, client: AsyncClient):
        payload = {
            "sequence_id": "SEQ-001",
            "module": "invalid_module",
            "section_number": "1.0",
            "title": "Bad Module",
            "file_name": "bad.pdf",
            "author": "A",
        }
        resp = await client.post(f"{API_PREFIX}/documents", json=payload)
        assert resp.status_code == 422


# ===========================================================================
# ECTDValidation CRUD - API
# ===========================================================================


class TestValidationAPI:

    @pytest.mark.anyio
    async def test_list_validations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_validations_filter_sequence(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"sequence_id": "SEQ-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(v["sequence_id"] == "SEQ-001" for v in data["items"])
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_validations_filter_passed_true(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"passed": True})
        assert resp.status_code == 200
        data = resp.json()
        assert all(v["passed"] is True for v in data["items"])

    @pytest.mark.anyio
    async def test_list_validations_filter_passed_false(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"passed": False})
        assert resp.status_code == 200
        data = resp.json()
        assert all(v["passed"] is False for v in data["items"])
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_validations_no_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations", params={"sequence_id": "SEQ-NOPE"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_validation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations/VAL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "VAL-001"
        assert data["passed"] is True

    @pytest.mark.anyio
    async def test_get_validation_with_errors(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations/VAL-005")
        assert resp.status_code == 200
        data = resp.json()
        assert data["passed"] is False
        assert data["errors"] == 2
        assert len(data["error_details"]) == 2

    @pytest.mark.anyio
    async def test_get_validation_404(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/validations/VAL-NOPE")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_validation(self, client: AsyncClient):
        payload = {
            "sequence_id": "SEQ-009",
            "validation_tool": "Test Validator",
            "passed": True,
            "errors": 0,
            "warnings": 1,
            "error_details": [],
            "validator": "Test User",
        }
        resp = await client.post(f"{API_PREFIX}/validations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["sequence_id"] == "SEQ-009"
        assert data["passed"] is True
        assert data["validation_tool"] == "Test Validator"

    @pytest.mark.anyio
    async def test_create_validation_with_errors(self, client: AsyncClient):
        payload = {
            "sequence_id": "SEQ-002",
            "validation_tool": "Custom QC",
            "passed": False,
            "errors": 5,
            "warnings": 10,
            "error_details": ["Error 1", "Error 2", "Error 3", "Error 4", "Error 5"],
            "validator": "QC Bot",
        }
        resp = await client.post(f"{API_PREFIX}/validations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["passed"] is False
        assert data["errors"] == 5
        assert len(data["error_details"]) == 5

    @pytest.mark.anyio
    async def test_create_validation_appears_in_list(self, client: AsyncClient):
        payload = {
            "sequence_id": "SEQ-009",
            "validation_tool": "Auto",
            "passed": True,
            "validator": "Bot",
        }
        await client.post(f"{API_PREFIX}/validations", json=payload)
        resp = await client.get(f"{API_PREFIX}/validations")
        assert resp.json()["total"] == 13

    @pytest.mark.anyio
    async def test_delete_validation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/validations/VAL-012")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_validation_gone(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/validations/VAL-012")
        resp = await client.get(f"{API_PREFIX}/validations/VAL-012")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_validation_404(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/validations/VAL-NOPE")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_validation_missing_field(self, client: AsyncClient):
        payload = {"sequence_id": "SEQ-001"}
        resp = await client.post(f"{API_PREFIX}/validations", json=payload)
        assert resp.status_code == 422


# ===========================================================================
# HAResponse CRUD - API
# ===========================================================================


class TestHAResponseAPI:

    @pytest.mark.anyio
    async def test_list_ha_responses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ha-responses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_ha_responses_filter_sequence(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ha-responses", params={"sequence_id": "SEQ-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["sequence_id"] == "SEQ-001" for r in data["items"])
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_ha_responses_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/ha-responses",
            params={"response_type": "acknowledgment"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["response_type"] == "acknowledgment" for r in data["items"])

    @pytest.mark.anyio
    async def test_list_ha_responses_filter_status_open(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ha-responses", params={"status": "open"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["status"] == "open" for r in data["items"])

    @pytest.mark.anyio
    async def test_list_ha_responses_filter_status_closed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ha-responses", params={"status": "closed"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["status"] == "closed" for r in data["items"])

    @pytest.mark.anyio
    async def test_list_ha_responses_no_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ha-responses", params={"sequence_id": "SEQ-NOPE"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_ha_response(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ha-responses/HAR-002")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "HAR-002"
        assert data["response_type"] == "information_request"

    @pytest.mark.anyio
    async def test_get_ha_response_questions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ha-responses/HAR-002")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["questions"]) == 3
        assert len(data["action_items"]) == 3

    @pytest.mark.anyio
    async def test_get_ha_response_404(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ha-responses/HAR-NOPE")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_ha_response(self, client: AsyncClient):
        payload = {
            "sequence_id": "SEQ-008",
            "response_type": "acknowledgment",
            "summary": "Test acknowledgment",
        }
        resp = await client.post(f"{API_PREFIX}/ha-responses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["sequence_id"] == "SEQ-008"
        assert data["response_type"] == "acknowledgment"
        assert data["status"] == "open"

    @pytest.mark.anyio
    async def test_create_ha_response_with_questions(self, client: AsyncClient):
        payload = {
            "sequence_id": "SEQ-004",
            "response_type": "information_request",
            "summary": "IR from FDA",
            "questions": ["Q1?", "Q2?"],
            "action_items": ["A1", "A2"],
            "assigned_to": "Dr. Test",
            "due_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        }
        resp = await client.post(f"{API_PREFIX}/ha-responses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["questions"]) == 2
        assert data["assigned_to"] == "Dr. Test"
        assert data["due_date"] is not None

    @pytest.mark.anyio
    async def test_create_ha_response_appears_in_list(self, client: AsyncClient):
        payload = {
            "sequence_id": "SEQ-009",
            "response_type": "acknowledgment",
            "summary": "Test ack",
        }
        await client.post(f"{API_PREFIX}/ha-responses", json=payload)
        resp = await client.get(f"{API_PREFIX}/ha-responses")
        assert resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_update_ha_response_status(self, client: AsyncClient):
        payload = {"status": "closed"}
        resp = await client.put(f"{API_PREFIX}/ha-responses/HAR-002", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"
        assert data["resolved_date"] is not None

    @pytest.mark.anyio
    async def test_update_ha_response_assigned_to(self, client: AsyncClient):
        payload = {"assigned_to": "Dr. New Assignee"}
        resp = await client.put(f"{API_PREFIX}/ha-responses/HAR-002", json=payload)
        assert resp.status_code == 200
        assert resp.json()["assigned_to"] == "Dr. New Assignee"

    @pytest.mark.anyio
    async def test_update_ha_response_action_items(self, client: AsyncClient):
        payload = {"action_items": ["New Action 1", "New Action 2"]}
        resp = await client.put(f"{API_PREFIX}/ha-responses/HAR-002", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["action_items"] == ["New Action 1", "New Action 2"]

    @pytest.mark.anyio
    async def test_update_ha_response_404(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/ha-responses/HAR-NOPE", json={"status": "closed"})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_ha_response(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/ha-responses/HAR-009")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_ha_response_gone(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/ha-responses/HAR-009")
        resp = await client.get(f"{API_PREFIX}/ha-responses/HAR-009")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_ha_response_404(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/ha-responses/HAR-NOPE")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_ha_response_missing_field(self, client: AsyncClient):
        payload = {"sequence_id": "SEQ-001"}
        resp = await client.post(f"{API_PREFIX}/ha-responses", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_ha_response_invalid_type(self, client: AsyncClient):
        payload = {
            "sequence_id": "SEQ-001",
            "response_type": "invalid_type",
            "summary": "bad",
        }
        resp = await client.post(f"{API_PREFIX}/ha-responses", json=payload)
        assert resp.status_code == 422


# ===========================================================================
# SubmissionPlan CRUD - API
# ===========================================================================


class TestPlanAPI:

    @pytest.mark.anyio
    async def test_list_plans(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_plans_filter_trial_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert all(p["trial_id"] == EYLEA_TRIAL for p in data["items"])

    @pytest.mark.anyio
    async def test_list_plans_filter_status_active(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans", params={"status": "active"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(p["status"] == "active" for p in data["items"])
        assert data["total"] == 9

    @pytest.mark.anyio
    async def test_list_plans_filter_status_completed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    @pytest.mark.anyio
    async def test_list_plans_filter_combined(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/plans",
            params={"trial_id": DUPIXENT_TRIAL, "status": "active"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for p in data["items"]:
            assert p["trial_id"] == DUPIXENT_TRIAL
            assert p["status"] == "active"

    @pytest.mark.anyio
    async def test_list_plans_no_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_plan(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans/PLAN-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PLAN-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_plan_target_regions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans/PLAN-001")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["target_regions"]) == 5

    @pytest.mark.anyio
    async def test_get_plan_404(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/plans/PLAN-NOPE")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_plan(self, client: AsyncClient):
        payload = {
            "trial_id": LIBTAYO_TRIAL,
            "plan_name": "Test Submission Plan",
            "target_regions": ["us_fda", "eu_ema"],
            "primary_contact": "Test Contact",
            "regulatory_lead": "Test Lead",
        }
        resp = await client.post(f"{API_PREFIX}/plans", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["plan_name"] == "Test Submission Plan"
        assert len(data["target_regions"]) == 2
        assert data["status"] == "active"

    @pytest.mark.anyio
    async def test_create_plan_empty_regions(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "plan_name": "Plan No Regions",
            "target_regions": [],
            "primary_contact": "TC",
            "regulatory_lead": "RL",
        }
        resp = await client.post(f"{API_PREFIX}/plans", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["target_regions"] == []

    @pytest.mark.anyio
    async def test_create_plan_appears_in_list(self, client: AsyncClient):
        payload = {
            "trial_id": DUPIXENT_TRIAL,
            "plan_name": "New Plan",
            "primary_contact": "TC",
            "regulatory_lead": "RL",
        }
        await client.post(f"{API_PREFIX}/plans", json=payload)
        resp = await client.get(f"{API_PREFIX}/plans")
        assert resp.json()["total"] == 11

    @pytest.mark.anyio
    async def test_update_plan_status(self, client: AsyncClient):
        payload = {"status": "on_hold"}
        resp = await client.put(f"{API_PREFIX}/plans/PLAN-008", json=payload)
        assert resp.status_code == 200
        assert resp.json()["status"] == "on_hold"

    @pytest.mark.anyio
    async def test_update_plan_sequences(self, client: AsyncClient):
        payload = {"planned_sequences": 8, "completed_sequences": 3}
        resp = await client.put(f"{API_PREFIX}/plans/PLAN-001", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["planned_sequences"] == 8
        assert data["completed_sequences"] == 3

    @pytest.mark.anyio
    async def test_update_plan_notes(self, client: AsyncClient):
        payload = {"notes": "Updated strategy notes"}
        resp = await client.put(f"{API_PREFIX}/plans/PLAN-005", json=payload)
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Updated strategy notes"

    @pytest.mark.anyio
    async def test_update_plan_404(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/plans/PLAN-NOPE", json={"status": "done"})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_plan(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/plans/PLAN-010")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_plan_gone(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/plans/PLAN-010")
        resp = await client.get(f"{API_PREFIX}/plans/PLAN-010")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_plan_reduces_count(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/plans/PLAN-010")
        resp = await client.get(f"{API_PREFIX}/plans")
        assert resp.json()["total"] == 9

    @pytest.mark.anyio
    async def test_delete_plan_404(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/plans/PLAN-NOPE")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_plan_missing_field(self, client: AsyncClient):
        payload = {"trial_id": EYLEA_TRIAL}
        resp = await client.post(f"{API_PREFIX}/plans", json=payload)
        assert resp.status_code == 422


# ===========================================================================
# Metrics
# ===========================================================================


class TestMetrics:

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sequences"] == 12
        assert data["total_documents"] == 15
        assert data["total_validations"] == 12
        assert data["total_ha_responses"] == 10
        assert data["total_plans"] == 10

    @pytest.mark.anyio
    async def test_metrics_sequences_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        sbs = data["sequences_by_status"]
        assert isinstance(sbs, dict)
        assert sum(sbs.values()) == 12

    @pytest.mark.anyio
    async def test_metrics_sequences_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        sbt = data["sequences_by_type"]
        assert isinstance(sbt, dict)
        assert sum(sbt.values()) == 12

    @pytest.mark.anyio
    async def test_metrics_sequences_by_region(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        sbr = data["sequences_by_region"]
        assert isinstance(sbr, dict)
        assert sum(sbr.values()) == 12

    @pytest.mark.anyio
    async def test_metrics_documents_by_module(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        dbm = data["documents_by_module"]
        assert isinstance(dbm, dict)
        assert sum(dbm.values()) == 15

    @pytest.mark.anyio
    async def test_metrics_approved_documents(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["approved_documents"] >= 0
        assert data["approved_documents"] <= data["total_documents"]

    @pytest.mark.anyio
    async def test_metrics_validation_pass_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0 <= data["validation_pass_rate_pct"] <= 100

    @pytest.mark.anyio
    async def test_metrics_responses_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        rbt = data["responses_by_type"]
        assert isinstance(rbt, dict)
        assert sum(rbt.values()) == 10

    @pytest.mark.anyio
    async def test_metrics_open_responses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["open_responses"] >= 0

    @pytest.mark.anyio
    async def test_metrics_active_plans(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["active_plans"] == 9

    @pytest.mark.anyio
    async def test_metrics_after_create_sequence(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "sequence_number": "0099",
            "submission_type": "initial",
            "region": "us_fda",
            "title": "New",
            "publisher": "P",
            "target_date": datetime.now(timezone.utc).isoformat(),
        }
        await client.post(f"{API_PREFIX}/sequences", json=payload)
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.json()["total_sequences"] == 13

    @pytest.mark.anyio
    async def test_metrics_after_delete_document(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/documents/DOC-001")
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.json()["total_documents"] == 14

    @pytest.mark.anyio
    async def test_metrics_after_create_validation(self, client: AsyncClient):
        payload = {
            "sequence_id": "SEQ-001",
            "validation_tool": "New Tool",
            "passed": True,
            "validator": "V",
        }
        await client.post(f"{API_PREFIX}/validations", json=payload)
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.json()["total_validations"] == 13

    @pytest.mark.anyio
    async def test_metrics_after_create_plan(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "plan_name": "Extra Plan",
            "primary_contact": "C",
            "regulatory_lead": "L",
        }
        await client.post(f"{API_PREFIX}/plans", json=payload)
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.json()["total_plans"] == 11
        assert resp.json()["active_plans"] == 10


# ===========================================================================
# Service-level tests
# ===========================================================================


class TestServiceDirect:
    """Direct service-level tests (no HTTP)."""

    def test_create_and_get_sequence(self, svc: ECTDSubmissionService):
        payload = ECTDSequenceCreate(
            trial_id=EYLEA_TRIAL,
            sequence_number="9999",
            submission_type=SubmissionType.INITIAL,
            region=RegulatoryRegion.US_FDA,
            title="Direct Test",
            publisher="Pub",
            target_date=datetime.now(timezone.utc),
        )
        created = svc.create_sequence(payload)
        assert created.id.startswith("SEQ-")
        fetched = svc.get_sequence(created.id)
        assert fetched is not None
        assert fetched.title == "Direct Test"

    def test_list_sequences_all(self, svc: ECTDSubmissionService):
        seqs = svc.list_sequences()
        assert len(seqs) == 12

    def test_list_sequences_filter_region(self, svc: ECTDSubmissionService):
        seqs = svc.list_sequences(region=RegulatoryRegion.EU_EMA)
        assert all(s.region == RegulatoryRegion.EU_EMA for s in seqs)

    def test_list_sequences_filter_status(self, svc: ECTDSubmissionService):
        seqs = svc.list_sequences(status=SequenceStatus.SUBMITTED)
        assert all(s.status == SequenceStatus.SUBMITTED for s in seqs)

    def test_update_sequence_returns_none_for_missing(self, svc: ECTDSubmissionService):
        result = svc.update_sequence("NONEXISTENT", ECTDSequenceUpdate())
        assert result is None

    def test_delete_sequence_returns_false_for_missing(self, svc: ECTDSubmissionService):
        assert svc.delete_sequence("NONEXISTENT") is False

    def test_create_and_get_document(self, svc: ECTDSubmissionService):
        payload = ECTDDocumentCreate(
            sequence_id="SEQ-001",
            module=CTDModule.MODULE_2,
            section_number="2.4",
            title="Direct Doc Test",
            file_name="test.pdf",
            author="Author",
        )
        created = svc.create_document(payload)
        assert created.id.startswith("DOC-")
        fetched = svc.get_document(created.id)
        assert fetched is not None
        assert fetched.title == "Direct Doc Test"

    def test_update_document_sets_approved_date(self, svc: ECTDSubmissionService):
        payload = ECTDDocumentUpdate(approved=True)
        updated = svc.update_document("DOC-006", payload)
        assert updated is not None
        assert updated.approved is True
        assert updated.approved_date is not None

    def test_update_document_returns_none_for_missing(self, svc: ECTDSubmissionService):
        result = svc.update_document("NONEXISTENT", ECTDDocumentUpdate())
        assert result is None

    def test_delete_document_returns_false_for_missing(self, svc: ECTDSubmissionService):
        assert svc.delete_document("NONEXISTENT") is False

    def test_create_validation(self, svc: ECTDSubmissionService):
        payload = ECTDValidationCreate(
            sequence_id="SEQ-001",
            validation_tool="Direct Tool",
            passed=True,
            validator="Direct V",
        )
        created = svc.create_validation(payload)
        assert created.id.startswith("VAL-")
        assert created.validation_date is not None

    def test_list_validations_filter_passed(self, svc: ECTDSubmissionService):
        failed = svc.list_validations(passed=False)
        assert all(v.passed is False for v in failed)

    def test_delete_validation_returns_false_for_missing(self, svc: ECTDSubmissionService):
        assert svc.delete_validation("NONEXISTENT") is False

    def test_create_ha_response(self, svc: ECTDSubmissionService):
        payload = HAResponseCreate(
            sequence_id="SEQ-001",
            response_type=HAResponseType.ACKNOWLEDGMENT,
            summary="Test HA",
        )
        created = svc.create_ha_response(payload)
        assert created.id.startswith("HAR-")
        assert created.status == "open"

    def test_update_ha_response_close_sets_resolved(self, svc: ECTDSubmissionService):
        payload = HAResponseUpdate(status="closed")
        updated = svc.update_ha_response("HAR-002", payload)
        assert updated is not None
        assert updated.status == "closed"
        assert updated.resolved_date is not None

    def test_update_ha_response_returns_none_for_missing(self, svc: ECTDSubmissionService):
        result = svc.update_ha_response("NONEXISTENT", HAResponseUpdate())
        assert result is None

    def test_delete_ha_response_returns_false_for_missing(self, svc: ECTDSubmissionService):
        assert svc.delete_ha_response("NONEXISTENT") is False

    def test_create_plan(self, svc: ECTDSubmissionService):
        payload = SubmissionPlanCreate(
            trial_id=LIBTAYO_TRIAL,
            plan_name="Direct Plan Test",
            primary_contact="PC",
            regulatory_lead="RL",
        )
        created = svc.create_plan(payload)
        assert created.id.startswith("PLAN-")
        assert created.status == "active"

    def test_update_plan_returns_none_for_missing(self, svc: ECTDSubmissionService):
        result = svc.update_plan("NONEXISTENT", SubmissionPlanUpdate())
        assert result is None

    def test_delete_plan_returns_false_for_missing(self, svc: ECTDSubmissionService):
        assert svc.delete_plan("NONEXISTENT") is False

    def test_list_plans_filter_trial(self, svc: ECTDSubmissionService):
        plans = svc.list_plans(trial_id=EYLEA_TRIAL)
        assert all(p.trial_id == EYLEA_TRIAL for p in plans)

    def test_list_plans_filter_status(self, svc: ECTDSubmissionService):
        active = svc.list_plans(status="active")
        assert all(p.status == "active" for p in active)

    def test_list_ha_responses_filter_type(self, svc: ECTDSubmissionService):
        acks = svc.list_ha_responses(response_type=HAResponseType.ACKNOWLEDGMENT)
        assert all(r.response_type == HAResponseType.ACKNOWLEDGMENT for r in acks)

    def test_get_metrics_structure(self, svc: ECTDSubmissionService):
        m = svc.get_metrics()
        assert m.total_sequences == 12
        assert m.total_documents == 15
        assert m.total_validations == 12
        assert m.total_ha_responses == 10
        assert m.total_plans == 10
        assert m.active_plans == 9
        assert 0 <= m.validation_pass_rate_pct <= 100

    def test_get_metrics_validation_pass_rate(self, svc: ECTDSubmissionService):
        m = svc.get_metrics()
        # 9 passed out of 12 = 75.0%
        assert m.validation_pass_rate_pct == 75.0

    def test_get_metrics_open_responses(self, svc: ECTDSubmissionService):
        m = svc.get_metrics()
        assert m.open_responses == 4

    def test_get_metrics_approved_documents(self, svc: ECTDSubmissionService):
        m = svc.get_metrics()
        assert m.approved_documents == 12


# ===========================================================================
# Edge Cases and Boundary Conditions
# ===========================================================================


class TestEdgeCases:

    @pytest.mark.anyio
    async def test_get_all_seed_sequences_individually(self, client: AsyncClient):
        """Fetch each seeded sequence individually to verify all are accessible."""
        for i in range(1, 13):
            seq_id = f"SEQ-{i:03d}"
            resp = await client.get(f"{API_PREFIX}/sequences/{seq_id}")
            assert resp.status_code == 200, f"Failed to get {seq_id}"

    @pytest.mark.anyio
    async def test_get_all_seed_documents_individually(self, client: AsyncClient):
        for i in range(1, 16):
            doc_id = f"DOC-{i:03d}"
            resp = await client.get(f"{API_PREFIX}/documents/{doc_id}")
            assert resp.status_code == 200, f"Failed to get {doc_id}"

    @pytest.mark.anyio
    async def test_get_all_seed_validations_individually(self, client: AsyncClient):
        for i in range(1, 13):
            val_id = f"VAL-{i:03d}"
            resp = await client.get(f"{API_PREFIX}/validations/{val_id}")
            assert resp.status_code == 200, f"Failed to get {val_id}"

    @pytest.mark.anyio
    async def test_get_all_seed_ha_responses_individually(self, client: AsyncClient):
        for i in range(1, 11):
            har_id = f"HAR-{i:03d}"
            resp = await client.get(f"{API_PREFIX}/ha-responses/{har_id}")
            assert resp.status_code == 200, f"Failed to get {har_id}"

    @pytest.mark.anyio
    async def test_get_all_seed_plans_individually(self, client: AsyncClient):
        for i in range(1, 11):
            plan_id = f"PLAN-{i:03d}"
            resp = await client.get(f"{API_PREFIX}/plans/{plan_id}")
            assert resp.status_code == 200, f"Failed to get {plan_id}"

    @pytest.mark.anyio
    async def test_create_then_update_then_delete_sequence(self, client: AsyncClient):
        """Full lifecycle test for sequence."""
        payload = {
            "trial_id": EYLEA_TRIAL,
            "sequence_number": "0100",
            "submission_type": "initial",
            "region": "us_fda",
            "title": "Lifecycle Test",
            "publisher": "LP",
            "target_date": datetime.now(timezone.utc).isoformat(),
        }
        resp = await client.post(f"{API_PREFIX}/sequences", json=payload)
        assert resp.status_code == 201
        seq_id = resp.json()["id"]

        resp = await client.put(f"{API_PREFIX}/sequences/{seq_id}", json={"status": "authoring"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "authoring"

        resp = await client.delete(f"{API_PREFIX}/sequences/{seq_id}")
        assert resp.status_code == 204

        resp = await client.get(f"{API_PREFIX}/sequences/{seq_id}")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_then_update_then_delete_document(self, client: AsyncClient):
        payload = {
            "sequence_id": "SEQ-001",
            "module": "module_1_regional",
            "section_number": "1.99",
            "title": "Lifecycle Doc",
            "file_name": "lifecycle.pdf",
            "author": "Auth",
        }
        resp = await client.post(f"{API_PREFIX}/documents", json=payload)
        assert resp.status_code == 201
        doc_id = resp.json()["id"]

        resp = await client.put(f"{API_PREFIX}/documents/{doc_id}", json={"approved": True})
        assert resp.status_code == 200

        resp = await client.delete(f"{API_PREFIX}/documents/{doc_id}")
        assert resp.status_code == 204

        resp = await client.get(f"{API_PREFIX}/documents/{doc_id}")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_then_delete_validation(self, client: AsyncClient):
        payload = {
            "sequence_id": "SEQ-001",
            "validation_tool": "LifecycleTool",
            "passed": True,
            "validator": "V",
        }
        resp = await client.post(f"{API_PREFIX}/validations", json=payload)
        assert resp.status_code == 201
        val_id = resp.json()["id"]

        resp = await client.delete(f"{API_PREFIX}/validations/{val_id}")
        assert resp.status_code == 204

        resp = await client.get(f"{API_PREFIX}/validations/{val_id}")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_then_update_then_delete_ha_response(self, client: AsyncClient):
        payload = {
            "sequence_id": "SEQ-001",
            "response_type": "acknowledgment",
            "summary": "Lifecycle HAR",
        }
        resp = await client.post(f"{API_PREFIX}/ha-responses", json=payload)
        assert resp.status_code == 201
        har_id = resp.json()["id"]

        resp = await client.put(f"{API_PREFIX}/ha-responses/{har_id}", json={"status": "closed"})
        assert resp.status_code == 200

        resp = await client.delete(f"{API_PREFIX}/ha-responses/{har_id}")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_create_then_update_then_delete_plan(self, client: AsyncClient):
        payload = {
            "trial_id": LIBTAYO_TRIAL,
            "plan_name": "Lifecycle Plan",
            "primary_contact": "C",
            "regulatory_lead": "L",
        }
        resp = await client.post(f"{API_PREFIX}/plans", json=payload)
        assert resp.status_code == 201
        plan_id = resp.json()["id"]

        resp = await client.put(f"{API_PREFIX}/plans/{plan_id}", json={"status": "completed"})
        assert resp.status_code == 200

        resp = await client.delete(f"{API_PREFIX}/plans/{plan_id}")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_multiple_sequences_same_trial(self, client: AsyncClient):
        for i in range(5):
            payload = {
                "trial_id": EYLEA_TRIAL,
                "sequence_number": f"01{i:02d}",
                "submission_type": "supplement",
                "region": "us_fda",
                "title": f"Batch Seq {i}",
                "publisher": "P",
                "target_date": datetime.now(timezone.utc).isoformat(),
            }
            resp = await client.post(f"{API_PREFIX}/sequences", json=payload)
            assert resp.status_code == 201

        resp = await client.get(f"{API_PREFIX}/sequences", params={"trial_id": EYLEA_TRIAL})
        data = resp.json()
        # Original EYLEA sequences + 5 new
        assert data["total"] >= 5

    @pytest.mark.anyio
    async def test_empty_body_update_sequence(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/sequences/SEQ-001", json={})
        assert resp.status_code == 200
        # Should return unchanged data
        assert resp.json()["id"] == "SEQ-001"

    @pytest.mark.anyio
    async def test_empty_body_update_document(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/documents/DOC-001", json={})
        assert resp.status_code == 200
        assert resp.json()["id"] == "DOC-001"

    @pytest.mark.anyio
    async def test_empty_body_update_ha_response(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/ha-responses/HAR-002", json={})
        assert resp.status_code == 200
        assert resp.json()["id"] == "HAR-002"

    @pytest.mark.anyio
    async def test_empty_body_update_plan(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/plans/PLAN-001", json={})
        assert resp.status_code == 200
        assert resp.json()["id"] == "PLAN-001"

    @pytest.mark.anyio
    async def test_sequence_all_regions(self, client: AsyncClient):
        """Verify sequences exist for multiple distinct regions."""
        resp = await client.get(f"{API_PREFIX}/sequences")
        data = resp.json()
        regions = {s["region"] for s in data["items"]}
        assert len(regions) >= 4  # At least US, EU, Japan, UK in seed data

    @pytest.mark.anyio
    async def test_sequence_all_statuses_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sequences")
        data = resp.json()
        statuses = {s["status"] for s in data["items"]}
        assert len(statuses) >= 5  # planning, authoring, qc_review, publishing, submitted, etc.

    @pytest.mark.anyio
    async def test_documents_all_modules_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/documents")
        data = resp.json()
        modules = {d["module"] for d in data["items"]}
        assert len(modules) == 5  # All 5 CTD modules

    @pytest.mark.anyio
    async def test_validation_pass_rate_changes_after_delete_failed(self, client: AsyncClient):
        """Deleting a failed validation should change the pass rate."""
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        rate1 = resp1.json()["validation_pass_rate_pct"]

        # Delete a failed validation
        await client.delete(f"{API_PREFIX}/validations/VAL-005")
        resp2 = await client.get(f"{API_PREFIX}/metrics")
        rate2 = resp2.json()["validation_pass_rate_pct"]

        assert rate2 > rate1

    @pytest.mark.anyio
    async def test_double_delete_sequence(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sequences/SEQ-012")
        assert resp.status_code == 204
        resp = await client.delete(f"{API_PREFIX}/sequences/SEQ-012")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_document(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/documents/DOC-015")
        assert resp.status_code == 204
        resp = await client.delete(f"{API_PREFIX}/documents/DOC-015")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_validation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/validations/VAL-012")
        assert resp.status_code == 204
        resp = await client.delete(f"{API_PREFIX}/validations/VAL-012")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_ha_response(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/ha-responses/HAR-009")
        assert resp.status_code == 204
        resp = await client.delete(f"{API_PREFIX}/ha-responses/HAR-009")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_double_delete_plan(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/plans/PLAN-010")
        assert resp.status_code == 204
        resp = await client.delete(f"{API_PREFIX}/plans/PLAN-010")
        assert resp.status_code == 404


# ===========================================================================
# Reset / Singleton tests
# ===========================================================================


class TestSingleton:

    def test_get_returns_same_instance(self):
        svc1 = get_ectd_submission_service()
        svc2 = get_ectd_submission_service()
        assert svc1 is svc2

    def test_reset_returns_new_instance(self):
        svc1 = get_ectd_submission_service()
        svc2 = reset_ectd_submission_service()
        assert svc1 is not svc2

    def test_reset_repopulates_data(self):
        svc = get_ectd_submission_service()
        svc.delete_sequence("SEQ-001")
        assert svc.get_sequence("SEQ-001") is None

        svc2 = reset_ectd_submission_service()
        assert svc2.get_sequence("SEQ-001") is not None
