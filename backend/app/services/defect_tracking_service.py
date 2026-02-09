"""Defect Tracking & Test Environment Management service.

QA-3: Pharma-grade defect tracking with SLA enforcement, forward-only
state machine, MTTR metrics, trend analysis, SLA breach detection,
duplicate linking, and test environment health monitoring.

Usage:
    from app.services.defect_tracking_service import get_defect_tracking_service

    service = get_defect_tracking_service()
    defect = service.create_defect(
        title="Screening engine returns wrong eligibility",
        description="...",
        severity=DefectSeverity.CRITICAL,
        category=DefectCategory.FUNCTIONAL,
        component="screening-engine",
        reported_by="qa-lead",
    )
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas.defect_tracking import (
    DefectCategory,
    DefectComment,
    DefectMetrics,
    DefectPriority,
    DefectRecord,
    DefectSeverity,
    DefectStatus,
    DefectTransition,
    DefectTrend,
    EnvironmentStatus,
    EnvironmentType,
    HealthCheck,
    SLA_HOURS,
    SLABreachRecord,
    TestEnvironment,
    TrendDataPoint,
    VALID_STATUS_TRANSITIONS,
)

logger = logging.getLogger(__name__)

# Singleton instance and lock
_defect_tracking_instance: DefectTrackingService | None = None
_defect_tracking_lock = Lock()


# ---------------------------------------------------------------------------
# Internal record models (service-layer, mutable)
# ---------------------------------------------------------------------------


class DefectInternalRecord(BaseModel):
    """Internal mutable defect record."""

    id: str = Field(default_factory=lambda: f"DEF-{uuid4().hex[:8].upper()}")
    title: str
    description: str
    severity: DefectSeverity
    priority: DefectPriority = DefectPriority.P2_MEDIUM
    status: DefectStatus = DefectStatus.NEW
    category: DefectCategory
    component: str
    reported_by: str
    assigned_to: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None
    resolution_notes: str | None = None
    steps_to_reproduce: str | None = None
    expected_behavior: str | None = None
    actual_behavior: str | None = None
    environment: str | None = None
    build_version: str | None = None
    linked_defects: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    sla_deadline: datetime | None = None


class CommentInternalRecord(BaseModel):
    """Internal comment record."""

    id: str = Field(default_factory=lambda: f"CMT-{uuid4().hex[:8].upper()}")
    defect_id: str
    author: str
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TransitionInternalRecord(BaseModel):
    """Internal transition audit record."""

    id: str = Field(default_factory=lambda: f"TRN-{uuid4().hex[:8].upper()}")
    defect_id: str
    from_status: DefectStatus
    to_status: DefectStatus
    transitioned_by: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str | None = None


class EnvironmentInternalRecord(BaseModel):
    """Internal test environment record."""

    id: str = Field(default_factory=lambda: f"ENV-{uuid4().hex[:8].upper()}")
    name: str
    env_type: EnvironmentType
    status: EnvironmentStatus = EnvironmentStatus.PROVISIONING
    description: str | None = None
    url: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_refreshed: datetime | None = None
    data_snapshot_date: datetime | None = None
    owner: str
    components: list[str] = Field(default_factory=list)
    health_checks: list[HealthCheck] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class DefectTrackingService:
    """In-memory defect tracking and test environment management service."""

    def __init__(self) -> None:
        self._defects: dict[str, DefectInternalRecord] = {}
        self._comments: dict[str, list[CommentInternalRecord]] = {}
        self._transitions: dict[str, list[TransitionInternalRecord]] = {}
        self._environments: dict[str, EnvironmentInternalRecord] = {}
        self._seed_data()

    # -------------------------------------------------------------------
    # Seed data
    # -------------------------------------------------------------------

    def _seed_data(self) -> None:
        """Pre-populate defects and environments for demo/testing."""
        now = datetime.now(timezone.utc)

        # ---- BLOCKER defects (2) ----

        # BLOCKER 1 - Resolved
        d1 = DefectInternalRecord(
            id="DEF-SEED-0001",
            title="Patient screening engine crashes on multi-site batch",
            description="Batch screening jobs crash with OOM when processing > 500 patients across multiple sites simultaneously.",
            severity=DefectSeverity.BLOCKER,
            priority=DefectPriority.P0_IMMEDIATE,
            status=DefectStatus.CLOSED,
            category=DefectCategory.FUNCTIONAL,
            component="screening-engine",
            reported_by="Sarah Chen",
            assigned_to="Marcus Johnson",
            created_at=now - timedelta(days=15),
            updated_at=now - timedelta(days=14, hours=20),
            resolved_at=now - timedelta(days=14, hours=20),
            resolution_notes="Implemented chunked processing with configurable batch size. Added memory guard rails.",
            steps_to_reproduce="1. Load 500+ patients\n2. Start multi-site batch screening\n3. Observe OOM crash after ~3 minutes",
            expected_behavior="Batch screening completes for all patients",
            actual_behavior="Process crashes with OutOfMemoryError",
            environment="QA",
            build_version="2.3.0-rc1",
            tags=["batch-processing", "memory", "P0"],
            sla_deadline=now - timedelta(days=15) + timedelta(hours=4),
        )
        self._defects[d1.id] = d1
        self._transitions[d1.id] = [
            TransitionInternalRecord(
                id="TRN-SEED-0001",
                defect_id=d1.id,
                from_status=DefectStatus.NEW,
                to_status=DefectStatus.TRIAGED,
                transitioned_by="QA Lead",
                timestamp=now - timedelta(days=15, hours=-0.5),
                reason="Critical impact on trial enrollment",
            ),
            TransitionInternalRecord(
                id="TRN-SEED-0002",
                defect_id=d1.id,
                from_status=DefectStatus.TRIAGED,
                to_status=DefectStatus.IN_PROGRESS,
                transitioned_by="Marcus Johnson",
                timestamp=now - timedelta(days=15, hours=-1),
            ),
            TransitionInternalRecord(
                id="TRN-SEED-0003",
                defect_id=d1.id,
                from_status=DefectStatus.IN_PROGRESS,
                to_status=DefectStatus.IN_REVIEW,
                transitioned_by="Marcus Johnson",
                timestamp=now - timedelta(days=14, hours=22),
            ),
            TransitionInternalRecord(
                id="TRN-SEED-0004",
                defect_id=d1.id,
                from_status=DefectStatus.IN_REVIEW,
                to_status=DefectStatus.VERIFIED,
                transitioned_by="QA Lead",
                timestamp=now - timedelta(days=14, hours=21),
            ),
            TransitionInternalRecord(
                id="TRN-SEED-0005",
                defect_id=d1.id,
                from_status=DefectStatus.VERIFIED,
                to_status=DefectStatus.CLOSED,
                transitioned_by="Sarah Chen",
                timestamp=now - timedelta(days=14, hours=20),
            ),
        ]
        self._comments[d1.id] = [
            CommentInternalRecord(
                id="CMT-SEED-0001",
                defect_id=d1.id,
                author="Marcus Johnson",
                content="Root cause identified: unbounded patient list loaded into memory. Will implement streaming/chunked approach.",
                created_at=now - timedelta(days=15, hours=-2),
            ),
        ]

        # BLOCKER 2 - In Progress
        d2 = DefectInternalRecord(
            id="DEF-SEED-0002",
            title="FHIR import pipeline drops observations silently",
            description="When importing FHIR bundles with > 100 observations, some observations are silently dropped without error logging. Data integrity violation.",
            severity=DefectSeverity.BLOCKER,
            priority=DefectPriority.P0_IMMEDIATE,
            status=DefectStatus.IN_PROGRESS,
            category=DefectCategory.DATA_INTEGRITY,
            component="fhir-import",
            reported_by="Dr. Emily Watson",
            assigned_to="Alex Rivera",
            created_at=now - timedelta(hours=6),
            updated_at=now - timedelta(hours=2),
            steps_to_reproduce="1. Create FHIR bundle with 150+ observations\n2. Import via /fhir/import\n3. Count imported observations - some missing",
            expected_behavior="All observations from bundle are imported",
            actual_behavior="Only ~95 of 150 observations are persisted",
            environment="UAT",
            build_version="2.4.0-beta",
            tags=["data-loss", "fhir", "P0", "regulatory-risk"],
            sla_deadline=now - timedelta(hours=6) + timedelta(hours=4),
        )
        self._defects[d2.id] = d2
        self._transitions[d2.id] = [
            TransitionInternalRecord(
                id="TRN-SEED-0006",
                defect_id=d2.id,
                from_status=DefectStatus.NEW,
                to_status=DefectStatus.TRIAGED,
                transitioned_by="QA Lead",
                timestamp=now - timedelta(hours=5),
                reason="Data integrity blocker - regulatory risk",
            ),
            TransitionInternalRecord(
                id="TRN-SEED-0007",
                defect_id=d2.id,
                from_status=DefectStatus.TRIAGED,
                to_status=DefectStatus.IN_PROGRESS,
                transitioned_by="Alex Rivera",
                timestamp=now - timedelta(hours=4),
            ),
        ]
        self._comments[d2.id] = []

        # ---- CRITICAL defects (3) ----

        d3 = DefectInternalRecord(
            id="DEF-SEED-0003",
            title="SQL injection vulnerability in patient search endpoint",
            description="The /patients/search endpoint does not properly parameterize user-supplied search terms, allowing SQL injection attacks.",
            severity=DefectSeverity.CRITICAL,
            priority=DefectPriority.P0_IMMEDIATE,
            status=DefectStatus.VERIFIED,
            category=DefectCategory.SECURITY,
            component="patient-search",
            reported_by="Security Team",
            assigned_to="Marcus Johnson",
            created_at=now - timedelta(days=3),
            updated_at=now - timedelta(days=1),
            resolved_at=now - timedelta(days=1),
            resolution_notes="Replaced string concatenation with parameterized queries. Added input sanitization layer.",
            environment="QA",
            build_version="2.3.1",
            tags=["security", "sqli", "urgent"],
            sla_deadline=now - timedelta(days=3) + timedelta(hours=24),
        )
        self._defects[d3.id] = d3
        self._transitions[d3.id] = []
        self._comments[d3.id] = []

        d4 = DefectInternalRecord(
            id="DEF-SEED-0004",
            title="PHI data exposed in application logs",
            description="Patient names and MRNs are being logged in plaintext in the application log files. HIPAA compliance violation.",
            severity=DefectSeverity.CRITICAL,
            priority=DefectPriority.P1_HIGH,
            status=DefectStatus.IN_REVIEW,
            category=DefectCategory.COMPLIANCE,
            component="logging-framework",
            reported_by="Compliance Officer",
            assigned_to="Priya Patel",
            created_at=now - timedelta(days=5),
            updated_at=now - timedelta(days=2),
            environment="STAGING",
            build_version="2.3.0",
            tags=["hipaa", "phi", "logging"],
            sla_deadline=now - timedelta(days=5) + timedelta(hours=24),
        )
        self._defects[d4.id] = d4
        self._transitions[d4.id] = []
        self._comments[d4.id] = []

        d5 = DefectInternalRecord(
            id="DEF-SEED-0005",
            title="Consent status not validated before data access",
            description="API endpoints serving patient data do not check consent status, allowing access to patient records with expired or revoked consent.",
            severity=DefectSeverity.CRITICAL,
            priority=DefectPriority.P1_HIGH,
            status=DefectStatus.TRIAGED,
            category=DefectCategory.DATA_INTEGRITY,
            component="consent-management",
            reported_by="Regulatory Affairs",
            assigned_to="Dev Team Lead",
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=1),
            environment="UAT",
            build_version="2.3.1",
            tags=["consent", "regulatory", "data-access"],
            sla_deadline=now - timedelta(days=2) + timedelta(hours=24),
        )
        self._defects[d5.id] = d5
        self._transitions[d5.id] = []
        self._comments[d5.id] = []

        # ---- MAJOR defects (5) ----

        d6 = DefectInternalRecord(
            id="DEF-SEED-0006",
            title="Trial eligibility criteria parser fails on nested boolean logic",
            description="Complex eligibility criteria with nested AND/OR groups are not parsed correctly, leading to incorrect patient matches.",
            severity=DefectSeverity.MAJOR,
            priority=DefectPriority.P2_MEDIUM,
            status=DefectStatus.IN_PROGRESS,
            category=DefectCategory.FUNCTIONAL,
            component="criteria-parser",
            reported_by="Clinical Operations",
            assigned_to="Alex Rivera",
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=3),
            environment="QA",
            build_version="2.3.0",
            tags=["eligibility", "parser"],
            sla_deadline=now - timedelta(days=10) + timedelta(hours=72),
        )
        self._defects[d6.id] = d6
        self._transitions[d6.id] = []
        self._comments[d6.id] = []

        d7 = DefectInternalRecord(
            id="DEF-SEED-0007",
            title="Dashboard charts render incorrectly on mobile viewports",
            description="Enrollment trend charts and site comparison bar charts overlap and become unreadable on screens < 768px wide.",
            severity=DefectSeverity.MAJOR,
            priority=DefectPriority.P2_MEDIUM,
            status=DefectStatus.NEW,
            category=DefectCategory.UI_UX,
            component="dashboard-frontend",
            reported_by="Product Manager",
            assigned_to=None,
            created_at=now - timedelta(days=7),
            updated_at=now - timedelta(days=7),
            environment="STAGING",
            build_version="2.3.1",
            tags=["responsive", "charts", "mobile"],
            sla_deadline=now - timedelta(days=7) + timedelta(hours=72),
        )
        self._defects[d7.id] = d7
        self._transitions[d7.id] = []
        self._comments[d7.id] = []

        d8 = DefectInternalRecord(
            id="DEF-SEED-0008",
            title="Medidata Rave integration timeout on large datasets",
            description="EDC export to Medidata Rave times out when exporting > 1000 CRF records. Connection pool exhaustion suspected.",
            severity=DefectSeverity.MAJOR,
            priority=DefectPriority.P2_MEDIUM,
            status=DefectStatus.IN_REVIEW,
            category=DefectCategory.INTEGRATION,
            component="medidata-connector",
            reported_by="Integration Team",
            assigned_to="Priya Patel",
            created_at=now - timedelta(days=8),
            updated_at=now - timedelta(days=4),
            environment="QA",
            build_version="2.3.0",
            tags=["medidata", "timeout", "integration"],
            sla_deadline=now - timedelta(days=8) + timedelta(hours=72),
        )
        self._defects[d8.id] = d8
        self._transitions[d8.id] = []
        self._comments[d8.id] = []

        d9 = DefectInternalRecord(
            id="DEF-SEED-0009",
            title="Screening score calculation differs between API and batch pipeline",
            description="Real-time API screening produces different eligibility scores than the nightly batch pipeline for the same patient/trial pair.",
            severity=DefectSeverity.MAJOR,
            priority=DefectPriority.P1_HIGH,
            status=DefectStatus.IN_PROGRESS,
            category=DefectCategory.REGRESSION,
            component="screening-engine",
            reported_by="QA Automation",
            assigned_to="Marcus Johnson",
            created_at=now - timedelta(days=4),
            updated_at=now - timedelta(days=2),
            environment="QA",
            build_version="2.3.1",
            tags=["screening", "regression", "consistency"],
            sla_deadline=now - timedelta(days=4) + timedelta(hours=72),
        )
        self._defects[d9.id] = d9
        self._transitions[d9.id] = []
        self._comments[d9.id] = []

        d10 = DefectInternalRecord(
            id="DEF-SEED-0010",
            title="API response times degrade under concurrent load > 200 RPS",
            description="P99 latency exceeds 5s when API receives > 200 requests per second. Connection pool sizing and query optimization needed.",
            severity=DefectSeverity.MAJOR,
            priority=DefectPriority.P2_MEDIUM,
            status=DefectStatus.TRIAGED,
            category=DefectCategory.PERFORMANCE,
            component="api-gateway",
            reported_by="Performance Team",
            assigned_to=None,
            created_at=now - timedelta(days=6),
            updated_at=now - timedelta(days=5),
            environment="PRE_PRODUCTION",
            build_version="2.3.1",
            tags=["performance", "latency", "scalability"],
            sla_deadline=now - timedelta(days=6) + timedelta(hours=72),
        )
        self._defects[d10.id] = d10
        self._transitions[d10.id] = []
        self._comments[d10.id] = []

        # ---- MINOR defects (4) ----

        d11 = DefectInternalRecord(
            id="DEF-SEED-0011",
            title="Export CSV missing column headers for custom fields",
            description="When exporting patient data to CSV with custom fields enabled, the headers for custom fields are omitted.",
            severity=DefectSeverity.MINOR,
            priority=DefectPriority.P3_LOW,
            status=DefectStatus.NEW,
            category=DefectCategory.FUNCTIONAL,
            component="data-export",
            reported_by="Site Coordinator",
            created_at=now - timedelta(days=12),
            updated_at=now - timedelta(days=12),
            environment="QA",
            build_version="2.3.0",
            tags=["export", "csv"],
            sla_deadline=now - timedelta(days=12) + timedelta(hours=168),
        )
        self._defects[d11.id] = d11
        self._transitions[d11.id] = []
        self._comments[d11.id] = []

        d12 = DefectInternalRecord(
            id="DEF-SEED-0012",
            title="Date picker does not respect user locale settings",
            description="Date picker always shows MM/DD/YYYY format regardless of user locale preference (should show DD/MM/YYYY for EU users).",
            severity=DefectSeverity.MINOR,
            priority=DefectPriority.P3_LOW,
            status=DefectStatus.IN_PROGRESS,
            category=DefectCategory.UI_UX,
            component="dashboard-frontend",
            reported_by="EU Site Admin",
            assigned_to="Frontend Dev",
            created_at=now - timedelta(days=14),
            updated_at=now - timedelta(days=9),
            environment="STAGING",
            build_version="2.3.0",
            tags=["i18n", "locale", "datepicker"],
            sla_deadline=now - timedelta(days=14) + timedelta(hours=168),
        )
        self._defects[d12.id] = d12
        self._transitions[d12.id] = []
        self._comments[d12.id] = []

        d13 = DefectInternalRecord(
            id="DEF-SEED-0013",
            title="Audit log entries missing user agent string",
            description="HTTP user agent information is not captured in audit log entries, reducing forensic capability.",
            severity=DefectSeverity.MINOR,
            priority=DefectPriority.P3_LOW,
            status=DefectStatus.CLOSED,
            category=DefectCategory.COMPLIANCE,
            component="audit-service",
            reported_by="Security Team",
            assigned_to="Priya Patel",
            created_at=now - timedelta(days=20),
            updated_at=now - timedelta(days=16),
            resolved_at=now - timedelta(days=16),
            resolution_notes="Added user agent capture to audit middleware. Backfilled missing entries where possible.",
            environment="STAGING",
            build_version="2.2.1",
            tags=["audit", "compliance"],
            sla_deadline=now - timedelta(days=20) + timedelta(hours=168),
        )
        self._defects[d13.id] = d13
        self._transitions[d13.id] = []
        self._comments[d13.id] = []

        d14 = DefectInternalRecord(
            id="DEF-SEED-0014",
            title="Notification emails sent with wrong reply-to address",
            description="Patient notification emails use noreply@example.com instead of the configured site coordinator email.",
            severity=DefectSeverity.MINOR,
            priority=DefectPriority.P3_LOW,
            status=DefectStatus.VERIFIED,
            category=DefectCategory.FUNCTIONAL,
            component="notification-service",
            reported_by="Site Coordinator",
            assigned_to="Alex Rivera",
            created_at=now - timedelta(days=11),
            updated_at=now - timedelta(days=7),
            resolved_at=now - timedelta(days=7),
            resolution_notes="Fixed email template to use site coordinator email from configuration.",
            environment="QA",
            build_version="2.3.0",
            tags=["email", "notification"],
            sla_deadline=now - timedelta(days=11) + timedelta(hours=168),
        )
        self._defects[d14.id] = d14
        self._transitions[d14.id] = []
        self._comments[d14.id] = []

        # ---- TRIVIAL defects (2) ----

        d15 = DefectInternalRecord(
            id="DEF-SEED-0015",
            title="Typo in consent form template: 'recieve' should be 'receive'",
            description="Consent form template contains a spelling error in paragraph 3.",
            severity=DefectSeverity.TRIVIAL,
            priority=DefectPriority.P4_BACKLOG,
            status=DefectStatus.NEW,
            category=DefectCategory.UI_UX,
            component="consent-forms",
            reported_by="Legal Review",
            created_at=now - timedelta(days=18),
            updated_at=now - timedelta(days=18),
            environment="STAGING",
            build_version="2.3.0",
            tags=["typo", "consent"],
            sla_deadline=now - timedelta(days=18) + timedelta(hours=720),
        )
        self._defects[d15.id] = d15
        self._transitions[d15.id] = []
        self._comments[d15.id] = []

        d16 = DefectInternalRecord(
            id="DEF-SEED-0016",
            title="Tooltip text wraps awkwardly on narrow info icons",
            description="Tooltip for 'Eligibility Score' info icon wraps mid-word on some browsers.",
            severity=DefectSeverity.TRIVIAL,
            priority=DefectPriority.P4_BACKLOG,
            status=DefectStatus.CLOSED,
            category=DefectCategory.UI_UX,
            component="dashboard-frontend",
            reported_by="UX Designer",
            assigned_to="Frontend Dev",
            created_at=now - timedelta(days=25),
            updated_at=now - timedelta(days=22),
            resolved_at=now - timedelta(days=22),
            resolution_notes="Added min-width and word-break CSS rules to tooltip component.",
            environment="QA",
            build_version="2.2.0",
            tags=["tooltip", "css"],
            sla_deadline=now - timedelta(days=25) + timedelta(hours=720),
        )
        self._defects[d16.id] = d16
        self._transitions[d16.id] = []
        self._comments[d16.id] = []

        # ---- Test Environments (5) ----

        env1 = EnvironmentInternalRecord(
            id="ENV-SEED-0001",
            name="Development",
            env_type=EnvironmentType.DEVELOPMENT,
            status=EnvironmentStatus.READY,
            description="Local development environment with mocked external services",
            url="http://localhost:8000",
            created_at=now - timedelta(days=180),
            last_refreshed=now - timedelta(hours=2),
            data_snapshot_date=now - timedelta(days=1),
            owner="Engineering Lead",
            components=["api", "frontend", "database", "redis"],
            health_checks=[
                HealthCheck(name="api", status="healthy", last_checked=now - timedelta(minutes=5), response_time_ms=12.5),
                HealthCheck(name="database", status="healthy", last_checked=now - timedelta(minutes=5), response_time_ms=3.2),
                HealthCheck(name="redis", status="healthy", last_checked=now - timedelta(minutes=5), response_time_ms=1.1),
            ],
        )
        self._environments[env1.id] = env1

        env2 = EnvironmentInternalRecord(
            id="ENV-SEED-0002",
            name="Staging",
            env_type=EnvironmentType.STAGING,
            status=EnvironmentStatus.READY,
            description="Staging environment mirroring production configuration",
            url="https://staging.clinical-trial.example.com",
            created_at=now - timedelta(days=120),
            last_refreshed=now - timedelta(hours=12),
            data_snapshot_date=now - timedelta(days=3),
            owner="DevOps Lead",
            components=["api", "frontend", "database", "redis", "neo4j", "monitoring"],
            health_checks=[
                HealthCheck(name="api", status="healthy", last_checked=now - timedelta(minutes=10), response_time_ms=45.3),
                HealthCheck(name="database", status="healthy", last_checked=now - timedelta(minutes=10), response_time_ms=8.7),
                HealthCheck(name="neo4j", status="degraded", last_checked=now - timedelta(minutes=10), response_time_ms=250.0),
            ],
        )
        self._environments[env2.id] = env2

        env3 = EnvironmentInternalRecord(
            id="ENV-SEED-0003",
            name="QA Automated",
            env_type=EnvironmentType.QA,
            status=EnvironmentStatus.IN_USE,
            description="Dedicated QA environment for automated regression testing",
            url="https://qa.clinical-trial.example.com",
            created_at=now - timedelta(days=90),
            last_refreshed=now - timedelta(hours=6),
            data_snapshot_date=now - timedelta(days=1),
            owner="QA Lead",
            components=["api", "frontend", "database", "redis", "selenium-grid"],
            health_checks=[
                HealthCheck(name="api", status="healthy", last_checked=now - timedelta(minutes=2), response_time_ms=23.1),
                HealthCheck(name="database", status="healthy", last_checked=now - timedelta(minutes=2), response_time_ms=5.4),
                HealthCheck(name="selenium-grid", status="healthy", last_checked=now - timedelta(minutes=2), response_time_ms=150.0),
            ],
        )
        self._environments[env3.id] = env3

        env4 = EnvironmentInternalRecord(
            id="ENV-SEED-0004",
            name="UAT",
            env_type=EnvironmentType.UAT,
            status=EnvironmentStatus.READY,
            description="User acceptance testing environment with anonymized production data",
            url="https://uat.clinical-trial.example.com",
            created_at=now - timedelta(days=60),
            last_refreshed=now - timedelta(days=2),
            data_snapshot_date=now - timedelta(days=7),
            owner="Clinical Operations Lead",
            components=["api", "frontend", "database", "redis", "neo4j"],
            health_checks=[
                HealthCheck(name="api", status="healthy", last_checked=now - timedelta(minutes=15), response_time_ms=38.9),
                HealthCheck(name="database", status="healthy", last_checked=now - timedelta(minutes=15), response_time_ms=11.2),
                HealthCheck(name="neo4j", status="healthy", last_checked=now - timedelta(minutes=15), response_time_ms=89.3),
            ],
        )
        self._environments[env4.id] = env4

        env5 = EnvironmentInternalRecord(
            id="ENV-SEED-0005",
            name="Pre-Production",
            env_type=EnvironmentType.PRE_PRODUCTION,
            status=EnvironmentStatus.MAINTENANCE,
            description="Pre-production environment for final validation before production deployment",
            url="https://preprod.clinical-trial.example.com",
            created_at=now - timedelta(days=45),
            last_refreshed=now - timedelta(days=5),
            data_snapshot_date=now - timedelta(days=14),
            owner="Release Manager",
            components=["api", "frontend", "database", "redis", "neo4j", "monitoring", "waf"],
            health_checks=[
                HealthCheck(name="api", status="unhealthy", last_checked=now - timedelta(hours=1), response_time_ms=0.0),
                HealthCheck(name="database", status="healthy", last_checked=now - timedelta(hours=1), response_time_ms=15.6),
            ],
        )
        self._environments[env5.id] = env5

        logger.info(
            f"Defect tracking service seeded: {len(self._defects)} defects, "
            f"{len(self._environments)} environments"
        )

    # -------------------------------------------------------------------
    # Defect CRUD
    # -------------------------------------------------------------------

    def create_defect(
        self,
        *,
        title: str,
        description: str,
        severity: DefectSeverity,
        category: DefectCategory,
        component: str,
        reported_by: str,
        priority: DefectPriority = DefectPriority.P2_MEDIUM,
        assigned_to: str | None = None,
        steps_to_reproduce: str | None = None,
        expected_behavior: str | None = None,
        actual_behavior: str | None = None,
        environment: str | None = None,
        build_version: str | None = None,
        tags: list[str] | None = None,
    ) -> DefectInternalRecord:
        """Create a new defect with auto-calculated SLA deadline."""
        now = datetime.now(timezone.utc)
        sla_hours = SLA_HOURS[severity]
        sla_deadline = now + timedelta(hours=sla_hours)

        record = DefectInternalRecord(
            title=title,
            description=description,
            severity=severity,
            priority=priority,
            status=DefectStatus.NEW,
            category=category,
            component=component,
            reported_by=reported_by,
            assigned_to=assigned_to,
            created_at=now,
            updated_at=now,
            steps_to_reproduce=steps_to_reproduce,
            expected_behavior=expected_behavior,
            actual_behavior=actual_behavior,
            environment=environment,
            build_version=build_version,
            tags=tags or [],
            sla_deadline=sla_deadline,
        )
        self._defects[record.id] = record
        self._comments[record.id] = []
        self._transitions[record.id] = []
        logger.info(f"Created defect {record.id}: {title} [{severity.value}]")
        return record

    def get_defect(self, defect_id: str) -> DefectInternalRecord:
        """Get a defect by ID. Raises KeyError if not found."""
        if defect_id not in self._defects:
            raise KeyError(f"Defect {defect_id} not found")
        return self._defects[defect_id]

    def list_defects(
        self,
        *,
        severity: DefectSeverity | None = None,
        status: DefectStatus | None = None,
        category: DefectCategory | None = None,
        assigned_to: str | None = None,
        component: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[DefectInternalRecord], int]:
        """List defects with optional filters and pagination."""
        results = list(self._defects.values())

        if severity is not None:
            results = [d for d in results if d.severity == severity]
        if status is not None:
            results = [d for d in results if d.status == status]
        if category is not None:
            results = [d for d in results if d.category == category]
        if assigned_to is not None:
            results = [d for d in results if d.assigned_to == assigned_to]
        if component is not None:
            results = [d for d in results if d.component == component]

        # Sort by created_at descending (newest first)
        results.sort(key=lambda d: d.created_at, reverse=True)
        total = len(results)
        return results[offset : offset + limit], total

    def update_defect(
        self,
        defect_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        priority: DefectPriority | None = None,
        category: DefectCategory | None = None,
        component: str | None = None,
        assigned_to: str | None = None,
        steps_to_reproduce: str | None = None,
        expected_behavior: str | None = None,
        actual_behavior: str | None = None,
        resolution_notes: str | None = None,
        tags: list[str] | None = None,
    ) -> DefectInternalRecord:
        """Update defect fields (not status - use transition_defect)."""
        record = self.get_defect(defect_id)
        if title is not None:
            record.title = title
        if description is not None:
            record.description = description
        if priority is not None:
            record.priority = priority
        if category is not None:
            record.category = category
        if component is not None:
            record.component = component
        if assigned_to is not None:
            record.assigned_to = assigned_to
        if steps_to_reproduce is not None:
            record.steps_to_reproduce = steps_to_reproduce
        if expected_behavior is not None:
            record.expected_behavior = expected_behavior
        if actual_behavior is not None:
            record.actual_behavior = actual_behavior
        if resolution_notes is not None:
            record.resolution_notes = resolution_notes
        if tags is not None:
            record.tags = tags
        record.updated_at = datetime.now(timezone.utc)
        return record

    def delete_defect(self, defect_id: str) -> None:
        """Delete a defect and its associated data. Raises KeyError if not found."""
        if defect_id not in self._defects:
            raise KeyError(f"Defect {defect_id} not found")
        del self._defects[defect_id]
        self._comments.pop(defect_id, None)
        self._transitions.pop(defect_id, None)

    # -------------------------------------------------------------------
    # Status Transitions
    # -------------------------------------------------------------------

    def transition_defect(
        self,
        defect_id: str,
        *,
        to_status: DefectStatus,
        transitioned_by: str,
        reason: str | None = None,
    ) -> DefectInternalRecord:
        """Transition a defect to a new status.

        Validates against the forward-only state machine.
        Raises ValueError for invalid transitions.
        """
        record = self.get_defect(defect_id)
        current = record.status
        valid_targets = VALID_STATUS_TRANSITIONS.get(current, [])

        if to_status not in valid_targets:
            raise ValueError(
                f"Invalid transition from {current.value} to {to_status.value}. "
                f"Valid targets: {[s.value for s in valid_targets]}"
            )

        now = datetime.now(timezone.utc)
        transition = TransitionInternalRecord(
            defect_id=defect_id,
            from_status=current,
            to_status=to_status,
            transitioned_by=transitioned_by,
            timestamp=now,
            reason=reason,
        )

        if defect_id not in self._transitions:
            self._transitions[defect_id] = []
        self._transitions[defect_id].append(transition)

        record.status = to_status
        record.updated_at = now

        # Mark resolved_at when entering terminal or verified/closed states
        if to_status in (DefectStatus.CLOSED, DefectStatus.WONT_FIX, DefectStatus.DUPLICATE):
            if record.resolved_at is None:
                record.resolved_at = now

        # Clear resolved_at on reopen
        if to_status == DefectStatus.REOPENED:
            record.resolved_at = None

        logger.info(f"Defect {defect_id}: {current.value} -> {to_status.value} by {transitioned_by}")
        return record

    def get_transitions(self, defect_id: str) -> list[TransitionInternalRecord]:
        """Get transition history for a defect."""
        self.get_defect(defect_id)  # Validate exists
        return self._transitions.get(defect_id, [])

    # -------------------------------------------------------------------
    # Comments
    # -------------------------------------------------------------------

    def add_comment(
        self,
        defect_id: str,
        *,
        author: str,
        content: str,
    ) -> CommentInternalRecord:
        """Add a comment to a defect."""
        self.get_defect(defect_id)  # Validate exists
        comment = CommentInternalRecord(
            defect_id=defect_id,
            author=author,
            content=content,
        )
        if defect_id not in self._comments:
            self._comments[defect_id] = []
        self._comments[defect_id].append(comment)
        return comment

    def get_comments(self, defect_id: str) -> list[CommentInternalRecord]:
        """Get all comments for a defect."""
        self.get_defect(defect_id)  # Validate exists
        return self._comments.get(defect_id, [])

    def delete_comment(self, defect_id: str, comment_id: str) -> None:
        """Delete a specific comment. Raises KeyError if not found."""
        self.get_defect(defect_id)
        comments = self._comments.get(defect_id, [])
        for i, c in enumerate(comments):
            if c.id == comment_id:
                comments.pop(i)
                return
        raise KeyError(f"Comment {comment_id} not found on defect {defect_id}")

    # -------------------------------------------------------------------
    # Test Environment CRUD
    # -------------------------------------------------------------------

    def create_environment(
        self,
        *,
        name: str,
        env_type: EnvironmentType,
        owner: str,
        description: str | None = None,
        url: str | None = None,
        components: list[str] | None = None,
    ) -> EnvironmentInternalRecord:
        """Create a new test environment."""
        record = EnvironmentInternalRecord(
            name=name,
            env_type=env_type,
            status=EnvironmentStatus.PROVISIONING,
            description=description,
            url=url,
            owner=owner,
            components=components or [],
        )
        self._environments[record.id] = record
        logger.info(f"Created environment {record.id}: {name} [{env_type.value}]")
        return record

    def get_environment(self, env_id: str) -> EnvironmentInternalRecord:
        """Get a test environment by ID. Raises KeyError if not found."""
        if env_id not in self._environments:
            raise KeyError(f"Environment {env_id} not found")
        return self._environments[env_id]

    def list_environments(
        self,
        *,
        env_type: EnvironmentType | None = None,
        status: EnvironmentStatus | None = None,
    ) -> list[EnvironmentInternalRecord]:
        """List test environments with optional filters."""
        results = list(self._environments.values())
        if env_type is not None:
            results = [e for e in results if e.env_type == env_type]
        if status is not None:
            results = [e for e in results if e.status == status]
        return results

    def update_environment(
        self,
        env_id: str,
        *,
        name: str | None = None,
        status: EnvironmentStatus | None = None,
        description: str | None = None,
        url: str | None = None,
        owner: str | None = None,
        components: list[str] | None = None,
    ) -> EnvironmentInternalRecord:
        """Update a test environment."""
        record = self.get_environment(env_id)
        if name is not None:
            record.name = name
        if status is not None:
            record.status = status
        if description is not None:
            record.description = description
        if url is not None:
            record.url = url
        if owner is not None:
            record.owner = owner
        if components is not None:
            record.components = components
        return record

    def update_health_checks(
        self, env_id: str, health_checks: list[HealthCheck]
    ) -> EnvironmentInternalRecord:
        """Update health check results for an environment."""
        record = self.get_environment(env_id)
        record.health_checks = health_checks
        record.last_refreshed = datetime.now(timezone.utc)
        return record

    def delete_environment(self, env_id: str) -> None:
        """Delete a test environment. Raises KeyError if not found."""
        if env_id not in self._environments:
            raise KeyError(f"Environment {env_id} not found")
        del self._environments[env_id]

    # -------------------------------------------------------------------
    # Duplicate Linking
    # -------------------------------------------------------------------

    def link_duplicate(
        self,
        defect_id: str,
        *,
        duplicate_of: str,
        linked_by: str,
    ) -> DefectInternalRecord:
        """Mark a defect as duplicate of another and link them.

        Transitions the defect to DUPLICATE status and creates a bidirectional link.
        Raises ValueError if source defect cannot transition to DUPLICATE.
        """
        # Validate both exist
        source = self.get_defect(defect_id)
        target = self.get_defect(duplicate_of)

        # Transition to DUPLICATE
        self.transition_defect(
            defect_id,
            to_status=DefectStatus.DUPLICATE,
            transitioned_by=linked_by,
            reason=f"Duplicate of {duplicate_of}",
        )

        # Add bidirectional links
        if duplicate_of not in source.linked_defects:
            source.linked_defects.append(duplicate_of)
        if defect_id not in target.linked_defects:
            target.linked_defects.append(defect_id)

        return source

    # -------------------------------------------------------------------
    # Metrics & Analytics
    # -------------------------------------------------------------------

    def get_metrics(self) -> DefectMetrics:
        """Compute aggregate defect metrics."""
        defects = list(self._defects.values())
        total = len(defects)

        # By severity
        by_severity: dict[str, int] = {}
        for sev in DefectSeverity:
            count = sum(1 for d in defects if d.severity == sev)
            if count > 0:
                by_severity[sev.value] = count

        # By status
        by_status: dict[str, int] = {}
        for st in DefectStatus:
            count = sum(1 for d in defects if d.status == st)
            if count > 0:
                by_status[st.value] = count

        # By category
        by_category: dict[str, int] = {}
        for cat in DefectCategory:
            count = sum(1 for d in defects if d.category == cat)
            if count > 0:
                by_category[cat.value] = count

        # MTTR (mean time to resolve) in hours
        resolved = [d for d in defects if d.resolved_at is not None]
        if resolved:
            total_hours = sum(
                (d.resolved_at - d.created_at).total_seconds() / 3600
                for d in resolved
            )
            mttr_hours = round(total_hours / len(resolved), 2)
        else:
            mttr_hours = 0.0

        # SLA compliance rate
        resolved_or_terminal = [
            d for d in defects
            if d.status in (DefectStatus.CLOSED, DefectStatus.WONT_FIX, DefectStatus.DUPLICATE, DefectStatus.VERIFIED)
            and d.resolved_at is not None
            and d.sla_deadline is not None
        ]
        if resolved_or_terminal:
            within_sla = sum(1 for d in resolved_or_terminal if d.resolved_at <= d.sla_deadline)
            sla_compliance_rate = round(within_sla / len(resolved_or_terminal) * 100, 2)
        else:
            sla_compliance_rate = 100.0

        # Reopen rate
        all_transitions = []
        for t_list in self._transitions.values():
            all_transitions.extend(t_list)
        reopen_count = sum(1 for t in all_transitions if t.to_status == DefectStatus.REOPENED)
        close_count = sum(1 for t in all_transitions if t.to_status == DefectStatus.CLOSED)
        if close_count > 0:
            reopen_rate = round(reopen_count / close_count * 100, 2)
        else:
            reopen_rate = 0.0

        # Aging buckets for open defects
        now = datetime.now(timezone.utc)
        open_statuses = {
            DefectStatus.NEW, DefectStatus.TRIAGED, DefectStatus.IN_PROGRESS,
            DefectStatus.IN_REVIEW, DefectStatus.REOPENED,
        }
        open_defects = [d for d in defects if d.status in open_statuses]
        aging_buckets = {"0-24h": 0, "24-72h": 0, "72h-1w": 0, "1w+": 0}
        for d in open_defects:
            age_hours = (now - d.created_at).total_seconds() / 3600
            if age_hours <= 24:
                aging_buckets["0-24h"] += 1
            elif age_hours <= 72:
                aging_buckets["24-72h"] += 1
            elif age_hours <= 168:
                aging_buckets["72h-1w"] += 1
            else:
                aging_buckets["1w+"] += 1

        return DefectMetrics(
            total=total,
            by_severity=by_severity,
            by_status=by_status,
            by_category=by_category,
            mttr_hours=mttr_hours,
            sla_compliance_rate=sla_compliance_rate,
            reopen_rate=reopen_rate,
            aging_buckets=aging_buckets,
        )

    def get_trends(self, period_days: int = 30) -> DefectTrend:
        """Compute defect open/close trends over the specified period."""
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=period_days)
        defects = list(self._defects.values())

        data_points: list[TrendDataPoint] = []
        total_opened = 0
        total_closed = 0

        for day_offset in range(period_days):
            day_start = start + timedelta(days=day_offset)
            day_end = day_start + timedelta(days=1)
            date_str = day_start.strftime("%Y-%m-%d")

            opened = sum(
                1 for d in defects
                if day_start <= d.created_at < day_end
            )
            closed = sum(
                1 for d in defects
                if d.resolved_at is not None and day_start <= d.resolved_at < day_end
            )

            total_opened += opened
            total_closed += closed
            data_points.append(TrendDataPoint(date=date_str, opened=opened, closed=closed))

        return DefectTrend(
            period_days=period_days,
            data_points=data_points,
            total_opened=total_opened,
            total_closed=total_closed,
            net_change=total_opened - total_closed,
        )

    def get_sla_breaches(self) -> list[SLABreachRecord]:
        """Find defects that have breached or are at risk of breaching SLA."""
        now = datetime.now(timezone.utc)
        open_statuses = {
            DefectStatus.NEW, DefectStatus.TRIAGED, DefectStatus.IN_PROGRESS,
            DefectStatus.IN_REVIEW, DefectStatus.REOPENED,
        }
        results: list[SLABreachRecord] = []

        for d in self._defects.values():
            if d.status not in open_statuses or d.sla_deadline is None:
                continue
            hours_overdue = (now - d.sla_deadline).total_seconds() / 3600
            results.append(SLABreachRecord(
                defect_id=d.id,
                title=d.title,
                severity=d.severity,
                sla_deadline=d.sla_deadline,
                hours_overdue=round(hours_overdue, 2),
                status=d.status,
                assigned_to=d.assigned_to,
            ))

        # Sort by hours_overdue descending (most overdue first)
        results.sort(key=lambda r: r.hours_overdue, reverse=True)
        return results

    # -------------------------------------------------------------------
    # Conversion helpers
    # -------------------------------------------------------------------

    def defect_to_schema(self, record: DefectInternalRecord) -> DefectRecord:
        """Convert internal record to API response schema."""
        return DefectRecord(
            id=record.id,
            title=record.title,
            description=record.description,
            severity=record.severity,
            priority=record.priority,
            status=record.status,
            category=record.category,
            component=record.component,
            reported_by=record.reported_by,
            assigned_to=record.assigned_to,
            created_at=record.created_at,
            updated_at=record.updated_at,
            resolved_at=record.resolved_at,
            resolution_notes=record.resolution_notes,
            steps_to_reproduce=record.steps_to_reproduce,
            expected_behavior=record.expected_behavior,
            actual_behavior=record.actual_behavior,
            environment=record.environment,
            build_version=record.build_version,
            linked_defects=record.linked_defects,
            tags=record.tags,
            sla_deadline=record.sla_deadline,
        )

    def comment_to_schema(self, record: CommentInternalRecord) -> DefectComment:
        """Convert internal comment to API response schema."""
        return DefectComment(
            id=record.id,
            defect_id=record.defect_id,
            author=record.author,
            content=record.content,
            created_at=record.created_at,
        )

    def transition_to_schema(self, record: TransitionInternalRecord) -> DefectTransition:
        """Convert internal transition to API response schema."""
        return DefectTransition(
            id=record.id,
            defect_id=record.defect_id,
            from_status=record.from_status,
            to_status=record.to_status,
            transitioned_by=record.transitioned_by,
            timestamp=record.timestamp,
            reason=record.reason,
        )

    def environment_to_schema(self, record: EnvironmentInternalRecord) -> TestEnvironment:
        """Convert internal environment to API response schema."""
        return TestEnvironment(
            id=record.id,
            name=record.name,
            env_type=record.env_type,
            status=record.status,
            description=record.description,
            url=record.url,
            created_at=record.created_at,
            last_refreshed=record.last_refreshed,
            data_snapshot_date=record.data_snapshot_date,
            owner=record.owner,
            components=record.components,
            health_checks=record.health_checks,
        )


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------


def get_defect_tracking_service() -> DefectTrackingService:
    """Get or create the singleton DefectTrackingService instance."""
    global _defect_tracking_instance
    if _defect_tracking_instance is None:
        with _defect_tracking_lock:
            if _defect_tracking_instance is None:
                _defect_tracking_instance = DefectTrackingService()
                logger.info("DefectTrackingService singleton initialized")
    return _defect_tracking_instance


def reset_defect_tracking_service() -> None:
    """Reset the singleton for testing."""
    global _defect_tracking_instance
    with _defect_tracking_lock:
        _defect_tracking_instance = None
