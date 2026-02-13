"""Patient Visit Tracking Service (PVT-TRK).

Manages patient visit tracking operations: visit schedules, visit adherence
records, visit window violations, missed visit follow-ups, and visit tracking
metrics.

Usage:
    from app.services.patient_visit_tracking_service import (
        get_patient_visit_tracking_service,
    )

    svc = get_patient_visit_tracking_service()
    schedules = svc.list_visit_schedules()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.patient_visit_tracking import (
    AdherenceRating,
    FollowUpStatus,
    MissedVisitFollowUp,
    MissedVisitFollowUpCreate,
    MissedVisitFollowUpUpdate,
    PatientVisitTrackingMetrics,
    ViolationSeverity,
    VisitAdherence,
    VisitAdherenceCreate,
    VisitAdherenceUpdate,
    VisitSchedule,
    VisitScheduleCreate,
    VisitScheduleUpdate,
    VisitStatus,
    VisitType,
    WindowViolation,
    WindowViolationCreate,
    WindowViolationUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class PatientVisitTrackingService:
    """In-memory Patient Visit Tracking engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._visit_schedules: dict[str, VisitSchedule] = {}
        self._visit_adherence: dict[str, VisitAdherence] = {}
        self._window_violations: dict[str, WindowViolation] = {}
        self._missed_visit_follow_ups: dict[str, MissedVisitFollowUp] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic patient visit tracking data."""
        now = datetime.now(timezone.utc)

        # --- 12 Visit Schedules ---
        schedules_data = [
            {
                "id": "VS-001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-NY-001",
                "visit_type": VisitType.SCREENING,
                "visit_number": 1,
                "visit_name": "Screening Visit",
                "visit_status": VisitStatus.COMPLETED,
                "scheduled_date": now - timedelta(days=90),
                "actual_date": now - timedelta(days=90),
                "window_open_date": now - timedelta(days=93),
                "window_close_date": now - timedelta(days=87),
                "duration_minutes": 120,
                "investigator_name": "Dr. Sarah Chen",
                "location": "Building A, Room 102",
                "procedures_planned": 8,
                "procedures_completed": 8,
                "notes": "Screening completed successfully. All assessments done.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "VS-002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-NY-001",
                "visit_type": VisitType.BASELINE,
                "visit_number": 2,
                "visit_name": "Baseline Visit",
                "visit_status": VisitStatus.COMPLETED,
                "scheduled_date": now - timedelta(days=75),
                "actual_date": now - timedelta(days=74),
                "window_open_date": now - timedelta(days=78),
                "window_close_date": now - timedelta(days=72),
                "duration_minutes": 180,
                "investigator_name": "Dr. Sarah Chen",
                "location": "Building A, Room 102",
                "procedures_planned": 12,
                "procedures_completed": 12,
                "notes": "Baseline assessments complete. Subject randomized.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "VS-003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E002",
                "site_id": "SITE-NY-001",
                "visit_type": VisitType.TREATMENT,
                "visit_number": 3,
                "visit_name": "Week 4 Treatment Visit",
                "visit_status": VisitStatus.COMPLETED,
                "scheduled_date": now - timedelta(days=60),
                "actual_date": now - timedelta(days=59),
                "window_open_date": now - timedelta(days=63),
                "window_close_date": now - timedelta(days=57),
                "duration_minutes": 90,
                "investigator_name": "Dr. James Rodriguez",
                "location": "Building B, Room 205",
                "procedures_planned": 6,
                "procedures_completed": 6,
                "notes": "Treatment administered per protocol. No adverse events.",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "VS-004",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E003",
                "site_id": "SITE-LA-001",
                "visit_type": VisitType.TREATMENT,
                "visit_number": 4,
                "visit_name": "Week 8 Treatment Visit",
                "visit_status": VisitStatus.MISSED,
                "scheduled_date": now - timedelta(days=30),
                "actual_date": None,
                "window_open_date": now - timedelta(days=33),
                "window_close_date": now - timedelta(days=27),
                "duration_minutes": 90,
                "investigator_name": "Dr. Maria Lopez",
                "location": "Building C, Room 301",
                "procedures_planned": 6,
                "procedures_completed": 0,
                "notes": "Subject did not attend. Contact attempts initiated.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "VS-005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-CHI-001",
                "visit_type": VisitType.SCREENING,
                "visit_number": 1,
                "visit_name": "Screening Visit",
                "visit_status": VisitStatus.COMPLETED,
                "scheduled_date": now - timedelta(days=80),
                "actual_date": now - timedelta(days=80),
                "window_open_date": now - timedelta(days=83),
                "window_close_date": now - timedelta(days=77),
                "duration_minutes": 120,
                "investigator_name": "Dr. Karen Liu",
                "location": "Clinic Suite 4A",
                "procedures_planned": 10,
                "procedures_completed": 10,
                "notes": "Full screening panel completed. Eligible for randomization.",
                "created_at": now - timedelta(days=85),
            },
            {
                "id": "VS-006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D002",
                "site_id": "SITE-CHI-001",
                "visit_type": VisitType.BASELINE,
                "visit_number": 2,
                "visit_name": "Baseline Visit",
                "visit_status": VisitStatus.PARTIALLY_COMPLETED,
                "scheduled_date": now - timedelta(days=55),
                "actual_date": now - timedelta(days=55),
                "window_open_date": now - timedelta(days=58),
                "window_close_date": now - timedelta(days=52),
                "duration_minutes": 150,
                "investigator_name": "Dr. Karen Liu",
                "location": "Clinic Suite 4A",
                "procedures_planned": 10,
                "procedures_completed": 7,
                "notes": "Subject felt unwell during visit. 3 procedures deferred to unscheduled visit.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "VS-007",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-CHI-001",
                "visit_type": VisitType.TREATMENT,
                "visit_number": 3,
                "visit_name": "Week 4 Treatment Visit",
                "visit_status": VisitStatus.RESCHEDULED,
                "scheduled_date": now - timedelta(days=40),
                "actual_date": None,
                "window_open_date": now - timedelta(days=43),
                "window_close_date": now - timedelta(days=37),
                "duration_minutes": 90,
                "investigator_name": "Dr. Karen Liu",
                "location": "Clinic Suite 4A",
                "procedures_planned": 6,
                "procedures_completed": 0,
                "notes": "Rescheduled due to site holiday. New date within window.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "VS-008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D003",
                "site_id": "SITE-BOS-001",
                "visit_type": VisitType.SCREENING,
                "visit_number": 1,
                "visit_name": "Screening Visit",
                "visit_status": VisitStatus.SCHEDULED,
                "scheduled_date": now + timedelta(days=5),
                "actual_date": None,
                "window_open_date": now + timedelta(days=2),
                "window_close_date": now + timedelta(days=8),
                "duration_minutes": 120,
                "investigator_name": "Dr. Alex Yun",
                "location": "Boston Clinical Center, Room 201",
                "procedures_planned": 10,
                "procedures_completed": 0,
                "notes": "Upcoming screening visit scheduled.",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "VS-009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-HOU-001",
                "visit_type": VisitType.BASELINE,
                "visit_number": 1,
                "visit_name": "Baseline Visit",
                "visit_status": VisitStatus.COMPLETED,
                "scheduled_date": now - timedelta(days=70),
                "actual_date": now - timedelta(days=70),
                "window_open_date": now - timedelta(days=73),
                "window_close_date": now - timedelta(days=67),
                "duration_minutes": 180,
                "investigator_name": "Dr. David Park",
                "location": "Oncology Suite 1",
                "procedures_planned": 14,
                "procedures_completed": 14,
                "notes": "Complete baseline assessment including tumor measurements.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "VS-010",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L002",
                "site_id": "SITE-HOU-001",
                "visit_type": VisitType.TREATMENT,
                "visit_number": 2,
                "visit_name": "Week 3 Infusion Visit",
                "visit_status": VisitStatus.COMPLETED,
                "scheduled_date": now - timedelta(days=50),
                "actual_date": now - timedelta(days=49),
                "window_open_date": now - timedelta(days=52),
                "window_close_date": now - timedelta(days=47),
                "duration_minutes": 240,
                "investigator_name": "Dr. Angela Martinez",
                "location": "Infusion Center Bay 3",
                "procedures_planned": 8,
                "procedures_completed": 8,
                "notes": "Infusion completed without reactions. Vital signs stable.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "VS-011",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L003",
                "site_id": "SITE-SEA-001",
                "visit_type": VisitType.FOLLOW_UP,
                "visit_number": 5,
                "visit_name": "Week 12 Follow-Up Visit",
                "visit_status": VisitStatus.CANCELLED,
                "scheduled_date": now - timedelta(days=15),
                "actual_date": None,
                "window_open_date": now - timedelta(days=18),
                "window_close_date": now - timedelta(days=12),
                "duration_minutes": 60,
                "investigator_name": "Dr. Sarah Kim",
                "location": "Seattle Clinical Center",
                "procedures_planned": 4,
                "procedures_completed": 0,
                "notes": "Cancelled due to subject withdrawal from study.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "VS-012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-HOU-001",
                "visit_type": VisitType.END_OF_STUDY,
                "visit_number": 8,
                "visit_name": "End of Study Visit",
                "visit_status": VisitStatus.SCHEDULED,
                "scheduled_date": now + timedelta(days=30),
                "actual_date": None,
                "window_open_date": now + timedelta(days=27),
                "window_close_date": now + timedelta(days=33),
                "duration_minutes": 180,
                "investigator_name": "Dr. David Park",
                "location": "Oncology Suite 1",
                "procedures_planned": 16,
                "procedures_completed": 0,
                "notes": "Final study visit pending. Full assessment panel required.",
                "created_at": now - timedelta(days=5),
            },
        ]

        for vs in schedules_data:
            self._visit_schedules[vs["id"]] = VisitSchedule(**vs)

        # --- 12 Visit Adherence Records ---
        adherence_data = [
            {
                "id": "VA-001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-NY-001",
                "visit_schedule_id": "VS-001",
                "adherence_rating": AdherenceRating.EXCELLENT,
                "days_from_target": 0,
                "within_window": True,
                "procedures_adherence_pct": 100.0,
                "medication_compliance": True,
                "diary_completion": True,
                "assessment_date": now - timedelta(days=89),
                "assessed_by": "CRA Jennifer Adams",
                "risk_flag": False,
                "notes": "Perfect adherence. All procedures completed on schedule.",
                "created_at": now - timedelta(days=89),
            },
            {
                "id": "VA-002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-NY-001",
                "visit_schedule_id": "VS-002",
                "adherence_rating": AdherenceRating.GOOD,
                "days_from_target": 1,
                "within_window": True,
                "procedures_adherence_pct": 100.0,
                "medication_compliance": True,
                "diary_completion": True,
                "assessment_date": now - timedelta(days=73),
                "assessed_by": "CRA Jennifer Adams",
                "risk_flag": False,
                "notes": "Visit 1 day late but within window. All procedures done.",
                "created_at": now - timedelta(days=73),
            },
            {
                "id": "VA-003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E002",
                "site_id": "SITE-NY-001",
                "visit_schedule_id": "VS-003",
                "adherence_rating": AdherenceRating.GOOD,
                "days_from_target": -1,
                "within_window": True,
                "procedures_adherence_pct": 100.0,
                "medication_compliance": True,
                "diary_completion": False,
                "assessment_date": now - timedelta(days=58),
                "assessed_by": "CRA Jennifer Adams",
                "risk_flag": False,
                "notes": "Visit 1 day early. Diary incomplete - reminder issued.",
                "created_at": now - timedelta(days=58),
            },
            {
                "id": "VA-004",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E003",
                "site_id": "SITE-LA-001",
                "visit_schedule_id": "VS-004",
                "adherence_rating": AdherenceRating.NON_COMPLIANT,
                "days_from_target": 0,
                "within_window": False,
                "procedures_adherence_pct": 0.0,
                "medication_compliance": False,
                "diary_completion": False,
                "assessment_date": now - timedelta(days=28),
                "assessed_by": "CRA Robert Miller",
                "risk_flag": True,
                "notes": "Visit missed entirely. Subject unreachable. Retention risk flagged.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "VA-005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-CHI-001",
                "visit_schedule_id": "VS-005",
                "adherence_rating": AdherenceRating.EXCELLENT,
                "days_from_target": 0,
                "within_window": True,
                "procedures_adherence_pct": 100.0,
                "medication_compliance": True,
                "diary_completion": True,
                "assessment_date": now - timedelta(days=79),
                "assessed_by": "CRA Lisa Wong",
                "risk_flag": False,
                "notes": "Excellent screening visit adherence. Fully compliant.",
                "created_at": now - timedelta(days=79),
            },
            {
                "id": "VA-006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D002",
                "site_id": "SITE-CHI-001",
                "visit_schedule_id": "VS-006",
                "adherence_rating": AdherenceRating.FAIR,
                "days_from_target": 0,
                "within_window": True,
                "procedures_adherence_pct": 70.0,
                "medication_compliance": True,
                "diary_completion": True,
                "assessment_date": now - timedelta(days=54),
                "assessed_by": "CRA Lisa Wong",
                "risk_flag": False,
                "notes": "On-time visit but only 70% procedures completed due to subject illness.",
                "created_at": now - timedelta(days=54),
            },
            {
                "id": "VA-007",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-CHI-001",
                "visit_schedule_id": "VS-007",
                "adherence_rating": AdherenceRating.NOT_EVALUATED,
                "days_from_target": 0,
                "within_window": True,
                "procedures_adherence_pct": 0.0,
                "medication_compliance": True,
                "diary_completion": True,
                "assessment_date": now - timedelta(days=39),
                "assessed_by": "CRA Lisa Wong",
                "risk_flag": False,
                "notes": "Visit rescheduled. Adherence pending new visit date.",
                "created_at": now - timedelta(days=39),
            },
            {
                "id": "VA-008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D003",
                "site_id": "SITE-BOS-001",
                "visit_schedule_id": "VS-008",
                "adherence_rating": AdherenceRating.NOT_EVALUATED,
                "days_from_target": 0,
                "within_window": True,
                "procedures_adherence_pct": 0.0,
                "medication_compliance": True,
                "diary_completion": True,
                "assessment_date": now - timedelta(days=2),
                "assessed_by": "CRA Tom Bradley",
                "risk_flag": False,
                "notes": "Pre-visit assessment. Visit upcoming.",
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "VA-009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-HOU-001",
                "visit_schedule_id": "VS-009",
                "adherence_rating": AdherenceRating.EXCELLENT,
                "days_from_target": 0,
                "within_window": True,
                "procedures_adherence_pct": 100.0,
                "medication_compliance": True,
                "diary_completion": True,
                "assessment_date": now - timedelta(days=69),
                "assessed_by": "CRA Michael Torres",
                "risk_flag": False,
                "notes": "Full baseline compliance. All 14 procedures completed.",
                "created_at": now - timedelta(days=69),
            },
            {
                "id": "VA-010",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L002",
                "site_id": "SITE-HOU-001",
                "visit_schedule_id": "VS-010",
                "adherence_rating": AdherenceRating.GOOD,
                "days_from_target": -1,
                "within_window": True,
                "procedures_adherence_pct": 100.0,
                "medication_compliance": True,
                "diary_completion": True,
                "assessment_date": now - timedelta(days=48),
                "assessed_by": "CRA Michael Torres",
                "risk_flag": False,
                "notes": "Visit 1 day early. All infusion and assessment procedures completed.",
                "created_at": now - timedelta(days=48),
            },
            {
                "id": "VA-011",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L003",
                "site_id": "SITE-SEA-001",
                "visit_schedule_id": "VS-011",
                "adherence_rating": AdherenceRating.POOR,
                "days_from_target": 0,
                "within_window": False,
                "procedures_adherence_pct": 0.0,
                "medication_compliance": False,
                "diary_completion": False,
                "assessment_date": now - timedelta(days=14),
                "assessed_by": "CRA Amy Chen",
                "risk_flag": True,
                "notes": "Visit cancelled. Subject withdrawing from study. High retention risk.",
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "VA-012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-HOU-001",
                "visit_schedule_id": "VS-012",
                "adherence_rating": AdherenceRating.NOT_EVALUATED,
                "days_from_target": 0,
                "within_window": True,
                "procedures_adherence_pct": 0.0,
                "medication_compliance": True,
                "diary_completion": True,
                "assessment_date": now - timedelta(days=4),
                "assessed_by": "CRA Michael Torres",
                "risk_flag": False,
                "notes": "End of study visit pending. Pre-visit compliance confirmed.",
                "created_at": now - timedelta(days=4),
            },
        ]

        for va in adherence_data:
            self._visit_adherence[va["id"]] = VisitAdherence(**va)

        # --- 12 Window Violations ---
        violations_data = [
            {
                "id": "WV-001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-NY-001",
                "visit_schedule_id": "VS-002",
                "violation_severity": ViolationSeverity.MINOR,
                "days_out_of_window": 1,
                "expected_window_open": now - timedelta(days=78),
                "expected_window_close": now - timedelta(days=72),
                "actual_visit_date": now - timedelta(days=74),
                "reason": "Subject arrived 1 day late due to transportation issues.",
                "impact_on_data": "Minimal impact. Within acceptable range for PK analysis.",
                "protocol_deviation_filed": False,
                "deviation_id": None,
                "reviewed_by": "Dr. Sarah Chen",
                "notes": "Minor window deviation. No corrective action needed.",
                "created_at": now - timedelta(days=73),
            },
            {
                "id": "WV-002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E002",
                "site_id": "SITE-NY-001",
                "visit_schedule_id": "VS-003",
                "violation_severity": ViolationSeverity.INFORMATIONAL,
                "days_out_of_window": 0,
                "expected_window_open": now - timedelta(days=63),
                "expected_window_close": now - timedelta(days=57),
                "actual_visit_date": now - timedelta(days=59),
                "reason": "Visit within window but flagged for early arrival documentation.",
                "impact_on_data": None,
                "protocol_deviation_filed": False,
                "deviation_id": None,
                "reviewed_by": None,
                "notes": "Informational only. No actual violation.",
                "created_at": now - timedelta(days=58),
            },
            {
                "id": "WV-003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E003",
                "site_id": "SITE-LA-001",
                "visit_schedule_id": "VS-004",
                "violation_severity": ViolationSeverity.CRITICAL,
                "days_out_of_window": 7,
                "expected_window_open": now - timedelta(days=33),
                "expected_window_close": now - timedelta(days=27),
                "actual_visit_date": now - timedelta(days=20),
                "reason": "Subject missed scheduled window entirely. Late recapture visit.",
                "impact_on_data": "Significant. PK data may not be evaluable for this timepoint.",
                "protocol_deviation_filed": True,
                "deviation_id": "PD-2025-047",
                "reviewed_by": "Dr. Maria Lopez",
                "notes": "Critical window violation. Protocol deviation filed. Medical monitor notified.",
                "created_at": now - timedelta(days=19),
            },
            {
                "id": "WV-004",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-NY-001",
                "visit_schedule_id": "VS-001",
                "violation_severity": ViolationSeverity.WAIVED,
                "days_out_of_window": 2,
                "expected_window_open": now - timedelta(days=93),
                "expected_window_close": now - timedelta(days=87),
                "actual_visit_date": now - timedelta(days=90),
                "reason": "Screening window extended per medical monitor approval.",
                "impact_on_data": None,
                "protocol_deviation_filed": False,
                "deviation_id": None,
                "reviewed_by": "Dr. Sarah Chen",
                "notes": "Window extension approved. No deviation required.",
                "created_at": now - timedelta(days=89),
            },
            {
                "id": "WV-005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D002",
                "site_id": "SITE-CHI-001",
                "visit_schedule_id": "VS-006",
                "violation_severity": ViolationSeverity.MINOR,
                "days_out_of_window": 1,
                "expected_window_open": now - timedelta(days=58),
                "expected_window_close": now - timedelta(days=52),
                "actual_visit_date": now - timedelta(days=55),
                "reason": "Subject arrived within window but late for morning assessments.",
                "impact_on_data": "Fasting labs may be affected by late arrival time.",
                "protocol_deviation_filed": False,
                "deviation_id": None,
                "reviewed_by": "Dr. Karen Liu",
                "notes": "Minor timing issue. Labs drawn within acceptable timeframe.",
                "created_at": now - timedelta(days=54),
            },
            {
                "id": "WV-006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-CHI-001",
                "visit_schedule_id": "VS-007",
                "violation_severity": ViolationSeverity.MAJOR,
                "days_out_of_window": 4,
                "expected_window_open": now - timedelta(days=43),
                "expected_window_close": now - timedelta(days=37),
                "actual_visit_date": now - timedelta(days=33),
                "reason": "Visit rescheduled beyond original window due to site closure.",
                "impact_on_data": "Efficacy assessment delayed. Data may need sensitivity analysis.",
                "protocol_deviation_filed": True,
                "deviation_id": "PD-2025-032",
                "reviewed_by": "Dr. Karen Liu",
                "notes": "Major violation due to site scheduling conflict. Deviation filed.",
                "created_at": now - timedelta(days=32),
            },
            {
                "id": "WV-007",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D002",
                "site_id": "SITE-CHI-001",
                "visit_schedule_id": "VS-005",
                "violation_severity": ViolationSeverity.MINOR,
                "days_out_of_window": 1,
                "expected_window_open": now - timedelta(days=83),
                "expected_window_close": now - timedelta(days=77),
                "actual_visit_date": now - timedelta(days=76),
                "reason": "Subject 1 day outside window due to personal conflict.",
                "impact_on_data": "Minimal impact on screening data.",
                "protocol_deviation_filed": False,
                "deviation_id": None,
                "reviewed_by": None,
                "notes": "Minor deviation. Within sponsor-acceptable range.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "WV-008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D003",
                "site_id": "SITE-BOS-001",
                "visit_schedule_id": "VS-008",
                "violation_severity": ViolationSeverity.INFORMATIONAL,
                "days_out_of_window": 0,
                "expected_window_open": now + timedelta(days=2),
                "expected_window_close": now + timedelta(days=8),
                "actual_visit_date": now + timedelta(days=5),
                "reason": "Pre-flagged for potential window concern based on scheduling.",
                "impact_on_data": None,
                "protocol_deviation_filed": False,
                "deviation_id": None,
                "reviewed_by": None,
                "notes": "Prospective tracking. Visit expected within window.",
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "WV-009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-HOU-001",
                "visit_schedule_id": "VS-009",
                "violation_severity": ViolationSeverity.MINOR,
                "days_out_of_window": 1,
                "expected_window_open": now - timedelta(days=73),
                "expected_window_close": now - timedelta(days=67),
                "actual_visit_date": now - timedelta(days=70),
                "reason": "Slight scheduling adjustment for infusion chair availability.",
                "impact_on_data": "No impact. Baseline data collected within protocol limits.",
                "protocol_deviation_filed": False,
                "deviation_id": None,
                "reviewed_by": "Dr. David Park",
                "notes": "Minor window adjustment. Documented for tracking.",
                "created_at": now - timedelta(days=69),
            },
            {
                "id": "WV-010",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L002",
                "site_id": "SITE-HOU-001",
                "visit_schedule_id": "VS-010",
                "violation_severity": ViolationSeverity.MINOR,
                "days_out_of_window": 1,
                "expected_window_open": now - timedelta(days=52),
                "expected_window_close": now - timedelta(days=47),
                "actual_visit_date": now - timedelta(days=49),
                "reason": "Subject arrived 1 day early for infusion convenience.",
                "impact_on_data": "No impact on efficacy or safety assessments.",
                "protocol_deviation_filed": False,
                "deviation_id": None,
                "reviewed_by": "Dr. Angela Martinez",
                "notes": "Minor early arrival. Within acceptable tolerance.",
                "created_at": now - timedelta(days=48),
            },
            {
                "id": "WV-011",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L003",
                "site_id": "SITE-SEA-001",
                "visit_schedule_id": "VS-011",
                "violation_severity": ViolationSeverity.CRITICAL,
                "days_out_of_window": 10,
                "expected_window_open": now - timedelta(days=18),
                "expected_window_close": now - timedelta(days=12),
                "actual_visit_date": now - timedelta(days=2),
                "reason": "Subject withdrew. Visit window expired without visit.",
                "impact_on_data": "Data missing for this timepoint. Subject discontinued.",
                "protocol_deviation_filed": True,
                "deviation_id": "PD-2025-055",
                "reviewed_by": "Dr. Sarah Kim",
                "notes": "Critical violation. Subject withdrawn from study. No further visits.",
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "WV-012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-HOU-001",
                "visit_schedule_id": "VS-012",
                "violation_severity": ViolationSeverity.INFORMATIONAL,
                "days_out_of_window": 0,
                "expected_window_open": now + timedelta(days=27),
                "expected_window_close": now + timedelta(days=33),
                "actual_visit_date": now + timedelta(days=30),
                "reason": "Pre-scheduled end of study visit flagged for tracking.",
                "impact_on_data": None,
                "protocol_deviation_filed": False,
                "deviation_id": None,
                "reviewed_by": None,
                "notes": "Informational. Visit confirmed within expected window.",
                "created_at": now - timedelta(days=3),
            },
        ]

        for wv in violations_data:
            self._window_violations[wv["id"]] = WindowViolation(**wv)

        # --- 12 Missed Visit Follow-Ups ---
        follow_ups_data = [
            {
                "id": "MVF-001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E003",
                "site_id": "SITE-LA-001",
                "visit_schedule_id": "VS-004",
                "follow_up_status": FollowUpStatus.IN_PROGRESS,
                "contact_attempts": 3,
                "last_contact_date": now - timedelta(days=25),
                "reason_for_miss": "Subject unreachable by phone. Voicemails left.",
                "reschedule_date": None,
                "retention_risk": True,
                "assigned_to": "CRA Robert Miller",
                "escalated_to": "Site Monitor Lead",
                "resolution_date": None,
                "notes": "Multiple contact attempts. Escalated to site monitor lead for home visit.",
                "created_at": now - timedelta(days=29),
            },
            {
                "id": "MVF-002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-NY-001",
                "visit_schedule_id": "VS-002",
                "follow_up_status": FollowUpStatus.COMPLETED,
                "contact_attempts": 1,
                "last_contact_date": now - timedelta(days=76),
                "reason_for_miss": "Subject called to delay by 1 day. Transportation issue.",
                "reschedule_date": now - timedelta(days=74),
                "retention_risk": False,
                "assigned_to": "CRA Jennifer Adams",
                "escalated_to": None,
                "resolution_date": now - timedelta(days=74),
                "notes": "Resolved quickly. Subject attended rescheduled visit.",
                "created_at": now - timedelta(days=76),
            },
            {
                "id": "MVF-003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E002",
                "site_id": "SITE-NY-001",
                "visit_schedule_id": "VS-003",
                "follow_up_status": FollowUpStatus.CLOSED,
                "contact_attempts": 0,
                "last_contact_date": None,
                "reason_for_miss": "Proactive flag - subject mentioned potential scheduling conflict.",
                "reschedule_date": None,
                "retention_risk": False,
                "assigned_to": "CRA Jennifer Adams",
                "escalated_to": None,
                "resolution_date": now - timedelta(days=59),
                "notes": "Closed. Subject attended visit without issue.",
                "created_at": now - timedelta(days=62),
            },
            {
                "id": "MVF-004",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E003",
                "site_id": "SITE-LA-001",
                "visit_schedule_id": "VS-004",
                "follow_up_status": FollowUpStatus.ESCALATED,
                "contact_attempts": 5,
                "last_contact_date": now - timedelta(days=22),
                "reason_for_miss": "Subject non-responsive to all contact methods.",
                "reschedule_date": None,
                "retention_risk": True,
                "assigned_to": "CRA Robert Miller",
                "escalated_to": "Clinical Operations Manager",
                "resolution_date": None,
                "notes": "Escalated to clinical ops. Home visit being arranged.",
                "created_at": now - timedelta(days=27),
            },
            {
                "id": "MVF-005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-CHI-001",
                "visit_schedule_id": "VS-007",
                "follow_up_status": FollowUpStatus.COMPLETED,
                "contact_attempts": 2,
                "last_contact_date": now - timedelta(days=38),
                "reason_for_miss": "Visit rescheduled due to site holiday closure.",
                "reschedule_date": now - timedelta(days=33),
                "retention_risk": False,
                "assigned_to": "CRA Lisa Wong",
                "escalated_to": None,
                "resolution_date": now - timedelta(days=33),
                "notes": "Successfully rescheduled. Subject attended new visit date.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "MVF-006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D002",
                "site_id": "SITE-CHI-001",
                "visit_schedule_id": "VS-006",
                "follow_up_status": FollowUpStatus.COMPLETED,
                "contact_attempts": 1,
                "last_contact_date": now - timedelta(days=53),
                "reason_for_miss": "Subject felt unwell. Partial visit completed.",
                "reschedule_date": now - timedelta(days=50),
                "retention_risk": False,
                "assigned_to": "CRA Lisa Wong",
                "escalated_to": None,
                "resolution_date": now - timedelta(days=50),
                "notes": "Remaining procedures completed at follow-up unscheduled visit.",
                "created_at": now - timedelta(days=54),
            },
            {
                "id": "MVF-007",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D003",
                "site_id": "SITE-BOS-001",
                "visit_schedule_id": "VS-008",
                "follow_up_status": FollowUpStatus.PENDING,
                "contact_attempts": 0,
                "last_contact_date": None,
                "reason_for_miss": None,
                "reschedule_date": None,
                "retention_risk": False,
                "assigned_to": "CRA Tom Bradley",
                "escalated_to": None,
                "resolution_date": None,
                "notes": "Pre-visit monitoring. No follow-up needed yet.",
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "MVF-008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-CHI-001",
                "visit_schedule_id": "VS-005",
                "follow_up_status": FollowUpStatus.CLOSED,
                "contact_attempts": 0,
                "last_contact_date": None,
                "reason_for_miss": "No actual miss. Routine compliance check.",
                "reschedule_date": None,
                "retention_risk": False,
                "assigned_to": "CRA Lisa Wong",
                "escalated_to": None,
                "resolution_date": now - timedelta(days=78),
                "notes": "Closed. No follow-up required.",
                "created_at": now - timedelta(days=79),
            },
            {
                "id": "MVF-009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-HOU-001",
                "visit_schedule_id": "VS-009",
                "follow_up_status": FollowUpStatus.CLOSED,
                "contact_attempts": 0,
                "last_contact_date": None,
                "reason_for_miss": "No miss. Routine tracking entry.",
                "reschedule_date": None,
                "retention_risk": False,
                "assigned_to": "CRA Michael Torres",
                "escalated_to": None,
                "resolution_date": now - timedelta(days=68),
                "notes": "Baseline visit completed on time. No follow-up needed.",
                "created_at": now - timedelta(days=69),
            },
            {
                "id": "MVF-010",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L003",
                "site_id": "SITE-SEA-001",
                "visit_schedule_id": "VS-011",
                "follow_up_status": FollowUpStatus.UNABLE_TO_REACH,
                "contact_attempts": 6,
                "last_contact_date": now - timedelta(days=10),
                "reason_for_miss": "Subject withdrew consent. Unable to reach for final visit.",
                "reschedule_date": None,
                "retention_risk": True,
                "assigned_to": "CRA Amy Chen",
                "escalated_to": "Clinical Operations Manager",
                "resolution_date": None,
                "notes": "Subject unreachable after withdrawal notification. All contact methods exhausted.",
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "MVF-011",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L002",
                "site_id": "SITE-HOU-001",
                "visit_schedule_id": "VS-010",
                "follow_up_status": FollowUpStatus.COMPLETED,
                "contact_attempts": 1,
                "last_contact_date": now - timedelta(days=50),
                "reason_for_miss": "Subject requested 1-day schedule change for personal reasons.",
                "reschedule_date": now - timedelta(days=49),
                "retention_risk": False,
                "assigned_to": "CRA Michael Torres",
                "escalated_to": None,
                "resolution_date": now - timedelta(days=49),
                "notes": "Quickly resolved. Subject attended adjusted visit.",
                "created_at": now - timedelta(days=51),
            },
            {
                "id": "MVF-012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-HOU-001",
                "visit_schedule_id": "VS-012",
                "follow_up_status": FollowUpStatus.PENDING,
                "contact_attempts": 0,
                "last_contact_date": None,
                "reason_for_miss": None,
                "reschedule_date": None,
                "retention_risk": False,
                "assigned_to": "CRA Michael Torres",
                "escalated_to": None,
                "resolution_date": None,
                "notes": "Pre-visit tracking for end of study. Visit 30 days out.",
                "created_at": now - timedelta(days=4),
            },
        ]

        for mvf in follow_ups_data:
            self._missed_visit_follow_ups[mvf["id"]] = MissedVisitFollowUp(**mvf)

    # ------------------------------------------------------------------
    # Visit Schedules
    # ------------------------------------------------------------------

    def list_visit_schedules(
        self,
        *,
        trial_id: str | None = None,
        visit_type: VisitType | None = None,
        visit_status: VisitStatus | None = None,
        site_id: str | None = None,
    ) -> list[VisitSchedule]:
        """List visit schedules with optional filters."""
        with self._lock:
            result = list(self._visit_schedules.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if visit_type is not None:
            result = [r for r in result if r.visit_type == visit_type]
        if visit_status is not None:
            result = [r for r in result if r.visit_status == visit_status]
        if site_id is not None:
            result = [r for r in result if r.site_id == site_id]

        return sorted(result, key=lambda r: r.scheduled_date, reverse=True)

    def get_visit_schedule(self, schedule_id: str) -> VisitSchedule | None:
        """Get a single visit schedule by ID."""
        with self._lock:
            return self._visit_schedules.get(schedule_id)

    def create_visit_schedule(self, payload: VisitScheduleCreate) -> VisitSchedule:
        """Create a new visit schedule."""
        now = datetime.now(timezone.utc)
        schedule_id = f"VS-{uuid4().hex[:8].upper()}"
        record = VisitSchedule(
            id=schedule_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            site_id=payload.site_id,
            visit_type=payload.visit_type,
            visit_number=payload.visit_number,
            visit_name=payload.visit_name,
            visit_status=VisitStatus.SCHEDULED,
            scheduled_date=payload.scheduled_date,
            actual_date=None,
            window_open_date=None,
            window_close_date=None,
            duration_minutes=payload.duration_minutes,
            investigator_name=None,
            location=None,
            procedures_planned=0,
            procedures_completed=0,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._visit_schedules[schedule_id] = record
        logger.info("Created visit schedule %s for trial %s", schedule_id, payload.trial_id)
        return record

    def update_visit_schedule(
        self, schedule_id: str, payload: VisitScheduleUpdate
    ) -> VisitSchedule | None:
        """Update an existing visit schedule."""
        with self._lock:
            existing = self._visit_schedules.get(schedule_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = VisitSchedule(**data)
            self._visit_schedules[schedule_id] = updated
        return updated

    def delete_visit_schedule(self, schedule_id: str) -> bool:
        """Delete a visit schedule. Returns True if deleted."""
        with self._lock:
            if schedule_id in self._visit_schedules:
                del self._visit_schedules[schedule_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Visit Adherence
    # ------------------------------------------------------------------

    def list_visit_adherence(
        self,
        *,
        trial_id: str | None = None,
        adherence_rating: AdherenceRating | None = None,
        subject_id: str | None = None,
    ) -> list[VisitAdherence]:
        """List visit adherence records with optional filters."""
        with self._lock:
            result = list(self._visit_adherence.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if adherence_rating is not None:
            result = [r for r in result if r.adherence_rating == adherence_rating]
        if subject_id is not None:
            result = [r for r in result if r.subject_id == subject_id]

        return sorted(result, key=lambda r: r.assessment_date, reverse=True)

    def get_visit_adherence(self, adherence_id: str) -> VisitAdherence | None:
        """Get a single visit adherence record by ID."""
        with self._lock:
            return self._visit_adherence.get(adherence_id)

    def create_visit_adherence(self, payload: VisitAdherenceCreate) -> VisitAdherence:
        """Create a new visit adherence record."""
        now = datetime.now(timezone.utc)
        adherence_id = f"VA-{uuid4().hex[:8].upper()}"
        record = VisitAdherence(
            id=adherence_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            site_id=payload.site_id,
            visit_schedule_id=payload.visit_schedule_id,
            adherence_rating=AdherenceRating.NOT_EVALUATED,
            days_from_target=payload.days_from_target,
            within_window=True,
            procedures_adherence_pct=100.0,
            medication_compliance=True,
            diary_completion=True,
            assessment_date=payload.assessment_date,
            assessed_by=payload.assessed_by,
            risk_flag=False,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._visit_adherence[adherence_id] = record
        logger.info("Created visit adherence %s for trial %s", adherence_id, payload.trial_id)
        return record

    def update_visit_adherence(
        self, adherence_id: str, payload: VisitAdherenceUpdate
    ) -> VisitAdherence | None:
        """Update an existing visit adherence record."""
        with self._lock:
            existing = self._visit_adherence.get(adherence_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = VisitAdherence(**data)
            self._visit_adherence[adherence_id] = updated
        return updated

    def delete_visit_adherence(self, adherence_id: str) -> bool:
        """Delete a visit adherence record. Returns True if deleted."""
        with self._lock:
            if adherence_id in self._visit_adherence:
                del self._visit_adherence[adherence_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Window Violations
    # ------------------------------------------------------------------

    def list_window_violations(
        self,
        *,
        trial_id: str | None = None,
        violation_severity: ViolationSeverity | None = None,
    ) -> list[WindowViolation]:
        """List window violations with optional filters."""
        with self._lock:
            result = list(self._window_violations.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if violation_severity is not None:
            result = [r for r in result if r.violation_severity == violation_severity]

        return sorted(result, key=lambda r: r.actual_visit_date, reverse=True)

    def get_window_violation(self, violation_id: str) -> WindowViolation | None:
        """Get a single window violation by ID."""
        with self._lock:
            return self._window_violations.get(violation_id)

    def create_window_violation(self, payload: WindowViolationCreate) -> WindowViolation:
        """Create a new window violation."""
        now = datetime.now(timezone.utc)
        violation_id = f"WV-{uuid4().hex[:8].upper()}"
        record = WindowViolation(
            id=violation_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            site_id=payload.site_id,
            visit_schedule_id=payload.visit_schedule_id,
            violation_severity=payload.violation_severity,
            days_out_of_window=payload.days_out_of_window,
            expected_window_open=payload.expected_window_open,
            expected_window_close=payload.expected_window_close,
            actual_visit_date=payload.actual_visit_date,
            reason=payload.reason,
            impact_on_data=None,
            protocol_deviation_filed=False,
            deviation_id=None,
            reviewed_by=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._window_violations[violation_id] = record
        logger.info("Created window violation %s for trial %s", violation_id, payload.trial_id)
        return record

    def update_window_violation(
        self, violation_id: str, payload: WindowViolationUpdate
    ) -> WindowViolation | None:
        """Update an existing window violation."""
        with self._lock:
            existing = self._window_violations.get(violation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = WindowViolation(**data)
            self._window_violations[violation_id] = updated
        return updated

    def delete_window_violation(self, violation_id: str) -> bool:
        """Delete a window violation. Returns True if deleted."""
        with self._lock:
            if violation_id in self._window_violations:
                del self._window_violations[violation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Missed Visit Follow-Ups
    # ------------------------------------------------------------------

    def list_missed_visit_follow_ups(
        self,
        *,
        trial_id: str | None = None,
        follow_up_status: FollowUpStatus | None = None,
    ) -> list[MissedVisitFollowUp]:
        """List missed visit follow-ups with optional filters."""
        with self._lock:
            result = list(self._missed_visit_follow_ups.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if follow_up_status is not None:
            result = [r for r in result if r.follow_up_status == follow_up_status]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_missed_visit_follow_up(self, follow_up_id: str) -> MissedVisitFollowUp | None:
        """Get a single missed visit follow-up by ID."""
        with self._lock:
            return self._missed_visit_follow_ups.get(follow_up_id)

    def create_missed_visit_follow_up(
        self, payload: MissedVisitFollowUpCreate
    ) -> MissedVisitFollowUp:
        """Create a new missed visit follow-up."""
        now = datetime.now(timezone.utc)
        follow_up_id = f"MVF-{uuid4().hex[:8].upper()}"
        record = MissedVisitFollowUp(
            id=follow_up_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            site_id=payload.site_id,
            visit_schedule_id=payload.visit_schedule_id,
            follow_up_status=FollowUpStatus.PENDING,
            contact_attempts=0,
            last_contact_date=None,
            reason_for_miss=payload.reason_for_miss,
            reschedule_date=None,
            retention_risk=False,
            assigned_to=payload.assigned_to,
            escalated_to=None,
            resolution_date=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._missed_visit_follow_ups[follow_up_id] = record
        logger.info(
            "Created missed visit follow-up %s for trial %s", follow_up_id, payload.trial_id
        )
        return record

    def update_missed_visit_follow_up(
        self, follow_up_id: str, payload: MissedVisitFollowUpUpdate
    ) -> MissedVisitFollowUp | None:
        """Update an existing missed visit follow-up."""
        with self._lock:
            existing = self._missed_visit_follow_ups.get(follow_up_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MissedVisitFollowUp(**data)
            self._missed_visit_follow_ups[follow_up_id] = updated
        return updated

    def delete_missed_visit_follow_up(self, follow_up_id: str) -> bool:
        """Delete a missed visit follow-up. Returns True if deleted."""
        with self._lock:
            if follow_up_id in self._missed_visit_follow_ups:
                del self._missed_visit_follow_ups[follow_up_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> PatientVisitTrackingMetrics:
        """Compute aggregated patient visit tracking metrics."""
        with self._lock:
            schedules = list(self._visit_schedules.values())
            adherence = list(self._visit_adherence.values())
            violations = list(self._window_violations.values())
            follow_ups = list(self._missed_visit_follow_ups.values())

        # Apply trial_id filter if provided
        if trial_id is not None:
            schedules = [s for s in schedules if s.trial_id == trial_id]
            adherence = [a for a in adherence if a.trial_id == trial_id]
            violations = [v for v in violations if v.trial_id == trial_id]
            follow_ups = [f for f in follow_ups if f.trial_id == trial_id]

        # Visits by status
        visits_by_status: dict[str, int] = {}
        for s in schedules:
            key = s.visit_status.value
            visits_by_status[key] = visits_by_status.get(key, 0) + 1

        # Visits by type
        visits_by_type: dict[str, int] = {}
        for s in schedules:
            key = s.visit_type.value
            visits_by_type[key] = visits_by_type.get(key, 0) + 1

        # Visit completion rate
        completed_count = sum(
            1 for s in schedules if s.visit_status == VisitStatus.COMPLETED
        )
        visit_completion_rate = round(
            (completed_count / max(1, len(schedules))) * 100, 1
        )

        # Adherence by rating
        adherence_by_rating: dict[str, int] = {}
        for a in adherence:
            key = a.adherence_rating.value
            adherence_by_rating[key] = adherence_by_rating.get(key, 0) + 1

        # Within window rate
        within_window_count = sum(1 for a in adherence if a.within_window)
        within_window_rate = round(
            (within_window_count / max(1, len(adherence))) * 100, 1
        )

        # Violations by severity
        violations_by_severity: dict[str, int] = {}
        for v in violations:
            key = v.violation_severity.value
            violations_by_severity[key] = violations_by_severity.get(key, 0) + 1

        # Follow-ups by status
        follow_ups_by_status: dict[str, int] = {}
        for f in follow_ups:
            key = f.follow_up_status.value
            follow_ups_by_status[key] = follow_ups_by_status.get(key, 0) + 1

        # Missed visit resolution rate
        resolved_count = sum(
            1
            for f in follow_ups
            if f.follow_up_status in (FollowUpStatus.COMPLETED, FollowUpStatus.CLOSED)
        )
        missed_visit_resolution_rate = round(
            (resolved_count / max(1, len(follow_ups))) * 100, 1
        )

        return PatientVisitTrackingMetrics(
            total_visits=len(schedules),
            visits_by_status=visits_by_status,
            visits_by_type=visits_by_type,
            visit_completion_rate=visit_completion_rate,
            total_adherence_records=len(adherence),
            adherence_by_rating=adherence_by_rating,
            within_window_rate=within_window_rate,
            total_window_violations=len(violations),
            violations_by_severity=violations_by_severity,
            total_missed_follow_ups=len(follow_ups),
            follow_ups_by_status=follow_ups_by_status,
            missed_visit_resolution_rate=missed_visit_resolution_rate,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: PatientVisitTrackingService | None = None
_instance_lock = threading.Lock()


def get_patient_visit_tracking_service() -> PatientVisitTrackingService:
    """Return the singleton PatientVisitTrackingService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = PatientVisitTrackingService()
    return _instance


def reset_patient_visit_tracking_service() -> PatientVisitTrackingService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = PatientVisitTrackingService()
    return _instance
