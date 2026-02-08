"""Tests for COO-4: Workforce Capacity Planning.

Tests cover:
- Team member CRUD: add, get, update, remove, list, filter by department
- Capacity requirement CRUD: add, get, update, remove, list, filter
- Hiring plan CRUD: add, get, update, remove, list, filter by dept/status
- Seed data validation: team members across departments, requirements, hiring plans
- Workforce metrics: headcount, FTE, utilization, gaps, tenure, PHI, cost
- Capacity by department: current vs required FTE per department
- Capacity projection: monthly projections with hiring pipeline
- Utilization report: per-department utilization analysis
- Skill gap identification: gaps, priorities, recommendations
- API endpoint integration tests (all 18 routes)
- Edge cases: not found, empty department, gap recalculation
- Singleton pattern (get/reset)
"""

from __future__ import annotations

from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.workforce_planning import (
    Department,
    HiringStatus,
    Priority,
    SkillLevel,
)
from app.services.workforce_planning_service import (
    WorkforcePlanningService,
    get_workforce_planning_service,
    reset_workforce_planning_service,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_service():
    """Reset the singleton service before and after each test."""
    reset_workforce_planning_service()
    yield
    reset_workforce_planning_service()


@pytest.fixture
def service() -> WorkforcePlanningService:
    return get_workforce_planning_service()


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ============================================================================
# Seed Data Tests
# ============================================================================


class TestSeedData:
    """Tests for pre-populated data."""

    def test_seed_team_members_count(self, service: WorkforcePlanningService):
        """Service should have at least 25 pre-populated team members."""
        result = service.list_team_members()
        assert result.total >= 25

    def test_seed_team_members_cover_all_departments(self, service: WorkforcePlanningService):
        """Seed data should have members in every department."""
        result = service.list_team_members()
        populated_depts = {m.department for m in result.members}
        assert populated_depts == set(Department)

    def test_seed_team_members_have_positive_costs(self, service: WorkforcePlanningService):
        """All seed team members should have positive annual costs."""
        result = service.list_team_members()
        for m in result.members:
            assert m.annual_cost > 0

    def test_seed_team_members_valid_fte(self, service: WorkforcePlanningService):
        """All seed team members should have FTE between 0 and 1."""
        result = service.list_team_members()
        for m in result.members:
            assert 0.0 <= m.fte_equivalent <= 1.0

    def test_seed_team_members_valid_utilization(self, service: WorkforcePlanningService):
        """All seed team members should have utilization between 0 and 100."""
        result = service.list_team_members()
        for m in result.members:
            assert 0 <= m.utilization_pct <= 100

    def test_seed_capacity_requirements_count(self, service: WorkforcePlanningService):
        """Service should have at least 5 pre-populated capacity requirements."""
        result = service.list_capacity_requirements()
        assert result.total >= 5

    def test_seed_capacity_requirements_have_gaps(self, service: WorkforcePlanningService):
        """All seed capacity requirements should have positive gaps."""
        result = service.list_capacity_requirements()
        for req in result.requirements:
            assert req.gap > 0

    def test_seed_capacity_requirements_have_justifications(self, service: WorkforcePlanningService):
        """All seed capacity requirements should have justifications."""
        result = service.list_capacity_requirements()
        for req in result.requirements:
            assert len(req.justification) > 0

    def test_seed_hiring_plans_count(self, service: WorkforcePlanningService):
        """Service should have at least 3 pre-populated hiring plans."""
        result = service.list_hiring_plans()
        assert result.total >= 3

    def test_seed_hiring_plans_have_requisition_ids(self, service: WorkforcePlanningService):
        """All seed hiring plans should have requisition IDs."""
        result = service.list_hiring_plans()
        for plan in result.plans:
            assert len(plan.requisition_id) > 0

    def test_seed_hiring_plans_have_positive_salary(self, service: WorkforcePlanningService):
        """All seed hiring plans should have positive estimated salaries."""
        result = service.list_hiring_plans()
        for plan in result.plans:
            assert plan.estimated_salary > 0

    def test_seed_phi_certified_members_exist(self, service: WorkforcePlanningService):
        """There should be multiple PHI-certified team members."""
        result = service.list_team_members()
        phi_count = sum(1 for m in result.members if m.can_handle_phi)
        assert phi_count >= 5

    def test_seed_has_multiple_skill_levels(self, service: WorkforcePlanningService):
        """Seed data should include multiple skill levels."""
        result = service.list_team_members()
        levels = {m.skill_level for m in result.members}
        assert len(levels) >= 4

    def test_seed_engineering_department_has_most_members(self, service: WorkforcePlanningService):
        """Engineering should have the most team members."""
        result = service.list_team_members()
        dept_counts = {}
        for m in result.members:
            dept_counts[m.department] = dept_counts.get(m.department, 0) + 1
        max_dept = max(dept_counts, key=dept_counts.get)
        assert max_dept == Department.ENGINEERING


# ============================================================================
# Team Member CRUD
# ============================================================================


class TestTeamMemberCRUD:
    """Tests for team member create, read, update, delete."""

    def test_add_team_member(self, service: WorkforcePlanningService):
        """Adding a team member should increase the count."""
        before = service.list_team_members().total
        member = service.add_team_member(
            name="Test Person",
            department=Department.ENGINEERING,
            role="Test Engineer",
            skill_level=SkillLevel.MID,
            fte_equivalent=1.0,
            hire_date=date(2024, 1, 1),
            annual_cost=120_000.0,
        )
        after = service.list_team_members().total
        assert after == before + 1
        assert member.name == "Test Person"
        assert member.id is not None

    def test_add_team_member_with_all_fields(self, service: WorkforcePlanningService):
        """All fields should be stored correctly."""
        member = service.add_team_member(
            name="Full Details",
            department=Department.COMPLIANCE,
            role="Compliance Analyst",
            skill_level=SkillLevel.SENIOR,
            fte_equivalent=0.8,
            hire_date=date(2023, 6, 15),
            annual_cost=150_000.0,
            utilization_pct=85.0,
            certifications=["CISA", "HIPAA"],
            can_handle_phi=True,
        )
        assert member.department == Department.COMPLIANCE
        assert member.skill_level == SkillLevel.SENIOR
        assert member.fte_equivalent == 0.8
        assert member.utilization_pct == 85.0
        assert "CISA" in member.certifications
        assert member.can_handle_phi is True

    def test_get_team_member(self, service: WorkforcePlanningService):
        """Should be able to retrieve a team member by ID."""
        member = service.add_team_member(
            name="Lookup Test",
            department=Department.PRODUCT,
            role="PM",
            skill_level=SkillLevel.MID,
            fte_equivalent=1.0,
            hire_date=date(2024, 1, 1),
            annual_cost=130_000.0,
        )
        fetched = service.get_team_member(member.id)
        assert fetched.name == "Lookup Test"

    def test_get_team_member_not_found(self, service: WorkforcePlanningService):
        """Should raise ValueError for non-existent ID."""
        with pytest.raises(ValueError, match="not found"):
            service.get_team_member("nonexistent-id")

    def test_update_team_member(self, service: WorkforcePlanningService):
        """Updating a team member should change its fields."""
        member = service.add_team_member(
            name="Original",
            department=Department.ENGINEERING,
            role="Engineer",
            skill_level=SkillLevel.JUNIOR,
            fte_equivalent=1.0,
            hire_date=date(2024, 1, 1),
            annual_cost=100_000.0,
        )
        updated = service.update_team_member(
            member.id, name="Updated", skill_level=SkillLevel.MID
        )
        assert updated.name == "Updated"
        assert updated.skill_level == SkillLevel.MID
        # Department should be unchanged
        assert updated.department == Department.ENGINEERING

    def test_update_team_member_not_found(self, service: WorkforcePlanningService):
        """Updating a non-existent member should raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.update_team_member("nonexistent", name="X")

    def test_remove_team_member(self, service: WorkforcePlanningService):
        """Removing a team member should decrease the count."""
        member = service.add_team_member(
            name="To Remove",
            department=Department.SUPPORT,
            role="Support",
            skill_level=SkillLevel.JUNIOR,
            fte_equivalent=1.0,
            hire_date=date(2024, 1, 1),
            annual_cost=80_000.0,
        )
        before = service.list_team_members().total
        service.remove_team_member(member.id)
        after = service.list_team_members().total
        assert after == before - 1

    def test_remove_team_member_not_found(self, service: WorkforcePlanningService):
        """Removing a non-existent member should raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.remove_team_member("nonexistent")

    def test_list_team_members_filter_by_department(self, service: WorkforcePlanningService):
        """Filtering by department should return only that department's members."""
        result = service.list_team_members(department=Department.ENGINEERING)
        assert result.total > 0
        for m in result.members:
            assert m.department == Department.ENGINEERING

    def test_list_team_members_all(self, service: WorkforcePlanningService):
        """Listing without filter should return all members."""
        result = service.list_team_members()
        assert result.total >= 25


# ============================================================================
# Capacity Requirement CRUD
# ============================================================================


class TestCapacityRequirementCRUD:
    """Tests for capacity requirement create, read, update, delete."""

    def test_add_capacity_requirement(self, service: WorkforcePlanningService):
        """Adding a requirement should increase the count."""
        before = service.list_capacity_requirements().total
        req = service.add_capacity_requirement(
            department=Department.ENGINEERING,
            role="DevOps Engineer",
            skill_level=SkillLevel.SENIOR,
            required_fte=2.0,
            current_fte=0.5,
        )
        after = service.list_capacity_requirements().total
        assert after == before + 1
        assert req.gap == 1.5

    def test_add_capacity_requirement_gap_calculation(self, service: WorkforcePlanningService):
        """Gap should be automatically calculated as required - current."""
        req = service.add_capacity_requirement(
            department=Department.DATA_SCIENCE,
            role="Data Engineer",
            skill_level=SkillLevel.MID,
            required_fte=3.0,
            current_fte=1.0,
        )
        assert req.gap == 2.0

    def test_get_capacity_requirement(self, service: WorkforcePlanningService):
        """Should be able to retrieve a requirement by ID."""
        req = service.add_capacity_requirement(
            department=Department.PRODUCT,
            role="PM",
            skill_level=SkillLevel.SENIOR,
            required_fte=1.0,
            current_fte=0.0,
        )
        fetched = service.get_capacity_requirement(req.id)
        assert fetched.role == "PM"

    def test_get_capacity_requirement_not_found(self, service: WorkforcePlanningService):
        """Should raise ValueError for non-existent ID."""
        with pytest.raises(ValueError, match="not found"):
            service.get_capacity_requirement("nonexistent-id")

    def test_update_capacity_requirement(self, service: WorkforcePlanningService):
        """Updating a requirement should change its fields and recalculate gap."""
        req = service.add_capacity_requirement(
            department=Department.ENGINEERING,
            role="Original Role",
            skill_level=SkillLevel.MID,
            required_fte=2.0,
            current_fte=1.0,
        )
        updated = service.update_capacity_requirement(
            req.id, required_fte=3.0
        )
        assert updated.required_fte == 3.0
        assert updated.gap == 2.0  # 3.0 - 1.0

    def test_update_capacity_requirement_not_found(self, service: WorkforcePlanningService):
        """Updating a non-existent requirement should raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.update_capacity_requirement("nonexistent", role="X")

    def test_remove_capacity_requirement(self, service: WorkforcePlanningService):
        """Removing a requirement should decrease the count."""
        req = service.add_capacity_requirement(
            department=Department.SUPPORT,
            role="Support Lead",
            skill_level=SkillLevel.LEAD,
            required_fte=1.0,
            current_fte=0.0,
        )
        before = service.list_capacity_requirements().total
        service.remove_capacity_requirement(req.id)
        after = service.list_capacity_requirements().total
        assert after == before - 1

    def test_remove_capacity_requirement_not_found(self, service: WorkforcePlanningService):
        """Removing a non-existent requirement should raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.remove_capacity_requirement("nonexistent")

    def test_list_capacity_requirements_filter_by_department(self, service: WorkforcePlanningService):
        """Filtering by department should return only that department's requirements."""
        result = service.list_capacity_requirements(department=Department.ENGINEERING)
        assert result.total > 0
        for req in result.requirements:
            assert req.department == Department.ENGINEERING

    def test_capacity_requirement_with_priority(self, service: WorkforcePlanningService):
        """Should be able to set priority on a requirement."""
        req = service.add_capacity_requirement(
            department=Department.COMPLIANCE,
            role="Privacy Engineer",
            skill_level=SkillLevel.SENIOR,
            required_fte=1.0,
            current_fte=0.0,
            priority=Priority.CRITICAL,
        )
        assert req.priority == Priority.CRITICAL


# ============================================================================
# Hiring Plan CRUD
# ============================================================================


class TestHiringPlanCRUD:
    """Tests for hiring plan create, read, update, delete."""

    def test_add_hiring_plan(self, service: WorkforcePlanningService):
        """Adding a hiring plan should increase the count."""
        before = service.list_hiring_plans().total
        plan = service.add_hiring_plan(
            department=Department.ENGINEERING,
            role="Frontend Engineer",
            skill_level=SkillLevel.MID,
            planned_start=date(2025, 6, 1),
            estimated_salary=140_000.0,
        )
        after = service.list_hiring_plans().total
        assert after == before + 1
        assert plan.status == HiringStatus.OPEN

    def test_add_hiring_plan_with_all_fields(self, service: WorkforcePlanningService):
        """All fields should be stored correctly."""
        plan = service.add_hiring_plan(
            department=Department.DATA_SCIENCE,
            role="ML Engineer",
            skill_level=SkillLevel.SENIOR,
            planned_start=date(2025, 7, 1),
            estimated_salary=190_000.0,
            status=HiringStatus.INTERVIEWING,
            requisition_id="REQ-TEST-001",
        )
        assert plan.department == Department.DATA_SCIENCE
        assert plan.status == HiringStatus.INTERVIEWING
        assert plan.requisition_id == "REQ-TEST-001"

    def test_get_hiring_plan(self, service: WorkforcePlanningService):
        """Should be able to retrieve a hiring plan by ID."""
        plan = service.add_hiring_plan(
            department=Department.SALES,
            role="AE",
            skill_level=SkillLevel.MID,
            planned_start=date(2025, 5, 1),
            estimated_salary=130_000.0,
        )
        fetched = service.get_hiring_plan(plan.id)
        assert fetched.role == "AE"

    def test_get_hiring_plan_not_found(self, service: WorkforcePlanningService):
        """Should raise ValueError for non-existent ID."""
        with pytest.raises(ValueError, match="not found"):
            service.get_hiring_plan("nonexistent-id")

    def test_update_hiring_plan(self, service: WorkforcePlanningService):
        """Updating a hiring plan should change its fields."""
        plan = service.add_hiring_plan(
            department=Department.ENGINEERING,
            role="Engineer",
            skill_level=SkillLevel.MID,
            planned_start=date(2025, 6, 1),
            estimated_salary=140_000.0,
        )
        updated = service.update_hiring_plan(
            plan.id, status=HiringStatus.OFFER
        )
        assert updated.status == HiringStatus.OFFER

    def test_update_hiring_plan_not_found(self, service: WorkforcePlanningService):
        """Updating a non-existent plan should raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.update_hiring_plan("nonexistent", role="X")

    def test_remove_hiring_plan(self, service: WorkforcePlanningService):
        """Removing a hiring plan should decrease the count."""
        plan = service.add_hiring_plan(
            department=Department.PRODUCT,
            role="Designer",
            skill_level=SkillLevel.JUNIOR,
            planned_start=date(2025, 8, 1),
            estimated_salary=90_000.0,
        )
        before = service.list_hiring_plans().total
        service.remove_hiring_plan(plan.id)
        after = service.list_hiring_plans().total
        assert after == before - 1

    def test_remove_hiring_plan_not_found(self, service: WorkforcePlanningService):
        """Removing a non-existent plan should raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.remove_hiring_plan("nonexistent")

    def test_list_hiring_plans_filter_by_department(self, service: WorkforcePlanningService):
        """Filtering by department should return only that department's plans."""
        result = service.list_hiring_plans(department=Department.ENGINEERING)
        assert result.total > 0
        for plan in result.plans:
            assert plan.department == Department.ENGINEERING

    def test_list_hiring_plans_filter_by_status(self, service: WorkforcePlanningService):
        """Filtering by status should return only plans with that status."""
        result = service.list_hiring_plans(status=HiringStatus.INTERVIEWING)
        assert result.total > 0
        for plan in result.plans:
            assert plan.status == HiringStatus.INTERVIEWING

    def test_list_hiring_plans_filter_by_dept_and_status(self, service: WorkforcePlanningService):
        """Should be able to filter by both department and status."""
        result = service.list_hiring_plans(
            department=Department.ENGINEERING,
            status=HiringStatus.INTERVIEWING,
        )
        for plan in result.plans:
            assert plan.department == Department.ENGINEERING
            assert plan.status == HiringStatus.INTERVIEWING


# ============================================================================
# Workforce Metrics
# ============================================================================


class TestWorkforceMetrics:
    """Tests for workforce KPI metrics."""

    def test_metrics_total_headcount(self, service: WorkforcePlanningService):
        """Headcount should match total team members."""
        metrics = service.get_metrics()
        members = service.list_team_members()
        assert metrics.total_headcount == members.total

    def test_metrics_total_fte(self, service: WorkforcePlanningService):
        """Total FTE should be sum of all member FTE equivalents."""
        metrics = service.get_metrics()
        members = service.list_team_members()
        expected_fte = sum(m.fte_equivalent for m in members.members)
        assert abs(metrics.total_fte - expected_fte) < 0.01

    def test_metrics_by_department(self, service: WorkforcePlanningService):
        """by_department dict should contain all departments with members."""
        metrics = service.get_metrics()
        assert len(metrics.by_department) > 0
        total = sum(metrics.by_department.values())
        assert total == metrics.total_headcount

    def test_metrics_avg_utilization(self, service: WorkforcePlanningService):
        """Average utilization should be between 0 and 100."""
        metrics = service.get_metrics()
        assert 0 < metrics.avg_utilization <= 100

    def test_metrics_capacity_gap(self, service: WorkforcePlanningService):
        """Capacity gap should be positive (we have hiring needs)."""
        metrics = service.get_metrics()
        assert metrics.capacity_gap_total_fte > 0

    def test_metrics_hiring_pipeline(self, service: WorkforcePlanningService):
        """Hiring pipeline count should include active (non-filled/cancelled) plans."""
        metrics = service.get_metrics()
        assert metrics.hiring_pipeline_count > 0

    def test_metrics_avg_tenure(self, service: WorkforcePlanningService):
        """Average tenure should be positive."""
        metrics = service.get_metrics()
        assert metrics.avg_tenure_months > 0

    def test_metrics_phi_certified(self, service: WorkforcePlanningService):
        """PHI certified count should be positive."""
        metrics = service.get_metrics()
        assert metrics.phi_certified_count > 0

    def test_metrics_cost_per_fte(self, service: WorkforcePlanningService):
        """Cost per FTE should be positive."""
        metrics = service.get_metrics()
        assert metrics.cost_per_fte > 0

    def test_metrics_projected_headcount(self, service: WorkforcePlanningService):
        """Projected headcount should be >= current headcount."""
        metrics = service.get_metrics()
        assert metrics.projected_headcount_12mo >= metrics.total_headcount


# ============================================================================
# Capacity by Department
# ============================================================================


class TestCapacityByDepartment:
    """Tests for department-level capacity analysis."""

    def test_capacity_covers_all_departments(self, service: WorkforcePlanningService):
        """Should return capacity info for all departments."""
        result = service.get_capacity_by_department()
        depts = {dc.department for dc in result}
        assert depts == set(Department)

    def test_capacity_engineering_has_gap(self, service: WorkforcePlanningService):
        """Engineering should have a positive capacity gap."""
        result = service.get_capacity_by_department()
        eng = next(dc for dc in result if dc.department == Department.ENGINEERING)
        assert eng.gap > 0

    def test_capacity_current_fte_matches_members(self, service: WorkforcePlanningService):
        """Current FTE should match sum of member FTEs in department."""
        result = service.get_capacity_by_department()
        members = service.list_team_members()
        for dc in result:
            dept_members = [m for m in members.members if m.department == dc.department]
            expected_fte = sum(m.fte_equivalent for m in dept_members)
            assert abs(dc.current_fte - expected_fte) < 0.01

    def test_capacity_headcount_matches(self, service: WorkforcePlanningService):
        """Headcount should match number of members in department."""
        result = service.get_capacity_by_department()
        members = service.list_team_members()
        for dc in result:
            dept_members = [m for m in members.members if m.department == dc.department]
            assert dc.headcount == len(dept_members)

    def test_capacity_open_reqs(self, service: WorkforcePlanningService):
        """Departments with hiring plans should have open_reqs > 0."""
        result = service.get_capacity_by_department()
        eng = next(dc for dc in result if dc.department == Department.ENGINEERING)
        assert eng.open_reqs > 0


# ============================================================================
# Capacity Projection
# ============================================================================


class TestCapacityProjection:
    """Tests for monthly capacity projections."""

    def test_projection_returns_correct_months(self, service: WorkforcePlanningService):
        """Should return projections for the requested number of months."""
        result = service.project_capacity(months=6)
        assert result.months == 6
        assert len(result.projections) == 6

    def test_projection_month_numbers_sequential(self, service: WorkforcePlanningService):
        """Month numbers should be sequential starting from 1."""
        result = service.project_capacity(months=12)
        for i, proj in enumerate(result.projections):
            assert proj.month == i + 1

    def test_projection_gap_decreases_over_time(self, service: WorkforcePlanningService):
        """Gap should decrease (or stay same) as hires come in."""
        result = service.project_capacity(months=12)
        # After month 4 (when OPEN plans fill), gap should be <= initial
        initial_gap = result.projections[0].gap
        later_gap = result.projections[5].gap
        assert later_gap <= initial_gap

    def test_projection_available_fte_increases(self, service: WorkforcePlanningService):
        """Available FTE should increase as hires join."""
        result = service.project_capacity(months=12)
        first_available = result.projections[0].available_fte
        last_available = result.projections[-1].available_fte
        assert last_available >= first_available

    def test_projection_required_fte_consistent(self, service: WorkforcePlanningService):
        """Required FTE should remain consistent across months."""
        result = service.project_capacity(months=6)
        required_values = {p.required_fte for p in result.projections}
        assert len(required_values) == 1  # All months have same required FTE

    def test_projection_single_month(self, service: WorkforcePlanningService):
        """Should work for a single month projection."""
        result = service.project_capacity(months=1)
        assert result.months == 1
        assert len(result.projections) == 1


# ============================================================================
# Utilization Report
# ============================================================================


class TestUtilizationReport:
    """Tests for utilization analysis."""

    def test_utilization_overall_avg(self, service: WorkforcePlanningService):
        """Overall average utilization should be between 0 and 100."""
        report = service.get_utilization_report()
        assert 0 < report.overall_avg_utilization <= 100

    def test_utilization_covers_all_departments(self, service: WorkforcePlanningService):
        """Should include all departments."""
        report = service.get_utilization_report()
        depts = {du.department for du in report.departments}
        assert depts == set(Department)

    def test_utilization_engineering_details(self, service: WorkforcePlanningService):
        """Engineering utilization should have valid metrics."""
        report = service.get_utilization_report()
        eng = next(du for du in report.departments if du.department == Department.ENGINEERING)
        assert eng.headcount > 0
        assert eng.total_fte > 0
        assert eng.avg_utilization > 0
        assert eng.min_utilization > 0
        assert eng.max_utilization >= eng.min_utilization

    def test_utilization_over_utilized_count(self, service: WorkforcePlanningService):
        """Over-utilized count should be non-negative."""
        report = service.get_utilization_report()
        assert report.total_over_utilized >= 0
        for du in report.departments:
            assert du.over_utilized_count >= 0

    def test_utilization_under_utilized_count(self, service: WorkforcePlanningService):
        """Under-utilized count should be non-negative."""
        report = service.get_utilization_report()
        assert report.total_under_utilized >= 0
        for du in report.departments:
            assert du.under_utilized_count >= 0

    def test_utilization_min_max_consistency(self, service: WorkforcePlanningService):
        """Max utilization should be >= min utilization for departments with members."""
        report = service.get_utilization_report()
        for du in report.departments:
            if du.headcount > 0:
                assert du.max_utilization >= du.min_utilization


# ============================================================================
# Skill Gaps
# ============================================================================


class TestSkillGaps:
    """Tests for skill gap identification."""

    def test_skill_gaps_found(self, service: WorkforcePlanningService):
        """Should identify skill gaps from capacity requirements."""
        report = service.identify_skill_gaps()
        assert report.total_gaps > 0

    def test_skill_gaps_have_recommendations(self, service: WorkforcePlanningService):
        """All skill gaps should have recommendations."""
        report = service.identify_skill_gaps()
        for gap in report.gaps:
            assert len(gap.recommendation) > 0

    def test_skill_gaps_critical_count(self, service: WorkforcePlanningService):
        """Should identify at least one critical gap."""
        report = service.identify_skill_gaps()
        assert report.critical_gaps >= 1

    def test_skill_gaps_gap_fte_positive(self, service: WorkforcePlanningService):
        """All gaps should have positive gap FTE."""
        report = service.identify_skill_gaps()
        for gap in report.gaps:
            assert gap.gap_fte > 0

    def test_skill_gaps_priorities_valid(self, service: WorkforcePlanningService):
        """All gaps should have valid priority levels."""
        report = service.identify_skill_gaps()
        valid_priorities = set(Priority)
        for gap in report.gaps:
            assert gap.priority in valid_priorities


# ============================================================================
# Singleton Pattern
# ============================================================================


class TestSingleton:
    """Tests for singleton service pattern."""

    def test_singleton_returns_same_instance(self):
        """get_workforce_planning_service should return the same instance."""
        svc1 = get_workforce_planning_service()
        svc2 = get_workforce_planning_service()
        assert svc1 is svc2

    def test_reset_creates_new_instance(self):
        """reset_workforce_planning_service should create a new instance."""
        svc1 = get_workforce_planning_service()
        reset_workforce_planning_service()
        svc2 = get_workforce_planning_service()
        assert svc1 is not svc2


# ============================================================================
# API Endpoint Integration Tests
# ============================================================================


class TestAPIEndpoints:
    """Integration tests for all API endpoints."""

    @pytest.mark.anyio
    async def test_get_metrics(self, client: AsyncClient):
        """GET /workforce-planning/metrics should return 200."""
        resp = await client.get("/api/v1/workforce-planning/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_headcount" in data
        assert "total_fte" in data
        assert data["total_headcount"] >= 25

    @pytest.mark.anyio
    async def test_list_team_members(self, client: AsyncClient):
        """GET /workforce-planning/team-members should return 200."""
        resp = await client.get("/api/v1/workforce-planning/team-members")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "members" in data
        assert data["total"] >= 25

    @pytest.mark.anyio
    async def test_list_team_members_filter(self, client: AsyncClient):
        """GET /workforce-planning/team-members?department=engineering should filter."""
        resp = await client.get(
            "/api/v1/workforce-planning/team-members",
            params={"department": "engineering"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] > 0
        for member in data["members"]:
            assert member["department"] == "engineering"

    @pytest.mark.anyio
    async def test_get_team_member(self, client: AsyncClient):
        """GET /workforce-planning/team-members/{id} should return 200."""
        # First list to get an ID
        list_resp = await client.get("/api/v1/workforce-planning/team-members")
        member_id = list_resp.json()["members"][0]["id"]
        resp = await client.get(f"/api/v1/workforce-planning/team-members/{member_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == member_id

    @pytest.mark.anyio
    async def test_get_team_member_not_found(self, client: AsyncClient):
        """GET /workforce-planning/team-members/nonexistent should return 404."""
        resp = await client.get("/api/v1/workforce-planning/team-members/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_add_team_member(self, client: AsyncClient):
        """POST /workforce-planning/team-members should return 201."""
        resp = await client.post(
            "/api/v1/workforce-planning/team-members",
            json={
                "name": "API Test Person",
                "department": "engineering",
                "role": "API Test Engineer",
                "skill_level": "mid",
                "fte_equivalent": 1.0,
                "hire_date": "2024-06-01",
                "annual_cost": 140000,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "API Test Person"
        assert data["id"] is not None

    @pytest.mark.anyio
    async def test_update_team_member(self, client: AsyncClient):
        """PUT /workforce-planning/team-members/{id} should return 200."""
        # Create first
        create_resp = await client.post(
            "/api/v1/workforce-planning/team-members",
            json={
                "name": "To Update",
                "department": "product",
                "role": "PM",
                "skill_level": "junior",
                "fte_equivalent": 1.0,
                "hire_date": "2024-01-01",
                "annual_cost": 100000,
            },
        )
        member_id = create_resp.json()["id"]
        resp = await client.put(
            f"/api/v1/workforce-planning/team-members/{member_id}",
            json={"name": "Updated Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    @pytest.mark.anyio
    async def test_delete_team_member(self, client: AsyncClient):
        """DELETE /workforce-planning/team-members/{id} should return 204."""
        create_resp = await client.post(
            "/api/v1/workforce-planning/team-members",
            json={
                "name": "To Delete",
                "department": "support",
                "role": "Support",
                "skill_level": "junior",
                "fte_equivalent": 1.0,
                "hire_date": "2024-01-01",
                "annual_cost": 80000,
            },
        )
        member_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/v1/workforce-planning/team-members/{member_id}")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_list_capacity_requirements(self, client: AsyncClient):
        """GET /workforce-planning/capacity-requirements should return 200."""
        resp = await client.get("/api/v1/workforce-planning/capacity-requirements")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert data["total"] >= 5

    @pytest.mark.anyio
    async def test_add_capacity_requirement(self, client: AsyncClient):
        """POST /workforce-planning/capacity-requirements should return 201."""
        resp = await client.post(
            "/api/v1/workforce-planning/capacity-requirements",
            json={
                "department": "engineering",
                "role": "API Test Role",
                "skill_level": "senior",
                "required_fte": 2.0,
                "current_fte": 0.5,
                "priority": "high",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["gap"] == 1.5

    @pytest.mark.anyio
    async def test_get_capacity_requirement(self, client: AsyncClient):
        """GET /workforce-planning/capacity-requirements/{id} should return 200."""
        list_resp = await client.get("/api/v1/workforce-planning/capacity-requirements")
        req_id = list_resp.json()["requirements"][0]["id"]
        resp = await client.get(f"/api/v1/workforce-planning/capacity-requirements/{req_id}")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_update_capacity_requirement(self, client: AsyncClient):
        """PUT /workforce-planning/capacity-requirements/{id} should return 200."""
        list_resp = await client.get("/api/v1/workforce-planning/capacity-requirements")
        req_id = list_resp.json()["requirements"][0]["id"]
        resp = await client.put(
            f"/api/v1/workforce-planning/capacity-requirements/{req_id}",
            json={"priority": "critical"},
        )
        assert resp.status_code == 200
        assert resp.json()["priority"] == "critical"

    @pytest.mark.anyio
    async def test_delete_capacity_requirement(self, client: AsyncClient):
        """DELETE /workforce-planning/capacity-requirements/{id} should return 204."""
        create_resp = await client.post(
            "/api/v1/workforce-planning/capacity-requirements",
            json={
                "department": "support",
                "role": "To Delete",
                "skill_level": "junior",
                "required_fte": 1.0,
                "current_fte": 0.0,
            },
        )
        req_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/v1/workforce-planning/capacity-requirements/{req_id}")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_list_hiring_plans(self, client: AsyncClient):
        """GET /workforce-planning/hiring-plans should return 200."""
        resp = await client.get("/api/v1/workforce-planning/hiring-plans")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert data["total"] >= 3

    @pytest.mark.anyio
    async def test_add_hiring_plan(self, client: AsyncClient):
        """POST /workforce-planning/hiring-plans should return 201."""
        resp = await client.post(
            "/api/v1/workforce-planning/hiring-plans",
            json={
                "department": "data_science",
                "role": "API Test ML Eng",
                "skill_level": "senior",
                "planned_start": "2025-08-01",
                "estimated_salary": 180000,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "open"

    @pytest.mark.anyio
    async def test_get_hiring_plan(self, client: AsyncClient):
        """GET /workforce-planning/hiring-plans/{id} should return 200."""
        list_resp = await client.get("/api/v1/workforce-planning/hiring-plans")
        plan_id = list_resp.json()["plans"][0]["id"]
        resp = await client.get(f"/api/v1/workforce-planning/hiring-plans/{plan_id}")
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_update_hiring_plan(self, client: AsyncClient):
        """PUT /workforce-planning/hiring-plans/{id} should return 200."""
        list_resp = await client.get("/api/v1/workforce-planning/hiring-plans")
        plan_id = list_resp.json()["plans"][0]["id"]
        resp = await client.put(
            f"/api/v1/workforce-planning/hiring-plans/{plan_id}",
            json={"status": "filled"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "filled"

    @pytest.mark.anyio
    async def test_delete_hiring_plan(self, client: AsyncClient):
        """DELETE /workforce-planning/hiring-plans/{id} should return 204."""
        create_resp = await client.post(
            "/api/v1/workforce-planning/hiring-plans",
            json={
                "department": "sales",
                "role": "To Delete",
                "skill_level": "junior",
                "planned_start": "2025-09-01",
                "estimated_salary": 80000,
            },
        )
        plan_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/v1/workforce-planning/hiring-plans/{plan_id}")
        assert resp.status_code == 204

    @pytest.mark.anyio
    async def test_capacity_by_department(self, client: AsyncClient):
        """GET /workforce-planning/capacity-by-department should return 200."""
        resp = await client.get("/api/v1/workforce-planning/capacity-by-department")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == len(Department)

    @pytest.mark.anyio
    async def test_capacity_projection(self, client: AsyncClient):
        """GET /workforce-planning/capacity-projection should return 200."""
        resp = await client.get(
            "/api/v1/workforce-planning/capacity-projection",
            params={"months": 6},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["months"] == 6
        assert len(data["projections"]) == 6

    @pytest.mark.anyio
    async def test_utilization_report(self, client: AsyncClient):
        """GET /workforce-planning/utilization should return 200."""
        resp = await client.get("/api/v1/workforce-planning/utilization")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_avg_utilization" in data
        assert "departments" in data

    @pytest.mark.anyio
    async def test_skill_gaps(self, client: AsyncClient):
        """GET /workforce-planning/skill-gaps should return 200."""
        resp = await client.get("/api/v1/workforce-planning/skill-gaps")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_gaps" in data
        assert data["total_gaps"] > 0
