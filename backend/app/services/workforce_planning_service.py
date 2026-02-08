"""Workforce Capacity Planning Service (COO-4).

Provides workforce analytics for a pharma-regulated clinical trial
patient recruitment platform:
- Team member management (CRUD)
- Capacity requirement tracking
- Hiring pipeline management
- Workforce KPI metrics
- Capacity projections with hiring pipeline
- Utilization analysis by department
- Skill gap identification

All data lives in-memory; in production this would be backed by an
HRIS / workforce management system.
"""

from __future__ import annotations

import logging
import math
import threading
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from app.schemas.workforce_planning import (
    CapacityProjection,
    CapacityProjectionResponse,
    CapacityRequirement,
    CapacityRequirementListResponse,
    Department,
    DepartmentCapacity,
    DepartmentUtilization,
    HiringPlan,
    HiringPlanListResponse,
    HiringStatus,
    Priority,
    SkillGap,
    SkillGapReport,
    SkillLevel,
    TeamMember,
    TeamMemberListResponse,
    UtilizationReport,
    WorkforceMetrics,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton plumbing
# ---------------------------------------------------------------------------

_service: WorkforcePlanningService | None = None
_service_lock = threading.Lock()


def get_workforce_planning_service() -> WorkforcePlanningService:
    """Return the singleton WorkforcePlanningService instance."""
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = WorkforcePlanningService()
    return _service


def reset_workforce_planning_service() -> None:
    """Reset the singleton (for testing)."""
    global _service
    with _service_lock:
        _service = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class WorkforcePlanningService:
    """In-memory workforce capacity planning engine."""

    def __init__(self) -> None:
        self._team_members: dict[str, TeamMember] = {}
        self._capacity_requirements: dict[str, CapacityRequirement] = {}
        self._hiring_plans: dict[str, HiringPlan] = {}
        self._populate_team_members()
        self._populate_capacity_requirements()
        self._populate_hiring_plans()

    # ------------------------------------------------------------------
    # Seed data
    # ------------------------------------------------------------------

    def _populate_team_members(self) -> None:
        """Pre-populate ~28 realistic team members across all departments."""
        seed: list[dict[str, Any]] = [
            # ENGINEERING (8 members)
            {
                "name": "Sarah Chen",
                "department": Department.ENGINEERING,
                "role": "Senior Backend Engineer",
                "skill_level": SkillLevel.SENIOR,
                "fte_equivalent": 1.0,
                "hire_date": date(2023, 3, 15),
                "annual_cost": 185_000.0,
                "utilization_pct": 88.0,
                "certifications": ["AWS Solutions Architect", "HIPAA Security"],
                "can_handle_phi": True,
            },
            {
                "name": "Marcus Johnson",
                "department": Department.ENGINEERING,
                "role": "Lead Platform Engineer",
                "skill_level": SkillLevel.LEAD,
                "fte_equivalent": 1.0,
                "hire_date": date(2022, 8, 1),
                "annual_cost": 210_000.0,
                "utilization_pct": 92.0,
                "certifications": ["AWS DevOps Professional", "Kubernetes CKA"],
                "can_handle_phi": True,
            },
            {
                "name": "Priya Patel",
                "department": Department.ENGINEERING,
                "role": "Frontend Engineer",
                "skill_level": SkillLevel.MID,
                "fte_equivalent": 1.0,
                "hire_date": date(2024, 1, 10),
                "annual_cost": 145_000.0,
                "utilization_pct": 82.0,
                "certifications": [],
                "can_handle_phi": False,
            },
            {
                "name": "David Kim",
                "department": Department.ENGINEERING,
                "role": "Backend Engineer",
                "skill_level": SkillLevel.MID,
                "fte_equivalent": 1.0,
                "hire_date": date(2023, 11, 20),
                "annual_cost": 155_000.0,
                "utilization_pct": 85.0,
                "certifications": ["HIPAA Security"],
                "can_handle_phi": True,
            },
            {
                "name": "Elena Rodriguez",
                "department": Department.ENGINEERING,
                "role": "Junior Backend Engineer",
                "skill_level": SkillLevel.JUNIOR,
                "fte_equivalent": 1.0,
                "hire_date": date(2024, 6, 3),
                "annual_cost": 115_000.0,
                "utilization_pct": 75.0,
                "certifications": [],
                "can_handle_phi": False,
            },
            {
                "name": "James Wilson",
                "department": Department.ENGINEERING,
                "role": "Senior Infrastructure Engineer",
                "skill_level": SkillLevel.SENIOR,
                "fte_equivalent": 1.0,
                "hire_date": date(2023, 5, 22),
                "annual_cost": 180_000.0,
                "utilization_pct": 90.0,
                "certifications": ["AWS Solutions Architect", "Terraform Associate"],
                "can_handle_phi": True,
            },
            {
                "name": "Aisha Mohammed",
                "department": Department.ENGINEERING,
                "role": "QA Engineer",
                "skill_level": SkillLevel.MID,
                "fte_equivalent": 1.0,
                "hire_date": date(2024, 2, 14),
                "annual_cost": 130_000.0,
                "utilization_pct": 78.0,
                "certifications": ["ISTQB Foundation"],
                "can_handle_phi": False,
            },
            {
                "name": "Robert Taylor",
                "department": Department.ENGINEERING,
                "role": "Principal Engineer",
                "skill_level": SkillLevel.PRINCIPAL,
                "fte_equivalent": 1.0,
                "hire_date": date(2022, 1, 15),
                "annual_cost": 250_000.0,
                "utilization_pct": 95.0,
                "certifications": ["AWS Solutions Architect Professional", "HIPAA Security"],
                "can_handle_phi": True,
            },
            # CLINICAL_OPS (5 members)
            {
                "name": "Dr. Jennifer Blake",
                "department": Department.CLINICAL_OPS,
                "role": "Clinical Data Manager",
                "skill_level": SkillLevel.SENIOR,
                "fte_equivalent": 1.0,
                "hire_date": date(2023, 2, 1),
                "annual_cost": 140_000.0,
                "utilization_pct": 87.0,
                "certifications": ["CCDM", "GCP"],
                "can_handle_phi": True,
            },
            {
                "name": "Michael Torres",
                "department": Department.CLINICAL_OPS,
                "role": "Trial Protocol Analyst",
                "skill_level": SkillLevel.MID,
                "fte_equivalent": 1.0,
                "hire_date": date(2023, 9, 18),
                "annual_cost": 120_000.0,
                "utilization_pct": 83.0,
                "certifications": ["GCP", "CCRP"],
                "can_handle_phi": True,
            },
            {
                "name": "Lisa Nakamura",
                "department": Department.CLINICAL_OPS,
                "role": "Medical Affairs Specialist",
                "skill_level": SkillLevel.SENIOR,
                "fte_equivalent": 1.0,
                "hire_date": date(2022, 11, 7),
                "annual_cost": 150_000.0,
                "utilization_pct": 80.0,
                "certifications": ["GCP", "RAC"],
                "can_handle_phi": True,
            },
            {
                "name": "Carlos Mendez",
                "department": Department.CLINICAL_OPS,
                "role": "Clinical Operations Coordinator",
                "skill_level": SkillLevel.JUNIOR,
                "fte_equivalent": 1.0,
                "hire_date": date(2024, 4, 15),
                "annual_cost": 85_000.0,
                "utilization_pct": 72.0,
                "certifications": ["GCP"],
                "can_handle_phi": True,
            },
            {
                "name": "Amanda Foster",
                "department": Department.CLINICAL_OPS,
                "role": "Lead Clinical Operations",
                "skill_level": SkillLevel.LEAD,
                "fte_equivalent": 1.0,
                "hire_date": date(2022, 6, 1),
                "annual_cost": 175_000.0,
                "utilization_pct": 91.0,
                "certifications": ["GCP", "CCDM", "PMP"],
                "can_handle_phi": True,
            },
            # DATA_SCIENCE (4 members)
            {
                "name": "Dr. Wei Zhang",
                "department": Department.DATA_SCIENCE,
                "role": "Senior ML Engineer",
                "skill_level": SkillLevel.SENIOR,
                "fte_equivalent": 1.0,
                "hire_date": date(2023, 4, 10),
                "annual_cost": 195_000.0,
                "utilization_pct": 86.0,
                "certifications": ["AWS ML Specialty"],
                "can_handle_phi": True,
            },
            {
                "name": "Rachel Green",
                "department": Department.DATA_SCIENCE,
                "role": "Data Scientist",
                "skill_level": SkillLevel.MID,
                "fte_equivalent": 1.0,
                "hire_date": date(2024, 1, 22),
                "annual_cost": 160_000.0,
                "utilization_pct": 79.0,
                "certifications": [],
                "can_handle_phi": False,
            },
            {
                "name": "Ahmed Hassan",
                "department": Department.DATA_SCIENCE,
                "role": "NLP Research Engineer",
                "skill_level": SkillLevel.SENIOR,
                "fte_equivalent": 1.0,
                "hire_date": date(2023, 7, 3),
                "annual_cost": 190_000.0,
                "utilization_pct": 84.0,
                "certifications": ["HIPAA Security"],
                "can_handle_phi": True,
            },
            {
                "name": "Sophie Martin",
                "department": Department.DATA_SCIENCE,
                "role": "Junior Data Analyst",
                "skill_level": SkillLevel.JUNIOR,
                "fte_equivalent": 1.0,
                "hire_date": date(2024, 8, 12),
                "annual_cost": 95_000.0,
                "utilization_pct": 70.0,
                "certifications": [],
                "can_handle_phi": False,
            },
            # PRODUCT (3 members)
            {
                "name": "Katherine Lee",
                "department": Department.PRODUCT,
                "role": "Senior Product Manager",
                "skill_level": SkillLevel.SENIOR,
                "fte_equivalent": 1.0,
                "hire_date": date(2023, 1, 9),
                "annual_cost": 170_000.0,
                "utilization_pct": 88.0,
                "certifications": ["CSPO"],
                "can_handle_phi": False,
            },
            {
                "name": "Brian O'Connor",
                "department": Department.PRODUCT,
                "role": "UX Designer",
                "skill_level": SkillLevel.MID,
                "fte_equivalent": 0.8,
                "hire_date": date(2024, 3, 1),
                "annual_cost": 120_000.0,
                "utilization_pct": 76.0,
                "certifications": [],
                "can_handle_phi": False,
            },
            {
                "name": "Diana Vasquez",
                "department": Department.PRODUCT,
                "role": "Product Analyst",
                "skill_level": SkillLevel.JUNIOR,
                "fte_equivalent": 1.0,
                "hire_date": date(2024, 5, 20),
                "annual_cost": 95_000.0,
                "utilization_pct": 73.0,
                "certifications": [],
                "can_handle_phi": False,
            },
            # COMPLIANCE (3 members)
            {
                "name": "Thomas Wright",
                "department": Department.COMPLIANCE,
                "role": "Compliance Officer",
                "skill_level": SkillLevel.SENIOR,
                "fte_equivalent": 1.0,
                "hire_date": date(2022, 10, 1),
                "annual_cost": 165_000.0,
                "utilization_pct": 85.0,
                "certifications": ["CISA", "HIPAA Privacy", "21 CFR Part 11"],
                "can_handle_phi": True,
            },
            {
                "name": "Nancy Park",
                "department": Department.COMPLIANCE,
                "role": "Regulatory Affairs Specialist",
                "skill_level": SkillLevel.MID,
                "fte_equivalent": 1.0,
                "hire_date": date(2023, 8, 14),
                "annual_cost": 130_000.0,
                "utilization_pct": 80.0,
                "certifications": ["RAC", "GCP"],
                "can_handle_phi": True,
            },
            {
                "name": "Frank Russo",
                "department": Department.COMPLIANCE,
                "role": "Quality Assurance Auditor",
                "skill_level": SkillLevel.MID,
                "fte_equivalent": 1.0,
                "hire_date": date(2024, 2, 5),
                "annual_cost": 125_000.0,
                "utilization_pct": 77.0,
                "certifications": ["ISO 27001 Lead Auditor"],
                "can_handle_phi": True,
            },
            # SALES (2 members)
            {
                "name": "Christopher Adams",
                "department": Department.SALES,
                "role": "VP of Sales",
                "skill_level": SkillLevel.LEAD,
                "fte_equivalent": 1.0,
                "hire_date": date(2023, 6, 1),
                "annual_cost": 200_000.0,
                "utilization_pct": 93.0,
                "certifications": [],
                "can_handle_phi": False,
            },
            {
                "name": "Jessica Turner",
                "department": Department.SALES,
                "role": "Account Executive",
                "skill_level": SkillLevel.MID,
                "fte_equivalent": 1.0,
                "hire_date": date(2024, 1, 15),
                "annual_cost": 130_000.0,
                "utilization_pct": 81.0,
                "certifications": [],
                "can_handle_phi": False,
            },
            # SUPPORT (1 member)
            {
                "name": "Kevin Brooks",
                "department": Department.SUPPORT,
                "role": "Technical Support Specialist",
                "skill_level": SkillLevel.MID,
                "fte_equivalent": 1.0,
                "hire_date": date(2024, 3, 18),
                "annual_cost": 95_000.0,
                "utilization_pct": 74.0,
                "certifications": ["HIPAA Security"],
                "can_handle_phi": True,
            },
            # EXECUTIVE (2 members)
            {
                "name": "Dr. Margaret Liu",
                "department": Department.EXECUTIVE,
                "role": "CEO",
                "skill_level": SkillLevel.PRINCIPAL,
                "fte_equivalent": 1.0,
                "hire_date": date(2021, 6, 1),
                "annual_cost": 300_000.0,
                "utilization_pct": 98.0,
                "certifications": ["MD", "MBA"],
                "can_handle_phi": True,
            },
            {
                "name": "Andrew Simmons",
                "department": Department.EXECUTIVE,
                "role": "CTO",
                "skill_level": SkillLevel.PRINCIPAL,
                "fte_equivalent": 1.0,
                "hire_date": date(2021, 6, 1),
                "annual_cost": 280_000.0,
                "utilization_pct": 96.0,
                "certifications": ["AWS Solutions Architect Professional"],
                "can_handle_phi": True,
            },
        ]

        for item in seed:
            member_id = str(uuid4())
            self._team_members[member_id] = TeamMember(id=member_id, **item)

    def _populate_capacity_requirements(self) -> None:
        """Pre-populate 6 capacity requirements (hiring gaps)."""
        seed: list[dict[str, Any]] = [
            {
                "department": Department.ENGINEERING,
                "role": "Senior FHIR Integration Engineer",
                "skill_level": SkillLevel.SENIOR,
                "required_fte": 2.0,
                "current_fte": 0.0,
                "priority": Priority.CRITICAL,
                "justification": "Metriport FHIR integration requires dedicated senior engineers for HL7/FHIR R4 interoperability",
                "timeline_months": 2,
            },
            {
                "department": Department.DATA_SCIENCE,
                "role": "Senior ML Engineer - Clinical NLP",
                "skill_level": SkillLevel.SENIOR,
                "required_fte": 1.0,
                "current_fte": 0.0,
                "priority": Priority.HIGH,
                "justification": "Screening algorithm accuracy improvements require additional ML capacity",
                "timeline_months": 3,
            },
            {
                "department": Department.CLINICAL_OPS,
                "role": "Clinical Trial Coordinator",
                "skill_level": SkillLevel.MID,
                "required_fte": 2.0,
                "current_fte": 1.0,
                "priority": Priority.HIGH,
                "justification": "Scaling to support 10+ concurrent trial protocols requires additional coordinators",
                "timeline_months": 2,
            },
            {
                "department": Department.COMPLIANCE,
                "role": "Privacy Engineer",
                "skill_level": SkillLevel.SENIOR,
                "required_fte": 1.0,
                "current_fte": 0.0,
                "priority": Priority.MEDIUM,
                "justification": "HIPAA/HITRUST compliance automation and PHI de-identification pipeline",
                "timeline_months": 4,
            },
            {
                "department": Department.SALES,
                "role": "Enterprise Account Executive",
                "skill_level": SkillLevel.SENIOR,
                "required_fte": 2.0,
                "current_fte": 1.0,
                "priority": Priority.MEDIUM,
                "justification": "Pharma enterprise sales pipeline requires senior AEs for Regeneron/Sanofi tier accounts",
                "timeline_months": 3,
            },
            {
                "department": Department.SUPPORT,
                "role": "Clinical Support Specialist",
                "skill_level": SkillLevel.MID,
                "required_fte": 2.0,
                "current_fte": 1.0,
                "priority": Priority.LOW,
                "justification": "Scaling support for site coordinators and CRAs across trial sites",
                "timeline_months": 6,
            },
        ]

        for item in seed:
            req_id = str(uuid4())
            gap = item["required_fte"] - item["current_fte"]
            self._capacity_requirements[req_id] = CapacityRequirement(
                id=req_id, gap=gap, **item
            )

    def _populate_hiring_plans(self) -> None:
        """Pre-populate 4 active hiring plans."""
        seed: list[dict[str, Any]] = [
            {
                "department": Department.ENGINEERING,
                "role": "Senior FHIR Integration Engineer",
                "skill_level": SkillLevel.SENIOR,
                "planned_start": date(2025, 4, 1),
                "estimated_salary": 185_000.0,
                "status": HiringStatus.INTERVIEWING,
                "requisition_id": "REQ-2025-001",
            },
            {
                "department": Department.ENGINEERING,
                "role": "Senior FHIR Integration Engineer",
                "skill_level": SkillLevel.SENIOR,
                "planned_start": date(2025, 5, 1),
                "estimated_salary": 185_000.0,
                "status": HiringStatus.OPEN,
                "requisition_id": "REQ-2025-002",
            },
            {
                "department": Department.DATA_SCIENCE,
                "role": "Senior ML Engineer - Clinical NLP",
                "skill_level": SkillLevel.SENIOR,
                "planned_start": date(2025, 5, 15),
                "estimated_salary": 195_000.0,
                "status": HiringStatus.OFFER,
                "requisition_id": "REQ-2025-003",
            },
            {
                "department": Department.CLINICAL_OPS,
                "role": "Clinical Trial Coordinator",
                "skill_level": SkillLevel.MID,
                "planned_start": date(2025, 4, 15),
                "estimated_salary": 110_000.0,
                "status": HiringStatus.INTERVIEWING,
                "requisition_id": "REQ-2025-004",
            },
        ]

        for item in seed:
            plan_id = str(uuid4())
            self._hiring_plans[plan_id] = HiringPlan(id=plan_id, **item)

    # ------------------------------------------------------------------
    # Team Member CRUD
    # ------------------------------------------------------------------

    def list_team_members(
        self, department: Department | None = None
    ) -> TeamMemberListResponse:
        """Return all team members, optionally filtered by department."""
        members = list(self._team_members.values())
        if department is not None:
            members = [m for m in members if m.department == department]
        return TeamMemberListResponse(total=len(members), members=members)

    def get_team_member(self, member_id: str) -> TeamMember:
        """Return a team member by ID."""
        if member_id not in self._team_members:
            raise ValueError(f"Team member '{member_id}' not found")
        return self._team_members[member_id]

    def add_team_member(
        self,
        name: str,
        department: Department,
        role: str,
        skill_level: SkillLevel,
        fte_equivalent: float,
        hire_date: date,
        annual_cost: float,
        utilization_pct: float = 80.0,
        certifications: list[str] | None = None,
        can_handle_phi: bool = False,
    ) -> TeamMember:
        """Add a new team member."""
        member_id = str(uuid4())
        member = TeamMember(
            id=member_id,
            name=name,
            department=department,
            role=role,
            skill_level=skill_level,
            fte_equivalent=fte_equivalent,
            hire_date=hire_date,
            annual_cost=annual_cost,
            utilization_pct=utilization_pct,
            certifications=certifications or [],
            can_handle_phi=can_handle_phi,
        )
        self._team_members[member_id] = member
        return member

    def update_team_member(
        self,
        member_id: str,
        **kwargs: Any,
    ) -> TeamMember:
        """Update fields on an existing team member."""
        if member_id not in self._team_members:
            raise ValueError(f"Team member '{member_id}' not found")
        current = self._team_members[member_id]
        data = current.model_dump()
        for key, value in kwargs.items():
            if value is not None:
                data[key] = value
        updated = TeamMember(**data)
        self._team_members[member_id] = updated
        return updated

    def remove_team_member(self, member_id: str) -> None:
        """Remove a team member by ID."""
        if member_id not in self._team_members:
            raise ValueError(f"Team member '{member_id}' not found")
        del self._team_members[member_id]

    # ------------------------------------------------------------------
    # Capacity Requirement CRUD
    # ------------------------------------------------------------------

    def list_capacity_requirements(
        self, department: Department | None = None
    ) -> CapacityRequirementListResponse:
        """Return all capacity requirements, optionally filtered."""
        reqs = list(self._capacity_requirements.values())
        if department is not None:
            reqs = [r for r in reqs if r.department == department]
        return CapacityRequirementListResponse(total=len(reqs), requirements=reqs)

    def get_capacity_requirement(self, req_id: str) -> CapacityRequirement:
        """Return a capacity requirement by ID."""
        if req_id not in self._capacity_requirements:
            raise ValueError(f"Capacity requirement '{req_id}' not found")
        return self._capacity_requirements[req_id]

    def add_capacity_requirement(
        self,
        department: Department,
        role: str,
        skill_level: SkillLevel,
        required_fte: float,
        current_fte: float,
        priority: Priority = Priority.MEDIUM,
        justification: str = "",
        timeline_months: int = 3,
    ) -> CapacityRequirement:
        """Add a new capacity requirement."""
        req_id = str(uuid4())
        gap = required_fte - current_fte
        req = CapacityRequirement(
            id=req_id,
            department=department,
            role=role,
            skill_level=skill_level,
            required_fte=required_fte,
            current_fte=current_fte,
            gap=gap,
            priority=priority,
            justification=justification,
            timeline_months=timeline_months,
        )
        self._capacity_requirements[req_id] = req
        return req

    def update_capacity_requirement(
        self,
        req_id: str,
        **kwargs: Any,
    ) -> CapacityRequirement:
        """Update fields on an existing capacity requirement."""
        if req_id not in self._capacity_requirements:
            raise ValueError(f"Capacity requirement '{req_id}' not found")
        current = self._capacity_requirements[req_id]
        data = current.model_dump()
        for key, value in kwargs.items():
            if value is not None:
                data[key] = value
        # Recalculate gap if required_fte or current_fte changed
        data["gap"] = data["required_fte"] - data["current_fte"]
        updated = CapacityRequirement(**data)
        self._capacity_requirements[req_id] = updated
        return updated

    def remove_capacity_requirement(self, req_id: str) -> None:
        """Remove a capacity requirement by ID."""
        if req_id not in self._capacity_requirements:
            raise ValueError(f"Capacity requirement '{req_id}' not found")
        del self._capacity_requirements[req_id]

    # ------------------------------------------------------------------
    # Hiring Plan CRUD
    # ------------------------------------------------------------------

    def list_hiring_plans(
        self, department: Department | None = None, status: HiringStatus | None = None
    ) -> HiringPlanListResponse:
        """Return hiring plans, optionally filtered."""
        plans = list(self._hiring_plans.values())
        if department is not None:
            plans = [p for p in plans if p.department == department]
        if status is not None:
            plans = [p for p in plans if p.status == status]
        return HiringPlanListResponse(total=len(plans), plans=plans)

    def get_hiring_plan(self, plan_id: str) -> HiringPlan:
        """Return a hiring plan by ID."""
        if plan_id not in self._hiring_plans:
            raise ValueError(f"Hiring plan '{plan_id}' not found")
        return self._hiring_plans[plan_id]

    def add_hiring_plan(
        self,
        department: Department,
        role: str,
        skill_level: SkillLevel,
        planned_start: date,
        estimated_salary: float,
        status: HiringStatus = HiringStatus.OPEN,
        requisition_id: str = "",
    ) -> HiringPlan:
        """Add a new hiring plan."""
        plan_id = str(uuid4())
        plan = HiringPlan(
            id=plan_id,
            department=department,
            role=role,
            skill_level=skill_level,
            planned_start=planned_start,
            estimated_salary=estimated_salary,
            status=status,
            requisition_id=requisition_id,
        )
        self._hiring_plans[plan_id] = plan
        return plan

    def update_hiring_plan(
        self,
        plan_id: str,
        **kwargs: Any,
    ) -> HiringPlan:
        """Update fields on an existing hiring plan."""
        if plan_id not in self._hiring_plans:
            raise ValueError(f"Hiring plan '{plan_id}' not found")
        current = self._hiring_plans[plan_id]
        data = current.model_dump()
        for key, value in kwargs.items():
            if value is not None:
                data[key] = value
        updated = HiringPlan(**data)
        self._hiring_plans[plan_id] = updated
        return updated

    def remove_hiring_plan(self, plan_id: str) -> None:
        """Remove a hiring plan by ID."""
        if plan_id not in self._hiring_plans:
            raise ValueError(f"Hiring plan '{plan_id}' not found")
        del self._hiring_plans[plan_id]

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def get_capacity_by_department(self) -> list[DepartmentCapacity]:
        """Current vs required FTE per department."""
        result: list[DepartmentCapacity] = []
        for dept in Department:
            members = [m for m in self._team_members.values() if m.department == dept]
            current_fte = sum(m.fte_equivalent for m in members)
            reqs = [
                r for r in self._capacity_requirements.values() if r.department == dept
            ]
            required_fte = current_fte + sum(max(r.gap, 0) for r in reqs)
            open_plans = [
                p
                for p in self._hiring_plans.values()
                if p.department == dept
                and p.status not in (HiringStatus.FILLED, HiringStatus.CANCELLED)
            ]
            result.append(
                DepartmentCapacity(
                    department=dept,
                    current_fte=round(current_fte, 2),
                    required_fte=round(required_fte, 2),
                    gap=round(required_fte - current_fte, 2),
                    headcount=len(members),
                    open_reqs=len(open_plans),
                )
            )
        return result

    def project_capacity(self, months: int = 12) -> CapacityProjectionResponse:
        """Monthly capacity projections accounting for hiring pipeline.

        Assumes:
        - Active hiring plans (OPEN/INTERVIEWING/OFFER) will be filled
          at a staggered rate over the projection period.
        - OFFER plans fill in month 1, INTERVIEWING in month 2-3, OPEN in month 4+.
        """
        current_fte = sum(m.fte_equivalent for m in self._team_members.values())
        total_required = current_fte + sum(
            max(r.gap, 0) for r in self._capacity_requirements.values()
        )

        # Build hiring schedule
        active_plans = [
            p
            for p in self._hiring_plans.values()
            if p.status not in (HiringStatus.FILLED, HiringStatus.CANCELLED)
        ]

        hire_schedule: dict[int, int] = {}
        for plan in active_plans:
            if plan.status == HiringStatus.OFFER:
                month = 1
            elif plan.status == HiringStatus.INTERVIEWING:
                month = 2
            else:
                month = 4
            # Clamp to projection window
            if month <= months:
                hire_schedule[month] = hire_schedule.get(month, 0) + 1

        projections: list[CapacityProjection] = []
        cumulative_hires = 0
        total_hires = 0

        for m in range(1, months + 1):
            new_hires = hire_schedule.get(m, 0)
            cumulative_hires += new_hires
            total_hires += new_hires
            available = current_fte + cumulative_hires
            gap = total_required - available
            hires_still_needed = max(0, math.ceil(gap))
            projections.append(
                CapacityProjection(
                    month=m,
                    required_fte=round(total_required, 2),
                    available_fte=round(available, 2),
                    gap=round(gap, 2),
                    hires_needed=hires_still_needed,
                )
            )

        return CapacityProjectionResponse(
            months=months,
            projections=projections,
            total_hires_needed=max(
                0,
                math.ceil(
                    total_required - current_fte - sum(hire_schedule.values())
                ),
            ),
        )

    def get_utilization_report(self) -> UtilizationReport:
        """Utilization analysis by department."""
        departments: list[DepartmentUtilization] = []
        total_over = 0
        total_under = 0
        all_utils: list[float] = []

        for dept in Department:
            members = [m for m in self._team_members.values() if m.department == dept]
            if not members:
                departments.append(
                    DepartmentUtilization(
                        department=dept,
                        headcount=0,
                        total_fte=0.0,
                        avg_utilization=0.0,
                        min_utilization=0.0,
                        max_utilization=0.0,
                    )
                )
                continue

            utils = [m.utilization_pct for m in members]
            all_utils.extend(utils)
            over = sum(1 for u in utils if u > 90)
            under = sum(1 for u in utils if u < 50)
            total_over += over
            total_under += under

            departments.append(
                DepartmentUtilization(
                    department=dept,
                    headcount=len(members),
                    total_fte=round(sum(m.fte_equivalent for m in members), 2),
                    avg_utilization=round(sum(utils) / len(utils), 1),
                    min_utilization=round(min(utils), 1),
                    max_utilization=round(max(utils), 1),
                    over_utilized_count=over,
                    under_utilized_count=under,
                )
            )

        overall = round(sum(all_utils) / len(all_utils), 1) if all_utils else 0.0

        return UtilizationReport(
            overall_avg_utilization=overall,
            departments=departments,
            total_over_utilized=total_over,
            total_under_utilized=total_under,
        )

    def get_metrics(self) -> WorkforceMetrics:
        """Return workforce KPIs."""
        members = list(self._team_members.values())
        if not members:
            return WorkforceMetrics()

        total_headcount = len(members)
        total_fte = sum(m.fte_equivalent for m in members)

        by_dept: dict[str, int] = {}
        for dept in Department:
            count = sum(1 for m in members if m.department == dept)
            if count > 0:
                by_dept[dept.value] = count

        utils = [m.utilization_pct for m in members]
        avg_util = sum(utils) / len(utils)

        total_gap = sum(
            max(r.gap, 0) for r in self._capacity_requirements.values()
        )

        active_hiring = sum(
            1
            for p in self._hiring_plans.values()
            if p.status not in (HiringStatus.FILLED, HiringStatus.CANCELLED)
        )

        today = date.today()
        tenures = []
        for m in members:
            delta = today - m.hire_date
            tenures.append(delta.days / 30.44)  # avg days per month
        avg_tenure = sum(tenures) / len(tenures) if tenures else 0.0

        phi_count = sum(1 for m in members if m.can_handle_phi)

        total_cost = sum(m.annual_cost for m in members)
        cost_per_fte = total_cost / total_fte if total_fte > 0 else 0.0

        projected_12mo = total_headcount + active_hiring

        return WorkforceMetrics(
            total_headcount=total_headcount,
            total_fte=round(total_fte, 2),
            by_department=by_dept,
            avg_utilization=round(avg_util, 1),
            capacity_gap_total_fte=round(total_gap, 2),
            hiring_pipeline_count=active_hiring,
            avg_tenure_months=round(avg_tenure, 1),
            phi_certified_count=phi_count,
            cost_per_fte=round(cost_per_fte, 2),
            projected_headcount_12mo=projected_12mo,
        )

    def identify_skill_gaps(self) -> SkillGapReport:
        """Identify skills needed but not present or under-staffed."""
        gaps: list[SkillGap] = []

        for req in self._capacity_requirements.values():
            if req.gap > 0:
                # Check if any hiring plan covers this
                covering_plans = [
                    p
                    for p in self._hiring_plans.values()
                    if p.department == req.department
                    and p.role == req.role
                    and p.status not in (HiringStatus.FILLED, HiringStatus.CANCELLED)
                ]
                covered_fte = len(covering_plans)  # each plan ~ 1 FTE
                remaining_gap = max(0, req.gap - covered_fte)

                recommendation = ""
                if remaining_gap > 0:
                    if req.priority in (Priority.CRITICAL, Priority.HIGH):
                        recommendation = (
                            f"Urgent: open {math.ceil(remaining_gap)} additional req(s) "
                            f"for {req.role} in {req.department.value}. "
                            f"Timeline: {req.timeline_months} months."
                        )
                    else:
                        recommendation = (
                            f"Plan to hire {math.ceil(remaining_gap)} {req.role} "
                            f"in {req.department.value} within {req.timeline_months} months."
                        )
                else:
                    recommendation = (
                        f"Gap covered by {covered_fte} active hiring plan(s). "
                        f"Monitor pipeline progress."
                    )

                gaps.append(
                    SkillGap(
                        department=req.department,
                        role=req.role,
                        skill_level=req.skill_level,
                        required_fte=req.required_fte,
                        current_fte=req.current_fte,
                        gap_fte=round(req.gap, 2),
                        priority=req.priority,
                        recommendation=recommendation,
                    )
                )

        critical_count = sum(1 for g in gaps if g.priority == Priority.CRITICAL)

        return SkillGapReport(
            total_gaps=len(gaps),
            critical_gaps=critical_count,
            gaps=gaps,
        )
