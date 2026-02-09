"""Release Management & Deployment Tracking service.

VPE-8: Provides release lifecycle management, deployment tracking with
blue-green/canary/rolling strategies, release gates, rollback capabilities,
and DORA metrics computation.

Usage:
    from app.services.release_management_service import get_release_management_service

    service = get_release_management_service()
    release = service.create_release(
        version="2.3.0",
        title="Patient Matching Improvements",
        release_type=ReleaseType.MINOR,
        release_manager="release-lead",
    )
"""

from __future__ import annotations

import logging
import random
import re
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas.release_management import (
    Deployment,
    DeploymentListResponse,
    DeploymentStatus,
    DeploymentType,
    Environment,
    GateName,
    GateStatus,
    GateUpdateRequest,
    Release,
    ReleaseGate,
    ReleaseGateListResponse,
    ReleaseHistoryEntry,
    ReleaseHistoryResponse,
    ReleaseMetrics,
    ReleaseReadinessResponse,
    ReleaseStatus,
    ReleaseType,
)

logger = logging.getLogger(__name__)

# Singleton instance and lock
_release_mgmt_instance: ReleaseManagementService | None = None
_release_mgmt_lock = Lock()

# Semver regex pattern
SEMVER_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)

# Valid release status transitions
VALID_RELEASE_TRANSITIONS: dict[ReleaseStatus, list[ReleaseStatus]] = {
    ReleaseStatus.PLANNING: [ReleaseStatus.DEVELOPMENT, ReleaseStatus.CANCELLED],
    ReleaseStatus.DEVELOPMENT: [ReleaseStatus.CODE_FREEZE, ReleaseStatus.CANCELLED],
    ReleaseStatus.CODE_FREEZE: [
        ReleaseStatus.TESTING,
        ReleaseStatus.DEVELOPMENT,
        ReleaseStatus.CANCELLED,
    ],
    ReleaseStatus.TESTING: [
        ReleaseStatus.STAGING,
        ReleaseStatus.CODE_FREEZE,
        ReleaseStatus.CANCELLED,
    ],
    ReleaseStatus.STAGING: [
        ReleaseStatus.APPROVED,
        ReleaseStatus.TESTING,
        ReleaseStatus.CANCELLED,
    ],
    ReleaseStatus.APPROVED: [
        ReleaseStatus.DEPLOYING,
        ReleaseStatus.CANCELLED,
    ],
    ReleaseStatus.DEPLOYING: [
        ReleaseStatus.DEPLOYED,
        ReleaseStatus.ROLLED_BACK,
    ],
    ReleaseStatus.DEPLOYED: [ReleaseStatus.ROLLED_BACK],
    ReleaseStatus.ROLLED_BACK: [ReleaseStatus.PLANNING],
    ReleaseStatus.CANCELLED: [],  # Terminal
}


# ---------------------------------------------------------------------------
# Internal record models
# ---------------------------------------------------------------------------


class ReleaseRecord(BaseModel):
    """Internal release record."""

    id: str = Field(default_factory=lambda: f"REL-{uuid4().hex[:8].upper()}")
    version: str
    title: str
    description: str | None = None
    status: ReleaseStatus = ReleaseStatus.PLANNING
    release_type: ReleaseType = ReleaseType.MINOR
    features: list[str] = Field(default_factory=list)
    bug_fixes: list[str] = Field(default_factory=list)
    breaking_changes: list[str] = Field(default_factory=list)
    release_manager: str = ""
    planned_date: datetime | None = None
    actual_date: datetime | None = None
    changelog: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DeploymentRecord(BaseModel):
    """Internal deployment record."""

    id: str = Field(default_factory=lambda: f"DEP-{uuid4().hex[:8].upper()}")
    release_id: str
    environment: Environment = Environment.DEVELOPMENT
    deployment_type: DeploymentType = DeploymentType.BLUE_GREEN
    status: DeploymentStatus = DeploymentStatus.PENDING
    deployed_by: str = ""
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    health_check_passed: bool | None = None
    rollback_available: bool = True
    rollback_to_version: str | None = None
    notes: str | None = None


class GateRecord(BaseModel):
    """Internal release gate record."""

    id: str = Field(default_factory=lambda: f"GATE-{uuid4().hex[:8].upper()}")
    release_id: str
    gate_name: GateName
    status: GateStatus = GateStatus.PENDING
    reviewer: str | None = None
    reviewed_at: datetime | None = None
    comments: str | None = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ReleaseManagementService:
    """In-memory release management service with DORA metrics."""

    def __init__(self) -> None:
        self._releases: dict[str, ReleaseRecord] = {}
        self._deployments: dict[str, DeploymentRecord] = {}
        self._gates: dict[str, GateRecord] = {}
        self._seed_data()

    # -------------------------------------------------------------------
    # Seed data
    # -------------------------------------------------------------------

    def _seed_data(self) -> None:
        """Pre-populate releases, deployments, and gates for demo."""
        now = datetime.now(timezone.utc)

        # Release v2.0.0 - Deployed successfully
        r1 = ReleaseRecord(
            id="REL-SEED-0001",
            version="2.0.0",
            title="Patient Recruitment Platform Launch",
            description="Initial release of the clinical trial patient recruitment platform",
            status=ReleaseStatus.DEPLOYED,
            release_type=ReleaseType.MAJOR,
            features=[
                "Patient screening engine",
                "Trial eligibility matching",
                "Site dashboard",
                "FHIR data import",
            ],
            bug_fixes=[],
            breaking_changes=["New database schema - migration required"],
            release_manager="Sarah Chen",
            planned_date=now - timedelta(days=90),
            actual_date=now - timedelta(days=88),
            changelog="## v2.0.0\n- Patient screening engine\n- Trial eligibility matching\n- Site dashboard\n- FHIR data import",
            created_at=now - timedelta(days=100),
            updated_at=now - timedelta(days=88),
        )
        self._releases[r1.id] = r1

        # Release v2.1.0 - Deployed
        r2 = ReleaseRecord(
            id="REL-SEED-0002",
            version="2.1.0",
            title="Enhanced Screening & Consent Management",
            description="Added bulk screening and electronic consent workflows",
            status=ReleaseStatus.DEPLOYED,
            release_type=ReleaseType.MINOR,
            features=[
                "Bulk patient screening",
                "Electronic consent management",
                "Screening failure analytics",
            ],
            bug_fixes=["Fixed eligibility score rounding", "Fixed timezone handling in scheduling"],
            breaking_changes=[],
            release_manager="Sarah Chen",
            planned_date=now - timedelta(days=60),
            actual_date=now - timedelta(days=58),
            changelog="## v2.1.0\n- Bulk screening\n- E-consent\n- Screening analytics",
            created_at=now - timedelta(days=70),
            updated_at=now - timedelta(days=58),
        )
        self._releases[r2.id] = r2

        # Release v2.2.0 - Rolled back
        r3 = ReleaseRecord(
            id="REL-SEED-0003",
            version="2.2.0",
            title="Diversity Analytics & Site Performance",
            description="Added diversity tracking and site performance dashboards",
            status=ReleaseStatus.ROLLED_BACK,
            release_type=ReleaseType.MINOR,
            features=[
                "Diversity enrollment analytics",
                "Site performance scoring",
                "Automated site rankings",
            ],
            bug_fixes=["Fixed patient deduplication edge case"],
            breaking_changes=[],
            release_manager="James Rodriguez",
            planned_date=now - timedelta(days=35),
            actual_date=now - timedelta(days=33),
            changelog="## v2.2.0\n- Diversity analytics\n- Site performance (ROLLED BACK)",
            created_at=now - timedelta(days=45),
            updated_at=now - timedelta(days=30),
        )
        self._releases[r3.id] = r3

        # Release v2.2.1 - Hotfix deployed
        r4 = ReleaseRecord(
            id="REL-SEED-0004",
            version="2.2.1",
            title="Hotfix: Data Pipeline Stability",
            description="Emergency fix for data pipeline timeout in production",
            status=ReleaseStatus.DEPLOYED,
            release_type=ReleaseType.HOTFIX,
            features=[],
            bug_fixes=[
                "Fixed data pipeline timeout under high load",
                "Fixed connection pool exhaustion",
            ],
            breaking_changes=[],
            release_manager="James Rodriguez",
            planned_date=now - timedelta(days=28),
            actual_date=now - timedelta(days=28),
            changelog="## v2.2.1 (Hotfix)\n- Pipeline timeout fix\n- Connection pool fix",
            created_at=now - timedelta(days=28),
            updated_at=now - timedelta(days=28),
        )
        self._releases[r4.id] = r4

        # Release v2.3.0 - In testing
        r5 = ReleaseRecord(
            id="REL-SEED-0005",
            version="2.3.0",
            title="ROI Dashboard & Protocol Deviation Tracking",
            description="New ROI analytics and protocol deviation management",
            status=ReleaseStatus.TESTING,
            release_type=ReleaseType.MINOR,
            features=[
                "ROI dashboard with cost modeling",
                "Protocol deviation tracking",
                "Automated deviation alerts",
            ],
            bug_fixes=["Improved search performance", "Fixed CSV export encoding"],
            breaking_changes=[],
            release_manager="Sarah Chen",
            planned_date=now + timedelta(days=7),
            actual_date=None,
            changelog=None,
            created_at=now - timedelta(days=14),
            updated_at=now - timedelta(days=1),
        )
        self._releases[r5.id] = r5

        # Release v2.4.0 - Planning
        r6 = ReleaseRecord(
            id="REL-SEED-0006",
            version="2.4.0",
            title="Regulatory Submission Tracking",
            description="Regulatory submission lifecycle and milestone tracking",
            status=ReleaseStatus.PLANNING,
            release_type=ReleaseType.MINOR,
            features=[
                "Regulatory submission management",
                "Submission milestone tracking",
                "Regulatory calendar view",
            ],
            bug_fixes=[],
            breaking_changes=[],
            release_manager="James Rodriguez",
            planned_date=now + timedelta(days=30),
            actual_date=None,
            changelog=None,
            created_at=now - timedelta(days=5),
            updated_at=now - timedelta(days=5),
        )
        self._releases[r6.id] = r6

        # --- Deployments ---

        # v2.0.0 deployments
        d1 = DeploymentRecord(
            id="DEP-SEED-0001",
            release_id="REL-SEED-0001",
            environment=Environment.STAGING,
            deployment_type=DeploymentType.BLUE_GREEN,
            status=DeploymentStatus.COMPLETED,
            deployed_by="Sarah Chen",
            started_at=now - timedelta(days=89),
            completed_at=now - timedelta(days=89) + timedelta(minutes=12),
            duration_seconds=720,
            health_check_passed=True,
            rollback_available=True,
            rollback_to_version="1.9.0",
        )
        self._deployments[d1.id] = d1

        d2 = DeploymentRecord(
            id="DEP-SEED-0002",
            release_id="REL-SEED-0001",
            environment=Environment.PRODUCTION,
            deployment_type=DeploymentType.BLUE_GREEN,
            status=DeploymentStatus.COMPLETED,
            deployed_by="Sarah Chen",
            started_at=now - timedelta(days=88),
            completed_at=now - timedelta(days=88) + timedelta(minutes=15),
            duration_seconds=900,
            health_check_passed=True,
            rollback_available=True,
            rollback_to_version="1.9.0",
        )
        self._deployments[d2.id] = d2

        # v2.1.0 canary deployment
        d3 = DeploymentRecord(
            id="DEP-SEED-0003",
            release_id="REL-SEED-0002",
            environment=Environment.PRODUCTION,
            deployment_type=DeploymentType.CANARY,
            status=DeploymentStatus.COMPLETED,
            deployed_by="Sarah Chen",
            started_at=now - timedelta(days=58),
            completed_at=now - timedelta(days=58) + timedelta(minutes=25),
            duration_seconds=1500,
            health_check_passed=True,
            rollback_available=True,
            rollback_to_version="2.0.0",
        )
        self._deployments[d3.id] = d3

        # v2.2.0 failed deployment
        d4 = DeploymentRecord(
            id="DEP-SEED-0004",
            release_id="REL-SEED-0003",
            environment=Environment.PRODUCTION,
            deployment_type=DeploymentType.ROLLING,
            status=DeploymentStatus.ROLLED_BACK,
            deployed_by="James Rodriguez",
            started_at=now - timedelta(days=33),
            completed_at=now - timedelta(days=33) + timedelta(minutes=8),
            duration_seconds=480,
            health_check_passed=False,
            rollback_available=False,
            rollback_to_version="2.1.0",
            notes="Health check failed - elevated error rate detected. Rolled back.",
        )
        self._deployments[d4.id] = d4

        # v2.2.0 rollback deployment
        d5 = DeploymentRecord(
            id="DEP-SEED-0005",
            release_id="REL-SEED-0003",
            environment=Environment.PRODUCTION,
            deployment_type=DeploymentType.ROLLBACK,
            status=DeploymentStatus.COMPLETED,
            deployed_by="James Rodriguez",
            started_at=now - timedelta(days=33) + timedelta(minutes=10),
            completed_at=now - timedelta(days=33) + timedelta(minutes=14),
            duration_seconds=240,
            health_check_passed=True,
            rollback_available=False,
            rollback_to_version="2.1.0",
            notes="Rollback to v2.1.0 completed successfully.",
        )
        self._deployments[d5.id] = d5

        # v2.2.1 hotfix deployment
        d6 = DeploymentRecord(
            id="DEP-SEED-0006",
            release_id="REL-SEED-0004",
            environment=Environment.PRODUCTION,
            deployment_type=DeploymentType.HOTFIX,
            status=DeploymentStatus.COMPLETED,
            deployed_by="James Rodriguez",
            started_at=now - timedelta(days=28),
            completed_at=now - timedelta(days=28) + timedelta(minutes=6),
            duration_seconds=360,
            health_check_passed=True,
            rollback_available=True,
            rollback_to_version="2.1.0",
        )
        self._deployments[d6.id] = d6

        # --- Release Gates ---

        # Gates for v2.3.0 (in testing)
        gate_names = list(GateName)
        for i, gate_name in enumerate(gate_names):
            gate = GateRecord(
                id=f"GATE-SEED-{i + 1:04d}",
                release_id="REL-SEED-0005",
                gate_name=gate_name,
                status=GateStatus.PASSED if i < 3 else GateStatus.PENDING,
                reviewer="QA Team" if i < 3 else None,
                reviewed_at=now - timedelta(days=2) if i < 3 else None,
                comments="Passed automated checks" if i < 3 else None,
            )
            self._gates[gate.id] = gate

        # Gates for v2.0.0 (all passed - deployed)
        for i, gate_name in enumerate(gate_names):
            gate = GateRecord(
                id=f"GATE-SEED-{len(gate_names) + i + 1:04d}",
                release_id="REL-SEED-0001",
                gate_name=gate_name,
                status=GateStatus.PASSED,
                reviewer="QA Team",
                reviewed_at=now - timedelta(days=90),
                comments="All checks passed",
            )
            self._gates[gate.id] = gate

    # -------------------------------------------------------------------
    # Clear / reset
    # -------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all data and re-seed."""
        self._releases.clear()
        self._deployments.clear()
        self._gates.clear()
        self._seed_data()

    # -------------------------------------------------------------------
    # Release CRUD
    # -------------------------------------------------------------------

    def create_release(
        self,
        version: str,
        title: str,
        release_type: ReleaseType,
        release_manager: str,
        description: str | None = None,
        features: list[str] | None = None,
        bug_fixes: list[str] | None = None,
        breaking_changes: list[str] | None = None,
        planned_date: datetime | None = None,
    ) -> ReleaseRecord:
        """Create a new release with SemVer validation."""
        if not SEMVER_PATTERN.match(version):
            raise ValueError(f"Invalid semantic version: {version}")

        # Check for duplicate version
        for r in self._releases.values():
            if r.version == version:
                raise ValueError(f"Release with version {version} already exists")

        record = ReleaseRecord(
            version=version,
            title=title,
            description=description,
            release_type=release_type,
            release_manager=release_manager,
            features=features or [],
            bug_fixes=bug_fixes or [],
            breaking_changes=breaking_changes or [],
            planned_date=planned_date,
        )
        self._releases[record.id] = record

        # Create default gates for the release
        for gate_name in GateName:
            gate = GateRecord(
                release_id=record.id,
                gate_name=gate_name,
            )
            self._gates[gate.id] = gate

        logger.info(f"Created release {record.id} (v{version})")
        return record

    def get_release(self, release_id: str) -> ReleaseRecord:
        """Get a release by ID."""
        if release_id not in self._releases:
            raise KeyError(f"Release {release_id} not found")
        return self._releases[release_id]

    def get_release_by_version(self, version: str) -> ReleaseRecord:
        """Get a release by version string."""
        for r in self._releases.values():
            if r.version == version:
                return r
        raise KeyError(f"Release with version {version} not found")

    def update_release(
        self,
        release_id: str,
        title: str | None = None,
        description: str | None = None,
        status: ReleaseStatus | None = None,
        features: list[str] | None = None,
        bug_fixes: list[str] | None = None,
        breaking_changes: list[str] | None = None,
        planned_date: datetime | None = None,
        changelog: str | None = None,
    ) -> ReleaseRecord:
        """Update a release record."""
        record = self.get_release(release_id)

        if status is not None:
            current = record.status
            allowed = VALID_RELEASE_TRANSITIONS.get(current, [])
            if status not in allowed:
                raise ValueError(
                    f"Invalid status transition: {current.value} -> {status.value}. "
                    f"Allowed: {[s.value for s in allowed]}"
                )
            record.status = status
            if status == ReleaseStatus.DEPLOYED:
                record.actual_date = datetime.now(timezone.utc)

        if title is not None:
            record.title = title
        if description is not None:
            record.description = description
        if features is not None:
            record.features = features
        if bug_fixes is not None:
            record.bug_fixes = bug_fixes
        if breaking_changes is not None:
            record.breaking_changes = breaking_changes
        if planned_date is not None:
            record.planned_date = planned_date
        if changelog is not None:
            record.changelog = changelog

        record.updated_at = datetime.now(timezone.utc)
        return record

    def list_releases(
        self,
        status: ReleaseStatus | None = None,
        release_type: ReleaseType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ReleaseRecord], int]:
        """List releases with optional filters."""
        results = list(self._releases.values())

        if status is not None:
            results = [r for r in results if r.status == status]
        if release_type is not None:
            results = [r for r in results if r.release_type == release_type]

        # Sort by created_at descending
        results.sort(key=lambda r: r.created_at, reverse=True)
        total = len(results)
        return results[offset: offset + limit], total

    def delete_release(self, release_id: str) -> None:
        """Delete a release and its associated gates and deployments."""
        if release_id not in self._releases:
            raise KeyError(f"Release {release_id} not found")

        del self._releases[release_id]

        # Clean up associated gates
        gate_ids = [g.id for g in self._gates.values() if g.release_id == release_id]
        for gid in gate_ids:
            del self._gates[gid]

        # Clean up associated deployments
        dep_ids = [d.id for d in self._deployments.values() if d.release_id == release_id]
        for did in dep_ids:
            del self._deployments[did]

        logger.info(f"Deleted release {release_id}")

    # -------------------------------------------------------------------
    # Deployment operations
    # -------------------------------------------------------------------

    def deploy(
        self,
        release_id: str,
        environment: Environment,
        deployment_type: DeploymentType,
        deployed_by: str,
        notes: str | None = None,
    ) -> DeploymentRecord:
        """Create a deployment for a release with health check simulation."""
        release = self.get_release(release_id)

        # Find the previous version for rollback reference
        all_versions = sorted(
            [r for r in self._releases.values() if r.version != release.version and r.actual_date is not None],
            key=lambda r: r.actual_date or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        rollback_version = all_versions[0].version if all_versions else None

        started_at = datetime.now(timezone.utc)

        # Simulate deployment duration and health check
        duration = random.uniform(120, 600)  # 2-10 minutes
        health_passed = random.random() > 0.1  # 90% success rate

        completed_at = started_at + timedelta(seconds=duration)

        dep_status = DeploymentStatus.COMPLETED if health_passed else DeploymentStatus.FAILED

        record = DeploymentRecord(
            release_id=release_id,
            environment=environment,
            deployment_type=deployment_type,
            status=dep_status,
            deployed_by=deployed_by,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=round(duration, 2),
            health_check_passed=health_passed,
            rollback_available=True,
            rollback_to_version=rollback_version,
            notes=notes,
        )
        self._deployments[record.id] = record

        logger.info(
            f"Deployment {record.id} for release {release_id} to {environment.value}: "
            f"{'COMPLETED' if health_passed else 'FAILED'}"
        )
        return record

    def get_deployment(self, deployment_id: str) -> DeploymentRecord:
        """Get a deployment by ID."""
        if deployment_id not in self._deployments:
            raise KeyError(f"Deployment {deployment_id} not found")
        return self._deployments[deployment_id]

    def list_deployments(
        self,
        release_id: str | None = None,
        environment: Environment | None = None,
        status: DeploymentStatus | None = None,
    ) -> list[DeploymentRecord]:
        """List deployments with optional filters."""
        results = list(self._deployments.values())

        if release_id is not None:
            results = [d for d in results if d.release_id == release_id]
        if environment is not None:
            results = [d for d in results if d.environment == environment]
        if status is not None:
            results = [d for d in results if d.status == status]

        results.sort(key=lambda d: d.started_at, reverse=True)
        return results

    def rollback(
        self,
        deployment_id: str,
        rolled_back_by: str,
        reason: str | None = None,
    ) -> DeploymentRecord:
        """Create a rollback deployment for an existing deployment."""
        original = self.get_deployment(deployment_id)

        if not original.rollback_available:
            raise ValueError(f"Rollback not available for deployment {deployment_id}")

        if original.status == DeploymentStatus.ROLLED_BACK:
            raise ValueError(f"Deployment {deployment_id} is already rolled back")

        # Mark original as rolled back
        original.status = DeploymentStatus.ROLLED_BACK
        original.rollback_available = False

        # Update release status
        release = self.get_release(original.release_id)
        if release.status == ReleaseStatus.DEPLOYED:
            release.status = ReleaseStatus.ROLLED_BACK
            release.updated_at = datetime.now(timezone.utc)

        # Create rollback deployment
        started_at = datetime.now(timezone.utc)
        duration = random.uniform(60, 300)  # 1-5 minutes
        completed_at = started_at + timedelta(seconds=duration)

        rollback_dep = DeploymentRecord(
            release_id=original.release_id,
            environment=original.environment,
            deployment_type=DeploymentType.ROLLBACK,
            status=DeploymentStatus.COMPLETED,
            deployed_by=rolled_back_by,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=round(duration, 2),
            health_check_passed=True,
            rollback_available=False,
            rollback_to_version=original.rollback_to_version,
            notes=reason or f"Rollback of deployment {deployment_id}",
        )
        self._deployments[rollback_dep.id] = rollback_dep

        logger.info(
            f"Rollback deployment {rollback_dep.id} created for {deployment_id} "
            f"(rolling back to {original.rollback_to_version})"
        )
        return rollback_dep

    # -------------------------------------------------------------------
    # Release Gates
    # -------------------------------------------------------------------

    def get_gates_for_release(self, release_id: str) -> list[GateRecord]:
        """Get all gates for a release."""
        self.get_release(release_id)  # Validate release exists
        return [g for g in self._gates.values() if g.release_id == release_id]

    def update_gate(
        self,
        release_id: str,
        gate_name: GateName,
        status: GateStatus,
        reviewer: str,
        comments: str | None = None,
    ) -> GateRecord:
        """Update a release gate status."""
        self.get_release(release_id)  # Validate release exists

        # Find the gate
        gate = None
        for g in self._gates.values():
            if g.release_id == release_id and g.gate_name == gate_name:
                gate = g
                break

        if gate is None:
            raise KeyError(
                f"Gate {gate_name.value} not found for release {release_id}"
            )

        gate.status = status
        gate.reviewer = reviewer
        gate.reviewed_at = datetime.now(timezone.utc)
        gate.comments = comments

        logger.info(
            f"Gate {gate_name.value} for release {release_id} "
            f"updated to {status.value} by {reviewer}"
        )
        return gate

    def check_release_readiness(self, release_id: str) -> ReleaseReadinessResponse:
        """Check if all gates have passed for a release."""
        release = self.get_release(release_id)
        gates = self.get_gates_for_release(release_id)

        gate_responses = [
            ReleaseGate(
                id=g.id,
                release_id=g.release_id,
                gate_name=g.gate_name,
                status=g.status,
                reviewer=g.reviewer,
                reviewed_at=g.reviewed_at,
                comments=g.comments,
            )
            for g in gates
        ]

        passed = [g for g in gates if g.status in (GateStatus.PASSED, GateStatus.WAIVED)]
        blocking = [
            g.gate_name.value
            for g in gates
            if g.status in (GateStatus.PENDING, GateStatus.FAILED)
        ]

        return ReleaseReadinessResponse(
            release_id=release_id,
            version=release.version,
            ready=len(blocking) == 0 and len(gates) > 0,
            gates=gate_responses,
            passed_count=len(passed),
            total_count=len(gates),
            blocking_gates=blocking,
        )

    # -------------------------------------------------------------------
    # DORA Metrics
    # -------------------------------------------------------------------

    def get_dora_metrics(self) -> ReleaseMetrics:
        """Compute DORA metrics from release and deployment data."""
        releases = list(self._releases.values())
        deployments = list(self._deployments.values())

        total = len(releases)

        # By type
        by_type: dict[str, int] = {}
        for r in releases:
            by_type[r.release_type.value] = by_type.get(r.release_type.value, 0) + 1

        # By status
        by_status: dict[str, int] = {}
        for r in releases:
            by_status[r.status.value] = by_status.get(r.status.value, 0) + 1

        # Deployment frequency (per month over last 90 days)
        now = datetime.now(timezone.utc)
        recent_deployments = [
            d for d in deployments
            if d.started_at >= now - timedelta(days=90)
            and d.status == DeploymentStatus.COMPLETED
        ]
        deployment_freq = len(recent_deployments) / 3.0 if recent_deployments else 0.0

        # Mean lead time (planning to deployment)
        lead_times: list[float] = []
        for r in releases:
            if r.actual_date and r.created_at:
                lead_days = (r.actual_date - r.created_at).total_seconds() / 86400
                lead_times.append(lead_days)
        mean_lead_time = sum(lead_times) / len(lead_times) if lead_times else 0.0

        # Change failure rate
        prod_deployments = [
            d for d in deployments
            if d.environment == Environment.PRODUCTION
        ]
        failed_or_rolled = [
            d for d in prod_deployments
            if d.status in (DeploymentStatus.FAILED, DeploymentStatus.ROLLED_BACK)
            and d.deployment_type != DeploymentType.ROLLBACK
        ]
        change_failure_rate = (
            (len(failed_or_rolled) / len(prod_deployments) * 100)
            if prod_deployments
            else 0.0
        )

        # MTTR (time between failure and recovery)
        recovery_times: list[float] = []
        for d in deployments:
            if d.status in (DeploymentStatus.FAILED, DeploymentStatus.ROLLED_BACK) and d.deployment_type != DeploymentType.ROLLBACK:
                # Find corresponding rollback deployment
                rollbacks = [
                    rb for rb in deployments
                    if rb.release_id == d.release_id
                    and rb.deployment_type == DeploymentType.ROLLBACK
                    and rb.status == DeploymentStatus.COMPLETED
                    and rb.started_at >= d.started_at
                ]
                if rollbacks:
                    recovery = rollbacks[0]
                    mttr_minutes = (
                        (recovery.completed_at or recovery.started_at) - d.started_at
                    ).total_seconds() / 60
                    recovery_times.append(mttr_minutes)
        mean_tttr = sum(recovery_times) / len(recovery_times) if recovery_times else 0.0

        # Rollback and hotfix counts
        rollback_count = len([
            d for d in deployments if d.deployment_type == DeploymentType.ROLLBACK
        ])
        hotfix_count = len([
            r for r in releases if r.release_type == ReleaseType.HOTFIX
        ])

        return ReleaseMetrics(
            total_releases=total,
            deployment_frequency_per_month=round(deployment_freq, 2),
            mean_lead_time_days=round(mean_lead_time, 2),
            change_failure_rate_pct=round(change_failure_rate, 2),
            mean_time_to_recovery_minutes=round(mean_tttr, 2),
            by_type=by_type,
            by_status=by_status,
            rollback_count=rollback_count,
            hotfix_count=hotfix_count,
        )

    # -------------------------------------------------------------------
    # Release History
    # -------------------------------------------------------------------

    def get_release_history(self, limit: int = 10) -> ReleaseHistoryResponse:
        """Get recent releases with deployment summary."""
        releases = sorted(
            self._releases.values(),
            key=lambda r: r.created_at,
            reverse=True,
        )[:limit]

        entries = []
        for r in releases:
            deps = [
                Deployment(
                    id=d.id,
                    release_id=d.release_id,
                    environment=d.environment,
                    deployment_type=d.deployment_type,
                    status=d.status,
                    deployed_by=d.deployed_by,
                    started_at=d.started_at,
                    completed_at=d.completed_at,
                    duration_seconds=d.duration_seconds,
                    health_check_passed=d.health_check_passed,
                    rollback_available=d.rollback_available,
                    rollback_to_version=d.rollback_to_version,
                    notes=d.notes,
                )
                for d in self._deployments.values()
                if d.release_id == r.id
            ]

            gates = [g for g in self._gates.values() if g.release_id == r.id]
            passed = len([g for g in gates if g.status in (GateStatus.PASSED, GateStatus.WAIVED)])

            entries.append(
                ReleaseHistoryEntry(
                    release=Release(
                        id=r.id,
                        version=r.version,
                        title=r.title,
                        description=r.description,
                        status=r.status,
                        release_type=r.release_type,
                        features=r.features,
                        bug_fixes=r.bug_fixes,
                        breaking_changes=r.breaking_changes,
                        release_manager=r.release_manager,
                        planned_date=r.planned_date,
                        actual_date=r.actual_date,
                        changelog=r.changelog,
                        created_at=r.created_at,
                        updated_at=r.updated_at,
                    ),
                    deployments=deps,
                    gates_passed=passed,
                    gates_total=len(gates),
                )
            )

        return ReleaseHistoryResponse(entries=entries, total=len(entries))


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------


def get_release_management_service() -> ReleaseManagementService:
    """Get or create the singleton ReleaseManagementService."""
    global _release_mgmt_instance
    if _release_mgmt_instance is None:
        with _release_mgmt_lock:
            if _release_mgmt_instance is None:
                _release_mgmt_instance = ReleaseManagementService()
                logger.info("ReleaseManagementService singleton created")
    return _release_mgmt_instance


def reset_release_management_service() -> None:
    """Reset the singleton (for testing)."""
    global _release_mgmt_instance
    with _release_mgmt_lock:
        _release_mgmt_instance = None
