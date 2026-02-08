"""Tests for Change Control and Configuration Management (VP-Quality-4).

Tests verify:
- Change request CRUD operations
- Change request state machine (valid/invalid transitions)
- Approval workflow by risk level (LOW: 1, MEDIUM: 2, HIGH: 3, CRITICAL: 4)
- Duplicate approval prevention
- Role-based approval chain validation
- Impact assessment capture
- Configuration baseline capture
- Configuration drift detection
- Change metrics calculation
- Pre-populated sample data
- API endpoint integration tests
- Rejection workflow
- Rollback handling
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.change_control import router as change_control_router
from app.schemas.change_control import (
    ApproverRole,
    ChangeMetrics,
    ChangeStatus,
    ChangeType,
    ConfigurationBaseline,
    DriftReport,
    ImpactAssessment,
    RiskLevel,
)
from app.services.change_control_service import (
    APPROVAL_REQUIREMENTS,
    VALID_CHANGE_TRANSITIONS,
    ChangeControlService,
    ChangeRecord,
    get_change_control_service,
    reset_change_control_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons between tests."""
    reset_change_control_service()
    yield
    reset_change_control_service()


@pytest.fixture
def service() -> ChangeControlService:
    """Fresh ChangeControlService instance."""
    return ChangeControlService()


@pytest.fixture
def client() -> TestClient:
    """FastAPI TestClient with change control router mounted."""
    app = FastAPI()
    app.include_router(change_control_router, prefix="/api/v1")
    return TestClient(app)


# ===========================================================================
# 1. Change Request CRUD Operations
# ===========================================================================


class TestChangeRequestCRUD:
    """Test change request create, read, update, list operations."""

    def test_create_change_request_basic(self, service: ChangeControlService):
        """Create a basic change request and verify fields."""
        change = service.create_change_request(
            title="Test change",
            description="Test description",
            change_type=ChangeType.ENHANCEMENT,
            risk_level=RiskLevel.LOW,
            requester="test-user",
        )
        assert change.id is not None
        assert change.id.startswith("CHG-")
        assert change.title == "Test change"
        assert change.description == "Test description"
        assert change.change_type == ChangeType.ENHANCEMENT
        assert change.risk_level == RiskLevel.LOW
        assert change.requester == "test-user"
        assert change.status == ChangeStatus.DRAFT
        assert change.created_at is not None
        assert change.updated_at is not None
        assert change.deployed_at is None
        assert change.closed_at is None

    def test_create_change_request_with_all_fields(self, service: ChangeControlService):
        """Create a change request with all optional fields."""
        impact = ImpactAssessment(
            affected_systems=["system-a", "system-b"],
            patient_data_impact=True,
            phi_details="Reads patient lab results",
            regulatory_impact=True,
            regulatory_details="Requires re-validation",
            performance_impact="Minimal",
            rollback_complexity="MEDIUM",
            estimated_downtime_minutes=10,
        )
        scheduled = datetime.now(timezone.utc) + timedelta(days=7)
        change = service.create_change_request(
            title="Full change",
            description="Complete description",
            change_type=ChangeType.REGULATORY,
            risk_level=RiskLevel.CRITICAL,
            requester="compliance-officer",
            assigned_to="compliance-engineer",
            impact_assessment=impact,
            rollback_plan="Revert all changes",
            testing_requirements="Full regression suite",
            scheduled_date=scheduled,
        )
        assert change.assigned_to == "compliance-engineer"
        assert change.impact_assessment is not None
        assert change.impact_assessment.patient_data_impact is True
        assert change.rollback_plan == "Revert all changes"
        assert change.testing_requirements == "Full regression suite"
        assert change.scheduled_date == scheduled
        assert change.required_approvals == 4  # CRITICAL needs 4

    def test_get_change_request(self, service: ChangeControlService):
        """Retrieve a change request by ID."""
        change = service.create_change_request(
            title="Get test",
            description="Test",
            change_type=ChangeType.BUG_FIX,
            risk_level=RiskLevel.LOW,
            requester="tester",
        )
        retrieved = service.get_change_request(change.id)
        assert retrieved is not None
        assert retrieved.id == change.id
        assert retrieved.title == "Get test"

    def test_get_change_request_not_found(self, service: ChangeControlService):
        """Return None for non-existent change request."""
        assert service.get_change_request("CHG-NONEXISTENT") is None

    def test_update_change_request_fields(self, service: ChangeControlService):
        """Update change request fields."""
        change = service.create_change_request(
            title="Original",
            description="Original desc",
            change_type=ChangeType.ENHANCEMENT,
            risk_level=RiskLevel.LOW,
            requester="tester",
        )
        updated = service.update_change_request(
            change_id=change.id,
            title="Updated title",
            description="Updated desc",
            assigned_to="new-assignee",
            rollback_plan="New rollback plan",
            testing_requirements="New testing reqs",
        )
        assert updated.title == "Updated title"
        assert updated.description == "Updated desc"
        assert updated.assigned_to == "new-assignee"
        assert updated.rollback_plan == "New rollback plan"
        assert updated.testing_requirements == "New testing reqs"
        assert updated.updated_at >= change.created_at

    def test_update_change_request_not_found(self, service: ChangeControlService):
        """Raise ValueError when updating non-existent change."""
        with pytest.raises(ValueError, match="not found"):
            service.update_change_request(
                change_id="CHG-MISSING", title="Nope"
            )

    def test_list_change_requests_all(self, service: ChangeControlService):
        """List all change requests including seeded ones."""
        changes, total = service.list_change_requests()
        assert total >= 5  # 5 seeded
        assert len(changes) >= 5

    def test_list_change_requests_filter_by_status(self, service: ChangeControlService):
        """Filter changes by status."""
        changes, total = service.list_change_requests(status=ChangeStatus.IN_PROGRESS)
        assert total >= 1
        for c in changes:
            assert c.status == ChangeStatus.IN_PROGRESS

    def test_list_change_requests_filter_by_risk(self, service: ChangeControlService):
        """Filter changes by risk level."""
        changes, total = service.list_change_requests(risk_level=RiskLevel.CRITICAL)
        assert total >= 1
        for c in changes:
            assert c.risk_level == RiskLevel.CRITICAL

    def test_list_change_requests_filter_by_type(self, service: ChangeControlService):
        """Filter changes by change type."""
        changes, total = service.list_change_requests(change_type=ChangeType.BUG_FIX)
        assert total >= 1
        for c in changes:
            assert c.change_type == ChangeType.BUG_FIX

    def test_list_change_requests_filter_by_requester(self, service: ChangeControlService):
        """Filter changes by requester."""
        changes, total = service.list_change_requests(requester="clinical-ops-lead")
        assert total >= 1
        for c in changes:
            assert c.requester == "clinical-ops-lead"

    def test_list_change_requests_pagination(self, service: ChangeControlService):
        """Test pagination of change requests."""
        changes, total = service.list_change_requests(limit=2, offset=0)
        assert len(changes) == 2
        assert total >= 5

        changes2, total2 = service.list_change_requests(limit=2, offset=2)
        assert len(changes2) == 2
        assert total2 == total
        # Different items
        assert changes[0].id != changes2[0].id


# ===========================================================================
# 2. State Machine Transitions
# ===========================================================================


class TestStateTransitions:
    """Test valid and invalid change status transitions."""

    def test_valid_draft_to_submitted(self, service: ChangeControlService):
        """DRAFT -> SUBMITTED is valid."""
        change = service.create_change_request(
            title="Transition test",
            description="Test",
            change_type=ChangeType.ENHANCEMENT,
            risk_level=RiskLevel.LOW,
            requester="tester",
        )
        updated = service.update_change_request(
            change_id=change.id, status=ChangeStatus.SUBMITTED
        )
        assert updated.status == ChangeStatus.SUBMITTED

    def test_valid_submitted_to_impact_assessed(self, service: ChangeControlService):
        """SUBMITTED -> IMPACT_ASSESSED is valid."""
        change = service.create_change_request(
            title="Test",
            description="Test",
            change_type=ChangeType.ENHANCEMENT,
            risk_level=RiskLevel.LOW,
            requester="tester",
        )
        service.update_change_request(
            change_id=change.id, status=ChangeStatus.SUBMITTED
        )
        updated = service.update_change_request(
            change_id=change.id, status=ChangeStatus.IMPACT_ASSESSED
        )
        assert updated.status == ChangeStatus.IMPACT_ASSESSED

    def test_invalid_transition_draft_to_deployed(self, service: ChangeControlService):
        """DRAFT -> DEPLOYED is invalid."""
        change = service.create_change_request(
            title="Bad transition",
            description="Test",
            change_type=ChangeType.ENHANCEMENT,
            risk_level=RiskLevel.LOW,
            requester="tester",
        )
        with pytest.raises(ValueError, match="Invalid status transition"):
            service.update_change_request(
                change_id=change.id, status=ChangeStatus.DEPLOYED
            )

    def test_invalid_transition_closed_terminal(self, service: ChangeControlService):
        """CLOSED is terminal - no transitions allowed."""
        # Get CHG-003 which is DEPLOYED, transition through to CLOSED
        change = service.get_change_request("CHG-003")
        assert change is not None
        assert change.status == ChangeStatus.DEPLOYED
        service.update_change_request(
            change_id="CHG-003", status=ChangeStatus.VERIFIED
        )
        service.update_change_request(
            change_id="CHG-003", status=ChangeStatus.CLOSED
        )
        with pytest.raises(ValueError, match="Invalid status transition"):
            service.update_change_request(
                change_id="CHG-003", status=ChangeStatus.DRAFT
            )

    def test_deployed_sets_deployed_at(self, service: ChangeControlService):
        """Transitioning to DEPLOYED sets deployed_at timestamp."""
        change = service.create_change_request(
            title="Deploy test",
            description="Test",
            change_type=ChangeType.ENHANCEMENT,
            risk_level=RiskLevel.LOW,
            requester="tester",
        )
        # Walk through valid transitions
        service.update_change_request(change_id=change.id, status=ChangeStatus.SUBMITTED)
        # Approve (LOW risk = 1 approval)
        service.approve_change(change.id, "lead", ApproverRole.TEAM_LEAD)
        # Now it's APPROVED
        service.update_change_request(change_id=change.id, status=ChangeStatus.IN_PROGRESS)
        service.update_change_request(change_id=change.id, status=ChangeStatus.TESTING)
        service.update_change_request(change_id=change.id, status=ChangeStatus.DEPLOYED)
        updated = service.get_change_request(change.id)
        assert updated is not None
        assert updated.deployed_at is not None

    def test_rolled_back_sets_rolled_back_at(self, service: ChangeControlService):
        """Transitioning to ROLLED_BACK sets rolled_back_at timestamp."""
        change = service.create_change_request(
            title="Rollback test",
            description="Test",
            change_type=ChangeType.BUG_FIX,
            risk_level=RiskLevel.LOW,
            requester="tester",
        )
        service.update_change_request(change_id=change.id, status=ChangeStatus.SUBMITTED)
        service.approve_change(change.id, "lead", ApproverRole.TEAM_LEAD)
        service.update_change_request(change_id=change.id, status=ChangeStatus.IN_PROGRESS)
        service.update_change_request(change_id=change.id, status=ChangeStatus.ROLLED_BACK)
        updated = service.get_change_request(change.id)
        assert updated is not None
        assert updated.rolled_back_at is not None

    def test_all_valid_transitions_defined(self):
        """Verify every ChangeStatus has a transition entry."""
        for status_val in ChangeStatus:
            assert status_val in VALID_CHANGE_TRANSITIONS


# ===========================================================================
# 3. Approval Workflow
# ===========================================================================


class TestApprovalWorkflow:
    """Test risk-based approval workflow."""

    def test_low_risk_requires_one_approval(self, service: ChangeControlService):
        """LOW risk needs 1 approver (team lead)."""
        change = service.create_change_request(
            title="Low risk",
            description="Test",
            change_type=ChangeType.CONFIGURATION,
            risk_level=RiskLevel.LOW,
            requester="tester",
        )
        assert change.required_approvals == 1
        service.update_change_request(change_id=change.id, status=ChangeStatus.SUBMITTED)
        approved = service.approve_change(
            change.id, "team-lead", ApproverRole.TEAM_LEAD, "Looks good"
        )
        assert approved.current_approvals == 1
        assert approved.status == ChangeStatus.APPROVED  # Auto-approved

    def test_medium_risk_requires_two_approvals(self, service: ChangeControlService):
        """MEDIUM risk needs 2 approvers (team lead + QA)."""
        change = service.create_change_request(
            title="Medium risk",
            description="Test",
            change_type=ChangeType.ENHANCEMENT,
            risk_level=RiskLevel.MEDIUM,
            requester="tester",
        )
        assert change.required_approvals == 2
        service.update_change_request(change_id=change.id, status=ChangeStatus.SUBMITTED)
        # First approval
        partial = service.approve_change(
            change.id, "team-lead", ApproverRole.TEAM_LEAD
        )
        assert partial.current_approvals == 1
        assert partial.status == ChangeStatus.SUBMITTED  # Not yet approved
        # Second approval
        approved = service.approve_change(
            change.id, "qa-lead", ApproverRole.QA
        )
        assert approved.current_approvals == 2
        assert approved.status == ChangeStatus.APPROVED

    def test_high_risk_requires_three_approvals(self, service: ChangeControlService):
        """HIGH risk needs 3 approvers (team lead + QA + compliance)."""
        change = service.create_change_request(
            title="High risk",
            description="Test",
            change_type=ChangeType.INFRASTRUCTURE,
            risk_level=RiskLevel.HIGH,
            requester="tester",
        )
        assert change.required_approvals == 3

    def test_critical_risk_requires_four_approvals(self, service: ChangeControlService):
        """CRITICAL risk needs 4 approvers."""
        change = service.create_change_request(
            title="Critical risk",
            description="Test",
            change_type=ChangeType.REGULATORY,
            risk_level=RiskLevel.CRITICAL,
            requester="tester",
        )
        assert change.required_approvals == 4

    def test_cannot_approve_in_wrong_status(self, service: ChangeControlService):
        """Cannot approve change that is not in SUBMITTED or IMPACT_ASSESSED."""
        change = service.create_change_request(
            title="Wrong status",
            description="Test",
            change_type=ChangeType.ENHANCEMENT,
            risk_level=RiskLevel.LOW,
            requester="tester",
        )
        # Still in DRAFT
        with pytest.raises(ValueError, match="cannot be approved"):
            service.approve_change(change.id, "lead", ApproverRole.TEAM_LEAD)

    def test_duplicate_role_approval_rejected(self, service: ChangeControlService):
        """Cannot approve twice with same role."""
        change = service.create_change_request(
            title="Duplicate test",
            description="Test",
            change_type=ChangeType.ENHANCEMENT,
            risk_level=RiskLevel.MEDIUM,
            requester="tester",
        )
        service.update_change_request(change_id=change.id, status=ChangeStatus.SUBMITTED)
        service.approve_change(change.id, "lead-1", ApproverRole.TEAM_LEAD)
        with pytest.raises(ValueError, match="already approved"):
            service.approve_change(change.id, "lead-2", ApproverRole.TEAM_LEAD)

    def test_invalid_role_for_risk_level(self, service: ChangeControlService):
        """Cannot approve with a role not in the required chain."""
        change = service.create_change_request(
            title="Invalid role",
            description="Test",
            change_type=ChangeType.ENHANCEMENT,
            risk_level=RiskLevel.LOW,
            requester="tester",
        )
        service.update_change_request(change_id=change.id, status=ChangeStatus.SUBMITTED)
        # LOW risk only needs TEAM_LEAD, not EXECUTIVE
        with pytest.raises(ValueError, match="not in the required approval chain"):
            service.approve_change(change.id, "exec", ApproverRole.EXECUTIVE)

    def test_cannot_manually_approve_without_enough_approvals(self, service: ChangeControlService):
        """Cannot manually transition to APPROVED without enough approvals."""
        change = service.create_change_request(
            title="Manual approve",
            description="Test",
            change_type=ChangeType.ENHANCEMENT,
            risk_level=RiskLevel.MEDIUM,
            requester="tester",
        )
        service.update_change_request(change_id=change.id, status=ChangeStatus.SUBMITTED)
        service.update_change_request(change_id=change.id, status=ChangeStatus.IMPACT_ASSESSED)
        # Try to go to APPROVED without any approvals
        with pytest.raises(ValueError, match="Cannot approve"):
            service.update_change_request(
                change_id=change.id, status=ChangeStatus.APPROVED
            )

    def test_approval_requirements_map(self):
        """Verify approval requirements are correctly defined."""
        assert len(APPROVAL_REQUIREMENTS[RiskLevel.LOW]) == 1
        assert len(APPROVAL_REQUIREMENTS[RiskLevel.MEDIUM]) == 2
        assert len(APPROVAL_REQUIREMENTS[RiskLevel.HIGH]) == 3
        assert len(APPROVAL_REQUIREMENTS[RiskLevel.CRITICAL]) == 4


# ===========================================================================
# 4. Rejection Workflow
# ===========================================================================


class TestRejectionWorkflow:
    """Test change rejection."""

    def test_reject_submitted_change(self, service: ChangeControlService):
        """Reject a submitted change request."""
        change = service.create_change_request(
            title="To reject",
            description="Test",
            change_type=ChangeType.ENHANCEMENT,
            risk_level=RiskLevel.LOW,
            requester="tester",
        )
        service.update_change_request(change_id=change.id, status=ChangeStatus.SUBMITTED)
        rejected = service.reject_change(
            change.id, "qa-lead", ApproverRole.QA, "Does not meet criteria"
        )
        assert rejected.status == ChangeStatus.REJECTED
        assert len(rejected.approval_chain) == 1
        assert rejected.approval_chain[0].decision == "REJECTED"
        assert rejected.approval_chain[0].comment == "Does not meet criteria"

    def test_cannot_reject_terminal_change(self, service: ChangeControlService):
        """Cannot reject a change that is already in terminal state."""
        change = service.create_change_request(
            title="Terminal reject",
            description="Test",
            change_type=ChangeType.BUG_FIX,
            risk_level=RiskLevel.LOW,
            requester="tester",
        )
        service.update_change_request(change_id=change.id, status=ChangeStatus.SUBMITTED)
        service.reject_change(change.id, "lead", ApproverRole.TEAM_LEAD, "No")
        with pytest.raises(ValueError, match="terminal status"):
            service.reject_change(change.id, "qa", ApproverRole.QA, "Also no")

    def test_reject_nonexistent_change(self, service: ChangeControlService):
        """Rejecting non-existent change raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            service.reject_change(
                "CHG-FAKE", "lead", ApproverRole.TEAM_LEAD, "No"
            )


# ===========================================================================
# 5. Configuration Baseline Management
# ===========================================================================


class TestConfigurationBaselines:
    """Test configuration baseline capture and listing."""

    def test_capture_baseline(self, service: ChangeControlService):
        """Capture a new configuration baseline."""
        baseline = service.capture_baseline(
            name="Test Baseline",
            description="For testing",
            captured_by="test-user",
            environment="staging",
        )
        assert baseline.id.startswith("BL-")
        assert baseline.name == "Test Baseline"
        assert baseline.description == "For testing"
        assert baseline.captured_by == "test-user"
        assert baseline.environment == "staging"
        assert len(baseline.items) > 0

    def test_list_baselines(self, service: ChangeControlService):
        """List baselines includes seeded baseline."""
        baselines = service.list_baselines()
        assert len(baselines) >= 1
        assert baselines[0].id == "BL-001"  # Most recent is seeded one

    def test_capture_multiple_baselines(self, service: ChangeControlService):
        """Capture multiple baselines and list them."""
        service.capture_baseline(name="BL Alpha", captured_by="user-a")
        service.capture_baseline(name="BL Beta", captured_by="user-b")
        baselines = service.list_baselines()
        assert len(baselines) >= 3  # 1 seeded + 2 new

    def test_baseline_items_snapshot(self, service: ChangeControlService):
        """Baseline items are a snapshot of current config."""
        # Modify a config item
        service.update_config_item("DATABASE_POOL_SIZE", "30")
        # Capture baseline with new value
        baseline = service.capture_baseline(name="After change", captured_by="test")
        # Find the item in baseline
        pool_item = next(
            (i for i in baseline.items if i.key == "DATABASE_POOL_SIZE"), None
        )
        assert pool_item is not None
        assert pool_item.value == "30"


# ===========================================================================
# 6. Configuration Drift Detection
# ===========================================================================


class TestDriftDetection:
    """Test configuration drift detection."""

    def test_detect_drift_with_changes(self, service: ChangeControlService):
        """Detect drift between current config and baseline."""
        # Seeded baseline has NLP_MODEL_VERSION=2.3.0 but current is 2.4.1
        # and API_RATE_LIMIT_PER_MINUTE was 100 in baseline but is 120 now
        report = service.detect_drift(baseline_id="BL-001")
        assert isinstance(report, DriftReport)
        assert report.baseline_id == "BL-001"
        assert report.drifted_items >= 2
        assert report.drift_percentage > 0

        # Check that NLP model version drift is detected
        nlp_drift = next(
            (d for d in report.drifts if d.key == "NLP_MODEL_VERSION"), None
        )
        assert nlp_drift is not None
        assert nlp_drift.baseline_value == "2.3.0"
        assert nlp_drift.current_value == "2.4.1"

    def test_detect_drift_no_baseline_id(self, service: ChangeControlService):
        """Uses most recent baseline when no ID provided."""
        report = service.detect_drift()
        assert report.baseline_id is not None

    def test_detect_drift_nonexistent_baseline(self, service: ChangeControlService):
        """Raise ValueError for non-existent baseline."""
        with pytest.raises(ValueError, match="not found"):
            service.detect_drift(baseline_id="BL-FAKE")

    def test_drift_severity_by_category(self, service: ChangeControlService):
        """Drift severity is based on config category."""
        report = service.detect_drift(baseline_id="BL-001")
        for drift in report.drifts:
            if drift.category == "service_version":
                assert drift.severity in ("MEDIUM", "HIGH")

    def test_no_drift_after_baseline_capture(self, service: ChangeControlService):
        """No drift detected right after capturing a baseline."""
        baseline = service.capture_baseline(name="Fresh", captured_by="test")
        report = service.detect_drift(baseline_id=baseline.id)
        assert report.drifted_items == 0
        assert report.drift_percentage == 0.0
        assert len(report.drifts) == 0


# ===========================================================================
# 7. Configuration Items
# ===========================================================================


class TestConfigurationItems:
    """Test configuration item management."""

    def test_get_current_config(self, service: ChangeControlService):
        """Get current configuration items."""
        items = service.get_current_config()
        assert len(items) >= 10
        keys = [i.key for i in items]
        assert "DATABASE_POOL_SIZE" in keys

    def test_update_existing_config_item(self, service: ChangeControlService):
        """Update an existing configuration item."""
        updated = service.update_config_item("DATABASE_POOL_SIZE", "50")
        assert updated.value == "50"
        # Verify in current config
        items = service.get_current_config()
        pool = next(i for i in items if i.key == "DATABASE_POOL_SIZE")
        assert pool.value == "50"

    def test_create_new_config_item(self, service: ChangeControlService):
        """Create a new configuration item."""
        item = service.update_config_item(
            "NEW_FEATURE_FLAG",
            "enabled",
            category="feature_flag",
            description="A new feature flag",
        )
        assert item.key == "NEW_FEATURE_FLAG"
        assert item.value == "enabled"
        assert item.category == "feature_flag"


# ===========================================================================
# 8. Change Metrics
# ===========================================================================


class TestChangeMetrics:
    """Test change control metrics calculation."""

    def test_metrics_basic(self, service: ChangeControlService):
        """Get basic metrics from seeded data."""
        metrics = service.get_metrics()
        assert isinstance(metrics, ChangeMetrics)
        assert metrics.total_changes >= 5
        assert metrics.open_changes >= 1

    def test_metrics_by_risk_level(self, service: ChangeControlService):
        """Metrics include breakdown by risk level."""
        metrics = service.get_metrics()
        assert len(metrics.by_risk_level) > 0
        # We have at least LOW, MEDIUM, HIGH, CRITICAL in seeds
        assert sum(metrics.by_risk_level.values()) == metrics.total_changes

    def test_metrics_by_status(self, service: ChangeControlService):
        """Metrics include breakdown by status."""
        metrics = service.get_metrics()
        assert len(metrics.by_status) > 0
        assert sum(metrics.by_status.values()) == metrics.total_changes

    def test_metrics_by_type(self, service: ChangeControlService):
        """Metrics include breakdown by change type."""
        metrics = service.get_metrics()
        assert len(metrics.by_type) > 0

    def test_metrics_deployed_last_30_days(self, service: ChangeControlService):
        """Metrics track deployments in last 30 days."""
        metrics = service.get_metrics()
        assert metrics.deployed_last_30_days >= 0

    def test_metrics_pending_approvals(self, service: ChangeControlService):
        """Metrics track pending approvals."""
        metrics = service.get_metrics()
        assert metrics.pending_approvals >= 1  # CHG-004 is SUBMITTED, CHG-005 is IMPACT_ASSESSED


# ===========================================================================
# 9. Pre-populated Data
# ===========================================================================


class TestSeededData:
    """Test pre-populated sample data."""

    def test_five_sample_changes(self, service: ChangeControlService):
        """Verify 5 sample change requests exist."""
        changes, total = service.list_change_requests()
        assert total >= 5

    def test_seeded_change_ids(self, service: ChangeControlService):
        """Verify seeded change IDs exist."""
        for cid in ["CHG-001", "CHG-002", "CHG-003", "CHG-004", "CHG-005"]:
            change = service.get_change_request(cid)
            assert change is not None, f"Missing seeded change: {cid}"

    def test_seeded_baseline_exists(self, service: ChangeControlService):
        """Verify seeded baseline exists."""
        baselines = service.list_baselines()
        assert any(b.id == "BL-001" for b in baselines)

    def test_seeded_change_types_variety(self, service: ChangeControlService):
        """Verify seeded changes have different types."""
        changes, _ = service.list_change_requests()
        types_seen = {c.change_type for c in changes[:5]}
        assert len(types_seen) >= 4  # At least 4 different types

    def test_seeded_risk_levels_variety(self, service: ChangeControlService):
        """Verify seeded changes have different risk levels."""
        changes, _ = service.list_change_requests()
        risks_seen = {c.risk_level for c in changes[:5]}
        assert len(risks_seen) >= 3  # At least 3 different risk levels


# ===========================================================================
# 10. API Endpoint Integration Tests
# ===========================================================================


class TestAPIEndpoints:
    """Test API endpoints via TestClient."""

    def test_api_create_change(self, client: TestClient):
        """POST /quality/changes creates a change request."""
        response = client.post(
            "/api/v1/quality/changes",
            json={
                "title": "API test change",
                "description": "Created via API",
                "change_type": "ENHANCEMENT",
                "risk_level": "LOW",
                "requester": "api-tester",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "API test change"
        assert data["status"] == "DRAFT"
        assert data["required_approvals"] == 1

    def test_api_list_changes(self, client: TestClient):
        """GET /quality/changes returns list."""
        response = client.get("/api/v1/quality/changes")
        assert response.status_code == 200
        data = response.json()
        assert "changes" in data
        assert "total" in data
        assert data["total"] >= 5

    def test_api_list_changes_with_filter(self, client: TestClient):
        """GET /quality/changes?status=IN_PROGRESS filters correctly."""
        response = client.get(
            "/api/v1/quality/changes", params={"status": "IN_PROGRESS"}
        )
        assert response.status_code == 200
        data = response.json()
        for change in data["changes"]:
            assert change["status"] == "IN_PROGRESS"

    def test_api_get_change_detail(self, client: TestClient):
        """GET /quality/changes/{id} returns detail."""
        response = client.get("/api/v1/quality/changes/CHG-001")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "CHG-001"
        assert data["impact_assessment"] is not None

    def test_api_get_change_not_found(self, client: TestClient):
        """GET /quality/changes/{id} returns 404 for missing change."""
        response = client.get("/api/v1/quality/changes/CHG-NONEXISTENT")
        assert response.status_code == 404

    def test_api_update_change(self, client: TestClient):
        """PUT /quality/changes/{id} updates change."""
        # Create a change first
        create_resp = client.post(
            "/api/v1/quality/changes",
            json={
                "title": "To update",
                "description": "Will be updated",
                "change_type": "BUG_FIX",
                "risk_level": "LOW",
                "requester": "tester",
            },
        )
        change_id = create_resp.json()["id"]

        response = client.put(
            f"/api/v1/quality/changes/{change_id}",
            json={"title": "Updated via API", "status": "SUBMITTED"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated via API"
        assert data["status"] == "SUBMITTED"

    def test_api_update_change_invalid_transition(self, client: TestClient):
        """PUT /quality/changes/{id} returns 400 for invalid transition."""
        create_resp = client.post(
            "/api/v1/quality/changes",
            json={
                "title": "Bad transition",
                "description": "Test",
                "change_type": "BUG_FIX",
                "risk_level": "LOW",
                "requester": "tester",
            },
        )
        change_id = create_resp.json()["id"]

        response = client.put(
            f"/api/v1/quality/changes/{change_id}",
            json={"status": "DEPLOYED"},
        )
        assert response.status_code == 400

    def test_api_approve_change(self, client: TestClient):
        """POST /quality/changes/{id}/approve approves change."""
        # Create and submit
        create_resp = client.post(
            "/api/v1/quality/changes",
            json={
                "title": "To approve",
                "description": "Test",
                "change_type": "CONFIGURATION",
                "risk_level": "LOW",
                "requester": "tester",
            },
        )
        change_id = create_resp.json()["id"]
        client.put(
            f"/api/v1/quality/changes/{change_id}",
            json={"status": "SUBMITTED"},
        )

        response = client.post(
            f"/api/v1/quality/changes/{change_id}/approve",
            json={"approver": "team-lead", "role": "TEAM_LEAD"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["current_approvals"] == 1
        assert data["status"] == "APPROVED"

    def test_api_reject_change(self, client: TestClient):
        """POST /quality/changes/{id}/reject rejects change."""
        create_resp = client.post(
            "/api/v1/quality/changes",
            json={
                "title": "To reject",
                "description": "Test",
                "change_type": "BUG_FIX",
                "risk_level": "LOW",
                "requester": "tester",
            },
        )
        change_id = create_resp.json()["id"]
        client.put(
            f"/api/v1/quality/changes/{change_id}",
            json={"status": "SUBMITTED"},
        )

        response = client.post(
            f"/api/v1/quality/changes/{change_id}/reject",
            json={
                "approver": "qa-lead",
                "role": "QA",
                "reason": "Insufficient testing plan",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "REJECTED"

    def test_api_get_change_metrics(self, client: TestClient):
        """GET /quality/changes/metrics returns metrics."""
        response = client.get("/api/v1/quality/changes/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "total_changes" in data
        assert "by_risk_level" in data
        assert "change_failure_rate" in data

    def test_api_capture_baseline(self, client: TestClient):
        """POST /quality/config/baseline captures baseline."""
        response = client.post(
            "/api/v1/quality/config/baseline",
            json={
                "name": "API Baseline",
                "description": "Captured via API",
                "captured_by": "api-tester",
                "environment": "staging",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "API Baseline"
        assert len(data["items"]) > 0

    def test_api_list_baselines(self, client: TestClient):
        """GET /quality/config/baselines returns list."""
        response = client.get("/api/v1/quality/config/baselines")
        assert response.status_code == 200
        data = response.json()
        assert "baselines" in data
        assert data["total"] >= 1

    def test_api_detect_drift(self, client: TestClient):
        """GET /quality/config/drift returns drift report."""
        response = client.get("/api/v1/quality/config/drift")
        assert response.status_code == 200
        data = response.json()
        assert "baseline_id" in data
        assert "drifted_items" in data
        assert "drift_percentage" in data

    def test_api_detect_drift_with_baseline_id(self, client: TestClient):
        """GET /quality/config/drift?baseline_id=BL-001 uses specified baseline."""
        response = client.get(
            "/api/v1/quality/config/drift", params={"baseline_id": "BL-001"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["baseline_id"] == "BL-001"

    def test_api_detect_drift_invalid_baseline(self, client: TestClient):
        """GET /quality/config/drift?baseline_id=FAKE returns 404."""
        response = client.get(
            "/api/v1/quality/config/drift", params={"baseline_id": "BL-FAKE"}
        )
        assert response.status_code == 404
