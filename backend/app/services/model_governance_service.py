"""Model Governance & Lifecycle Management Service (VP-DS-8).

Provides a governance layer on top of the model registry for:
- Risk-tiered approval workflows
- Validation tracking (technical, clinical, regulatory)
- Model lifecycle management (dev -> validation -> approval -> deploy -> monitoring)
- Monitoring alerts (drift, performance degradation, fairness violations)
- Overdue review detection
- Governance metrics dashboard

This is a SEPARATE governance layer that complements the existing model_registry_service.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.schemas.model_governance import (
    AlertSeverity,
    AlertType,
    ApprovalStatus,
    GovernanceStatus,
    GovernedModel,
    GovernedModelType,
    ModelApprovalRequest,
    ModelGovernanceMetrics,
    ModelMonitoringAlert,
    ModelRiskTier,
    ModelValidationRecord,
    ValidationType,
)

logger = logging.getLogger(__name__)

# Tier-based approval requirements
TIER_APPROVAL_REQUIREMENTS: dict[ModelRiskTier, list[str]] = {
    ModelRiskTier.TIER_1_HIGH: ["clinical_lead", "regulatory_officer", "ml_engineer"],
    ModelRiskTier.TIER_2_MEDIUM: ["clinical_lead", "ml_engineer"],
    ModelRiskTier.TIER_3_LOW: ["ml_engineer"],
}


class ModelGovernanceService:
    """Service for ML model governance and lifecycle management."""

    def __init__(self) -> None:
        """Initialize the model governance service."""
        self._models: dict[str, GovernedModel] = {}
        self._validations: dict[str, list[ModelValidationRecord]] = {}
        self._approval_requests: dict[str, list[ModelApprovalRequest]] = {}
        self._alerts: dict[str, list[ModelMonitoringAlert]] = {}
        self._lock = threading.Lock()
        self._init_seed_data()

    # =========================================================================
    # Seed data
    # =========================================================================

    def _init_seed_data(self) -> None:
        """Pre-populate models, validations, approvals, and alerts."""
        now = datetime.now(timezone.utc)

        seed_models = [
            GovernedModel(
                id="gov-model-001",
                name="NLP Entity Extractor",
                version="2.3.1",
                description="Extracts clinical entities (conditions, medications, procedures) from clinical notes using transformer-based NER.",
                model_type=GovernedModelType.NLP,
                risk_tier=ModelRiskTier.TIER_1_HIGH,
                status=GovernanceStatus.DEPLOYED,
                owner="Dr. Sarah Chen",
                team="NLP Engineering",
                training_data_hash="sha256:abc123def456",
                performance_metrics={"f1": 0.94, "precision": 0.96, "recall": 0.92},
                fairness_metrics={"demographic_parity": 0.97, "equal_opportunity": 0.95},
                validation_date=now - timedelta(days=30),
                approved_by="Dr. James Wilson",
                approval_date=now - timedelta(days=25),
                deployment_date=now - timedelta(days=20),
                monitoring_config={"drift_threshold": 0.1, "alert_on_degradation": True},
                review_frequency_days=90,
                next_review_date=now + timedelta(days=60),
                created_at=now - timedelta(days=180),
                updated_at=now - timedelta(days=20),
            ),
            GovernedModel(
                id="gov-model-002",
                name="Trial Eligibility Scorer",
                version="1.5.0",
                description="Scores patient eligibility for clinical trials based on inclusion/exclusion criteria matching.",
                model_type=GovernedModelType.CLASSIFICATION,
                risk_tier=ModelRiskTier.TIER_1_HIGH,
                status=GovernanceStatus.MONITORING,
                owner="Dr. Michael Park",
                team="Clinical AI",
                training_data_hash="sha256:789ghi012jkl",
                performance_metrics={"auc": 0.91, "precision": 0.88, "recall": 0.85, "f1": 0.86},
                fairness_metrics={"demographic_parity": 0.93, "four_fifths_rule": True},
                validation_date=now - timedelta(days=45),
                approved_by="Dr. Emily Rodriguez",
                approval_date=now - timedelta(days=40),
                deployment_date=now - timedelta(days=35),
                monitoring_config={"drift_threshold": 0.08, "performance_floor": 0.80},
                review_frequency_days=60,
                next_review_date=now - timedelta(days=5),  # overdue
                created_at=now - timedelta(days=200),
                updated_at=now - timedelta(days=35),
            ),
            GovernedModel(
                id="gov-model-003",
                name="Risk Prediction Model",
                version="3.0.0",
                description="Predicts patient risk scores for adverse events using gradient-boosted trees.",
                model_type=GovernedModelType.ENSEMBLE,
                risk_tier=ModelRiskTier.TIER_1_HIGH,
                status=GovernanceStatus.PENDING_APPROVAL,
                owner="Dr. Lisa Wang",
                team="Predictive Analytics",
                training_data_hash="sha256:mno345pqr678",
                performance_metrics={"auc": 0.89, "precision": 0.85, "recall": 0.82},
                fairness_metrics={"demographic_parity": 0.91},
                validation_date=now - timedelta(days=10),
                review_frequency_days=90,
                next_review_date=now + timedelta(days=80),
                created_at=now - timedelta(days=120),
                updated_at=now - timedelta(days=10),
            ),
            GovernedModel(
                id="gov-model-004",
                name="Drug Interaction Classifier",
                version="1.2.0",
                description="Classifies potential drug-drug interactions from medication lists.",
                model_type=GovernedModelType.CLASSIFICATION,
                risk_tier=ModelRiskTier.TIER_2_MEDIUM,
                status=GovernanceStatus.DEPLOYED,
                owner="Dr. Robert Kim",
                team="Drug Safety",
                training_data_hash="sha256:stu901vwx234",
                performance_metrics={"accuracy": 0.93, "f1": 0.90},
                fairness_metrics={},
                validation_date=now - timedelta(days=60),
                approved_by="Dr. Sarah Chen",
                approval_date=now - timedelta(days=55),
                deployment_date=now - timedelta(days=50),
                monitoring_config={"alert_on_new_drug_class": True},
                review_frequency_days=120,
                next_review_date=now + timedelta(days=60),
                created_at=now - timedelta(days=250),
                updated_at=now - timedelta(days=50),
            ),
            GovernedModel(
                id="gov-model-005",
                name="OMOP Concept Mapper",
                version="4.1.2",
                description="Maps extracted clinical terms to OMOP standard vocabulary concepts using semantic similarity.",
                model_type=GovernedModelType.NLP,
                risk_tier=ModelRiskTier.TIER_2_MEDIUM,
                status=GovernanceStatus.MONITORING,
                owner="Alex Torres",
                team="Terminology",
                training_data_hash="sha256:yza567bcd890",
                performance_metrics={"top_1_accuracy": 0.87, "top_5_accuracy": 0.96},
                fairness_metrics={},
                validation_date=now - timedelta(days=90),
                approved_by="Dr. James Wilson",
                approval_date=now - timedelta(days=85),
                deployment_date=now - timedelta(days=80),
                review_frequency_days=90,
                next_review_date=now - timedelta(days=1),  # overdue
                created_at=now - timedelta(days=300),
                updated_at=now - timedelta(days=80),
            ),
            GovernedModel(
                id="gov-model-006",
                name="Patient Similarity Engine",
                version="1.0.0",
                description="Computes patient similarity scores for cohort identification and trial matching.",
                model_type=GovernedModelType.REGRESSION,
                risk_tier=ModelRiskTier.TIER_2_MEDIUM,
                status=GovernanceStatus.VALIDATION,
                owner="Dr. Nina Patel",
                team="Clinical AI",
                training_data_hash="sha256:efg123hij456",
                performance_metrics={"mae": 0.12, "r2": 0.78},
                fairness_metrics={},
                validation_date=now - timedelta(days=5),
                review_frequency_days=90,
                next_review_date=now + timedelta(days=85),
                created_at=now - timedelta(days=60),
                updated_at=now - timedelta(days=5),
            ),
            GovernedModel(
                id="gov-model-007",
                name="Adverse Event Detector",
                version="2.0.0",
                description="Detects potential adverse events from clinical notes and lab results.",
                model_type=GovernedModelType.CLASSIFICATION,
                risk_tier=ModelRiskTier.TIER_1_HIGH,
                status=GovernanceStatus.PENDING_APPROVAL,
                owner="Dr. Karen Hughes",
                team="Drug Safety",
                training_data_hash="sha256:klm789nop012",
                performance_metrics={"auc": 0.92, "sensitivity": 0.95, "specificity": 0.88},
                fairness_metrics={"demographic_parity": 0.94},
                validation_date=now - timedelta(days=7),
                review_frequency_days=60,
                next_review_date=now + timedelta(days=53),
                created_at=now - timedelta(days=90),
                updated_at=now - timedelta(days=7),
            ),
            GovernedModel(
                id="gov-model-008",
                name="Internal Analytics Dashboard Model",
                version="1.1.0",
                description="Powers internal analytics dashboards with patient volume forecasting.",
                model_type=GovernedModelType.REGRESSION,
                risk_tier=ModelRiskTier.TIER_3_LOW,
                status=GovernanceStatus.DEPLOYED,
                owner="Data Team",
                team="Analytics",
                training_data_hash="sha256:qrs345tuv678",
                performance_metrics={"mae": 5.2, "r2": 0.85},
                fairness_metrics={},
                validation_date=now - timedelta(days=30),
                approved_by="Alex Torres",
                approval_date=now - timedelta(days=28),
                deployment_date=now - timedelta(days=25),
                review_frequency_days=180,
                next_review_date=now + timedelta(days=150),
                created_at=now - timedelta(days=100),
                updated_at=now - timedelta(days=25),
            ),
        ]

        for model in seed_models:
            self._models[model.id] = model
            self._validations[model.id] = []
            self._approval_requests[model.id] = []
            self._alerts[model.id] = []

        # Seed validation records
        self._validations["gov-model-001"].extend([
            ModelValidationRecord(
                id="val-001",
                model_id="gov-model-001",
                validation_type=ValidationType.TECHNICAL,
                validator="ML Engineering Team",
                date=now - timedelta(days=35),
                passed=True,
                metrics={"f1": 0.94, "latency_p99_ms": 45},
                findings=["Model meets all technical benchmarks"],
                recommendations=[],
            ),
            ModelValidationRecord(
                id="val-002",
                model_id="gov-model-001",
                validation_type=ValidationType.CLINICAL,
                validator="Dr. James Wilson",
                date=now - timedelta(days=32),
                passed=True,
                metrics={"clinical_accuracy": 0.96},
                findings=["Reviewed 200 clinical cases", "Entity extraction aligns with clinical expectations"],
                recommendations=["Consider adding rare disease entity types"],
            ),
        ])

        self._validations["gov-model-003"].append(
            ModelValidationRecord(
                id="val-003",
                model_id="gov-model-003",
                validation_type=ValidationType.TECHNICAL,
                validator="Predictive Analytics Team",
                date=now - timedelta(days=10),
                passed=True,
                metrics={"auc": 0.89, "calibration_error": 0.03},
                findings=["Model technically validated"],
                recommendations=["Run clinical validation before deployment"],
            ),
        )

        # Seed approval requests (pending)
        self._approval_requests["gov-model-003"].append(
            ModelApprovalRequest(
                id="apr-001",
                model_id="gov-model-003",
                requested_by="Dr. Lisa Wang",
                request_date=now - timedelta(days=8),
                approvers_required=["clinical_lead", "regulatory_officer", "ml_engineer"],
                approvals_received=["ml_engineer"],
                status=ApprovalStatus.PENDING,
                comments="Technical validation passed. Awaiting clinical and regulatory approval.",
            ),
        )

        self._approval_requests["gov-model-007"].append(
            ModelApprovalRequest(
                id="apr-002",
                model_id="gov-model-007",
                requested_by="Dr. Karen Hughes",
                request_date=now - timedelta(days=5),
                approvers_required=["clinical_lead", "regulatory_officer", "ml_engineer"],
                approvals_received=[],
                status=ApprovalStatus.PENDING,
                comments="All validations passed. Ready for approval review.",
            ),
        )

        # Seed monitoring alerts
        self._alerts["gov-model-002"].append(
            ModelMonitoringAlert(
                id="alert-001",
                model_id="gov-model-002",
                alert_type=AlertType.DRIFT,
                severity=AlertSeverity.MEDIUM,
                message="Feature drift detected in patient age distribution (PSI=0.18).",
                detected_at=now - timedelta(days=3),
                acknowledged=True,
                resolved_at=None,
            ),
        )

        self._alerts["gov-model-005"].append(
            ModelMonitoringAlert(
                id="alert-002",
                model_id="gov-model-005",
                alert_type=AlertType.PERFORMANCE_DEGRADATION,
                severity=AlertSeverity.HIGH,
                message="Top-1 accuracy dropped from 0.87 to 0.81 over the last 7 days.",
                detected_at=now - timedelta(days=1),
                acknowledged=False,
                resolved_at=None,
            ),
        )

        self._alerts["gov-model-001"].append(
            ModelMonitoringAlert(
                id="alert-003",
                model_id="gov-model-001",
                alert_type=AlertType.DATA_QUALITY,
                severity=AlertSeverity.LOW,
                message="3% of input documents missing section headers - may affect extraction quality.",
                detected_at=now - timedelta(days=10),
                acknowledged=True,
                resolved_at=now - timedelta(days=8),
            ),
        )

        logger.info(
            f"Model governance initialized with {len(self._models)} models, "
            f"validation records, pending approvals, and monitoring alerts."
        )

    # =========================================================================
    # CRUD operations
    # =========================================================================

    def register_model(
        self,
        name: str,
        version: str,
        model_type: GovernedModelType,
        risk_tier: ModelRiskTier,
        owner: str,
        description: str = "",
        team: str = "",
        training_data_hash: str = "",
        performance_metrics: dict[str, Any] | None = None,
        fairness_metrics: dict[str, Any] | None = None,
        review_frequency_days: int = 90,
    ) -> GovernedModel:
        """Register a new model under governance."""
        now = datetime.now(timezone.utc)
        model_id = f"gov-model-{uuid4().hex[:8]}"

        model = GovernedModel(
            id=model_id,
            name=name,
            version=version,
            description=description,
            model_type=model_type,
            risk_tier=risk_tier,
            status=GovernanceStatus.DEVELOPMENT,
            owner=owner,
            team=team,
            training_data_hash=training_data_hash,
            performance_metrics=performance_metrics or {},
            fairness_metrics=fairness_metrics or {},
            review_frequency_days=review_frequency_days,
            next_review_date=now + timedelta(days=review_frequency_days),
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            self._models[model_id] = model
            self._validations[model_id] = []
            self._approval_requests[model_id] = []
            self._alerts[model_id] = []

        logger.info(f"Registered governed model: {name} v{version} ({model_id})")
        return model

    def get_model(self, model_id: str) -> GovernedModel | None:
        """Get a governed model by ID."""
        return self._models.get(model_id)

    def list_models(
        self,
        risk_tier: ModelRiskTier | None = None,
        status: GovernanceStatus | None = None,
        limit: int = 100,
    ) -> list[GovernedModel]:
        """List governed models with optional filtering."""
        models = list(self._models.values())

        if risk_tier is not None:
            models = [m for m in models if m.risk_tier == risk_tier]

        if status is not None:
            models = [m for m in models if m.status == status]

        models.sort(key=lambda m: m.updated_at, reverse=True)
        return models[:limit]

    def update_model(self, model_id: str, **kwargs: Any) -> GovernedModel | None:
        """Update a governed model's mutable fields."""
        with self._lock:
            model = self._models.get(model_id)
            if model is None:
                return None

            allowed_fields = {
                "description", "performance_metrics", "fairness_metrics",
                "monitoring_config", "review_frequency_days",
            }

            for field_name, value in kwargs.items():
                if field_name in allowed_fields and value is not None:
                    setattr(model, field_name, value)

            model.updated_at = datetime.now(timezone.utc)
            return model

    def delete_model(self, model_id: str) -> bool:
        """Delete a governed model and all associated records."""
        with self._lock:
            if model_id not in self._models:
                return False
            del self._models[model_id]
            self._validations.pop(model_id, None)
            self._approval_requests.pop(model_id, None)
            self._alerts.pop(model_id, None)
            logger.info(f"Deleted governed model: {model_id}")
            return True

    # =========================================================================
    # Lifecycle transitions
    # =========================================================================

    def submit_for_validation(
        self,
        model_id: str,
        validation_type: ValidationType,
        validator: str,
    ) -> ModelValidationRecord | None:
        """Submit a model for validation and record the result."""
        with self._lock:
            model = self._models.get(model_id)
            if model is None:
                return None

            now = datetime.now(timezone.utc)
            record = ModelValidationRecord(
                id=f"val-{uuid4().hex[:8]}",
                model_id=model_id,
                validation_type=validation_type,
                validator=validator,
                date=now,
                passed=True,
                metrics=dict(model.performance_metrics),
                findings=[f"{validation_type.value} validation completed by {validator}"],
                recommendations=[],
            )

            self._validations.setdefault(model_id, []).append(record)

            # Transition to VALIDATION if in DEVELOPMENT
            if model.status == GovernanceStatus.DEVELOPMENT:
                model.status = GovernanceStatus.VALIDATION
            model.validation_date = now
            model.updated_at = now

            logger.info(
                f"Model {model.name} submitted for {validation_type.value} validation by {validator}"
            )
            return record

    def request_approval(self, model_id: str, requested_by: str = "") -> ModelApprovalRequest | None:
        """Request approval for a model to progress to APPROVED status."""
        with self._lock:
            model = self._models.get(model_id)
            if model is None:
                return None

            if model.status not in (GovernanceStatus.VALIDATION, GovernanceStatus.PENDING_APPROVAL):
                return None

            now = datetime.now(timezone.utc)
            required_roles = list(TIER_APPROVAL_REQUIREMENTS.get(
                model.risk_tier, ["ml_engineer"]
            ))

            request = ModelApprovalRequest(
                id=f"apr-{uuid4().hex[:8]}",
                model_id=model_id,
                requested_by=requested_by or model.owner,
                request_date=now,
                approvers_required=required_roles,
                approvals_received=[],
                status=ApprovalStatus.PENDING,
                comments="",
            )

            self._approval_requests.setdefault(model_id, []).append(request)
            model.status = GovernanceStatus.PENDING_APPROVAL
            model.updated_at = now

            logger.info(
                f"Approval requested for model {model.name} - requires {len(required_roles)} approvals"
            )
            return request

    def approve_model(
        self,
        model_id: str,
        approver: str,
        role: str = "reviewer",
        comments: str = "",
    ) -> ModelApprovalRequest | None:
        """Record an approval for a model. Auto-approves when all required roles are met."""
        with self._lock:
            model = self._models.get(model_id)
            if model is None:
                return None

            # Find the latest pending request
            requests = self._approval_requests.get(model_id, [])
            pending = [r for r in requests if r.status == ApprovalStatus.PENDING]
            if not pending:
                return None

            request = pending[-1]

            # Add approval if role is required and not yet received
            if role in request.approvers_required and role not in request.approvals_received:
                request.approvals_received.append(role)

            if comments:
                request.comments = (
                    f"{request.comments}\n{approver} ({role}): {comments}".strip()
                )

            now = datetime.now(timezone.utc)

            # Check if all required approvals are met
            if all(r in request.approvals_received for r in request.approvers_required):
                request.status = ApprovalStatus.APPROVED
                model.status = GovernanceStatus.APPROVED
                model.approved_by = approver
                model.approval_date = now

            model.updated_at = now

            logger.info(
                f"Model {model.name} approved by {approver} ({role}) - "
                f"{len(request.approvals_received)}/{len(request.approvers_required)} approvals"
            )
            return request

    def reject_approval(
        self,
        model_id: str,
        rejector: str,
        reason: str = "",
    ) -> ModelApprovalRequest | None:
        """Reject a pending approval request."""
        with self._lock:
            model = self._models.get(model_id)
            if model is None:
                return None

            requests = self._approval_requests.get(model_id, [])
            pending = [r for r in requests if r.status == ApprovalStatus.PENDING]
            if not pending:
                return None

            request = pending[-1]
            request.status = ApprovalStatus.REJECTED
            request.comments = (
                f"{request.comments}\nREJECTED by {rejector}: {reason}".strip()
            )

            model.status = GovernanceStatus.VALIDATION
            model.updated_at = datetime.now(timezone.utc)

            logger.info(f"Approval rejected for model {model.name} by {rejector}")
            return request

    def deploy_model(self, model_id: str) -> GovernedModel | None:
        """Deploy an approved model."""
        with self._lock:
            model = self._models.get(model_id)
            if model is None:
                return None

            if model.status != GovernanceStatus.APPROVED:
                return None

            now = datetime.now(timezone.utc)
            model.status = GovernanceStatus.DEPLOYED
            model.deployment_date = now
            model.updated_at = now

            logger.info(f"Model {model.name} deployed")
            return model

    def deprecate_model(self, model_id: str) -> GovernedModel | None:
        """Deprecate a model."""
        with self._lock:
            model = self._models.get(model_id)
            if model is None:
                return None

            model.status = GovernanceStatus.DEPRECATED
            model.updated_at = datetime.now(timezone.utc)

            logger.info(f"Model {model.name} deprecated")
            return model

    def retire_model(self, model_id: str) -> GovernedModel | None:
        """Retire a model (final lifecycle stage)."""
        with self._lock:
            model = self._models.get(model_id)
            if model is None:
                return None

            model.status = GovernanceStatus.RETIRED
            model.updated_at = datetime.now(timezone.utc)

            logger.info(f"Model {model.name} retired")
            return model

    # =========================================================================
    # Monitoring alerts
    # =========================================================================

    def record_monitoring_alert(
        self,
        model_id: str,
        alert_type: AlertType,
        severity: AlertSeverity,
        message: str,
    ) -> ModelMonitoringAlert | None:
        """Record a monitoring alert for a model."""
        with self._lock:
            if model_id not in self._models:
                return None

            alert = ModelMonitoringAlert(
                id=f"alert-{uuid4().hex[:8]}",
                model_id=model_id,
                alert_type=alert_type,
                severity=severity,
                message=message,
                detected_at=datetime.now(timezone.utc),
                acknowledged=False,
                resolved_at=None,
            )

            self._alerts.setdefault(model_id, []).append(alert)
            logger.info(f"Alert recorded for model {model_id}: {alert_type.value} ({severity.value})")
            return alert

    def acknowledge_alert(self, alert_id: str) -> ModelMonitoringAlert | None:
        """Acknowledge a monitoring alert."""
        with self._lock:
            for alerts in self._alerts.values():
                for alert in alerts:
                    if alert.id == alert_id:
                        alert.acknowledged = True
                        return alert
        return None

    def resolve_alert(self, alert_id: str) -> ModelMonitoringAlert | None:
        """Resolve a monitoring alert."""
        with self._lock:
            for alerts in self._alerts.values():
                for alert in alerts:
                    if alert.id == alert_id:
                        alert.acknowledged = True
                        alert.resolved_at = datetime.now(timezone.utc)
                        return alert
        return None

    def get_alerts(
        self,
        model_id: str | None = None,
        unresolved_only: bool = False,
    ) -> list[ModelMonitoringAlert]:
        """Get monitoring alerts, optionally filtered."""
        if model_id:
            alerts = list(self._alerts.get(model_id, []))
        else:
            alerts = [a for al in self._alerts.values() for a in al]

        if unresolved_only:
            alerts = [a for a in alerts if a.resolved_at is None]

        alerts.sort(key=lambda a: a.detected_at, reverse=True)
        return alerts

    # =========================================================================
    # Validation records
    # =========================================================================

    def get_validations(self, model_id: str) -> list[ModelValidationRecord]:
        """Get all validation records for a model."""
        return list(self._validations.get(model_id, []))

    def get_approval_requests(self, model_id: str) -> list[ModelApprovalRequest]:
        """Get all approval requests for a model."""
        return list(self._approval_requests.get(model_id, []))

    # =========================================================================
    # Queries and reporting
    # =========================================================================

    def get_overdue_reviews(self) -> list[GovernedModel]:
        """Get models with overdue reviews."""
        now = datetime.now(timezone.utc)
        overdue = []
        for model in self._models.values():
            if (
                model.next_review_date is not None
                and model.next_review_date < now
                and model.status not in (GovernanceStatus.RETIRED, GovernanceStatus.DEPRECATED)
            ):
                overdue.append(model)
        overdue.sort(key=lambda m: m.next_review_date or now)
        return overdue

    def get_model_history(self, model_id: str) -> dict[str, Any] | None:
        """Get complete history for a model (validations + alerts + approvals)."""
        model = self._models.get(model_id)
        if model is None:
            return None

        return {
            "model_id": model_id,
            "model_name": model.name,
            "validations": list(self._validations.get(model_id, [])),
            "alerts": list(self._alerts.get(model_id, [])),
            "approval_requests": list(self._approval_requests.get(model_id, [])),
        }

    def get_metrics(self) -> ModelGovernanceMetrics:
        """Get aggregated governance metrics."""
        models = list(self._models.values())
        now = datetime.now(timezone.utc)

        by_tier: dict[str, int] = {}
        by_status: dict[str, int] = {}

        for model in models:
            tier_key = model.risk_tier.value
            by_tier[tier_key] = by_tier.get(tier_key, 0) + 1

            status_key = model.status.value
            by_status[status_key] = by_status.get(status_key, 0) + 1

        # Count pending approvals
        pending_count = 0
        for req_list in self._approval_requests.values():
            pending_count += sum(1 for r in req_list if r.status == ApprovalStatus.PENDING)

        # Count overdue reviews
        overdue_count = len(self.get_overdue_reviews())

        # Count active (unresolved) alerts
        active_alerts = sum(
            1
            for al in self._alerts.values()
            for a in al
            if a.resolved_at is None
        )

        # Calculate average time to approval
        approval_times: list[float] = []
        for req_list in self._approval_requests.values():
            for req in req_list:
                if req.status == ApprovalStatus.APPROVED:
                    model = self._models.get(req.model_id)
                    if model and model.approval_date:
                        delta = (model.approval_date - req.request_date).total_seconds()
                        approval_times.append(delta / 86400.0)  # convert to days

        avg_approval = (
            sum(approval_times) / len(approval_times)
            if approval_times
            else 0.0
        )

        # Count production models (deployed + monitoring)
        prod_statuses = {GovernanceStatus.DEPLOYED, GovernanceStatus.MONITORING}
        models_in_prod = sum(1 for m in models if m.status in prod_statuses)

        deprecated_count = sum(
            1 for m in models if m.status == GovernanceStatus.DEPRECATED
        )

        return ModelGovernanceMetrics(
            total_models=len(models),
            by_tier=by_tier,
            by_status=by_status,
            pending_approvals=pending_count,
            overdue_reviews=overdue_count,
            active_alerts=active_alerts,
            avg_time_to_approval_days=round(avg_approval, 2),
            models_in_production=models_in_prod,
            deprecated_count=deprecated_count,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics (for health endpoint compatibility)."""
        metrics = self.get_metrics()
        return {
            "total_models": metrics.total_models,
            "pending_approvals": metrics.pending_approvals,
            "active_alerts": metrics.active_alerts,
            "overdue_reviews": metrics.overdue_reviews,
            "models_in_production": metrics.models_in_production,
        }


# ============================================================================
# Singleton
# ============================================================================

_model_governance_service: ModelGovernanceService | None = None
_model_governance_lock = threading.Lock()


def get_model_governance_service() -> ModelGovernanceService:
    """Get the singleton ModelGovernanceService instance."""
    global _model_governance_service

    if _model_governance_service is None:
        with _model_governance_lock:
            if _model_governance_service is None:
                logger.info("Creating singleton ModelGovernanceService instance")
                _model_governance_service = ModelGovernanceService()

    return _model_governance_service


def reset_model_governance_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _model_governance_service
    with _model_governance_lock:
        _model_governance_service = None
