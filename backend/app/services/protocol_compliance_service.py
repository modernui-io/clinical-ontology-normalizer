"""Protocol Compliance Management Service (PROT-COMP).

Manages protocol compliance operations: GCP compliance monitoring,
protocol adherence tracking, compliance audit findings, training
compliance records, corrective action tracking, and compliance metrics.

Usage:
    from app.services.protocol_compliance_service import (
        get_protocol_compliance_service,
    )

    svc = get_protocol_compliance_service()
    assessments = svc.list_assessments()
    metrics = svc.get_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.protocol_compliance import (
    ComplianceArea,
    ComplianceAssessment,
    ComplianceAssessmentCreate,
    ComplianceAssessmentUpdate,
    ComplianceFinding,
    ComplianceFindingCreate,
    ComplianceFindingUpdate,
    ComplianceRating,
    CorrectiveAction,
    CorrectiveActionCreate,
    CorrectiveActionUpdate,
    FindingSeverity,
    FindingStatus,
    ProtocolAdherence,
    ProtocolAdherenceCreate,
    ProtocolAdherenceUpdate,
    ProtocolComplianceMetrics,
    TrainingCompliance,
    TrainingComplianceCreate,
    TrainingComplianceUpdate,
    TrainingStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ProtocolComplianceService:
    """In-memory Protocol Compliance engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._assessments: dict[str, ComplianceAssessment] = {}
        self._findings: dict[str, ComplianceFinding] = {}
        self._training: dict[str, TrainingCompliance] = {}
        self._adherence: dict[str, ProtocolAdherence] = {}
        self._corrective_actions: dict[str, CorrectiveAction] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic protocol compliance data."""
        now = datetime.now(timezone.utc)

        # --- 12 Compliance Assessments ---
        assessments_data = [
            {
                "id": "CA-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "compliance_area": ComplianceArea.GCP,
                "assessment_date": now - timedelta(days=90),
                "rating": ComplianceRating.FULLY_COMPLIANT,
                "score": 95.0,
                "findings_count": 0,
                "critical_findings": 0,
                "assessor": "Dr. Sarah Mitchell",
                "methodology": "On-site audit with documentation review",
                "next_assessment_date": now + timedelta(days=90),
                "notes": "Excellent GCP compliance. No findings.",
                "created_at": now - timedelta(days=95),
            },
            {
                "id": "CA-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "compliance_area": ComplianceArea.INFORMED_CONSENT,
                "assessment_date": now - timedelta(days=85),
                "rating": ComplianceRating.FULLY_COMPLIANT,
                "score": 98.0,
                "findings_count": 0,
                "critical_findings": 0,
                "assessor": "Dr. Sarah Mitchell",
                "methodology": "Document review and interview",
                "next_assessment_date": now + timedelta(days=95),
                "notes": "All consent forms properly executed and filed.",
                "created_at": now - timedelta(days=90),
            },
            {
                "id": "CA-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "compliance_area": ComplianceArea.DATA_INTEGRITY,
                "assessment_date": now - timedelta(days=60),
                "rating": ComplianceRating.PARTIALLY_COMPLIANT,
                "score": 65.0,
                "findings_count": 3,
                "critical_findings": 0,
                "assessor": "David Park",
                "methodology": "Source data verification and electronic data review",
                "next_assessment_date": now + timedelta(days=30),
                "notes": "Multiple data integrity issues identified. CAPA required.",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "CA-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "compliance_area": ComplianceArea.SAFETY_REPORTING,
                "assessment_date": now - timedelta(days=45),
                "rating": ComplianceRating.NON_COMPLIANT,
                "score": 40.0,
                "findings_count": 4,
                "critical_findings": 2,
                "assessor": "Jennifer Lee",
                "methodology": "Safety reporting audit with timeline analysis",
                "next_assessment_date": now + timedelta(days=15),
                "notes": "Critical safety reporting deficiencies. Immediate corrective action required.",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "CA-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "compliance_area": ComplianceArea.DRUG_MANAGEMENT,
                "assessment_date": now - timedelta(days=40),
                "rating": ComplianceRating.SUBSTANTIALLY_COMPLIANT,
                "score": 78.0,
                "findings_count": 2,
                "critical_findings": 0,
                "assessor": "Jennifer Lee",
                "methodology": "IP accountability review",
                "next_assessment_date": now + timedelta(days=50),
                "notes": "Minor drug management deviations noted.",
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "CA-006",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "compliance_area": ComplianceArea.PROTOCOL_PROCEDURES,
                "assessment_date": now - timedelta(days=30),
                "rating": ComplianceRating.NON_COMPLIANT,
                "score": 35.0,
                "findings_count": 5,
                "critical_findings": 3,
                "assessor": "David Park",
                "methodology": "Comprehensive protocol adherence review",
                "next_assessment_date": now + timedelta(days=14),
                "notes": "Systemic protocol non-compliance. Site remediation plan required.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "CA-007",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "compliance_area": ComplianceArea.SOURCE_DOCUMENTATION,
                "assessment_date": now - timedelta(days=28),
                "rating": ComplianceRating.PARTIALLY_COMPLIANT,
                "score": 55.0,
                "findings_count": 3,
                "critical_findings": 1,
                "assessor": "David Park",
                "methodology": "Source document verification",
                "next_assessment_date": now + timedelta(days=20),
                "notes": "Significant source documentation gaps.",
                "created_at": now - timedelta(days=33),
            },
            {
                "id": "CA-008",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "compliance_area": ComplianceArea.REGULATORY,
                "assessment_date": now - timedelta(days=20),
                "rating": ComplianceRating.FULLY_COMPLIANT,
                "score": 92.0,
                "findings_count": 1,
                "critical_findings": 0,
                "assessor": "Sarah Mitchell",
                "methodology": "Regulatory document review",
                "next_assessment_date": now + timedelta(days=70),
                "notes": "Strong regulatory compliance. Minor observation only.",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "CA-009",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "compliance_area": ComplianceArea.GCP,
                "assessment_date": now - timedelta(days=15),
                "rating": ComplianceRating.SUBSTANTIALLY_COMPLIANT,
                "score": 82.0,
                "findings_count": 2,
                "critical_findings": 0,
                "assessor": "Jennifer Lee",
                "methodology": "GCP compliance audit",
                "next_assessment_date": now + timedelta(days=75),
                "notes": "Generally compliant with minor areas for improvement.",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "CA-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "compliance_area": ComplianceArea.INFORMED_CONSENT,
                "assessment_date": now - timedelta(days=10),
                "rating": ComplianceRating.PARTIALLY_COMPLIANT,
                "score": 60.0,
                "findings_count": 3,
                "critical_findings": 1,
                "assessor": "David Park",
                "methodology": "Informed consent process audit",
                "next_assessment_date": now + timedelta(days=30),
                "notes": "Consent form version control issues at multiple visits.",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "CA-011",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-108",
                "compliance_area": ComplianceArea.DATA_INTEGRITY,
                "assessment_date": now - timedelta(days=5),
                "rating": ComplianceRating.SUBSTANTIALLY_COMPLIANT,
                "score": 85.0,
                "findings_count": 1,
                "critical_findings": 0,
                "assessor": "Sarah Mitchell",
                "methodology": "Data quality assessment",
                "next_assessment_date": now + timedelta(days=85),
                "notes": "Good data integrity practices with one minor gap.",
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "CA-012",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "compliance_area": ComplianceArea.SAFETY_REPORTING,
                "assessment_date": now - timedelta(days=3),
                "rating": ComplianceRating.SUBSTANTIALLY_COMPLIANT,
                "score": 80.0,
                "findings_count": 2,
                "critical_findings": 0,
                "assessor": "Jennifer Lee",
                "methodology": "Safety reporting process review",
                "next_assessment_date": now + timedelta(days=60),
                "notes": "Adequate safety reporting with minor timeliness issues.",
                "created_at": now - timedelta(days=8),
            },
        ]

        for a in assessments_data:
            self._assessments[a["id"]] = ComplianceAssessment(**a)

        # --- 12 Compliance Findings ---
        findings_data = [
            {
                "id": "CF-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "assessment_id": "CA-003",
                "compliance_area": ComplianceArea.DATA_INTEGRITY,
                "finding_description": "CRF data entries lack source document verification for 15% of critical fields",
                "severity": FindingSeverity.MAJOR,
                "status": FindingStatus.IN_REMEDIATION,
                "root_cause": "Insufficient CRA training on SDV requirements",
                "corrective_action": "Retrain CRAs on SDV procedures",
                "preventive_action": "Implement automated SDV tracking dashboard",
                "responsible_person": "Dr. James Wilson",
                "due_date": now + timedelta(days=14),
                "days_open": 55,
                "created_at": now - timedelta(days=58),
            },
            {
                "id": "CF-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "assessment_id": "CA-003",
                "compliance_area": ComplianceArea.DATA_INTEGRITY,
                "finding_description": "Electronic signatures missing on 8 completed eCRF pages",
                "severity": FindingSeverity.MINOR,
                "status": FindingStatus.REMEDIATED,
                "root_cause": "Staff unfamiliar with e-signature workflow",
                "corrective_action": "Complete all missing signatures",
                "responsible_person": "Dr. James Wilson",
                "due_date": now - timedelta(days=20),
                "remediation_date": now - timedelta(days=25),
                "verified_by": "David Park",
                "verification_date": now - timedelta(days=18),
                "days_open": 33,
                "created_at": now - timedelta(days=58),
            },
            {
                "id": "CF-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "assessment_id": "CA-003",
                "compliance_area": ComplianceArea.DATA_INTEGRITY,
                "finding_description": "Query response time exceeds 10 business days for 20% of queries",
                "severity": FindingSeverity.MINOR,
                "status": FindingStatus.OPEN,
                "responsible_person": "Site Coordinator Anna Chen",
                "due_date": now + timedelta(days=21),
                "days_open": 55,
                "created_at": now - timedelta(days=58),
            },
            {
                "id": "CF-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "assessment_id": "CA-004",
                "compliance_area": ComplianceArea.SAFETY_REPORTING,
                "finding_description": "3 SAEs not reported to sponsor within 24 hours of site awareness",
                "severity": FindingSeverity.CRITICAL,
                "status": FindingStatus.IN_REMEDIATION,
                "root_cause": "PI delegation log not updated; designated safety reporter was on leave",
                "corrective_action": "Immediate notification to all site staff of SAE reporting procedures",
                "preventive_action": "Designate backup safety reporter and implement automated alerts",
                "responsible_person": "Dr. Michael Torres",
                "due_date": now + timedelta(days=7),
                "days_open": 42,
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "CF-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "assessment_id": "CA-004",
                "compliance_area": ComplianceArea.SAFETY_REPORTING,
                "finding_description": "AE severity grading inconsistent with CTCAE v5.0 criteria",
                "severity": FindingSeverity.CRITICAL,
                "status": FindingStatus.OPEN,
                "responsible_person": "Dr. Michael Torres",
                "due_date": now + timedelta(days=10),
                "days_open": 42,
                "created_at": now - timedelta(days=45),
            },
            {
                "id": "CF-006",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "assessment_id": "CA-006",
                "compliance_area": ComplianceArea.PROTOCOL_PROCEDURES,
                "finding_description": "5 subjects with visits outside protocol-specified windows",
                "severity": FindingSeverity.CRITICAL,
                "status": FindingStatus.OPEN,
                "responsible_person": "Dr. Robert Chen",
                "due_date": now + timedelta(days=5),
                "days_open": 28,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "CF-007",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "assessment_id": "CA-006",
                "compliance_area": ComplianceArea.PROTOCOL_PROCEDURES,
                "finding_description": "Incorrect dosing calculation for 2 subjects based on outdated weight measurements",
                "severity": FindingSeverity.CRITICAL,
                "status": FindingStatus.IN_REMEDIATION,
                "root_cause": "Dosing worksheet not updated after protocol amendment",
                "corrective_action": "Recalculate doses and implement dose verification checklist",
                "responsible_person": "Dr. Robert Chen",
                "due_date": now + timedelta(days=3),
                "days_open": 28,
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "CF-008",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "assessment_id": "CA-007",
                "compliance_area": ComplianceArea.SOURCE_DOCUMENTATION,
                "finding_description": "Source documents for 3 visits cannot be located in investigator site file",
                "severity": FindingSeverity.MAJOR,
                "status": FindingStatus.OPEN,
                "responsible_person": "Site Coordinator Lisa Wang",
                "due_date": now + timedelta(days=14),
                "days_open": 25,
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "CF-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "assessment_id": "CA-010",
                "compliance_area": ComplianceArea.INFORMED_CONSENT,
                "finding_description": "Consent form version 3.1 used after version 4.0 was approved by IRB",
                "severity": FindingSeverity.CRITICAL,
                "status": FindingStatus.IN_REMEDIATION,
                "root_cause": "IRB approval notification not distributed to clinical team promptly",
                "corrective_action": "Re-consent affected subjects with current version",
                "responsible_person": "Dr. Patricia Hayes",
                "due_date": now + timedelta(days=7),
                "days_open": 8,
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "CF-010",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "assessment_id": "CA-008",
                "compliance_area": ComplianceArea.REGULATORY,
                "finding_description": "Annual IRB renewal submitted 3 days after expiration date",
                "severity": FindingSeverity.OBSERVATION,
                "status": FindingStatus.CLOSED,
                "root_cause": "Calendar reminder set for wrong date",
                "corrective_action": "Updated reminder system with 30-day advance notice",
                "responsible_person": "Regulatory Coordinator Maria Santos",
                "due_date": now - timedelta(days=5),
                "remediation_date": now - timedelta(days=8),
                "verified_by": "Sarah Mitchell",
                "verification_date": now - timedelta(days=3),
                "days_open": 12,
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "CF-011",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "assessment_id": "CA-009",
                "compliance_area": ComplianceArea.GCP,
                "finding_description": "Delegation log not updated for 2 new staff members",
                "severity": FindingSeverity.MINOR,
                "status": FindingStatus.REMEDIATED,
                "root_cause": "No formal process for delegation log updates during staff changes",
                "corrective_action": "Updated delegation log and implemented onboarding checklist",
                "responsible_person": "Site Manager John Adams",
                "due_date": now - timedelta(days=2),
                "remediation_date": now - timedelta(days=5),
                "days_open": 10,
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "CF-012",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "assessment_id": "CA-012",
                "compliance_area": ComplianceArea.SAFETY_REPORTING,
                "finding_description": "Follow-up SAE reports not submitted within required 15-day timeframe",
                "severity": FindingSeverity.MAJOR,
                "status": FindingStatus.OPEN,
                "responsible_person": "Dr. James Wilson",
                "due_date": now + timedelta(days=21),
                "days_open": 2,
                "created_at": now - timedelta(days=3),
            },
        ]

        for f in findings_data:
            self._findings[f["id"]] = ComplianceFinding(**f)

        # --- 12 Training Compliance Records ---
        training_data = [
            {
                "id": "TC-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "trainee_name": "Dr. Sarah Mitchell",
                "trainee_role": "Principal Investigator",
                "training_topic": "GCP/ICH E6(R2) Requirements",
                "training_type": "initial",
                "status": TrainingStatus.COMPLETED,
                "required_date": now - timedelta(days=180),
                "completion_date": now - timedelta(days=185),
                "expiry_date": now + timedelta(days=180),
                "score": 95.0,
                "passing_score": 80.0,
                "certificate_id": "CERT-GCP-001",
                "trainer": "CITI Program",
                "created_at": now - timedelta(days=190),
            },
            {
                "id": "TC-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "trainee_name": "Anna Chen",
                "trainee_role": "Study Coordinator",
                "training_topic": "Protocol-Specific Training EYLEA-2024",
                "training_type": "initial",
                "status": TrainingStatus.COMPLETED,
                "required_date": now - timedelta(days=170),
                "completion_date": now - timedelta(days=172),
                "expiry_date": now + timedelta(days=190),
                "score": 92.0,
                "passing_score": 80.0,
                "certificate_id": "CERT-PROT-002",
                "trainer": "Medical Monitor Dr. Klein",
                "created_at": now - timedelta(days=175),
            },
            {
                "id": "TC-003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "trainee_name": "Dr. Michael Torres",
                "trainee_role": "Principal Investigator",
                "training_topic": "SAE Reporting and Safety Monitoring",
                "training_type": "remedial",
                "status": TrainingStatus.IN_PROGRESS,
                "required_date": now - timedelta(days=10),
                "score": None,
                "passing_score": 85.0,
                "trainer": "Sponsor Medical Monitor",
                "notes": "Remedial training required due to safety reporting deficiencies",
                "created_at": now - timedelta(days=15),
            },
            {
                "id": "TC-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "trainee_name": "Nurse Rachel Green",
                "trainee_role": "Study Nurse",
                "training_topic": "AE/SAE Assessment and CTCAE Grading",
                "training_type": "refresher",
                "status": TrainingStatus.NOT_STARTED,
                "required_date": now + timedelta(days=7),
                "passing_score": 80.0,
                "notes": "Scheduled for next week",
                "created_at": now - timedelta(days=5),
            },
            {
                "id": "TC-005",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "trainee_name": "Dr. Robert Chen",
                "trainee_role": "Principal Investigator",
                "training_topic": "Protocol Amendment 4.0 Training",
                "training_type": "amendment",
                "status": TrainingStatus.EXPIRED,
                "required_date": now - timedelta(days=30),
                "expiry_date": now - timedelta(days=5),
                "passing_score": 80.0,
                "notes": "Training completion overdue. Protocol amendment training critical.",
                "created_at": now - timedelta(days=35),
            },
            {
                "id": "TC-006",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "trainee_name": "Lisa Wang",
                "trainee_role": "Study Coordinator",
                "training_topic": "EDC System Training (Medidata Rave)",
                "training_type": "initial",
                "status": TrainingStatus.COMPLETED,
                "required_date": now - timedelta(days=60),
                "completion_date": now - timedelta(days=62),
                "expiry_date": now + timedelta(days=300),
                "score": 88.0,
                "passing_score": 80.0,
                "certificate_id": "CERT-EDC-006",
                "trainer": "Medidata Training Team",
                "created_at": now - timedelta(days=65),
            },
            {
                "id": "TC-007",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "trainee_name": "Dr. Alan Wright",
                "trainee_role": "Sub-Investigator",
                "training_topic": "GCP/ICH E6(R2) Requirements",
                "training_type": "initial",
                "status": TrainingStatus.COMPLETED,
                "required_date": now - timedelta(days=150),
                "completion_date": now - timedelta(days=155),
                "expiry_date": now + timedelta(days=210),
                "score": 90.0,
                "passing_score": 80.0,
                "certificate_id": "CERT-GCP-007",
                "trainer": "CITI Program",
                "created_at": now - timedelta(days=160),
            },
            {
                "id": "TC-008",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "trainee_name": "John Adams",
                "trainee_role": "Site Manager",
                "training_topic": "Delegation Log and Staff Management SOP",
                "training_type": "remedial",
                "status": TrainingStatus.COMPLETED,
                "required_date": now - timedelta(days=10),
                "completion_date": now - timedelta(days=8),
                "expiry_date": now + timedelta(days=355),
                "score": 87.0,
                "passing_score": 80.0,
                "certificate_id": "CERT-SOP-008",
                "trainer": "QA Director",
                "created_at": now - timedelta(days=12),
            },
            {
                "id": "TC-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "trainee_name": "Dr. Patricia Hayes",
                "trainee_role": "Principal Investigator",
                "training_topic": "Informed Consent Process and Version Control",
                "training_type": "remedial",
                "status": TrainingStatus.IN_PROGRESS,
                "required_date": now - timedelta(days=5),
                "passing_score": 85.0,
                "trainer": "Clinical QA Specialist",
                "notes": "Remedial training for consent version control finding",
                "created_at": now - timedelta(days=7),
            },
            {
                "id": "TC-010",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-108",
                "trainee_name": "Dr. Karen Lee",
                "trainee_role": "Principal Investigator",
                "training_topic": "Data Quality and Electronic Source Documentation",
                "training_type": "refresher",
                "status": TrainingStatus.COMPLETED,
                "required_date": now - timedelta(days=20),
                "completion_date": now - timedelta(days=22),
                "expiry_date": now + timedelta(days=340),
                "score": 94.0,
                "passing_score": 80.0,
                "certificate_id": "CERT-DQ-010",
                "trainer": "Data Management Lead",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "TC-011",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "trainee_name": "Dr. James Wilson",
                "trainee_role": "Principal Investigator",
                "training_topic": "Safety Reporting Timeliness Requirements",
                "training_type": "refresher",
                "status": TrainingStatus.WAIVED,
                "required_date": now - timedelta(days=15),
                "passing_score": 80.0,
                "notes": "Waived due to equivalent training completed at another site",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "TC-012",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "trainee_name": "Pharmacy Tech Mark Stevens",
                "trainee_role": "Pharmacist",
                "training_topic": "IP Storage, Handling, and Accountability",
                "training_type": "initial",
                "status": TrainingStatus.COMPLETED,
                "required_date": now - timedelta(days=160),
                "completion_date": now - timedelta(days=162),
                "expiry_date": now + timedelta(days=200),
                "score": 96.0,
                "passing_score": 80.0,
                "certificate_id": "CERT-IP-012",
                "trainer": "Sponsor Drug Supply Manager",
                "created_at": now - timedelta(days=165),
            },
        ]

        for t in training_data:
            self._training[t["id"]] = TrainingCompliance(**t)

        # --- 12 Protocol Adherence Records ---
        adherence_data = [
            {
                "id": "PA-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "subject_id": "SUBJ-1001",
                "procedure_name": "Screening Visit Assessments",
                "visit_name": "Screening",
                "expected_date": now - timedelta(days=120),
                "actual_date": now - timedelta(days=120),
                "is_compliant": True,
                "reported_by": "Anna Chen",
                "reviewed_by": "Dr. Sarah Mitchell",
                "created_at": now - timedelta(days=118),
            },
            {
                "id": "PA-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "subject_id": "SUBJ-1001",
                "procedure_name": "Intravitreal Injection",
                "visit_name": "Day 1",
                "expected_date": now - timedelta(days=90),
                "actual_date": now - timedelta(days=90),
                "is_compliant": True,
                "reported_by": "Anna Chen",
                "reviewed_by": "Dr. Sarah Mitchell",
                "created_at": now - timedelta(days=88),
            },
            {
                "id": "PA-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "subject_id": "SUBJ-1030",
                "procedure_name": "Visual Acuity Assessment",
                "visit_name": "Week 4",
                "expected_date": now - timedelta(days=60),
                "actual_date": now - timedelta(days=55),
                "is_compliant": False,
                "deviation_type": "Visit Window Deviation",
                "deviation_description": "Visit completed 5 days outside protocol-specified window of +/- 3 days",
                "impact_assessment": "Minor impact on efficacy assessment; data still evaluable",
                "reported_by": "Site Coordinator",
                "reviewed_by": "David Park",
                "created_at": now - timedelta(days=53),
            },
            {
                "id": "PA-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "subject_id": "SUBJ-5010",
                "procedure_name": "Blood Draw for PK Analysis",
                "visit_name": "Week 8",
                "expected_date": now - timedelta(days=40),
                "actual_date": now - timedelta(days=40),
                "is_compliant": False,
                "deviation_type": "Procedural Deviation",
                "deviation_description": "PK sample collected 2 hours outside specified time window",
                "impact_assessment": "PK data point excluded from primary analysis",
                "reported_by": "Study Nurse",
                "reviewed_by": "Jennifer Lee",
                "created_at": now - timedelta(days=38),
            },
            {
                "id": "PA-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "subject_id": "SUBJ-5010",
                "procedure_name": "Concomitant Medication Review",
                "visit_name": "Week 12",
                "expected_date": now - timedelta(days=20),
                "actual_date": now - timedelta(days=20),
                "is_compliant": True,
                "reported_by": "Study Nurse",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "PA-006",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "subject_id": "SUBJ-7001",
                "procedure_name": "IV Infusion Administration",
                "visit_name": "Cycle 3 Day 1",
                "expected_date": now - timedelta(days=25),
                "actual_date": now - timedelta(days=20),
                "is_compliant": False,
                "deviation_type": "Visit Window Deviation",
                "deviation_description": "Treatment delayed 5 days beyond protocol window due to scheduling error",
                "impact_assessment": "Protocol deviation reported; subject continued in study per medical monitor approval",
                "reported_by": "Lisa Wang",
                "reviewed_by": "Dr. Robert Chen",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "PA-007",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "subject_id": "SUBJ-7002",
                "procedure_name": "Tumor Assessment CT Scan",
                "visit_name": "Week 12",
                "expected_date": now - timedelta(days=15),
                "actual_date": None,
                "is_compliant": False,
                "deviation_type": "Missed Procedure",
                "deviation_description": "CT scan not performed at required timepoint; subject did not attend visit",
                "impact_assessment": "Critical efficacy endpoint missing; protocol deviation reported",
                "reported_by": "Lisa Wang",
                "created_at": now - timedelta(days=13),
            },
            {
                "id": "PA-008",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "subject_id": "SUBJ-2005",
                "procedure_name": "Optical Coherence Tomography",
                "visit_name": "Week 8",
                "expected_date": now - timedelta(days=10),
                "actual_date": now - timedelta(days=10),
                "is_compliant": True,
                "reported_by": "Study Coordinator",
                "reviewed_by": "Dr. Alan Wright",
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "PA-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "subject_id": "SUBJ-6003",
                "procedure_name": "Informed Consent Re-consent",
                "visit_name": "Amendment Visit",
                "expected_date": now - timedelta(days=8),
                "actual_date": now - timedelta(days=8),
                "is_compliant": False,
                "deviation_type": "Consent Deviation",
                "deviation_description": "Subject re-consented with outdated consent version (v3.1 instead of v4.0)",
                "impact_assessment": "Subject must be re-consented with correct version; potential regulatory impact",
                "reported_by": "Study Coordinator",
                "reviewed_by": "Dr. Patricia Hayes",
                "created_at": now - timedelta(days=6),
            },
            {
                "id": "PA-010",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "subject_id": "SUBJ-4008",
                "procedure_name": "Spirometry Assessment",
                "visit_name": "Week 16",
                "expected_date": now - timedelta(days=5),
                "actual_date": now - timedelta(days=5),
                "is_compliant": True,
                "reported_by": "Study Coordinator",
                "reviewed_by": "Jennifer Lee",
                "created_at": now - timedelta(days=3),
            },
            {
                "id": "PA-011",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-108",
                "subject_id": "SUBJ-8001",
                "procedure_name": "Best Corrected Visual Acuity",
                "visit_name": "Week 4",
                "expected_date": now - timedelta(days=3),
                "actual_date": now - timedelta(days=3),
                "is_compliant": True,
                "reported_by": "Study Coordinator",
                "reviewed_by": "Dr. Karen Lee",
                "created_at": now - timedelta(days=1),
            },
            {
                "id": "PA-012",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "subject_id": "SUBJ-7003",
                "procedure_name": "ECG Assessment",
                "visit_name": "Cycle 2 Day 1",
                "expected_date": now - timedelta(days=2),
                "actual_date": now - timedelta(days=2),
                "is_compliant": False,
                "deviation_type": "Procedural Deviation",
                "deviation_description": "ECG performed post-dose instead of pre-dose as required by protocol",
                "impact_assessment": "Safety data may not reflect baseline cardiac status; documented as deviation",
                "reported_by": "Lisa Wang",
                "created_at": now - timedelta(days=1),
            },
        ]

        for a in adherence_data:
            self._adherence[a["id"]] = ProtocolAdherence(**a)

        # --- 10 Corrective Actions ---
        corrective_data = [
            {
                "id": "CAPA-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "finding_id": "CF-001",
                "action_description": "Retrain all CRAs on source data verification requirements per protocol",
                "action_type": "corrective",
                "assigned_to": "Dr. James Wilson",
                "status": FindingStatus.IN_REMEDIATION,
                "priority": FindingSeverity.MAJOR,
                "due_date": now + timedelta(days=14),
                "notes": "Training session scheduled for next week",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "CAPA-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "finding_id": "CF-001",
                "action_description": "Implement automated SDV tracking dashboard for real-time monitoring",
                "action_type": "preventive",
                "assigned_to": "Data Management Team",
                "status": FindingStatus.OPEN,
                "priority": FindingSeverity.MAJOR,
                "due_date": now + timedelta(days=30),
                "notes": "Dashboard development in progress",
                "created_at": now - timedelta(days=50),
            },
            {
                "id": "CAPA-003",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "finding_id": "CF-004",
                "action_description": "Update delegation log and designate backup safety reporter",
                "action_type": "corrective",
                "assigned_to": "Dr. Michael Torres",
                "status": FindingStatus.IN_REMEDIATION,
                "priority": FindingSeverity.CRITICAL,
                "due_date": now + timedelta(days=3),
                "notes": "Delegation log updated; backup reporter training in progress",
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "CAPA-004",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "finding_id": "CF-004",
                "action_description": "Implement automated SAE reporting alert system with 12-hour reminders",
                "action_type": "preventive",
                "assigned_to": "IT Systems Team",
                "status": FindingStatus.OPEN,
                "priority": FindingSeverity.CRITICAL,
                "due_date": now + timedelta(days=21),
                "created_at": now - timedelta(days=40),
            },
            {
                "id": "CAPA-005",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "finding_id": "CF-006",
                "action_description": "Implement visit scheduling system with automated window alerts",
                "action_type": "corrective",
                "assigned_to": "Site Coordinator Lisa Wang",
                "status": FindingStatus.OPEN,
                "priority": FindingSeverity.CRITICAL,
                "due_date": now + timedelta(days=10),
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "CAPA-006",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "finding_id": "CF-007",
                "action_description": "Develop and implement dose verification checklist for all protocol visits",
                "action_type": "corrective",
                "assigned_to": "Dr. Robert Chen",
                "status": FindingStatus.IN_REMEDIATION,
                "priority": FindingSeverity.CRITICAL,
                "due_date": now + timedelta(days=7),
                "notes": "Checklist drafted, pending PI review",
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "CAPA-007",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "finding_id": "CF-009",
                "action_description": "Re-consent all affected subjects with current consent version 4.0",
                "action_type": "corrective",
                "assigned_to": "Dr. Patricia Hayes",
                "status": FindingStatus.IN_REMEDIATION,
                "priority": FindingSeverity.CRITICAL,
                "due_date": now + timedelta(days=7),
                "notes": "3 of 5 subjects re-consented",
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "CAPA-008",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-106",
                "finding_id": "CF-009",
                "action_description": "Establish IRB approval notification workflow with mandatory acknowledgment",
                "action_type": "preventive",
                "assigned_to": "Regulatory Coordinator",
                "status": FindingStatus.OPEN,
                "priority": FindingSeverity.MAJOR,
                "due_date": now + timedelta(days=21),
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "CAPA-009",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "finding_id": "CF-010",
                "action_description": "Update IRB renewal tracking system with 30-day advance alerts",
                "action_type": "preventive",
                "assigned_to": "Regulatory Coordinator Maria Santos",
                "status": FindingStatus.VERIFIED,
                "priority": FindingSeverity.OBSERVATION,
                "due_date": now - timedelta(days=5),
                "completion_date": now - timedelta(days=7),
                "effectiveness_check_date": now + timedelta(days=60),
                "is_effective": True,
                "verified_by": "Sarah Mitchell",
                "created_at": now - timedelta(days=18),
            },
            {
                "id": "CAPA-010",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-104",
                "finding_id": "CF-011",
                "action_description": "Implement onboarding checklist that includes delegation log update requirement",
                "action_type": "preventive",
                "assigned_to": "Site Manager John Adams",
                "status": FindingStatus.CLOSED,
                "priority": FindingSeverity.MINOR,
                "due_date": now - timedelta(days=3),
                "completion_date": now - timedelta(days=5),
                "is_effective": True,
                "verified_by": "Jennifer Lee",
                "created_at": now - timedelta(days=12),
            },
        ]

        for c in corrective_data:
            self._corrective_actions[c["id"]] = CorrectiveAction(**c)

    # ------------------------------------------------------------------
    # Compliance Assessments
    # ------------------------------------------------------------------

    def list_assessments(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        compliance_area: ComplianceArea | None = None,
        rating: ComplianceRating | None = None,
    ) -> list[ComplianceAssessment]:
        """List compliance assessments with optional filters."""
        with self._lock:
            result = list(self._assessments.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if site_id is not None:
            result = [a for a in result if a.site_id == site_id]
        if compliance_area is not None:
            result = [a for a in result if a.compliance_area == compliance_area]
        if rating is not None:
            result = [a for a in result if a.rating == rating]

        return sorted(result, key=lambda a: a.assessment_date, reverse=True)

    def get_assessment(self, assessment_id: str) -> ComplianceAssessment | None:
        """Get a single compliance assessment by ID."""
        with self._lock:
            return self._assessments.get(assessment_id)

    def create_assessment(self, payload: ComplianceAssessmentCreate) -> ComplianceAssessment:
        """Create a new compliance assessment."""
        now = datetime.now(timezone.utc)
        assessment_id = f"CA-{uuid4().hex[:8].upper()}"
        assessment = ComplianceAssessment(
            id=assessment_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            compliance_area=payload.compliance_area,
            assessment_date=now,
            rating=payload.rating,
            score=payload.score,
            findings_count=0,
            critical_findings=0,
            assessor=payload.assessor,
            methodology=None,
            next_assessment_date=None,
            notes=None,
            created_at=now,
        )
        with self._lock:
            self._assessments[assessment_id] = assessment
        logger.info("Created compliance assessment %s for site %s", assessment_id, payload.site_id)
        return assessment

    def update_assessment(
        self, assessment_id: str, payload: ComplianceAssessmentUpdate
    ) -> ComplianceAssessment | None:
        """Update an existing compliance assessment."""
        with self._lock:
            existing = self._assessments.get(assessment_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ComplianceAssessment(**data)
            self._assessments[assessment_id] = updated
        return updated

    def delete_assessment(self, assessment_id: str) -> bool:
        """Delete a compliance assessment. Returns True if deleted."""
        with self._lock:
            if assessment_id in self._assessments:
                del self._assessments[assessment_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Compliance Findings
    # ------------------------------------------------------------------

    def list_findings(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        compliance_area: ComplianceArea | None = None,
        severity: FindingSeverity | None = None,
        status: FindingStatus | None = None,
    ) -> list[ComplianceFinding]:
        """List compliance findings with optional filters."""
        with self._lock:
            result = list(self._findings.values())

        if trial_id is not None:
            result = [f for f in result if f.trial_id == trial_id]
        if site_id is not None:
            result = [f for f in result if f.site_id == site_id]
        if compliance_area is not None:
            result = [f for f in result if f.compliance_area == compliance_area]
        if severity is not None:
            result = [f for f in result if f.severity == severity]
        if status is not None:
            result = [f for f in result if f.status == status]

        return sorted(result, key=lambda f: f.created_at, reverse=True)

    def get_finding(self, finding_id: str) -> ComplianceFinding | None:
        """Get a single compliance finding by ID."""
        with self._lock:
            return self._findings.get(finding_id)

    def create_finding(self, payload: ComplianceFindingCreate) -> ComplianceFinding:
        """Create a new compliance finding."""
        now = datetime.now(timezone.utc)
        finding_id = f"CF-{uuid4().hex[:8].upper()}"
        finding = ComplianceFinding(
            id=finding_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            assessment_id=payload.assessment_id,
            compliance_area=payload.compliance_area,
            finding_description=payload.finding_description,
            severity=payload.severity,
            status=FindingStatus.OPEN,
            responsible_person=payload.responsible_person,
            due_date=payload.due_date,
            days_open=0,
            created_at=now,
        )
        with self._lock:
            self._findings[finding_id] = finding
        logger.info("Created compliance finding %s for site %s", finding_id, payload.site_id)
        return finding

    def update_finding(
        self, finding_id: str, payload: ComplianceFindingUpdate
    ) -> ComplianceFinding | None:
        """Update a compliance finding."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._findings.get(finding_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set remediation_date when status goes to remediated
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = FindingStatus(new_status)
                if new_status == FindingStatus.REMEDIATED and existing.status != FindingStatus.REMEDIATED:
                    updates["remediation_date"] = now

            data.update(updates)
            updated = ComplianceFinding(**data)
            self._findings[finding_id] = updated
        return updated

    def delete_finding(self, finding_id: str) -> bool:
        """Delete a compliance finding. Returns True if deleted."""
        with self._lock:
            if finding_id in self._findings:
                del self._findings[finding_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Training Compliance
    # ------------------------------------------------------------------

    def list_training(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        status: TrainingStatus | None = None,
    ) -> list[TrainingCompliance]:
        """List training compliance records with optional filters."""
        with self._lock:
            result = list(self._training.values())

        if trial_id is not None:
            result = [t for t in result if t.trial_id == trial_id]
        if site_id is not None:
            result = [t for t in result if t.site_id == site_id]
        if status is not None:
            result = [t for t in result if t.status == status]

        return sorted(result, key=lambda t: t.created_at, reverse=True)

    def get_training(self, training_id: str) -> TrainingCompliance | None:
        """Get a single training compliance record by ID."""
        with self._lock:
            return self._training.get(training_id)

    def create_training(self, payload: TrainingComplianceCreate) -> TrainingCompliance:
        """Create a new training compliance record."""
        now = datetime.now(timezone.utc)
        training_id = f"TC-{uuid4().hex[:8].upper()}"
        training = TrainingCompliance(
            id=training_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            trainee_name=payload.trainee_name,
            trainee_role=payload.trainee_role,
            training_topic=payload.training_topic,
            training_type="initial",
            status=TrainingStatus.NOT_STARTED,
            required_date=payload.required_date,
            passing_score=80.0,
            created_at=now,
        )
        with self._lock:
            self._training[training_id] = training
        logger.info("Created training record %s for %s", training_id, payload.trainee_name)
        return training

    def update_training(
        self, training_id: str, payload: TrainingComplianceUpdate
    ) -> TrainingCompliance | None:
        """Update a training compliance record."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._training.get(training_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set completion_date when status goes to completed
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = TrainingStatus(new_status)
                if new_status == TrainingStatus.COMPLETED and existing.status != TrainingStatus.COMPLETED:
                    data["completion_date"] = now

            data.update(updates)
            updated = TrainingCompliance(**data)
            self._training[training_id] = updated
        return updated

    def delete_training(self, training_id: str) -> bool:
        """Delete a training compliance record. Returns True if deleted."""
        with self._lock:
            if training_id in self._training:
                del self._training[training_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Protocol Adherence
    # ------------------------------------------------------------------

    def list_adherence(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        is_compliant: bool | None = None,
    ) -> list[ProtocolAdherence]:
        """List protocol adherence records with optional filters."""
        with self._lock:
            result = list(self._adherence.values())

        if trial_id is not None:
            result = [a for a in result if a.trial_id == trial_id]
        if site_id is not None:
            result = [a for a in result if a.site_id == site_id]
        if is_compliant is not None:
            result = [a for a in result if a.is_compliant == is_compliant]

        return sorted(result, key=lambda a: a.created_at, reverse=True)

    def get_adherence(self, adherence_id: str) -> ProtocolAdherence | None:
        """Get a single protocol adherence record by ID."""
        with self._lock:
            return self._adherence.get(adherence_id)

    def create_adherence(self, payload: ProtocolAdherenceCreate) -> ProtocolAdherence:
        """Create a new protocol adherence record."""
        now = datetime.now(timezone.utc)
        adherence_id = f"PA-{uuid4().hex[:8].upper()}"
        adherence = ProtocolAdherence(
            id=adherence_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            subject_id=payload.subject_id,
            procedure_name=payload.procedure_name,
            visit_name=payload.visit_name,
            is_compliant=payload.is_compliant,
            reported_by=payload.reported_by,
            created_at=now,
        )
        with self._lock:
            self._adherence[adherence_id] = adherence
        logger.info("Created adherence record %s for site %s", adherence_id, payload.site_id)
        return adherence

    def update_adherence(
        self, adherence_id: str, payload: ProtocolAdherenceUpdate
    ) -> ProtocolAdherence | None:
        """Update a protocol adherence record."""
        with self._lock:
            existing = self._adherence.get(adherence_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = ProtocolAdherence(**data)
            self._adherence[adherence_id] = updated
        return updated

    def delete_adherence(self, adherence_id: str) -> bool:
        """Delete a protocol adherence record. Returns True if deleted."""
        with self._lock:
            if adherence_id in self._adherence:
                del self._adherence[adherence_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Corrective Actions
    # ------------------------------------------------------------------

    def list_corrective_actions(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        status: FindingStatus | None = None,
        priority: FindingSeverity | None = None,
    ) -> list[CorrectiveAction]:
        """List corrective actions with optional filters."""
        with self._lock:
            result = list(self._corrective_actions.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if site_id is not None:
            result = [c for c in result if c.site_id == site_id]
        if status is not None:
            result = [c for c in result if c.status == status]
        if priority is not None:
            result = [c for c in result if c.priority == priority]

        return sorted(result, key=lambda c: c.created_at, reverse=True)

    def get_corrective_action(self, action_id: str) -> CorrectiveAction | None:
        """Get a single corrective action by ID."""
        with self._lock:
            return self._corrective_actions.get(action_id)

    def create_corrective_action(self, payload: CorrectiveActionCreate) -> CorrectiveAction:
        """Create a new corrective action."""
        now = datetime.now(timezone.utc)
        action_id = f"CAPA-{uuid4().hex[:8].upper()}"
        action = CorrectiveAction(
            id=action_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            finding_id=payload.finding_id,
            action_description=payload.action_description,
            action_type="corrective",
            assigned_to=payload.assigned_to,
            status=FindingStatus.OPEN,
            priority=payload.priority,
            due_date=payload.due_date,
            created_at=now,
        )
        with self._lock:
            self._corrective_actions[action_id] = action
        logger.info("Created corrective action %s for site %s", action_id, payload.site_id)
        return action

    def update_corrective_action(
        self, action_id: str, payload: CorrectiveActionUpdate
    ) -> CorrectiveAction | None:
        """Update a corrective action."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._corrective_actions.get(action_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)

            # Auto-set completion_date when status goes to closed or verified
            if "status" in updates:
                new_status = updates["status"]
                if isinstance(new_status, str):
                    new_status = FindingStatus(new_status)
                if new_status in (FindingStatus.CLOSED, FindingStatus.VERIFIED) and existing.status not in (
                    FindingStatus.CLOSED, FindingStatus.VERIFIED
                ):
                    if data.get("completion_date") is None:
                        updates["completion_date"] = now

            data.update(updates)
            updated = CorrectiveAction(**data)
            self._corrective_actions[action_id] = updated
        return updated

    def delete_corrective_action(self, action_id: str) -> bool:
        """Delete a corrective action. Returns True if deleted."""
        with self._lock:
            if action_id in self._corrective_actions:
                del self._corrective_actions[action_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> ProtocolComplianceMetrics:
        """Compute aggregated protocol compliance metrics."""
        with self._lock:
            assessments = list(self._assessments.values())
            findings = list(self._findings.values())
            training = list(self._training.values())
            adherence = list(self._adherence.values())
            corrective_actions = list(self._corrective_actions.values())

        # Assessments by area
        assessments_by_area: dict[str, int] = {}
        for a in assessments:
            key = a.compliance_area.value
            assessments_by_area[key] = assessments_by_area.get(key, 0) + 1

        # Assessments by rating
        assessments_by_rating: dict[str, int] = {}
        for a in assessments:
            key = a.rating.value
            assessments_by_rating[key] = assessments_by_rating.get(key, 0) + 1

        # Average compliance score
        total_score = sum(a.score for a in assessments)
        avg_score = round(total_score / max(1, len(assessments)), 1)

        # Findings by severity
        findings_by_severity: dict[str, int] = {}
        for f in findings:
            key = f.severity.value
            findings_by_severity[key] = findings_by_severity.get(key, 0) + 1

        # Findings by status
        findings_by_status: dict[str, int] = {}
        for f in findings:
            key = f.status.value
            findings_by_status[key] = findings_by_status.get(key, 0) + 1

        # Open findings
        open_findings = sum(
            1 for f in findings
            if f.status in (FindingStatus.OPEN, FindingStatus.IN_REMEDIATION)
        )

        # Training by status
        training_by_status: dict[str, int] = {}
        for t in training:
            key = t.status.value
            training_by_status[key] = training_by_status.get(key, 0) + 1

        # Training completion percentage
        completed_training = sum(1 for t in training if t.status == TrainingStatus.COMPLETED)
        training_completion_pct = round(
            (completed_training / max(1, len(training))) * 100, 1
        )

        # Adherence rate
        compliant_count = sum(1 for a in adherence if a.is_compliant)
        adherence_rate = round(
            (compliant_count / max(1, len(adherence))) * 100, 1
        )

        # Open corrective actions
        open_corrective = sum(
            1 for c in corrective_actions
            if c.status in (FindingStatus.OPEN, FindingStatus.IN_REMEDIATION)
        )

        return ProtocolComplianceMetrics(
            total_assessments=len(assessments),
            assessments_by_area=assessments_by_area,
            assessments_by_rating=assessments_by_rating,
            avg_compliance_score=avg_score,
            total_findings=len(findings),
            findings_by_severity=findings_by_severity,
            findings_by_status=findings_by_status,
            open_findings=open_findings,
            total_training_records=len(training),
            training_by_status=training_by_status,
            training_completion_pct=training_completion_pct,
            total_adherence_records=len(adherence),
            adherence_rate=adherence_rate,
            total_corrective_actions=len(corrective_actions),
            open_corrective_actions=open_corrective,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ProtocolComplianceService | None = None
_instance_lock = threading.Lock()


def get_protocol_compliance_service() -> ProtocolComplianceService:
    """Return the singleton ProtocolComplianceService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ProtocolComplianceService()
    return _instance


def reset_protocol_compliance_service() -> ProtocolComplianceService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ProtocolComplianceService()
    return _instance
