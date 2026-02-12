"""Tests for Digital Biomarkers Management (DIGI-BIO).

Covers:
- Seed data verification (endpoints, streams, algorithms, scores, qualifications)
- Digital Endpoint CRUD (create, read, update, delete, list, filter by trial_id)
- Data Stream CRUD (create, read, update, delete, list, filter by trial_id/endpoint_id)
- Algorithm Validation CRUD (create, read, update, delete, list, filter by endpoint_id)
- Digital Measure Score CRUD (create, read, update, delete, list, filter by trial_id/endpoint_id)
- Regulatory Qualification CRUD (create, read, update, delete, list, filter by endpoint_id)
- Metrics computation
- 404 error handling for all entities
- Validation errors
- Edge cases
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.digital_biomarkers import (
    AlgorithmStatus,
    AlgorithmValidationCreate,
    AlgorithmValidationUpdate,
    DataStreamCreate,
    DataStreamUpdate,
    DeviceType,
    DigitalEndpointCreate,
    DigitalEndpointUpdate,
    DigitalMeasureScoreCreate,
    DigitalMeasureScoreUpdate,
    EndpointQualification,
    RegulatoryQualificationCreate,
    RegulatoryQualificationUpdate,
    ScoringStatus,
    StreamStatus,
)
from app.services.digital_biomarkers_service import (
    DigitalBiomarkersService,
    get_digital_biomarkers_service,
    reset_digital_biomarkers_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/digital-biomarkers"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_digital_biomarkers_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> DigitalBiomarkersService:
    """Convenience alias for the fresh service."""
    return fresh_service


@pytest.fixture
def client():
    """Async test client."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test", follow_redirects=True)


# ===========================================================================
# SEED DATA VERIFICATION
# ===========================================================================


class TestSeedData:
    """Verify seed data is populated correctly."""

    def test_seed_endpoints_count(self, svc: DigitalBiomarkersService):
        assert len(svc._endpoints) >= 10

    def test_seed_streams_count(self, svc: DigitalBiomarkersService):
        assert len(svc._streams) >= 10

    def test_seed_algorithms_count(self, svc: DigitalBiomarkersService):
        assert len(svc._algorithms) >= 10

    def test_seed_scores_count(self, svc: DigitalBiomarkersService):
        assert len(svc._scores) >= 10

    def test_seed_qualifications_count(self, svc: DigitalBiomarkersService):
        assert len(svc._qualifications) >= 10

    def test_seed_endpoint_has_required_fields(self, svc: DigitalBiomarkersService):
        ep = svc.get_endpoint("DEP-001")
        assert ep is not None
        assert ep.trial_id == EYLEA_TRIAL
        assert ep.endpoint_name == "Daily Step Count"
        assert ep.device_type == DeviceType.ACCELEROMETER
        assert ep.unit == "steps/day"

    def test_seed_stream_has_required_fields(self, svc: DigitalBiomarkersService):
        stream = svc.get_stream("DST-001")
        assert stream is not None
        assert stream.endpoint_id == "DEP-001"
        assert stream.trial_id == EYLEA_TRIAL
        assert stream.status == StreamStatus.ACTIVE

    def test_seed_algorithm_has_required_fields(self, svc: DigitalBiomarkersService):
        algo = svc.get_algorithm("ALG-001")
        assert algo is not None
        assert algo.endpoint_id == "DEP-001"
        assert algo.algorithm_name == "StepDetect-CNN"
        assert algo.status == AlgorithmStatus.LOCKED

    def test_seed_score_has_required_fields(self, svc: DigitalBiomarkersService):
        score = svc.get_score("DMS-001")
        assert score is not None
        assert score.trial_id == EYLEA_TRIAL
        assert score.scoring_status == ScoringStatus.QC_PASSED

    def test_seed_qualification_has_required_fields(self, svc: DigitalBiomarkersService):
        qual = svc.get_qualification("RQU-001")
        assert qual is not None
        assert qual.endpoint_id == "DEP-003"
        assert qual.regulatory_authority == "FDA"

    def test_seed_endpoints_span_all_trials(self, svc: DigitalBiomarkersService):
        trials = {ep.trial_id for ep in svc._endpoints.values()}
        assert EYLEA_TRIAL in trials
        assert DUPIXENT_TRIAL in trials
        assert LIBTAYO_TRIAL in trials

    def test_seed_streams_have_various_statuses(self, svc: DigitalBiomarkersService):
        statuses = {s.status for s in svc._streams.values()}
        assert StreamStatus.ACTIVE in statuses
        assert StreamStatus.COMPLETED in statuses

    def test_seed_algorithms_have_various_statuses(self, svc: DigitalBiomarkersService):
        statuses = {a.status for a in svc._algorithms.values()}
        assert AlgorithmStatus.LOCKED in statuses
        assert AlgorithmStatus.DEVELOPMENT in statuses

    def test_seed_scores_have_various_statuses(self, svc: DigitalBiomarkersService):
        statuses = {s.scoring_status for s in svc._scores.values()}
        assert ScoringStatus.QC_PASSED in statuses
        assert ScoringStatus.QC_FAILED in statuses

    def test_seed_qualifications_have_various_statuses(self, svc: DigitalBiomarkersService):
        statuses = {q.status for q in svc._qualifications.values()}
        assert "planning" in statuses
        assert "qualified" in statuses


# ===========================================================================
# DIGITAL ENDPOINTS - API TESTS
# ===========================================================================


class TestEndpointsAPI:
    """Digital Endpoint REST API tests."""

    @pytest.mark.anyio
    async def test_list_endpoints(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/endpoints")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 10
        assert len(data["items"]) == data["total"]

    @pytest.mark.anyio
    async def test_list_endpoints_filter_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/endpoints", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_endpoints_filter_by_nonexistent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/endpoints", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_endpoint(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/endpoints/DEP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DEP-001"
        assert data["endpoint_name"] == "Daily Step Count"

    @pytest.mark.anyio
    async def test_get_endpoint_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/endpoints/NONEXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_endpoint(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "endpoint_name": "New Digital Endpoint",
            "description": "Test endpoint",
            "device_type": "accelerometer",
            "measure_type": "gait_analysis",
            "unit": "m/s",
            "collection_frequency": "continuous",
            "concept_of_interest": "Gait speed",
            "context_of_use": "Exploratory gait analysis",
            "created_by": "Test User",
        }
        resp = await client.post(f"{API_PREFIX}/endpoints", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["endpoint_name"] == "New Digital Endpoint"
        assert data["id"].startswith("DEP-")
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_create_endpoint_appears_in_list(self, client: AsyncClient):
        payload = {
            "trial_id": DUPIXENT_TRIAL,
            "endpoint_name": "Test Appears In List",
            "description": "For list test",
            "device_type": "smartwatch",
            "measure_type": "sleep",
            "unit": "hours",
            "collection_frequency": "nightly",
            "concept_of_interest": "Sleep duration",
            "context_of_use": "Test context",
            "created_by": "Tester",
        }
        create_resp = await client.post(f"{API_PREFIX}/endpoints", json=payload)
        new_id = create_resp.json()["id"]
        list_resp = await client.get(f"{API_PREFIX}/endpoints")
        ids = [item["id"] for item in list_resp.json()["items"]]
        assert new_id in ids

    @pytest.mark.anyio
    async def test_update_endpoint(self, client: AsyncClient):
        payload = {"qualification_level": "qualified", "test_retest_icc": 0.95}
        resp = await client.put(f"{API_PREFIX}/endpoints/DEP-001", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["qualification_level"] == "qualified"
        assert data["test_retest_icc"] == 0.95

    @pytest.mark.anyio
    async def test_update_endpoint_not_found(self, client: AsyncClient):
        payload = {"qualification_level": "qualified"}
        resp = await client.put(f"{API_PREFIX}/endpoints/NONEXIST", json=payload)
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_endpoint_partial(self, client: AsyncClient):
        payload = {"clinically_meaningful_change": 2000.0}
        resp = await client.put(f"{API_PREFIX}/endpoints/DEP-001", json=payload)
        assert resp.status_code == 200
        assert resp.json()["clinically_meaningful_change"] == 2000.0
        # Original fields unchanged
        assert resp.json()["endpoint_name"] == "Daily Step Count"

    @pytest.mark.anyio
    async def test_delete_endpoint(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/endpoints/DEP-001")
        assert resp.status_code == 204
        # Verify deletion
        resp2 = await client.get(f"{API_PREFIX}/endpoints/DEP-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_endpoint_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/endpoints/NONEXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_endpoint_invalid_device_type(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "endpoint_name": "Bad Device",
            "description": "Invalid",
            "device_type": "invalid_device",
            "measure_type": "test",
            "unit": "unit",
            "collection_frequency": "daily",
            "concept_of_interest": "Test",
            "context_of_use": "Test",
            "created_by": "Test",
        }
        resp = await client.post(f"{API_PREFIX}/endpoints", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_endpoint_missing_required_field(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            # missing endpoint_name
            "description": "Missing name",
            "device_type": "accelerometer",
            "measure_type": "test",
            "unit": "unit",
            "collection_frequency": "daily",
            "concept_of_interest": "Test",
            "context_of_use": "Test",
            "created_by": "Test",
        }
        resp = await client.post(f"{API_PREFIX}/endpoints", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_list_endpoints_dupixent_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/endpoints", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3

    @pytest.mark.anyio
    async def test_list_endpoints_libtayo_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/endpoints", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3

    @pytest.mark.anyio
    async def test_update_endpoint_regulatory_reference(self, client: AsyncClient):
        payload = {"regulatory_reference": "New Reference Doc 2025"}
        resp = await client.put(f"{API_PREFIX}/endpoints/DEP-002", json=payload)
        assert resp.status_code == 200
        assert resp.json()["regulatory_reference"] == "New Reference Doc 2025"

    @pytest.mark.anyio
    async def test_update_endpoint_sensitivity_to_change(self, client: AsyncClient):
        payload = {"sensitivity_to_change": 0.99}
        resp = await client.put(f"{API_PREFIX}/endpoints/DEP-003", json=payload)
        assert resp.status_code == 200
        assert resp.json()["sensitivity_to_change"] == 0.99


# ===========================================================================
# DATA STREAMS - API TESTS
# ===========================================================================


class TestStreamsAPI:
    """Data Stream REST API tests."""

    @pytest.mark.anyio
    async def test_list_streams(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/streams")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 10

    @pytest.mark.anyio
    async def test_list_streams_filter_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/streams", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_streams_filter_by_endpoint(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/streams", params={"endpoint_id": "DEP-001"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["endpoint_id"] == "DEP-001"

    @pytest.mark.anyio
    async def test_list_streams_filter_by_both(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/streams",
            params={"trial_id": DUPIXENT_TRIAL, "endpoint_id": "DEP-003"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL
            assert item["endpoint_id"] == "DEP-003"

    @pytest.mark.anyio
    async def test_list_streams_no_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/streams", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_stream(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/streams/DST-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DST-001"
        assert data["status"] == "active"

    @pytest.mark.anyio
    async def test_get_stream_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/streams/NONEXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_stream(self, client: AsyncClient):
        payload = {
            "endpoint_id": "DEP-001",
            "trial_id": EYLEA_TRIAL,
            "subject_id": "SUBJ-NEW-001",
            "device_type": "accelerometer",
            "device_serial": "NEW-SERIAL-001",
            "sampling_rate_hz": 50.0,
            "site_id": "SITE-999",
        }
        resp = await client.post(f"{API_PREFIX}/streams", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("DST-")
        assert data["subject_id"] == "SUBJ-NEW-001"
        assert data["status"] == "configured"

    @pytest.mark.anyio
    async def test_create_stream_minimal(self, client: AsyncClient):
        payload = {
            "endpoint_id": "DEP-002",
            "trial_id": EYLEA_TRIAL,
            "subject_id": "SUBJ-MIN-001",
            "device_type": "smartphone_sensor",
            "site_id": "SITE-100",
        }
        resp = await client.post(f"{API_PREFIX}/streams", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["device_serial"] is None
        assert data["sampling_rate_hz"] is None

    @pytest.mark.anyio
    async def test_update_stream(self, client: AsyncClient):
        payload = {
            "status": "completed",
            "total_data_points": 10000000,
            "compliance_pct": 95.5,
        }
        resp = await client.put(f"{API_PREFIX}/streams/DST-001", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["total_data_points"] == 10000000
        assert data["compliance_pct"] == 95.5

    @pytest.mark.anyio
    async def test_update_stream_not_found(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/streams/NONEXIST", json={"status": "active"})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_stream_partial(self, client: AsyncClient):
        payload = {"data_quality_score": 0.99}
        resp = await client.put(f"{API_PREFIX}/streams/DST-001", json=payload)
        assert resp.status_code == 200
        assert resp.json()["data_quality_score"] == 0.99

    @pytest.mark.anyio
    async def test_delete_stream(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/streams/DST-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/streams/DST-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_stream_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/streams/NONEXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_stream_invalid_device(self, client: AsyncClient):
        payload = {
            "endpoint_id": "DEP-001",
            "trial_id": EYLEA_TRIAL,
            "subject_id": "SUBJ-BAD",
            "device_type": "invalid",
            "site_id": "SITE-100",
        }
        resp = await client.post(f"{API_PREFIX}/streams", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_stream_wear_time(self, client: AsyncClient):
        payload = {"wear_time_hours": 2000.0}
        resp = await client.put(f"{API_PREFIX}/streams/DST-002", json=payload)
        assert resp.status_code == 200
        assert resp.json()["wear_time_hours"] == 2000.0

    @pytest.mark.anyio
    async def test_list_streams_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/streams", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2


# ===========================================================================
# ALGORITHM VALIDATIONS - API TESTS
# ===========================================================================


class TestAlgorithmsAPI:
    """Algorithm Validation REST API tests."""

    @pytest.mark.anyio
    async def test_list_algorithms(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/algorithms")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 10

    @pytest.mark.anyio
    async def test_list_algorithms_filter_by_endpoint(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/algorithms", params={"endpoint_id": "DEP-001"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["endpoint_id"] == "DEP-001"

    @pytest.mark.anyio
    async def test_list_algorithms_no_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/algorithms", params={"endpoint_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_algorithm(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/algorithms/ALG-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "ALG-001"
        assert data["algorithm_name"] == "StepDetect-CNN"

    @pytest.mark.anyio
    async def test_get_algorithm_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/algorithms/NONEXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_algorithm(self, client: AsyncClient):
        payload = {
            "endpoint_id": "DEP-001",
            "algorithm_name": "NewAlgo",
            "version": "0.1.0",
            "reference_method": "Gold standard method",
        }
        resp = await client.post(f"{API_PREFIX}/algorithms", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("ALG-")
        assert data["algorithm_name"] == "NewAlgo"
        assert data["status"] == "development"

    @pytest.mark.anyio
    async def test_create_algorithm_minimal(self, client: AsyncClient):
        payload = {
            "endpoint_id": "DEP-002",
            "algorithm_name": "MinimalAlgo",
            "version": "1.0.0",
        }
        resp = await client.post(f"{API_PREFIX}/algorithms", json=payload)
        assert resp.status_code == 201
        assert resp.json()["reference_method"] is None

    @pytest.mark.anyio
    async def test_update_algorithm(self, client: AsyncClient):
        payload = {
            "status": "clinical_validation",
            "accuracy": 0.99,
            "precision": 0.98,
            "recall": 0.97,
        }
        resp = await client.put(f"{API_PREFIX}/algorithms/ALG-009", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "clinical_validation"
        assert data["accuracy"] == 0.99

    @pytest.mark.anyio
    async def test_update_algorithm_not_found(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/algorithms/NONEXIST", json={"accuracy": 0.5})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_algorithm_lock(self, client: AsyncClient):
        # ALG-009 is in development, lock it
        payload = {"status": "locked", "validated_by": "Dr. Test"}
        resp = await client.put(f"{API_PREFIX}/algorithms/ALG-009", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "locked"
        assert data["locked_date"] is not None

    @pytest.mark.anyio
    async def test_update_algorithm_partial(self, client: AsyncClient):
        payload = {"f1_score": 0.975}
        resp = await client.put(f"{API_PREFIX}/algorithms/ALG-001", json=payload)
        assert resp.status_code == 200
        assert resp.json()["f1_score"] == 0.975

    @pytest.mark.anyio
    async def test_delete_algorithm(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/algorithms/ALG-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/algorithms/ALG-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_algorithm_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/algorithms/NONEXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_algorithm_missing_name(self, client: AsyncClient):
        payload = {
            "endpoint_id": "DEP-001",
            "version": "1.0.0",
        }
        resp = await client.post(f"{API_PREFIX}/algorithms", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_algorithm_training_samples(self, client: AsyncClient):
        payload = {"training_samples": 500000, "validation_samples": 125000}
        resp = await client.put(f"{API_PREFIX}/algorithms/ALG-002", json=payload)
        assert resp.status_code == 200
        assert resp.json()["training_samples"] == 500000

    @pytest.mark.anyio
    async def test_update_algorithm_auc_roc(self, client: AsyncClient):
        payload = {"auc_roc": 0.999}
        resp = await client.put(f"{API_PREFIX}/algorithms/ALG-003", json=payload)
        assert resp.status_code == 200
        assert resp.json()["auc_roc"] == 0.999


# ===========================================================================
# DIGITAL MEASURE SCORES - API TESTS
# ===========================================================================


class TestScoresAPI:
    """Digital Measure Score REST API tests."""

    @pytest.mark.anyio
    async def test_list_scores(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scores")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 10

    @pytest.mark.anyio
    async def test_list_scores_filter_by_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scores", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_scores_filter_by_endpoint(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scores", params={"endpoint_id": "DEP-001"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["endpoint_id"] == "DEP-001"

    @pytest.mark.anyio
    async def test_list_scores_filter_by_both(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/scores",
            params={"trial_id": DUPIXENT_TRIAL, "endpoint_id": "DEP-003"},
        )
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["trial_id"] == DUPIXENT_TRIAL
            assert item["endpoint_id"] == "DEP-003"

    @pytest.mark.anyio
    async def test_list_scores_no_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scores", params={"trial_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_score(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scores/DMS-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "DMS-001"
        assert data["scoring_status"] == "qc_passed"

    @pytest.mark.anyio
    async def test_get_score_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scores/NONEXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_score(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {
            "stream_id": "DST-001",
            "endpoint_id": "DEP-001",
            "subject_id": "SUBJ-E001",
            "trial_id": EYLEA_TRIAL,
            "algorithm_id": "ALG-001",
            "score_unit": "steps/day",
            "measurement_period_start": (now - timedelta(days=7)).isoformat(),
            "measurement_period_end": now.isoformat(),
            "score_value": 8500.0,
            "visit": "Week 12",
        }
        resp = await client.post(f"{API_PREFIX}/scores", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("DMS-")
        assert data["score_value"] == 8500.0
        assert data["scoring_status"] == "raw"

    @pytest.mark.anyio
    async def test_create_score_no_value(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {
            "stream_id": "DST-001",
            "endpoint_id": "DEP-001",
            "subject_id": "SUBJ-E001",
            "trial_id": EYLEA_TRIAL,
            "algorithm_id": "ALG-001",
            "score_unit": "steps/day",
            "measurement_period_start": (now - timedelta(days=7)).isoformat(),
            "measurement_period_end": now.isoformat(),
        }
        resp = await client.post(f"{API_PREFIX}/scores", json=payload)
        assert resp.status_code == 201
        assert resp.json()["score_value"] is None

    @pytest.mark.anyio
    async def test_update_score(self, client: AsyncClient):
        payload = {"scoring_status": "adjudicated", "score_value": 7500.0}
        resp = await client.put(f"{API_PREFIX}/scores/DMS-003", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["scoring_status"] == "adjudicated"
        assert data["score_value"] == 7500.0

    @pytest.mark.anyio
    async def test_update_score_not_found(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/scores/NONEXIST", json={"score_value": 1.0})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_score_qc_flag(self, client: AsyncClient):
        payload = {"qc_flag": "Manual review required", "scoring_status": "qc_failed"}
        resp = await client.put(f"{API_PREFIX}/scores/DMS-003", json=payload)
        assert resp.status_code == 200
        assert resp.json()["qc_flag"] == "Manual review required"

    @pytest.mark.anyio
    async def test_update_score_minimum_wear(self, client: AsyncClient):
        payload = {"minimum_wear_met": False}
        resp = await client.put(f"{API_PREFIX}/scores/DMS-001", json=payload)
        assert resp.status_code == 200
        assert resp.json()["minimum_wear_met"] is False

    @pytest.mark.anyio
    async def test_delete_score(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/scores/DMS-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/scores/DMS-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_score_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/scores/NONEXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_score_missing_required(self, client: AsyncClient):
        payload = {
            "stream_id": "DST-001",
            # missing other required fields
        }
        resp = await client.post(f"{API_PREFIX}/scores", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_list_scores_dupixent(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scores", params={"trial_id": DUPIXENT_TRIAL})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    @pytest.mark.anyio
    async def test_list_scores_libtayo(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scores", params={"trial_id": LIBTAYO_TRIAL})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    @pytest.mark.anyio
    async def test_update_score_scored_date_auto_set(self, client: AsyncClient):
        # DMS-003 has scoring_status SCORED but let's create a new raw one and move it
        now = datetime.now(timezone.utc)
        create_payload = {
            "stream_id": "DST-001",
            "endpoint_id": "DEP-001",
            "subject_id": "SUBJ-E001",
            "trial_id": EYLEA_TRIAL,
            "algorithm_id": "ALG-001",
            "score_unit": "steps/day",
            "measurement_period_start": (now - timedelta(days=7)).isoformat(),
            "measurement_period_end": now.isoformat(),
        }
        create_resp = await client.post(f"{API_PREFIX}/scores", json=create_payload)
        new_id = create_resp.json()["id"]
        assert create_resp.json()["scored_date"] is None

        update_payload = {"scoring_status": "qc_passed", "score_value": 9000.0}
        update_resp = await client.put(f"{API_PREFIX}/scores/{new_id}", json=update_payload)
        assert update_resp.status_code == 200
        assert update_resp.json()["scored_date"] is not None


# ===========================================================================
# REGULATORY QUALIFICATIONS - API TESTS
# ===========================================================================


class TestQualificationsAPI:
    """Regulatory Qualification REST API tests."""

    @pytest.mark.anyio
    async def test_list_qualifications(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qualifications")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 10

    @pytest.mark.anyio
    async def test_list_qualifications_filter_by_endpoint(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qualifications", params={"endpoint_id": "DEP-003"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["endpoint_id"] == "DEP-003"

    @pytest.mark.anyio
    async def test_list_qualifications_no_results(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qualifications", params={"endpoint_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_get_qualification(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qualifications/RQU-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RQU-001"
        assert data["regulatory_authority"] == "FDA"

    @pytest.mark.anyio
    async def test_get_qualification_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qualifications/NONEXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_qualification(self, client: AsyncClient):
        payload = {
            "endpoint_id": "DEP-001",
            "regulatory_authority": "PMDA",
            "qualification_type": "Biomarker Qualification",
            "context_of_use": "Exploratory endpoint for mobility in Japan",
            "responsible_person": "Dr. Tanaka",
            "evidence_package": ["Japan clinical data", "Translation report"],
        }
        resp = await client.post(f"{API_PREFIX}/qualifications", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("RQU-")
        assert data["regulatory_authority"] == "PMDA"
        assert data["status"] == "planning"

    @pytest.mark.anyio
    async def test_create_qualification_minimal(self, client: AsyncClient):
        payload = {
            "endpoint_id": "DEP-002",
            "regulatory_authority": "Health Canada",
            "qualification_type": "Scientific Advice",
            "context_of_use": "Test context",
            "responsible_person": "Dr. Smith",
        }
        resp = await client.post(f"{API_PREFIX}/qualifications", json=payload)
        assert resp.status_code == 201
        assert resp.json()["evidence_package"] == []

    @pytest.mark.anyio
    async def test_update_qualification(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        payload = {
            "status": "submitted",
            "submission_date": now.isoformat(),
        }
        resp = await client.put(f"{API_PREFIX}/qualifications/RQU-003", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "submitted"
        assert data["submission_date"] is not None

    @pytest.mark.anyio
    async def test_update_qualification_not_found(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/qualifications/NONEXIST", json={"status": "submitted"})
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_update_qualification_to_qualified(self, client: AsyncClient):
        payload = {"status": "qualified"}
        resp = await client.put(f"{API_PREFIX}/qualifications/RQU-001", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "qualified"
        assert data["qualification_date"] is not None

    @pytest.mark.anyio
    async def test_update_qualification_feedback(self, client: AsyncClient):
        payload = {"feedback": "Additional data requested for subpopulation analysis"}
        resp = await client.put(f"{API_PREFIX}/qualifications/RQU-004", json=payload)
        assert resp.status_code == 200
        assert "subpopulation" in resp.json()["feedback"]

    @pytest.mark.anyio
    async def test_delete_qualification(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/qualifications/RQU-001")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/qualifications/RQU-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_qualification_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/qualifications/NONEXIST")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_qualification_missing_required(self, client: AsyncClient):
        payload = {
            "endpoint_id": "DEP-001",
            # missing other required fields
        }
        resp = await client.post(f"{API_PREFIX}/qualifications", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_list_qualifications_dep003(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qualifications", params={"endpoint_id": "DEP-003"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    @pytest.mark.anyio
    async def test_list_qualifications_dep010(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qualifications", params={"endpoint_id": "DEP-010"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 2

    @pytest.mark.anyio
    async def test_create_and_get_qualification(self, client: AsyncClient):
        payload = {
            "endpoint_id": "DEP-005",
            "regulatory_authority": "TGA",
            "qualification_type": "Pre-submission",
            "context_of_use": "Australian regulatory pathway",
            "responsible_person": "Dr. Koala",
        }
        create_resp = await client.post(f"{API_PREFIX}/qualifications", json=payload)
        new_id = create_resp.json()["id"]

        get_resp = await client.get(f"{API_PREFIX}/qualifications/{new_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["regulatory_authority"] == "TGA"


# ===========================================================================
# METRICS - API TESTS
# ===========================================================================


class TestMetricsAPI:
    """Digital Biomarker Metrics REST API tests."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_endpoints"] >= 10
        assert data["total_streams"] >= 10
        assert data["total_algorithms"] >= 10
        assert data["total_scores"] >= 10
        assert data["total_qualifications"] >= 10

    @pytest.mark.anyio
    async def test_metrics_endpoints_by_device(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert len(data["endpoints_by_device"]) >= 3

    @pytest.mark.anyio
    async def test_metrics_endpoints_by_qualification(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert len(data["endpoints_by_qualification"]) >= 2

    @pytest.mark.anyio
    async def test_metrics_streams_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "active" in data["streams_by_status"]

    @pytest.mark.anyio
    async def test_metrics_avg_compliance(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0 <= data["avg_compliance_pct"] <= 100

    @pytest.mark.anyio
    async def test_metrics_algorithms_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "locked" in data["algorithms_by_status"]

    @pytest.mark.anyio
    async def test_metrics_locked_algorithms(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["locked_algorithms"] >= 4

    @pytest.mark.anyio
    async def test_metrics_scores_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "qc_passed" in data["scores_by_status"]

    @pytest.mark.anyio
    async def test_metrics_qc_pass_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0 <= data["qc_pass_rate_pct"] <= 100

    @pytest.mark.anyio
    async def test_metrics_qualifications_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert "planning" in data["qualifications_by_status"]

    @pytest.mark.anyio
    async def test_metrics_after_creating_endpoint(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        before_count = resp1.json()["total_endpoints"]

        payload = {
            "trial_id": EYLEA_TRIAL,
            "endpoint_name": "Metrics Test",
            "description": "For metrics",
            "device_type": "spirometer",
            "measure_type": "lung_function",
            "unit": "liters",
            "collection_frequency": "daily",
            "concept_of_interest": "FEV1",
            "context_of_use": "Test",
            "created_by": "Tester",
        }
        await client.post(f"{API_PREFIX}/endpoints", json=payload)

        resp2 = await client.get(f"{API_PREFIX}/metrics")
        assert resp2.json()["total_endpoints"] == before_count + 1

    @pytest.mark.anyio
    async def test_metrics_after_deleting_stream(self, client: AsyncClient):
        resp1 = await client.get(f"{API_PREFIX}/metrics")
        before_count = resp1.json()["total_streams"]

        await client.delete(f"{API_PREFIX}/streams/DST-001")

        resp2 = await client.get(f"{API_PREFIX}/metrics")
        assert resp2.json()["total_streams"] == before_count - 1


# ===========================================================================
# SERVICE UNIT TESTS
# ===========================================================================


class TestServiceUnit:
    """Direct service method tests."""

    def test_create_endpoint_returns_id(self, svc: DigitalBiomarkersService):
        ep = svc.create_endpoint(DigitalEndpointCreate(
            trial_id=EYLEA_TRIAL,
            endpoint_name="Unit Test Endpoint",
            description="Unit test",
            device_type=DeviceType.CGM,
            measure_type="glucose",
            unit="mg/dL",
            collection_frequency="every_5_min",
            concept_of_interest="Glycemic control",
            context_of_use="Test",
            created_by="Unit Tester",
        ))
        assert ep.id.startswith("DEP-")
        assert ep.endpoint_name == "Unit Test Endpoint"

    def test_get_nonexistent_endpoint(self, svc: DigitalBiomarkersService):
        assert svc.get_endpoint("NONEXIST") is None

    def test_delete_nonexistent_endpoint(self, svc: DigitalBiomarkersService):
        assert svc.delete_endpoint("NONEXIST") is False

    def test_create_stream_returns_configured(self, svc: DigitalBiomarkersService):
        stream = svc.create_stream(DataStreamCreate(
            endpoint_id="DEP-001",
            trial_id=EYLEA_TRIAL,
            subject_id="SUBJ-UNIT",
            device_type=DeviceType.ACCELEROMETER,
            site_id="SITE-UNIT",
        ))
        assert stream.status == StreamStatus.CONFIGURED

    def test_get_nonexistent_stream(self, svc: DigitalBiomarkersService):
        assert svc.get_stream("NONEXIST") is None

    def test_delete_nonexistent_stream(self, svc: DigitalBiomarkersService):
        assert svc.delete_stream("NONEXIST") is False

    def test_create_algorithm_returns_development(self, svc: DigitalBiomarkersService):
        algo = svc.create_algorithm(AlgorithmValidationCreate(
            endpoint_id="DEP-001",
            algorithm_name="UnitTestAlgo",
            version="0.0.1",
        ))
        assert algo.status == AlgorithmStatus.DEVELOPMENT

    def test_get_nonexistent_algorithm(self, svc: DigitalBiomarkersService):
        assert svc.get_algorithm("NONEXIST") is None

    def test_delete_nonexistent_algorithm(self, svc: DigitalBiomarkersService):
        assert svc.delete_algorithm("NONEXIST") is False

    def test_create_score_returns_raw(self, svc: DigitalBiomarkersService):
        now = datetime.now(timezone.utc)
        score = svc.create_score(DigitalMeasureScoreCreate(
            stream_id="DST-001",
            endpoint_id="DEP-001",
            subject_id="SUBJ-E001",
            trial_id=EYLEA_TRIAL,
            algorithm_id="ALG-001",
            score_unit="steps/day",
            measurement_period_start=now - timedelta(days=7),
            measurement_period_end=now,
        ))
        assert score.scoring_status == ScoringStatus.RAW

    def test_get_nonexistent_score(self, svc: DigitalBiomarkersService):
        assert svc.get_score("NONEXIST") is None

    def test_delete_nonexistent_score(self, svc: DigitalBiomarkersService):
        assert svc.delete_score("NONEXIST") is False

    def test_create_qualification_returns_planning(self, svc: DigitalBiomarkersService):
        qual = svc.create_qualification(RegulatoryQualificationCreate(
            endpoint_id="DEP-001",
            regulatory_authority="MHRA",
            qualification_type="Scientific Advice",
            context_of_use="UK pathway",
            responsible_person="Dr. Test",
        ))
        assert qual.status == "planning"

    def test_get_nonexistent_qualification(self, svc: DigitalBiomarkersService):
        assert svc.get_qualification("NONEXIST") is None

    def test_delete_nonexistent_qualification(self, svc: DigitalBiomarkersService):
        assert svc.delete_qualification("NONEXIST") is False

    def test_update_nonexistent_endpoint(self, svc: DigitalBiomarkersService):
        result = svc.update_endpoint("NONEXIST", DigitalEndpointUpdate(test_retest_icc=0.5))
        assert result is None

    def test_update_nonexistent_stream(self, svc: DigitalBiomarkersService):
        result = svc.update_stream("NONEXIST", DataStreamUpdate(status=StreamStatus.ACTIVE))
        assert result is None

    def test_update_nonexistent_algorithm(self, svc: DigitalBiomarkersService):
        result = svc.update_algorithm("NONEXIST", AlgorithmValidationUpdate(accuracy=0.5))
        assert result is None

    def test_update_nonexistent_score(self, svc: DigitalBiomarkersService):
        result = svc.update_score("NONEXIST", DigitalMeasureScoreUpdate(score_value=1.0))
        assert result is None

    def test_update_nonexistent_qualification(self, svc: DigitalBiomarkersService):
        result = svc.update_qualification("NONEXIST", RegulatoryQualificationUpdate(status="submitted"))
        assert result is None

    def test_list_endpoints_all(self, svc: DigitalBiomarkersService):
        eps = svc.list_endpoints()
        assert len(eps) >= 10

    def test_list_endpoints_by_trial(self, svc: DigitalBiomarkersService):
        eps = svc.list_endpoints(trial_id=EYLEA_TRIAL)
        assert all(e.trial_id == EYLEA_TRIAL for e in eps)

    def test_list_streams_all(self, svc: DigitalBiomarkersService):
        streams = svc.list_streams()
        assert len(streams) >= 10

    def test_list_streams_by_trial(self, svc: DigitalBiomarkersService):
        streams = svc.list_streams(trial_id=DUPIXENT_TRIAL)
        assert all(s.trial_id == DUPIXENT_TRIAL for s in streams)

    def test_list_streams_by_endpoint(self, svc: DigitalBiomarkersService):
        streams = svc.list_streams(endpoint_id="DEP-003")
        assert all(s.endpoint_id == "DEP-003" for s in streams)

    def test_list_algorithms_all(self, svc: DigitalBiomarkersService):
        algos = svc.list_algorithms()
        assert len(algos) >= 10

    def test_list_algorithms_by_endpoint(self, svc: DigitalBiomarkersService):
        algos = svc.list_algorithms(endpoint_id="DEP-001")
        assert all(a.endpoint_id == "DEP-001" for a in algos)

    def test_list_scores_all(self, svc: DigitalBiomarkersService):
        scores = svc.list_scores()
        assert len(scores) >= 10

    def test_list_scores_by_trial(self, svc: DigitalBiomarkersService):
        scores = svc.list_scores(trial_id=LIBTAYO_TRIAL)
        assert all(s.trial_id == LIBTAYO_TRIAL for s in scores)

    def test_list_scores_by_endpoint(self, svc: DigitalBiomarkersService):
        scores = svc.list_scores(endpoint_id="DEP-001")
        assert all(s.endpoint_id == "DEP-001" for s in scores)

    def test_list_qualifications_all(self, svc: DigitalBiomarkersService):
        quals = svc.list_qualifications()
        assert len(quals) >= 10

    def test_list_qualifications_by_endpoint(self, svc: DigitalBiomarkersService):
        quals = svc.list_qualifications(endpoint_id="DEP-003")
        assert all(q.endpoint_id == "DEP-003" for q in quals)

    def test_metrics_computation(self, svc: DigitalBiomarkersService):
        metrics = svc.get_metrics()
        assert metrics.total_endpoints >= 10
        assert metrics.total_streams >= 10
        assert metrics.total_algorithms >= 10
        assert metrics.total_scores >= 10
        assert metrics.total_qualifications >= 10
        assert metrics.locked_algorithms >= 4
        assert 0 <= metrics.avg_compliance_pct <= 100
        assert 0 <= metrics.qc_pass_rate_pct <= 100


# ===========================================================================
# ENDPOINT CRUD LIFECYCLE
# ===========================================================================


class TestEndpointLifecycle:
    """Full lifecycle tests for endpoints."""

    @pytest.mark.anyio
    async def test_create_update_delete_endpoint(self, client: AsyncClient):
        # Create
        payload = {
            "trial_id": LIBTAYO_TRIAL,
            "endpoint_name": "Lifecycle Test",
            "description": "Full lifecycle",
            "device_type": "ecg_patch",
            "measure_type": "cardiac",
            "unit": "bpm",
            "collection_frequency": "continuous",
            "concept_of_interest": "Heart rate",
            "context_of_use": "Lifecycle test",
            "created_by": "Lifecycle Tester",
        }
        create_resp = await client.post(f"{API_PREFIX}/endpoints", json=payload)
        assert create_resp.status_code == 201
        ep_id = create_resp.json()["id"]

        # Read
        get_resp = await client.get(f"{API_PREFIX}/endpoints/{ep_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["endpoint_name"] == "Lifecycle Test"

        # Update
        update_resp = await client.put(
            f"{API_PREFIX}/endpoints/{ep_id}",
            json={"qualification_level": "regulatory_accepted", "test_retest_icc": 0.97},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["qualification_level"] == "regulatory_accepted"

        # Delete
        del_resp = await client.delete(f"{API_PREFIX}/endpoints/{ep_id}")
        assert del_resp.status_code == 204

        # Verify deleted
        verify_resp = await client.get(f"{API_PREFIX}/endpoints/{ep_id}")
        assert verify_resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_multiple_endpoints_same_trial(self, client: AsyncClient):
        for i in range(3):
            payload = {
                "trial_id": EYLEA_TRIAL,
                "endpoint_name": f"Multi Endpoint {i}",
                "description": f"Multi test {i}",
                "device_type": "accelerometer",
                "measure_type": "activity",
                "unit": "steps",
                "collection_frequency": "daily",
                "concept_of_interest": "Activity",
                "context_of_use": "Multi test",
                "created_by": "Tester",
            }
            resp = await client.post(f"{API_PREFIX}/endpoints", json=payload)
            assert resp.status_code == 201

        resp = await client.get(f"{API_PREFIX}/endpoints", params={"trial_id": EYLEA_TRIAL})
        # Original seed + 3 new
        assert resp.json()["total"] >= 6


class TestStreamLifecycle:
    """Full lifecycle tests for streams."""

    @pytest.mark.anyio
    async def test_create_update_delete_stream(self, client: AsyncClient):
        # Create
        payload = {
            "endpoint_id": "DEP-001",
            "trial_id": EYLEA_TRIAL,
            "subject_id": "SUBJ-LIFECYCLE",
            "device_type": "accelerometer",
            "device_serial": "LIFE-001",
            "sampling_rate_hz": 100.0,
            "site_id": "SITE-LIFE",
        }
        create_resp = await client.post(f"{API_PREFIX}/streams", json=payload)
        assert create_resp.status_code == 201
        stream_id = create_resp.json()["id"]

        # Update to active
        update_resp = await client.put(
            f"{API_PREFIX}/streams/{stream_id}",
            json={"status": "active", "total_data_points": 50000},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["status"] == "active"

        # Delete
        del_resp = await client.delete(f"{API_PREFIX}/streams/{stream_id}")
        assert del_resp.status_code == 204


class TestAlgorithmLifecycle:
    """Full lifecycle tests for algorithms."""

    @pytest.mark.anyio
    async def test_create_validate_lock_algorithm(self, client: AsyncClient):
        # Create
        create_resp = await client.post(f"{API_PREFIX}/algorithms", json={
            "endpoint_id": "DEP-001",
            "algorithm_name": "LifecycleAlgo",
            "version": "1.0.0",
            "reference_method": "Gold standard",
        })
        assert create_resp.status_code == 201
        algo_id = create_resp.json()["id"]
        assert create_resp.json()["status"] == "development"

        # Move to analytical validation
        resp2 = await client.put(f"{API_PREFIX}/algorithms/{algo_id}", json={
            "status": "analytical_validation",
            "accuracy": 0.92,
        })
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "analytical_validation"

        # Move to clinical validation
        resp3 = await client.put(f"{API_PREFIX}/algorithms/{algo_id}", json={
            "status": "clinical_validation",
            "validated_by": "Dr. Validator",
        })
        assert resp3.status_code == 200
        assert resp3.json()["validation_date"] is not None

        # Lock
        resp4 = await client.put(f"{API_PREFIX}/algorithms/{algo_id}", json={
            "status": "locked",
        })
        assert resp4.status_code == 200
        assert resp4.json()["locked_date"] is not None

        # Delete
        del_resp = await client.delete(f"{API_PREFIX}/algorithms/{algo_id}")
        assert del_resp.status_code == 204


class TestScoreLifecycle:
    """Full lifecycle tests for scores."""

    @pytest.mark.anyio
    async def test_create_score_and_advance_status(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        create_resp = await client.post(f"{API_PREFIX}/scores", json={
            "stream_id": "DST-001",
            "endpoint_id": "DEP-001",
            "subject_id": "SUBJ-E001",
            "trial_id": EYLEA_TRIAL,
            "algorithm_id": "ALG-001",
            "score_unit": "steps/day",
            "measurement_period_start": (now - timedelta(days=7)).isoformat(),
            "measurement_period_end": now.isoformat(),
            "score_value": 6000.0,
        })
        assert create_resp.status_code == 201
        score_id = create_resp.json()["id"]
        assert create_resp.json()["scoring_status"] == "raw"

        # Preprocess
        resp2 = await client.put(f"{API_PREFIX}/scores/{score_id}", json={
            "scoring_status": "preprocessed",
        })
        assert resp2.json()["scoring_status"] == "preprocessed"

        # Score
        resp3 = await client.put(f"{API_PREFIX}/scores/{score_id}", json={
            "scoring_status": "scored",
        })
        assert resp3.json()["scoring_status"] == "scored"
        assert resp3.json()["scored_date"] is not None

        # QC pass
        resp4 = await client.put(f"{API_PREFIX}/scores/{score_id}", json={
            "scoring_status": "qc_passed",
        })
        assert resp4.json()["scoring_status"] == "qc_passed"


class TestQualificationLifecycle:
    """Full lifecycle tests for qualifications."""

    @pytest.mark.anyio
    async def test_qualification_planning_to_qualified(self, client: AsyncClient):
        # Create
        create_resp = await client.post(f"{API_PREFIX}/qualifications", json={
            "endpoint_id": "DEP-001",
            "regulatory_authority": "ANVISA",
            "qualification_type": "Biomarker Qualification",
            "context_of_use": "Brazil regulatory pathway",
            "responsible_person": "Dr. Silva",
        })
        assert create_resp.status_code == 201
        qual_id = create_resp.json()["id"]
        assert create_resp.json()["status"] == "planning"

        # Submit
        now = datetime.now(timezone.utc)
        resp2 = await client.put(f"{API_PREFIX}/qualifications/{qual_id}", json={
            "status": "submitted",
            "submission_date": now.isoformat(),
        })
        assert resp2.json()["status"] == "submitted"

        # Under review
        resp3 = await client.put(f"{API_PREFIX}/qualifications/{qual_id}", json={
            "status": "under_review",
            "feedback": "Under active review",
        })
        assert resp3.json()["status"] == "under_review"

        # Qualified
        resp4 = await client.put(f"{API_PREFIX}/qualifications/{qual_id}", json={
            "status": "qualified",
        })
        assert resp4.json()["status"] == "qualified"
        assert resp4.json()["qualification_date"] is not None


# ===========================================================================
# SINGLETON & RESET TESTS
# ===========================================================================


class TestSingleton:
    """Singleton pattern tests."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_digital_biomarkers_service()
        svc2 = get_digital_biomarkers_service()
        assert svc1 is svc2

    def test_reset_service_returns_new_instance(self):
        svc1 = get_digital_biomarkers_service()
        svc2 = reset_digital_biomarkers_service()
        assert svc1 is not svc2

    def test_reset_service_repopulates_data(self):
        svc = get_digital_biomarkers_service()
        # Delete everything
        for ep_id in list(svc._endpoints.keys()):
            svc.delete_endpoint(ep_id)
        assert len(svc._endpoints) == 0

        # Reset
        new_svc = reset_digital_biomarkers_service()
        assert len(new_svc._endpoints) >= 10


# ===========================================================================
# EDGE CASES & ADDITIONAL COVERAGE
# ===========================================================================


class TestEdgeCases:
    """Edge case and boundary tests."""

    @pytest.mark.anyio
    async def test_empty_update_endpoint(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/endpoints/DEP-001", json={})
        assert resp.status_code == 200
        assert resp.json()["id"] == "DEP-001"

    @pytest.mark.anyio
    async def test_empty_update_stream(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/streams/DST-001", json={})
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_empty_update_algorithm(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/algorithms/ALG-001", json={})
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_empty_update_score(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/scores/DMS-001", json={})
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_empty_update_qualification(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/qualifications/RQU-001", json={})
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_get_each_seeded_endpoint(self, client: AsyncClient):
        for i in range(1, 12):
            dep_id = f"DEP-{i:03d}"
            resp = await client.get(f"{API_PREFIX}/endpoints/{dep_id}")
            assert resp.status_code == 200, f"Failed to get {dep_id}"

    @pytest.mark.anyio
    async def test_get_each_seeded_stream(self, client: AsyncClient):
        for i in range(1, 12):
            dst_id = f"DST-{i:03d}"
            resp = await client.get(f"{API_PREFIX}/streams/{dst_id}")
            assert resp.status_code == 200, f"Failed to get {dst_id}"

    @pytest.mark.anyio
    async def test_get_each_seeded_algorithm(self, client: AsyncClient):
        for i in range(1, 12):
            alg_id = f"ALG-{i:03d}"
            resp = await client.get(f"{API_PREFIX}/algorithms/{alg_id}")
            assert resp.status_code == 200, f"Failed to get {alg_id}"

    @pytest.mark.anyio
    async def test_get_each_seeded_score(self, client: AsyncClient):
        for i in range(1, 12):
            dms_id = f"DMS-{i:03d}"
            resp = await client.get(f"{API_PREFIX}/scores/{dms_id}")
            assert resp.status_code == 200, f"Failed to get {dms_id}"

    @pytest.mark.anyio
    async def test_get_each_seeded_qualification(self, client: AsyncClient):
        for i in range(1, 11):
            rqu_id = f"RQU-{i:03d}"
            resp = await client.get(f"{API_PREFIX}/qualifications/{rqu_id}")
            assert resp.status_code == 200, f"Failed to get {rqu_id}"

    @pytest.mark.anyio
    async def test_delete_all_endpoints_and_verify_metrics(self, client: AsyncClient):
        # Get all endpoints
        resp = await client.get(f"{API_PREFIX}/endpoints")
        for item in resp.json()["items"]:
            await client.delete(f"{API_PREFIX}/endpoints/{item['id']}")

        metrics = await client.get(f"{API_PREFIX}/metrics")
        assert metrics.json()["total_endpoints"] == 0

    @pytest.mark.anyio
    async def test_create_endpoint_all_device_types(self, client: AsyncClient):
        for dt in DeviceType:
            payload = {
                "trial_id": EYLEA_TRIAL,
                "endpoint_name": f"Device {dt.value}",
                "description": f"Test {dt.value}",
                "device_type": dt.value,
                "measure_type": "test",
                "unit": "unit",
                "collection_frequency": "daily",
                "concept_of_interest": "Test",
                "context_of_use": "Test",
                "created_by": "Tester",
            }
            resp = await client.post(f"{API_PREFIX}/endpoints", json=payload)
            assert resp.status_code == 201, f"Failed for device type {dt.value}"

    @pytest.mark.anyio
    async def test_update_endpoint_all_qualification_levels(self, client: AsyncClient):
        for ql in EndpointQualification:
            payload = {"qualification_level": ql.value}
            resp = await client.put(f"{API_PREFIX}/endpoints/DEP-001", json=payload)
            assert resp.status_code == 200
            assert resp.json()["qualification_level"] == ql.value

    @pytest.mark.anyio
    async def test_update_stream_all_statuses(self, client: AsyncClient):
        for st in StreamStatus:
            payload = {"status": st.value}
            resp = await client.put(f"{API_PREFIX}/streams/DST-001", json=payload)
            assert resp.status_code == 200
            assert resp.json()["status"] == st.value

    @pytest.mark.anyio
    async def test_update_algorithm_all_statuses(self, client: AsyncClient):
        # Use a development algo
        for st in AlgorithmStatus:
            payload = {"status": st.value}
            resp = await client.put(f"{API_PREFIX}/algorithms/ALG-009", json=payload)
            assert resp.status_code == 200
            assert resp.json()["status"] == st.value

    @pytest.mark.anyio
    async def test_update_score_all_statuses(self, client: AsyncClient):
        now = datetime.now(timezone.utc)
        create_resp = await client.post(f"{API_PREFIX}/scores", json={
            "stream_id": "DST-001",
            "endpoint_id": "DEP-001",
            "subject_id": "SUBJ-E001",
            "trial_id": EYLEA_TRIAL,
            "algorithm_id": "ALG-001",
            "score_unit": "steps/day",
            "measurement_period_start": (now - timedelta(days=7)).isoformat(),
            "measurement_period_end": now.isoformat(),
        })
        score_id = create_resp.json()["id"]

        for ss in ScoringStatus:
            payload = {"scoring_status": ss.value}
            resp = await client.put(f"{API_PREFIX}/scores/{score_id}", json=payload)
            assert resp.status_code == 200
            assert resp.json()["scoring_status"] == ss.value

    @pytest.mark.anyio
    async def test_stream_completed_has_end_date_in_seed(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/streams/DST-009")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert resp.json()["end_date"] is not None

    @pytest.mark.anyio
    async def test_stream_error_has_low_compliance(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/streams/DST-010")
        assert resp.status_code == 200
        assert resp.json()["status"] == "error"
        assert resp.json()["compliance_pct"] < 50

    @pytest.mark.anyio
    async def test_score_qc_failed_has_flag(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scores/DMS-010")
        assert resp.status_code == 200
        assert resp.json()["scoring_status"] == "qc_failed"
        assert resp.json()["qc_flag"] is not None

    @pytest.mark.anyio
    async def test_score_qc_failed_minimum_wear_not_met(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scores/DMS-010")
        assert resp.json()["minimum_wear_met"] is False

    @pytest.mark.anyio
    async def test_qualification_qualified_has_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qualifications/RQU-002")
        assert resp.json()["status"] == "qualified"
        assert resp.json()["qualification_date"] is not None

    @pytest.mark.anyio
    async def test_qualification_planning_no_submission_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/qualifications/RQU-003")
        assert resp.json()["status"] == "planning"
        assert resp.json()["submission_date"] is None

    @pytest.mark.anyio
    async def test_endpoint_ecg_regulatory_accepted(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/endpoints/DEP-010")
        assert resp.json()["qualification_level"] == "regulatory_accepted"
        assert resp.json()["device_type"] == "ecg_patch"

    @pytest.mark.anyio
    async def test_algorithm_locked_has_locked_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/algorithms/ALG-001")
        assert resp.json()["status"] == "locked"
        assert resp.json()["locked_date"] is not None

    @pytest.mark.anyio
    async def test_algorithm_development_no_locked_date(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/algorithms/ALG-009")
        assert resp.json()["status"] == "development"
        assert resp.json()["locked_date"] is None

    @pytest.mark.anyio
    async def test_score_adjudicated_has_qc_flag(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/scores/DMS-011")
        assert resp.json()["scoring_status"] == "adjudicated"
        assert resp.json()["qc_flag"] is not None

    @pytest.mark.anyio
    async def test_metrics_device_type_counts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_device = sum(data["endpoints_by_device"].values())
        assert total_by_device == data["total_endpoints"]

    @pytest.mark.anyio
    async def test_metrics_qualification_counts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_qual = sum(data["endpoints_by_qualification"].values())
        assert total_by_qual == data["total_endpoints"]

    @pytest.mark.anyio
    async def test_metrics_stream_status_counts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_status = sum(data["streams_by_status"].values())
        assert total_by_status == data["total_streams"]

    @pytest.mark.anyio
    async def test_metrics_algo_status_counts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_status = sum(data["algorithms_by_status"].values())
        assert total_by_status == data["total_algorithms"]

    @pytest.mark.anyio
    async def test_metrics_score_status_counts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_status = sum(data["scores_by_status"].values())
        assert total_by_status == data["total_scores"]

    @pytest.mark.anyio
    async def test_metrics_qualification_status_counts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        total_by_status = sum(data["qualifications_by_status"].values())
        assert total_by_status == data["total_qualifications"]
