"""Regulatory Submission Tracking Service (CLO-5).

Manages regulatory submissions, milestones, deadlines, and metrics
for clinical trial programs across multiple regulatory bodies.

Usage:
    from app.services.regulatory_submission_service import (
        get_regulatory_submission_service,
    )

    svc = get_regulatory_submission_service()
    submission = svc.create_submission(...)
    calendar = svc.get_calendar()
"""

from __future__ import annotations

import logging
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.regulatory_submissions import (
    DeadlineAlert,
    MilestoneCreate,
    MilestoneStatus,
    MilestoneUpdate,
    RegulatoryBody,
    RegulatoryCalendar,
    RegulatorySubmission,
    RecordResponseRequest,
    SubmissionCreate,
    SubmissionMetrics,
    SubmissionMilestone,
    SubmissionPriority,
    SubmissionStatus,
    SubmissionType,
    SubmissionUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid status transitions
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[SubmissionStatus, set[SubmissionStatus]] = {
    SubmissionStatus.DRAFTING: {
        SubmissionStatus.INTERNAL_REVIEW,
        SubmissionStatus.WITHDRAWN,
    },
    SubmissionStatus.INTERNAL_REVIEW: {
        SubmissionStatus.DRAFTING,
        SubmissionStatus.SUBMITTED,
        SubmissionStatus.WITHDRAWN,
    },
    SubmissionStatus.SUBMITTED: {
        SubmissionStatus.UNDER_REVIEW,
        SubmissionStatus.WITHDRAWN,
    },
    SubmissionStatus.UNDER_REVIEW: {
        SubmissionStatus.INFORMATION_REQUEST,
        SubmissionStatus.APPROVED,
        SubmissionStatus.REJECTED,
        SubmissionStatus.WITHDRAWN,
    },
    SubmissionStatus.INFORMATION_REQUEST: {
        SubmissionStatus.UNDER_REVIEW,
        SubmissionStatus.SUBMITTED,
        SubmissionStatus.WITHDRAWN,
    },
    SubmissionStatus.APPROVED: set(),  # terminal
    SubmissionStatus.REJECTED: {
        SubmissionStatus.DRAFTING,  # allow re-submission
    },
    SubmissionStatus.WITHDRAWN: set(),  # terminal
}


class RegulatorySubmissionService:
    """In-memory regulatory submission management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._submissions: dict[str, RegulatorySubmission] = {}
        self._milestones: dict[str, SubmissionMilestone] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic regulatory submissions for Regeneron trials."""
        now = datetime.now(timezone.utc)

        # Stable trial IDs matching trial_eligibility_service
        eylea_id = "00000000-de00-0001-0000-000000000001"
        dupixent_id = "00000000-de00-0002-0000-000000000002"
        libtayo_id = "00000000-de00-0003-0000-000000000003"

        seed_submissions: list[dict] = [
            # 1. IND for EYLEA HD - APPROVED by FDA
            {
                "title": "IND Application - EYLEA HD Phase 3 DME Trial",
                "submission_type": SubmissionType.IND,
                "regulatory_body": RegulatoryBody.FDA,
                "trial_id": eylea_id,
                "status": SubmissionStatus.APPROVED,
                "reference_number": "IND-2024-78432",
                "submitted_date": now - timedelta(days=180),
                "expected_response_date": now - timedelta(days=150),
                "actual_response_date": now - timedelta(days=155),
                "assigned_to": "Dr. Sarah Chen",
                "reviewer": "Dr. Michael Torres",
                "priority": SubmissionPriority.HIGH,
                "notes": "IND approved. 30-day safety review passed without clinical hold.",
            },
            # 2. Protocol Amendment for Dupixent - SUBMITTED to FDA
            {
                "title": "Protocol Amendment v4.2 - Dupixent Atopic Dermatitis",
                "submission_type": SubmissionType.PROTOCOL_AMENDMENT,
                "regulatory_body": RegulatoryBody.FDA,
                "trial_id": dupixent_id,
                "status": SubmissionStatus.SUBMITTED,
                "reference_number": "AMD-2025-00142",
                "submitted_date": now - timedelta(days=14),
                "expected_response_date": now + timedelta(days=16),
                "assigned_to": "Dr. James Liu",
                "reviewer": "Dr. Emily Watson",
                "priority": SubmissionPriority.HIGH,
                "notes": "Amendment adds adolescent sub-group (12-17 years). Includes updated PK sampling schedule.",
            },
            # 3. Protocol Amendment for Dupixent - SUBMITTED to EMA
            {
                "title": "Substantial Amendment - Dupixent AD Trial (EU)",
                "submission_type": SubmissionType.PROTOCOL_AMENDMENT,
                "regulatory_body": RegulatoryBody.EMA,
                "trial_id": dupixent_id,
                "status": SubmissionStatus.SUBMITTED,
                "reference_number": "EMA/H/C/004390/II/0087",
                "submitted_date": now - timedelta(days=10),
                "expected_response_date": now + timedelta(days=50),
                "assigned_to": "Dr. Hans Mueller",
                "reviewer": "Dr. Sophie Laurent",
                "priority": SubmissionPriority.HIGH,
                "notes": "Parallel submission with FDA amendment. EU-specific language adjustments.",
            },
            # 4. IRB Approval for Libtayo - APPROVED
            {
                "title": "IRB Initial Approval - Libtayo CSCC Combination Study",
                "submission_type": SubmissionType.IRB_APPROVAL,
                "regulatory_body": RegulatoryBody.FDA,
                "trial_id": libtayo_id,
                "status": SubmissionStatus.APPROVED,
                "reference_number": "IRB-2024-0892",
                "submitted_date": now - timedelta(days=90),
                "expected_response_date": now - timedelta(days=60),
                "actual_response_date": now - timedelta(days=65),
                "assigned_to": "Dr. Robert Kim",
                "reviewer": "Jennifer Walsh",
                "priority": SubmissionPriority.STANDARD,
                "notes": "Central IRB approval obtained. All 12 sites can begin enrollment.",
            },
            # 5. Annual Safety Report - DRAFTING for FDA
            {
                "title": "Annual Safety Report - EYLEA HD (Year 1)",
                "submission_type": SubmissionType.ANNUAL_REPORT,
                "regulatory_body": RegulatoryBody.FDA,
                "trial_id": eylea_id,
                "status": SubmissionStatus.DRAFTING,
                "assigned_to": "Dr. Lisa Park",
                "reviewer": "Dr. Sarah Chen",
                "priority": SubmissionPriority.STANDARD,
                "notes": "Compiling AE/SAE data from all sites. Due to FDA within 60 days of IND anniversary.",
            },
            # 6. DSMB Report - INTERNAL_REVIEW
            {
                "title": "DSMB Interim Analysis Report - Libtayo CSCC",
                "submission_type": SubmissionType.DSMB_REPORT,
                "regulatory_body": RegulatoryBody.FDA,
                "trial_id": libtayo_id,
                "status": SubmissionStatus.INTERNAL_REVIEW,
                "assigned_to": "Dr. Michael Torres",
                "reviewer": "Dr. Robert Kim",
                "priority": SubmissionPriority.URGENT,
                "notes": "Interim futility/efficacy analysis at 50% enrollment. DSMB meeting scheduled.",
            },
            # 7. EMA submission - UNDER_REVIEW
            {
                "title": "Clinical Trial Application - EYLEA HD (EU)",
                "submission_type": SubmissionType.IND,
                "regulatory_body": RegulatoryBody.EMA,
                "trial_id": eylea_id,
                "status": SubmissionStatus.UNDER_REVIEW,
                "reference_number": "EudraCT-2024-004521-38",
                "submitted_date": now - timedelta(days=45),
                "expected_response_date": now + timedelta(days=15),
                "assigned_to": "Dr. Hans Mueller",
                "reviewer": "Dr. Sophie Laurent",
                "priority": SubmissionPriority.HIGH,
                "notes": "CTA under review by lead member state (Germany). Day 60 assessment pending.",
            },
            # 8. MHRA submission - INFORMATION_REQUEST
            {
                "title": "CTA - Dupixent AD Trial (UK)",
                "submission_type": SubmissionType.IND,
                "regulatory_body": RegulatoryBody.MHRA,
                "trial_id": dupixent_id,
                "status": SubmissionStatus.INFORMATION_REQUEST,
                "reference_number": "MHRA-CTA-2025-01234",
                "submitted_date": now - timedelta(days=60),
                "expected_response_date": now - timedelta(days=20),
                "assigned_to": "Dr. Emily Watson",
                "reviewer": "Dr. James Liu",
                "priority": SubmissionPriority.HIGH,
                "notes": "MHRA requested additional CMC data for drug product stability. Response due in 14 days.",
            },
            # 9. Health Canada - SUBMITTED
            {
                "title": "CTA - Libtayo CSCC Combination (Canada)",
                "submission_type": SubmissionType.IND,
                "regulatory_body": RegulatoryBody.HEALTH_CANADA,
                "trial_id": libtayo_id,
                "status": SubmissionStatus.SUBMITTED,
                "reference_number": "HC-CTA-2025-0567",
                "submitted_date": now - timedelta(days=20),
                "expected_response_date": now + timedelta(days=10),
                "assigned_to": "Dr. Maria Santos",
                "reviewer": "Dr. Robert Kim",
                "priority": SubmissionPriority.STANDARD,
                "notes": "Standard 30-day review. No Qualifying Notice expected.",
            },
            # 10. Safety Report - SUBMITTED to FDA
            {
                "title": "IND Safety Report - Unexpected SAE (EYLEA HD)",
                "submission_type": SubmissionType.SAFETY_REPORT,
                "regulatory_body": RegulatoryBody.FDA,
                "trial_id": eylea_id,
                "status": SubmissionStatus.SUBMITTED,
                "reference_number": "SR-2025-0034",
                "submitted_date": now - timedelta(days=3),
                "expected_response_date": now + timedelta(days=12),
                "assigned_to": "Dr. Lisa Park",
                "reviewer": "Dr. Michael Torres",
                "priority": SubmissionPriority.URGENT,
                "notes": "15-day safety report for unexpected serious adverse event (retinal detachment in non-study eye).",
            },
        ]

        for i, data in enumerate(seed_submissions, start=1):
            sub_id = f"SUB-{i:04d}"
            created_at = data.get("submitted_date", now - timedelta(days=30 + i * 10)) - timedelta(days=14)
            self._submissions[sub_id] = RegulatorySubmission(
                id=sub_id,
                title=data["title"],
                submission_type=data["submission_type"],
                regulatory_body=data["regulatory_body"],
                trial_id=data["trial_id"],
                status=data["status"],
                reference_number=data.get("reference_number"),
                submitted_date=data.get("submitted_date"),
                expected_response_date=data.get("expected_response_date"),
                actual_response_date=data.get("actual_response_date"),
                assigned_to=data.get("assigned_to"),
                reviewer=data.get("reviewer"),
                priority=data.get("priority", SubmissionPriority.STANDARD),
                documents=[],
                notes=data.get("notes"),
                created_at=created_at,
                updated_at=created_at,
            )

        # Seed milestones for each submission
        self._seed_milestones(now)

    def _seed_milestones(self, now: datetime) -> None:
        """Pre-populate milestones for seeded submissions."""
        milestone_defs: dict[str, list[dict]] = {
            # SUB-0001: IND for EYLEA HD (APPROVED)
            "SUB-0001": [
                {"name": "Pre-IND meeting minutes finalized", "offset_days": -200, "completed_offset": -195, "status": MilestoneStatus.COMPLETED, "responsible": "Dr. Sarah Chen"},
                {"name": "IND submission package compiled", "offset_days": -185, "completed_offset": -182, "status": MilestoneStatus.COMPLETED, "responsible": "Regulatory Affairs Team"},
                {"name": "FDA 30-day safety review complete", "offset_days": -150, "completed_offset": -155, "status": MilestoneStatus.COMPLETED, "responsible": "FDA"},
                {"name": "First patient dosed", "offset_days": -140, "completed_offset": -138, "status": MilestoneStatus.COMPLETED, "responsible": "Dr. Michael Torres"},
            ],
            # SUB-0002: Protocol Amendment Dupixent (FDA, SUBMITTED)
            "SUB-0002": [
                {"name": "Amendment draft finalized", "offset_days": -20, "completed_offset": -18, "status": MilestoneStatus.COMPLETED, "responsible": "Dr. James Liu"},
                {"name": "Internal review complete", "offset_days": -15, "completed_offset": -14, "status": MilestoneStatus.COMPLETED, "responsible": "Dr. Emily Watson"},
                {"name": "FDA submission", "offset_days": -14, "completed_offset": -14, "status": MilestoneStatus.COMPLETED, "responsible": "Regulatory Affairs"},
                {"name": "FDA acknowledgment", "offset_days": 5, "status": MilestoneStatus.PENDING, "responsible": "FDA"},
                {"name": "Site implementation", "offset_days": 30, "status": MilestoneStatus.PENDING, "responsible": "Clinical Operations"},
            ],
            # SUB-0003: Protocol Amendment Dupixent (EMA, SUBMITTED)
            "SUB-0003": [
                {"name": "EU-specific amendment drafted", "offset_days": -18, "completed_offset": -15, "status": MilestoneStatus.COMPLETED, "responsible": "Dr. Hans Mueller"},
                {"name": "EMA submission", "offset_days": -10, "completed_offset": -10, "status": MilestoneStatus.COMPLETED, "responsible": "EU Regulatory Affairs"},
                {"name": "Member state validation", "offset_days": 20, "status": MilestoneStatus.PENDING, "responsible": "EMA"},
                {"name": "EU site activation", "offset_days": 60, "status": MilestoneStatus.PENDING, "responsible": "EU Clinical Ops"},
            ],
            # SUB-0004: IRB Approval Libtayo (APPROVED)
            "SUB-0004": [
                {"name": "IRB package submitted", "offset_days": -90, "completed_offset": -90, "status": MilestoneStatus.COMPLETED, "responsible": "Jennifer Walsh"},
                {"name": "IRB review meeting", "offset_days": -70, "completed_offset": -72, "status": MilestoneStatus.COMPLETED, "responsible": "Central IRB"},
                {"name": "IRB approval letter received", "offset_days": -60, "completed_offset": -65, "status": MilestoneStatus.COMPLETED, "responsible": "Central IRB"},
            ],
            # SUB-0005: Annual Safety Report (DRAFTING)
            "SUB-0005": [
                {"name": "AE/SAE data compilation", "offset_days": 10, "status": MilestoneStatus.PENDING, "responsible": "Drug Safety Team"},
                {"name": "Safety narrative drafting", "offset_days": 25, "status": MilestoneStatus.PENDING, "responsible": "Dr. Lisa Park"},
                {"name": "Medical review", "offset_days": 40, "status": MilestoneStatus.PENDING, "responsible": "Dr. Sarah Chen"},
                {"name": "FDA submission deadline", "offset_days": 55, "status": MilestoneStatus.PENDING, "responsible": "Regulatory Affairs"},
            ],
            # SUB-0006: DSMB Report (INTERNAL_REVIEW)
            "SUB-0006": [
                {"name": "Statistical analysis complete", "offset_days": -5, "completed_offset": -3, "status": MilestoneStatus.COMPLETED, "responsible": "Biostatistics Team"},
                {"name": "DSMB report drafted", "offset_days": 0, "status": MilestoneStatus.PENDING, "responsible": "Dr. Michael Torres"},
                {"name": "DSMB meeting", "offset_days": 10, "status": MilestoneStatus.PENDING, "responsible": "DSMB Chair"},
                {"name": "DSMB recommendation letter", "offset_days": 15, "status": MilestoneStatus.PENDING, "responsible": "DSMB"},
            ],
            # SUB-0007: EMA CTA EYLEA HD (UNDER_REVIEW)
            "SUB-0007": [
                {"name": "CTA dossier compiled", "offset_days": -55, "completed_offset": -50, "status": MilestoneStatus.COMPLETED, "responsible": "EU Regulatory Affairs"},
                {"name": "CTA submitted to lead member state", "offset_days": -45, "completed_offset": -45, "status": MilestoneStatus.COMPLETED, "responsible": "Dr. Hans Mueller"},
                {"name": "Day 60 assessment report", "offset_days": 15, "status": MilestoneStatus.PENDING, "responsible": "German BfArM"},
                {"name": "Ethics committee approval", "offset_days": 25, "status": MilestoneStatus.PENDING, "responsible": "German Ethics Committee"},
            ],
            # SUB-0008: MHRA CTA Dupixent (INFORMATION_REQUEST)
            "SUB-0008": [
                {"name": "CTA submitted to MHRA", "offset_days": -60, "completed_offset": -60, "status": MilestoneStatus.COMPLETED, "responsible": "UK Regulatory Affairs"},
                {"name": "MHRA initial assessment", "offset_days": -30, "completed_offset": -28, "status": MilestoneStatus.COMPLETED, "responsible": "MHRA"},
                {"name": "Response to information request", "offset_days": 5, "status": MilestoneStatus.OVERDUE, "responsible": "Dr. Emily Watson"},
                {"name": "MHRA final decision", "offset_days": 20, "status": MilestoneStatus.PENDING, "responsible": "MHRA"},
            ],
            # SUB-0009: Health Canada CTA Libtayo (SUBMITTED)
            "SUB-0009": [
                {"name": "CTA package compiled", "offset_days": -30, "completed_offset": -25, "status": MilestoneStatus.COMPLETED, "responsible": "Dr. Maria Santos"},
                {"name": "CTA submitted", "offset_days": -20, "completed_offset": -20, "status": MilestoneStatus.COMPLETED, "responsible": "Canadian Regulatory Affairs"},
                {"name": "30-day review period ends", "offset_days": 10, "status": MilestoneStatus.PENDING, "responsible": "Health Canada"},
                {"name": "Canadian site activation", "offset_days": 20, "status": MilestoneStatus.PENDING, "responsible": "Canadian Clinical Ops"},
            ],
            # SUB-0010: Safety Report EYLEA HD (SUBMITTED)
            "SUB-0010": [
                {"name": "Initial SAE assessment", "offset_days": -5, "completed_offset": -4, "status": MilestoneStatus.COMPLETED, "responsible": "Drug Safety Team"},
                {"name": "15-day safety report submitted", "offset_days": -3, "completed_offset": -3, "status": MilestoneStatus.COMPLETED, "responsible": "Dr. Lisa Park"},
                {"name": "FDA acknowledgment", "offset_days": 5, "status": MilestoneStatus.PENDING, "responsible": "FDA"},
                {"name": "Follow-up report if needed", "offset_days": 30, "status": MilestoneStatus.PENDING, "responsible": "Drug Safety Team"},
            ],
        }

        ms_counter = 0
        for sub_id, milestones in milestone_defs.items():
            for m in milestones:
                ms_counter += 1
                ms_id = f"MS-{ms_counter:04d}"
                due = now + timedelta(days=m["offset_days"])
                completed = None
                if "completed_offset" in m:
                    completed = now + timedelta(days=m["completed_offset"])
                self._milestones[ms_id] = SubmissionMilestone(
                    id=ms_id,
                    submission_id=sub_id,
                    milestone_name=m["name"],
                    due_date=due,
                    completed_date=completed,
                    status=m["status"],
                    responsible=m.get("responsible"),
                )

    # ------------------------------------------------------------------
    # CRUD: Submissions
    # ------------------------------------------------------------------

    def create_submission(self, payload: SubmissionCreate) -> RegulatorySubmission:
        """Create a new regulatory submission."""
        now = datetime.now(timezone.utc)
        with self._lock:
            sub_id = f"SUB-{uuid4().hex[:8].upper()}"
            submission = RegulatorySubmission(
                id=sub_id,
                title=payload.title,
                submission_type=payload.submission_type,
                regulatory_body=payload.regulatory_body,
                trial_id=payload.trial_id,
                status=SubmissionStatus.DRAFTING,
                priority=payload.priority,
                assigned_to=payload.assigned_to,
                reviewer=payload.reviewer,
                notes=payload.notes,
                documents=[],
                created_at=now,
                updated_at=now,
            )
            self._submissions[sub_id] = submission
            logger.info("Created regulatory submission %s: %s", sub_id, payload.title)
            return submission

    def get_submission(self, submission_id: str) -> RegulatorySubmission:
        """Retrieve a single submission by ID."""
        with self._lock:
            sub = self._submissions.get(submission_id)
            if sub is None:
                raise KeyError(f"Submission {submission_id} not found")
            return sub

    def update_submission(
        self, submission_id: str, payload: SubmissionUpdate
    ) -> RegulatorySubmission:
        """Update an existing submission."""
        now = datetime.now(timezone.utc)
        with self._lock:
            sub = self._submissions.get(submission_id)
            if sub is None:
                raise KeyError(f"Submission {submission_id} not found")

            data = sub.model_dump()

            if payload.status is not None and payload.status != sub.status:
                allowed = VALID_TRANSITIONS.get(sub.status, set())
                if payload.status not in allowed:
                    raise ValueError(
                        f"Invalid status transition: {sub.status.value} -> {payload.status.value}"
                    )
                data["status"] = payload.status

            for field in ("title", "priority", "assigned_to", "reviewer", "reference_number", "expected_response_date", "notes"):
                val = getattr(payload, field)
                if val is not None:
                    data[field] = val

            data["updated_at"] = now
            updated = RegulatorySubmission(**data)
            self._submissions[submission_id] = updated
            logger.info("Updated submission %s", submission_id)
            return updated

    def delete_submission(self, submission_id: str) -> None:
        """Delete a submission and its milestones."""
        with self._lock:
            if submission_id not in self._submissions:
                raise KeyError(f"Submission {submission_id} not found")
            del self._submissions[submission_id]
            # Remove associated milestones
            to_remove = [
                ms_id for ms_id, ms in self._milestones.items()
                if ms.submission_id == submission_id
            ]
            for ms_id in to_remove:
                del self._milestones[ms_id]
            logger.info("Deleted submission %s and %d milestones", submission_id, len(to_remove))

    def list_submissions(
        self,
        *,
        trial_id: str | None = None,
        submission_type: SubmissionType | None = None,
        regulatory_body: RegulatoryBody | None = None,
        status: SubmissionStatus | None = None,
        priority: SubmissionPriority | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RegulatorySubmission], int]:
        """List submissions with optional filters."""
        with self._lock:
            items = list(self._submissions.values())

        if trial_id is not None:
            items = [s for s in items if s.trial_id == trial_id]
        if submission_type is not None:
            items = [s for s in items if s.submission_type == submission_type]
        if regulatory_body is not None:
            items = [s for s in items if s.regulatory_body == regulatory_body]
        if status is not None:
            items = [s for s in items if s.status == status]
        if priority is not None:
            items = [s for s in items if s.priority == priority]

        # Sort by updated_at descending
        items.sort(key=lambda s: s.updated_at, reverse=True)
        total = len(items)
        return items[offset: offset + limit], total

    # ------------------------------------------------------------------
    # Workflow: Submit
    # ------------------------------------------------------------------

    def submit(self, submission_id: str) -> RegulatorySubmission:
        """Transition a submission to SUBMITTED status with date stamp."""
        now = datetime.now(timezone.utc)
        with self._lock:
            sub = self._submissions.get(submission_id)
            if sub is None:
                raise KeyError(f"Submission {submission_id} not found")

            allowed = VALID_TRANSITIONS.get(sub.status, set())
            if SubmissionStatus.SUBMITTED not in allowed:
                raise ValueError(
                    f"Cannot submit from status {sub.status.value}. "
                    f"Allowed transitions: {[s.value for s in allowed]}"
                )

            data = sub.model_dump()
            data["status"] = SubmissionStatus.SUBMITTED
            data["submitted_date"] = now
            data["updated_at"] = now
            updated = RegulatorySubmission(**data)
            self._submissions[submission_id] = updated
            logger.info("Submission %s submitted at %s", submission_id, now.isoformat())
            return updated

    # ------------------------------------------------------------------
    # Workflow: Record response
    # ------------------------------------------------------------------

    def record_response(
        self, submission_id: str, request: RecordResponseRequest
    ) -> RegulatorySubmission:
        """Record a regulatory body response."""
        now = datetime.now(timezone.utc)
        with self._lock:
            sub = self._submissions.get(submission_id)
            if sub is None:
                raise KeyError(f"Submission {submission_id} not found")

            allowed = VALID_TRANSITIONS.get(sub.status, set())
            if request.status not in allowed:
                raise ValueError(
                    f"Invalid response status transition: {sub.status.value} -> {request.status.value}"
                )

            data = sub.model_dump()
            data["status"] = request.status
            data["actual_response_date"] = now
            data["updated_at"] = now
            if request.notes:
                existing = data.get("notes") or ""
                data["notes"] = f"{existing}\n[Response] {request.notes}".strip()
            updated = RegulatorySubmission(**data)
            self._submissions[submission_id] = updated
            logger.info(
                "Recorded response for %s: %s", submission_id, request.status.value
            )
            return updated

    # ------------------------------------------------------------------
    # CRUD: Milestones
    # ------------------------------------------------------------------

    def create_milestone(
        self, submission_id: str, payload: MilestoneCreate
    ) -> SubmissionMilestone:
        """Create a new milestone for a submission."""
        with self._lock:
            if submission_id not in self._submissions:
                raise KeyError(f"Submission {submission_id} not found")
            ms_id = f"MS-{uuid4().hex[:8].upper()}"
            milestone = SubmissionMilestone(
                id=ms_id,
                submission_id=submission_id,
                milestone_name=payload.milestone_name,
                due_date=payload.due_date,
                responsible=payload.responsible,
                status=MilestoneStatus.PENDING,
            )
            self._milestones[ms_id] = milestone
            logger.info("Created milestone %s for submission %s", ms_id, submission_id)
            return milestone

    def get_milestone(self, milestone_id: str) -> SubmissionMilestone:
        """Retrieve a single milestone by ID."""
        with self._lock:
            ms = self._milestones.get(milestone_id)
            if ms is None:
                raise KeyError(f"Milestone {milestone_id} not found")
            return ms

    def update_milestone(
        self, milestone_id: str, payload: MilestoneUpdate
    ) -> SubmissionMilestone:
        """Update an existing milestone."""
        with self._lock:
            ms = self._milestones.get(milestone_id)
            if ms is None:
                raise KeyError(f"Milestone {milestone_id} not found")

            data = ms.model_dump()
            for field in ("milestone_name", "due_date", "status", "completed_date", "responsible"):
                val = getattr(payload, field)
                if val is not None:
                    data[field] = val

            # Auto-set completed_date when status becomes COMPLETED
            if payload.status == MilestoneStatus.COMPLETED and data.get("completed_date") is None:
                data["completed_date"] = datetime.now(timezone.utc)

            updated = SubmissionMilestone(**data)
            self._milestones[milestone_id] = updated
            logger.info("Updated milestone %s", milestone_id)
            return updated

    def delete_milestone(self, milestone_id: str) -> None:
        """Delete a milestone."""
        with self._lock:
            if milestone_id not in self._milestones:
                raise KeyError(f"Milestone {milestone_id} not found")
            del self._milestones[milestone_id]
            logger.info("Deleted milestone %s", milestone_id)

    def list_milestones(
        self, submission_id: str
    ) -> list[SubmissionMilestone]:
        """List milestones for a submission, sorted by due date."""
        with self._lock:
            if submission_id not in self._submissions:
                raise KeyError(f"Submission {submission_id} not found")
            items = [
                ms for ms in self._milestones.values()
                if ms.submission_id == submission_id
            ]
        items.sort(key=lambda m: m.due_date)
        return items

    # ------------------------------------------------------------------
    # Calendar
    # ------------------------------------------------------------------

    def get_calendar(self) -> RegulatoryCalendar:
        """Build regulatory calendar with upcoming, overdue, and pending."""
        now = datetime.now(timezone.utc)
        upcoming: list[DeadlineAlert] = []
        overdue: list[DeadlineAlert] = []

        with self._lock:
            # Check milestones
            for ms in self._milestones.values():
                if ms.status in (MilestoneStatus.COMPLETED, MilestoneStatus.WAIVED):
                    continue
                sub = self._submissions.get(ms.submission_id)
                if sub is None:
                    continue
                days_until = (ms.due_date - now).days
                alert = DeadlineAlert(
                    submission_id=ms.submission_id,
                    submission_title=sub.title,
                    milestone_id=ms.id,
                    milestone_name=ms.milestone_name,
                    due_date=ms.due_date,
                    days_until_due=days_until,
                    is_overdue=days_until < 0,
                )
                if days_until < 0:
                    overdue.append(alert)
                elif days_until <= 30:
                    upcoming.append(alert)

            # Check expected response dates
            for sub in self._submissions.values():
                if sub.status in (
                    SubmissionStatus.SUBMITTED,
                    SubmissionStatus.UNDER_REVIEW,
                ) and sub.expected_response_date:
                    days_until = (sub.expected_response_date - now).days
                    alert = DeadlineAlert(
                        submission_id=sub.id,
                        submission_title=sub.title,
                        due_date=sub.expected_response_date,
                        days_until_due=days_until,
                        is_overdue=days_until < 0,
                    )
                    if days_until < 0:
                        overdue.append(alert)
                    elif days_until <= 30:
                        upcoming.append(alert)

            awaiting = [
                sub for sub in self._submissions.values()
                if sub.status in (
                    SubmissionStatus.SUBMITTED,
                    SubmissionStatus.UNDER_REVIEW,
                )
            ]

        upcoming.sort(key=lambda a: a.due_date)
        overdue.sort(key=lambda a: a.days_until_due)

        return RegulatoryCalendar(
            upcoming_deadlines=upcoming,
            overdue=overdue,
            submitted_awaiting_response=awaiting,
        )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> SubmissionMetrics:
        """Compute aggregated submission program metrics."""
        with self._lock:
            subs = list(self._submissions.values())
            milestones = list(self._milestones.values())

        total = len(subs)
        by_type = dict(Counter(s.submission_type.value for s in subs))
        by_body = dict(Counter(s.regulatory_body.value for s in subs))
        by_status = dict(Counter(s.status.value for s in subs))

        # Average review time
        review_times: list[float] = []
        approved_count = 0
        resolved_count = 0
        for s in subs:
            if s.actual_response_date and s.submitted_date:
                delta = (s.actual_response_date - s.submitted_date).total_seconds() / 86400
                review_times.append(delta)
            if s.status == SubmissionStatus.APPROVED:
                approved_count += 1
            if s.status in (SubmissionStatus.APPROVED, SubmissionStatus.REJECTED):
                resolved_count += 1

        avg_review = (
            sum(review_times) / len(review_times) if review_times else None
        )
        approval_rate = approved_count / resolved_count if resolved_count > 0 else 0.0

        now = datetime.now(timezone.utc)
        overdue_ms = sum(
            1 for m in milestones
            if m.status not in (MilestoneStatus.COMPLETED, MilestoneStatus.WAIVED)
            and m.due_date < now
        )

        info_requests = sum(
            1 for s in subs
            if s.status == SubmissionStatus.INFORMATION_REQUEST
        )

        return SubmissionMetrics(
            total_submissions=total,
            by_type=by_type,
            by_body=by_body,
            by_status=by_status,
            avg_review_time_days=round(avg_review, 1) if avg_review is not None else None,
            approval_rate=round(approval_rate, 4),
            overdue_milestones=overdue_ms,
            pending_information_requests=info_requests,
        )

    # ------------------------------------------------------------------
    # Information requests
    # ------------------------------------------------------------------

    def get_information_requests(self) -> list[RegulatorySubmission]:
        """Return submissions that have pending information requests."""
        with self._lock:
            return [
                s for s in self._submissions.values()
                if s.status == SubmissionStatus.INFORMATION_REQUEST
            ]

    # ------------------------------------------------------------------
    # Deadline checking
    # ------------------------------------------------------------------

    def check_deadlines(self, days_ahead: int = 14) -> list[DeadlineAlert]:
        """Flag approaching and overdue deadlines."""
        now = datetime.now(timezone.utc)
        alerts: list[DeadlineAlert] = []

        with self._lock:
            for ms in self._milestones.values():
                if ms.status in (MilestoneStatus.COMPLETED, MilestoneStatus.WAIVED):
                    continue
                sub = self._submissions.get(ms.submission_id)
                if sub is None:
                    continue
                days_until = (ms.due_date - now).days
                if days_until <= days_ahead:
                    alerts.append(DeadlineAlert(
                        submission_id=ms.submission_id,
                        submission_title=sub.title,
                        milestone_id=ms.id,
                        milestone_name=ms.milestone_name,
                        due_date=ms.due_date,
                        days_until_due=days_until,
                        is_overdue=days_until < 0,
                    ))

        alerts.sort(key=lambda a: a.days_until_due)
        return alerts

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all data (for testing)."""
        with self._lock:
            self._submissions.clear()
            self._milestones.clear()

    def get_stats(self) -> dict:
        """Return service statistics."""
        with self._lock:
            return {
                "submissions": len(self._submissions),
                "milestones": len(self._milestones),
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: RegulatorySubmissionService | None = None
_instance_lock = threading.Lock()


def get_regulatory_submission_service() -> RegulatorySubmissionService:
    """Return the singleton RegulatorySubmissionService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = RegulatorySubmissionService()
                logger.info("RegulatorySubmissionService initialized")
    return _instance
