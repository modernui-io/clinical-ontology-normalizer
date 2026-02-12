"""Investigator Meeting Management Service (INV-MTG).

Manages investigator meeting operations: meeting planning, attendance
tracking, training session records, presentation materials management,
and action item tracking with meeting metrics.

Usage:
    from app.services.investigator_meeting_service import (
        get_investigator_meeting_service,
    )

    svc = get_investigator_meeting_service()
    plans = svc.list_meeting_plans()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.investigator_meeting import (
    ActionItem,
    ActionItemCreate,
    ActionItemUpdate,
    ActionPriority,
    AttendanceRecord,
    AttendanceRecordCreate,
    AttendanceRecordUpdate,
    AttendanceStatus,
    InvestigatorMeetingMetrics,
    MeetingFormat,
    MeetingPlan,
    MeetingPlanCreate,
    MeetingPlanUpdate,
    MeetingStatus,
    MeetingType,
    PresentationMaterial,
    PresentationMaterialCreate,
    PresentationMaterialUpdate,
    TrainingSession,
    TrainingSessionCreate,
    TrainingSessionUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class InvestigatorMeetingService:
    """In-memory Investigator Meeting Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._meeting_plans: dict[str, MeetingPlan] = {}
        self._attendance_records: dict[str, AttendanceRecord] = {}
        self._training_sessions: dict[str, TrainingSession] = {}
        self._presentation_materials: dict[str, PresentationMaterial] = {}
        self._action_items: dict[str, ActionItem] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic investigator meeting data."""
        now = datetime.now(timezone.utc)

        # --- 12 Meeting Plans ---
        plans_data = [
            {
                "id": "MP-001",
                "trial_id": EYLEA_TRIAL,
                "meeting_name": "EYLEA Phase III Investigator Meeting",
                "meeting_type": MeetingType.INVESTIGATOR_MEETING,
                "meeting_format": MeetingFormat.IN_PERSON,
                "status": MeetingStatus.COMPLETED,
                "planned_date": now - timedelta(days=180),
                "actual_date": now - timedelta(days=179),
                "duration_hours": 8.0,
                "location": "Grand Hyatt, New York, NY",
                "virtual_platform": None,
                "max_attendees": 120,
                "budget_estimate": 185000.0,
                "actual_cost": 178500.0,
                "agenda_finalized": True,
                "logistics_confirmed": True,
                "organized_by": "Dr. Sarah Chen",
                "sponsor_representative": "Dr. William Torres",
                "notes": "Full-day investigator meeting with protocol training and Q&A.",
                "created_at": now - timedelta(days=210),
            },
            {
                "id": "MP-002",
                "trial_id": EYLEA_TRIAL,
                "meeting_name": "EYLEA Site Initiation Visit - US Sites",
                "meeting_type": MeetingType.SITE_INITIATION,
                "meeting_format": MeetingFormat.HYBRID,
                "status": MeetingStatus.COMPLETED,
                "planned_date": now - timedelta(days=150),
                "actual_date": now - timedelta(days=149),
                "duration_hours": 4.0,
                "location": "Regeneron Headquarters, Tarrytown, NY",
                "virtual_platform": "Zoom",
                "max_attendees": 80,
                "budget_estimate": 45000.0,
                "actual_cost": 42300.0,
                "agenda_finalized": True,
                "logistics_confirmed": True,
                "organized_by": "Dr. James Wright",
                "sponsor_representative": "Dr. Sarah Chen",
                "notes": "Site initiation for 25 US sites. Hybrid format with virtual option.",
                "created_at": now - timedelta(days=170),
            },
            {
                "id": "MP-003",
                "trial_id": EYLEA_TRIAL,
                "meeting_name": "EYLEA Interim Review Meeting",
                "meeting_type": MeetingType.INTERIM_REVIEW,
                "meeting_format": MeetingFormat.VIRTUAL,
                "status": MeetingStatus.COMPLETED,
                "planned_date": now - timedelta(days=90),
                "actual_date": now - timedelta(days=90),
                "duration_hours": 3.0,
                "location": None,
                "virtual_platform": "Microsoft Teams",
                "max_attendees": 60,
                "budget_estimate": 12000.0,
                "actual_cost": 10800.0,
                "agenda_finalized": True,
                "logistics_confirmed": True,
                "organized_by": "Dr. Sarah Chen",
                "sponsor_representative": "Dr. William Torres",
                "notes": "Review of interim analysis results with DSMB recommendations.",
                "created_at": now - timedelta(days=100),
            },
            {
                "id": "MP-004",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_name": "DUPIXENT Phase IIb Investigator Meeting",
                "meeting_type": MeetingType.INVESTIGATOR_MEETING,
                "meeting_format": MeetingFormat.IN_PERSON,
                "status": MeetingStatus.COMPLETED,
                "planned_date": now - timedelta(days=200),
                "actual_date": now - timedelta(days=199),
                "duration_hours": 8.0,
                "location": "Four Seasons, Boston, MA",
                "virtual_platform": None,
                "max_attendees": 100,
                "budget_estimate": 165000.0,
                "actual_cost": 159200.0,
                "agenda_finalized": True,
                "logistics_confirmed": True,
                "organized_by": "Dr. Maria Lopez",
                "sponsor_representative": "Dr. Robert Kim",
                "notes": "Comprehensive investigator meeting. Protocol amendment review included.",
                "created_at": now - timedelta(days=230),
            },
            {
                "id": "MP-005",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_name": "DUPIXENT Advisory Board Meeting",
                "meeting_type": MeetingType.ADVISORY_BOARD,
                "meeting_format": MeetingFormat.HYBRID,
                "status": MeetingStatus.COMPLETED,
                "planned_date": now - timedelta(days=120),
                "actual_date": now - timedelta(days=119),
                "duration_hours": 6.0,
                "location": "Marriott Marquis, Chicago, IL",
                "virtual_platform": "Webex",
                "max_attendees": 30,
                "budget_estimate": 95000.0,
                "actual_cost": 91200.0,
                "agenda_finalized": True,
                "logistics_confirmed": True,
                "organized_by": "Dr. Robert Kim",
                "sponsor_representative": "Dr. Maria Lopez",
                "notes": "External advisory board review of efficacy data and dose selection.",
                "created_at": now - timedelta(days=140),
            },
            {
                "id": "MP-006",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_name": "DUPIXENT GCP Training Refresher",
                "meeting_type": MeetingType.TRAINING_SESSION,
                "meeting_format": MeetingFormat.VIRTUAL,
                "status": MeetingStatus.COMPLETED,
                "planned_date": now - timedelta(days=60),
                "actual_date": now - timedelta(days=60),
                "duration_hours": 2.0,
                "location": None,
                "virtual_platform": "Zoom",
                "max_attendees": 200,
                "budget_estimate": 8000.0,
                "actual_cost": 7500.0,
                "agenda_finalized": True,
                "logistics_confirmed": True,
                "organized_by": "Dr. Angela Park",
                "sponsor_representative": "Dr. Robert Kim",
                "notes": "Mandatory GCP refresher training for all site staff.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "MP-007",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_name": "LIBTAYO Phase III Investigator Meeting",
                "meeting_type": MeetingType.INVESTIGATOR_MEETING,
                "meeting_format": MeetingFormat.IN_PERSON,
                "status": MeetingStatus.COMPLETED,
                "planned_date": now - timedelta(days=240),
                "actual_date": now - timedelta(days=239),
                "duration_hours": 8.0,
                "location": "Hilton Midtown, New York, NY",
                "virtual_platform": None,
                "max_attendees": 150,
                "budget_estimate": 210000.0,
                "actual_cost": 205800.0,
                "agenda_finalized": True,
                "logistics_confirmed": True,
                "organized_by": "Dr. Angela Park",
                "sponsor_representative": "Dr. William Torres",
                "notes": "Large-scale investigator meeting for multi-center oncology trial.",
                "created_at": now - timedelta(days=270),
            },
            {
                "id": "MP-008",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_name": "LIBTAYO Site Initiation - EU Sites",
                "meeting_type": MeetingType.SITE_INITIATION,
                "meeting_format": MeetingFormat.HYBRID,
                "status": MeetingStatus.COMPLETED,
                "planned_date": now - timedelta(days=210),
                "actual_date": now - timedelta(days=209),
                "duration_hours": 5.0,
                "location": "Sofitel Munich Bayerpost, Munich, Germany",
                "virtual_platform": "Microsoft Teams",
                "max_attendees": 90,
                "budget_estimate": 55000.0,
                "actual_cost": 52100.0,
                "agenda_finalized": True,
                "logistics_confirmed": True,
                "organized_by": "Dr. Angela Park",
                "sponsor_representative": "Dr. William Torres",
                "notes": "EU site initiation covering 30 sites across 8 countries.",
                "created_at": now - timedelta(days=230),
            },
            {
                "id": "MP-009",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_name": "LIBTAYO Close-Out Meeting",
                "meeting_type": MeetingType.CLOSE_OUT,
                "meeting_format": MeetingFormat.VIRTUAL,
                "status": MeetingStatus.PLANNED,
                "planned_date": now + timedelta(days=30),
                "actual_date": None,
                "duration_hours": 4.0,
                "location": None,
                "virtual_platform": "Zoom",
                "max_attendees": 100,
                "budget_estimate": 15000.0,
                "actual_cost": None,
                "agenda_finalized": False,
                "logistics_confirmed": False,
                "organized_by": "Dr. Angela Park",
                "sponsor_representative": "Dr. William Torres",
                "notes": "Planned close-out meeting pending final analysis completion.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "MP-010",
                "trial_id": EYLEA_TRIAL,
                "meeting_name": "EYLEA Protocol Amendment Review",
                "meeting_type": MeetingType.ADVISORY_BOARD,
                "meeting_format": MeetingFormat.VIRTUAL,
                "status": MeetingStatus.CONFIRMED,
                "planned_date": now + timedelta(days=14),
                "actual_date": None,
                "duration_hours": 3.0,
                "location": None,
                "virtual_platform": "Microsoft Teams",
                "max_attendees": 25,
                "budget_estimate": 18000.0,
                "actual_cost": None,
                "agenda_finalized": True,
                "logistics_confirmed": True,
                "organized_by": "Dr. Sarah Chen",
                "sponsor_representative": "Dr. James Wright",
                "notes": "Review protocol amendment for expanded inclusion criteria.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "MP-011",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_name": "DUPIXENT Interim Data Review",
                "meeting_type": MeetingType.INTERIM_REVIEW,
                "meeting_format": MeetingFormat.HYBRID,
                "status": MeetingStatus.CONFIRMED,
                "planned_date": now + timedelta(days=7),
                "actual_date": None,
                "duration_hours": 4.0,
                "location": "Regeneron, Tarrytown, NY",
                "virtual_platform": "Zoom",
                "max_attendees": 40,
                "budget_estimate": 32000.0,
                "actual_cost": None,
                "agenda_finalized": True,
                "logistics_confirmed": False,
                "organized_by": "Dr. Maria Lopez",
                "sponsor_representative": "Dr. Robert Kim",
                "notes": "Interim data review with key opinion leaders.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "MP-012",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_name": "LIBTAYO Safety Review Board",
                "meeting_type": MeetingType.ADVISORY_BOARD,
                "meeting_format": MeetingFormat.VIRTUAL,
                "status": MeetingStatus.POSTPONED,
                "planned_date": now - timedelta(days=5),
                "actual_date": None,
                "duration_hours": 2.0,
                "location": None,
                "virtual_platform": "Webex",
                "max_attendees": 20,
                "budget_estimate": 22000.0,
                "actual_cost": None,
                "agenda_finalized": True,
                "logistics_confirmed": True,
                "organized_by": "Dr. Angela Park",
                "sponsor_representative": "Dr. William Torres",
                "notes": "Postponed pending updated safety database lock.",
                "created_at": now - timedelta(days=30),
            },
        ]

        for p in plans_data:
            self._meeting_plans[p["id"]] = MeetingPlan(**p)

        # --- 12 Attendance Records ---
        attendance_data = [
            {
                "id": "AR-001",
                "trial_id": EYLEA_TRIAL,
                "meeting_id": "MP-001",
                "attendee_name": "Dr. Michael Johnson",
                "role": "Principal Investigator",
                "site_id": "SITE-US-001",
                "attendance_status": AttendanceStatus.ATTENDED,
                "invitation_date": now - timedelta(days=220),
                "rsvp_date": now - timedelta(days=210),
                "check_in_time": now - timedelta(days=179, hours=8),
                "travel_required": True,
                "travel_arranged": True,
                "accommodation_required": True,
                "dietary_requirements": None,
                "managed_by": "Clinical Operations Team",
                "notes": None,
                "created_at": now - timedelta(days=220),
            },
            {
                "id": "AR-002",
                "trial_id": EYLEA_TRIAL,
                "meeting_id": "MP-001",
                "attendee_name": "Dr. Emily Davis",
                "role": "Sub-Investigator",
                "site_id": "SITE-US-002",
                "attendance_status": AttendanceStatus.ATTENDED,
                "invitation_date": now - timedelta(days=220),
                "rsvp_date": now - timedelta(days=215),
                "check_in_time": now - timedelta(days=179, hours=7),
                "travel_required": True,
                "travel_arranged": True,
                "accommodation_required": True,
                "dietary_requirements": "Vegetarian",
                "managed_by": "Clinical Operations Team",
                "notes": "Requested vegetarian meals for all sessions.",
                "created_at": now - timedelta(days=220),
            },
            {
                "id": "AR-003",
                "trial_id": EYLEA_TRIAL,
                "meeting_id": "MP-001",
                "attendee_name": "Nurse Patricia Wilson",
                "role": "Study Coordinator",
                "site_id": "SITE-US-001",
                "attendance_status": AttendanceStatus.ATTENDED,
                "invitation_date": now - timedelta(days=220),
                "rsvp_date": now - timedelta(days=218),
                "check_in_time": now - timedelta(days=179, hours=8),
                "travel_required": False,
                "travel_arranged": False,
                "accommodation_required": False,
                "dietary_requirements": None,
                "managed_by": "Clinical Operations Team",
                "notes": "Local attendee - no travel required.",
                "created_at": now - timedelta(days=220),
            },
            {
                "id": "AR-004",
                "trial_id": EYLEA_TRIAL,
                "meeting_id": "MP-001",
                "attendee_name": "Dr. Richard Lee",
                "role": "Principal Investigator",
                "site_id": "SITE-US-003",
                "attendance_status": AttendanceStatus.DECLINED,
                "invitation_date": now - timedelta(days=220),
                "rsvp_date": now - timedelta(days=200),
                "check_in_time": None,
                "travel_required": True,
                "travel_arranged": False,
                "accommodation_required": False,
                "dietary_requirements": None,
                "managed_by": "Clinical Operations Team",
                "notes": "Declined due to scheduling conflict. Sub-I attended instead.",
                "created_at": now - timedelta(days=220),
            },
            {
                "id": "AR-005",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_id": "MP-004",
                "attendee_name": "Dr. Ana Martinez",
                "role": "Principal Investigator",
                "site_id": "SITE-US-010",
                "attendance_status": AttendanceStatus.ATTENDED,
                "invitation_date": now - timedelta(days=240),
                "rsvp_date": now - timedelta(days=230),
                "check_in_time": now - timedelta(days=199, hours=8),
                "travel_required": True,
                "travel_arranged": True,
                "accommodation_required": True,
                "dietary_requirements": "Gluten-free",
                "managed_by": "Meeting Logistics Team",
                "notes": None,
                "created_at": now - timedelta(days=240),
            },
            {
                "id": "AR-006",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_id": "MP-004",
                "attendee_name": "Dr. Thomas Brown",
                "role": "Sub-Investigator",
                "site_id": "SITE-US-011",
                "attendance_status": AttendanceStatus.NO_SHOW,
                "invitation_date": now - timedelta(days=240),
                "rsvp_date": now - timedelta(days=225),
                "check_in_time": None,
                "travel_required": True,
                "travel_arranged": True,
                "accommodation_required": True,
                "dietary_requirements": None,
                "managed_by": "Meeting Logistics Team",
                "notes": "No-show. Follow-up training session scheduled.",
                "created_at": now - timedelta(days=240),
            },
            {
                "id": "AR-007",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_id": "MP-005",
                "attendee_name": "Prof. Catherine White",
                "role": "Advisory Board Member",
                "site_id": None,
                "attendance_status": AttendanceStatus.ATTENDED,
                "invitation_date": now - timedelta(days=150),
                "rsvp_date": now - timedelta(days=145),
                "check_in_time": now - timedelta(days=119, hours=9),
                "travel_required": True,
                "travel_arranged": True,
                "accommodation_required": True,
                "dietary_requirements": None,
                "managed_by": "Medical Affairs Team",
                "notes": "Key opinion leader in dermatology.",
                "created_at": now - timedelta(days=150),
            },
            {
                "id": "AR-008",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_id": "MP-007",
                "attendee_name": "Dr. Hans Mueller",
                "role": "Principal Investigator",
                "site_id": "SITE-EU-001",
                "attendance_status": AttendanceStatus.ATTENDED,
                "invitation_date": now - timedelta(days=280),
                "rsvp_date": now - timedelta(days=270),
                "check_in_time": now - timedelta(days=239, hours=8),
                "travel_required": True,
                "travel_arranged": True,
                "accommodation_required": True,
                "dietary_requirements": None,
                "managed_by": "EU Operations Team",
                "notes": None,
                "created_at": now - timedelta(days=280),
            },
            {
                "id": "AR-009",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_id": "MP-007",
                "attendee_name": "Dr. Sophie Dubois",
                "role": "Principal Investigator",
                "site_id": "SITE-EU-002",
                "attendance_status": AttendanceStatus.ATTENDED,
                "invitation_date": now - timedelta(days=280),
                "rsvp_date": now - timedelta(days=275),
                "check_in_time": now - timedelta(days=239, hours=9),
                "travel_required": True,
                "travel_arranged": True,
                "accommodation_required": True,
                "dietary_requirements": "Vegan",
                "managed_by": "EU Operations Team",
                "notes": "Fluent in French and English.",
                "created_at": now - timedelta(days=280),
            },
            {
                "id": "AR-010",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_id": "MP-008",
                "attendee_name": "Dr. Kenji Tanaka",
                "role": "Sub-Investigator",
                "site_id": "SITE-EU-003",
                "attendance_status": AttendanceStatus.EXCUSED,
                "invitation_date": now - timedelta(days=240),
                "rsvp_date": now - timedelta(days=230),
                "check_in_time": None,
                "travel_required": True,
                "travel_arranged": False,
                "accommodation_required": False,
                "dietary_requirements": None,
                "managed_by": "EU Operations Team",
                "notes": "Excused due to medical emergency. Catch-up training provided.",
                "created_at": now - timedelta(days=240),
            },
            {
                "id": "AR-011",
                "trial_id": EYLEA_TRIAL,
                "meeting_id": "MP-010",
                "attendee_name": "Dr. Lisa Anderson",
                "role": "Advisory Board Member",
                "site_id": None,
                "attendance_status": AttendanceStatus.CONFIRMED,
                "invitation_date": now - timedelta(days=25),
                "rsvp_date": now - timedelta(days=18),
                "check_in_time": None,
                "travel_required": False,
                "travel_arranged": False,
                "accommodation_required": False,
                "dietary_requirements": None,
                "managed_by": "Medical Affairs Team",
                "notes": "Virtual attendance confirmed.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "AR-012",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_id": "MP-011",
                "attendee_name": "Dr. Robert Kim",
                "role": "Sponsor Representative",
                "site_id": None,
                "attendance_status": AttendanceStatus.INVITED,
                "invitation_date": now - timedelta(days=20),
                "rsvp_date": None,
                "check_in_time": None,
                "travel_required": False,
                "travel_arranged": False,
                "accommodation_required": False,
                "dietary_requirements": None,
                "managed_by": "Clinical Operations Team",
                "notes": "Awaiting RSVP.",
                "created_at": now - timedelta(days=20),
            },
        ]

        for a in attendance_data:
            self._attendance_records[a["id"]] = AttendanceRecord(**a)

        # --- 12 Training Sessions ---
        training_data = [
            {
                "id": "TS-001",
                "trial_id": EYLEA_TRIAL,
                "meeting_id": "MP-001",
                "session_title": "EYLEA Protocol Overview and Objectives",
                "topic": "Protocol Design",
                "trainer": "Dr. Sarah Chen",
                "session_date": now - timedelta(days=179, hours=9),
                "duration_minutes": 90,
                "attendee_count": 105,
                "assessment_required": True,
                "pass_rate_pct": 98.1,
                "materials_distributed": True,
                "recording_available": True,
                "certificate_issued": True,
                "gcp_training": False,
                "protocol_training": True,
                "created_by": "Dr. Sarah Chen",
                "notes": "Comprehensive protocol review with case studies.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "TS-002",
                "trial_id": EYLEA_TRIAL,
                "meeting_id": "MP-001",
                "session_title": "GCP Refresher and Regulatory Updates",
                "topic": "Good Clinical Practice",
                "trainer": "Dr. James Wright",
                "session_date": now - timedelta(days=179, hours=11),
                "duration_minutes": 60,
                "attendee_count": 105,
                "assessment_required": True,
                "pass_rate_pct": 100.0,
                "materials_distributed": True,
                "recording_available": True,
                "certificate_issued": True,
                "gcp_training": True,
                "protocol_training": False,
                "created_by": "Dr. James Wright",
                "notes": "GCP refresher with ICH E6(R2) updates.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "TS-003",
                "trial_id": EYLEA_TRIAL,
                "meeting_id": "MP-001",
                "session_title": "EDC System Training - RAVE",
                "topic": "Electronic Data Capture",
                "trainer": "Clinical Data Manager",
                "session_date": now - timedelta(days=179, hours=14),
                "duration_minutes": 120,
                "attendee_count": 95,
                "assessment_required": False,
                "pass_rate_pct": 0.0,
                "materials_distributed": True,
                "recording_available": True,
                "certificate_issued": False,
                "gcp_training": False,
                "protocol_training": False,
                "created_by": "Dr. Sarah Chen",
                "notes": "Hands-on EDC training with practice data entry.",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "TS-004",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_id": "MP-004",
                "session_title": "DUPIXENT Protocol and Amendment Review",
                "topic": "Protocol Training",
                "trainer": "Dr. Maria Lopez",
                "session_date": now - timedelta(days=199, hours=9),
                "duration_minutes": 90,
                "attendee_count": 88,
                "assessment_required": True,
                "pass_rate_pct": 95.5,
                "materials_distributed": True,
                "recording_available": True,
                "certificate_issued": True,
                "gcp_training": False,
                "protocol_training": True,
                "created_by": "Dr. Maria Lopez",
                "notes": "Protocol amendment 2 reviewed in detail.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "TS-005",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_id": "MP-004",
                "session_title": "Biomarker Sample Collection Procedures",
                "topic": "Laboratory Procedures",
                "trainer": "Dr. Lab Director",
                "session_date": now - timedelta(days=199, hours=13),
                "duration_minutes": 75,
                "attendee_count": 88,
                "assessment_required": True,
                "pass_rate_pct": 92.0,
                "materials_distributed": True,
                "recording_available": False,
                "certificate_issued": False,
                "gcp_training": False,
                "protocol_training": False,
                "created_by": "Dr. Maria Lopez",
                "notes": "Detailed sample collection and handling procedures.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "TS-006",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_id": "MP-006",
                "session_title": "Annual GCP Certification Training",
                "topic": "Good Clinical Practice",
                "trainer": "Dr. Angela Park",
                "session_date": now - timedelta(days=60),
                "duration_minutes": 120,
                "attendee_count": 175,
                "assessment_required": True,
                "pass_rate_pct": 99.4,
                "materials_distributed": True,
                "recording_available": True,
                "certificate_issued": True,
                "gcp_training": True,
                "protocol_training": False,
                "created_by": "Dr. Angela Park",
                "notes": "Mandatory annual GCP certification for all site staff.",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "TS-007",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_id": "MP-007",
                "session_title": "LIBTAYO Protocol and Study Design",
                "topic": "Protocol Design",
                "trainer": "Dr. Angela Park",
                "session_date": now - timedelta(days=239, hours=9),
                "duration_minutes": 90,
                "attendee_count": 130,
                "assessment_required": True,
                "pass_rate_pct": 96.2,
                "materials_distributed": True,
                "recording_available": True,
                "certificate_issued": True,
                "gcp_training": False,
                "protocol_training": True,
                "created_by": "Dr. Angela Park",
                "notes": "Multi-arm, multi-stage adaptive design explained.",
                "created_at": now - timedelta(days=240),
            },
            {
                "id": "TS-008",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_id": "MP-007",
                "session_title": "Immune-Related Adverse Event Management",
                "topic": "Safety Management",
                "trainer": "Dr. William Torres",
                "session_date": now - timedelta(days=239, hours=13),
                "duration_minutes": 90,
                "attendee_count": 130,
                "assessment_required": True,
                "pass_rate_pct": 97.7,
                "materials_distributed": True,
                "recording_available": True,
                "certificate_issued": True,
                "gcp_training": False,
                "protocol_training": False,
                "created_by": "Dr. Angela Park",
                "notes": "irAE grading and management algorithms reviewed.",
                "created_at": now - timedelta(days=240),
            },
            {
                "id": "TS-009",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_id": "MP-008",
                "session_title": "EU Regulatory Requirements Overview",
                "topic": "Regulatory Compliance",
                "trainer": "Regulatory Affairs Lead",
                "session_date": now - timedelta(days=209, hours=10),
                "duration_minutes": 60,
                "attendee_count": 75,
                "assessment_required": False,
                "pass_rate_pct": 0.0,
                "materials_distributed": True,
                "recording_available": True,
                "certificate_issued": False,
                "gcp_training": False,
                "protocol_training": False,
                "created_by": "Dr. Angela Park",
                "notes": "EU CTR and country-specific requirements.",
                "created_at": now - timedelta(days=210),
            },
            {
                "id": "TS-010",
                "trial_id": EYLEA_TRIAL,
                "meeting_id": "MP-003",
                "session_title": "Interim Analysis Review Training",
                "topic": "Data Analysis",
                "trainer": "Dr. Sarah Chen",
                "session_date": now - timedelta(days=90, hours=10),
                "duration_minutes": 45,
                "attendee_count": 45,
                "assessment_required": False,
                "pass_rate_pct": 0.0,
                "materials_distributed": True,
                "recording_available": True,
                "certificate_issued": False,
                "gcp_training": False,
                "protocol_training": False,
                "created_by": "Dr. Sarah Chen",
                "notes": "Training on interpreting interim analysis results.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "TS-011",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_id": None,
                "session_title": "LIBTAYO Pharmacovigilance Update",
                "topic": "Pharmacovigilance",
                "trainer": "PV Lead",
                "session_date": now - timedelta(days=30),
                "duration_minutes": 60,
                "attendee_count": 50,
                "assessment_required": False,
                "pass_rate_pct": 0.0,
                "materials_distributed": True,
                "recording_available": True,
                "certificate_issued": False,
                "gcp_training": False,
                "protocol_training": False,
                "created_by": "Dr. Angela Park",
                "notes": "Updated safety reporting requirements.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "TS-012",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_id": None,
                "session_title": "DUPIXENT ePRO Device Training",
                "topic": "Patient Reported Outcomes",
                "trainer": "ePRO Vendor Specialist",
                "session_date": now - timedelta(days=15),
                "duration_minutes": 45,
                "attendee_count": 60,
                "assessment_required": True,
                "pass_rate_pct": 88.3,
                "materials_distributed": True,
                "recording_available": False,
                "certificate_issued": False,
                "gcp_training": False,
                "protocol_training": False,
                "created_by": "Dr. Maria Lopez",
                "notes": "Training on new ePRO device for patient-reported outcomes.",
                "created_at": now - timedelta(days=20),
            },
        ]

        for t in training_data:
            self._training_sessions[t["id"]] = TrainingSession(**t)

        # --- 12 Presentation Materials ---
        materials_data = [
            {
                "id": "PM-001",
                "trial_id": EYLEA_TRIAL,
                "meeting_id": "MP-001",
                "title": "EYLEA Phase III Protocol Overview",
                "presenter": "Dr. Sarah Chen",
                "material_type": "slides",
                "version": "2.0",
                "slide_count": 85,
                "duration_minutes": 45,
                "approved_for_distribution": True,
                "confidential": True,
                "medical_review_completed": True,
                "legal_review_completed": True,
                "translated": False,
                "languages": ["English"],
                "uploaded_by": "Dr. Sarah Chen",
                "approved_by": "Dr. William Torres",
                "notes": "Final version distributed at investigator meeting.",
                "created_at": now - timedelta(days=185),
            },
            {
                "id": "PM-002",
                "trial_id": EYLEA_TRIAL,
                "meeting_id": "MP-001",
                "title": "EYLEA Efficacy and Safety Data Summary",
                "presenter": "Dr. James Wright",
                "material_type": "slides",
                "version": "1.0",
                "slide_count": 45,
                "duration_minutes": 30,
                "approved_for_distribution": True,
                "confidential": True,
                "medical_review_completed": True,
                "legal_review_completed": True,
                "translated": False,
                "languages": ["English"],
                "uploaded_by": "Dr. James Wright",
                "approved_by": "Dr. Sarah Chen",
                "notes": "Blinded safety data presentation.",
                "created_at": now - timedelta(days=185),
            },
            {
                "id": "PM-003",
                "trial_id": EYLEA_TRIAL,
                "meeting_id": "MP-001",
                "title": "EDC Quick Reference Guide",
                "presenter": "Clinical Data Manager",
                "material_type": "handbook",
                "version": "3.1",
                "slide_count": 0,
                "duration_minutes": 0,
                "approved_for_distribution": True,
                "confidential": False,
                "medical_review_completed": False,
                "legal_review_completed": True,
                "translated": True,
                "languages": ["English", "Spanish", "French", "German"],
                "uploaded_by": "Data Management Team",
                "approved_by": "Dr. Sarah Chen",
                "notes": "Multi-language reference guide for EDC system.",
                "created_at": now - timedelta(days=185),
            },
            {
                "id": "PM-004",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_id": "MP-004",
                "title": "DUPIXENT Protocol Amendment 2 Summary",
                "presenter": "Dr. Maria Lopez",
                "material_type": "slides",
                "version": "1.0",
                "slide_count": 55,
                "duration_minutes": 40,
                "approved_for_distribution": True,
                "confidential": True,
                "medical_review_completed": True,
                "legal_review_completed": True,
                "translated": False,
                "languages": ["English"],
                "uploaded_by": "Dr. Maria Lopez",
                "approved_by": "Dr. Robert Kim",
                "notes": "Protocol amendment rationale and key changes.",
                "created_at": now - timedelta(days=205),
            },
            {
                "id": "PM-005",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_id": "MP-004",
                "title": "Biomarker Collection Procedures Manual",
                "presenter": "Dr. Lab Director",
                "material_type": "manual",
                "version": "2.0",
                "slide_count": 0,
                "duration_minutes": 0,
                "approved_for_distribution": True,
                "confidential": False,
                "medical_review_completed": True,
                "legal_review_completed": False,
                "translated": True,
                "languages": ["English", "Japanese"],
                "uploaded_by": "Laboratory Team",
                "approved_by": "Dr. Maria Lopez",
                "notes": "Updated procedures for biomarker sample handling.",
                "created_at": now - timedelta(days=205),
            },
            {
                "id": "PM-006",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_id": "MP-005",
                "title": "DUPIXENT Dose-Response Analysis",
                "presenter": "Dr. Robert Kim",
                "material_type": "slides",
                "version": "1.2",
                "slide_count": 62,
                "duration_minutes": 35,
                "approved_for_distribution": False,
                "confidential": True,
                "medical_review_completed": True,
                "legal_review_completed": False,
                "translated": False,
                "languages": ["English"],
                "uploaded_by": "Dr. Robert Kim",
                "approved_by": None,
                "notes": "Advisory board presentation. Pending legal review.",
                "created_at": now - timedelta(days=125),
            },
            {
                "id": "PM-007",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_id": "MP-007",
                "title": "LIBTAYO Multi-Arm Adaptive Design Overview",
                "presenter": "Dr. Angela Park",
                "material_type": "slides",
                "version": "1.0",
                "slide_count": 95,
                "duration_minutes": 50,
                "approved_for_distribution": True,
                "confidential": True,
                "medical_review_completed": True,
                "legal_review_completed": True,
                "translated": True,
                "languages": ["English", "German", "French"],
                "uploaded_by": "Dr. Angela Park",
                "approved_by": "Dr. William Torres",
                "notes": "Multi-language presentation for global investigator meeting.",
                "created_at": now - timedelta(days=245),
            },
            {
                "id": "PM-008",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_id": "MP-007",
                "title": "irAE Management Algorithm Cards",
                "presenter": "Dr. William Torres",
                "material_type": "reference_card",
                "version": "2.1",
                "slide_count": 0,
                "duration_minutes": 0,
                "approved_for_distribution": True,
                "confidential": False,
                "medical_review_completed": True,
                "legal_review_completed": True,
                "translated": True,
                "languages": ["English", "German", "French", "Spanish", "Italian", "Japanese"],
                "uploaded_by": "Medical Affairs Team",
                "approved_by": "Dr. William Torres",
                "notes": "Pocket reference cards for irAE management distributed at IM.",
                "created_at": now - timedelta(days=245),
            },
            {
                "id": "PM-009",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_id": "MP-008",
                "title": "EU Regulatory Compliance Deck",
                "presenter": "Regulatory Affairs Lead",
                "material_type": "slides",
                "version": "1.0",
                "slide_count": 40,
                "duration_minutes": 25,
                "approved_for_distribution": True,
                "confidential": False,
                "medical_review_completed": False,
                "legal_review_completed": True,
                "translated": True,
                "languages": ["English", "German"],
                "uploaded_by": "Regulatory Affairs Lead",
                "approved_by": "Dr. Angela Park",
                "notes": "EU CTR compliance and country-specific guidance.",
                "created_at": now - timedelta(days=215),
            },
            {
                "id": "PM-010",
                "trial_id": EYLEA_TRIAL,
                "meeting_id": "MP-003",
                "title": "EYLEA Interim Analysis Results Summary",
                "presenter": "Dr. Sarah Chen",
                "material_type": "slides",
                "version": "1.0",
                "slide_count": 30,
                "duration_minutes": 20,
                "approved_for_distribution": False,
                "confidential": True,
                "medical_review_completed": True,
                "legal_review_completed": True,
                "translated": False,
                "languages": ["English"],
                "uploaded_by": "Dr. Sarah Chen",
                "approved_by": None,
                "notes": "Restricted distribution. DSMB eyes only.",
                "created_at": now - timedelta(days=92),
            },
            {
                "id": "PM-011",
                "trial_id": EYLEA_TRIAL,
                "meeting_id": "MP-010",
                "title": "Protocol Amendment Proposal - Expanded Criteria",
                "presenter": "Dr. Sarah Chen",
                "material_type": "slides",
                "version": "0.9",
                "slide_count": 38,
                "duration_minutes": 25,
                "approved_for_distribution": False,
                "confidential": True,
                "medical_review_completed": True,
                "legal_review_completed": False,
                "translated": False,
                "languages": ["English"],
                "uploaded_by": "Dr. Sarah Chen",
                "approved_by": None,
                "notes": "Draft slides for advisory board review.",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "PM-012",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_id": "MP-011",
                "title": "DUPIXENT Interim Efficacy Data Presentation",
                "presenter": "Dr. Maria Lopez",
                "material_type": "slides",
                "version": "1.0",
                "slide_count": 50,
                "duration_minutes": 30,
                "approved_for_distribution": False,
                "confidential": True,
                "medical_review_completed": False,
                "legal_review_completed": False,
                "translated": False,
                "languages": ["English"],
                "uploaded_by": "Dr. Maria Lopez",
                "approved_by": None,
                "notes": "Under preparation. Medical review pending.",
                "created_at": now - timedelta(days=22),
            },
        ]

        for m in materials_data:
            self._presentation_materials[m["id"]] = PresentationMaterial(**m)

        # --- 12 Action Items ---
        action_items_data = [
            {
                "id": "AI-001",
                "trial_id": EYLEA_TRIAL,
                "meeting_id": "MP-001",
                "action_description": "Distribute updated informed consent forms to all US sites",
                "assigned_to": "Dr. James Wright",
                "priority": ActionPriority.HIGH,
                "due_date": now - timedelta(days=165),
                "completed_date": now - timedelta(days=168),
                "status": "completed",
                "follow_up_required": False,
                "follow_up_meeting_id": None,
                "escalated": False,
                "escalated_to": None,
                "days_overdue": None,
                "created_by": "Dr. Sarah Chen",
                "notes": "All sites confirmed receipt.",
                "created_at": now - timedelta(days=179),
            },
            {
                "id": "AI-002",
                "trial_id": EYLEA_TRIAL,
                "meeting_id": "MP-001",
                "action_description": "Set up central lab shipment logistics for new sites",
                "assigned_to": "Lab Coordinator",
                "priority": ActionPriority.MEDIUM,
                "due_date": now - timedelta(days=160),
                "completed_date": now - timedelta(days=162),
                "status": "completed",
                "follow_up_required": False,
                "follow_up_meeting_id": None,
                "escalated": False,
                "escalated_to": None,
                "days_overdue": None,
                "created_by": "Dr. Sarah Chen",
                "notes": "Shipment kits dispatched to all new sites.",
                "created_at": now - timedelta(days=179),
            },
            {
                "id": "AI-003",
                "trial_id": EYLEA_TRIAL,
                "meeting_id": "MP-003",
                "action_description": "Prepare protocol amendment based on interim results",
                "assigned_to": "Dr. Sarah Chen",
                "priority": ActionPriority.CRITICAL,
                "due_date": now - timedelta(days=60),
                "completed_date": now - timedelta(days=55),
                "status": "completed",
                "follow_up_required": True,
                "follow_up_meeting_id": "MP-010",
                "escalated": False,
                "escalated_to": None,
                "days_overdue": None,
                "created_by": "Dr. William Torres",
                "notes": "Amendment drafted and scheduled for advisory board review.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "AI-004",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_id": "MP-004",
                "action_description": "Update IRB submissions for protocol amendment 2",
                "assigned_to": "Regulatory Affairs Lead",
                "priority": ActionPriority.HIGH,
                "due_date": now - timedelta(days=185),
                "completed_date": now - timedelta(days=187),
                "status": "completed",
                "follow_up_required": False,
                "follow_up_meeting_id": None,
                "escalated": False,
                "escalated_to": None,
                "days_overdue": None,
                "created_by": "Dr. Maria Lopez",
                "notes": "IRB approvals obtained for all participating sites.",
                "created_at": now - timedelta(days=199),
            },
            {
                "id": "AI-005",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_id": "MP-004",
                "action_description": "Schedule make-up training for no-show investigators",
                "assigned_to": "Clinical Operations Team",
                "priority": ActionPriority.MEDIUM,
                "due_date": now - timedelta(days=190),
                "completed_date": now - timedelta(days=188),
                "status": "completed",
                "follow_up_required": False,
                "follow_up_meeting_id": None,
                "escalated": False,
                "escalated_to": None,
                "days_overdue": None,
                "created_by": "Dr. Maria Lopez",
                "notes": "Catch-up training completed for 3 investigators.",
                "created_at": now - timedelta(days=199),
            },
            {
                "id": "AI-006",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_id": "MP-005",
                "action_description": "Complete legal review of dose-response presentation",
                "assigned_to": "Legal Affairs Team",
                "priority": ActionPriority.HIGH,
                "due_date": now - timedelta(days=100),
                "completed_date": None,
                "status": "open",
                "follow_up_required": True,
                "follow_up_meeting_id": "MP-011",
                "escalated": True,
                "escalated_to": "VP Legal Affairs",
                "days_overdue": int((now - (now - timedelta(days=100))).days),
                "created_by": "Dr. Robert Kim",
                "notes": "Escalated due to delay. Blocking presentation distribution.",
                "created_at": now - timedelta(days=119),
            },
            {
                "id": "AI-007",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_id": "MP-007",
                "action_description": "Translate irAE management cards into remaining languages",
                "assigned_to": "Medical Writing Team",
                "priority": ActionPriority.MEDIUM,
                "due_date": now - timedelta(days=220),
                "completed_date": now - timedelta(days=225),
                "status": "completed",
                "follow_up_required": False,
                "follow_up_meeting_id": None,
                "escalated": False,
                "escalated_to": None,
                "days_overdue": None,
                "created_by": "Dr. Angela Park",
                "notes": "All 6 languages completed and verified.",
                "created_at": now - timedelta(days=239),
            },
            {
                "id": "AI-008",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_id": "MP-007",
                "action_description": "Establish tumor assessment central review workflow",
                "assigned_to": "Dr. William Torres",
                "priority": ActionPriority.HIGH,
                "due_date": now - timedelta(days=210),
                "completed_date": now - timedelta(days=215),
                "status": "completed",
                "follow_up_required": False,
                "follow_up_meeting_id": None,
                "escalated": False,
                "escalated_to": None,
                "days_overdue": None,
                "created_by": "Dr. Angela Park",
                "notes": "Central review panel established with 3 independent radiologists.",
                "created_at": now - timedelta(days=239),
            },
            {
                "id": "AI-009",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_id": "MP-008",
                "action_description": "Provide catch-up training for excused EU investigators",
                "assigned_to": "EU Operations Team",
                "priority": ActionPriority.MEDIUM,
                "due_date": now - timedelta(days=195),
                "completed_date": now - timedelta(days=198),
                "status": "completed",
                "follow_up_required": False,
                "follow_up_meeting_id": None,
                "escalated": False,
                "escalated_to": None,
                "days_overdue": None,
                "created_by": "Dr. Angela Park",
                "notes": "Virtual catch-up session completed for 4 investigators.",
                "created_at": now - timedelta(days=209),
            },
            {
                "id": "AI-010",
                "trial_id": EYLEA_TRIAL,
                "meeting_id": "MP-010",
                "action_description": "Finalize protocol amendment for expanded inclusion criteria",
                "assigned_to": "Dr. Sarah Chen",
                "priority": ActionPriority.CRITICAL,
                "due_date": now + timedelta(days=21),
                "completed_date": None,
                "status": "open",
                "follow_up_required": True,
                "follow_up_meeting_id": None,
                "escalated": False,
                "escalated_to": None,
                "days_overdue": None,
                "created_by": "Dr. James Wright",
                "notes": "Draft under medical writing review.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "AI-011",
                "trial_id": LIBTAYO_TRIAL,
                "meeting_id": "MP-009",
                "action_description": "Prepare close-out meeting agenda and site notification letters",
                "assigned_to": "Dr. Angela Park",
                "priority": ActionPriority.HIGH,
                "due_date": now + timedelta(days=15),
                "completed_date": None,
                "status": "open",
                "follow_up_required": False,
                "follow_up_meeting_id": None,
                "escalated": False,
                "escalated_to": None,
                "days_overdue": None,
                "created_by": "Dr. William Torres",
                "notes": "Close-out planning in progress.",
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "AI-012",
                "trial_id": DUPIXENT_TRIAL,
                "meeting_id": "MP-011",
                "action_description": "Complete medical review of interim efficacy presentation",
                "assigned_to": "Dr. Robert Kim",
                "priority": ActionPriority.HIGH,
                "due_date": now + timedelta(days=3),
                "completed_date": None,
                "status": "open",
                "follow_up_required": False,
                "follow_up_meeting_id": None,
                "escalated": False,
                "escalated_to": None,
                "days_overdue": None,
                "created_by": "Dr. Maria Lopez",
                "notes": "Priority review required before data review meeting.",
                "created_at": now - timedelta(days=18),
            },
        ]

        for ai in action_items_data:
            self._action_items[ai["id"]] = ActionItem(**ai)

    # ------------------------------------------------------------------
    # Meeting Plans
    # ------------------------------------------------------------------

    def list_meeting_plans(
        self,
        *,
        trial_id: str | None = None,
        meeting_type: MeetingType | None = None,
        status: MeetingStatus | None = None,
        meeting_format: MeetingFormat | None = None,
    ) -> list[MeetingPlan]:
        """List meeting plans with optional filters."""
        with self._lock:
            result = list(self._meeting_plans.values())

        if trial_id is not None:
            result = [p for p in result if p.trial_id == trial_id]
        if meeting_type is not None:
            result = [p for p in result if p.meeting_type == meeting_type]
        if status is not None:
            result = [p for p in result if p.status == status]
        if meeting_format is not None:
            result = [p for p in result if p.meeting_format == meeting_format]

        return sorted(result, key=lambda p: p.planned_date, reverse=True)

    def get_meeting_plan(self, plan_id: str) -> MeetingPlan | None:
        """Get a single meeting plan by ID."""
        with self._lock:
            return self._meeting_plans.get(plan_id)

    def create_meeting_plan(self, payload: MeetingPlanCreate) -> MeetingPlan:
        """Create a new meeting plan."""
        now = datetime.now(timezone.utc)
        plan_id = f"MP-{uuid4().hex[:8].upper()}"
        plan = MeetingPlan(
            id=plan_id,
            trial_id=payload.trial_id,
            meeting_name=payload.meeting_name,
            meeting_type=payload.meeting_type,
            meeting_format=payload.meeting_format,
            status=MeetingStatus.PLANNED,
            planned_date=payload.planned_date,
            actual_date=None,
            duration_hours=payload.duration_hours,
            location=None,
            virtual_platform=None,
            max_attendees=0,
            budget_estimate=0.0,
            actual_cost=None,
            agenda_finalized=False,
            logistics_confirmed=False,
            organized_by=payload.organized_by,
            sponsor_representative=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._meeting_plans[plan_id] = plan
        logger.info("Created meeting plan %s for trial %s", plan_id, payload.trial_id)
        return plan

    def update_meeting_plan(
        self, plan_id: str, payload: MeetingPlanUpdate
    ) -> MeetingPlan | None:
        """Update an existing meeting plan."""
        with self._lock:
            existing = self._meeting_plans.get(plan_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MeetingPlan(**data)
            self._meeting_plans[plan_id] = updated
        return updated

    def delete_meeting_plan(self, plan_id: str) -> bool:
        """Delete a meeting plan. Returns True if deleted."""
        with self._lock:
            if plan_id in self._meeting_plans:
                del self._meeting_plans[plan_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Attendance Records
    # ------------------------------------------------------------------

    def list_attendance_records(
        self,
        *,
        trial_id: str | None = None,
        meeting_id: str | None = None,
        attendance_status: AttendanceStatus | None = None,
    ) -> list[AttendanceRecord]:
        """List attendance records with optional filters."""
        with self._lock:
            result = list(self._attendance_records.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if meeting_id is not None:
            result = [a for a in result if a.meeting_id == meeting_id]
        if attendance_status is not None:
            result = [a for a in result if a.attendance_status == attendance_status]

        return sorted(result, key=lambda a: a.created_at, reverse=True)

    def get_attendance_record(self, record_id: str) -> AttendanceRecord | None:
        """Get a single attendance record by ID."""
        with self._lock:
            return self._attendance_records.get(record_id)

    def create_attendance_record(self, payload: AttendanceRecordCreate) -> AttendanceRecord:
        """Create a new attendance record."""
        now = datetime.now(timezone.utc)
        record_id = f"AR-{uuid4().hex[:8].upper()}"
        record = AttendanceRecord(
            id=record_id,
            trial_id=payload.trial_id,
            meeting_id=payload.meeting_id,
            attendee_name=payload.attendee_name,
            role=payload.role,
            site_id=payload.site_id,
            attendance_status=AttendanceStatus.INVITED,
            invitation_date=now,
            rsvp_date=None,
            check_in_time=None,
            travel_required=False,
            travel_arranged=False,
            accommodation_required=False,
            dietary_requirements=None,
            managed_by=payload.managed_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._attendance_records[record_id] = record
        logger.info("Created attendance record %s for meeting %s", record_id, payload.meeting_id)
        return record

    def update_attendance_record(
        self, record_id: str, payload: AttendanceRecordUpdate
    ) -> AttendanceRecord | None:
        """Update an existing attendance record."""
        with self._lock:
            existing = self._attendance_records.get(record_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AttendanceRecord(**data)
            self._attendance_records[record_id] = updated
        return updated

    def delete_attendance_record(self, record_id: str) -> bool:
        """Delete an attendance record. Returns True if deleted."""
        with self._lock:
            if record_id in self._attendance_records:
                del self._attendance_records[record_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Training Sessions
    # ------------------------------------------------------------------

    def list_training_sessions(
        self,
        *,
        trial_id: str | None = None,
        meeting_id: str | None = None,
        gcp_training: bool | None = None,
    ) -> list[TrainingSession]:
        """List training sessions with optional filters."""
        with self._lock:
            result = list(self._training_sessions.values())

        if trial_id is not None:
            result = [t for t in result if t.trial_id == trial_id]
        if meeting_id is not None:
            result = [t for t in result if t.meeting_id == meeting_id]
        if gcp_training is not None:
            result = [t for t in result if t.gcp_training == gcp_training]

        return sorted(result, key=lambda t: t.session_date, reverse=True)

    def get_training_session(self, session_id: str) -> TrainingSession | None:
        """Get a single training session by ID."""
        with self._lock:
            return self._training_sessions.get(session_id)

    def create_training_session(self, payload: TrainingSessionCreate) -> TrainingSession:
        """Create a new training session."""
        now = datetime.now(timezone.utc)
        session_id = f"TS-{uuid4().hex[:8].upper()}"
        session = TrainingSession(
            id=session_id,
            trial_id=payload.trial_id,
            meeting_id=payload.meeting_id,
            session_title=payload.session_title,
            topic=payload.topic,
            trainer=payload.trainer,
            session_date=now,
            duration_minutes=payload.duration_minutes,
            attendee_count=0,
            assessment_required=False,
            pass_rate_pct=0.0,
            materials_distributed=False,
            recording_available=False,
            certificate_issued=False,
            gcp_training=False,
            protocol_training=False,
            created_by=payload.created_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._training_sessions[session_id] = session
        logger.info("Created training session %s for trial %s", session_id, payload.trial_id)
        return session

    def update_training_session(
        self, session_id: str, payload: TrainingSessionUpdate
    ) -> TrainingSession | None:
        """Update an existing training session."""
        with self._lock:
            existing = self._training_sessions.get(session_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = TrainingSession(**data)
            self._training_sessions[session_id] = updated
        return updated

    def delete_training_session(self, session_id: str) -> bool:
        """Delete a training session. Returns True if deleted."""
        with self._lock:
            if session_id in self._training_sessions:
                del self._training_sessions[session_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Presentation Materials
    # ------------------------------------------------------------------

    def list_presentation_materials(
        self,
        *,
        trial_id: str | None = None,
        meeting_id: str | None = None,
        approved_for_distribution: bool | None = None,
    ) -> list[PresentationMaterial]:
        """List presentation materials with optional filters."""
        with self._lock:
            result = list(self._presentation_materials.values())

        if trial_id is not None:
            result = [m for m in result if m.trial_id == trial_id]
        if meeting_id is not None:
            result = [m for m in result if m.meeting_id == meeting_id]
        if approved_for_distribution is not None:
            result = [m for m in result if m.approved_for_distribution == approved_for_distribution]

        return sorted(result, key=lambda m: m.created_at, reverse=True)

    def get_presentation_material(self, material_id: str) -> PresentationMaterial | None:
        """Get a single presentation material by ID."""
        with self._lock:
            return self._presentation_materials.get(material_id)

    def create_presentation_material(
        self, payload: PresentationMaterialCreate
    ) -> PresentationMaterial:
        """Create a new presentation material."""
        now = datetime.now(timezone.utc)
        material_id = f"PM-{uuid4().hex[:8].upper()}"
        material = PresentationMaterial(
            id=material_id,
            trial_id=payload.trial_id,
            meeting_id=payload.meeting_id,
            title=payload.title,
            presenter=payload.presenter,
            material_type=payload.material_type,
            version="1.0",
            slide_count=payload.slide_count,
            duration_minutes=30,
            approved_for_distribution=False,
            confidential=True,
            medical_review_completed=False,
            legal_review_completed=False,
            translated=False,
            languages=["English"],
            uploaded_by=payload.uploaded_by,
            approved_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._presentation_materials[material_id] = material
        logger.info(
            "Created presentation material %s for meeting %s", material_id, payload.meeting_id
        )
        return material

    def update_presentation_material(
        self, material_id: str, payload: PresentationMaterialUpdate
    ) -> PresentationMaterial | None:
        """Update an existing presentation material."""
        with self._lock:
            existing = self._presentation_materials.get(material_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = PresentationMaterial(**data)
            self._presentation_materials[material_id] = updated
        return updated

    def delete_presentation_material(self, material_id: str) -> bool:
        """Delete a presentation material. Returns True if deleted."""
        with self._lock:
            if material_id in self._presentation_materials:
                del self._presentation_materials[material_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Action Items
    # ------------------------------------------------------------------

    def list_action_items(
        self,
        *,
        trial_id: str | None = None,
        meeting_id: str | None = None,
        priority: ActionPriority | None = None,
        status: str | None = None,
    ) -> list[ActionItem]:
        """List action items with optional filters."""
        with self._lock:
            result = list(self._action_items.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if meeting_id is not None:
            result = [a for a in result if a.meeting_id == meeting_id]
        if priority is not None:
            result = [a for a in result if a.priority == priority]
        if status is not None:
            result = [a for a in result if a.status == status]

        return sorted(result, key=lambda a: a.due_date, reverse=True)

    def get_action_item(self, item_id: str) -> ActionItem | None:
        """Get a single action item by ID."""
        with self._lock:
            return self._action_items.get(item_id)

    def create_action_item(self, payload: ActionItemCreate) -> ActionItem:
        """Create a new action item."""
        now = datetime.now(timezone.utc)
        item_id = f"AI-{uuid4().hex[:8].upper()}"
        item = ActionItem(
            id=item_id,
            trial_id=payload.trial_id,
            meeting_id=payload.meeting_id,
            action_description=payload.action_description,
            assigned_to=payload.assigned_to,
            priority=payload.priority,
            due_date=payload.due_date,
            completed_date=None,
            status="open",
            follow_up_required=False,
            follow_up_meeting_id=None,
            escalated=False,
            escalated_to=None,
            days_overdue=None,
            created_by=payload.created_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._action_items[item_id] = item
        logger.info("Created action item %s for meeting %s", item_id, payload.meeting_id)
        return item

    def update_action_item(
        self, item_id: str, payload: ActionItemUpdate
    ) -> ActionItem | None:
        """Update an existing action item."""
        with self._lock:
            existing = self._action_items.get(item_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ActionItem(**data)
            self._action_items[item_id] = updated
        return updated

    def delete_action_item(self, item_id: str) -> bool:
        """Delete an action item. Returns True if deleted."""
        with self._lock:
            if item_id in self._action_items:
                del self._action_items[item_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> InvestigatorMeetingMetrics:
        """Compute aggregated investigator meeting metrics."""
        with self._lock:
            plans = list(self._meeting_plans.values())
            attendance = list(self._attendance_records.values())
            sessions = list(self._training_sessions.values())
            materials = list(self._presentation_materials.values())
            actions = list(self._action_items.values())

        # Meetings by type
        meetings_by_type: dict[str, int] = {}
        for p in plans:
            key = p.meeting_type.value
            meetings_by_type[key] = meetings_by_type.get(key, 0) + 1

        # Meetings by status
        meetings_by_status: dict[str, int] = {}
        for p in plans:
            key = p.status.value
            meetings_by_status[key] = meetings_by_status.get(key, 0) + 1

        # Meetings by format
        meetings_by_format: dict[str, int] = {}
        for p in plans:
            key = p.meeting_format.value
            meetings_by_format[key] = meetings_by_format.get(key, 0) + 1

        # Attendance by status
        attendance_by_status: dict[str, int] = {}
        for a in attendance:
            key = a.attendance_status.value
            attendance_by_status[key] = attendance_by_status.get(key, 0) + 1

        # Average attendance rate (attended / (attended + declined + no_show + excused + confirmed + invited))
        attended_count = sum(1 for a in attendance if a.attendance_status == AttendanceStatus.ATTENDED)
        total_final = sum(
            1
            for a in attendance
            if a.attendance_status
            in (
                AttendanceStatus.ATTENDED,
                AttendanceStatus.DECLINED,
                AttendanceStatus.NO_SHOW,
                AttendanceStatus.EXCUSED,
            )
        )
        avg_attendance_rate = round(
            (attended_count / max(1, total_final)) * 100, 1
        )

        # Training: average pass rate (only sessions with assessment)
        assessed_sessions = [s for s in sessions if s.assessment_required and s.pass_rate_pct > 0]
        avg_pass_rate = round(
            sum(s.pass_rate_pct for s in assessed_sessions) / max(1, len(assessed_sessions)), 1
        ) if assessed_sessions else 0.0

        # Presentations approved
        approved_presentations = sum(1 for m in materials if m.approved_for_distribution)

        # Action items by priority
        action_items_by_priority: dict[str, int] = {}
        for a in actions:
            key = a.priority.value
            action_items_by_priority[key] = action_items_by_priority.get(key, 0) + 1

        # Open action items
        open_action_items = sum(1 for a in actions if a.status == "open")

        # Overdue action items
        now = datetime.now(timezone.utc)
        overdue_action_items = sum(
            1 for a in actions if a.status == "open" and a.due_date < now
        )

        return InvestigatorMeetingMetrics(
            total_meetings=len(plans),
            meetings_by_type=meetings_by_type,
            meetings_by_status=meetings_by_status,
            meetings_by_format=meetings_by_format,
            total_attendance_records=len(attendance),
            attendance_by_status=attendance_by_status,
            avg_attendance_rate_pct=avg_attendance_rate,
            total_training_sessions=len(sessions),
            avg_pass_rate_pct=avg_pass_rate,
            total_presentations=len(materials),
            approved_presentations=approved_presentations,
            total_action_items=len(actions),
            action_items_by_priority=action_items_by_priority,
            open_action_items=open_action_items,
            overdue_action_items=overdue_action_items,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: InvestigatorMeetingService | None = None
_instance_lock = threading.Lock()


def get_investigator_meeting_service() -> InvestigatorMeetingService:
    """Return the singleton InvestigatorMeetingService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = InvestigatorMeetingService()
    return _instance


def reset_investigator_meeting_service() -> InvestigatorMeetingService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = InvestigatorMeetingService()
    return _instance
