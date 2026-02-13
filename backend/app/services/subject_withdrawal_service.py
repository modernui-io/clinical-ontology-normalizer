"""Subject Withdrawal Service (SWD-MGT).

Manages subject withdrawal operations: withdrawal requests, withdrawal
assessments, follow-up tracking, data disposition records, and withdrawal
metrics.

Usage:
    from app.services.subject_withdrawal_service import (
        get_subject_withdrawal_service,
    )

    svc = get_subject_withdrawal_service()
    requests = svc.list_withdrawal_requests()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.subject_withdrawal import (
    AssessmentType,
    DataDisposition,
    DataDispositionRecord,
    DataDispositionRecordCreate,
    DataDispositionRecordUpdate,
    FollowUpOutcome,
    SubjectWithdrawalMetrics,
    WithdrawalAssessment,
    WithdrawalAssessmentCreate,
    WithdrawalAssessmentUpdate,
    WithdrawalFollowUp,
    WithdrawalFollowUpCreate,
    WithdrawalFollowUpUpdate,
    WithdrawalReason,
    WithdrawalRequest,
    WithdrawalRequestCreate,
    WithdrawalRequestUpdate,
    WithdrawalStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class SubjectWithdrawalService:
    """In-memory Subject Withdrawal engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._withdrawal_requests: dict[str, WithdrawalRequest] = {}
        self._withdrawal_assessments: dict[str, WithdrawalAssessment] = {}
        self._withdrawal_follow_ups: dict[str, WithdrawalFollowUp] = {}
        self._data_disposition_records: dict[str, DataDispositionRecord] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic subject withdrawal data."""
        now = datetime.now(timezone.utc)

        # --- 12 Withdrawal Requests ---
        requests_data = [
            {
                "id": "WDR-001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E001",
                "site_id": "SITE-NY-001",
                "withdrawal_reason": WithdrawalReason.ADVERSE_EVENT,
                "withdrawal_status": WithdrawalStatus.COMPLETED,
                "request_date": now - timedelta(days=90),
                "effective_date": now - timedelta(days=85),
                "last_dose_date": now - timedelta(days=92),
                "last_visit_date": now - timedelta(days=88),
                "initiated_by": "Dr. Sarah Chen",
                "investigator_name": "Dr. Sarah Chen",
                "subject_consents_to_follow_up": True,
                "subject_consents_to_data_use": True,
                "irb_notification_date": now - timedelta(days=87),
                "sponsor_notification_date": now - timedelta(days=86),
                "notes": "Subject experienced Grade 3 ocular inflammation. Withdrawal per investigator decision.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "WDR-002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E002",
                "site_id": "SITE-NY-001",
                "withdrawal_reason": WithdrawalReason.CONSENT_WITHDRAWN,
                "withdrawal_status": WithdrawalStatus.COMPLETED,
                "request_date": now - timedelta(days=75),
                "effective_date": now - timedelta(days=73),
                "last_dose_date": now - timedelta(days=80),
                "last_visit_date": now - timedelta(days=75),
                "initiated_by": "Subject",
                "investigator_name": "Dr. Sarah Chen",
                "subject_consents_to_follow_up": False,
                "subject_consents_to_data_use": True,
                "irb_notification_date": now - timedelta(days=72),
                "sponsor_notification_date": now - timedelta(days=71),
                "notes": "Subject voluntarily withdrew consent citing personal reasons.",
                "created_at": now - timedelta(days=75),
            },
            {
                "id": "WDR-003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E003",
                "site_id": "SITE-LA-001",
                "withdrawal_reason": WithdrawalReason.LOST_TO_FOLLOW_UP,
                "withdrawal_status": WithdrawalStatus.CONFIRMED,
                "request_date": now - timedelta(days=60),
                "effective_date": now - timedelta(days=55),
                "last_dose_date": now - timedelta(days=90),
                "last_visit_date": now - timedelta(days=75),
                "initiated_by": "Study Coordinator",
                "investigator_name": "Dr. Robert Kim",
                "subject_consents_to_follow_up": False,
                "subject_consents_to_data_use": True,
                "irb_notification_date": now - timedelta(days=53),
                "sponsor_notification_date": now - timedelta(days=52),
                "notes": "Subject unreachable after multiple contact attempts over 30 days.",
                "created_at": now - timedelta(days=60),
            },
            {
                "id": "WDR-004",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-E004",
                "site_id": "SITE-LA-001",
                "withdrawal_reason": WithdrawalReason.PROTOCOL_VIOLATION,
                "withdrawal_status": WithdrawalStatus.UNDER_REVIEW,
                "request_date": now - timedelta(days=30),
                "effective_date": None,
                "last_dose_date": now - timedelta(days=35),
                "last_visit_date": now - timedelta(days=30),
                "initiated_by": "Dr. Robert Kim",
                "investigator_name": "Dr. Robert Kim",
                "subject_consents_to_follow_up": True,
                "subject_consents_to_data_use": True,
                "irb_notification_date": None,
                "sponsor_notification_date": now - timedelta(days=28),
                "notes": "Major protocol deviation: subject took prohibited concomitant medication.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "WDR-005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D001",
                "site_id": "SITE-CHI-001",
                "withdrawal_reason": WithdrawalReason.LACK_OF_EFFICACY,
                "withdrawal_status": WithdrawalStatus.COMPLETED,
                "request_date": now - timedelta(days=80),
                "effective_date": now - timedelta(days=77),
                "last_dose_date": now - timedelta(days=84),
                "last_visit_date": now - timedelta(days=80),
                "initiated_by": "Dr. Michael Torres",
                "investigator_name": "Dr. Michael Torres",
                "subject_consents_to_follow_up": True,
                "subject_consents_to_data_use": True,
                "irb_notification_date": now - timedelta(days=76),
                "sponsor_notification_date": now - timedelta(days=75),
                "notes": "No clinical improvement after 12 weeks. Subject requests alternative treatment.",
                "created_at": now - timedelta(days=80),
            },
            {
                "id": "WDR-006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D002",
                "site_id": "SITE-CHI-001",
                "withdrawal_reason": WithdrawalReason.ADVERSE_EVENT,
                "withdrawal_status": WithdrawalStatus.COMPLETED,
                "request_date": now - timedelta(days=65),
                "effective_date": now - timedelta(days=62),
                "last_dose_date": now - timedelta(days=67),
                "last_visit_date": now - timedelta(days=65),
                "initiated_by": "Dr. Michael Torres",
                "investigator_name": "Dr. Michael Torres",
                "subject_consents_to_follow_up": True,
                "subject_consents_to_data_use": True,
                "irb_notification_date": now - timedelta(days=61),
                "sponsor_notification_date": now - timedelta(days=60),
                "notes": "Severe injection site reaction with secondary infection requiring hospitalization.",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "WDR-007",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D003",
                "site_id": "SITE-BOS-001",
                "withdrawal_reason": WithdrawalReason.CONSENT_WITHDRAWN,
                "withdrawal_status": WithdrawalStatus.INITIATED,
                "request_date": now - timedelta(days=10),
                "effective_date": None,
                "last_dose_date": now - timedelta(days=14),
                "last_visit_date": now - timedelta(days=10),
                "initiated_by": "Subject",
                "investigator_name": "Dr. Emily Watson",
                "subject_consents_to_follow_up": False,
                "subject_consents_to_data_use": False,
                "irb_notification_date": None,
                "sponsor_notification_date": None,
                "notes": "Subject withdrew all consent including data use. Requires full data disposition review.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "WDR-008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-D004",
                "site_id": "SITE-BOS-001",
                "withdrawal_reason": WithdrawalReason.INVESTIGATOR_DECISION,
                "withdrawal_status": WithdrawalStatus.PENDING_DOCUMENTATION,
                "request_date": now - timedelta(days=20),
                "effective_date": now - timedelta(days=18),
                "last_dose_date": now - timedelta(days=25),
                "last_visit_date": now - timedelta(days=20),
                "initiated_by": "Dr. Emily Watson",
                "investigator_name": "Dr. Emily Watson",
                "subject_consents_to_follow_up": True,
                "subject_consents_to_data_use": True,
                "irb_notification_date": now - timedelta(days=17),
                "sponsor_notification_date": None,
                "notes": "Investigator decision due to subject non-compliance with visit schedule.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "WDR-009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L001",
                "site_id": "SITE-HOU-001",
                "withdrawal_reason": WithdrawalReason.ADVERSE_EVENT,
                "withdrawal_status": WithdrawalStatus.COMPLETED,
                "request_date": now - timedelta(days=70),
                "effective_date": now - timedelta(days=67),
                "last_dose_date": now - timedelta(days=73),
                "last_visit_date": now - timedelta(days=70),
                "initiated_by": "Dr. Angela Martinez",
                "investigator_name": "Dr. Angela Martinez",
                "subject_consents_to_follow_up": True,
                "subject_consents_to_data_use": True,
                "irb_notification_date": now - timedelta(days=66),
                "sponsor_notification_date": now - timedelta(days=65),
                "notes": "Immune-related hepatitis (Grade 3). Treatment discontinued per protocol.",
                "created_at": now - timedelta(days=70),
            },
            {
                "id": "WDR-010",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L002",
                "site_id": "SITE-HOU-001",
                "withdrawal_reason": WithdrawalReason.LACK_OF_EFFICACY,
                "withdrawal_status": WithdrawalStatus.CONFIRMED,
                "request_date": now - timedelta(days=45),
                "effective_date": now - timedelta(days=42),
                "last_dose_date": now - timedelta(days=49),
                "last_visit_date": now - timedelta(days=45),
                "initiated_by": "Dr. Angela Martinez",
                "investigator_name": "Dr. Angela Martinez",
                "subject_consents_to_follow_up": True,
                "subject_consents_to_data_use": True,
                "irb_notification_date": now - timedelta(days=41),
                "sponsor_notification_date": now - timedelta(days=40),
                "notes": "Disease progression confirmed on imaging. Subject transitioning to alternative therapy.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "WDR-011",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L003",
                "site_id": "SITE-SEA-001",
                "withdrawal_reason": WithdrawalReason.CONSENT_WITHDRAWN,
                "withdrawal_status": WithdrawalStatus.RESCINDED,
                "request_date": now - timedelta(days=35),
                "effective_date": None,
                "last_dose_date": None,
                "last_visit_date": now - timedelta(days=35),
                "initiated_by": "Subject",
                "investigator_name": "Dr. David Park",
                "subject_consents_to_follow_up": True,
                "subject_consents_to_data_use": True,
                "irb_notification_date": None,
                "sponsor_notification_date": None,
                "notes": "Subject initially requested withdrawal but rescinded after counseling session.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "WDR-012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-L004",
                "site_id": "SITE-SEA-001",
                "withdrawal_reason": WithdrawalReason.INVESTIGATOR_DECISION,
                "withdrawal_status": WithdrawalStatus.INITIATED,
                "request_date": now - timedelta(days=5),
                "effective_date": None,
                "last_dose_date": now - timedelta(days=8),
                "last_visit_date": now - timedelta(days=5),
                "initiated_by": "Dr. David Park",
                "investigator_name": "Dr. David Park",
                "subject_consents_to_follow_up": True,
                "subject_consents_to_data_use": True,
                "irb_notification_date": None,
                "sponsor_notification_date": None,
                "notes": "New diagnosis of autoimmune condition contraindicating continued treatment.",
                "created_at": now - timedelta(days=5),
            },
        ]

        for r in requests_data:
            self._withdrawal_requests[r["id"]] = WithdrawalRequest(**r)

        # --- 12 Withdrawal Assessments ---
        assessments_data = [
            {
                "id": "WDA-001",
                "trial_id": EYLEA_TRIAL,
                "withdrawal_request_id": "WDR-001",
                "assessment_type": AssessmentType.SAFETY_ASSESSMENT,
                "assessment_date": now - timedelta(days=88),
                "assessor_name": "Dr. Sarah Chen",
                "assessor_role": "Principal Investigator",
                "clinical_findings": "Grade 3 ocular inflammation with vitreous cells. IOP elevated to 28 mmHg.",
                "safety_concerns_identified": True,
                "ongoing_aes": 2,
                "unresolved_saes": 1,
                "medication_washout_required": False,
                "washout_period_days": 0,
                "recommendations": "Continue monitoring IOP. Refer to ophthalmology for inflammation management.",
                "notes": "Safety assessment completed within 48 hours of withdrawal request.",
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "WDA-002",
                "trial_id": EYLEA_TRIAL,
                "withdrawal_request_id": "WDR-001",
                "assessment_type": AssessmentType.COMPREHENSIVE,
                "assessment_date": now - timedelta(days=86),
                "assessor_name": "Dr. Elena Voss",
                "assessor_role": "Medical Monitor",
                "clinical_findings": "All ongoing AEs documented and causality assessed. No new safety signals.",
                "safety_concerns_identified": True,
                "ongoing_aes": 2,
                "unresolved_saes": 1,
                "medication_washout_required": False,
                "washout_period_days": 0,
                "recommendations": "Follow-up visits at 30 and 90 days post-withdrawal recommended.",
                "notes": "Comprehensive review by medical monitor.",
                "created_at": now - timedelta(days=86),
            },
            {
                "id": "WDA-003",
                "trial_id": EYLEA_TRIAL,
                "withdrawal_request_id": "WDR-002",
                "assessment_type": AssessmentType.CONSENT_REVIEW,
                "assessment_date": now - timedelta(days=74),
                "assessor_name": "Study Coordinator Jane Smith",
                "assessor_role": "Study Coordinator",
                "clinical_findings": "Consent withdrawal documented. Subject declines further follow-up visits.",
                "safety_concerns_identified": False,
                "ongoing_aes": 0,
                "unresolved_saes": 0,
                "medication_washout_required": False,
                "washout_period_days": 0,
                "recommendations": "Ensure data collected to date is properly documented.",
                "notes": "Subject confirmed withdrawal of consent in writing.",
                "created_at": now - timedelta(days=74),
            },
            {
                "id": "WDA-004",
                "trial_id": EYLEA_TRIAL,
                "withdrawal_request_id": "WDR-004",
                "assessment_type": AssessmentType.PROTOCOL_REVIEW,
                "assessment_date": now - timedelta(days=28),
                "assessor_name": "Dr. Robert Kim",
                "assessor_role": "Sub-Investigator",
                "clinical_findings": "Subject received prohibited statin medication for 3 weeks during treatment period.",
                "safety_concerns_identified": False,
                "ongoing_aes": 1,
                "unresolved_saes": 0,
                "medication_washout_required": True,
                "washout_period_days": 14,
                "recommendations": "Review protocol deviation impact on data integrity. Washout required before any further assessments.",
                "notes": "Protocol deviation report filed. Under sponsor review.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "WDA-005",
                "trial_id": DUPIXENT_TRIAL,
                "withdrawal_request_id": "WDR-005",
                "assessment_type": AssessmentType.EFFICACY_ASSESSMENT,
                "assessment_date": now - timedelta(days=79),
                "assessor_name": "Dr. Michael Torres",
                "assessor_role": "Principal Investigator",
                "clinical_findings": "EASI score unchanged from baseline after 12 weeks. No clinical improvement observed.",
                "safety_concerns_identified": False,
                "ongoing_aes": 0,
                "unresolved_saes": 0,
                "medication_washout_required": True,
                "washout_period_days": 28,
                "recommendations": "28-day washout before initiating alternative therapy.",
                "notes": "Efficacy failure documented per protocol criteria.",
                "created_at": now - timedelta(days=79),
            },
            {
                "id": "WDA-006",
                "trial_id": DUPIXENT_TRIAL,
                "withdrawal_request_id": "WDR-006",
                "assessment_type": AssessmentType.SAFETY_ASSESSMENT,
                "assessment_date": now - timedelta(days=64),
                "assessor_name": "Dr. Michael Torres",
                "assessor_role": "Principal Investigator",
                "clinical_findings": "Severe injection site reaction with cellulitis requiring IV antibiotics and hospitalization.",
                "safety_concerns_identified": True,
                "ongoing_aes": 3,
                "unresolved_saes": 1,
                "medication_washout_required": False,
                "washout_period_days": 0,
                "recommendations": "Continue antibiotic course. Monitor wound healing. SAE report filed.",
                "notes": "SAE reported to sponsor within 24 hours.",
                "created_at": now - timedelta(days=64),
            },
            {
                "id": "WDA-007",
                "trial_id": DUPIXENT_TRIAL,
                "withdrawal_request_id": "WDR-006",
                "assessment_type": AssessmentType.MEDICAL_EVALUATION,
                "assessment_date": now - timedelta(days=55),
                "assessor_name": "Dr. Grace Lee",
                "assessor_role": "Independent Medical Monitor",
                "clinical_findings": "Infection resolved. Wound healing appropriately. No systemic complications.",
                "safety_concerns_identified": False,
                "ongoing_aes": 1,
                "unresolved_saes": 0,
                "medication_washout_required": False,
                "washout_period_days": 0,
                "recommendations": "Clear for follow-up assessments. No further intervention required.",
                "notes": "Independent review confirms resolution of SAE.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "WDA-008",
                "trial_id": DUPIXENT_TRIAL,
                "withdrawal_request_id": "WDR-008",
                "assessment_type": AssessmentType.PROTOCOL_REVIEW,
                "assessment_date": now - timedelta(days=18),
                "assessor_name": "Dr. Emily Watson",
                "assessor_role": "Principal Investigator",
                "clinical_findings": "Subject missed 4 of last 6 scheduled visits. Non-compliance documented.",
                "safety_concerns_identified": False,
                "ongoing_aes": 0,
                "unresolved_saes": 0,
                "medication_washout_required": False,
                "washout_period_days": 0,
                "recommendations": "Complete withdrawal documentation. Schedule final safety visit.",
                "notes": "Investigator-initiated withdrawal due to visit non-compliance.",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "WDA-009",
                "trial_id": LIBTAYO_TRIAL,
                "withdrawal_request_id": "WDR-009",
                "assessment_type": AssessmentType.SAFETY_ASSESSMENT,
                "assessment_date": now - timedelta(days=69),
                "assessor_name": "Dr. Angela Martinez",
                "assessor_role": "Principal Investigator",
                "clinical_findings": "ALT/AST >10x ULN. Bilirubin 3.2 mg/dL. Immune-related hepatitis confirmed on biopsy.",
                "safety_concerns_identified": True,
                "ongoing_aes": 4,
                "unresolved_saes": 1,
                "medication_washout_required": True,
                "washout_period_days": 42,
                "recommendations": "High-dose corticosteroids initiated. Hepatology consult obtained. Monitor LFTs biweekly.",
                "notes": "Grade 3 irAE hepatitis. Requires extended safety follow-up.",
                "created_at": now - timedelta(days=69),
            },
            {
                "id": "WDA-010",
                "trial_id": LIBTAYO_TRIAL,
                "withdrawal_request_id": "WDR-009",
                "assessment_type": AssessmentType.COMPREHENSIVE,
                "assessment_date": now - timedelta(days=50),
                "assessor_name": "Dr. Mark Phillips",
                "assessor_role": "Medical Monitor",
                "clinical_findings": "LFTs trending toward normalization. Steroid taper initiated. Tumor assessment stable.",
                "safety_concerns_identified": True,
                "ongoing_aes": 3,
                "unresolved_saes": 1,
                "medication_washout_required": True,
                "washout_period_days": 42,
                "recommendations": "Continue steroid taper. Follow-up LFTs weekly. Consider alternative oncology treatment.",
                "notes": "Comprehensive 30-day post-withdrawal assessment.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "WDA-011",
                "trial_id": LIBTAYO_TRIAL,
                "withdrawal_request_id": "WDR-010",
                "assessment_type": AssessmentType.EFFICACY_ASSESSMENT,
                "assessment_date": now - timedelta(days=44),
                "assessor_name": "Dr. Angela Martinez",
                "assessor_role": "Principal Investigator",
                "clinical_findings": "CT scan shows 25% increase in target lesion sum. Progressive disease per RECIST 1.1.",
                "safety_concerns_identified": False,
                "ongoing_aes": 1,
                "unresolved_saes": 0,
                "medication_washout_required": False,
                "washout_period_days": 0,
                "recommendations": "Refer to tumor board for next-line therapy discussion.",
                "notes": "Disease progression confirmed. Withdrawal justified per protocol.",
                "created_at": now - timedelta(days=44),
            },
            {
                "id": "WDA-012",
                "trial_id": LIBTAYO_TRIAL,
                "withdrawal_request_id": "WDR-012",
                "assessment_type": AssessmentType.MEDICAL_EVALUATION,
                "assessment_date": now - timedelta(days=4),
                "assessor_name": "Dr. David Park",
                "assessor_role": "Principal Investigator",
                "clinical_findings": "New diagnosis of lupus-like syndrome. Contraindication to checkpoint inhibitor therapy.",
                "safety_concerns_identified": True,
                "ongoing_aes": 2,
                "unresolved_saes": 0,
                "medication_washout_required": True,
                "washout_period_days": 30,
                "recommendations": "Rheumatology referral. Complete withdrawal processing. 30-day washout required.",
                "notes": "Preliminary assessment. Full evaluation pending rheumatology input.",
                "created_at": now - timedelta(days=4),
            },
        ]

        for a in assessments_data:
            self._withdrawal_assessments[a["id"]] = WithdrawalAssessment(**a)

        # --- 12 Withdrawal Follow-Ups ---
        follow_ups_data = [
            {
                "id": "WDF-001",
                "trial_id": EYLEA_TRIAL,
                "withdrawal_request_id": "WDR-001",
                "subject_id": "SUBJ-E001",
                "follow_up_outcome": FollowUpOutcome.COMPLETED,
                "visit_number": 1,
                "scheduled_date": now - timedelta(days=55),
                "actual_date": now - timedelta(days=55),
                "contact_method": "In-person visit",
                "contact_attempts": 1,
                "safety_data_collected": True,
                "survival_status_confirmed": True,
                "performed_by": "Nurse Patricia Wells",
                "notes": "30-day post-withdrawal safety visit completed. IOP normalized to 16 mmHg.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "WDF-002",
                "trial_id": EYLEA_TRIAL,
                "withdrawal_request_id": "WDR-001",
                "subject_id": "SUBJ-E001",
                "follow_up_outcome": FollowUpOutcome.COMPLETED,
                "visit_number": 2,
                "scheduled_date": now - timedelta(days=1),
                "actual_date": now - timedelta(days=1),
                "contact_method": "In-person visit",
                "contact_attempts": 1,
                "safety_data_collected": True,
                "survival_status_confirmed": True,
                "performed_by": "Nurse Patricia Wells",
                "notes": "90-day follow-up complete. All AEs resolved. Subject stable.",
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "WDF-003",
                "trial_id": EYLEA_TRIAL,
                "withdrawal_request_id": "WDR-003",
                "subject_id": "SUBJ-E003",
                "follow_up_outcome": FollowUpOutcome.UNABLE_TO_CONTACT,
                "visit_number": 1,
                "scheduled_date": now - timedelta(days=30),
                "actual_date": None,
                "contact_method": "Phone",
                "contact_attempts": 5,
                "safety_data_collected": False,
                "survival_status_confirmed": False,
                "performed_by": "Study Coordinator Jane Smith",
                "notes": "Multiple phone attempts over 14 days. Registered mail sent. No response.",
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "WDF-004",
                "trial_id": EYLEA_TRIAL,
                "withdrawal_request_id": "WDR-004",
                "subject_id": "SUBJ-E004",
                "follow_up_outcome": FollowUpOutcome.ONGOING,
                "visit_number": 1,
                "scheduled_date": now + timedelta(days=5),
                "actual_date": None,
                "contact_method": None,
                "contact_attempts": 0,
                "safety_data_collected": False,
                "survival_status_confirmed": False,
                "performed_by": "Study Coordinator Jane Smith",
                "notes": "Follow-up visit scheduled pending withdrawal confirmation.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "WDF-005",
                "trial_id": DUPIXENT_TRIAL,
                "withdrawal_request_id": "WDR-005",
                "subject_id": "SUBJ-D001",
                "follow_up_outcome": FollowUpOutcome.COMPLETED,
                "visit_number": 1,
                "scheduled_date": now - timedelta(days=49),
                "actual_date": now - timedelta(days=49),
                "contact_method": "In-person visit",
                "contact_attempts": 1,
                "safety_data_collected": True,
                "survival_status_confirmed": True,
                "performed_by": "Nurse Karen Liu",
                "notes": "28-day washout confirmed. No residual drug effects. Cleared for alternative therapy.",
                "created_at": now - timedelta(days=49),
            },
            {
                "id": "WDF-006",
                "trial_id": DUPIXENT_TRIAL,
                "withdrawal_request_id": "WDR-006",
                "subject_id": "SUBJ-D002",
                "follow_up_outcome": FollowUpOutcome.COMPLETED,
                "visit_number": 1,
                "scheduled_date": now - timedelta(days=35),
                "actual_date": now - timedelta(days=34),
                "contact_method": "In-person visit",
                "contact_attempts": 1,
                "safety_data_collected": True,
                "survival_status_confirmed": True,
                "performed_by": "Nurse Karen Liu",
                "notes": "Injection site fully healed. No signs of infection recurrence.",
                "created_at": now - timedelta(days=34),
            },
            {
                "id": "WDF-007",
                "trial_id": DUPIXENT_TRIAL,
                "withdrawal_request_id": "WDR-006",
                "subject_id": "SUBJ-D002",
                "follow_up_outcome": FollowUpOutcome.PARTIAL,
                "visit_number": 2,
                "scheduled_date": now - timedelta(days=5),
                "actual_date": now - timedelta(days=5),
                "contact_method": "Phone",
                "contact_attempts": 2,
                "safety_data_collected": True,
                "survival_status_confirmed": True,
                "performed_by": "Nurse Karen Liu",
                "notes": "Phone follow-up only. Subject declined in-person visit. Verbal safety assessment obtained.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "WDF-008",
                "trial_id": DUPIXENT_TRIAL,
                "withdrawal_request_id": "WDR-008",
                "subject_id": "SUBJ-D004",
                "follow_up_outcome": FollowUpOutcome.REFUSED,
                "visit_number": 1,
                "scheduled_date": now - timedelta(days=5),
                "actual_date": None,
                "contact_method": "Phone",
                "contact_attempts": 3,
                "safety_data_collected": False,
                "survival_status_confirmed": True,
                "performed_by": "Study Coordinator Alex Yun",
                "notes": "Subject refused follow-up visit. Confirmed alive and well via phone but declines further participation.",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "WDF-009",
                "trial_id": LIBTAYO_TRIAL,
                "withdrawal_request_id": "WDR-009",
                "subject_id": "SUBJ-L001",
                "follow_up_outcome": FollowUpOutcome.COMPLETED,
                "visit_number": 1,
                "scheduled_date": now - timedelta(days=37),
                "actual_date": now - timedelta(days=37),
                "contact_method": "In-person visit",
                "contact_attempts": 1,
                "safety_data_collected": True,
                "survival_status_confirmed": True,
                "performed_by": "Nurse David Park",
                "notes": "30-day follow-up. LFTs improving on steroid taper. ALT 3x ULN, down from 10x.",
                "created_at": now - timedelta(days=37),
            },
            {
                "id": "WDF-010",
                "trial_id": LIBTAYO_TRIAL,
                "withdrawal_request_id": "WDR-009",
                "subject_id": "SUBJ-L001",
                "follow_up_outcome": FollowUpOutcome.ONGOING,
                "visit_number": 2,
                "scheduled_date": now + timedelta(days=10),
                "actual_date": None,
                "contact_method": None,
                "contact_attempts": 0,
                "safety_data_collected": False,
                "survival_status_confirmed": False,
                "performed_by": "Nurse David Park",
                "notes": "90-day follow-up scheduled. Pending LFT normalization confirmation.",
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "WDF-011",
                "trial_id": LIBTAYO_TRIAL,
                "withdrawal_request_id": "WDR-010",
                "subject_id": "SUBJ-L002",
                "follow_up_outcome": FollowUpOutcome.DECEASED,
                "visit_number": 1,
                "scheduled_date": now - timedelta(days=15),
                "actual_date": now - timedelta(days=20),
                "contact_method": "Medical records review",
                "contact_attempts": 2,
                "safety_data_collected": True,
                "survival_status_confirmed": True,
                "performed_by": "Dr. Angela Martinez",
                "notes": "Subject deceased due to disease progression. Death unrelated to study drug per investigator assessment.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "WDF-012",
                "trial_id": LIBTAYO_TRIAL,
                "withdrawal_request_id": "WDR-012",
                "subject_id": "SUBJ-L004",
                "follow_up_outcome": FollowUpOutcome.ONGOING,
                "visit_number": 1,
                "scheduled_date": now + timedelta(days=25),
                "actual_date": None,
                "contact_method": None,
                "contact_attempts": 0,
                "safety_data_collected": False,
                "survival_status_confirmed": False,
                "performed_by": "Nurse Sarah Kim",
                "notes": "Initial follow-up scheduled for 30 days post-withdrawal.",
                "created_at": now - timedelta(days=3),
            },
        ]

        for f in follow_ups_data:
            self._withdrawal_follow_ups[f["id"]] = WithdrawalFollowUp(**f)

        # --- 12 Data Disposition Records ---
        disposition_data = [
            {
                "id": "DDR-001",
                "trial_id": EYLEA_TRIAL,
                "withdrawal_request_id": "WDR-001",
                "subject_id": "SUBJ-E001",
                "data_disposition": DataDisposition.INCLUDE_ALL,
                "analysis_population": "ITT",
                "data_cutoff_date": now - timedelta(days=85),
                "visits_included": 8,
                "visits_excluded": 0,
                "rationale": "Subject consents to data use. All data collected per protocol prior to withdrawal.",
                "statistician_name": "Dr. James Liu",
                "approved_by": "Dr. Elena Voss",
                "approval_date": now - timedelta(days=82),
                "regulatory_impact": "None. Data included in primary analysis per SAP.",
                "notes": "Full data inclusion per subject consent and SAP requirements.",
                "created_at": now - timedelta(days=84),
            },
            {
                "id": "DDR-002",
                "trial_id": EYLEA_TRIAL,
                "withdrawal_request_id": "WDR-002",
                "subject_id": "SUBJ-E002",
                "data_disposition": DataDisposition.INCLUDE_PARTIAL,
                "analysis_population": "ITT",
                "data_cutoff_date": now - timedelta(days=73),
                "visits_included": 5,
                "visits_excluded": 3,
                "rationale": "Subject consents to data use but declined follow-up. Include data through last visit.",
                "statistician_name": "Dr. James Liu",
                "approved_by": "Dr. Elena Voss",
                "approval_date": now - timedelta(days=70),
                "regulatory_impact": "Minor. Last observation carried forward for missing visits.",
                "notes": "LOCF applied for missing efficacy data points.",
                "created_at": now - timedelta(days=72),
            },
            {
                "id": "DDR-003",
                "trial_id": EYLEA_TRIAL,
                "withdrawal_request_id": "WDR-003",
                "subject_id": "SUBJ-E003",
                "data_disposition": DataDisposition.EXCLUDE_POST_WITHDRAWAL,
                "analysis_population": "Modified ITT",
                "data_cutoff_date": now - timedelta(days=75),
                "visits_included": 3,
                "visits_excluded": 5,
                "rationale": "Lost to follow-up. Include data through last confirmed visit only.",
                "statistician_name": "Dr. James Liu",
                "approved_by": None,
                "approval_date": None,
                "regulatory_impact": "Moderate. Missing data may require sensitivity analysis.",
                "notes": "Pending approval. Sensitivity analysis planned for primary endpoint.",
                "created_at": now - timedelta(days=55),
            },
            {
                "id": "DDR-004",
                "trial_id": EYLEA_TRIAL,
                "withdrawal_request_id": "WDR-004",
                "subject_id": "SUBJ-E004",
                "data_disposition": DataDisposition.PER_PROTOCOL_ANALYSIS,
                "analysis_population": "Per Protocol",
                "data_cutoff_date": now - timedelta(days=35),
                "visits_included": 6,
                "visits_excluded": 2,
                "rationale": "Protocol violation. Exclude from per-protocol set. Include in ITT with sensitivity analysis.",
                "statistician_name": "Dr. James Liu",
                "approved_by": None,
                "approval_date": None,
                "regulatory_impact": "Significant. Protocol deviation requires DSMB review.",
                "notes": "Under review. Awaiting DSMB recommendation on data handling.",
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "DDR-005",
                "trial_id": DUPIXENT_TRIAL,
                "withdrawal_request_id": "WDR-005",
                "subject_id": "SUBJ-D001",
                "data_disposition": DataDisposition.INCLUDE_ALL,
                "analysis_population": "ITT",
                "data_cutoff_date": now - timedelta(days=77),
                "visits_included": 10,
                "visits_excluded": 0,
                "rationale": "Lack of efficacy withdrawal. All data valuable for efficacy analysis.",
                "statistician_name": "Dr. Rebecca Torres",
                "approved_by": "Dr. Mark Phillips",
                "approval_date": now - timedelta(days=74),
                "regulatory_impact": "None. Expected withdrawal pattern in efficacy analysis.",
                "notes": "Treatment failure data essential for primary endpoint analysis.",
                "created_at": now - timedelta(days=76),
            },
            {
                "id": "DDR-006",
                "trial_id": DUPIXENT_TRIAL,
                "withdrawal_request_id": "WDR-006",
                "subject_id": "SUBJ-D002",
                "data_disposition": DataDisposition.INCLUDE_ALL,
                "analysis_population": "Safety Population",
                "data_cutoff_date": now - timedelta(days=62),
                "visits_included": 7,
                "visits_excluded": 0,
                "rationale": "AE withdrawal. All data critical for safety analysis. Subject consents to full data use.",
                "statistician_name": "Dr. Rebecca Torres",
                "approved_by": "Dr. Mark Phillips",
                "approval_date": now - timedelta(days=58),
                "regulatory_impact": "None for safety. SAE data reported to regulatory authorities.",
                "notes": "Key safety data for injection site reaction signal detection.",
                "created_at": now - timedelta(days=61),
            },
            {
                "id": "DDR-007",
                "trial_id": DUPIXENT_TRIAL,
                "withdrawal_request_id": "WDR-007",
                "subject_id": "SUBJ-D003",
                "data_disposition": DataDisposition.EXCLUDE_ALL,
                "analysis_population": "None",
                "data_cutoff_date": None,
                "visits_included": 0,
                "visits_excluded": 4,
                "rationale": "Subject withdrew all consent including data use. All data must be excluded per regulatory requirements.",
                "statistician_name": "Dr. Rebecca Torres",
                "approved_by": None,
                "approval_date": None,
                "regulatory_impact": "High. Complete data exclusion may affect sample size calculations.",
                "notes": "Legal review of consent withdrawal implications in progress.",
                "created_at": now - timedelta(days=9),
            },
            {
                "id": "DDR-008",
                "trial_id": DUPIXENT_TRIAL,
                "withdrawal_request_id": "WDR-008",
                "subject_id": "SUBJ-D004",
                "data_disposition": DataDisposition.SENSITIVITY_ANALYSIS,
                "analysis_population": "ITT with sensitivity",
                "data_cutoff_date": now - timedelta(days=25),
                "visits_included": 4,
                "visits_excluded": 6,
                "rationale": "Non-compliance withdrawal. Include in ITT. Perform sensitivity analysis excluding this subject.",
                "statistician_name": "Dr. Rebecca Torres",
                "approved_by": None,
                "approval_date": None,
                "regulatory_impact": "Moderate. Requires pre-specified sensitivity analysis per SAP.",
                "notes": "Documentation pending. Sensitivity analysis methodology under review.",
                "created_at": now - timedelta(days=17),
            },
            {
                "id": "DDR-009",
                "trial_id": LIBTAYO_TRIAL,
                "withdrawal_request_id": "WDR-009",
                "subject_id": "SUBJ-L001",
                "data_disposition": DataDisposition.INCLUDE_ALL,
                "analysis_population": "Safety and ITT",
                "data_cutoff_date": now - timedelta(days=67),
                "visits_included": 6,
                "visits_excluded": 0,
                "rationale": "Safety withdrawal due to irAE. All data included for both safety and efficacy analyses.",
                "statistician_name": "Dr. Kevin Park",
                "approved_by": "Dr. Grace Lee",
                "approval_date": now - timedelta(days=63),
                "regulatory_impact": "None. irAE withdrawal expected in IO trial. Data essential for safety profiling.",
                "notes": "Hepatitis event data critical for regulatory safety narrative.",
                "created_at": now - timedelta(days=66),
            },
            {
                "id": "DDR-010",
                "trial_id": LIBTAYO_TRIAL,
                "withdrawal_request_id": "WDR-010",
                "subject_id": "SUBJ-L002",
                "data_disposition": DataDisposition.INCLUDE_ALL,
                "analysis_population": "ITT",
                "data_cutoff_date": now - timedelta(days=42),
                "visits_included": 8,
                "visits_excluded": 0,
                "rationale": "Disease progression withdrawal. All data valuable for efficacy and survival analysis.",
                "statistician_name": "Dr. Kevin Park",
                "approved_by": "Dr. Grace Lee",
                "approval_date": now - timedelta(days=38),
                "regulatory_impact": "None. Progressive disease is a protocol-defined endpoint event.",
                "notes": "Progression event included in PFS analysis per statistical analysis plan.",
                "created_at": now - timedelta(days=41),
            },
            {
                "id": "DDR-011",
                "trial_id": LIBTAYO_TRIAL,
                "withdrawal_request_id": "WDR-011",
                "subject_id": "SUBJ-L003",
                "data_disposition": DataDisposition.INCLUDE_ALL,
                "analysis_population": "ITT",
                "data_cutoff_date": None,
                "visits_included": 5,
                "visits_excluded": 0,
                "rationale": "Withdrawal rescinded. Subject continues in study. All data included.",
                "statistician_name": "Dr. Kevin Park",
                "approved_by": "Dr. Grace Lee",
                "approval_date": now - timedelta(days=30),
                "regulatory_impact": "None. Subject remains enrolled. No data disposition changes.",
                "notes": "Rescission documented. Subject continuing per protocol.",
                "created_at": now - timedelta(days=33),
            },
            {
                "id": "DDR-012",
                "trial_id": LIBTAYO_TRIAL,
                "withdrawal_request_id": "WDR-012",
                "subject_id": "SUBJ-L004",
                "data_disposition": DataDisposition.EXCLUDE_POST_WITHDRAWAL,
                "analysis_population": "Modified ITT",
                "data_cutoff_date": now - timedelta(days=8),
                "visits_included": 3,
                "visits_excluded": 0,
                "rationale": "New medical condition withdrawal. Include pre-withdrawal data. Exclude any post-withdrawal assessments.",
                "statistician_name": "Dr. Kevin Park",
                "approved_by": None,
                "approval_date": None,
                "regulatory_impact": "Minor. Small dataset but no impact on primary analysis power.",
                "notes": "Preliminary disposition. Subject consents to data use for collected data.",
                "created_at": now - timedelta(days=4),
            },
        ]

        for d in disposition_data:
            self._data_disposition_records[d["id"]] = DataDispositionRecord(**d)

    # ------------------------------------------------------------------
    # Withdrawal Requests
    # ------------------------------------------------------------------

    def list_withdrawal_requests(
        self,
        *,
        trial_id: str | None = None,
        withdrawal_reason: WithdrawalReason | None = None,
        withdrawal_status: WithdrawalStatus | None = None,
    ) -> list[WithdrawalRequest]:
        """List withdrawal requests with optional filters."""
        with self._lock:
            result = list(self._withdrawal_requests.values())

        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if withdrawal_reason is not None:
            result = [r for r in result if r.withdrawal_reason == withdrawal_reason]
        if withdrawal_status is not None:
            result = [r for r in result if r.withdrawal_status == withdrawal_status]

        return sorted(result, key=lambda r: r.request_date, reverse=True)

    def get_withdrawal_request(self, request_id: str) -> WithdrawalRequest | None:
        """Get a single withdrawal request by ID."""
        with self._lock:
            return self._withdrawal_requests.get(request_id)

    def create_withdrawal_request(self, payload: WithdrawalRequestCreate) -> WithdrawalRequest:
        """Create a new withdrawal request."""
        now = datetime.now(timezone.utc)
        request_id = f"WDR-{uuid4().hex[:8].upper()}"
        record = WithdrawalRequest(
            id=request_id,
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            site_id=payload.site_id,
            withdrawal_reason=payload.withdrawal_reason,
            withdrawal_status=WithdrawalStatus.INITIATED,
            request_date=payload.request_date,
            effective_date=None,
            last_dose_date=None,
            last_visit_date=None,
            initiated_by=payload.initiated_by,
            investigator_name=payload.investigator_name,
            subject_consents_to_follow_up=False,
            subject_consents_to_data_use=True,
            irb_notification_date=None,
            sponsor_notification_date=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._withdrawal_requests[request_id] = record
        logger.info("Created withdrawal request %s for trial %s", request_id, payload.trial_id)
        return record

    def update_withdrawal_request(
        self, request_id: str, payload: WithdrawalRequestUpdate
    ) -> WithdrawalRequest | None:
        """Update an existing withdrawal request."""
        with self._lock:
            existing = self._withdrawal_requests.get(request_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = WithdrawalRequest(**data)
            self._withdrawal_requests[request_id] = updated
        return updated

    def delete_withdrawal_request(self, request_id: str) -> bool:
        """Delete a withdrawal request. Returns True if deleted."""
        with self._lock:
            if request_id in self._withdrawal_requests:
                del self._withdrawal_requests[request_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Withdrawal Assessments
    # ------------------------------------------------------------------

    def list_withdrawal_assessments(
        self,
        *,
        trial_id: str | None = None,
        assessment_type: AssessmentType | None = None,
        withdrawal_request_id: str | None = None,
    ) -> list[WithdrawalAssessment]:
        """List withdrawal assessments with optional filters."""
        with self._lock:
            result = list(self._withdrawal_assessments.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if assessment_type is not None:
            result = [a for a in result if a.assessment_type == assessment_type]
        if withdrawal_request_id is not None:
            result = [a for a in result if a.withdrawal_request_id == withdrawal_request_id]

        return sorted(result, key=lambda a: a.assessment_date, reverse=True)

    def get_withdrawal_assessment(self, assessment_id: str) -> WithdrawalAssessment | None:
        """Get a single withdrawal assessment by ID."""
        with self._lock:
            return self._withdrawal_assessments.get(assessment_id)

    def create_withdrawal_assessment(self, payload: WithdrawalAssessmentCreate) -> WithdrawalAssessment:
        """Create a new withdrawal assessment."""
        now = datetime.now(timezone.utc)
        assessment_id = f"WDA-{uuid4().hex[:8].upper()}"
        record = WithdrawalAssessment(
            id=assessment_id,
            trial_id=payload.trial_id,
            withdrawal_request_id=payload.withdrawal_request_id,
            assessment_type=payload.assessment_type,
            assessment_date=payload.assessment_date,
            assessor_name=payload.assessor_name,
            assessor_role=payload.assessor_role,
            clinical_findings=payload.clinical_findings,
            safety_concerns_identified=False,
            ongoing_aes=0,
            unresolved_saes=0,
            medication_washout_required=False,
            washout_period_days=0,
            recommendations=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._withdrawal_assessments[assessment_id] = record
        logger.info("Created withdrawal assessment %s for request %s", assessment_id, payload.withdrawal_request_id)
        return record

    def update_withdrawal_assessment(
        self, assessment_id: str, payload: WithdrawalAssessmentUpdate
    ) -> WithdrawalAssessment | None:
        """Update an existing withdrawal assessment."""
        with self._lock:
            existing = self._withdrawal_assessments.get(assessment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = WithdrawalAssessment(**data)
            self._withdrawal_assessments[assessment_id] = updated
        return updated

    def delete_withdrawal_assessment(self, assessment_id: str) -> bool:
        """Delete a withdrawal assessment. Returns True if deleted."""
        with self._lock:
            if assessment_id in self._withdrawal_assessments:
                del self._withdrawal_assessments[assessment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Withdrawal Follow-Ups
    # ------------------------------------------------------------------

    def list_withdrawal_follow_ups(
        self,
        *,
        trial_id: str | None = None,
        follow_up_outcome: FollowUpOutcome | None = None,
        subject_id: str | None = None,
    ) -> list[WithdrawalFollowUp]:
        """List withdrawal follow-ups with optional filters."""
        with self._lock:
            result = list(self._withdrawal_follow_ups.values())

        if trial_id is not None:
            result = [f for f in result if f.trial_id == trial_id]
        if follow_up_outcome is not None:
            result = [f for f in result if f.follow_up_outcome == follow_up_outcome]
        if subject_id is not None:
            result = [f for f in result if f.subject_id == subject_id]

        return sorted(result, key=lambda f: f.scheduled_date, reverse=True)

    def get_withdrawal_follow_up(self, follow_up_id: str) -> WithdrawalFollowUp | None:
        """Get a single withdrawal follow-up by ID."""
        with self._lock:
            return self._withdrawal_follow_ups.get(follow_up_id)

    def create_withdrawal_follow_up(self, payload: WithdrawalFollowUpCreate) -> WithdrawalFollowUp:
        """Create a new withdrawal follow-up."""
        now = datetime.now(timezone.utc)
        follow_up_id = f"WDF-{uuid4().hex[:8].upper()}"
        record = WithdrawalFollowUp(
            id=follow_up_id,
            trial_id=payload.trial_id,
            withdrawal_request_id=payload.withdrawal_request_id,
            subject_id=payload.subject_id,
            follow_up_outcome=FollowUpOutcome.ONGOING,
            visit_number=payload.visit_number,
            scheduled_date=payload.scheduled_date,
            actual_date=None,
            contact_method=None,
            contact_attempts=0,
            safety_data_collected=False,
            survival_status_confirmed=False,
            performed_by=payload.performed_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._withdrawal_follow_ups[follow_up_id] = record
        logger.info("Created withdrawal follow-up %s for request %s", follow_up_id, payload.withdrawal_request_id)
        return record

    def update_withdrawal_follow_up(
        self, follow_up_id: str, payload: WithdrawalFollowUpUpdate
    ) -> WithdrawalFollowUp | None:
        """Update an existing withdrawal follow-up."""
        with self._lock:
            existing = self._withdrawal_follow_ups.get(follow_up_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = WithdrawalFollowUp(**data)
            self._withdrawal_follow_ups[follow_up_id] = updated
        return updated

    def delete_withdrawal_follow_up(self, follow_up_id: str) -> bool:
        """Delete a withdrawal follow-up. Returns True if deleted."""
        with self._lock:
            if follow_up_id in self._withdrawal_follow_ups:
                del self._withdrawal_follow_ups[follow_up_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Data Disposition Records
    # ------------------------------------------------------------------

    def list_data_disposition_records(
        self,
        *,
        trial_id: str | None = None,
        data_disposition: DataDisposition | None = None,
        subject_id: str | None = None,
    ) -> list[DataDispositionRecord]:
        """List data disposition records with optional filters."""
        with self._lock:
            result = list(self._data_disposition_records.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]
        if data_disposition is not None:
            result = [d for d in result if d.data_disposition == data_disposition]
        if subject_id is not None:
            result = [d for d in result if d.subject_id == subject_id]

        return sorted(result, key=lambda d: d.created_at, reverse=True)

    def get_data_disposition_record(self, disposition_id: str) -> DataDispositionRecord | None:
        """Get a single data disposition record by ID."""
        with self._lock:
            return self._data_disposition_records.get(disposition_id)

    def create_data_disposition_record(self, payload: DataDispositionRecordCreate) -> DataDispositionRecord:
        """Create a new data disposition record."""
        now = datetime.now(timezone.utc)
        disposition_id = f"DDR-{uuid4().hex[:8].upper()}"
        record = DataDispositionRecord(
            id=disposition_id,
            trial_id=payload.trial_id,
            withdrawal_request_id=payload.withdrawal_request_id,
            subject_id=payload.subject_id,
            data_disposition=payload.data_disposition,
            analysis_population=payload.analysis_population,
            data_cutoff_date=None,
            visits_included=0,
            visits_excluded=0,
            rationale=payload.rationale,
            statistician_name=payload.statistician_name,
            approved_by=None,
            approval_date=None,
            regulatory_impact=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._data_disposition_records[disposition_id] = record
        logger.info("Created data disposition record %s for request %s", disposition_id, payload.withdrawal_request_id)
        return record

    def update_data_disposition_record(
        self, disposition_id: str, payload: DataDispositionRecordUpdate
    ) -> DataDispositionRecord | None:
        """Update an existing data disposition record."""
        with self._lock:
            existing = self._data_disposition_records.get(disposition_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DataDispositionRecord(**data)
            self._data_disposition_records[disposition_id] = updated
        return updated

    def delete_data_disposition_record(self, disposition_id: str) -> bool:
        """Delete a data disposition record. Returns True if deleted."""
        with self._lock:
            if disposition_id in self._data_disposition_records:
                del self._data_disposition_records[disposition_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> SubjectWithdrawalMetrics:
        """Compute aggregated subject withdrawal metrics, optionally filtered by trial."""
        with self._lock:
            requests = list(self._withdrawal_requests.values())
            assessments = list(self._withdrawal_assessments.values())
            follow_ups = list(self._withdrawal_follow_ups.values())
            dispositions = list(self._data_disposition_records.values())

        # Apply trial filter if provided
        if trial_id is not None:
            requests = [r for r in requests if r.trial_id == trial_id]
            assessments = [a for a in assessments if a.trial_id == trial_id]
            follow_ups = [f for f in follow_ups if f.trial_id == trial_id]
            dispositions = [d for d in dispositions if d.trial_id == trial_id]

        # Withdrawals by reason
        withdrawals_by_reason: dict[str, int] = {}
        for r in requests:
            key = r.withdrawal_reason.value
            withdrawals_by_reason[key] = withdrawals_by_reason.get(key, 0) + 1

        # Withdrawals by status
        withdrawals_by_status: dict[str, int] = {}
        for r in requests:
            key = r.withdrawal_status.value
            withdrawals_by_status[key] = withdrawals_by_status.get(key, 0) + 1

        # Withdrawal rate (completed + confirmed vs total)
        completed_count = sum(
            1 for r in requests if r.withdrawal_status in (
                WithdrawalStatus.COMPLETED, WithdrawalStatus.CONFIRMED
            )
        )
        withdrawal_rate = round(
            (completed_count / max(1, len(requests))) * 100, 1
        )

        # Assessments by type
        assessments_by_type: dict[str, int] = {}
        for a in assessments:
            key = a.assessment_type.value
            assessments_by_type[key] = assessments_by_type.get(key, 0) + 1

        # Safety concern rate
        safety_concern_count = sum(1 for a in assessments if a.safety_concerns_identified)
        safety_concern_rate = round(
            (safety_concern_count / max(1, len(assessments))) * 100, 1
        )

        # Follow-ups by outcome
        follow_ups_by_outcome: dict[str, int] = {}
        for f in follow_ups:
            key = f.follow_up_outcome.value
            follow_ups_by_outcome[key] = follow_ups_by_outcome.get(key, 0) + 1

        # Follow-up completion rate
        completed_follow_ups = sum(
            1 for f in follow_ups if f.follow_up_outcome == FollowUpOutcome.COMPLETED
        )
        follow_up_completion_rate = round(
            (completed_follow_ups / max(1, len(follow_ups))) * 100, 1
        )

        # Dispositions by type
        dispositions_by_type: dict[str, int] = {}
        for d in dispositions:
            key = d.data_disposition.value
            dispositions_by_type[key] = dispositions_by_type.get(key, 0) + 1

        return SubjectWithdrawalMetrics(
            total_withdrawals=len(requests),
            withdrawals_by_reason=withdrawals_by_reason,
            withdrawals_by_status=withdrawals_by_status,
            withdrawal_rate=withdrawal_rate,
            total_assessments=len(assessments),
            assessments_by_type=assessments_by_type,
            safety_concern_rate=safety_concern_rate,
            total_follow_ups=len(follow_ups),
            follow_ups_by_outcome=follow_ups_by_outcome,
            follow_up_completion_rate=follow_up_completion_rate,
            total_disposition_records=len(dispositions),
            dispositions_by_type=dispositions_by_type,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: SubjectWithdrawalService | None = None
_instance_lock = threading.Lock()


def get_subject_withdrawal_service() -> SubjectWithdrawalService:
    """Return the singleton SubjectWithdrawalService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = SubjectWithdrawalService()
    return _instance


def reset_subject_withdrawal_service() -> SubjectWithdrawalService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = SubjectWithdrawalService()
    return _instance
