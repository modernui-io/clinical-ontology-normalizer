"""Security incident tracking service for CISO-11 Incident Response.

Provides centralized incident lifecycle management with:
- Severity classification (SEV1-SEV4)
- State machine (DETECTED -> TRIAGING -> CONTAINED -> ERADICATING -> RECOVERING -> CLOSED)
- Timeline event tracking
- Responder assignment
- Auto-escalation for unacknowledged SEV1 incidents
- In-memory storage (production deployments should use database persistence)

Usage:
    from app.services.incident_service import get_incident_service

    service = get_incident_service()
    incident = service.create_incident(
        title="Unauthorized PHI access detected",
        description="Audit logs show bulk patient record access from unknown IP",
        severity=IncidentSeverity.SEV1,
        incident_type=IncidentType.PHI_BREACH,
        reported_by="security-analyst-1",
    )
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from threading import Lock
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Singleton instance and lock
_incident_service_instance: "IncidentService | None" = None
_incident_service_lock = Lock()

# Auto-escalation threshold for SEV1 incidents (minutes)
SEV1_ACKNOWLEDGE_TIMEOUT_MINUTES = 15


class IncidentSeverity(str, Enum):
    """Incident severity levels aligned with the Incident Response Plan."""

    SEV1 = "SEV1"  # Critical / Data Breach
    SEV2 = "SEV2"  # High / Service Outage
    SEV3 = "SEV3"  # Medium / Security Event
    SEV4 = "SEV4"  # Low / Anomaly


class IncidentStatus(str, Enum):
    """Incident lifecycle states."""

    DETECTED = "DETECTED"
    TRIAGING = "TRIAGING"
    CONTAINED = "CONTAINED"
    ERADICATING = "ERADICATING"
    RECOVERING = "RECOVERING"
    CLOSED = "CLOSED"


class IncidentType(str, Enum):
    """Incident type classification."""

    PHI_BREACH = "PHI_BREACH"
    UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS"
    DATA_EXFILTRATION = "DATA_EXFILTRATION"
    RANSOMWARE = "RANSOMWARE"
    DDOS = "DDOS"
    INSIDER_THREAT = "INSIDER_THREAT"
    SYSTEM_COMPROMISE = "SYSTEM_COMPROMISE"
    CREDENTIAL_LEAK = "CREDENTIAL_LEAK"
    VULNERABILITY_EXPLOITATION = "VULNERABILITY_EXPLOITATION"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    SERVICE_OUTAGE = "SERVICE_OUTAGE"
    OTHER = "OTHER"


# Valid state transitions
VALID_TRANSITIONS: dict[IncidentStatus, list[IncidentStatus]] = {
    IncidentStatus.DETECTED: [IncidentStatus.TRIAGING, IncidentStatus.CLOSED],
    IncidentStatus.TRIAGING: [IncidentStatus.CONTAINED, IncidentStatus.CLOSED],
    IncidentStatus.CONTAINED: [IncidentStatus.ERADICATING, IncidentStatus.CLOSED],
    IncidentStatus.ERADICATING: [IncidentStatus.RECOVERING, IncidentStatus.CONTAINED, IncidentStatus.CLOSED],
    IncidentStatus.RECOVERING: [IncidentStatus.CLOSED, IncidentStatus.ERADICATING],
    IncidentStatus.CLOSED: [],  # Terminal state
}


class TimelineEvent(BaseModel):
    """A single event in an incident timeline."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str  # e.g., "status_change", "note", "escalation", "notification"
    description: str
    actor: str | None = None  # Who performed this action
    metadata: dict[str, Any] = Field(default_factory=dict)


class Incident(BaseModel):
    """A security incident record."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus = IncidentStatus.DETECTED
    incident_type: IncidentType
    reported_by: str
    reported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_at: datetime | None = None
    contained_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Assigned responders
    incident_commander: str | None = None
    assigned_responders: list[str] = Field(default_factory=list)

    # Affected systems and evidence
    affected_systems: list[str] = Field(default_factory=list)
    evidence_links: list[str] = Field(default_factory=list)
    phi_involved: bool = False
    estimated_affected_records: int | None = None

    # Timeline
    timeline: list[TimelineEvent] = Field(default_factory=list)

    # Auto-escalation tracking
    escalated: bool = False
    original_severity: IncidentSeverity | None = None


class IncidentService:
    """Service for managing security incident lifecycle.

    Uses in-memory storage. Production deployments should persist
    incidents to the database.
    """

    def __init__(self) -> None:
        """Initialize the incident service with empty storage."""
        self._incidents: dict[str, Incident] = {}
        self._lock = Lock()
        logger.info("IncidentService initialized")

    def create_incident(
        self,
        title: str,
        description: str,
        severity: IncidentSeverity,
        incident_type: IncidentType,
        reported_by: str,
        affected_systems: list[str] | None = None,
        phi_involved: bool = False,
        incident_commander: str | None = None,
    ) -> Incident:
        """Create a new security incident.

        Args:
            title: Brief incident title.
            description: Detailed description of the incident.
            severity: Severity classification (SEV1-SEV4).
            incident_type: Type of incident.
            reported_by: Identifier of the person reporting.
            affected_systems: List of affected system names.
            phi_involved: Whether PHI is potentially involved.
            incident_commander: Assigned incident commander.

        Returns:
            The created Incident record.
        """
        incident = Incident(
            title=title,
            description=description,
            severity=severity,
            incident_type=incident_type,
            reported_by=reported_by,
            affected_systems=affected_systems or [],
            phi_involved=phi_involved,
            incident_commander=incident_commander,
        )

        # Add creation timeline event
        incident.timeline.append(
            TimelineEvent(
                event_type="created",
                description=f"Incident created with severity {severity.value}",
                actor=reported_by,
            )
        )

        with self._lock:
            self._incidents[incident.id] = incident

        logger.info(
            f"Incident created: id={incident.id}, severity={severity.value}, "
            f"type={incident_type.value}, phi={phi_involved}"
        )

        return incident

    def get_incident(self, incident_id: str) -> Incident | None:
        """Retrieve an incident by ID.

        Args:
            incident_id: The unique incident identifier.

        Returns:
            The Incident if found, otherwise None.
        """
        with self._lock:
            return self._incidents.get(incident_id)

    def update_incident(
        self,
        incident_id: str,
        status: IncidentStatus | None = None,
        severity: IncidentSeverity | None = None,
        title: str | None = None,
        description: str | None = None,
        incident_commander: str | None = None,
        assigned_responders: list[str] | None = None,
        affected_systems: list[str] | None = None,
        evidence_links: list[str] | None = None,
        phi_involved: bool | None = None,
        estimated_affected_records: int | None = None,
        updated_by: str | None = None,
    ) -> Incident:
        """Update an existing incident.

        Args:
            incident_id: The unique incident identifier.
            status: New status (must be a valid transition).
            severity: Updated severity classification.
            title: Updated title.
            description: Updated description.
            incident_commander: Updated incident commander.
            assigned_responders: Updated list of responders.
            affected_systems: Updated list of affected systems.
            evidence_links: Updated list of evidence links.
            phi_involved: Updated PHI involvement flag.
            estimated_affected_records: Updated affected records count.
            updated_by: Who is making this update.

        Returns:
            The updated Incident.

        Raises:
            ValueError: If incident not found or invalid state transition.
        """
        with self._lock:
            incident = self._incidents.get(incident_id)
            if incident is None:
                raise ValueError(f"Incident not found: {incident_id}")

            now = datetime.now(timezone.utc)

            # Handle status transition
            if status is not None and status != incident.status:
                valid_next = VALID_TRANSITIONS.get(incident.status, [])
                if status not in valid_next:
                    raise ValueError(
                        f"Invalid status transition: {incident.status.value} -> {status.value}. "
                        f"Valid transitions: {[s.value for s in valid_next]}"
                    )

                old_status = incident.status
                incident.status = status

                # Track key timestamps
                if status == IncidentStatus.TRIAGING and incident.acknowledged_at is None:
                    incident.acknowledged_at = now
                elif status == IncidentStatus.CONTAINED:
                    incident.contained_at = now
                elif status == IncidentStatus.CLOSED:
                    incident.closed_at = now
                    incident.resolved_at = now

                # Add timeline event
                incident.timeline.append(
                    TimelineEvent(
                        event_type="status_change",
                        description=f"Status changed from {old_status.value} to {status.value}",
                        actor=updated_by,
                        metadata={"old_status": old_status.value, "new_status": status.value},
                    )
                )

            # Handle severity change
            if severity is not None and severity != incident.severity:
                old_severity = incident.severity
                if incident.original_severity is None:
                    incident.original_severity = old_severity
                incident.severity = severity
                incident.timeline.append(
                    TimelineEvent(
                        event_type="severity_change",
                        description=f"Severity changed from {old_severity.value} to {severity.value}",
                        actor=updated_by,
                        metadata={"old_severity": old_severity.value, "new_severity": severity.value},
                    )
                )

            # Update other fields
            if title is not None:
                incident.title = title
            if description is not None:
                incident.description = description
            if incident_commander is not None:
                incident.incident_commander = incident_commander
            if assigned_responders is not None:
                incident.assigned_responders = assigned_responders
            if affected_systems is not None:
                incident.affected_systems = affected_systems
            if evidence_links is not None:
                incident.evidence_links = evidence_links
            if phi_involved is not None:
                incident.phi_involved = phi_involved
            if estimated_affected_records is not None:
                incident.estimated_affected_records = estimated_affected_records

            incident.updated_at = now

        logger.info(f"Incident updated: id={incident_id}, status={incident.status.value}")
        return incident

    def add_timeline_event(
        self,
        incident_id: str,
        event_type: str,
        description: str,
        actor: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TimelineEvent:
        """Add a timeline event to an incident.

        Args:
            incident_id: The unique incident identifier.
            event_type: Type of event (e.g., "note", "action", "escalation").
            description: Description of the event.
            actor: Who performed the action.
            metadata: Additional event data.

        Returns:
            The created TimelineEvent.

        Raises:
            ValueError: If incident not found.
        """
        with self._lock:
            incident = self._incidents.get(incident_id)
            if incident is None:
                raise ValueError(f"Incident not found: {incident_id}")

            event = TimelineEvent(
                event_type=event_type,
                description=description,
                actor=actor,
                metadata=metadata or {},
            )

            incident.timeline.append(event)
            incident.updated_at = datetime.now(timezone.utc)

        logger.info(
            f"Timeline event added: incident={incident_id}, type={event_type}"
        )
        return event

    def list_incidents(
        self,
        severity: IncidentSeverity | None = None,
        status: IncidentStatus | None = None,
        incident_type: IncidentType | None = None,
        phi_involved: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Incident], int]:
        """List incidents with optional filters.

        Args:
            severity: Filter by severity level.
            status: Filter by status.
            incident_type: Filter by incident type.
            phi_involved: Filter by PHI involvement.
            limit: Maximum number of results.
            offset: Pagination offset.

        Returns:
            Tuple of (filtered incidents, total count).
        """
        with self._lock:
            filtered = list(self._incidents.values())

        # Apply filters
        if severity is not None:
            filtered = [i for i in filtered if i.severity == severity]
        if status is not None:
            filtered = [i for i in filtered if i.status == status]
        if incident_type is not None:
            filtered = [i for i in filtered if i.incident_type == incident_type]
        if phi_involved is not None:
            filtered = [i for i in filtered if i.phi_involved == phi_involved]

        # Sort by reported_at descending (most recent first)
        filtered.sort(key=lambda i: i.reported_at, reverse=True)

        total = len(filtered)

        # Apply pagination
        filtered = filtered[offset : offset + limit]

        return filtered, total

    def check_auto_escalation(self) -> list[Incident]:
        """Check for SEV1 incidents needing auto-escalation.

        SEV1 incidents that have not been acknowledged (moved past DETECTED
        status) within SEV1_ACKNOWLEDGE_TIMEOUT_MINUTES are flagged for
        escalation.

        Returns:
            List of incidents that were auto-escalated.
        """
        escalated = []
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(minutes=SEV1_ACKNOWLEDGE_TIMEOUT_MINUTES)

        with self._lock:
            for incident in self._incidents.values():
                if (
                    incident.severity == IncidentSeverity.SEV1
                    and incident.status == IncidentStatus.DETECTED
                    and incident.reported_at < threshold
                    and not incident.escalated
                ):
                    incident.escalated = True
                    incident.timeline.append(
                        TimelineEvent(
                            event_type="auto_escalation",
                            description=(
                                f"AUTO-ESCALATION: SEV1 incident not acknowledged within "
                                f"{SEV1_ACKNOWLEDGE_TIMEOUT_MINUTES} minutes. "
                                f"Escalating to backup Incident Commander and CISO."
                            ),
                            actor="system",
                            metadata={
                                "escalation_reason": "sev1_acknowledge_timeout",
                                "timeout_minutes": SEV1_ACKNOWLEDGE_TIMEOUT_MINUTES,
                                "reported_at": incident.reported_at.isoformat(),
                            },
                        )
                    )
                    incident.updated_at = now
                    escalated.append(incident)

                    logger.warning(
                        f"AUTO-ESCALATION: SEV1 incident {incident.id} not acknowledged "
                        f"within {SEV1_ACKNOWLEDGE_TIMEOUT_MINUTES} minutes"
                    )

        return escalated

    def get_stats(self) -> dict[str, Any]:
        """Get incident service statistics.

        Returns:
            Dictionary with counts by severity and status.
        """
        with self._lock:
            incidents = list(self._incidents.values())

        severity_counts = {}
        for sev in IncidentSeverity:
            severity_counts[sev.value] = len([i for i in incidents if i.severity == sev])

        status_counts = {}
        for st in IncidentStatus:
            status_counts[st.value] = len([i for i in incidents if i.status == st])

        open_incidents = [
            i for i in incidents if i.status != IncidentStatus.CLOSED
        ]

        return {
            "total_incidents": len(incidents),
            "open_incidents": len(open_incidents),
            "by_severity": severity_counts,
            "by_status": status_counts,
            "phi_involved_count": len([i for i in incidents if i.phi_involved]),
        }


def get_incident_service() -> IncidentService:
    """Get the singleton IncidentService instance.

    Uses double-checked locking for thread-safe initialization.

    Returns:
        The singleton IncidentService instance.
    """
    global _incident_service_instance

    if _incident_service_instance is None:
        with _incident_service_lock:
            if _incident_service_instance is None:
                _incident_service_instance = IncidentService()
                logger.info("IncidentService singleton created")

    return _incident_service_instance


def reset_incident_service() -> None:
    """Reset the singleton instance. Used for testing."""
    global _incident_service_instance
    with _incident_service_lock:
        _incident_service_instance = None
