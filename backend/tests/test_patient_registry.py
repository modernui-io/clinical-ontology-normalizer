"""Tests for Patient Registry & Long-Term Follow-Up (PAT-REG).

Covers:
- Seed data verification (registries, patients, visits, outcomes, milestones)
- Registry CRUD (create, read, update, delete, list, filter by trial/type/status)
- Patient enrollment CRUD with registry validation
- Follow-up visit CRUD with patient validation
- Outcome report CRUD with patient validation
- Milestone CRUD with registry validation
- Metrics computation (visit completion rate, retention rate, etc.)
- Error handling (404s, 400s, invalid operations)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.patient_registry import (
    EnrollmentStatus,
    FollowUpStatus,
    FollowUpType,
    OutcomeCategory,
    RegistryStatus,
    RegistryType,
)
from app.services.patient_registry_service import (
    PatientRegistryService,
    get_patient_registry_service,
    reset_patient_registry_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/patient-registry"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_patient_registry_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> PatientRegistryService:
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


def _make_registry_create(**overrides) -> dict:
    defaults = {
        "name": "Test Registry",
        "registry_type": "disease_registry",
        "disease_area": "Test Disease",
        "description": "A test registry",
        "sponsor": "Test Sponsor",
        "target_enrollment": 100,
        "follow_up_duration_months": 24,
        "countries": ["US"],
    }
    defaults.update(overrides)
    return defaults


def _make_patient_create(**overrides) -> dict:
    defaults = {
        "registry_id": "REG-001",
        "patient_id": "PAT-99999",
        "site_id": "SITE-101",
    }
    defaults.update(overrides)
    return defaults


def _make_visit_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "registry_patient_id": "RPAT-001",
        "visit_type": "scheduled",
        "visit_number": 99,
        "scheduled_date": (now + timedelta(days=30)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_outcome_create(**overrides) -> dict:
    defaults = {
        "registry_patient_id": "RPAT-001",
        "category": "primary",
        "outcome_name": "Test Outcome",
        "value": "42",
        "reported_by": "Dr. Test",
    }
    defaults.update(overrides)
    return defaults


def _make_milestone_create(**overrides) -> dict:
    now = datetime.now(timezone.utc)
    defaults = {
        "registry_id": "REG-001",
        "milestone_name": "Test Milestone",
        "description": "A test milestone",
        "target_date": (now + timedelta(days=90)).isoformat(),
        "responsible_person": "Test Person",
    }
    defaults.update(overrides)
    return defaults


# ===========================================================================
# SEED DATA VERIFICATION
# ===========================================================================


class TestSeedData:
    """Verify seed data is correctly loaded."""

    def test_seed_registries_count(self, svc: PatientRegistryService):
        assert len(svc.list_registries()) == 10

    def test_seed_patients_count(self, svc: PatientRegistryService):
        assert len(svc.list_patients()) == 12

    def test_seed_visits_count(self, svc: PatientRegistryService):
        assert len(svc.list_visits()) == 14

    def test_seed_outcomes_count(self, svc: PatientRegistryService):
        assert len(svc.list_outcomes()) == 12

    def test_seed_milestones_count(self, svc: PatientRegistryService):
        assert len(svc.list_milestones()) == 10

    def test_seed_eylea_registry(self, svc: PatientRegistryService):
        reg = svc.get_registry("REG-001")
        assert reg is not None
        assert reg.trial_id == EYLEA_TRIAL
        assert reg.registry_type == RegistryType.DISEASE_REGISTRY
        assert reg.disease_area == "Diabetic Macular Edema"
        assert reg.status == RegistryStatus.ACTIVE

    def test_seed_dupixent_registry(self, svc: PatientRegistryService):
        reg = svc.get_registry("REG-002")
        assert reg is not None
        assert reg.trial_id == DUPIXENT_TRIAL
        assert reg.registry_type == RegistryType.NATURAL_HISTORY
        assert reg.disease_area == "Atopic Dermatitis"

    def test_seed_libtayo_registry(self, svc: PatientRegistryService):
        reg = svc.get_registry("REG-003")
        assert reg is not None
        assert reg.trial_id == LIBTAYO_TRIAL
        assert reg.registry_type == RegistryType.POST_MARKETING
        assert reg.disease_area == "Cutaneous Squamous Cell Carcinoma"

    def test_seed_patient_statuses_present(self, svc: PatientRegistryService):
        statuses = {p.enrollment_status for p in svc.list_patients()}
        assert EnrollmentStatus.ACTIVE in statuses
        assert EnrollmentStatus.SCREENED in statuses
        assert EnrollmentStatus.COMPLETED in statuses
        assert EnrollmentStatus.WITHDRAWN in statuses
        assert EnrollmentStatus.LOST_TO_FOLLOW_UP in statuses
        assert EnrollmentStatus.DECEASED in statuses

    def test_seed_visit_types_present(self, svc: PatientRegistryService):
        types = {v.visit_type for v in svc.list_visits()}
        assert FollowUpType.SCHEDULED in types
        assert FollowUpType.SAFETY in types
        assert FollowUpType.ANNUAL_REVIEW in types
        assert FollowUpType.END_OF_STUDY in types

    def test_seed_outcome_categories_present(self, svc: PatientRegistryService):
        cats = {o.category for o in svc.list_outcomes()}
        assert OutcomeCategory.PRIMARY in cats
        assert OutcomeCategory.SECONDARY in cats
        assert OutcomeCategory.SAFETY in cats
        assert OutcomeCategory.BIOMARKER in cats
        assert OutcomeCategory.SURVIVAL in cats
        assert OutcomeCategory.PATIENT_REPORTED in cats

    def test_seed_registry_types_present(self, svc: PatientRegistryService):
        types = {r.registry_type for r in svc.list_registries()}
        assert RegistryType.DISEASE_REGISTRY in types
        assert RegistryType.NATURAL_HISTORY in types
        assert RegistryType.POST_MARKETING in types
        assert RegistryType.PREGNANCY_REGISTRY in types
        assert RegistryType.PRODUCT_REGISTRY in types
        assert RegistryType.EXPANDED_ACCESS in types


# ===========================================================================
# REGISTRY CRUD (Service Layer)
# ===========================================================================


class TestRegistryServiceCRUD:
    """Test registry CRUD operations at service layer."""

    def test_list_all_registries(self, svc: PatientRegistryService):
        result = svc.list_registries()
        assert len(result) == 10

    def test_list_registries_filter_by_trial(self, svc: PatientRegistryService):
        result = svc.list_registries(trial_id=EYLEA_TRIAL)
        assert all(r.trial_id == EYLEA_TRIAL for r in result)
        assert len(result) >= 3

    def test_list_registries_filter_by_type(self, svc: PatientRegistryService):
        result = svc.list_registries(registry_type=RegistryType.DISEASE_REGISTRY)
        assert all(r.registry_type == RegistryType.DISEASE_REGISTRY for r in result)
        assert len(result) >= 3

    def test_list_registries_filter_by_status(self, svc: PatientRegistryService):
        result = svc.list_registries(status=RegistryStatus.ACTIVE)
        assert all(r.status == RegistryStatus.ACTIVE for r in result)
        assert len(result) >= 4

    def test_list_registries_combined_filters(self, svc: PatientRegistryService):
        result = svc.list_registries(trial_id=EYLEA_TRIAL, status=RegistryStatus.ACTIVE)
        assert all(r.trial_id == EYLEA_TRIAL and r.status == RegistryStatus.ACTIVE for r in result)

    def test_get_registry_exists(self, svc: PatientRegistryService):
        reg = svc.get_registry("REG-001")
        assert reg is not None
        assert reg.id == "REG-001"

    def test_get_registry_not_found(self, svc: PatientRegistryService):
        assert svc.get_registry("REG-NONEXISTENT") is None

    def test_create_registry(self, svc: PatientRegistryService):
        from app.schemas.patient_registry import RegistryCreate
        payload = RegistryCreate(**_make_registry_create())
        result = svc.create_registry(payload)
        assert result.id.startswith("REG-")
        assert result.name == "Test Registry"
        assert result.status == RegistryStatus.PLANNING
        assert result.current_enrollment == 0

    def test_update_registry(self, svc: PatientRegistryService):
        from app.schemas.patient_registry import RegistryUpdate
        payload = RegistryUpdate(status=RegistryStatus.ENROLLING, sites_count=20)
        result = svc.update_registry("REG-009", payload)
        assert result is not None
        assert result.status == RegistryStatus.ENROLLING
        assert result.sites_count == 20

    def test_update_registry_not_found(self, svc: PatientRegistryService):
        from app.schemas.patient_registry import RegistryUpdate
        payload = RegistryUpdate(status=RegistryStatus.CLOSED)
        assert svc.update_registry("REG-NONEXISTENT", payload) is None

    def test_delete_registry(self, svc: PatientRegistryService):
        assert svc.delete_registry("REG-010") is True
        assert svc.get_registry("REG-010") is None

    def test_delete_registry_not_found(self, svc: PatientRegistryService):
        assert svc.delete_registry("REG-NONEXISTENT") is False


# ===========================================================================
# PATIENT CRUD (Service Layer)
# ===========================================================================


class TestPatientServiceCRUD:
    """Test patient enrollment CRUD operations at service layer."""

    def test_list_all_patients(self, svc: PatientRegistryService):
        result = svc.list_patients()
        assert len(result) == 12

    def test_list_patients_filter_by_registry(self, svc: PatientRegistryService):
        result = svc.list_patients(registry_id="REG-001")
        assert all(p.registry_id == "REG-001" for p in result)
        assert len(result) >= 3

    def test_list_patients_filter_by_status(self, svc: PatientRegistryService):
        result = svc.list_patients(enrollment_status=EnrollmentStatus.ACTIVE)
        assert all(p.enrollment_status == EnrollmentStatus.ACTIVE for p in result)

    def test_list_patients_filter_by_patient_id(self, svc: PatientRegistryService):
        result = svc.list_patients(patient_id="PAT-10001")
        assert len(result) == 1
        assert result[0].patient_id == "PAT-10001"

    def test_get_patient_exists(self, svc: PatientRegistryService):
        pat = svc.get_patient("RPAT-001")
        assert pat is not None
        assert pat.registry_id == "REG-001"

    def test_get_patient_not_found(self, svc: PatientRegistryService):
        assert svc.get_patient("RPAT-NONEXISTENT") is None

    def test_create_patient(self, svc: PatientRegistryService):
        from app.schemas.patient_registry import RegistryPatientCreate
        payload = RegistryPatientCreate(**_make_patient_create())
        result = svc.create_patient(payload)
        assert result.id.startswith("RPAT-")
        assert result.enrollment_status == EnrollmentStatus.SCREENED
        assert result.registry_id == "REG-001"

    def test_create_patient_invalid_registry(self, svc: PatientRegistryService):
        from app.schemas.patient_registry import RegistryPatientCreate
        payload = RegistryPatientCreate(**_make_patient_create(registry_id="REG-NONEXISTENT"))
        with pytest.raises(ValueError, match="not found"):
            svc.create_patient(payload)

    def test_update_patient(self, svc: PatientRegistryService):
        from app.schemas.patient_registry import RegistryPatientUpdate
        payload = RegistryPatientUpdate(enrollment_status=EnrollmentStatus.ACTIVE)
        result = svc.update_patient("RPAT-010", payload)
        assert result is not None
        assert result.enrollment_status == EnrollmentStatus.ACTIVE

    def test_update_patient_not_found(self, svc: PatientRegistryService):
        from app.schemas.patient_registry import RegistryPatientUpdate
        payload = RegistryPatientUpdate(enrollment_status=EnrollmentStatus.ACTIVE)
        assert svc.update_patient("RPAT-NONEXISTENT", payload) is None

    def test_delete_patient(self, svc: PatientRegistryService):
        assert svc.delete_patient("RPAT-010") is True
        assert svc.get_patient("RPAT-010") is None

    def test_delete_patient_not_found(self, svc: PatientRegistryService):
        assert svc.delete_patient("RPAT-NONEXISTENT") is False


# ===========================================================================
# VISIT CRUD (Service Layer)
# ===========================================================================


class TestVisitServiceCRUD:
    """Test follow-up visit CRUD operations at service layer."""

    def test_list_all_visits(self, svc: PatientRegistryService):
        result = svc.list_visits()
        assert len(result) == 14

    def test_list_visits_filter_by_patient(self, svc: PatientRegistryService):
        result = svc.list_visits(registry_patient_id="RPAT-001")
        assert all(v.registry_patient_id == "RPAT-001" for v in result)
        assert len(result) >= 3

    def test_list_visits_filter_by_type(self, svc: PatientRegistryService):
        result = svc.list_visits(visit_type=FollowUpType.SAFETY)
        assert all(v.visit_type == FollowUpType.SAFETY for v in result)
        assert len(result) >= 1

    def test_list_visits_filter_by_status(self, svc: PatientRegistryService):
        result = svc.list_visits(visit_status=FollowUpStatus.COMPLETED)
        assert all(v.status == FollowUpStatus.COMPLETED for v in result)

    def test_get_visit_exists(self, svc: PatientRegistryService):
        v = svc.get_visit("FUV-001")
        assert v is not None
        assert v.registry_patient_id == "RPAT-001"

    def test_get_visit_not_found(self, svc: PatientRegistryService):
        assert svc.get_visit("FUV-NONEXISTENT") is None

    def test_create_visit(self, svc: PatientRegistryService):
        from app.schemas.patient_registry import FollowUpVisitCreate
        payload = FollowUpVisitCreate(**_make_visit_create())
        result = svc.create_visit(payload)
        assert result.id.startswith("FUV-")
        assert result.status == FollowUpStatus.SCHEDULED

    def test_create_visit_invalid_patient(self, svc: PatientRegistryService):
        from app.schemas.patient_registry import FollowUpVisitCreate
        payload = FollowUpVisitCreate(**_make_visit_create(registry_patient_id="RPAT-NONEXISTENT"))
        with pytest.raises(ValueError, match="not found"):
            svc.create_visit(payload)

    def test_update_visit(self, svc: PatientRegistryService):
        from app.schemas.patient_registry import FollowUpVisitUpdate
        payload = FollowUpVisitUpdate(status=FollowUpStatus.COMPLETED, data_complete=True)
        result = svc.update_visit("FUV-004", payload)
        assert result is not None
        assert result.status == FollowUpStatus.COMPLETED
        assert result.data_complete is True

    def test_update_visit_not_found(self, svc: PatientRegistryService):
        from app.schemas.patient_registry import FollowUpVisitUpdate
        payload = FollowUpVisitUpdate(status=FollowUpStatus.CANCELLED)
        assert svc.update_visit("FUV-NONEXISTENT", payload) is None

    def test_delete_visit(self, svc: PatientRegistryService):
        assert svc.delete_visit("FUV-012") is True
        assert svc.get_visit("FUV-012") is None

    def test_delete_visit_not_found(self, svc: PatientRegistryService):
        assert svc.delete_visit("FUV-NONEXISTENT") is False


# ===========================================================================
# OUTCOME CRUD (Service Layer)
# ===========================================================================


class TestOutcomeServiceCRUD:
    """Test outcome report CRUD operations at service layer."""

    def test_list_all_outcomes(self, svc: PatientRegistryService):
        result = svc.list_outcomes()
        assert len(result) == 12

    def test_list_outcomes_filter_by_patient(self, svc: PatientRegistryService):
        result = svc.list_outcomes(registry_patient_id="RPAT-001")
        assert all(o.registry_patient_id == "RPAT-001" for o in result)
        assert len(result) >= 2

    def test_list_outcomes_filter_by_category(self, svc: PatientRegistryService):
        result = svc.list_outcomes(category=OutcomeCategory.PRIMARY)
        assert all(o.category == OutcomeCategory.PRIMARY for o in result)
        assert len(result) >= 3

    def test_get_outcome_exists(self, svc: PatientRegistryService):
        o = svc.get_outcome("OUT-001")
        assert o is not None
        assert o.outcome_name == "Best Corrected Visual Acuity (BCVA)"

    def test_get_outcome_not_found(self, svc: PatientRegistryService):
        assert svc.get_outcome("OUT-NONEXISTENT") is None

    def test_create_outcome(self, svc: PatientRegistryService):
        from app.schemas.patient_registry import OutcomeReportCreate
        payload = OutcomeReportCreate(**_make_outcome_create())
        result = svc.create_outcome(payload)
        assert result.id.startswith("OUT-")
        assert result.outcome_name == "Test Outcome"

    def test_create_outcome_invalid_patient(self, svc: PatientRegistryService):
        from app.schemas.patient_registry import OutcomeReportCreate
        payload = OutcomeReportCreate(**_make_outcome_create(registry_patient_id="RPAT-NONEXISTENT"))
        with pytest.raises(ValueError, match="not found"):
            svc.create_outcome(payload)

    def test_delete_outcome(self, svc: PatientRegistryService):
        assert svc.delete_outcome("OUT-012") is True
        assert svc.get_outcome("OUT-012") is None

    def test_delete_outcome_not_found(self, svc: PatientRegistryService):
        assert svc.delete_outcome("OUT-NONEXISTENT") is False


# ===========================================================================
# MILESTONE CRUD (Service Layer)
# ===========================================================================


class TestMilestoneServiceCRUD:
    """Test registry milestone CRUD operations at service layer."""

    def test_list_all_milestones(self, svc: PatientRegistryService):
        result = svc.list_milestones()
        assert len(result) == 10

    def test_list_milestones_filter_by_registry(self, svc: PatientRegistryService):
        result = svc.list_milestones(registry_id="REG-001")
        assert all(m.registry_id == "REG-001" for m in result)
        assert len(result) >= 3

    def test_get_milestone_exists(self, svc: PatientRegistryService):
        m = svc.get_milestone("RMS-001")
        assert m is not None
        assert m.achieved is True

    def test_get_milestone_not_found(self, svc: PatientRegistryService):
        assert svc.get_milestone("RMS-NONEXISTENT") is None

    def test_create_milestone(self, svc: PatientRegistryService):
        from app.schemas.patient_registry import RegistryMilestoneCreate
        payload = RegistryMilestoneCreate(**_make_milestone_create())
        result = svc.create_milestone(payload)
        assert result.id.startswith("RMS-")
        assert result.achieved is False
        assert result.actual_date is None

    def test_create_milestone_invalid_registry(self, svc: PatientRegistryService):
        from app.schemas.patient_registry import RegistryMilestoneCreate
        payload = RegistryMilestoneCreate(**_make_milestone_create(registry_id="REG-NONEXISTENT"))
        with pytest.raises(ValueError, match="not found"):
            svc.create_milestone(payload)

    def test_update_milestone(self, svc: PatientRegistryService):
        from app.schemas.patient_registry import RegistryMilestoneUpdate
        now = datetime.now(timezone.utc)
        payload = RegistryMilestoneUpdate(achieved=True, actual_date=now, notes="Done")
        result = svc.update_milestone("RMS-004", payload)
        assert result is not None
        assert result.achieved is True
        assert result.notes == "Done"

    def test_update_milestone_not_found(self, svc: PatientRegistryService):
        from app.schemas.patient_registry import RegistryMilestoneUpdate
        payload = RegistryMilestoneUpdate(achieved=True)
        assert svc.update_milestone("RMS-NONEXISTENT", payload) is None

    def test_delete_milestone(self, svc: PatientRegistryService):
        assert svc.delete_milestone("RMS-010") is True
        assert svc.get_milestone("RMS-010") is None

    def test_delete_milestone_not_found(self, svc: PatientRegistryService):
        assert svc.delete_milestone("RMS-NONEXISTENT") is False


# ===========================================================================
# METRICS (Service Layer)
# ===========================================================================


class TestMetricsService:
    """Test metrics computation at service layer."""

    def test_metrics_total_registries(self, svc: PatientRegistryService):
        m = svc.get_metrics()
        assert m.total_registries == 10

    def test_metrics_total_patients(self, svc: PatientRegistryService):
        m = svc.get_metrics()
        assert m.total_patients == 12

    def test_metrics_active_patients(self, svc: PatientRegistryService):
        m = svc.get_metrics()
        assert m.active_patients >= 4

    def test_metrics_lost_to_follow_up(self, svc: PatientRegistryService):
        m = svc.get_metrics()
        assert m.lost_to_follow_up >= 1

    def test_metrics_total_visits(self, svc: PatientRegistryService):
        m = svc.get_metrics()
        assert m.total_follow_up_visits == 14

    def test_metrics_visit_completion_rate(self, svc: PatientRegistryService):
        m = svc.get_metrics()
        completed = sum(1 for v in svc.list_visits() if v.status == FollowUpStatus.COMPLETED)
        expected = completed / 14 * 100
        assert abs(m.visit_completion_rate - round(expected, 1)) < 0.2

    def test_metrics_total_outcomes(self, svc: PatientRegistryService):
        m = svc.get_metrics()
        assert m.total_outcomes == 12

    def test_metrics_total_milestones(self, svc: PatientRegistryService):
        m = svc.get_metrics()
        assert m.total_milestones == 10

    def test_metrics_milestones_achieved(self, svc: PatientRegistryService):
        m = svc.get_metrics()
        achieved = sum(1 for ms in svc.list_milestones() if ms.achieved)
        assert m.milestones_achieved == achieved

    def test_metrics_retention_rate(self, svc: PatientRegistryService):
        m = svc.get_metrics()
        # retention_rate = (active + completed) / (total - screened) * 100
        patients = svc.list_patients()
        active = sum(1 for p in patients if p.enrollment_status == EnrollmentStatus.ACTIVE)
        completed = sum(1 for p in patients if p.enrollment_status == EnrollmentStatus.COMPLETED)
        screened = sum(1 for p in patients if p.enrollment_status == EnrollmentStatus.SCREENED)
        denom = len(patients) - screened
        expected = (active + completed) / denom * 100 if denom > 0 else 0
        assert abs(m.retention_rate - round(expected, 1)) < 0.2

    def test_metrics_registries_by_type(self, svc: PatientRegistryService):
        m = svc.get_metrics()
        assert "disease_registry" in m.registries_by_type
        assert m.registries_by_type["disease_registry"] >= 3

    def test_metrics_registries_by_status(self, svc: PatientRegistryService):
        m = svc.get_metrics()
        assert "active" in m.registries_by_status

    def test_metrics_patients_by_status(self, svc: PatientRegistryService):
        m = svc.get_metrics()
        assert "active" in m.patients_by_status

    def test_metrics_visits_by_status(self, svc: PatientRegistryService):
        m = svc.get_metrics()
        assert "completed" in m.visits_by_status

    def test_metrics_outcomes_by_category(self, svc: PatientRegistryService):
        m = svc.get_metrics()
        assert "primary" in m.outcomes_by_category


# ===========================================================================
# REGISTRY API ENDPOINTS
# ===========================================================================


class TestRegistryAPI:
    """Test registry CRUD via HTTP API."""

    @pytest.mark.anyio
    async def test_list_registries(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/registries")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert len(data["items"]) == 10

    @pytest.mark.anyio
    async def test_list_registries_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/registries", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["trial_id"] == EYLEA_TRIAL for r in data["items"])

    @pytest.mark.anyio
    async def test_list_registries_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/registries", params={"registry_type": "post_marketing"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["registry_type"] == "post_marketing" for r in data["items"])

    @pytest.mark.anyio
    async def test_list_registries_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/registries", params={"status": "active"})
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["status"] == "active" for r in data["items"])

    @pytest.mark.anyio
    async def test_get_registry(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/registries/REG-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "REG-001"

    @pytest.mark.anyio
    async def test_get_registry_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/registries/REG-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_registry(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/registries", json=_make_registry_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Registry"
        assert data["status"] == "planning"

    @pytest.mark.anyio
    async def test_update_registry(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/registries/REG-009",
            json={"status": "enrolling", "irb_approved": True},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "enrolling"
        assert resp.json()["irb_approved"] is True

    @pytest.mark.anyio
    async def test_update_registry_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/registries/REG-NONEXISTENT",
            json={"status": "closed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_registry(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/registries/REG-010")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_registry_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/registries/REG-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_registry_with_trial(self, client: AsyncClient):
        payload = _make_registry_create(trial_id=EYLEA_TRIAL, name="Trial-linked Registry")
        resp = await client.post(f"{API_PREFIX}/registries", json=payload)
        assert resp.status_code == 201
        assert resp.json()["trial_id"] == EYLEA_TRIAL


# ===========================================================================
# PATIENT API ENDPOINTS
# ===========================================================================


class TestPatientAPI:
    """Test patient enrollment CRUD via HTTP API."""

    @pytest.mark.anyio
    async def test_list_patients(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12

    @pytest.mark.anyio
    async def test_list_patients_filter_registry(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients", params={"registry_id": "REG-001"})
        assert resp.status_code == 200
        assert all(p["registry_id"] == "REG-001" for p in resp.json()["items"])

    @pytest.mark.anyio
    async def test_list_patients_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients", params={"enrollment_status": "active"})
        assert resp.status_code == 200
        assert all(p["enrollment_status"] == "active" for p in resp.json()["items"])

    @pytest.mark.anyio
    async def test_list_patients_filter_patient_id(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients", params={"patient_id": "PAT-10001"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.anyio
    async def test_get_patient(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/RPAT-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "RPAT-001"

    @pytest.mark.anyio
    async def test_get_patient_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients/RPAT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_patient(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/patients", json=_make_patient_create())
        assert resp.status_code == 201
        assert resp.json()["enrollment_status"] == "screened"

    @pytest.mark.anyio
    async def test_create_patient_invalid_registry(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/patients",
            json=_make_patient_create(registry_id="REG-NONEXISTENT"),
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_patient(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/patients/RPAT-010",
            json={"enrollment_status": "consented"},
        )
        assert resp.status_code == 200
        assert resp.json()["enrollment_status"] == "consented"

    @pytest.mark.anyio
    async def test_update_patient_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/patients/RPAT-NONEXISTENT",
            json={"enrollment_status": "active"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_patient(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/patients/RPAT-010")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_patient_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/patients/RPAT-NONEXISTENT")
        assert resp.status_code == 404


# ===========================================================================
# VISIT API ENDPOINTS
# ===========================================================================


class TestVisitAPI:
    """Test follow-up visit CRUD via HTTP API."""

    @pytest.mark.anyio
    async def test_list_visits(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits")
        assert resp.status_code == 200
        assert resp.json()["total"] == 14

    @pytest.mark.anyio
    async def test_list_visits_filter_patient(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits", params={"registry_patient_id": "RPAT-001"})
        assert resp.status_code == 200
        assert all(v["registry_patient_id"] == "RPAT-001" for v in resp.json()["items"])

    @pytest.mark.anyio
    async def test_list_visits_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits", params={"visit_type": "safety"})
        assert resp.status_code == 200
        assert all(v["visit_type"] == "safety" for v in resp.json()["items"])

    @pytest.mark.anyio
    async def test_list_visits_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits", params={"visit_status": "completed"})
        assert resp.status_code == 200
        assert all(v["status"] == "completed" for v in resp.json()["items"])

    @pytest.mark.anyio
    async def test_get_visit(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits/FUV-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "FUV-001"

    @pytest.mark.anyio
    async def test_get_visit_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits/FUV-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_visit(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/visits", json=_make_visit_create())
        assert resp.status_code == 201
        assert resp.json()["status"] == "scheduled"

    @pytest.mark.anyio
    async def test_create_visit_invalid_patient(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/visits",
            json=_make_visit_create(registry_patient_id="RPAT-NONEXISTENT"),
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_visit(self, client: AsyncClient):
        now = datetime.now(timezone.utc).isoformat()
        resp = await client.put(
            f"{API_PREFIX}/visits/FUV-004",
            json={"status": "completed", "actual_date": now, "data_complete": True},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    @pytest.mark.anyio
    async def test_update_visit_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/visits/FUV-NONEXISTENT",
            json={"status": "cancelled"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_visit(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/visits/FUV-012")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_visit_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/visits/FUV-NONEXISTENT")
        assert resp.status_code == 404


# ===========================================================================
# OUTCOME API ENDPOINTS
# ===========================================================================


class TestOutcomeAPI:
    """Test outcome report CRUD via HTTP API."""

    @pytest.mark.anyio
    async def test_list_outcomes(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/outcomes")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_list_outcomes_filter_patient(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/outcomes", params={"registry_patient_id": "RPAT-001"})
        assert resp.status_code == 200
        assert all(o["registry_patient_id"] == "RPAT-001" for o in resp.json()["items"])

    @pytest.mark.anyio
    async def test_list_outcomes_filter_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/outcomes", params={"category": "primary"})
        assert resp.status_code == 200
        assert all(o["category"] == "primary" for o in resp.json()["items"])

    @pytest.mark.anyio
    async def test_get_outcome(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/outcomes/OUT-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "OUT-001"

    @pytest.mark.anyio
    async def test_get_outcome_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/outcomes/OUT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_outcome(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/outcomes", json=_make_outcome_create())
        assert resp.status_code == 201
        assert resp.json()["outcome_name"] == "Test Outcome"

    @pytest.mark.anyio
    async def test_create_outcome_invalid_patient(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/outcomes",
            json=_make_outcome_create(registry_patient_id="RPAT-NONEXISTENT"),
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_delete_outcome(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/outcomes/OUT-012")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_outcome_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/outcomes/OUT-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_outcome_with_visit(self, client: AsyncClient):
        payload = _make_outcome_create(visit_id="FUV-001")
        resp = await client.post(f"{API_PREFIX}/outcomes", json=payload)
        assert resp.status_code == 201
        assert resp.json()["visit_id"] == "FUV-001"

    @pytest.mark.anyio
    async def test_create_outcome_with_optional_fields(self, client: AsyncClient):
        payload = _make_outcome_create(
            unit="mg/dL",
            baseline_value="100",
            change_from_baseline="-20",
            clinically_significant=True,
        )
        resp = await client.post(f"{API_PREFIX}/outcomes", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["unit"] == "mg/dL"
        assert data["clinically_significant"] is True


# ===========================================================================
# MILESTONE API ENDPOINTS
# ===========================================================================


class TestMilestoneAPI:
    """Test registry milestone CRUD via HTTP API."""

    @pytest.mark.anyio
    async def test_list_milestones(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones")
        assert resp.status_code == 200
        assert resp.json()["total"] == 10

    @pytest.mark.anyio
    async def test_list_milestones_filter_registry(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones", params={"registry_id": "REG-001"})
        assert resp.status_code == 200
        assert all(m["registry_id"] == "REG-001" for m in resp.json()["items"])

    @pytest.mark.anyio
    async def test_get_milestone(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones/RMS-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "RMS-001"
        assert resp.json()["achieved"] is True

    @pytest.mark.anyio
    async def test_get_milestone_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones/RMS-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_milestone(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/milestones", json=_make_milestone_create())
        assert resp.status_code == 201
        assert resp.json()["achieved"] is False

    @pytest.mark.anyio
    async def test_create_milestone_invalid_registry(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/milestones",
            json=_make_milestone_create(registry_id="REG-NONEXISTENT"),
        )
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_milestone(self, client: AsyncClient):
        now = datetime.now(timezone.utc).isoformat()
        resp = await client.put(
            f"{API_PREFIX}/milestones/RMS-004",
            json={"achieved": True, "actual_date": now, "notes": "Completed!"},
        )
        assert resp.status_code == 200
        assert resp.json()["achieved"] is True
        assert resp.json()["notes"] == "Completed!"

    @pytest.mark.anyio
    async def test_update_milestone_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/milestones/RMS-NONEXISTENT",
            json={"achieved": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_milestone(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/milestones/RMS-010")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_milestone_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/milestones/RMS-NONEXISTENT")
        assert resp.status_code == 404


# ===========================================================================
# METRICS API ENDPOINT
# ===========================================================================


class TestMetricsAPI:
    """Test metrics endpoint via HTTP API."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_registries"] == 10
        assert data["total_patients"] == 12
        assert data["total_follow_up_visits"] == 14
        assert data["total_outcomes"] == 12
        assert data["total_milestones"] == 10

    @pytest.mark.anyio
    async def test_metrics_visit_completion_rate_range(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0 <= data["visit_completion_rate"] <= 100

    @pytest.mark.anyio
    async def test_metrics_retention_rate_range(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert 0 <= data["retention_rate"] <= 100

    @pytest.mark.anyio
    async def test_metrics_has_breakdown_dicts(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert isinstance(data["registries_by_type"], dict)
        assert isinstance(data["registries_by_status"], dict)
        assert isinstance(data["patients_by_status"], dict)
        assert isinstance(data["visits_by_status"], dict)
        assert isinstance(data["outcomes_by_category"], dict)


# ===========================================================================
# EDGE CASES & ADDITIONAL COVERAGE
# ===========================================================================


class TestEdgeCases:
    """Test edge cases and additional coverage."""

    def test_singleton_returns_same_instance(self):
        svc1 = get_patient_registry_service()
        svc2 = get_patient_registry_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        svc1 = get_patient_registry_service()
        svc2 = reset_patient_registry_service()
        assert svc1 is not svc2

    def test_list_registries_empty_filter(self, svc: PatientRegistryService):
        result = svc.list_registries(trial_id="NONEXISTENT-TRIAL")
        assert len(result) == 0

    def test_list_patients_empty_filter(self, svc: PatientRegistryService):
        result = svc.list_patients(registry_id="NONEXISTENT-REG")
        assert len(result) == 0

    def test_list_visits_empty_filter(self, svc: PatientRegistryService):
        result = svc.list_visits(registry_patient_id="NONEXISTENT-PAT")
        assert len(result) == 0

    def test_list_outcomes_empty_filter(self, svc: PatientRegistryService):
        result = svc.list_outcomes(registry_patient_id="NONEXISTENT-PAT")
        assert len(result) == 0

    def test_list_milestones_empty_filter(self, svc: PatientRegistryService):
        result = svc.list_milestones(registry_id="NONEXISTENT-REG")
        assert len(result) == 0

    @pytest.mark.anyio
    async def test_create_and_retrieve_registry(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/registries",
            json=_make_registry_create(name="Roundtrip Test"),
        )
        assert resp.status_code == 201
        reg_id = resp.json()["id"]
        resp2 = await client.get(f"{API_PREFIX}/registries/{reg_id}")
        assert resp2.status_code == 200
        assert resp2.json()["name"] == "Roundtrip Test"

    @pytest.mark.anyio
    async def test_create_and_retrieve_patient(self, client: AsyncClient):
        resp = await client.post(
            f"{API_PREFIX}/patients",
            json=_make_patient_create(patient_id="PAT-ROUNDTRIP"),
        )
        assert resp.status_code == 201
        pat_id = resp.json()["id"]
        resp2 = await client.get(f"{API_PREFIX}/patients/{pat_id}")
        assert resp2.status_code == 200
        assert resp2.json()["patient_id"] == "PAT-ROUNDTRIP"

    @pytest.mark.anyio
    async def test_create_and_retrieve_visit(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/visits", json=_make_visit_create())
        assert resp.status_code == 201
        visit_id = resp.json()["id"]
        resp2 = await client.get(f"{API_PREFIX}/visits/{visit_id}")
        assert resp2.status_code == 200

    @pytest.mark.anyio
    async def test_create_and_retrieve_outcome(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/outcomes", json=_make_outcome_create())
        assert resp.status_code == 201
        out_id = resp.json()["id"]
        resp2 = await client.get(f"{API_PREFIX}/outcomes/{out_id}")
        assert resp2.status_code == 200

    @pytest.mark.anyio
    async def test_create_and_retrieve_milestone(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/milestones", json=_make_milestone_create())
        assert resp.status_code == 201
        ms_id = resp.json()["id"]
        resp2 = await client.get(f"{API_PREFIX}/milestones/{ms_id}")
        assert resp2.status_code == 200

    @pytest.mark.anyio
    async def test_delete_then_get_registry(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/registries/REG-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/registries/REG-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_then_get_patient(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/patients/RPAT-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/patients/RPAT-010")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_then_get_visit(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/visits/FUV-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/visits/FUV-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_then_get_outcome(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/outcomes/OUT-012")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/outcomes/OUT-012")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_then_get_milestone(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/milestones/RMS-010")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/milestones/RMS-010")
        assert resp2.status_code == 404

    def test_update_registry_partial(self, svc: PatientRegistryService):
        from app.schemas.patient_registry import RegistryUpdate
        payload = RegistryUpdate(irb_approved=True)
        result = svc.update_registry("REG-009", payload)
        assert result is not None
        assert result.irb_approved is True
        assert result.status == RegistryStatus.PLANNING  # unchanged

    def test_update_patient_partial(self, svc: PatientRegistryService):
        from app.schemas.patient_registry import RegistryPatientUpdate
        payload = RegistryPatientUpdate(notes="Updated note")
        result = svc.update_patient("RPAT-001", payload)
        assert result is not None
        assert result.notes == "Updated note"
        assert result.enrollment_status == EnrollmentStatus.ACTIVE  # unchanged

    def test_update_visit_partial(self, svc: PatientRegistryService):
        from app.schemas.patient_registry import FollowUpVisitUpdate
        payload = FollowUpVisitUpdate(conducted_by="Dr. New")
        result = svc.update_visit("FUV-004", payload)
        assert result is not None
        assert result.conducted_by == "Dr. New"
        assert result.status == FollowUpStatus.SCHEDULED  # unchanged

    def test_update_milestone_partial(self, svc: PatientRegistryService):
        from app.schemas.patient_registry import RegistryMilestoneUpdate
        payload = RegistryMilestoneUpdate(notes="In progress")
        result = svc.update_milestone("RMS-004", payload)
        assert result is not None
        assert result.notes == "In progress"
        assert result.achieved is False  # unchanged

    def test_list_registries_sorted_by_created_at(self, svc: PatientRegistryService):
        result = svc.list_registries()
        for i in range(len(result) - 1):
            assert result[i].created_at >= result[i + 1].created_at

    def test_list_patients_sorted_by_id(self, svc: PatientRegistryService):
        result = svc.list_patients()
        for i in range(len(result) - 1):
            assert result[i].id <= result[i + 1].id

    def test_list_visits_sorted_by_date_desc(self, svc: PatientRegistryService):
        result = svc.list_visits()
        for i in range(len(result) - 1):
            assert result[i].scheduled_date >= result[i + 1].scheduled_date

    def test_list_outcomes_sorted_by_date_desc(self, svc: PatientRegistryService):
        result = svc.list_outcomes()
        for i in range(len(result) - 1):
            assert result[i].reported_date >= result[i + 1].reported_date

    def test_list_milestones_sorted_by_target_date(self, svc: PatientRegistryService):
        result = svc.list_milestones()
        for i in range(len(result) - 1):
            assert result[i].target_date <= result[i + 1].target_date

    def test_registry_pregnancy_type_exists(self, svc: PatientRegistryService):
        result = svc.list_registries(registry_type=RegistryType.PREGNANCY_REGISTRY)
        assert len(result) >= 1

    def test_registry_expanded_access_exists(self, svc: PatientRegistryService):
        result = svc.list_registries(registry_type=RegistryType.EXPANDED_ACCESS)
        assert len(result) >= 1

    def test_registry_product_type_exists(self, svc: PatientRegistryService):
        result = svc.list_registries(registry_type=RegistryType.PRODUCT_REGISTRY)
        assert len(result) >= 1

    def test_patient_enrolled_status(self, svc: PatientRegistryService):
        result = svc.list_patients(enrollment_status=EnrollmentStatus.ENROLLED)
        assert len(result) >= 1

    def test_patient_consented_status(self, svc: PatientRegistryService):
        result = svc.list_patients(enrollment_status=EnrollmentStatus.CONSENTED)
        assert len(result) >= 1

    def test_patient_deceased_status(self, svc: PatientRegistryService):
        result = svc.list_patients(enrollment_status=EnrollmentStatus.DECEASED)
        assert len(result) >= 1

    def test_visit_milestone_type(self, svc: PatientRegistryService):
        result = svc.list_visits(visit_type=FollowUpType.MILESTONE)
        assert len(result) >= 1

    def test_visit_unscheduled_type(self, svc: PatientRegistryService):
        result = svc.list_visits(visit_type=FollowUpType.UNSCHEDULED)
        assert len(result) >= 1

    def test_visit_overdue_status(self, svc: PatientRegistryService):
        result = svc.list_visits(visit_status=FollowUpStatus.OVERDUE)
        assert len(result) >= 1

    def test_visit_missed_status(self, svc: PatientRegistryService):
        result = svc.list_visits(visit_status=FollowUpStatus.MISSED)
        assert len(result) >= 1

    def test_outcome_safety_category(self, svc: PatientRegistryService):
        result = svc.list_outcomes(category=OutcomeCategory.SAFETY)
        assert len(result) >= 1

    def test_outcome_survival_category(self, svc: PatientRegistryService):
        result = svc.list_outcomes(category=OutcomeCategory.SURVIVAL)
        assert len(result) >= 1

    def test_outcome_biomarker_category(self, svc: PatientRegistryService):
        result = svc.list_outcomes(category=OutcomeCategory.BIOMARKER)
        assert len(result) >= 1

    def test_outcome_patient_reported_category(self, svc: PatientRegistryService):
        result = svc.list_outcomes(category=OutcomeCategory.PATIENT_REPORTED)
        assert len(result) >= 1

    def test_closed_registry_exists(self, svc: PatientRegistryService):
        result = svc.list_registries(status=RegistryStatus.CLOSED)
        assert len(result) >= 1

    def test_planning_registry_exists(self, svc: PatientRegistryService):
        result = svc.list_registries(status=RegistryStatus.PLANNING)
        assert len(result) >= 1

    def test_enrolling_registry_exists(self, svc: PatientRegistryService):
        result = svc.list_registries(status=RegistryStatus.ENROLLING)
        assert len(result) >= 1

    def test_follow_up_only_registry_exists(self, svc: PatientRegistryService):
        result = svc.list_registries(status=RegistryStatus.FOLLOW_UP_ONLY)
        assert len(result) >= 1

    @pytest.mark.anyio
    async def test_create_patient_then_visit(self, client: AsyncClient):
        """Test creating a patient then a visit for that patient."""
        resp = await client.post(
            f"{API_PREFIX}/patients",
            json=_make_patient_create(patient_id="PAT-CHAIN"),
        )
        assert resp.status_code == 201
        pat_id = resp.json()["id"]
        resp2 = await client.post(
            f"{API_PREFIX}/visits",
            json=_make_visit_create(registry_patient_id=pat_id),
        )
        assert resp2.status_code == 201
        assert resp2.json()["registry_patient_id"] == pat_id

    @pytest.mark.anyio
    async def test_create_patient_then_outcome(self, client: AsyncClient):
        """Test creating a patient then an outcome for that patient."""
        resp = await client.post(
            f"{API_PREFIX}/patients",
            json=_make_patient_create(patient_id="PAT-CHAIN2"),
        )
        assert resp.status_code == 201
        pat_id = resp.json()["id"]
        resp2 = await client.post(
            f"{API_PREFIX}/outcomes",
            json=_make_outcome_create(registry_patient_id=pat_id),
        )
        assert resp2.status_code == 201

    @pytest.mark.anyio
    async def test_create_registry_then_milestone(self, client: AsyncClient):
        """Test creating a registry then a milestone for it."""
        resp = await client.post(
            f"{API_PREFIX}/registries",
            json=_make_registry_create(name="Chain Registry"),
        )
        assert resp.status_code == 201
        reg_id = resp.json()["id"]
        resp2 = await client.post(
            f"{API_PREFIX}/milestones",
            json=_make_milestone_create(registry_id=reg_id),
        )
        assert resp2.status_code == 201
        assert resp2.json()["registry_id"] == reg_id

    @pytest.mark.anyio
    async def test_create_registry_then_patient(self, client: AsyncClient):
        """Test creating a registry then enrolling a patient."""
        resp = await client.post(
            f"{API_PREFIX}/registries",
            json=_make_registry_create(name="Chain Registry 2"),
        )
        assert resp.status_code == 201
        reg_id = resp.json()["id"]
        resp2 = await client.post(
            f"{API_PREFIX}/patients",
            json=_make_patient_create(registry_id=reg_id, patient_id="PAT-CHAIN3"),
        )
        assert resp2.status_code == 201
        assert resp2.json()["registry_id"] == reg_id

    def test_metrics_after_create(self, svc: PatientRegistryService):
        """Test metrics update correctly after creating new records."""
        m1 = svc.get_metrics()
        from app.schemas.patient_registry import RegistryCreate
        svc.create_registry(RegistryCreate(**_make_registry_create()))
        m2 = svc.get_metrics()
        assert m2.total_registries == m1.total_registries + 1

    def test_metrics_after_delete(self, svc: PatientRegistryService):
        """Test metrics update correctly after deleting records."""
        m1 = svc.get_metrics()
        svc.delete_registry("REG-010")
        m2 = svc.get_metrics()
        assert m2.total_registries == m1.total_registries - 1

    def test_visit_end_of_study_type(self, svc: PatientRegistryService):
        result = svc.list_visits(visit_type=FollowUpType.END_OF_STUDY)
        assert len(result) >= 1

    def test_visit_annual_review_type(self, svc: PatientRegistryService):
        result = svc.list_visits(visit_type=FollowUpType.ANNUAL_REVIEW)
        assert len(result) >= 1

    def test_outcome_secondary_category(self, svc: PatientRegistryService):
        result = svc.list_outcomes(category=OutcomeCategory.SECONDARY)
        assert len(result) >= 1

    def test_registry_has_countries(self, svc: PatientRegistryService):
        reg = svc.get_registry("REG-001")
        assert len(reg.countries) > 0

    def test_registry_has_sites_count(self, svc: PatientRegistryService):
        reg = svc.get_registry("REG-001")
        assert reg.sites_count > 0

    def test_registry_has_follow_up_duration(self, svc: PatientRegistryService):
        reg = svc.get_registry("REG-001")
        assert reg.follow_up_duration_months > 0

    def test_milestone_achieved_and_not(self, svc: PatientRegistryService):
        achieved = [m for m in svc.list_milestones() if m.achieved]
        not_achieved = [m for m in svc.list_milestones() if not m.achieved]
        assert len(achieved) >= 5
        assert len(not_achieved) >= 2

    @pytest.mark.anyio
    async def test_list_registries_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/registries")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 10

    @pytest.mark.anyio
    async def test_list_patients_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/patients")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 12

    @pytest.mark.anyio
    async def test_list_visits_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/visits")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 14

    @pytest.mark.anyio
    async def test_list_outcomes_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/outcomes")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 12

    @pytest.mark.anyio
    async def test_list_milestones_no_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/milestones")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 10
