"""Corrective and Preventive Action (CAPA) Management Service.

Manages CAPA lifecycle operations including record creation, root cause
investigation, action plan development, implementation tracking, effectiveness
verification, and CAPA metrics aggregation across clinical trial sites.

Usage:
    from app.services.capa_management_service import (
        get_capa_management_service,
    )

    svc = get_capa_management_service()
    capas = svc.list_capas()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.capa_management import (
    CapaAction,
    CapaActionCreate,
    CapaActionStatus,
    CapaActionType,
    CapaActionUpdate,
    CapaCreate,
    CapaMetrics,
    CapaPriority,
    CapaRecord,
    CapaSource,
    CapaStatus,
    CapaType,
    CapaUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# Valid status transitions
VALID_TRANSITIONS: dict[CapaStatus, list[CapaStatus]] = {
    CapaStatus.OPEN: [CapaStatus.INVESTIGATION],
    CapaStatus.INVESTIGATION: [CapaStatus.ACTION_PLAN],
    CapaStatus.ACTION_PLAN: [CapaStatus.IMPLEMENTATION],
    CapaStatus.IMPLEMENTATION: [CapaStatus.VERIFICATION],
    CapaStatus.VERIFICATION: [CapaStatus.CLOSED],
    CapaStatus.CLOSED: [],
}


class CapaManagementService:
    """In-memory CAPA Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._capas: dict[str, CapaRecord] = {}
        self._actions: dict[str, CapaAction] = {}
        self._capa_counter: int = 0
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _next_capa_number(self) -> str:
        """Generate sequential CAPA number."""
        self._capa_counter += 1
        return f"CAPA-2026-{self._capa_counter:03d}"

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic CAPA data for clinical trials."""
        now = datetime.now(timezone.utc)

        # --- 8 CAPA Records ---
        capas_data = [
            {
                "id": "CAPA-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "capa_number": "CAPA-2026-001",
                "capa_type": CapaType.CORRECTIVE,
                "status": CapaStatus.CLOSED,
                "priority": CapaPriority.MAJOR,
                "source": CapaSource.AUDIT_FINDING,
                "title": "Query resolution process deficiency at SITE-103",
                "description": "Audit finding revealed that query resolution exceeds 10 business days for 15% of queries at SITE-103. Root cause identified as insufficient CRA training and lack of automated reminders.",
                "root_cause_analysis": "Insufficient CRA training on EDC query workflow. No automated escalation for queries exceeding 5 business days. Staff turnover resulted in knowledge gaps.",
                "identified_date": now - timedelta(days=90),
                "due_date": now - timedelta(days=30),
                "closed_date": now - timedelta(days=25),
                "assigned_to": "Dr. Sarah Chen",
                "department": "Clinical Operations",
                "related_deviation_ids": [],
                "related_audit_ids": ["AUD-2025-015"],
                "effectiveness_check_date": now - timedelta(days=10),
                "effectiveness_verified": True,
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "CAPA-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "capa_number": "CAPA-2026-002",
                "capa_type": CapaType.CORRECTIVE,
                "status": CapaStatus.VERIFICATION,
                "priority": CapaPriority.MAJOR,
                "source": CapaSource.DEVIATION,
                "title": "Protocol deviation documentation gaps at SITE-103",
                "description": "Three major protocol deviations in past 60 days lacked adequate documentation and timely reporting to sponsor.",
                "root_cause_analysis": "Site staff unaware of updated protocol deviation reporting timelines. Delegation log not current. No standardized deviation report template in use.",
                "identified_date": now - timedelta(days=75),
                "due_date": now - timedelta(days=15),
                "closed_date": None,
                "assigned_to": "Michael Rodriguez",
                "department": "Quality Assurance",
                "related_deviation_ids": ["DEV-2025-042", "DEV-2025-043", "DEV-2025-047"],
                "related_audit_ids": [],
                "effectiveness_check_date": now + timedelta(days=14),
                "effectiveness_verified": False,
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "CAPA-003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "capa_number": "CAPA-2026-003",
                "capa_type": CapaType.CORRECTIVE,
                "status": CapaStatus.IMPLEMENTATION,
                "priority": CapaPriority.CRITICAL,
                "source": CapaSource.AUDIT_FINDING,
                "title": "SAE reporting timeliness failure at SITE-105",
                "description": "Three SAEs not reported to sponsor within 24 hours of site awareness. Potential regulatory impact requiring immediate corrective action.",
                "root_cause_analysis": "Principal Investigator unavailable for timely SAE assessment. No backup PI designated for safety reporting. After-hours SAE reporting process not established.",
                "identified_date": now - timedelta(days=45),
                "due_date": now - timedelta(days=5),
                "closed_date": None,
                "assigned_to": "Dr. Jennifer Lee",
                "department": "Drug Safety",
                "related_deviation_ids": ["DEV-2025-058", "DEV-2025-059", "DEV-2025-061"],
                "related_audit_ids": ["AUD-2025-022"],
                "effectiveness_check_date": None,
                "effectiveness_verified": False,
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "CAPA-004",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "capa_number": "CAPA-2026-004",
                "capa_type": CapaType.CORRECTIVE,
                "status": CapaStatus.ACTION_PLAN,
                "priority": CapaPriority.CRITICAL,
                "source": CapaSource.INSPECTION,
                "title": "Systematic informed consent errors at SITE-107",
                "description": "Five subjects enrolled with incorrect consent form version. FDA inspection finding requiring comprehensive corrective action plan.",
                "root_cause_analysis": "IRB-approved consent form version not distributed to site within required timeframe. Site filing system disorganized. No version control checklist in place.",
                "identified_date": now - timedelta(days=30),
                "due_date": now + timedelta(days=15),
                "closed_date": None,
                "assigned_to": "Dr. Amanda Foster",
                "department": "Regulatory Affairs",
                "related_deviation_ids": ["DEV-2025-070", "DEV-2025-071", "DEV-2025-072", "DEV-2025-073", "DEV-2025-074"],
                "related_audit_ids": [],
                "effectiveness_check_date": None,
                "effectiveness_verified": False,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "CAPA-005",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "capa_number": "CAPA-2026-005",
                "capa_type": CapaType.CORRECTIVE,
                "status": CapaStatus.INVESTIGATION,
                "priority": CapaPriority.CRITICAL,
                "source": CapaSource.AUDIT_FINDING,
                "title": "Randomization errors at SITE-107",
                "description": "Three patients assigned to wrong treatment arm due to IWRS entry errors. Unblinding risk and potential protocol integrity compromise.",
                "root_cause_analysis": None,
                "identified_date": now - timedelta(days=20),
                "due_date": now + timedelta(days=25),
                "closed_date": None,
                "assigned_to": "Dr. Robert Kim",
                "department": "Clinical Operations",
                "related_deviation_ids": ["DEV-2025-080", "DEV-2025-081", "DEV-2025-082"],
                "related_audit_ids": ["AUD-2025-028"],
                "effectiveness_check_date": None,
                "effectiveness_verified": False,
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "CAPA-006",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "capa_number": "CAPA-2026-006",
                "capa_type": CapaType.PREVENTIVE,
                "status": CapaStatus.OPEN,
                "priority": CapaPriority.MAJOR,
                "source": CapaSource.TREND_ANALYSIS,
                "title": "Declining visit completion rate at SITE-106",
                "description": "Trend analysis shows visit completion rate declining from 85% to 68% over the past quarter. Eight missed visit windows identified. Preventive action needed to halt further deterioration.",
                "root_cause_analysis": None,
                "identified_date": now - timedelta(days=12),
                "due_date": now + timedelta(days=45),
                "closed_date": None,
                "assigned_to": "Lisa Thompson",
                "department": "Site Management",
                "related_deviation_ids": [],
                "related_audit_ids": [],
                "effectiveness_check_date": None,
                "effectiveness_verified": False,
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "CAPA-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "capa_number": "CAPA-2026-007",
                "capa_type": CapaType.PREVENTIVE,
                "status": CapaStatus.OPEN,
                "priority": CapaPriority.MINOR,
                "source": CapaSource.SELF_IDENTIFIED,
                "title": "Data entry lag improvement at SITE-104",
                "description": "Self-identified opportunity to reduce data entry lag from median 7 days to under 3 days through process optimization and dedicated data entry staff scheduling.",
                "root_cause_analysis": None,
                "identified_date": now - timedelta(days=8),
                "due_date": now + timedelta(days=60),
                "closed_date": None,
                "assigned_to": "James Wilson",
                "department": "Data Management",
                "related_deviation_ids": [],
                "related_audit_ids": [],
                "effectiveness_check_date": None,
                "effectiveness_verified": False,
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "CAPA-008",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-108",
                "capa_number": "CAPA-2026-008",
                "capa_type": CapaType.PREVENTIVE,
                "status": CapaStatus.OPEN,
                "priority": CapaPriority.MINOR,
                "source": CapaSource.COMPLAINT,
                "title": "Patient screening process clarification at SITE-108",
                "description": "Complaint from referring physician regarding unclear screening criteria communication. Preventive CAPA to standardize referral documentation and screening communication templates.",
                "root_cause_analysis": None,
                "identified_date": now - timedelta(days=5),
                "due_date": now + timedelta(days=30),
                "closed_date": None,
                "assigned_to": "Karen Davis",
                "department": "Clinical Operations",
                "related_deviation_ids": [],
                "related_audit_ids": [],
                "effectiveness_check_date": None,
                "effectiveness_verified": False,
                "created_at": now - timedelta(days=5),
            },
        ]

        self._capa_counter = 8

        for c in capas_data:
            self._capas[c["id"]] = CapaRecord(**c)

        # --- 12 CAPA Actions ---
        actions_data = [
            # Actions for CAPA-001 (closed)
            {
                "id": "ACT-001",
                "capa_id": "CAPA-001",
                "action_description": "Conduct refresher training for all CRAs on EDC query workflow",
                "action_type": CapaActionType.CORRECTIVE,
                "assigned_to": "Dr. Sarah Chen",
                "due_date": now - timedelta(days=60),
                "completed_date": now - timedelta(days=55),
                "status": CapaActionStatus.COMPLETED,
                "evidence_description": "Training completion records and competency assessment results on file",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "ACT-002",
                "capa_id": "CAPA-001",
                "action_description": "Implement automated query escalation reminders at 3 and 5 business days",
                "action_type": CapaActionType.PREVENTIVE,
                "assigned_to": "IT Support Team",
                "due_date": now - timedelta(days=45),
                "completed_date": now - timedelta(days=40),
                "status": CapaActionStatus.COMPLETED,
                "evidence_description": "EDC system configuration change log and test evidence",
                "created_at": now - timedelta(days=85),
            },
            # Actions for CAPA-002 (verification)
            {
                "id": "ACT-003",
                "capa_id": "CAPA-002",
                "action_description": "Update site delegation log and ensure all staff acknowledged",
                "action_type": CapaActionType.CORRECTIVE,
                "assigned_to": "Michael Rodriguez",
                "due_date": now - timedelta(days=40),
                "completed_date": now - timedelta(days=35),
                "status": CapaActionStatus.COMPLETED,
                "evidence_description": "Updated delegation log with all signatures collected",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "ACT-004",
                "capa_id": "CAPA-002",
                "action_description": "Develop and distribute standardized protocol deviation report template",
                "action_type": CapaActionType.PREVENTIVE,
                "assigned_to": "Quality Assurance Team",
                "due_date": now - timedelta(days=30),
                "completed_date": now - timedelta(days=28),
                "status": CapaActionStatus.COMPLETED,
                "evidence_description": "Template approved by QA and distributed to all sites",
                "created_at": now - timedelta(days=70),
            },
            # Actions for CAPA-003 (implementation)
            {
                "id": "ACT-005",
                "capa_id": "CAPA-003",
                "action_description": "Designate backup PI for safety reporting with 24/7 availability",
                "action_type": CapaActionType.CORRECTIVE,
                "assigned_to": "Dr. Jennifer Lee",
                "due_date": now - timedelta(days=20),
                "completed_date": now - timedelta(days=18),
                "status": CapaActionStatus.COMPLETED,
                "evidence_description": "Backup PI designation letter and updated delegation log",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "ACT-006",
                "capa_id": "CAPA-003",
                "action_description": "Establish after-hours SAE reporting SOP and on-call schedule",
                "action_type": CapaActionType.PREVENTIVE,
                "assigned_to": "Drug Safety Team",
                "due_date": now - timedelta(days=10),
                "completed_date": None,
                "status": CapaActionStatus.IN_PROGRESS,
                "evidence_description": None,
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "ACT-007",
                "capa_id": "CAPA-003",
                "action_description": "Retrain all site staff on SAE identification and reporting timelines",
                "action_type": CapaActionType.CORRECTIVE,
                "assigned_to": "Site Training Coordinator",
                "due_date": now + timedelta(days=5),
                "completed_date": None,
                "status": CapaActionStatus.IN_PROGRESS,
                "evidence_description": None,
                "created_at": now - timedelta(days=35),
            },
            # Actions for CAPA-004 (action_plan)
            {
                "id": "ACT-008",
                "capa_id": "CAPA-004",
                "action_description": "Re-consent all 5 affected subjects with correct consent form version",
                "action_type": CapaActionType.CONTAINMENT,
                "assigned_to": "Dr. Amanda Foster",
                "due_date": now + timedelta(days=7),
                "completed_date": None,
                "status": CapaActionStatus.PENDING,
                "evidence_description": None,
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "ACT-009",
                "capa_id": "CAPA-004",
                "action_description": "Implement consent form version control checklist and tracking system",
                "action_type": CapaActionType.PREVENTIVE,
                "assigned_to": "Regulatory Affairs Team",
                "due_date": now + timedelta(days=14),
                "completed_date": None,
                "status": CapaActionStatus.PENDING,
                "evidence_description": None,
                "created_at": now - timedelta(days=25),
            },
            # Actions for CAPA-005 (investigation)
            {
                "id": "ACT-010",
                "capa_id": "CAPA-005",
                "action_description": "Conduct root cause analysis with fishbone diagram for IWRS errors",
                "action_type": CapaActionType.CORRECTIVE,
                "assigned_to": "Dr. Robert Kim",
                "due_date": now + timedelta(days=10),
                "completed_date": None,
                "status": CapaActionStatus.IN_PROGRESS,
                "evidence_description": None,
                "created_at": now - timedelta(days=18),
            },
            # Actions for CAPA-006 (open)
            {
                "id": "ACT-011",
                "capa_id": "CAPA-006",
                "action_description": "Analyze visit scheduling data and identify barriers to completion",
                "action_type": CapaActionType.PREVENTIVE,
                "assigned_to": "Lisa Thompson",
                "due_date": now + timedelta(days=20),
                "completed_date": None,
                "status": CapaActionStatus.PENDING,
                "evidence_description": None,
                "created_at": now - timedelta(days=10),
            },
            # Actions for CAPA-007 (open)
            {
                "id": "ACT-012",
                "capa_id": "CAPA-007",
                "action_description": "Develop optimized data entry scheduling plan with dedicated time blocks",
                "action_type": CapaActionType.PREVENTIVE,
                "assigned_to": "James Wilson",
                "due_date": now + timedelta(days=30),
                "completed_date": None,
                "status": CapaActionStatus.PENDING,
                "evidence_description": None,
                "created_at": now - timedelta(days=6),
            },
        ]

        for a in actions_data:
            self._actions[a["id"]] = CapaAction(**a)

    # ------------------------------------------------------------------
    # CAPA CRUD
    # ------------------------------------------------------------------

    def list_capas(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        status: CapaStatus | None = None,
        priority: CapaPriority | None = None,
        source: CapaSource | None = None,
    ) -> list[CapaRecord]:
        """List CAPAs with optional filters."""
        with self._lock:
            result = list(self._capas.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if site_id is not None:
            result = [c for c in result if c.site_id == site_id]
        if status is not None:
            result = [c for c in result if c.status == status]
        if priority is not None:
            result = [c for c in result if c.priority == priority]
        if source is not None:
            result = [c for c in result if c.source == source]

        return sorted(result, key=lambda c: c.created_at, reverse=True)

    def get_capa(self, capa_id: str) -> CapaRecord | None:
        """Get a single CAPA by ID."""
        with self._lock:
            return self._capas.get(capa_id)

    def create_capa(self, payload: CapaCreate) -> CapaRecord:
        """Create a new CAPA record."""
        now = datetime.now(timezone.utc)
        capa_id = f"CAPA-{uuid4().hex[:8].upper()}"

        with self._lock:
            capa_number = self._next_capa_number()

        capa = CapaRecord(
            id=capa_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            capa_number=capa_number,
            capa_type=payload.capa_type,
            status=CapaStatus.OPEN,
            priority=payload.priority,
            source=payload.source,
            title=payload.title,
            description=payload.description,
            root_cause_analysis=None,
            identified_date=now,
            due_date=payload.due_date,
            closed_date=None,
            assigned_to=payload.assigned_to,
            department=payload.department,
            related_deviation_ids=payload.related_deviation_ids,
            related_audit_ids=payload.related_audit_ids,
            effectiveness_check_date=None,
            effectiveness_verified=False,
            created_at=now,
        )

        with self._lock:
            self._capas[capa_id] = capa

        logger.info("Created CAPA %s (%s): %s", capa_id, capa_number, payload.title)
        return capa

    def update_capa(self, capa_id: str, payload: CapaUpdate) -> CapaRecord | None:
        """Update an existing CAPA record."""
        with self._lock:
            existing = self._capas.get(capa_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CapaRecord(**data)
            self._capas[capa_id] = updated
        return updated

    def delete_capa(self, capa_id: str) -> bool:
        """Delete a CAPA. Returns True if deleted, False if not found."""
        with self._lock:
            if capa_id in self._capas:
                del self._capas[capa_id]
                # Also remove associated actions
                action_ids = [
                    aid for aid, a in self._actions.items() if a.capa_id == capa_id
                ]
                for aid in action_ids:
                    del self._actions[aid]
                return True
            return False

    # ------------------------------------------------------------------
    # Status Transitions
    # ------------------------------------------------------------------

    def _transition_status(
        self,
        capa_id: str,
        target_status: CapaStatus,
    ) -> CapaRecord | None:
        """Transition a CAPA to a new status with validation."""
        with self._lock:
            existing = self._capas.get(capa_id)
            if existing is None:
                return None

            allowed = VALID_TRANSITIONS.get(existing.status, [])
            if target_status not in allowed:
                raise ValueError(
                    f"Cannot transition CAPA from '{existing.status.value}' to '{target_status.value}'. "
                    f"Allowed transitions: {[s.value for s in allowed]}"
                )

            data = existing.model_dump()
            data["status"] = target_status

            if target_status == CapaStatus.CLOSED:
                data["closed_date"] = datetime.now(timezone.utc)

            updated = CapaRecord(**data)
            self._capas[capa_id] = updated

        logger.info(
            "CAPA %s transitioned from %s to %s",
            capa_id, existing.status.value, target_status.value,
        )
        return updated

    def start_investigation(self, capa_id: str) -> CapaRecord | None:
        """Transition CAPA to investigation status."""
        return self._transition_status(capa_id, CapaStatus.INVESTIGATION)

    def submit_action_plan(self, capa_id: str) -> CapaRecord | None:
        """Transition CAPA to action_plan status."""
        return self._transition_status(capa_id, CapaStatus.ACTION_PLAN)

    def begin_implementation(self, capa_id: str) -> CapaRecord | None:
        """Transition CAPA to implementation status."""
        return self._transition_status(capa_id, CapaStatus.IMPLEMENTATION)

    def verify_effectiveness(self, capa_id: str) -> CapaRecord | None:
        """Transition CAPA to verification status."""
        return self._transition_status(capa_id, CapaStatus.VERIFICATION)

    def close_capa(self, capa_id: str) -> CapaRecord | None:
        """Transition CAPA to closed status."""
        result = self._transition_status(capa_id, CapaStatus.CLOSED)
        if result is not None:
            with self._lock:
                data = result.model_dump()
                data["effectiveness_verified"] = True
                updated = CapaRecord(**data)
                self._capas[capa_id] = updated
                return updated
        return result

    # ------------------------------------------------------------------
    # CAPA Actions
    # ------------------------------------------------------------------

    def list_actions(self, capa_id: str) -> list[CapaAction]:
        """List all actions for a CAPA."""
        with self._lock:
            result = [a for a in self._actions.values() if a.capa_id == capa_id]
        return sorted(result, key=lambda a: a.created_at)

    def create_action(self, capa_id: str, payload: CapaActionCreate) -> CapaAction | None:
        """Create a new action for a CAPA. Returns None if CAPA not found."""
        now = datetime.now(timezone.utc)

        with self._lock:
            if capa_id not in self._capas:
                return None

        action_id = f"ACT-{uuid4().hex[:8].upper()}"
        action = CapaAction(
            id=action_id,
            capa_id=capa_id,
            action_description=payload.action_description,
            action_type=payload.action_type,
            assigned_to=payload.assigned_to,
            due_date=payload.due_date,
            completed_date=None,
            status=CapaActionStatus.PENDING,
            evidence_description=payload.evidence_description,
            created_at=now,
        )

        with self._lock:
            self._actions[action_id] = action

        logger.info("Created action %s for CAPA %s", action_id, capa_id)
        return action

    def update_action(self, action_id: str, payload: CapaActionUpdate) -> CapaAction | None:
        """Update a CAPA action."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._actions.get(action_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set completed_date when status changes to completed
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = CapaActionStatus(new_status)
                if (
                    new_status == CapaActionStatus.COMPLETED
                    and existing.status != CapaActionStatus.COMPLETED
                ):
                    updates["completed_date"] = now

            data.update(updates)
            updated = CapaAction(**data)
            self._actions[action_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> CapaMetrics:
        """Compute aggregated CAPA metrics."""
        now = datetime.now(timezone.utc)

        with self._lock:
            capas = list(self._capas.values())
            actions = list(self._actions.values())

        total = len(capas)
        closed = sum(1 for c in capas if c.status == CapaStatus.CLOSED)
        open_capas = total - closed
        overdue = sum(
            1 for c in capas
            if c.status != CapaStatus.CLOSED and c.due_date < now
        )

        # By status
        by_status: dict[str, int] = {}
        for c in capas:
            key = c.status.value
            by_status[key] = by_status.get(key, 0) + 1

        # By priority
        by_priority: dict[str, int] = {}
        for c in capas:
            key = c.priority.value
            by_priority[key] = by_priority.get(key, 0) + 1

        # By source
        by_source: dict[str, int] = {}
        for c in capas:
            key = c.source.value
            by_source[key] = by_source.get(key, 0) + 1

        # Average days to close
        closed_capas = [c for c in capas if c.status == CapaStatus.CLOSED and c.closed_date]
        if closed_capas:
            total_days = sum(
                (c.closed_date - c.identified_date).days for c in closed_capas
            )
            avg_days = round(total_days / len(closed_capas), 1)
        else:
            avg_days = 0.0

        # Effectiveness verified
        verified = sum(1 for c in capas if c.effectiveness_verified)

        # Actions
        total_actions = len(actions)
        completed_actions = sum(
            1 for a in actions if a.status == CapaActionStatus.COMPLETED
        )

        return CapaMetrics(
            total_capas=total,
            open_capas=open_capas,
            closed_capas=closed,
            overdue_capas=overdue,
            capas_by_status=by_status,
            capas_by_priority=by_priority,
            capas_by_source=by_source,
            avg_days_to_close=avg_days,
            effectiveness_verified_count=verified,
            total_actions=total_actions,
            completed_actions=completed_actions,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: CapaManagementService | None = None
_lock = threading.Lock()


def get_capa_management_service() -> CapaManagementService:
    """Return the singleton CapaManagementService instance."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = CapaManagementService()
    return _instance


def reset_capa_management_service() -> CapaManagementService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _lock:
        _instance = CapaManagementService()
    return _instance
