"""Tests for Protocol Knowledge Assessment (PKA-ASM).

Covers:
- Seed data verification (assessment questionnaires, assessment responses,
  competency records, remediation plans)
- Assessment questionnaire CRUD (create, read, update, delete, list, filter by trial/status)
- Assessment response CRUD (create, read, update, delete, list, filter by trial/result/questionnaire)
- Competency record CRUD (create, read, update, delete, list, filter by trial/level/site)
- Remediation plan CRUD (create, read, update, delete, list, filter by trial/status)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.protocol_knowledge_assessment import (
    AssessmentResult,
    CompetencyLevel,
    QuestionnaireStatus,
    RemediationStatus,
)
from app.services.protocol_knowledge_assessment_service import (
    ProtocolKnowledgeAssessmentService,
    get_protocol_knowledge_assessment_service,
    reset_protocol_knowledge_assessment_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/protocol-knowledge-assessment"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_protocol_knowledge_assessment_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ProtocolKnowledgeAssessmentService:
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


def _make_questionnaire_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "questionnaire_title": "Test Protocol Assessment",
        "version": "1.0",
        "authored_by": "Dr. Test Author",
        "total_questions": 20,
        "passing_score_pct": 80.0,
    }
    defaults.update(overrides)
    return defaults


def _make_response_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "questionnaire_id": "AQ-001",
        "respondent_name": "Dr. Test Respondent",
        "respondent_role": "Investigator",
        "site_id": "SITE-TEST-001",
        "started_at": "2026-01-15T09:00:00Z",
        "attempt_number": 1,
    }
    defaults.update(overrides)
    return defaults


def _make_competency_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "staff_name": "Dr. Test Staff",
        "staff_role": "Sub-Investigator",
        "site_id": "SITE-TEST-001",
    }
    defaults.update(overrides)
    return defaults


def _make_remediation_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "staff_name": "Nurse Test Staff",
        "site_id": "SITE-TEST-001",
        "knowledge_gaps": "Protocol visit windows",
        "remediation_activities": "Self-study module on visit scheduling",
        "assigned_by": "Dr. Test Assigner",
        "due_date": "2026-03-01T00:00:00Z",
        "assessment_response_id": None,
    }
    defaults.update(overrides)
    return defaults


# ===================================================================
# SEED DATA VERIFICATION
# ===================================================================


class TestSeedData:
    """Verify all 4 entity types are seeded with 12 records each."""

    @pytest.mark.anyio
    async def test_seed_assessment_questionnaires(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessment-questionnaires")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_seed_assessment_responses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessment-responses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_competency_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/competency-records")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_remediation_plans(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/remediation-plans")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12


# ===================================================================
# ASSESSMENT QUESTIONNAIRE CRUD
# ===================================================================


class TestAssessmentQuestionnaireCRUD:
    @pytest.mark.anyio
    async def test_list_assessment_questionnaires(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessment-questionnaires")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_assessment_questionnaire(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessment-questionnaires/AQ-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "AQ-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_assessment_questionnaire_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessment-questionnaires/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_assessment_questionnaire(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/assessment-questionnaires",
            json=_make_questionnaire_create(),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("AQ-")
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["questionnaire_status"] == "draft"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/assessment-questionnaires")
        before = resp1.json()["total"]
        await client.post(
            f"{API_PREFIX}/assessment-questionnaires",
            json=_make_questionnaire_create(),
        )
        resp2 = await client.get(f"{API_PREFIX}/assessment-questionnaires")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_assessment_questionnaire(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assessment-questionnaires/AQ-001",
            json={"questionnaire_status": "active", "notes": "Updated note"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["questionnaire_status"] == "active"
        assert data["notes"] == "Updated note"

    @pytest.mark.anyio
    async def test_update_assessment_questionnaire_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assessment-questionnaires/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assessment_questionnaire(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assessment-questionnaires/AQ-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/assessment-questionnaires/AQ-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assessment_questionnaire_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assessment-questionnaires/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assessment-questionnaires",
            params={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_questionnaire_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assessment-questionnaires",
            params={"questionnaire_status": "active"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["questionnaire_status"] == "active"


# ===================================================================
# ASSESSMENT RESPONSE CRUD
# ===================================================================


class TestAssessmentResponseCRUD:
    @pytest.mark.anyio
    async def test_list_assessment_responses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessment-responses")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_assessment_response(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessment-responses/AR-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "AR-001"

    @pytest.mark.anyio
    async def test_get_assessment_response_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessment-responses/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_assessment_response(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/assessment-responses",
            json=_make_response_create(),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("AR-")
        assert data["respondent_name"] == "Dr. Test Respondent"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/assessment-responses")
        before = resp1.json()["total"]
        await client.post(
            f"{API_PREFIX}/assessment-responses",
            json=_make_response_create(),
        )
        resp2 = await client.get(f"{API_PREFIX}/assessment-responses")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_assessment_response(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assessment-responses/AR-001",
            json={"assessment_result": "pass", "notes": "Updated"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["assessment_result"] == "pass"
        assert data["notes"] == "Updated"

    @pytest.mark.anyio
    async def test_update_assessment_response_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assessment-responses/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assessment_response(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assessment-responses/AR-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/assessment-responses/AR-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assessment_response_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assessment-responses/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assessment-responses",
            params={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_assessment_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assessment-responses",
            params={"assessment_result": "pass"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["assessment_result"] == "pass"

    @pytest.mark.anyio
    async def test_filter_by_questionnaire_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assessment-responses",
            params={"questionnaire_id": "AQ-001"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["questionnaire_id"] == "AQ-001"


# ===================================================================
# COMPETENCY RECORD CRUD
# ===================================================================


class TestCompetencyRecordCRUD:
    @pytest.mark.anyio
    async def test_list_competency_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/competency-records")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_competency_record(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/competency-records/CR-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "CR-001"

    @pytest.mark.anyio
    async def test_get_competency_record_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/competency-records/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_competency_record(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/competency-records",
            json=_make_competency_create(),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("CR-")
        assert data["staff_name"] == "Dr. Test Staff"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/competency-records")
        before = resp1.json()["total"]
        await client.post(
            f"{API_PREFIX}/competency-records",
            json=_make_competency_create(),
        )
        resp2 = await client.get(f"{API_PREFIX}/competency-records")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_competency_record(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/competency-records/CR-001",
            json={"competency_level": "expert", "notes": "Updated competency"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["competency_level"] == "expert"
        assert data["notes"] == "Updated competency"

    @pytest.mark.anyio
    async def test_update_competency_record_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/competency-records/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_competency_record(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/competency-records/CR-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/competency-records/CR-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_competency_record_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/competency-records/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/competency-records",
            params={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_competency_level(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/competency-records",
            params={"competency_level": "expert"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["competency_level"] == "expert"

    @pytest.mark.anyio
    async def test_filter_by_site_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/competency-records",
            params={"site_id": "SITE-NY-001"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["site_id"] == "SITE-NY-001"


# ===================================================================
# REMEDIATION PLAN CRUD
# ===================================================================


class TestRemediationPlanCRUD:
    @pytest.mark.anyio
    async def test_list_remediation_plans(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/remediation-plans")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_get_remediation_plan(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/remediation-plans/RP-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "RP-001"

    @pytest.mark.anyio
    async def test_get_remediation_plan_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/remediation-plans/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_remediation_plan(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/remediation-plans",
            json=_make_remediation_create(),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("RP-")
        assert data["staff_name"] == "Nurse Test Staff"
        assert data["remediation_status"] == "assigned"

    @pytest.mark.anyio
    async def test_create_increments_count(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/remediation-plans")
        before = resp1.json()["total"]
        await client.post(
            f"{API_PREFIX}/remediation-plans",
            json=_make_remediation_create(),
        )
        resp2 = await client.get(f"{API_PREFIX}/remediation-plans")
        assert resp2.json()["total"] == before + 1

    @pytest.mark.anyio
    async def test_update_remediation_plan(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/remediation-plans/RP-001",
            json={"remediation_status": "completed", "notes": "Done"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["remediation_status"] == "completed"
        assert data["notes"] == "Done"

    @pytest.mark.anyio
    async def test_update_remediation_plan_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/remediation-plans/NONEXISTENT",
            json={"notes": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_remediation_plan(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/remediation-plans/RP-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/remediation-plans/RP-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_remediation_plan_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/remediation-plans/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_filter_by_trial_id(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/remediation-plans",
            params={"trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_filter_by_remediation_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/remediation-plans",
            params={"remediation_status": "completed"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["remediation_status"] == "completed"


# ===================================================================
# METRICS
# ===================================================================


class TestMetrics:
    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_questionnaires" in data
        assert "total_responses" in data
        assert "total_competency_records" in data
        assert "total_remediation_plans" in data
        assert "average_score_pct" in data
        assert "pass_rate" in data
        assert "certification_rate" in data
        assert "remediation_completion_rate" in data

    @pytest.mark.anyio
    async def test_metrics_total_questionnaires(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_questionnaires"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_responses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_responses"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_competency_records(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_competency_records"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_remediation_plans(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_remediation_plans"] == 12

    @pytest.mark.anyio
    async def test_metrics_has_breakdowns(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert isinstance(data["questionnaires_by_status"], dict)
        assert isinstance(data["responses_by_result"], dict)
        assert isinstance(data["records_by_level"], dict)
        assert isinstance(data["plans_by_status"], dict)

    @pytest.mark.anyio
    async def test_metrics_filter_by_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_questionnaires"] == 4
        assert data["total_responses"] == 4
        assert data["total_competency_records"] == 4
        assert data["total_remediation_plans"] == 4

    def test_metrics_service_level(self, svc: ProtocolKnowledgeAssessmentService):
        metrics = svc.get_metrics()
        assert metrics.total_questionnaires == 12
        assert metrics.total_responses == 12
        assert metrics.total_competency_records == 12
        assert metrics.total_remediation_plans == 12


# ===================================================================
# EDGE CASES & UPDATE PRESERVATION
# ===================================================================


class TestEdgeCases:
    @pytest.mark.anyio
    async def test_update_questionnaire_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessment-questionnaires/AQ-001")
        original = resp.json()
        original_title = original["questionnaire_title"]

        resp2 = await client.put(
            f"{API_PREFIX}/assessment-questionnaires/AQ-001",
            json={"notes": "Partial update"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["questionnaire_title"] == original_title
        assert updated["notes"] == "Partial update"

    @pytest.mark.anyio
    async def test_update_response_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessment-responses/AR-001")
        original = resp.json()
        original_name = original["respondent_name"]

        resp2 = await client.put(
            f"{API_PREFIX}/assessment-responses/AR-001",
            json={"notes": "Updated response note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["respondent_name"] == original_name

    @pytest.mark.anyio
    async def test_update_competency_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/competency-records/CR-001")
        original = resp.json()
        original_staff = original["staff_name"]

        resp2 = await client.put(
            f"{API_PREFIX}/competency-records/CR-001",
            json={"notes": "Updated competency note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["staff_name"] == original_staff

    @pytest.mark.anyio
    async def test_update_remediation_preserves_unmodified(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/remediation-plans/RP-001")
        original = resp.json()
        original_gaps = original["knowledge_gaps"]

        resp2 = await client.put(
            f"{API_PREFIX}/remediation-plans/RP-001",
            json={"notes": "Updated plan note"},
        )
        assert resp2.status_code == 200
        updated = resp2.json()
        assert updated["knowledge_gaps"] == original_gaps


# ===================================================================
# SINGLETON PATTERN
# ===================================================================


class TestSingleton:
    def test_get_returns_same_instance(self):
        svc1 = get_protocol_knowledge_assessment_service()
        svc2 = get_protocol_knowledge_assessment_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        svc1 = get_protocol_knowledge_assessment_service()
        svc2 = reset_protocol_knowledge_assessment_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_protocol_knowledge_assessment_service()
        svc.delete_assessment_questionnaire("AQ-001")
        assert svc.get_assessment_questionnaire("AQ-001") is None
        svc2 = reset_protocol_knowledge_assessment_service()
        assert svc2.get_assessment_questionnaire("AQ-001") is not None


# ===================================================================
# SERVICE-LEVEL CRUD
# ===================================================================


class TestServiceLevelCRUD:
    def test_list_questionnaires_service(self, svc: ProtocolKnowledgeAssessmentService):
        items = svc.list_assessment_questionnaires()
        assert len(items) == 12

    def test_get_questionnaire_service(self, svc: ProtocolKnowledgeAssessmentService):
        record = svc.get_assessment_questionnaire("AQ-001")
        assert record is not None
        assert record.id == "AQ-001"

    def test_list_responses_service(self, svc: ProtocolKnowledgeAssessmentService):
        items = svc.list_assessment_responses()
        assert len(items) == 12

    def test_get_response_service(self, svc: ProtocolKnowledgeAssessmentService):
        record = svc.get_assessment_response("AR-001")
        assert record is not None
        assert record.id == "AR-001"

    def test_list_competency_service(self, svc: ProtocolKnowledgeAssessmentService):
        items = svc.list_competency_records()
        assert len(items) == 12

    def test_get_competency_service(self, svc: ProtocolKnowledgeAssessmentService):
        record = svc.get_competency_record("CR-001")
        assert record is not None
        assert record.id == "CR-001"

    def test_list_remediation_service(self, svc: ProtocolKnowledgeAssessmentService):
        items = svc.list_remediation_plans()
        assert len(items) == 12

    def test_get_remediation_service(self, svc: ProtocolKnowledgeAssessmentService):
        record = svc.get_remediation_plan("RP-001")
        assert record is not None
        assert record.id == "RP-001"

    def test_delete_questionnaire_service(self, svc: ProtocolKnowledgeAssessmentService):
        assert svc.delete_assessment_questionnaire("AQ-001") is True
        assert svc.get_assessment_questionnaire("AQ-001") is None

    def test_delete_nonexistent_returns_false(self, svc: ProtocolKnowledgeAssessmentService):
        assert svc.delete_assessment_questionnaire("NONEXISTENT") is False

    def test_filter_questionnaire_by_trial(self, svc: ProtocolKnowledgeAssessmentService):
        items = svc.list_assessment_questionnaires(trial_id=EYLEA_TRIAL)
        for item in items:
            assert item.trial_id == EYLEA_TRIAL

    def test_filter_responses_by_result(self, svc: ProtocolKnowledgeAssessmentService):
        items = svc.list_assessment_responses(assessment_result=AssessmentResult.PASS)
        for item in items:
            assert item.assessment_result == AssessmentResult.PASS

    def test_filter_competency_by_level(self, svc: ProtocolKnowledgeAssessmentService):
        items = svc.list_competency_records(competency_level=CompetencyLevel.EXPERT)
        for item in items:
            assert item.competency_level == CompetencyLevel.EXPERT

    def test_filter_remediation_by_status(self, svc: ProtocolKnowledgeAssessmentService):
        items = svc.list_remediation_plans(remediation_status=RemediationStatus.COMPLETED)
        for item in items:
            assert item.remediation_status == RemediationStatus.COMPLETED


# ===================================================================
# BULK / MULTI-ENTITY
# ===================================================================


class TestBulkOperations:
    @pytest.mark.anyio
    async def test_create_multiple_questionnaires(self, client: AsyncClient):
        for i in range(3):
            resp = await client.post(
                f"{API_PREFIX}/assessment-questionnaires",
                json=_make_questionnaire_create(questionnaire_title=f"Bulk Test {i}"),
            )
            assert resp.status_code == 201
        resp = await client.get(f"{API_PREFIX}/assessment-questionnaires")
        assert resp.json()["total"] == 15  # 12 seed + 3 new

    @pytest.mark.anyio
    async def test_delete_multiple_remediation_plans(self, client: AsyncClient):
        for plan_id in ["RP-001", "RP-002", "RP-003"]:
            resp = await client.delete(f"{API_PREFIX}/remediation-plans/{plan_id}")
            assert resp.status_code == 204
        resp = await client.get(f"{API_PREFIX}/remediation-plans")
        assert resp.json()["total"] == 9  # 12 seed - 3 deleted


# ===================================================================
# RESPONSE STRUCTURE
# ===================================================================


class TestAPIResponseStructure:
    @pytest.mark.anyio
    async def test_questionnaire_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessment-questionnaires/AQ-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "questionnaire_title", "version",
            "questionnaire_status", "total_questions", "passing_score_pct",
            "authored_by", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_response_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessment-responses/AR-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "questionnaire_id", "respondent_name",
            "respondent_role", "site_id", "assessment_result", "score_pct",
            "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_competency_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/competency-records/CR-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "staff_name", "staff_role", "site_id",
            "competency_level", "certification_valid", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_remediation_response_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/remediation-plans/RP-001")
        assert resp.status_code == 200
        data = resp.json()
        for field in [
            "id", "trial_id", "staff_name", "site_id", "remediation_status",
            "knowledge_gaps", "remediation_activities", "assigned_by",
            "due_date", "created_at",
        ]:
            assert field in data

    @pytest.mark.anyio
    async def test_list_response_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessment-questionnaires")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
