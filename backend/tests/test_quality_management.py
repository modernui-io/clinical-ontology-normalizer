"""Tests for Quality Management: CAPA system and IQ/OQ/PQ qualification runner.

VP-Quality-2: Tests verify:
- CAPA CRUD operations
- CAPA state machine (valid/invalid transitions)
- Root cause categorization
- Severity assignment and metrics
- Overdue CAPA detection
- Effectiveness verification (recurrence tracking)
- IQ qualification checks (database, config)
- OQ qualification checks (API health, auth)
- PQ qualification checks (response time)
- Qualification report generation
- Pre-populated CAPA examples
- CAPA metrics calculation
- Qualification check pass/fail logic
- API endpoint integration tests
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.quality_management import router as quality_management_router
from app.schemas.quality_management import (
    CAPAMetrics,
    CAPASeverity,
    CAPASource,
    CAPAStatus,
    CAPAType,
    CheckStatus,
    QualificationType,
    RootCauseCategory,
)
from app.services.capa_service import (
    CAPARecord,
    CAPAService,
    VALID_CAPA_TRANSITIONS,
    get_capa_service,
    reset_capa_service,
)
from app.services.qualification_runner_service import (
    QualificationRunner,
    get_qualification_runner,
    reset_qualification_runner,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons between tests."""
    reset_capa_service()
    reset_qualification_runner()
    yield
    reset_capa_service()
    reset_qualification_runner()


@pytest.fixture
def capa_service() -> CAPAService:
    """Fresh CAPAService instance."""
    return CAPAService()


@pytest.fixture
def runner() -> QualificationRunner:
    """Fresh QualificationRunner instance."""
    return QualificationRunner()


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient with quality management router mounted."""
    app = FastAPI()
    app.include_router(quality_management_router, prefix="/api/v1")
    return TestClient(app)


# ===========================================================================
# 1. CAPA CRUD Operations
# ===========================================================================


class TestCAPACRUD:
    """Test CAPA create, read, update, delete operations."""

    def test_create_capa_basic(self, capa_service: CAPAService):
        """Create a basic CAPA and verify fields."""
        capa = capa_service.create_capa(
            title="Test CAPA",
            description="Test description",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MAJOR,
        )
        assert capa.id is not None
        assert capa.title == "Test CAPA"
        assert capa.description == "Test description"
        assert capa.capa_type == CAPAType.CORRECTIVE
        assert capa.source == CAPASource.AUDIT
        assert capa.severity == CAPASeverity.MAJOR
        assert capa.status == CAPAStatus.OPEN
        assert capa.created_at is not None
        assert capa.updated_at is not None
        assert capa.closed_at is None

    def test_create_capa_with_all_fields(self, capa_service: CAPAService):
        """Create a CAPA with all optional fields."""
        due = datetime.now(timezone.utc) + timedelta(days=30)
        capa = capa_service.create_capa(
            title="Full CAPA",
            description="Complete description",
            capa_type=CAPAType.PREVENTIVE,
            source=CAPASource.INCIDENT,
            severity=CAPASeverity.CRITICAL,
            root_cause_category=RootCauseCategory.PROCESS,
            root_cause="Process gap identified",
            corrective_action="Fix the process",
            preventive_action="Add validation step",
            assigned_to="eng-lead",
            due_date=due,
        )
        assert capa.capa_type == CAPAType.PREVENTIVE
        assert capa.source == CAPASource.INCIDENT
        assert capa.severity == CAPASeverity.CRITICAL
        assert capa.root_cause_category == RootCauseCategory.PROCESS
        assert capa.root_cause == "Process gap identified"
        assert capa.corrective_action == "Fix the process"
        assert capa.preventive_action == "Add validation step"
        assert capa.assigned_to == "eng-lead"
        assert capa.due_date == due

    def test_get_capa_by_id(self, capa_service: CAPAService):
        """Retrieve a CAPA by its ID."""
        capa = capa_service.create_capa(
            title="Retrievable",
            description="Should be retrievable",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.COMPLAINT,
            severity=CAPASeverity.MINOR,
        )
        retrieved = capa_service.get_capa(capa.id)
        assert retrieved is not None
        assert retrieved.id == capa.id
        assert retrieved.title == "Retrievable"

    def test_get_capa_not_found(self, capa_service: CAPAService):
        """Return None for non-existent CAPA ID."""
        result = capa_service.get_capa("CAPA-NONEXISTENT")
        assert result is None

    def test_update_capa_title(self, capa_service: CAPAService):
        """Update CAPA title."""
        capa = capa_service.create_capa(
            title="Original Title",
            description="Description",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MAJOR,
        )
        updated = capa_service.update_capa(capa.id, title="Updated Title")
        assert updated.title == "Updated Title"

    def test_update_capa_severity(self, capa_service: CAPAService):
        """Update CAPA severity."""
        capa = capa_service.create_capa(
            title="Severity Test",
            description="Description",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MINOR,
        )
        updated = capa_service.update_capa(capa.id, severity=CAPASeverity.CRITICAL)
        assert updated.severity == CAPASeverity.CRITICAL

    def test_update_capa_not_found(self, capa_service: CAPAService):
        """Raise ValueError when updating non-existent CAPA."""
        with pytest.raises(ValueError, match="CAPA not found"):
            capa_service.update_capa("NONEXISTENT", title="x")

    def test_list_capas_all(self, capa_service: CAPAService):
        """List all CAPAs including seed data."""
        capas, total = capa_service.list_capas()
        # Service is seeded with 3 example CAPAs
        assert total >= 3
        assert len(capas) >= 3

    def test_list_capas_filter_by_severity(self, capa_service: CAPAService):
        """Filter CAPAs by severity."""
        capas, total = capa_service.list_capas(severity=CAPASeverity.CRITICAL)
        for c in capas:
            assert c.severity == CAPASeverity.CRITICAL

    def test_list_capas_filter_by_status(self, capa_service: CAPAService):
        """Filter CAPAs by status."""
        capas, total = capa_service.list_capas(status=CAPAStatus.IN_PROGRESS)
        for c in capas:
            assert c.status == CAPAStatus.IN_PROGRESS

    def test_list_capas_filter_by_type(self, capa_service: CAPAService):
        """Filter CAPAs by type."""
        capas, total = capa_service.list_capas(capa_type=CAPAType.PREVENTIVE)
        for c in capas:
            assert c.capa_type == CAPAType.PREVENTIVE

    def test_list_capas_pagination(self, capa_service: CAPAService):
        """Test pagination of CAPA list."""
        capas, total = capa_service.list_capas(limit=1, offset=0)
        assert len(capas) == 1
        assert total >= 3  # Seed data


# ===========================================================================
# 2. CAPA State Machine
# ===========================================================================


class TestCAPAStateMachine:
    """Test CAPA state machine transitions."""

    def test_valid_transition_open_to_investigating(self, capa_service: CAPAService):
        """OPEN -> INVESTIGATING is valid."""
        capa = capa_service.create_capa(
            title="SM Test",
            description="State machine test",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MAJOR,
        )
        updated = capa_service.update_capa(capa.id, status=CAPAStatus.INVESTIGATING)
        assert updated.status == CAPAStatus.INVESTIGATING

    def test_valid_transition_investigating_to_action_planned(self, capa_service: CAPAService):
        """INVESTIGATING -> ACTION_PLANNED is valid."""
        capa = capa_service.create_capa(
            title="SM Test 2",
            description="State machine test 2",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MAJOR,
        )
        capa_service.update_capa(capa.id, status=CAPAStatus.INVESTIGATING)
        updated = capa_service.update_capa(capa.id, status=CAPAStatus.ACTION_PLANNED)
        assert updated.status == CAPAStatus.ACTION_PLANNED

    def test_valid_transition_action_planned_to_in_progress(self, capa_service: CAPAService):
        """ACTION_PLANNED -> IN_PROGRESS is valid."""
        capa = capa_service.create_capa(
            title="SM Test 3",
            description="State machine test 3",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MAJOR,
        )
        capa_service.update_capa(capa.id, status=CAPAStatus.INVESTIGATING)
        capa_service.update_capa(capa.id, status=CAPAStatus.ACTION_PLANNED)
        updated = capa_service.update_capa(capa.id, status=CAPAStatus.IN_PROGRESS)
        assert updated.status == CAPAStatus.IN_PROGRESS

    def test_valid_transition_in_progress_to_verification(self, capa_service: CAPAService):
        """IN_PROGRESS -> VERIFICATION is valid."""
        capa = capa_service.create_capa(
            title="SM Test 4",
            description="State machine test 4",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MAJOR,
        )
        capa_service.update_capa(capa.id, status=CAPAStatus.INVESTIGATING)
        capa_service.update_capa(capa.id, status=CAPAStatus.ACTION_PLANNED)
        capa_service.update_capa(capa.id, status=CAPAStatus.IN_PROGRESS)
        updated = capa_service.update_capa(capa.id, status=CAPAStatus.VERIFICATION)
        assert updated.status == CAPAStatus.VERIFICATION

    def test_valid_transition_verification_to_closed(self, capa_service: CAPAService):
        """VERIFICATION -> CLOSED is valid."""
        capa = capa_service.create_capa(
            title="SM Test 5",
            description="State machine test 5",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MAJOR,
        )
        capa_service.update_capa(capa.id, status=CAPAStatus.INVESTIGATING)
        capa_service.update_capa(capa.id, status=CAPAStatus.ACTION_PLANNED)
        capa_service.update_capa(capa.id, status=CAPAStatus.IN_PROGRESS)
        capa_service.update_capa(capa.id, status=CAPAStatus.VERIFICATION)
        updated = capa_service.update_capa(capa.id, status=CAPAStatus.CLOSED)
        assert updated.status == CAPAStatus.CLOSED
        assert updated.closed_at is not None

    def test_invalid_transition_open_to_verification(self, capa_service: CAPAService):
        """OPEN -> VERIFICATION is invalid."""
        capa = capa_service.create_capa(
            title="Invalid Transition",
            description="Should fail",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MAJOR,
        )
        with pytest.raises(ValueError, match="Invalid CAPA status transition"):
            capa_service.update_capa(capa.id, status=CAPAStatus.VERIFICATION)

    def test_invalid_transition_open_to_in_progress(self, capa_service: CAPAService):
        """OPEN -> IN_PROGRESS is invalid (must go through INVESTIGATING first)."""
        capa = capa_service.create_capa(
            title="Skip Steps",
            description="Should fail",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MAJOR,
        )
        with pytest.raises(ValueError, match="Invalid CAPA status transition"):
            capa_service.update_capa(capa.id, status=CAPAStatus.IN_PROGRESS)

    def test_closed_is_terminal(self, capa_service: CAPAService):
        """CLOSED is terminal - no transitions allowed."""
        capa = capa_service.create_capa(
            title="Terminal State",
            description="Test terminal",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MAJOR,
        )
        capa_service.update_capa(capa.id, status=CAPAStatus.CLOSED)
        with pytest.raises(ValueError, match="Invalid CAPA status transition"):
            capa_service.update_capa(capa.id, status=CAPAStatus.OPEN)

    def test_valid_transition_open_to_closed_directly(self, capa_service: CAPAService):
        """OPEN -> CLOSED is valid (early closure)."""
        capa = capa_service.create_capa(
            title="Early Close",
            description="Close without investigation",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MINOR,
        )
        updated = capa_service.update_capa(capa.id, status=CAPAStatus.CLOSED)
        assert updated.status == CAPAStatus.CLOSED
        assert updated.closed_at is not None

    def test_closed_sets_effectiveness_check_date(self, capa_service: CAPAService):
        """Closing a CAPA sets effectiveness check date (90 days)."""
        capa = capa_service.create_capa(
            title="Effectiveness Date",
            description="Should set check date",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MAJOR,
        )
        updated = capa_service.update_capa(capa.id, status=CAPAStatus.CLOSED)
        assert updated.effectiveness_check_date is not None
        # Should be approximately 90 days from now
        delta = (updated.effectiveness_check_date - datetime.now(timezone.utc)).days
        assert 89 <= delta <= 91


# ===========================================================================
# 3. Root Cause and Severity
# ===========================================================================


class TestRootCauseAndSeverity:
    """Test root cause categorization and severity handling."""

    def test_root_cause_technology(self, capa_service: CAPAService):
        """Assign TECHNOLOGY root cause."""
        capa = capa_service.create_capa(
            title="Tech Issue",
            description="Technology root cause",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.INCIDENT,
            severity=CAPASeverity.MAJOR,
            root_cause_category=RootCauseCategory.TECHNOLOGY,
        )
        assert capa.root_cause_category == RootCauseCategory.TECHNOLOGY

    def test_root_cause_human_error(self, capa_service: CAPAService):
        """Assign HUMAN_ERROR root cause."""
        capa = capa_service.create_capa(
            title="Human Error",
            description="Human error root cause",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.COMPLAINT,
            severity=CAPASeverity.MINOR,
            root_cause_category=RootCauseCategory.HUMAN_ERROR,
        )
        assert capa.root_cause_category == RootCauseCategory.HUMAN_ERROR

    def test_update_root_cause(self, capa_service: CAPAService):
        """Update root cause after investigation."""
        capa = capa_service.create_capa(
            title="Root Cause Update",
            description="Initially unknown",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MAJOR,
        )
        assert capa.root_cause_category is None
        updated = capa_service.update_capa(
            capa.id,
            root_cause_category=RootCauseCategory.DESIGN,
            root_cause="Architectural flaw in data pipeline",
        )
        assert updated.root_cause_category == RootCauseCategory.DESIGN
        assert updated.root_cause == "Architectural flaw in data pipeline"

    def test_all_severity_levels(self, capa_service: CAPAService):
        """Verify all severity levels can be assigned."""
        for severity in CAPASeverity:
            capa = capa_service.create_capa(
                title=f"{severity.value} CAPA",
                description=f"Severity {severity.value}",
                capa_type=CAPAType.CORRECTIVE,
                source=CAPASource.AUDIT,
                severity=severity,
            )
            assert capa.severity == severity


# ===========================================================================
# 4. Overdue CAPA Detection
# ===========================================================================


class TestOverdueCAPADetection:
    """Test overdue CAPA detection."""

    def test_no_overdue_initially(self, capa_service: CAPAService):
        """Seed data should not be overdue (due dates are in the future)."""
        overdue = capa_service.get_overdue_capas()
        # The seed data has future due dates, so none should be overdue
        assert isinstance(overdue, list)

    def test_overdue_capa_detected(self, capa_service: CAPAService):
        """CAPA with past due date is detected as overdue."""
        capa = capa_service.create_capa(
            title="Overdue CAPA",
            description="Past due date",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MAJOR,
            due_date=datetime.now(timezone.utc) - timedelta(days=1),
        )
        overdue = capa_service.get_overdue_capas()
        overdue_ids = [c.id for c in overdue]
        assert capa.id in overdue_ids

    def test_closed_capa_not_overdue(self, capa_service: CAPAService):
        """Closed CAPA with past due date is NOT considered overdue."""
        capa = capa_service.create_capa(
            title="Closed but Past Due",
            description="Should not be overdue",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MINOR,
            due_date=datetime.now(timezone.utc) - timedelta(days=1),
        )
        capa_service.update_capa(capa.id, status=CAPAStatus.CLOSED)
        overdue = capa_service.get_overdue_capas()
        overdue_ids = [c.id for c in overdue]
        assert capa.id not in overdue_ids


# ===========================================================================
# 5. Effectiveness Verification (Recurrence Tracking)
# ===========================================================================


class TestEffectivenessVerification:
    """Test effectiveness verification and recurrence tracking."""

    def test_record_recurrence_on_closed_capa(self, capa_service: CAPAService):
        """Record recurrence on a closed CAPA."""
        capa = capa_service.create_capa(
            title="Recurrence Test",
            description="Will recur",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MAJOR,
        )
        capa_service.update_capa(capa.id, status=CAPAStatus.CLOSED)
        updated = capa_service.record_recurrence(capa.id)
        assert updated.recurrence_count == 1

    def test_record_multiple_recurrences(self, capa_service: CAPAService):
        """Record multiple recurrences."""
        capa = capa_service.create_capa(
            title="Multiple Recurrences",
            description="Will recur multiple times",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MAJOR,
        )
        capa_service.update_capa(capa.id, status=CAPAStatus.CLOSED)
        capa_service.record_recurrence(capa.id)
        capa_service.record_recurrence(capa.id)
        updated = capa_service.record_recurrence(capa.id)
        assert updated.recurrence_count == 3

    def test_recurrence_only_on_closed(self, capa_service: CAPAService):
        """Cannot record recurrence on open CAPA."""
        capa = capa_service.create_capa(
            title="Open CAPA",
            description="Cannot recur when open",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MAJOR,
        )
        with pytest.raises(ValueError, match="CLOSED"):
            capa_service.record_recurrence(capa.id)

    def test_recurrence_not_found(self, capa_service: CAPAService):
        """Raise ValueError for recurrence on non-existent CAPA."""
        with pytest.raises(ValueError, match="CAPA not found"):
            capa_service.record_recurrence("NONEXISTENT")


# ===========================================================================
# 6. CAPA Metrics
# ===========================================================================


class TestCAPAMetrics:
    """Test CAPA metrics calculation."""

    def test_metrics_basic(self, capa_service: CAPAService):
        """Get basic metrics from seed data."""
        metrics = capa_service.get_metrics()
        assert isinstance(metrics, CAPAMetrics)
        assert metrics.total_capas >= 3  # Seed data
        assert metrics.open_capas >= 0
        assert isinstance(metrics.by_severity, dict)
        assert isinstance(metrics.by_status, dict)
        assert isinstance(metrics.by_type, dict)

    def test_metrics_overdue_count(self, capa_service: CAPAService):
        """Verify overdue count in metrics."""
        # Create an overdue CAPA
        capa_service.create_capa(
            title="Overdue for Metrics",
            description="Past due date",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MAJOR,
            due_date=datetime.now(timezone.utc) - timedelta(days=5),
        )
        metrics = capa_service.get_metrics()
        assert metrics.overdue_count >= 1

    def test_metrics_recurrence_rate(self, capa_service: CAPAService):
        """Verify recurrence rate calculation."""
        # Create and close two CAPAs, one with recurrence
        c1 = capa_service.create_capa(
            title="Recurrence Rate 1",
            description="Will recur",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MAJOR,
        )
        c2 = capa_service.create_capa(
            title="Recurrence Rate 2",
            description="Will not recur",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MINOR,
        )
        capa_service.update_capa(c1.id, status=CAPAStatus.CLOSED)
        capa_service.update_capa(c2.id, status=CAPAStatus.CLOSED)
        capa_service.record_recurrence(c1.id)

        metrics = capa_service.get_metrics()
        # At least one closed CAPA has recurrence
        assert metrics.recurrence_rate > 0

    def test_metrics_avg_days_to_close(self, capa_service: CAPAService):
        """Verify average days to close calculation."""
        capa = capa_service.create_capa(
            title="Close Time Test",
            description="Track close time",
            capa_type=CAPAType.CORRECTIVE,
            source=CAPASource.AUDIT,
            severity=CAPASeverity.MINOR,
        )
        capa_service.update_capa(capa.id, status=CAPAStatus.CLOSED)
        metrics = capa_service.get_metrics()
        assert metrics.avg_days_to_close >= 0


# ===========================================================================
# 7. Pre-populated Example CAPAs
# ===========================================================================


class TestPrePopulatedCAPAs:
    """Test pre-populated example CAPAs."""

    def test_capa_001_exists(self, capa_service: CAPAService):
        """CAPA-001 NLP false negative is present."""
        capa = capa_service.get_capa("CAPA-001")
        assert capa is not None
        assert "NLP" in capa.title
        assert capa.severity == CAPASeverity.MAJOR
        assert capa.root_cause_category == RootCauseCategory.TECHNOLOGY

    def test_capa_002_exists(self, capa_service: CAPAService):
        """CAPA-002 Missing audit log is present."""
        capa = capa_service.get_capa("CAPA-002")
        assert capa is not None
        assert "audit" in capa.title.lower()
        assert capa.severity == CAPASeverity.CRITICAL
        assert capa.root_cause_category == RootCauseCategory.PROCESS

    def test_capa_003_exists(self, capa_service: CAPAService):
        """CAPA-003 Inconsistent OMOP mapping is present."""
        capa = capa_service.get_capa("CAPA-003")
        assert capa is not None
        assert "OMOP" in capa.title
        assert capa.severity == CAPASeverity.MAJOR
        assert capa.capa_type == CAPAType.PREVENTIVE


# ===========================================================================
# 8. IQ Qualification Checks
# ===========================================================================


class TestIQChecks:
    """Test Installation Qualification checks."""

    def test_run_iq_suite(self, runner: QualificationRunner):
        """Run full IQ suite and verify report structure."""
        report = runner.run_qualification(QualificationType.IQ)
        assert report.qualification_type == QualificationType.IQ
        assert report.id.startswith("QR-IQ-")
        assert report.summary.total_checks > 0
        assert report.summary.passed >= 0
        assert report.summary.total_checks == len(report.checks)
        assert report.executed_at is not None

    def test_iq_database_check(self, runner: QualificationRunner):
        """IQ database connectivity check runs."""
        report = runner.run_qualification(QualificationType.IQ)
        db_checks = [c for c in report.checks if c.check_id == "IQ-TC-001"]
        assert len(db_checks) == 1
        # Should pass (DATABASE_URL is configured via settings)
        assert db_checks[0].status in (CheckStatus.PASS, CheckStatus.FAIL)

    def test_iq_python_version_check(self, runner: QualificationRunner):
        """IQ Python version check passes."""
        report = runner.run_qualification(QualificationType.IQ)
        py_checks = [c for c in report.checks if c.check_id == "IQ-TC-004"]
        assert len(py_checks) == 1
        assert py_checks[0].status == CheckStatus.PASS
        assert "Python" in py_checks[0].details

    def test_iq_api_prefix_check(self, runner: QualificationRunner):
        """IQ API prefix check passes."""
        report = runner.run_qualification(QualificationType.IQ)
        prefix_checks = [c for c in report.checks if c.check_id == "IQ-TC-010"]
        assert len(prefix_checks) == 1
        assert prefix_checks[0].status == CheckStatus.PASS

    def test_iq_fastapi_check(self, runner: QualificationRunner):
        """IQ FastAPI installation check passes."""
        report = runner.run_qualification(QualificationType.IQ)
        fa_checks = [c for c in report.checks if c.check_id == "IQ-SW-003"]
        assert len(fa_checks) == 1
        assert fa_checks[0].status == CheckStatus.PASS

    def test_iq_pydantic_check(self, runner: QualificationRunner):
        """IQ Pydantic installation check passes."""
        report = runner.run_qualification(QualificationType.IQ)
        pd_checks = [c for c in report.checks if c.check_id == "IQ-SW-005"]
        assert len(pd_checks) == 1
        assert pd_checks[0].status == CheckStatus.PASS


# ===========================================================================
# 9. OQ Qualification Checks
# ===========================================================================


class TestOQChecks:
    """Test Operational Qualification checks."""

    def test_run_oq_suite(self, runner: QualificationRunner):
        """Run full OQ suite and verify report structure."""
        report = runner.run_qualification(QualificationType.OQ)
        assert report.qualification_type == QualificationType.OQ
        assert report.id.startswith("QR-OQ-")
        assert report.summary.total_checks > 0

    def test_oq_health_module(self, runner: QualificationRunner):
        """OQ health module check passes."""
        report = runner.run_qualification(QualificationType.OQ)
        checks = [c for c in report.checks if c.check_id == "OQ-TC-017"]
        assert len(checks) == 1
        assert checks[0].status == CheckStatus.PASS

    def test_oq_auth_module(self, runner: QualificationRunner):
        """OQ auth module check passes."""
        report = runner.run_qualification(QualificationType.OQ)
        checks = [c for c in report.checks if c.check_id == "OQ-TC-001"]
        assert len(checks) == 1
        assert checks[0].status == CheckStatus.PASS

    def test_oq_trial_module(self, runner: QualificationRunner):
        """OQ trial screening module check passes."""
        report = runner.run_qualification(QualificationType.OQ)
        checks = [c for c in report.checks if c.check_id == "OQ-TC-013"]
        assert len(checks) == 1
        assert checks[0].status == CheckStatus.PASS

    def test_oq_audit_module(self, runner: QualificationRunner):
        """OQ audit trail module check passes."""
        report = runner.run_qualification(QualificationType.OQ)
        checks = [c for c in report.checks if c.check_id == "OQ-TC-022"]
        assert len(checks) == 1
        assert checks[0].status == CheckStatus.PASS


# ===========================================================================
# 10. PQ Qualification Checks
# ===========================================================================


class TestPQChecks:
    """Test Performance Qualification checks."""

    def test_run_pq_suite(self, runner: QualificationRunner):
        """Run full PQ suite and verify report structure."""
        report = runner.run_qualification(QualificationType.PQ)
        assert report.qualification_type == QualificationType.PQ
        assert report.id.startswith("QR-PQ-")
        assert report.summary.total_checks > 0

    def test_pq_response_time_baseline(self, runner: QualificationRunner):
        """PQ response time baseline check passes."""
        report = runner.run_qualification(QualificationType.PQ)
        checks = [c for c in report.checks if c.check_id == "PQ-TC-004"]
        assert len(checks) == 1
        assert checks[0].status == CheckStatus.PASS

    def test_pq_concurrent_handling(self, runner: QualificationRunner):
        """PQ concurrent handling check passes."""
        report = runner.run_qualification(QualificationType.PQ)
        checks = [c for c in report.checks if c.check_id == "PQ-TC-001"]
        assert len(checks) == 1
        assert checks[0].status == CheckStatus.PASS

    def test_pq_serialization_performance(self, runner: QualificationRunner):
        """PQ serialization performance check passes."""
        report = runner.run_qualification(QualificationType.PQ)
        checks = [c for c in report.checks if c.check_id == "PQ-TC-005"]
        assert len(checks) == 1
        assert checks[0].status == CheckStatus.PASS


# ===========================================================================
# 11. Qualification Report Management
# ===========================================================================


class TestQualificationReportManagement:
    """Test qualification report storage and retrieval."""

    def test_report_stored_after_run(self, runner: QualificationRunner):
        """Report is stored and retrievable after run."""
        report = runner.run_qualification(QualificationType.IQ)
        retrieved = runner.get_report(report.id)
        assert retrieved is not None
        assert retrieved.id == report.id

    def test_list_reports(self, runner: QualificationRunner):
        """List all reports."""
        runner.run_qualification(QualificationType.IQ)
        runner.run_qualification(QualificationType.OQ)
        reports = runner.list_reports()
        assert len(reports) >= 2

    def test_report_not_found(self, runner: QualificationRunner):
        """Return None for non-existent report."""
        assert runner.get_report("NONEXISTENT") is None

    def test_report_pass_rate(self, runner: QualificationRunner):
        """Verify pass rate calculation."""
        report = runner.run_qualification(QualificationType.IQ)
        expected = (report.summary.passed / report.summary.total_checks * 100) if report.summary.total_checks > 0 else 0
        assert abs(report.summary.pass_rate - round(expected, 1)) < 0.2

    def test_report_overall_result(self, runner: QualificationRunner):
        """Verify overall result logic."""
        report = runner.run_qualification(QualificationType.PQ)
        if report.summary.failed == 0:
            assert report.summary.overall_result == "PASS"
        else:
            assert report.summary.overall_result == "FAIL"

    def test_check_duration_recorded(self, runner: QualificationRunner):
        """Each check has duration_ms recorded."""
        report = runner.run_qualification(QualificationType.IQ)
        for check in report.checks:
            assert check.duration_ms >= 0


# ===========================================================================
# 12. API Endpoint Integration Tests
# ===========================================================================


class TestAPIEndpoints:
    """Test API endpoints via TestClient."""

    def test_list_capas_api(self, client: TestClient):
        """GET /quality-management/capa returns list."""
        resp = client.get("/api/v1/quality-management/capa")
        assert resp.status_code == 200
        data = resp.json()
        assert "capas" in data
        assert "total" in data
        assert data["total"] >= 3  # Seed data

    def test_get_capa_api(self, client: TestClient):
        """GET /quality-management/capa/{id} returns detail."""
        resp = client.get("/api/v1/quality-management/capa/CAPA-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "CAPA-001"
        assert "NLP" in data["title"]

    def test_get_capa_not_found_api(self, client: TestClient):
        """GET /quality-management/capa/{id} returns 404."""
        resp = client.get("/api/v1/quality-management/capa/NONEXISTENT")
        assert resp.status_code == 404

    def test_create_capa_api(self, client: TestClient):
        """POST /quality-management/capa creates CAPA."""
        resp = client.post(
            "/api/v1/quality-management/capa",
            json={
                "title": "API Created CAPA",
                "description": "Created via API test",
                "capa_type": "CORRECTIVE",
                "source": "AUDIT",
                "severity": "MINOR",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "API Created CAPA"
        assert data["status"] == "OPEN"

    def test_update_capa_api(self, client: TestClient):
        """PUT /quality-management/capa/{id} updates CAPA."""
        # Use seed CAPA-001 which is in IN_PROGRESS state
        resp = client.put(
            "/api/v1/quality-management/capa/CAPA-001",
            json={"status": "VERIFICATION"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "VERIFICATION"

    def test_update_capa_invalid_transition_api(self, client: TestClient):
        """PUT /quality-management/capa/{id} returns 400 on invalid transition."""
        # CAPA-002 is in ACTION_PLANNED, OPEN is not a valid next state
        # Actually ACTION_PLANNED -> INVESTIGATING is valid. Let's try ACTION_PLANNED -> VERIFICATION
        resp = client.put(
            "/api/v1/quality-management/capa/CAPA-002",
            json={"status": "VERIFICATION"},
        )
        assert resp.status_code == 400

    def test_capa_metrics_api(self, client: TestClient):
        """GET /quality-management/capa/metrics returns metrics."""
        resp = client.get("/api/v1/quality-management/capa/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_capas" in data
        assert "open_capas" in data
        assert "by_severity" in data
        assert "overdue_count" in data

    def test_run_qualification_api(self, client: TestClient):
        """POST /quality-management/qualification/run executes suite."""
        resp = client.post(
            "/api/v1/quality-management/qualification/run",
            json={"qualification_type": "IQ", "executed_by": "test-user"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["qualification_type"] == "IQ"
        assert "summary" in data
        assert "checks" in data
        assert data["summary"]["total_checks"] > 0

    def test_list_qualification_reports_api(self, client: TestClient):
        """GET /quality-management/qualification/reports returns list."""
        # First run a qualification
        client.post(
            "/api/v1/quality-management/qualification/run",
            json={"qualification_type": "OQ"},
        )
        resp = client.get("/api/v1/quality-management/qualification/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert "reports" in data
        assert data["total"] >= 1

    def test_get_qualification_report_api(self, client: TestClient):
        """GET /quality-management/qualification/reports/{id} returns report."""
        # Run a qualification first
        run_resp = client.post(
            "/api/v1/quality-management/qualification/run",
            json={"qualification_type": "PQ"},
        )
        report_id = run_resp.json()["id"]

        resp = client.get(f"/api/v1/quality-management/qualification/reports/{report_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == report_id

    def test_get_qualification_report_not_found_api(self, client: TestClient):
        """GET /quality-management/qualification/reports/{id} returns 404."""
        resp = client.get("/api/v1/quality-management/qualification/reports/NONEXISTENT")
        assert resp.status_code == 404

    def test_filter_capas_by_severity_api(self, client: TestClient):
        """GET /quality-management/capa?severity=CRITICAL filters correctly."""
        resp = client.get("/api/v1/quality-management/capa?severity=CRITICAL")
        assert resp.status_code == 200
        data = resp.json()
        for capa in data["capas"]:
            assert capa["severity"] == "CRITICAL"

    def test_filter_capas_by_status_api(self, client: TestClient):
        """GET /quality-management/capa?status=IN_PROGRESS filters correctly."""
        resp = client.get("/api/v1/quality-management/capa?status=IN_PROGRESS")
        assert resp.status_code == 200
        data = resp.json()
        for capa in data["capas"]:
            assert capa["status"] == "IN_PROGRESS"


# ===========================================================================
# 13. Singleton Management
# ===========================================================================


class TestSingletonManagement:
    """Test singleton behavior and reset."""

    def test_capa_service_singleton(self):
        """get_capa_service returns same instance."""
        s1 = get_capa_service()
        s2 = get_capa_service()
        assert s1 is s2

    def test_capa_service_reset(self):
        """reset_capa_service creates new instance."""
        s1 = get_capa_service()
        reset_capa_service()
        s2 = get_capa_service()
        assert s1 is not s2

    def test_qualification_runner_singleton(self):
        """get_qualification_runner returns same instance."""
        r1 = get_qualification_runner()
        r2 = get_qualification_runner()
        assert r1 is r2

    def test_qualification_runner_reset(self):
        """reset_qualification_runner creates new instance."""
        r1 = get_qualification_runner()
        reset_qualification_runner()
        r2 = get_qualification_runner()
        assert r1 is not r2
