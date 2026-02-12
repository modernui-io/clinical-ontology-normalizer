"""Tests for Regulatory Inspection Management (REG-INSP).

Covers:
- Seed data verification (inspections, findings, mock inspections, readiness assessments, commitments)
- Inspection CRUD (create, read, update, delete, list, filter by trial/status/authority/type)
- Finding CRUD (create, read, update, delete, list, filter by inspection/severity/classification)
- Mock inspection CRUD (create, read, update, delete, list, filter by trial/status)
- Readiness assessment CRUD (create, read, update, delete, list, filter by trial/authority)
- Commitment CRUD (create, read, update, delete, list, filter by inspection/status)
- Metrics computation (inspections by type/authority/status, findings by severity, readiness scores)
- Error handling (404s)
- Edge cases (empty filters, nonexistent trial)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.regulatory_inspection import (
    FindingClassification,
    FindingSeverity,
    InspectionAuthority,
    InspectionStatus,
    InspectionType,
)
from app.services.regulatory_inspection_service import (
    RegulatoryInspectionService,
    get_regulatory_inspection_service,
    reset_regulatory_inspection_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/regulatory-inspection"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_regulatory_inspection_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> RegulatoryInspectionService:
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


def _make_inspection_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "inspection_type": "pre_approval",
        "authority": "fda",
        "title": "Test Inspection",
        "scope": "GCP compliance review",
        "sponsor_lead": "Dr. Test Lead",
    }
    defaults.update(overrides)
    return defaults


def _make_finding_create(**overrides) -> dict:
    defaults = {
        "inspection_id": "INSP-001",
        "finding_number": "TEST-FND-001",
        "severity": "major",
        "classification": "major_finding",
        "description": "Test finding description",
        "area": "data integrity",
        "assigned_to": "Dr. Test Assignee",
    }
    defaults.update(overrides)
    return defaults


def _make_mock_inspection_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "target_authority": "fda",
        "planned_date": (now + timedelta(days=30)).isoformat(),
        "lead_auditor": "Dr. Test Auditor",
    }
    defaults.update(overrides)
    return defaults


def _make_readiness_assessment_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "target_authority": "fda",
        "assessed_by": "Dr. Test Assessor",
    }
    defaults.update(overrides)
    return defaults


def _make_commitment_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "inspection_id": "INSP-001",
        "commitment_text": "Implement corrective action for test finding.",
        "authority": "fda",
        "due_date": (now + timedelta(days=30)).isoformat(),
        "responsible_person": "Dr. Test Person",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_inspections_count(self, svc: RegulatoryInspectionService):
        inspections = svc.list_inspections()
        assert len(inspections) == 12

    def test_seed_inspections_across_trials(self, svc: RegulatoryInspectionService):
        trials = {i.trial_id for i in svc.list_inspections()}
        assert EYLEA_TRIAL in trials
        assert DUPIXENT_TRIAL in trials
        assert LIBTAYO_TRIAL in trials

    def test_seed_findings_count(self, svc: RegulatoryInspectionService):
        findings = svc.list_findings()
        assert len(findings) == 15

    def test_seed_findings_severities_present(self, svc: RegulatoryInspectionService):
        findings = svc.list_findings()
        severities = {f.severity for f in findings}
        assert FindingSeverity.CRITICAL in severities
        assert FindingSeverity.MAJOR in severities
        assert FindingSeverity.MINOR in severities
        assert FindingSeverity.OBSERVATION in severities

    def test_seed_mock_inspections_count(self, svc: RegulatoryInspectionService):
        mocks = svc.list_mock_inspections()
        assert len(mocks) == 10

    def test_seed_readiness_assessments_count(self, svc: RegulatoryInspectionService):
        assessments = svc.list_readiness_assessments()
        assert len(assessments) == 10

    def test_seed_commitments_count(self, svc: RegulatoryInspectionService):
        commitments = svc.list_commitments()
        assert len(commitments) == 12

    def test_seed_inspections_statuses_present(self, svc: RegulatoryInspectionService):
        inspections = svc.list_inspections()
        statuses = {i.status for i in inspections}
        assert InspectionStatus.PLANNED in statuses
        assert InspectionStatus.COMPLETED in statuses
        assert InspectionStatus.IN_PROGRESS in statuses
        assert InspectionStatus.CLOSED in statuses

    def test_seed_inspections_authorities_present(self, svc: RegulatoryInspectionService):
        inspections = svc.list_inspections()
        authorities = {i.authority for i in inspections}
        assert InspectionAuthority.FDA in authorities
        assert InspectionAuthority.EMA in authorities
        assert InspectionAuthority.PMDA in authorities
        assert InspectionAuthority.MHRA in authorities

    def test_seed_inspection_types_present(self, svc: RegulatoryInspectionService):
        inspections = svc.list_inspections()
        types = {i.inspection_type for i in inspections}
        assert InspectionType.PRE_APPROVAL in types
        assert InspectionType.ROUTINE_GCP in types
        assert InspectionType.FOR_CAUSE in types
        assert InspectionType.SYSTEMS in types


# =====================================================================
# INSPECTION CRUD
# =====================================================================


class TestInspectionCrud:
    """Test inspection create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_inspections(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inspections")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_inspections_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inspections", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_inspections_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inspections", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_inspections_filter_authority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inspections", params={"authority": "fda"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["authority"] == "fda"

    @pytest.mark.anyio
    async def test_list_inspections_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inspections", params={"inspection_type": "pre_approval"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["inspection_type"] == "pre_approval"

    @pytest.mark.anyio
    async def test_get_inspection(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inspections/INSP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "INSP-001"
        assert data["inspection_type"] == "pre_approval"
        assert data["authority"] == "fda"

    @pytest.mark.anyio
    async def test_get_inspection_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inspections/INSP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_inspection(self, client: AsyncClient):
        payload = _make_inspection_create()
        resp = await client.post(f"{API_PREFIX}/inspections", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Inspection"
        assert data["id"].startswith("INSP-")
        assert data["status"] == "planned"

    @pytest.mark.anyio
    async def test_update_inspection(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/inspections/INSP-001",
            json={"status": "closed", "outcome": "Updated outcome"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"
        assert data["outcome"] == "Updated outcome"

    @pytest.mark.anyio
    async def test_update_inspection_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/inspections/INSP-NONEXISTENT",
            json={"status": "closed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_inspection(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/inspections/INSP-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/inspections/INSP-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_inspection_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/inspections/INSP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# FINDING CRUD
# =====================================================================


class TestFindingCrud:
    """Test finding create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_findings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15
        assert len(data["items"]) == 15

    @pytest.mark.anyio
    async def test_list_findings_filter_inspection(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"inspection_id": "INSP-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["inspection_id"] == "INSP-001"

    @pytest.mark.anyio
    async def test_list_findings_filter_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"severity": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["severity"] == "critical"

    @pytest.mark.anyio
    async def test_list_findings_filter_classification(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"classification": "form_483"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["classification"] == "form_483"

    @pytest.mark.anyio
    async def test_get_finding(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/FND-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "FND-001"
        assert data["inspection_id"] == "INSP-001"

    @pytest.mark.anyio
    async def test_get_finding_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/FND-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_finding(self, client: AsyncClient):
        payload = _make_finding_create()
        resp = await client.post(f"{API_PREFIX}/findings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["description"] == "Test finding description"
        assert data["id"].startswith("FND-")

    @pytest.mark.anyio
    async def test_update_finding(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/findings/FND-004",
            json={"response_status": "submitted", "root_cause": "Updated root cause"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["response_status"] == "submitted"
        assert data["root_cause"] == "Updated root cause"

    @pytest.mark.anyio
    async def test_update_finding_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/findings/FND-NONEXISTENT",
            json={"response_status": "submitted"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_finding(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/findings/FND-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/findings/FND-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_finding_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/findings/FND-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# MOCK INSPECTION CRUD
# =====================================================================


class TestMockInspectionCrud:
    """Test mock inspection create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_mock_inspections(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mock-inspections")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_mock_inspections_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mock-inspections", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_mock_inspections_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mock-inspections", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_mock_inspection(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mock-inspections/MOCK-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "MOCK-001"
        assert data["mock_type"] == "full"

    @pytest.mark.anyio
    async def test_get_mock_inspection_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mock-inspections/MOCK-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_mock_inspection(self, client: AsyncClient):
        payload = _make_mock_inspection_create()
        resp = await client.post(f"{API_PREFIX}/mock-inspections", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["lead_auditor"] == "Dr. Test Auditor"
        assert data["id"].startswith("MOCK-")
        assert data["status"] == "planned"

    @pytest.mark.anyio
    async def test_update_mock_inspection(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/mock-inspections/MOCK-007",
            json={"status": "completed", "findings_count": 3, "readiness_score_pct": 85.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["findings_count"] == 3
        assert data["readiness_score_pct"] == 85.0

    @pytest.mark.anyio
    async def test_update_mock_inspection_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/mock-inspections/MOCK-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_mock_inspection(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/mock-inspections/MOCK-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/mock-inspections/MOCK-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_mock_inspection_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/mock-inspections/MOCK-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# READINESS ASSESSMENT CRUD
# =====================================================================


class TestReadinessAssessmentCrud:
    """Test readiness assessment create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_readiness_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/readiness-assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_readiness_assessments_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/readiness-assessments", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_readiness_assessments_filter_authority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/readiness-assessments", params={"target_authority": "fda"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["target_authority"] == "fda"

    @pytest.mark.anyio
    async def test_get_readiness_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/readiness-assessments/RA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RA-001"
        assert data["overall_score_pct"] == 88.5

    @pytest.mark.anyio
    async def test_get_readiness_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/readiness-assessments/RA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_readiness_assessment(self, client: AsyncClient):
        payload = _make_readiness_assessment_create()
        resp = await client.post(f"{API_PREFIX}/readiness-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["assessed_by"] == "Dr. Test Assessor"
        assert data["id"].startswith("RA-")

    @pytest.mark.anyio
    async def test_update_readiness_assessment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/readiness-assessments/RA-001",
            json={"overall_score_pct": 95.0, "remediation_plan": "Updated plan"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_score_pct"] == 95.0
        assert data["remediation_plan"] == "Updated plan"

    @pytest.mark.anyio
    async def test_update_readiness_assessment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/readiness-assessments/RA-NONEXISTENT",
            json={"overall_score_pct": 95.0},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_readiness_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/readiness-assessments/RA-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/readiness-assessments/RA-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_readiness_assessment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/readiness-assessments/RA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# COMMITMENT CRUD
# =====================================================================


class TestCommitmentCrud:
    """Test commitment create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_commitments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/commitments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_commitments_filter_inspection(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/commitments", params={"inspection_id": "INSP-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["inspection_id"] == "INSP-001"

    @pytest.mark.anyio
    async def test_list_commitments_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/commitments", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_commitment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/commitments/CMT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CMT-001"
        assert data["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_commitment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/commitments/CMT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_commitment(self, client: AsyncClient):
        payload = _make_commitment_create()
        resp = await client.post(f"{API_PREFIX}/commitments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["commitment_text"] == "Implement corrective action for test finding."
        assert data["id"].startswith("CMT-")
        assert data["status"] == "open"

    @pytest.mark.anyio
    async def test_update_commitment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/commitments/CMT-004",
            json={"status": "completed", "evidence_reference": "EVIDENCE-2024-004"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["evidence_reference"] == "EVIDENCE-2024-004"

    @pytest.mark.anyio
    async def test_update_commitment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/commitments/CMT-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_commitment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/commitments/CMT-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/commitments/CMT-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_commitment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/commitments/CMT-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test regulatory inspection metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_inspections"] == 12
        assert data["total_findings"] == 15
        assert data["total_mock_inspections"] == 10
        assert data["total_commitments"] == 12

    @pytest.mark.anyio
    async def test_get_metrics_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_inspections"] > 0
        assert data["total_inspections"] < 12

    @pytest.mark.anyio
    async def test_get_metrics_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_inspections"] == 0
        assert data["total_findings"] == 0

    def test_metrics_inspections_by_type(self, svc: RegulatoryInspectionService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.inspections_by_type.values())
        assert total_by_type == metrics.total_inspections

    def test_metrics_inspections_by_authority(self, svc: RegulatoryInspectionService):
        metrics = svc.get_metrics()
        total_by_authority = sum(metrics.inspections_by_authority.values())
        assert total_by_authority == metrics.total_inspections

    def test_metrics_inspections_by_status(self, svc: RegulatoryInspectionService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.inspections_by_status.values())
        assert total_by_status == metrics.total_inspections

    def test_metrics_findings_by_severity(self, svc: RegulatoryInspectionService):
        metrics = svc.get_metrics()
        total_by_severity = sum(metrics.findings_by_severity.values())
        assert total_by_severity == metrics.total_findings

    def test_metrics_open_findings(self, svc: RegulatoryInspectionService):
        metrics = svc.get_metrics()
        findings = svc.list_findings()
        expected_open = sum(1 for f in findings if f.response_status == "pending")
        assert metrics.open_findings == expected_open

    def test_metrics_avg_readiness_score(self, svc: RegulatoryInspectionService):
        metrics = svc.get_metrics()
        assert 0.0 <= metrics.avg_readiness_score_pct <= 100.0
        assert metrics.avg_readiness_score_pct > 0

    def test_metrics_overdue_commitments(self, svc: RegulatoryInspectionService):
        metrics = svc.get_metrics()
        assert metrics.overdue_commitments >= 0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_regulatory_inspection_service()
        svc2 = get_regulatory_inspection_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_regulatory_inspection_service()
        svc2 = reset_regulatory_inspection_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_regulatory_inspection_service()
        svc.delete_inspection("INSP-001")
        assert svc.get_inspection("INSP-001") is None
        svc2 = reset_regulatory_inspection_service()
        assert svc2.get_inspection("INSP-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_inspections_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inspections")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_findings_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_mock_inspections_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mock-inspections")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_readiness_assessments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/readiness-assessments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_commitments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/commitments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_inspection_with_optional_fields(self, client: AsyncClient):
        payload = _make_inspection_create(
            site_id="SITE-999",
            site_contact="Dr. Contact",
        )
        resp = await client.post(f"{API_PREFIX}/inspections", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_id"] == "SITE-999"
        assert data["site_contact"] == "Dr. Contact"

    @pytest.mark.anyio
    async def test_create_finding_with_optional_fields(self, client: AsyncClient):
        payload = _make_finding_create(
            regulatory_reference="21 CFR 312.62",
        )
        resp = await client.post(f"{API_PREFIX}/findings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["regulatory_reference"] == "21 CFR 312.62"

    @pytest.mark.anyio
    async def test_create_mock_inspection_with_optional_fields(self, client: AsyncClient):
        payload = _make_mock_inspection_create(
            site_id="SITE-999",
            mock_type="tabletop",
        )
        resp = await client.post(f"{API_PREFIX}/mock-inspections", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_id"] == "SITE-999"
        assert data["mock_type"] == "tabletop"

    @pytest.mark.anyio
    async def test_create_readiness_assessment_with_optional_fields(self, client: AsyncClient):
        payload = _make_readiness_assessment_create(
            site_id="SITE-999",
        )
        resp = await client.post(f"{API_PREFIX}/readiness-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_id"] == "SITE-999"

    @pytest.mark.anyio
    async def test_create_commitment_with_optional_fields(self, client: AsyncClient):
        payload = _make_commitment_create(
            finding_id="FND-001",
        )
        resp = await client.post(f"{API_PREFIX}/commitments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["finding_id"] == "FND-001"

    @pytest.mark.anyio
    async def test_list_findings_nonexistent_inspection(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"inspection_id": "INSP-NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_commitments_nonexistent_inspection(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/commitments", params={"inspection_id": "INSP-NONEXISTENT"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_update_commitment_auto_completed_date(self, client: AsyncClient):
        """Updating commitment status to 'completed' should auto-set completed_date."""
        resp = await client.put(
            f"{API_PREFIX}/commitments/CMT-006",
            json={"status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["completed_date"] is not None


# =====================================================================
# DATA VALIDATION
# =====================================================================


class TestDataValidation:
    """Test detailed data validation across the system."""

    @pytest.mark.anyio
    async def test_inspection_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inspections/INSP-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "inspection_type" in data
        assert "authority" in data
        assert "status" in data
        assert "title" in data
        assert "scope" in data
        assert "sponsor_lead" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_finding_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/FND-001")
        data = resp.json()
        assert "id" in data
        assert "inspection_id" in data
        assert "finding_number" in data
        assert "severity" in data
        assert "classification" in data
        assert "description" in data
        assert "area" in data
        assert "assigned_to" in data

    @pytest.mark.anyio
    async def test_mock_inspection_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/mock-inspections/MOCK-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "target_authority" in data
        assert "lead_auditor" in data
        assert "status" in data
        assert "findings_count" in data

    @pytest.mark.anyio
    async def test_readiness_assessment_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/readiness-assessments/RA-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "target_authority" in data
        assert "overall_score_pct" in data
        assert "document_readiness_pct" in data
        assert "process_readiness_pct" in data
        assert "staff_readiness_pct" in data
        assert "system_readiness_pct" in data
        assert "assessed_by" in data

    @pytest.mark.anyio
    async def test_commitment_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/commitments/CMT-001")
        data = resp.json()
        assert "id" in data
        assert "inspection_id" in data
        assert "commitment_text" in data
        assert "authority" in data
        assert "due_date" in data
        assert "status" in data
        assert "responsible_person" in data

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_inspections" in data
        assert "inspections_by_type" in data
        assert "inspections_by_authority" in data
        assert "inspections_by_status" in data
        assert "total_findings" in data
        assert "findings_by_severity" in data
        assert "open_findings" in data
        assert "total_mock_inspections" in data
        assert "avg_readiness_score_pct" in data
        assert "total_commitments" in data
        assert "overdue_commitments" in data

    def test_completed_inspections_have_outcome(self, svc: RegulatoryInspectionService):
        inspections = svc.list_inspections(status=InspectionStatus.COMPLETED)
        for i in inspections:
            assert i.outcome is not None

    def test_findings_have_required_fields(self, svc: RegulatoryInspectionService):
        findings = svc.list_findings()
        for f in findings:
            assert f.id
            assert f.inspection_id
            assert f.finding_number
            assert f.severity is not None
            assert f.classification is not None
            assert f.description
            assert f.area
            assert f.assigned_to

    def test_eylea_inspections_count(self, svc: RegulatoryInspectionService):
        inspections = svc.list_inspections(trial_id=EYLEA_TRIAL)
        assert len(inspections) == 4

    def test_dupixent_inspections_count(self, svc: RegulatoryInspectionService):
        inspections = svc.list_inspections(trial_id=DUPIXENT_TRIAL)
        assert len(inspections) == 4

    def test_libtayo_inspections_count(self, svc: RegulatoryInspectionService):
        inspections = svc.list_inspections(trial_id=LIBTAYO_TRIAL)
        assert len(inspections) == 4
