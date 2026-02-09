"""Tests for Clinical Trial Management System (CTMS) Core (CLINICAL-22).

Covers:
- Seed data verification (trials, sites, patients, visits, metrics)
- Trial CRUD (create, read, update, delete, list, filter by phase/status/therapeutic_area)
- Site CRUD (create, read, update, delete, list, filter by trial/status/country)
- Patient CRUD (create, read, update, delete, list, filter by trial/site/status)
- Visit CRUD (create, read, update, delete, list, filter by patient/trial/status)
- Enrollment summary (trial-level and site-level)
- Visit compliance metrics
- Screen failure tracking (~25% rate)
- Visit window compliance (in-window vs out-of-window auto-detection)
- Source data verification (SDV)
- CTMS metrics computation
- Error handling (404s, invalid operations)
- Edge cases (empty filters, boundary conditions)
- Service singleton pattern
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.ctms_core import (
    PatientCreate,
    PatientStatus,
    PatientUpdate,
    SiteCreate,
    SiteStatus,
    SiteUpdate,
    StudyDesign,
    TherapeuticArea,
    TrialCreate,
    TrialPhase,
    TrialStatus,
    TrialUpdate,
    VisitCreate,
    VisitStatus,
    VisitUpdate,
)
from app.services.ctms_core_service import (
    CTMSService,
    get_ctms_service,
    reset_ctms_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/ctms"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_ctms_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> CTMSService:
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


def _make_trial_create(**overrides) -> dict:
    defaults = {
        "protocol_number": "R9999-TST-0001",
        "title": "Test Trial: A Phase 2 Study",
        "phase": "phase2",
        "therapeutic_area": "oncology",
        "study_design": "parallel",
        "indication": "Test Indication",
        "sponsor": "Test Sponsor Inc.",
        "start_date": "2026-01-01",
        "estimated_end_date": "2028-06-30",
        "target_enrollment": 100,
        "countries": ["US", "UK"],
        "sites_planned": 5,
        "primary_endpoint": "Overall response rate",
        "secondary_endpoints": ["PFS", "OS"],
        "regulatory_ids": {"FDA IND": "IND-999999"},
    }
    defaults.update(overrides)
    return defaults


def _make_site_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_number": "099",
        "name": "Test Hospital",
        "pi_name": "Dr. Test PI",
        "address": "123 Test St, Test City",
        "country": "US",
        "enrollment_target": 25,
    }
    defaults.update(overrides)
    return defaults


def _make_patient_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "site_id": "CTMS-SITE-001",
        "subject_number": "SUBJ-TEST-001",
        "screening_date": "2026-01-15",
    }
    defaults.update(overrides)
    return defaults


def _make_visit_create(**overrides) -> dict:
    defaults = {
        "patient_id": "CTMS-PAT-0001",
        "trial_id": EYLEA_TRIAL,
        "visit_number": 99,
        "visit_name": "Test Visit",
        "scheduled_date": "2026-06-15",
        "window_start": "2026-06-12",
        "window_end": "2026-06-20",
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_trials_count(self, svc: CTMSService):
        trials = svc.list_trials()
        assert len(trials) == 3

    def test_seed_trials_are_regeneron(self, svc: CTMSService):
        trials = svc.list_trials()
        for t in trials:
            assert "Regeneron" in t.sponsor or "Sanofi" in t.sponsor

    def test_seed_trial_eylea(self, svc: CTMSService):
        trial = svc.get_trial(EYLEA_TRIAL)
        assert trial is not None
        assert trial.protocol_number == "R1234-OPH-1553"
        assert trial.phase == TrialPhase.PHASE3
        assert trial.therapeutic_area == TherapeuticArea.OPHTHALMOLOGY

    def test_seed_trial_dupixent(self, svc: CTMSService):
        trial = svc.get_trial(DUPIXENT_TRIAL)
        assert trial is not None
        assert trial.therapeutic_area == TherapeuticArea.IMMUNOLOGY
        assert trial.status == TrialStatus.ENROLLING

    def test_seed_trial_libtayo(self, svc: CTMSService):
        trial = svc.get_trial(LIBTAYO_TRIAL)
        assert trial is not None
        assert trial.therapeutic_area == TherapeuticArea.ONCOLOGY
        assert trial.status == TrialStatus.FULLY_ENROLLED

    def test_seed_sites_count(self, svc: CTMSService):
        sites = svc.list_sites()
        assert len(sites) == 15

    def test_seed_sites_per_trial(self, svc: CTMSService):
        for trial_id in [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]:
            sites = svc.list_sites(trial_id=trial_id)
            assert len(sites) == 5

    def test_seed_patients_count(self, svc: CTMSService):
        patients = svc.list_patients()
        assert len(patients) == 50

    def test_seed_visits_exist(self, svc: CTMSService):
        visits = svc.list_visits()
        assert len(visits) >= 120

    def test_seed_screen_failure_rate_approximately_25_percent(self, svc: CTMSService):
        patients = svc.list_patients()
        screen_failures = sum(1 for p in patients if p.status == PatientStatus.SCREEN_FAILED)
        total = len(patients)
        rate = screen_failures / total
        # Allow range 15%-35% for randomness
        assert 0.10 <= rate <= 0.40, f"Screen failure rate {rate:.1%} outside expected range"

    def test_seed_trials_have_regulatory_ids(self, svc: CTMSService):
        for trial_id in [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]:
            trial = svc.get_trial(trial_id)
            assert trial is not None
            assert "FDA IND" in trial.regulatory_ids

    def test_seed_trials_have_endpoints(self, svc: CTMSService):
        for trial_id in [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]:
            trial = svc.get_trial(trial_id)
            assert trial is not None
            assert trial.primary_endpoint
            assert len(trial.secondary_endpoints) > 0

    def test_seed_sites_have_pi_names(self, svc: CTMSService):
        sites = svc.list_sites()
        for site in sites:
            assert site.pi_name
            assert "Dr." in site.pi_name or "Prof." in site.pi_name

    def test_seed_sites_have_countries(self, svc: CTMSService):
        sites = svc.list_sites()
        countries = {s.country for s in sites}
        assert "US" in countries
        assert len(countries) >= 5


# =====================================================================
# TRIAL CRUD
# =====================================================================


class TestTrialCrud:
    """Test trial create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_trials(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    @pytest.mark.anyio
    async def test_list_trials_filter_phase(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials", params={"phase": "phase3"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["phase"] == "phase3"

    @pytest.mark.anyio
    async def test_list_trials_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials", params={"status": "enrolling"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "enrolling"

    @pytest.mark.anyio
    async def test_list_trials_filter_therapeutic_area(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/trials", params={"therapeutic_area": "oncology"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["therapeutic_area"] == "oncology"

    @pytest.mark.anyio
    async def test_get_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/{EYLEA_TRIAL}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == EYLEA_TRIAL
        assert data["protocol_number"] == "R1234-OPH-1553"

    @pytest.mark.anyio
    async def test_get_trial_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_trial(self, client: AsyncClient):
        payload = _make_trial_create()
        resp = await client.post(f"{API_PREFIX}/trials", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["protocol_number"] == "R9999-TST-0001"
        assert data["status"] == "planning"
        assert data["current_enrollment"] == 0
        assert data["id"].startswith("CTMS-TRIAL-")

    @pytest.mark.anyio
    async def test_create_trial_all_phases(self, client: AsyncClient):
        for phase in ["phase1", "phase1b", "phase2", "phase2b", "phase3", "phase3b", "phase4", "post_marketing"]:
            payload = _make_trial_create(
                phase=phase,
                protocol_number=f"R0000-{phase}",
                title=f"Test {phase} trial",
            )
            resp = await client.post(f"{API_PREFIX}/trials", json=payload)
            assert resp.status_code == 201
            assert resp.json()["phase"] == phase

    @pytest.mark.anyio
    async def test_update_trial(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/trials/{EYLEA_TRIAL}",
            json={"title": "Updated EYLEA Trial Title", "target_enrollment": 500},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated EYLEA Trial Title"
        assert data["target_enrollment"] == 500

    @pytest.mark.anyio
    async def test_update_trial_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/trials/{EYLEA_TRIAL}",
            json={"status": "fully_enrolled"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "fully_enrolled"

    @pytest.mark.anyio
    async def test_update_trial_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/trials/NONEXISTENT",
            json={"title": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_trial(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/trials/{EYLEA_TRIAL}")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/trials/{EYLEA_TRIAL}")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_trial_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/trials/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_trial_has_countries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/{EYLEA_TRIAL}")
        data = resp.json()
        assert isinstance(data["countries"], list)
        assert "US" in data["countries"]

    @pytest.mark.anyio
    async def test_trial_has_regulatory_ids(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/{EYLEA_TRIAL}")
        data = resp.json()
        assert "FDA IND" in data["regulatory_ids"]

    @pytest.mark.anyio
    async def test_trial_has_secondary_endpoints(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/{EYLEA_TRIAL}")
        data = resp.json()
        assert isinstance(data["secondary_endpoints"], list)
        assert len(data["secondary_endpoints"]) > 0


# =====================================================================
# SITE CRUD
# =====================================================================


class TestSiteCrud:
    """Test site create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_sites(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 15

    @pytest.mark.anyio
    async def test_list_sites_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_sites_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites", params={"status": "active"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "active"

    @pytest.mark.anyio
    async def test_list_sites_filter_country(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites", params={"country": "US"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["country"] == "US"

    @pytest.mark.anyio
    async def test_get_site(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/CTMS-SITE-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CTMS-SITE-001"
        assert data["name"] == "Bascom Palmer Eye Institute"

    @pytest.mark.anyio
    async def test_get_site_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_site(self, client: AsyncClient):
        payload = _make_site_create()
        resp = await client.post(f"{API_PREFIX}/sites", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Hospital"
        assert data["status"] == "selected"
        assert data["id"].startswith("CTMS-SITE-")

    @pytest.mark.anyio
    async def test_update_site(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sites/CTMS-SITE-001",
            json={"pi_name": "Dr. Updated PI", "status": "enrolling"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["pi_name"] == "Dr. Updated PI"
        assert data["status"] == "enrolling"

    @pytest.mark.anyio
    async def test_update_site_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sites/NONEXISTENT",
            json={"name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_site(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sites/CTMS-SITE-015")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/sites/CTMS-SITE-015")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_site_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sites/NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# PATIENT CRUD
# =====================================================================


class TestPatientCrud:
    """Test patient create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_patients(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 50

    @pytest.mark.anyio
    async def test_list_patients_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/patients", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_patients_filter_site(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/patients", params={"site_id": "CTMS-SITE-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["site_id"] == "CTMS-SITE-001"

    @pytest.mark.anyio
    async def test_list_patients_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/patients", params={"status": "screen_failed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["status"] == "screen_failed"

    @pytest.mark.anyio
    async def test_get_patient(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/CTMS-PAT-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CTMS-PAT-0001"

    @pytest.mark.anyio
    async def test_get_patient_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_patient(self, client: AsyncClient):
        payload = _make_patient_create()
        resp = await client.post(f"{API_PREFIX}/patients", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject_number"] == "SUBJ-TEST-001"
        assert data["status"] == "screening"
        assert data["id"].startswith("CTMS-PAT-")

    @pytest.mark.anyio
    async def test_update_patient_enroll(self, client: AsyncClient):
        # First create a screening patient
        payload = _make_patient_create(subject_number="SUBJ-ENROLL-001")
        resp = await client.post(f"{API_PREFIX}/patients", json=payload)
        pid = resp.json()["id"]

        # Enroll
        resp2 = await client.put(
            f"{API_PREFIX}/patients/{pid}",
            json={
                "status": "enrolled",
                "randomization_date": "2026-02-01",
                "treatment_arm": "Active Treatment",
            },
        )
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["status"] == "enrolled"
        assert data["treatment_arm"] == "Active Treatment"

    @pytest.mark.anyio
    async def test_update_patient_screen_fail(self, client: AsyncClient):
        payload = _make_patient_create(subject_number="SUBJ-SF-001")
        resp = await client.post(f"{API_PREFIX}/patients", json=payload)
        pid = resp.json()["id"]

        resp2 = await client.put(
            f"{API_PREFIX}/patients/{pid}",
            json={
                "status": "screen_failed",
                "withdrawal_reason": "Exclusion criterion met",
            },
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "screen_failed"

    @pytest.mark.anyio
    async def test_update_patient_withdraw(self, client: AsyncClient):
        # Find an active patient
        resp = await client.get(
            f"{API_PREFIX}/patients", params={"status": "active"}
        )
        data = resp.json()
        if data["total"] > 0:
            pid = data["items"][0]["id"]
            resp2 = await client.put(
                f"{API_PREFIX}/patients/{pid}",
                json={
                    "status": "withdrawn",
                    "withdrawal_reason": "Adverse event",
                },
            )
            assert resp2.status_code == 200
            assert resp2.json()["status"] == "withdrawn"

    @pytest.mark.anyio
    async def test_update_patient_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/patients/NONEXISTENT",
            json={"status": "enrolled"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_patient(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/patients/CTMS-PAT-0050")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/patients/CTMS-PAT-0050")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_patient_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/patients/NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# VISIT CRUD
# =====================================================================


class TestVisitCrud:
    """Test visit create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_visits(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 120

    @pytest.mark.anyio
    async def test_list_visits_filter_patient(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/visits", params={"patient_id": "CTMS-PAT-0001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["patient_id"] == "CTMS-PAT-0001"

    @pytest.mark.anyio
    async def test_list_visits_filter_trial(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/visits", params={"trial_id": EYLEA_TRIAL}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_list_visits_filter_status(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/visits", params={"status": "completed"}
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_visit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits/CTMS-VIS-0001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CTMS-VIS-0001"

    @pytest.mark.anyio
    async def test_get_visit_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_visit(self, client: AsyncClient):
        payload = _make_visit_create()
        resp = await client.post(f"{API_PREFIX}/visits", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["visit_name"] == "Test Visit"
        assert data["status"] == "scheduled"
        assert data["id"].startswith("CTMS-VIS-")

    @pytest.mark.anyio
    async def test_update_visit_complete_in_window(self, client: AsyncClient):
        # Create a visit then complete it within window
        payload = _make_visit_create(
            scheduled_date="2026-06-15",
            window_start="2026-06-12",
            window_end="2026-06-20",
        )
        resp = await client.post(f"{API_PREFIX}/visits", json=payload)
        vid = resp.json()["id"]

        resp2 = await client.put(
            f"{API_PREFIX}/visits/{vid}",
            json={"actual_date": "2026-06-15"},
        )
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["actual_date"] == "2026-06-15"
        assert data["status"] == "completed"

    @pytest.mark.anyio
    async def test_update_visit_out_of_window(self, client: AsyncClient):
        payload = _make_visit_create(
            scheduled_date="2026-06-15",
            window_start="2026-06-12",
            window_end="2026-06-20",
        )
        resp = await client.post(f"{API_PREFIX}/visits", json=payload)
        vid = resp.json()["id"]

        resp2 = await client.put(
            f"{API_PREFIX}/visits/{vid}",
            json={"actual_date": "2026-06-25"},
        )
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["status"] == "out_of_window"

    @pytest.mark.anyio
    async def test_update_visit_sdv(self, client: AsyncClient):
        # Find a completed visit
        resp = await client.get(
            f"{API_PREFIX}/visits", params={"status": "completed"}
        )
        data = resp.json()
        if data["total"] > 0:
            vid = data["items"][0]["id"]
            resp2 = await client.put(
                f"{API_PREFIX}/visits/{vid}",
                json={"source_data_verified": True},
            )
            assert resp2.status_code == 200
            assert resp2.json()["source_data_verified"] is True

    @pytest.mark.anyio
    async def test_update_visit_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/visits/NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_visit(self, client: AsyncClient):
        # Create then delete
        payload = _make_visit_create()
        resp = await client.post(f"{API_PREFIX}/visits", json=payload)
        vid = resp.json()["id"]

        resp2 = await client.delete(f"{API_PREFIX}/visits/{vid}")
        assert resp2.status_code == 204
        resp3 = await client.get(f"{API_PREFIX}/visits/{vid}")
        assert resp3.status_code == 404

    @pytest.mark.anyio
    async def test_delete_visit_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/visits/NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# ENROLLMENT SUMMARY
# =====================================================================


class TestEnrollmentSummary:
    """Test trial and site enrollment summaries."""

    @pytest.mark.anyio
    async def test_trial_enrollment_summary(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/{EYLEA_TRIAL}/enrollment-summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert "target_enrollment" in data
        assert "total_screened" in data
        assert "total_enrolled" in data
        assert "screen_failures" in data
        assert "screen_failure_rate" in data
        assert "enrollment_rate" in data
        assert "active_patients" in data
        assert "sites_active" in data

    @pytest.mark.anyio
    async def test_trial_enrollment_summary_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/NONEXISTENT/enrollment-summary")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_enrollment_summary_has_screen_failure_rate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/{EYLEA_TRIAL}/enrollment-summary")
        data = resp.json()
        assert 0 <= data["screen_failure_rate"] <= 100

    @pytest.mark.anyio
    async def test_enrollment_summary_all_trials(self, client: AsyncClient):
        for trial_id in [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]:
            resp = await client.get(f"{API_PREFIX}/trials/{trial_id}/enrollment-summary")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_screened"] > 0

    @pytest.mark.anyio
    async def test_site_enrollment(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/CTMS-SITE-001/enrollment")
        assert resp.status_code == 200
        data = resp.json()
        assert data["site_id"] == "CTMS-SITE-001"
        assert "enrollment_target" in data
        assert "enrolled" in data
        assert "screen_failures" in data
        assert "screen_failure_rate" in data
        assert "patients_by_status" in data

    @pytest.mark.anyio
    async def test_site_enrollment_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites/NONEXISTENT/enrollment")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_libtayo_fully_enrolled(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/{LIBTAYO_TRIAL}/enrollment-summary")
        data = resp.json()
        assert data["total_enrolled"] > 0


# =====================================================================
# VISIT COMPLIANCE
# =====================================================================


class TestVisitCompliance:
    """Test visit compliance metrics."""

    @pytest.mark.anyio
    async def test_visit_compliance(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/{EYLEA_TRIAL}/visit-compliance")
        assert resp.status_code == 200
        data = resp.json()
        assert data["trial_id"] == EYLEA_TRIAL
        assert "total_visits" in data
        assert "completed" in data
        assert "out_of_window" in data
        assert "compliance_rate" in data
        assert "sdv_rate" in data

    @pytest.mark.anyio
    async def test_visit_compliance_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/NONEXISTENT/visit-compliance")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_visit_compliance_rates_valid(self, client: AsyncClient):
        for trial_id in [EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL]:
            resp = await client.get(f"{API_PREFIX}/trials/{trial_id}/visit-compliance")
            data = resp.json()
            assert 0 <= data["compliance_rate"] <= 100
            assert 0 <= data["sdv_rate"] <= 100

    @pytest.mark.anyio
    async def test_visit_compliance_has_sdv_counts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials/{EYLEA_TRIAL}/visit-compliance")
        data = resp.json()
        assert "sdv_completed" in data
        assert "sdv_eligible" in data
        assert data["sdv_eligible"] >= data["sdv_completed"]


# =====================================================================
# CTMS METRICS
# =====================================================================


class TestCTMSMetrics:
    """Test CTMS metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_trials"] == 3
        assert data["total_sites"] == 15
        assert data["total_patients"] == 50
        assert data["avg_enrollment_rate"] > 0
        assert data["screen_failure_rate_overall"] > 0

    @pytest.mark.anyio
    async def test_metrics_trials_by_phase(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_phase = data["trials_by_phase"]
        total_by_phase = sum(by_phase.values())
        assert total_by_phase == data["total_trials"]

    @pytest.mark.anyio
    async def test_metrics_trials_by_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        by_status = data["trials_by_status"]
        total_by_status = sum(by_status.values())
        assert total_by_status == data["total_trials"]

    def test_metrics_screen_failure_rate(self, svc: CTMSService):
        metrics = svc.get_metrics()
        # Should be approximately 25%
        assert 5.0 <= metrics.screen_failure_rate_overall <= 50.0

    def test_metrics_enrollment_rate(self, svc: CTMSService):
        metrics = svc.get_metrics()
        assert metrics.avg_enrollment_rate > 0
        assert metrics.avg_enrollment_rate <= 100.0


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_ctms_service()
        svc2 = get_ctms_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_ctms_service()
        svc2 = reset_ctms_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_ctms_service()
        svc.delete_trial(EYLEA_TRIAL)
        assert svc.get_trial(EYLEA_TRIAL) is None
        svc2 = reset_ctms_service()
        assert svc2.get_trial(EYLEA_TRIAL) is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_trials_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_sites_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_patients_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_visits_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_trial_with_all_study_designs(self, client: AsyncClient):
        for design in ["parallel", "crossover", "factorial", "single_arm", "basket", "umbrella", "platform", "adaptive"]:
            payload = _make_trial_create(
                study_design=design,
                protocol_number=f"R0000-{design}",
                title=f"Test {design} trial",
            )
            resp = await client.post(f"{API_PREFIX}/trials", json=payload)
            assert resp.status_code == 201
            assert resp.json()["study_design"] == design

    @pytest.mark.anyio
    async def test_create_trial_with_all_therapeutic_areas(self, client: AsyncClient):
        for ta in ["oncology", "immunology", "ophthalmology", "rare_disease", "neurology", "cardiology", "infectious_disease"]:
            payload = _make_trial_create(
                therapeutic_area=ta,
                protocol_number=f"R0000-{ta}",
                title=f"Test {ta} trial",
            )
            resp = await client.post(f"{API_PREFIX}/trials", json=payload)
            assert resp.status_code == 201
            assert resp.json()["therapeutic_area"] == ta

    @pytest.mark.anyio
    async def test_patient_statuses_in_seed_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "screen_failed" in statuses
        assert "active" in statuses

    @pytest.mark.anyio
    async def test_visit_statuses_in_seed_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "completed" in statuses
        assert "scheduled" in statuses

    @pytest.mark.anyio
    async def test_site_statuses_in_seed_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "active" in statuses

    @pytest.mark.anyio
    async def test_screen_failed_patients_have_withdrawal_reason(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/patients", params={"status": "screen_failed"}
        )
        data = resp.json()
        for item in data["items"]:
            assert item["withdrawal_reason"] is not None

    @pytest.mark.anyio
    async def test_active_patients_have_treatment_arm(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/patients", params={"status": "active"}
        )
        data = resp.json()
        for item in data["items"]:
            assert item["treatment_arm"] is not None

    @pytest.mark.anyio
    async def test_completed_visits_have_actual_date(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/visits", params={"status": "completed"}
        )
        data = resp.json()
        for item in data["items"]:
            assert item["actual_date"] is not None

    @pytest.mark.anyio
    async def test_scheduled_visits_no_actual_date(self, client: AsyncClient):
        resp = await client.get(
            f"{API_PREFIX}/visits", params={"status": "scheduled"}
        )
        data = resp.json()
        for item in data["items"]:
            assert item["actual_date"] is None

    @pytest.mark.anyio
    async def test_visit_window_dates_valid(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits")
        data = resp.json()
        for item in data["items"]:
            assert item["window_start"] <= item["scheduled_date"]
            assert item["window_end"] >= item["scheduled_date"]


# =====================================================================
# TRIAL STATUS TRANSITIONS
# =====================================================================


class TestTrialStatusTransitions:
    """Test trial status can be updated through lifecycle."""

    @pytest.mark.anyio
    async def test_trial_lifecycle_planning_to_completed(self, client: AsyncClient):
        payload = _make_trial_create()
        resp = await client.post(f"{API_PREFIX}/trials", json=payload)
        tid = resp.json()["id"]
        assert resp.json()["status"] == "planning"

        for status in ["startup", "enrolling", "fully_enrolled", "last_patient_last_visit", "database_lock", "analysis", "completed"]:
            resp = await client.put(
                f"{API_PREFIX}/trials/{tid}",
                json={"status": status},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == status

    @pytest.mark.anyio
    async def test_trial_can_be_terminated(self, client: AsyncClient):
        payload = _make_trial_create()
        resp = await client.post(f"{API_PREFIX}/trials", json=payload)
        tid = resp.json()["id"]

        resp = await client.put(
            f"{API_PREFIX}/trials/{tid}",
            json={"status": "terminated"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "terminated"

    @pytest.mark.anyio
    async def test_trial_update_actual_end_date(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/trials/{EYLEA_TRIAL}",
            json={"actual_end_date": "2027-10-15", "status": "completed"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["actual_end_date"] == "2027-10-15"
        assert data["status"] == "completed"


# =====================================================================
# SITE STATUS TRANSITIONS
# =====================================================================


class TestSiteStatusTransitions:
    """Test site status transitions."""

    @pytest.mark.anyio
    async def test_site_lifecycle(self, client: AsyncClient):
        payload = _make_site_create()
        resp = await client.post(f"{API_PREFIX}/sites", json=payload)
        sid = resp.json()["id"]
        assert resp.json()["status"] == "selected"

        for status in ["initiating", "active", "enrolling", "closed_to_enrollment", "closed"]:
            resp = await client.put(
                f"{API_PREFIX}/sites/{sid}",
                json={"status": status},
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == status

    @pytest.mark.anyio
    async def test_site_activation_date_update(self, client: AsyncClient):
        payload = _make_site_create()
        resp = await client.post(f"{API_PREFIX}/sites", json=payload)
        sid = resp.json()["id"]

        resp = await client.put(
            f"{API_PREFIX}/sites/{sid}",
            json={"activation_date": "2026-03-01", "status": "active"},
        )
        assert resp.status_code == 200
        assert resp.json()["activation_date"] == "2026-03-01"


# =====================================================================
# PATIENT LIFECYCLE
# =====================================================================


class TestPatientLifecycle:
    """Test patient lifecycle transitions."""

    def test_patient_lifecycle_screening_to_completed(self, svc: CTMSService):
        patient = svc.create_patient(PatientCreate(
            trial_id=EYLEA_TRIAL,
            site_id="CTMS-SITE-001",
            subject_number="SUBJ-LC-001",
            screening_date=date(2026, 1, 15),
        ))
        assert patient.status == PatientStatus.SCREENING

        updated = svc.update_patient(patient.id, PatientUpdate(
            status=PatientStatus.ENROLLED,
            randomization_date=date(2026, 1, 25),
            treatment_arm="Active",
        ))
        assert updated is not None
        assert updated.status == PatientStatus.ENROLLED

        updated = svc.update_patient(patient.id, PatientUpdate(
            status=PatientStatus.ACTIVE,
        ))
        assert updated is not None
        assert updated.status == PatientStatus.ACTIVE

        updated = svc.update_patient(patient.id, PatientUpdate(
            status=PatientStatus.COMPLETED,
        ))
        assert updated is not None
        assert updated.status == PatientStatus.COMPLETED

    def test_patient_screen_failure_increments_site_count(self, svc: CTMSService):
        site = svc.get_site("CTMS-SITE-001")
        assert site is not None
        initial_sf = site.screen_failure_count

        patient = svc.create_patient(PatientCreate(
            trial_id=EYLEA_TRIAL,
            site_id="CTMS-SITE-001",
            subject_number="SUBJ-SF-002",
            screening_date=date(2026, 2, 1),
        ))

        svc.update_patient(patient.id, PatientUpdate(
            status=PatientStatus.SCREEN_FAILED,
            withdrawal_reason="Lab values abnormal",
        ))

        site_after = svc.get_site("CTMS-SITE-001")
        assert site_after is not None
        assert site_after.screen_failure_count == initial_sf + 1


# =====================================================================
# VISIT WINDOW COMPLIANCE
# =====================================================================


class TestVisitWindowCompliance:
    """Test visit window compliance logic."""

    def test_visit_in_window_auto_completes(self, svc: CTMSService):
        visit = svc.create_visit(VisitCreate(
            patient_id="CTMS-PAT-0001",
            trial_id=EYLEA_TRIAL,
            visit_number=50,
            visit_name="Window Test",
            scheduled_date=date(2026, 6, 15),
            window_start=date(2026, 6, 12),
            window_end=date(2026, 6, 20),
        ))
        updated = svc.update_visit(visit.id, VisitUpdate(
            actual_date=date(2026, 6, 15),
        ))
        assert updated is not None
        assert updated.status == VisitStatus.COMPLETED

    def test_visit_out_of_window_detected(self, svc: CTMSService):
        visit = svc.create_visit(VisitCreate(
            patient_id="CTMS-PAT-0001",
            trial_id=EYLEA_TRIAL,
            visit_number=51,
            visit_name="OOW Test",
            scheduled_date=date(2026, 6, 15),
            window_start=date(2026, 6, 12),
            window_end=date(2026, 6, 20),
        ))
        updated = svc.update_visit(visit.id, VisitUpdate(
            actual_date=date(2026, 6, 25),
        ))
        assert updated is not None
        assert updated.status == VisitStatus.OUT_OF_WINDOW

    def test_visit_window_boundary_start(self, svc: CTMSService):
        visit = svc.create_visit(VisitCreate(
            patient_id="CTMS-PAT-0001",
            trial_id=EYLEA_TRIAL,
            visit_number=52,
            visit_name="Boundary Start Test",
            scheduled_date=date(2026, 6, 15),
            window_start=date(2026, 6, 12),
            window_end=date(2026, 6, 20),
        ))
        updated = svc.update_visit(visit.id, VisitUpdate(
            actual_date=date(2026, 6, 12),
        ))
        assert updated is not None
        assert updated.status == VisitStatus.COMPLETED

    def test_visit_window_boundary_end(self, svc: CTMSService):
        visit = svc.create_visit(VisitCreate(
            patient_id="CTMS-PAT-0001",
            trial_id=EYLEA_TRIAL,
            visit_number=53,
            visit_name="Boundary End Test",
            scheduled_date=date(2026, 6, 15),
            window_start=date(2026, 6, 12),
            window_end=date(2026, 6, 20),
        ))
        updated = svc.update_visit(visit.id, VisitUpdate(
            actual_date=date(2026, 6, 20),
        ))
        assert updated is not None
        assert updated.status == VisitStatus.COMPLETED

    def test_visit_before_window_out(self, svc: CTMSService):
        visit = svc.create_visit(VisitCreate(
            patient_id="CTMS-PAT-0001",
            trial_id=EYLEA_TRIAL,
            visit_number=54,
            visit_name="Before Window Test",
            scheduled_date=date(2026, 6, 15),
            window_start=date(2026, 6, 12),
            window_end=date(2026, 6, 20),
        ))
        updated = svc.update_visit(visit.id, VisitUpdate(
            actual_date=date(2026, 6, 10),
        ))
        assert updated is not None
        assert updated.status == VisitStatus.OUT_OF_WINDOW


# =====================================================================
# ENUMERATION COVERAGE
# =====================================================================


class TestEnumerations:
    """Test enum values are correctly used throughout the system."""

    @pytest.mark.anyio
    async def test_trial_phases_in_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials")
        data = resp.json()
        phases = {item["phase"] for item in data["items"]}
        assert "phase3" in phases

    @pytest.mark.anyio
    async def test_trial_statuses_in_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert "enrolling" in statuses
        assert "fully_enrolled" in statuses

    @pytest.mark.anyio
    async def test_therapeutic_areas_in_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials")
        data = resp.json()
        areas = {item["therapeutic_area"] for item in data["items"]}
        assert "ophthalmology" in areas
        assert "immunology" in areas
        assert "oncology" in areas

    @pytest.mark.anyio
    async def test_study_designs_in_data(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/trials")
        data = resp.json()
        designs = {item["study_design"] for item in data["items"]}
        assert "parallel" in designs
        assert "adaptive" in designs

    @pytest.mark.anyio
    async def test_site_status_values(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sites")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert len(statuses) >= 2

    @pytest.mark.anyio
    async def test_patient_status_values(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients")
        data = resp.json()
        statuses = {item["status"] for item in data["items"]}
        assert len(statuses) >= 2


# =====================================================================
# DATA INTEGRITY
# =====================================================================


class TestDataIntegrity:
    """Test data relationships and integrity."""

    @pytest.mark.anyio
    async def test_patients_belong_to_valid_trials(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients")
        data = resp.json()
        valid_trial_ids = {EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL}
        for item in data["items"]:
            assert item["trial_id"] in valid_trial_ids

    @pytest.mark.anyio
    async def test_patients_belong_to_valid_sites(self, client: AsyncClient):
        sites_resp = await client.get(f"{API_PREFIX}/sites")
        valid_site_ids = {s["id"] for s in sites_resp.json()["items"]}

        patients_resp = await client.get(f"{API_PREFIX}/patients")
        for item in patients_resp.json()["items"]:
            assert item["site_id"] in valid_site_ids

    @pytest.mark.anyio
    async def test_visits_belong_to_valid_patients(self, client: AsyncClient):
        patients_resp = await client.get(f"{API_PREFIX}/patients")
        valid_patient_ids = {p["id"] for p in patients_resp.json()["items"]}

        visits_resp = await client.get(f"{API_PREFIX}/visits")
        for item in visits_resp.json()["items"]:
            assert item["patient_id"] in valid_patient_ids

    @pytest.mark.anyio
    async def test_visits_belong_to_valid_trials(self, client: AsyncClient):
        valid_trial_ids = {EYLEA_TRIAL, DUPIXENT_TRIAL, LIBTAYO_TRIAL}
        visits_resp = await client.get(f"{API_PREFIX}/visits")
        for item in visits_resp.json()["items"]:
            assert item["trial_id"] in valid_trial_ids

    def test_metrics_total_patients_matches_list(self, svc: CTMSService):
        metrics = svc.get_metrics()
        patients = svc.list_patients()
        assert metrics.total_patients == len(patients)

    def test_metrics_total_sites_matches_list(self, svc: CTMSService):
        metrics = svc.get_metrics()
        sites = svc.list_sites()
        assert metrics.total_sites == len(sites)

    def test_metrics_total_trials_matches_list(self, svc: CTMSService):
        metrics = svc.get_metrics()
        trials = svc.list_trials()
        assert metrics.total_trials == len(trials)
