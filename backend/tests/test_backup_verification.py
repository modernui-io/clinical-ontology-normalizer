"""Tests for backup verification service and API endpoints (COO-1).

Tests cover:
- Backup registration (valid, invalid inputs)
- RPO compliance checking (within window, warning, violation, unknown)
- Backup integrity verification
- Missing backup alerting
- Backup history tracking
- Suspicious size change detection
- API endpoint responses
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.services.backup_verification_service import (
    BackupRecord,
    BackupStatus,
    BackupType,
    BackupVerificationService,
    ComplianceStatus,
    RPO_WINDOWS,
    WARNING_FACTOR,
    get_backup_verification_service,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def service() -> BackupVerificationService:
    """Create a fresh BackupVerificationService for each test."""
    return BackupVerificationService()


@pytest.fixture
def now() -> datetime:
    """Current UTC timestamp."""
    return datetime.now(timezone.utc)


def _make_checksum(data: str = "test-backup-data") -> str:
    """Generate a valid SHA-256 checksum for test data."""
    return hashlib.sha256(data.encode()).hexdigest()


# ============================================================================
# Test: Backup Registration
# ============================================================================


class TestBackupRegistration:
    """Tests for registering backups."""

    def test_register_backup_success(self, service: BackupVerificationService, now: datetime) -> None:
        """Test successful backup registration with valid inputs."""
        checksum = _make_checksum()
        record = service.register_backup(
            backup_type=BackupType.POSTGRES_BASE,
            timestamp=now - timedelta(minutes=5),
            size_bytes=1_073_741_824,  # 1 GB
            checksum=checksum,
        )

        assert isinstance(record, BackupRecord)
        assert record.backup_type == BackupType.POSTGRES_BASE
        assert record.size_bytes == 1_073_741_824
        assert record.checksum == checksum
        assert record.checksum_algorithm == "sha256"
        assert record.verified is False

    def test_register_backup_with_string_type(self, service: BackupVerificationService, now: datetime) -> None:
        """Test backup registration accepts string backup type."""
        record = service.register_backup(
            backup_type="postgres_wal",
            timestamp=now - timedelta(minutes=1),
            size_bytes=16_777_216,
            checksum=_make_checksum("wal-segment"),
        )

        assert record.backup_type == BackupType.POSTGRES_WAL

    def test_register_backup_with_metadata(self, service: BackupVerificationService, now: datetime) -> None:
        """Test backup registration with optional metadata."""
        metadata = {"filename": "base_backup_20260208.tar.gz", "encrypted": True}
        record = service.register_backup(
            backup_type=BackupType.POSTGRES_BASE,
            timestamp=now - timedelta(minutes=5),
            size_bytes=500_000_000,
            checksum=_make_checksum(),
            metadata=metadata,
        )

        assert record.metadata == metadata
        assert record.metadata["encrypted"] is True

    def test_register_backup_rejects_naive_timestamp(self, service: BackupVerificationService) -> None:
        """Test that naive (non-timezone-aware) timestamps are rejected."""
        with pytest.raises(ValueError, match="timezone-aware"):
            service.register_backup(
                backup_type=BackupType.POSTGRES_BASE,
                timestamp=datetime(2026, 2, 8, 12, 0, 0),  # naive
                size_bytes=100,
                checksum=_make_checksum(),
            )

    def test_register_backup_rejects_negative_size(self, service: BackupVerificationService, now: datetime) -> None:
        """Test that negative backup sizes are rejected."""
        with pytest.raises(ValueError, match="non-negative"):
            service.register_backup(
                backup_type=BackupType.POSTGRES_BASE,
                timestamp=now,
                size_bytes=-1,
                checksum=_make_checksum(),
            )

    def test_register_backup_rejects_short_checksum(self, service: BackupVerificationService, now: datetime) -> None:
        """Test that checksums shorter than 8 chars are rejected."""
        with pytest.raises(ValueError, match="at least 8"):
            service.register_backup(
                backup_type=BackupType.POSTGRES_BASE,
                timestamp=now,
                size_bytes=100,
                checksum="abc",
            )

    def test_register_backup_rejects_future_timestamp(self, service: BackupVerificationService) -> None:
        """Test that future timestamps are rejected."""
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        with pytest.raises(ValueError, match="future"):
            service.register_backup(
                backup_type=BackupType.POSTGRES_BASE,
                timestamp=future,
                size_bytes=100,
                checksum=_make_checksum(),
            )

    def test_register_multiple_backups_same_type(self, service: BackupVerificationService, now: datetime) -> None:
        """Test registering multiple backups of the same type."""
        for i in range(5):
            service.register_backup(
                backup_type=BackupType.REDIS_RDB,
                timestamp=now - timedelta(minutes=60 - i * 10),
                size_bytes=1000 + i * 100,
                checksum=_make_checksum(f"redis-{i}"),
            )

        history = service.get_backup_history(BackupType.REDIS_RDB)
        assert len(history) == 5

    def test_backup_history_trimmed(self, service: BackupVerificationService, now: datetime) -> None:
        """Test that backup history is trimmed to max_history_per_type."""
        service._max_history_per_type = 5
        for i in range(10):
            service.register_backup(
                backup_type=BackupType.POSTGRES_WAL,
                timestamp=now - timedelta(minutes=100 - i),
                size_bytes=100,
                checksum=_make_checksum(f"wal-{i}"),
            )

        history = service.get_backup_history(BackupType.POSTGRES_WAL)
        assert len(history) == 5


# ============================================================================
# Test: RPO Compliance
# ============================================================================


class TestRPOCompliance:
    """Tests for RPO compliance checking."""

    def test_rpo_compliant_recent_backup(self, service: BackupVerificationService, now: datetime) -> None:
        """Test RPO compliance when backup is well within window."""
        service.register_backup(
            backup_type=BackupType.POSTGRES_WAL,
            timestamp=now - timedelta(minutes=10),  # WAL RPO is 1 hour
            size_bytes=16_000_000,
            checksum=_make_checksum(),
        )

        entries = service.check_rpo_compliance()
        wal_entry = next(e for e in entries if e.backup_type == BackupType.POSTGRES_WAL)

        assert wal_entry.status == ComplianceStatus.COMPLIANT
        assert wal_entry.last_backup_age_hours is not None
        assert wal_entry.last_backup_age_hours < 1.0

    def test_rpo_warning_approaching_limit(self, service: BackupVerificationService, now: datetime) -> None:
        """Test RPO warning when backup is approaching the limit."""
        # WAL RPO is 1 hour, warning at 75% = 45 minutes
        service.register_backup(
            backup_type=BackupType.POSTGRES_WAL,
            timestamp=now - timedelta(minutes=50),  # Past 75% threshold
            size_bytes=16_000_000,
            checksum=_make_checksum(),
        )

        entries = service.check_rpo_compliance()
        wal_entry = next(e for e in entries if e.backup_type == BackupType.POSTGRES_WAL)

        assert wal_entry.status == ComplianceStatus.WARNING

    def test_rpo_violation_exceeded(self, service: BackupVerificationService, now: datetime) -> None:
        """Test RPO violation when backup exceeds the window."""
        # WAL RPO is 1 hour, backup is 2 hours old
        service.register_backup(
            backup_type=BackupType.POSTGRES_WAL,
            timestamp=now - timedelta(hours=2),
            size_bytes=16_000_000,
            checksum=_make_checksum(),
        )

        entries = service.check_rpo_compliance()
        wal_entry = next(e for e in entries if e.backup_type == BackupType.POSTGRES_WAL)

        assert wal_entry.status == ComplianceStatus.VIOLATION
        assert "VIOLATION" in wal_entry.message

    def test_rpo_unknown_no_backups(self, service: BackupVerificationService) -> None:
        """Test RPO unknown status when no backups are registered."""
        entries = service.check_rpo_compliance()

        # All types should be UNKNOWN since no backups registered
        for entry in entries:
            assert entry.status == ComplianceStatus.UNKNOWN
            assert entry.last_backup_age_hours is None
            assert entry.last_backup_timestamp is None

    def test_rpo_compliance_all_types_checked(self, service: BackupVerificationService) -> None:
        """Test that all backup types from RPO_WINDOWS are checked."""
        entries = service.check_rpo_compliance()
        checked_types = {e.backup_type for e in entries}
        expected_types = set(RPO_WINDOWS.keys())

        assert checked_types == expected_types

    def test_rpo_next_required_by_calculated(self, service: BackupVerificationService, now: datetime) -> None:
        """Test that next_required_by is correctly calculated."""
        backup_time = now - timedelta(minutes=10)
        service.register_backup(
            backup_type=BackupType.POSTGRES_BASE,
            timestamp=backup_time,
            size_bytes=1_000_000_000,
            checksum=_make_checksum(),
        )

        entries = service.check_rpo_compliance()
        base_entry = next(e for e in entries if e.backup_type == BackupType.POSTGRES_BASE)

        expected_next = backup_time + RPO_WINDOWS[BackupType.POSTGRES_BASE]
        assert base_entry.next_required_by is not None
        # Allow 1 second tolerance
        assert abs((base_entry.next_required_by - expected_next).total_seconds()) < 1


# ============================================================================
# Test: Backup Integrity Verification
# ============================================================================


class TestBackupIntegrity:
    """Tests for backup integrity verification."""

    def test_verify_integrity_matching_checksum(self, service: BackupVerificationService, now: datetime) -> None:
        """Test integrity verification with matching checksum."""
        checksum = _make_checksum("important-backup")
        service.register_backup(
            backup_type=BackupType.POSTGRES_BASE,
            timestamp=now - timedelta(hours=1),
            size_bytes=1_000_000_000,
            checksum=checksum,
        )

        result = service.verify_backup_integrity(BackupType.POSTGRES_BASE, checksum)
        assert result is True

        # Record should now be marked as verified
        latest = service.get_latest_backup(BackupType.POSTGRES_BASE)
        assert latest is not None
        assert latest.verified is True
        assert latest.verified_at is not None

    def test_verify_integrity_wrong_checksum(self, service: BackupVerificationService, now: datetime) -> None:
        """Test integrity verification with non-matching checksum."""
        service.register_backup(
            backup_type=BackupType.POSTGRES_BASE,
            timestamp=now - timedelta(hours=1),
            size_bytes=1_000_000_000,
            checksum=_make_checksum("original"),
        )

        result = service.verify_backup_integrity(
            BackupType.POSTGRES_BASE,
            _make_checksum("different"),
        )
        assert result is False

    def test_verify_integrity_no_backups(self, service: BackupVerificationService) -> None:
        """Test integrity verification when no backups exist."""
        result = service.verify_backup_integrity(
            BackupType.NEO4J_FULL,
            _make_checksum("nonexistent"),
        )
        assert result is False


# ============================================================================
# Test: Backup Status Report
# ============================================================================


class TestBackupStatusReport:
    """Tests for the comprehensive backup status report."""

    def test_report_healthy_all_compliant(self, service: BackupVerificationService, now: datetime) -> None:
        """Test report shows healthy when all backups are compliant."""
        # Register recent backups for all types
        for bt in BackupType:
            service.register_backup(
                backup_type=bt,
                timestamp=now - timedelta(minutes=5),
                size_bytes=100_000,
                checksum=_make_checksum(bt.value),
            )

        report = service.verify_backup_status()

        assert report.overall_status == BackupStatus.HEALTHY
        assert len(report.alerts) == 0
        assert report.total_backups_tracked == len(BackupType)

    def test_report_critical_on_violation(self, service: BackupVerificationService, now: datetime) -> None:
        """Test report shows critical when RPO is violated."""
        # Register a very old WAL backup (RPO = 1 hour)
        service.register_backup(
            backup_type=BackupType.POSTGRES_WAL,
            timestamp=now - timedelta(hours=3),
            size_bytes=16_000_000,
            checksum=_make_checksum(),
        )

        report = service.verify_backup_status()

        assert report.overall_status == BackupStatus.CRITICAL
        assert any("CRITICAL" in alert for alert in report.alerts)

    def test_report_degraded_on_unknown(self, service: BackupVerificationService) -> None:
        """Test report shows degraded when backup types have no data."""
        report = service.verify_backup_status()

        # All types are UNKNOWN -> degraded
        assert report.overall_status == BackupStatus.DEGRADED
        assert report.total_backups_tracked == 0

    def test_report_suspicious_size_change(self, service: BackupVerificationService, now: datetime) -> None:
        """Test report alerts on suspicious backup size changes."""
        # Register 3 backups with dramatic size change
        for i, size in enumerate([1_000_000, 1_000_000, 100]):  # 10000x shrinkage
            service.register_backup(
                backup_type=BackupType.POSTGRES_BASE,
                timestamp=now - timedelta(hours=3 - i),
                size_bytes=size,
                checksum=_make_checksum(f"base-{i}"),
            )

        report = service.verify_backup_status()

        size_alerts = [a for a in report.alerts if "size changed" in a]
        assert len(size_alerts) > 0

    def test_report_recent_backups_list(self, service: BackupVerificationService, now: datetime) -> None:
        """Test that recent backups are included in report."""
        service.register_backup(
            backup_type=BackupType.REDIS_RDB,
            timestamp=now - timedelta(minutes=10),
            size_bytes=50_000_000,
            checksum=_make_checksum("redis"),
        )

        report = service.verify_backup_status()

        assert len(report.recent_backups) == 1
        assert report.recent_backups[0]["backup_type"] == "redis_rdb"
        assert "checksum_prefix" in report.recent_backups[0]

    def test_report_summary_text(self, service: BackupVerificationService) -> None:
        """Test that summary text is generated."""
        report = service.verify_backup_status()

        assert report.summary is not None
        assert len(report.summary) > 0
        assert "unknown" in report.summary.lower()


# ============================================================================
# Test: Backup History
# ============================================================================


class TestBackupHistory:
    """Tests for backup history retrieval."""

    def test_get_latest_backup(self, service: BackupVerificationService, now: datetime) -> None:
        """Test getting the most recent backup of a type."""
        old_checksum = _make_checksum("old")
        new_checksum = _make_checksum("new")

        service.register_backup(
            backup_type=BackupType.NEO4J_FULL,
            timestamp=now - timedelta(hours=5),
            size_bytes=2_000_000_000,
            checksum=old_checksum,
        )
        service.register_backup(
            backup_type=BackupType.NEO4J_FULL,
            timestamp=now - timedelta(hours=1),
            size_bytes=2_100_000_000,
            checksum=new_checksum,
        )

        latest = service.get_latest_backup(BackupType.NEO4J_FULL)
        assert latest is not None
        assert latest.checksum == new_checksum

    def test_get_latest_backup_none(self, service: BackupVerificationService) -> None:
        """Test getting latest backup when none exist."""
        latest = service.get_latest_backup(BackupType.POSTGRES_LOGICAL)
        assert latest is None

    def test_get_history_all_types(self, service: BackupVerificationService, now: datetime) -> None:
        """Test getting history across all backup types."""
        for bt in [BackupType.POSTGRES_BASE, BackupType.REDIS_RDB]:
            service.register_backup(
                backup_type=bt,
                timestamp=now - timedelta(minutes=5),
                size_bytes=100_000,
                checksum=_make_checksum(bt.value),
            )

        history = service.get_backup_history(backup_type=None, limit=10)
        assert len(history) == 2

    def test_get_history_respects_limit(self, service: BackupVerificationService, now: datetime) -> None:
        """Test that history respects the limit parameter."""
        for i in range(10):
            service.register_backup(
                backup_type=BackupType.POSTGRES_WAL,
                timestamp=now - timedelta(minutes=i),
                size_bytes=100,
                checksum=_make_checksum(f"wal-{i}"),
            )

        history = service.get_backup_history(BackupType.POSTGRES_WAL, limit=3)
        assert len(history) == 3


# ============================================================================
# Test: Service Stats
# ============================================================================


class TestServiceStats:
    """Tests for service statistics."""

    def test_stats_empty(self, service: BackupVerificationService) -> None:
        """Test stats with no backups registered."""
        stats = service.get_stats()
        assert stats["total_backups_tracked"] == 0
        assert stats["backup_types_registered"] == 0

    def test_stats_with_backups(self, service: BackupVerificationService, now: datetime) -> None:
        """Test stats after registering backups."""
        service.register_backup(
            backup_type=BackupType.POSTGRES_BASE,
            timestamp=now - timedelta(hours=1),
            size_bytes=1_000_000,
            checksum=_make_checksum(),
        )
        service.register_backup(
            backup_type=BackupType.REDIS_RDB,
            timestamp=now - timedelta(minutes=10),
            size_bytes=50_000,
            checksum=_make_checksum("redis"),
        )

        stats = service.get_stats()
        assert stats["total_backups_tracked"] == 2
        assert stats["backup_types_registered"] == 2


# ============================================================================
# Test: API Endpoints
# ============================================================================


class TestAPIEndpoints:
    """Tests for backup status API endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client for the FastAPI app."""
        from app.main import app

        return TestClient(app, raise_server_exceptions=False)

    @pytest.fixture(autouse=True)
    def _reset_service(self) -> None:
        """Reset the singleton service before each test."""
        import app.services.backup_verification_service as mod

        mod._backup_verification_service = None

    def test_backup_status_endpoint(self, client: TestClient) -> None:
        """Test GET /api/v1/ops/backup-status returns valid response."""
        response = client.get("/api/v1/ops/backup-status")

        assert response.status_code == 200
        data = response.json()
        assert "overall_status" in data
        assert "compliance_entries" in data
        assert "alerts" in data
        assert "summary" in data
        assert data["overall_status"] in ("healthy", "degraded", "critical")

    def test_rpo_compliance_endpoint(self, client: TestClient) -> None:
        """Test GET /api/v1/ops/rpo-compliance returns valid response."""
        response = client.get("/api/v1/ops/rpo-compliance")

        assert response.status_code == 200
        data = response.json()
        assert "overall_compliant" in data
        assert "violation_count" in data
        assert "warning_count" in data
        assert "entries" in data
        assert isinstance(data["entries"], list)
        assert len(data["entries"]) == len(RPO_WINDOWS)

    def test_backup_status_with_registered_backup(self, client: TestClient) -> None:
        """Test backup status after registering a backup via service."""
        now = datetime.now(timezone.utc)
        service = get_backup_verification_service()
        service.register_backup(
            backup_type=BackupType.POSTGRES_WAL,
            timestamp=now - timedelta(minutes=5),
            size_bytes=16_000_000,
            checksum=_make_checksum(),
        )

        response = client.get("/api/v1/ops/backup-status")

        assert response.status_code == 200
        data = response.json()
        assert data["total_backups_tracked"] >= 1

        # Find the WAL entry
        wal_entries = [
            e for e in data["compliance_entries"]
            if e["backup_type"] == "postgres_wal"
        ]
        assert len(wal_entries) == 1
        assert wal_entries[0]["status"] == "compliant"

    def test_rpo_compliance_shows_violation(self, client: TestClient) -> None:
        """Test RPO compliance endpoint shows violations correctly."""
        now = datetime.now(timezone.utc)
        service = get_backup_verification_service()
        # Register old WAL backup (RPO = 1 hour)
        service.register_backup(
            backup_type=BackupType.POSTGRES_WAL,
            timestamp=now - timedelta(hours=3),
            size_bytes=16_000_000,
            checksum=_make_checksum(),
        )

        response = client.get("/api/v1/ops/rpo-compliance")

        assert response.status_code == 200
        data = response.json()
        assert data["violation_count"] >= 1
        assert data["overall_compliant"] is False
