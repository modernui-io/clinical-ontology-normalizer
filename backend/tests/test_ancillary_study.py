"""Tests for Ancillary Study Management.

Covers:
- Seed data verification (studies, samples, endpoints, sites, agreements)
- Study CRUD (create, read, update, delete, list, filter by type/status/parent)
- Sample management (collect, list, filter, update, track analysis, delete)
- Study endpoint CRUD (create, read, update, delete, list, filter by type)
- Sub-study site management (create, list, filter, update, activate, delete)
- Data sharing agreement lifecycle (create, list, filter, update, delete)
- Study progress computation
- Ancillary metrics dashboard
- Error handling (404s, 400s, invalid operations)
- Edge cases (empty filters, boundary conditions, invalid study references)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.ancillary_study import (
    AgreementStatus,
    AgreementType,
    AnalysisStatus,
    AncillaryStatus,
    AncillaryStudyType,
    EndpointType,
    SampleType,
    StudyRelationship,
    StudySampleCreate,
    SubStudySiteCreate,
    SubStudySiteStatus,
)
from app.services.ancillary_study_service import (
    AncillaryStudyService,
    get_ancillary_study_service,
    reset_ancillary_study_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/ancillary-studies"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_ancillary_study_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> AncillaryStudyService:
    """Shorthand for the fresh service."""
    return fresh_service


@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=True
    ) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_study_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "parent_trial_id": EYLEA_TRIAL,
        "study_name": "Test Ancillary Study",
        "study_type": "biomarker",
        "relationship": "embedded",
        "protocol_number": "TEST-001",
        "pi_name": "Dr. Test PI",
        "pi_institution": "Test University",
        "start_date": now.isoformat(),
        "end_date": (now + timedelta(days=365)).isoformat(),
        "target_enrollment": 50,
        "budget": 500000.0,
        "funding_source": "Test Grant",
        "description": "A test ancillary study for unit testing",
    }
    defaults.update(overrides)
    return defaults


def _make_sample_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "ancillary_study_id": "ANC-001",
        "patient_id": "PAT-TEST-001",
        "site_id": "SITE-101",
        "sample_type": "plasma",
        "collection_date": now.isoformat(),
        "visit_number": 1,
        "processing_instructions": "Centrifuge at 2000g for 15 min",
        "storage_condition": "-80C",
        "aliquot_count": 3,
    }
    defaults.update(overrides)
    return defaults


def _make_endpoint_create(**overrides) -> dict:
    defaults = {
        "ancillary_study_id": "ANC-001",
        "endpoint_name": "Test Endpoint",
        "endpoint_type": "primary",
        "description": "A test endpoint",
        "measurement_method": "ELISA",
        "measurement_timepoints": ["Baseline", "Week 4"],
        "target_value": ">=50%",
        "statistical_method": "ANOVA",
        "analysis_population": "ITT",
    }
    defaults.update(overrides)
    return defaults


def _make_site_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "ancillary_study_id": "ANC-001",
        "site_id": "SITE-NEW-001",
        "site_name": "Test Clinical Site",
        "irb_approval_date": now.isoformat(),
        "irb_expiry_date": (now + timedelta(days=365)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_agreement_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "ancillary_study_id": "ANC-001",
        "partner_organization": "Test Partner Org",
        "agreement_type": "data_use_agreement",
        "effective_date": now.isoformat(),
        "expiry_date": (now + timedelta(days=365)).isoformat(),
        "data_types_shared": ["demographics", "lab_results"],
        "restrictions": "No commercial use",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_studies_count(self, svc: AncillaryStudyService):
        studies = svc.list_studies()
        assert len(studies) == 4

    def test_seed_studies_types(self, svc: AncillaryStudyService):
        studies = svc.list_studies()
        types = {s.study_type for s in studies}
        assert AncillaryStudyType.BIOMARKER in types
        assert AncillaryStudyType.PK_STUDY in types
        assert AncillaryStudyType.COMPANION_DIAGNOSTIC in types
        assert AncillaryStudyType.IMAGING in types

    def test_seed_studies_statuses(self, svc: AncillaryStudyService):
        studies = svc.list_studies()
        statuses = {s.status for s in studies}
        assert AncillaryStatus.ENROLLING in statuses
        assert AncillaryStatus.ACTIVE in statuses
        assert AncillaryStatus.PLANNED in statuses

    def test_seed_samples_count(self, svc: AncillaryStudyService):
        samples = svc.list_samples()
        assert len(samples) == 10

    def test_seed_samples_types(self, svc: AncillaryStudyService):
        samples = svc.list_samples()
        types = {s.sample_type for s in samples}
        assert SampleType.PLASMA in types
        assert SampleType.SERUM in types
        assert SampleType.BLOOD in types
        assert SampleType.TISSUE in types

    def test_seed_endpoints_count(self, svc: AncillaryStudyService):
        endpoints = svc.list_endpoints()
        assert len(endpoints) == 7

    def test_seed_endpoints_types(self, svc: AncillaryStudyService):
        endpoints = svc.list_endpoints()
        types = {e.endpoint_type for e in endpoints}
        assert EndpointType.PRIMARY in types
        assert EndpointType.SECONDARY in types
        assert EndpointType.EXPLORATORY in types
        assert EndpointType.SAFETY in types

    def test_seed_sites_count(self, svc: AncillaryStudyService):
        sites = svc.list_sites()
        assert len(sites) == 6

    def test_seed_agreements_count(self, svc: AncillaryStudyService):
        agreements = svc.list_agreements()
        assert len(agreements) == 3

    def test_seed_agreements_all_active(self, svc: AncillaryStudyService):
        agreements = svc.list_agreements()
        for a in agreements:
            assert a.status == AgreementStatus.ACTIVE


# =====================================================================
# STUDY CRUD
# =====================================================================


class TestStudyCrud:
    """Test study create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_studies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4
        assert len(data["items"]) == 4

    @pytest.mark.anyio
    async def test_list_studies_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/", params={"study_type": "biomarker"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["study_type"] == "biomarker"

    @pytest.mark.anyio
    async def test_list_studies_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/", params={"status": "active"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "active"

    @pytest.mark.anyio
    async def test_list_studies_filter_parent_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/", params={"parent_trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["parent_trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_study(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ANC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ANC-001"
        assert data["study_name"] == "VEGF Biomarker Substudy"

    @pytest.mark.anyio
    async def test_get_study_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ANC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_study(self, client: AsyncClient):
        payload = _make_study_create()
        resp = await client.post(f"{API_PREFIX}/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["study_name"] == "Test Ancillary Study"
        assert data["status"] == "planned"
        assert data["id"].startswith("ANC-")
        assert data["current_enrollment"] == 0

    @pytest.mark.anyio
    async def test_create_study_pk(self, client: AsyncClient):
        payload = _make_study_create(
            study_type="pk_study",
            relationship="mandatory",
            study_name="PK Extension Study",
        )
        resp = await client.post(f"{API_PREFIX}/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["study_type"] == "pk_study"
        assert data["relationship"] == "mandatory"

    @pytest.mark.anyio
    async def test_update_study(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/ANC-001",
            json={
                "study_name": "Updated Biomarker Study",
                "current_enrollment": 85,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["study_name"] == "Updated Biomarker Study"
        assert data["current_enrollment"] == 85

    @pytest.mark.anyio
    async def test_update_study_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/ANC-004",
            json={"status": "protocol_development"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "protocol_development"

    @pytest.mark.anyio
    async def test_update_study_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/ANC-NONEXISTENT",
            json={"study_name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_study(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/ANC-004")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/ANC-004")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_study_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/ANC-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# SAMPLE MANAGEMENT
# =====================================================================


class TestSampleManagement:
    """Test sample collection, listing, updating, and tracking."""

    @pytest.mark.anyio
    async def test_list_samples(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_samples_filter_study(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/samples/", params={"ancillary_study_id": "ANC-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["ancillary_study_id"] == "ANC-001"

    @pytest.mark.anyio
    async def test_list_samples_filter_patient(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/samples/", params={"patient_id": "PAT-1001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["patient_id"] == "PAT-1001"

    @pytest.mark.anyio
    async def test_list_samples_filter_site(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/samples/", params={"site_id": "SITE-101"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "SITE-101"

    @pytest.mark.anyio
    async def test_list_samples_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/samples/", params={"sample_type": "tissue"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["sample_type"] == "tissue"

    @pytest.mark.anyio
    async def test_list_samples_filter_analysis_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/samples/", params={"analysis_status": "completed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["analysis_status"] == "completed"

    @pytest.mark.anyio
    async def test_get_sample(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples/SMP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SMP-001"
        assert data["sample_type"] == "plasma"
        assert data["results_available"] is True

    @pytest.mark.anyio
    async def test_get_sample_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples/SMP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_collect_sample(self, client: AsyncClient):
        payload = _make_sample_create()
        resp = await client.post(f"{API_PREFIX}/samples/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["patient_id"] == "PAT-TEST-001"
        assert data["analysis_status"] == "pending"
        assert data["shipped_to_lab"] is False
        assert data["results_available"] is False
        assert data["id"].startswith("SMP-")

    @pytest.mark.anyio
    async def test_collect_sample_invalid_study(self, client: AsyncClient):
        payload = _make_sample_create(ancillary_study_id="ANC-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/samples/", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_sample_ship(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        resp = await client.put(
            f"{API_PREFIX}/samples/SMP-004",
            json={
                "shipped_to_lab": True,
                "lab_received_date": now.isoformat(),
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["shipped_to_lab"] is True
        assert data["lab_received_date"] is not None

    @pytest.mark.anyio
    async def test_update_sample_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/samples/SMP-NONEXISTENT",
            json={"shipped_to_lab": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_track_analysis_completed(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/samples/SMP-003/track-analysis",
            params={"analysis_status": "completed", "results_available": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["analysis_status"] == "completed"
        assert data["results_available"] is True

    @pytest.mark.anyio
    async def test_track_analysis_failed(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/samples/SMP-004/track-analysis",
            params={"analysis_status": "failed", "results_available": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["analysis_status"] == "failed"

    @pytest.mark.anyio
    async def test_track_analysis_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/samples/SMP-NONEXISTENT/track-analysis",
            params={"analysis_status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sample(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/samples/SMP-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/samples/SMP-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sample_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/samples/SMP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# ENDPOINT MANAGEMENT
# =====================================================================


class TestEndpointManagement:
    """Test study endpoint CRUD operations."""

    @pytest.mark.anyio
    async def test_list_endpoints(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/endpoints/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7

    @pytest.mark.anyio
    async def test_list_endpoints_filter_study(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/endpoints/",
            params={"ancillary_study_id": "ANC-002"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["ancillary_study_id"] == "ANC-002"

    @pytest.mark.anyio
    async def test_list_endpoints_filter_type(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/endpoints/", params={"endpoint_type": "primary"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["endpoint_type"] == "primary"

    @pytest.mark.anyio
    async def test_get_endpoint(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/endpoints/EP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "EP-001"
        assert "VEGF-A" in data["endpoint_name"]

    @pytest.mark.anyio
    async def test_get_endpoint_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/endpoints/EP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_endpoint(self, client: AsyncClient):
        payload = _make_endpoint_create()
        resp = await client.post(f"{API_PREFIX}/endpoints/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["endpoint_name"] == "Test Endpoint"
        assert data["endpoint_type"] == "primary"
        assert data["id"].startswith("EP-")

    @pytest.mark.anyio
    async def test_create_endpoint_invalid_study(self, client: AsyncClient):
        payload = _make_endpoint_create(ancillary_study_id="ANC-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/endpoints/", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_endpoint(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/endpoints/EP-001",
            json={
                "endpoint_name": "Updated VEGF-A Endpoint",
                "target_value": ">=40% reduction",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["endpoint_name"] == "Updated VEGF-A Endpoint"
        assert data["target_value"] == ">=40% reduction"

    @pytest.mark.anyio
    async def test_update_endpoint_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/endpoints/EP-NONEXISTENT",
            json={"endpoint_name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_endpoint(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/endpoints/EP-007")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/endpoints/EP-007")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_endpoint_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/endpoints/EP-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# SUB-STUDY SITE MANAGEMENT
# =====================================================================


class TestSubStudySiteManagement:
    """Test sub-study site operations including activation."""

    @pytest.mark.anyio
    async def test_list_sites(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    @pytest.mark.anyio
    async def test_list_sites_filter_study(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sites/",
            params={"ancillary_study_id": "ANC-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["ancillary_study_id"] == "ANC-001"

    @pytest.mark.anyio
    async def test_list_sites_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/sites/", params={"status": "enrolling"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "enrolling"

    @pytest.mark.anyio
    async def test_get_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SSS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SSS-001"
        assert data["site_name"] == "Memorial Hermann Hospital"

    @pytest.mark.anyio
    async def test_get_site_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SSS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_site(self, client: AsyncClient):
        payload = _make_site_create()
        resp = await client.post(f"{API_PREFIX}/sites/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["site_name"] == "Test Clinical Site"
        assert data["status"] == "pending"
        assert data["patients_enrolled"] == 0
        assert data["samples_collected"] == 0
        assert data["id"].startswith("SSS-")

    @pytest.mark.anyio
    async def test_create_site_invalid_study(self, client: AsyncClient):
        payload = _make_site_create(ancillary_study_id="ANC-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/sites/", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_site(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sites/SSS-004",
            json={"patients_enrolled": 18, "samples_collected": 30},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["patients_enrolled"] == 18
        assert data["samples_collected"] == 30

    @pytest.mark.anyio
    async def test_update_site_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sites/SSS-NONEXISTENT",
            json={"patients_enrolled": 5},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_activate_site_from_pending(self, client: AsyncClient):
        # First create a pending site
        payload = _make_site_create()
        create_resp = await client.post(f"{API_PREFIX}/sites/", json=payload)
        assert create_resp.status_code == 201
        site_id = create_resp.json()["id"]

        # Activate it
        resp = await client.post(f"{API_PREFIX}/sites/{site_id}/activate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "activated"
        assert data["activation_date"] is not None

    @pytest.mark.anyio
    async def test_activate_already_active_site(self, client: AsyncClient):
        # SSS-001 is already enrolling (not pending)
        resp = await client.post(f"{API_PREFIX}/sites/SSS-001/activate")
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_activate_site_not_found(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/sites/SSS-NONEXISTENT/activate"
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_site(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sites/SSS-006")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/sites/SSS-006")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_site_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sites/SSS-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# DATA SHARING AGREEMENTS
# =====================================================================


class TestDataSharingAgreements:
    """Test data sharing agreement lifecycle."""

    @pytest.mark.anyio
    async def test_list_agreements(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3

    @pytest.mark.anyio
    async def test_list_agreements_filter_study(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/agreements/",
            params={"ancillary_study_id": "ANC-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["ancillary_study_id"] == "ANC-001"

    @pytest.mark.anyio
    async def test_list_agreements_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/agreements/", params={"status": "active"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        for item in data["items"]:
            assert item["status"] == "active"

    @pytest.mark.anyio
    async def test_get_agreement(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements/DSA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DSA-001"
        assert data["partner_organization"] == "Genentech Biomarker Lab"

    @pytest.mark.anyio
    async def test_get_agreement_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements/DSA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_agreement(self, client: AsyncClient):
        payload = _make_agreement_create()
        resp = await client.post(f"{API_PREFIX}/agreements/", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["partner_organization"] == "Test Partner Org"
        assert data["status"] == "draft"
        assert data["id"].startswith("DSA-")
        assert "demographics" in data["data_types_shared"]

    @pytest.mark.anyio
    async def test_create_agreement_invalid_study(self, client: AsyncClient):
        payload = _make_agreement_create(ancillary_study_id="ANC-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/agreements/", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_agreement(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/agreements/DSA-001",
            json={
                "status": "expired",
                "restrictions": "Agreement expired - no further data sharing permitted",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "expired"
        assert "expired" in data["restrictions"].lower()

    @pytest.mark.anyio
    async def test_update_agreement_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/agreements/DSA-NONEXISTENT",
            json={"status": "expired"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_agreement(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/agreements/DSA-003")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/agreements/DSA-003")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_agreement_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/agreements/DSA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# STUDY PROGRESS
# =====================================================================


class TestStudyProgress:
    """Test study progress computation."""

    @pytest.mark.anyio
    async def test_get_study_progress(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ANC-001/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["study_id"] == "ANC-001"
        assert data["study_name"] == "VEGF Biomarker Substudy"
        assert data["status"] == "enrolling"
        assert 0 <= data["enrollment_percentage"] <= 100
        assert data["samples_collected"] > 0
        assert data["active_sites"] > 0

    @pytest.mark.anyio
    async def test_get_study_progress_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ANC-NONEXISTENT/progress")
        assert resp.status_code == 404

    def test_study_progress_enrollment_calculation(self, svc: AncillaryStudyService):
        progress = svc.get_study_progress("ANC-001")
        assert progress is not None
        study = svc.get_study("ANC-001")
        assert study is not None
        expected_pct = round(study.current_enrollment / study.target_enrollment * 100, 1)
        assert progress.enrollment_percentage == expected_pct

    def test_study_progress_sample_counts(self, svc: AncillaryStudyService):
        progress = svc.get_study_progress("ANC-001")
        assert progress is not None
        samples = svc.list_samples(ancillary_study_id="ANC-001")
        assert progress.samples_collected == len(samples)
        analyzed = sum(
            1 for s in samples if s.analysis_status == AnalysisStatus.COMPLETED
        )
        assert progress.samples_analyzed == analyzed

    def test_study_progress_active_sites(self, svc: AncillaryStudyService):
        progress = svc.get_study_progress("ANC-001")
        assert progress is not None
        sites = svc.list_sites(ancillary_study_id="ANC-001")
        active = sum(
            1 for s in sites
            if s.status in (SubStudySiteStatus.ACTIVATED, SubStudySiteStatus.ENROLLING)
        )
        assert progress.active_sites == active

    def test_study_progress_planned_study(self, svc: AncillaryStudyService):
        # ANC-004 is planned with 0 enrollment
        progress = svc.get_study_progress("ANC-004")
        assert progress is not None
        assert progress.enrollment_percentage == 0.0
        assert progress.samples_collected == 0
        assert progress.active_sites == 0


# =====================================================================
# METRICS
# =====================================================================


class TestAncillaryMetrics:
    """Test metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_studies"] == 4
        assert data["total_samples"] == 10
        assert data["total_endpoints"] == 7
        assert data["total_sites"] == 6
        assert data["total_agreements"] == 3
        assert data["total_budget"] > 0
        assert data["total_enrollment"] > 0

    def test_metrics_studies_by_type(self, svc: AncillaryStudyService):
        metrics = svc.get_metrics()
        total_by_type = sum(metrics.studies_by_type.values())
        assert total_by_type == metrics.total_studies

    def test_metrics_studies_by_status(self, svc: AncillaryStudyService):
        metrics = svc.get_metrics()
        total_by_status = sum(metrics.studies_by_status.values())
        assert total_by_status == metrics.total_studies

    def test_metrics_samples_pending_and_analyzed(self, svc: AncillaryStudyService):
        metrics = svc.get_metrics()
        # pending + analyzed should not exceed total
        assert metrics.samples_pending_analysis + metrics.samples_analyzed <= metrics.total_samples

    def test_metrics_active_sites(self, svc: AncillaryStudyService):
        metrics = svc.get_metrics()
        assert metrics.active_sites <= metrics.total_sites
        assert metrics.active_sites > 0

    def test_metrics_active_agreements(self, svc: AncillaryStudyService):
        metrics = svc.get_metrics()
        assert metrics.active_agreements <= metrics.total_agreements

    def test_metrics_avg_enrollment(self, svc: AncillaryStudyService):
        metrics = svc.get_metrics()
        assert 0 <= metrics.avg_enrollment_percentage <= 100

    def test_metrics_total_budget(self, svc: AncillaryStudyService):
        metrics = svc.get_metrics()
        studies = svc.list_studies()
        expected_budget = sum(s.budget for s in studies)
        assert metrics.total_budget == expected_budget


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_ancillary_study_service()
        svc2 = get_ancillary_study_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_ancillary_study_service()
        svc2 = reset_ancillary_study_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_ancillary_study_service()
        svc.delete_study("ANC-001")
        assert svc.get_study("ANC-001") is None
        svc2 = reset_ancillary_study_service()
        assert svc2.get_study("ANC-001") is not None


# =====================================================================
# SAMPLE COLLECTION SIDE EFFECTS
# =====================================================================


class TestSampleCollectionSideEffects:
    """Test that sample collection updates site counters."""

    def test_collect_sample_updates_site_counter(self, svc: AncillaryStudyService):
        site = svc.get_site("SSS-001")
        assert site is not None
        initial_count = site.samples_collected

        now = datetime.now(timezone.utc)
        svc.collect_sample(
            StudySampleCreate(
                ancillary_study_id="ANC-001",
                patient_id="PAT-NEW-001",
                site_id="SITE-101",
                sample_type=SampleType.BLOOD,
                collection_date=now,
                visit_number=1,
                processing_instructions="Test processing",
                storage_condition="-80C",
                aliquot_count=2,
            )
        )

        site = svc.get_site("SSS-001")
        assert site is not None
        assert site.samples_collected == initial_count + 1


# =====================================================================
# SITE ACTIVATION LOGIC
# =====================================================================


class TestSiteActivation:
    """Test site activation state machine."""

    def test_activate_pending_site(self, svc: AncillaryStudyService):
        # Create a pending site
        site = svc.create_site(
            SubStudySiteCreate(
                ancillary_study_id="ANC-001",
                site_id="SITE-NEW-ACTIVATE",
                site_name="New Activation Site",
            )
        )
        assert site.status == SubStudySiteStatus.PENDING

        activated = svc.activate_site(site.id)
        assert activated is not None
        assert activated.status == SubStudySiteStatus.ACTIVATED
        assert activated.activation_date is not None

    def test_cannot_activate_enrolling_site(self, svc: AncillaryStudyService):
        # SSS-001 is enrolling
        with pytest.raises(ValueError):
            svc.activate_site("SSS-001")

    def test_activate_nonexistent_site(self, svc: AncillaryStudyService):
        result = svc.activate_site("SSS-NONEXISTENT")
        assert result is None


# =====================================================================
# ANALYSIS TRACKING
# =====================================================================


class TestAnalysisTracking:
    """Test sample analysis tracking operations."""

    def test_track_analysis_to_completed(self, svc: AncillaryStudyService):
        result = svc.track_analysis("SMP-003", AnalysisStatus.COMPLETED, True)
        assert result is not None
        assert result.analysis_status == AnalysisStatus.COMPLETED
        assert result.results_available is True

    def test_track_analysis_to_failed(self, svc: AncillaryStudyService):
        result = svc.track_analysis("SMP-004", AnalysisStatus.FAILED, False)
        assert result is not None
        assert result.analysis_status == AnalysisStatus.FAILED
        assert result.results_available is False

    def test_track_analysis_to_repeated(self, svc: AncillaryStudyService):
        result = svc.track_analysis("SMP-009", AnalysisStatus.REPEATED, False)
        assert result is not None
        assert result.analysis_status == AnalysisStatus.REPEATED

    def test_track_analysis_nonexistent(self, svc: AncillaryStudyService):
        result = svc.track_analysis("SMP-NONEXISTENT", AnalysisStatus.COMPLETED, True)
        assert result is None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_studies_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_samples_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples/")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_endpoints_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/endpoints/")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_sites_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_agreements_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements/")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_study_all_types(self, client: AsyncClient):
        for study_type in [
            "pk_study", "pd_study", "biomarker", "companion_diagnostic",
            "imaging", "genetic", "quality_of_life", "health_economics",
            "registry", "long_term_extension",
        ]:
            payload = _make_study_create(
                study_type=study_type,
                study_name=f"Test {study_type} study",
                protocol_number=f"TEST-{study_type}",
            )
            resp = await client.post(f"{API_PREFIX}/", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["study_type"] == study_type

    @pytest.mark.anyio
    async def test_create_study_all_relationships(self, client: AsyncClient):
        for rel in ["embedded", "parallel", "sequential", "optional", "mandatory"]:
            payload = _make_study_create(
                relationship=rel,
                study_name=f"Test {rel} study",
                protocol_number=f"TEST-REL-{rel}",
            )
            resp = await client.post(f"{API_PREFIX}/", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["relationship"] == rel

    @pytest.mark.anyio
    async def test_create_sample_all_types(self, client: AsyncClient):
        for sample_type in ["blood", "serum", "plasma", "urine", "tissue", "csf", "saliva", "bone_marrow"]:
            payload = _make_sample_create(
                sample_type=sample_type,
                patient_id=f"PAT-TYPE-{sample_type}",
            )
            resp = await client.post(f"{API_PREFIX}/samples/", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["sample_type"] == sample_type

    @pytest.mark.anyio
    async def test_create_endpoint_all_types(self, client: AsyncClient):
        for ep_type in ["primary", "secondary", "exploratory", "safety"]:
            payload = _make_endpoint_create(
                endpoint_type=ep_type,
                endpoint_name=f"Test {ep_type} endpoint",
            )
            resp = await client.post(f"{API_PREFIX}/endpoints/", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["endpoint_type"] == ep_type

    @pytest.mark.anyio
    async def test_create_agreement_all_types(self, client: AsyncClient):
        for ag_type in ["data_use_agreement", "material_transfer", "collaboration", "license"]:
            payload = _make_agreement_create(
                agreement_type=ag_type,
                partner_organization=f"Partner for {ag_type}",
            )
            resp = await client.post(f"{API_PREFIX}/agreements/", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["agreement_type"] == ag_type

    @pytest.mark.anyio
    async def test_study_sorted_by_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/")
        data = resp.json()
        ids = [item["id"] for item in data["items"]]
        assert ids == sorted(ids)

    @pytest.mark.anyio
    async def test_samples_sorted_by_collection_date_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples/")
        data = resp.json()
        dates = [item["collection_date"] for item in data["items"]]
        assert dates == sorted(dates, reverse=True)


# =====================================================================
# DETAILED FIELD VALIDATION
# =====================================================================


class TestFieldValidation:
    """Test that fields are correctly populated."""

    @pytest.mark.anyio
    async def test_study_has_all_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ANC-001")
        data = resp.json()
        assert "id" in data
        assert "parent_trial_id" in data
        assert "study_name" in data
        assert "study_type" in data
        assert "relationship" in data
        assert "status" in data
        assert "protocol_number" in data
        assert "pi_name" in data
        assert "pi_institution" in data
        assert "target_enrollment" in data
        assert "current_enrollment" in data
        assert "budget" in data
        assert "funding_source" in data
        assert "description" in data

    @pytest.mark.anyio
    async def test_sample_has_all_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/samples/SMP-001")
        data = resp.json()
        assert "id" in data
        assert "ancillary_study_id" in data
        assert "patient_id" in data
        assert "site_id" in data
        assert "sample_type" in data
        assert "collection_date" in data
        assert "visit_number" in data
        assert "processing_instructions" in data
        assert "storage_condition" in data
        assert "aliquot_count" in data
        assert "shipped_to_lab" in data
        assert "analysis_status" in data
        assert "results_available" in data

    @pytest.mark.anyio
    async def test_endpoint_has_all_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/endpoints/EP-001")
        data = resp.json()
        assert "id" in data
        assert "ancillary_study_id" in data
        assert "endpoint_name" in data
        assert "endpoint_type" in data
        assert "description" in data
        assert "measurement_method" in data
        assert "measurement_timepoints" in data
        assert "statistical_method" in data
        assert "analysis_population" in data

    @pytest.mark.anyio
    async def test_site_has_all_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/SSS-001")
        data = resp.json()
        assert "id" in data
        assert "ancillary_study_id" in data
        assert "site_id" in data
        assert "site_name" in data
        assert "activation_date" in data
        assert "status" in data
        assert "patients_enrolled" in data
        assert "samples_collected" in data
        assert "irb_approval_date" in data
        assert "irb_expiry_date" in data

    @pytest.mark.anyio
    async def test_agreement_has_all_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/agreements/DSA-001")
        data = resp.json()
        assert "id" in data
        assert "ancillary_study_id" in data
        assert "partner_organization" in data
        assert "agreement_type" in data
        assert "effective_date" in data
        assert "expiry_date" in data
        assert "data_types_shared" in data
        assert "status" in data

    @pytest.mark.anyio
    async def test_progress_has_all_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/ANC-001/progress")
        data = resp.json()
        assert "study_id" in data
        assert "study_name" in data
        assert "status" in data
        assert "enrollment_percentage" in data
        assert "samples_collected" in data
        assert "samples_analyzed" in data
        assert "active_sites" in data
        assert "endpoints_defined" in data
        assert "agreements_active" in data

    @pytest.mark.anyio
    async def test_metrics_has_all_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics/")
        data = resp.json()
        assert "total_studies" in data
        assert "studies_by_type" in data
        assert "studies_by_status" in data
        assert "total_samples" in data
        assert "samples_pending_analysis" in data
        assert "samples_analyzed" in data
        assert "total_endpoints" in data
        assert "total_sites" in data
        assert "active_sites" in data
        assert "total_agreements" in data
        assert "active_agreements" in data
        assert "total_budget" in data
        assert "total_enrollment" in data
        assert "avg_enrollment_percentage" in data
