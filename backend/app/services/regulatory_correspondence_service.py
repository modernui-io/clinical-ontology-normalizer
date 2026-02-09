"""Regulatory Correspondence Tracking Service (CLO-7).

Manages regulatory correspondence, action items, timelines, agency contacts,
deadline reports, metrics, and relationship summaries for clinical trial programs.

Usage:
    from app.services.regulatory_correspondence_service import (
        get_regulatory_correspondence_service,
    )

    svc = get_regulatory_correspondence_service()
    corr = svc.create_correspondence(...)
    report = svc.get_deadline_report(days_ahead=30)
"""

from __future__ import annotations

import logging
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.regulatory_correspondence import (
    ActionItem,
    ActionItemCreate,
    ActionItemUpdate,
    AgencyContact,
    AgencyContactCreate,
    AgencyContactUpdate,
    AgencyRelationshipSummary,
    Correspondence,
    CorrespondenceCreate,
    CorrespondenceMetrics,
    CorrespondenceStatus,
    CorrespondenceType,
    CorrespondenceUpdate,
    DeadlineEntry,
    DeadlineReport,
    LinkCorrespondenceRequest,
    MilestoneCreate,
    MilestoneUpdate,
    Priority,
    RegulatoryAgency,
    RegulatoryTimeline,
    ResponseDeadline,
    TimelineCreate,
    TimelineMilestone,
    TimelineUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid status transitions
# ---------------------------------------------------------------------------

VALID_STATUS_TRANSITIONS: dict[CorrespondenceStatus, set[CorrespondenceStatus]] = {
    CorrespondenceStatus.DRAFT: {
        CorrespondenceStatus.UNDER_REVIEW,
        CorrespondenceStatus.SUBMITTED,
        CorrespondenceStatus.WITHDRAWN,
    },
    CorrespondenceStatus.UNDER_REVIEW: {
        CorrespondenceStatus.DRAFT,
        CorrespondenceStatus.SUBMITTED,
        CorrespondenceStatus.WITHDRAWN,
    },
    CorrespondenceStatus.SUBMITTED: {
        CorrespondenceStatus.ACKNOWLEDGED,
        CorrespondenceStatus.RESPONSE_RECEIVED,
        CorrespondenceStatus.WITHDRAWN,
    },
    CorrespondenceStatus.ACKNOWLEDGED: {
        CorrespondenceStatus.RESPONSE_RECEIVED,
        CorrespondenceStatus.FOLLOW_UP_REQUIRED,
        CorrespondenceStatus.CLOSED,
    },
    CorrespondenceStatus.RESPONSE_RECEIVED: {
        CorrespondenceStatus.FOLLOW_UP_REQUIRED,
        CorrespondenceStatus.CLOSED,
    },
    CorrespondenceStatus.FOLLOW_UP_REQUIRED: {
        CorrespondenceStatus.SUBMITTED,
        CorrespondenceStatus.CLOSED,
    },
    CorrespondenceStatus.CLOSED: set(),  # terminal
    CorrespondenceStatus.WITHDRAWN: set(),  # terminal
}

# Deadline day mapping
DEADLINE_DAYS: dict[ResponseDeadline, int | None] = {
    ResponseDeadline.DAYS_15: 15,
    ResponseDeadline.DAYS_30: 30,
    ResponseDeadline.DAYS_60: 60,
    ResponseDeadline.DAYS_90: 90,
    ResponseDeadline.DAYS_120: 120,
    ResponseDeadline.CALENDAR_DRIVEN: None,
    ResponseDeadline.NONE: None,
}


def _compute_deadline_date(
    submission_date: datetime | None,
    deadline: ResponseDeadline,
) -> datetime | None:
    """Compute the response deadline date from submission date and category."""
    if submission_date is None:
        return None
    days = DEADLINE_DAYS.get(deadline)
    if days is None:
        return None
    return submission_date + timedelta(days=days)


class RegulatoryCorrespondenceService:
    """In-memory regulatory correspondence management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._correspondence: dict[str, Correspondence] = {}
        self._action_items: dict[str, ActionItem] = {}
        self._timelines: dict[str, RegulatoryTimeline] = {}
        self._contacts: dict[str, AgencyContact] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic regulatory correspondence for Regeneron trials."""
        now = datetime.now(timezone.utc)

        # Stable trial IDs matching trial_eligibility_service
        eylea_id = "00000000-de00-0001-0000-000000000001"
        dupixent_id = "00000000-de00-0002-0000-000000000002"
        libtayo_id = "00000000-de00-0003-0000-000000000003"

        eylea_name = "EYLEA HD Phase 3 DME Trial"
        dupixent_name = "DUPIXENT Atopic Dermatitis Phase 3"
        libtayo_name = "LIBTAYO NSCLC First-Line Phase 3"

        # ---------------------------------------------------------------
        # 10 Correspondence records
        # ---------------------------------------------------------------
        seed_correspondence: list[dict] = [
            # 1. FDA Pre-IND Meeting (EYLEA)
            {
                "id": "CORR-001",
                "title": "Pre-IND Meeting Request - EYLEA HD DME Extension",
                "correspondence_type": CorrespondenceType.PRE_IND_MEETING,
                "agency": RegulatoryAgency.FDA,
                "status": CorrespondenceStatus.CLOSED,
                "priority": Priority.HIGH,
                "trial_id": eylea_id,
                "trial_name": eylea_name,
                "description": "Pre-IND meeting to discuss Phase 3 DME extension study design with CDER.",
                "submission_date": now - timedelta(days=120),
                "response_deadline": ResponseDeadline.DAYS_60,
                "response_deadline_date": now - timedelta(days=60),
                "response_received_date": now - timedelta(days=75),
                "assigned_to": "Dr. Sarah Chen",
                "reviewer": "Dr. Michael Torres",
                "attachments_count": 3,
                "tags": ["pre-ind", "dme", "cder"],
                "key_points": [
                    "FDA agreed to primary endpoint design",
                    "Requested additional PK data in elderly population",
                ],
                "action_items": ["Submit PK bridging study protocol"],
            },
            # 2. FDA Complete Response Letter (EYLEA)
            {
                "id": "CORR-002",
                "title": "Complete Response Letter - EYLEA HD sBLA",
                "correspondence_type": CorrespondenceType.COMPLETE_RESPONSE_LETTER,
                "agency": RegulatoryAgency.FDA,
                "status": CorrespondenceStatus.FOLLOW_UP_REQUIRED,
                "priority": Priority.URGENT,
                "trial_id": eylea_id,
                "trial_name": eylea_name,
                "description": "CRL received requesting additional CMC data for manufacturing process.",
                "submission_date": now - timedelta(days=90),
                "response_deadline": ResponseDeadline.DAYS_90,
                "response_deadline_date": now + timedelta(days=5),
                "response_received_date": now - timedelta(days=5),
                "assigned_to": "Dr. James Wilson",
                "reviewer": "Dr. Sarah Chen",
                "attachments_count": 5,
                "tags": ["crl", "cmc", "manufacturing"],
                "key_points": [
                    "CMC deficiency noted in Section 3.2.S.2",
                    "Additional stability data required",
                ],
                "action_items": [
                    "Prepare CMC amendment",
                    "Submit 6-month stability data",
                ],
            },
            # 3. FDA Form 483 (DUPIXENT)
            {
                "id": "CORR-003",
                "title": "Form 483 Observations - Dupixent Manufacturing Facility",
                "correspondence_type": CorrespondenceType.FORM_483,
                "agency": RegulatoryAgency.FDA,
                "status": CorrespondenceStatus.RESPONSE_RECEIVED,
                "priority": Priority.URGENT,
                "trial_id": dupixent_id,
                "trial_name": dupixent_name,
                "description": "Three observations from FDA inspection of Limerick facility.",
                "submission_date": now - timedelta(days=45),
                "response_deadline": ResponseDeadline.DAYS_15,
                "response_deadline_date": now - timedelta(days=30),
                "response_received_date": now - timedelta(days=32),
                "assigned_to": "Dr. Emily Park",
                "reviewer": "Dr. Robert Kim",
                "attachments_count": 2,
                "tags": ["483", "gmp", "manufacturing"],
                "key_points": [
                    "Observation 1: Data integrity in LIMS",
                    "Observation 2: Equipment cleaning validation",
                    "Observation 3: Environmental monitoring gaps",
                ],
                "action_items": [
                    "Remediate LIMS data integrity",
                    "Update cleaning validation SOPs",
                ],
            },
            # 4. EMA Type B Meeting (DUPIXENT)
            {
                "id": "CORR-004",
                "title": "Scientific Advice Meeting - Dupixent Pediatric Extension",
                "correspondence_type": CorrespondenceType.TYPE_B_MEETING,
                "agency": RegulatoryAgency.EMA,
                "status": CorrespondenceStatus.ACKNOWLEDGED,
                "priority": Priority.HIGH,
                "trial_id": dupixent_id,
                "trial_name": dupixent_name,
                "description": "CHMP scientific advice on pediatric indication extension.",
                "submission_date": now - timedelta(days=30),
                "response_deadline": ResponseDeadline.DAYS_90,
                "response_deadline_date": now + timedelta(days=60),
                "assigned_to": "Dr. Anna Mueller",
                "reviewer": "Dr. Emily Park",
                "attachments_count": 4,
                "tags": ["scientific-advice", "pediatric", "chmp"],
                "key_points": ["Pediatric study design discussed", "PIP update required"],
                "action_items": ["Submit updated PIP"],
            },
            # 5. MHRA Information Request (LIBTAYO)
            {
                "id": "CORR-005",
                "title": "MHRA Information Request - LIBTAYO Post-Brexit Registration",
                "correspondence_type": CorrespondenceType.INFORMATION_REQUEST,
                "agency": RegulatoryAgency.MHRA,
                "status": CorrespondenceStatus.SUBMITTED,
                "priority": Priority.NORMAL,
                "trial_id": libtayo_id,
                "trial_name": libtayo_name,
                "description": "MHRA requesting additional safety data for UK marketing authorization.",
                "submission_date": now - timedelta(days=20),
                "response_deadline": ResponseDeadline.DAYS_30,
                "response_deadline_date": now + timedelta(days=10),
                "assigned_to": "Dr. William Hayes",
                "reviewer": "Dr. Michael Torres",
                "attachments_count": 2,
                "tags": ["mhra", "safety-data", "post-brexit"],
                "key_points": ["Safety data gaps identified in UK-specific population"],
                "action_items": ["Compile UK-specific PSUR supplement"],
            },
            # 6. FDA IND Safety Report (LIBTAYO)
            {
                "id": "CORR-006",
                "title": "IND Safety Report - LIBTAYO Serious AE Notification",
                "correspondence_type": CorrespondenceType.IND_SAFETY_REPORT,
                "agency": RegulatoryAgency.FDA,
                "status": CorrespondenceStatus.SUBMITTED,
                "priority": Priority.URGENT,
                "trial_id": libtayo_id,
                "trial_name": libtayo_name,
                "description": "15-day safety report for unexpected serious adverse event.",
                "submission_date": now - timedelta(days=3),
                "response_deadline": ResponseDeadline.DAYS_15,
                "response_deadline_date": now + timedelta(days=12),
                "assigned_to": "Dr. Sarah Chen",
                "reviewer": "Dr. Robert Kim",
                "attachments_count": 1,
                "tags": ["ind-safety", "serious-ae", "15-day"],
                "key_points": [
                    "Grade 4 hepatotoxicity in patient 1042",
                    "Possibly related to study drug",
                ],
                "action_items": [
                    "Follow up with investigator site",
                    "Update IB safety section",
                ],
            },
            # 7. FDA Annual Report (EYLEA)
            {
                "id": "CORR-007",
                "title": "IND Annual Report - EYLEA HD Year 2",
                "correspondence_type": CorrespondenceType.ANNUAL_REPORT,
                "agency": RegulatoryAgency.FDA,
                "status": CorrespondenceStatus.DRAFT,
                "priority": Priority.NORMAL,
                "trial_id": eylea_id,
                "trial_name": eylea_name,
                "description": "Year 2 annual report summarizing study progress, safety, and protocol amendments.",
                "response_deadline": ResponseDeadline.DAYS_60,
                "assigned_to": "Dr. James Wilson",
                "reviewer": "Dr. Sarah Chen",
                "attachments_count": 0,
                "tags": ["annual-report", "ind"],
                "key_points": [],
                "action_items": ["Complete enrollment summary", "Compile safety tables"],
            },
            # 8. EMA Protocol Amendment (LIBTAYO)
            {
                "id": "CORR-008",
                "title": "Protocol Amendment Notification - LIBTAYO Combination Arm",
                "correspondence_type": CorrespondenceType.PROTOCOL_AMENDMENT,
                "agency": RegulatoryAgency.EMA,
                "status": CorrespondenceStatus.UNDER_REVIEW,
                "priority": Priority.HIGH,
                "trial_id": libtayo_id,
                "trial_name": libtayo_name,
                "description": "Substantial amendment to add pembrolizumab combination arm per DSMB recommendation.",
                "response_deadline": ResponseDeadline.DAYS_30,
                "assigned_to": "Dr. Anna Mueller",
                "reviewer": "Dr. William Hayes",
                "attachments_count": 3,
                "tags": ["protocol-amendment", "combination", "dsmb"],
                "key_points": ["DSMB recommended additional combination arm"],
                "action_items": [
                    "Finalize amended protocol",
                    "Update IMPD",
                    "Notify ethics committees",
                ],
            },
            # 9. FDA DMCR Report (DUPIXENT)
            {
                "id": "CORR-009",
                "title": "DSMB Report Submission - Dupixent Interim Analysis",
                "correspondence_type": CorrespondenceType.DMCR_REPORT,
                "agency": RegulatoryAgency.FDA,
                "status": CorrespondenceStatus.CLOSED,
                "priority": Priority.NORMAL,
                "trial_id": dupixent_id,
                "trial_name": dupixent_name,
                "description": "Interim analysis DSMB report recommending continuation without modification.",
                "submission_date": now - timedelta(days=60),
                "response_deadline": ResponseDeadline.NONE,
                "response_received_date": now - timedelta(days=50),
                "assigned_to": "Dr. Emily Park",
                "reviewer": "Dr. Robert Kim",
                "attachments_count": 2,
                "tags": ["dsmb", "interim-analysis"],
                "key_points": [
                    "DSMB recommended continuation",
                    "No safety concerns",
                    "Futility boundary not crossed",
                ],
                "action_items": [],
            },
            # 10. FDA Advisory Committee (EYLEA)
            {
                "id": "CORR-010",
                "title": "Advisory Committee Preparation - EYLEA HD BLA",
                "correspondence_type": CorrespondenceType.ADVISORY_COMMITTEE,
                "agency": RegulatoryAgency.FDA,
                "status": CorrespondenceStatus.DRAFT,
                "priority": Priority.HIGH,
                "trial_id": eylea_id,
                "trial_name": eylea_name,
                "description": "Preparation materials for upcoming DERP advisory committee meeting.",
                "response_deadline": ResponseDeadline.DAYS_120,
                "assigned_to": "Dr. Sarah Chen",
                "reviewer": "Dr. Michael Torres",
                "attachments_count": 0,
                "tags": ["advisory-committee", "derp", "bla"],
                "key_points": [],
                "action_items": [
                    "Draft briefing document",
                    "Prepare presentation slides",
                    "Identify KOL panelists",
                ],
            },
        ]

        for data in seed_correspondence:
            corr_id = data["id"]
            data.setdefault("created_at", now - timedelta(days=150))
            data.setdefault("updated_at", now)
            data.setdefault("related_correspondence_ids", [])
            self._correspondence[corr_id] = Correspondence(**data)

        # Link some correspondence
        self._correspondence["CORR-001"].related_correspondence_ids.append("CORR-002")
        self._correspondence["CORR-002"].related_correspondence_ids.append("CORR-001")

        # ---------------------------------------------------------------
        # 15 Action items
        # ---------------------------------------------------------------
        seed_actions: list[dict] = [
            # CORR-001 actions
            {"id": "AI-001", "correspondence_id": "CORR-001", "description": "Submit PK bridging study protocol", "assigned_to": "Dr. Sarah Chen", "due_date": now - timedelta(days=30), "completed": True, "completed_date": now - timedelta(days=35), "priority": Priority.HIGH},
            {"id": "AI-002", "correspondence_id": "CORR-001", "description": "Compile elderly PK dataset from Phase 2", "assigned_to": "Dr. James Wilson", "due_date": now - timedelta(days=45), "completed": True, "completed_date": now - timedelta(days=40), "priority": Priority.NORMAL},
            # CORR-002 actions
            {"id": "AI-003", "correspondence_id": "CORR-002", "description": "Prepare CMC amendment package", "assigned_to": "Dr. James Wilson", "due_date": now + timedelta(days=3), "completed": False, "priority": Priority.URGENT},
            {"id": "AI-004", "correspondence_id": "CORR-002", "description": "Submit 6-month stability data", "assigned_to": "Dr. Emily Park", "due_date": now + timedelta(days=10), "completed": False, "priority": Priority.HIGH},
            # CORR-003 actions
            {"id": "AI-005", "correspondence_id": "CORR-003", "description": "Remediate LIMS data integrity findings", "assigned_to": "Dr. Emily Park", "due_date": now - timedelta(days=10), "completed": True, "completed_date": now - timedelta(days=12), "priority": Priority.URGENT},
            {"id": "AI-006", "correspondence_id": "CORR-003", "description": "Update cleaning validation SOPs", "assigned_to": "Dr. Robert Kim", "due_date": now + timedelta(days=5), "completed": False, "priority": Priority.HIGH},
            {"id": "AI-007", "correspondence_id": "CORR-003", "description": "Conduct environmental monitoring gap analysis", "assigned_to": "Dr. Emily Park", "due_date": now + timedelta(days=15), "completed": False, "priority": Priority.NORMAL},
            # CORR-004 actions
            {"id": "AI-008", "correspondence_id": "CORR-004", "description": "Submit updated Pediatric Investigation Plan", "assigned_to": "Dr. Anna Mueller", "due_date": now + timedelta(days=45), "completed": False, "priority": Priority.HIGH},
            # CORR-005 actions
            {"id": "AI-009", "correspondence_id": "CORR-005", "description": "Compile UK-specific PSUR supplement", "assigned_to": "Dr. William Hayes", "due_date": now + timedelta(days=8), "completed": False, "priority": Priority.NORMAL},
            # CORR-006 actions
            {"id": "AI-010", "correspondence_id": "CORR-006", "description": "Follow up with investigator site on SAE details", "assigned_to": "Dr. Sarah Chen", "due_date": now + timedelta(days=2), "completed": False, "priority": Priority.URGENT},
            {"id": "AI-011", "correspondence_id": "CORR-006", "description": "Update Investigator's Brochure safety section", "assigned_to": "Dr. Robert Kim", "due_date": now + timedelta(days=20), "completed": False, "priority": Priority.HIGH},
            # CORR-007 actions
            {"id": "AI-012", "correspondence_id": "CORR-007", "description": "Complete enrollment summary for annual report", "assigned_to": "Dr. James Wilson", "due_date": now + timedelta(days=30), "completed": False, "priority": Priority.NORMAL},
            {"id": "AI-013", "correspondence_id": "CORR-007", "description": "Compile safety tables for annual report", "assigned_to": "Dr. Sarah Chen", "due_date": now + timedelta(days=25), "completed": False, "priority": Priority.NORMAL},
            # CORR-008 actions
            {"id": "AI-014", "correspondence_id": "CORR-008", "description": "Finalize amended protocol document", "assigned_to": "Dr. Anna Mueller", "due_date": now + timedelta(days=14), "completed": False, "priority": Priority.HIGH},
            # CORR-010 actions
            {"id": "AI-015", "correspondence_id": "CORR-010", "description": "Draft advisory committee briefing document", "assigned_to": "Dr. Sarah Chen", "due_date": now + timedelta(days=60), "completed": False, "priority": Priority.HIGH},
        ]

        for data in seed_actions:
            ai_id = data["id"]
            data.setdefault("completed_date", None)
            self._action_items[ai_id] = ActionItem(**data)

        # ---------------------------------------------------------------
        # 3 Regulatory timelines (one per trial)
        # ---------------------------------------------------------------
        self._timelines["TL-001"] = RegulatoryTimeline(
            id="TL-001",
            trial_id=eylea_id,
            trial_name=eylea_name,
            milestones=[
                TimelineMilestone(name="Pre-IND Meeting", planned_date=now - timedelta(days=120), actual_date=now - timedelta(days=120), status="COMPLETED", correspondence_id="CORR-001"),
                TimelineMilestone(name="IND Submission", planned_date=now - timedelta(days=90), actual_date=now - timedelta(days=88), status="COMPLETED"),
                TimelineMilestone(name="First Patient Enrolled", planned_date=now - timedelta(days=30), actual_date=now - timedelta(days=28), status="COMPLETED"),
                TimelineMilestone(name="Interim Analysis", planned_date=now + timedelta(days=90), status="PENDING"),
                TimelineMilestone(name="BLA Submission", planned_date=now + timedelta(days=270), status="PENDING"),
                TimelineMilestone(name="Advisory Committee", planned_date=now + timedelta(days=360), status="PENDING", correspondence_id="CORR-010"),
            ],
        )

        self._timelines["TL-002"] = RegulatoryTimeline(
            id="TL-002",
            trial_id=dupixent_id,
            trial_name=dupixent_name,
            milestones=[
                TimelineMilestone(name="IND Submission", planned_date=now - timedelta(days=200), actual_date=now - timedelta(days=198), status="COMPLETED"),
                TimelineMilestone(name="FDA 30-Day Review", planned_date=now - timedelta(days=170), actual_date=now - timedelta(days=168), status="COMPLETED"),
                TimelineMilestone(name="First Patient Enrolled", planned_date=now - timedelta(days=120), actual_date=now - timedelta(days=115), status="COMPLETED"),
                TimelineMilestone(name="DSMB Interim Review", planned_date=now - timedelta(days=60), actual_date=now - timedelta(days=60), status="COMPLETED", correspondence_id="CORR-009"),
                TimelineMilestone(name="Enrollment Complete", planned_date=now + timedelta(days=60), status="PENDING"),
                TimelineMilestone(name="Database Lock", planned_date=now + timedelta(days=180), status="PENDING"),
            ],
        )

        self._timelines["TL-003"] = RegulatoryTimeline(
            id="TL-003",
            trial_id=libtayo_id,
            trial_name=libtayo_name,
            milestones=[
                TimelineMilestone(name="EMA Scientific Advice", planned_date=now - timedelta(days=60), actual_date=now - timedelta(days=58), status="COMPLETED"),
                TimelineMilestone(name="CTA Submission", planned_date=now - timedelta(days=30), actual_date=now - timedelta(days=30), status="COMPLETED"),
                TimelineMilestone(name="MHRA Registration", planned_date=now + timedelta(days=15), status="PENDING", correspondence_id="CORR-005"),
                TimelineMilestone(name="First Patient Enrolled (EU)", planned_date=now + timedelta(days=45), status="PENDING"),
                TimelineMilestone(name="Protocol Amendment Approval", planned_date=now + timedelta(days=30), status="PENDING", correspondence_id="CORR-008"),
            ],
        )

        # ---------------------------------------------------------------
        # 8 Agency contacts
        # ---------------------------------------------------------------
        seed_contacts: list[dict] = [
            {"id": "AC-001", "name": "Dr. Patricia Williams", "agency": RegulatoryAgency.FDA, "title": "Review Division Director", "division": "Division of Ophthalmology Products (CDER)", "email": "patricia.williams@fda.hhs.gov", "phone": "+1-301-555-0101"},
            {"id": "AC-002", "name": "Dr. Richard Chang", "agency": RegulatoryAgency.FDA, "title": "Medical Officer", "division": "Division of Dermatology and Dental Products (CDER)", "email": "richard.chang@fda.hhs.gov", "phone": "+1-301-555-0102"},
            {"id": "AC-003", "name": "Dr. Lisa Martinez", "agency": RegulatoryAgency.FDA, "title": "Pharmacology Reviewer", "division": "Office of Clinical Pharmacology (CDER)", "email": "lisa.martinez@fda.hhs.gov", "phone": "+1-301-555-0103"},
            {"id": "AC-004", "name": "Dr. Hans Becker", "agency": RegulatoryAgency.EMA, "title": "Scientific Assessor", "division": "CHMP Scientific Committee", "email": "hans.becker@ema.europa.eu", "phone": "+31-88-781-0104"},
            {"id": "AC-005", "name": "Dr. Sophie Laurent", "agency": RegulatoryAgency.EMA, "title": "Rapporteur Coordinator", "division": "Procedure Management Department", "email": "sophie.laurent@ema.europa.eu", "phone": "+31-88-781-0105"},
            {"id": "AC-006", "name": "Dr. James Thornton", "agency": RegulatoryAgency.MHRA, "title": "Senior Assessor", "division": "Licensing Division", "email": "james.thornton@mhra.gov.uk", "phone": "+44-20-3080-0106"},
            {"id": "AC-007", "name": "Dr. Eleanor Hughes", "agency": RegulatoryAgency.MHRA, "title": "GMP Inspector", "division": "Inspectorate", "email": "eleanor.hughes@mhra.gov.uk", "phone": "+44-20-3080-0107"},
            {"id": "AC-008", "name": "Dr. David Chen", "agency": RegulatoryAgency.FDA, "title": "Chemistry Reviewer", "division": "Office of Pharmaceutical Quality (CDER)", "email": "david.chen@fda.hhs.gov", "phone": "+1-301-555-0108"},
        ]

        for data in seed_contacts:
            c_id = data["id"]
            data.setdefault("notes", None)
            self._contacts[c_id] = AgencyContact(**data)

        logger.info(
            "Seeded %d correspondence, %d action items, %d timelines, %d contacts",
            len(self._correspondence),
            len(self._action_items),
            len(self._timelines),
            len(self._contacts),
        )

    # ------------------------------------------------------------------
    # Correspondence CRUD
    # ------------------------------------------------------------------

    def create_correspondence(self, payload: CorrespondenceCreate) -> Correspondence:
        """Create a new correspondence record."""
        now = datetime.now(timezone.utc)
        corr_id = f"CORR-{uuid4().hex[:8].upper()}"

        corr = Correspondence(
            id=corr_id,
            title=payload.title,
            correspondence_type=payload.correspondence_type,
            agency=payload.agency,
            status=CorrespondenceStatus.DRAFT,
            priority=payload.priority,
            trial_id=payload.trial_id,
            trial_name=payload.trial_name,
            description=payload.description,
            response_deadline=payload.response_deadline,
            assigned_to=payload.assigned_to,
            reviewer=payload.reviewer,
            tags=payload.tags,
            key_points=payload.key_points,
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            self._correspondence[corr_id] = corr
            logger.info("Created correspondence %s: %s", corr_id, payload.title)
            return corr

    def get_correspondence(self, correspondence_id: str) -> Correspondence:
        """Retrieve a single correspondence by ID."""
        with self._lock:
            corr = self._correspondence.get(correspondence_id)
            if corr is None:
                raise KeyError(f"Correspondence {correspondence_id} not found")
            return corr

    def update_correspondence(
        self, correspondence_id: str, payload: CorrespondenceUpdate
    ) -> Correspondence:
        """Update an existing correspondence record."""
        now = datetime.now(timezone.utc)
        with self._lock:
            corr = self._correspondence.get(correspondence_id)
            if corr is None:
                raise KeyError(f"Correspondence {correspondence_id} not found")

            data = corr.model_dump()

            # Validate status transition
            if payload.status is not None and payload.status != corr.status:
                allowed = VALID_STATUS_TRANSITIONS.get(corr.status, set())
                if payload.status not in allowed:
                    raise ValueError(
                        f"Invalid status transition: {corr.status.value} -> {payload.status.value}"
                    )
                data["status"] = payload.status

                # Auto-set submission_date when transitioning to SUBMITTED
                if payload.status == CorrespondenceStatus.SUBMITTED and data.get("submission_date") is None:
                    data["submission_date"] = now
                    # Compute deadline date
                    deadline = data.get("response_deadline", ResponseDeadline.NONE)
                    if isinstance(deadline, str):
                        deadline = ResponseDeadline(deadline)
                    data["response_deadline_date"] = _compute_deadline_date(now, deadline)

                # Auto-set response_received_date when response received
                if payload.status == CorrespondenceStatus.RESPONSE_RECEIVED and data.get("response_received_date") is None:
                    data["response_received_date"] = now

            for field in (
                "title", "priority", "description", "response_deadline",
                "response_deadline_date", "assigned_to", "reviewer",
                "tags", "key_points", "action_items",
            ):
                val = getattr(payload, field, None)
                if val is not None:
                    data[field] = val

            data["updated_at"] = now
            updated = Correspondence(**data)
            self._correspondence[correspondence_id] = updated
            logger.info("Updated correspondence %s", correspondence_id)
            return updated

    def delete_correspondence(self, correspondence_id: str) -> None:
        """Delete a correspondence and its action items."""
        with self._lock:
            if correspondence_id not in self._correspondence:
                raise KeyError(f"Correspondence {correspondence_id} not found")
            del self._correspondence[correspondence_id]
            # Remove associated action items
            to_remove = [
                ai_id for ai_id, ai in self._action_items.items()
                if ai.correspondence_id == correspondence_id
            ]
            for ai_id in to_remove:
                del self._action_items[ai_id]
            # Remove from related_correspondence_ids of others
            for c in self._correspondence.values():
                if correspondence_id in c.related_correspondence_ids:
                    c.related_correspondence_ids.remove(correspondence_id)
            logger.info(
                "Deleted correspondence %s and %d action items",
                correspondence_id,
                len(to_remove),
            )

    def list_correspondence(
        self,
        *,
        agency: RegulatoryAgency | None = None,
        correspondence_type: CorrespondenceType | None = None,
        status: CorrespondenceStatus | None = None,
        priority: Priority | None = None,
        trial_id: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Correspondence], int]:
        """List correspondence with optional filters and pagination."""
        with self._lock:
            items = list(self._correspondence.values())

        if agency is not None:
            items = [c for c in items if c.agency == agency]
        if correspondence_type is not None:
            items = [c for c in items if c.correspondence_type == correspondence_type]
        if status is not None:
            items = [c for c in items if c.status == status]
        if priority is not None:
            items = [c for c in items if c.priority == priority]
        if trial_id is not None:
            items = [c for c in items if c.trial_id == trial_id]
        if search is not None:
            search_lower = search.lower()
            items = [
                c for c in items
                if search_lower in c.title.lower()
                or (c.description and search_lower in c.description.lower())
            ]

        items.sort(key=lambda c: c.updated_at, reverse=True)
        total = len(items)
        return items[offset: offset + limit], total

    def submit_correspondence(self, correspondence_id: str) -> Correspondence:
        """Transition correspondence to SUBMITTED status."""
        now = datetime.now(timezone.utc)
        with self._lock:
            corr = self._correspondence.get(correspondence_id)
            if corr is None:
                raise KeyError(f"Correspondence {correspondence_id} not found")

            allowed = VALID_STATUS_TRANSITIONS.get(corr.status, set())
            if CorrespondenceStatus.SUBMITTED not in allowed:
                raise ValueError(
                    f"Cannot submit from status {corr.status.value}"
                )

            data = corr.model_dump()
            data["status"] = CorrespondenceStatus.SUBMITTED
            data["submission_date"] = now
            data["updated_at"] = now

            # Compute deadline date
            deadline = data.get("response_deadline", ResponseDeadline.NONE)
            if isinstance(deadline, str):
                deadline = ResponseDeadline(deadline)
            data["response_deadline_date"] = _compute_deadline_date(now, deadline)

            updated = Correspondence(**data)
            self._correspondence[correspondence_id] = updated
            logger.info("Submitted correspondence %s", correspondence_id)
            return updated

    def link_correspondence(
        self, correspondence_id: str, related_id: str
    ) -> Correspondence:
        """Link two correspondence records together."""
        with self._lock:
            corr = self._correspondence.get(correspondence_id)
            if corr is None:
                raise KeyError(f"Correspondence {correspondence_id} not found")
            related = self._correspondence.get(related_id)
            if related is None:
                raise KeyError(f"Related correspondence {related_id} not found")
            if correspondence_id == related_id:
                raise ValueError("Cannot link correspondence to itself")

            if related_id not in corr.related_correspondence_ids:
                corr.related_correspondence_ids.append(related_id)
            if correspondence_id not in related.related_correspondence_ids:
                related.related_correspondence_ids.append(correspondence_id)

            logger.info("Linked %s <-> %s", correspondence_id, related_id)
            return corr

    # ------------------------------------------------------------------
    # Action item management
    # ------------------------------------------------------------------

    def create_action_item(
        self, correspondence_id: str, payload: ActionItemCreate
    ) -> ActionItem:
        """Create an action item for a correspondence."""
        with self._lock:
            if correspondence_id not in self._correspondence:
                raise KeyError(f"Correspondence {correspondence_id} not found")
            ai_id = f"AI-{uuid4().hex[:8].upper()}"
            item = ActionItem(
                id=ai_id,
                correspondence_id=correspondence_id,
                description=payload.description,
                assigned_to=payload.assigned_to,
                due_date=payload.due_date,
                priority=payload.priority,
            )
            self._action_items[ai_id] = item
            logger.info("Created action item %s for %s", ai_id, correspondence_id)
            return item

    def get_action_item(self, action_item_id: str) -> ActionItem:
        """Retrieve a single action item by ID."""
        with self._lock:
            item = self._action_items.get(action_item_id)
            if item is None:
                raise KeyError(f"Action item {action_item_id} not found")
            return item

    def update_action_item(
        self, action_item_id: str, payload: ActionItemUpdate
    ) -> ActionItem:
        """Update an action item."""
        with self._lock:
            item = self._action_items.get(action_item_id)
            if item is None:
                raise KeyError(f"Action item {action_item_id} not found")

            data = item.model_dump()
            for field in ("description", "assigned_to", "due_date", "completed", "priority"):
                val = getattr(payload, field, None)
                if val is not None:
                    data[field] = val

            # Auto-set completed_date
            if payload.completed is True and data.get("completed_date") is None:
                data["completed_date"] = datetime.now(timezone.utc)
            elif payload.completed is False:
                data["completed_date"] = None

            updated = ActionItem(**data)
            self._action_items[action_item_id] = updated
            logger.info("Updated action item %s", action_item_id)
            return updated

    def delete_action_item(self, action_item_id: str) -> None:
        """Delete an action item."""
        with self._lock:
            if action_item_id not in self._action_items:
                raise KeyError(f"Action item {action_item_id} not found")
            del self._action_items[action_item_id]
            logger.info("Deleted action item %s", action_item_id)

    def list_action_items(
        self,
        correspondence_id: str | None = None,
        *,
        completed: bool | None = None,
        overdue_only: bool = False,
    ) -> list[ActionItem]:
        """List action items with optional filters."""
        now = datetime.now(timezone.utc)
        with self._lock:
            items = list(self._action_items.values())

        if correspondence_id is not None:
            items = [a for a in items if a.correspondence_id == correspondence_id]
        if completed is not None:
            items = [a for a in items if a.completed == completed]
        if overdue_only:
            items = [a for a in items if not a.completed and a.due_date < now]

        items.sort(key=lambda a: a.due_date)
        return items

    # ------------------------------------------------------------------
    # Timeline management
    # ------------------------------------------------------------------

    def create_timeline(self, payload: TimelineCreate) -> RegulatoryTimeline:
        """Create a regulatory timeline."""
        tl_id = f"TL-{uuid4().hex[:8].upper()}"
        timeline = RegulatoryTimeline(
            id=tl_id,
            trial_id=payload.trial_id,
            trial_name=payload.trial_name,
            milestones=payload.milestones,
        )
        with self._lock:
            self._timelines[tl_id] = timeline
            logger.info("Created timeline %s for trial %s", tl_id, payload.trial_id)
            return timeline

    def get_timeline(self, timeline_id: str) -> RegulatoryTimeline:
        """Retrieve a timeline by ID."""
        with self._lock:
            tl = self._timelines.get(timeline_id)
            if tl is None:
                raise KeyError(f"Timeline {timeline_id} not found")
            return tl

    def get_timeline_by_trial(self, trial_id: str) -> RegulatoryTimeline | None:
        """Retrieve a timeline by trial ID."""
        with self._lock:
            for tl in self._timelines.values():
                if tl.trial_id == trial_id:
                    return tl
            return None

    def update_timeline(
        self, timeline_id: str, payload: TimelineUpdate
    ) -> RegulatoryTimeline:
        """Update a timeline."""
        with self._lock:
            tl = self._timelines.get(timeline_id)
            if tl is None:
                raise KeyError(f"Timeline {timeline_id} not found")

            data = tl.model_dump()
            if payload.trial_name is not None:
                data["trial_name"] = payload.trial_name

            updated = RegulatoryTimeline(**data)
            self._timelines[timeline_id] = updated
            logger.info("Updated timeline %s", timeline_id)
            return updated

    def delete_timeline(self, timeline_id: str) -> None:
        """Delete a timeline."""
        with self._lock:
            if timeline_id not in self._timelines:
                raise KeyError(f"Timeline {timeline_id} not found")
            del self._timelines[timeline_id]
            logger.info("Deleted timeline %s", timeline_id)

    def list_timelines(self) -> list[RegulatoryTimeline]:
        """List all timelines."""
        with self._lock:
            return list(self._timelines.values())

    def add_milestone(
        self, timeline_id: str, payload: MilestoneCreate
    ) -> RegulatoryTimeline:
        """Add a milestone to a timeline."""
        with self._lock:
            tl = self._timelines.get(timeline_id)
            if tl is None:
                raise KeyError(f"Timeline {timeline_id} not found")

            milestone = TimelineMilestone(
                name=payload.name,
                planned_date=payload.planned_date,
                correspondence_id=payload.correspondence_id,
                notes=payload.notes,
            )

            data = tl.model_dump()
            data["milestones"].append(milestone.model_dump())
            updated = RegulatoryTimeline(**data)
            self._timelines[timeline_id] = updated
            logger.info("Added milestone '%s' to timeline %s", payload.name, timeline_id)
            return updated

    def update_milestone(
        self, timeline_id: str, milestone_index: int, payload: MilestoneUpdate
    ) -> RegulatoryTimeline:
        """Update a milestone within a timeline by index."""
        with self._lock:
            tl = self._timelines.get(timeline_id)
            if tl is None:
                raise KeyError(f"Timeline {timeline_id} not found")

            if milestone_index < 0 or milestone_index >= len(tl.milestones):
                raise IndexError(
                    f"Milestone index {milestone_index} out of range "
                    f"(0-{len(tl.milestones) - 1})"
                )

            data = tl.model_dump()
            ms_data = data["milestones"][milestone_index]

            for field in ("name", "planned_date", "actual_date", "status", "correspondence_id", "notes"):
                val = getattr(payload, field, None)
                if val is not None:
                    ms_data[field] = val

            updated = RegulatoryTimeline(**data)
            self._timelines[timeline_id] = updated
            logger.info(
                "Updated milestone %d in timeline %s", milestone_index, timeline_id
            )
            return updated

    def delete_milestone(
        self, timeline_id: str, milestone_index: int
    ) -> RegulatoryTimeline:
        """Delete a milestone from a timeline by index."""
        with self._lock:
            tl = self._timelines.get(timeline_id)
            if tl is None:
                raise KeyError(f"Timeline {timeline_id} not found")

            if milestone_index < 0 or milestone_index >= len(tl.milestones):
                raise IndexError(
                    f"Milestone index {milestone_index} out of range "
                    f"(0-{len(tl.milestones) - 1})"
                )

            data = tl.model_dump()
            data["milestones"].pop(milestone_index)
            updated = RegulatoryTimeline(**data)
            self._timelines[timeline_id] = updated
            logger.info(
                "Deleted milestone %d from timeline %s", milestone_index, timeline_id
            )
            return updated

    # ------------------------------------------------------------------
    # Agency contact management
    # ------------------------------------------------------------------

    def create_contact(self, payload: AgencyContactCreate) -> AgencyContact:
        """Create an agency contact."""
        c_id = f"AC-{uuid4().hex[:8].upper()}"
        contact = AgencyContact(
            id=c_id,
            name=payload.name,
            agency=payload.agency,
            title=payload.title,
            division=payload.division,
            email=payload.email,
            phone=payload.phone,
            notes=payload.notes,
        )
        with self._lock:
            self._contacts[c_id] = contact
            logger.info("Created contact %s: %s", c_id, payload.name)
            return contact

    def get_contact(self, contact_id: str) -> AgencyContact:
        """Retrieve a contact by ID."""
        with self._lock:
            contact = self._contacts.get(contact_id)
            if contact is None:
                raise KeyError(f"Contact {contact_id} not found")
            return contact

    def update_contact(
        self, contact_id: str, payload: AgencyContactUpdate
    ) -> AgencyContact:
        """Update an agency contact."""
        with self._lock:
            contact = self._contacts.get(contact_id)
            if contact is None:
                raise KeyError(f"Contact {contact_id} not found")

            data = contact.model_dump()
            for field in ("name", "agency", "title", "division", "email", "phone", "notes"):
                val = getattr(payload, field, None)
                if val is not None:
                    data[field] = val

            updated = AgencyContact(**data)
            self._contacts[contact_id] = updated
            logger.info("Updated contact %s", contact_id)
            return updated

    def delete_contact(self, contact_id: str) -> None:
        """Delete an agency contact."""
        with self._lock:
            if contact_id not in self._contacts:
                raise KeyError(f"Contact {contact_id} not found")
            del self._contacts[contact_id]
            logger.info("Deleted contact %s", contact_id)

    def list_contacts(
        self, agency: RegulatoryAgency | None = None
    ) -> list[AgencyContact]:
        """List contacts, optionally filtered by agency."""
        with self._lock:
            items = list(self._contacts.values())
        if agency is not None:
            items = [c for c in items if c.agency == agency]
        items.sort(key=lambda c: c.name)
        return items

    # ------------------------------------------------------------------
    # Deadline report
    # ------------------------------------------------------------------

    def get_deadline_report(self, days_ahead: int = 30) -> DeadlineReport:
        """Get all upcoming deadlines within N days and overdue items."""
        now = datetime.now(timezone.utc)
        upcoming: list[DeadlineEntry] = []
        overdue: list[DeadlineEntry] = []

        with self._lock:
            # Check correspondence response deadlines
            for corr in self._correspondence.values():
                if corr.status in (
                    CorrespondenceStatus.CLOSED,
                    CorrespondenceStatus.WITHDRAWN,
                ):
                    continue
                if corr.response_deadline_date is not None:
                    days_until = (corr.response_deadline_date - now).days
                    entry = DeadlineEntry(
                        id=corr.id,
                        title=corr.title,
                        deadline_date=corr.response_deadline_date,
                        days_until_due=days_until,
                        is_overdue=days_until < 0,
                        source_type="correspondence",
                        agency=corr.agency,
                        priority=corr.priority,
                    )
                    if days_until < 0:
                        overdue.append(entry)
                    elif days_until <= days_ahead:
                        upcoming.append(entry)

            # Check action item deadlines
            for ai in self._action_items.values():
                if ai.completed:
                    continue
                days_until = (ai.due_date - now).days
                corr = self._correspondence.get(ai.correspondence_id)
                entry = DeadlineEntry(
                    id=ai.id,
                    title=ai.description,
                    deadline_date=ai.due_date,
                    days_until_due=days_until,
                    is_overdue=days_until < 0,
                    source_type="action_item",
                    agency=corr.agency if corr else None,
                    priority=ai.priority,
                )
                if days_until < 0:
                    overdue.append(entry)
                elif days_until <= days_ahead:
                    upcoming.append(entry)

        upcoming.sort(key=lambda e: e.deadline_date)
        overdue.sort(key=lambda e: e.days_until_due)

        return DeadlineReport(
            upcoming=upcoming,
            overdue=overdue,
            total_upcoming=len(upcoming),
            total_overdue=len(overdue),
        )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> CorrespondenceMetrics:
        """Compute aggregated correspondence metrics."""
        now = datetime.now(timezone.utc)

        with self._lock:
            corrs = list(self._correspondence.values())
            ais = list(self._action_items.values())

        total = len(corrs)
        by_agency = dict(Counter(c.agency.value for c in corrs))
        by_type = dict(Counter(c.correspondence_type.value for c in corrs))
        by_status = dict(Counter(c.status.value for c in corrs))

        # Average response time
        response_times: list[float] = []
        for c in corrs:
            if c.submission_date and c.response_received_date:
                delta = (c.response_received_date - c.submission_date).total_seconds() / 86400
                response_times.append(delta)

        avg_response = (
            round(sum(response_times) / len(response_times), 1)
            if response_times
            else None
        )

        open_ais = sum(1 for a in ais if not a.completed)
        completed_ais = sum(1 for a in ais if a.completed)
        overdue_ais = sum(
            1 for a in ais if not a.completed and a.due_date < now
        )

        return CorrespondenceMetrics(
            total_correspondence=total,
            by_agency=by_agency,
            by_type=by_type,
            by_status=by_status,
            overdue_action_items=overdue_ais,
            avg_response_time_days=avg_response,
            open_action_items=open_ais,
            completed_action_items=completed_ais,
        )

    # ------------------------------------------------------------------
    # Agency relationship summary
    # ------------------------------------------------------------------

    def get_agency_relationship_summary(
        self, agency: RegulatoryAgency
    ) -> AgencyRelationshipSummary:
        """Get a relationship summary for a specific agency."""
        with self._lock:
            corrs = [
                c for c in self._correspondence.values() if c.agency == agency
            ]
            contacts = [
                c for c in self._contacts.values() if c.agency == agency
            ]

        open_statuses = {
            CorrespondenceStatus.DRAFT,
            CorrespondenceStatus.UNDER_REVIEW,
            CorrespondenceStatus.SUBMITTED,
            CorrespondenceStatus.ACKNOWLEDGED,
            CorrespondenceStatus.RESPONSE_RECEIVED,
            CorrespondenceStatus.FOLLOW_UP_REQUIRED,
        }
        closed_statuses = {
            CorrespondenceStatus.CLOSED,
            CorrespondenceStatus.WITHDRAWN,
        }

        open_items = sum(1 for c in corrs if c.status in open_statuses)
        closed_items = sum(1 for c in corrs if c.status in closed_statuses)

        # Average response time for this agency
        response_times: list[float] = []
        for c in corrs:
            if c.submission_date and c.response_received_date:
                delta = (c.response_received_date - c.submission_date).total_seconds() / 86400
                response_times.append(delta)

        avg_response = (
            round(sum(response_times) / len(response_times), 1)
            if response_times
            else None
        )

        # Most recent 5
        recent = sorted(corrs, key=lambda c: c.updated_at, reverse=True)[:5]

        return AgencyRelationshipSummary(
            agency=agency,
            total_correspondence=len(corrs),
            open_items=open_items,
            closed_items=closed_items,
            avg_response_time_days=avg_response,
            contacts=contacts,
            recent_correspondence=recent,
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all data (for testing)."""
        with self._lock:
            self._correspondence.clear()
            self._action_items.clear()
            self._timelines.clear()
            self._contacts.clear()

    def get_stats(self) -> dict:
        """Return service statistics."""
        with self._lock:
            return {
                "correspondence": len(self._correspondence),
                "action_items": len(self._action_items),
                "timelines": len(self._timelines),
                "contacts": len(self._contacts),
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: RegulatoryCorrespondenceService | None = None
_instance_lock = threading.Lock()


def get_regulatory_correspondence_service() -> RegulatoryCorrespondenceService:
    """Return the singleton RegulatoryCorrespondenceService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = RegulatoryCorrespondenceService()
                logger.info("RegulatoryCorrespondenceService initialized")
    return _instance
