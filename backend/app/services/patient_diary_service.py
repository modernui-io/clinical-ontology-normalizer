"""Patient Diary / eDiary Management Service (EDIARY-MGT).

Manages electronic patient diary operations: diary entry tracking,
symptom recording, compliance monitoring, diary form validation,
diary schedule management, and eDiary operational metrics.

Usage:
    from app.services.patient_diary_service import (
        get_patient_diary_service,
    )

    svc = get_patient_diary_service()
    entries = svc.list_diary_entries()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.patient_diary import (
    ComplianceLevel,
    DiaryCompliance,
    DiaryComplianceCreate,
    DiaryComplianceUpdate,
    DiaryEntry,
    DiaryEntryCreate,
    DiaryEntryUpdate,
    DiarySchedule,
    DiaryScheduleCreate,
    DiaryScheduleUpdate,
    DiaryType,
    DiaryValidation,
    DiaryValidationCreate,
    DiaryValidationUpdate,
    EntryStatus,
    PatientDiaryMetrics,
    SymptomRecord,
    SymptomRecordCreate,
    SymptomRecordUpdate,
    ValidationStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class PatientDiaryService:
    """In-memory Patient Diary / eDiary management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._diary_entries: dict[str, DiaryEntry] = {}
        self._symptom_records: dict[str, SymptomRecord] = {}
        self._diary_schedules: dict[str, DiarySchedule] = {}
        self._diary_compliance: dict[str, DiaryCompliance] = {}
        self._diary_validations: dict[str, DiaryValidation] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic eDiary data across Regeneron clinical trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Diary Entries ---
        entries_data = [
            {
                "id": "DE-001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1001",
                "site_id": "SITE-101",
                "diary_type": DiaryType.SYMPTOM,
                "scheduled_date": now - timedelta(days=14),
                "completed_date": now - timedelta(days=14, hours=2),
                "status": EntryStatus.COMPLETED,
                "form_version": "v2.1",
                "responses": {"headache": "mild", "nausea": False, "pain_score": 3.0},
                "total_questions": 10,
                "answered_questions": 10,
                "completion_pct": 100.0,
                "time_to_complete_minutes": 8.5,
                "device_type": "iPhone 15",
                "submission_source": "mobile_app",
                "validated": True,
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "DE-002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1001",
                "site_id": "SITE-101",
                "diary_type": DiaryType.MEDICATION,
                "scheduled_date": now - timedelta(days=13),
                "completed_date": now - timedelta(days=13, hours=1),
                "status": EntryStatus.COMPLETED,
                "form_version": "v2.1",
                "responses": {"took_medication": True, "dose_mg": 40.0, "time_taken": "08:30"},
                "total_questions": 5,
                "answered_questions": 5,
                "completion_pct": 100.0,
                "time_to_complete_minutes": 3.2,
                "device_type": "iPhone 15",
                "submission_source": "mobile_app",
                "validated": True,
                "created_at": now - timedelta(days=13),
            },
            {
                "id": "DE-003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1002",
                "site_id": "SITE-101",
                "diary_type": DiaryType.QUALITY_OF_LIFE,
                "scheduled_date": now - timedelta(days=10),
                "completed_date": now - timedelta(days=10, hours=4),
                "status": EntryStatus.COMPLETED,
                "form_version": "v1.3",
                "responses": {"overall_wellbeing": 7.0, "daily_functioning": 8.0, "social_activity": 6.0},
                "total_questions": 15,
                "answered_questions": 15,
                "completion_pct": 100.0,
                "time_to_complete_minutes": 12.0,
                "device_type": "Samsung Galaxy S24",
                "submission_source": "mobile_app",
                "validated": True,
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "DE-004",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2001",
                "site_id": "SITE-103",
                "diary_type": DiaryType.SYMPTOM,
                "scheduled_date": now - timedelta(days=7),
                "completed_date": now - timedelta(days=6, hours=20),
                "status": EntryStatus.LATE,
                "form_version": "v3.0",
                "responses": {"itching_score": 6.0, "redness": "moderate", "sleep_disruption": True},
                "total_questions": 12,
                "answered_questions": 12,
                "completion_pct": 100.0,
                "time_to_complete_minutes": 10.0,
                "device_type": "iPad Pro",
                "submission_source": "mobile_app",
                "validated": False,
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "DE-005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2001",
                "site_id": "SITE-103",
                "diary_type": DiaryType.PAIN,
                "scheduled_date": now - timedelta(days=5),
                "completed_date": now - timedelta(days=5, hours=3),
                "status": EntryStatus.COMPLETED,
                "form_version": "v3.0",
                "responses": {"pain_level": 4.0, "pain_location": "joints", "pain_type": "aching"},
                "total_questions": 8,
                "answered_questions": 8,
                "completion_pct": 100.0,
                "time_to_complete_minutes": 5.5,
                "device_type": "iPad Pro",
                "submission_source": "mobile_app",
                "validated": True,
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "DE-006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2002",
                "site_id": "SITE-104",
                "diary_type": DiaryType.ADVERSE_EVENT,
                "scheduled_date": now - timedelta(days=4),
                "completed_date": now - timedelta(days=4, hours=1),
                "status": EntryStatus.COMPLETED,
                "form_version": "v3.0",
                "responses": {"event_description": "mild headache", "severity": "mild", "ongoing": False},
                "total_questions": 10,
                "answered_questions": 10,
                "completion_pct": 100.0,
                "time_to_complete_minutes": 7.0,
                "device_type": "iPhone 14",
                "submission_source": "mobile_app",
                "validated": True,
                "created_at": now - timedelta(days=4),
            },
            {
                "id": "DE-007",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3001",
                "site_id": "SITE-105",
                "diary_type": DiaryType.SYMPTOM,
                "scheduled_date": now - timedelta(days=3),
                "completed_date": None,
                "status": EntryStatus.MISSED,
                "form_version": "v1.0",
                "responses": {},
                "total_questions": 10,
                "answered_questions": 0,
                "completion_pct": 0.0,
                "time_to_complete_minutes": None,
                "device_type": None,
                "submission_source": "mobile_app",
                "validated": False,
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "DE-008",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3001",
                "site_id": "SITE-105",
                "diary_type": DiaryType.ACTIVITY,
                "scheduled_date": now - timedelta(days=2),
                "completed_date": now - timedelta(days=2, hours=5),
                "status": EntryStatus.COMPLETED,
                "form_version": "v1.0",
                "responses": {"steps_today": 4500.0, "exercise_minutes": 30.0, "fatigue_level": 5.0},
                "total_questions": 6,
                "answered_questions": 6,
                "completion_pct": 100.0,
                "time_to_complete_minutes": 4.0,
                "device_type": "Pixel 8",
                "submission_source": "mobile_app",
                "validated": True,
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "DE-009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3002",
                "site_id": "SITE-106",
                "diary_type": DiaryType.SLEEP,
                "scheduled_date": now - timedelta(days=1),
                "completed_date": now - timedelta(hours=20),
                "status": EntryStatus.COMPLETED,
                "form_version": "v1.0",
                "responses": {"hours_slept": 6.5, "sleep_quality": 5.0, "awakenings": 2.0},
                "total_questions": 8,
                "answered_questions": 8,
                "completion_pct": 100.0,
                "time_to_complete_minutes": 3.5,
                "device_type": "iPhone 16",
                "submission_source": "mobile_app",
                "validated": True,
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "DE-010",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1003",
                "site_id": "SITE-102",
                "diary_type": DiaryType.MOOD,
                "scheduled_date": now - timedelta(days=1),
                "completed_date": now - timedelta(hours=22),
                "status": EntryStatus.COMPLETED,
                "form_version": "v2.1",
                "responses": {"mood_score": 7.0, "anxiety_level": 3.0, "motivation": 8.0},
                "total_questions": 10,
                "answered_questions": 10,
                "completion_pct": 100.0,
                "time_to_complete_minutes": 6.0,
                "device_type": "Samsung Galaxy S23",
                "submission_source": "mobile_app",
                "validated": True,
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "DE-011",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2003",
                "site_id": "SITE-104",
                "diary_type": DiaryType.SYMPTOM,
                "scheduled_date": now,
                "completed_date": None,
                "status": EntryStatus.PENDING,
                "form_version": "v3.0",
                "responses": {},
                "total_questions": 12,
                "answered_questions": 0,
                "completion_pct": 0.0,
                "time_to_complete_minutes": None,
                "device_type": None,
                "submission_source": "mobile_app",
                "validated": False,
                "created_at": now,
            },
            {
                "id": "DE-012",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1002",
                "site_id": "SITE-101",
                "diary_type": DiaryType.MEDICATION,
                "scheduled_date": now - timedelta(days=6),
                "completed_date": now - timedelta(days=6, hours=2),
                "status": EntryStatus.PARTIALLY_COMPLETED,
                "form_version": "v2.1",
                "responses": {"took_medication": True, "dose_mg": 40.0},
                "total_questions": 5,
                "answered_questions": 3,
                "completion_pct": 60.0,
                "time_to_complete_minutes": 2.5,
                "device_type": "Samsung Galaxy S24",
                "submission_source": "web_portal",
                "validated": False,
                "created_at": now - timedelta(days=6),
            },
        ]

        for e in entries_data:
            self._diary_entries[e["id"]] = DiaryEntry(**e)

        # --- 10 Symptom Records ---
        symptoms_data = [
            {
                "id": "SR-001",
                "entry_id": "DE-001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1001",
                "symptom_name": "Headache",
                "severity_score": 3,
                "frequency": "daily",
                "onset_date": now - timedelta(days=16),
                "duration_hours": 4.0,
                "interference_score": 2,
                "treatment_taken": True,
                "treatment_description": "Acetaminophen 500mg",
                "reported_to_site": False,
                "ae_reference": None,
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "SR-002",
                "entry_id": "DE-001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1001",
                "symptom_name": "Fatigue",
                "severity_score": 4,
                "frequency": "daily",
                "onset_date": now - timedelta(days=15),
                "duration_hours": 8.0,
                "interference_score": 5,
                "treatment_taken": False,
                "treatment_description": None,
                "reported_to_site": True,
                "ae_reference": "AE-0012",
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "SR-003",
                "entry_id": "DE-004",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2001",
                "symptom_name": "Pruritus",
                "severity_score": 6,
                "frequency": "intermittent",
                "onset_date": now - timedelta(days=10),
                "duration_hours": 12.0,
                "interference_score": 7,
                "treatment_taken": True,
                "treatment_description": "Topical corticosteroid applied twice daily",
                "reported_to_site": True,
                "ae_reference": None,
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "SR-004",
                "entry_id": "DE-004",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2001",
                "symptom_name": "Skin Redness",
                "severity_score": 5,
                "frequency": "constant",
                "onset_date": now - timedelta(days=9),
                "duration_hours": 24.0,
                "interference_score": 4,
                "treatment_taken": False,
                "treatment_description": None,
                "reported_to_site": False,
                "ae_reference": None,
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "SR-005",
                "entry_id": "DE-005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2001",
                "symptom_name": "Joint Pain",
                "severity_score": 4,
                "frequency": "daily",
                "onset_date": now - timedelta(days=8),
                "duration_hours": 6.0,
                "interference_score": 5,
                "treatment_taken": True,
                "treatment_description": "Ibuprofen 400mg as needed",
                "reported_to_site": False,
                "ae_reference": None,
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "SR-006",
                "entry_id": "DE-006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2002",
                "symptom_name": "Headache",
                "severity_score": 2,
                "frequency": "occasional",
                "onset_date": now - timedelta(days=4),
                "duration_hours": 2.0,
                "interference_score": 1,
                "treatment_taken": False,
                "treatment_description": None,
                "reported_to_site": False,
                "ae_reference": None,
                "created_at": now - timedelta(days=4),
            },
            {
                "id": "SR-007",
                "entry_id": "DE-008",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3001",
                "symptom_name": "Fatigue",
                "severity_score": 5,
                "frequency": "daily",
                "onset_date": now - timedelta(days=5),
                "duration_hours": 10.0,
                "interference_score": 6,
                "treatment_taken": False,
                "treatment_description": None,
                "reported_to_site": True,
                "ae_reference": "AE-0045",
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "SR-008",
                "entry_id": "DE-009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3002",
                "symptom_name": "Insomnia",
                "severity_score": 4,
                "frequency": "nightly",
                "onset_date": now - timedelta(days=3),
                "duration_hours": 6.0,
                "interference_score": 5,
                "treatment_taken": True,
                "treatment_description": "Melatonin 3mg",
                "reported_to_site": False,
                "ae_reference": None,
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "SR-009",
                "entry_id": "DE-003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1002",
                "symptom_name": "Blurred Vision",
                "severity_score": 3,
                "frequency": "occasional",
                "onset_date": now - timedelta(days=12),
                "duration_hours": 1.5,
                "interference_score": 4,
                "treatment_taken": False,
                "treatment_description": None,
                "reported_to_site": True,
                "ae_reference": "AE-0023",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "SR-010",
                "entry_id": "DE-010",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1003",
                "symptom_name": "Anxiety",
                "severity_score": 3,
                "frequency": "intermittent",
                "onset_date": now - timedelta(days=2),
                "duration_hours": 3.0,
                "interference_score": 3,
                "treatment_taken": False,
                "treatment_description": None,
                "reported_to_site": False,
                "ae_reference": None,
                "created_at": now - timedelta(days=1),
            },
        ]

        for s in symptoms_data:
            self._symptom_records[s["id"]] = SymptomRecord(**s)

        # --- 10 Diary Schedules ---
        schedules_data = [
            {
                "id": "DS-001",
                "trial_id": EYLEA_TRIAL,
                "diary_type": DiaryType.SYMPTOM,
                "form_name": "Daily Symptom Diary",
                "frequency": "daily",
                "window_before_hours": 2,
                "window_after_hours": 24,
                "reminder_enabled": True,
                "reminder_hours_before": 1,
                "start_visit": "Screening",
                "end_visit": "Week 52",
                "total_entries_expected": 365,
                "is_active": True,
                "created_by": "Dr. Rebecca Foster",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "DS-002",
                "trial_id": EYLEA_TRIAL,
                "diary_type": DiaryType.MEDICATION,
                "form_name": "Medication Adherence Log",
                "frequency": "daily",
                "window_before_hours": 0,
                "window_after_hours": 12,
                "reminder_enabled": True,
                "reminder_hours_before": 2,
                "start_visit": "Randomization",
                "end_visit": "Week 52",
                "total_entries_expected": 365,
                "is_active": True,
                "created_by": "Dr. Rebecca Foster",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "DS-003",
                "trial_id": EYLEA_TRIAL,
                "diary_type": DiaryType.QUALITY_OF_LIFE,
                "form_name": "Weekly QoL Assessment",
                "frequency": "weekly",
                "window_before_hours": 0,
                "window_after_hours": 48,
                "reminder_enabled": True,
                "reminder_hours_before": 4,
                "start_visit": "Screening",
                "end_visit": "Week 52",
                "total_entries_expected": 52,
                "is_active": True,
                "created_by": "Dr. Rebecca Foster",
                "created_at": now - timedelta(days=180),
            },
            {
                "id": "DS-004",
                "trial_id": DUPIXENT_TRIAL,
                "diary_type": DiaryType.SYMPTOM,
                "form_name": "Atopic Dermatitis Symptom Diary",
                "frequency": "daily",
                "window_before_hours": 2,
                "window_after_hours": 24,
                "reminder_enabled": True,
                "reminder_hours_before": 1,
                "start_visit": "Baseline",
                "end_visit": "Week 16",
                "total_entries_expected": 112,
                "is_active": True,
                "created_by": "Dr. James Chen",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "DS-005",
                "trial_id": DUPIXENT_TRIAL,
                "diary_type": DiaryType.PAIN,
                "form_name": "Pain Assessment Diary",
                "frequency": "daily",
                "window_before_hours": 0,
                "window_after_hours": 24,
                "reminder_enabled": True,
                "reminder_hours_before": 2,
                "start_visit": "Baseline",
                "end_visit": "Week 16",
                "total_entries_expected": 112,
                "is_active": True,
                "created_by": "Dr. James Chen",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "DS-006",
                "trial_id": DUPIXENT_TRIAL,
                "diary_type": DiaryType.ADVERSE_EVENT,
                "form_name": "AE Reporting Diary",
                "frequency": "as_needed",
                "window_before_hours": 0,
                "window_after_hours": 72,
                "reminder_enabled": False,
                "reminder_hours_before": 0,
                "start_visit": "Baseline",
                "end_visit": "Week 16",
                "total_entries_expected": 0,
                "is_active": True,
                "created_by": "Dr. James Chen",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "DS-007",
                "trial_id": LIBTAYO_TRIAL,
                "diary_type": DiaryType.SYMPTOM,
                "form_name": "Oncology Symptom Tracker",
                "frequency": "daily",
                "window_before_hours": 2,
                "window_after_hours": 24,
                "reminder_enabled": True,
                "reminder_hours_before": 1,
                "start_visit": "Cycle 1 Day 1",
                "end_visit": "End of Treatment",
                "total_entries_expected": 180,
                "is_active": True,
                "created_by": "Dr. Maria Santos",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "DS-008",
                "trial_id": LIBTAYO_TRIAL,
                "diary_type": DiaryType.ACTIVITY,
                "form_name": "Physical Activity Log",
                "frequency": "daily",
                "window_before_hours": 0,
                "window_after_hours": 24,
                "reminder_enabled": True,
                "reminder_hours_before": 3,
                "start_visit": "Cycle 1 Day 1",
                "end_visit": "End of Treatment",
                "total_entries_expected": 180,
                "is_active": True,
                "created_by": "Dr. Maria Santos",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "DS-009",
                "trial_id": LIBTAYO_TRIAL,
                "diary_type": DiaryType.SLEEP,
                "form_name": "Sleep Quality Diary",
                "frequency": "daily",
                "window_before_hours": 0,
                "window_after_hours": 12,
                "reminder_enabled": True,
                "reminder_hours_before": 1,
                "start_visit": "Cycle 1 Day 1",
                "end_visit": "End of Treatment",
                "total_entries_expected": 180,
                "is_active": True,
                "created_by": "Dr. Maria Santos",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "DS-010",
                "trial_id": EYLEA_TRIAL,
                "diary_type": DiaryType.MOOD,
                "form_name": "Mood and Well-Being Tracker",
                "frequency": "weekly",
                "window_before_hours": 0,
                "window_after_hours": 48,
                "reminder_enabled": False,
                "reminder_hours_before": 0,
                "start_visit": "Screening",
                "end_visit": "Week 52",
                "total_entries_expected": 52,
                "is_active": False,
                "created_by": "Dr. Rebecca Foster",
                "created_at": now - timedelta(days=180),
            },
        ]

        for s in schedules_data:
            self._diary_schedules[s["id"]] = DiarySchedule(**s)

        # --- 10 Diary Compliance Records ---
        compliance_data = [
            {
                "id": "DC-001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1001",
                "site_id": "SITE-101",
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "entries_expected": 30,
                "entries_completed": 28,
                "entries_missed": 1,
                "entries_late": 1,
                "compliance_rate": 93.3,
                "compliance_level": ComplianceLevel.EXCELLENT,
                "avg_completion_time_min": 6.5,
                "consecutive_misses": 0,
                "alert_triggered": False,
                "calculated_at": now,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "DC-002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1002",
                "site_id": "SITE-101",
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "entries_expected": 30,
                "entries_completed": 25,
                "entries_missed": 3,
                "entries_late": 2,
                "compliance_rate": 83.3,
                "compliance_level": ComplianceLevel.GOOD,
                "avg_completion_time_min": 8.0,
                "consecutive_misses": 1,
                "alert_triggered": False,
                "calculated_at": now,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "DC-003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1003",
                "site_id": "SITE-102",
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "entries_expected": 30,
                "entries_completed": 22,
                "entries_missed": 5,
                "entries_late": 3,
                "compliance_rate": 73.3,
                "compliance_level": ComplianceLevel.MODERATE,
                "avg_completion_time_min": 7.5,
                "consecutive_misses": 2,
                "alert_triggered": False,
                "calculated_at": now,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "DC-004",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2001",
                "site_id": "SITE-103",
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "entries_expected": 30,
                "entries_completed": 27,
                "entries_missed": 1,
                "entries_late": 2,
                "compliance_rate": 90.0,
                "compliance_level": ComplianceLevel.EXCELLENT,
                "avg_completion_time_min": 7.0,
                "consecutive_misses": 0,
                "alert_triggered": False,
                "calculated_at": now,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "DC-005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2002",
                "site_id": "SITE-104",
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "entries_expected": 30,
                "entries_completed": 18,
                "entries_missed": 8,
                "entries_late": 4,
                "compliance_rate": 60.0,
                "compliance_level": ComplianceLevel.POOR,
                "avg_completion_time_min": 9.5,
                "consecutive_misses": 3,
                "alert_triggered": True,
                "calculated_at": now,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "DC-006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2003",
                "site_id": "SITE-104",
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "entries_expected": 30,
                "entries_completed": 26,
                "entries_missed": 2,
                "entries_late": 2,
                "compliance_rate": 86.7,
                "compliance_level": ComplianceLevel.GOOD,
                "avg_completion_time_min": 5.5,
                "consecutive_misses": 0,
                "alert_triggered": False,
                "calculated_at": now,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "DC-007",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3001",
                "site_id": "SITE-105",
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "entries_expected": 30,
                "entries_completed": 12,
                "entries_missed": 14,
                "entries_late": 4,
                "compliance_rate": 40.0,
                "compliance_level": ComplianceLevel.NON_COMPLIANT,
                "avg_completion_time_min": 4.0,
                "consecutive_misses": 5,
                "alert_triggered": True,
                "calculated_at": now,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "DC-008",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3002",
                "site_id": "SITE-106",
                "period_start": now - timedelta(days=30),
                "period_end": now,
                "entries_expected": 30,
                "entries_completed": 24,
                "entries_missed": 4,
                "entries_late": 2,
                "compliance_rate": 80.0,
                "compliance_level": ComplianceLevel.GOOD,
                "avg_completion_time_min": 5.0,
                "consecutive_misses": 1,
                "alert_triggered": False,
                "calculated_at": now,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "DC-009",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1001",
                "site_id": "SITE-101",
                "period_start": now - timedelta(days=60),
                "period_end": now - timedelta(days=30),
                "entries_expected": 30,
                "entries_completed": 30,
                "entries_missed": 0,
                "entries_late": 0,
                "compliance_rate": 100.0,
                "compliance_level": ComplianceLevel.EXCELLENT,
                "avg_completion_time_min": 5.8,
                "consecutive_misses": 0,
                "alert_triggered": False,
                "calculated_at": now - timedelta(days=30),
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "DC-010",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2001",
                "site_id": "SITE-103",
                "period_start": now - timedelta(days=60),
                "period_end": now - timedelta(days=30),
                "entries_expected": 30,
                "entries_completed": 29,
                "entries_missed": 0,
                "entries_late": 1,
                "compliance_rate": 96.7,
                "compliance_level": ComplianceLevel.EXCELLENT,
                "avg_completion_time_min": 6.2,
                "consecutive_misses": 0,
                "alert_triggered": False,
                "calculated_at": now - timedelta(days=30),
                "created_at": now - timedelta(days=60),
            },
        ]

        for c in compliance_data:
            self._diary_compliance[c["id"]] = DiaryCompliance(**c)

        # --- 10 Diary Validations ---
        validations_data = [
            {
                "id": "DV-001",
                "entry_id": "DE-001",
                "trial_id": EYLEA_TRIAL,
                "validation_status": ValidationStatus.VALID,
                "total_checks": 10,
                "passed_checks": 10,
                "warnings": [],
                "errors": [],
                "out_of_range_values": [],
                "reviewer": "Sarah Mitchell",
                "review_date": now - timedelta(days=13),
                "review_notes": "All responses within expected ranges.",
                "created_at": now - timedelta(days=14),
            },
            {
                "id": "DV-002",
                "entry_id": "DE-002",
                "trial_id": EYLEA_TRIAL,
                "validation_status": ValidationStatus.VALID,
                "total_checks": 5,
                "passed_checks": 5,
                "warnings": [],
                "errors": [],
                "out_of_range_values": [],
                "reviewer": "Sarah Mitchell",
                "review_date": now - timedelta(days=12),
                "review_notes": "Medication adherence confirmed.",
                "created_at": now - timedelta(days=13),
            },
            {
                "id": "DV-003",
                "entry_id": "DE-003",
                "trial_id": EYLEA_TRIAL,
                "validation_status": ValidationStatus.VALID,
                "total_checks": 15,
                "passed_checks": 15,
                "warnings": [],
                "errors": [],
                "out_of_range_values": [],
                "reviewer": "David Park",
                "review_date": now - timedelta(days=9),
                "review_notes": "QoL scores consistent with previous assessments.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "DV-004",
                "entry_id": "DE-004",
                "trial_id": DUPIXENT_TRIAL,
                "validation_status": ValidationStatus.WARNINGS,
                "total_checks": 12,
                "passed_checks": 10,
                "warnings": ["Entry submitted outside completion window", "Itching score increased significantly from last entry"],
                "errors": [],
                "out_of_range_values": [],
                "reviewer": None,
                "review_date": None,
                "review_notes": None,
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "DV-005",
                "entry_id": "DE-005",
                "trial_id": DUPIXENT_TRIAL,
                "validation_status": ValidationStatus.VALID,
                "total_checks": 8,
                "passed_checks": 8,
                "warnings": [],
                "errors": [],
                "out_of_range_values": [],
                "reviewer": "Jennifer Lee",
                "review_date": now - timedelta(days=4),
                "review_notes": "Pain assessment within expected range for treatment phase.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "DV-006",
                "entry_id": "DE-006",
                "trial_id": DUPIXENT_TRIAL,
                "validation_status": ValidationStatus.REVIEWED,
                "total_checks": 10,
                "passed_checks": 10,
                "warnings": [],
                "errors": [],
                "out_of_range_values": [],
                "reviewer": "Jennifer Lee",
                "review_date": now - timedelta(days=3),
                "review_notes": "AE entry reviewed and forwarded to safety team.",
                "created_at": now - timedelta(days=4),
            },
            {
                "id": "DV-007",
                "entry_id": "DE-008",
                "trial_id": LIBTAYO_TRIAL,
                "validation_status": ValidationStatus.VALID,
                "total_checks": 6,
                "passed_checks": 6,
                "warnings": [],
                "errors": [],
                "out_of_range_values": [],
                "reviewer": "David Park",
                "review_date": now - timedelta(days=1),
                "review_notes": "Activity levels consistent.",
                "created_at": now - timedelta(days=2),
            },
            {
                "id": "DV-008",
                "entry_id": "DE-009",
                "trial_id": LIBTAYO_TRIAL,
                "validation_status": ValidationStatus.PENDING_REVIEW,
                "total_checks": 8,
                "passed_checks": 7,
                "warnings": ["Sleep hours below minimum expected threshold"],
                "errors": [],
                "out_of_range_values": ["hours_slept: 6.5 (expected >= 7.0)"],
                "reviewer": None,
                "review_date": None,
                "review_notes": None,
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "DV-009",
                "entry_id": "DE-012",
                "trial_id": EYLEA_TRIAL,
                "validation_status": ValidationStatus.ERRORS,
                "total_checks": 5,
                "passed_checks": 3,
                "warnings": ["Partial completion detected"],
                "errors": ["Missing required field: time_taken", "Missing required field: side_effects_noted"],
                "out_of_range_values": [],
                "reviewer": None,
                "review_date": None,
                "review_notes": None,
                "created_at": now - timedelta(days=6),
            },
            {
                "id": "DV-010",
                "entry_id": "DE-010",
                "trial_id": EYLEA_TRIAL,
                "validation_status": ValidationStatus.VALID,
                "total_checks": 10,
                "passed_checks": 10,
                "warnings": [],
                "errors": [],
                "out_of_range_values": [],
                "reviewer": "Sarah Mitchell",
                "review_date": now - timedelta(hours=12),
                "review_notes": "Mood assessment completed accurately.",
                "created_at": now - timedelta(days=1),
            },
        ]

        for v in validations_data:
            self._diary_validations[v["id"]] = DiaryValidation(**v)

    # ------------------------------------------------------------------
    # Diary Entries
    # ------------------------------------------------------------------

    def list_diary_entries(
        self,
        *,
        trial_id: str | None = None,
        subject_id: str | None = None,
        status: EntryStatus | None = None,
        diary_type: DiaryType | None = None,
    ) -> list[DiaryEntry]:
        """List diary entries with optional filters."""
        with self._lock:
            result = list(self._diary_entries.values())

        if trial_id is not None:
            result = [e for e in result if e.trial_id == trial_id]
        if subject_id is not None:
            result = [e for e in result if e.subject_id == subject_id]
        if status is not None:
            result = [e for e in result if e.status == status]
        if diary_type is not None:
            result = [e for e in result if e.diary_type == diary_type]

        return sorted(result, key=lambda e: e.scheduled_date, reverse=True)

    def get_diary_entry(self, entry_id: str) -> DiaryEntry | None:
        """Get a single diary entry by ID."""
        with self._lock:
            return self._diary_entries.get(entry_id)

    def create_diary_entry(self, payload: DiaryEntryCreate) -> DiaryEntry:
        """Create a new diary entry."""
        now = datetime.now(timezone.utc)
        entry_id = f"DE-{uuid4().hex[:8].upper()}"
        entry = DiaryEntry(
            id=entry_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            site_id=payload.site_id,
            diary_type=payload.diary_type,
            scheduled_date=now,
            completed_date=None,
            status=EntryStatus.PENDING,
            form_version=payload.form_version,
            responses={},
            total_questions=0,
            answered_questions=0,
            completion_pct=0.0,
            time_to_complete_minutes=None,
            device_type=payload.device_type,
            submission_source="mobile_app",
            validated=False,
            created_at=now,
        )
        with self._lock:
            self._diary_entries[entry_id] = entry
        logger.info("Created diary entry %s for subject %s", entry_id, payload.subject_id)
        return entry

    def update_diary_entry(self, entry_id: str, payload: DiaryEntryUpdate) -> DiaryEntry | None:
        """Update an existing diary entry."""
        with self._lock:
            existing = self._diary_entries.get(entry_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set completed_date when status goes to completed
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = EntryStatus(new_status)
                if new_status == EntryStatus.COMPLETED and existing.status != EntryStatus.COMPLETED:
                    data["completed_date"] = datetime.now(timezone.utc)

            # Recalculate completion_pct if answered_questions changed
            if "answered_questions" in updates and data.get("total_questions", 0) > 0:
                answered = updates["answered_questions"]
                total = data["total_questions"]
                data["completion_pct"] = round(answered / total * 100.0, 1)

            data.update(updates)
            updated = DiaryEntry(**data)
            self._diary_entries[entry_id] = updated
        return updated

    def delete_diary_entry(self, entry_id: str) -> bool:
        """Delete a diary entry. Returns True if deleted, False if not found."""
        with self._lock:
            if entry_id in self._diary_entries:
                del self._diary_entries[entry_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Symptom Records
    # ------------------------------------------------------------------

    def list_symptom_records(
        self,
        *,
        trial_id: str | None = None,
        subject_id: str | None = None,
        entry_id: str | None = None,
    ) -> list[SymptomRecord]:
        """List symptom records with optional filters."""
        with self._lock:
            result = list(self._symptom_records.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if subject_id is not None:
            result = [s for s in result if s.subject_id == subject_id]
        if entry_id is not None:
            result = [s for s in result if s.entry_id == entry_id]

        return sorted(result, key=lambda s: s.created_at, reverse=True)

    def get_symptom_record(self, record_id: str) -> SymptomRecord | None:
        """Get a single symptom record by ID."""
        with self._lock:
            return self._symptom_records.get(record_id)

    def create_symptom_record(self, payload: SymptomRecordCreate) -> SymptomRecord:
        """Create a new symptom record."""
        now = datetime.now(timezone.utc)
        record_id = f"SR-{uuid4().hex[:8].upper()}"
        record = SymptomRecord(
            id=record_id,
            entry_id=payload.entry_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            symptom_name=payload.symptom_name,
            severity_score=payload.severity_score,
            frequency=payload.frequency,
            onset_date=None,
            duration_hours=None,
            interference_score=None,
            treatment_taken=payload.treatment_taken,
            treatment_description=None,
            reported_to_site=False,
            ae_reference=None,
            created_at=now,
        )
        with self._lock:
            self._symptom_records[record_id] = record
        logger.info("Created symptom record %s: %s", record_id, payload.symptom_name)
        return record

    def update_symptom_record(self, record_id: str, payload: SymptomRecordUpdate) -> SymptomRecord | None:
        """Update an existing symptom record."""
        with self._lock:
            existing = self._symptom_records.get(record_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = SymptomRecord(**data)
            self._symptom_records[record_id] = updated
        return updated

    def delete_symptom_record(self, record_id: str) -> bool:
        """Delete a symptom record. Returns True if deleted."""
        with self._lock:
            if record_id in self._symptom_records:
                del self._symptom_records[record_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Diary Schedules
    # ------------------------------------------------------------------

    def list_diary_schedules(
        self,
        *,
        trial_id: str | None = None,
        diary_type: DiaryType | None = None,
        is_active: bool | None = None,
    ) -> list[DiarySchedule]:
        """List diary schedules with optional filters."""
        with self._lock:
            result = list(self._diary_schedules.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if diary_type is not None:
            result = [s for s in result if s.diary_type == diary_type]
        if is_active is not None:
            result = [s for s in result if s.is_active == is_active]

        return sorted(result, key=lambda s: s.id)

    def get_diary_schedule(self, schedule_id: str) -> DiarySchedule | None:
        """Get a single diary schedule by ID."""
        with self._lock:
            return self._diary_schedules.get(schedule_id)

    def create_diary_schedule(self, payload: DiaryScheduleCreate) -> DiarySchedule:
        """Create a new diary schedule."""
        now = datetime.now(timezone.utc)
        schedule_id = f"DS-{uuid4().hex[:8].upper()}"
        schedule = DiarySchedule(
            id=schedule_id,
            trial_id=payload.trial_id,
            diary_type=payload.diary_type,
            form_name=payload.form_name,
            frequency=payload.frequency,
            window_before_hours=0,
            window_after_hours=payload.window_after_hours,
            reminder_enabled=payload.reminder_enabled,
            reminder_hours_before=2,
            start_visit=None,
            end_visit=None,
            total_entries_expected=0,
            is_active=True,
            created_by=payload.created_by,
            created_at=now,
        )
        with self._lock:
            self._diary_schedules[schedule_id] = schedule
        logger.info("Created diary schedule %s: %s", schedule_id, payload.form_name)
        return schedule

    def update_diary_schedule(self, schedule_id: str, payload: DiaryScheduleUpdate) -> DiarySchedule | None:
        """Update an existing diary schedule."""
        with self._lock:
            existing = self._diary_schedules.get(schedule_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DiarySchedule(**data)
            self._diary_schedules[schedule_id] = updated
        return updated

    def delete_diary_schedule(self, schedule_id: str) -> bool:
        """Delete a diary schedule. Returns True if deleted."""
        with self._lock:
            if schedule_id in self._diary_schedules:
                del self._diary_schedules[schedule_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Diary Compliance
    # ------------------------------------------------------------------

    def list_diary_compliance(
        self,
        *,
        trial_id: str | None = None,
        subject_id: str | None = None,
        compliance_level: ComplianceLevel | None = None,
    ) -> list[DiaryCompliance]:
        """List diary compliance records with optional filters."""
        with self._lock:
            result = list(self._diary_compliance.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if subject_id is not None:
            result = [c for c in result if c.subject_id == subject_id]
        if compliance_level is not None:
            result = [c for c in result if c.compliance_level == compliance_level]

        return sorted(result, key=lambda c: c.calculated_at, reverse=True)

    def get_diary_compliance(self, compliance_id: str) -> DiaryCompliance | None:
        """Get a single compliance record by ID."""
        with self._lock:
            return self._diary_compliance.get(compliance_id)

    def create_diary_compliance(self, payload: DiaryComplianceCreate) -> DiaryCompliance:
        """Create a new compliance record."""
        now = datetime.now(timezone.utc)
        compliance_id = f"DC-{uuid4().hex[:8].upper()}"
        compliance = DiaryCompliance(
            id=compliance_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            site_id=payload.site_id,
            period_start=payload.period_start,
            period_end=payload.period_end,
            entries_expected=0,
            entries_completed=0,
            entries_missed=0,
            entries_late=0,
            compliance_rate=0.0,
            compliance_level=ComplianceLevel.GOOD,
            avg_completion_time_min=None,
            consecutive_misses=0,
            alert_triggered=False,
            calculated_at=now,
            created_at=now,
        )
        with self._lock:
            self._diary_compliance[compliance_id] = compliance
        logger.info("Created compliance record %s for subject %s", compliance_id, payload.subject_id)
        return compliance

    def update_diary_compliance(self, compliance_id: str, payload: DiaryComplianceUpdate) -> DiaryCompliance | None:
        """Update an existing compliance record."""
        with self._lock:
            existing = self._diary_compliance.get(compliance_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Recalculate compliance_rate if entries changed
            if "entries_completed" in updates or "entries_missed" in updates:
                completed = updates.get("entries_completed", data["entries_completed"])
                expected = data["entries_expected"]
                if expected > 0:
                    data["compliance_rate"] = round(completed / expected * 100.0, 1)

            data.update(updates)
            updated = DiaryCompliance(**data)
            self._diary_compliance[compliance_id] = updated
        return updated

    def delete_diary_compliance(self, compliance_id: str) -> bool:
        """Delete a compliance record. Returns True if deleted."""
        with self._lock:
            if compliance_id in self._diary_compliance:
                del self._diary_compliance[compliance_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Diary Validations
    # ------------------------------------------------------------------

    def list_diary_validations(
        self,
        *,
        trial_id: str | None = None,
        entry_id: str | None = None,
        validation_status: ValidationStatus | None = None,
    ) -> list[DiaryValidation]:
        """List diary validations with optional filters."""
        with self._lock:
            result = list(self._diary_validations.values())

        if trial_id is not None:
            result = [v for v in result if v.trial_id == trial_id]
        if entry_id is not None:
            result = [v for v in result if v.entry_id == entry_id]
        if validation_status is not None:
            result = [v for v in result if v.validation_status == validation_status]

        return sorted(result, key=lambda v: v.created_at, reverse=True)

    def get_diary_validation(self, validation_id: str) -> DiaryValidation | None:
        """Get a single validation record by ID."""
        with self._lock:
            return self._diary_validations.get(validation_id)

    def create_diary_validation(self, payload: DiaryValidationCreate) -> DiaryValidation:
        """Create a new validation record."""
        now = datetime.now(timezone.utc)
        validation_id = f"DV-{uuid4().hex[:8].upper()}"
        validation = DiaryValidation(
            id=validation_id,
            entry_id=payload.entry_id,
            trial_id=payload.trial_id,
            validation_status=ValidationStatus.PENDING_REVIEW,
            total_checks=payload.total_checks,
            passed_checks=0,
            warnings=[],
            errors=[],
            out_of_range_values=[],
            reviewer=None,
            review_date=None,
            review_notes=None,
            created_at=now,
        )
        with self._lock:
            self._diary_validations[validation_id] = validation
        logger.info("Created validation %s for entry %s", validation_id, payload.entry_id)
        return validation

    def update_diary_validation(self, validation_id: str, payload: DiaryValidationUpdate) -> DiaryValidation | None:
        """Update an existing validation record."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._diary_validations.get(validation_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set review_date when reviewer is assigned
            if "reviewer" in updates and updates["reviewer"] is not None and existing.reviewer is None:
                data["review_date"] = now

            data.update(updates)
            updated = DiaryValidation(**data)
            self._diary_validations[validation_id] = updated
        return updated

    def delete_diary_validation(self, validation_id: str) -> bool:
        """Delete a validation record. Returns True if deleted."""
        with self._lock:
            if validation_id in self._diary_validations:
                del self._diary_validations[validation_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> PatientDiaryMetrics:
        """Compute aggregated patient diary operational metrics."""
        with self._lock:
            entries = list(self._diary_entries.values())
            symptoms = list(self._symptom_records.values())
            schedules = list(self._diary_schedules.values())
            compliance = list(self._diary_compliance.values())
            validations = list(self._diary_validations.values())

        # Entries by type
        entries_by_type: dict[str, int] = {}
        for entry in entries:
            key = entry.diary_type.value
            entries_by_type[key] = entries_by_type.get(key, 0) + 1

        # Entries by status
        entries_by_status: dict[str, int] = {}
        for entry in entries:
            key = entry.status.value
            entries_by_status[key] = entries_by_status.get(key, 0) + 1

        # Overall compliance rate
        if compliance:
            overall_compliance = round(
                sum(c.compliance_rate for c in compliance) / len(compliance), 1
            )
        else:
            overall_compliance = 0.0

        # Compliance by level
        compliance_by_level: dict[str, int] = {}
        for c in compliance:
            key = c.compliance_level.value
            compliance_by_level[key] = compliance_by_level.get(key, 0) + 1

        # Average severity score
        if symptoms:
            avg_severity = round(
                sum(s.severity_score for s in symptoms) / len(symptoms), 1
            )
        else:
            avg_severity = 0.0

        # Schedules
        active_schedules = sum(1 for s in schedules if s.is_active)

        # Validations with errors
        validations_with_errors = sum(
            1 for v in validations if v.validation_status == ValidationStatus.ERRORS
        )

        # Average completion time
        completed_entries = [
            e for e in entries if e.time_to_complete_minutes is not None
        ]
        if completed_entries:
            avg_completion_time = round(
                sum(e.time_to_complete_minutes for e in completed_entries) / len(completed_entries),  # type: ignore[arg-type]
                1,
            )
        else:
            avg_completion_time = 0.0

        return PatientDiaryMetrics(
            total_entries=len(entries),
            entries_by_type=entries_by_type,
            entries_by_status=entries_by_status,
            overall_compliance_rate=overall_compliance,
            compliance_by_level=compliance_by_level,
            total_symptoms=len(symptoms),
            avg_severity_score=avg_severity,
            total_schedules=len(schedules),
            active_schedules=active_schedules,
            total_validations=len(validations),
            validations_with_errors=validations_with_errors,
            avg_completion_time_min=avg_completion_time,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: PatientDiaryService | None = None
_instance_lock = threading.Lock()


def get_patient_diary_service() -> PatientDiaryService:
    """Return the singleton PatientDiaryService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = PatientDiaryService()
    return _instance


def reset_patient_diary_service() -> PatientDiaryService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = PatientDiaryService()
    return _instance
