"""Change Control and Configuration Management service.

VP-Quality-4: Provides formal change request lifecycle management, approval
workflows based on risk level, configuration baseline management, and
configuration drift detection.

Usage:
    from app.services.change_control_service import get_change_control_service

    service = get_change_control_service()
    change = service.create_change_request(
        title="Add new screening criterion",
        description="Add HbA1c threshold for diabetes trial",
        change_type=ChangeType.ENHANCEMENT,
        risk_level=RiskLevel.MEDIUM,
        requester="clinical-ops-lead",
    )
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas.change_control import (
    ApprovalRecord,
    ApproverRole,
    BaselineListResponse,
    ChangeMetrics,
    ChangeStatus,
    ChangeType,
    ConfigurationBaseline,
    ConfigurationItem,
    DriftItem,
    DriftReport,
    ImpactAssessment,
    RiskLevel,
)

logger = logging.getLogger(__name__)

# Singleton instance and lock
_change_control_instance: ChangeControlService | None = None
_change_control_lock = Lock()


# ---------------------------------------------------------------------------
# Valid change status transitions
# ---------------------------------------------------------------------------

VALID_CHANGE_TRANSITIONS: dict[ChangeStatus, list[ChangeStatus]] = {
    ChangeStatus.DRAFT: [ChangeStatus.SUBMITTED, ChangeStatus.REJECTED],
    ChangeStatus.SUBMITTED: [
        ChangeStatus.IMPACT_ASSESSED,
        ChangeStatus.REJECTED,
        ChangeStatus.DRAFT,
    ],
    ChangeStatus.IMPACT_ASSESSED: [
        ChangeStatus.APPROVED,
        ChangeStatus.REJECTED,
        ChangeStatus.SUBMITTED,
    ],
    ChangeStatus.APPROVED: [
        ChangeStatus.SCHEDULED,
        ChangeStatus.IN_PROGRESS,
        ChangeStatus.REJECTED,
    ],
    ChangeStatus.SCHEDULED: [
        ChangeStatus.IN_PROGRESS,
        ChangeStatus.APPROVED,
    ],
    ChangeStatus.IN_PROGRESS: [
        ChangeStatus.TESTING,
        ChangeStatus.ROLLED_BACK,
    ],
    ChangeStatus.TESTING: [
        ChangeStatus.DEPLOYED,
        ChangeStatus.IN_PROGRESS,
        ChangeStatus.ROLLED_BACK,
    ],
    ChangeStatus.DEPLOYED: [
        ChangeStatus.VERIFIED,
        ChangeStatus.ROLLED_BACK,
    ],
    ChangeStatus.VERIFIED: [ChangeStatus.CLOSED],
    ChangeStatus.CLOSED: [],  # Terminal
    ChangeStatus.REJECTED: [],  # Terminal
    ChangeStatus.ROLLED_BACK: [ChangeStatus.CLOSED, ChangeStatus.DRAFT],
}

# Approval requirements by risk level
APPROVAL_REQUIREMENTS: dict[RiskLevel, list[ApproverRole]] = {
    RiskLevel.LOW: [ApproverRole.TEAM_LEAD],
    RiskLevel.MEDIUM: [ApproverRole.TEAM_LEAD, ApproverRole.QA],
    RiskLevel.HIGH: [ApproverRole.TEAM_LEAD, ApproverRole.QA, ApproverRole.COMPLIANCE],
    RiskLevel.CRITICAL: [
        ApproverRole.TEAM_LEAD,
        ApproverRole.QA,
        ApproverRole.COMPLIANCE,
        ApproverRole.EXECUTIVE,
    ],
}


# ---------------------------------------------------------------------------
# Change request record model
# ---------------------------------------------------------------------------


class ChangeRecord(BaseModel):
    """Internal change request record."""

    id: str = Field(default_factory=lambda: f"CHG-{uuid4().hex[:8].upper()}")
    title: str
    description: str
    change_type: ChangeType
    risk_level: RiskLevel
    requester: str
    assigned_to: str | None = None
    status: ChangeStatus = ChangeStatus.DRAFT
    impact_assessment: ImpactAssessment | None = None
    rollback_plan: str | None = None
    testing_requirements: str | None = None
    approval_chain: list[ApprovalRecord] = Field(default_factory=list)
    required_approvals: int = 1
    current_approvals: int = 0
    scheduled_date: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deployed_at: datetime | None = None
    closed_at: datetime | None = None
    rolled_back_at: datetime | None = None


# ---------------------------------------------------------------------------
# ChangeControlService
# ---------------------------------------------------------------------------


class ChangeControlService:
    """Service for managing change requests and configuration baselines.

    Uses in-memory storage with thread-safe access.
    Production deployments should persist to the database.
    """

    def __init__(self) -> None:
        """Initialize the change control service."""
        self._changes: dict[str, ChangeRecord] = {}
        self._baselines: dict[str, ConfigurationBaseline] = {}
        self._current_config: dict[str, ConfigurationItem] = {}
        self._lock = Lock()
        self._seed_config_items()
        self._seed_examples()
        logger.info(
            "ChangeControlService initialized with %d changes, %d baselines",
            len(self._changes),
            len(self._baselines),
        )

    # -------------------------------------------------------------------
    # Seeding
    # -------------------------------------------------------------------

    def _seed_config_items(self) -> None:
        """Populate current configuration items for drift detection."""
        items = [
            ConfigurationItem(
                key="DATABASE_POOL_SIZE",
                value="20",
                category="env_var",
                description="PostgreSQL connection pool size",
            ),
            ConfigurationItem(
                key="REDIS_MAX_CONNECTIONS",
                value="50",
                category="env_var",
                description="Redis maximum connections",
            ),
            ConfigurationItem(
                key="NLP_MODEL_VERSION",
                value="2.4.1",
                category="service_version",
                description="Active NLP model version",
            ),
            ConfigurationItem(
                key="FHIR_VALIDATION_ENABLED",
                value="true",
                category="feature_flag",
                description="Enable FHIR resource validation on import",
            ),
            ConfigurationItem(
                key="SCREENING_AUTO_APPROVE",
                value="false",
                category="feature_flag",
                description="Auto-approve low-risk screening matches",
            ),
            ConfigurationItem(
                key="MAX_CONCURRENT_SCREENINGS",
                value="100",
                category="setting",
                description="Maximum concurrent screening jobs",
            ),
            ConfigurationItem(
                key="AUDIT_LOG_RETENTION_DAYS",
                value="365",
                category="setting",
                description="Audit log retention period in days",
            ),
            ConfigurationItem(
                key="API_RATE_LIMIT_PER_MINUTE",
                value="120",
                category="setting",
                description="API rate limit per minute per user",
            ),
            ConfigurationItem(
                key="OMOP_CDM_VERSION",
                value="5.4",
                category="service_version",
                description="OMOP CDM version in use",
            ),
            ConfigurationItem(
                key="ENCRYPTION_ALGORITHM",
                value="AES-256-GCM",
                category="setting",
                description="PHI encryption algorithm",
                sensitive=True,
            ),
        ]
        for item in items:
            self._current_config[item.key] = item

    def _seed_examples(self) -> None:
        """Pre-populate sample change requests and baseline."""
        now = datetime.now(timezone.utc)

        # --- Sample change requests ---
        examples = [
            ChangeRecord(
                id="CHG-001",
                title="Add HbA1c screening criterion for REGEN-DM-042 trial",
                description=(
                    "Add glycated hemoglobin (HbA1c) threshold as an inclusion "
                    "criterion for the Regeneron diabetes trial REGEN-DM-042. "
                    "Patients must have HbA1c >= 7.0% and <= 10.0% to qualify."
                ),
                change_type=ChangeType.ENHANCEMENT,
                risk_level=RiskLevel.MEDIUM,
                requester="clinical-ops-lead",
                assigned_to="screening-engineer",
                status=ChangeStatus.APPROVED,
                impact_assessment=ImpactAssessment(
                    affected_systems=["screening-engine", "criteria-parser", "patient-matching"],
                    patient_data_impact=True,
                    phi_details="Reads lab results containing PHI to evaluate HbA1c values",
                    regulatory_impact=False,
                    performance_impact="Minimal - adds one additional criterion check per patient",
                    rollback_complexity="LOW",
                    estimated_downtime_minutes=0,
                ),
                rollback_plan="Remove HbA1c criterion from trial config and re-run affected screenings",
                testing_requirements="Unit tests for criterion parser, integration test with sample patients",
                approval_chain=[
                    ApprovalRecord(
                        approver="eng-team-lead",
                        role=ApproverRole.TEAM_LEAD,
                        decision="APPROVED",
                        comment="Criterion well-defined, low risk",
                        decided_at=now - timedelta(days=2),
                    ),
                    ApprovalRecord(
                        approver="qa-manager",
                        role=ApproverRole.QA,
                        decision="APPROVED",
                        comment="Test plan adequate",
                        decided_at=now - timedelta(days=1),
                    ),
                ],
                required_approvals=2,
                current_approvals=2,
                created_at=now - timedelta(days=5),
                updated_at=now - timedelta(days=1),
            ),
            ChangeRecord(
                id="CHG-002",
                title="Fix race condition in concurrent screening job processing",
                description=(
                    "Under high load, concurrent screening jobs can produce duplicate "
                    "ScreeningResult records for the same patient-trial pair. Fix requires "
                    "adding a database-level unique constraint and optimistic locking."
                ),
                change_type=ChangeType.BUG_FIX,
                risk_level=RiskLevel.HIGH,
                requester="platform-engineer",
                assigned_to="backend-lead",
                status=ChangeStatus.IN_PROGRESS,
                impact_assessment=ImpactAssessment(
                    affected_systems=["screening-engine", "job-queue", "database"],
                    patient_data_impact=True,
                    phi_details="Screening results contain patient identifiers",
                    regulatory_impact=True,
                    regulatory_details="Data integrity fix - requires regression validation",
                    performance_impact="Slight increase in per-job latency due to locking",
                    rollback_complexity="MEDIUM",
                    estimated_downtime_minutes=5,
                ),
                rollback_plan="Revert migration, remove unique constraint, deploy previous version",
                testing_requirements="Load test with 200 concurrent jobs, verify no duplicates",
                approval_chain=[
                    ApprovalRecord(
                        approver="eng-team-lead",
                        role=ApproverRole.TEAM_LEAD,
                        decision="APPROVED",
                        comment="Critical fix needed",
                        decided_at=now - timedelta(days=3),
                    ),
                    ApprovalRecord(
                        approver="qa-manager",
                        role=ApproverRole.QA,
                        decision="APPROVED",
                        comment="Load test plan approved",
                        decided_at=now - timedelta(days=2),
                    ),
                    ApprovalRecord(
                        approver="compliance-officer",
                        role=ApproverRole.COMPLIANCE,
                        decision="APPROVED",
                        comment="Data integrity is regulatory requirement",
                        decided_at=now - timedelta(days=1),
                    ),
                ],
                required_approvals=3,
                current_approvals=3,
                created_at=now - timedelta(days=7),
                updated_at=now - timedelta(hours=6),
            ),
            ChangeRecord(
                id="CHG-003",
                title="Update NLP model from v2.3.0 to v2.4.1",
                description=(
                    "Upgrade the NLP extraction model to version 2.4.1 which includes "
                    "improved medication route detection and abbreviation expansion. "
                    "This addresses CAPA-001 (NLP false negatives for diabetes)."
                ),
                change_type=ChangeType.CONFIGURATION,
                risk_level=RiskLevel.LOW,
                requester="nlp-team-lead",
                assigned_to="ml-engineer",
                status=ChangeStatus.DEPLOYED,
                impact_assessment=ImpactAssessment(
                    affected_systems=["nlp-pipeline", "mention-extraction"],
                    patient_data_impact=False,
                    regulatory_impact=False,
                    performance_impact="5% increase in extraction latency, offset by accuracy gains",
                    rollback_complexity="LOW",
                    estimated_downtime_minutes=0,
                ),
                rollback_plan="Revert NLP_MODEL_VERSION to 2.3.0 in config",
                testing_requirements="Run golden dataset validation, check F1 score >= 0.92",
                approval_chain=[
                    ApprovalRecord(
                        approver="eng-team-lead",
                        role=ApproverRole.TEAM_LEAD,
                        decision="APPROVED",
                        comment="Model validated on golden set",
                        decided_at=now - timedelta(days=10),
                    ),
                ],
                required_approvals=1,
                current_approvals=1,
                deployed_at=now - timedelta(days=8),
                created_at=now - timedelta(days=14),
                updated_at=now - timedelta(days=8),
            ),
            ChangeRecord(
                id="CHG-004",
                title="Migrate Redis cluster to high-availability configuration",
                description=(
                    "Move from single Redis instance to a 3-node Redis Sentinel cluster "
                    "for improved reliability of job queue and caching layers."
                ),
                change_type=ChangeType.INFRASTRUCTURE,
                risk_level=RiskLevel.CRITICAL,
                requester="devops-lead",
                assigned_to="infrastructure-engineer",
                status=ChangeStatus.SUBMITTED,
                impact_assessment=None,
                rollback_plan="Failback to standalone Redis instance from backup",
                testing_requirements="Failover simulation, job queue continuity test, cache coherency test",
                required_approvals=4,
                current_approvals=0,
                created_at=now - timedelta(days=2),
                updated_at=now - timedelta(days=2),
            ),
            ChangeRecord(
                id="CHG-005",
                title="Update consent forms for 21 CFR Part 11 audit findings",
                description=(
                    "Revise electronic consent workflow to capture additional audit trail "
                    "fields required by recent 21 CFR Part 11 audit findings. Includes "
                    "adding timestamp precision to milliseconds and IP address logging."
                ),
                change_type=ChangeType.REGULATORY,
                risk_level=RiskLevel.HIGH,
                requester="compliance-officer",
                assigned_to="compliance-engineer",
                status=ChangeStatus.IMPACT_ASSESSED,
                impact_assessment=ImpactAssessment(
                    affected_systems=["consent-service", "audit-service", "patient-portal"],
                    patient_data_impact=True,
                    phi_details="Consent records linked to patient identifiers",
                    regulatory_impact=True,
                    regulatory_details="Directly addresses 21 CFR Part 11 audit findings",
                    performance_impact="Negligible - adds millisecond timestamp field",
                    rollback_complexity="HIGH",
                    estimated_downtime_minutes=0,
                ),
                rollback_plan="Revert consent form schema, audit log format changes require data migration",
                testing_requirements="Compliance validation checklist, audit trail completeness test",
                required_approvals=3,
                current_approvals=0,
                created_at=now - timedelta(days=4),
                updated_at=now - timedelta(days=1),
            ),
        ]

        for change in examples:
            self._changes[change.id] = change

        # --- Seed one configuration baseline ---
        baseline_items = [
            ConfigurationItem(
                key="DATABASE_POOL_SIZE",
                value="20",
                category="env_var",
                description="PostgreSQL connection pool size",
            ),
            ConfigurationItem(
                key="REDIS_MAX_CONNECTIONS",
                value="50",
                category="env_var",
                description="Redis maximum connections",
            ),
            ConfigurationItem(
                key="NLP_MODEL_VERSION",
                value="2.3.0",
                category="service_version",
                description="Active NLP model version",
            ),
            ConfigurationItem(
                key="FHIR_VALIDATION_ENABLED",
                value="true",
                category="feature_flag",
                description="Enable FHIR resource validation on import",
            ),
            ConfigurationItem(
                key="SCREENING_AUTO_APPROVE",
                value="false",
                category="feature_flag",
                description="Auto-approve low-risk screening matches",
            ),
            ConfigurationItem(
                key="MAX_CONCURRENT_SCREENINGS",
                value="100",
                category="setting",
                description="Maximum concurrent screening jobs",
            ),
            ConfigurationItem(
                key="AUDIT_LOG_RETENTION_DAYS",
                value="365",
                category="setting",
                description="Audit log retention period in days",
            ),
            ConfigurationItem(
                key="API_RATE_LIMIT_PER_MINUTE",
                value="100",
                category="setting",
                description="API rate limit per minute per user",
            ),
            ConfigurationItem(
                key="OMOP_CDM_VERSION",
                value="5.4",
                category="service_version",
                description="OMOP CDM version in use",
            ),
            ConfigurationItem(
                key="ENCRYPTION_ALGORITHM",
                value="AES-256-GCM",
                category="setting",
                description="PHI encryption algorithm",
                sensitive=True,
            ),
        ]

        baseline = ConfigurationBaseline(
            id="BL-001",
            name="Production Baseline v1.0",
            description="Initial production configuration baseline before NLP model upgrade",
            captured_at=now - timedelta(days=30),
            captured_by="devops-lead",
            items=baseline_items,
            environment="production",
        )
        self._baselines[baseline.id] = baseline

    # -------------------------------------------------------------------
    # Change Request CRUD
    # -------------------------------------------------------------------

    def create_change_request(
        self,
        title: str,
        description: str,
        change_type: ChangeType,
        risk_level: RiskLevel,
        requester: str,
        assigned_to: str | None = None,
        impact_assessment: ImpactAssessment | None = None,
        rollback_plan: str | None = None,
        testing_requirements: str | None = None,
        scheduled_date: datetime | None = None,
    ) -> ChangeRecord:
        """Create a new change request.

        Args:
            title: Brief change title.
            description: Detailed description.
            change_type: Type of change.
            risk_level: Risk classification.
            requester: Person requesting the change.
            assigned_to: Person assigned to implement.
            impact_assessment: Impact assessment details.
            rollback_plan: Rollback plan.
            testing_requirements: Testing requirements.
            scheduled_date: Scheduled deployment date.

        Returns:
            The created ChangeRecord.
        """
        required_roles = APPROVAL_REQUIREMENTS.get(risk_level, [ApproverRole.TEAM_LEAD])
        change = ChangeRecord(
            title=title,
            description=description,
            change_type=change_type,
            risk_level=risk_level,
            requester=requester,
            assigned_to=assigned_to,
            impact_assessment=impact_assessment,
            rollback_plan=rollback_plan,
            testing_requirements=testing_requirements,
            scheduled_date=scheduled_date,
            required_approvals=len(required_roles),
        )

        with self._lock:
            self._changes[change.id] = change

        logger.info(
            "Change request created: id=%s, type=%s, risk=%s",
            change.id,
            change_type.value,
            risk_level.value,
        )
        return change

    def get_change_request(self, change_id: str) -> ChangeRecord | None:
        """Retrieve a change request by ID.

        Args:
            change_id: The unique change identifier.

        Returns:
            The ChangeRecord if found, otherwise None.
        """
        with self._lock:
            return self._changes.get(change_id)

    def update_change_request(
        self,
        change_id: str,
        title: str | None = None,
        description: str | None = None,
        status: ChangeStatus | None = None,
        risk_level: RiskLevel | None = None,
        assigned_to: str | None = None,
        impact_assessment: ImpactAssessment | None = None,
        rollback_plan: str | None = None,
        testing_requirements: str | None = None,
        scheduled_date: datetime | None = None,
    ) -> ChangeRecord:
        """Update an existing change request.

        Args:
            change_id: The unique change identifier.
            title: Updated title.
            description: Updated description.
            status: New status (must be valid transition).
            risk_level: Updated risk level.
            assigned_to: Updated assignee.
            impact_assessment: Updated impact assessment.
            rollback_plan: Updated rollback plan.
            testing_requirements: Updated testing requirements.
            scheduled_date: Updated scheduled date.

        Returns:
            The updated ChangeRecord.

        Raises:
            ValueError: If change not found or invalid state transition.
        """
        with self._lock:
            change = self._changes.get(change_id)
            if change is None:
                raise ValueError(f"Change request not found: {change_id}")

            now = datetime.now(timezone.utc)

            # Handle status transition
            if status is not None and status != change.status:
                valid_next = VALID_CHANGE_TRANSITIONS.get(change.status, [])
                if status not in valid_next:
                    raise ValueError(
                        f"Invalid status transition: {change.status.value} -> {status.value}. "
                        f"Valid transitions: {[s.value for s in valid_next]}"
                    )

                # Enforce approval requirement for APPROVED transition
                if status == ChangeStatus.APPROVED:
                    if change.current_approvals < change.required_approvals:
                        raise ValueError(
                            f"Cannot approve: {change.current_approvals}/{change.required_approvals} "
                            f"approvals received. Need {change.required_approvals - change.current_approvals} more."
                        )

                change.status = status

                if status == ChangeStatus.DEPLOYED:
                    change.deployed_at = now
                elif status == ChangeStatus.CLOSED:
                    change.closed_at = now
                elif status == ChangeStatus.ROLLED_BACK:
                    change.rolled_back_at = now

            # Update fields
            if title is not None:
                change.title = title
            if description is not None:
                change.description = description
            if risk_level is not None:
                required_roles = APPROVAL_REQUIREMENTS.get(risk_level, [ApproverRole.TEAM_LEAD])
                change.risk_level = risk_level
                change.required_approvals = len(required_roles)
            if assigned_to is not None:
                change.assigned_to = assigned_to
            if impact_assessment is not None:
                change.impact_assessment = impact_assessment
            if rollback_plan is not None:
                change.rollback_plan = rollback_plan
            if testing_requirements is not None:
                change.testing_requirements = testing_requirements
            if scheduled_date is not None:
                change.scheduled_date = scheduled_date

            change.updated_at = now

        logger.info(
            "Change request updated: id=%s, status=%s",
            change_id,
            change.status.value,
        )
        return change

    def list_change_requests(
        self,
        status: ChangeStatus | None = None,
        risk_level: RiskLevel | None = None,
        change_type: ChangeType | None = None,
        requester: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ChangeRecord], int]:
        """List change requests with optional filters.

        Args:
            status: Filter by status.
            risk_level: Filter by risk level.
            change_type: Filter by change type.
            requester: Filter by requester.
            limit: Max results.
            offset: Pagination offset.

        Returns:
            Tuple of (filtered changes, total count).
        """
        with self._lock:
            changes = list(self._changes.values())

        if status is not None:
            changes = [c for c in changes if c.status == status]
        if risk_level is not None:
            changes = [c for c in changes if c.risk_level == risk_level]
        if change_type is not None:
            changes = [c for c in changes if c.change_type == change_type]
        if requester is not None:
            changes = [c for c in changes if c.requester == requester]

        changes.sort(key=lambda c: c.created_at, reverse=True)
        total = len(changes)
        paginated = changes[offset : offset + limit]

        return paginated, total

    # -------------------------------------------------------------------
    # Approval Workflow
    # -------------------------------------------------------------------

    def approve_change(
        self,
        change_id: str,
        approver: str,
        role: ApproverRole,
        comment: str | None = None,
    ) -> ChangeRecord:
        """Approve a change request.

        Args:
            change_id: The change to approve.
            approver: Name/ID of the approver.
            role: Approver's role.
            comment: Optional comment.

        Returns:
            The updated ChangeRecord.

        Raises:
            ValueError: If change not found, not in approvable state, or
                        duplicate approval from same role.
        """
        with self._lock:
            change = self._changes.get(change_id)
            if change is None:
                raise ValueError(f"Change request not found: {change_id}")

            approvable_statuses = [
                ChangeStatus.SUBMITTED,
                ChangeStatus.IMPACT_ASSESSED,
            ]
            if change.status not in approvable_statuses:
                raise ValueError(
                    f"Change {change_id} is in {change.status.value} status and cannot be approved. "
                    f"Must be in: {[s.value for s in approvable_statuses]}"
                )

            # Check for duplicate role approval
            required_roles = APPROVAL_REQUIREMENTS.get(
                change.risk_level, [ApproverRole.TEAM_LEAD]
            )
            if role not in required_roles:
                raise ValueError(
                    f"Role {role.value} is not in the required approval chain for "
                    f"{change.risk_level.value} risk changes. Required: {[r.value for r in required_roles]}"
                )

            existing_roles = [a.role for a in change.approval_chain if a.decision == "APPROVED"]
            if role in existing_roles:
                raise ValueError(
                    f"Role {role.value} has already approved this change"
                )

            now = datetime.now(timezone.utc)
            approval = ApprovalRecord(
                approver=approver,
                role=role,
                decision="APPROVED",
                comment=comment,
                decided_at=now,
            )
            change.approval_chain.append(approval)
            change.current_approvals += 1
            change.updated_at = now

            # Auto-transition to APPROVED if all approvals received
            if change.current_approvals >= change.required_approvals:
                change.status = ChangeStatus.APPROVED
                logger.info(
                    "Change %s fully approved (%d/%d)",
                    change_id,
                    change.current_approvals,
                    change.required_approvals,
                )

        logger.info(
            "Change %s approved by %s (%s): %d/%d",
            change_id,
            approver,
            role.value,
            change.current_approvals,
            change.required_approvals,
        )
        return change

    def reject_change(
        self,
        change_id: str,
        approver: str,
        role: ApproverRole,
        reason: str,
    ) -> ChangeRecord:
        """Reject a change request.

        Args:
            change_id: The change to reject.
            approver: Name/ID of the rejector.
            role: Rejector's role.
            reason: Reason for rejection.

        Returns:
            The updated ChangeRecord.

        Raises:
            ValueError: If change not found or already in terminal state.
        """
        with self._lock:
            change = self._changes.get(change_id)
            if change is None:
                raise ValueError(f"Change request not found: {change_id}")

            terminal = [ChangeStatus.CLOSED, ChangeStatus.REJECTED]
            if change.status in terminal:
                raise ValueError(
                    f"Change {change_id} is in terminal status {change.status.value} and cannot be rejected"
                )

            now = datetime.now(timezone.utc)
            rejection = ApprovalRecord(
                approver=approver,
                role=role,
                decision="REJECTED",
                comment=reason,
                decided_at=now,
            )
            change.approval_chain.append(rejection)
            change.status = ChangeStatus.REJECTED
            change.updated_at = now

        logger.info(
            "Change %s rejected by %s (%s): %s",
            change_id,
            approver,
            role.value,
            reason,
        )
        return change

    # -------------------------------------------------------------------
    # Configuration Management
    # -------------------------------------------------------------------

    def capture_baseline(
        self,
        name: str,
        description: str | None = None,
        captured_by: str = "system",
        environment: str = "production",
    ) -> ConfigurationBaseline:
        """Capture current configuration as a baseline.

        Args:
            name: Human-readable name for the baseline.
            description: Optional description.
            captured_by: Who is capturing the baseline.
            environment: Environment being captured.

        Returns:
            The created ConfigurationBaseline.
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            items = list(self._current_config.values())

        baseline = ConfigurationBaseline(
            id=f"BL-{uuid4().hex[:8].upper()}",
            name=name,
            description=description,
            captured_at=now,
            captured_by=captured_by,
            items=[item.model_copy() for item in items],
            environment=environment,
        )

        with self._lock:
            self._baselines[baseline.id] = baseline

        logger.info(
            "Configuration baseline captured: id=%s, name=%s, items=%d",
            baseline.id,
            name,
            len(items),
        )
        return baseline

    def list_baselines(self) -> list[ConfigurationBaseline]:
        """List all configuration baselines.

        Returns:
            List of ConfigurationBaseline, sorted by captured_at descending.
        """
        with self._lock:
            baselines = list(self._baselines.values())
        baselines.sort(key=lambda b: b.captured_at, reverse=True)
        return baselines

    def detect_drift(self, baseline_id: str | None = None) -> DriftReport:
        """Detect configuration drift from a baseline.

        Compares current configuration against a baseline to find changes.
        If no baseline_id is given, uses the most recent baseline.

        Args:
            baseline_id: Optional baseline ID to compare against.

        Returns:
            DriftReport with details of any configuration drift.

        Raises:
            ValueError: If baseline not found or no baselines exist.
        """
        with self._lock:
            if baseline_id:
                baseline = self._baselines.get(baseline_id)
                if baseline is None:
                    raise ValueError(f"Baseline not found: {baseline_id}")
            else:
                if not self._baselines:
                    raise ValueError("No configuration baselines exist")
                baselines = sorted(
                    self._baselines.values(),
                    key=lambda b: b.captured_at,
                    reverse=True,
                )
                baseline = baselines[0]

            current = dict(self._current_config)

        now = datetime.now(timezone.utc)

        # Build baseline lookup
        baseline_lookup: dict[str, ConfigurationItem] = {
            item.key: item for item in baseline.items
        }

        drifts: list[DriftItem] = []
        added_items: list[ConfigurationItem] = []
        removed_keys: list[str] = []

        # Check for drifted and removed items
        for key, bl_item in baseline_lookup.items():
            curr_item = current.get(key)
            if curr_item is None:
                removed_keys.append(key)
            elif curr_item.value != bl_item.value:
                # Determine severity based on category
                severity = "LOW"
                if bl_item.category == "service_version":
                    severity = "MEDIUM"
                if bl_item.sensitive:
                    severity = "HIGH"
                drifts.append(
                    DriftItem(
                        key=key,
                        baseline_value=bl_item.value,
                        current_value=curr_item.value,
                        category=bl_item.category,
                        severity=severity,
                    )
                )

        # Check for added items
        for key, curr_item in current.items():
            if key not in baseline_lookup:
                added_items.append(curr_item)

        total_items = len(baseline_lookup)
        drifted_count = len(drifts) + len(removed_keys) + len(added_items)
        drift_pct = (drifted_count / total_items * 100) if total_items > 0 else 0.0

        return DriftReport(
            baseline_id=baseline.id,
            baseline_name=baseline.name,
            checked_at=now,
            total_items=total_items,
            drifted_items=drifted_count,
            drift_percentage=round(drift_pct, 1),
            drifts=drifts,
            added_items=added_items,
            removed_keys=removed_keys,
        )

    def get_current_config(self) -> list[ConfigurationItem]:
        """Get current configuration items.

        Returns:
            List of current ConfigurationItems.
        """
        with self._lock:
            return list(self._current_config.values())

    def update_config_item(
        self,
        key: str,
        value: str,
        category: str | None = None,
        description: str | None = None,
    ) -> ConfigurationItem:
        """Update or create a configuration item.

        Args:
            key: Configuration key.
            value: New value.
            category: Optional category.
            description: Optional description.

        Returns:
            The updated ConfigurationItem.
        """
        with self._lock:
            existing = self._current_config.get(key)
            if existing:
                existing.value = value
                if category is not None:
                    existing.category = category
                if description is not None:
                    existing.description = description
                return existing
            else:
                item = ConfigurationItem(
                    key=key,
                    value=value,
                    category=category or "general",
                    description=description,
                )
                self._current_config[key] = item
                return item

    # -------------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------------

    def get_metrics(self) -> ChangeMetrics:
        """Calculate change control dashboard metrics.

        Returns:
            ChangeMetrics with aggregated statistics.
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            all_changes = list(self._changes.values())

        total = len(all_changes)

        terminal = [ChangeStatus.CLOSED, ChangeStatus.REJECTED, ChangeStatus.ROLLED_BACK]
        open_changes = [c for c in all_changes if c.status not in terminal]
        deployed = [c for c in all_changes if c.deployed_at is not None]
        rolled_back = [c for c in all_changes if c.status == ChangeStatus.ROLLED_BACK]

        # By risk level
        by_risk: dict[str, int] = {}
        for rl in RiskLevel:
            count = sum(1 for c in all_changes if c.risk_level == rl)
            if count > 0:
                by_risk[rl.value] = count

        # By status
        by_status: dict[str, int] = {}
        for s in ChangeStatus:
            count = sum(1 for c in all_changes if c.status == s)
            if count > 0:
                by_status[s.value] = count

        # By type
        by_type: dict[str, int] = {}
        for ct in ChangeType:
            count = sum(1 for c in all_changes if c.change_type == ct)
            if count > 0:
                by_type[ct.value] = count

        # Average time to deploy
        avg_deploy_hours = 0.0
        if deployed:
            total_hours = sum(
                (c.deployed_at - c.created_at).total_seconds() / 3600
                for c in deployed
                if c.deployed_at is not None
            )
            avg_deploy_hours = total_hours / len(deployed)

        # Change failure rate (rolled back / deployed)
        change_failure_rate = 0.0
        if deployed:
            failures = sum(
                1 for c in deployed if c.status == ChangeStatus.ROLLED_BACK
            )
            change_failure_rate = (failures / len(deployed)) * 100

        # Rollback rate (rolled back / total)
        rollback_rate = 0.0
        if total > 0:
            rollback_rate = (len(rolled_back) / total) * 100

        # Pending approvals
        pending_approval_statuses = [ChangeStatus.SUBMITTED, ChangeStatus.IMPACT_ASSESSED]
        pending_approvals = sum(
            1 for c in all_changes if c.status in pending_approval_statuses
        )

        # Deployed in last 30 days
        thirty_days_ago = now - timedelta(days=30)
        deployed_last_30 = sum(
            1
            for c in deployed
            if c.deployed_at is not None and c.deployed_at >= thirty_days_ago
        )

        return ChangeMetrics(
            total_changes=total,
            open_changes=len(open_changes),
            by_risk_level=by_risk,
            by_status=by_status,
            by_type=by_type,
            avg_time_to_deploy_hours=round(avg_deploy_hours, 1),
            change_failure_rate=round(change_failure_rate, 1),
            rollback_rate=round(rollback_rate, 1),
            pending_approvals=pending_approvals,
            deployed_last_30_days=deployed_last_30,
        )


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------


def get_change_control_service() -> ChangeControlService:
    """Get or create the singleton ChangeControlService instance."""
    global _change_control_instance
    if _change_control_instance is None:
        with _change_control_lock:
            if _change_control_instance is None:
                _change_control_instance = ChangeControlService()
    return _change_control_instance


def reset_change_control_service() -> None:
    """Reset the singleton for testing."""
    global _change_control_instance
    with _change_control_lock:
        _change_control_instance = None
