"""Clinical Event Adjudication Service (CEA-ADJ).

Manages clinical event adjudication operations: event submissions, adjudicator
assignments, adjudication decision records, consensus reviews, and adjudication
metrics.

Usage:
    from app.services.clinical_event_adjudication_service import (
        get_clinical_event_adjudication_service,
    )

    svc = get_clinical_event_adjudication_service()
    submissions = svc.list_event_submissions()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.clinical_event_adjudication import (
    AdjudicationDecision,
    AdjudicationDecisionRecord,
    AdjudicationDecisionRecordCreate,
    AdjudicationDecisionRecordUpdate,
    AdjudicatorAssignment,
    AdjudicatorAssignmentCreate,
    AdjudicatorAssignmentUpdate,
    AdjudicatorRole,
    ClinicalEventAdjudicationMetrics,
    ConsensusOutcome,
    ConsensusReview,
    ConsensusReviewCreate,
    ConsensusReviewUpdate,
    EventCategory,
    EventStatus,
    EventSubmission,
    EventSubmissionCreate,
    EventSubmissionUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ClinicalEventAdjudicationService:
    """In-memory Clinical Event Adjudication engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._event_submissions: dict[str, EventSubmission] = {}
        self._adjudicator_assignments: dict[str, AdjudicatorAssignment] = {}
        self._adjudication_decision_records: dict[str, AdjudicationDecisionRecord] = {}
        self._consensus_reviews: dict[str, ConsensusReview] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic clinical event adjudication data."""
        now = datetime.now(timezone.utc)

        # --- 12 Event Submissions ---
        submissions_data = [
            {
                "id": "EVT-001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-NY-001",
                "event_category": EventCategory.CARDIOVASCULAR,
                "event_status": EventStatus.ADJUDICATED,
                "event_date": now - timedelta(days=90),
                "event_description": "Subject experienced acute myocardial infarction confirmed by troponin elevation and ECG changes.",
                "source_documents_count": 5,
                "submitted_by": "Dr. Sarah Mitchell",
                "submission_date": now - timedelta(days=88),
                "blinded": True,
                "priority_review": True,
                "target_turnaround_days": 7,
                "notes": "Urgent review requested due to MACE endpoint relevance.",
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "EVT-002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E002",
                "site_id": "SITE-NY-001",
                "event_category": EventCategory.NEUROLOGICAL,
                "event_status": EventStatus.ADJUDICATED,
                "event_date": now - timedelta(days=75),
                "event_description": "Transient ischemic attack reported with temporary speech impairment and right-sided weakness.",
                "source_documents_count": 4,
                "submitted_by": "Dr. Sarah Mitchell",
                "submission_date": now - timedelta(days=73),
                "blinded": True,
                "priority_review": True,
                "target_turnaround_days": 7,
                "notes": "Neurology consult notes included. MRI brain performed.",
                "created_at": now - timedelta(days=73),
            },
            {
                "id": "EVT-003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E003",
                "site_id": "SITE-LA-001",
                "event_category": EventCategory.HEPATIC,
                "event_status": EventStatus.UNDER_REVIEW,
                "event_date": now - timedelta(days=45),
                "event_description": "Elevated ALT and AST levels >5x ULN detected at Week 12 visit. No clinical symptoms.",
                "source_documents_count": 3,
                "submitted_by": "Dr. James Park",
                "submission_date": now - timedelta(days=43),
                "blinded": True,
                "priority_review": False,
                "target_turnaround_days": 14,
                "notes": "Hepatology review pending. Hy's Law assessment in progress.",
                "created_at": now - timedelta(days=43),
            },
            {
                "id": "EVT-004",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-NY-001",
                "event_category": EventCategory.DEATH,
                "event_status": EventStatus.FINAL,
                "event_date": now - timedelta(days=30),
                "event_description": "Subject death due to cardiac arrest. Autopsy requested and pending.",
                "source_documents_count": 8,
                "submitted_by": "Dr. Sarah Mitchell",
                "submission_date": now - timedelta(days=29),
                "blinded": False,
                "priority_review": True,
                "target_turnaround_days": 3,
                "notes": "Death event requires expedited review per protocol. Unblinded for safety reporting.",
                "created_at": now - timedelta(days=29),
            },
            {
                "id": "EVT-005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-CHI-001",
                "event_category": EventCategory.OTHER_SERIOUS,
                "event_status": EventStatus.ADJUDICATED,
                "event_date": now - timedelta(days=80),
                "event_description": "Severe anaphylactic reaction requiring epinephrine administration and ER visit.",
                "source_documents_count": 6,
                "submitted_by": "Dr. Karen Liu",
                "submission_date": now - timedelta(days=78),
                "blinded": True,
                "priority_review": True,
                "target_turnaround_days": 7,
                "notes": "Allergology consult obtained. Subject recovered fully within 24 hours.",
                "created_at": now - timedelta(days=78),
            },
            {
                "id": "EVT-006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D002",
                "site_id": "SITE-CHI-001",
                "event_category": EventCategory.CARDIOVASCULAR,
                "event_status": EventStatus.SUBMITTED,
                "event_date": now - timedelta(days=20),
                "event_description": "New onset atrial fibrillation detected on routine ECG monitoring at Week 8.",
                "source_documents_count": 2,
                "submitted_by": "Dr. Michael Torres",
                "submission_date": now - timedelta(days=18),
                "blinded": True,
                "priority_review": False,
                "target_turnaround_days": 14,
                "notes": "Awaiting cardiology consult and 24-hour Holter results.",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "EVT-007",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D003",
                "site_id": "SITE-BOS-001",
                "event_category": EventCategory.RENAL,
                "event_status": EventStatus.UNDER_REVIEW,
                "event_date": now - timedelta(days=55),
                "event_description": "Acute kidney injury with creatinine doubling from baseline. Dialysis not required.",
                "source_documents_count": 4,
                "submitted_by": "Dr. Rachel Green",
                "submission_date": now - timedelta(days=53),
                "blinded": True,
                "priority_review": True,
                "target_turnaround_days": 7,
                "notes": "Nephrology consult requested. Urine sediment analysis pending.",
                "created_at": now - timedelta(days=53),
            },
            {
                "id": "EVT-008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-CHI-001",
                "event_category": EventCategory.NEUROLOGICAL,
                "event_status": EventStatus.APPEALED,
                "event_date": now - timedelta(days=40),
                "event_description": "Seizure episode reported during study visit. EEG performed showing focal temporal lobe activity.",
                "source_documents_count": 5,
                "submitted_by": "Dr. Karen Liu",
                "submission_date": now - timedelta(days=38),
                "blinded": True,
                "priority_review": False,
                "target_turnaround_days": 14,
                "notes": "Initial adjudication classified as non-event. Investigator appeals with additional EEG data.",
                "created_at": now - timedelta(days=38),
            },
            {
                "id": "EVT-009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-HOU-001",
                "event_category": EventCategory.HEPATIC,
                "event_status": EventStatus.ADJUDICATED,
                "event_date": now - timedelta(days=70),
                "event_description": "Drug-induced liver injury suspected. Bilirubin >3x ULN with ALT >10x ULN.",
                "source_documents_count": 7,
                "submitted_by": "Dr. David Park",
                "submission_date": now - timedelta(days=68),
                "blinded": True,
                "priority_review": True,
                "target_turnaround_days": 5,
                "notes": "Hy's Law criteria met. Causality assessment completed. Drug discontinued.",
                "created_at": now - timedelta(days=68),
            },
            {
                "id": "EVT-010",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L002",
                "site_id": "SITE-HOU-001",
                "event_category": EventCategory.CARDIOVASCULAR,
                "event_status": EventStatus.FINAL,
                "event_date": now - timedelta(days=50),
                "event_description": "Pulmonary embolism confirmed by CT pulmonary angiogram. Anticoagulation initiated.",
                "source_documents_count": 6,
                "submitted_by": "Dr. Angela Martinez",
                "submission_date": now - timedelta(days=48),
                "blinded": True,
                "priority_review": True,
                "target_turnaround_days": 7,
                "notes": "VTE endpoint confirmed. Subject stable on treatment.",
                "created_at": now - timedelta(days=48),
            },
            {
                "id": "EVT-011",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L003",
                "site_id": "SITE-SEA-001",
                "event_category": EventCategory.RENAL,
                "event_status": EventStatus.WITHDRAWN,
                "event_date": now - timedelta(days=35),
                "event_description": "Proteinuria detected on routine urinalysis. Initially submitted as renal event.",
                "source_documents_count": 2,
                "submitted_by": "Dr. Sarah Kim",
                "submission_date": now - timedelta(days=33),
                "blinded": True,
                "priority_review": False,
                "target_turnaround_days": 14,
                "notes": "Withdrawn by investigator after repeat testing showed normal results. Considered lab artifact.",
                "created_at": now - timedelta(days=33),
            },
            {
                "id": "EVT-012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-HOU-001",
                "event_category": EventCategory.OTHER_SERIOUS,
                "event_status": EventStatus.SUBMITTED,
                "event_date": now - timedelta(days=10),
                "event_description": "Immune-related pneumonitis Grade 3 requiring hospitalization and IV steroids.",
                "source_documents_count": 3,
                "submitted_by": "Dr. David Park",
                "submission_date": now - timedelta(days=8),
                "blinded": True,
                "priority_review": True,
                "target_turnaround_days": 7,
                "notes": "Chest CT and pulmonology consult submitted. Pending adjudication.",
                "created_at": now - timedelta(days=8),
            },
        ]

        for s in submissions_data:
            self._event_submissions[s["id"]] = EventSubmission(**s)

        # --- 12 Adjudicator Assignments ---
        assignments_data = [
            {
                "id": "AAG-001",
                "trial_id": EYLEA_TRIAL,
                "event_submission_id": "EVT-001",
                "adjudicator_name": "Dr. Robert Chen",
                "adjudicator_role": AdjudicatorRole.PRIMARY_REVIEWER,
                "specialty": "Cardiology",
                "assigned_date": now - timedelta(days=87),
                "due_date": now - timedelta(days=80),
                "completed_date": now - timedelta(days=82),
                "conflict_of_interest_declared": False,
                "conflict_details": None,
                "review_time_hours": 4.5,
                "is_active": True,
                "notes": "Primary cardiology review of MI event.",
                "created_at": now - timedelta(days=87),
            },
            {
                "id": "AAG-002",
                "trial_id": EYLEA_TRIAL,
                "event_submission_id": "EVT-001",
                "adjudicator_name": "Dr. Lisa Wang",
                "adjudicator_role": AdjudicatorRole.SECONDARY_REVIEWER,
                "specialty": "Cardiology",
                "assigned_date": now - timedelta(days=87),
                "due_date": now - timedelta(days=80),
                "completed_date": now - timedelta(days=81),
                "conflict_of_interest_declared": False,
                "conflict_details": None,
                "review_time_hours": 3.0,
                "is_active": True,
                "notes": "Secondary review for MI confirmation.",
                "created_at": now - timedelta(days=87),
            },
            {
                "id": "AAG-003",
                "trial_id": EYLEA_TRIAL,
                "event_submission_id": "EVT-002",
                "adjudicator_name": "Dr. Amanda Foster",
                "adjudicator_role": AdjudicatorRole.PRIMARY_REVIEWER,
                "specialty": "Neurology",
                "assigned_date": now - timedelta(days=72),
                "due_date": now - timedelta(days=65),
                "completed_date": now - timedelta(days=66),
                "conflict_of_interest_declared": False,
                "conflict_details": None,
                "review_time_hours": 5.0,
                "is_active": True,
                "notes": "Neurology specialist review of TIA event.",
                "created_at": now - timedelta(days=72),
            },
            {
                "id": "AAG-004",
                "trial_id": EYLEA_TRIAL,
                "event_submission_id": "EVT-004",
                "adjudicator_name": "Dr. Robert Chen",
                "adjudicator_role": AdjudicatorRole.CHAIR,
                "specialty": "Cardiology",
                "assigned_date": now - timedelta(days=28),
                "due_date": now - timedelta(days=25),
                "completed_date": now - timedelta(days=26),
                "conflict_of_interest_declared": False,
                "conflict_details": None,
                "review_time_hours": 6.0,
                "is_active": True,
                "notes": "Chair-led review of death event. Expedited timeline.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "AAG-005",
                "trial_id": DUPIXENT_TRIAL,
                "event_submission_id": "EVT-005",
                "adjudicator_name": "Dr. Patricia Novak",
                "adjudicator_role": AdjudicatorRole.PRIMARY_REVIEWER,
                "specialty": "Allergology/Immunology",
                "assigned_date": now - timedelta(days=77),
                "due_date": now - timedelta(days=70),
                "completed_date": now - timedelta(days=71),
                "conflict_of_interest_declared": True,
                "conflict_details": "Previously consulted for sponsor on unrelated compound. Approved by committee.",
                "review_time_hours": 3.5,
                "is_active": True,
                "notes": "Reviewed anaphylaxis event with declared COI.",
                "created_at": now - timedelta(days=77),
            },
            {
                "id": "AAG-006",
                "trial_id": DUPIXENT_TRIAL,
                "event_submission_id": "EVT-005",
                "adjudicator_name": "Dr. James Harrison",
                "adjudicator_role": AdjudicatorRole.SECONDARY_REVIEWER,
                "specialty": "Emergency Medicine",
                "assigned_date": now - timedelta(days=77),
                "due_date": now - timedelta(days=70),
                "completed_date": now - timedelta(days=72),
                "conflict_of_interest_declared": False,
                "conflict_details": None,
                "review_time_hours": 2.5,
                "is_active": True,
                "notes": "EM perspective on anaphylaxis management and classification.",
                "created_at": now - timedelta(days=77),
            },
            {
                "id": "AAG-007",
                "trial_id": DUPIXENT_TRIAL,
                "event_submission_id": "EVT-007",
                "adjudicator_name": "Dr. Kevin Wu",
                "adjudicator_role": AdjudicatorRole.SPECIALIST,
                "specialty": "Nephrology",
                "assigned_date": now - timedelta(days=52),
                "due_date": now - timedelta(days=45),
                "completed_date": None,
                "conflict_of_interest_declared": False,
                "conflict_details": None,
                "review_time_hours": 0.0,
                "is_active": True,
                "notes": "Nephrology specialist assigned for AKI review. Review in progress.",
                "created_at": now - timedelta(days=52),
            },
            {
                "id": "AAG-008",
                "trial_id": DUPIXENT_TRIAL,
                "event_submission_id": "EVT-008",
                "adjudicator_name": "Dr. Amanda Foster",
                "adjudicator_role": AdjudicatorRole.TIE_BREAKER,
                "specialty": "Neurology",
                "assigned_date": now - timedelta(days=30),
                "due_date": now - timedelta(days=23),
                "completed_date": None,
                "conflict_of_interest_declared": False,
                "conflict_details": None,
                "review_time_hours": 0.0,
                "is_active": True,
                "notes": "Tie-breaker for appealed seizure event. Split decision from initial reviewers.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "AAG-009",
                "trial_id": LIBTAYO_TRIAL,
                "event_submission_id": "EVT-009",
                "adjudicator_name": "Dr. Helen Zhang",
                "adjudicator_role": AdjudicatorRole.PRIMARY_REVIEWER,
                "specialty": "Hepatology",
                "assigned_date": now - timedelta(days=67),
                "due_date": now - timedelta(days=62),
                "completed_date": now - timedelta(days=63),
                "conflict_of_interest_declared": False,
                "conflict_details": None,
                "review_time_hours": 5.5,
                "is_active": True,
                "notes": "Hepatology review of suspected DILI. Hy's Law assessment completed.",
                "created_at": now - timedelta(days=67),
            },
            {
                "id": "AAG-010",
                "trial_id": LIBTAYO_TRIAL,
                "event_submission_id": "EVT-010",
                "adjudicator_name": "Dr. Robert Chen",
                "adjudicator_role": AdjudicatorRole.PRIMARY_REVIEWER,
                "specialty": "Cardiology",
                "assigned_date": now - timedelta(days=47),
                "due_date": now - timedelta(days=40),
                "completed_date": now - timedelta(days=41),
                "conflict_of_interest_declared": False,
                "conflict_details": None,
                "review_time_hours": 4.0,
                "is_active": True,
                "notes": "Reviewed PE event. CT-PA imaging confirmed diagnosis.",
                "created_at": now - timedelta(days=47),
            },
            {
                "id": "AAG-011",
                "trial_id": LIBTAYO_TRIAL,
                "event_submission_id": "EVT-010",
                "adjudicator_name": "Dr. Lisa Wang",
                "adjudicator_role": AdjudicatorRole.SECONDARY_REVIEWER,
                "specialty": "Pulmonology",
                "assigned_date": now - timedelta(days=47),
                "due_date": now - timedelta(days=40),
                "completed_date": now - timedelta(days=42),
                "conflict_of_interest_declared": False,
                "conflict_details": None,
                "review_time_hours": 3.5,
                "is_active": True,
                "notes": "Pulmonology perspective on PE classification and severity.",
                "created_at": now - timedelta(days=47),
            },
            {
                "id": "AAG-012",
                "trial_id": LIBTAYO_TRIAL,
                "event_submission_id": "EVT-012",
                "adjudicator_name": "Dr. Kevin Wu",
                "adjudicator_role": AdjudicatorRole.ALTERNATE,
                "specialty": "Pulmonology",
                "assigned_date": now - timedelta(days=7),
                "due_date": now + timedelta(days=7),
                "completed_date": None,
                "conflict_of_interest_declared": False,
                "conflict_details": None,
                "review_time_hours": 0.0,
                "is_active": True,
                "notes": "Alternate reviewer for pneumonitis event. Primary reviewer unavailable.",
                "created_at": now - timedelta(days=7),
            },
        ]

        for a in assignments_data:
            self._adjudicator_assignments[a["id"]] = AdjudicatorAssignment(**a)

        # --- 12 Adjudication Decision Records ---
        decisions_data = [
            {
                "id": "ADR-001",
                "trial_id": EYLEA_TRIAL,
                "event_submission_id": "EVT-001",
                "assignment_id": "AAG-001",
                "adjudication_decision": AdjudicationDecision.CONFIRMED,
                "original_classification": "Acute Myocardial Infarction - Type 1",
                "adjudicated_classification": "Acute Myocardial Infarction - Type 1",
                "confidence_level": 95.0,
                "rationale": "Troponin rise/fall pattern with ischemic symptoms and ST-elevation on ECG consistent with Type 1 MI per Universal Definition.",
                "additional_data_requested": False,
                "decision_date": now - timedelta(days=82),
                "notes": "Clear-cut MI. No additional data needed.",
                "created_at": now - timedelta(days=82),
            },
            {
                "id": "ADR-002",
                "trial_id": EYLEA_TRIAL,
                "event_submission_id": "EVT-001",
                "assignment_id": "AAG-002",
                "adjudication_decision": AdjudicationDecision.CONFIRMED,
                "original_classification": "Acute Myocardial Infarction - Type 1",
                "adjudicated_classification": "Acute Myocardial Infarction - Type 1",
                "confidence_level": 92.0,
                "rationale": "Agrees with primary reviewer. ECG findings and biomarker pattern confirm Type 1 MI classification.",
                "additional_data_requested": False,
                "decision_date": now - timedelta(days=81),
                "notes": "Concordant with primary review.",
                "created_at": now - timedelta(days=81),
            },
            {
                "id": "ADR-003",
                "trial_id": EYLEA_TRIAL,
                "event_submission_id": "EVT-002",
                "assignment_id": "AAG-003",
                "adjudication_decision": AdjudicationDecision.RECLASSIFIED,
                "original_classification": "Transient Ischemic Attack",
                "adjudicated_classification": "Minor Ischemic Stroke",
                "confidence_level": 78.0,
                "rationale": "MRI shows small area of restricted diffusion. Symptoms >24h duration. Reclassified from TIA to minor ischemic stroke per TOAST criteria.",
                "additional_data_requested": True,
                "decision_date": now - timedelta(days=66),
                "notes": "Requested follow-up MRI at 30 days for confirmation.",
                "created_at": now - timedelta(days=66),
            },
            {
                "id": "ADR-004",
                "trial_id": EYLEA_TRIAL,
                "event_submission_id": "EVT-004",
                "assignment_id": "AAG-004",
                "adjudication_decision": AdjudicationDecision.CONFIRMED,
                "original_classification": "Cardiovascular Death",
                "adjudicated_classification": "Cardiovascular Death - Sudden Cardiac Death",
                "confidence_level": 88.0,
                "rationale": "Death due to cardiac arrest with preceding MI history. Classified as sudden cardiac death per ACC/AHA endpoint definitions.",
                "additional_data_requested": True,
                "decision_date": now - timedelta(days=26),
                "notes": "Autopsy results pending. May refine classification.",
                "created_at": now - timedelta(days=26),
            },
            {
                "id": "ADR-005",
                "trial_id": DUPIXENT_TRIAL,
                "event_submission_id": "EVT-005",
                "assignment_id": "AAG-005",
                "adjudication_decision": AdjudicationDecision.CONFIRMED,
                "original_classification": "Anaphylaxis - Grade 3",
                "adjudicated_classification": "Anaphylaxis - Grade 3",
                "confidence_level": 97.0,
                "rationale": "Meets Sampson criteria for anaphylaxis. Multi-system involvement with hypotension requiring epinephrine.",
                "additional_data_requested": False,
                "decision_date": now - timedelta(days=71),
                "notes": "Clear anaphylaxis. IgE-mediated mechanism suspected.",
                "created_at": now - timedelta(days=71),
            },
            {
                "id": "ADR-006",
                "trial_id": DUPIXENT_TRIAL,
                "event_submission_id": "EVT-005",
                "assignment_id": "AAG-006",
                "adjudication_decision": AdjudicationDecision.CONFIRMED,
                "original_classification": "Anaphylaxis - Grade 3",
                "adjudicated_classification": "Anaphylaxis - Grade 3",
                "confidence_level": 94.0,
                "rationale": "Acute onset with skin/mucosal and respiratory involvement. Epinephrine response confirms anaphylaxis.",
                "additional_data_requested": False,
                "decision_date": now - timedelta(days=72),
                "notes": "Concordant review. Time to epinephrine documented.",
                "created_at": now - timedelta(days=72),
            },
            {
                "id": "ADR-007",
                "trial_id": DUPIXENT_TRIAL,
                "event_submission_id": "EVT-008",
                "assignment_id": "AAG-008",
                "adjudication_decision": AdjudicationDecision.SPLIT_DECISION,
                "original_classification": "New-Onset Seizure",
                "adjudicated_classification": None,
                "confidence_level": 55.0,
                "rationale": "EEG shows focal temporal activity but clinical presentation ambiguous. One reviewer classified as seizure, other as non-epileptic event. Appeal review in progress.",
                "additional_data_requested": True,
                "decision_date": now - timedelta(days=25),
                "notes": "Tie-breaker review pending. Video EEG requested.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "ADR-008",
                "trial_id": DUPIXENT_TRIAL,
                "event_submission_id": "EVT-007",
                "assignment_id": "AAG-007",
                "adjudication_decision": AdjudicationDecision.DEFERRED,
                "original_classification": "Acute Kidney Injury - Stage 2",
                "adjudicated_classification": None,
                "confidence_level": 0.0,
                "rationale": "Insufficient data to determine etiology. Urine sediment and renal ultrasound results needed for KDIGO staging.",
                "additional_data_requested": True,
                "decision_date": now - timedelta(days=48),
                "notes": "Decision deferred pending additional diagnostic data.",
                "created_at": now - timedelta(days=48),
            },
            {
                "id": "ADR-009",
                "trial_id": LIBTAYO_TRIAL,
                "event_submission_id": "EVT-009",
                "assignment_id": "AAG-009",
                "adjudication_decision": AdjudicationDecision.CONFIRMED,
                "original_classification": "Drug-Induced Liver Injury",
                "adjudicated_classification": "Drug-Induced Liver Injury - Hepatocellular Pattern",
                "confidence_level": 91.0,
                "rationale": "RUCAM score 8 (probable DILI). Hepatocellular pattern with R-value >5. Hy's Law criteria met.",
                "additional_data_requested": False,
                "decision_date": now - timedelta(days=63),
                "notes": "DILI confirmed. Drug permanently discontinued.",
                "created_at": now - timedelta(days=63),
            },
            {
                "id": "ADR-010",
                "trial_id": LIBTAYO_TRIAL,
                "event_submission_id": "EVT-010",
                "assignment_id": "AAG-010",
                "adjudication_decision": AdjudicationDecision.CONFIRMED,
                "original_classification": "Pulmonary Embolism",
                "adjudicated_classification": "Pulmonary Embolism - Submassive",
                "confidence_level": 96.0,
                "rationale": "CT-PA confirms bilateral PE. RV strain on echo without hemodynamic instability. Classified as submassive per AHA guidelines.",
                "additional_data_requested": False,
                "decision_date": now - timedelta(days=41),
                "notes": "VTE endpoint confirmed. Submassive classification.",
                "created_at": now - timedelta(days=41),
            },
            {
                "id": "ADR-011",
                "trial_id": LIBTAYO_TRIAL,
                "event_submission_id": "EVT-010",
                "assignment_id": "AAG-011",
                "adjudication_decision": AdjudicationDecision.CONFIRMED,
                "original_classification": "Pulmonary Embolism",
                "adjudicated_classification": "Pulmonary Embolism - Submassive",
                "confidence_level": 93.0,
                "rationale": "Agrees with primary. CT-PA imaging definitive. RV dilation without shock classifies as submassive.",
                "additional_data_requested": False,
                "decision_date": now - timedelta(days=42),
                "notes": "Concordant with primary reviewer.",
                "created_at": now - timedelta(days=42),
            },
            {
                "id": "ADR-012",
                "trial_id": LIBTAYO_TRIAL,
                "event_submission_id": "EVT-011",
                "assignment_id": "AAG-009",
                "adjudication_decision": AdjudicationDecision.NOT_AN_EVENT,
                "original_classification": "Renal Event - Proteinuria",
                "adjudicated_classification": None,
                "confidence_level": 85.0,
                "rationale": "Repeat urinalysis normal. Initial finding consistent with laboratory artifact or transient benign proteinuria. Does not meet protocol-defined renal endpoint.",
                "additional_data_requested": False,
                "decision_date": now - timedelta(days=28),
                "notes": "Event withdrawn by investigator concurrent with not-an-event determination.",
                "created_at": now - timedelta(days=28),
            },
        ]

        for d in decisions_data:
            self._adjudication_decision_records[d["id"]] = AdjudicationDecisionRecord(**d)

        # --- 12 Consensus Reviews ---
        consensus_data = [
            {
                "id": "CNS-001",
                "trial_id": EYLEA_TRIAL,
                "event_submission_id": "EVT-001",
                "consensus_outcome": ConsensusOutcome.UNANIMOUS,
                "reviewers_count": 2,
                "agreeing_count": 2,
                "disagreeing_count": 0,
                "final_classification": "Acute Myocardial Infarction - Type 1",
                "meeting_date": now - timedelta(days=80),
                "chair_name": "Dr. Robert Chen",
                "discussion_summary": "Both reviewers unanimously confirmed Type 1 MI. No discussion needed.",
                "escalation_reason": None,
                "finalized_date": now - timedelta(days=80),
                "notes": "Unanimous consensus. Event confirmed as primary MACE endpoint.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "CNS-002",
                "trial_id": EYLEA_TRIAL,
                "event_submission_id": "EVT-002",
                "consensus_outcome": ConsensusOutcome.MAJORITY,
                "reviewers_count": 3,
                "agreeing_count": 2,
                "disagreeing_count": 1,
                "final_classification": "Minor Ischemic Stroke",
                "meeting_date": now - timedelta(days=64),
                "chair_name": "Dr. Robert Chen",
                "discussion_summary": "Majority agreed on reclassification from TIA to minor stroke based on MRI findings. One dissent argued symptoms duration was borderline.",
                "escalation_reason": None,
                "finalized_date": now - timedelta(days=64),
                "notes": "Majority consensus with documented dissenting opinion.",
                "created_at": now - timedelta(days=64),
            },
            {
                "id": "CNS-003",
                "trial_id": EYLEA_TRIAL,
                "event_submission_id": "EVT-003",
                "consensus_outcome": ConsensusOutcome.PENDING,
                "reviewers_count": 2,
                "agreeing_count": 0,
                "disagreeing_count": 0,
                "final_classification": None,
                "meeting_date": None,
                "chair_name": "Dr. Robert Chen",
                "discussion_summary": None,
                "escalation_reason": None,
                "finalized_date": None,
                "notes": "Awaiting completion of adjudicator reviews before consensus meeting.",
                "created_at": now - timedelta(days=42),
            },
            {
                "id": "CNS-004",
                "trial_id": EYLEA_TRIAL,
                "event_submission_id": "EVT-004",
                "consensus_outcome": ConsensusOutcome.UNANIMOUS,
                "reviewers_count": 3,
                "agreeing_count": 3,
                "disagreeing_count": 0,
                "final_classification": "Cardiovascular Death - Sudden Cardiac Death",
                "meeting_date": now - timedelta(days=25),
                "chair_name": "Dr. Robert Chen",
                "discussion_summary": "All reviewers agreed on cardiovascular death classification. Autopsy pending but clinical evidence sufficient.",
                "escalation_reason": None,
                "finalized_date": now - timedelta(days=25),
                "notes": "Expedited consensus for death event. Unanimous agreement.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "CNS-005",
                "trial_id": DUPIXENT_TRIAL,
                "event_submission_id": "EVT-005",
                "consensus_outcome": ConsensusOutcome.UNANIMOUS,
                "reviewers_count": 2,
                "agreeing_count": 2,
                "disagreeing_count": 0,
                "final_classification": "Anaphylaxis - Grade 3",
                "meeting_date": now - timedelta(days=70),
                "chair_name": "Dr. Patricia Novak",
                "discussion_summary": "Both reviewers confirmed anaphylaxis using Sampson criteria. No further discussion required.",
                "escalation_reason": None,
                "finalized_date": now - timedelta(days=70),
                "notes": "Unanimous. Clear anaphylactic reaction.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "CNS-006",
                "trial_id": DUPIXENT_TRIAL,
                "event_submission_id": "EVT-006",
                "consensus_outcome": ConsensusOutcome.PENDING,
                "reviewers_count": 0,
                "agreeing_count": 0,
                "disagreeing_count": 0,
                "final_classification": None,
                "meeting_date": None,
                "chair_name": None,
                "discussion_summary": None,
                "escalation_reason": None,
                "finalized_date": None,
                "notes": "Event recently submitted. Adjudicator assignment pending.",
                "created_at": now - timedelta(days=17),
            },
            {
                "id": "CNS-007",
                "trial_id": DUPIXENT_TRIAL,
                "event_submission_id": "EVT-007",
                "consensus_outcome": ConsensusOutcome.PENDING,
                "reviewers_count": 1,
                "agreeing_count": 0,
                "disagreeing_count": 0,
                "final_classification": None,
                "meeting_date": None,
                "chair_name": "Dr. Kevin Wu",
                "discussion_summary": None,
                "escalation_reason": None,
                "finalized_date": None,
                "notes": "Single reviewer assigned. Decision deferred pending additional data.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "CNS-008",
                "trial_id": DUPIXENT_TRIAL,
                "event_submission_id": "EVT-008",
                "consensus_outcome": ConsensusOutcome.ESCALATED,
                "reviewers_count": 3,
                "agreeing_count": 1,
                "disagreeing_count": 2,
                "final_classification": None,
                "meeting_date": now - timedelta(days=22),
                "chair_name": "Dr. Amanda Foster",
                "discussion_summary": "Initial reviewers split on seizure classification. Tie-breaker assigned but additional EEG data requested before final determination.",
                "escalation_reason": "Split decision between primary and secondary reviewers. Additional diagnostic data needed for tie-breaker review.",
                "finalized_date": None,
                "notes": "Escalated due to split decision and appeal by investigator.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "CNS-009",
                "trial_id": LIBTAYO_TRIAL,
                "event_submission_id": "EVT-009",
                "consensus_outcome": ConsensusOutcome.UNANIMOUS,
                "reviewers_count": 2,
                "agreeing_count": 2,
                "disagreeing_count": 0,
                "final_classification": "Drug-Induced Liver Injury - Hepatocellular Pattern",
                "meeting_date": now - timedelta(days=62),
                "chair_name": "Dr. Helen Zhang",
                "discussion_summary": "Unanimous agreement on DILI classification. RUCAM score and Hy's Law criteria unambiguous.",
                "escalation_reason": None,
                "finalized_date": now - timedelta(days=62),
                "notes": "Confirmed DILI with hepatocellular pattern.",
                "created_at": now - timedelta(days=62),
            },
            {
                "id": "CNS-010",
                "trial_id": LIBTAYO_TRIAL,
                "event_submission_id": "EVT-010",
                "consensus_outcome": ConsensusOutcome.UNANIMOUS,
                "reviewers_count": 2,
                "agreeing_count": 2,
                "disagreeing_count": 0,
                "final_classification": "Pulmonary Embolism - Submassive",
                "meeting_date": now - timedelta(days=40),
                "chair_name": "Dr. Robert Chen",
                "discussion_summary": "Both reviewers confirmed submassive PE. CT-PA findings definitive.",
                "escalation_reason": None,
                "finalized_date": now - timedelta(days=40),
                "notes": "VTE endpoint confirmed unanimously.",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "CNS-011",
                "trial_id": LIBTAYO_TRIAL,
                "event_submission_id": "EVT-011",
                "consensus_outcome": ConsensusOutcome.NO_CONSENSUS,
                "reviewers_count": 1,
                "agreeing_count": 0,
                "disagreeing_count": 0,
                "final_classification": None,
                "meeting_date": now - timedelta(days=28),
                "chair_name": "Dr. Helen Zhang",
                "discussion_summary": "Event withdrawn before full consensus process. Single reviewer determined not-an-event.",
                "escalation_reason": None,
                "finalized_date": now - timedelta(days=28),
                "notes": "Consensus not required. Event withdrawn by investigator.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "CNS-012",
                "trial_id": LIBTAYO_TRIAL,
                "event_submission_id": "EVT-012",
                "consensus_outcome": ConsensusOutcome.PENDING,
                "reviewers_count": 1,
                "agreeing_count": 0,
                "disagreeing_count": 0,
                "final_classification": None,
                "meeting_date": None,
                "chair_name": None,
                "discussion_summary": None,
                "escalation_reason": None,
                "finalized_date": None,
                "notes": "Newly submitted pneumonitis event. Alternate reviewer assigned.",
                "created_at": now - timedelta(days=7),
            },
        ]

        for c in consensus_data:
            self._consensus_reviews[c["id"]] = ConsensusReview(**c)

    # ------------------------------------------------------------------
    # Event Submissions
    # ------------------------------------------------------------------

    def list_event_submissions(
        self,
        *,
        trial_id: str | None = None,
        event_category: EventCategory | None = None,
        event_status: EventStatus | None = None,
    ) -> list[EventSubmission]:
        """List event submissions with optional filters."""
        with self._lock:
            result = list(self._event_submissions.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if event_category is not None:
            result = [r for r in result if r.event_category == event_category]
        if event_status is not None:
            result = [r for r in result if r.event_status == event_status]

        return sorted(result, key=lambda r: r.submission_date, reverse=True)

    def get_event_submission(self, submission_id: str) -> EventSubmission | None:
        """Get a single event submission by ID."""
        with self._lock:
            return self._event_submissions.get(submission_id)

    def create_event_submission(self, payload: EventSubmissionCreate) -> EventSubmission:
        """Create a new event submission."""
        now = datetime.now(timezone.utc)
        submission_id = f"EVT-{uuid4().hex[:8].upper()}"
        record = EventSubmission(
            id=submission_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            site_id=payload.site_id,
            event_category=payload.event_category,
            event_status=EventStatus.SUBMITTED,
            event_date=payload.event_date,
            event_description=payload.event_description,
            source_documents_count=0,
            submitted_by=payload.submitted_by,
            submission_date=payload.submission_date,
            blinded=True,
            priority_review=False,
            target_turnaround_days=14,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._event_submissions[submission_id] = record
        logger.info("Created event submission %s for trial %s", submission_id, payload.trial_id)
        return record

    def update_event_submission(
        self, submission_id: str, payload: EventSubmissionUpdate
    ) -> EventSubmission | None:
        """Update an existing event submission."""
        with self._lock:
            existing = self._event_submissions.get(submission_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = EventSubmission(**data)
            self._event_submissions[submission_id] = updated
        return updated

    def delete_event_submission(self, submission_id: str) -> bool:
        """Delete an event submission. Returns True if deleted."""
        with self._lock:
            if submission_id in self._event_submissions:
                del self._event_submissions[submission_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Adjudicator Assignments
    # ------------------------------------------------------------------

    def list_adjudicator_assignments(
        self,
        *,
        trial_id: str | None = None,
        adjudicator_role: AdjudicatorRole | None = None,
        event_submission_id: str | None = None,
    ) -> list[AdjudicatorAssignment]:
        """List adjudicator assignments with optional filters."""
        with self._lock:
            result = list(self._adjudicator_assignments.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if adjudicator_role is not None:
            result = [r for r in result if r.adjudicator_role == adjudicator_role]
        if event_submission_id is not None:
            result = [r for r in result if r.event_submission_id == event_submission_id]

        return sorted(result, key=lambda r: r.assigned_date, reverse=True)

    def get_adjudicator_assignment(self, assignment_id: str) -> AdjudicatorAssignment | None:
        """Get a single adjudicator assignment by ID."""
        with self._lock:
            return self._adjudicator_assignments.get(assignment_id)

    def create_adjudicator_assignment(
        self, payload: AdjudicatorAssignmentCreate
    ) -> AdjudicatorAssignment:
        """Create a new adjudicator assignment."""
        now = datetime.now(timezone.utc)
        assignment_id = f"AAG-{uuid4().hex[:8].upper()}"
        record = AdjudicatorAssignment(
            id=assignment_id,
            trial_id=payload.trial_id,
            event_submission_id=payload.event_submission_id,
            adjudicator_name=payload.adjudicator_name,
            adjudicator_role=payload.adjudicator_role,
            specialty=payload.specialty,
            assigned_date=payload.assigned_date,
            due_date=payload.due_date,
            completed_date=None,
            conflict_of_interest_declared=False,
            conflict_details=None,
            review_time_hours=0.0,
            is_active=True,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._adjudicator_assignments[assignment_id] = record
        logger.info(
            "Created adjudicator assignment %s for event %s",
            assignment_id,
            payload.event_submission_id,
        )
        return record

    def update_adjudicator_assignment(
        self, assignment_id: str, payload: AdjudicatorAssignmentUpdate
    ) -> AdjudicatorAssignment | None:
        """Update an existing adjudicator assignment."""
        with self._lock:
            existing = self._adjudicator_assignments.get(assignment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AdjudicatorAssignment(**data)
            self._adjudicator_assignments[assignment_id] = updated
        return updated

    def delete_adjudicator_assignment(self, assignment_id: str) -> bool:
        """Delete an adjudicator assignment. Returns True if deleted."""
        with self._lock:
            if assignment_id in self._adjudicator_assignments:
                del self._adjudicator_assignments[assignment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Adjudication Decision Records
    # ------------------------------------------------------------------

    def list_adjudication_decision_records(
        self,
        *,
        trial_id: str | None = None,
        adjudication_decision: AdjudicationDecision | None = None,
        event_submission_id: str | None = None,
    ) -> list[AdjudicationDecisionRecord]:
        """List adjudication decision records with optional filters."""
        with self._lock:
            result = list(self._adjudication_decision_records.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if adjudication_decision is not None:
            result = [r for r in result if r.adjudication_decision == adjudication_decision]
        if event_submission_id is not None:
            result = [r for r in result if r.event_submission_id == event_submission_id]

        return sorted(result, key=lambda r: r.decision_date, reverse=True)

    def get_adjudication_decision_record(
        self, decision_id: str
    ) -> AdjudicationDecisionRecord | None:
        """Get a single adjudication decision record by ID."""
        with self._lock:
            return self._adjudication_decision_records.get(decision_id)

    def create_adjudication_decision_record(
        self, payload: AdjudicationDecisionRecordCreate
    ) -> AdjudicationDecisionRecord:
        """Create a new adjudication decision record."""
        now = datetime.now(timezone.utc)
        decision_id = f"ADR-{uuid4().hex[:8].upper()}"
        record = AdjudicationDecisionRecord(
            id=decision_id,
            trial_id=payload.trial_id,
            event_submission_id=payload.event_submission_id,
            assignment_id=payload.assignment_id,
            adjudication_decision=payload.adjudication_decision,
            original_classification=payload.original_classification,
            adjudicated_classification=None,
            confidence_level=0.0,
            rationale=payload.rationale,
            additional_data_requested=False,
            decision_date=payload.decision_date,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._adjudication_decision_records[decision_id] = record
        logger.info(
            "Created adjudication decision %s for event %s",
            decision_id,
            payload.event_submission_id,
        )
        return record

    def update_adjudication_decision_record(
        self, decision_id: str, payload: AdjudicationDecisionRecordUpdate
    ) -> AdjudicationDecisionRecord | None:
        """Update an existing adjudication decision record."""
        with self._lock:
            existing = self._adjudication_decision_records.get(decision_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AdjudicationDecisionRecord(**data)
            self._adjudication_decision_records[decision_id] = updated
        return updated

    def delete_adjudication_decision_record(self, decision_id: str) -> bool:
        """Delete an adjudication decision record. Returns True if deleted."""
        with self._lock:
            if decision_id in self._adjudication_decision_records:
                del self._adjudication_decision_records[decision_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Consensus Reviews
    # ------------------------------------------------------------------

    def list_consensus_reviews(
        self,
        *,
        trial_id: str | None = None,
        consensus_outcome: ConsensusOutcome | None = None,
        event_submission_id: str | None = None,
    ) -> list[ConsensusReview]:
        """List consensus reviews with optional filters."""
        with self._lock:
            result = list(self._consensus_reviews.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if consensus_outcome is not None:
            result = [r for r in result if r.consensus_outcome == consensus_outcome]
        if event_submission_id is not None:
            result = [r for r in result if r.event_submission_id == event_submission_id]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_consensus_review(self, consensus_id: str) -> ConsensusReview | None:
        """Get a single consensus review by ID."""
        with self._lock:
            return self._consensus_reviews.get(consensus_id)

    def create_consensus_review(self, payload: ConsensusReviewCreate) -> ConsensusReview:
        """Create a new consensus review."""
        now = datetime.now(timezone.utc)
        consensus_id = f"CNS-{uuid4().hex[:8].upper()}"
        record = ConsensusReview(
            id=consensus_id,
            trial_id=payload.trial_id,
            event_submission_id=payload.event_submission_id,
            consensus_outcome=ConsensusOutcome.PENDING,
            reviewers_count=payload.reviewers_count,
            agreeing_count=0,
            disagreeing_count=0,
            final_classification=None,
            meeting_date=None,
            chair_name=payload.chair_name,
            discussion_summary=None,
            escalation_reason=None,
            finalized_date=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._consensus_reviews[consensus_id] = record
        logger.info(
            "Created consensus review %s for event %s",
            consensus_id,
            payload.event_submission_id,
        )
        return record

    def update_consensus_review(
        self, consensus_id: str, payload: ConsensusReviewUpdate
    ) -> ConsensusReview | None:
        """Update an existing consensus review."""
        with self._lock:
            existing = self._consensus_reviews.get(consensus_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ConsensusReview(**data)
            self._consensus_reviews[consensus_id] = updated
        return updated

    def delete_consensus_review(self, consensus_id: str) -> bool:
        """Delete a consensus review. Returns True if deleted."""
        with self._lock:
            if consensus_id in self._consensus_reviews:
                del self._consensus_reviews[consensus_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> ClinicalEventAdjudicationMetrics:
        """Compute aggregated clinical event adjudication metrics."""
        with self._lock:
            submissions = list(self._event_submissions.values())
            assignments = list(self._adjudicator_assignments.values())
            decisions = list(self._adjudication_decision_records.values())
            consensus = list(self._consensus_reviews.values())

        # Submissions by category
        submissions_by_category: dict[str, int] = {}
        for s in submissions:
            key = s.event_category.value
            submissions_by_category[key] = submissions_by_category.get(key, 0) + 1

        # Submissions by status
        submissions_by_status: dict[str, int] = {}
        for s in submissions:
            key = s.event_status.value
            submissions_by_status[key] = submissions_by_status.get(key, 0) + 1

        # Assignments by role
        assignments_by_role: dict[str, int] = {}
        for a in assignments:
            key = a.adjudicator_role.value
            assignments_by_role[key] = assignments_by_role.get(key, 0) + 1

        # Decisions by outcome
        decisions_by_outcome: dict[str, int] = {}
        for d in decisions:
            key = d.adjudication_decision.value
            decisions_by_outcome[key] = decisions_by_outcome.get(key, 0) + 1

        # Average confidence level
        confidence_values = [d.confidence_level for d in decisions if d.confidence_level > 0]
        avg_confidence = round(
            sum(confidence_values) / max(1, len(confidence_values)), 1
        ) if confidence_values else 0.0

        # Consensus by outcome
        consensus_by_outcome: dict[str, int] = {}
        for c in consensus:
            key = c.consensus_outcome.value
            consensus_by_outcome[key] = consensus_by_outcome.get(key, 0) + 1

        # Consensus rate (finalized / total)
        finalized_count = sum(1 for c in consensus if c.finalized_date is not None)
        consensus_rate = round(
            (finalized_count / max(1, len(consensus))) * 100, 1
        )

        return ClinicalEventAdjudicationMetrics(
            total_submissions=len(submissions),
            submissions_by_category=submissions_by_category,
            submissions_by_status=submissions_by_status,
            total_assignments=len(assignments),
            assignments_by_role=assignments_by_role,
            total_decisions=len(decisions),
            decisions_by_outcome=decisions_by_outcome,
            avg_confidence_level=avg_confidence,
            total_consensus_reviews=len(consensus),
            consensus_by_outcome=consensus_by_outcome,
            consensus_rate=consensus_rate,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ClinicalEventAdjudicationService | None = None
_instance_lock = threading.Lock()


def get_clinical_event_adjudication_service() -> ClinicalEventAdjudicationService:
    """Return the singleton ClinicalEventAdjudicationService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ClinicalEventAdjudicationService()
    return _instance


def reset_clinical_event_adjudication_service() -> ClinicalEventAdjudicationService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ClinicalEventAdjudicationService()
    return _instance
