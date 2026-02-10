"""Clinical Monitoring Service (CLINICAL-18).

Manages CRA monitoring visit scheduling, source data verification (SDV),
findings tracking, CAPA integration, monitoring reports, and metrics.

Usage:
    from app.services.clinical_monitoring_service import (
        get_clinical_monitoring_service,
    )

    svc = get_clinical_monitoring_service()
    visits = svc.list_visits()
    metrics = svc.get_monitoring_metrics()
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.clinical_monitoring import (
    CAPAItem,
    CAPAItemCreate,
    CAPAItemUpdate,
    CAPAStatus,
    FindingCategory,
    FindingSeverity,
    FindingStatus,
    MonitoringFinding,
    MonitoringFindingCreate,
    MonitoringFindingUpdate,
    MonitoringMetrics,
    MonitoringReport,
    MonitoringReportCreate,
    MonitoringReportUpdate,
    MonitoringVisit,
    MonitoringVisitCreate,
    MonitoringVisitUpdate,
    ReportStatus,
    SDVRecord,
    SDVRecordCreate,
    SDVSiteSummary,
    SDVStatus,
    SiteMonitoringSummary,
    VisitCompletePayload,
    VisitStartPayload,
    VisitStatus,
    VisitType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EYLEA_TRIAL = "00000000-de00-0001-0000-000000000001"
DUPIXENT_TRIAL = "00000000-de00-0002-0000-000000000002"
LIBTAYO_TRIAL = "00000000-de00-0003-0000-000000000003"


class ClinicalMonitoringService:
    """In-memory Clinical Monitoring engine.

    Thread-safe: all mutations are guarded by ``_lock``.
    """

    def __init__(self) -> None:
        self._visits: dict[str, MonitoringVisit] = {}
        self._findings: dict[str, MonitoringFinding] = {}
        self._sdv_records: dict[str, SDVRecord] = {}
        self._reports: dict[str, MonitoringReport] = {}
        self._capas: dict[str, CAPAItem] = {}
        self._lock = threading.Lock()
        self._seed_demo_data()

    # ------------------------------------------------------------------
    # Demo data
    # ------------------------------------------------------------------

    def _seed_demo_data(self) -> None:  # noqa: C901
        """Pre-populate realistic monitoring visit data across clinical trials."""
        now = datetime.now(timezone.utc)

        # --- 12 Monitoring Visits across multiple sites/trials ---
        visits_data = [
            # EYLEA - SITE-101: completed routine visit
            {
                "id": "MV-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "visit_type": VisitType.ROUTINE,
                "status": VisitStatus.COMPLETED,
                "cra_name": "Sarah Chen",
                "cra_id": "CRA-001",
                "scheduled_date": now - timedelta(days=30),
                "actual_start_date": now - timedelta(days=30),
                "actual_end_date": now - timedelta(days=29),
                "objectives": [
                    "Review informed consent forms",
                    "Verify source data for last 5 enrolled subjects",
                    "Check IP accountability log",
                    "Review AE/SAE reporting compliance",
                ],
                "notes": "Site performing well overall. Minor consent date discrepancy for 1 subject.",
                "created_at": now - timedelta(days=45),
            },
            # EYLEA - SITE-102: completed for-cause visit
            {
                "id": "MV-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "visit_type": VisitType.FOR_CAUSE,
                "status": VisitStatus.COMPLETED,
                "cra_name": "Michael Torres",
                "cra_id": "CRA-002",
                "scheduled_date": now - timedelta(days=21),
                "actual_start_date": now - timedelta(days=21),
                "actual_end_date": now - timedelta(days=20),
                "objectives": [
                    "Investigate high query rate for adverse event CRFs",
                    "Review data entry processes with site coordinator",
                    "Conduct 100% SDV on safety-related data",
                    "Assess need for retraining",
                ],
                "notes": "For-cause visit due to elevated query rate. Found systematic data entry errors by new coordinator.",
                "created_at": now - timedelta(days=28),
            },
            # EYLEA - SITE-103: in-progress routine visit
            {
                "id": "MV-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-103",
                "visit_type": VisitType.ROUTINE,
                "status": VisitStatus.IN_PROGRESS,
                "cra_name": "Sarah Chen",
                "cra_id": "CRA-001",
                "scheduled_date": now - timedelta(days=1),
                "actual_start_date": now - timedelta(days=1),
                "actual_end_date": None,
                "objectives": [
                    "Routine source data verification",
                    "Review regulatory binder updates",
                    "Verify protocol amendment implementation",
                    "Review enrollment progress",
                ],
                "notes": None,
                "created_at": now - timedelta(days=14),
            },
            # EYLEA - SITE-104: scheduled routine visit
            {
                "id": "MV-004",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-104",
                "visit_type": VisitType.ROUTINE,
                "status": VisitStatus.SCHEDULED,
                "cra_name": "Jennifer Park",
                "cra_id": "CRA-003",
                "scheduled_date": now + timedelta(days=14),
                "actual_start_date": None,
                "actual_end_date": None,
                "objectives": [
                    "Quarterly source data verification",
                    "IP accountability and temperature log review",
                    "Follow up on previous visit findings",
                ],
                "notes": None,
                "created_at": now - timedelta(days=7),
            },
            # DUPIXENT - SITE-105: completed remote visit
            {
                "id": "MV-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "visit_type": VisitType.REMOTE,
                "status": VisitStatus.COMPLETED,
                "cra_name": "David Kim",
                "cra_id": "CRA-004",
                "scheduled_date": now - timedelta(days=15),
                "actual_start_date": now - timedelta(days=15),
                "actual_end_date": now - timedelta(days=15),
                "objectives": [
                    "Remote review of eCRF completion status",
                    "Verify query resolution timeliness",
                    "Review enrollment milestones",
                ],
                "notes": "Remote monitoring via EDC system review. All queries resolved within SLA.",
                "created_at": now - timedelta(days=21),
            },
            # DUPIXENT - SITE-106: completed routine visit
            {
                "id": "MV-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-106",
                "visit_type": VisitType.ROUTINE,
                "status": VisitStatus.COMPLETED,
                "cra_name": "Lisa Martinez",
                "cra_id": "CRA-005",
                "scheduled_date": now - timedelta(days=10),
                "actual_start_date": now - timedelta(days=10),
                "actual_end_date": now - timedelta(days=9),
                "objectives": [
                    "Source data verification for 8 subjects",
                    "Review IP storage and dispensing logs",
                    "Check laboratory certification status",
                    "Assess site staff training documentation",
                ],
                "notes": "IP temperature excursion documented on 2025-12-15. CAPA initiated.",
                "created_at": now - timedelta(days=20),
            },
            # DUPIXENT - SITE-103: report pending
            {
                "id": "MV-007",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-103",
                "visit_type": VisitType.ROUTINE,
                "status": VisitStatus.REPORT_PENDING,
                "cra_name": "David Kim",
                "cra_id": "CRA-004",
                "scheduled_date": now - timedelta(days=5),
                "actual_start_date": now - timedelta(days=5),
                "actual_end_date": now - timedelta(days=4),
                "objectives": [
                    "Routine monitoring per monitoring plan",
                    "Review dose modification compliance",
                    "Verify PK sample handling and shipment",
                ],
                "notes": "Visit completed. Monitoring report in preparation.",
                "created_at": now - timedelta(days=12),
            },
            # LIBTAYO - SITE-107: confirmed triggered visit
            {
                "id": "MV-008",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-107",
                "visit_type": VisitType.TRIGGERED,
                "status": VisitStatus.CONFIRMED,
                "cra_name": "Michael Torres",
                "cra_id": "CRA-002",
                "scheduled_date": now + timedelta(days=3),
                "actual_start_date": None,
                "actual_end_date": None,
                "objectives": [
                    "Triggered by DSMB recommendation after safety signal",
                    "100% SDV on immune-related adverse events",
                    "Review concomitant medication records",
                    "Assess irAE management protocol adherence",
                ],
                "notes": "Triggered visit following DSMB safety review.",
                "created_at": now - timedelta(days=3),
            },
            # LIBTAYO - SITE-108: completed routine visit
            {
                "id": "MV-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-108",
                "visit_type": VisitType.ROUTINE,
                "status": VisitStatus.COMPLETED,
                "cra_name": "Jennifer Park",
                "cra_id": "CRA-003",
                "scheduled_date": now - timedelta(days=25),
                "actual_start_date": now - timedelta(days=25),
                "actual_end_date": now - timedelta(days=24),
                "objectives": [
                    "Quarterly routine monitoring",
                    "SDV for newly enrolled subjects",
                    "Regulatory document review",
                    "Staff delegation log update verification",
                ],
                "notes": "Site in compliance. New sub-investigator onboarded with proper training documentation.",
                "created_at": now - timedelta(days=35),
            },
            # LIBTAYO - SITE-105: scheduled closeout
            {
                "id": "MV-010",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-105",
                "visit_type": VisitType.CLOSEOUT,
                "status": VisitStatus.SCHEDULED,
                "cra_name": "Lisa Martinez",
                "cra_id": "CRA-005",
                "scheduled_date": now + timedelta(days=30),
                "actual_start_date": None,
                "actual_end_date": None,
                "objectives": [
                    "Final source data verification",
                    "Collect all outstanding CRF pages",
                    "Verify final IP accountability",
                    "Archive regulatory documents",
                    "Site closeout documentation",
                ],
                "notes": None,
                "created_at": now - timedelta(days=5),
            },
            # EYLEA - SITE-101: cancelled visit
            {
                "id": "MV-011",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "visit_type": VisitType.ROUTINE,
                "status": VisitStatus.CANCELLED,
                "cra_name": "Sarah Chen",
                "cra_id": "CRA-001",
                "scheduled_date": now - timedelta(days=60),
                "actual_start_date": None,
                "actual_end_date": None,
                "objectives": ["Routine monitoring"],
                "notes": "Cancelled due to site closure for facility maintenance.",
                "created_at": now - timedelta(days=75),
            },
            # DUPIXENT - SITE-106: scheduled triggered visit
            {
                "id": "MV-012",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-106",
                "visit_type": VisitType.TRIGGERED,
                "status": VisitStatus.SCHEDULED,
                "cra_name": "Lisa Martinez",
                "cra_id": "CRA-005",
                "scheduled_date": now + timedelta(days=7),
                "actual_start_date": None,
                "actual_end_date": None,
                "objectives": [
                    "Follow-up on IP temperature excursion CAPA",
                    "Verify corrective actions implemented",
                    "Review updated IP storage procedures",
                ],
                "notes": "Triggered by unresolved IP storage CAPA from MV-006.",
                "created_at": now - timedelta(days=2),
            },
        ]

        for v in visits_data:
            visit = MonitoringVisit(**v)
            self._visits[visit.id] = visit

        # --- Monitoring Findings ---
        findings_data = [
            # MV-001: Minor consent finding
            {
                "id": "MF-001",
                "visit_id": "MV-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "severity": FindingSeverity.MINOR,
                "category": FindingCategory.INFORMED_CONSENT,
                "status": FindingStatus.RESOLVED,
                "description": "Subject S-1042 consent form dated 2025-10-15 but screening visit documented on 2025-10-14. Consent obtained one day after initial screening procedures.",
                "corrective_action": "Re-consent subject at next visit. Retrain coordinator on consent timing requirements.",
                "response": "Subject re-consented on 2025-11-02. Coordinator completed retraining on 2025-11-05.",
                "response_due_date": now - timedelta(days=15),
                "resolved_date": now - timedelta(days=10),
                "capa_id": None,
                "created_at": now - timedelta(days=29),
            },
            # MV-002: Critical data entry findings
            {
                "id": "MF-002",
                "visit_id": "MV-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "severity": FindingSeverity.CRITICAL,
                "category": FindingCategory.DATA_ENTRY,
                "status": FindingStatus.RESPONSE_REQUIRED,
                "description": "Systematic transcription errors in adverse event severity grading. 12 of 45 AE records had incorrect CTCAE grades in eCRF compared to source documents. Grade 3 events recorded as Grade 1 in 4 cases.",
                "corrective_action": "Immediate 100% audit of all AE records. Correct all discrepant entries. Retrain all data entry staff on CTCAE grading. Implement double data entry for safety data.",
                "response": None,
                "response_due_date": now + timedelta(days=5),
                "resolved_date": None,
                "capa_id": "CAPA-001",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "MF-003",
                "visit_id": "MV-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "severity": FindingSeverity.MAJOR,
                "category": FindingCategory.SAFETY_REPORTING,
                "status": FindingStatus.RESPONSE_REQUIRED,
                "description": "Two SAEs reported beyond the 24-hour reporting window. SAE for Subject S-2018 reported 72 hours after onset. SAE for Subject S-2031 reported 48 hours after onset.",
                "corrective_action": "Submit late SAE reports with explanation to sponsor. Review SAE reporting procedures with PI and study team. Implement daily safety data review process.",
                "response": None,
                "response_due_date": now + timedelta(days=3),
                "resolved_date": None,
                "capa_id": "CAPA-002",
                "created_at": now - timedelta(days=20),
            },
            {
                "id": "MF-004",
                "visit_id": "MV-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "severity": FindingSeverity.MINOR,
                "category": FindingCategory.TRAINING,
                "status": FindingStatus.OPEN,
                "description": "New study coordinator (hired 2025-11-01) had not completed protocol-specific training module on adverse event classification before beginning data entry duties.",
                "corrective_action": "Complete all required training modules before resuming independent data entry. Provide supervised data entry period of 2 weeks after training.",
                "response": None,
                "response_due_date": now + timedelta(days=10),
                "resolved_date": None,
                "capa_id": None,
                "created_at": now - timedelta(days=20),
            },
            # MV-005: No findings (clean remote visit)
            # MV-006: IP management finding
            {
                "id": "MF-005",
                "visit_id": "MV-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-106",
                "severity": FindingSeverity.MAJOR,
                "category": FindingCategory.IP_MANAGEMENT,
                "status": FindingStatus.ESCALATED,
                "description": "Temperature excursion recorded for IP storage unit on 2025-12-15. Temperature reached 12.4C (acceptable range 2-8C) for approximately 4 hours. 15 vials of study drug potentially affected.",
                "corrective_action": "Quarantine affected vials. Contact sponsor for stability assessment. Review and upgrade temperature monitoring system. Install backup power supply.",
                "response": "Affected vials quarantined immediately. Sponsor stability assessment pending. New temperature monitoring system with SMS alerts ordered.",
                "response_due_date": now - timedelta(days=2),
                "resolved_date": None,
                "capa_id": "CAPA-003",
                "created_at": now - timedelta(days=9),
            },
            {
                "id": "MF-006",
                "visit_id": "MV-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-106",
                "severity": FindingSeverity.OBSERVATION,
                "category": FindingCategory.FACILITIES,
                "status": FindingStatus.RESOLVED,
                "description": "Pharmacy IP storage area access log not consistently maintained. 3 entries missing signatures in past month.",
                "corrective_action": "Remind pharmacy staff of access log requirements.",
                "response": "All staff reminded. Electronic access log system being evaluated.",
                "response_due_date": now - timedelta(days=3),
                "resolved_date": now - timedelta(days=4),
                "capa_id": None,
                "created_at": now - timedelta(days=9),
            },
            # MV-009: Routine finding
            {
                "id": "MF-007",
                "visit_id": "MV-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-108",
                "severity": FindingSeverity.MINOR,
                "category": FindingCategory.REGULATORY,
                "status": FindingStatus.RESOLVED,
                "description": "Updated CV for sub-investigator Dr. Patel not filed in regulatory binder within 30 days of update as required by SOP.",
                "corrective_action": "File updated CV immediately. Review filing timelines with regulatory coordinator.",
                "response": "CV filed. Regulatory coordinator implemented tickler system for document updates.",
                "response_due_date": now - timedelta(days=10),
                "resolved_date": now - timedelta(days=12),
                "capa_id": None,
                "created_at": now - timedelta(days=24),
            },
            # Additional finding for metrics
            {
                "id": "MF-008",
                "visit_id": "MV-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "severity": FindingSeverity.OBSERVATION,
                "category": FindingCategory.SOURCE_DATA,
                "status": FindingStatus.RESOLVED,
                "description": "Source document filing system could be improved. Lab results filed chronologically rather than by subject, making SDV less efficient.",
                "corrective_action": "Consider reorganizing source document filing by subject.",
                "response": "Site has transitioned to subject-based filing system.",
                "response_due_date": now - timedelta(days=14),
                "resolved_date": now - timedelta(days=16),
                "capa_id": None,
                "created_at": now - timedelta(days=29),
            },
        ]

        for f in findings_data:
            finding = MonitoringFinding(**f)
            self._findings[finding.id] = finding

        # --- SDV Records ---
        sdv_data = [
            # MV-001 SDV records (SITE-101)
            {
                "id": "SDV-001", "visit_id": "MV-001", "trial_id": EYLEA_TRIAL, "site_id": "SITE-101",
                "subject_id": "S-1040", "form": "Demographics", "field": "Date of Birth",
                "status": SDVStatus.VERIFIED, "source_verified": True, "discrepancy_noted": False,
                "verified_by": "Sarah Chen", "verified_date": now - timedelta(days=30),
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SDV-002", "visit_id": "MV-001", "trial_id": EYLEA_TRIAL, "site_id": "SITE-101",
                "subject_id": "S-1040", "form": "Vital Signs", "field": "Blood Pressure",
                "status": SDVStatus.VERIFIED, "source_verified": True, "discrepancy_noted": False,
                "verified_by": "Sarah Chen", "verified_date": now - timedelta(days=30),
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SDV-003", "visit_id": "MV-001", "trial_id": EYLEA_TRIAL, "site_id": "SITE-101",
                "subject_id": "S-1041", "form": "Adverse Events", "field": "AE Start Date",
                "status": SDVStatus.VERIFIED, "source_verified": True, "discrepancy_noted": False,
                "verified_by": "Sarah Chen", "verified_date": now - timedelta(days=30),
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SDV-004", "visit_id": "MV-001", "trial_id": EYLEA_TRIAL, "site_id": "SITE-101",
                "subject_id": "S-1042", "form": "Informed Consent", "field": "Consent Date",
                "status": SDVStatus.DISCREPANCY, "source_verified": False, "discrepancy_noted": True,
                "discrepancy_description": "Consent date on CRF is 2025-10-15 but source shows 2025-10-14",
                "verified_by": "Sarah Chen", "verified_date": now - timedelta(days=30),
                "created_at": now - timedelta(days=30),
            },
            {
                "id": "SDV-005", "visit_id": "MV-001", "trial_id": EYLEA_TRIAL, "site_id": "SITE-101",
                "subject_id": "S-1043", "form": "Lab Results", "field": "Hemoglobin",
                "status": SDVStatus.VERIFIED, "source_verified": True, "discrepancy_noted": False,
                "verified_by": "Sarah Chen", "verified_date": now - timedelta(days=29),
                "created_at": now - timedelta(days=29),
            },
            # MV-002 SDV records (SITE-102) - for-cause visit, higher SDV rate
            {
                "id": "SDV-006", "visit_id": "MV-002", "trial_id": EYLEA_TRIAL, "site_id": "SITE-102",
                "subject_id": "S-2018", "form": "Adverse Events", "field": "AE Severity Grade",
                "status": SDVStatus.DISCREPANCY, "source_verified": False, "discrepancy_noted": True,
                "discrepancy_description": "Source shows Grade 3, CRF entry shows Grade 1",
                "verified_by": "Michael Torres", "verified_date": now - timedelta(days=21),
                "created_at": now - timedelta(days=21),
            },
            {
                "id": "SDV-007", "visit_id": "MV-002", "trial_id": EYLEA_TRIAL, "site_id": "SITE-102",
                "subject_id": "S-2019", "form": "Adverse Events", "field": "AE Severity Grade",
                "status": SDVStatus.DISCREPANCY, "source_verified": False, "discrepancy_noted": True,
                "discrepancy_description": "Source shows Grade 2, CRF entry shows Grade 1",
                "verified_by": "Michael Torres", "verified_date": now - timedelta(days=21),
                "created_at": now - timedelta(days=21),
            },
            {
                "id": "SDV-008", "visit_id": "MV-002", "trial_id": EYLEA_TRIAL, "site_id": "SITE-102",
                "subject_id": "S-2020", "form": "Concomitant Meds", "field": "Medication Name",
                "status": SDVStatus.VERIFIED, "source_verified": True, "discrepancy_noted": False,
                "verified_by": "Michael Torres", "verified_date": now - timedelta(days=21),
                "created_at": now - timedelta(days=21),
            },
            {
                "id": "SDV-009", "visit_id": "MV-002", "trial_id": EYLEA_TRIAL, "site_id": "SITE-102",
                "subject_id": "S-2021", "form": "Vital Signs", "field": "Heart Rate",
                "status": SDVStatus.VERIFIED, "source_verified": True, "discrepancy_noted": False,
                "verified_by": "Michael Torres", "verified_date": now - timedelta(days=20),
                "created_at": now - timedelta(days=20),
            },
            # MV-006 SDV records (SITE-106)
            {
                "id": "SDV-010", "visit_id": "MV-006", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-106",
                "subject_id": "S-6010", "form": "IP Dispensing", "field": "Lot Number",
                "status": SDVStatus.VERIFIED, "source_verified": True, "discrepancy_noted": False,
                "verified_by": "Lisa Martinez", "verified_date": now - timedelta(days=10),
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "SDV-011", "visit_id": "MV-006", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-106",
                "subject_id": "S-6011", "form": "Lab Results", "field": "IgE Level",
                "status": SDVStatus.VERIFIED, "source_verified": True, "discrepancy_noted": False,
                "verified_by": "Lisa Martinez", "verified_date": now - timedelta(days=10),
                "created_at": now - timedelta(days=10),
            },
            {
                "id": "SDV-012", "visit_id": "MV-006", "trial_id": DUPIXENT_TRIAL, "site_id": "SITE-106",
                "subject_id": "S-6012", "form": "EASI Score", "field": "Total Score",
                "status": SDVStatus.VERIFIED, "source_verified": True, "discrepancy_noted": False,
                "verified_by": "Lisa Martinez", "verified_date": now - timedelta(days=9),
                "created_at": now - timedelta(days=9),
            },
            # MV-009 SDV records (SITE-108)
            {
                "id": "SDV-013", "visit_id": "MV-009", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-108",
                "subject_id": "S-8001", "form": "Tumor Assessment", "field": "RECIST Response",
                "status": SDVStatus.VERIFIED, "source_verified": True, "discrepancy_noted": False,
                "verified_by": "Jennifer Park", "verified_date": now - timedelta(days=25),
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "SDV-014", "visit_id": "MV-009", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-108",
                "subject_id": "S-8002", "form": "Immunotherapy AE", "field": "irAE Grade",
                "status": SDVStatus.VERIFIED, "source_verified": True, "discrepancy_noted": False,
                "verified_by": "Jennifer Park", "verified_date": now - timedelta(days=25),
                "created_at": now - timedelta(days=25),
            },
            {
                "id": "SDV-015", "visit_id": "MV-009", "trial_id": LIBTAYO_TRIAL, "site_id": "SITE-108",
                "subject_id": "S-8003", "form": "Lab Results", "field": "Thyroid Panel",
                "status": SDVStatus.VERIFIED, "source_verified": True, "discrepancy_noted": False,
                "verified_by": "Jennifer Park", "verified_date": now - timedelta(days=24),
                "created_at": now - timedelta(days=24),
            },
        ]

        for s in sdv_data:
            rec = SDVRecord(**s)
            self._sdv_records[rec.id] = rec

        # --- Monitoring Reports ---
        reports_data = [
            {
                "id": "MR-001",
                "visit_id": "MV-001",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-101",
                "status": ReportStatus.APPROVED,
                "summary": "Routine monitoring visit completed successfully. Site performance is satisfactory. One minor informed consent date discrepancy identified for Subject S-1042 and addressed. SDV completed for 5 subjects with 80% verification rate. IP accountability records are up to date. No protocol deviations identified.",
                "findings_count": 2,
                "critical_findings": 0,
                "major_findings": 0,
                "sdv_rate": 80.0,
                "subjects_reviewed": 5,
                "follow_up_items": [
                    "Confirm re-consent for Subject S-1042 at next visit",
                    "Verify coordinator training completion",
                ],
                "submitted_date": now - timedelta(days=27),
                "approved_date": now - timedelta(days=25),
                "created_at": now - timedelta(days=28),
            },
            {
                "id": "MR-002",
                "visit_id": "MV-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "status": ReportStatus.SUBMITTED,
                "summary": "For-cause monitoring visit conducted due to elevated query rate for AE CRFs. Investigation revealed systematic data entry errors by newly hired coordinator who had not completed required training. Critical finding: 12 of 45 AE records had incorrect CTCAE severity grades. Two SAE reports submitted beyond 24-hour window. Immediate corrective actions initiated including 100% data audit and staff retraining.",
                "findings_count": 3,
                "critical_findings": 1,
                "major_findings": 1,
                "sdv_rate": 100.0,
                "subjects_reviewed": 15,
                "follow_up_items": [
                    "Verify 100% AE record audit completion within 2 weeks",
                    "Confirm coordinator training completion",
                    "Review implementation of double data entry for safety data",
                    "Follow up on CAPA-001 and CAPA-002 progress",
                ],
                "submitted_date": now - timedelta(days=18),
                "approved_date": None,
                "created_at": now - timedelta(days=19),
            },
            {
                "id": "MR-003",
                "visit_id": "MV-006",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-106",
                "status": ReportStatus.REVIEWED,
                "summary": "Routine monitoring visit identified IP temperature excursion on 2025-12-15. 15 vials of study drug potentially affected and quarantined. Sponsor stability assessment requested. CAPA initiated for IP storage improvements. General site compliance is satisfactory for non-IP areas.",
                "findings_count": 2,
                "critical_findings": 0,
                "major_findings": 1,
                "sdv_rate": 100.0,
                "subjects_reviewed": 8,
                "follow_up_items": [
                    "Obtain sponsor stability assessment result",
                    "Verify new temperature monitoring system installation",
                    "Review CAPA-003 implementation at next visit",
                ],
                "submitted_date": now - timedelta(days=7),
                "approved_date": None,
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "MR-004",
                "visit_id": "MV-009",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-108",
                "status": ReportStatus.APPROVED,
                "summary": "Quarterly routine monitoring visit. Site in overall compliance. New sub-investigator Dr. Patel onboarded with complete training documentation. Minor regulatory filing delay for CV update addressed. SDV completed for 6 subjects with no discrepancies. irAE management consistent with protocol requirements.",
                "findings_count": 1,
                "critical_findings": 0,
                "major_findings": 0,
                "sdv_rate": 100.0,
                "subjects_reviewed": 6,
                "follow_up_items": [
                    "Confirm regulatory filing tickler system operational",
                ],
                "submitted_date": now - timedelta(days=22),
                "approved_date": now - timedelta(days=20),
                "created_at": now - timedelta(days=23),
            },
            {
                "id": "MR-005",
                "visit_id": "MV-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-105",
                "status": ReportStatus.APPROVED,
                "summary": "Remote monitoring visit via EDC system review. All queries resolved within SLA. eCRF completion rate at 95%. No safety signals identified during remote data review. Enrollment on track with milestones.",
                "findings_count": 0,
                "critical_findings": 0,
                "major_findings": 0,
                "sdv_rate": 0.0,
                "subjects_reviewed": 0,
                "follow_up_items": [],
                "submitted_date": now - timedelta(days=13),
                "approved_date": now - timedelta(days=11),
                "created_at": now - timedelta(days=14),
            },
        ]

        for r in reports_data:
            report = MonitoringReport(**r)
            self._reports[report.id] = report

        # --- CAPA Items ---
        capas_data = [
            {
                "id": "CAPA-001",
                "finding_id": "MF-002",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "status": CAPAStatus.IN_PROGRESS,
                "root_cause": "Newly hired study coordinator began independent data entry duties before completing required CTCAE training module. Supervisory oversight gap during onboarding period.",
                "corrective_action": "1) Complete 100% audit of all AE records entered by new coordinator. 2) Correct all discrepant CTCAE grades. 3) Implement mandatory supervised data entry period for new staff. 4) Establish double data entry process for all safety-related CRF data.",
                "preventive_action": "1) Update onboarding checklist to include training verification before system access. 2) Implement role-based EDC permissions (no independent safety data entry until training complete). 3) Quarterly quality review of AE data entry accuracy across all staff.",
                "responsible_party": "Site PI - Dr. Rebecca Wong",
                "due_date": now + timedelta(days=14),
                "completion_date": None,
                "verification_date": None,
                "effectiveness_check": None,
                "created_at": now - timedelta(days=19),
            },
            {
                "id": "CAPA-002",
                "finding_id": "MF-003",
                "trial_id": EYLEA_TRIAL,
                "site_id": "SITE-102",
                "status": CAPAStatus.OPEN,
                "root_cause": "Inadequate SAE reporting procedures at site. No daily safety data review process in place. PI not promptly notified of new AEs by study team.",
                "corrective_action": "1) Submit late SAE notification reports to sponsor with full explanation. 2) Implement daily safety data review by PI or delegate. 3) Create SAE reporting checklist with real-time tracking.",
                "preventive_action": "1) Establish automated alert system for new AE entries requiring PI review. 2) Weekly safety data review meetings with study team. 3) Annual SAE reporting refresher training for all study staff.",
                "responsible_party": "Site PI - Dr. Rebecca Wong",
                "due_date": now + timedelta(days=7),
                "completion_date": None,
                "verification_date": None,
                "effectiveness_check": None,
                "created_at": now - timedelta(days=19),
            },
            {
                "id": "CAPA-003",
                "finding_id": "MF-005",
                "trial_id": DUPIXENT_TRIAL,
                "site_id": "SITE-106",
                "status": CAPAStatus.IN_PROGRESS,
                "root_cause": "Single-point-of-failure temperature monitoring system without redundancy. Backup power supply not installed for pharmacy refrigerator. Temperature monitoring alarm only checked during business hours.",
                "corrective_action": "1) Quarantine all potentially affected study drug vials. 2) Request sponsor stability assessment for affected lot. 3) Install dual-probe temperature monitoring system with 24/7 SMS alerting. 4) Install UPS backup power for pharmacy refrigerator.",
                "preventive_action": "1) Implement redundant temperature monitoring across all IP storage locations. 2) Establish 24/7 temperature alarm response protocol. 3) Quarterly preventive maintenance for refrigeration equipment. 4) Annual emergency preparedness drill including power failure scenarios.",
                "responsible_party": "Pharmacy Director - Dr. Thomas Lee",
                "due_date": now + timedelta(days=21),
                "completion_date": None,
                "verification_date": None,
                "effectiveness_check": None,
                "created_at": now - timedelta(days=8),
            },
            {
                "id": "CAPA-004",
                "finding_id": "MF-007",
                "trial_id": LIBTAYO_TRIAL,
                "site_id": "SITE-108",
                "status": CAPAStatus.CLOSED,
                "root_cause": "No systematic tracking of regulatory document update deadlines. Regulatory coordinator relied on manual calendar reminders.",
                "corrective_action": "Implemented electronic tickler system with automated reminders at 14, 7, and 1 day before filing deadlines.",
                "preventive_action": "Monthly regulatory document completeness audit. Backup coordinator assigned for regulatory filing duties.",
                "responsible_party": "Regulatory Coordinator - Maria Santos",
                "due_date": now - timedelta(days=8),
                "completion_date": now - timedelta(days=10),
                "verification_date": now - timedelta(days=5),
                "effectiveness_check": "Verified tickler system operational. All regulatory documents current as of verification date.",
                "created_at": now - timedelta(days=22),
            },
        ]

        for c in capas_data:
            capa = CAPAItem(**c)
            self._capas[capa.id] = capa

    # ------------------------------------------------------------------
    # Visit CRUD
    # ------------------------------------------------------------------

    def list_visits(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        visit_type: VisitType | None = None,
        status: VisitStatus | None = None,
        cra_id: str | None = None,
    ) -> list[MonitoringVisit]:
        """List monitoring visits with optional filters."""
        with self._lock:
            result = list(self._visits.values())

        if trial_id is not None:
            result = [v for v in result if v.trial_id == trial_id]
        if site_id is not None:
            result = [v for v in result if v.site_id == site_id]
        if visit_type is not None:
            result = [v for v in result if v.visit_type == visit_type]
        if status is not None:
            result = [v for v in result if v.status == status]
        if cra_id is not None:
            result = [v for v in result if v.cra_id == cra_id]

        return sorted(result, key=lambda v: v.scheduled_date, reverse=True)

    def get_visit(self, visit_id: str) -> MonitoringVisit | None:
        """Get a single monitoring visit by ID."""
        with self._lock:
            return self._visits.get(visit_id)

    def create_visit(self, payload: MonitoringVisitCreate) -> MonitoringVisit:
        """Create a new monitoring visit."""
        now = datetime.now(timezone.utc)
        visit_id = f"MV-{uuid4().hex[:8].upper()}"
        visit = MonitoringVisit(
            id=visit_id,
            trial_id=payload.trial_id,
            site_id=payload.site_id,
            visit_type=payload.visit_type,
            status=VisitStatus.SCHEDULED,
            cra_name=payload.cra_name,
            cra_id=payload.cra_id,
            scheduled_date=payload.scheduled_date,
            actual_start_date=None,
            actual_end_date=None,
            objectives=payload.objectives,
            notes=payload.notes,
            created_at=now,
        )
        with self._lock:
            self._visits[visit_id] = visit
        logger.info("Created monitoring visit %s for site %s", visit_id, payload.site_id)
        return visit

    def update_visit(self, visit_id: str, payload: MonitoringVisitUpdate) -> MonitoringVisit | None:
        """Update an existing monitoring visit."""
        with self._lock:
            existing = self._visits.get(visit_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MonitoringVisit(**data)
            self._visits[visit_id] = updated
        return updated

    def delete_visit(self, visit_id: str) -> bool:
        """Delete a monitoring visit. Returns True if deleted."""
        with self._lock:
            if visit_id in self._visits:
                del self._visits[visit_id]
                return True
            return False

    # ------------------------------------------------------------------
    # Visit Lifecycle
    # ------------------------------------------------------------------

    def schedule_visit(self, payload: MonitoringVisitCreate) -> MonitoringVisit:
        """Schedule a new monitoring visit (alias for create_visit)."""
        return self.create_visit(payload)

    def start_visit(self, visit_id: str, payload: VisitStartPayload) -> MonitoringVisit | None:
        """Start a monitoring visit."""
        with self._lock:
            existing = self._visits.get(visit_id)
            if existing is None:
                return None
            if existing.status not in (VisitStatus.SCHEDULED, VisitStatus.CONFIRMED):
                raise ValueError(
                    f"Visit '{visit_id}' cannot be started from status '{existing.status.value}'"
                )
            data = existing.model_dump()
            data["status"] = VisitStatus.IN_PROGRESS
            data["actual_start_date"] = payload.actual_start_date
            updated = MonitoringVisit(**data)
            self._visits[visit_id] = updated
        logger.info("Started monitoring visit %s", visit_id)
        return updated

    def complete_visit(self, visit_id: str, payload: VisitCompletePayload) -> MonitoringVisit | None:
        """Complete a monitoring visit."""
        with self._lock:
            existing = self._visits.get(visit_id)
            if existing is None:
                return None
            if existing.status != VisitStatus.IN_PROGRESS:
                raise ValueError(
                    f"Visit '{visit_id}' cannot be completed from status '{existing.status.value}'"
                )
            data = existing.model_dump()
            data["status"] = VisitStatus.COMPLETED
            data["actual_end_date"] = payload.actual_end_date
            updated = MonitoringVisit(**data)
            self._visits[visit_id] = updated
        logger.info("Completed monitoring visit %s", visit_id)
        return updated

    def cancel_visit(self, visit_id: str) -> MonitoringVisit | None:
        """Cancel a monitoring visit."""
        with self._lock:
            existing = self._visits.get(visit_id)
            if existing is None:
                return None
            if existing.status in (VisitStatus.COMPLETED, VisitStatus.CANCELLED):
                raise ValueError(
                    f"Visit '{visit_id}' cannot be cancelled from status '{existing.status.value}'"
                )
            data = existing.model_dump()
            data["status"] = VisitStatus.CANCELLED
            updated = MonitoringVisit(**data)
            self._visits[visit_id] = updated
        logger.info("Cancelled monitoring visit %s", visit_id)
        return updated

    def confirm_visit(self, visit_id: str) -> MonitoringVisit | None:
        """Confirm a scheduled monitoring visit."""
        with self._lock:
            existing = self._visits.get(visit_id)
            if existing is None:
                return None
            if existing.status != VisitStatus.SCHEDULED:
                raise ValueError(
                    f"Visit '{visit_id}' cannot be confirmed from status '{existing.status.value}'"
                )
            data = existing.model_dump()
            data["status"] = VisitStatus.CONFIRMED
            updated = MonitoringVisit(**data)
            self._visits[visit_id] = updated
        logger.info("Confirmed monitoring visit %s", visit_id)
        return updated

    # ------------------------------------------------------------------
    # Findings CRUD
    # ------------------------------------------------------------------

    def list_findings(
        self,
        *,
        visit_id: str | None = None,
        trial_id: str | None = None,
        site_id: str | None = None,
        severity: FindingSeverity | None = None,
        category: FindingCategory | None = None,
        status: FindingStatus | None = None,
    ) -> list[MonitoringFinding]:
        """List monitoring findings with optional filters."""
        with self._lock:
            result = list(self._findings.values())

        if visit_id is not None:
            result = [f for f in result if f.visit_id == visit_id]
        if trial_id is not None:
            result = [f for f in result if f.trial_id == trial_id]
        if site_id is not None:
            result = [f for f in result if f.site_id == site_id]
        if severity is not None:
            result = [f for f in result if f.severity == severity]
        if category is not None:
            result = [f for f in result if f.category == category]
        if status is not None:
            result = [f for f in result if f.status == status]

        return sorted(result, key=lambda f: f.created_at, reverse=True)

    def get_finding(self, finding_id: str) -> MonitoringFinding | None:
        """Get a single finding by ID."""
        with self._lock:
            return self._findings.get(finding_id)

    def create_finding(self, payload: MonitoringFindingCreate) -> MonitoringFinding:
        """Create a new monitoring finding."""
        now = datetime.now(timezone.utc)
        finding_id = f"MF-{uuid4().hex[:8].upper()}"

        with self._lock:
            visit = self._visits.get(payload.visit_id)
            if visit is None:
                raise ValueError(f"Visit '{payload.visit_id}' not found")

            finding = MonitoringFinding(
                id=finding_id,
                visit_id=payload.visit_id,
                trial_id=visit.trial_id,
                site_id=visit.site_id,
                severity=payload.severity,
                category=payload.category,
                status=FindingStatus.OPEN,
                description=payload.description,
                corrective_action=payload.corrective_action,
                response=None,
                response_due_date=payload.response_due_date,
                resolved_date=None,
                capa_id=None,
                created_at=now,
            )
            self._findings[finding_id] = finding
        logger.info("Created finding %s for visit %s", finding_id, payload.visit_id)
        return finding

    def update_finding(self, finding_id: str, payload: MonitoringFindingUpdate) -> MonitoringFinding | None:
        """Update an existing finding."""
        with self._lock:
            existing = self._findings.get(finding_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MonitoringFinding(**data)
            self._findings[finding_id] = updated
        return updated

    def resolve_finding(self, finding_id: str) -> MonitoringFinding | None:
        """Mark a finding as resolved."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._findings.get(finding_id)
            if existing is None:
                return None
            if existing.status == FindingStatus.RESOLVED:
                raise ValueError(f"Finding '{finding_id}' is already resolved")
            data = existing.model_dump()
            data["status"] = FindingStatus.RESOLVED
            data["resolved_date"] = now
            updated = MonitoringFinding(**data)
            self._findings[finding_id] = updated
        logger.info("Resolved finding %s", finding_id)
        return updated

    def escalate_finding(self, finding_id: str) -> MonitoringFinding | None:
        """Escalate a finding."""
        with self._lock:
            existing = self._findings.get(finding_id)
            if existing is None:
                return None
            if existing.status in (FindingStatus.RESOLVED, FindingStatus.ESCALATED):
                raise ValueError(
                    f"Finding '{finding_id}' cannot be escalated from status '{existing.status.value}'"
                )
            data = existing.model_dump()
            data["status"] = FindingStatus.ESCALATED
            updated = MonitoringFinding(**data)
            self._findings[finding_id] = updated
        logger.info("Escalated finding %s", finding_id)
        return updated

    # ------------------------------------------------------------------
    # SDV Records
    # ------------------------------------------------------------------

    def list_sdv_records(
        self,
        *,
        visit_id: str | None = None,
        trial_id: str | None = None,
        site_id: str | None = None,
        subject_id: str | None = None,
        status: SDVStatus | None = None,
    ) -> list[SDVRecord]:
        """List SDV records with optional filters."""
        with self._lock:
            result = list(self._sdv_records.values())

        if visit_id is not None:
            result = [r for r in result if r.visit_id == visit_id]
        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if site_id is not None:
            result = [r for r in result if r.site_id == site_id]
        if subject_id is not None:
            result = [r for r in result if r.subject_id == subject_id]
        if status is not None:
            result = [r for r in result if r.status == status]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_sdv_record(self, sdv_id: str) -> SDVRecord | None:
        """Get a single SDV record by ID."""
        with self._lock:
            return self._sdv_records.get(sdv_id)

    def record_sdv(self, payload: SDVRecordCreate) -> SDVRecord:
        """Create a new SDV record."""
        now = datetime.now(timezone.utc)
        sdv_id = f"SDV-{uuid4().hex[:8].upper()}"

        with self._lock:
            visit = self._visits.get(payload.visit_id)
            if visit is None:
                raise ValueError(f"Visit '{payload.visit_id}' not found")

            sdv_status = SDVStatus.PENDING
            if payload.source_verified:
                sdv_status = SDVStatus.VERIFIED
            if payload.discrepancy_noted:
                sdv_status = SDVStatus.DISCREPANCY

            rec = SDVRecord(
                id=sdv_id,
                visit_id=payload.visit_id,
                trial_id=visit.trial_id,
                site_id=visit.site_id,
                subject_id=payload.subject_id,
                form=payload.form,
                field=payload.field,
                status=sdv_status,
                source_verified=payload.source_verified,
                discrepancy_noted=payload.discrepancy_noted,
                discrepancy_description=payload.discrepancy_description,
                verified_by=visit.cra_name,
                verified_date=now if payload.source_verified or payload.discrepancy_noted else None,
                created_at=now,
            )
            self._sdv_records[sdv_id] = rec
        logger.info("Recorded SDV %s for visit %s", sdv_id, payload.visit_id)
        return rec

    def get_sdv_rate_by_site(self, site_id: str) -> float:
        """Calculate SDV verification rate for a site."""
        with self._lock:
            records = [r for r in self._sdv_records.values() if r.site_id == site_id]

        if not records:
            return 0.0

        verified = sum(1 for r in records if r.source_verified)
        return round((verified / len(records)) * 100.0, 1)

    def get_sdv_summary(self) -> list[SDVSiteSummary]:
        """Get SDV summary across all sites."""
        with self._lock:
            records = list(self._sdv_records.values())

        site_data: dict[str, dict] = {}
        for rec in records:
            if rec.site_id not in site_data:
                site_data[rec.site_id] = {
                    "total": 0,
                    "verified": 0,
                    "discrepancy": 0,
                }
            site_data[rec.site_id]["total"] += 1
            if rec.source_verified:
                site_data[rec.site_id]["verified"] += 1
            if rec.discrepancy_noted:
                site_data[rec.site_id]["discrepancy"] += 1

        summaries = []
        for site_id, data in sorted(site_data.items()):
            rate = round((data["verified"] / max(1, data["total"])) * 100.0, 1)
            summaries.append(
                SDVSiteSummary(
                    site_id=site_id,
                    total_records=data["total"],
                    verified_count=data["verified"],
                    discrepancy_count=data["discrepancy"],
                    sdv_rate=rate,
                )
            )
        return summaries

    # ------------------------------------------------------------------
    # Monitoring Reports
    # ------------------------------------------------------------------

    def list_reports(
        self,
        *,
        visit_id: str | None = None,
        trial_id: str | None = None,
        site_id: str | None = None,
        status: ReportStatus | None = None,
    ) -> list[MonitoringReport]:
        """List monitoring reports with optional filters."""
        with self._lock:
            result = list(self._reports.values())

        if visit_id is not None:
            result = [r for r in result if r.visit_id == visit_id]
        if trial_id is not None:
            result = [r for r in result if r.trial_id == trial_id]
        if site_id is not None:
            result = [r for r in result if r.site_id == site_id]
        if status is not None:
            result = [r for r in result if r.status == status]

        return sorted(result, key=lambda r: r.created_at, reverse=True)

    def get_report(self, report_id: str) -> MonitoringReport | None:
        """Get a single monitoring report by ID."""
        with self._lock:
            return self._reports.get(report_id)

    def create_report(self, payload: MonitoringReportCreate) -> MonitoringReport:
        """Create a monitoring report for a visit."""
        now = datetime.now(timezone.utc)
        report_id = f"MR-{uuid4().hex[:8].upper()}"

        with self._lock:
            visit = self._visits.get(payload.visit_id)
            if visit is None:
                raise ValueError(f"Visit '{payload.visit_id}' not found")

            # Compute findings counts from actual findings
            visit_findings = [f for f in self._findings.values() if f.visit_id == payload.visit_id]
            critical = sum(1 for f in visit_findings if f.severity == FindingSeverity.CRITICAL)
            major = sum(1 for f in visit_findings if f.severity == FindingSeverity.MAJOR)

            # Compute SDV rate from actual records
            visit_sdv = [r for r in self._sdv_records.values() if r.visit_id == payload.visit_id]
            sdv_total = len(visit_sdv)
            sdv_verified = sum(1 for r in visit_sdv if r.source_verified)
            sdv_rate = round((sdv_verified / max(1, sdv_total)) * 100.0, 1) if sdv_total > 0 else 0.0

            report = MonitoringReport(
                id=report_id,
                visit_id=payload.visit_id,
                trial_id=visit.trial_id,
                site_id=visit.site_id,
                status=ReportStatus.DRAFT,
                summary=payload.summary,
                findings_count=len(visit_findings),
                critical_findings=critical,
                major_findings=major,
                sdv_rate=sdv_rate,
                subjects_reviewed=len({r.subject_id for r in visit_sdv}),
                follow_up_items=payload.follow_up_items,
                submitted_date=None,
                approved_date=None,
                created_at=now,
            )
            self._reports[report_id] = report

            # Update visit status to report_pending if completed
            if visit.status == VisitStatus.COMPLETED:
                data = visit.model_dump()
                data["status"] = VisitStatus.REPORT_PENDING
                self._visits[visit.id] = MonitoringVisit(**data)

        logger.info("Created monitoring report %s for visit %s", report_id, payload.visit_id)
        return report

    def update_report(self, report_id: str, payload: MonitoringReportUpdate) -> MonitoringReport | None:
        """Update a monitoring report."""
        with self._lock:
            existing = self._reports.get(report_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = MonitoringReport(**data)
            self._reports[report_id] = updated
        return updated

    def submit_report(self, report_id: str, submitted_date: datetime) -> MonitoringReport | None:
        """Submit a monitoring report."""
        with self._lock:
            existing = self._reports.get(report_id)
            if existing is None:
                return None
            if existing.status != ReportStatus.DRAFT:
                raise ValueError(
                    f"Report '{report_id}' cannot be submitted from status '{existing.status.value}'"
                )
            data = existing.model_dump()
            data["status"] = ReportStatus.SUBMITTED
            data["submitted_date"] = submitted_date
            updated = MonitoringReport(**data)
            self._reports[report_id] = updated
        logger.info("Submitted monitoring report %s", report_id)
        return updated

    def approve_report(self, report_id: str) -> MonitoringReport | None:
        """Approve a monitoring report."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._reports.get(report_id)
            if existing is None:
                return None
            if existing.status not in (ReportStatus.SUBMITTED, ReportStatus.REVIEWED):
                raise ValueError(
                    f"Report '{report_id}' cannot be approved from status '{existing.status.value}'"
                )
            data = existing.model_dump()
            data["status"] = ReportStatus.APPROVED
            data["approved_date"] = now
            updated = MonitoringReport(**data)
            self._reports[report_id] = updated
        logger.info("Approved monitoring report %s", report_id)
        return updated

    # ------------------------------------------------------------------
    # CAPA Items
    # ------------------------------------------------------------------

    def list_capas(
        self,
        *,
        trial_id: str | None = None,
        site_id: str | None = None,
        status: CAPAStatus | None = None,
        finding_id: str | None = None,
    ) -> list[CAPAItem]:
        """List CAPA items with optional filters."""
        with self._lock:
            result = list(self._capas.values())

        if trial_id is not None:
            result = [c for c in result if c.trial_id == trial_id]
        if site_id is not None:
            result = [c for c in result if c.site_id == site_id]
        if status is not None:
            result = [c for c in result if c.status == status]
        if finding_id is not None:
            result = [c for c in result if c.finding_id == finding_id]

        return sorted(result, key=lambda c: c.created_at, reverse=True)

    def get_capa(self, capa_id: str) -> CAPAItem | None:
        """Get a single CAPA item by ID."""
        with self._lock:
            return self._capas.get(capa_id)

    def create_capa(self, payload: CAPAItemCreate) -> CAPAItem:
        """Create a new CAPA item."""
        now = datetime.now(timezone.utc)
        capa_id = f"CAPA-{uuid4().hex[:8].upper()}"

        with self._lock:
            finding = self._findings.get(payload.finding_id)
            if finding is None:
                raise ValueError(f"Finding '{payload.finding_id}' not found")

            capa = CAPAItem(
                id=capa_id,
                finding_id=payload.finding_id,
                trial_id=finding.trial_id,
                site_id=finding.site_id,
                status=CAPAStatus.OPEN,
                root_cause=payload.root_cause,
                corrective_action=payload.corrective_action,
                preventive_action=payload.preventive_action,
                responsible_party=payload.responsible_party,
                due_date=payload.due_date,
                completion_date=None,
                verification_date=None,
                effectiveness_check=None,
                created_at=now,
            )
            self._capas[capa_id] = capa

            # Link finding to CAPA
            f_data = finding.model_dump()
            f_data["capa_id"] = capa_id
            self._findings[payload.finding_id] = MonitoringFinding(**f_data)

        logger.info("Created CAPA %s for finding %s", capa_id, payload.finding_id)
        return capa

    def update_capa(self, capa_id: str, payload: CAPAItemUpdate) -> CAPAItem | None:
        """Update a CAPA item."""
        with self._lock:
            existing = self._capas.get(capa_id)
            if existing is None:
                return None
            data = existing.model_dump()
            updates = payload.model_dump(exclude_unset=True)
            data.update(updates)
            updated = CAPAItem(**data)
            self._capas[capa_id] = updated
        return updated

    def close_capa(self, capa_id: str, effectiveness_check: str) -> CAPAItem | None:
        """Close a CAPA item with effectiveness verification."""
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._capas.get(capa_id)
            if existing is None:
                return None
            if existing.status == CAPAStatus.CLOSED:
                raise ValueError(f"CAPA '{capa_id}' is already closed")
            data = existing.model_dump()
            data["status"] = CAPAStatus.CLOSED
            data["completion_date"] = now
            data["verification_date"] = now
            data["effectiveness_check"] = effectiveness_check
            updated = CAPAItem(**data)
            self._capas[capa_id] = updated
        logger.info("Closed CAPA %s", capa_id)
        return updated

    # ------------------------------------------------------------------
    # Metrics & Summaries
    # ------------------------------------------------------------------

    def get_monitoring_metrics(self) -> MonitoringMetrics:
        """Compute aggregated monitoring metrics across all trials."""
        with self._lock:
            visits = list(self._visits.values())
            findings = list(self._findings.values())
            sdv_records = list(self._sdv_records.values())
            capas = list(self._capas.values())
            reports = list(self._reports.values())

        # Visits
        visits_completed = sum(1 for v in visits if v.status == VisitStatus.COMPLETED)
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for v in visits:
            by_type[v.visit_type.value] = by_type.get(v.visit_type.value, 0) + 1
            by_status[v.status.value] = by_status.get(v.status.value, 0) + 1

        # Findings
        open_findings = sum(
            1 for f in findings if f.status not in (FindingStatus.RESOLVED,)
        )
        by_severity: dict[str, int] = {}
        by_category: dict[str, int] = {}
        for f in findings:
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
            by_category[f.category.value] = by_category.get(f.category.value, 0) + 1

        # SDV
        sdv_verified = sum(1 for r in sdv_records if r.source_verified)
        overall_sdv_rate = (
            round((sdv_verified / len(sdv_records)) * 100.0, 1) if sdv_records else 0.0
        )

        # CAPAs
        open_capas = sum(
            1 for c in capas if c.status not in (CAPAStatus.CLOSED,)
        )
        closed_capas = sum(1 for c in capas if c.status == CAPAStatus.CLOSED)
        capa_closure_rate = (
            round((closed_capas / len(capas)) * 100.0, 1) if capas else 0.0
        )

        # Reports
        reports_pending = sum(
            1 for r in reports if r.status in (ReportStatus.DRAFT, ReportStatus.SUBMITTED)
        )

        return MonitoringMetrics(
            total_visits=len(visits),
            visits_completed=visits_completed,
            visits_by_type=by_type,
            visits_by_status=by_status,
            total_findings=len(findings),
            open_findings=open_findings,
            findings_by_severity=by_severity,
            findings_by_category=by_category,
            overall_sdv_rate=overall_sdv_rate,
            total_sdv_records=len(sdv_records),
            total_capas=len(capas),
            open_capas=open_capas,
            capa_closure_rate=capa_closure_rate,
            total_reports=len(reports),
            reports_pending_review=reports_pending,
        )

    def get_site_monitoring_summary(
        self, site_id: str, trial_id: str | None = None,
    ) -> SiteMonitoringSummary | None:
        """Get monitoring summary for a specific site."""
        with self._lock:
            visits = [v for v in self._visits.values() if v.site_id == site_id]
            if trial_id:
                visits = [v for v in visits if v.trial_id == trial_id]

            if not visits:
                return None

            actual_trial_id = trial_id or visits[0].trial_id
            findings = [
                f for f in self._findings.values()
                if f.site_id == site_id and (trial_id is None or f.trial_id == trial_id)
            ]
            sdv_records = [
                r for r in self._sdv_records.values()
                if r.site_id == site_id and (trial_id is None or r.trial_id == trial_id)
            ]
            capas = [
                c for c in self._capas.values()
                if c.site_id == site_id and (trial_id is None or c.trial_id == trial_id)
            ]

        completed = [v for v in visits if v.status == VisitStatus.COMPLETED]
        open_findings = sum(1 for f in findings if f.status != FindingStatus.RESOLVED)
        critical = sum(
            1 for f in findings
            if f.severity == FindingSeverity.CRITICAL and f.status != FindingStatus.RESOLVED
        )
        verified = sum(1 for r in sdv_records if r.source_verified)
        sdv_rate = round((verified / max(1, len(sdv_records))) * 100.0, 1) if sdv_records else 0.0
        open_capas = sum(1 for c in capas if c.status != CAPAStatus.CLOSED)

        last_visit_date = None
        if completed:
            last = max(completed, key=lambda v: v.actual_end_date or v.scheduled_date)
            last_visit_date = last.actual_end_date or last.scheduled_date

        return SiteMonitoringSummary(
            site_id=site_id,
            trial_id=actual_trial_id,
            total_visits=len(visits),
            completed_visits=len(completed),
            open_findings=open_findings,
            critical_findings=critical,
            sdv_rate=sdv_rate,
            open_capas=open_capas,
            last_visit_date=last_visit_date,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: ClinicalMonitoringService | None = None
_instance_lock = threading.Lock()


def get_clinical_monitoring_service() -> ClinicalMonitoringService:
    """Return the singleton ClinicalMonitoringService instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = ClinicalMonitoringService()
    return _instance


def reset_clinical_monitoring_service() -> ClinicalMonitoringService:
    """Reset the singleton (for testing).

    Creates a fresh instance with re-seeded demo data.
    """
    global _instance
    with _instance_lock:
        _instance = ClinicalMonitoringService()
    return _instance
