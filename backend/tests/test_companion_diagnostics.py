"""Tests for Companion Diagnostics (CDx) Management (CDx-MGMT).

Covers:
- Seed data verification (CDx records, validation studies)
- CDx CRUD (create, read, update, delete, list with filters)
- Validation study CRUD (create, read, update, delete, list with filters)
- Metrics computation (portfolio-wide and per-trial)
- Error handling (404s, validation errors)
- Edge cases (empty filters, boundary conditions, cascading deletes)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.companion_diagnostics import (
    BiomarkerType,
    CdxCreate,
    CdxStatus,
    CdxType,
    CdxUpdate,
    CdxValidationStudyCreate,
    CdxValidationStudyUpdate,
    RegulatoryPathway,
    ValidationStudyStatus,
    ValidationStudyType,
)
from app.services.companion_diagnostics_service import (
    CompanionDiagnosticsService,
    get_companion_diagnostics_service,
    reset_companion_diagnostics_service,
)


# ---------------------------------------------------------------------------
# Force asyncio backend only (trio causes event-loop conflicts with SQLAlchemy)
# ---------------------------------------------------------------------------

@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/companion-diagnostics"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_companion_diagnostics_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> CompanionDiagnosticsService:
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


def _make_cdx_create(**overrides) -> dict:
    defaults = {
        "cdx_name": "Test CDx Assay",
        "cdx_type": "ihc",
        "biomarker_name": "Test Biomarker",
        "biomarker_type": "proteomic",
        "assay_manufacturer": "Test Manufacturer",
        "assay_platform": "Test Platform",
        "drug_name": "Test Drug",
        "therapeutic_area": "Oncology",
    }
    defaults.update(overrides)
    return defaults


def _make_study_create(**overrides) -> dict:
    defaults = {
        "study_type": "analytical_validation",
        "study_name": "Test Validation Study",
        "sample_size": 100,
    }
    defaults.update(overrides)
    return defaults


# ===========================================================================
# SECTION 1: Seed Data Verification
# ===========================================================================


class TestSeedDataCdx:
    """Verify seeded CDx records."""

    @pytest.mark.anyio
    async def test_seed_cdx_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_seed_cdx_001_exists(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx/CDX-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cdx_name"] == "VEGF-A Ocular Level Assay"
        assert data["cdx_type"] == "ivd"
        assert data["status"] == "approved"
        assert data["biomarker_name"] == "VEGF-A"
        assert data["drug_name"] == "Eylea (aflibercept)"

    @pytest.mark.anyio
    async def test_seed_cdx_008_pdl1(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx/CDX-008")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cdx_name"] == "PD-L1 IHC 22C3 pharmDx"
        assert data["therapeutic_area"] == "Oncology"
        assert data["sensitivity"] == 96.5
        assert data["specificity"] == 93.2

    @pytest.mark.anyio
    async def test_seed_cdx_012_withdrawn(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx/CDX-012")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "withdrawn"
        assert data["gene_target"] == "KRAS"
        assert data["variant"] == "G12C"

    @pytest.mark.anyio
    async def test_seed_cdx_004_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx/CDX-004")
        assert resp.status_code == 200
        data = resp.json()
        assert data["drug_name"] == "Dupixent (dupilumab)"
        assert data["biomarker_name"] == "Total IgE"
        assert data["status"] == "approved"

    @pytest.mark.anyio
    async def test_seed_cdx_007_in_development(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx/CDX-007")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_development"
        assert data["sensitivity"] is None

    @pytest.mark.anyio
    async def test_seed_cdx_all_have_required_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx")
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["id"] is not None
            assert item["cdx_name"] is not None
            assert item["drug_name"] is not None
            assert item["created_at"] is not None
            assert item["updated_at"] is not None

    @pytest.mark.anyio
    async def test_seed_cdx_010_regulatory_submission(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx/CDX-010")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "regulatory_submission"
        assert data["submission_date"] is not None
        assert data["approval_date"] is None

    @pytest.mark.anyio
    async def test_seed_cdx_003_analytical_validation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx/CDX-003")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "analytical_validation"
        assert data["concordance_rate"] is None

    @pytest.mark.anyio
    async def test_seed_cdx_002_clinical_validation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx/CDX-002")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "clinical_validation"
        assert data["variant"] == "Y402H"


class TestSeedDataStudies:
    """Verify seeded validation studies."""

    @pytest.mark.anyio
    async def test_seed_studies_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_seed_study_001(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/VS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cdx_id"] == "CDX-001"
        assert data["study_type"] == "analytical_validation"
        assert data["sample_size"] == 240
        assert data["status"] == "completed"

    @pytest.mark.anyio
    async def test_seed_study_007_in_progress(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/VS-007")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["completion_date"] is None

    @pytest.mark.anyio
    async def test_seed_study_015_planned(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/VS-015")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "planned"
        assert data["findings"] is None

    @pytest.mark.anyio
    async def test_seed_study_010_concordance_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/VS-010")
        assert resp.status_code == 200
        data = resp.json()
        assert data["study_type"] == "concordance"
        assert data["concordance_rate"] == 82.5

    @pytest.mark.anyio
    async def test_seed_study_014_proficiency(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/VS-014")
        assert resp.status_code == 200
        data = resp.json()
        assert data["study_type"] == "proficiency_testing"

    @pytest.mark.anyio
    async def test_seed_study_all_have_required_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["id"] is not None
            assert item["cdx_id"] is not None
            assert item["study_name"] is not None
            assert item["sample_size"] >= 1


# ===========================================================================
# SECTION 2: CDx CRUD
# ===========================================================================


class TestCdxCreate:
    """Test CDx creation."""

    @pytest.mark.anyio
    async def test_create_cdx_minimal(self, client: AsyncClient):
        payload = _make_cdx_create()
        resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["cdx_name"] == "Test CDx Assay"
        assert data["status"] == "in_development"
        assert data["id"].startswith("CDX-")

    @pytest.mark.anyio
    async def test_create_cdx_full(self, client: AsyncClient):
        payload = _make_cdx_create(
            gene_target="BRAF",
            variant="V600E",
            sensitivity=95.0,
            specificity=92.0,
            ppv=88.0,
            npv=96.0,
            concordance_rate=93.0,
            trial_ids=[LIBTAYO_TRIAL],
            regulatory_pathway="pma",
            labeling_text="For BRAF V600E testing",
            cutoff_value=1.0,
            cutoff_unit="%",
            sample_type="FFPE tissue",
            turnaround_days=7,
        )
        resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["gene_target"] == "BRAF"
        assert data["variant"] == "V600E"
        assert data["sensitivity"] == 95.0
        assert data["trial_ids"] == [LIBTAYO_TRIAL]
        assert data["regulatory_pathway"] == "pma"

    @pytest.mark.anyio
    async def test_create_cdx_default_status(self, client: AsyncClient):
        payload = _make_cdx_create()
        resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        assert resp.status_code == 201
        assert resp.json()["status"] == "in_development"

    @pytest.mark.anyio
    async def test_create_cdx_has_timestamps(self, client: AsyncClient):
        payload = _make_cdx_create()
        resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["created_at"] is not None
        assert data["updated_at"] is not None

    @pytest.mark.anyio
    async def test_create_cdx_empty_trial_ids(self, client: AsyncClient):
        payload = _make_cdx_create(trial_ids=[])
        resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        assert resp.status_code == 201
        assert resp.json()["trial_ids"] == []

    @pytest.mark.anyio
    async def test_create_cdx_multiple_trial_ids(self, client: AsyncClient):
        payload = _make_cdx_create(trial_ids=[EYLEA_TRIAL, DUPIXENT_TRIAL])
        resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        assert resp.status_code == 201
        assert len(resp.json()["trial_ids"]) == 2

    @pytest.mark.anyio
    async def test_create_cdx_missing_required_field(self, client: AsyncClient):
        payload = {"cdx_name": "Incomplete"}
        resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_cdx_invalid_cdx_type(self, client: AsyncClient):
        payload = _make_cdx_create(cdx_type="invalid")
        resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_cdx_invalid_biomarker_type(self, client: AsyncClient):
        payload = _make_cdx_create(biomarker_type="invalid")
        resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_cdx_sensitivity_out_of_range(self, client: AsyncClient):
        payload = _make_cdx_create(sensitivity=150.0)
        resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_cdx_negative_sensitivity(self, client: AsyncClient):
        payload = _make_cdx_create(sensitivity=-5.0)
        resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_cdx_specificity_boundary_100(self, client: AsyncClient):
        payload = _make_cdx_create(specificity=100.0)
        resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        assert resp.status_code == 201
        assert resp.json()["specificity"] == 100.0

    @pytest.mark.anyio
    async def test_create_cdx_specificity_boundary_0(self, client: AsyncClient):
        payload = _make_cdx_create(specificity=0.0)
        resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        assert resp.status_code == 201
        assert resp.json()["specificity"] == 0.0

    @pytest.mark.anyio
    async def test_create_cdx_negative_turnaround_days(self, client: AsyncClient):
        payload = _make_cdx_create(turnaround_days=-1)
        resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_cdx_all_types(self, client: AsyncClient):
        for ctype in CdxType:
            payload = _make_cdx_create(cdx_type=ctype.value)
            resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
            assert resp.status_code == 201
            assert resp.json()["cdx_type"] == ctype.value

    @pytest.mark.anyio
    async def test_create_cdx_all_biomarker_types(self, client: AsyncClient):
        for btype in BiomarkerType:
            payload = _make_cdx_create(biomarker_type=btype.value)
            resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
            assert resp.status_code == 201
            assert resp.json()["biomarker_type"] == btype.value


class TestCdxRead:
    """Test CDx retrieval."""

    @pytest.mark.anyio
    async def test_get_cdx_exists(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx/CDX-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "CDX-001"

    @pytest.mark.anyio
    async def test_get_cdx_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx/CDX-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_cdx_not_found_detail(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx/FAKE-ID")
        assert resp.status_code == 404
        body = resp.json()
        detail_text = body.get("detail", body.get("message", ""))
        assert "FAKE-ID" in detail_text


class TestCdxUpdate:
    """Test CDx updates."""

    @pytest.mark.anyio
    async def test_update_cdx_name(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/cdx/CDX-001",
            json={"cdx_name": "Updated Assay Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["cdx_name"] == "Updated Assay Name"

    @pytest.mark.anyio
    async def test_update_cdx_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/cdx/CDX-003",
            json={"status": "clinical_validation"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "clinical_validation"

    @pytest.mark.anyio
    async def test_update_cdx_performance_metrics(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/cdx/CDX-003",
            json={"sensitivity": 90.0, "specificity": 88.0, "ppv": 85.0, "npv": 92.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sensitivity"] == 90.0
        assert data["specificity"] == 88.0
        assert data["ppv"] == 85.0
        assert data["npv"] == 92.0

    @pytest.mark.anyio
    async def test_update_cdx_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/cdx/CDX-NONEXISTENT",
            json={"cdx_name": "Ghost"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_cdx_partial(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/cdx/CDX-001",
            json={"drug_name": "New Drug Name"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["drug_name"] == "New Drug Name"
        # Other fields unchanged
        assert data["cdx_name"] == "VEGF-A Ocular Level Assay"

    @pytest.mark.anyio
    async def test_update_cdx_updates_timestamp(self, client: AsyncClient):
        before = await client.get(f"{API_PREFIX}/cdx/CDX-001")
        old_updated = before.json()["updated_at"]
        resp = await client.put(
            f"{API_PREFIX}/cdx/CDX-001",
            json={"cdx_name": "Timestamp Test"},
        )
        assert resp.status_code == 200
        new_updated = resp.json()["updated_at"]
        assert new_updated >= old_updated

    @pytest.mark.anyio
    async def test_update_cdx_trial_ids(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/cdx/CDX-001",
            json={"trial_ids": [EYLEA_TRIAL, DUPIXENT_TRIAL]},
        )
        assert resp.status_code == 200
        assert len(resp.json()["trial_ids"]) == 2

    @pytest.mark.anyio
    async def test_update_cdx_regulatory_pathway(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/cdx/CDX-003",
            json={"regulatory_pathway": "ce_mark"},
        )
        assert resp.status_code == 200
        assert resp.json()["regulatory_pathway"] == "ce_mark"

    @pytest.mark.anyio
    async def test_update_cdx_invalid_sensitivity(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/cdx/CDX-001",
            json={"sensitivity": 200.0},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_cdx_approval_date(self, client: AsyncClient):
        now = datetime.now(timezone.utc).isoformat()
        resp = await client.put(
            f"{API_PREFIX}/cdx/CDX-010",
            json={"approval_date": now, "status": "approved"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
        assert resp.json()["approval_date"] is not None

    @pytest.mark.anyio
    async def test_update_cdx_labeling_text(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/cdx/CDX-003",
            json={"labeling_text": "New labeling text for ANGPT2 assay"},
        )
        assert resp.status_code == 200
        assert resp.json()["labeling_text"] == "New labeling text for ANGPT2 assay"

    @pytest.mark.anyio
    async def test_update_cdx_cutoff_values(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/cdx/CDX-001",
            json={"cutoff_value": 250.0, "cutoff_unit": "pg/mL"},
        )
        assert resp.status_code == 200
        assert resp.json()["cutoff_value"] == 250.0


class TestCdxDelete:
    """Test CDx deletion."""

    @pytest.mark.anyio
    async def test_delete_cdx(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/cdx/CDX-012")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_cdx_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/cdx/CDX-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_cdx_then_get_returns_404(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/cdx/CDX-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/cdx/CDX-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_cdx_reduces_count(self, client: AsyncClient):
        before = await client.get(f"{API_PREFIX}/cdx")
        before_count = before.json()["total"]
        await client.delete(f"{API_PREFIX}/cdx/CDX-012")
        after = await client.get(f"{API_PREFIX}/cdx")
        assert after.json()["total"] == before_count - 1

    @pytest.mark.anyio
    async def test_delete_cdx_cascades_to_studies(self, client: AsyncClient):
        """Deleting a CDx should also remove its validation studies."""
        # CDX-001 has studies VS-001, VS-002, VS-003
        before = await client.get(f"{API_PREFIX}/studies", params={"cdx_id": "CDX-001"})
        assert before.json()["total"] == 3

        await client.delete(f"{API_PREFIX}/cdx/CDX-001")

        after = await client.get(f"{API_PREFIX}/studies", params={"cdx_id": "CDX-001"})
        assert after.json()["total"] == 0

    @pytest.mark.anyio
    async def test_delete_cdx_double_delete(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/cdx/CDX-012")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/cdx/CDX-012")
        assert resp2.status_code == 404


class TestCdxListFilters:
    """Test CDx list with filters."""

    @pytest.mark.anyio
    async def test_list_cdx_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_list_cdx_filter_by_trial_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert EYLEA_TRIAL in item["trial_ids"]

    @pytest.mark.anyio
    async def test_list_cdx_filter_by_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        assert resp.json()["total"] == 4

    @pytest.mark.anyio
    async def test_list_cdx_filter_by_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        assert resp.json()["total"] == 5

    @pytest.mark.anyio
    async def test_list_cdx_filter_by_status_approved(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx", params={"status": "approved"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        for item in data["items"]:
            assert item["status"] == "approved"

    @pytest.mark.anyio
    async def test_list_cdx_filter_by_status_withdrawn(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx", params={"status": "withdrawn"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["id"] == "CDX-012"

    @pytest.mark.anyio
    async def test_list_cdx_filter_by_status_in_development(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx", params={"status": "in_development"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.anyio
    async def test_list_cdx_filter_by_type_ihc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx", params={"cdx_type": "ihc"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["cdx_type"] == "ihc"

    @pytest.mark.anyio
    async def test_list_cdx_filter_by_type_ngs_panel(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx", params={"cdx_type": "ngs_panel"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    @pytest.mark.anyio
    async def test_list_cdx_filter_by_type_liquid_biopsy(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx", params={"cdx_type": "liquid_biopsy"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    @pytest.mark.anyio
    async def test_list_cdx_filter_by_biomarker_type_genomic(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx", params={"biomarker_type": "genomic"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["biomarker_type"] == "genomic"

    @pytest.mark.anyio
    async def test_list_cdx_filter_by_biomarker_type_proteomic(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx", params={"biomarker_type": "proteomic"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["biomarker_type"] == "proteomic"

    @pytest.mark.anyio
    async def test_list_cdx_filter_by_therapeutic_area_oncology(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx", params={"therapeutic_area": "Oncology"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        for item in data["items"]:
            assert item["therapeutic_area"] == "Oncology"

    @pytest.mark.anyio
    async def test_list_cdx_filter_by_therapeutic_area_case_insensitive(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx", params={"therapeutic_area": "oncology"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 5

    @pytest.mark.anyio
    async def test_list_cdx_filter_by_therapeutic_area_immunology(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx", params={"therapeutic_area": "Immunology"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 4

    @pytest.mark.anyio
    async def test_list_cdx_filter_by_therapeutic_area_ophthalmology(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx", params={"therapeutic_area": "Ophthalmology"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 3

    @pytest.mark.anyio
    async def test_list_cdx_filter_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx", params={"trial_id": "nonexistent-trial"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_list_cdx_combined_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/cdx",
            params={"trial_id": LIBTAYO_TRIAL, "status": "approved"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == "CDX-008"

    @pytest.mark.anyio
    async def test_list_cdx_sorted_by_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx")
        assert resp.status_code == 200
        items = resp.json()["items"]
        ids = [i["id"] for i in items]
        assert ids == sorted(ids)

    @pytest.mark.anyio
    async def test_list_cdx_filter_by_type_pcr(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx", params={"cdx_type": "pcr"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    @pytest.mark.anyio
    async def test_list_cdx_filter_by_type_fish(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx", params={"cdx_type": "fish"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.anyio
    async def test_list_cdx_filter_by_type_ivd(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/cdx", params={"cdx_type": "ivd"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 3


# ===========================================================================
# SECTION 3: Validation Study CRUD
# ===========================================================================


class TestStudyCreate:
    """Test validation study creation."""

    @pytest.mark.anyio
    async def test_create_study_minimal(self, client: AsyncClient):
        payload = _make_study_create()
        resp = await client.post(f"{API_PREFIX}/cdx/CDX-001/studies", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["cdx_id"] == "CDX-001"
        assert data["study_name"] == "Test Validation Study"
        assert data["status"] == "planned"
        assert data["id"].startswith("VS-")

    @pytest.mark.anyio
    async def test_create_study_full(self, client: AsyncClient):
        now = datetime.now(timezone.utc).isoformat()
        payload = _make_study_create(
            concordance_rate=88.0,
            sensitivity=92.0,
            specificity=90.0,
            start_date=now,
            findings="Preliminary findings look promising.",
        )
        resp = await client.post(f"{API_PREFIX}/cdx/CDX-001/studies", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["concordance_rate"] == 88.0
        assert data["sensitivity"] == 92.0

    @pytest.mark.anyio
    async def test_create_study_cdx_not_found(self, client: AsyncClient):
        payload = _make_study_create()
        resp = await client.post(f"{API_PREFIX}/cdx/CDX-NONEXISTENT/studies", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_study_default_status_planned(self, client: AsyncClient):
        payload = _make_study_create()
        resp = await client.post(f"{API_PREFIX}/cdx/CDX-001/studies", json=payload)
        assert resp.status_code == 201
        assert resp.json()["status"] == "planned"

    @pytest.mark.anyio
    async def test_create_study_missing_required(self, client: AsyncClient):
        payload = {"study_name": "Incomplete"}
        resp = await client.post(f"{API_PREFIX}/cdx/CDX-001/studies", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_study_invalid_sample_size(self, client: AsyncClient):
        payload = _make_study_create(sample_size=0)
        resp = await client.post(f"{API_PREFIX}/cdx/CDX-001/studies", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_study_negative_sample_size(self, client: AsyncClient):
        payload = _make_study_create(sample_size=-10)
        resp = await client.post(f"{API_PREFIX}/cdx/CDX-001/studies", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_study_all_types(self, client: AsyncClient):
        for stype in ValidationStudyType:
            payload = _make_study_create(study_type=stype.value)
            resp = await client.post(f"{API_PREFIX}/cdx/CDX-001/studies", json=payload)
            assert resp.status_code == 201
            assert resp.json()["study_type"] == stype.value

    @pytest.mark.anyio
    async def test_create_study_invalid_study_type(self, client: AsyncClient):
        payload = _make_study_create(study_type="invalid")
        resp = await client.post(f"{API_PREFIX}/cdx/CDX-001/studies", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_study_concordance_out_of_range(self, client: AsyncClient):
        payload = _make_study_create(concordance_rate=110.0)
        resp = await client.post(f"{API_PREFIX}/cdx/CDX-001/studies", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_study_has_timestamp(self, client: AsyncClient):
        payload = _make_study_create()
        resp = await client.post(f"{API_PREFIX}/cdx/CDX-001/studies", json=payload)
        assert resp.status_code == 201
        assert resp.json()["created_at"] is not None


class TestStudyRead:
    """Test validation study retrieval."""

    @pytest.mark.anyio
    async def test_get_study_exists(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/VS-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "VS-001"

    @pytest.mark.anyio
    async def test_get_study_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/VS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_get_study_not_found_detail(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/FAKE-VS")
        assert resp.status_code == 404
        body = resp.json()
        detail_text = body.get("detail", body.get("message", ""))
        assert "FAKE-VS" in detail_text


class TestStudyUpdate:
    """Test validation study updates."""

    @pytest.mark.anyio
    async def test_update_study_name(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/studies/VS-001",
            json={"study_name": "Updated Study Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["study_name"] == "Updated Study Name"

    @pytest.mark.anyio
    async def test_update_study_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/studies/VS-015",
            json={"status": "in_progress"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

    @pytest.mark.anyio
    async def test_update_study_findings(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/studies/VS-007",
            json={"findings": "Interim results show 90% concordance."},
        )
        assert resp.status_code == 200
        assert "Interim results" in resp.json()["findings"]

    @pytest.mark.anyio
    async def test_update_study_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/studies/VS-NONEXISTENT",
            json={"study_name": "Ghost"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_study_sample_size(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/studies/VS-001",
            json={"sample_size": 500},
        )
        assert resp.status_code == 200
        assert resp.json()["sample_size"] == 500

    @pytest.mark.anyio
    async def test_update_study_concordance(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/studies/VS-012",
            json={"concordance_rate": 91.5},
        )
        assert resp.status_code == 200
        assert resp.json()["concordance_rate"] == 91.5

    @pytest.mark.anyio
    async def test_update_study_partial(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/studies/VS-001",
            json={"sensitivity": 96.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sensitivity"] == 96.0
        # Other fields unchanged
        assert data["study_name"] == "VEGF-A Analytical Sensitivity & Linearity Study"

    @pytest.mark.anyio
    async def test_update_study_completion_date(self, client: AsyncClient):
        now = datetime.now(timezone.utc).isoformat()
        resp = await client.put(
            f"{API_PREFIX}/studies/VS-007",
            json={"completion_date": now, "status": "completed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert resp.json()["completion_date"] is not None

    @pytest.mark.anyio
    async def test_update_study_invalid_sample_size(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/studies/VS-001",
            json={"sample_size": 0},
        )
        assert resp.status_code == 422


class TestStudyDelete:
    """Test validation study deletion."""

    @pytest.mark.anyio
    async def test_delete_study(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/studies/VS-015")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_study_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/studies/VS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_study_then_get_returns_404(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/studies/VS-015")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/studies/VS-015")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_study_reduces_count(self, client: AsyncClient):
        before = await client.get(f"{API_PREFIX}/studies")
        before_count = before.json()["total"]
        await client.delete(f"{API_PREFIX}/studies/VS-015")
        after = await client.get(f"{API_PREFIX}/studies")
        assert after.json()["total"] == before_count - 1

    @pytest.mark.anyio
    async def test_delete_study_double_delete(self, client: AsyncClient):
        resp1 = await client.delete(f"{API_PREFIX}/studies/VS-015")
        assert resp1.status_code == 204
        resp2 = await client.delete(f"{API_PREFIX}/studies/VS-015")
        assert resp2.status_code == 404


class TestStudyListFilters:
    """Test validation study list with filters."""

    @pytest.mark.anyio
    async def test_list_studies_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        assert resp.status_code == 200
        assert resp.json()["total"] == 15

    @pytest.mark.anyio
    async def test_list_studies_filter_by_cdx_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"cdx_id": "CDX-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["cdx_id"] == "CDX-001"

    @pytest.mark.anyio
    async def test_list_studies_filter_by_cdx_008(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"cdx_id": "CDX-008"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 3

    @pytest.mark.anyio
    async def test_list_studies_filter_by_type_analytical(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies",
            params={"study_type": "analytical_validation"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["study_type"] == "analytical_validation"

    @pytest.mark.anyio
    async def test_list_studies_filter_by_type_clinical(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies",
            params={"study_type": "clinical_validation"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["study_type"] == "clinical_validation"

    @pytest.mark.anyio
    async def test_list_studies_filter_by_status_completed(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies",
            params={"status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_list_studies_filter_by_status_in_progress(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies",
            params={"status": "in_progress"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    @pytest.mark.anyio
    async def test_list_studies_filter_by_status_planned(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies",
            params={"status": "planned"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.anyio
    async def test_list_studies_filter_nonexistent_cdx(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"cdx_id": "CDX-999"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_list_studies_combined_filters(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies",
            params={"cdx_id": "CDX-008", "study_type": "concordance"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == "VS-010"

    @pytest.mark.anyio
    async def test_list_studies_sorted_by_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        assert resp.status_code == 200
        items = resp.json()["items"]
        ids = [i["id"] for i in items]
        assert ids == sorted(ids)

    @pytest.mark.anyio
    async def test_list_studies_filter_by_type_bridging(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies",
            params={"study_type": "bridging_study"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.anyio
    async def test_list_studies_filter_by_type_proficiency(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies",
            params={"study_type": "proficiency_testing"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.anyio
    async def test_list_studies_filter_by_type_concordance(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies",
            params={"study_type": "concordance"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.anyio
    async def test_list_studies_filter_by_type_reproducibility(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies",
            params={"study_type": "reproducibility"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1


# ===========================================================================
# SECTION 4: Metrics
# ===========================================================================


class TestMetrics:
    """Test CDx portfolio metrics."""

    @pytest.mark.anyio
    async def test_metrics_total_cdx(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cdx"] == 12

    @pytest.mark.anyio
    async def test_metrics_total_studies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        assert resp.json()["total_validation_studies"] == 15

    @pytest.mark.anyio
    async def test_metrics_cdx_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "approved" in data["cdx_by_status"]
        assert data["cdx_by_status"]["approved"] == 4

    @pytest.mark.anyio
    async def test_metrics_cdx_by_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "ihc" in data["cdx_by_type"]
        assert "ngs_panel" in data["cdx_by_type"]

    @pytest.mark.anyio
    async def test_metrics_cdx_by_biomarker_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "genomic" in data["cdx_by_biomarker_type"]
        assert "proteomic" in data["cdx_by_biomarker_type"]

    @pytest.mark.anyio
    async def test_metrics_studies_in_progress(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        assert resp.json()["studies_in_progress"] == 2

    @pytest.mark.anyio
    async def test_metrics_studies_completed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        assert resp.json()["studies_completed"] == 12

    @pytest.mark.anyio
    async def test_metrics_avg_sensitivity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["avg_sensitivity"] is not None
        assert 80.0 <= data["avg_sensitivity"] <= 100.0

    @pytest.mark.anyio
    async def test_metrics_avg_specificity(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["avg_specificity"] is not None
        assert 80.0 <= data["avg_specificity"] <= 100.0

    @pytest.mark.anyio
    async def test_metrics_avg_concordance(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["avg_concordance"] is not None
        assert 80.0 <= data["avg_concordance"] <= 100.0

    @pytest.mark.anyio
    async def test_metrics_approved_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        assert resp.json()["approved_count"] == 4

    @pytest.mark.anyio
    async def test_metrics_pending_submission_count(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        assert resp.json()["pending_submission_count"] == 1

    @pytest.mark.anyio
    async def test_metrics_filter_by_trial_eylea(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cdx"] == 3
        # CDX-001 has 3 studies, CDX-002 has 1 study
        assert data["total_validation_studies"] == 4

    @pytest.mark.anyio
    async def test_metrics_filter_by_trial_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cdx"] == 4

    @pytest.mark.anyio
    async def test_metrics_filter_by_trial_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cdx"] == 5

    @pytest.mark.anyio
    async def test_metrics_filter_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cdx"] == 0
        assert data["total_validation_studies"] == 0
        assert data["approved_count"] == 0

    @pytest.mark.anyio
    async def test_metrics_after_create(self, client: AsyncClient):
        before = await client.get(f"{API_PREFIX}/metrics")
        before_total = before.json()["total_cdx"]

        payload = _make_cdx_create()
        await client.post(f"{API_PREFIX}/cdx", json=payload)

        after = await client.get(f"{API_PREFIX}/metrics")
        assert after.json()["total_cdx"] == before_total + 1

    @pytest.mark.anyio
    async def test_metrics_after_delete(self, client: AsyncClient):
        before = await client.get(f"{API_PREFIX}/metrics")
        before_total = before.json()["total_cdx"]

        await client.delete(f"{API_PREFIX}/cdx/CDX-012")

        after = await client.get(f"{API_PREFIX}/metrics")
        assert after.json()["total_cdx"] == before_total - 1

    @pytest.mark.anyio
    async def test_metrics_cdx_by_status_all_keys(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        status_counts = data["cdx_by_status"]
        # Sum should equal total
        assert sum(status_counts.values()) == data["total_cdx"]


# ===========================================================================
# SECTION 5: Service Direct Tests
# ===========================================================================


class TestServiceDirect:
    """Test service methods directly (non-HTTP)."""

    def test_service_singleton(self):
        svc1 = get_companion_diagnostics_service()
        svc2 = get_companion_diagnostics_service()
        assert svc1 is svc2

    def test_service_reset(self):
        svc1 = get_companion_diagnostics_service()
        svc2 = reset_companion_diagnostics_service()
        assert svc1 is not svc2

    def test_service_list_cdx_count(self, svc: CompanionDiagnosticsService):
        items = svc.list_cdx()
        assert len(items) == 12

    def test_service_list_cdx_filter_trial(self, svc: CompanionDiagnosticsService):
        items = svc.list_cdx(trial_id=EYLEA_TRIAL)
        assert len(items) == 3

    def test_service_list_cdx_filter_status(self, svc: CompanionDiagnosticsService):
        items = svc.list_cdx(status=CdxStatus.APPROVED)
        assert len(items) == 4

    def test_service_list_cdx_filter_type(self, svc: CompanionDiagnosticsService):
        items = svc.list_cdx(cdx_type=CdxType.IHC)
        assert len(items) == 2

    def test_service_list_cdx_filter_biomarker_type(self, svc: CompanionDiagnosticsService):
        items = svc.list_cdx(biomarker_type=BiomarkerType.GENOMIC)
        assert all(c.biomarker_type == BiomarkerType.GENOMIC for c in items)

    def test_service_get_cdx_exists(self, svc: CompanionDiagnosticsService):
        cdx = svc.get_cdx("CDX-001")
        assert cdx is not None
        assert cdx.id == "CDX-001"

    def test_service_get_cdx_not_found(self, svc: CompanionDiagnosticsService):
        assert svc.get_cdx("CDX-NONEXISTENT") is None

    def test_service_create_cdx(self, svc: CompanionDiagnosticsService):
        payload = CdxCreate(
            cdx_name="Service Test CDx",
            cdx_type=CdxType.PCR,
            biomarker_name="Test BM",
            biomarker_type=BiomarkerType.GENOMIC,
            assay_manufacturer="Test Mfr",
            assay_platform="Test Plat",
            drug_name="Test Drug",
            therapeutic_area="Oncology",
        )
        cdx = svc.create_cdx(payload)
        assert cdx.cdx_name == "Service Test CDx"
        assert cdx.status == CdxStatus.IN_DEVELOPMENT

    def test_service_update_cdx(self, svc: CompanionDiagnosticsService):
        payload = CdxUpdate(cdx_name="Updated Name")
        updated = svc.update_cdx("CDX-001", payload)
        assert updated is not None
        assert updated.cdx_name == "Updated Name"

    def test_service_update_cdx_not_found(self, svc: CompanionDiagnosticsService):
        payload = CdxUpdate(cdx_name="Ghost")
        assert svc.update_cdx("CDX-FAKE", payload) is None

    def test_service_delete_cdx(self, svc: CompanionDiagnosticsService):
        assert svc.delete_cdx("CDX-012") is True
        assert svc.get_cdx("CDX-012") is None

    def test_service_delete_cdx_not_found(self, svc: CompanionDiagnosticsService):
        assert svc.delete_cdx("CDX-FAKE") is False

    def test_service_list_studies_count(self, svc: CompanionDiagnosticsService):
        items = svc.list_studies()
        assert len(items) == 15

    def test_service_list_studies_filter_cdx(self, svc: CompanionDiagnosticsService):
        items = svc.list_studies(cdx_id="CDX-001")
        assert len(items) == 3

    def test_service_list_studies_filter_type(self, svc: CompanionDiagnosticsService):
        items = svc.list_studies(study_type=ValidationStudyType.ANALYTICAL_VALIDATION)
        assert all(s.study_type == ValidationStudyType.ANALYTICAL_VALIDATION for s in items)

    def test_service_list_studies_filter_status(self, svc: CompanionDiagnosticsService):
        items = svc.list_studies(status=ValidationStudyStatus.COMPLETED)
        assert all(s.status == ValidationStudyStatus.COMPLETED for s in items)

    def test_service_get_study_exists(self, svc: CompanionDiagnosticsService):
        study = svc.get_study("VS-001")
        assert study is not None
        assert study.id == "VS-001"

    def test_service_get_study_not_found(self, svc: CompanionDiagnosticsService):
        assert svc.get_study("VS-FAKE") is None

    def test_service_create_study(self, svc: CompanionDiagnosticsService):
        payload = CdxValidationStudyCreate(
            study_type=ValidationStudyType.ANALYTICAL_VALIDATION,
            study_name="Service Test Study",
            sample_size=50,
        )
        study = svc.create_study("CDX-001", payload)
        assert study is not None
        assert study.study_name == "Service Test Study"

    def test_service_create_study_cdx_not_found(self, svc: CompanionDiagnosticsService):
        payload = CdxValidationStudyCreate(
            study_type=ValidationStudyType.ANALYTICAL_VALIDATION,
            study_name="Service Test Study",
            sample_size=50,
        )
        assert svc.create_study("CDX-FAKE", payload) is None

    def test_service_update_study(self, svc: CompanionDiagnosticsService):
        payload = CdxValidationStudyUpdate(study_name="Updated Study")
        updated = svc.update_study("VS-001", payload)
        assert updated is not None
        assert updated.study_name == "Updated Study"

    def test_service_update_study_not_found(self, svc: CompanionDiagnosticsService):
        payload = CdxValidationStudyUpdate(study_name="Ghost")
        assert svc.update_study("VS-FAKE", payload) is None

    def test_service_delete_study(self, svc: CompanionDiagnosticsService):
        assert svc.delete_study("VS-015") is True
        assert svc.get_study("VS-015") is None

    def test_service_delete_study_not_found(self, svc: CompanionDiagnosticsService):
        assert svc.delete_study("VS-FAKE") is False

    def test_service_metrics(self, svc: CompanionDiagnosticsService):
        metrics = svc.get_metrics()
        assert metrics.total_cdx == 12
        assert metrics.total_validation_studies == 15
        assert metrics.approved_count == 4

    def test_service_metrics_with_trial_filter(self, svc: CompanionDiagnosticsService):
        metrics = svc.get_metrics(trial_id=EYLEA_TRIAL)
        assert metrics.total_cdx == 3

    def test_service_metrics_empty_trial(self, svc: CompanionDiagnosticsService):
        metrics = svc.get_metrics(trial_id="nonexistent")
        assert metrics.total_cdx == 0
        assert metrics.avg_sensitivity is None


# ===========================================================================
# SECTION 6: Edge Cases & Error Handling
# ===========================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_create_and_get_round_trip(self, client: AsyncClient):
        payload = _make_cdx_create(cdx_name="Round Trip CDx")
        create_resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        assert create_resp.status_code == 201
        cdx_id = create_resp.json()["id"]

        get_resp = await client.get(f"{API_PREFIX}/cdx/{cdx_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["cdx_name"] == "Round Trip CDx"

    @pytest.mark.anyio
    async def test_create_update_get_round_trip(self, client: AsyncClient):
        payload = _make_cdx_create(cdx_name="Update Test CDx")
        create_resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        cdx_id = create_resp.json()["id"]

        update_resp = await client.put(
            f"{API_PREFIX}/cdx/{cdx_id}",
            json={"cdx_name": "Updated CDx Name"},
        )
        assert update_resp.status_code == 200

        get_resp = await client.get(f"{API_PREFIX}/cdx/{cdx_id}")
        assert get_resp.json()["cdx_name"] == "Updated CDx Name"

    @pytest.mark.anyio
    async def test_study_create_and_list_round_trip(self, client: AsyncClient):
        payload = _make_study_create(study_name="Round Trip Study")
        create_resp = await client.post(f"{API_PREFIX}/cdx/CDX-001/studies", json=payload)
        assert create_resp.status_code == 201
        study_id = create_resp.json()["id"]

        list_resp = await client.get(f"{API_PREFIX}/studies", params={"cdx_id": "CDX-001"})
        study_ids = [s["id"] for s in list_resp.json()["items"]]
        assert study_id in study_ids

    @pytest.mark.anyio
    async def test_empty_update_preserves_data(self, client: AsyncClient):
        before = await client.get(f"{API_PREFIX}/cdx/CDX-001")
        before_data = before.json()

        resp = await client.put(f"{API_PREFIX}/cdx/CDX-001", json={})
        assert resp.status_code == 200
        after_data = resp.json()

        # All fields except updated_at should be the same
        for key in before_data:
            if key != "updated_at":
                assert after_data[key] == before_data[key], f"Field {key} changed unexpectedly"

    @pytest.mark.anyio
    async def test_create_cdx_with_null_optional_fields(self, client: AsyncClient):
        payload = _make_cdx_create(
            gene_target=None,
            variant=None,
            sensitivity=None,
            specificity=None,
        )
        resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["gene_target"] is None
        assert data["sensitivity"] is None

    @pytest.mark.anyio
    async def test_list_cdx_after_multiple_creates(self, client: AsyncClient):
        initial = await client.get(f"{API_PREFIX}/cdx")
        initial_count = initial.json()["total"]

        for i in range(5):
            payload = _make_cdx_create(cdx_name=f"Bulk CDx {i}")
            await client.post(f"{API_PREFIX}/cdx", json=payload)

        final = await client.get(f"{API_PREFIX}/cdx")
        assert final.json()["total"] == initial_count + 5

    @pytest.mark.anyio
    async def test_list_studies_after_multiple_creates(self, client: AsyncClient):
        initial = await client.get(f"{API_PREFIX}/studies")
        initial_count = initial.json()["total"]

        for i in range(3):
            payload = _make_study_create(study_name=f"Bulk Study {i}")
            await client.post(f"{API_PREFIX}/cdx/CDX-001/studies", json=payload)

        final = await client.get(f"{API_PREFIX}/studies")
        assert final.json()["total"] == initial_count + 3

    @pytest.mark.anyio
    async def test_ppv_out_of_range_high(self, client: AsyncClient):
        payload = _make_cdx_create(ppv=101.0)
        resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_npv_out_of_range_negative(self, client: AsyncClient):
        payload = _make_cdx_create(npv=-0.1)
        resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_concordance_boundary_values(self, client: AsyncClient):
        # 0 should work
        payload = _make_cdx_create(concordance_rate=0.0)
        resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        assert resp.status_code == 201

        # 100 should work
        payload2 = _make_cdx_create(concordance_rate=100.0)
        resp2 = await client.post(f"{API_PREFIX}/cdx", json=payload2)
        assert resp2.status_code == 201

    @pytest.mark.anyio
    async def test_turnaround_days_zero(self, client: AsyncClient):
        payload = _make_cdx_create(turnaround_days=0)
        resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        assert resp.status_code == 201
        assert resp.json()["turnaround_days"] == 0

    @pytest.mark.anyio
    async def test_study_sensitivity_out_of_range(self, client: AsyncClient):
        payload = _make_study_create(sensitivity=101.0)
        resp = await client.post(f"{API_PREFIX}/cdx/CDX-001/studies", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_study_specificity_negative(self, client: AsyncClient):
        payload = _make_study_create(specificity=-1.0)
        resp = await client.post(f"{API_PREFIX}/cdx/CDX-001/studies", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_cdx_all_regulatory_pathways(self, client: AsyncClient):
        for pathway in RegulatoryPathway:
            payload = _make_cdx_create(regulatory_pathway=pathway.value)
            resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
            assert resp.status_code == 201
            assert resp.json()["regulatory_pathway"] == pathway.value

    @pytest.mark.anyio
    async def test_create_cdx_no_regulatory_pathway(self, client: AsyncClient):
        payload = _make_cdx_create()
        # regulatory_pathway is not in defaults, so it's None
        resp = await client.post(f"{API_PREFIX}/cdx", json=payload)
        assert resp.status_code == 201
        assert resp.json()["regulatory_pathway"] is None

    @pytest.mark.anyio
    async def test_update_cdx_all_status_values(self, client: AsyncClient):
        for status in CdxStatus:
            resp = await client.put(
                f"{API_PREFIX}/cdx/CDX-001",
                json={"status": status.value},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == status.value

    @pytest.mark.anyio
    async def test_update_study_all_status_values(self, client: AsyncClient):
        for status in ValidationStudyStatus:
            resp = await client.put(
                f"{API_PREFIX}/studies/VS-001",
                json={"status": status.value},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == status.value

    @pytest.mark.anyio
    async def test_metrics_consistency_with_list(self, client: AsyncClient):
        """Metrics total should match list total."""
        metrics_resp = await client.get(f"{API_PREFIX}/metrics")
        list_resp = await client.get(f"{API_PREFIX}/cdx")
        assert metrics_resp.json()["total_cdx"] == list_resp.json()["total"]

    @pytest.mark.anyio
    async def test_metrics_studies_consistency(self, client: AsyncClient):
        """Metrics study counts should match list totals."""
        metrics_resp = await client.get(f"{API_PREFIX}/metrics")
        studies_resp = await client.get(f"{API_PREFIX}/studies")
        assert metrics_resp.json()["total_validation_studies"] == studies_resp.json()["total"]

    @pytest.mark.anyio
    async def test_metrics_per_trial_consistency(self, client: AsyncClient):
        """Per-trial metrics should sum correctly."""
        eylea = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": EYLEA_TRIAL})
        dupixent = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": DUPIXENT_TRIAL})
        libtayo = await client.get(f"{API_PREFIX}/metrics", params={"trial_id": LIBTAYO_TRIAL})
        total = await client.get(f"{API_PREFIX}/metrics")

        per_trial_sum = (
            eylea.json()["total_cdx"]
            + dupixent.json()["total_cdx"]
            + libtayo.json()["total_cdx"]
        )
        assert per_trial_sum == total.json()["total_cdx"]
