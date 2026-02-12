"""Tests for Protocol Compliance Management (PROT-COMP).

Covers:
- Seed data verification (assessments, findings, training, adherence, corrective actions)
- Compliance Assessment CRUD (create, read, update, delete, list, filter)
- Compliance Finding CRUD with severity/status filtering
- Training Compliance CRUD with status filtering
- Protocol Adherence CRUD with compliance filtering
- Corrective Action CRUD with status/priority filtering
- Metrics computation
- Auto-set remediation_date on finding status change
- Auto-set completion_date on corrective action close
- Error handling (404s)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.protocol_compliance import (
    ComplianceArea,
    ComplianceRating,
    FindingSeverity,
    FindingStatus,
    TrainingStatus,
)
from app.services.protocol_compliance_service import (
    ProtocolComplianceService,
    get_protocol_compliance_service,
    reset_protocol_compliance_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/protocol-compliance"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_protocol_compliance_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ProtocolComplianceService:
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


def _make_assessment_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "compliance_area": "gcp",
        "assessor": "Test Assessor",
        "score": 90.0,
        "rating": "fully_compliant",
    }
    defaults.update(overrides)
    return defaults


def _make_finding_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "compliance_area": "gcp",
        "finding_description": "Test compliance finding",
        "severity": "major",
        "responsible_person": "Test Person",
        "due_date": (now + timedelta(days=30)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_training_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "trainee_name": "Test Trainee",
        "trainee_role": "Study Coordinator",
        "training_topic": "GCP Training",
        "required_date": (now + timedelta(days=14)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_adherence_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "procedure_name": "Test Procedure",
        "reported_by": "Test Reporter",
        "is_compliant": True,
    }
    defaults.update(overrides)
    return defaults


def _make_corrective_action_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "action_description": "Test corrective action",
        "assigned_to": "Test Assignee",
        "priority": "major",
        "due_date": (now + timedelta(days=21)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_assessments_count(self, svc: ProtocolComplianceService):
        items = svc.list_assessments()
        assert len(items) == 12

    def test_seed_findings_count(self, svc: ProtocolComplianceService):
        items = svc.list_findings()
        assert len(items) == 12

    def test_seed_training_count(self, svc: ProtocolComplianceService):
        items = svc.list_training()
        assert len(items) == 12

    def test_seed_adherence_count(self, svc: ProtocolComplianceService):
        items = svc.list_adherence()
        assert len(items) == 12

    def test_seed_corrective_actions_count(self, svc: ProtocolComplianceService):
        items = svc.list_corrective_actions()
        assert len(items) == 10

    def test_seed_assessments_have_all_trials(self, svc: ProtocolComplianceService):
        items = svc.list_assessments()
        trial_ids = {a.trial_id for a in items}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_assessments_cover_multiple_areas(self, svc: ProtocolComplianceService):
        items = svc.list_assessments()
        areas = {a.compliance_area for a in items}
        assert len(areas) >= 5

    def test_seed_assessments_cover_multiple_ratings(self, svc: ProtocolComplianceService):
        items = svc.list_assessments()
        ratings = {a.rating for a in items}
        assert ComplianceRating.FULLY_COMPLIANT in ratings
        assert ComplianceRating.NON_COMPLIANT in ratings

    def test_seed_findings_cover_multiple_severities(self, svc: ProtocolComplianceService):
        items = svc.list_findings()
        severities = {f.severity for f in items}
        assert FindingSeverity.CRITICAL in severities
        assert FindingSeverity.MAJOR in severities
        assert FindingSeverity.MINOR in severities
        assert FindingSeverity.OBSERVATION in severities

    def test_seed_training_cover_multiple_statuses(self, svc: ProtocolComplianceService):
        items = svc.list_training()
        statuses = {t.status for t in items}
        assert TrainingStatus.COMPLETED in statuses
        assert TrainingStatus.IN_PROGRESS in statuses
        assert TrainingStatus.NOT_STARTED in statuses
        assert TrainingStatus.EXPIRED in statuses
        assert TrainingStatus.WAIVED in statuses

    def test_seed_adherence_has_non_compliant(self, svc: ProtocolComplianceService):
        non_compliant = svc.list_adherence(is_compliant=False)
        assert len(non_compliant) >= 3

    def test_seed_corrective_actions_have_verified(self, svc: ProtocolComplianceService):
        items = svc.list_corrective_actions()
        statuses = {c.status for c in items}
        assert FindingStatus.VERIFIED in statuses


# =====================================================================
# COMPLIANCE ASSESSMENT CRUD
# =====================================================================


class TestAssessmentCrud:
    """Test compliance assessment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_assessments_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_assessments_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments", params={"site_id": "SITE-107"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SITE-107"

    @pytest.mark.anyio
    async def test_list_assessments_filter_area(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments", params={"compliance_area": "gcp"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["compliance_area"] == "gcp"

    @pytest.mark.anyio
    async def test_list_assessments_filter_rating(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assessments", params={"rating": "fully_compliant"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["rating"] == "fully_compliant"

    @pytest.mark.anyio
    async def test_get_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/CA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CA-001"
        assert data["compliance_area"] == "gcp"
        assert data["rating"] == "fully_compliant"

    @pytest.mark.anyio
    async def test_get_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/CA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_assessment(self, client: AsyncClient):
        payload = _make_assessment_create()
        resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["compliance_area"] == "gcp"
        assert data["id"].startswith("CA-")

    @pytest.mark.anyio
    async def test_update_assessment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assessments/CA-001",
            json={"rating": "substantially_compliant", "score": 88.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rating"] == "substantially_compliant"
        assert data["score"] == 88.0

    @pytest.mark.anyio
    async def test_update_assessment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assessments/CA-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assessments/CA-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/assessments/CA-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assessment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assessments/CA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# COMPLIANCE FINDING CRUD
# =====================================================================


class TestFindingCrud:
    """Test compliance finding CRUD operations."""

    @pytest.mark.anyio
    async def test_list_findings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_findings_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_findings_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"site_id": "SITE-107"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SITE-107"

    @pytest.mark.anyio
    async def test_list_findings_filter_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"severity": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["severity"] == "critical"

    @pytest.mark.anyio
    async def test_list_findings_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"status": "open"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "open"

    @pytest.mark.anyio
    async def test_list_findings_filter_area(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/findings", params={"compliance_area": "safety_reporting"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["compliance_area"] == "safety_reporting"

    @pytest.mark.anyio
    async def test_get_finding(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/CF-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CF-001"
        assert data["severity"] == "major"

    @pytest.mark.anyio
    async def test_get_finding_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/CF-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_finding(self, client: AsyncClient):
        payload = _make_finding_create()
        resp = await client.post(f"{API_PREFIX}/findings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["finding_description"] == "Test compliance finding"
        assert data["status"] == "open"
        assert data["id"].startswith("CF-")

    @pytest.mark.anyio
    async def test_update_finding(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/findings/CF-003",
            json={"status": "in_remediation", "root_cause": "Staffing shortage"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_remediation"
        assert data["root_cause"] == "Staffing shortage"

    @pytest.mark.anyio
    async def test_update_finding_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/findings/CF-NONEXISTENT",
            json={"status": "open"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_finding_remediated_auto_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/findings/CF-003",
            json={"status": "remediated"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "remediated"
        assert data["remediation_date"] is not None

    @pytest.mark.anyio
    async def test_delete_finding(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/findings/CF-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/findings/CF-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_finding_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/findings/CF-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# TRAINING COMPLIANCE CRUD
# =====================================================================


class TestTrainingCrud:
    """Test training compliance CRUD operations."""

    @pytest.mark.anyio
    async def test_list_training(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/training")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_training_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/training", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_training_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/training", params={"site_id": "SITE-107"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SITE-107"

    @pytest.mark.anyio
    async def test_list_training_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/training", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_training(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/training/TC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "TC-001"
        assert data["trainee_name"] == "Dr. Sarah Mitchell"

    @pytest.mark.anyio
    async def test_get_training_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/training/TC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_training(self, client: AsyncClient):
        payload = _make_training_create()
        resp = await client.post(f"{API_PREFIX}/training", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trainee_name"] == "Test Trainee"
        assert data["status"] == "not_started"
        assert data["id"].startswith("TC-")

    @pytest.mark.anyio
    async def test_update_training(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/training/TC-004",
            json={"status": "in_progress", "notes": "Started training"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["notes"] == "Started training"

    @pytest.mark.anyio
    async def test_update_training_completed_auto_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/training/TC-004",
            json={"status": "completed", "score": 90.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["completion_date"] is not None

    @pytest.mark.anyio
    async def test_update_training_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/training/TC-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_training(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/training/TC-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/training/TC-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_training_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/training/TC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# PROTOCOL ADHERENCE CRUD
# =====================================================================


class TestAdherenceCrud:
    """Test protocol adherence CRUD operations."""

    @pytest.mark.anyio
    async def test_list_adherence(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adherence")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_adherence_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adherence", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_adherence_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adherence", params={"site_id": "SITE-101"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_adherence_filter_compliant(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adherence", params={"is_compliant": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["is_compliant"] is True

    @pytest.mark.anyio
    async def test_list_adherence_filter_non_compliant(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adherence", params={"is_compliant": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["is_compliant"] is False

    @pytest.mark.anyio
    async def test_get_adherence(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adherence/PA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PA-001"
        assert data["is_compliant"] is True

    @pytest.mark.anyio
    async def test_get_adherence_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adherence/PA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_adherence(self, client: AsyncClient):
        payload = _make_adherence_create()
        resp = await client.post(f"{API_PREFIX}/adherence", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["procedure_name"] == "Test Procedure"
        assert data["is_compliant"] is True
        assert data["id"].startswith("PA-")

    @pytest.mark.anyio
    async def test_create_adherence_non_compliant(self, client: AsyncClient):
        payload = _make_adherence_create(is_compliant=False)
        resp = await client.post(f"{API_PREFIX}/adherence", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["is_compliant"] is False

    @pytest.mark.anyio
    async def test_update_adherence(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/adherence/PA-003",
            json={
                "deviation_type": "Updated Deviation",
                "reviewed_by": "New Reviewer",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deviation_type"] == "Updated Deviation"
        assert data["reviewed_by"] == "New Reviewer"

    @pytest.mark.anyio
    async def test_update_adherence_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/adherence/PA-NONEXISTENT",
            json={"is_compliant": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_adherence(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/adherence/PA-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/adherence/PA-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_adherence_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/adherence/PA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CORRECTIVE ACTION CRUD
# =====================================================================


class TestCorrectiveActionCrud:
    """Test corrective action CRUD operations."""

    @pytest.mark.anyio
    async def test_list_corrective_actions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/corrective-actions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_corrective_actions_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/corrective-actions", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_corrective_actions_filter_site(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/corrective-actions", params={"site_id": "SITE-105"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["site_id"] == "SITE-105"

    @pytest.mark.anyio
    async def test_list_corrective_actions_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/corrective-actions", params={"status": "open"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "open"

    @pytest.mark.anyio
    async def test_list_corrective_actions_filter_priority(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/corrective-actions", params={"priority": "critical"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["priority"] == "critical"

    @pytest.mark.anyio
    async def test_get_corrective_action(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/corrective-actions/CAPA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CAPA-001"
        assert data["action_type"] == "corrective"

    @pytest.mark.anyio
    async def test_get_corrective_action_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/corrective-actions/CAPA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_corrective_action(self, client: AsyncClient):
        payload = _make_corrective_action_create()
        resp = await client.post(f"{API_PREFIX}/corrective-actions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["action_description"] == "Test corrective action"
        assert data["status"] == "open"
        assert data["id"].startswith("CAPA-")

    @pytest.mark.anyio
    async def test_update_corrective_action(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/corrective-actions/CAPA-002",
            json={"status": "in_remediation", "notes": "Development started"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_remediation"
        assert data["notes"] == "Development started"

    @pytest.mark.anyio
    async def test_update_corrective_action_closed_auto_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/corrective-actions/CAPA-002",
            json={"status": "closed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"
        assert data["completion_date"] is not None

    @pytest.mark.anyio
    async def test_update_corrective_action_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/corrective-actions/CAPA-NONEXISTENT",
            json={"status": "closed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_corrective_action(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/corrective-actions/CAPA-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/corrective-actions/CAPA-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_corrective_action_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/corrective-actions/CAPA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test protocol compliance metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_assessments"] == 12
        assert data["total_findings"] == 12
        assert data["total_training_records"] == 12
        assert data["total_adherence_records"] == 12
        assert data["total_corrective_actions"] == 10

    @pytest.mark.anyio
    async def test_metrics_compliance_score(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0 <= data["avg_compliance_score"] <= 100

    @pytest.mark.anyio
    async def test_metrics_training_completion_pct(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0 <= data["training_completion_pct"] <= 100

    @pytest.mark.anyio
    async def test_metrics_adherence_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0 <= data["adherence_rate"] <= 100

    @pytest.mark.anyio
    async def test_metrics_open_findings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["open_findings"] >= 0
        assert data["open_findings"] <= data["total_findings"]

    @pytest.mark.anyio
    async def test_metrics_open_corrective_actions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["open_corrective_actions"] >= 0
        assert data["open_corrective_actions"] <= data["total_corrective_actions"]

    def test_metrics_assessments_by_area(self, svc: ProtocolComplianceService):
        metrics = svc.get_metrics()
        total_by_area = sum(metrics.assessments_by_area.values())
        assert total_by_area == metrics.total_assessments

    def test_metrics_assessments_by_rating(self, svc: ProtocolComplianceService):
        metrics = svc.get_metrics()
        total_by_rating = sum(metrics.assessments_by_rating.values())
        assert total_by_rating == metrics.total_assessments

    def test_metrics_findings_by_severity(self, svc: ProtocolComplianceService):
        metrics = svc.get_metrics()
        total_by_severity = sum(metrics.findings_by_severity.values())
        assert total_by_severity == metrics.total_findings

    def test_metrics_findings_by_status(self, svc: ProtocolComplianceService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.findings_by_status.values())
        assert total_by_status == metrics.total_findings

    def test_metrics_training_by_status(self, svc: ProtocolComplianceService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.training_by_status.values())
        assert total_by_status == metrics.total_training_records


# =====================================================================
# FINDING LIFECYCLE
# =====================================================================


class TestFindingLifecycle:
    """Test compliance finding lifecycle: open -> in_remediation -> remediated -> verified -> closed."""

    def test_finding_lifecycle_transitions(self, svc: ProtocolComplianceService):
        from app.schemas.protocol_compliance import ComplianceFindingUpdate

        # Start: open
        finding = svc.get_finding("CF-003")
        assert finding is not None
        assert finding.status == FindingStatus.OPEN

        # Transition to in_remediation
        updated = svc.update_finding(
            "CF-003", ComplianceFindingUpdate(status=FindingStatus.IN_REMEDIATION)
        )
        assert updated is not None
        assert updated.status == FindingStatus.IN_REMEDIATION

        # Transition to remediated (auto-sets remediation_date)
        updated = svc.update_finding(
            "CF-003", ComplianceFindingUpdate(status=FindingStatus.REMEDIATED)
        )
        assert updated is not None
        assert updated.status == FindingStatus.REMEDIATED
        assert updated.remediation_date is not None

        # Transition to verified
        updated = svc.update_finding(
            "CF-003",
            ComplianceFindingUpdate(status=FindingStatus.VERIFIED, verified_by="QA Lead"),
        )
        assert updated is not None
        assert updated.status == FindingStatus.VERIFIED

        # Transition to closed
        updated = svc.update_finding(
            "CF-003", ComplianceFindingUpdate(status=FindingStatus.CLOSED)
        )
        assert updated is not None
        assert updated.status == FindingStatus.CLOSED


# =====================================================================
# CORRECTIVE ACTION LIFECYCLE
# =====================================================================


class TestCorrectiveActionLifecycle:
    """Test corrective action lifecycle with auto-completion date."""

    def test_corrective_action_close_auto_completion(self, svc: ProtocolComplianceService):
        from app.schemas.protocol_compliance import CorrectiveActionUpdate

        # CAPA-005 is OPEN
        action = svc.get_corrective_action("CAPA-005")
        assert action is not None
        assert action.status == FindingStatus.OPEN
        assert action.completion_date is None

        # Close it - should auto-set completion_date
        updated = svc.update_corrective_action(
            "CAPA-005", CorrectiveActionUpdate(status=FindingStatus.CLOSED)
        )
        assert updated is not None
        assert updated.status == FindingStatus.CLOSED
        assert updated.completion_date is not None

    def test_corrective_action_verified_auto_completion(self, svc: ProtocolComplianceService):
        from app.schemas.protocol_compliance import CorrectiveActionUpdate

        # CAPA-002 is OPEN
        action = svc.get_corrective_action("CAPA-002")
        assert action is not None
        assert action.status == FindingStatus.OPEN

        # Verify it - should auto-set completion_date
        updated = svc.update_corrective_action(
            "CAPA-002", CorrectiveActionUpdate(status=FindingStatus.VERIFIED)
        )
        assert updated is not None
        assert updated.status == FindingStatus.VERIFIED
        assert updated.completion_date is not None

    def test_already_completed_keeps_date(self, svc: ProtocolComplianceService):
        from app.schemas.protocol_compliance import CorrectiveActionUpdate

        # CAPA-009 is VERIFIED with a completion_date
        action = svc.get_corrective_action("CAPA-009")
        assert action is not None
        assert action.completion_date is not None
        original_date = action.completion_date

        # Update notes should not change completion_date
        updated = svc.update_corrective_action(
            "CAPA-009", CorrectiveActionUpdate(notes="Updated notes")
        )
        assert updated is not None
        assert updated.completion_date == original_date


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_protocol_compliance_service()
        svc2 = get_protocol_compliance_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_protocol_compliance_service()
        svc2 = reset_protocol_compliance_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_protocol_compliance_service()
        # Delete an assessment
        svc.delete_assessment("CA-001")
        assert svc.get_assessment("CA-001") is None
        # Reset should bring it back
        svc2 = reset_protocol_compliance_service()
        assert svc2.get_assessment("CA-001") is not None


# =====================================================================
# EDGE CASES
# =====================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.anyio
    async def test_list_assessments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_findings_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_training_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/training")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_adherence_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/adherence")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_corrective_actions_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/corrective-actions")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_assessment_minimal(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "site_id": "SITE-101",
            "compliance_area": "gcp",
            "assessor": "Minimal Assessor",
        }
        resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["score"] == 0.0
        assert data["rating"] == "not_assessed"

    @pytest.mark.anyio
    async def test_create_finding_with_assessment_id(self, client: AsyncClient):
        payload = _make_finding_create(assessment_id="CA-001")
        resp = await client.post(f"{API_PREFIX}/findings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["assessment_id"] == "CA-001"

    @pytest.mark.anyio
    async def test_create_corrective_action_with_finding_id(self, client: AsyncClient):
        payload = _make_corrective_action_create(finding_id="CF-001")
        resp = await client.post(f"{API_PREFIX}/corrective-actions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["finding_id"] == "CF-001"

    @pytest.mark.anyio
    async def test_create_adherence_with_subject(self, client: AsyncClient):
        payload = _make_adherence_create(
            subject_id="SUBJ-TEST-001",
            visit_name="Screening",
        )
        resp = await client.post(f"{API_PREFIX}/adherence", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject_id"] == "SUBJ-TEST-001"
        assert data["visit_name"] == "Screening"

    @pytest.mark.anyio
    async def test_assessment_sorted_by_date_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        data = resp.json()
        dates = [item["assessment_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_findings_sorted_by_created_at_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings")
        data = resp.json()
        dates = [item["created_at"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_multiple_filter_combination(self, client: AsyncClient):
        """Test combining multiple filters on findings."""
        resp = await client.get(
            f"{API_PREFIX}/findings",
            params={
                "trial_id": LIBTAYO_TRIAL,
                "severity": "critical",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL
            assert item["severity"] == "critical"

    @pytest.mark.anyio
    async def test_empty_filter_result(self, client: AsyncClient):
        """Filtering with non-matching criteria should return empty list."""
        resp = await client.get(
            f"{API_PREFIX}/assessments",
            params={"site_id": "SITE-NONEXISTENT"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []


# =====================================================================
# ENUMERATION COVERAGE
# =====================================================================


class TestEnumerations:
    """Test that enums are correctly represented in API responses."""

    @pytest.mark.anyio
    async def test_compliance_areas_in_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        data = resp.json()
        areas = {item["compliance_area"] for item in data["items"]}
        assert "gcp" in areas
        assert "informed_consent" in areas
        assert "data_integrity" in areas
        assert "safety_reporting" in areas

    @pytest.mark.anyio
    async def test_ratings_in_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        data = resp.json()
        ratings = {item["rating"] for item in data["items"]}
        assert "fully_compliant" in ratings
        assert "substantially_compliant" in ratings
        assert "partially_compliant" in ratings
        assert "non_compliant" in ratings

    @pytest.mark.anyio
    async def test_finding_severities(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings")
        data = resp.json()
        severities = {item["severity"] for item in data["items"]}
        assert "critical" in severities
        assert "major" in severities
        assert "minor" in severities
        assert "observation" in severities

    @pytest.mark.anyio
    async def test_finding_statuses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "open" in statuses
        assert "in_remediation" in statuses

    @pytest.mark.anyio
    async def test_training_statuses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/training")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "completed" in statuses
        assert "in_progress" in statuses
        assert "not_started" in statuses
        assert "expired" in statuses
        assert "waived" in statuses
