"""Tests for Clinical Imaging Management (IMG-MGMT).

Covers:
- Seed data verification (studies, acquisitions, readers, assessments, QC reviews)
- Imaging study CRUD (create, read, update, delete, list, filter by trial/modality/criteria)
- Image acquisition CRUD (create, read, update, delete, list, filter)
- Central reader CRUD (create, read, update, delete, list, filter by status/modality)
- Disease assessment CRUD (create, read, delete, list, filter)
- Image quality review CRUD (create, read, delete, list, filter by outcome)
- Metrics computation (QC pass rate, reader agreement rate, aggregations)
- Error handling (404s, invalid operations)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.imaging_management import (
    AssessmentCriteria,
    ImageStatus,
    ImagingModality,
    OverallResponse,
    QCOutcome,
    QualificationStatus,
    ReadingDesign,
)
from app.services.imaging_management_service import (
    ImagingManagementService,
    get_imaging_management_service,
    reset_imaging_management_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/imaging-management"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_imaging_management_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ImagingManagementService:
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


def _make_study_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "title": "Test Imaging Study",
        "modalities": ["oct"],
        "assessment_criteria": "etdrs",
        "reading_design": "single_reader",
        "blinded": True,
        "assessment_schedule": ["Screening", "Week 12"],
        "charter_version": "1.0",
        "vendor": "Test Vendor",
    }
    defaults.update(overrides)
    return defaults


def _make_acquisition_create(**overrides) -> dict:
    defaults = {
        "study_id": "IMG-STUDY-001",
        "subject_id": "SUBJ-TEST-001",
        "visit": "Screening",
        "modality": "oct",
        "site_id": "SITE-101",
    }
    defaults.update(overrides)
    return defaults


def _make_reader_create(**overrides) -> dict:
    defaults = {
        "name": "Dr. Test Reader",
        "specialty": "Radiology",
        "institution": "Test Hospital",
        "qualified_modalities": ["ct", "mri"],
        "qualified_criteria": ["recist_1_1"],
    }
    defaults.update(overrides)
    return defaults


def _make_assessment_create(**overrides) -> dict:
    defaults = {
        "acquisition_id": "ACQ-001",
        "reader_id": "RDR-001",
        "assessment_criteria": "recist_1_1",
        "timepoint": "Week 8",
        "target_lesion_count": 2,
        "target_lesion_sum_mm": 45.0,
    }
    defaults.update(overrides)
    return defaults


def _make_qc_create(**overrides) -> dict:
    defaults = {
        "acquisition_id": "ACQ-001",
        "reviewer": "QC Tester",
        "outcome": "pass",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_studies_count(self, svc: ImagingManagementService):
        studies = svc.list_studies()
        assert len(studies) == 10

    def test_seed_studies_across_trials(self, svc: ImagingManagementService):
        eylea = svc.list_studies(trial_id=EYLEA_TRIAL)
        dupixent = svc.list_studies(trial_id=DUPIXENT_TRIAL)
        libtayo = svc.list_studies(trial_id=LIBTAYO_TRIAL)
        assert len(eylea) > 0
        assert len(dupixent) > 0
        assert len(libtayo) > 0
        assert len(eylea) + len(dupixent) + len(libtayo) == 10

    def test_seed_eylea_modalities(self, svc: ImagingManagementService):
        studies = svc.list_studies(trial_id=EYLEA_TRIAL)
        modalities = set()
        for s in studies:
            modalities.update(s.modalities)
        assert ImagingModality.OCT in modalities
        assert ImagingModality.FUNDUS_PHOTO in modalities

    def test_seed_eylea_criteria(self, svc: ImagingManagementService):
        studies = svc.list_studies(trial_id=EYLEA_TRIAL)
        criteria = {s.assessment_criteria for s in studies}
        assert AssessmentCriteria.ETDRS in criteria

    def test_seed_dupixent_criteria(self, svc: ImagingManagementService):
        studies = svc.list_studies(trial_id=DUPIXENT_TRIAL)
        criteria = {s.assessment_criteria for s in studies}
        assert AssessmentCriteria.EASI in criteria

    def test_seed_libtayo_modalities(self, svc: ImagingManagementService):
        studies = svc.list_studies(trial_id=LIBTAYO_TRIAL)
        modalities = set()
        for s in studies:
            modalities.update(s.modalities)
        assert ImagingModality.CT in modalities
        assert ImagingModality.MRI in modalities

    def test_seed_libtayo_criteria(self, svc: ImagingManagementService):
        studies = svc.list_studies(trial_id=LIBTAYO_TRIAL)
        criteria = {s.assessment_criteria for s in studies}
        assert AssessmentCriteria.RECIST_1_1 in criteria

    def test_seed_acquisitions_count(self, svc: ImagingManagementService):
        acqs = svc.list_acquisitions()
        assert len(acqs) >= 10

    def test_seed_readers_count(self, svc: ImagingManagementService):
        readers = svc.list_readers()
        assert len(readers) >= 10

    def test_seed_assessments_count(self, svc: ImagingManagementService):
        assessments = svc.list_assessments()
        assert len(assessments) >= 10

    def test_seed_qc_reviews_count(self, svc: ImagingManagementService):
        qc = svc.list_qc_reviews()
        assert len(qc) >= 10

    def test_seed_reader_statuses(self, svc: ImagingManagementService):
        readers = svc.list_readers()
        statuses = {r.qualification_status for r in readers}
        assert QualificationStatus.QUALIFIED in statuses
        assert QualificationStatus.IN_TRAINING in statuses

    def test_seed_qc_outcomes(self, svc: ImagingManagementService):
        qc = svc.list_qc_reviews()
        outcomes = {q.outcome for q in qc}
        assert QCOutcome.PASS in outcomes
        assert QCOutcome.FAIL in outcomes


# =====================================================================
# IMAGING STUDY CRUD
# =====================================================================


class TestImagingStudyCrud:
    """Test imaging study create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_studies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_studies_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_studies_filter_modality(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"modality": "ct"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert "ct" in item["modalities"]

    @pytest.mark.anyio
    async def test_list_studies_filter_criteria(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"criteria": "recist_1_1"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["assessment_criteria"] == "recist_1_1"

    @pytest.mark.anyio
    async def test_get_study(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/IMG-STUDY-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "IMG-STUDY-001"
        assert data["title"] == "EYLEA Retinal Imaging Sub-study"

    @pytest.mark.anyio
    async def test_get_study_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/IMG-STUDY-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_study(self, client: AsyncClient):
        payload = _make_study_create()
        resp = await client.post(f"{API_PREFIX}/studies", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Imaging Study"
        assert data["id"].startswith("IMG-STUDY-")
        assert data["total_subjects"] == 0

    @pytest.mark.anyio
    async def test_create_study_with_all_fields(self, client: AsyncClient):
        payload = _make_study_create(
            title="Full Study",
            modalities=["ct", "mri", "pet_ct"],
            assessment_criteria="recist_1_1",
            reading_design="dual_reader",
            blinded=False,
            assessment_schedule=["Screening", "Week 8", "Week 16", "Week 24"],
            charter_version="5.0",
            vendor="Full Test Vendor",
        )
        resp = await client.post(f"{API_PREFIX}/studies", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Full Study"
        assert len(data["modalities"]) == 3

    @pytest.mark.anyio
    async def test_update_study(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/studies/IMG-STUDY-001",
            json={"title": "Updated Title", "total_subjects": 300},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Title"
        assert data["total_subjects"] == 300

    @pytest.mark.anyio
    async def test_update_study_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/studies/IMG-STUDY-NONEXISTENT",
            json={"title": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_study_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/studies/IMG-STUDY-001",
            json={"status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"

    @pytest.mark.anyio
    async def test_update_study_charter_version(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/studies/IMG-STUDY-001",
            json={"charter_version": "4.0"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["charter_version"] == "4.0"

    @pytest.mark.anyio
    async def test_delete_study(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/studies/IMG-STUDY-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/studies/IMG-STUDY-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_study_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/studies/IMG-STUDY-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_studies_sorted_by_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        data = resp.json()
        ids = [item["id"] for item in data["items"]]
        assert ids == sorted(ids)


# =====================================================================
# IMAGE ACQUISITION CRUD
# =====================================================================


class TestImageAcquisitionCrud:
    """Test image acquisition create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_acquisitions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/acquisitions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 10

    @pytest.mark.anyio
    async def test_list_acquisitions_filter_study(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/acquisitions", params={"study_id": "IMG-STUDY-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["study_id"] == "IMG-STUDY-001"

    @pytest.mark.anyio
    async def test_list_acquisitions_filter_modality(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/acquisitions", params={"modality": "ct"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["modality"] == "ct"

    @pytest.mark.anyio
    async def test_list_acquisitions_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/acquisitions", params={"status": "read_complete"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "read_complete"

    @pytest.mark.anyio
    async def test_get_acquisition(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/acquisitions/ACQ-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ACQ-001"
        assert data["modality"] == "oct"

    @pytest.mark.anyio
    async def test_get_acquisition_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/acquisitions/ACQ-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_acquisition(self, client: AsyncClient):
        payload = _make_acquisition_create()
        resp = await client.post(f"{API_PREFIX}/acquisitions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("ACQ-")
        assert data["status"] == "pending_upload"
        assert data["file_count"] == 0

    @pytest.mark.anyio
    async def test_create_acquisition_with_options(self, client: AsyncClient):
        payload = _make_acquisition_create(
            modality="ct",
            series_description="Chest CT with contrast",
            slice_thickness_mm=2.5,
            contrast_used=True,
            technologist="Test Tech",
        )
        resp = await client.post(f"{API_PREFIX}/acquisitions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["modality"] == "ct"
        assert data["contrast_used"] is True
        assert data["slice_thickness_mm"] == 2.5

    @pytest.mark.anyio
    async def test_update_acquisition(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/acquisitions/ACQ-004",
            json={"status": "qc_passed", "file_count": 130, "total_size_mb": 260.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "qc_passed"
        assert data["file_count"] == 130

    @pytest.mark.anyio
    async def test_update_acquisition_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/acquisitions/ACQ-NONEXISTENT",
            json={"status": "uploaded"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_acquisition(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/acquisitions/ACQ-014")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/acquisitions/ACQ-014")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_acquisition_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/acquisitions/ACQ-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_acquisition_upload_date_auto_set(self, client: AsyncClient):
        """Upload date should auto-set when status changes to uploaded from pending_upload."""
        # ACQ-013 is pending_upload
        resp = await client.put(
            f"{API_PREFIX}/acquisitions/ACQ-013",
            json={"status": "uploaded"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "uploaded"
        assert data["upload_date"] is not None


# =====================================================================
# CENTRAL READER CRUD
# =====================================================================


class TestCentralReaderCrud:
    """Test central reader create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_readers(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/readers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 10

    @pytest.mark.anyio
    async def test_list_readers_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/readers", params={"qualification_status": "qualified"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["qualification_status"] == "qualified"

    @pytest.mark.anyio
    async def test_list_readers_filter_modality(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/readers", params={"modality": "oct"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert "oct" in item["qualified_modalities"]

    @pytest.mark.anyio
    async def test_get_reader(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/readers/RDR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RDR-001"
        assert data["name"] == "Dr. Elizabeth Warren"

    @pytest.mark.anyio
    async def test_get_reader_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/readers/RDR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_reader(self, client: AsyncClient):
        payload = _make_reader_create()
        resp = await client.post(f"{API_PREFIX}/readers", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Dr. Test Reader"
        assert data["id"].startswith("RDR-")
        assert data["qualification_status"] == "in_training"
        assert data["cases_read"] == 0

    @pytest.mark.anyio
    async def test_update_reader(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/readers/RDR-007",
            json={"qualification_status": "qualified", "cases_read": 50, "agreement_rate": 92.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["qualification_status"] == "qualified"
        assert data["cases_read"] == 50
        assert data["agreement_rate"] == 92.0

    @pytest.mark.anyio
    async def test_update_reader_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/readers/RDR-NONEXISTENT",
            json={"cases_read": 10},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_reader_deactivate(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/readers/RDR-001",
            json={"active": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is False

    @pytest.mark.anyio
    async def test_update_reader_modalities(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/readers/RDR-007",
            json={"qualified_modalities": ["oct", "fundus_photography"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "oct" in data["qualified_modalities"]

    @pytest.mark.anyio
    async def test_delete_reader(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/readers/RDR-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/readers/RDR-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_reader_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/readers/RDR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_reader_training_date_auto_set(self, client: AsyncClient):
        """Training completed date should auto-set when status changes to qualified."""
        # RDR-007 is in_training with no training_completed_date
        resp = await client.get(f"{API_PREFIX}/readers/RDR-007")
        data = resp.json()
        assert data["training_completed_date"] is None

        resp = await client.put(
            f"{API_PREFIX}/readers/RDR-007",
            json={"qualification_status": "qualified"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["training_completed_date"] is not None


# =====================================================================
# DISEASE ASSESSMENT CRUD
# =====================================================================


class TestDiseaseAssessmentCrud:
    """Test disease assessment create, read, delete operations."""

    @pytest.mark.anyio
    async def test_list_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 10

    @pytest.mark.anyio
    async def test_list_assessments_filter_acquisition(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments", params={"acquisition_id": "ACQ-008"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["acquisition_id"] == "ACQ-008"

    @pytest.mark.anyio
    async def test_list_assessments_filter_reader(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments", params={"reader_id": "RDR-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["reader_id"] == "RDR-001"

    @pytest.mark.anyio
    async def test_list_assessments_filter_criteria(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments", params={"criteria": "recist_1_1"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["assessment_criteria"] == "recist_1_1"

    @pytest.mark.anyio
    async def test_get_assessment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/DA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DA-001"
        assert data["assessment_criteria"] == "etdrs"

    @pytest.mark.anyio
    async def test_get_assessment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/DA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_assessment(self, client: AsyncClient):
        payload = _make_assessment_create()
        resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("DA-")
        assert data["acquisition_id"] == "ACQ-001"
        assert data["target_lesion_count"] == 2

    @pytest.mark.anyio
    async def test_create_assessment_with_response(self, client: AsyncClient):
        payload = _make_assessment_create(
            overall_response="partial_response",
            percent_change_from_baseline=-35.0,
            percent_change_from_nadir=-35.0,
            new_lesions=False,
            comments="Test PR assessment",
        )
        resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["overall_response"] == "partial_response"
        assert data["percent_change_from_baseline"] == -35.0

    @pytest.mark.anyio
    async def test_create_assessment_progressive_disease(self, client: AsyncClient):
        payload = _make_assessment_create(
            overall_response="progressive_disease",
            new_lesions=True,
            comments="New lesions identified",
        )
        resp = await client.post(f"{API_PREFIX}/assessments", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["overall_response"] == "progressive_disease"
        assert data["new_lesions"] is True

    @pytest.mark.anyio
    async def test_delete_assessment(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assessments/DA-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/assessments/DA-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_assessment_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/assessments/DA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_assessments_sorted_by_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        data = resp.json()
        ids = [item["id"] for item in data["items"]]
        assert ids == sorted(ids)


# =====================================================================
# IMAGE QUALITY REVIEW CRUD
# =====================================================================


class TestImageQualityReviewCrud:
    """Test image quality review create, read, delete operations."""

    @pytest.mark.anyio
    async def test_list_qc_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qc-reviews")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 10

    @pytest.mark.anyio
    async def test_list_qc_reviews_filter_acquisition(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qc-reviews", params={"acquisition_id": "ACQ-001"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["acquisition_id"] == "ACQ-001"

    @pytest.mark.anyio
    async def test_list_qc_reviews_filter_outcome_pass(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qc-reviews", params={"outcome": "pass"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["outcome"] == "pass"

    @pytest.mark.anyio
    async def test_list_qc_reviews_filter_outcome_fail(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qc-reviews", params={"outcome": "fail"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["outcome"] == "fail"

    @pytest.mark.anyio
    async def test_get_qc_review(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qc-reviews/QC-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "QC-001"
        assert data["outcome"] == "pass"

    @pytest.mark.anyio
    async def test_get_qc_review_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qc-reviews/QC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_qc_review_pass(self, client: AsyncClient):
        payload = _make_qc_create()
        resp = await client.post(f"{API_PREFIX}/qc-reviews", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("QC-")
        assert data["outcome"] == "pass"
        assert data["protocol_compliant"] is True

    @pytest.mark.anyio
    async def test_create_qc_review_fail(self, client: AsyncClient):
        payload = _make_qc_create(
            outcome="fail",
            issues=["Slice thickness exceeds protocol", "Missing contrast phase"],
            protocol_compliant=False,
            resolution_adequate=False,
            action_required="Rescan required",
        )
        resp = await client.post(f"{API_PREFIX}/qc-reviews", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["outcome"] == "fail"
        assert data["protocol_compliant"] is False
        assert len(data["issues"]) == 2

    @pytest.mark.anyio
    async def test_create_qc_review_minor_deviation(self, client: AsyncClient):
        payload = _make_qc_create(
            outcome="minor_deviation",
            issues=["Slight motion artifact"],
            action_required="Acceptable for grading",
        )
        resp = await client.post(f"{API_PREFIX}/qc-reviews", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["outcome"] == "minor_deviation"

    @pytest.mark.anyio
    async def test_create_qc_review_rescan_required(self, client: AsyncClient):
        payload = _make_qc_create(
            outcome="rescan_required",
            issues=["Incomplete coverage"],
            coverage_adequate=False,
            action_required="Rescan with full coverage",
        )
        resp = await client.post(f"{API_PREFIX}/qc-reviews", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["outcome"] == "rescan_required"
        assert data["coverage_adequate"] is False

    @pytest.mark.anyio
    async def test_delete_qc_review(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/qc-reviews/QC-013")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/qc-reviews/QC-013")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_qc_review_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/qc-reviews/QC-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_qc_review_with_major_deviation(self, client: AsyncClient):
        payload = _make_qc_create(
            outcome="major_deviation",
            issues=["SUV calibration off", "Missing series"],
            protocol_compliant=False,
        )
        resp = await client.post(f"{API_PREFIX}/qc-reviews", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["outcome"] == "major_deviation"


# =====================================================================
# METRICS
# =====================================================================


class TestMetrics:
    """Test imaging management metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_studies"] == 10
        assert data["total_acquisitions"] >= 10
        assert data["total_readers"] >= 10
        assert data["total_assessments"] >= 10
        assert data["total_qc_reviews"] >= 10

    @pytest.mark.anyio
    async def test_metrics_qc_pass_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0 <= data["qc_pass_rate"] <= 100
        # With seed data: 7 pass + 2 minor = 9 passing out of 13 total
        assert data["qc_pass_rate"] > 50

    @pytest.mark.anyio
    async def test_metrics_avg_reader_agreement(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0 <= data["avg_reader_agreement_rate"] <= 100
        assert data["avg_reader_agreement_rate"] > 80

    @pytest.mark.anyio
    async def test_metrics_acquisitions_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert len(data["acquisitions_by_status"]) > 0
        total_by_status = sum(data["acquisitions_by_status"].values())
        assert total_by_status == data["total_acquisitions"]

    @pytest.mark.anyio
    async def test_metrics_acquisitions_by_modality(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert len(data["acquisitions_by_modality"]) > 0
        total_by_modality = sum(data["acquisitions_by_modality"].values())
        assert total_by_modality == data["total_acquisitions"]

    @pytest.mark.anyio
    async def test_metrics_qualified_readers(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["qualified_readers"] > 0
        assert data["qualified_readers"] <= data["total_readers"]

    @pytest.mark.anyio
    async def test_metrics_readers_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_status = sum(data["readers_by_status"].values())
        assert total_by_status == data["total_readers"]

    @pytest.mark.anyio
    async def test_metrics_qc_by_outcome(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_outcome = sum(data["qc_by_outcome"].values())
        assert total_by_outcome == data["total_qc_reviews"]

    def test_metrics_qc_pass_rate_calculation(self, svc: ImagingManagementService):
        """Verify QC pass rate = (pass + minor_deviation) / total * 100."""
        metrics = svc.get_metrics()
        qc_reviews = svc.list_qc_reviews()
        total = len(qc_reviews)
        passing = sum(
            1 for q in qc_reviews
            if q.outcome in (QCOutcome.PASS, QCOutcome.MINOR_DEVIATION)
        )
        expected_rate = round((passing / total * 100) if total > 0 else 0.0, 1)
        assert metrics.qc_pass_rate == expected_rate

    def test_metrics_avg_agreement_rate_calculation(self, svc: ImagingManagementService):
        """Verify avg agreement rate from readers with agreement_rate set."""
        metrics = svc.get_metrics()
        readers = svc.list_readers()
        rates = [r.agreement_rate for r in readers if r.agreement_rate is not None]
        expected = round(sum(rates) / len(rates), 1) if rates else 0.0
        assert metrics.avg_reader_agreement_rate == expected

    @pytest.mark.anyio
    async def test_metrics_assessments_by_response(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert isinstance(data["assessments_by_response"], dict)


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_imaging_management_service()
        svc2 = get_imaging_management_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_imaging_management_service()
        svc2 = reset_imaging_management_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_imaging_management_service()
        svc.delete_study("IMG-STUDY-001")
        assert svc.get_study("IMG-STUDY-001") is None
        svc2 = reset_imaging_management_service()
        assert svc2.get_study("IMG-STUDY-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_studies_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_acquisitions_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/acquisitions")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_readers_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/readers")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_assessments_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_qc_reviews_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qc-reviews")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_multiple_studies(self, client: AsyncClient):
        for i in range(3):
            payload = _make_study_create(title=f"Batch Study {i}")
            resp = await client.post(f"{API_PREFIX}/studies", json=payload)
            assert resp.status_code == 201

        resp = await client.get(f"{API_PREFIX}/studies")
        data = resp.json()
        assert data["total"] == 13

    @pytest.mark.anyio
    async def test_create_multiple_acquisitions(self, client: AsyncClient):
        for i in range(3):
            payload = _make_acquisition_create(subject_id=f"SUBJ-BATCH-{i}")
            resp = await client.post(f"{API_PREFIX}/acquisitions", json=payload)
            assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_create_multiple_readers(self, client: AsyncClient):
        for i in range(3):
            payload = _make_reader_create(name=f"Dr. Batch Reader {i}")
            resp = await client.post(f"{API_PREFIX}/readers", json=payload)
            assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_study_contains_required_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/IMG-STUDY-005")
        data = resp.json()
        assert "id" in data
        assert "trial_id" in data
        assert "title" in data
        assert "modalities" in data
        assert "assessment_criteria" in data
        assert "reading_design" in data
        assert "blinded" in data
        assert "charter_version" in data
        assert "vendor" in data
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_acquisition_contains_required_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/acquisitions/ACQ-007")
        data = resp.json()
        assert "id" in data
        assert "study_id" in data
        assert "subject_id" in data
        assert "visit" in data
        assert "modality" in data
        assert "status" in data
        assert "site_id" in data

    @pytest.mark.anyio
    async def test_reader_contains_required_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/readers/RDR-001")
        data = resp.json()
        assert "id" in data
        assert "name" in data
        assert "specialty" in data
        assert "institution" in data
        assert "qualification_status" in data
        assert "qualified_modalities" in data
        assert "cases_read" in data

    @pytest.mark.anyio
    async def test_assessment_contains_required_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/DA-004")
        data = resp.json()
        assert "id" in data
        assert "acquisition_id" in data
        assert "reader_id" in data
        assert "assessment_criteria" in data
        assert "timepoint" in data
        assert "overall_response" in data
        assert "assessment_date" in data

    @pytest.mark.anyio
    async def test_qc_review_contains_required_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qc-reviews/QC-009")
        data = resp.json()
        assert "id" in data
        assert "acquisition_id" in data
        assert "reviewer" in data
        assert "outcome" in data
        assert "issues" in data
        assert "protocol_compliant" in data

    @pytest.mark.anyio
    async def test_list_studies_filter_returns_empty_for_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies", params={"trial_id": "nonexistent-trial"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    @pytest.mark.anyio
    async def test_list_acquisitions_filter_returns_empty_for_nonexistent_study(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/acquisitions", params={"study_id": "nonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


# =====================================================================
# ENUM COVERAGE
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout the system."""

    @pytest.mark.anyio
    async def test_imaging_modalities_in_studies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        data = resp.json()
        all_modalities = set()
        for item in data["items"]:
            all_modalities.update(item["modalities"])
        assert "oct" in all_modalities
        assert "ct" in all_modalities
        assert "mri" in all_modalities

    @pytest.mark.anyio
    async def test_assessment_criteria_in_studies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        data = resp.json()
        criteria = {item["assessment_criteria"] for item in data["items"]}
        assert "recist_1_1" in criteria
        assert "etdrs" in criteria
        assert "easi" in criteria

    @pytest.mark.anyio
    async def test_reading_designs_in_studies(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies")
        data = resp.json()
        designs = {item["reading_design"] for item in data["items"]}
        assert "single_reader" in designs
        assert "dual_reader" in designs

    @pytest.mark.anyio
    async def test_image_statuses_in_acquisitions(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/acquisitions")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "read_complete" in statuses
        assert "qc_passed" in statuses

    @pytest.mark.anyio
    async def test_qualification_statuses_in_readers(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/readers")
        data = resp.json()
        statuses = {item["qualification_status"] for item in data["items"]}
        assert "qualified" in statuses
        assert "in_training" in statuses
        assert "disqualified" in statuses

    @pytest.mark.anyio
    async def test_qc_outcomes_in_reviews(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qc-reviews")
        data = resp.json()
        outcomes = {item["outcome"] for item in data["items"]}
        assert "pass" in outcomes
        assert "fail" in outcomes
        assert "minor_deviation" in outcomes

    @pytest.mark.anyio
    async def test_overall_responses_in_assessments(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments")
        data = resp.json()
        responses = {
            item["overall_response"]
            for item in data["items"]
            if item["overall_response"] is not None
        }
        assert "partial_response" in responses


# =====================================================================
# CROSS-ENTITY CONSISTENCY
# =====================================================================


class TestCrossEntityConsistency:
    """Test relationships and consistency across entities."""

    def test_acquisitions_reference_valid_studies(self, svc: ImagingManagementService):
        acquisitions = svc.list_acquisitions()
        study_ids = {s.id for s in svc.list_studies()}
        for acq in acquisitions:
            assert acq.study_id in study_ids

    def test_assessments_reference_valid_acquisitions(self, svc: ImagingManagementService):
        assessments = svc.list_assessments()
        acq_ids = {a.id for a in svc.list_acquisitions()}
        for da in assessments:
            assert da.acquisition_id in acq_ids

    def test_assessments_reference_valid_readers(self, svc: ImagingManagementService):
        assessments = svc.list_assessments()
        reader_ids = {r.id for r in svc.list_readers()}
        for da in assessments:
            assert da.reader_id in reader_ids

    def test_qc_reviews_reference_valid_acquisitions(self, svc: ImagingManagementService):
        qc_reviews = svc.list_qc_reviews()
        acq_ids = {a.id for a in svc.list_acquisitions()}
        for qc in qc_reviews:
            assert qc.acquisition_id in acq_ids

    def test_eylea_study_has_oct_acquisitions(self, svc: ImagingManagementService):
        eylea_studies = svc.list_studies(trial_id=EYLEA_TRIAL)
        study_ids = {s.id for s in eylea_studies}
        oct_acqs = svc.list_acquisitions(modality=ImagingModality.OCT)
        eylea_oct = [a for a in oct_acqs if a.study_id in study_ids]
        assert len(eylea_oct) > 0

    def test_libtayo_study_has_ct_acquisitions(self, svc: ImagingManagementService):
        libtayo_studies = svc.list_studies(trial_id=LIBTAYO_TRIAL)
        study_ids = {s.id for s in libtayo_studies}
        ct_acqs = svc.list_acquisitions(modality=ImagingModality.CT)
        libtayo_ct = [a for a in ct_acqs if a.study_id in study_ids]
        assert len(libtayo_ct) > 0

    def test_dupixent_study_has_easi_assessments(self, svc: ImagingManagementService):
        easi_assessments = svc.list_assessments(criteria=AssessmentCriteria.EASI)
        assert len(easi_assessments) > 0

    def test_libtayo_study_has_recist_assessments(self, svc: ImagingManagementService):
        recist_assessments = svc.list_assessments(criteria=AssessmentCriteria.RECIST_1_1)
        assert len(recist_assessments) > 0

    def test_failed_qc_has_issues(self, svc: ImagingManagementService):
        qc_reviews = svc.list_qc_reviews(outcome=QCOutcome.FAIL)
        for qc in qc_reviews:
            assert len(qc.issues) > 0
            assert qc.protocol_compliant is False

    def test_passed_qc_is_compliant(self, svc: ImagingManagementService):
        qc_reviews = svc.list_qc_reviews(outcome=QCOutcome.PASS)
        for qc in qc_reviews:
            assert qc.protocol_compliant is True
            assert qc.resolution_adequate is True
            assert qc.coverage_adequate is True


# =====================================================================
# ADDITIONAL FILTER COMBINATIONS
# =====================================================================


class TestFilterCombinations:
    """Test various filter combinations."""

    @pytest.mark.anyio
    async def test_studies_filter_trial_and_modality(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/studies",
            params={"trial_id": LIBTAYO_TRIAL, "modality": "ct"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == LIBTAYO_TRIAL
            assert "ct" in item["modalities"]

    @pytest.mark.anyio
    async def test_acquisitions_filter_study_and_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/acquisitions",
            params={"study_id": "IMG-STUDY-005", "status": "read_complete"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["study_id"] == "IMG-STUDY-005"
            assert item["status"] == "read_complete"

    @pytest.mark.anyio
    async def test_readers_filter_status_and_modality(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/readers",
            params={"qualification_status": "qualified", "modality": "ct"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["qualification_status"] == "qualified"
            assert "ct" in item["qualified_modalities"]

    @pytest.mark.anyio
    async def test_assessments_filter_reader_and_criteria(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/assessments",
            params={"reader_id": "RDR-001", "criteria": "recist_1_1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["reader_id"] == "RDR-001"
            assert item["assessment_criteria"] == "recist_1_1"


# =====================================================================
# DATA DETAIL TESTS
# =====================================================================


class TestDataDetails:
    """Test detailed data characteristics."""

    @pytest.mark.anyio
    async def test_study_001_details(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/IMG-STUDY-001")
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert "oct" in data["modalities"]
        assert data["assessment_criteria"] == "etdrs"
        assert data["reading_design"] == "dual_reader"
        assert data["blinded"] is True

    @pytest.mark.anyio
    async def test_study_005_details(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/studies/IMG-STUDY-005")
        data = resp.json()
        assert data["trial_id"] == LIBTAYO_TRIAL
        assert "ct" in data["modalities"]
        assert "mri" in data["modalities"]
        assert data["assessment_criteria"] == "recist_1_1"

    @pytest.mark.anyio
    async def test_acquisition_001_has_oct_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/acquisitions/ACQ-001")
        data = resp.json()
        assert data["modality"] == "oct"
        assert data["file_count"] > 0
        assert data["total_size_mb"] > 0
        assert data["slice_thickness_mm"] is not None

    @pytest.mark.anyio
    async def test_acquisition_007_has_ct_contrast(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/acquisitions/ACQ-007")
        data = resp.json()
        assert data["modality"] == "ct"
        assert data["contrast_used"] is True
        assert data["slice_thickness_mm"] == 2.5

    @pytest.mark.anyio
    async def test_reader_003_retinal_specialist(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/readers/RDR-003")
        data = resp.json()
        assert data["specialty"] == "Retinal Imaging"
        assert "oct" in data["qualified_modalities"]
        assert "etdrs" in data["qualified_criteria"]
        assert data["agreement_rate"] > 95.0

    @pytest.mark.anyio
    async def test_assessment_004_recist_pr(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/assessments/DA-004")
        data = resp.json()
        assert data["overall_response"] == "partial_response"
        assert data["percent_change_from_baseline"] < 0
        assert data["target_lesion_count"] == 3

    @pytest.mark.anyio
    async def test_qc_009_failed_review(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qc-reviews/QC-009")
        data = resp.json()
        assert data["outcome"] == "fail"
        assert len(data["issues"]) == 2
        assert data["protocol_compliant"] is False
        assert data["resolution_adequate"] is False
        assert data["action_required"] is not None
