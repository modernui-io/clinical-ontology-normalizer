"""Tests for Clinical Pharmacokinetics (CLIN-PK).

Covers:
- Seed data verification (PK studies, concentration data, compartmental models,
  drug interactions, exposure-response)
- PK study CRUD (create, read, update, delete, list, filter by trial/type/status)
- Concentration data CRUD (create, read, update, delete, list, filter by trial/study/subject)
- Compartmental model CRUD (create, read, update, delete, list, filter by trial/study/model_type)
- Drug interaction CRUD (create, read, update, delete, list, filter by trial/type/severity)
- Exposure-response CRUD (create, read, update, delete, list, filter by trial/study/significant)
- Metrics computation
- Error handling (404s for missing entities)
- Singleton pattern behavior
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.clinical_pharmacokinetics import (
    InteractionSeverity,
    InteractionType,
    ModelType,
    PKStudyStatus,
    PKStudyType,
)
from app.services.clinical_pharmacokinetics_service import (
    ClinicalPharmacokineticsService,
    get_clinical_pharmacokinetics_service,
    reset_clinical_pharmacokinetics_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/clinical-pharmacokinetics"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_clinical_pharmacokinetics_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ClinicalPharmacokineticsService:
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


def _make_pk_study_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "study_name": "Test PK Study",
        "study_type": "single_dose",
        "drug_name": "Test Drug",
        "dose": "100 mg",
        "principal_investigator": "Dr. Test Investigator",
        "subjects_planned": 20,
    }
    defaults.update(overrides)
    return defaults


def _make_concentration_data_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "study_id": "PKS-001",
        "subject_id": "SUBJ-TEST",
        "timepoint_hours": 2.0,
        "nominal_time_hours": 2.0,
        "analyzed_by": "Lab Tech Test",
        "concentration": 25.5,
        "unit": "ng/mL",
    }
    defaults.update(overrides)
    return defaults


def _make_compartmental_model_create(**overrides) -> dict:
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "study_id": "PKS-005",
        "model_name": "Test Compartmental Model",
        "model_type": "one_compartment",
        "modeler": "Dr. Test Modeler",
        "software": "NONMEM",
    }
    defaults.update(overrides)
    return defaults


def _make_drug_interaction_create(**overrides) -> dict:
    defaults = {
        "trial_id": LIBTAYO_TRIAL,
        "perpetrator_drug": "Drug A",
        "victim_drug": "Drug B",
        "interaction_type": "inhibitor",
        "assessed_by": "Dr. Test Assessor",
        "severity": "no_interaction",
    }
    defaults.update(overrides)
    return defaults


def _make_exposure_response_create(**overrides) -> dict:
    defaults = {
        "trial_id": DUPIXENT_TRIAL,
        "analysis_name": "Test E-R Analysis",
        "exposure_metric": "AUCss",
        "response_endpoint": "Primary Efficacy",
        "analyzed_by": "Dr. Test Analyst",
        "subjects_analyzed": 100,
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_pk_studies_count(self, svc: ClinicalPharmacokineticsService):
        studies = svc.list_pk_studies()
        assert len(studies) == 12

    def test_seed_concentration_data_count(self, svc: ClinicalPharmacokineticsService):
        records = svc.list_concentration_data()
        assert len(records) == 12

    def test_seed_compartmental_models_count(self, svc: ClinicalPharmacokineticsService):
        models = svc.list_compartmental_models()
        assert len(models) == 12

    def test_seed_drug_interactions_count(self, svc: ClinicalPharmacokineticsService):
        interactions = svc.list_drug_interactions()
        assert len(interactions) == 12

    def test_seed_exposure_responses_count(self, svc: ClinicalPharmacokineticsService):
        er = svc.list_exposure_responses()
        assert len(er) == 12

    def test_seed_studies_cover_all_trials(self, svc: ClinicalPharmacokineticsService):
        studies = svc.list_pk_studies()
        trial_ids = {s.trial_id for s in studies}
        assert EYLEA_TRIAL in trial_ids
        assert DUPIXENT_TRIAL in trial_ids
        assert LIBTAYO_TRIAL in trial_ids

    def test_seed_studies_have_multiple_types(self, svc: ClinicalPharmacokineticsService):
        studies = svc.list_pk_studies()
        types = {s.study_type for s in studies}
        assert len(types) >= 4

    def test_seed_studies_have_multiple_statuses(self, svc: ClinicalPharmacokineticsService):
        studies = svc.list_pk_studies()
        statuses = {s.status for s in studies}
        assert PKStudyStatus.COMPLETED in statuses
        assert PKStudyStatus.PLANNED in statuses

    def test_seed_models_have_multiple_types(self, svc: ClinicalPharmacokineticsService):
        models = svc.list_compartmental_models()
        types = {m.model_type for m in models}
        assert len(types) >= 4

    def test_seed_interactions_have_multiple_severities(self, svc: ClinicalPharmacokineticsService):
        interactions = svc.list_drug_interactions()
        severities = {di.severity for di in interactions}
        assert InteractionSeverity.NO_INTERACTION in severities
        assert InteractionSeverity.SEVERE in severities
        assert InteractionSeverity.CONTRAINDICATED in severities

    def test_seed_concentration_has_below_lloq(self, svc: ClinicalPharmacokineticsService):
        records = svc.list_concentration_data()
        below_lloq = [r for r in records if r.below_lloq]
        assert len(below_lloq) >= 1

    def test_seed_models_have_qualified(self, svc: ClinicalPharmacokineticsService):
        models = svc.list_compartmental_models()
        qualified = [m for m in models if m.model_qualified]
        not_qualified = [m for m in models if not m.model_qualified]
        assert len(qualified) >= 1
        assert len(not_qualified) >= 1

    def test_seed_interactions_have_dose_adjustments(self, svc: ClinicalPharmacokineticsService):
        interactions = svc.list_drug_interactions()
        dose_adj = [di for di in interactions if di.dose_adjustment_needed]
        assert len(dose_adj) >= 1

    def test_seed_er_have_significant_relationships(self, svc: ClinicalPharmacokineticsService):
        er = svc.list_exposure_responses()
        sig = [e for e in er if e.significant_relationship]
        not_sig = [e for e in er if not e.significant_relationship]
        assert len(sig) >= 1
        assert len(not_sig) >= 1


# =====================================================================
# PK STUDY CRUD
# =====================================================================


class TestPKStudyCrud:
    """Test PK study CRUD operations."""

    @pytest.mark.anyio
    async def test_list_pk_studies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pk-studies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_pk_studies_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/pk-studies", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_pk_studies_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/pk-studies", params={"study_type": "single_dose"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["study_type"] == "single_dose"

    @pytest.mark.anyio
    async def test_list_pk_studies_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/pk-studies", params={"status": "completed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_pk_study(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pk-studies/PKS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PKS-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["study_type"] == "single_dose"

    @pytest.mark.anyio
    async def test_get_pk_study_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pk-studies/PKS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_pk_study(self, client: AsyncClient):
        payload = _make_pk_study_create()
        resp = await client.post(f"{API_PREFIX}/pk-studies", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["study_type"] == "single_dose"
        assert data["status"] == "planned"
        assert data["id"].startswith("PKS-")

    @pytest.mark.anyio
    async def test_update_pk_study(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/pk-studies/PKS-012",
            json={"status": "sample_collection", "subjects_enrolled": 10, "notes": "Enrollment started"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "sample_collection"
        assert data["subjects_enrolled"] == 10
        assert data["notes"] == "Enrollment started"

    @pytest.mark.anyio
    async def test_update_pk_study_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/pk-studies/PKS-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_pk_study(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/pk-studies/PKS-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/pk-studies/PKS-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_pk_study_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/pk-studies/PKS-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# CONCENTRATION DATA CRUD
# =====================================================================


class TestConcentrationDataCrud:
    """Test concentration data CRUD operations."""

    @pytest.mark.anyio
    async def test_list_concentration_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/concentration-data")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_concentration_data_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/concentration-data", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_concentration_data_filter_study(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/concentration-data", params={"study_id": "PKS-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["study_id"] == "PKS-001"

    @pytest.mark.anyio
    async def test_list_concentration_data_filter_subject(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/concentration-data", params={"subject_id": "SUBJ-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["subject_id"] == "SUBJ-001"

    @pytest.mark.anyio
    async def test_get_concentration_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/concentration-data/CD-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CD-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["timepoint_hours"] == 0.0

    @pytest.mark.anyio
    async def test_get_concentration_data_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/concentration-data/CD-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_concentration_data(self, client: AsyncClient):
        payload = _make_concentration_data_create()
        resp = await client.post(f"{API_PREFIX}/concentration-data", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["study_id"] == "PKS-001"
        assert data["concentration"] == 25.5
        assert data["id"].startswith("CD-")

    @pytest.mark.anyio
    async def test_update_concentration_data(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/concentration-data/CD-004",
            json={"below_lloq": True, "flag": "BLQ-confirmed", "notes": "Confirmed below LLOQ"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["below_lloq"] is True
        assert data["flag"] == "BLQ-confirmed"
        assert data["notes"] == "Confirmed below LLOQ"

    @pytest.mark.anyio
    async def test_update_concentration_data_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/concentration-data/CD-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_concentration_data(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/concentration-data/CD-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/concentration-data/CD-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_concentration_data_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/concentration-data/CD-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# COMPARTMENTAL MODEL CRUD
# =====================================================================


class TestCompartmentalModelCrud:
    """Test compartmental model CRUD operations."""

    @pytest.mark.anyio
    async def test_list_compartmental_models(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compartmental-models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_compartmental_models_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compartmental-models", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_compartmental_models_filter_study(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compartmental-models", params={"study_id": "PKS-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["study_id"] == "PKS-001"

    @pytest.mark.anyio
    async def test_list_compartmental_models_filter_model_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/compartmental-models", params={"model_type": "noncompartmental"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["model_type"] == "noncompartmental"

    @pytest.mark.anyio
    async def test_get_compartmental_model(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compartmental-models/CM-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CM-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["model_type"] == "one_compartment"

    @pytest.mark.anyio
    async def test_get_compartmental_model_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compartmental-models/CM-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_compartmental_model(self, client: AsyncClient):
        payload = _make_compartmental_model_create()
        resp = await client.post(f"{API_PREFIX}/compartmental-models", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["model_type"] == "one_compartment"
        assert data["model_qualified"] is False
        assert data["id"].startswith("CM-")

    @pytest.mark.anyio
    async def test_update_compartmental_model(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/compartmental-models/CM-004",
            json={
                "model_qualified": True,
                "reviewer": "Dr. External Reviewer",
                "notes": "Externally qualified",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["model_qualified"] is True
        assert data["reviewer"] == "Dr. External Reviewer"
        assert data["notes"] == "Externally qualified"

    @pytest.mark.anyio
    async def test_update_compartmental_model_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/compartmental-models/CM-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_compartmental_model(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/compartmental-models/CM-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/compartmental-models/CM-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_compartmental_model_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/compartmental-models/CM-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# DRUG INTERACTION CRUD
# =====================================================================


class TestDrugInteractionCrud:
    """Test drug interaction CRUD operations."""

    @pytest.mark.anyio
    async def test_list_drug_interactions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-interactions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_drug_interactions_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/drug-interactions", params={"trial_id": DUPIXENT_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL

    @pytest.mark.anyio
    async def test_list_drug_interactions_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/drug-interactions", params={"interaction_type": "inhibitor"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["interaction_type"] == "inhibitor"

    @pytest.mark.anyio
    async def test_list_drug_interactions_filter_severity(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/drug-interactions", params={"severity": "contraindicated"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["severity"] == "contraindicated"

    @pytest.mark.anyio
    async def test_get_drug_interaction(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-interactions/DI-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DI-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["severity"] == "no_interaction"

    @pytest.mark.anyio
    async def test_get_drug_interaction_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-interactions/DI-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_drug_interaction(self, client: AsyncClient):
        payload = _make_drug_interaction_create()
        resp = await client.post(f"{API_PREFIX}/drug-interactions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["interaction_type"] == "inhibitor"
        assert data["severity"] == "no_interaction"
        assert data["id"].startswith("DI-")

    @pytest.mark.anyio
    async def test_update_drug_interaction(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/drug-interactions/DI-003",
            json={
                "severity": "moderate",
                "dose_adjustment_needed": True,
                "recommended_adjustment": "Reduce methotrexate by 25%",
                "notes": "Updated based on Phase 3 data",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["severity"] == "moderate"
        assert data["dose_adjustment_needed"] is True
        assert data["recommended_adjustment"] == "Reduce methotrexate by 25%"

    @pytest.mark.anyio
    async def test_update_drug_interaction_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/drug-interactions/DI-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_drug_interaction(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/drug-interactions/DI-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/drug-interactions/DI-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_drug_interaction_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/drug-interactions/DI-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# EXPOSURE-RESPONSE CRUD
# =====================================================================


class TestExposureResponseCrud:
    """Test exposure-response CRUD operations."""

    @pytest.mark.anyio
    async def test_list_exposure_responses(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/exposure-responses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_exposure_responses_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/exposure-responses", params={"trial_id": LIBTAYO_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL

    @pytest.mark.anyio
    async def test_list_exposure_responses_filter_study(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/exposure-responses", params={"study_id": "PKS-008"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["study_id"] == "PKS-008"

    @pytest.mark.anyio
    async def test_list_exposure_responses_significant_only(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/exposure-responses", params={"significant_only": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["significant_relationship"] is True

    @pytest.mark.anyio
    async def test_get_exposure_response(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/exposure-responses/ER-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ER-001"
        assert data["trial_id"] == EYLEA_TRIAL
        assert data["significant_relationship"] is True

    @pytest.mark.anyio
    async def test_get_exposure_response_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/exposure-responses/ER-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_exposure_response(self, client: AsyncClient):
        payload = _make_exposure_response_create()
        resp = await client.post(f"{API_PREFIX}/exposure-responses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == DUPIXENT_TRIAL
        assert data["significant_relationship"] is False
        assert data["id"].startswith("ER-")

    @pytest.mark.anyio
    async def test_update_exposure_response(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/exposure-responses/ER-003",
            json={
                "significant_relationship": True,
                "r_squared": 0.25,
                "dose_recommendation": "Updated recommendation",
                "notes": "Reanalysis with larger dataset",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["significant_relationship"] is True
        assert data["r_squared"] == 0.25
        assert data["notes"] == "Reanalysis with larger dataset"

    @pytest.mark.anyio
    async def test_update_exposure_response_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/exposure-responses/ER-NONEXISTENT",
            json={"notes": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_exposure_response(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/exposure-responses/ER-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/exposure-responses/ER-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_exposure_response_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/exposure-responses/ER-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# METRICS
# =====================================================================


class TestClinicalPharmacokineticsMetrics:
    """Test clinical pharmacokinetics metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_pk_studies"] == 12
        assert data["total_concentration_records"] == 12
        assert data["total_models"] == 12
        assert data["total_interactions"] == 12
        assert data["total_exposure_response"] == 12

    @pytest.mark.anyio
    async def test_metrics_studies_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_type = data["studies_by_type"]
        total = sum(by_type.values())
        assert total == data["total_pk_studies"]

    @pytest.mark.anyio
    async def test_metrics_studies_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["studies_by_status"]
        total = sum(by_status.values())
        assert total == data["total_pk_studies"]

    @pytest.mark.anyio
    async def test_metrics_models_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_type = data["models_by_type"]
        total = sum(by_type.values())
        assert total == data["total_models"]

    @pytest.mark.anyio
    async def test_metrics_qualified_models(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["qualified_models"] > 0
        assert data["qualified_models"] <= data["total_models"]

    @pytest.mark.anyio
    async def test_metrics_interactions_by_severity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_severity = data["interactions_by_severity"]
        total = sum(by_severity.values())
        assert total == data["total_interactions"]

    @pytest.mark.anyio
    async def test_metrics_dose_adjustments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["dose_adjustments_needed"] > 0
        assert data["dose_adjustments_needed"] <= data["total_interactions"]

    @pytest.mark.anyio
    async def test_metrics_significant_relationships(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["significant_relationships"] > 0
        assert data["significant_relationships"] <= data["total_exposure_response"]

    @pytest.mark.anyio
    async def test_metrics_below_lloq_pct(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["below_lloq_pct"] >= 0.0
        assert data["below_lloq_pct"] <= 100.0

    def test_metrics_below_lloq_pct_value(self, svc: ClinicalPharmacokineticsService):
        metrics = svc.get_metrics()
        # 1 out of 12 is below LLOQ = 8.3%
        assert metrics.below_lloq_pct == 8.3


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_clinical_pharmacokinetics_service()
        svc2 = get_clinical_pharmacokinetics_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_clinical_pharmacokinetics_service()
        svc2 = reset_clinical_pharmacokinetics_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_clinical_pharmacokinetics_service()
        # Delete a study
        svc.delete_pk_study("PKS-001")
        assert svc.get_pk_study("PKS-001") is None
        # Reset should bring it back
        svc2 = reset_clinical_pharmacokinetics_service()
        assert svc2.get_pk_study("PKS-001") is not None


# =====================================================================
# FILTERING AND EDGE CASES
# =====================================================================


class TestFilteringAndEdgeCases:
    """Test filtering combinations and edge cases."""

    @pytest.mark.anyio
    async def test_list_studies_empty_filter(self, client: AsyncClient):
        """Filter by a trial that has no studies."""
        resp = await client.get(
            f"{API_PREFIX}/pk-studies",
            params={"trial_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.anyio
    async def test_list_interactions_empty_filter(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/drug-interactions",
            params={"severity": "moderate", "trial_id": EYLEA_TRIAL},
        )
        assert resp.status_code == 200
        data = resp.json()
        # EYLEA doesn't have moderate severity interactions
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_concentration_filter_multiple(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/concentration-data",
            params={"trial_id": EYLEA_TRIAL, "study_id": "PKS-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL
            assert item["study_id"] == "PKS-001"

    @pytest.mark.anyio
    async def test_create_study_then_retrieve(self, client: AsyncClient):
        """Create a study and verify it shows in the list."""
        payload = _make_pk_study_create()
        resp = await client.post(f"{API_PREFIX}/pk-studies", json=payload)
        assert resp.status_code == 201
        created_id = resp.json()["id"]

        resp2 = await client.get(f"{API_PREFIX}/pk-studies/{created_id}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == created_id

    @pytest.mark.anyio
    async def test_create_study_then_update_status(self, client: AsyncClient):
        """Create a study, then update its status through lifecycle."""
        payload = _make_pk_study_create()
        resp = await client.post(f"{API_PREFIX}/pk-studies", json=payload)
        assert resp.status_code == 201
        study_id = resp.json()["id"]
        assert resp.json()["status"] == "planned"

        # Update to sample_collection
        resp2 = await client.put(
            f"{API_PREFIX}/pk-studies/{study_id}",
            json={"status": "sample_collection"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "sample_collection"

        # Update to bioanalysis
        resp3 = await client.put(
            f"{API_PREFIX}/pk-studies/{study_id}",
            json={"status": "bioanalysis", "bioanalytical_method": "LC-MS/MS"},
        )
        assert resp3.status_code == 200
        assert resp3.json()["status"] == "bioanalysis"
        assert resp3.json()["bioanalytical_method"] == "LC-MS/MS"

    @pytest.mark.anyio
    async def test_create_and_delete_concentration(self, client: AsyncClient):
        """Create a concentration record and then delete it."""
        payload = _make_concentration_data_create()
        resp = await client.post(f"{API_PREFIX}/concentration-data", json=payload)
        assert resp.status_code == 201
        cd_id = resp.json()["id"]

        resp2 = await client.delete(f"{API_PREFIX}/concentration-data/{cd_id}")
        assert resp2.status_code == 204

        resp3 = await client.get(f"{API_PREFIX}/concentration-data/{cd_id}")
        assert resp3.status_code == 404

    @pytest.mark.anyio
    async def test_create_model_with_study_id(self, client: AsyncClient):
        """Create a compartmental model linked to a study."""
        payload = _make_compartmental_model_create(study_id="PKS-009")
        resp = await client.post(f"{API_PREFIX}/compartmental-models", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["study_id"] == "PKS-009"

    @pytest.mark.anyio
    async def test_create_interaction_with_study_id(self, client: AsyncClient):
        """Create a drug interaction linked to a study."""
        payload = _make_drug_interaction_create(study_id="PKS-011")
        resp = await client.post(f"{API_PREFIX}/drug-interactions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["study_id"] == "PKS-011"

    @pytest.mark.anyio
    async def test_create_er_with_study_id(self, client: AsyncClient):
        """Create an exposure-response linked to a study."""
        payload = _make_exposure_response_create(study_id="PKS-010")
        resp = await client.post(f"{API_PREFIX}/exposure-responses", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["study_id"] == "PKS-010"

    @pytest.mark.anyio
    async def test_metrics_after_create_and_delete(self, client: AsyncClient):
        """Metrics should reflect dynamic changes."""
        # Get baseline metrics
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        baseline = resp1.json()

        # Create a new study
        payload = _make_pk_study_create()
        await client.post(f"{API_PREFIX}/pk-studies", json=payload)

        resp2 = await client.get(f"{API_PREFIX}/metrics")
        after_create = resp2.json()
        assert after_create["total_pk_studies"] == baseline["total_pk_studies"] + 1

        # Delete a study
        await client.delete(f"{API_PREFIX}/pk-studies/PKS-012")
        resp3 = await client.get(f"{API_PREFIX}/metrics")
        after_delete = resp3.json()
        assert after_delete["total_pk_studies"] == baseline["total_pk_studies"]

    @pytest.mark.anyio
    async def test_exposure_responses_not_significant_exist(self, client: AsyncClient):
        """Verify non-significant E-R analyses exist in seed data."""
        resp = await client.get(f"{API_PREFIX}/exposure-responses")
        data = resp.json()
        not_sig = [item for item in data["items"] if not item["significant_relationship"]]
        assert len(not_sig) >= 1

    @pytest.mark.anyio
    async def test_models_filter_by_qualified(self, client: AsyncClient):
        """Ensure both qualified and not-qualified models exist."""
        resp = await client.get(f"{API_PREFIX}/compartmental-models")
        data = resp.json()
        qualified = [m for m in data["items"] if m["model_qualified"]]
        not_qualified = [m for m in data["items"] if not m["model_qualified"]]
        assert len(qualified) >= 1
        assert len(not_qualified) >= 1


# =====================================================================
# ENUM COVERAGE
# =====================================================================


class TestEnumCoverage:
    """Verify enum values are represented in seed data."""

    @pytest.mark.anyio
    async def test_study_types_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pk-studies")
        data = resp.json()
        types = {item["study_type"] for item in data["items"]}
        assert "single_dose" in types
        assert "multiple_dose" in types
        assert "food_effect" in types
        assert "drug_interaction" in types
        assert "special_population" in types
        assert "population_pk" in types

    @pytest.mark.anyio
    async def test_study_statuses_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pk-studies")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "planned" in statuses
        assert "sample_collection" in statuses
        assert "bioanalysis" in statuses
        assert "data_analysis" in statuses
        assert "report_writing" in statuses
        assert "completed" in statuses

    @pytest.mark.anyio
    async def test_model_types_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compartmental-models")
        data = resp.json()
        types = {item["model_type"] for item in data["items"]}
        assert "one_compartment" in types
        assert "two_compartment" in types
        assert "three_compartment" in types
        assert "noncompartmental" in types
        assert "population_mixed_effects" in types
        assert "pbpk" in types

    @pytest.mark.anyio
    async def test_interaction_types_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-interactions")
        data = resp.json()
        types = {item["interaction_type"] for item in data["items"]}
        assert "inhibitor" in types
        assert "inducer" in types
        assert "substrate" in types
        assert "combined" in types
        assert "transporter" in types

    @pytest.mark.anyio
    async def test_interaction_severities_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-interactions")
        data = resp.json()
        severities = {item["severity"] for item in data["items"]}
        assert "no_interaction" in severities
        assert "mild" in severities
        assert "moderate" in severities
        assert "severe" in severities
        assert "contraindicated" in severities


# =====================================================================
# ADDITIONAL CRUD EDGE CASES
# =====================================================================


class TestAdditionalEdgeCases:
    """Additional edge case tests for robustness."""

    @pytest.mark.anyio
    async def test_create_pk_study_different_trial(self, client: AsyncClient):
        payload = _make_pk_study_create(trial_id=LIBTAYO_TRIAL, study_type="population_pk")
        resp = await client.post(f"{API_PREFIX}/pk-studies", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert data["study_type"] == "population_pk"

    @pytest.mark.anyio
    async def test_create_concentration_with_null_concentration(self, client: AsyncClient):
        payload = _make_concentration_data_create(concentration=None)
        resp = await client.post(f"{API_PREFIX}/concentration-data", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["concentration"] is None

    @pytest.mark.anyio
    async def test_update_concentration_sample_quality(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/concentration-data/CD-008",
            json={"sample_quality": "reanalyzed_acceptable"},
        )
        assert resp.status_code == 200
        assert resp.json()["sample_quality"] == "reanalyzed_acceptable"

    @pytest.mark.anyio
    async def test_update_model_goodness_of_fit(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/compartmental-models/CM-011",
            json={"goodness_of_fit_adequate": True, "vpc_adequate": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["goodness_of_fit_adequate"] is True
        assert data["vpc_adequate"] is True

    @pytest.mark.anyio
    async def test_update_drug_interaction_auc_ratio(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/drug-interactions/DI-003",
            json={"auc_ratio": 0.82},
        )
        assert resp.status_code == 200
        assert resp.json()["auc_ratio"] == 0.82

    @pytest.mark.anyio
    async def test_update_exposure_response_ec50(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/exposure-responses/ER-005",
            json={"ec50": 28.0, "notes": "Updated EC50 from reanalysis"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ec50"] == 28.0
        assert data["notes"] == "Updated EC50 from reanalysis"

    @pytest.mark.anyio
    async def test_list_all_entities_returns_items_and_total(self, client: AsyncClient):
        """Ensure all list endpoints return items and total."""
        endpoints = [
            "pk-studies",
            "concentration-data",
            "compartmental-models",
            "drug-interactions",
            "exposure-responses",
        ]
        for endpoint in endpoints:
            resp = await client.get(f"{API_PREFIX}/{endpoint}")
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data
            assert "total" in data
            assert data["total"] == len(data["items"])

    @pytest.mark.anyio
    async def test_get_nonexistent_for_all_entities(self, client: AsyncClient):
        """Verify 404 for all entity types with nonexistent IDs."""
        endpoints = [
            "pk-studies/NONEXISTENT",
            "concentration-data/NONEXISTENT",
            "compartmental-models/NONEXISTENT",
            "drug-interactions/NONEXISTENT",
            "exposure-responses/NONEXISTENT",
        ]
        for endpoint in endpoints:
            resp = await client.get(f"{API_PREFIX}/{endpoint}")
            assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_nonexistent_for_all_entities(self, client: AsyncClient):
        """Verify 404 for delete on all entity types with nonexistent IDs."""
        endpoints = [
            "pk-studies/NONEXISTENT",
            "concentration-data/NONEXISTENT",
            "compartmental-models/NONEXISTENT",
            "drug-interactions/NONEXISTENT",
            "exposure-responses/NONEXISTENT",
        ]
        for endpoint in endpoints:
            resp = await client.delete(f"{API_PREFIX}/{endpoint}")
            assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_multiple_then_list(self, client: AsyncClient):
        """Create multiple studies and verify count increases."""
        resp0 = await client.get(f"{API_PREFIX}/pk-studies")
        initial_count = resp0.json()["total"]

        for i in range(3):
            payload = _make_pk_study_create(study_name=f"Batch Study {i}")
            await client.post(f"{API_PREFIX}/pk-studies", json=payload)

        resp1 = await client.get(f"{API_PREFIX}/pk-studies")
        assert resp1.json()["total"] == initial_count + 3

    @pytest.mark.anyio
    async def test_pk_study_has_correct_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/pk-studies/PKS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert "drug_name" in data
        assert "dose" in data
        assert "route" in data
        assert "subjects_planned" in data
        assert "subjects_enrolled" in data
        assert "sampling_timepoints" in data
        assert "bioanalytical_method" in data
        assert "lloq" in data
        assert "uloq" in data
        assert "principal_investigator" in data

    @pytest.mark.anyio
    async def test_concentration_data_has_correct_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/concentration-data/CD-001")
        assert resp.status_code == 200
        data = resp.json()
        assert "subject_id" in data
        assert "period" in data
        assert "timepoint_hours" in data
        assert "concentration" in data
        assert "unit" in data
        assert "below_lloq" in data
        assert "sample_quality" in data
        assert "matrix" in data
        assert "analyzed_by" in data

    @pytest.mark.anyio
    async def test_compartmental_model_has_correct_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/compartmental-models/CM-001")
        assert resp.status_code == 200
        data = resp.json()
        assert "model_name" in data
        assert "model_type" in data
        assert "software" in data
        assert "parameters" in data
        assert "covariates_tested" in data
        assert "significant_covariates" in data
        assert "goodness_of_fit_adequate" in data
        assert "vpc_adequate" in data
        assert "bootstrap_runs" in data
        assert "model_qualified" in data
        assert "modeler" in data

    @pytest.mark.anyio
    async def test_drug_interaction_has_correct_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/drug-interactions/DI-001")
        assert resp.status_code == 200
        data = resp.json()
        assert "perpetrator_drug" in data
        assert "victim_drug" in data
        assert "interaction_type" in data
        assert "severity" in data
        assert "auc_ratio" in data
        assert "cmax_ratio" in data
        assert "dose_adjustment_needed" in data
        assert "in_vitro_data" in data
        assert "in_vivo_data" in data
        assert "assessed_by" in data

    @pytest.mark.anyio
    async def test_exposure_response_has_correct_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/exposure-responses/ER-001")
        assert resp.status_code == 200
        data = resp.json()
        assert "analysis_name" in data
        assert "exposure_metric" in data
        assert "response_endpoint" in data
        assert "relationship_type" in data
        assert "model_type" in data
        assert "subjects_analyzed" in data
        assert "significant_relationship" in data
        assert "p_value" in data
        assert "r_squared" in data
        assert "ec50" in data
        assert "emax" in data
        assert "analyzed_by" in data
