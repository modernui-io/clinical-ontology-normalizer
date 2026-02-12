"""Tests for Benefit-Risk Assessment (CLINICAL-8).

Covers:
- Seed data verification (assessments, benefit outcomes, risk outcomes)
- Assessment CRUD (create, read, update, delete, list, filter by trial/status/framework/drug)
- Assessment lifecycle (finalize, supersede)
- Benefit outcome CRUD (create, read, update, delete, list per assessment)
- Risk outcome CRUD (create, read, update, delete, list per assessment)
- Metrics computation
- Error handling (404s, 400s, invalid lifecycle transitions)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.benefit_risk_assessment import (
    AssessmentFramework,
    AssessmentStatus,
    OutcomeCategory,
    SeverityLevel,
    LikelihoodLevel,
)
from app.services.benefit_risk_assessment_service import (
    BenefitRiskAssessmentService,
    get_benefit_risk_assessment_service,
    reset_benefit_risk_assessment_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/benefit-risk-assessment"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_benefit_risk_assessment_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> BenefitRiskAssessmentService:
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
        "drug_name": "Test Drug",
        "indication": "Test Indication",
        "comparator": "Placebo",
        "framework": "fda_brf",
        "assessor": "Dr. Test Assessor",
    }
    defaults.update(overrides)
    return defaults


def _make_benefit_create(**overrides) -> dict:
    defaults = {
        "outcome_name": "Test Benefit Outcome",
        "category": "efficacy",
        "description": "A test benefit outcome for unit testing",
        "effect_size": 0.75,
        "confidence_interval": "0.55-0.95",
        "p_value": 0.01,
        "clinical_significance": "Clinically meaningful improvement",
        "weight": 3.0,
    }
    defaults.update(overrides)
    return defaults


def _make_risk_create(**overrides) -> dict:
    defaults = {
        "outcome_name": "Test Risk Outcome",
        "category": "safety",
        "description": "A test risk outcome for unit testing",
        "incidence_rate": 5.0,
        "relative_risk": 2.0,
        "severity": "moderate",
        "likelihood": "uncommon",
        "reversibility": "Reversible with treatment",
        "management_strategy": "Monitor and treat as needed",
        "weight": 2.5,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_assessments_count(self, svc: BenefitRiskAssessmentService):
        assessments = svc.list_assessments()
        assert len(assessments) == 5

    def test_seed_assessments_all_statuses_present(self, svc: BenefitRiskAssessmentService):
        assessments = svc.list_assessments()
        statuses = {a.status for a in assessments}
        assert AssessmentStatus.DRAFT in statuses
        assert AssessmentStatus.IN_REVIEW in statuses
        assert AssessmentStatus.FINALIZED in statuses
        assert AssessmentStatus.SUPERSEDED in statuses

    def test_seed_assessments_all_frameworks_present(self, svc: BenefitRiskAssessmentService):
        assessments = svc.list_assessments()
        frameworks = {a.framework for a in assessments}
        assert AssessmentFramework.FDA_BRF in frameworks
        assert AssessmentFramework.EMA_EFFECTS_TABLE in frameworks
        assert AssessmentFramework.MCDA in frameworks
        assert AssessmentFramework.PROACT_URL in frameworks

    def test_seed_benefit_outcomes_count(self, svc: BenefitRiskAssessmentService):
        # BRA-001: 4, BRA-002: 4, BRA-003: 2, BRA-005: 2 = 12
        total = 0
        for a in svc.list_assessments():
            total += len(svc.list_benefits(a.id))
        assert total == 12

    def test_seed_risk_outcomes_count(self, svc: BenefitRiskAssessmentService):
        # BRA-001: 4, BRA-002: 4, BRA-003: 2, BRA-005: 2 = 12
        total = 0
        for a in svc.list_assessments():
            total += len(svc.list_risks(a.id))
        assert total == 12

    def test_seed_oncology_assessment(self, svc: BenefitRiskAssessmentService):
        assessment = svc.get_assessment("BRA-001")
        assert assessment is not None
        assert assessment.drug_name == "Cemiplimab (Libtayo)"
        assert assessment.status == AssessmentStatus.FINALIZED
        assert assessment.framework == AssessmentFramework.FDA_BRF

    def test_seed_autoimmune_assessment(self, svc: BenefitRiskAssessmentService):
        assessment = svc.get_assessment("BRA-002")
        assert assessment is not None
        assert assessment.drug_name == "Dupilumab (Dupixent)"
        assert assessment.status == AssessmentStatus.FINALIZED
        assert assessment.framework == AssessmentFramework.EMA_EFFECTS_TABLE

    def test_seed_ophthalmology_assessment_draft(self, svc: BenefitRiskAssessmentService):
        assessment = svc.get_assessment("BRA-003")
        assert assessment is not None
        assert assessment.drug_name == "Aflibercept (Eylea)"
        assert assessment.status == AssessmentStatus.DRAFT
        assert assessment.finalized_date is None

    def test_seed_superseded_assessment(self, svc: BenefitRiskAssessmentService):
        assessment = svc.get_assessment("BRA-004")
        assert assessment is not None
        assert assessment.status == AssessmentStatus.SUPERSEDED

    def test_seed_in_review_assessment(self, svc: BenefitRiskAssessmentService):
        assessment = svc.get_assessment("BRA-005")
        assert assessment is not None
        assert assessment.status == AssessmentStatus.IN_REVIEW

    def test_seed_finalized_has_date(self, svc: BenefitRiskAssessmentService):
        assessment = svc.get_assessment("BRA-001")
        assert assessment is not None
        assert assessment.finalized_date is not None

    def test_seed_benefits_have_required_fields(self, svc: BenefitRiskAssessmentService):
        benefits = svc.list_benefits("BRA-001")
        for b in benefits:
            assert b.id
            assert b.assessment_id == "BRA-001"
            assert b.outcome_name
            assert b.category is not None
            assert b.description

    def test_seed_risks_have_required_fields(self, svc: BenefitRiskAssessmentService):
        risks = svc.list_risks("BRA-001")
        for r in risks:
            assert r.id
            assert r.assessment_id == "BRA-001"
            assert r.outcome_name
            assert r.category is not None
            assert r.severity is not None
            assert r.likelihood is not None


# =====================================================================
# ASSESSMENT CRUD
# =====================================================================


class TestAssessmentCrud:
    """Test assessment create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 5

    @pytest.mark.anyio
    async def test_list_assessments_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assessments", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_assessments_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assessments", params={"status": "finalized"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["status"] == "finalized"

    @pytest.mark.anyio
    async def test_list_assessments_filter_framework(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assessments", params={"framework": "fda_brf"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["framework"] == "fda_brf"

    @pytest.mark.anyio
    async def test_list_assessments_filter_drug_name(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assessments", params={"drug_name": "Cemiplimab"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert "Cemiplimab" in item["drug_name"]

    @pytest.mark.anyio
    async def test_get_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/BRA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "BRA-001"
        assert data["drug_name"] == "Cemiplimab (Libtayo)"

    @pytest.mark.anyio
    async def test_get_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/BRA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_assessment(self, client: AsyncClient):
        payload = _make_assessment_create()
        resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["drug_name"] == "Test Drug"
        assert data["status"] == "draft"
        assert data["id"].startswith("BRA-")

    @pytest.mark.anyio
    async def test_create_assessment_with_optional_fields(self, client: AsyncClient):
        payload = _make_assessment_create(
            overall_conclusion="Favorable benefit-risk profile",
            regulatory_context="Pre-NDA",
            target_population="Adults with condition X",
        )
        resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["overall_conclusion"] == "Favorable benefit-risk profile"
        assert data["regulatory_context"] == "Pre-NDA"
        assert data["target_population"] == "Adults with condition X"

    @pytest.mark.anyio
    async def test_update_assessment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assessments/BRA-003",
            json={"drug_name": "Updated Drug Name", "assessor": "Dr. Updated"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["drug_name"] == "Updated Drug Name"
        assert data["assessor"] == "Dr. Updated"

    @pytest.mark.anyio
    async def test_update_assessment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assessments/BRA-NONEXISTENT",
            json={"drug_name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_finalized_assessment_rejected(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assessments/BRA-001",
            json={"drug_name": "Should Fail"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_superseded_assessment_rejected(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/assessments/BRA-004",
            json={"drug_name": "Should Fail"},
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_delete_draft_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assessments/BRA-003")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/assessments/BRA-003")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assessment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assessments/BRA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_finalized_assessment_rejected(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assessments/BRA-001")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_assessments_sorted_by_date_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        data = resp.json()
        dates = [item["assessment_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)


# =====================================================================
# ASSESSMENT LIFECYCLE
# =====================================================================


class TestAssessmentLifecycle:
    """Test assessment lifecycle transitions (finalize, supersede)."""

    @pytest.mark.anyio
    async def test_finalize_draft_assessment(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/assessments/BRA-003/finalize")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "finalized"
        assert data["finalized_date"] is not None

    @pytest.mark.anyio
    async def test_finalize_in_review_assessment(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/assessments/BRA-005/finalize")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "finalized"

    @pytest.mark.anyio
    async def test_finalize_already_finalized_rejected(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/assessments/BRA-001/finalize")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_finalize_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/assessments/BRA-NONEXISTENT/finalize")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_supersede_finalized_assessment(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/assessments/BRA-001/supersede")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "superseded"

    @pytest.mark.anyio
    async def test_supersede_draft_rejected(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/assessments/BRA-003/supersede")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_supersede_not_found(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/assessments/BRA-NONEXISTENT/supersede")
        assert resp.status_code == 404


# =====================================================================
# BENEFIT OUTCOME CRUD
# =====================================================================


class TestBenefitOutcomeCrud:
    """Test benefit outcome CRUD operations."""

    @pytest.mark.anyio
    async def test_list_benefits_for_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/BRA-001/benefits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["assessment_id"] == "BRA-001"

    @pytest.mark.anyio
    async def test_list_benefits_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/BRA-NONEXISTENT/benefits")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_benefits_empty(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/BRA-004/benefits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_get_benefit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/benefits/BEN-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "BEN-001"
        assert data["outcome_name"] == "Overall Response Rate (ORR)"

    @pytest.mark.anyio
    async def test_get_benefit_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/benefits/BEN-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_benefit(self, client: AsyncClient):
        payload = _make_benefit_create()
        resp = await client.post(f"{API_PREFIX}/assessments/BRA-001/benefits", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["outcome_name"] == "Test Benefit Outcome"
        assert data["assessment_id"] == "BRA-001"
        assert data["id"].startswith("BEN-")

    @pytest.mark.anyio
    async def test_create_benefit_assessment_not_found(self, client: AsyncClient):
        payload = _make_benefit_create()
        resp = await client.post(
            f"{API_PREFIX}/assessments/BRA-NONEXISTENT/benefits", json=payload
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_benefit(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/benefits/BEN-001",
            json={"outcome_name": "Updated ORR", "weight": 5.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome_name"] == "Updated ORR"
        assert data["weight"] == 5.0

    @pytest.mark.anyio
    async def test_update_benefit_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/benefits/BEN-NONEXISTENT",
            json={"outcome_name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_benefit(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/benefits/BEN-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/benefits/BEN-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_benefit_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/benefits/BEN-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_benefits_sorted_by_weight_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/BRA-001/benefits")
        data = resp.json()
        weights = [item["weight"] for item in data["items"]]
        assert weights == sorted(weights, reverse=True)


# =====================================================================
# RISK OUTCOME CRUD
# =====================================================================


class TestRiskOutcomeCrud:
    """Test risk outcome CRUD operations."""

    @pytest.mark.anyio
    async def test_list_risks_for_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/BRA-001/risks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["assessment_id"] == "BRA-001"

    @pytest.mark.anyio
    async def test_list_risks_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/BRA-NONEXISTENT/risks")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_risks_empty(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/BRA-004/risks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_get_risk(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks/RSK-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RSK-001"
        assert data["outcome_name"] == "Hepatotoxicity (Grade 3+)"

    @pytest.mark.anyio
    async def test_get_risk_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks/RSK-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_risk(self, client: AsyncClient):
        payload = _make_risk_create()
        resp = await client.post(f"{API_PREFIX}/assessments/BRA-001/risks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["outcome_name"] == "Test Risk Outcome"
        assert data["assessment_id"] == "BRA-001"
        assert data["id"].startswith("RSK-")

    @pytest.mark.anyio
    async def test_create_risk_assessment_not_found(self, client: AsyncClient):
        payload = _make_risk_create()
        resp = await client.post(
            f"{API_PREFIX}/assessments/BRA-NONEXISTENT/risks", json=payload
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_risk(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/risks/RSK-001",
            json={"outcome_name": "Updated Hepatotoxicity", "weight": 5.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["outcome_name"] == "Updated Hepatotoxicity"
        assert data["weight"] == 5.0

    @pytest.mark.anyio
    async def test_update_risk_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/risks/RSK-NONEXISTENT",
            json={"outcome_name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_risk(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/risks/RSK-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/risks/RSK-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_risk_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/risks/RSK-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_risks_sorted_by_weight_descending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/BRA-001/risks")
        data = resp.json()
        weights = [item["weight"] for item in data["items"]]
        assert weights == sorted(weights, reverse=True)


# =====================================================================
# METRICS
# =====================================================================


class TestBenefitRiskMetrics:
    """Test benefit-risk assessment metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_assessments"] == 5
        assert data["total_benefit_outcomes"] == 12
        assert data["total_risk_outcomes"] == 12
        assert data["finalized_assessments"] == 2
        assert data["superseded_assessments"] == 1

    @pytest.mark.anyio
    async def test_metrics_assessments_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["assessments_by_status"]
        total_by_status = sum(by_status.values())
        assert total_by_status == data["total_assessments"]

    @pytest.mark.anyio
    async def test_metrics_assessments_by_framework(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_framework = data["assessments_by_framework"]
        total_by_framework = sum(by_framework.values())
        assert total_by_framework == data["total_assessments"]

    @pytest.mark.anyio
    async def test_metrics_averages(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_benefits_per_assessment"] > 0
        assert data["avg_risks_per_assessment"] > 0

    def test_metrics_service_direct(self, svc: BenefitRiskAssessmentService):
        metrics = svc.get_metrics()
        assert metrics.total_assessments == 5
        assert metrics.finalized_assessments == 2
        assert metrics.superseded_assessments == 1
        assert metrics.total_benefit_outcomes == 12
        assert metrics.total_risk_outcomes == 12

    def test_metrics_status_counts(self, svc: BenefitRiskAssessmentService):
        metrics = svc.get_metrics()
        assert metrics.assessments_by_status.get("draft", 0) == 1
        assert metrics.assessments_by_status.get("in_review", 0) == 1
        assert metrics.assessments_by_status.get("finalized", 0) == 2
        assert metrics.assessments_by_status.get("superseded", 0) == 1

    def test_metrics_framework_counts(self, svc: BenefitRiskAssessmentService):
        metrics = svc.get_metrics()
        assert metrics.assessments_by_framework.get("fda_brf", 0) == 1
        assert metrics.assessments_by_framework.get("ema_effects_table", 0) == 2
        assert metrics.assessments_by_framework.get("mcda", 0) == 1
        assert metrics.assessments_by_framework.get("proact_url", 0) == 1


# =====================================================================
# DELETING ASSESSMENT CASCADES
# =====================================================================


class TestDeleteCascade:
    """Test that deleting an assessment removes associated outcomes."""

    @pytest.mark.anyio
    async def test_delete_assessment_removes_benefits(self, client: AsyncClient):
        # BRA-003 is draft with benefits BEN-009 and BEN-010
        resp = await client.get(f"{API_PREFIX}/benefits/BEN-009")
        assert resp.status_code == 200

        resp = await client.delete(f"{API_PREFIX}/assessments/BRA-003")
        assert resp.status_code == 204

        resp = await client.get(f"{API_PREFIX}/benefits/BEN-009")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assessment_removes_risks(self, client: AsyncClient):
        # BRA-003 is draft with risks RSK-009 and RSK-010
        resp = await client.get(f"{API_PREFIX}/risks/RSK-009")
        assert resp.status_code == 200

        resp = await client.delete(f"{API_PREFIX}/assessments/BRA-003")
        assert resp.status_code == 204

        resp = await client.get(f"{API_PREFIX}/risks/RSK-009")
        assert resp.status_code == 404


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_benefit_risk_assessment_service()
        svc2 = get_benefit_risk_assessment_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_benefit_risk_assessment_service()
        svc2 = reset_benefit_risk_assessment_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_benefit_risk_assessment_service()
        svc.delete_assessment("BRA-003")
        assert svc.get_assessment("BRA-003") is None
        svc2 = reset_benefit_risk_assessment_service()
        assert svc2.get_assessment("BRA-003") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_assessments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_assessments_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assessments", params={"trial_id": "NONEXISTENT"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_create_assessment_all_frameworks(self, client: AsyncClient):
        for fw in ["fda_brf", "ema_effects_table", "mcda", "proact_url", "incremental_net_benefit"]:
            payload = _make_assessment_create(framework=fw, drug_name=f"Drug-{fw}")
            resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["framework"] == fw

    @pytest.mark.anyio
    async def test_create_benefit_all_categories(self, client: AsyncClient):
        for cat in ["efficacy", "safety", "tolerability", "convenience", "quality_of_life"]:
            payload = _make_benefit_create(category=cat, outcome_name=f"Outcome-{cat}")
            resp = await client.post(
                f"{API_PREFIX}/assessments/BRA-001/benefits", json=payload
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["category"] == cat

    @pytest.mark.anyio
    async def test_create_risk_all_severities(self, client: AsyncClient):
        for sev in ["mild", "moderate", "severe", "life_threatening", "fatal"]:
            payload = _make_risk_create(severity=sev, outcome_name=f"Risk-{sev}")
            resp = await client.post(
                f"{API_PREFIX}/assessments/BRA-001/risks", json=payload
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["severity"] == sev

    @pytest.mark.anyio
    async def test_create_risk_all_likelihoods(self, client: AsyncClient):
        for lk in ["very_common", "common", "uncommon", "rare", "very_rare"]:
            payload = _make_risk_create(likelihood=lk, outcome_name=f"Risk-{lk}")
            resp = await client.post(
                f"{API_PREFIX}/assessments/BRA-001/risks", json=payload
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["likelihood"] == lk

    @pytest.mark.anyio
    async def test_assessment_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/BRA-001")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "drug_name" in data
        assert "indication" in data
        assert "comparator" in data
        assert "assessment_number" in data
        assert "version" in data
        assert "status" in data
        assert "framework" in data
        assert "assessor" in data
        assert "assessment_date" in data

    @pytest.mark.anyio
    async def test_benefit_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/benefits/BEN-001")
        data = resp.json()
        assert "id" in data
        assert "assessment_id" in data
        assert "outcome_name" in data
        assert "category" in data
        assert "description" in data
        assert "weight" in data

    @pytest.mark.anyio
    async def test_risk_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks/RSK-001")
        data = resp.json()
        assert "id" in data
        assert "assessment_id" in data
        assert "outcome_name" in data
        assert "category" in data
        assert "description" in data
        assert "severity" in data
        assert "likelihood" in data
        assert "weight" in data

    @pytest.mark.anyio
    async def test_metrics_has_correct_structure(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "total_assessments" in data
        assert "assessments_by_status" in data
        assert "assessments_by_framework" in data
        assert "total_benefit_outcomes" in data
        assert "total_risk_outcomes" in data
        assert "avg_benefits_per_assessment" in data
        assert "avg_risks_per_assessment" in data
        assert "finalized_assessments" in data
        assert "superseded_assessments" in data
