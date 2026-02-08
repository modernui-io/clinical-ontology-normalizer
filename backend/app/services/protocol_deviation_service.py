"""Protocol Deviation Tracking Service (CMO-7).

Manages protocol deviations across clinical trial sites with severity
classification, notification tracking, CAPA linkage, and compliance
metrics.

Usage:
    from app.services.protocol_deviation_service import (
        get_protocol_deviation_service,
    )

    svc = get_protocol_deviation_service()
    deviation = svc.create_deviation(...)
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.protocol_deviation import (
    DeviationCreate,
    DeviationMetrics,
    DeviationRecord,
    DeviationSeverity,
    DeviationStatus,
    DeviationTrend,
    DeviationType,
    DeviationUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SLA constants (business days)
# ---------------------------------------------------------------------------

IRB_NOTIFICATION_SLA_DAYS = 5  # 5 business days for MAJOR/CRITICAL
SPONSOR_NOTIFICATION_SLA_HOURS = 24  # 24 hours for CRITICAL

# ---------------------------------------------------------------------------
# Valid status transitions
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[DeviationStatus, set[DeviationStatus]] = {
    DeviationStatus.REPORTED: {
        DeviationStatus.UNDER_REVIEW,
        DeviationStatus.CLOSED,
    },
    DeviationStatus.UNDER_REVIEW: {
        DeviationStatus.CONFIRMED,
        DeviationStatus.CLOSED,
    },
    DeviationStatus.CONFIRMED: {
        DeviationStatus.CAPA_REQUIRED,
        DeviationStatus.RESOLVED,
        DeviationStatus.CLOSED,
    },
    DeviationStatus.CAPA_REQUIRED: {
        DeviationStatus.CAPA_IN_PROGRESS,
        DeviationStatus.CLOSED,
    },
    DeviationStatus.CAPA_IN_PROGRESS: {
        DeviationStatus.RESOLVED,
        DeviationStatus.CLOSED,
    },
    DeviationStatus.RESOLVED: {
        DeviationStatus.CLOSED,
    },
    DeviationStatus.CLOSED: set(),  # terminal state
}


class ProtocolDeviationService:
    """In-memory protocol deviation management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._deviations: dict[str, DeviationRecord] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic deviations across the 3 Regeneron trials."""
        now = datetime.now(timezone.utc)

        # Stable trial IDs matching trial_eligibility_service
        eylea_id = "00000000-de00-0001-0000-000000000001"
        dupixent_id = "00000000-de00-0002-0000-000000000002"
        libtayo_id = "00000000-de00-0003-0000-000000000003"

        seed_deviations: list[dict] = [
            {
                "trial_id": eylea_id,
                "patient_id": "PAT-DME-003",
                "site_id": "SITE-101",
                "deviation_type": DeviationType.VISIT_WINDOW,
                "severity": DeviationSeverity.MINOR,
                "status": DeviationStatus.RESOLVED,
                "title": "Missed visit window - Week 12 follow-up",
                "description": (
                    "Patient PAT-DME-003 missed the Week 12 follow-up visit "
                    "window by 4 days due to a scheduling conflict. Visit was "
                    "completed outside the protocol-defined window."
                ),
                "date_occurred": now - timedelta(days=45),
                "reported_by": "Dr. Sarah Chen",
                "reviewer": "Dr. Michael Torres",
                "root_cause": "Patient scheduling conflict",
                "resolution_notes": "Visit completed. Data collected per protocol amendment allowance.",
                "irb_notification_required": False,
                "sponsor_notification_required": False,
            },
            {
                "trial_id": dupixent_id,
                "patient_id": "PAT-AD-007",
                "site_id": "SITE-205",
                "deviation_type": DeviationType.PROHIBITED_MEDICATION,
                "severity": DeviationSeverity.MODERATE,
                "status": DeviationStatus.CAPA_IN_PROGRESS,
                "title": "Prohibited concomitant medication use - oral corticosteroid",
                "description": (
                    "Patient PAT-AD-007 was prescribed a 5-day course of oral "
                    "prednisone by their PCP for an acute asthma exacerbation "
                    "without notifying the study team. This is a prohibited "
                    "concomitant medication per protocol section 6.2."
                ),
                "date_occurred": now - timedelta(days=30),
                "reported_by": "Nurse Coordinator Lisa Park",
                "reviewer": "Dr. James Liu",
                "root_cause": "Patient did not inform PCP of trial participation",
                "capa_id": "CAPA-2024-015",
                "irb_notification_required": False,
                "sponsor_notification_required": False,
            },
            {
                "trial_id": libtayo_id,
                "patient_id": "PAT-CSCC-012",
                "site_id": "SITE-310",
                "deviation_type": DeviationType.INFORMED_CONSENT,
                "severity": DeviationSeverity.MAJOR,
                "status": DeviationStatus.CONFIRMED,
                "title": "Informed consent version discrepancy",
                "description": (
                    "Patient PAT-CSCC-012 was consented using ICF version 3.0 "
                    "instead of the current IRB-approved version 4.1. The site "
                    "had not updated their consent forms after the most recent "
                    "protocol amendment. Patient was re-consented on the correct "
                    "version upon discovery."
                ),
                "date_occurred": now - timedelta(days=20),
                "reported_by": "CRA Jennifer Walsh",
                "reviewer": "Dr. Robert Kim",
                "irb_notification_required": True,
                "sponsor_notification_required": True,
                "irb_notified_date": now - timedelta(days=17),
                "sponsor_notified_date": now - timedelta(days=19),
            },
            {
                "trial_id": eylea_id,
                "patient_id": "PAT-DME-019",
                "site_id": "SITE-102",
                "deviation_type": DeviationType.INCLUSION_CRITERIA,
                "severity": DeviationSeverity.MODERATE,
                "status": DeviationStatus.UNDER_REVIEW,
                "title": "Inclusion criteria deviation - HbA1c measured outside window",
                "description": (
                    "Patient PAT-DME-019 HbA1c value used for eligibility was "
                    "from a lab drawn 45 days before screening, exceeding the "
                    "protocol-specified 30-day window. The value was 8.2%, "
                    "within the eligibility range."
                ),
                "date_occurred": now - timedelta(days=15),
                "reported_by": "Study Coordinator Maria Santos",
                "irb_notification_required": False,
                "sponsor_notification_required": False,
            },
            {
                "trial_id": dupixent_id,
                "patient_id": "PAT-AD-021",
                "site_id": "SITE-207",
                "deviation_type": DeviationType.SAFETY_REPORTING,
                "severity": DeviationSeverity.MAJOR,
                "status": DeviationStatus.CAPA_REQUIRED,
                "title": "Late adverse event reporting - SAE reported 5 days late",
                "description": (
                    "A serious adverse event (anaphylactic reaction) was reported "
                    "to the sponsor 5 business days after the site became aware, "
                    "exceeding the 24-hour reporting requirement. The event "
                    "occurred during the dupilumab injection at the Week 8 visit."
                ),
                "date_occurred": now - timedelta(days=10),
                "reported_by": "Dr. Angela Martinez",
                "irb_notification_required": True,
                "sponsor_notification_required": True,
                "sponsor_notified_date": now - timedelta(days=5),
            },
            {
                "trial_id": libtayo_id,
                "patient_id": "PAT-CSCC-005",
                "site_id": "SITE-312",
                "deviation_type": DeviationType.RANDOMIZATION_ERROR,
                "severity": DeviationSeverity.CRITICAL,
                "status": DeviationStatus.CAPA_IN_PROGRESS,
                "title": "Randomization error - wrong treatment arm assignment",
                "description": (
                    "Patient PAT-CSCC-005 was assigned to the wrong treatment "
                    "arm due to an error in the IVRS system entry. The site "
                    "entered the wrong stratification factor (ECOG 0 instead "
                    "of ECOG 1), resulting in incorrect randomization. Patient "
                    "received one dose before the error was discovered."
                ),
                "date_occurred": now - timedelta(days=8),
                "reported_by": "Pharmacist David Lee",
                "reviewer": "Dr. Robert Kim",
                "root_cause": "Data entry error in IVRS stratification",
                "capa_id": "CAPA-2024-022",
                "irb_notification_required": True,
                "sponsor_notification_required": True,
                "irb_notified_date": now - timedelta(days=6),
                "sponsor_notified_date": now - timedelta(days=7),
            },
            {
                "trial_id": eylea_id,
                "patient_id": None,
                "site_id": "SITE-103",
                "deviation_type": DeviationType.DATA_COLLECTION,
                "severity": DeviationSeverity.MINOR,
                "status": DeviationStatus.REPORTED,
                "title": "Data collection form incomplete - BCVA assessment",
                "description": (
                    "The Week 8 BCVA assessment form for three patients at "
                    "SITE-103 was incomplete. The refraction measurements "
                    "were not recorded per the protocol-specified procedure. "
                    "Data was subsequently obtained from the source documents."
                ),
                "date_occurred": now - timedelta(days=5),
                "reported_by": "CRA Tom Johnson",
                "irb_notification_required": False,
                "sponsor_notification_required": False,
            },
            {
                "trial_id": dupixent_id,
                "patient_id": "PAT-AD-015",
                "site_id": "SITE-206",
                "deviation_type": DeviationType.DOSING_ERROR,
                "severity": DeviationSeverity.MODERATE,
                "status": DeviationStatus.CONFIRMED,
                "title": "Dosing schedule deviation - injection administered early",
                "description": (
                    "Patient PAT-AD-015 received the Week 4 dupilumab injection "
                    "3 days ahead of schedule due to a planned vacation. The "
                    "protocol specifies a +/- 2 day window for dosing visits."
                ),
                "date_occurred": now - timedelta(days=3),
                "reported_by": "Nurse Coordinator Lisa Park",
                "irb_notification_required": False,
                "sponsor_notification_required": False,
            },
        ]

        for i, data in enumerate(seed_deviations):
            dev_id = f"DEV-{i + 1:04d}"
            date_reported = data["date_occurred"] + timedelta(hours=4)
            record = DeviationRecord(
                id=dev_id,
                trial_id=data["trial_id"],
                patient_id=data.get("patient_id"),
                site_id=data["site_id"],
                deviation_type=data["deviation_type"],
                severity=data["severity"],
                status=data["status"],
                title=data["title"],
                description=data["description"],
                date_occurred=data["date_occurred"],
                date_reported=date_reported,
                reported_by=data["reported_by"],
                reviewer=data.get("reviewer"),
                root_cause=data.get("root_cause"),
                impact_assessment=data.get("impact_assessment"),
                capa_id=data.get("capa_id"),
                irb_notification_required=data.get("irb_notification_required", False),
                sponsor_notification_required=data.get("sponsor_notification_required", False),
                irb_notified_date=data.get("irb_notified_date"),
                sponsor_notified_date=data.get("sponsor_notified_date"),
                resolution_notes=data.get("resolution_notes"),
                created_at=date_reported,
                updated_at=date_reported,
                closed_at=None,
            )
            self._deviations[dev_id] = record

        logger.info(
            "Protocol deviation service initialised with %d demo deviations",
            len(self._deviations),
        )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_deviation(self, data: DeviationCreate) -> DeviationRecord:
        """Create a new protocol deviation record.

        Automatically sets notification requirements based on severity:
        - MAJOR: IRB notification required
        - CRITICAL: IRB + sponsor notification required
        """
        now = datetime.now(timezone.utc)
        dev_id = f"DEV-{uuid4().hex[:8].upper()}"

        irb_required = data.severity in (
            DeviationSeverity.MAJOR,
            DeviationSeverity.CRITICAL,
        )
        sponsor_required = data.severity == DeviationSeverity.CRITICAL

        record = DeviationRecord(
            id=dev_id,
            trial_id=data.trial_id,
            patient_id=data.patient_id,
            site_id=data.site_id,
            deviation_type=data.deviation_type,
            severity=data.severity,
            status=DeviationStatus.REPORTED,
            title=data.title,
            description=data.description,
            date_occurred=data.date_occurred,
            date_reported=now,
            reported_by=data.reported_by,
            reviewer=None,
            root_cause=None,
            impact_assessment=None,
            capa_id=None,
            irb_notification_required=irb_required,
            sponsor_notification_required=sponsor_required,
            irb_notified_date=None,
            sponsor_notified_date=None,
            resolution_notes=None,
            created_at=now,
            updated_at=now,
            closed_at=None,
        )

        with self._lock:
            self._deviations[dev_id] = record

        logger.info(
            "Created deviation %s [%s/%s] for trial %s",
            dev_id,
            data.deviation_type.value,
            data.severity.value,
            data.trial_id,
        )
        return record

    def update_deviation(
        self, deviation_id: str, data: DeviationUpdate
    ) -> DeviationRecord:
        """Update deviation fields with status transition validation.

        Raises ``KeyError`` if the deviation does not exist.
        Raises ``ValueError`` for invalid status transitions.
        """
        with self._lock:
            record = self._deviations.get(deviation_id)
            if record is None:
                raise KeyError(f"Deviation {deviation_id} not found")

            # Validate status transition
            if data.status is not None and data.status != record.status:
                allowed = VALID_TRANSITIONS.get(record.status, set())
                if data.status not in allowed:
                    raise ValueError(
                        f"Invalid status transition from {record.status.value} "
                        f"to {data.status.value}. Allowed: "
                        f"{[s.value for s in allowed]}"
                    )

            now = datetime.now(timezone.utc)
            updates: dict = {}

            if data.status is not None:
                updates["status"] = data.status
                if data.status == DeviationStatus.CLOSED:
                    updates["closed_at"] = now
            if data.severity is not None:
                updates["severity"] = data.severity
                # Re-evaluate notification requirements on severity change
                updates["irb_notification_required"] = data.severity in (
                    DeviationSeverity.MAJOR,
                    DeviationSeverity.CRITICAL,
                )
                updates["sponsor_notification_required"] = (
                    data.severity == DeviationSeverity.CRITICAL
                )
            if data.reviewer is not None:
                updates["reviewer"] = data.reviewer
            if data.root_cause is not None:
                updates["root_cause"] = data.root_cause
            if data.resolution_notes is not None:
                updates["resolution_notes"] = data.resolution_notes

            updates["updated_at"] = now

            updated = record.model_copy(update=updates)
            self._deviations[deviation_id] = updated

        return updated

    def get_deviation(self, deviation_id: str) -> DeviationRecord:
        """Retrieve a single deviation by ID.

        Raises ``KeyError`` if not found.
        """
        record = self._deviations.get(deviation_id)
        if record is None:
            raise KeyError(f"Deviation {deviation_id} not found")
        return record

    def list_deviations(
        self,
        *,
        trial_id: str | None = None,
        severity: DeviationSeverity | None = None,
        status: DeviationStatus | None = None,
        deviation_type: DeviationType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[DeviationRecord], int]:
        """List deviations with optional filtering and pagination.

        Returns a tuple of ``(items, total_matching)``.
        """
        records = list(self._deviations.values())

        if trial_id is not None:
            records = [r for r in records if r.trial_id == trial_id]
        if severity is not None:
            records = [r for r in records if r.severity == severity]
        if status is not None:
            records = [r for r in records if r.status == status]
        if deviation_type is not None:
            records = [r for r in records if r.deviation_type == deviation_type]

        # Sort by date_reported descending (most recent first)
        records.sort(key=lambda r: r.date_reported, reverse=True)

        total = len(records)
        page = records[offset : offset + limit]
        return page, total

    # ------------------------------------------------------------------
    # CAPA linkage
    # ------------------------------------------------------------------

    def link_capa(self, deviation_id: str, capa_id: str) -> DeviationRecord:
        """Link a deviation to a CAPA record.

        Raises ``KeyError`` if deviation not found.
        """
        with self._lock:
            record = self._deviations.get(deviation_id)
            if record is None:
                raise KeyError(f"Deviation {deviation_id} not found")

            now = datetime.now(timezone.utc)
            updated = record.model_copy(
                update={"capa_id": capa_id, "updated_at": now}
            )
            self._deviations[deviation_id] = updated

        logger.info("Linked deviation %s to CAPA %s", deviation_id, capa_id)
        return updated

    # ------------------------------------------------------------------
    # Notification tracking
    # ------------------------------------------------------------------

    def record_irb_notification(
        self, deviation_id: str, notified_date: datetime
    ) -> DeviationRecord:
        """Record that IRB notification was sent.

        Raises ``KeyError`` if deviation not found.
        """
        with self._lock:
            record = self._deviations.get(deviation_id)
            if record is None:
                raise KeyError(f"Deviation {deviation_id} not found")

            now = datetime.now(timezone.utc)
            updated = record.model_copy(
                update={"irb_notified_date": notified_date, "updated_at": now}
            )
            self._deviations[deviation_id] = updated

        return updated

    def record_sponsor_notification(
        self, deviation_id: str, notified_date: datetime
    ) -> DeviationRecord:
        """Record that sponsor notification was sent.

        Raises ``KeyError`` if deviation not found.
        """
        with self._lock:
            record = self._deviations.get(deviation_id)
            if record is None:
                raise KeyError(f"Deviation {deviation_id} not found")

            now = datetime.now(timezone.utc)
            updated = record.model_copy(
                update={"sponsor_notified_date": notified_date, "updated_at": now}
            )
            self._deviations[deviation_id] = updated

        return updated

    # ------------------------------------------------------------------
    # Impact assessment
    # ------------------------------------------------------------------

    def assess_impact(
        self, deviation_id: str, impact_text: str
    ) -> DeviationRecord:
        """Record an impact assessment on a deviation.

        Raises ``KeyError`` if deviation not found.
        """
        with self._lock:
            record = self._deviations.get(deviation_id)
            if record is None:
                raise KeyError(f"Deviation {deviation_id} not found")

            now = datetime.now(timezone.utc)
            updated = record.model_copy(
                update={"impact_assessment": impact_text, "updated_at": now}
            )
            self._deviations[deviation_id] = updated

        return updated

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> DeviationMetrics:
        """Compute aggregated deviation metrics, optionally filtered by trial."""
        records = list(self._deviations.values())
        if trial_id is not None:
            records = [r for r in records if r.trial_id == trial_id]

        if not records:
            return DeviationMetrics(
                total_deviations=0,
                by_type={},
                by_severity={},
                by_status={},
                by_trial={},
                mean_time_to_resolution_days=None,
                capa_linkage_rate=0.0,
                irb_notification_compliance_rate=0.0,
                sponsor_notification_compliance_rate=0.0,
                trends=[],
            )

        by_type = Counter(r.deviation_type.value for r in records)
        by_severity = Counter(r.severity.value for r in records)
        by_status = Counter(r.status.value for r in records)
        by_trial = Counter(r.trial_id for r in records)

        # Mean time to resolution (only for resolved/closed deviations)
        resolved = [
            r
            for r in records
            if r.status in (DeviationStatus.RESOLVED, DeviationStatus.CLOSED)
        ]
        if resolved:
            resolution_days = []
            for r in resolved:
                end = r.closed_at or r.updated_at
                delta = (end - r.date_reported).total_seconds() / 86400
                resolution_days.append(delta)
            mtr = sum(resolution_days) / len(resolution_days)
        else:
            mtr = None

        # CAPA linkage rate
        capa_linked = sum(1 for r in records if r.capa_id is not None)
        capa_rate = capa_linked / len(records)

        # IRB notification compliance
        irb_required = [r for r in records if r.irb_notification_required]
        if irb_required:
            irb_compliant = sum(
                1 for r in irb_required if r.irb_notified_date is not None
            )
            irb_rate = irb_compliant / len(irb_required)
        else:
            irb_rate = 1.0  # no requirement → fully compliant

        # Sponsor notification compliance
        sponsor_required = [r for r in records if r.sponsor_notification_required]
        if sponsor_required:
            sponsor_compliant = sum(
                1 for r in sponsor_required if r.sponsor_notified_date is not None
            )
            sponsor_rate = sponsor_compliant / len(sponsor_required)
        else:
            sponsor_rate = 1.0

        # Trends
        trends = self._compute_trends(records)

        return DeviationMetrics(
            total_deviations=len(records),
            by_type=dict(by_type),
            by_severity=dict(by_severity),
            by_status=dict(by_status),
            by_trial=dict(by_trial),
            mean_time_to_resolution_days=round(mtr, 2) if mtr is not None else None,
            capa_linkage_rate=round(capa_rate, 4),
            irb_notification_compliance_rate=round(irb_rate, 4),
            sponsor_notification_compliance_rate=round(sponsor_rate, 4),
            trends=trends,
        )

    # ------------------------------------------------------------------
    # Trends
    # ------------------------------------------------------------------

    def get_trends(self, months: int = 12) -> list[DeviationTrend]:
        """Return monthly deviation trends for the last N months."""
        records = list(self._deviations.values())
        return self._compute_trends(records, months=months)

    def _compute_trends(
        self,
        records: list[DeviationRecord],
        months: int = 12,
    ) -> list[DeviationTrend]:
        """Aggregate records into monthly trend data."""
        now = datetime.now(timezone.utc)
        # Build list of month keys
        month_keys: list[str] = []
        for i in range(months - 1, -1, -1):
            dt = now - timedelta(days=30 * i)
            month_keys.append(dt.strftime("%Y-%m"))

        # Remove duplicates while preserving order
        seen: set[str] = set()
        unique_keys: list[str] = []
        for mk in month_keys:
            if mk not in seen:
                seen.add(mk)
                unique_keys.append(mk)

        # Bucket records by month
        by_month: dict[str, list[DeviationRecord]] = defaultdict(list)
        for r in records:
            mk = r.date_reported.strftime("%Y-%m")
            by_month[mk].append(r)

        trends: list[DeviationTrend] = []
        for mk in unique_keys:
            month_records = by_month.get(mk, [])
            sev_counts = Counter(r.severity.value for r in month_records)
            trends.append(
                DeviationTrend(
                    month=mk,
                    count=len(month_records),
                    by_severity=dict(sev_counts),
                )
            )

        return trends

    # ------------------------------------------------------------------
    # Overdue notifications
    # ------------------------------------------------------------------

    def get_overdue_notifications(self) -> list[DeviationRecord]:
        """Return deviations with overdue IRB or sponsor notifications.

        SLA rules:
        - IRB: Within 5 business days of MAJOR/CRITICAL deviation report.
        - Sponsor: Within 24 hours of CRITICAL deviation report.
        """
        now = datetime.now(timezone.utc)
        overdue: list[DeviationRecord] = []

        for record in self._deviations.values():
            # Skip closed deviations
            if record.status == DeviationStatus.CLOSED:
                continue

            # IRB overdue check
            if (
                record.irb_notification_required
                and record.irb_notified_date is None
            ):
                deadline = record.date_reported + timedelta(
                    days=IRB_NOTIFICATION_SLA_DAYS
                )
                if now > deadline:
                    overdue.append(record)
                    continue

            # Sponsor overdue check
            if (
                record.sponsor_notification_required
                and record.sponsor_notified_date is None
            ):
                deadline = record.date_reported + timedelta(
                    hours=SPONSOR_NOTIFICATION_SLA_HOURS
                )
                if now > deadline:
                    overdue.append(record)

        return overdue

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all deviations (for testing)."""
        with self._lock:
            self._deviations.clear()

    def get_stats(self) -> dict:
        """Return service stats for health/prewarm."""
        return {
            "total_deviations": len(self._deviations),
            "service": "protocol_deviation",
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ProtocolDeviationService | None = None
_instance_lock = threading.Lock()


def get_protocol_deviation_service() -> ProtocolDeviationService:
    """Return the singleton ProtocolDeviationService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ProtocolDeviationService()
    return _instance
