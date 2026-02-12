"""Tests for Protocol Design & Optimization (PROTO-DESIGN).

Covers:
- Seed data verification (protocols, endpoints, sample calcs, schedules, simulations)
- Protocol Element CRUD (create, read, update, delete, list, filter by trial/phase/status)
- Endpoint Definition CRUD (create, read, update, delete, list, filter by protocol/category)
- Sample Size Calc CRUD (create, read, update, delete, list, filter by protocol)
- Schedule of Assessments CRUD (create, read, update, delete, list, filter by protocol)
- Protocol Simulation CRUD (create, read, update, delete, list, filter by protocol/status)
- Protocol Design Metrics computation
- Error handling (404s, validation errors)
- Edge cases (empty filters, boundary conditions)
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.protocol_design import (
    AssessmentType,
    DesignStatus,
    DesignType,
    EndpointCategory,
    ProtocolPhase,
    SimulationStatus,
)
from app.services.protocol_design_service import (
    ProtocolDesignService,
    get_protocol_design_service,
    reset_protocol_design_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

API_PREFIX = "/api/v1/protocol-design"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_protocol_design_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> ProtocolDesignService:
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


def _make_protocol_create(**overrides) -> dict:
    defaults = {
        "trial_id": EYLEA_TRIAL,
        "protocol_version": "1.0",
        "phase": "phase_3",
        "design_type": "parallel",
        "title": "Test Protocol",
        "indication": "Test Indication",
        "target_population": "Adults >=18",
        "treatment_arms": ["Arm A", "Arm B"],
        "blinding": "double_blind",
        "planned_enrollment": 500,
        "author": "Dr. Test Author",
    }
    defaults.update(overrides)
    return defaults


def _make_endpoint_create(**overrides) -> dict:
    defaults = {
        "protocol_id": "PROTO-001",
        "category": "primary",
        "name": "Test Endpoint",
        "description": "Test description",
        "measurement_tool": "Test Tool",
        "timepoint": "Week 12",
        "statistical_method": "MMRM",
        "clinically_meaningful_difference": None,
    }
    defaults.update(overrides)
    return defaults


def _make_sample_calc_create(**overrides) -> dict:
    defaults = {
        "protocol_id": "PROTO-001",
        "endpoint_id": None,
        "alpha": 0.05,
        "power": 0.80,
        "effect_size": 0.30,
        "dropout_rate_pct": 10.0,
        "sample_per_arm": 100,
        "total_sample": 200,
        "method": "t-test",
        "assumptions": ["Normal distribution", "Equal variance"],
        "calculated_by": "Dr. Test Stats",
    }
    defaults.update(overrides)
    return defaults


def _make_schedule_create(**overrides) -> dict:
    defaults = {
        "protocol_id": "PROTO-001",
        "visit_name": "Test Visit",
        "visit_number": 99,
        "day": 100,
        "window_minus_days": 3,
        "window_plus_days": 3,
        "assessments": ["vital_signs", "lab_work"],
        "mandatory": True,
        "estimated_duration_minutes": 60,
    }
    defaults.update(overrides)
    return defaults


def _make_simulation_create(**overrides) -> dict:
    defaults = {
        "protocol_id": "PROTO-001",
        "simulation_name": "Test Simulation",
        "iterations": 1000,
        "enrollment_rate_per_month": 20.0,
        "dropout_rate_pct": 10.0,
        "effect_size": 0.3,
        "run_by": "Dr. Test Runner",
    }
    defaults.update(overrides)
    return defaults


# ===========================================================================
# SERVICE-LEVEL TESTS: Seed Data Verification
# ===========================================================================


class TestSeedDataProtocols:
    """Verify seeded protocol elements."""

    def test_seed_protocol_count(self, svc: ProtocolDesignService):
        protocols = svc.list_protocols()
        assert len(protocols) == 12

    def test_seed_eylea_protocols(self, svc: ProtocolDesignService):
        protocols = svc.list_protocols(trial_id=EYLEA_TRIAL)
        assert len(protocols) == 4

    def test_seed_dupixent_protocols(self, svc: ProtocolDesignService):
        protocols = svc.list_protocols(trial_id=DUPIXENT_TRIAL)
        assert len(protocols) == 4

    def test_seed_libtayo_protocols(self, svc: ProtocolDesignService):
        protocols = svc.list_protocols(trial_id=LIBTAYO_TRIAL)
        assert len(protocols) == 4

    def test_seed_protocol_001_fields(self, svc: ProtocolDesignService):
        p = svc.get_protocol("PROTO-001")
        assert p is not None
        assert p.trial_id == EYLEA_TRIAL
        assert p.phase == ProtocolPhase.PHASE_3
        assert p.design_type == DesignType.PARALLEL
        assert p.status == DesignStatus.FINALIZED
        assert p.planned_enrollment == 1050
        assert len(p.treatment_arms) == 3
        assert len(p.countries) == 5

    def test_seed_protocol_005_dupixent(self, svc: ProtocolDesignService):
        p = svc.get_protocol("PROTO-005")
        assert p is not None
        assert p.trial_id == DUPIXENT_TRIAL
        assert "Dupixent" in p.title or "LIBERTY" in p.title

    def test_seed_protocol_009_libtayo(self, svc: ProtocolDesignService):
        p = svc.get_protocol("PROTO-009")
        assert p is not None
        assert p.trial_id == LIBTAYO_TRIAL
        assert p.phase == ProtocolPhase.PHASE_3

    def test_seed_protocol_phases_diverse(self, svc: ProtocolDesignService):
        protocols = svc.list_protocols()
        phases = {p.phase for p in protocols}
        assert len(phases) >= 5

    def test_seed_protocol_statuses_diverse(self, svc: ProtocolDesignService):
        protocols = svc.list_protocols()
        statuses = {p.status for p in protocols}
        assert len(statuses) >= 4


class TestSeedDataEndpoints:
    """Verify seeded endpoint definitions."""

    def test_seed_endpoint_count(self, svc: ProtocolDesignService):
        endpoints = svc.list_endpoints()
        assert len(endpoints) == 18

    def test_seed_endpoints_for_proto_001(self, svc: ProtocolDesignService):
        endpoints = svc.list_endpoints(protocol_id="PROTO-001")
        assert len(endpoints) == 4

    def test_seed_endpoints_for_proto_005(self, svc: ProtocolDesignService):
        endpoints = svc.list_endpoints(protocol_id="PROTO-005")
        assert len(endpoints) == 5

    def test_seed_endpoint_categories(self, svc: ProtocolDesignService):
        endpoints = svc.list_endpoints()
        cats = {e.category for e in endpoints}
        assert EndpointCategory.PRIMARY in cats
        assert EndpointCategory.SECONDARY in cats
        assert EndpointCategory.SAFETY in cats

    def test_seed_endpoint_001_details(self, svc: ProtocolDesignService):
        e = svc.get_endpoint("EP-001")
        assert e is not None
        assert e.protocol_id == "PROTO-001"
        assert e.category == EndpointCategory.PRIMARY
        assert "BCVA" in e.name


class TestSeedDataSampleCalcs:
    """Verify seeded sample size calculations."""

    def test_seed_sample_calc_count(self, svc: ProtocolDesignService):
        calcs = svc.list_sample_calcs()
        assert len(calcs) == 12

    def test_seed_calcs_for_proto_001(self, svc: ProtocolDesignService):
        calcs = svc.list_sample_calcs(protocol_id="PROTO-001")
        assert len(calcs) == 1

    def test_seed_calc_001_details(self, svc: ProtocolDesignService):
        c = svc.get_sample_calc("SSC-001")
        assert c is not None
        assert c.protocol_id == "PROTO-001"
        assert c.alpha == 0.025
        assert c.power == 0.90
        assert c.total_sample == 1050


class TestSeedDataSchedules:
    """Verify seeded schedule of assessments."""

    def test_seed_schedule_count(self, svc: ProtocolDesignService):
        schedules = svc.list_schedules()
        assert len(schedules) == 15

    def test_seed_schedules_for_proto_001(self, svc: ProtocolDesignService):
        schedules = svc.list_schedules(protocol_id="PROTO-001")
        assert len(schedules) == 5

    def test_seed_schedule_001_details(self, svc: ProtocolDesignService):
        s = svc.get_schedule("SOA-001")
        assert s is not None
        assert s.protocol_id == "PROTO-001"
        assert s.visit_name == "Screening"
        assert s.mandatory is True
        assert len(s.assessments) >= 3


class TestSeedDataSimulations:
    """Verify seeded protocol simulations."""

    def test_seed_simulation_count(self, svc: ProtocolDesignService):
        sims = svc.list_simulations()
        assert len(sims) == 12

    def test_seed_simulations_for_proto_001(self, svc: ProtocolDesignService):
        sims = svc.list_simulations(protocol_id="PROTO-001")
        assert len(sims) == 3

    def test_seed_simulation_001_details(self, svc: ProtocolDesignService):
        s = svc.get_simulation("SIM-001")
        assert s is not None
        assert s.protocol_id == "PROTO-001"
        assert s.status == SimulationStatus.COMPLETED
        assert s.predicted_power == 0.92
        assert s.success_probability_pct == 88.5

    def test_seed_simulation_statuses(self, svc: ProtocolDesignService):
        sims = svc.list_simulations()
        statuses = {s.status for s in sims}
        assert SimulationStatus.COMPLETED in statuses
        assert SimulationStatus.RUNNING in statuses
        assert SimulationStatus.CONFIGURED in statuses
        assert SimulationStatus.FAILED in statuses


# ===========================================================================
# SERVICE-LEVEL TESTS: Protocol CRUD
# ===========================================================================


class TestProtocolCRUD:
    """Test protocol element CRUD operations at the service level."""

    def test_create_protocol(self, svc: ProtocolDesignService):
        payload = ProtocolDesignService  # not used, direct call
        from app.schemas.protocol_design import ProtocolElementCreate
        p = svc.create_protocol(ProtocolElementCreate(**_make_protocol_create()))
        assert p.id.startswith("PROTO-")
        assert p.trial_id == EYLEA_TRIAL
        assert p.status == DesignStatus.CONCEPT

    def test_get_protocol_exists(self, svc: ProtocolDesignService):
        p = svc.get_protocol("PROTO-001")
        assert p is not None
        assert p.id == "PROTO-001"

    def test_get_protocol_not_found(self, svc: ProtocolDesignService):
        assert svc.get_protocol("NONEXISTENT") is None

    def test_update_protocol(self, svc: ProtocolDesignService):
        from app.schemas.protocol_design import ProtocolElementUpdate
        updated = svc.update_protocol("PROTO-001", ProtocolElementUpdate(
            status=DesignStatus.AMENDED,
            planned_enrollment=1200,
        ))
        assert updated is not None
        assert updated.status == DesignStatus.AMENDED
        assert updated.planned_enrollment == 1200

    def test_update_protocol_not_found(self, svc: ProtocolDesignService):
        from app.schemas.protocol_design import ProtocolElementUpdate
        assert svc.update_protocol("NONEXISTENT", ProtocolElementUpdate(status=DesignStatus.DRAFT)) is None

    def test_delete_protocol(self, svc: ProtocolDesignService):
        assert svc.delete_protocol("PROTO-001") is True
        assert svc.get_protocol("PROTO-001") is None

    def test_delete_protocol_not_found(self, svc: ProtocolDesignService):
        assert svc.delete_protocol("NONEXISTENT") is False

    def test_list_protocols_filter_by_phase(self, svc: ProtocolDesignService):
        phase3 = svc.list_protocols(phase=ProtocolPhase.PHASE_3)
        assert len(phase3) >= 4
        for p in phase3:
            assert p.phase == ProtocolPhase.PHASE_3

    def test_list_protocols_filter_by_status(self, svc: ProtocolDesignService):
        finalized = svc.list_protocols(status=DesignStatus.FINALIZED)
        assert len(finalized) >= 3
        for p in finalized:
            assert p.status == DesignStatus.FINALIZED

    def test_list_protocols_filter_combined(self, svc: ProtocolDesignService):
        result = svc.list_protocols(
            trial_id=EYLEA_TRIAL, phase=ProtocolPhase.PHASE_3,
        )
        for p in result:
            assert p.trial_id == EYLEA_TRIAL
            assert p.phase == ProtocolPhase.PHASE_3

    def test_list_protocols_empty_result(self, svc: ProtocolDesignService):
        result = svc.list_protocols(trial_id="nonexistent-trial-id")
        assert result == []


# ===========================================================================
# SERVICE-LEVEL TESTS: Endpoint CRUD
# ===========================================================================


class TestEndpointCRUD:
    """Test endpoint definition CRUD operations."""

    def test_create_endpoint(self, svc: ProtocolDesignService):
        from app.schemas.protocol_design import EndpointDefinitionCreate
        e = svc.create_endpoint(EndpointDefinitionCreate(**_make_endpoint_create()))
        assert e.id.startswith("EP-")
        assert e.category == EndpointCategory.PRIMARY

    def test_get_endpoint_exists(self, svc: ProtocolDesignService):
        e = svc.get_endpoint("EP-001")
        assert e is not None

    def test_get_endpoint_not_found(self, svc: ProtocolDesignService):
        assert svc.get_endpoint("NONEXISTENT") is None

    def test_update_endpoint(self, svc: ProtocolDesignService):
        updated = svc.update_endpoint("EP-001", {"name": "Updated BCVA Endpoint"})
        assert updated is not None
        assert updated.name == "Updated BCVA Endpoint"

    def test_update_endpoint_not_found(self, svc: ProtocolDesignService):
        assert svc.update_endpoint("NONEXISTENT", {"name": "x"}) is None

    def test_delete_endpoint(self, svc: ProtocolDesignService):
        assert svc.delete_endpoint("EP-001") is True
        assert svc.get_endpoint("EP-001") is None

    def test_delete_endpoint_not_found(self, svc: ProtocolDesignService):
        assert svc.delete_endpoint("NONEXISTENT") is False

    def test_list_endpoints_filter_by_protocol(self, svc: ProtocolDesignService):
        result = svc.list_endpoints(protocol_id="PROTO-001")
        for e in result:
            assert e.protocol_id == "PROTO-001"

    def test_list_endpoints_filter_by_category(self, svc: ProtocolDesignService):
        result = svc.list_endpoints(category=EndpointCategory.PRIMARY)
        assert len(result) >= 4
        for e in result:
            assert e.category == EndpointCategory.PRIMARY

    def test_list_endpoints_empty_result(self, svc: ProtocolDesignService):
        result = svc.list_endpoints(protocol_id="NONEXISTENT")
        assert result == []


# ===========================================================================
# SERVICE-LEVEL TESTS: Sample Size Calc CRUD
# ===========================================================================


class TestSampleCalcCRUD:
    """Test sample size calculation CRUD operations."""

    def test_create_sample_calc(self, svc: ProtocolDesignService):
        from app.schemas.protocol_design import SampleSizeCalcCreate
        c = svc.create_sample_calc(SampleSizeCalcCreate(**_make_sample_calc_create()))
        assert c.id.startswith("SSC-")
        assert c.total_sample == 200

    def test_get_sample_calc_exists(self, svc: ProtocolDesignService):
        c = svc.get_sample_calc("SSC-001")
        assert c is not None

    def test_get_sample_calc_not_found(self, svc: ProtocolDesignService):
        assert svc.get_sample_calc("NONEXISTENT") is None

    def test_update_sample_calc(self, svc: ProtocolDesignService):
        updated = svc.update_sample_calc("SSC-001", {"total_sample": 1200})
        assert updated is not None
        assert updated.total_sample == 1200

    def test_update_sample_calc_not_found(self, svc: ProtocolDesignService):
        assert svc.update_sample_calc("NONEXISTENT", {"total_sample": 1}) is None

    def test_delete_sample_calc(self, svc: ProtocolDesignService):
        assert svc.delete_sample_calc("SSC-001") is True
        assert svc.get_sample_calc("SSC-001") is None

    def test_delete_sample_calc_not_found(self, svc: ProtocolDesignService):
        assert svc.delete_sample_calc("NONEXISTENT") is False

    def test_list_sample_calcs_filter_by_protocol(self, svc: ProtocolDesignService):
        result = svc.list_sample_calcs(protocol_id="PROTO-005")
        assert len(result) == 2
        for c in result:
            assert c.protocol_id == "PROTO-005"

    def test_list_sample_calcs_empty_result(self, svc: ProtocolDesignService):
        result = svc.list_sample_calcs(protocol_id="NONEXISTENT")
        assert result == []


# ===========================================================================
# SERVICE-LEVEL TESTS: Schedule of Assessments CRUD
# ===========================================================================


class TestScheduleCRUD:
    """Test schedule of assessments CRUD operations."""

    def test_create_schedule(self, svc: ProtocolDesignService):
        from app.schemas.protocol_design import ScheduleOfAssessmentsCreate
        s = svc.create_schedule(ScheduleOfAssessmentsCreate(**_make_schedule_create()))
        assert s.id.startswith("SOA-")
        assert s.visit_name == "Test Visit"

    def test_get_schedule_exists(self, svc: ProtocolDesignService):
        s = svc.get_schedule("SOA-001")
        assert s is not None

    def test_get_schedule_not_found(self, svc: ProtocolDesignService):
        assert svc.get_schedule("NONEXISTENT") is None

    def test_update_schedule(self, svc: ProtocolDesignService):
        updated = svc.update_schedule("SOA-001", {"visit_name": "Updated Screening"})
        assert updated is not None
        assert updated.visit_name == "Updated Screening"

    def test_update_schedule_not_found(self, svc: ProtocolDesignService):
        assert svc.update_schedule("NONEXISTENT", {"visit_name": "x"}) is None

    def test_delete_schedule(self, svc: ProtocolDesignService):
        assert svc.delete_schedule("SOA-001") is True
        assert svc.get_schedule("SOA-001") is None

    def test_delete_schedule_not_found(self, svc: ProtocolDesignService):
        assert svc.delete_schedule("NONEXISTENT") is False

    def test_list_schedules_filter_by_protocol(self, svc: ProtocolDesignService):
        result = svc.list_schedules(protocol_id="PROTO-005")
        assert len(result) == 4
        for s in result:
            assert s.protocol_id == "PROTO-005"

    def test_list_schedules_empty_result(self, svc: ProtocolDesignService):
        result = svc.list_schedules(protocol_id="NONEXISTENT")
        assert result == []

    def test_list_schedules_sorted_by_visit_number(self, svc: ProtocolDesignService):
        result = svc.list_schedules(protocol_id="PROTO-001")
        visit_numbers = [s.visit_number for s in result]
        assert visit_numbers == sorted(visit_numbers)


# ===========================================================================
# SERVICE-LEVEL TESTS: Simulation CRUD
# ===========================================================================


class TestSimulationCRUD:
    """Test protocol simulation CRUD operations."""

    def test_create_simulation(self, svc: ProtocolDesignService):
        from app.schemas.protocol_design import ProtocolSimulationCreate
        s = svc.create_simulation(ProtocolSimulationCreate(**_make_simulation_create()))
        assert s.id.startswith("SIM-")
        assert s.status == SimulationStatus.CONFIGURED

    def test_get_simulation_exists(self, svc: ProtocolDesignService):
        s = svc.get_simulation("SIM-001")
        assert s is not None

    def test_get_simulation_not_found(self, svc: ProtocolDesignService):
        assert svc.get_simulation("NONEXISTENT") is None

    def test_update_simulation(self, svc: ProtocolDesignService):
        from app.schemas.protocol_design import ProtocolSimulationUpdate
        updated = svc.update_simulation("SIM-006", ProtocolSimulationUpdate(
            status=SimulationStatus.COMPLETED,
            predicted_power=0.85,
            predicted_duration_months=20.0,
        ))
        assert updated is not None
        assert updated.status == SimulationStatus.COMPLETED
        assert updated.predicted_power == 0.85

    def test_update_simulation_not_found(self, svc: ProtocolDesignService):
        from app.schemas.protocol_design import ProtocolSimulationUpdate
        assert svc.update_simulation("NONEXISTENT", ProtocolSimulationUpdate(status=SimulationStatus.COMPLETED)) is None

    def test_delete_simulation(self, svc: ProtocolDesignService):
        assert svc.delete_simulation("SIM-001") is True
        assert svc.get_simulation("SIM-001") is None

    def test_delete_simulation_not_found(self, svc: ProtocolDesignService):
        assert svc.delete_simulation("NONEXISTENT") is False

    def test_list_simulations_filter_by_protocol(self, svc: ProtocolDesignService):
        result = svc.list_simulations(protocol_id="PROTO-001")
        assert len(result) == 3
        for s in result:
            assert s.protocol_id == "PROTO-001"

    def test_list_simulations_filter_by_status(self, svc: ProtocolDesignService):
        result = svc.list_simulations(status=SimulationStatus.COMPLETED)
        assert len(result) >= 7
        for s in result:
            assert s.status == SimulationStatus.COMPLETED

    def test_list_simulations_empty_result(self, svc: ProtocolDesignService):
        result = svc.list_simulations(protocol_id="NONEXISTENT")
        assert result == []


# ===========================================================================
# SERVICE-LEVEL TESTS: Metrics
# ===========================================================================


class TestMetrics:
    """Test protocol design metrics computation."""

    def test_metrics_total_protocols(self, svc: ProtocolDesignService):
        m = svc.get_metrics()
        assert m.total_protocols == 12

    def test_metrics_total_endpoints(self, svc: ProtocolDesignService):
        m = svc.get_metrics()
        assert m.total_endpoints == 18

    def test_metrics_total_sample_calcs(self, svc: ProtocolDesignService):
        m = svc.get_metrics()
        assert m.total_sample_calcs == 12

    def test_metrics_total_schedule_visits(self, svc: ProtocolDesignService):
        m = svc.get_metrics()
        assert m.total_schedule_visits == 15

    def test_metrics_total_simulations(self, svc: ProtocolDesignService):
        m = svc.get_metrics()
        assert m.total_simulations == 12

    def test_metrics_protocols_by_phase(self, svc: ProtocolDesignService):
        m = svc.get_metrics()
        assert "phase_3" in m.protocols_by_phase
        assert m.protocols_by_phase["phase_3"] >= 4

    def test_metrics_protocols_by_design(self, svc: ProtocolDesignService):
        m = svc.get_metrics()
        assert "parallel" in m.protocols_by_design

    def test_metrics_protocols_by_status(self, svc: ProtocolDesignService):
        m = svc.get_metrics()
        assert "finalized" in m.protocols_by_status

    def test_metrics_endpoints_by_category(self, svc: ProtocolDesignService):
        m = svc.get_metrics()
        assert "primary" in m.endpoints_by_category

    def test_metrics_simulations_by_status(self, svc: ProtocolDesignService):
        m = svc.get_metrics()
        assert "completed" in m.simulations_by_status

    def test_metrics_avg_visit_duration(self, svc: ProtocolDesignService):
        m = svc.get_metrics()
        assert m.avg_visit_duration_minutes > 0

    def test_metrics_avg_predicted_power(self, svc: ProtocolDesignService):
        m = svc.get_metrics()
        assert m.avg_predicted_power is not None
        assert 0.0 < m.avg_predicted_power <= 1.0


# ===========================================================================
# API-LEVEL TESTS: Protocol Endpoints
# ===========================================================================


class TestProtocolAPI:
    """Test protocol element API endpoints."""

    @pytest.mark.anyio
    async def test_list_protocols(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/protocols")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 12
        assert len(data["items"]) == 12

    @pytest.mark.anyio
    async def test_list_protocols_filter_trial(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/protocols", params={"trial_id": EYLEA_TRIAL})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4

    @pytest.mark.anyio
    async def test_list_protocols_filter_phase(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/protocols", params={"phase": "phase_3"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["phase"] == "phase_3"

    @pytest.mark.anyio
    async def test_list_protocols_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/protocols", params={"status": "finalized"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["status"] == "finalized"

    @pytest.mark.anyio
    async def test_get_protocol(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/protocols/PROTO-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PROTO-001"
        assert data["trial_id"] == EYLEA_TRIAL

    @pytest.mark.anyio
    async def test_get_protocol_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/protocols/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_protocol(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/protocols", json=_make_protocol_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("PROTO-")
        assert data["status"] == "concept"

    @pytest.mark.anyio
    async def test_create_protocol_minimal(self, client: AsyncClient):
        payload = {
            "trial_id": EYLEA_TRIAL,
            "protocol_version": "1.0",
            "phase": "phase_1",
            "design_type": "single_arm",
            "title": "Minimal Protocol",
            "indication": "Test",
            "target_population": "Adults",
            "author": "Dr. Test",
        }
        resp = await client.post(f"{API_PREFIX}/protocols", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_update_protocol(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/protocols/PROTO-001",
            json={"status": "amended", "planned_enrollment": 1200},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "amended"
        assert data["planned_enrollment"] == 1200

    @pytest.mark.anyio
    async def test_update_protocol_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/protocols/NONEXISTENT",
            json={"status": "draft"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_protocol(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/protocols/PROTO-001")
        assert resp.status_code == 204
        # Verify deleted
        resp2 = await client.get(f"{API_PREFIX}/protocols/PROTO-001")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_protocol_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/protocols/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_and_retrieve_protocol(self, client: AsyncClient):
        create_resp = await client.post(f"{API_PREFIX}/protocols", json=_make_protocol_create(
            title="Roundtrip Test Protocol",
        ))
        assert create_resp.status_code == 201
        created_id = create_resp.json()["id"]
        get_resp = await client.get(f"{API_PREFIX}/protocols/{created_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == "Roundtrip Test Protocol"

    @pytest.mark.anyio
    async def test_list_protocols_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/protocols", params={"trial_id": "no-such-trial"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_update_protocol_partial(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/protocols/PROTO-001",
            json={"countries": ["US", "UK", "DE", "JP", "AU", "CA"]},
        )
        assert resp.status_code == 200
        assert len(resp.json()["countries"]) == 6


# ===========================================================================
# API-LEVEL TESTS: Endpoint Definition Endpoints
# ===========================================================================


class TestEndpointAPI:
    """Test endpoint definition API endpoints."""

    @pytest.mark.anyio
    async def test_list_endpoints(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/endpoints")
        assert resp.status_code == 200
        assert resp.json()["total"] == 18

    @pytest.mark.anyio
    async def test_list_endpoints_filter_protocol(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/endpoints", params={"protocol_id": "PROTO-001"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 4

    @pytest.mark.anyio
    async def test_list_endpoints_filter_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/endpoints", params={"category": "primary"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["category"] == "primary"

    @pytest.mark.anyio
    async def test_get_endpoint(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/endpoints/EP-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "EP-001"

    @pytest.mark.anyio
    async def test_get_endpoint_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/endpoints/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_endpoint(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/endpoints", json=_make_endpoint_create())
        assert resp.status_code == 201
        assert resp.json()["id"].startswith("EP-")

    @pytest.mark.anyio
    async def test_update_endpoint(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/endpoints/EP-001",
            json={"name": "Updated BCVA Endpoint", "id": "EP-001", "protocol_id": "PROTO-001",
                  "category": "primary", "description": "Updated", "measurement_tool": "ETDRS Chart",
                  "timepoint": "Week 48", "statistical_method": "MMRM"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated BCVA Endpoint"

    @pytest.mark.anyio
    async def test_update_endpoint_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/endpoints/NONEXISTENT",
            json={"name": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_endpoint(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/endpoints/EP-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_endpoint_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/endpoints/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_endpoints_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/endpoints", params={"protocol_id": "NONEXISTENT"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_create_and_delete_endpoint(self, client: AsyncClient):
        create_resp = await client.post(f"{API_PREFIX}/endpoints", json=_make_endpoint_create())
        assert create_resp.status_code == 201
        eid = create_resp.json()["id"]
        del_resp = await client.delete(f"{API_PREFIX}/endpoints/{eid}")
        assert del_resp.status_code == 204
        get_resp = await client.get(f"{API_PREFIX}/endpoints/{eid}")
        assert get_resp.status_code == 404


# ===========================================================================
# API-LEVEL TESTS: Sample Size Calc Endpoints
# ===========================================================================


class TestSampleCalcAPI:
    """Test sample size calculation API endpoints."""

    @pytest.mark.anyio
    async def test_list_sample_calcs(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sample-calcs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_list_sample_calcs_filter_protocol(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sample-calcs", params={"protocol_id": "PROTO-005"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    @pytest.mark.anyio
    async def test_get_sample_calc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sample-calcs/SSC-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "SSC-001"

    @pytest.mark.anyio
    async def test_get_sample_calc_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sample-calcs/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_sample_calc(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/sample-calcs", json=_make_sample_calc_create())
        assert resp.status_code == 201
        assert resp.json()["id"].startswith("SSC-")

    @pytest.mark.anyio
    async def test_update_sample_calc(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sample-calcs/SSC-001",
            json={"total_sample": 1200, "id": "SSC-001", "protocol_id": "PROTO-001",
                  "alpha": 0.025, "power": 0.90, "method": "MMRM with non-inferiority margin",
                  "calculated_by": "Dr. Robert Statman",
                  "calculation_date": datetime.now(timezone.utc).isoformat()},
        )
        assert resp.status_code == 200
        assert resp.json()["total_sample"] == 1200

    @pytest.mark.anyio
    async def test_update_sample_calc_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/sample-calcs/NONEXISTENT",
            json={"total_sample": 1},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_sample_calc(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sample-calcs/SSC-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_sample_calc_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/sample-calcs/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_sample_calcs_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/sample-calcs", params={"protocol_id": "NONEXISTENT"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_create_and_retrieve_sample_calc(self, client: AsyncClient):
        create_resp = await client.post(f"{API_PREFIX}/sample-calcs", json=_make_sample_calc_create(
            method="Custom Power Analysis",
        ))
        assert create_resp.status_code == 201
        cid = create_resp.json()["id"]
        get_resp = await client.get(f"{API_PREFIX}/sample-calcs/{cid}")
        assert get_resp.status_code == 200
        assert get_resp.json()["method"] == "Custom Power Analysis"


# ===========================================================================
# API-LEVEL TESTS: Schedule of Assessments Endpoints
# ===========================================================================


class TestScheduleAPI:
    """Test schedule of assessments API endpoints."""

    @pytest.mark.anyio
    async def test_list_schedules(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules")
        assert resp.status_code == 200
        assert resp.json()["total"] == 15

    @pytest.mark.anyio
    async def test_list_schedules_filter_protocol(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules", params={"protocol_id": "PROTO-001"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 5

    @pytest.mark.anyio
    async def test_get_schedule(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules/SOA-001")
        assert resp.status_code == 200
        assert resp.json()["id"] == "SOA-001"

    @pytest.mark.anyio
    async def test_get_schedule_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_schedule(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/schedules", json=_make_schedule_create())
        assert resp.status_code == 201
        assert resp.json()["id"].startswith("SOA-")

    @pytest.mark.anyio
    async def test_update_schedule(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/schedules/SOA-001",
            json={"visit_name": "Updated Screening", "id": "SOA-001",
                  "protocol_id": "PROTO-001", "visit_number": 0, "day": -28},
        )
        assert resp.status_code == 200
        assert resp.json()["visit_name"] == "Updated Screening"

    @pytest.mark.anyio
    async def test_update_schedule_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/schedules/NONEXISTENT",
            json={"visit_name": "x"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_schedule(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/schedules/SOA-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_schedule_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/schedules/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_schedules_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/schedules", params={"protocol_id": "NONEXISTENT"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_create_schedule_with_assessments(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/schedules", json=_make_schedule_create(
            assessments=["physical_exam", "vital_signs", "lab_work", "ecg"],
        ))
        assert resp.status_code == 201
        assert len(resp.json()["assessments"]) == 4

    @pytest.mark.anyio
    async def test_create_and_delete_schedule(self, client: AsyncClient):
        create_resp = await client.post(f"{API_PREFIX}/schedules", json=_make_schedule_create())
        assert create_resp.status_code == 201
        sid = create_resp.json()["id"]
        del_resp = await client.delete(f"{API_PREFIX}/schedules/{sid}")
        assert del_resp.status_code == 204
        get_resp = await client.get(f"{API_PREFIX}/schedules/{sid}")
        assert get_resp.status_code == 404


# ===========================================================================
# API-LEVEL TESTS: Protocol Simulation Endpoints
# ===========================================================================


class TestSimulationAPI:
    """Test protocol simulation API endpoints."""

    @pytest.mark.anyio
    async def test_list_simulations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/simulations")
        assert resp.status_code == 200
        assert resp.json()["total"] == 12

    @pytest.mark.anyio
    async def test_list_simulations_filter_protocol(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/simulations", params={"protocol_id": "PROTO-001"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 3

    @pytest.mark.anyio
    async def test_list_simulations_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/simulations", params={"status": "completed"})
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_get_simulation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/simulations/SIM-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SIM-001"
        assert data["predicted_power"] == 0.92

    @pytest.mark.anyio
    async def test_get_simulation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/simulations/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_simulation(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/simulations", json=_make_simulation_create())
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"].startswith("SIM-")
        assert data["status"] == "configured"

    @pytest.mark.anyio
    async def test_update_simulation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/simulations/SIM-006",
            json={"status": "completed", "predicted_power": 0.85},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["predicted_power"] == 0.85

    @pytest.mark.anyio
    async def test_update_simulation_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/simulations/NONEXISTENT",
            json={"status": "completed"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_simulation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/simulations/SIM-001")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_delete_simulation_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/simulations/NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_list_simulations_empty_filter(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/simulations", params={"protocol_id": "NONEXISTENT"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.anyio
    async def test_create_and_retrieve_simulation(self, client: AsyncClient):
        create_resp = await client.post(f"{API_PREFIX}/simulations", json=_make_simulation_create(
            simulation_name="Roundtrip Test Sim",
        ))
        assert create_resp.status_code == 201
        sid = create_resp.json()["id"]
        get_resp = await client.get(f"{API_PREFIX}/simulations/{sid}")
        assert get_resp.status_code == 200
        assert get_resp.json()["simulation_name"] == "Roundtrip Test Sim"

    @pytest.mark.anyio
    async def test_update_simulation_partial(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/simulations/SIM-010",
            json={"predicted_cost": 15000000.0},
        )
        assert resp.status_code == 200
        assert resp.json()["predicted_cost"] == 15000000.0
        # Verify status unchanged
        assert resp.json()["status"] == "configured"


# ===========================================================================
# API-LEVEL TESTS: Metrics Endpoint
# ===========================================================================


class TestMetricsAPI:
    """Test metrics API endpoint."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_protocols"] == 12
        assert data["total_endpoints"] == 18
        assert data["total_sample_calcs"] == 12
        assert data["total_schedule_visits"] == 15
        assert data["total_simulations"] == 12

    @pytest.mark.anyio
    async def test_metrics_has_breakdowns(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert len(data["protocols_by_phase"]) >= 5
        assert len(data["protocols_by_design"]) >= 4
        assert len(data["protocols_by_status"]) >= 4
        assert len(data["endpoints_by_category"]) >= 4
        assert len(data["simulations_by_status"]) >= 3

    @pytest.mark.anyio
    async def test_metrics_avg_visit_duration(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_visit_duration_minutes"] > 0

    @pytest.mark.anyio
    async def test_metrics_avg_predicted_power(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["avg_predicted_power"] is not None
        assert 0.0 < data["avg_predicted_power"] <= 1.0

    @pytest.mark.anyio
    async def test_metrics_after_delete(self, client: AsyncClient):
        # Delete a protocol and verify metrics update
        await client.delete(f"{API_PREFIX}/protocols/PROTO-001")
        resp = await client.get(f"{API_PREFIX}/metrics")
        data = resp.json()
        assert data["total_protocols"] == 11


# ===========================================================================
# EDGE CASES & VALIDATION
# ===========================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.anyio
    async def test_create_protocol_with_empty_arms(self, client: AsyncClient):
        payload = _make_protocol_create(treatment_arms=[])
        resp = await client.post(f"{API_PREFIX}/protocols", json=payload)
        assert resp.status_code == 201
        assert resp.json()["treatment_arms"] == []

    @pytest.mark.anyio
    async def test_create_protocol_zero_enrollment(self, client: AsyncClient):
        payload = _make_protocol_create(planned_enrollment=0)
        resp = await client.post(f"{API_PREFIX}/protocols", json=payload)
        assert resp.status_code == 201
        assert resp.json()["planned_enrollment"] == 0

    @pytest.mark.anyio
    async def test_create_sample_calc_boundary_alpha(self, client: AsyncClient):
        payload = _make_sample_calc_create(alpha=0.0, power=1.0)
        resp = await client.post(f"{API_PREFIX}/sample-calcs", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_create_simulation_min_iterations(self, client: AsyncClient):
        payload = _make_simulation_create(iterations=1)
        resp = await client.post(f"{API_PREFIX}/simulations", json=payload)
        assert resp.status_code == 201
        assert resp.json()["iterations"] == 1

    @pytest.mark.anyio
    async def test_create_schedule_negative_day(self, client: AsyncClient):
        payload = _make_schedule_create(day=-28, visit_number=0, visit_name="Screening")
        resp = await client.post(f"{API_PREFIX}/schedules", json=payload)
        assert resp.status_code == 201
        assert resp.json()["day"] == -28

    @pytest.mark.anyio
    async def test_create_schedule_zero_window(self, client: AsyncClient):
        payload = _make_schedule_create(window_minus_days=0, window_plus_days=0)
        resp = await client.post(f"{API_PREFIX}/schedules", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_multiple_creates_unique_ids(self, client: AsyncClient):
        ids = set()
        for i in range(5):
            resp = await client.post(f"{API_PREFIX}/protocols", json=_make_protocol_create(
                title=f"Protocol {i}",
            ))
            assert resp.status_code == 201
            ids.add(resp.json()["id"])
        assert len(ids) == 5

    @pytest.mark.anyio
    async def test_delete_then_create_same_fields(self, client: AsyncClient):
        await client.delete(f"{API_PREFIX}/protocols/PROTO-001")
        resp = await client.post(f"{API_PREFIX}/protocols", json=_make_protocol_create(
            title="Replacement Protocol",
        ))
        assert resp.status_code == 201
        assert resp.json()["id"] != "PROTO-001"  # New ID generated

    @pytest.mark.anyio
    async def test_update_protocol_no_fields(self, client: AsyncClient):
        resp = await client.put(f"{API_PREFIX}/protocols/PROTO-001", json={})
        assert resp.status_code == 200
        # Should return unchanged protocol
        assert resp.json()["id"] == "PROTO-001"

    @pytest.mark.anyio
    async def test_simulation_update_only_cost(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/simulations/SIM-001",
            json={"predicted_cost": 200000000.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["predicted_cost"] == 200000000.0
        # Other fields remain unchanged
        assert data["predicted_power"] == 0.92

    def test_service_singleton(self):
        svc1 = get_protocol_design_service()
        svc2 = get_protocol_design_service()
        assert svc1 is svc2

    def test_service_reset_creates_new_instance(self):
        svc1 = get_protocol_design_service()
        svc2 = reset_protocol_design_service()
        assert svc1 is not svc2

    @pytest.mark.anyio
    async def test_list_all_protocols_after_bulk_create(self, client: AsyncClient):
        for i in range(3):
            resp = await client.post(f"{API_PREFIX}/protocols", json=_make_protocol_create(
                title=f"Bulk Protocol {i}",
            ))
            assert resp.status_code == 201
        resp = await client.get(f"{API_PREFIX}/protocols")
        assert resp.json()["total"] == 15  # 12 seed + 3 created

    @pytest.mark.anyio
    async def test_endpoint_filter_by_both_protocol_and_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/endpoints", params={
            "protocol_id": "PROTO-001",
            "category": "primary",
        })
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["protocol_id"] == "PROTO-001"
            assert item["category"] == "primary"

    @pytest.mark.anyio
    async def test_simulation_filter_combined(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/simulations", params={
            "protocol_id": "PROTO-001",
            "status": "completed",
        })
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["protocol_id"] == "PROTO-001"
            assert item["status"] == "completed"

    @pytest.mark.anyio
    async def test_create_endpoint_all_categories(self, client: AsyncClient):
        """Verify all endpoint categories can be created."""
        for cat in ["primary", "secondary", "exploratory", "safety", "pharmacokinetic", "biomarker", "patient_reported"]:
            resp = await client.post(f"{API_PREFIX}/endpoints", json=_make_endpoint_create(category=cat))
            assert resp.status_code == 201
            assert resp.json()["category"] == cat

    @pytest.mark.anyio
    async def test_create_protocol_all_phases(self, client: AsyncClient):
        """Verify all protocol phases can be created."""
        for phase in ["phase_1", "phase_1b", "phase_2", "phase_2b", "phase_3", "phase_3b", "phase_4"]:
            resp = await client.post(f"{API_PREFIX}/protocols", json=_make_protocol_create(phase=phase))
            assert resp.status_code == 201
            assert resp.json()["phase"] == phase

    @pytest.mark.anyio
    async def test_create_protocol_all_design_types(self, client: AsyncClient):
        """Verify all design types can be created."""
        for dt in ["parallel", "crossover", "factorial", "adaptive", "basket", "umbrella", "platform", "single_arm"]:
            resp = await client.post(f"{API_PREFIX}/protocols", json=_make_protocol_create(design_type=dt))
            assert resp.status_code == 201
            assert resp.json()["design_type"] == dt

    @pytest.mark.anyio
    async def test_schedule_assessment_types(self, client: AsyncClient):
        """Verify all assessment types can be used."""
        all_types = ["physical_exam", "vital_signs", "lab_work", "ecg", "imaging",
                     "questionnaire", "biomarker", "pk_sample", "adverse_event", "concomitant_medication"]
        resp = await client.post(f"{API_PREFIX}/schedules", json=_make_schedule_create(
            assessments=all_types,
        ))
        assert resp.status_code == 201
        assert len(resp.json()["assessments"]) == 10


# ===========================================================================
# VALIDATION ERROR TESTS
# ===========================================================================


class TestValidationErrors:
    """Test validation error handling."""

    @pytest.mark.anyio
    async def test_create_protocol_invalid_phase(self, client: AsyncClient):
        payload = _make_protocol_create(phase="phase_99")
        resp = await client.post(f"{API_PREFIX}/protocols", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_protocol_invalid_design_type(self, client: AsyncClient):
        payload = _make_protocol_create(design_type="invalid_design")
        resp = await client.post(f"{API_PREFIX}/protocols", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_protocol_negative_enrollment(self, client: AsyncClient):
        payload = _make_protocol_create(planned_enrollment=-1)
        resp = await client.post(f"{API_PREFIX}/protocols", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_sample_calc_alpha_out_of_range(self, client: AsyncClient):
        payload = _make_sample_calc_create(alpha=1.5)
        resp = await client.post(f"{API_PREFIX}/sample-calcs", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_sample_calc_power_out_of_range(self, client: AsyncClient):
        payload = _make_sample_calc_create(power=2.0)
        resp = await client.post(f"{API_PREFIX}/sample-calcs", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_sample_calc_negative_dropout(self, client: AsyncClient):
        payload = _make_sample_calc_create(dropout_rate_pct=-5.0)
        resp = await client.post(f"{API_PREFIX}/sample-calcs", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_sample_calc_dropout_over_100(self, client: AsyncClient):
        payload = _make_sample_calc_create(dropout_rate_pct=101.0)
        resp = await client.post(f"{API_PREFIX}/sample-calcs", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_simulation_zero_iterations(self, client: AsyncClient):
        payload = _make_simulation_create(iterations=0)
        resp = await client.post(f"{API_PREFIX}/simulations", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_simulation_negative_enrollment_rate(self, client: AsyncClient):
        payload = _make_simulation_create(enrollment_rate_per_month=-1.0)
        resp = await client.post(f"{API_PREFIX}/simulations", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_simulation_dropout_over_100(self, client: AsyncClient):
        payload = _make_simulation_create(dropout_rate_pct=101.0)
        resp = await client.post(f"{API_PREFIX}/simulations", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_schedule_negative_visit_number(self, client: AsyncClient):
        payload = _make_schedule_create(visit_number=-1)
        resp = await client.post(f"{API_PREFIX}/schedules", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_schedule_negative_window(self, client: AsyncClient):
        payload = _make_schedule_create(window_minus_days=-1)
        resp = await client.post(f"{API_PREFIX}/schedules", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_schedule_negative_duration(self, client: AsyncClient):
        payload = _make_schedule_create(estimated_duration_minutes=-10)
        resp = await client.post(f"{API_PREFIX}/schedules", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_endpoint_invalid_category(self, client: AsyncClient):
        payload = _make_endpoint_create(category="invalid_category")
        resp = await client.post(f"{API_PREFIX}/endpoints", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_simulation_invalid_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/simulations/SIM-001",
            json={"status": "invalid_status"},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_update_protocol_invalid_status(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/protocols/PROTO-001",
            json={"status": "invalid_status"},
        )
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_protocol_missing_required_field(self, client: AsyncClient):
        payload = {"trial_id": EYLEA_TRIAL}  # Missing many required fields
        resp = await client.post(f"{API_PREFIX}/protocols", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_simulation_missing_required_field(self, client: AsyncClient):
        payload = {"protocol_id": "PROTO-001"}  # Missing many required fields
        resp = await client.post(f"{API_PREFIX}/simulations", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_endpoint_missing_required_field(self, client: AsyncClient):
        payload = {"protocol_id": "PROTO-001"}  # Missing many required fields
        resp = await client.post(f"{API_PREFIX}/endpoints", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_schedule_missing_required_field(self, client: AsyncClient):
        payload = {"protocol_id": "PROTO-001"}  # Missing many required fields
        resp = await client.post(f"{API_PREFIX}/schedules", json=payload)
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_create_sample_calc_missing_required_field(self, client: AsyncClient):
        payload = {"protocol_id": "PROTO-001"}  # Missing many required fields
        resp = await client.post(f"{API_PREFIX}/sample-calcs", json=payload)
        assert resp.status_code == 422
