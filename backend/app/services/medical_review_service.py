"""Medical Review & Lab Data Review Service (CLINICAL-14).

Manages medical review operations including review task assignment, medical coding
with auto-coding confidence scoring, data listing generation, medical signal
detection with risk ratio calculation, review prioritization, and overdue
escalation.

Usage:
    from app.services.medical_review_service import (
        get_medical_review_service,
    )

    svc = get_medical_review_service()
    tasks = svc.list_review_tasks()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import math
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.medical_review import (
    CodingDictionary,
    CodingLevel,
    CodingStatus,
    CodingTask,
    CodingTaskCreate,
    CodingTaskUpdate,
    DataListing,
    DataListingCreate,
    ListingType,
    MedicalReviewMetrics,
    MedicalReviewTask,
    MedicalReviewTaskCreate,
    MedicalReviewTaskUpdate,
    MedicalSignal,
    MedicalSignalCreate,
    MedicalSignalUpdate,
    ReviewPriority,
    ReviewStatus,
    ReviewType,
    SignalCategory,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# Auto-coding confidence thresholds
CONFIDENCE_AUTO_ACCEPT = 0.9
CONFIDENCE_MANUAL_REVIEW = 0.7
# Below 0.7 -> query raised

# Overdue escalation threshold (hours)
OVERDUE_THRESHOLD_HOURS = 48


class MedicalReviewService:
    """In-memory Medical Review engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._review_tasks: dict[str, MedicalReviewTask] = {}
        self._coding_tasks: dict[str, CodingTask] = {}
        self._data_listings: dict[str, DataListing] = {}
        self._signals: dict[str, MedicalSignal] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic medical review data."""
        now = datetime.now(timezone.utc)

        # --- 25 Review Tasks ---
        reviewers = [
            "Dr. Sarah Chen", "Dr. James Morton", "Dr. Lisa Park",
            "Dr. Michael Torres", "Dr. Anna Kowalski",
        ]
        tasks_data = [
            # AE reviews - critical priority
            {"id": "MRT-001", "trial_id": EYLEA_TRIAL, "patient_id": "PAT-1001", "review_type": ReviewType.AE_REVIEW, "status": ReviewStatus.COMPLETED, "priority": ReviewPriority.CRITICAL, "assigned_reviewer": reviewers[0], "created_date": now - timedelta(days=14), "completed_date": now - timedelta(days=12), "findings": "SAE reviewed - retinal detachment. Causality assessment: possibly related to study drug.", "actions_taken": "SUSAR filed. DSMB notified."},
            {"id": "MRT-002", "trial_id": EYLEA_TRIAL, "patient_id": "PAT-1002", "review_type": ReviewType.AE_REVIEW, "status": ReviewStatus.COMPLETED, "priority": ReviewPriority.CRITICAL, "assigned_reviewer": reviewers[0], "created_date": now - timedelta(days=10), "completed_date": now - timedelta(days=8), "findings": "SAE reviewed - severe allergic reaction. Causality: unlikely related.", "actions_taken": "Safety report updated. No further action."},
            {"id": "MRT-003", "trial_id": DUPIXENT_TRIAL, "patient_id": "PAT-2001", "review_type": ReviewType.AE_REVIEW, "status": ReviewStatus.IN_PROGRESS, "priority": ReviewPriority.CRITICAL, "assigned_reviewer": reviewers[1], "created_date": now - timedelta(days=3), "completed_date": None, "findings": None, "actions_taken": None},
            {"id": "MRT-004", "trial_id": LIBTAYO_TRIAL, "patient_id": "PAT-3001", "review_type": ReviewType.AE_REVIEW, "status": ReviewStatus.PENDING, "priority": ReviewPriority.CRITICAL, "assigned_reviewer": reviewers[2], "created_date": now - timedelta(days=1), "completed_date": None, "findings": None, "actions_taken": None},
            {"id": "MRT-005", "trial_id": LIBTAYO_TRIAL, "patient_id": "PAT-3002", "review_type": ReviewType.AE_REVIEW, "status": ReviewStatus.ESCALATED, "priority": ReviewPriority.CRITICAL, "assigned_reviewer": reviewers[0], "created_date": now - timedelta(days=5), "completed_date": None, "findings": "Escalated - immune-related hepatitis Grade 3. Requires medical monitor review.", "actions_taken": "Escalated to global medical monitor."},
            # Lab reviews - urgent priority
            {"id": "MRT-006", "trial_id": EYLEA_TRIAL, "patient_id": "PAT-1003", "review_type": ReviewType.LAB_REVIEW, "status": ReviewStatus.COMPLETED, "priority": ReviewPriority.URGENT, "assigned_reviewer": reviewers[3], "created_date": now - timedelta(days=7), "completed_date": now - timedelta(days=5), "findings": "Liver function tests elevated - ALT 3x ULN. Confirmed on repeat testing.", "actions_taken": "Drug held. Recheck in 2 weeks."},
            {"id": "MRT-007", "trial_id": DUPIXENT_TRIAL, "patient_id": "PAT-2002", "review_type": ReviewType.LAB_REVIEW, "status": ReviewStatus.IN_PROGRESS, "priority": ReviewPriority.URGENT, "assigned_reviewer": reviewers[3], "created_date": now - timedelta(days=2), "completed_date": None, "findings": None, "actions_taken": None},
            {"id": "MRT-008", "trial_id": LIBTAYO_TRIAL, "patient_id": "PAT-3003", "review_type": ReviewType.LAB_REVIEW, "status": ReviewStatus.PENDING, "priority": ReviewPriority.URGENT, "assigned_reviewer": reviewers[4], "created_date": now - timedelta(days=1), "completed_date": None, "findings": None, "actions_taken": None},
            {"id": "MRT-009", "trial_id": EYLEA_TRIAL, "patient_id": "PAT-1004", "review_type": ReviewType.LAB_REVIEW, "status": ReviewStatus.COMPLETED, "priority": ReviewPriority.URGENT, "assigned_reviewer": reviewers[4], "created_date": now - timedelta(days=20), "completed_date": now - timedelta(days=18), "findings": "Neutropenia Grade 2. Not clinically significant.", "actions_taken": "Continue monitoring per protocol."},
            {"id": "MRT-010", "trial_id": DUPIXENT_TRIAL, "patient_id": "PAT-2003", "review_type": ReviewType.LAB_REVIEW, "status": ReviewStatus.PENDING, "priority": ReviewPriority.URGENT, "assigned_reviewer": reviewers[1], "created_date": now - timedelta(hours=36), "completed_date": None, "findings": None, "actions_taken": None},
            # ConMed reviews
            {"id": "MRT-011", "trial_id": EYLEA_TRIAL, "patient_id": "PAT-1005", "review_type": ReviewType.CONMED_REVIEW, "status": ReviewStatus.COMPLETED, "priority": ReviewPriority.ROUTINE, "assigned_reviewer": reviewers[2], "created_date": now - timedelta(days=15), "completed_date": now - timedelta(days=14), "findings": "Concomitant medication review complete. No prohibited medications.", "actions_taken": "No action required."},
            {"id": "MRT-012", "trial_id": DUPIXENT_TRIAL, "patient_id": "PAT-2004", "review_type": ReviewType.CONMED_REVIEW, "status": ReviewStatus.COMPLETED, "priority": ReviewPriority.URGENT, "assigned_reviewer": reviewers[2], "created_date": now - timedelta(days=8), "completed_date": now - timedelta(days=6), "findings": "Prohibited medication detected - systemic corticosteroids started.", "actions_taken": "Protocol deviation reported. Patient remains in study with waiver."},
            {"id": "MRT-013", "trial_id": LIBTAYO_TRIAL, "patient_id": "PAT-3004", "review_type": ReviewType.CONMED_REVIEW, "status": ReviewStatus.IN_PROGRESS, "priority": ReviewPriority.ROUTINE, "assigned_reviewer": reviewers[3], "created_date": now - timedelta(days=4), "completed_date": None, "findings": None, "actions_taken": None},
            {"id": "MRT-014", "trial_id": EYLEA_TRIAL, "patient_id": "PAT-1006", "review_type": ReviewType.CONMED_REVIEW, "status": ReviewStatus.PENDING, "priority": ReviewPriority.ROUTINE, "assigned_reviewer": reviewers[4], "created_date": now - timedelta(hours=20), "completed_date": None, "findings": None, "actions_taken": None},
            # Eligibility reviews
            {"id": "MRT-015", "trial_id": EYLEA_TRIAL, "patient_id": "PAT-1007", "review_type": ReviewType.ELIGIBILITY_REVIEW, "status": ReviewStatus.COMPLETED, "priority": ReviewPriority.URGENT, "assigned_reviewer": reviewers[0], "created_date": now - timedelta(days=25), "completed_date": now - timedelta(days=24), "findings": "Eligibility confirmed. All inclusion/exclusion criteria met.", "actions_taken": "Patient eligible for randomization."},
            {"id": "MRT-016", "trial_id": DUPIXENT_TRIAL, "patient_id": "PAT-2005", "review_type": ReviewType.ELIGIBILITY_REVIEW, "status": ReviewStatus.COMPLETED, "priority": ReviewPriority.URGENT, "assigned_reviewer": reviewers[1], "created_date": now - timedelta(days=18), "completed_date": now - timedelta(days=17), "findings": "Exclusion criterion #4 borderline - eGFR 29.5 mL/min (cutoff: 30).", "actions_taken": "Patient excluded per protocol. Site notified."},
            {"id": "MRT-017", "trial_id": LIBTAYO_TRIAL, "patient_id": "PAT-3005", "review_type": ReviewType.ELIGIBILITY_REVIEW, "status": ReviewStatus.IN_PROGRESS, "priority": ReviewPriority.URGENT, "assigned_reviewer": reviewers[2], "created_date": now - timedelta(days=2), "completed_date": None, "findings": None, "actions_taken": None},
            {"id": "MRT-018", "trial_id": EYLEA_TRIAL, "patient_id": "PAT-1008", "review_type": ReviewType.ELIGIBILITY_REVIEW, "status": ReviewStatus.PENDING, "priority": ReviewPriority.ROUTINE, "assigned_reviewer": reviewers[3], "created_date": now - timedelta(hours=30), "completed_date": None, "findings": None, "actions_taken": None},
            # Medical history reviews
            {"id": "MRT-019", "trial_id": EYLEA_TRIAL, "patient_id": "PAT-1009", "review_type": ReviewType.MEDICAL_HISTORY_REVIEW, "status": ReviewStatus.COMPLETED, "priority": ReviewPriority.ROUTINE, "assigned_reviewer": reviewers[4], "created_date": now - timedelta(days=30), "completed_date": now - timedelta(days=28), "findings": "Medical history reviewed. Pre-existing hypertension and type 2 diabetes noted.", "actions_taken": "Baseline conditions documented."},
            {"id": "MRT-020", "trial_id": DUPIXENT_TRIAL, "patient_id": "PAT-2006", "review_type": ReviewType.MEDICAL_HISTORY_REVIEW, "status": ReviewStatus.COMPLETED, "priority": ReviewPriority.ROUTINE, "assigned_reviewer": reviewers[0], "created_date": now - timedelta(days=22), "completed_date": now - timedelta(days=21), "findings": "Significant history of asthma and eczema. Relevant to study indication.", "actions_taken": "Baseline conditions documented."},
            {"id": "MRT-021", "trial_id": LIBTAYO_TRIAL, "patient_id": "PAT-3006", "review_type": ReviewType.MEDICAL_HISTORY_REVIEW, "status": ReviewStatus.IN_PROGRESS, "priority": ReviewPriority.ROUTINE, "assigned_reviewer": reviewers[1], "created_date": now - timedelta(days=3), "completed_date": None, "findings": None, "actions_taken": None},
            {"id": "MRT-022", "trial_id": EYLEA_TRIAL, "patient_id": "PAT-1010", "review_type": ReviewType.MEDICAL_HISTORY_REVIEW, "status": ReviewStatus.PENDING, "priority": ReviewPriority.ROUTINE, "assigned_reviewer": reviewers[2], "created_date": now - timedelta(hours=10), "completed_date": None, "findings": None, "actions_taken": None},
            # Additional overdue tasks for escalation testing
            {"id": "MRT-023", "trial_id": DUPIXENT_TRIAL, "patient_id": "PAT-2007", "review_type": ReviewType.AE_REVIEW, "status": ReviewStatus.PENDING, "priority": ReviewPriority.URGENT, "assigned_reviewer": reviewers[3], "created_date": now - timedelta(hours=60), "completed_date": None, "findings": None, "actions_taken": None},
            {"id": "MRT-024", "trial_id": LIBTAYO_TRIAL, "patient_id": "PAT-3007", "review_type": ReviewType.LAB_REVIEW, "status": ReviewStatus.PENDING, "priority": ReviewPriority.ROUTINE, "assigned_reviewer": reviewers[4], "created_date": now - timedelta(hours=72), "completed_date": None, "findings": None, "actions_taken": None},
            {"id": "MRT-025", "trial_id": EYLEA_TRIAL, "patient_id": "PAT-1011", "review_type": ReviewType.CONMED_REVIEW, "status": ReviewStatus.PENDING, "priority": ReviewPriority.ROUTINE, "assigned_reviewer": reviewers[0], "created_date": now - timedelta(hours=55), "completed_date": None, "findings": None, "actions_taken": None},
        ]

        for t in tasks_data:
            self._review_tasks[t["id"]] = MedicalReviewTask(**t)

        # --- 30 Coding Tasks (MedDRA AE terms + WHODrug conmeds) ---
        # ~85% auto-coded, ~15% manual
        ae_terms = [
            ("Headache", "10019211", CodingLevel.PT, "Nervous system disorders"),
            ("Nausea", "10028813", CodingLevel.PT, "Gastrointestinal disorders"),
            ("Injection site reaction", "10022095", CodingLevel.PT, "General disorders and administration site conditions"),
            ("Fatigue", "10016256", CodingLevel.PT, "General disorders and administration site conditions"),
            ("Dizziness", "10013573", CodingLevel.PT, "Nervous system disorders"),
            ("Arthralgia", "10003239", CodingLevel.PT, "Musculoskeletal and connective tissue disorders"),
            ("Pyrexia", "10037660", CodingLevel.PT, "General disorders and administration site conditions"),
            ("Diarrhoea", "10012735", CodingLevel.PT, "Gastrointestinal disorders"),
            ("Rash", "10037844", CodingLevel.PT, "Skin and subcutaneous tissue disorders"),
            ("Upper respiratory tract infection", "10046306", CodingLevel.PT, "Infections and infestations"),
            ("Pruritus", "10037087", CodingLevel.PT, "Skin and subcutaneous tissue disorders"),
            ("Vomiting", "10047700", CodingLevel.PT, "Gastrointestinal disorders"),
            ("Back pain", "10003988", CodingLevel.PT, "Musculoskeletal and connective tissue disorders"),
            ("Myalgia", "10028411", CodingLevel.PT, "Musculoskeletal and connective tissue disorders"),
            ("Insomnia", "10022437", CodingLevel.PT, "Psychiatric disorders"),
            ("Cough", "10011224", CodingLevel.PT, "Respiratory, thoracic and mediastinal disorders"),
            ("Constipation", "10010774", CodingLevel.PT, "Gastrointestinal disorders"),
            ("Abdominal pain", "10000081", CodingLevel.PT, "Gastrointestinal disorders"),
            ("Hypertension", "10020772", CodingLevel.PT, "Vascular disorders"),
            ("Oedema peripheral", "10030124", CodingLevel.PT, "General disorders and administration site conditions"),
        ]

        conmed_terms = [
            ("Paracetamol", "001234", "Analgesics"),
            ("Ibuprofen", "002345", "Anti-inflammatory agents"),
            ("Metformin", "003456", "Antidiabetic agents"),
            ("Lisinopril", "004567", "ACE inhibitors"),
            ("Atorvastatin", "005678", "Lipid modifying agents"),
            ("Omeprazole", "006789", "Proton pump inhibitors"),
            ("Amlodipine", "007890", "Calcium channel blockers"),
            ("Cetirizine", "008901", "Antihistamines"),
            ("Prednisolone", "009012", "Corticosteroids"),
            ("Amoxicillin", "010123", "Penicillins"),
        ]

        coding_counter = 0
        coders = ["Alice Johnson", "Bob Williams", "Carol Davis"]
        verifiers = ["Dr. Sarah Chen", "Dr. James Morton"]

        # MedDRA AE coding tasks (20 tasks)
        for i, (verbatim, code, level, _soc) in enumerate(ae_terms):
            coding_counter += 1
            is_auto = i < 17  # 85% auto-coded
            confidence = round(0.92 + (i % 5) * 0.015, 3) if is_auto else round(0.55 + (i % 3) * 0.08, 3)

            if is_auto and confidence >= CONFIDENCE_AUTO_ACCEPT:
                status = CodingStatus.AUTO_CODED
                coder_name = None
            elif is_auto and confidence >= CONFIDENCE_MANUAL_REVIEW:
                status = CodingStatus.MANUALLY_CODED
                coder_name = coders[i % len(coders)]
            elif not is_auto:
                if i == 17:
                    status = CodingStatus.MANUALLY_CODED
                    coder_name = coders[i % len(coders)]
                elif i == 18:
                    status = CodingStatus.QUERY_RAISED
                    coder_name = None
                else:
                    status = CodingStatus.UNCODED
                    coder_name = None
            else:
                status = CodingStatus.QUERY_RAISED
                coder_name = None

            # Some verified
            verified = None
            if status in (CodingStatus.AUTO_CODED, CodingStatus.MANUALLY_CODED) and i < 12:
                verified = verifiers[i % len(verifiers)]
                status = CodingStatus.VERIFIED

            task = CodingTask(
                id=f"COD-{coding_counter:04d}",
                verbatim_term=verbatim,
                dictionary=CodingDictionary.MEDDRA,
                coded_term=verbatim if status != CodingStatus.UNCODED else None,
                coded_code=code if status != CodingStatus.UNCODED else None,
                level=level,
                status=status,
                auto_coded=is_auto,
                confidence_score=confidence,
                coder=coder_name,
                verified_by=verified,
            )
            self._coding_tasks[task.id] = task

        # WHODrug conmed coding tasks (10 tasks)
        for i, (verbatim, code, _category) in enumerate(conmed_terms):
            coding_counter += 1
            is_auto = i < 9  # 90% auto for conmeds
            confidence = round(0.93 + (i % 4) * 0.012, 3) if is_auto else 0.45

            if is_auto and confidence >= CONFIDENCE_AUTO_ACCEPT:
                status = CodingStatus.AUTO_CODED
                coder_name = None
            else:
                status = CodingStatus.UNCODED
                coder_name = None

            # Some verified
            verified = None
            if status == CodingStatus.AUTO_CODED and i < 6:
                verified = verifiers[i % len(verifiers)]
                status = CodingStatus.VERIFIED

            task = CodingTask(
                id=f"COD-{coding_counter:04d}",
                verbatim_term=verbatim,
                dictionary=CodingDictionary.WHODRUG,
                coded_term=verbatim if status != CodingStatus.UNCODED else None,
                coded_code=code if status != CodingStatus.UNCODED else None,
                level=CodingLevel.PT,
                status=status,
                auto_coded=is_auto,
                confidence_score=confidence,
                coder=coder_name,
                verified_by=verified,
            )
            self._coding_tasks[task.id] = task

        # --- 8 Data Listings ---
        listings_data = [
            {"id": "DL-001", "trial_id": EYLEA_TRIAL, "listing_type": ListingType.AE_LISTING, "generated_date": now - timedelta(days=7), "record_count": 156, "flagged_records": 12, "filters_applied": {"severity": "serious", "relatedness": "all"}},
            {"id": "DL-002", "trial_id": EYLEA_TRIAL, "listing_type": ListingType.LAB_LISTING, "generated_date": now - timedelta(days=5), "record_count": 842, "flagged_records": 34, "filters_applied": {"visit": "all", "abnormal_only": "true"}},
            {"id": "DL-003", "trial_id": DUPIXENT_TRIAL, "listing_type": ListingType.CONMED_LISTING, "generated_date": now - timedelta(days=3), "record_count": 423, "flagged_records": 8, "filters_applied": {"prohibited": "true"}},
            {"id": "DL-004", "trial_id": DUPIXENT_TRIAL, "listing_type": ListingType.AE_LISTING, "generated_date": now - timedelta(days=2), "record_count": 198, "flagged_records": 15, "filters_applied": {"severity": "all"}},
            {"id": "DL-005", "trial_id": LIBTAYO_TRIAL, "listing_type": ListingType.VITALS_LISTING, "generated_date": now - timedelta(days=4), "record_count": 1250, "flagged_records": 45, "filters_applied": {"abnormal_only": "true", "visit_window": "all"}},
            {"id": "DL-006", "trial_id": LIBTAYO_TRIAL, "listing_type": ListingType.MEDHIST_LISTING, "generated_date": now - timedelta(days=6), "record_count": 312, "flagged_records": 5, "filters_applied": {}},
            {"id": "DL-007", "trial_id": EYLEA_TRIAL, "listing_type": ListingType.LAB_LISTING, "generated_date": now - timedelta(days=1), "record_count": 890, "flagged_records": 28, "filters_applied": {"parameter": "liver_function", "abnormal_only": "true"}},
            {"id": "DL-008", "trial_id": LIBTAYO_TRIAL, "listing_type": ListingType.AE_LISTING, "generated_date": now - timedelta(hours=12), "record_count": 267, "flagged_records": 22, "filters_applied": {"severity": "serious", "ongoing": "true"}},
        ]

        for dl in listings_data:
            self._data_listings[dl["id"]] = DataListing(**dl)

        # --- 6 Medical Signals ---
        signals_data = [
            {"id": "SIG-001", "trial_id": EYLEA_TRIAL, "signal_category": SignalCategory.EXPECTED, "term": "Injection site reaction", "observed_count": 45, "expected_count": 50, "patients_affected": 38, "risk_ratio": 0.9, "p_value": 0.68, "assessment": "Injection site reactions occurring at expected rate. No safety concern identified.", "action_required": False},
            {"id": "SIG-002", "trial_id": DUPIXENT_TRIAL, "signal_category": SignalCategory.EXPECTED, "term": "Headache", "observed_count": 32, "expected_count": 35, "patients_affected": 28, "risk_ratio": 0.91, "p_value": 0.72, "assessment": "Headache rate within expected range for this patient population.", "action_required": False},
            {"id": "SIG-003", "trial_id": LIBTAYO_TRIAL, "signal_category": SignalCategory.UNEXPECTED, "term": "Nausea", "observed_count": 28, "expected_count": 15, "patients_affected": 24, "risk_ratio": 1.87, "p_value": 0.003, "assessment": "Nausea rate significantly higher than expected. Possible drug-related effect. Further analysis needed.", "action_required": True},
            {"id": "SIG-004", "trial_id": LIBTAYO_TRIAL, "signal_category": SignalCategory.SERIOUS_UNEXPECTED, "term": "Immune-related hepatitis", "observed_count": 5, "expected_count": 1, "patients_affected": 5, "risk_ratio": 5.0, "p_value": 0.001, "assessment": "Immune-related hepatitis occurring at 5x expected rate. Consistent with known class effect of checkpoint inhibitors. Protocol amendment may be required.", "action_required": True},
            {"id": "SIG-005", "trial_id": EYLEA_TRIAL, "signal_category": SignalCategory.UNEXPECTED, "term": "Visual disturbance", "observed_count": 12, "expected_count": 6, "patients_affected": 11, "risk_ratio": 2.0, "p_value": 0.02, "assessment": "Visual disturbance rate elevated. May be related to underlying condition or procedure. Monitoring recommended.", "action_required": True},
            {"id": "SIG-006", "trial_id": DUPIXENT_TRIAL, "signal_category": SignalCategory.EXPECTED, "term": "Injection site erythema", "observed_count": 22, "expected_count": 25, "patients_affected": 20, "risk_ratio": 0.88, "p_value": 0.55, "assessment": "Injection site erythema within expected range. No concern.", "action_required": False},
        ]

        for s in signals_data:
            self._signals[s["id"]] = MedicalSignal(**s)

    # ------------------------------------------------------------------
    # Review Task Management
    # ------------------------------------------------------------------

    def list_review_tasks(
        self,
        *,
        trial_id: str | None = None,
        review_type: ReviewType | None = None,
        status: ReviewStatus | None = None,
        priority: ReviewPriority | None = None,
        assigned_reviewer: str | None = None,
    ) -> list[MedicalReviewTask]:
        """List review tasks with optional filters."""
        with self._lock:
            result = list(self._review_tasks.values())

        if trial_id is not None:
            result = [t for t in result if t.trial_id == trial_id]
        if review_type is not None:
            result = [t for t in result if t.review_type == review_type]
        if status is not None:
            result = [t for t in result if t.status == status]
        if priority is not None:
            result = [t for t in result if t.priority == priority]
        if assigned_reviewer is not None:
            result = [t for t in result if t.assigned_reviewer == assigned_reviewer]

        # Sort by priority (critical first), then by created date
        priority_order = {
            ReviewPriority.CRITICAL: 0,
            ReviewPriority.URGENT: 1,
            ReviewPriority.ROUTINE: 2,
        }
        return sorted(
            result,
            key=lambda t: (priority_order.get(t.priority, 3), t.created_date),
        )

    def get_review_task(self, task_id: str) -> MedicalReviewTask | None:
        """Get a single review task by ID."""
        with self._lock:
            return self._review_tasks.get(task_id)

    def create_review_task(self, payload: MedicalReviewTaskCreate) -> MedicalReviewTask:
        """Create a new review task."""
        now = datetime.now(timezone.utc)
        task_id = f"MRT-{uuid4().hex[:8].upper()}"
        task = MedicalReviewTask(
            id=task_id,
            trial_id=payload.trial_id,
            patient_id=payload.patient_id,
            review_type=payload.review_type,
            status=ReviewStatus.PENDING,
            priority=payload.priority,
            assigned_reviewer=payload.assigned_reviewer,
            created_date=now,
            completed_date=None,
            findings=None,
            actions_taken=None,
        )
        with self._lock:
            self._review_tasks[task_id] = task
        logger.info("Created review task %s: type=%s priority=%s", task_id, payload.review_type.value, payload.priority.value)
        return task

    def update_review_task(self, task_id: str, payload: MedicalReviewTaskUpdate) -> MedicalReviewTask | None:
        """Update a review task."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._review_tasks.get(task_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set completed_date when status goes to completed
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = ReviewStatus(new_status)
                if new_status == ReviewStatus.COMPLETED and existing.status != ReviewStatus.COMPLETED:
                    updates["completed_date"] = now

            data.update(updates)
            updated = MedicalReviewTask(**data)
            self._review_tasks[task_id] = updated
        return updated

    def delete_review_task(self, task_id: str) -> bool:
        """Delete a review task. Returns True if deleted."""
        with self._lock:
            if task_id in self._review_tasks:
                del self._review_tasks[task_id]
                return True
            return False

    def get_overdue_reviews(self) -> list[MedicalReviewTask]:
        """Get review tasks pending > 48 hours (overdue)."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=OVERDUE_THRESHOLD_HOURS)
        with self._lock:
            result = [
                t for t in self._review_tasks.values()
                if t.status == ReviewStatus.PENDING
                and t.created_date < cutoff
            ]
        return sorted(result, key=lambda t: t.created_date)

    def escalate_overdue_reviews(self) -> list[MedicalReviewTask]:
        """Auto-escalate reviews pending > 48 hours.

        Returns the list of escalated tasks.
        """
        overdue = self.get_overdue_reviews()
        escalated = []
        now = datetime.now(timezone.utc)
        with self._lock:
            for task in overdue:
                existing = self._review_tasks.get(task.id)
                if existing is not None and existing.status == ReviewStatus.PENDING:
                    data = existing.model_dump()
                    data["status"] = ReviewStatus.ESCALATED
                    updated = MedicalReviewTask(**data)
                    self._review_tasks[task.id] = updated
                    escalated.append(updated)
        if escalated:
            logger.info("Auto-escalated %d overdue review tasks", len(escalated))
        return escalated

    # ------------------------------------------------------------------
    # Coding Tasks
    # ------------------------------------------------------------------

    def list_coding_tasks(
        self,
        *,
        dictionary: CodingDictionary | None = None,
        status: CodingStatus | None = None,
        auto_coded: bool | None = None,
    ) -> list[CodingTask]:
        """List coding tasks with optional filters."""
        with self._lock:
            result = list(self._coding_tasks.values())

        if dictionary is not None:
            result = [c for c in result if c.dictionary == dictionary]
        if status is not None:
            result = [c for c in result if c.status == status]
        if auto_coded is not None:
            result = [c for c in result if c.auto_coded == auto_coded]

        return sorted(result, key=lambda c: c.id)

    def get_coding_task(self, task_id: str) -> CodingTask | None:
        """Get a single coding task by ID."""
        with self._lock:
            return self._coding_tasks.get(task_id)

    def create_coding_task(self, payload: CodingTaskCreate) -> CodingTask:
        """Create a coding task and attempt auto-coding."""
        task_id = f"COD-{uuid4().hex[:8].upper()}"

        # Attempt auto-coding
        auto_result = self._auto_code(payload.verbatim_term, payload.dictionary)

        if auto_result is not None:
            coded_term, coded_code, confidence = auto_result
            if confidence >= CONFIDENCE_AUTO_ACCEPT:
                status = CodingStatus.AUTO_CODED
            elif confidence >= CONFIDENCE_MANUAL_REVIEW:
                status = CodingStatus.UNCODED  # Needs manual review
            else:
                status = CodingStatus.QUERY_RAISED
        else:
            coded_term, coded_code, confidence = None, None, None
            status = CodingStatus.UNCODED

        task = CodingTask(
            id=task_id,
            verbatim_term=payload.verbatim_term,
            dictionary=payload.dictionary,
            coded_term=coded_term if status == CodingStatus.AUTO_CODED else None,
            coded_code=coded_code if status == CodingStatus.AUTO_CODED else None,
            level=payload.level,
            status=status,
            auto_coded=status == CodingStatus.AUTO_CODED,
            confidence_score=confidence,
            coder=None,
            verified_by=None,
        )
        with self._lock:
            self._coding_tasks[task_id] = task
        logger.info(
            "Created coding task %s: term='%s' dict=%s status=%s confidence=%s",
            task_id, payload.verbatim_term, payload.dictionary.value,
            status.value, confidence,
        )
        return task

    def update_coding_task(self, task_id: str, payload: CodingTaskUpdate) -> CodingTask | None:
        """Update a coding task (manual coding, verification)."""
        with self._lock:
            existing = self._coding_tasks.get(task_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CodingTask(**data)
            self._coding_tasks[task_id] = updated
        return updated

    def _auto_code(
        self, verbatim_term: str, dictionary: CodingDictionary
    ) -> tuple[str, str, float] | None:
        """Attempt auto-coding of a verbatim term.

        Returns (coded_term, coded_code, confidence) or None if no match.
        """
        # Simple lookup-based auto-coding for demonstration
        term_lower = verbatim_term.lower().strip()

        if dictionary == CodingDictionary.MEDDRA:
            meddra_lookup = {
                "headache": ("Headache", "10019211", 0.98),
                "nausea": ("Nausea", "10028813", 0.97),
                "injection site reaction": ("Injection site reaction", "10022095", 0.96),
                "fatigue": ("Fatigue", "10016256", 0.95),
                "dizziness": ("Dizziness", "10013573", 0.94),
                "rash": ("Rash", "10037844", 0.93),
                "vomiting": ("Vomiting", "10047700", 0.95),
                "diarrhoea": ("Diarrhoea", "10012735", 0.94),
                "diarrhea": ("Diarrhoea", "10012735", 0.92),
                "pyrexia": ("Pyrexia", "10037660", 0.91),
                "fever": ("Pyrexia", "10037660", 0.85),
                "back pain": ("Back pain", "10003988", 0.93),
                "cough": ("Cough", "10011224", 0.96),
                "constipation": ("Constipation", "10010774", 0.95),
                "abdominal pain": ("Abdominal pain", "10000081", 0.94),
            }
            return meddra_lookup.get(term_lower)

        elif dictionary == CodingDictionary.WHODRUG:
            whodrug_lookup = {
                "paracetamol": ("Paracetamol", "001234", 0.97),
                "acetaminophen": ("Paracetamol", "001234", 0.90),
                "ibuprofen": ("Ibuprofen", "002345", 0.96),
                "metformin": ("Metformin", "003456", 0.95),
                "lisinopril": ("Lisinopril", "004567", 0.94),
                "atorvastatin": ("Atorvastatin", "005678", 0.96),
                "omeprazole": ("Omeprazole", "006789", 0.95),
                "amlodipine": ("Amlodipine", "007890", 0.94),
                "cetirizine": ("Cetirizine", "008901", 0.93),
                "amoxicillin": ("Amoxicillin", "010123", 0.95),
            }
            return whodrug_lookup.get(term_lower)

        return None

    # ------------------------------------------------------------------
    # Data Listings
    # ------------------------------------------------------------------

    def list_data_listings(
        self,
        *,
        trial_id: str | None = None,
        listing_type: ListingType | None = None,
    ) -> list[DataListing]:
        """List data listings with optional filters."""
        with self._lock:
            result = list(self._data_listings.values())

        if trial_id is not None:
            result = [dl for dl in result if dl.trial_id == trial_id]
        if listing_type is not None:
            result = [dl for dl in result if dl.listing_type == listing_type]

        return sorted(result, key=lambda dl: dl.generated_date, reverse=True)

    def get_data_listing(self, listing_id: str) -> DataListing | None:
        """Get a single data listing by ID."""
        with self._lock:
            return self._data_listings.get(listing_id)

    def create_data_listing(self, payload: DataListingCreate) -> DataListing:
        """Generate a new data listing."""
        now = datetime.now(timezone.utc)
        listing_id = f"DL-{uuid4().hex[:8].upper()}"

        # Simulate record generation
        import random
        record_count = random.randint(50, 500)
        flagged_records = random.randint(0, max(1, record_count // 10))

        listing = DataListing(
            id=listing_id,
            trial_id=payload.trial_id,
            listing_type=payload.listing_type,
            generated_date=now,
            record_count=record_count,
            flagged_records=flagged_records,
            filters_applied=payload.filters_applied,
        )
        with self._lock:
            self._data_listings[listing_id] = listing
        logger.info(
            "Generated data listing %s: type=%s records=%d flagged=%d",
            listing_id, payload.listing_type.value, record_count, flagged_records,
        )
        return listing

    def delete_data_listing(self, listing_id: str) -> bool:
        """Delete a data listing. Returns True if deleted."""
        with self._lock:
            if listing_id in self._data_listings:
                del self._data_listings[listing_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Medical Signals
    # ------------------------------------------------------------------

    def list_signals(
        self,
        *,
        trial_id: str | None = None,
        signal_category: SignalCategory | None = None,
        action_required: bool | None = None,
    ) -> list[MedicalSignal]:
        """List medical signals with optional filters."""
        with self._lock:
            result = list(self._signals.values())

        if trial_id is not None:
            result = [s for s in result if s.trial_id == trial_id]
        if signal_category is not None:
            result = [s for s in result if s.signal_category == signal_category]
        if action_required is not None:
            result = [s for s in result if s.action_required == action_required]

        return sorted(result, key=lambda s: s.risk_ratio, reverse=True)

    def get_signal(self, signal_id: str) -> MedicalSignal | None:
        """Get a single medical signal by ID."""
        with self._lock:
            return self._signals.get(signal_id)

    def create_signal(self, payload: MedicalSignalCreate) -> MedicalSignal:
        """Create a medical signal with auto-calculated risk ratio and p-value."""
        signal_id = f"SIG-{uuid4().hex[:8].upper()}"

        # Calculate risk ratio
        if payload.expected_count > 0:
            risk_ratio = round(payload.observed_count / payload.expected_count, 2)
        else:
            risk_ratio = float(payload.observed_count) if payload.observed_count > 0 else 0.0

        # Calculate approximate p-value using Poisson model
        p_value = self._calculate_p_value(payload.observed_count, payload.expected_count)

        # Determine if action is required (risk ratio > 1.5 and p < 0.05)
        action_required = risk_ratio > 1.5 and p_value < 0.05

        signal = MedicalSignal(
            id=signal_id,
            trial_id=payload.trial_id,
            signal_category=payload.signal_category,
            term=payload.term,
            observed_count=payload.observed_count,
            expected_count=payload.expected_count,
            patients_affected=payload.patients_affected,
            risk_ratio=risk_ratio,
            p_value=p_value,
            assessment=payload.assessment,
            action_required=action_required,
        )
        with self._lock:
            self._signals[signal_id] = signal
        logger.info(
            "Created signal %s: term='%s' RR=%.2f p=%.4f action_required=%s",
            signal_id, payload.term, risk_ratio, p_value, action_required,
        )
        return signal

    def update_signal(self, signal_id: str, payload: MedicalSignalUpdate) -> MedicalSignal | None:
        """Update a medical signal."""
        with self._lock:
            existing = self._signals.get(signal_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MedicalSignal(**data)
            self._signals[signal_id] = updated
        return updated

    def delete_signal(self, signal_id: str) -> bool:
        """Delete a signal. Returns True if deleted."""
        with self._lock:
            if signal_id in self._signals:
                del self._signals[signal_id]
                return True
            return False

    def detect_signals(self, trial_id: str) -> list[MedicalSignal]:
        """Run signal detection for a trial based on existing data.

        Returns signals where risk ratio > 1.5 and p-value < 0.05.
        """
        with self._lock:
            signals = [
                s for s in self._signals.values()
                if s.trial_id == trial_id and s.risk_ratio > 1.5 and s.p_value < 0.05
            ]
        return sorted(signals, key=lambda s: s.risk_ratio, reverse=True)

    @staticmethod
    def _calculate_p_value(observed: int, expected: int) -> float:
        """Calculate approximate p-value using Poisson distribution.

        Uses a simplified calculation for demonstration.
        """
        if expected == 0:
            return 0.001 if observed > 0 else 1.0

        # Simplified Poisson-based p-value approximation
        if observed <= expected:
            return min(1.0, max(0.0, 1.0 - (expected - observed) / max(1, expected)))

        # For observed > expected, use normal approximation to Poisson
        z = (observed - expected) / max(1.0, math.sqrt(expected))
        # Simplified one-sided p-value from z-score
        if z <= 0:
            return 1.0
        elif z < 1.0:
            return round(0.5 - z * 0.2, 4)
        elif z < 2.0:
            return round(0.15 - (z - 1.0) * 0.1, 4)
        elif z < 3.0:
            return round(0.05 - (z - 2.0) * 0.04, 4)
        else:
            return 0.001

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> MedicalReviewMetrics:
        """Compute aggregated medical review metrics."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=OVERDUE_THRESHOLD_HOURS)

        with self._lock:
            tasks = list(self._review_tasks.values())
            coding_tasks = list(self._coding_tasks.values())
            signals = list(self._signals.values())

        # Tasks by status
        tasks_by_status: dict[str, int] = {}
        completed_times: list[float] = []
        for task in tasks:
            key = task.status.value
            tasks_by_status[key] = tasks_by_status.get(key, 0) + 1
            if task.completed_date and task.created_date:
                delta = (task.completed_date - task.created_date).total_seconds() / 3600
                completed_times.append(delta)

        avg_review_time = round(sum(completed_times) / max(1, len(completed_times)), 1)

        # Coding metrics
        total_coding = len(coding_tasks)
        auto_coded = sum(1 for c in coding_tasks if c.auto_coded)
        verified = sum(1 for c in coding_tasks if c.status == CodingStatus.VERIFIED)
        auto_coding_rate = round(auto_coded / max(1, total_coding), 3)
        coding_accuracy_rate = round(verified / max(1, total_coding), 3)

        # Signals
        open_signals = sum(1 for s in signals if s.action_required)

        # Overdue reviews
        overdue_reviews = sum(
            1 for t in tasks
            if t.status == ReviewStatus.PENDING and t.created_date < cutoff
        )

        return MedicalReviewMetrics(
            total_tasks=len(tasks),
            tasks_by_status=tasks_by_status,
            avg_review_time_hours=avg_review_time,
            coding_accuracy_rate=coding_accuracy_rate,
            auto_coding_rate=auto_coding_rate,
            open_signals=open_signals,
            overdue_reviews=overdue_reviews,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: MedicalReviewService | None = None
_instance_lock = threading.Lock()


def get_medical_review_service() -> MedicalReviewService:
    """Return the singleton MedicalReviewService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = MedicalReviewService()
    return _instance


def reset_medical_review_service() -> MedicalReviewService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = MedicalReviewService()
    return _instance
