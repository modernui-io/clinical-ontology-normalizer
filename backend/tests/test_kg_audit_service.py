"""Tests for KG Audit Service."""

import pytest
import time
from datetime import datetime, timedelta

from app.services.kg_audit_service import (
    AuditEventType,
    AuditSeverity,
    PHIAccessType,
    AuditContext,
    PHIAccess,
    AuditEvent,
    AuditQueryFilters,
    KGAuditService,
    get_audit_service,
    reset_audit_service,
    audit_log,
)


class TestAuditContext:
    """Tests for AuditContext."""

    def test_create_context(self):
        """Create an audit context."""
        ctx = AuditContext(
            user_id="user123",
            session_id="session456",
            ip_address="192.168.1.1",
        )
        assert ctx.user_id == "user123"
        assert ctx.session_id == "session456"

    def test_context_to_dict(self):
        """Convert context to dictionary."""
        ctx = AuditContext(
            user_id="user123",
            role="admin",
        )
        result = ctx.to_dict()
        assert result["user_id"] == "user123"
        assert result["role"] == "admin"
        assert "session_id" not in result  # None values excluded


class TestPHIAccess:
    """Tests for PHIAccess."""

    def test_create_phi_access(self):
        """Create PHI access info."""
        phi = PHIAccess(
            access_type=PHIAccessType.VIEW,
            patient_ids=["PAT-001", "PAT-002"],
            data_types=["diagnosis", "medication"],
            record_count=5,
            purpose="Treatment",
        )
        assert phi.access_type == PHIAccessType.VIEW
        assert len(phi.patient_ids) == 2

    def test_phi_access_to_dict(self):
        """Convert PHI access to dictionary."""
        phi = PHIAccess(
            access_type=PHIAccessType.EXPORT,
            patient_ids=["PAT-001"],
            data_types=["full_record"],
            record_count=1,
            purpose="Research",
            consent_verified=True,
        )
        result = phi.to_dict()
        assert result["access_type"] == "export"
        assert result["consent_verified"] is True


class TestAuditEvent:
    """Tests for AuditEvent."""

    def test_create_event(self):
        """Create an audit event."""
        ctx = AuditContext(user_id="user123")
        event = AuditEvent(
            id="evt-001",
            timestamp=datetime.utcnow(),
            event_type=AuditEventType.PATIENT_VIEW,
            severity=AuditSeverity.INFO,
            context=ctx,
            resource="patient/PAT-001",
        )
        assert event.id == "evt-001"
        assert event.event_hash is not None

    def test_event_hash_computed(self):
        """Event hash is computed automatically."""
        ctx = AuditContext(user_id="user123")
        event = AuditEvent(
            id="evt-001",
            timestamp=datetime.utcnow(),
            event_type=AuditEventType.KG_QUERY,
            severity=AuditSeverity.INFO,
            context=ctx,
        )
        assert len(event.event_hash) == 64  # SHA-256 hex

    def test_event_to_dict(self):
        """Convert event to dictionary."""
        ctx = AuditContext(user_id="user123")
        event = AuditEvent(
            id="evt-001",
            timestamp=datetime.utcnow(),
            event_type=AuditEventType.LOGIN,
            severity=AuditSeverity.INFO,
            context=ctx,
            outcome="success",
        )
        result = event.to_dict()
        assert result["id"] == "evt-001"
        assert result["event_type"] == "auth.login"
        assert result["severity"] == "info"


class TestKGAuditService:
    """Tests for KGAuditService."""

    @pytest.fixture
    def service(self):
        return KGAuditService()

    @pytest.fixture
    def context(self):
        return AuditContext(
            user_id="user123",
            session_id="session456",
            ip_address="192.168.1.1",
            correlation_id="corr-001",
        )

    def test_log_event(self, service, context):
        """Log a basic event."""
        event = service.log(
            event_type=AuditEventType.LOGIN,
            context=context,
        )
        assert event is not None
        assert event.event_type == AuditEventType.LOGIN

    def test_log_event_with_details(self, service, context):
        """Log event with details."""
        event = service.log(
            event_type=AuditEventType.KG_QUERY,
            context=context,
            resource="kg/concepts",
            action="search",
            details={"query": "diabetes"},
        )
        assert event.resource == "kg/concepts"
        assert event.details["query"] == "diabetes"

    def test_log_phi_access(self, service, context):
        """Log PHI access event."""
        event = service.log_phi_access(
            event_type=AuditEventType.PATIENT_VIEW,
            context=context,
            patient_ids=["PAT-001", "PAT-002"],
            data_types=["diagnosis", "medication"],
            purpose="Treatment",
            record_count=3,
        )
        assert event.phi_access is not None
        assert event.phi_access.access_type == PHIAccessType.VIEW
        assert len(event.phi_access.patient_ids) == 2

    def test_log_security_event(self, service, context):
        """Log security event."""
        event = service.log_security_event(
            event_type=AuditEventType.LOGIN_FAILED,
            context=context,
            reason="Invalid password",
        )
        assert event.outcome == "failure"
        assert event.severity == AuditSeverity.WARNING

    def test_log_kg_operation(self, service, context):
        """Log KG operation."""
        event = service.log_kg_operation(
            event_type=AuditEventType.KG_QUERY,
            context=context,
            resource="kg/paths",
            action="find_path",
            query="MATCH (n)-[r]->(m) RETURN n,r,m",
            result_count=15,
            duration_ms=120,
        )
        assert event.details["result_count"] == 15
        assert event.duration_ms == 120

    def test_get_event(self, service, context):
        """Get event by ID."""
        event = service.log(
            event_type=AuditEventType.LOGIN,
            context=context,
        )
        retrieved = service.get_event(event.id)
        assert retrieved is not None
        assert retrieved.id == event.id

    def test_get_event_not_found(self, service):
        """Get non-existent event returns None."""
        result = service.get_event("nonexistent")
        assert result is None

    def test_query_events(self, service, context):
        """Query events with filters."""
        # Log some events
        service.log(AuditEventType.LOGIN, context)
        service.log(AuditEventType.KG_QUERY, context)
        service.log(AuditEventType.LOGOUT, context)

        filters = AuditQueryFilters(
            event_types=[AuditEventType.LOGIN, AuditEventType.LOGOUT],
        )
        events, total = service.query(filters)
        assert total == 2

    def test_query_events_by_user(self, service, context):
        """Query events by user ID."""
        service.log(AuditEventType.LOGIN, context)
        other_ctx = AuditContext(user_id="other_user")
        service.log(AuditEventType.LOGIN, other_ctx)

        filters = AuditQueryFilters(user_id="user123")
        events, total = service.query(filters)
        assert total == 1
        assert events[0].context.user_id == "user123"

    def test_query_events_by_time_range(self, service, context):
        """Query events by time range."""
        service.log(AuditEventType.LOGIN, context)

        # Query future time range
        filters = AuditQueryFilters(
            start_time=datetime.utcnow() + timedelta(hours=1),
        )
        events, total = service.query(filters)
        assert total == 0

    def test_query_events_by_severity(self, service, context):
        """Query events by minimum severity."""
        service.log(AuditEventType.LOGIN, context, severity=AuditSeverity.INFO)
        service.log(AuditEventType.LOGIN_FAILED, context)  # WARNING
        service.log_security_event(
            AuditEventType.SECURITY_ALERT,
            context,
            reason="Test"
        )  # CRITICAL

        filters = AuditQueryFilters(severity_min=AuditSeverity.WARNING)
        events, total = service.query(filters)
        assert total == 2

    def test_query_events_by_outcome(self, service, context):
        """Query events by outcome."""
        service.log(AuditEventType.LOGIN, context, outcome="success")
        service.log(AuditEventType.LOGIN, context, outcome="failure")

        filters = AuditQueryFilters(outcome="failure")
        events, total = service.query(filters)
        assert total == 1

    def test_query_events_by_phi_access(self, service, context):
        """Query events with PHI access."""
        service.log(AuditEventType.KG_QUERY, context)  # No PHI
        service.log_phi_access(
            AuditEventType.PATIENT_VIEW,
            context,
            patient_ids=["PAT-001"],
            data_types=["diagnosis"],
            purpose="Treatment",
        )

        filters = AuditQueryFilters(has_phi_access=True)
        events, total = service.query(filters)
        assert total == 1

    def test_query_events_by_patient(self, service, context):
        """Query events for a specific patient."""
        service.log_phi_access(
            AuditEventType.PATIENT_VIEW,
            context,
            patient_ids=["PAT-001"],
            data_types=["diagnosis"],
            purpose="Treatment",
        )
        service.log_phi_access(
            AuditEventType.PATIENT_VIEW,
            context,
            patient_ids=["PAT-002"],
            data_types=["medication"],
            purpose="Treatment",
        )

        filters = AuditQueryFilters(patient_id="PAT-001")
        events, total = service.query(filters)
        assert total == 1

    def test_get_events_by_user(self, service, context):
        """Get events for a user."""
        service.log(AuditEventType.LOGIN, context)
        service.log(AuditEventType.KG_QUERY, context)

        events = service.get_events_by_user("user123")
        assert len(events) == 2

    def test_get_events_by_session(self, service, context):
        """Get events for a session."""
        service.log(AuditEventType.LOGIN, context)
        service.log(AuditEventType.KG_QUERY, context)

        events = service.get_events_by_session("session456")
        assert len(events) == 2

    def test_get_events_by_patient(self, service, context):
        """Get events for a patient."""
        service.log_phi_access(
            AuditEventType.PATIENT_VIEW,
            context,
            patient_ids=["PAT-001"],
            data_types=["diagnosis"],
            purpose="Treatment",
        )

        events = service.get_events_by_patient("PAT-001")
        assert len(events) == 1

    def test_get_events_by_correlation(self, service, context):
        """Get correlated events."""
        service.log(AuditEventType.BATCH_START, context)
        service.log(AuditEventType.KG_QUERY, context)
        service.log(AuditEventType.BATCH_COMPLETE, context)

        events = service.get_events_by_correlation("corr-001")
        assert len(events) == 3

    def test_get_statistics(self, service, context):
        """Get audit statistics."""
        service.log(AuditEventType.LOGIN, context)
        service.log(AuditEventType.KG_QUERY, context)
        service.log(AuditEventType.LOGIN_FAILED, context)
        service.log_phi_access(
            AuditEventType.PATIENT_VIEW,
            context,
            patient_ids=["PAT-001"],
            data_types=["diagnosis"],
            purpose="Treatment",
        )

        stats = service.get_statistics()
        assert stats.total_events == 4
        assert stats.unique_users == 1
        assert stats.phi_access_count == 1

    def test_verify_chain_integrity(self, service, context):
        """Verify audit chain integrity."""
        service.log(AuditEventType.LOGIN, context)
        service.log(AuditEventType.KG_QUERY, context)
        service.log(AuditEventType.LOGOUT, context)

        is_valid, invalid_id = service.verify_chain_integrity()
        assert is_valid is True
        assert invalid_id is None

    def test_export_events_json(self, service, context):
        """Export events as JSON."""
        service.log(AuditEventType.LOGIN, context)
        service.log(AuditEventType.LOGOUT, context)

        export = service.export_events(AuditQueryFilters(), format="json")
        assert "auth.login" in export
        assert "auth.logout" in export

    def test_export_events_jsonl(self, service, context):
        """Export events as JSON Lines."""
        service.log(AuditEventType.LOGIN, context)
        service.log(AuditEventType.LOGOUT, context)

        export = service.export_events(AuditQueryFilters(), format="jsonl")
        lines = export.split("\n")
        assert len(lines) == 2

    def test_export_events_csv(self, service, context):
        """Export events as CSV."""
        service.log(AuditEventType.LOGIN, context)

        export = service.export_events(AuditQueryFilters(), format="csv")
        assert "id,timestamp,event_type" in export
        assert "auth.login" in export

    def test_export_invalid_format(self, service, context):
        """Export with invalid format raises error."""
        with pytest.raises(ValueError):
            service.export_events(AuditQueryFilters(), format="xml")

    def test_add_listener(self, service, context):
        """Add event listener."""
        received_events = []

        def listener(event):
            received_events.append(event)

        service.add_listener(listener)
        service.log(AuditEventType.LOGIN, context)

        assert len(received_events) == 1

    def test_remove_listener(self, service, context):
        """Remove event listener."""
        received_events = []

        def listener(event):
            received_events.append(event)

        service.add_listener(listener)
        service.log(AuditEventType.LOGIN, context)
        service.remove_listener(listener)
        service.log(AuditEventType.LOGOUT, context)

        assert len(received_events) == 1

    def test_get_recent_phi_access(self, service, context):
        """Get recent PHI access events."""
        service.log_phi_access(
            AuditEventType.PATIENT_VIEW,
            context,
            patient_ids=["PAT-001"],
            data_types=["diagnosis"],
            purpose="Treatment",
        )

        events = service.get_recent_phi_access(hours=24)
        assert len(events) == 1

    def test_get_security_events(self, service, context):
        """Get recent security events."""
        service.log_security_event(
            AuditEventType.LOGIN_FAILED,
            context,
            reason="Invalid password",
        )
        service.log_security_event(
            AuditEventType.PERMISSION_DENIED,
            context,
            reason="Unauthorized",
        )

        events = service.get_security_events(hours=24)
        assert len(events) == 2

    def test_redact_phi(self, service):
        """PHI is redacted from queries."""
        redacted = service._redact_phi("SELECT * FROM patients WHERE id = PAT-12345")
        assert "[PATIENT_ID]" in redacted
        assert "PAT-12345" not in redacted

    def test_redact_ssn(self, service):
        """SSN is redacted."""
        redacted = service._redact_phi("SSN: 123-45-6789")
        assert "[SSN]" in redacted

    def test_auto_phi_for_patient_events(self, service, context):
        """PHI access is auto-added for patient events."""
        event = service.log(
            event_type=AuditEventType.PATIENT_VIEW,
            context=context,
        )
        assert event.phi_access is not None

    def test_severity_mapping(self, service, context):
        """Event types have correct severity mapping."""
        event = service.log_security_event(
            AuditEventType.SECURITY_ALERT,
            context,
            reason="Test alert",
        )
        assert event.severity == AuditSeverity.CRITICAL

    def test_cleanup_old_events(self):
        """Old events are cleaned up when over capacity."""
        service = KGAuditService(max_events_in_memory=100)
        context = AuditContext(user_id="user")

        for i in range(150):
            service.log(AuditEventType.KG_QUERY, context)

        # Should have cleaned up some events
        assert len(service._events) <= 100

    def test_clear(self, service, context):
        """Clear all events."""
        service.log(AuditEventType.LOGIN, context)
        service.log(AuditEventType.LOGOUT, context)
        service.clear()

        events, total = service.query(AuditQueryFilters())
        assert total == 0


class TestAuditDecorator:
    """Tests for audit_log decorator."""

    def test_decorator_logs_success(self):
        """Decorator logs successful function calls."""
        service = KGAuditService()
        context = AuditContext(user_id="user123")

        @audit_log(service, AuditEventType.KG_QUERY)
        def my_query(audit_context=None):
            return {"result": "data"}

        result = my_query(audit_context=context)
        assert result == {"result": "data"}

        events = service.get_events_by_user("user123")
        assert len(events) == 1
        assert events[0].outcome == "success"

    def test_decorator_logs_failure(self):
        """Decorator logs failed function calls."""
        service = KGAuditService()
        context = AuditContext(user_id="user123")

        @audit_log(service, AuditEventType.KG_QUERY)
        def failing_query(audit_context=None):
            raise ValueError("Query failed")

        with pytest.raises(ValueError):
            failing_query(audit_context=context)

        events = service.get_events_by_user("user123")
        assert len(events) == 1
        assert events[0].outcome == "failure"
        assert events[0].reason == "Query failed"


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_audit_service_returns_same_instance(self):
        """Singleton returns same instance."""
        reset_audit_service()
        s1 = get_audit_service()
        s2 = get_audit_service()
        assert s1 is s2
        reset_audit_service()


class TestChainIntegrity:
    """Tests for audit chain integrity."""

    def test_hash_chain_links(self):
        """Events are linked by hash chain."""
        service = KGAuditService()
        context = AuditContext(user_id="user")

        e1 = service.log(AuditEventType.LOGIN, context)
        e2 = service.log(AuditEventType.KG_QUERY, context)
        e3 = service.log(AuditEventType.LOGOUT, context)

        assert e1.previous_hash is None
        assert e2.previous_hash == e1.event_hash
        assert e3.previous_hash == e2.event_hash

    def test_tamper_detection(self):
        """Tampering is detected via hash chain."""
        service = KGAuditService()
        context = AuditContext(user_id="user")

        service.log(AuditEventType.LOGIN, context)
        service.log(AuditEventType.KG_QUERY, context)

        # Tamper with an event
        service._events[0].details["tampered"] = True

        is_valid, invalid_id = service.verify_chain_integrity()
        assert is_valid is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
