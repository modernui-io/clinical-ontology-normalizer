"""Tests for Bioequivalence Study Management (BE-STUDY).

Covers:
- Seed data verification (BE studies, PK parameters, formulation comparisons,
  statistical assessments, regulatory filings)
- BE study CRUD (create, read, update, delete, list, filter by trial/status/design/result)
- PK parameter CRUD (create, read, update, delete, list, filter by trial/study/name)
- Formulation comparison CRUD (create, read, update, delete, list, filter by trial/study/result)
- Statistical assessment CRUD (create, read, update, delete, list, filter by trial/study)
- Regulatory filing CRUD (create, read, update, delete, list, filter by trial/study/status)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
- Filtering edge cases and enum coverage
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.bioequivalence import (
    BECriterion,
    BEResult,
    PKParameterName,
    StudyDesign,
    StudyStatus,
)
from app.services.bioequivalence_service import (
    BioequivalenceService,
    get_bioequivalence_service,
    reset_bioequivalence_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/bioequivalence"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_bioequivalence_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> BioequivalenceService:
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


def _make_be_study_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "study_name": "Test BE Study",
        "study_design": "crossover_2x2",
        "reference_product": "Reference Product A",
        "test_product": "Test Product B",
        "dosage_strength": "100mg",
        "principal_investigator": "Dr. Test Investigator",
        "subjects_planned": 50,
    }
    defaults.update(overrides)
    return defaults


def _make_pk_parameter_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "study_id": "BE-001",
        "parameter_name": "AUC_0_inf",
        "formulation": "test",
        "analyzed_by": "Dr. Test Analyst",
        "subject_count": 30,
    }
    defaults.update(overrides)
    return defaults


def _make_formulation_comparison_create(**overrides) -> dict:
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "study_id": "BE-004",
        "parameter_name": "Cmax",
        "be_criterion": "80_125",
        "analyzed_by": "Dr. Test Analyst",
        "method": "ANOVA",
    }
    defaults.update(overrides)
    return defaults


def _make_statistical_assessment_create(**overrides) -> dict:
    defaults = {
        "trial_id": LIBTAYO_TRIAL,
        "study_id": "BE-008",
        "assessment_name": "Test Statistical Assessment",
        "assessed_by": "Dr. Test Statistician",
        "model_used": "mixed_effects_ANOVA",
        "factors": ["sequence", "period", "treatment"],
    }
    defaults.update(overrides)
    return defaults


def _make_regulatory_filing_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "study_id": "BE-001",
        "filing_type": "ANDA",
        "regulatory_authority": "FDA",
        "prepared_by": "Dr. Test Preparer",
        "target_date": (now + timedelta(days=60)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_be_studies_count(self, svc: BioequivalenceService):
        studies = svc.list_be_studies()
        assert len(studies) == 12

    def test_seed_pk_parameters_count(self, svc: BioequivalenceService):
        params = svc.list_pk_parameters()
        assert len(params) == 12

    def test_seed_formulation_comparisons_count(self, svc: BioequivalenceService):
        comparisons = svc.list_formulation_comparisons()
        assert len(comparisons) == 12

    def test_seed_statistical_assessments_count(self, svc: BioequivalenceService):
        assessments = svc.list_statistical_assessments()
        assert len(assessments) == 10

    def test_seed_regulatory_filings_count(self, svc: BioequivalenceService):
        filings = svc.list_regulatory_filings()
        assert len(filings) == 10

    def test_seed_studies_cover_all_trials(self, svc: BioequivalenceService):
        studies = svc.list_be_studies()
        trial_ids = {s.trial_id for s in studies}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_studies_have_multiple_designs(self, svc: BioequivalenceService):
        studies = svc.list_be_studies()
        designs = {s.study_design for s in studies}
        assert len(designs) >= 4

    def test_seed_studies_have_multiple_statuses(self, svc: BioequivalenceService):
        studies = svc.list_be_studies()
        statuses = {s.status for s in studies}
        assert StudyStatus.COMPLETED in statuses
        assert StudyStatus.IN_PROGRESS in statuses
        assert StudyStatus.PLANNED in statuses

    def test_seed_studies_have_be_and_not_be_results(self, svc: BioequivalenceService):
        studies = svc.list_be_studies()
        results = {s.overall_result for s in studies}
        assert BEResult.BIOEQUIVALENT in results
        assert BEResult.NOT_BIOEQUIVALENT in results
        assert BEResult.PENDING in results

    def test_seed_pk_parameters_have_multiple_names(self, svc: BioequivalenceService):
        params = svc.list_pk_parameters()
        names = {p.parameter_name for p in params}
        assert len(names) >= 4

    def test_seed_comparisons_have_within_and_outside_limits(self, svc: BioequivalenceService):
        comparisons = svc.list_formulation_comparisons()
        within = [c for c in comparisons if c.within_limits]
        outside = [c for c in comparisons if not c.within_limits]
        assert len(within) >= 1
        assert len(outside) >= 1

    def test_seed_filings_have_multiple_statuses(self, svc: BioequivalenceService):
        filings = svc.list_regulatory_filings()
        statuses = {f.status for f in filings}
        assert "draft" in statuses
        assert "submitted" in statuses
        assert "approved" in statuses


# =====================================================================
# BE STUDY CRUD
# =====================================================================


class TestBEStudyCrud:
    """Test BE study CRUD operations."""

    @pytest.mark.anyio
    async def test_list_be_studies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_be_studies_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_be_studies_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies", params={"status": "completed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_be_studies_filter_design(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies", params={"study_design": "crossover_2x2"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["study_design"] == "crossover_2x2"

    @pytest.mark.anyio
    async def test_list_be_studies_filter_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies", params={"overall_result": "bioequivalent"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["overall_result"] == "bioequivalent"

    @pytest.mark.anyio
    async def test_get_be_study(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/BE-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "BE-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_be_study_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/BE-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_be_study(self, client: AsyncClient):
        payload = _make_be_study_create()
        resp = await client.post(f"{API_PREFIX}/studies", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["study_design"] == "crossover_2x2"
        assert data["status"] == "planned"
        assert data["overall_result"] == "pending"
        assert data["id"].startswith("BE-")

    @pytest.mark.anyio
    async def test_update_be_study(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/studies/BE-002",
            json={"status": "completed", "overall_result": "bioequivalent", "notes": "Done"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["overall_result"] == "bioequivalent"
        assert data["notes"] == "Done"

    @pytest.mark.anyio
    async def test_update_be_study_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/studies/BE-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_be_study(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/studies/BE-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/studies/BE-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_be_study_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/studies/BE-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# PK PARAMETER CRUD
# =====================================================================


class TestPKParameterCrud:
    """Test PK parameter CRUD operations."""

    @pytest.mark.anyio
    async def test_list_pk_parameters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pk-parameters")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_pk_parameters_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/pk-parameters", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_pk_parameters_filter_study(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/pk-parameters", params={"study_id": "BE-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["study_id"] == "BE-001"

    @pytest.mark.anyio
    async def test_list_pk_parameters_filter_name(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/pk-parameters", params={"parameter_name": "Cmax"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["parameter_name"] == "Cmax"

    @pytest.mark.anyio
    async def test_get_pk_parameter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pk-parameters/PK-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PK-001"
        assert data["parameter_name"] == "AUC_0_inf"

    @pytest.mark.anyio
    async def test_get_pk_parameter_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pk-parameters/PK-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_pk_parameter(self, client: AsyncClient):
        payload = _make_pk_parameter_create()
        resp = await client.post(f"{API_PREFIX}/pk-parameters", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["parameter_name"] == "AUC_0_inf"
        assert data["id"].startswith("PK-")

    @pytest.mark.anyio
    async def test_update_pk_parameter(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/pk-parameters/PK-001",
            json={"geometric_mean": 4600.0, "cv_pct": 29.0, "notes": "Updated"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["geometric_mean"] == 4600.0
        assert data["cv_pct"] == 29.0
        assert data["notes"] == "Updated"

    @pytest.mark.anyio
    async def test_update_pk_parameter_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/pk-parameters/PK-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_pk_parameter(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/pk-parameters/PK-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/pk-parameters/PK-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_pk_parameter_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/pk-parameters/PK-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# FORMULATION COMPARISON CRUD
# =====================================================================


class TestFormulationComparisonCrud:
    """Test formulation comparison CRUD operations."""

    @pytest.mark.anyio
    async def test_list_formulation_comparisons(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/formulation-comparisons")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_formulation_comparisons_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/formulation-comparisons", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_formulation_comparisons_filter_study(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/formulation-comparisons", params={"study_id": "BE-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["study_id"] == "BE-001"

    @pytest.mark.anyio
    async def test_list_formulation_comparisons_filter_result(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/formulation-comparisons", params={"result": "bioequivalent"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["result"] == "bioequivalent"

    @pytest.mark.anyio
    async def test_get_formulation_comparison(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/formulation-comparisons/FC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "FC-001"
        assert data["result"] == "bioequivalent"
        assert data["within_limits"] is True

    @pytest.mark.anyio
    async def test_get_formulation_comparison_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/formulation-comparisons/FC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_formulation_comparison(self, client: AsyncClient):
        payload = _make_formulation_comparison_create()
        resp = await client.post(f"{API_PREFIX}/formulation-comparisons", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["result"] == "pending"
        assert data["id"].startswith("FC-")

    @pytest.mark.anyio
    async def test_update_formulation_comparison(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/formulation-comparisons/FC-007",
            json={
                "result": "bioequivalent",
                "ratio_pct": 101.5,
                "ci_lower_pct": 95.0,
                "ci_upper_pct": 108.3,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] == "bioequivalent"
        assert data["ratio_pct"] == 101.5

    @pytest.mark.anyio
    async def test_update_formulation_comparison_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/formulation-comparisons/FC-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_formulation_comparison(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/formulation-comparisons/FC-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/formulation-comparisons/FC-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_formulation_comparison_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/formulation-comparisons/FC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# STATISTICAL ASSESSMENT CRUD
# =====================================================================


class TestStatisticalAssessmentCrud:
    """Test statistical assessment CRUD operations."""

    @pytest.mark.anyio
    async def test_list_statistical_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/statistical-assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_statistical_assessments_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/statistical-assessments", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_statistical_assessments_filter_study(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/statistical-assessments", params={"study_id": "BE-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["study_id"] == "BE-001"

    @pytest.mark.anyio
    async def test_get_statistical_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/statistical-assessments/SA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SA-001"
        assert data["model_used"] == "mixed_effects_ANOVA"

    @pytest.mark.anyio
    async def test_get_statistical_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/statistical-assessments/SA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_statistical_assessment(self, client: AsyncClient):
        payload = _make_statistical_assessment_create()
        resp = await client.post(f"{API_PREFIX}/statistical-assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["model_used"] == "mixed_effects_ANOVA"
        assert data["id"].startswith("SA-")

    @pytest.mark.anyio
    async def test_update_statistical_assessment(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/statistical-assessments/SA-009",
            json={
                "sensitivity_analysis_done": True,
                "consistent_with_primary": True,
                "notes": "Full analysis completed",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sensitivity_analysis_done"] is True
        assert data["notes"] == "Full analysis completed"

    @pytest.mark.anyio
    async def test_update_statistical_assessment_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/statistical-assessments/SA-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_statistical_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/statistical-assessments/SA-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/statistical-assessments/SA-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_statistical_assessment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/statistical-assessments/SA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# REGULATORY FILING CRUD
# =====================================================================


class TestRegulatoryFilingCrud:
    """Test regulatory filing CRUD operations."""

    @pytest.mark.anyio
    async def test_list_regulatory_filings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/regulatory-filings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_regulatory_filings_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/regulatory-filings", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_regulatory_filings_filter_study(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/regulatory-filings", params={"study_id": "BE-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["study_id"] == "BE-001"

    @pytest.mark.anyio
    async def test_list_regulatory_filings_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/regulatory-filings", params={"status": "draft"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "draft"

    @pytest.mark.anyio
    async def test_get_regulatory_filing(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/regulatory-filings/RF-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RF-001"
        assert data["filing_type"] == "ANDA"
        assert data["regulatory_authority"] == "FDA"

    @pytest.mark.anyio
    async def test_get_regulatory_filing_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/regulatory-filings/RF-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_regulatory_filing(self, client: AsyncClient):
        payload = _make_regulatory_filing_create()
        resp = await client.post(f"{API_PREFIX}/regulatory-filings", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["filing_type"] == "ANDA"
        assert data["status"] == "draft"
        assert data["id"].startswith("RF-")

    @pytest.mark.anyio
    async def test_update_regulatory_filing(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/regulatory-filings/RF-005",
            json={
                "status": "submitted",
                "reviewer": "Dr. Review Board",
                "reference_number": "ANDA-2026-0001",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "submitted"
        assert data["reviewer"] == "Dr. Review Board"
        assert data["reference_number"] == "ANDA-2026-0001"

    @pytest.mark.anyio
    async def test_update_regulatory_filing_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/regulatory-filings/RF-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_regulatory_filing(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/regulatory-filings/RF-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/regulatory-filings/RF-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_regulatory_filing_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/regulatory-filings/RF-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestBioequivalenceMetrics:
    """Test bioequivalence metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_studies"] == 12
        assert data["total_pk_parameters"] == 12
        assert data["total_comparisons"] == 12
        assert data["total_assessments"] == 10
        assert data["total_filings"] == 10

    @pytest.mark.anyio
    async def test_metrics_studies_by_design(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_design = data["studies_by_design"]
        total = sum(by_design.values())
        assert total == data["total_studies"]

    @pytest.mark.anyio
    async def test_metrics_studies_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["studies_by_status"]
        total = sum(by_status.values())
        assert total == data["total_studies"]

    @pytest.mark.anyio
    async def test_metrics_studies_by_result(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_result = data["studies_by_result"]
        total = sum(by_result.values())
        assert total == data["total_studies"]

    @pytest.mark.anyio
    async def test_metrics_parameters_by_name(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_name = data["parameters_by_name"]
        total = sum(by_name.values())
        assert total == data["total_pk_parameters"]

    @pytest.mark.anyio
    async def test_metrics_comparisons_within_limits(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["comparisons_within_limits"] > 0
        assert data["comparisons_within_limits"] <= data["total_comparisons"]

    @pytest.mark.anyio
    async def test_metrics_filings_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["filings_by_status"]
        total = sum(by_status.values())
        assert total == data["total_filings"]


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_bioequivalence_service()
        svc2 = get_bioequivalence_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_bioequivalence_service()
        svc2 = reset_bioequivalence_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_bioequivalence_service()
        # Delete a study
        svc.delete_be_study("BE-001")
        assert svc.get_be_study("BE-001") is None
        # Reset should bring it back
        svc2 = reset_bioequivalence_service()
        assert svc2.get_be_study("BE-001") is not None


# =====================================================================
# FILTERING AND EDGE CASES
# =====================================================================


class TestFilteringAndEdgeCases:
    """Test filtering combinations and edge cases."""

    @pytest.mark.anyio
    async def test_list_studies_empty_filter(self, client: AsyncClient):
        """Filter by a trial that has no studies."""
        resp = await client.get(
            f"{API_PREFIX}/studies",
            params={"trial_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_list_comparisons_not_bioequivalent(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/formulation-comparisons", params={"result": "not_bioequivalent"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["result"] == "not_bioequivalent"

    @pytest.mark.anyio
    async def test_list_comparisons_inconclusive(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/formulation-comparisons", params={"result": "inconclusive"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["result"] == "inconclusive"

    @pytest.mark.anyio
    async def test_create_study_then_retrieve(self, client: AsyncClient):
        """Create a study and verify it shows in the list."""
        payload = _make_be_study_create()
        resp = await client.post(f"{API_PREFIX}/studies", json=payload)
        assert resp.status_code == 201
        created_id = resp.json()["id"]

        resp2 = await client.get(f"{API_PREFIX}/studies/{created_id}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == created_id

    @pytest.mark.anyio
    async def test_create_study_then_update_status(self, client: AsyncClient):
        """Create a study, then update its status through lifecycle."""
        payload = _make_be_study_create()
        resp = await client.post(f"{API_PREFIX}/studies", json=payload)
        assert resp.status_code == 201
        study_id = resp.json()["id"]
        assert resp.json()["status"] == "planned"

        # Update to enrolled
        resp2 = await client.put(
            f"{API_PREFIX}/studies/{study_id}",
            json={"status": "enrolled", "subjects_enrolled": 50},
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "enrolled"
        assert resp2.json()["subjects_enrolled"] == 50

        # Update to completed
        resp3 = await client.put(
            f"{API_PREFIX}/studies/{study_id}",
            json={"status": "completed", "overall_result": "bioequivalent"},
        )
        assert resp3.status_code == 200
        assert resp3.json()["status"] == "completed"
        assert resp3.json()["overall_result"] == "bioequivalent"

    @pytest.mark.anyio
    async def test_create_and_delete_pk_parameter(self, client: AsyncClient):
        """Create a PK parameter and then delete it."""
        payload = _make_pk_parameter_create()
        resp = await client.post(f"{API_PREFIX}/pk-parameters", json=payload)
        assert resp.status_code == 201
        pk_id = resp.json()["id"]

        resp2 = await client.delete(f"{API_PREFIX}/pk-parameters/{pk_id}")
        assert resp2.status_code == 204

        resp3 = await client.get(f"{API_PREFIX}/pk-parameters/{pk_id}")
        assert resp3.status_code == 404

    @pytest.mark.anyio
    async def test_create_filing_then_update_through_lifecycle(self, client: AsyncClient):
        """Create a filing and advance through draft -> submitted -> approved."""
        payload = _make_regulatory_filing_create()
        resp = await client.post(f"{API_PREFIX}/regulatory-filings", json=payload)
        assert resp.status_code == 201
        filing_id = resp.json()["id"]
        assert resp.json()["status"] == "draft"

        # Submit
        resp2 = await client.put(
            f"{API_PREFIX}/regulatory-filings/{filing_id}",
            json={"status": "submitted", "reference_number": "TEST-REF-001"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "submitted"

        # Approve
        resp3 = await client.put(
            f"{API_PREFIX}/regulatory-filings/{filing_id}",
            json={"status": "approved", "outcome": "approved"},
        )
        assert resp3.status_code == 200
        assert resp3.json()["status"] == "approved"
        assert resp3.json()["outcome"] == "approved"

    @pytest.mark.anyio
    async def test_studies_sorted_by_created_at_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        data = resp.json()
        dates = [item["created_at"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.anyio
    async def test_metrics_after_create_and_delete(self, client: AsyncClient):
        """Metrics should reflect dynamic changes."""
        # Get baseline metrics
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        baseline = resp1.json()

        # Create a new study
        payload = _make_be_study_create()
        await client.post(f"{API_PREFIX}/studies", json=payload)

        resp2 = await client.get(f"{API_PREFIX}/metrics")
        after_create = resp2.json()
        assert after_create["total_studies"] == baseline["total_studies"] + 1

        # Delete a study
        await client.delete(f"{API_PREFIX}/studies/BE-010")
        resp3 = await client.get(f"{API_PREFIX}/metrics")
        after_delete = resp3.json()
        assert after_delete["total_studies"] == baseline["total_studies"]

    @pytest.mark.anyio
    async def test_list_filings_combined_filters(self, client: AsyncClient):
        """Filter filings by both trial and status."""
        resp = await client.get(
            f"{API_PREFIX}/regulatory-filings",
            params={"trial_id": EYLEA_TRIAL, "status": "submitted"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["status"] == "submitted"


# =====================================================================
# ENUM COVERAGE
# =====================================================================


class TestEnumCoverage:
    """Verify enum values are represented in seed data."""

    @pytest.mark.anyio
    async def test_study_designs_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        data = resp.json()
        designs = {item["study_design"] for item in data["items"]}
        assert "crossover_2x2" in designs
        assert "crossover_3x3" in designs
        assert "parallel" in designs
        assert "replicate" in designs
        assert "sequential" in designs
        assert "adaptive" in designs

    @pytest.mark.anyio
    async def test_study_statuses_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "planned" in statuses
        assert "enrolled" in statuses
        assert "in_progress" in statuses
        assert "analysis" in statuses
        assert "completed" in statuses
        assert "failed" in statuses

    @pytest.mark.anyio
    async def test_be_criteria_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        data = resp.json()
        criteria = {item["be_criterion"] for item in data["items"]}
        assert "80_125" in criteria
        assert "90_111" in criteria
        assert "75_133" in criteria
        assert "scaled_ABE" in criteria
        assert "Tmax_nonparametric" in criteria

    @pytest.mark.anyio
    async def test_be_results_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        data = resp.json()
        results = {item["overall_result"] for item in data["items"]}
        assert "bioequivalent" in results
        assert "not_bioequivalent" in results
        assert "pending" in results

    @pytest.mark.anyio
    async def test_pk_parameter_names_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pk-parameters")
        data = resp.json()
        names = {item["parameter_name"] for item in data["items"]}
        assert "AUC_0_t" in names
        assert "AUC_0_inf" in names
        assert "Cmax" in names
        assert "Tmax" in names
        assert "t_half" in names
        assert "CL_F" in names

    @pytest.mark.anyio
    async def test_comparison_results_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/formulation-comparisons")
        data = resp.json()
        results = {item["result"] for item in data["items"]}
        assert "bioequivalent" in results
        assert "not_bioequivalent" in results
        assert "pending" in results
        assert "inconclusive" in results
