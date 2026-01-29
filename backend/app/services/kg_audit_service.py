"""Audit Logging Service for Knowledge Graph Operations.

This module provides comprehensive audit logging for healthcare compliance
(HIPAA, GDPR, HITECH), tracking all access to patient data and KG operations.

Key Features:
- Immutable audit trail with cryptographic hashing
- PHI access tracking per HIPAA requirements
- Event correlation with session tracking
- Configurable retention policies
- Export to SIEM systems
- Tamper detection via hash chains
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from functools import wraps

logger = logging.getLogger(__name__)
from typing import Any, Callable, TypeVar
import asyncio
import re


class AuditEventType(str, Enum):
    """Types of auditable events."""

    # Authentication & Authorization
    LOGIN = "auth.login"
    LOGOUT = "auth.logout"
    LOGIN_FAILED = "auth.login_failed"
    SESSION_CREATED = "auth.session_created"
    SESSION_EXPIRED = "auth.session_expired"
    PERMISSION_DENIED = "auth.permission_denied"
    ROLE_CHANGED = "auth.role_changed"

    # Patient Data Access (HIPAA critical)
    PATIENT_VIEW = "patient.view"
    PATIENT_SEARCH = "patient.search"
    PATIENT_CREATE = "patient.create"
    PATIENT_UPDATE = "patient.update"
    PATIENT_DELETE = "patient.delete"
    PATIENT_EXPORT = "patient.export"
    PATIENT_GRAPH_ACCESS = "patient.graph_access"

    # Clinical Data Access
    DIAGNOSIS_VIEW = "clinical.diagnosis_view"
    DIAGNOSIS_CREATE = "clinical.diagnosis_create"
    MEDICATION_VIEW = "clinical.medication_view"
    MEDICATION_CREATE = "clinical.medication_create"
    LAB_VIEW = "clinical.lab_view"
    LAB_CREATE = "clinical.lab_create"
    PROCEDURE_VIEW = "clinical.procedure_view"
    PROCEDURE_CREATE = "clinical.procedure_create"

    # Knowledge Graph Operations
    KG_QUERY = "kg.query"
    KG_CONCEPT_LOOKUP = "kg.concept_lookup"
    KG_PATH_FINDING = "kg.path_finding"
    KG_REASONING = "kg.reasoning"
    KG_SIMILARITY = "kg.similarity"
    KG_EXPORT = "kg.export"
    KG_UPDATE = "kg.update"
    KG_DELETE = "kg.delete"

    # Batch Operations
    BATCH_START = "batch.start"
    BATCH_COMPLETE = "batch.complete"
    BATCH_FAILED = "batch.failed"
    BULK_EXPORT = "batch.bulk_export"

    # Administrative
    CONFIG_CHANGE = "admin.config_change"
    USER_CREATE = "admin.user_create"
    USER_UPDATE = "admin.user_update"
    USER_DELETE = "admin.user_delete"
    AUDIT_EXPORT = "admin.audit_export"
    SYSTEM_STARTUP = "admin.system_startup"
    SYSTEM_SHUTDOWN = "admin.system_shutdown"

    # Security Events
    SECURITY_ALERT = "security.alert"
    ANOMALY_DETECTED = "security.anomaly_detected"
    RATE_LIMIT_EXCEEDED = "security.rate_limit_exceeded"
    SUSPICIOUS_ACCESS = "security.suspicious_access"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class PHIAccessType(str, Enum):
    """Types of PHI (Protected Health Information) access."""

    NONE = "none"
    VIEW = "view"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    EXPORT = "export"


@dataclass
class AuditContext:
    """Context information for an audit event."""

    user_id: str
    session_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    correlation_id: str | None = None
    tenant_id: str | None = None
    role: str | None = None
    department: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class PHIAccess:
    """Information about PHI access for HIPAA compliance."""

    access_type: PHIAccessType
    patient_ids: list[str] = field(default_factory=list)
    data_types: list[str] = field(default_factory=list)
    record_count: int = 0
    purpose: str | None = None  # Treatment, Payment, Operations, Research, etc.
    consent_verified: bool = False
    minimum_necessary: bool = True  # HIPAA minimum necessary principle

    def to_dict(self) -> dict[str, Any]:
        result = {
            "access_type": self.access_type.value,
            "patient_ids": self.patient_ids,
            "data_types": self.data_types,
            "record_count": self.record_count,
        }
        if self.purpose:
            result["purpose"] = self.purpose
        result["consent_verified"] = self.consent_verified
        result["minimum_necessary"] = self.minimum_necessary
        return result


@dataclass
class AuditEvent:
    """An audit log event."""

    id: str
    timestamp: datetime
    event_type: AuditEventType
    severity: AuditSeverity
    context: AuditContext
    resource: str | None = None
    action: str | None = None
    outcome: str = "success"  # success, failure, partial
    reason: str | None = None
    duration_ms: int | None = None
    phi_access: PHIAccess | None = None
    details: dict[str, Any] = field(default_factory=dict)
    previous_hash: str | None = None
    event_hash: str | None = None

    def __post_init__(self):
        if self.event_hash is None:
            self.event_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of the event for integrity verification."""
        data = {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "context": self.context.to_dict(),
            "resource": self.resource,
            "action": self.action,
            "outcome": self.outcome,
            "reason": self.reason,
            "previous_hash": self.previous_hash,
        }
        if self.phi_access:
            data["phi_access"] = self.phi_access.to_dict()
        if self.details:
            data["details"] = self.details

        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "context": self.context.to_dict(),
            "outcome": self.outcome,
            "event_hash": self.event_hash,
        }
        if self.resource:
            result["resource"] = self.resource
        if self.action:
            result["action"] = self.action
        if self.reason:
            result["reason"] = self.reason
        if self.duration_ms is not None:
            result["duration_ms"] = self.duration_ms
        if self.phi_access:
            result["phi_access"] = self.phi_access.to_dict()
        if self.details:
            result["details"] = self.details
        if self.previous_hash:
            result["previous_hash"] = self.previous_hash
        return result


@dataclass
class AuditQueryFilters:
    """Filters for querying audit logs."""

    start_time: datetime | None = None
    end_time: datetime | None = None
    event_types: list[AuditEventType | None] = None
    severity_min: AuditSeverity | None = None
    user_id: str | None = None
    session_id: str | None = None
    patient_id: str | None = None
    correlation_id: str | None = None
    outcome: str | None = None
    resource_pattern: str | None = None
    has_phi_access: bool | None = None


@dataclass
class AuditStatistics:
    """Statistics about audit logs."""

    total_events: int
    events_by_type: dict[str, int]
    events_by_severity: dict[str, int]
    events_by_outcome: dict[str, int]
    unique_users: int
    unique_sessions: int
    phi_access_count: int
    time_range_start: datetime | None = None
    time_range_end: datetime | None = None


class KGAuditService:
    """Audit logging service for Knowledge Graph operations.

    Provides comprehensive audit logging for healthcare compliance.
    """

    # Event types that involve PHI access
    PHI_EVENT_TYPES = {
        AuditEventType.PATIENT_VIEW,
        AuditEventType.PATIENT_SEARCH,
        AuditEventType.PATIENT_CREATE,
        AuditEventType.PATIENT_UPDATE,
        AuditEventType.PATIENT_DELETE,
        AuditEventType.PATIENT_EXPORT,
        AuditEventType.PATIENT_GRAPH_ACCESS,
        AuditEventType.DIAGNOSIS_VIEW,
        AuditEventType.DIAGNOSIS_CREATE,
        AuditEventType.MEDICATION_VIEW,
        AuditEventType.MEDICATION_CREATE,
        AuditEventType.LAB_VIEW,
        AuditEventType.LAB_CREATE,
        AuditEventType.PROCEDURE_VIEW,
        AuditEventType.PROCEDURE_CREATE,
        AuditEventType.BULK_EXPORT,
    }

    # Severity mapping for event types
    SEVERITY_MAP = {
        AuditEventType.LOGIN_FAILED: AuditSeverity.WARNING,
        AuditEventType.PERMISSION_DENIED: AuditSeverity.WARNING,
        AuditEventType.SECURITY_ALERT: AuditSeverity.CRITICAL,
        AuditEventType.ANOMALY_DETECTED: AuditSeverity.WARNING,
        AuditEventType.RATE_LIMIT_EXCEEDED: AuditSeverity.WARNING,
        AuditEventType.SUSPICIOUS_ACCESS: AuditSeverity.CRITICAL,
        AuditEventType.PATIENT_DELETE: AuditSeverity.WARNING,
        AuditEventType.USER_DELETE: AuditSeverity.WARNING,
        AuditEventType.BATCH_FAILED: AuditSeverity.ERROR,
    }

    def __init__(
        self,
        retention_days: int = 365 * 7,  # 7 years for HIPAA
        max_events_in_memory: int = 100000,
    ):
        self.retention_days = retention_days
        self.max_events_in_memory = max_events_in_memory
        self._events: list[AuditEvent] = []
        self._events_by_user: dict[str, list[str]] = defaultdict(list)
        self._events_by_session: dict[str, list[str]] = defaultdict(list)
        self._events_by_patient: dict[str, list[str]] = defaultdict(list)
        self._events_by_correlation: dict[str, list[str]] = defaultdict(list)
        self._event_index: dict[str, AuditEvent] = {}
        self._last_hash: str | None = None
        self._lock = threading.RLock()
        self._listeners: list[Callable[[AuditEvent], None]] = []

    def log(
        self,
        event_type: AuditEventType,
        context: AuditContext,
        resource: str | None = None,
        action: str | None = None,
        outcome: str = "success",
        reason: str | None = None,
        duration_ms: int | None = None,
        phi_access: PHIAccess | None = None,
        details: dict[str, Any | None] = None,
        severity: AuditSeverity | None = None,
    ) -> AuditEvent:
        """Log an audit event."""
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)

        # Determine severity - first check SEVERITY_MAP, then fallback based on outcome
        if severity is None:
            if event_type in self.SEVERITY_MAP:
                severity = self.SEVERITY_MAP[event_type]
            elif outcome == "failure":
                severity = AuditSeverity.ERROR
            else:
                severity = AuditSeverity.INFO

        # Validate PHI access for relevant event types
        if event_type in self.PHI_EVENT_TYPES and phi_access is None:
            phi_access = PHIAccess(access_type=PHIAccessType.VIEW)

        with self._lock:
            event = AuditEvent(
                id=event_id,
                timestamp=timestamp,
                event_type=event_type,
                severity=severity,
                context=context,
                resource=resource,
                action=action,
                outcome=outcome,
                reason=reason,
                duration_ms=duration_ms,
                phi_access=phi_access,
                details=details or {},
                previous_hash=self._last_hash,
            )

            self._events.append(event)
            self._event_index[event_id] = event
            self._last_hash = event.event_hash

            # Update indexes
            self._events_by_user[context.user_id].append(event_id)
            if context.session_id:
                self._events_by_session[context.session_id].append(event_id)
            if context.correlation_id:
                self._events_by_correlation[context.correlation_id].append(event_id)
            if phi_access and phi_access.patient_ids:
                for patient_id in phi_access.patient_ids:
                    self._events_by_patient[patient_id].append(event_id)

            # Cleanup old events if needed
            self._cleanup_if_needed()

        # Notify listeners
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                pass  # Don't let listener errors affect audit logging

        return event

    def log_phi_access(
        self,
        event_type: AuditEventType,
        context: AuditContext,
        patient_ids: list[str],
        data_types: list[str],
        purpose: str,
        record_count: int = 1,
        consent_verified: bool = False,
        resource: str | None = None,
        duration_ms: int | None = None,
        details: dict[str, Any | None] = None,
    ) -> AuditEvent:
        """Log PHI access with HIPAA-required information."""
        access_type = {
            AuditEventType.PATIENT_VIEW: PHIAccessType.VIEW,
            AuditEventType.PATIENT_SEARCH: PHIAccessType.VIEW,
            AuditEventType.PATIENT_CREATE: PHIAccessType.CREATE,
            AuditEventType.PATIENT_UPDATE: PHIAccessType.UPDATE,
            AuditEventType.PATIENT_DELETE: PHIAccessType.DELETE,
            AuditEventType.PATIENT_EXPORT: PHIAccessType.EXPORT,
            AuditEventType.PATIENT_GRAPH_ACCESS: PHIAccessType.VIEW,
        }.get(event_type, PHIAccessType.VIEW)

        phi_access = PHIAccess(
            access_type=access_type,
            patient_ids=patient_ids,
            data_types=data_types,
            record_count=record_count,
            purpose=purpose,
            consent_verified=consent_verified,
            minimum_necessary=True,
        )

        return self.log(
            event_type=event_type,
            context=context,
            resource=resource,
            action=f"access_{access_type.value}",
            phi_access=phi_access,
            duration_ms=duration_ms,
            details=details,
        )

    def log_security_event(
        self,
        event_type: AuditEventType,
        context: AuditContext,
        reason: str,
        details: dict[str, Any | None] = None,
    ) -> AuditEvent:
        """Log a security-related event."""
        return self.log(
            event_type=event_type,
            context=context,
            reason=reason,
            outcome="failure" if event_type in {
                AuditEventType.LOGIN_FAILED,
                AuditEventType.PERMISSION_DENIED,
                AuditEventType.SECURITY_ALERT,
                AuditEventType.SUSPICIOUS_ACCESS,
            } else "success",
            details=details,
            severity=AuditSeverity.CRITICAL if event_type == AuditEventType.SECURITY_ALERT else None,
        )

    def log_kg_operation(
        self,
        event_type: AuditEventType,
        context: AuditContext,
        resource: str,
        action: str,
        query: str | None = None,
        result_count: int | None = None,
        duration_ms: int | None = None,
        details: dict[str, Any | None] = None,
    ) -> AuditEvent:
        """Log a Knowledge Graph operation."""
        event_details = details or {}
        if query:
            # Redact any patient IDs from the query for the audit log
            redacted_query = self._redact_phi(query)
            event_details["query"] = redacted_query
        if result_count is not None:
            event_details["result_count"] = result_count

        return self.log(
            event_type=event_type,
            context=context,
            resource=resource,
            action=action,
            duration_ms=duration_ms,
            details=event_details,
        )

    def _redact_phi(self, text: str) -> str:
        """Redact potential PHI from text."""
        # Redact patterns that look like patient IDs
        text = re.sub(r'\bPAT-\d+\b', '[PATIENT_ID]', text)
        text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', text)  # SSN pattern
        text = re.sub(r'\b\d{10}\b', '[MRN]', text)  # MRN pattern
        return text

    def get_event(self, event_id: str) -> AuditEvent | None:
        """Get a specific audit event by ID."""
        with self._lock:
            return self._event_index.get(event_id)

    def query(
        self,
        filters: AuditQueryFilters,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditEvent], int]:
        """Query audit events with filters."""
        with self._lock:
            results = []

            for event in reversed(self._events):
                if self._matches_filters(event, filters):
                    results.append(event)

            total = len(results)
            return results[offset:offset + limit], total

    def _matches_filters(self, event: AuditEvent, filters: AuditQueryFilters) -> bool:
        """Check if an event matches the given filters."""
        if filters.start_time and event.timestamp < filters.start_time:
            return False
        if filters.end_time and event.timestamp > filters.end_time:
            return False
        if filters.event_types and event.event_type not in filters.event_types:
            return False
        if filters.severity_min:
            severity_order = [AuditSeverity.DEBUG, AuditSeverity.INFO, AuditSeverity.WARNING,
                             AuditSeverity.ERROR, AuditSeverity.CRITICAL]
            if severity_order.index(event.severity) < severity_order.index(filters.severity_min):
                return False
        if filters.user_id and event.context.user_id != filters.user_id:
            return False
        if filters.session_id and event.context.session_id != filters.session_id:
            return False
        if filters.correlation_id and event.context.correlation_id != filters.correlation_id:
            return False
        if filters.outcome and event.outcome != filters.outcome:
            return False
        if filters.resource_pattern and event.resource:
            if not re.search(filters.resource_pattern, event.resource):
                return False
        if filters.has_phi_access is not None:
            has_phi = event.phi_access is not None and event.phi_access.access_type != PHIAccessType.NONE
            if filters.has_phi_access != has_phi:
                return False
        if filters.patient_id:
            if not event.phi_access or filters.patient_id not in event.phi_access.patient_ids:
                return False
        return True

    def get_events_by_user(self, user_id: str, limit: int = 100) -> list[AuditEvent]:
        """Get events for a specific user."""
        with self._lock:
            event_ids = self._events_by_user.get(user_id, [])[-limit:]
            return [self._event_index[eid] for eid in reversed(event_ids) if eid in self._event_index]

    def get_events_by_session(self, session_id: str) -> list[AuditEvent]:
        """Get events for a specific session."""
        with self._lock:
            event_ids = self._events_by_session.get(session_id, [])
            return [self._event_index[eid] for eid in event_ids if eid in self._event_index]

    def get_events_by_patient(self, patient_id: str, limit: int = 100) -> list[AuditEvent]:
        """Get PHI access events for a specific patient."""
        with self._lock:
            event_ids = self._events_by_patient.get(patient_id, [])[-limit:]
            return [self._event_index[eid] for eid in reversed(event_ids) if eid in self._event_index]

    def get_events_by_correlation(self, correlation_id: str) -> list[AuditEvent]:
        """Get events with the same correlation ID (related operations)."""
        with self._lock:
            event_ids = self._events_by_correlation.get(correlation_id, [])
            return [self._event_index[eid] for eid in event_ids if eid in self._event_index]

    def get_statistics(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> AuditStatistics:
        """Get statistics about audit events."""
        with self._lock:
            events_by_type: dict[str, int] = defaultdict(int)
            events_by_severity: dict[str, int] = defaultdict(int)
            events_by_outcome: dict[str, int] = defaultdict(int)
            unique_users: set[str] = set()
            unique_sessions: set[str] = set()
            phi_access_count = 0
            total_events = 0

            for event in self._events:
                if start_time and event.timestamp < start_time:
                    continue
                if end_time and event.timestamp > end_time:
                    continue

                total_events += 1
                events_by_type[event.event_type.value] += 1
                events_by_severity[event.severity.value] += 1
                events_by_outcome[event.outcome] += 1
                unique_users.add(event.context.user_id)
                if event.context.session_id:
                    unique_sessions.add(event.context.session_id)
                if event.phi_access and event.phi_access.access_type != PHIAccessType.NONE:
                    phi_access_count += 1

            return AuditStatistics(
                total_events=total_events,
                events_by_type=dict(events_by_type),
                events_by_severity=dict(events_by_severity),
                events_by_outcome=dict(events_by_outcome),
                unique_users=len(unique_users),
                unique_sessions=len(unique_sessions),
                phi_access_count=phi_access_count,
                time_range_start=start_time,
                time_range_end=end_time,
            )

    def verify_chain_integrity(self) -> tuple[bool, str | None]:
        """Verify the integrity of the audit log chain.

        Returns (is_valid, first_invalid_event_id).
        """
        with self._lock:
            prev_hash = None
            for event in self._events:
                # Check previous hash matches
                if event.previous_hash != prev_hash:
                    return False, event.id

                # Recompute and verify event hash
                computed = event._compute_hash()
                if computed != event.event_hash:
                    return False, event.id

                prev_hash = event.event_hash

            return True, None

    # VP-Validation-1: Maximum records for single export to prevent memory issues
    MAX_EXPORT_RECORDS = 10000

    def export_events(
        self,
        filters: AuditQueryFilters,
        format: str = "json",
    ) -> str:
        """Export audit events for compliance reporting or SIEM integration.

        Note: Limited to MAX_EXPORT_RECORDS (10,000) per export.
        For larger exports, use pagination or streaming APIs.
        """
        events, _ = self.query(filters, limit=self.MAX_EXPORT_RECORDS)

        if format == "json":
            return json.dumps([e.to_dict() for e in events], indent=2, default=str)
        elif format == "jsonl":
            lines = [json.dumps(e.to_dict(), default=str) for e in events]
            return "\n".join(lines)
        elif format == "csv":
            if not events:
                return "id,timestamp,event_type,severity,user_id,outcome,resource,phi_access"
            lines = ["id,timestamp,event_type,severity,user_id,outcome,resource,phi_access"]
            for e in events:
                phi = "yes" if e.phi_access and e.phi_access.access_type != PHIAccessType.NONE else "no"
                lines.append(f"{e.id},{e.timestamp.isoformat()},{e.event_type.value},{e.severity.value},"
                           f"{e.context.user_id},{e.outcome},{e.resource or ''},{phi}")
            return "\n".join(lines)
        else:
            raise ValueError(f"Unknown export format: {format}")

    def add_listener(self, listener: Callable[[AuditEvent], None]):
        """Add a listener for audit events (for real-time SIEM integration)."""
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[AuditEvent], None]):
        """Remove an audit event listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _cleanup_if_needed(self):
        """Remove old events if over capacity."""
        if len(self._events) > self.max_events_in_memory:
            # Remove oldest 10%
            remove_count = int(self.max_events_in_memory * 0.1)
            for event in self._events[:remove_count]:
                self._event_index.pop(event.id, None)
            self._events = self._events[remove_count:]

    def get_recent_phi_access(
        self,
        hours: int = 24,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Get recent PHI access events for compliance monitoring."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        filters = AuditQueryFilters(
            start_time=cutoff,
            has_phi_access=True,
        )
        events, _ = self.query(filters, limit=limit)
        return events

    def get_security_events(
        self,
        hours: int = 24,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Get recent security events."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        security_types = [
            AuditEventType.LOGIN_FAILED,
            AuditEventType.PERMISSION_DENIED,
            AuditEventType.SECURITY_ALERT,
            AuditEventType.ANOMALY_DETECTED,
            AuditEventType.RATE_LIMIT_EXCEEDED,
            AuditEventType.SUSPICIOUS_ACCESS,
        ]
        filters = AuditQueryFilters(
            start_time=cutoff,
            event_types=security_types,
        )
        events, _ = self.query(filters, limit=limit)
        return events

    def clear(self):
        """Clear all events (for testing only)."""
        with self._lock:
            self._events.clear()
            self._event_index.clear()
            self._events_by_user.clear()
            self._events_by_session.clear()
            self._events_by_patient.clear()
            self._events_by_correlation.clear()
            self._last_hash = None


# Decorators for automatic audit logging

F = TypeVar('F', bound=Callable[..., Any])


def audit_log(
    audit_service: KGAuditService,
    event_type: AuditEventType,
    resource_arg: str | None = None,
    action: str | None = None,
):
    """Decorator to automatically log function calls to audit."""
    def decorator(func: F) -> F:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Try to extract context from kwargs
            context = kwargs.get("audit_context") or AuditContext(user_id="system")
            resource = kwargs.get(resource_arg) if resource_arg else None

            start_time = datetime.now(timezone.utc)
            outcome = "success"
            reason = None

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                outcome = "failure"
                reason = str(e)
                raise
            finally:
                end_time = datetime.now(timezone.utc)
                duration_ms = int((end_time - start_time).total_seconds() * 1000)
                audit_service.log(
                    event_type=event_type,
                    context=context,
                    resource=str(resource) if resource else None,
                    action=action or func.__name__,
                    outcome=outcome,
                    reason=reason,
                    duration_ms=duration_ms,
                )

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            context = kwargs.get("audit_context") or AuditContext(user_id="system")
            resource = kwargs.get(resource_arg) if resource_arg else None

            start_time = datetime.now(timezone.utc)
            outcome = "success"
            reason = None

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                outcome = "failure"
                reason = str(e)
                raise
            finally:
                end_time = datetime.now(timezone.utc)
                duration_ms = int((end_time - start_time).total_seconds() * 1000)
                audit_service.log(
                    event_type=event_type,
                    context=context,
                    resource=str(resource) if resource else None,
                    action=action or func.__name__,
                    outcome=outcome,
                    reason=reason,
                    duration_ms=duration_ms,
                )

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


# Singleton instance
_audit_service: KGAuditService | None = None


def get_audit_service() -> KGAuditService:
    """Get the singleton audit service instance."""
    global _audit_service
    if _audit_service is None:
        _audit_service = KGAuditService()
    return _audit_service


def reset_audit_service():
    """Reset the audit service (for testing)."""
    global _audit_service
    _audit_service = None
