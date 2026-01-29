"""Tests for audit logging (Phase 10.3)."""

from datetime import datetime, timezone

from app.core.audit import (
    AuditAction,
    AuditEvent,
    log_audit,
    log_auth_event,
    log_data_access,
    log_export,
)


class TestAuditEvent:
    """Tests for AuditEvent model."""

    def test_audit_event_required_fields(self) -> None:
        """Test AuditEvent with required fields only."""
        event = AuditEvent(
            action=AuditAction.READ,
            resource_type="document",
        )
        assert event.action == AuditAction.READ
        assert event.resource_type == "document"
        assert event.success is True
        assert event.timestamp is not None

    def test_audit_event_all_fields(self) -> None:
        """Test AuditEvent with all fields."""
        event = AuditEvent(
            action=AuditAction.EXPORT,
            resource_type="patient_data",
            resource_id="doc-123",
            patient_id="P001",
            user_id="user-456",
            ip_address="192.168.1.1",
            details={"format": "omop"},
            success=True,
        )
        assert event.resource_id == "doc-123"
        assert event.patient_id == "P001"
        assert event.user_id == "user-456"
        assert event.ip_address == "192.168.1.1"
        assert event.details == {"format": "omop"}

    def test_audit_event_timestamp_auto_set(self) -> None:
        """Test that timestamp is automatically set."""
        before = datetime.now(timezone.utc)
        event = AuditEvent(action=AuditAction.READ, resource_type="test")
        after = datetime.now(timezone.utc)
        assert before <= event.timestamp <= after


class TestAuditActions:
    """Tests for audit action types."""

    def test_audit_action_data_operations(self) -> None:
        """Test data operation action types exist."""
        assert AuditAction.READ == "read"
        assert AuditAction.CREATE == "create"
        assert AuditAction.UPDATE == "update"
        assert AuditAction.DELETE == "delete"
        assert AuditAction.EXPORT == "export"

    def test_audit_action_auth_operations(self) -> None:
        """Test authentication action types exist."""
        assert AuditAction.AUTH_SUCCESS == "auth_success"
        assert AuditAction.AUTH_FAILURE == "auth_failure"


class TestLogFunctions:
    """Tests for audit logging convenience functions."""

    def test_log_audit_returns_event(self) -> None:
        """Test log_audit returns the audit event."""
        event = log_audit(
            action=AuditAction.READ,
            resource_type="document",
            resource_id="doc-123",
        )
        assert isinstance(event, AuditEvent)
        assert event.action == AuditAction.READ
        assert event.resource_id == "doc-123"

    def test_log_data_access_defaults_to_read(self) -> None:
        """Test log_data_access defaults to READ action."""
        event = log_data_access(
            resource_type="document",
            resource_id="doc-123",
            patient_id="P001",
        )
        assert event.action == AuditAction.READ
        assert event.patient_id == "P001"

    def test_log_data_access_custom_action(self) -> None:
        """Test log_data_access with custom action."""
        event = log_data_access(
            resource_type="document",
            action=AuditAction.CREATE,
        )
        assert event.action == AuditAction.CREATE

    def test_log_export_records_details(self) -> None:
        """Test log_export captures export details."""
        event = log_export(
            patient_id="P001",
            export_type="omop",
            record_count=42,
        )
        assert event.action == AuditAction.EXPORT
        assert event.patient_id == "P001"
        assert event.details["export_type"] == "omop"
        assert event.details["record_count"] == 42

    def test_log_auth_event_success(self) -> None:
        """Test log_auth_event for successful auth."""
        event = log_auth_event(
            success=True,
            user_id="user-123",
            ip_address="10.0.0.1",
        )
        assert event.action == AuditAction.AUTH_SUCCESS
        assert event.success is True

    def test_log_auth_event_failure(self) -> None:
        """Test log_auth_event for failed auth."""
        event = log_auth_event(
            success=False,
            ip_address="10.0.0.1",
            reason="Invalid API key",
        )
        assert event.action == AuditAction.AUTH_FAILURE
        assert event.success is False
        assert event.details["reason"] == "Invalid API key"
