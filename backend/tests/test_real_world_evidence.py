"""Tests for Real-World Evidence (RWE) Integration & Analysis.

Covers:
- Seed data verification (data sources, studies, outcomes, comparative, health economics, submissions)
- Data source CRUD (create, read, update, delete, list, filter by type)
- Study lifecycle (initiate, update status, complete, list, filter by trial/status/design)
- Outcome recording (create, read, update, delete, list, filter by study/type/grade)
- Comparative effectiveness analyses (create, read, update, delete, list, filter)
- Health economic analyses (create, read, update, delete, list, filter)
- Submission package lifecycle (prepare, update, delete, list, filter by study/authority/status)
- RWE metrics computation
- Error handling (404s, 400s, invalid operations)
- Edge cases (empty filters, boundary conditions)
- Service singleton pattern
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.real_world_evidence import router as rwe_router
from app.schemas.real_world_evidence import (
    AnalysisStatus,
    DataSourceType,
    EvidenceGrade,
    OutcomeType,
    StudyDesign,
)
from app.services.real_world_evidence_service import (
    RWEService,
    get_rwe_service,
    reset_real_world_evidence_service,
)

# Build a lightweight test app that includes only the RWE router
_test_app = FastAPI()
_test_app.include_router(rwe_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/real-world-evidence"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_real_world_evidence_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> RWEService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=_test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_data_source_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "name": "Test Data Source",
        "data_source_type": "ehr",
        "description": "A test EHR data source",
        "patient_count": 50000,
        "date_range_start": (now - timedelta(days=365)).isoformat(),
        "date_range_end": now.isoformat(),
        "geographic_coverage": ["United States"],
        "data_elements": ["diagnoses", "procedures"],
        "refresh_frequency": "monthly",
        "data_lag_days": 30,
        "quality_score": 85.0,
        "vendor": "Test Vendor",
        "contract_id": "TEST-001",
    }
    defaults.update(overrides)
    return defaults


def _make_study_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "study_name": "Test RWE Study",
        "study_design": "retrospective_cohort",
        "indication": "Test indication",
        "comparator": "Standard of care",
        "primary_endpoint": "Overall survival",
        "secondary_endpoints": ["PFS", "QoL"],
        "target_population": "Adults aged 18+",
        "sample_size": 5000,
        "lead_analyst": "Dr. Test Analyst",
        "protocol_document": "PROT-TEST-001",
    }
    defaults.update(overrides)
    return defaults


def _make_outcome_create(**overrides) -> dict:
    defaults = {
        "study_id": "RWE-STUDY-001",
        "outcome_type": "effectiveness",
        "outcome_name": "Test Outcome",
        "measurement_method": "Standard assessment",
        "timepoint": "12 months",
        "result_value": 75.5,
        "confidence_interval_lower": 70.0,
        "confidence_interval_upper": 81.0,
        "p_value": 0.001,
        "clinical_significance": "Clinically meaningful improvement",
        "evidence_grade": "moderate",
        "population_size": 1000,
    }
    defaults.update(overrides)
    return defaults


def _make_comparative_create(**overrides) -> dict:
    defaults = {
        "study_id": "RWE-STUDY-001",
        "treatment_arm": "Drug A",
        "comparator_arm": "Drug B",
        "endpoint": "Primary endpoint",
        "hazard_ratio": 0.75,
        "odds_ratio": None,
        "relative_risk": None,
        "absolute_risk_reduction": 0.12,
        "nnt": 9,
        "nnh": None,
        "favors": "Drug A",
        "statistical_method": "Cox proportional hazards",
    }
    defaults.update(overrides)
    return defaults


def _make_health_econ_create(**overrides) -> dict:
    defaults = {
        "study_id": "RWE-STUDY-001",
        "analysis_type": "CUA",
        "perspective": "US payer",
        "time_horizon": "lifetime",
        "discount_rate": 0.03,
        "cost_per_qaly": 45000.0,
        "incremental_cost": 15000.0,
        "incremental_effectiveness": 0.33,
        "icer": 45454.55,
        "willingness_to_pay_threshold": 100000.0,
        "cost_effective": True,
        "sensitivity_analysis_results": {"base_case": 45454.55},
    }
    defaults.update(overrides)
    return defaults


def _make_submission_create(**overrides) -> dict:
    defaults = {
        "study_id": "RWE-STUDY-001",
        "regulatory_authority": "FDA",
        "package_type": "supplemental NDA",
        "data_sources_included": ["DS-001"],
        "methodology_summary": "Retrospective cohort study using claims data",
        "key_findings": ["Treatment X superior to comparator"],
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_data_sources_count(self, svc: RWEService):
        sources = svc.list_data_sources()
        assert len(sources) == 4

    def test_seed_data_source_types(self, svc: RWEService):
        sources = svc.list_data_sources()
        types = {ds.data_source_type for ds in sources}
        assert DataSourceType.CLAIMS in types
        assert DataSourceType.EHR in types
        assert DataSourceType.REGISTRY in types

    def test_seed_studies_count(self, svc: RWEService):
        studies = svc.list_studies()
        assert len(studies) == 4

    def test_seed_study_designs(self, svc: RWEService):
        studies = svc.list_studies()
        designs = {s.study_design for s in studies}
        assert StudyDesign.RETROSPECTIVE_COHORT in designs
        assert StudyDesign.PROSPECTIVE_COHORT in designs

    def test_seed_study_statuses(self, svc: RWEService):
        studies = svc.list_studies()
        statuses = {s.status for s in studies}
        assert AnalysisStatus.PUBLISHED in statuses
        assert AnalysisStatus.ANALYSIS in statuses
        assert AnalysisStatus.PEER_REVIEW in statuses
        assert AnalysisStatus.DATA_COLLECTION in statuses

    def test_seed_outcomes_count(self, svc: RWEService):
        outcomes = svc.list_outcomes()
        assert len(outcomes) == 8

    def test_seed_outcome_types(self, svc: RWEService):
        outcomes = svc.list_outcomes()
        types = {o.outcome_type for o in outcomes}
        assert OutcomeType.EFFECTIVENESS in types
        assert OutcomeType.SAFETY in types
        assert OutcomeType.PATIENT_REPORTED in types
        assert OutcomeType.ECONOMIC in types

    def test_seed_comparative_count(self, svc: RWEService):
        analyses = svc.list_comparative_analyses()
        assert len(analyses) == 4

    def test_seed_health_economics_count(self, svc: RWEService):
        analyses = svc.list_health_economics()
        assert len(analyses) == 3

    def test_seed_submissions_count(self, svc: RWEService):
        subs = svc.list_submission_packages()
        assert len(subs) == 3

    def test_seed_data_source_quality_scores_valid(self, svc: RWEService):
        sources = svc.list_data_sources()
        for ds in sources:
            assert 0.0 <= ds.quality_score <= 100.0

    def test_seed_study_linked_to_trial(self, svc: RWEService):
        study = svc.get_study("RWE-STUDY-001")
        assert study is not None
        assert study.trial_id == EYLEA_TRIAL


# =====================================================================
# DATA SOURCE CRUD
# =====================================================================


class TestDataSourceCrud:
    """Test data source create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_data_sources(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        assert len(data["items"]) == 4

    @pytest.mark.anyio
    async def test_list_data_sources_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources", params={"data_source_type": "claims"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["data_source_type"] == "claims"

    @pytest.mark.anyio
    async def test_get_data_source(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources/DS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DS-001"
        assert data["name"] == "Optum Clinformatics Extended DOD"

    @pytest.mark.anyio
    async def test_get_data_source_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources/DS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_data_source(self, client: AsyncClient):
        payload = _make_data_source_create()
        resp = await client.post(f"{API_PREFIX}/data-sources", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Data Source"
        assert data["data_source_type"] == "ehr"
        assert data["id"].startswith("DS-")

    @pytest.mark.anyio
    async def test_update_data_source(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/data-sources/DS-001",
            json={"name": "Updated Optum", "quality_score": 92.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Optum"
        assert data["quality_score"] == 92.0

    @pytest.mark.anyio
    async def test_update_data_source_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/data-sources/DS-NONEXISTENT",
            json={"name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_data_source(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/data-sources/DS-004")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/data-sources/DS-004")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_data_source_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/data-sources/DS-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# STUDY LIFECYCLE
# =====================================================================


class TestStudyLifecycle:
    """Test study CRUD and lifecycle operations."""

    @pytest.mark.anyio
    async def test_list_studies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4

    @pytest.mark.anyio
    async def test_list_studies_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_studies_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"status": "published"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "published"

    @pytest.mark.anyio
    async def test_list_studies_filter_design(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"study_design": "retrospective_cohort"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["study_design"] == "retrospective_cohort"

    @pytest.mark.anyio
    async def test_get_study(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/RWE-STUDY-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RWE-STUDY-001"
        assert "nAMD" in data["study_name"]

    @pytest.mark.anyio
    async def test_get_study_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/RWE-STUDY-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_initiate_study(self, client: AsyncClient):
        payload = _make_study_create()
        resp = await client.post(f"{API_PREFIX}/studies", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["study_name"] == "Test RWE Study"
        assert data["status"] == "planned"
        assert data["id"].startswith("RWE-STUDY-")

    @pytest.mark.anyio
    async def test_initiate_study_sets_start_date(self, client: AsyncClient):
        payload = _make_study_create()
        resp = await client.post(f"{API_PREFIX}/studies", json=payload)
        data = resp.json()
        assert data["start_date"] is not None

    @pytest.mark.anyio
    async def test_update_study_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/studies/RWE-STUDY-004",
            json={"status": "analysis"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "analysis"

    @pytest.mark.anyio
    async def test_update_study_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/studies/RWE-STUDY-NONEXISTENT",
            json={"status": "analysis"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_study(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/studies/RWE-STUDY-004")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/studies/RWE-STUDY-004")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_study_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/studies/RWE-STUDY-NONEXISTENT")
        assert resp.status_code == 404

    def test_study_lifecycle_planned_to_published(self, svc: RWEService):
        """Test full study lifecycle through status transitions."""
        from app.schemas.real_world_evidence import RWEStudyCreate, RWEStudyUpdate

        study = svc.initiate_study(RWEStudyCreate(
            trial_id=EYLEA_TRIAL,
            study_name="Lifecycle Test Study",
            study_design=StudyDesign.PROSPECTIVE_COHORT,
            indication="Test",
            comparator="Placebo",
            primary_endpoint="OS",
            target_population="Adults",
            sample_size=1000,
            lead_analyst="Dr. Test",
        ))
        assert study.status == AnalysisStatus.PLANNED

        updated = svc.update_study(study.id, RWEStudyUpdate(status=AnalysisStatus.DATA_COLLECTION))
        assert updated is not None
        assert updated.status == AnalysisStatus.DATA_COLLECTION

        updated = svc.update_study(study.id, RWEStudyUpdate(status=AnalysisStatus.ANALYSIS))
        assert updated is not None
        assert updated.status == AnalysisStatus.ANALYSIS

        updated = svc.update_study(study.id, RWEStudyUpdate(status=AnalysisStatus.PEER_REVIEW))
        assert updated is not None
        assert updated.status == AnalysisStatus.PEER_REVIEW

        updated = svc.update_study(study.id, RWEStudyUpdate(status=AnalysisStatus.PUBLISHED))
        assert updated is not None
        assert updated.status == AnalysisStatus.PUBLISHED

        updated = svc.update_study(study.id, RWEStudyUpdate(status=AnalysisStatus.SUBMITTED_TO_FDA))
        assert updated is not None
        assert updated.status == AnalysisStatus.SUBMITTED_TO_FDA


# =====================================================================
# OUTCOME RECORDING
# =====================================================================


class TestOutcomeRecording:
    """Test outcome recording and management."""

    @pytest.mark.anyio
    async def test_list_outcomes(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/outcomes")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8

    @pytest.mark.anyio
    async def test_list_outcomes_filter_study(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/outcomes", params={"study_id": "RWE-STUDY-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["study_id"] == "RWE-STUDY-001"

    @pytest.mark.anyio
    async def test_list_outcomes_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/outcomes", params={"outcome_type": "effectiveness"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["outcome_type"] == "effectiveness"

    @pytest.mark.anyio
    async def test_list_outcomes_filter_grade(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/outcomes", params={"evidence_grade": "high"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["evidence_grade"] == "high"

    @pytest.mark.anyio
    async def test_get_outcome(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/outcomes/OUT-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "OUT-001"
        assert data["outcome_type"] == "effectiveness"

    @pytest.mark.anyio
    async def test_get_outcome_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/outcomes/OUT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_record_outcome(self, client: AsyncClient):
        payload = _make_outcome_create()
        resp = await client.post(f"{API_PREFIX}/outcomes", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["outcome_name"] == "Test Outcome"
        assert data["id"].startswith("OUT-")

    @pytest.mark.anyio
    async def test_record_outcome_invalid_study(self, client: AsyncClient):
        payload = _make_outcome_create(study_id="RWE-STUDY-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/outcomes", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_outcome(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/outcomes/OUT-001",
            json={"result_value": 9.5, "evidence_grade": "high"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["result_value"] == 9.5
        assert data["evidence_grade"] == "high"

    @pytest.mark.anyio
    async def test_update_outcome_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/outcomes/OUT-NONEXISTENT",
            json={"result_value": 10.0},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_outcome(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/outcomes/OUT-008")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/outcomes/OUT-008")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_outcome_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/outcomes/OUT-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# COMPARATIVE EFFECTIVENESS
# =====================================================================


class TestComparativeEffectiveness:
    """Test comparative effectiveness analysis operations."""

    @pytest.mark.anyio
    async def test_list_comparative(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comparative")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4

    @pytest.mark.anyio
    async def test_list_comparative_filter_study(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comparative", params={"study_id": "RWE-STUDY-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["study_id"] == "RWE-STUDY-001"

    @pytest.mark.anyio
    async def test_get_comparative(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comparative/CE-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CE-001"
        assert data["favors"] == "Aflibercept (EYLEA)"

    @pytest.mark.anyio
    async def test_get_comparative_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comparative/CE-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_run_comparative_analysis(self, client: AsyncClient):
        payload = _make_comparative_create()
        resp = await client.post(f"{API_PREFIX}/comparative", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["treatment_arm"] == "Drug A"
        assert data["id"].startswith("CE-")

    @pytest.mark.anyio
    async def test_run_comparative_invalid_study(self, client: AsyncClient):
        payload = _make_comparative_create(study_id="RWE-STUDY-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/comparative", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_comparative(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/comparative/CE-001",
            json={"hazard_ratio": 0.65, "favors": "EYLEA (updated)"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["hazard_ratio"] == 0.65
        assert data["favors"] == "EYLEA (updated)"

    @pytest.mark.anyio
    async def test_update_comparative_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/comparative/CE-NONEXISTENT",
            json={"favors": "Drug A"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_comparative(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/comparative/CE-004")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/comparative/CE-004")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_comparative_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/comparative/CE-NONEXISTENT")
        assert resp.status_code == 404

    def test_comparative_with_nnt_and_nnh(self, svc: RWEService):
        """CE-004 has both NNT and NNH."""
        ce = svc.get_comparative_analysis("CE-004")
        assert ce is not None
        assert ce.nnt == 5
        assert ce.nnh == 8

    def test_comparative_favors_field(self, svc: RWEService):
        """All comparative analyses should have a favors field."""
        analyses = svc.list_comparative_analyses()
        for a in analyses:
            assert a.favors
            assert len(a.favors) > 0


# =====================================================================
# HEALTH ECONOMICS
# =====================================================================


class TestHealthEconomics:
    """Test health economic analysis operations."""

    @pytest.mark.anyio
    async def test_list_health_economics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/health-economics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_health_economics_filter_study(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/health-economics", params={"study_id": "RWE-STUDY-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["study_id"] == "RWE-STUDY-001"

    @pytest.mark.anyio
    async def test_get_health_economic(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/health-economics/HE-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "HE-001"
        assert data["analysis_type"] == "CUA"
        assert data["cost_effective"] is True

    @pytest.mark.anyio
    async def test_get_health_economic_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/health-economics/HE-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_calculate_health_economics(self, client: AsyncClient):
        payload = _make_health_econ_create()
        resp = await client.post(f"{API_PREFIX}/health-economics", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["analysis_type"] == "CUA"
        assert data["cost_effective"] is True
        assert data["id"].startswith("HE-")

    @pytest.mark.anyio
    async def test_calculate_health_economics_invalid_study(self, client: AsyncClient):
        payload = _make_health_econ_create(study_id="RWE-STUDY-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/health-economics", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_health_economic(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/health-economics/HE-001",
            json={"cost_per_qaly": 42000.0, "cost_effective": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["cost_per_qaly"] == 42000.0

    @pytest.mark.anyio
    async def test_update_health_economic_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/health-economics/HE-NONEXISTENT",
            json={"cost_per_qaly": 50000.0},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_health_economic(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/health-economics/HE-003")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/health-economics/HE-003")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_health_economic_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/health-economics/HE-NONEXISTENT")
        assert resp.status_code == 404

    def test_sensitivity_analysis_results(self, svc: RWEService):
        """HE-001 should have sensitivity analysis results."""
        he = svc.get_health_economic("HE-001")
        assert he is not None
        assert len(he.sensitivity_analysis_results) > 0
        assert "discount_rate_0%" in he.sensitivity_analysis_results

    def test_all_seeded_cost_effective(self, svc: RWEService):
        """All 3 seeded analyses should be cost-effective."""
        analyses = svc.list_health_economics()
        for a in analyses:
            assert a.cost_effective is True

    def test_icer_values_present(self, svc: RWEService):
        """All seeded analyses should have ICER values."""
        analyses = svc.list_health_economics()
        for a in analyses:
            assert a.icer is not None
            assert a.icer > 0


# =====================================================================
# SUBMISSION PACKAGES
# =====================================================================


class TestSubmissionPackages:
    """Test RWE submission package operations."""

    @pytest.mark.anyio
    async def test_list_submissions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_submissions_filter_study(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions", params={"study_id": "RWE-STUDY-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["study_id"] == "RWE-STUDY-001"

    @pytest.mark.anyio
    async def test_list_submissions_filter_authority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions", params={"regulatory_authority": "FDA"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["regulatory_authority"] == "FDA"

    @pytest.mark.anyio
    async def test_list_submissions_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions", params={"status": "submitted_to_fda"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "submitted_to_fda"

    @pytest.mark.anyio
    async def test_get_submission(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions/SUB-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SUB-001"
        assert data["regulatory_authority"] == "FDA"

    @pytest.mark.anyio
    async def test_get_submission_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions/SUB-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_prepare_submission_package(self, client: AsyncClient):
        payload = _make_submission_create()
        resp = await client.post(f"{API_PREFIX}/submissions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["regulatory_authority"] == "FDA"
        assert data["status"] == "planned"
        assert data["id"].startswith("SUB-")
        assert data["submission_date"] is None

    @pytest.mark.anyio
    async def test_prepare_submission_invalid_study(self, client: AsyncClient):
        payload = _make_submission_create(study_id="RWE-STUDY-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/submissions", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_submission(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/submissions/SUB-002",
            json={
                "submission_date": now.isoformat(),
                "status": "submitted_to_fda",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "submitted_to_fda"
        assert data["submission_date"] is not None

    @pytest.mark.anyio
    async def test_update_submission_reviewer_feedback(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/submissions/SUB-001",
            json={"reviewer_feedback": "Request additional subgroup analyses"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["reviewer_feedback"] == "Request additional subgroup analyses"

    @pytest.mark.anyio
    async def test_update_submission_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/submissions/SUB-NONEXISTENT",
            json={"status": "published"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_submission(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/submissions/SUB-003")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/submissions/SUB-003")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_submission_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/submissions/SUB-NONEXISTENT")
        assert resp.status_code == 404

    def test_submission_has_key_findings(self, svc: RWEService):
        """SUB-001 should have key findings populated."""
        sub = svc.get_submission_package("SUB-001")
        assert sub is not None
        assert len(sub.key_findings) >= 3

    def test_submission_has_data_sources(self, svc: RWEService):
        """SUB-001 should list data sources included."""
        sub = svc.get_submission_package("SUB-001")
        assert sub is not None
        assert "DS-001" in sub.data_sources_included


# =====================================================================
# METRICS
# =====================================================================


class TestRWEMetrics:
    """Test RWE metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_data_sources"] == 4
        assert data["total_studies"] == 4
        assert data["total_outcomes"] == 8
        assert data["total_comparative_analyses"] == 4
        assert data["total_health_economic_analyses"] == 3
        assert data["total_submission_packages"] == 3

    def test_metrics_total_patients(self, svc: RWEService):
        metrics = svc.get_metrics()
        assert metrics.total_patients_across_sources > 0
        # Sum of all data source patient counts
        total = sum(ds.patient_count for ds in svc.list_data_sources())
        assert metrics.total_patients_across_sources == total

    def test_metrics_average_quality(self, svc: RWEService):
        metrics = svc.get_metrics()
        assert metrics.average_data_quality_score > 0
        sources = svc.list_data_sources()
        expected_avg = round(sum(ds.quality_score for ds in sources) / len(sources), 1)
        assert metrics.average_data_quality_score == expected_avg

    def test_metrics_studies_by_status(self, svc: RWEService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.studies_by_status.values())
        assert total_by_status == metrics.total_studies

    def test_metrics_studies_by_design(self, svc: RWEService):
        metrics = svc.get_metrics()
        total_by_design = sum(metrics.studies_by_design.values())
        assert total_by_design == metrics.total_studies

    def test_metrics_outcomes_by_type(self, svc: RWEService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.outcomes_by_type.values())
        assert total_by_type == metrics.total_outcomes

    def test_metrics_cost_effective_count(self, svc: RWEService):
        metrics = svc.get_metrics()
        assert metrics.cost_effective_treatments == 3

    def test_metrics_submissions_by_authority(self, svc: RWEService):
        metrics = svc.get_metrics()
        total_by_auth = sum(metrics.submissions_by_authority.values())
        assert total_by_auth == metrics.total_submission_packages

    def test_metrics_average_evidence_grade(self, svc: RWEService):
        metrics = svc.get_metrics()
        assert metrics.average_evidence_grade == "moderate"


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_rwe_service()
        svc2 = get_rwe_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_rwe_service()
        svc2 = reset_real_world_evidence_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_rwe_service()
        svc.delete_data_source("DS-001")
        assert svc.get_data_source("DS-001") is None
        svc2 = reset_real_world_evidence_service()
        assert svc2.get_data_source("DS-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_data_sources_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_studies_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_outcomes_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/outcomes")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_comparative_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/comparative")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_health_economics_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/health-economics")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_submissions_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/submissions")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_data_source_all_fields(self, client: AsyncClient):
        payload = _make_data_source_create(
            name="Full DS",
            data_source_type="wearable",
            geographic_coverage=["US", "EU"],
            data_elements=["heart_rate", "activity", "sleep"],
        )
        resp = await client.post(f"{API_PREFIX}/data-sources", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["data_source_type"] == "wearable"
        assert len(data["geographic_coverage"]) == 2

    @pytest.mark.anyio
    async def test_create_study_with_all_designs(self, client: AsyncClient):
        """Test creating studies with different designs."""
        for design in ["retrospective_cohort", "prospective_cohort", "case_control", "cross_sectional", "pragmatic_trial"]:
            payload = _make_study_create(
                study_name=f"Test {design} Study",
                study_design=design,
            )
            resp = await client.post(f"{API_PREFIX}/studies", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["study_design"] == design

    @pytest.mark.anyio
    async def test_outcome_with_all_types(self, client: AsyncClient):
        """Test recording outcomes of all types."""
        for outcome_type in ["effectiveness", "safety", "patient_reported", "economic", "composite"]:
            payload = _make_outcome_create(
                outcome_name=f"Test {outcome_type} outcome",
                outcome_type=outcome_type,
            )
            resp = await client.post(f"{API_PREFIX}/outcomes", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["outcome_type"] == outcome_type

    @pytest.mark.anyio
    async def test_outcome_with_all_grades(self, client: AsyncClient):
        """Test recording outcomes with all evidence grades."""
        for grade in ["high", "moderate", "low", "very_low", "insufficient"]:
            payload = _make_outcome_create(
                outcome_name=f"Test {grade} grade outcome",
                evidence_grade=grade,
            )
            resp = await client.post(f"{API_PREFIX}/outcomes", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["evidence_grade"] == grade

    @pytest.mark.anyio
    async def test_submission_for_ema(self, client: AsyncClient):
        payload = _make_submission_create(regulatory_authority="EMA")
        resp = await client.post(f"{API_PREFIX}/submissions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["regulatory_authority"] == "EMA"

    @pytest.mark.anyio
    async def test_submission_for_pmda(self, client: AsyncClient):
        payload = _make_submission_create(regulatory_authority="PMDA")
        resp = await client.post(f"{API_PREFIX}/submissions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["regulatory_authority"] == "PMDA"

    def test_data_source_patient_count_positive(self, svc: RWEService):
        """All data sources should have positive patient counts."""
        for ds in svc.list_data_sources():
            assert ds.patient_count > 0

    def test_study_sample_sizes_positive(self, svc: RWEService):
        """All studies should have positive sample sizes."""
        for study in svc.list_studies():
            assert study.sample_size > 0

    def test_outcome_confidence_intervals_valid(self, svc: RWEService):
        """CI lower should be less than CI upper for all outcomes."""
        for outcome in svc.list_outcomes():
            assert outcome.confidence_interval_lower <= outcome.confidence_interval_upper

    def test_outcome_p_values_valid(self, svc: RWEService):
        """P-values should be between 0 and 1."""
        for outcome in svc.list_outcomes():
            if outcome.p_value is not None:
                assert 0.0 <= outcome.p_value <= 1.0

    def test_health_econ_discount_rates_valid(self, svc: RWEService):
        """Discount rates should be between 0 and 1."""
        for he in svc.list_health_economics():
            assert 0.0 <= he.discount_rate <= 1.0


# =====================================================================
# DATA SOURCE TYPE ENUMERATION
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used in the system."""

    @pytest.mark.anyio
    async def test_data_source_types_in_sources(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/data-sources")
        data = resp.json()
        types = {item["data_source_type"] for item in data["items"]}
        assert "claims" in types
        assert "ehr" in types
        assert "registry" in types

    @pytest.mark.anyio
    async def test_study_statuses_in_studies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "published" in statuses
        assert "analysis" in statuses
        assert "peer_review" in statuses
        assert "data_collection" in statuses

    @pytest.mark.anyio
    async def test_outcome_types_in_outcomes(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/outcomes")
        data = resp.json()
        types = {item["outcome_type"] for item in data["items"]}
        assert "effectiveness" in types
        assert "safety" in types
        assert "patient_reported" in types
        assert "economic" in types

    @pytest.mark.anyio
    async def test_evidence_grades_in_outcomes(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/outcomes")
        data = resp.json()
        grades = {item["evidence_grade"] for item in data["items"]}
        assert "moderate" in grades
        assert "high" in grades
        assert "low" in grades


# =====================================================================
# CROSS-ENTITY RELATIONSHIPS
# =====================================================================


class TestCrossEntityRelationships:
    """Test relationships between RWE entities."""

    def test_outcomes_linked_to_studies(self, svc: RWEService):
        """All outcomes should reference existing studies."""
        study_ids = {s.id for s in svc.list_studies()}
        for outcome in svc.list_outcomes():
            assert outcome.study_id in study_ids

    def test_comparative_linked_to_studies(self, svc: RWEService):
        """All comparative analyses should reference existing studies."""
        study_ids = {s.id for s in svc.list_studies()}
        for ce in svc.list_comparative_analyses():
            assert ce.study_id in study_ids

    def test_health_econ_linked_to_studies(self, svc: RWEService):
        """All health econ analyses should reference existing studies."""
        study_ids = {s.id for s in svc.list_studies()}
        for he in svc.list_health_economics():
            assert he.study_id in study_ids

    def test_submissions_linked_to_studies(self, svc: RWEService):
        """All submissions should reference existing studies."""
        study_ids = {s.id for s in svc.list_studies()}
        for sub in svc.list_submission_packages():
            assert sub.study_id in study_ids

    def test_submission_data_sources_exist(self, svc: RWEService):
        """Submission data sources should reference existing data sources."""
        ds_ids = {ds.id for ds in svc.list_data_sources()}
        for sub in svc.list_submission_packages():
            for ds_id in sub.data_sources_included:
                assert ds_id in ds_ids

    def test_studies_linked_to_trials(self, svc: RWEService):
        """All studies should reference known trial IDs."""
        known_trials = {EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL}
        for study in svc.list_studies():
            assert study.trial_id in known_trials

    @pytest.mark.anyio
    async def test_outcomes_for_study_001(self, client: AsyncClient):
        """RWE-STUDY-001 should have 3 outcomes."""
        resp = await client.get(f"{API_PREFIX}/outcomes", params={"study_id": "RWE-STUDY-001"})
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_comparative_for_study_001(self, client: AsyncClient):
        """RWE-STUDY-001 should have 2 comparative analyses."""
        resp = await client.get(f"{API_PREFIX}/comparative", params={"study_id": "RWE-STUDY-001"})
        data = resp.json()
        assert data["total"] == 2

    @pytest.mark.anyio
    async def test_health_econ_for_study_001(self, client: AsyncClient):
        """RWE-STUDY-001 should have 1 health economic analysis."""
        resp = await client.get(f"{API_PREFIX}/health-economics", params={"study_id": "RWE-STUDY-001"})
        data = resp.json()
        assert data["total"] == 1

    @pytest.mark.anyio
    async def test_submissions_for_study_001(self, client: AsyncClient):
        """RWE-STUDY-001 should have 2 submission packages."""
        resp = await client.get(f"{API_PREFIX}/submissions", params={"study_id": "RWE-STUDY-001"})
        data = resp.json()
        assert data["total"] == 2


# =====================================================================
# STUDY DETAILS VERIFICATION
# =====================================================================


class TestStudyDetails:
    """Test detailed study content and structure."""

    @pytest.mark.anyio
    async def test_study_has_secondary_endpoints(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/RWE-STUDY-001")
        data = resp.json()
        assert len(data["secondary_endpoints"]) >= 2

    @pytest.mark.anyio
    async def test_published_study_has_completion_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/RWE-STUDY-001")
        data = resp.json()
        assert data["status"] == "published"
        assert data["completion_date"] is not None

    @pytest.mark.anyio
    async def test_in_progress_study_no_completion_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/RWE-STUDY-004")
        data = resp.json()
        assert data["status"] == "data_collection"
        assert data["completion_date"] is None

    def test_study_has_lead_analyst(self, svc: RWEService):
        for study in svc.list_studies():
            assert study.lead_analyst
            assert len(study.lead_analyst) > 0

    def test_study_has_indication(self, svc: RWEService):
        for study in svc.list_studies():
            assert study.indication
            assert len(study.indication) > 0

    def test_study_has_comparator(self, svc: RWEService):
        for study in svc.list_studies():
            assert study.comparator
            assert len(study.comparator) > 0

    @pytest.mark.anyio
    async def test_studies_sorted_by_start_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        data = resp.json()
        dates = [item["start_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)


# =====================================================================
# MULTIPLE SUBMISSIONS AND AGGREGATION
# =====================================================================


class TestMultipleSubmissions:
    """Test multiple submissions and aggregation behavior."""

    @pytest.mark.anyio
    async def test_multiple_submissions_for_same_study(self, client: AsyncClient):
        """Create multiple submissions for the same study."""
        for authority in ["FDA", "EMA", "PMDA"]:
            payload = _make_submission_create(regulatory_authority=authority)
            resp = await client.post(f"{API_PREFIX}/submissions", json=payload)
            assert resp.status_code == 201

        # Verify all created
        resp = await client.get(f"{API_PREFIX}/submissions", params={"study_id": "RWE-STUDY-001"})
        data = resp.json()
        # 2 seeded + 3 new
        assert data["total"] >= 5

    @pytest.mark.anyio
    async def test_metrics_update_after_new_study(self, client: AsyncClient):
        """Metrics should reflect newly created studies."""
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        initial_studies = resp1.json()["total_studies"]

        payload = _make_study_create(study_name="New Metrics Test Study")
        await client.post(f"{API_PREFIX}/studies", json=payload)

        resp2 = await client.get(f"{API_PREFIX}/metrics")
        assert resp2.json()["total_studies"] == initial_studies + 1

    @pytest.mark.anyio
    async def test_metrics_update_after_new_outcome(self, client: AsyncClient):
        """Metrics should reflect newly recorded outcomes."""
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        initial_outcomes = resp1.json()["total_outcomes"]

        payload = _make_outcome_create(outcome_name="New Metrics Outcome")
        await client.post(f"{API_PREFIX}/outcomes", json=payload)

        resp2 = await client.get(f"{API_PREFIX}/metrics")
        assert resp2.json()["total_outcomes"] == initial_outcomes + 1

    @pytest.mark.anyio
    async def test_metrics_update_after_deletion(self, client: AsyncClient):
        """Metrics should reflect deleted entities."""
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        initial_ds = resp1.json()["total_data_sources"]

        await client.delete(f"{API_PREFIX}/data-sources/DS-001")

        resp2 = await client.get(f"{API_PREFIX}/metrics")
        assert resp2.json()["total_data_sources"] == initial_ds - 1
