"""Cross-Functional Team Management Service (CFT-MGT).

Manages cross-functional team operations: team formation, role assignments,
meeting cadence records, deliverable tracking, and performance review
with team metrics.

Usage:
    from app.services.cross_functional_team_service import (
        get_cross_functional_team_service,
    )

    svc = get_cross_functional_team_service()
    teams = svc.list_team_formations()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.cross_functional_team import (
    CrossFunctionalTeamMetrics,
    DeliverableStatus,
    DeliverableTracker,
    DeliverableTrackerCreate,
    DeliverableTrackerUpdate,
    FunctionalRole,
    MeetingCadence,
    MeetingCadenceRecord,
    MeetingCadenceRecordCreate,
    MeetingCadenceRecordUpdate,
    PerformanceReview,
    PerformanceReviewCreate,
    PerformanceReviewUpdate,
    RoleAssignment,
    RoleAssignmentCreate,
    RoleAssignmentUpdate,
    TeamFormation,
    TeamFormationCreate,
    TeamFormationUpdate,
    TeamStatus,
    TeamType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class CrossFunctionalTeamService:
    """In-memory Cross-Functional Team Management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._team_formations: dict[str, TeamFormation] = {}
        self._role_assignments: dict[str, RoleAssignment] = {}
        self._meeting_cadence_records: dict[str, MeetingCadenceRecord] = {}
        self._deliverable_trackers: dict[str, DeliverableTracker] = {}
        self._performance_reviews: dict[str, PerformanceReview] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic cross-functional team data."""
        now = datetime.now(timezone.utc)

        # --- 12 Team Formations ---
        team_data = [
            {
                "id": "TF-001",
                "trial_id": EYLEA_TRIAL,
                "team_name": "EYLEA Phase III Core Team",
                "team_type": TeamType.CORE_TEAM,
                "status": TeamStatus.ACTIVE,
                "charter_approved": True,
                "sponsor_name": "Regeneron Pharmaceuticals",
                "formation_date": now - timedelta(days=365),
                "target_completion_date": now + timedelta(days=180),
                "actual_completion_date": None,
                "max_members": 15,
                "current_members": 12,
                "objectives": [
                    "Oversee EYLEA Phase III pivotal trial execution",
                    "Ensure regulatory milestone adherence",
                    "Coordinate cross-functional deliverables",
                ],
                "created_by": "Dr. Sarah Chen",
                "notes": "Core team established at trial initiation.",
                "created_at": now - timedelta(days=365),
            },
            {
                "id": "TF-002",
                "trial_id": EYLEA_TRIAL,
                "team_name": "EYLEA Safety Governance Board",
                "team_type": TeamType.GOVERNANCE,
                "status": TeamStatus.ACTIVE,
                "charter_approved": True,
                "sponsor_name": "Regeneron Pharmaceuticals",
                "formation_date": now - timedelta(days=350),
                "target_completion_date": now + timedelta(days=180),
                "actual_completion_date": None,
                "max_members": 8,
                "current_members": 7,
                "objectives": [
                    "Review all safety data on a biweekly basis",
                    "Provide oversight on DSMB communications",
                    "Ensure pharmacovigilance compliance",
                ],
                "created_by": "Dr. James Wright",
                "notes": "Reports to the EYLEA Core Team.",
                "created_at": now - timedelta(days=350),
            },
            {
                "id": "TF-003",
                "trial_id": EYLEA_TRIAL,
                "team_name": "EYLEA Biostatistics Sub-Team",
                "team_type": TeamType.SUB_TEAM,
                "status": TeamStatus.ACTIVE,
                "charter_approved": True,
                "sponsor_name": "Regeneron Pharmaceuticals",
                "formation_date": now - timedelta(days=340),
                "target_completion_date": now + timedelta(days=200),
                "actual_completion_date": None,
                "max_members": 6,
                "current_members": 5,
                "objectives": [
                    "Develop statistical analysis plan",
                    "Perform interim and final analyses",
                    "Support DSMB with unblinded data",
                ],
                "created_by": "Dr. Sarah Chen",
                "notes": None,
                "created_at": now - timedelta(days=340),
            },
            {
                "id": "TF-004",
                "trial_id": DUPIXENT_TRIAL,
                "team_name": "DUPIXENT Atopic Dermatitis Core Team",
                "team_type": TeamType.CORE_TEAM,
                "status": TeamStatus.ACTIVE,
                "charter_approved": True,
                "sponsor_name": "Regeneron / Sanofi",
                "formation_date": now - timedelta(days=300),
                "target_completion_date": now + timedelta(days=365),
                "actual_completion_date": None,
                "max_members": 18,
                "current_members": 15,
                "objectives": [
                    "Lead DUPIXENT AD expansion trial",
                    "Manage partnership deliverables with Sanofi",
                    "Coordinate global regulatory submissions",
                ],
                "created_by": "Dr. Maria Lopez",
                "notes": "Joint Regeneron-Sanofi team structure.",
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "TF-005",
                "trial_id": DUPIXENT_TRIAL,
                "team_name": "DUPIXENT Advisory Committee",
                "team_type": TeamType.ADVISORY,
                "status": TeamStatus.ACTIVE,
                "charter_approved": True,
                "sponsor_name": "Regeneron / Sanofi",
                "formation_date": now - timedelta(days=280),
                "target_completion_date": None,
                "actual_completion_date": None,
                "max_members": 10,
                "current_members": 8,
                "objectives": [
                    "Provide scientific guidance on trial design",
                    "Review efficacy endpoints quarterly",
                    "Advise on patient-reported outcome measures",
                ],
                "created_by": "Dr. Robert Kim",
                "notes": "External KOL advisory panel.",
                "created_at": now - timedelta(days=280),
            },
            {
                "id": "TF-006",
                "trial_id": DUPIXENT_TRIAL,
                "team_name": "DUPIXENT Data Management Task Force",
                "team_type": TeamType.TASK_FORCE,
                "status": TeamStatus.ACTIVE,
                "charter_approved": True,
                "sponsor_name": "Regeneron / Sanofi",
                "formation_date": now - timedelta(days=200),
                "target_completion_date": now + timedelta(days=90),
                "actual_completion_date": None,
                "max_members": 8,
                "current_members": 6,
                "objectives": [
                    "Resolve data quality issues from site audits",
                    "Implement new EDC validation rules",
                    "Complete database lock preparation",
                ],
                "created_by": "Dr. Maria Lopez",
                "notes": "Time-limited task force for data remediation.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "TF-007",
                "trial_id": LIBTAYO_TRIAL,
                "team_name": "LIBTAYO Immuno-Oncology Core Team",
                "team_type": TeamType.CORE_TEAM,
                "status": TeamStatus.ACTIVE,
                "charter_approved": True,
                "sponsor_name": "Regeneron Pharmaceuticals",
                "formation_date": now - timedelta(days=400),
                "target_completion_date": now + timedelta(days=300),
                "actual_completion_date": None,
                "max_members": 20,
                "current_members": 17,
                "objectives": [
                    "Drive LIBTAYO IO combination trial strategy",
                    "Manage multi-arm adaptive design execution",
                    "Coordinate companion diagnostics development",
                ],
                "created_by": "Dr. Angela Park",
                "notes": "Largest cross-functional team in the portfolio.",
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "TF-008",
                "trial_id": LIBTAYO_TRIAL,
                "team_name": "LIBTAYO Regulatory Strategy Sub-Team",
                "team_type": TeamType.SUB_TEAM,
                "status": TeamStatus.ACTIVE,
                "charter_approved": True,
                "sponsor_name": "Regeneron Pharmaceuticals",
                "formation_date": now - timedelta(days=380),
                "target_completion_date": now + timedelta(days=300),
                "actual_completion_date": None,
                "max_members": 6,
                "current_members": 5,
                "objectives": [
                    "Prepare FDA Breakthrough Therapy application",
                    "Manage rolling NDA submission strategy",
                    "Coordinate with EMA for conditional approval",
                ],
                "created_by": "Dr. Angela Park",
                "notes": None,
                "created_at": now - timedelta(days=380),
            },
            {
                "id": "TF-009",
                "trial_id": LIBTAYO_TRIAL,
                "team_name": "LIBTAYO Extended Operations Team",
                "team_type": TeamType.EXTENDED_TEAM,
                "status": TeamStatus.ACTIVE,
                "charter_approved": True,
                "sponsor_name": "Regeneron Pharmaceuticals",
                "formation_date": now - timedelta(days=360),
                "target_completion_date": now + timedelta(days=300),
                "actual_completion_date": None,
                "max_members": 25,
                "current_members": 20,
                "objectives": [
                    "Coordinate CRO activities across 15 countries",
                    "Manage supply chain logistics for investigational product",
                    "Support local regulatory submissions",
                ],
                "created_by": "Dr. Angela Park",
                "notes": "Includes CRO representatives and local affiliates.",
                "created_at": now - timedelta(days=360),
            },
            {
                "id": "TF-010",
                "trial_id": EYLEA_TRIAL,
                "team_name": "EYLEA Publication Planning Committee",
                "team_type": TeamType.ADVISORY,
                "status": TeamStatus.FORMING,
                "charter_approved": False,
                "sponsor_name": "Regeneron Pharmaceuticals",
                "formation_date": now - timedelta(days=30),
                "target_completion_date": now + timedelta(days=365),
                "actual_completion_date": None,
                "max_members": 10,
                "current_members": 3,
                "objectives": [
                    "Develop publication strategy for pivotal trial results",
                    "Coordinate abstract submissions to major conferences",
                ],
                "created_by": "Dr. Sarah Chen",
                "notes": "In formation; awaiting charter approval.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "TF-011",
                "trial_id": DUPIXENT_TRIAL,
                "team_name": "DUPIXENT Legacy Study Close-Out",
                "team_type": TeamType.TASK_FORCE,
                "status": TeamStatus.DISBANDED,
                "charter_approved": True,
                "sponsor_name": "Regeneron / Sanofi",
                "formation_date": now - timedelta(days=500),
                "target_completion_date": now - timedelta(days=100),
                "actual_completion_date": now - timedelta(days=105),
                "max_members": 6,
                "current_members": 0,
                "objectives": [
                    "Complete legacy study database lock",
                    "Archive TMF documents",
                    "Finalize CSR for legacy indications",
                ],
                "created_by": "Dr. Maria Lopez",
                "notes": "Successfully disbanded after deliverables completed.",
                "created_at": now - timedelta(days=500),
            },
            {
                "id": "TF-012",
                "trial_id": LIBTAYO_TRIAL,
                "team_name": "LIBTAYO Combination Therapy Task Force",
                "team_type": TeamType.TASK_FORCE,
                "status": TeamStatus.ON_HOLD,
                "charter_approved": True,
                "sponsor_name": "Regeneron Pharmaceuticals",
                "formation_date": now - timedelta(days=90),
                "target_completion_date": now + timedelta(days=180),
                "actual_completion_date": None,
                "max_members": 10,
                "current_members": 7,
                "objectives": [
                    "Evaluate ipilimumab combination arm feasibility",
                    "Prepare protocol amendment for combination arm",
                ],
                "created_by": "Dr. Angela Park",
                "notes": "On hold pending regulatory feedback on combination arm.",
                "created_at": now - timedelta(days=90),
            },
        ]

        for t in team_data:
            self._team_formations[t["id"]] = TeamFormation(**t)

        # --- 12 Role Assignments ---
        role_data = [
            {
                "id": "RA-001",
                "trial_id": EYLEA_TRIAL,
                "team_id": "TF-001",
                "member_name": "Dr. Sarah Chen",
                "functional_role": FunctionalRole.CLINICAL_LEAD,
                "department": "Clinical Development",
                "is_primary": True,
                "start_date": now - timedelta(days=365),
                "end_date": None,
                "time_commitment_pct": 80.0,
                "backup_member": "Dr. Emily Torres",
                "responsibilities": [
                    "Lead clinical strategy for EYLEA Phase III",
                    "Chair weekly core team meetings",
                    "Provide clinical input on protocol amendments",
                ],
                "assigned_by": "VP Clinical Development",
                "notes": "Lead clinical investigator for the trial.",
                "created_at": now - timedelta(days=365),
            },
            {
                "id": "RA-002",
                "trial_id": EYLEA_TRIAL,
                "team_id": "TF-001",
                "member_name": "Dr. James Wright",
                "functional_role": FunctionalRole.SAFETY_OFFICER,
                "department": "Pharmacovigilance",
                "is_primary": True,
                "start_date": now - timedelta(days=365),
                "end_date": None,
                "time_commitment_pct": 60.0,
                "backup_member": "Dr. Lisa Park",
                "responsibilities": [
                    "Review all SAE reports within 24 hours",
                    "Chair safety governance board meetings",
                    "Prepare DSUR and safety narratives",
                ],
                "assigned_by": "VP Clinical Development",
                "notes": None,
                "created_at": now - timedelta(days=365),
            },
            {
                "id": "RA-003",
                "trial_id": EYLEA_TRIAL,
                "team_id": "TF-003",
                "member_name": "Dr. Wei Zhang",
                "functional_role": FunctionalRole.BIOSTATISTICIAN,
                "department": "Biostatistics",
                "is_primary": True,
                "start_date": now - timedelta(days=340),
                "end_date": None,
                "time_commitment_pct": 70.0,
                "backup_member": None,
                "responsibilities": [
                    "Develop and maintain statistical analysis plan",
                    "Perform interim analyses under DSMB charter",
                    "Validate adaptive design operating characteristics",
                ],
                "assigned_by": "Dr. Sarah Chen",
                "notes": "Also serves as unblinded statistician.",
                "created_at": now - timedelta(days=340),
            },
            {
                "id": "RA-004",
                "trial_id": EYLEA_TRIAL,
                "team_id": "TF-002",
                "member_name": "Dr. Michael Rivera",
                "functional_role": FunctionalRole.MEDICAL_MONITOR,
                "department": "Medical Affairs",
                "is_primary": True,
                "start_date": now - timedelta(days=350),
                "end_date": None,
                "time_commitment_pct": 50.0,
                "backup_member": "Dr. Karen Patel",
                "responsibilities": [
                    "Perform ongoing medical review of patient data",
                    "Adjudicate protocol deviations",
                    "Provide medical guidance to clinical sites",
                ],
                "assigned_by": "Dr. James Wright",
                "notes": None,
                "created_at": now - timedelta(days=350),
            },
            {
                "id": "RA-005",
                "trial_id": DUPIXENT_TRIAL,
                "team_id": "TF-004",
                "member_name": "Dr. Maria Lopez",
                "functional_role": FunctionalRole.CLINICAL_LEAD,
                "department": "Clinical Development",
                "is_primary": True,
                "start_date": now - timedelta(days=300),
                "end_date": None,
                "time_commitment_pct": 75.0,
                "backup_member": "Dr. Thomas Green",
                "responsibilities": [
                    "Lead DUPIXENT AD expansion program",
                    "Coordinate with Sanofi alliance team",
                    "Oversee global site activation strategy",
                ],
                "assigned_by": "SVP Clinical Operations",
                "notes": "Joint appointment with Sanofi.",
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "RA-006",
                "trial_id": DUPIXENT_TRIAL,
                "team_id": "TF-004",
                "member_name": "Dr. Robert Kim",
                "functional_role": FunctionalRole.REGULATORY_LEAD,
                "department": "Regulatory Affairs",
                "is_primary": True,
                "start_date": now - timedelta(days=300),
                "end_date": None,
                "time_commitment_pct": 60.0,
                "backup_member": None,
                "responsibilities": [
                    "Manage FDA and EMA regulatory interactions",
                    "Prepare sNDA/sBLA submission packages",
                    "Track regulatory commitments and timelines",
                ],
                "assigned_by": "SVP Clinical Operations",
                "notes": None,
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "RA-007",
                "trial_id": DUPIXENT_TRIAL,
                "team_id": "TF-006",
                "member_name": "Jennifer Walsh",
                "functional_role": FunctionalRole.DATA_MANAGER,
                "department": "Data Management",
                "is_primary": True,
                "start_date": now - timedelta(days=200),
                "end_date": None,
                "time_commitment_pct": 100.0,
                "backup_member": "David Chang",
                "responsibilities": [
                    "Lead data cleaning and query resolution",
                    "Implement EDC validation rules",
                    "Prepare database for interim lock",
                ],
                "assigned_by": "Dr. Maria Lopez",
                "notes": "Full-time assignment for data remediation task force.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "RA-008",
                "trial_id": DUPIXENT_TRIAL,
                "team_id": "TF-004",
                "member_name": "Dr. Priya Sharma",
                "functional_role": FunctionalRole.SAFETY_OFFICER,
                "department": "Pharmacovigilance",
                "is_primary": True,
                "start_date": now - timedelta(days=290),
                "end_date": None,
                "time_commitment_pct": 50.0,
                "backup_member": None,
                "responsibilities": [
                    "Monitor safety signals for DUPIXENT indications",
                    "Prepare periodic safety update reports",
                    "Coordinate with Sanofi pharmacovigilance",
                ],
                "assigned_by": "SVP Clinical Operations",
                "notes": None,
                "created_at": now - timedelta(days=290),
            },
            {
                "id": "RA-009",
                "trial_id": LIBTAYO_TRIAL,
                "team_id": "TF-007",
                "member_name": "Dr. Angela Park",
                "functional_role": FunctionalRole.CLINICAL_LEAD,
                "department": "Oncology Clinical Development",
                "is_primary": True,
                "start_date": now - timedelta(days=400),
                "end_date": None,
                "time_commitment_pct": 90.0,
                "backup_member": "Dr. Nathan Brooks",
                "responsibilities": [
                    "Lead LIBTAYO IO combination strategy",
                    "Chair core team and governance meetings",
                    "Drive adaptive design decision-making",
                ],
                "assigned_by": "CSO Oncology",
                "notes": "Senior clinical lead with IO expertise.",
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "RA-010",
                "trial_id": LIBTAYO_TRIAL,
                "team_id": "TF-007",
                "member_name": "Dr. David Nakamura",
                "functional_role": FunctionalRole.BIOSTATISTICIAN,
                "department": "Biostatistics",
                "is_primary": True,
                "start_date": now - timedelta(days=400),
                "end_date": None,
                "time_commitment_pct": 75.0,
                "backup_member": "Dr. Rachel Moore",
                "responsibilities": [
                    "Design and validate multi-arm adaptive trial simulations",
                    "Conduct planned interim analyses",
                    "Support DSMB with statistical reports",
                ],
                "assigned_by": "CSO Oncology",
                "notes": None,
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "RA-011",
                "trial_id": LIBTAYO_TRIAL,
                "team_id": "TF-008",
                "member_name": "Dr. Christine Yamamoto",
                "functional_role": FunctionalRole.REGULATORY_LEAD,
                "department": "Regulatory Affairs - Oncology",
                "is_primary": True,
                "start_date": now - timedelta(days=380),
                "end_date": None,
                "time_commitment_pct": 65.0,
                "backup_member": None,
                "responsibilities": [
                    "Manage Breakthrough Therapy designation application",
                    "Coordinate rolling NDA submission",
                    "Prepare regulatory strategy for combination arm",
                ],
                "assigned_by": "Dr. Angela Park",
                "notes": None,
                "created_at": now - timedelta(days=380),
            },
            {
                "id": "RA-012",
                "trial_id": LIBTAYO_TRIAL,
                "team_id": "TF-007",
                "member_name": "Dr. Mark Sullivan",
                "functional_role": FunctionalRole.MEDICAL_MONITOR,
                "department": "Oncology Medical Affairs",
                "is_primary": False,
                "start_date": now - timedelta(days=360),
                "end_date": None,
                "time_commitment_pct": 40.0,
                "backup_member": None,
                "responsibilities": [
                    "Support medical monitoring across global sites",
                    "Review imaging-based response assessments",
                    "Adjudicate immune-related adverse events",
                ],
                "assigned_by": "Dr. Angela Park",
                "notes": "Secondary medical monitor; complements primary on-call.",
                "created_at": now - timedelta(days=360),
            },
        ]

        for r in role_data:
            self._role_assignments[r["id"]] = RoleAssignment(**r)

        # --- 12 Meeting Cadence Records ---
        meeting_data = [
            {
                "id": "MC-001",
                "trial_id": EYLEA_TRIAL,
                "team_id": "TF-001",
                "cadence": MeetingCadence.WEEKLY,
                "meeting_day": "Tuesday",
                "meeting_time": "10:00",
                "duration_minutes": 60,
                "platform": "Microsoft Teams",
                "recurring": True,
                "total_meetings_held": 48,
                "average_attendance": 10,
                "minutes_distributed": True,
                "next_meeting_date": now + timedelta(days=3),
                "managed_by": "Dr. Sarah Chen",
                "notes": "Core team weekly standup.",
                "created_at": now - timedelta(days=365),
            },
            {
                "id": "MC-002",
                "trial_id": EYLEA_TRIAL,
                "team_id": "TF-002",
                "cadence": MeetingCadence.BIWEEKLY,
                "meeting_day": "Thursday",
                "meeting_time": "14:00",
                "duration_minutes": 90,
                "platform": "Microsoft Teams",
                "recurring": True,
                "total_meetings_held": 24,
                "average_attendance": 6,
                "minutes_distributed": True,
                "next_meeting_date": now + timedelta(days=5),
                "managed_by": "Dr. James Wright",
                "notes": "Safety governance board review.",
                "created_at": now - timedelta(days=350),
            },
            {
                "id": "MC-003",
                "trial_id": EYLEA_TRIAL,
                "team_id": "TF-003",
                "cadence": MeetingCadence.WEEKLY,
                "meeting_day": "Monday",
                "meeting_time": "09:00",
                "duration_minutes": 45,
                "platform": "Zoom",
                "recurring": True,
                "total_meetings_held": 44,
                "average_attendance": 4,
                "minutes_distributed": True,
                "next_meeting_date": now + timedelta(days=1),
                "managed_by": "Dr. Wei Zhang",
                "notes": "Biostatistics sub-team working session.",
                "created_at": now - timedelta(days=340),
            },
            {
                "id": "MC-004",
                "trial_id": DUPIXENT_TRIAL,
                "team_id": "TF-004",
                "cadence": MeetingCadence.WEEKLY,
                "meeting_day": "Wednesday",
                "meeting_time": "11:00",
                "duration_minutes": 60,
                "platform": "Microsoft Teams",
                "recurring": True,
                "total_meetings_held": 38,
                "average_attendance": 12,
                "minutes_distributed": True,
                "next_meeting_date": now + timedelta(days=2),
                "managed_by": "Dr. Maria Lopez",
                "notes": "DUPIXENT core team weekly. Joint Regeneron-Sanofi call.",
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "MC-005",
                "trial_id": DUPIXENT_TRIAL,
                "team_id": "TF-005",
                "cadence": MeetingCadence.QUARTERLY,
                "meeting_day": "Friday",
                "meeting_time": "15:00",
                "duration_minutes": 120,
                "platform": "Zoom",
                "recurring": True,
                "total_meetings_held": 4,
                "average_attendance": 7,
                "minutes_distributed": True,
                "next_meeting_date": now + timedelta(days=45),
                "managed_by": "Dr. Robert Kim",
                "notes": "External advisory committee quarterly review.",
                "created_at": now - timedelta(days=280),
            },
            {
                "id": "MC-006",
                "trial_id": DUPIXENT_TRIAL,
                "team_id": "TF-006",
                "cadence": MeetingCadence.BIWEEKLY,
                "meeting_day": "Monday",
                "meeting_time": "13:00",
                "duration_minutes": 60,
                "platform": "Microsoft Teams",
                "recurring": True,
                "total_meetings_held": 12,
                "average_attendance": 5,
                "minutes_distributed": True,
                "next_meeting_date": now + timedelta(days=8),
                "managed_by": "Jennifer Walsh",
                "notes": "Data management task force biweekly sync.",
                "created_at": now - timedelta(days=200),
            },
            {
                "id": "MC-007",
                "trial_id": LIBTAYO_TRIAL,
                "team_id": "TF-007",
                "cadence": MeetingCadence.WEEKLY,
                "meeting_day": "Tuesday",
                "meeting_time": "09:00",
                "duration_minutes": 75,
                "platform": "Microsoft Teams",
                "recurring": True,
                "total_meetings_held": 52,
                "average_attendance": 14,
                "minutes_distributed": True,
                "next_meeting_date": now + timedelta(days=3),
                "managed_by": "Dr. Angela Park",
                "notes": "LIBTAYO core team weekly. Largest recurring meeting.",
                "created_at": now - timedelta(days=400),
            },
            {
                "id": "MC-008",
                "trial_id": LIBTAYO_TRIAL,
                "team_id": "TF-008",
                "cadence": MeetingCadence.BIWEEKLY,
                "meeting_day": "Wednesday",
                "meeting_time": "16:00",
                "duration_minutes": 60,
                "platform": "Microsoft Teams",
                "recurring": True,
                "total_meetings_held": 26,
                "average_attendance": 4,
                "minutes_distributed": True,
                "next_meeting_date": now + timedelta(days=6),
                "managed_by": "Dr. Christine Yamamoto",
                "notes": "Regulatory strategy sub-team.",
                "created_at": now - timedelta(days=380),
            },
            {
                "id": "MC-009",
                "trial_id": LIBTAYO_TRIAL,
                "team_id": "TF-009",
                "cadence": MeetingCadence.MONTHLY,
                "meeting_day": "Thursday",
                "meeting_time": "08:00",
                "duration_minutes": 90,
                "platform": "Zoom",
                "recurring": True,
                "total_meetings_held": 11,
                "average_attendance": 16,
                "minutes_distributed": True,
                "next_meeting_date": now + timedelta(days=18),
                "managed_by": "Dr. Angela Park",
                "notes": "Extended ops monthly. Multi-timezone scheduling.",
                "created_at": now - timedelta(days=360),
            },
            {
                "id": "MC-010",
                "trial_id": EYLEA_TRIAL,
                "team_id": "TF-010",
                "cadence": MeetingCadence.AD_HOC,
                "meeting_day": "Friday",
                "meeting_time": "11:00",
                "duration_minutes": 60,
                "platform": "Microsoft Teams",
                "recurring": False,
                "total_meetings_held": 2,
                "average_attendance": 3,
                "minutes_distributed": False,
                "next_meeting_date": None,
                "managed_by": "Dr. Sarah Chen",
                "notes": "Publication committee kick-off meetings.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "MC-011",
                "trial_id": LIBTAYO_TRIAL,
                "team_id": "TF-012",
                "cadence": MeetingCadence.WEEKLY,
                "meeting_day": "Friday",
                "meeting_time": "10:00",
                "duration_minutes": 45,
                "platform": "Microsoft Teams",
                "recurring": True,
                "total_meetings_held": 8,
                "average_attendance": 5,
                "minutes_distributed": True,
                "next_meeting_date": None,
                "managed_by": "Dr. Angela Park",
                "notes": "Combination therapy TF - currently on hold.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "MC-012",
                "trial_id": DUPIXENT_TRIAL,
                "team_id": "TF-004",
                "cadence": MeetingCadence.MONTHLY,
                "meeting_day": "Thursday",
                "meeting_time": "10:00",
                "duration_minutes": 120,
                "platform": "In-Person + Teams Hybrid",
                "recurring": True,
                "total_meetings_held": 9,
                "average_attendance": 14,
                "minutes_distributed": True,
                "next_meeting_date": now + timedelta(days=20),
                "managed_by": "Dr. Maria Lopez",
                "notes": "Monthly deep-dive operational review.",
                "created_at": now - timedelta(days=270),
            },
        ]

        for m in meeting_data:
            self._meeting_cadence_records[m["id"]] = MeetingCadenceRecord(**m)

        # --- 12 Deliverable Trackers ---
        deliverable_data = [
            {
                "id": "DT-001",
                "trial_id": EYLEA_TRIAL,
                "team_id": "TF-001",
                "deliverable_name": "EYLEA Phase III Protocol Final",
                "description": "Finalize pivotal trial protocol with all amendments incorporated.",
                "status": DeliverableStatus.APPROVED,
                "owner": "Dr. Sarah Chen",
                "due_date": now - timedelta(days=300),
                "completed_date": now - timedelta(days=305),
                "priority": "high",
                "dependency_ids": [],
                "pct_complete": 100.0,
                "review_required": True,
                "reviewer": "VP Clinical Development",
                "created_by": "Dr. Sarah Chen",
                "notes": "Completed ahead of schedule.",
                "created_at": now - timedelta(days=365),
            },
            {
                "id": "DT-002",
                "trial_id": EYLEA_TRIAL,
                "team_id": "TF-003",
                "deliverable_name": "Statistical Analysis Plan v2.0",
                "description": "Updated SAP reflecting adaptive design modifications and revised endpoints.",
                "status": DeliverableStatus.UNDER_REVIEW,
                "owner": "Dr. Wei Zhang",
                "due_date": now + timedelta(days=14),
                "completed_date": None,
                "priority": "high",
                "dependency_ids": ["DT-001"],
                "pct_complete": 85.0,
                "review_required": True,
                "reviewer": "Dr. Sarah Chen",
                "created_by": "Dr. Wei Zhang",
                "notes": "Awaiting clinical lead review.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "DT-003",
                "trial_id": EYLEA_TRIAL,
                "team_id": "TF-002",
                "deliverable_name": "Annual DSUR Report",
                "description": "Development Safety Update Report for regulatory submission.",
                "status": DeliverableStatus.IN_PROGRESS,
                "owner": "Dr. James Wright",
                "due_date": now + timedelta(days=30),
                "completed_date": None,
                "priority": "high",
                "dependency_ids": [],
                "pct_complete": 60.0,
                "review_required": True,
                "reviewer": "VP Pharmacovigilance",
                "created_by": "Dr. James Wright",
                "notes": "Safety narratives 75% complete.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "DT-004",
                "trial_id": DUPIXENT_TRIAL,
                "team_id": "TF-004",
                "deliverable_name": "DUPIXENT Global Enrollment Report",
                "description": "Comprehensive enrollment status report across all regions.",
                "status": DeliverableStatus.IN_PROGRESS,
                "owner": "Dr. Maria Lopez",
                "due_date": now + timedelta(days=7),
                "completed_date": None,
                "priority": "medium",
                "dependency_ids": [],
                "pct_complete": 70.0,
                "review_required": True,
                "reviewer": "SVP Clinical Operations",
                "created_by": "Dr. Maria Lopez",
                "notes": "EU region data pending from Sanofi.",
                "created_at": now - timedelta(days=21),
            },
            {
                "id": "DT-005",
                "trial_id": DUPIXENT_TRIAL,
                "team_id": "TF-006",
                "deliverable_name": "EDC Validation Rules Update",
                "description": "Implement 45 new edit checks based on audit findings.",
                "status": DeliverableStatus.IN_PROGRESS,
                "owner": "Jennifer Walsh",
                "due_date": now + timedelta(days=21),
                "completed_date": None,
                "priority": "high",
                "dependency_ids": [],
                "pct_complete": 55.0,
                "review_required": True,
                "reviewer": "Dr. Maria Lopez",
                "created_by": "Jennifer Walsh",
                "notes": "32 of 45 edit checks implemented and validated.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "DT-006",
                "trial_id": DUPIXENT_TRIAL,
                "team_id": "TF-004",
                "deliverable_name": "Sanofi Alliance Quarterly Report",
                "description": "Joint operational report for alliance governance committee.",
                "status": DeliverableStatus.OVERDUE,
                "owner": "Dr. Robert Kim",
                "due_date": now - timedelta(days=5),
                "completed_date": None,
                "priority": "high",
                "dependency_ids": ["DT-004"],
                "pct_complete": 40.0,
                "review_required": True,
                "reviewer": "SVP Alliance Management",
                "created_by": "Dr. Maria Lopez",
                "notes": "Delayed due to dependency on enrollment report.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "DT-007",
                "trial_id": LIBTAYO_TRIAL,
                "team_id": "TF-007",
                "deliverable_name": "LIBTAYO Adaptive Design Operating Manual",
                "description": "Comprehensive manual detailing decision rules for all adaptive features.",
                "status": DeliverableStatus.APPROVED,
                "owner": "Dr. Angela Park",
                "due_date": now - timedelta(days=200),
                "completed_date": now - timedelta(days=210),
                "priority": "critical",
                "dependency_ids": [],
                "pct_complete": 100.0,
                "review_required": True,
                "reviewer": "CSO Oncology",
                "created_by": "Dr. Angela Park",
                "notes": "Approved by governance and DSMB.",
                "created_at": now - timedelta(days=380),
            },
            {
                "id": "DT-008",
                "trial_id": LIBTAYO_TRIAL,
                "team_id": "TF-008",
                "deliverable_name": "FDA Breakthrough Therapy Application",
                "description": "Prepare and submit Breakthrough Therapy designation request.",
                "status": DeliverableStatus.IN_PROGRESS,
                "owner": "Dr. Christine Yamamoto",
                "due_date": now + timedelta(days=60),
                "completed_date": None,
                "priority": "critical",
                "dependency_ids": ["DT-007"],
                "pct_complete": 45.0,
                "review_required": True,
                "reviewer": "VP Regulatory Affairs",
                "created_by": "Dr. Angela Park",
                "notes": "Clinical benefit section drafted. CMC module in progress.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "DT-009",
                "trial_id": LIBTAYO_TRIAL,
                "team_id": "TF-009",
                "deliverable_name": "Global Site Activation Tracker",
                "description": "Maintain real-time tracker for site activation across 15 countries.",
                "status": DeliverableStatus.IN_PROGRESS,
                "owner": "CRO Project Manager",
                "due_date": now + timedelta(days=120),
                "completed_date": None,
                "priority": "medium",
                "dependency_ids": [],
                "pct_complete": 65.0,
                "review_required": False,
                "reviewer": None,
                "created_by": "Dr. Angela Park",
                "notes": "12 of 15 countries activated.",
                "created_at": now - timedelta(days=300),
            },
            {
                "id": "DT-010",
                "trial_id": LIBTAYO_TRIAL,
                "team_id": "TF-012",
                "deliverable_name": "Combination Arm Protocol Amendment",
                "description": "Draft protocol amendment for ipilimumab combination arm addition.",
                "status": DeliverableStatus.NOT_STARTED,
                "owner": "Dr. Angela Park",
                "due_date": now + timedelta(days=90),
                "completed_date": None,
                "priority": "high",
                "dependency_ids": [],
                "pct_complete": 0.0,
                "review_required": True,
                "reviewer": "CSO Oncology",
                "created_by": "Dr. Angela Park",
                "notes": "Pending regulatory feedback; team on hold.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "DT-011",
                "trial_id": EYLEA_TRIAL,
                "team_id": "TF-001",
                "deliverable_name": "Interim Analysis Report",
                "description": "Prepare comprehensive interim analysis report for DSMB review.",
                "status": DeliverableStatus.OVERDUE,
                "owner": "Dr. Wei Zhang",
                "due_date": now - timedelta(days=3),
                "completed_date": None,
                "priority": "critical",
                "dependency_ids": ["DT-002"],
                "pct_complete": 80.0,
                "review_required": True,
                "reviewer": "Dr. Sarah Chen",
                "created_by": "Dr. Sarah Chen",
                "notes": "Delayed pending SAP v2.0 finalization.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "DT-012",
                "trial_id": DUPIXENT_TRIAL,
                "team_id": "TF-005",
                "deliverable_name": "Advisory Committee Meeting Minutes",
                "description": "Document and distribute advisory committee recommendations.",
                "status": DeliverableStatus.CANCELLED,
                "owner": "Dr. Robert Kim",
                "due_date": now - timedelta(days=10),
                "completed_date": None,
                "priority": "low",
                "dependency_ids": [],
                "pct_complete": 0.0,
                "review_required": False,
                "reviewer": None,
                "created_by": "Dr. Robert Kim",
                "notes": "Cancelled; advisory meeting rescheduled to next quarter.",
                "created_at": now - timedelta(days=40),
            },
        ]

        for d in deliverable_data:
            self._deliverable_trackers[d["id"]] = DeliverableTracker(**d)

        # --- 12 Performance Reviews ---
        review_data = [
            {
                "id": "PR-001",
                "trial_id": EYLEA_TRIAL,
                "team_id": "TF-001",
                "review_period": "Q3 2025",
                "review_date": now - timedelta(days=90),
                "overall_rating": 4.5,
                "collaboration_score": 4.8,
                "delivery_score": 4.2,
                "communication_score": 4.5,
                "goals_met_pct": 92.0,
                "strengths": [
                    "Strong cross-functional collaboration",
                    "Consistent meeting cadence and follow-through",
                    "Proactive risk identification",
                ],
                "improvement_areas": [
                    "Improve vendor management response times",
                    "Strengthen documentation of decision rationale",
                ],
                "action_items": [
                    "Implement vendor SLA tracking dashboard",
                    "Create decision log template for core team",
                ],
                "reviewed_by": "VP Clinical Development",
                "acknowledged": True,
                "notes": "Strong quarter. Trial on track for primary endpoints.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "PR-002",
                "trial_id": EYLEA_TRIAL,
                "team_id": "TF-001",
                "review_period": "Q4 2025",
                "review_date": now - timedelta(days=5),
                "overall_rating": 4.7,
                "collaboration_score": 4.9,
                "delivery_score": 4.5,
                "communication_score": 4.6,
                "goals_met_pct": 95.0,
                "strengths": [
                    "Exceptional response to DSMB efficacy signal",
                    "Seamless coordination during early stop evaluation",
                    "Timely regulatory communications",
                ],
                "improvement_areas": [
                    "SAP v2.0 finalization slightly behind schedule",
                ],
                "action_items": [
                    "Expedite SAP review and approval",
                    "Begin planning for NDA submission team",
                ],
                "reviewed_by": "VP Clinical Development",
                "acknowledged": False,
                "notes": "Outstanding quarter. Team recommended for recognition award.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "PR-003",
                "trial_id": EYLEA_TRIAL,
                "team_id": "TF-002",
                "review_period": "Q4 2025",
                "review_date": now - timedelta(days=10),
                "overall_rating": 4.3,
                "collaboration_score": 4.5,
                "delivery_score": 4.0,
                "communication_score": 4.4,
                "goals_met_pct": 88.0,
                "strengths": [
                    "Thorough safety signal evaluation process",
                    "Strong DSMB communication and documentation",
                ],
                "improvement_areas": [
                    "DSUR timeline management needs improvement",
                    "More structured approach to SAE narrative reviews",
                ],
                "action_items": [
                    "Create DSUR milestone tracker with automated reminders",
                    "Implement SAE narrative review checklist",
                ],
                "reviewed_by": "VP Pharmacovigilance",
                "acknowledged": True,
                "notes": None,
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "PR-004",
                "trial_id": DUPIXENT_TRIAL,
                "team_id": "TF-004",
                "review_period": "Q3 2025",
                "review_date": now - timedelta(days=95),
                "overall_rating": 3.8,
                "collaboration_score": 3.5,
                "delivery_score": 4.0,
                "communication_score": 3.8,
                "goals_met_pct": 78.0,
                "strengths": [
                    "Enrollment targets met in US and Japan",
                    "Effective use of centralized monitoring",
                ],
                "improvement_areas": [
                    "Alliance coordination with Sanofi needs strengthening",
                    "EU enrollment significantly behind target",
                    "Meeting action item follow-up inconsistent",
                ],
                "action_items": [
                    "Establish weekly Sanofi bilateral sync",
                    "Deploy EU enrollment acceleration plan",
                    "Implement action item tracking tool",
                ],
                "reviewed_by": "SVP Clinical Operations",
                "acknowledged": True,
                "notes": "Below target on key alliance metrics. Improvement plan activated.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "PR-005",
                "trial_id": DUPIXENT_TRIAL,
                "team_id": "TF-004",
                "review_period": "Q4 2025",
                "review_date": now - timedelta(days=8),
                "overall_rating": 4.1,
                "collaboration_score": 4.0,
                "delivery_score": 4.2,
                "communication_score": 4.0,
                "goals_met_pct": 84.0,
                "strengths": [
                    "Significant improvement in Sanofi collaboration",
                    "EU enrollment gap reduced by 40%",
                    "Data quality task force showing results",
                ],
                "improvement_areas": [
                    "Alliance report still pending",
                    "Need to formalize escalation pathways",
                ],
                "action_items": [
                    "Complete alliance quarterly report within 2 weeks",
                    "Document escalation matrix and distribute to team",
                ],
                "reviewed_by": "SVP Clinical Operations",
                "acknowledged": True,
                "notes": "Notable improvement from Q3. Trend is positive.",
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "PR-006",
                "trial_id": DUPIXENT_TRIAL,
                "team_id": "TF-006",
                "review_period": "Q4 2025",
                "review_date": now - timedelta(days=12),
                "overall_rating": 3.5,
                "collaboration_score": 3.8,
                "delivery_score": 3.0,
                "communication_score": 3.7,
                "goals_met_pct": 65.0,
                "strengths": [
                    "Strong technical data management expertise",
                    "Good documentation of edit check rationale",
                ],
                "improvement_areas": [
                    "Edit check implementation behind schedule",
                    "Resource constraints impacting delivery velocity",
                    "Cross-team handoff processes need improvement",
                ],
                "action_items": [
                    "Request additional data management FTE",
                    "Implement sprint-based work planning",
                    "Create handoff checklist for cross-team deliverables",
                ],
                "reviewed_by": "Dr. Maria Lopez",
                "acknowledged": True,
                "notes": "Understaffed for scope. Resource request escalated.",
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "PR-007",
                "trial_id": LIBTAYO_TRIAL,
                "team_id": "TF-007",
                "review_period": "Q3 2025",
                "review_date": now - timedelta(days=92),
                "overall_rating": 4.6,
                "collaboration_score": 4.7,
                "delivery_score": 4.5,
                "communication_score": 4.6,
                "goals_met_pct": 93.0,
                "strengths": [
                    "Excellent adaptive design execution",
                    "Strong DSMB interaction and arm-drop decision process",
                    "Highly effective multi-arm trial coordination",
                ],
                "improvement_areas": [
                    "CRO oversight in Asia-Pacific region",
                ],
                "action_items": [
                    "Deploy regional CRO oversight lead for APAC",
                ],
                "reviewed_by": "CSO Oncology",
                "acknowledged": True,
                "notes": "Best performing team in oncology portfolio.",
                "created_at": now - timedelta(days=92),
            },
            {
                "id": "PR-008",
                "trial_id": LIBTAYO_TRIAL,
                "team_id": "TF-007",
                "review_period": "Q4 2025",
                "review_date": now - timedelta(days=3),
                "overall_rating": 4.8,
                "collaboration_score": 4.9,
                "delivery_score": 4.7,
                "communication_score": 4.8,
                "goals_met_pct": 96.0,
                "strengths": [
                    "Flawless execution of combination arm assessment",
                    "Outstanding cross-functional alignment on adaptive decisions",
                    "Regulatory strategy highly praised by FDA reviewers",
                ],
                "improvement_areas": [
                    "Documentation backlog from rapid decision cycles",
                ],
                "action_items": [
                    "Hire dedicated trial documentation coordinator",
                    "Implement real-time decision documentation protocol",
                ],
                "reviewed_by": "CSO Oncology",
                "acknowledged": False,
                "notes": "Top-rated team in the organization for Q4.",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "PR-009",
                "trial_id": LIBTAYO_TRIAL,
                "team_id": "TF-008",
                "review_period": "Q4 2025",
                "review_date": now - timedelta(days=7),
                "overall_rating": 4.2,
                "collaboration_score": 4.3,
                "delivery_score": 4.0,
                "communication_score": 4.3,
                "goals_met_pct": 85.0,
                "strengths": [
                    "Excellent FDA communication management",
                    "Thorough Breakthrough Therapy application preparation",
                ],
                "improvement_areas": [
                    "EMA parallel pathway coordination could be earlier",
                    "CMC section timeline at risk",
                ],
                "action_items": [
                    "Initiate EMA scientific advice request immediately",
                    "Assign dedicated CMC regulatory writer",
                ],
                "reviewed_by": "Dr. Angela Park",
                "acknowledged": True,
                "notes": None,
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "PR-010",
                "trial_id": LIBTAYO_TRIAL,
                "team_id": "TF-009",
                "review_period": "Q4 2025",
                "review_date": now - timedelta(days=15),
                "overall_rating": 3.9,
                "collaboration_score": 3.7,
                "delivery_score": 4.0,
                "communication_score": 4.0,
                "goals_met_pct": 80.0,
                "strengths": [
                    "Strong site activation rate in major markets",
                    "Effective investigational product supply management",
                ],
                "improvement_areas": [
                    "Timezone coordination challenges affecting response times",
                    "Local regulatory submission tracking needs automation",
                ],
                "action_items": [
                    "Implement follow-the-sun communication model",
                    "Deploy regulatory milestone tracking system",
                ],
                "reviewed_by": "Dr. Angela Park",
                "acknowledged": True,
                "notes": "Good performance given global complexity.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "PR-011",
                "trial_id": EYLEA_TRIAL,
                "team_id": "TF-003",
                "review_period": "Q4 2025",
                "review_date": now - timedelta(days=6),
                "overall_rating": 4.4,
                "collaboration_score": 4.6,
                "delivery_score": 4.2,
                "communication_score": 4.4,
                "goals_met_pct": 90.0,
                "strengths": [
                    "Rigorous statistical methodology",
                    "Excellent DSMB support and interim analysis execution",
                ],
                "improvement_areas": [
                    "SAP v2.0 delivery timeline slippage",
                ],
                "action_items": [
                    "Complete SAP v2.0 within 10 business days",
                    "Establish version control for SAP documents",
                ],
                "reviewed_by": "Dr. Sarah Chen",
                "acknowledged": True,
                "notes": None,
                "created_at": now - timedelta(days=6),
            },
            {
                "id": "PR-012",
                "trial_id": LIBTAYO_TRIAL,
                "team_id": "TF-012",
                "review_period": "Q4 2025",
                "review_date": now - timedelta(days=20),
                "overall_rating": 3.0,
                "collaboration_score": 3.2,
                "delivery_score": 2.5,
                "communication_score": 3.3,
                "goals_met_pct": 45.0,
                "strengths": [
                    "Strong initial feasibility assessment for combination",
                ],
                "improvement_areas": [
                    "Team on hold with no clear restart timeline",
                    "Key deliverables not started due to regulatory dependency",
                    "Team engagement declining during hold period",
                ],
                "action_items": [
                    "Schedule monthly keep-warm meeting during hold",
                    "Reassign team members to other active teams temporarily",
                    "Establish clear restart criteria with governance",
                ],
                "reviewed_by": "Dr. Angela Park",
                "acknowledged": True,
                "notes": "Performance impacted by external regulatory dependency. Rating reflects limited scope during hold.",
                "created_at": now - timedelta(days=20),
            },
        ]

        for r in review_data:
            self._performance_reviews[r["id"]] = PerformanceReview(**r)

    # ------------------------------------------------------------------
    # Team Formations
    # ------------------------------------------------------------------

    def list_team_formations(
        self,
        *,
        trial_id: str | None = None,
        team_type: TeamType | None = None,
        status: TeamStatus | None = None,
    ) -> list[TeamFormation]:
        """List team formations with optional filters."""
        with self._lock:
            result = list(self._team_formations.values())

        if trial_id is not None:
            result = [t for t in result if t.trial_id == trial_id]
        if team_type is not None:
            result = [t for t in result if t.team_type == team_type]
        if status is not None:
            result = [t for t in result if t.status == status]

        return sorted(result, key=lambda t: t.formation_date, reverse=True)

    def get_team_formation(self, team_id: str) -> TeamFormation | None:
        """Get a single team formation by ID."""
        with self._lock:
            return self._team_formations.get(team_id)

    def create_team_formation(self, payload: TeamFormationCreate) -> TeamFormation:
        """Create a new team formation."""
        now = datetime.now(timezone.utc)
        team_id = f"TF-{uuid4().hex[:8].upper()}"
        team = TeamFormation(
            id=team_id,
            trial_id=payload.trial_id,
            team_name=payload.team_name,
            team_type=payload.team_type,
            status=TeamStatus.FORMING,
            charter_approved=False,
            sponsor_name=payload.sponsor_name,
            formation_date=now,
            target_completion_date=None,
            actual_completion_date=None,
            max_members=payload.max_members,
            current_members=0,
            objectives=[],
            created_by=payload.created_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._team_formations[team_id] = team
        logger.info("Created team formation %s for trial %s", team_id, payload.trial_id)
        return team

    def update_team_formation(
        self, team_id: str, payload: TeamFormationUpdate
    ) -> TeamFormation | None:
        """Update an existing team formation."""
        with self._lock:
            existing = self._team_formations.get(team_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = TeamFormation(**data)
            self._team_formations[team_id] = updated
        return updated

    def delete_team_formation(self, team_id: str) -> bool:
        """Delete a team formation. Returns True if deleted."""
        with self._lock:
            if team_id in self._team_formations:
                del self._team_formations[team_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Role Assignments
    # ------------------------------------------------------------------

    def list_role_assignments(
        self,
        *,
        trial_id: str | None = None,
        team_id: str | None = None,
        functional_role: FunctionalRole | None = None,
    ) -> list[RoleAssignment]:
        """List role assignments with optional filters."""
        with self._lock:
            result = list(self._role_assignments.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if team_id is not None:
            result = [r for r in result if r.team_id == team_id]
        if functional_role is not None:
            result = [r for r in result if r.functional_role == functional_role]

        return sorted(result, key=lambda r: r.start_date, reverse=True)

    def get_role_assignment(self, assignment_id: str) -> RoleAssignment | None:
        """Get a single role assignment by ID."""
        with self._lock:
            return self._role_assignments.get(assignment_id)

    def create_role_assignment(self, payload: RoleAssignmentCreate) -> RoleAssignment:
        """Create a new role assignment."""
        now = datetime.now(timezone.utc)
        assignment_id = f"RA-{uuid4().hex[:8].upper()}"
        assignment = RoleAssignment(
            id=assignment_id,
            trial_id=payload.trial_id,
            team_id=payload.team_id,
            member_name=payload.member_name,
            functional_role=payload.functional_role,
            department=payload.department,
            is_primary=True,
            start_date=now,
            end_date=None,
            time_commitment_pct=payload.time_commitment_pct,
            backup_member=None,
            responsibilities=[],
            assigned_by=payload.assigned_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._role_assignments[assignment_id] = assignment
        logger.info("Created role assignment %s for trial %s", assignment_id, payload.trial_id)
        return assignment

    def update_role_assignment(
        self, assignment_id: str, payload: RoleAssignmentUpdate
    ) -> RoleAssignment | None:
        """Update an existing role assignment."""
        with self._lock:
            existing = self._role_assignments.get(assignment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = RoleAssignment(**data)
            self._role_assignments[assignment_id] = updated
        return updated

    def delete_role_assignment(self, assignment_id: str) -> bool:
        """Delete a role assignment. Returns True if deleted."""
        with self._lock:
            if assignment_id in self._role_assignments:
                del self._role_assignments[assignment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Meeting Cadence Records
    # ------------------------------------------------------------------

    def list_meeting_cadence_records(
        self,
        *,
        trial_id: str | None = None,
        team_id: str | None = None,
        cadence: MeetingCadence | None = None,
    ) -> list[MeetingCadenceRecord]:
        """List meeting cadence records with optional filters."""
        with self._lock:
            result = list(self._meeting_cadence_records.values())

        if trial_id is not None:
            result = [m for m in result if m.trial_id == trial_id]
        if team_id is not None:
            result = [m for m in result if m.team_id == team_id]
        if cadence is not None:
            result = [m for m in result if m.cadence == cadence]

        return sorted(result, key=lambda m: m.created_at, reverse=True)

    def get_meeting_cadence_record(self, record_id: str) -> MeetingCadenceRecord | None:
        """Get a single meeting cadence record by ID."""
        with self._lock:
            return self._meeting_cadence_records.get(record_id)

    def create_meeting_cadence_record(
        self, payload: MeetingCadenceRecordCreate
    ) -> MeetingCadenceRecord:
        """Create a new meeting cadence record."""
        now = datetime.now(timezone.utc)
        record_id = f"MC-{uuid4().hex[:8].upper()}"
        record = MeetingCadenceRecord(
            id=record_id,
            trial_id=payload.trial_id,
            team_id=payload.team_id,
            cadence=payload.cadence,
            meeting_day=payload.meeting_day,
            meeting_time="10:00",
            duration_minutes=payload.duration_minutes,
            platform="Microsoft Teams",
            recurring=True,
            total_meetings_held=0,
            average_attendance=0,
            minutes_distributed=True,
            next_meeting_date=None,
            managed_by=payload.managed_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._meeting_cadence_records[record_id] = record
        logger.info("Created meeting cadence record %s for trial %s", record_id, payload.trial_id)
        return record

    def update_meeting_cadence_record(
        self, record_id: str, payload: MeetingCadenceRecordUpdate
    ) -> MeetingCadenceRecord | None:
        """Update an existing meeting cadence record."""
        with self._lock:
            existing = self._meeting_cadence_records.get(record_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MeetingCadenceRecord(**data)
            self._meeting_cadence_records[record_id] = updated
        return updated

    def delete_meeting_cadence_record(self, record_id: str) -> bool:
        """Delete a meeting cadence record. Returns True if deleted."""
        with self._lock:
            if record_id in self._meeting_cadence_records:
                del self._meeting_cadence_records[record_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Deliverable Trackers
    # ------------------------------------------------------------------

    def list_deliverable_trackers(
        self,
        *,
        trial_id: str | None = None,
        team_id: str | None = None,
        status: DeliverableStatus | None = None,
    ) -> list[DeliverableTracker]:
        """List deliverable trackers with optional filters."""
        with self._lock:
            result = list(self._deliverable_trackers.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]
        if team_id is not None:
            result = [d for d in result if d.team_id == team_id]
        if status is not None:
            result = [d for d in result if d.status == status]

        return sorted(result, key=lambda d: d.due_date, reverse=True)

    def get_deliverable_tracker(self, deliverable_id: str) -> DeliverableTracker | None:
        """Get a single deliverable tracker by ID."""
        with self._lock:
            return self._deliverable_trackers.get(deliverable_id)

    def create_deliverable_tracker(self, payload: DeliverableTrackerCreate) -> DeliverableTracker:
        """Create a new deliverable tracker."""
        now = datetime.now(timezone.utc)
        deliverable_id = f"DT-{uuid4().hex[:8].upper()}"
        deliverable = DeliverableTracker(
            id=deliverable_id,
            trial_id=payload.trial_id,
            team_id=payload.team_id,
            deliverable_name=payload.deliverable_name,
            description=payload.description,
            status=DeliverableStatus.NOT_STARTED,
            owner=payload.owner,
            due_date=payload.due_date,
            completed_date=None,
            priority=payload.priority,
            dependency_ids=[],
            pct_complete=0.0,
            review_required=True,
            reviewer=None,
            created_by=payload.created_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._deliverable_trackers[deliverable_id] = deliverable
        logger.info(
            "Created deliverable tracker %s for trial %s", deliverable_id, payload.trial_id
        )
        return deliverable

    def update_deliverable_tracker(
        self, deliverable_id: str, payload: DeliverableTrackerUpdate
    ) -> DeliverableTracker | None:
        """Update an existing deliverable tracker."""
        with self._lock:
            existing = self._deliverable_trackers.get(deliverable_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DeliverableTracker(**data)
            self._deliverable_trackers[deliverable_id] = updated
        return updated

    def delete_deliverable_tracker(self, deliverable_id: str) -> bool:
        """Delete a deliverable tracker. Returns True if deleted."""
        with self._lock:
            if deliverable_id in self._deliverable_trackers:
                del self._deliverable_trackers[deliverable_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Performance Reviews
    # ------------------------------------------------------------------

    def list_performance_reviews(
        self,
        *,
        trial_id: str | None = None,
        team_id: str | None = None,
    ) -> list[PerformanceReview]:
        """List performance reviews with optional filters."""
        with self._lock:
            result = list(self._performance_reviews.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if team_id is not None:
            result = [r for r in result if r.team_id == team_id]

        return sorted(result, key=lambda r: r.review_date, reverse=True)

    def get_performance_review(self, review_id: str) -> PerformanceReview | None:
        """Get a single performance review by ID."""
        with self._lock:
            return self._performance_reviews.get(review_id)

    def create_performance_review(self, payload: PerformanceReviewCreate) -> PerformanceReview:
        """Create a new performance review."""
        now = datetime.now(timezone.utc)
        review_id = f"PR-{uuid4().hex[:8].upper()}"
        review = PerformanceReview(
            id=review_id,
            trial_id=payload.trial_id,
            team_id=payload.team_id,
            review_period=payload.review_period,
            review_date=now,
            overall_rating=payload.overall_rating,
            collaboration_score=payload.collaboration_score,
            delivery_score=3.0,
            communication_score=3.0,
            goals_met_pct=0.0,
            strengths=[],
            improvement_areas=[],
            action_items=[],
            reviewed_by=payload.reviewed_by,
            acknowledged=False,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._performance_reviews[review_id] = review
        logger.info("Created performance review %s for trial %s", review_id, payload.trial_id)
        return review

    def update_performance_review(
        self, review_id: str, payload: PerformanceReviewUpdate
    ) -> PerformanceReview | None:
        """Update an existing performance review."""
        with self._lock:
            existing = self._performance_reviews.get(review_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = PerformanceReview(**data)
            self._performance_reviews[review_id] = updated
        return updated

    def delete_performance_review(self, review_id: str) -> bool:
        """Delete a performance review. Returns True if deleted."""
        with self._lock:
            if review_id in self._performance_reviews:
                del self._performance_reviews[review_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> CrossFunctionalTeamMetrics:
        """Compute aggregated cross-functional team metrics."""
        with self._lock:
            teams = list(self._team_formations.values())
            assignments = list(self._role_assignments.values())
            meetings = list(self._meeting_cadence_records.values())
            deliverables = list(self._deliverable_trackers.values())
            reviews = list(self._performance_reviews.values())

        # Teams by type
        teams_by_type: dict[str, int] = {}
        for t in teams:
            key = t.team_type.value
            teams_by_type[key] = teams_by_type.get(key, 0) + 1

        # Teams by status
        teams_by_status: dict[str, int] = {}
        for t in teams:
            key = t.status.value
            teams_by_status[key] = teams_by_status.get(key, 0) + 1

        # Active teams
        active_teams = sum(1 for t in teams if t.status == TeamStatus.ACTIVE)

        # Assignments by role
        assignments_by_role: dict[str, int] = {}
        for a in assignments:
            key = a.functional_role.value
            assignments_by_role[key] = assignments_by_role.get(key, 0) + 1

        # Meetings by cadence
        meetings_by_cadence: dict[str, int] = {}
        for m in meetings:
            key = m.cadence.value
            meetings_by_cadence[key] = meetings_by_cadence.get(key, 0) + 1

        # Deliverables by status
        deliverables_by_status: dict[str, int] = {}
        for d in deliverables:
            key = d.status.value
            deliverables_by_status[key] = deliverables_by_status.get(key, 0) + 1

        # Overdue deliverables
        overdue_deliverables = sum(
            1 for d in deliverables if d.status == DeliverableStatus.OVERDUE
        )

        # Average overall rating
        ratings = [r.overall_rating for r in reviews]
        avg_overall_rating = (
            round(sum(ratings) / len(ratings), 2) if ratings else 0.0
        )

        return CrossFunctionalTeamMetrics(
            total_teams=len(teams),
            teams_by_type=teams_by_type,
            teams_by_status=teams_by_status,
            active_teams=active_teams,
            total_role_assignments=len(assignments),
            assignments_by_role=assignments_by_role,
            total_meeting_records=len(meetings),
            meetings_by_cadence=meetings_by_cadence,
            total_deliverables=len(deliverables),
            deliverables_by_status=deliverables_by_status,
            overdue_deliverables=overdue_deliverables,
            total_reviews=len(reviews),
            avg_overall_rating=avg_overall_rating,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: CrossFunctionalTeamService | None = None
_instance_lock = threading.Lock()


def get_cross_functional_team_service() -> CrossFunctionalTeamService:
    """Return the singleton CrossFunctionalTeamService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = CrossFunctionalTeamService()
    return _instance


def reset_cross_functional_team_service() -> CrossFunctionalTeamService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = CrossFunctionalTeamService()
    return _instance
