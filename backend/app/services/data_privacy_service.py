"""Data Privacy Management Service (DATA-PRIV).

Manages data privacy operations: consent records, anonymization tracking,
data subject requests (DSR), privacy impact assessments, data retention
policies, and privacy compliance metrics.

Usage:
    from app.services.data_privacy_service import (
        get_data_privacy_service,
    )

    svc = get_data_privacy_service()
    consents = svc.list_consent_records()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.data_privacy import (
    AnonymizationMethod,
    AnonymizationRecord,
    AnonymizationRecordCreate,
    AnonymizationRecordUpdate,
    ConsentRecord,
    ConsentRecordCreate,
    ConsentRecordUpdate,
    ConsentStatus,
    ConsentType,
    DataPrivacyMetrics,
    DataRetentionPolicy,
    DataRetentionPolicyCreate,
    DataRetentionPolicyUpdate,
    DataSubjectRequest,
    DataSubjectRequestCreate,
    DataSubjectRequestUpdate,
    DSRStatus,
    DSRType,
    PIAStatus,
    PrivacyImpactAssessment,
    PrivacyImpactAssessmentCreate,
    PrivacyImpactAssessmentUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class DataPrivacyService:
    """In-memory Data Privacy management engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._consent_records: dict[str, ConsentRecord] = {}
        self._anonymization_records: dict[str, AnonymizationRecord] = {}
        self._dsr_records: dict[str, DataSubjectRequest] = {}
        self._pia_records: dict[str, PrivacyImpactAssessment] = {}
        self._retention_policies: dict[str, DataRetentionPolicy] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic data privacy records across clinical trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Consent Records ---
        consent_data = [
            {
                "id": "CONSENT-001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1001",
                "consent_type": ConsentType.BROAD,
                "consent_status": ConsentStatus.ACTIVE,
                "consent_date": now - timedelta(days=180),
                "purpose": "Participation in EYLEA Phase III trial including genomic data collection",
                "data_categories": ["demographics", "clinical", "genomic"],
                "retention_period_months": 120,
                "third_party_sharing": True,
                "collected_by": "Dr. Sarah Chen",
                "consent_version": "2.1",
                "consent_method": "electronic",
            },
            {
                "id": "CONSENT-002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1002",
                "consent_type": ConsentType.SPECIFIC,
                "consent_status": ConsentStatus.ACTIVE,
                "consent_date": now - timedelta(days=150),
                "purpose": "EYLEA efficacy monitoring with limited data sharing",
                "data_categories": ["demographics", "clinical"],
                "retention_period_months": 60,
                "collected_by": "Dr. Sarah Chen",
                "consent_version": "2.1",
            },
            {
                "id": "CONSENT-003",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1003",
                "consent_type": ConsentType.TIERED,
                "consent_status": ConsentStatus.WITHDRAWN,
                "consent_date": now - timedelta(days=200),
                "withdrawal_date": now - timedelta(days=30),
                "purpose": "EYLEA trial participation with tiered data use options",
                "data_categories": ["demographics", "clinical", "imaging"],
                "retention_period_months": 60,
                "collected_by": "Nurse Rachel Adams",
                "consent_version": "2.0",
            },
            {
                "id": "CONSENT-004",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2001",
                "consent_type": ConsentType.BROAD,
                "consent_status": ConsentStatus.ACTIVE,
                "consent_date": now - timedelta(days=120),
                "purpose": "DUPIXENT atopic dermatitis trial including biomarker analysis",
                "data_categories": ["demographics", "clinical", "biomarker", "PRO"],
                "retention_period_months": 84,
                "third_party_sharing": True,
                "collected_by": "Dr. James Wilson",
                "consent_version": "3.0",
            },
            {
                "id": "CONSENT-005",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2002",
                "consent_type": ConsentType.DYNAMIC,
                "consent_status": ConsentStatus.ACTIVE,
                "consent_date": now - timedelta(days=90),
                "purpose": "DUPIXENT dynamic consent with ongoing preference updates",
                "data_categories": ["demographics", "clinical"],
                "retention_period_months": 60,
                "collected_by": "Dr. James Wilson",
                "consent_version": "3.0",
            },
            {
                "id": "CONSENT-006",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2003",
                "consent_type": ConsentType.SPECIFIC,
                "consent_status": ConsentStatus.EXPIRED,
                "consent_date": now - timedelta(days=400),
                "purpose": "DUPIXENT safety monitoring only",
                "data_categories": ["clinical", "safety"],
                "retention_period_months": 36,
                "collected_by": "Nurse Maria Santos",
                "consent_version": "2.5",
            },
            {
                "id": "CONSENT-007",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3001",
                "consent_type": ConsentType.BROAD,
                "consent_status": ConsentStatus.ACTIVE,
                "consent_date": now - timedelta(days=60),
                "purpose": "LIBTAYO immunotherapy trial with comprehensive data collection",
                "data_categories": ["demographics", "clinical", "genomic", "imaging"],
                "retention_period_months": 120,
                "third_party_sharing": True,
                "guardian_consent": True,
                "collected_by": "Dr. Emily Park",
                "consent_version": "1.0",
            },
            {
                "id": "CONSENT-008",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3002",
                "consent_type": ConsentType.TIERED,
                "consent_status": ConsentStatus.PENDING,
                "purpose": "LIBTAYO trial enrollment pending guardian approval",
                "data_categories": ["demographics", "clinical"],
                "retention_period_months": 60,
                "guardian_consent": True,
                "collected_by": "Dr. Emily Park",
                "consent_version": "1.0",
            },
            {
                "id": "CONSENT-009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3003",
                "consent_type": ConsentType.BLANKET,
                "consent_status": ConsentStatus.ACTIVE,
                "consent_date": now - timedelta(days=45),
                "purpose": "LIBTAYO blanket consent for all trial-related activities",
                "data_categories": ["demographics", "clinical", "genomic", "biomarker", "imaging", "PRO"],
                "retention_period_months": 180,
                "third_party_sharing": True,
                "collected_by": "Dr. Emily Park",
                "consent_version": "1.0",
            },
            {
                "id": "CONSENT-010",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1004",
                "consent_type": ConsentType.SPECIFIC,
                "consent_status": ConsentStatus.RESTRICTED,
                "consent_date": now - timedelta(days=100),
                "purpose": "EYLEA limited consent - clinical data only, no sharing",
                "data_categories": ["clinical"],
                "retention_period_months": 36,
                "collected_by": "Nurse Rachel Adams",
                "consent_version": "2.1",
            },
            {
                "id": "CONSENT-011",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2004",
                "consent_type": ConsentType.DYNAMIC,
                "consent_status": ConsentStatus.ACTIVE,
                "consent_date": now - timedelta(days=75),
                "purpose": "DUPIXENT dynamic consent for pediatric cohort",
                "data_categories": ["demographics", "clinical", "PRO"],
                "retention_period_months": 60,
                "guardian_consent": True,
                "collected_by": "Dr. James Wilson",
                "consent_version": "3.0",
            },
            {
                "id": "CONSENT-012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3004",
                "consent_type": ConsentType.BROAD,
                "consent_status": ConsentStatus.WITHDRAWN,
                "consent_date": now - timedelta(days=90),
                "withdrawal_date": now - timedelta(days=10),
                "purpose": "LIBTAYO broad consent - withdrawn due to relocation",
                "data_categories": ["demographics", "clinical", "genomic"],
                "retention_period_months": 120,
                "collected_by": "Dr. Emily Park",
                "consent_version": "1.0",
            },
        ]

        for c in consent_data:
            rec = ConsentRecord(
                created_at=now - timedelta(days=200),
                consent_method=c.get("consent_method", "electronic"),
                guardian_consent=c.get("guardian_consent", False),
                third_party_sharing=c.get("third_party_sharing", False),
                withdrawal_date=c.get("withdrawal_date"),
                notes=c.get("notes"),
                **{k: v for k, v in c.items() if k not in (
                    "consent_method", "guardian_consent", "third_party_sharing",
                    "withdrawal_date", "notes",
                )},
            )
            self._consent_records[rec.id] = rec

        # --- 10 Anonymization Records ---
        anon_data = [
            {
                "id": "ANON-001",
                "trial_id": EYLEA_TRIAL,
                "dataset_name": "EYLEA Phase III Demographics",
                "method": AnonymizationMethod.K_ANONYMITY,
                "records_processed": 1250,
                "fields_anonymized": ["name", "dob", "ssn", "address", "phone"],
                "k_value": 5,
                "re_identification_risk": 2.3,
                "quality_score": 95.0,
                "validated": True,
                "validated_by": "Dr. Privacy Officer",
                "performed_by": "Data Engineering Team",
            },
            {
                "id": "ANON-002",
                "trial_id": EYLEA_TRIAL,
                "dataset_name": "EYLEA Genomic Samples",
                "method": AnonymizationMethod.DIFFERENTIAL_PRIVACY,
                "records_processed": 800,
                "fields_anonymized": ["genomic_id", "sample_id", "collector"],
                "epsilon_value": 1.5,
                "re_identification_risk": 1.1,
                "quality_score": 92.0,
                "validated": True,
                "validated_by": "Genomics Privacy Lead",
                "performed_by": "Bioinformatics Team",
            },
            {
                "id": "ANON-003",
                "trial_id": DUPIXENT_TRIAL,
                "dataset_name": "DUPIXENT Clinical Outcomes",
                "method": AnonymizationMethod.L_DIVERSITY,
                "records_processed": 2100,
                "fields_anonymized": ["patient_id", "name", "dob", "email"],
                "k_value": 3,
                "re_identification_risk": 3.7,
                "quality_score": 88.5,
                "validated": True,
                "validated_by": "Dr. Privacy Officer",
                "performed_by": "Data Engineering Team",
            },
            {
                "id": "ANON-004",
                "trial_id": DUPIXENT_TRIAL,
                "dataset_name": "DUPIXENT PRO Survey Data",
                "method": AnonymizationMethod.PSEUDONYMIZATION,
                "records_processed": 3500,
                "fields_anonymized": ["respondent_id", "name", "email"],
                "re_identification_risk": 5.2,
                "quality_score": 85.0,
                "validated": False,
                "performed_by": "Survey Analytics Team",
            },
            {
                "id": "ANON-005",
                "trial_id": LIBTAYO_TRIAL,
                "dataset_name": "LIBTAYO Imaging Metadata",
                "method": AnonymizationMethod.DATA_MASKING,
                "records_processed": 4200,
                "fields_anonymized": ["patient_name", "mrn", "accession_number", "study_date"],
                "re_identification_risk": 1.8,
                "quality_score": 97.0,
                "validated": True,
                "validated_by": "Imaging Privacy Lead",
                "performed_by": "Radiology IT Team",
            },
            {
                "id": "ANON-006",
                "trial_id": LIBTAYO_TRIAL,
                "dataset_name": "LIBTAYO Safety Reports",
                "method": AnonymizationMethod.T_CLOSENESS,
                "records_processed": 650,
                "fields_anonymized": ["reporter_id", "patient_name", "facility"],
                "re_identification_risk": 2.9,
                "quality_score": 91.0,
                "validated": True,
                "validated_by": "Safety Data Lead",
                "performed_by": "Pharmacovigilance Team",
            },
            {
                "id": "ANON-007",
                "trial_id": EYLEA_TRIAL,
                "dataset_name": "EYLEA Lab Results Export",
                "method": AnonymizationMethod.K_ANONYMITY,
                "records_processed": 5600,
                "fields_anonymized": ["patient_id", "name", "collector_id"],
                "k_value": 7,
                "re_identification_risk": 1.5,
                "quality_score": 96.0,
                "validated": True,
                "validated_by": "Lab Privacy Officer",
                "performed_by": "Central Lab Team",
            },
            {
                "id": "ANON-008",
                "trial_id": DUPIXENT_TRIAL,
                "dataset_name": "DUPIXENT Biomarker Panel",
                "method": AnonymizationMethod.DIFFERENTIAL_PRIVACY,
                "records_processed": 1800,
                "fields_anonymized": ["subject_id", "sample_collector", "site_name"],
                "epsilon_value": 2.0,
                "re_identification_risk": 1.9,
                "quality_score": 93.5,
                "validated": False,
                "performed_by": "Biomarker Analytics Team",
            },
            {
                "id": "ANON-009",
                "trial_id": LIBTAYO_TRIAL,
                "dataset_name": "LIBTAYO Patient Registry",
                "method": AnonymizationMethod.PSEUDONYMIZATION,
                "records_processed": 920,
                "fields_anonymized": ["name", "dob", "address", "phone", "email", "insurance_id"],
                "re_identification_risk": 4.1,
                "quality_score": 87.0,
                "validated": False,
                "performed_by": "Registry Management Team",
            },
            {
                "id": "ANON-010",
                "trial_id": EYLEA_TRIAL,
                "dataset_name": "EYLEA Adverse Event Reports",
                "method": AnonymizationMethod.DATA_MASKING,
                "records_processed": 320,
                "fields_anonymized": ["reporter_name", "patient_id", "facility_name"],
                "re_identification_risk": 2.0,
                "quality_score": 94.0,
                "validated": True,
                "validated_by": "Safety Data Lead",
                "performed_by": "Safety Reporting Team",
            },
        ]

        for a in anon_data:
            rec = AnonymizationRecord(
                anonymization_date=now - timedelta(days=60),
                created_at=now - timedelta(days=60),
                notes=a.get("notes"),
                **{k: v for k, v in a.items() if k != "notes"},
            )
            self._anonymization_records[rec.id] = rec

        # --- 12 Data Subject Requests ---
        dsr_data = [
            {
                "id": "DSR-001",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1001",
                "request_type": DSRType.ACCESS,
                "status": DSRStatus.COMPLETED,
                "received_date": now - timedelta(days=45),
                "acknowledged_date": now - timedelta(days=44),
                "completed_date": now - timedelta(days=20),
                "request_details": "Subject requests full copy of all personal data held in EYLEA trial",
                "response_details": "Complete data package provided via secure portal",
                "handled_by": "Privacy Team Lead",
                "data_categories_affected": ["demographics", "clinical", "genomic"],
                "systems_affected": ["EDC", "CTMS", "Lab System"],
                "days_to_complete": 25,
            },
            {
                "id": "DSR-002",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1003",
                "request_type": DSRType.ERASURE,
                "status": DSRStatus.IN_PROGRESS,
                "received_date": now - timedelta(days=15),
                "acknowledged_date": now - timedelta(days=14),
                "due_date": now + timedelta(days=15),
                "request_details": "Subject requests erasure of all data following consent withdrawal",
                "handled_by": "Privacy Team Lead",
                "data_categories_affected": ["demographics", "clinical", "imaging"],
                "systems_affected": ["EDC", "CTMS", "PACS"],
            },
            {
                "id": "DSR-003",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2001",
                "request_type": DSRType.PORTABILITY,
                "status": DSRStatus.COMPLETED,
                "received_date": now - timedelta(days=60),
                "acknowledged_date": now - timedelta(days=59),
                "completed_date": now - timedelta(days=40),
                "request_details": "Subject requests machine-readable export for transfer to new provider",
                "response_details": "FHIR bundle exported and transmitted securely",
                "handled_by": "Data Ops Specialist",
                "data_categories_affected": ["demographics", "clinical", "biomarker"],
                "systems_affected": ["EDC", "Biomarker DB"],
                "days_to_complete": 20,
            },
            {
                "id": "DSR-004",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2002",
                "request_type": DSRType.RECTIFICATION,
                "status": DSRStatus.COMPLETED,
                "received_date": now - timedelta(days=30),
                "acknowledged_date": now - timedelta(days=29),
                "completed_date": now - timedelta(days=22),
                "request_details": "Subject requests correction of date of birth and address",
                "response_details": "Records updated across all systems",
                "handled_by": "Data Ops Specialist",
                "data_categories_affected": ["demographics"],
                "systems_affected": ["EDC", "CTMS"],
                "days_to_complete": 8,
            },
            {
                "id": "DSR-005",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3001",
                "request_type": DSRType.ACCESS,
                "status": DSRStatus.ACKNOWLEDGED,
                "received_date": now - timedelta(days=5),
                "acknowledged_date": now - timedelta(days=4),
                "due_date": now + timedelta(days=25),
                "request_details": "Subject requests access to imaging data and reports",
                "handled_by": "Privacy Team Lead",
                "data_categories_affected": ["imaging", "clinical"],
                "systems_affected": ["PACS", "EDC"],
            },
            {
                "id": "DSR-006",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3002",
                "request_type": DSRType.RESTRICTION,
                "status": DSRStatus.COMPLETED,
                "received_date": now - timedelta(days=40),
                "acknowledged_date": now - timedelta(days=39),
                "completed_date": now - timedelta(days=25),
                "request_details": "Subject requests restriction on genomic data processing",
                "response_details": "Processing restricted; data flagged in all systems",
                "handled_by": "Genomics Privacy Lead",
                "data_categories_affected": ["genomic"],
                "systems_affected": ["Genomics DB", "Bioinformatics Platform"],
                "days_to_complete": 15,
            },
            {
                "id": "DSR-007",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1002",
                "request_type": DSRType.OBJECTION,
                "status": DSRStatus.DENIED,
                "received_date": now - timedelta(days=50),
                "acknowledged_date": now - timedelta(days=49),
                "completed_date": now - timedelta(days=35),
                "request_details": "Subject objects to secondary use of clinical data for research",
                "denial_reason": "Legal basis for processing exists under clinical trial regulation",
                "handled_by": "Legal Counsel",
                "data_categories_affected": ["clinical"],
                "systems_affected": ["EDC"],
                "days_to_complete": 15,
            },
            {
                "id": "DSR-008",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2003",
                "request_type": DSRType.ERASURE,
                "status": DSRStatus.EXTENDED,
                "received_date": now - timedelta(days=25),
                "acknowledged_date": now - timedelta(days=24),
                "due_date": now + timedelta(days=35),
                "request_details": "Subject requests erasure - complex multi-system data removal required",
                "handled_by": "Privacy Team Lead",
                "data_categories_affected": ["demographics", "clinical", "safety"],
                "systems_affected": ["EDC", "CTMS", "Safety DB", "Archival"],
            },
            {
                "id": "DSR-009",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3003",
                "request_type": DSRType.PORTABILITY,
                "status": DSRStatus.RECEIVED,
                "received_date": now - timedelta(days=2),
                "request_details": "Subject requests data portability for all trial records",
                "handled_by": "Data Ops Specialist",
                "data_categories_affected": ["demographics", "clinical", "genomic", "imaging"],
                "systems_affected": ["EDC", "CTMS", "PACS", "Genomics DB"],
            },
            {
                "id": "DSR-010",
                "trial_id": EYLEA_TRIAL,
                "subject_id": "SUBJ-1004",
                "request_type": DSRType.ACCESS,
                "status": DSRStatus.COMPLETED,
                "received_date": now - timedelta(days=70),
                "acknowledged_date": now - timedelta(days=69),
                "completed_date": now - timedelta(days=50),
                "request_details": "Subject requests summary of data processing activities",
                "response_details": "Processing summary report provided",
                "handled_by": "Privacy Team Lead",
                "data_categories_affected": ["clinical"],
                "systems_affected": ["EDC"],
                "days_to_complete": 20,
            },
            {
                "id": "DSR-011",
                "trial_id": DUPIXENT_TRIAL,
                "subject_id": "SUBJ-2004",
                "request_type": DSRType.RECTIFICATION,
                "status": DSRStatus.IN_PROGRESS,
                "received_date": now - timedelta(days=8),
                "acknowledged_date": now - timedelta(days=7),
                "due_date": now + timedelta(days=22),
                "request_details": "Guardian requests correction of minor subject demographic data",
                "handled_by": "Data Ops Specialist",
                "data_categories_affected": ["demographics"],
                "systems_affected": ["EDC", "CTMS"],
            },
            {
                "id": "DSR-012",
                "trial_id": LIBTAYO_TRIAL,
                "subject_id": "SUBJ-3004",
                "request_type": DSRType.ERASURE,
                "status": DSRStatus.ACKNOWLEDGED,
                "received_date": now - timedelta(days=6),
                "acknowledged_date": now - timedelta(days=5),
                "due_date": now + timedelta(days=24),
                "request_details": "Subject requests erasure following consent withdrawal",
                "handled_by": "Privacy Team Lead",
                "data_categories_affected": ["demographics", "clinical", "genomic"],
                "systems_affected": ["EDC", "CTMS", "Genomics DB"],
            },
        ]

        for d in dsr_data:
            rec = DataSubjectRequest(
                created_at=now - timedelta(days=70),
                response_details=d.get("response_details"),
                denial_reason=d.get("denial_reason"),
                days_to_complete=d.get("days_to_complete"),
                **{k: v for k, v in d.items() if k not in (
                    "response_details", "denial_reason", "days_to_complete",
                )},
            )
            self._dsr_records[rec.id] = rec

        # --- 10 Privacy Impact Assessments ---
        pia_data = [
            {
                "id": "PIA-001",
                "trial_id": EYLEA_TRIAL,
                "assessment_name": "EYLEA Phase III Genomic Data Collection PIA",
                "status": PIAStatus.APPROVED,
                "assessment_date": now - timedelta(days=200),
                "data_types_assessed": ["genomic", "demographics", "clinical"],
                "risk_level": "high",
                "findings_count": 8,
                "high_risk_findings": 3,
                "mitigations_required": 5,
                "mitigations_completed": 5,
                "dpo_review_required": True,
                "dpo_approved": True,
                "assessor": "Dr. Privacy Officer",
                "reviewer": "Chief Data Protection Officer",
            },
            {
                "id": "PIA-002",
                "trial_id": EYLEA_TRIAL,
                "assessment_name": "EYLEA Third-Party Data Sharing PIA",
                "status": PIAStatus.COMPLETED,
                "assessment_date": now - timedelta(days=150),
                "data_types_assessed": ["clinical", "demographics"],
                "risk_level": "medium",
                "findings_count": 4,
                "high_risk_findings": 1,
                "mitigations_required": 3,
                "mitigations_completed": 3,
                "dpo_review_required": True,
                "dpo_approved": True,
                "assessor": "Privacy Analyst",
                "reviewer": "Dr. Privacy Officer",
            },
            {
                "id": "PIA-003",
                "trial_id": DUPIXENT_TRIAL,
                "assessment_name": "DUPIXENT PRO Data Platform PIA",
                "status": PIAStatus.REQUIRES_ACTION,
                "assessment_date": now - timedelta(days=90),
                "data_types_assessed": ["PRO", "demographics", "clinical"],
                "risk_level": "medium",
                "findings_count": 6,
                "high_risk_findings": 2,
                "mitigations_required": 4,
                "mitigations_completed": 1,
                "dpo_review_required": True,
                "dpo_approved": False,
                "assessor": "Privacy Analyst",
                "reviewer": "Dr. Privacy Officer",
            },
            {
                "id": "PIA-004",
                "trial_id": DUPIXENT_TRIAL,
                "assessment_name": "DUPIXENT Biomarker Analytics PIA",
                "status": PIAStatus.APPROVED,
                "assessment_date": now - timedelta(days=120),
                "data_types_assessed": ["biomarker", "clinical"],
                "risk_level": "low",
                "findings_count": 2,
                "high_risk_findings": 0,
                "mitigations_required": 1,
                "mitigations_completed": 1,
                "dpo_review_required": False,
                "dpo_approved": False,
                "assessor": "Privacy Analyst",
            },
            {
                "id": "PIA-005",
                "trial_id": LIBTAYO_TRIAL,
                "assessment_name": "LIBTAYO Imaging Data Processing PIA",
                "status": PIAStatus.IN_PROGRESS,
                "assessment_date": now - timedelta(days=30),
                "data_types_assessed": ["imaging", "demographics"],
                "risk_level": "high",
                "findings_count": 5,
                "high_risk_findings": 2,
                "mitigations_required": 3,
                "mitigations_completed": 0,
                "dpo_review_required": True,
                "assessor": "Dr. Privacy Officer",
            },
            {
                "id": "PIA-006",
                "trial_id": LIBTAYO_TRIAL,
                "assessment_name": "LIBTAYO Cross-Border Transfer PIA",
                "status": PIAStatus.COMPLETED,
                "assessment_date": now - timedelta(days=100),
                "data_types_assessed": ["demographics", "clinical", "genomic"],
                "risk_level": "high",
                "findings_count": 10,
                "high_risk_findings": 4,
                "mitigations_required": 7,
                "mitigations_completed": 7,
                "dpo_review_required": True,
                "dpo_approved": True,
                "assessor": "International Privacy Lead",
                "reviewer": "Chief Data Protection Officer",
            },
            {
                "id": "PIA-007",
                "trial_id": EYLEA_TRIAL,
                "assessment_name": "EYLEA Data Retention Review PIA",
                "status": PIAStatus.PLANNED,
                "assessment_date": now + timedelta(days=30),
                "data_types_assessed": ["clinical", "demographics"],
                "risk_level": "low",
                "findings_count": 0,
                "assessor": "Privacy Analyst",
            },
            {
                "id": "PIA-008",
                "trial_id": DUPIXENT_TRIAL,
                "assessment_name": "DUPIXENT Pediatric Cohort PIA",
                "status": PIAStatus.APPROVED,
                "assessment_date": now - timedelta(days=80),
                "data_types_assessed": ["demographics", "clinical", "PRO"],
                "risk_level": "high",
                "findings_count": 7,
                "high_risk_findings": 3,
                "mitigations_required": 5,
                "mitigations_completed": 5,
                "dpo_review_required": True,
                "dpo_approved": True,
                "assessor": "Dr. Privacy Officer",
                "reviewer": "Chief Data Protection Officer",
            },
            {
                "id": "PIA-009",
                "trial_id": LIBTAYO_TRIAL,
                "assessment_name": "LIBTAYO Registry Linkage PIA",
                "status": PIAStatus.IN_PROGRESS,
                "assessment_date": now - timedelta(days=15),
                "data_types_assessed": ["demographics", "clinical"],
                "risk_level": "medium",
                "findings_count": 3,
                "high_risk_findings": 1,
                "mitigations_required": 2,
                "mitigations_completed": 0,
                "dpo_review_required": True,
                "assessor": "Privacy Analyst",
            },
            {
                "id": "PIA-010",
                "trial_id": DUPIXENT_TRIAL,
                "assessment_name": "DUPIXENT AI/ML Model Training PIA",
                "status": PIAStatus.PLANNED,
                "assessment_date": now + timedelta(days=45),
                "data_types_assessed": ["clinical", "biomarker", "genomic"],
                "risk_level": "high",
                "findings_count": 0,
                "dpo_review_required": True,
                "assessor": "AI Privacy Specialist",
            },
        ]

        for p in pia_data:
            rec = PrivacyImpactAssessment(
                created_at=now - timedelta(days=200),
                reviewer=p.get("reviewer"),
                notes=p.get("notes"),
                **{k: v for k, v in p.items() if k not in ("reviewer", "notes")},
            )
            self._pia_records[rec.id] = rec

        # --- 10 Data Retention Policies ---
        retention_data = [
            {
                "id": "RET-001",
                "trial_id": EYLEA_TRIAL,
                "policy_name": "EYLEA Clinical Data Retention",
                "data_category": "clinical",
                "retention_period_months": 180,
                "legal_basis": "ICH E6(R2) GCP requirement - 15 years post trial completion",
                "applicable_regulations": ["ICH E6(R2)", "21 CFR Part 11", "EU CTR"],
                "destruction_method": "secure_deletion",
                "review_date": now - timedelta(days=30),
                "next_review_date": now + timedelta(days=335),
                "is_active": True,
                "records_covered": 12500,
                "records_due_deletion": 0,
                "created_by": "Privacy Team Lead",
                "approved_by": "Chief Data Protection Officer",
            },
            {
                "id": "RET-002",
                "trial_id": EYLEA_TRIAL,
                "policy_name": "EYLEA Genomic Data Retention",
                "data_category": "genomic",
                "retention_period_months": 300,
                "legal_basis": "Genomic research consent allows 25-year retention",
                "applicable_regulations": ["GINA", "EU GDPR Art 9", "ICH E18"],
                "destruction_method": "cryptographic_erasure",
                "review_date": now - timedelta(days=60),
                "next_review_date": now + timedelta(days=305),
                "is_active": True,
                "records_covered": 800,
                "records_due_deletion": 0,
                "created_by": "Genomics Privacy Lead",
                "approved_by": "Chief Data Protection Officer",
            },
            {
                "id": "RET-003",
                "trial_id": DUPIXENT_TRIAL,
                "policy_name": "DUPIXENT Clinical Data Retention",
                "data_category": "clinical",
                "retention_period_months": 180,
                "legal_basis": "ICH E6(R2) GCP requirement",
                "applicable_regulations": ["ICH E6(R2)", "21 CFR Part 11"],
                "destruction_method": "secure_deletion",
                "review_date": now - timedelta(days=45),
                "next_review_date": now + timedelta(days=320),
                "is_active": True,
                "records_covered": 21000,
                "records_due_deletion": 150,
                "created_by": "Privacy Team Lead",
                "approved_by": "Chief Data Protection Officer",
            },
            {
                "id": "RET-004",
                "trial_id": DUPIXENT_TRIAL,
                "policy_name": "DUPIXENT PRO Data Retention",
                "data_category": "PRO",
                "retention_period_months": 60,
                "legal_basis": "Consent-based retention for patient reported outcomes",
                "applicable_regulations": ["EU GDPR Art 6", "HIPAA"],
                "destruction_method": "secure_deletion",
                "review_date": now - timedelta(days=20),
                "next_review_date": now + timedelta(days=345),
                "is_active": True,
                "records_covered": 3500,
                "records_due_deletion": 420,
                "created_by": "PRO Data Manager",
                "approved_by": "Privacy Team Lead",
            },
            {
                "id": "RET-005",
                "trial_id": LIBTAYO_TRIAL,
                "policy_name": "LIBTAYO Clinical Data Retention",
                "data_category": "clinical",
                "retention_period_months": 180,
                "legal_basis": "ICH E6(R2) GCP requirement",
                "applicable_regulations": ["ICH E6(R2)", "21 CFR Part 11", "EU CTR"],
                "destruction_method": "secure_deletion",
                "review_date": now - timedelta(days=15),
                "next_review_date": now + timedelta(days=350),
                "is_active": True,
                "records_covered": 9200,
                "records_due_deletion": 0,
                "created_by": "Privacy Team Lead",
                "approved_by": "Chief Data Protection Officer",
            },
            {
                "id": "RET-006",
                "trial_id": LIBTAYO_TRIAL,
                "policy_name": "LIBTAYO Imaging Data Retention",
                "data_category": "imaging",
                "retention_period_months": 120,
                "legal_basis": "Medical imaging retention per institutional policy",
                "applicable_regulations": ["HIPAA", "21 CFR Part 11"],
                "destruction_method": "physical_destruction",
                "review_date": now - timedelta(days=10),
                "next_review_date": now + timedelta(days=355),
                "is_active": True,
                "records_covered": 4200,
                "records_due_deletion": 85,
                "created_by": "Imaging Privacy Lead",
                "approved_by": "Chief Data Protection Officer",
            },
            {
                "id": "RET-007",
                "trial_id": EYLEA_TRIAL,
                "policy_name": "EYLEA Safety Data Retention",
                "data_category": "safety",
                "retention_period_months": 240,
                "legal_basis": "Pharmacovigilance regulatory requirement - lifetime retention",
                "applicable_regulations": ["ICH E2E", "EU GVP Module VI", "21 CFR 314.80"],
                "destruction_method": "secure_deletion",
                "is_active": True,
                "records_covered": 1800,
                "records_due_deletion": 0,
                "created_by": "Safety Data Lead",
                "approved_by": "Chief Medical Officer",
            },
            {
                "id": "RET-008",
                "trial_id": DUPIXENT_TRIAL,
                "policy_name": "DUPIXENT Biomarker Data Retention",
                "data_category": "biomarker",
                "retention_period_months": 120,
                "legal_basis": "Research consent with 10-year retention window",
                "applicable_regulations": ["EU GDPR Art 9", "ICH E18"],
                "destruction_method": "cryptographic_erasure",
                "is_active": True,
                "records_covered": 1800,
                "records_due_deletion": 0,
                "created_by": "Biomarker Data Manager",
                "approved_by": "Privacy Team Lead",
            },
            {
                "id": "RET-009",
                "trial_id": LIBTAYO_TRIAL,
                "policy_name": "LIBTAYO Genomic Research Retention",
                "data_category": "genomic",
                "retention_period_months": 300,
                "legal_basis": "Broad consent for long-term genomic research retention",
                "applicable_regulations": ["GINA", "EU GDPR Art 9", "Common Rule"],
                "destruction_method": "cryptographic_erasure",
                "is_active": True,
                "records_covered": 450,
                "records_due_deletion": 0,
                "created_by": "Genomics Privacy Lead",
                "approved_by": "Chief Data Protection Officer",
            },
            {
                "id": "RET-010",
                "trial_id": EYLEA_TRIAL,
                "policy_name": "EYLEA Legacy Demo Data (Inactive)",
                "data_category": "demographics",
                "retention_period_months": 36,
                "legal_basis": "Legacy policy - superseded",
                "applicable_regulations": ["HIPAA"],
                "destruction_method": "secure_deletion",
                "review_date": now - timedelta(days=400),
                "is_active": False,
                "records_covered": 500,
                "records_due_deletion": 500,
                "created_by": "Privacy Team Lead",
                "approved_by": "Privacy Team Lead",
            },
        ]

        for r in retention_data:
            rec = DataRetentionPolicy(
                created_at=now - timedelta(days=200),
                approved_by=r.get("approved_by"),
                review_date=r.get("review_date"),
                next_review_date=r.get("next_review_date"),
                **{k: v for k, v in r.items() if k not in (
                    "approved_by", "review_date", "next_review_date",
                )},
            )
            self._retention_policies[rec.id] = rec

    # ------------------------------------------------------------------
    # Consent Record CRUD
    # ------------------------------------------------------------------

    def list_consent_records(
        self,
        trial_id: str | None = None,
        consent_type: ConsentType | None = None,
        consent_status: ConsentStatus | None = None,
    ) -> list[ConsentRecord]:
        with self._lock:
            items = list(self._consent_records.values())
        if trial_id:
            items = [i for i in items if i.trial_id == trial_id]
        if consent_type:
            items = [i for i in items if i.consent_type == consent_type]
        if consent_status:
            items = [i for i in items if i.consent_status == consent_status]
        return items

    def get_consent_record(self, record_id: str) -> ConsentRecord | None:
        with self._lock:
            return self._consent_records.get(record_id)

    def create_consent_record(self, payload: ConsentRecordCreate) -> ConsentRecord:
        now = datetime.now(timezone.utc)
        rec = ConsentRecord(
            id=f"CONSENT-{uuid4().hex[:8].upper()}",
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            consent_type=payload.consent_type,
            consent_status=ConsentStatus.PENDING,
            purpose=payload.purpose,
            collected_by=payload.collected_by,
            data_categories=payload.data_categories,
            retention_period_months=payload.retention_period_months,
            created_at=now,
        )
        with self._lock:
            self._consent_records[rec.id] = rec
        return rec

    def update_consent_record(
        self, record_id: str, payload: ConsentRecordUpdate
    ) -> ConsentRecord | None:
        with self._lock:
            rec = self._consent_records.get(record_id)
            if rec is None:
                return None
            data = rec.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            if "consent_status" in updates and updates["consent_status"] == ConsentStatus.WITHDRAWN:
                updates["withdrawal_date"] = datetime.now(timezone.utc)
            if "consent_status" in updates and updates["consent_status"] == ConsentStatus.ACTIVE:
                updates["consent_date"] = datetime.now(timezone.utc)
            data.update(updates)
            updated = ConsentRecord(**data)
            self._consent_records[record_id] = updated
            return updated

    def delete_consent_record(self, record_id: str) -> bool:
        with self._lock:
            return self._consent_records.pop(record_id, None) is not None

    # ------------------------------------------------------------------
    # Anonymization Record CRUD
    # ------------------------------------------------------------------

    def list_anonymization_records(
        self,
        trial_id: str | None = None,
        method: AnonymizationMethod | None = None,
        validated: bool | None = None,
    ) -> list[AnonymizationRecord]:
        with self._lock:
            items = list(self._anonymization_records.values())
        if trial_id:
            items = [i for i in items if i.trial_id == trial_id]
        if method:
            items = [i for i in items if i.method == method]
        if validated is not None:
            items = [i for i in items if i.validated == validated]
        return items

    def get_anonymization_record(self, record_id: str) -> AnonymizationRecord | None:
        with self._lock:
            return self._anonymization_records.get(record_id)

    def create_anonymization_record(
        self, payload: AnonymizationRecordCreate
    ) -> AnonymizationRecord:
        now = datetime.now(timezone.utc)
        rec = AnonymizationRecord(
            id=f"ANON-{uuid4().hex[:8].upper()}",
            trial_id=payload.trial_id,
            dataset_name=payload.dataset_name,
            method=payload.method,
            performed_by=payload.performed_by,
            records_processed=payload.records_processed,
            fields_anonymized=payload.fields_anonymized,
            anonymization_date=now,
            created_at=now,
        )
        with self._lock:
            self._anonymization_records[rec.id] = rec
        return rec

    def update_anonymization_record(
        self, record_id: str, payload: AnonymizationRecordUpdate
    ) -> AnonymizationRecord | None:
        with self._lock:
            rec = self._anonymization_records.get(record_id)
            if rec is None:
                return None
            data = rec.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = AnonymizationRecord(**data)
            self._anonymization_records[record_id] = updated
            return updated

    def delete_anonymization_record(self, record_id: str) -> bool:
        with self._lock:
            return self._anonymization_records.pop(record_id, None) is not None

    # ------------------------------------------------------------------
    # Data Subject Request CRUD
    # ------------------------------------------------------------------

    def list_dsr(
        self,
        trial_id: str | None = None,
        request_type: DSRType | None = None,
        status: DSRStatus | None = None,
    ) -> list[DataSubjectRequest]:
        with self._lock:
            items = list(self._dsr_records.values())
        if trial_id:
            items = [i for i in items if i.trial_id == trial_id]
        if request_type:
            items = [i for i in items if i.request_type == request_type]
        if status:
            items = [i for i in items if i.status == status]
        return items

    def get_dsr(self, record_id: str) -> DataSubjectRequest | None:
        with self._lock:
            return self._dsr_records.get(record_id)

    def create_dsr(self, payload: DataSubjectRequestCreate) -> DataSubjectRequest:
        now = datetime.now(timezone.utc)
        rec = DataSubjectRequest(
            id=f"DSR-{uuid4().hex[:8].upper()}",
            trial_id=payload.trial_id,
            subject_id=payload.subject_id,
            request_type=payload.request_type,
            status=DSRStatus.RECEIVED,
            received_date=now,
            request_details=payload.request_details,
            handled_by=payload.handled_by,
            data_categories_affected=payload.data_categories_affected,
            created_at=now,
        )
        with self._lock:
            self._dsr_records[rec.id] = rec
        return rec

    def update_dsr(
        self, record_id: str, payload: DataSubjectRequestUpdate
    ) -> DataSubjectRequest | None:
        with self._lock:
            rec = self._dsr_records.get(record_id)
            if rec is None:
                return None
            data = rec.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            now = datetime.now(timezone.utc)
            if "status" in updates:
                new_status = updates["status"]
                if new_status == DSRStatus.ACKNOWLEDGED:
                    updates["acknowledged_date"] = now
                elif new_status == DSRStatus.COMPLETED:
                    updates["completed_date"] = now
                    if rec.received_date:
                        delta = now - rec.received_date
                        updates["days_to_complete"] = delta.days
            data.update(updates)
            updated = DataSubjectRequest(**data)
            self._dsr_records[record_id] = updated
            return updated

    def delete_dsr(self, record_id: str) -> bool:
        with self._lock:
            return self._dsr_records.pop(record_id, None) is not None

    # ------------------------------------------------------------------
    # Privacy Impact Assessment CRUD
    # ------------------------------------------------------------------

    def list_pia(
        self,
        trial_id: str | None = None,
        status: PIAStatus | None = None,
        risk_level: str | None = None,
    ) -> list[PrivacyImpactAssessment]:
        with self._lock:
            items = list(self._pia_records.values())
        if trial_id:
            items = [i for i in items if i.trial_id == trial_id]
        if status:
            items = [i for i in items if i.status == status]
        if risk_level:
            items = [i for i in items if i.risk_level == risk_level]
        return items

    def get_pia(self, record_id: str) -> PrivacyImpactAssessment | None:
        with self._lock:
            return self._pia_records.get(record_id)

    def create_pia(
        self, payload: PrivacyImpactAssessmentCreate
    ) -> PrivacyImpactAssessment:
        now = datetime.now(timezone.utc)
        rec = PrivacyImpactAssessment(
            id=f"PIA-{uuid4().hex[:8].upper()}",
            trial_id=payload.trial_id,
            assessment_name=payload.assessment_name,
            status=PIAStatus.PLANNED,
            assessment_date=now,
            data_types_assessed=payload.data_types_assessed,
            risk_level=payload.risk_level,
            assessor=payload.assessor,
            created_at=now,
        )
        with self._lock:
            self._pia_records[rec.id] = rec
        return rec

    def update_pia(
        self, record_id: str, payload: PrivacyImpactAssessmentUpdate
    ) -> PrivacyImpactAssessment | None:
        with self._lock:
            rec = self._pia_records.get(record_id)
            if rec is None:
                return None
            data = rec.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = PrivacyImpactAssessment(**data)
            self._pia_records[record_id] = updated
            return updated

    def delete_pia(self, record_id: str) -> bool:
        with self._lock:
            return self._pia_records.pop(record_id, None) is not None

    # ------------------------------------------------------------------
    # Data Retention Policy CRUD
    # ------------------------------------------------------------------

    def list_retention_policies(
        self,
        trial_id: str | None = None,
        is_active: bool | None = None,
        data_category: str | None = None,
    ) -> list[DataRetentionPolicy]:
        with self._lock:
            items = list(self._retention_policies.values())
        if trial_id:
            items = [i for i in items if i.trial_id == trial_id]
        if is_active is not None:
            items = [i for i in items if i.is_active == is_active]
        if data_category:
            items = [i for i in items if i.data_category == data_category]
        return items

    def get_retention_policy(self, record_id: str) -> DataRetentionPolicy | None:
        with self._lock:
            return self._retention_policies.get(record_id)

    def create_retention_policy(
        self, payload: DataRetentionPolicyCreate
    ) -> DataRetentionPolicy:
        now = datetime.now(timezone.utc)
        rec = DataRetentionPolicy(
            id=f"RET-{uuid4().hex[:8].upper()}",
            trial_id=payload.trial_id,
            policy_name=payload.policy_name,
            data_category=payload.data_category,
            legal_basis=payload.legal_basis,
            created_by=payload.created_by,
            retention_period_months=payload.retention_period_months,
            created_at=now,
        )
        with self._lock:
            self._retention_policies[rec.id] = rec
        return rec

    def update_retention_policy(
        self, record_id: str, payload: DataRetentionPolicyUpdate
    ) -> DataRetentionPolicy | None:
        with self._lock:
            rec = self._retention_policies.get(record_id)
            if rec is None:
                return None
            data = rec.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = DataRetentionPolicy(**data)
            self._retention_policies[record_id] = updated
            return updated

    def delete_retention_policy(self, record_id: str) -> bool:
        with self._lock:
            return self._retention_policies.pop(record_id, None) is not None

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> DataPrivacyMetrics:
        with self._lock:
            consents = list(self._consent_records.values())
            anon_recs = list(self._anonymization_records.values())
            dsrs = list(self._dsr_records.values())
            pias = list(self._pia_records.values())
            policies = list(self._retention_policies.values())

        # Consent metrics
        consents_by_type: dict[str, int] = {}
        consents_by_status: dict[str, int] = {}
        active_consents = 0
        withdrawn_consents = 0
        for c in consents:
            consents_by_type[c.consent_type.value] = consents_by_type.get(c.consent_type.value, 0) + 1
            consents_by_status[c.consent_status.value] = consents_by_status.get(c.consent_status.value, 0) + 1
            if c.consent_status == ConsentStatus.ACTIVE:
                active_consents += 1
            if c.consent_status == ConsentStatus.WITHDRAWN:
                withdrawn_consents += 1

        # Anonymization metrics
        records_by_method: dict[str, int] = {}
        total_risk = 0.0
        for a in anon_recs:
            records_by_method[a.method.value] = records_by_method.get(a.method.value, 0) + 1
            total_risk += a.re_identification_risk
        avg_risk = total_risk / len(anon_recs) if anon_recs else 0.0

        # DSR metrics
        dsr_by_type: dict[str, int] = {}
        dsr_by_status: dict[str, int] = {}
        completion_days: list[int] = []
        for d in dsrs:
            dsr_by_type[d.request_type.value] = dsr_by_type.get(d.request_type.value, 0) + 1
            dsr_by_status[d.status.value] = dsr_by_status.get(d.status.value, 0) + 1
            if d.days_to_complete is not None:
                completion_days.append(d.days_to_complete)
        avg_completion = sum(completion_days) / len(completion_days) if completion_days else 0.0

        # PIA metrics
        pia_by_status: dict[str, int] = {}
        for p in pias:
            pia_by_status[p.status.value] = pia_by_status.get(p.status.value, 0) + 1

        # Retention metrics
        active_policies = sum(1 for p in policies if p.is_active)
        total_due_deletion = sum(p.records_due_deletion for p in policies)

        return DataPrivacyMetrics(
            total_consent_records=len(consents),
            consents_by_type=consents_by_type,
            consents_by_status=consents_by_status,
            active_consents=active_consents,
            withdrawn_consents=withdrawn_consents,
            total_anonymization_records=len(anon_recs),
            records_by_method=records_by_method,
            avg_re_identification_risk=round(avg_risk, 2),
            total_dsr=len(dsrs),
            dsr_by_type=dsr_by_type,
            dsr_by_status=dsr_by_status,
            avg_dsr_completion_days=round(avg_completion, 2),
            total_pia=len(pias),
            pia_by_status=pia_by_status,
            total_retention_policies=len(policies),
            active_policies=active_policies,
            records_due_deletion=total_due_deletion,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: DataPrivacyService | None = None
_instance_lock = threading.Lock()


def get_data_privacy_service() -> DataPrivacyService:
    """Return (or create) the singleton DataPrivacyService."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = DataPrivacyService()
    return _instance


def reset_data_privacy_service() -> DataPrivacyService:
    """Replace the singleton with a fresh instance (for tests).

    Returns the new instance.
    """
    global _instance
    with _instance_lock:
        _instance = DataPrivacyService()
    return _instance
