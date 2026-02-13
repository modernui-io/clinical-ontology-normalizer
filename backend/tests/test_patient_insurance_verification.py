"""Tests for Patient Insurance Verification (PIV-VER).

Covers:
- Seed data verification (12 records per entity across 3 trials)
- Eligibility Check CRUD (list, get, create, update, delete, not-found, trial filter)
- Pre-Authorization Request CRUD (list, get, create, update, delete, not-found, trial filter)
- Coverage Determination CRUD (list, get, create, update, delete, not-found, trial filter)
- Reimbursement Tracking CRUD (list, get, create, update, delete, not-found, trial filter)
- Metrics computation (overall + per-trial filtering)
- Service singleton pattern
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.patient_insurance_verification_service import (
    PatientInsuranceVerificationService,
    get_patient_insurance_verification_service,
    reset_patient_insurance_verification_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/patient-insurance-verification"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_patient_insurance_verification_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> PatientInsuranceVerificationService:
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


def _make_eligibility_check_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-TEST-001",
        "site_id": "SITE-101",
        "coverage_type": "private",
        "insurance_provider": "Test Insurance Co",
        "verification_date": now.isoformat(),
        "verified_by": "Test Verifier",
    }
    defaults.update(overrides)
    return defaults


def _make_pre_auth_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "subject_id": "SUBJ-TEST-002",
        "site_id": "SITE-103",
        "procedure_code": "J0000",
        "procedure_description": "Test procedure",
        "requesting_provider": "Dr. Test Provider",
        "insurance_provider": "Test Insurance Co",
        "request_date": now.isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_coverage_determination_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": LIBTAYO_TRIAL,
        "subject_id": "SUBJ-TEST-003",
        "site_id": "SITE-105",
        "coverage_type": "medicare",
        "procedure_category": "Test procedure category",
        "determination_date": now.isoformat(),
        "determined_by": "Test Coordinator",
    }
    defaults.update(overrides)
    return defaults


def _make_reimbursement_tracking_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "subject_id": "SUBJ-TEST-004",
        "site_id": "SITE-101",
        "procedure_code": "J0178",
        "billed_amount": 2000.0,
        "submission_date": now.isoformat(),
        "processed_by": "Test Analyst",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_eligibility_checks_count(self, svc: PatientInsuranceVerificationService):
        items = svc.list_eligibility_checks()
        assert len(items) == 12

    def test_seed_pre_authorization_requests_count(self, svc: PatientInsuranceVerificationService):
        items = svc.list_pre_authorization_requests()
        assert len(items) == 12

    def test_seed_coverage_determinations_count(self, svc: PatientInsuranceVerificationService):
        items = svc.list_coverage_determinations()
        assert len(items) == 12

    def test_seed_reimbursement_trackings_count(self, svc: PatientInsuranceVerificationService):
        items = svc.list_reimbursement_trackings()
        assert len(items) == 12

    def test_seed_eligibility_checks_per_trial(self, svc: PatientInsuranceVerificationService):
        for trial_id in [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]:
            items = svc.list_eligibility_checks(trial_id=trial_id)
            assert len(items) == 4

    def test_seed_pre_auths_per_trial(self, svc: PatientInsuranceVerificationService):
        for trial_id in [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]:
            items = svc.list_pre_authorization_requests(trial_id=trial_id)
            assert len(items) == 4

    def test_seed_coverage_determinations_per_trial(self, svc: PatientInsuranceVerificationService):
        for trial_id in [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]:
            items = svc.list_coverage_determinations(trial_id=trial_id)
            assert len(items) == 4

    def test_seed_reimbursements_per_trial(self, svc: PatientInsuranceVerificationService):
        for trial_id in [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]:
            items = svc.list_reimbursement_trackings(trial_id=trial_id)
            assert len(items) == 4

    def test_seed_eligibility_check_ids_prefixed(self, svc: PatientInsuranceVerificationService):
        items = svc.list_eligibility_checks()
        for item in items:
            assert item.id.startswith("ELC-")

    def test_seed_pre_auth_ids_prefixed(self, svc: PatientInsuranceVerificationService):
        items = svc.list_pre_authorization_requests()
        for item in items:
            assert item.id.startswith("PAR-")

    def test_seed_coverage_determination_ids_prefixed(
        self, svc: PatientInsuranceVerificationService
    ):
        items = svc.list_coverage_determinations()
        for item in items:
            assert item.id.startswith("CVD-")

    def test_seed_reimbursement_ids_prefixed(self, svc: PatientInsuranceVerificationService):
        items = svc.list_reimbursement_trackings()
        for item in items:
            assert item.id.startswith("RMB-")


# =====================================================================
# ELIGIBILITY CHECK CRUD
# =====================================================================


class TestEligibilityCheckCrud:
    """Test eligibility check CRUD operations."""

    @pytest.mark.anyio
    async def test_list_eligibility_checks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/eligibility-checks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_eligibility_checks_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/eligibility-checks", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_eligibility_check(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/eligibility-checks/ELC-00000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ELC-00000001"
        assert data["eligibility_status"] == "eligible"
        assert data["insurance_provider"] == "Aetna"

    @pytest.mark.anyio
    async def test_get_eligibility_check_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/eligibility-checks/ELC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_eligibility_check(self, client: AsyncClient):
        payload = _make_eligibility_check_create()
        resp = await client.post(f"{API_PREFIX}/eligibility-checks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("ELC-")
        assert data["subject_id"] == "SUBJ-TEST-001"
        assert data["insurance_provider"] == "Test Insurance Co"

    @pytest.mark.anyio
    async def test_update_eligibility_check(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/eligibility-checks/ELC-00000001",
            json={"eligibility_status": "conditional", "notes": "Updated notes"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["eligibility_status"] == "conditional"
        assert data["notes"] == "Updated notes"

    @pytest.mark.anyio
    async def test_update_eligibility_check_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/eligibility-checks/ELC-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_eligibility_check(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/eligibility-checks/ELC-00000001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/eligibility-checks/ELC-00000001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_eligibility_check_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/eligibility-checks/ELC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# PRE-AUTHORIZATION REQUEST CRUD
# =====================================================================


class TestPreAuthorizationRequestCrud:
    """Test pre-authorization request CRUD operations."""

    @pytest.mark.anyio
    async def test_list_pre_authorization_requests(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pre-authorization-requests")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_pre_authorization_requests_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/pre-authorization-requests", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_get_pre_authorization_request(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pre-authorization-requests/PAR-00000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PAR-00000001"
        assert data["pre_auth_status"] == "approved"
        assert data["procedure_code"] == "J0178"

    @pytest.mark.anyio
    async def test_get_pre_authorization_request_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pre-authorization-requests/PAR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_pre_authorization_request(self, client: AsyncClient):
        payload = _make_pre_auth_create()
        resp = await client.post(f"{API_PREFIX}/pre-authorization-requests", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("PAR-")
        assert data["subject_id"] == "SUBJ-TEST-002"
        assert data["pre_auth_status"] == "requested"

    @pytest.mark.anyio
    async def test_update_pre_authorization_request(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/pre-authorization-requests/PAR-00000003",
            json={
                "pre_auth_status": "approved",
                "authorization_number": "AUTH-TEST-999",
                "approved_units": 10,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["pre_auth_status"] == "approved"
        assert data["authorization_number"] == "AUTH-TEST-999"
        assert data["approved_units"] == 10

    @pytest.mark.anyio
    async def test_update_pre_authorization_request_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/pre-authorization-requests/PAR-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_pre_authorization_request(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/pre-authorization-requests/PAR-00000001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/pre-authorization-requests/PAR-00000001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_pre_authorization_request_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/pre-authorization-requests/PAR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# COVERAGE DETERMINATION CRUD
# =====================================================================


class TestCoverageDeterminationCrud:
    """Test coverage determination CRUD operations."""

    @pytest.mark.anyio
    async def test_list_coverage_determinations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/coverage-determinations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_coverage_determinations_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/coverage-determinations", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_coverage_determination(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/coverage-determinations/CVD-00000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CVD-00000001"
        assert data["is_covered"] is True
        assert data["coverage_type"] == "private"

    @pytest.mark.anyio
    async def test_get_coverage_determination_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/coverage-determinations/CVD-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_coverage_determination(self, client: AsyncClient):
        payload = _make_coverage_determination_create()
        resp = await client.post(f"{API_PREFIX}/coverage-determinations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("CVD-")
        assert data["subject_id"] == "SUBJ-TEST-003"
        assert data["coverage_type"] == "medicare"

    @pytest.mark.anyio
    async def test_update_coverage_determination(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/coverage-determinations/CVD-00000003",
            json={
                "is_covered": True,
                "sponsor_responsibility": False,
                "patient_responsibility_pct": 15.0,
                "notes": "Coverage confirmed after verification",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_covered"] is True
        assert data["sponsor_responsibility"] is False
        assert data["patient_responsibility_pct"] == 15.0

    @pytest.mark.anyio
    async def test_update_coverage_determination_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/coverage-determinations/CVD-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_coverage_determination(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/coverage-determinations/CVD-00000001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/coverage-determinations/CVD-00000001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_coverage_determination_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/coverage-determinations/CVD-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# REIMBURSEMENT TRACKING CRUD
# =====================================================================


class TestReimbursementTrackingCrud:
    """Test reimbursement tracking CRUD operations."""

    @pytest.mark.anyio
    async def test_list_reimbursement_trackings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reimbursement-trackings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_reimbursement_trackings_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/reimbursement-trackings", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_get_reimbursement_tracking(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reimbursement-trackings/RMB-00000001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RMB-00000001"
        assert data["reimbursement_status"] == "approved"
        assert data["billed_amount"] == 1850.0

    @pytest.mark.anyio
    async def test_get_reimbursement_tracking_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/reimbursement-trackings/RMB-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_reimbursement_tracking(self, client: AsyncClient):
        payload = _make_reimbursement_tracking_create()
        resp = await client.post(f"{API_PREFIX}/reimbursement-trackings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("RMB-")
        assert data["subject_id"] == "SUBJ-TEST-004"
        assert data["reimbursement_status"] == "submitted"
        assert data["billed_amount"] == 2000.0

    @pytest.mark.anyio
    async def test_update_reimbursement_tracking(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reimbursement-trackings/RMB-00000003",
            json={
                "reimbursement_status": "approved",
                "approved_amount": 1480.0,
                "paid_amount": 1480.0,
                "notes": "Claim approved and paid",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reimbursement_status"] == "approved"
        assert data["approved_amount"] == 1480.0
        assert data["paid_amount"] == 1480.0

    @pytest.mark.anyio
    async def test_update_reimbursement_tracking_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/reimbursement-trackings/RMB-NONEXISTENT",
            json={"notes": "test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_reimbursement_tracking(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reimbursement-trackings/RMB-00000001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/reimbursement-trackings/RMB-00000001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_reimbursement_tracking_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/reimbursement-trackings/RMB-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test aggregated insurance verification metrics."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_eligibility_checks"] == 12
        assert data["total_pre_authorizations"] == 12
        assert data["total_coverage_determinations"] == 12
        assert data["total_reimbursements"] == 12
        assert data["total_billed_amount"] > 0
        assert data["total_paid_amount"] > 0
        assert data["pre_auth_approval_rate"] > 0
        assert data["coverage_rate"] > 0
        assert len(data["checks_by_status"]) > 0
        assert len(data["checks_by_coverage_type"]) > 0
        assert len(data["pre_auths_by_status"]) > 0
        assert len(data["reimbursements_by_status"]) > 0

    @pytest.mark.anyio
    async def test_get_metrics_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_eligibility_checks"] == 4
        assert data["total_pre_authorizations"] == 4
        assert data["total_coverage_determinations"] == 4
        assert data["total_reimbursements"] == 4

    def test_metrics_checks_by_status_totals(self, svc: PatientInsuranceVerificationService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.checks_by_status.values())
        assert total_by_status == metrics.total_eligibility_checks

    def test_metrics_checks_by_coverage_type_totals(
        self, svc: PatientInsuranceVerificationService
    ):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.checks_by_coverage_type.values())
        assert total_by_type == metrics.total_eligibility_checks

    def test_metrics_pre_auths_by_status_totals(self, svc: PatientInsuranceVerificationService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.pre_auths_by_status.values())
        assert total_by_status == metrics.total_pre_authorizations

    def test_metrics_reimbursements_by_status_totals(
        self, svc: PatientInsuranceVerificationService
    ):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.reimbursements_by_status.values())
        assert total_by_status == metrics.total_reimbursements

    def test_metrics_billed_exceeds_paid(self, svc: PatientInsuranceVerificationService):
        metrics = svc.get_metrics()
        assert metrics.total_billed_amount >= metrics.total_paid_amount

    def test_metrics_approval_rate_range(self, svc: PatientInsuranceVerificationService):
        metrics = svc.get_metrics()
        assert 0 <= metrics.pre_auth_approval_rate <= 100

    def test_metrics_coverage_rate_range(self, svc: PatientInsuranceVerificationService):
        metrics = svc.get_metrics()
        assert 0 <= metrics.coverage_rate <= 100


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_patient_insurance_verification_service()
        svc2 = get_patient_insurance_verification_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_patient_insurance_verification_service()
        svc2 = reset_patient_insurance_verification_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_patient_insurance_verification_service()
        svc.delete_eligibility_check("ELC-00000001")
        assert svc.get_eligibility_check("ELC-00000001") is None
        svc2 = reset_patient_insurance_verification_service()
        assert svc2.get_eligibility_check("ELC-00000001") is not None
