"""Tests for Clinical Trial Insurance module.

Covers:
- Seed data verification (policies, certificates, claims, requirements, renewals)
- Policy CRUD (create, read, update, delete, list, filter by trial/type/status)
- Certificate issuance, CRUD, and filtering
- Claim filing, lifecycle, CRUD, and filtering
- Coverage requirement CRUD and filtering
- Coverage compliance checking
- Renewal initiation, CRUD, and filtering
- Expiring policies detection
- Insurance metrics computation
- Error handling (404s, 400s, invalid operations)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.trial_insurance import (
    CertificateStatus,
    ClaimStatus,
    CoverageScope,
    PolicyStatus,
    PolicyType,
    RenewalStatus,
)
from app.services.trial_insurance_service import (
    TrialInsuranceService,
    get_trial_insurance_service,
    reset_trial_insurance_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/trial-insurance"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_trial_insurance_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> TrialInsuranceService:
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


def _make_policy_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "policy_number": "TEST-POL-001",
        "policy_type": "clinical_trial_liability",
        "insurer": "Test Insurance Co",
        "coverage_scope": "global",
        "countries_covered": ["US", "UK"],
        "coverage_amount": 10_000_000.0,
        "deductible": 50_000.0,
        "premium": 200_000.0,
        "premium_currency": "USD",
        "effective_date": now.isoformat(),
        "expiry_date": (now + timedelta(days=365)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_certificate_create(**overrides) -> dict:
    defaults = {
        "policy_id": "POL-001",
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-201",
        "coverage_amount": 50_000_000.0,
        "country": "JP",
    }
    defaults.update(overrides)
    return defaults


def _make_claim_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "policy_id": "POL-001",
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "patient_id": "PAT-99999",
        "incident_date": (now - timedelta(days=5)).isoformat(),
        "incident_description": "Test incident for unit testing purposes",
        "claim_amount": 100_000.0,
    }
    defaults.update(overrides)
    return defaults


def _make_requirement_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "country": "JP",
        "regulatory_authority": "PMDA",
        "required_policy_type": "clinical_trial_liability",
        "minimum_coverage_amount": 5_000_000.0,
        "per_patient_minimum": 200_000.0,
        "aggregate_minimum": 5_000_000.0,
        "proof_required": True,
        "deadline": (now + timedelta(days=60)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_renewal_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "policy_id": "POL-001",
        "renewal_date": (now + timedelta(days=30)).isoformat(),
        "new_premium": 920_000.0,
        "premium_change_pct": 5.14,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_policies_count(self, svc: TrialInsuranceService):
        policies = svc.list_policies()
        assert len(policies) == 4

    def test_seed_policies_types(self, svc: TrialInsuranceService):
        policies = svc.list_policies()
        types = {p.policy_type for p in policies}
        assert PolicyType.CLINICAL_TRIAL_LIABILITY in types
        assert PolicyType.PRODUCT_LIABILITY in types
        assert PolicyType.NO_FAULT_COMPENSATION in types
        assert PolicyType.PROFESSIONAL_INDEMNITY in types

    def test_seed_policies_statuses(self, svc: TrialInsuranceService):
        policies = svc.list_policies()
        statuses = {p.status for p in policies}
        assert PolicyStatus.ACTIVE in statuses
        assert PolicyStatus.EXPIRED in statuses
        assert PolicyStatus.PENDING_RENEWAL in statuses

    def test_seed_certificates_count(self, svc: TrialInsuranceService):
        certs = svc.list_certificates()
        assert len(certs) == 6

    def test_seed_claims_count(self, svc: TrialInsuranceService):
        claims = svc.list_claims()
        assert len(claims) == 3

    def test_seed_claims_statuses(self, svc: TrialInsuranceService):
        claims = svc.list_claims()
        statuses = {c.status for c in claims}
        assert ClaimStatus.SETTLED in statuses
        assert ClaimStatus.UNDER_INVESTIGATION in statuses
        assert ClaimStatus.FILED in statuses

    def test_seed_requirements_count(self, svc: TrialInsuranceService):
        reqs = svc.list_requirements()
        assert len(reqs) == 5

    def test_seed_requirements_met_unmet(self, svc: TrialInsuranceService):
        met = svc.list_requirements(met=True)
        unmet = svc.list_requirements(met=False)
        assert len(met) == 4
        assert len(unmet) == 1

    def test_seed_renewals_count(self, svc: TrialInsuranceService):
        renewals = svc.list_renewals()
        assert len(renewals) == 3

    def test_seed_renewals_statuses(self, svc: TrialInsuranceService):
        renewals = svc.list_renewals()
        statuses = {r.status for r in renewals}
        assert RenewalStatus.PENDING in statuses
        assert RenewalStatus.APPROVED in statuses
        assert RenewalStatus.REJECTED in statuses

    def test_seed_settled_claim_has_amount(self, svc: TrialInsuranceService):
        claim = svc.get_claim("CLM-001")
        assert claim is not None
        assert claim.status == ClaimStatus.SETTLED
        assert claim.settled_amount is not None
        assert claim.settled_amount > 0
        assert claim.resolution_date is not None


# =====================================================================
# POLICY CRUD
# =====================================================================


class TestPolicyCrud:
    """Test policy create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_policies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/policies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        assert len(data["items"]) == 4

    @pytest.mark.anyio
    async def test_list_policies_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/policies", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_policies_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/policies",
            params={"policy_type": "clinical_trial_liability"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["policy_type"] == "clinical_trial_liability"

    @pytest.mark.anyio
    async def test_list_policies_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/policies", params={"status": "active"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "active"

    @pytest.mark.anyio
    async def test_get_policy(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/policies/POL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "POL-001"
        assert data["policy_number"] == "CTL-2025-00147"
        assert data["insurer"] == "AIG Clinical Trials Division"

    @pytest.mark.anyio
    async def test_get_policy_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/policies/POL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_policy(self, client: AsyncClient):
        payload = _make_policy_create()
        resp = await client.post(f"{API_PREFIX}/policies", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["policy_number"] == "TEST-POL-001"
        assert data["status"] == "draft"
        assert data["id"].startswith("POL-")

    @pytest.mark.anyio
    async def test_create_policy_with_broker(self, client: AsyncClient):
        payload = _make_policy_create(
            broker="Test Broker Inc",
            special_conditions="Test special conditions",
        )
        resp = await client.post(f"{API_PREFIX}/policies", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["broker"] == "Test Broker Inc"
        assert data["special_conditions"] == "Test special conditions"

    @pytest.mark.anyio
    async def test_update_policy(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/policies/POL-001",
            json={"premium": 950_000.0, "status": "active"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["premium"] == 950_000.0

    @pytest.mark.anyio
    async def test_update_policy_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/policies/POL-NONEXISTENT",
            json={"premium": 100_000.0},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_policy(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/policies/POL-004")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/policies/POL-004")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_policy_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/policies/POL-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CERTIFICATE MANAGEMENT
# =====================================================================


class TestCertificateManagement:
    """Test certificate issuance and CRUD operations."""

    @pytest.mark.anyio
    async def test_list_certificates(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/certificates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    @pytest.mark.anyio
    async def test_list_certificates_filter_policy(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/certificates", params={"policy_id": "POL-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["policy_id"] == "POL-001"

    @pytest.mark.anyio
    async def test_list_certificates_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/certificates", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_certificates_filter_site(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/certificates", params={"site_id": "SITE-101"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_certificates_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/certificates", params={"status": "active"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "active"

    @pytest.mark.anyio
    async def test_list_certificates_filter_country(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/certificates", params={"country": "DE"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["country"] == "DE"

    @pytest.mark.anyio
    async def test_get_certificate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/certificates/CERT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CERT-001"
        assert data["country"] == "US"

    @pytest.mark.anyio
    async def test_get_certificate_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/certificates/CERT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_issue_certificate(self, client: AsyncClient):
        payload = _make_certificate_create()
        resp = await client.post(f"{API_PREFIX}/certificates", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["policy_id"] == "POL-001"
        assert data["site_id"] == "SITE-201"
        assert data["country"] == "JP"
        assert data["status"] == "active"
        assert data["id"].startswith("CERT-")

    @pytest.mark.anyio
    async def test_issue_certificate_with_regulatory(self, client: AsyncClient):
        payload = _make_certificate_create(
            regulatory_requirement="PMDA Clinical Trial Notification",
            authority_name="PMDA",
        )
        resp = await client.post(f"{API_PREFIX}/certificates", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["regulatory_requirement"] == "PMDA Clinical Trial Notification"
        assert data["authority_name"] == "PMDA"

    @pytest.mark.anyio
    async def test_issue_certificate_invalid_policy(self, client: AsyncClient):
        payload = _make_certificate_create(policy_id="POL-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/certificates", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_issue_certificate_expired_policy(self, client: AsyncClient):
        payload = _make_certificate_create(policy_id="POL-004")
        resp = await client.post(f"{API_PREFIX}/certificates", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_certificate(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/certificates/CERT-006",
            json={"status": "active", "filed_with_authority": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"
        assert data["filed_with_authority"] is True

    @pytest.mark.anyio
    async def test_update_certificate_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/certificates/CERT-NONEXISTENT",
            json={"status": "revoked"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_certificate(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/certificates/CERT-006")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/certificates/CERT-006")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_certificate_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/certificates/CERT-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CLAIMS MANAGEMENT
# =====================================================================


class TestClaimsManagement:
    """Test claim filing, lifecycle, and CRUD operations."""

    @pytest.mark.anyio
    async def test_list_claims(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/claims")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_claims_filter_policy(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/claims", params={"policy_id": "POL-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["policy_id"] == "POL-001"

    @pytest.mark.anyio
    async def test_list_claims_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/claims", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_claims_filter_site(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/claims", params={"site_id": "SITE-101"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_claims_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/claims", params={"status": "filed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "filed"

    @pytest.mark.anyio
    async def test_get_claim(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/claims/CLM-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CLM-001"
        assert data["status"] == "settled"

    @pytest.mark.anyio
    async def test_get_claim_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/claims/CLM-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_file_claim(self, client: AsyncClient):
        payload = _make_claim_create()
        resp = await client.post(f"{API_PREFIX}/claims", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "filed"
        assert data["claim_amount"] == 100_000.0
        assert data["id"].startswith("CLM-")
        assert data["settled_amount"] is None

    @pytest.mark.anyio
    async def test_file_claim_without_patient(self, client: AsyncClient):
        payload = _make_claim_create(patient_id=None)
        resp = await client.post(f"{API_PREFIX}/claims", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] is None

    @pytest.mark.anyio
    async def test_file_claim_invalid_policy(self, client: AsyncClient):
        payload = _make_claim_create(policy_id="POL-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/claims", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_file_claim_expired_policy(self, client: AsyncClient):
        payload = _make_claim_create(policy_id="POL-004")
        resp = await client.post(f"{API_PREFIX}/claims", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_claim_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/claims/CLM-003",
            json={"status": "under_investigation", "adjuster": "Test Adjuster"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "under_investigation"
        assert data["adjuster"] == "Test Adjuster"

    @pytest.mark.anyio
    async def test_update_claim_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/claims/CLM-NONEXISTENT",
            json={"status": "closed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_claim(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/claims/CLM-003")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/claims/CLM-003")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_claim_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/claims/CLM-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CLAIM LIFECYCLE
# =====================================================================


class TestClaimLifecycle:
    """Test claim status transitions and auto-resolution date."""

    def test_claim_lifecycle_filed_to_settled(self, svc: TrialInsuranceService):
        claim = svc.get_claim("CLM-003")
        assert claim is not None
        assert claim.status == ClaimStatus.FILED

        # Move to under_investigation
        from app.schemas.trial_insurance import InsuranceClaimUpdate
        updated = svc.update_claim(
            "CLM-003",
            InsuranceClaimUpdate(
                status=ClaimStatus.UNDER_INVESTIGATION,
                adjuster="Test Adjuster",
            ),
        )
        assert updated is not None
        assert updated.status == ClaimStatus.UNDER_INVESTIGATION

        # Approve
        updated = svc.update_claim(
            "CLM-003",
            InsuranceClaimUpdate(status=ClaimStatus.APPROVED),
        )
        assert updated is not None
        assert updated.status == ClaimStatus.APPROVED

        # Settle - should auto-set resolution_date
        updated = svc.update_claim(
            "CLM-003",
            InsuranceClaimUpdate(
                status=ClaimStatus.SETTLED,
                settled_amount=150_000.0,
            ),
        )
        assert updated is not None
        assert updated.status == ClaimStatus.SETTLED
        assert updated.settled_amount == 150_000.0
        assert updated.resolution_date is not None

    def test_claim_denied_auto_resolution_date(self, svc: TrialInsuranceService):
        from app.schemas.trial_insurance import InsuranceClaimUpdate
        updated = svc.update_claim(
            "CLM-003",
            InsuranceClaimUpdate(status=ClaimStatus.DENIED),
        )
        assert updated is not None
        assert updated.status == ClaimStatus.DENIED
        assert updated.resolution_date is not None

    def test_claim_closed_auto_resolution_date(self, svc: TrialInsuranceService):
        from app.schemas.trial_insurance import InsuranceClaimUpdate
        updated = svc.update_claim(
            "CLM-003",
            InsuranceClaimUpdate(status=ClaimStatus.CLOSED),
        )
        assert updated is not None
        assert updated.status == ClaimStatus.CLOSED
        assert updated.resolution_date is not None

    def test_settled_claim_keeps_resolution_date(self, svc: TrialInsuranceService):
        from app.schemas.trial_insurance import InsuranceClaimUpdate
        claim = svc.get_claim("CLM-001")
        assert claim is not None
        original_date = claim.resolution_date

        # Update notes should not change resolution_date
        updated = svc.update_claim(
            "CLM-001",
            InsuranceClaimUpdate(investigation_notes="Additional notes"),
        )
        assert updated is not None
        assert updated.resolution_date == original_date


# =====================================================================
# COVERAGE REQUIREMENTS
# =====================================================================


class TestCoverageRequirements:
    """Test coverage requirement CRUD and filtering."""

    @pytest.mark.anyio
    async def test_list_requirements(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requirements")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_requirements_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/requirements", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_requirements_filter_country(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/requirements", params={"country": "US"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["country"] == "US"

    @pytest.mark.anyio
    async def test_list_requirements_filter_met(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/requirements", params={"met": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["met"] is True

    @pytest.mark.anyio
    async def test_list_requirements_filter_unmet(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/requirements", params={"met": False}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        for item in data["items"]:
            assert item["met"] is False

    @pytest.mark.anyio
    async def test_get_requirement(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requirements/REQ-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "REQ-001"
        assert data["country"] == "US"

    @pytest.mark.anyio
    async def test_get_requirement_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requirements/REQ-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_requirement(self, client: AsyncClient):
        payload = _make_requirement_create()
        resp = await client.post(f"{API_PREFIX}/requirements", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["country"] == "JP"
        assert data["regulatory_authority"] == "PMDA"
        assert data["met"] is False
        assert data["id"].startswith("REQ-")

    @pytest.mark.anyio
    async def test_update_requirement(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/requirements/REQ-004",
            json={"met": True, "notes": "Certificate filed successfully"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["met"] is True
        assert data["notes"] == "Certificate filed successfully"

    @pytest.mark.anyio
    async def test_update_requirement_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/requirements/REQ-NONEXISTENT",
            json={"met": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_requirement(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/requirements/REQ-005")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/requirements/REQ-005")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_requirement_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/requirements/REQ-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# COVERAGE COMPLIANCE
# =====================================================================


class TestCoverageCompliance:
    """Test coverage compliance checking."""

    @pytest.mark.anyio
    async def test_compliance_eylea_fully_compliant(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance/{EYLEA_TRIAL}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["fully_compliant"] is True
        assert data["compliance_pct"] == 100.0
        assert data["requirements_unmet"] == 0

    @pytest.mark.anyio
    async def test_compliance_libtayo_partially_compliant(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance/{LIBTAYO_TRIAL}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["fully_compliant"] is False
        assert data["requirements_unmet"] > 0
        assert len(data["unmet_details"]) > 0

    @pytest.mark.anyio
    async def test_compliance_unknown_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance/unknown-trial")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_requirements"] == 0
        assert data["fully_compliant"] is True
        assert data["compliance_pct"] == 100.0

    def test_compliance_percentages(self, svc: TrialInsuranceService):
        result = svc.check_coverage_compliance(LIBTAYO_TRIAL)
        assert result.total_requirements == 2
        assert result.requirements_met == 1
        assert result.requirements_unmet == 1
        assert result.compliance_pct == 50.0

    def test_compliance_dupixent_fully_met(self, svc: TrialInsuranceService):
        result = svc.check_coverage_compliance(DUPIXENT_TRIAL)
        assert result.fully_compliant is True
        assert result.compliance_pct == 100.0


# =====================================================================
# RENEWAL MANAGEMENT
# =====================================================================


class TestRenewalManagement:
    """Test renewal initiation and management."""

    @pytest.mark.anyio
    async def test_list_renewals(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/renewals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_renewals_filter_policy(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/renewals", params={"policy_id": "POL-003"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["policy_id"] == "POL-003"

    @pytest.mark.anyio
    async def test_list_renewals_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/renewals", params={"status": "pending"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "pending"

    @pytest.mark.anyio
    async def test_get_renewal(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/renewals/RNW-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RNW-001"
        assert data["status"] == "pending"

    @pytest.mark.anyio
    async def test_get_renewal_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/renewals/RNW-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_initiate_renewal(self, client: AsyncClient):
        payload = _make_renewal_create(policy_id="POL-002")
        resp = await client.post(f"{API_PREFIX}/renewals", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["policy_id"] == "POL-002"
        assert data["status"] == "pending"
        assert data["id"].startswith("RNW-")

        # Verify policy status was updated
        resp2 = await client.get(f"{API_PREFIX}/policies/POL-002")
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "pending_renewal"

    @pytest.mark.anyio
    async def test_initiate_renewal_invalid_policy(self, client: AsyncClient):
        payload = _make_renewal_create(policy_id="POL-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/renewals", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_renewal(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/renewals/RNW-001",
            json={
                "status": "approved",
                "approved_by": "Dr. Test Approver",
                "approved_date": now.isoformat(),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["approved_by"] == "Dr. Test Approver"

    @pytest.mark.anyio
    async def test_update_renewal_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/renewals/RNW-NONEXISTENT",
            json={"status": "approved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_renewal(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/renewals/RNW-003")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/renewals/RNW-003")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_renewal_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/renewals/RNW-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# EXPIRING POLICIES
# =====================================================================


class TestExpiringPolicies:
    """Test expiring policies detection."""

    @pytest.mark.anyio
    async def test_expiring_policies_default_90_days(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/expiring")
        assert resp.status_code == 200
        data = resp.json()
        # POL-003 expires in ~25 days; POL-001 might or might not depending on timing
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_expiring_policies_30_days(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/expiring", params={"days": 30})
        assert resp.status_code == 200
        data = resp.json()
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=30)
        for item in data["items"]:
            expiry = datetime.fromisoformat(item["expiry_date"])
            assert expiry <= cutoff

    @pytest.mark.anyio
    async def test_expiring_policies_sorted_by_expiry(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/expiring", params={"days": 365})
        assert resp.status_code == 200
        data = resp.json()
        if len(data["items"]) > 1:
            dates = [
                datetime.fromisoformat(item["expiry_date"])
                for item in data["items"]
            ]
            assert dates == sorted(dates)

    @pytest.mark.anyio
    async def test_expiring_policies_custom_days(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/expiring", params={"days": 7})
        assert resp.status_code == 200

    def test_expiring_excludes_expired_policies(self, svc: TrialInsuranceService):
        expiring = svc.get_expiring_policies(days=365)
        for p in expiring:
            assert p.status in (PolicyStatus.ACTIVE, PolicyStatus.PENDING_RENEWAL)


# =====================================================================
# INSURANCE METRICS
# =====================================================================


class TestInsuranceMetrics:
    """Test insurance metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_policies"] == 4
        assert data["active_policies"] >= 2
        assert data["total_certificates"] == 6
        assert data["active_certificates"] >= 4
        assert data["total_claims"] == 3
        assert data["open_claims"] >= 1
        assert data["total_requirements"] == 5
        assert data["requirements_met"] == 4
        assert 0 <= data["compliance_pct"] <= 100

    def test_metrics_policies_by_type(self, svc: TrialInsuranceService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.policies_by_type.values())
        assert total_by_type == metrics.total_policies

    def test_metrics_policies_by_status(self, svc: TrialInsuranceService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.policies_by_status.values())
        assert total_by_status == metrics.total_policies

    def test_metrics_coverage_amount(self, svc: TrialInsuranceService):
        metrics = svc.get_metrics()
        assert metrics.total_coverage_amount > 0
        assert metrics.total_premium > 0

    def test_metrics_claims_amounts(self, svc: TrialInsuranceService):
        metrics = svc.get_metrics()
        assert metrics.total_claimed_amount > 0
        assert metrics.total_settled_amount > 0
        assert metrics.total_settled_amount <= metrics.total_claimed_amount

    def test_metrics_compliance_percentage(self, svc: TrialInsuranceService):
        metrics = svc.get_metrics()
        expected_pct = round((4 / 5) * 100.0, 1)
        assert metrics.compliance_pct == expected_pct

    def test_metrics_pending_renewals(self, svc: TrialInsuranceService):
        metrics = svc.get_metrics()
        assert metrics.pending_renewals >= 1

    def test_metrics_expiring_within_30_days(self, svc: TrialInsuranceService):
        metrics = svc.get_metrics()
        assert metrics.expiring_within_30_days >= 1  # POL-003

    def test_metrics_expiring_within_90_days(self, svc: TrialInsuranceService):
        metrics = svc.get_metrics()
        assert metrics.expiring_within_90_days >= metrics.expiring_within_30_days


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_trial_insurance_service()
        svc2 = get_trial_insurance_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_trial_insurance_service()
        svc2 = reset_trial_insurance_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_trial_insurance_service()
        svc.delete_policy("POL-001")
        assert svc.get_policy("POL-001") is None
        svc2 = reset_trial_insurance_service()
        assert svc2.get_policy("POL-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_policies_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/policies")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_certificates_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/certificates")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_claims_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/claims")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_requirements_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requirements")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_renewals_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/renewals")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_policy_create_all_fields(self, client: AsyncClient):
        payload = _make_policy_create(
            policy_type="product_liability",
            coverage_scope="regional",
            countries_covered=["US", "CA", "MX"],
            deductible=25_000.0,
            premium_currency="EUR",
            broker="Complete Broker LLC",
            special_conditions="All fields populated",
        )
        resp = await client.post(f"{API_PREFIX}/policies", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["policy_type"] == "product_liability"
        assert data["coverage_scope"] == "regional"

    @pytest.mark.anyio
    async def test_policy_update_coverage_amount(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/policies/POL-001",
            json={"coverage_amount": 75_000_000.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["coverage_amount"] == 75_000_000.0

    @pytest.mark.anyio
    async def test_claim_create_all_fields(self, client: AsyncClient):
        payload = _make_claim_create(
            patient_id="PAT-12345",
            claim_amount=500_000.0,
        )
        resp = await client.post(f"{API_PREFIX}/claims", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_requirement_create_with_notes(self, client: AsyncClient):
        payload = _make_requirement_create(
            notes="Special requirement for Phase III trial",
        )
        resp = await client.post(f"{API_PREFIX}/requirements", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["notes"] == "Special requirement for Phase III trial"

    @pytest.mark.anyio
    async def test_renewal_with_coverage_changes(self, client: AsyncClient):
        payload = _make_renewal_create(
            coverage_changes="Extended to include South America",
        )
        resp = await client.post(f"{API_PREFIX}/renewals", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["coverage_changes"] == "Extended to include South America"

    @pytest.mark.anyio
    async def test_issue_certificate_for_pending_renewal_policy(self, client: AsyncClient):
        """Certificates can be issued for policies with pending_renewal status."""
        payload = _make_certificate_create(
            policy_id="POL-003",
            trial_id=LIBTAYO_TRIAL,
            site_id="SITE-201",
            country="NL",
        )
        resp = await client.post(f"{API_PREFIX}/certificates", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_multiple_claims_same_policy(self, client: AsyncClient):
        """Filing multiple claims against the same policy should work."""
        for i in range(3):
            payload = _make_claim_create(
                claim_amount=50_000.0 * (i + 1),
                incident_description=f"Test incident {i + 1}",
            )
            resp = await client.post(f"{API_PREFIX}/claims", json=payload)
            assert resp.status_code == 201

        # Verify all claims exist
        resp = await client.get(
            f"{API_PREFIX}/claims", params={"policy_id": "POL-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 5  # 2 seed + 3 new


# =====================================================================
# POLICY DETAILS VERIFICATION
# =====================================================================


class TestPolicyDetails:
    """Test detailed policy attributes and relationships."""

    @pytest.mark.anyio
    async def test_policy_has_countries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/policies/POL-001")
        data = resp.json()
        assert isinstance(data["countries_covered"], list)
        assert len(data["countries_covered"]) > 0
        assert "US" in data["countries_covered"]

    @pytest.mark.anyio
    async def test_policy_coverage_scope(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/policies/POL-001")
        data = resp.json()
        assert data["coverage_scope"] == "global"

    @pytest.mark.anyio
    async def test_policy_dates(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/policies/POL-001")
        data = resp.json()
        effective = datetime.fromisoformat(data["effective_date"])
        expiry = datetime.fromisoformat(data["expiry_date"])
        assert expiry > effective

    @pytest.mark.anyio
    async def test_expired_policy_attributes(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/policies/POL-004")
        data = resp.json()
        assert data["status"] == "expired"
        expiry = datetime.fromisoformat(data["expiry_date"])
        assert expiry < datetime.now(timezone.utc)

    @pytest.mark.anyio
    async def test_certificate_has_filing_info(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/certificates/CERT-001")
        data = resp.json()
        assert data["filed_with_authority"] is True
        assert data["authority_name"] == "FDA"
        assert data["filing_date"] is not None

    @pytest.mark.anyio
    async def test_pending_certificate_not_filed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/certificates/CERT-006")
        data = resp.json()
        assert data["status"] == "pending"
        assert data["filed_with_authority"] is False
        assert data["filing_date"] is None


# =====================================================================
# COMPLIANCE DETAILS
# =====================================================================


class TestComplianceDetails:
    """Test detailed compliance checking scenarios."""

    def test_compliance_unmet_details_contain_requirement_info(
        self, svc: TrialInsuranceService
    ):
        result = svc.check_coverage_compliance(LIBTAYO_TRIAL)
        assert len(result.unmet_details) == 1
        unmet = result.unmet_details[0]
        assert unmet.country == "BE"
        assert unmet.regulatory_authority == "FAMHP"
        assert unmet.met is False

    def test_compliance_after_meeting_requirement(self, svc: TrialInsuranceService):
        from app.schemas.trial_insurance import CoverageRequirementUpdate
        # Mark the unmet requirement as met
        svc.update_requirement("REQ-004", CoverageRequirementUpdate(met=True))

        result = svc.check_coverage_compliance(LIBTAYO_TRIAL)
        assert result.fully_compliant is True
        assert result.compliance_pct == 100.0
        assert len(result.unmet_details) == 0

    @pytest.mark.anyio
    async def test_compliance_after_adding_requirement(self, client: AsyncClient):
        # Add a new unmet requirement for EYLEA
        payload = _make_requirement_create(
            trial_id=EYLEA_TRIAL, country="AU", met=False
        )
        # Need to pass met=False explicitly since _make_requirement_create doesnt include it
        payload["met"] = False
        resp = await client.post(f"{API_PREFIX}/requirements", json=payload)
        assert resp.status_code == 201

        # Compliance should now be partial
        resp = await client.get(f"{API_PREFIX}/compliance/{EYLEA_TRIAL}")
        data = resp.json()
        assert data["fully_compliant"] is False
        assert data["requirements_unmet"] >= 1


# =====================================================================
# RENEWAL WORKFLOW
# =====================================================================


class TestRenewalWorkflow:
    """Test complete renewal workflow."""

    def test_renewal_changes_policy_status(self, svc: TrialInsuranceService):
        # POL-002 is active
        policy = svc.get_policy("POL-002")
        assert policy is not None
        assert policy.status == PolicyStatus.ACTIVE

        # Initiate renewal
        from app.schemas.trial_insurance import InsuranceRenewalCreate
        now = datetime.now(timezone.utc)
        svc.initiate_renewal(InsuranceRenewalCreate(
            policy_id="POL-002",
            renewal_date=now + timedelta(days=60),
            new_premium=450_000.0,
            premium_change_pct=5.88,
        ))

        # Policy should be pending_renewal
        policy = svc.get_policy("POL-002")
        assert policy is not None
        assert policy.status == PolicyStatus.PENDING_RENEWAL

    def test_renewal_premium_change_tracking(self, svc: TrialInsuranceService):
        renewal = svc.get_renewal("RNW-001")
        assert renewal is not None
        assert renewal.premium_change_pct == 10.26
        assert renewal.new_premium == 215_000.0

    def test_renewal_approval_workflow(self, svc: TrialInsuranceService):
        from app.schemas.trial_insurance import InsuranceRenewalUpdate
        now = datetime.now(timezone.utc)

        # Approve the pending renewal
        updated = svc.update_renewal(
            "RNW-001",
            InsuranceRenewalUpdate(
                status=RenewalStatus.APPROVED,
                approved_by="Dr. Renewal Approver",
                approved_date=now,
            ),
        )
        assert updated is not None
        assert updated.status == RenewalStatus.APPROVED
        assert updated.approved_by == "Dr. Renewal Approver"

    @pytest.mark.anyio
    async def test_full_renewal_api_workflow(self, client: AsyncClient):
        # 1. Initiate renewal for POL-002
        now = datetime.now(timezone.utc)
        payload = {
            "policy_id": "POL-002",
            "renewal_date": (now + timedelta(days=60)).isoformat(),
            "new_premium": 440_000.0,
            "premium_change_pct": 3.53,
            "coverage_changes": "Added Mexico coverage",
        }
        resp = await client.post(f"{API_PREFIX}/renewals", json=payload)
        assert resp.status_code == 201
        renewal_id = resp.json()["id"]

        # 2. Verify policy status changed
        resp = await client.get(f"{API_PREFIX}/policies/POL-002")
        assert resp.json()["status"] == "pending_renewal"

        # 3. Approve renewal
        resp = await client.put(
            f"{API_PREFIX}/renewals/{renewal_id}",
            json={
                "status": "approved",
                "approved_by": "VP Clinical Ops",
                "approved_date": now.isoformat(),
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"


# =====================================================================
# SORTED OUTPUT VERIFICATION
# =====================================================================


class TestSortedOutput:
    """Test that list endpoints return sorted results."""

    @pytest.mark.anyio
    async def test_policies_sorted_by_created_at_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/policies")
        data = resp.json()
        dates = [
            datetime.fromisoformat(item["created_at"])
            for item in data["items"]
        ]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_certificates_sorted_by_issued_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/certificates")
        data = resp.json()
        dates = [
            datetime.fromisoformat(item["issued_date"])
            for item in data["items"]
        ]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_claims_sorted_by_claim_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/claims")
        data = resp.json()
        dates = [
            datetime.fromisoformat(item["claim_date"])
            for item in data["items"]
        ]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_requirements_sorted_by_deadline_asc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/requirements")
        data = resp.json()
        dates = [
            datetime.fromisoformat(item["deadline"])
            for item in data["items"]
        ]
        assert dates == sorted(dates)

    @pytest.mark.anyio
    async def test_renewals_sorted_by_renewal_date_asc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/renewals")
        data = resp.json()
        dates = [
            datetime.fromisoformat(item["renewal_date"])
            for item in data["items"]
        ]
        assert dates == sorted(dates)
