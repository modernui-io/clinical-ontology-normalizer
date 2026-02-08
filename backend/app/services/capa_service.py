"""Corrective and Preventive Action (CAPA) tracking service.

VP-Quality-2: Provides lifecycle management for CAPAs including:
- CAPA creation, update, and state machine transitions
- Root cause analysis categorization
- Effectiveness verification (90-day recurrence tracking)
- Metrics and dashboard data
- Pre-populated example CAPAs for demonstration

Usage:
    from app.services.capa_service import get_capa_service

    service = get_capa_service()
    capa = service.create_capa(
        title="NLP false negative for diabetes",
        description="Rule-based NLP misses 'DM2' abbreviation",
        capa_type=CAPAType.CORRECTIVE,
        source=CAPASource.AUDIT,
        severity=CAPASeverity.MAJOR,
    )
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas.quality_management import (
    CAPAMetrics,
    CAPASeverity,
    CAPASource,
    CAPAStatus,
    CAPAType,
    RootCauseCategory,
)

logger = logging.getLogger(__name__)

# Singleton instance and lock
_capa_service_instance: CAPAService | None = None
_capa_service_lock = Lock()


# ---------------------------------------------------------------------------
# Valid CAPA state transitions
# ---------------------------------------------------------------------------

VALID_CAPA_TRANSITIONS: dict[CAPAStatus, list[CAPAStatus]] = {
    CAPAStatus.OPEN: [CAPAStatus.INVESTIGATING, CAPAStatus.CLOSED],
    CAPAStatus.INVESTIGATING: [CAPAStatus.ACTION_PLANNED, CAPAStatus.OPEN, CAPAStatus.CLOSED],
    CAPAStatus.ACTION_PLANNED: [CAPAStatus.IN_PROGRESS, CAPAStatus.INVESTIGATING, CAPAStatus.CLOSED],
    CAPAStatus.IN_PROGRESS: [CAPAStatus.VERIFICATION, CAPAStatus.ACTION_PLANNED, CAPAStatus.CLOSED],
    CAPAStatus.VERIFICATION: [CAPAStatus.CLOSED, CAPAStatus.IN_PROGRESS],
    CAPAStatus.CLOSED: [],  # Terminal state
}

# Effectiveness verification window (days)
EFFECTIVENESS_WINDOW_DAYS = 90


# ---------------------------------------------------------------------------
# CAPA record model
# ---------------------------------------------------------------------------


class CAPARecord(BaseModel):
    """Internal CAPA record."""

    id: str = Field(default_factory=lambda: f"CAPA-{uuid4().hex[:8].upper()}")
    title: str
    description: str
    capa_type: CAPAType
    source: CAPASource
    severity: CAPASeverity
    status: CAPAStatus = CAPAStatus.OPEN
    root_cause_category: RootCauseCategory | None = None
    root_cause: str | None = None
    corrective_action: str | None = None
    preventive_action: str | None = None
    assigned_to: str | None = None
    due_date: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: datetime | None = None
    effectiveness_check_date: datetime | None = None
    recurrence_count: int = 0


# ---------------------------------------------------------------------------
# CAPAService
# ---------------------------------------------------------------------------


class CAPAService:
    """Service for managing Corrective and Preventive Actions.

    Uses in-memory storage with thread-safe access.
    Production deployments should persist to the database.
    """

    def __init__(self) -> None:
        """Initialize the CAPA service with empty storage."""
        self._capas: dict[str, CAPARecord] = {}
        self._lock = Lock()
        self._seed_examples()
        logger.info("CAPAService initialized with %d example CAPAs", len(self._capas))

    def _seed_examples(self) -> None:
        """Pre-populate example CAPAs for demonstration."""
        now = datetime.now(timezone.utc)

        examples = [
            CAPARecord(
                id="CAPA-001",
                title="NLP false negative for diabetes condition",
                description=(
                    "Rule-based NLP pipeline fails to extract 'DM2' and 'DMII' "
                    "abbreviations as type 2 diabetes mellitus. This leads to missed "
                    "inclusion criteria matches for diabetes trials."
                ),
                capa_type=CAPAType.CORRECTIVE,
                source=CAPASource.AUDIT,
                severity=CAPASeverity.MAJOR,
                status=CAPAStatus.IN_PROGRESS,
                root_cause_category=RootCauseCategory.TECHNOLOGY,
                root_cause="NLP lexicon missing common clinical abbreviations for diabetes",
                corrective_action="Add DM2, DMII, DM-II to diabetes synonym list in NLP lexicon",
                preventive_action="Implement abbreviation expansion module and periodic lexicon review process",
                assigned_to="nlp-team-lead",
                due_date=now + timedelta(days=14),
                created_at=now - timedelta(days=10),
                updated_at=now - timedelta(days=2),
            ),
            CAPARecord(
                id="CAPA-002",
                title="Missing audit log entries for screening overrides",
                description=(
                    "When a clinician overrides an automated screening decision, "
                    "the audit log does not capture the override reason or the "
                    "original automated decision. This creates a compliance gap "
                    "for 21 CFR Part 11 requirements."
                ),
                capa_type=CAPAType.CORRECTIVE,
                source=CAPASource.AUDIT,
                severity=CAPASeverity.CRITICAL,
                status=CAPAStatus.ACTION_PLANNED,
                root_cause_category=RootCauseCategory.PROCESS,
                root_cause="Override endpoint bypasses AuditMiddleware due to incorrect route configuration",
                corrective_action="Fix route registration to ensure override endpoint passes through AuditMiddleware",
                preventive_action="Add integration test that verifies audit entries for all screening state changes",
                assigned_to="compliance-engineer",
                due_date=now + timedelta(days=7),
                created_at=now - timedelta(days=5),
                updated_at=now - timedelta(days=1),
            ),
            CAPARecord(
                id="CAPA-003",
                title="Inconsistent OMOP mapping for medication routes",
                description=(
                    "Medication route of administration (e.g., 'oral', 'IV', 'topical') "
                    "maps to different OMOP concept_ids depending on whether the input "
                    "comes from FHIR import vs. NLP extraction. This causes duplicate "
                    "ClinicalFacts with different concept_ids for the same medication."
                ),
                capa_type=CAPAType.PREVENTIVE,
                source=CAPASource.DEVIATION,
                severity=CAPASeverity.MAJOR,
                status=CAPAStatus.INVESTIGATING,
                root_cause_category=RootCauseCategory.DESIGN,
                root_cause="Two separate mapping codepaths with different synonym tables for route normalization",
                corrective_action=None,
                preventive_action="Consolidate route mapping to single canonical service with unified synonym table",
                assigned_to="data-engineering-lead",
                due_date=now + timedelta(days=21),
                created_at=now - timedelta(days=3),
                updated_at=now - timedelta(days=1),
            ),
        ]

        for capa in examples:
            self._capas[capa.id] = capa

    def create_capa(
        self,
        title: str,
        description: str,
        capa_type: CAPAType,
        source: CAPASource,
        severity: CAPASeverity,
        root_cause_category: RootCauseCategory | None = None,
        root_cause: str | None = None,
        corrective_action: str | None = None,
        preventive_action: str | None = None,
        assigned_to: str | None = None,
        due_date: datetime | None = None,
    ) -> CAPARecord:
        """Create a new CAPA record.

        Args:
            title: Brief CAPA title.
            description: Detailed description of the issue.
            capa_type: Corrective or Preventive.
            source: Source that triggered the CAPA.
            severity: Severity classification.
            root_cause_category: Optional root cause category.
            root_cause: Optional root cause description.
            corrective_action: Optional corrective action.
            preventive_action: Optional preventive action.
            assigned_to: Optional assignee.
            due_date: Optional target resolution date.

        Returns:
            The created CAPARecord.
        """
        capa = CAPARecord(
            title=title,
            description=description,
            capa_type=capa_type,
            source=source,
            severity=severity,
            root_cause_category=root_cause_category,
            root_cause=root_cause,
            corrective_action=corrective_action,
            preventive_action=preventive_action,
            assigned_to=assigned_to,
            due_date=due_date,
        )

        with self._lock:
            self._capas[capa.id] = capa

        logger.info(
            "CAPA created: id=%s, type=%s, severity=%s",
            capa.id,
            capa_type.value,
            severity.value,
        )
        return capa

    def get_capa(self, capa_id: str) -> CAPARecord | None:
        """Retrieve a CAPA by ID.

        Args:
            capa_id: The unique CAPA identifier.

        Returns:
            The CAPARecord if found, otherwise None.
        """
        with self._lock:
            return self._capas.get(capa_id)

    def update_capa(
        self,
        capa_id: str,
        title: str | None = None,
        description: str | None = None,
        status: CAPAStatus | None = None,
        severity: CAPASeverity | None = None,
        root_cause_category: RootCauseCategory | None = None,
        root_cause: str | None = None,
        corrective_action: str | None = None,
        preventive_action: str | None = None,
        assigned_to: str | None = None,
        due_date: datetime | None = None,
        effectiveness_check_date: datetime | None = None,
    ) -> CAPARecord:
        """Update an existing CAPA.

        Args:
            capa_id: The unique CAPA identifier.
            title: Updated title.
            description: Updated description.
            status: New status (must be a valid transition).
            severity: Updated severity.
            root_cause_category: Updated root cause category.
            root_cause: Updated root cause.
            corrective_action: Updated corrective action.
            preventive_action: Updated preventive action.
            assigned_to: Updated assignee.
            due_date: Updated due date.
            effectiveness_check_date: Date to verify effectiveness.

        Returns:
            The updated CAPARecord.

        Raises:
            ValueError: If CAPA not found or invalid state transition.
        """
        with self._lock:
            capa = self._capas.get(capa_id)
            if capa is None:
                raise ValueError(f"CAPA not found: {capa_id}")

            now = datetime.now(timezone.utc)

            # Handle status transition
            if status is not None and status != capa.status:
                valid_next = VALID_CAPA_TRANSITIONS.get(capa.status, [])
                if status not in valid_next:
                    raise ValueError(
                        f"Invalid CAPA status transition: {capa.status.value} -> {status.value}. "
                        f"Valid transitions: {[s.value for s in valid_next]}"
                    )
                capa.status = status

                # Set closed_at timestamp
                if status == CAPAStatus.CLOSED:
                    capa.closed_at = now
                    # Set default effectiveness check date if not provided
                    if capa.effectiveness_check_date is None and effectiveness_check_date is None:
                        capa.effectiveness_check_date = now + timedelta(days=EFFECTIVENESS_WINDOW_DAYS)

            # Update fields
            if title is not None:
                capa.title = title
            if description is not None:
                capa.description = description
            if severity is not None:
                capa.severity = severity
            if root_cause_category is not None:
                capa.root_cause_category = root_cause_category
            if root_cause is not None:
                capa.root_cause = root_cause
            if corrective_action is not None:
                capa.corrective_action = corrective_action
            if preventive_action is not None:
                capa.preventive_action = preventive_action
            if assigned_to is not None:
                capa.assigned_to = assigned_to
            if due_date is not None:
                capa.due_date = due_date
            if effectiveness_check_date is not None:
                capa.effectiveness_check_date = effectiveness_check_date

            capa.updated_at = now

        logger.info("CAPA updated: id=%s, status=%s", capa_id, capa.status.value)
        return capa

    def list_capas(
        self,
        status: CAPAStatus | None = None,
        severity: CAPASeverity | None = None,
        capa_type: CAPAType | None = None,
        source: CAPASource | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[CAPARecord], int]:
        """List CAPAs with optional filters.

        Args:
            status: Filter by status.
            severity: Filter by severity.
            capa_type: Filter by type.
            source: Filter by source.
            limit: Max results to return.
            offset: Pagination offset.

        Returns:
            Tuple of (filtered CAPAs, total count).
        """
        with self._lock:
            capas = list(self._capas.values())

        # Apply filters
        if status is not None:
            capas = [c for c in capas if c.status == status]
        if severity is not None:
            capas = [c for c in capas if c.severity == severity]
        if capa_type is not None:
            capas = [c for c in capas if c.capa_type == capa_type]
        if source is not None:
            capas = [c for c in capas if c.source == source]

        # Sort by created_at descending
        capas.sort(key=lambda c: c.created_at, reverse=True)

        total = len(capas)
        paginated = capas[offset : offset + limit]

        return paginated, total

    def record_recurrence(self, capa_id: str) -> CAPARecord:
        """Record a recurrence of the issue tracked by a closed CAPA.

        This increments the recurrence counter for effectiveness tracking.

        Args:
            capa_id: The CAPA to record recurrence for.

        Returns:
            The updated CAPARecord.

        Raises:
            ValueError: If CAPA not found or not closed.
        """
        with self._lock:
            capa = self._capas.get(capa_id)
            if capa is None:
                raise ValueError(f"CAPA not found: {capa_id}")
            if capa.status != CAPAStatus.CLOSED:
                raise ValueError(f"Recurrence can only be recorded for CLOSED CAPAs (current: {capa.status.value})")

            capa.recurrence_count += 1
            capa.updated_at = datetime.now(timezone.utc)

        logger.warning(
            "CAPA recurrence recorded: id=%s, count=%d",
            capa_id,
            capa.recurrence_count,
        )
        return capa

    def get_overdue_capas(self) -> list[CAPARecord]:
        """Get all open CAPAs that are past their due date.

        Returns:
            List of overdue CAPARecords.
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            return [
                c
                for c in self._capas.values()
                if c.status != CAPAStatus.CLOSED
                and c.due_date is not None
                and c.due_date < now
            ]

    def get_metrics(self) -> CAPAMetrics:
        """Calculate CAPA dashboard metrics.

        Returns:
            CAPAMetrics with aggregated statistics.
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            all_capas = list(self._capas.values())

        total = len(all_capas)
        open_capas = [c for c in all_capas if c.status != CAPAStatus.CLOSED]
        closed_capas = [c for c in all_capas if c.status == CAPAStatus.CLOSED]

        # Count by severity
        by_severity: dict[str, int] = {}
        for s in CAPASeverity:
            count = sum(1 for c in all_capas if c.severity == s)
            if count > 0:
                by_severity[s.value] = count

        # Count by status
        by_status: dict[str, int] = {}
        for s in CAPAStatus:
            count = sum(1 for c in all_capas if c.status == s)
            if count > 0:
                by_status[s.value] = count

        # Count by type
        by_type: dict[str, int] = {}
        for t in CAPAType:
            count = sum(1 for c in all_capas if c.capa_type == t)
            if count > 0:
                by_type[t.value] = count

        # Overdue count
        overdue_count = sum(
            1
            for c in open_capas
            if c.due_date is not None and c.due_date < now
        )

        # Average days to close
        avg_days_to_close = 0.0
        if closed_capas:
            total_days = sum(
                (c.closed_at - c.created_at).total_seconds() / 86400
                for c in closed_capas
                if c.closed_at is not None
            )
            avg_days_to_close = total_days / len(closed_capas)

        # Recurrence rate
        recurrence_rate = 0.0
        if closed_capas:
            recurred = sum(1 for c in closed_capas if c.recurrence_count > 0)
            recurrence_rate = (recurred / len(closed_capas)) * 100

        return CAPAMetrics(
            total_capas=total,
            open_capas=len(open_capas),
            by_severity=by_severity,
            by_status=by_status,
            by_type=by_type,
            overdue_count=overdue_count,
            avg_days_to_close=round(avg_days_to_close, 1),
            recurrence_rate=round(recurrence_rate, 1),
        )


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------


def get_capa_service() -> CAPAService:
    """Get or create the singleton CAPAService instance."""
    global _capa_service_instance
    if _capa_service_instance is None:
        with _capa_service_lock:
            if _capa_service_instance is None:
                _capa_service_instance = CAPAService()
    return _capa_service_instance


def reset_capa_service() -> None:
    """Reset the singleton for testing."""
    global _capa_service_instance
    with _capa_service_lock:
        _capa_service_instance = None
