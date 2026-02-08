"""Backup verification service for disaster recovery compliance (COO-1).

Tracks backup registrations, verifies RPO compliance, and validates
backup integrity for all critical systems (PostgreSQL, Redis, Neo4j).

This service uses in-memory storage for backup records. In production,
backup registration would be called by the actual backup scripts/cron jobs
to record each successful backup.

HIPAA Note: This service does not handle PHI directly. It tracks metadata
about backups (timestamps, sizes, checksums) but never accesses backup content.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class BackupType(str, Enum):
    """Types of backups tracked by the system."""

    POSTGRES_BASE = "postgres_base"
    POSTGRES_WAL = "postgres_wal"
    POSTGRES_LOGICAL = "postgres_logical"
    REDIS_RDB = "redis_rdb"
    REDIS_AOF = "redis_aof"
    NEO4J_FULL = "neo4j_full"
    NEO4J_INCREMENTAL = "neo4j_incremental"


class ComplianceStatus(str, Enum):
    """RPO compliance status."""

    COMPLIANT = "compliant"
    WARNING = "warning"
    VIOLATION = "violation"
    UNKNOWN = "unknown"


class BackupStatus(str, Enum):
    """Overall backup health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"


# RPO windows per backup type (how old the most recent backup can be)
RPO_WINDOWS: dict[BackupType, timedelta] = {
    # Clinical data: 1-hour RPO
    BackupType.POSTGRES_WAL: timedelta(hours=1),
    BackupType.POSTGRES_BASE: timedelta(hours=25),  # Daily + 1 hour grace
    BackupType.POSTGRES_LOGICAL: timedelta(days=8),  # Weekly + 1 day grace
    # Transient data: best-effort
    BackupType.REDIS_RDB: timedelta(hours=1),
    BackupType.REDIS_AOF: timedelta(hours=1),
    # Derived data: 4-hour RPO
    BackupType.NEO4J_FULL: timedelta(hours=25),  # Daily + 1 hour grace
    BackupType.NEO4J_INCREMENTAL: timedelta(hours=5),  # 4 hours + 1 hour grace
}

# Warning thresholds (alert before RPO violation)
WARNING_FACTOR = 0.75  # Warn at 75% of RPO window


@dataclass
class BackupRecord:
    """Record of a single backup execution."""

    backup_type: BackupType
    timestamp: datetime
    size_bytes: int
    checksum: str  # SHA-256 hex digest
    checksum_algorithm: str = "sha256"
    verified: bool = False
    verified_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def age(self) -> timedelta:
        """Time since this backup was created."""
        return datetime.now(timezone.utc) - self.timestamp

    @property
    def age_hours(self) -> float:
        """Age in hours (for reporting)."""
        return self.age.total_seconds() / 3600


@dataclass
class RPOComplianceEntry:
    """RPO compliance status for a single backup type."""

    backup_type: BackupType
    status: ComplianceStatus
    rpo_window_hours: float
    last_backup_age_hours: float | None
    last_backup_timestamp: datetime | None
    next_required_by: datetime | None
    message: str


@dataclass
class BackupVerificationReport:
    """Complete backup verification report."""

    generated_at: datetime
    overall_status: BackupStatus
    total_backups_tracked: int
    compliance_entries: list[RPOComplianceEntry]
    recent_backups: list[dict[str, Any]]
    alerts: list[str]
    summary: str


class BackupVerificationService:
    """Service for tracking and verifying backup compliance.

    Maintains an in-memory registry of backup records and provides
    RPO compliance checking against configured windows.

    Usage:
        service = get_backup_verification_service()

        # Register a backup (called by backup scripts)
        service.register_backup(
            backup_type=BackupType.POSTGRES_BASE,
            timestamp=datetime.now(timezone.utc),
            size_bytes=1073741824,  # 1 GB
            checksum="sha256hexdigest...",
        )

        # Check compliance
        report = service.verify_backup_status()
        rpo_status = service.check_rpo_compliance()
    """

    def __init__(self) -> None:
        """Initialize with empty backup registry."""
        self._backups: dict[BackupType, list[BackupRecord]] = {
            bt: [] for bt in BackupType
        }
        self._max_history_per_type = 100

    def register_backup(
        self,
        backup_type: BackupType | str,
        timestamp: datetime,
        size_bytes: int,
        checksum: str,
        checksum_algorithm: str = "sha256",
        metadata: dict[str, Any] | None = None,
    ) -> BackupRecord:
        """Register a completed backup.

        Args:
            backup_type: Type of backup (e.g., "postgres_base").
            timestamp: When the backup was created (must be timezone-aware UTC).
            size_bytes: Size of the backup in bytes.
            checksum: Hex digest of the backup content checksum.
            checksum_algorithm: Hash algorithm used (default: sha256).
            metadata: Optional additional metadata.

        Returns:
            The created BackupRecord.

        Raises:
            ValueError: If inputs are invalid.
        """
        # Coerce string to enum
        if isinstance(backup_type, str):
            backup_type = BackupType(backup_type)

        # Validate inputs
        if timestamp.tzinfo is None:
            raise ValueError("Backup timestamp must be timezone-aware (use UTC)")

        if size_bytes < 0:
            raise ValueError("Backup size must be non-negative")

        if not checksum or len(checksum) < 8:
            raise ValueError("Checksum must be at least 8 characters")

        if timestamp > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("Backup timestamp cannot be in the future")

        record = BackupRecord(
            backup_type=backup_type,
            timestamp=timestamp,
            size_bytes=size_bytes,
            checksum=checksum,
            checksum_algorithm=checksum_algorithm,
            metadata=metadata or {},
        )

        self._backups[backup_type].append(record)

        # Trim history to prevent unbounded memory growth
        if len(self._backups[backup_type]) > self._max_history_per_type:
            self._backups[backup_type] = self._backups[backup_type][
                -self._max_history_per_type :
            ]

        logger.info(
            "Backup registered: type=%s, size=%d bytes, checksum=%s...%s",
            backup_type.value,
            size_bytes,
            checksum[:8],
            checksum[-4:] if len(checksum) > 12 else "",
        )

        return record

    def get_latest_backup(self, backup_type: BackupType) -> BackupRecord | None:
        """Get the most recent backup of a given type."""
        backups = self._backups.get(backup_type, [])
        if not backups:
            return None
        return max(backups, key=lambda b: b.timestamp)

    def get_backup_history(
        self,
        backup_type: BackupType | None = None,
        limit: int = 20,
    ) -> list[BackupRecord]:
        """Get backup history, optionally filtered by type.

        Args:
            backup_type: Filter to a specific type, or None for all.
            limit: Maximum number of records to return.

        Returns:
            List of BackupRecords, most recent first.
        """
        if backup_type is not None:
            records = list(self._backups.get(backup_type, []))
        else:
            records = [r for backups in self._backups.values() for r in backups]

        records.sort(key=lambda b: b.timestamp, reverse=True)
        return records[:limit]

    def verify_backup_integrity(
        self,
        backup_type: BackupType,
        checksum: str,
    ) -> bool:
        """Verify a backup's integrity by matching its checksum.

        In production, this would compare the stored checksum against a
        freshly computed checksum of the backup file. Here we verify that
        a backup with the given checksum exists in our registry.

        Args:
            backup_type: Type of backup to verify.
            checksum: Expected checksum hex digest.

        Returns:
            True if a matching backup is found.
        """
        for record in self._backups.get(backup_type, []):
            if record.checksum == checksum:
                record.verified = True
                record.verified_at = datetime.now(timezone.utc)
                logger.info(
                    "Backup integrity verified: type=%s, checksum=%s...%s",
                    backup_type.value,
                    checksum[:8],
                    checksum[-4:] if len(checksum) > 12 else "",
                )
                return True
        return False

    def check_rpo_compliance(self) -> list[RPOComplianceEntry]:
        """Check RPO compliance for all backup types.

        Returns:
            List of RPOComplianceEntry, one per backup type.
        """
        now = datetime.now(timezone.utc)
        entries: list[RPOComplianceEntry] = []

        for backup_type, rpo_window in RPO_WINDOWS.items():
            latest = self.get_latest_backup(backup_type)
            rpo_hours = rpo_window.total_seconds() / 3600
            warning_window = rpo_window * WARNING_FACTOR

            if latest is None:
                entries.append(
                    RPOComplianceEntry(
                        backup_type=backup_type,
                        status=ComplianceStatus.UNKNOWN,
                        rpo_window_hours=rpo_hours,
                        last_backup_age_hours=None,
                        last_backup_timestamp=None,
                        next_required_by=None,
                        message=f"No {backup_type.value} backups registered. "
                        f"RPO compliance cannot be verified.",
                    )
                )
                continue

            age = now - latest.timestamp
            age_hours = age.total_seconds() / 3600
            next_required = latest.timestamp + rpo_window

            if age <= warning_window:
                status = ComplianceStatus.COMPLIANT
                message = (
                    f"{backup_type.value}: Last backup {age_hours:.1f}h ago. "
                    f"Within RPO window ({rpo_hours:.0f}h)."
                )
            elif age <= rpo_window:
                status = ComplianceStatus.WARNING
                message = (
                    f"{backup_type.value}: Last backup {age_hours:.1f}h ago. "
                    f"Approaching RPO limit ({rpo_hours:.0f}h). "
                    f"Next backup required by {next_required.isoformat()}."
                )
            else:
                status = ComplianceStatus.VIOLATION
                message = (
                    f"{backup_type.value}: RPO VIOLATION. Last backup {age_hours:.1f}h ago. "
                    f"Exceeds RPO window of {rpo_hours:.0f}h. "
                    f"Backup was due by {next_required.isoformat()}."
                )

            entries.append(
                RPOComplianceEntry(
                    backup_type=backup_type,
                    status=status,
                    rpo_window_hours=rpo_hours,
                    last_backup_age_hours=round(age_hours, 2),
                    last_backup_timestamp=latest.timestamp,
                    next_required_by=next_required,
                    message=message,
                )
            )

        return entries

    def verify_backup_status(self) -> BackupVerificationReport:
        """Generate a complete backup verification report.

        Returns:
            BackupVerificationReport with overall status, compliance entries,
            recent backup list, and any alerts.
        """
        now = datetime.now(timezone.utc)
        compliance = self.check_rpo_compliance()
        recent = self.get_backup_history(limit=10)
        alerts: list[str] = []

        # Determine overall status
        statuses = [e.status for e in compliance]

        if ComplianceStatus.VIOLATION in statuses:
            overall = BackupStatus.CRITICAL
        elif ComplianceStatus.UNKNOWN in statuses or ComplianceStatus.WARNING in statuses:
            overall = BackupStatus.DEGRADED
        else:
            overall = BackupStatus.HEALTHY

        # Generate alerts
        for entry in compliance:
            if entry.status == ComplianceStatus.VIOLATION:
                alerts.append(f"CRITICAL: {entry.message}")
            elif entry.status == ComplianceStatus.WARNING:
                alerts.append(f"WARNING: {entry.message}")
            elif entry.status == ComplianceStatus.UNKNOWN:
                alerts.append(f"INFO: {entry.message}")

        # Check for suspicious patterns
        for backup_type in BackupType:
            history = self._backups.get(backup_type, [])
            if len(history) >= 3:
                # Check if backup sizes are consistent (>50% size change is suspicious)
                sizes = [b.size_bytes for b in history[-3:]]
                if sizes[-1] > 0 and sizes[-2] > 0:
                    ratio = sizes[-1] / sizes[-2]
                    if ratio > 2.0 or ratio < 0.5:
                        alerts.append(
                            f"WARNING: {backup_type.value} size changed significantly "
                            f"({sizes[-2]} -> {sizes[-1]} bytes). Investigate possible "
                            f"data corruption or incomplete backup."
                        )

        # Count total backups
        total = sum(len(bl) for bl in self._backups.values())

        # Build recent backups summary
        recent_dicts = [
            {
                "backup_type": r.backup_type.value,
                "timestamp": r.timestamp.isoformat(),
                "size_bytes": r.size_bytes,
                "age_hours": round(r.age_hours, 2),
                "checksum_prefix": r.checksum[:12] + "...",
                "verified": r.verified,
            }
            for r in recent
        ]

        # Build summary
        violation_count = statuses.count(ComplianceStatus.VIOLATION)
        warning_count = statuses.count(ComplianceStatus.WARNING)
        unknown_count = statuses.count(ComplianceStatus.UNKNOWN)
        compliant_count = statuses.count(ComplianceStatus.COMPLIANT)

        summary_parts = []
        if compliant_count:
            summary_parts.append(f"{compliant_count} compliant")
        if warning_count:
            summary_parts.append(f"{warning_count} warnings")
        if violation_count:
            summary_parts.append(f"{violation_count} violations")
        if unknown_count:
            summary_parts.append(f"{unknown_count} unknown")
        summary = f"Backup status: {overall.value}. {', '.join(summary_parts)}."

        return BackupVerificationReport(
            generated_at=now,
            overall_status=overall,
            total_backups_tracked=total,
            compliance_entries=compliance,
            recent_backups=recent_dicts,
            alerts=alerts,
            summary=summary,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics (for health endpoint integration)."""
        total = sum(len(bl) for bl in self._backups.values())
        compliance = self.check_rpo_compliance()
        violations = sum(
            1 for e in compliance if e.status == ComplianceStatus.VIOLATION
        )
        return {
            "total_backups_tracked": total,
            "backup_types_registered": sum(
                1 for bl in self._backups.values() if bl
            ),
            "rpo_violations": violations,
        }


# Singleton instance
_backup_verification_service: BackupVerificationService | None = None


def get_backup_verification_service() -> BackupVerificationService:
    """Get or create the singleton BackupVerificationService instance."""
    global _backup_verification_service
    if _backup_verification_service is None:
        _backup_verification_service = BackupVerificationService()
    return _backup_verification_service
