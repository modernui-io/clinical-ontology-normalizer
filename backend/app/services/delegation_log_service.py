"""Delegation Log Service (DELEG-LOG).

Manages delegation of authority operations: delegation entries, authority
records, training verifications, delegation audits, and delegation metrics.

Usage:
    from app.services.delegation_log_service import (
        get_delegation_log_service,
    )

    svc = get_delegation_log_service()
    entries = svc.list_delegation_entries()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.delegation_log import (
    AuditResult,
    AuthorityLevel,
    AuthorityRecord,
    AuthorityRecordCreate,
    AuthorityRecordUpdate,
    DelegationAudit,
    DelegationAuditCreate,
    DelegationAuditUpdate,
    DelegationCategory,
    DelegationEntry,
    DelegationEntryCreate,
    DelegationEntryUpdate,
    DelegationLogMetrics,
    DelegationStatus,
    TrainingStatus,
    TrainingVerification,
    TrainingVerificationCreate,
    TrainingVerificationUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Trial IDs matching trial_eligibility_service
EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class DelegationLogService:
    """In-memory Delegation Log engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._delegation_entries: dict[str, DelegationEntry] = {}
        self._authority_records: dict[str, AuthorityRecord] = {}
        self._training_verifications: dict[str, TrainingVerification] = {}
        self._delegation_audits: dict[str, DelegationAudit] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic delegation log data."""
        now = datetime.now(timezone.utc)

        # --- 12 Delegation Entries ---
        entries_data = [
            {
                "id": "DEL-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "delegator_name": "Dr. Sarah Mitchell",
                "delegate_name": "Dr. James Chen",
                "delegation_category": DelegationCategory.INFORMED_CONSENT,
                "delegation_status": DelegationStatus.ACTIVE,
                "authority_level": AuthorityLevel.SUB_INVESTIGATOR,
                "effective_date": now - timedelta(days=180),
                "expiry_date": now + timedelta(days=185),
                "specific_tasks": ["Obtain informed consent", "Explain study procedures"],
                "restrictions": None,
                "approved_by": "Dr. Sarah Mitchell",
                "notes": "Sub-investigator delegated for informed consent process.",
                "created_at": now - timedelta(days=181),
            },
            {
                "id": "DEL-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "delegator_name": "Dr. Sarah Mitchell",
                "delegate_name": "Nurse Patricia Wells",
                "delegation_category": DelegationCategory.LAB_ASSESSMENTS,
                "delegation_status": DelegationStatus.ACTIVE,
                "authority_level": AuthorityLevel.NURSE,
                "effective_date": now - timedelta(days=170),
                "expiry_date": now + timedelta(days=195),
                "specific_tasks": ["Collect blood samples", "Process lab specimens"],
                "restrictions": "Must follow central lab manual",
                "approved_by": "Dr. Sarah Mitchell",
                "notes": "Nurse delegated for laboratory assessments.",
                "created_at": now - timedelta(days=171),
            },
            {
                "id": "DEL-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "delegator_name": "Dr. Sarah Mitchell",
                "delegate_name": "Pharmacist Robert Kim",
                "delegation_category": DelegationCategory.DISPENSING_IP,
                "delegation_status": DelegationStatus.ACTIVE,
                "authority_level": AuthorityLevel.PHARMACIST,
                "effective_date": now - timedelta(days=160),
                "expiry_date": None,
                "specific_tasks": ["Dispense investigational product", "Maintain IP accountability"],
                "restrictions": "Unblinded pharmacist only",
                "approved_by": "Dr. Sarah Mitchell",
                "notes": "Pharmacist delegated for IP dispensing at LA site.",
                "created_at": now - timedelta(days=161),
            },
            {
                "id": "DEL-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "delegator_name": "Dr. Sarah Mitchell",
                "delegate_name": "Coordinator Amy Lin",
                "delegation_category": DelegationCategory.DATA_ENTRY,
                "delegation_status": DelegationStatus.EXPIRED,
                "authority_level": AuthorityLevel.STUDY_COORDINATOR,
                "effective_date": now - timedelta(days=365),
                "expiry_date": now - timedelta(days=5),
                "specific_tasks": ["Enter CRF data", "Resolve queries"],
                "restrictions": None,
                "approved_by": "Dr. Sarah Mitchell",
                "notes": "Delegation expired. Renewal pending re-training.",
                "created_at": now - timedelta(days=366),
            },
            {
                "id": "DEL-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "delegator_name": "Dr. Michael Torres",
                "delegate_name": "Dr. Karen Liu",
                "delegation_category": DelegationCategory.PHYSICAL_EXAMINATION,
                "delegation_status": DelegationStatus.ACTIVE,
                "authority_level": AuthorityLevel.SUB_INVESTIGATOR,
                "effective_date": now - timedelta(days=150),
                "expiry_date": now + timedelta(days=215),
                "specific_tasks": ["Perform physical examinations", "Assess vital signs"],
                "restrictions": None,
                "approved_by": "Dr. Michael Torres",
                "notes": "Sub-investigator delegated for physical exams.",
                "created_at": now - timedelta(days=151),
            },
            {
                "id": "DEL-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "delegator_name": "Dr. Michael Torres",
                "delegate_name": "Coordinator Rachel Green",
                "delegation_category": DelegationCategory.ADVERSE_EVENT_REPORTING,
                "delegation_status": DelegationStatus.ACTIVE,
                "authority_level": AuthorityLevel.STUDY_COORDINATOR,
                "effective_date": now - timedelta(days=140),
                "expiry_date": now + timedelta(days=225),
                "specific_tasks": ["Document adverse events", "Submit SAE reports"],
                "restrictions": "PI must review all SAEs within 24 hours",
                "approved_by": "Dr. Michael Torres",
                "notes": "Coordinator delegated for AE reporting with PI oversight.",
                "created_at": now - timedelta(days=141),
            },
            {
                "id": "DEL-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "delegator_name": "Dr. Michael Torres",
                "delegate_name": "Lab Tech Rachel Green",
                "delegation_category": DelegationCategory.LAB_ASSESSMENTS,
                "delegation_status": DelegationStatus.REVOKED,
                "authority_level": AuthorityLevel.LAB_TECHNICIAN,
                "effective_date": now - timedelta(days=200),
                "expiry_date": now - timedelta(days=30),
                "specific_tasks": ["Process lab specimens"],
                "restrictions": None,
                "approved_by": "Dr. Michael Torres",
                "notes": "Revoked due to personnel change.",
                "created_at": now - timedelta(days=201),
            },
            {
                "id": "DEL-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "delegator_name": "Dr. Michael Torres",
                "delegate_name": "Nurse Karen Liu",
                "delegation_category": DelegationCategory.DATA_ENTRY,
                "delegation_status": DelegationStatus.SUSPENDED,
                "authority_level": AuthorityLevel.NURSE,
                "effective_date": now - timedelta(days=120),
                "expiry_date": now + timedelta(days=245),
                "specific_tasks": ["Enter CRF data"],
                "restrictions": "Pending GCP re-certification",
                "approved_by": "Dr. Michael Torres",
                "notes": "Suspended pending completion of GCP re-training.",
                "created_at": now - timedelta(days=121),
            },
            {
                "id": "DEL-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "delegator_name": "Dr. Angela Martinez",
                "delegate_name": "Dr. David Park",
                "delegation_category": DelegationCategory.INFORMED_CONSENT,
                "delegation_status": DelegationStatus.ACTIVE,
                "authority_level": AuthorityLevel.SUB_INVESTIGATOR,
                "effective_date": now - timedelta(days=130),
                "expiry_date": now + timedelta(days=235),
                "specific_tasks": ["Obtain informed consent", "Explain risks and benefits"],
                "restrictions": None,
                "approved_by": "Dr. Angela Martinez",
                "notes": "Sub-investigator delegated for consent at Houston site.",
                "created_at": now - timedelta(days=131),
            },
            {
                "id": "DEL-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "delegator_name": "Dr. Angela Martinez",
                "delegate_name": "Pharmacist Tom Bradley",
                "delegation_category": DelegationCategory.DISPENSING_IP,
                "delegation_status": DelegationStatus.PENDING_APPROVAL,
                "authority_level": AuthorityLevel.PHARMACIST,
                "effective_date": now - timedelta(days=10),
                "expiry_date": None,
                "specific_tasks": ["Dispense IP", "Record accountability logs"],
                "restrictions": None,
                "approved_by": "Dr. Angela Martinez",
                "notes": "Pending IRB approval for delegation.",
                "created_at": now - timedelta(days=11),
            },
            {
                "id": "DEL-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "delegator_name": "Dr. Angela Martinez",
                "delegate_name": "Coordinator Amy Chen",
                "delegation_category": DelegationCategory.ADVERSE_EVENT_REPORTING,
                "delegation_status": DelegationStatus.SUPERSEDED,
                "authority_level": AuthorityLevel.STUDY_COORDINATOR,
                "effective_date": now - timedelta(days=300),
                "expiry_date": now - timedelta(days=60),
                "specific_tasks": ["Document adverse events"],
                "restrictions": None,
                "approved_by": "Dr. Angela Martinez",
                "notes": "Superseded by updated delegation log v2.",
                "created_at": now - timedelta(days=301),
            },
            {
                "id": "DEL-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "delegator_name": "Dr. Angela Martinez",
                "delegate_name": "Nurse Sarah Kim",
                "delegation_category": DelegationCategory.PHYSICAL_EXAMINATION,
                "delegation_status": DelegationStatus.ACTIVE,
                "authority_level": AuthorityLevel.NURSE,
                "effective_date": now - timedelta(days=100),
                "expiry_date": now + timedelta(days=265),
                "specific_tasks": ["Assist with physical examinations", "Record vital signs"],
                "restrictions": "Under physician supervision only",
                "approved_by": "Dr. Angela Martinez",
                "notes": "Nurse delegated for physical exams under supervision.",
                "created_at": now - timedelta(days=101),
            },
        ]

        for e in entries_data:
            self._delegation_entries[e["id"]] = DelegationEntry(**e)

        # --- 12 Authority Records ---
        authority_data = [
            {
                "id": "AUTH-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "person_name": "Dr. Sarah Mitchell",
                "authority_level": AuthorityLevel.PRINCIPAL_INVESTIGATOR,
                "license_number": "NY-MD-2015-44821",
                "credential_type": "Medical License",
                "credential_expiry": now + timedelta(days=400),
                "is_qualified": True,
                "qualifications": ["Board Certified Ophthalmologist", "GCP Certified"],
                "supervision_required": False,
                "supervisor_name": None,
                "verified_by": "CRA Jennifer Adams",
                "verified_date": now - timedelta(days=180),
                "notes": "Principal Investigator for EYLEA trial.",
                "created_at": now - timedelta(days=181),
            },
            {
                "id": "AUTH-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "person_name": "Dr. James Chen",
                "authority_level": AuthorityLevel.SUB_INVESTIGATOR,
                "license_number": "NY-MD-2018-55932",
                "credential_type": "Medical License",
                "credential_expiry": now + timedelta(days=350),
                "is_qualified": True,
                "qualifications": ["Ophthalmology Fellow", "GCP Certified"],
                "supervision_required": False,
                "supervisor_name": None,
                "verified_by": "CRA Jennifer Adams",
                "verified_date": now - timedelta(days=175),
                "notes": "Sub-investigator qualified for consent and assessments.",
                "created_at": now - timedelta(days=176),
            },
            {
                "id": "AUTH-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "person_name": "Nurse Patricia Wells",
                "authority_level": AuthorityLevel.NURSE,
                "license_number": "NY-RN-2012-33210",
                "credential_type": "Nursing License",
                "credential_expiry": now + timedelta(days=500),
                "is_qualified": True,
                "qualifications": ["Registered Nurse", "Phlebotomy Certified", "GCP Trained"],
                "supervision_required": False,
                "supervisor_name": None,
                "verified_by": "CRA Jennifer Adams",
                "verified_date": now - timedelta(days=170),
                "notes": "Qualified for lab assessments and specimen collection.",
                "created_at": now - timedelta(days=171),
            },
            {
                "id": "AUTH-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "person_name": "Pharmacist Robert Kim",
                "authority_level": AuthorityLevel.PHARMACIST,
                "license_number": "CA-RPH-2016-78543",
                "credential_type": "Pharmacy License",
                "credential_expiry": now + timedelta(days=300),
                "is_qualified": True,
                "qualifications": ["Registered Pharmacist", "IP Management Trained"],
                "supervision_required": False,
                "supervisor_name": None,
                "verified_by": "CRA Mark Wilson",
                "verified_date": now - timedelta(days=160),
                "notes": "Unblinded pharmacist for IP dispensing.",
                "created_at": now - timedelta(days=161),
            },
            {
                "id": "AUTH-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "person_name": "Dr. Michael Torres",
                "authority_level": AuthorityLevel.PRINCIPAL_INVESTIGATOR,
                "license_number": "IL-MD-2010-22198",
                "credential_type": "Medical License",
                "credential_expiry": now + timedelta(days=450),
                "is_qualified": True,
                "qualifications": ["Board Certified Dermatologist", "GCP Certified"],
                "supervision_required": False,
                "supervisor_name": None,
                "verified_by": "CRA Lisa Park",
                "verified_date": now - timedelta(days=150),
                "notes": "Principal Investigator for DUPIXENT trial.",
                "created_at": now - timedelta(days=151),
            },
            {
                "id": "AUTH-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "person_name": "Dr. Karen Liu",
                "authority_level": AuthorityLevel.SUB_INVESTIGATOR,
                "license_number": "IL-MD-2017-44876",
                "credential_type": "Medical License",
                "credential_expiry": now + timedelta(days=380),
                "is_qualified": True,
                "qualifications": ["Dermatology Resident", "GCP Certified"],
                "supervision_required": True,
                "supervisor_name": "Dr. Michael Torres",
                "verified_by": "CRA Lisa Park",
                "verified_date": now - timedelta(days=145),
                "notes": "Sub-investigator under PI supervision.",
                "created_at": now - timedelta(days=146),
            },
            {
                "id": "AUTH-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "person_name": "Coordinator Rachel Green",
                "authority_level": AuthorityLevel.STUDY_COORDINATOR,
                "license_number": None,
                "credential_type": "CCRC Certification",
                "credential_expiry": now + timedelta(days=200),
                "is_qualified": True,
                "qualifications": ["Certified Clinical Research Coordinator", "GCP Trained"],
                "supervision_required": False,
                "supervisor_name": None,
                "verified_by": "CRA Lisa Park",
                "verified_date": now - timedelta(days=140),
                "notes": "Certified coordinator for AE reporting and data entry.",
                "created_at": now - timedelta(days=141),
            },
            {
                "id": "AUTH-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "person_name": "Lab Tech Rachel Green",
                "authority_level": AuthorityLevel.LAB_TECHNICIAN,
                "license_number": "MA-CLT-2019-11245",
                "credential_type": "Clinical Lab Technician License",
                "credential_expiry": now - timedelta(days=30),
                "is_qualified": False,
                "qualifications": ["Clinical Lab Technician"],
                "supervision_required": True,
                "supervisor_name": "Lab Director",
                "verified_by": "CRA Lisa Park",
                "verified_date": now - timedelta(days=200),
                "notes": "Credential expired. Not currently qualified.",
                "created_at": now - timedelta(days=201),
            },
            {
                "id": "AUTH-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "person_name": "Dr. Angela Martinez",
                "authority_level": AuthorityLevel.PRINCIPAL_INVESTIGATOR,
                "license_number": "TX-MD-2008-19445",
                "credential_type": "Medical License",
                "credential_expiry": now + timedelta(days=500),
                "is_qualified": True,
                "qualifications": ["Board Certified Oncologist", "GCP Certified"],
                "supervision_required": False,
                "supervisor_name": None,
                "verified_by": "CRA David Smith",
                "verified_date": now - timedelta(days=130),
                "notes": "Principal Investigator for LIBTAYO trial.",
                "created_at": now - timedelta(days=131),
            },
            {
                "id": "AUTH-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "person_name": "Dr. David Park",
                "authority_level": AuthorityLevel.SUB_INVESTIGATOR,
                "license_number": "TX-MD-2019-67832",
                "credential_type": "Medical License",
                "credential_expiry": now + timedelta(days=420),
                "is_qualified": True,
                "qualifications": ["Oncology Fellow", "GCP Certified"],
                "supervision_required": True,
                "supervisor_name": "Dr. Angela Martinez",
                "verified_by": "CRA David Smith",
                "verified_date": now - timedelta(days=125),
                "notes": "Sub-investigator for consent and assessments under PI supervision.",
                "created_at": now - timedelta(days=126),
            },
            {
                "id": "AUTH-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "person_name": "Coordinator Amy Chen",
                "authority_level": AuthorityLevel.STUDY_COORDINATOR,
                "license_number": None,
                "credential_type": "CCRC Certification",
                "credential_expiry": now + timedelta(days=150),
                "is_qualified": True,
                "qualifications": ["Certified Clinical Research Coordinator", "GCP Trained", "Oncology Research Experience"],
                "supervision_required": False,
                "supervisor_name": None,
                "verified_by": "CRA David Smith",
                "verified_date": now - timedelta(days=120),
                "notes": "Coordinator qualified for AE documentation.",
                "created_at": now - timedelta(days=121),
            },
            {
                "id": "AUTH-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "person_name": "Nurse Sarah Kim",
                "authority_level": AuthorityLevel.NURSE,
                "license_number": "WA-RN-2014-55621",
                "credential_type": "Nursing License",
                "credential_expiry": now + timedelta(days=600),
                "is_qualified": True,
                "qualifications": ["Registered Nurse", "Oncology Nursing Certification", "GCP Trained"],
                "supervision_required": True,
                "supervisor_name": "Dr. Angela Martinez",
                "verified_by": "CRA David Smith",
                "verified_date": now - timedelta(days=100),
                "notes": "Nurse qualified for physical exams under physician supervision.",
                "created_at": now - timedelta(days=101),
            },
        ]

        for a in authority_data:
            self._authority_records[a["id"]] = AuthorityRecord(**a)

        # --- 12 Training Verifications ---
        training_data = [
            {
                "id": "TRN-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "trainee_name": "Dr. Sarah Mitchell",
                "training_topic": "Good Clinical Practice (GCP)",
                "training_status": TrainingStatus.COMPLETED,
                "training_date": now - timedelta(days=200),
                "completion_date": now - timedelta(days=200),
                "expiry_date": now + timedelta(days=530),
                "trainer_name": "CITI Program",
                "certificate_number": "GCP-2025-SM-44821",
                "score_pct": 95.0,
                "is_gcp_training": True,
                "notes": "GCP certification completed via CITI Program.",
                "created_at": now - timedelta(days=201),
            },
            {
                "id": "TRN-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "trainee_name": "Dr. James Chen",
                "training_topic": "Good Clinical Practice (GCP)",
                "training_status": TrainingStatus.COMPLETED,
                "training_date": now - timedelta(days=190),
                "completion_date": now - timedelta(days=190),
                "expiry_date": now + timedelta(days=540),
                "trainer_name": "CITI Program",
                "certificate_number": "GCP-2025-JC-55932",
                "score_pct": 92.0,
                "is_gcp_training": True,
                "notes": "GCP re-certification completed.",
                "created_at": now - timedelta(days=191),
            },
            {
                "id": "TRN-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "trainee_name": "Nurse Patricia Wells",
                "training_topic": "Protocol-Specific Training - EYLEA",
                "training_status": TrainingStatus.COMPLETED,
                "training_date": now - timedelta(days=175),
                "completion_date": now - timedelta(days=175),
                "expiry_date": None,
                "trainer_name": "Dr. Sarah Mitchell",
                "certificate_number": None,
                "score_pct": 100.0,
                "is_gcp_training": False,
                "notes": "Protocol-specific training completed by PI.",
                "created_at": now - timedelta(days=176),
            },
            {
                "id": "TRN-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "trainee_name": "Coordinator Amy Lin",
                "training_topic": "Good Clinical Practice (GCP)",
                "training_status": TrainingStatus.EXPIRED,
                "training_date": now - timedelta(days=800),
                "completion_date": now - timedelta(days=800),
                "expiry_date": now - timedelta(days=70),
                "trainer_name": "CITI Program",
                "certificate_number": "GCP-2023-AL-12345",
                "score_pct": 88.0,
                "is_gcp_training": True,
                "notes": "GCP certification expired. Re-training required.",
                "created_at": now - timedelta(days=801),
            },
            {
                "id": "TRN-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "trainee_name": "Dr. Michael Torres",
                "training_topic": "Good Clinical Practice (GCP)",
                "training_status": TrainingStatus.COMPLETED,
                "training_date": now - timedelta(days=160),
                "completion_date": now - timedelta(days=160),
                "expiry_date": now + timedelta(days=570),
                "trainer_name": "CITI Program",
                "certificate_number": "GCP-2025-MT-22198",
                "score_pct": 97.0,
                "is_gcp_training": True,
                "notes": "PI GCP certification current.",
                "created_at": now - timedelta(days=161),
            },
            {
                "id": "TRN-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "trainee_name": "Dr. Karen Liu",
                "training_topic": "Protocol-Specific Training - DUPIXENT",
                "training_status": TrainingStatus.IN_PROGRESS,
                "training_date": now - timedelta(days=10),
                "completion_date": None,
                "expiry_date": None,
                "trainer_name": "Dr. Michael Torres",
                "certificate_number": None,
                "score_pct": None,
                "is_gcp_training": False,
                "notes": "Protocol training in progress for sub-investigator.",
                "created_at": now - timedelta(days=11),
            },
            {
                "id": "TRN-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "trainee_name": "Coordinator Rachel Green",
                "training_topic": "EDC System Training - Medidata Rave",
                "training_status": TrainingStatus.COMPLETED,
                "training_date": now - timedelta(days=145),
                "completion_date": now - timedelta(days=145),
                "expiry_date": None,
                "trainer_name": "Medidata Trainer",
                "certificate_number": "EDC-RG-2025-001",
                "score_pct": 90.0,
                "is_gcp_training": False,
                "notes": "EDC system training completed.",
                "created_at": now - timedelta(days=146),
            },
            {
                "id": "TRN-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "trainee_name": "Nurse Karen Liu",
                "training_topic": "Good Clinical Practice (GCP)",
                "training_status": TrainingStatus.OVERDUE,
                "training_date": None,
                "completion_date": None,
                "expiry_date": now - timedelta(days=15),
                "trainer_name": None,
                "certificate_number": None,
                "score_pct": None,
                "is_gcp_training": True,
                "notes": "GCP training overdue. Delegation suspended pending completion.",
                "created_at": now - timedelta(days=120),
            },
            {
                "id": "TRN-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "trainee_name": "Dr. Angela Martinez",
                "training_topic": "Good Clinical Practice (GCP)",
                "training_status": TrainingStatus.COMPLETED,
                "training_date": now - timedelta(days=140),
                "completion_date": now - timedelta(days=140),
                "expiry_date": now + timedelta(days=590),
                "trainer_name": "CITI Program",
                "certificate_number": "GCP-2025-AM-19445",
                "score_pct": 98.0,
                "is_gcp_training": True,
                "notes": "PI GCP certification current.",
                "created_at": now - timedelta(days=141),
            },
            {
                "id": "TRN-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "trainee_name": "Dr. David Park",
                "training_topic": "Protocol-Specific Training - LIBTAYO",
                "training_status": TrainingStatus.COMPLETED,
                "training_date": now - timedelta(days=128),
                "completion_date": now - timedelta(days=128),
                "expiry_date": None,
                "trainer_name": "Dr. Angela Martinez",
                "certificate_number": None,
                "score_pct": 94.0,
                "is_gcp_training": False,
                "notes": "Protocol training completed by PI.",
                "created_at": now - timedelta(days=129),
            },
            {
                "id": "TRN-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "trainee_name": "Coordinator Amy Chen",
                "training_topic": "Good Clinical Practice (GCP)",
                "training_status": TrainingStatus.COMPLETED,
                "training_date": now - timedelta(days=125),
                "completion_date": now - timedelta(days=125),
                "expiry_date": now + timedelta(days=605),
                "trainer_name": "CITI Program",
                "certificate_number": "GCP-2025-AC-33456",
                "score_pct": 91.0,
                "is_gcp_training": True,
                "notes": "GCP certification current.",
                "created_at": now - timedelta(days=126),
            },
            {
                "id": "TRN-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "trainee_name": "Nurse Sarah Kim",
                "training_topic": "Immunotherapy Safety Training",
                "training_status": TrainingStatus.NOT_STARTED,
                "training_date": None,
                "completion_date": None,
                "expiry_date": None,
                "trainer_name": None,
                "certificate_number": None,
                "score_pct": None,
                "is_gcp_training": False,
                "notes": "Immunotherapy-specific safety training not yet started.",
                "created_at": now - timedelta(days=100),
            },
        ]

        for t in training_data:
            self._training_verifications[t["id"]] = TrainingVerification(**t)

        # --- 12 Delegation Audits ---
        audit_data = [
            {
                "id": "DAUD-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "audit_date": now - timedelta(days=90),
                "auditor_name": "CRA Jennifer Adams",
                "audit_result": AuditResult.COMPLIANT,
                "entries_reviewed": 4,
                "entries_compliant": 4,
                "findings_count": 0,
                "critical_findings": 0,
                "corrective_actions_required": 0,
                "corrective_actions_completed": 0,
                "next_audit_date": now + timedelta(days=90),
                "notes": "All delegation entries compliant at NY site.",
                "created_at": now - timedelta(days=91),
            },
            {
                "id": "DAUD-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-LA-001",
                "audit_date": now - timedelta(days=85),
                "auditor_name": "CRA Mark Wilson",
                "audit_result": AuditResult.COMPLIANT,
                "entries_reviewed": 2,
                "entries_compliant": 2,
                "findings_count": 0,
                "critical_findings": 0,
                "corrective_actions_required": 0,
                "corrective_actions_completed": 0,
                "next_audit_date": now + timedelta(days=95),
                "notes": "LA site delegation log in good order.",
                "created_at": now - timedelta(days=86),
            },
            {
                "id": "DAUD-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "audit_date": now - timedelta(days=30),
                "auditor_name": "QA Auditor Patricia Lane",
                "audit_result": AuditResult.PARTIAL,
                "entries_reviewed": 4,
                "entries_compliant": 3,
                "findings_count": 1,
                "critical_findings": 0,
                "corrective_actions_required": 1,
                "corrective_actions_completed": 0,
                "next_audit_date": now + timedelta(days=30),
                "notes": "One expired delegation entry found. Corrective action required.",
                "created_at": now - timedelta(days=31),
            },
            {
                "id": "DAUD-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-NY-001",
                "audit_date": now - timedelta(days=15),
                "auditor_name": "CRA Jennifer Adams",
                "audit_result": AuditResult.NOT_ASSESSED,
                "entries_reviewed": 0,
                "entries_compliant": 0,
                "findings_count": 0,
                "critical_findings": 0,
                "corrective_actions_required": 0,
                "corrective_actions_completed": 0,
                "next_audit_date": now + timedelta(days=60),
                "notes": "Scheduled audit postponed due to site availability.",
                "created_at": now - timedelta(days=16),
            },
            {
                "id": "DAUD-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "audit_date": now - timedelta(days=75),
                "auditor_name": "CRA Lisa Park",
                "audit_result": AuditResult.COMPLIANT,
                "entries_reviewed": 4,
                "entries_compliant": 4,
                "findings_count": 0,
                "critical_findings": 0,
                "corrective_actions_required": 0,
                "corrective_actions_completed": 0,
                "next_audit_date": now + timedelta(days=105),
                "notes": "Chicago site fully compliant.",
                "created_at": now - timedelta(days=76),
            },
            {
                "id": "DAUD-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "audit_date": now - timedelta(days=60),
                "auditor_name": "CRA Lisa Park",
                "audit_result": AuditResult.NON_COMPLIANT,
                "entries_reviewed": 2,
                "entries_compliant": 0,
                "findings_count": 3,
                "critical_findings": 2,
                "corrective_actions_required": 3,
                "corrective_actions_completed": 1,
                "next_audit_date": now + timedelta(days=15),
                "notes": "Critical findings: expired credentials, revoked delegation still active in system.",
                "created_at": now - timedelta(days=61),
            },
            {
                "id": "DAUD-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-CHI-001",
                "audit_date": now - timedelta(days=20),
                "auditor_name": "QA Auditor Patricia Lane",
                "audit_result": AuditResult.REMEDIATION_NEEDED,
                "entries_reviewed": 4,
                "entries_compliant": 3,
                "findings_count": 2,
                "critical_findings": 0,
                "corrective_actions_required": 2,
                "corrective_actions_completed": 0,
                "next_audit_date": now + timedelta(days=40),
                "notes": "Minor findings: suspended delegation needs formal documentation.",
                "created_at": now - timedelta(days=21),
            },
            {
                "id": "DAUD-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-BOS-001",
                "audit_date": now - timedelta(days=10),
                "auditor_name": "CRA Lisa Park",
                "audit_result": AuditResult.PARTIAL,
                "entries_reviewed": 2,
                "entries_compliant": 1,
                "findings_count": 1,
                "critical_findings": 1,
                "corrective_actions_required": 1,
                "corrective_actions_completed": 1,
                "next_audit_date": now + timedelta(days=30),
                "notes": "Follow-up audit. One corrective action completed, one finding remains.",
                "created_at": now - timedelta(days=11),
            },
            {
                "id": "DAUD-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "audit_date": now - timedelta(days=50),
                "auditor_name": "CRA David Smith",
                "audit_result": AuditResult.COMPLIANT,
                "entries_reviewed": 3,
                "entries_compliant": 3,
                "findings_count": 0,
                "critical_findings": 0,
                "corrective_actions_required": 0,
                "corrective_actions_completed": 0,
                "next_audit_date": now + timedelta(days=130),
                "notes": "Houston site fully compliant.",
                "created_at": now - timedelta(days=51),
            },
            {
                "id": "DAUD-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "audit_date": now - timedelta(days=45),
                "auditor_name": "CRA David Smith",
                "audit_result": AuditResult.PARTIAL,
                "entries_reviewed": 3,
                "entries_compliant": 2,
                "findings_count": 1,
                "critical_findings": 0,
                "corrective_actions_required": 1,
                "corrective_actions_completed": 0,
                "next_audit_date": now + timedelta(days=45),
                "notes": "Superseded delegation entry not properly archived.",
                "created_at": now - timedelta(days=46),
            },
            {
                "id": "DAUD-011",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-HOU-001",
                "audit_date": now - timedelta(days=5),
                "auditor_name": "QA Auditor Patricia Lane",
                "audit_result": AuditResult.COMPLIANT,
                "entries_reviewed": 3,
                "entries_compliant": 3,
                "findings_count": 0,
                "critical_findings": 0,
                "corrective_actions_required": 0,
                "corrective_actions_completed": 0,
                "next_audit_date": now + timedelta(days=175),
                "notes": "QA audit confirms ongoing compliance at Houston site.",
                "created_at": now - timedelta(days=6),
            },
            {
                "id": "DAUD-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-SEA-001",
                "audit_date": now - timedelta(days=2),
                "auditor_name": "CRA David Smith",
                "audit_result": AuditResult.REMEDIATION_NEEDED,
                "entries_reviewed": 3,
                "entries_compliant": 2,
                "findings_count": 1,
                "critical_findings": 0,
                "corrective_actions_required": 1,
                "corrective_actions_completed": 0,
                "next_audit_date": now + timedelta(days=30),
                "notes": "Nurse training record incomplete. Remediation needed.",
                "created_at": now - timedelta(days=3),
            },
        ]

        for aud in audit_data:
            self._delegation_audits[aud["id"]] = DelegationAudit(**aud)

    # ------------------------------------------------------------------
    # Delegation Entries
    # ------------------------------------------------------------------

    def list_delegation_entries(
        self,
        *,
        trial_id: str | None = None,
        delegation_category: DelegationCategory | None = None,
        delegation_status: DelegationStatus | None = None,
    ) -> list[DelegationEntry]:
        """List delegation entries with optional filters."""
        with self._lock:
            result = list(self._delegation_entries.values())

        if trial_id is not None:
            result = [e for e in result if e.trial_id == trial_id]
        if delegation_category is not None:
            result = [e for e in result if e.delegation_category == delegation_category]
        if delegation_status is not None:
            result = [e for e in result if e.delegation_status == delegation_status]

        return sorted(result, key=lambda e: e.effective_date, reverse=True)

    def get_delegation_entry(self, entry_id: str) -> DelegationEntry | None:
        """Get a single delegation entry by ID."""
        with self._lock:
            return self._delegation_entries.get(entry_id)

    def create_delegation_entry(self, payload: DelegationEntryCreate) -> DelegationEntry:
        """Create a new delegation entry."""
        now = datetime.now(timezone.utc)
        entry_id = f"DEL-{uuid4().hex[:8].upper()}"
        entry = DelegationEntry(
            id=entry_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            delegator_name=payload.delegator_name,
            delegate_name=payload.delegate_name,
            delegation_category=payload.delegation_category,
            delegation_status=DelegationStatus.ACTIVE,
            authority_level=payload.authority_level,
            effective_date=payload.effective_date,
            expiry_date=None,
            specific_tasks=payload.specific_tasks,
            restrictions=None,
            approved_by=payload.approved_by,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._delegation_entries[entry_id] = entry
        logger.info("Created delegation entry %s for trial %s", entry_id, payload.trial_id)
        return entry

    def update_delegation_entry(
        self, entry_id: str, payload: DelegationEntryUpdate
    ) -> DelegationEntry | None:
        """Update an existing delegation entry."""
        with self._lock:
            existing = self._delegation_entries.get(entry_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DelegationEntry(**data)
            self._delegation_entries[entry_id] = updated
        return updated

    def delete_delegation_entry(self, entry_id: str) -> bool:
        """Delete a delegation entry. Returns True if deleted."""
        with self._lock:
            if entry_id in self._delegation_entries:
                del self._delegation_entries[entry_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Authority Records
    # ------------------------------------------------------------------

    def list_authority_records(
        self,
        *,
        trial_id: str | None = None,
        authority_level: AuthorityLevel | None = None,
        is_qualified: bool | None = None,
    ) -> list[AuthorityRecord]:
        """List authority records with optional filters."""
        with self._lock:
            result = list(self._authority_records.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if authority_level is not None:
            result = [a for a in result if a.authority_level == authority_level]
        if is_qualified is not None:
            result = [a for a in result if a.is_qualified == is_qualified]

        return sorted(result, key=lambda a: a.verified_date, reverse=True)

    def get_authority_record(self, record_id: str) -> AuthorityRecord | None:
        """Get a single authority record by ID."""
        with self._lock:
            return self._authority_records.get(record_id)

    def create_authority_record(self, payload: AuthorityRecordCreate) -> AuthorityRecord:
        """Create a new authority record."""
        now = datetime.now(timezone.utc)
        record_id = f"AUTH-{uuid4().hex[:8].upper()}"
        record = AuthorityRecord(
            id=record_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            person_name=payload.person_name,
            authority_level=payload.authority_level,
            license_number=None,
            credential_type=payload.credential_type,
            credential_expiry=None,
            is_qualified=True,
            qualifications=payload.qualifications,
            supervision_required=False,
            supervisor_name=None,
            verified_by=payload.verified_by,
            verified_date=payload.verified_date,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._authority_records[record_id] = record
        logger.info("Created authority record %s for trial %s", record_id, payload.trial_id)
        return record

    def update_authority_record(
        self, record_id: str, payload: AuthorityRecordUpdate
    ) -> AuthorityRecord | None:
        """Update an existing authority record."""
        with self._lock:
            existing = self._authority_records.get(record_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AuthorityRecord(**data)
            self._authority_records[record_id] = updated
        return updated

    def delete_authority_record(self, record_id: str) -> bool:
        """Delete an authority record. Returns True if deleted."""
        with self._lock:
            if record_id in self._authority_records:
                del self._authority_records[record_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Training Verifications
    # ------------------------------------------------------------------

    def list_training_verifications(
        self,
        *,
        trial_id: str | None = None,
        training_status: TrainingStatus | None = None,
        is_gcp_training: bool | None = None,
    ) -> list[TrainingVerification]:
        """List training verifications with optional filters."""
        with self._lock:
            result = list(self._training_verifications.values())

        if trial_id is not None:
            result = [t for t in result if t.trial_id == trial_id]
        if training_status is not None:
            result = [t for t in result if t.training_status == training_status]
        if is_gcp_training is not None:
            result = [t for t in result if t.is_gcp_training == is_gcp_training]

        return sorted(result, key=lambda t: t.created_at, reverse=True)

    def get_training_verification(self, training_id: str) -> TrainingVerification | None:
        """Get a single training verification by ID."""
        with self._lock:
            return self._training_verifications.get(training_id)

    def create_training_verification(
        self, payload: TrainingVerificationCreate
    ) -> TrainingVerification:
        """Create a new training verification."""
        now = datetime.now(timezone.utc)
        training_id = f"TRN-{uuid4().hex[:8].upper()}"
        record = TrainingVerification(
            id=training_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            trainee_name=payload.trainee_name,
            training_topic=payload.training_topic,
            training_status=TrainingStatus.NOT_STARTED,
            training_date=None,
            completion_date=None,
            expiry_date=None,
            trainer_name=payload.trainer_name,
            certificate_number=None,
            score_pct=None,
            is_gcp_training=payload.is_gcp_training,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._training_verifications[training_id] = record
        logger.info(
            "Created training verification %s for trial %s", training_id, payload.trial_id
        )
        return record

    def update_training_verification(
        self, training_id: str, payload: TrainingVerificationUpdate
    ) -> TrainingVerification | None:
        """Update an existing training verification."""
        with self._lock:
            existing = self._training_verifications.get(training_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = TrainingVerification(**data)
            self._training_verifications[training_id] = updated
        return updated

    def delete_training_verification(self, training_id: str) -> bool:
        """Delete a training verification. Returns True if deleted."""
        with self._lock:
            if training_id in self._training_verifications:
                del self._training_verifications[training_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Delegation Audits
    # ------------------------------------------------------------------

    def list_delegation_audits(
        self,
        *,
        trial_id: str | None = None,
        audit_result: AuditResult | None = None,
    ) -> list[DelegationAudit]:
        """List delegation audits with optional filters."""
        with self._lock:
            result = list(self._delegation_audits.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if audit_result is not None:
            result = [a for a in result if a.audit_result == audit_result]

        return sorted(result, key=lambda a: a.audit_date, reverse=True)

    def get_delegation_audit(self, audit_id: str) -> DelegationAudit | None:
        """Get a single delegation audit by ID."""
        with self._lock:
            return self._delegation_audits.get(audit_id)

    def create_delegation_audit(self, payload: DelegationAuditCreate) -> DelegationAudit:
        """Create a new delegation audit."""
        now = datetime.now(timezone.utc)
        audit_id = f"DAUD-{uuid4().hex[:8].upper()}"
        record = DelegationAudit(
            id=audit_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            audit_date=now,
            auditor_name=payload.auditor_name,
            audit_result=AuditResult.NOT_ASSESSED,
            entries_reviewed=payload.entries_reviewed,
            entries_compliant=0,
            findings_count=0,
            critical_findings=0,
            corrective_actions_required=0,
            corrective_actions_completed=0,
            next_audit_date=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._delegation_audits[audit_id] = record
        logger.info("Created delegation audit %s for trial %s", audit_id, payload.trial_id)
        return record

    def update_delegation_audit(
        self, audit_id: str, payload: DelegationAuditUpdate
    ) -> DelegationAudit | None:
        """Update an existing delegation audit."""
        with self._lock:
            existing = self._delegation_audits.get(audit_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DelegationAudit(**data)
            self._delegation_audits[audit_id] = updated
        return updated

    def delete_delegation_audit(self, audit_id: str) -> bool:
        """Delete a delegation audit. Returns True if deleted."""
        with self._lock:
            if audit_id in self._delegation_audits:
                del self._delegation_audits[audit_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self, trial_id: str | None = None) -> DelegationLogMetrics:
        """Compute aggregated delegation log metrics."""
        with self._lock:
            entries = list(self._delegation_entries.values())
            authority = list(self._authority_records.values())
            training = list(self._training_verifications.values())
            audits = list(self._delegation_audits.values())

        # Apply trial_id filter if provided
        if trial_id is not None:
            entries = [e for e in entries if e.trial_id == trial_id]
            authority = [a for a in authority if a.trial_id == trial_id]
            training = [t for t in training if t.trial_id == trial_id]
            audits = [a for a in audits if a.trial_id == trial_id]

        # Delegations by category
        delegations_by_category: dict[str, int] = {}
        for e in entries:
            key = e.delegation_category.value
            delegations_by_category[key] = delegations_by_category.get(key, 0) + 1

        # Delegations by status
        delegations_by_status: dict[str, int] = {}
        for e in entries:
            key = e.delegation_status.value
            delegations_by_status[key] = delegations_by_status.get(key, 0) + 1

        # Active delegation rate
        active_count = sum(
            1 for e in entries if e.delegation_status == DelegationStatus.ACTIVE
        )
        active_delegation_rate = round(
            (active_count / max(1, len(entries))) * 100, 1
        )

        # Qualified personnel count
        qualified_personnel_count = sum(1 for a in authority if a.is_qualified)

        # Training by status
        training_by_status: dict[str, int] = {}
        for t in training:
            key = t.training_status.value
            training_by_status[key] = training_by_status.get(key, 0) + 1

        # Training completion rate
        completed_count = sum(
            1 for t in training if t.training_status == TrainingStatus.COMPLETED
        )
        training_completion_rate = round(
            (completed_count / max(1, len(training))) * 100, 1
        )

        # Audits by result
        audits_by_result: dict[str, int] = {}
        for a in audits:
            key = a.audit_result.value
            audits_by_result[key] = audits_by_result.get(key, 0) + 1

        # Compliance rate
        compliant_count = sum(
            1 for a in audits if a.audit_result == AuditResult.COMPLIANT
        )
        assessed_count = sum(
            1 for a in audits if a.audit_result != AuditResult.NOT_ASSESSED
        )
        compliance_rate = round(
            (compliant_count / max(1, assessed_count)) * 100, 1
        )

        return DelegationLogMetrics(
            total_delegations=len(entries),
            delegations_by_category=delegations_by_category,
            delegations_by_status=delegations_by_status,
            active_delegation_rate=active_delegation_rate,
            total_authority_records=len(authority),
            qualified_personnel_count=qualified_personnel_count,
            total_training_records=len(training),
            training_by_status=training_by_status,
            training_completion_rate=training_completion_rate,
            total_audits=len(audits),
            audits_by_result=audits_by_result,
            compliance_rate=compliance_rate,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: DelegationLogService | None = None
_instance_lock = threading.Lock()


def get_delegation_log_service() -> DelegationLogService:
    """Return the singleton DelegationLogService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = DelegationLogService()
    return _instance


def reset_delegation_log_service() -> DelegationLogService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = DelegationLogService()
    return _instance
