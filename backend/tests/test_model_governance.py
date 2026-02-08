"""Tests for Model Governance & Lifecycle Management Service (VP-DS-8).

Covers:
- Seed data: pre-populated models, validations, approvals, alerts
- Model CRUD: register, get, list, update, delete
- Lifecycle transitions: validation -> approval -> deploy -> deprecate -> retire
- Tier-based approval: TIER_1 (3 approvers), TIER_2 (2 approvers), TIER_3 (1 approver)
- Validation records: submit, list
- Approval workflows: request, approve, reject, partial approvals
- Monitoring alerts: record, acknowledge, resolve, filter
- Overdue reviews
- Governance metrics
- Model history
- Singleton pattern
- Thread safety
- API endpoint smoke tests (15+ endpoints)
"""

from __future__ import annotations

import threading

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.model_governance import (
    AlertSeverity,
    AlertType,
    ApprovalStatus,
    GovernanceStatus,
    GovernedModelType,
    ModelRiskTier,
    ValidationType,
)
from app.services.model_governance_service import (
    ModelGovernanceService,
    get_model_governance_service,
    reset_model_governance_service,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_service():
    """Reset the singleton service before and after each test."""
    reset_model_governance_service()
    yield
    reset_model_governance_service()


@pytest.fixture
def service() -> ModelGovernanceService:
    return get_model_governance_service()


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ============================================================================
# Seed Data Tests
# ============================================================================


class TestSeedData:
    """Tests for pre-populated seed data."""

    def test_seed_models_count(self, service: ModelGovernanceService):
        """Should have 8 pre-populated models."""
        models = service.list_models()
        assert len(models) == 8

    def test_seed_model_names(self, service: ModelGovernanceService):
        """All expected model names should be present."""
        models = service.list_models()
        names = {m.name for m in models}
        assert "NLP Entity Extractor" in names
        assert "Trial Eligibility Scorer" in names
        assert "Risk Prediction Model" in names
        assert "Drug Interaction Classifier" in names
        assert "OMOP Concept Mapper" in names
        assert "Patient Similarity Engine" in names
        assert "Adverse Event Detector" in names
        assert "Internal Analytics Dashboard Model" in names

    def test_seed_model_risk_tiers(self, service: ModelGovernanceService):
        """Should have models across all risk tiers."""
        models = service.list_models()
        tiers = {m.risk_tier for m in models}
        assert ModelRiskTier.TIER_1_HIGH in tiers
        assert ModelRiskTier.TIER_2_MEDIUM in tiers
        assert ModelRiskTier.TIER_3_LOW in tiers

    def test_seed_model_statuses(self, service: ModelGovernanceService):
        """Should have models in multiple governance statuses."""
        models = service.list_models()
        statuses = {m.status for m in models}
        assert GovernanceStatus.DEPLOYED in statuses
        assert GovernanceStatus.MONITORING in statuses
        assert GovernanceStatus.PENDING_APPROVAL in statuses

    def test_seed_validation_records(self, service: ModelGovernanceService):
        """Should have pre-populated validation records."""
        records = service.get_validations("gov-model-001")
        assert len(records) >= 2
        types = {r.validation_type for r in records}
        assert ValidationType.TECHNICAL in types
        assert ValidationType.CLINICAL in types

    def test_seed_pending_approvals(self, service: ModelGovernanceService):
        """Should have pending approval requests."""
        requests_003 = service.get_approval_requests("gov-model-003")
        pending = [r for r in requests_003 if r.status == ApprovalStatus.PENDING]
        assert len(pending) >= 1

        requests_007 = service.get_approval_requests("gov-model-007")
        pending_007 = [r for r in requests_007 if r.status == ApprovalStatus.PENDING]
        assert len(pending_007) >= 1

    def test_seed_monitoring_alerts(self, service: ModelGovernanceService):
        """Should have pre-populated monitoring alerts."""
        alerts = service.get_alerts()
        assert len(alerts) >= 3
        alert_types = {a.alert_type for a in alerts}
        assert AlertType.DRIFT in alert_types
        assert AlertType.PERFORMANCE_DEGRADATION in alert_types

    def test_seed_model_get_by_id(self, service: ModelGovernanceService):
        """Should retrieve seed model by known ID."""
        model = service.get_model("gov-model-001")
        assert model is not None
        assert model.name == "NLP Entity Extractor"

    def test_seed_model_performance_metrics(self, service: ModelGovernanceService):
        """Seed models should have performance metrics."""
        model = service.get_model("gov-model-001")
        assert model is not None
        assert "f1" in model.performance_metrics
        assert model.performance_metrics["f1"] == 0.94


# ============================================================================
# Model CRUD Tests
# ============================================================================


class TestModelCRUD:
    """Tests for model CRUD operations."""

    def test_register_model(self, service: ModelGovernanceService):
        """Should register a new governed model."""
        model = service.register_model(
            name="New Test Model",
            version="1.0.0",
            model_type=GovernedModelType.CLASSIFICATION,
            risk_tier=ModelRiskTier.TIER_2_MEDIUM,
            owner="Test Owner",
            description="A test model",
            team="Test Team",
        )
        assert model.id is not None
        assert model.name == "New Test Model"
        assert model.status == GovernanceStatus.DEVELOPMENT
        assert model.risk_tier == ModelRiskTier.TIER_2_MEDIUM

    def test_register_model_with_metrics(self, service: ModelGovernanceService):
        """Should register model with performance and fairness metrics."""
        model = service.register_model(
            name="Metrics Model",
            version="2.0.0",
            model_type=GovernedModelType.NLP,
            risk_tier=ModelRiskTier.TIER_1_HIGH,
            owner="ML Team",
            performance_metrics={"auc": 0.95, "f1": 0.92},
            fairness_metrics={"demographic_parity": 0.98},
        )
        assert model.performance_metrics["auc"] == 0.95
        assert model.fairness_metrics["demographic_parity"] == 0.98

    def test_get_model_not_found(self, service: ModelGovernanceService):
        """Should return None for non-existent model."""
        assert service.get_model("nonexistent-id") is None

    def test_list_models_filter_by_tier(self, service: ModelGovernanceService):
        """Should filter models by risk tier."""
        high_models = service.list_models(risk_tier=ModelRiskTier.TIER_1_HIGH)
        assert all(m.risk_tier == ModelRiskTier.TIER_1_HIGH for m in high_models)
        assert len(high_models) >= 1

    def test_list_models_filter_by_status(self, service: ModelGovernanceService):
        """Should filter models by governance status."""
        deployed = service.list_models(status=GovernanceStatus.DEPLOYED)
        assert all(m.status == GovernanceStatus.DEPLOYED for m in deployed)
        assert len(deployed) >= 1

    def test_list_models_with_limit(self, service: ModelGovernanceService):
        """Should respect limit parameter."""
        models = service.list_models(limit=3)
        assert len(models) <= 3

    def test_update_model(self, service: ModelGovernanceService):
        """Should update mutable model fields."""
        model = service.update_model(
            "gov-model-001",
            description="Updated description",
            performance_metrics={"f1": 0.96},
        )
        assert model is not None
        assert model.description == "Updated description"
        assert model.performance_metrics["f1"] == 0.96

    def test_update_model_not_found(self, service: ModelGovernanceService):
        """Should return None when updating non-existent model."""
        result = service.update_model("nonexistent", description="test")
        assert result is None

    def test_delete_model(self, service: ModelGovernanceService):
        """Should delete a model and its records."""
        initial_count = len(service.list_models())
        result = service.delete_model("gov-model-008")
        assert result is True
        assert len(service.list_models()) == initial_count - 1
        assert service.get_model("gov-model-008") is None

    def test_delete_model_not_found(self, service: ModelGovernanceService):
        """Should return False for non-existent model."""
        assert service.delete_model("nonexistent") is False

    def test_register_model_next_review_date(self, service: ModelGovernanceService):
        """Registered model should have next_review_date set."""
        model = service.register_model(
            name="Review Date Model",
            version="1.0.0",
            model_type=GovernedModelType.REGRESSION,
            risk_tier=ModelRiskTier.TIER_3_LOW,
            owner="Owner",
            review_frequency_days=30,
        )
        assert model.next_review_date is not None


# ============================================================================
# Lifecycle Transition Tests
# ============================================================================


class TestLifecycleTransitions:
    """Tests for model lifecycle state transitions."""

    def test_submit_for_validation(self, service: ModelGovernanceService):
        """Should transition model from DEVELOPMENT to VALIDATION."""
        model = service.register_model(
            name="Lifecycle Model",
            version="1.0.0",
            model_type=GovernedModelType.CLASSIFICATION,
            risk_tier=ModelRiskTier.TIER_3_LOW,
            owner="Test",
        )
        record = service.submit_for_validation(
            model.id, ValidationType.TECHNICAL, "Tester"
        )
        assert record is not None
        assert record.passed is True
        updated = service.get_model(model.id)
        assert updated is not None
        assert updated.status == GovernanceStatus.VALIDATION

    def test_submit_validation_sets_date(self, service: ModelGovernanceService):
        """Validation should set validation_date."""
        model = service.register_model(
            name="Val Date Model",
            version="1.0.0",
            model_type=GovernedModelType.NLP,
            risk_tier=ModelRiskTier.TIER_2_MEDIUM,
            owner="Test",
        )
        service.submit_for_validation(model.id, ValidationType.CLINICAL, "Doctor")
        updated = service.get_model(model.id)
        assert updated is not None
        assert updated.validation_date is not None

    def test_submit_validation_not_found(self, service: ModelGovernanceService):
        """Should return None for non-existent model."""
        assert service.submit_for_validation("fake", ValidationType.TECHNICAL, "x") is None

    def test_request_approval(self, service: ModelGovernanceService):
        """Should create approval request and transition to PENDING_APPROVAL."""
        model = service.register_model(
            name="Approval Model",
            version="1.0.0",
            model_type=GovernedModelType.CLASSIFICATION,
            risk_tier=ModelRiskTier.TIER_3_LOW,
            owner="Test",
        )
        service.submit_for_validation(model.id, ValidationType.TECHNICAL, "Tester")
        request = service.request_approval(model.id)
        assert request is not None
        assert request.status == ApprovalStatus.PENDING
        updated = service.get_model(model.id)
        assert updated is not None
        assert updated.status == GovernanceStatus.PENDING_APPROVAL

    def test_request_approval_not_found(self, service: ModelGovernanceService):
        """Should return None for non-existent model."""
        assert service.request_approval("fake") is None

    def test_request_approval_wrong_status(self, service: ModelGovernanceService):
        """Should return None if model is not in valid status for approval."""
        model = service.register_model(
            name="Wrong Status Model",
            version="1.0.0",
            model_type=GovernedModelType.REGRESSION,
            risk_tier=ModelRiskTier.TIER_3_LOW,
            owner="Test",
        )
        # Model is in DEVELOPMENT, can't request approval
        assert service.request_approval(model.id) is None

    def test_full_lifecycle_tier_3(self, service: ModelGovernanceService):
        """TIER_3 model should complete lifecycle with 1 approval."""
        model = service.register_model(
            name="T3 Model",
            version="1.0.0",
            model_type=GovernedModelType.REGRESSION,
            risk_tier=ModelRiskTier.TIER_3_LOW,
            owner="Test",
        )
        # Validate
        service.submit_for_validation(model.id, ValidationType.TECHNICAL, "Engineer")
        # Request approval
        service.request_approval(model.id)
        # Approve (only 1 needed for TIER_3)
        result = service.approve_model(model.id, "Approver", role="ml_engineer")
        assert result is not None
        assert result.status == ApprovalStatus.APPROVED

        updated = service.get_model(model.id)
        assert updated is not None
        assert updated.status == GovernanceStatus.APPROVED

        # Deploy
        deployed = service.deploy_model(model.id)
        assert deployed is not None
        assert deployed.status == GovernanceStatus.DEPLOYED

    def test_full_lifecycle_tier_1(self, service: ModelGovernanceService):
        """TIER_1 model requires 3 approvals: clinical, regulatory, ml_engineer."""
        model = service.register_model(
            name="T1 Model",
            version="1.0.0",
            model_type=GovernedModelType.CLASSIFICATION,
            risk_tier=ModelRiskTier.TIER_1_HIGH,
            owner="Test",
        )
        service.submit_for_validation(model.id, ValidationType.TECHNICAL, "Engineer")
        service.request_approval(model.id)

        # First approval (partial)
        r1 = service.approve_model(model.id, "Engineer A", role="ml_engineer")
        assert r1 is not None
        assert r1.status == ApprovalStatus.PENDING
        assert service.get_model(model.id).status == GovernanceStatus.PENDING_APPROVAL

        # Second approval (partial)
        r2 = service.approve_model(model.id, "Dr. Smith", role="clinical_lead")
        assert r2 is not None
        assert r2.status == ApprovalStatus.PENDING

        # Third approval (should complete)
        r3 = service.approve_model(model.id, "Reg Officer", role="regulatory_officer")
        assert r3 is not None
        assert r3.status == ApprovalStatus.APPROVED
        assert service.get_model(model.id).status == GovernanceStatus.APPROVED

    def test_full_lifecycle_tier_2(self, service: ModelGovernanceService):
        """TIER_2 model requires 2 approvals: clinical_lead + ml_engineer."""
        model = service.register_model(
            name="T2 Model",
            version="1.0.0",
            model_type=GovernedModelType.NLP,
            risk_tier=ModelRiskTier.TIER_2_MEDIUM,
            owner="Test",
        )
        service.submit_for_validation(model.id, ValidationType.TECHNICAL, "Tester")
        service.request_approval(model.id)

        service.approve_model(model.id, "Engineer", role="ml_engineer")
        result = service.approve_model(model.id, "Doctor", role="clinical_lead")
        assert result is not None
        assert result.status == ApprovalStatus.APPROVED

    def test_deploy_not_approved(self, service: ModelGovernanceService):
        """Should not deploy model that is not APPROVED."""
        model = service.register_model(
            name="Not Approved",
            version="1.0.0",
            model_type=GovernedModelType.REGRESSION,
            risk_tier=ModelRiskTier.TIER_3_LOW,
            owner="Test",
        )
        assert service.deploy_model(model.id) is None

    def test_deploy_not_found(self, service: ModelGovernanceService):
        """Should return None for non-existent model deploy."""
        assert service.deploy_model("fake") is None

    def test_deprecate_model(self, service: ModelGovernanceService):
        """Should deprecate a model."""
        result = service.deprecate_model("gov-model-001")
        assert result is not None
        assert result.status == GovernanceStatus.DEPRECATED

    def test_deprecate_not_found(self, service: ModelGovernanceService):
        """Should return None for non-existent model."""
        assert service.deprecate_model("fake") is None

    def test_retire_model(self, service: ModelGovernanceService):
        """Should retire a model."""
        result = service.retire_model("gov-model-001")
        assert result is not None
        assert result.status == GovernanceStatus.RETIRED

    def test_retire_not_found(self, service: ModelGovernanceService):
        """Should return None for non-existent model."""
        assert service.retire_model("fake") is None


# ============================================================================
# Approval Workflow Tests
# ============================================================================


class TestApprovalWorkflow:
    """Tests for approval workflow details."""

    def test_reject_approval(self, service: ModelGovernanceService):
        """Should reject a pending approval and revert to VALIDATION."""
        model = service.register_model(
            name="Reject Model",
            version="1.0.0",
            model_type=GovernedModelType.CLASSIFICATION,
            risk_tier=ModelRiskTier.TIER_3_LOW,
            owner="Test",
        )
        service.submit_for_validation(model.id, ValidationType.TECHNICAL, "Tester")
        service.request_approval(model.id)

        result = service.reject_approval(model.id, "Reviewer", "Needs more testing")
        assert result is not None
        assert result.status == ApprovalStatus.REJECTED
        assert "Needs more testing" in result.comments

        updated = service.get_model(model.id)
        assert updated is not None
        assert updated.status == GovernanceStatus.VALIDATION

    def test_reject_approval_not_found(self, service: ModelGovernanceService):
        """Should return None for non-existent model."""
        assert service.reject_approval("fake", "x") is None

    def test_reject_no_pending(self, service: ModelGovernanceService):
        """Should return None when no pending approval exists."""
        model = service.register_model(
            name="No Pending Model",
            version="1.0.0",
            model_type=GovernedModelType.NLP,
            risk_tier=ModelRiskTier.TIER_3_LOW,
            owner="Test",
        )
        assert service.reject_approval(model.id, "x") is None

    def test_approve_no_pending(self, service: ModelGovernanceService):
        """Should return None when no pending approval exists."""
        model = service.register_model(
            name="No Pending Model 2",
            version="1.0.0",
            model_type=GovernedModelType.REGRESSION,
            risk_tier=ModelRiskTier.TIER_3_LOW,
            owner="Test",
        )
        assert service.approve_model(model.id, "Approver", role="ml_engineer") is None

    def test_approve_with_comments(self, service: ModelGovernanceService):
        """Approval comments should be captured."""
        model = service.register_model(
            name="Comment Model",
            version="1.0.0",
            model_type=GovernedModelType.CLASSIFICATION,
            risk_tier=ModelRiskTier.TIER_3_LOW,
            owner="Test",
        )
        service.submit_for_validation(model.id, ValidationType.TECHNICAL, "Tester")
        service.request_approval(model.id)
        result = service.approve_model(
            model.id, "Engineer", role="ml_engineer", comments="Looks good"
        )
        assert result is not None
        assert "Looks good" in result.comments

    def test_duplicate_role_approval_ignored(self, service: ModelGovernanceService):
        """Duplicate role approvals should not add extra entries."""
        model = service.register_model(
            name="Dup Role Model",
            version="1.0.0",
            model_type=GovernedModelType.CLASSIFICATION,
            risk_tier=ModelRiskTier.TIER_2_MEDIUM,
            owner="Test",
        )
        service.submit_for_validation(model.id, ValidationType.TECHNICAL, "Tester")
        service.request_approval(model.id)

        service.approve_model(model.id, "Engineer 1", role="ml_engineer")
        service.approve_model(model.id, "Engineer 2", role="ml_engineer")

        requests = service.get_approval_requests(model.id)
        pending = [r for r in requests if r.status == ApprovalStatus.PENDING]
        assert len(pending) == 1
        assert pending[0].approvals_received.count("ml_engineer") == 1

    def test_approval_request_sets_required_roles(self, service: ModelGovernanceService):
        """Approval request should set correct required roles based on tier."""
        model = service.register_model(
            name="Roles Model",
            version="1.0.0",
            model_type=GovernedModelType.CLASSIFICATION,
            risk_tier=ModelRiskTier.TIER_1_HIGH,
            owner="Test",
        )
        service.submit_for_validation(model.id, ValidationType.TECHNICAL, "Tester")
        request = service.request_approval(model.id)
        assert request is not None
        assert "clinical_lead" in request.approvers_required
        assert "regulatory_officer" in request.approvers_required
        assert "ml_engineer" in request.approvers_required

    def test_approval_sets_approved_by_and_date(self, service: ModelGovernanceService):
        """Full approval should set approved_by and approval_date on the model."""
        model = service.register_model(
            name="Approved By Model",
            version="1.0.0",
            model_type=GovernedModelType.REGRESSION,
            risk_tier=ModelRiskTier.TIER_3_LOW,
            owner="Test",
        )
        service.submit_for_validation(model.id, ValidationType.TECHNICAL, "T")
        service.request_approval(model.id)
        service.approve_model(model.id, "Final Approver", role="ml_engineer")

        updated = service.get_model(model.id)
        assert updated is not None
        assert updated.approved_by == "Final Approver"
        assert updated.approval_date is not None


# ============================================================================
# Monitoring Alert Tests
# ============================================================================


class TestMonitoringAlerts:
    """Tests for monitoring alert management."""

    def test_record_alert(self, service: ModelGovernanceService):
        """Should record a monitoring alert."""
        alert = service.record_monitoring_alert(
            model_id="gov-model-001",
            alert_type=AlertType.DRIFT,
            severity=AlertSeverity.HIGH,
            message="Significant drift detected",
        )
        assert alert is not None
        assert alert.alert_type == AlertType.DRIFT
        assert alert.severity == AlertSeverity.HIGH
        assert alert.acknowledged is False

    def test_record_alert_not_found(self, service: ModelGovernanceService):
        """Should return None for non-existent model."""
        assert service.record_monitoring_alert(
            "fake", AlertType.DRIFT, AlertSeverity.LOW, "test"
        ) is None

    def test_acknowledge_alert(self, service: ModelGovernanceService):
        """Should acknowledge an alert."""
        alert = service.record_monitoring_alert(
            "gov-model-001", AlertType.DRIFT, AlertSeverity.MEDIUM, "Drift"
        )
        assert alert is not None
        result = service.acknowledge_alert(alert.id)
        assert result is not None
        assert result.acknowledged is True

    def test_acknowledge_alert_not_found(self, service: ModelGovernanceService):
        """Should return None for non-existent alert."""
        assert service.acknowledge_alert("fake-alert") is None

    def test_resolve_alert(self, service: ModelGovernanceService):
        """Should resolve an alert with timestamp."""
        alert = service.record_monitoring_alert(
            "gov-model-001", AlertType.PERFORMANCE_DEGRADATION, AlertSeverity.HIGH, "Degraded"
        )
        assert alert is not None
        result = service.resolve_alert(alert.id)
        assert result is not None
        assert result.resolved_at is not None
        assert result.acknowledged is True

    def test_resolve_alert_not_found(self, service: ModelGovernanceService):
        """Should return None for non-existent alert."""
        assert service.resolve_alert("fake-alert") is None

    def test_get_alerts_all(self, service: ModelGovernanceService):
        """Should get all alerts across models."""
        alerts = service.get_alerts()
        assert len(alerts) >= 3  # seed alerts

    def test_get_alerts_by_model(self, service: ModelGovernanceService):
        """Should filter alerts by model ID."""
        alerts = service.get_alerts(model_id="gov-model-002")
        assert len(alerts) >= 1
        assert all(a.model_id == "gov-model-002" for a in alerts)

    def test_get_alerts_unresolved_only(self, service: ModelGovernanceService):
        """Should filter to unresolved alerts only."""
        alerts = service.get_alerts(unresolved_only=True)
        assert all(a.resolved_at is None for a in alerts)

    def test_get_alerts_sorted_by_time(self, service: ModelGovernanceService):
        """Alerts should be sorted by detected_at descending."""
        service.record_monitoring_alert(
            "gov-model-001", AlertType.DRIFT, AlertSeverity.LOW, "First"
        )
        service.record_monitoring_alert(
            "gov-model-001", AlertType.DRIFT, AlertSeverity.LOW, "Second"
        )
        alerts = service.get_alerts(model_id="gov-model-001")
        for i in range(len(alerts) - 1):
            assert alerts[i].detected_at >= alerts[i + 1].detected_at

    def test_record_all_alert_types(self, service: ModelGovernanceService):
        """Should handle all alert types."""
        for atype in AlertType:
            alert = service.record_monitoring_alert(
                "gov-model-001", atype, AlertSeverity.MEDIUM, f"Test {atype.value}"
            )
            assert alert is not None
            assert alert.alert_type == atype

    def test_record_all_severity_levels(self, service: ModelGovernanceService):
        """Should handle all severity levels."""
        for sev in AlertSeverity:
            alert = service.record_monitoring_alert(
                "gov-model-001", AlertType.DRIFT, sev, f"Test {sev.value}"
            )
            assert alert is not None
            assert alert.severity == sev


# ============================================================================
# Validation Record Tests
# ============================================================================


class TestValidationRecords:
    """Tests for validation record management."""

    def test_get_validations_seed(self, service: ModelGovernanceService):
        """Should retrieve seed validation records."""
        records = service.get_validations("gov-model-001")
        assert len(records) >= 2

    def test_get_validations_empty(self, service: ModelGovernanceService):
        """Should return empty list for model with no validations."""
        model = service.register_model(
            name="No Val Model",
            version="1.0.0",
            model_type=GovernedModelType.REGRESSION,
            risk_tier=ModelRiskTier.TIER_3_LOW,
            owner="Test",
        )
        records = service.get_validations(model.id)
        assert records == []

    def test_validation_record_fields(self, service: ModelGovernanceService):
        """Validation records should have all expected fields."""
        records = service.get_validations("gov-model-001")
        record = records[0]
        assert record.id is not None
        assert record.model_id == "gov-model-001"
        assert record.validator is not None
        assert record.date is not None
        assert isinstance(record.passed, bool)


# ============================================================================
# Overdue Reviews Tests
# ============================================================================


class TestOverdueReviews:
    """Tests for overdue review detection."""

    def test_overdue_reviews_from_seed(self, service: ModelGovernanceService):
        """Should detect overdue reviews from seed data."""
        overdue = service.get_overdue_reviews()
        assert len(overdue) >= 2  # gov-model-002 and gov-model-005
        names = {m.name for m in overdue}
        assert "Trial Eligibility Scorer" in names
        assert "OMOP Concept Mapper" in names

    def test_overdue_excludes_retired(self, service: ModelGovernanceService):
        """Retired models should not appear in overdue reviews."""
        service.retire_model("gov-model-002")
        overdue = service.get_overdue_reviews()
        ids = {m.id for m in overdue}
        assert "gov-model-002" not in ids

    def test_overdue_excludes_deprecated(self, service: ModelGovernanceService):
        """Deprecated models should not appear in overdue reviews."""
        service.deprecate_model("gov-model-005")
        overdue = service.get_overdue_reviews()
        ids = {m.id for m in overdue}
        assert "gov-model-005" not in ids

    def test_new_model_not_overdue(self, service: ModelGovernanceService):
        """Newly registered model should not be overdue."""
        model = service.register_model(
            name="Fresh Model",
            version="1.0.0",
            model_type=GovernedModelType.CLASSIFICATION,
            risk_tier=ModelRiskTier.TIER_3_LOW,
            owner="Test",
        )
        overdue = service.get_overdue_reviews()
        ids = {m.id for m in overdue}
        assert model.id not in ids


# ============================================================================
# Governance Metrics Tests
# ============================================================================


class TestGovernanceMetrics:
    """Tests for governance metrics calculation."""

    def test_metrics_total_models(self, service: ModelGovernanceService):
        """Total models should match seed count."""
        metrics = service.get_metrics()
        assert metrics.total_models == 8

    def test_metrics_by_tier(self, service: ModelGovernanceService):
        """Should break down models by tier."""
        metrics = service.get_metrics()
        assert ModelRiskTier.TIER_1_HIGH.value in metrics.by_tier
        assert ModelRiskTier.TIER_2_MEDIUM.value in metrics.by_tier
        assert ModelRiskTier.TIER_3_LOW.value in metrics.by_tier
        assert sum(metrics.by_tier.values()) == metrics.total_models

    def test_metrics_by_status(self, service: ModelGovernanceService):
        """Should break down models by status."""
        metrics = service.get_metrics()
        assert sum(metrics.by_status.values()) == metrics.total_models

    def test_metrics_pending_approvals(self, service: ModelGovernanceService):
        """Should count pending approvals."""
        metrics = service.get_metrics()
        assert metrics.pending_approvals >= 2  # seed has 2 pending

    def test_metrics_overdue_reviews(self, service: ModelGovernanceService):
        """Should count overdue reviews."""
        metrics = service.get_metrics()
        assert metrics.overdue_reviews >= 2

    def test_metrics_active_alerts(self, service: ModelGovernanceService):
        """Should count active (unresolved) alerts."""
        metrics = service.get_metrics()
        assert metrics.active_alerts >= 2  # seed has 2 unresolved

    def test_metrics_models_in_production(self, service: ModelGovernanceService):
        """Should count deployed + monitoring models."""
        metrics = service.get_metrics()
        assert metrics.models_in_production >= 4  # seed: deployed + monitoring

    def test_metrics_deprecated_count(self, service: ModelGovernanceService):
        """Should count deprecated models (initially 0)."""
        metrics = service.get_metrics()
        initial = metrics.deprecated_count
        service.deprecate_model("gov-model-001")
        updated = service.get_metrics()
        assert updated.deprecated_count == initial + 1


# ============================================================================
# Model History Tests
# ============================================================================


class TestModelHistory:
    """Tests for model history retrieval."""

    def test_history_includes_validations(self, service: ModelGovernanceService):
        """History should include validation records."""
        history = service.get_model_history("gov-model-001")
        assert history is not None
        assert len(history["validations"]) >= 2

    def test_history_includes_alerts(self, service: ModelGovernanceService):
        """History should include monitoring alerts."""
        history = service.get_model_history("gov-model-001")
        assert history is not None
        assert "alerts" in history

    def test_history_includes_approvals(self, service: ModelGovernanceService):
        """History should include approval requests."""
        history = service.get_model_history("gov-model-003")
        assert history is not None
        assert len(history["approval_requests"]) >= 1

    def test_history_not_found(self, service: ModelGovernanceService):
        """Should return None for non-existent model."""
        assert service.get_model_history("fake") is None

    def test_history_model_name(self, service: ModelGovernanceService):
        """History should include model name."""
        history = service.get_model_history("gov-model-001")
        assert history is not None
        assert history["model_name"] == "NLP Entity Extractor"


# ============================================================================
# Service Stats Tests
# ============================================================================


class TestServiceStats:
    """Tests for service statistics."""

    def test_stats_keys(self, service: ModelGovernanceService):
        """Stats should contain expected keys."""
        stats = service.get_stats()
        assert "total_models" in stats
        assert "pending_approvals" in stats
        assert "active_alerts" in stats
        assert "overdue_reviews" in stats
        assert "models_in_production" in stats

    def test_stats_values(self, service: ModelGovernanceService):
        """Stats values should match metrics."""
        stats = service.get_stats()
        assert stats["total_models"] == 8


# ============================================================================
# Singleton Tests
# ============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_singleton_returns_same_instance(self):
        """Should return the same service instance."""
        s1 = get_model_governance_service()
        s2 = get_model_governance_service()
        assert s1 is s2

    def test_reset_creates_new_instance(self):
        """Reset should create a fresh instance."""
        s1 = get_model_governance_service()
        reset_model_governance_service()
        s2 = get_model_governance_service()
        assert s1 is not s2

    def test_thread_safe_singleton(self):
        """Singleton should be thread-safe."""
        instances = []

        def create():
            instances.append(get_model_governance_service())

        threads = [threading.Thread(target=create) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(inst is instances[0] for inst in instances)


# ============================================================================
# API Endpoint Tests
# ============================================================================


class TestAPIEndpoints:
    """Tests for the REST API layer."""

    @pytest.mark.anyio
    async def test_list_models_api(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/model-governance/models")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 8
        assert len(data["models"]) == 8

    @pytest.mark.anyio
    async def test_list_models_filter_tier_api(self, client):
        async with client as ac:
            response = await ac.get(
                "/api/v1/model-governance/models",
                params={"risk_tier": "tier_1_high"},
            )
        assert response.status_code == 200
        data = response.json()
        assert all(m["risk_tier"] == "tier_1_high" for m in data["models"])

    @pytest.mark.anyio
    async def test_get_model_api(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/model-governance/models/gov-model-001")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "NLP Entity Extractor"

    @pytest.mark.anyio
    async def test_get_model_not_found_api(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/model-governance/models/nonexistent")
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_register_model_api(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/model-governance/models",
                json={
                    "name": "API Test Model",
                    "version": "1.0.0",
                    "model_type": "classification",
                    "risk_tier": "tier_3_low",
                    "owner": "API Tester",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "API Test Model"
        assert data["status"] == "development"

    @pytest.mark.anyio
    async def test_update_model_api(self, client):
        async with client as ac:
            response = await ac.patch(
                "/api/v1/model-governance/models/gov-model-001",
                json={"description": "Updated via API"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated via API"

    @pytest.mark.anyio
    async def test_update_model_not_found_api(self, client):
        async with client as ac:
            response = await ac.patch(
                "/api/v1/model-governance/models/nonexistent",
                json={"description": "test"},
            )
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_delete_model_api(self, client):
        async with client as ac:
            response = await ac.delete("/api/v1/model-governance/models/gov-model-008")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"

    @pytest.mark.anyio
    async def test_delete_model_not_found_api(self, client):
        async with client as ac:
            response = await ac.delete("/api/v1/model-governance/models/nonexistent")
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_submit_validation_api(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/model-governance/models/gov-model-006/validate",
                json={
                    "validation_type": "technical",
                    "validator": "API Tester",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["model_id"] == "gov-model-006"
        assert data["passed"] is True

    @pytest.mark.anyio
    async def test_submit_validation_not_found_api(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/model-governance/models/nonexistent/validate",
                json={"validation_type": "technical", "validator": "x"},
            )
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_request_approval_api(self, client):
        """Request approval for a model in VALIDATION status."""
        async with client as ac:
            response = await ac.post(
                "/api/v1/model-governance/models/gov-model-006/request-approval",
                params={"requested_by": "API Tester"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"

    @pytest.mark.anyio
    async def test_approve_model_api(self, client):
        """Approve a pending model."""
        async with client as ac:
            response = await ac.post(
                "/api/v1/model-governance/models/gov-model-003/approve",
                json={
                    "approver": "Dr. Smith",
                    "role": "clinical_lead",
                    "comments": "Approved via API",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert "clinical_lead" in data["approvals_received"]

    @pytest.mark.anyio
    async def test_reject_approval_api(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/model-governance/models/gov-model-007/reject",
                params={"rejector": "Reviewer", "reason": "Needs more work"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"

    @pytest.mark.anyio
    async def test_deploy_model_api(self, client):
        """Deploy needs an APPROVED model. Use seed model and fully approve first."""
        svc = get_model_governance_service()
        model = svc.register_model(
            name="Deploy API Model",
            version="1.0.0",
            model_type=GovernedModelType.REGRESSION,
            risk_tier=ModelRiskTier.TIER_3_LOW,
            owner="Test",
        )
        svc.submit_for_validation(model.id, ValidationType.TECHNICAL, "T")
        svc.request_approval(model.id)
        svc.approve_model(model.id, "A", role="ml_engineer")

        async with client as ac:
            response = await ac.post(
                f"/api/v1/model-governance/models/{model.id}/deploy"
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deployed"

    @pytest.mark.anyio
    async def test_deprecate_model_api(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/model-governance/models/gov-model-001/deprecate"
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deprecated"

    @pytest.mark.anyio
    async def test_retire_model_api(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/model-governance/models/gov-model-001/retire"
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "retired"

    @pytest.mark.anyio
    async def test_record_alert_api(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/model-governance/models/gov-model-001/alerts",
                json={
                    "alert_type": "drift",
                    "severity": "high",
                    "message": "API drift alert",
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["alert_type"] == "drift"
        assert data["severity"] == "high"

    @pytest.mark.anyio
    async def test_list_alerts_api(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/model-governance/alerts")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 3

    @pytest.mark.anyio
    async def test_list_alerts_filter_model_api(self, client):
        async with client as ac:
            response = await ac.get(
                "/api/v1/model-governance/alerts",
                params={"model_id": "gov-model-002"},
            )
        assert response.status_code == 200
        data = response.json()
        assert all(a["model_id"] == "gov-model-002" for a in data["alerts"])

    @pytest.mark.anyio
    async def test_acknowledge_alert_api(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/model-governance/alerts/alert-002/acknowledge"
            )
        assert response.status_code == 200
        data = response.json()
        assert data["acknowledged"] is True

    @pytest.mark.anyio
    async def test_resolve_alert_api(self, client):
        async with client as ac:
            response = await ac.post(
                "/api/v1/model-governance/alerts/alert-002/resolve"
            )
        assert response.status_code == 200
        data = response.json()
        assert data["resolved_at"] is not None

    @pytest.mark.anyio
    async def test_list_validations_api(self, client):
        async with client as ac:
            response = await ac.get(
                "/api/v1/model-governance/models/gov-model-001/validations"
            )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2

    @pytest.mark.anyio
    async def test_list_validations_not_found_api(self, client):
        async with client as ac:
            response = await ac.get(
                "/api/v1/model-governance/models/nonexistent/validations"
            )
        assert response.status_code == 404

    @pytest.mark.anyio
    async def test_list_approvals_api(self, client):
        async with client as ac:
            response = await ac.get(
                "/api/v1/model-governance/models/gov-model-003/approvals"
            )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_overdue_reviews_api(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/model-governance/overdue-reviews")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2

    @pytest.mark.anyio
    async def test_metrics_api(self, client):
        async with client as ac:
            response = await ac.get("/api/v1/model-governance/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["total_models"] == 8
        assert "by_tier" in data
        assert "by_status" in data
        assert "pending_approvals" in data

    @pytest.mark.anyio
    async def test_model_history_api(self, client):
        async with client as ac:
            response = await ac.get(
                "/api/v1/model-governance/models/gov-model-001/history"
            )
        assert response.status_code == 200
        data = response.json()
        assert data["model_name"] == "NLP Entity Extractor"
        assert "validations" in data
        assert "alerts" in data

    @pytest.mark.anyio
    async def test_model_history_not_found_api(self, client):
        async with client as ac:
            response = await ac.get(
                "/api/v1/model-governance/models/nonexistent/history"
            )
        assert response.status_code == 404
