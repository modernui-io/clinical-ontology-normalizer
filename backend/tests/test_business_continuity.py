"""Tests for Business Continuity Testing (COO-2).

Tests verify:
- Tabletop scenario listing and detail
- Scenario filtering by severity
- Exercise scheduling and lifecycle
- Exercise status transitions (valid and invalid)
- Exercise update with findings, action items, success criteria
- Procedure validation for all scenarios
- Procedure validation for specific scenarios
- BC metrics calculation
- RTO/RPO compliance tracking
- Action item closure rate
- Overall readiness score
- API endpoint integration tests (all 8 endpoints)
- Error handling (404, 400)
- Duration parsing
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.business_continuity import router as business_continuity_router
from app.schemas.business_continuity import (
    ActionItem,
    BCMetrics,
    ExerciseCreate,
    ExerciseListResponse,
    ExerciseResponse,
    ExerciseStatus,
    ExerciseUpdate,
    ProcedureValidationReport,
    Severity,
    SuccessCriterion,
    TabletopScenario,
)
from app.services.business_continuity_service import (
    BusinessContinuityService,
    ExerciseRecord,
    TABLETOP_SCENARIOS,
    _duration_lte,
    _parse_duration_hours,
    get_business_continuity_service,
    reset_business_continuity_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons between tests."""
    reset_business_continuity_service()
    yield
    reset_business_continuity_service()


@pytest.fixture
def service() -> BusinessContinuityService:
    """Fresh BusinessContinuityService instance."""
    return BusinessContinuityService()


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient with BC router mounted."""
    app = FastAPI()
    app.include_router(business_continuity_router, prefix="/api/v1")
    return TestClient(app)


# ===========================================================================
# 1. Tabletop Scenario Tests
# ===========================================================================


class TestScenarios:
    """Tests for tabletop scenario management."""

    def test_list_all_scenarios(self, service: BusinessContinuityService):
        """All 8 pre-defined scenarios are available."""
        scenarios = service.list_scenarios()
        assert len(scenarios) == 8

    def test_scenario_ids_are_unique(self, service: BusinessContinuityService):
        """Each scenario has a unique ID."""
        scenarios = service.list_scenarios()
        ids = [s.id for s in scenarios]
        assert len(ids) == len(set(ids))

    def test_scenario_has_required_fields(self, service: BusinessContinuityService):
        """Each scenario has all required fields populated."""
        for scenario in service.list_scenarios():
            assert scenario.id
            assert scenario.title
            assert scenario.description
            assert scenario.severity in Severity
            assert len(scenario.affected_systems) > 0
            assert scenario.expected_rto
            assert scenario.expected_rpo
            assert len(scenario.recovery_steps) > 0
            assert len(scenario.roles_involved) > 0
            assert len(scenario.success_criteria) > 0

    def test_get_scenario_by_id(self, service: BusinessContinuityService):
        """Can retrieve a specific scenario by ID."""
        scenario = service.get_scenario("SCENARIO_1")
        assert scenario is not None
        assert scenario.id == "SCENARIO_1"
        assert "database corruption" in scenario.title.lower()

    def test_get_scenario_not_found(self, service: BusinessContinuityService):
        """Returns None for unknown scenario ID."""
        result = service.get_scenario("SCENARIO_999")
        assert result is None

    def test_filter_scenarios_by_severity_critical(
        self, service: BusinessContinuityService
    ):
        """Filter scenarios by CRITICAL severity."""
        critical = service.list_scenarios(severity=Severity.CRITICAL)
        assert len(critical) > 0
        assert all(s.severity == Severity.CRITICAL for s in critical)

    def test_filter_scenarios_by_severity_high(
        self, service: BusinessContinuityService
    ):
        """Filter scenarios by HIGH severity."""
        high = service.list_scenarios(severity=Severity.HIGH)
        assert len(high) > 0
        assert all(s.severity == Severity.HIGH for s in high)

    def test_filter_scenarios_by_severity_medium(
        self, service: BusinessContinuityService
    ):
        """Filter scenarios by MEDIUM severity."""
        medium = service.list_scenarios(severity=Severity.MEDIUM)
        assert len(medium) > 0
        assert all(s.severity == Severity.MEDIUM for s in medium)

    def test_filter_scenarios_by_severity_low_returns_empty(
        self, service: BusinessContinuityService
    ):
        """No scenarios have LOW severity in default set."""
        low = service.list_scenarios(severity=Severity.LOW)
        assert len(low) == 0

    def test_scenario_recovery_steps_are_ordered(
        self, service: BusinessContinuityService
    ):
        """Recovery steps are sequentially ordered."""
        for scenario in service.list_scenarios():
            orders = [s.order for s in scenario.recovery_steps]
            expected = list(range(1, len(orders) + 1))
            assert orders == expected, f"Scenario {scenario.id} has unordered steps"

    def test_scenario_1_details(self, service: BusinessContinuityService):
        """SCENARIO_1: DB corruption has correct structure."""
        s = service.get_scenario("SCENARIO_1")
        assert s is not None
        assert s.severity == Severity.CRITICAL
        assert "PostgreSQL" in s.affected_systems[0]
        assert len(s.recovery_steps) >= 5
        assert "DBA" in s.roles_involved

    def test_scenario_3_phi_breach(self, service: BusinessContinuityService):
        """SCENARIO_3: PHI breach has appropriate response steps."""
        s = service.get_scenario("SCENARIO_3")
        assert s is not None
        assert s.severity == Severity.CRITICAL
        assert any("revoke" in step.action.lower() for step in s.recovery_steps)
        assert "Privacy Officer" in s.roles_involved


# ===========================================================================
# 2. Exercise Lifecycle Tests
# ===========================================================================


class TestExercises:
    """Tests for exercise scheduling and management."""

    def test_schedule_exercise(self, service: BusinessContinuityService):
        """Can schedule an exercise for a valid scenario."""
        scheduled = datetime.now(timezone.utc) + timedelta(days=7)
        ex = service.schedule_exercise(
            scenario_id="SCENARIO_1",
            scheduled_date=scheduled,
            participants=["Alice", "Bob"],
            notes="Quarterly drill",
        )
        assert ex.id.startswith("EX-")
        assert ex.scenario_id == "SCENARIO_1"
        assert ex.status == ExerciseStatus.PLANNED
        assert len(ex.participants) == 2
        assert ex.notes == "Quarterly drill"

    def test_schedule_exercise_invalid_scenario(
        self, service: BusinessContinuityService
    ):
        """Scheduling for unknown scenario raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.schedule_exercise(
                scenario_id="SCENARIO_INVALID",
                scheduled_date=datetime.now(timezone.utc),
            )

    def test_get_exercise_by_id(self, service: BusinessContinuityService):
        """Can retrieve a scheduled exercise."""
        ex = service.schedule_exercise(
            scenario_id="SCENARIO_2",
            scheduled_date=datetime.now(timezone.utc) + timedelta(days=14),
        )
        retrieved = service.get_exercise(ex.id)
        assert retrieved is not None
        assert retrieved.id == ex.id

    def test_get_exercise_not_found(self, service: BusinessContinuityService):
        """Returns None for unknown exercise ID."""
        assert service.get_exercise("EX-nonexistent") is None

    def test_list_exercises_empty(self, service: BusinessContinuityService):
        """Empty list when no exercises scheduled."""
        exercises, total = service.list_exercises()
        assert total == 0
        assert exercises == []

    def test_list_exercises_with_data(self, service: BusinessContinuityService):
        """Lists exercises after scheduling."""
        for i in range(3):
            service.schedule_exercise(
                scenario_id="SCENARIO_1",
                scheduled_date=datetime.now(timezone.utc) + timedelta(days=i + 1),
            )
        exercises, total = service.list_exercises()
        assert total == 3

    def test_list_exercises_filter_by_scenario(
        self, service: BusinessContinuityService
    ):
        """Filter exercises by scenario_id."""
        service.schedule_exercise(
            scenario_id="SCENARIO_1",
            scheduled_date=datetime.now(timezone.utc) + timedelta(days=1),
        )
        service.schedule_exercise(
            scenario_id="SCENARIO_2",
            scheduled_date=datetime.now(timezone.utc) + timedelta(days=2),
        )
        exercises, total = service.list_exercises(scenario_id="SCENARIO_1")
        assert total == 1
        assert exercises[0].scenario_id == "SCENARIO_1"

    def test_list_exercises_filter_by_status(
        self, service: BusinessContinuityService
    ):
        """Filter exercises by status."""
        ex = service.schedule_exercise(
            scenario_id="SCENARIO_1",
            scheduled_date=datetime.now(timezone.utc),
        )
        service.update_exercise(ex.id, status=ExerciseStatus.IN_PROGRESS)
        service.schedule_exercise(
            scenario_id="SCENARIO_2",
            scheduled_date=datetime.now(timezone.utc) + timedelta(days=1),
        )

        in_progress, total = service.list_exercises(status=ExerciseStatus.IN_PROGRESS)
        assert total == 1
        assert in_progress[0].status == ExerciseStatus.IN_PROGRESS

    def test_list_exercises_pagination(self, service: BusinessContinuityService):
        """Pagination works correctly."""
        for i in range(5):
            service.schedule_exercise(
                scenario_id="SCENARIO_1",
                scheduled_date=datetime.now(timezone.utc) + timedelta(days=i),
            )
        exercises, total = service.list_exercises(limit=2, offset=0)
        assert total == 5
        assert len(exercises) == 2

        exercises2, total2 = service.list_exercises(limit=2, offset=2)
        assert total2 == 5
        assert len(exercises2) == 2


# ===========================================================================
# 3. Exercise Status Transitions
# ===========================================================================


class TestExerciseTransitions:
    """Tests for exercise status state machine."""

    def test_planned_to_in_progress(self, service: BusinessContinuityService):
        """PLANNED -> IN_PROGRESS is valid."""
        ex = service.schedule_exercise(
            scenario_id="SCENARIO_1",
            scheduled_date=datetime.now(timezone.utc),
        )
        updated = service.update_exercise(ex.id, status=ExerciseStatus.IN_PROGRESS)
        assert updated.status == ExerciseStatus.IN_PROGRESS

    def test_planned_to_cancelled(self, service: BusinessContinuityService):
        """PLANNED -> CANCELLED is valid."""
        ex = service.schedule_exercise(
            scenario_id="SCENARIO_1",
            scheduled_date=datetime.now(timezone.utc),
        )
        updated = service.update_exercise(ex.id, status=ExerciseStatus.CANCELLED)
        assert updated.status == ExerciseStatus.CANCELLED

    def test_in_progress_to_completed(self, service: BusinessContinuityService):
        """IN_PROGRESS -> COMPLETED is valid."""
        ex = service.schedule_exercise(
            scenario_id="SCENARIO_1",
            scheduled_date=datetime.now(timezone.utc),
        )
        service.update_exercise(ex.id, status=ExerciseStatus.IN_PROGRESS)
        updated = service.update_exercise(ex.id, status=ExerciseStatus.COMPLETED)
        assert updated.status == ExerciseStatus.COMPLETED

    def test_invalid_transition_planned_to_completed(
        self, service: BusinessContinuityService
    ):
        """PLANNED -> COMPLETED is invalid (must go through IN_PROGRESS)."""
        ex = service.schedule_exercise(
            scenario_id="SCENARIO_1",
            scheduled_date=datetime.now(timezone.utc),
        )
        with pytest.raises(ValueError, match="Invalid status transition"):
            service.update_exercise(ex.id, status=ExerciseStatus.COMPLETED)

    def test_completed_is_terminal(self, service: BusinessContinuityService):
        """COMPLETED is a terminal state."""
        ex = service.schedule_exercise(
            scenario_id="SCENARIO_1",
            scheduled_date=datetime.now(timezone.utc),
        )
        service.update_exercise(ex.id, status=ExerciseStatus.IN_PROGRESS)
        service.update_exercise(ex.id, status=ExerciseStatus.COMPLETED)
        with pytest.raises(ValueError, match="Invalid status transition"):
            service.update_exercise(ex.id, status=ExerciseStatus.IN_PROGRESS)

    def test_cancelled_is_terminal(self, service: BusinessContinuityService):
        """CANCELLED is a terminal state."""
        ex = service.schedule_exercise(
            scenario_id="SCENARIO_1",
            scheduled_date=datetime.now(timezone.utc),
        )
        service.update_exercise(ex.id, status=ExerciseStatus.CANCELLED)
        with pytest.raises(ValueError, match="Invalid status transition"):
            service.update_exercise(ex.id, status=ExerciseStatus.IN_PROGRESS)

    def test_update_exercise_not_found(self, service: BusinessContinuityService):
        """Updating non-existent exercise raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.update_exercise("EX-nonexistent", status=ExerciseStatus.IN_PROGRESS)


# ===========================================================================
# 4. Exercise Update with Results
# ===========================================================================


class TestExerciseResults:
    """Tests for recording exercise results."""

    def test_update_exercise_with_findings(self, service: BusinessContinuityService):
        """Can record findings from an exercise."""
        ex = service.schedule_exercise(
            scenario_id="SCENARIO_1",
            scheduled_date=datetime.now(timezone.utc),
        )
        service.update_exercise(ex.id, status=ExerciseStatus.IN_PROGRESS)
        updated = service.update_exercise(
            ex.id,
            findings=["Backup restore took 2x expected time", "Runbook out of date"],
        )
        assert len(updated.findings) == 2

    def test_update_exercise_with_action_items(
        self, service: BusinessContinuityService
    ):
        """Can record action items from an exercise."""
        ex = service.schedule_exercise(
            scenario_id="SCENARIO_1",
            scheduled_date=datetime.now(timezone.utc),
        )
        action_items = [
            ActionItem(
                id="AI-001",
                description="Update backup restore runbook",
                assignee="DBA Lead",
                status="OPEN",
            ),
            ActionItem(
                id="AI-002",
                description="Increase backup frequency to hourly",
                assignee="Platform Engineer",
                status="OPEN",
            ),
        ]
        updated = service.update_exercise(ex.id, action_items=action_items)
        assert len(updated.action_items) == 2

    def test_update_exercise_with_rto_rpo(self, service: BusinessContinuityService):
        """Can record actual RTO and RPO."""
        ex = service.schedule_exercise(
            scenario_id="SCENARIO_1",
            scheduled_date=datetime.now(timezone.utc),
        )
        updated = service.update_exercise(
            ex.id,
            actual_rto="3 hours",
            actual_rpo="45 minutes",
        )
        assert updated.actual_rto == "3 hours"
        assert updated.actual_rpo == "45 minutes"

    def test_update_exercise_conducted_date(
        self, service: BusinessContinuityService
    ):
        """Can record when exercise was conducted."""
        ex = service.schedule_exercise(
            scenario_id="SCENARIO_1",
            scheduled_date=datetime.now(timezone.utc),
        )
        now = datetime.now(timezone.utc)
        updated = service.update_exercise(ex.id, conducted_date=now)
        assert updated.conducted_date == now

    def test_update_exercise_success_criteria(
        self, service: BusinessContinuityService
    ):
        """Can record evaluated success criteria."""
        ex = service.schedule_exercise(
            scenario_id="SCENARIO_1",
            scheduled_date=datetime.now(timezone.utc),
        )
        criteria = [
            SuccessCriterion(
                id="SC1-1",
                description="DB restored within RTO",
                measurement="Time measurement",
                met=True,
            ),
            SuccessCriterion(
                id="SC1-2",
                description="No data loss beyond RPO",
                measurement="Data comparison",
                met=False,
            ),
        ]
        updated = service.update_exercise(ex.id, success_criteria_results=criteria)
        assert len(updated.success_criteria_results) == 2
        assert updated.success_criteria_results[0].met is True
        assert updated.success_criteria_results[1].met is False


# ===========================================================================
# 5. Procedure Validation Tests
# ===========================================================================


class TestProcedureValidation:
    """Tests for recovery procedure validation."""

    def test_validate_all_procedures(self, service: BusinessContinuityService):
        """Validate all scenario procedures."""
        report = service.validate_procedures()
        assert report.total_scenarios == 8
        assert report.valid_scenarios > 0
        assert len(report.results) == 8

    def test_validate_specific_scenario(self, service: BusinessContinuityService):
        """Validate procedures for a specific scenario."""
        report = service.validate_procedures(scenario_ids=["SCENARIO_1"])
        assert report.total_scenarios == 1
        assert report.results[0].scenario_id == "SCENARIO_1"

    def test_all_scenarios_have_valid_procedures(
        self, service: BusinessContinuityService
    ):
        """All built-in scenarios pass validation."""
        report = service.validate_procedures()
        for result in report.results:
            assert result.overall_valid, (
                f"Scenario {result.scenario_id} failed validation: "
                f"{[c for c in result.checks if not c.passed]}"
            )

    def test_validation_checks_completeness(
        self, service: BusinessContinuityService
    ):
        """Validation includes all expected checks."""
        report = service.validate_procedures(scenario_ids=["SCENARIO_1"])
        result = report.results[0]
        check_names = {c.check_name for c in result.checks}
        expected_checks = {
            "recovery_steps_defined",
            "steps_properly_ordered",
            "documentation_references",
            "roles_assigned",
            "success_criteria_defined",
            "roles_involved_defined",
            "rto_rpo_specified",
        }
        assert expected_checks.issubset(check_names)

    def test_validate_invalid_scenario_id_ignored(
        self, service: BusinessContinuityService
    ):
        """Invalid scenario IDs are silently ignored."""
        report = service.validate_procedures(scenario_ids=["NONEXISTENT"])
        assert report.total_scenarios == 0


# ===========================================================================
# 6. BC Metrics Tests
# ===========================================================================


class TestBCMetrics:
    """Tests for BC program metrics calculation."""

    def test_metrics_empty_state(self, service: BusinessContinuityService):
        """Metrics work with no exercises."""
        metrics = service.get_metrics()
        assert metrics.total_scenarios == 8
        assert metrics.total_exercises == 0
        assert metrics.completed_exercises == 0
        assert metrics.rto_compliance_rate == 100.0
        assert metrics.rpo_compliance_rate == 100.0
        assert metrics.action_item_closure_rate == 100.0

    def test_metrics_with_completed_exercise(
        self, service: BusinessContinuityService
    ):
        """Metrics track completed exercises."""
        ex = service.schedule_exercise(
            scenario_id="SCENARIO_1",
            scheduled_date=datetime.now(timezone.utc),
        )
        service.update_exercise(ex.id, status=ExerciseStatus.IN_PROGRESS)
        service.update_exercise(
            ex.id,
            status=ExerciseStatus.COMPLETED,
            conducted_date=datetime.now(timezone.utc),
            actual_rto="3 hours",
            actual_rpo="30 minutes",
        )

        metrics = service.get_metrics()
        assert metrics.total_exercises == 1
        assert metrics.completed_exercises == 1
        assert metrics.rto_compliance_rate == 100.0  # 3h <= 4h

    def test_metrics_rto_non_compliant(self, service: BusinessContinuityService):
        """RTO non-compliance when actual exceeds expected."""
        ex = service.schedule_exercise(
            scenario_id="SCENARIO_1",
            scheduled_date=datetime.now(timezone.utc),
        )
        service.update_exercise(ex.id, status=ExerciseStatus.IN_PROGRESS)
        service.update_exercise(
            ex.id,
            status=ExerciseStatus.COMPLETED,
            conducted_date=datetime.now(timezone.utc),
            actual_rto="6 hours",  # exceeds 4h RTO
            actual_rpo="30 minutes",
        )
        metrics = service.get_metrics()
        assert metrics.rto_compliance_rate == 0.0

    def test_metrics_action_item_closure(self, service: BusinessContinuityService):
        """Action item closure rate calculated correctly."""
        ex = service.schedule_exercise(
            scenario_id="SCENARIO_1",
            scheduled_date=datetime.now(timezone.utc),
        )
        items = [
            ActionItem(id="AI-1", description="Fix A", assignee="Alice", status="CLOSED"),
            ActionItem(id="AI-2", description="Fix B", assignee="Bob", status="OPEN"),
        ]
        service.update_exercise(ex.id, action_items=items)
        metrics = service.get_metrics()
        assert metrics.total_action_items == 2
        assert metrics.closed_action_items == 1
        assert metrics.open_action_items == 1
        assert metrics.action_item_closure_rate == 50.0

    def test_metrics_scenario_coverage(self, service: BusinessContinuityService):
        """Scenario coverage is reported per scenario."""
        metrics = service.get_metrics()
        assert len(metrics.scenario_coverage) == 8
        for cov in metrics.scenario_coverage:
            assert cov.scenario_id
            assert cov.scenario_title

    def test_metrics_readiness_score_range(self, service: BusinessContinuityService):
        """Readiness score is between 0 and 100."""
        metrics = service.get_metrics()
        assert 0 <= metrics.overall_readiness_score <= 100


# ===========================================================================
# 7. Duration Parsing Tests
# ===========================================================================


class TestDurationParsing:
    """Tests for duration string parsing and comparison."""

    def test_parse_hours(self):
        """Parse hour durations."""
        assert _parse_duration_hours("4 hours") == 4.0
        assert _parse_duration_hours("1 hour") == 1.0

    def test_parse_minutes(self):
        """Parse minute durations."""
        assert _parse_duration_hours("30 minutes") == 0.5
        assert _parse_duration_hours("90 minutes") == 1.5

    def test_parse_days(self):
        """Parse day durations."""
        assert _parse_duration_hours("1 day") == 24.0
        assert _parse_duration_hours("2 days") == 48.0

    def test_duration_comparison(self):
        """Duration less-than-or-equal comparison."""
        assert _duration_lte("3 hours", "4 hours") is True
        assert _duration_lte("4 hours", "4 hours") is True
        assert _duration_lte("5 hours", "4 hours") is False
        assert _duration_lte("30 minutes", "1 hour") is True


# ===========================================================================
# 8. API Endpoint Tests
# ===========================================================================


class TestScenariosAPI:
    """API tests for scenario endpoints."""

    def test_list_scenarios_api(self, client: TestClient):
        """GET /operations/bc/scenarios returns all scenarios."""
        resp = client.get("/api/v1/operations/bc/scenarios")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 8

    def test_list_scenarios_filter_severity(self, client: TestClient):
        """GET /operations/bc/scenarios?severity=CRITICAL filters correctly."""
        resp = client.get("/api/v1/operations/bc/scenarios?severity=CRITICAL")
        assert resp.status_code == 200
        data = resp.json()
        assert all(s["severity"] == "CRITICAL" for s in data)

    def test_get_scenario_api(self, client: TestClient):
        """GET /operations/bc/scenarios/{id} returns scenario detail."""
        resp = client.get("/api/v1/operations/bc/scenarios/SCENARIO_1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "SCENARIO_1"
        assert len(data["recovery_steps"]) > 0
        assert len(data["success_criteria"]) > 0

    def test_get_scenario_not_found_api(self, client: TestClient):
        """GET /operations/bc/scenarios/{id} returns 404 for unknown."""
        resp = client.get("/api/v1/operations/bc/scenarios/SCENARIO_999")
        assert resp.status_code == 404


class TestExercisesAPI:
    """API tests for exercise endpoints."""

    def test_schedule_exercise_api(self, client: TestClient):
        """POST /operations/bc/exercises schedules an exercise."""
        scheduled = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        resp = client.post(
            "/api/v1/operations/bc/exercises",
            json={
                "scenario_id": "SCENARIO_1",
                "scheduled_date": scheduled,
                "participants": ["Alice", "Bob"],
                "notes": "Quarterly drill",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["scenario_id"] == "SCENARIO_1"
        assert data["status"] == "PLANNED"
        assert len(data["participants"]) == 2

    def test_schedule_exercise_invalid_scenario_api(self, client: TestClient):
        """POST /operations/bc/exercises returns 400 for invalid scenario."""
        scheduled = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        resp = client.post(
            "/api/v1/operations/bc/exercises",
            json={
                "scenario_id": "INVALID",
                "scheduled_date": scheduled,
            },
        )
        assert resp.status_code == 400

    def test_list_exercises_api(self, client: TestClient):
        """GET /operations/bc/exercises returns exercise list."""
        # Schedule one first
        scheduled = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        client.post(
            "/api/v1/operations/bc/exercises",
            json={"scenario_id": "SCENARIO_1", "scheduled_date": scheduled},
        )
        resp = client.get("/api/v1/operations/bc/exercises")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["exercises"]) == 1

    def test_get_exercise_api(self, client: TestClient):
        """GET /operations/bc/exercises/{id} returns exercise detail."""
        scheduled = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        create_resp = client.post(
            "/api/v1/operations/bc/exercises",
            json={"scenario_id": "SCENARIO_2", "scheduled_date": scheduled},
        )
        ex_id = create_resp.json()["id"]
        resp = client.get(f"/api/v1/operations/bc/exercises/{ex_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == ex_id

    def test_get_exercise_not_found_api(self, client: TestClient):
        """GET /operations/bc/exercises/{id} returns 404 for unknown."""
        resp = client.get("/api/v1/operations/bc/exercises/EX-nonexistent")
        assert resp.status_code == 404

    def test_update_exercise_api(self, client: TestClient):
        """PUT /operations/bc/exercises/{id} updates exercise."""
        scheduled = datetime.now(timezone.utc).isoformat()
        create_resp = client.post(
            "/api/v1/operations/bc/exercises",
            json={"scenario_id": "SCENARIO_1", "scheduled_date": scheduled},
        )
        ex_id = create_resp.json()["id"]

        # Transition to IN_PROGRESS
        resp = client.put(
            f"/api/v1/operations/bc/exercises/{ex_id}",
            json={"status": "IN_PROGRESS"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "IN_PROGRESS"

    def test_update_exercise_invalid_transition_api(self, client: TestClient):
        """PUT /operations/bc/exercises/{id} returns 400 for invalid transition."""
        scheduled = datetime.now(timezone.utc).isoformat()
        create_resp = client.post(
            "/api/v1/operations/bc/exercises",
            json={"scenario_id": "SCENARIO_1", "scheduled_date": scheduled},
        )
        ex_id = create_resp.json()["id"]

        # Try to go directly to COMPLETED (invalid)
        resp = client.put(
            f"/api/v1/operations/bc/exercises/{ex_id}",
            json={"status": "COMPLETED"},
        )
        assert resp.status_code == 400

    def test_update_exercise_not_found_api(self, client: TestClient):
        """PUT /operations/bc/exercises/{id} returns 404 for unknown."""
        resp = client.put(
            "/api/v1/operations/bc/exercises/EX-nonexistent",
            json={"status": "IN_PROGRESS"},
        )
        assert resp.status_code == 404


class TestMetricsAPI:
    """API tests for metrics endpoint."""

    def test_get_metrics_api(self, client: TestClient):
        """GET /operations/bc/metrics returns metrics."""
        resp = client.get("/api/v1/operations/bc/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_scenarios"] == 8
        assert "overall_readiness_score" in data
        assert "scenario_coverage" in data


class TestValidationAPI:
    """API tests for procedure validation endpoint."""

    def test_validate_procedures_api(self, client: TestClient):
        """POST /operations/bc/validate-procedures validates all."""
        resp = client.post("/api/v1/operations/bc/validate-procedures")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_scenarios"] == 8
        assert "results" in data

    def test_validate_specific_scenarios_api(self, client: TestClient):
        """POST /operations/bc/validate-procedures with specific IDs."""
        resp = client.post(
            "/api/v1/operations/bc/validate-procedures",
            json=["SCENARIO_1", "SCENARIO_2"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_scenarios"] == 2


# ===========================================================================
# 9. Singleton Management Tests
# ===========================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_service_returns_same_instance(self):
        """Singleton returns same instance."""
        svc1 = get_business_continuity_service()
        svc2 = get_business_continuity_service()
        assert svc1 is svc2

    def test_reset_clears_instance(self):
        """Reset creates new instance."""
        svc1 = get_business_continuity_service()
        reset_business_continuity_service()
        svc2 = get_business_continuity_service()
        assert svc1 is not svc2


# ===========================================================================
# 10. Schema Validation Tests
# ===========================================================================


class TestSchemas:
    """Tests for Pydantic schema validation."""

    def test_exercise_create_schema(self):
        """ExerciseCreate validates correctly."""
        data = ExerciseCreate(
            scenario_id="SCENARIO_1",
            scheduled_date=datetime.now(timezone.utc),
            participants=["Alice"],
        )
        assert data.scenario_id == "SCENARIO_1"

    def test_exercise_update_all_none(self):
        """ExerciseUpdate with all None is valid (no-op update)."""
        data = ExerciseUpdate()
        assert data.status is None
        assert data.findings is None

    def test_action_item_defaults(self):
        """ActionItem has sensible defaults."""
        item = ActionItem(id="AI-1", description="Fix thing", assignee="Alice")
        assert item.status == "OPEN"
        assert item.closed_at is None

    def test_tabletop_scenario_from_dict(self):
        """TabletopScenario can be constructed from dict."""
        scenarios = TABLETOP_SCENARIOS
        assert len(scenarios) >= 8
        for s in scenarios:
            assert isinstance(s, TabletopScenario)
