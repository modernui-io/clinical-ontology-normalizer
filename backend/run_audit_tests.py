#!/usr/bin/env python3
"""Standalone test runner for KG Audit Service tests."""

import sys
import os
import importlib.util
import traceback
from datetime import datetime, timedelta

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Create comprehensive mocks for dependencies
class MockModule:
    def __getattr__(self, name):
        return MockModule()
    def __call__(self, *args, **kwargs):
        return MockModule()

# Mock the problematic modules before any imports
sys.modules["sentence_transformers"] = MockModule()
sys.modules["sentence_transformers"].SentenceTransformer = MockModule()
sys.modules["neo4j"] = MockModule()
sys.modules["neo4j"].GraphDatabase = MockModule()

# Load the module directly
spec = importlib.util.spec_from_file_location(
    "app.services.kg_audit_service",
    "app/services/kg_audit_service.py",
    submodule_search_locations=[]
)
audit_module = importlib.util.module_from_spec(spec)
audit_module.__package__ = "app.services"
sys.modules["app.services.kg_audit_service"] = audit_module
spec.loader.exec_module(audit_module)

# Import the module under test
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


def run_test(name, test_func):
    """Run a single test."""
    try:
        test_func()
        print(f"  ✓ {name}")
        return True
    except AssertionError as e:
        print(f"  ✗ {name}: {e}")
        return False
    except Exception as e:
        print(f"  ✗ {name}: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False


# AuditContext tests
def test_create_context():
    ctx = AuditContext(
        user_id="user123",
        session_id="session456",
        ip_address="192.168.1.1",
    )
    assert ctx.user_id == "user123"
    assert ctx.session_id == "session456"


def test_context_to_dict():
    ctx = AuditContext(
        user_id="user123",
        role="admin",
    )
    result = ctx.to_dict()
    assert result["user_id"] == "user123"
    assert result["role"] == "admin"
    assert "session_id" not in result


# PHIAccess tests
def test_create_phi_access():
    phi = PHIAccess(
        access_type=PHIAccessType.VIEW,
        patient_ids=["PAT-001", "PAT-002"],
        data_types=["diagnosis", "medication"],
        record_count=5,
        purpose="Treatment",
    )
    assert phi.access_type == PHIAccessType.VIEW
    assert len(phi.patient_ids) == 2


def test_phi_access_to_dict():
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


# AuditEvent tests
def test_create_event():
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


def test_event_hash_computed():
    ctx = AuditContext(user_id="user123")
    event = AuditEvent(
        id="evt-001",
        timestamp=datetime.utcnow(),
        event_type=AuditEventType.KG_QUERY,
        severity=AuditSeverity.INFO,
        context=ctx,
    )
    assert len(event.event_hash) == 64


def test_event_to_dict():
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


# KGAuditService tests
def test_log_event():
    service = KGAuditService()
    context = AuditContext(user_id="user123", session_id="session456")
    event = service.log(
        event_type=AuditEventType.LOGIN,
        context=context,
    )
    assert event is not None
    assert event.event_type == AuditEventType.LOGIN


def test_log_event_with_details():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
    event = service.log(
        event_type=AuditEventType.KG_QUERY,
        context=context,
        resource="kg/concepts",
        action="search",
        details={"query": "diabetes"},
    )
    assert event.resource == "kg/concepts"
    assert event.details["query"] == "diabetes"


def test_log_phi_access():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
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


def test_log_security_event():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
    event = service.log_security_event(
        event_type=AuditEventType.LOGIN_FAILED,
        context=context,
        reason="Invalid password",
    )
    assert event.outcome == "failure"
    assert event.severity == AuditSeverity.WARNING


def test_log_kg_operation():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
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


def test_get_event():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
    event = service.log(
        event_type=AuditEventType.LOGIN,
        context=context,
    )
    retrieved = service.get_event(event.id)
    assert retrieved is not None
    assert retrieved.id == event.id


def test_get_event_not_found():
    service = KGAuditService()
    result = service.get_event("nonexistent")
    assert result is None


def test_query_events():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
    service.log(AuditEventType.LOGIN, context)
    service.log(AuditEventType.KG_QUERY, context)
    service.log(AuditEventType.LOGOUT, context)

    filters = AuditQueryFilters(
        event_types=[AuditEventType.LOGIN, AuditEventType.LOGOUT],
    )
    events, total = service.query(filters)
    assert total == 2


def test_query_events_by_user():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
    service.log(AuditEventType.LOGIN, context)
    other_ctx = AuditContext(user_id="other_user")
    service.log(AuditEventType.LOGIN, other_ctx)

    filters = AuditQueryFilters(user_id="user123")
    events, total = service.query(filters)
    assert total == 1
    assert events[0].context.user_id == "user123"


def test_query_events_by_time_range():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
    service.log(AuditEventType.LOGIN, context)

    filters = AuditQueryFilters(
        start_time=datetime.utcnow() + timedelta(hours=1),
    )
    events, total = service.query(filters)
    assert total == 0


def test_query_events_by_severity():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
    service.log(AuditEventType.LOGIN, context, severity=AuditSeverity.INFO)
    service.log(AuditEventType.LOGIN_FAILED, context)
    service.log_security_event(
        AuditEventType.SECURITY_ALERT,
        context,
        reason="Test"
    )

    filters = AuditQueryFilters(severity_min=AuditSeverity.WARNING)
    events, total = service.query(filters)
    assert total == 2


def test_query_events_by_outcome():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
    service.log(AuditEventType.LOGIN, context, outcome="success")
    service.log(AuditEventType.LOGIN, context, outcome="failure")

    filters = AuditQueryFilters(outcome="failure")
    events, total = service.query(filters)
    assert total == 1


def test_query_events_by_phi_access():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
    service.log(AuditEventType.KG_QUERY, context)
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


def test_query_events_by_patient():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
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


def test_get_events_by_user():
    service = KGAuditService()
    context = AuditContext(user_id="user123", session_id="s1")
    service.log(AuditEventType.LOGIN, context)
    service.log(AuditEventType.KG_QUERY, context)

    events = service.get_events_by_user("user123")
    assert len(events) == 2


def test_get_events_by_session():
    service = KGAuditService()
    context = AuditContext(user_id="user123", session_id="session456")
    service.log(AuditEventType.LOGIN, context)
    service.log(AuditEventType.KG_QUERY, context)

    events = service.get_events_by_session("session456")
    assert len(events) == 2


def test_get_events_by_patient():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
    service.log_phi_access(
        AuditEventType.PATIENT_VIEW,
        context,
        patient_ids=["PAT-001"],
        data_types=["diagnosis"],
        purpose="Treatment",
    )

    events = service.get_events_by_patient("PAT-001")
    assert len(events) == 1


def test_get_events_by_correlation():
    service = KGAuditService()
    context = AuditContext(user_id="user123", correlation_id="corr-001")
    service.log(AuditEventType.BATCH_START, context)
    service.log(AuditEventType.KG_QUERY, context)
    service.log(AuditEventType.BATCH_COMPLETE, context)

    events = service.get_events_by_correlation("corr-001")
    assert len(events) == 3


def test_get_statistics():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
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


def test_verify_chain_integrity():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
    service.log(AuditEventType.LOGIN, context)
    service.log(AuditEventType.KG_QUERY, context)
    service.log(AuditEventType.LOGOUT, context)

    is_valid, invalid_id = service.verify_chain_integrity()
    assert is_valid is True
    assert invalid_id is None


def test_export_events_json():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
    service.log(AuditEventType.LOGIN, context)
    service.log(AuditEventType.LOGOUT, context)

    export = service.export_events(AuditQueryFilters(), format="json")
    assert "auth.login" in export
    assert "auth.logout" in export


def test_export_events_jsonl():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
    service.log(AuditEventType.LOGIN, context)
    service.log(AuditEventType.LOGOUT, context)

    export = service.export_events(AuditQueryFilters(), format="jsonl")
    lines = export.split("\n")
    assert len(lines) == 2


def test_export_events_csv():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
    service.log(AuditEventType.LOGIN, context)

    export = service.export_events(AuditQueryFilters(), format="csv")
    assert "id,timestamp,event_type" in export
    assert "auth.login" in export


def test_export_invalid_format():
    service = KGAuditService()
    try:
        service.export_events(AuditQueryFilters(), format="xml")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_add_listener():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
    received_events = []

    def listener(event):
        received_events.append(event)

    service.add_listener(listener)
    service.log(AuditEventType.LOGIN, context)

    assert len(received_events) == 1


def test_remove_listener():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
    received_events = []

    def listener(event):
        received_events.append(event)

    service.add_listener(listener)
    service.log(AuditEventType.LOGIN, context)
    service.remove_listener(listener)
    service.log(AuditEventType.LOGOUT, context)

    assert len(received_events) == 1


def test_get_recent_phi_access():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
    service.log_phi_access(
        AuditEventType.PATIENT_VIEW,
        context,
        patient_ids=["PAT-001"],
        data_types=["diagnosis"],
        purpose="Treatment",
    )

    events = service.get_recent_phi_access(hours=24)
    assert len(events) == 1


def test_get_security_events():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
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


def test_redact_phi():
    service = KGAuditService()
    redacted = service._redact_phi("SELECT * FROM patients WHERE id = PAT-12345")
    assert "[PATIENT_ID]" in redacted
    assert "PAT-12345" not in redacted


def test_redact_ssn():
    service = KGAuditService()
    redacted = service._redact_phi("SSN: 123-45-6789")
    assert "[SSN]" in redacted


def test_auto_phi_for_patient_events():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
    event = service.log(
        event_type=AuditEventType.PATIENT_VIEW,
        context=context,
    )
    assert event.phi_access is not None


def test_severity_mapping():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
    event = service.log_security_event(
        AuditEventType.SECURITY_ALERT,
        context,
        reason="Test alert",
    )
    assert event.severity == AuditSeverity.CRITICAL


def test_cleanup_old_events():
    service = KGAuditService(max_events_in_memory=100)
    context = AuditContext(user_id="user")

    for i in range(150):
        service.log(AuditEventType.KG_QUERY, context)

    assert len(service._events) <= 100


def test_clear():
    service = KGAuditService()
    context = AuditContext(user_id="user123")
    service.log(AuditEventType.LOGIN, context)
    service.log(AuditEventType.LOGOUT, context)
    service.clear()

    events, total = service.query(AuditQueryFilters())
    assert total == 0


def test_decorator_logs_success():
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


def test_decorator_logs_failure():
    service = KGAuditService()
    context = AuditContext(user_id="user123")

    @audit_log(service, AuditEventType.KG_QUERY)
    def failing_query(audit_context=None):
        raise ValueError("Query failed")

    try:
        failing_query(audit_context=context)
        assert False, "Should have raised"
    except ValueError:
        pass

    events = service.get_events_by_user("user123")
    assert len(events) == 1
    assert events[0].outcome == "failure"
    assert events[0].reason == "Query failed"


def test_singleton_returns_same_instance():
    reset_audit_service()
    s1 = get_audit_service()
    s2 = get_audit_service()
    assert s1 is s2
    reset_audit_service()


def test_hash_chain_links():
    service = KGAuditService()
    context = AuditContext(user_id="user")

    e1 = service.log(AuditEventType.LOGIN, context)
    e2 = service.log(AuditEventType.KG_QUERY, context)
    e3 = service.log(AuditEventType.LOGOUT, context)

    assert e1.previous_hash is None
    assert e2.previous_hash == e1.event_hash
    assert e3.previous_hash == e2.event_hash


def test_tamper_detection():
    service = KGAuditService()
    context = AuditContext(user_id="user")

    service.log(AuditEventType.LOGIN, context)
    service.log(AuditEventType.KG_QUERY, context)

    # Tamper with an event
    service._events[0].details["tampered"] = True

    is_valid, invalid_id = service.verify_chain_integrity()
    assert is_valid is False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("KG Audit Service Tests")
    print("=" * 60 + "\n")

    tests = [
        # AuditContext tests
        ("create_context", test_create_context),
        ("context_to_dict", test_context_to_dict),

        # PHIAccess tests
        ("create_phi_access", test_create_phi_access),
        ("phi_access_to_dict", test_phi_access_to_dict),

        # AuditEvent tests
        ("create_event", test_create_event),
        ("event_hash_computed", test_event_hash_computed),
        ("event_to_dict", test_event_to_dict),

        # KGAuditService tests
        ("log_event", test_log_event),
        ("log_event_with_details", test_log_event_with_details),
        ("log_phi_access", test_log_phi_access),
        ("log_security_event", test_log_security_event),
        ("log_kg_operation", test_log_kg_operation),
        ("get_event", test_get_event),
        ("get_event_not_found", test_get_event_not_found),
        ("query_events", test_query_events),
        ("query_events_by_user", test_query_events_by_user),
        ("query_events_by_time_range", test_query_events_by_time_range),
        ("query_events_by_severity", test_query_events_by_severity),
        ("query_events_by_outcome", test_query_events_by_outcome),
        ("query_events_by_phi_access", test_query_events_by_phi_access),
        ("query_events_by_patient", test_query_events_by_patient),
        ("get_events_by_user", test_get_events_by_user),
        ("get_events_by_session", test_get_events_by_session),
        ("get_events_by_patient", test_get_events_by_patient),
        ("get_events_by_correlation", test_get_events_by_correlation),
        ("get_statistics", test_get_statistics),
        ("verify_chain_integrity", test_verify_chain_integrity),
        ("export_events_json", test_export_events_json),
        ("export_events_jsonl", test_export_events_jsonl),
        ("export_events_csv", test_export_events_csv),
        ("export_invalid_format", test_export_invalid_format),
        ("add_listener", test_add_listener),
        ("remove_listener", test_remove_listener),
        ("get_recent_phi_access", test_get_recent_phi_access),
        ("get_security_events", test_get_security_events),
        ("redact_phi", test_redact_phi),
        ("redact_ssn", test_redact_ssn),
        ("auto_phi_for_patient_events", test_auto_phi_for_patient_events),
        ("severity_mapping", test_severity_mapping),
        ("cleanup_old_events", test_cleanup_old_events),
        ("clear", test_clear),

        # Decorator tests
        ("decorator_logs_success", test_decorator_logs_success),
        ("decorator_logs_failure", test_decorator_logs_failure),

        # Singleton tests
        ("singleton_returns_same_instance", test_singleton_returns_same_instance),

        # Chain integrity tests
        ("hash_chain_links", test_hash_chain_links),
        ("tamper_detection", test_tamper_detection),
    ]

    passed = 0
    failed = 0

    for name, test in tests:
        if run_test(name, test):
            passed += 1
        else:
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
