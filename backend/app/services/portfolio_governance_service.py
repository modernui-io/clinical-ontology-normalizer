"""Portfolio & Project Governance Service.

Manages program lifecycles, stage-gate decisions, cross-functional team
structures, resource allocation, portfolio prioritization, risk registers,
and executive governance dashboards for clinical trial portfolio management.

Usage:
    from app.services.portfolio_governance_service import (
        get_portfolio_governance_service,
    )

    svc = get_portfolio_governance_service()
    programs = svc.list_programs()
    dashboard = svc.get_portfolio_dashboard()
"""

from __future__ import annotations

import logging
import threading
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.portfolio_governance import (
    AdvanceStageGateRequest,
    GovernanceMetrics,
    GovernanceRole,
    PortfolioDashboard,
    PortfolioPrioritization,
    PortfolioPrioritizationCreate,
    PriorityLevel,
    Program,
    ProgramCreate,
    ProgramPhase,
    ProgramStatus,
    ProgramUpdate,
    ResourceAllocation,
    ResourceAllocationCreate,
    ResourceAllocationUpdate,
    ResourceType,
    RiskCategory,
    RiskRegister,
    RiskRegisterCreate,
    RiskRegisterUpdate,
    RiskStatus,
    StageGate,
    StageGateCreate,
    StageGateDecision,
    StageGateUpdate,
    TeamMember,
    TeamMemberCreate,
    TeamMemberUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HIGH_RISK_SCORE_THRESHOLD = 3.0


class PortfolioGovernanceService:
    """In-memory Portfolio & Project Governance engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._programs: dict[str, Program] = {}
        self._stage_gates: dict[str, StageGate] = {}
        self._team_members: dict[str, TeamMember] = {}
        self._resource_allocations: dict[str, ResourceAllocation] = {}
        self._prioritizations: dict[str, PortfolioPrioritization] = {}
        self._risks: dict[str, RiskRegister] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic Regeneron pipeline portfolio data."""
        now = datetime.now(timezone.utc)
        today = date.today()

        # --- 7 Programs (Regeneron pipeline) ---
        programs_data = [
            {
                "id": "PGM-001",
                "name": "Dupixent Expansion - COPD",
                "therapeutic_area": "Immunology",
                "indication": "Chronic Obstructive Pulmonary Disease (COPD)",
                "molecule": "Dupilumab",
                "modality": "Monoclonal Antibody (mAb)",
                "phase": ProgramPhase.PHASE_3,
                "start_date": date(2021, 3, 15),
                "target_approval_date": date(2026, 6, 30),
                "program_lead": "Dr. Sarah Chen",
                "executive_sponsor": "Dr. George D. Yancopoulos",
                "total_budget": 850.0,
                "spent_budget": 620.0,
                "strategic_priority": PriorityLevel.CRITICAL,
                "status": ProgramStatus.ACTIVE,
                "description": "Phase 3 expansion of Dupixent into COPD with type 2 inflammation biomarkers",
                "created_at": now - timedelta(days=1200),
                "updated_at": now - timedelta(days=5),
            },
            {
                "id": "PGM-002",
                "name": "Libtayo Combination Oncology",
                "therapeutic_area": "Oncology",
                "indication": "Non-Small Cell Lung Cancer (NSCLC)",
                "molecule": "Cemiplimab",
                "modality": "Monoclonal Antibody (mAb)",
                "phase": ProgramPhase.PHASE_2,
                "start_date": date(2022, 1, 10),
                "target_approval_date": date(2027, 12, 31),
                "program_lead": "Dr. Michael Torres",
                "executive_sponsor": "Dr. Leonard S. Schleifer",
                "total_budget": 720.0,
                "spent_budget": 310.0,
                "strategic_priority": PriorityLevel.HIGH,
                "status": ProgramStatus.ACTIVE,
                "description": "Combination of cemiplimab with bispecific antibodies for advanced NSCLC",
                "created_at": now - timedelta(days=900),
                "updated_at": now - timedelta(days=10),
            },
            {
                "id": "PGM-003",
                "name": "Odronextamab (REGN1979)",
                "therapeutic_area": "Oncology",
                "indication": "Relapsed/Refractory Follicular Lymphoma",
                "molecule": "Odronextamab",
                "modality": "Bispecific Antibody",
                "phase": ProgramPhase.NDA_SUBMISSION,
                "start_date": date(2019, 6, 1),
                "target_approval_date": date(2026, 3, 15),
                "program_lead": "Dr. Emily Watson",
                "executive_sponsor": "Dr. George D. Yancopoulos",
                "total_budget": 950.0,
                "spent_budget": 890.0,
                "strategic_priority": PriorityLevel.CRITICAL,
                "status": ProgramStatus.ACTIVE,
                "description": "BLA submission for CD20xCD3 bispecific in relapsed/refractory follicular lymphoma",
                "created_at": now - timedelta(days=2000),
                "updated_at": now - timedelta(days=2),
            },
            {
                "id": "PGM-004",
                "name": "Fianlimab + Libtayo Melanoma",
                "therapeutic_area": "Oncology",
                "indication": "Advanced Melanoma",
                "molecule": "Fianlimab (REGN3767)",
                "modality": "Monoclonal Antibody (mAb)",
                "phase": ProgramPhase.PHASE_3,
                "start_date": date(2021, 9, 20),
                "target_approval_date": date(2027, 6, 30),
                "program_lead": "Dr. James Park",
                "executive_sponsor": "Dr. Leonard S. Schleifer",
                "total_budget": 680.0,
                "spent_budget": 410.0,
                "strategic_priority": PriorityLevel.HIGH,
                "status": ProgramStatus.ACTIVE,
                "description": "Pivotal Phase 3 trial of LAG-3 inhibitor fianlimab combined with cemiplimab in melanoma",
                "created_at": now - timedelta(days=1100),
                "updated_at": now - timedelta(days=8),
            },
            {
                "id": "PGM-005",
                "name": "Itepekimab Asthma",
                "therapeutic_area": "Immunology",
                "indication": "Moderate-to-Severe Asthma",
                "molecule": "Itepekimab (REGN3500)",
                "modality": "Monoclonal Antibody (mAb)",
                "phase": ProgramPhase.PHASE_2,
                "start_date": date(2022, 6, 15),
                "target_approval_date": date(2028, 12, 31),
                "program_lead": "Dr. Lisa Huang",
                "executive_sponsor": "Dr. George D. Yancopoulos",
                "total_budget": 420.0,
                "spent_budget": 185.0,
                "strategic_priority": PriorityLevel.MEDIUM,
                "status": ProgramStatus.ACTIVE,
                "description": "Anti-IL-33 antibody for moderate-to-severe asthma including non-type 2 phenotypes",
                "created_at": now - timedelta(days=800),
                "updated_at": now - timedelta(days=15),
            },
            {
                "id": "PGM-006",
                "name": "Linvoseltamab (REGN5458)",
                "therapeutic_area": "Oncology",
                "indication": "Relapsed/Refractory Multiple Myeloma",
                "molecule": "Linvoseltamab",
                "modality": "Bispecific Antibody",
                "phase": ProgramPhase.PHASE_3,
                "start_date": date(2021, 1, 10),
                "target_approval_date": date(2026, 9, 30),
                "program_lead": "Dr. Robert Kim",
                "executive_sponsor": "Dr. George D. Yancopoulos",
                "total_budget": 780.0,
                "spent_budget": 550.0,
                "strategic_priority": PriorityLevel.CRITICAL,
                "status": ProgramStatus.ACTIVE,
                "description": "BCMAxCD3 bispecific antibody for relapsed/refractory multiple myeloma",
                "created_at": now - timedelta(days=1300),
                "updated_at": now - timedelta(days=3),
            },
            {
                "id": "PGM-007",
                "name": "REGN-EB3 Ebola",
                "therapeutic_area": "Infectious Disease",
                "indication": "Ebola Virus Disease",
                "molecule": "REGN-EB3 (Inmazeb)",
                "modality": "Monoclonal Antibody Cocktail",
                "phase": ProgramPhase.POST_APPROVAL,
                "start_date": date(2015, 3, 1),
                "target_approval_date": None,
                "program_lead": "Dr. Amanda Foster",
                "executive_sponsor": "Dr. Leonard S. Schleifer",
                "total_budget": 320.0,
                "spent_budget": 310.0,
                "strategic_priority": PriorityLevel.LOW,
                "status": ProgramStatus.ACTIVE,
                "description": "Post-approval lifecycle management for FDA-approved Ebola treatment",
                "created_at": now - timedelta(days=3500),
                "updated_at": now - timedelta(days=30),
            },
        ]

        for p in programs_data:
            self._programs[p["id"]] = Program(**p)

        # --- 10 Stage Gates ---
        gates_data = [
            {
                "id": "SG-001",
                "program_id": "PGM-001",
                "gate_name": "Phase 3 Interim Analysis Gate",
                "phase_from": ProgramPhase.PHASE_3,
                "phase_to": ProgramPhase.PHASE_3,
                "scheduled_date": today - timedelta(days=120),
                "actual_date": today - timedelta(days=118),
                "decision": StageGateDecision.GO,
                "decision_rationale": "Positive interim efficacy signal; primary endpoint on track",
                "conditions": [],
                "decision_makers": ["Dr. Yancopoulos", "Dr. Schleifer", "Dr. Chen"],
                "key_data_reviewed": ["Interim efficacy analysis", "Safety database review", "DSMB recommendation"],
                "next_gate_date": today + timedelta(days=90),
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "SG-002",
                "program_id": "PGM-001",
                "gate_name": "NDA Readiness Gate",
                "phase_from": ProgramPhase.PHASE_3,
                "phase_to": ProgramPhase.NDA_SUBMISSION,
                "scheduled_date": today + timedelta(days=90),
                "actual_date": None,
                "decision": None,
                "decision_rationale": None,
                "conditions": [],
                "decision_makers": ["Dr. Yancopoulos", "Dr. Schleifer", "SVP Regulatory"],
                "key_data_reviewed": [],
                "next_gate_date": None,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SG-003",
                "program_id": "PGM-002",
                "gate_name": "Phase 2 Dose Selection Gate",
                "phase_from": ProgramPhase.PHASE_2,
                "phase_to": ProgramPhase.PHASE_2,
                "scheduled_date": today - timedelta(days=45),
                "actual_date": today - timedelta(days=44),
                "decision": StageGateDecision.CONDITIONAL_GO,
                "decision_rationale": "Dose-response relationship established; need additional PK data",
                "conditions": ["Complete PK bridging study", "Confirm RP2D in expansion cohort"],
                "decision_makers": ["Dr. Schleifer", "Dr. Torres", "VP Clinical"],
                "key_data_reviewed": ["Phase 2a dose-escalation data", "PK/PD modeling", "Biomarker analysis"],
                "next_gate_date": today + timedelta(days=180),
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "SG-004",
                "program_id": "PGM-002",
                "gate_name": "Phase 3 Entry Gate",
                "phase_from": ProgramPhase.PHASE_2,
                "phase_to": ProgramPhase.PHASE_3,
                "scheduled_date": today + timedelta(days=180),
                "actual_date": None,
                "decision": None,
                "decision_rationale": None,
                "conditions": [],
                "decision_makers": ["Dr. Yancopoulos", "Dr. Schleifer", "Dr. Torres"],
                "key_data_reviewed": [],
                "next_gate_date": None,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SG-005",
                "program_id": "PGM-003",
                "gate_name": "BLA Submission Gate",
                "phase_from": ProgramPhase.PHASE_3,
                "phase_to": ProgramPhase.NDA_SUBMISSION,
                "scheduled_date": today - timedelta(days=60),
                "actual_date": today - timedelta(days=58),
                "decision": StageGateDecision.GO,
                "decision_rationale": "Strong Phase 3 results support BLA filing; complete response package ready",
                "conditions": [],
                "decision_makers": ["Dr. Yancopoulos", "SVP Regulatory", "Dr. Watson"],
                "key_data_reviewed": ["Phase 3 primary/secondary endpoints", "Integrated safety summary", "CMC package"],
                "next_gate_date": today + timedelta(days=270),
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "SG-006",
                "program_id": "PGM-004",
                "gate_name": "Phase 3 Enrollment Gate",
                "phase_from": ProgramPhase.PHASE_3,
                "phase_to": ProgramPhase.PHASE_3,
                "scheduled_date": today - timedelta(days=30),
                "actual_date": today - timedelta(days=28),
                "decision": StageGateDecision.GO,
                "decision_rationale": "Enrollment targets on track; strong site activation",
                "conditions": [],
                "decision_makers": ["Dr. Schleifer", "Dr. Park", "VP Clinical Ops"],
                "key_data_reviewed": ["Enrollment projection model", "Site activation status", "Safety monitoring report"],
                "next_gate_date": today + timedelta(days=365),
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "SG-007",
                "program_id": "PGM-005",
                "gate_name": "Phase 2 Efficacy Gate",
                "phase_from": ProgramPhase.PHASE_2,
                "phase_to": ProgramPhase.PHASE_2,
                "scheduled_date": today + timedelta(days=60),
                "actual_date": None,
                "decision": None,
                "decision_rationale": None,
                "conditions": [],
                "decision_makers": ["Dr. Yancopoulos", "Dr. Huang", "SVP Immunology"],
                "key_data_reviewed": [],
                "next_gate_date": None,
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "SG-008",
                "program_id": "PGM-006",
                "gate_name": "Phase 3 Primary Endpoint Gate",
                "phase_from": ProgramPhase.PHASE_3,
                "phase_to": ProgramPhase.PHASE_3,
                "scheduled_date": today + timedelta(days=45),
                "actual_date": None,
                "decision": None,
                "decision_rationale": None,
                "conditions": [],
                "decision_makers": ["Dr. Yancopoulos", "Dr. Kim", "VP Hematology"],
                "key_data_reviewed": [],
                "next_gate_date": None,
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "SG-009",
                "program_id": "PGM-003",
                "gate_name": "FDA PDUFA Date Preparation Gate",
                "phase_from": ProgramPhase.NDA_SUBMISSION,
                "phase_to": ProgramPhase.POST_APPROVAL,
                "scheduled_date": today + timedelta(days=270),
                "actual_date": None,
                "decision": None,
                "decision_rationale": None,
                "conditions": [],
                "decision_makers": ["Dr. Yancopoulos", "Dr. Schleifer", "SVP Regulatory", "SVP Commercial"],
                "key_data_reviewed": [],
                "next_gate_date": None,
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "SG-010",
                "program_id": "PGM-001",
                "gate_name": "Phase 2 to Phase 3 Transition",
                "phase_from": ProgramPhase.PHASE_2,
                "phase_to": ProgramPhase.PHASE_3,
                "scheduled_date": today - timedelta(days=800),
                "actual_date": today - timedelta(days=798),
                "decision": StageGateDecision.GO,
                "decision_rationale": "Compelling Phase 2 data in COPD subpopulation; strong FEV1 improvement signal",
                "conditions": [],
                "decision_makers": ["Dr. Yancopoulos", "Dr. Schleifer"],
                "key_data_reviewed": ["Phase 2 top-line results", "Biomarker stratification", "Competitive landscape"],
                "next_gate_date": today - timedelta(days=120),
                "created_at": now - timedelta(days=850),
            },
        ]

        for g in gates_data:
            self._stage_gates[g["id"]] = StageGate(**g)

        # --- 14 Team Members ---
        team_data = [
            {"id": "TM-001", "program_id": "PGM-001", "name": "Dr. Sarah Chen", "role": GovernanceRole.PROGRAM_LEAD, "department": "Clinical Development", "allocation_pct": 80.0, "start_date": date(2021, 3, 15), "end_date": None, "active": True},
            {"id": "TM-002", "program_id": "PGM-001", "name": "Dr. George D. Yancopoulos", "role": GovernanceRole.EXECUTIVE_SPONSOR, "department": "Executive", "allocation_pct": 10.0, "start_date": date(2021, 3, 15), "end_date": None, "active": True},
            {"id": "TM-003", "program_id": "PGM-001", "name": "Dr. Rachel Greene", "role": GovernanceRole.MEDICAL_LEAD, "department": "Medical Affairs", "allocation_pct": 60.0, "start_date": date(2021, 6, 1), "end_date": None, "active": True},
            {"id": "TM-004", "program_id": "PGM-001", "name": "Karen Mitchell", "role": GovernanceRole.REGULATORY_LEAD, "department": "Regulatory Affairs", "allocation_pct": 50.0, "start_date": date(2021, 4, 1), "end_date": None, "active": True},
            {"id": "TM-005", "program_id": "PGM-002", "name": "Dr. Michael Torres", "role": GovernanceRole.PROGRAM_LEAD, "department": "Clinical Development", "allocation_pct": 75.0, "start_date": date(2022, 1, 10), "end_date": None, "active": True},
            {"id": "TM-006", "program_id": "PGM-002", "name": "Dr. Leonard S. Schleifer", "role": GovernanceRole.EXECUTIVE_SPONSOR, "department": "Executive", "allocation_pct": 5.0, "start_date": date(2022, 1, 10), "end_date": None, "active": True},
            {"id": "TM-007", "program_id": "PGM-003", "name": "Dr. Emily Watson", "role": GovernanceRole.PROGRAM_LEAD, "department": "Clinical Development", "allocation_pct": 90.0, "start_date": date(2019, 6, 1), "end_date": None, "active": True},
            {"id": "TM-008", "program_id": "PGM-003", "name": "Thomas Nguyen", "role": GovernanceRole.CMC_LEAD, "department": "CMC/Manufacturing", "allocation_pct": 70.0, "start_date": date(2020, 1, 15), "end_date": None, "active": True},
            {"id": "TM-009", "program_id": "PGM-004", "name": "Dr. James Park", "role": GovernanceRole.PROGRAM_LEAD, "department": "Clinical Development", "allocation_pct": 85.0, "start_date": date(2021, 9, 20), "end_date": None, "active": True},
            {"id": "TM-010", "program_id": "PGM-004", "name": "Jessica Adams", "role": GovernanceRole.COMMERCIAL_LEAD, "department": "Commercial Strategy", "allocation_pct": 40.0, "start_date": date(2023, 1, 1), "end_date": None, "active": True},
            {"id": "TM-011", "program_id": "PGM-005", "name": "Dr. Lisa Huang", "role": GovernanceRole.PROGRAM_LEAD, "department": "Clinical Development", "allocation_pct": 70.0, "start_date": date(2022, 6, 15), "end_date": None, "active": True},
            {"id": "TM-012", "program_id": "PGM-006", "name": "Dr. Robert Kim", "role": GovernanceRole.PROGRAM_LEAD, "department": "Clinical Development", "allocation_pct": 80.0, "start_date": date(2021, 1, 10), "end_date": None, "active": True},
            {"id": "TM-013", "program_id": "PGM-006", "name": "Sandra Patel", "role": GovernanceRole.FINANCE_LEAD, "department": "Finance", "allocation_pct": 30.0, "start_date": date(2021, 3, 1), "end_date": None, "active": True},
            {"id": "TM-014", "program_id": "PGM-001", "name": "David Chen", "role": GovernanceRole.CMC_LEAD, "department": "CMC/Manufacturing", "allocation_pct": 45.0, "start_date": date(2022, 1, 1), "end_date": None, "active": True},
        ]

        for t in team_data:
            self._team_members[t["id"]] = TeamMember(**t)

        # --- 8 Resource Allocations ---
        resources_data = [
            {"id": "RA-001", "program_id": "PGM-001", "resource_type": ResourceType.FTE, "description": "Phase 3 clinical operations team", "quantity": 25.0, "unit_cost": 200.0, "total_cost": 5000.0, "period_start": date(2025, 1, 1), "period_end": date(2025, 12, 31), "approved": True, "approved_by": "Dr. Yancopoulos", "created_at": now - timedelta(days=400)},
            {"id": "RA-002", "program_id": "PGM-001", "resource_type": ResourceType.VENDOR, "description": "CRO services - ICON PLC", "quantity": 1.0, "unit_cost": 45000.0, "total_cost": 45000.0, "period_start": date(2024, 6, 1), "period_end": date(2026, 6, 30), "approved": True, "approved_by": "SVP Clinical Ops", "created_at": now - timedelta(days=600)},
            {"id": "RA-003", "program_id": "PGM-002", "resource_type": ResourceType.BUDGET, "description": "Phase 2b expansion cohort funding", "quantity": 1.0, "unit_cost": 15000.0, "total_cost": 15000.0, "period_start": date(2025, 7, 1), "period_end": date(2026, 6, 30), "approved": True, "approved_by": "CFO", "created_at": now - timedelta(days=200)},
            {"id": "RA-004", "program_id": "PGM-003", "resource_type": ResourceType.FTE, "description": "Regulatory submission team", "quantity": 12.0, "unit_cost": 220.0, "total_cost": 2640.0, "period_start": date(2025, 10, 1), "period_end": date(2026, 6, 30), "approved": True, "approved_by": "SVP Regulatory", "created_at": now - timedelta(days=120)},
            {"id": "RA-005", "program_id": "PGM-004", "resource_type": ResourceType.FACILITY, "description": "Dedicated manufacturing suite allocation", "quantity": 1.0, "unit_cost": 8000.0, "total_cost": 8000.0, "period_start": date(2025, 1, 1), "period_end": date(2027, 12, 31), "approved": True, "approved_by": "SVP Manufacturing", "created_at": now - timedelta(days=500)},
            {"id": "RA-006", "program_id": "PGM-006", "resource_type": ResourceType.VENDOR, "description": "Central lab services - Covance", "quantity": 1.0, "unit_cost": 12000.0, "total_cost": 12000.0, "period_start": date(2025, 1, 1), "period_end": date(2026, 12, 31), "approved": True, "approved_by": "VP Clinical Ops", "created_at": now - timedelta(days=350)},
            {"id": "RA-007", "program_id": "PGM-005", "resource_type": ResourceType.EQUIPMENT, "description": "Biomarker assay platform", "quantity": 3.0, "unit_cost": 500.0, "total_cost": 1500.0, "period_start": date(2025, 6, 1), "period_end": date(2026, 5, 31), "approved": False, "approved_by": None, "created_at": now - timedelta(days=30)},
            {"id": "RA-008", "program_id": "PGM-002", "resource_type": ResourceType.FTE, "description": "Translational medicine support", "quantity": 5.0, "unit_cost": 250.0, "total_cost": 1250.0, "period_start": date(2026, 1, 1), "period_end": date(2026, 12, 31), "approved": False, "approved_by": None, "created_at": now - timedelta(days=15)},
        ]

        for r in resources_data:
            self._resource_allocations[r["id"]] = ResourceAllocation(**r)

        # --- 7 Portfolio Prioritizations ---
        prioritizations_data = [
            {"id": "PP-001", "program_id": "PGM-001", "strategic_alignment_score": 95.0, "probability_of_success": 72.0, "npv_estimate": 4200.0, "peak_revenue_estimate": 3500.0, "unmet_need_score": 85.0, "competitive_position_score": 80.0, "overall_priority_score": 88.0, "rank": 1, "assessment_date": today - timedelta(days=30), "assessed_by": "Portfolio Review Committee"},
            {"id": "PP-002", "program_id": "PGM-003", "strategic_alignment_score": 90.0, "probability_of_success": 85.0, "npv_estimate": 2800.0, "peak_revenue_estimate": 1800.0, "unmet_need_score": 90.0, "competitive_position_score": 75.0, "overall_priority_score": 86.0, "rank": 2, "assessment_date": today - timedelta(days=30), "assessed_by": "Portfolio Review Committee"},
            {"id": "PP-003", "program_id": "PGM-006", "strategic_alignment_score": 88.0, "probability_of_success": 65.0, "npv_estimate": 3100.0, "peak_revenue_estimate": 2500.0, "unmet_need_score": 88.0, "competitive_position_score": 70.0, "overall_priority_score": 82.0, "rank": 3, "assessment_date": today - timedelta(days=30), "assessed_by": "Portfolio Review Committee"},
            {"id": "PP-004", "program_id": "PGM-004", "strategic_alignment_score": 85.0, "probability_of_success": 55.0, "npv_estimate": 2200.0, "peak_revenue_estimate": 1500.0, "unmet_need_score": 75.0, "competitive_position_score": 65.0, "overall_priority_score": 72.0, "rank": 4, "assessment_date": today - timedelta(days=30), "assessed_by": "Portfolio Review Committee"},
            {"id": "PP-005", "program_id": "PGM-002", "strategic_alignment_score": 80.0, "probability_of_success": 45.0, "npv_estimate": 1800.0, "peak_revenue_estimate": 1200.0, "unmet_need_score": 70.0, "competitive_position_score": 60.0, "overall_priority_score": 65.0, "rank": 5, "assessment_date": today - timedelta(days=30), "assessed_by": "Portfolio Review Committee"},
            {"id": "PP-006", "program_id": "PGM-005", "strategic_alignment_score": 75.0, "probability_of_success": 40.0, "npv_estimate": 1500.0, "peak_revenue_estimate": 900.0, "unmet_need_score": 80.0, "competitive_position_score": 55.0, "overall_priority_score": 60.0, "rank": 6, "assessment_date": today - timedelta(days=30), "assessed_by": "Portfolio Review Committee"},
            {"id": "PP-007", "program_id": "PGM-007", "strategic_alignment_score": 60.0, "probability_of_success": 95.0, "npv_estimate": 150.0, "peak_revenue_estimate": 80.0, "unmet_need_score": 95.0, "competitive_position_score": 90.0, "overall_priority_score": 55.0, "rank": 7, "assessment_date": today - timedelta(days=30), "assessed_by": "Portfolio Review Committee"},
        ]

        for pp in prioritizations_data:
            self._prioritizations[pp["id"]] = PortfolioPrioritization(**pp)

        # --- 6 Risk Register Entries ---
        risks_data = [
            {"id": "RR-001", "program_id": "PGM-001", "risk_description": "Competitor dupilumab biosimilar filing may erode market exclusivity window", "category": RiskCategory.COMMERCIAL, "probability": 0.6, "impact": 4.0, "risk_score": 2.4, "mitigation_plan": "Accelerate lifecycle management strategy; file for additional indications", "owner": "SVP Commercial", "status": RiskStatus.MITIGATING, "identified_date": today - timedelta(days=180), "target_resolution_date": today + timedelta(days=365), "created_at": now - timedelta(days=180)},
            {"id": "RR-002", "program_id": "PGM-002", "risk_description": "Phase 2 biomarker stratification may not translate to Phase 3 patient selection", "category": RiskCategory.SCIENTIFIC, "probability": 0.4, "impact": 4.5, "risk_score": 1.8, "mitigation_plan": "Expand biomarker panel; engage KOLs for protocol design input", "owner": "Dr. Torres", "status": RiskStatus.OPEN, "identified_date": today - timedelta(days=90), "target_resolution_date": today + timedelta(days=180), "created_at": now - timedelta(days=90)},
            {"id": "RR-003", "program_id": "PGM-003", "risk_description": "FDA may issue Complete Response Letter requiring additional clinical data", "category": RiskCategory.REGULATORY, "probability": 0.25, "impact": 5.0, "risk_score": 1.25, "mitigation_plan": "Pre-submission meetings; robust CMC package; proactive FDA engagement", "owner": "SVP Regulatory", "status": RiskStatus.MITIGATING, "identified_date": today - timedelta(days=60), "target_resolution_date": today + timedelta(days=270), "created_at": now - timedelta(days=60)},
            {"id": "RR-004", "program_id": "PGM-004", "risk_description": "Manufacturing scale-up challenges for bispecific antibody combination", "category": RiskCategory.SUPPLY_CHAIN, "probability": 0.35, "impact": 3.5, "risk_score": 1.225, "mitigation_plan": "Invest in backup manufacturing site; optimize cell line productivity", "owner": "SVP Manufacturing", "status": RiskStatus.OPEN, "identified_date": today - timedelta(days=120), "target_resolution_date": today + timedelta(days=240), "created_at": now - timedelta(days=120)},
            {"id": "RR-005", "program_id": "PGM-006", "risk_description": "Budget overrun risk due to expanded Phase 3 sample size requirement", "category": RiskCategory.FINANCIAL, "probability": 0.5, "impact": 3.0, "risk_score": 1.5, "mitigation_plan": "Implement adaptive trial design; negotiate volume discounts with CRO", "owner": "Sandra Patel", "status": RiskStatus.OPEN, "identified_date": today - timedelta(days=45), "target_resolution_date": today + timedelta(days=120), "created_at": now - timedelta(days=45)},
            {"id": "RR-006", "program_id": "PGM-001", "risk_description": "Key opinion leader departure may impact advisory board engagement", "category": RiskCategory.OPERATIONAL, "probability": 0.2, "impact": 2.5, "risk_score": 0.5, "mitigation_plan": "Maintain diverse KOL network; cross-train internal medical science liaisons", "owner": "Dr. Rachel Greene", "status": RiskStatus.ACCEPTED, "identified_date": today - timedelta(days=200), "target_resolution_date": None, "created_at": now - timedelta(days=200)},
        ]

        for r in risks_data:
            self._risks[r["id"]] = RiskRegister(**r)

    # ------------------------------------------------------------------
    # Program CRUD
    # ------------------------------------------------------------------

    def list_programs(
        self,
        *,
        phase: ProgramPhase | None = None,
        status: ProgramStatus | None = None,
        priority: PriorityLevel | None = None,
        therapeutic_area: str | None = None,
    ) -> list[Program]:
        """List programs with optional filters."""
        with self._lock:
            result = list(self._programs.values())

        if phase is not None:
            result = [p for p in result if p.phase == phase]
        if status is not None:
            result = [p for p in result if p.status == status]
        if priority is not None:
            result = [p for p in result if p.strategic_priority == priority]
        if therapeutic_area is not None:
            result = [p for p in result if p.therapeutic_area.lower() == therapeutic_area.lower()]

        return sorted(result, key=lambda p: p.id)

    def get_program(self, program_id: str) -> Program | None:
        """Get a single program by ID."""
        with self._lock:
            return self._programs.get(program_id)

    def create_program(self, payload: ProgramCreate) -> Program:
        """Create a new program."""
        now = datetime.now(timezone.utc)
        program_id = f"PGM-{uuid4().hex[:8].upper()}"
        program = Program(
            id=program_id,
            spent_budget=0.0,
            status=ProgramStatus.ACTIVE,
            created_at=now,
            updated_at=now,
            **payload.model_dump(),
        )
        with self._lock:
            self._programs[program_id] = program
        logger.info("Created program %s: %s", program_id, payload.name)
        return program

    def update_program(self, program_id: str, payload: ProgramUpdate) -> Program | None:
        """Update an existing program."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._programs.get(program_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            data["updated_at"] = now
            updated = Program(**data)
            self._programs[program_id] = updated
        return updated

    def delete_program(self, program_id: str) -> bool:
        """Delete a program. Returns True if deleted."""
        with self._lock:
            if program_id in self._programs:
                del self._programs[program_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Stage Gate CRUD
    # ------------------------------------------------------------------

    def list_stage_gates(
        self,
        *,
        program_id: str | None = None,
        decision: StageGateDecision | None = None,
        pending: bool | None = None,
    ) -> list[StageGate]:
        """List stage gates with optional filters."""
        with self._lock:
            result = list(self._stage_gates.values())

        if program_id is not None:
            result = [g for g in result if g.program_id == program_id]
        if decision is not None:
            result = [g for g in result if g.decision == decision]
        if pending is not None:
            if pending:
                result = [g for g in result if g.decision is None]
            else:
                result = [g for g in result if g.decision is not None]

        return sorted(result, key=lambda g: g.scheduled_date)

    def get_stage_gate(self, gate_id: str) -> StageGate | None:
        """Get a single stage gate by ID."""
        with self._lock:
            return self._stage_gates.get(gate_id)

    def create_stage_gate(self, payload: StageGateCreate) -> StageGate:
        """Create a new stage gate."""
        now = datetime.now(timezone.utc)
        with self._lock:
            if payload.program_id not in self._programs:
                raise ValueError(f"Program '{payload.program_id}' not found")

        gate_id = f"SG-{uuid4().hex[:8].upper()}"
        gate = StageGate(
            id=gate_id,
            program_id=payload.program_id,
            gate_name=payload.gate_name,
            phase_from=payload.phase_from,
            phase_to=payload.phase_to,
            scheduled_date=payload.scheduled_date,
            actual_date=None,
            decision=None,
            decision_rationale=None,
            conditions=[],
            decision_makers=payload.decision_makers,
            key_data_reviewed=[],
            next_gate_date=None,
            created_at=now,
        )
        with self._lock:
            self._stage_gates[gate_id] = gate
        logger.info("Created stage gate %s for program %s", gate_id, payload.program_id)
        return gate

    def update_stage_gate(self, gate_id: str, payload: StageGateUpdate) -> StageGate | None:
        """Update a stage gate."""
        with self._lock:
            existing = self._stage_gates.get(gate_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = StageGate(**data)
            self._stage_gates[gate_id] = updated
        return updated

    def delete_stage_gate(self, gate_id: str) -> bool:
        """Delete a stage gate."""
        with self._lock:
            if gate_id in self._stage_gates:
                del self._stage_gates[gate_id]
                return True
            return False

    def advance_stage_gate(
        self,
        gate_id: str,
        payload: AdvanceStageGateRequest,
    ) -> StageGate | None:
        """Advance a stage gate with a decision.

        If decision is GO, also advances the program phase.
        """
        with self._lock:
            existing = self._stage_gates.get(gate_id)
            if existing is None:
                return None

            if existing.decision is not None:
                raise ValueError(f"Stage gate '{gate_id}' already has a decision: {existing.decision.value}")

            data = existing.model_dump()
            data["decision"] = payload.decision
            data["decision_rationale"] = payload.decision_rationale
            data["actual_date"] = payload.actual_date
            data["conditions"] = payload.conditions
            data["key_data_reviewed"] = payload.key_data_reviewed
            data["next_gate_date"] = payload.next_gate_date
            updated_gate = StageGate(**data)
            self._stage_gates[gate_id] = updated_gate

            # If GO decision, advance the program phase
            if payload.decision == StageGateDecision.GO:
                program = self._programs.get(existing.program_id)
                if program is not None and existing.phase_from != existing.phase_to:
                    prog_data = program.model_dump()
                    prog_data["phase"] = existing.phase_to
                    prog_data["updated_at"] = datetime.now(timezone.utc)
                    self._programs[existing.program_id] = Program(**prog_data)
                    logger.info(
                        "Advanced program %s from %s to %s",
                        existing.program_id,
                        existing.phase_from.value,
                        existing.phase_to.value,
                    )

            # If HOLD, put program on hold
            if payload.decision == StageGateDecision.HOLD:
                program = self._programs.get(existing.program_id)
                if program is not None:
                    prog_data = program.model_dump()
                    prog_data["status"] = ProgramStatus.ON_HOLD
                    prog_data["updated_at"] = datetime.now(timezone.utc)
                    self._programs[existing.program_id] = Program(**prog_data)

            # If NO_GO, terminate the program
            if payload.decision == StageGateDecision.NO_GO:
                program = self._programs.get(existing.program_id)
                if program is not None:
                    prog_data = program.model_dump()
                    prog_data["status"] = ProgramStatus.TERMINATED
                    prog_data["updated_at"] = datetime.now(timezone.utc)
                    self._programs[existing.program_id] = Program(**prog_data)

        return updated_gate

    # ------------------------------------------------------------------
    # Team Member CRUD
    # ------------------------------------------------------------------

    def list_team_members(
        self,
        *,
        program_id: str | None = None,
        role: GovernanceRole | None = None,
        active: bool | None = None,
    ) -> list[TeamMember]:
        """List team members with optional filters."""
        with self._lock:
            result = list(self._team_members.values())

        if program_id is not None:
            result = [t for t in result if t.program_id == program_id]
        if role is not None:
            result = [t for t in result if t.role == role]
        if active is not None:
            result = [t for t in result if t.active == active]

        return sorted(result, key=lambda t: t.id)

    def get_team_member(self, member_id: str) -> TeamMember | None:
        """Get a single team member by ID."""
        with self._lock:
            return self._team_members.get(member_id)

    def create_team_member(self, payload: TeamMemberCreate) -> TeamMember:
        """Add a team member to a program."""
        with self._lock:
            if payload.program_id not in self._programs:
                raise ValueError(f"Program '{payload.program_id}' not found")

        member_id = f"TM-{uuid4().hex[:8].upper()}"
        member = TeamMember(
            id=member_id,
            active=True,
            **payload.model_dump(),
        )
        with self._lock:
            self._team_members[member_id] = member
        logger.info("Added team member %s to program %s", member_id, payload.program_id)
        return member

    def update_team_member(self, member_id: str, payload: TeamMemberUpdate) -> TeamMember | None:
        """Update a team member assignment."""
        with self._lock:
            existing = self._team_members.get(member_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = TeamMember(**data)
            self._team_members[member_id] = updated
        return updated

    def delete_team_member(self, member_id: str) -> bool:
        """Delete a team member assignment."""
        with self._lock:
            if member_id in self._team_members:
                del self._team_members[member_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Resource Allocation CRUD
    # ------------------------------------------------------------------

    def list_resource_allocations(
        self,
        *,
        program_id: str | None = None,
        resource_type: ResourceType | None = None,
        approved: bool | None = None,
    ) -> list[ResourceAllocation]:
        """List resource allocations with optional filters."""
        with self._lock:
            result = list(self._resource_allocations.values())

        if program_id is not None:
            result = [r for r in result if r.program_id == program_id]
        if resource_type is not None:
            result = [r for r in result if r.resource_type == resource_type]
        if approved is not None:
            result = [r for r in result if r.approved == approved]

        return sorted(result, key=lambda r: r.id)

    def get_resource_allocation(self, allocation_id: str) -> ResourceAllocation | None:
        """Get a single resource allocation by ID."""
        with self._lock:
            return self._resource_allocations.get(allocation_id)

    def create_resource_allocation(self, payload: ResourceAllocationCreate) -> ResourceAllocation:
        """Allocate a resource to a program."""
        now = datetime.now(timezone.utc)
        with self._lock:
            if payload.program_id not in self._programs:
                raise ValueError(f"Program '{payload.program_id}' not found")

        alloc_id = f"RA-{uuid4().hex[:8].upper()}"
        total_cost = round(payload.quantity * payload.unit_cost, 2)
        alloc = ResourceAllocation(
            id=alloc_id,
            total_cost=total_cost,
            approved=False,
            approved_by=None,
            created_at=now,
            **payload.model_dump(),
        )
        with self._lock:
            self._resource_allocations[alloc_id] = alloc
        logger.info("Created resource allocation %s for program %s", alloc_id, payload.program_id)
        return alloc

    def update_resource_allocation(
        self,
        allocation_id: str,
        payload: ResourceAllocationUpdate,
    ) -> ResourceAllocation | None:
        """Update a resource allocation."""
        with self._lock:
            existing = self._resource_allocations.get(allocation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            # Recalculate total cost if quantity or unit_cost changed
            quantity = data.get("quantity", existing.quantity)
            unit_cost = data.get("unit_cost", existing.unit_cost)
            data["total_cost"] = round(quantity * unit_cost, 2)
            updated = ResourceAllocation(**data)
            self._resource_allocations[allocation_id] = updated
        return updated

    def delete_resource_allocation(self, allocation_id: str) -> bool:
        """Delete a resource allocation."""
        with self._lock:
            if allocation_id in self._resource_allocations:
                del self._resource_allocations[allocation_id]
                return True
            return False

    def allocate_resources(
        self,
        program_id: str,
        payload: ResourceAllocationCreate,
    ) -> ResourceAllocation:
        """Convenience method to allocate resources ensuring program exists."""
        with self._lock:
            if program_id not in self._programs:
                raise ValueError(f"Program '{program_id}' not found")

        return self.create_resource_allocation(payload)

    # ------------------------------------------------------------------
    # Portfolio Prioritization
    # ------------------------------------------------------------------

    def list_prioritizations(
        self,
        *,
        program_id: str | None = None,
    ) -> list[PortfolioPrioritization]:
        """List prioritization assessments."""
        with self._lock:
            result = list(self._prioritizations.values())

        if program_id is not None:
            result = [p for p in result if p.program_id == program_id]

        return sorted(result, key=lambda p: p.rank)

    def get_prioritization(self, prioritization_id: str) -> PortfolioPrioritization | None:
        """Get a single prioritization by ID."""
        with self._lock:
            return self._prioritizations.get(prioritization_id)

    def create_prioritization(
        self,
        payload: PortfolioPrioritizationCreate,
    ) -> PortfolioPrioritization:
        """Create a portfolio prioritization assessment with computed score."""
        with self._lock:
            if payload.program_id not in self._programs:
                raise ValueError(f"Program '{payload.program_id}' not found")

        # Compute overall priority score: weighted average
        overall_score = round(
            (
                payload.strategic_alignment_score * 0.25
                + payload.probability_of_success * 0.20
                + min(payload.npv_estimate / 50.0, 100.0) * 0.20  # Normalize NPV
                + payload.unmet_need_score * 0.20
                + payload.competitive_position_score * 0.15
            ),
            1,
        )

        # Determine rank based on existing prioritizations
        with self._lock:
            existing_scores = sorted(
                [p.overall_priority_score for p in self._prioritizations.values()],
                reverse=True,
            )
        rank = 1
        for score in existing_scores:
            if overall_score < score:
                rank += 1

        prio_id = f"PP-{uuid4().hex[:8].upper()}"
        prio = PortfolioPrioritization(
            id=prio_id,
            program_id=payload.program_id,
            strategic_alignment_score=payload.strategic_alignment_score,
            probability_of_success=payload.probability_of_success,
            npv_estimate=payload.npv_estimate,
            peak_revenue_estimate=payload.peak_revenue_estimate,
            unmet_need_score=payload.unmet_need_score,
            competitive_position_score=payload.competitive_position_score,
            overall_priority_score=overall_score,
            rank=rank,
            assessment_date=date.today(),
            assessed_by=payload.assessed_by,
        )

        with self._lock:
            self._prioritizations[prio_id] = prio
        logger.info("Created prioritization %s for program %s (score=%.1f, rank=%d)", prio_id, payload.program_id, overall_score, rank)
        return prio

    def prioritize_portfolio(self) -> list[PortfolioPrioritization]:
        """Re-rank all prioritizations by overall_priority_score descending.

        Returns the updated ranked list.
        """
        with self._lock:
            prios = list(self._prioritizations.values())
            prios.sort(key=lambda p: p.overall_priority_score, reverse=True)
            for i, prio in enumerate(prios, start=1):
                data = prio.model_dump()
                data["rank"] = i
                self._prioritizations[prio.id] = PortfolioPrioritization(**data)
            return sorted(self._prioritizations.values(), key=lambda p: p.rank)

    # ------------------------------------------------------------------
    # Risk Register
    # ------------------------------------------------------------------

    def list_risks(
        self,
        *,
        program_id: str | None = None,
        category: RiskCategory | None = None,
        status: RiskStatus | None = None,
    ) -> list[RiskRegister]:
        """List risk register entries with optional filters."""
        with self._lock:
            result = list(self._risks.values())

        if program_id is not None:
            result = [r for r in result if r.program_id == program_id]
        if category is not None:
            result = [r for r in result if r.category == category]
        if status is not None:
            result = [r for r in result if r.status == status]

        return sorted(result, key=lambda r: r.risk_score, reverse=True)

    def get_risk(self, risk_id: str) -> RiskRegister | None:
        """Get a single risk by ID."""
        with self._lock:
            return self._risks.get(risk_id)

    def register_risk(self, payload: RiskRegisterCreate) -> RiskRegister:
        """Register a new risk in the risk register."""
        now = datetime.now(timezone.utc)
        with self._lock:
            if payload.program_id not in self._programs:
                raise ValueError(f"Program '{payload.program_id}' not found")

        risk_id = f"RR-{uuid4().hex[:8].upper()}"
        risk_score = round(payload.probability * payload.impact, 3)
        risk = RiskRegister(
            id=risk_id,
            program_id=payload.program_id,
            risk_description=payload.risk_description,
            category=payload.category,
            probability=payload.probability,
            impact=payload.impact,
            risk_score=risk_score,
            mitigation_plan=payload.mitigation_plan,
            owner=payload.owner,
            status=RiskStatus.OPEN,
            identified_date=date.today(),
            target_resolution_date=payload.target_resolution_date,
            created_at=now,
        )
        with self._lock:
            self._risks[risk_id] = risk
        logger.info("Registered risk %s for program %s (score=%.2f)", risk_id, payload.program_id, risk_score)
        return risk

    def update_risk(self, risk_id: str, payload: RiskRegisterUpdate) -> RiskRegister | None:
        """Update a risk register entry."""
        with self._lock:
            existing = self._risks.get(risk_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            # Recalculate risk score if probability or impact changed
            prob = data.get("probability", existing.probability)
            impact = data.get("impact", existing.impact)
            data["risk_score"] = round(prob * impact, 3)
            updated = RiskRegister(**data)
            self._risks[risk_id] = updated
        return updated

    def delete_risk(self, risk_id: str) -> bool:
        """Delete a risk register entry."""
        with self._lock:
            if risk_id in self._risks:
                del self._risks[risk_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> GovernanceMetrics:
        """Compute aggregated portfolio governance metrics."""
        today = date.today()

        with self._lock:
            programs = list(self._programs.values())
            gates = list(self._stage_gates.values())
            members = list(self._team_members.values())
            allocations = list(self._resource_allocations.values())
            prios = list(self._prioritizations.values())
            risks = list(self._risks.values())

        active_programs = [p for p in programs if p.status == ProgramStatus.ACTIVE]

        # Programs by phase
        by_phase: dict[str, int] = {}
        for p in programs:
            key = p.phase.value
            by_phase[key] = by_phase.get(key, 0) + 1

        # Programs by priority
        by_priority: dict[str, int] = {}
        for p in programs:
            key = p.strategic_priority.value
            by_priority[key] = by_priority.get(key, 0) + 1

        # Budget
        total_budget = sum(p.total_budget for p in programs)
        total_spent = sum(p.spent_budget for p in programs)
        budget_util = round((total_spent / total_budget * 100) if total_budget > 0 else 0.0, 1)

        # Stage gates
        upcoming = sum(
            1 for g in gates
            if g.decision is None and g.scheduled_date <= today + timedelta(days=90)
        )
        overdue = sum(
            1 for g in gates
            if g.decision is None and g.scheduled_date < today
        )

        # Team
        active_members = [m for m in members if m.active]
        avg_alloc = round(
            sum(m.allocation_pct for m in active_members) / max(1, len(active_members)),
            1,
        )

        # Risks
        open_risks = sum(1 for r in risks if r.status in (RiskStatus.OPEN, RiskStatus.MITIGATING))
        high_impact = sum(1 for r in risks if r.risk_score >= HIGH_RISK_SCORE_THRESHOLD and r.status != RiskStatus.RESOLVED)

        # Resources
        pending_approvals = sum(1 for a in allocations if not a.approved)

        # Prioritization
        avg_pos = round(
            sum(p.probability_of_success for p in prios) / max(1, len(prios)),
            1,
        )
        total_npv = round(sum(p.npv_estimate for p in prios), 1)

        return GovernanceMetrics(
            total_programs=len(programs),
            active_programs=len(active_programs),
            programs_by_phase=by_phase,
            programs_by_priority=by_priority,
            total_portfolio_budget=total_budget,
            total_portfolio_spent=total_spent,
            budget_utilization_pct=budget_util,
            upcoming_stage_gates=upcoming,
            overdue_stage_gates=overdue,
            total_team_members=len(active_members),
            avg_team_allocation=avg_alloc,
            open_risks=open_risks,
            high_impact_risks=high_impact,
            total_resource_allocations=len(allocations),
            pending_approvals=pending_approvals,
            avg_probability_of_success=avg_pos,
            total_npv=total_npv,
        )

    def get_portfolio_dashboard(self) -> PortfolioDashboard:
        """Get the executive portfolio dashboard."""
        today = date.today()
        metrics = self.get_metrics()

        with self._lock:
            active_programs = [
                p for p in self._programs.values()
                if p.status == ProgramStatus.ACTIVE
            ]
            upcoming_gates = sorted(
                [
                    g for g in self._stage_gates.values()
                    if g.decision is None and g.scheduled_date <= today + timedelta(days=90)
                ],
                key=lambda g: g.scheduled_date,
            )
            top_risks = sorted(
                [
                    r for r in self._risks.values()
                    if r.status in (RiskStatus.OPEN, RiskStatus.MITIGATING)
                ],
                key=lambda r: r.risk_score,
                reverse=True,
            )[:10]
            rankings = sorted(
                self._prioritizations.values(),
                key=lambda p: p.rank,
            )

        return PortfolioDashboard(
            metrics=metrics,
            programs=sorted(active_programs, key=lambda p: p.id),
            upcoming_gates=upcoming_gates,
            top_risks=top_risks,
            priority_rankings=list(rankings),
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: PortfolioGovernanceService | None = None
_instance_lock = threading.Lock()


def get_portfolio_governance_service() -> PortfolioGovernanceService:
    """Return the singleton PortfolioGovernanceService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = PortfolioGovernanceService()
    return _instance


def reset_portfolio_governance_service() -> PortfolioGovernanceService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = PortfolioGovernanceService()
    return _instance
