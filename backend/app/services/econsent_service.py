"""Electronic Informed Consent (eConsent) Management Service (CLINICAL-18).

Manages electronic consent operations including consent document definitions,
patient consent lifecycle, 21 CFR Part 11 compliant audit trails, quiz-based
comprehension verification, withdrawal management with data retention preferences,
re-consent tracking for protocol amendments, and multi-language support.

Usage:
    from app.services.econsent_service import (
        get_econsent_service,
    )

    svc = get_econsent_service()
    docs = svc.list_documents()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.econsent import (
    ComprehensionAnalytics,
    CompleteElementRequest,
    ConsentAuditAction,
    ConsentAuditEntry,
    ConsentDocument,
    ConsentDocumentCreate,
    ConsentDocumentUpdate,
    ConsentElement,
    ConsentElementCreate,
    ConsentElementType,
    ConsentSignRequest,
    ConsentStatus,
    ConsentType,
    ConsentWithdrawal,
    ConsentWithdrawalCreate,
    DataRetentionPreference,
    DocumentLanguage,
    EConsentMetrics,
    PatientConsent,
    PatientConsentCreate,
    PatientConsentUpdate,
    ViewElementRequest,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"

# Quiz pass threshold (80%)
QUIZ_PASS_THRESHOLD = 80.0


class EConsentService:
    """In-memory Electronic Informed Consent engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._documents: dict[str, ConsentDocument] = {}
        self._consents: dict[str, PatientConsent] = {}
        self._withdrawals: dict[str, ConsentWithdrawal] = {}
        self._audit_entries: dict[str, ConsentAuditEntry] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:
        """Pre-populate realistic eConsent data across clinical trials."""
        now = datetime.now(timezone.utc)

        # --- 6 Consent Documents ---
        docs_data = [
            {
                "id": "CDOC-001",
                "trial_id": EYLEA_TRIAL,
                "version": "3.0",
                "title": "EYLEA HD Phase III Main Study Informed Consent",
                "consent_type": ConsentType.MAIN_STUDY,
                "effective_date": now - timedelta(days=120),
                "language": DocumentLanguage.EN,
                "irb_approval_date": now - timedelta(days=130),
                "total_pages": 18,
                "estimated_read_time_minutes": 35,
                "elements": [
                    ConsentElement(
                        id="EL-001-01",
                        element_type=ConsentElementType.TEXT,
                        page_number=1,
                        content_summary="Study purpose and background information",
                        required=True,
                    ),
                    ConsentElement(
                        id="EL-001-02",
                        element_type=ConsentElementType.VIDEO,
                        page_number=3,
                        content_summary="Video overview of the EYLEA HD treatment process",
                        required=True,
                    ),
                    ConsentElement(
                        id="EL-001-03",
                        element_type=ConsentElementType.TEXT,
                        page_number=5,
                        content_summary="Risks and benefits of participation",
                        required=True,
                    ),
                    ConsentElement(
                        id="EL-001-04",
                        element_type=ConsentElementType.QUIZ,
                        page_number=8,
                        content_summary="Knowledge verification quiz",
                        required=True,
                        quiz_question="What is the primary purpose of this study?",
                        quiz_correct_answer="To evaluate the efficacy of EYLEA HD for wet AMD",
                        quiz_options=[
                            "To evaluate the efficacy of EYLEA HD for wet AMD",
                            "To test a new surgical procedure",
                            "To compare different vitamins for eye health",
                            "To study general eye health in adults",
                        ],
                    ),
                    ConsentElement(
                        id="EL-001-05",
                        element_type=ConsentElementType.QUIZ,
                        page_number=10,
                        content_summary="Risk understanding quiz",
                        required=True,
                        quiz_question="Which of the following is a potential risk of the study medication?",
                        quiz_correct_answer="Eye infection or inflammation",
                        quiz_options=[
                            "Eye infection or inflammation",
                            "Permanent hair loss",
                            "Significant weight gain",
                            "Hearing impairment",
                        ],
                    ),
                    ConsentElement(
                        id="EL-001-06",
                        element_type=ConsentElementType.CHECKBOX,
                        page_number=15,
                        content_summary="Acknowledgment of voluntary participation",
                        required=True,
                    ),
                    ConsentElement(
                        id="EL-001-07",
                        element_type=ConsentElementType.ACKNOWLEDGMENT,
                        page_number=17,
                        content_summary="HIPAA authorization acknowledgment",
                        required=True,
                    ),
                    ConsentElement(
                        id="EL-001-08",
                        element_type=ConsentElementType.SIGNATURE,
                        page_number=18,
                        content_summary="Patient signature block",
                        required=True,
                    ),
                ],
            },
            {
                "id": "CDOC-002",
                "trial_id": DUPIXENT_TRIAL,
                "version": "2.1",
                "title": "DUPIXENT Atopic Dermatitis Phase III Main Study Consent",
                "consent_type": ConsentType.MAIN_STUDY,
                "effective_date": now - timedelta(days=90),
                "language": DocumentLanguage.EN,
                "irb_approval_date": now - timedelta(days=100),
                "total_pages": 22,
                "estimated_read_time_minutes": 40,
                "elements": [
                    ConsentElement(
                        id="EL-002-01",
                        element_type=ConsentElementType.TEXT,
                        page_number=1,
                        content_summary="Study overview and purpose",
                        required=True,
                    ),
                    ConsentElement(
                        id="EL-002-02",
                        element_type=ConsentElementType.VIDEO,
                        page_number=4,
                        content_summary="Video explaining subcutaneous injection technique",
                        required=True,
                    ),
                    ConsentElement(
                        id="EL-002-03",
                        element_type=ConsentElementType.QUIZ,
                        page_number=8,
                        content_summary="Comprehension quiz on study procedures",
                        required=True,
                        quiz_question="How often will study visits occur during the treatment period?",
                        quiz_correct_answer="Every 2 weeks",
                        quiz_options=[
                            "Every 2 weeks",
                            "Once a month",
                            "Every 3 months",
                            "Only at the start and end",
                        ],
                    ),
                    ConsentElement(
                        id="EL-002-04",
                        element_type=ConsentElementType.QUIZ,
                        page_number=12,
                        content_summary="Safety understanding quiz",
                        required=True,
                        quiz_question="What should you do if you experience a severe allergic reaction?",
                        quiz_correct_answer="Seek immediate medical attention and contact the study team",
                        quiz_options=[
                            "Seek immediate medical attention and contact the study team",
                            "Wait until your next study visit to report it",
                            "Take over-the-counter antihistamines only",
                            "Stop all medications and rest",
                        ],
                    ),
                    ConsentElement(
                        id="EL-002-05",
                        element_type=ConsentElementType.CHECKBOX,
                        page_number=19,
                        content_summary="Acknowledgment of rights and voluntary participation",
                        required=True,
                    ),
                    ConsentElement(
                        id="EL-002-06",
                        element_type=ConsentElementType.SIGNATURE,
                        page_number=22,
                        content_summary="Patient signature block",
                        required=True,
                    ),
                ],
            },
            {
                "id": "CDOC-003",
                "trial_id": LIBTAYO_TRIAL,
                "version": "1.2",
                "title": "LIBTAYO Oncology Phase II Main Study Consent",
                "consent_type": ConsentType.MAIN_STUDY,
                "effective_date": now - timedelta(days=60),
                "language": DocumentLanguage.EN,
                "irb_approval_date": now - timedelta(days=70),
                "total_pages": 25,
                "estimated_read_time_minutes": 45,
                "elements": [
                    ConsentElement(
                        id="EL-003-01",
                        element_type=ConsentElementType.TEXT,
                        page_number=1,
                        content_summary="Study purpose and immunotherapy background",
                        required=True,
                    ),
                    ConsentElement(
                        id="EL-003-02",
                        element_type=ConsentElementType.VIDEO,
                        page_number=5,
                        content_summary="Video on immunotherapy mechanism and potential side effects",
                        required=True,
                    ),
                    ConsentElement(
                        id="EL-003-03",
                        element_type=ConsentElementType.QUIZ,
                        page_number=10,
                        content_summary="Knowledge verification quiz",
                        required=True,
                        quiz_question="What type of treatment is cemiplimab (LIBTAYO)?",
                        quiz_correct_answer="An immune checkpoint inhibitor",
                        quiz_options=[
                            "An immune checkpoint inhibitor",
                            "A traditional chemotherapy drug",
                            "A surgical procedure",
                            "A dietary supplement",
                        ],
                    ),
                    ConsentElement(
                        id="EL-003-04",
                        element_type=ConsentElementType.ACKNOWLEDGMENT,
                        page_number=20,
                        content_summary="Acknowledgment of immunotherapy-specific risks",
                        required=True,
                    ),
                    ConsentElement(
                        id="EL-003-05",
                        element_type=ConsentElementType.SIGNATURE,
                        page_number=25,
                        content_summary="Patient signature block",
                        required=True,
                    ),
                ],
            },
            {
                "id": "CDOC-004",
                "trial_id": EYLEA_TRIAL,
                "version": "1.0",
                "title": "EYLEA HD Biobanking Consent",
                "consent_type": ConsentType.BIOBANKING,
                "effective_date": now - timedelta(days=120),
                "language": DocumentLanguage.EN,
                "irb_approval_date": now - timedelta(days=130),
                "total_pages": 8,
                "estimated_read_time_minutes": 15,
                "elements": [
                    ConsentElement(
                        id="EL-004-01",
                        element_type=ConsentElementType.TEXT,
                        page_number=1,
                        content_summary="Biobanking purpose and sample storage information",
                        required=True,
                    ),
                    ConsentElement(
                        id="EL-004-02",
                        element_type=ConsentElementType.CHECKBOX,
                        page_number=5,
                        content_summary="Consent for future use of biological samples",
                        required=True,
                    ),
                    ConsentElement(
                        id="EL-004-03",
                        element_type=ConsentElementType.SIGNATURE,
                        page_number=8,
                        content_summary="Patient signature block",
                        required=True,
                    ),
                ],
            },
            {
                "id": "CDOC-005",
                "trial_id": DUPIXENT_TRIAL,
                "version": "1.0",
                "title": "DUPIXENT Genetic Testing Consent",
                "consent_type": ConsentType.GENETIC_TESTING,
                "effective_date": now - timedelta(days=90),
                "language": DocumentLanguage.EN,
                "irb_approval_date": now - timedelta(days=100),
                "total_pages": 10,
                "estimated_read_time_minutes": 20,
                "elements": [
                    ConsentElement(
                        id="EL-005-01",
                        element_type=ConsentElementType.TEXT,
                        page_number=1,
                        content_summary="Genetic testing purpose and scope",
                        required=True,
                    ),
                    ConsentElement(
                        id="EL-005-02",
                        element_type=ConsentElementType.QUIZ,
                        page_number=5,
                        content_summary="Genetic testing understanding quiz",
                        required=True,
                        quiz_question="Can genetic test results affect your insurance coverage?",
                        quiz_correct_answer="GINA protects against discrimination by health insurers and employers",
                        quiz_options=[
                            "GINA protects against discrimination by health insurers and employers",
                            "Yes, your insurance will be cancelled",
                            "No, genetic tests have no implications",
                            "Only if you share results publicly",
                        ],
                    ),
                    ConsentElement(
                        id="EL-005-03",
                        element_type=ConsentElementType.SIGNATURE,
                        page_number=10,
                        content_summary="Patient signature block",
                        required=True,
                    ),
                ],
            },
            {
                "id": "CDOC-006",
                "trial_id": LIBTAYO_TRIAL,
                "version": "1.0",
                "title": "LIBTAYO Pediatric Assent Form (Ages 12-17)",
                "consent_type": ConsentType.PEDIATRIC_ASSENT,
                "effective_date": now - timedelta(days=60),
                "language": DocumentLanguage.EN,
                "irb_approval_date": now - timedelta(days=70),
                "total_pages": 6,
                "estimated_read_time_minutes": 10,
                "elements": [
                    ConsentElement(
                        id="EL-006-01",
                        element_type=ConsentElementType.TEXT,
                        page_number=1,
                        content_summary="Simple explanation of the study for adolescents",
                        required=True,
                    ),
                    ConsentElement(
                        id="EL-006-02",
                        element_type=ConsentElementType.VIDEO,
                        page_number=3,
                        content_summary="Animated video explaining the study in age-appropriate language",
                        required=True,
                    ),
                    ConsentElement(
                        id="EL-006-03",
                        element_type=ConsentElementType.QUIZ,
                        page_number=4,
                        content_summary="Understanding check for pediatric participants",
                        required=True,
                        quiz_question="Can you stop being in this study whenever you want?",
                        quiz_correct_answer="Yes, you can leave the study at any time",
                        quiz_options=[
                            "Yes, you can leave the study at any time",
                            "No, you must stay until the study ends",
                            "Only if the doctor says it is okay",
                            "Only if your parents agree",
                        ],
                    ),
                    ConsentElement(
                        id="EL-006-04",
                        element_type=ConsentElementType.SIGNATURE,
                        page_number=6,
                        content_summary="Minor assent signature block",
                        required=True,
                    ),
                ],
            },
        ]

        for d in docs_data:
            self._documents[d["id"]] = ConsentDocument(**d)

        # --- 40 Patient Consent Records ---
        patient_ids = [f"PAT-{i:04d}" for i in range(1, 41)]
        sites = ["SITE-101", "SITE-102", "SITE-103", "SITE-104", "SITE-105"]
        doc_ids_by_trial = {
            EYLEA_TRIAL: ["CDOC-001", "CDOC-004"],
            DUPIXENT_TRIAL: ["CDOC-002", "CDOC-005"],
            LIBTAYO_TRIAL: ["CDOC-003", "CDOC-006"],
        }

        consent_counter = 0
        consents_data: list[dict] = []

        # 15 signed consents for EYLEA
        for i in range(15):
            consent_counter += 1
            pid = patient_ids[i]
            site = sites[i % len(sites)]
            started = now - timedelta(days=100 - i * 2)
            completed = started + timedelta(hours=1, minutes=i * 3)
            doc_id = "CDOC-001" if i < 12 else "CDOC-004"
            quiz_score = 80.0 + (i % 5) * 4.0  # 80, 84, 88, 92, 96
            consents_data.append({
                "id": f"PC-{consent_counter:04d}",
                "patient_id": pid,
                "trial_id": EYLEA_TRIAL,
                "document_id": doc_id,
                "site_id": site,
                "status": ConsentStatus.SIGNED,
                "started_at": started,
                "completed_at": completed,
                "signature_date": completed,
                "witness_name": f"Dr. Witness {i + 1}",
                "witness_signature_date": completed + timedelta(minutes=5),
                "ip_address": f"192.168.1.{10 + i}",
                "device_info": "Chrome 120 / Windows 11" if i % 2 == 0 else "Safari 17 / macOS 14",
                "time_spent_minutes": 25.0 + i * 1.5,
                "quiz_score": min(quiz_score, 100.0),
                "elements_viewed": [f"EL-001-0{j}" for j in range(1, 9)] if doc_id == "CDOC-001" else [f"EL-004-0{j}" for j in range(1, 4)],
                "elements_completed": [f"EL-001-0{j}" for j in range(1, 9)] if doc_id == "CDOC-001" else [f"EL-004-0{j}" for j in range(1, 4)],
                "re_consent_reason": None,
            })

        # 10 signed consents for DUPIXENT
        for i in range(10):
            consent_counter += 1
            pid = patient_ids[15 + i]
            site = sites[i % len(sites)]
            started = now - timedelta(days=80 - i * 2)
            completed = started + timedelta(hours=1, minutes=i * 4)
            doc_id = "CDOC-002" if i < 8 else "CDOC-005"
            quiz_score = 75.0 + (i % 6) * 5.0
            consents_data.append({
                "id": f"PC-{consent_counter:04d}",
                "patient_id": pid,
                "trial_id": DUPIXENT_TRIAL,
                "document_id": doc_id,
                "site_id": site,
                "status": ConsentStatus.SIGNED,
                "started_at": started,
                "completed_at": completed,
                "signature_date": completed,
                "witness_name": f"Dr. Witness {15 + i + 1}",
                "witness_signature_date": completed + timedelta(minutes=5),
                "ip_address": f"10.0.1.{20 + i}",
                "device_info": "Firefox 121 / Ubuntu 22",
                "time_spent_minutes": 30.0 + i * 2.0,
                "quiz_score": min(quiz_score, 100.0),
                "elements_viewed": [f"EL-002-0{j}" for j in range(1, 7)] if doc_id == "CDOC-002" else [f"EL-005-0{j}" for j in range(1, 4)],
                "elements_completed": [f"EL-002-0{j}" for j in range(1, 7)] if doc_id == "CDOC-002" else [f"EL-005-0{j}" for j in range(1, 4)],
                "re_consent_reason": None,
            })

        # 5 in_progress consents for LIBTAYO
        for i in range(5):
            consent_counter += 1
            pid = patient_ids[25 + i]
            site = sites[i % len(sites)]
            started = now - timedelta(hours=i * 2 + 1)
            consents_data.append({
                "id": f"PC-{consent_counter:04d}",
                "patient_id": pid,
                "trial_id": LIBTAYO_TRIAL,
                "document_id": "CDOC-003",
                "site_id": site,
                "status": ConsentStatus.IN_PROGRESS,
                "started_at": started,
                "completed_at": None,
                "signature_date": None,
                "witness_name": None,
                "witness_signature_date": None,
                "ip_address": f"172.16.0.{30 + i}",
                "device_info": "Edge 120 / Windows 11",
                "time_spent_minutes": 10.0 + i * 3.0,
                "quiz_score": None,
                "elements_viewed": [f"EL-003-0{j}" for j in range(1, min(3 + i, 6))],
                "elements_completed": [f"EL-003-0{j}" for j in range(1, min(2 + i, 4))],
                "re_consent_reason": None,
            })

        # 3 re-consented (protocol amendment)
        for i in range(3):
            consent_counter += 1
            pid = patient_ids[i]  # Same patients who already signed
            site = sites[i % len(sites)]
            started = now - timedelta(days=10 - i)
            completed = started + timedelta(hours=0, minutes=45 + i * 5)
            consents_data.append({
                "id": f"PC-{consent_counter:04d}",
                "patient_id": pid,
                "trial_id": EYLEA_TRIAL,
                "document_id": "CDOC-001",
                "site_id": site,
                "status": ConsentStatus.RE_CONSENTED,
                "started_at": started,
                "completed_at": completed,
                "signature_date": completed,
                "witness_name": f"Dr. Re-Witness {i + 1}",
                "witness_signature_date": completed + timedelta(minutes=5),
                "ip_address": f"192.168.2.{50 + i}",
                "device_info": "Chrome 121 / Windows 11",
                "time_spent_minutes": 20.0 + i * 2.0,
                "quiz_score": 90.0 + i * 3.0,
                "elements_viewed": [f"EL-001-0{j}" for j in range(1, 9)],
                "elements_completed": [f"EL-001-0{j}" for j in range(1, 9)],
                "re_consent_reason": "Protocol Amendment 3 - Updated dosing schedule",
            })

        # 4 not_started
        for i in range(4):
            consent_counter += 1
            pid = patient_ids[30 + i]
            site = sites[i % len(sites)]
            consents_data.append({
                "id": f"PC-{consent_counter:04d}",
                "patient_id": pid,
                "trial_id": LIBTAYO_TRIAL,
                "document_id": "CDOC-003",
                "site_id": site,
                "status": ConsentStatus.NOT_STARTED,
                "started_at": None,
                "completed_at": None,
                "signature_date": None,
                "witness_name": None,
                "witness_signature_date": None,
                "ip_address": None,
                "device_info": None,
                "time_spent_minutes": None,
                "quiz_score": None,
                "elements_viewed": [],
                "elements_completed": [],
                "re_consent_reason": None,
            })

        # 3 expired consents
        for i in range(3):
            consent_counter += 1
            pid = patient_ids[34 + i]
            site = sites[i % len(sites)]
            started = now - timedelta(days=400 - i * 10)
            completed = started + timedelta(hours=2)
            consents_data.append({
                "id": f"PC-{consent_counter:04d}",
                "patient_id": pid,
                "trial_id": EYLEA_TRIAL,
                "document_id": "CDOC-001",
                "site_id": site,
                "status": ConsentStatus.EXPIRED,
                "started_at": started,
                "completed_at": completed,
                "signature_date": completed,
                "witness_name": f"Dr. Old Witness {i + 1}",
                "witness_signature_date": completed + timedelta(minutes=5),
                "ip_address": f"192.168.3.{60 + i}",
                "device_info": "Chrome 115 / Windows 10",
                "time_spent_minutes": 35.0 + i * 3.0,
                "quiz_score": 85.0 + i * 2.0,
                "elements_viewed": [f"EL-001-0{j}" for j in range(1, 9)],
                "elements_completed": [f"EL-001-0{j}" for j in range(1, 9)],
                "re_consent_reason": None,
            })

        for c in consents_data:
            self._consents[c["id"]] = PatientConsent(**c)

        # --- 5 Withdrawal Records ---
        withdrawals_data = [
            {
                "id": "WD-001",
                "patient_consent_id": "PC-0005",
                "patient_id": "PAT-0005",
                "withdrawal_date": now - timedelta(days=50),
                "reason": "Personal reasons - relocation to another state",
                "data_retention_preference": DataRetentionPreference.RETAIN_ANONYMIZED,
                "specimens_disposition": "Destroy all biological samples",
                "acknowledged_by": "Dr. Sarah Mitchell",
            },
            {
                "id": "WD-002",
                "patient_consent_id": "PC-0010",
                "patient_id": "PAT-0010",
                "withdrawal_date": now - timedelta(days=35),
                "reason": "Adverse events - decided to discontinue participation",
                "data_retention_preference": DataRetentionPreference.RETAIN_IDENTIFIED,
                "specimens_disposition": "Retain for safety analysis only",
                "acknowledged_by": "Dr. David Park",
            },
            {
                "id": "WD-003",
                "patient_consent_id": "PC-0018",
                "patient_id": "PAT-0018",
                "withdrawal_date": now - timedelta(days=20),
                "reason": "Family decision - concerns about study procedures",
                "data_retention_preference": DataRetentionPreference.DELETE_ALL,
                "specimens_disposition": "Destroy all samples and data",
                "acknowledged_by": "Dr. Jennifer Lee",
            },
            {
                "id": "WD-004",
                "patient_consent_id": "PC-0022",
                "patient_id": "PAT-0022",
                "withdrawal_date": now - timedelta(days=10),
                "reason": "Alternative treatment available outside of trial",
                "data_retention_preference": DataRetentionPreference.RETAIN_ANONYMIZED,
                "specimens_disposition": "Return samples to patient if possible",
                "acknowledged_by": "Dr. Sarah Mitchell",
            },
            {
                "id": "WD-005",
                "patient_consent_id": "PC-0025",
                "patient_id": "PAT-0025",
                "withdrawal_date": now - timedelta(days=5),
                "reason": "Transportation difficulties preventing visit attendance",
                "data_retention_preference": DataRetentionPreference.RETAIN_IDENTIFIED,
                "specimens_disposition": None,
                "acknowledged_by": None,
            },
        ]

        for w in withdrawals_data:
            self._withdrawals[w["id"]] = ConsentWithdrawal(**w)

        # Update withdrawal consent statuses
        for wd in withdrawals_data:
            pc_id = wd["patient_consent_id"]
            if pc_id in self._consents:
                data = self._consents[pc_id].model_dump()
                data["status"] = ConsentStatus.WITHDRAWN
                self._consents[pc_id] = PatientConsent(**data)

        # --- 60 Audit Trail Entries ---
        audit_counter = 0
        for consent_id, consent in self._consents.items():
            # "viewed" entry for every consent that has started
            if consent.started_at:
                audit_counter += 1
                self._audit_entries[f"AUD-{audit_counter:04d}"] = ConsentAuditEntry(
                    id=f"AUD-{audit_counter:04d}",
                    patient_consent_id=consent_id,
                    action=ConsentAuditAction.VIEWED,
                    timestamp=consent.started_at,
                    ip_address=consent.ip_address,
                    details=f"Patient began consent review for document {consent.document_id}",
                )

            # "signed" entry for signed/re-consented consents
            if consent.status in (ConsentStatus.SIGNED, ConsentStatus.RE_CONSENTED) and consent.signature_date:
                audit_counter += 1
                self._audit_entries[f"AUD-{audit_counter:04d}"] = ConsentAuditEntry(
                    id=f"AUD-{audit_counter:04d}",
                    patient_consent_id=consent_id,
                    action=ConsentAuditAction.SIGNED,
                    timestamp=consent.signature_date,
                    ip_address=consent.ip_address,
                    details=f"Patient signed consent. Quiz score: {consent.quiz_score}%",
                )

            # "re_consented" entry for re-consented
            if consent.status == ConsentStatus.RE_CONSENTED and consent.signature_date:
                audit_counter += 1
                self._audit_entries[f"AUD-{audit_counter:04d}"] = ConsentAuditEntry(
                    id=f"AUD-{audit_counter:04d}",
                    patient_consent_id=consent_id,
                    action=ConsentAuditAction.RE_CONSENTED,
                    timestamp=consent.signature_date + timedelta(seconds=30),
                    ip_address=consent.ip_address,
                    details=f"Re-consent completed. Reason: {consent.re_consent_reason}",
                )

            # "withdrawn" entry for withdrawn consents
            if consent.status == ConsentStatus.WITHDRAWN:
                wd = next(
                    (w for w in self._withdrawals.values() if w.patient_consent_id == consent_id),
                    None,
                )
                if wd:
                    audit_counter += 1
                    self._audit_entries[f"AUD-{audit_counter:04d}"] = ConsentAuditEntry(
                        id=f"AUD-{audit_counter:04d}",
                        patient_consent_id=consent_id,
                        action=ConsentAuditAction.WITHDRAWN,
                        timestamp=wd.withdrawal_date,
                        ip_address=consent.ip_address,
                        details=f"Consent withdrawn. Reason: {wd.reason}. Data pref: {wd.data_retention_preference.value}",
                    )

            if audit_counter >= 60:
                break

    # ------------------------------------------------------------------
    # Document Management
    # ------------------------------------------------------------------

    def list_documents(
        self,
        *,
        trial_id: str | None = None,
        consent_type: ConsentType | None = None,
        language: DocumentLanguage | None = None,
    ) -> list[ConsentDocument]:
        """List consent documents with optional filters."""
        with self._lock:
            result = list(self._documents.values())

        if trial_id is not None:
            result = [d for d in result if d.trial_id == trial_id]
        if consent_type is not None:
            result = [d for d in result if d.consent_type == consent_type]
        if language is not None:
            result = [d for d in result if d.language == language]

        return sorted(result, key=lambda d: d.id)

    def get_document(self, document_id: str) -> ConsentDocument | None:
        """Get a single consent document by ID."""
        with self._lock:
            return self._documents.get(document_id)

    def create_document(self, payload: ConsentDocumentCreate) -> ConsentDocument:
        """Create a new consent document."""
        doc_id = f"CDOC-{uuid4().hex[:8].upper()}"
        doc = ConsentDocument(
            id=doc_id,
            trial_id=payload.trial_id,
            version=payload.version,
            title=payload.title,
            consent_type=payload.consent_type,
            effective_date=payload.effective_date,
            language=payload.language,
            elements=[],
            irb_approval_date=payload.irb_approval_date,
            total_pages=payload.total_pages,
            estimated_read_time_minutes=payload.estimated_read_time_minutes,
        )
        with self._lock:
            self._documents[doc_id] = doc
        logger.info("Created consent document %s: %s", doc_id, payload.title)
        return doc

    def update_document(self, document_id: str, payload: ConsentDocumentUpdate) -> ConsentDocument | None:
        """Update an existing consent document."""
        with self._lock:
            existing = self._documents.get(document_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ConsentDocument(**data)
            self._documents[document_id] = updated
        return updated

    def delete_document(self, document_id: str) -> bool:
        """Delete a consent document. Returns True if deleted."""
        with self._lock:
            if document_id in self._documents:
                del self._documents[document_id]
                return True
            return False

    def add_element_to_document(
        self, document_id: str, payload: ConsentElementCreate
    ) -> ConsentDocument | None:
        """Add an element to a consent document."""
        with self._lock:
            existing = self._documents.get(document_id)
            if existing is None:
                return None
            element_id = f"EL-{document_id.split('-')[1]}-{uuid4().hex[:4].upper()}"
            element = ConsentElement(
                id=element_id,
                element_type=payload.element_type,
                page_number=payload.page_number,
                content_summary=payload.content_summary,
                required=payload.required,
                quiz_question=payload.quiz_question,
                quiz_correct_answer=payload.quiz_correct_answer,
                quiz_options=payload.quiz_options,
            )
            data = existing.model_dump()
            data["elements"].append(element.model_dump())
            updated = ConsentDocument(**data)
            self._documents[document_id] = updated
        return updated

    # ------------------------------------------------------------------
    # Patient Consent Management
    # ------------------------------------------------------------------

    def list_consents(
        self,
        *,
        patient_id: str | None = None,
        trial_id: str | None = None,
        site_id: str | None = None,
        status: ConsentStatus | None = None,
        document_id: str | None = None,
    ) -> list[PatientConsent]:
        """List patient consents with optional filters."""
        with self._lock:
            result = list(self._consents.values())

        if patient_id is not None:
            result = [c for c in result if c.patient_id == patient_id]
        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if site_id is not None:
            result = [c for c in result if c.site_id == site_id]
        if status is not None:
            result = [c for c in result if c.status == status]
        if document_id is not None:
            result = [c for c in result if c.document_id == document_id]

        return sorted(result, key=lambda c: c.id)

    def get_consent(self, consent_id: str) -> PatientConsent | None:
        """Get a single patient consent by ID."""
        with self._lock:
            return self._consents.get(consent_id)

    def create_consent(self, payload: PatientConsentCreate) -> PatientConsent:
        """Create a new patient consent record."""
        consent_id = f"PC-{uuid4().hex[:8].upper()}"
        consent = PatientConsent(
            id=consent_id,
            patient_id=payload.patient_id,
            trial_id=payload.trial_id,
            document_id=payload.document_id,
            site_id=payload.site_id,
            status=ConsentStatus.NOT_STARTED,
        )
        with self._lock:
            self._consents[consent_id] = consent
        logger.info("Created patient consent %s for patient %s", consent_id, payload.patient_id)
        return consent

    def update_consent(self, consent_id: str, payload: PatientConsentUpdate) -> PatientConsent | None:
        """Update a patient consent record."""
        with self._lock:
            existing = self._consents.get(consent_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = PatientConsent(**data)
            self._consents[consent_id] = updated
        return updated

    def sign_consent(self, consent_id: str, payload: ConsentSignRequest) -> PatientConsent | None:
        """Sign a patient consent with 21 CFR Part 11 compliance.

        Validates quiz answers, records signature metadata, creates audit trail.
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._consents.get(consent_id)
            if existing is None:
                return None

            if existing.status == ConsentStatus.SIGNED:
                raise ValueError(f"Consent '{consent_id}' is already signed")

            if existing.status == ConsentStatus.WITHDRAWN:
                raise ValueError(f"Consent '{consent_id}' has been withdrawn")

            # Get document for quiz validation
            doc = self._documents.get(existing.document_id)

            # Calculate quiz score if answers provided
            quiz_score = None
            if payload.quiz_answers and doc:
                quiz_elements = [
                    e for e in doc.elements
                    if e.element_type == ConsentElementType.QUIZ and e.quiz_correct_answer
                ]
                if quiz_elements:
                    correct = 0
                    total = len(quiz_elements)
                    for qe in quiz_elements:
                        answer = payload.quiz_answers.get(qe.id)
                        if answer and answer == qe.quiz_correct_answer:
                            correct += 1
                    quiz_score = round((correct / total) * 100, 1) if total > 0 else 0.0

                    if quiz_score < QUIZ_PASS_THRESHOLD:
                        raise ValueError(
                            f"Quiz score {quiz_score}% is below the required {QUIZ_PASS_THRESHOLD}% threshold"
                        )

            # Determine if this is a re-consent
            is_reconsent = existing.re_consent_reason is not None
            new_status = ConsentStatus.RE_CONSENTED if is_reconsent else ConsentStatus.SIGNED

            data = existing.model_dump()
            data["status"] = new_status
            data["signature_date"] = now
            data["completed_at"] = now
            data["ip_address"] = payload.ip_address
            data["device_info"] = payload.device_info
            data["witness_name"] = payload.witness_name
            if payload.witness_name:
                data["witness_signature_date"] = now
            if quiz_score is not None:
                data["quiz_score"] = quiz_score

            # Calculate time spent if started_at exists
            if existing.started_at:
                delta = now - existing.started_at
                data["time_spent_minutes"] = round(delta.total_seconds() / 60, 1)

            updated = PatientConsent(**data)
            self._consents[consent_id] = updated

            # Create audit entry
            audit_action = ConsentAuditAction.RE_CONSENTED if is_reconsent else ConsentAuditAction.SIGNED
            audit_id = f"AUD-{uuid4().hex[:8].upper()}"
            audit = ConsentAuditEntry(
                id=audit_id,
                patient_consent_id=consent_id,
                action=audit_action,
                timestamp=now,
                ip_address=payload.ip_address,
                details=f"Consent {'re-' if is_reconsent else ''}signed. Quiz score: {quiz_score}%"
                if quiz_score is not None
                else f"Consent {'re-' if is_reconsent else ''}signed. No quiz required.",
            )
            self._audit_entries[audit_id] = audit

        logger.info(
            "Consent %s signed by patient %s (quiz_score=%s)",
            consent_id, existing.patient_id, quiz_score,
        )
        return updated

    def view_element(self, consent_id: str, payload: ViewElementRequest) -> PatientConsent | None:
        """Record that a patient has viewed a consent element."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._consents.get(consent_id)
            if existing is None:
                return None

            data = existing.model_dump()

            # Start the consent if not_started
            if existing.status == ConsentStatus.NOT_STARTED:
                data["status"] = ConsentStatus.IN_PROGRESS
                data["started_at"] = now

            # Add to viewed list if not already there
            if payload.element_id not in data["elements_viewed"]:
                data["elements_viewed"].append(payload.element_id)

            updated = PatientConsent(**data)
            self._consents[consent_id] = updated

            # Audit entry
            audit_id = f"AUD-{uuid4().hex[:8].upper()}"
            self._audit_entries[audit_id] = ConsentAuditEntry(
                id=audit_id,
                patient_consent_id=consent_id,
                action=ConsentAuditAction.VIEWED,
                timestamp=now,
                ip_address=existing.ip_address,
                details=f"Viewed element {payload.element_id}",
            )

        return updated

    def complete_element(self, consent_id: str, payload: CompleteElementRequest) -> PatientConsent | None:
        """Record that a patient has completed a consent element (checkbox, quiz, etc.)."""
        with self._lock:
            existing = self._consents.get(consent_id)
            if existing is None:
                return None

            data = existing.model_dump()
            if payload.element_id not in data["elements_completed"]:
                data["elements_completed"].append(payload.element_id)

            updated = PatientConsent(**data)
            self._consents[consent_id] = updated

        return updated

    # ------------------------------------------------------------------
    # Withdrawal Management
    # ------------------------------------------------------------------

    def list_withdrawals(
        self,
        *,
        patient_id: str | None = None,
    ) -> list[ConsentWithdrawal]:
        """List consent withdrawals with optional patient filter."""
        with self._lock:
            result = list(self._withdrawals.values())

        if patient_id is not None:
            result = [w for w in result if w.patient_id == patient_id]

        return sorted(result, key=lambda w: w.withdrawal_date, reverse=True)

    def get_withdrawal(self, withdrawal_id: str) -> ConsentWithdrawal | None:
        """Get a single withdrawal by ID."""
        with self._lock:
            return self._withdrawals.get(withdrawal_id)

    def withdraw_consent(
        self, consent_id: str, payload: ConsentWithdrawalCreate
    ) -> ConsentWithdrawal | None:
        """Withdraw a patient's consent."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._consents.get(consent_id)
            if existing is None:
                return None

            if existing.status == ConsentStatus.WITHDRAWN:
                raise ValueError(f"Consent '{consent_id}' is already withdrawn")

            # Update consent status
            data = existing.model_dump()
            data["status"] = ConsentStatus.WITHDRAWN
            updated_consent = PatientConsent(**data)
            self._consents[consent_id] = updated_consent

            # Create withdrawal record
            wd_id = f"WD-{uuid4().hex[:8].upper()}"
            withdrawal = ConsentWithdrawal(
                id=wd_id,
                patient_consent_id=consent_id,
                patient_id=existing.patient_id,
                withdrawal_date=now,
                reason=payload.reason,
                data_retention_preference=payload.data_retention_preference,
                specimens_disposition=payload.specimens_disposition,
                acknowledged_by=None,
            )
            self._withdrawals[wd_id] = withdrawal

            # Audit entry
            audit_id = f"AUD-{uuid4().hex[:8].upper()}"
            self._audit_entries[audit_id] = ConsentAuditEntry(
                id=audit_id,
                patient_consent_id=consent_id,
                action=ConsentAuditAction.WITHDRAWN,
                timestamp=now,
                ip_address=existing.ip_address,
                details=f"Withdrawn: {payload.reason}. Data pref: {payload.data_retention_preference.value}",
            )

        logger.info(
            "Consent %s withdrawn for patient %s. Reason: %s",
            consent_id, existing.patient_id, payload.reason,
        )
        return withdrawal

    # ------------------------------------------------------------------
    # Audit Trail
    # ------------------------------------------------------------------

    def list_audit_entries(
        self,
        *,
        patient_consent_id: str | None = None,
        action: ConsentAuditAction | None = None,
    ) -> list[ConsentAuditEntry]:
        """List audit entries with optional filters."""
        with self._lock:
            result = list(self._audit_entries.values())

        if patient_consent_id is not None:
            result = [a for a in result if a.patient_consent_id == patient_consent_id]
        if action is not None:
            result = [a for a in result if a.action == action]

        return sorted(result, key=lambda a: a.timestamp, reverse=True)

    def get_audit_entry(self, audit_id: str) -> ConsentAuditEntry | None:
        """Get a single audit entry by ID."""
        with self._lock:
            return self._audit_entries.get(audit_id)

    # ------------------------------------------------------------------
    # Comprehension Analytics
    # ------------------------------------------------------------------

    def get_comprehension_analytics(
        self,
        *,
        trial_id: str | None = None,
    ) -> ComprehensionAnalytics:
        """Get comprehension analytics for quiz performance."""
        with self._lock:
            consents = list(self._consents.values())

        if trial_id is not None:
            consents = [c for c in consents if c.trial_id == trial_id]

        # Filter consents with quiz scores
        scored = [c for c in consents if c.quiz_score is not None]
        total_quizzes = len(scored)

        if total_quizzes == 0:
            return ComprehensionAnalytics(
                total_quizzes_taken=0,
                avg_score=0.0,
                pass_rate=0.0,
                score_distribution={},
                avg_time_spent_minutes=0.0,
                elements_with_lowest_completion=[],
            )

        scores = [c.quiz_score for c in scored if c.quiz_score is not None]
        avg_score = round(sum(scores) / len(scores), 1)
        passing = sum(1 for s in scores if s >= QUIZ_PASS_THRESHOLD)
        pass_rate = round((passing / total_quizzes) * 100, 1)

        # Score distribution buckets
        distribution: dict[str, int] = {
            "0-59": 0,
            "60-69": 0,
            "70-79": 0,
            "80-89": 0,
            "90-100": 0,
        }
        for s in scores:
            if s < 60:
                distribution["0-59"] += 1
            elif s < 70:
                distribution["60-69"] += 1
            elif s < 80:
                distribution["70-79"] += 1
            elif s < 90:
                distribution["80-89"] += 1
            else:
                distribution["90-100"] += 1

        # Average time spent
        times = [c.time_spent_minutes for c in scored if c.time_spent_minutes is not None]
        avg_time = round(sum(times) / len(times), 1) if times else 0.0

        return ComprehensionAnalytics(
            total_quizzes_taken=total_quizzes,
            avg_score=avg_score,
            pass_rate=pass_rate,
            score_distribution=distribution,
            avg_time_spent_minutes=avg_time,
            elements_with_lowest_completion=[],
        )

    # ------------------------------------------------------------------
    # Re-consent Management
    # ------------------------------------------------------------------

    def get_re_consent_pending(self, trial_id: str | None = None) -> list[PatientConsent]:
        """Get patients who need re-consent due to protocol amendments.

        Returns signed consents for documents that have newer versions.
        """
        with self._lock:
            consents = list(self._consents.values())
            docs = list(self._documents.values())

        if trial_id is not None:
            consents = [c for c in consents if c.trial_id == trial_id]

        # Find documents with multiple versions
        doc_versions: dict[str, list[str]] = {}
        for doc in docs:
            key = f"{doc.trial_id}:{doc.consent_type.value}"
            if key not in doc_versions:
                doc_versions[key] = []
            doc_versions[key].append(doc.version)

        # Find signed consents that may need re-consent
        pending: list[PatientConsent] = []
        for c in consents:
            if c.status == ConsentStatus.SIGNED and c.re_consent_reason is None:
                doc = next((d for d in docs if d.id == c.document_id), None)
                if doc:
                    key = f"{doc.trial_id}:{doc.consent_type.value}"
                    versions = doc_versions.get(key, [])
                    if len(versions) > 1 and doc.version != max(versions):
                        pending.append(c)

        return pending

    # ------------------------------------------------------------------
    # Metrics & Dashboard
    # ------------------------------------------------------------------

    def get_metrics(self) -> EConsentMetrics:
        """Compute aggregated eConsent operational metrics."""
        with self._lock:
            documents = list(self._documents.values())
            consents = list(self._consents.values())
            withdrawals = list(self._withdrawals.values())

        # Consents by status
        status_counts: dict[str, int] = {}
        for c in consents:
            key = c.status.value
            status_counts[key] = status_counts.get(key, 0) + 1

        # Average completion time
        completed = [
            c for c in consents
            if c.time_spent_minutes is not None
            and c.status in (ConsentStatus.SIGNED, ConsentStatus.RE_CONSENTED)
        ]
        avg_time = (
            round(sum(c.time_spent_minutes for c in completed) / len(completed), 1)  # type: ignore[arg-type]
            if completed
            else 0.0
        )

        # Average quiz score
        scored = [c for c in consents if c.quiz_score is not None]
        avg_quiz = (
            round(sum(c.quiz_score for c in scored) / len(scored), 1)  # type: ignore[arg-type]
            if scored
            else 0.0
        )

        # Withdrawal rate
        total_signed = sum(
            1 for c in consents
            if c.status in (ConsentStatus.SIGNED, ConsentStatus.RE_CONSENTED, ConsentStatus.WITHDRAWN)
        )
        withdrawal_rate = (
            round((len(withdrawals) / total_signed) * 100, 1)
            if total_signed > 0
            else 0.0
        )

        # Re-consent pending
        re_consent_pending = len(self.get_re_consent_pending())

        # Language distribution
        lang_dist: dict[str, int] = {}
        for doc in documents:
            key = doc.language.value
            # Count consents using documents of this language
            doc_consents = sum(1 for c in consents if c.document_id == doc.id)
            lang_dist[key] = lang_dist.get(key, 0) + doc_consents

        return EConsentMetrics(
            total_documents=len(documents),
            total_consents=len(consents),
            consents_by_status=status_counts,
            avg_completion_time_minutes=avg_time,
            avg_quiz_score=avg_quiz,
            withdrawal_rate=withdrawal_rate,
            re_consent_pending=re_consent_pending,
            language_distribution=lang_dist,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: EConsentService | None = None
_instance_lock = threading.Lock()


def get_econsent_service() -> EConsentService:
    """Return the singleton EConsentService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = EConsentService()
    return _instance


def reset_econsent_service() -> EConsentService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = EConsentService()
    return _instance
