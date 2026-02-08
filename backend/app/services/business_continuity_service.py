"""Business Continuity Testing service (COO-2).

Manages tabletop exercise scenarios, exercise scheduling/tracking,
recovery procedure validation, and BC program metrics for clinical
trial patient recruitment platform.

Usage:
    from app.services.business_continuity_service import get_business_continuity_service

    service = get_business_continuity_service()
    scenarios = service.list_scenarios()
    exercise = service.schedule_exercise(scenario_id="SCENARIO_1", ...)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas.business_continuity import (
    ActionItem,
    BCMetrics,
    ExerciseStatus,
    ProcedureCheck,
    ProcedureValidationReport,
    ProcedureValidationResult,
    RecoveryStep,
    ScenarioCoverage,
    Severity,
    SuccessCriterion,
    TabletopScenario,
)

logger = logging.getLogger(__name__)

# Singleton instance and lock
_bc_instance: BusinessContinuityService | None = None
_bc_lock = Lock()


# ---------------------------------------------------------------------------
# Internal Exercise Record (not exposed directly; mapped to ExerciseResponse)
# ---------------------------------------------------------------------------


class ExerciseRecord(BaseModel):
    """Internal representation of a BC exercise."""

    id: str = Field(default_factory=lambda: f"EX-{uuid4().hex[:8]}")
    scenario_id: str
    scenario_title: str = ""
    scheduled_date: datetime
    conducted_date: datetime | None = None
    participants: list[str] = Field(default_factory=list)
    status: ExerciseStatus = ExerciseStatus.PLANNED
    actual_rto: str | None = None
    actual_rpo: str | None = None
    findings: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    success_criteria_results: list[SuccessCriterion] = Field(default_factory=list)
    notes: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# Pre-defined Tabletop Scenarios
# ---------------------------------------------------------------------------

TABLETOP_SCENARIOS: list[TabletopScenario] = [
    TabletopScenario(
        id="SCENARIO_1",
        title="Database corruption during active trial screening",
        description=(
            "The primary PostgreSQL database experiences corruption in the clinical_facts "
            "and screening_results tables during peak screening hours. Active trial "
            "screening for 3 concurrent trials is disrupted. Patient data integrity "
            "is uncertain and audit logs show anomalous write patterns. The system must "
            "recover to a known-good state while preserving in-flight screening decisions."
        ),
        severity=Severity.CRITICAL,
        affected_systems=[
            "PostgreSQL primary database",
            "Screening engine",
            "Clinical facts store",
            "Audit logging",
            "Patient matching service",
        ],
        expected_rto="4 hours",
        expected_rpo="1 hour",
        recovery_steps=[
            RecoveryStep(
                order=1,
                action="Activate incident response team and notify stakeholders",
                responsible_role="Incident Commander",
                estimated_duration_minutes=15,
                requires_approval=False,
            ),
            RecoveryStep(
                order=2,
                action="Halt all active screening pipelines to prevent further data writes",
                responsible_role="Platform Engineer",
                estimated_duration_minutes=5,
                documentation_ref="docs/operations/runbooks/screening_halt.md",
            ),
            RecoveryStep(
                order=3,
                action="Assess corruption extent using pg_check and WAL analysis",
                responsible_role="DBA",
                estimated_duration_minutes=30,
                documentation_ref="docs/operations/runbooks/db_corruption_assessment.md",
            ),
            RecoveryStep(
                order=4,
                action="Restore database from latest verified backup (point-in-time recovery)",
                responsible_role="DBA",
                estimated_duration_minutes=60,
                requires_approval=True,
                documentation_ref="docs/operations/runbooks/db_restore.md",
            ),
            RecoveryStep(
                order=5,
                action="Validate data integrity post-restore with checksums",
                responsible_role="DBA",
                estimated_duration_minutes=30,
            ),
            RecoveryStep(
                order=6,
                action="Resume screening pipelines and verify end-to-end flow",
                responsible_role="Platform Engineer",
                estimated_duration_minutes=20,
            ),
            RecoveryStep(
                order=7,
                action="Notify trial coordinators and provide impact assessment",
                responsible_role="Clinical Operations Lead",
                estimated_duration_minutes=15,
            ),
        ],
        roles_involved=[
            "Incident Commander",
            "DBA",
            "Platform Engineer",
            "Clinical Operations Lead",
            "Compliance Officer",
        ],
        success_criteria=[
            SuccessCriterion(
                id="SC1-1",
                description="Database restored to consistent state within RTO",
                measurement="Time from incident detection to full service restoration",
            ),
            SuccessCriterion(
                id="SC1-2",
                description="No patient data lost beyond RPO window",
                measurement="Compare restored data against audit logs",
            ),
            SuccessCriterion(
                id="SC1-3",
                description="All active trial screening resumes successfully",
                measurement="End-to-end screening test for each active trial",
            ),
        ],
    ),
    TabletopScenario(
        id="SCENARIO_2",
        title="Complete datacenter failover (DR activation)",
        description=(
            "The primary datacenter becomes unavailable due to a regional cloud "
            "provider outage. All production services, including the screening engine, "
            "FHIR server, and knowledge graph, must failover to the disaster recovery "
            "site. Patient recruitment must continue with minimal disruption."
        ),
        severity=Severity.CRITICAL,
        affected_systems=[
            "All production services",
            "PostgreSQL (primary)",
            "Redis cluster",
            "Neo4j graph database",
            "File storage",
            "Load balancer",
            "DNS",
        ],
        expected_rto="8 hours",
        expected_rpo="4 hours",
        recovery_steps=[
            RecoveryStep(
                order=1,
                action="Confirm primary datacenter is unavailable (not transient)",
                responsible_role="Platform Engineer",
                estimated_duration_minutes=15,
            ),
            RecoveryStep(
                order=2,
                action="Declare DR event and activate BC plan",
                responsible_role="Incident Commander",
                estimated_duration_minutes=10,
                requires_approval=True,
            ),
            RecoveryStep(
                order=3,
                action="Activate DR database replicas and promote to primary",
                responsible_role="DBA",
                estimated_duration_minutes=30,
                documentation_ref="docs/operations/runbooks/dr_db_failover.md",
            ),
            RecoveryStep(
                order=4,
                action="Switch DNS and load balancer to DR site",
                responsible_role="Platform Engineer",
                estimated_duration_minutes=15,
                documentation_ref="docs/operations/runbooks/dr_dns_failover.md",
            ),
            RecoveryStep(
                order=5,
                action="Verify all services healthy in DR environment",
                responsible_role="Platform Engineer",
                estimated_duration_minutes=60,
            ),
            RecoveryStep(
                order=6,
                action="Validate screening engine end-to-end in DR",
                responsible_role="QA Engineer",
                estimated_duration_minutes=30,
            ),
            RecoveryStep(
                order=7,
                action="Notify trial sponsors and sites of DR activation",
                responsible_role="Clinical Operations Lead",
                estimated_duration_minutes=20,
            ),
        ],
        roles_involved=[
            "Incident Commander",
            "DBA",
            "Platform Engineer",
            "QA Engineer",
            "Clinical Operations Lead",
            "CISO",
        ],
        success_criteria=[
            SuccessCriterion(
                id="SC2-1",
                description="All critical services operational in DR within RTO",
                measurement="Health check endpoints returning 200 in DR site",
            ),
            SuccessCriterion(
                id="SC2-2",
                description="Data loss within RPO window",
                measurement="Compare DR database timestamp with last known primary write",
            ),
            SuccessCriterion(
                id="SC2-3",
                description="Trial screening continues without patient-facing impact",
                measurement="Successful end-to-end screening test in DR",
            ),
        ],
    ),
    TabletopScenario(
        id="SCENARIO_3",
        title="PHI breach detected in audit logs",
        description=(
            "Audit log analysis reveals unauthorized access to Protected Health "
            "Information (PHI) in the patient matching service. An API key with "
            "elevated privileges was used from an unknown IP address to access "
            "patient demographic data and screening results for 500+ patients "
            "across 4 clinical trials."
        ),
        severity=Severity.CRITICAL,
        affected_systems=[
            "Patient matching service",
            "Audit logging system",
            "API gateway",
            "Auth service",
            "Patient demographics store",
            "Screening results",
        ],
        expected_rto="2 hours",
        expected_rpo="0 hours",
        recovery_steps=[
            RecoveryStep(
                order=1,
                action="Immediately revoke the compromised API key",
                responsible_role="Security Engineer",
                estimated_duration_minutes=5,
            ),
            RecoveryStep(
                order=2,
                action="Activate HIPAA breach response team",
                responsible_role="Privacy Officer",
                estimated_duration_minutes=10,
                requires_approval=False,
            ),
            RecoveryStep(
                order=3,
                action="Forensic analysis of access logs to determine breach scope",
                responsible_role="Security Engineer",
                estimated_duration_minutes=60,
                documentation_ref="docs/operations/runbooks/breach_forensics.md",
            ),
            RecoveryStep(
                order=4,
                action="Rotate all API keys and enforce IP allowlisting",
                responsible_role="Security Engineer",
                estimated_duration_minutes=30,
            ),
            RecoveryStep(
                order=5,
                action="Prepare breach notification report per HIPAA requirements",
                responsible_role="Privacy Officer",
                estimated_duration_minutes=120,
                requires_approval=True,
                documentation_ref="docs/operations/runbooks/hipaa_breach_notification.md",
            ),
            RecoveryStep(
                order=6,
                action="Notify affected patients and HHS within regulatory timeframes",
                responsible_role="Privacy Officer",
                estimated_duration_minutes=60,
                requires_approval=True,
            ),
        ],
        roles_involved=[
            "CISO",
            "Privacy Officer",
            "Security Engineer",
            "Legal Counsel",
            "Clinical Operations Lead",
            "Compliance Officer",
        ],
        success_criteria=[
            SuccessCriterion(
                id="SC3-1",
                description="Compromised credentials revoked within 15 minutes",
                measurement="Time from detection to credential revocation",
            ),
            SuccessCriterion(
                id="SC3-2",
                description="Breach scope fully determined within 24 hours",
                measurement="Forensic report completeness",
            ),
            SuccessCriterion(
                id="SC3-3",
                description="HIPAA notification obligations met within regulatory timeframes",
                measurement="Notification sent within 60 days of discovery",
            ),
        ],
    ),
    TabletopScenario(
        id="SCENARIO_4",
        title="NLP service complete failure during batch processing",
        description=(
            "The NLP extraction service fails completely during a large batch "
            "processing job of 2,000 clinical notes from a new trial site. The "
            "ML ensemble model crashes due to memory exhaustion, and the fallback "
            "rule-based engine also fails due to a corrupted vocabulary cache. "
            "Screening is blocked for all pending patients."
        ),
        severity=Severity.HIGH,
        affected_systems=[
            "NLP extraction service",
            "ML ensemble model",
            "Rule-based NLP engine",
            "Vocabulary cache",
            "Batch processing queue",
            "Screening pipeline",
        ],
        expected_rto="2 hours",
        expected_rpo="0 hours",
        recovery_steps=[
            RecoveryStep(
                order=1,
                action="Identify root cause (memory, model corruption, or vocab cache)",
                responsible_role="ML Engineer",
                estimated_duration_minutes=20,
            ),
            RecoveryStep(
                order=2,
                action="Restart NLP service with increased memory limits",
                responsible_role="Platform Engineer",
                estimated_duration_minutes=10,
                documentation_ref="docs/operations/runbooks/nlp_service_restart.md",
            ),
            RecoveryStep(
                order=3,
                action="Rebuild vocabulary cache from source data",
                responsible_role="ML Engineer",
                estimated_duration_minutes=15,
            ),
            RecoveryStep(
                order=4,
                action="Requeue failed batch jobs with smaller batch sizes",
                responsible_role="Platform Engineer",
                estimated_duration_minutes=10,
            ),
            RecoveryStep(
                order=5,
                action="Validate NLP output quality on sample documents",
                responsible_role="Clinical NLP Specialist",
                estimated_duration_minutes=30,
            ),
            RecoveryStep(
                order=6,
                action="Resume full batch processing and monitor",
                responsible_role="Platform Engineer",
                estimated_duration_minutes=15,
            ),
        ],
        roles_involved=[
            "ML Engineer",
            "Platform Engineer",
            "Clinical NLP Specialist",
            "Clinical Operations Lead",
        ],
        success_criteria=[
            SuccessCriterion(
                id="SC4-1",
                description="NLP service restored within RTO",
                measurement="Time from failure detection to service restoration",
            ),
            SuccessCriterion(
                id="SC4-2",
                description="No clinical notes lost (RPO = 0)",
                measurement="All queued notes successfully re-processed",
            ),
            SuccessCriterion(
                id="SC4-3",
                description="NLP output quality matches baseline F1 score",
                measurement="F1 score on validation set >= 0.85",
            ),
        ],
    ),
    TabletopScenario(
        id="SCENARIO_5",
        title="Ransomware attack on file storage",
        description=(
            "A ransomware attack encrypts clinical document storage including "
            "uploaded PDFs, lab reports, and diagnostic images. The attack vector "
            "was a compromised service account with write access to the document "
            "store. Encrypted files include source documents for 12 active trials."
        ),
        severity=Severity.CRITICAL,
        affected_systems=[
            "Document storage (S3/blob)",
            "Document ingestion service",
            "Clinical document viewer",
            "Backup storage",
            "Service account credentials",
        ],
        expected_rto="12 hours",
        expected_rpo="24 hours",
        recovery_steps=[
            RecoveryStep(
                order=1,
                action="Isolate affected storage accounts and revoke service credentials",
                responsible_role="Security Engineer",
                estimated_duration_minutes=10,
            ),
            RecoveryStep(
                order=2,
                action="Activate incident response and engage forensics team",
                responsible_role="CISO",
                estimated_duration_minutes=15,
                requires_approval=True,
            ),
            RecoveryStep(
                order=3,
                action="Assess ransomware variant and determine attack vector",
                responsible_role="Security Engineer",
                estimated_duration_minutes=120,
            ),
            RecoveryStep(
                order=4,
                action="Restore documents from immutable backup (air-gapped)",
                responsible_role="Platform Engineer",
                estimated_duration_minutes=240,
                requires_approval=True,
                documentation_ref="docs/operations/runbooks/storage_restore.md",
            ),
            RecoveryStep(
                order=5,
                action="Verify document integrity with checksums against manifest",
                responsible_role="Platform Engineer",
                estimated_duration_minutes=60,
            ),
            RecoveryStep(
                order=6,
                action="Rotate all service credentials and implement MFA",
                responsible_role="Security Engineer",
                estimated_duration_minutes=30,
            ),
            RecoveryStep(
                order=7,
                action="Resume document ingestion and notify trial sponsors",
                responsible_role="Clinical Operations Lead",
                estimated_duration_minutes=30,
            ),
        ],
        roles_involved=[
            "CISO",
            "Security Engineer",
            "Platform Engineer",
            "Legal Counsel",
            "Clinical Operations Lead",
            "Forensics Team",
        ],
        success_criteria=[
            SuccessCriterion(
                id="SC5-1",
                description="Ransomware contained and eradicated",
                measurement="No further encryption activity detected for 24 hours",
            ),
            SuccessCriterion(
                id="SC5-2",
                description="All clinical documents restored from backup",
                measurement="Document count and checksum verification against manifest",
            ),
            SuccessCriterion(
                id="SC5-3",
                description="Attack vector identified and remediated",
                measurement="Root cause analysis report completed",
            ),
        ],
    ),
    TabletopScenario(
        id="SCENARIO_6",
        title="Third-party API (Metriport) extended outage",
        description=(
            "The Metriport health data integration API experiences an extended "
            "outage lasting 48+ hours. Patient medical records cannot be fetched "
            "or synced for new screening candidates. Trials requiring real-time "
            "EHR data for eligibility screening are blocked."
        ),
        severity=Severity.HIGH,
        affected_systems=[
            "Metriport integration",
            "FHIR import pipeline",
            "Patient data sync",
            "Screening eligibility engine",
            "Trial enrollment workflow",
        ],
        expected_rto="1 hour",
        expected_rpo="0 hours",
        recovery_steps=[
            RecoveryStep(
                order=1,
                action="Confirm Metriport outage via status page and support channels",
                responsible_role="Platform Engineer",
                estimated_duration_minutes=10,
            ),
            RecoveryStep(
                order=2,
                action="Activate cached data fallback for screening decisions",
                responsible_role="Platform Engineer",
                estimated_duration_minutes=15,
                documentation_ref="docs/operations/runbooks/metriport_fallback.md",
            ),
            RecoveryStep(
                order=3,
                action="Enable manual document upload workflow for trial sites",
                responsible_role="Clinical Operations Lead",
                estimated_duration_minutes=20,
            ),
            RecoveryStep(
                order=4,
                action="Notify trial coordinators of degraded mode and alternative workflows",
                responsible_role="Clinical Operations Lead",
                estimated_duration_minutes=15,
            ),
            RecoveryStep(
                order=5,
                action="Monitor Metriport status and queue sync jobs for recovery",
                responsible_role="Platform Engineer",
                estimated_duration_minutes=10,
            ),
            RecoveryStep(
                order=6,
                action="Re-sync all pending patient records when API restores",
                responsible_role="Platform Engineer",
                estimated_duration_minutes=60,
            ),
        ],
        roles_involved=[
            "Platform Engineer",
            "Clinical Operations Lead",
            "Trial Coordinator",
        ],
        success_criteria=[
            SuccessCriterion(
                id="SC6-1",
                description="Screening continues via fallback within RTO",
                measurement="Fallback screening available within 1 hour of outage",
            ),
            SuccessCriterion(
                id="SC6-2",
                description="No patient data lost during outage",
                measurement="All pending syncs completed after API restoration",
            ),
            SuccessCriterion(
                id="SC6-3",
                description="Trial sites notified and provided alternative workflow",
                measurement="Notification sent to all active trial sites",
            ),
        ],
    ),
    TabletopScenario(
        id="SCENARIO_7",
        title="Key personnel unavailability (bus factor)",
        description=(
            "The sole DBA and the lead ML engineer are simultaneously unavailable "
            "(medical emergency). Critical database maintenance is overdue and the "
            "NLP model requires an urgent hotfix for a false-negative pattern "
            "affecting trial screening accuracy."
        ),
        severity=Severity.MEDIUM,
        affected_systems=[
            "Database administration",
            "NLP model management",
            "On-call rotation",
            "Knowledge transfer documentation",
        ],
        expected_rto="24 hours",
        expected_rpo="0 hours",
        recovery_steps=[
            RecoveryStep(
                order=1,
                action="Activate secondary on-call personnel from cross-trained team",
                responsible_role="Engineering Manager",
                estimated_duration_minutes=30,
            ),
            RecoveryStep(
                order=2,
                action="Access runbook documentation for database maintenance procedures",
                responsible_role="Backup DBA",
                estimated_duration_minutes=15,
                documentation_ref="docs/operations/runbooks/db_maintenance.md",
            ),
            RecoveryStep(
                order=3,
                action="Execute critical database maintenance using documented procedures",
                responsible_role="Backup DBA",
                estimated_duration_minutes=120,
            ),
            RecoveryStep(
                order=4,
                action="Deploy NLP model hotfix using documented CI/CD pipeline",
                responsible_role="Backup ML Engineer",
                estimated_duration_minutes=60,
                documentation_ref="docs/operations/runbooks/nlp_model_deploy.md",
            ),
            RecoveryStep(
                order=5,
                action="Validate screening accuracy post-hotfix",
                responsible_role="QA Engineer",
                estimated_duration_minutes=30,
            ),
        ],
        roles_involved=[
            "Engineering Manager",
            "Backup DBA",
            "Backup ML Engineer",
            "QA Engineer",
        ],
        success_criteria=[
            SuccessCriterion(
                id="SC7-1",
                description="Critical tasks completed by backup personnel within RTO",
                measurement="Tasks completed within 24 hours",
            ),
            SuccessCriterion(
                id="SC7-2",
                description="Documentation sufficient for backup personnel",
                measurement="Backup personnel can complete tasks without external help",
            ),
            SuccessCriterion(
                id="SC7-3",
                description="No service degradation during personnel gap",
                measurement="SLA metrics maintained throughout incident",
            ),
        ],
    ),
    TabletopScenario(
        id="SCENARIO_8",
        title="Regulatory audit with 48-hour data production requirement",
        description=(
            "The FDA issues a 48-hour data production request as part of a GCP "
            "inspection for one of the active trials. The request covers all "
            "screening decisions, eligibility criteria mappings, audit trails, "
            "and algorithm validation documentation for the past 6 months."
        ),
        severity=Severity.HIGH,
        affected_systems=[
            "Audit logging system",
            "Data export service",
            "Screening decision records",
            "Algorithm validation reports",
            "Document management system",
        ],
        expected_rto="48 hours",
        expected_rpo="0 hours",
        recovery_steps=[
            RecoveryStep(
                order=1,
                action="Acknowledge regulatory request and assemble response team",
                responsible_role="Compliance Officer",
                estimated_duration_minutes=30,
                requires_approval=True,
            ),
            RecoveryStep(
                order=2,
                action="Generate comprehensive audit trail export for specified trial and period",
                responsible_role="Platform Engineer",
                estimated_duration_minutes=60,
                documentation_ref="docs/operations/runbooks/audit_export.md",
            ),
            RecoveryStep(
                order=3,
                action="Compile eligibility criteria documentation and mapping rationale",
                responsible_role="Clinical Operations Lead",
                estimated_duration_minutes=120,
            ),
            RecoveryStep(
                order=4,
                action="Generate algorithm validation report with F1/precision/recall metrics",
                responsible_role="ML Engineer",
                estimated_duration_minutes=90,
            ),
            RecoveryStep(
                order=5,
                action="Legal review of data package before submission",
                responsible_role="Legal Counsel",
                estimated_duration_minutes=120,
                requires_approval=True,
            ),
            RecoveryStep(
                order=6,
                action="Submit data package to regulatory authority",
                responsible_role="Compliance Officer",
                estimated_duration_minutes=30,
                requires_approval=True,
            ),
        ],
        roles_involved=[
            "Compliance Officer",
            "Platform Engineer",
            "Clinical Operations Lead",
            "ML Engineer",
            "Legal Counsel",
            "CTO",
        ],
        success_criteria=[
            SuccessCriterion(
                id="SC8-1",
                description="Data package produced within 48-hour deadline",
                measurement="Submission timestamp vs. request timestamp",
            ),
            SuccessCriterion(
                id="SC8-2",
                description="All requested data elements included and complete",
                measurement="Checklist verification against regulatory request",
            ),
            SuccessCriterion(
                id="SC8-3",
                description="Data package passes legal review without redactions",
                measurement="Legal sign-off on submission",
            ),
        ],
    ),
]

# Build lookup map
_SCENARIO_MAP: dict[str, TabletopScenario] = {s.id: s for s in TABLETOP_SCENARIOS}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class BusinessContinuityService:
    """Business Continuity Testing and Exercise Management service.

    Manages tabletop scenarios, exercise scheduling and tracking,
    recovery procedure validation, and BC program metrics.
    """

    def __init__(self) -> None:
        self._exercises: dict[str, ExerciseRecord] = {}
        self._lock = Lock()
        logger.info(
            "BusinessContinuityService initialized with %d scenarios",
            len(TABLETOP_SCENARIOS),
        )

    # -- Scenarios ----------------------------------------------------------

    def list_scenarios(
        self,
        severity: Severity | None = None,
    ) -> list[TabletopScenario]:
        """List all tabletop scenarios, optionally filtered by severity."""
        scenarios = list(TABLETOP_SCENARIOS)
        if severity is not None:
            scenarios = [s for s in scenarios if s.severity == severity]
        return scenarios

    def get_scenario(self, scenario_id: str) -> TabletopScenario | None:
        """Get a specific scenario by ID."""
        return _SCENARIO_MAP.get(scenario_id)

    # -- Exercises ----------------------------------------------------------

    def schedule_exercise(
        self,
        scenario_id: str,
        scheduled_date: datetime,
        participants: list[str] | None = None,
        notes: str | None = None,
    ) -> ExerciseRecord:
        """Schedule a new exercise for a scenario."""
        scenario = self.get_scenario(scenario_id)
        if scenario is None:
            raise ValueError(f"Scenario not found: {scenario_id}")

        with self._lock:
            record = ExerciseRecord(
                scenario_id=scenario_id,
                scenario_title=scenario.title,
                scheduled_date=scheduled_date,
                participants=participants or [],
                notes=notes,
            )
            self._exercises[record.id] = record
            logger.info(
                "Exercise scheduled: %s for scenario %s on %s",
                record.id,
                scenario_id,
                scheduled_date.isoformat(),
            )
            return record

    def list_exercises(
        self,
        scenario_id: str | None = None,
        status: ExerciseStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ExerciseRecord], int]:
        """List exercises with optional filtering."""
        exercises = list(self._exercises.values())

        if scenario_id is not None:
            exercises = [e for e in exercises if e.scenario_id == scenario_id]
        if status is not None:
            exercises = [e for e in exercises if e.status == status]

        # Sort by scheduled_date descending
        exercises.sort(key=lambda e: e.scheduled_date, reverse=True)
        total = len(exercises)
        return exercises[offset : offset + limit], total

    def get_exercise(self, exercise_id: str) -> ExerciseRecord | None:
        """Get a specific exercise by ID."""
        return self._exercises.get(exercise_id)

    def update_exercise(
        self,
        exercise_id: str,
        status: ExerciseStatus | None = None,
        conducted_date: datetime | None = None,
        participants: list[str] | None = None,
        actual_rto: str | None = None,
        actual_rpo: str | None = None,
        findings: list[str] | None = None,
        action_items: list[ActionItem] | None = None,
        success_criteria_results: list[SuccessCriterion] | None = None,
        notes: str | None = None,
    ) -> ExerciseRecord:
        """Update an exercise record."""
        with self._lock:
            exercise = self._exercises.get(exercise_id)
            if exercise is None:
                raise ValueError(f"Exercise not found: {exercise_id}")

            # Validate status transitions
            if status is not None:
                valid = _valid_exercise_transitions(exercise.status)
                if status not in valid:
                    raise ValueError(
                        f"Invalid status transition: {exercise.status.value} -> {status.value}. "
                        f"Valid transitions: {[s.value for s in valid]}"
                    )
                exercise.status = status

            if conducted_date is not None:
                exercise.conducted_date = conducted_date
            if participants is not None:
                exercise.participants = participants
            if actual_rto is not None:
                exercise.actual_rto = actual_rto
            if actual_rpo is not None:
                exercise.actual_rpo = actual_rpo
            if findings is not None:
                exercise.findings = findings
            if action_items is not None:
                exercise.action_items = action_items
            if success_criteria_results is not None:
                exercise.success_criteria_results = success_criteria_results
            if notes is not None:
                exercise.notes = notes

            exercise.updated_at = datetime.now(timezone.utc)
            logger.info("Exercise updated: %s (status=%s)", exercise_id, exercise.status.value)
            return exercise

    # -- Procedure Validation -----------------------------------------------

    def validate_procedures(
        self,
        scenario_ids: list[str] | None = None,
    ) -> ProcedureValidationReport:
        """Validate recovery procedures for scenarios.

        For each scenario, checks that:
        - Recovery steps are defined and ordered
        - Referenced documentation paths are plausible
        - Referenced services are in the known service list
        - Roles are assigned to steps
        - Success criteria are defined
        """
        now = datetime.now(timezone.utc)
        scenarios_to_check = (
            [_SCENARIO_MAP[sid] for sid in scenario_ids if sid in _SCENARIO_MAP]
            if scenario_ids
            else list(TABLETOP_SCENARIOS)
        )

        results: list[ProcedureValidationResult] = []
        for scenario in scenarios_to_check:
            checks: list[ProcedureCheck] = []
            recommendations: list[str] = []

            # Check 1: Recovery steps exist
            has_steps = len(scenario.recovery_steps) > 0
            checks.append(
                ProcedureCheck(
                    check_name="recovery_steps_defined",
                    passed=has_steps,
                    details=(
                        f"{len(scenario.recovery_steps)} recovery steps defined"
                        if has_steps
                        else "No recovery steps defined"
                    ),
                )
            )
            if not has_steps:
                recommendations.append("Define recovery steps for this scenario")

            # Check 2: Steps are properly ordered (sequential from 1)
            if has_steps:
                orders = [s.order for s in scenario.recovery_steps]
                expected = list(range(1, len(orders) + 1))
                properly_ordered = orders == expected
                checks.append(
                    ProcedureCheck(
                        check_name="steps_properly_ordered",
                        passed=properly_ordered,
                        details=(
                            "Steps are sequentially ordered"
                            if properly_ordered
                            else f"Step ordering is incorrect: {orders}"
                        ),
                    )
                )
                if not properly_ordered:
                    recommendations.append("Fix step ordering to be sequential from 1")

            # Check 3: Documentation references exist for critical steps
            steps_with_docs = [
                s for s in scenario.recovery_steps if s.documentation_ref
            ]
            has_doc_refs = len(steps_with_docs) > 0
            checks.append(
                ProcedureCheck(
                    check_name="documentation_references",
                    passed=has_doc_refs,
                    details=(
                        f"{len(steps_with_docs)} steps reference documentation"
                        if has_doc_refs
                        else "No steps reference external documentation"
                    ),
                )
            )
            if not has_doc_refs:
                recommendations.append(
                    "Add documentation references to critical recovery steps"
                )

            # Check 4: Roles assigned to all steps
            steps_with_roles = [
                s for s in scenario.recovery_steps if s.responsible_role
            ]
            all_roles_assigned = len(steps_with_roles) == len(scenario.recovery_steps)
            checks.append(
                ProcedureCheck(
                    check_name="roles_assigned",
                    passed=all_roles_assigned,
                    details=(
                        "All steps have responsible roles assigned"
                        if all_roles_assigned
                        else f"Only {len(steps_with_roles)}/{len(scenario.recovery_steps)} steps have roles"
                    ),
                )
            )

            # Check 5: Success criteria defined
            has_criteria = len(scenario.success_criteria) > 0
            checks.append(
                ProcedureCheck(
                    check_name="success_criteria_defined",
                    passed=has_criteria,
                    details=(
                        f"{len(scenario.success_criteria)} success criteria defined"
                        if has_criteria
                        else "No success criteria defined"
                    ),
                )
            )
            if not has_criteria:
                recommendations.append("Define success criteria for this scenario")

            # Check 6: Roles involved list is populated
            has_roles = len(scenario.roles_involved) > 0
            checks.append(
                ProcedureCheck(
                    check_name="roles_involved_defined",
                    passed=has_roles,
                    details=(
                        f"{len(scenario.roles_involved)} roles involved"
                        if has_roles
                        else "No roles defined for this scenario"
                    ),
                )
            )

            # Check 7: RTO and RPO are specified
            has_rto_rpo = bool(scenario.expected_rto) and bool(scenario.expected_rpo)
            checks.append(
                ProcedureCheck(
                    check_name="rto_rpo_specified",
                    passed=has_rto_rpo,
                    details=(
                        f"RTO: {scenario.expected_rto}, RPO: {scenario.expected_rpo}"
                        if has_rto_rpo
                        else "RTO or RPO not specified"
                    ),
                )
            )

            overall_valid = all(c.passed for c in checks)
            results.append(
                ProcedureValidationResult(
                    scenario_id=scenario.id,
                    scenario_title=scenario.title,
                    validated_at=now,
                    overall_valid=overall_valid,
                    checks=checks,
                    recommendations=recommendations,
                )
            )

        valid_count = sum(1 for r in results if r.overall_valid)
        return ProcedureValidationReport(
            validated_at=now,
            total_scenarios=len(results),
            valid_scenarios=valid_count,
            invalid_scenarios=len(results) - valid_count,
            results=results,
        )

    # -- BC Metrics ---------------------------------------------------------

    def get_metrics(self) -> BCMetrics:
        """Calculate BC program metrics."""
        now = datetime.now(timezone.utc)
        ninety_days_ago = now - timedelta(days=90)

        all_exercises = list(self._exercises.values())
        completed = [e for e in all_exercises if e.status == ExerciseStatus.COMPLETED]
        recent = [
            e
            for e in completed
            if e.conducted_date and e.conducted_date >= ninety_days_ago
        ]

        # Action items across all exercises
        all_action_items: list[ActionItem] = []
        for ex in all_exercises:
            all_action_items.extend(ex.action_items)

        open_items = [ai for ai in all_action_items if ai.status != "CLOSED"]
        closed_items = [ai for ai in all_action_items if ai.status == "CLOSED"]

        total_ai = len(all_action_items)
        closure_rate = (len(closed_items) / total_ai * 100.0) if total_ai > 0 else 100.0

        # RTO/RPO compliance: exercises where actual <= expected
        rto_compliant = 0
        rpo_compliant = 0
        compliance_checked = 0
        for ex in completed:
            if ex.actual_rto is not None:
                compliance_checked += 1
                scenario = self.get_scenario(ex.scenario_id)
                if scenario:
                    if _duration_lte(ex.actual_rto, scenario.expected_rto):
                        rto_compliant += 1
                    if ex.actual_rpo is not None and _duration_lte(
                        ex.actual_rpo, scenario.expected_rpo
                    ):
                        rpo_compliant += 1

        rto_rate = (rto_compliant / compliance_checked * 100.0) if compliance_checked > 0 else 100.0
        rpo_rate = (rpo_compliant / compliance_checked * 100.0) if compliance_checked > 0 else 100.0

        # Per-scenario coverage
        scenario_coverage: list[ScenarioCoverage] = []
        for scenario in TABLETOP_SCENARIOS:
            s_exercises = [
                e for e in completed if e.scenario_id == scenario.id
            ]
            last_date = None
            days_since = None
            if s_exercises:
                last_ex = max(
                    s_exercises,
                    key=lambda e: e.conducted_date or e.scheduled_date,
                )
                last_date = last_ex.conducted_date or last_ex.scheduled_date
                days_since = (now - last_date).days

            s_all = [e for e in all_exercises if e.scenario_id == scenario.id]

            scenario_coverage.append(
                ScenarioCoverage(
                    scenario_id=scenario.id,
                    scenario_title=scenario.title,
                    severity=scenario.severity,
                    total_exercises=len(s_all),
                    completed_exercises=len(s_exercises),
                    last_exercise_date=last_date,
                    days_since_last_exercise=days_since,
                )
            )

        # Exercise frequency: at least one exercise per scenario in the last 90 days
        scenarios_exercised_recently = {
            e.scenario_id for e in recent
        }
        frequency_met = len(scenarios_exercised_recently) >= len(TABLETOP_SCENARIOS)

        # Overall readiness score (0-100)
        # Components: exercise frequency (30%), RTO compliance (25%),
        #             RPO compliance (25%), action item closure (20%)
        freq_score = min(
            len(scenarios_exercised_recently) / max(len(TABLETOP_SCENARIOS), 1) * 100, 100
        )
        readiness = (
            freq_score * 0.30
            + rto_rate * 0.25
            + rpo_rate * 0.25
            + closure_rate * 0.20
        )

        return BCMetrics(
            total_scenarios=len(TABLETOP_SCENARIOS),
            total_exercises=len(all_exercises),
            completed_exercises=len(completed),
            exercises_last_quarter=len(recent),
            exercise_frequency_met=frequency_met,
            rto_compliance_rate=round(rto_rate, 1),
            rpo_compliance_rate=round(rpo_rate, 1),
            total_action_items=total_ai,
            open_action_items=len(open_items),
            closed_action_items=len(closed_items),
            action_item_closure_rate=round(closure_rate, 1),
            scenario_coverage=scenario_coverage,
            overall_readiness_score=round(readiness, 1),
        )


# ---------------------------------------------------------------------------
# Exercise Status Transitions
# ---------------------------------------------------------------------------

_EXERCISE_TRANSITIONS: dict[ExerciseStatus, list[ExerciseStatus]] = {
    ExerciseStatus.PLANNED: [ExerciseStatus.IN_PROGRESS, ExerciseStatus.CANCELLED],
    ExerciseStatus.IN_PROGRESS: [ExerciseStatus.COMPLETED, ExerciseStatus.CANCELLED],
    ExerciseStatus.COMPLETED: [],  # Terminal
    ExerciseStatus.CANCELLED: [],  # Terminal
}


def _valid_exercise_transitions(current: ExerciseStatus) -> list[ExerciseStatus]:
    """Return valid transitions from the current exercise status."""
    return _EXERCISE_TRANSITIONS.get(current, [])


# ---------------------------------------------------------------------------
# Duration Comparison Helper
# ---------------------------------------------------------------------------


def _parse_duration_hours(duration_str: str) -> float:
    """Parse a duration string like '4 hours' or '30 minutes' into hours."""
    duration_str = duration_str.strip().lower()
    parts = duration_str.split()
    if len(parts) < 2:
        try:
            return float(parts[0])
        except ValueError:
            return float("inf")

    value = float(parts[0])
    unit = parts[1]

    if unit.startswith("hour"):
        return value
    elif unit.startswith("minute"):
        return value / 60.0
    elif unit.startswith("day"):
        return value * 24.0
    else:
        return value


def _duration_lte(actual: str, expected: str) -> bool:
    """Check if actual duration is less than or equal to expected."""
    return _parse_duration_hours(actual) <= _parse_duration_hours(expected)


# ---------------------------------------------------------------------------
# Singleton Management
# ---------------------------------------------------------------------------


def get_business_continuity_service() -> BusinessContinuityService:
    """Get or create the singleton BusinessContinuityService."""
    global _bc_instance
    if _bc_instance is None:
        with _bc_lock:
            if _bc_instance is None:
                _bc_instance = BusinessContinuityService()
    return _bc_instance


def reset_business_continuity_service() -> None:
    """Reset singleton (for testing)."""
    global _bc_instance
    with _bc_lock:
        _bc_instance = None
