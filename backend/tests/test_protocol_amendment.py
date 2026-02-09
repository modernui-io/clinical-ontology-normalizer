"""Tests for Protocol Amendment Management (CLINICAL-16).

Covers:
- Seed data verification (amendments, IRB submissions, impact assessments, site implementations)
- Amendment CRUD (create, read, update, delete, list, filter by trial/status/type)
- Amendment lifecycle (draft -> sponsor_review -> irb_submitted -> irb_approved -> implemented)
- Amendment withdrawal
- IRB submission CRUD (create, read, update, list, filter by amendment/site/status)
- IRB approval workflow and site implementation status sync
- Impact assessment CRUD (create, read)
- Site implementation tracking
- Re-consent progress tracking
- Amendment tracker per trial
- Global amendment metrics
- Error handling (404s, 400s, invalid lifecycle transitions)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.protocol_amendment import (
    AmendmentCreate,
    AmendmentImpact,
    AmendmentImpactAssessment,
    AmendmentImplement,
    AmendmentStatus,
    AmendmentSubmit,
    AmendmentType,
    AmendmentUpdate,
    IRBStatus,
    IRBSubmissionCreate,
    IRBSubmissionUpdate,
    ImpactSeverity,
    ReConsentUpdate,
)
from app.services.protocol_amendment_service import (
    ProtocolAmendmentService,
    get_protocol_amendment_service,
    reset_protocol_amendment_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/protocol-amendments"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_protocol_amendment_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ProtocolAmendmentService:
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


def _make_amendment_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "amendment_number": 10,
        "version_from": "9.0",
        "version_to": "10.0",
        "amendment_type": "substantial",
        "title": "Test Amendment",
        "rationale": "Testing amendment creation",
        "description": "A test amendment for unit testing",
        "impacted_sections": ["Section 1.1"],
        "impacted_areas": ["enrollment_criteria"],
        "affected_sites": ["SITE-101", "SITE-102"],
    }
    defaults.update(overrides)
    return defaults


def _make_irb_submission_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "irb_name": "Test IRB",
        "site_id": "SITE-101",
        "submitted_date": now.isoformat(),
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_amendments_count(self, svc: ProtocolAmendmentService):
        amendments = svc.list_amendments()
        assert len(amendments) == 6

    def test_seed_amendments_across_trials(self, svc: ProtocolAmendmentService):
        eylea = svc.list_amendments(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_amendments(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_amendments(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) == 3  # AMD-001, AMD-002, AMD-006
        assert len(dupixent) == 1  # AMD-003
        assert len(libtayo) == 2  # AMD-004, AMD-005

    def test_seed_amendment_statuses(self, svc: ProtocolAmendmentService):
        amendments = svc.list_amendments()
        statuses = {a.status for a in amendments}
        assert AmendmentStatus.DRAFT in statuses
        assert AmendmentStatus.IMPLEMENTED in statuses
        assert AmendmentStatus.IRB_APPROVED in statuses

    def test_seed_amendment_types(self, svc: ProtocolAmendmentService):
        amendments = svc.list_amendments()
        types = {a.amendment_type for a in amendments}
        assert AmendmentType.SUBSTANTIAL in types
        assert AmendmentType.ADMINISTRATIVE in types
        assert AmendmentType.NON_SUBSTANTIAL in types

    def test_seed_irb_submissions_count(self, svc: ProtocolAmendmentService):
        subs = svc.list_irb_submissions()
        assert len(subs) == 20

    def test_seed_irb_statuses(self, svc: ProtocolAmendmentService):
        subs = svc.list_irb_submissions()
        statuses = {s.status for s in subs}
        assert IRBStatus.APPROVED in statuses
        assert IRBStatus.PENDING in statuses
        assert IRBStatus.MODIFICATIONS_REQUIRED in statuses

    def test_seed_impact_assessments(self, svc: ProtocolAmendmentService):
        for amd_id in ["AMD-001", "AMD-002", "AMD-003", "AMD-004", "AMD-005", "AMD-006"]:
            assessment = svc.get_impact_assessment(amd_id)
            assert assessment is not None

    def test_seed_site_implementations(self, svc: ProtocolAmendmentService):
        impls = svc.get_site_implementations("AMD-001")
        assert len(impls) == 4  # 4 sites

    def test_seed_implemented_amendment_sites(self, svc: ProtocolAmendmentService):
        impls = svc.get_site_implementations("AMD-001")
        for impl in impls:
            assert impl.implemented is True
            assert impl.irb_status == IRBStatus.APPROVED

    def test_seed_irb_embedded_in_amendment(self, svc: ProtocolAmendmentService):
        amd = svc.get_amendment("AMD-001")
        assert amd is not None
        assert len(amd.irb_submissions) > 0

    def test_seed_re_consent_progress(self, svc: ProtocolAmendmentService):
        impls = svc.get_site_implementations("AMD-001")
        has_re_consent = any(i.re_consent_required for i in impls)
        assert has_re_consent

    def test_seed_pending_sites_for_amd002(self, svc: ProtocolAmendmentService):
        impls = svc.get_site_implementations("AMD-002")
        pending = [i for i in impls if not i.implemented]
        assert len(pending) == 4  # None implemented yet


# =====================================================================
# AMENDMENT CRUD
# =====================================================================


class TestAmendmentCrud:
    """Test amendment create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_amendments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6
        assert len(data["items"]) == 6

    @pytest.mark.anyio
    async def test_list_amendments_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_amendments_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/", params={"status": "implemented"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "implemented"

    @pytest.mark.anyio
    async def test_list_amendments_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/", params={"amendment_type": "substantial"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["amendment_type"] == "substantial"

    @pytest.mark.anyio
    async def test_get_amendment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/AMD-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "AMD-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["amendment_type"] == "substantial"

    @pytest.mark.anyio
    async def test_get_amendment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/AMD-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_amendment(self, client: AsyncClient):
        payload = _make_amendment_create()
        resp = await client.post(f"{API_PREFIX}/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Amendment"
        assert data["status"] == "draft"
        assert data["id"].startswith("AMD-")

    @pytest.mark.anyio
    async def test_create_amendment_initializes_site_implementations(self, client: AsyncClient, svc: ProtocolAmendmentService):
        payload = _make_amendment_create(affected_sites=["SITE-101", "SITE-102", "SITE-103"])
        resp = await client.post(f"{API_PREFIX}/", json=payload)
        assert resp.status_code == 201
        amd_id = resp.json()["id"]
        impls = svc.get_site_implementations(amd_id)
        assert len(impls) == 3

    @pytest.mark.anyio
    async def test_update_amendment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/AMD-005",
            json={"title": "Updated Safety Monitoring", "rationale": "Updated rationale"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Safety Monitoring"
        assert data["rationale"] == "Updated rationale"

    @pytest.mark.anyio
    async def test_update_amendment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/AMD-NONEXISTENT",
            json={"title": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_amendment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/AMD-005")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/AMD-005")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_amendment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/AMD-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_amendment_cleans_up_related_data(self, svc: ProtocolAmendmentService, client: AsyncClient):
        # Verify related data exists before deletion
        assert svc.get_impact_assessment("AMD-005") is not None
        irb_subs_before = svc.list_irb_submissions(amendment_id="AMD-005")

        resp = await client.delete(f"{API_PREFIX}/AMD-005")
        assert resp.status_code == 204

        # Verify related data is cleaned up
        assert svc.get_impact_assessment("AMD-005") is None
        assert len(svc.get_site_implementations("AMD-005")) == 0


# =====================================================================
# AMENDMENT LIFECYCLE
# =====================================================================


class TestAmendmentLifecycle:
    """Test amendment lifecycle transitions."""

    @pytest.mark.anyio
    async def test_submit_draft_amendment(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.post(
            f"{API_PREFIX}/AMD-005/submit",
            json={"submitted_date": now.isoformat()},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "sponsor_review"
        assert data["submitted_date"] is not None

    @pytest.mark.anyio
    async def test_submit_non_draft_fails(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        # AMD-001 is implemented, not draft
        resp = await client.post(
            f"{API_PREFIX}/AMD-001/submit",
            json={"submitted_date": now.isoformat()},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_submit_not_found(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.post(
            f"{API_PREFIX}/AMD-NONEXISTENT/submit",
            json={"submitted_date": now.isoformat()},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_approve_irb_submitted_amendment(self, client: AsyncClient):
        # AMD-003 is irb_submitted
        resp = await client.post(f"{API_PREFIX}/AMD-003/approve")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "irb_approved"
        assert data["approved_date"] is not None

    @pytest.mark.anyio
    async def test_approve_non_irb_submitted_fails(self, client: AsyncClient):
        # AMD-005 is draft
        resp = await client.post(f"{API_PREFIX}/AMD-005/approve")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_approve_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/AMD-NONEXISTENT/approve")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_implement_approved_amendment(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        # AMD-002 is irb_approved
        resp = await client.post(
            f"{API_PREFIX}/AMD-002/implement",
            json={"implementation_date": now.isoformat()},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "implemented"
        assert data["implementation_date"] is not None

    @pytest.mark.anyio
    async def test_implement_non_approved_fails(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        # AMD-005 is draft
        resp = await client.post(
            f"{API_PREFIX}/AMD-005/implement",
            json={"implementation_date": now.isoformat()},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_implement_not_found(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.post(
            f"{API_PREFIX}/AMD-NONEXISTENT/implement",
            json={"implementation_date": now.isoformat()},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_withdraw_draft_amendment(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/AMD-005/withdraw")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "withdrawn"

    @pytest.mark.anyio
    async def test_withdraw_implemented_fails(self, client: AsyncClient):
        # AMD-001 is implemented
        resp = await client.post(f"{API_PREFIX}/AMD-001/withdraw")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_withdraw_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/AMD-NONEXISTENT/withdraw")
        assert resp.status_code == 404

    def test_full_lifecycle_via_service(self, svc: ProtocolAmendmentService):
        """Test complete lifecycle: draft -> sponsor_review -> irb_submitted -> irb_approved -> implemented."""
        now = datetime.now(timezone.utc)

        # Create amendment in draft
        amd = svc.create_amendment(AmendmentCreate(
            trial_id=EYLEA_TRIAL,
            amendment_number=99,
            version_from="99.0",
            version_to="100.0",
            amendment_type=AmendmentType.SUBSTANTIAL,
            title="Lifecycle Test",
            rationale="Testing lifecycle",
            description="Full lifecycle test",
            affected_sites=["SITE-101"],
        ))
        assert amd.status == AmendmentStatus.DRAFT

        # Submit
        amd = svc.submit_amendment(amd.id, AmendmentSubmit(submitted_date=now))
        assert amd is not None
        assert amd.status == AmendmentStatus.SPONSOR_REVIEW

        # Update to irb_submitted (manual status change for sponsor -> irb transition)
        amd = svc.update_amendment(amd.id, AmendmentUpdate(status=AmendmentStatus.IRB_SUBMITTED))
        assert amd is not None
        assert amd.status == AmendmentStatus.IRB_SUBMITTED

        # Approve
        amd = svc.approve_amendment(amd.id)
        assert amd is not None
        assert amd.status == AmendmentStatus.IRB_APPROVED

        # Implement
        amd = svc.implement_amendment(amd.id, AmendmentImplement(implementation_date=now))
        assert amd is not None
        assert amd.status == AmendmentStatus.IMPLEMENTED

    def test_withdraw_from_sponsor_review(self, svc: ProtocolAmendmentService):
        # AMD-004 is in sponsor_review
        result = svc.withdraw_amendment("AMD-004")
        assert result is not None
        assert result.status == AmendmentStatus.WITHDRAWN


# =====================================================================
# IRB SUBMISSIONS
# =====================================================================


class TestIRBSubmissions:
    """Test IRB submission operations."""

    @pytest.mark.anyio
    async def test_list_irb_submissions_for_amendment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/AMD-001/irb-submissions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["amendment_id"] == "AMD-001"

    @pytest.mark.anyio
    async def test_list_irb_submissions_filter_site(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/AMD-001/irb-submissions",
            params={"site_id": "SITE-101"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_irb_submissions_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/AMD-003/irb-submissions",
            params={"status": "pending"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "pending"

    @pytest.mark.anyio
    async def test_get_irb_submission(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/irb-submissions/IRB-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "IRB-001"
        assert data["amendment_id"] == "AMD-001"

    @pytest.mark.anyio
    async def test_get_irb_submission_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/irb-submissions/IRB-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_irb_submission(self, client: AsyncClient):
        payload = _make_irb_submission_create()
        resp = await client.post(f"{API_PREFIX}/AMD-002/irb-submissions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["amendment_id"] == "AMD-002"
        assert data["status"] == "pending"
        assert data["id"].startswith("IRB-")

    @pytest.mark.anyio
    async def test_create_irb_submission_invalid_amendment(self, client: AsyncClient):
        payload = _make_irb_submission_create()
        resp = await client.post(f"{API_PREFIX}/AMD-NONEXISTENT/irb-submissions", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_irb_submission_approve(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/irb-submissions/IRB-008",
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
    async def test_update_irb_submission_modifications_required(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/irb-submissions/IRB-009",
            json={
                "status": "modifications_required",
                "conditions": "Need additional safety data",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "modifications_required"
        assert data["conditions"] == "Need additional safety data"

    @pytest.mark.anyio
    async def test_update_irb_submission_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/irb-submissions/IRB-NONEXISTENT",
            json={"status": "approved"},
        )
        assert resp.status_code == 404

    def test_irb_submission_embedded_in_amendment_after_create(self, svc: ProtocolAmendmentService):
        now = datetime.now(timezone.utc)
        initial_count = len(svc.get_amendment("AMD-004").irb_submissions) if svc.get_amendment("AMD-004") else 0
        svc.create_irb_submission("AMD-004", IRBSubmissionCreate(
            irb_name="New IRB",
            site_id="SITE-105",
            submitted_date=now,
        ))
        amd = svc.get_amendment("AMD-004")
        assert amd is not None
        assert len(amd.irb_submissions) == initial_count + 1

    def test_all_irb_statuses_represented(self, svc: ProtocolAmendmentService):
        subs = svc.list_irb_submissions()
        statuses = {s.status for s in subs}
        assert IRBStatus.APPROVED in statuses
        assert IRBStatus.PENDING in statuses
        assert IRBStatus.MODIFICATIONS_REQUIRED in statuses
        assert IRBStatus.DEFERRED in statuses
        assert IRBStatus.NOT_APPLICABLE in statuses


# =====================================================================
# IMPACT ASSESSMENT
# =====================================================================


class TestImpactAssessment:
    """Test impact assessment operations."""

    @pytest.mark.anyio
    async def test_get_impact_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/AMD-001/impact-assessment")
        assert resp.status_code == 200
        data = resp.json()
        assert data["amendment_id"] == "AMD-001"
        assert data["operational_impact"] == "high"
        assert data["re_consent_required"] is True

    @pytest.mark.anyio
    async def test_get_impact_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/AMD-NONEXISTENT/impact-assessment")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_impact_assessment(self, client: AsyncClient):
        # Create a new amendment first
        amd_payload = _make_amendment_create()
        amd_resp = await client.post(f"{API_PREFIX}/", json=amd_payload)
        amd_id = amd_resp.json()["id"]

        payload = {
            "amendment_id": amd_id,
            "operational_impact": "medium",
            "enrollment_impact": "low",
            "safety_impact": "high",
            "cost_impact_estimate": 150000.0,
            "timeline_impact_weeks": 4,
            "re_consent_required": True,
            "training_required": True,
        }
        resp = await client.post(f"{API_PREFIX}/{amd_id}/impact-assessment", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["operational_impact"] == "medium"
        assert data["cost_impact_estimate"] == 150000.0

    @pytest.mark.anyio
    async def test_create_impact_assessment_invalid_amendment(self, client: AsyncClient):
        payload = {
            "amendment_id": "AMD-NONEXISTENT",
            "operational_impact": "low",
            "enrollment_impact": "low",
            "safety_impact": "low",
            "cost_impact_estimate": 1000.0,
            "timeline_impact_weeks": 0,
        }
        resp = await client.post(f"{API_PREFIX}/AMD-NONEXISTENT/impact-assessment", json=payload)
        assert resp.status_code == 400

    def test_impact_assessment_fields(self, svc: ProtocolAmendmentService):
        assessment = svc.get_impact_assessment("AMD-003")
        assert assessment is not None
        assert assessment.operational_impact == ImpactSeverity.HIGH
        assert assessment.safety_impact == ImpactSeverity.HIGH
        assert assessment.re_consent_required is True
        assert assessment.training_required is True
        assert assessment.cost_impact_estimate == 380000.0
        assert assessment.timeline_impact_weeks == 6

    def test_administrative_amendment_low_impact(self, svc: ProtocolAmendmentService):
        assessment = svc.get_impact_assessment("AMD-006")
        assert assessment is not None
        assert assessment.operational_impact == ImpactSeverity.LOW
        assert assessment.enrollment_impact == ImpactSeverity.LOW
        assert assessment.safety_impact == ImpactSeverity.LOW
        assert assessment.re_consent_required is False
        assert assessment.training_required is False
        assert assessment.cost_impact_estimate == 5000.0
        assert assessment.timeline_impact_weeks == 0


# =====================================================================
# SITE IMPLEMENTATION
# =====================================================================


class TestSiteImplementation:
    """Test site implementation tracking."""

    @pytest.mark.anyio
    async def test_get_site_implementations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/AMD-001/site-implementations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["implemented"] is True

    @pytest.mark.anyio
    async def test_get_site_implementation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/AMD-001/sites/SITE-101/implementation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["site_id"] == "SITE-101"
        assert data["implemented"] is True
        assert data["irb_status"] == "approved"

    @pytest.mark.anyio
    async def test_get_site_implementation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/AMD-001/sites/SITE-NONEXISTENT/implementation")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_site_implementation(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/AMD-002/sites/SITE-101/implementation",
            params={"implemented": True, "implementation_date": now.isoformat()},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["implemented"] is True

    @pytest.mark.anyio
    async def test_update_site_implementation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/AMD-NONEXISTENT/sites/SITE-101/implementation",
            params={"implemented": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_pending_implementations_for_amd002(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/AMD-002/site-implementations")
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["implemented"] is False

    def test_site_implementation_sorted_by_site_id(self, svc: ProtocolAmendmentService):
        impls = svc.get_site_implementations("AMD-001")
        site_ids = [i.site_id for i in impls]
        assert site_ids == sorted(site_ids)


# =====================================================================
# RE-CONSENT PROGRESS
# =====================================================================


class TestReConsentProgress:
    """Test re-consent progress tracking."""

    @pytest.mark.anyio
    async def test_update_re_consent_progress(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/AMD-001/sites/SITE-101/re-consent",
            json={"completed": 30, "total": 30},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["re_consent_completed"] == 30
        assert data["re_consent_total"] == 30

    @pytest.mark.anyio
    async def test_update_re_consent_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/AMD-NONEXISTENT/sites/SITE-101/re-consent",
            json={"completed": 5, "total": 10},
        )
        assert resp.status_code == 404

    def test_re_consent_partial_progress(self, svc: ProtocolAmendmentService):
        impl = svc.get_site_implementation("AMD-001", "SITE-101")
        assert impl is not None
        assert impl.re_consent_required is True
        assert impl.re_consent_completed < impl.re_consent_total or impl.re_consent_completed == impl.re_consent_total

    def test_re_consent_complete_at_site(self, svc: ProtocolAmendmentService):
        impl = svc.get_site_implementation("AMD-001", "SITE-102")
        assert impl is not None
        assert impl.re_consent_completed == impl.re_consent_total

    def test_update_re_consent_via_service(self, svc: ProtocolAmendmentService):
        result = svc.update_re_consent_progress(
            "AMD-001", "SITE-103",
            ReConsentUpdate(completed=18, total=18),
        )
        assert result is not None
        assert result.re_consent_completed == 18
        assert result.re_consent_total == 18


# =====================================================================
# AMENDMENT TRACKER
# =====================================================================


class TestAmendmentTracker:
    """Test amendment tracker per trial."""

    @pytest.mark.anyio
    async def test_get_tracker_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tracker/{EYLEA_TRIAL}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["total_amendments"] == 3

    @pytest.mark.anyio
    async def test_get_tracker_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tracker/{LIBTAYO_TRIAL}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_amendments"] == 2

    @pytest.mark.anyio
    async def test_get_tracker_empty_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/tracker/nonexistent-trial")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_amendments"] == 0

    def test_tracker_amendments_by_status(self, svc: ProtocolAmendmentService):
        tracker = svc.get_amendment_tracker(EYLEA_TRIAL)
        total_by_status = sum(tracker.amendments_by_status.values())
        assert total_by_status == tracker.total_amendments

    def test_tracker_amendments_by_type(self, svc: ProtocolAmendmentService):
        tracker = svc.get_amendment_tracker(EYLEA_TRIAL)
        total_by_type = sum(tracker.amendments_by_type.values())
        assert total_by_type == tracker.total_amendments

    def test_tracker_avg_approval_days(self, svc: ProtocolAmendmentService):
        tracker = svc.get_amendment_tracker(EYLEA_TRIAL)
        assert tracker.avg_approval_days > 0

    def test_tracker_re_consent_progress(self, svc: ProtocolAmendmentService):
        tracker = svc.get_amendment_tracker(EYLEA_TRIAL)
        progress = tracker.re_consent_progress
        assert "total_required" in progress
        assert "completed" in progress
        assert "pending" in progress
        assert progress["pending"] == progress["total_required"] - progress["completed"]

    def test_tracker_sites_pending_implementation(self, svc: ProtocolAmendmentService):
        tracker = svc.get_amendment_tracker(EYLEA_TRIAL)
        # AMD-002 has 4 pending sites
        assert tracker.sites_pending_implementation >= 4


# =====================================================================
# METRICS
# =====================================================================


class TestAmendmentMetrics:
    """Test amendment metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_amendments"] == 6
        assert data["total_irb_submissions"] == 20
        assert data["avg_approval_days"] > 0

    def test_metrics_by_status(self, svc: ProtocolAmendmentService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.amendments_by_status.values())
        assert total_by_status == metrics.total_amendments

    def test_metrics_by_type(self, svc: ProtocolAmendmentService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.amendments_by_type.values())
        assert total_by_type == metrics.total_amendments

    def test_metrics_irb_by_status(self, svc: ProtocolAmendmentService):
        metrics = svc.get_metrics()
        total_irb = sum(metrics.irb_submissions_by_status.values())
        assert total_irb == metrics.total_irb_submissions

    def test_metrics_re_consent_count(self, svc: ProtocolAmendmentService):
        metrics = svc.get_metrics()
        assert metrics.amendments_requiring_re_consent > 0

    def test_metrics_pending_sites(self, svc: ProtocolAmendmentService):
        metrics = svc.get_metrics()
        assert metrics.total_sites_pending_implementation > 0


# =====================================================================
# AMENDMENT DETAILS
# =====================================================================


class TestAmendmentDetails:
    """Test amendment content and field validation."""

    @pytest.mark.anyio
    async def test_amendment_has_impacted_areas(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/AMD-001")
        data = resp.json()
        assert len(data["impacted_areas"]) > 0
        assert "enrollment_criteria" in data["impacted_areas"]

    @pytest.mark.anyio
    async def test_amendment_has_impacted_sections(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/AMD-001")
        data = resp.json()
        assert len(data["impacted_sections"]) > 0

    @pytest.mark.anyio
    async def test_amendment_has_affected_sites(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/AMD-001")
        data = resp.json()
        assert len(data["affected_sites"]) > 0

    @pytest.mark.anyio
    async def test_amendment_has_rationale(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/AMD-003")
        data = resp.json()
        assert len(data["rationale"]) > 20

    @pytest.mark.anyio
    async def test_implemented_amendment_has_dates(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/AMD-001")
        data = resp.json()
        assert data["submitted_date"] is not None
        assert data["approved_date"] is not None
        assert data["implementation_date"] is not None

    @pytest.mark.anyio
    async def test_draft_amendment_has_no_dates(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/AMD-005")
        data = resp.json()
        assert data["submitted_date"] is None
        assert data["approved_date"] is None
        assert data["implementation_date"] is None

    @pytest.mark.anyio
    async def test_administrative_amendment_no_impact_areas(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/AMD-006")
        data = resp.json()
        assert data["amendment_type"] == "administrative"
        assert len(data["impacted_areas"]) == 0


# =====================================================================
# IRB SUBMISSION DETAILS
# =====================================================================


class TestIRBSubmissionDetails:
    """Test IRB submission content and statuses."""

    @pytest.mark.anyio
    async def test_approved_irb_has_approval_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/irb-submissions/IRB-001")
        data = resp.json()
        assert data["status"] == "approved"
        assert data["approval_date"] is not None

    @pytest.mark.anyio
    async def test_pending_irb_has_no_approval_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/irb-submissions/IRB-008")
        data = resp.json()
        assert data["status"] == "pending"
        assert data["approval_date"] is None

    @pytest.mark.anyio
    async def test_modifications_required_has_conditions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/irb-submissions/IRB-010")
        data = resp.json()
        assert data["status"] == "modifications_required"
        assert data["conditions"] is not None
        assert len(data["conditions"]) > 10

    @pytest.mark.anyio
    async def test_deferred_irb(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/irb-submissions/IRB-016")
        data = resp.json()
        assert data["status"] == "deferred"
        assert data["conditions"] is not None

    @pytest.mark.anyio
    async def test_not_applicable_irb(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/irb-submissions/IRB-019")
        data = resp.json()
        assert data["status"] == "not_applicable"


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_protocol_amendment_service()
        svc2 = get_protocol_amendment_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_protocol_amendment_service()
        svc2 = reset_protocol_amendment_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_protocol_amendment_service()
        svc.delete_amendment("AMD-001")
        assert svc.get_amendment("AMD-001") is None
        svc2 = reset_protocol_amendment_service()
        assert svc2.get_amendment("AMD-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_amendments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_amendments_empty_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_create_amendment_with_all_fields(self, client: AsyncClient):
        payload = _make_amendment_create(
            impacted_areas=["enrollment_criteria", "endpoints", "dosing"],
            impacted_sections=["Section 1", "Section 2", "Section 3"],
            affected_sites=["SITE-101", "SITE-102", "SITE-103", "SITE-104"],
        )
        resp = await client.post(f"{API_PREFIX}/", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_create_amendment_minimal_fields(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "amendment_number": 50,
            "version_from": "1.0",
            "version_to": "2.0",
            "amendment_type": "administrative",
            "title": "Minimal Amendment",
            "rationale": "Test",
            "description": "Test",
        }
        resp = await client.post(f"{API_PREFIX}/", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_amendment_update_impacted_areas(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/AMD-005",
            json={"impacted_areas": ["safety_monitoring", "dosing", "informed_consent"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "safety_monitoring" in data["impacted_areas"]
        assert "dosing" in data["impacted_areas"]

    @pytest.mark.anyio
    async def test_amendment_sorted_by_created_at_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        data = resp.json()
        dates = [item["created_at"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_irb_submissions_sorted_by_submitted_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/AMD-001/irb-submissions")
        data = resp.json()
        dates = [item["submitted_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_site_implementations_empty_for_unknown_amendment(self, client: AsyncClient, svc: ProtocolAmendmentService):
        impls = svc.get_site_implementations("AMD-NONEXISTENT")
        assert len(impls) == 0


# =====================================================================
# ENUMERATION VALUES
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout."""

    @pytest.mark.anyio
    async def test_amendment_types_in_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        data = resp.json()
        types = {item["amendment_type"] for item in data["items"]}
        assert "substantial" in types
        assert "administrative" in types
        assert "non_substantial" in types

    @pytest.mark.anyio
    async def test_amendment_statuses_in_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "draft" in statuses
        assert "implemented" in statuses

    @pytest.mark.anyio
    async def test_impact_areas_valid_values(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/AMD-001")
        data = resp.json()
        valid_areas = {
            "enrollment_criteria", "endpoints", "dosing", "visit_schedule",
            "safety_monitoring", "sample_size", "statistical_plan", "informed_consent",
        }
        for area in data["impacted_areas"]:
            assert area in valid_areas

    @pytest.mark.anyio
    async def test_irb_statuses_in_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/AMD-001/irb-submissions")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "approved" in statuses

    @pytest.mark.anyio
    async def test_impact_severity_values(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/AMD-001/impact-assessment")
        data = resp.json()
        valid_severities = {"high", "medium", "low"}
        assert data["operational_impact"] in valid_severities
        assert data["enrollment_impact"] in valid_severities
        assert data["safety_impact"] in valid_severities


# =====================================================================
# CROSS-AMENDMENT ANALYSIS
# =====================================================================


class TestCrossAmendmentAnalysis:
    """Test cross-amendment and cross-trial analysis."""

    def test_amendments_across_multiple_trials(self, svc: ProtocolAmendmentService):
        all_amds = svc.list_amendments()
        trial_ids = {a.trial_id for a in all_amds}
        assert len(trial_ids) >= 3

    def test_irb_submissions_across_amendments(self, svc: ProtocolAmendmentService):
        all_subs = svc.list_irb_submissions()
        amendment_ids = {s.amendment_id for s in all_subs}
        assert len(amendment_ids) >= 4

    def test_re_consent_required_amendments(self, svc: ProtocolAmendmentService):
        all_assessments = [
            svc.get_impact_assessment(amd.id)
            for amd in svc.list_amendments()
        ]
        re_consent_count = sum(
            1 for a in all_assessments if a is not None and a.re_consent_required
        )
        assert re_consent_count >= 3  # AMD-001, AMD-003, AMD-005

    def test_training_required_amendments(self, svc: ProtocolAmendmentService):
        all_assessments = [
            svc.get_impact_assessment(amd.id)
            for amd in svc.list_amendments()
        ]
        training_count = sum(
            1 for a in all_assessments if a is not None and a.training_required
        )
        assert training_count >= 4

    def test_total_cost_impact(self, svc: ProtocolAmendmentService):
        all_assessments = [
            svc.get_impact_assessment(amd.id)
            for amd in svc.list_amendments()
        ]
        total_cost = sum(
            a.cost_impact_estimate for a in all_assessments if a is not None
        )
        assert total_cost > 0
