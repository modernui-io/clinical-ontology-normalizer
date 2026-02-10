"""Tests for Inspection Readiness module.

Covers:
- Seed data verification (inspections, assessments, checklists, findings, CAPAs)
- Inspection event CRUD (schedule, read, update, delete, list, filter)
- Readiness assessment CRUD (conduct, read, update, delete, list, filter)
- Readiness scoring (score calculation, status determination, category scores)
- Checklist management (create, read, update, delete, list, filter)
- Inspection finding recording and management
- CAPA lifecycle (create, update, close, verify, overdue tracking)
- Metrics computation
- Error handling (404s, 400s, invalid operations)
- Edge cases and boundary conditions
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.inspection_readiness import (
    CAPACreate,
    CAPAStatus,
    CAPAUpdate,
    ChecklistCategory,
    ChecklistItemStatus,
    FindingSeverity,
    InspectionEventCreate,
    InspectionEventStatus,
    InspectionEventUpdate,
    InspectionFindingCreate,
    InspectionFindingUpdate,
    InspectionOutcome,
    InspectionType,
    ReadinessAssessmentCreate,
    ReadinessAssessmentUpdate,
    ReadinessChecklistCreate,
    ReadinessChecklistUpdate,
    ReadinessStatus,
)
from app.services.inspection_readiness_service import (
    InspectionReadinessService,
    get_inspection_readiness_service,
    reset_inspection_readiness_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/inspection-readiness"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_inspection_readiness_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> InspectionReadinessService:
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
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "inspection_type": "fda_routine",
        "scheduled_date": (now + timedelta(days=45)).isoformat(),
        "inspector_name": "Dr. Test Inspector",
        "inspector_agency": "FDA CDER",
        "duration_days": 3,
        "scope": "GCP compliance review",
    }
    defaults.update(overrides)
    return defaults


def _make_assessment_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "assessed_by": "Test Assessor",
    }
    defaults.update(overrides)
    return defaults


def _make_checklist_create(**overrides) -> dict:
    defaults = {
        "assessment_id": "RA-001",
        "category": "documentation",
        "item_description": "Test checklist item",
        "required": True,
    }
    defaults.update(overrides)
    return defaults


def _make_finding_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "inspection_id": "INSP-001",
        "severity": "minor",
        "category": "documentation",
        "description": "Test finding description",
        "response_due_date": (now + timedelta(days=30)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_capa_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "finding_id": "IF-001",
        "trial_id": EYLEA_TRIAL,
        "site_id": "SITE-101",
        "description": "Test CAPA",
        "root_cause_analysis": "Test root cause analysis",
        "corrective_action": "Test corrective action",
        "preventive_action": "Test preventive action",
        "assigned_to": "Test Assignee",
        "due_date": (now + timedelta(days=30)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_inspections_count(self, svc: InspectionReadinessService):
        inspections = svc.list_inspections()
        assert len(inspections) == 5

    def test_seed_inspections_types(self, svc: InspectionReadinessService):
        inspections = svc.list_inspections()
        types = {i.inspection_type for i in inspections}
        assert InspectionType.FDA_ROUTINE in types
        assert InspectionType.FDA_FOR_CAUSE in types
        assert InspectionType.MOCK in types

    def test_seed_inspections_statuses(self, svc: InspectionReadinessService):
        inspections = svc.list_inspections()
        statuses = {i.status for i in inspections}
        assert InspectionEventStatus.COMPLETED in statuses
        assert InspectionEventStatus.SCHEDULED in statuses

    def test_seed_assessments_count(self, svc: InspectionReadinessService):
        assessments = svc.list_assessments()
        assert len(assessments) == 5

    def test_seed_assessments_statuses(self, svc: InspectionReadinessService):
        assessments = svc.list_assessments()
        statuses = {a.overall_status for a in assessments}
        assert ReadinessStatus.READY in statuses
        assert ReadinessStatus.CRITICAL_GAPS in statuses
        assert ReadinessStatus.NEEDS_ATTENTION in statuses

    def test_seed_checklists_count(self, svc: InspectionReadinessService):
        checklists = svc.list_checklists()
        assert len(checklists) == 18

    def test_seed_findings_count(self, svc: InspectionReadinessService):
        findings = svc.list_findings()
        assert len(findings) == 7

    def test_seed_findings_severities(self, svc: InspectionReadinessService):
        findings = svc.list_findings()
        severities = {f.severity for f in findings}
        assert FindingSeverity.CRITICAL in severities
        assert FindingSeverity.MAJOR in severities
        assert FindingSeverity.MINOR in severities
        assert FindingSeverity.OBSERVATION in severities

    def test_seed_capas_count(self, svc: InspectionReadinessService):
        capas = svc.list_capas()
        assert len(capas) == 6

    def test_seed_capas_statuses(self, svc: InspectionReadinessService):
        capas = svc.list_capas()
        statuses = {c.status for c in capas}
        assert CAPAStatus.CLOSED in statuses
        assert CAPAStatus.OPEN in statuses
        assert CAPAStatus.IN_PROGRESS in statuses
        assert CAPAStatus.OVERDUE in statuses
        assert CAPAStatus.PENDING_VERIFICATION in statuses

    def test_seed_completed_inspection_has_findings(self, svc: InspectionReadinessService):
        insp = svc.get_inspection("INSP-002")
        assert insp is not None
        assert insp.findings_count == 4

    def test_seed_closed_capa_has_verification(self, svc: InspectionReadinessService):
        capa = svc.get_capa("CAPA-001")
        assert capa is not None
        assert capa.status == CAPAStatus.CLOSED
        assert capa.verified_by is not None
        assert capa.effectiveness_check is True


# =====================================================================
# INSPECTION EVENT CRUD
# =====================================================================


class TestInspectionCrud:
    """Test inspection event CRUD operations."""

    @pytest.mark.anyio
    async def test_list_inspections(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inspections")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 5

    @pytest.mark.anyio
    async def test_list_inspections_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inspections", params={"inspection_type": "fda_routine"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["inspection_type"] == "fda_routine"

    @pytest.mark.anyio
    async def test_list_inspections_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inspections", params={"status": "completed"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_inspections_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inspections", params={"site_id": "SITE-101"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_inspections_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inspections", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_inspection(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inspections/INSP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "INSP-001"
        assert data["inspection_type"] == "fda_routine"
        assert data["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_inspection_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inspections/INSP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_schedule_inspection(self, client: AsyncClient):
        payload = _make_inspection_create()
        resp = await client.post(f"{API_PREFIX}/inspections", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["inspection_type"] == "fda_routine"
        assert data["status"] == "scheduled"
        assert data["id"].startswith("INSP-")
        assert data["outcome"] == "pending"

    @pytest.mark.anyio
    async def test_schedule_inspection_ema(self, client: AsyncClient):
        payload = _make_inspection_create(inspection_type="ema_gcp", inspector_agency="EMA")
        resp = await client.post(f"{API_PREFIX}/inspections", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["inspection_type"] == "ema_gcp"

    @pytest.mark.anyio
    async def test_update_inspection(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/inspections/INSP-003",
            json={"status": "in_progress", "observations": "Inspection started"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["observations"] == "Inspection started"

    @pytest.mark.anyio
    async def test_update_inspection_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/inspections/INSP-NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_inspection(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/inspections/INSP-005")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/inspections/INSP-005")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_inspection_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/inspections/INSP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# READINESS ASSESSMENT CRUD
# =====================================================================


class TestAssessmentCrud:
    """Test readiness assessment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5

    @pytest.mark.anyio
    async def test_list_assessments_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments", params={"site_id": "SITE-101"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_assessments_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_assessments_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments", params={"status": "critical_gaps"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["overall_status"] == "critical_gaps"

    @pytest.mark.anyio
    async def test_get_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/RA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RA-001"
        assert data["overall_score"] == 92.0
        assert data["overall_status"] == "ready"

    @pytest.mark.anyio
    async def test_get_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/RA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_conduct_assessment(self, client: AsyncClient):
        payload = _make_assessment_create()
        resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_id"] == "SITE-101"
        assert data["overall_status"] == "not_assessed"
        assert data["overall_score"] == 0.0
        assert data["id"].startswith("RA-")

    @pytest.mark.anyio
    async def test_update_assessment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assessments/RA-002",
            json={"overall_score": 65.0, "overall_status": "in_progress"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_score"] == 65.0
        assert data["overall_status"] == "in_progress"

    @pytest.mark.anyio
    async def test_update_assessment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assessments/RA-NONEXISTENT",
            json={"overall_score": 50.0},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assessments/RA-005")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/assessments/RA-005")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assessment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assessments/RA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_assessment_has_category_scores(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/RA-001")
        data = resp.json()
        assert len(data["category_scores"]) > 0
        for cs in data["category_scores"]:
            assert "category" in cs
            assert "score" in cs
            assert 0 <= cs["score"] <= 100


# =====================================================================
# READINESS SCORING
# =====================================================================


class TestReadinessScoring:
    """Test readiness scoring operations."""

    @pytest.mark.anyio
    async def test_score_readiness(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/assessments/RA-001/score")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_score"] > 0
        assert data["overall_status"] in ["not_assessed", "in_progress", "ready", "needs_attention", "critical_gaps"]
        assert len(data["category_scores"]) > 0

    @pytest.mark.anyio
    async def test_score_readiness_ready_site(self, client: AsyncClient):
        """RA-001 has all complete items, should score high."""
        resp = await client.post(f"{API_PREFIX}/assessments/RA-001/score")
        data = resp.json()
        assert data["overall_score"] >= 85.0
        assert data["overall_status"] == "ready"

    @pytest.mark.anyio
    async def test_score_readiness_critical_site(self, client: AsyncClient):
        """RA-003 has mostly not_started items, should score low."""
        resp = await client.post(f"{API_PREFIX}/assessments/RA-003/score")
        data = resp.json()
        assert data["overall_score"] < 50.0
        assert data["overall_status"] == "critical_gaps"

    @pytest.mark.anyio
    async def test_score_readiness_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/assessments/RA-NONEXISTENT/score")
        assert resp.status_code == 404

    def test_score_readiness_gaps_identified(self, svc: InspectionReadinessService):
        """Scoring should identify gaps from needs_remediation and not_started required items."""
        result = svc.score_readiness("RA-003")
        assert result is not None
        assert result.gaps_identified > 0

    def test_score_readiness_no_checklists(self, svc: InspectionReadinessService):
        """Assessment with no checklist items should return existing data."""
        # Create a new assessment with no checklists
        asmt = svc.conduct_assessment(ReadinessAssessmentCreate(
            trial_id=EYLEA_TRIAL, site_id="SITE-102", assessed_by="Test"
        ))
        result = svc.score_readiness(asmt.id)
        assert result is not None
        assert result.overall_score == 0.0


# =====================================================================
# CHECKLIST MANAGEMENT
# =====================================================================


class TestChecklistCrud:
    """Test checklist item CRUD operations."""

    @pytest.mark.anyio
    async def test_list_checklists(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/checklists")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 18

    @pytest.mark.anyio
    async def test_list_checklists_filter_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/checklists", params={"assessment_id": "RA-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6
        for item in data["items"]:
            assert item["assessment_id"] == "RA-001"

    @pytest.mark.anyio
    async def test_list_checklists_filter_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/checklists", params={"category": "documentation"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["category"] == "documentation"

    @pytest.mark.anyio
    async def test_list_checklists_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/checklists", params={"status": "complete"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "complete"

    @pytest.mark.anyio
    async def test_get_checklist(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/checklists/CL-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CL-001"
        assert data["status"] == "complete"

    @pytest.mark.anyio
    async def test_get_checklist_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/checklists/CL-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_checklist(self, client: AsyncClient):
        payload = _make_checklist_create()
        resp = await client.post(f"{API_PREFIX}/checklists", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["category"] == "documentation"
        assert data["status"] == "not_started"
        assert data["id"].startswith("CL-")

    @pytest.mark.anyio
    async def test_create_checklist_invalid_assessment(self, client: AsyncClient):
        payload = _make_checklist_create(assessment_id="RA-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/checklists", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_checklist(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/checklists/CL-007",
            json={
                "status": "complete",
                "evidence_reference": "DOC-REF-001",
                "verified_by": "Test Verifier",
                "verified_date": now.isoformat(),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "complete"
        assert data["evidence_reference"] == "DOC-REF-001"
        assert data["verified_by"] == "Test Verifier"

    @pytest.mark.anyio
    async def test_update_checklist_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/checklists/CL-NONEXISTENT",
            json={"status": "complete"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_checklist(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/checklists/CL-018")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/checklists/CL-018")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_checklist_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/checklists/CL-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# INSPECTION FINDINGS
# =====================================================================


class TestFindingsCrud:
    """Test inspection finding CRUD operations."""

    @pytest.mark.anyio
    async def test_list_findings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7

    @pytest.mark.anyio
    async def test_list_findings_filter_inspection(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"inspection_id": "INSP-002"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["inspection_id"] == "INSP-002"

    @pytest.mark.anyio
    async def test_list_findings_filter_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"severity": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["severity"] == "critical"

    @pytest.mark.anyio
    async def test_list_findings_filter_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings", params={"category": "documentation"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["category"] == "documentation"

    @pytest.mark.anyio
    async def test_get_finding(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/IF-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "IF-001"
        assert data["severity"] == "minor"
        assert data["response_submitted"] is True
        assert data["response_accepted"] is True

    @pytest.mark.anyio
    async def test_get_finding_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings/IF-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_record_finding(self, client: AsyncClient):
        payload = _make_finding_create()
        resp = await client.post(f"{API_PREFIX}/findings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["severity"] == "minor"
        assert data["inspection_id"] == "INSP-001"
        assert data["id"].startswith("IF-")
        assert data["response_submitted"] is False

    @pytest.mark.anyio
    async def test_record_finding_auto_number(self, client: AsyncClient):
        """Recording a finding should auto-generate finding number."""
        payload = _make_finding_create()
        resp = await client.post(f"{API_PREFIX}/findings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["finding_number"].startswith("F-")

    @pytest.mark.anyio
    async def test_record_finding_invalid_inspection(self, client: AsyncClient):
        payload = _make_finding_create(inspection_id="INSP-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/findings", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_record_finding_critical(self, client: AsyncClient):
        payload = _make_finding_create(
            severity="critical",
            category="processes",
            description="Critical process failure",
            regulatory_reference="21 CFR 312.32",
        )
        resp = await client.post(f"{API_PREFIX}/findings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["severity"] == "critical"
        assert data["regulatory_reference"] == "21 CFR 312.32"

    @pytest.mark.anyio
    async def test_update_finding(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/findings/IF-005",
            json={"response_submitted": True, "root_cause": "Updated root cause"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["response_submitted"] is True
        assert data["root_cause"] == "Updated root cause"

    @pytest.mark.anyio
    async def test_update_finding_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/findings/IF-NONEXISTENT",
            json={"response_submitted": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_finding(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/findings/IF-007")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/findings/IF-007")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_finding_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/findings/IF-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_record_finding_updates_inspection_count(self, client: AsyncClient):
        """Recording a finding should increment the inspection's findings_count."""
        # Get current count
        resp1 = await client.get(f"{API_PREFIX}/inspections/INSP-001")
        initial_count = resp1.json()["findings_count"]

        # Record a new finding
        payload = _make_finding_create(inspection_id="INSP-001")
        await client.post(f"{API_PREFIX}/findings", json=payload)

        # Check updated count
        resp2 = await client.get(f"{API_PREFIX}/inspections/INSP-001")
        assert resp2.json()["findings_count"] == initial_count + 1


# =====================================================================
# FINDING WORKFLOW
# =====================================================================


class TestFindingWorkflow:
    """Test finding response submission and acceptance workflow."""

    def test_finding_response_workflow(self, svc: InspectionReadinessService):
        """Test submitting and accepting a response to a finding."""
        finding = svc.get_finding("IF-005")
        assert finding is not None
        assert finding.response_submitted is False
        assert finding.response_accepted is False

        # Submit response
        updated = svc.update_finding("IF-005", InspectionFindingUpdate(response_submitted=True))
        assert updated is not None
        assert updated.response_submitted is True
        assert updated.response_accepted is False

        # Accept response
        updated = svc.update_finding("IF-005", InspectionFindingUpdate(response_accepted=True))
        assert updated is not None
        assert updated.response_accepted is True

    def test_finding_with_regulatory_reference(self, svc: InspectionReadinessService):
        finding = svc.get_finding("IF-003")
        assert finding is not None
        assert finding.regulatory_reference is not None
        assert "21 CFR" in finding.regulatory_reference or "ICH" in finding.regulatory_reference


# =====================================================================
# CAPA LIFECYCLE
# =====================================================================


class TestCAPACrud:
    """Test CAPA CRUD operations."""

    @pytest.mark.anyio
    async def test_list_capas(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    @pytest.mark.anyio
    async def test_list_capas_filter_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas", params={"site_id": "SITE-101"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_capas_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_capas_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas", params={"status": "open"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "open"

    @pytest.mark.anyio
    async def test_list_capas_filter_finding(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas", params={"finding_id": "IF-003"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["finding_id"] == "IF-003"

    @pytest.mark.anyio
    async def test_get_capa(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas/CAPA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CAPA-001"
        assert data["status"] == "closed"
        assert data["effectiveness_check"] is True

    @pytest.mark.anyio
    async def test_get_capa_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas/CAPA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_capa(self, client: AsyncClient):
        payload = _make_capa_create()
        resp = await client.post(f"{API_PREFIX}/capas", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["finding_id"] == "IF-001"
        assert data["status"] == "open"
        assert data["id"].startswith("CAPA-")
        assert data["effectiveness_check"] is False

    @pytest.mark.anyio
    async def test_create_capa_invalid_finding(self, client: AsyncClient):
        payload = _make_capa_create(finding_id="IF-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/capas", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_capa_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/capas/CAPA-004",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_update_capa_close_auto_complete_date(self, client: AsyncClient):
        """Closing a CAPA should auto-set completed_date if not provided."""
        resp = await client.put(
            f"{API_PREFIX}/capas/CAPA-002",
            json={"status": "closed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"
        assert data["completed_date"] is not None

    @pytest.mark.anyio
    async def test_update_capa_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/capas/CAPA-NONEXISTENT",
            json={"status": "closed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_capa(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/capas/CAPA-006")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/capas/CAPA-006")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_capa_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/capas/CAPA-NONEXISTENT")
        assert resp.status_code == 404


class TestCAPALifecycle:
    """Test full CAPA lifecycle transitions."""

    def test_capa_full_lifecycle(self, svc: InspectionReadinessService):
        """Test CAPA lifecycle: open -> in_progress -> pending_verification -> closed."""
        now = datetime.now(timezone.utc)
        capa = svc.get_capa("CAPA-004")
        assert capa is not None
        assert capa.status == CAPAStatus.OPEN

        # Move to in_progress
        updated = svc.update_capa("CAPA-004", CAPAUpdate(status=CAPAStatus.IN_PROGRESS))
        assert updated is not None
        assert updated.status == CAPAStatus.IN_PROGRESS

        # Move to pending_verification
        updated = svc.update_capa("CAPA-004", CAPAUpdate(
            status=CAPAStatus.PENDING_VERIFICATION,
            completed_date=now,
        ))
        assert updated is not None
        assert updated.status == CAPAStatus.PENDING_VERIFICATION
        assert updated.completed_date is not None

        # Close with verification
        updated = svc.update_capa("CAPA-004", CAPAUpdate(
            status=CAPAStatus.CLOSED,
            verified_by="QA Manager",
            verification_date=now,
            effectiveness_check=True,
        ))
        assert updated is not None
        assert updated.status == CAPAStatus.CLOSED
        assert updated.verified_by == "QA Manager"
        assert updated.effectiveness_check is True

    def test_capa_closed_auto_complete_date(self, svc: InspectionReadinessService):
        """Closing a CAPA should auto-set completed_date."""
        updated = svc.update_capa("CAPA-004", CAPAUpdate(status=CAPAStatus.CLOSED))
        assert updated is not None
        assert updated.completed_date is not None

    def test_capa_already_closed_keeps_date(self, svc: InspectionReadinessService):
        """Updating a closed CAPA's description should not change completed_date."""
        capa = svc.get_capa("CAPA-001")
        assert capa is not None
        original_date = capa.completed_date

        updated = svc.update_capa("CAPA-001", CAPAUpdate(description="Updated description"))
        assert updated is not None
        assert updated.completed_date == original_date


# =====================================================================
# OVERDUE CAPAs
# =====================================================================


class TestOverdueCAPAs:
    """Test overdue CAPA tracking."""

    @pytest.mark.anyio
    async def test_get_overdue_capas(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas/overdue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        now = datetime.now(timezone.utc)
        for item in data["items"]:
            due_date = datetime.fromisoformat(item["due_date"])
            assert due_date < now

    def test_overdue_capas_excludes_closed(self, svc: InspectionReadinessService):
        """Overdue tracking should not include closed CAPAs."""
        overdue = svc.get_overdue_capas()
        for capa in overdue:
            assert capa.status != CAPAStatus.CLOSED

    def test_overdue_capas_includes_overdue_status(self, svc: InspectionReadinessService):
        """CAPA-003 has overdue status and should appear."""
        overdue = svc.get_overdue_capas()
        overdue_ids = {c.id for c in overdue}
        assert "CAPA-003" in overdue_ids

    def test_overdue_capas_sorted_by_due_date(self, svc: InspectionReadinessService):
        overdue = svc.get_overdue_capas()
        if len(overdue) > 1:
            dates = [c.due_date for c in overdue]
            assert dates == sorted(dates)


# =====================================================================
# METRICS
# =====================================================================


class TestInspectionMetrics:
    """Test inspection readiness metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_inspections"] == 5
        assert data["total_assessments"] == 5
        assert data["total_checklist_items"] == 18
        assert data["total_findings"] == 7
        assert data["total_capas"] == 6

    @pytest.mark.anyio
    async def test_metrics_inspections_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_type = data["inspections_by_type"]
        total = sum(by_type.values())
        assert total == data["total_inspections"]

    @pytest.mark.anyio
    async def test_metrics_inspections_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["inspections_by_status"]
        total = sum(by_status.values())
        assert total == data["total_inspections"]

    @pytest.mark.anyio
    async def test_metrics_average_readiness_score(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["average_readiness_score"] > 0

    @pytest.mark.anyio
    async def test_metrics_checklist_completion_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0 <= data["checklist_completion_rate"] <= 100

    @pytest.mark.anyio
    async def test_metrics_findings_by_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_severity = data["findings_by_severity"]
        total = sum(by_severity.values())
        assert total == data["total_findings"]

    @pytest.mark.anyio
    async def test_metrics_capas_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["capas_by_status"]
        total = sum(by_status.values())
        assert total == data["total_capas"]

    def test_metrics_overdue_capas_count(self, svc: InspectionReadinessService):
        metrics = svc.get_metrics()
        overdue_list = svc.get_overdue_capas()
        assert metrics.overdue_capas == len(overdue_list)

    def test_metrics_sites_ready_count(self, svc: InspectionReadinessService):
        metrics = svc.get_metrics()
        ready_list = svc.list_assessments(status=ReadinessStatus.READY)
        assert metrics.sites_ready == len(ready_list)

    def test_metrics_sites_critical_count(self, svc: InspectionReadinessService):
        metrics = svc.get_metrics()
        critical_list = svc.list_assessments(status=ReadinessStatus.CRITICAL_GAPS)
        assert metrics.sites_with_critical_gaps == len(critical_list)

    def test_metrics_open_capas(self, svc: InspectionReadinessService):
        metrics = svc.get_metrics()
        open_capas = [
            c for c in svc.list_capas()
            if c.status in (CAPAStatus.OPEN, CAPAStatus.IN_PROGRESS)
        ]
        assert metrics.open_capas == len(open_capas)


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_inspection_readiness_service()
        svc2 = get_inspection_readiness_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_inspection_readiness_service()
        svc2 = reset_inspection_readiness_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_inspection_readiness_service()
        # Delete an inspection
        svc.delete_inspection("INSP-001")
        assert svc.get_inspection("INSP-001") is None
        # Reset should bring it back
        svc2 = reset_inspection_readiness_service()
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
    async def test_list_assessments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_checklists_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/checklists")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_findings_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/findings")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_capas_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/capas")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_inspection_with_all_fields(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = _make_inspection_create(
            trial_id=LIBTAYO_TRIAL,
            site_id="SITE-107",
            inspection_type="pmda",
            inspector_name="Dr. Tanaka",
            inspector_agency="PMDA",
            duration_days=5,
            scope="Full GCP/GMP audit",
        )
        resp = await client.post(f"{API_PREFIX}/inspections", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["inspection_type"] == "pmda"
        assert data["duration_days"] == 5

    @pytest.mark.anyio
    async def test_capa_with_all_fields(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = _make_capa_create(
            finding_id="IF-002",
            trial_id=EYLEA_TRIAL,
            site_id="SITE-101",
            description="Comprehensive CAPA",
            root_cause_analysis="Detailed root cause",
            corrective_action="Detailed corrective action plan",
            preventive_action="Detailed preventive measures",
            assigned_to="Quality Manager",
        )
        resp = await client.post(f"{API_PREFIX}/capas", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["description"] == "Comprehensive CAPA"

    @pytest.mark.anyio
    async def test_finding_severity_distribution(self, client: AsyncClient):
        """Verify all severity levels are represented in seed data."""
        resp = await client.get(f"{API_PREFIX}/findings")
        data = resp.json()
        severities = {item["severity"] for item in data["items"]}
        assert "critical" in severities
        assert "major" in severities
        assert "minor" in severities
        assert "observation" in severities

    @pytest.mark.anyio
    async def test_checklist_categories_in_seed(self, client: AsyncClient):
        """Verify multiple categories exist in checklist seed data."""
        resp = await client.get(f"{API_PREFIX}/checklists")
        data = resp.json()
        categories = {item["category"] for item in data["items"]}
        assert "documentation" in categories
        assert "facilities" in categories
        assert "personnel" in categories
        assert "training" in categories

    @pytest.mark.anyio
    async def test_inspection_outcomes_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/inspections")
        data = resp.json()
        outcomes = {item["outcome"] for item in data["items"]}
        assert "no_action_indicated" in outcomes
        assert "voluntary_action_indicated" in outcomes
        assert "pending" in outcomes

    @pytest.mark.anyio
    async def test_update_inspection_outcome(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/inspections/INSP-003",
            json={
                "status": "completed",
                "actual_date": now.isoformat(),
                "outcome": "no_action_indicated",
                "observations": "Clean inspection",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome"] == "no_action_indicated"
        assert data["status"] == "completed"

    @pytest.mark.anyio
    async def test_checklist_not_applicable_status(self, client: AsyncClient):
        """Verify not_applicable checklist items exist in seed data."""
        resp = await client.get(f"{API_PREFIX}/checklists", params={"status": "not_applicable"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0

    @pytest.mark.anyio
    async def test_score_readiness_after_checklist_update(self, client: AsyncClient):
        """Updating a checklist to complete should change the readiness score."""
        # Get initial score
        resp1 = await client.post(f"{API_PREFIX}/assessments/RA-002/score")
        initial_score = resp1.json()["overall_score"]

        # Update an incomplete item to complete
        now = datetime.now(timezone.utc)
        await client.put(
            f"{API_PREFIX}/checklists/CL-008",
            json={
                "status": "complete",
                "verified_by": "Test",
                "verified_date": now.isoformat(),
            },
        )

        # Re-score
        resp2 = await client.post(f"{API_PREFIX}/assessments/RA-002/score")
        new_score = resp2.json()["overall_score"]
        assert new_score >= initial_score

    def test_score_readiness_with_mixed_statuses(self, svc: InspectionReadinessService):
        """RA-004 has a mix of complete, in_progress, and not_applicable items."""
        result = svc.score_readiness("RA-004")
        assert result is not None
        assert 0 < result.overall_score < 100

    @pytest.mark.anyio
    async def test_multiple_findings_for_same_inspection(self, client: AsyncClient):
        """Record multiple findings for the same inspection."""
        for i in range(3):
            payload = _make_finding_create(
                inspection_id="INSP-004",
                severity="minor",
                description=f"Additional finding {i + 1}",
            )
            resp = await client.post(f"{API_PREFIX}/findings", json=payload)
            assert resp.status_code == 201

        # Verify count increased
        resp = await client.get(f"{API_PREFIX}/findings", params={"inspection_id": "INSP-004"})
        data = resp.json()
        assert data["total"] >= 5  # 2 original + 3 new

    @pytest.mark.anyio
    async def test_create_capa_for_different_findings(self, client: AsyncClient):
        """Create CAPAs for different findings."""
        for finding_id in ["IF-002", "IF-006"]:
            payload = _make_capa_create(finding_id=finding_id)
            resp = await client.post(f"{API_PREFIX}/capas", json=payload)
            assert resp.status_code == 201

    def test_inspection_sorted_by_date_descending(self, svc: InspectionReadinessService):
        inspections = svc.list_inspections()
        dates = [i.scheduled_date for i in inspections]
        assert dates == sorted(dates, reverse=True)

    def test_capas_sorted_by_due_date(self, svc: InspectionReadinessService):
        capas = svc.list_capas()
        dates = [c.due_date for c in capas]
        assert dates == sorted(dates)

    def test_assessment_score_range(self, svc: InspectionReadinessService):
        assessments = svc.list_assessments()
        for asmt in assessments:
            assert 0 <= asmt.overall_score <= 100

    @pytest.mark.anyio
    async def test_schedule_mock_inspection(self, client: AsyncClient):
        payload = _make_inspection_create(
            inspection_type="mock",
            inspector_agency="Internal QA",
        )
        resp = await client.post(f"{API_PREFIX}/inspections", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["inspection_type"] == "mock"

    @pytest.mark.anyio
    async def test_schedule_health_canada_inspection(self, client: AsyncClient):
        payload = _make_inspection_create(
            inspection_type="health_canada",
            inspector_agency="Health Canada",
        )
        resp = await client.post(f"{API_PREFIX}/inspections", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["inspection_type"] == "health_canada"

    @pytest.mark.anyio
    async def test_schedule_mhra_inspection(self, client: AsyncClient):
        payload = _make_inspection_create(
            inspection_type="mhra",
            inspector_agency="MHRA",
        )
        resp = await client.post(f"{API_PREFIX}/inspections", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["inspection_type"] == "mhra"
