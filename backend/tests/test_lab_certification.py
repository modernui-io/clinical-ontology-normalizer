"""Tests for Lab Certification & Accreditation (CLINICAL-LC).

Covers:
- Seed data verification (labs, certifications, proficiency tests, qualifications, findings)
- Laboratory CRUD (create, read, update, delete, list, filter by type/active/country)
- Certification CRUD (create, read, update, delete, list, filter by lab/type/status)
- Proficiency test CRUD (create, read, update, delete, list, filter by lab/result/cycle)
- Qualification workflow (qualify, auto-qualify, prerequisite promotion, disqualify)
- Compliance finding lifecycle (open -> in_progress -> resolved -> verified)
- Expiring certification detection
- Metrics computation
- Error handling (404s, 400s, invalid operations)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.lab_certification import router as lab_certification_router
from app.schemas.lab_certification import (
    AccreditationBody,
    CertificationStatus,
    CertificationType,
    ComplianceFindingCreate,
    ComplianceFindingStatus,
    ComplianceFindingUpdate,
    FindingSeverity,
    FindingType,
    LabQualificationCreate,
    LabQualificationUpdate,
    LabType,
    ProficiencyResult,
    QualificationStatus,
)
from app.services.lab_certification_service import (
    LabCertificationService,
    get_lab_certification_service,
    reset_lab_certification_service,
)

# Build a lightweight test app with only our router registered
_test_app = FastAPI()
_test_app.include_router(lab_certification_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/lab-certification"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_lab_certification_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> LabCertificationService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=_test_app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lab_create(**overrides) -> dict:
    defaults = {
        "name": "Test Laboratory",
        "lab_type": "central",
        "address": "123 Test Lane, Boston, MA 02101",
        "country": "US",
        "contact_name": "Dr. Test User",
        "contact_email": "test@lab.com",
        "phone": "+1-555-0100",
        "capabilities": ["hematology", "chemistry"],
        "specializations": ["oncology"],
    }
    defaults.update(overrides)
    return defaults


def _make_cert_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "lab_id": "LAB-001",
        "certification_type": "clia",
        "accreditation_body": "clia",
        "certificate_number": "TEST-CERT-001",
        "issued_date": now.isoformat(),
        "expiry_date": (now + timedelta(days=365)).isoformat(),
        "scope": "Full clinical laboratory testing",
    }
    defaults.update(overrides)
    return defaults


def _make_proficiency_test_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "lab_id": "LAB-001",
        "test_name": "CAP Surveys - Chemistry",
        "analyte": "Glucose",
        "sample_id": "TEST-SAMPLE-001",
        "expected_value": 100.0,
        "reported_value": 99.5,
        "result": "satisfactory",
        "tested_date": now.isoformat(),
        "reported_date": now.isoformat(),
        "cycle": "2026-Q1",
    }
    defaults.update(overrides)
    return defaults


def _make_qualification_create(**overrides) -> dict:
    defaults = {
        "lab_id": "LAB-001",
        "trial_id": LIBTAYO_TRIAL,
        "assays_qualified": ["PD-L1 IHC", "Complete Blood Count"],
        "training_completed": True,
        "equipment_verified": True,
        "sop_reviewed": True,
        "qualified_by": "Dr. Test Reviewer",
        "notes": "Test qualification",
    }
    defaults.update(overrides)
    return defaults


def _make_finding_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "lab_id": "LAB-001",
        "certification_id": "CERT-001",
        "finding_type": "documentation",
        "severity": "minor",
        "description": "Test compliance finding for unit testing",
        "due_date": (now + timedelta(days=30)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_labs_count(self, svc: LabCertificationService):
        labs = svc.list_laboratories()
        assert len(labs) == 5

    def test_seed_labs_types(self, svc: LabCertificationService):
        labs = svc.list_laboratories()
        types = {lab.lab_type for lab in labs}
        assert LabType.CENTRAL in types
        assert LabType.REFERENCE in types
        assert LabType.BIOANALYTICAL in types
        assert LabType.LOCAL in types

    def test_seed_labs_active_inactive(self, svc: LabCertificationService):
        active = svc.list_laboratories(active=True)
        inactive = svc.list_laboratories(active=False)
        assert len(active) == 4
        assert len(inactive) == 1

    def test_seed_certifications_count(self, svc: LabCertificationService):
        certs = svc.list_certifications()
        assert len(certs) == 10

    def test_seed_certifications_statuses(self, svc: LabCertificationService):
        certs = svc.list_certifications()
        statuses = {c.status for c in certs}
        assert CertificationStatus.ACTIVE in statuses
        assert CertificationStatus.EXPIRED in statuses
        assert CertificationStatus.PENDING in statuses
        assert CertificationStatus.SUSPENDED in statuses

    def test_seed_proficiency_tests_count(self, svc: LabCertificationService):
        pts = svc.list_proficiency_tests()
        assert len(pts) == 7

    def test_seed_proficiency_test_results(self, svc: LabCertificationService):
        pts = svc.list_proficiency_tests()
        results = {pt.result for pt in pts}
        assert ProficiencyResult.SATISFACTORY in results
        assert ProficiencyResult.UNSATISFACTORY in results
        assert ProficiencyResult.PENDING in results

    def test_seed_qualifications_count(self, svc: LabCertificationService):
        quals = svc.list_qualifications()
        assert len(quals) == 4

    def test_seed_qualification_statuses(self, svc: LabCertificationService):
        quals = svc.list_qualifications()
        statuses = {q.qualification_status for q in quals}
        assert QualificationStatus.QUALIFIED in statuses
        assert QualificationStatus.CONDITIONALLY_QUALIFIED in statuses
        assert QualificationStatus.DISQUALIFIED in statuses

    def test_seed_compliance_findings_count(self, svc: LabCertificationService):
        findings = svc.list_compliance_findings()
        assert len(findings) == 6

    def test_seed_compliance_finding_severities(self, svc: LabCertificationService):
        findings = svc.list_compliance_findings()
        severities = {f.severity for f in findings}
        assert FindingSeverity.CRITICAL in severities
        assert FindingSeverity.MAJOR in severities
        assert FindingSeverity.MINOR in severities

    def test_seed_compliance_finding_statuses(self, svc: LabCertificationService):
        findings = svc.list_compliance_findings()
        statuses = {f.status for f in findings}
        assert ComplianceFindingStatus.OPEN in statuses
        assert ComplianceFindingStatus.VERIFIED in statuses
        assert ComplianceFindingStatus.OVERDUE in statuses


# =====================================================================
# LABORATORY CRUD
# =====================================================================


class TestLaboratoryCrud:
    """Test laboratory CRUD operations."""

    @pytest.mark.anyio
    async def test_list_labs(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 5

    @pytest.mark.anyio
    async def test_list_labs_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labs", params={"lab_type": "central"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["lab_type"] == "central"

    @pytest.mark.anyio
    async def test_list_labs_filter_active(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labs", params={"active": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["active"] is True

    @pytest.mark.anyio
    async def test_list_labs_filter_inactive(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labs", params={"active": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["active"] is False

    @pytest.mark.anyio
    async def test_list_labs_filter_country(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labs", params={"country": "US"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["country"] == "US"

    @pytest.mark.anyio
    async def test_get_lab(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labs/LAB-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "LAB-001"
        assert data["name"] == "Covance Central Laboratory"

    @pytest.mark.anyio
    async def test_get_lab_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labs/LAB-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_lab(self, client: AsyncClient):
        payload = _make_lab_create()
        resp = await client.post(f"{API_PREFIX}/labs", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Laboratory"
        assert data["lab_type"] == "central"
        assert data["id"].startswith("LAB-")
        assert data["active"] is True

    @pytest.mark.anyio
    async def test_create_lab_specialty(self, client: AsyncClient):
        payload = _make_lab_create(
            name="Specialty Genetics Lab",
            lab_type="specialty",
            country="GB",
        )
        resp = await client.post(f"{API_PREFIX}/labs", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["lab_type"] == "specialty"
        assert data["country"] == "GB"

    @pytest.mark.anyio
    async def test_update_lab(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/labs/LAB-001",
            json={"name": "Updated Lab Name", "active": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Lab Name"
        assert data["active"] is False

    @pytest.mark.anyio
    async def test_update_lab_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/labs/LAB-NONEXISTENT",
            json={"name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_lab(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/labs/LAB-005")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/labs/LAB-005")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_lab_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/labs/LAB-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_lab_has_capabilities(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labs/LAB-001")
        data = resp.json()
        assert "hematology" in data["capabilities"]
        assert "chemistry" in data["capabilities"]

    @pytest.mark.anyio
    async def test_lab_has_specializations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labs/LAB-001")
        data = resp.json()
        assert len(data["specializations"]) > 0


# =====================================================================
# CERTIFICATION CRUD
# =====================================================================


class TestCertificationCrud:
    """Test certification CRUD operations."""

    @pytest.mark.anyio
    async def test_list_certifications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/certifications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_certifications_filter_lab(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/certifications", params={"lab_id": "LAB-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["lab_id"] == "LAB-001"

    @pytest.mark.anyio
    async def test_list_certifications_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/certifications",
            params={"certification_type": "clia"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["certification_type"] == "clia"

    @pytest.mark.anyio
    async def test_list_certifications_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/certifications", params={"status": "active"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "active"

    @pytest.mark.anyio
    async def test_get_certification(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/certifications/CERT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CERT-001"
        assert data["lab_id"] == "LAB-001"

    @pytest.mark.anyio
    async def test_get_certification_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/certifications/CERT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_certification(self, client: AsyncClient):
        payload = _make_cert_create()
        resp = await client.post(f"{API_PREFIX}/certifications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["lab_id"] == "LAB-001"
        assert data["certification_type"] == "clia"
        assert data["id"].startswith("CERT-")

    @pytest.mark.anyio
    async def test_create_certification_invalid_lab(self, client: AsyncClient):
        payload = _make_cert_create(lab_id="LAB-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/certifications", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_certification(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/certifications/CERT-001",
            json={"status": "suspended", "findings_count": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "suspended"
        assert data["findings_count"] == 5

    @pytest.mark.anyio
    async def test_update_certification_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/certifications/CERT-NONEXISTENT",
            json={"status": "active"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_certification(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/certifications/CERT-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/certifications/CERT-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_certification_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/certifications/CERT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_certification_sorted_by_expiry(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/certifications")
        data = resp.json()
        expiry_dates = [item["expiry_date"] for item in data["items"]]
        assert expiry_dates == sorted(expiry_dates)


# =====================================================================
# PROFICIENCY TESTING
# =====================================================================


class TestProficiencyTesting:
    """Test proficiency test operations."""

    @pytest.mark.anyio
    async def test_list_proficiency_tests(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/proficiency-tests")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7

    @pytest.mark.anyio
    async def test_list_proficiency_tests_filter_lab(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/proficiency-tests", params={"lab_id": "LAB-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["lab_id"] == "LAB-001"

    @pytest.mark.anyio
    async def test_list_proficiency_tests_filter_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/proficiency-tests",
            params={"result": "unsatisfactory"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["result"] == "unsatisfactory"

    @pytest.mark.anyio
    async def test_list_proficiency_tests_filter_cycle(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/proficiency-tests", params={"cycle": "2026-Q1"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["cycle"] == "2026-Q1"

    @pytest.mark.anyio
    async def test_get_proficiency_test(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/proficiency-tests/PT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PT-001"
        assert data["analyte"] == "Hemoglobin A1c"

    @pytest.mark.anyio
    async def test_get_proficiency_test_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/proficiency-tests/PT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_record_proficiency_test(self, client: AsyncClient):
        payload = _make_proficiency_test_create()
        resp = await client.post(f"{API_PREFIX}/proficiency-tests", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["analyte"] == "Glucose"
        assert data["result"] == "satisfactory"
        assert data["id"].startswith("PT-")

    @pytest.mark.anyio
    async def test_record_proficiency_test_unsatisfactory(self, client: AsyncClient):
        payload = _make_proficiency_test_create(
            analyte="Potassium",
            expected_value=4.5,
            reported_value=6.2,
            result="unsatisfactory",
            notes="Significant deviation from expected",
        )
        resp = await client.post(f"{API_PREFIX}/proficiency-tests", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["result"] == "unsatisfactory"

    @pytest.mark.anyio
    async def test_record_proficiency_test_invalid_lab(self, client: AsyncClient):
        payload = _make_proficiency_test_create(lab_id="LAB-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/proficiency-tests", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_proficiency_test(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/proficiency-tests/PT-007",
            json={"result": "not_graded", "notes": "Grading deferred"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "not_graded"
        assert data["notes"] == "Grading deferred"

    @pytest.mark.anyio
    async def test_update_proficiency_test_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/proficiency-tests/PT-NONEXISTENT",
            json={"result": "satisfactory"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_proficiency_test(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/proficiency-tests/PT-007")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/proficiency-tests/PT-007")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_proficiency_test_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/proficiency-tests/PT-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# LAB QUALIFICATIONS
# =====================================================================


class TestLabQualifications:
    """Test lab qualification operations and workflow."""

    @pytest.mark.anyio
    async def test_list_qualifications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qualifications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4

    @pytest.mark.anyio
    async def test_list_qualifications_filter_lab(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/qualifications", params={"lab_id": "LAB-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["lab_id"] == "LAB-001"

    @pytest.mark.anyio
    async def test_list_qualifications_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/qualifications", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_qualifications_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/qualifications",
            params={"qualification_status": "qualified"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["qualification_status"] == "qualified"

    @pytest.mark.anyio
    async def test_get_qualification(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qualifications/QUAL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "QUAL-001"
        assert data["qualification_status"] == "qualified"

    @pytest.mark.anyio
    async def test_get_qualification_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qualifications/QUAL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_qualify_lab_all_prereqs_met(self, client: AsyncClient):
        """When all prerequisites are met, qualification should auto-qualify."""
        payload = _make_qualification_create()
        resp = await client.post(f"{API_PREFIX}/qualifications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["qualification_status"] == "qualified"
        assert data["qualified_date"] is not None

    @pytest.mark.anyio
    async def test_qualify_lab_prereqs_not_met(self, client: AsyncClient):
        """When prerequisites are not met, status should be pending."""
        payload = _make_qualification_create(
            training_completed=False,
            equipment_verified=True,
            sop_reviewed=False,
        )
        resp = await client.post(f"{API_PREFIX}/qualifications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["qualification_status"] == "pending"
        assert data["qualified_date"] is None

    @pytest.mark.anyio
    async def test_qualify_lab_invalid_lab(self, client: AsyncClient):
        payload = _make_qualification_create(lab_id="LAB-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/qualifications", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_qualification(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/qualifications/QUAL-003",
            json={"sop_reviewed": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sop_reviewed"] is True
        # Should auto-promote to qualified since all prereqs now met
        assert data["qualification_status"] == "qualified"
        assert data["qualified_date"] is not None

    @pytest.mark.anyio
    async def test_update_qualification_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/qualifications/QUAL-NONEXISTENT",
            json={"sop_reviewed": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_qualification_explicit_status(self, client: AsyncClient):
        """Explicitly setting a status should override auto-promotion."""
        resp = await client.put(
            f"{API_PREFIX}/qualifications/QUAL-003",
            json={
                "sop_reviewed": True,
                "qualification_status": "suspended",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["qualification_status"] == "suspended"

    @pytest.mark.anyio
    async def test_delete_qualification(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/qualifications/QUAL-004")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/qualifications/QUAL-004")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_qualification_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/qualifications/QUAL-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# QUALIFICATION WORKFLOW
# =====================================================================


class TestQualificationWorkflow:
    """Test the lab qualification workflow: pending -> qualified."""

    def test_auto_qualify_when_all_prereqs_met(
        self, svc: LabCertificationService
    ):
        qual = svc.qualify_lab_for_trial(
            LabQualificationCreate(
                lab_id="LAB-002",
                trial_id=LIBTAYO_TRIAL,
                assays_qualified=["CBC"],
                training_completed=True,
                equipment_verified=True,
                sop_reviewed=True,
                qualified_by="Dr. Test",
            )
        )
        assert qual.qualification_status == QualificationStatus.QUALIFIED
        assert qual.qualified_date is not None

    def test_pending_when_prereqs_incomplete(
        self, svc: LabCertificationService
    ):
        qual = svc.qualify_lab_for_trial(
            LabQualificationCreate(
                lab_id="LAB-002",
                trial_id=LIBTAYO_TRIAL,
                assays_qualified=["CBC"],
                training_completed=True,
                equipment_verified=False,
                sop_reviewed=True,
            )
        )
        assert qual.qualification_status == QualificationStatus.PENDING
        assert qual.qualified_date is None

    def test_auto_promote_on_update(self, svc: LabCertificationService):
        """Completing the last prerequisite should auto-promote to qualified."""
        qual = svc.get_qualification("QUAL-003")
        assert qual is not None
        assert qual.qualification_status == QualificationStatus.CONDITIONALLY_QUALIFIED
        assert qual.sop_reviewed is False

        updated = svc.update_qualification(
            "QUAL-003",
            LabQualificationUpdate(sop_reviewed=True),
        )
        assert updated is not None
        assert updated.qualification_status == QualificationStatus.QUALIFIED
        assert updated.qualified_date is not None

    def test_no_auto_promote_when_explicit_status_set(
        self, svc: LabCertificationService
    ):
        updated = svc.update_qualification(
            "QUAL-003",
            LabQualificationUpdate(
                sop_reviewed=True,
                qualification_status=QualificationStatus.SUSPENDED,
            ),
        )
        assert updated is not None
        assert updated.qualification_status == QualificationStatus.SUSPENDED

    def test_disqualified_lab_details(self, svc: LabCertificationService):
        qual = svc.get_qualification("QUAL-004")
        assert qual is not None
        assert qual.qualification_status == QualificationStatus.DISQUALIFIED
        assert qual.training_completed is False
        assert qual.equipment_verified is False


# =====================================================================
# COMPLIANCE FINDINGS
# =====================================================================


class TestComplianceFindings:
    """Test compliance finding operations."""

    @pytest.mark.anyio
    async def test_list_findings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-findings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    @pytest.mark.anyio
    async def test_list_findings_filter_lab(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compliance-findings", params={"lab_id": "LAB-005"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["lab_id"] == "LAB-005"

    @pytest.mark.anyio
    async def test_list_findings_filter_severity(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compliance-findings", params={"severity": "critical"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["severity"] == "critical"

    @pytest.mark.anyio
    async def test_list_findings_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compliance-findings", params={"status": "open"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "open"

    @pytest.mark.anyio
    async def test_list_findings_filter_certification(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compliance-findings",
            params={"certification_id": "CERT-010"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["certification_id"] == "CERT-010"

    @pytest.mark.anyio
    async def test_get_finding(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-findings/CF-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CF-001"

    @pytest.mark.anyio
    async def test_get_finding_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-findings/CF-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_log_compliance_finding(self, client: AsyncClient):
        payload = _make_finding_create()
        resp = await client.post(f"{API_PREFIX}/compliance-findings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["lab_id"] == "LAB-001"
        assert data["finding_type"] == "documentation"
        assert data["severity"] == "minor"
        assert data["status"] == "open"
        assert data["id"].startswith("CF-")

    @pytest.mark.anyio
    async def test_log_finding_invalid_lab(self, client: AsyncClient):
        payload = _make_finding_create(lab_id="LAB-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/compliance-findings", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_log_finding_invalid_certification(self, client: AsyncClient):
        payload = _make_finding_create(certification_id="CERT-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/compliance-findings", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_log_finding_no_certification(self, client: AsyncClient):
        """Logging a finding without a certification_id should succeed."""
        payload = _make_finding_create(certification_id=None)
        resp = await client.post(f"{API_PREFIX}/compliance-findings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["certification_id"] is None

    @pytest.mark.anyio
    async def test_update_finding(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/compliance-findings/CF-003",
            json={
                "status": "in_progress",
                "corrective_action": "Pipettes sent for calibration",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["corrective_action"] == "Pipettes sent for calibration"

    @pytest.mark.anyio
    async def test_update_finding_resolve_auto_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/compliance-findings/CF-003",
            json={"status": "resolved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "resolved"
        assert data["resolved_date"] is not None

    @pytest.mark.anyio
    async def test_update_finding_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/compliance-findings/CF-NONEXISTENT",
            json={"status": "resolved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_finding(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/compliance-findings/CF-006")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/compliance-findings/CF-006")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_finding_not_found(self, client: AsyncClient):
        resp = await client.delete(
            f"{API_PREFIX}/compliance-findings/CF-NONEXISTENT"
        )
        assert resp.status_code == 404


# =====================================================================
# COMPLIANCE FINDING LIFECYCLE
# =====================================================================


class TestFindingLifecycle:
    """Test finding lifecycle: open -> in_progress -> resolved -> verified."""

    def test_finding_lifecycle_transitions(
        self, svc: LabCertificationService
    ):
        # Start: open
        finding = svc.get_compliance_finding("CF-003")
        assert finding is not None
        assert finding.status == ComplianceFindingStatus.OPEN

        # Transition to in_progress
        updated = svc.update_compliance_finding(
            "CF-003",
            ComplianceFindingUpdate(status=ComplianceFindingStatus.IN_PROGRESS),
        )
        assert updated is not None
        assert updated.status == ComplianceFindingStatus.IN_PROGRESS

        # Transition to resolved
        updated = svc.update_compliance_finding(
            "CF-003",
            ComplianceFindingUpdate(status=ComplianceFindingStatus.RESOLVED),
        )
        assert updated is not None
        assert updated.status == ComplianceFindingStatus.RESOLVED
        assert updated.resolved_date is not None

        # Transition to verified
        updated = svc.update_compliance_finding(
            "CF-003",
            ComplianceFindingUpdate(status=ComplianceFindingStatus.VERIFIED),
        )
        assert updated is not None
        assert updated.status == ComplianceFindingStatus.VERIFIED

    def test_resolved_finding_keeps_date(self, svc: LabCertificationService):
        # CF-001 is already verified with a resolved_date
        finding = svc.get_compliance_finding("CF-001")
        assert finding is not None
        assert finding.resolved_date is not None
        original_date = finding.resolved_date

        # Updating description should not change resolved_date
        updated = svc.update_compliance_finding(
            "CF-001",
            ComplianceFindingUpdate(description="Updated description"),
        )
        assert updated is not None
        assert updated.resolved_date == original_date

    def test_log_finding_increments_cert_counters(
        self, svc: LabCertificationService
    ):
        cert_before = svc.get_certification("CERT-001")
        assert cert_before is not None
        count_before = cert_before.findings_count
        capa_before = cert_before.corrective_actions_pending

        svc.log_compliance_finding(
            ComplianceFindingCreate(
                lab_id="LAB-001",
                certification_id="CERT-001",
                finding_type=FindingType.EQUIPMENT,
                severity=FindingSeverity.MINOR,
                description="Test finding to check counter increment",
                due_date=datetime.now(timezone.utc) + timedelta(days=30),
            )
        )

        cert_after = svc.get_certification("CERT-001")
        assert cert_after is not None
        assert cert_after.findings_count == count_before + 1
        assert cert_after.corrective_actions_pending == capa_before + 1


# =====================================================================
# EXPIRING CERTIFICATIONS
# =====================================================================


class TestExpiringCertifications:
    """Test expiring certification detection."""

    @pytest.mark.anyio
    async def test_get_expiring_default_90_days(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/expiring")
        assert resp.status_code == 200
        data = resp.json()
        # CERT-002 expires in 65 days, should be caught
        assert data["total"] >= 1
        cert_ids = [c["id"] for c in data["items"]]
        assert "CERT-002" in cert_ids

    @pytest.mark.anyio
    async def test_get_expiring_custom_days(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/expiring", params={"days": 30})
        assert resp.status_code == 200
        data = resp.json()
        # Only certs expiring within 30 days should appear
        # CERT-002 expires in 65 days, should NOT be here
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=30)
        for item in data["items"]:
            expiry = datetime.fromisoformat(item["expiry_date"])
            assert expiry <= cutoff

    @pytest.mark.anyio
    async def test_expiring_excludes_already_expired(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/expiring", params={"days": 365})
        assert resp.status_code == 200
        data = resp.json()
        cert_ids = [c["id"] for c in data["items"]]
        # CERT-007 is expired, CERT-010 is suspended - neither should appear
        assert "CERT-007" not in cert_ids
        assert "CERT-010" not in cert_ids

    @pytest.mark.anyio
    async def test_expiring_sorted_by_expiry_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/expiring")
        data = resp.json()
        if data["total"] > 1:
            dates = [item["expiry_date"] for item in data["items"]]
            assert dates == sorted(dates)

    def test_expiring_service_method(self, svc: LabCertificationService):
        expiring = svc.get_expiring_certifications(days=365)
        for cert in expiring:
            assert cert.status in (
                CertificationStatus.ACTIVE,
                CertificationStatus.PENDING,
            )


# =====================================================================
# METRICS
# =====================================================================


class TestLabMetrics:
    """Test lab certification metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_labs"] == 5
        assert data["active_labs"] == 4
        assert data["total_certifications"] == 10
        assert data["active_certifications"] >= 1
        assert data["total_proficiency_tests"] == 7
        assert data["total_qualifications"] == 4
        assert data["total_compliance_findings"] == 6

    def test_metrics_labs_by_type(self, svc: LabCertificationService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.labs_by_type.values())
        assert total_by_type == metrics.total_labs

    def test_metrics_certifications_by_status(
        self, svc: LabCertificationService
    ):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.certifications_by_status.values())
        assert total_by_status == metrics.total_certifications

    def test_metrics_satisfactory_rate(self, svc: LabCertificationService):
        metrics = svc.get_metrics()
        # 5 satisfactory out of 6 graded (1 unsatisfactory, 1 pending = ungraded)
        assert 0 <= metrics.satisfactory_rate <= 100
        assert metrics.satisfactory_rate > 0

    def test_metrics_qualified_count(self, svc: LabCertificationService):
        metrics = svc.get_metrics()
        assert metrics.qualified_count == 2  # QUAL-001 and QUAL-002

    def test_metrics_open_findings(self, svc: LabCertificationService):
        metrics = svc.get_metrics()
        assert metrics.open_findings >= 2  # CF-003 and CF-004 at least

    def test_metrics_overdue_findings(self, svc: LabCertificationService):
        metrics = svc.get_metrics()
        assert metrics.overdue_findings >= 2  # CF-005 and CF-006 are overdue

    def test_metrics_critical_findings(self, svc: LabCertificationService):
        metrics = svc.get_metrics()
        assert metrics.critical_findings >= 1  # CF-004, CF-005

    def test_metrics_expiring_soon(self, svc: LabCertificationService):
        metrics = svc.get_metrics()
        assert metrics.expiring_soon >= 1  # CERT-002 at least

    def test_metrics_expired_certifications(
        self, svc: LabCertificationService
    ):
        metrics = svc.get_metrics()
        assert metrics.expired_certifications >= 1  # CERT-007


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_lab_certification_service()
        svc2 = get_lab_certification_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_lab_certification_service()
        svc2 = reset_lab_certification_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_lab_certification_service()
        # Delete a lab
        svc.delete_laboratory("LAB-001")
        assert svc.get_laboratory("LAB-001") is None
        # Reset should bring it back
        svc2 = reset_lab_certification_service()
        assert svc2.get_laboratory("LAB-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_labs_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labs")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_certifications_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/certifications")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_proficiency_tests_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/proficiency-tests")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_qualifications_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qualifications")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_findings_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compliance-findings")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_lab_with_all_fields(self, client: AsyncClient):
        payload = _make_lab_create(
            name="Full Lab",
            lab_type="bioanalytical",
            address="456 Full St, NYC",
            country="US",
            contact_name="Dr. Full",
            contact_email="full@lab.com",
            phone="+1-555-0200",
            capabilities=["pharmacokinetic", "biomarker"],
            specializations=["rare diseases", "gene therapy"],
        )
        resp = await client.post(f"{API_PREFIX}/labs", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_create_cert_with_iso_type(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = _make_cert_create(
            certification_type="iso_15189",
            accreditation_body="ukas",
            certificate_number="UKAS-ISO-TEST",
            scope="ISO 15189 accreditation for medical laboratories",
            expiry_date=(now + timedelta(days=730)).isoformat(),
        )
        resp = await client.post(f"{API_PREFIX}/certifications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["certification_type"] == "iso_15189"
        assert data["accreditation_body"] == "ukas"

    @pytest.mark.anyio
    async def test_update_lab_capabilities(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/labs/LAB-003",
            json={"capabilities": ["pharmacokinetic", "biomarker", "genomics"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "genomics" in data["capabilities"]

    @pytest.mark.anyio
    async def test_create_finding_critical_severity(self, client: AsyncClient):
        payload = _make_finding_create(
            severity="critical",
            finding_type="data_integrity",
            description="Critical data integrity issue found during audit",
        )
        resp = await client.post(f"{API_PREFIX}/compliance-findings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["severity"] == "critical"
        assert data["finding_type"] == "data_integrity"

    @pytest.mark.anyio
    async def test_labs_sorted_by_name(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/labs")
        data = resp.json()
        names = [item["name"] for item in data["items"]]
        assert names == sorted(names)

    @pytest.mark.anyio
    async def test_proficiency_tests_sorted_by_date_desc(
        self, client: AsyncClient
    ):
        resp = await client.get(f"{API_PREFIX}/proficiency-tests")
        data = resp.json()
        dates = [item["tested_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)


# =====================================================================
# ENUM COVERAGE
# =====================================================================


class TestEnumCoverage:
    """Test that all key enum values are represented in seed data."""

    @pytest.mark.anyio
    async def test_all_lab_types_queryable(self, client: AsyncClient):
        for lab_type in ["central", "local", "specialty", "reference", "bioanalytical"]:
            resp = await client.get(
                f"{API_PREFIX}/labs", params={"lab_type": lab_type}
            )
            assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_all_cert_types_queryable(self, client: AsyncClient):
        for cert_type in [
            "clia", "cap", "iso_15189", "gcp_compliant", "gmp_compliant",
            "state_license",
        ]:
            resp = await client.get(
                f"{API_PREFIX}/certifications",
                params={"certification_type": cert_type},
            )
            assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_all_cert_statuses_queryable(self, client: AsyncClient):
        for status in ["active", "pending", "expired", "suspended", "revoked"]:
            resp = await client.get(
                f"{API_PREFIX}/certifications", params={"status": status}
            )
            assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_all_proficiency_results_queryable(self, client: AsyncClient):
        for result in ["satisfactory", "unsatisfactory", "not_graded", "pending"]:
            resp = await client.get(
                f"{API_PREFIX}/proficiency-tests", params={"result": result}
            )
            assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_all_finding_severities_queryable(self, client: AsyncClient):
        for severity in ["critical", "major", "minor", "observation"]:
            resp = await client.get(
                f"{API_PREFIX}/compliance-findings",
                params={"severity": severity},
            )
            assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_all_finding_statuses_queryable(self, client: AsyncClient):
        for status in [
            "open", "in_progress", "resolved", "verified", "overdue",
        ]:
            resp = await client.get(
                f"{API_PREFIX}/compliance-findings", params={"status": status}
            )
            assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_all_qualification_statuses_queryable(
        self, client: AsyncClient
    ):
        for status in [
            "pending", "qualified", "conditionally_qualified",
            "disqualified", "suspended",
        ]:
            resp = await client.get(
                f"{API_PREFIX}/qualifications",
                params={"qualification_status": status},
            )
            assert resp.status_code == 200


# =====================================================================
# CERTIFICATION TYPES IN SEED DATA
# =====================================================================


class TestCertificationTypes:
    """Test that seed data covers different certification and accreditation types."""

    @pytest.mark.anyio
    async def test_clia_certifications_present(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/certifications",
            params={"certification_type": "clia"},
        )
        data = resp.json()
        assert data["total"] >= 3

    @pytest.mark.anyio
    async def test_cap_certifications_present(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/certifications",
            params={"certification_type": "cap"},
        )
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_iso_15189_certifications_present(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/certifications",
            params={"certification_type": "iso_15189"},
        )
        data = resp.json()
        assert data["total"] >= 2

    @pytest.mark.anyio
    async def test_gcp_compliant_present(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/certifications",
            params={"certification_type": "gcp_compliant"},
        )
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_gmp_compliant_present(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/certifications",
            params={"certification_type": "gmp_compliant"},
        )
        data = resp.json()
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_state_license_present(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/certifications",
            params={"certification_type": "state_license"},
        )
        data = resp.json()
        assert data["total"] >= 1


# =====================================================================
# CROSS-ENTITY RELATIONSHIPS
# =====================================================================


class TestCrossEntityRelationships:
    """Test relationships between labs, certs, qualifications, and findings."""

    @pytest.mark.anyio
    async def test_lab_certifications_match(self, client: AsyncClient):
        """Certifications filtered by lab should match existing labs."""
        resp = await client.get(
            f"{API_PREFIX}/certifications", params={"lab_id": "LAB-001"}
        )
        data = resp.json()
        assert data["total"] == 3  # CERT-001, CERT-002, CERT-003

    @pytest.mark.anyio
    async def test_lab_qualifications_match(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/qualifications", params={"lab_id": "LAB-001"}
        )
        data = resp.json()
        assert data["total"] == 1  # QUAL-001

    @pytest.mark.anyio
    async def test_lab_findings_match(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compliance-findings", params={"lab_id": "LAB-001"}
        )
        data = resp.json()
        assert data["total"] == 2  # CF-001, CF-002

    @pytest.mark.anyio
    async def test_certification_findings_match(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compliance-findings",
            params={"certification_id": "CERT-002"},
        )
        data = resp.json()
        assert data["total"] == 2  # CF-001, CF-002

    @pytest.mark.anyio
    async def test_trial_qualifications_match(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/qualifications", params={"trial_id": EYLEA_TRIAL}
        )
        data = resp.json()
        assert data["total"] == 2  # QUAL-001, QUAL-004

    def test_proficiency_tests_for_lab(self, svc: LabCertificationService):
        pts = svc.list_proficiency_tests(lab_id="LAB-002")
        assert len(pts) == 2
        for pt in pts:
            assert pt.lab_id == "LAB-002"

    def test_inactive_lab_can_have_findings(
        self, svc: LabCertificationService
    ):
        """LAB-005 is inactive but still has compliance findings."""
        lab = svc.get_laboratory("LAB-005")
        assert lab is not None
        assert lab.active is False
        findings = svc.list_compliance_findings(lab_id="LAB-005")
        assert len(findings) == 2
