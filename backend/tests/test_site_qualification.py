"""Tests for Site Qualification Management (SITE-QUAL).

Covers:
- Seed data verification (capability assessments, equipment, credentials, audits, qualifications)
- Capability assessment CRUD (create, read, update, delete, list, filter by trial/site/category)
- Equipment verification CRUD (create, read, update, delete, list, filter by trial/site/status)
- Staff credential CRUD (create, read, update, delete, list, filter by trial/site/type)
- Infrastructure audit CRUD (create, read, update, delete, list, filter by trial/site/rating)
- Qualification record CRUD (create, read, update, delete, list, filter by trial/site/status)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.site_qualification import (
    AssessmentCategory,
    AuditRating,
    CredentialType,
    EquipmentStatus,
    QualificationStatus,
)
from app.services.site_qualification_service import (
    SiteQualificationService,
    get_site_qualification_service,
    reset_site_qualification_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/site-qualification"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_site_qualification_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> SiteQualificationService:
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


def _make_capability_assessment_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-NEW",
        "category": "therapeutic_experience",
        "assessor": "Dr. Test Assessor",
        "score": 80.0,
        "pass_threshold": 70.0,
    }
    defaults.update(overrides)
    return defaults


def _make_equipment_verification_create(**overrides) -> dict:
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "site_id": "SITE-NEW",
        "equipment_name": "Test Centrifuge",
        "equipment_type": "Laboratory",
        "verified_by": "Tech. Test Verifier",
        "status": "operational",
    }
    defaults.update(overrides)
    return defaults


def _make_staff_credential_create(**overrides) -> dict:
    defaults = {
        "trial_id": LIBTAYO_TRIAL,
        "site_id": "SITE-NEW",
        "staff_name": "Dr. Test Doctor",
        "role": "Sub-Investigator",
        "credential_type": "medical_license",
        "issuing_authority": "Test Medical Board",
        "managed_by": "Dr. Test Manager",
    }
    defaults.update(overrides)
    return defaults


def _make_infrastructure_audit_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-NEW",
        "auditor": "Test Auditor, CQA",
        "audit_type": "pre_study",
        "rating": "satisfactory",
    }
    defaults.update(overrides)
    return defaults


def _make_qualification_record_create(**overrides) -> dict:
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "site_id": "SITE-NEW",
        "risk_tier": "medium",
        "conditions": ["Complete staff training"],
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_capability_assessments_count(self, svc: SiteQualificationService):
        assessments = svc.list_capability_assessments()
        assert len(assessments) == 12

    def test_seed_equipment_verifications_count(self, svc: SiteQualificationService):
        equipment = svc.list_equipment_verifications()
        assert len(equipment) == 12

    def test_seed_staff_credentials_count(self, svc: SiteQualificationService):
        credentials = svc.list_staff_credentials()
        assert len(credentials) == 12

    def test_seed_infrastructure_audits_count(self, svc: SiteQualificationService):
        audits = svc.list_infrastructure_audits()
        assert len(audits) == 12

    def test_seed_qualification_records_count(self, svc: SiteQualificationService):
        records = svc.list_qualification_records()
        assert len(records) == 12

    def test_seed_assessments_cover_all_trials(self, svc: SiteQualificationService):
        assessments = svc.list_capability_assessments()
        trial_ids = {a.trial_id for a in assessments}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_assessments_have_multiple_categories(self, svc: SiteQualificationService):
        assessments = svc.list_capability_assessments()
        categories = {a.category for a in assessments}
        assert len(categories) >= 4

    def test_seed_equipment_has_multiple_statuses(self, svc: SiteQualificationService):
        equipment = svc.list_equipment_verifications()
        statuses = {e.status for e in equipment}
        assert EquipmentStatus.OPERATIONAL in statuses
        assert EquipmentStatus.NEEDS_CALIBRATION in statuses
        assert EquipmentStatus.OUT_OF_SERVICE in statuses

    def test_seed_credentials_have_multiple_types(self, svc: SiteQualificationService):
        credentials = svc.list_staff_credentials()
        types = {c.credential_type for c in credentials}
        assert CredentialType.MEDICAL_LICENSE in types
        assert CredentialType.GCP_CERTIFICATION in types

    def test_seed_audits_have_multiple_ratings(self, svc: SiteQualificationService):
        audits = svc.list_infrastructure_audits()
        ratings = {a.rating for a in audits}
        assert AuditRating.EXCELLENT in ratings
        assert AuditRating.UNSATISFACTORY in ratings

    def test_seed_qualifications_have_multiple_statuses(self, svc: SiteQualificationService):
        records = svc.list_qualification_records()
        statuses = {r.qualification_status for r in records}
        assert QualificationStatus.QUALIFIED in statuses
        assert QualificationStatus.NOT_QUALIFIED in statuses
        assert QualificationStatus.PENDING_ASSESSMENT in statuses

    def test_seed_has_failed_assessments(self, svc: SiteQualificationService):
        assessments = svc.list_capability_assessments()
        failed = [a for a in assessments if not a.passed]
        assert len(failed) >= 2

    def test_seed_has_expired_credentials(self, svc: SiteQualificationService):
        credentials = svc.list_staff_credentials()
        expired = [c for c in credentials if not c.is_current]
        assert len(expired) >= 2


# =====================================================================
# CAPABILITY ASSESSMENT CRUD
# =====================================================================


class TestCapabilityAssessmentCrud:
    """Test capability assessment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_capability_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capability-assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_capability_assessments_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/capability-assessments", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_capability_assessments_filter_site(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/capability-assessments", params={"site_id": "SITE-101"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_capability_assessments_filter_category(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/capability-assessments",
            params={"category": "therapeutic_experience"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["category"] == "therapeutic_experience"

    @pytest.mark.anyio
    async def test_get_capability_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capability-assessments/CA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CA-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["category"] == "therapeutic_experience"

    @pytest.mark.anyio
    async def test_get_capability_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capability-assessments/CA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_capability_assessment(self, client: AsyncClient):
        payload = _make_capability_assessment_create()
        resp = await client.post(f"{API_PREFIX}/capability-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["category"] == "therapeutic_experience"
        assert data["passed"] is True  # score 80 >= threshold 70
        assert data["id"].startswith("CA-")

    @pytest.mark.anyio
    async def test_create_capability_assessment_fails(self, client: AsyncClient):
        payload = _make_capability_assessment_create(score=50.0, pass_threshold=70.0)
        resp = await client.post(f"{API_PREFIX}/capability-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["passed"] is False

    @pytest.mark.anyio
    async def test_update_capability_assessment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/capability-assessments/CA-005",
            json={"score": 75.0, "passed": True, "notes": "Remediation completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] == 75.0
        assert data["passed"] is True
        assert data["notes"] == "Remediation completed"

    @pytest.mark.anyio
    async def test_update_capability_assessment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/capability-assessments/CA-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_capability_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/capability-assessments/CA-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/capability-assessments/CA-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_capability_assessment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/capability-assessments/CA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# EQUIPMENT VERIFICATION CRUD
# =====================================================================


class TestEquipmentVerificationCrud:
    """Test equipment verification CRUD operations."""

    @pytest.mark.anyio
    async def test_list_equipment_verifications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/equipment-verifications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_equipment_verifications_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/equipment-verifications", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_equipment_verifications_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/equipment-verifications", params={"status": "operational"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "operational"

    @pytest.mark.anyio
    async def test_get_equipment_verification(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/equipment-verifications/EV-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "EV-001"
        assert data["equipment_name"] == "Heidelberg Spectralis OCT"

    @pytest.mark.anyio
    async def test_get_equipment_verification_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/equipment-verifications/EV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_equipment_verification(self, client: AsyncClient):
        payload = _make_equipment_verification_create()
        resp = await client.post(f"{API_PREFIX}/equipment-verifications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["equipment_name"] == "Test Centrifuge"
        assert data["status"] == "operational"
        assert data["id"].startswith("EV-")

    @pytest.mark.anyio
    async def test_update_equipment_verification(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/equipment-verifications/EV-003",
            json={"status": "operational", "meets_protocol_requirements": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "operational"
        assert data["meets_protocol_requirements"] is True

    @pytest.mark.anyio
    async def test_update_equipment_verification_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/equipment-verifications/EV-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_equipment_verification(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/equipment-verifications/EV-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/equipment-verifications/EV-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_equipment_verification_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/equipment-verifications/EV-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# STAFF CREDENTIAL CRUD
# =====================================================================


class TestStaffCredentialCrud:
    """Test staff credential CRUD operations."""

    @pytest.mark.anyio
    async def test_list_staff_credentials(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/staff-credentials")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_staff_credentials_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/staff-credentials", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_staff_credentials_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/staff-credentials", params={"credential_type": "medical_license"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["credential_type"] == "medical_license"

    @pytest.mark.anyio
    async def test_get_staff_credential(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/staff-credentials/SC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SC-001"
        assert data["staff_name"] == "Dr. Jonathan Blake"

    @pytest.mark.anyio
    async def test_get_staff_credential_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/staff-credentials/SC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_staff_credential(self, client: AsyncClient):
        payload = _make_staff_credential_create()
        resp = await client.post(f"{API_PREFIX}/staff-credentials", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["staff_name"] == "Dr. Test Doctor"
        assert data["credential_type"] == "medical_license"
        assert data["verified"] is False
        assert data["id"].startswith("SC-")

    @pytest.mark.anyio
    async def test_update_staff_credential(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/staff-credentials/SC-010",
            json={"verified": True, "verified_by": "Compliance Team", "cv_on_file": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["verified"] is True
        assert data["verified_by"] == "Compliance Team"
        assert data["cv_on_file"] is True

    @pytest.mark.anyio
    async def test_update_staff_credential_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/staff-credentials/SC-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_staff_credential(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/staff-credentials/SC-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/staff-credentials/SC-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_staff_credential_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/staff-credentials/SC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# INFRASTRUCTURE AUDIT CRUD
# =====================================================================


class TestInfrastructureAuditCrud:
    """Test infrastructure audit CRUD operations."""

    @pytest.mark.anyio
    async def test_list_infrastructure_audits(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/infrastructure-audits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_infrastructure_audits_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/infrastructure-audits", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_infrastructure_audits_filter_rating(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/infrastructure-audits", params={"rating": "excellent"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["rating"] == "excellent"

    @pytest.mark.anyio
    async def test_get_infrastructure_audit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/infrastructure-audits/IA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "IA-001"
        assert data["rating"] == "excellent"

    @pytest.mark.anyio
    async def test_get_infrastructure_audit_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/infrastructure-audits/IA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_infrastructure_audit(self, client: AsyncClient):
        payload = _make_infrastructure_audit_create()
        resp = await client.post(f"{API_PREFIX}/infrastructure-audits", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["audit_type"] == "pre_study"
        assert data["rating"] == "satisfactory"
        assert data["id"].startswith("IA-")

    @pytest.mark.anyio
    async def test_update_infrastructure_audit(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/infrastructure-audits/IA-009",
            json={"rating": "satisfactory", "corrective_actions_completed": 3, "notes": "All items resolved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rating"] == "satisfactory"
        assert data["corrective_actions_completed"] == 3
        assert data["notes"] == "All items resolved"

    @pytest.mark.anyio
    async def test_update_infrastructure_audit_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/infrastructure-audits/IA-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_infrastructure_audit(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/infrastructure-audits/IA-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/infrastructure-audits/IA-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_infrastructure_audit_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/infrastructure-audits/IA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# QUALIFICATION RECORD CRUD
# =====================================================================


class TestQualificationRecordCrud:
    """Test qualification record CRUD operations."""

    @pytest.mark.anyio
    async def test_list_qualification_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qualification-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_qualification_records_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/qualification-records", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_qualification_records_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/qualification-records",
            params={"qualification_status": "qualified"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["qualification_status"] == "qualified"

    @pytest.mark.anyio
    async def test_get_qualification_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qualification-records/QR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "QR-001"
        assert data["qualification_status"] == "qualified"

    @pytest.mark.anyio
    async def test_get_qualification_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qualification-records/QR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_qualification_record(self, client: AsyncClient):
        payload = _make_qualification_record_create()
        resp = await client.post(f"{API_PREFIX}/qualification-records", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["qualification_status"] == "pending_assessment"
        assert data["conditions"] == ["Complete staff training"]
        assert data["id"].startswith("QR-")

    @pytest.mark.anyio
    async def test_update_qualification_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/qualification-records/QR-009",
            json={
                "qualification_status": "in_assessment",
                "overall_score": 65.0,
                "notes": "Assessment started",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["qualification_status"] == "in_assessment"
        assert data["overall_score"] == 65.0
        assert data["notes"] == "Assessment started"

    @pytest.mark.anyio
    async def test_update_qualification_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/qualification-records/QR-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_qualification_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/qualification-records/QR-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/qualification-records/QR-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_qualification_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/qualification-records/QR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestSiteQualificationMetrics:
    """Test site qualification metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_assessments"] == 12
        assert data["total_equipment"] == 12
        assert data["total_credentials"] == 12
        assert data["total_audits"] == 12
        assert data["total_qualifications"] == 12

    @pytest.mark.anyio
    async def test_metrics_assessments_by_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_category = data["assessments_by_category"]
        total = sum(by_category.values())
        assert total == data["total_assessments"]

    @pytest.mark.anyio
    async def test_metrics_equipment_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["equipment_by_status"]
        total = sum(by_status.values())
        assert total == data["total_equipment"]

    @pytest.mark.anyio
    async def test_metrics_credentials_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_type = data["credentials_by_type"]
        total = sum(by_type.values())
        assert total == data["total_credentials"]

    @pytest.mark.anyio
    async def test_metrics_expired_credentials(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["expired_credentials"] >= 2

    @pytest.mark.anyio
    async def test_metrics_audits_by_rating(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_rating = data["audits_by_rating"]
        total = sum(by_rating.values())
        assert total == data["total_audits"]

    @pytest.mark.anyio
    async def test_metrics_qualifications_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["qualifications_by_status"]
        total = sum(by_status.values())
        assert total == data["total_qualifications"]

    @pytest.mark.anyio
    async def test_metrics_sites_qualified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["sites_qualified"] >= 1
        assert data["sites_qualified"] <= data["total_qualifications"]

    @pytest.mark.anyio
    async def test_metrics_avg_assessment_score(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert isinstance(data["avg_assessment_score"], float)
        assert data["avg_assessment_score"] > 0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_site_qualification_service()
        svc2 = get_site_qualification_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_site_qualification_service()
        svc2 = reset_site_qualification_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_site_qualification_service()
        # Delete an assessment
        svc.delete_capability_assessment("CA-001")
        assert svc.get_capability_assessment("CA-001") is None
        # Reset should bring it back
        svc2 = reset_site_qualification_service()
        assert svc2.get_capability_assessment("CA-001") is not None


# =====================================================================
# FILTERING AND EDGE CASES
# =====================================================================


class TestFilteringAndEdgeCases:
    """Test filtering combinations and edge cases."""

    @pytest.mark.anyio
    async def test_list_assessments_empty_filter(self, client: AsyncClient):
        """Filter by a trial that has no assessments."""
        resp = await client.get(
            f"{API_PREFIX}/capability-assessments",
            params={"trial_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_list_equipment_empty_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/equipment-verifications",
            params={"status": "decommissioned", "trial_id": DUPIXENT_TRIAL},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_qualifications_filter_site(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/qualification-records", params={"site_id": "SITE-101"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_create_assessment_then_retrieve(self, client: AsyncClient):
        """Create an assessment and verify it shows in the list."""
        payload = _make_capability_assessment_create()
        resp = await client.post(f"{API_PREFIX}/capability-assessments", json=payload)
        assert resp.status_code == 201
        created_id = resp.json()["id"]

        resp2 = await client.get(f"{API_PREFIX}/capability-assessments/{created_id}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == created_id

    @pytest.mark.anyio
    async def test_create_record_then_update_status(self, client: AsyncClient):
        """Create a qualification record and advance through lifecycle."""
        payload = _make_qualification_record_create()
        resp = await client.post(f"{API_PREFIX}/qualification-records", json=payload)
        assert resp.status_code == 201
        record_id = resp.json()["id"]
        assert resp.json()["qualification_status"] == "pending_assessment"

        # Update to in_assessment
        resp2 = await client.put(
            f"{API_PREFIX}/qualification-records/{record_id}",
            json={"qualification_status": "in_assessment"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["qualification_status"] == "in_assessment"

        # Update to qualified
        resp3 = await client.put(
            f"{API_PREFIX}/qualification-records/{record_id}",
            json={
                "qualification_status": "qualified",
                "overall_score": 85.0,
                "approved_by": "Dr. Board Chair",
            },
        )
        assert resp3.status_code == 200
        assert resp3.json()["qualification_status"] == "qualified"
        assert resp3.json()["approved_by"] == "Dr. Board Chair"

    @pytest.mark.anyio
    async def test_create_and_delete_equipment(self, client: AsyncClient):
        """Create equipment and then delete it."""
        payload = _make_equipment_verification_create()
        resp = await client.post(f"{API_PREFIX}/equipment-verifications", json=payload)
        assert resp.status_code == 201
        ev_id = resp.json()["id"]

        resp2 = await client.delete(f"{API_PREFIX}/equipment-verifications/{ev_id}")
        assert resp2.status_code == 204

        resp3 = await client.get(f"{API_PREFIX}/equipment-verifications/{ev_id}")
        assert resp3.status_code == 404

    @pytest.mark.anyio
    async def test_assessments_sorted_by_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capability-assessments")
        data = resp.json()
        dates = [item["assessment_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_audits_sorted_by_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/infrastructure-audits")
        data = resp.json()
        dates = [item["audit_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_metrics_after_create_and_delete(self, client: AsyncClient):
        """Metrics should reflect dynamic changes."""
        # Get baseline metrics
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        baseline = resp1.json()

        # Create a new assessment
        payload = _make_capability_assessment_create()
        await client.post(f"{API_PREFIX}/capability-assessments", json=payload)

        resp2 = await client.get(f"{API_PREFIX}/metrics")
        after_create = resp2.json()
        assert after_create["total_assessments"] == baseline["total_assessments"] + 1

        # Delete an assessment
        await client.delete(f"{API_PREFIX}/capability-assessments/CA-012")
        resp3 = await client.get(f"{API_PREFIX}/metrics")
        after_delete = resp3.json()
        assert after_delete["total_assessments"] == baseline["total_assessments"]


# =====================================================================
# ENUM COVERAGE
# =====================================================================


class TestEnumCoverage:
    """Verify enum values are represented in seed data."""

    @pytest.mark.anyio
    async def test_assessment_categories_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capability-assessments")
        data = resp.json()
        categories = {item["category"] for item in data["items"]}
        assert "therapeutic_experience" in categories
        assert "patient_population" in categories
        assert "infrastructure" in categories
        assert "staff_capability" in categories
        assert "data_management" in categories
        assert "regulatory_history" in categories

    @pytest.mark.anyio
    async def test_equipment_statuses_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/equipment-verifications")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "operational" in statuses
        assert "needs_calibration" in statuses
        assert "under_maintenance" in statuses
        assert "out_of_service" in statuses
        assert "decommissioned" in statuses

    @pytest.mark.anyio
    async def test_credential_types_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/staff-credentials")
        data = resp.json()
        types = {item["credential_type"] for item in data["items"]}
        assert "medical_license" in types
        assert "gcp_certification" in types
        assert "specialty_board" in types
        assert "research_training" in types
        assert "institutional_approval" in types
        assert "dea_registration" in types

    @pytest.mark.anyio
    async def test_audit_ratings_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/infrastructure-audits")
        data = resp.json()
        ratings = {item["rating"] for item in data["items"]}
        assert "excellent" in ratings
        assert "satisfactory" in ratings
        assert "needs_improvement" in ratings
        assert "unsatisfactory" in ratings
        assert "critical" in ratings

    @pytest.mark.anyio
    async def test_qualification_statuses_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qualification-records")
        data = resp.json()
        statuses = {item["qualification_status"] for item in data["items"]}
        assert "pending_assessment" in statuses
        assert "in_assessment" in statuses
        assert "qualified" in statuses
        assert "conditionally_qualified" in statuses
        assert "not_qualified" in statuses
        assert "suspended" in statuses
