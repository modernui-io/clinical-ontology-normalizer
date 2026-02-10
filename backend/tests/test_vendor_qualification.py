"""Tests for Vendor Qualification & Oversight (QA-VENDOR).

Covers:
- Seed data verification (vendors, agreements, assessments, risk assessments)
- Vendor CRUD (create, read, update, delete, list, filter by category/status/risk/trial)
- Quality agreement CRUD (create, read, update, delete, list, filter by vendor/trial/status)
- Vendor assessment CRUD (create, read, delete, list, filter by vendor/trial/rating)
- Risk assessment CRUD (create, read, delete, list, filter by vendor/risk_level)
- Overall score computation (average of 4 component scores)
- Metrics computation (vendor counts, agreement breakdown, score averages, risk overview)
- Error handling (404s, 400s for invalid vendor references)
- Edge cases (empty filters, boundary conditions, enum coverage)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.vendor_qualification import (
    AgreementStatus,
    PerformanceRating,
    QualificationStatus,
    RiskLevel,
    VendorCategory,
)
from app.services.vendor_qualification_service import (
    VendorQualificationService,
    get_vendor_qualification_service,
    reset_vendor_qualification_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/vendor-qualification"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_vendor_qualification_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> VendorQualificationService:
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


def _make_vendor_create(**overrides) -> dict:
    defaults = {
        "name": "Test Vendor Inc.",
        "category": "cro",
        "contact_name": "John Doe",
        "contact_email": "john.doe@testvendor.com",
        "country": "United States",
        "services_provided": ["Clinical monitoring", "Data management"],
        "risk_level": "medium",
    }
    defaults.update(overrides)
    return defaults


def _make_agreement_create(**overrides) -> dict:
    defaults = {
        "vendor_id": "VND-001",
        "trial_id": EYLEA_TRIAL,
        "agreement_number": "QA-TEST-001",
        "title": "Test Quality Agreement",
        "key_terms": ["GCP compliance", "Data integrity"],
    }
    defaults.update(overrides)
    return defaults


def _make_assessment_create(**overrides) -> dict:
    defaults = {
        "vendor_id": "VND-001",
        "trial_id": EYLEA_TRIAL,
        "assessor": "Dr. Test Assessor",
        "quality_score": 85.0,
        "timeliness_score": 80.0,
        "communication_score": 82.0,
        "compliance_score": 88.0,
        "rating": "good",
        "strengths": ["Reliable service"],
        "improvements_needed": ["Response time"],
        "notes": "Quarterly assessment.",
    }
    defaults.update(overrides)
    return defaults


def _make_risk_assessment_create(**overrides) -> dict:
    defaults = {
        "vendor_id": "VND-001",
        "assessed_by": "Quality Director",
        "risk_level": "medium",
        "risk_factors": ["New engagement", "Complex integration"],
        "mitigation_plan": "Enhanced monitoring for first quarter.",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_vendors_count(self, svc: VendorQualificationService):
        vendors = svc.list_vendors()
        assert len(vendors) == 12

    def test_seed_vendors_categories_present(self, svc: VendorQualificationService):
        vendors = svc.list_vendors()
        categories = {v.category for v in vendors}
        assert VendorCategory.CRO in categories
        assert VendorCategory.CENTRAL_LAB in categories
        assert VendorCategory.IRT_PROVIDER in categories
        assert VendorCategory.EDC_PROVIDER in categories
        assert VendorCategory.PACKAGING in categories
        assert VendorCategory.LOGISTICS in categories
        assert VendorCategory.IMAGING in categories
        assert VendorCategory.BIOANALYTICAL_LAB in categories
        assert VendorCategory.SAFETY_DATABASE in categories
        assert VendorCategory.MEDICAL_WRITING in categories

    def test_seed_vendors_statuses_present(self, svc: VendorQualificationService):
        vendors = svc.list_vendors()
        statuses = {v.qualification_status for v in vendors}
        assert QualificationStatus.QUALIFIED in statuses
        assert QualificationStatus.CONDITIONALLY_QUALIFIED in statuses
        assert QualificationStatus.REQUALIFICATION_DUE in statuses
        assert QualificationStatus.DISQUALIFIED in statuses

    def test_seed_vendors_risk_levels_present(self, svc: VendorQualificationService):
        vendors = svc.list_vendors()
        risks = {v.risk_level for v in vendors}
        assert RiskLevel.LOW in risks
        assert RiskLevel.MEDIUM in risks
        assert RiskLevel.HIGH in risks
        assert RiskLevel.CRITICAL in risks

    def test_seed_agreements_count(self, svc: VendorQualificationService):
        agreements = svc.list_agreements()
        assert len(agreements) == 15

    def test_seed_agreements_statuses_present(self, svc: VendorQualificationService):
        agreements = svc.list_agreements()
        statuses = {a.status for a in agreements}
        assert AgreementStatus.DRAFT in statuses
        assert AgreementStatus.UNDER_REVIEW in statuses
        assert AgreementStatus.EXECUTED in statuses
        assert AgreementStatus.EXPIRED in statuses
        assert AgreementStatus.TERMINATED in statuses

    def test_seed_assessments_count(self, svc: VendorQualificationService):
        assessments = svc.list_assessments()
        assert len(assessments) == 15

    def test_seed_assessments_ratings_present(self, svc: VendorQualificationService):
        assessments = svc.list_assessments()
        ratings = {a.rating for a in assessments}
        assert PerformanceRating.EXCELLENT in ratings
        assert PerformanceRating.GOOD in ratings
        assert PerformanceRating.ACCEPTABLE in ratings
        assert PerformanceRating.BELOW_EXPECTATIONS in ratings
        assert PerformanceRating.UNACCEPTABLE in ratings

    def test_seed_risk_assessments_count(self, svc: VendorQualificationService):
        risk_assessments = svc.list_risk_assessments()
        assert len(risk_assessments) == 12

    def test_seed_risk_assessments_levels_present(self, svc: VendorQualificationService):
        risk_assessments = svc.list_risk_assessments()
        levels = {r.risk_level for r in risk_assessments}
        assert RiskLevel.LOW in levels
        assert RiskLevel.MEDIUM in levels
        assert RiskLevel.HIGH in levels
        assert RiskLevel.CRITICAL in levels

    def test_seed_vendor_has_active_trials(self, svc: VendorQualificationService):
        vendor = svc.get_vendor("VND-001")
        assert vendor is not None
        assert len(vendor.active_trials) >= 2
        assert EYLEA_TRIAL in vendor.active_trials

    def test_seed_vendor_has_services(self, svc: VendorQualificationService):
        vendor = svc.get_vendor("VND-001")
        assert vendor is not None
        assert len(vendor.services_provided) > 0

    def test_seed_disqualified_vendor_no_trials(self, svc: VendorQualificationService):
        vendor = svc.get_vendor("VND-012")
        assert vendor is not None
        assert vendor.qualification_status == QualificationStatus.DISQUALIFIED
        assert vendor.risk_level == RiskLevel.CRITICAL
        assert len(vendor.active_trials) == 0

    def test_seed_agreement_has_key_terms(self, svc: VendorQualificationService):
        agreement = svc.get_agreement("QA-001")
        assert agreement is not None
        assert len(agreement.key_terms) > 0

    def test_seed_assessment_has_overall_score(self, svc: VendorQualificationService):
        assessment = svc.get_assessment("VA-001")
        assert assessment is not None
        expected = round(
            (assessment.quality_score + assessment.timeliness_score
             + assessment.communication_score + assessment.compliance_score) / 4.0,
            1,
        )
        assert assessment.overall_score == expected


# =====================================================================
# VENDOR CRUD
# =====================================================================


class TestVendorCrud:
    """Test vendor create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_vendors(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/vendors")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_vendors_filter_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/vendors", params={"category": "cro"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        for item in data["items"]:
            assert item["category"] == "cro"

    @pytest.mark.anyio
    async def test_list_vendors_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/vendors", params={"qualification_status": "qualified"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["qualification_status"] == "qualified"

    @pytest.mark.anyio
    async def test_list_vendors_filter_risk_level(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/vendors", params={"risk_level": "high"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["risk_level"] == "high"

    @pytest.mark.anyio
    async def test_list_vendors_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/vendors", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert EYLEA_TRIAL in item["active_trials"]

    @pytest.mark.anyio
    async def test_get_vendor(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/vendors/VND-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "VND-001"
        assert data["name"] == "Covance Drug Development (LabCorp)"

    @pytest.mark.anyio
    async def test_get_vendor_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/vendors/VND-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_vendor(self, client: AsyncClient):
        payload = _make_vendor_create()
        resp = await client.post(f"{API_PREFIX}/vendors", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Vendor Inc."
        assert data["id"].startswith("VND-")
        assert data["qualification_status"] == "pending"
        assert data["active_trials"] == []

    @pytest.mark.anyio
    async def test_create_vendor_all_categories(self, client: AsyncClient):
        for cat in ["cro", "central_lab", "irt_provider", "edc_provider",
                     "packaging", "logistics", "imaging", "bioanalytical_lab",
                     "safety_database", "medical_writing"]:
            payload = _make_vendor_create(category=cat, name=f"Test {cat}")
            resp = await client.post(f"{API_PREFIX}/vendors", json=payload)
            assert resp.status_code == 201
            assert resp.json()["category"] == cat

    @pytest.mark.anyio
    async def test_update_vendor(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/vendors/VND-001",
            json={"name": "Updated Vendor Name", "risk_level": "high"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Vendor Name"
        assert data["risk_level"] == "high"

    @pytest.mark.anyio
    async def test_update_vendor_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/vendors/VND-008",
            json={"qualification_status": "qualified"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["qualification_status"] == "qualified"

    @pytest.mark.anyio
    async def test_update_vendor_rating(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/vendors/VND-008",
            json={"overall_rating": "good"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_rating"] == "good"

    @pytest.mark.anyio
    async def test_update_vendor_active_trials(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/vendors/VND-012",
            json={"active_trials": [LIBTAYO_TRIAL]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert LIBTAYO_TRIAL in data["active_trials"]

    @pytest.mark.anyio
    async def test_update_vendor_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/vendors/VND-NONEXISTENT",
            json={"name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_vendor(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/vendors/VND-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/vendors/VND-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_vendor_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/vendors/VND-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_vendors_sorted_by_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/vendors")
        data = resp.json()
        ids = [item["id"] for item in data["items"]]
        assert ids == sorted(ids)


# =====================================================================
# QUALITY AGREEMENT CRUD
# =====================================================================


class TestAgreementCrud:
    """Test quality agreement CRUD operations."""

    @pytest.mark.anyio
    async def test_list_agreements(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_agreements_filter_vendor(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements", params={"vendor_id": "VND-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["vendor_id"] == "VND-001"

    @pytest.mark.anyio
    async def test_list_agreements_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/agreements", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_agreements_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/agreements", params={"status": "executed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "executed"

    @pytest.mark.anyio
    async def test_get_agreement(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements/QA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "QA-001"
        assert data["vendor_id"] == "VND-001"

    @pytest.mark.anyio
    async def test_get_agreement_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements/QA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_agreement(self, client: AsyncClient):
        payload = _make_agreement_create()
        resp = await client.post(f"{API_PREFIX}/agreements", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["vendor_id"] == "VND-001"
        assert data["id"].startswith("QA-")
        assert data["status"] == "draft"

    @pytest.mark.anyio
    async def test_create_agreement_invalid_vendor(self, client: AsyncClient):
        payload = _make_agreement_create(vendor_id="VND-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/agreements", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_create_agreement_with_dates(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = _make_agreement_create(
            effective_date=now.isoformat(),
            expiry_date=(now + timedelta(days=365)).isoformat(),
        )
        resp = await client.post(f"{API_PREFIX}/agreements", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["effective_date"] is not None
        assert data["expiry_date"] is not None

    @pytest.mark.anyio
    async def test_update_agreement(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/agreements/QA-009",
            json={"status": "executed", "signed_by_sponsor": "Dr. Smith", "signed_by_vendor": "Jane Doe"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "executed"
        assert data["signed_by_sponsor"] == "Dr. Smith"
        assert data["signed_by_vendor"] == "Jane Doe"

    @pytest.mark.anyio
    async def test_update_agreement_key_terms(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/agreements/QA-001",
            json={"key_terms": ["Updated term 1", "Updated term 2"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["key_terms"]) == 2
        assert "Updated term 1" in data["key_terms"]

    @pytest.mark.anyio
    async def test_update_agreement_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/agreements/QA-NONEXISTENT",
            json={"status": "executed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_agreement(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/agreements/QA-015")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/agreements/QA-015")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_agreement_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/agreements/QA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_agreements_sorted_by_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements")
        data = resp.json()
        ids = [item["id"] for item in data["items"]]
        assert ids == sorted(ids)


# =====================================================================
# VENDOR ASSESSMENT CRUD
# =====================================================================


class TestAssessmentCrud:
    """Test vendor assessment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_assessments_filter_vendor(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assessments", params={"vendor_id": "VND-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["vendor_id"] == "VND-001"

    @pytest.mark.anyio
    async def test_list_assessments_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assessments", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_assessments_filter_rating(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assessments", params={"rating": "excellent"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["rating"] == "excellent"

    @pytest.mark.anyio
    async def test_get_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/VA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "VA-001"
        assert data["vendor_id"] == "VND-001"

    @pytest.mark.anyio
    async def test_get_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/VA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_assessment(self, client: AsyncClient):
        payload = _make_assessment_create()
        resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["vendor_id"] == "VND-001"
        assert data["id"].startswith("VA-")
        # Verify overall_score is computed correctly
        expected_overall = round(
            (85.0 + 80.0 + 82.0 + 88.0) / 4.0, 1
        )
        assert data["overall_score"] == expected_overall

    @pytest.mark.anyio
    async def test_create_assessment_invalid_vendor(self, client: AsyncClient):
        payload = _make_assessment_create(vendor_id="VND-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_create_assessment_overall_score_computation(self, client: AsyncClient):
        payload = _make_assessment_create(
            quality_score=100.0,
            timeliness_score=80.0,
            communication_score=60.0,
            compliance_score=40.0,
        )
        resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["overall_score"] == 70.0  # (100+80+60+40)/4

    @pytest.mark.anyio
    async def test_create_assessment_no_trial(self, client: AsyncClient):
        payload = _make_assessment_create(trial_id=None)
        resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] is None

    @pytest.mark.anyio
    async def test_create_assessment_all_ratings(self, client: AsyncClient):
        for rating in ["excellent", "good", "acceptable", "below_expectations", "unacceptable"]:
            payload = _make_assessment_create(rating=rating)
            resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
            assert resp.status_code == 201
            assert resp.json()["rating"] == rating

    @pytest.mark.anyio
    async def test_delete_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assessments/VA-013")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/assessments/VA-013")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assessment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assessments/VA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_assessments_sorted_by_date_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        data = resp.json()
        dates = [item["assessment_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    def test_all_seed_assessments_have_overall_score(self, svc: VendorQualificationService):
        assessments = svc.list_assessments()
        for a in assessments:
            expected = round(
                (a.quality_score + a.timeliness_score
                 + a.communication_score + a.compliance_score) / 4.0,
                1,
            )
            assert a.overall_score == expected

    def test_assessment_scores_in_valid_range(self, svc: VendorQualificationService):
        assessments = svc.list_assessments()
        for a in assessments:
            assert 0 <= a.quality_score <= 100
            assert 0 <= a.timeliness_score <= 100
            assert 0 <= a.communication_score <= 100
            assert 0 <= a.compliance_score <= 100
            assert 0 <= a.overall_score <= 100


# =====================================================================
# RISK ASSESSMENT CRUD
# =====================================================================


class TestRiskAssessmentCrud:
    """Test vendor risk assessment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_risk_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risk-assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_risk_assessments_filter_vendor(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/risk-assessments", params={"vendor_id": "VND-008"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["vendor_id"] == "VND-008"

    @pytest.mark.anyio
    async def test_list_risk_assessments_filter_risk_level(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/risk-assessments", params={"risk_level": "high"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["risk_level"] == "high"

    @pytest.mark.anyio
    async def test_get_risk_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risk-assessments/VRA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "VRA-001"
        assert data["vendor_id"] == "VND-001"

    @pytest.mark.anyio
    async def test_get_risk_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risk-assessments/VRA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_risk_assessment(self, client: AsyncClient):
        payload = _make_risk_assessment_create()
        resp = await client.post(f"{API_PREFIX}/risk-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["vendor_id"] == "VND-001"
        assert data["id"].startswith("VRA-")
        assert data["risk_level"] == "medium"

    @pytest.mark.anyio
    async def test_create_risk_assessment_invalid_vendor(self, client: AsyncClient):
        payload = _make_risk_assessment_create(vendor_id="VND-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/risk-assessments", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_create_risk_assessment_all_levels(self, client: AsyncClient):
        for level in ["low", "medium", "high", "critical"]:
            payload = _make_risk_assessment_create(risk_level=level)
            resp = await client.post(f"{API_PREFIX}/risk-assessments", json=payload)
            assert resp.status_code == 201
            assert resp.json()["risk_level"] == level

    @pytest.mark.anyio
    async def test_create_risk_assessment_with_next_review(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = _make_risk_assessment_create(
            next_review_date=(now + timedelta(days=30)).isoformat()
        )
        resp = await client.post(f"{API_PREFIX}/risk-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["next_review_date"] is not None

    @pytest.mark.anyio
    async def test_delete_risk_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/risk-assessments/VRA-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/risk-assessments/VRA-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_risk_assessment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/risk-assessments/VRA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_risk_assessments_sorted_by_date_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risk-assessments")
        data = resp.json()
        dates = [item["assessed_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    def test_risk_assessment_has_required_fields(self, svc: VendorQualificationService):
        ra = svc.get_risk_assessment("VRA-007")
        assert ra is not None
        assert ra.vendor_id == "VND-008"
        assert ra.risk_level == RiskLevel.HIGH
        assert len(ra.risk_factors) > 0
        assert ra.mitigation_plan is not None
        assert ra.assessed_by

    def test_critical_risk_has_factors(self, svc: VendorQualificationService):
        ra = svc.get_risk_assessment("VRA-009")
        assert ra is not None
        assert ra.risk_level == RiskLevel.CRITICAL
        assert len(ra.risk_factors) >= 3


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test vendor qualification metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_vendors"] == 12
        assert data["total_agreements"] == 15
        assert data["total_assessments"] == 15
        assert data["total_risk_assessments"] == 12
        assert data["avg_quality_score"] > 0
        assert data["avg_overall_score"] > 0

    @pytest.mark.anyio
    async def test_metrics_vendors_by_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_cat = data["vendors_by_category"]
        total = sum(by_cat.values())
        assert total == data["total_vendors"]
        assert "cro" in by_cat

    @pytest.mark.anyio
    async def test_metrics_vendors_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["vendors_by_status"]
        total = sum(by_status.values())
        assert total == data["total_vendors"]
        assert "qualified" in by_status

    @pytest.mark.anyio
    async def test_metrics_vendors_by_risk(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_risk = data["vendors_by_risk"]
        total = sum(by_risk.values())
        assert total == data["total_vendors"]

    @pytest.mark.anyio
    async def test_metrics_agreements_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["agreements_by_status"]
        total = sum(by_status.values())
        assert total == data["total_agreements"]
        assert "executed" in by_status

    @pytest.mark.anyio
    async def test_metrics_high_risk_vendors(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["high_risk_vendors"] > 0

    @pytest.mark.anyio
    async def test_metrics_requalification_due(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["requalification_due"] >= 1

    def test_metrics_avg_quality_score(self, svc: VendorQualificationService):
        metrics = svc.get_metrics()
        assessments = svc.list_assessments()
        expected = round(
            sum(a.quality_score for a in assessments) / len(assessments), 1
        )
        assert abs(metrics.avg_quality_score - expected) < 0.2

    def test_metrics_avg_overall_score(self, svc: VendorQualificationService):
        metrics = svc.get_metrics()
        assessments = svc.list_assessments()
        expected = round(
            sum(a.overall_score for a in assessments) / len(assessments), 1
        )
        assert abs(metrics.avg_overall_score - expected) < 0.2

    def test_metrics_high_risk_matches_risk_assessments(self, svc: VendorQualificationService):
        metrics = svc.get_metrics()
        risk_assessments = svc.list_risk_assessments()
        high_risk_vendor_ids = {
            r.vendor_id for r in risk_assessments
            if r.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        }
        assert metrics.high_risk_vendors == len(high_risk_vendor_ids)


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_vendor_qualification_service()
        svc2 = get_vendor_qualification_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_vendor_qualification_service()
        svc2 = reset_vendor_qualification_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_vendor_qualification_service()
        svc.delete_vendor("VND-001")
        assert svc.get_vendor("VND-001") is None
        svc2 = reset_vendor_qualification_service()
        assert svc2.get_vendor("VND-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_vendors_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/vendors")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_agreements_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_assessments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_risk_assessments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risk-assessments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_vendors_empty_trial_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/vendors", params={"trial_id": "NONEXISTENT"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_agreements_empty_vendor_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/agreements", params={"vendor_id": "VND-NONEXISTENT"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_assessments_empty_vendor_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assessments", params={"vendor_id": "VND-NONEXISTENT"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_risk_assessments_empty_vendor_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/risk-assessments", params={"vendor_id": "VND-NONEXISTENT"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_create_vendor_with_services(self, client: AsyncClient):
        payload = _make_vendor_create(
            services_provided=["Service A", "Service B", "Service C"]
        )
        resp = await client.post(f"{API_PREFIX}/vendors", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["services_provided"]) == 3

    @pytest.mark.anyio
    async def test_create_vendor_minimal(self, client: AsyncClient):
        payload = {
            "name": "Minimal Vendor",
            "category": "cro",
            "contact_name": "Contact",
            "contact_email": "contact@minimal.com",
            "country": "US",
        }
        resp = await client.post(f"{API_PREFIX}/vendors", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["services_provided"] == []
        assert data["risk_level"] == "medium"

    @pytest.mark.anyio
    async def test_create_agreement_with_key_terms(self, client: AsyncClient):
        payload = _make_agreement_create(
            key_terms=["Term 1", "Term 2", "Term 3", "Term 4"]
        )
        resp = await client.post(f"{API_PREFIX}/agreements", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["key_terms"]) == 4

    @pytest.mark.anyio
    async def test_create_assessment_with_strengths(self, client: AsyncClient):
        payload = _make_assessment_create(
            strengths=["Strength 1", "Strength 2", "Strength 3"],
            improvements_needed=["Improve 1"],
        )
        resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["strengths"]) == 3
        assert len(data["improvements_needed"]) == 1

    @pytest.mark.anyio
    async def test_create_risk_assessment_with_factors(self, client: AsyncClient):
        payload = _make_risk_assessment_create(
            risk_factors=["Factor 1", "Factor 2", "Factor 3", "Factor 4"]
        )
        resp = await client.post(f"{API_PREFIX}/risk-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["risk_factors"]) == 4


# =====================================================================
# DATA VALIDATION
# =====================================================================


class TestDataValidation:
    """Test detailed data validation across the system."""

    @pytest.mark.anyio
    async def test_vendor_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/vendors/VND-001")
        data = resp.json()
        assert "id" in data
        assert "name" in data
        assert "category" in data
        assert "qualification_status" in data
        assert "risk_level" in data
        assert "contact_name" in data
        assert "contact_email" in data
        assert "country" in data
        assert "services_provided" in data
        assert "active_trials" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_agreement_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements/QA-001")
        data = resp.json()
        assert "id" in data
        assert "vendor_id" in data
        assert "trial_id" in data
        assert "agreement_number" in data
        assert "title" in data
        assert "status" in data
        assert "key_terms" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_assessment_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/VA-001")
        data = resp.json()
        assert "id" in data
        assert "vendor_id" in data
        assert "trial_id" in data
        assert "assessor" in data
        assert "quality_score" in data
        assert "timeliness_score" in data
        assert "communication_score" in data
        assert "compliance_score" in data
        assert "overall_score" in data
        assert "rating" in data
        assert "strengths" in data
        assert "improvements_needed" in data

    @pytest.mark.anyio
    async def test_risk_assessment_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risk-assessments/VRA-001")
        data = resp.json()
        assert "id" in data
        assert "vendor_id" in data
        assert "assessed_date" in data
        assert "assessed_by" in data
        assert "risk_level" in data
        assert "risk_factors" in data
        assert "mitigation_plan" in data

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_vendors" in data
        assert "vendors_by_category" in data
        assert "vendors_by_status" in data
        assert "vendors_by_risk" in data
        assert "total_agreements" in data
        assert "agreements_by_status" in data
        assert "total_assessments" in data
        assert "avg_quality_score" in data
        assert "avg_overall_score" in data
        assert "total_risk_assessments" in data
        assert "high_risk_vendors" in data
        assert "requalification_due" in data

    def test_qualified_vendors_have_dates(self, svc: VendorQualificationService):
        vendors = svc.list_vendors(qualification_status=QualificationStatus.QUALIFIED)
        for v in vendors:
            assert v.qualification_date is not None

    def test_executed_agreements_have_signers(self, svc: VendorQualificationService):
        agreements = svc.list_agreements(status=AgreementStatus.EXECUTED)
        for a in agreements:
            assert a.signed_by_sponsor is not None
            assert a.signed_by_vendor is not None

    def test_draft_agreements_have_no_signers(self, svc: VendorQualificationService):
        agreements = svc.list_agreements(status=AgreementStatus.DRAFT)
        for a in agreements:
            assert a.signed_by_sponsor is None
            assert a.signed_by_vendor is None

    def test_vendor_covance_details(self, svc: VendorQualificationService):
        v = svc.get_vendor("VND-001")
        assert v is not None
        assert v.category == VendorCategory.CRO
        assert v.qualification_status == QualificationStatus.QUALIFIED
        assert v.risk_level == RiskLevel.LOW
        assert v.overall_rating == PerformanceRating.EXCELLENT
        assert v.country == "United States"

    def test_vendor_clario_conditionally_qualified(self, svc: VendorQualificationService):
        v = svc.get_vendor("VND-008")
        assert v is not None
        assert v.qualification_status == QualificationStatus.CONDITIONALLY_QUALIFIED
        assert v.risk_level == RiskLevel.HIGH
        assert v.overall_rating == PerformanceRating.BELOW_EXPECTATIONS

    def test_vendor_oracle_requalification_due(self, svc: VendorQualificationService):
        v = svc.get_vendor("VND-010")
        assert v is not None
        assert v.qualification_status == QualificationStatus.REQUALIFICATION_DUE

    def test_agreements_across_all_trials(self, svc: VendorQualificationService):
        eylea = svc.list_agreements(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_agreements(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_agreements(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) > 0
        assert len(dupixent) > 0
        assert len(libtayo) > 0

    def test_vendor_has_multiple_services(self, svc: VendorQualificationService):
        for vid in ["VND-001", "VND-003", "VND-005"]:
            v = svc.get_vendor(vid)
            assert v is not None
            assert len(v.services_provided) >= 3

    def test_unacceptable_vendor_low_scores(self, svc: VendorQualificationService):
        assessment = svc.get_assessment("VA-013")
        assert assessment is not None
        assert assessment.rating == PerformanceRating.UNACCEPTABLE
        assert assessment.overall_score < 40


# =====================================================================
# ENUMERATION COVERAGE
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout the system."""

    @pytest.mark.anyio
    async def test_all_vendor_categories_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/vendors")
        data = resp.json()
        categories = {item["category"] for item in data["items"]}
        assert "cro" in categories
        assert "central_lab" in categories
        assert "irt_provider" in categories
        assert "edc_provider" in categories
        assert "packaging" in categories
        assert "logistics" in categories
        assert "imaging" in categories
        assert "bioanalytical_lab" in categories
        assert "safety_database" in categories
        assert "medical_writing" in categories

    @pytest.mark.anyio
    async def test_all_qualification_statuses_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/vendors")
        data = resp.json()
        statuses = {item["qualification_status"] for item in data["items"]}
        assert "qualified" in statuses
        assert "conditionally_qualified" in statuses
        assert "requalification_due" in statuses
        assert "disqualified" in statuses

    @pytest.mark.anyio
    async def test_all_risk_levels_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/vendors")
        data = resp.json()
        risks = {item["risk_level"] for item in data["items"]}
        assert "low" in risks
        assert "medium" in risks
        assert "high" in risks
        assert "critical" in risks

    @pytest.mark.anyio
    async def test_all_agreement_statuses_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "draft" in statuses
        assert "under_review" in statuses
        assert "executed" in statuses
        assert "expired" in statuses
        assert "terminated" in statuses

    @pytest.mark.anyio
    async def test_all_performance_ratings_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        data = resp.json()
        ratings = {item["rating"] for item in data["items"]}
        assert "excellent" in ratings
        assert "good" in ratings
        assert "acceptable" in ratings
        assert "below_expectations" in ratings
        assert "unacceptable" in ratings

    @pytest.mark.anyio
    async def test_all_risk_assessment_levels_present(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risk-assessments")
        data = resp.json()
        levels = {item["risk_level"] for item in data["items"]}
        assert "low" in levels
        assert "medium" in levels
        assert "high" in levels
        assert "critical" in levels


# =====================================================================
# CROSS-ENTITY RELATIONSHIPS
# =====================================================================


class TestCrossEntityRelationships:
    """Test relationships between vendors, agreements, assessments, and risk assessments."""

    def test_agreements_reference_valid_vendors(self, svc: VendorQualificationService):
        agreements = svc.list_agreements()
        vendor_ids = {v.id for v in svc.list_vendors()}
        for a in agreements:
            assert a.vendor_id in vendor_ids

    def test_assessments_reference_valid_vendors(self, svc: VendorQualificationService):
        assessments = svc.list_assessments()
        vendor_ids = {v.id for v in svc.list_vendors()}
        for a in assessments:
            assert a.vendor_id in vendor_ids

    def test_risk_assessments_reference_valid_vendors(self, svc: VendorQualificationService):
        risk_assessments = svc.list_risk_assessments()
        vendor_ids = {v.id for v in svc.list_vendors()}
        for r in risk_assessments:
            assert r.vendor_id in vendor_ids

    def test_covance_has_agreements(self, svc: VendorQualificationService):
        agreements = svc.list_agreements(vendor_id="VND-001")
        assert len(agreements) >= 2

    def test_covance_has_assessments(self, svc: VendorQualificationService):
        assessments = svc.list_assessments(vendor_id="VND-001")
        assert len(assessments) >= 2

    def test_q2_solutions_spans_all_trials(self, svc: VendorQualificationService):
        vendor = svc.get_vendor("VND-003")
        assert vendor is not None
        assert EYLEA_TRIAL in vendor.active_trials
        assert DUPIXENT_TRIAL in vendor.active_trials
        assert LIBTAYO_TRIAL in vendor.active_trials

    def test_disqualified_vendor_has_terminated_agreement(self, svc: VendorQualificationService):
        agreements = svc.list_agreements(vendor_id="VND-012")
        statuses = {a.status for a in agreements}
        assert AgreementStatus.TERMINATED in statuses

    def test_high_risk_vendor_has_risk_assessment(self, svc: VendorQualificationService):
        ra = svc.list_risk_assessments(vendor_id="VND-008")
        assert len(ra) > 0
        assert any(r.risk_level == RiskLevel.HIGH for r in ra)

    @pytest.mark.anyio
    async def test_vendor_filter_eylea_trial_count(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/vendors", params={"trial_id": EYLEA_TRIAL}
        )
        data = resp.json()
        assert data["total"] >= 5

    @pytest.mark.anyio
    async def test_vendor_filter_dupixent_trial_count(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/vendors", params={"trial_id": DUPIXENT_TRIAL}
        )
        data = resp.json()
        assert data["total"] >= 4

    @pytest.mark.anyio
    async def test_vendor_filter_libtayo_trial_count(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/vendors", params={"trial_id": LIBTAYO_TRIAL}
        )
        data = resp.json()
        assert data["total"] >= 4


# =====================================================================
# UPDATE OPERATIONS PRESERVE UNMODIFIED FIELDS
# =====================================================================


class TestUpdatePreservesFields:
    """Test that update operations preserve fields not included in the update."""

    @pytest.mark.anyio
    async def test_vendor_update_preserves_category(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/vendors/VND-001",
            json={"name": "Updated Name"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"
        assert data["category"] == "cro"
        assert data["country"] == "United States"

    @pytest.mark.anyio
    async def test_agreement_update_preserves_vendor(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/agreements/QA-001",
            json={"status": "expired"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "expired"
        assert data["vendor_id"] == "VND-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_vendor_update_services(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/vendors/VND-001",
            json={"services_provided": ["New service 1", "New service 2"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["services_provided"]) == 2
        assert "New service 1" in data["services_provided"]
