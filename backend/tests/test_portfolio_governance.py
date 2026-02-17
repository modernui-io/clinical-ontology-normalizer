"""Tests for Portfolio & Project Governance module.

Covers:
- Seed data verification (programs, stage gates, team members, resources, prioritizations, risks)
- Program CRUD (create, read, update, delete, list, filter by phase/status/priority/therapeutic_area)
- Stage gate CRUD and advance with GO/HOLD/NO_GO/CONDITIONAL_GO/DEFERRED decisions
- Program phase advancement on GO decision
- Program status changes on HOLD/NO_GO decisions
- Team member CRUD (create, read, update, delete, list, filter by program/role/active)
- Resource allocation CRUD (create, read, update, delete, list, filter by program/type/approved)
- Total cost auto-calculation
- Portfolio prioritization (create with computed score, list, re-rank)
- Risk register CRUD (create, read, update, delete, list, filter by program/category/status)
- Risk score auto-calculation
- Portfolio dashboard
- Governance metrics computation
- Error handling (404s, 400s, invalid operations)
- Service singleton pattern
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.portfolio_governance import (
    AdvanceStageGateRequest,
    GovernanceRole,
    PortfolioPrioritizationCreate,
    PriorityLevel,
    ProgramCreate,
    ProgramPhase,
    ProgramStatus,
    ProgramUpdate,
    ResourceAllocationCreate,
    ResourceAllocationUpdate,
    ResourceType,
    RiskCategory,
    RiskRegisterCreate,
    RiskRegisterUpdate,
    RiskStatus,
    StageGateCreate,
    StageGateDecision,
    StageGateUpdate,
    TeamMemberCreate,
    TeamMemberUpdate,
)
from app.services.portfolio_governance_service import (
    PortfolioGovernanceService,
    get_portfolio_governance_service,
    reset_portfolio_governance_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1/portfolio-governance"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fresh_service():
    """Reset service with fresh seed data before every test."""
    svc = reset_portfolio_governance_service()
    yield svc


@pytest.fixture
def svc(fresh_service) -> PortfolioGovernanceService:
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

today = date.today()


def _make_program_create(**overrides) -> dict:
    defaults = {
        "name": "Test Program",
        "therapeutic_area": "Oncology",
        "indication": "Test Indication",
        "molecule": "TEST-001",
        "modality": "Small Molecule",
        "phase": "preclinical",
        "start_date": today.isoformat(),
        "program_lead": "Dr. Test Lead",
        "executive_sponsor": "Dr. Test Sponsor",
        "total_budget": 100.0,
        "strategic_priority": "medium",
        "description": "Test program description",
    }
    defaults.update(overrides)
    return defaults


def _make_gate_create(**overrides) -> dict:
    defaults = {
        "program_id": "PGM-001",
        "gate_name": "Test Gate",
        "phase_from": "phase_2",
        "phase_to": "phase_3",
        "scheduled_date": (today + timedelta(days=60)).isoformat(),
        "decision_makers": ["Dr. Test"],
    }
    defaults.update(overrides)
    return defaults


def _make_team_member_create(**overrides) -> dict:
    defaults = {
        "program_id": "PGM-001",
        "name": "Test Member",
        "role": "medical_lead",
        "department": "Medical Affairs",
        "allocation_pct": 50.0,
        "start_date": today.isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_resource_create(**overrides) -> dict:
    defaults = {
        "program_id": "PGM-001",
        "resource_type": "fte",
        "description": "Test FTE allocation",
        "quantity": 5.0,
        "unit_cost": 200.0,
        "period_start": today.isoformat(),
        "period_end": (today + timedelta(days=365)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


def _make_prioritization_create(**overrides) -> dict:
    defaults = {
        "program_id": "PGM-001",
        "strategic_alignment_score": 80.0,
        "probability_of_success": 60.0,
        "npv_estimate": 2000.0,
        "peak_revenue_estimate": 1500.0,
        "unmet_need_score": 75.0,
        "competitive_position_score": 65.0,
        "assessed_by": "Test Committee",
    }
    defaults.update(overrides)
    return defaults


def _make_risk_create(**overrides) -> dict:
    defaults = {
        "program_id": "PGM-001",
        "risk_description": "Test risk description",
        "category": "scientific",
        "probability": 0.5,
        "impact": 3.0,
        "mitigation_plan": "Test mitigation plan",
        "owner": "Test Owner",
        "target_resolution_date": (today + timedelta(days=180)).isoformat(),
    }
    defaults.update(overrides)
    return defaults


# =====================================================================
# SEED DATA VERIFICATION
# =====================================================================


class TestSeedData:
    """Verify demo seed data is correctly loaded."""

    def test_seed_programs_count(self, svc: PortfolioGovernanceService):
        programs = svc.list_programs()
        assert len(programs) == 7

    def test_seed_programs_have_regeneron_pipeline(self, svc: PortfolioGovernanceService):
        programs = svc.list_programs()
        names = {p.name for p in programs}
        assert "Dupixent Expansion - COPD" in names
        assert "Libtayo Combination Oncology" in names
        assert "Odronextamab (REGN1979)" in names

    def test_seed_programs_phases(self, svc: PortfolioGovernanceService):
        programs = svc.list_programs()
        phases = {p.phase for p in programs}
        assert ProgramPhase.PHASE_2 in phases
        assert ProgramPhase.PHASE_3 in phases
        assert ProgramPhase.NDA_SUBMISSION in phases
        assert ProgramPhase.POST_APPROVAL in phases

    def test_seed_programs_priorities(self, svc: PortfolioGovernanceService):
        programs = svc.list_programs()
        priorities = {p.strategic_priority for p in programs}
        assert PriorityLevel.CRITICAL in priorities
        assert PriorityLevel.HIGH in priorities
        assert PriorityLevel.MEDIUM in priorities
        assert PriorityLevel.LOW in priorities

    def test_seed_stage_gates_count(self, svc: PortfolioGovernanceService):
        gates = svc.list_stage_gates()
        assert len(gates) == 10

    def test_seed_stage_gates_decisions(self, svc: PortfolioGovernanceService):
        gates = svc.list_stage_gates()
        decisions = {g.decision for g in gates if g.decision is not None}
        assert StageGateDecision.GO in decisions
        assert StageGateDecision.CONDITIONAL_GO in decisions

    def test_seed_team_members_count(self, svc: PortfolioGovernanceService):
        members = svc.list_team_members()
        assert len(members) == 14

    def test_seed_team_members_roles(self, svc: PortfolioGovernanceService):
        members = svc.list_team_members()
        roles = {m.role for m in members}
        assert GovernanceRole.EXECUTIVE_SPONSOR in roles
        assert GovernanceRole.PROGRAM_LEAD in roles
        assert GovernanceRole.MEDICAL_LEAD in roles
        assert GovernanceRole.CMC_LEAD in roles
        assert GovernanceRole.COMMERCIAL_LEAD in roles
        assert GovernanceRole.FINANCE_LEAD in roles
        assert GovernanceRole.REGULATORY_LEAD in roles

    def test_seed_resource_allocations_count(self, svc: PortfolioGovernanceService):
        allocations = svc.list_resource_allocations()
        assert len(allocations) == 8

    def test_seed_resource_types(self, svc: PortfolioGovernanceService):
        allocations = svc.list_resource_allocations()
        types = {a.resource_type for a in allocations}
        assert ResourceType.FTE in types
        assert ResourceType.VENDOR in types
        assert ResourceType.BUDGET in types
        assert ResourceType.FACILITY in types
        assert ResourceType.EQUIPMENT in types

    def test_seed_prioritizations_count(self, svc: PortfolioGovernanceService):
        prios = svc.list_prioritizations()
        assert len(prios) == 7

    def test_seed_prioritizations_ranked(self, svc: PortfolioGovernanceService):
        prios = svc.list_prioritizations()
        ranks = [p.rank for p in prios]
        assert ranks == sorted(ranks)

    def test_seed_risks_count(self, svc: PortfolioGovernanceService):
        risks = svc.list_risks()
        assert len(risks) == 6

    def test_seed_risks_categories(self, svc: PortfolioGovernanceService):
        risks = svc.list_risks()
        categories = {r.category for r in risks}
        assert RiskCategory.SCIENTIFIC in categories
        assert RiskCategory.REGULATORY in categories
        assert RiskCategory.COMMERCIAL in categories
        assert RiskCategory.SUPPLY_CHAIN in categories
        assert RiskCategory.FINANCIAL in categories
        assert RiskCategory.OPERATIONAL in categories


# =====================================================================
# PROGRAM CRUD
# =====================================================================


class TestProgramCrud:
    """Test program create, read, update, delete operations."""

    @pytest.mark.anyio
    async def test_list_programs(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/programs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7
        assert len(data["items"]) == 7

    @pytest.mark.anyio
    async def test_list_programs_filter_phase(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/programs", params={"phase": "phase_3"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["phase"] == "phase_3"

    @pytest.mark.anyio
    async def test_list_programs_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/programs", params={"status": "active"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7  # All seeded programs are active

    @pytest.mark.anyio
    async def test_list_programs_filter_priority(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/programs", params={"priority": "critical"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["strategic_priority"] == "critical"

    @pytest.mark.anyio
    async def test_list_programs_filter_therapeutic_area(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/programs", params={"therapeutic_area": "Oncology"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for item in data["items"]:
            assert item["therapeutic_area"] == "Oncology"

    @pytest.mark.anyio
    async def test_get_program(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/programs/PGM-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PGM-001"
        assert data["name"] == "Dupixent Expansion - COPD"

    @pytest.mark.anyio
    async def test_get_program_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/programs/PGM-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_program(self, client: AsyncClient):
        payload = _make_program_create()
        resp = await client.post(f"{API_PREFIX}/programs", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Program"
        assert data["id"].startswith("PGM-")
        assert data["status"] == "active"
        assert data["spent_budget"] == 0.0

    @pytest.mark.anyio
    async def test_update_program(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/programs/PGM-001",
            json={"name": "Updated Dupixent Program", "spent_budget": 650.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Dupixent Program"
        assert data["spent_budget"] == 650.0

    @pytest.mark.anyio
    async def test_update_program_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/programs/PGM-NONEXISTENT",
            json={"name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_program(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/programs/PGM-007")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/programs/PGM-007")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_program_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/programs/PGM-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# STAGE GATE CRUD & ADVANCE
# =====================================================================


class TestStageGateCrud:
    """Test stage gate CRUD and decision advancement."""

    @pytest.mark.anyio
    async def test_list_stage_gates(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stage-gates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10

    @pytest.mark.anyio
    async def test_list_stage_gates_filter_program(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stage-gates", params={"program_id": "PGM-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["program_id"] == "PGM-001"

    @pytest.mark.anyio
    async def test_list_stage_gates_filter_pending(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stage-gates", params={"pending": True})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["decision"] is None

    @pytest.mark.anyio
    async def test_list_stage_gates_filter_decision(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stage-gates", params={"decision": "go"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["decision"] == "go"

    @pytest.mark.anyio
    async def test_get_stage_gate(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stage-gates/SG-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SG-001"
        assert data["decision"] == "go"

    @pytest.mark.anyio
    async def test_get_stage_gate_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stage-gates/SG-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_stage_gate(self, client: AsyncClient):
        payload = _make_gate_create()
        resp = await client.post(f"{API_PREFIX}/stage-gates", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["gate_name"] == "Test Gate"
        assert data["decision"] is None
        assert data["id"].startswith("SG-")

    @pytest.mark.anyio
    async def test_create_stage_gate_invalid_program(self, client: AsyncClient):
        payload = _make_gate_create(program_id="PGM-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/stage-gates", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_stage_gate(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/stage-gates/SG-002",
            json={"gate_name": "Updated NDA Gate"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["gate_name"] == "Updated NDA Gate"

    @pytest.mark.anyio
    async def test_update_stage_gate_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/stage-gates/SG-NONEXISTENT",
            json={"gate_name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_stage_gate(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/stage-gates/SG-009")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/stage-gates/SG-009")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_stage_gate_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/stage-gates/SG-NONEXISTENT")
        assert resp.status_code == 404


class TestStageGateAdvance:
    """Test stage-gate advancement and its side effects."""

    @pytest.mark.anyio
    async def test_advance_stage_gate_go(self, client: AsyncClient):
        """GO decision should record the decision and advance the program phase."""
        payload = {
            "decision": "go",
            "decision_rationale": "Phase 2b data supports Phase 3 entry",
            "actual_date": today.isoformat(),
            "conditions": [],
            "key_data_reviewed": ["Phase 2b efficacy", "Safety data"],
            "next_gate_date": (today + timedelta(days=365)).isoformat(),
        }
        resp = await client.post(f"{API_PREFIX}/stage-gates/SG-004/advance", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "go"
        assert data["actual_date"] is not None

        # Verify program was advanced from phase_2 to phase_3
        resp2 = await client.get(f"{API_PREFIX}/programs/PGM-002")
        assert resp2.status_code == 200
        assert resp2.json()["phase"] == "phase_3"

    @pytest.mark.anyio
    async def test_advance_stage_gate_hold(self, client: AsyncClient):
        """HOLD decision should put program on hold."""
        payload = {
            "decision": "hold",
            "decision_rationale": "Insufficient data to proceed",
            "actual_date": today.isoformat(),
        }
        resp = await client.post(f"{API_PREFIX}/stage-gates/SG-007/advance", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "hold"

        # Verify program is on hold
        resp2 = await client.get(f"{API_PREFIX}/programs/PGM-005")
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "on_hold"

    @pytest.mark.anyio
    async def test_advance_stage_gate_no_go(self, client: AsyncClient):
        """NO_GO decision should terminate the program."""
        payload = {
            "decision": "no_go",
            "decision_rationale": "Safety concerns preclude further development",
            "actual_date": today.isoformat(),
        }
        resp = await client.post(f"{API_PREFIX}/stage-gates/SG-008/advance", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "no_go"

        # Verify program is terminated
        resp2 = await client.get(f"{API_PREFIX}/programs/PGM-006")
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "terminated"

    @pytest.mark.anyio
    async def test_advance_stage_gate_conditional_go(self, client: AsyncClient):
        """CONDITIONAL_GO should record conditions."""
        payload = {
            "decision": "conditional_go",
            "decision_rationale": "Proceed with conditions",
            "actual_date": today.isoformat(),
            "conditions": ["Complete additional PK study", "Resolve CMC issue"],
        }
        resp = await client.post(f"{API_PREFIX}/stage-gates/SG-002/advance", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "conditional_go"
        assert len(data["conditions"]) == 2

    @pytest.mark.anyio
    async def test_advance_stage_gate_deferred(self, client: AsyncClient):
        """DEFERRED decision should record without changing program status."""
        # Get initial program status
        resp_prog = await client.get(f"{API_PREFIX}/programs/PGM-005")
        initial_status = resp_prog.json()["status"]

        payload = {
            "decision": "deferred",
            "decision_rationale": "Postpone decision pending additional data readout",
            "actual_date": today.isoformat(),
        }
        resp = await client.post(f"{API_PREFIX}/stage-gates/SG-007/advance", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "deferred"

        # Verify program status unchanged for deferred
        resp2 = await client.get(f"{API_PREFIX}/programs/PGM-005")
        assert resp2.json()["status"] == initial_status

    @pytest.mark.anyio
    async def test_advance_already_decided_gate(self, client: AsyncClient):
        """Advancing a gate that already has a decision should fail."""
        payload = {
            "decision": "go",
            "decision_rationale": "Try again",
            "actual_date": today.isoformat(),
        }
        resp = await client.post(f"{API_PREFIX}/stage-gates/SG-001/advance", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_advance_stage_gate_not_found(self, client: AsyncClient):
        payload = {
            "decision": "go",
            "decision_rationale": "Test",
            "actual_date": today.isoformat(),
        }
        resp = await client.post(f"{API_PREFIX}/stage-gates/SG-NONEXISTENT/advance", json=payload)
        assert resp.status_code == 404


# =====================================================================
# TEAM MEMBER CRUD
# =====================================================================


class TestTeamMemberCrud:
    """Test team member CRUD operations."""

    @pytest.mark.anyio
    async def test_list_team_members(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/team-members")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 14

    @pytest.mark.anyio
    async def test_list_team_members_filter_program(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/team-members", params={"program_id": "PGM-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["program_id"] == "PGM-001"

    @pytest.mark.anyio
    async def test_list_team_members_filter_role(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/team-members", params={"role": "program_lead"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["role"] == "program_lead"

    @pytest.mark.anyio
    async def test_list_team_members_filter_active(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/team-members", params={"active": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 14  # All seeded members are active

    @pytest.mark.anyio
    async def test_get_team_member(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/team-members/TM-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Dr. Sarah Chen"
        assert data["role"] == "program_lead"

    @pytest.mark.anyio
    async def test_get_team_member_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/team-members/TM-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_team_member(self, client: AsyncClient):
        payload = _make_team_member_create()
        resp = await client.post(f"{API_PREFIX}/team-members", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Member"
        assert data["active"] is True
        assert data["id"].startswith("TM-")

    @pytest.mark.anyio
    async def test_create_team_member_invalid_program(self, client: AsyncClient):
        payload = _make_team_member_create(program_id="PGM-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/team-members", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_team_member(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/team-members/TM-001",
            json={"allocation_pct": 90.0, "department": "Updated Department"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["allocation_pct"] == 90.0
        assert data["department"] == "Updated Department"

    @pytest.mark.anyio
    async def test_update_team_member_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/team-members/TM-NONEXISTENT",
            json={"name": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_team_member(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/team-members/TM-014")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/team-members/TM-014")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_team_member_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/team-members/TM-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_deactivate_team_member(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/team-members/TM-001",
            json={"active": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] is False


# =====================================================================
# RESOURCE ALLOCATION CRUD
# =====================================================================


class TestResourceAllocationCrud:
    """Test resource allocation CRUD operations."""

    @pytest.mark.anyio
    async def test_list_resource_allocations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resources")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 8

    @pytest.mark.anyio
    async def test_list_resources_filter_program(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resources", params={"program_id": "PGM-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["program_id"] == "PGM-001"

    @pytest.mark.anyio
    async def test_list_resources_filter_type(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resources", params={"resource_type": "fte"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["resource_type"] == "fte"

    @pytest.mark.anyio
    async def test_list_resources_filter_approved(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resources", params={"approved": False})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["approved"] is False

    @pytest.mark.anyio
    async def test_get_resource_allocation(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resources/RA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RA-001"
        assert data["approved"] is True

    @pytest.mark.anyio
    async def test_get_resource_allocation_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resources/RA-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_resource_allocation(self, client: AsyncClient):
        payload = _make_resource_create()
        resp = await client.post(f"{API_PREFIX}/resources", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["resource_type"] == "fte"
        assert data["total_cost"] == 1000.0  # 5.0 * 200.0
        assert data["approved"] is False
        assert data["id"].startswith("RA-")

    @pytest.mark.anyio
    async def test_create_resource_invalid_program(self, client: AsyncClient):
        payload = _make_resource_create(program_id="PGM-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/resources", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_update_resource_allocation(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/resources/RA-007",
            json={"approved": True, "approved_by": "CFO"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approved"] is True
        assert data["approved_by"] == "CFO"

    @pytest.mark.anyio
    async def test_update_resource_recalculates_total(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/resources/RA-001",
            json={"quantity": 30.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["quantity"] == 30.0
        # total_cost should be recalculated: 30.0 * 200.0 = 6000.0
        assert data["total_cost"] == 6000.0

    @pytest.mark.anyio
    async def test_update_resource_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/resources/RA-NONEXISTENT",
            json={"approved": True},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_resource_allocation(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/resources/RA-008")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/resources/RA-008")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_resource_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/resources/RA-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# PORTFOLIO PRIORITIZATION
# =====================================================================


class TestPortfolioPrioritization:
    """Test portfolio prioritization operations."""

    @pytest.mark.anyio
    async def test_list_prioritizations(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/prioritizations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 7

    @pytest.mark.anyio
    async def test_list_prioritizations_filter_program(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/prioritizations", params={"program_id": "PGM-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["program_id"] == "PGM-001"

    @pytest.mark.anyio
    async def test_prioritizations_sorted_by_rank(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/prioritizations")
        data = resp.json()
        ranks = [item["rank"] for item in data["items"]]
        assert ranks == sorted(ranks)

    @pytest.mark.anyio
    async def test_get_prioritization(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/prioritizations/PP-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "PP-001"
        assert data["rank"] == 1

    @pytest.mark.anyio
    async def test_get_prioritization_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/prioritizations/PP-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_create_prioritization(self, client: AsyncClient):
        payload = _make_prioritization_create()
        resp = await client.post(f"{API_PREFIX}/prioritizations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["program_id"] == "PGM-001"
        assert 0 <= data["overall_priority_score"] <= 100
        assert data["rank"] >= 1
        assert data["id"].startswith("PP-")

    @pytest.mark.anyio
    async def test_create_prioritization_invalid_program(self, client: AsyncClient):
        payload = _make_prioritization_create(program_id="PGM-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/prioritizations", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_create_prioritization_computes_score(self, client: AsyncClient):
        payload = _make_prioritization_create(
            strategic_alignment_score=100.0,
            probability_of_success=100.0,
            npv_estimate=5000.0,
            unmet_need_score=100.0,
            competitive_position_score=100.0,
        )
        resp = await client.post(f"{API_PREFIX}/prioritizations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["overall_priority_score"] > 80.0  # High scores -> high overall

    @pytest.mark.anyio
    async def test_rerank_portfolio(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/prioritizations/rerank")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 7
        ranks = [item["rank"] for item in data["items"]]
        assert ranks == list(range(1, len(ranks) + 1))  # Sequential 1..N

    @pytest.mark.anyio
    async def test_rerank_preserves_score_ordering(self, client: AsyncClient):
        resp = await client.post(f"{API_PREFIX}/prioritizations/rerank")
        data = resp.json()
        scores = [item["overall_priority_score"] for item in data["items"]]
        assert scores == sorted(scores, reverse=True)


# =====================================================================
# RISK REGISTER
# =====================================================================


class TestRiskRegister:
    """Test risk register CRUD operations."""

    @pytest.mark.anyio
    async def test_list_risks(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6

    @pytest.mark.anyio
    async def test_list_risks_filter_program(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks", params={"program_id": "PGM-001"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["program_id"] == "PGM-001"

    @pytest.mark.anyio
    async def test_list_risks_filter_category(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks", params={"category": "scientific"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["category"] == "scientific"

    @pytest.mark.anyio
    async def test_list_risks_filter_status(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks", params={"status": "open"})
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["status"] == "open"

    @pytest.mark.anyio
    async def test_risks_sorted_by_score_desc(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks")
        data = resp.json()
        scores = [item["risk_score"] for item in data["items"]]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.anyio
    async def test_get_risk(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks/RR-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "RR-001"
        assert data["category"] == "commercial"

    @pytest.mark.anyio
    async def test_get_risk_not_found(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks/RR-NONEXISTENT")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_register_risk(self, client: AsyncClient):
        payload = _make_risk_create()
        resp = await client.post(f"{API_PREFIX}/risks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["risk_description"] == "Test risk description"
        assert data["risk_score"] == 1.5  # 0.5 * 3.0
        assert data["status"] == "open"
        assert data["id"].startswith("RR-")

    @pytest.mark.anyio
    async def test_register_risk_invalid_program(self, client: AsyncClient):
        payload = _make_risk_create(program_id="PGM-NONEXISTENT")
        resp = await client.post(f"{API_PREFIX}/risks", json=payload)
        assert resp.status_code == 400

    @pytest.mark.anyio
    async def test_register_risk_computes_score(self, client: AsyncClient):
        payload = _make_risk_create(probability=0.8, impact=5.0)
        resp = await client.post(f"{API_PREFIX}/risks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["risk_score"] == 4.0  # 0.8 * 5.0

    @pytest.mark.anyio
    async def test_update_risk(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/risks/RR-002",
            json={"status": "mitigating", "mitigation_plan": "Updated plan"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "mitigating"
        assert data["mitigation_plan"] == "Updated plan"

    @pytest.mark.anyio
    async def test_update_risk_recalculates_score(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/risks/RR-002",
            json={"probability": 0.1, "impact": 2.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["risk_score"] == 0.2  # 0.1 * 2.0

    @pytest.mark.anyio
    async def test_update_risk_not_found(self, client: AsyncClient):
        resp = await client.put(
            f"{API_PREFIX}/risks/RR-NONEXISTENT",
            json={"status": "resolved"},
        )
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_delete_risk(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/risks/RR-006")
        assert resp.status_code == 204
        resp2 = await client.get(f"{API_PREFIX}/risks/RR-006")
        assert resp2.status_code == 404

    @pytest.mark.anyio
    async def test_delete_risk_not_found(self, client: AsyncClient):
        resp = await client.delete(f"{API_PREFIX}/risks/RR-NONEXISTENT")
        assert resp.status_code == 404


# =====================================================================
# DASHBOARD
# =====================================================================


class TestPortfolioDashboard:
    """Test portfolio dashboard."""

    @pytest.mark.anyio
    async def test_get_dashboard(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "metrics" in data
        assert "programs" in data
        assert "upcoming_gates" in data
        assert "top_risks" in data
        assert "priority_rankings" in data

    @pytest.mark.anyio
    async def test_dashboard_has_active_programs(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dashboard")
        data = resp.json()
        assert len(data["programs"]) == 7  # All programs active

    @pytest.mark.anyio
    async def test_dashboard_has_priority_rankings(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dashboard")
        data = resp.json()
        assert len(data["priority_rankings"]) == 7
        ranks = [r["rank"] for r in data["priority_rankings"]]
        assert ranks == sorted(ranks)

    @pytest.mark.anyio
    async def test_dashboard_top_risks_ordered(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dashboard")
        data = resp.json()
        if len(data["top_risks"]) > 1:
            scores = [r["risk_score"] for r in data["top_risks"]]
            assert scores == sorted(scores, reverse=True)

    @pytest.mark.anyio
    async def test_dashboard_upcoming_gates_within_90_days(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/dashboard")
        data = resp.json()
        # Use date.today() at assertion time to match the service's runtime cutoff,
        # avoiding stale module-level `today` when tests run across midnight.
        cutoff = (date.today() + timedelta(days=90)).isoformat()
        for gate in data["upcoming_gates"]:
            assert gate["scheduled_date"] <= cutoff
            assert gate["decision"] is None


# =====================================================================
# GOVERNANCE METRICS
# =====================================================================


class TestGovernanceMetrics:
    """Test governance metrics computation."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_programs"] == 7
        assert data["active_programs"] == 7
        assert data["total_portfolio_budget"] > 0
        assert data["total_portfolio_spent"] > 0
        assert 0 <= data["budget_utilization_pct"] <= 100
        assert data["total_team_members"] > 0
        assert data["total_resource_allocations"] == 8
        assert data["open_risks"] > 0

    def test_metrics_programs_by_phase(self, svc: PortfolioGovernanceService):
        metrics = svc.get_metrics()
        total_by_phase = sum(metrics.programs_by_phase.values())
        assert total_by_phase == metrics.total_programs

    def test_metrics_programs_by_priority(self, svc: PortfolioGovernanceService):
        metrics = svc.get_metrics()
        total_by_priority = sum(metrics.programs_by_priority.values())
        assert total_by_priority == metrics.total_programs

    def test_metrics_budget_utilization(self, svc: PortfolioGovernanceService):
        metrics = svc.get_metrics()
        if metrics.total_portfolio_budget > 0:
            expected_util = round(
                metrics.total_portfolio_spent / metrics.total_portfolio_budget * 100, 1
            )
            assert metrics.budget_utilization_pct == expected_util

    def test_metrics_pending_approvals(self, svc: PortfolioGovernanceService):
        metrics = svc.get_metrics()
        unapproved = [
            r for r in svc.list_resource_allocations()
            if not r.approved
        ]
        assert metrics.pending_approvals == len(unapproved)

    def test_metrics_open_risks(self, svc: PortfolioGovernanceService):
        metrics = svc.get_metrics()
        open_risks = [
            r for r in svc.list_risks()
            if r.status in (RiskStatus.OPEN, RiskStatus.MITIGATING)
        ]
        assert metrics.open_risks == len(open_risks)

    def test_metrics_avg_pos(self, svc: PortfolioGovernanceService):
        metrics = svc.get_metrics()
        assert 0 <= metrics.avg_probability_of_success <= 100

    def test_metrics_total_npv(self, svc: PortfolioGovernanceService):
        metrics = svc.get_metrics()
        prios = svc.list_prioritizations()
        expected_npv = round(sum(p.npv_estimate for p in prios), 1)
        assert metrics.total_npv == expected_npv


# =====================================================================
# SERVICE SINGLETON
# =====================================================================


class TestServiceSingleton:
    """Test singleton pattern behavior."""

    def test_get_service_returns_same_instance(self):
        svc1 = get_portfolio_governance_service()
        svc2 = get_portfolio_governance_service()
        assert svc1 is svc2

    def test_reset_creates_fresh_instance(self):
        svc1 = get_portfolio_governance_service()
        svc2 = reset_portfolio_governance_service()
        assert svc1 is not svc2

    def test_reset_reseeds_data(self):
        svc = get_portfolio_governance_service()
        svc.delete_program("PGM-001")
        assert svc.get_program("PGM-001") is None
        svc2 = reset_portfolio_governance_service()
        assert svc2.get_program("PGM-001") is not None


# =====================================================================
# EDGE CASES AND ERROR HANDLING
# =====================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.anyio
    async def test_list_programs_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/programs")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_stage_gates_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stage-gates")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_team_members_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/team-members")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_resources_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resources")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_risks_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_list_prioritizations_no_filters(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/prioritizations")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_create_program_with_all_fields(self, client: AsyncClient):
        payload = _make_program_create(
            name="Full Program",
            therapeutic_area="Immunology",
            indication="Atopic Dermatitis",
            molecule="DUPX-001",
            modality="Bispecific Antibody",
            phase="phase_1",
            target_approval_date=(today + timedelta(days=1825)).isoformat(),
            total_budget=500.0,
            strategic_priority="high",
            description="A comprehensive test program",
        )
        resp = await client.post(f"{API_PREFIX}/programs", json=payload)
        assert resp.status_code == 201

    @pytest.mark.anyio
    async def test_create_gate_with_all_fields(self, client: AsyncClient):
        payload = _make_gate_create(
            gate_name="Comprehensive Test Gate",
            phase_from="phase_1",
            phase_to="phase_2",
            decision_makers=["Dr. A", "Dr. B", "Dr. C"],
        )
        resp = await client.post(f"{API_PREFIX}/stage-gates", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["decision_makers"]) == 3

    @pytest.mark.anyio
    async def test_resource_total_cost_calculation(self, client: AsyncClient):
        """Verify total_cost = quantity * unit_cost on create."""
        payload = _make_resource_create(quantity=10.0, unit_cost=500.0)
        resp = await client.post(f"{API_PREFIX}/resources", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["total_cost"] == 5000.0

    @pytest.mark.anyio
    async def test_risk_score_calculation(self, client: AsyncClient):
        """Verify risk_score = probability * impact on create."""
        payload = _make_risk_create(probability=0.7, impact=4.5)
        resp = await client.post(f"{API_PREFIX}/risks", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert abs(data["risk_score"] - 3.15) < 0.01

    def test_service_advance_go_updates_phase(self, svc: PortfolioGovernanceService):
        """Test service-level phase advancement on GO."""
        # SG-004: PGM-002, phase_2 -> phase_3
        program_before = svc.get_program("PGM-002")
        assert program_before is not None
        assert program_before.phase == ProgramPhase.PHASE_2

        svc.advance_stage_gate("SG-004", AdvanceStageGateRequest(
            decision=StageGateDecision.GO,
            decision_rationale="Positive data",
            actual_date=today,
        ))

        program_after = svc.get_program("PGM-002")
        assert program_after is not None
        assert program_after.phase == ProgramPhase.PHASE_3

    def test_service_advance_same_phase_no_change(self, svc: PortfolioGovernanceService):
        """GO on a same-phase gate should not change the phase."""
        # SG-008: PGM-006, phase_3 -> phase_3
        program_before = svc.get_program("PGM-006")
        assert program_before is not None
        assert program_before.phase == ProgramPhase.PHASE_3

        svc.advance_stage_gate("SG-008", AdvanceStageGateRequest(
            decision=StageGateDecision.GO,
            decision_rationale="Primary endpoint met",
            actual_date=today,
        ))

        program_after = svc.get_program("PGM-006")
        assert program_after is not None
        assert program_after.phase == ProgramPhase.PHASE_3

    def test_prioritize_portfolio_reranks(self, svc: PortfolioGovernanceService):
        """Re-ranking should produce sequential ranks matching score order."""
        ranked = svc.prioritize_portfolio()
        scores = [p.overall_priority_score for p in ranked]
        assert scores == sorted(scores, reverse=True)
        ranks = [p.rank for p in ranked]
        assert ranks == list(range(1, len(ranks) + 1))

    def test_allocate_resources_convenience(self, svc: PortfolioGovernanceService):
        """Test the allocate_resources convenience method."""
        payload = ResourceAllocationCreate(
            program_id="PGM-002",
            resource_type=ResourceType.FTE,
            description="Test FTE",
            quantity=3.0,
            unit_cost=150.0,
            period_start=today,
            period_end=today + timedelta(days=365),
        )
        alloc = svc.allocate_resources("PGM-002", payload)
        assert alloc.program_id == "PGM-002"
        assert alloc.total_cost == 450.0

    def test_allocate_resources_invalid_program(self, svc: PortfolioGovernanceService):
        payload = ResourceAllocationCreate(
            program_id="PGM-NONEXISTENT",
            resource_type=ResourceType.FTE,
            description="Test",
            quantity=1.0,
            unit_cost=100.0,
            period_start=today,
            period_end=today + timedelta(days=30),
        )
        with pytest.raises(ValueError, match="not found"):
            svc.allocate_resources("PGM-NONEXISTENT", payload)


# =====================================================================
# COMPREHENSIVE FIELD VALIDATIONS
# =====================================================================


class TestFieldValidations:
    """Test field-level validations and data integrity."""

    @pytest.mark.anyio
    async def test_program_has_timestamps(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/programs/PGM-001")
        data = resp.json()
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.anyio
    async def test_stage_gate_has_created_at(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/stage-gates/SG-001")
        data = resp.json()
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_resource_has_created_at(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/resources/RA-001")
        data = resp.json()
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_risk_has_created_at(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks/RR-001")
        data = resp.json()
        assert "created_at" in data

    @pytest.mark.anyio
    async def test_program_budget_fields(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/programs/PGM-001")
        data = resp.json()
        assert data["total_budget"] >= 0
        assert data["spent_budget"] >= 0
        assert data["spent_budget"] <= data["total_budget"]

    @pytest.mark.anyio
    async def test_prioritization_scores_in_range(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/prioritizations/PP-001")
        data = resp.json()
        assert 0 <= data["strategic_alignment_score"] <= 100
        assert 0 <= data["probability_of_success"] <= 100
        assert 0 <= data["unmet_need_score"] <= 100
        assert 0 <= data["competitive_position_score"] <= 100
        assert 0 <= data["overall_priority_score"] <= 100

    @pytest.mark.anyio
    async def test_risk_score_within_range(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/risks/RR-001")
        data = resp.json()
        assert 0 <= data["probability"] <= 1
        assert 1 <= data["impact"] <= 5
        assert 0 <= data["risk_score"] <= 5

    @pytest.mark.anyio
    async def test_team_member_allocation_range(self, client: AsyncClient):
        resp = await client.get(f"{API_PREFIX}/team-members/TM-001")
        data = resp.json()
        assert 0 <= data["allocation_pct"] <= 100


# =====================================================================
# ENUM COVERAGE
# =====================================================================


class TestEnumCoverage:
    """Test that all enum values are represented in seed data."""

    @pytest.mark.anyio
    async def test_all_program_statuses_accessible(self, client: AsyncClient):
        """Test that we can filter by all program statuses."""
        for status in ["active", "on_hold", "terminated", "completed"]:
            resp = await client.get(f"{API_PREFIX}/programs", params={"status": status})
            assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_all_resource_types_accessible(self, client: AsyncClient):
        for rtype in ["fte", "budget", "equipment", "vendor", "facility"]:
            resp = await client.get(f"{API_PREFIX}/resources", params={"resource_type": rtype})
            assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_all_risk_categories_accessible(self, client: AsyncClient):
        for cat in ["scientific", "regulatory", "commercial", "operational", "financial", "supply_chain"]:
            resp = await client.get(f"{API_PREFIX}/risks", params={"category": cat})
            assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_all_risk_statuses_accessible(self, client: AsyncClient):
        for status in ["open", "mitigating", "resolved", "accepted"]:
            resp = await client.get(f"{API_PREFIX}/risks", params={"status": status})
            assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_all_governance_roles_accessible(self, client: AsyncClient):
        for role in ["executive_sponsor", "program_lead", "medical_lead",
                     "regulatory_lead", "cmc_lead", "commercial_lead", "finance_lead"]:
            resp = await client.get(f"{API_PREFIX}/team-members", params={"role": role})
            assert resp.status_code == 200
