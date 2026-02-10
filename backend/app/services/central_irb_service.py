"""Central IRB/EC Management Service (CLINICAL-8).

Manages Institutional Review Board and Ethics Committee operations including
board registration, submission lifecycle, continuing reviews, reportable event
filing, regulatory document tracking, correspondence management, and metrics.

Usage:
    from app.services.central_irb_service import (
        get_central_irb_service,
    )

    svc = get_central_irb_service()
    submissions = svc.list_submissions()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.central_irb import (
    BoardType,
    ContinuingReview,
    ContinuingReviewCreate,
    ContinuingReviewUpdate,
    CorrespondenceDirection,
    DocumentStatus,
    DocumentType,
    EventSeverity,
    EventStatus,
    IRBBoard,
    IRBBoardCreate,
    IRBBoardUpdate,
    IRBCorrespondence,
    IRBCorrespondenceCreate,
    IRBMetrics,
    IRBSubmission,
    IRBSubmissionCreate,
    IRBSubmissionUpdate,
    RecordOutcomeRequest,
    RegulatoryDocument,
    RegulatoryDocumentCreate,
    ReportableEvent,
    ReportableEventCreate,
    ReportableEventUpdate,
    ReviewOutcome,
    ReviewStatus,
    SubmissionSubmitRequest,
    SubmissionType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class CentralIRBService:
    """In-memory Central IRB/EC Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._boards: dict[str, IRBBoard] = {}
        self._submissions: dict[str, IRBSubmission] = {}
        self._continuing_reviews: dict[str, ContinuingReview] = {}
        self._reportable_events: dict[str, ReportableEvent] = {}
        self._documents: dict[str, RegulatoryDocument] = {}
        self._correspondence: dict[str, IRBCorrespondence] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic IRB/EC data for clinical trials."""
        now = datetime.now(timezone.utc)

        # --- 3 Boards ---
        boards_data = [
            {
                "id": "IRB-001",
                "name": "WCG IRB (Western Institutional Review Board)",
                "board_type": BoardType.CENTRAL_IRB,
                "organization": "WCG Clinical",
                "country": "United States",
                "contact_email": "submissions@wcgirb.com",
                "meeting_schedule": "Weekly, every Tuesday",
                "submission_lead_time_days": 14,
                "active": True,
            },
            {
                "id": "IRB-002",
                "name": "Advarra Central IRB",
                "board_type": BoardType.CENTRAL_IRB,
                "organization": "Advarra Inc.",
                "country": "United States",
                "contact_email": "irb@advarra.com",
                "meeting_schedule": "Bi-weekly, alternating Thursdays",
                "submission_lead_time_days": 21,
                "active": True,
            },
            {
                "id": "IRB-003",
                "name": "NHS Health Research Authority REC",
                "board_type": BoardType.ETHICS_COMMITTEE,
                "organization": "National Health Service",
                "country": "United Kingdom",
                "contact_email": "rec@hra.nhs.uk",
                "meeting_schedule": "Monthly, first Wednesday",
                "submission_lead_time_days": 30,
                "active": True,
            },
        ]

        for b in boards_data:
            self._boards[b["id"]] = IRBBoard(**b)

        # --- 7 Submissions ---
        submissions_data = [
            {
                "id": "SUB-001",
                "board_id": "IRB-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": None,
                "submission_type": SubmissionType.INITIAL,
                "submission_number": "WCG-2025-001",
                "protocol_version": "1.0",
                "submitted_date": now - timedelta(days=180),
                "submitted_by": "Dr. Sarah Chen",
                "review_date": now - timedelta(days=165),
                "status": ReviewStatus.APPROVED,
                "outcome": ReviewOutcome.APPROVED,
                "approval_date": now - timedelta(days=165),
                "expiry_date": now + timedelta(days=200),
                "conditions": None,
                "response_due_date": None,
                "notes": "Initial protocol approval granted.",
            },
            {
                "id": "SUB-002",
                "board_id": "IRB-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "submission_type": SubmissionType.AMENDMENT,
                "submission_number": "WCG-2025-002",
                "protocol_version": "2.0",
                "submitted_date": now - timedelta(days=90),
                "submitted_by": "Dr. Sarah Chen",
                "review_date": now - timedelta(days=75),
                "status": ReviewStatus.APPROVED_WITH_CONDITIONS,
                "outcome": ReviewOutcome.CONDITIONALLY_APPROVED,
                "approval_date": now - timedelta(days=75),
                "expiry_date": now + timedelta(days=290),
                "conditions": "Update ICF to include new safety information within 30 days.",
                "response_due_date": now - timedelta(days=45),
                "notes": "Amendment to add new dosing arm.",
            },
            {
                "id": "SUB-003",
                "board_id": "IRB-002",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": None,
                "submission_type": SubmissionType.INITIAL,
                "submission_number": "ADV-2025-101",
                "protocol_version": "1.0",
                "submitted_date": now - timedelta(days=120),
                "submitted_by": "Dr. James Rodriguez",
                "review_date": now - timedelta(days=100),
                "status": ReviewStatus.APPROVED,
                "outcome": ReviewOutcome.APPROVED,
                "approval_date": now - timedelta(days=100),
                "expiry_date": now + timedelta(days=265),
                "conditions": None,
                "response_due_date": None,
                "notes": "Dupixent atopic dermatitis trial approved.",
            },
            {
                "id": "SUB-004",
                "board_id": "IRB-002",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "submission_type": SubmissionType.CONTINUING_REVIEW,
                "submission_number": "ADV-2025-102",
                "protocol_version": "1.0",
                "submitted_date": now - timedelta(days=30),
                "submitted_by": "Dr. James Rodriguez",
                "review_date": None,
                "status": ReviewStatus.UNDER_REVIEW,
                "outcome": None,
                "approval_date": None,
                "expiry_date": None,
                "conditions": None,
                "response_due_date": None,
                "notes": "Annual continuing review for Dupixent trial.",
            },
            {
                "id": "SUB-005",
                "board_id": "IRB-003",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": None,
                "submission_type": SubmissionType.INITIAL,
                "submission_number": "HRA-2025-050",
                "protocol_version": "1.0",
                "submitted_date": now - timedelta(days=60),
                "submitted_by": "Dr. Emily Watson",
                "review_date": now - timedelta(days=40),
                "status": ReviewStatus.APPROVED,
                "outcome": ReviewOutcome.APPROVED,
                "approval_date": now - timedelta(days=40),
                "expiry_date": now + timedelta(days=15),
                "conditions": None,
                "response_due_date": None,
                "notes": "Libtayo NSCLC trial UK ethics approval.",
            },
            {
                "id": "SUB-006",
                "board_id": "IRB-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-105",
                "submission_type": SubmissionType.SAFETY_REPORT,
                "submission_number": "WCG-2025-003",
                "protocol_version": "2.0",
                "submitted_date": now - timedelta(days=15),
                "submitted_by": "Dr. Michael Park",
                "review_date": None,
                "status": ReviewStatus.SUBMITTED,
                "outcome": None,
                "approval_date": None,
                "expiry_date": None,
                "conditions": None,
                "response_due_date": now + timedelta(days=15),
                "notes": "Safety report for serious adverse event at SITE-105.",
            },
            {
                "id": "SUB-007",
                "board_id": "IRB-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": None,
                "submission_type": SubmissionType.STUDY_CLOSURE,
                "submission_number": "WCG-2025-004",
                "protocol_version": "2.0",
                "submitted_date": None,
                "submitted_by": "Dr. Sarah Chen",
                "review_date": None,
                "status": ReviewStatus.DRAFT,
                "outcome": None,
                "approval_date": None,
                "expiry_date": None,
                "conditions": None,
                "response_due_date": None,
                "notes": "Study closure submission pending finalization.",
            },
        ]

        for s in submissions_data:
            self._submissions[s["id"]] = IRBSubmission(**s)

        # --- 3 Continuing Reviews ---
        cr_data = [
            {
                "id": "CR-001",
                "submission_id": "SUB-001",
                "board_id": "IRB-001",
                "trial_id": EYLEA_TRIAL,
                "review_period_start": now - timedelta(days=365),
                "review_period_end": now - timedelta(days=5),
                "enrollment_since_last_review": 45,
                "total_enrolled": 120,
                "adverse_events_count": 8,
                "protocol_deviations_count": 3,
                "amendments_since_last": 1,
                "risk_assessment": "Risk remains acceptable. No unexpected safety signals identified. Enrollment on track.",
                "submitted_date": now - timedelta(days=5),
                "status": ReviewStatus.SUBMITTED,
                "next_review_date": now + timedelta(days=360),
            },
            {
                "id": "CR-002",
                "submission_id": "SUB-003",
                "board_id": "IRB-002",
                "trial_id": DUPIXENT_TRIAL,
                "review_period_start": now - timedelta(days=180),
                "review_period_end": now - timedelta(days=30),
                "enrollment_since_last_review": 32,
                "total_enrolled": 85,
                "adverse_events_count": 12,
                "protocol_deviations_count": 5,
                "amendments_since_last": 0,
                "risk_assessment": "Moderate risk. Elevated AE rate at two sites requires monitoring.",
                "submitted_date": now - timedelta(days=30),
                "status": ReviewStatus.UNDER_REVIEW,
                "next_review_date": now + timedelta(days=150),
            },
            {
                "id": "CR-003",
                "submission_id": "SUB-005",
                "board_id": "IRB-003",
                "trial_id": LIBTAYO_TRIAL,
                "review_period_start": now - timedelta(days=90),
                "review_period_end": now - timedelta(days=1),
                "enrollment_since_last_review": 18,
                "total_enrolled": 42,
                "adverse_events_count": 4,
                "protocol_deviations_count": 1,
                "amendments_since_last": 0,
                "risk_assessment": "Low risk. Trial proceeding as expected with good safety profile.",
                "submitted_date": None,
                "status": ReviewStatus.DRAFT,
                "next_review_date": now + timedelta(days=90),
            },
        ]

        for cr in cr_data:
            self._continuing_reviews[cr["id"]] = ContinuingReview(**cr)

        # --- 3 Reportable Events ---
        events_data = [
            {
                "id": "RE-001",
                "board_id": "IRB-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-105",
                "event_type": "Serious Adverse Event",
                "event_description": "Patient experienced severe hypotension requiring hospitalization 48 hours post-injection.",
                "event_date": now - timedelta(days=20),
                "reported_date": now - timedelta(days=18),
                "severity": EventSeverity.HIGH,
                "requires_immediate_report": True,
                "report_deadline": now - timedelta(days=17),
                "status": EventStatus.UNDER_REVIEW,
                "board_response": None,
                "resolution": None,
            },
            {
                "id": "RE-002",
                "board_id": "IRB-002",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "event_type": "Protocol Deviation",
                "event_description": "Subject enrolled who did not meet inclusion criterion #5 (age requirement).",
                "event_date": now - timedelta(days=45),
                "reported_date": now - timedelta(days=40),
                "severity": EventSeverity.MEDIUM,
                "requires_immediate_report": False,
                "report_deadline": now - timedelta(days=30),
                "status": EventStatus.ACKNOWLEDGED,
                "board_response": "Acknowledged. Subject to remain in study with additional monitoring.",
                "resolution": None,
            },
            {
                "id": "RE-003",
                "board_id": "IRB-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "event_type": "Unanticipated Problem",
                "event_description": "Unexpected increase in injection site reactions exceeding protocol threshold.",
                "event_date": now - timedelta(days=10),
                "reported_date": None,
                "severity": EventSeverity.MEDIUM,
                "requires_immediate_report": False,
                "report_deadline": now + timedelta(days=5),
                "status": EventStatus.DRAFT,
                "board_response": None,
                "resolution": None,
            },
        ]

        for e in events_data:
            self._reportable_events[e["id"]] = ReportableEvent(**e)

        # --- 5 Regulatory Documents ---
        docs_data = [
            {
                "id": "DOC-001",
                "submission_id": "SUB-001",
                "trial_id": EYLEA_TRIAL,
                "document_type": DocumentType.PROTOCOL,
                "document_name": "EYLEA Phase III Protocol v1.0",
                "version": "1.0",
                "effective_date": now - timedelta(days=180),
                "expiry_date": None,
                "file_reference": "/documents/eylea/protocol_v1.0.pdf",
                "uploaded_by": "Dr. Sarah Chen",
                "uploaded_date": now - timedelta(days=185),
                "status": DocumentStatus.SUPERSEDED,
            },
            {
                "id": "DOC-002",
                "submission_id": "SUB-002",
                "trial_id": EYLEA_TRIAL,
                "document_type": DocumentType.PROTOCOL,
                "document_name": "EYLEA Phase III Protocol v2.0",
                "version": "2.0",
                "effective_date": now - timedelta(days=75),
                "expiry_date": None,
                "file_reference": "/documents/eylea/protocol_v2.0.pdf",
                "uploaded_by": "Dr. Sarah Chen",
                "uploaded_date": now - timedelta(days=92),
                "status": DocumentStatus.APPROVED,
            },
            {
                "id": "DOC-003",
                "submission_id": "SUB-002",
                "trial_id": EYLEA_TRIAL,
                "document_type": DocumentType.ICF,
                "document_name": "EYLEA Informed Consent Form v2.1",
                "version": "2.1",
                "effective_date": now - timedelta(days=70),
                "expiry_date": now + timedelta(days=295),
                "file_reference": "/documents/eylea/icf_v2.1.pdf",
                "uploaded_by": "Dr. Sarah Chen",
                "uploaded_date": now - timedelta(days=88),
                "status": DocumentStatus.APPROVED,
            },
            {
                "id": "DOC-004",
                "submission_id": "SUB-003",
                "trial_id": DUPIXENT_TRIAL,
                "document_type": DocumentType.INVESTIGATOR_BROCHURE,
                "document_name": "Dupixent Investigator Brochure Edition 8",
                "version": "8.0",
                "effective_date": now - timedelta(days=100),
                "expiry_date": None,
                "file_reference": "/documents/dupixent/ib_ed8.pdf",
                "uploaded_by": "Dr. James Rodriguez",
                "uploaded_date": now - timedelta(days=125),
                "status": DocumentStatus.APPROVED,
            },
            {
                "id": "DOC-005",
                "submission_id": "SUB-006",
                "trial_id": EYLEA_TRIAL,
                "document_type": DocumentType.SAFETY_REPORT,
                "document_name": "SAE Report - SITE-105 Hypotension Event",
                "version": "1.0",
                "effective_date": None,
                "expiry_date": None,
                "file_reference": "/documents/eylea/sae_report_site105.pdf",
                "uploaded_by": "Dr. Michael Park",
                "uploaded_date": now - timedelta(days=15),
                "status": DocumentStatus.SUBMITTED,
            },
        ]

        for d in docs_data:
            self._documents[d["id"]] = RegulatoryDocument(**d)

        # --- 4 Correspondence ---
        corr_data = [
            {
                "id": "CORR-001",
                "submission_id": "SUB-002",
                "direction": CorrespondenceDirection.INCOMING,
                "subject": "Conditional Approval - WCG-2025-002",
                "content": "Your amendment submission has been conditionally approved. Please update the ICF to include new safety information and resubmit within 30 days.",
                "sent_date": now - timedelta(days=75),
                "sent_by": "WCG IRB Review Committee",
                "response_required": True,
                "response_deadline": now - timedelta(days=45),
                "response_received_date": now - timedelta(days=50),
            },
            {
                "id": "CORR-002",
                "submission_id": "SUB-002",
                "direction": CorrespondenceDirection.OUTGOING,
                "subject": "Re: Conditional Approval - Updated ICF Submitted",
                "content": "Please find attached the updated ICF v2.1 incorporating the requested safety information changes.",
                "sent_date": now - timedelta(days=50),
                "sent_by": "Dr. Sarah Chen",
                "response_required": False,
                "response_deadline": None,
                "response_received_date": None,
            },
            {
                "id": "CORR-003",
                "submission_id": "SUB-004",
                "direction": CorrespondenceDirection.OUTGOING,
                "subject": "Continuing Review Submission - ADV-2025-102",
                "content": "Submitting annual continuing review for the Dupixent trial. All required documents are attached.",
                "sent_date": now - timedelta(days=30),
                "sent_by": "Dr. James Rodriguez",
                "response_required": False,
                "response_deadline": None,
                "response_received_date": None,
            },
            {
                "id": "CORR-004",
                "submission_id": "SUB-006",
                "direction": CorrespondenceDirection.OUTGOING,
                "subject": "Safety Report - SAE at SITE-105",
                "content": "Reporting a serious adverse event (severe hypotension) at SITE-105. Full details and supporting documentation are included.",
                "sent_date": now - timedelta(days=15),
                "sent_by": "Dr. Michael Park",
                "response_required": True,
                "response_deadline": now + timedelta(days=15),
                "response_received_date": None,
            },
        ]

        for c in corr_data:
            self._correspondence[c["id"]] = IRBCorrespondence(**c)

    # ------------------------------------------------------------------
    # Board Management
    # ------------------------------------------------------------------

    def list_boards(
        self,
        *,
        board_type: BoardType | None = None,
        active: bool | None = None,
    ) -> list[IRBBoard]:
        """List boards with optional filters."""
        with self._lock:
            result = list(self._boards.values())

        if board_type is not None:
            result = [b for b in result if b.board_type == board_type]
        if active is not None:
            result = [b for b in result if b.active == active]

        return sorted(result, key=lambda b: b.name)

    def get_board(self, board_id: str) -> IRBBoard | None:
        """Get a single board by ID."""
        with self._lock:
            return self._boards.get(board_id)

    def create_board(self, payload: IRBBoardCreate) -> IRBBoard:
        """Create a new board."""
        board_id = f"IRB-{uuid4().hex[:8].upper()}"
        board = IRBBoard(id=board_id, **payload.model_dump())
        with self._lock:
            self._boards[board_id] = board
        logger.info("Created board %s: %s", board_id, payload.name)
        return board

    def update_board(self, board_id: str, payload: IRBBoardUpdate) -> IRBBoard | None:
        """Update an existing board."""
        with self._lock:
            existing = self._boards.get(board_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = IRBBoard(**data)
            self._boards[board_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Submission Management
    # ------------------------------------------------------------------

    def list_submissions(
        self,
        *,
        board_id: str | None = None,
        trial_id: str | None = None,
        status: ReviewStatus | None = None,
        submission_type: SubmissionType | None = None,
    ) -> list[IRBSubmission]:
        """List submissions with optional filters."""
        with self._lock:
            result = list(self._submissions.values())

        if board_id is not None:
            result = [s for s in result if s.board_id == board_id]
        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if status is not None:
            result = [s for s in result if s.status == status]
        if submission_type is not None:
            result = [s for s in result if s.submission_type == submission_type]

        return sorted(result, key=lambda s: s.submission_number)

    def get_submission(self, submission_id: str) -> IRBSubmission | None:
        """Get a single submission by ID."""
        with self._lock:
            return self._submissions.get(submission_id)

    def create_submission(self, payload: IRBSubmissionCreate) -> IRBSubmission:
        """Create a new submission."""
        sub_id = f"SUB-{uuid4().hex[:8].upper()}"
        submission = IRBSubmission(
            id=sub_id,
            status=ReviewStatus.DRAFT,
            **payload.model_dump(),
        )
        with self._lock:
            self._submissions[sub_id] = submission
        logger.info("Created submission %s: %s", sub_id, payload.submission_number)
        return submission

    def update_submission(
        self, submission_id: str, payload: IRBSubmissionUpdate
    ) -> IRBSubmission | None:
        """Update an existing submission."""
        with self._lock:
            existing = self._submissions.get(submission_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = IRBSubmission(**data)
            self._submissions[submission_id] = updated
        return updated

    def submit_for_review(
        self, submission_id: str, payload: SubmissionSubmitRequest
    ) -> IRBSubmission | None:
        """Transition a submission from draft to submitted."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._submissions.get(submission_id)
            if existing is None:
                return None

            if existing.status != ReviewStatus.DRAFT:
                raise ValueError(
                    f"Submission '{submission_id}' is in status '{existing.status.value}', "
                    "only 'draft' submissions can be submitted."
                )

            data = existing.model_dump()
            data["status"] = ReviewStatus.SUBMITTED
            data["submitted_date"] = payload.submitted_date or now
            updated = IRBSubmission(**data)
            self._submissions[submission_id] = updated

        logger.info("Submitted %s for review", submission_id)
        return updated

    def record_outcome(
        self, submission_id: str, payload: RecordOutcomeRequest
    ) -> IRBSubmission | None:
        """Record the board's review outcome for a submission."""
        with self._lock:
            existing = self._submissions.get(submission_id)
            if existing is None:
                return None

            if existing.status not in (
                ReviewStatus.SUBMITTED,
                ReviewStatus.UNDER_REVIEW,
            ):
                raise ValueError(
                    f"Submission '{submission_id}' is in status '{existing.status.value}', "
                    "outcome can only be recorded for 'submitted' or 'under_review' submissions."
                )

            data = existing.model_dump()
            data["outcome"] = payload.outcome
            data["review_date"] = payload.review_date
            data["notes"] = payload.notes if payload.notes else existing.notes

            # Map outcome to status
            if payload.outcome == ReviewOutcome.APPROVED:
                data["status"] = ReviewStatus.APPROVED
                data["approval_date"] = payload.approval_date or payload.review_date
                data["expiry_date"] = payload.expiry_date
            elif payload.outcome == ReviewOutcome.CONDITIONALLY_APPROVED:
                data["status"] = ReviewStatus.APPROVED_WITH_CONDITIONS
                data["approval_date"] = payload.approval_date or payload.review_date
                data["expiry_date"] = payload.expiry_date
                data["conditions"] = payload.conditions
            elif payload.outcome == ReviewOutcome.DEFERRED:
                data["status"] = ReviewStatus.DEFERRED
            elif payload.outcome == ReviewOutcome.TABLED:
                data["status"] = ReviewStatus.DEFERRED
            elif payload.outcome == ReviewOutcome.DISAPPROVED:
                data["status"] = ReviewStatus.DISAPPROVED

            updated = IRBSubmission(**data)
            self._submissions[submission_id] = updated

        logger.info(
            "Recorded outcome %s for submission %s",
            payload.outcome.value,
            submission_id,
        )
        return updated

    # ------------------------------------------------------------------
    # Continuing Reviews
    # ------------------------------------------------------------------

    def list_continuing_reviews(
        self,
        *,
        submission_id: str | None = None,
        board_id: str | None = None,
        trial_id: str | None = None,
        status: ReviewStatus | None = None,
    ) -> list[ContinuingReview]:
        """List continuing reviews with optional filters."""
        with self._lock:
            result = list(self._continuing_reviews.values())

        if submission_id is not None:
            result = [cr for cr in result if cr.submission_id == submission_id]
        if board_id is not None:
            result = [cr for cr in result if cr.board_id == board_id]
        if trial_id is not None:
            result = [cr for cr in result if cr.trial_id == trial_id]
        if status is not None:
            result = [cr for cr in result if cr.status == status]

        return sorted(result, key=lambda cr: cr.review_period_end, reverse=True)

    def get_continuing_review(self, review_id: str) -> ContinuingReview | None:
        """Get a single continuing review by ID."""
        with self._lock:
            return self._continuing_reviews.get(review_id)

    def create_continuing_review(
        self, submission_id: str, payload: ContinuingReviewCreate
    ) -> ContinuingReview:
        """Create a new continuing review for a submission."""
        cr_id = f"CR-{uuid4().hex[:8].upper()}"
        cr = ContinuingReview(
            id=cr_id,
            submission_id=submission_id,
            status=ReviewStatus.DRAFT,
            **payload.model_dump(),
        )
        with self._lock:
            self._continuing_reviews[cr_id] = cr
        logger.info("Created continuing review %s for submission %s", cr_id, submission_id)
        return cr

    def update_continuing_review(
        self, review_id: str, payload: ContinuingReviewUpdate
    ) -> ContinuingReview | None:
        """Update a continuing review."""
        with self._lock:
            existing = self._continuing_reviews.get(review_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ContinuingReview(**data)
            self._continuing_reviews[review_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Reportable Events
    # ------------------------------------------------------------------

    def list_reportable_events(
        self,
        *,
        board_id: str | None = None,
        trial_id: str | None = None,
        status: EventStatus | None = None,
        severity: EventSeverity | None = None,
    ) -> list[ReportableEvent]:
        """List reportable events with optional filters."""
        with self._lock:
            result = list(self._reportable_events.values())

        if board_id is not None:
            result = [e for e in result if e.board_id == board_id]
        if trial_id is not None:
            result = [e for e in result if e.trial_id == trial_id]
        if status is not None:
            result = [e for e in result if e.status == status]
        if severity is not None:
            result = [e for e in result if e.severity == severity]

        return sorted(result, key=lambda e: e.event_date, reverse=True)

    def get_reportable_event(self, event_id: str) -> ReportableEvent | None:
        """Get a single reportable event by ID."""
        with self._lock:
            return self._reportable_events.get(event_id)

    def file_reportable_event(self, payload: ReportableEventCreate) -> ReportableEvent:
        """File a new reportable event."""
        event_id = f"RE-{uuid4().hex[:8].upper()}"
        event = ReportableEvent(
            id=event_id,
            status=EventStatus.DRAFT,
            **payload.model_dump(),
        )
        with self._lock:
            self._reportable_events[event_id] = event
        logger.info("Filed reportable event %s: %s", event_id, payload.event_type)
        return event

    def update_reportable_event(
        self, event_id: str, payload: ReportableEventUpdate
    ) -> ReportableEvent | None:
        """Update a reportable event."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._reportable_events.get(event_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set reported_date when transitioning to submitted
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = EventStatus(new_status)
                if new_status == EventStatus.SUBMITTED and existing.status == EventStatus.DRAFT:
                    data["reported_date"] = now

            data.update(updates)
            updated = ReportableEvent(**data)
            self._reportable_events[event_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Regulatory Documents
    # ------------------------------------------------------------------

    def list_documents(
        self,
        *,
        submission_id: str | None = None,
        trial_id: str | None = None,
        document_type: DocumentType | None = None,
        status: DocumentStatus | None = None,
    ) -> list[RegulatoryDocument]:
        """List regulatory documents with optional filters."""
        with self._lock:
            result = list(self._documents.values())

        if submission_id is not None:
            result = [d for d in result if d.submission_id == submission_id]
        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]
        if document_type is not None:
            result = [d for d in result if d.document_type == document_type]
        if status is not None:
            result = [d for d in result if d.status == status]

        return sorted(result, key=lambda d: d.uploaded_date, reverse=True)

    def get_document(self, document_id: str) -> RegulatoryDocument | None:
        """Get a single regulatory document by ID."""
        with self._lock:
            return self._documents.get(document_id)

    def create_document(
        self, submission_id: str, payload: RegulatoryDocumentCreate
    ) -> RegulatoryDocument:
        """Create a regulatory document for a submission."""
        now = datetime.now(timezone.utc)
        doc_id = f"DOC-{uuid4().hex[:8].upper()}"
        doc = RegulatoryDocument(
            id=doc_id,
            submission_id=submission_id,
            uploaded_date=now,
            status=DocumentStatus.DRAFT,
            **payload.model_dump(),
        )
        with self._lock:
            self._documents[doc_id] = doc
        logger.info("Created document %s: %s", doc_id, payload.document_name)
        return doc

    # ------------------------------------------------------------------
    # Correspondence
    # ------------------------------------------------------------------

    def list_correspondence(
        self,
        *,
        submission_id: str | None = None,
        direction: CorrespondenceDirection | None = None,
    ) -> list[IRBCorrespondence]:
        """List correspondence with optional filters."""
        with self._lock:
            result = list(self._correspondence.values())

        if submission_id is not None:
            result = [c for c in result if c.submission_id == submission_id]
        if direction is not None:
            result = [c for c in result if c.direction == direction]

        return sorted(result, key=lambda c: c.sent_date, reverse=True)

    def get_correspondence(self, correspondence_id: str) -> IRBCorrespondence | None:
        """Get a single correspondence record by ID."""
        with self._lock:
            return self._correspondence.get(correspondence_id)

    def create_correspondence(
        self, submission_id: str, payload: IRBCorrespondenceCreate
    ) -> IRBCorrespondence:
        """Create a correspondence record for a submission."""
        now = datetime.now(timezone.utc)
        corr_id = f"CORR-{uuid4().hex[:8].upper()}"
        corr = IRBCorrespondence(
            id=corr_id,
            submission_id=submission_id,
            sent_date=now,
            **payload.model_dump(),
        )
        with self._lock:
            self._correspondence[corr_id] = corr
        logger.info("Created correspondence %s for submission %s", corr_id, submission_id)
        return corr

    # ------------------------------------------------------------------
    # Expiring Approvals
    # ------------------------------------------------------------------

    def get_expiring_approvals(
        self, days: int = 30
    ) -> list[IRBSubmission]:
        """Get submissions with approvals expiring within the specified number of days."""
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days)

        with self._lock:
            result = [
                s
                for s in self._submissions.values()
                if s.status in (ReviewStatus.APPROVED, ReviewStatus.APPROVED_WITH_CONDITIONS)
                and s.expiry_date is not None
                and s.expiry_date <= cutoff
            ]

        return sorted(result, key=lambda s: s.expiry_date or now)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> IRBMetrics:
        """Compute aggregated IRB/EC operational metrics."""
        now = datetime.now(timezone.utc)
        cutoff_30d = now + timedelta(days=30)

        with self._lock:
            submissions = list(self._submissions.values())
            continuing_reviews = list(self._continuing_reviews.values())
            reportable_events = list(self._reportable_events.values())

        total_submissions = len(submissions)

        pending_reviews = sum(
            1
            for s in submissions
            if s.status in (ReviewStatus.SUBMITTED, ReviewStatus.UNDER_REVIEW)
        )

        approved_count = sum(
            1
            for s in submissions
            if s.status in (ReviewStatus.APPROVED, ReviewStatus.APPROVED_WITH_CONDITIONS)
        )

        # Average review days for submissions that have both submitted_date and review_date
        review_durations: list[float] = []
        for s in submissions:
            if s.submitted_date and s.review_date:
                delta = (s.review_date - s.submitted_date).total_seconds() / 86400
                review_durations.append(delta)
        avg_review_days = (
            round(sum(review_durations) / len(review_durations), 1)
            if review_durations
            else 0.0
        )

        expiring_approvals_30d = sum(
            1
            for s in submissions
            if s.status in (ReviewStatus.APPROVED, ReviewStatus.APPROVED_WITH_CONDITIONS)
            and s.expiry_date is not None
            and s.expiry_date <= cutoff_30d
        )

        overdue_continuing_reviews = sum(
            1
            for cr in continuing_reviews
            if cr.status in (ReviewStatus.DRAFT, ReviewStatus.SUBMITTED)
            and cr.next_review_date is not None
            and cr.next_review_date < now
        )

        reportable_events_open = sum(
            1
            for e in reportable_events
            if e.status in (EventStatus.DRAFT, EventStatus.SUBMITTED, EventStatus.UNDER_REVIEW)
        )

        return IRBMetrics(
            total_submissions=total_submissions,
            pending_reviews=pending_reviews,
            approved_count=approved_count,
            avg_review_days=avg_review_days,
            expiring_approvals_30d=expiring_approvals_30d,
            overdue_continuing_reviews=overdue_continuing_reviews,
            reportable_events_open=reportable_events_open,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: CentralIRBService | None = None
_lock = threading.Lock()


def get_central_irb_service() -> CentralIRBService:
    """Return the singleton CentralIRBService instance."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = CentralIRBService()
    return _instance


def reset_central_irb_service() -> CentralIRBService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _lock:
        _instance = CentralIRBService()
    return _instance
