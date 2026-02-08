"""Tests for Disaster Recovery Runbooks & RTO/RPO Management (VPE-7).

Covers:
- Seed data verification (10 runbooks, 4 test results)
- Runbook CRUD (create, read, update, delete, list with filters)
- Test recording with auto-update of runbook state
- RTO/RPO compliance tracking (met and unmet scenarios)
- Tier-based overdue test detection (90/180/365 day thresholds)
- Runbook validation (completeness checks)
- Communication plan retrieval
- DR program metrics calculation
- API endpoint integration tests (12+ endpoints)
- Error handling (404 for unknown IDs)
- Edge cases (empty filters, all filters combined, version bumps)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.disaster_recovery import (
    CommunicationPlanResponse,
    DisasterCategory,
    DisasterRecoveryRunbook,
    DRMetrics,
    DRTestResult,
    RecordTestRequest,
    RecoveryTier,
    RunbookCreateRequest,
    RunbookListResponse,
    RunbookStatus,
    RunbookStep,
    RunbookUpdateRequest,
    RunbookValidation,
    TestHistoryResponse,
    TestResult,
)
from app.services.disaster_recovery_service import (
    OVERDUE_THRESHOLDS,
    DisasterRecoveryService,
    get_disaster_recovery_service,
    reset_disaster_recovery_service,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1/disaster-recovery"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton between tests."""
    reset_disaster_recovery_service()
    yield
    reset_disaster_recovery_service()


@pytest.fixture
def svc() -> DisasterRecoveryService:
    """Fresh service instance via singleton."""
    return get_disaster_recovery_service()


def _make_step(**overrides) -> RunbookStep:
    """Helper to build a RunbookStep with defaults."""
    defaults = dict(
        step_number=1,
        title="Test step",
        description="Test step description",
        responsible_role="SRE On-Call",
        estimated_minutes=5,
        verification_criteria="Step completed successfully",
        rollback_instructions="Rollback step",
    )
    defaults.update(overrides)
    return RunbookStep(**defaults)


def _make_create(**overrides) -> RunbookCreateRequest:
    """Helper to build a RunbookCreateRequest with defaults."""
    defaults = dict(
        title="Test Runbook",
        category=DisasterCategory.DATABASE_FAILURE,
        tier=RecoveryTier.TIER_2_HIGH,
        rto_minutes=60,
        rpo_minutes=15,
        steps=[_make_step(step_number=1), _make_step(step_number=2, title="Step 2")],
        prerequisites=["Prereq 1"],
        communication_plan=["Notify team"],
        escalation_contacts=[{"name": "Test Lead", "role": "Lead", "phone": "+1-555-0000", "email": "lead@test.com"}],
    )
    defaults.update(overrides)
    return RunbookCreateRequest(**defaults)


def _make_test_request(**overrides) -> RecordTestRequest:
    """Helper to build a RecordTestRequest with defaults."""
    defaults = dict(
        tester="Test Engineer",
        actual_rto_minutes=45.0,
        actual_rpo_minutes=10.0,
        result=TestResult.PASS,
        issues_found=[],
        lessons_learned=[],
        steps_completed=5,
        total_steps=5,
    )
    defaults.update(overrides)
    return RecordTestRequest(**defaults)


# ===========================================================================
# 1. Seed Data Verification
# ===========================================================================


class TestSeedData:
    """Verify pre-populated seed data."""

    def test_seed_runbook_count(self, svc: DisasterRecoveryService):
        runbooks = svc.list_runbooks()
        assert len(runbooks) == 10

    def test_seed_runbook_ids(self, svc: DisasterRecoveryService):
        runbooks = svc.list_runbooks()
        ids = {rb.id for rb in runbooks}
        expected = {f"DR-{i:03d}" for i in range(1, 11)}
        assert ids == expected

    def test_seed_postgresql_failover(self, svc: DisasterRecoveryService):
        rb = svc.get_runbook("DR-001")
        assert rb is not None
        assert rb.title == "PostgreSQL Primary Failover"
        assert rb.category == DisasterCategory.DATABASE_FAILURE
        assert rb.tier == RecoveryTier.TIER_1_CRITICAL
        assert rb.rto_minutes == 30
        assert rb.rpo_minutes == 5
        assert len(rb.steps) == 8
        assert rb.status == RunbookStatus.TESTED
        assert rb.version == 3

    def test_seed_redis_recovery(self, svc: DisasterRecoveryService):
        rb = svc.get_runbook("DR-002")
        assert rb is not None
        assert rb.tier == RecoveryTier.TIER_2_HIGH
        assert rb.rto_minutes == 60
        assert len(rb.steps) == 6

    def test_seed_app_rollback(self, svc: DisasterRecoveryService):
        rb = svc.get_runbook("DR-003")
        assert rb is not None
        assert rb.rto_minutes == 15
        assert rb.rpo_minutes == 0
        assert len(rb.steps) == 5

    def test_seed_cloud_region_failover(self, svc: DisasterRecoveryService):
        rb = svc.get_runbook("DR-004")
        assert rb is not None
        assert rb.category == DisasterCategory.CLOUD_REGION_FAILURE
        assert len(rb.steps) == 10

    def test_seed_ransomware(self, svc: DisasterRecoveryService):
        rb = svc.get_runbook("DR-005")
        assert rb is not None
        assert rb.category == DisasterCategory.RANSOMWARE
        assert rb.tier == RecoveryTier.TIER_1_CRITICAL
        assert len(rb.steps) == 12

    def test_seed_data_corruption(self, svc: DisasterRecoveryService):
        rb = svc.get_runbook("DR-006")
        assert rb is not None
        assert rb.category == DisasterCategory.DATA_CORRUPTION
        assert len(rb.steps) == 9

    def test_seed_dns_failure(self, svc: DisasterRecoveryService):
        rb = svc.get_runbook("DR-007")
        assert rb is not None
        assert rb.category == DisasterCategory.DNS_FAILURE
        assert rb.tier == RecoveryTier.TIER_3_MEDIUM
        assert len(rb.steps) == 4

    def test_seed_certificate_rotation(self, svc: DisasterRecoveryService):
        rb = svc.get_runbook("DR-008")
        assert rb is not None
        assert rb.category == DisasterCategory.CERTIFICATE_EXPIRY
        assert len(rb.steps) == 6

    def test_seed_third_party_outage(self, svc: DisasterRecoveryService):
        rb = svc.get_runbook("DR-009")
        assert rb is not None
        assert rb.category == DisasterCategory.THIRD_PARTY_OUTAGE
        assert rb.rto_minutes == 240
        assert len(rb.steps) == 5

    def test_seed_key_compromise(self, svc: DisasterRecoveryService):
        rb = svc.get_runbook("DR-010")
        assert rb is not None
        assert rb.category == DisasterCategory.KEY_COMPROMISE
        assert rb.tier == RecoveryTier.TIER_1_CRITICAL
        assert rb.rto_minutes == 45
        assert len(rb.steps) == 8

    def test_seed_test_results_exist(self, svc: DisasterRecoveryService):
        history = svc.get_test_history("DR-001")
        assert history is not None
        assert history.total >= 1

    def test_seed_test_results_for_app_rollback(self, svc: DisasterRecoveryService):
        history = svc.get_test_history("DR-003")
        assert history is not None
        assert history.total >= 1

    def test_seed_test_results_count(self, svc: DisasterRecoveryService):
        """At least 4 seed test results across all runbooks."""
        total = 0
        for rb in svc.list_runbooks():
            h = svc.get_test_history(rb.id)
            if h:
                total += h.total
        assert total >= 4


# ===========================================================================
# 2. Runbook CRUD - Create
# ===========================================================================


class TestRunbookCreate:
    """Tests for create_runbook."""

    def test_create_basic(self, svc: DisasterRecoveryService):
        req = _make_create()
        rb = svc.create_runbook(req)
        assert rb.id.startswith("DR-")
        assert rb.title == "Test Runbook"
        assert rb.category == DisasterCategory.DATABASE_FAILURE
        assert rb.tier == RecoveryTier.TIER_2_HIGH
        assert rb.status == RunbookStatus.DRAFT
        assert rb.version == 1
        assert rb.created_at is not None
        assert rb.updated_at is not None

    def test_create_sets_rto_rpo(self, svc: DisasterRecoveryService):
        rb = svc.create_runbook(_make_create(rto_minutes=120, rpo_minutes=30))
        assert rb.rto_minutes == 120
        assert rb.rpo_minutes == 30

    def test_create_includes_steps(self, svc: DisasterRecoveryService):
        rb = svc.create_runbook(_make_create())
        assert len(rb.steps) == 2
        assert rb.steps[0].title == "Test step"
        assert rb.steps[1].title == "Step 2"

    def test_create_includes_prerequisites(self, svc: DisasterRecoveryService):
        rb = svc.create_runbook(_make_create(prerequisites=["P1", "P2"]))
        assert rb.prerequisites == ["P1", "P2"]

    def test_create_includes_contacts(self, svc: DisasterRecoveryService):
        contacts = [{"name": "Alice", "role": "DBA", "phone": "555", "email": "a@b.com"}]
        rb = svc.create_runbook(_make_create(escalation_contacts=contacts))
        assert len(rb.escalation_contacts) == 1
        assert rb.escalation_contacts[0]["name"] == "Alice"

    def test_create_increments_total(self, svc: DisasterRecoveryService):
        initial = len(svc.list_runbooks())
        svc.create_runbook(_make_create(title="New 1"))
        svc.create_runbook(_make_create(title="New 2"))
        assert len(svc.list_runbooks()) == initial + 2

    def test_create_with_no_steps(self, svc: DisasterRecoveryService):
        rb = svc.create_runbook(_make_create(steps=[]))
        assert len(rb.steps) == 0

    def test_create_with_approved_by(self, svc: DisasterRecoveryService):
        rb = svc.create_runbook(_make_create(approved_by="VP Eng"))
        assert rb.approved_by == "VP Eng"


# ===========================================================================
# 3. Runbook CRUD - Read / Get
# ===========================================================================


class TestRunbookRead:
    """Tests for get_runbook and list_runbooks."""

    def test_get_existing(self, svc: DisasterRecoveryService):
        rb = svc.get_runbook("DR-001")
        assert rb is not None
        assert rb.id == "DR-001"

    def test_get_nonexistent(self, svc: DisasterRecoveryService):
        rb = svc.get_runbook("DR-NONEXISTENT")
        assert rb is None

    def test_list_all(self, svc: DisasterRecoveryService):
        all_rb = svc.list_runbooks()
        assert len(all_rb) == 10

    def test_list_filter_category(self, svc: DisasterRecoveryService):
        result = svc.list_runbooks(category=DisasterCategory.DATABASE_FAILURE)
        assert len(result) == 2  # DR-001 (PostgreSQL) and DR-002 (Redis)
        for rb in result:
            assert rb.category == DisasterCategory.DATABASE_FAILURE

    def test_list_filter_tier(self, svc: DisasterRecoveryService):
        result = svc.list_runbooks(tier=RecoveryTier.TIER_1_CRITICAL)
        assert len(result) >= 3  # DR-001, DR-003, DR-005, DR-010
        for rb in result:
            assert rb.tier == RecoveryTier.TIER_1_CRITICAL

    def test_list_filter_status(self, svc: DisasterRecoveryService):
        result = svc.list_runbooks(status=RunbookStatus.TESTED)
        assert len(result) >= 2  # DR-001, DR-003, DR-006
        for rb in result:
            assert rb.status == RunbookStatus.TESTED

    def test_list_filter_combined(self, svc: DisasterRecoveryService):
        result = svc.list_runbooks(
            category=DisasterCategory.DATABASE_FAILURE,
            tier=RecoveryTier.TIER_1_CRITICAL,
        )
        assert len(result) == 1
        assert result[0].id == "DR-001"

    def test_list_filter_no_match(self, svc: DisasterRecoveryService):
        result = svc.list_runbooks(category=DisasterCategory.NETWORK_PARTITION)
        assert len(result) == 0


# ===========================================================================
# 4. Runbook CRUD - Update
# ===========================================================================


class TestRunbookUpdate:
    """Tests for update_runbook."""

    def test_update_title(self, svc: DisasterRecoveryService):
        req = RunbookUpdateRequest(title="Updated Title")
        updated = svc.update_runbook("DR-001", req)
        assert updated is not None
        assert updated.title == "Updated Title"

    def test_update_bumps_version(self, svc: DisasterRecoveryService):
        original = svc.get_runbook("DR-001")
        assert original is not None
        original_version = original.version
        req = RunbookUpdateRequest(title="V bump")
        updated = svc.update_runbook("DR-001", req)
        assert updated is not None
        assert updated.version == original_version + 1

    def test_update_status(self, svc: DisasterRecoveryService):
        req = RunbookUpdateRequest(status=RunbookStatus.OUTDATED)
        updated = svc.update_runbook("DR-001", req)
        assert updated is not None
        assert updated.status == RunbookStatus.OUTDATED

    def test_update_rto_rpo(self, svc: DisasterRecoveryService):
        req = RunbookUpdateRequest(rto_minutes=45, rpo_minutes=10)
        updated = svc.update_runbook("DR-001", req)
        assert updated is not None
        assert updated.rto_minutes == 45
        assert updated.rpo_minutes == 10

    def test_update_steps(self, svc: DisasterRecoveryService):
        new_steps = [_make_step(step_number=1, title="Only Step")]
        req = RunbookUpdateRequest(steps=new_steps)
        updated = svc.update_runbook("DR-001", req)
        assert updated is not None
        assert len(updated.steps) == 1
        assert updated.steps[0].title == "Only Step"

    def test_update_nonexistent(self, svc: DisasterRecoveryService):
        req = RunbookUpdateRequest(title="Ghost")
        result = svc.update_runbook("DR-GHOST", req)
        assert result is None

    def test_update_updates_timestamp(self, svc: DisasterRecoveryService):
        original = svc.get_runbook("DR-001")
        assert original is not None
        req = RunbookUpdateRequest(title="Time Test")
        updated = svc.update_runbook("DR-001", req)
        assert updated is not None
        assert updated.updated_at >= original.updated_at

    def test_update_communication_plan(self, svc: DisasterRecoveryService):
        req = RunbookUpdateRequest(communication_plan=["New comm plan step"])
        updated = svc.update_runbook("DR-001", req)
        assert updated is not None
        assert updated.communication_plan == ["New comm plan step"]

    def test_update_escalation_contacts(self, svc: DisasterRecoveryService):
        contacts = [{"name": "New Contact", "role": "Tester"}]
        req = RunbookUpdateRequest(escalation_contacts=contacts)
        updated = svc.update_runbook("DR-001", req)
        assert updated is not None
        assert len(updated.escalation_contacts) == 1
        assert updated.escalation_contacts[0]["name"] == "New Contact"


# ===========================================================================
# 5. Runbook CRUD - Delete
# ===========================================================================


class TestRunbookDelete:
    """Tests for delete_runbook."""

    def test_delete_existing(self, svc: DisasterRecoveryService):
        initial = len(svc.list_runbooks())
        deleted = svc.delete_runbook("DR-001")
        assert deleted is True
        assert len(svc.list_runbooks()) == initial - 1
        assert svc.get_runbook("DR-001") is None

    def test_delete_nonexistent(self, svc: DisasterRecoveryService):
        deleted = svc.delete_runbook("DR-NONEXISTENT")
        assert deleted is False

    def test_delete_removes_test_history(self, svc: DisasterRecoveryService):
        # Verify test history exists
        history = svc.get_test_history("DR-001")
        assert history is not None
        assert history.total >= 1
        # Delete and verify history is gone
        svc.delete_runbook("DR-001")
        result = svc.get_test_history("DR-001")
        assert result is None


# ===========================================================================
# 6. Test Recording
# ===========================================================================


class TestRecordTest:
    """Tests for record_test."""

    def test_record_basic(self, svc: DisasterRecoveryService):
        req = _make_test_request(actual_rto_minutes=20.0, actual_rpo_minutes=3.0)
        result = svc.record_test("DR-001", req)
        assert result is not None
        assert result.id.startswith("DRT-")
        assert result.runbook_id == "DR-001"
        assert result.tester == "Test Engineer"
        assert result.result == TestResult.PASS

    def test_record_rto_met_when_under_target(self, svc: DisasterRecoveryService):
        req = _make_test_request(actual_rto_minutes=25.0)
        result = svc.record_test("DR-001", req)
        assert result is not None
        assert result.rto_met is True  # Target is 30

    def test_record_rto_not_met_when_over_target(self, svc: DisasterRecoveryService):
        req = _make_test_request(actual_rto_minutes=35.0)
        result = svc.record_test("DR-001", req)
        assert result is not None
        assert result.rto_met is False  # Target is 30

    def test_record_rpo_met_when_under_target(self, svc: DisasterRecoveryService):
        req = _make_test_request(actual_rpo_minutes=3.0)
        result = svc.record_test("DR-001", req)
        assert result is not None
        assert result.rpo_met is True  # Target is 5

    def test_record_rpo_not_met_when_over_target(self, svc: DisasterRecoveryService):
        req = _make_test_request(actual_rpo_minutes=10.0)
        result = svc.record_test("DR-001", req)
        assert result is not None
        assert result.rpo_met is False  # Target is 5

    def test_record_rto_met_at_exact_target(self, svc: DisasterRecoveryService):
        req = _make_test_request(actual_rto_minutes=30.0)
        result = svc.record_test("DR-001", req)
        assert result is not None
        assert result.rto_met is True  # Exactly at target

    def test_record_updates_runbook_last_tested(self, svc: DisasterRecoveryService):
        before = svc.get_runbook("DR-002")
        assert before is not None
        old_tested = before.last_tested

        req = _make_test_request()
        svc.record_test("DR-002", req)

        after = svc.get_runbook("DR-002")
        assert after is not None
        assert after.last_tested is not None
        if old_tested is not None:
            assert after.last_tested > old_tested

    def test_record_updates_runbook_test_result(self, svc: DisasterRecoveryService):
        req = _make_test_request(result=TestResult.FAIL)
        svc.record_test("DR-002", req)
        rb = svc.get_runbook("DR-002")
        assert rb is not None
        assert rb.test_result == TestResult.FAIL

    def test_record_updates_runbook_status_to_tested(self, svc: DisasterRecoveryService):
        req = _make_test_request()
        svc.record_test("DR-002", req)
        rb = svc.get_runbook("DR-002")
        assert rb is not None
        assert rb.status == RunbookStatus.TESTED

    def test_record_sets_next_test_due(self, svc: DisasterRecoveryService):
        req = _make_test_request()
        svc.record_test("DR-001", req)
        rb = svc.get_runbook("DR-001")
        assert rb is not None
        assert rb.next_test_due is not None
        # TIER_1_CRITICAL => 90 days
        expected_days = OVERDUE_THRESHOLDS[RecoveryTier.TIER_1_CRITICAL]
        delta = (rb.next_test_due - datetime.now(timezone.utc)).days
        assert abs(delta - expected_days) <= 1

    def test_record_nonexistent_runbook(self, svc: DisasterRecoveryService):
        req = _make_test_request()
        result = svc.record_test("DR-NONEXISTENT", req)
        assert result is None

    def test_record_appends_to_history(self, svc: DisasterRecoveryService):
        initial_history = svc.get_test_history("DR-001")
        assert initial_history is not None
        initial_count = initial_history.total

        req = _make_test_request()
        svc.record_test("DR-001", req)

        updated_history = svc.get_test_history("DR-001")
        assert updated_history is not None
        assert updated_history.total == initial_count + 1

    def test_record_with_issues_and_lessons(self, svc: DisasterRecoveryService):
        req = _make_test_request(
            issues_found=["Issue 1", "Issue 2"],
            lessons_learned=["Lesson 1"],
        )
        result = svc.record_test("DR-001", req)
        assert result is not None
        assert len(result.issues_found) == 2
        assert len(result.lessons_learned) == 1

    def test_record_partial_result(self, svc: DisasterRecoveryService):
        req = _make_test_request(result=TestResult.PARTIAL, steps_completed=3, total_steps=5)
        result = svc.record_test("DR-001", req)
        assert result is not None
        assert result.result == TestResult.PARTIAL
        assert result.steps_completed == 3

    def test_record_preserves_outdated_status(self, svc: DisasterRecoveryService):
        """Recording a test on an OUTDATED runbook keeps it OUTDATED."""
        svc.update_runbook("DR-001", RunbookUpdateRequest(status=RunbookStatus.OUTDATED))
        req = _make_test_request()
        svc.record_test("DR-001", req)
        rb = svc.get_runbook("DR-001")
        assert rb is not None
        assert rb.status == RunbookStatus.OUTDATED


# ===========================================================================
# 7. Test History
# ===========================================================================


class TestTestHistory:
    """Tests for get_test_history."""

    def test_get_history_with_results(self, svc: DisasterRecoveryService):
        history = svc.get_test_history("DR-001")
        assert history is not None
        assert history.runbook_id == "DR-001"
        assert history.total >= 1
        assert len(history.tests) == history.total

    def test_get_history_no_results(self, svc: DisasterRecoveryService):
        # DR-005 (ransomware) has never been tested
        history = svc.get_test_history("DR-005")
        assert history is not None
        assert history.total == 0

    def test_get_history_nonexistent(self, svc: DisasterRecoveryService):
        history = svc.get_test_history("DR-GHOST")
        assert history is None

    def test_history_test_fields(self, svc: DisasterRecoveryService):
        history = svc.get_test_history("DR-001")
        assert history is not None
        assert history.total >= 1
        test = history.tests[0]
        assert test.id.startswith("DRT-")
        assert test.runbook_id == "DR-001"
        assert test.tester is not None
        assert test.actual_rto_minutes > 0
        assert isinstance(test.rto_met, bool)
        assert isinstance(test.rpo_met, bool)


# ===========================================================================
# 8. Metrics
# ===========================================================================


class TestMetrics:
    """Tests for get_metrics."""

    def test_metrics_total(self, svc: DisasterRecoveryService):
        m = svc.get_metrics()
        assert m.total_runbooks == 10

    def test_metrics_by_category(self, svc: DisasterRecoveryService):
        m = svc.get_metrics()
        assert DisasterCategory.DATABASE_FAILURE.value in m.by_category
        assert m.by_category[DisasterCategory.DATABASE_FAILURE.value] == 2

    def test_metrics_by_tier(self, svc: DisasterRecoveryService):
        m = svc.get_metrics()
        assert RecoveryTier.TIER_1_CRITICAL.value in m.by_tier
        assert m.by_tier[RecoveryTier.TIER_1_CRITICAL.value] >= 3

    def test_metrics_by_status(self, svc: DisasterRecoveryService):
        m = svc.get_metrics()
        assert RunbookStatus.TESTED.value in m.by_status
        assert RunbookStatus.APPROVED.value in m.by_status

    def test_metrics_tested_percentage(self, svc: DisasterRecoveryService):
        m = svc.get_metrics()
        # 8 out of 10 have last_tested set (DR-005 and DR-008 are None)
        assert m.tested_percentage == 80.0

    def test_metrics_rto_compliance(self, svc: DisasterRecoveryService):
        m = svc.get_metrics()
        # 3 out of 4 seed tests met RTO
        assert m.rto_compliance_rate == 75.0

    def test_metrics_rpo_compliance(self, svc: DisasterRecoveryService):
        m = svc.get_metrics()
        # 3 out of 4 seed tests met RPO
        assert m.rpo_compliance_rate == 75.0

    def test_metrics_mean_rto(self, svc: DisasterRecoveryService):
        m = svc.get_metrics()
        # Mean of 25, 12, 160, 150
        expected = (25.0 + 12.0 + 160.0 + 150.0) / 4
        assert abs(m.mean_actual_rto - expected) < 0.2

    def test_metrics_mean_rpo(self, svc: DisasterRecoveryService):
        m = svc.get_metrics()
        expected = (3.0 + 0.0 + 45.0 + 40.0) / 4
        assert abs(m.mean_actual_rpo - expected) < 0.2

    def test_metrics_overdue_count(self, svc: DisasterRecoveryService):
        m = svc.get_metrics()
        # Should have at least some overdue (DR-005 never tested, DR-007 >365 days, DR-004 >180)
        assert m.overdue_tests_count >= 2

    def test_metrics_last_full_dr_test(self, svc: DisasterRecoveryService):
        m = svc.get_metrics()
        assert m.last_full_dr_test is not None

    def test_metrics_after_new_test(self, svc: DisasterRecoveryService):
        initial = svc.get_metrics()
        # Record a new test that fails RTO
        req = _make_test_request(actual_rto_minutes=100.0, actual_rpo_minutes=50.0, result=TestResult.FAIL)
        svc.record_test("DR-002", req)
        updated = svc.get_metrics()
        # Now 5 tests total, so compliance should change
        assert updated.rto_compliance_rate != initial.rto_compliance_rate


# ===========================================================================
# 9. Overdue Tests
# ===========================================================================


class TestOverdueTests:
    """Tests for get_overdue_tests."""

    def test_overdue_includes_never_tested(self, svc: DisasterRecoveryService):
        overdue = svc.get_overdue_tests()
        ids = {rb.id for rb in overdue}
        # DR-005 (ransomware) and DR-008 (cert rotation) never tested
        assert "DR-005" in ids
        assert "DR-008" in ids

    def test_overdue_includes_stale_tests(self, svc: DisasterRecoveryService):
        overdue = svc.get_overdue_tests()
        ids = {rb.id for rb in overdue}
        # DR-007 (DNS) last tested 400 days ago, threshold 365
        assert "DR-007" in ids

    def test_overdue_excludes_recently_tested(self, svc: DisasterRecoveryService):
        overdue = svc.get_overdue_tests()
        ids = {rb.id for rb in overdue}
        # DR-001 (PostgreSQL) tested 45 days ago, threshold 90
        assert "DR-001" not in ids
        # DR-003 (App rollback) tested 30 days ago, threshold 90
        assert "DR-003" not in ids

    def test_overdue_threshold_tier1(self, svc: DisasterRecoveryService):
        assert OVERDUE_THRESHOLDS[RecoveryTier.TIER_1_CRITICAL] == 90

    def test_overdue_threshold_tier2(self, svc: DisasterRecoveryService):
        assert OVERDUE_THRESHOLDS[RecoveryTier.TIER_2_HIGH] == 180

    def test_overdue_threshold_tier3(self, svc: DisasterRecoveryService):
        assert OVERDUE_THRESHOLDS[RecoveryTier.TIER_3_MEDIUM] == 365

    def test_overdue_threshold_tier4(self, svc: DisasterRecoveryService):
        assert OVERDUE_THRESHOLDS[RecoveryTier.TIER_4_LOW] == 365

    def test_overdue_after_fresh_test(self, svc: DisasterRecoveryService):
        """Recording a test removes runbook from overdue list."""
        overdue_before = {rb.id for rb in svc.get_overdue_tests()}
        assert "DR-005" in overdue_before

        req = _make_test_request()
        svc.record_test("DR-005", req)

        overdue_after = {rb.id for rb in svc.get_overdue_tests()}
        assert "DR-005" not in overdue_after


# ===========================================================================
# 10. Validation
# ===========================================================================


class TestValidation:
    """Tests for validate_runbook."""

    def test_valid_seed_runbook(self, svc: DisasterRecoveryService):
        validation = svc.validate_runbook("DR-001")
        assert validation is not None
        assert validation.is_valid is True
        assert len(validation.issues) == 0

    def test_validate_nonexistent(self, svc: DisasterRecoveryService):
        validation = svc.validate_runbook("DR-GHOST")
        assert validation is None

    def test_validate_no_steps(self, svc: DisasterRecoveryService):
        rb = svc.create_runbook(_make_create(steps=[]))
        validation = svc.validate_runbook(rb.id)
        assert validation is not None
        assert validation.is_valid is False
        assert any("no recovery steps" in i.lower() for i in validation.issues)

    def test_validate_missing_verification(self, svc: DisasterRecoveryService):
        bad_step = RunbookStep(
            step_number=1,
            title="Bad step",
            description="No verification",
            responsible_role="SRE",
            estimated_minutes=5,
            verification_criteria="",
            rollback_instructions="N/A",
        )
        rb = svc.create_runbook(_make_create(steps=[bad_step]))
        validation = svc.validate_runbook(rb.id)
        assert validation is not None
        assert validation.is_valid is False
        assert any("verification criteria" in i.lower() for i in validation.issues)

    def test_validate_missing_responsible_role(self, svc: DisasterRecoveryService):
        bad_step = RunbookStep(
            step_number=1,
            title="Bad step",
            description="No role",
            responsible_role="",
            estimated_minutes=5,
            verification_criteria="Check it",
            rollback_instructions="N/A",
        )
        rb = svc.create_runbook(_make_create(steps=[bad_step]))
        validation = svc.validate_runbook(rb.id)
        assert validation is not None
        assert validation.is_valid is False
        assert any("responsible role" in i.lower() for i in validation.issues)

    def test_validate_no_contacts(self, svc: DisasterRecoveryService):
        rb = svc.create_runbook(_make_create(escalation_contacts=[]))
        validation = svc.validate_runbook(rb.id)
        assert validation is not None
        assert validation.is_valid is False
        assert any("escalation contacts" in i.lower() for i in validation.issues)

    def test_validate_no_communication_plan(self, svc: DisasterRecoveryService):
        rb = svc.create_runbook(_make_create(communication_plan=[]))
        validation = svc.validate_runbook(rb.id)
        assert validation is not None
        assert validation.is_valid is False
        assert any("communication plan" in i.lower() for i in validation.issues)

    def test_validate_no_prerequisites(self, svc: DisasterRecoveryService):
        rb = svc.create_runbook(_make_create(prerequisites=[]))
        validation = svc.validate_runbook(rb.id)
        assert validation is not None
        assert validation.is_valid is False
        assert any("prerequisites" in i.lower() for i in validation.issues)

    def test_validate_has_checked_at(self, svc: DisasterRecoveryService):
        validation = svc.validate_runbook("DR-001")
        assert validation is not None
        assert validation.checked_at is not None


# ===========================================================================
# 11. Communication Plan
# ===========================================================================


class TestCommunicationPlan:
    """Tests for get_communication_plan."""

    def test_get_plan(self, svc: DisasterRecoveryService):
        plan = svc.get_communication_plan("DR-001")
        assert plan is not None
        assert plan.runbook_id == "DR-001"
        assert plan.runbook_title == "PostgreSQL Primary Failover"
        assert plan.category == DisasterCategory.DATABASE_FAILURE
        assert plan.tier == RecoveryTier.TIER_1_CRITICAL
        assert len(plan.communication_plan) >= 3
        assert len(plan.escalation_contacts) >= 2

    def test_get_plan_nonexistent(self, svc: DisasterRecoveryService):
        plan = svc.get_communication_plan("DR-GHOST")
        assert plan is None

    def test_plan_contacts_have_required_fields(self, svc: DisasterRecoveryService):
        plan = svc.get_communication_plan("DR-001")
        assert plan is not None
        for contact in plan.escalation_contacts:
            assert "name" in contact
            assert "role" in contact


# ===========================================================================
# 12. Clear / Reset
# ===========================================================================


class TestClear:
    """Tests for clear/reset functionality."""

    def test_clear_resets_to_seed(self, svc: DisasterRecoveryService):
        # Delete a runbook and add custom one
        svc.delete_runbook("DR-001")
        svc.create_runbook(_make_create(title="Custom"))
        assert len(svc.list_runbooks()) == 10  # 10-1+1 = 10 but different set

        # Clear resets
        svc.clear()
        runbooks = svc.list_runbooks()
        assert len(runbooks) == 10
        ids = {rb.id for rb in runbooks}
        assert "DR-001" in ids  # Restored

    def test_reset_singleton(self):
        svc1 = get_disaster_recovery_service()
        svc1.create_runbook(_make_create(title="Before Reset"))
        count1 = len(svc1.list_runbooks())

        reset_disaster_recovery_service()
        svc2 = get_disaster_recovery_service()
        count2 = len(svc2.list_runbooks())

        assert count2 == 10  # Back to seed data
        assert count1 == 11  # Was 10+1


# ===========================================================================
# 13. Schema / Enum Tests
# ===========================================================================


class TestSchemas:
    """Tests for schema models and enums."""

    def test_disaster_category_values(self):
        assert len(DisasterCategory) == 10
        assert DisasterCategory.DATABASE_FAILURE.value == "DATABASE_FAILURE"
        assert DisasterCategory.RANSOMWARE.value == "RANSOMWARE"

    def test_runbook_status_values(self):
        assert len(RunbookStatus) == 5
        assert RunbookStatus.DRAFT.value == "DRAFT"
        assert RunbookStatus.OUTDATED.value == "OUTDATED"

    def test_recovery_tier_values(self):
        assert len(RecoveryTier) == 4
        assert RecoveryTier.TIER_1_CRITICAL.value == "TIER_1_CRITICAL"
        assert RecoveryTier.TIER_4_LOW.value == "TIER_4_LOW"

    def test_test_result_values(self):
        assert len(TestResult) == 3
        assert TestResult.PASS.value == "PASS"
        assert TestResult.FAIL.value == "FAIL"
        assert TestResult.PARTIAL.value == "PARTIAL"

    def test_runbook_step_model(self):
        step = _make_step(commands=["echo hello"])
        assert step.step_number == 1
        assert step.commands == ["echo hello"]
        assert step.rollback_instructions == "Rollback step"

    def test_runbook_step_no_commands(self):
        step = _make_step()
        assert step.commands is None


# ===========================================================================
# 14. API Endpoint Integration Tests
# ===========================================================================


@pytest.mark.anyio
class TestAPIEndpoints:
    """Integration tests for disaster recovery API."""

    async def test_list_runbooks(self, svc: DisasterRecoveryService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/runbooks")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 10
            assert len(data["items"]) == 10

    async def test_list_runbooks_filter_category(self, svc: DisasterRecoveryService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/runbooks",
                params={"category": "DATABASE_FAILURE"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 2

    async def test_list_runbooks_filter_tier(self, svc: DisasterRecoveryService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/runbooks",
                params={"tier": "TIER_1_CRITICAL"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] >= 3

    async def test_list_runbooks_filter_status(self, svc: DisasterRecoveryService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(
                f"{API_PREFIX}/runbooks",
                params={"status": "TESTED"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] >= 2

    async def test_create_runbook(self, svc: DisasterRecoveryService):
        payload = {
            "title": "API Test Runbook",
            "category": "NETWORK_PARTITION",
            "tier": "TIER_3_MEDIUM",
            "rto_minutes": 120,
            "rpo_minutes": 30,
            "steps": [
                {
                    "step_number": 1,
                    "title": "Step 1",
                    "description": "First step",
                    "responsible_role": "SRE",
                    "estimated_minutes": 10,
                    "verification_criteria": "Done",
                    "rollback_instructions": "Undo",
                }
            ],
            "prerequisites": ["Network diagram available"],
            "communication_plan": ["Alert team"],
            "escalation_contacts": [{"name": "Net Lead", "role": "Networking"}],
        }
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(f"{API_PREFIX}/runbooks", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["title"] == "API Test Runbook"
            assert data["status"] == "DRAFT"
            assert data["category"] == "NETWORK_PARTITION"

    async def test_get_runbook(self, svc: DisasterRecoveryService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/runbooks/DR-001")
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == "DR-001"
            assert data["title"] == "PostgreSQL Primary Failover"

    async def test_get_runbook_not_found(self, svc: DisasterRecoveryService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/runbooks/DR-GHOST")
            assert resp.status_code == 404

    async def test_update_runbook(self, svc: DisasterRecoveryService):
        payload = {"title": "Updated PostgreSQL Failover"}
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.put(f"{API_PREFIX}/runbooks/DR-001", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data["title"] == "Updated PostgreSQL Failover"
            assert data["version"] == 4  # Was 3

    async def test_update_runbook_not_found(self, svc: DisasterRecoveryService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.put(
                f"{API_PREFIX}/runbooks/DR-GHOST",
                json={"title": "Ghost"},
            )
            assert resp.status_code == 404

    async def test_delete_runbook(self, svc: DisasterRecoveryService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.delete(f"{API_PREFIX}/runbooks/DR-001")
            assert resp.status_code == 204

            # Verify it's gone
            resp2 = await client.get(f"{API_PREFIX}/runbooks/DR-001")
            assert resp2.status_code == 404

    async def test_delete_runbook_not_found(self, svc: DisasterRecoveryService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.delete(f"{API_PREFIX}/runbooks/DR-GHOST")
            assert resp.status_code == 404

    async def test_record_test(self, svc: DisasterRecoveryService):
        payload = {
            "tester": "API Tester",
            "actual_rto_minutes": 20.0,
            "actual_rpo_minutes": 3.0,
            "result": "PASS",
            "issues_found": ["Minor delay"],
            "lessons_learned": ["Pre-stage scripts"],
            "steps_completed": 8,
            "total_steps": 8,
        }
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(f"{API_PREFIX}/runbooks/DR-001/tests", json=payload)
            assert resp.status_code == 201
            data = resp.json()
            assert data["tester"] == "API Tester"
            assert data["rto_met"] is True
            assert data["rpo_met"] is True

    async def test_record_test_not_found(self, svc: DisasterRecoveryService):
        payload = {
            "tester": "Tester",
            "actual_rto_minutes": 10.0,
            "actual_rpo_minutes": 5.0,
            "result": "PASS",
            "steps_completed": 1,
            "total_steps": 1,
        }
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.post(f"{API_PREFIX}/runbooks/DR-GHOST/tests", json=payload)
            assert resp.status_code == 404

    async def test_get_test_history(self, svc: DisasterRecoveryService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/runbooks/DR-001/tests")
            assert resp.status_code == 200
            data = resp.json()
            assert data["runbook_id"] == "DR-001"
            assert data["total"] >= 1

    async def test_get_test_history_not_found(self, svc: DisasterRecoveryService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/runbooks/DR-GHOST/tests")
            assert resp.status_code == 404

    async def test_validate_runbook(self, svc: DisasterRecoveryService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/runbooks/DR-001/validate")
            assert resp.status_code == 200
            data = resp.json()
            assert data["is_valid"] is True
            assert data["runbook_id"] == "DR-001"

    async def test_validate_runbook_not_found(self, svc: DisasterRecoveryService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/runbooks/DR-GHOST/validate")
            assert resp.status_code == 404

    async def test_get_communication_plan(self, svc: DisasterRecoveryService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/runbooks/DR-001/communication")
            assert resp.status_code == 200
            data = resp.json()
            assert data["runbook_id"] == "DR-001"
            assert len(data["communication_plan"]) >= 3
            assert len(data["escalation_contacts"]) >= 2

    async def test_get_communication_plan_not_found(self, svc: DisasterRecoveryService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/runbooks/DR-GHOST/communication")
            assert resp.status_code == 404

    async def test_get_metrics(self, svc: DisasterRecoveryService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/metrics")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_runbooks"] == 10
            assert "by_category" in data
            assert "by_tier" in data
            assert "by_status" in data
            assert "tested_percentage" in data
            assert "rto_compliance_rate" in data
            assert "rpo_compliance_rate" in data

    async def test_get_overdue(self, svc: DisasterRecoveryService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/overdue")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] >= 2
            ids = {item["id"] for item in data["items"]}
            assert "DR-005" in ids  # Never tested

    async def test_list_categories(self, svc: DisasterRecoveryService):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get(f"{API_PREFIX}/categories")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 10
            values = {c["value"] for c in data}
            assert "DATABASE_FAILURE" in values
            assert "RANSOMWARE" in values
